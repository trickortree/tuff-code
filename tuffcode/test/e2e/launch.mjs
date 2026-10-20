// Starts TuffCode for the e2e tests without touching anything of yours: a throwaway --user-data-dir with its
// own settings.json, a scratch copy of a fixture project, the stand-in agent CLIs (fixtures/mock agents), a
// scratch home and temp folder, and a free DevTools port. Starts the source checkout (`electron .` in
// tuffcode/) or a packaged TuffCode binary.
//   As a library: const app = await launch({ name, project, app, env }); ... await app.stop();
//   By hand, to poke at it: node test/e2e/launch.mjs [--project project2] [--app <TuffCode binary>]
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const E2E = path.dirname(fileURLToPath(import.meta.url));
export const APP_DIR = path.resolve(E2E, '..', '..'); // tuffcode/
export const REPO = path.resolve(APP_DIR, '..');
export const FIXTURES = path.join(E2E, 'fixtures');
export const MOCKS = path.join(FIXTURES, 'mock agents');
export const OUT = path.join(E2E, 'out');
const WIN = process.platform === 'win32';

// Keep drawing while the window is covered or in the background: Chromium otherwise pauses a hidden
// window's animations and timers, and the suites wait on both.
const FLAGS = ['--disable-features=CalculateNativeWinOcclusion', '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'];

export function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => { const { port } = srv.address(); srv.close(() => resolve(port)); });
  });
}

export const electronBinary = () => createRequire(path.join(APP_DIR, 'package.json'))('electron');
export const mockBin = (who) => path.join(MOCKS, WIN ? `${who}.cmd` : who);

const rmScratch = async (dir) => {
  // Windows can hold on to files for a moment after the app exits.
  for (let i = 0; i < 20; i++) {
    try { fs.rmSync(dir, { recursive: true, force: true }); return true; } catch { await new Promise((r) => setTimeout(r, 300)); }
  }
  return false;
};

// name: the out folder (test/e2e/out/<name>). project: a folder in fixtures/. app: a packaged TuffCode binary
// (default: the source checkout). mocks: false starts it with the real agents and your real home folder (manual
// tests only). env: more environment variables for the app (and the agents it starts).
export async function launch({ name = 'manual', project = 'project', app = null, mocks = true, env = {}, args = [], keep = false } = {}) {
  // realpath: the agents report their working folder that way (/private/var on a Mac, no 8.3 names on Windows).
  const scratch = fs.realpathSync.native(fs.mkdtempSync(path.join(os.tmpdir(), `tuffcode-e2e-${name}-`)));
  const root = path.join(scratch, project);
  fs.cpSync(path.join(FIXTURES, project), root, { recursive: true });
  const userData = path.join(scratch, 'user-data');
  const home = path.join(scratch, 'home');
  const tmp = path.join(scratch, 'tmp');
  for (const d of [userData, home, tmp]) fs.mkdirSync(d, { recursive: true });
  const out = path.join(OUT, name);
  fs.rmSync(out, { recursive: true, force: true });
  const agents = path.join(out, 'agents');
  fs.mkdirSync(agents, { recursive: true });
  const settingsFile = path.join(userData, 'settings.json');
  fs.writeFileSync(settingsFile, JSON.stringify({ introSeen: true, autoCheckUpdates: false, autoUpdate: false, lastFolder: root }, null, 2));

  const exe = app ? path.resolve(app) : electronBinary();
  const port = await freePort();
  const childEnv = { ...process.env, TEMP: tmp, TMP: tmp, TMPDIR: tmp };
  delete childEnv.ELECTRON_RUN_AS_NODE; // would start Electron as plain Node, with no window
  if (mocks) {
    Object.assign(childEnv, {
      // A scratch home, so nothing the IDE does can reach ~/.claude.json, ~/.codex or ~/.gemini.
      [WIN ? 'USERPROFILE' : 'HOME']: home,
      TUFFCODE_CLAUDE_BIN: mockBin('claude'),
      TUFFCODE_CODEX_BIN: mockBin('codex'),
      TUFFCODE_ANTIGRAVITY_BIN: mockBin('agy'),
      TUFFCODE_CLAUDE_APP_CONFIG: path.join(agents, 'claude_desktop_config.json'),
      MOCK_AGENT_OUT: agents,
      MOCK_NODE: process.execPath,
    });
    if (!WIN) for (const who of ['claude', 'codex', 'agy']) fs.chmodSync(mockBin(who), 0o755);
  }
  Object.assign(childEnv, env);

  const log = fs.openSync(path.join(out, 'app.log'), 'a');
  const argv = [...(app ? [] : ['.']), `--user-data-dir=${userData}`, `--remote-debugging-port=${port}`, ...FLAGS, ...args];
  // On a Mac the app gets its own process group, so stop() ends everything it started.
  const proc = spawn(exe, argv, { cwd: app ? scratch : APP_DIR, env: childEnv, stdio: ['ignore', log, log], detached: !WIN });
  const exited = new Promise((r) => proc.once('exit', r));
  proc.once('error', (err) => fs.appendFileSync(path.join(out, 'app.log'), `\n[launch] couldn't start ${exe}: ${err.message}\n`));

  const alive = () => proc.exitCode === null && proc.signalCode === null;
  async function stop() {
    // Only the process this launch started, and everything under it.
    if (alive()) {
      if (WIN) spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { windowsHide: true });
      else { try { process.kill(-proc.pid, 'SIGTERM'); } catch {} }
      await Promise.race([exited, new Promise((r) => setTimeout(r, 5000))]);
      if (alive() && !WIN) { try { process.kill(-proc.pid, 'SIGKILL'); } catch {} }
    }
    try { fs.closeSync(log); } catch {}
    if (!keep) await rmScratch(scratch);
  }
  return { name, exe, packaged: !!app, port, pid: proc.pid, proc, alive, scratch, root, userData, settingsFile, home, tmp, out, agents, stop };
}

