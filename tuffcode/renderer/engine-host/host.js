// Tuff Engine's preview page: tuffview://app/host/index.html, shown in an iframe by the Tuff Engine tab. It runs the
// real game engine (tuffview://app/engine/engine.js, from tuff_view_web, with three.js r186) behind a stand-in for
// pywebview's bridge, and draws what `tuff.py --scene` recorded (TuffIDE.scene / IPC engine:scene). It also lets
// people pick things, drag them and look around a 3D world. It never runs Tuff code and never edits code: it tells
// the parent page what happened, and the parent writes the code (which then comes back here as a new load).
//
// ================================================================== API (for renderer/js/tuff-engine.js)
// Messages are postMessage objects with a `tuffHost` field naming them. The parent is file://, an opaque origin,
// so both sides post with '*' and check the source: this page only listens to window.parent, and the parent should
// check e.source === iframe.contentWindow.
//
// PARENT -> HOST
//   hello                     Answered with `ready` (also sent by itself once the engine has started).
//   load   { seq, mode: '2d'|'3d', size: [W, H], batch, things, player, canvas, camera, roots,    <- a scene dump
//            gameDirRel, assetEpoch, cam?, camMode?, select? }
//            Draws a dump in place of the last one. Pass the dump's fields as they are, with these changes:
//            - things[n].drag: set it to null for things the editor can't edit (made in a loop, a function, ...).
//              Things keep their dump index `i`, and every message here names things by it.
//            - player.drag: null when the player's start can't be dragged (otherwise the start marker drags).
//            - gameDirRel: the game file's folder relative to the open project ('' at the project's root, '/'
//              separators). Pictures, sounds and models ("asset:<rel>") load from tuffview://app/project/<that>/<rel>.
//            - assetEpoch: a number; bump it when a picture or model changes on disk so it loads again.
//            - cam (3D): the editor camera { tx, ty, tz, az, el, dist } to use (the one the last `cam` gave for this
//              file). null: fit the camera around the world. Left out: keep the current camera (same file again).
//            - camMode (3D): 'editor' (the default, the orbit camera) or 'game' (the game's own starting camera).
//            - select: like `select` below, drawn with the load. Without it the selection is cleared, so send
//              `select` again after `loaded`.
//            The old scene goes; a 3D scene's WebGL context is kept from one 3D load to the next.
//   select { is: [i, ...] | ['player'] | [] }
//            2D: a blue box around the union of those things. 3D: a blue wire box in each thing (it moves, turns
//            and scales with it); 'player' outlines the start marker.
//   view   { cam: 'editor' | 'game' }  (3D) The orbit camera, or the game's starting camera (view only: no
//            picking, dragging or orbiting; camera-attached things like a held axe show; the start marker hides).
//   camera { cam: { tx, ty, tz, az, el, dist } }  (3D) Move the editor camera (answered with `cam`).
//   cancel {}                 Stop a drag in progress and put the thing back (Escape pressed in the parent).
//   ask    { tag, what, i? }  Answered with `reply { tag, value, error }`:
//            'snapshot'      a PNG data: URL of the preview, from the engine
//            'screen', i     where thing i (or 'player') is, in this page's CSS pixels: [x, y]; 3D: its middle
//            'stats'         { objs, mode, sceneBg, cameraNodesVisible, things, sel, camMode, cam, outlines, marker,
//                              load, b, scene, sel2d }
//            'pos', i        thing i's live position: 2D { x, y }, 3D { x, y, z } (follows a drag in progress)
//            'fetch', url    { status, type, size } of a tuffview://app/ address (tests of what the scheme serves)
//
// HOST -> PARENT
//   ready  { webgl }          The engine has started (webgl: WebGL 2 works here). Send `load` after this.
//   loaded { seq, objs, mode } A load has been drawn (seq is the load's).
//   pick   { i, point? }      Pointer down on thing i (a number, or 'player'), or i: null for a click (no drag) on
//                             empty space, the island or the ground. 3D adds point: [x, y, z] on what was hit.
//   drag   { i, phase: 'end', dx, dy, alt }   2D: thing i was dragged by (dx, dy) game units (whole numbers).
//          { i, phase: 'end', x, z, alt }     3D: thing i's group (or the player marker) now stands at x, z, snapped
//                                             to 0.5 (0.1 with Alt held). Moving the thing was live; write the code.
//          { i, phase: 'cancel' }            Escape during a drag: the thing went back.
//   cam    { tx, ty, tz, az, el, dist }       The 3D editor camera after orbiting, panning, zooming or fitting (at
//                                             most every 200 ms, and once at the end). Keep it per file.
//   key    { key, code, ctrl, shift, alt, meta }   A key pressed while this page had focus.
//   wheel  { dx, dy, ctrl, shift, alt, meta }      2D only: the wheel over the preview (Ctrl+wheel zooms the stage).
//   focus  {}                 After every pointer up: give focus back to the stage so IDE shortcuts work. (Move
//                             focus only then, not on `pick`: during a drag this page needs it for Escape.)
//   error  { message, where } The engine (or this page) couldn't draw something.
//   reply  { tag, value, error }  The answer to an `ask`.
//
// Controls. 2D: press a thing to pick it, drag to move it (live), click empty space to pick nothing. 3D: press a
// thing to pick it and drag it over the ground at its height; drag empty space (or a thing that can't move, or
// right-drag anywhere) to orbit; Shift-drag or middle-drag to pan; the wheel zooms; double-click a thing to frame it.
// The HUD over a 3D world picks and drags like 2D, before the world. Size the iframe to the game's W:H (a 2D
// game is letterboxed in it, filled with its background). The dump comes from window.tuff.engine.scene(file,
// source) (preload.js); its things are { i, kind, layer, ids, x, y, z, dims, k, heading, hidden, made, var, drag },
// where made[0] is the top-level line that made it (made.length > 1: inside a loop, an if or a function) and `var` is only the
// last variable that held it, so judge editability by `made`, not by `var`. tests: test/e2e/suites/engine-host.mjs.
// ==================================================================

