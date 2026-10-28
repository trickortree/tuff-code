// Learn Tuff (renderer/js/learn.js) in Node with no window: its sections, its lessons' checks, and what "Start lesson"
// writes into a project (the lesson's file, and the files some lessons use next to it, like money.tuf and a sprite
// sheet). The page is pretend: every element takes anything, and Learn's buttons are clicked by calling the listener
// it gave them. It prints what it saw as JSON; run_tests.py (t_learn_150) checks it.
//
//     node learn_test.mjs path/to/learn.js plan.json
//
// plan.json: {"checks": [{"id", "src", "out"}...], "starts": [{"root", "id", "remove": [names in lessons/ to delete
// first]}...], "runs": [{"root", "id", "runs": [{"code", "src", "out"}...]}...]}. It prints {"sections", "verdicts" (a
// check's true or hint, or "THREW ..."), "starts": [{"calls", "files"}], "runs": [[what the lesson's status line says
// after each run, or null]]}, where calls are the file operations Learn asked for, in order, and files what lessons/
// holds after.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const [learnFile, planFile] = process.argv.slice(2);
const source = fs.readFileSync(learnFile, 'utf8');
const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));

// One fresh Learn, as the page loads it: window.tuff (the IDE's bridge to the main process) is read when it loads.
function load(tuff) {
  const clicks = {};
  const shown = {}; // by selector, the element Learn last looked up in one it made, with what it put there
  const listeners = {}; // the window's, like tuff:run-finished
  const element = (sel = '') => ({
    sel, style: { setProperty() {} }, dataset: {}, textContent: '', innerHTML: '', className: '',
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild: (child) => child, remove() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0 }),
    addEventListener: (type, fn) => { if (type === 'click') (clicks[sel] = clicks[sel] || []).push(fn); },
    querySelector: (s) => (shown[s] = element(s)), querySelectorAll: () => [],
  });
  const window = { tuff, addEventListener: (type, fn) => (listeners[type] = listeners[type] || []).push(fn) };
  const document = { querySelector: (s) => element(s), querySelectorAll: () => [], createElement: () => element(), body: element('body'), addEventListener() {} };
  vm.runInNewContext(source, { window, document, console, setTimeout, clearTimeout, TuffIcon: () => '<svg></svg>' });
  return { learn: window.TuffLearn, clicks, shown, listeners };
}

const { learn } = load({});
const out = { sections: learn.sections(), verdicts: [], starts: [], runs: [] };
for (const job of plan.checks || []) {
  try {
    out.verdicts.push(learn.check(job.id, job.src, job.out || ''));
  } catch (err) {
    out.verdicts.push(`THREW ${err.message}`);
  }
}

// "Start lesson" in a project: the IDE's own file calls, on real files in root.
for (const start of plan.starts || []) {
  const root = path.resolve(start.root);
  const lessons = path.join(root, 'lessons');
  const rel = (p) => path.relative(root, p).split(path.sep).join('/');
  for (const name of start.remove || []) fs.rmSync(path.join(lessons, name), { force: true });
  const calls = [];
  const tuff = {
    fs: {
      exists: async (p) => fs.existsSync(p),
      createDir: async (p) => { calls.push(['createDir', rel(p)]); fs.mkdirSync(p); },
      writeFile: async (p, text) => { calls.push(['writeFile', rel(p)]); fs.writeFileSync(p, String(text), 'utf8'); },
      readFile: async (p) => fs.readFileSync(p, 'utf8'),
    },
    // main.js's plugins:writeFile: text or base64, and only inside the open project (the folder it watches).
    plugins: {
      writeFile: async (p, data, encoding = 'utf8') => {
        const target = path.resolve(root, String(p));
        if (!target.startsWith(root + path.sep)) throw new Error('Plugins can only save inside the open project.');
        calls.push(['plugins.writeFile', rel(target), encoding]);
        fs.mkdirSync(path.dirname(target), { recursive: true });
        if (encoding === 'base64') fs.writeFileSync(target, Buffer.from(String(data), 'base64'));
        else fs.writeFileSync(target, String(data), 'utf8');
        return target;
      },
    },
  };
  const page = load(tuff);
  const settings = { learnDone: [], learnCurrent: start.id, learnOpen: ['basics'] };
  page.learn.init({
    root: () => root,
    join: (a, b) => a.replace(/[\\/]+$/, '') + path.sep + b,
    settings: () => settings,
    saveSettings() {},
    toast() {},
    refreshTree: async () => { calls.push(['refreshTree']); },
    openFile: async (p) => { calls.push(['openFile', rel(p)]); },
    runFile() {},
    monacoReady: async () => ({ editor: { colorize: async (code) => code } }),
  });
  const buttons = page.clicks['[data-act="open"]'] || [];  // the open lesson's Start lesson
  if (buttons.length) await buttons[buttons.length - 1]();
  else calls.push(['no Start lesson button']);
  const files = fs.existsSync(lessons) ? fs.readdirSync(lessons).sort() : [];
  out.starts.push({ calls, files });
}

// Runs of a lesson's file ending, as ide.js says so (tuff:run-finished, with the exit code and what the run said), with
// that lesson open: what its status line says after each one. The file holds each run's src while it's checked.
for (const job of plan.runs || []) {
  const root = path.resolve(job.root);
  let src = '';
  const page = load({ fs: { readFile: async () => src, exists: async () => true } });
  page.learn.init({
    root: () => root,
    join: (a, b) => a.replace(/[\\/]+$/, '') + path.sep + b,
    settings: () => ({ learnDone: [], learnCurrent: job.id, learnOpen: ['basics'] }),
    saveSettings() {},
    toast() {},
    monacoReady: async () => ({ editor: { colorize: async (code) => code } }),
  });
  const file = path.join(root, 'lessons', learn.sections().flatMap((s) => s.lessons).find((l) => l.id === job.id).file);
  const said = [];
  for (const run of job.runs) {
    src = run.src || '';
    for (const fn of page.listeners['tuff:run-finished'] || []) await fn({ detail: { file, code: run.code, output: run.out || '' } });
    said.push(page.shown['.lx-status span']?.textContent ?? null);
  }
  out.runs.push(said);
}

console.log(JSON.stringify(out));