let pythonCmd;
// The Python that runs tuff.py here: py -3 on Windows, python3 elsewhere (python as a fallback). null: none.
export function python() {
  if (pythonCmd === undefined) {
    const tries = WIN ? [['py', '-3'], ['python']] : [['python3'], ['python']];
    pythonCmd = tries.find(([cmd, ...a]) => spawnSync(cmd, [...a, '--version'], { windowsHide: true }).status === 0) || null;
  }
  return pythonCmd;
}

// What a suite gets besides the driver: where everything is, and a few helpers.
export function context(app) {
  const resources = process.platform === 'darwin' ? path.join(path.dirname(app.exe), '..', 'Resources') : path.join(path.dirname(app.exe), 'resources');
  const runtime = path.join(resources, 'runtime', WIN ? 'tuff-runtime.exe' : 'tuff-runtime');
  const norm = (p) => { const r = path.resolve(String(p || '')); return WIN ? r.toLowerCase() : r; };
  return {
    platform: process.platform,
    win: WIN,
    ci: !!process.env.CI,
    packaged: app.packaged,
    exe: app.exe, // what TuffCode reports as its own executable (process.execPath)
    pid: app.pid,
    root: app.root, // the scratch project the IDE has open
    fixtures: FIXTURES,
    mocks: MOCKS,
    agents: app.agents, // the stand-ins' logs, .connected markers and the Claude app's settings file
    out: app.out,
    settingsFile: app.settingsFile,
    tmp: app.tmp, // the app's temp folder
    appDir: APP_DIR,
    samePath: (a, b) => norm(a) === norm(b),
    readLog: (who) => { try { return fs.readFileSync(path.join(app.agents, `${who}.log`), 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)); } catch { return []; } },
    // tuff --check on a file, with the packaged app's own runtime or else Python + the checkout's tuff.py.
    tuffCheck(file) {
      const cmd = app.packaged && fs.existsSync(runtime) ? [runtime] : python() ? [...python(), path.join(REPO, 'tuff.py')] : null;
      if (!cmd) return 'No Python found to run tuff.py';
      const r = spawnSync(cmd[0], [...cmd.slice(1), '--check', file], { encoding: 'utf8', windowsHide: true });
      return `${r.stdout || ''}${r.stderr || ''}${r.error ? r.error.message : ''}`;
    },
    // CPU time the app's main process has used so far, in ms.
    cpuMs() {
      if (WIN) {
        const r = spawnSync('powershell', ['-NoProfile', '-Command', `(Get-Process -Id ${app.pid}).TotalProcessorTime.TotalMilliseconds`], { encoding: 'utf8', windowsHide: true });
        return Number(r.stdout.trim());
      }
      const s = spawnSync('ps', ['-o', 'time=', '-p', String(app.pid)], { encoding: 'utf8' }).stdout.trim(); // [[dd-]hh:]mm:ss.cc
      const [days, rest] = s.includes('-') ? s.split('-') : ['0', s];
      return (Number(days) * 86400 + rest.split(':').reduce((acc, x) => acc * 60 + Number(x), 0)) * 1000;
    },
  };
}

// node test/e2e/launch.mjs [--project <fixture>] [--app <binary>]: start one and leave it running.
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const opt = (n) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : null; };
  const app = await launch({ name: 'manual', project: opt('--project') || 'project', app: opt('--app'), keep: true });
  console.log(`TuffCode is starting: DevTools port ${app.port}, pid ${app.pid}`);
  console.log(`project ${app.root}\nsettings ${app.settingsFile}\nlog ${path.join(app.out, 'app.log')}`);
  console.log('Press Ctrl+C to stop it (the scratch folder is kept).');
  const quit = async () => { await app.stop(); process.exit(0); };
  process.on('SIGINT', quit);
  process.on('SIGTERM', quit);
  app.proc.on('exit', () => process.exit(0));
}
