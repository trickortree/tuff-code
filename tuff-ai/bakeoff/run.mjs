// Tuff AI Phase 1 bake-off: runs a GGUF model on Tuff Bench on the CPU and scores it with the real interpreter.
//   node tuff-ai/bakeoff/run.mjs --model <file.gguf> --name <label> [--runtime <dir with node_modules/node-llama-cpp>]
//        [--mode lean|guide] [--threads 8] [--ctx 8192] [--only write,gui,fix] [--limit N] [--out results/<name>-<mode>.jsonl]
// lean:  short system prompt + the guide's core sections; the 2 most relevant other sections go in the message.
// guide: the whole guide (minus the MCP-only "Using the tools") in the system prompt.
// Each task is a fresh chat with the same system prompt. If the code fails tuff.py --check, the model gets
// one retry with the error, the way Tuff AI would do it in the app. Results append to --out, so a run can resume.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { tuff, norm, hasNeed } from '../bench/verify.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const MODEL = arg('model');
const NAME = arg('name', path.basename(MODEL || '', '.gguf'));
const MODE = arg('mode', 'lean');
const THREADS = Number(arg('threads', 8));
const CTX = Number(arg('ctx', 8192));
const ONLY = arg('only', 'write,gui,fix').split(',');
const LIMIT = Number(arg('limit', 0));
const MAX_TOKENS = Number(arg('max-tokens', 600));
const CKPT = arg('checkpoint-interval');
const OUT = arg('out', path.join(HERE, 'results', `${NAME}-${MODE}.jsonl`));
if (!MODEL) { console.error('--model is required'); process.exit(2); }

const runtime = arg('runtime');
const lib = await import(runtime ? pathToFileURL(path.join(runtime, 'node_modules', 'node-llama-cpp', 'dist', 'index.js')).href : 'node-llama-cpp');
const { getLlama, LlamaChatSession, QwenChatWrapper } = lib;

