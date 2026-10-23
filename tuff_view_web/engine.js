// The page side of tuff_view.py. Python sends batches of commands (create / set / remove / call); this file keeps
// the retained scene they describe (DOM elements, 2D canvases, three.js scenes) and draws it on every animation
// frame, at the display's own rate. Input goes back to Python as batched events.

import * as anim from './anim.js';  // models that move by themselves: swaying trees, spinning coins, walking people, water
import * as fx from './fx.js';      // tgame's effects: a shake, pop text, rain and snow, stars; its clock runs at the game's speed
import './hud.js';  // tgame's HUD: health bars, the countdown, the arrow and the minimap (the <tg-hud> element)
import './interact.js';  // tgame's speech bubbles (npc:say), drawn for Python's view.js as window.tgInteract
import * as level from './level.js';  // tgame's level pieces looking alive: jump pads and boost pads glowing, whooshing

const DEG = Math.PI / 180;
const TAU = Math.PI * 2;
const objs = new Map();              // id -> node
const canvases = new Set();          // 2D canvas nodes
const scenes = new Set();            // three.js scene nodes
const images = new Map();            // src -> Image (2D sprites)
const textures = new Map();          // src + repeat -> THREE.Texture
const geometries = new Map();        // shape + sizes -> THREE.BufferGeometry, shared by every mesh of that size
const batches = [];                  // received from Python, not applied yet (waiting for three.js to load)
const root = document.getElementById('tv-root');
let THREE = null;
let threeLoading = null;

const stats = { since: performance.now(), frames: 0, draws: 0, gaps: [], last: 0, batches: 0, cmds: 0, applyMs: 0, drawMs: 0, seq: 0 };

function node(id) {
  const n = objs.get(id);
  if (!n) throw new Error(`there's no object ${id} (it was never made, or it was removed)`);
  return n;
}

// ---------------------------------------------------------------- applying Python's batches

function apply(list) {
  for (const b of list) batches.push(b);
  pump();
  return batches.length;
}

function pump() {
  const t0 = performance.now();
  while (batches.length) {
    const b = batches[0];
    const cmds = b[1];
    b.i = b.i || 0;
    while (b.i < cmds.length) {
      const c = cmds[b.i];
      if (!THREE && c[0] === 'c' && (c[2] === 'scene' || c[2] === 'obj')) {
        loadThree().then(pump, (err) => { THREE = { failed: err }; report(err, 'loading three.js'); pump(); });
        stats.applyMs += performance.now() - t0;
        return;
      }
      b.i++;
      if (skip(c)) continue;
      try {
        run(c);
      } catch (err) {
        if (c[0] === 'c' && !objs.has(c[1])) broken.add(c[1]);
        report(err, describe(c));
      }
    }
    batches.shift();
    stats.batches++;
    stats.cmds += cmds.length;
    stats.seq = b[0];
  }
  stats.applyMs += performance.now() - t0;
}

// Objects that couldn't be made. Commands for them, and for what goes inside them, are skipped quietly: the one
// error that said why is enough, and a "there's no object" for each of them would bury it.
const broken = new Set();

function skip(c) {
  if (!broken.size) return false;
  if (c[0] === 'c' && broken.has(c[4])) { broken.add(c[1]); return true; }
  if ((c[0] === 's' || (c[0] === 'k' && !c[4])) && broken.has(c[1])) return true;
  if (c[0] === 'r' && broken.has(c[1])) { broken.delete(c[1]); return true; }
  return false;
}

function loadThree() {
  if (!threeLoading) threeLoading = import('./three/three.module.js').then((m) => { THREE = m; });
  return threeLoading;
}

function describe(c) {
  const what = { c: 'making', s: 'changing', r: 'removing', k: 'calling', j: 'running JS' }[c[0]] || c[0];
  return c[0] === 'j' ? what : `${what} object ${c[1]}${c[0] === 'k' ? ` (${c[2]})` : ''}`;
}

function run(c) {
  switch (c[0]) {
    case 's': setProps(node(c[1]), c[2]); break;
    case 'c': create(c[1], c[2], c[3], c[4], c[5]); break;
    case 'r': remove(c[1]); break;
    case 'k': {
      if (!c[4]) { call(c[1], c[2], c[3] || []); break; }
      // An answer for view.ask(): a failure goes back with the answer instead of as an error event.
      let value = null;
      let error = null;
      try {
        value = call(c[1], c[2], c[3] || []);
      } catch (err) {
        error = err && err.message ? err.message : String(err);
      }
      emit('reply', { tag: c[4], value: value === undefined ? null : value, error });
      break;
    }
    case 'j': new Function('tv', c[1])(api); break;
    default: throw new Error(`unknown command ${c[0]}`);
  }
}

// ---------------------------------------------------------------- making and removing objects

function create(id, kind, type, parentId, props) {
  if (objs.has(id)) throw new Error(`object ${id} already exists`);
  let n;
  switch (kind) {
    case 'el': n = { el: document.createElement(type || 'div') }; break;
    case 'canvas': n = makeCanvas(); break;
    case 'shape': n = makeShape(type); break;
    case 'scene': n = makeScene(); break;
    case 'obj': n = makeObj(type); break;
    default: throw new Error(`unknown kind of object '${kind}'`);
  }
  n.id = id;
  n.kind = kind;
  n.type = type;
  n.kids = new Set();
  if (n.el) n.el._tv = id;
  if (n.obj) n.obj.userData.tv = id;
  const parent = parentId ? node(parentId) : null;
  attach(n, parent, props && props.before);
  if (n.kind === 'obj') track(n, true);
  objs.set(id, n);
  if (props) setProps(n, props);
}

// A scene keeps its land, water and sunlight close at hand: the land's colours depend on the water near it, and
// modern lighting changes the lights.
const TRACKED = { terrain: 'lands', water: 'waters', sun: 'suns', hemi: 'hemis' };

function track(n, on) {
  const key = TRACKED[n.type];
  if (!key) return;
  const h = n.host;
  if (!h[key]) h[key] = new Set();
  if (on) h[key].add(n);
  else h[key].delete(n);
  if (n.type === 'water') h.recolor = true;
}

function attach(n, parent, before) {
  if (n.kind === 'shape') {
    if (!parent || parent.kind !== 'canvas') throw new Error('a 2D shape has to go in a canvas');
    n.host = parent;
    parent.shapes.push(n);
    parent.order = parent.dirty = true;
  } else if (n.kind === 'obj') {
    if (!parent || (parent.kind !== 'scene' && parent.kind !== 'obj')) throw new Error('a 3D object has to go in a scene or a group');
    n.host = parent.kind === 'scene' ? parent : parent.host;
    (parent.kind === 'scene' ? parent.scene : parent.obj).add(n.obj);
    if (parent.anim) parent.anim.kids = -1;  // a model that moves by itself (anim.js) looks at its parts again
    n.host.dirty = true;
  } else {
    if (parent && parent.kind !== 'el') throw new Error('elements, canvases and scenes go inside an element (or the window)');
    const into = parent ? parent.el : root;
    into.insertBefore(n.el, before ? node(before).el : null);
  }
  if (n.parent) n.parent.kids.delete(n.id);
  n.parent = parent;
  if (parent) parent.kids.add(n.id);
}

function remove(id) {
  const n = objs.get(id);
  if (!n) return;
  for (const k of [...n.kids]) remove(k);
  objs.delete(id);
  if (n.parent) n.parent.kids.delete(id);
  if (n.phys) { n.dead = true; withPhysics((p) => p.detach(n)); }
  switch (n.kind) {
    case 'shape':
      n.dead = true;
      n.host.prune = n.host.dirty = true;
      break;
    case 'obj':
      n.obj.removeFromParent();
      if (n.parent && n.parent.anim) n.parent.anim.kids = -1;  // (a thing swapped for another of its parts)
      labels.delete(n);
      track(n, false);
      if (n.type === 'label' && n.obj.material.map) n.obj.material.map.dispose();
      if (n.obj.material) n.obj.material.dispose();
      if (n.land || n.water) n.obj.geometry.dispose();  // their own, not shared like a box's
      if (n.skirt) { n.skirt.geometry.dispose(); n.skirt.material.dispose(); }
      if (n.apron) n.apron.geometry.dispose();  // its material is the land's
      if (n.obj.dispose) n.obj.dispose();
      n.host.dirty = true;
      break;
    case 'scene':
      scenes.delete(n);
      n.ro.disconnect();
      if (n.envRT) n.envRT.dispose();
      if (n.pmrem) n.pmrem.dispose();
      n.renderer.dispose();
      n.el.remove();
      break;
    case 'canvas':
      canvases.delete(n);
      n.ro.disconnect();
      n.el.remove();
      break;
    default:
      n.el.remove();
  }
}

function setProps(n, props) {
  switch (n.kind) {
    case 'shape': setShape(n, props); break;
    case 'obj': setObj(n, props); break;
    case 'canvas': setCanvas(n, props); break;
    case 'scene': setScene(n, props); break;
    default: setEl(n.el, props);
  }
}

function call(id, method, args) {
  if (!id) {
    const fn = engineCalls[method];
    if (!fn) throw new Error(`the window has no '${method}'`);
    return fn(...args);
  }
  const n = node(id);
  if (n.kind === 'canvas' && method === 'pick') return pick2d(n, args[0], args[1]);
  if (n.kind === 'scene') {
    if (method === 'pick') return pick3d(n, args.length ? args[0] : null, args.length ? args[1] : null);
    if (method === 'project') return project(n, args[0], args[1], args[2]);
    if (method === 'lock') { const p = n.el.requestPointerLock(); if (p && p.catch) p.catch(() => {}); return null; }
  }
  if (n.kind === 'obj' && method === 'look') { n.obj.lookAt(args[0], args[1], args[2]); n.host.dirty = true; return null; }
  if (n.el && method === 'move') { attach(n, args[0] ? node(args[0]) : null, args[1]); return null; }
  if (n.el && typeof n.el[method] === 'function') return plain(n.el[method](...args));
  throw new Error(`a ${n.kind === 'el' ? n.type : n.kind} has no '${method}'`);
}

function plain(v) {
  if (v === undefined || v === null || typeof v !== 'object') return v === undefined ? null : v;
  if (typeof v.toJSON === 'function') return v.toJSON();
  return Array.isArray(v) || Object.getPrototypeOf(v) === Object.prototype ? v : null;
}

const engineCalls = {
  css(text) { const s = document.createElement('style'); s.textContent = text; document.head.appendChild(s); return null; },
  cursor(value) { document.body.style.cursor = value || ''; return null; },
  unlock() { if (document.pointerLockElement) document.exitPointerLock(); return null; },
  stats(reset) {
    const now = performance.now();
    const gaps = stats.gaps.slice().sort((a, b) => a - b);
    const at = (q) => (gaps.length ? gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))] : 0);
    const secs = (now - stats.since) / 1000;
    const out = {
      seconds: secs, frames: stats.frames, fps: stats.frames / secs, draws: stats.draws,
      gap_median_ms: at(0.5), gap_p95_ms: at(0.95), gap_p99_ms: at(0.99), gap_max_ms: gaps.length ? gaps[gaps.length - 1] : 0,
      batches: stats.batches, cmds: stats.cmds, last_seq: stats.seq,
      apply_ms_per_batch: stats.batches ? stats.applyMs / stats.batches : 0,
      draw_ms_per_frame: stats.frames ? stats.drawMs / stats.frames : 0,
      objects: objs.size, waiting: Math.max(0, batches.length - 1),
      physics: physics ? physics.info() : physicsJob ? 'loading' : null, anim: anim.info(), level: level.info(),
    };
    if (reset) Object.assign(stats, { since: now, frames: 0, draws: 0, gaps: [], batches: 0, cmds: 0, applyMs: 0, drawMs: 0 });
    return out;
  },
  snapshot,
  tones,
  sound,
  sound_stop: soundStop,
  sound_volume: soundVolume,
  sound_state: soundState,
  fx(op, ...args) { return fx.call(op, args); },  // tgame's effects (fx.js)
  // tgame's physics: 'start' loads it (physics.js and Rapier); the rest go to physics.js's OPS, in order.
  physics(op, ...args) {
    if (op === 'start') startPhysics(args[0] || {});
    else withPhysics((p) => p.call(op, args));
    return null;
  },
};

