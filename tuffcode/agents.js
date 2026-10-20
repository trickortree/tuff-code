// Tuff Agents backend: finds the AI coding agents installed on this PC (Claude Code, Codex,
// Antigravity), runs them on the user's project, streams what they do back to the panel, and
// connects them to the TuffCode MCP server (mcp/tuff-mcp.js) so they know the Tuff language.
const { app, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execFile } = require('child_process');
const shellPath = require('./shellpath');

const MCP_NAME = 'tuffcode';
const AGENTS = {
  claude: { name: 'Claude Code', bin: 'claude', install: 'npm install -g @anthropic-ai/claude-code', url: 'https://code.claude.com/docs' },
  codex: { name: 'Codex', bin: 'codex', install: 'npm install -g @openai/codex', url: 'https://developers.openai.com/codex' },
  antigravity: { name: 'Antigravity', bin: 'agy', install: 'Install Antigravity from antigravity.google, then run: agy install', url: 'https://antigravity.google' },
  // Tuff AI runs a model on this computer (ai.js). "Installed" means its model is downloaded.
  tuffai: { name: 'Tuff AI', local: true },
};
const ai = require('./ai');

const runs = new Map();
let tuffCommand = () => ['py', '-3', '-u', path.join(__dirname, '..', 'tuff.py')];

function setup(opts) {
  if (opts.tuffCommand) tuffCommand = opts.tuffCommand;
}

// ---------------------------------------------------------------- finding and starting agents
function which(bin) {
  return new Promise((resolve) => {
    const finder = process.platform === 'win32' ? 'where' : 'which';
    execFile(finder, [bin], { windowsHide: true }, (err, out) => {
      if (err) return resolve(null);
      const found = out.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      resolve(found.find((p) => /\.exe$/i.test(p)) || found.find((p) => /\.(cmd|bat)$/i.test(p)) || found[0] || null);
    });
  });
}

async function resolveBin(id) {
  const override = process.env[`TUFFCODE_${id.toUpperCase()}_BIN`];
  if (override) return override;
  await shellPath.ready(); // on a Mac, wait for the login shell's PATH
  const found = await which(AGENTS[id].bin);
  if (found) return found;
  if (id === 'claude') return findClaudeElsewhere();
  if (id === 'codex') return findCodexElsewhere();
  return null;
}

// Codex that isn't on PATH: the copy the Codex desktop app keeps for itself
// (AppData/Local/OpenAI/Codex/bin/<build>/codex.exe). It shares the app's sign-in.
function findCodexElsewhere() {
  if (process.platform === 'darwin') {
    // The Mac Codex app keeps its CLI inside the app bundle.
    const apps = ['/Applications', path.join(os.homedir(), 'Applications')];
    return apps.map((d) => path.join(d, 'Codex.app', 'Contents', 'Resources', 'codex')).find((f) => fs.existsSync(f)) || null;
  }
  const exe = process.platform === 'win32' ? 'codex.exe' : 'codex';
  const root = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'OpenAI', 'Codex', 'bin');
  let newest = null;
  let builds = [];
  try { builds = fs.readdirSync(root); } catch { return null; }
  for (const b of builds) {
    const file = path.join(root, b, exe);
    try {
      const t = fs.statSync(file).mtimeMs;
      if (!newest || t > newest.t) newest = { file, t };
    } catch {}
  }
  return newest ? newest.file : null;
}

// Claude Code that isn't on PATH: the standard installer's folder, or the copy the Claude desktop
// app keeps for its Code tab (AppData/Roaming/Claude/claude-code/<version>/<build>/claude.exe).
function findClaudeElsewhere() {
  const exe = process.platform === 'win32' ? 'claude.exe' : 'claude';
  const home = path.join(os.homedir(), '.local', 'bin', exe);
  if (fs.existsSync(home)) return home;
  // appData is AppData/Roaming on Windows and ~/Library/Application Support on a Mac. The Microsoft
  // Store version of the Claude app keeps its files in its package folder instead.
  const roots = [path.join(app.getPath('appData'), 'Claude', 'claude-code')];
  const pkgs = path.join(process.env.LOCALAPPDATA || '', 'Packages');
  if (process.platform === 'win32') {
    try { for (const p of fs.readdirSync(pkgs)) if (/claude/i.test(p)) roots.push(path.join(pkgs, p, 'LocalCache', 'Roaming', 'Claude', 'claude-code')); } catch {}
  }
  const num = (v) => v.split(/[.-]/).slice(0, 3).map((n) => parseInt(n, 10) || 0);
  // On a Mac the binary sits inside an app bundle (…/<build>/claude.app/Contents/MacOS/claude).
  const inner = process.platform === 'darwin' ? [path.join('claude.app', 'Contents', 'MacOS', 'claude'), exe] : [exe];
  const isFile = (f) => { try { return fs.statSync(f).isFile(); } catch { return false; } };
  for (const root of roots) {
    let versions = [];
    try { versions = fs.readdirSync(root).filter((v) => /^\d+\.\d+\.\d+/.test(v)); } catch { continue; }
    versions.sort((a, b) => { const x = num(a), y = num(b); return (y[0] - x[0]) || (y[1] - x[1]) || (y[2] - x[2]); });
    for (const v of versions) {
      let builds = [];
      try { builds = fs.readdirSync(path.join(root, v)); } catch { continue; }
      // Each build folder, then the version folder itself (older installs).
      for (const dir of [...builds.map((b) => path.join(root, v, b)), path.join(root, v)]) {
        for (const rel of inner) if (isFile(path.join(dir, rel))) return path.join(dir, rel);
      }
    }
  }
  return null;
}

