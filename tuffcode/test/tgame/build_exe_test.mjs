// Build exe for a tgame program, the way the IDE does it (tuffcode/build.js, with Electron's app and nativeImage
// stood in for), then run the built app: it has no console (--windowed), so it plays itself with tgame's autopilot
// and the test reads the screenshot and the JSON it writes.
//   node tuffcode/test/tgame/build_exe_test.mjs [--keep]
// Takes a minute or two (PyInstaller --onefile). Exits 1 if a check failed.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import Module from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_DIR = path.resolve(HERE, '..', '..');
const require = createRequire(import.meta.url);
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'tgame-build-'));
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

const project = path.join(scratch, 'My Game');
fs.mkdirSync(project, { recursive: true });
for (const f of ['features_2d.tuf', 'star.png', 'blip.wav']) fs.copyFileSync(path.join(HERE, 'games', f), path.join(project, f));
const events = [];
const t0 = Date.now();
console.log(`== Build exe: features_2d.tuf in ${project}`);
await build.start({ file: path.join(project, 'features_2d.tuf'), name: 'Tgame Build Test', root: project }, (e) => {
  events.push(e);
  if (e.type === 'step' && e.state !== 'running') console.log(`  step ${e.id}: ${e.state} ${e.label}`);
});
const done = events.find((e) => e.type === 'done') || {};
const log = events.filter((e) => e.type === 'log').map((e) => e.text).join('\n');
fs.writeFileSync(path.join(scratch, 'build.log'), log);
check(done.ok, `it built (${Math.round((Date.now() - t0) / 1000)} s)`, done.message || log.slice(-1500));
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
// A program without a game window doesn't carry the window engine: same size as before, and a console.
const plain = path.join(scratch, 'Plain');
fs.mkdirSync(plain, { recursive: true });
fs.writeFileSync(path.join(plain, 'hello.tuf'), 'say "hello from a plain app"\n');
const plainEvents = [];
await build.start({ file: path.join(plain, 'hello.tuf'), name: 'Plain Test', root: plain }, (e) => plainEvents.push(e));
const plainDone = plainEvents.find((e) => e.type === 'done') || {};
check(plainDone.ok && !plainDone.windowed, 'a program without tgame still builds as a console app', plainDone.message);
check(plainDone.size && plainDone.size < 10 * 1048576, `without the window engine (${plainDone.size ? (plainDone.size / 1048576).toFixed(1) : '?'} MB, the game was ${done.size ? (done.size / 1048576).toFixed(1) : '?'} MB)`, plainDone.size);
if (plainDone.exe) {
  const r = spawnSync(plainDone.exe, [], { input: '\n', encoding: 'utf8', timeout: 30000, windowsHide: true });
  check(r.stdout.startsWith('hello from a plain app'), 'and it runs, with no Tuff Engine line', r.stdout.slice(0, 200));
}
console.log(`build_exe: ${passed} passed, ${failed} failed`);
if (process.argv.includes('--keep')) console.log(`kept ${scratch}`);
else fs.rmSync(scratch, { recursive: true, force: true });
process.exit(failed ? 1 : 0);