// ---------------------------------------------------------------- physics (physics.js), loaded on first use

let physics = null;           // physics.js, once it and Rapier have loaded
let physicsJob = null;
let physicsFailed = false;    // a step went wrong: it stops (the error was reported)
const physicsWaiting = [];    // what came for it while it loads, in order

function startPhysics(opts) {
  if (physicsJob) return;
  physicsJob = import('./physics.js')
    .then((m) => m.load({ emit, report, node: (id) => objs.get(id), applied: () => stats.seq }, opts))
    .then((m) => {
      physics = m;
      for (const fn of physicsWaiting.splice(0)) runPhysics(fn);
    }, (err) => { physicsWaiting.length = 0; report(err, 'loading physics'); });
}

function withPhysics(fn) {
  if (physics) runPhysics(fn);
  else if (physicsJob) physicsWaiting.push(fn);
}

function runPhysics(fn) {
  try {
    fn(physics);
  } catch (err) {
    report(err, 'physics');
  }
}

// An object's `phys` (what its body is) came, or what it was moved by: physics.js puts its body there.
const PHYS_MOVES = new Set(['x', 'y', 'z', 'rx', 'ry', 'rz', 'rot', 'visible', 'sx', 'sy', 'sz', 'scale', 'wobble']);

function physicsChanged(n, props) {
  if ('phys' in props) {
    n.phys = props.phys;
    withPhysics((p) => p.attach(n));
  }
  if (!n.phys) return;
  for (const k in props) {
    if (PHYS_MOVES.has(k)) { withPhysics((p) => p.moved(n, props)); return; }
  }
}

// ---------------------------------------------------------------- DOM elements

function setEl(el, props) {
  for (const k in props) {
    const v = props[k];
    switch (k) {
      case 'before': break;
      case 'text': el.textContent = v == null ? '' : v; break;
      case 'html': el.innerHTML = v == null ? '' : v; break;
      case 'class': el.className = v == null ? '' : v; break;
      case 'style':
        if (typeof v === 'string') el.style.cssText = v;
        else for (const s in v) {
          if (v[s] == null) el.style.removeProperty(s);
          else if (s.includes('-')) el.style.setProperty(s, v[s]);
          else el.style[s] = v[s];
        }
        break;
      case 'attrs':
        for (const a in v) {
          if (v[a] == null || v[a] === false) el.removeAttribute(a);
          else el.setAttribute(a, v[a] === true ? '' : v[a]);
        }
        break;
      case 'show': el.style.display = v ? '' : 'none'; break;
      default:
        if (k in el) el[k] = v;
        else if (v == null || v === false) el.removeAttribute(k);
        else el.setAttribute(k, v === true ? '' : v);
    }
  }
}

// ---------------------------------------------------------------- 2D canvases

function makeCanvas() {
  const el = document.createElement('canvas');
  el.className = 'tv-canvas';
  const n = { el, ctx: el.getContext('2d'), shapes: [], order: false, prune: false, dirty: true, resized: true,
    bg: null, cx: 0, cy: 0, zoom: 1, fit: null, smooth: true };
  n.ro = new ResizeObserver(() => { n.resized = n.dirty = true; });
  n.ro.observe(el);
  canvases.add(n);
  return n;
}

function setCanvas(n, props) {
  const rest = {};
  for (const k in props) {
    const v = props[k];
    if (k === 'bg') n.bg = v;
    else if (k === 'cx' || k === 'cy' || k === 'zoom') n[k] = +v;
    else if (k === 'fit') n.fit = v && v.length === 2 ? [+v[0], +v[1]] : null;
    else if (k === 'smooth') n.smooth = !!v;
    else rest[k] = v;
  }
  setEl(n.el, rest);
  n.dirty = true;
}

const SHAPE_DEFAULTS = {
  rect: { w: 20, h: 20 }, circle: { r: 10 }, ellipse: { w: 30, h: 20 }, line: { points: [] }, poly: { points: [] },
  text: { text: '', size: 16, font: 'Segoe UI, system-ui, sans-serif', bold: false, ax: 0, ay: 0 }, image: { src: '' },
};

function makeShape(type) {
  if (!SHAPE_DEFAULTS[type]) throw new Error(`there's no 2D shape called '${type}'`);
  const p = { x: 0, y: 0, z: 0, rot: 0, sx: 1, sy: 1, scale: 1, alpha: 1, ax: 0.5, ay: 0.5, color: '#ffffff',
    stroke: null, lw: 1, radius: 0, visible: true, pick: true, frame: null, w: null, h: null, nudge: null, ...SHAPE_DEFAULTS[type] };
  if (type === 'line') p.color = null;
  return { p, fontStr: '', tw: 0 };
}

function setShape(n, props) {
  const p = n.p;
  for (const k in props) {
    const v = props[k];
    if (k === 'phys') continue;
    if (k === 'z' && v !== p.z) n.host.order = true;
    p[k] = v;
    if (k === 'text' || k === 'size' || k === 'font' || k === 'bold') n.fontStr = '';
  }
  if (n.phys || 'phys' in props) physicsChanged(n, props);
  n.host.dirty = true;
}

function image(src) {
  let img = images.get(src);
  if (!img) {
    img = new Image();
    img.onload = () => { for (const c of canvases) c.dirty = true; };
    img.onerror = () => report(new Error(`couldn't load the image ${src}`), 'loading an image');
    img.src = src;
    images.set(src, img);
  }
  return img.complete && img.naturalWidth ? img : null;
}

function fillStroke(ctx, p) {
  if (p.color) { ctx.fillStyle = p.color; ctx.fill(); }
  if (p.stroke) { ctx.lineWidth = p.lw; ctx.strokeStyle = p.stroke; ctx.stroke(); }
}

function textSize(ctx, s) {
  const p = s.p;
  if (!s.fontStr) {
    s.fontStr = `${p.bold ? 'bold ' : ''}${p.size}px ${p.font}`;
    ctx.font = s.fontStr;
    s.tw = ctx.measureText(String(p.text)).width;
  }
  return s.tw;
}

// The box a shape covers in its own (unrotated, unscaled) space, before the anchor is applied.
function shapeSize(ctx, s) {
  const p = s.p;
  switch (s.type) {
    case 'circle': return [Math.max(0, p.r) * 2, Math.max(0, p.r) * 2];
    case 'text': return [textSize(ctx, s), p.size];
    case 'image': {
      const img = images.get(p.src);
      const f = p.frame;
      const nw = f ? f[2] : img && img.naturalWidth ? img.naturalWidth : 0;
      const nh = f ? f[3] : img && img.naturalHeight ? img.naturalHeight : 0;
      return [p.w == null ? nw : p.w, p.h == null ? nh : p.h];
    }
    default: return [p.w, p.h];
  }
}

function view2d(n) {
  const r = window.devicePixelRatio || 1;
  let k = n.zoom * r;
  let ox = 0;
  let oy = 0;
  if (n.fit) {
    const f = Math.min(n.el.width / n.fit[0], n.el.height / n.fit[1]);
    k = f * n.zoom;
    ox = (n.el.width - n.fit[0] * f) / 2;
    oy = (n.el.height - n.fit[1] * f) / 2;
  }
  return [k, ox - n.cx * k, oy - n.cy * k];
}

function draw2d(n) {
  const el = n.el;
  const ctx = n.ctx;
  if (n.resized) {
    const r = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.round(el.clientWidth * r));
    const h = Math.max(1, Math.round(el.clientHeight * r));
    if (el.width !== w) el.width = w;
    if (el.height !== h) el.height = h;
    n.resized = false;
  }
  if (n.prune) { n.shapes = n.shapes.filter((s) => !s.dead); n.prune = false; }
  if (n.order) { n.shapes.sort((a, b) => a.p.z - b.p.z || a.id - b.id); n.order = false; }
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  if (n.bg) { ctx.fillStyle = n.bg; ctx.fillRect(0, 0, el.width, el.height); } else ctx.clearRect(0, 0, el.width, el.height);
  ctx.imageSmoothingEnabled = n.smooth;
  const [k, ox, oy] = view2d(n);
  for (const s of n.shapes) {
    if (!s.p.visible || s.dead) continue;
    // One shape that can't be drawn mustn't hide the ones after it. Its error is reported once, not every frame.
    try {
      drawShape(ctx, s, k, ox, oy);
    } catch (err) {
      if (!s.failed) { s.failed = true; report(err, `drawing object ${s.id}`); }
    }
  }
}

function drawShape(ctx, s, k, ox, oy) {
  const p = s.p;
  const a = p.rot * DEG;
  const cos = Math.cos(a);
  const sin = Math.sin(a);
  const sx = p.sx * p.scale * k;
  const sy = p.sy * p.scale * k;
  const nx = p.nudge ? +p.nudge[0] || 0 : 0;  // drawn this far from where it is (a shake of a thing physics moves)
  const ny = p.nudge ? +p.nudge[1] || 0 : 0;
  ctx.setTransform(cos * sx, sin * sx, -sin * sy, cos * sy, ox + (p.x + nx) * k, oy + (p.y + ny) * k);
  ctx.globalAlpha = p.alpha;
  switch (s.type) {
    case 'rect': {
      const x = -p.ax * p.w;
      const y = -p.ay * p.h;
      if (p.radius) {
        ctx.beginPath();
        ctx.roundRect(x, y, p.w, p.h, Math.max(0, p.radius));
        fillStroke(ctx, p);
      } else {
        if (p.color) { ctx.fillStyle = p.color; ctx.fillRect(x, y, p.w, p.h); }
        if (p.stroke) { ctx.lineWidth = p.lw; ctx.strokeStyle = p.stroke; ctx.strokeRect(x, y, p.w, p.h); }
      }
      break;
    }
    case 'circle': {
      const r = Math.max(0, p.r);  // a circle shrunk below 0 draws nothing (the canvas throws on a negative radius)
      ctx.beginPath();
      ctx.arc((0.5 - p.ax) * 2 * r, (0.5 - p.ay) * 2 * r, r, 0, TAU);
      fillStroke(ctx, p);
      break;
    }
    case 'ellipse':
      ctx.beginPath();
      ctx.ellipse((0.5 - p.ax) * p.w, (0.5 - p.ay) * p.h, Math.max(0, p.w / 2), Math.max(0, p.h / 2), 0, 0, TAU);
      fillStroke(ctx, p);
      break;
    case 'line':
    case 'poly': {
      const pts = p.points;
      if (!pts || pts.length < 2) break;
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      if (s.type === 'poly') {
        ctx.closePath();
        if (p.color) { ctx.fillStyle = p.color; ctx.fill(); }
      }
      if (p.stroke || s.type === 'line') {
        ctx.lineWidth = p.lw;
        ctx.lineCap = ctx.lineJoin = 'round';
        ctx.strokeStyle = p.stroke || p.color || '#ffffff';
        ctx.stroke();
      }
      break;
    }
    case 'text': {
      const w = textSize(ctx, s);
      ctx.font = s.fontStr;
      ctx.textBaseline = 'top';
      ctx.fillStyle = p.color;
      ctx.fillText(String(p.text), -p.ax * w, -p.ay * p.size);
      break;
    }
    case 'image': {
      const img = image(p.src);
      if (!img) break;
      const [w, h] = shapeSize(ctx, s);
      const f = p.frame;
      if (f) ctx.drawImage(img, f[0], f[1], f[2], f[3], -p.ax * w, -p.ay * h, w, h);
      else ctx.drawImage(img, -p.ax * w, -p.ay * h, w, h);
      break;
    }
  }
}

