// Tuff AI's backend (ai.js) without the 1.3 GB model, in plain Node, with a stand-in for Electron:
//   - the model download, against a local server that answers byte ranges the way Hugging Face does;
//   - the worker's life (loading, Stop, the idle timer), with the real ai-worker.mjs running on a stand-in
//     for node-llama-cpp that answers with canned text;
//   - Pumice 1's name and identity, the thinking levels and their budgets, the plan, the improver, and
//     Stop while it thinks or plans.
// Usage: node test/ai-download-test.mjs        Exits 1 if any check fails.
import Module, { createRequire } from 'node:module';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fork } from 'node:child_process';
import { EventEmitter } from 'node:events';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'tuff-ai-test-'));
const userData = path.join(tmp, 'userData');
fs.mkdirSync(userData);

let pass = 0, fail = 0;
const check = (name, ok, got) => { ok ? pass++ : fail++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `\n        got: ${JSON.stringify(got)?.slice(0, 700)}`}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// Waits for a promise, but gives up after ms (some of the bugs these checks catch made it hang forever).
const within = (p, ms) => Promise.race([p.then((v) => ({ v }), (e) => ({ e })), sleep(ms).then(() => ({ timeout: true }))]);
const until = async (fn, ms = 5000) => { const end = Date.now() + ms; while (Date.now() < end) { if (fn()) return true; await sleep(20); } return false; };
const uncaught = [];
process.on('uncaughtException', (err) => uncaught.push(String(err?.message || err)));
process.on('unhandledRejection', (err) => uncaught.push(String(err?.message || err)));

// ---------------------------------------------------------------- stand-ins for Electron and node-llama-cpp
const runtime = path.join(tmp, 'runtime');
const lib = path.join(runtime, 'node_modules', 'node-llama-cpp', 'dist');
fs.mkdirSync(lib, { recursive: true });
const cfgFile = path.join(tmp, 'llama.json');
const logFile = `${cfgFile}.log`;
const setLlama = (c) => fs.writeFileSync(cfgFile, JSON.stringify({ loadMs: 0, prefixMs: 0, tokenMs: 1, reply: 'Hello there.', fixed: '```tuff\nsay 1\n```', plan: 'Task: say hi.', thought: 'Hmm, let me think about that. '.repeat(40), failLoads: 0, ...c }));
const llamaLog = () => { try { return fs.readFileSync(logFile, 'utf8').split('\n').filter(Boolean); } catch { return []; } };
setLlama({});
// The stand-in model: loads after loadMs (or fails), reads the system prompt in prefixMs, and writes its
// reply 8 characters at a time, tokenMs apart. A chat that may think (thoughts: 'auto' and a budget) first
// thinks, one token per 8 characters, until its thought runs out or the budget does, like node-llama-cpp.
// Everything it does goes in the log.
fs.writeFileSync(path.join(lib, 'index.js'), `
import fs from 'node:fs';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const cfg = () => JSON.parse(fs.readFileSync(process.env.FAKE_LLAMA, 'utf8'));
const log = (s) => fs.appendFileSync(process.env.FAKE_LLAMA + '.log', s + '\\n');
const sequence = {
  nextTokenIndex: 0,
  needsCheckpoints: true,
  tokenMeter: { usedInputTokens: 0, usedOutputTokens: 0 },
  async eraseContextTokenRanges() { this.nextTokenIndex = 0; },
  async evaluateWithoutGeneratingNewTokens(t) { log('prefix'); await sleep(cfg().prefixMs); this.nextTokenIndex = t.length; },
  async takeCheckpoint() {},
};
export async function getLlama() {
  return {
    gpu: false,
    async getGpuDeviceNames() { return []; },
    async dispose() {},
    async loadModel() {
      const c = cfg();
      await sleep(c.loadMs);
      if (c.failLoads > 0) { c.failLoads--; fs.writeFileSync(process.env.FAKE_LLAMA, JSON.stringify(c)); log('load failed'); throw new Error('Failed to create context (not enough memory)'); }
      log('loaded');
      return { tokenizer: {}, async createContext() { return { getSequence: () => sequence }; } };
    },
  };
}
export class QwenChatWrapper {
  constructor(o = {}) { this.thoughts = o.thoughts || 'auto'; }
  generateContextState({ chatHistory }) { const u = chatHistory.find((x) => x.type === 'user').text; return { contextText: { tokenize: () => [1, 2, 3, u.charCodeAt(0)] } }; }
}
export class LlamaChatSession {
  constructor({ chatWrapper, systemPrompt }) { this.chatWrapper = chatWrapper || new QwenChatWrapper(); log('session ' + this.chatWrapper.thoughts); if (cfg().logPrompts) log('system ' + JSON.stringify(systemPrompt)); }
  dispose() {}
  resetChatHistory() {}
  async prompt(text, { signal, onTextChunk, onResponseChunk, budgets, maxTokens, customStopTriggers }) {
    const c = cfg();
    const which = /^That program doesn't pass/.test(text) ? 'followup' : /Don't answer yet/.test(text) ? 'plan' : /^Now answer their request/.test(text) ? 'go' : (text.match(/\\bQ\\d+\\b/) || ['?'])[0];
    log('prompt ' + which);
    const budget = budgets?.thoughtTokens ?? 'none';
    log('opts ' + which + ' thoughts=' + this.chatWrapper.thoughts + ' budget=' + budget + ' max=' + maxTokens + (customStopTriggers ? ' stop=' + customStopTriggers.join('|') : ''));
    if (c.logPrompts) log('text ' + which + ' ' + JSON.stringify(text));
    if (this.chatWrapper.thoughts === 'auto' && budget > 0) {
      let n = 0;
      for (const piece of c.thought.match(/[\\s\\S]{1,8}/g)) {
        if (signal?.aborted) { log('aborted thinking ' + which); return ''; }
        if (n >= budget) { log('cut ' + which + ' at ' + n); break; }
        await sleep(c.tokenMs);
        n++;
        onResponseChunk?.({ type: 'segment', segmentType: 'thought', text: piece, tokens: [7] });
      }
    }
    let reply = which === 'followup' ? c.fixed : which === 'plan' ? c.plan : c.reply;
    for (const s of customStopTriggers || []) if (reply.includes(s)) reply = reply.slice(0, reply.indexOf(s));
    let out = '';
    for (const piece of reply.match(/[\\s\\S]{1,8}/g) || []) {
      if (signal?.aborted) { log('aborted ' + which); return out; }
      await sleep(c.tokenMs);
      out += piece;
      onTextChunk?.(piece);
      onResponseChunk?.({ type: undefined, segmentType: undefined, text: piece, tokens: [8] });
    }
    log('answered ' + which);
    return out;
  }
}
`);
process.env.TUFFCODE_LLAMA_RUNTIME = runtime;
process.env.FAKE_LLAMA = cfgFile;

