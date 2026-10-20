const { app, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const { spawn } = require('child_process');

const RUNTIME_DIR = app.isPackaged ? path.join(process.resourcesPath, 'runtime-src') : path.join(__dirname, '..');
const RUNTIME_FILES = ['tuff.py', 'tuff_tgui.py'];
const DEFAULT_ICON = path.join(__dirname, 'renderer', 'assets', 'icon.png');
const ASSET_EXTS = new Set(['.png', '.gif', '.ico', '.jpg', '.jpeg', '.txt', '.json', '.csv', '.wav']);
const PY = process.platform === 'win32' ? { cmd: 'py', args: ['-3'] } : { cmd: 'python3', args: [] };

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
    return 'Windows wouldn\'t let TuffCode replace the old .exe. If your app is still open, close it and build again.';
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
  [/Building EXE/i, 'Writing the .exe…'],
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
  let r = await run(PY.cmd, [...PY.args, '--version'], { onLine: log });
  if (r.code !== 0) {
    return fail('python', 'Finding Python', 'Python isn\'t installed (or Windows can\'t find it). Install it from python.org, tick "Add python.exe to PATH", then build again.');
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
  r = await run(PY.cmd, [...PY.args, '-m', 'PyInstaller', '--version'], { onLine: log });
  if (r.code !== 0) {
    step('tools', 'running', 'Installing the build tools', 'First time only. This needs the internet and takes about a minute.');
    r = await run(PY.cmd, [...PY.args, '-m', 'pip', 'install', '--user', '--disable-pip-version-check', 'pyinstaller'], {
      onLine: (line) => {
        log(line);
        const m = line.match(/^(Collecting|Downloading|Installing collected packages)\s*:?\s*(\S+)?/);
        if (m) step('tools', 'running', 'Installing the build tools', `${m[1]} ${m[2] || ''}`.trim() + '…');
      },
    });
    if (r.code !== 0) {
      return fail('tools', 'Installing the build tools', 'TuffCode couldn\'t download its build tools (PyInstaller). Check your internet connection and try again.');
    }
    r = await run(PY.cmd, [...PY.args, '-m', 'PyInstaller', '--version'], { onLine: log });
    if (r.code !== 0) {
      return fail('tools', 'Installing the build tools', 'The build tools installed, but Python can\'t start them. Try restarting TuffCode and building again.');
    }
  }
  step('tools', 'done', `Build tools ready (PyInstaller ${r.out.trim().split(/\s+/).pop()})`);

  step('pack', 'running', 'Packing your program');
  const work = path.join(app.getPath('temp'), 'tuffcode-build', `${name.replace(/\s/g, '_')}-${Date.now()}`);
  await fsp.mkdir(work, { recursive: true });
  for (const f of RUNTIME_FILES) await fsp.copyFile(path.join(RUNTIME_DIR, f), path.join(work, f));
  const programCopy = path.join(work, 'program.tuf');
  await fsp.copyFile(program, programCopy);
  const launcher = path.join(work, 'tuff_app.py');
  await fsp.writeFile(launcher, [
    'import os, sys',
    'import tuff',
    'base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))',
    'sys.argv = [sys.argv[0], os.path.join(base, "program.tuf")]',
    'sys.exit(tuff.main())',
    '',
  ].join('\n'));

  let iconFile = path.join(work, 'icon.ico');
  try {
    if (opts.icon && opts.icon.toLowerCase().endsWith('.ico')) {
      await fsp.copyFile(opts.icon, iconFile);
    } else {
      const img = nativeImage.createFromPath(opts.icon || DEFAULT_ICON);
      if (img.isEmpty()) throw new Error('empty image');
      await fsp.writeFile(iconFile, pngToIco(img.resize({ width: 256, height: 256, quality: 'best' }).toPNG()));
    }
  } catch {
    return fail('pack', 'Packing your program', 'The icon image couldn\'t be read. Pick a .png, .jpg or .ico file, or use the default icon.');
  }

  const sep = process.platform === 'win32' ? ';' : ':';
  const addData = [`${programCopy}${sep}.`];
  const assets = [];
  for (const entry of await fsp.readdir(path.dirname(program), { withFileTypes: true })) {
    if (entry.isFile() && ASSET_EXTS.has(path.extname(entry.name).toLowerCase())) {
      assets.push(entry.name);
      addData.push(`${path.join(path.dirname(program), entry.name)}${sep}.`);
    }
  }
  const src = await fsp.readFile(program, 'utf8');
  const usesGui = /^\s*(import|mention)\s+m?tgui\b/m.test(src);
  const windowed = opts.windowed ?? usesGui;
  step('pack', 'done', `Packed your program${assets.length ? ` and ${assets.length} file${assets.length > 1 ? 's' : ''} (${assets.slice(0, 3).join(', ')}${assets.length > 3 ? '…' : ''})` : ''}`);

  step('build', 'running', 'Building your .exe', 'This usually takes 20–60 seconds.');
  await fsp.mkdir(distDir, { recursive: true });
  const args = [
    ...PY.args, '-m', 'PyInstaller', '--onefile', '--noconfirm', '--clean', '--log-level', 'INFO',
    '--name', name, '--distpath', distDir, '--workpath', path.join(work, 'work'), '--specpath', work,
    // A Mac app's icon has to be .icns; PyInstaller would need extra tools to convert ours.
    ...(process.platform === 'win32' ? ['--icon', iconFile] : []), windowed ? '--windowed' : '--console',
    ...addData.flatMap((d) => ['--add-data', d]),
    ...(usesGui ? ['--hidden-import', 'tuff_tgui'] : ['--exclude-module', 'tkinter', '--exclude-module', 'tuff_tgui']),
    launcher,
  ];
  let lastDetail = '';
  r = await run(PY.cmd, args, {
    cwd: work,
    onLine: (line) => {
      log(line);
      for (const [re, detail] of MILESTONES) {
        if (re.test(line) && detail !== lastDetail) {
          lastDetail = detail;
          step('build', 'running', 'Building your .exe', detail);
        }
      }
    },
  });
  // On a Mac a windowed program comes out as name.app (plus a bare name binary beside it).
  const exe = process.platform === 'darwin' && windowed && fs.existsSync(path.join(distDir, `${name}.app`))
    ? path.join(distDir, `${name}.app`)
    : path.join(distDir, `${name}${process.platform === 'win32' ? '.exe' : ''}`);
  if (r.code !== 0 || !fs.existsSync(exe)) {
    return fail('build', 'Building your .exe', friendlyError(r.out));
  }
  const size = (await fsp.stat(exe)).size;
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