// The topmost shape under a point given in CSS pixels from the canvas's top-left corner.
function pick2d(n, x, y) {
  const r = window.devicePixelRatio || 1;
  const [k, ox, oy] = view2d(n);
  const wx = (x * r - ox) / k;
  const wy = (y * r - oy) / k;
  for (let i = n.shapes.length - 1; i >= 0; i--) {
    const s = n.shapes[i];
    const p = s.p;
    if (s.dead || !p.visible || !p.pick) continue;
    const a = -p.rot * DEG;
    const dx = wx - p.x;
    const dy = wy - p.y;
    const lx = (dx * Math.cos(a) - dy * Math.sin(a)) / (p.sx * p.scale || 1);
    const ly = (dx * Math.sin(a) + dy * Math.cos(a)) / (p.sy * p.scale || 1);
    let hit;
    if (s.type === 'line' || s.type === 'poly') {
      const pts = p.points || [];
      const pad = p.lw / 2 + 2;
      hit = pts.length > 1 && lx >= Math.min(...pts.map((q) => q[0])) - pad && lx <= Math.max(...pts.map((q) => q[0])) + pad
        && ly >= Math.min(...pts.map((q) => q[1])) - pad && ly <= Math.max(...pts.map((q) => q[1])) + pad;
    } else {
      const [w, h] = shapeSize(n.ctx, s);
      const x0 = -p.ax * w;
      const y0 = -p.ay * h;
      if (s.type === 'circle' || s.type === 'ellipse') {
        const ex = (lx - x0 - w / 2) / (w / 2);
        const ey = (ly - y0 - h / 2) / (h / 2);
        hit = ex * ex + ey * ey <= 1;
      } else hit = lx >= x0 && lx <= x0 + w && ly >= y0 && ly <= y0 + h;
    }
    if (hit) return { id: s.id, x: wx, y: wy };
  }
  return { id: null, x: wx, y: wy };
}

// ---------------------------------------------------------------- three.js scenes

function makeScene() {
  if (!THREE || THREE.failed) throw new Error("three.js couldn't be loaded, so 3D scenes can't be shown");
  const el = document.createElement('canvas');
  el.className = 'tv-canvas';
  el.tabIndex = -1;
  const renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, 1, 0.1, 1000);
  camera.rotation.order = 'YXZ';
  scene.add(camera);
  const n = { el, renderer, scene, camera, dirty: true, resized: true, yaw: 0, pitch: 0, roll: 0, ray: null };
  n.ro = new ResizeObserver(() => { n.resized = n.dirty = true; });
  n.ro.observe(el);
  scenes.add(n);
  return n;
}

function color(v) {
  return new THREE.Color(v);
}

function setScene(n, props) {
  const cam = n.camera;
  const rest = {};
  let lens = false;
  for (const k in props) {
    const v = props[k];
    switch (k) {
      case 'bg': n.scene.background = v == null ? null : color(v); n.envDirty = true; break;
      case 'fog': n.scene.fog = v ? new THREE.Fog(color(v[0]), v[1], v[2]) : null; break;
      case 'fov': cam.fov = v; lens = true; break;
      case 'near': cam.near = v; lens = true; break;
      case 'far': cam.far = v; lens = true; break;
      case 'cx': cam.position.x = v; break;
      case 'cy': cam.position.y = v; break;
      case 'cz': cam.position.z = v; break;
      case 'yaw': case 'pitch': case 'roll':
        n[k] = v;
        cam.rotation.set(n.pitch * DEG, n.yaw * DEG, n.roll * DEG, 'YXZ');
        break;
      case 'look':
        cam.lookAt(v[0], v[1], v[2]);
        n.yaw = cam.rotation.y / DEG;
        n.pitch = cam.rotation.x / DEG;
        n.roll = cam.rotation.z / DEG;
        break;
      case 'shadows':
        n.renderer.shadowMap.enabled = !!v;
        n.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        break;
      case 'sky': setSky(n, v); break;
      case 'clicklock': n.clicklock = !!v; break;
      case 'lighting': setLighting(n, v); break;
      default: rest[k] = v;
    }
  }
  if (lens) cam.updateProjectionMatrix();
  setEl(n.el, rest);
  n.dirty = true;
}

// A gradient sky: a dome around the camera, [top, horizon] or [top, horizon, below], drawn behind everything.
function setSky(n, v) {
  n.envDirty = true;  // modern lighting's light from the sky changes with it
  if (!v) {
    if (n.sky) { n.sky.removeFromParent(); n.sky.material.dispose(); n.sky = null; }
    return;
  }
  if (!n.sky) {
    const material = new THREE.ShaderMaterial({
      uniforms: { top: { value: new THREE.Color() }, mid: { value: new THREE.Color() }, low: { value: new THREE.Color() } },
      vertexShader: 'varying vec3 vDir;\nvoid main() { vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: 'uniform vec3 top; uniform vec3 mid; uniform vec3 low; varying vec3 vDir;\n'
        + 'void main() { float h = normalize(vDir).y; vec3 c = h > 0.0 ? mix(mid, top, pow(h, 0.55)) : mix(mid, low, pow(-h, 0.35));\n'
        + 'gl_FragColor = vec4(c, 1.0);\n#include <colorspace_fragment>\n}',
      side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false,
    });
    n.sky = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), material);
    n.sky.renderOrder = -1e6;
    n.sky.frustumCulled = false;
    n.sky.raycast = () => {};
    n.scene.add(n.sky);
  }
  const u = n.sky.material.uniforms;
  u.top.value.set(v[0]);
  u.mid.value.set(v[1] || v[0]);
  u.low.value.set(v[2] || v[1] || v[0]);
}

// Lighting: 'simple' (the default: worlds look the way they always have) or 'modern': ACES filmic tone mapping, soft
// light from the sky itself (an environment map made from the gradient sky, which shiny things like water also
// reflect), a softer hemisphere light, and sun shadows that follow the camera, sized to what it looks at. If the
// graphics can't do part of it, the scene quietly stays simple.
const MODERN = { exposure: 0.78, hemi: 0.35, sun: 1.3, env: 0.6 };

function setLighting(n, v) {
  n.modern = v === 'modern';
  try {
    applyLighting(n);
  } catch {
    n.modern = false;
    applyLighting(n);
  }
}

function lightScale(l) {
  if (!l.host || !l.host.modern) return 1;
  return l.type === 'hemi' ? MODERN.hemi : l.type === 'sun' ? MODERN.sun : 1;
}

function applyLighting(n) {
  const r = n.renderer;
  r.toneMapping = n.modern ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
  r.toneMappingExposure = n.modern ? MODERN.exposure : 1;
  if (!n.modern) {
    n.scene.environment = null;
    if (n.envRT) { n.envRT.dispose(); n.envRT = null; }
  }
  n.envDirty = n.modern;
  for (const l of n.hemis || []) l.obj.intensity = l.p.intensity * lightScale(l);
  for (const l of n.suns || []) {
    l.obj.intensity = l.p.intensity * lightScale(l);
    if (!n.modern) simpleSun(l);
  }
  n.dirty = true;
}

// The environment map: the sky dome (or the plain background colour) seen from the middle, blurred by PMREM.
function makeEnvironment(n) {
  n.envDirty = false;
  const env = new THREE.Scene();
  if (n.sky) env.add(new THREE.Mesh(n.sky.geometry, n.sky.material));
  else if (n.scene.background && n.scene.background.isColor) env.background = n.scene.background.clone();
  else {
    n.scene.environment = null;
    return;
  }
  if (!n.pmrem) n.pmrem = new THREE.PMREMGenerator(n.renderer);
  const rt = n.pmrem.fromScene(env, 0.04, 0.1, 100);
  if (n.envRT) n.envRT.dispose();
  n.envRT = rt;
  n.scene.environment = rt.texture;
  n.scene.environmentIntensity = MODERN.env;
}

// The sun as Python put it: where it is (`at`), aimed at the middle of the world, its shadows `area` around that.
function simpleSun(l) {
  const o = l.obj;
  o.position.fromArray(l.at);
  o.target.position.set(0, 0, 0);
  o.target.updateMatrixWorld();
  const c = o.shadow.camera;
  const a = l.p.area || 5;
  c.left = c.bottom = -a;
  c.right = c.top = a;
  c.near = 0.5;
  c.far = 500;
  c.updateProjectionMatrix();
  o.shadow.normalBias = 0.03;
}

// Modern: the sun's shadows cover what the camera looks at. Its light keeps the direction Python gave it, and its
// shadow box moves with the camera, bigger the further away the camera looks (an editor's view from high up gets
// the whole land; a player's eye gets sharp shadows close by). Moves snap to the shadow map's pixels, so the
// shadows' edges don't crawl while the camera moves.
const sunWork = {};

function followSun(n, l) {
  const o = l.obj;
  const cam = n.camera;
  const fwd = sunWork.fwd || (sunWork.fwd = new THREE.Vector3());
  const dir = sunWork.dir || (sunWork.dir = new THREE.Vector3());
  cam.updateMatrixWorld();
  cam.getWorldDirection(fwd);
  const hit = landHit(n, cam.position, fwd);
  const flat = Math.hypot(fwd.x, fwd.z) || 1;
  let area = 45;
  let ahead = area * 0.5;
  if (hit != null) {
    area = Math.min(180, Math.max(area, Math.ceil(hit * 0.9 / 15) * 15));
    ahead = Math.min(hit * flat, area * 0.5);
  }
  const texel = (2 * area) / o.shadow.mapSize.x;
  const cx = Math.round((cam.position.x + (fwd.x / flat) * ahead) / texel) * texel;
  const cz = Math.round((cam.position.z + (fwd.z / flat) * ahead) / texel) * texel;
  const cy = groundAt(n, cx, cz);
  dir.fromArray(l.at).normalize();
  o.target.position.set(cx, cy, cz);
  o.target.updateMatrixWorld();
  o.position.set(cx + dir.x * 250, cy + dir.y * 250, cz + dir.z * 250);
  const c = o.shadow.camera;
  if (c.right !== area || c.far !== 600) {
    c.left = c.bottom = -area;
    c.right = c.top = area;
    c.near = 1;
    c.far = 600;
    c.updateProjectionMatrix();
  }
  o.shadow.normalBias = Math.max(0.03, texel * 0.8);
}

// How far along a ray (from o, direction d) the land is, or null when it doesn't reach the land within 400 m.
function landHit(n, o, d) {
  if (o.y <= groundAt(n, o.x, o.z)) return 0;
  for (let t = 0.3; t < 400; t += Math.max(0.5, t * 0.05)) {
    if (o.y + d.y * t <= groundAt(n, o.x + d.x * t, o.z + d.z * t)) return t;
  }
  return null;
}

function groundAt(n, x, z) {
  if (n.lands) for (const t of n.lands) return landHeight(t, x, z);
  return 0;
}

const MESHES = new Set(['box', 'sphere', 'plane', 'cylinder', 'cone', 'torus', 'capsule']);
const GEO_KEYS = new Set(['w', 'h', 'd', 'r', 'rt', 'rb', 'tube', 'seg']);
const MAT_KEYS = new Set(['color', 'opacity', 'emissive', 'rough', 'metal', 'wireframe', 'flat', 'mat', 'texture', 'repeat', 'side']);
const OBJ_DEFAULTS = {
  box: { w: 1, h: 1, d: 1 }, sphere: { r: 0.5, seg: 24 }, plane: { w: 1, h: 1 }, cylinder: { rt: 0.5, rb: 0.5, h: 1, seg: 24 },
  cone: { r: 0.5, h: 1, seg: 24 }, torus: { r: 0.5, tube: 0.15, seg: 32 }, capsule: { r: 0.3, h: 1, seg: 12 },
};