// utilityProcess.fork: the real worker file in a Node child process, with process.parentPort made up
// from Node's own IPC channel.
const host = path.join(tmp, 'host.mjs');
fs.writeFileSync(host, `
import { pathToFileURL } from 'node:url';
process.parentPort = { postMessage: (m) => process.send(m), on: (ev, fn) => { if (ev === 'message') process.on('message', (data) => fn({ data })); } };
await import(pathToFileURL(process.argv[2]).href);
`);
const forks = [];
function standIn(file) {
  const child = fork(host, [file], { stdio: ['ignore', 'pipe', 'pipe', 'ipc'] });
  const proc = new EventEmitter();
  proc.stdout = child.stdout;
  proc.stderr = child.stderr;
  proc.postMessage = (msg) => { if (child.connected) child.send(msg); };
  proc.kill = () => child.kill();
  child.on('message', (msg) => proc.emit('message', msg));
  child.on('exit', (code) => proc.emit('exit', code ?? 0));
  forks.push(child);
  return proc;
}

const electron = {
  app: { getPath: () => userData },
  net: { fetch: (url, opts) => fetch(url, opts) },
  utilityProcess: { fork: standIn },
};
const realLoad = Module._load;
Module._load = function (request, ...rest) { return request === 'electron' ? electron : realLoad.call(this, request, ...rest); };
const ai = createRequire(import.meta.url)('../ai.js');

// ---------------------------------------------------------------- a server that answers byte ranges
const SIZE = 3 * 1024 * 1024 + 123;
const body = crypto.randomBytes(SIZE);
const sha = crypto.createHash('sha256').update(body).digest('hex');
const mode = { slow: false, refuse: false }; // refuse: answer 416 to any byte range
const seen = []; // the Range header of each request ('' for none)
const server = http.createServer((req, res) => {
  const range = req.headers.range || '';
  seen.push(range);
  const r = /^bytes=(\d+)-$/.exec(range);
  const start = r ? +r[1] : 0;
  if (r && (start >= SIZE || mode.refuse)) { res.writeHead(416, { 'Content-Range': `bytes */${SIZE}` }); res.end(); return; }
  if (r) res.writeHead(206, { 'Content-Length': SIZE - start, 'Content-Range': `bytes ${start}-${SIZE - 1}/${SIZE}`, 'Accept-Ranges': 'bytes' });
  else res.writeHead(200, { 'Content-Length': SIZE, 'Accept-Ranges': 'bytes' });
  if (!mode.slow) { res.end(body.subarray(start)); return; }
  // Slowly, so Stop can land in the middle.
  let at = start;
  const timer = setInterval(() => {
    if (at >= SIZE) { clearInterval(timer); res.end(); return; }
    res.write(body.subarray(at, at + 64 * 1024));
    at += 64 * 1024;
  }, 20);
  res.on('close', () => clearInterval(timer));
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));

