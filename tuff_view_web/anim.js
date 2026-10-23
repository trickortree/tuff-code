// Animation that runs in the page, every frame, with no work for Python: tgame's trees, bushes and flowers sway in
// the wind, coins spin and bob, people walk while they move (and stand breathing when they don't, or wave), and
// water ripples. A model's parts say how it moves with an `anim` prop (the kit in tuff_tgame.py): its style ("tree",
// "pine", "bush", "flower", "coin", "person"), or for a person's parts [style, part, pivot], the part being "leg_l",
// "arm_r", "head", "torso"... and the pivot the point it turns about (a hip, a shoulder, the neck). The model's group
// can choose with `anim` too (thing:animate): "auto" (its own way), "walk", "idle", "wave" or "none" (still).
// Everything holds still while the game is paused (tgame puts data-paused on the scene's canvas).
//
// engine.js calls add() when an object gets an `anim`, and frame() before it draws each frame (with the real time
// and the game's clock, which slow motion slows); it sets a model's `kids` to -1 when a part is added or removed (a
// held axe swapped for a sword), so its parts are looked at again. level.js's pads move on the same steps.
// Python never moves a model's parts after making them (only the model's group), so each part's pose is worked out
// from the one it was made with.

const live = new Set();   // groups (models) that move by themselves
let THREE = null;
let W = null;             // scratch vectors and quaternions, made once three.js is here

export function add(n, v) {
  const group = n.type === 'group' ? n : n.parent;
  if (!group || group.kind !== 'obj') return;
  const a = group.anim || (group.anim = { style: null, mode: 'auto', parts: [], held: [], kids: -1, rest: true });
  if (n === group) {
    a.mode = typeof v === 'string' ? v : 'auto';
  } else {
    const [style, role, pivot] = Array.isArray(v) ? v : [v];
    if (style) a.style = style;
    n.obj.userData.anim = { role: role || null, pivot: pivot || null };
  }
  a.kids = -1;  // look at its parts again
  live.add(group);
}

// For the page's stats (the tests): the models that move by themselves, the things they hold that move with them,
// and how many of those are no longer in their model (moved, though they've gone).
export function info() {
  let held = 0;
  let stale = 0;
  for (const g of live) {
    for (const h of g.anim.held) {
      held++;
      if (h.o.parent !== g.obj) stale++;
    }
  }
  return { live: live.size, held, stale };
}

// Moves everything for this frame: now is the real time, game the game's clock (fx.js's, slow in slow motion). If it
// ever fails, it stops (the error goes out once) and the game goes on still.
let broken = false;

export function frame(now, game, scenes) {
  if (broken) { for (const s of scenes) s.animDt = 0; return; }
  try {
    step(now, game, scenes);
  } catch (err) {
    broken = true;
    throw err;
  }
}

function step(now, game, scenes) {
  if (!THREE) {
    const t = window.tuffView && window.tuffView.three();
    if (!t || t.failed || !t.Quaternion) return;
    THREE = t;
    W = { q: new THREE.Quaternion(), turn: new THREE.Quaternion(), e: new THREE.Euler(), axis: new THREE.Vector3(),
      up: new THREE.Vector3(), y: new THREE.Vector3(0, 1, 0), x: new THREE.Vector3(1, 0, 0), z: new THREE.Vector3(0, 0, 1) };
  }
  for (const s of scenes) {
    // A scene's models move with each frame it's drawn anyway (Python changed something), and on their own at most
    // about 60 times a second, less while something else is drawing it: a screen faster than 60 Hz doesn't draw the
    // whole world again on every refresh just because a tree sways. That's real time; each step goes on by the
    // game's time, so in slow motion they move slower, as smoothly.
    if (s.dirty) s.busyAt = now;
    s.animDt = 0;
    if (s.animAt && !s.dirty && now - s.animAt < (now - s.busyAt < 50 ? 33 : 15)) continue;
    const since = s.animAt ? game - s.animGame : 0;
    s.animAt = now;
    s.animGame = game;
    if (!s.paused && !s.el.hasAttribute('data-paused')) s.animDt = Math.min(0.1, since / 1000);
    s.animT = (s.animT || 0) + s.animDt;
    if (s.waters && s.waters.size && ripple(s)) s.dirty = true;
  }
  for (const g of live) {
    if (!g.obj.parent) { live.delete(g); continue; }  // removed
    const s = g.host;
    const a = g.anim;
    const move = STYLES[a.style];
    if (!move || !s || !s.animDt || !g.obj.visible) continue;
    if (a.kids !== g.obj.children.length) parts(g, a);
    if (a.mode === 'none') {
      if (!a.rest) { still(a); s.dirty = true; }
      continue;
    }
    const c = s.camera.position;
    const p = g.obj.position;
    if (g.parent === s && (p.x - c.x) ** 2 + (p.z - c.z) ** 2 > 90 * 90) continue;  // too far away to see it move
    if (move(g, a, s.animT, s.animDt) === false) continue;
    a.rest = false;
    s.dirty = true;
  }
}

