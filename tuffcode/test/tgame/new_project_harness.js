// New Project (1.5.0), in Node with no window: starters.js's create logic (names, clashes, copying, never
// overwriting) on a scratch folder, then the gallery (renderer/js/new-project.js) in a small stand-in DOM, with
// window.tuff's starters calls going to the real starters.js and a stand-in TuffIDE that notes what it's asked to
// open. run_tests.py's starters group runs it:
//     node new_project_harness.js <scratch folder>
// and prints one JSON list of [ok, what, got] checks.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const APP = path.resolve(__dirname, '..', '..');
const STARTERS = path.join(APP, 'starters');
const scratch = path.resolve(process.argv[2] || path.join(__dirname, 'out', 'new_project'));
const checks = [];
const check = (ok, what, got) => { checks.push([!!ok, what, ok ? null : got === undefined ? null : got]); return !!ok; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const filesIn = (dir) => {
  const out = [];
  const walk = (d, rel) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const r = rel ? `${rel}/${e.name}` : e.name;
      if (e.isDirectory()) walk(path.join(d, e.name), r);
      else out.push(r);
    }
  };
  walk(dir, '');
  return out.sort();
};
const sameFiles = (a, b) => {
  const fa = filesIn(a);
  return JSON.stringify(fa) === JSON.stringify(filesIn(b)) && fa.every((f) => fs.readFileSync(path.join(a, f)).equals(fs.readFileSync(path.join(b, f))));
};

// ---------------------------------------------------------------- a small DOM: enough for new-project.js
const VOID = new Set(['input', 'img', 'br', 'hr', 'meta', 'link']);
const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", nbsp: ' ' };
const decode = (s) => s.replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (_m, e) => ENTITIES[e]);
let active = null;
let layoutColumns = 4; // where cards sit: 4 across, 100 px a row (offsetTop)

class Text {
  constructor(text) { this.nodeType = 3; this.data = text; this.parentNode = null; }
  get textContent() { return this.data; }
}

class El {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.attrs = new Map();
    this.childNodes = [];
    this.parentNode = null;
    this.listeners = {};
    this.value = '';
    this.style = { props: {}, setProperty(k, v) { this.props[k] = v; } };
    const el = this;
    this.classList = {
      list: () => (el.getAttribute('class') || '').split(/\s+/).filter(Boolean),
      contains: (c) => el.classList.list().includes(c),
      add: (...cs) => el.setAttribute('class', [...new Set([...el.classList.list(), ...cs])].join(' ')),
      remove: (...cs) => el.setAttribute('class', el.classList.list().filter((x) => !cs.includes(x)).join(' ')),
      toggle: (c, on) => { const want = on === undefined ? !el.classList.contains(c) : !!on; want ? el.classList.add(c) : el.classList.remove(c); return want; },
    };
    this.dataset = new Proxy({}, {
      get: (_t, k) => el.getAttribute(`data-${String(k).replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}`) ?? undefined,
      set: (_t, k, v) => { el.setAttribute(`data-${String(k).replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}`, String(v)); return true; },
    });
  }
  get tag() { return this.tagName.toLowerCase(); }
  getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; }
  setAttribute(k, v) { this.attrs.set(k, String(v)); if (k === 'value') this.value = String(v); }
  removeAttribute(k) { this.attrs.delete(k); }
  hasAttribute(k) { return this.attrs.has(k); }
  get id() { return this.getAttribute('id') || ''; }
  set id(v) { this.setAttribute('id', v); }
  get className() { return this.getAttribute('class') || ''; }
  set className(v) { this.setAttribute('class', v); }
  get title() { return this.getAttribute('title') || ''; }
  set title(v) { this.setAttribute('title', v); }
  get type() { return this.getAttribute('type') || ''; }
  set type(v) { this.setAttribute('type', v); }
  get disabled() { return this.hasAttribute('disabled'); }
  set disabled(v) { v ? this.setAttribute('disabled', '') : this.removeAttribute('disabled'); }
  get tabIndex() { return this.hasAttribute('tabindex') ? Number(this.getAttribute('tabindex')) : ['button', 'input'].includes(this.tag) ? 0 : -1; }
  set tabIndex(v) { this.setAttribute('tabindex', v); }
  get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(''); }
  set textContent(v) { this.childNodes.forEach((n) => { n.parentNode = null; }); this.childNodes = v === '' ? [] : [new Text(String(v))]; this.childNodes.forEach((n) => { n.parentNode = this; }); }
  get innerHTML() { return this.childNodes.map((n) => (n.nodeType === 3 ? n.data : n.outerHTML)).join(''); }
  set innerHTML(html) { this.childNodes.forEach((n) => { n.parentNode = null; }); this.childNodes = []; parseInto(this, String(html)); }
  get outerHTML() { return `<${this.tag}${[...this.attrs].map(([k, v]) => ` ${k}="${v}"`).join('')}>${this.innerHTML}</${this.tag}>`; }
  get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === document.documentElement; }
  get offsetTop() {
    if (!this.classList.contains('np-card') || !this.parentNode) return 0;
    return Math.floor(this.parentNode.children.indexOf(this) / layoutColumns) * 100;
  }
  appendChild(n) { n.parentNode?.childNodes.splice(n.parentNode.childNodes.indexOf(n), 1); n.parentNode = this; this.childNodes.push(n); return n; }
  remove() { if (this.parentNode) { this.parentNode.childNodes.splice(this.parentNode.childNodes.indexOf(this), 1); this.parentNode = null; } if (active && !active.isConnected) active = null; }
  contains(n) { for (let x = n; x; x = x.parentNode) if (x === this) return true; return false; }
  focus() { active = this; }
  blur() { if (active === this) active = null; }
  scrollIntoView() {}
  click() { dispatch(this, { type: 'click' }); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn); }
  matches(sel) { return sel.split(',').some((one) => matchChain(this, one.trim().split(/\s+/))); }
  closest(sel) { for (let n = this; n && n.nodeType === 1; n = n.parentNode) if (n.matches(sel)) return n; return null; }
  querySelectorAll(sel) { const out = []; const walk = (n) => { for (const c of n.children) { if (c.matches(sel)) out.push(c); walk(c); } }; walk(this); return out; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}

