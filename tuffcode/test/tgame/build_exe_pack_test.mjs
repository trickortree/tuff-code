// Build exe with no PyInstaller and no windows: what it packs and where it goes in the app, and the launcher's error
// box. tuffcode/build.js runs as the Build exe dialog runs it (Electron's app and nativeImage stood in for, as in
// build_exe_test.mjs) and its --check is real, but PyInstaller is stood in for: the stand-in lays the --add-data files
// out in a folder the way a --onefile app unpacks them (its _MEIPASS), with the launcher and the runtime beside them.
// Console programs then run from that folder for real, and as_windowed.py runs the launcher as an app with no console
// would, with its error box stood in for, so nothing ever opens. 1.5.0: where a built app keeps what it saves (run frozen,
// unpacked afresh each time), and a project folder with ";" in its path.
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

// PyInstaller's stand-in: the app's files laid out in archives/<name> (what the .exe holds), unpacked into apps/<name>
// as the app does each time it starts (unpack), and an empty .exe.
let lastBuild = null;
function standInBuild(args) {
  const value = (flag) => args[args.indexOf(flag) + 1];
  const name = value('--name');
  const archive = path.join(scratch, 'archives', name);
  const bundle = path.join(scratch, 'apps', name);
  fs.rmSync(archive, { recursive: true, force: true });
  fs.mkdirSync(archive, { recursive: true });
  const data = [];
  args.forEach((a, i) => { if (a === '--add-data') data.push(args[i + 1]); });
  for (const d of data) {
    const from = d.slice(0, d.lastIndexOf(SEP));
    const dest = path.join(archive, ...d.slice(d.lastIndexOf(SEP) + 1).split('/'));
    fs.mkdirSync(dest, { recursive: true });
    if (fs.statSync(from).isDirectory()) fs.cpSync(from, dest, { recursive: true });
    else fs.copyFileSync(from, path.join(dest, path.basename(from)));
  }
  const work = path.dirname(args.at(-1)); // the launcher, with the runtime's modules beside it
  for (const f of fs.readdirSync(work)) if (f.endsWith('.py')) fs.copyFileSync(path.join(work, f), path.join(archive, f));
  const unpack = () => {
    fs.rmSync(bundle, { recursive: true, force: true });
    fs.cpSync(archive, bundle, { recursive: true });
  };
  unpack();
  fs.mkdirSync(value('--distpath'), { recursive: true });
  const exe = path.join(value('--distpath'), name + (process.platform === 'win32' ? '.exe' : ''));
  if (process.platform === 'darwin' && args.includes('--windowed')) fs.mkdirSync(`${exe}.app`, { recursive: true });
  else fs.writeFileSync(exe, 'a stand-in');
  lastBuild = { args, data, bundle, unpack, exe, launcher: path.join(bundle, path.basename(args.at(-1))) };
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
for (const k of ['TUFF_IDE', 'TUFF_BASE_DIR', 'TUFF_NO_WRITES', 'TUFF_DATA_DIR']) delete env[k];
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
check(plain.log.length > 0 && !/python|pyinstaller/i.test(plain.log), "its Technical details name no tool behind Build Exe (1.5.0)",
  plain.log.match(/.{0,60}(python|pyinstaller).{0,60}/i)?.[0] ?? plain.log.length);
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

// 1.5.0: a built app runs from the folder it unpacks into each time it starts, which goes when it closes. So what its
// program saves goes in "<the app's name> files" beside its .exe (on a Mac, beside its .app), or in TuffApps in the
// user's data folder when the .exe's folder can't be written to, and the next start reads it back, starting from the
// files packed with it.
// Its own .tuf files still come from the app. Run here as the real app runs: frozen, unpacked afresh each time, its .exe
// in dist, started from another folder; and the user's data folder is one of the test's own.
console.log('== Build exe: a built app keeps what it saves');
const BOOT = ['import runpy, sys', 'sys.frozen, sys._MEIPASS, sys.executable = True, sys.argv[1], sys.argv[2]', 'sys.path.insert(0, sys.argv[1])',
  'launcher, sys.argv = sys.argv[3], sys.argv[2:3]', 'runpy.run_path(launcher, run_name="__main__")'].join('\n');
const elsewhere = path.join(scratch, 'Elsewhere');
fs.mkdirSync(elsewhere, { recursive: true });
const userEnv = { ...env, APPDATA: path.join(scratch, 'appdata'), HOME: path.join(scratch, 'home'), XDG_DATA_HOME: path.join(scratch, 'xdg'),
  TUFF_NO_SOUND: '1', TUFF_MUSIC_DIR: path.join(scratch, 'music') };
const tuffApps = process.platform === 'win32' ? path.join(userEnv.APPDATA, 'TuffApps')
  : process.platform === 'darwin' ? path.join(userEnv.HOME, 'Library', 'Application Support', 'TuffApps') : path.join(userEnv.XDG_DATA_HOME, 'TuffApps');
const runFrozen = (app, exe) => {
  app.unpack();
  return spawnSync(PY[0], [...PY.slice(1), '-c', BOOT, app.bundle, exe, app.launcher], { cwd: elsewhere, env: userEnv, input: '', encoding: 'utf8', timeout: 30000, windowsHide: true });
};
const saidFrozen = (r) => r.stdout.replace(/\r/g, '').split('\n').filter((x) => x.trim() && x !== 'Press Enter to close...').join('|');
const text = (file) => (fs.existsSync(file) ? fs.readFileSync(file, 'utf8').replace(/\r/g, '') : null);
const keepDir = path.join(scratch, 'Keeps Files');
write(path.join(keepDir, 'notes.txt'), 'packed line\n');
write(path.join(keepDir, 'prices.json'), '{"apple": 0.45}\n');
write(path.join(keepDir, 'tune.wav'), 'a tune it was built with'); // (song:save writes a new one: not over the packed one)
write(path.join(keepDir, 'helper.tuf'), 'func hello():\n    return "the helper.tuf it was built with"\n');
write(path.join(keepDir, 'keeper.tuf'), ['import helper.tuf', 'mention tmusic', 'runs = file.load("runs.json", 0) + 1', 'file.save("runs.json", runs)',
  'file.add("notes.txt", f"run {runs}")', 'say f"run {runs}, {helper.hello()}"', 'apple = file.load("prices.json")["apple"]',
  'notes = file.lines("notes.txt"):join(" / ")', 'say f"apple {apple}, notes {notes}"', 'if runs is 1:', '    file.write("gone.txt", "for a moment")',
  '    file.delete("gone.txt")', '    file.delete("prices.json")', '    song = tmusic.song(120)', '    song:track("piano", "C4")', '    song:save("tune.wav")',
  'say f"{file.exists("gone.txt")} {file.exists("prices.json")} {file.exists("tune.wav")}"', ''].join('\n'));
const keep = await buildApp(path.join(keepDir, 'keeper.tuf'), 'Keeps Files Test');
check(keep.ok && keep.app, 'it builds', keep.message);
if (keep.app) {
  const dist = path.dirname(keep.app.exe);
  // On a Mac the .exe is the program inside name.app (what a windowed build makes): its files go beside the .app.
  const exe = process.platform === 'darwin' ? path.join(dist, 'Keeps Files Test.app', 'Contents', 'MacOS', 'Keeps Files Test') : keep.app.exe;
  fs.mkdirSync(path.dirname(exe), { recursive: true });
  let r = runFrozen(keep.app, exe);
  check(r.status === 0 && saidFrozen(r) === 'run 1, the helper.tuf it was built with|apple 0.45, notes packed line / run 1|false true true',
    'the first run reads the files packed with it (prices.json, notes.txt), and file.delete leaves a packed file there',
    { status: r.status, stdout: r.stdout, stderr: r.stderr });
  const mine = (f) => path.join(dist, 'Keeps Files Test files', f);
  check(text(mine('runs.json')) === '1' && text(mine('notes.txt')) === 'packed line\nrun 1\n' && text(mine('tune.wav'))?.startsWith('RIFF')
    && !fs.existsSync(mine('gone.txt')) && !['runs.json', 'notes.txt', 'tune.wav'].some((f) => fs.existsSync(path.join(dist, f))),
  'file.save, file.add (after the packed text) and song:save go in "Keeps Files Test files" beside the .exe, not loose beside it',
  { dist: fs.readdirSync(dist), mine: fs.existsSync(mine('')) && fs.readdirSync(mine('')) });
  const inside = (f) => fs.existsSync(path.join(keep.app.bundle, f));
  check(!inside('runs.json') && text(path.join(keep.app.bundle, 'tune.wav')) === 'a tune it was built with'
    && text(path.join(keep.app.bundle, 'notes.txt')) === 'packed line\n' && inside('prices.json')
    && !fs.readdirSync(elsewhere).length && (process.platform !== 'darwin' || !fs.readdirSync(path.dirname(exe)).length),
  'and none of it goes in the folder the app unpacks into (it goes when the app closes), inside a Mac\'s .app, or where it was started from',
  { unpacked: fs.readdirSync(keep.app.bundle), elsewhere: fs.readdirSync(elsewhere) });
  write(mine('helper.tuf'), 'func hello():\n    return "a helper.tuf next to the .exe"\n');
  // (and files with its files' names loose beside the .exe, another app's or anyone's, as in a Downloads folder)
  write(path.join(dist, 'runs.json'), '41');
  write(path.join(dist, 'prices.json'), '{"apple": 9.99}\n');
  r = runFrozen(keep.app, exe);
  check(r.status === 0 && saidFrozen(r) === 'run 2, the helper.tuf it was built with|apple 0.45, notes packed line / run 1 / run 2|false true true'
    && text(mine('runs.json')) === '2' && text(path.join(dist, 'runs.json')) === '41',
  'the next start (unpacked afresh) reads them back, its own .tuf files still come from the app, and files loose beside the .exe '
    + '(another app\'s runs.json and prices.json) aren\'t taken for its own', { status: r.status, stdout: r.stdout, stderr: r.stderr });
  // A folder that can't be written to (Program Files, or a Mac app run where it was downloaded): here one that isn't there.
  const locked = path.join(scratch, 'Not There', path.basename(keep.app.exe));
  const own = path.join(tuffApps, 'Keeps Files Test');
  check(!fs.existsSync(tuffApps), 'while the .exe\'s folder can be written to, nothing goes in TuffApps', tuffApps);
  r = runFrozen(keep.app, locked);
  const again = runFrozen(keep.app, locked);
  check(r.status === 0 && saidFrozen(r).startsWith('run 1,') && saidFrozen(again).startsWith('run 2,') && text(path.join(own, 'runs.json')) === '2'
    && text(path.join(own, 'notes.txt')) === 'packed line\nrun 1\nrun 2\n',
  'when the .exe\'s folder can\'t be written to, they go in TuffApps/<the app\'s name> in the user\'s data folder, and are read back',
  { first: r.stdout + r.stderr, again: again.stdout + again.stderr, own: fs.existsSync(own) && fs.readdirSync(own) });
  if (plain.app) {
    r = runFrozen(plain.app, path.join(scratch, 'Not There', 'Plain Pack Test.exe'));
    check(r.status === 0 && saidFrozen(r) === 'words next to it|and one in sprites' && !fs.existsSync(path.join(tuffApps, 'Plain Pack Test')),
      'an app that saves nothing makes no folder there', { stdout: r.stdout, stderr: r.stderr });
  }
  // On Windows, a folder that's there but that the user may not write in, as Program Files is. (1.5.0: the app hung
  // there before it started, its write check trying name after name.)
  if (process.platform === 'win32') {
    const denied = path.join(scratch, 'No Writing');
    fs.mkdirSync(denied, { recursive: true });
    const me = `${process.env.USERDOMAIN}\\${process.env.USERNAME}`;
    const lock = spawnSync('icacls', [denied, '/deny', `${me}:(OI)(CI)(WD,AD)`], { encoding: 'utf8', windowsHide: true });
    fs.rmSync(own, { recursive: true, force: true });
    const t0 = Date.now();
    r = runFrozen(keep.app, path.join(denied, path.basename(keep.app.exe)));
    const took = Date.now() - t0;
    spawnSync('icacls', [denied, '/remove:d', me], { encoding: 'utf8', windowsHide: true });
    check(lock.status === 0 && r.status === 0 && saidFrozen(r).startsWith('run 1,') && text(path.join(own, 'runs.json')) === '1' && took < 20000,
      `in a folder that's there but can't be written in (like Program Files) it starts straight away (${(took / 1000).toFixed(1)} s) and saves in TuffApps`,
      { lock: lock.stdout + lock.stderr, status: r.status, error: r.error?.message, out: r.stdout + r.stderr });
  }
}
// Not built (TuffCode's Run): the program's files stay next to it, as before.
const notBuilt = spawnSync(PY[0], [...PY.slice(1), path.join(APP_DIR, '..', 'tuff.py'), 'keeper.tuf'], { cwd: keepDir, env: userEnv, input: '', encoding: 'utf8', timeout: 30000, windowsHide: true });
check(notBuilt.status === 0 && said(notBuilt).endsWith('false false true') && text(path.join(keepDir, 'runs.json')) === '1'
  && text(path.join(keepDir, 'notes.txt')) === 'packed line\nrun 1\n' && !fs.existsSync(path.join(keepDir, 'prices.json')),
'not built, a program\'s files stay next to it (and file.delete deletes)', { stdout: notBuilt.stdout, stderr: notBuilt.stderr, files: fs.readdirSync(keepDir) });

// A project folder with PyInstaller's separator in its path (";", ":" on a Mac), from Open Folder or a folder chosen for
// New Project: --add-data can't name its files, so Build exe packs copies of them. The app's name drops it.
console.log(`== Build exe: a project folder with ${SEP} in its path`);
// How PyInstaller reads --add-data (makespec.py's SourceDestAction): at its one ":" or ";" (":" on a Mac) that isn't a
// drive's (C:\), and it refuses one with more.
const splitsOnce = (d) => [...d.matchAll(process.platform === 'win32' ? /(^\w:[/\\])|[:;]/g : /(^\w:[/\\])|:/g)].filter((m) => !m[1]).length === 1;
const semiDir = path.join(scratch, `Shop${SEP} Cafe`);
write(path.join(semiDir, 'money.tuf'), 'func as_money(x):\n    return f"{x:money}"\n');
write(path.join(semiDir, 'words.txt'), 'words next to it');
write(path.join(semiDir, 'data', 'info.txt'), 'and one in data');
write(path.join(semiDir, 'shop.tuf'), 'import money.tuf\nsay money.as_money(1.5)\nsay file.read("words.txt")\nsay file.read("data/info.txt")\n');
const semi = await buildApp(path.join(semiDir, 'shop.tuf'), `Shop${SEP} Cafe`);
check(semi.ok && semi.app, 'it builds', semi.message);
if (semi.app) {
  check(semi.app.data.every(splitsOnce), `every --add-data has one ${SEP}, so PyInstaller can read it`, semi.app.data);
  check(path.basename(semi.app.exe) === `Shop Cafe${process.platform === 'win32' ? '.exe' : ''}` && !semi.app.data.some((d) => d.includes(`Shop${SEP}`)),
    `the app is called Shop Cafe, and it packs copies of the project's files`, { exe: semi.app.exe, data: semi.app.data });
  check(['program.tuf', 'money.tuf', 'words.txt', 'data/info.txt'].every((f) => inApp(semi.app, f)) && !inApp(semi.app, 'packed'),
    'they\'re where they belong in the app: money.tuf beside the program, data/info.txt in data', fs.readdirSync(semi.app.bundle));
  const r = runApp(semi.app);
  check(r.status === 0 && said(r) === '$1.50|words next to it|and one in data', 'and the program runs in the app, with all three', { status: r.status, stdout: r.stdout, stderr: r.stderr });
}
// With a file from the folder above too, the program's own folder in the app (_project/Shop; Cafe) has the separator.
write(path.join(scratch, 'Semi Up', 'shared.txt'), 'from the folder above');
write(path.join(scratch, 'Semi Up', `Shop${SEP} Cafe`, 'up.tuf'), 'say file.read("../shared.txt")\n');
const semiUp = await buildApp(path.join(scratch, 'Semi Up', `Shop${SEP} Cafe`, 'up.tuf'), 'Semi Up Test');
if (semiUp.app) {
  const r = runApp(semiUp.app);
  check(semiUp.app.data.every(splitsOnce) && inApp(semiUp.app, `_project/Shop${SEP} Cafe/program.tuf`) && inApp(semiUp.app, '_project/shared.txt')
    && r.status === 0 && said(r) === 'from the folder above', `with a "../" file, the program goes in _project/Shop${SEP} Cafe and finds it there`,
  { data: semiUp.app.data, stdout: r.stdout, stderr: r.stderr });
} else check(false, 'the program with a "../" file builds', semiUp.message);

// 1.5.0: a program in several files (import money.tuf). The files it imports go in the app beside it, in the folders they're
// in (libs/ too), and only those: a .tuf file it doesn't import stays out.
console.log('== Build exe: a program that imports its own files');
const modsDir = path.join(scratch, 'Own Files');
write(path.join(modsDir, 'shop.tuf'), 'import money.tuf\nimport fmt.tuf\nsay money.as_money(6.375)\nsay fmt.stars(3)\nsay money.half("a")\n');
write(path.join(modsDir, 'money.tuf'), 'import tax.tuf\nfunc as_money(x):\n    return f"{tax.add(x):money}"\nfunc half(n):\n    return n / 2\n');
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
