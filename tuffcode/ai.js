// Tuff AI: the offline helper. Its model, Pumice 1, runs in ai-worker.mjs (a utility process). This side
// downloads the model, checks there's enough memory, keeps the worker alive while it's being used, turns
// the question into a clearer task (the improver), and checks every Tuff program the model writes with
// tuff.py --check. A program that fails gets one more try with the checker's error, the way Tuff Bench
// scores it (tuff-ai/bakeoff/run.mjs runs this file to measure it).
const { app, utilityProcess, net } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const os = require('os');
const crypto = require('crypto');
const { pipeline } = require('stream/promises');

// Pumice 1 is TuffCode's model. For now it's the open Qwen3.5-2B (Apache 2.0) as it is, before any training on
// Tuff. Nothing TuffCode shows names the base model: Pumice 1 is the name people see and the one it answers to.
// The id and the file name stay the base model's, so a copy downloaded by 1.0.4 is still found.
const MODELS = [
  {
    id: 'qwen3.5-2b',
    name: 'Pumice 1',
    sub: "TuffCode's own AI. Runs on your computer, no internet needed.",
    file: 'Qwen3.5-2B-Q4_K_M.gguf',
    url: 'https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf',
    size: 1280835840,
    sha256: 'aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223',
    ram: 1.8e9, // measured peak in Phase 1 was ~1.6 GB, plus room for the answer
  },
];
// Thinking levels. budget: how many tokens it may think for before it must answer (node-llama-cpp
// enforces it, so a thinking loop can't run on). plan: before answering, the model rewrites the request
// as a clear task in one short pass (off since 1.1.0, with the improver). Off is exactly what 1.0.4 did. The budgets and the default come from
// Tuff Bench (tuff-ai/bakeoff/RESULTS.md, "Thinking levels").
const LEVELS = [
  { id: 'off', name: 'Off', sub: 'Answers straight away', budget: 0, plan: false, temperature: 0.2 },
  { id: 'low', name: 'Low', sub: 'Thinks for a moment first', budget: 128, plan: false, temperature: 0.2 },
  { id: 'medium', name: 'Medium', sub: 'Thinks a little longer', budget: 256, plan: false, temperature: 0.2 },
  { id: 'high', name: 'High', sub: 'Thinks longest. Slower, and not always better', budget: 512, plan: false, temperature: 0.2 },
];
const DEFAULT_LEVEL = 'low';
const level = (id) => LEVELS.find((l) => l.id === id) || LEVELS.find((l) => l.id === DEFAULT_LEVEL);
const sampling = (lv) => ({ temperature: lv.temperature, ...(lv.topK ? { topK: lv.topK } : {}), ...(lv.topP ? { topP: lv.topP } : {}) });
const IDLE_MS = 5 * 60 * 1000;
const MAX_TOKENS = 700;
const PLAN_TOKENS = 160;

let checkSource = async () => ({ ok: true, unknown: true });
let readSettings = () => ({});
let onProgress = () => {};
let download = null; // { id, got, total, abort }
let worker = null; // { proc, model, ready, info }
let idleTimer = null;
const runs = new Map(); // runId -> { emit, resolve }: questions the worker is answering
const active = new Set(); // runIds of questions still going, from the first check to the last event
const stoppedRuns = new Set(); // the active ones the person stopped

function setup(opts) {
  if (opts.checkSource) checkSource = opts.checkSource;
  if (opts.settings) readSettings = opts.settings;
  if (opts.progress) onProgress = opts.progress;
}

const modelsDir = () => path.join(app.getPath('userData'), 'models');
const modelPath = (m) => path.join(modelsDir(), m.file);
const find = (id) => MODELS.find((m) => m.id === id) || MODELS[0];
const downloaded = (m) => { try { return fs.statSync(modelPath(m)).size === m.size; } catch { return false; } };
// Error text for people: the model's file is named after the base model, so its path and name (and the
// download's .part) become "its model file". Pumice 1 is the only name TuffCode shows.
const tidy = (m, text) => String(text).split(modelPath(m)).join('its model file').replace(/its model file\.part\b/g, 'its model file')
  .replace(/[^\s'"]*\.gguf(?:\.part)?\b/gi, 'its model file');

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
    ram: { total: os.totalmem(), free: freeMemory(), need: find().ram },
  };
}