// npm installs agents as .cmd shims, which Windows can only start through cmd.exe. Our arguments
// are fixed flags and quoted paths; free text (the prompt) always goes through stdin instead.
const cmdQuote = (a) => (/^[\w\-.:=/\\@]+$/.test(a) ? a : `"${String(a).replace(/"/g, '""')}"`);
function startCli(file, args, opts) {
  if (/\.(cmd|bat)$/i.test(file)) {
    if (args.some((a) => /[\r\n%!^]/.test(a))) throw new Error('Unsafe argument for a .cmd agent');
    return spawn(`"${file}"`, args.map(cmdQuote), { ...opts, shell: true, windowsHide: true });
  }
  // On a Mac or Linux the agent gets its own process group, so Stop can end everything it started.
  return spawn(file, args, { ...opts, windowsHide: true, detached: process.platform !== 'win32' });
}

function quick(file, args, timeout = 15000) {
  return new Promise((resolve) => {
    let out = '';
    let proc;
    try { proc = startCli(file, args, { stdio: ['ignore', 'pipe', 'pipe'] }); } catch (err) { resolve({ code: -1, out: err.message }); return; }
    const t = setTimeout(() => killTree(proc), timeout);
    proc.stdout.on('data', (d) => { out += d; });
    proc.stderr.on('data', (d) => { out += d; });
    proc.on('error', (err) => { clearTimeout(t); resolve({ code: -1, out: err.message }); });
    proc.on('close', (code) => { clearTimeout(t); resolve({ code, out: out.trim() }); });
  });
}

