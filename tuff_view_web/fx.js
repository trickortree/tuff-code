// tgame's effects in the page: the camera shaking (3D) or the game shaking (2D), text that pops up from a spot in a 3D
// world and floats away, rain and snow falling around the camera, the ground looking wet in the rain, and stars at
// night. Python (Effects in tuff_tgame.py) works out the rest: slow motion, the sky's colours for the weather and the
// time of day, and pop text in 2D (sprites).
//
// engine.js sends tgame's 'fx' calls here (call), and steps anim.js and physics.js by time(): a clock that runs at the
// game's speed, so in slow motion models, physics and these effects all slow down together. Everything here holds
// still while the game is paused. This file draws from its own animation frame, which runs just before engine.js's.

const DEG = Math.PI / 180;
const POP = { life: 1100, rise: 70, outline: 'rgba(10,12,18,0.7)' };   // pop text: ms it lasts, px it floats up
const RAIN = { drops: 1700, box: [44, 26, 44], fall: [17, 24], len: [0.55, 0.95], wind: 2.2, color: 0xb9cde0, opacity: 0.62 };
const SNOW = { flakes: 1500, box: [36, 22, 36], fall: [0.8, 1.6], size: 0.16, color: 0xffffff };
const STARS = 1400;

let THREE = null;
let speed = 1;          // the game's speed (slow motion)
let paused = false;
let realThen = 0;       // the last frame's real time (ms)
let clock = 0;          // the game's clock (ms): real time at the game's speed
let last = 0;           // the clock at the last effects frame
let broken = false;     // a frame went wrong: the effects stop (the error went out once)
const shakes = new Map();   // scene or canvas node -> its shake
const pops = new Set();     // 3D pop text
const weathers = new Map(); // scene node -> its rain or snow
const skies = new Map();    // scene node -> its stars
const wet = new Map();      // scene node -> how wet its ground is

// The game's clock: real time, at the game's speed. Asked for several times in one frame, it gives the same time.
export function time(now) {
  if (now !== realThen) {
    clock = realThen ? clock + (now - realThen) * speed : now;
    realThen = now;
  }
  return clock;
}

export function call(op, args) {
  const fn = OPS[op];
  if (!fn) throw new Error(`the effects have no '${op}'`);
  const out = fn(...args);
  return out === undefined ? null : out;
}

function tv() {
  return window.tuffView;
}

function three() {
  if (!THREE) {
    const t = tv() && tv().three();
    if (!t || t.failed || !t.Vector3) throw new Error("three.js isn't loaded");
    THREE = t;
  }
  return THREE;
}

const OPS = {
  speed(k) { speed = Math.max(0, +k || 0); },
  pause(on) { paused = !!on; },
  // A shake of a 3D scene's camera or a 2D game's canvas: strength 0-2, for `seconds` (game time).
  shake(id, strength, seconds) {
    const n = tv().node(id);
    if (n.kind === 'scene') hook(n);
    const old = shakes.get(n);
    const amp = old ? old.strength * fade(old) : 0;
    shakes.set(n, { strength: Math.max(+strength, amp), left: +seconds, total: +seconds, t: 0,
      seed: [0, 1, 2, 3, 4].map(() => Math.random() * 100) });
  },
  pop(id, text, x, y, z, color, size) { pop(tv().node(id), String(text), +x, +y, +z, color, +size); },
  weather(id, kind, strength) { weather(tv().node(id), kind, +strength); },
  wet(id, amount, ids) { soak(tv().node(id), +amount, ids || []); },
  stars(id, amount) { stars(tv().node(id), +amount); },
  info() {
    const drops = [...weathers.values()].reduce((a, w) => a + w.count, 0);
    return { speed, paused, clock: Math.round(clock), shaking: [...shakes.values()].filter((s) => s.left > 0).length,
      pops: pops.size, weather: [...weathers.values()].map((w) => w.kind), drops,
      stars: [...skies.values()].map((s) => s.amount), wet: [...wet.values()], broken };
  },
};

// ---------------------------------------------------------------- every frame

function frame(now) {
  requestAnimationFrame(frame);
  if (broken) return;
  const t = time(now);
  const dt = last && !paused ? Math.min(0.1, (t - last) / 1000) : 0;
  last = t;
  try {
    for (const [n, s] of shakes) shakeStep(n, s, dt);
    for (const p of pops) popStep(p, dt);
    for (const [n, w] of weathers) fallStep(n, w, dt);
  } catch (err) {
    broken = true;
    const message = err && err.message ? err.message : String(err);
    tv().emit('error', { message, where: 'effects', stack: err && err.stack ? String(err.stack).split('\n').slice(0, 6).join('\n') : '' });
  }
}

