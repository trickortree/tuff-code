// tgame's HUD (the end of tuff_tgame.py): health bars over things (in 3D a bar in the scene that faces the camera, in
// 2D one over the sprite), the player's health along the bottom of the screen, a countdown in the top right, an arrow
// that points the way to something, and a round minimap. tgame makes one <tg-hud> element and calls its methods like
// any element's (view.call): setup, bar, countdown, arrow, minimap, mark, unmark and player. It draws on a canvas of
// its own, over the game and under the game's HUD layer and menus, every animation frame after the engine has drawn,
// so bars, marks and the arrow are where the page has things (physics moves them here, not in Python). A 3D bar is a
// sprite in the scene that puts itself over its thing as the scene is drawn. It uses the page's API (window.tuffView).

const DEG = Math.PI / 180;
const BAR_W = 256;          // a 3D bar's picture, in pixels (it's drawn at about half that on screen, at most)
const BAR_H = 40;
const GREEN = '#3ccf6e';
const YELLOW = '#f2c230';
const RED = '#ef4b4b';
const FONT = 'Segoe UI, system-ui, sans-serif';

const tv = () => window.tuffView;
let W = null;               // three.js scratch objects, once three.js is here

function three() {
  const T = tv() && tv().three();
  if (!T || T.failed || !T.Vector3) return null;
  if (!W) W = { T, box: new T.Box3(), v: new T.Vector3(), c: new T.Vector3(), cam: new T.Vector3() };
  return T;
}

function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

function seen(o) {
  for (; o; o = o.parent) if (!o.visible) return false;
  return true;
}

// ---------------------------------------------------------------- health bars

// A bar's look, moving toward its value: `shown` (the bar) eases there, `ghost` (the light part a hurt leaves) waits a
// moment and drains after it, and `flash` fades (white for a hurt, green for a heal). True while it's still moving.
function stepBar(b, dt) {
  const want = b.most > 0 ? clamp(b.value / b.most, 0, 1) : 0;
  const was = [b.shown, b.ghost, b.flash];
  b.shown += (want - b.shown) * Math.min(1, dt * 14);
  if (Math.abs(want - b.shown) < 0.002) b.shown = want;
  if (b.hold > 0) b.hold -= dt;
  else b.ghost = Math.max(b.shown, b.ghost - Math.max(0.6 * dt, (b.ghost - b.shown) * Math.min(1, dt * 8)));
  if (b.ghost < b.shown || Math.abs(b.ghost - b.shown) < 0.002) b.ghost = b.shown;
  b.flash = Math.max(0, b.flash - dt * 3.2);
  return b.shown !== was[0] || b.ghost !== was[1] || b.flash !== was[2];
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.roundRect(x, y, w, h, Math.min(r, h / 2, w / 2));
}

// The bar itself: a dark rounded box, the light part a hurt leaves, the health (green, then yellow under half, red
// under a quarter), a shine along its top, and the flash over it.
function drawBar(g, x, y, w, h, b) {
  roundRect(g, x, y, w, h, h / 2);
  g.fillStyle = 'rgba(12, 14, 20, 0.8)';
  g.fill();
  const pad = Math.max(1.5, h * 0.17);
  const iw = w - pad * 2;
  const ih = h - pad * 2;
  if (b.ghost > b.shown) {
    roundRect(g, x + pad, y + pad, iw * b.ghost, ih, ih / 2);
    g.fillStyle = 'rgba(255, 214, 206, 0.9)';
    g.fill();
  }
  if (b.shown > 0) {
    const frac = b.most > 0 ? b.value / b.most : 0;
    roundRect(g, x + pad, y + pad, Math.max(ih * 0.6, iw * b.shown), ih, ih / 2);
    g.fillStyle = frac > 0.5 ? GREEN : frac > 0.25 ? YELLOW : RED;
    g.fill();
    g.fillStyle = 'rgba(255, 255, 255, 0.22)';
    roundRect(g, x + pad + ih * 0.3, y + pad + ih * 0.12, Math.max(0, iw * b.shown - ih * 0.6), ih * 0.3, ih * 0.15);
    g.fill();
  }
  if (b.flash > 0) {
    roundRect(g, x, y, w, h, h / 2);
    g.fillStyle = b.flashKind === 'heal' ? `rgba(120, 255, 160, ${0.6 * b.flash})` : `rgba(255, 255, 255, ${0.85 * b.flash})`;
    g.fill();
  }
  roundRect(g, x + 0.5, y + 0.5, w - 1, h - 1, h / 2);
  g.strokeStyle = 'rgba(255, 255, 255, 0.2)';
  g.lineWidth = 1;
  g.stroke();
}