function killTree(proc) {
  if (!proc || proc.exitCode !== null) return;
  if (process.platform === 'win32') execFile('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { windowsHide: true }, () => {});
  else { try { process.kill(-proc.pid, 'SIGTERM'); } catch { proc.kill('SIGTERM'); } }
}

async function detect() {
  return Promise.all(Object.entries(AGENTS).map(async ([id, a]) => {
    if (a.local) {
      const s = await ai.status();
      const m = s.models[0];
      return { id, name: a.name, local: true, installed: s.runtime && m.downloaded, runtime: s.runtime, path: null, version: m.downloaded ? m.name : null };
    }
    const file = await resolveBin(id);
    const info = { id, name: a.name, bin: a.bin, install: a.install, url: a.url, installed: !!file, path: file, version: null };
    if (file) {
      const r = await quick(file, ['--version'], 10000);
      info.version = (r.out.split(/\r?\n/)[0] || '').replace(/^[^\d]*/, '').trim() || null;
    }
    return info;
  }));
}

// ---------------------------------------------------------------- TuffCode MCP server
function mcpServerPath() {
  const p = path.join(__dirname, 'mcp', 'tuff-mcp.js');
  return app.isPackaged ? p.replace(`app.asar${path.sep}`, `app.asar.unpacked${path.sep}`) : p;
}

// Agents start the server with TuffCode's own executable in Node mode, so nothing else is needed.
function mcpServer() {
  return {
    command: process.execPath,
    args: [mcpServerPath()],
    env: { ELECTRON_RUN_AS_NODE: '1', TUFF_CMD: JSON.stringify(tuffCommand()) },
  };
}

const CONNECT = {
  claude: {
    // The name goes before -e: -e takes several values and would swallow it.
    add: () => ['mcp', 'add', '--scope', 'user', MCP_NAME, '-e', 'ELECTRON_RUN_AS_NODE=1', '--', mcpServer().command, mcpServer().args[0]],
    remove: () => ['mcp', 'remove', '--scope', 'user', MCP_NAME],
    check: async (file) => (await quick(file, ['mcp', 'get', MCP_NAME])).code === 0,
  },
  codex: {
    add: () => ['mcp', 'add', MCP_NAME, '--env', 'ELECTRON_RUN_AS_NODE=1', '--', mcpServer().command, mcpServer().args[0]],
    remove: () => ['mcp', 'remove', MCP_NAME],
    check: async (file) => (await quick(file, ['mcp', 'get', MCP_NAME])).code === 0,
  },
  antigravity: {
    add: () => ['mcp', 'add', '--env', 'ELECTRON_RUN_AS_NODE=1', MCP_NAME, mcpServer().command, mcpServer().args[0]],
    remove: () => ['mcp', 'remove', MCP_NAME],
    check: async (file) => new RegExp(`\\b${MCP_NAME}\\b`).test((await quick(file, ['mcp', 'list'])).out),
  },
};

// The Claude desktop app's chat reads its tool servers from claude_desktop_config.json (Claude Code
// and the app's Code tab use ~/.claude.json, which `claude mcp add --scope user` writes).
function claudeAppConfig() {
  if (process.env.TUFFCODE_CLAUDE_APP_CONFIG) return process.env.TUFFCODE_CLAUDE_APP_CONFIG;
  const dirs = [path.join(app.getPath('appData'), 'Claude')];
  const pkgs = path.join(process.env.LOCALAPPDATA || '', 'Packages');
  try { for (const p of fs.readdirSync(pkgs)) if (/claude/i.test(p)) dirs.push(path.join(pkgs, p, 'LocalCache', 'Roaming', 'Claude')); } catch {}
  const dir = dirs.find((d) => fs.existsSync(d));
  return dir ? path.join(dir, 'claude_desktop_config.json') : null;
}
function readClaudeApp(file) {
  if (!fs.existsSync(file)) return {};
  try { return JSON.parse(fs.readFileSync(file, 'utf8') || '{}'); } catch { return null; }
}
function claudeAppHas() {
  const file = claudeAppConfig();
  if (!file) return null; // no Claude app on this PC
  return !!readClaudeApp(file)?.mcpServers?.[MCP_NAME];
}
function setClaudeApp(on) {
  const file = claudeAppConfig();
  if (!file) return;
  const cfg = readClaudeApp(file);
  if (!cfg) throw new Error("Couldn't read the Claude app's settings file, so TuffCode left it alone.");
  if (fs.existsSync(file) && !fs.existsSync(`${file}.before-tuffcode`)) fs.copyFileSync(file, `${file}.before-tuffcode`);
  cfg.mcpServers = cfg.mcpServers || {};
  const s = mcpServer();
  if (on) cfg.mcpServers[MCP_NAME] = { command: s.command, args: s.args, env: { ELECTRON_RUN_AS_NODE: '1' } };
  else delete cfg.mcpServers[MCP_NAME];
  fs.writeFileSync(`${file}.tmp`, JSON.stringify(cfg, null, 2));
  fs.renameSync(`${file}.tmp`, file);
}

// Antigravity runs headless in the panel, where it can't ask before using a tool, so it turns
// down every tool that needs permission, TuffCode's included. Connecting it also allows TuffCode's
// own four tools in its settings (and nothing else); removing takes those rules out again.
const AGY_DIR = path.join(os.homedir(), '.gemini', 'antigravity-cli');
const AGY_ALLOW = ['tuff_reference', 'tuff_examples', 'tuff_check', 'tuff_run'].map((n) => `mcp(${MCP_NAME}/${n})`);
function setAgyAllow(on) {
  const file = path.join(AGY_DIR, 'settings.json');
  if (!fs.existsSync(AGY_DIR)) return;
  let cfg = {};
  if (fs.existsSync(file)) { try { cfg = JSON.parse(fs.readFileSync(file, 'utf8') || '{}'); } catch { return; } }
  const had = cfg.permissions?.allow || [];
  const allow = on ? [...new Set([...had, ...AGY_ALLOW])] : had.filter((r) => !AGY_ALLOW.includes(r));
  if (allow.length === had.length && allow.every((r, i) => r === had[i])) return;
  cfg.permissions = { ...(cfg.permissions || {}), allow };
  fs.writeFileSync(`${file}.tmp`, JSON.stringify(cfg, null, 2));
  fs.renameSync(`${file}.tmp`, file);
}
// Antigravity keeps a folder per connected tool server, so this needs no slow `agy mcp list`.
const agyHasTuffTools = () => fs.existsSync(path.join(AGY_DIR, 'mcp', MCP_NAME));

async function connection(id) {
  if (!CONNECT[id]) return { id, installed: true, connected: null };
  const file = await resolveBin(id);
  if (!file) return { id, installed: false, connected: false };
  let connected = await CONNECT[id].check(file);
  if (id === 'claude' && claudeAppHas() === false) connected = false;
  return { id, installed: true, connected };
}

async function connect(id, on = true) {
  const file = await resolveBin(id);
  if (!file) throw new Error(`${AGENTS[id].name} isn't installed.`);
  const r = await quick(file, on ? CONNECT[id].add() : CONNECT[id].remove(), 30000);
  if (id === 'claude') setClaudeApp(on);
  if (id === 'antigravity') { try { setAgyAllow(on); } catch {} }
  const state = await connection(id);
  if (state.connected !== on) throw new Error(r.out || `Couldn't ${on ? 'connect' : 'disconnect'} ${AGENTS[id].name}.`);
  return state;
}

// ---------------------------------------------------------------- models and thinking levels
// Each agent is asked which models it offers and how hard each can think. The list is the
// agent's own (for this account and version), so nothing here goes out of date. id '' = the
// agent's own default.
const LEVEL_NAMES = { minimal: 'Minimal', low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high', max: 'Max', ultra: 'Ultra' };
const levels = (list) => list.map((id) => ({ id, name: LEVEL_NAMES[id] || id[0].toUpperCase() + id.slice(1) }));
const safeArg = (s) => typeof s === 'string' && /^[\w.\-:/]{1,80}$/.test(s);
const modelCache = {};

// "claude-opus-5-5" -> "Opus 5.5"
// Also reads IDs with a context tag ("claude-opus-5-5[1m]") or a cloud prefix/suffix
// ("us.anthropic.claude-opus-5-5-v1:0"); the tag is left out so a model has one name.
function claudeModelName(id) {
  const m = /claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?!\d)/.exec(String(id || '').replace(/(\[[^\]]*\])+$/, ''));
  return m ? `${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]}${m[3] ? `.${m[3]}` : ''}` : null;
}