function makeObj(type) {
  if (!THREE || THREE.failed) throw new Error("three.js couldn't be loaded, so 3D objects can't be shown");
  const p = { color: '#cccccc', opacity: 1, emissive: null, rough: 0.8, metal: 0, wireframe: false, flat: false, mat: 'standard',
    texture: null, repeat: null, side: 'front', ...(OBJ_DEFAULTS[type] || {}) };
  let obj;
  if (MESHES.has(type)) {
    obj = new THREE.Mesh(geometry(type, p), null);
  } else switch (type) {
    case 'group': obj = new THREE.Group(); break;
    case 'ambient': obj = new THREE.AmbientLight(0xffffff, 0.4); break;
    case 'hemi': obj = new THREE.HemisphereLight(0xddeeff, 0x445533, 0.8); break;
    case 'sun':
      obj = new THREE.DirectionalLight(0xffffff, 2.5);
      obj.position.set(5, 10, 4);
      obj.shadow.mapSize.set(2048, 2048);
      obj.shadow.bias = -0.0004;      // no stripes ("shadow acne") on flat ground
      obj.shadow.normalBias = 0.03;
      break;
    case 'point': obj = new THREE.PointLight(0xffffff, 10, 0, 2); break;
    case 'label': return makeLabel(p);
    case 'model': obj = new THREE.Group(); break;
    case 'terrain': return makeLand();
    case 'water': return makeWater();
    default: throw new Error(`there's no 3D object called '${type}'`);
  }
  const n = { obj, p, pick: true };
  if (obj.isMesh) material(n);
  if (obj.isLight) p.intensity = obj.intensity;  // what Python asked for: modern lighting scales some lights
  if (type === 'sun') n.at = [5, 10, 4];          // where Python put the sun (modern lighting moves the light itself)
  return n;
}

// A text label that always faces the camera: `text`, `h` (height in world units), `color`, `bg` (a CSS colour or
// null), `ontop` (drawn over everything), `px` (the most it grows to on screen, in CSS pixels, so a label up close
// doesn't fill the view). Its position is the middle of its bottom edge.
const LABEL_KEYS = new Set(['text', 'h', 'color', 'bg', 'bold']);
const labels = new Set();

function makeLabel(p) {
  Object.assign(p, { text: '', h: 0.45, color: '#ffffff', bg: 'rgba(10,12,18,0.55)', bold: true, px: 30 });
  const obj = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthWrite: false }));
  obj.center.set(0.5, 0);
  const n = { obj, p, pick: false };
  drawLabel(n);
  labels.add(n);
  return n;
}

const labelAt = { v: null };

function sizeLabels(n) {
  if (!labels.size) return;
  const cam = n.camera;
  const v = labelAt.v || (labelAt.v = new THREE.Vector3());
  const perPx = 2 * Math.tan((cam.fov * DEG) / 2) / Math.max(1, n.el.clientHeight);
  for (const l of labels) {
    if (l.host !== n || !l.obj.visible) continue;
    l.obj.getWorldPosition(v);
    const dist = Math.max(0.01, v.distanceTo(cam.position));
    const h = Math.min(l.p.h, (l.p.px || 1e9) * perPx * dist);
    l.obj.scale.set(h * l.aspect, h, 1);
  }
}

function drawLabel(n) {
  const p = n.p;
  // A canvas texture can't change size once it's on the GPU, so a new text gets a new canvas.
  const c = n.canvas = document.createElement('canvas');
  const g = c.getContext('2d');
  const font = `${p.bold ? 'bold ' : ''}48px Segoe UI, system-ui, sans-serif`;
  g.font = font;
  const text = String(p.text ?? '');
  c.width = Math.max(8, Math.ceil(g.measureText(text).width) + 36);
  c.height = 72;
  g.font = font;
  if (p.bg) {
    g.fillStyle = p.bg;
    g.beginPath();
    g.roundRect(0, 0, c.width, c.height, 18);
    g.fill();
  }
  g.fillStyle = p.color;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(text, c.width / 2, c.height / 2 + 2);
  const m = n.obj.material;
  if (m.map) m.map.dispose();
  m.map = new THREE.CanvasTexture(c);
  m.map.colorSpace = THREE.SRGBColorSpace;
  m.needsUpdate = true;
  n.aspect = c.width / c.height;
  n.obj.scale.set(p.h * n.aspect, p.h, 1);
}

// ---------------------------------------------------------------- the land (tgame's world:terrain) and water

// A 'terrain' is a square of land centred on its position: `size` (metres across), `n` (points along each side),
// `heights` (n * n of them, row by row from -z to +z, each row from -x to +x; left out, it's flat) and `style`.
// Each point gets its colour from the style by its height and slope: sand by the water, rock on steep slopes and
// high up, snow on the peaks, the style's own colours in soft patches everywhere else, a little darker in hollows.
// A soft noise texture over all of it gives it grain. It casts and catches shadows, and can be picked.
const LAND_KEYS = new Set(['size', 'n', 'heights', 'style']);
const LAND_STYLES = {
  // main: three colours, in big and small patches; shore: by the water; bed: under it; rock: on steep slopes, and
  // more of it from `rockline` up; snow: from `snowline` up (none for desert and autumn; the snow style is all snow)
  grass: { main: ['#5a9838', '#7aa843', '#477f30'], shore: '#d8c58e', bed: '#77694c', rock: '#8a847a', rockline: 10, snow: '#f2f5f8', snowline: 17 },
  desert: { main: ['#dcb57a', '#cfa266', '#e6c793'], shore: '#8aa14e', bed: '#9b845a', rock: '#ad7250', rockline: 14, snow: null, snowline: 0 },
  snow: { main: ['#eef2f6', '#dde5ed', '#f8fafc'], shore: '#c7d1d9', bed: '#5d6970', rock: '#7b7e85', rockline: 1e9, snow: null, snowline: 0 },
  rocky: { main: ['#8a867c', '#9b968a', '#6b8146'], shore: '#c4b48c', bed: '#5f5a50', rock: '#6c675f', rockline: 4, snow: '#f2f5f8', snowline: 13 },
  autumn: { main: ['#b9893a', '#c77537', '#8e7d39'], shore: '#d8c58e', bed: '#77694c', rock: '#857b6e', rockline: 12, snow: null, snowline: 0 },
};
const palettes = new Map(); // style -> its colours as THREE.Colors
let landGrain = null;       // the detail texture, made once

function makeLand() {
  const p = { size: 100, n: 2, heights: null, style: 'grass' };
  const m = new THREE.MeshStandardMaterial({ vertexColors: true, map: landTexture(), roughness: 0.93, metalness: 0 });
  m.color.setScalar(1.22);  // the grain darkens a little on average: this evens it out
  const obj = new THREE.Mesh(new THREE.BufferGeometry(), m);
  obj.castShadow = obj.receiveShadow = true;
  const n = { obj, p, pick: true, land: true, grid: null };
  obj.raycast = (rc, hits) => rayLand(n, rc, hits);
  buildLand(n);
  return n;
}

// New heights: only the rows and columns between the first and last point that changed are worked out again (their
// normals and colours) and sent to the GPU, so a brush that paints, or a game that digs, stays quick on a big land.
function buildLand(n) {
  const p = n.p;
  const N = Math.max(2, Math.min(1025, Math.round(+p.n) || 2));
  const size = Math.max(0.01, +p.size || 1);
  let g = n.obj.geometry;
  const fresh = !n.grid || n.grid.N !== N || n.grid.size !== size;
  if (fresh) {
    g.dispose();
    g = new THREE.PlaneGeometry(size, size, N - 1, N - 1);
    g.rotateX(-Math.PI / 2);  // rows now go from -z to +z, each from -x to +x, like the heights
    const uv = g.attributes.uv.array;
    for (let i = 0; i < uv.length; i++) uv[i] *= size / 8;  // the grain repeats every 8 m
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * N * 3), 3));
    n.obj.geometry = g;
    n.grid = { N, size, step: size / (N - 1), lo: 0, hi: 0, bottom: null };
    const pos = g.attributes.position.array;
    n.grid.noise = new Float32Array(N * N * 2);  // each point's two patch noises: they never change
    for (let k = 0; k < N * N; k++) {
      n.grid.noise[k * 2] = bigPatches(pos[k * 3], pos[k * 3 + 2]);
      n.grid.noise[k * 2 + 1] = smallPatches(pos[k * 3], pos[k * 3 + 2]);
    }
  }
  const pos = g.attributes.position.array;
  const hs = p.heights;
  let i0 = N;
  let i1 = -1;
  let j0 = N;
  let j1 = -1;
  let lo = Infinity;
  let hi = -Infinity;
  for (let j = 0, k = 0; j < N; j++) {
    for (let i = 0; i < N; i++, k++) {
      const h = Math.fround(hs ? +hs[k] || 0 : 0);
      if (h < lo) lo = h;
      if (h > hi) hi = h;
      if (fresh || pos[k * 3 + 1] !== h) {
        pos[k * 3 + 1] = h;
        if (i < i0) i0 = i;
        if (i > i1) i1 = i;
        if (j < j0) j0 = j;
        if (j > j1) j1 = j;
      }
    }
  }
  const restyle = n.restyle;
  n.restyle = false;
  if (i1 < 0) {  // the same heights: maybe a new style
    if (restyle) colorLand(n, 0, N - 1, 0, N - 1);
    return;
  }
  const grid = n.grid;
  grid.lo = lo;
  grid.hi = hi;
  const half = size / 2;
  g.boundingBox = new THREE.Box3(new THREE.Vector3(-half, lo, -half), new THREE.Vector3(half, hi, half));
  g.boundingSphere = g.boundingBox.getBoundingSphere(new THREE.Sphere());
  const a = Math.max(0, i0 - 1);
  const b = Math.min(N - 1, i1 + 1);
  const c = Math.max(0, j0 - 1);
  const d = Math.min(N - 1, j1 + 1);
  landNormals(n, a, b, c, d);
  for (const name of ['position', 'normal']) {
    if (!fresh) g.attributes[name].addUpdateRange(c * N * 3, (d - c + 1) * N * 3);
    g.attributes[name].needsUpdate = true;
  }
  if (restyle) colorLand(n, 0, N - 1, 0, N - 1);
  else colorLand(n, Math.max(0, i0 - 3), Math.min(N - 1, i1 + 3), Math.max(0, j0 - 3), Math.min(N - 1, j1 + 3));
  const bottom = lo - Math.max(2, size * 0.04);
  if (fresh || grid.bottom !== bottom || i0 === 0 || j0 === 0 || i1 === N - 1 || j1 === N - 1) {
    grid.bottom = bottom;
    buildSkirt(n, pos, N, bottom);
  }
}

// Each point's normal, from the slope of the land around it.
function landNormals(n, i0, i1, j0, j1) {
  const { N, step } = n.grid;
  const g = n.obj.geometry;
  const pos = g.attributes.position.array;
  const nor = g.attributes.normal.array;
  for (let j = j0; j <= j1; j++) {
    const ja = j > 0 ? j - 1 : j;
    const jb = j < N - 1 ? j + 1 : j;
    for (let i = i0; i <= i1; i++) {
      const ia = i > 0 ? i - 1 : i;
      const ib = i < N - 1 ? i + 1 : i;
      const dx = (pos[(j * N + ib) * 3 + 1] - pos[(j * N + ia) * 3 + 1]) / ((ib - ia) * step);
      const dz = (pos[(jb * N + i) * 3 + 1] - pos[(ja * N + i) * 3 + 1]) / ((jb - ja) * step);
      const l = Math.sqrt(dx * dx + 1 + dz * dz);
      const k = (j * N + i) * 3;
      nor[k] = -dx / l;
      nor[k + 1] = 1 / l;
      nor[k + 2] = -dz / l;
    }
  }
}

// The land's height at x, z in its own space (between its four nearest points), from its positions.
function gridHeight(grid, pos, x, z) {
  const { N, size, step } = grid;
  const fx = Math.min(N - 1, Math.max(0, (x + size / 2) / step));
  const fz = Math.min(N - 1, Math.max(0, (z + size / 2) / step));
  const i = Math.min(Math.floor(fx), N - 2);
  const j = Math.min(Math.floor(fz), N - 2);
  const tx = fx - i;
  const tz = fz - j;
  const k = j * N + i;
  const a = pos[k * 3 + 1];
  const b = pos[(k + 1) * 3 + 1];
  const c = pos[(k + N) * 3 + 1];
  const d = pos[(k + N + 1) * 3 + 1];
  return a + (b - a) * tx + (c - a) * tz + (a - b - c + d) * tx * tz;
}

