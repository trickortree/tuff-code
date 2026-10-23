#!/usr/bin/env node
// TuffCode MCP server: teaches AI agents (Claude Code, Codex, Antigravity...) the Tuff language
// and lets them check and run Tuff programs. Speaks MCP over stdio (one JSON-RPC message per line).
//
// Run it with Node, or with TuffCode itself: ELECTRON_RUN_AS_NODE=1 TuffCode.exe tuff-mcp.js
// TUFF_CMD (JSON array) says how to run the interpreter, e.g. ["py","-3","-u","C:/.../tuff.py"].
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { spawn } = require('child_process');
const os = require('os');

const VERSION = '1.2.0';
const PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const RENDERER_JS = path.join(__dirname, '..', 'renderer', 'js');

function tuffCommand() {
  try {
    const cmd = JSON.parse(process.env.TUFF_CMD || 'null');
    if (Array.isArray(cmd) && cmd.length) return cmd;
  } catch {}
  // Installed TuffCode: resources/app.asar.unpacked/mcp -> resources/runtime/tuff-runtime.exe
  const runtime = path.join(__dirname, '..', '..', 'runtime', process.platform === 'win32' ? 'tuff-runtime.exe' : 'tuff-runtime');
  if (fs.existsSync(runtime)) return [runtime];
  const py = path.join(__dirname, '..', '..', 'tuff.py');
  return process.platform === 'win32' ? ['py', '-3', '-u', py] : ['python3', '-u', py];
}

// Load the IDE's own language tables (keywords, docs, widget methods, templates) so agents
// see exactly what the editor's hover help and Design Studio know.
function loadTables() {
  const window = {};
  for (const file of ['tuff-lang.js', 'tuff-templates.js']) {
    try { vm.runInNewContext(fs.readFileSync(path.join(RENDERER_JS, file), 'utf8'), { window }, { filename: file }); } catch {}
  }
  return window;
}

// The Tuff guide agents read first (tuff_reference). It lives next to this file so it is easy to edit.
const GUIDE = (() => {
  try { return fs.readFileSync(path.join(__dirname, 'tuff-guide.md'), 'utf8'); } catch {
    return '# Tuff language guide\n\nThe guide file (tuff-guide.md) is missing. Reinstall TuffCode.\n';
  }
})();

function reference(topic) {
  const t = loadTables();
  const fmt = (table) => Object.entries(table || {}).map(([k, [sig, doc]]) => `- \`${sig}\`: ${doc}`).join('\n');
  const parts = {
    guide: GUIDE,
    keywords: `## Keywords\n${(t.TUFF_KEYWORDS || []).join(', ')}`,
    builtins: `## Built-in functions and keywords\n${fmt(t.TUFF_DOCS)}`,
    libraries: `## Libraries\n${Object.entries(t.TUFF_LIBS || {}).map(([lib, fns]) => `### ${lib}\n${fmt(fns)}`).join('\n\n')}`,
    widgets: `## Methods (windows, widgets, lists, text and lines)\n${fmt(t.TUFF_METHOD_DOCS)}`,
  };
  if (topic && parts[topic]) return parts[topic];
  return Object.values(parts).join('\n\n');
}

// The Design Studio's apps, then the tgame games kept for agents.
function examples() {
  const t = loadTables();
  return [...(t.TUFF_TEMPLATES || []), ...(t.TUFF_GAME_EXAMPLES || [])].map((x) => `## ${x.name} (${x.id}.tuf)\n${x.desc}\n\n\`\`\`tuff\n${x.code}\`\`\``).join('\n\n') || 'No examples found.';
}

// Run the interpreter. Returns { code, out, stdout, stderr, timedOut }.
// echo: typed answers show up in the output. ide: the console speaks TuffCode's line protocol
// (say / rewrite / clear), so screen() can rebuild what the Run window would show.
function runTuff(args, { input = '', timeout = 10, cwd, echo = false, ide = false } = {}) {
  return new Promise((resolve) => {
    const [cmd, ...base] = tuffCommand();
    let out = '';
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    let proc;
    try {
      const env = { ...process.env, PYTHONIOENCODING: 'utf-8', TUFF_IDE: ide ? '1' : '', TUFF_ECHO_INPUT: echo ? '1' : '' };
      proc = spawn(cmd, [...base, ...args], { cwd, windowsHide: true, env });
    } catch (err) {
      resolve({ code: -1, out: `Could not start Tuff: ${err.message}`, stdout, stderr: '', timedOut });
      return;
    }
    const add = (which) => (d) => {
      if (out.length >= 60000) return;
      const s = d.toString();
      out += s;
      if (which === 'out') stdout += s; else stderr += s;
    };
    proc.stdout.on('data', add('out'));
    proc.stderr.on('data', add('err'));
    proc.on('error', (err) => resolve({ code: -1, out: `Could not start Tuff (${cmd}): ${err.message}`, stdout, stderr, timedOut }));
    const timer = setTimeout(() => { timedOut = true; proc.kill(); }, Math.max(1, Math.min(60, timeout)) * 1000);
    proc.on('close', (code) => { clearTimeout(timer); resolve({ code, out, stdout, stderr, timedOut }); });
    if (input) proc.stdin.write(input.endsWith('\n') ? input : input + '\n');
    proc.stdin.end();
  });
}