// The newest model ID Claude Code knows for each family (opus -> claude-opus-5-5), read from Claude
// Code itself. Its aliases always point at the newest of their family, so this names what "opus"
// really is. npm installs are a .cmd/shell shim, so the script it starts is read instead.
const claudeIdCache = new Map();
async function claudeModelIds(file) {
  let target = file;
  try {
    if (/\.(cmd|bat)$/i.test(file) || fs.statSync(file).size < 4096) {
      const shim = fs.readFileSync(file, 'utf8').replace(/%~?dp0%?\\?/gi, `${path.dirname(file)}${path.sep}`).replace(/\$basedir\//g, `${path.dirname(file)}/`);
      const js = /"?([^"\r\n]+?\.(?:js|cjs|mjs|exe))"?(?:\s|$)/i.exec(shim);
      if (js && fs.existsSync(path.resolve(path.dirname(file), js[1]))) target = path.resolve(path.dirname(file), js[1]);
    }
  } catch {}
  let stat;
  try { stat = fs.statSync(target); } catch { return {}; }
  const key = `${target}|${stat.size}|${stat.mtimeMs}`;
  if (claudeIdCache.has(key)) return claudeIdCache.get(key);
  const best = {};
  const rank = (m) => Number(m[2]) * 100 + Number(m[3] || 0);
  await new Promise((resolve) => {
    let tail = '';
    const re = /claude-(opus|sonnet|haiku|fable)-(\d+)(?:-(\d{1,2}))?(?!\d)/g;
    fs.createReadStream(target, { encoding: 'latin1', highWaterMark: 4 << 20 })
      .on('data', (chunk) => {
        const text = tail + chunk;
        let m;
        while ((m = re.exec(text))) if (!best[m[1]] || rank(m) > best[m[1]].rank) best[m[1]] = { id: m[0], rank: rank(m) };
        tail = text.slice(-40);
      })
      .on('error', resolve)
      .on('close', resolve);
  });
  const ids = Object.fromEntries(Object.entries(best).map(([family, v]) => [family, v.id]));
  claudeIdCache.set(key, ids);
  return ids;
}

const CLAUDE_FAMILIES = {
  fable: "Anthropic's most capable, for the hardest work",
  opus: 'Great for complex coding',
  sonnet: 'Fast and smart',
  haiku: 'Quickest, for small jobs',
};

const MODELS = {
  // Claude Code has no list command; its help names the model aliases and effort levels, and the
  // model IDs inside Claude Code give each alias its real name.
  claude: async (file) => {
    const help = (await quick(file, ['--help'], 15000)).out.replace(/\s+/g, ' ');
    const aliases = [...((/--model <model>.*?\(e\.g\.([^)]*)\)/.exec(help) || [])[1] || '').matchAll(/'([\w.-]+)'/g)].map((m) => m[1]);
    const efforts = (((/--effort <level>[^(]*\(([^)]*)\)/.exec(help) || [])[1] || '').match(/[a-z]+/g)) || [];
    if (!aliases.length) throw new Error("Claude Code didn't list its models.");
    const ids = await claudeModelIds(file).catch(() => ({}));
    // Haiku isn't in the help's examples, but Claude Code takes it when it knows a current Haiku.
    if (ids.haiku && !aliases.includes('haiku') && ids.opus && ids.haiku.split('-')[2] === ids.opus.split('-')[2]) aliases.push('haiku');
    const order = Object.keys(CLAUDE_FAMILIES);
    aliases.sort((a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99));
    return {
      models: aliases.map((id) => ({
        id,
        name: claudeModelName(ids[id]) || id[0].toUpperCase() + id.slice(1),
        sub: CLAUDE_FAMILIES[id] || '',
        efforts: levels(efforts),
      })),
      efforts: levels(efforts),
    };
  },
  // Codex prints its model catalog; "list" models are the ones its own picker shows.
  codex: async (file) => {
    const r = await quick(file, ['debug', 'models'], 30000);
    const json = JSON.parse(r.out.slice(r.out.indexOf('{')));
    const models = (json.models || []).filter((m) => m.slug && m.visibility !== 'hide').map((m) => ({
      id: m.slug,
      name: m.display_name || m.slug,
      sub: String(m.description || '').split(/(?<=\.)\s/)[0].slice(0, 80),
      efforts: levels((m.supported_reasoning_levels || []).map((l) => l.effort || l).filter((e) => typeof e === 'string')),
      defaultEffort: m.default_reasoning_level || null,
    }));
    if (!models.length) throw new Error("Codex didn't list any models.");
    return { models, efforts: [] };
  },
  // Antigravity lists one entry per model and thinking level ("gemini-4-argon-high  Gemini 4 Argon (High)").
  antigravity: async (file) => {
    const out = (await quick(file, ['models'], 45000)).out;
    const byBase = new Map();
    for (const line of out.split(/\r?\n/)) {
      const m = /^(\S+)\s+(.+)$/.exec(line.trim());
      if (!m || /^fetching/i.test(line)) continue;
      const [, id, label] = m;
      const lv = /-(minimal|low|medium|high|xhigh|max)$/.exec(id);
      const base = lv ? id.slice(0, -lv[0].length) : id;
      const name = label.replace(/\s*\((minimal|low|medium|high|extra high|xhigh|max)\)\s*$/i, '').trim();
      const maker = /^gemini/i.test(name) ? 'Google' : /^claude/i.test(name) ? 'Anthropic' : /^gpt/i.test(name) ? 'OpenAI' : '';
      if (!byBase.has(base)) byBase.set(base, { id: base, name, sub: maker, efforts: [], ids: {} });
      const e = byBase.get(base);
      if (lv) { e.efforts.push(...levels([lv[1]])); e.ids[lv[1]] = id; } else e.ids[''] = id;
    }
    const order = Object.keys(LEVEL_NAMES);
    const models = [...byBase.values()];
    for (const m of models) m.efforts.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
    if (!models.length) throw new Error("Antigravity didn't list any models. Is it signed in?");
    return { models, efforts: [] };
  },
};

async function models(id, fresh = false) {
  if (id === 'tuffai') return { models: ai.MODELS.map((m) => ({ id: m.id, name: m.name, sub: m.sub, efforts: [] })), efforts: [] };
  if (!MODELS[id]) return { models: [], efforts: [] };
  if (modelCache[id] && !fresh) return modelCache[id];
  const file = await resolveBin(id);
  if (!file) return { models: [], efforts: [] };
  const list = await MODELS[id](file);
  modelCache[id] = list;
  return list;
}

