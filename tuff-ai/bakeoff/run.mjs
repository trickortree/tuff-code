// Tuff AI bake-off: runs a GGUF model on Tuff Bench and scores it with the real interpreter.
//
// Phase 1 (a model on its own, as the bake-off first ran it):
//   node tuff-ai/bakeoff/run.mjs --model <file.gguf> --name <label> [--runtime <dir with node_modules/node-llama-cpp>]
//        [--mode lean|guide] [--threads 8] [--ctx 8192] [--only write,gui,fix] [--limit N] [--out results/<name>-<mode>.jsonl]
// lean:  short system prompt + the guide's core sections; the 2 most relevant other sections go in the message.
// guide: the whole guide (minus the MCP-only "Using the tools") in the system prompt.
// Each task is a fresh chat with the same system prompt. If the code fails tuff.py --check, the model gets
// one retry with the error, the way Tuff AI would do it in the app. Results append to --out, so a run can resume.
//
// The app (--app): Tuff AI exactly as TuffCode runs it. It loads tuffcode/ai.js with a stand-in for Electron,
// and ai.js starts the real tuffcode/ai-worker.mjs in a Node child process, so the system prompt, the
// improver, the thinking levels, the plan, the checker retry and the worker are the app's own code.
//   node tuff-ai/bakeoff/run.mjs --app --model <file.gguf> --level off|low|medium|high --improve on|off
//        [--gpu auto|cpu] [--threads N] [--budget N] [--sample write:40,gui:10,fix:30] [--out results/think/<...>.jsonl]
// --gpu auto is what the app does (Vulkan on a real graphics card); --threads only matters on the CPU.
// --budget overrides the level's thought budget, to try other budgets. The questions are what a beginner
// would type in the app: the task (for a fix, with the broken program as the open file, the error, and
// "Can you fix it?").
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import Module from 'node:module';
import { fork } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { tuff, norm, hasNeed } from '../bench/verify.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const flag = (k) => process.argv.includes('--' + k);
const MODEL = arg('model');
const APP = flag('app');
const NAME = arg('name', path.basename(MODEL || '', '.gguf'));
const MODE = arg('mode', 'lean');
const LEVEL = arg('level', 'off');
const IMPROVE = arg('improve', 'on') !== 'off';
const GPU = arg('gpu', APP ? 'auto' : 'false'); // Phase 1: e.g. --gpu vulkan; scores don't depend on it, only the speed does
const THREADS = Number(arg('threads', APP ? 0 : 8));
const CTX = Number(arg('ctx', 8192));
const ONLY = arg('only', 'write,gui,fix').split(',');
const LIMIT = Number(arg('limit', 0));
const MAX_TOKENS = Number(arg('max-tokens', 600));
const CKPT = arg('checkpoint-interval');
const OUT = arg('out', APP
  ? path.join(HERE, 'results', 'think', `${LEVEL}${arg('budget') ? `-${arg('budget')}` : ''}-${IMPROVE ? 'improved' : 'plain'}-${GPU === 'cpu' ? `cpu${THREADS || ''}` : 'gpu'}.jsonl`)
  : path.join(HERE, 'results', `${NAME}-${MODE}.jsonl`));
if (!MODEL) { console.error('--model is required'); process.exit(2); }
const runtime = arg('runtime');

// ---------------------------------------------------------------- scoring
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
// --sample write:40,gui:10,fix:30 takes that many tasks from each file, evenly spread through it.
const SAMPLE = Object.fromEntries((arg('sample') || '').split(',').filter(Boolean).map((p) => p.split(':')).map(([k, n]) => [k, Number(n)]));
const spread = (xs, n) => (n && n < xs.length ? Array.from({ length: n }, (_, i) => xs[Math.floor((i * xs.length) / n)]) : xs);
let tasks = arg('tasks') ? load(arg('tasks'))
  : (arg('sample') ? Object.keys(SAMPLE) : ONLY).flatMap((k) => spread(load(path.join(ROOT, 'tuff-ai', 'bench', `${k}.jsonl`)), SAMPLE[k]));
