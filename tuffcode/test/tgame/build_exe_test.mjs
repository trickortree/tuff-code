// Build exe for a tgame program, the way the IDE does it (tuffcode/build.js, with Electron's app and nativeImage
// stood in for), then run the built app: it has no console (--windowed), so it plays itself with tgame's autopilot
// and the test reads the screenshot and the JSON it writes.
//   node tuffcode/test/tgame/build_exe_test.mjs [--keep] [--only game,box,plain]
// Takes a few minutes (PyInstaller --onefile, three times). Exits 1 if a check failed.
//   game     features_2d.tuf builds, runs from inside the app and draws
//   box      on Windows: a game whose picture won't load, opened like a double-click in Explorer (no console, no
//            pipes), shows the window's error in the app's error box (error_box.py reads it and clicks OK)
//   plain    a program without tgame builds as a small console app
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import Module from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_DIR = path.resolve(HERE, '..', '..');
const require = createRequire(import.meta.url);
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'tgame-build-'));
const onlyArg = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] || '' : '';
const only = (name) => !onlyArg || onlyArg.split(',').includes(name);
const PY = process.platform === 'win32' ? ['py', '-3'] : ['python3'];
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
const load = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'electron') return electron;
  if (request === './shellpath') return { ready: async () => {} };
  return load.call(this, request, ...rest);
};
const build = require(path.join(APP_DIR, 'build.js'));

// Builds a program as the Build exe dialog does; gives back its done event (with the log and steps).
async function buildApp(file, name) {
  const events = [];
  const t0 = Date.now();
  await build.start({ file, name, root: path.dirname(file) }, (e) => {
    events.push(e);
    if (e.type === 'step' && e.state !== 'running') console.log(`  step ${e.id}: ${e.state} ${e.label}`);
  });
  const done = events.find((e) => e.type === 'done') || {};
  done.log = events.filter((e) => e.type === 'log').map((e) => e.text).join('\n');
  done.steps = events.filter((e) => e.type === 'step');
  done.took = Math.round((Date.now() - t0) / 1000);
  fs.writeFileSync(path.join(scratch, `${name}.build.log`), done.log);
  return done;
}

let done = {};
if (only('game')) {
  const project = path.join(scratch, 'My Game');
  fs.mkdirSync(project, { recursive: true });
  for (const f of ['features_2d.tuf', 'star.png', 'blip.wav']) fs.copyFileSync(path.join(HERE, 'games', f), path.join(project, f));
  console.log(`== Build exe: features_2d.tuf in ${project}`);
  done = await buildApp(path.join(project, 'features_2d.tuf'), 'Tgame Build Test');
  check(done.ok, `it built (${done.took} s)`, done.message || done.log.slice(-1500));
  check(done.windowed, 'a game builds windowed (no console)', done.windowed);
  const exe = done.exe;
  check(exe && fs.existsSync(exe), `the app is there: ${exe} (${done.size ? (done.size / 1048576).toFixed(1) : '?'} MB)`, exe);

  if (exe && fs.existsSync(exe)) {
    const out = path.join(scratch, 'out');
    fs.mkdirSync(out, { recursive: true });
    const plan = path.join(out, 'plan.json');
    fs.writeFileSync(plan, JSON.stringify({ on_top: true, out, timeout: 20, steps: [
      { at: 0.5, click_world: [100, 100] }, { at: 0.7, key: 'a' }, { at: 1.6, call: 'report' },
      { at: 1.7, shot: 'built.png' }, { at: 1.8, dump: 'built.json' }, { at: 2.0, close: true }] }));
    const t1 = Date.now();
    const r = spawnSync(exe, [], { cwd: scratch, env: { ...process.env, TUFF_TGAME_AUTOPILOT: plan }, timeout: 60000, windowsHide: false });
    check(r.status === 0, `the built game ran and closed by itself (exit ${r.status}, ${((Date.now() - t1) / 1000).toFixed(1)} s)`, r.error?.message);
    let state = {};
    try { state = JSON.parse(fs.readFileSync(path.join(out, 'built.json'), 'utf8')); } catch {}
    check((state.texts || []).includes('Features!'), 'it ran the program (its text sprite says "Features!")', state.texts);
    check((state.sprites || []).filter((s) => s[0] === 'image').length === 2, 'the star.png sprites loaded from inside the app', state.sprites);
    check(state.fps >= 30, `and drew frames (${state.fps} fps)`, state.fps);
    check(fs.existsSync(path.join(out, 'built.png')) && fs.statSync(path.join(out, 'built.png')).size > 3000, 'it took a screenshot', null);
    const shot = path.join(HERE, 'out', 'build_exe.png');
    fs.mkdirSync(path.dirname(shot), { recursive: true });
    if (fs.existsSync(path.join(out, 'built.png'))) fs.copyFileSync(path.join(out, 'built.png'), shot);
  }
}