(() => {
  'use strict';

  const post = (type, data = {}) => parent.postMessage({ ...data, tuffHost: type }, '*');
  let webgl = null;

  // pywebview's bridge, as engine.js expects it. ready() gives what the page can do; ev() gets the page's events,
  // of which only errors and the answers to asks matter here (picking and dragging are worked out below).
  window.pywebview = {
    api: {
      ready: (info) => { webgl = !!(info && info.webgl); post('ready', { webgl }); return Promise.resolve(); },
      ev: (_seq, events) => {
        for (const e of events || []) {
          if (e.type === 'error') post('error', { message: String(e.message || ''), where: String(e.where || '') });
          else if (e.type === 'reply') post('reply', { tag: e.tag, value: e.value, error: e.error || null });
        }
        return Promise.resolve();
      },
    },
  };

  const DEG = Math.PI / 180;
  const SEL = '#4da3ff';
  const MARKER = 900001;          // + B: the player's start marker (a group), and its capsule (+1)
  const OUTLINES = 900100;        // + B: selection outlines, counting up within a load
  const DROP_CALLS = new Set(['sound', 'sound_stop', 'sound_volume', 'sound_state', 'tones', 'unlock', 'css', 'cursor']);
  const CAM_KEYS = ['cx', 'cy', 'cz', 'yaw', 'pitch', 'roll', 'look'];
  const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
  const tv = () => window.tuffView;
  const objs = () => window.tuffView.objs;
  let applySeq = 0;
  const send = (cmds) => (cmds.length ? window.__tv.apply([[++applySeq, cmds]]) : 0);

  // ---------------------------------------------------------------- state

  let loadNo = 0;
  let loadToken = 0;
  let L = null;                   // the scene being shown (see load())
  let camMode = 'editor';
  let cam = null;                 // the 3D editor camera: { tx, ty, tz, az, el, dist }, degrees
  let selIs = [];
  let outlineIds = [];
  let outlineNo = 0;
  let press = null;               // what the pointer is doing (see onDown)
  const sel2d = () => document.getElementById('sel2d');

  // ---------------------------------------------------------------- messages from the parent

  const queue = [];
  addEventListener('message', (e) => {
    if (e.source !== parent || !e.data || typeof e.data !== 'object' || !e.data.tuffHost) return;
    if (!window.__tv || !window.tuffView) { queue.push(e.data); return; }
    handle(e.data);
  });
  addEventListener('DOMContentLoaded', () => {
    // Module scripts run before DOMContentLoaded, so the engine is there now. Space and the arrows are the
    // editor's here, not a game's.
    if (window.tuffView) window.tuffView.gameKeys = false;
    else post('error', { message: "The game engine didn't start.", where: 'the preview page' });
    while (queue.length && window.__tv) handle(queue.shift());
  });

  let heldLoad = null; // the newest scene that came while the mouse was held
  let heldTimer = null;
  function startLoad(m) {
    load(m).catch((err) => post('error', { message: String(err && err.message || err), where: 'loading the scene' }));
  }
  function loadHeld() {
    clearTimeout(heldTimer);
    const m = heldLoad;
    heldLoad = null;
    if (m) startLoad(m);
  }

  function handle(m) {
    try {
      switch (m.tuffHost) {
        case 'hello': post('ready', { webgl: webgl ?? !!document.createElement('canvas').getContext('webgl2') }); break;
        // A new scene while the mouse is held waits until it's let go: loading would drop the drag (a refresh
        // after the last change can land just as the kid presses on something).
        case 'load':
          if (!press) { startLoad(m); break; }
          heldLoad = m;
          // A release this page never sees can't keep the scene old for long.
          clearTimeout(heldTimer);
          heldTimer = setTimeout(() => { if (heldLoad) { finish(null, true); loadHeld(); } }, 4000);
          break;
        case 'select': select(Array.isArray(m.is) ? m.is : []); break;
        case 'view': setCamMode(m.cam === 'game' ? 'game' : 'editor'); break;
        case 'camera': if (m.cam && L && L.mode === '3d') { cam = { ...cam, ...m.cam }; applyCam(); postCam(true); } break;
        case 'ask': ask(m); break;
        case 'cancel': if (press && press.started) finish(null, true); else press = null; loadHeld(); break;
        default: break;
      }
    } catch (err) {
      post('error', { message: String(err && err.message || err), where: `the preview page (${m.tuffHost})` });
    }
  }

  // ---------------------------------------------------------------- loading a scene dump

  // Every load gets its own id range (B + the dump's ids), so an id the engine has seen before (and maybe marked
  // as broken) is never used again.
  async function load(m) {
    const token = ++loadToken;
    const is3d = m.mode === '3d';
    const batch = Array.isArray(m.batch) ? m.batch : [];
    if (batch.some((c) => c[0] === 'c' && (c[2] === 'scene' || c[2] === 'obj')) && !tv().three()) {
      try { await tv().loadThree(); } catch { /* the engine reports it when it gets to the scene */ }
      if (token !== loadToken) return;
    }
    const B = ++loadNo * 1e6;
    const prev = L;
    const rawScene = is3d && m.roots ? m.roots.view : null;
    const old = prev && prev.mode === '3d' && prev.sceneId ? objs().get(prev.sceneId) : null;
    const makesScene = rawScene && batch.some((c) => c[0] === 'c' && c[1] === rawScene && c[2] === 'scene');
    const keep = is3d && old && old.kind === 'scene' && makesScene ? prev.sceneId : null;
    const mapId = (id) => (!id ? 0 : keep && id === rawScene ? keep : id + B);
    if (m.camMode === 'game' || m.camMode === 'editor') camMode = m.camMode;
    const editorCam = is3d && camMode === 'editor';
    const epoch = encodeURIComponent(String(m.assetEpoch ?? 0));
    const dirParts = String(m.gameDirRel || '').split(/[\\/]+/).filter(Boolean);
    const asset = (rel) => `tuffview://app/project/${[...dirParts, ...rel.split('/').filter(Boolean)].map(encodeURIComponent).join('/')}?v=${epoch}`;
    const fix = (v) => {
      if (typeof v === 'string') return v.startsWith('asset:') ? asset(v.slice(6)) : v;
      if (Array.isArray(v)) return v.map(fix);
      if (v && typeof v === 'object') { const o = {}; for (const k in v) o[k] = fix(v[k]); return o; }
      return v;
    };
    const sceneProps = (p) => {
      const q = { ...p };
      delete q.clicklock; // a click locks the mouse for looking around in a game, not in the editor
      if (editorCam) for (const k of CAM_KEYS) delete q[k];
      return q;
    };

    const out = [];
    // What was there goes: everything at the top level, except a 3D scene that is kept (only what's inside it goes).
    for (const el of [...tv().root.children]) {
      const id = el._tv;
      if (id === undefined || id === keep) continue;
      const n = objs().get(id);
      if (n && n.kind === 'scene') { try { n.renderer.forceContextLoss(); } catch { /* already lost */ } }
      out.push(['r', id]);
    }
    if (keep) {
      for (const kid of [...old.kids]) out.push(['r', kid]);
      out.push(['s', keep, { sky: null, fog: null, bg: null }]);
    }
    const cameraNodes = new Set();
    const gameVisible = new Map();
    for (const c of batch) {
      switch (c[0]) {
        case 'c': {
          const [, id, kind, type, parentId, props] = c;
          let p = props ? fix(props) : null;
          if (kind === 'scene' && p) p = sceneProps(p);
          if (keep && id === rawScene) { out.push(['s', keep, p || {}]); break; }
          if (p && p.camera) cameraNodes.add(mapId(id));
          out.push(['c', mapId(id), kind, type, mapId(parentId), p]);
          break;
        }
        case 's': {
          let p = fix(c[2] || {});
          if (is3d && c[1] === rawScene) p = sceneProps(p);
          if ('visible' in p) gameVisible.set(mapId(c[1]), p.visible !== false);
          if (Object.keys(p).length) out.push(['s', mapId(c[1]), p]);
          break;
        }
        case 'r': out.push(['r', mapId(c[1])]); break;
        case 'k':
          if (c[4] != null) break;                                  // an ask: there's no Python to answer
          if (!c[1] && DROP_CALLS.has(c[2])) break;                 // no sound in the editor
          if (c[1] && c[2] === 'lock') break;
          out.push(['k', mapId(c[1]), c[2], fix(c[3] || [])]);
          break;
        default: break;                                             // 'j' (custom JS) never runs here
      }
    }

    const things = Array.isArray(m.things) ? m.things : [];
    const idToThing = new Map();
    const meta = new Map();
    for (const t of things) {
      const ids = (t.ids || []).map(mapId);
      for (const id of ids) idToThing.set(id, t.i);
      meta.set(t.i, { i: t.i, ids, drag: t.drag || null, layer: t.layer, kind: t.kind, dims: t.dims || null, k: t.k || [1, 1, 1],
        x: t.x, y: t.y, z: t.z });
    }
    let player = null;
    if (is3d && m.player && rawScene) {
      const pl = m.player;
      const sceneId = keep || mapId(rawScene);
      player = { ids: [B + MARKER, B + MARKER + 1, ...(pl.ids || []).map(mapId), ...((pl.held && pl.held.ids) || []).map(mapId)],
        drag: pl.drag === null ? null : 'xz', x: pl.x || 0, y: pl.y || 0, z: pl.z || 0 };
      for (const id of player.ids) idToThing.set(id, 'player');
      out.push(['c', B + MARKER, 'obj', 'group', sceneId, { x: player.x, y: player.y, z: player.z }]);
      out.push(['c', B + MARKER + 1, 'obj', 'capsule', B + MARKER, { r: 0.3, h: 1.1, y: 0.85, seg: 12, color: SEL, opacity: 0.45, shadow: false }]);
    }

    L = { seq: m.seq, mode: is3d ? '3d' : '2d', size: Array.isArray(m.size) ? m.size : [800, 600], B, idToThing, meta, player,
      sceneId: is3d && rawScene ? keep || mapId(rawScene) : null,
      gameCanvas: !is3d && m.roots && m.roots.view ? mapId(m.roots.view) : null,
      hudCanvas: m.roots && m.roots.hud ? mapId(m.roots.hud) : null,
      gameCamera: is3d ? m.camera || null : null, cameraNodes, gameVisible };
    outlineIds = [];
    outlineNo = 0;
    selIs = [];
    press = null;
    send(out);
    await settle();
    if (token !== loadToken) return;

    if (is3d && L.sceneId) {
      if (m.cam) cam = { ...defaultCam(), ...m.cam };
      else if (m.cam === null || !cam || !prev || prev.mode !== '3d') cam = fitCam(things, m.player);
      applyView();
      postCam(true);
    }
    if (Array.isArray(m.select)) select(m.select);
    else drawSel();
    post('loaded', { seq: m.seq, objs: objs().size, mode: L.mode });
  }

  // The first 3D batch waits for three.js to load; the engine applies the rest once it's there.
  async function settle() {
    const end = performance.now() + 8000;
    while (window.__tv.apply([]) > 0 && performance.now() < end) await new Promise((r) => setTimeout(r, 16));
  }

  // ---------------------------------------------------------------- the 3D camera

  function defaultCam() { return { tx: 0, ty: 0, tz: -6, az: 0, el: 35, dist: 18 }; }

  // The middle of the x/z box around every object (not the island or the ground) and the player.
  function fitCam(things, pl) {
    const pts = things.filter((t) => t.layer === 'world' && t.kind !== 'island' && t.kind !== 'ground').map((t) => [t.x, t.z]);
    if (pl) pts.push([pl.x || 0, pl.z || 0]);
    if (!pts.length) return defaultCam();
    const xs = pts.map((p) => p[0]);
    const zs = pts.map((p) => p[1]);
    const [x0, x1, z0, z1] = [Math.min(...xs), Math.max(...xs), Math.min(...zs), Math.max(...zs)];
    return { tx: (x0 + x1) / 2, ty: 0, tz: (z0 + z1) / 2, az: 0, el: 35, dist: clamp(1.4 * Math.hypot(x1 - x0, z1 - z0), 12, 150) };
  }

  function camPos(c) {
    const el = c.el * DEG;
    const az = c.az * DEG;
    return [c.tx + c.dist * Math.cos(el) * Math.sin(az), c.ty + c.dist * Math.sin(el), c.tz + c.dist * Math.cos(el) * Math.cos(az)];
  }

  // cx, cy, cz, then look: the engine aims the camera after placing it.
  function applyCam() {
    if (!L || L.mode !== '3d' || !L.sceneId || !cam || camMode !== 'editor') return;
    const [cx, cy, cz] = camPos(cam);
    send([['s', L.sceneId, { cx, cy, cz, look: [cam.tx, cam.ty, cam.tz] }]]);
  }

  // Shows the editor's camera (camera-attached things hidden, the start marker shown) or the game's.
  function applyView() {
    if (!L || L.mode !== '3d' || !L.sceneId) return;
    const cmds = [];
    const game = camMode === 'game';
    for (const id of L.cameraNodes) cmds.push(['s', id, { visible: game ? L.gameVisible.get(id) !== false : false }]);
    if (L.player) cmds.push(['s', L.B + MARKER, { visible: !game }]);
    const gc = L.gameCamera;
    if (game && gc) cmds.push(['s', L.sceneId, { cx: gc.cx, cy: gc.cy, cz: gc.cz, yaw: gc.yaw, pitch: gc.pitch, roll: 0 }]);
    send(cmds);
    if (!game) applyCam();
  }

  function setCamMode(mode) {
    if (mode === camMode) return;
    camMode = mode;
    press = null;
    applyView();
    loadHeld();
  }

  let camTimer = null;
  let camLast = 0;
  function postCam(now) {
    if (!cam) return;
    const go = () => { camTimer = null; camLast = performance.now(); post('cam', { ...cam }); };
    clearTimeout(camTimer);
    if (now || performance.now() - camLast >= 200) go();
    else camTimer = setTimeout(go, 200 - (performance.now() - camLast));
  }

  function three() {
    const T = tv().three();
    const n = L && L.sceneId ? objs().get(L.sceneId) : null;
    return T && !T.failed && n && n.kind === 'scene' ? { T, n } : null;
  }

  function ray(px, py) {
    const g = three();
    if (!g) return null;
    const r = g.n.el.getBoundingClientRect();
    const ndc = new g.T.Vector2(((px - r.left) / (r.width || 1)) * 2 - 1, -((py - r.top) / (r.height || 1)) * 2 + 1);
    g.n.scene.updateMatrixWorld();
    // The camera isn't in the scene, and only a drawn frame brings it up to date. On a slow PC a click can
    // come before that frame (just after a load, a camera fit or a resize), so bring it up to date here.
    const cam = g.n.camera;
    if (cam.isPerspectiveCamera && r.width && r.height && Math.abs(cam.aspect - r.width / r.height) > 1e-3) {
      cam.aspect = r.width / r.height;
      cam.updateProjectionMatrix();
    }
    cam.updateMatrixWorld();
    const rc = new g.T.Raycaster();
    rc.setFromCamera(ndc, g.n.camera);
    return { ...g, rc };
  }

  function shown(o) {
    for (; o; o = o.parent) if (!o.visible) return false;
    return true;
  }

  // Like engine.js's pick3d: the nearest pickable object under the pointer, as a thing (or 'player'). The island,
  // the ground and the sky count as empty space.
  function pick3d(px, py) {
    const g = ray(px, py);
    if (!g) return { i: null, point: null };
    for (const hit of g.rc.intersectObjects(g.n.scene.children, true)) {
      let o = hit.object;
      while (o && o.userData.tv === undefined) o = o.parent;
      const m = o && objs().get(o.userData.tv);
      if (!m || !m.pick || !shown(hit.object)) continue;
      const point = [hit.point.x, hit.point.y, hit.point.z];
      for (let k = m; k; k = k.parent) {
        if (!L.idToThing.has(k.id)) continue;
        const i = L.idToThing.get(k.id);
        const t = L.meta.get(i);
        return t && (t.kind === 'island' || t.kind === 'ground') ? { i: null, point, floor: true } : { i, point };
      }
      return { i: null, point };
    }
    return { i: null, point: null };
  }

  function groupOf(i) {
    if (i === 'player') return L.player ? L.B + MARKER : null;
    const t = L.meta.get(i);
    return t && t.ids.length ? t.ids[0] : null;
  }

  function onPlane(px, py, y) {
    const g = ray(px, py);
    if (!g) return null;
    const hit = new g.T.Vector3();
    return g.rc.ray.intersectPlane(new g.T.Plane(new g.T.Vector3(0, 1, 0), -y), hit) ? hit : null;
  }

  // ---------------------------------------------------------------- 2D: where things are on screen

  // A canvas's game units -> this page's CSS pixels (what engine.js's view2d does in device pixels).
  function view(c) {
    const w = c.el.clientWidth || innerWidth;
    const h = c.el.clientHeight || innerHeight;
    let k = c.zoom || 1;
    let ox = 0;
    let oy = 0;
    if (c.fit) {
      const f = Math.min(w / c.fit[0], h / c.fit[1]);
      k = f * (c.zoom || 1);
      ox = (w - c.fit[0] * f) / 2;
      oy = (h - c.fit[1] * f) / 2;
    }
    const r = c.el.getBoundingClientRect();
    return { k, ox: r.left + ox - c.cx * k, oy: r.top + oy - c.cy * k };
  }

  let measurer = null;
  function textWidth(p) {
    measurer = measurer || document.createElement('canvas').getContext('2d');
    measurer.font = `${p.bold ? 'bold ' : ''}${p.size}px ${p.font}`;
    return measurer.measureText(String(p.text ?? '')).width;
  }

  // A shape's own box (before rotation and scale, with its anchor applied): [x0, y0, x1, y1].
  function localBox(n) {
    const p = n.p;
    if (n.type === 'line' || n.type === 'poly') {
      const pts = p.points && p.points.length ? p.points : [[0, 0]];
      const xs = pts.map((q) => q[0]);
      const ys = pts.map((q) => q[1]);
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    }
    let w;
    let h;
    if (n.type === 'circle') w = h = Math.max(0, p.r) * 2;
    else if (n.type === 'text') { w = textWidth(p); h = p.size; }
    else if (n.type === 'image') { w = p.w ?? 64; h = p.h ?? 64; }
    else { w = p.w || 0; h = p.h || 0; }
    return [-p.ax * w, -p.ay * h, -p.ax * w + w, -p.ay * h + h];
  }

  function toWorld(p, lx, ly) {
    const a = (p.rot || 0) * DEG;
    const sx = (p.sx ?? 1) * (p.scale ?? 1);
    const sy = (p.sy ?? 1) * (p.scale ?? 1);
    return [p.x + Math.cos(a) * sx * lx - Math.sin(a) * sy * ly, p.y + Math.sin(a) * sx * lx + Math.cos(a) * sy * ly];
  }

  // A shape's box on screen (CSS pixels), rotation included: { l, t, r, b }.
  function screenBox(id) {
    const n = objs().get(id);
    if (!n || n.kind !== 'shape' || !n.host) return null;
    const v = view(n.host);
    const [x0, y0, x1, y1] = localBox(n);
    const pts = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => toWorld(n.p, x, y)).map(([x, y]) => [x * v.k + v.ox, y * v.k + v.oy]);
    const pad = n.type === 'line' ? (n.p.lw || 1) * v.k / 2 : 0;
    return { l: Math.min(...pts.map((q) => q[0])) - pad, t: Math.min(...pts.map((q) => q[1])) - pad,
      r: Math.max(...pts.map((q) => q[0])) + pad, b: Math.max(...pts.map((q) => q[1])) + pad };
  }

  function distToSegment(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const len = dx * dx + dy * dy;
    const t = len ? clamp(((px - ax) * dx + (py - ay) * dy) / len, 0, 1) : 0;
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }

  // Is the point (CSS pixels) on this shape? Worked out in the shape's own space, like engine.js's pick2d.
  function hit2d(n, px, py) {
    const p = n.p;
    const v = view(n.host);
    const wx = (px - v.ox) / v.k;
    const wy = (py - v.oy) / v.k;
    const a = -(p.rot || 0) * DEG;
    const sx = (p.sx ?? 1) * (p.scale ?? 1) || 1;
    const sy = (p.sy ?? 1) * (p.scale ?? 1) || 1;
    const dx = wx - p.x;
    const dy = wy - p.y;
    const lx = (dx * Math.cos(a) - dy * Math.sin(a)) / sx;
    const ly = (dx * Math.sin(a) + dy * Math.cos(a)) / sy;
    const tol = 3 / v.k / Math.min(Math.abs(sx), Math.abs(sy));    // 3 px of slack, so small things can be grabbed
    if (n.type === 'line' || n.type === 'poly') {
      const pts = p.points || [];
      const near = Math.max(6, (p.lw || 1) / 2 + tol);
      for (let j = 1; j < pts.length; j++) if (distToSegment(lx, ly, pts[j - 1][0], pts[j - 1][1], pts[j][0], pts[j][1]) <= near) return true;
      return false;
    }
    const [x0, y0, x1, y1] = localBox(n);
    if (n.type === 'circle') return Math.hypot(lx - (x0 + x1) / 2, ly - (y0 + y1) / 2) <= Math.max(0, p.r) + tol;
    return lx >= x0 - tol && lx <= x1 + tol && ly >= y0 - tol && ly <= y1 + tol;
  }

  // The topmost thing under the point: the HUD first, then the game, highest layer (z) first, then the one drawn last.
  function pick2d(px, py) {
    const cands = [];
    for (const [id, i] of L.idToThing) {
      const n = objs().get(id);
      if (!n || n.kind !== 'shape' || n.p.visible === false || n.dead) continue;
      cands.push({ id, i, n, hud: n.host && n.host.id === L.hudCanvas });
    }
    cands.sort((a, b) => (b.hud - a.hud) || (b.n.p.z - a.n.p.z) || (b.id - a.id));
    for (const c of cands) if (hit2d(c.n, px, py)) return { i: c.i, id: c.id, n: c.n };
    return { i: null };
  }

  // ---------------------------------------------------------------- selection

  function select(is) {
    selIs = is.filter((i) => i === 'player' || L?.meta.has(i));
    drawSel();
  }

  // 2D shapes (a 2D game's things, and the HUD in either) get #sel2d around all of them; 3D things a wire box each.
  function drawSel() {
    const box = sel2d();
    if (!L) { if (box) box.hidden = true; return; }
    let u = null;
    for (const i of selIs) {
      const t = L.meta.get(i);
      for (const id of (t ? t.ids : [])) {
        const b = screenBox(id);
        if (!b) continue;
        u = u ? { l: Math.min(u.l, b.l), t: Math.min(u.t, b.t), r: Math.max(u.r, b.r), b: Math.max(u.b, b.b) } : b;
      }
    }
    if (box) {
      box.hidden = !u;
      if (u) {
        const pad = 3;
        Object.assign(box.style, { left: `${u.l - pad - 2}px`, top: `${u.t - pad - 2}px`, width: `${u.r - u.l + pad * 2}px`, height: `${u.b - u.t + pad * 2}px` });
      }
    }
    if (L.mode !== '3d') return;
    const cmds = outlineIds.map((id) => ['r', id]);
    outlineIds = [];
    for (const i of selIs) {
      let parentId;
      let d;
      if (i === 'player') {
        if (!L.player) continue;
        parentId = L.B + MARKER;
        d = [0.6, 1.7, 0.6];
      } else {
        const t = L.meta.get(i);
        if (!t || !t.dims || !t.ids.length || objs().get(t.ids[0])?.kind !== 'obj') continue;
        parentId = t.ids[0];
        d = t.dims;
      }
      if (!objs().get(parentId)) continue;
      const [w, h, dd] = d.map((v) => Math.max(0.05, +v || 0) * 1.03 + 0.02);
      const id = L.B + OUTLINES + outlineNo++;
      cmds.push(['c', id, 'obj', 'box', parentId, { w, h, d: dd, y: h / 2 - 0.01, wireframe: true, mat: 'basic', color: SEL, pick: false, shadow: false }]);
      outlineIds.push(id);
    }
    send(cmds);
  }

  addEventListener('resize', () => {
    if (L && selIs.some((i) => L.meta.get(i)?.layer !== 'world')) requestAnimationFrame(drawSel);
  });

  // ---------------------------------------------------------------- the pointer

  const mods = (e) => ({ ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey, meta: e.metaKey });
  const snap = (v, alt) => { const s = alt ? 0.1 : 0.5; const r = Math.round(v / s) * s; return +r.toFixed(2) || 0; };

  function capture(e) {
    try { (e.target && e.target.setPointerCapture ? e.target : document.documentElement).setPointerCapture(e.pointerId); } catch { /* not ours */ }
  }

  addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault(); });   // no middle-button autoscroll

  const BUTTON_BIT = [1, 4, 2];   // e.button -> its bit in e.buttons
  addEventListener('pointerdown', (e) => {
    if (!L) return;
    if (press && e.buttons & (BUTTON_BIT[press.button] ?? 0)) return;   // another button while one is held: ignored
    press = null;                                                        // (a release this page never saw)
    try {
      onDown(e);
      if (press) press.button = e.button;
    } catch (err) { press = null; post('error', { message: String(err.message || err), where: 'picking' }); loadHeld(); }
  });

  function onDown(e) {
    const x = e.clientX;
    const y = e.clientY;
    if (L.mode === '3d' && camMode === 'game') return;            // the game's camera is for looking only
    // 2D shapes first: a 2D game's things, or the HUD over a 3D world.
    const flat = e.button === 0 && !(L.mode === '3d' && e.shiftKey) ? pick2d(x, y) : { i: null };
    if (flat.i !== null) {
      post('pick', { i: flat.i });
      const t = L.meta.get(flat.i);
      if (t && t.drag) {
        const v = view(flat.n.host);
        press = { kind: 'drag2d', i: flat.i, x0: x, y0: y, k: v.k, dx: 0, dy: 0,
          starts: t.ids.map((id) => { const n = objs().get(id); return n && n.kind === 'shape' ? [id, n.p.x, n.p.y] : null; }).filter(Boolean) };
      } else press = { kind: 'none', x0: x, y0: y };
      capture(e);
      return;
    }
    if (L.mode !== '3d') {
      if (e.button === 0) { press = { kind: 'empty', x0: x, y0: y }; capture(e); }
      return;
    }
    if (!three()) return;
    if (e.button === 1 || (e.button === 0 && e.shiftKey)) { press = { kind: 'pan', x0: x, y0: y, lx: x, ly: y }; capture(e); return; }
    if (e.button === 2) { press = { kind: 'orbit', x0: x, y0: y, lx: x, ly: y }; capture(e); return; }
    if (e.button !== 0) return;
    const hit = pick3d(x, y);
    if (hit.i === null) { press = { kind: 'orbit', empty: true, x0: x, y0: y, lx: x, ly: y }; capture(e); return; }
    post('pick', { i: hit.i, point: hit.point });
    const drag = hit.i === 'player' ? L.player && L.player.drag : L.meta.get(hit.i)?.drag;
    const gid = groupOf(hit.i);
    const g = gid ? objs().get(gid) : null;
    if (drag && g) {
      const pos = g.obj.position;
      const at = onPlane(x, y, pos.y);
      press = { kind: 'drag3d', i: hit.i, gid, x0: x, y0: y, sx: pos.x, sz: pos.z, y: pos.y,
        offx: at ? pos.x - at.x : 0, offz: at ? pos.z - at.z : 0, x: pos.x, z: pos.z };
    } else press = { kind: 'orbit', x0: x, y0: y, lx: x, ly: y };
    capture(e);
  }

  addEventListener('pointermove', (e) => {
    if (!press || !L) return;
    const x = e.clientX;
    const y = e.clientY;
    if (!press.started) {
      if (Math.hypot(x - press.x0, y - press.y0) < 4) return;
      press.started = true;   // (orbit and pan count from where the pointer went down)
    }
    try { onMove(e, x, y); } catch (err) { post('error', { message: String(err.message || err), where: 'dragging' }); }
  });

  function onMove(e, x, y) {
    const p = press;
    if (p.kind === 'drag2d') {
      p.dx = Math.round((x - p.x0) / p.k);
      p.dy = Math.round((y - p.y0) / p.k);
      send(p.starts.map(([id, sx, sy]) => ['s', id, { x: sx + p.dx, y: sy + p.dy }]));
      drawSel();
    } else if (p.kind === 'drag3d') {
      const at = onPlane(x, y, p.y);
      if (!at) return;
      p.x = snap(at.x + p.offx, e.altKey);
      p.z = snap(at.z + p.offz, e.altKey);
      p.alt = e.altKey;
      send([['s', p.gid, { x: p.x, z: p.z }]]);
    } else if (p.kind === 'orbit' && cam) {
      cam.az -= (x - p.lx) * 0.3;
      cam.el = clamp(cam.el + (y - p.ly) * 0.3, 5, 89);
      p.lx = x;
      p.ly = y;
      applyCam();
      postCam();
    } else if (p.kind === 'pan' && cam) {
      const az = cam.az * DEG;
      const s = cam.dist * 0.0015;
      const dx = (x - p.lx) * s;
      const dy = (y - p.ly) * s;
      // Grab the world: it follows the pointer. Right is (cos az, 0, -sin az), forward (to the target) is -(sin az, 0, cos az).
      cam.tx += -Math.cos(az) * dx - Math.sin(az) * dy;
      cam.tz += Math.sin(az) * dx - Math.cos(az) * dy;
      p.lx = x;
      p.ly = y;
      applyCam();
      postCam();
    }
  }

  function finish(e, cancelled) {
    const p = press;
    press = null;
    if (!p || !L) return;
    if (cancelled) {
      if (p.kind === 'drag2d' && p.started) { send(p.starts.map(([id, sx, sy]) => ['s', id, { x: sx, y: sy }])); drawSel(); post('drag', { i: p.i, phase: 'cancel' }); }
      else if (p.kind === 'drag3d' && p.started) { send([['s', p.gid, { x: p.sx, z: p.sz }]]); post('drag', { i: p.i, phase: 'cancel' }); }
      return;
    }
    if (p.kind === 'drag2d' && p.started) post('drag', { i: p.i, phase: 'end', dx: p.dx, dy: p.dy, alt: !!(e && e.altKey) });
    else if (p.kind === 'drag3d' && p.started) post('drag', { i: p.i, phase: 'end', x: p.x, z: p.z, alt: !!(p.alt || (e && e.altKey)) });
    else if ((p.kind === 'empty' || (p.kind === 'orbit' && p.empty)) && !p.started) post('pick', { i: null });
    else if ((p.kind === 'orbit' || p.kind === 'pan') && p.started) postCam(true);
  }

  // (A second button pressed during a drag comes as a pointermove, and pointerup only when all are up.)
  addEventListener('pointerup', (e) => { finish(e, false); post('focus'); loadHeld(); });
  addEventListener('pointercancel', () => { finish(null, true); post('focus'); loadHeld(); });

  addEventListener('dblclick', (e) => {
    if (!L || L.mode !== '3d' || camMode !== 'editor' || !cam) return;
    const hit = pick3d(e.clientX, e.clientY);
    if (hit.i === null) return;
    const gid = groupOf(hit.i);
    const g = gid ? objs().get(gid) : null;
    if (!g) return;
    const t = hit.i === 'player' ? { dims: [0.6, 1.7, 0.6], k: [1, 1, 1] } : L.meta.get(hit.i);
    const d = (t.dims || [1, 1, 1]).map((v, j) => v * ((t.k || [1, 1, 1])[j] || 1));
    const pos = g.obj.position;
    cam = { ...cam, tx: pos.x, ty: pos.y + d[1] / 2, tz: pos.z, dist: clamp(Math.max(...d) * 3, 4, 150) };
    applyCam();
    postCam(true);
  });

  addEventListener('wheel', (e) => {
    if (!L) return;
    if (L.mode === '2d') {
      if (e.ctrlKey) e.preventDefault();
      post('wheel', { dx: e.deltaX, dy: e.deltaY, ...mods(e) });
      return;
    }
    if (camMode !== 'editor' || !cam) return;
    e.preventDefault();
    cam.dist = clamp(cam.dist * 1.0015 ** e.deltaY, 2, 300);
    applyCam();
    postCam();
  }, { passive: false });

  // ---------------------------------------------------------------- keys

  const OURS = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Delete', 'Backspace', ' ', 'F11']);
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && press && press.started && (press.kind === 'drag2d' || press.kind === 'drag3d')) {
      e.preventDefault();
      finish(null, true);
      return;
    }
    if (OURS.has(e.key)) e.preventDefault();
    post('key', { key: e.key, code: e.code, ...mods(e) });
  });

  // ---------------------------------------------------------------- asks (mostly for tests)

  function ask(m) {
    const reply = (value, error = null) => post('reply', { tag: m.tag, value, error });
    if (m.what === 'snapshot') { send([['k', 0, 'snapshot', [], m.tag]]); return; }
    if (m.what === 'fetch') { askFetch(m); return; }
    if (!L) { reply(null, 'nothing is loaded yet'); return; }
    if (m.what === 'screen' || m.what === 'pos') {
      const gid = groupOf(m.i);
      const g = gid && objs().get(gid);
      if (!g) { reply(null, `no thing ${m.i}`); return; }
      if (g.kind === 'shape') {
        if (m.what === 'pos') { reply({ x: g.p.x, y: g.p.y }); return; }
        const b = screenBox(g.id);
        reply([(b.l + b.r) / 2, (b.t + b.b) / 2]);
        return;
      }
      const pos = g.obj.position;
      if (m.what === 'pos') { reply({ x: pos.x, y: pos.y, z: pos.z }); return; }
      const t = m.i === 'player' ? { dims: [0.6, 1.7, 0.6], k: [1, 1, 1] } : L.meta.get(m.i);
      const h = (t.dims ? t.dims[1] : 1) * ((t.k || [1, 1, 1])[1] || 1);
      send([['k', L.sceneId, 'project', [pos.x, pos.y + h / 2, pos.z], m.tag]]);
      return;
    }
    if (m.what === 'stats') {
      let sceneBg = null;
      if (L.mode === '3d') {
        const n = objs().get(L.sceneId);
        sceneBg = n && n.scene && n.scene.background && n.scene.background.getHexString ? `#${n.scene.background.getHexString()}` : null;
      } else {
        const c = objs().get(L.gameCanvas);
        sceneBg = c ? c.bg : null;
      }
      const marker = L.player ? objs().get(L.B + MARKER) : null;
      reply({ objs: objs().size, mode: L.mode, sceneBg, things: L.meta.size, sel: selIs, camMode, cam: cam && L.mode === '3d' ? { ...cam } : null,
        cameraNodesVisible: [...L.cameraNodes].some((id) => objs().get(id)?.obj?.visible), outlines: outlineIds.length,
        marker: marker ? marker.obj.visible : null, load: L.seq, b: L.B, scene: L.sceneId, sel2d: !sel2d()?.hidden });
      return;
    }
    reply(null, `unknown ask '${m.what}'`);
  }

  // 'fetch', url: what this page gets for a tuffview://app/ address (for the tests of what the scheme serves).
  function askFetch(m) {
    const u = new URL(String(m.url || ''), location.href);
    if (u.origin !== location.origin) { post('reply', { tag: m.tag, value: null, error: 'only tuffview://app/ addresses' }); return; }
    fetch(u.href).then(async (r) => post('reply', { tag: m.tag, value: { status: r.status, type: r.headers.get('content-type'), size: (await r.arrayBuffer()).byteLength }, error: null }),
      (err) => post('reply', { tag: m.tag, value: null, error: String(err && err.message || err) }));
  }
})();
