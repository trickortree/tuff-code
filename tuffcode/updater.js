const { app, net } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const { spawn } = require('child_process');

const REPO = 'trickortree/tuff-code';
const ROOT = path.join(__dirname, '..');
const SKIP = new Set(['.git', 'node_modules', 'dist', '__pycache__', '.idea']);
const HOUR = 60 * 60 * 1000;
const INTERVALS = [1, 2, 4, 8];

let emit = () => {};
let state = { status: 'idle', latest: null, ready: null, error: null };
let timer = null;

const version = () => app.getVersion();
const isGitCheckout = () => !app.isPackaged && fs.existsSync(path.join(ROOT, '.git'));

function parseVersion(v) {
  return String(v || '').replace(/^v/i, '').split(/[.+-]/).slice(0, 3).map((n) => parseInt(n, 10) || 0);
}

function newer(a, b) {
  const x = parseVersion(a), y = parseVersion(b);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
}

function set(patch) {
  state = { ...state, ...patch };
  emit({ ...state, current: version(), git: isGitCheckout() });
}

async function github(url) {
  const res = await net.fetch(url, { headers: { 'User-Agent': `TuffCode/${version()}`, Accept: 'application/vnd.github+json' } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub answered ${res.status}`);
  return res.json();
}

async function findLatest() {
  const rel = await github(`https://api.github.com/repos/${REPO}/releases/latest`);
  if (rel && rel.tag_name) {
    return { version: rel.tag_name.replace(/^v/i, ''), zip: rel.zipball_url, notes: rel.body || '', url: rel.html_url };
  }
  const tags = await github(`https://api.github.com/repos/${REPO}/tags`);
  if (Array.isArray(tags) && tags.length) {
    const best = tags.filter((t) => /^v?\d+\.\d+\.\d+/.test(t.name)).sort((a, b) => (newer(a.name, b.name) ? -1 : 1))[0];
    if (best) return { version: best.name.replace(/^v/i, ''), zip: best.zipball_url, notes: '', url: `https://github.com/${REPO}/releases` };
  }
  return null;
}

function run(cmd, args, cwd) {
  return new Promise((resolve) => {
    let out = '';
    let proc;
    try {
      proc = spawn(cmd, args, { cwd, windowsHide: true, shell: process.platform === 'win32' && /\.cmd$/i.test(cmd) });
    } catch (err) {
      resolve({ code: -1, out: String(err.message) });
      return;
    }
    proc.stdout.on('data', (d) => (out += d));
    proc.stderr.on('data', (d) => (out += d));
    proc.on('error', (err) => resolve({ code: -1, out: out + err.message }));
    proc.on('close', (code) => resolve({ code, out }));
  });
}

async function copyTree(from, to) {
  for (const entry of await fsp.readdir(from, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) {
      await fsp.mkdir(dst, { recursive: true });
      await copyTree(src, dst);
    } else {
      await fsp.copyFile(src, dst);
    }
  }
}

function findNpm() {
  const candidates = [
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'nodejs', 'npm.cmd'),
    path.join(process.env.ProgramFiles || '', 'nodejs', 'npm.cmd'),
  ];
  return candidates.find((p) => fs.existsSync(p)) || (process.platform === 'win32' ? 'npm.cmd' : 'npm');
}

async function installFromZip(latest) {
  const work = path.join(app.getPath('temp'), 'tuffcode-update', String(Date.now()));
  await fsp.mkdir(work, { recursive: true });
  const zip = path.join(work, 'update.zip');
  set({ status: 'downloading' });
  const res = await net.fetch(latest.zip, { headers: { 'User-Agent': `TuffCode/${version()}` } });
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  await fsp.writeFile(zip, Buffer.from(await res.arrayBuffer()));

  set({ status: 'installing' });
  const out = path.join(work, 'files');
  await fsp.mkdir(out, { recursive: true });
  const tar = process.platform === 'win32' ? path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe') : 'unzip';
  const unpack = process.platform === 'win32' ? await run(tar, ['-xf', zip, '-C', out]) : await run('unzip', ['-q', zip, '-d', out]);
  if (unpack.code !== 0) throw new Error(`Couldn't unpack the update: ${unpack.out.trim()}`);
  const [top] = await fsp.readdir(out);
  const source = path.join(out, top);
  if (!fs.existsSync(path.join(source, 'tuffcode', 'package.json')) || !fs.existsSync(path.join(source, 'tuff.py'))) {
    throw new Error('The downloaded update looks incomplete, so nothing was changed.');
  }

  const oldPkg = JSON.parse(await fsp.readFile(path.join(__dirname, 'package.json'), 'utf8'));
  const newPkg = JSON.parse(await fsp.readFile(path.join(source, 'tuffcode', 'package.json'), 'utf8'));
  await copyTree(source, ROOT);
  const depsChanged = JSON.stringify(oldPkg.dependencies || {}) !== JSON.stringify(newPkg.dependencies || {})
    || JSON.stringify(oldPkg.devDependencies || {}) !== JSON.stringify(newPkg.devDependencies || {});
  if (depsChanged) {
    set({ status: 'installing', detail: 'Installing new parts…' });
    const npm = await run(findNpm(), ['install', '--no-fund', '--no-audit'], __dirname);
    if (npm.code !== 0) throw new Error('The update needs new parts, but npm couldn\'t install them. Install Node.js, then try again.');
  }
  fsp.rm(work, { recursive: true, force: true }).catch(() => {});
}

function findGit() {
  const candidates = [
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'PortableGit', 'cmd', 'git.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Git', 'cmd', 'git.exe'),
    path.join(process.env.ProgramFiles || '', 'Git', 'cmd', 'git.exe'),
  ];
  return candidates.find((p) => fs.existsSync(p)) || 'git';
}

