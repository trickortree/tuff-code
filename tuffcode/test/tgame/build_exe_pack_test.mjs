// Build exe with no PyInstaller and no windows: what it packs and where it goes in the app, and the launcher's error
// box. tuffcode/build.js runs as the Build exe dialog runs it (Electron's app and nativeImage stood in for, as in
// build_exe_test.mjs) and its --check is real, but PyInstaller is stood in for: the stand-in lays the --add-data files
// out in a folder the way a --onefile app unpacks them (its _MEIPASS), with the launcher and the runtime beside them.
// Console programs then run from that folder for real, and as_windowed.py runs the launcher as an app with no console
// would, with its error box stood in for, so nothing ever opens.
//   node tuffcode/test/tgame/build_exe_pack_test.mjs [--keep]
// About 10 s. Exits 1 if a check failed. The real builds (PyInstaller, and the apps opened) are build_exe_test.mjs.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { EventEmitter } from 'node:events';
import childProcess, { spawnSync } from 'node:child_process';
import Module, { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_DIR = path.resolve(HERE, '..', '..');
const require = createRequire(import.meta.url);
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'tgame-pack-'));
const PY = process.platform === 'win32' ? ['py', '-3'] : ['python3'];
const SEP = process.platform === 'win32' ? ';' : ':';
let passed = 0;
let failed = 0;
const check = (ok, what, got) => {
  if (ok) passed++; else failed++;
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}${ok || got === undefined ? '' : `\n         got: ${String(JSON.stringify(got)).slice(0, 600)}`}`);
};

// Electron's app and nativeImage, as much as build.js uses of them.
const image = (png) => ({ isEmpty: () => !png || !png.length, resize: () => image(png), toPNG: () => png,
  toDataURL: () => `data:image/png;base64,${png.toString('base64')}` });
const electron = {
  app: { isPackaged: false, getPath: (name) => (name === 'temp' ? path.join(scratch, 'temp') : path.join(scratch, 'user-data')) },
  nativeImage: { createFromPath: (file) => image(fs.existsSync(file) ? fs.readFileSync(file) : null) },
};

// PyInstaller's stand-in: the app's files laid out in apps/<name> (what the app unpacks to), and an empty .exe.
let lastBuild = null;
function standInBuild(args) {
  const value = (flag) => args[args.indexOf(flag) + 1];
  const name = value('--name');
  const bundle = path.join(scratch, 'apps', name);
  fs.rmSync(bundle, { recursive: true, force: true });
  fs.mkdirSync(bundle, { recursive: true });
  const data = [];
  args.forEach((a, i) => { if (a === '--add-data') data.push(args[i + 1]); });
  for (const d of data) {
    const from = d.slice(0, d.lastIndexOf(SEP));
    const dest = path.join(bundle, ...d.slice(d.lastIndexOf(SEP) + 1).split('/'));
    fs.mkdirSync(dest, { recursive: true });
    if (fs.statSync(from).isDirectory()) fs.cpSync(from, dest, { recursive: true });
    else fs.copyFileSync(from, path.join(dest, path.basename(from)));
  }
  const work = path.dirname(args.at(-1)); // the launcher, with the runtime's modules beside it
  for (const f of fs.readdirSync(work)) if (f.endsWith('.py')) fs.copyFileSync(path.join(work, f), path.join(bundle, f));
  fs.mkdirSync(value('--distpath'), { recursive: true });
  const exe = path.join(value('--distpath'), name + (process.platform === 'win32' ? '.exe' : ''));
  if (process.platform === 'darwin' && args.includes('--windowed')) fs.mkdirSync(`${exe}.app`, { recursive: true });
  else fs.writeFileSync(exe, 'a stand-in');
  lastBuild = { args, data, bundle, launcher: path.join(bundle, path.basename(args.at(-1))) };
}
function standInSpawn(cmd, args, opts) {
  if (args.includes('--check')) return childProcess.spawn(cmd, args, opts); // the real check (it opens nothing)
  const answer = (out, code = 0, effect) => {
    const proc = new EventEmitter();
    proc.stdout = new EventEmitter();
    proc.stderr = new EventEmitter();
    proc.kill = () => {};
    setImmediate(() => {
      try { effect?.(); } catch (err) { out += String(err.stack); code = 1; }
      if (out) proc.stdout.emit('data', Buffer.from(out));
      proc.emit('close', code);
    });
    return proc;
  };
  if (args.includes('PyInstaller')) return args.includes('--version') ? answer('6.0.0\n') : answer('Building EXE\n', 0, () => standInBuild(args));
  if (args.includes('pip')) return args.includes('install') ? answer('Nothing is downloaded in this test.\n', 1) : answer('pip 24\n');
  if (args.includes('-c')) return answer(''); // import webview, tkinter: they're there
  if (args.at(-1) === '--version') return answer('Python 3.12.10\n');
  return answer(`The test didn't expect: ${cmd} ${args.join(' ')}\n`, 1);
}
const load = Module._load;
Module._load = function (request, parent, ...rest) {
  if (request === 'electron') return electron;
  if (request === './shellpath') return { ready: async () => {} };
  if (request === 'child_process' && parent?.filename === path.join(APP_DIR, 'build.js')) return { ...childProcess, spawn: standInSpawn };
  return load.call(this, request, parent, ...rest);
};
const build = require(path.join(APP_DIR, 'build.js'));

