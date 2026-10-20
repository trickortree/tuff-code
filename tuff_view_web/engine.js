// The page side of tuff_view.py. Python sends batches of commands (create / set / remove / call); this file keeps
// the retained scene they describe (DOM elements, 2D canvases, three.js scenes) and draws it on every animation
// frame, at the display's own rate. Input goes back to Python as batched events.

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

const stats = { since: performance.now(), frames: 0, gaps: [], last: 0, batches: 0, cmds: 0, applyMs: 0, drawMs: 0, seq: 0 };

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
      try {
        run(c);
      } catch (err) {
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
  objs.set(id, n);
  if (props) setProps(n, props);
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
  switch (n.kind) {
    case 'shape':
      n.dead = true;
      n.host.prune = n.host.dirty = true;
      break;
    case 'obj':
      n.obj.removeFromParent();
      labels.delete(n);
      if (n.type === 'label' && n.obj.material.map) n.obj.material.map.dispose();
      if (n.obj.material) n.obj.material.dispose();
      if (n.obj.dispose) n.obj.dispose();
      n.host.dirty = true;
      break;
    case 'scene':
      scenes.delete(n);
      n.ro.disconnect();
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
    if (method === 'lock') { n.el.requestPointerLock(); return null; }
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
      seconds: secs, frames: stats.frames, fps: stats.frames / secs,
      gap_median_ms: at(0.5), gap_p95_ms: at(0.95), gap_p99_ms: at(0.99), gap_max_ms: gaps.length ? gaps[gaps.length - 1] : 0,
      batches: stats.batches, cmds: stats.cmds, last_seq: stats.seq,
      apply_ms_per_batch: stats.batches ? stats.applyMs / stats.batches : 0,
      draw_ms_per_frame: stats.frames ? stats.drawMs / stats.frames : 0,
      objects: objs.size, waiting: Math.max(0, batches.length - 1),
    };
    if (reset) Object.assign(stats, { since: now, frames: 0, gaps: [], batches: 0, cmds: 0, applyMs: 0, drawMs: 0 });
    return out;
  },
  snapshot,
  tones,
  sound,
  sound_stop: soundStop,
  sound_volume: soundVolume,
  sound_state: soundState,
};

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
    stroke: null, lw: 1, radius: 0, visible: true, pick: true, frame: null, w: null, h: null, ...SHAPE_DEFAULTS[type] };
  if (type === 'line') p.color = null;
  return { p, fontStr: '', tw: 0 };
}

function setShape(n, props) {
  const p = n.p;
  for (const k in props) {
    const v = props[k];
    if (k === 'z' && v !== p.z) n.host.order = true;
    p[k] = v;
    if (k === 'text' || k === 'size' || k === 'font' || k === 'bold') n.fontStr = '';
  }
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
    case 'circle': return [p.r * 2, p.r * 2];
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
  for (const s of n.shapes) if (s.p.visible && !s.dead) drawShape(ctx, s, k, ox, oy);
}

function drawShape(ctx, s, k, ox, oy) {
  const p = s.p;
  const a = p.rot * DEG;
  const cos = Math.cos(a);
  const sin = Math.sin(a);
  const sx = p.sx * p.scale * k;
  const sy = p.sy * p.scale * k;
  ctx.setTransform(cos * sx, sin * sx, -sin * sy, cos * sy, ox + p.x * k, oy + p.y * k);
  ctx.globalAlpha = p.alpha;
  switch (s.type) {
    case 'rect': {
      const x = -p.ax * p.w;
      const y = -p.ay * p.h;
      if (p.radius) {
        ctx.beginPath();
        ctx.roundRect(x, y, p.w, p.h, p.radius);
        fillStroke(ctx, p);
      } else {
        if (p.color) { ctx.fillStyle = p.color; ctx.fillRect(x, y, p.w, p.h); }
        if (p.stroke) { ctx.lineWidth = p.lw; ctx.strokeStyle = p.stroke; ctx.strokeRect(x, y, p.w, p.h); }
      }
      break;
    }
    case 'circle':
      ctx.beginPath();
      ctx.arc((0.5 - p.ax) * 2 * p.r, (0.5 - p.ay) * 2 * p.r, p.r, 0, TAU);
      fillStroke(ctx, p);
      break;
    case 'ellipse':
      ctx.beginPath();
      ctx.ellipse((0.5 - p.ax) * p.w, (0.5 - p.ay) * p.h, p.w / 2, p.h / 2, 0, 0, TAU);
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
      case 'bg': n.scene.background = v == null ? null : color(v); break;
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
      default: rest[k] = v;
    }
  }
  if (lens) cam.updateProjectionMatrix();
  setEl(n.el, rest);
  n.dirty = true;
}

