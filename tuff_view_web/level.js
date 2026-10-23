// tgame's level pieces in the page: world:jump_pad and world:boost_pad looking alive. Python makes each pad out of
// ordinary objects (a dark rim, a glowing top, a jump pad's ring, a boost pad's arrows) and does everything that
// matters itself: who stands on a pad, the launch, where a moving platform is and who rides it. This file only makes
// them look alive: a jump pad's glow breathes and rings rise from it, a boost pad's arrows light up one after another
// the way it points, a pad flashes and sends out a ring when it launches something, and speed lines streak across the
// screen when the player is boosted. Nothing moves while the game is paused (tgame puts data-paused on the scene's
// canvas, as anim.js reads it).
//
// engine.js imports this file. Python reaches it through view.js: window.tuffLevel.pad(group, kind, glows, arrows)
// when it makes a pad, .whoosh(id) when a pad launches something, .streak(scene) when the player is boosted. It has
// its own animation frame, asked for before engine.js asks for its own, so it comes first and its changes are drawn
// in the same frame.

const pads = new Map();     // a pad's group id -> { n, kind, glows, arrows (pairs of meshes), rings, burst, flash, t }
const streaks = new Map();  // a scene node -> its speed lines: { c (a canvas over the scene), g, left (seconds), lines }
const STREAK = 0.75;        // how long the speed lines last (seconds)
const FAR = 120;            // pads further from the camera than this (metres) hold still: too far to see them move
const TAU = Math.PI * 2;
let THREE = null;
let ringShape = null;       // the rings' geometry, shared
let then = 0;
let broken = false;

const tv = () => window.tuffView;

function three() {
  if (!THREE) {
    const t = tv() && tv().three();
    if (t && !t.failed && t.Mesh) THREE = t;
  }
  return THREE;
}

// ---------------------------------------------------------------- what Python asks for

// A new pad: its group node, "jump" or "boost", the ids of its glowing parts, and a boost pad's arrows (two bars
// each, back to front).
function pad(n, kind, glows, arrows) {
  if (!three() || !n || !n.obj) return;
  const mesh = (id) => tv().node(id).obj;
  const p = { n, kind, glows: glows.map(mesh), arrows: [], rings: [], burst: null, flash: 0, t: Math.random() * 4 };
  for (let i = 0; i + 1 < arrows.length; i += 2) p.arrows.push([mesh(arrows[i]), mesh(arrows[i + 1])]);
  if (kind === 'jump') for (let i = 0; i < 2; i++) p.rings.push(ring(p));
  pads.set(n.id, p);
  n.host.dirty = true;
}

// A pad launched something: it flashes, and a ring bursts out of it.
function whoosh(id) {
  const p = pads.get(id);
  if (!p) return;
  p.flash = 1;
  if (!p.burst) p.burst = ring(p);
  p.burst.userData.age = 0;
  p.burst.visible = true;
}

// The player was boosted: speed lines rush past the edges of the screen for a moment.
function streak(scene) {
  if (!scene || !scene.el) return;
  let s = streaks.get(scene);
  if (!s) {
    const c = document.createElement('canvas');
    c.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:none';
    scene.el.after(c);  // over the 3D view, under the HUD and the menus
    s = { c, g: c.getContext('2d'), left: 0, lines: null, age: 0 };
    streaks.set(scene, s);
  }
  s.left = STREAK;
  s.lines = null;
}

window.tuffLevel = { pad, whoosh, streak };

// A glowing ring that lies flat on a pad (it rises, or bursts outward). It's the pad's own: it moves, turns and hides
// with it, and is never in the way of a click or :looking_at.
function ring(p) {
  if (!ringShape) ringShape = new THREE.TorusGeometry(1, 0.035, 6, 56);
  const m = new THREE.Mesh(ringShape, new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false,
    blending: THREE.AdditiveBlending }));
  m.rotation.x = Math.PI / 2;
  m.position.y = 0.16;
  m.renderOrder = 2;
  m.raycast = () => {};
  m.userData.age = 1;
  p.n.obj.add(m);
  return m;
}

function forget(id, p) {
  pads.delete(id);
  for (const m of [...p.rings, p.burst]) if (m) { m.removeFromParent(); m.material.dispose(); }
}

// ---------------------------------------------------------------- every frame

function frame(now) {
  requestAnimationFrame(frame);
  const dt = then ? Math.min(0.1, (now - then) / 1000) : 0;
  then = now;
  if (broken || (!pads.size && !streaks.size)) return;
  try {
    for (const [id, p] of pads) animate(id, p, dt);
    for (const [scene, s] of streaks) speedLines(scene, s, dt);
  } catch (err) {
    broken = true;  // once: the game goes on with still pads
    tv().emit('error', { message: err && err.message ? err.message : String(err), where: 'the level pieces (level.js)',
      stack: err && err.stack ? String(err.stack).split('\n').slice(0, 6).join('\n') : '' });
  }
}

