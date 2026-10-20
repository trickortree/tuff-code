// Tuff Agents backend: finds the AI coding agents installed on this PC (Claude Code, Codex,
// Antigravity), runs them on the user's project, streams what they do back to the panel, and
// connects them to the TuffCode MCP server (mcp/tuff-mcp.js) so they know the Tuff language.
const { app } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execFile } = require('child_process');

const MCP_NAME = 'tuffcode';
const AGENTS = {
  claude: { name: 'Claude Code', bin: 'claude', install: 'npm install -g @anthropic-ai/claude-code', url: 'https://code.claude.com/docs' },
  codex: { name: 'Codex', bin: 'codex', install: 'npm install -g @openai/codex', url: 'https://developers.openai.com/codex' },
  antigravity: { name: 'Antigravity', bin: 'agy', install: 'Install Antigravity from antigravity.google, then run: agy install', url: 'https://antigravity.google' },
};

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
  return which(AGENTS[id].bin);
}

// npm installs agents as .cmd shims, which Windows can only start through cmd.exe. Our arguments
// are fixed flags and quoted paths; free text (the prompt) always goes through stdin instead.
const cmdQuote = (a) => (/^[\w\-.:=/\\@]+$/.test(a) ? a : `"${String(a).replace(/"/g, '""')}"`);
function startCli(file, args, opts) {
  if (/\.(cmd|bat)$/i.test(file)) {
    if (args.some((a) => /[\r\n%!^]/.test(a))) throw new Error('Unsafe argument for a .cmd agent');
    return spawn(`"${file}"`, args.map(cmdQuote), { ...opts, shell: true, windowsHide: true });
  }
  return spawn(file, args, { ...opts, windowsHide: true });
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
  else proc.kill('SIGTERM');
}

async function detect() {
  return Promise.all(Object.entries(AGENTS).map(async ([id, a]) => {
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
    add: () => ['mcp', 'add', '--scope', 'user', '-e', 'ELECTRON_RUN_AS_NODE=1', MCP_NAME, '--', mcpServer().command, mcpServer().args[0]],
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

async function connection(id) {
  const file = await resolveBin(id);
  if (!file) return { id, installed: false, connected: false };
  return { id, installed: true, connected: await CONNECT[id].check(file) };
}

async function connect(id, on = true) {
  const file = await resolveBin(id);
  if (!file) throw new Error(`${AGENTS[id].name} isn't installed.`);
  const r = await quick(file, on ? CONNECT[id].add() : CONNECT[id].remove(), 30000);
  const state = await connection(id);
  if (state.connected !== on) throw new Error(r.out || `Couldn't ${on ? 'connect' : 'disconnect'} ${AGENTS[id].name}.`);
  return state;
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

function argsFor(agent, { mode, session }) {
  const edit = mode === 'edit';
  if (agent === 'claude') {
    const args = ['-p', '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
      '--mcp-config', claudeMcpConfigFile(), '--allowedTools', `mcp__${MCP_NAME}`, '--permission-mode', edit ? 'acceptEdits' : 'default'];
    if (session) args.push('--resume', session);
    return { args, stdin: true };
  }
  if (agent === 'codex') return { args: ['exec', '--json', '--skip-git-repo-check', '--sandbox', edit ? 'workspace-write' : 'read-only', '-'], stdin: true };
  return { args: ['-p', '--output-format', 'stream-json', '--mode', edit ? 'accept-edits' : 'plan'], stdin: false };
}

// Each parser turns one JSON line from an agent into panel events:
// session, delta (streamed text), text (a whole message), tool, tool_result, done, error.
function claudeParser() {
  let streamed = false;
  let anyText = false;
  return (o, emit) => {
    if (o.type === 'system' && o.subtype === 'init') {
      emit({ kind: 'session', id: o.session_id });
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
      else if (it.type === 'file_change') emit({ kind: 'tool', name: 'Edit', input: { file_path: (it.changes || []).map((c) => c.path).join(', ') } });
      else if (it.type === 'command_execution') emit({ kind: 'tool_result', ok: it.exit_code === 0 || it.status === 'completed' });
      else if (it.type === 'mcp_tool_call') emit({ kind: 'tool_result', ok: it.status !== 'failed' });
      else if (it.type === 'error') emit({ kind: 'error', text: it.message });
    } else if (o.type === 'turn.completed') emit({ kind: 'done', ok: true });
    else if (o.type === 'turn.failed') emit({ kind: 'done', ok: false, error: o.error?.message || 'The turn failed.' });
    else if (o.type === 'error') emit({ kind: 'error', text: o.message });
  };
}

// Antigravity's stream mirrors Claude Code's; anything else with text in it is shown as text.
function antigravityParser() {
  const claude = claudeParser();
  let shown = false;
  return (o, emit) => {
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

async function run({ runId, agent, prompt, root, mode, session }, emit) {
  const send = (e) => emit({ runId, ...e });
  const file = await resolveBin(agent);
  if (!file) { send({ kind: 'done', ok: false, error: `${AGENTS[agent].name} isn't installed. ${AGENTS[agent].install}` }); return; }
  const { args, stdin } = argsFor(agent, { mode, session });
  if (!stdin) args.push(prompt);
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
  const proc = runs.get(runId);
  if (proc) killTree(proc);
  runs.delete(runId);
}

module.exports = { AGENTS, setup, detect, run, stop, connection, connect, mcpServer, mcpSetup, mcpCheck };