// Picking the land: walk along the ray over the heights (half a grid step at a time) instead of testing every
// triangle, then home in on where it crosses. Quick enough for a brush that picks on every mouse move.
function rayLand(n, rc, hits) {
  const grid = n.grid;
  if (!grid) return;
  const pos = n.obj.geometry.attributes.position.array;
  const half = grid.size / 2;
  const o = n.obj.position;  // the land moves, but never turns or grows
  const ray = rc.ray;
  const ox = ray.origin.x - o.x;
  const oy = ray.origin.y - o.y;
  const oz = ray.origin.z - o.z;
  const { x: dx, y: dy, z: dz } = ray.direction;
  let t0 = rc.near;
  let t1 = rc.far;
  for (const [org, dir, a, b] of [[ox, dx, -half, half], [oy, dy, grid.lo - 0.01, grid.hi + 0.01], [oz, dz, -half, half]]) {
    if (Math.abs(dir) < 1e-12) {
      if (org < a || org > b) return;
      continue;
    }
    const ta = (a - org) / dir;
    const tb = (b - org) / dir;
    t0 = Math.max(t0, Math.min(ta, tb));
    t1 = Math.min(t1, Math.max(ta, tb));
    if (t0 > t1) return;
  }
  const above = (t) => oy + dy * t - gridHeight(grid, pos, ox + dx * t, oz + dz * t);
  if (above(t0) < 0) return;  // it starts under the land
  const st = grid.step * 0.5;
  for (let ta = t0; ta < t1;) {
    const tb = Math.min(ta + st, t1);
    if (above(tb) <= 0) {
      let a = ta;
      let b = tb;
      for (let q = 0; q < 14; q++) {
        const m = (a + b) / 2;
        if (above(m) > 0) a = m;
        else b = m;
      }
      hits.push({ distance: b, point: new THREE.Vector3(ray.origin.x + dx * b, ray.origin.y + dy * b, ray.origin.z + dz * b),
        object: n.obj, face: null, faceIndex: null });
      return;
    }
    ta = tb;
  }
}

// The land's sides: earth going down from its edges, so from afar it's a solid piece of land, not a sheet.
function buildSkirt(n, pos, N, bottom) {
  if (!n.skirt) {
    n.skirt = new THREE.Mesh(new THREE.BufferGeometry(),
      new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0, side: THREE.DoubleSide }));
    n.skirt.castShadow = n.skirt.receiveShadow = true;
    n.obj.add(n.skirt);
  }
  let g = n.skirt.geometry;
  const count = (N - 1) * 4 * 6;
  if (!g.attributes.position || g.attributes.position.count !== count) {  // a new size: a new geometry (no stale buffers)
    g.dispose();
    g = n.skirt.geometry = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  }
  const out = g.attributes.position.array;
  const col = g.attributes.color.array;
  const top = new THREE.Color('#6e5436');
  const low = new THREE.Color('#33281d');
  let at = 0;
  const corner = (k, y, c) => {
    out[at] = pos[k * 3]; out[at + 1] = y; out[at + 2] = pos[k * 3 + 2];
    col[at] = c.r; col[at + 1] = c.g; col[at + 2] = c.b;
    at += 3;
  };
  for (let side = 0; side < 4; side++) {
    for (let q = 0; q + 1 < N; q++) {
      const a = side === 0 ? q : side === 1 ? (N - 1) * N + q : side === 2 ? q * N : q * N + N - 1;
      const b = side === 0 ? q + 1 : side === 1 ? (N - 1) * N + q + 1 : side === 2 ? (q + 1) * N : (q + 1) * N + N - 1;
      corner(a, pos[a * 3 + 1], top); corner(b, pos[b * 3 + 1], top); corner(b, bottom, low);
      corner(a, pos[a * 3 + 1], top); corner(b, bottom, low); corner(a, bottom, low);
    }
  }
  g.attributes.position.needsUpdate = true;
  g.attributes.color.needsUpdate = true;
  g.computeVertexNormals();
  g.computeBoundingSphere();
}

function palette(style) {
  let pal = palettes.get(style);
  if (!pal) {
    const s = LAND_STYLES[style] || LAND_STYLES.grass;
    const c = (hex) => (hex ? new THREE.Color(hex) : null);
    pal = { ...s, main: s.main.map(c), shore: c(s.shore), bed: c(s.bed), rock: c(s.rock), snow: c(s.snow) };
    palettes.set(style, pal);
  }
  return pal;
}

function smooth01(a, b, x) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

// The water near the land: [x, z, level, r (0: a sea)], in the land's own space.
function landWaters(n) {
  const o = n.obj.position;
  const waters = [];
  for (const w of (n.host && n.host.waters) || []) {
    if (w.obj.visible) waters.push([w.obj.position.x - o.x, w.obj.position.z - o.z, w.obj.position.y - o.y, +w.p.r || 0]);
  }
  return waters;
}

// Colours the points from k0 to k1 in the style s, by where they are (pos), how steep (their normals) and how they
// curve (curveOf(k): above or below the land around it). `noise`, if given, has each point's two patch noises.
function paintLand(s, pos, nor, k0, k1, curveOf, waters, out, noise) {
  const [m0, m1, m2] = s.main;
  let r = 0;
  let gr = 0;
  let b = 0;
  const mix = (c, t) => { if (t > 0) { r += (c.r - r) * t; gr += (c.g - gr) * t; b += (c.b - b) * t; } };
  for (let k = k0; k <= k1; k++) {
    const x = pos[k * 3];
    const h = pos[k * 3 + 1];
    const z = pos[k * 3 + 2];
    const slope = 1 - nor[k * 3 + 1];  // 0 flat, 1 a wall
    const big = noise ? noise[k * 2] : bigPatches(x, z);
    const small = noise ? noise[k * 2 + 1] : smallPatches(x, z);
    r = m0.r; gr = m0.g; b = m0.b;
    mix(m1, smooth01(0.3, 0.75, big));
    mix(m2, smooth01(0.5, 0.9, small) * 0.55);
    let shore = 0;
    let bed = 0;
    for (const [wx, wz, wy, wr] of waters) {
      const near = wr > 0 ? 1 - smooth01(wr * 1.02, wr * 1.15, Math.hypot(x - wx, z - wz) + (small - 0.5) * wr * 0.12) : 1;
      if (near <= 0) continue;
      shore = Math.max(shore, near * (1 - smooth01(wy + 0.12, wy + 0.45 + small * 0.5, h)));
      bed = Math.max(bed, near * smooth01(wy - 0.2, wy - 1.8, h));
    }
    mix(s.shore, shore);
    mix(s.bed, bed);
    // Rock in layers: bands of lighter and darker stone up the slope.
    const rock = Math.max(smooth01(0.2, 0.36, slope + (small - 0.5) * 0.12),
      smooth01(s.rockline, s.rockline + 5, h + (big - 0.5) * 6) * 0.85);
    mix(s.rock, rock);
    if (rock > 0) {
      const band = 0.84 + 0.2 * (0.5 + 0.5 * Math.sin(h * 1.1 + big * 7)) * (0.6 + 0.4 * small);
      const f = 1 + (band - 1) * rock;
      r *= f; gr *= f; b *= f;
    }
    if (s.snow) mix(s.snow, smooth01(s.snowline - 1.5, s.snowline + 1.5, h + (big - 0.5) * 5) * (1 - smooth01(0.45, 0.65, slope)));
    const shade = Math.min(1.14, Math.max(0.72, 1 + curveOf(k) * 0.22)) * (0.94 + small * 0.12);
    out[k * 3] = r * shade;
    out[k * 3 + 1] = gr * shade;
    out[k * 3 + 2] = b * shade;
  }
}

// Colours the land's points from column i0 to i1 in rows j0 to j1 (and the land around it, when that changed).
function colorLand(n, i0, i1, j0, j1) {
  const g = n.obj.geometry;
  const { N, size, noise } = n.grid;
  const pos = g.attributes.position.array;
  const H = (i, j) => pos[((j < 0 ? 0 : j >= N ? N - 1 : j) * N + (i < 0 ? 0 : i >= N ? N - 1 : i)) * 3 + 1];
  const curve = (k) => {
    const i = k % N;
    const j = (k - i) / N;
    return pos[k * 3 + 1] - (H(i - 2, j) + H(i + 2, j) + H(i, j - 2) + H(i, j + 2)) / 4;
  };
  const s = palette(n.p.style);
  const waters = landWaters(n);
  const color = g.attributes.color;
  for (let j = j0; j <= j1; j++) paintLand(s, pos, g.attributes.normal.array, j * N + i0, j * N + i1, curve, waters, color.array, noise);
  color.addUpdateRange(j0 * N * 3, (j1 - j0 + 1) * N * 3);
  color.needsUpdate = true;
  buildApron(n, pos, N, size, s, waters);
  if (n.host) n.host.dirty = true;
}

// Beyond the land's edges: more land, out to the fog, so nobody looks over the edge into nothing. It starts at the
// edge's own heights, levels out, and rolls into low hills further off. It's only scenery: nothing stands on it,
// the player can't walk there, and picking goes through it.
function buildApron(n, pos, N, size, s, waters) {
  let sum = 0;
  for (let q = 0; q < N; q++) sum += pos[q * 3 + 1] + pos[((N - 1) * N + q) * 3 + 1] + pos[q * N * 3 + 1] + pos[(q * N + N - 1) * 3 + 1];
  const key = `${N} ${size} ${n.p.style} ${sum.toFixed(3)} ${JSON.stringify(waters)}`;
  if (n.apronKey === key) return;  // painting inside the land doesn't change it
  n.apronKey = key;
  const C = 16;          // cells per land width
  const reach = 3.5;     // land widths from the middle
  const cells = Math.round(2 * reach * C);
  const K = cells + 1;
  const step = size / C;
  const half = size / 2;
  const base = sum / (4 * N);
  if (n.apron && n.apron.userData.size !== size) {  // its texture coordinates are for the old size
    n.obj.remove(n.apron);
    n.apron.geometry.dispose();
    n.apron = null;
  }
  if (!n.apron) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(K * K * 3), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(K * K * 3), 3));
    const uv = new Float32Array(K * K * 2);
    const index = [];
    for (let j = 0; j < K; j++) {
      for (let i = 0; i < K; i++) {
        const x = -reach * size + i * step;
        const z = -reach * size + j * step;
        uv[(j * K + i) * 2] = (x + half) / 8;
        uv[(j * K + i) * 2 + 1] = (half - z) / 8;
        const cx = x + step / 2;
        const cz = z + step / 2;
        if (i < cells && j < cells && (Math.abs(cx) > half || Math.abs(cz) > half)) {
          const a = j * K + i;
          index.push(a, a + K, a + 1, a + 1, a + K, a + K + 1);
        }
      }
    }
    g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    g.setIndex(index);
    n.apron = new THREE.Mesh(g, n.obj.material);
    n.apron.userData.size = size;
    n.apron.receiveShadow = true;
    n.apron.raycast = () => {};
    n.obj.add(n.apron);
  }
  const g = n.apron.geometry;
  const out = g.attributes.position.array;
  for (let j = 0, k = 0; j < K; j++) {
    for (let i = 0; i < K; i++, k++) {
      const x = -reach * size + i * step;
      const z = -reach * size + j * step;
      const away = Math.max(Math.abs(x), Math.abs(z)) - half;  // how far outside the land
      const e = gridHeight(n.grid, pos, x, z);  // the land's height at the nearest point of its edge
      let h = e;
      if (away > 0) {
        const hills = size * 0.12 * Math.max(0, noise2(x / (size * 0.3) + 3.1, z / (size * 0.3) - 7.7) - 0.35);
        h = e + (base - e) * smooth01(0, size * 0.25, away) + hills * smooth01(size * 0.2, size * 1.2, away);
      }
      out[k * 3] = x;
      out[k * 3 + 1] = h;
      out[k * 3 + 2] = z;
    }
  }
  g.attributes.position.needsUpdate = true;
  g.computeVertexNormals();
  g.computeBoundingSphere();
  paintLand(s, out, g.attributes.normal.array, 0, K * K - 1, () => 0, waters, g.attributes.color.array, null);
  g.attributes.color.needsUpdate = true;
}

// Smooth value noise from 0 to 1 (the same every time for the same x, z), and its lattice: `wrap` makes it repeat.
function hash2(i, j) {
  let h = (Math.imul(i, 374761393) + Math.imul(j, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) & 0xffff) / 65535;
}