// The flags that pick the model and thinking level for one run. Unknown values are dropped.
function modelArgs(agent, model, effort) {
  const m = safeArg(model) ? model : '';
  const e = safeArg(effort) ? effort : '';
  if (agent === 'claude') return [...(m ? ['--model', m] : []), ...(e ? ['--effort', e] : [])];
  if (agent === 'codex') return [...(m ? ['-m', m] : []), ...(e ? ['-c', `model_reasoning_effort=${e}`] : [])];
  if (agent === 'antigravity') {
    const entry = modelCache.antigravity?.models.find((x) => x.id === m);
    const full = entry ? entry.ids[e] || entry.ids[''] || Object.values(entry.ids)[0] : m;
    if (full) return ['--model', full];
    return e ? ['--effort', e] : [];
  }
  return [];
}

// How each agent reports and starts its own sign-in. Antigravity can't say without a prompt.
const SIGN_IN = {
  claude: {
    status: ['auth', 'status'],
    read: (r) => { try { return !!JSON.parse(r.out).loggedIn; } catch { return null; } },
    login: ['auth', 'login'],
  },
  codex: {
    status: ['login', 'status'],
    read: (r) => (/not logged in/i.test(r.out) ? false : r.code === 0 && /logged in/i.test(r.out) ? true : null),
    login: ['login'],
  },
};

// Is the agent signed in? null: can't tell.
async function signedIn(id) {
  if (!SIGN_IN[id]) return null;
  const file = await resolveBin(id);
  if (!file) return null;
  return SIGN_IN[id].read(await quick(file, SIGN_IN[id].status, 15000));
}

// Opens a window running the agent's own sign-in, so the person signs in themselves in the browser.
async function signIn(id) {
  const file = await resolveBin(id);
  if (!file) throw new Error(`${AGENTS[id].name} isn't installed.`);
  if (!SIGN_IN[id]) throw new Error(`Sign in to ${AGENTS[id].name} in a terminal.`);
  const name = AGENTS[id].name;
  if (process.platform === 'win32') {
    // The sign-in needs a real console window: it opens the browser from there and shows the link
    // if that fails. A small script opened like a double-click gets one (a hidden child doesn't).
    const script = path.join(os.tmpdir(), `tuffcode-signin-${id}.cmd`);
    fs.writeFileSync(script, [
      '@echo off',
      `title Sign in to ${name}`,
      `echo Signing in to ${name}. Your browser should open; finish signing in there.`,
      'echo If it doesn\'t open, copy the link below into your browser.',
      'echo.',
      `call "${file}" ${SIGN_IN[id].login.join(' ')}`,
      'echo.',
      'echo When it says you\'re signed in, close this window and click Check again in TuffCode.',
      'pause',
      '',
    ].join('\r\n'));
    const err = await shell.openPath(script);
    if (err) throw new Error(`Couldn't open the sign-in window: ${err}`);
    return true;
  }
  // Mac: a .command file opens in Terminal, which gives the sign-in a real window too.
  const script = path.join(os.tmpdir(), `tuffcode-signin-${id}.command`);
  const q = (s) => `'${String(s).replace(/'/g, `'\\''`)}'`;
  fs.writeFileSync(script, [
    '#!/bin/bash',
    `echo ${q(`Signing in to ${name}. Your browser should open; finish signing in there.`)}`,
    `echo ${q("If it doesn't open, copy the link below into your browser.")}`,
    'echo',
    `${q(file)} ${SIGN_IN[id].login.join(' ')}`,
    'echo',
    `echo ${q("When it says you're signed in, close this window and click Check again in TuffCode.")}`,
    '',
  ].join('\n'), { mode: 0o755 });
  fs.chmodSync(script, 0o755);
  const err = await shell.openPath(script);
  if (err) throw new Error(`Couldn't open the sign-in window: ${err}`);
  return true;
}

// What to type to set the tools up by hand: the same commands the Connect buttons run, plus the
// JSON other MCP apps (Claude Desktop, Cursor...) want.
function mcpSetup() {
  const s = mcpServer();
  const show = (bin, args) => [bin, ...args].map((a) => (/^[\w\-.:=/\\@]+$/.test(a) ? a : `"${a}"`)).join(' ');
  const agents = {};
  for (const id of Object.keys(CONNECT)) {
    agents[id] = {
      add: show(AGENTS[id].bin, CONNECT[id].add()),
      check: show(AGENTS[id].bin, id === 'antigravity' ? ['mcp', 'list'] : ['mcp', 'get', MCP_NAME]),
      remove: show(AGENTS[id].bin, CONNECT[id].remove()),
    };
  }
  const json = JSON.stringify({ mcpServers: { [MCP_NAME]: { command: s.command, args: s.args, env: { ELECTRON_RUN_AS_NODE: '1' } } } }, null, 2);
  return { command: s.command, args: s.args, agents, json };
}