// Memory the model can have. On a Mac, os.freemem() leaves out the cache macOS gives back when asked,
// so it's often only a few hundred MB; availableMemory() counts it. On Windows they're the same.
const freeMemory = () => process.availableMemory?.() ?? os.freemem();

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
    // Carry on from where an interrupted download stopped. A .part that's already whole (TuffCode was
    // closed while it was being checked, say) only needs the check below: the server refuses to send
    // anything from past the end.
    if (have < m.size) {
      let res = await net.fetch(m.url, { headers: have ? { Range: `bytes=${have}-` } : {}, signal: abort.signal });
      if (have && res.status === 416) {
        // The server can't carry on from there, so start again from the beginning.
        await res.body?.cancel().catch(() => {});
        have = 0;
        download.got = 0;
        res = await net.fetch(m.url, { signal: abort.signal });
      }
      if (!res.ok && res.status !== 206) throw new Error(`The download failed (${res.status}).`);
      if (have && res.status !== 206) { have = 0; download.got = 0; }
      let last = 0;
      // pipeline hands a failed write (a full disk, say) and Stop to the catch below, and closes the file.
      await pipeline(res.body, async function* count(body) {
        for await (const chunk of body) {
          download.got += chunk.length;
          if (Date.now() - last > 250) { last = Date.now(); tell(); }
          yield chunk;
        }
      }, fs.createWriteStream(part, { flags: have ? 'a' : 'w' }), { signal: abort.signal });
    }
    // Check the whole file, including a part downloaded earlier.
    const hash = crypto.createHash('sha256');
    await new Promise((r, j) => fs.createReadStream(part).on('data', (d) => hash.update(d)).on('end', r).on('error', j));
    if (fs.statSync(part).size !== m.size || hash.digest('hex') !== m.sha256) {
      await fsp.rm(part, { force: true });
      throw new Error("The downloaded model didn't match what was expected, so it was deleted. Try again.");
    }
    // On Windows, antivirus can hold a brand-new file for a moment, so try the rename a few times.
    for (let i = 0; ; i++) {
      try { await fsp.rename(part, modelPath(m)); break; } catch (err) {
        if (i >= 4 || !['EPERM', 'EBUSY', 'EACCES'].includes(err.code)) throw err;
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    onProgress({ id: m.id, got: m.size, total: m.size, done: true });
  } catch (err) {
    const stopped = abort.signal.aborted;
    const why = err.code === 'ENOSPC' ? `There isn't enough free disk space. ${m.name} needs ${(m.size / 1e9).toFixed(1)} GB. Free some up, then try again.`
      : ['EPERM', 'EBUSY', 'EACCES'].includes(err.code) ? `Couldn't save ${m.name}: something else is using its file (often an antivirus checking it). Try again in a minute.`
      : tidy(m, err.message || err);
    onProgress({ id: m.id, got: download?.got || 0, total: m.size, done: true, error: stopped ? null : why, stopped });
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
// It stays inside app.asar with node-llama-cpp's JavaScript; only its native files are unpacked.
const workerFile = () => path.join(__dirname, 'ai-worker.mjs');

function unload() {
  clearTimeout(idleTimer);
  if (!worker) return;
  const w = worker;
  worker = null;
  try { w.proc.kill(); } catch {}
  // Each question being answered then finishes with this, and sends its own done.
  for (const [, r] of runs) r.resolve({ ok: false, error: `${find(w.model).name} stopped.` });
  runs.clear();
}

// The model is unloaded after 5 minutes without questions, but never while one is being answered.
function touch() {
  clearTimeout(idleTimer);
  if (!active.size) idleTimer = setTimeout(unload, IDLE_MS);
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
      if (msg.type === 'failed') {
        // The model didn't load. Let this worker go, so the next question starts a fresh one.
        if (worker === w) worker = null;
        try { proc.kill(); } catch {}
        reject(new Error(`${m.name} couldn't start: ${tidy(m, msg.error || "its model file didn't load")}`));
        return;
      }
      const r = runs.get(msg.runId);
      if (!r) return;
      if (msg.type === 'delta') r.emit({ kind: 'delta', text: msg.text });
      else if (msg.type === 'thinking') r.emit({ kind: 'thinking', text: msg.text });
      else if (msg.type === 'thought') r.emit({ kind: 'thought', ms: msg.ms, tokens: msg.tokens, cut: msg.cut });
      else if (msg.type === 'done') { runs.delete(msg.runId); r.resolve(msg); }
    });
    proc.on('exit', (code) => {
      // A worker that was already let go (unloaded, or failed to load) has no questions left here.
      const mine = worker === w;
      if (mine) worker = null;
      const why = tidy(m, w.err.trim().split(/\r?\n/).pop() || '');
      reject(new Error(`${m.name} stopped unexpectedly (code ${code}).${why ? ` ${why}` : ''}`));
      if (mine) for (const [id, r] of runs) { runs.delete(id); r.resolve({ ok: false, error: `${m.name} stopped unexpectedly. Try again.` }); }
    });
  });
  w.ready.catch(() => {});
  const s = readSettings();
  // aiThreads is only for measuring (the bake-off's CPU check); the app lets node-llama-cpp pick.
  const threads = Number.isInteger(s.aiThreads) && s.aiThreads > 0 ? s.aiThreads : undefined;
  proc.postMessage({ type: 'load', modelPath: modelPath(m), gpu: s.aiGpu === 'cpu' ? 'cpu' : 'auto', contextSize: 8192, threads });
  worker = w;
  return w.ready;
}