function matchOne(el, sel) {
  const m = sel.match(/^([a-z][a-z0-9-]*)?((?:[#.][\w-]+|\[[\w-]+(?:="[^"]*")?\]|:not\(\[disabled\]\))*)$/i);
  if (!m) throw new Error(`The stand-in DOM can't read the selector ${sel}`);
  if (m[1] && el.tag !== m[1].toLowerCase()) return false;
  for (const part of m[2].match(/[#.][\w-]+|\[[\w-]+(?:="[^"]*")?\]|:not\(\[disabled\]\)/g) || []) {
    if (part[0] === '#' && el.id !== part.slice(1)) return false;
    if (part[0] === '.' && !el.classList.contains(part.slice(1))) return false;
    if (part[0] === '[') {
      const [, k, v] = part.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
      if (!el.hasAttribute(k) || (v !== undefined && el.getAttribute(k) !== v)) return false;
    }
    if (part.startsWith(':not') && el.disabled) return false;
  }
  return true;
}
function matchChain(el, parts) {
  if (!matchOne(el, parts[parts.length - 1])) return false;
  if (parts.length === 1) return true;
  for (let p = el.parentNode; p && p.nodeType === 1; p = p.parentNode) if (matchChain(p, parts.slice(0, -1))) return true;
  return false;
}

function parseInto(parent, html) {
  const stack = [parent];
  const re = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[\w:-]+(?:\s*=\s*(?:"[^"]*"|'[^']*'))?)*)\s*(\/?)>|([^<]+)/g;
  let m;
  while ((m = re.exec(html))) {
    const top = stack[stack.length - 1];
    if (m[1]) {
      const at = stack.map((el) => el.tag).lastIndexOf(m[1].toLowerCase());
      if (at > 0) stack.length = at; // closes it (and anything left open inside it)
    }
    else if (m[2]) {
      const el = new El(m[2]);
      for (const a of m[3].matchAll(/([\w:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'))?/g)) el.setAttribute(a[1], decode(a[2] ?? a[3] ?? ''));
      top.appendChild(el);
      if (!m[4] && !VOID.has(el.tag)) stack.push(el);
    } else if (m[5] && !m[0].startsWith('<!--')) {
      const t = new Text(decode(m[5]));
      t.parentNode = top;
      top.childNodes.push(t);
    }
  }
}

function dispatch(target, init) {
  const e = { bubbles: true, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...init, target, defaultPrevented: false, stopped: false,
    preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; } };
  for (let n = target; n && !e.stopped; n = n.parentNode) for (const fn of [...(n.listeners?.[e.type] || [])]) fn.call(n, e);
  return e;
}

const document = {
  documentElement: new El('html'),
  get activeElement() { return active || document.body; },
  createElement: (tag) => new El(tag),
  getElementById: (id) => document.documentElement.querySelector(`#${id}`),
  querySelector: (sel) => document.documentElement.querySelector(sel),
  querySelectorAll: (sel) => document.documentElement.querySelectorAll(sel),
};
document.body = document.documentElement.appendChild(new El('body'));

// ---------------------------------------------------------------- part 1: starters.js on a scratch folder
async function createLogic() {
  const starters = require(path.join(APP, 'starters.js'));
  const home = path.join(scratch, 'logic', 'TuffProjects');
  starters.setup({ dir: STARTERS, folder: () => home });
  const { starters: list, folder } = await starters.list();
  const ids = list.map((s) => s.id);
  check(folder === home, 'starters:list gives the folder new projects go in', folder);
  check(JSON.stringify(ids) === JSON.stringify(['blank', 'hello', 'quiz', 'habits', 'shop', 'snake', 'coins', 'music', 'drawing', 'weather']),
    'starters:list gives the 10 starters, in the gallery\'s order', ids);
  check(list.every((s) => s.picture && s.picture.trim().startsWith('<svg') && s.about && s.color && s.main === 'main.tuf'),
    'every starter has a picture, an about line, a colour and main.tuf', list.filter((s) => !s.picture || !s.about || !s.color).map((s) => s.id));
  check(list.find((s) => s.id === 'blank').project === 'My Project' && list.find((s) => s.id === 'coins').project === 'Coin Collector',
    'a new project is named after its starter (Blank makes "My Project")', list.map((s) => s.project));
  check(list.every((s) => !/<script|\son\w+=/i.test(s.picture)), 'the pictures are plain drawings (no scripts or on... handlers)', null);

  // names
  const bad = ['', '   ', 'a/b', 'a\\b', 'what?', 'x:y', 'CON', 'lpt1.txt', 'dots...', '..', 'a'.repeat(81)];
  const problems = bad.map((n) => starters.check(home, n));
  check(problems.every((r) => !r.ok && r.problem), 'names that can\'t be folders are refused, each with a reason', problems.map((r, i) => [bad[i], r.problem]));
  check(starters.check(home, 'a/b').problem.includes('/'), '...like a name with a / in it', starters.check(home, 'a/b').problem);
  check(starters.check(home, 'Shop; Cafe').problem === 'A name can\'t have < > : " / \\ | ? * or ; in it.',
    '...and one with a ; in it, which Build exe\'s tools split paths at (the message lists ; too)', starters.check(home, 'Shop; Cafe'));
  check(starters.check('relative/folder', 'Snake').problem === 'Choose a folder for the project.', 'a folder that isn\'t a full path is refused', null);
  const fresh = starters.check(home, '  Snake ');
  check(fresh.ok && fresh.target === path.join(home, 'Snake'), 'a free name (trimmed) is fine, even before TuffProjects is there', fresh);

  // creating: TuffProjects is made the first time, and the files are copies of the starter's
  const made = await starters.create('snake', home, 'Snake');
  check(made.ok && made.dir === path.join(home, 'Snake') && made.main === path.join(home, 'Snake', 'main.tuf') && fs.existsSync(made.main),
    'create makes TuffProjects and Snake in it, and says where main.tuf is', made);
  check(made.ok && sameFiles(path.join(STARTERS, 'snake'), made.dir), '...with exactly the starter\'s files, byte for byte', made.ok && filesIn(made.dir));
  const coins = await starters.create('coins', home, 'Coin Collector');
  check(coins.ok && sameFiles(path.join(STARTERS, 'coins'), coins.dir) && fs.existsSync(path.join(coins.dir, 'pictures', 'hero.png')),
    'a starter with a folder of pictures is copied whole (pictures/hero.png too)', coins.ok && filesIn(coins.dir));
  const shop = await starters.create('shop', home, 'Corner Shop');
  check(shop.ok && JSON.stringify(filesIn(shop.dir)) === '["main.tuf","money.tuf"]', 'a starter in two files gets both (main.tuf and money.tuf)', shop.ok && filesIn(shop.dir));

  // clashes: never overwritten, and a free name is offered
  fs.writeFileSync(path.join(made.dir, 'main.tuf'), 'say "mine"\n');
  const again = await starters.create('snake', home, 'Snake');
  check(!again.ok && again.taken && again.free === 'Snake 2' && again.target === path.join(home, 'Snake'),
    'Snake again: refused, with "Snake 2" offered', again);
  check(fs.readFileSync(path.join(made.dir, 'main.tuf'), 'utf8') === 'say "mine"\n', '...and the Snake folder that\'s there is left alone', null);
  check(starters.check(home, 'snake').taken, 'a name that differs only in capitals counts as taken (as it does on Windows and Macs)', starters.check(home, 'snake'));
  fs.mkdirSync(path.join(home, 'Snake 2'));
  check(starters.freeName(home, 'Snake') === 'Snake 3', 'with Snake 2 there too, Snake 3 is offered', starters.freeName(home, 'Snake'));
  check(starters.check(home, 'Snake 2').free === 'Snake 3', 'Snake 2 taken offers Snake 3 (not "Snake 2 2")', starters.check(home, 'Snake 2'));
  fs.mkdirSync(path.join(home, 'Room 101'));
  check(starters.freeName(home, 'Room 101') === 'Room 102', 'a name ending in a number goes on from it: Room 101 offers Room 102', starters.freeName(home, 'Room 101'));
  fs.writeFileSync(path.join(home, 'notes'), 'a file, not a folder');
  check(starters.check(home, 'notes').taken, 'a file with the name counts as taken too', starters.check(home, 'notes'));
  check(starters.check(path.join(home, 'notes'), 'X').problem?.includes('is a file'), 'a file as the folder is refused', starters.check(path.join(home, 'notes'), 'X'));
  const long = 'L'.repeat(80); // the longest name the gallery's name box takes
  fs.mkdirSync(path.join(home, long));
  const longFree = starters.freeName(home, long);
  check(longFree === `${'L'.repeat(78)} 2` && starters.check(home, longFree).ok, 'an 80-letter name that\'s taken offers a free one that still fits (78 letters and " 2")', longFree);

  // the copy skips what a starter run in place leaves (hidden files, __pycache__)
  const fake = path.join(scratch, 'logic', 'fake-starters');
  fs.mkdirSync(path.join(fake, 'demo', '__pycache__'), { recursive: true });
  fs.mkdirSync(path.join(fake, 'demo', 'art'), { recursive: true });
  fs.writeFileSync(path.join(fake, 'starters.json'), JSON.stringify([{ id: 'demo', name: 'Demo', about: 'x', tags: [] }, { id: 'gone', name: 'Gone' }, { id: '../up', name: 'Up' }]));
  fs.writeFileSync(path.join(fake, 'demo', 'main.tuf'), 'say 1\n');
  fs.writeFileSync(path.join(fake, 'demo', 'art', 'a.png'), Buffer.from([137, 80, 78, 71]));
  fs.writeFileSync(path.join(fake, 'demo', '.DS_Store'), 'x');
  fs.writeFileSync(path.join(fake, 'demo', '__pycache__', 'x.pyc'), 'x');
  starters.setup({ dir: fake });
  const demoList = (await starters.list()).starters;
  check(demoList.length === 1 && demoList[0].id === 'demo' && demoList[0].picture === null && demoList[0].project === 'Demo',
    'starters:list leaves out a starter whose folder is missing and an id that isn\'t a plain name; a missing picture is null', demoList);
  const demo = await starters.create('demo', home, 'Demo');
  check(demo.ok && JSON.stringify(filesIn(demo.dir)) === '["art/a.png","main.tuf"]', 'hidden files and __pycache__ aren\'t copied', demo.ok && filesIn(demo.dir));
  const none = await starters.create('nope', home, 'Nope');
  check(!none.ok && none.problem && !fs.existsSync(path.join(home, 'Nope')), 'an unknown starter makes nothing', none);
  check(starters.nearestFolder(path.join(home, 'not', 'there', 'yet')) === home, 'Change… starts in the nearest folder that\'s there', starters.nearestFolder(path.join(home, 'not', 'there', 'yet')));
  const listed = (await starters.list()).starters;
  check(Array.isArray(listed[0].uses) && listed[0].uses.length === 0, 'a starter that says nothing about what it uses has an empty uses list', listed[0]);

  // When the project's folder can't be made or filled, it says why in plain words, never Node's own
  // ("EPERM: operation not permitted, mkdir ..."). Some troubles are real here; the rest come from a stand-in fs call.
  const plain = (r) => !!(r && !r.ok && r.problem && !/\bE[A-Z]{4,}\b|mkdir|open '|syscall/.test(r.problem));
  const nowhere = process.platform === 'win32' ? [...'ZYXWVUTSRQ'].find((l) => !fs.existsSync(`${l}:\\`)) : null;
  if (nowhere) {
    const r = await starters.create('demo', `${nowhere}:\\TuffProjects`, 'Demo');
    check(plain(r) && r.problem === 'That folder can\'t be reached any more. Use Change… to choose another folder.',
      `a folder on a drive that isn't there (${nowhere}:) says so plainly`, r);
  }
  const under = await starters.create('demo', path.join(home, 'notes', 'deeper'), 'Demo'); // notes is a file
  check(plain(under) && under.problem.startsWith('That folder can\'t be reached'), 'a folder that can\'t be made (a file is in its way) says so plainly', under);
  const failing = (name, code, when = () => true) => {
    const real = fs.promises[name];
    fs.promises[name] = async (...args) => {
      if (!when(...args)) return real.apply(fs.promises, args);
      const err = new Error(`${code}: made-up trouble, ${name} '${args[0]}'`);
      err.code = code;
      err.path = String(args[0]);
      throw err;
    };
    return () => { fs.promises[name] = real; };
  };
  let undo = failing('mkdir', 'EPERM');
  const denied = await starters.create('demo', path.join(home, 'Guarded'), 'Demo');
  undo();
  check(plain(denied) && denied.problem === 'TuffCode isn\'t allowed to make folders in Guarded. Use Change… to choose another folder.',
    'a folder TuffCode may not write in (EPERM, as when Windows guards Documents) says so, and points to Change…', denied);
  undo = failing('writeFile', 'ENOSPC');
  const full = await starters.create('demo', home, 'Full');
  undo();
  check(plain(full) && full.problem.startsWith('The disk is full.') && !fs.existsSync(path.join(home, 'Full')),
    'a full disk says so, and the half-made folder is taken away again', { full, there: fs.existsSync(path.join(home, 'Full')) });
  undo = failing('readFile', 'ENOENT', (p) => String(p).startsWith(path.join(fake, 'demo') + path.sep));
  const missing = await starters.create('demo', home, 'Missing');
  undo();
  check(plain(missing) && missing.problem === 'That starter\'s files are missing. Reinstalling TuffCode brings them back.' && !fs.existsSync(path.join(home, 'Missing')),
    'a starter whose files are gone says so, and makes nothing', missing);
  starters.setup({ dir: STARTERS });
  return starters;
}

// ---------------------------------------------------------------- part 2: the gallery, in the stand-in DOM
async function gallery(starters) {
  const home = path.join(scratch, 'ui', 'TuffProjects');
  const other = path.join(scratch, 'ui', 'Elsewhere');
  fs.mkdirSync(path.join(home, 'Snake'), { recursive: true }); // so the gallery offers "Snake 2"
  fs.mkdirSync(other, { recursive: true });
  starters.setup({ dir: STARTERS, folder: () => home });
  const calls = [];
  const settings = {};
  let picked = other;
  let slow = 0; // ms more that create takes, as on a busy disk
  const api = {
    starters: {
      list: async () => { calls.push(['list']); return starters.list(); },
      check: async (folder, name) => starters.check(folder, name),
      create: async (id, folder, name) => { calls.push(['create', id, folder, name]); await sleep(slow); return starters.create(id, folder, name); },
      pickFolder: async (from) => { calls.push(['pickFolder', from]); return picked; },
    },
    fs: { exists: async (p) => fs.existsSync(p) },
  };
  const editor = document.body.appendChild(new El('textarea'));
  const ide = {
    settings: () => settings,
    saveSettings: (patch) => { Object.assign(settings, patch); calls.push(['saveSettings', patch]); },
    openFolder: async (dir) => { calls.push(['openFolder', dir]); },
    openFile: async (p) => { calls.push(['openFile', p]); },
    toast: (msg, kind) => calls.push(['toast', msg, kind]),
    editor: () => ({ focus: () => editor.focus() }),
  };
  const empty = document.body.appendChild(new El('button'));
  empty.id = 'es-new-project';
  const window = { tuff: api, TuffIDE: ide, TuffIcon: (name) => `<svg data-icon="${name}"></svg>` };
  vm.runInNewContext(fs.readFileSync(path.join(APP, 'renderer', 'js', 'new-project.js'), 'utf8'), { window, document, setTimeout, clearTimeout, console });
  const NP = window.TuffNewProject;
  const $ = (sel) => document.querySelector(sel);
  const cards = () => document.querySelectorAll('.np-card').map((c) => c.dataset.id);
  const sel = () => document.querySelector('.np-card.sel')?.dataset.id || null;
  const name = () => $('#np-name')?.value;
  const status = () => $('#np-status')?.textContent;
  const key = (k, extra = {}) => dispatch(document.activeElement, { type: 'keydown', key: k, ...extra });
  const type = (el, text) => { el.focus(); el.value = text; dispatch(el, { type: 'input' }); };
  const until = async (fn, ms = 3000) => { const end = Date.now() + ms; while (Date.now() < end) { if (fn()) return true; await sleep(10); } return false; };
  const created = () => calls.filter((c) => c[0] === 'create');

  // Opening: the empty state's button opens it too
  editor.focus();
  empty.click();
  await until(() => name() === 'My Project');
  check(NP.isOpen() && $('#new-project') && JSON.stringify(cards()) === JSON.stringify(['blank', 'hello', 'quiz', 'habits', 'shop', 'snake', 'coins', 'music', 'drawing', 'weather']),
    'the empty state\'s New Project button opens the gallery: 10 cards, in order', cards());
  check(sel() === 'blank' && name() === 'My Project' && document.activeElement.id === 'np-q', 'Blank is chosen, the name is "My Project", and the search box has the focus',
    { sel: sel(), name: name(), focus: document.activeElement.id });
  check(document.querySelectorAll('.np-card .np-pic svg').length === 10 && document.querySelectorAll('.np-card .np-tags span').length >= 10,
    'every card has its picture and its tags', null);
  const first = document.querySelector('.np-card');
  check(first.getAttribute('aria-selected') === 'true' && first.tabIndex === 0 && document.querySelectorAll('.np-card')[1].tabIndex === -1,
    'the chosen card is marked for screen readers, and is the one Tab reaches', null);
  check($('#np-folder').textContent === home && status() === `Makes ${path.join(home, 'My Project')}` && !$('#np-create').disabled,
    'the folder is Documents/TuffProjects, and it says where the project goes', { folder: $('#np-folder').textContent, status: status() });

  // Searching
  type($('#np-q'), 'game');
  await until(() => name() === 'Quiz');
  check(JSON.stringify(cards()) === '["quiz","snake","coins"]' && sel() === 'quiz', '"game" leaves Quiz, Snake and Coin Collector, and chooses Quiz', { cards: cards(), sel: sel() });
  type($('#np-q'), 'terminal snake');
  await until(() => sel() === 'snake');
  check(JSON.stringify(cards()) === '["snake"]', 'every word has to match ("terminal snake")', cards());
  type($('#np-q'), 'zzz');
  await until(() => $('#np-create').disabled);
  check(!cards().length && $('.np-none').textContent === 'No starter matches “zzz”.' && $('#np-create').disabled, 'no match says so, and Create waits', $('.np-none')?.textContent);
  type($('#np-q'), '');
  await until(() => cards().length === 10 && !$('#np-create').disabled);
  check(cards().length === 10 && sel() === 'blank', 'clearing the search brings every card back', { cards: cards().length, sel: sel() });

  // Keys: arrows in the search box move by a row; on the cards they move across and down (4 across here)
  $('#np-q').focus();
  key('ArrowDown');
  await until(() => sel() === 'shop');
  check(sel() === 'shop' && document.activeElement.id === 'np-q', 'Down in the search box chooses the card below and keeps the focus there', { sel: sel(), focus: document.activeElement.id });
  key('ArrowUp');
  await until(() => sel() === 'blank');
  document.querySelector('.np-card.sel').focus();
  key('ArrowRight');
  await until(() => sel() === 'hello');
  key('ArrowDown');
  await until(() => sel() === 'snake');
  check(sel() === 'snake' && document.activeElement.dataset?.id === 'snake', 'Right then Down on the cards: Hello, then Snake below it, with the focus', { sel: sel(), focus: document.activeElement.dataset?.id });
  await until(() => name() === 'Snake 2');
  check(name() === 'Snake 2' && status() === `Makes ${path.join(home, 'Snake 2')}`, 'there\'s a Snake folder already, so the name is "Snake 2"', { name: name(), status: status() });
  key('End');
  await until(() => sel() === 'weather');
  key('Home');
  await until(() => sel() === 'blank');
  key('ArrowLeft');
  await sleep(30);
  check(sel() === 'blank', 'End and Home go to the last and first cards, and Left stops at the first', sel());
  key('w');
  check(document.activeElement.id === 'np-q', 'typing a letter on a card goes to the search box', document.activeElement.id);

  // The name: typed names stay, taken ones are never used, bad ones are refused
  document.querySelector('.np-card[data-id="snake"]').click();
  await until(() => name() === 'Snake 2');
  type($('#np-name'), 'My Snake');
  await until(() => status() === `Makes ${path.join(home, 'My Snake')}`);
  document.querySelector('.np-card[data-id="music"]').click();
  await until(() => sel() === 'music');
  await sleep(40);
  check(name() === 'My Snake', 'a typed name stays when another starter is chosen', name());
  type($('#np-name'), '');
  document.querySelector('.np-card[data-id="snake"]').click();
  await until(() => name() === 'Snake 2');
  check(name() === 'Snake 2', '...and once it\'s emptied, choosing a starter fills it in again', name());
  type($('#np-name'), 'a/b');
  await until(() => $('#np-status').classList.contains('bad'));
  check(/can't have/.test(status()) && $('#np-create').disabled, 'a name with a / in it says why, and Create waits', status());
  type($('#np-name'), 'Snake');
  await until(() => $('#np-status').classList.contains('taken'));
  check(status() === 'There\'s already a “Snake” there. Use “Snake 2”' && !$('#np-create').disabled, 'a taken name says so, and offers "Snake 2"', status());
  key('Enter');
  await until(() => name() === 'Snake 2');
  check(name() === 'Snake 2' && !created().length && NP.isOpen(), 'Enter on a taken name puts in the free one, and makes nothing yet', { name: name(), created: created() });

  // Create: the folder, then the IDE opens it and its main.tuf
  key('Enter');
  await until(() => !NP.isOpen());
  const snake2 = path.join(home, 'Snake 2');
  check(JSON.stringify(created()) === JSON.stringify([['create', 'snake', home, 'Snake 2']]), 'Enter again creates Snake 2 from the Snake starter', created());
  check(!NP.isOpen() && !$('#new-project') && sameFiles(path.join(STARTERS, 'snake'), snake2), 'the dialog closes, and Snake 2 has the starter\'s files', filesIn(home));
  await until(() => calls.some((c) => c[0] === 'toast'));
  const order = calls.filter((c) => ['openFolder', 'openFile', 'toast', 'saveSettings'].includes(c[0]));
  check(JSON.stringify(order.map((c) => c[0])) === '["saveSettings","openFolder","openFile","toast"]' && order[1][1] === snake2 && order[2][1] === path.join(snake2, 'main.tuf'),
    'then the IDE opens the folder as the project, and opens its main.tuf', order);
  check(/^Made Snake 2 from the Snake starter/.test(order[3]?.[1]) && settings.newProjectFolder === null, '...says what it made, and remembers the default folder', { toast: order[3], settings });
  check(fs.readdirSync(path.join(home, 'Snake')).length === 0, 'the Snake folder that was there is untouched', fs.readdirSync(path.join(home, 'Snake')));

  // Change…: another folder, which is remembered for next time
  calls.length = 0;
  NP.open();
  await until(() => name() === 'My Project');
  document.querySelector('[data-a="change"]').click();
  await until(() => $('#np-folder').textContent === other && status() === `Makes ${path.join(other, 'My Project')}`);
  check(JSON.stringify(calls.find((c) => c[0] === 'pickFolder')) === JSON.stringify(['pickFolder', home]) && $('#np-folder').textContent === other,
    'Change… asks for a folder, starting from the one shown, and shows the new one', calls);
  check(status() === `Makes ${path.join(other, 'My Project')}`, '...and the project goes there', status());
  const habits = document.querySelector('.np-card[data-id="habits"]');
  habits.click(); // a double-click: its click, then the dblclick straight away, before the name has come
  dispatch(habits, { type: 'dblclick' });
  await until(() => !NP.isOpen());
  check(fs.existsSync(path.join(other, 'Habit Tracker', 'habits.tuf')) && !fs.existsSync(path.join(other, 'My Project')) && settings.newProjectFolder === other,
    'double-clicking a card creates it there with its own name, and that folder is remembered', { settings, files: fs.readdirSync(other) });
  calls.length = 0;
  NP.open();
  await until(() => name() === 'My Project');
  check($('#np-folder').textContent === other, 'next time, the gallery starts in the remembered folder', $('#np-folder').textContent);
  picked = null; // Change… cancelled
  document.querySelector('[data-a="change"]').click();
  await sleep(40);
  check($('#np-folder').textContent === other, 'cancelling Change… keeps the folder', $('#np-folder').textContent);

  // Tab stays inside, and Esc closes without making anything
  $('#np-create').focus();
  key('Tab');
  check(document.activeElement.id === 'np-q', 'Tab after Create goes back to the search box', document.activeElement.id);
  key('Tab', { shiftKey: true });
  check(document.activeElement.id === 'np-create', 'Shift+Tab from the search box goes to Create', document.activeElement.id);
  editor.focus();
  NP.close();
  NP.open();
  await until(() => name() === 'My Project');
  key('Escape');
  check(!NP.isOpen() && !created().length && document.activeElement === editor, 'Esc closes it, makes nothing, and gives the focus back', { open: NP.isOpen(), created: created() });
  NP.open();
  await until(() => name() === 'My Project');
  dispatch($('#new-project'), { type: 'mousedown' });
  check(!NP.isOpen(), 'a click outside the box closes it too', NP.isOpen());

  // A clash that appears while the dialog is open: create refuses, and offers the free name
  calls.length = 0;
  NP.open();
  await until(() => name() === 'My Project');
  fs.mkdirSync(path.join(other, 'My Project'));
  $('#np-create').click();
  await until(() => name() === 'My Project 2');
  check(name() === 'My Project 2' && !created().length && NP.isOpen(), 'a folder made meanwhile is noticed before anything is copied', { name: name(), created: created() });
  NP.close();

  // The search finds what a starter uses too (starters.json's uses), though its card doesn't show it
  const ready = () => until(() => /^Makes /.test(status() || ''));
  NP.open();
  await ready();
  for (const [q, want] of [['tgame', ['coins']], ['tterm', ['snake']], ['import', ['habits', 'shop']], ['turtle', ['drawing']], ['tap', ['weather']]]) {
    type($('#np-q'), q);
    check(JSON.stringify(cards()) === JSON.stringify(want), `searching "${q}" finds ${want.join(' and ')}, which use it`, cards());
  }
  NP.close();

  // A click on the dialog's text or a gap focuses the box itself (tabindex="-1", as the Build and Settings dialogs
  // do), and the keys still work from there
  NP.open();
  await ready();
  const npBox = $('.np-box');
  check(npBox.getAttribute('tabindex') === '-1', 'the box itself can take the focus', npBox.getAttribute('tabindex'));
  npBox.focus();
  key('ArrowRight');
  await until(() => sel() === 'hello');
  check(sel() === 'hello' && document.activeElement.dataset?.id === 'hello', 'with the focus on the box, Right chooses the next card and the focus goes with it',
    { sel: sel(), focus: document.activeElement.id || document.activeElement.dataset?.id });
  npBox.focus();
  key('Tab', { shiftKey: true });
  check(document.activeElement.id === 'np-create', '...Shift+Tab goes to Create, the last thing in it', document.activeElement.id);
  npBox.focus();
  key('Escape');
  check(!NP.isOpen() && !created().length, 'with the focus on the box, Esc closes the gallery', { open: NP.isOpen(), created: created() });

  // While Create makes the project (slowly here, as on a busy disk), Esc, Cancel, the X and a click outside don't
  // close the dialog: it stays until it's done, then the IDE opens the project
  calls.length = 0;
  slow = 300;
  NP.open();
  await ready();
  const making = name();
  $('.np-box').focus();
  key('Enter'); // Enter with the focus on the box creates, too
  await until(() => $('#np-create')?.textContent === 'Creating…');
  key('Escape');
  $('[data-a="cancel"]')?.click(); // (switched off, but a click that came anyway still has to wait)
  $('[data-a="close"]')?.click();
  if ($('#new-project')) dispatch($('#new-project'), { type: 'mousedown' });
  check(NP.isOpen() && $('#np-create')?.textContent === 'Creating…' && status() === 'Making the project…'
    && ['cancel', 'close', 'change', 'create'].every((a) => $(`[data-a="${a}"]`)?.disabled),
    'while Create makes the project, Esc, Cancel, the X and a click outside leave the dialog open, and its buttons are off', { open: NP.isOpen(), status: status() });
  await until(() => calls.some((c) => c[0] === 'openFile'), 5000);
  check(!NP.isOpen() && JSON.stringify(created().map((c) => c[3])) === JSON.stringify([making])
    && calls.some((c) => c[0] === 'openFolder' && c[1] === path.join(other, making)), '...then it closes, and the IDE opens the new project', calls);
  slow = 0;

  // A long name that's taken: the offer of a free name is a button of its own after the message, so it always shows
  NP.open();
  await ready();
  const long = 'L'.repeat(80);
  fs.mkdirSync(path.join(other, long));
  if ($('#np-name')) type($('#np-name'), long);
  await until(() => $('#np-status')?.classList.contains('taken'));
  const offer = $('#np-status [data-a="free"]');
  const longFree = `${'L'.repeat(78)} 2`;
  check(offer && offer.parentNode === $('#np-status') && $('#np-status .np-msg') && !$('#np-status .np-msg').contains(offer) && offer.textContent === `Use “${longFree}”`,
    'a long taken name: the message and the offer (cut to fit: 78 letters and " 2") are side by side, so the offer always shows', $('#np-status')?.innerHTML.slice(0, 300));
  offer?.click();
  await ready();
  check(name() === longFree && !$('#np-create').disabled, '...and the offer is a name Create takes', { name: name(), status: status() });
  check($('#np-status .np-path bdi')?.textContent === path.join(other, longFree) && $('#np-status')?.title === status(),
    'where it goes is a path of its own (a long one loses its start, not the new folder\'s name), and the tooltip has all of it', $('#np-status')?.innerHTML.slice(0, 300));
  NP.close();

  // A project that can't be made (a file is in the way of the folder) says why plainly, and the box takes the focus
  // Create lost when it was switched off, so the keys still work
  calls.length = 0;
  fs.writeFileSync(path.join(other, 'a file'), 'not a folder');
  picked = path.join(other, 'a file', 'inside');
  NP.open();
  await ready();
  document.querySelector('[data-a="change"]')?.click();
  await until(() => $('#np-folder')?.textContent === picked && /^Makes /.test(status() || ''));
  $('#np-create')?.focus();
  $('#np-create')?.click();
  $('#np-create')?.blur(); // as in a browser: a button that's switched off loses the focus
  await until(() => $('#np-status')?.classList.contains('bad'));
  check(status() === 'That folder can\'t be reached any more. Use Change… to choose another folder.' && document.activeElement === $('.np-box') && NP.isOpen()
    && $('[data-a="change"]') && !$('[data-a="change"]').disabled, 'a project that can\'t be made says why in plain words, Change… is on again, and the box has the focus',
    { status: status(), focus: document.activeElement.className || document.activeElement.id });
  key('Escape');
  check(!NP.isOpen() && !calls.some((c) => c[0] === 'openFolder'), '...so Esc still closes it, and nothing was opened', { open: NP.isOpen(), calls });
  picked = other;
}

(async () => {
  fs.rmSync(scratch, { recursive: true, force: true });
  fs.mkdirSync(scratch, { recursive: true });
  try {
    const starters = await createLogic();
    await gallery(starters);
  } catch (err) {
    check(false, `the harness stopped: ${err.stack || err}`);
  }
  console.log(JSON.stringify(checks));
})();