requestAnimationFrame(frame);

// ---------------------------------------------------------------- shaking

function fade(s) {
  const f = s.total > 0 ? Math.max(0, s.left) / s.total : 0;
  return Math.pow(f, 1.4);
}

// Smooth wobble from -1 to 1, different for each seed.
function wobble(t, seed) {
  return Math.sin(t * 41 + seed) * 0.55 + Math.sin(t * 73 + seed * 1.7) * 0.3 + Math.sin(t * 19 + seed * 2.3) * 0.15;
}

function shakeStep(n, s, dt) {
  if (dt) { s.left -= dt; s.t += dt; }
  const amp = paused ? 0 : s.strength * fade(s);
  if (n.kind === 'scene') {
    s.amp = amp;
    n.dirty = true;
  } else if (n.el) {
    // A 2D game: its canvas moves (a little bigger, so its edges stay off screen). The HUD on top stays still.
    const r = 9 * amp;
    const k = 1 + (2 * r + 2) / Math.max(1, Math.min(n.el.clientWidth, n.el.clientHeight));
    n.el.style.transform = amp > 0.001
      ? `translate(${(wobble(s.t, s.seed[0]) * r).toFixed(2)}px, ${(wobble(s.t, s.seed[1]) * r).toFixed(2)}px) scale(${k.toFixed(4)})`
      : '';
  }
  if (s.left <= 0) {
    s.amp = 0;
    if (n.el && n.kind !== 'scene') n.el.style.transform = '';
    shakes.delete(n);
  }
}

// A 3D scene's camera shakes while it's drawn (moved a little and turned a little), then goes back to where tgame put it.
// The stars stay around the camera. Whatever else the scene does before and after it's drawn still runs first.
function hook(n) {
  if (n.fx) return;
  three();
  const cam = n.camera;
  const saved = { p: new THREE.Vector3(), r: new THREE.Euler() };
  const before = n.scene.onBeforeRender;
  const after = n.scene.onAfterRender;
  n.fx = { moved: false };
  n.scene.onBeforeRender = function (...args) {
    before.apply(this, args);
    const sky = skies.get(n);
    if (sky) { sky.obj.position.copy(cam.position); sky.obj.updateMatrixWorld(); }
    const s = shakes.get(n);
    if (!s || !s.amp) return;
    saved.p.copy(cam.position);
    saved.r.copy(cam.rotation);
    const a = s.amp;
    cam.position.x += wobble(s.t, s.seed[0]) * 0.07 * a;
    cam.position.y += wobble(s.t, s.seed[1]) * 0.07 * a;
    cam.rotation.x += wobble(s.t, s.seed[2]) * 1.1 * a * DEG;
    cam.rotation.y += wobble(s.t, s.seed[3]) * 0.8 * a * DEG;
    cam.rotation.z += wobble(s.t, s.seed[4]) * 0.9 * a * DEG;
    cam.updateMatrixWorld();
    n.fx.moved = true;
  };
  n.scene.onAfterRender = function (...args) {
    after.apply(this, args);
    if (!n.fx.moved) return;
    cam.position.copy(saved.p);
    cam.rotation.copy(saved.r);
    cam.updateMatrixWorld();
    n.fx.moved = false;
  };
}

// ---------------------------------------------------------------- pop text (3D)

// Text that pops up at a spot, floats up and fades: `size` is its height on screen, in pixels, wherever it is.
function pop(n, text, x, y, z, color, size) {
  three();
  hook(n);
  const c = document.createElement('canvas');
  const g = c.getContext('2d');
  const px = 64;
  const font = `bold ${px}px Segoe UI, system-ui, sans-serif`;
  g.font = font;
  c.width = Math.max(8, Math.ceil(g.measureText(text).width) + 28);
  c.height = px + 30;
  g.font = font;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.lineJoin = 'round';
  g.lineWidth = 11;
  g.strokeStyle = POP.outline;
  g.strokeText(text, c.width / 2, c.height / 2 + 2);
  g.fillStyle = color || '#ffffff';
  g.fillText(text, c.width / 2, c.height / 2 + 2);
  const map = new THREE.CanvasTexture(c);
  map.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map, transparent: true, depthTest: false, depthWrite: false, fog: false }));
  s.center.set(0.5, 0);
  s.renderOrder = 2000;  // over everything, even labels drawn on top
  s.raycast = () => {};  // clicks go through it
  s.position.set(x, y, z);
  n.scene.add(s);
  const p = { n, s, age: 0, x, y, z, size, tall: c.height / px, aspect: c.width / c.height };
  pops.add(p);
  if (pops.size > 60) popDone(pops.values().next().value);
  popStep(p, 0);
}

