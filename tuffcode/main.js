const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const { spawn } = require('child_process');
const shellPath = require('./shellpath');

// On a Mac, read the login shell's PATH in the background (see shellpath.js).
shellPath.start();
const builder = require('./build');
const updater = require('./updater');
const plugins = require('./plugins');
const agents = require('./agents');
const ai = require('./ai');

const TUFF_INTERPRETER = app.isPackaged
  ? path.join(process.resourcesPath, 'runtime-src', 'tuff.py')
  : path.join(__dirname, '..', 'tuff.py');
const SKIP_DIRS = new Set(['node_modules', '.git', '__pycache__', '.venv', 'venv']);

let win;
let runProc = null;

const settingsPath = () => path.join(app.getPath('userData'), 'settings.json');

function loadSettings() {
  try {
    return JSON.parse(fs.readFileSync(settingsPath(), 'utf8'));
  } catch {
    return {};
  }
}

function saveSettings(patch) {
  const next = { ...loadSettings(), ...patch };
  fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(next, null, 2));
  return next;
}

const SAMPLE_MAIN = `# Welcome to Tuff!
# Press Shift+F10 (or the green play button) to run this file.
# New here? Open the Learn panel (graduation cap on the left).

name = "world"
say "Hello, " + name + "!"

say name

line = say name
wait(1)  # pause so you can watch the line change
line:rewrite say name + " is that you?"

answer = input "is it? "

func dop(value1):
    value1 = true

if answer is "yes":
    say "he said yes!"
    if dop(true) then # 'then' works anywhere ':' does
        print("yes AGAIN")
`;

async function ensureDefaultProject() {
  const dir = path.join(app.getPath('documents'), 'TuffProjects', 'HelloTuff');
  const main = path.join(dir, 'main.tuf');
  await fsp.mkdir(dir, { recursive: true });
  if (!fs.existsSync(main)) await fsp.writeFile(main, SAMPLE_MAIN, 'utf8');
  return dir;
}

async function readDir(dir) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  return entries
    .map((e) => ({ name: e.name, path: path.join(dir, e.name), isDir: e.isDirectory() }))
    .sort((a, b) => (a.isDir === b.isDir ? a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }) : a.isDir ? -1 : 1));
}

async function listAllFiles(root, limit = 5000) {
  const out = [];
  const walk = async (dir) => {
    if (out.length >= limit) return;
    let entries;
    try {
      entries = await fsp.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (out.length >= limit) return;
      const p = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (!SKIP_DIRS.has(e.name)) await walk(p);
      } else {
        out.push({ name: e.name, path: p, rel: path.relative(root, p) });
      }
    }
  };
  await walk(root);
  return out;
}

const RUNTIME_EXE = path.join(process.resourcesPath || '', 'runtime', process.platform === 'win32' ? 'tuff-runtime.exe' : 'tuff-runtime');

// Installed copies run Tuff with the bundled runtime; source checkouts use Python + tuff.py.
function tuffCommand(extra) {
  if (app.isPackaged && fs.existsSync(RUNTIME_EXE)) return { cmd: RUNTIME_EXE, args: extra };
  const py = process.platform === 'win32' ? { cmd: 'py', args: ['-3', '-u'] } : { cmd: 'python3', args: ['-u'] };
  return { cmd: py.cmd, args: [...py.args, TUFF_INTERPRETER, ...extra] };
}

function send(channel, payload) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
}