// A 3D bar: a sprite in the scene, drawn from its own little picture. Just before the scene draws it, it goes over
// its thing (the top of everything the thing is made of, wherever physics has it) and sizes itself to stay readable.
function makeSprite(b, host) {
  const T = W.T;
  b.picture = document.createElement('canvas');
  b.picture.width = BAR_W;
  b.picture.height = BAR_H;
  b.tex = new T.CanvasTexture(b.picture);
  b.tex.colorSpace = T.SRGBColorSpace;
  const m = new T.SpriteMaterial({ map: b.tex, transparent: true, depthWrite: false, fog: false, toneMapped: false });
  const s = b.sprite = new T.Sprite(m);
  s.center.set(0.5, 0);
  s.renderOrder = 900;
  s.frustumCulled = false;
  s.raycast = () => {};
  s.onBeforeRender = (_r, _scene, cam) => placeSprite(b, host, cam);
  b.host = host;
  host.scene.add(s);
  b.redraw = true;
}

function placeSprite(b, host, cam) {
  const n = tv().objs.get(b.id);
  if (!n) return;
  const { box, c, cam: eye } = W;
  box.setFromObject(n.obj);
  if (box.isEmpty()) n.obj.getWorldPosition(c);
  else box.getCenter(c).setY(box.max.y);
  c.y += 0.3;
  const wide = box.isEmpty() ? 1 : clamp(Math.max(box.max.x - box.min.x, box.max.z - box.min.z), 0.9, 1.8);
  eye.setFromMatrixPosition(cam.matrixWorld);
  const perPx = 2 * Math.tan((cam.fov * DEG) / 2) / Math.max(1, host.el.clientHeight) * Math.max(0.01, c.distanceTo(eye));
  const label = b.label && tv().objs.get(b.label);
  if (label && seen(label.obj)) c.y = Math.max(c.y, label.obj.position.y + label.obj.scale.y + 5 * perPx);  // over it
  const w = clamp(wide / perPx, 56, 120) * perPx;  // between 56 and 120 pixels wide on screen
  const s = b.sprite;
  s.position.copy(c);
  s.scale.set(w, w * BAR_H / BAR_W, 1);
  s.updateMatrixWorld();
}

function dropSprite(b) {
  if (!b.sprite) return;
  b.sprite.removeFromParent();
  b.sprite.material.dispose();
  b.tex.dispose();
  b.sprite = null;
  if (b.host) b.host.dirty = true;
}

// Where a 2D canvas puts its game's units, in CSS pixels: [scale, x offset, y offset] (engine.js's view2d, which
// works in device pixels).
function view2d(c) {
  const r = window.devicePixelRatio || 1;
  let k = c.zoom * r;
  let ox = 0;
  let oy = 0;
  if (c.fit) {
    const f = Math.min(c.el.width / c.fit[0], c.el.height / c.fit[1]);
    k = f * c.zoom;
    ox = (c.el.width - c.fit[0] * f) / 2;
    oy = (c.el.height - c.fit[1] * f) / 2;
  }
  return [k / r, (ox - c.cx * k) / r, (oy - c.cy * k) / r];
}

// A 2D shape's width and height in its own units (before its scale), roughly as engine.js draws it.
function shapeBox(n) {
  const p = n.p;
  switch (n.type) {
    case 'circle': return [p.r * 2, p.r * 2];
    case 'text': return [String(p.text).length * p.size * 0.58, p.size];
    case 'line': case 'poly': {
      const ys = (p.points || []).map((q) => q[1]);
      const xs = (p.points || []).map((q) => q[0]);
      return ys.length ? [Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)] : [0, 0];
    }
    default: return [p.w || 0, p.h || 0];
  }
}

// ---------------------------------------------------------------- the minimap's land

const WATER = '#2f7fc8';
const SHALLOW = '#4f9fe3';