// A model's parts, each with the pose it was made with.
function parts(g, a) {
  a.kids = g.obj.children.length;
  a.parts = [];
  a.held = [];
  let top = 0.01;
  for (const o of g.obj.children) {
    const b = o.userData.animBase || (o.userData.animBase = { p: o.position.clone(), q: o.quaternion.clone(), s: o.scale.clone() });
    if (!o.isMesh) { a.held.push({ o, b }); continue; }  // a group of its own: something a person holds (its own thing)
    const info = o.userData.anim || {};
    a.parts.push({ o, b, role: info.role, pivot: info.pivot ? new THREE.Vector3().fromArray(info.pivot) : null, w: 1 });
    top = Math.max(top, b.p.y);
  }
  for (const p of a.parts) p.w = Math.max(0, p.b.p.y / top) ** 1.5;  // swaying: the higher up, the further it goes
}

function still(a) {
  for (const p of a.parts) {
    p.o.position.copy(p.b.p);
    p.o.quaternion.copy(p.b.q);
    p.o.scale.copy(p.b.s);
  }
  for (const h of a.held) h.o.position.y = h.b.p.y;
  a.rest = true;
}

// A part turned by q about `at` (null: the model's own middle, on the ground), from the pose it was made with, then
// lifted by `lift`.
function pose(p, q, at, lift) {
  const o = p.o;
  o.position.copy(p.b.p);
  if (at) o.position.sub(at);
  o.position.applyQuaternion(q);
  if (at) o.position.add(at);
  o.position.y += lift;
  o.quaternion.multiplyQuaternions(q, p.b.q);
}

// ---------------------------------------------------------------- the styles

// How far each sways (radians at the top) and how fast.
const SWAY = { tree: [0.028, 1.1], pine: [0.02, 0.9], bush: [0.04, 1.5], flower: [0.13, 2.1] };

function sway(g, a, t) {
  const [amp, speed] = SWAY[a.style];
  const o = g.obj;
  const upright = W.up.set(0, 1, 0).applyQuaternion(o.quaternion).y;
  if (upright < 0.95) {  // fallen over (thing:fall): no swaying on the ground
    if (!a.rest) { still(a); g.host.dirty = true; }
    return false;
  }
  // The wind leans it along x, a little along z, in gusts that roll across the land, so neighbours sway out of step.
  const ph = o.position.x * 0.31 + o.position.z * 0.23;
  const gust = 0.65 + 0.35 * Math.sin(t * 0.37 + ph * 0.2);
  const lx = (Math.sin(t * speed + ph) * 0.75 + Math.sin(t * speed * 2.7 + ph * 1.9) * 0.25) * amp * gust;
  const lz = Math.sin(t * speed * 0.73 + ph + 1.7) * amp * 0.45 * gust;
  // That lean in the model's own space (it's turned to face some way), as an axis and an angle.
  W.q.setFromEuler(W.e.set(lz, 0, -lx));
  W.turn.copy(o.quaternion).invert().multiply(W.q).multiply(o.quaternion);
  const w = Math.min(1, Math.max(-1, W.turn.w));
  const angle = 2 * Math.acos(w);
  const sin = Math.sqrt(1 - w * w);
  if (sin < 1e-6) return false;
  W.axis.set(W.turn.x / sin, W.turn.y / sin, W.turn.z / sin);
  for (const p of a.parts) pose(p, W.q.setFromAxisAngle(W.axis, angle * p.w), null, 0);
}