// The land's colour patches: big soft ones (~30 m) and small ones (~6 m), turned off the grid so they don't line up.
function bigPatches(x, z) {
  return noise2(x * 0.03 + z * 0.018 + 17.3, z * 0.03 - x * 0.018 - 5.1);
}

function smallPatches(x, z) {
  const u = x * 0.87 + z * 0.5;
  const v = z * 0.87 - x * 0.5;
  return 0.65 * noise2(u * 0.16 - 3.7, v * 0.16 + 8.9) + 0.35 * noise2(u * 0.41 + 1.3, v * 0.41 - 2.2);
}

function noise2(x, z, wrap = 0) {
  const i = Math.floor(x);
  const j = Math.floor(z);
  const fx = x - i;
  const fz = z - j;
  const sx = fx * fx * (3 - 2 * fx);
  const sz = fz * fz * (3 - 2 * fz);
  const at = wrap ? (a, c) => hash2(((a % wrap) + wrap) % wrap, ((c % wrap) + wrap) % wrap) : hash2;
  const a = at(i, j);
  const bb = at(i + 1, j);
  const c = at(i, j + 1);
  const d = at(i + 1, j + 1);
  return a + (bb - a) * sx + (c - a) * sz + (a - bb - c + d) * sx * sz;
}

// The land's grain: soft grey noise in three sizes and a few specks (it multiplies the colours), repeating every 8 m
// without a seam. Up close it's tufts and grit; further off it fades into the land's own colours.
function landTexture() {
  if (landGrain) return landGrain;
  const S = 512;
  const c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d');
  const img = g.createImageData(S, S);
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const speck = hash2(x * 3 + 11, y * 5 + 3);
      // No blobs bigger than half a metre: bigger ones would show the 8 m repeat from up high.
      let v = 0.38 * noise2(x / 32, y / 32, 16) + 0.3 * noise2(x / 10.24, y / 10.24, 50) + 0.2 * noise2(x / 4, y / 4, 128)
        + 0.12 * hash2(x + 1013, y + 7);
      if (speck < 0.05) v -= 0.22;
      else if (speck > 0.975) v += 0.14;
      const k = Math.round(255 * Math.max(0, Math.min(1, 0.45 + 0.75 * v)));
      const at = (y * S + x) * 4;
      img.data[at] = img.data[at + 1] = img.data[at + 2] = k;
      img.data[at + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  landGrain = new THREE.CanvasTexture(c);
  landGrain.wrapS = landGrain.wrapT = THREE.RepeatWrapping;
  landGrain.anisotropy = 8;
  return landGrain;
}

// 'water': a lake's (a circle of radius `r` around its position, a little wider than the hollow under it) or, with
// r 0, a sea (a square `size` across). Its height is its level. With modern lighting it reflects the sky.
const WATER_KEYS = new Set(['r', 'size', 'color', 'opacity']);

function makeWater() {
  const p = { r: 10, size: 800, color: '#1f6f98', opacity: 0.82 };
  const m = new THREE.MeshStandardMaterial({ color: p.color, roughness: 0.15, metalness: 0.1, transparent: true, opacity: p.opacity,
    envMapIntensity: 0.65 });
  const obj = new THREE.Mesh(new THREE.BufferGeometry(), m);
  obj.receiveShadow = true;
  const n = { obj, p, pick: true, water: true };
  buildWater(n);
  return n;
}

function buildWater(n) {
  const p = n.p;
  const r = +p.r || 0;
  const g = r > 0 ? new THREE.CircleGeometry(r * 1.04, Math.max(24, Math.min(96, Math.round(r * 4))))
    : new THREE.PlaneGeometry(+p.size || 800, +p.size || 800);
  g.rotateX(-Math.PI / 2);
  n.obj.geometry.dispose();
  n.obj.geometry = g;
  n.obj.material.color.set(p.color);
  n.obj.material.opacity = p.opacity;
}

// The land's height at x, z in the world (between its four nearest points), as Python works it out too.
function landHeight(t, x, z) {
  const o = t.obj.position;
  if (!t.grid) return o.y;
  return o.y + gridHeight(t.grid, t.obj.geometry.attributes.position.array, x - o.x, z - o.z);
}

function geometry(type, p) {
  let key;
  let make;
  switch (type) {
    case 'box': key = `box ${p.w} ${p.h} ${p.d}`; make = () => new THREE.BoxGeometry(p.w, p.h, p.d); break;
    case 'sphere': key = `sphere ${p.r} ${p.seg}`; make = () => new THREE.SphereGeometry(p.r, p.seg, Math.max(2, p.seg >> 1)); break;
    case 'plane': key = `plane ${p.w} ${p.h}`; make = () => new THREE.PlaneGeometry(p.w, p.h); break;
    case 'cylinder': key = `cyl ${p.rt} ${p.rb} ${p.h} ${p.seg}`; make = () => new THREE.CylinderGeometry(p.rt, p.rb, p.h, p.seg); break;
    case 'cone': key = `cone ${p.r} ${p.h} ${p.seg}`; make = () => new THREE.ConeGeometry(p.r, p.h, p.seg); break;
    case 'torus': key = `torus ${p.r} ${p.tube} ${p.seg}`; make = () => new THREE.TorusGeometry(p.r, p.tube, Math.max(3, p.seg >> 2), p.seg); break;
    case 'capsule': key = `capsule ${p.r} ${p.h} ${p.seg}`; make = () => new THREE.CapsuleGeometry(p.r, p.h, 4, p.seg); break;
  }
  let g = geometries.get(key);
  if (!g) {
    g = make();
    geometries.set(key, g);
  }
  return g;
}

function texture(src, repeat) {
  const key = repeat ? `${src} ${repeat[0]} ${repeat[1]}` : src;
  let t = textures.get(key);
  if (!t) {
    t = new THREE.TextureLoader().load(src, () => { for (const s of scenes) s.dirty = true; },
      undefined, () => report(new Error(`couldn't load the texture ${src}`), 'loading a texture'));
    t.colorSpace = THREE.SRGBColorSpace;
    if (repeat) {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.repeat.set(repeat[0], repeat[1]);
    }
    textures.set(key, t);
  }
  return t;
}

function material(n) {
  const p = n.p;
  const Kind = { basic: THREE.MeshBasicMaterial, lambert: THREE.MeshLambertMaterial, phong: THREE.MeshPhongMaterial,
    toon: THREE.MeshToonMaterial, standard: THREE.MeshStandardMaterial }[p.mat];
  if (!Kind) throw new Error(`there's no material called '${p.mat}'`);
  let m = n.obj.material;
  if (!(m instanceof Kind)) {
    if (m) m.dispose();
    m = n.obj.material = new Kind();
  }
  m.color.set(p.color);
  m.opacity = p.opacity;
  m.transparent = p.opacity < 1;
  m.wireframe = !!p.wireframe;
  m.side = p.side === 'both' ? THREE.DoubleSide : p.side === 'back' ? THREE.BackSide : THREE.FrontSide;
  m.map = p.texture ? texture(p.texture, p.repeat) : null;
  if ('flatShading' in m && m.flatShading !== !!p.flat) { m.flatShading = !!p.flat; m.needsUpdate = true; }
  if (m.emissive) m.emissive.set(p.emissive || 0x000000);
  if ('roughness' in m) { m.roughness = p.rough; m.metalness = p.metal; }
  m.needsUpdate = true;
}

function setObj(n, props) {
  const o = n.obj;
  const p = n.p;
  let geo = false;
  let mat = false;
  let relabel = false;
  let land = false;
  let water = false;
  for (const k in props) {
    const v = props[k];
    switch (k) {
      case 'ontop':
        if (o.material) { o.material.depthTest = !v; o.material.needsUpdate = true; }
        o.renderOrder = v ? 1000 : 0;
        break;
      case 'src':
        if (n.type === 'model') loadModel(n, v);
        else p[k] = v;
        break;
      case 'x': o.position.x = v; if (n.at) n.at[0] = v; break;
      case 'y': o.position.y = v; if (n.at) n.at[1] = v; break;
      case 'z': o.position.z = v; if (n.at) n.at[2] = v; break;
      case 'rx': o.rotation.x = v * DEG; break;
      case 'ry': o.rotation.y = v * DEG; break;
      case 'rz': o.rotation.z = v * DEG; break;
      case 'sx': o.scale.x = v; break;
      case 'sy': o.scale.y = v; break;
      case 'sz': o.scale.z = v; break;
      case 'scale': o.scale.setScalar(v); break;
      case 'visible': o.visible = !!v; break;
      case 'anim': anim.add(n, v); break;  // how it moves by itself (anim.js)
      case 'pick': n.pick = v !== false; break;
      case 'look': o.lookAt(v[0], v[1], v[2]); break;
      case 'camera': (v ? n.host.camera : n.host.scene).add(o); break;
      case 'shadow':
        o.castShadow = !!v;
        if (o.isMesh) o.receiveShadow = !!v;
        break;
      case 'phys': break;  // physicsChanged, below
      case 'wobble': n.wobble = v; break;  // a physics body's shake: physics.js tilts how it's drawn by it
      case 'intensity': if (o.isLight) { p.intensity = v; o.intensity = v * lightScale(n); } break;
      case 'distance': if (o.isLight) o.distance = v; break;
      case 'ground': if (o.groundColor) o.groundColor.set(v); break;
      case 'area':
        p.area = v;
        if (o.shadow && o.shadow.camera.isOrthographicCamera && !n.host.modern) {
          const c = o.shadow.camera;
          c.left = c.bottom = -v;
          c.right = c.top = v;
          c.updateProjectionMatrix();
        }
        break;
      default:
        if (n.land) {
          if (LAND_KEYS.has(k)) { p[k] = v; land = true; }
          if (k === 'style') n.restyle = true;
          break;
        }
        if (n.water) { if (WATER_KEYS.has(k)) { p[k] = v; water = true; } break; }
        if (k === 'r' && n.type === 'cylinder') { p.rt = p.rb = v; geo = true; break; }
        if (k === 'color' && o.isLight) { o.color.set(v); break; }
        p[k] = v;
        if (n.type === 'label') relabel = relabel || LABEL_KEYS.has(k);
        else if (GEO_KEYS.has(k)) geo = true;
        else if (MAT_KEYS.has(k)) mat = true;
    }
  }
  if (geo && o.isMesh) o.geometry = geometry(n.type, p);
  if (mat && o.isMesh) material(n);
  if (relabel) drawLabel(n);
  if (land) buildLand(n);
  if (water) buildWater(n);
  if (n.phys || 'phys' in props) physicsChanged(n, props);
  if (land && n.phys) withPhysics((ph) => ph.landChanged(n));
  if (n.water) n.host.recolor = true;  // the land by it gets its sand where the water is now
  n.host.dirty = true;
}

function draw3d(n) {
  if (n.resized) {
    const w = Math.max(1, n.el.clientWidth);
    const h = Math.max(1, n.el.clientHeight);
    n.renderer.setPixelRatio(window.devicePixelRatio || 1);
    n.renderer.setSize(w, h, false);
    n.camera.aspect = w / h;
    n.camera.updateProjectionMatrix();
    n.resized = false;
  }
  if (n.sky) {
    n.sky.position.copy(n.camera.position);
    n.sky.scale.setScalar(n.camera.far * 0.9);
  }
  if (n.recolor) {
    n.recolor = false;
    for (const t of n.lands || []) if (t.grid) colorLand(t, 0, t.grid.N - 1, 0, t.grid.N - 1);
  }
  if (n.modern) {
    try {
      if (n.envDirty) makeEnvironment(n);
      for (const l of n.suns || []) followSun(n, l);
    } catch {
      setLighting(n, 'simple');  // the graphics couldn't: this scene stays simple, without an error
    }
  }
  sizeLabels(n);
  n.renderer.render(n.scene, n.camera);
}

function visible(o) {
  for (; o; o = o.parent) if (!o.visible) return false;
  return true;
}

// The nearest pickable object under a point (CSS pixels from the scene's top-left), or under the
// middle of the view when no point is given (a crosshair, e.g. with the mouse locked).
function pick3d(n, x, y) {
  if (!n.ray) n.ray = new THREE.Raycaster();
  const w = n.el.clientWidth || 1;
  const h = n.el.clientHeight || 1;
  const ndc = x == null ? { x: 0, y: 0 } : { x: (x / w) * 2 - 1, y: -(y / h) * 2 + 1 };
  n.scene.updateMatrixWorld();
  n.ray.setFromCamera(ndc, n.camera);
  for (const hit of n.ray.intersectObjects(n.scene.children, true)) {
    let o = hit.object;
    while (o && o.userData.tv === undefined) o = o.parent;
    const m = o && objs.get(o.userData.tv);
    if (!m || !m.pick || !visible(hit.object)) continue;
    const pt = hit.point;
    return { id: m.id, point: [pt.x, pt.y, pt.z], dist: hit.distance, path: path3d(m) };
  }
  return { id: null, point: null, dist: null, path: [n.id] };
}

function path3d(m) {
  const out = [];
  for (let k = m; k; k = k.parent) out.push(k.id);
  return out.concat(domPath(m.host.el.parentNode));
}

// Where a point in the 3D world shows up, in CSS pixels from the scene's top-left (null when it's behind the camera).
function project(n, x, y, z) {
  n.scene.updateMatrixWorld();
  const v = new THREE.Vector3(x, y, z).project(n.camera);
  if (v.z > 1) return null;
  return [(v.x + 1) / 2 * n.el.clientWidth, (1 - v.y) / 2 * n.el.clientHeight];
}

// ---------------------------------------------------------------- .glb models

// A 'model' object loads a binary glTF (.glb) from `src`: its meshes, node transforms, PBR base colors, and
// pictures packed inside it. Skins, animations and morph targets are left out. The model is moved so its bottom
// is at the object's position and it's centred over it, and a 'model' event tells Python its size.
const models = new Map(); // src -> a promise of the loaded model, which each object copies

function loadModel(n, src) {
  n.p.src = src;
  for (const c of [...n.obj.children]) n.obj.remove(c);
  let job = models.get(src);
  if (!job) {
    job = fetch(src)
      .then((r) => { if (!r.ok) throw new Error(`couldn't load the model ${decodeURIComponent(src.split('/').pop())} (${r.status})`); return r.arrayBuffer(); })
      .then(parseGlb);
    models.set(src, job);
  }
  job.then((model) => {
    if (!objs.has(n.id) || n.p.src !== src) return;
    const copy = model.clone(true);
    const box = new THREE.Box3().setFromObject(copy);
    const size = box.getSize(new THREE.Vector3());
    const mid = box.getCenter(new THREE.Vector3());
    copy.position.set(-mid.x, -box.min.y, -mid.z);
    copy.traverse((o) => { if (o.isMesh) o.castShadow = o.receiveShadow = true; });
    n.obj.add(copy);
    n.host.dirty = true;
    emit('model', { id: n.id, size: [size.x, size.y, size.z] });
  }, (err) => report(err, 'loading a model'));
}

const GLB_TYPES = { 5120: Int8Array, 5121: Uint8Array, 5122: Int16Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
const GLB_SIZES = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 };

function parseGlb(buf) {
  const dv = new DataView(buf);
  if (buf.byteLength < 20 || dv.getUint32(0, true) !== 0x46546c67) throw new Error("that file isn't a .glb model");
  let json = null;
  let bin = null;
  for (let off = 12; off + 8 <= buf.byteLength;) {
    const len = dv.getUint32(off, true);
    const type = dv.getUint32(off + 4, true);
    if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, off + 8, len)));
    else if (type === 0x004e4942) bin = buf.slice(off + 8, off + 8 + len);
    off += 8 + len;
  }
  if (!json) throw new Error('the .glb file has no model in it');
  const views = json.bufferViews || [];
  const accessor = (i) => {
    const a = json.accessors[i];
    const T = GLB_TYPES[a.componentType];
    const n = GLB_SIZES[a.type];
    if (a.bufferView === undefined) return { array: new T(a.count * n), size: n, normalized: !!a.normalized };
    const v = views[a.bufferView];
    const start = (v.byteOffset || 0) + (a.byteOffset || 0);
    const stride = v.byteStride || n * T.BYTES_PER_ELEMENT;
    let array;
    if (stride === n * T.BYTES_PER_ELEMENT) array = new T(bin.slice(start, start + a.count * stride));
    else {
      array = new T(a.count * n);
      for (let k = 0; k < a.count; k++) array.set(new T(bin, start + k * stride, n), k * n);
    }
    return { array, size: n, normalized: !!a.normalized };
  };
  const pictures = new Map();
  const picture = (index) => {
    if (!pictures.has(index)) {
      const tex = (json.textures || [])[index] || {};
      const img = (json.images || [])[tex.source] || {};
      let url = img.uri;
      if (img.bufferView !== undefined) {
        const v = views[img.bufferView];
        url = URL.createObjectURL(new Blob([bin.slice(v.byteOffset || 0, (v.byteOffset || 0) + v.byteLength)], { type: img.mimeType || 'image/png' }));
      }
      const t = url ? new THREE.TextureLoader().load(url, () => { for (const s of scenes) s.dirty = true; }) : null;
      if (t) {
        t.flipY = false;
        t.colorSpace = THREE.SRGBColorSpace;
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
      }
      pictures.set(index, t);
    }
    return pictures.get(index);
  };
  const materials = (json.materials || []).map((m) => {
    const pbr = m.pbrMetallicRoughness || {};
    const f = pbr.baseColorFactor || [1, 1, 1, 1];
    const mat = new THREE.MeshStandardMaterial({
      metalness: pbr.metallicFactor ?? 1, roughness: pbr.roughnessFactor ?? 1, opacity: f[3],
      transparent: f[3] < 1 || m.alphaMode === 'BLEND', side: m.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
    });
    mat.color.setRGB(f[0], f[1], f[2]);  // glTF colors are linear, like three's working colors
    if (pbr.baseColorTexture) mat.map = picture(pbr.baseColorTexture.index);
    if (m.emissiveFactor) mat.emissive.setRGB(m.emissiveFactor[0], m.emissiveFactor[1], m.emissiveFactor[2]);
    return mat;
  });
  const plain = new THREE.MeshStandardMaterial({ color: 0xcccccc });
  const meshes = (json.meshes || []).map((mesh) => mesh.primitives.filter((pr) => (pr.mode ?? 4) === 4).map((pr) => {
    const g = new THREE.BufferGeometry();
    const set = (name, key) => {
      if (pr.attributes[key] === undefined) return;
      const a = accessor(pr.attributes[key]);
      g.setAttribute(name, new THREE.BufferAttribute(a.array, a.size, a.normalized));
    };
    set('position', 'POSITION');
    set('normal', 'NORMAL');
    set('uv', 'TEXCOORD_0');
    set('color', 'COLOR_0');
    if (pr.indices !== undefined) g.setIndex(new THREE.BufferAttribute(accessor(pr.indices).array, 1));
    if (pr.attributes.NORMAL === undefined) g.computeVertexNormals();
    let mat = pr.material !== undefined ? materials[pr.material] : plain;
    if (pr.attributes.COLOR_0 !== undefined) { mat = mat.clone(); mat.vertexColors = true; }
    return new THREE.Mesh(g, mat);
  }));
  const node = (i) => {
    const d = json.nodes[i];
    const o = new THREE.Group();
    if (d.matrix) new THREE.Matrix4().fromArray(d.matrix).decompose(o.position, o.quaternion, o.scale);
    else {
      if (d.translation) o.position.fromArray(d.translation);
      if (d.rotation) o.quaternion.fromArray(d.rotation);
      if (d.scale) o.scale.fromArray(d.scale);
    }
    if (d.mesh !== undefined) for (const m of meshes[d.mesh]) o.add(m.clone());
    for (const c of d.children || []) o.add(node(c));
    return o;
  };
  const root = new THREE.Group();
  const scene = (json.scenes || [])[json.scene || 0];
  for (const i of scene ? scene.nodes || [] : (json.nodes || []).map((_, k) => k)) root.add(node(i));
  return root;
}