// An error the game window finds (here a .png that isn't a picture) isn't a Tuff error with a line, and a built game
// has no console to print it to. Opened the way Explorer opens it (Start-Process: no console and no pipes, so the app
// can't print anywhere), it has to come up in the app's error box, and the game goes on once it's closed.
if (only('box') && process.platform === 'win32') {
  const project = path.join(scratch, 'Broken Picture');
  fs.mkdirSync(project, { recursive: true });
  fs.writeFileSync(path.join(project, 'broken.png'), 'this is not a picture\n');
  fs.writeFileSync(path.join(project, 'broken.tuf'), 'mention tgame\n\ngame = tgame.window("Broken picture", 400, 300)\n'
    + 'game:text("Still running", 200, 40)\npic = game:image("broken.png", 200, 150)\n');
  console.log(`== Build exe: a game with a broken picture, opened like a double-click`);
  const bad = await buildApp(path.join(project, 'broken.tuf'), 'Broken Picture Test');
  check(bad.ok && bad.windowed, `it built, windowed (${bad.took} s)`, bad.message || bad.log.slice(-1500));
  if (bad.ok && bad.exe) {
    const out = path.join(scratch, 'out-box');
    fs.mkdirSync(out, { recursive: true });
    const plan = path.join(out, 'plan.json');
    fs.writeFileSync(plan, JSON.stringify({ on_top: true, out, timeout: 40, steps: [{ at: 1.5, dump: 'after.json' }, { at: 2.0, close: true }] }));
    const q = (s) => `'${s.replace(/'/g, "''")}'`;
    // Start-Process opens it through the shell, as Explorer does; PowerShell waits for it and says how it ended.
    const ps = spawn('powershell', ['-NoProfile', '-NonInteractive', '-Command',
      `$p = Start-Process -FilePath ${q(bad.exe)} -WorkingDirectory ${q(scratch)} -PassThru; if ($p.WaitForExit(90000)) { 'exit ' + $p.ExitCode } else { 'still running' }`],
    { env: { ...process.env, TUFF_TGAME_AUTOPILOT: plan }, windowsHide: true });
    let psOut = '';
    ps.stdout.on('data', (d) => { psOut += d; });
    const ended = new Promise((r) => ps.on('close', r));
    const watcher = spawnSync(PY[0], [...PY.slice(1), path.join(HERE, 'error_box.py'), bad.exe, '45'], { encoding: 'utf8', timeout: 60000, windowsHide: true });
    let box = {};
    try { box = JSON.parse(watcher.stdout.trim().split('\n').pop()); } catch { box = { stdout: watcher.stdout, stderr: watcher.stderr }; }
    if (box.text) console.log(`  the box says: ${box.text.replace(/\n/g, ' / ')}`);
    check(box.found && box.title === 'Something went wrong', 'the app shows its error box ("Something went wrong")', box);
    check(/^Tuff error: The game window had a problem \(loading an image\): couldn't load the image 'broken\.png'/.test(box.text || ''),
      'it says the game window couldn\'t load broken.png, by its name', box.text);
    await ended;
    if (/still running/.test(psOut)) {
      // Only that .exe, by its full path (it's in this test's own temporary folder).
      spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command',
        `Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq ${q(bad.exe)} } | Invoke-CimMethod -MethodName Terminate | Out-Null`], { windowsHide: true });
    }
    check(/exit 0/.test(psOut), 'after OK the game goes on, and closes by itself', psOut.trim());
    let state = {};
    try { state = JSON.parse(fs.readFileSync(path.join(out, 'after.json'), 'utf8')); } catch {}
    check((state.texts || []).includes('Still running'), 'it kept running after the box (its text says "Still running")', state.texts);
  }
}

// A program without a game window doesn't carry the window engine: same size as before, and a console.
if (only('plain')) {
  const plain = path.join(scratch, 'Plain');
  fs.mkdirSync(plain, { recursive: true });
  fs.writeFileSync(path.join(plain, 'hello.tuf'), 'say "hello from a plain app"\n');
  const plainDone = await buildApp(path.join(plain, 'hello.tuf'), 'Plain Test');
  check(plainDone.ok && !plainDone.windowed, 'a program without tgame still builds as a console app', plainDone.message);
  check(plainDone.size && plainDone.size < 10 * 1048576, `without the window engine (${plainDone.size ? (plainDone.size / 1048576).toFixed(1) : '?'} MB, the game was ${done.size ? (done.size / 1048576).toFixed(1) : '?'} MB)`, plainDone.size);
  if (plainDone.exe) {
    const r = spawnSync(plainDone.exe, [], { input: '\n', encoding: 'utf8', timeout: 30000, windowsHide: true });
    check(r.stdout.startsWith('hello from a plain app'), 'and it runs, with no Tuff Engine line', r.stdout.slice(0, 200));
  }
}
console.log(`build_exe: ${passed} passed, ${failed} failed`);
if (process.argv.includes('--keep')) console.log(`kept ${scratch}`);
else fs.rmSync(scratch, { recursive: true, force: true });
process.exit(failed ? 1 : 0);
