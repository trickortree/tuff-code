// New Project's starters (1.5.0): real projects to start from, in starters/ (resources/starters in an installed
// TuffCode, see main.js). starters/starters.json lists them in the gallery's order, each as
// { id, name, about, tags, color, project? (the new folder's name, the name if left out), main? (main.tuf) };
// starters/<id>/ holds its files, and starters/<id>.svg is its card's picture. A new project is a new folder with
// a copy of those files: an existing folder is never touched, and a name that's taken gets a free one ("Snake 2").
// Plain Node (no Electron), so the tests can load it.
const fs = require('fs');
const fsp = fs.promises;
const os = require('os');
const path = require('path');

const where = {
  dir: path.join(__dirname, 'starters'),
  folder: () => path.join(os.homedir(), 'Documents', 'TuffProjects'), // main.js gives Electron's Documents folder
};
function setup({ dir, folder } = {}) {
  if (dir) where.dir = dir;
  if (folder) where.folder = folder;
}

// Never copied into a project: what a starter leaves when it's run in place, and system files.
const SKIP = /^(\.|__pycache__$|thumbs\.db$|desktop\.ini$)/i;
// Names Windows keeps for itself (whatever comes after a dot), so a project made on a Mac still opens there.
const RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/i;

// The starters, in the gallery's order, with their pictures; and the folder new projects go in by default.
async function list() {
  let all = [];
  try { all = JSON.parse(await fsp.readFile(path.join(where.dir, 'starters.json'), 'utf8')); } catch {}
  const out = [];
  for (const s of Array.isArray(all) ? all : []) {
    if (!s || !/^[a-z0-9-]+$/.test(String(s.id)) || !s.name) continue;
    const main = s.main || 'main.tuf';
    if (!fs.existsSync(path.join(where.dir, s.id, main))) continue;
    let picture = null;
    try { picture = await fsp.readFile(path.join(where.dir, `${s.id}.svg`), 'utf8'); } catch {}
    out.push({ id: s.id, name: String(s.name), about: String(s.about || ''), tags: Array.isArray(s.tags) ? s.tags.map(String) : [],
      color: /^#[0-9a-f]{6}$/i.test(s.color || '') ? s.color : null, project: String(s.project || s.name), main, picture });
  }
  return { starters: out, folder: where.folder() };
}

// What's wrong with a project's name (it becomes a folder's name), or null.
function nameProblem(name) {
  if (!name) return 'Give the project a name.';
  if (/[<>:"/\\|?*\u0000-\u001f]/.test(name)) return 'A name can\'t have < > : " / \\ | ? or * in it.';
  if (/^\.+$/.test(name)) return 'A name needs a letter or a number in it.';
  if (/[. ]$/.test(name)) return 'A name can\'t end with a dot.';
  if (RESERVED.test(name)) return `${name} is a name Windows keeps for itself. Try another one.`;
  if (name.length > 80) return 'That name is too long.';
  return null;
}

// A name that isn't taken in the folder: the name itself, or with a number after it ("Snake 2", "Snake 3").
// A name that ends in a number goes on from there: "Room 101" is taken, so "Room 102".
function freeName(folder, name) {
  if (!fs.existsSync(path.join(folder, name))) return name;
  const m = name.match(/^(.*\S) (\d{1,6})$/);
  const stem = m ? m[1] : name;
  for (let n = m ? Number(m[2]) + 1 : 2; n < 10000; n++) {
    if (!fs.existsSync(path.join(folder, `${stem} ${n}`))) return `${stem} ${n}`;
  }
  return null;
}

// Can a project called name go in folder? { ok, target } when it can; { ok: false, problem } when the name or the
// folder won't do; { ok: false, taken: true, free, target } when there's already something called that there.
function check(folder, name) {
  const n = String(name ?? '').trim();
  const problem = nameProblem(n);
  if (problem) return { ok: false, problem };
  if (typeof folder !== 'string' || !path.isAbsolute(folder)) return { ok: false, problem: 'Choose a folder for the project.' };
  let st = null;
  try { st = fs.statSync(folder); } catch {}
  if (st && !st.isDirectory()) return { ok: false, problem: `${path.basename(folder)} is a file, not a folder. Choose another folder.` };
  const target = path.join(folder, n);
  if (fs.existsSync(target)) return { ok: false, taken: true, free: freeName(folder, n), target };
  return { ok: true, target };
}

// Copies a starter's files and folders into to, which is new and empty: a file that's there already is never
// overwritten (wx).
async function copyTree(from, to) {
  for (const e of await fsp.readdir(from, { withFileTypes: true })) {
    if (SKIP.test(e.name)) continue;
    const a = path.join(from, e.name);
    const b = path.join(to, e.name);
    if (e.isDirectory()) {
      await fsp.mkdir(b);
      await copyTree(a, b);
    } else if (e.isFile()) {
      await fsp.writeFile(b, await fsp.readFile(a), { flag: 'wx' });
    }
  }
}

// Makes the project: folder/name with the starter's files in it. Gives { ok, dir, main } (main is the file to
// open), or what check() gives when it can't, or { ok: false, problem } when making or copying failed.
async function create(id, folder, name) {
  const starter = (await list()).starters.find((s) => s.id === id);
  if (!starter) return { ok: false, problem: 'That starter isn\'t there any more.' };
  const c = check(folder, name);
  if (!c.ok) return c;
  try {
    await fsp.mkdir(folder, { recursive: true }); // Documents/TuffProjects, the first time
    await fsp.mkdir(c.target); // not recursive: if the folder appeared meanwhile, this fails instead of mixing files in
  } catch (err) {
    if (err.code === 'EEXIST') return { ok: false, taken: true, free: freeName(folder, path.basename(c.target)), target: c.target };
    return { ok: false, problem: `Couldn't make the folder: ${err.message}` };
  }
  try {
    await copyTree(path.join(where.dir, id), c.target);
  } catch (err) {
    // Only what this call made goes: the folder was new a moment ago, and holds just these copies.
    await fsp.rm(c.target, { recursive: true, force: true }).catch(() => {});
    return { ok: false, problem: `Couldn't copy the starter: ${err.message}` };
  }
  return { ok: true, dir: c.target, main: path.join(c.target, starter.main) };
}

// Where Change… starts: the folder, or the nearest folder above it that's there.
function nearestFolder(p) {
  let dir = typeof p === 'string' && path.isAbsolute(p) ? p : where.folder();
  while (!fs.existsSync(dir) && path.dirname(dir) !== dir) dir = path.dirname(dir);
  return dir;
}

module.exports = { setup, list, nameProblem, freeName, check, create, nearestFolder };
