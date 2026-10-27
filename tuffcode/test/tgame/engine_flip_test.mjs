// The game page's engine (tuff_view_web/engine.js) drawing a sprite sheet, in Node with a pretend page (no window):
// it gets tgame's commands for a canvas and a picture cut into 4 x 2 frames playing a walk, and each frame it draws
// the right part of the picture; with data-paused on the canvas it holds still; a stop shows the frame it's given.
// It prints what it saw as JSON; run_tests.py (t_frames) checks it.   Usage: node engine_flip_test.mjs path/to/engine.js
import { pathToFileURL } from 'node:url';

// ---- a pretend page: just enough of the DOM for engine.js and the modules it imports
const draws = [];  // every drawImage: [the picture's src, sx, sy, sw, sh, dx, dy, dw, dh]
const ctx = new Proxy({}, {
  get(target, k) {
    if (k === 'drawImage') return (img, ...a) => draws.push([img.src, ...a.map((v) => Math.round(v * 100) / 100)]);
    if (k === 'measureText') return () => ({ width: 10 });
    if (k in target) return target[k];
    return () => {};
  },
  set(target, k, v) { target[k] = v; return true; },
});
class El {
  constructor(tag) {
    this.tagName = String(tag || 'div').toUpperCase();
    this.attrs = new Map();
    this.style = { setProperty() {}, removeProperty() {} };
    this.children = [];
    this.clientWidth = 400;
    this.clientHeight = 300;
    this.width = 400;
    this.height = 300;
    this.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };
  }
  getContext() { return ctx; }
  setAttribute(k, v) { this.attrs.set(k, String(v)); }
  removeAttribute(k) { this.attrs.delete(k); }
  hasAttribute(k) { return this.attrs.has(k); }
  getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; }
  insertBefore(el) { this.children.push(el); return el; }
  appendChild(el) { this.children.push(el); return el; }
  addEventListener() {}
  removeEventListener() {}
  remove() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 400, height: 300 }; }
  attachShadow() { return new El('shadow'); }
}
const frames = [];  // requestAnimationFrame's waiting functions
const events = [];  // what the page sends Python: its errors, and the answers to questions
Object.assign(globalThis, {
  pywebview: { api: { ready() {}, ev: (_seq, list) => { events.push(...list); return Promise.resolve(); } } },
  window: globalThis,
  document: {
    createElement: (tag) => new El(tag),
    getElementById: () => new El('div'),
    documentElement: new El('html'),
    head: new El('head'),
    body: new El('body'),
    addEventListener() {},
    dispatchEvent() {},
    hasFocus: () => true,
  },
  HTMLElement: class extends El {},
  Element: El,
  Document: class {},
  customElements: { define() {}, get() {} },
  ResizeObserver: class { observe() {} disconnect() {} },
  Image: class {
    constructor() { this.complete = false; this.naturalWidth = 0; this.naturalHeight = 0; }
    set src(v) { this._src = v; this.complete = true; this.naturalWidth = 128; this.naturalHeight = 64; }  // hero_sheet.png
    get src() { return this._src; }
  },
  requestAnimationFrame: (fn) => { frames.push(fn); return frames.length; },
  cancelAnimationFrame() {},
  addEventListener() {},
  removeEventListener() {},
  devicePixelRatio: 1,
  innerWidth: 400,
  innerHeight: 300,
});

await import(pathToFileURL(process.argv[2]).href);
let now = 1000;
function run(seconds) {  // the page's animation frames at 60 a second
  for (let i = 0; i < Math.round(seconds * 60); i++) {
    now += 1000 / 60;
    for (const fn of frames.splice(0)) fn(now);
  }
}
const lastDraw = () => draws[draws.length - 1] || null;
const seen = {};
let seq = 0;
const apply = (cmds) => window.__tv.apply([[++seq, cmds]]);

apply([
  ['c', 1, 'canvas', null, 0, { bg: '#000000', fit: [400, 300] }],
  ['c', 2, 'shape', 'image', 1, { x: 100, y: 100, src: 'asset:hero_sheet.png', w: 64, h: 32 }],
]);
run(0.05);
seen.whole = lastDraw();
apply([['s', 2, { cells: [4, 2], cell: 6, play: null, w: 64, h: 64 }]]);
run(0.05);
seen.cell6 = lastDraw();
apply([['s', 2, { play: [[1, 2, 3, 4], 10, true] }]]);
run(0.25);
seen.walk_025 = lastDraw();
const drawsBefore = draws.length;
apply([['s', 1, { attrs: { 'data-paused': true } }]]);
run(0.05);
const atPause = lastDraw();
run(0.5);
seen.paused_same = JSON.stringify(lastDraw()) === JSON.stringify(atPause);
seen.paused_draws = draws.length - drawsBefore;  // a held picture isn't drawn again and again
apply([['s', 1, { attrs: { 'data-paused': false } }]]);
run(0.15);
seen.after_pause = lastDraw();
apply([['s', 2, { play: null, cell: 7 }]]);
run(0.05);
seen.stopped = lastDraw();
apply([['k', 0, 'stats', [false], 'stats']]);
await new Promise((done) => setTimeout(done, 0));  // events go out after the task that made them
seen.stats = (events.find((e) => e.type === 'reply' && e.tag === 'stats') || {}).value?.flip || null;
seen.errors = events.filter((e) => e.type === 'error').map((e) => `${e.where}: ${e.message}`);
console.log(JSON.stringify(seen));
