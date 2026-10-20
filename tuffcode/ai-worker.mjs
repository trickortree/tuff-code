// Tuff AI's model runs here, in an Electron utility process, so a crash in the native model code can't
// take the IDE down with it. ai.js starts this file and talks to it with messages:
//   in:  load {modelPath, gpu, contextSize} · chat {runId, system, prompt, maxTokens} · followup {runId, prompt} · stop {runId}
//   out: loaded {gpu, device} · delta {runId, text} · done {runId, ok, text, error} · failed {error}
// What Phase 1 measured (tuff-ai/bakeoff) shapes this file:
// - useMmap is off: on the CPU, memory-mapping costs ~500 MB more for no speed gain.
// - Qwen3.5 is a hybrid model that can't rewind its memory, so a new chat would re-read the whole system
//   prompt. It's evaluated once and checkpointed, and every new chat is cut back to that point.
// - Thinking is off (Qwen3.5's 2B gets stuck in thinking loops).
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const port = process.parentPort;
let lib = null;
let llama = null;
let model = null;
let context = null;
let sequence = null;
let session = null;
let systemText = null;
let prefix = 0;
let current = null; // { runId, abort }
let modelFile = '';

const post = (msg) => port.postMessage(msg);

async function loadLib() {
  if (lib) return lib;
  // Development copies can point at a separate node-llama-cpp install (tuff-ai/README.md).
  const dir = process.env.TUFFCODE_LLAMA_RUNTIME;
  lib = await import(dir ? pathToFileURL(path.join(dir, 'node_modules', 'node-llama-cpp', 'dist', 'index.js')).href : 'node-llama-cpp');
  return lib;
}

// Integrated Intel graphics run small models slower than the CPU, and some give garbled output over Vulkan.
const WEAK_GPU = /Intel\(R\) (UHD|HD|Iris)|Microsoft Basic/i;

async function load({ modelPath, gpu = 'auto', contextSize = 8192 }) {
  const { getLlama } = await loadLib();
  llama = await getLlama({ gpu: gpu === 'cpu' ? false : 'auto', build: 'never', logLevel: 'error' });
  let device = '';
  if (llama.gpu) {
    device = (await llama.getGpuDeviceNames().catch(() => [])).join(', ');
    if (gpu === 'auto' && llama.gpu === 'vulkan' && (!device || WEAK_GPU.test(device))) {
      await llama.dispose();
      llama = await getLlama({ gpu: false, build: 'never', logLevel: 'error' });
      device = '';
    }
  }
  model = await llama.loadModel({ modelPath, useMmap: false });
  modelFile = modelPath;
  context = await model.createContext({ contextSize });
  sequence = context.getSequence();
  post({ type: 'loaded', gpu: llama.gpu || 'cpu', device });
}

function wrapper() {
  const { QwenChatWrapper } = lib;
  return /qwen/i.test(path.basename(modelFile)) ? { chatWrapper: new QwenChatWrapper({ variation: '3.5', thoughts: 'discourage' }) } : {};
}

// A fresh chat that shares the system prompt with the last one only reads the new message.
async function newChat(system) {
  const { LlamaChatSession } = lib;
  if (system !== systemText) {
    session?.dispose?.({ disposeSequence: false });
    session = new LlamaChatSession({ contextSequence: sequence, systemPrompt: system, ...wrapper() });
    systemText = system;
    prefix = 0;
    if (sequence.nextTokenIndex > 0) await sequence.eraseContextTokenRanges([{ start: 0, end: sequence.nextTokenIndex }]);
    if (sequence.needsCheckpoints) {
      const render = (text) => session.chatWrapper.generateContextState({ chatHistory: [{ type: 'system', text: system }, { type: 'user', text }, { type: 'model', response: [] }] }).contextText.tokenize(model.tokenizer);
      const a = render('A'), b = render('B');
      while (prefix < a.length && a[prefix] === b[prefix]) prefix++;
      await sequence.evaluateWithoutGeneratingNewTokens(a.slice(0, prefix));
      await sequence.takeCheckpoint();
    }
  } else {
    session.resetChatHistory();
    if (prefix && sequence.nextTokenIndex > prefix) await sequence.eraseContextTokenRanges([{ start: prefix, end: sequence.nextTokenIndex }]);
  }
}

async function answer(runId, prompt, maxTokens) {
  const abort = new AbortController();
  current = { runId, abort };
  try {
    const text = await session.prompt(prompt, {
      maxTokens,
      temperature: 0.2,
      budgets: { thoughtTokens: 0 },
      signal: abort.signal,
      stopOnAbortSignal: true,
      onTextChunk: (t) => post({ type: 'delta', runId, text: t }),
    });
    if (sequence.needsCheckpoints) await sequence.takeCheckpoint();
    post({ type: 'done', runId, ok: !abort.signal.aborted, text, stopped: abort.signal.aborted });
  } catch (err) {
    post({ type: 'done', runId, ok: false, error: String(err?.message || err) });
  } finally {
    if (current?.runId === runId) current = null;
  }
}

let queue = Promise.resolve();
port.on('message', (e) => {
  const msg = e.data;
  if (msg.type === 'stop') { if (current?.runId === msg.runId) current.abort.abort(); return; }
  // Everything else runs one at a time, in order.
  queue = queue.then(async () => {
    try {
      if (msg.type === 'load') await load(msg);
      else if (msg.type === 'chat') { await newChat(msg.system); await answer(msg.runId, msg.prompt, msg.maxTokens || 700); }
      else if (msg.type === 'followup') await answer(msg.runId, msg.prompt, msg.maxTokens || 700);
    } catch (err) {
      if (msg.runId) post({ type: 'done', runId: msg.runId, ok: false, error: String(err?.message || err) });
      else post({ type: 'failed', error: String(err?.message || err) });
    }
  });
});