function toSrgb(c) {
  return Math.round(255 * clamp(c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055, 0, 1));
}

// The land seen from above: one pixel for each of its points, in the colours the page gave them, and blue where
// water covers it. Made again when the land's colours or its water change. `edge` is the colour around it.
function landPicture(t, scene) {
  const N = t.grid.N;
  const g = t.obj.geometry;
  const pos = g.attributes.position.array;
  const col = g.attributes.color.array;
  const o = t.obj.position;
  const waters = [...(scene.waters || [])].filter((w) => w.obj.visible).map((w) => [w.obj.position.x, w.obj.position.z, w.obj.position.y, +w.p.r || 0]);
  const pic = document.createElement('canvas');
  pic.width = pic.height = N;
  const img = pic.getContext('2d').createImageData(N, N);
  const d = img.data;
  let sr = 0;
  let sg = 0;
  let sb = 0;
  for (let k = 0; k < N * N; k++) {
    const x = pos[k * 3] + o.x;
    const h = pos[k * 3 + 1] + o.y;
    const z = pos[k * 3 + 2] + o.z;
    let level = null;
    for (const [wx, wz, wy, wr] of waters) {
      if (h < wy && (wr <= 0 || (x - wx) ** 2 + (z - wz) ** 2 < (wr * 1.04) ** 2) && (level === null || wy > level)) level = wy;
    }
    let r;
    let gr;
    let b;
    if (level !== null) {
      const hex = level - h < 0.7 ? SHALLOW : WATER;
      r = parseInt(hex.slice(1, 3), 16); gr = parseInt(hex.slice(3, 5), 16); b = parseInt(hex.slice(5, 7), 16);
    } else {
      r = toSrgb(col[k * 3]); gr = toSrgb(col[k * 3 + 1]); b = toSrgb(col[k * 3 + 2]);
    }
    d[k * 4] = r; d[k * 4 + 1] = gr; d[k * 4 + 2] = b; d[k * 4 + 3] = 255;
    sr += r; sg += gr; sb += b;
  }
  pic.getContext('2d').putImageData(img, 0, 0);
  const sea = waters.some((w) => w[3] <= 0);
  const m = N * N;
  return { pic, size: t.grid.size, x: o.x, z: o.z, edge: sea ? WATER : `rgb(${Math.round(sr / m * 0.85)}, ${Math.round(sg / m * 0.85)}, ${Math.round(sb / m * 0.85)})` };
}

// ---------------------------------------------------------------- the element

class TgHud extends HTMLElement {
  constructor() {
    super();
    this.opts = { three_d: false, view: 0, size: [800, 600] };
    this.bars = new Map();     // 'player', or a sprite's or object's id -> its bar
    this.clock = null;         // the countdown: { left, at (when it changed) }
    this.pointer = null;       // the arrow: { id or at, shown, color }
    this.map = null;           // the minimap: { size, corner, zoom, floors }
    this.marks = new Map();    // id -> colour
    this.playerId = 0;         // the player's figure (third person), or 0: the camera is where the player is
    this.land = null;          // the minimap's picture of the land, and what it was made from
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.then = 0;
    this.blank = true;
    this.loop = this.loop.bind(this);
  }

  connectedCallback() {
    this.style.cssText = 'position: absolute; inset: 0; display: block; pointer-events: none;';
    this.canvas.style.cssText = 'position: absolute; inset: 0; width: 100%; height: 100%; display: block;';
    if (!this.canvas.parentNode) this.appendChild(this.canvas);
    if (!this.raf) this.raf = requestAnimationFrame(this.loop);
  }

  disconnectedCallback() {
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    for (const b of this.bars.values()) dropSprite(b);
    this.bars.clear();
  }

  // ---- what tgame calls
  setup(o) { this.opts = { ...this.opts, ...o }; return null; }

  bar(id, o) {
    let b = this.bars.get(id);
    if (!b) {
      b = { id, shown: 1, ghost: 1, flash: 0, hold: 0, value: o.most, most: o.most };
      this.bars.set(id, b);
    }
    const lost = o.value < b.value;
    Object.assign(b, { kind: o.kind, value: o.value, most: o.most, label: o.label || 0 });
    if (o.flash) {
      b.flash = 1;
      b.flashKind = o.flash;
      if (lost) b.hold = 0.35;
    } else if (!lost) {
      b.shown = b.ghost = o.most > 0 ? clamp(o.value / o.most, 0, 1) : 0;  // a new bar starts full, not filling up
    }
    b.redraw = true;
    return null;
  }