function startRun(file, id) {
  if (runProc) runProc.kill();
  const { cmd, args: fullArgs } = tuffCommand([file]);
  const out = (stream, text) => send('run:data', { id, stream, text });
  out('cmd', `${cmd} ${fullArgs.map((a) => (a.includes(' ') ? `"${a}"` : a)).join(' ')}\n`);
  const proc = spawn(cmd, fullArgs, {
    cwd: path.dirname(file),
    windowsHide: true,
    env: { ...process.env, TUFF_IDE: '1', PYTHONIOENCODING: 'utf-8' },
  });
  runProc = proc;
  proc.stdout.setEncoding('utf8');
  proc.stderr.setEncoding('utf8');
  proc.stdout.on('data', (d) => out('stdout', d));
  proc.stderr.on('data', (d) => out('stderr', d));
  proc.stdin.on('error', () => {});
  proc.on('error', (err) => out('stderr', app.isPackaged
    ? `Could not start the Tuff runtime (${err.message}). Try reinstalling TuffCode.\n`
    : `Could not start Python (${err.message}). Is Python installed?\n`));
  proc.on('close', (code, signal) => {
    if (runProc === proc) runProc = null;
    send('run:exit', { id, code: code ?? (signal ? -1 : 0) });
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1400,
    height: 880,
    minWidth: 900,
    minHeight: 560,
    // Our own title bar everywhere; on a Mac it keeps the real traffic-light buttons.
    ...(process.platform === 'darwin' ? { titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 14, y: 14 } } : { frame: false }),
    show: false,
    backgroundColor: '#05060a',
    icon: path.join(__dirname, 'renderer', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.once('ready-to-show', () => win.show());
  win.on('maximize', () => send('window:maximized', true));
  win.on('unmaximize', () => send('window:maximized', false));
  win.on('blur', () => {
    send('window:blur');
    if (process.platform === 'win32') stopWatching();
  });
  win.on('focus', () => {
    if (process.platform !== 'win32' || !watchedDir) return;
    startWatching();
    send('fs:changed', { root: watchedDir, paths: [], overflow: true }); // catch up on what changed meanwhile
  });
  win.on('enter-full-screen', () => send('window:fullscreen', true));
  win.on('leave-full-screen', () => send('window:fullscreen', false));
}

ipcMain.handle('settings:get', () => loadSettings());
ipcMain.handle('settings:set', (_e, patch) => saveSettings(patch));

ipcMain.handle('project:default', () => ensureDefaultProject());
ipcMain.handle('fs:readDir', (_e, dir) => readDir(dir));
ipcMain.handle('fs:listAll', (_e, root) => listAllFiles(root));
ipcMain.handle('fs:readFile', (_e, p) => fsp.readFile(p, 'utf8'));
ipcMain.handle('fs:writeFile', (_e, p, content) => fsp.writeFile(p, content, 'utf8'));
ipcMain.handle('fs:exists', (_e, p) => fs.existsSync(p));
// Last-moment save while the window closes (Cmd+Q, the Mac's red button, logging out): it has to be
// synchronous, because the page is gone right after.
ipcMain.on('fs:writeFilesSync', (e, files) => {
  for (const f of files || []) { try { fs.writeFileSync(f.path, f.content, 'utf8'); } catch {} }
  e.returnValue = true;
});

// Watches the open folder, so files made, changed or deleted outside the editor (by an AI agent,
// Explorer/Finder, a build) show up in the project tree right away. Changes go out in batches at
// most 150 ms apart. On Windows a recursive watch keeps the folder's parents from being renamed or
// moved, so it only runs while TuffCode has focus and catches up when you come back.
let watcher = null;
let watchedDir = null;
let watchTimer = null;
let watchOverflow = false;
const watchChanged = new Set();
const WATCH_SKIP = /(^|[\/])(\.git|node_modules|__pycache__|\.DS_Store)([\/]|$)/;
function stopWatching() {
  try { watcher?.close(); } catch {}
  watcher = null;
  clearTimeout(watchTimer);
  watchTimer = null;
  watchChanged.clear();
  watchOverflow = false;
}
function flushWatch() {
  watchTimer = null;
  const paths = [...watchChanged];
  const overflow = watchOverflow;
  watchChanged.clear();
  watchOverflow = false;
  send('fs:changed', { root: watchedDir, paths, overflow });
}
function startWatching() {
  stopWatching();
  const dir = watchedDir;
  if (!dir || !fs.existsSync(dir)) return false;
  if (process.platform === 'win32' && win && !win.isDestroyed() && !win.isFocused()) return true;
  try {
    watcher = fs.watch(dir, { recursive: true }, (_type, name) => {
      const n = name == null ? '' : String(name);
      // The folder itself was deleted or moved: stop instead of erroring on every event.
      if ((n && path.isAbsolute(n)) || !fs.existsSync(dir)) {
        stopWatching();
        send('fs:changed', { root: dir, paths: [dir], gone: true });
        return;
      }
      if (n && WATCH_SKIP.test(n)) return;
      if (n) watchChanged.add(path.join(dir, n));
      else watchOverflow = true; // too many changes at once: the OS didn't say which
      if (!watchTimer) watchTimer = setTimeout(flushWatch, 150);
    });
    watcher.on('error', () => stopWatching());
    return true;
  } catch {
    return false;
  }
}
function watchFolder(dir) {
  watchedDir = dir || null;
  return startWatching();
}
ipcMain.handle('fs:watch', (_e, dir) => watchFolder(dir));
ipcMain.handle('fs:createFile', async (_e, p) => {
  if (fs.existsSync(p)) throw new Error(`${path.basename(p)} already exists`);
  await fsp.writeFile(p, '', 'utf8');
});
ipcMain.handle('fs:createDir', async (_e, p) => {
  if (fs.existsSync(p)) throw new Error(`${path.basename(p)} already exists`);
  await fsp.mkdir(p);
});
ipcMain.handle('fs:rename', async (_e, from, to) => {
  if (fs.existsSync(to)) throw new Error(`${path.basename(to)} already exists`);
  await fsp.rename(from, to);
});
ipcMain.handle('fs:trash', (_e, p) => shell.trashItem(p));

// Find in Files: every match of a pattern in the project's text files.
const NOT_TEXT = /\.(png|jpe?g|gif|ico|bmp|webp|exe|dll|zip|7z|rar|pdf|mp3|wav|ogg|mp4|woff2?|ttf|otf|pyc|asar)$/i;
ipcMain.handle('fs:search', async (_e, root, source, flags) => {
  const re = new RegExp(source, flags.includes('g') ? flags : `${flags}g`);
  const results = [];
  let total = 0;
  for (const f of await listAllFiles(root)) {
    if (NOT_TEXT.test(f.name)) continue;
    let text;
    try {
      if ((await fsp.stat(f.path)).size > 1_000_000) continue;
      text = await fsp.readFile(f.path, 'utf8');
    } catch { continue; }
    if (text.includes('\u0000')) continue;
    const matches = [];
    text.split(/\r?\n/).forEach((line, i) => {
      re.lastIndex = 0;
      let m;
      while (total < 2000 && (m = re.exec(line))) {
        if (!m[0]) { re.lastIndex++; continue; }
        matches.push({ line: i + 1, col: m.index + 1, len: m[0].length, preview: line.slice(0, 300) });
        total++;
      }
    });
    if (matches.length) results.push({ path: f.path, rel: f.rel, matches });
    if (total >= 2000) return { results, total, truncated: true };
  }
  return { results, total, truncated: false };
});
ipcMain.handle('fs:replaceInFile', async (_e, file, source, flags, replacement, isRegex) => {
  const text = await fsp.readFile(file, 'utf8');
  const next = text.replace(new RegExp(source, flags.includes('g') ? flags : `${flags}g`), isRegex ? replacement : () => replacement);
  if (next !== text) await fsp.writeFile(file, next, 'utf8');
  return next !== text;
});
ipcMain.handle('shell:reveal', (_e, p) => shell.showItemInFolder(p));

// Since Electron 43 the dialog opens in Downloads unless it's told where. It starts where the last
// project was picked from (the folder it's in), which is what Windows and macOS used to remember.
ipcMain.handle('dialog:openFolder', async () => {
  const last = loadSettings().lastFolder;
  const from = typeof last === 'string' && last && fs.existsSync(path.dirname(last)) ? path.dirname(last) : app.getPath('home');
  const res = await dialog.showOpenDialog(win, { defaultPath: from, properties: ['openDirectory'] });
  return res.canceled ? null : res.filePaths[0];
});

ipcMain.handle('run:start', (_e, file, id) => startRun(file, id));
ipcMain.handle('run:input', (_e, text) => {
  if (runProc && runProc.stdin.writable) runProc.stdin.write(text);
});
ipcMain.handle('run:stop', () => {
  if (runProc) runProc.kill();
});

let building = false;
ipcMain.handle('build:start', async (_e, opts) => {
  if (building) return;
  building = true;
  await builder.start(opts, (event) => send('build:event', event));
  building = false;
});
ipcMain.handle('build:cancel', () => builder.cancel());
ipcMain.handle('build:iconPreview', (_e, file) => builder.iconPreview(file));
ipcMain.handle('dialog:openImage', async (_e, defaultPath) => {
  const res = await dialog.showOpenDialog(win, {
    title: 'Choose an app icon',
    defaultPath,
    properties: ['openFile'],
    filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'ico'] }],
  });
  return res.canceled ? null : res.filePaths[0];
});
ipcMain.handle('shell:openPath', (_e, p) => shell.openPath(p));
ipcMain.handle('shell:openExternal', (_e, url) => {
  // Only TuffCode's repo and the sites of the agents Tuff Agents can run.
  if (/^https:\/\/(github\.com\/trickortree\/tuff-code\b|code\.claude\.com\/|developers\.openai\.com\/codex|antigravity\.google\b)/.test(url)) shell.openExternal(url);
});

ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('update:state', () => updater.state());
ipcMain.handle('update:check', () => updater.check());
ipcMain.handle('update:install', () => updater.install());
ipcMain.handle('update:restart', () => updater.restart());
ipcMain.handle('update:reschedule', () => updater.reschedule());