// Starts the TuffCode MCP server the way connected agents do (only ELECTRON_RUN_AS_NODE, so it has
// to find the Tuff interpreter by itself) and uses every tool once, like an agent would.
// Resolves to { ok, steps: [{ id, ok, detail, ms }] }.
function mcpCheck() {
  const s = mcpServer();
  const env = { ...process.env, ELECTRON_RUN_AS_NODE: '1' };
  delete env.TUFF_CMD;
  const steps = [];
  return new Promise((resolve) => {
    let proc;
    try {
      proc = spawn(s.command, s.args, { env, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    } catch (err) {
      resolve({ ok: false, steps: [{ id: 'start', ok: false, detail: err.message, ms: 0 }] });
      return;
    }
    const waiting = new Map();
    let nextId = 0;
    let buf = '';
    let errText = '';
    proc.stdout.setEncoding('utf8');
    proc.stdout.on('data', (d) => {
      buf += d;
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        let msg;
        try { msg = JSON.parse(line); } catch { continue; }
        waiting.get(msg.id)?.resolve(msg);
      }
    });
    proc.stderr.on('data', (d) => { errText = (errText + d).slice(-1500); });
    const failAll = (why) => { for (const w of [...waiting.values()]) w.reject(new Error(why)); };
    proc.on('error', (err) => failAll(`The tools couldn't start: ${err.message}`));
    proc.on('close', (code) => failAll(`The tools stopped (exit code ${code}).${errText.trim() ? `\n${errText.trim()}` : ''}`));

    const call = (method, params, ms) => new Promise((res, rej) => {
      const id = ++nextId;
      const timer = setTimeout(() => { waiting.delete(id); rej(new Error(`No answer after ${ms / 1000} seconds.`)); }, ms);
      waiting.set(id, {
        resolve: (m) => { clearTimeout(timer); waiting.delete(id); res(m); },
        reject: (e) => { clearTimeout(timer); waiting.delete(id); rej(e); },
      });
      proc.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
    });
    const tool = async (name, args, ms = 15000) => {
      const m = await call('tools/call', { name, arguments: args }, ms);
      if (m.error) throw new Error(m.error.message);
      return { text: (m.result?.content || []).map((c) => c.text).join('\n'), bad: !!m.result?.isError };
    };
    const step = async (id, fn) => {
      const t0 = Date.now();
      try {
        steps.push({ id, ok: true, detail: await fn(), ms: Date.now() - t0 });
        return true;
      } catch (err) {
        steps.push({ id, ok: false, detail: err.message, ms: Date.now() - t0 });
        return false;
      }
    };

    (async () => {
      const started = await step('start', async () => {
        const m = await call('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'tuffcode-check', version: app.getVersion() } }, 20000);
        const info = m.result?.serverInfo;
        if (info?.name !== MCP_NAME) throw new Error(m.error?.message || "The tools didn't say who they are.");
        proc.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);
        return `TuffCode tools ${info.version}`;
      });
      if (started) {
        await step('tools', async () => {
          const names = ((await call('tools/list', {}, 10000)).result?.tools || []).map((x) => x.name);
          const missing = ['tuff_reference', 'tuff_examples', 'tuff_check', 'tuff_run'].filter((n) => !names.includes(n));
          if (missing.length) throw new Error(`Missing: ${missing.join(', ')}`);
          return names.join(', ');
        });
        await step('guide', async () => {
          const r = await tool('tuff_reference', {});
          if (r.bad || r.text.length < 2000) throw new Error(r.text.slice(0, 300) || 'The guide came back empty.');
          return `${r.text.length.toLocaleString('en-US')} characters, ${(r.text.match(/^## /gm) || []).length} sections`;
        });
        await step('examples', async () => {
          const r = await tool('tuff_examples', {});
          const n = (r.text.match(/^## /gm) || []).length;
          if (r.bad || !n) throw new Error(r.text.slice(0, 300) || 'No examples came back.');
          return `${n} example apps`;
        });
        await step('check', async () => {
          const good = await tool('tuff_check', { code: 'say "Hello"\n' }, 30000);
          if (good.bad || !/^OK\b/.test(good.text.trim())) throw new Error(`Correct code wasn't OK: ${good.text.slice(0, 300)}`);
          const bad = await tool('tuff_check', { code: 'say "Hello" +\n' }, 30000);
          if (!bad.bad || !/line 1/i.test(bad.text)) throw new Error(`It missed a mistake on purpose: ${bad.text.slice(0, 300)}`);
          return bad.text.split('\n')[0];
        });
        await step('run', async () => {
          const r = await tool('tuff_run', { code: 'name = input "Name? "\nsay "Hi " + name + "!"\n', input: 'Sam', timeout_seconds: 20 }, 40000);
          if (r.bad || !/Hi Sam!/.test(r.text)) throw new Error(r.text.slice(0, 400) || 'It printed nothing.');
          return 'It asked for a name and printed "Hi Sam!"';
        });
      }
      killTree(proc);
      resolve({ ok: steps.length === 6 && steps.every((x) => x.ok), steps });
    })();
  });
}

// ---------------------------------------------------------------- running a prompt
function claudeMcpConfigFile() {
  const file = path.join(os.tmpdir(), `tuffcode-mcp-${process.pid}.json`);
  fs.writeFileSync(file, JSON.stringify({ mcpServers: { [MCP_NAME]: mcpServer() } }, null, 2));
  return file;
}

// Antigravity takes the prompt as the value of --print, on the command line. Windows allows about
// 32,000 characters there, so a longer prompt loses the middle (the file) and keeps the request at the end.
function fitCommandLine(prompt, limit = 30000) {
  if (prompt.length <= limit) return prompt;
  const note = '\n\n… (part of this was cut to fit) …\n\n';
  const head = 6000;
  return prompt.slice(0, head) + note + prompt.slice(-(limit - head - note.length));
}

function argsFor(agent, { mode, session, prompt, model, effort }) {
  const edit = mode === 'edit';
  const pick = modelArgs(agent, model, effort);
  if (agent === 'claude') {
    const args = ['-p', '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
      '--mcp-config', claudeMcpConfigFile(), '--allowedTools', `mcp__${MCP_NAME}`, '--permission-mode', edit ? 'acceptEdits' : 'default', ...pick];
    if (session) args.push('--resume', session);
    return { args, stdin: true };
  }
  if (agent === 'codex') return { args: ['exec', '--json', '--skip-git-repo-check', '--sandbox', edit ? 'workspace-write' : 'read-only', ...pick, '-'], stdin: true };
  const args = [`--print=${fitCommandLine(prompt)}`, '--output-format', 'stream-json', '--mode', edit ? 'accept-edits' : 'plan', ...pick];
  if (session) args.push('--conversation', session);
  return { args, stdin: false };
}

// Each parser turns one JSON line from an agent into panel events:
// session, delta (streamed text), text (a whole message), tool, tool_result, done, error.
function claudeParser() {
  let streamed = false;
  let anyText = false;
  return (o, emit) => {
    if (o.type === 'system' && o.subtype === 'init') {
      emit({ kind: 'session', id: o.session_id });
      if (o.model) emit({ kind: 'model', id: o.model, name: claudeModelName(o.model) || o.model });
      const mcp = (o.mcp_servers || []).find((s) => s.name === MCP_NAME);
      if (mcp && mcp.status !== 'connected') emit({ kind: 'note', text: `TuffCode tools didn't start (${mcp.status}).` });
    } else if (o.type === 'stream_event' && o.event?.type === 'content_block_delta' && o.event.delta?.type === 'text_delta') {
      streamed = anyText = true;
      emit({ kind: 'delta', text: o.event.delta.text });
    } else if (o.type === 'stream_event' && o.event?.type === 'content_block_stop') {
      emit({ kind: 'break' });
    } else if (o.type === 'assistant') {
      for (const b of o.message?.content || []) {
        if (b.type === 'tool_use') emit({ kind: 'tool', name: b.name, input: b.input });
        else if (b.type === 'text' && !streamed && b.text) { anyText = true; emit({ kind: 'text', text: b.text }); }
      }
    } else if (o.type === 'user') {
      for (const b of o.message?.content || []) if (b.type === 'tool_result') emit({ kind: 'tool_result', ok: !b.is_error });
    } else if (o.type === 'result') {
      if (!anyText && o.result) emit({ kind: 'text', text: o.result });
      emit({ kind: 'done', ok: !o.is_error && o.subtype === 'success', error: o.is_error ? o.result || o.subtype : null, session: o.session_id, cost: o.total_cost_usd });
    }
  };
}

function codexParser() {
  return (o, emit) => {
    const it = o.item || {};
    if (o.type === 'thread.started') emit({ kind: 'session', id: o.thread_id });
    else if (o.type === 'item.started' && it.type === 'command_execution') emit({ kind: 'tool', name: 'Bash', input: { command: it.command } });
    else if (o.type === 'item.started' && it.type === 'mcp_tool_call') emit({ kind: 'tool', name: `mcp__${it.server}__${it.tool}`, input: it.arguments || {} });
    else if (o.type === 'item.completed') {
      if (it.type === 'agent_message' && it.text) emit({ kind: 'text', text: it.text });
      else if (it.type === 'file_change') {
        // One step per file, each with its own result, so every changed file is named.
        for (const c of it.changes || []) {
          emit({ kind: 'tool', name: 'Edit', input: { file_path: c.path } });
          emit({ kind: 'tool_result', ok: it.status !== 'failed' });
        }
      }
      else if (it.type === 'command_execution') emit({ kind: 'tool_result', ok: it.exit_code === 0 || it.status === 'completed' });
      else if (it.type === 'mcp_tool_call') emit({ kind: 'tool_result', ok: it.status !== 'failed' });
      else if (it.type === 'error') emit({ kind: 'error', text: it.message });
    } else if (o.type === 'turn.completed') emit({ kind: 'done', ok: true });
    else if (o.type === 'turn.failed') emit({ kind: 'done', ok: false, error: o.error?.message || 'The turn failed.' });
    else if (o.type === 'error') emit({ kind: 'error', text: o.message });
  };
}

// Antigravity (agy --output-format stream-json) sends {event: 'init' | 'step_update' | 'result'}.
// Each step is the agent talking (text_delta pieces) or one tool call (ACTIVE, then DONE).
const AGY_TOOLS = {
  write_file: 'Write', write_to_file: 'Write',
  replace_file_content: 'Edit', multi_replace_file_content: 'Edit', sed_file: 'Edit', notebook_edit: 'Edit',
  read_file: 'Read', view_file: 'Read',
  run_command: 'Bash',
  list_dir: 'Glob', find_by_name: 'Glob', grep_search: 'Grep',
  search_web: 'WebSearch', read_url_content: 'WebFetch',
};
function agyTool(name, p = {}) {
  const file = p.Path || p.AbsolutePath || p.TargetFile || p.FilePath || p.path || p.file_path;
  const tuff = /tuff_(reference|examples|check|run)/.exec(`${name} ${p.ToolName || p.tool_name || p.tool || ''}`);
  if (tuff) return { name: `mcp__${MCP_NAME}__${tuff[0]}`, input: p.Arguments || p.arguments || {} };
  if (AGY_TOOLS[name]) return { name: AGY_TOOLS[name], input: { file_path: file, command: p.CommandLine || p.Command || p.command } };
  return { name, input: { file_path: file } };
}
function antigravityParser() {
  const claude = claudeParser();
  let shown = false;
  let talking = false;
  const started = new Set();
  const hidden = new Set(); // agy reading its own description of a tool before calling it
  return (o, emit) => {
    if (o.event === 'init') { if (o.conversation_id) emit({ kind: 'session', id: o.conversation_id }); return; }
    if (o.event === 'step_update') {
      const s = o.step_update || {};
      if (s.step_type === 'agent_response' && typeof s.text_delta === 'string' && s.text_delta) {
        shown = talking = true;
        emit({ kind: 'delta', text: s.text_delta });
      } else if (s.step_type === 'tool') {
        if (talking) { talking = false; emit({ kind: 'break' }); }
        const key = s.step_index;
        const p = s.tool_info?.parameters || {};
        if (hidden.has(key) || /[\\/]antigravity-cli[\\/]mcp[\\/][^\\/]+[\\/][^\\/]+\.json$/i.test(p.Path || p.AbsolutePath || '')) { hidden.add(key); return; }
        if (!started.has(key)) { started.add(key); const t = agyTool(s.tool_name || s.tool_info?.name, s.tool_info?.parameters); emit({ kind: 'tool', name: t.name, input: t.input }); }
        if (/^(DONE|ERROR|FAILED|CANCELED|CANCELLED)$/i.test(s.state || '')) emit({ kind: 'tool_result', ok: /^DONE$/i.test(s.state) && !s.tool_info?.error });
      }
      return;
    }
    if (o.event === 'result') {
      const r = o.result || {};
      const ok = /^success$/i.test(r.status || '');
      if (!shown && r.response) emit({ kind: 'text', text: r.response });
      const denied = [...new Set((r.denied_actions || []).map((d) => (d.action === 'command' ? 'run a command' : `use ${d.display_name || d.action}`)))];
      if (denied.length) emit({ kind: 'note', text: `Antigravity wanted to ${denied.join(' and ')}, but it can't ask for permission from this panel, so that was skipped.` });
      emit({ kind: 'done', ok, error: ok ? null : (r.error?.message || r.error || r.message || `Antigravity stopped (${r.status || 'no result'}).`), session: r.conversation_id });
      return;
    }
    if (o.event === 'error') { emit({ kind: 'error', text: o.error?.message || o.error || o.message || 'Antigravity reported an error.' }); return; }
    // Older builds mirrored Claude Code's stream; anything else with text in it is shown as text.
    const known = ['system', 'stream_event', 'assistant', 'user', 'result'].includes(o.type);
    if (known) {
      claude(o, (e) => { if (['delta', 'text'].includes(e.kind)) shown = true; emit(e); });
      return;
    }
    const text = typeof o.text === 'string' ? o.text : typeof o.delta?.text === 'string' ? o.delta.text : typeof o.content === 'string' ? o.content : null;
    if (text && /delta|chunk|token/i.test(o.type || '')) { shown = true; emit({ kind: 'delta', text }); } else if (text) { shown = true; emit({ kind: 'text', text }); }
    if (/done|complete|finish|end/i.test(o.type || '') && !text && !shown && typeof o.result === 'string') emit({ kind: 'text', text: o.result });
  };
}

const PARSERS = { claude: claudeParser, codex: codexParser, antigravity: antigravityParser };

async function run({ runId, agent, prompt, root, mode, session, model, effort }, emit) {
  if (AGENTS[agent]?.local) return ai.run({ runId, prompt, model }, emit);
  const send = (e) => emit({ runId, ...e });
  const file = await resolveBin(agent);
  if (!file) { send({ kind: 'done', ok: false, error: `${AGENTS[agent].name} isn't installed. ${AGENTS[agent].install}` }); return; }
  if (agent === 'antigravity') {
    if (model && !modelCache.antigravity) await models('antigravity').catch(() => {});
    if (agyHasTuffTools()) { try { setAgyAllow(true); } catch {} }
  }
  const { args, stdin } = argsFor(agent, { mode, session, prompt, model, effort });
  let proc;
  try {
    proc = startCli(file, args, { cwd: root, env: { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1' }, stdio: ['pipe', 'pipe', 'pipe'] });
  } catch (err) {
    send({ kind: 'done', ok: false, error: err.message });
    return;
  }
  runs.set(runId, proc);
  const parse = PARSERS[agent]();
  let finished = false;
  let errText = '';
  let buf = '';
  const onEvent = (e) => { if (e.kind === 'done') finished = true; send(e); };
  proc.stdout.setEncoding('utf8');
  proc.stdout.on('data', (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let o;
      try { o = JSON.parse(line); } catch { send({ kind: 'delta', text: line + '\n' }); continue; }
      try { parse(o, onEvent); } catch {}
    }
  });
  proc.stderr.on('data', (d) => { errText = (errText + d).slice(-4000); });
  proc.on('error', (err) => { if (!finished) { finished = true; send({ kind: 'done', ok: false, error: err.message }); } });
  proc.on('close', (code) => {
    runs.delete(runId);
    if (buf.trim()) { try { parse(JSON.parse(buf), onEvent); } catch { send({ kind: 'delta', text: buf }); } }
    if (!finished) send({ kind: 'done', ok: code === 0, error: code === 0 ? null : (errText.trim() || `${AGENTS[agent].name} stopped (exit code ${code}).`) });
  });
  if (stdin) proc.stdin.write(prompt);
  proc.stdin.end();
}

function stop(runId) {
  ai.stop(runId);
  const proc = runs.get(runId);
  if (proc) killTree(proc);
  runs.delete(runId);
}

module.exports = { AGENTS, setup, detect, run, stop, connection, connect, mcpServer, mcpSetup, mcpCheck, signedIn, signIn, models };