// Use the given file, or write `code` to a temp file.
function sourceFile(a) {
  if (a.file) {
    const p = path.resolve(process.cwd(), a.file);
    if (!fs.existsSync(p)) throw new Error(`No file at ${p}`);
    return { file: p, cleanup: () => {} };
  }
  if (typeof a.code !== 'string') throw new Error('Give either "file" (a .tuf path) or "code" (Tuff source).');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tuff-mcp-'));
  const file = path.join(dir, 'snippet.tuf');
  fs.writeFileSync(file, a.code, 'utf8');
  return { file, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

const clean = (s) => s.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '').replace(/\x1b\][^\x07]*\x07/g, '').replace(/\r/g, '');

// What the Run window would show at the end: replays say / rewrite / clear from the line protocol,
// with plain text (questions and typed answers) in between.
function screen(raw) {
  const lines = [];
  let partial = '';
  const plain = (text) => {
    const parts = (partial + clean(text)).split('\n');
    partial = parts.pop();
    for (const p of parts) lines.push({ text: p });
  };
  const re = /\x1b\]tuff;([^\x07]*)\x07/g;
  let last = 0;
  let m;
  while ((m = re.exec(raw))) {
    plain(raw.slice(last, m.index));
    last = re.lastIndex;
    // say;<id>;<b64>[;<style>]: a style (like "notice", the yellow line tgame programs start with) only colors
    // the line in the IDE, so it's left out here and the line reads like any other.
    const [kind, a, b] = m[1].split(';');
    const text = (s) => Buffer.from(s || '', 'base64').toString('utf8');
    if (kind === 'say') {
      if (partial) { lines.push({ text: partial }); partial = ''; }
      lines.push({ id: a, text: text(b) });
      if (raw[last] === '\n') last += 1; // the protocol's own line end
    } else if (kind === 'rewrite') {
      const line = lines.find((l) => l.id === a);
      if (line) line.text = text(b);
    } else if (kind === 'clear') {
      if (a === 'all') { lines.length = 0; partial = ''; } else lines.splice(Math.max(0, lines.length - Number(a)));
    }
  }
  plain(raw.slice(last));
  if (partial) lines.push({ text: partial });
  return lines.map((l) => l.text).join('\n');
}
const EXAMPLE_NAMES = (loadTables().TUFF_TEMPLATES || []).map((x) => x.name.replace(/^(\w)/, (c) => c.toLowerCase()));
const GAME_EXAMPLE_NAMES = (loadTables().TUFF_GAME_EXAMPLES || []).map((x) => x.name.replace(/^(\w)/, (c) => c.toLowerCase()));