function coin(g, a, t, dt) {
  // A program that spins it (coin:spin) turns its group: then it doesn't spin twice as fast.
  const ry = g.obj.rotation.y;
  if (a.ry !== undefined && ry !== a.ry) a.turned = t;
  a.ry = ry;
  if (!(t - (a.turned ?? -1) < 0.5)) a.spin = ((a.spin || 0) + dt * 2.4) % (Math.PI * 2);
  const p = g.obj.position;
  const lift = Math.sin(t * 2.6 + p.x * 0.7 + p.z * 0.5) * 0.07;
  W.q.setFromAxisAngle(W.y, a.spin || 0);
  for (const part of a.parts) pose(part, W.q, null, lift);
}

function person(g, a, t, dt) {
  const p = g.obj.position;
  if (a.px === undefined) Object.assign(a, { px: p.x, pz: p.z, speed: 0, walk: 0, wave: 0, phase: 0 });
  // How fast it's going (smoothed: Python moves it at its own frame rate). A big jump is a move_to, not a step.
  let d = Math.hypot(p.x - a.px, p.z - a.pz);
  a.px = p.x;
  a.pz = p.z;
  if (d > 2) d = 0;
  a.speed += (d / dt - a.speed) * Math.min(1, dt * 6);
  const walking = a.mode === 'walk' || (a.mode === 'auto' && a.speed > 0.35);
  a.walk += ((walking ? 1 : 0) - a.walk) * Math.min(1, dt * 7);
  a.wave += ((a.mode === 'wave' ? 1 : 0) - a.wave) * Math.min(1, dt * 5);
  const speed = a.mode === 'walk' && a.speed < 0.6 ? 1.4 : Math.min(a.speed, 9);
  a.phase = (a.phase + dt * Math.PI * 2 * speed / (1.2 + speed * 0.25)) % (Math.PI * 2);  // two steps a stride
  const leg = Math.sin(a.phase) * (0.3 + Math.min(speed, 6) * 0.05) * a.walk;
  const breathe = Math.sin(t * 2.2) * (1 - a.walk);
  const lift = -0.73 * (1 - Math.cos(leg)) + breathe * 0.006;  // legs apart, it's lower: the foot down stays down
  const look = Math.sin(t * 0.45) * 0.22 * (1 - a.walk) * (1 - a.wave);
  for (const part of a.parts) {
    switch (part.role) {
      case 'leg_l': case 'leg_r':
        pose(part, W.q.setFromAxisAngle(W.x, part.role === 'leg_l' ? leg : -leg), part.pivot, lift);
        break;
      case 'arm_l':
        pose(part, W.q.setFromAxisAngle(W.x, -leg * 0.85 + breathe * 0.04), part.pivot, lift);
        break;
      case 'arm_r': {
        // Holding something: the hand stays where the thing is. Waving: up and out to the side, to and fro.
        const holds = a.held.length > 0;
        const swing = (holds ? 0.17 : leg * 0.85 - breathe * 0.04) * (1 - a.wave);
        W.turn.setFromAxisAngle(W.z, a.wave * (2.75 + 0.3 * Math.sin(t * 9)) + (holds ? 0.13 * (1 - a.wave) : 0));
        pose(part, W.turn.multiply(W.q.setFromAxisAngle(W.x, swing)), part.pivot, lift);
        break;
      }
      case 'head':
        pose(part, W.q.setFromAxisAngle(W.y, look), part.pivot, lift);
        break;
      case 'torso':
        pose(part, W.q.identity(), null, lift);
        part.o.scale.y = part.b.s.y * (1 + breathe * 0.014);
        break;
      default:
        pose(part, W.q.identity(), null, lift);
    }
  }
  for (const h of a.held) h.o.position.y = h.b.p.y + lift;  // what it holds goes up and down with its hand
}

