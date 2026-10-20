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

const VERSION = '1.0.0';
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

const GUIDE = `# Tuff language guide

Tuff is a small, beginner-friendly language. Files end in \`.tuf\`. Blocks are indented (4 spaces), like Python.

## Basics
\`\`\`tuff
# comments start with #
say "Hello"                 # show a line
name = input "Your name? "  # ask a question (gives back text)
score = 10
score += 5                  # also -= *= /=
if score is 15:             # 'is' means equals, 'is not' means not equal; 'then' works instead of ':'
    say "fifteen"
elif score > 20:
    say "big"
else:
    say "small"
for i in range(1, 3):       # 1, 2, 3 - the END IS INCLUDED (unlike Python)
    say i
while score > 0:
    score -= 1
func double(n):
    n * 2                   # a function gives back its last value; 'return' also works
say double(4)
\`\`\`

- Text joins with +: \`"Hi " + name\`. Turn numbers into text with \`text(n)\` and text into numbers with \`number(t)\`.
- Lists: \`[1, 2, 3]\`, \`items[0]\`, \`len(items)\`.
- \`and\`, \`or\`, \`not\`, \`true\`, \`false\`, \`nil\`.
- Functions can change variables made outside them (\`n += 1\` inside a func updates the outer n).

## Live lines and clearing
\`\`\`tuff
line = say "Loading"
wait(1)
line:rewrite "Done!"
flush        # clear the screen
clear(2)     # remove the last 2 lines
\`\`\`

## Methods use a colon
\`thing:method args\`. Brackets are optional for one argument: \`app:heading "Hi"\`, \`name:value\`, \`status:set "Done"\`.
A method with no inputs is called just by naming it: \`task:clear\`, \`clock:pause\`.

## Libraries
\`import x\` and \`mention x\` mean the same thing. Put them at the top.
- **anims**: console animations (\`anims.loading\`, \`anims.bar\`, \`anims.type\`, \`anims.countdown\`).
- **tgui**: real desktop app windows. **mtgui**: the same widgets with a modern look (gradients, gloss, glow).

## Making an app window (tgui / mtgui)
\`\`\`tuff
mention mtgui

app = mtgui.window("Greeter", 380, 420)   # title, width, height
app:accent "purple"                        # blue purple pink red orange yellow green teal or "#hex"
app:heading "Hello!"
name = app:input "Your name"
hello = app:text ""
row = app:row                              # side by side
row:button("Say hi", greet, "primary")     # text, function to run, style
row:button("Clear", clear, "ghost")
name:enter greet                           # run greet when Enter is pressed in the box

func greet():
    hello:set "Hey " + name:value + "!"

func clear():
    name:clear
    hello:set ""
\`\`\`

Widgets: heading, text, small, button, input, toggle, checkbox, dropdown, slider, progress, spinner, clock, image, divider, space, row, card.
Containers: \`row = app:row\` (side by side) and \`card = app:card\` (a rounded panel). Add to them with \`row:button(...)\`, \`card:text "..."\`.
Button styles: primary, secondary, outline, ghost, success, danger.
Events: \`button:click fn\`, \`box:change fn\`, \`box:enter fn\`, \`switch:change fn\`, \`dropdown:change fn\`, \`slider:change fn\`.
Timers: \`app:every(seconds, fn)\`, \`app:after(seconds, fn)\`. Popups: \`app:alert "Hi"\`, \`app:confirm "Sure?"\`, \`app:ask "Name?"\`.
Every widget has \`:hide\`, \`:show\`, \`:remove\`; buttons have \`:disable\`/\`:enable\`; anything animated has \`:speed n\`.
Functions used by buttons and events must be defined with \`func\` (they can be lower in the file than the button).

## Tips for writing Tuff for beginners
- Keep programs short and readable, with clear names.
- Use mtgui for apps unless asked otherwise.
- Check your code with the tuff_check tool before giving it to the user.
`;

function reference(topic) {
  const t = loadTables();
  const fmt = (table) => Object.entries(table || {}).map(([k, [sig, doc]]) => `- \`${sig}\`: ${doc}`).join('\n');
  const parts = {
    guide: GUIDE,
    keywords: `## Keywords\n${(t.TUFF_KEYWORDS || []).join(', ')}`,
    builtins: `## Built-in functions and keywords\n${fmt(t.TUFF_DOCS)}`,
    libraries: `## Libraries\n${Object.entries(t.TUFF_LIBS || {}).map(([lib, fns]) => `### ${lib}\n${fmt(fns)}`).join('\n\n')}`,
    widgets: `## tgui / mtgui methods\n${fmt(t.TUFF_METHOD_DOCS)}`,
  };
  if (topic && parts[topic]) return parts[topic];
  return Object.values(parts).join('\n\n');
}

function examples() {
  const t = loadTables();
  return (t.TUFF_TEMPLATES || []).map((x) => `## ${x.name} (${x.id}.tuf)\n${x.desc}\n\n\`\`\`tuff\n${x.code}\`\`\``).join('\n\n') || 'No examples found.';
}

// Run the interpreter. Returns { code, out, timedOut }.
function runTuff(args, { input = '', timeout = 10, cwd } = {}) {
  return new Promise((resolve) => {
    const [cmd, ...base] = tuffCommand();
    let out = '';
    let timedOut = false;
    let proc;
    try {
      proc = spawn(cmd, [...base, ...args], { cwd, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8', TUFF_IDE: '' } });
    } catch (err) {
      resolve({ code: -1, out: `Could not start Tuff: ${err.message}`, timedOut });
      return;
    }
    const add = (d) => { if (out.length < 60000) out += d.toString(); };
    proc.stdout.on('data', add);
    proc.stderr.on('data', add);
    proc.on('error', (err) => resolve({ code: -1, out: `Could not start Tuff (${cmd}): ${err.message}`, timedOut }));
    const timer = setTimeout(() => { timedOut = true; proc.kill(); }, Math.max(1, Math.min(60, timeout)) * 1000);
    proc.on('close', (code) => { clearTimeout(timer); resolve({ code, out, timedOut }); });
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
    description: 'Complete, working Tuff app examples (counter, sign-in form, to-do list, order form, clock, settings page, quiz). Good patterns for tgui/mtgui windows, events and functions.',
    inputSchema: { type: 'object', properties: {} },
    annotations: { readOnlyHint: true },
    async run() { return examples(); },
  },
  {
    name: 'tuff_check',
    description: 'Check Tuff code for mistakes without running it. Pass "file" (path to a .tuf file) or "code". Returns OK or the error with its line number, in plain English.',
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
    description: 'Run a Tuff program and return what it printed. Pass "file" or "code", plus optional "input" (text typed in, one answer per line) and "timeout_seconds" (default 10, max 60). Programs that open app windows (tgui/mtgui) show a real window on the user\'s screen until the timeout, so prefer tuff_check for those.',
    inputSchema: { type: 'object', properties: { file: { type: 'string' }, code: { type: 'string' }, input: { type: 'string' }, timeout_seconds: { type: 'number' } } },
    async run(a) {
      const src = sourceFile(a);
      try {
        const r = await runTuff([src.file], { input: a.input || '', timeout: a.timeout_seconds || 10, cwd: a.file ? path.dirname(src.file) : process.cwd() });
        const text = clean(r.out).trim();
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