const popAt = { v: null };

function popStep(p, dt) {
  const n = p.n;
  p.age += dt * 1000;
  if (p.age >= POP.life) { popDone(p); return; }
  const f = p.age / POP.life;
  const cam = n.camera;
  const v = popAt.v || (popAt.v = new THREE.Vector3());
  v.set(p.x, p.y, p.z);
  const dist = Math.max(0.05, v.distanceTo(cam.position));
  const perPx = 2 * Math.tan((cam.fov * DEG) / 2) / Math.max(1, n.el.clientHeight) * dist;  // metres per pixel there
  const grow = 1 + 0.3 * Math.sin(Math.min(1, f / 0.22) * Math.PI);
  const h = p.size * p.tall * grow * perPx;
  p.s.scale.set(h * p.aspect, h, 1);
  p.s.position.set(p.x, p.y + (1 - Math.pow(1 - f, 3)) * POP.rise * perPx, p.z);
  p.s.material.opacity = f < 0.55 ? 1 : Math.max(0, 1 - (f - 0.55) / 0.45);
  n.dirty = true;
}

function popDone(p) {
  pops.delete(p);
  p.s.removeFromParent();
  p.s.material.map.dispose();
  p.s.material.dispose();
  p.n.dirty = true;
}

// ---------------------------------------------------------------- rain and snow (3D)

function rand(a, b) {
  return a + Math.random() * (b - a);
}

// Rain: streaks (lines) falling fast and a little slanted. Snow: soft flakes drifting down. Both fill a box around
// the camera that goes where it goes, so it's raining wherever you walk.
function weather(n, kind, strength) {
  three();
  hook(n);
  const old = weathers.get(n);
  if (old) {
    old.obj.removeFromParent();
    old.obj.geometry.dispose();
    old.obj.material.dispose();
    weathers.delete(n);
  }
  n.dirty = true;
  if ((kind !== 'rain' && kind !== 'snow') || !(strength > 0)) return;
  const rain = kind === 'rain';
  const spec = rain ? RAIN : SNOW;
  const count = Math.round((rain ? RAIN.drops : SNOW.flakes) * Math.min(2, strength));
  const [W, H, D] = spec.box;
  const cam = n.camera.position;
  const w = { kind, count, box: spec.box, at: new Float32Array(count * 3), fall: new Float32Array(count), len: new Float32Array(count), t: 0 };
  for (let i = 0; i < count; i++) {
    w.at[i * 3] = cam.x + rand(-W / 2, W / 2);
    w.at[i * 3 + 1] = cam.y + rand(-H * 0.35, H * 0.65);
    w.at[i * 3 + 2] = cam.z + rand(-D / 2, D / 2);
    w.fall[i] = rand(spec.fall[0], spec.fall[1]);
    w.len[i] = rain ? rand(RAIN.len[0], RAIN.len[1]) : Math.random() * 100;  // snow: each flake's own sway
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * (rain ? 6 : 3)), 3));
  let obj;
  if (rain) {
    obj = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: RAIN.color, transparent: true,
      opacity: Math.min(0.85, RAIN.opacity * (0.8 + strength * 0.2)), depthWrite: false }));
  } else {
    obj = new THREE.Points(geo, new THREE.PointsMaterial({ color: SNOW.color, size: SNOW.size, map: flake(),
      transparent: true, depthWrite: false, alphaTest: 0.02 }));
  }
  obj.frustumCulled = false;
  obj.raycast = () => {};
  obj.renderOrder = 10;
  n.scene.add(obj);
  w.obj = obj;
  weathers.set(n, w);
  fallStep(n, w, 0);
}

let flakeMap = null;

function flake() {
  if (!flakeMap) {
    const c = document.createElement('canvas');
    c.width = c.height = 32;
    const g = c.getContext('2d');
    const grad = g.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.45, 'rgba(255,255,255,0.85)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 32, 32);
    flakeMap = new THREE.CanvasTexture(c);
    flakeMap.colorSpace = THREE.SRGBColorSpace;
  }
  return flakeMap;
}