async function installWithGit() {
  set({ status: 'installing', detail: 'Pulling with git…' });
  const git = findGit();
  const status = await run(git, ['status', '--porcelain', '--untracked-files=no'], ROOT);
  if (status.code !== 0) throw new Error('This copy of TuffCode is a git checkout, but git isn\'t available. Update it with git pull.');
  if (status.out.trim()) throw new Error('This is a git checkout with unsaved changes, so TuffCode won\'t touch it. Commit or stash, then update with git pull.');
  const pull = await run(git, ['pull', '--ff-only'], ROOT);
  if (pull.code !== 0) throw new Error(`git pull didn't work: ${pull.out.trim().split('\n').pop()}`);
}

// ---------------------------------------------------------------- installed copies: electron-updater
let au = null;
let auSilent = false;
let auAutoInstall = false;

function installer() {
  if (au) return au;
  const { autoUpdater } = require('electron-updater');
  au = autoUpdater;
  au.autoDownload = false;
  au.autoInstallOnAppQuit = true;
  au.on('update-available', (info) => {
    set({ status: 'available', latest: { version: info.version, url: `https://github.com/${REPO}/releases/tag/v${info.version}` } });
    if (auAutoInstall) install();
  });
  au.on('update-not-available', () => set({ status: state.ready ? 'ready' : 'up-to-date' }));
  au.on('download-progress', (p) => set({ status: 'downloading', detail: `${Math.round(p.percent)}%` }));
  au.on('update-downloaded', (info) => set({ status: 'ready', ready: info.version, detail: null }));
  au.on('error', (err) => {
    const msg = String(err?.message || err).split('\n')[0];
    set(auSilent && state.status === 'checking' ? { status: state.ready ? 'ready' : 'idle' } : { status: 'error', error: msg });
  });
  return au;
}

async function check({ silent = false, autoInstall = false } = {}) {
  if (['checking', 'downloading', 'installing'].includes(state.status)) return state;
  if (app.isPackaged) {
    auSilent = silent;
    auAutoInstall = autoInstall;
    set({ status: 'checking', error: null, detail: null });
    try {
      await installer().checkForUpdates();
    } catch (err) {
      set({ status: silent ? 'idle' : 'error', error: String(err?.message || err).split('\n')[0] });
    }
    return state;
  }
  set({ status: 'checking', error: null, detail: null });
  try {
    const latest = await findLatest();
    if (!latest || !newer(latest.version, version())) {
      set({ status: state.ready ? 'ready' : 'up-to-date', latest });
      return state;
    }
    set({ status: 'available', latest });
    if (autoInstall) await install();
  } catch (err) {
    set({ status: silent ? (state.ready ? 'ready' : 'idle') : 'error', error: String(err.message || err) });
  }
  return state;
}

async function install() {
  if (!state.latest || !newer(state.latest.version, version())) return state;
  if (app.isPackaged) {
    set({ status: 'downloading', detail: '0%' });
    try {
      await installer().downloadUpdate();
    } catch (err) {
      set({ status: 'error', error: String(err?.message || err).split('\n')[0] });
    }
    return state;
  }
  try {
    if (isGitCheckout()) await installWithGit();
    else await installFromZip(state.latest);
    set({ status: 'ready', ready: state.latest.version, detail: null });
  } catch (err) {
    set({ status: 'error', error: String(err.message || err), detail: null });
  }
  return state;
}

let readSettings = () => ({});

function hours() {
  const h = Number(readSettings().updateHours);
  return INTERVALS.includes(h) ? h : 2;
}

function background() {
  const s = readSettings();
  if (s.autoCheckUpdates !== false) check({ silent: true, autoInstall: s.autoUpdate !== false });
}

function reschedule() {
  clearInterval(timer);
  timer = setInterval(background, hours() * HOUR);
}

function start(sendEvent, getSettings) {
  emit = sendEvent;
  readSettings = getSettings;
  setTimeout(background, 15000);
  reschedule();
}

function restart() {
  if (app.isPackaged && au) {
    au.quitAndInstall(true, true);
    return;
  }
  app.relaunch();
  app.exit(0);
}

module.exports = { start, check, install, restart, reschedule, state:() => ({ ...state, current: version(), git: isGitCheckout() }) };
