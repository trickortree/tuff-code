// Tuff AI's backend (ai.js) without the 1.3 GB model, in plain Node, with a stand-in for Electron:
//   - the model download, against a local server that answers byte ranges the way Hugging Face does;
//   - the worker's life (loading, Stop, the idle timer), with the real ai-worker.mjs running on a stand-in
//     for node-llama-cpp that answers with canned text.
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
const setLlama = (c) => fs.writeFileSync(cfgFile, JSON.stringify({ loadMs: 0, prefixMs: 0, tokenMs: 1, reply: 'Hello there.', fixed: '```tuff\nsay 1\n```', failLoads: 0, ...c }));
const llamaLog = () => { try { return fs.readFileSync(logFile, 'utf8').split('\n').filter(Boolean); } catch { return []; } };
setLlama({});
// The stand-in model: loads after loadMs (or fails), reads the system prompt in prefixMs, and writes its
// reply 8 characters at a time, tokenMs apart. Everything it does goes in the log.
fs.writeFileSync(path.join(lib, 'index.js'), `
import fs from 'node:fs';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const cfg = () => JSON.parse(fs.readFileSync(process.env.FAKE_LLAMA, 'utf8'));
const log = (s) => fs.appendFileSync(process.env.FAKE_LLAMA + '.log', s + '\\n');
const sequence = {
  nextTokenIndex: 0,
  needsCheckpoints: true,
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
  generateContextState({ chatHistory }) { const u = chatHistory.find((x) => x.type === 'user').text; return { contextText: { tokenize: () => [1, 2, 3, u.charCodeAt(0)] } }; }
}
export class LlamaChatSession {
  constructor({ chatWrapper }) { this.chatWrapper = chatWrapper || new QwenChatWrapper(); }
  dispose() {}
  resetChatHistory() {}
  async prompt(text, { signal, onTextChunk }) {
    const c = cfg();
    const which = /^That program doesn't pass/.test(text) ? 'followup' : (text.match(/\\bQ\\d+\\b/) || ['?'])[0];
    log('prompt ' + which);
    let out = '';
    for (const piece of (which === 'followup' ? c.fixed : c.reply).match(/[\\s\\S]{1,8}/g)) {
      if (signal?.aborted) { log('aborted ' + which); return out; }
      await sleep(c.tokenMs);
      out += piece;
      onTextChunk?.(piece);
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
  let n = 0;
  const ask = (q) => {
    const runId = `r${++n}`;
    const events = [];
    let done;
    const ended = new Promise((res) => (done = res));
    const finished = ai.run({ runId, prompt: q, model: m.id }, (e) => { events.push(e); if (e.kind === 'done') done(e); });
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
  check('Unloading in the middle of an answer still finishes the question, with a message (#13)', !fin.timeout && !fin.e && a.events.filter((x) => x.kind === 'done').length === 1 && /Tuff AI stopped/.test(a.events.find((x) => x.kind === 'done')?.error || ''), { fin, done: a.events.filter((x) => x.kind === 'done') });

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
