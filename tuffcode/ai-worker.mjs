// Tuff AI's model, Pumice 1, runs here, in an Electron utility process, so a crash in the native model code
// can't take the IDE down with it. ai.js starts this file and talks to it with messages:
//   in:  load {modelPath, gpu, contextSize, threads?}
//        chat {runId, system, prompt, maxTokens, thinking, budget, temperature, topK?, topP?, stop?}
//        followup {runId, prompt, maxTokens, budget, temperature, topK?, topP?, stop?}
//        stop {runId}
//   out: loaded {gpu, device} · delta {runId, text} · thinking {runId, text} · thought {runId, ms, tokens, cut}
//        done {runId, ok, text, error, stopped, thought, tokens} · failed {error}
// What Phase 1 measured (tuff-ai/bakeoff) shapes this file:
// - useMmap is off: on the CPU, memory-mapping costs ~500 MB more for no speed gain.
// - Qwen3.5 is a hybrid model that can't rewind its memory, so a new chat would re-read the whole system
//   prompt. It's evaluated once and checkpointed, and every new chat is cut back to that point.
// - The 2B gets stuck in thinking loops. With thinking off (the Off level) it's told not to think at all
//   (thoughts: 'discourage', a budget of 0). The other levels let it think, but only up to a hard budget of
//   thought tokens: past it, node-llama-cpp closes the thought and the model has to answer.
// A chat that thinks and one that doesn't render the model's turn differently, so each has its own chat
// session. Both share the one sequence and the system prompt read into it, so switching costs nothing.
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const port = process.parentPort;
let lib = null;
let llama = null;
let model = null;
let context = null;
let sequence = null;
let sessions = {}; // 'plain' (no thinking) and 'think': chat sessions on the one sequence
let session = null; // the one the current chat uses
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

async function load({ modelPath, gpu = 'auto', contextSize = 8192, threads }) {
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
  context = await model.createContext({ contextSize, ...(threads ? { threads } : {}) });
  sequence = context.getSequence();
  post({ type: 'loaded', gpu: llama.gpu || 'cpu', device });
}

function makeSession(system, thinking) {
  const { LlamaChatSession, QwenChatWrapper } = lib;
  const qwen = /qwen/i.test(path.basename(modelFile));
  const wrapper = qwen ? { chatWrapper: new QwenChatWrapper({ variation: '3.5', thoughts: thinking ? 'auto' : 'discourage' }) } : {};
  return new LlamaChatSession({ contextSequence: sequence, systemPrompt: system, ...wrapper });
}

// A fresh chat that shares the system prompt with the last one only reads the new message.
async function newChat(system, thinking) {
  const kind = thinking ? 'think' : 'plain';
  if (system !== systemText) {
    for (const s of Object.values(sessions)) s.dispose?.({ disposeSequence: false });
    sessions = {};
    systemText = system;
    prefix = 0;
    if (sequence.nextTokenIndex > 0) await sequence.eraseContextTokenRanges([{ start: 0, end: sequence.nextTokenIndex }]);
    sessions[kind] = makeSession(system, thinking);
    if (sequence.needsCheckpoints) {
      // Both kinds of chat render the system prompt and the start of the question the same way.
      const render = (text) => sessions[kind].chatWrapper.generateContextState({ chatHistory: [{ type: 'system', text: system }, { type: 'user', text }, { type: 'model', response: [] }] }).contextText.tokenize(model.tokenizer);
      const a = render('A'), b = render('B');
      while (prefix < a.length && a[prefix] === b[prefix]) prefix++;
      await sequence.evaluateWithoutGeneratingNewTokens(a.slice(0, prefix));
      await sequence.takeCheckpoint();
    }
  }
  sessions[kind] = sessions[kind] || makeSession(system, thinking);
  session = sessions[kind];
  session.resetChatHistory();
  if (prefix && sequence.nextTokenIndex > prefix) await sequence.eraseContextTokenRanges([{ start: prefix, end: sequence.nextTokenIndex }]);
}

// budget: how many tokens it may think for (0: not at all). maxTokens is for the answer, so the thinking
// gets its budget on top. stop: text that ends the answer early (the plan stops at a code block).
async function answer(runId, { prompt, maxTokens = 700, budget = 0, temperature = 0.2, topK, topP, stop }) {
  if (stopped.delete(runId)) { post({ type: 'done', runId, ok: false, text: '', stopped: true }); return; }
  const abort = new AbortController();
  current = { runId, abort };
  const th = { start: 0, ms: 0, tokens: 0, open: false };
  const thought = () => (th.start ? { ms: th.ms, tokens: th.tokens, cut: budget > 0 && th.tokens >= budget } : null);
  const endThought = () => {
    if (!th.open) return;
    th.open = false;
    th.ms = Date.now() - th.start;
    post({ type: 'thought', runId, ...thought() });
  };
  const before = { in: sequence.tokenMeter.usedInputTokens, out: sequence.tokenMeter.usedOutputTokens };
  const tokens = () => ({ in: sequence.tokenMeter.usedInputTokens - before.in, out: sequence.tokenMeter.usedOutputTokens - before.out });
  try {
    const text = await session.prompt(prompt, {
      maxTokens: maxTokens + budget,
      temperature,
      ...(topK ? { topK } : {}),
      ...(topP ? { topP } : {}),
      ...(stop?.length ? { customStopTriggers: stop } : {}),
      budgets: { thoughtTokens: budget },
      signal: abort.signal,
      stopOnAbortSignal: true,
      onResponseChunk: (c) => {
        if (c.type === 'segment' && c.segmentType === 'thought') {
          if (!th.start) th.start = Date.now();
          th.open = true;
          th.tokens += c.tokens?.length || 0;
          if (c.text) post({ type: 'thinking', runId, text: c.text });
        } else if (c.type === undefined && c.text) {
          endThought();
          post({ type: 'delta', runId, text: c.text });
        }
      },
    });
    endThought();
    if (sequence.needsCheckpoints) await sequence.takeCheckpoint();
    post({ type: 'done', runId, ok: !abort.signal.aborted, text, stopped: abort.signal.aborted, thought: thought(), tokens: tokens() });
  } catch (err) {
    endThought();
    post({ type: 'done', runId, ok: false, error: String(err?.message || err), thought: thought() });
  } finally {
    if (current?.runId === runId) current = null;
  }
}

// A stop for a question that's still waiting its turn (or whose chat is still being set up) is kept,
// and the question is skipped when its turn comes.
const stopped = new Set();
let queue = Promise.resolve();
port.on('message', (e) => {
  const msg = e.data;
  if (msg.type === 'stop') {
    if (current?.runId === msg.runId) current.abort.abort();
    else {
      stopped.add(msg.runId);
      if (stopped.size > 50) stopped.delete(stopped.values().next().value);
    }
    return;
  }
  // Everything else runs one at a time, in order.
  queue = queue.then(async () => {
    try {
      if (msg.type === 'load') await load(msg);
      else if (msg.type === 'chat') { if (!stopped.has(msg.runId)) await newChat(msg.system, !!msg.thinking); await answer(msg.runId, msg); }
      else if (msg.type === 'followup') await answer(msg.runId, msg);
    } catch (err) {
      if (msg.runId) post({ type: 'done', runId: msg.runId, ok: false, error: String(err?.message || err) });
      else post({ type: 'failed', error: String(err?.message || err) });
    }
  });
});