// ---------------------------------------------------------------- a picture of the window

// Every canvas and 3D scene in the window, drawn as they are now into one PNG (a data: URL). Scenes are
// rendered again first, in the same task, so their pictures are complete. DOM elements aren't included.
function snapshot() {
  const r = window.devicePixelRatio || 1;
  const out = document.createElement('canvas');
  out.width = Math.max(1, Math.round(innerWidth * r));
  out.height = Math.max(1, Math.round(innerHeight * r));
  const g = out.getContext('2d');
  g.fillStyle = getComputedStyle(document.body).backgroundColor || '#000';
  g.fillRect(0, 0, out.width, out.height);
  for (const el of root.querySelectorAll('canvas')) {
    const n = el._tv !== undefined ? objs.get(el._tv) : null;
    if (!el.getClientRects().length || getComputedStyle(el).visibility === 'hidden') continue;
    if (n && n.kind === 'scene') draw3d(n);
    else if (n && n.kind === 'canvas') draw2d(n);
    const b = el.getBoundingClientRect();
    g.drawImage(el, b.left * r, b.top * r, b.width * r, b.height * r);
  }
  return out.toDataURL('image/png');
}

// ---------------------------------------------------------------- sound

let audio = null;         // the AudioContext, made on first use
let master = null;        // its main volume
let masterVolume = 1;
const playing = new Map(); // id -> HTMLAudioElement, for sound files
let noise = null;

function audioContext() {
  if (!audio) {
    audio = new AudioContext();
    master = audio.createGain();
    master.gain.value = masterVolume;
    master.connect(audio.destination);
  }
  if (audio.state === 'suspended') audio.resume().catch(() => {});
  return audio;
}

// Synthesised sound: a list of notes [frequency, start, seconds, wave, volume, end frequency]. wave is sine,
// square, sawtooth, triangle or noise (frequency is then a low-pass cut-off). Starts are seconds from now.
function tones(notes, volume = 0.3) {
  const a = audioContext();
  const t0 = a.currentTime + 0.005;
  for (const [freq, start = 0, secs = 0.15, wave = 'square', vol = 1, end = null] of notes || []) {
    const at = t0 + start;
    const gain = a.createGain();
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, vol * volume), at + Math.min(0.01, secs / 4));
    gain.gain.exponentialRampToValueAtTime(0.0001, at + secs);
    gain.connect(master);
    let src;
    if (wave === 'noise') {
      if (!noise) {
        noise = a.createBuffer(1, a.sampleRate, a.sampleRate);
        const d = noise.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      }
      src = a.createBufferSource();
      src.buffer = noise;
      src.loop = true;
      const filter = a.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(freq, at);
      if (end) filter.frequency.exponentialRampToValueAtTime(end, at + secs);
      src.connect(filter);
      filter.connect(gain);
    } else {
      src = a.createOscillator();
      src.type = wave;
      src.frequency.setValueAtTime(freq, at);
      if (end) src.frequency.exponentialRampToValueAtTime(end, at + secs);
      src.connect(gain);
    }
    src.start(at);
    src.stop(at + secs + 0.02);
  }
  return null;
}

// A sound file (an address from view.url). id names it for sound_stop; loop repeats it.
function sound(id, src, volume = 1, loop = false) {
  const el = new Audio(src);
  el.baseVolume = Math.max(0, Math.min(1, volume));
  el.volume = el.baseVolume * masterVolume;
  el.loop = !!loop;
  el.onended = () => { if (playing.get(id) === el) playing.delete(id); };
  el.onerror = () => report(new Error(`couldn't play the sound ${decodeURIComponent(src.split('/').pop())}`), 'playing a sound');
  playing.set(id, el);
  el.play().catch((err) => {
    // Without a click or key press first, the browser may refuse to start sound: try again on the next one.
    if (err && err.name === 'NotAllowedError') el.waiting = true;
  });
  return null;
}

function soundStop(id) {
  for (const [key, el] of [...playing]) {
    if (id == null || key === id) { el.pause(); playing.delete(key); }
  }
  return null;
}