// Checks Tuff source with tuff.py --check. Used by live error checking and by Tuff AI.
async function checkSource(source) {
  const dir = path.join(app.getPath('temp'), 'tuffcode-check');
  await fsp.mkdir(dir, { recursive: true });
  const file = path.join(dir, `check-${process.pid}-${Date.now()}.tuf`);
  await fsp.writeFile(file, source, 'utf8');
  const { cmd, args } = tuffCommand(['--check', file]);
  const result = await new Promise((resolve) => {
    let out = '';
    const proc = spawn(cmd, args, { windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
    proc.stdout.on('data', (d) => (out += d));
    proc.stderr.on('data', (d) => (out += d));
    proc.on('error', () => resolve({ ok: true, unknown: true, message: '' }));
    proc.on('close', (code) => {
      // "Tuff error on line 3: ...", then "  3 | code" and a caret under the column.
      const lines = out.split(/\r?\n/);
      const i = lines.findIndex((l) => /^Tuff error/.test(l));
      const m = i >= 0 ? lines[i].match(/^Tuff error on line (\d+): (.*)$/) : null;
      const codeLine = lines[i + 1] || '';
      const caret = (lines[i + 2] || '').indexOf('^');
      const prefix = (codeLine.match(/^\s*\d+ \| /) || [''])[0].length;
      resolve({ ok: code === 0, message: i >= 0 ? lines[i] : '', line: m ? Number(m[1]) : null, col: caret >= prefix ? caret - prefix + 1 : 1, text: m ? m[2] : '' });
    });
  });
  fsp.rm(file, { force: true }).catch(() => {});
  return result;
}
ipcMain.handle('tuff:check', (_e, source) => checkSource(source));

// plugins and Tuff Agents
plugins.setup({ load: loadSettings, save: saveSettings });
agents.setup({ tuffCommand: () => { const { cmd, args } = tuffCommand([]); return [cmd, ...args]; } });
ipcMain.handle('plugins:list', (_e, force) => plugins.list(force));
ipcMain.handle('plugins:install', (_e, id) => plugins.install(id));
ipcMain.handle('plugins:uninstall', (_e, id) => plugins.uninstall(id));
ipcMain.handle('plugins:setEnabled', (_e, id, on) => plugins.setEnabled(id, on));
ipcMain.handle('agents:detect', () => agents.detect());
ipcMain.handle('agents:connection', (_e, id) => agents.connection(id));
ipcMain.handle('agents:connect', (_e, id, on) => agents.connect(id, on));
ipcMain.handle('agents:mcpServer', () => agents.mcpServer());
ipcMain.handle('agents:mcpSetup', () => agents.mcpSetup());
ipcMain.handle('agents:mcpCheck', () => agents.mcpCheck());
ipcMain.handle('agents:signedIn', (_e, id) => agents.signedIn(id));
ipcMain.handle('agents:signIn', (_e, id) => agents.signIn(id));
ipcMain.handle('agents:models', (_e, id, fresh) => agents.models(id, fresh));
ipcMain.handle('agents:run', (_e, params) => { agents.run(params, (ev) => send('agents:event', ev)); return true; });
ipcMain.handle('agents:stop', (_e, runId) => agents.stop(runId));
ai.setup({ checkSource, settings: loadSettings, progress: (p) => send('ai:progress', p) });
ipcMain.handle('ai:status', () => ai.status());
ipcMain.handle('ai:download', (_e, id) => ai.fetchModel(id));
ipcMain.handle('ai:cancel', () => ai.cancelDownload());
ipcMain.handle('ai:remove', (_e, id) => ai.removeModel(id));

ipcMain.handle('window:minimize', () => win.minimize());
ipcMain.handle('window:toggleMaximize', () => (win.isMaximized() ? win.unmaximize() : win.maximize()));
ipcMain.handle('window:close', () => win.close());
ipcMain.handle('window:isMaximized', () => win.isMaximized());
ipcMain.handle('app:devtools', () => win.webContents.toggleDevTools());

// The Mac menu bar. On a Mac, text fields only get Cmd+Z/C/V/X/A from Edit menu items. The editor
// and TuffCode's own shortcuts still handle their keys first. Close and Reload are left out so
// Cmd+W and Cmd+R reach the editor's own shortcuts.
function macMenu() {
  if (process.platform !== 'darwin') return;
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { role: 'appMenu', submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' }, { type: 'separator' }, { role: 'quit' }] },
    { label: 'Edit', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] },
    { role: 'windowMenu', submenu: [{ role: 'minimize' }, { role: 'zoom' }, { type: 'separator' }, { role: 'front' }] },
  ]));
}

app.whenReady().then(() => {
  macMenu();
  createWindow();
  updater.start((s) => send('update:status', s), loadSettings);
});
app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) createWindow(); });
app.on('will-quit', () => ai.quit());

app.on('window-all-closed', () => {
  if (runProc) runProc.kill();
  app.quit();
});