// Keeps a coordinate within half a box of the camera, wrapping round to the other side.
function wrap(v, c, size) {
  const r = (((v - c + size / 2) % size) + size) % size;
  return c + r - size / 2;
}

function fallStep(n, w, dt) {
  const cam = n.camera.position;
  const [W, H, D] = w.box;
  const at = w.at;
  const pos = w.obj.geometry.attributes.position.array;
  const rain = w.kind === 'rain';
  w.t += dt;
  for (let i = 0; i < w.count; i++) {
    const k = i * 3;
    let x = at[k];
    let y = at[k + 1] - w.fall[i] * dt;
    let z = at[k + 2];
    if (rain) x += RAIN.wind * dt;
    else {
      x += Math.sin(w.t * 0.9 + w.len[i]) * 0.45 * dt;
      z += Math.cos(w.t * 0.7 + w.len[i] * 1.3) * 0.35 * dt;
    }
    if (y < cam.y - H * 0.35) y += H;
    else if (y > cam.y + H * 0.65) y -= H;
    x = wrap(x, cam.x, W);
    z = wrap(z, cam.z, D);
    at[k] = x;
    at[k + 1] = y;
    at[k + 2] = z;
    if (rain) {
      const len = w.len[i];
      const j = i * 6;
      pos[j] = x; pos[j + 1] = y; pos[j + 2] = z;
      pos[j + 3] = x - (RAIN.wind / w.fall[i]) * len; pos[j + 4] = y - len; pos[j + 5] = z;
    } else {
      pos[k] = x; pos[k + 1] = y; pos[k + 2] = z;
    }
  }
  w.obj.geometry.attributes.position.needsUpdate = true;
  n.dirty = true;
}

// The ground in the rain: darker and shinier (less rough), on the land and on world:ground and world:island.
function soak(n, amount, ids) {
  const a = Math.max(0, Math.min(1, amount));
  if (!a && !wet.has(n)) return;
  for (const id of ids) {
    const m = tv().objs.get(id);
    if (!m || !m.obj) continue;
    m.obj.traverse((o) => {
      const mat = o.isMesh && o.material;
      if (!mat || !('roughness' in mat)) return;
      const dry = mat.userData.fxDry || (mat.userData.fxDry = { rough: mat.roughness, color: mat.color.clone() });
      mat.roughness = dry.rough + (0.18 - dry.rough) * a;
      mat.color.copy(dry.color).multiplyScalar(1 - 0.32 * a);
      if (!a) delete mat.userData.fxDry;
    });
  }
  if (a) wet.set(n, a);
  else wet.delete(n);
  n.dirty = true;
}

// ---------------------------------------------------------------- stars at night (3D)

// Little points of light over the sky, brighter the darker it gets (0 hides them). They're drawn just after the sky,
// adding their light to it, and everything else is drawn over them.
function stars(n, amount) {
  three();
  hook(n);
  let s = skies.get(n);
  if (!s && amount > 0) {
    const pos = new Float32Array(STARS * 3);
    const col = new Float32Array(STARS * 3);
    const r = Math.min(400, n.camera.far * 0.5);
    for (let i = 0; i < STARS; i++) {
      const up = Math.pow(Math.random(), 0.8) * 0.97 + 0.03;   // more of them higher up
      const turn = Math.random() * Math.PI * 2;
      const flat = Math.sqrt(1 - up * up);
      pos[i * 3] = Math.cos(turn) * flat * r;
      pos[i * 3 + 1] = up * r;
      pos[i * 3 + 2] = Math.sin(turn) * flat * r;
      const b = Math.random() < 0.08 ? 1 : rand(0.35, 0.8);
      col[i * 3] = b * rand(0.85, 1);
      col[i * 3 + 1] = b * rand(0.9, 1);
      col[i * 3 + 2] = b;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    const mat = new THREE.PointsMaterial({ size: 1.7 * (window.devicePixelRatio || 1), sizeAttenuation: false, vertexColors: true,
      blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false, fog: false });
    const obj = new THREE.Points(geo, mat);
    obj.renderOrder = -1e5;  // after the sky dome (-1e6), before everything else
    obj.frustumCulled = false;
    obj.raycast = () => {};
    obj.position.copy(n.camera.position);
    n.scene.add(obj);
    s = { obj, amount: 0 };
    skies.set(n, s);
  }
  if (!s) return;
  s.amount = Math.max(0, Math.min(1, amount));
  s.obj.material.color.setScalar(s.amount);
  s.obj.visible = s.amount > 0.01;
  n.dirty = true;
}