function soundVolume(v) {
  masterVolume = Math.max(0, Math.min(1, +v));
  if (master) master.gain.value = masterVolume;
  for (const el of playing.values()) el.volume = el.baseVolume * masterVolume;
  return null;
}

function soundState() {
  return { context: audio ? audio.state : 'none', files: playing.size, waiting: [...playing.values()].filter((el) => el.waiting).length };
}

function wakeSound() {
  if (audio && audio.state === 'suspended') audio.resume().catch(() => {});
  for (const el of playing.values()) if (el.waiting) { el.waiting = false; el.play().catch(() => {}); }
}

// ---------------------------------------------------------------- drawing, every animation frame

function tick(now) {
  requestAnimationFrame(tick);
  const game = fx.time(now);  // the game's clock: physics, models and pads go at the game's speed (slow motion)
  try { anim.frame(now, game, scenes); } catch (err) { report(err, 'animating'); }  // anim.js: before the scenes are drawn
  level.frame(game);  // level.js's pads, on anim.js's steps (it reports its own errors)
  if (stats.last) {
    stats.gaps.push(now - stats.last);
    if (stats.gaps.length > 4000) stats.gaps.splice(0, 1000);
  }
  stats.last = now;
  stats.frames++;
  const t0 = performance.now();
  if (physics && !physicsFailed) {
    try {
      physics.step(game);  // at the game's speed (slow motion)
    } catch (err) {
      physicsFailed = true;  // once: an error every frame would bury everything else
      report(err, 'physics');
    }
  }
  for (const c of canvases) if (c.dirty) { c.dirty = false; stats.draws++; try { draw2d(c); } catch (err) { report(err, 'drawing a canvas'); } }
  for (const s of scenes) if (s.dirty) { s.dirty = false; stats.draws++; try { draw3d(s); } catch (err) { report(err, 'drawing a 3D scene'); } }
  stats.drawMs += performance.now() - t0;
  flushMoves();
}

// ---------------------------------------------------------------- events back to Python

let outbox = [];
let sendQueued = false;
let seq = 0;
let bridgeReady = false;
let moved = null;      // mouse movement, merged until the next animation frame
let wheel = null;
let resized = false;

// Clicks, keys and typing go to Python straight away (all of one task's events in one call); mouse
// movement, wheel and resize are merged and go once per animation frame.
function emit(type, data) {
  if (moved) { outbox.push(moved); moved = null; }
  const e = data || {};
  e.type = type;
  outbox.push(e);
  queueSend();
}

function queueSend() {
  if (!sendQueued) {
    sendQueued = true;
    queueMicrotask(send);
  }
}

function send() {
  sendQueued = false;
  if (!bridgeReady || !outbox.length) return;
  const list = outbox;
  outbox = [];
  window.pywebview.api.ev(++seq, list).catch(() => {});
}

function flushMoves() {
  if (resized) { resized = false; emit('resize', { w: innerWidth, h: innerHeight }); }
  if (wheel) { const w = wheel; wheel = null; emit('wheel', w); }
  if (moved) { outbox.push(moved); moved = null; queueSend(); }
}

function report(err, where) {
  const message = err && err.message ? err.message : String(err);
  emit('error', { message, where: where || '', stack: err && err.stack ? String(err.stack).split('\n').slice(0, 6).join('\n') : '' });
}

function domPath(el) {
  const out = [];
  for (; el && el !== document.body; el = el.parentNode) if (el._tv !== undefined) out.push(el._tv);
  return out;
}

function editable(el) {
  return el && (el.isContentEditable || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT');
}

// A field the keys type into (a text box, not a checkbox or a slider): a game leaves those keys alone.
function typing(el) {
  return !!el && editable(el) && !(el.tagName === 'INPUT' && /^(checkbox|radio|range|button|submit|reset|color|file|image)$/i.test(el.type));
}

// What's under the pointer: a 2D shape or 3D object first, then the element and its parents. With the mouse held
// for looking around, the element holding it, as with the browser's lock.
function target(e) {
  const t = (passing && heldBy) || e.target;
  const n = t && t._tv !== undefined ? objs.get(t._tv) : null;
  const info = { x: e.clientX, y: e.clientY, path: domPath(t) };
  if (n && (n.kind === 'canvas' || n.kind === 'scene')) {
    const r = t.getBoundingClientRect();
    const lx = e.clientX - r.left;
    const ly = e.clientY - r.top;
    if (n.kind === 'canvas') {
      const hit = pick2d(n, lx, ly);
      info.cx = hit.x;
      info.cy = hit.y;
      if (hit.id != null) info.path.unshift(hit.id);
    } else {
      const hit = document.pointerLockElement === t ? pick3d(n, null, null) : pick3d(n, lx, ly);
      if (hit.id != null) { info.path = hit.path; info.point = hit.point; info.dist = hit.dist; }
    }
  }
  info.id = info.path.length ? info.path[0] : null;
  return info;
}

function mods(e) {
  return { shift: e.shiftKey, ctrl: e.ctrlKey, alt: e.altKey, meta: e.metaKey };
}

addEventListener('pointerdown', (e) => emit('mousedown', { ...target(e), button: e.button, ...mods(e), ...(e.tvLocks ? { locks: true } : null) }));
addEventListener('pointerup', (e) => emit('mouseup', { ...target(e), button: e.button, ...mods(e) }));
addEventListener('click', (e) => emit('click', { ...target(e), button: e.button, ...mods(e) }));
addEventListener('dblclick', (e) => emit('dblclick', { ...target(e), button: e.button, ...mods(e) }));
addEventListener('contextmenu', (e) => { if (!editable(e.target)) e.preventDefault(); });
addEventListener('pointermove', (e) => {
  if (!moved) moved = { type: 'mousemove', x: e.clientX, y: e.clientY, dx: 0, dy: 0 };
  moved.x = e.clientX;
  moved.y = e.clientY;
  moved.dx += e.movementX || 0;
  moved.dy += e.movementY || 0;
});
addEventListener('wheel', (e) => {
  if (!wheel) wheel = { dx: 0, dy: 0, x: e.clientX, y: e.clientY, path: domPath((passing && heldBy) || e.target) };
  wheel.dx += e.deltaX;
  wheel.dy += e.deltaY;
}, { passive: true });
// In a game, Space and the arrows are for playing: they mustn't scroll the page or press a focused button. An app
// turns this off (tv.gameKeys = false, as atgui does), so Space presses its buttons and the arrows scroll.
const GAME_KEYS = new Set([' ', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']);
addEventListener('keydown', (e) => {
  if (api.gameKeys && GAME_KEYS.has(e.key) && !editable(e.target)) e.preventDefault();
  emit('keydown', { key: e.key, code: e.code, repeat: e.repeat, typing: typing(e.target), ...mods(e) });
});
addEventListener('keyup', (e) => emit('keyup', { key: e.key, code: e.code, ...mods(e) }));
document.addEventListener('input', (e) => {
  const t = e.target;
  if (t._tv !== undefined) emit('input', { id: t._tv, path: domPath(t), value: t.type === 'checkbox' || t.type === 'radio' ? t.checked : t.value });
});
document.addEventListener('change', (e) => {
  const t = e.target;
  if (t._tv !== undefined) emit('change', { id: t._tv, path: domPath(t), value: t.type === 'checkbox' || t.type === 'radio' ? t.checked : t.value });
});
document.addEventListener('submit', (e) => { e.preventDefault(); emit('submit', { id: e.target._tv ?? null, path: domPath(e.target) }); });
document.addEventListener('pointerlockchange', () => emit('lock', { locked: !!document.pointerLockElement }));
addEventListener('resize', () => { resized = true; });
addEventListener('blur', () => emit('blur', {}));
addEventListener('focus', () => emit('focus', {}));
// A press of the mouse still going on, from its pointerdown until just after its click (see passThrough). First of
// the pointerdown listeners, so it's known before one asks to hold the mouse.
let pressing = false;
addEventListener('pointerdown', () => { pressing = true; }, true);
addEventListener('pointerup', () => setTimeout(() => { pressing = false; passThrough(); }, 0), true);
// A scene with `clicklock` locks the pointer when it's clicked (for mouse look); the browser only allows that
// inside the click itself, so it can't wait for Python. Escape unlocks it. That click's mousedown has `locks: true`.
addEventListener('pointerdown', (e) => {
  wakeSound();
  const n = e.target && e.target._tv !== undefined ? objs.get(e.target._tv) : null;
  if (n && n.kind === 'scene' && n.clicklock && document.pointerLockElement !== n.el) {
    e.tvLocks = true;
    const p = n.el.requestPointerLock();
    if (p && p.catch) p.catch(() => {});
  }
}, true);
addEventListener('keydown', wakeSound, true);

// The mouse held for looking around without the browser's pointer lock, which shows "To show your cursor, press
// Esc" over the game: Python holds it (tuff_view's _MouseHold keeps it in the window and measures its moves), and
// the page stands in for the lock, so requestPointerLock, document.pointerLockElement, exitPointerLock and
// 'pointerlockchange' work as before. As with the real lock, only a window with the focus can hold it, Escape and
// the window losing the focus let go, and while it's held the mouse's events go to the element holding it (nothing
// else on the page is under the pointer, so a card in the middle of the window doesn't take the game's clicks).
// Python turns this on (nativeMouse(true)) where it can hold the mouse.
let heldBy = null;
let passing = false;  // the mouse's events go to heldBy
function holdMouse(el) {
  if (heldBy === el) return;
  if (heldBy) heldBy.removeAttribute('data-tv-holder');
  heldBy = el;
  if (el) el.setAttribute('data-tv-holder', '');
  document.documentElement.classList.toggle('tv-held', !!el);
  passThrough();
  emit('capture', { on: !!el });
  document.dispatchEvent(new Event('pointerlockchange'));
}
// The mouse's events go to the element holding it, but not before the click that asked for the hold is over (a click
// on a start screen holds the mouse and hides the screen), so that click still goes where it was made.
function passThrough() {
  passing = !!heldBy && !pressing;
  document.documentElement.classList.toggle('tv-through', passing);
}
function nativeMouse(on) {
  if (!on || nativeMouse.on) return null;
  nativeMouse.on = true;
  Object.defineProperty(Document.prototype, 'pointerLockElement', { configurable: true, get() { return heldBy; } });
  Element.prototype.requestPointerLock = function () {
    if (!document.hasFocus()) {  // another window is in front: no (the next click on the game asks again)
      document.dispatchEvent(new Event('pointerlockerror'));
      return Promise.reject(new DOMException("the window doesn't have the focus", 'WrongDocumentError'));
    }
    holdMouse(this.isConnected ? this : null);
    return Promise.resolve();
  };
  Document.prototype.exitPointerLock = function () { holdMouse(null); };
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && heldBy) holdMouse(null); }, true);
  addEventListener('blur', () => { pressing = false; holdMouse(null); });
  const s = document.createElement('style');
  s.textContent = 'html.tv-held, html.tv-held * { cursor: none !important; }'
    + ' html.tv-through * { pointer-events: none !important; } html.tv-through [data-tv-holder] { pointer-events: auto !important; }';
  document.head.appendChild(s);
  return null;
}
addEventListener('error', (e) => report(e.error || new Error(e.message), 'the page'));
addEventListener('unhandledrejection', (e) => report(e.reason, 'the page'));

// ---------------------------------------------------------------- start up

// What custom JS (view.js(...) in Python) gets as `tv`.
const api = { objs, node, emit, three: () => THREE, loadThree, root, gameKeys: true, nativeMouse };
window.__tv = { apply };
window.tuffView = api;
requestAnimationFrame(tick);

function hello() {
  if (bridgeReady) return;
  bridgeReady = true;
  let webgl = false;
  try { webgl = !!document.createElement('canvas').getContext('webgl2'); } catch { /* no WebGL */ }
  window.pywebview.api.ready({ w: innerWidth, h: innerHeight, dpr: window.devicePixelRatio || 1, webgl, ua: navigator.userAgent });
  send();
}

if (window.pywebview && window.pywebview.api && window.pywebview.api.ready) hello();
else addEventListener('pywebviewready', hello);