const TOOLS = [
  {
    name: 'tuff_reference',
    description: 'The Tuff language reference: syntax guide, keywords, built-in functions, libraries and every tgui/mtgui widget method. Read this before writing or changing Tuff (.tuf) code.',
    inputSchema: { type: 'object', properties: { topic: { type: 'string', enum: ['guide', 'keywords', 'builtins', 'libraries', 'widgets'], description: 'Only one part of the reference. Leave out for everything.' } } },
    annotations: { readOnlyHint: true },
    async run(a) { return reference(a.topic); },
  },
  {
    name: 'tuff_examples',
    description: `Complete, working Tuff apps (${EXAMPLE_NAMES.join(', ')}). Good patterns for tgui/mtgui windows, pages, events and functions.${GAME_EXAMPLE_NAMES.length ? ` Also tgame games: ${GAME_EXAMPLE_NAMES.join(', ')}.` : ''}`,
    inputSchema: { type: 'object', properties: {} },
    annotations: { readOnlyHint: true },
    async run() { return examples(); },
  },
  {
    name: 'tuff_check',
    description: 'Check Tuff code for mistakes without running it: syntax, names that are never set or only exist inside another function (with "did you mean"), wrong input counts, event functions that would crash or are passed with brackets, methods a list, text, window or widget doesn\'t have, unknown styles and colors, and Python habits that break in Tuff (range(len(...)), typed text used as a number, "Total: " + a + b, :pop(0), random()). Pass "file" (path to a .tuf file) or "code". Returns OK, or every problem with its line number, in plain English. Use it on every Tuff file you write or change, especially window (tgui/mtgui) apps, which tuff_run can only test with a self-test (see the guide).',
    inputSchema: { type: 'object', properties: { file: { type: 'string', description: 'Path to a .tuf file (relative to the project or absolute).' }, code: { type: 'string', description: 'Tuff source code to check.' } } },
    annotations: { readOnlyHint: true },
    async run(a) {
      const src = sourceFile(a);
      try {
        const r = await runTuff(['--check', src.file], { timeout: 15 });
        const text = clean(r.out).trim();
        if (r.code === 0) return text || 'OK';
        throw new Error(text || `The check failed (exit code ${r.code}).`);
      } finally { src.cleanup(); }
    },
  },
  {
    name: 'tuff_run',
    description: 'Run a Tuff program and return what its Run window shows at the end (lines changed with :rewrite or removed with clear show their final state), with each typed answer shown after its question. Pass "file" or "code", plus optional "input" (the answers to type, one per line) and "timeout_seconds" (default 10, max 60). If the program asks more questions than there are answers, it stops with an error saying so. Programs that open app windows (tgui/mtgui) show a real window on the user\'s screen until the timeout, so use tuff_check for those.',
    inputSchema: { type: 'object', properties: { file: { type: 'string' }, code: { type: 'string' }, input: { type: 'string' }, timeout_seconds: { type: 'number' } } },
    async run(a) {
      const src = sourceFile(a);
      try {
        const r = await runTuff([src.file], { input: a.input || '', timeout: a.timeout_seconds || 10, cwd: a.file ? path.dirname(src.file) : process.cwd(), echo: true, ide: true });
        const text = [screen(r.stdout).trim(), clean(r.stderr).trim()].filter(Boolean).join('\n');
        const status = r.timedOut ? `Stopped after ${a.timeout_seconds || 10} seconds (still running).` : `Exit code ${r.code}.`;
        return `${text || '(no output)'}\n\n${status}`;
      } finally { src.cleanup(); }
    },
  },
];

// ---------------------------------------------------------------- JSON-RPC over stdio
const send = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');
const reply = (id, result) => send({ jsonrpc: '2.0', id, result });
const fail = (id, code, message) => send({ jsonrpc: '2.0', id, error: { code, message } });

async function handle(msg) {
  const { id, method, params = {} } = msg;
  const isRequest = id !== undefined && id !== null;
  switch (method) {
    case 'initialize': {
      const version = PROTOCOLS.includes(params.protocolVersion) ? params.protocolVersion : PROTOCOLS[0];
      return reply(id, {
        protocolVersion: version,
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: 'tuffcode', title: 'TuffCode', version: VERSION },
        instructions: 'Tools for the Tuff programming language (.tuf files). Call tuff_reference before writing Tuff, tuff_check after changing it.',
      });
    }
    case 'ping': return reply(id, {});
    case 'tools/list':
      return reply(id, { tools: TOOLS.map(({ name, description, inputSchema, annotations }) => ({ name, description, inputSchema, ...(annotations ? { annotations } : {}) })) });
    case 'tools/call': {
      const tool = TOOLS.find((t) => t.name === params.name);
      if (!tool) return fail(id, -32602, `Unknown tool: ${params.name}`);
      try {
        const text = await tool.run(params.arguments || {});
        return reply(id, { content: [{ type: 'text', text: String(text) }] });
      } catch (err) {
        return reply(id, { content: [{ type: 'text', text: err.message }], isError: true });
      }
    }
    default:
      if (isRequest) return fail(id, -32601, `Method not found: ${method}`);
  }
}

let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buf += chunk;
  let nl;
  while ((nl = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { fail(null, -32700, 'Parse error'); continue; }
    for (const m of Array.isArray(msg) ? msg : [msg]) handle(m).catch((err) => m.id != null && fail(m.id, -32603, err.message));
  }
});
process.stdin.on('end', () => process.exit(0));