// A gradient sky: a dome around the camera, [top, horizon] or [top, horizon, below], drawn behind everything.
function setSky(n, v) {
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
    default: throw new Error(`there's no 3D object called '${type}'`);
  }
  const n = { obj, p, pick: true };
  if (obj.isMesh) material(n);
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
      case 'x': o.position.x = v; break;
      case 'y': o.position.y = v; break;
      case 'z': o.position.z = v; break;
      case 'rx': o.rotation.x = v * DEG; break;
      case 'ry': o.rotation.y = v * DEG; break;
      case 'rz': o.rotation.z = v * DEG; break;
      case 'sx': o.scale.x = v; break;
      case 'sy': o.scale.y = v; break;
      case 'sz': o.scale.z = v; break;
      case 'scale': o.scale.setScalar(v); break;
      case 'visible': o.visible = !!v; break;
      case 'pick': n.pick = v !== false; break;
      case 'look': o.lookAt(v[0], v[1], v[2]); break;
      case 'camera': (v ? n.host.camera : n.host.scene).add(o); break;
      case 'shadow':
        o.castShadow = !!v;
        if (o.isMesh) o.receiveShadow = !!v;
        break;
      case 'intensity': if (o.isLight) o.intensity = v; break;
      case 'distance': if (o.isLight) o.distance = v; break;
      case 'ground': if (o.groundColor) o.groundColor.set(v); break;
      case 'area':
        if (o.shadow && o.shadow.camera.isOrthographicCamera) {
          const c = o.shadow.camera;
          c.left = c.bottom = -v;
          c.right = c.top = v;
          c.updateProjectionMatrix();
        }
        break;
      default:
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
  if (stats.last) {
    stats.gaps.push(now - stats.last);
    if (stats.gaps.length > 4000) stats.gaps.splice(0, 1000);
  }
  stats.last = now;
  stats.frames++;
  const t0 = performance.now();
  for (const c of canvases) if (c.dirty) { c.dirty = false; try { draw2d(c); } catch (err) { report(err, 'drawing a canvas'); } }
  for (const s of scenes) if (s.dirty) { s.dirty = false; try { draw3d(s); } catch (err) { report(err, 'drawing a 3D scene'); } }
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

// What's under the pointer: a 2D shape or 3D object first, then the element and its parents.
function target(e) {
  const t = e.target;
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

addEventListener('pointerdown', (e) => emit('mousedown', { ...target(e), button: e.button, ...mods(e) }));
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
  if (!wheel) wheel = { dx: 0, dy: 0, x: e.clientX, y: e.clientY, path: domPath(e.target) };
  wheel.dx += e.deltaX;
  wheel.dy += e.deltaY;
}, { passive: true });
const GAME_KEYS = new Set([' ', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']);
addEventListener('keydown', (e) => {
  if (GAME_KEYS.has(e.key) && !editable(e.target)) e.preventDefault();
  emit('keydown', { key: e.key, code: e.code, repeat: e.repeat, ...mods(e) });
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
// A scene with `clicklock` locks the pointer when it's clicked (for mouse look); the browser only allows that
// inside the click itself, so it can't wait for Python. Escape unlocks it.
addEventListener('pointerdown', (e) => {
  wakeSound();
  const n = e.target && e.target._tv !== undefined ? objs.get(e.target._tv) : null;
  if (n && n.kind === 'scene' && n.clicklock && document.pointerLockElement !== n.el) {
    const p = n.el.requestPointerLock();
    if (p && p.catch) p.catch(() => {});
  }
}, true);
addEventListener('keydown', wakeSound, true);
addEventListener('error', (e) => report(e.error || new Error(e.message), 'the page'));
addEventListener('unhandledrejection', (e) => report(e.reason, 'the page'));

// ---------------------------------------------------------------- start up

// What custom JS (view.js(...) in Python) gets as `tv`.
const api = { objs, node, emit, three: () => THREE, loadThree, root };
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