// ---------------------------------------------------------------- the guide, in sections
const guide = fs.readFileSync(path.join(ROOT, 'tuffcode', 'mcp', 'tuff-guide.md'), 'utf8').replace(/\r\n/g, '\n');
const sections = [];
for (const part of guide.split(/\n(?=##+ )/)) {
  const title = (/^##+ (.*)/.exec(part) || [])[1];
  if (title) sections.push({ title, text: part.trim() });
}
const SKIP = ['Using the tools'];
const CORE = ['Tuff is not Python', 'Two rules that trip everyone up', 'Basics', 'Asking questions'];
const core = sections.filter((s) => CORE.includes(s.title));
const rest = sections.filter((s) => !CORE.includes(s.title) && !SKIP.includes(s.title));
const words = (t) => (t.toLowerCase().match(/[a-z_]{3,}/g) || []);
const df = new Map();
for (const s of rest) for (const w of new Set(words(s.text))) df.set(w, (df.get(w) || 0) + 1);
function relevant(text, n = 2) {
  const q = new Set(words(text));
  const scored = rest.map((s) => {
    const have = new Set(words(s.title + ' ' + s.text));
    let score = 0;
    for (const w of q) if (have.has(w)) score += Math.log(1 + rest.length / (df.get(w) || 1));
    return { s, score };
  }).sort((a, b) => b.score - a.score);
  return scored.slice(0, n).filter((x) => x.score > 0).map((x) => x.s);
}

const INTRO = `You are Tuff AI, the helper built into TuffCode. You help beginners with the Tuff programming language.
Tuff is its own language, not Python. Only use what the Tuff guide below shows.
Keep answers short. When you give a program, give the whole program in one \`\`\`tuff code block.`;
const SYSTEM = MODE === 'guide'
  ? `${INTRO}\n\n# Tuff guide\n\n${sections.filter((s) => !SKIP.includes(s.title)).map((s) => s.text).join('\n\n')}`
  : `${INTRO}\n\n# Tuff guide (the basics)\n\n${core.map((s) => s.text).join('\n\n')}`;

function userMessage(x) {
  const about = x.type === 'fix' ? `${x.task}\n${x.broken}` : x.task;
  const extra = MODE === 'lean' ? relevant(about, x.type === 'gui' ? 1 : 2) : [];
  const ref = extra.length ? `More of the Tuff guide that may help:\n\n${extra.map((s) => s.text).join('\n\n')}\n\n---\n\n` : '';
  if (x.type === 'fix') {
    const what = x.kind === 'error' ? `When I run it, I get this error:\n${x.error}` : `When I run it, it prints:\n${x.got}`;
    return `${ref}This Tuff program doesn't work. It should do this: ${x.task}\n\n\`\`\`tuff\n${x.broken.trimEnd()}\n\`\`\`\n\n${what}\n\nExplain the mistake in one or two sentences, then give the whole fixed program.`;
  }
  return `${ref}${x.task}`;
}

function codeOf(text) {
  const m = /```[ \t]*tuff[^\n]*\n([\s\S]*?)```/i.exec(text) || /```[^\n]*\n([\s\S]*?)```/.exec(text);
  return m ? m[1] : null;
}
const proseOf = (text) => text.replace(/```[\s\S]*?(```|$)/g, ' ');

async function score(x, code) {
  if (code == null) return { ok: false, why: 'no code block' };
  const c = await tuff(code, { check: true });
  if (c.code !== 0) return { ok: false, check: false, why: [c.out, c.err].filter(Boolean).join('\n').split('\n').slice(0, 3).join('\n') };
  if (x.type === 'gui') {
    const missing = (x.needs || []).filter((s) => !hasNeed(code, s));
    return missing.length ? { ok: false, check: true, why: `missing ${missing.map((s) => JSON.stringify(s)).join(', ')}` } : { ok: true, check: true };
  }
  for (const [i, t] of (x.type === 'fix' ? x.tests : x.tests).entries()) {
    const r = await tuff(code, { stdin: t.stdin || '' });
    if (r.code !== 0) return { ok: false, check: true, why: `test ${i} exits ${r.code}: ${[r.out, r.err].join('\n').trim().split('\n').slice(-2).join(' | ')}` };
    if (r.out !== norm(t.stdout)) return { ok: false, check: true, why: `test ${i} output: ${JSON.stringify(r.out.slice(0, 200))}` };
  }
  return { ok: true, check: true };
}

// ---------------------------------------------------------------- tasks
const load = (f) => fs.existsSync(f) ? fs.readFileSync(f, 'utf8').split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l)) : [];
// --tasks <file> runs just that file (for a quick test); otherwise the bench files picked by --only.
let tasks = arg('tasks') ? load(arg('tasks'))
  : ONLY.flatMap((k) => load(path.join(ROOT, 'tuff-ai', 'bench', `${k}.jsonl`)));
const ids = arg('ids');
if (ids) { const want = new Set(ids.split(',')); tasks = tasks.filter((x) => want.has(x.id)); }
if (LIMIT) tasks = tasks.slice(0, LIMIT);
fs.mkdirSync(path.dirname(OUT), { recursive: true });
const done = new Set(load(OUT).map((r) => r.id));
tasks = tasks.filter((x) => !done.has(x.id));

// ---------------------------------------------------------------- model
let peak = 0;
const sample = () => { peak = Math.max(peak, process.memoryUsage().rss); };
const sampler = setInterval(sample, 100);
const GPU = arg('gpu', 'false'); // e.g. --gpu vulkan; scores don't depend on it, only the speed does
const llama = await getLlama({ gpu: GPU === 'false' ? false : GPU, build: 'never', logLevel: 'error' });
const t0 = Date.now();
const model = await llama.loadModel({ modelPath: MODEL, useMmap: false }); // mmap costs ~500 MB extra on CPU (probe.mjs)
const loadMs = Date.now() - t0;
const context = await model.createContext({ contextSize: CTX, threads: THREADS, ...(CKPT ? { checkpoints: { interval: Number(CKPT) } } : {}) });
const sequence = context.getSequence();
const isQwen = /qwen/i.test(MODEL);
const session = new LlamaChatSession({
  contextSequence: sequence,
  systemPrompt: SYSTEM,
  ...(isQwen ? { chatWrapper: new QwenChatWrapper({ variation: '3.5', thoughts: 'discourage' }) } : {}),
});
// Hybrid models (Qwen3.5) can't rewind their memory to an arbitrary point, so a new chat would re-read the
// whole system prompt. Evaluate exactly the shared opening once, checkpoint it, and cut back to it per task
// (probe.mjs --what reuse-manual measured 17 tokens read per new chat this way, instead of ~7,950).
let prefix = 0;
if (sequence.needsCheckpoints) {
  const render = (text) => session.chatWrapper.generateContextState({ chatHistory: [{ type: 'system', text: SYSTEM }, { type: 'user', text }, { type: 'model', response: [] }] }).contextText.tokenize(model.tokenizer);
  const a = render('A'), b = render('B');
  while (prefix < a.length && a[prefix] === b[prefix]) prefix++;
  await sequence.evaluateWithoutGeneratingNewTokens(a.slice(0, prefix));
  await sequence.takeCheckpoint();
}
sample();
console.log(JSON.stringify({ event: 'start', name: NAME, mode: MODE, gpu: llama.gpu, threads: THREADS, ctx: CTX, wrapper: session.chatWrapper.wrapperName,
  needsCheckpoints: sequence.needsCheckpoints, prefixCheckpoint: prefix, systemTokens: model.tokenize(SYSTEM).length, loadMs, rssMB: Math.round(process.memoryUsage().rss / 2 ** 20), todo: tasks.length }));

