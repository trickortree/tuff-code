// Tuff AI: the offline helper. The model runs in ai-worker.mjs (a utility process). This side downloads
// the model, checks there's enough memory, keeps the worker alive while it's being used, and checks
// every Tuff program the model writes with tuff.py --check. A program that fails gets one more try with
// the checker's error, the way Tuff Bench scores it (tuff-ai/bakeoff/run.mjs).
const { app, utilityProcess, net } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const os = require('os');
const crypto = require('crypto');

// Until Pumice (the trained model) is ready, the preview uses its base model as it is.
const MODELS = [
  {
    id: 'qwen3.5-2b',
    name: 'Qwen3.5-2B',
    sub: 'Untrained preview. Pumice, trained on Tuff, replaces it later.',
    file: 'Qwen3.5-2B-Q4_K_M.gguf',
    url: 'https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf',
    size: 1280835840,
    sha256: 'aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223',
    ram: 1.8e9, // measured peak in Phase 1 was ~1.6 GB, plus room for the answer
  },
];
const IDLE_MS = 5 * 60 * 1000;
const MAX_TOKENS = 700;

let checkSource = async () => ({ ok: true, unknown: true });
let readSettings = () => ({});
let onProgress = () => {};
let download = null; // { id, got, total, abort }
let worker = null; // { proc, model, ready, info }
let idleTimer = null;
const runs = new Map(); // runId -> { emit, resolve }

function setup(opts) {
  if (opts.checkSource) checkSource = opts.checkSource;
  if (opts.settings) readSettings = opts.settings;
  if (opts.progress) onProgress = opts.progress;
}

const modelsDir = () => path.join(app.getPath('userData'), 'models');
const modelPath = (m) => path.join(modelsDir(), m.file);
const find = (id) => MODELS.find((m) => m.id === id) || MODELS[0];
const downloaded = (m) => { try { return fs.statSync(modelPath(m)).size === m.size; } catch { return false; } };

async function runtimeAvailable() {
  try {
    if (process.env.TUFFCODE_LLAMA_RUNTIME) return fs.existsSync(path.join(process.env.TUFFCODE_LLAMA_RUNTIME, 'node_modules', 'node-llama-cpp'));
    require.resolve('node-llama-cpp');
    return true;
  } catch { return false; }
}

async function status() {
  return {
    runtime: await runtimeAvailable(),
    models: MODELS.map((m) => ({ id: m.id, name: m.name, sub: m.sub, size: m.size, downloaded: downloaded(m) })),
    downloading: download ? { id: download.id, got: download.got, total: download.total } : null,
    loaded: worker?.info ? { model: worker.model, ...worker.info } : null,
    ram: { total: os.totalmem(), free: os.freemem(), need: find().ram },
  };
}

// ---------------------------------------------------------------- the model file
async function fetchModel(id) {
  const m = find(id);
  if (download) throw new Error('A download is already running.');
  if (downloaded(m)) return status();
  await fsp.mkdir(modelsDir(), { recursive: true });
  const part = modelPath(m) + '.part';
  let have = 0;
  try { have = fs.statSync(part).size; } catch {}
  if (have > m.size) { await fsp.rm(part, { force: true }); have = 0; }
  const abort = new AbortController();
  download = { id: m.id, got: have, total: m.size, abort };
  const tell = () => onProgress({ id: m.id, got: download?.got || 0, total: m.size, done: false });
  try {
    // Carry on from where an interrupted download stopped.
    const res = await net.fetch(m.url, { headers: have ? { Range: `bytes=${have}-` } : {}, signal: abort.signal });
    if (!res.ok && res.status !== 206) throw new Error(`The download failed (${res.status}).`);
    if (have && res.status !== 206) { have = 0; download.got = 0; }
    const out = fs.createWriteStream(part, { flags: have ? 'a' : 'w' });
    let last = 0;
    for await (const chunk of res.body) {
      if (!out.write(chunk)) await new Promise((r) => out.once('drain', r));
      download.got += chunk.length;
      if (Date.now() - last > 250) { last = Date.now(); tell(); }
    }
    await new Promise((r, j) => out.end((err) => (err ? j(err) : r())));
    // Check the whole file, including a part downloaded earlier.
    const hash = crypto.createHash('sha256');
    await new Promise((r, j) => fs.createReadStream(part).on('data', (d) => hash.update(d)).on('end', r).on('error', j));
    if (fs.statSync(part).size !== m.size || hash.digest('hex') !== m.sha256) {
      await fsp.rm(part, { force: true });
      throw new Error("The downloaded model didn't match what was expected, so it was deleted. Try again.");
    }
    await fsp.rename(part, modelPath(m));
    onProgress({ id: m.id, got: m.size, total: m.size, done: true });
  } catch (err) {
    const stopped = abort.signal.aborted;
    onProgress({ id: m.id, got: download?.got || 0, total: m.size, done: true, error: stopped ? null : String(err.message || err), stopped });
    if (!stopped) throw err;
  } finally {
    download = null;
  }
  return status();
}

