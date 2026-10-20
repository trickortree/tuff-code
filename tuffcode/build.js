const { app, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const { spawn } = require('child_process');

const RUNTIME_DIR = app.isPackaged ? path.join(process.resourcesPath, 'runtime-src') : path.join(__dirname, '..');
const RUNTIME_FILES = ['tuff.py', 'tuff_tgui.py', 'tuff_tap.py', 'tuff_atgui.py'];
const DEFAULT_ICON = path.join(__dirname, 'renderer', 'assets', 'icon.png');
const ASSET_EXTS = new Set(['.png', '.gif', '.ico', '.jpg', '.jpeg', '.webp', '.svg', '.txt', '.json', '.csv', '.wav']);
// Libraries whose windows are web views (tuff_view.py and its page, tuff_view_web): each is tuff_<name>.py.
const VIEW_LIBS = ['atgui', 'tgame'];
// Files a web view program can also use: sounds, models and more kinds of picture.
const VIEW_ASSET_EXTS = new Set(['.mp3', '.ogg', '.m4a', '.webp', '.bmp', '.svg', '.avif', '.glb']);
// Folders that are never packed: earlier builds, tools' folders and hidden ones (.git and so on).
const SKIP_DIRS = new Set(['dist', 'build', 'node_modules', '__pycache__', 'venv']);
const usesLib = (src, lib) => new RegExp(`^\\s*(import|mention)\\s+${lib}\\b`, 'm').test(src);
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// The files a program can use: the ones next to it, and everything in a folder its code names in a
// path (like "sprites/hero.png", or "sounds/" + name), where Sprite Studio and Sound Lab save.
// Gives paths relative to the program's folder, with / between folders.
async function programFiles(dir, src, wanted) {
  const found = [];
  const walk = async (folder, rel, all) => {
    for (const entry of await fsp.readdir(folder, { withFileTypes: true })) {
      const r = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        if (entry.name.startsWith('.') || SKIP_DIRS.has(entry.name.toLowerCase())) continue;
        if (all || new RegExp(`["'](\\./)?${escapeRe(entry.name)}[\\\\/]`, 'i').test(src)) await walk(path.join(folder, entry.name), r, true);
      } else if (entry.isFile() && wanted(path.extname(entry.name).toLowerCase())) {
        found.push(r);
      }
    }
  };
  await walk(dir, '', false);
  return found;
}
const PY = process.platform === 'win32' ? { cmd: 'py', args: ['-3'] } : { cmd: 'python3', args: [] };
// What the build makes: an .exe on Windows, an app elsewhere.
const WIN = process.platform === 'win32';
const BUILDING = WIN ? 'Building your .exe' : 'Building your app';

let current = null;

function safeName(name) {
  return (name || '').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').replace(/\s+/g, ' ').trim().slice(0, 60) || 'MyTuffApp';
}

function pngToIco(png) {
  const header = Buffer.alloc(22);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(1, 4);
  header.writeUInt8(0, 6);
  header.writeUInt8(0, 7);
  header.writeUInt8(0, 8);
  header.writeUInt8(0, 9);
  header.writeUInt16LE(1, 10);
  header.writeUInt16LE(32, 12);
  header.writeUInt32LE(png.length, 14);
  header.writeUInt32LE(22, 18);
  return Buffer.concat([header, png]);
}

function iconPreview(file) {
  const img = nativeImage.createFromPath(file || DEFAULT_ICON);
  if (img.isEmpty()) return null;
  return img.resize({ width: 64, height: 64, quality: 'best' }).toDataURL();
}

