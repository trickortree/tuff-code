const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const { spawn } = require('child_process');
const builder = require('./build');
const updater = require('./updater');
const plugins = require('./plugins');
const agents = require('./agents');

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
    frame: false,
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
  win.on('blur', () => send('window:blur'));
}

ipcMain.handle('settings:get', () => loadSettings());
ipcMain.handle('settings:set', (_e, patch) => saveSettings(patch));

ipcMain.handle('project:default', () => ensureDefaultProject());
ipcMain.handle('fs:readDir', (_e, dir) => readDir(dir));
ipcMain.handle('fs:listAll', (_e, root) => listAllFiles(root));
ipcMain.handle('fs:readFile', (_e, p) => fsp.readFile(p, 'utf8'));
ipcMain.handle('fs:writeFile', (_e, p, content) => fsp.writeFile(p, content, 'utf8'));
ipcMain.handle('fs:exists', (_e, p) => fs.existsSync(p));
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
ipcMain.handle('shell:reveal', (_e, p) => shell.showItemInFolder(p));

ipcMain.handle('dialog:openFolder', async () => {
  const res = await dialog.showOpenDialog(win, { properties: ['openDirectory'] });
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
  if (/^https:\/\/github\.com\/trickortree\/tuff-code\b/.test(url)) shell.openExternal(url);
});

ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('update:state', () => updater.state());
ipcMain.handle('update:check', () => updater.check());
ipcMain.handle('update:install', () => updater.install());
ipcMain.handle('update:restart', () => updater.restart());
ipcMain.handle('update:reschedule', () => updater.reschedule());

ipcMain.handle('tuff:check', async (_e, source) => {
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
    proc.on('close', (code) => resolve({ ok: code === 0, message: (out.match(/Tuff error[^\r\n]*/) || [''])[0] }));
  });
  fsp.rm(file, { force: true }).catch(() => {});
  return result;
});

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
ipcMain.handle('agents:run', (_e, params) => { agents.run(params, (ev) => send('agents:event', ev)); return true; });
ipcMain.handle('agents:stop', (_e, runId) => agents.stop(runId));

ipcMain.handle('window:minimize', () => win.minimize());
ipcMain.handle('window:toggleMaximize', () => (win.isMaximized() ? win.unmaximize() : win.maximize()));
ipcMain.handle('window:close', () => win.close());
ipcMain.handle('window:isMaximized', () => win.isMaximized());
ipcMain.handle('app:devtools', () => win.webContents.toggleDevTools());

app.whenReady().then(() => {
  createWindow();
  updater.start((s) => send('update:status', s), loadSettings);
});
app.on('window-all-closed', () => {
  if (runProc) runProc.kill();
  app.quit();
});