function cancelDownload() {
  download?.abort.abort();
}

async function removeModel(id) {
  const m = find(id);
  if (worker?.model === m.id) unload();
  await fsp.rm(modelPath(m), { force: true });
  await fsp.rm(modelPath(m) + '.part', { force: true });
  return status();
}

// ---------------------------------------------------------------- the worker
function workerFile() {
  const f = path.join(__dirname, 'ai-worker.mjs');
  return app.isPackaged ? f.replace(`app.asar${path.sep}`, `app.asar.unpacked${path.sep}`) : f;
}

function unload() {
  clearTimeout(idleTimer);
  if (!worker) return;
  const w = worker;
  worker = null;
  try { w.proc.kill(); } catch {}
  for (const [, r] of runs) r.emit({ kind: 'done', ok: false, error: 'Tuff AI stopped.' });
  runs.clear();
}

function touch() {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(unload, IDLE_MS);
}

function start(m) {
  if (worker?.model === m.id) return worker.ready;
  unload();
  const proc = utilityProcess.fork(workerFile(), [], { serviceName: 'Tuff AI', stdio: 'pipe', env: { ...process.env } });
  const w = { proc, model: m.id, info: null, err: '' };
  // What the worker prints only matters when it fails, so keep the last bit for the error message.
  proc.stderr?.on('data', (d) => { w.err = (w.err + d).slice(-2000); });
  proc.stdout?.on('data', () => {});
  w.ready = new Promise((resolve, reject) => {
    proc.on('message', (msg) => {
      if (msg.type === 'loaded') { w.info = { gpu: msg.gpu, device: msg.device }; resolve(w.info); return; }
      if (msg.type === 'failed') { reject(new Error(msg.error)); return; }
      const r = runs.get(msg.runId);
      if (!r) return;
      if (msg.type === 'delta') r.emit({ kind: 'delta', text: msg.text });
      else if (msg.type === 'done') { runs.delete(msg.runId); r.resolve(msg); }
    });
    proc.on('exit', (code) => {
      if (worker === w) worker = null;
      const why = w.err.trim().split(/\r?\n/).pop();
      reject(new Error(`Tuff AI's model stopped unexpectedly (code ${code}).${why ? ` ${why}` : ''}`));
      for (const [id, r] of runs) { runs.delete(id); r.resolve({ ok: false, error: 'Tuff AI stopped unexpectedly. Try again.' }); }
    });
  });
  w.ready.catch(() => {});
  const s = readSettings();
  proc.postMessage({ type: 'load', modelPath: modelPath(m), gpu: s.aiGpu === 'cpu' ? 'cpu' : 'auto', contextSize: 8192 });
  worker = w;
  return w.ready;
}

function ask(runId, type, payload, emit) {
  return new Promise((resolve) => {
    runs.set(runId, { emit, resolve });
    worker.proc.postMessage({ type, runId, maxTokens: MAX_TOKENS, ...payload });
  });
}