const ids = arg('ids');
if (ids) { const want = new Set(ids.split(',')); tasks = tasks.filter((x) => want.has(x.id)); }
if (LIMIT) tasks = tasks.slice(0, LIMIT);
fs.mkdirSync(path.dirname(OUT), { recursive: true });
const done = new Set(load(OUT).map((r) => r.id));
tasks = tasks.filter((x) => !done.has(x.id));

if (APP) {
  await appBench();
  process.exit(0);
}

// ---------------------------------------------------------------- the app's own code, with a stand-in for Electron
// A thought that ran to the budget and was going round in circles: some line of it comes back 3 times or more.
function loops(thought) {
  const seen = new Map();
  for (const l of thought.split(/\n+/).map((s) => s.trim()).filter((s) => s.length >= 12)) seen.set(l, (seen.get(l) || 0) + 1);
  return Math.max(0, ...seen.values()) >= 3;
}

async function appBench() {
  if (runtime) process.env.TUFFCODE_LLAMA_RUNTIME = path.resolve(runtime);
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'tuff-bench-'));
  // utilityProcess.fork: the real worker in a Node child process, with process.parentPort made from Node's IPC.
  const host = path.join(userData, 'host.mjs');
  fs.writeFileSync(host, "import { pathToFileURL } from 'node:url';\nprocess.parentPort = { postMessage: (m) => process.send(m), on: (ev, fn) => { if (ev === 'message') process.on('message', (data) => fn({ data })); } };\nawait import(pathToFileURL(process.argv[2]).href);\n");
  const children = [];
  const utilityProcess = {
    fork(file, args, opts = {}) {
      const child = fork(host, [file], { stdio: ['ignore', 'pipe', 'pipe', 'ipc'], env: opts.env });
      children.push(child);
      const proc = new EventEmitter();
      Object.assign(proc, { stdout: child.stdout, stderr: child.stderr, postMessage: (m) => { if (child.connected) child.send(m); }, kill: () => child.kill() });
      child.on('message', (m) => proc.emit('message', m));
      child.on('exit', (code) => proc.emit('exit', code ?? 0));
      return proc;
    },
  };
  const electron = { app: { getPath: () => userData }, utilityProcess, net: {} };
  const realLoad = Module._load;
  Module._load = function (request, ...rest) { return request === 'electron' ? electron : realLoad.call(this, request, ...rest); };
  const ai = createRequire(import.meta.url)(path.join(ROOT, 'tuffcode', 'ai.js'));
  const m = ai.MODELS[0];
  fs.mkdirSync(path.join(userData, 'models'));
  const linked = path.join(userData, 'models', m.file);
  try { fs.linkSync(MODEL, linked); } catch { fs.symlinkSync(path.resolve(MODEL), linked); }
  const lv = ai.LEVELS.find((l) => l.id === LEVEL);
  if (!lv) { console.error(`--level must be one of ${ai.LEVELS.map((l) => l.id).join(', ')}`); process.exit(2); }
  if (arg('budget')) lv.budget = Number(arg('budget'));
  if (arg('temp')) lv.temperature = Number(arg('temp'));
  if (arg('topk')) lv.topK = Number(arg('topk'));
  if (arg('topp')) lv.topP = Number(arg('topp'));
  ai.setup({
    settings: () => ({ aiGpu: GPU === 'cpu' ? 'cpu' : 'auto', ...(THREADS ? { aiThreads: THREADS } : {}) }),
    // Like main.js's checkSource: tuff.py --check, and its "Tuff error on line …" line.
    checkSource: async (code) => {
      const c = await tuff(code, { check: true });
      const lines = `${c.out}\n${c.err}`.split('\n');
      return { ok: c.code === 0, message: lines.find((l) => /^Tuff error/.test(l)) || '' };
    },
  });
  let n = 0;
  const ask = (parts) => new Promise((resolve) => {
    const got = { events: [], thought: [''], plan: '', stages: [] };
    ai.run({ runId: `b${++n}`, prompt: parts.question, model: m.id, effort: LEVEL, ai: parts, improve: IMPROVE }, (e) => {
      if (e.kind === 'thinking') got.thought[got.thought.length - 1] += e.text;
      else if (e.kind === 'break') got.thought.push('');
      else if (e.kind === 'stage') got.stages.push(e.text);
      else if (e.kind === 'improved') got.improved = e.text;
      else if (e.kind === 'model' || e.kind === 'note') got[e.kind] = e.name || e.text;
      else if (e.kind === 'done') resolve({ ...got, done: e });
    });
  });
  const question = (x) => (x.type !== 'fix' ? { question: x.task } : {
    question: x.kind === 'error' ? `${x.task}\nWhen I run it, I get this error:\n${x.error}\nCan you fix it?` : `${x.task}\nBut when I run it, it shows this instead:\n${x.got}\nCan you fix it?`,
    file: 'program.tuf',
    code: x.broken,
    ...(x.kind === 'error' ? { runError: x.error } : {}),
  });
  // The first question also starts the model and reads the system prompt, so it isn't timed.
  const warm = await ask({ question: 'Say hi in one word.' });
  if (!warm.done.ok) { console.error(`The model didn't start: ${warm.done.error}`); process.exit(1); }
  const loaded = await ai.status();
  console.log(JSON.stringify({ event: 'start', app: true, level: LEVEL, budget: lv.budget, plan: lv.plan && IMPROVE, temperature: lv.temperature, topK: lv.topK, topP: lv.topP, improve: IMPROVE, gpu: loaded.loaded?.gpu, device: loaded.loaded?.device, threads: THREADS || 'auto', todo: tasks.length, warmMs: warm.done.stats.ms }));
  for (const x of tasks) {
    const a = await ask(question(x));
    const s = a.done.stats || {};
    const answers = s.answers || [];
    const r1 = await score(x, codeOf(answers[0] || ''));
    const r = answers.length > 1 ? await score(x, codeOf(answers[answers.length - 1])) : r1;
    const thought = a.thought.join('\n\n');
    const res = {
      id: x.id, type: x.type, cat: x.cat, level: x.level, kind: x.kind, mistake: x.mistake,
      think: LEVEL, budget: lv.budget, temp: lv.temperature, improve: IMPROVE, dev: loaded.loaded?.gpu || 'cpu', threads: THREADS || null,
      ok: a.done.ok, error: a.done.error || undefined,
      pass1: r1.ok, check1: !!r1.check, why1: r1.ok ? undefined : r1.why, pass: r.ok, why: r.ok ? undefined : r.why, retried: answers.length > 1,
      ms: s.ms, planMs: s.planMs, thinkMs: s.thinkMs, thinkTokens: s.thinkTokens, cut: s.cut, loop: s.cut > 0 && loops(thought),
      reqKind: s.kind, target: s.target, stages: [...new Set(a.stages)],
      improved: a.improved, plan: s.plan || undefined,
      // The start and end of the thinking, enough to see what it did without keeping all of it.
      thought: thought.length > 700 ? `${thought.slice(0, 350)} … ${thought.slice(-350)}` : thought || undefined,
      reply1: answers[0], reply2: answers[1],
    };
    if (x.type === 'fix') res.explained = (x.explain_words || []).some((w) => proseOf(answers[0] || '').toLowerCase().includes(String(w).toLowerCase()));
    fs.appendFileSync(OUT, JSON.stringify(res) + '\n');
    console.log(`${x.id.padEnd(12)} ${res.pass1 ? 'PASS' : res.pass ? 'pass*' : 'fail'} ${String(s.ms).padStart(6)} ms  think ${String(s.thinkTokens || 0).padStart(4)} tok${s.cut ? ' CUT' : ''}${res.loop ? ' LOOP' : ''}  plan ${s.planMs || 0} ms`);
  }
  ai.quit();
  for (const c of children) try { c.kill(); } catch {}
  console.log(JSON.stringify({ event: 'end', level: LEVEL, improve: IMPROVE }));
  try { fs.rmSync(userData, { recursive: true, force: true }); } catch {}
}

// ---------------------------------------------------------------- Phase 1: the model on its own
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

// ---------------------------------------------------------------- model
let peak = 0;
const sample = () => { peak = Math.max(peak, process.memoryUsage().rss); };
const sampler = setInterval(sample, 100);
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
