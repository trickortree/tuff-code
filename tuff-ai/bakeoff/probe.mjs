// Speed, memory and prompt-reuse probes for the bake-off.
//   node tuff-ai/bakeoff/probe.mjs --model <file.gguf> [--runtime <dir>] --what speed [--threads 4]
//   node tuff-ai/bakeoff/probe.mjs --model <file.gguf> [--runtime <dir>] --what reuse [--checkpoint-interval 512]
// speed: prompt reading speed on ~1,000 tokens of the guide, and writing speed on ~200 tokens, both from cold.
// reuse: the whole guide as the system prompt, then 3 new chats and 1 follow-up; prints how many tokens each
//        one had to read, which shows whether the shared system prompt is reused.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const MODEL = arg('model');
const WHAT = arg('what', 'speed');
const THREADS = Number(arg('threads', 8));
const CKPT = arg('checkpoint-interval');
const MMAP = arg('mmap', 'on') !== 'off';
const runtime = arg('runtime');
const { getLlama, LlamaChatSession, QwenChatWrapper } = await import(runtime ? pathToFileURL(path.join(runtime, 'node_modules', 'node-llama-cpp', 'dist', 'index.js')).href : 'node-llama-cpp');

const guide = fs.readFileSync(path.join(ROOT, 'tuffcode', 'mcp', 'tuff-guide.md'), 'utf8').replace(/\r\n/g, '\n').split(/\n(?=## Using the tools)/)[0];
let peak = 0;
const sampler = setInterval(() => { peak = Math.max(peak, process.memoryUsage().rss); }, 50);
const llama = await getLlama({ gpu: false, build: 'never', logLevel: 'error' });
const model = await llama.loadModel({ modelPath: MODEL, useMmap: MMAP });
const isQwen = /qwen/i.test(MODEL);
const wrapper = () => (isQwen ? { chatWrapper: new QwenChatWrapper({ variation: '3.5', thoughts: 'discourage' }) } : {});
const out = { model: path.basename(MODEL), what: WHAT, threads: THREADS, mmap: MMAP, checkpointInterval: CKPT ? Number(CKPT) : 'default' };

async function timed(session, seq, fn) {
  const i0 = seq.tokenMeter.usedInputTokens, o0 = seq.tokenMeter.usedOutputTokens;
  const t0 = Date.now();
  let first = 0;
  await fn(() => { if (!first) first = Date.now(); });
  const t1 = Date.now();
  return { inTok: seq.tokenMeter.usedInputTokens - i0, outTok: seq.tokenMeter.usedOutputTokens - o0, ms: t1 - t0, firstMs: first ? first - t0 : t1 - t0, genMs: first ? t1 - first : 0 };
}

if (WHAT === 'speed') {
  const ctx = await model.createContext({ contextSize: 4096, threads: THREADS, ...(arg("batch") ? { batchSize: Number(arg("batch")) } : {}) });
  const seq = ctx.getSequence();
  const s = new LlamaChatSession({ contextSequence: seq, ...wrapper() });
  // Prompt reading: ~1,000 tokens of the guide, evaluated without answering.
  const text = guide.slice(0, 4200);
  const pre = await timed(s, seq, () => s.preloadPrompt(text));
  out.promptTokens = pre.inTok;
  out.promptTps = Math.round(pre.inTok / (pre.ms / 1000));
  // Writing: a long, easy answer.
  s.resetChatHistory();
  const gen = await timed(s, seq, (onFirst) => s.prompt('Write the whole numbers from 1 to 400, separated by commas, and nothing else.', { maxTokens: 200, temperature: 0, budgets: { thoughtTokens: 0 }, onTextChunk: onFirst }));
  out.genTokens = gen.outTok;
  out.genTps = Math.round(((gen.outTok - 1) / (gen.genMs / 1000)) * 10) / 10;
  await ctx.dispose();
} else if (WHAT === 'reuse-manual') {
  // The workaround for hybrid models: evaluate exactly the shared opening, checkpoint it, and before each
  // new chat cut the memory back to that point, so only the new message is read.
  const ctx = await model.createContext({ contextSize: 12288, threads: THREADS });
  const seq = ctx.getSequence();
  const SYS = `You are Tuff AI. Answer in one short sentence.\n\n${guide}`;
  const s = new LlamaChatSession({ contextSequence: seq, systemPrompt: SYS, ...wrapper() });
  const render = (history) => s.chatWrapper.generateContextState({ chatHistory: history }).contextText.tokenize(model.tokenizer);
  const a = render([{ type: 'system', text: SYS }, { type: 'user', text: 'A' }, { type: 'model', response: [] }]);
  const b = render([{ type: 'system', text: SYS }, { type: 'user', text: 'B' }, { type: 'model', response: [] }]);
  let P = 0;
  while (P < a.length && a[P] === b[P]) P++;
  const t0 = Date.now();
  await seq.evaluateWithoutGeneratingNewTokens(a.slice(0, P));
  await seq.takeCheckpoint();
  out.prefixTokens = P;
  out.prefixMs = Date.now() - t0;
  out.chats = [];
  const qs = ['How do I show text on the screen?', 'How do I make a list of three names?', 'What does round(2.5) give?'];
  for (const q of qs) {
    s.resetChatHistory();
    if (seq.nextTokenIndex > P) await seq.eraseContextTokenRanges([{ start: P, end: seq.nextTokenIndex }]);
    const r = await timed(s, seq, (onFirst) => s.prompt(q, { maxTokens: 40, temperature: 0, budgets: { thoughtTokens: 0 }, onTextChunk: onFirst }));
    out.chats.push({ q, readTokens: r.inTok, firstTokenMs: r.firstMs });
  }
  // Where would a follow-up stop matching what's already in memory?
  const history = s.getChatHistory();
  const next = render([...history, { type: 'user', text: 'And how do I add a fourth one?' }, { type: 'model', response: [] }]);
  const have = seq.contextTokens;
  let d = 0;
  while (d < have.length && d < next.length && have[d] === next[d]) d++;
  out.followUpDiverges = { at: d, inMemory: have.length, fromEnd: have.length - d, around: model.detokenize(have.slice(Math.max(0, d - 3), d + 6)) };
  await seq.takeCheckpoint();
  const f = await timed(s, seq, (onFirst) => s.prompt('And how do I add a fourth one?', { maxTokens: 40, temperature: 0, budgets: { thoughtTokens: 0 }, onTextChunk: onFirst }));
  out.followUp = { readTokens: f.inTok, firstTokenMs: f.firstMs };
  await ctx.dispose();
} else {
  const ctx = await model.createContext({ contextSize: 12288, threads: THREADS, ...(CKPT ? { checkpoints: { interval: Number(CKPT) } } : {}) });
  const seq = ctx.getSequence();
  out.needsCheckpoints = seq.needsCheckpoints;
  const s = new LlamaChatSession({ contextSequence: seq, systemPrompt: `You are Tuff AI. Answer in one short sentence.\n\n${guide}`, ...wrapper() });
  out.systemTokens = model.tokenize(guide).length;
  const qs = ['How do I show text on the screen?', 'How do I make a list of three names?', 'What does round(2.5) give?'];
  out.chats = [];
  for (const q of qs) {
    s.resetChatHistory();
    const r = await timed(s, seq, (onFirst) => s.prompt(q, { maxTokens: 40, temperature: 0, budgets: { thoughtTokens: 0 }, onTextChunk: onFirst }));
    out.chats.push({ q, readTokens: r.inTok, firstTokenMs: r.firstMs });
  }
  const f = await timed(s, seq, (onFirst) => s.prompt('And how do I add a fourth one?', { maxTokens: 40, temperature: 0, budgets: { thoughtTokens: 0 }, onTextChunk: onFirst }));
  out.followUp = { readTokens: f.inTok, firstTokenMs: f.firstMs };
  await ctx.dispose();
}
clearInterval(sampler);
out.peakRssMB = Math.round(peak / 2 ** 20);
console.log(JSON.stringify(out));
await model.dispose();
await llama.dispose();