const STYLES = { tree: sway, pine: sway, bush: sway, flower: sway, coin, person };

// ---------------------------------------------------------------- water

// Ripples: one small normal map, worked out again ~30 times a second from waves that run across it (it tiles, so
// every lake and sea shares it, a ripple every few metres). Each wave is sin(k·p + ωt); its sines and cosines over
// the map are worked out once, so a frame only mixes them.
const RES = 128;
const WAVES = [[1, 2, 0.9], [-2, 1, 0.8], [3, -1, 0.55], [2, 3, 0.45], [-4, -1, 0.4], [1, -5, 0.3], [5, 3, 0.25],
  [-6, 2, 0.2], [3, 7, 0.16], [-7, -5, 0.12]];  // [waves across x, across y, height]
let sea = null;

function waterMap() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = RES;
  const ctx = canvas.getContext('2d');
  const sin = [];
  const cos = [];
  for (const [fx, fy] of WAVES) {
    const s = new Float32Array(RES * RES);
    const c = new Float32Array(RES * RES);
    for (let y = 0; y < RES; y++) {
      for (let x = 0; x < RES; x++) {
        const b = (Math.PI * 2 * (fx * x + fy * y)) / RES;
        s[y * RES + x] = Math.sin(b);
        c[y * RES + x] = Math.cos(b);
      }
    }
    sin.push(s);
    cos.push(c);
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return { canvas, ctx, img: ctx.createImageData(RES, RES), sin, cos, tex, t: 0, drawn: -1, gx: new Float32Array(RES * RES),
    gy: new Float32Array(RES * RES), users: new Set() };
}

function drawWater(m) {
  const { gx, gy, img } = m;
  gx.fill(0);
  gy.fill(0);
  WAVES.forEach(([fx, fy, h], k) => {
    const omega = 1.6 * Math.sqrt(Math.hypot(fx, fy));  // longer waves go slower, like real ones
    const cp = Math.cos(omega * m.t) * h;
    const sp = Math.sin(omega * m.t) * h;
    const s = m.sin[k];
    const c = m.cos[k];
    for (let i = 0; i < gx.length; i++) {
      const slope = c[i] * cp - s[i] * sp;  // cos(k·p + ωt), times the height
      gx[i] += slope * fx;
      gy[i] += slope * fy;
    }
  });
  const d = img.data;
  const k = 0.09;
  for (let i = 0, j = 0; i < gx.length; i++, j += 4) {
    const nx = -gx[i] * k;
    const ny = gy[i] * k;
    const len = Math.sqrt(nx * nx + ny * ny + 1);
    d[j] = (nx / len * 0.5 + 0.5) * 255;
    d[j + 1] = (ny / len * 0.5 + 0.5) * 255;
    d[j + 2] = (1 / len * 0.5 + 0.5) * 255;
    d[j + 3] = 255;
  }
  m.ctx.putImageData(img, 0, 0);
  for (const tex of m.users) tex.needsUpdate = true;
}

function ripple(s) {
  if (!sea) sea = waterMap();
  let first = false;
  for (const w of s.waters) {
    const mat = w.obj.material;
    if (!mat.normalMap) {
      mat.normalMap = sea.tex.clone();
      mat.normalMap.needsUpdate = true;
      mat.normalScale.set(0.55, 0.55);
      mat.needsUpdate = true;
      sea.users.add(mat.normalMap);
      first = true;
    }
    const across = +w.p.r > 0 ? w.p.r * 2.08 : +w.p.size || 800;
    mat.normalMap.repeat.set(across / 9, across / 9);  // a 9 m square of ripples, again and again
  }
  if (!s.animDt && !first) return false;
  sea.t += s.animDt;
  if (Math.abs(sea.t - sea.drawn) > 1 / 30 || first) {
    sea.drawn = sea.t;
    drawWater(sea);
  }
  return true;
}