// ---------------------------------------------------------------- prompts
// The guide's opening sections stay the same for every chat, so the worker only reads them once.
// One or two more sections that match the question go in the message itself.
let guide = null;
function guideSections() {
  if (guide) return guide;
  const text = fs.readFileSync(path.join(__dirname, 'mcp', 'tuff-guide.md'), 'utf8').replace(/\r\n/g, '\n');
  const all = [];
  for (const part of text.split(/\n(?=##+ )/)) {
    const title = (/^##+ (.*)/.exec(part) || [])[1];
    if (title) all.push({ title, text: part.trim() });
  }
  const CORE = ['Tuff is not Python', 'Two rules that trip everyone up', 'Basics', 'Asking questions'];
  const rest = all.filter((s) => !CORE.includes(s.title) && s.title !== 'Using the tools');
  const words = (t) => t.toLowerCase().match(/[a-z_]{3,}/g) || [];
  const df = new Map();
  for (const s of rest) for (const w of new Set(words(s.text))) df.set(w, (df.get(w) || 0) + 1);
  guide = { core: all.filter((s) => CORE.includes(s.title)), rest, words, df };
  return guide;
}

function relevant(text, n = 2) {
  const g = guideSections();
  const q = new Set(g.words(text));
  return g.rest.map((s) => {
    const have = new Set(g.words(`${s.title} ${s.text}`));
    let score = 0;
    for (const w of q) if (have.has(w)) score += Math.log(1 + g.rest.length / (g.df.get(w) || 1));
    return { s, score };
  }).sort((a, b) => b.score - a.score).slice(0, n).filter((x) => x.score > 0).map((x) => x.s);
}

function systemPrompt() {
  return `You are Tuff AI, the helper built into TuffCode. You run on this computer, with no internet. You help beginners with the Tuff programming language.
Tuff is its own language, not Python. Only use what the Tuff guide below shows.
Keep answers short and friendly. When you give a program, give the whole program in one \`\`\`tuff code block.

# Tuff guide (the basics)

${guideSections().core.map((s) => s.text).join('\n\n')}`;
}

function codeOf(text) {
  const m = /```[ \t]*tuff[^\n]*\n([\s\S]*?)```/i.exec(text) || /```[^\n]*\n([\s\S]*?)```/.exec(text);
  return m ? m[1] : null;
}

// ---------------------------------------------------------------- runs (same events as the CLI agents)
async function run({ runId, prompt, model }, emit) {
  const send = (e) => emit({ runId, ...e });
  const m = find(model);
  if (!(await runtimeAvailable())) { send({ kind: 'done', ok: false, error: "Tuff AI's engine isn't in this copy of TuffCode." }); return; }
  if (!downloaded(m)) { send({ kind: 'done', ok: false, error: 'Download Tuff AI first (the card at the top).' }); return; }
  if (!worker || worker.model !== m.id) {
    const free = os.freemem();
    if (free < m.ram) {
      send({ kind: 'done', ok: false, error: `Tuff AI needs about ${(m.ram / 1e9).toFixed(1)} GB of free memory, and ${(free / 1e9).toFixed(1)} GB is free right now. Close some apps or browser tabs, then try again.` });
      return;
    }
    send({ kind: 'note', text: 'Starting Tuff AI on this computer…' });
  }
  send({ kind: 'model', id: m.id, name: m.name });
  try {
    await start(m);
  } catch (err) {
    send({ kind: 'done', ok: false, error: String(err.message || err) });
    return;
  }
  touch();
  const extra = relevant(prompt);
  const message = `${extra.length ? `More of the Tuff guide that may help:\n\n${extra.map((s) => s.text).join('\n\n')}\n\n---\n\n` : ''}${prompt}`;
  let r = await ask(runId, 'chat', { system: systemPrompt(), prompt: message }, send);
  if (r.ok && !r.stopped) {
    const code = codeOf(r.text || '');
    if (code) {
      send({ kind: 'tool', name: 'mcp__tuffcode__tuff_check', input: { code } });
      const c = await checkSource(code);
      send({ kind: 'tool_result', ok: c.ok });
      if (!c.ok && !c.unknown) {
        send({ kind: 'note', text: "The checker found a mistake, so Tuff AI is fixing it." });
        send({ kind: 'break' });
        r = await ask(runId, 'followup', { prompt: `That program doesn't pass Tuff's checker:\n${c.message}\n\nFix it and give the whole program again.` }, send);
        const again = codeOf(r.text || '');
        if (r.ok && again) {
          send({ kind: 'tool', name: 'mcp__tuffcode__tuff_check', input: { code: again } });
          const c2 = await checkSource(again);
          send({ kind: 'tool_result', ok: c2.ok });
          if (!c2.ok && !c2.unknown) send({ kind: 'note', text: `The checker still finds a mistake: ${c2.message}` });
        }
      }
    }
  }
  touch();
  send({ kind: 'done', ok: !!r.ok || !!r.stopped, error: r.ok || r.stopped ? null : r.error });
}

function stop(runId) {
  if (worker && runs.has(runId)) worker.proc.postMessage({ type: 'stop', runId });
}

function quit() {
  cancelDownload();
  unload();
}

module.exports = { MODELS, setup, status, fetchModel, cancelDownload, removeModel, run, stop, quit, codeOf };