function paused(s) {
  return !!(s.paused || (s.el && s.el.hasAttribute('data-paused')));
}

function shown(o) {
  for (; o; o = o.parent) if (!o.visible) return false;
  return true;
}

function animate(id, p, dt) {
  const n = p.n;
  if (!tv().objs.has(id) || !n.obj.parent) { forget(id, p); return; }  // removed
  const s = n.host;
  if (paused(s) || !shown(n.obj)) return;
  const at = n.obj.position;
  const cam = s.camera.position;
  if (n.parent === s && (at.x - cam.x) ** 2 + (at.z - cam.z) ** 2 > FAR * FAR) return;
  p.t += dt;
  p.flash = Math.max(0, p.flash - dt * 2.2);
  const t = p.t;
  const glow = p.glows[0] && p.glows[0].material;
  if (p.kind === 'jump') {
    const k = 0.85 + 0.3 * Math.sin(t * 3.1) + p.flash * 2.4;
    for (const m of p.glows) if (m.material.emissive) m.material.emissiveIntensity = k;
    // Two rings rise from it, shrinking and fading: it pushes up.
    p.rings.forEach((r, i) => {
      const ph = (t * 0.7 + i / p.rings.length) % 1;
      r.position.y = 0.16 + ph * 1.6;
      r.scale.setScalar(0.86 * (1 - 0.32 * ph));
      r.material.opacity = Math.min(1, ph * 6) * (1 - ph) ** 1.4 * 0.75 * (1 + p.flash);
      if (glow && glow.emissive) r.material.color.copy(glow.emissive);
    });
  } else {
    const k = 0.75 + 0.15 * Math.sin(t * 4.3) + p.flash * 2;
    for (const m of p.glows) if (m.material.emissive) m.material.emissiveIntensity = k;
    // The arrows light up one after another, from the back to the front: the way it sends you.
    p.arrows.forEach((pair, i) => {
      const ph = (((t * 1.8 - i / p.arrows.length) % 1) + 1) % 1;
      const lit = (0.5 + 0.5 * Math.cos(ph * TAU)) ** 3;
      for (const m of pair) if (m.material.emissive) m.material.emissiveIntensity = 0.2 + 1.9 * lit + p.flash * 2;
    });
  }
  const b = p.burst;
  if (b && b.visible) {
    b.userData.age += dt / 0.5;
    const a = Math.min(1, b.userData.age);
    const grow = 1 + 1.7 * (1 - (1 - a) ** 2);
    if (p.kind === 'jump') b.scale.set(1.05 * grow, 1.05 * grow, 1);
    else b.scale.set(1.05 * grow, 1.65 * grow, 1);  // a boost pad's is long, like the pad
    b.position.y = 0.18 + a * 0.25;
    b.material.opacity = 0.95 * (1 - a) ** 2;
    if (glow && glow.emissive) b.material.color.copy(glow.emissive);
    if (a >= 1) b.visible = false;
  }
  s.dirty = true;
}

// Speed lines: thin wedges from the middle of the screen out past its edges, fading as the boost wears off. They're
// drawn again every few frames, each time a little differently, so they flicker past like wind.
function speedLines(scene, s, dt) {
  const c = s.c;
  if (!c.isConnected || !scene.el.isConnected) { c.remove(); streaks.delete(scene); return; }
  if (s.left <= 0) return;
  if (!paused(scene)) s.left = Math.max(0, s.left - dt);
  const g = s.g;
  const w = c.clientWidth || scene.el.clientWidth || 1;
  const h = c.clientHeight || scene.el.clientHeight || 1;
  const dpr = window.devicePixelRatio || 1;
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
  }
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.clearRect(0, 0, c.width, c.height);
  if (s.left <= 0) { c.style.display = 'none'; return; }
  c.style.display = '';
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const k = s.left / STREAK;
  if (!s.lines || s.age++ % 3 === 0) {
    s.lines = Array.from({ length: 48 }, (_, i) => [(i + Math.random()) / 48 * TAU, 0.42 + Math.random() * 0.3,
      1 + Math.random() * 3, 0.35 + Math.random() * 0.65]);  // all the way round, none bunched up
  }
  const cx = w / 2;
  const cy = h / 2;
  const R = Math.hypot(cx, cy);
  for (const [a, inner, wide, alpha] of s.lines) {
    const ca = Math.cos(a);
    const sa = Math.sin(a);
    const r0 = R * (inner + (1 - k) * 0.22);  // as it fades, they draw back to the edges
    const r1 = R * 1.04;
    g.beginPath();
    g.moveTo(cx + ca * r0, cy + sa * r0);
    g.lineTo(cx + ca * r1 - sa * wide, cy + sa * r1 + ca * wide);
    g.lineTo(cx + ca * r1 + sa * wide, cy + sa * r1 - ca * wide);
    g.closePath();
    g.fillStyle = `rgba(255, 255, 255, ${(0.6 * alpha * k).toFixed(3)})`;
    g.fill();
  }
}

requestAnimationFrame(frame);