function run(cmd, args, { cwd, onLine } = {}) {
  return new Promise((resolve) => {
    let out = '';
    let partial = '';
    let proc;
    try {
      proc = spawn(cmd, args, { cwd, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' } });
    } catch (err) {
      resolve({ code: -1, out: String(err.message), missing: true });
      return;
    }
    current = proc;
    const feed = (d) => {
      const text = d.toString();
      out += text;
      partial += text;
      const lines = partial.split(/\r?\n/);
      partial = lines.pop();
      for (const line of lines) if (line.trim()) onLine?.(line);
    };
    proc.stdout.on('data', feed);
    proc.stderr.on('data', feed);
    proc.on('error', (err) => {
      out += String(err.message);
      resolve({ code: -1, out, missing: err.code === 'ENOENT' });
    });
    proc.on('close', (code) => {
      if (partial.trim()) onLine?.(partial);
      if (current === proc) current = null;
      resolve({ code: code ?? -1, out });
    });
  });
}

function friendlyError(out) {
  if (/PermissionError|Access is denied|being used by another process/i.test(out)) {
    return WIN
      ? 'Windows wouldn\'t let TuffCode replace the old .exe. If your app is still open, close it and build again.'
      : 'TuffCode couldn\'t replace the old app. If it\'s still open, quit it and build again.';
  }
  if (/No space left on device/i.test(out)) return 'Your disk is full. Free up some space and try again.';
  if (/icon/i.test(out) && /(error|failed|invalid)/i.test(out)) {
    return 'The icon couldn\'t be used. Try a different image (a square .png works best).';
  }
  return 'Something went wrong while building. Open "Technical details" below to see the full log.';
}

const MILESTONES = [
  [/Analyzing|Initializing module dependency graph/i, 'Looking at what your program needs…'],
  [/Looking for dynamic libraries|Processing (standard )?module hook/i, 'Collecting Python pieces…'],
  [/Building PYZ/i, 'Bundling Python…'],
  [/Building PKG/i, 'Packing everything together…'],
  [/Building EXE/i, WIN ? 'Writing the .exe…' : 'Writing the app…'],
  [/Copying icon|Copying \d+ resources/i, 'Adding your icon…'],
];

async function build(opts, emit) {
  const step = (id, state, label, detail) => emit({ type: 'step', id, state, label, detail });
  const log = (text) => emit({ type: 'log', text });
  const fail = (id, label, message) => {
    step(id, 'error', label);
    emit({ type: 'done', ok: false, message });
  };
  const started = Date.now();
  const name = safeName(opts.name);
  const program = opts.file;
  const projectDir = opts.root || path.dirname(program);
  const distDir = path.join(projectDir, 'dist');

  step('python', 'running', 'Finding Python');
  await require('./shellpath').ready(); // on a Mac, wait for the login shell's PATH
  let r = await run(PY.cmd, [...PY.args, '--version'], { onLine: log });
  if (r.code !== 0) {
    return fail('python', 'Finding Python', WIN
      ? 'Python isn\'t installed (or Windows can\'t find it). Install it from python.org, tick "Add python.exe to PATH", then build again.'
      : 'Python 3 isn\'t installed. Install it from python.org (or with Homebrew: brew install python), then build again.');
  }
  step('python', 'done', `Found ${r.out.trim()}`);

  step('check', 'running', 'Checking your code for mistakes');
  r = await run(PY.cmd, [...PY.args, path.join(RUNTIME_DIR, 'tuff.py'), '--check', program], { onLine: log });
  if (r.code !== 0) {
    const msg = (r.out.match(/Tuff error[^\n]*/) || [r.out.trim()])[0];
    emit({ type: 'tuff-error', text: r.out });
    return fail('check', 'Checking your code for mistakes', `Your code has a mistake, so it can't be built yet.\n${msg}\nFix it (the Run window shows the same message), then build again.`);
  }
  step('check', 'done', 'Your code looks good');

  step('tools', 'running', 'Getting the build tools ready');
  // Mac and Linux: Homebrew's Python (and many Linux ones) refuse `pip install --user`, so the build
  // tools go in TuffCode's own Python environment. If Python was upgraded and it broke, it's remade.
  let py = PY;
  if (process.platform !== 'win32') {
    const venv = path.join(app.getPath('userData'), 'build-python');
    const vpy = path.join(venv, 'bin', 'python3');
    // It's made in a temporary folder and only moved into place once complete, so a cancelled or
    // failed setup can't leave a half-made one behind.
    if ((await run(vpy, ['-m', 'pip', '--version'])).code !== 0) {
      step('tools', 'running', 'Getting the build tools ready', 'Setting up a Python just for building (first time only)');
      const tmp = `${venv}.tmp`;
      await fsp.rm(tmp, { recursive: true, force: true }).catch(() => {});
      r = await run(PY.cmd, [...PY.args, '-m', 'venv', tmp], { onLine: log });
      if (r.code !== 0) {
        await fsp.rm(tmp, { recursive: true, force: true }).catch(() => {});
        return fail('tools', 'Getting the build tools ready', "Python couldn't set up a place for the build tools. Reinstall Python 3 (from python.org, or with Homebrew: brew install python), then build again.");
      }
      await fsp.rm(venv, { recursive: true, force: true }).catch(() => {});
      await fsp.rename(tmp, venv);
    }
    py = { cmd: vpy, args: [] };
  }
  r = await run(py.cmd, [...py.args, '-m', 'PyInstaller', '--version'], { onLine: log });
  if (r.code !== 0) {
    step('tools', 'running', 'Installing the build tools', 'First time only. This needs the internet and takes about a minute.');
    r = await run(py.cmd, [...py.args, '-m', 'pip', 'install', ...(py === PY ? ['--user'] : []), '--disable-pip-version-check', 'pyinstaller'], {
      onLine: (line) => {
        log(line);
        const m = line.match(/^(Collecting|Downloading|Installing collected packages)\s*:?\s*(\S+)?/);
        if (m) step('tools', 'running', 'Installing the build tools', `${m[1]} ${m[2] || ''}`.trim() + '…');
      },
    });
    if (r.code !== 0) {
      return fail('tools', 'Installing the build tools', 'TuffCode couldn\'t download its build tools (PyInstaller). Check your internet connection and try again.');
    }
    r = await run(py.cmd, [...py.args, '-m', 'PyInstaller', '--version'], { onLine: log });
    if (r.code !== 0) {
      return fail('tools', 'Installing the build tools', 'The build tools installed, but Python can\'t start them. Try restarting TuffCode and building again.');
    }
  }
  const pyinstallerVersion = r.out.trim().split(/\s+/).pop();
  // A web view program (atgui, tgame) needs pywebview in the Python that builds it, like PyInstaller.
  const programSrc = await fsp.readFile(program, 'utf8');
  const viewLibs = VIEW_LIBS.filter((lib) => usesLib(programSrc, lib));
  if (viewLibs.length && (await run(py.cmd, [...py.args, '-c', 'import webview'], { onLine: log })).code !== 0) {
    step('tools', 'running', 'Installing the window engine', 'First time only: pywebview, for game and app windows.');
    r = await run(py.cmd, [...py.args, '-m', 'pip', 'install', ...(py === PY ? ['--user'] : []), '--disable-pip-version-check', 'pywebview'], { onLine: log });
    if (r.code !== 0 || (await run(py.cmd, [...py.args, '-c', 'import webview'], { onLine: log })).code !== 0) {
      return fail('tools', 'Installing the window engine', 'TuffCode couldn\'t download pywebview, which game and app windows need. Check your internet connection and try again.');
    }
  }
  step('tools', 'done', `Build tools ready (PyInstaller ${pyinstallerVersion})`);

  // A window app needs tkinter in the Python that builds it. Without it the app would build fine
  // and then close straight away when opened, so check first.
  const usesGuiEarly = /^\s*(import|mention)\s+m?tgui\b/m.test(await fsp.readFile(program, 'utf8'));
  if (usesGuiEarly && (await run(py.cmd, [...py.args, '-c', 'import tkinter, _tkinter; tkinter.Tcl()'], { onLine: log })).code !== 0) {
    const ver = (await run(PY.cmd, [...PY.args, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'])).out.trim().split(/\s+/).pop() || '3';
    return fail('tools', 'Getting the build tools ready', WIN
      ? 'Your Python doesn\'t include tkinter, which window apps need. Reinstall Python from python.org with "tcl/tk and IDLE" ticked, then build again.'
      : `Your Python (${ver}) doesn't include tkinter, which window apps need. With Homebrew run: brew install python-tk@${ver} (or install Python from python.org), then build again.`);
  }

  step('pack', 'running', 'Packing your program');
  const work = path.join(app.getPath('temp'), 'tuffcode-build', `${name.replace(/\s/g, '_')}-${Date.now()}`);
  await fsp.mkdir(work, { recursive: true });
  for (const f of RUNTIME_FILES) await fsp.copyFile(path.join(RUNTIME_DIR, f), path.join(work, f));
  // Web view programs get the engine, its page and their library (only those: other apps stay small).
  const viewModules = viewLibs.map((lib) => `tuff_${lib}`).filter((m) => fs.existsSync(path.join(RUNTIME_DIR, `${m}.py`)));
  if (viewLibs.length) {
    for (const f of ['tuff_view.py', ...viewModules.map((m) => `${m}.py`)]) await fsp.copyFile(path.join(RUNTIME_DIR, f), path.join(work, f));
    await fsp.cp(path.join(RUNTIME_DIR, 'tuff_view_web'), path.join(work, 'tuff_view_web'), { recursive: true });
  }
  const programCopy = path.join(work, 'program.tuf');
  await fsp.copyFile(program, programCopy);
  const launcher = path.join(work, 'tuff_app.py');
  // The app's windows use the same icon as the app file: the launcher tells the window library
  // where the packed PNG copy is (Tk shows PNGs; its .ico reader can't read modern .ico files).
  await fsp.writeFile(launcher, [
    'import os, sys',
    'base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))',
    'icon = os.path.join(base, "_tuffcode", "app_icon.png")',
    'if os.path.isfile(icon):',
    '    os.environ["TUFF_APP_ICON"] = icon',
    'import tuff',
    // An app with no console shows its errors in tkinter's box, but only tgui apps carry tkinter.
    // The others (games, atgui apps) use the system's own box, so they never just close without a word.
    ...(usesGuiEarly ? [] : [
      '_report = tuff.report',
      '_shown = set()',
      'def _box(text):',
      '    if sys.platform == "win32":',
      '        import ctypes',
      '        ctypes.windll.user32.MessageBoxW(None, text, "Something went wrong", 0x10 | 0x10000 | 0x40000)  # error icon, in front',
      '    elif sys.platform == "darwin":',
      '        import subprocess',
      "        subprocess.run([\"osascript\", \"-e\", \"on run argv\", \"-e\", 'display alert \"Something went wrong\" message (item 1 of argv) as critical', \"-e\", \"end run\", text], capture_output=True)",
      'def report(err, src):',
      '    _report(err, src)',
      '    if not tuff.WINDOWED:',
      '        return',
      '    lines = src.splitlines()',
      '    text = f"Tuff error on line {err.line}: {err.msg}" if err.line else f"Tuff error: {err.msg}"',
      '    if err.line and 0 < err.line <= len(lines):',
      '        text += f"\\n  {err.line} | {lines[err.line - 1]}"',
      '    if text not in _shown:  # the same error again (a key pressed over and over) is shown once',
      '        _shown.add(text)',
      '        try:',
      '            _box(text)',
      '        except Exception:',
      '            pass',
      'tuff.report = report',
    ]),
    'sys.argv = [sys.argv[0], os.path.join(base, "program.tuf")]',
    'sys.exit(tuff.main())',
    '',
  ].join('\n'));

  let iconFile = path.join(work, 'app_icon.ico');
  const iconPng = path.join(work, 'app_icon.png');
  try {
    const img = nativeImage.createFromPath(opts.icon || DEFAULT_ICON);
    if (opts.icon && opts.icon.toLowerCase().endsWith('.ico')) {
      await fsp.copyFile(opts.icon, iconFile);
    } else {
      if (img.isEmpty()) throw new Error('empty image');
      await fsp.writeFile(iconFile, pngToIco(img.resize({ width: 256, height: 256, quality: 'best' }).toPNG()));
    }
    // Tk shows PNGs; an .ico can only be turned into one where Electron reads .ico (Windows).
    if (!img.isEmpty()) await fsp.writeFile(iconPng, img.resize({ width: 128, height: 128, quality: 'best' }).toPNG());
  } catch {
    return fail('pack', 'Packing your program', 'The icon image couldn\'t be read. Pick a .png, .jpg or .ico file, or use the default icon.');
  }

  const sep = process.platform === 'win32' ? ';' : ':';
  // The icon goes in a folder of its own inside the app, so no project file can clash with it.
  const addData = [`${programCopy}${sep}.`];
  if (fs.existsSync(iconPng)) addData.push(`${iconPng}${sep}_tuffcode`);
  if (viewLibs.length) addData.push(`${path.join(work, 'tuff_view_web')}${sep}tuff_view_web`);
  // Each file keeps its folder inside the app, so "sprites/hero.png" works there as it does here.
  const assets = await programFiles(path.dirname(program), programSrc, (ext) => ASSET_EXTS.has(ext) || (viewLibs.length > 0 && VIEW_ASSET_EXTS.has(ext)));
  for (const rel of assets) addData.push(`${path.join(path.dirname(program), rel)}${sep}${path.posix.dirname(rel)}`);
  // On a Mac the app's icon has to be .icns; macOS's own sips tool makes one from the PNG.
  let macIcon = null;
  if (process.platform === 'darwin') {
    const img = nativeImage.createFromPath(opts.icon || DEFAULT_ICON);
    const big = path.join(work, 'app_icon_512.png');
    const icns = path.join(work, 'app_icon.icns');
    if (!img.isEmpty()) {
      await fsp.writeFile(big, img.resize({ width: 512, height: 512, quality: 'best' }).toPNG());
      if ((await run('sips', ['-s', 'format', 'icns', big, '--out', icns])).code === 0 && fs.existsSync(icns)) macIcon = icns;
    }
  }
  const src = await fsp.readFile(program, 'utf8');
  const usesGui = /^\s*(import|mention)\s+m?tgui\b/m.test(src);
  // tap needs Python's ssl (and certifi, where installed, for a Mac app's https:// certificates).
  const usesTap = /^\s*(import|mention)\s+tap\b/m.test(src);
  const windowed = opts.windowed ?? (usesGui || viewLibs.length > 0);
  step('pack', 'done', `Packed your program${assets.length ? ` and ${assets.length} file${assets.length > 1 ? 's' : ''} (${assets.slice(0, 3).join(', ')}${assets.length > 3 ? '…' : ''})` : ''}`);

  step('build', 'running', BUILDING, 'This usually takes 20–60 seconds.');
  await fsp.mkdir(distDir, { recursive: true });
  const args = [
    ...py.args, '-m', 'PyInstaller', '--onefile', '--noconfirm', '--clean', '--log-level', 'INFO',
    '--name', name, '--distpath', distDir, '--workpath', path.join(work, 'work'), '--specpath', work,
    // A Mac app's icon has to be .icns; PyInstaller would need extra tools to convert ours.
    ...(WIN ? ['--icon', iconFile] : macIcon ? ['--icon', macIcon] : []), windowed ? '--windowed' : '--console',
    ...addData.flatMap((d) => ['--add-data', d]),
    ...(usesGui ? ['--hidden-import', 'tuff_tgui'] : ['--exclude-module', 'tkinter', '--exclude-module', 'tuff_tgui']),
    ...(usesTap ? ['--hidden-import', 'tuff_tap', '--hidden-import', 'ssl', '--hidden-import', 'certifi'] : ['--exclude-module', 'tuff_tap']),
    ...(viewLibs.length ? ['--hidden-import', 'tuff_view', ...viewModules.flatMap((m) => ['--hidden-import', m])] : ['--exclude-module', 'tuff_view', '--exclude-module', 'webview']),
    ...VIEW_LIBS.filter((lib) => !viewLibs.includes(lib)).flatMap((lib) => ['--exclude-module', `tuff_${lib}`]),
    launcher,
  ];
  let lastDetail = '';
  r = await run(py.cmd, args, {
    cwd: work,
    onLine: (line) => {
      log(line);
      for (const [re, detail] of MILESTONES) {
        if (re.test(line) && detail !== lastDetail) {
          lastDetail = detail;
          step('build', 'running', BUILDING, detail);
        }
      }
    },
  });
  // On a Mac a windowed program comes out as name.app (plus a bare name binary beside it).
  const exe = process.platform === 'darwin' && windowed && fs.existsSync(path.join(distDir, `${name}.app`))
    ? path.join(distDir, `${name}.app`)
    : path.join(distDir, `${name}${process.platform === 'win32' ? '.exe' : ''}`);
  if (r.code !== 0 || !fs.existsSync(exe)) {
    return fail('build', BUILDING, friendlyError(r.out));
  }
  // A Mac .app is a folder: add up what's inside it.
  const du = async (p) => {
    const st = await fsp.lstat(p);
    if (!st.isDirectory()) return st.size;
    let total = 0;
    for (const e of await fsp.readdir(p)) total += await du(path.join(p, e));
    return total;
  };
  const size = await du(exe);
  step('build', 'done', `Built ${path.basename(exe)}`);
  fsp.rm(work, { recursive: true, force: true }).catch(() => {});
  emit({ type: 'done', ok: true, exe, size, windowed, seconds: Math.round((Date.now() - started) / 1000) });
}

module.exports = {
  iconPreview,
  async start(opts, emit) {
    try {
      await build(opts, emit);
    } catch (err) {
      emit({ type: 'log', text: String(err.stack || err) });
      emit({ type: 'done', ok: false, message: 'Something unexpected went wrong. Open "Technical details" below to see what happened.' });
    }
  },
  cancel() {
    if (current) current.kill();
  },
};
