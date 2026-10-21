// Plugin manager: the marketplace list, installing/removing plugins and turning them on or off.
// Built-in plugins ship in tuffcode/plugins/<id>; downloaded ones live in userData/plugins/<id>.
const { app, net } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const { pathToFileURL } = require('url');

const BUILTIN_DIR = path.join(__dirname, 'plugins');
const REGISTRY_URL = 'https://raw.githubusercontent.com/trickortree/tuff-code/main/tuffcode/plugins/registry.json';
// The e2e tests serve their own online list (a slow one, or none) from this computer.
const TEST_URL = /^http:\/\/(127\.0\.0\.1|localhost):\d+\//.test(process.env.TUFFCODE_REGISTRY_URL || '') ? process.env.TUFFCODE_REGISTRY_URL : null;
const SAFE_SOURCE = /^https:\/\/(raw\.githubusercontent\.com|github\.com)\//;
const SAFE_FILE = /^[\w-]+(\/[\w-]+)*\.(json|js|css|svg|png|md)$/;

let settings = { load: () => ({}), save: () => {} };
let bundled = null; // the marketplace list TuffCode comes with
let online = null; // the newest list from GitHub, once it has come
let fetching = null; // the request for it, while it's on its way

const userDir = () => path.join(app.getPath('userData'), 'plugins');
const state = () => settings.load().plugins || {};
const saveState = (next) => settings.save({ plugins: next });

function setup(opts) { settings = opts; }

function readManifest(dir) {
  try {
    const m = JSON.parse(fs.readFileSync(path.join(dir, 'plugin.json'), 'utf8'));
    return m && m.id && m.name ? m : null;
  } catch { return null; }
}

// TuffCode 1.0.3 and older read only "plugins" from registry.json, also from the main branch, and offer
// to download any entry there they didn't come with. So a plugin that needs a newer TuffCode goes in
// "newer", with "needs": the first version that has what it uses. This version reads both lists and
// leaves out what needs a newer version than this one.
const versionParts = (v) => String(v || '').replace(/^v/i, '').split(/[.+-]/).slice(0, 3).map((n) => parseInt(n, 10) || 0);
function tooNew(needs) {
  const want = versionParts(needs), have = versionParts(app.getVersion());
  for (let i = 0; i < 3; i++) if (want[i] !== have[i]) return want[i] > have[i];
  return false;
}
const entries = (json) => [...(json.plugins || []), ...(json.newer || [])].filter((p) => p && !(p.needs && tooNew(p.needs)));

async function bundledRegistry() {
  try { return entries(JSON.parse(await fsp.readFile(path.join(BUILTIN_DIR, 'registry.json'), 'utf8'))); } catch { return []; }
}

// The online list's entries, or null when it didn't come (offline, or no answer within 6 s).
async function remoteRegistry() {
  try {
    const res = await Promise.race([net.fetch(TEST_URL || REGISTRY_URL, { headers: { 'Cache-Control': 'no-cache' } }), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 6000))]);
    if (!res.ok) return null;
    return entries(await res.json());
  } catch { return null; }
}

// Asks GitHub for the newest list, one request at a time. If it doesn't come, the last one that did is kept.
function fetchOnline() {
  if (!fetching) fetching = remoteRegistry().then((r) => { if (r) online = r; }).finally(() => { fetching = null; });
  return fetching;
}

// The marketplace: the list that ships with TuffCode, with the online list's entries added once it has
// come. Only goOnline waits for the network (up to 6 s, the refresh button): startup never does, so the
// cards show and installed plugins start straight away, and the IDE asks again for the online entries.
async function registry(goOnline) {
  if (!bundled) bundled = await bundledRegistry();
  if (goOnline) await fetchOnline();
  const byId = new Map(bundled.map((p) => [p.id, p]));
  for (const p of online || []) {
    if (!p.id || (byId.get(p.id)?.builtin && !p.source)) continue;
    byId.set(p.id, { ...byId.get(p.id), ...p });
  }
  return [...byId.values()];
}

function dirFor(id, entry) {
  const builtin = path.join(BUILTIN_DIR, id);
  if ((entry?.builtin || !entry) && fs.existsSync(path.join(builtin, 'plugin.json'))) return { dir: builtin, builtin: true };
  return { dir: path.join(userDir(), id), builtin: false };
}

// goOnline: wait for the newest online list first. Without it: what TuffCode knows now, at once.
async function list(goOnline) {
  const reg = await registry(goOnline);
  const st = state();
  const installed = [];
  for (const [id, s] of Object.entries(st)) {
    const { dir, builtin } = dirFor(id, reg.find((r) => r.id === id));
    const manifest = readManifest(dir);
    if (!manifest) continue;
    installed.push({ ...manifest, dir, builtin, enabled: s.enabled !== false, url: builtin ? `../plugins/${id}/` : `${pathToFileURL(dir).href}/` });
  }
  const available = reg.map((r) => ({ ...r, installed: !!st[r.id] && installed.some((p) => p.id === r.id) }));
  return { installed, available };
}

async function download(entry) {
  if (!SAFE_SOURCE.test(entry.source || '')) throw new Error('This plugin comes from a place TuffCode doesn\'t trust.');
  const files = entry.files || ['plugin.json'];
  if (!files.includes('plugin.json') || files.some((f) => !SAFE_FILE.test(f))) throw new Error('This plugin has a file TuffCode won\'t download.');
  const target = path.join(userDir(), entry.id);
  const temp = target + '.download';
  await fsp.rm(temp, { recursive: true, force: true });
  for (const f of files) {
    const res = await net.fetch(entry.source.replace(/\/?$/, '/') + f);
    if (!res.ok) throw new Error(`Couldn't download ${f} (${res.status}).`);
    const out = path.join(temp, f);
    await fsp.mkdir(path.dirname(out), { recursive: true });
    await fsp.writeFile(out, Buffer.from(await res.arrayBuffer()));
  }
  const m = readManifest(temp);
  if (!m || m.id !== entry.id) throw new Error('The downloaded plugin doesn\'t match the marketplace entry.');
  await fsp.rm(target, { recursive: true, force: true });
  await fsp.rename(temp, target);
}

async function install(id) {
  const entry = (await registry()).find((r) => r.id === id);
  if (!entry) throw new Error('That plugin isn\'t in the marketplace.');
  if (!dirFor(id, entry).builtin) await download(entry);
  saveState({ ...state(), [id]: { enabled: true, version: entry.version } });
  return list();
}

async function uninstall(id) {
  const st = { ...state() };
  delete st[id];
  saveState(st);
  const { dir, builtin } = dirFor(id, (await registry()).find((r) => r.id === id));
  if (!builtin) await fsp.rm(dir, { recursive: true, force: true });
  return list();
}

async function setEnabled(id, enabled) {
  const st = state();
  if (!st[id]) throw new Error('That plugin isn\'t installed.');
  saveState({ ...st, [id]: { ...st[id], enabled } });
  return list();
}

module.exports = { setup, list, install, uninstall, setEnabled };