const m = ai.MODELS[0];
Object.assign(m, { url: `http://127.0.0.1:${server.address().port}/model.gguf`, size: SIZE, sha256: sha, ram: 1 });
const progress = [];
let checkMs = 0;
ai.setup({
  progress: (p) => progress.push(p),
  settings: () => ({}),
  checkSource: async (code) => { await sleep(checkMs); return /BROKEN|error/.test(code) ? { ok: false, message: 'Tuff error on line 1: that is broken' } : { ok: true }; },
});
const models = path.join(userData, 'models');
const modelFile = path.join(models, m.file);
const part = `${modelFile}.part`;
const fresh = (partBytes) => {
  fs.rmSync(models, { recursive: true, force: true });
  seen.length = 0;
  progress.length = 0;
  if (partBytes) { fs.mkdirSync(models, { recursive: true }); fs.writeFileSync(part, partBytes); }
};
const last = () => progress[progress.length - 1] || {};
const matches = () => { try { return crypto.createHash('sha256').update(fs.readFileSync(modelFile)).digest('hex') === sha; } catch { return false; } };

try {
  // ---------------------------------------------------------------- the download
  fresh();
  let r = await within(ai.fetchModel(m.id), 10000);
  check('A download finishes, and the model matches', !r.e && !r.timeout && matches() && !fs.existsSync(part) && last().done && !last().error, { r, last: last() });

  // A .part with every byte in it (TuffCode closed while it was being checked). The server answers
  // 416 to a range that starts at the end, so asking for more can never work.
  fresh(body);
  r = await within(ai.fetchModel(m.id), 10000);
  check('A .part that is already whole gets checked and used, without asking the server for more (#1, #10)', !r.e && !r.timeout && matches() && !seen.includes(`bytes=${SIZE}-`), { r, seen, last: last() });

  fresh(Buffer.alloc(SIZE));
  r = await within(ai.fetchModel(m.id), 10000);
  const r2 = await within(ai.fetchModel(m.id), 10000);
  check('A whole .part with the wrong bytes is deleted, and the next try downloads it again', /didn't match/.test(r.e?.message) && !r2.e && !r2.timeout && matches(), { r, r2, seen });

  const half = Math.floor(SIZE / 2);
  fresh(body.subarray(0, half));
  r = await within(ai.fetchModel(m.id), 10000);
  check('Half a .part: it carries on from there', !r.e && !r.timeout && matches() && seen.join() === `bytes=${half}-`, { r, seen });

  mode.refuse = true;
  fresh(body.subarray(0, half));
  r = await within(ai.fetchModel(m.id), 10000);
  mode.refuse = false;
  check('A server that refuses to carry on (416): it starts again from the beginning (#10)', !r.e && !r.timeout && matches() && seen.join() === `bytes=${half}-,`, { r, seen, last: last() });

  // A full disk: every write after the first MB fails with ENOSPC.
  fresh();
  const realWrite = fs.write;
  const realWritev = fs.writev;
  let written = 0;
  const full = () => Object.assign(new Error('ENOSPC: no space left on device, write'), { code: 'ENOSPC', errno: -28, syscall: 'write' });
  fs.write = function (fd, buf, ...rest) {
    if (written > 1024 * 1024) { process.nextTick(rest[rest.length - 1], full()); return; }
    written += buf.length || 0;
    return realWrite.call(this, fd, buf, ...rest);
  };
  fs.writev = function (fd, bufs, ...rest) {
    if (written > 1024 * 1024) { process.nextTick(rest[rest.length - 1], full()); return; }
    written += bufs.reduce((n, b) => n + b.length, 0);
    return realWritev.call(this, fd, bufs, ...rest);
  };
  r = await within(ai.fetchModel(m.id), 5000);
  fs.write = realWrite;
  fs.writev = realWritev;
  const st = await ai.status();
  check('A failed write (a full disk) ends the download instead of hanging (#2)', r.e && !r.timeout && st.downloading === null && !uncaught.length, { r, downloading: st.downloading, uncaught });
  check('... and says so in plain words', /isn't enough free disk space/.test(last().error || ''), last());
  r = await within(ai.fetchModel(m.id), 10000);
  check('After the disk has room again, the download carries on and finishes', !r.e && !r.timeout && matches() && /^bytes=\d+-$/.test(seen[seen.length - 1]), { r, seen });

  fresh();
  mode.slow = true;
  const going = ai.fetchModel(m.id);
  await until(() => progress.some((p) => !p.done && p.got > 0));
  ai.cancelDownload();
  r = await within(going, 5000);
  mode.slow = false;
  let kept = 0;
  try { kept = fs.statSync(part).size; } catch {}
  check('Stop ends the download and keeps what it has', !r.e && !r.timeout && last().stopped && kept > 0 && kept < SIZE && (await ai.status()).downloading === null, { r, kept, last: last() });
  r = await within(ai.fetchModel(m.id), 10000);
  check('... and the next download carries on from there', !r.e && !r.timeout && matches() && seen[seen.length - 1] === `bytes=${kept}-`, { r, seen, kept });

  // ---------------------------------------------------------------- the worker
  // The model file is in place now (ai.js only checks its size).
  // These checks are about the worker's life, so they ask with thinking off. The thinking levels are below.
  let n = 0;
  const ask = (q, opts = {}) => {
    const runId = `r${++n}`;
    const events = [];
    let done;
    const ended = new Promise((res) => (done = res));
    const finished = ai.run({ runId, prompt: q, model: m.id, effort: 'off', ...opts }, (e) => { events.push(e); if (e.kind === 'done') done(e); });
    return { runId, events, ended, finished };
  };
  const since = (k) => llamaLog().slice(k);

  check('codeOf takes the ```tuff block', ai.codeOf('Here:\n```tuff\nsay 1\n```') === 'say 1\n', ai.codeOf('Here:\n```tuff\nsay 1\n```'));
  check('codeOf leaves out error messages, program output and other languages (#36)', ai.codeOf('```\nTuff error on line 2: expected ":"\n```') === null && ai.codeOf('```python\nprint(1)\n```') === null && ai.codeOf('```\nHello, Sam!\n```\nNow:\n```tuff\nsay "Hello"\n```') === 'say "Hello"\n', null);

  setLlama({ failLoads: 1, loadMs: 50 });
  let a = ask('Q1 say hi');
  let e1 = await within(a.ended, 5000);
  let b = ask('Q2 say hi');
  let e2 = await within(b.ended, 5000);
  await until(() => forks[0]?.exitCode !== null || forks[0]?.signalCode, 3000);
  check('After the model fails to load, the next question starts Tuff AI again and gets its answer (#7)', e1.v?.ok === false && /Failed to create context/.test(e1.v.error) && e2.v?.ok === true && b.events.some((x) => x.kind === 'note' && /Starting/.test(x.text)) && forks.length === 2, { e1, e2, forks: forks.length, events: b.events.map((x) => x.kind) });
  check('... and the worker that failed is closed', forks[0].exitCode !== null || !!forks[0].signalCode, { exit: forks[0].exitCode, signal: forks[0].signalCode });

  // Stop while the model loads.
  ai.quit();
  setLlama({ loadMs: 600 });
  let k = llamaLog().length;
  a = ask('Q3 say hi');
  await sleep(150);
  ai.stop(a.runId);
  e1 = await within(a.ended, 5000);
  await sleep(300);
  check('Stop while Tuff AI is starting: it never answers that question (#8)', e1.v?.ok && !since(k).includes('prompt Q3') && !a.events.some((x) => x.kind === 'delta'), { e1, log: since(k) });

  // Stop while a fresh chat reads the system prompt.
  ai.quit();
  setLlama({ prefixMs: 800 });
  k = llamaLog().length;
  a = ask('Q4 say hi');
  await until(() => since(k).includes('prefix'));
  ai.stop(a.runId);
  e1 = await within(a.ended, 5000);
  await sleep(200);
  check('Stop while Tuff AI reads its guide: the question is skipped (#8)', e1.v?.ok && !since(k).includes('prompt Q4'), { e1, log: since(k) });

  // Stop while the checker runs.
  setLlama({ reply: 'Try this:\n```tuff\nBROKEN\n```' });
  checkMs = 400;
  k = llamaLog().length;
  a = ask('Q5 make a program');
  await until(() => a.events.some((x) => x.kind === 'tool'));
  ai.stop(a.runId);
  e1 = await within(a.ended, 5000);
  await sleep(200);
  checkMs = 0;
  check('Stop while the checker runs: no second answer (#8)', e1.v?.ok && since(k).includes('answered Q5') && !since(k).includes('prompt followup'), { e1, log: since(k) });

  // Stop on a question that's waiting for the one before it.
  setLlama({ reply: 'x'.repeat(8 * 20), tokenMs: 20 });
  k = llamaLog().length;
  a = ask('Q6 first');
  b = ask('Q7 second');
  await until(() => since(k).includes('prompt Q6'));
  ai.stop(b.runId);
  [e1, e2] = await Promise.all([within(a.ended, 5000), within(b.ended, 5000)]);
  check('Stop on a question waiting its turn: it is skipped (#8)', e1.v?.ok && e2.v?.ok && !since(k).includes('prompt Q7'), { e1, e2, log: since(k) });

  // A checker mistake still gets one more try (the normal case).
  setLlama({ reply: '```tuff\nBROKEN\n```' });
  k = llamaLog().length;
  a = ask('Q8 make a program');
  e1 = await within(a.ended, 5000);
  check('A program that fails the checker still gets fixed', e1.v?.ok && since(k).includes('answered followup') && a.events.some((x) => x.kind === 'note' && /fixing it/.test(x.text)), { e1, log: since(k) });

  setLlama({ reply: 'It means this:\n```\nTuff error on line 2: expected ":"\n```' });
  k = llamaLog().length;
  a = ask('Q9 explain my error');
  e1 = await within(a.ended, 5000);
  check('An echoed error message is not checked or "fixed" (#36)', e1.v?.ok && !a.events.some((x) => x.kind === 'tool') && !since(k).includes('prompt followup'), { e1, events: a.events.map((x) => x.kind) });

  // The 5-minute idle timer, made 300 ms here. An answer that takes longer than that must not be cut off.
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms, ...rest) => realSetTimeout(fn, ms >= 60000 ? 300 : ms, ...rest);
  try {
    setLlama({ reply: 'y'.repeat(8 * 40), tokenMs: 25 });
    a = ask('Q10 a long answer');
    e1 = await within(a.ended, 5000);
    check('A long answer is not cut off by the idle timer (#13)', e1.v?.ok === true, e1);
    await sleep(800);
    check('... and once nothing is being answered, the idle timer still unloads the model', (await ai.status()).loaded === null, await ai.status());
  } finally {
    globalThis.setTimeout = realSetTimeout;
  }

  // Unloading while an answer is being written (TuffCode closing, or the model deleted).
  setLlama({ reply: 'z'.repeat(8 * 40), tokenMs: 25 });
  a = ask('Q11 another long answer');
  await until(() => a.events.some((x) => x.kind === 'delta'));
  ai.quit();
  const fin = await within(a.finished, 3000);
  check('Unloading in the middle of an answer still finishes the question, with a message (#13)', !fin.timeout && !fin.e && a.events.filter((x) => x.kind === 'done').length === 1 && /Pumice 1 stopped/.test(a.events.find((x) => x.kind === 'done')?.error || ''), { fin, done: a.events.filter((x) => x.kind === 'done') });

  // ---------------------------------------------------------------- Pumice 1: name, identity, levels, improver
  check('The model is called Pumice 1, with its base model and licence for the credit line', m.name === 'Pumice 1' && m.base === 'Qwen3.5-2B' && m.licence === 'Apache 2.0' && /Qwen3\.5-2B/.test(m.sub), m);
  check('... and keeps the id and file name 1.0.4 used, so a downloaded model is still found', m.id === 'qwen3.5-2b' && m.file === 'Qwen3.5-2B-Q4_K_M.gguf', m);
  const sys = ai.systemPrompt();
  check('The system prompt says it is Pumice 1, based on Qwen3.5-2B, on this computer, and not another assistant', /^You are Pumice 1\b/.test(sys) && /based on Qwen3\.5-2B/.test(sys) && /run on the person's own computer/.test(sys) && /not ChatGPT, Claude, Gemini or Qwen's own chat app/.test(sys) && !/You are Tuff AI/.test(sys), sys.slice(0, 600));
  // With the sentence to say in the system prompt, the 2B began almost every answer with it (58 of 60 in
  // Tuff Bench), so only the card for "who are you?" has it.
  const intro = "I'm Pumice 1, TuffCode's own AI model. I'm based on the open Qwen3.5-2B model, and I run right here on your computer.";
  check('... without a sentence to say word for word, and told not to say who it is unless they ask', !/I'm Pumice|Answer like this/.test(sys) && /When they ask about anything else, don't say who you are/.test(sys), sys.slice(0, 900));
  const whoCard = ai.improve({ question: 'Who are you?' }).text;
  const sayCard = ai.improve({ question: 'What does say do?', file: 'main.tuf', code: 'say "Hello"\n' }).text;
  check('The card for "Who are you?" has the sentence to answer with; the card for another question does not', whoCard.includes(intro) && !/Pumice/.test(sayCard) && !/Pumice/.test(ai.improve({ question: 'Make a program that counts from 1 to 10.' }).text), { whoCard, sayCard });
  const now = await ai.status();
  check('status() names Pumice 1 for the download card', now.models[0].name === 'Pumice 1' && now.models[0].base === 'Qwen3.5-2B', now.models[0]);

  const L = Object.fromEntries(ai.LEVELS.map((l) => [l.id, l]));
  check('Four thinking levels: Off, Low, Medium, High', ai.LEVELS.map((l) => l.name).join() === 'Off,Low,Medium,High', ai.LEVELS);
  check('Off has no budget; each level up has a bigger budget, and Medium and High plan', L.off.budget === 0 && L.low.budget > 0 && L.medium.budget > L.low.budget && L.high.budget > L.medium.budget && !L.off.plan && !L.low.plan && L.medium.plan && L.high.plan, ai.LEVELS);
  check('The default level is one of them', !!L[ai.DEFAULT_LEVEL], ai.DEFAULT_LEVEL);

  // Off is exactly 1.0.4: no thinking, budget 0, 700 tokens, the "discourage" chat.
  setLlama({ reply: 'Hi!' });
  k = llamaLog().length;
  a = ask('Q20 say hi', { effort: 'off' });
  e1 = await within(a.ended, 5000);
  check('Off: the worker gets thoughts "discourage", a budget of 0 and 700 tokens, and nothing thinks', e1.v?.ok && since(k).includes('opts Q20 thoughts=discourage budget=0 max=700') && !a.events.some((x) => x.kind === 'thinking'), { log: since(k) });
  const stages = (ev) => ev.filter((x) => x.kind === 'stage').map((x) => x.text);
  check('Off: the stages are "Reading your question", then "Writing"', stages(a.events).join(' > ') === 'Reading your question > Writing', stages(a.events));
  check('Every answer says it is Pumice 1', a.events.some((x) => x.kind === 'model' && x.name === 'Pumice 1'), a.events.filter((x) => x.kind === 'model'));

  // Low: it thinks, up to its budget. The stand-in's thought is longer than the budget, so the budget ends it.
  setLlama({ reply: 'Hi!', thought: 'Let me think. '.repeat(400) });
  k = llamaLog().length;
  a = ask('Q21 say hi', { effort: 'low' });
  e1 = await within(a.ended, 10000);
  const th = a.events.find((x) => x.kind === 'thought');
  check(`Low: thoughts "auto" with a budget of ${L.low.budget}, on top of the 700 for the answer`, e1.v?.ok && since(k).includes(`opts Q21 thoughts=auto budget=${L.low.budget} max=${700 + L.low.budget}`), since(k));
  check('Low: a thought that would run on is cut at the budget, and the answer still comes', since(k).includes(`cut Q21 at ${L.low.budget}`) && th?.cut === true && th.tokens === L.low.budget && a.events.some((x) => x.kind === 'delta'), { th, log: since(k) });
  check('Low: the thinking streams to the panel, then the stages go Thinking, then Writing', a.events.filter((x) => x.kind === 'thinking').length > 3 && stages(a.events).join(' > ') === 'Reading your question > Thinking > Writing', stages(a.events));
  check('Low: the thinking is counted for Tuff Bench (time, tokens, cut)', e1.v?.stats?.thinkTokens === L.low.budget && e1.v.stats.cut === 1 && e1.v.stats.thinkMs >= 0, e1.v?.stats);

  // A thought that ends by itself isn't "cut".
  setLlama({ reply: 'Hi!', thought: 'Short thought.' });
  a = ask('Q22 say hi', { effort: 'low' });
  e1 = await within(a.ended, 5000);
  check('A short thought ends by itself and is not counted as cut', e1.v?.ok && a.events.find((x) => x.kind === 'thought')?.cut === false, a.events.find((x) => x.kind === 'thought'));

  // Medium: the plan first (a chat that doesn't think, stopping at a code block), then a fresh chat that
  // thinks and answers, with the plan in the card.
  setLlama({ reply: 'Here:\n```tuff\nsay "hi"\n```', plan: 'Task: show hi.\n```tuff\nsay "hi"\n```', thought: 'Think. '.repeat(30), logPrompts: true });
  k = llamaLog().length;
  a = ask('Q23 make a program that says hi', { effort: 'medium' });
  e1 = await within(a.ended, 10000);
  const plan = a.events.filter((x) => x.kind === 'plan').map((x) => x.text).join('');
  check('Medium: it plans first, without thinking, stopping at a code block', since(k).some((l) => /^opts plan thoughts=discourage budget=0 max=\d+ stop=```/.test(l)), since(k).filter((l) => l.startsWith('opts')));
  check(`... then answers in a fresh chat that thinks, with a budget of ${L.medium.budget}`, since(k).includes(`opts Q23 thoughts=auto budget=${L.medium.budget} max=${700 + L.medium.budget}`) && since(k).filter((l) => l.startsWith('prompt')).join() === 'prompt plan,prompt Q23', since(k).filter((l) => /^(prompt|opts)/.test(l)));
  const answerText = since(k).find((l) => l.startsWith('text Q23 '));
  check('... and its plan is in the card it answers from', !!answerText && JSON.parse(answerText.slice('text Q23 '.length)).includes('- The task, as you rewrote it: show hi.'), answerText?.slice(-300));
  check('Medium: the plan streams to the panel without its code', /^Task: show hi\./.test(plan) && !/```/.test(plan) && e1.v?.stats?.plan === 'show hi.', { plan, stats: e1.v?.stats });
  setLlama({});
  check('Medium: the stages go Reading your question, Planning, Thinking, Writing, Checking the code', stages(a.events).join(' > ') === 'Reading your question > Planning > Thinking > Writing > Checking the code', stages(a.events));
  setLlama({ reply: 'Hi!', thought: 'x' });
  k = llamaLog().length;
  a = ask('Q24 make a program', { effort: 'medium', improve: false });
  e1 = await within(a.ended, 5000);
  check('Without the improver, Medium only thinks (no plan, nothing "improved")', e1.v?.ok && !since(k).includes('prompt plan') && !a.events.some((x) => x.kind === 'improved'), since(k));

  // High: the biggest budget; the checker retry thinks too.
  setLlama({ reply: '```tuff\nBROKEN\n```', fixed: '```tuff\nsay 1\n```', thought: 'y' });
  k = llamaLog().length;
  a = ask('Q25 make a program', { effort: 'high' });
  e1 = await within(a.ended, 10000);
  check(`High: a budget of ${L.high.budget}, and the checker's retry thinks too`, e1.v?.ok && since(k).includes(`opts Q25 thoughts=auto budget=${L.high.budget} max=${700 + L.high.budget}`) && since(k).some((l) => l.startsWith('opts followup thoughts=auto budget=')) && stages(a.events).includes('Fixing it'), { log: since(k), stages: stages(a.events) });
  setLlama({ reply: 'Hi!', thought: 'x' });
  k = llamaLog().length;
  a = ask('Q29 hi', { effort: 'bogus' });
  e1 = await within(a.ended, 5000);
  const def = L[ai.DEFAULT_LEVEL];
  check(`A level it doesn't know (or none) means the default, ${def.name}`, e1.v?.ok && e1.v.stats.level === def.id && since(k).some((l) => l.startsWith(`opts Q29 thoughts=${def.budget ? 'auto' : 'discourage'} budget=${def.budget} `)), since(k).filter((l) => l.startsWith('opts')));

  // Stop while it thinks: no answer, and the next question isn't stuck behind it.
  setLlama({ reply: 'Answer.', thought: 'Thinking hard. '.repeat(200), tokenMs: 15 });
  k = llamaLog().length;
  a = ask('Q26 think a lot', { effort: 'high' });
  await until(() => a.events.filter((x) => x.kind === 'thinking').length > 3, 8000);
  ai.stop(a.runId);
  e1 = await within(a.ended, 5000);
  await sleep(200);
  check('Stop while it thinks: it stops at once, with no answer', e1.v?.ok && since(k).includes('aborted thinking Q26') && !a.events.some((x) => x.kind === 'delta') && !since(k).includes('answered Q26'), { e1, log: since(k) });
  setLlama({ reply: 'Next one.', thought: 'z', tokenMs: 1 });
  b = ask('Q27 next', { effort: 'low' });
  e2 = await within(b.ended, 5000);
  check('... and the next question gets its answer', e2.v?.ok && b.events.some((x) => x.kind === 'delta'), { e2, kinds: b.events.map((x) => x.kind) });

  // Stop while it plans: no answer turn at all.
  setLlama({ reply: 'Answer.', plan: 'Task: '.padEnd(400, 'x'), tokenMs: 15 });
  k = llamaLog().length;
  a = ask('Q28 make it', { effort: 'medium' });
  await until(() => a.events.some((x) => x.kind === 'plan'), 8000);
  ai.stop(a.runId);
  e1 = await within(a.ended, 5000);
  await sleep(200);
  check('Stop while it plans: it never answers', e1.v?.ok && !since(k).includes('prompt Q28') && !a.events.some((x) => x.kind === 'delta'), { e1, log: since(k) });
  setLlama({ tokenMs: 1 });

  // The improver.
  const kinds = {
    'Make a program that asks "What is your name? " and greets them.': 'write',
    'Write me a guessing game': 'write',
    'Can you make a timer app with a button?': 'write',
    "My program doesn't work, it says Tuff error on line 3": 'fix',
    'Look for bugs or mistakes in this code and explain how to fix them.': 'fix',
    'Explain what this file does, step by step, in simple words.': 'explain',
    'How do I make a list?': 'question',
    'Who are you?': 'about',
    'Are you ChatGPT?': 'about',
    'What model are you?': 'about',
    'What does round(2.5) give?': 'question',
    'Suggest ways to make this app look and feel nicer.': 'question',
  };
  const gotKinds = Object.fromEntries(Object.keys(kinds).map((q) => [q, ai.improve({ question: q }).kind]));
  check('The improver tells writing, fixing, explaining and questions apart', Object.entries(kinds).every(([q, k2]) => gotKinds[q] === k2), gotKinds);
  check('"Asks for your name" is a console program; buttons and mtgui mean a window', ai.improve({ question: 'Make a program that asks for your name' }).target === 'console' && ai.improve({ question: 'Make an mtgui window with a button' }).target === 'window' && ai.improve({ question: 'add a score', file: 'a.tuf', code: 'mention tgui\n' }).target === 'window', null);
  const fixIn = { question: 'It should count to 3. Can you fix it?', file: 'C:\\p\\count.tuf', code: 'say "Counting"\nfor n in range(1, 3)\n    say n\n', runError: 'Tuff error on line 2: expected ":"\n  2 | for n in range(1, 3)\n                       ^' };
  const card = ai.improve(fixIn);
  check('A fix: the card names the file, the error\'s line and what it says, and what a good answer has', card.kind === 'fix' && /count\.tuf \(3 lines\)/.test(card.text) && /stopped at line 2 \(for n in range\(1, 3\)\): Tuff error on line 2: expected ":"/.test(card.text) && /naming the mistake and the line/.test(card.text), card.text);
  const msg = ai.buildMessage(fixIn, card);
  check('... and the message has the file, the error and the card, last', /Their open file, count\.tuf:\n```tuff\nsay "Counting"/.test(msg) && /When they last ran it, it stopped with this error/.test(msg) && /What TuffCode worked out from their question:\n- They want: their program fixed/.test(msg) && msg.trim().endsWith('range(1, 3) gives 1, 2, 3.'), msg.slice(-900));
  const legacy = ai.buildMessage(fixIn, null);
  check('Without the improver, the message is what 1.0.4 sent (no card, no error block)', !/What TuffCode worked out/.test(legacy) && !/When they last ran it/.test(legacy) && /Their question:\nIt should count to 3\. Can you fix it\?$/.test(legacy), legacy.slice(-300));
  const ask1 = { question: 'Make a program that asks "What is your name? " and then says Hello and the name.' };
  check('A console request leaves the guide\'s app-window sections out (1.0.4 put them in)', !/## App windows/.test(ai.buildMessage(ask1, ai.improve(ask1))) && /## App windows/.test(ai.buildMessage(ask1, null)), null);
  check('A window request always gets the app-window section', /## App windows/.test(ai.buildMessage({ question: 'Make an mtgui window with a heading' }, ai.improve({ question: 'Make an mtgui window with a heading' }))), null);
  const big = Array.from({ length: 400 }, (_, i) => `say "line ${i + 1}, a fairly long line of text to fill the file"`).join('\n');
  const bigCard = ai.improve({ question: 'fix it', file: 'big.tuf', code: big, runError: 'Tuff error on line 300: oops' });
  check('A long file: only the part around the error goes in, and the card says which lines', !bigCard.focus.whole && bigCard.focus.from <= 300 && bigCard.focus.to >= 300 && bigCard.focus.text.length <= 6000 && /lines \d+ to \d+/.test(bigCard.text), { from: bigCard.focus.from, to: bigCard.focus.to });

  // The improved request goes to the panel, and the model reads it.
  setLlama({ reply: 'Fixed.', logPrompts: true });
  k = llamaLog().length;
  a = ask('fix it', { effort: 'off', ai: fixIn });
  e1 = await within(a.ended, 5000);
  const imp = a.events.find((x) => x.kind === 'improved');
  const sent = since(k).find((l) => l.startsWith('text '));
  check('The panel gets the improved request, and the model gets it at the end of the message', e1.v?.ok && imp?.text === card.text && sent && JSON.parse(sent.slice(sent.indexOf(' ', 5) + 1)).includes('What TuffCode worked out from their question'), { imp, sent: sent?.slice(-300) });
  setLlama({});

  check('Nothing threw without being caught', !uncaught.length, uncaught);
} catch (err) {
  fail++;
  console.log(`FAIL  ${err.stack || err}`);
} finally {
  ai.quit();
  for (const c of forks) try { c.kill(); } catch {}
  server.closeAllConnections?.();
  server.close();
  await sleep(200);
  try { fs.rmSync(tmp, { recursive: true, force: true }); } catch {}
}
console.log(`--- ai-download-test: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