async function buildApp(file, name) {
  const events = [];
  lastBuild = null;
  await build.start({ file, name, root: path.dirname(file) }, (e) => events.push(e));
  const done = events.find((e) => e.type === 'done') || {};
  done.steps = events.filter((e) => e.type === 'step');
  done.log = events.filter((e) => e.type === 'log').map((e) => e.text).join('\n');
  done.app = lastBuild;
  if (!done.ok) console.log(`  the build says: ${String(done.message).replace(/\n/g, ' / ')}`);
  return done;
}
const write = (file, text) => { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, text); };
const env = { ...process.env };
for (const k of ['TUFF_IDE', 'TUFF_BASE_DIR', 'TUFF_NO_WRITES']) delete env[k];
const runApp = (app) => spawnSync(PY[0], [...PY.slice(1), app.launcher], { cwd: scratch, env, input: '', encoding: 'utf8', timeout: 30000, windowsHide: true });
const said = (r) => r.stdout.replace(/\r/g, '').trim().split('\n').join('|');
const inApp = (app, rel) => fs.existsSync(path.join(app.bundle, ...rel.split('/')));
const launcherLine = (app) => (fs.readFileSync(app.launcher, 'utf8').match(/^sys\.argv = .*$/m) || [''])[0];
const STAR = path.join(HERE, 'games', 'star.png');

// Files next to the program and in a folder it names: the app's layout is as before (the program at its top).
console.log('== Build exe: a program with files next to it and in sprites/');
const plainDir = path.join(scratch, 'Plain Files');
write(path.join(plainDir, 'words.txt'), 'words next to it');
write(path.join(plainDir, 'sprites', 'hero.txt'), 'and one in sprites');
write(path.join(plainDir, 'hello.tuf'), 'say file.read("words.txt")\nsay file.read("sprites/hero.txt")\n');
const plain = await buildApp(path.join(plainDir, 'hello.tuf'), 'Plain Pack Test');
check(plain.ok && plain.app, 'it builds', plain.message);
if (plain.app) {
  check(plain.app.data[0].endsWith(`program.tuf${SEP}.`), 'program.tuf goes at the top of the app, as before', plain.app.data);
  check(inApp(plain.app, 'program.tuf') && inApp(plain.app, 'words.txt') && inApp(plain.app, 'sprites/hero.txt') && !inApp(plain.app, '_project'),
    'words.txt and sprites/hero.txt beside it, no _project folder', fs.readdirSync(plain.app.bundle));
  check(launcherLine(plain.app) === 'sys.argv = [sys.argv[0], os.path.join(base, "program.tuf")]', 'the launcher runs program.tuf from the top', launcherLine(plain.app));
  const r = runApp(plain.app);
  check(r.status === 0 && said(r) === 'words next to it|and one in sprites', 'and the program finds both files in the app', { status: r.status, stdout: r.stdout, stderr: r.stderr });
}

// mtgui loads "../" pictures from the folder above. The app keeps them in _project, laid out as they are here.
console.log('== Build exe: an mtgui app with "../" pictures');
const above = path.join(scratch, 'Pictures Above');
const appDir = path.join(above, 'app');
fs.mkdirSync(path.join(above, 'art', 'sub'), { recursive: true });
fs.mkdirSync(path.join(above, 'other'), { recursive: true });
fs.mkdirSync(appDir, { recursive: true });
for (const f of ['star.png', 'top.png', 'art/moon.png', 'art/sub/deep.png', 'other/far.png', 'app/inside.png']) fs.copyFileSync(STAR, path.join(above, f));
write(path.join(above, 'notes.md'), '# not a file Build exe packs\n');
write(path.join(appDir, 'pics.tuf'), 'mention mtgui\n\napp = mtgui.window("Pictures")\napp:image("inside.png")\napp:image("../star.png")\n'
  + 'app:image("../art/" + "moon.png")\npic = "top.png"\napp:image("../" + pic)\n');