function ask(runId, type, payload, emit) {
  if (!worker) return Promise.resolve({ ok: false, error: `${find().name} stopped unexpectedly. Try again.` });
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

// The n sections that share the most (rare) words with the text. first: sections that go in whatever the
// text says; skip: sections to leave out.
function relevant(text, n = 2, { first = [], skip = [] } = {}) {
  const g = guideSections();
  const q = new Set(g.words(text));
  const forced = g.rest.filter((s) => first.includes(s.title)).slice(0, n);
  return [...forced, ...g.rest.filter((s) => !first.includes(s.title) && !skip.includes(s.title)).map((s) => {
    const have = new Set(g.words(`${s.title} ${s.text}`));
    let score = 0;
    for (const w of q) if (have.has(w)) score += Math.log(1 + g.rest.length / (g.df.get(w) || 1));
    return { s, score };
  }).sort((a, b) => b.score - a.score).slice(0, n - forced.length).filter((x) => x.score > 0).map((x) => x.s)];
}

// Who it is. Asked "who are you?" or "are you ChatGPT?", a base model gives its own maker's name or a made-up
// helper's, so it's told plainly who it is here: Pumice 1. The exact sentence to answer with is only in the improver's card for
// those questions (GOOD.about): with it in the system prompt, the 2B started almost every answer with it.
function systemPrompt() {
  const m = MODELS[0];
  return `You are ${m.name}, TuffCode's own AI model. You power Tuff AI, the helper built into TuffCode, the code editor for the Tuff programming language. You run on the person's own computer, with no internet.
If they ask who or what you are, which model you are, or who made you, say it in a sentence or two: you're ${m.name}, TuffCode's own AI model, running right here on their computer. You are not ChatGPT, Claude or Gemini, and you're not a person. When they ask about anything else, don't say who you are: go straight to their question.
You help beginners, often kids, with the Tuff programming language.
Tuff is its own language, not Python. Only use what the Tuff guide below shows.
Keep answers short and friendly. When you give a program, give the whole program in one \`\`\`tuff code block.

# Tuff guide (the basics)

${guideSections().core.map((s) => s.text).join('\n\n')}`;
}

// ---------------------------------------------------------------- the improver
// Before the model answers, the question is turned into a clearer task, the same way every time: what kind
// of request it is, the part of the open file that matters, the error from the last run, and what a good
// answer looks like. That card goes at the end of the message (small models follow what they read last)
// and is shown in the reply, collapsed. At Medium and High the model then rewrites it in its own words
// (the plan) before it answers.
// What the panel sends (all but the question may be missing):
//   { question, file, code, selection: { from, to, text }, history: ['Them: …', 'You: …'], runError }
const FILE_LIMIT = 6000;
const fence = '```';
const trim = (s, n) => (s.length > n ? `${s.slice(0, n)}\n… (cut off, ${s.length - n} more characters)` : s);
const baseName = (p) => String(p || '').split(/[\\/]/).pop();
const errLineOf = (s) => +((/Tuff error on line (\d+)/.exec(s || '') || [])[1] || 0);

const MAKE = '(make|write|create|build|code|program|add|change|turn|give me|show me)';
// With their program open, "my player doesn't move", "it never stops" or "the ball should bounce" say what
// it does wrong: a not, never or should, then (a few words on) something a program does. Without that,
// "I don't get what dt means", "Why don't we use def?" and "What should I add next?" are questions.
const DOES = "(work|run|ran|show|say|said|print|move|happen|stop|start|appear|change|count|jump|load|go|went|end|close|open|play|draw|display|fall|fell|bounce|turn|hit|touch|update|ask|wait|respond|react|spawn|collide|do (anything|what|it|that))(s|es|ed|d|ing|ning|ped|ping|n)?\\b";
// ("I don't get why it moves" is about them, not the program.)
const NOT_DOES = new RegExp(`\\b(doesn'?t|does not|don'?t|do not|didn'?t|did not|won'?t|will not|isn'?t|is not|aren'?t|are not|wasn'?t|was not|can'?t|cannot|can not|couldn'?t|could not|never|nothing)\\s+(?!(get|understand|know|see|think|remember|mind)\\b)(?:[\\w']+\\s+){0,3}?${DOES}|\\b(can'?t|cannot) see\\b|\\b(keeps|kept) \\w+ing\\b`);
// "Should" says what it should do, but not in "should I…?" or "Where should the score go?".
const SHOULD_DOES = new RegExp(`\\bshould(n'?t| not)?\\s+(?!(i|we|you)\\b)(?:[\\w']+\\s+){0,3}?${DOES}`);
const ASKING = /^\s*(what|why|how|where|when|which|who|should|can|could|would|will|is|are|do|does)\b/;
const saysWhatsWrong = (s) => NOT_DOES.test(s) || s.split(/[.?!\n]+/).some((part) => !ASKING.test(part) && SHOULD_DOES.test(part));
function kindOf(question, hasCode) {
  const s = question.toLowerCase();
  if (/\b(fix|bugs?|broken|errors?|wrong|crash(es|ed|ing)?|stuck|mistakes?|instead|not working|does not work)\b|n'?t (work|run)/.test(s)) return 'fix';
  // "Make a program that asks "What is your name?"" is a request, not a question, and so is "Make it so the
  // player can't go off the screen".
  const making = new RegExp(`^(please |ok,? |now )?((can|could|will|would) you (please )?|i want (you to |a |an )?|i'd like (you to |a |an )?|let's )?${MAKE}\\b`).test(s);
  if (hasCode && !making && saysWhatsWrong(s)) return 'fix';
  // "I don't get what dt means", "I don't understand this": explain their code. ("I don't know how to add a
  // score" goes on to the rules below: a request.)
  if (hasCode && /\bi (don'?t|do not|didn'?t|did not) (get|understand|know|see)\b/.test(s) && /\b(mean(s|ing|t)?|this|that|it|(my|the|this) (code|program)|line \d+)\b/.test(s)) return 'explain';
  if (/\b(explain|walk me through|step by step|what do(es)? (this|it|that|my|the code|the program)|how does (this|it|that|my)|what is this|what's this|mean)\b/.test(s)) return 'explain';
  if (making) return 'write';
  // "Who are you?", "Are you ChatGPT?", "Which model is this?"
  if (s.length < 120 && /\b(who|what) (are|r) (you|u)\b|\bare (you|u) (an? )?(chat ?gpt|gpt|claude|gemini|qwen|llama|copilot|tuff ai|pumice|ai|robot|bot|person|human|real)\b|\b(which|what) (ai |language )?model\b|\bwho (made|built|created|trained) (you|u|this)\b|\bwhat('s| is) your name\b/.test(s)) return 'about';
  if (/\b(suggest|ideas?|tips?|ways to|teach|how (do|can|could|should) i|(what|which|where|when) (should|can|could|do) (i|we)|should (i|we)|what (is|are)|why|can i|is there)\b/.test(s)) return 'question';
  if (new RegExp(`\\b${MAKE}\\b`).test(s)) return 'write';
  return 'question';
}

// "Make a game where you catch apples" is a tgame game. A guessing game, a quiz or a game score in a variable
// is a console program (Tuff Bench has those), and an mtgui game is a window.
const PLAYS = /\b(catch(es|ing)?|jump(s|ing)?|dodg(e|es|ing)|chas(e|es|ing)|shoot(s|ing|er)?|collect(s|ing)?|fall(s|ing)?|enem(y|ies)|players?|paddles?|balls?|maze|rac(e|es|ing)|racer|pong|snake|flappy|clicker|asteroids?|breakout|invaders|aliens?|space ?ships?|ships?|coins?|obstacles?|rocks?|bricks?|fly(ing)?|runner|3d|world)\b/;
const NOT_PLAYED = /\b(guess(es|ing)?|quiz|trivia|hangman|riddles?|text|adventure|words?|dice|tic.?tac.?toe|in a variable|m?tgui|atgui)\b/;
const isGame = (s) => /\bgames?\b/.test(s) && PLAYS.test(s) && !NOT_PLAYED.test(s);
// "Make a 3D world with hills and a lake" is a tgame world too, without the word game ("Hello world" isn't).
const isWorld = (s) => /\bterrain\b|\b3d (worlds?|scenes?|land|maps?)\b/.test(s) || (/\bworlds?\b/.test(s) && /\b(hills?|mountains?|lakes?|valleys?|islands?|forests?)\b/.test(s));

// Menus, buttons and screens in a game: tgame's panels and screens (the guide's "Menus, buttons and screens in
// games"). "Add a Shop button" with a game open, or "a game with a start screen", is game UI, not an app window.
const GAME_UI = /\b(menus?|buttons?|panels?|shops?|stores?|inventory|upgrades?|settings|text ?box(es)?|sliders?|dropdowns?|checkbox(es)?|widgets?|ui|gui|(start|title|pause|game ?over|end|win|lose|level|options|main|splash) (screens?|menus?|pages?)|click to (play|start|enter))\b/;
const SCREEN_WORDS = /\b(start|title|pause|game ?over) (screen|menu)s?\b|\bclick to (play|start|enter)\b/;

// Console, window, game or web: from the words, or else from the library the open file mentions.
function targetOf(question, code) {
  const s = question.toLowerCase();
  if (/\btgame\b|\bsprites?\b|arrow keys|\bplatformer\b/.test(s) || isGame(s) || isWorld(s)) return 'game';
  if (/\btap\b|\bweb ?(page|site)s?\b|\bwebsite\b|\bapi\b|\burl\b|\binternet\b/.test(s)) return 'web';
  const lib = /^\s*(?:mention|import)\s+(\w+)/m.exec(code || '');
  const inGame = lib?.[1] === 'tgame' || (/\bgames?\b/.test(s) && !NOT_PLAYED.test(s) && SCREEN_WORDS.test(s));
  if (inGame && GAME_UI.test(s) && !/\b(m?tgui|atgui|apps?)\b/.test(s)) return 'game';
  if (/\b(m?tgui|atgui|windows?|buttons?|sliders?|labels?|gui|clicks?|clicked|text ?box|checkbox|dropdown|toggle|headings?)\b/.test(s)) return 'window';
  if (lib) return { tgui: 'window', mtgui: 'window', atgui: 'window', tgame: 'game', tap: 'web' }[lib[1]] || 'console';
  return 'console';
}

// Sections of the guide about windows, games and the web. A console program doesn't need them, and with
// them in the message the model answers "ask my name" with a window (37 of Qwen's 105 failed write tasks
// in Phase 1 did).
const WINDOW_SECTIONS = ['App windows (tgui / mtgui)', 'Events: what the function gets', 'Timers', 'Pages (several screens in one window)', 'Layout and size', 'Looking good', 'atgui'];
// The guide splits at every heading, so tgame's "Menus, buttons and screens in games", "Land and lighting (3D)",
// "Physics" and "Games Tuff Engine can edit" are sections of their own. A game request about menus, buttons or
// screens always gets the menus one (sectionsFor).
const GAME_UI_SECTION = 'Menus, buttons and screens in games';
// Splash screens, a main menu, or locking and freeing the mouse in 3D: the guide's section on them.
const INTRO_SECTION = 'Splash screens, main menus and the mouse';
const INTRO = /\b(splash|intro (screen|video)s?|logo screens?|main ?menus?|home (screen|menu)s?)\b|\b(mouse|cursor|pointer)\b.*\b(lock(s|ed|ing)?|unlock(s|ed|ing)?|free|release[sd]?|captur(e|es|ed)|grab(s|bed)?|visible|hidden)\b|\b(lock(s|ed|ing)?|unlock(s|ed|ing)?|free|release|capture|grab|show|hide)\b.*\b(mouse|cursor|pointer)\b/;
const GAME_SECTIONS = ['tgame', GAME_UI_SECTION, INTRO_SECTION, 'Land and lighting (3D)', 'Physics', 'Games Tuff Engine can edit'];
const SECTIONS = {
  console: { skip: [...WINDOW_SECTIONS, 'Libraries', ...GAME_SECTIONS, 'tap'] },
  window: { first: ['App windows (tgui / mtgui)'], skip: [...GAME_SECTIONS, 'tap', 'Live lines and clearing (console programs)'] },
  game: { first: ['tgame'], skip: [...WINDOW_SECTIONS, 'tap'] },
  web: { first: ['tap'], skip: [...WINDOW_SECTIONS, ...GAME_SECTIONS] },
};
// The sections for a request (and how many): a game's menus, buttons or screens add the guide's section on them,
// with room left for one more, like the land for a 3D world.
// Splash screens, main menus and the mouse only come when the request is about them (not in the place of the land's).
function sectionsFor(target, question) {
  const q = question.toLowerCase();
  const ui = target === 'game' && GAME_UI.test(q), intro = target === 'game' && INTRO.test(q);
  const want = target === 'game' && !intro ? { ...SECTIONS.game, skip: [...SECTIONS.game.skip, INTRO_SECTION] } : SECTIONS[target];
  if (!ui && !intro) return { n: 2, want };
  const first = [...want.first, ...(ui ? [GAME_UI_SECTION] : []), ...(intro ? [INTRO_SECTION] : [])];
  return { n: first.length + 1, want: { ...want, first } };
}
const WANT = {
  write: 'a Tuff program that does what they describe',
  fix: 'their program fixed, and to know what was wrong',
  explain: 'an explanation of their code in simple words',
  question: 'an answer to their question about Tuff',
  about: 'to know who you are',
  plan: 'a plan for what they asked, before any code is written',
  edit: 'their open program changed to do what they asked',
};
const GOOD = {
  write: `the whole program in one ${fence}tuff block, then one sentence on how it works. It must show exactly the text they asked for.`,
  fix: `one or two sentences naming the mistake and the line it's on, then the whole fixed program in one ${fence}tuff block.`,
  explain: 'a short explanation, step by step, in plain words. Quote small bits of their code. No whole new program unless they ask for one.',
  question: `a short, friendly answer in plain words, with a tiny ${fence}tuff example if it helps (only real Tuff code goes in it).`,
  about: `a sentence or two, like: "I'm ${MODELS[0].name}, TuffCode's own AI model, and I run right here on your computer." No code.`,
  plan: 'a numbered plan of 3 to 6 short steps in plain words: what to add or change, and where in their program. No code.',
  edit: `one sentence on what you changed, then the whole changed program in one ${fence}tuff block: all of it, not just the new part.`,
};
const ASKS = /\b(asks?|asking|types?|typed|typing|enters?|input|answers?|guess(es)?)\b/i;
const TARGET = {
  console: 'It\'s a console program, not a window: show text with say. Don\'t use mtgui or tgui.',
  consoleAsks: 'It\'s a console program, not a window: show text with say, and ask each question with input on a line of its own (a name, =, input, then the question in quotes). Don\'t use mtgui or tgui.',
  window: 'It\'s an app window: start with mention mtgui (or mention tgui for the plain look), then app = mtgui.window("Title", 400, 300). No input or wait in a window app.',
  game: 'It\'s a tgame game: start with mention tgame, then game = tgame.window("Title", 800, 600).',
  world: 'It\'s a tgame 3D world: start with mention tgame, then game = tgame.world("Title"). Hills, lakes and mountains go on land = game:terrain(200).',
  web: 'It uses the web: start with mention tap, then res = tap.get(url).',
  gameUi: 'Buttons, text boxes and menus go on the game, not in an app window: bar = game:panel("top left") pins widgets to it (bar:button("Shop", open_shop)), shop = game:screen("Shop") is a screen over it that pauses the game (shop:hide() until it\'s needed), and start = game:start_screen("Title", "Click to play") waits for a click to play.',
  intro: 'Splash screens are game:splash("logo.png", 3) or game:splash("Some text") (game:splash() is "Made with Tuff"), and a main menu is menu = game:main_menu("Title") with menu:button("Play", play), where func play(): menu:hide(). In 3D, world:lock_mouse() and world:unlock_mouse() lock and free the mouse; screens free it by themselves while they show.',
};
const NOT_PYTHON = 'Tuff, not Python: func (not def), true, false and nil, x is y, items:add(x) (not .append), "Hi " + name (no f-strings), and range(1, 3) gives 1, 2, 3.';

// The lines of a long file that matter: around the selection, the error's line, or the lines that share
// the most words with the question.
function focusOf(code, { line, selection, question }) {
  const lines = code.split('\n');
  if (code.length <= FILE_LIMIT) return { text: code, from: 1, to: lines.length, whole: true };
  let center = selection ? Math.round((selection.from + selection.to) / 2) : line;
  if (!center) {
    const want = new Set((question.toLowerCase().match(/[a-z_]{4,}/g) || []));
    let best = 0;
    lines.forEach((l, i) => {
      const n = (l.toLowerCase().match(/[a-z_]{4,}/g) || []).filter((w) => want.has(w)).length;
      if (n > best) { best = n; center = i + 1; }
    });
  }
  center = Math.min(Math.max(1, center || 1), lines.length);
  let from = center, to = center, size = lines[center - 1].length + 1;
  for (let grew = true; grew;) {
    grew = false;
    if (to < lines.length && size + lines[to].length + 1 <= FILE_LIMIT) { size += lines[to].length + 1; to++; grew = true; }
    if (from > 1 && size + lines[from - 2].length + 1 <= FILE_LIMIT) { from--; size += lines[from - 1].length + 1; grew = true; }
  }
  return { text: lines.slice(from - 1, to).join('\n'), from, to, whole: false };
}

const hasFile = (input) => !!input.file && typeof input.code === 'string';

// mode: the panel's Plan / Ask / Edit. Plan always plans; Edit changes the open file (or writes a program when
// none is open), and the panel puts the checked program into the file.
function improve(input) {
  const question = String(input.question || '').trim();
  const code = hasFile(input) ? input.code : '';
  const guessed = kindOf(question, !!code.trim());
  const kind = input.mode === 'plan' ? 'plan' : input.mode === 'edit' ? (!code.trim() ? 'write' : guessed === 'fix' ? 'fix' : 'edit') : guessed;
  const target = targetOf(question, code);
  // The question itself, when it's short enough to repeat: "an answer to: how do I add a score?"
  const said = question.replace(/\s+/g, ' ');
  const lines = [`They want: ${kind === 'question' && said.length <= 120 ? `an answer to: ${said}` : WANT[kind]}.`];
  let focus = null;
  if (hasFile(input)) {
    focus = focusOf(code, { line: errLineOf(input.runError || question), selection: input.selection, question });
    const n = code.replace(/\n$/, '').split('\n').length;
    const size = code.trim() ? `${n} line${n === 1 ? '' : 's'}` : 'empty';
    const which = focus.whole ? '' : `, and the part that matters is above (lines ${focus.from} to ${focus.to})`;
    lines.push(kind === 'write'
      ? `Their open file is ${baseName(input.file)} (${size})${which}. Change it if the request is about it; otherwise write a new program.`
      : kind === 'edit'
        ? `Their program is ${baseName(input.file)} (${size})${which}. Change it to do what they ask, and keep everything else as it is.`
        : `Their program is ${baseName(input.file)} (${size})${which}.`);
    if (kind === 'explain' && said.split(' ').length <= 2) lines.push(`Their message is short, so say what ${baseName(input.file)} does as a whole: what happens when it runs, then its main parts.`);
  }
  const err = input.runError || (/Tuff error on line \d+[^\n]*/.exec(question) || [])[0] || '';
  const errLine = errLineOf(err);
  if (err && kind !== 'write') {
    const src = errLine && code ? code.split('\n')[errLine - 1] : '';
    lines.push(`When they last ran it, it stopped${errLine ? ` at line ${errLine}` : ''}${src?.trim() ? ` (${src.trim()})` : ''}: ${err.split('\n')[0].trim()}`);
  }
  const in3d = target === 'game' && (isWorld(question.toLowerCase()) || /\b3d\b/i.test(question) || /\btgame\.world\(/.test(code));
  if (kind === 'write' || kind === 'edit' || (kind === 'fix' && target !== 'console')) {
    lines.push(TARGET[target === 'console' && ASKS.test(question) ? 'consoleAsks' : in3d ? 'world' : target]);
    if (target === 'game' && GAME_UI.test(question.toLowerCase())) lines.push(TARGET.gameUi);
    if (target === 'game' && INTRO.test(question.toLowerCase())) lines.push(TARGET.intro);
  }
  lines.push(`A good answer: ${GOOD[kind]}`);
  if (kind === 'write' || kind === 'fix' || kind === 'edit') lines.push(NOT_PYTHON);
  return { kind, target, focus, text: lines.map((l) => `- ${l}`).join('\n') };
}

// The message the model reads. Without a card it's exactly what 1.0.4 sent. plan: the model's own rewrite
// of the request (Medium and High), added to the card.
function buildMessage(input, card, plan = '') {
  const question = String(input.question || '').trim();
  const parts = [];
  if (hasFile(input)) {
    const name = baseName(input.file);
    const lang = /\.tuf$/i.test(name) ? 'tuff' : '';
    if (!card) parts.push(`Their open file, ${name}:\n${fence}${lang}\n${trim(input.code, FILE_LIMIT)}\n${fence}`);
    else if (card.focus.whole) parts.push(`Their open file, ${name}:\n${fence}${lang}\n${card.focus.text}\n${fence}`);
    else parts.push(`Their open file, ${name}, lines ${card.focus.from} to ${card.focus.to}:\n${fence}${lang}\n${card.focus.text}\n${fence}`);
  }
  const sel = input.selection;
  if (sel?.text) parts.push(`They selected lines ${sel.from} to ${sel.to}:\n${fence}\n${trim(sel.text, 3000)}\n${fence}`);
  if (card && input.runError && !question.includes(input.runError.split('\n')[0])) parts.push(`When they last ran it, it stopped with this error:\n${fence}\n${trim(input.runError, 1500)}\n${fence}`);
  if (input.history?.length) parts.push(`Earlier in this chat (already answered):\n${input.history.join('\n')}`);
  parts.push(`Their question:\n${question}`);
  // Plan and Edit, said plainly (the improver's card said more, before it was turned off).
  if (!card && input.mode === 'plan') parts.push('Answer with a numbered plan of 3 to 6 short steps in plain words: what to add or change, and where. No code yet.');
  if (!card && input.mode === 'edit' && hasFile(input)) parts.push(`Change their program to do what they ask, keep everything else as it is, and give back the whole changed program in one ${fence}tuff block.`);
  if (card) parts.push(`What TuffCode worked out from their question:\n${card.text}${plan ? `\n- The task, as you rewrote it: ${plan.replace(/\s*\n\s*/g, ' ')}` : ''}`);
  const body = parts.join('\n\n');
  const sections = card && sectionsFor(card.target, question);
  const extra = card ? relevant(`${question}\n${card.focus?.text || ''}\n${input.runError || ''}`, sections.n, sections.want) : relevant(body);
  return `${extra.length ? `More of the Tuff guide that may help:\n\n${extra.map((s) => s.text).join('\n\n')}\n\n---\n\n` : ''}${body}`;
}

// The plan pass. A 2B model asked to plan tends to answer straight away, so the plan stops at the first
// code block, and only the task it wrote is kept.
const PLAN_ASK = '\n\nDon\'t answer yet. First rewrite their request as a clear task for yourself, in 2 to 4 short lines starting with "Task:": what to make or fix, the exact text it must show, and what your answer will include. No code.';
const PLAN_STOP = ['```', '**Answer', 'Answer:'];
const cleanPlan = (text) => String(text || '').replace(/(```|\*\*Answer|Answer:)[\s\S]*$/, '').replace(/^\s*\**Task:?\**:?\s*/i, '').trim();
// Thinking levels also say how to think: the 2B otherwise spends its whole budget restating the request.
const THINK_HINT = '\n\n(Think in a few short lines: what the answer needs, then check it against the Tuff rules. Don\'t repeat yourself.)';

// Only a ```tuff block is a program to check. Other blocks are an error message, what a program prints,
// or another language, and the checker would wrongly say they're broken.
function codeOf(text) {
  const m = /```[ \t]*tuff[^\n]*\n([\s\S]*?)```/i.exec(text);
  return m ? m[1] : null;
}

// ---------------------------------------------------------------- runs (same events as the CLI agents)
async function run(params, emit) {
  // While a question is going, the idle timer waits.
  active.add(params.runId);
  touch();
  try {
    await answerRun(params, emit);
  } finally {
    active.delete(params.runId);
    stoppedRuns.delete(params.runId);
    touch();
  }
}

// params.ai: the question's parts (see the improver); without them, prompt is the whole question.
// params.effort: the thinking level ('' for the default). params.improve: false leaves the question as it
// is (Tuff Bench measures both).
// The improver (a "Made your request clearer" card, and Medium and High's plan) is off since 1.1.0: people
// found it got in the way ("hi" became "explain my program"). Tuff Bench can still turn it on (improve: true).
async function answerRun({ runId, prompt, model, effort, ai: parts, improve: improving = false }, emit) {
  const send = (e) => emit({ runId, ...e });
  const m = find(model);
  const lv = level(effort);
  const t0 = Date.now();
  // What happened, for Tuff Bench (the panel doesn't need it).
  const stats = { level: lv.id, improved: false, plan: '', planMs: 0, thinkMs: 0, thinkTokens: 0, cut: 0, answers: [] };
  const finish = (e) => send({ kind: 'done', ...e, stats: { ...stats, ms: Date.now() - t0 } });
  // Stop can come at any point: while the model loads, while it plans, while the checker runs, or between
  // the two answers.
  const halted = () => stoppedRuns.has(runId);
  if (!(await runtimeAvailable())) { finish({ ok: false, error: "Tuff AI's engine isn't in this copy of TuffCode." }); return; }
  if (!downloaded(m)) { finish({ ok: false, error: `Download ${m.name} first (the card at the top).` }); return; }
  if (!worker || worker.model !== m.id) {
    const free = freeMemory();
    if (free < m.ram) {
      finish({ ok: false, error: `${m.name} needs about ${(m.ram / 1e9).toFixed(1)} GB of free memory, and ${(free / 1e9).toFixed(1)} GB is free right now. Close some apps or browser tabs, then try again.` });
      return;
    }
    send({ kind: 'note', text: `Starting ${m.name} on this computer…` });
  }
  send({ kind: 'model', id: m.id, name: m.name });
  // What it's doing, for the panel's "Thinking…" label: sent only when it changes.
  let now = '';
  const stage = (text) => { if (text !== now) { now = text; send({ kind: 'stage', text }); } };
  stage('Reading your question');
  const input = parts && typeof parts === 'object' ? { ...parts, question: parts.question ?? prompt } : { question: prompt };
  const card = improving ? improve(input) : null;
  if (card) { stats.improved = true; stats.kind = card.kind; stats.target = card.target; send({ kind: 'improved', text: card.text }); }
  try {
    await start(m);
  } catch (err) {
    finish({ ok: false, error: String(err.message || err) });
    return;
  }
  if (halted()) { finish({ ok: true, error: null }); return; }
  const message = buildMessage(input, card);
  // Each answer's events, with the stage the panel shows ("Thinking", then "Writing").
  const relay = () => {
    let thinking = false, writing = false;
    return (e) => {
      if (e.kind === 'thinking' && !thinking) { thinking = true; stage('Thinking'); }
      if (e.kind === 'delta' && !writing) { writing = true; stage('Writing'); }
      if (e.kind === 'thought') { stats.thinkMs += e.ms; stats.thinkTokens += e.tokens; if (e.cut) stats.cut++; }
      send(e);
    };
  };
  const thinks = lv.budget > 0;
  let r;
  let task = message;
  if (card && lv.plan) {
    // The plan: in one short pass (no thinking), the model rewrites the request as a task in its own words.
    // It goes in the card, and the answer is a fresh chat: asked to answer in a second turn of the same chat,
    // the 2B repeated its plan and lost track of the code (Tuff Bench, RESULTS.md).
    stage('Planning');
    const p0 = Date.now();
    const p = await ask(runId, 'chat', { system: systemPrompt(), prompt: message + PLAN_ASK, maxTokens: PLAN_TOKENS, thinking: false, budget: 0, stop: PLAN_STOP, ...sampling(lv) }, (e) => {
      if (e.kind === 'delta') send({ kind: 'plan', text: e.text });
    });
    stats.planMs = Date.now() - p0;
    stats.plan = cleanPlan(p.text);
    if (!p.ok || p.stopped || halted()) {
      const ok = !!p.ok || !!p.stopped || halted();
      finish({ ok, error: ok ? null : p.error });
      return;
    }
    if (stats.plan) task = buildMessage(input, card, stats.plan);
    stage(thinks ? 'Thinking' : 'Writing');
  }
  r = await ask(runId, 'chat', { system: systemPrompt(), prompt: task + (thinks ? THINK_HINT : ''), thinking: thinks, budget: lv.budget, ...sampling(lv) }, relay());
  stats.answers.push(r.text || '');
  if (r.ok && !r.stopped && !halted()) {
    const code = codeOf(r.text || '');
    if (code) {
      stage('Checking the code');
      send({ kind: 'tool', name: 'mcp__tuffcode__tuff_check', input: { code } });
      const c = await checkSource(code);
      send({ kind: 'tool_result', ok: c.ok });
      let final = { code, ok: c.ok || !!c.unknown };
      if (!c.ok && !c.unknown && !halted()) {
        send({ kind: 'note', text: `The checker found a mistake, so ${m.name} is fixing it.` });
        send({ kind: 'break' });
        stage('Fixing it');
        r = await ask(runId, 'followup', { prompt: `That program doesn't pass Tuff's checker:\n${c.message}\n\nFix it and give the whole program again.`, budget: lv.retryBudget ?? lv.budget, ...sampling(lv) }, relay());
        stats.answers.push(r.text || '');
        const again = codeOf(r.text || '');
        if (r.ok && again && !halted()) {
          stage('Checking the code');
          send({ kind: 'tool', name: 'mcp__tuffcode__tuff_check', input: { code: again } });
          const c2 = await checkSource(again);
          send({ kind: 'tool_result', ok: c2.ok });
          if (!c2.ok && !c2.unknown) send({ kind: 'note', text: `The checker still finds a mistake: ${c2.message}` });
          final = { code: again, ok: c2.ok || !!c2.unknown };
        }
      }
      // The program it ended with, and whether it passed the checker (the panel's Edit puts it into the file).
      if (!halted()) send({ kind: 'code', ...final });
    }
  }
  const ok = !!r.ok || !!r.stopped || halted();
  finish({ ok, error: ok ? null : r.error });
}

function stop(runId) {
  if (!active.has(runId)) return;
  stoppedRuns.add(runId);
  // The worker stops the answer it's writing, or skips the question when it gets to it.
  if (worker && runs.has(runId)) worker.proc.postMessage({ type: 'stop', runId });
}

function quit() {
  cancelDownload();
  unload();
}

module.exports = { MODELS, LEVELS, DEFAULT_LEVEL, setup, status, fetchModel, cancelDownload, removeModel, run, stop, quit, codeOf, improve, buildMessage, systemPrompt };