  countdown(o) {
    if (!o) this.clock = null;
    else if (!this.clock || this.clock.left !== o.left) this.clock = { left: o.left, at: performance.now() };
    return null;
  }

  arrow(o) { this.pointer = o; return null; }
  minimap(o) { this.map = o; return null; }
  mark(id, color) { this.marks.set(id, color); return null; }
  unmark(id) { this.marks.delete(id); return null; }
  player(id) { this.playerId = id || 0; return null; }

  // ---- every frame
  loop(now) {
    this.raf = requestAnimationFrame(this.loop);
    const dt = this.then ? Math.min(0.1, (now - this.then) / 1000) : 0;
    this.then = now;
    try {
      this.frame(now, dt);
    } catch (err) {
      if (!this.failed) { this.failed = true; tv().emit('error', { message: err.message || String(err), where: 'drawing the HUD', stack: String(err.stack || '') }); }
    }
  }

  frame(now, dt) {
    const api = tv();
    if (!api) return;
    const view = api.objs.get(this.opts.view);
    if (!view) return;
    const r = window.devicePixelRatio || 1;
    const el = this.canvas;
    const w = Math.max(1, Math.round(el.clientWidth * r));
    const h = Math.max(1, Math.round(el.clientHeight * r));
    const sized = el.width !== w || el.height !== h;
    if (sized) { el.width = w; el.height = h; }
    // The 3D bars live in the scene: they only need a new picture (and the scene a new frame) when they change.
    let flat = 0;
    for (const b of [...this.bars.values()]) {
      const moving = stepBar(b, dt);
      if (b.kind !== '3d') { flat++; continue; }
      const n = api.objs.get(b.id);
      if (!n) { dropSprite(b); this.bars.delete(b.id); continue; }
      if (!b.sprite) { if (!three() || !n.host || !n.host.scene) continue; makeSprite(b, n.host); }
      const show = seen(n.obj);
      if (b.sprite.visible !== show) { b.sprite.visible = show; n.host.dirty = true; }
      if (moving || b.redraw) {
        b.redraw = false;
        const g = b.picture.getContext('2d');
        g.clearRect(0, 0, BAR_W, BAR_H);
        drawBar(g, 4, 4, BAR_W - 8, BAR_H - 8, b);
        b.tex.needsUpdate = true;
        n.host.dirty = true;
      }
    }
    const busy = flat || this.clock || (this.pointer && this.pointer.shown) || this.map;
    if (!busy && this.blank && !sized) return;
    const g = this.ctx;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, w, h);
    this.blank = !busy;
    if (!busy) return;
    g.setTransform(r, 0, 0, r, 0, 0);
    const cw = el.clientWidth;
    const ch = el.clientHeight;
    // The game's own area: all of the window in 3D; a 2D game's picture, which keeps its shape (bars beside it).
    let area = [0, 0, cw, ch];
    if (!this.opts.three_d && view.fit) {
      const [k, ox, oy] = view2d({ ...view, cx: 0, cy: 0 });
      area = [ox, oy, view.fit[0] * k, view.fit[1] * k];
    }
    for (const b of this.bars.values()) {
      if (b.kind === '2d') this.drawBar2d(g, b, api);
      else if (b.kind === 'player') this.drawPlayerBar(g, b, area);
    }
    let top = 14;
    if (this.clock) top = this.drawClock(g, now, area) + 10;
    if (this.opts.three_d && three()) {
      if (this.map) this.drawMap(g, view, area, top, now);
      if (this.pointer && this.pointer.shown) this.drawArrow(g, view, cw, ch, now);
    }
  }

  drawBar2d(g, b, api) {
    const n = api.objs.get(b.id);
    if (!n || n.dead) { this.bars.delete(b.id); return; }
    const p = n.p;
    if (!p.visible || !n.host) return;
    const [k, ox, oy] = view2d(n.host);
    const [sw, sh] = shapeBox(n);
    const sx = Math.abs(p.sx * p.scale);
    const sy = Math.abs(p.sy * p.scale);
    const wide = clamp(sw * sx, 36, 80) * k;
    const tall = Math.max(6, 8 * k);
    const x = ox + (p.x + (0.5 - p.ax) * sw * sx) * k;
    const y = oy + (p.y - p.ay * sh * sy) * k - tall - 6 * k;
    drawBar(g, x - wide / 2, y, wide, tall, b);
  }

  // The player's health, along the bottom left: a heart, then the bar.
  drawPlayerBar(g, b, area) {
    const x = area[0] + 16;
    const y = area[1] + area[3] - 16 - 26;
    roundRect(g, x, y, 250, 26, 13);
    g.fillStyle = 'rgba(12, 14, 20, 0.55)';
    g.fill();
    g.save();
    g.translate(x + 17, y + 14);
    const beat = 1 + 0.18 * b.flash;
    g.scale(beat, beat);
    g.beginPath();
    g.moveTo(0, 7);
    g.bezierCurveTo(-11, -1, -7, -10, 0, -5);
    g.bezierCurveTo(7, -10, 11, -1, 0, 7);
    g.fillStyle = b.most > 0 && b.value / b.most <= 0.25 ? RED : '#ff5f6d';
    g.fill();
    g.restore();
    drawBar(g, x + 32, y + 6, 208, 14, b);
  }

  // The countdown: m:ss in a dark pill at the top right, red under 10 seconds (it grows a little with each second then).
  drawClock(g, now, area) {
    const left = Math.max(0, this.clock.left);
    const m = Math.floor(left / 60);
    const s = left % 60;
    const text = m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
    const hurry = left < 10;
    g.font = `bold 26px ${FONT}`;
    const tw = g.measureText(text).width;
    const wide = tw + 58;
    const tall = 44;
    const x = area[0] + area[2] - 14 - wide;
    const y = area[1] + 14;
    const pulse = hurry ? 1 + 0.16 * Math.max(0, 1 - (now - this.clock.at) / 350) : 1;
    g.save();
    g.translate(x + wide / 2, y + tall / 2);
    g.scale(pulse, pulse);
    roundRect(g, -wide / 2, -tall / 2, wide, tall, tall / 2);
    g.fillStyle = hurry ? 'rgba(70, 12, 16, 0.82)' : 'rgba(12, 14, 20, 0.72)';
    g.fill();
    g.lineWidth = 2;
    g.strokeStyle = hurry ? RED : 'rgba(255, 255, 255, 0.25)';
    g.stroke();
    // a little clock face
    const fx = -wide / 2 + 24;
    g.beginPath();
    g.arc(fx, 0, 9, 0, Math.PI * 2);
    g.lineWidth = 2.4;
    g.strokeStyle = hurry ? '#ff8a8a' : '#ffffff';
    g.stroke();
    g.beginPath();
    g.moveTo(fx, -5);
    g.lineTo(fx, 0);
    g.lineTo(fx + 4, 2);
    g.stroke();
    g.fillStyle = hurry ? '#ff6b6b' : '#ffffff';
    g.textBaseline = 'middle';
    g.textAlign = 'left';
    g.fillText(text, fx + 16, 1);
    g.restore();
    return y + tall;
  }

  // Where the player is and which way it looks: its figure in third person, the camera otherwise.
  viewer(view) {
    const api = tv();
    const at = new W.T.Vector3();
    const body = this.playerId && api.objs.get(this.playerId);
    if (body) body.obj.getWorldPosition(at);
    else at.setFromMatrixPosition(view.camera.matrixWorld);
    return { at, yaw: view.yaw * DEG };
  }

  // Where a thing is: the middle of everything it's made of, and its top. null when it's gone.
  spotOf(o) {
    const api = tv();
    if (o.at) return { mid: new W.T.Vector3(o.at[0], o.at[1], o.at[2]), top: o.at[1] };
    const n = api.objs.get(o.id);
    if (!n) return null;
    if (!seen(n.obj)) return { hidden: true };
    const box = W.box.setFromObject(n.obj);
    const mid = new W.T.Vector3();
    if (box.isEmpty()) n.obj.getWorldPosition(mid);
    else box.getCenter(mid);
    return { mid, top: box.isEmpty() ? mid.y + 1 : box.max.y };
  }

  // The arrow: over the thing while it's in view, at the edge of the screen pointing the way when it isn't, along the
  // bottom when it's behind. Beside it, how far away it is.
  drawArrow(g, view, cw, ch, now) {
    const spot = this.spotOf(this.pointer);
    if (!spot || spot.hidden) return;
    const cam = view.camera;
    const me = this.viewer(view);
    const dist = Math.round(Math.hypot(spot.mid.x - me.at.x, spot.mid.z - me.at.z));
    const aim = new W.T.Vector3(spot.mid.x, spot.top + 0.5, spot.mid.z);
    const local = aim.clone().applyMatrix4(cam.matrixWorldInverse);
    const ndc = aim.clone().project(cam);
    const margin = 46;
    let x;
    let y;
    let dx;
    let dy;
    let over = false;
    if (local.z < 0 && Math.abs(ndc.x) < 0.94 && Math.abs(ndc.y) < 0.94) {
      over = true;
      x = (ndc.x + 1) / 2 * cw;
      y = (1 - ndc.y) / 2 * ch - 22 - 4 * Math.sin(now / 220);
      dx = 0;
      dy = 1;
    } else if (local.z >= 0) {  // behind: along the bottom, toward the side it's on
      const a = Math.atan2(local.x, local.z);
      x = cw / 2 + Math.sin(a) * (cw / 2 - margin);
      y = ch - margin - 8;
      dx = Math.sin(a);
      dy = Math.cos(a);
    } else {
      dx = ndc.x * cw / 2;
      dy = -ndc.y * ch / 2;
      const len = Math.hypot(dx, dy) || 1;
      dx /= len;
      dy /= len;
      const t = Math.min((cw / 2 - margin) / Math.max(1e-6, Math.abs(dx)), (ch / 2 - margin) / Math.max(1e-6, Math.abs(dy)));
      x = cw / 2 + dx * t;
      y = ch / 2 + dy * t;
    }
    g.save();
    g.translate(x, y);
    g.rotate(Math.atan2(dy, dx));
    g.beginPath();
    g.moveTo(17, 0);
    g.lineTo(-11, -14);
    g.lineTo(-5, 0);
    g.lineTo(-11, 14);
    g.closePath();
    g.lineJoin = 'round';
    g.lineWidth = 3;
    g.strokeStyle = 'rgba(16, 18, 24, 0.85)';
    g.stroke();
    g.fillStyle = this.pointer.color || YELLOW;
    g.fill();
    g.restore();
    const label = `${dist} m`;
    g.font = `bold 15px ${FONT}`;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    const lx = over ? x : x - dx * 36;
    const ly = over ? y - 28 : y - dy * 30;
    g.lineWidth = 4;
    g.lineJoin = 'round';
    g.strokeStyle = 'rgba(12, 14, 20, 0.85)';
    g.strokeText(label, lx, ly);
    g.fillStyle = '#ffffff';
    g.fillText(label, lx, ly);
  }

  // The minimap: north up, centred on the player, `zoom` 1 showing 50 m each way.
  drawMap(g, view, area, top, now) {
    const o = this.map;
    const S = o.size;
    const R = S / 2;
    const left = o.corner.endsWith('left');
    const up = o.corner.startsWith('top');
    const playerBar = this.bars.has('player');
    const cx = left ? area[0] + 14 + R : area[0] + area[2] - 14 - R;
    let cy = up ? (o.corner === 'top right' ? top : area[1] + 14) + R : area[1] + area[3] - 14 - R;
    if (!up && left && playerBar) cy -= 40;
    const me = this.viewer(view);
    const k = R / (50 / (o.zoom || 1));  // pixels a metre
    const px = (x) => cx + (x - me.at.x) * k;
    const pz = (z) => cy + (z - me.at.z) * k;
    g.save();
    g.beginPath();
    g.arc(cx, cy, R, 0, Math.PI * 2);
    g.shadowColor = 'rgba(0, 0, 0, 0.45)';
    g.shadowBlur = 10;
    g.fillStyle = '#1d2530';
    g.fill();
    g.shadowBlur = 0;
    g.clip();
    // the land: the terrain's own colours, or the ground and islands tgame said
    const t = view.lands && [...view.lands][0];
    if (t && t.grid) {
      const sig = `${t.obj.geometry.attributes.color.version}/${t.grid.N}/${[...(view.waters || [])].map((w) => `${w.obj.position.y}:${w.p.r}:${w.obj.visible}`).join(',')}`;
      if (!this.land || this.land.sig !== sig) {
        if (!this.land || now - (this.land.made || 0) > 300) this.land = { ...landPicture(t, view), sig, made: now };
      }
      const L = this.land;
      g.fillStyle = L.edge;
      g.fillRect(cx - R, cy - R, S, S);
      g.imageSmoothingEnabled = true;
      g.drawImage(L.pic, px(L.x - L.size / 2), pz(L.z - L.size / 2), L.size * k, L.size * k);
    } else {
      for (const f of o.floors || []) {
        if (f.island) {
          g.fillStyle = WATER;
          g.fillRect(cx - R, cy - R, S, S);
          g.beginPath(); g.arc(px(0), pz(0), (f.island + 5) * k, 0, Math.PI * 2); g.fillStyle = '#e8d39a'; g.fill();
          g.beginPath(); g.arc(px(0), pz(0), f.island * k, 0, Math.PI * 2); g.fillStyle = '#5fa83f'; g.fill();
        } else if (f.ground) {
          g.fillStyle = f.color;
          g.fillRect(px(-f.ground / 2), pz(-f.ground / 2), f.ground * k, f.ground * k);
        }
      }
    }
    // a faint grid every 10 m, so moving shows even on plain ground
    g.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    g.lineWidth = 1;
    const step = 10 * k >= 8 ? 10 : 50;
    g.beginPath();
    for (let gx = Math.ceil((me.at.x - R / k) / step) * step; gx <= me.at.x + R / k; gx += step) { g.moveTo(px(gx), cy - R); g.lineTo(px(gx), cy + R); }
    for (let gz = Math.ceil((me.at.z - R / k) / step) * step; gz <= me.at.z + R / k; gz += step) { g.moveTo(cx - R, pz(gz)); g.lineTo(cx + R, pz(gz)); }
    g.stroke();
    // the marks: a dot each, at the edge when they're further than the map shows
    const api = tv();
    const at = W.v;
    for (const [id, color] of [...this.marks]) {
      const n = api.objs.get(id);
      if (!n) { this.marks.delete(id); continue; }
      if (!seen(n.obj)) continue;
      n.obj.getWorldPosition(at);
      let mx = (at.x - me.at.x) * k;
      let mz = (at.z - me.at.z) * k;
      const d = Math.hypot(mx, mz);
      const out = d > R - 7;
      if (out) { mx *= (R - 7) / d; mz *= (R - 7) / d; }
      g.beginPath();
      g.arc(cx + mx, cy + mz, out ? 3.5 : 5, 0, Math.PI * 2);
      g.fillStyle = color;
      g.fill();
      g.lineWidth = 1.5;
      g.strokeStyle = 'rgba(12, 14, 20, 0.85)';
      g.stroke();
    }
    // the player, an arrow the way it looks
    g.save();
    g.translate(cx, cy);
    g.rotate(-me.yaw);
    g.beginPath();
    g.moveTo(0, -9);
    g.lineTo(7, 7);
    g.lineTo(0, 3.5);
    g.lineTo(-7, 7);
    g.closePath();
    g.lineJoin = 'round';
    g.lineWidth = 2.5;
    g.strokeStyle = 'rgba(12, 14, 20, 0.9)';
    g.stroke();
    g.fillStyle = '#ffffff';
    g.fill();
    g.restore();
    g.restore();
    // the rim, and north
    g.beginPath();
    g.arc(cx, cy, R - 1.5, 0, Math.PI * 2);
    g.lineWidth = 3;
    g.strokeStyle = 'rgba(255, 255, 255, 0.85)';
    g.stroke();
    g.beginPath();
    g.arc(cx, cy - R + 1, 9, 0, Math.PI * 2);
    g.fillStyle = 'rgba(12, 14, 20, 0.85)';
    g.fill();
    g.font = `bold 11px ${FONT}`;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillStyle = '#ffffff';
    g.fillText('N', cx, cy - R + 1.5);
  }
}

customElements.define('tg-hud', TgHud);