const pics = await buildApp(path.join(appDir, 'pics.tuf'), 'Outside Pack Test');
const pack = pics.steps.filter((s) => s.id === 'pack').pop() || {};
check(pics.ok && pack.state === 'done', 'it builds (it doesn\'t stop at "Packing your program" any more)', { message: pics.message, pack });
check(/\.\.\/star\.png/.test(pack.label || ''), `and says what it packed: ${pack.label}`, pack.label);
if (pics.app) {
  const want = ['_project/app/program.tuf', '_project/app/inside.png', '_project/star.png', '_project/top.png', '_project/art/moon.png', '_project/art/sub/deep.png'];
  check(want.every((f) => inApp(pics.app, f)), 'the app has the program in _project/app, ../star.png and ../top.png in _project, and all of ../art/', want.filter((f) => !inApp(pics.app, f)));
  check(!inApp(pics.app, '_project/notes.md') && !inApp(pics.app, '_project/other') && !inApp(pics.app, 'inside.png') && !inApp(pics.app, 'program.tuf'),
    'but not notes.md, nor other/ (the code never names it), and nothing of the project at the top', fs.readdirSync(pics.app.bundle));
  check(launcherLine(pics.app) === 'sys.argv = [sys.argv[0], os.path.join(base, "_project", "app", "program.tuf")]', 'the launcher runs it from _project/app', launcherLine(pics.app));
  const from = path.join(pics.app.bundle, '_project', 'app');
  const used = ['inside.png', '../star.png', '../art/moon.png', '../top.png'];
  check(used.every((p) => fs.existsSync(path.resolve(from, p))), 'so every picture the code uses is there, from where the program is', used.filter((p) => !fs.existsSync(path.resolve(from, p))));
}

// Two folders up, and a console program that really reads them in the app.
console.log('== Build exe: a console program reading "../../" files');
const shared = path.join(scratch, 'Shared');
write(path.join(shared, 'data.txt'), 'hello from two folders up');
write(path.join(shared, 'more', 'info.txt'), 'and from a folder beside them');
write(path.join(shared, 'games', 'level1', 'here.txt'), 'and from here');
write(path.join(shared, 'games', 'level1', 'read.tuf'), 'say file.read("../../data.txt")\nsay file.read("../../more/info.txt")\nsay file.read("here.txt")\n');
const up = await buildApp(path.join(shared, 'games', 'level1', 'read.tuf'), 'Up Two Pack Test');
check(up.ok && up.app, 'it builds', up.message);
if (up.app) {
  check(inApp(up.app, '_project/games/level1/program.tuf') && inApp(up.app, '_project/data.txt') && inApp(up.app, '_project/more/info.txt')
    && inApp(up.app, '_project/games/level1/here.txt'), 'laid out from Shared, the folder that holds them all', up.app.data);
  const r = runApp(up.app);
  check(r.status === 0 && said(r) === 'hello from two folders up|and from a folder beside them|and from here', 'and the program reads all three in the app', { status: r.status, stdout: r.stdout, stderr: r.stderr });
}

// The launcher's error box, for an app with no console: Tuff errors as before, and problems inside Tuff itself.
console.log('== Build exe: the launcher\'s error box');
const oopsDir = path.join(scratch, 'Mistake');
write(path.join(oopsDir, 'oops.tuf'), 'say "before"\nitems = [1, 2]\nsay items[5]\n');
const oops = await buildApp(path.join(oopsDir, 'oops.tuf'), 'Mistake Pack Test');
const windowed = (app, mode, ...more) => {
  const out = path.join(scratch, `boxes-${path.basename(app.bundle)}-${mode}${more.join('')}.json`);
  const r = spawnSync(PY[0], [...PY.slice(1), path.join(HERE, 'as_windowed.py'), app.launcher, out, mode, ...more],
    { cwd: scratch, env, input: '', encoding: 'utf8', timeout: 30000, windowsHide: true });
  let state = {};
  try { state = JSON.parse(fs.readFileSync(out, 'utf8')); } catch {}
  return { ...state, status: r.status, stderr: r.stderr, boxes: state.boxes || [] };
};
const texts = (s) => s.boxes.map((b) => `${b.title}: ${b.text}`);
const problem = (where) => new RegExp(`^Something went wrong: Tuff error: Tuff itself had a problem \\(${where}\\): RuntimeError: the engine broke \\(as_windowed\\.py, line \\d+\\)$`);
if (oops.ok && oops.app) {
  const s = windowed(oops.app, 'none');
  check(s.windowed === true && s.code === 1 && s.boxes.length === 1 && texts(s)[0] === 'Something went wrong: Tuff error on line 3: Position 5 is outside this list (it has 2 items, starting at 0).\n  3 | say items[5]',
    'a Tuff error shows in the box, with its line, as before', s);
} else check(false, 'the program with a mistake builds (--check can\'t see it)', oops.message);
if (plain.app) {
  let s = windowed(plain.app, 'none');
  check(s.windowed === true && s.code === 0 && s.boxes.length === 0, 'a program that works shows no box', s);
  s = windowed(plain.app, 'crash');
  check(s.code === 1 && s.boxes.length === 1 && problem('running the program').test(texts(s)[0]),
    'a Python problem from the runtime (not a Tuff error) shows in the box too, not just on stderr', s);
  s = windowed(plain.app, 'thread');
  check(s.code === 0 && s.boxes.length === 1 && problem('in the background').test(texts(s)[0]), 'so does one in a thread, and the program goes on', s);
  s = windowed(plain.app, 'twice');
  check(s.boxes.length === 1, 'the same problem twice is shown once', s);
  s = windowed(plain.app, 'hook');
  check(s.boxes.length === 1 && problem('running the program').test(texts(s)[0]), 'and one handed to sys.excepthook', s);
  s = windowed(plain.app, 'stuck');
  check(s.status === 1 && s.boxes.length === 1 && problem('running the program').test(texts(s)[0]),
    'tuff_view ending the app at once (pywebview stuck) still shows the problem it ended with', s);
  s = windowed(plain.app, 'crash', 'console');
  check(s.windowed === false && s.code === 1 && s.boxes.length === 0 && /Traceback/.test(s.stderr)
    && /Tuff error: Tuff itself had a problem \(running the program\): RuntimeError: the engine broke/.test(s.stderr),
  'with a console there\'s no box: the problem and its traceback are printed', s);
}