async function ask(text) {
  const before = { i: sequence.tokenMeter.usedInputTokens, o: sequence.tokenMeter.usedOutputTokens };
  const start = Date.now();
  let first = 0;
  const reply = await session.prompt(text, {
    maxTokens: MAX_TOKENS,
    temperature: 0,
    budgets: { thoughtTokens: 0 },
    onTextChunk: () => { if (!first) first = Date.now(); },
  });
  const end = Date.now();
  const inTok = sequence.tokenMeter.usedInputTokens - before.i;
  const outTok = sequence.tokenMeter.usedOutputTokens - before.o;
  return { reply, ms: end - start, ttftMs: (first || end) - start, inTok, outTok, genTps: outTok > 1 && first ? (outTok - 1) / ((end - first) / 1000) : 0 };
}

for (const x of tasks) {
  session.resetChatHistory();
  if (prefix && sequence.nextTokenIndex > prefix) await sequence.eraseContextTokenRanges([{ start: prefix, end: sequence.nextTokenIndex }]);
  const a = await ask(userMessage(x));
  if (prefix) await sequence.takeCheckpoint();
  let r = await score(x, codeOf(a.reply));
  const res = { id: x.id, dev: llama.gpu || 'cpu', type: x.type, cat: x.cat, level: x.level, kind: x.kind, mistake: x.mistake, pass1: r.ok, check1: !!r.check, why1: r.ok ? undefined : r.why,
    ms: a.ms, ttftMs: a.ttftMs, inTok: a.inTok, outTok: a.outTok, genTps: Math.round(a.genTps * 10) / 10, reply1: a.reply };
  if (x.type === 'fix') {
    const prose = proseOf(a.reply).toLowerCase();
    res.explained = (x.explain_words || []).some((w) => prose.includes(String(w).toLowerCase()));
  }
  res.pass = r.ok;
  if (!r.ok && !r.check) {
    // The app would quietly try once more with the checker's error.
    const b = await ask(r.why === 'no code block'
      ? 'Please give the whole program in one ```tuff code block.'
      : `That program doesn't pass Tuff's checker:\n${r.why}\n\nFix it and give the whole program again.`);
    r = await score(x, codeOf(b.reply));
    Object.assign(res, { retried: true, pass: r.ok, why2: r.ok ? undefined : r.why, ms2: b.ms, ttftMs2: b.ttftMs, inTok2: b.inTok, outTok2: b.outTok, reply2: b.reply });
  }
  sample();
  res.rssMB = Math.round(peak / 2 ** 20);
  fs.appendFileSync(OUT, JSON.stringify(res) + '\n');
  console.log(`${x.id.padEnd(12)} ${res.pass1 ? 'PASS' : res.pass ? 'pass*' : 'fail'} ${String(a.ms).padStart(6)} ms  ttft ${String(a.ttftMs).padStart(6)}  in ${a.inTok}  out ${a.outTok}  ${res.genTps} tok/s`);
}

clearInterval(sampler);
console.log(JSON.stringify({ event: 'end', name: NAME, mode: MODE, peakRssMB: Math.round(peak / 2 ** 20), freeMB: Math.round(os.freemem() / 2 ** 20) }));
await context.dispose();
await model.dispose();
await llama.dispose();