// 1.5.0: a program in several files (import money). The files it imports go in the app beside it, in the folders they're
// in (libs/ too), and only those: a .tuf file it doesn't import stays out.
console.log('== Build exe: a program that imports its own files');
const modsDir = path.join(scratch, 'Own Files');
write(path.join(modsDir, 'shop.tuf'), 'import money\nimport fmt\nsay money.as_money(6.375)\nsay fmt.stars(3)\nsay money.half("a")\n');
write(path.join(modsDir, 'money.tuf'), 'import tax\nfunc as_money(x):\n    return f"{tax.add(x):money}"\nfunc half(n):\n    return n / 2\n');
write(path.join(modsDir, 'tax.tuf'), 'func add(x):\n    return x * 2\n');
write(path.join(modsDir, 'libs', 'fmt.tuf'), 'func stars(n):\n    return "*" * n\n');
write(path.join(modsDir, 'unused.tuf'), 'say "never imported"\n');
const mods = await buildApp(path.join(modsDir, 'shop.tuf'), 'Own Files Pack Test');
check(mods.ok && mods.app, 'it builds', mods.message);
if (mods.app) {
  check(['program.tuf', 'money.tuf', 'tax.tuf', 'libs/fmt.tuf'].every((f) => inApp(mods.app, f)) && !inApp(mods.app, 'unused.tuf') && !inApp(mods.app, 'shop.tuf'),
    'program.tuf, money.tuf, tax.tuf (money.tuf imports it) and libs/fmt.tuf are in the app, unused.tuf isn\'t', fs.readdirSync(mods.app.bundle));
  const checkStep = mods.steps.filter((s) => s.id === 'check').pop() || {};
  check(/money\.tuf/.test(checkStep.label || '') && /fmt\.tuf/.test(checkStep.label || ''), `each file is checked: ${checkStep.label}`, checkStep);
  const r = runApp(mods.app);
  check(r.status === 1 && said(r) === '$12.75|***' && /Tuff error in money\.tuf on line 5: Can't divide text and a number\./.test(r.stderr),
    'and the program runs in the app, with an error in money.tuf reported there', { status: r.status, stdout: r.stdout, stderr: r.stderr });
  const s = windowed(mods.app, 'none');
  check(s.code === 1 && s.boxes.length === 1 && texts(s)[0] === "Something went wrong: Tuff error in money.tuf on line 5: Can't divide text and a number.\n  5 |     return n / 2",
    "with no console, the box names money.tuf and shows its line", s);
}
write(path.join(modsDir, 'tax.tuf'), 'func add(x:\n    return x * 2\n');
const broken = await buildApp(path.join(modsDir, 'shop.tuf'), 'Own Files Broken Test');
check(!broken.ok && /tax\.tuf has a mistake/.test(broken.message || '') && /Tuff error on line 1/.test(broken.message || ''),
  'a mistake in a file it imports stops the build and names the file', broken.message);

console.log(`build_exe_pack: ${passed} passed, ${failed} failed`);
if (process.argv.includes('--keep')) console.log(`kept ${scratch}`);
else fs.rmSync(scratch, { recursive: true, force: true });
process.exit(failed ? 1 : 0);
