// Sprite Studio: a pixel-art editor in the right sidebar. Draw sprites and icons, animate them with frames,
// save them as PNG pictures in the project ("files" permission) and get the Tuff code that shows them.
// Everything is plain canvas work: the PNG encoder is below, and opening a project PNG loads it through its
// file:// address, because t.project.read gives text and would spoil a picture's bytes.
TuffPlugins.register('sprite-studio', (t) => {
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  const SIZES = [16, 24, 32, 64];
  const MAX_SIDE = 256;
  const SCALES = [1, 2, 4, 8];
  const PALETTE = ['#1b1b24', '#4a4a5a', '#9a9aa8', '#f2f2ee', '#7a4a32', '#c98a5a', '#f4c9a0', '#d8403c',
    '#f08a3c', '#f7d046', '#8fd14f', '#2f9a54', '#3fb7d9', '#3460c8', '#6b3fa8', '#e070b0'];
  const CHECK = ['#45464c', '#3a3b40']; // the see-through checkerboard
  const CLEAR = [0, 0, 0, 0];

  const ICONS = {
    pencil: '<path d="M11 2.6l2.4 2.4-7.6 7.6-3.1.7.7-3.1z"/><path d="M9.6 4l2.4 2.4"/>',
    eraser: '<path d="M9 2.9a1.3 1.3 0 0 1 1.8 0l2.3 2.3a1.3 1.3 0 0 1 0 1.8l-5.5 5.5H5l-2.1-2.1a1.3 1.3 0 0 1 0-1.8z"/><path d="M5.6 6.3l4.1 4.1M7.6 12.5h5.6"/>',
    fill: '<path d="M6.6 2.6l6 6-4.7 4.7a1.3 1.3 0 0 1-1.8 0L2 9.2a1.3 1.3 0 0 1 0-1.8z"/><path d="M2.3 8.3h10"/><path d="M13.6 10.6c.7.9 1.1 1.6 1.1 2.1a1.1 1.1 0 0 1-2.2 0c0-.5.4-1.2 1.1-2.1z"/>',
    picker: '<path d="M8.8 3.4l3.8 3.8"/><path d="M11.4 4.6l1.7-1.7a1.3 1.3 0 0 0-1.9-1.9L9.5 2.7"/><path d="M10 4.6l-6 6-.8 2.2 2.2-.8 6-6"/>',
    line: '<path d="M4.6 11.4l6.8-6.8"/><rect x="1.8" y="10.8" width="3.4" height="3.4" rx=".6"/><rect x="10.8" y="1.8" width="3.4" height="3.4" rx=".6"/>',
    rect: '<rect x="2.5" y="3.5" width="11" height="9" rx="1.2"/>',
    fillrect: '<rect x="2.5" y="3.5" width="11" height="9" rx="1.2" fill="currentColor"/>',
    mirror: '<path d="M8 1.8v12.4" stroke-dasharray="1.6 1.8"/><path d="M5.6 4.6v6.8L2.2 8z"/><path d="M10.4 4.6v6.8L13.8 8z"/>',
    undo: '<path d="M5.5 3.5L2.5 6.5l3 3"/><path d="M2.5 6.5h6.8a3.7 3.7 0 0 1 0 7.4H7"/>',
    redo: '<path d="M10.5 3.5l3 3-3 3"/><path d="M13.5 6.5H6.7a3.7 3.7 0 0 0 0 7.4H9"/>',
    page: '<path d="M9 2H4.5A1.5 1.5 0 0 0 3 3.5v9A1.5 1.5 0 0 0 4.5 14h7a1.5 1.5 0 0 0 1.5-1.5V6z"/><path d="M9 2v4h4"/>',
    folder: '<path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h2.8l1.5 1.5h4.7A1.5 1.5 0 0 1 14 6v5.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 11.5z"/>',
    plus: '<path d="M8 3v10M3 8h10"/>',
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 5.5V4A1.5 1.5 0 0 0 9 2.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1.5"/>',
    trash: '<path d="M2.5 4.5h11M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5M4 4.5l.7 8.6a1 1 0 0 0 1 .9h4.6a1 1 0 0 0 1-.9l.7-8.6"/>',
    left: '<path d="M10 3.5L5.5 8l4.5 4.5"/>',
    right: '<path d="M6 3.5L10.5 8 6 12.5"/>',
    play: '<path d="M5 3.2v9.6L12.5 8z"/>',
    pause: '<path d="M5.5 3.5v9M10.5 3.5v9"/>',
  };
  const icon = (n) => `<svg viewBox="0 0 16 16" aria-hidden="true">${ICONS[n]}</svg>`;

  const TOOLS = [
    { id: 'pencil', name: 'Pencil', key: 'P', hint: 'Click and drag to draw. Right-click rubs out.' },
    { id: 'eraser', name: 'Eraser', key: 'E', hint: 'Click and drag to rub pixels out.' },
    { id: 'fill', name: 'Fill', key: 'F', hint: 'Click to fill an area that is all one colour.' },
    { id: 'picker', name: 'Eyedropper', key: 'I', hint: 'Click a pixel to use its colour.' },
    { id: 'line', name: 'Line', key: 'L', hint: 'Drag from one end of the line to the other.' },
    { id: 'rect', name: 'Rectangle', key: 'R', hint: 'Drag from one corner to the other.' },
    { id: 'fillrect', name: 'Filled rectangle', key: 'B', hint: 'Drag from one corner to the other.' },
  ];
  const DRAWING = new Set(['pencil', 'fill', 'line', 'rect', 'fillrect']);

  // Tuff's keywords and built-ins, and library names: a sprite's variable can't be one of these.
  const RESERVED = new Set(('func return if elif else then while for in break continue and or not is true false nil say input flush import mention ' +
    'print text str number num int len round random wait range clear sqrt abs floor ceil min max sum average pi err all ' +
    'game app tgame mtgui tgui atgui tap anims').split(' '));

  // ---------------------------------------------------------------- state
  const blank = (w, h) => new Uint8ClampedArray(w * h * 4);
  const doc = { w: 16, h: 16, frames: [blank(16, 16)], cur: 0 };
  let fps = clamp(Number(t.storage.get('fps', 8)) || 8, 1, 30);
  let tool = 'pencil';
  let lastDraw = 'pencil';
  let mirror = false;
  let color = PALETTE[7];
  let recent = (t.storage.get('recent', []) || []).filter((c) => /^#[0-9a-f]{6}$/.test(c)).slice(0, 8);
  let grid = t.storage.get('grid', true) !== false;
  let onion = !!t.storage.get('onion', false);
  let scale = SCALES.includes(t.storage.get('scale', 1)) ? t.storage.get('scale', 1) : 1;
  let sheet = !!t.storage.get('sheet', false);
  let lib = ['tgame', 'mtgui', 'atgui'].includes(t.storage.get('lib')) ? t.storage.get('lib') : 'tgame';
  const undos = [];
  const redos = [];
  let editRedo = null; // the redo list while an edit is going on, given back if the edit changed nothing
  let mine = new Set(); // project paths (lower case) this sprite came from or went to: saving there again doesn't ask
  let made = new Set(); // .tuf files "Try in a new file" made
  let saved = null; // what the last save wrote, for "Use in code"
  let stroke = null; // the drag going on now
  let hover = null;
  let playing = true;
  let pv = 0; // the preview's frame
  let timer = null;
  let raf = 0;
  let K = 1; // device pixels per sprite pixel on the big canvas
  let laid = { w: 0, h: 0 }; // the sprite size the big canvas was laid out for
  let root = null;
  let view = null;
  let menuFiles = [];
  let ro = null;
  const bufA = document.createElement('canvas');
  const bufB = document.createElement('canvas');
  let checker = null;

  const frame = () => doc.frames[doc.cur];
  const $ = (s) => root.querySelector(s);
  const $$ = (s) => [...root.querySelectorAll(s)];

  // ---------------------------------------------------------------- colours
  const hexOk = (s) => {
    const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(s || '').trim());
    if (!m) return null;
    const h = m[1].length === 3 ? m[1].split('').map((c) => c + c).join('') : m[1];
    return '#' + h.toLowerCase();
  };
  const rgba = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16), 255];
  const toHex = (r, g, b) => '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');

  function setColor(hex, fromPicker) {
    color = hex;
    if (!fromPicker) $('[data-f="picker"]').value = hex;
    $('[data-f="hex"]').value = hex;
    $$('[data-color]').forEach((b) => b.classList.toggle('on', b.dataset.color === hex));
    if (tool === 'eraser' || tool === 'picker') setTool(lastDraw);
  }

  function addRecent(hex) {
    if (recent[0] === hex) return;
    recent = [hex, ...recent.filter((c) => c !== hex)].slice(0, 8);
    t.storage.set('recent', recent);
    renderRecent();
  }

  function renderRecent() {
    const box = $('.ss-recent');
    box.innerHTML = recent.length
      ? recent.map((c) => `<button data-color="${c}" title="${c}" style="--c:${c}"${c === color ? ' class="on"' : ''}></button>`).join('')
      : '<span class="ss-muted">Colours you use show up here.</span>';
  }

  // ---------------------------------------------------------------- undo
  const snapshot = () => ({ w: doc.w, h: doc.h, cur: doc.cur, frames: doc.frames.map((f) => f.slice()) });
  const same = (a, b) => { if (a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false; return true; };
  const sameDoc = (s) => s.w === doc.w && s.h === doc.h && s.frames.length === doc.frames.length && s.frames.every((f, i) => same(f, doc.frames[i]));

  function begin() {
    undos.push(snapshot());
    editRedo = redos.splice(0);
    // keep roughly 48 MB of history at most
    let bytes = undos.reduce((n, s) => n + s.frames.length * s.w * s.h * 4, 0);
    while (undos.length > 1 && (undos.length > 200 || bytes > 48e6)) { const s = undos.shift(); bytes -= s.frames.length * s.w * s.h * 4; }
  }

  function finish(usedColor) {
    const top = undos[undos.length - 1];
    if (top && sameDoc(top)) { undos.pop(); if (editRedo) redos.push(...editRedo); }
    else if (usedColor) addRecent(color);
    editRedo = null;
    changed();
  }

  function restore(s) {
    doc.w = s.w; doc.h = s.h; doc.cur = Math.min(s.cur, s.frames.length - 1);
    doc.frames = s.frames.map((f) => f.slice());
  }

  function undo() {
    if (stroke) return;
    if (!undos.length) return t.toast('Nothing to undo.', 'info', 1400);
    redos.push(snapshot());
    restore(undos.pop());
    changed();
  }

  function redo() {
    if (stroke) return;
    if (!redos.length) return t.toast('Nothing to redo.', 'info', 1400);
    undos.push(snapshot());
    restore(redos.pop());
    changed();
  }

  // ---------------------------------------------------------------- drawing
  const at = (x, y) => (y * doc.w + x) * 4;
  function put(d, x, y, c) {
    if (x < 0 || y < 0 || x >= doc.w || y >= doc.h) return;
    const i = at(x, y);
    d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = c[3];
  }
  function plot(x, y, c) {
    const d = frame();
    put(d, x, y, c);
    if (mirror) put(d, doc.w - 1 - x, y, c);
  }

  function lineCells(a, b) {
    const out = [];
    let x0 = a.x, y0 = a.y;
    const dx = Math.abs(b.x - x0), dy = -Math.abs(b.y - y0), sx = x0 < b.x ? 1 : -1, sy = y0 < b.y ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      out.push([x0, y0]);
      if (x0 === b.x && y0 === b.y) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
    return out;
  }

  function shapeCells(kind, a, b) {
    if (kind === 'line') return lineCells(a, b);
    const out = [];
    const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x), y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (kind === 'fillrect' || x === x0 || x === x1 || y === y0 || y === y1) out.push([x, y]);
    return out;
  }

  // Fill the area of one colour around (x, y): its neighbours up, down, left and right with exactly that colour.
  function fill(x, y, c) {
    const d = frame(), w = doc.w, h = doc.h;
    const i0 = at(x, y);
    const target = [d[i0], d[i0 + 1], d[i0 + 2], d[i0 + 3]];
    const match = (i) => (target[3] === 0 ? d[i + 3] === 0 : d[i] === target[0] && d[i + 1] === target[1] && d[i + 2] === target[2] && d[i + 3] === target[3]);
    const already = target[3] === 0 ? c[3] === 0 : c[0] === target[0] && c[1] === target[1] && c[2] === target[2] && c[3] === target[3];
    if (already) return;
    const stack = [x, y];
    while (stack.length) {
      const py = stack.pop(), px = stack.pop();
      if (px < 0 || py < 0 || px >= w || py >= h) continue;
      const i = at(px, py);
      if (!match(i)) continue;
      d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = c[3];
      stack.push(px + 1, py, px - 1, py, px, py + 1, px, py - 1);
    }
  }

  // The sprite pixel under the mouse. raw: even outside the canvas (a pencil line can run off the edge).
  function cellAt(e, mode) {
    const r = view.getBoundingClientRect();
    let x = Math.floor(((e.clientX - r.left) / r.width) * doc.w);
    let y = Math.floor(((e.clientY - r.top) / r.height) * doc.h);
    if (mode === 'raw') return { x, y };
    if (mode === 'clamp') { x = clamp(x, 0, doc.w - 1); y = clamp(y, 0, doc.h - 1); }
    return x >= 0 && y >= 0 && x < doc.w && y < doc.h ? { x, y } : null;
  }

  function onDown(e) {
    if (e.button !== 0 && e.button !== 2) return;
    e.preventDefault();
    root.focus({ preventScroll: true });
    closeMenu();
    const p = cellAt(e);
    if (!p || stroke) return;
    try { view.setPointerCapture(e.pointerId); } catch {}
    const erase = e.button === 2 || tool === 'eraser';
    const c = erase ? CLEAR : rgba(color);
    if (tool === 'picker' && e.button === 0) { pick(p); return; }
    if (tool === 'fill') {
      begin();
      fill(p.x, p.y, c);
      if (mirror) fill(doc.w - 1 - p.x, p.y, c);
      finish(!erase);
      return;
    }
    if (tool === 'pencil' || tool === 'eraser' || tool === 'picker') {
      begin();
      stroke = { kind: 'free', c, erase, last: p };
      plot(p.x, p.y, c);
    } else {
      stroke = { kind: tool, c, erase, from: p, cells: shapeCells(tool, p, p) };
    }
    hover = p;
    schedule();
  }

  function onMove(e) {
    hover = cellAt(e);
    if (stroke?.kind === 'free') {
      const p = cellAt(e, 'raw');
      for (const [x, y] of lineCells(stroke.last, p)) plot(x, y, stroke.c);
      stroke.last = p;
    } else if (stroke) {
      stroke.cells = shapeCells(stroke.kind, stroke.from, cellAt(e, 'clamp'));
    }
    showPos();
    schedule();
  }

  function onUp() {
    if (!stroke) return;
    const s = stroke;
    stroke = null;
    if (s.kind !== 'free') {
      begin();
      for (const [x, y] of s.cells) plot(x, y, s.c);
    }
    finish(!s.erase);
  }

  function cancelStroke() {
    if (!stroke) return;
    const s = stroke;
    stroke = null;
    if (s.kind === 'free') { restore(undos.pop()); redos.push(...(editRedo || [])); editRedo = null; }
    changed();
  }

  function pick(p) {
    const d = frame(), i = at(p.x, p.y);
    if (d[i + 3] === 0) { setTool('eraser'); t.toast('That pixel is see-through, so you have the eraser now.', 'info', 2200); return; }
    setColor(toHex(d[i], d[i + 1], d[i + 2]));
    setTool(lastDraw);
  }

  function setTool(id) {
    tool = id;
    if (DRAWING.has(id)) lastDraw = id;
    $$('[data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === id));
    const tl = TOOLS.find((x) => x.id === id);
    $('.ss-hint').innerHTML = `<b>${esc(tl.name)}</b> ${esc(tl.hint)}${mirror ? ' <span class="ss-muted">Mirror is on.</span>' : ''}`;
  }

  function setMirror(on) {
    mirror = on;
    $('[data-a="mirror"]').classList.toggle('on', on);
    setTool(tool);
    schedule();
  }

  // ---------------------------------------------------------------- the big canvas
  function paintBuf(buf, data, w = doc.w, h = doc.h) {
    if (buf.width !== w) buf.width = w;
    if (buf.height !== h) buf.height = h;
    buf.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(data), w, h), 0, 0);
    return buf;
  }

  function makeChecker() {
    const c = K >= 16 ? 2 : 1; // checks per pixel
    checker = document.createElement('canvas');
    checker.width = doc.w * c;
    checker.height = doc.h * c;
    const img = new ImageData(checker.width, checker.height);
    const cols = CHECK.map((h) => rgba(h));
    for (let y = 0; y < checker.height; y++) for (let x = 0; x < checker.width; x++) img.data.set(cols[(x + y) % 2], (y * checker.width + x) * 4);
    checker.getContext('2d').putImageData(img, 0, 0);
  }

  function layout() {
    if (!root || !view || !root.clientWidth) return;
    const stage = $('.ss-stage');
    const avail = Math.max(48, stage.clientWidth);
    const maxH = Math.max(160, Math.min(avail, root.clientHeight * 0.55));
    const dpr = window.devicePixelRatio || 1;
    const k = Math.max(1, Math.floor(Math.min(avail / doc.w, maxH / doc.h) * dpr));
    if (k !== K || laid.w !== doc.w || laid.h !== doc.h || !checker) {
      K = k;
      laid = { w: doc.w, h: doc.h };
      view.width = doc.w * k;
      view.height = doc.h * k;
      view.style.width = `${view.width / dpr}px`;
      view.style.height = `${view.height / dpr}px`;
      view.dataset.w = doc.w;
      view.dataset.h = doc.h;
      view.setAttribute('aria-label', `Drawing area, ${doc.w} by ${doc.h} pixels`);
      makeChecker();
    }
    render();
  }

  function schedule() {
    if (raf) return;
    raf = requestAnimationFrame(() => { raf = 0; render(); paintThumb(doc.cur); if (!playing || doc.frames.length === 1) drawPreview(); });
  }

  function render() {
    if (!view || !checker) return;
    const g = view.getContext('2d');
    const W = view.width, H = view.height, k = K;
    g.imageSmoothingEnabled = false;
    g.globalAlpha = 1;
    g.drawImage(checker, 0, 0, W, H);
    if (onion && doc.cur > 0) {
      g.globalAlpha = 0.3;
      g.drawImage(paintBuf(bufB, doc.frames[doc.cur - 1]), 0, 0, W, H);
      g.globalAlpha = 1;
    }
    g.drawImage(paintBuf(bufA, frame()), 0, 0, W, H);
    if (stroke && stroke.kind !== 'free') {
      g.fillStyle = stroke.erase ? 'rgba(30, 31, 34, .7)' : color;
      for (const [x, y] of stroke.cells) {
        g.fillRect(x * k, y * k, k, k);
        if (mirror) g.fillRect((doc.w - 1 - x) * k, y * k, k, k);
      }
    }
    if (grid && k >= 5) {
      for (let x = 1; x < doc.w; x++) { g.fillStyle = x % 8 ? 'rgba(255,255,255,.07)' : 'rgba(255,255,255,.17)'; g.fillRect(x * k, 0, 1, H); }
      for (let y = 1; y < doc.h; y++) { g.fillStyle = y % 8 ? 'rgba(255,255,255,.07)' : 'rgba(255,255,255,.17)'; g.fillRect(0, y * k, W, 1); }
    }
    if (mirror) {
      g.fillStyle = getComputedStyle(root).getPropertyValue('--accent').trim() || '#3574f0';
      g.globalAlpha = 0.8;
      g.fillRect(Math.round((doc.w / 2) * k) - 1, 0, 2, H);
      g.globalAlpha = 1;
    }
    if (hover && !stroke) {
      g.strokeStyle = 'rgba(255,255,255,.75)';
      g.lineWidth = Math.max(1, Math.round(k / 12));
      const box = (x) => g.strokeRect(x * k + g.lineWidth / 2, hover.y * k + g.lineWidth / 2, k - g.lineWidth, k - g.lineWidth);
      box(hover.x);
      if (mirror && doc.w - 1 - hover.x !== hover.x) box(doc.w - 1 - hover.x);
    }
  }

  function showPos() {
    $('.ss-pos').textContent = hover ? `x ${hover.x}, y ${hover.y}` : `${doc.w} x ${doc.h}`;
  }

  // Something about the sprite changed: redraw everything that shows it.
  function changed() {
    if (laid.w !== doc.w || laid.h !== doc.h) layout(); else render();
    hover = null;
    showPos();
    syncSize();
    renderFrames();
    drawPreview();
    whereText();
    $('[data-a="undo"]').disabled = !undos.length;
    $('[data-a="redo"]').disabled = !redos.length;
  }

  // ---------------------------------------------------------------- size
  function syncSize() {
    const preset = doc.w === doc.h && SIZES.includes(doc.w);
    const customOpen = !$('.ss-custom').classList.contains('hidden');
    $$('[data-size]').forEach((b) => b.classList.toggle('on', b.dataset.size === 'custom' ? !preset || customOpen : !customOpen && +b.dataset.size === doc.w && preset));
  }

  function resizeTo(nw, nh) {
    nw = clamp(Math.round(nw) || 1, 1, MAX_SIDE);
    nh = clamp(Math.round(nh) || 1, 1, MAX_SIDE);
    if (nw === doc.w && nh === doc.h) return;
    // the drawing stays in the middle: bigger adds see-through space around it, smaller trims the edges
    const dx = Math.floor((nw - doc.w) / 2), dy = Math.floor((nh - doc.h) / 2);
    begin();
    doc.frames = doc.frames.map((f) => {
      const out = blank(nw, nh);
      for (let y = 0; y < doc.h; y++) {
        const ty = y + dy;
        if (ty < 0 || ty >= nh) continue;
        for (let x = 0; x < doc.w; x++) {
          const tx = x + dx;
          if (tx < 0 || tx >= nw) continue;
          const s = (y * doc.w + x) * 4, d = (ty * nw + tx) * 4;
          out[d] = f[s]; out[d + 1] = f[s + 1]; out[d + 2] = f[s + 2]; out[d + 3] = f[s + 3];
        }
      }
      return out;
    });
    doc.w = nw;
    doc.h = nh;
    finish(false);
  }

  function newSprite() {
    begin();
    doc.frames = [blank(doc.w, doc.h)];
    doc.cur = 0;
    finish(false);
    $('[data-f="name"]').value = 'sprite';
    mine = new Set();
    saved = null;
    renderCode();
  }

  // ---------------------------------------------------------------- frames and the preview
  function renderFrames() {
    const box = $('.ss-frames');
    const n = doc.frames.length;
    const big = Math.max(doc.w, doc.h);
    const cw = Math.max(4, Math.round((36 * doc.w) / big)), ch = Math.max(4, Math.round((36 * doc.h) / big));
    box.innerHTML = doc.frames.map((_, i) => `<button class="ss-frame${i === doc.cur ? ' on' : ''}" data-frame="${i}" title="Frame ${i + 1}"><canvas width="${doc.w}" height="${doc.h}" style="width:${cw}px;height:${ch}px"></canvas><span>${i + 1}</span></button>`).join('');
    doc.frames.forEach((_, i) => paintThumb(i));
    const on = box.querySelector('.ss-frame.on');
    if (on && (on.offsetLeft < box.scrollLeft || on.offsetLeft + on.offsetWidth > box.scrollLeft + box.clientWidth)) box.scrollLeft = on.offsetLeft - 4;
    $('.ss-count').textContent = n === 1 ? '1 frame' : `${n} frames`;
    $('[data-a="del"]').disabled = n === 1;
    $('[data-a="left"]').disabled = doc.cur === 0;
    $('[data-a="right"]').disabled = doc.cur === n - 1;
    const sh = $('[data-f="sheet"]');
    sh.disabled = n === 1;
    sh.closest('label').classList.toggle('off', n === 1);
    $('.ss-anim').classList.toggle('one', n === 1);
    if (pv >= n) pv = 0;
    restartPreview();
  }

  function paintThumb(i) {
    const c = root.querySelector(`.ss-frame[data-frame="${i}"] canvas`);
    if (c && doc.frames[i]) paintBuf(c, doc.frames[i]);
  }

  function frameOp(kind) {
    const n = doc.frames.length;
    begin();
    if (kind === 'add') { doc.frames.splice(doc.cur + 1, 0, blank(doc.w, doc.h)); doc.cur++; }
    if (kind === 'dup') { doc.frames.splice(doc.cur + 1, 0, frame().slice()); doc.cur++; }
    if (kind === 'del' && n > 1) { doc.frames.splice(doc.cur, 1); doc.cur = Math.min(doc.cur, doc.frames.length - 1); }
    if ((kind === 'left' && doc.cur > 0) || (kind === 'right' && doc.cur < n - 1)) {
      const j = doc.cur + (kind === 'left' ? -1 : 1);
      [doc.frames[doc.cur], doc.frames[j]] = [doc.frames[j], doc.frames[doc.cur]];
      doc.cur = j;
    }
    finish(false);
  }

  function selectFrame(i) {
    if (i === doc.cur || !doc.frames[i]) return;
    doc.cur = i;
    $$('.ss-frame').forEach((b) => b.classList.toggle('on', +b.dataset.frame === i));
    $('[data-a="left"]').disabled = doc.cur === 0;
    $('[data-a="right"]').disabled = doc.cur === doc.frames.length - 1;
    render();
    drawPreview();
  }

  function drawPreview() {
    const c = root?.querySelector('.ss-preview canvas');
    if (!c) return;
    const i = doc.frames.length > 1 && playing ? pv % doc.frames.length : doc.cur;
    paintBuf(c, doc.frames[i]);
    const s = Math.max(doc.w, doc.h);
    const fit = s <= 64 ? Math.floor(64 / s) * s : 64;
    c.style.width = `${Math.round((fit * doc.w) / s)}px`;
    c.style.height = `${Math.round((fit * doc.h) / s)}px`;
  }

  function restartPreview() {
    clearInterval(timer);
    timer = null;
    const shown = root && !root.closest('.hidden');
    if (shown && playing && doc.frames.length > 1) {
      timer = setInterval(() => { pv = (pv + 1) % doc.frames.length; drawPreview(); }, 1000 / fps);
    }
    drawPreview();
  }

  function setPlaying(on) {
    playing = on;
    const b = $('[data-a="play"]');
    b.innerHTML = on ? `${icon('pause')}Pause` : `${icon('play')}Play`;
    restartPreview();
  }

  // ---------------------------------------------------------------- PNG files
  const CRC = (() => {
    const tbl = new Uint32Array(256);
    for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; tbl[n] = c >>> 0; }
    return tbl;
  })();
  const crc32 = (bytes) => { let c = 0xffffffff; for (let i = 0; i < bytes.length; i++) c = CRC[(c ^ bytes[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };

  async function zlib(bytes) {
    if (typeof CompressionStream === 'function') {
      const s = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate'));
      return new Uint8Array(await new Response(s).arrayBuffer());
    }
    // no CompressionStream: zlib with stored (uncompressed) blocks, still a valid PNG
    const blocks = Math.max(1, Math.ceil(bytes.length / 65535));
    const out = new Uint8Array(2 + bytes.length + blocks * 5 + 4);
    out[0] = 0x78; out[1] = 0x01;
    let o = 2;
    for (let b = 0; b < blocks; b++) {
      const part = bytes.subarray(b * 65535, (b + 1) * 65535);
      out[o++] = b === blocks - 1 ? 1 : 0;
      out[o++] = part.length & 255; out[o++] = part.length >> 8;
      out[o++] = ~part.length & 255; out[o++] = (~part.length >> 8) & 255;
      out.set(part, o);
      o += part.length;
    }
    let a = 1, b2 = 0;
    for (let i = 0; i < bytes.length; i++) { a = (a + bytes[i]) % 65521; b2 = (b2 + a) % 65521; }
    new DataView(out.buffer).setUint32(o, ((b2 << 16) | a) >>> 0);
    return out;
  }

  // An RGBA picture as PNG bytes. A "Sprite Studio" text note records the scale, so opening the file again
  // gives back the real pixels to edit.
  async function encodePng(w, h, data, sc) {
    const row = w * 4 + 1;
    const raw = new Uint8Array(row * h);
    for (let y = 0; y < h; y++) {
      raw.set(data.subarray(y * w * 4, (y + 1) * w * 4), y * row + 1);
      for (let x = 0; x < w; x++) { const i = y * row + 1 + x * 4; if (!raw[i + 3]) raw[i] = raw[i + 1] = raw[i + 2] = 0; }
    }
    const enc = new TextEncoder();
    const chunk = (type, body) => {
      const out = new Uint8Array(12 + body.length);
      const dv = new DataView(out.buffer);
      dv.setUint32(0, body.length);
      out.set(enc.encode(type), 4);
      out.set(body, 8);
      dv.setUint32(8 + body.length, crc32(out.subarray(4, 8 + body.length)));
      return out;
    };
    const ihdr = new Uint8Array(13);
    new DataView(ihdr.buffer).setUint32(0, w);
    new DataView(ihdr.buffer).setUint32(4, h);
    ihdr[8] = 8; // bits per channel
    ihdr[9] = 6; // RGBA
    const parts = [new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr),
      chunk('tEXt', enc.encode(`Software\0TuffCode Sprite Studio`)), chunk('tEXt', enc.encode(`Sprite Studio\0scale=${sc}`)),
      chunk('IDAT', await zlib(raw)), chunk('IEND', new Uint8Array(0))];
    const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }

  const base64 = (bytes) => { let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); };

  function upscale(data, w, h, s) {
    if (s === 1) return data;
    const W = w * s, out = new Uint8ClampedArray(W * h * s * 4);
    for (let y = 0; y < h * s; y++) for (let x = 0; x < W; x++) {
      const si = ((Math.floor(y / s) * w) + Math.floor(x / s)) * 4, di = (y * W + x) * 4;
      out[di] = data[si]; out[di + 1] = data[si + 1]; out[di + 2] = data[si + 2]; out[di + 3] = data[si + 3];
    }
    return out;
  }

  // Every frame side by side, left to right.
  function sheetOf(frames) {
    const n = frames.length, W = doc.w * n, out = new Uint8ClampedArray(W * doc.h * 4);
    frames.forEach((f, i) => { for (let y = 0; y < doc.h; y++) out.set(f.subarray(y * doc.w * 4, (y + 1) * doc.w * 4), (y * W + i * doc.w) * 4); });
    return { w: W, h: doc.h, data: out };
  }

  // The "Sprite Studio" note in a PNG's tEXt chunks: the scale it was saved at.
  function noteScale(bytes) {
    if (bytes.length < 8 || bytes[0] !== 137 || bytes[1] !== 80) return 1;
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const dec = new TextDecoder('latin1');
    for (let o = 8; o + 12 <= bytes.length;) {
      const len = dv.getUint32(o), type = dec.decode(bytes.subarray(o + 4, o + 8));
      if (type === 'tEXt') {
        const m = /^Sprite Studio\0scale=(\d+)$/.exec(dec.decode(bytes.subarray(o + 8, o + 8 + len)));
        if (m && SCALES.includes(+m[1])) return +m[1];
      }
      if (type === 'IDAT' || type === 'IEND') break;
      o += 12 + len;
    }
    return 1;
  }

  // file:///C:/My%20Game/sprites/hero.png from C:\My Game\sprites\hero.png (and /Users/... on a Mac).
  const fileUrl = (abs) => {
    let p = String(abs).replace(/\\/g, '/');
    if (!p.startsWith('/')) p = '/' + p;
    return 'file://' + p.split('/').map((s) => (/^[A-Za-z]:$/.test(s) ? s : encodeURIComponent(s))).join('/') + `?v=${Date.now()}`;
  };

  async function loadPng(abs) {
    const url = fileUrl(abs);
    let sc = 1;
    try { sc = noteScale(new Uint8Array(await (await fetch(url)).arrayBuffer())); } catch {}
    const img = await new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = () => rej(new Error('it isn\'t a picture Sprite Studio can read'));
      im.src = url;
    });
    const c = document.createElement('canvas');
    c.width = img.naturalWidth;
    c.height = img.naturalHeight;
    const g = c.getContext('2d', { willReadFrequently: true });
    g.drawImage(img, 0, 0);
    return { w: c.width, h: c.height, data: new Uint8ClampedArray(g.getImageData(0, 0, c.width, c.height).data), scale: sc };
  }

  // A picture saved at 2x, 4x or 8x back at its real pixels, or null if it isn't made of whole blocks.
  function shrink(p, s) {
    if (s === 1) return p;
    if (p.w % s || p.h % s) return null;
    const w = p.w / s, h = p.h / s, out = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < p.h; y++) for (let x = 0; x < p.w; x++) {
      const si = (y * p.w + x) * 4, bi = ((y - (y % s)) * p.w + (x - (x % s))) * 4;
      for (let k = 0; k < 4; k++) if (p.data[si + k] !== p.data[bi + k]) return null;
      if (x % s === 0 && y % s === 0) out.set(p.data.subarray(si, si + 4), ((y / s) * w + x / s) * 4);
    }
    return { w, h, data: out };
  }

  const slash = (p) => String(p || '').replace(/\\/g, '/');
  const dirOf = (rel) => (rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '');
  const baseOf = (rel) => rel.slice(rel.lastIndexOf('/') + 1);

  async function toggleMenu() {
    const menu = $('.ss-menu');
    if (!menu.classList.contains('hidden')) return closeMenu();
    if (!t.project.root()) { t.toast('Open a project folder first.'); return; }
    const files = (await t.project.files()).filter((f) => /\.png$/i.test(f.name)).map((f) => ({ ...f, rel: slash(f.rel) })).sort((a, b) => a.rel.localeCompare(b.rel));
    menuFiles = files;
    menu.innerHTML = `<div class="ss-menu-title">Open a PNG from this project</div>` + (files.length
      ? files.slice(0, 400).map((f, i) => `<button data-open="${i}" title="${esc(f.rel)}">${esc(f.rel)}</button>`).join('')
      : '<div class="ss-empty">There are no PNG pictures in this project yet.</div>');
    const b = $('[data-a="open"]');
    menu.style.top = `${b.offsetTop + b.offsetHeight + 4}px`;
    menu.classList.remove('hidden');
    b.classList.add('on');
  }

  function closeMenu() {
    if (!root) return;
    $('.ss-menu').classList.add('hidden');
    $('[data-a="open"]').classList.remove('on');
  }

  async function openPng(f) {
    closeMenu();
    // walk_2.png next to walk_1.png and walk_3.png opens all of them, as frames
    let group = [f];
    const m = /^(.*)_(\d+)\.png$/i.exec(baseOf(f.rel));
    const dir = dirOf(f.rel);
    if (m) {
      const byRel = new Map(menuFiles.map((x) => [x.rel.toLowerCase(), x]));
      const run = [];
      for (let i = 1; i <= 200; i++) {
        const hit = byRel.get(`${dir ? dir + '/' : ''}${m[1]}_${i}.png`.toLowerCase());
        if (!hit) break;
        run.push(hit);
      }
      if (run.length > 1 && run.includes(f)) group = run;
    }
    try {
      let pics = [];
      for (const g of group) pics.push(await loadPng(g.path));
      if (!pics.every((p) => p.w === pics[0].w && p.h === pics[0].h)) { group = [f]; pics = [await loadPng(f.path)]; }
      let sc = pics[0].scale;
      let real = pics.map((p) => shrink(p, sc));
      if (real.some((p) => !p)) { sc = 1; real = pics; }
      const { w, h } = real[0];
      if (w > MAX_SIDE || h > MAX_SIDE) { t.toast(`${f.rel} is ${w} x ${h} pixels. Sprite Studio edits pictures up to ${MAX_SIDE} x ${MAX_SIDE}.`, 'error', 5000); return; }
      begin();
      doc.w = w;
      doc.h = h;
      doc.frames = real.map((p) => p.data);
      doc.cur = Math.max(0, group.indexOf(f));
      finish(false);
      $('[data-f="name"]').value = group.length > 1 ? m[1] : baseOf(f.rel).replace(/\.png$/i, '');
      $('[data-f="folder"]').value = dir;
      setScale(sc);
      mine = new Set(group.map((g) => g.rel.toLowerCase()));
      if (group.length > 1) mine.add(`${dir ? dir + '/' : ''}${m[1]}_sheet.png`.toLowerCase()); // its sprite sheet is its own too
      saved = null;
      renderCode();
      const what = group.length > 1 ? `${group.length} frames of ${m[1]}` : f.rel;
      t.toast(sc > 1 ? `Opened ${what}. It was saved at ${sc}x, so you're editing the real ${w} x ${h} pixels.` : `Opened ${what} (${w} x ${h}).`, 'ok', 3500);
    } catch (err) {
      t.toast(`Couldn't open ${f.rel}: ${err.message}`, 'error', 5000);
    }
  }

  // ---------------------------------------------------------------- saving
  const cleanName = (s) => String(s || '').trim().replace(/\.png$/i, '').replace(/\s+/g, '_').replace(/[^\w-]/g, '').slice(0, 60) || 'sprite';
  const cleanFolder = (s) => slash(s).split('/').map((p) => p.trim().replace(/[<>:"|?*]/g, '')).filter((p) => p && p !== '.' && p !== '..').join('/');

  function plan() {
    const name = cleanName($('[data-f="name"]').value);
    const dir = cleanFolder($('[data-f="folder"]').value);
    const pre = dir ? dir + '/' : '';
    const n = doc.frames.length;
    const frames = n === 1 ? [`${pre}${name}.png`] : doc.frames.map((_, i) => `${pre}${name}_${i + 1}.png`);
    return { name, dir, pre, frames, sheet: n > 1 && sheet ? `${pre}${name}_sheet.png` : null };
  }

  function whereText() {
    const p = plan();
    const size = `${doc.w * scale} x ${doc.h * scale}`;
    const el = $('.ss-where');
    if (p.frames.length === 1) el.textContent = `Saves ${p.frames[0]} (${size} pixels).`;
    else el.textContent = `Saves ${p.frames[0]} to ${baseOf(p.frames[p.frames.length - 1])} (${size} pixels each)${p.sheet ? `, and the sheet ${baseOf(p.sheet)}` : ''}.`;
  }

  function setScale(s) {
    scale = s;
    t.storage.set('scale', s);
    $$('[data-scale]').forEach((b) => b.classList.toggle('on', +b.dataset.scale === s));
    whereText();
  }

  async function save() {
    if (!t.project.write) { t.toast('Sprite Studio needs the "files" permission to save pictures.', 'error'); return; }
    if (!t.project.root()) { t.toast('Open a project folder first.'); return; }
    if (stroke) onUp();
    const p = plan();
    $('[data-f="name"]').value = p.name;
    $('[data-f="folder"]').value = p.dir;
    t.storage.set('folder', p.dir);
    const all = [...p.frames, ...(p.sheet ? [p.sheet] : [])];
    const files = (await t.project.files()).map((f) => slash(f.rel).toLowerCase());
    const existing = new Set(files);
    const clash = all.filter((f) => existing.has(f.toLowerCase()) && !mine.has(f.toLowerCase()));
    if (clash.length) {
      const ok = await t.ask({ title: clash.length === 1 ? `Replace ${clash[0]}?` : `Replace ${clash.length} pictures in ${p.dir || 'the project'}?`, confirm: true, okLabel: 'Replace' });
      if (!ok) return;
    }
    const btn = $('[data-a="save"]');
    btn.disabled = true;
    try {
      const jobs = p.frames.map((f, i) => [f, { w: doc.w, h: doc.h, data: doc.frames[i] }]);
      if (p.sheet) jobs.push([p.sheet, sheetOf(doc.frames)]);
      for (const [path, pic] of jobs) {
        const bytes = await encodePng(pic.w * scale, pic.h * scale, upscale(pic.data, pic.w, pic.h, scale), scale);
        await t.project.write(path, base64(bytes), { encoding: 'base64' });
        mine.add(path.toLowerCase());
      }
      saved = { name: p.name, frames: p.frames, sheet: p.sheet, w: doc.w * scale, h: doc.h * scale, scale };
      const found = /^\s*(?:mention|import)\s+(tgame|atgui|mtgui|tgui)\b/m.exec(t.editor.code() || '');
      if (found) setLib(found[1] === 'tgui' ? 'mtgui' : found[1]);
      renderCode();
      const left = p.frames.length > 1 && existing.has(`${p.pre}${p.name}_${p.frames.length + 1}.png`.toLowerCase());
      t.toast(`Saved ${p.frames.length === 1 ? p.frames[0] : `${p.frames.length} frames in ${p.dir || 'the project'}`}${p.sheet ? ' and a sprite sheet' : ''}.${left ? ` ${p.name}_${p.frames.length + 1}.png from before is still there.` : ''}`, 'ok', 3000);
      root.querySelector('.ss-code').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } catch (err) {
      t.toast(`Couldn't save: ${String(err.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, '')}`, 'error', 6000);
    } finally {
      btn.disabled = false;
    }
  }

  // ---------------------------------------------------------------- "Use in code"
  function varName(name) {
    let v = name.replace(/-/g, '_').replace(/[^\w]/g, '');
    if (!v || /^\d/.test(v)) v = 'sprite_' + v;
    if (RESERVED.has(v)) v += '_pic';
    return v;
  }

  // The path from the folder of the open .tuf file to a project file, with forward slashes.
  function relFrom(fromDir, target) {
    const a = fromDir ? fromDir.split('/') : [], b = target.split('/');
    let i = 0;
    while (i < a.length && i < b.length - 1 && a[i].toLowerCase() === b[i].toLowerCase()) i++;
    return [...a.slice(i).map(() => '..'), ...b.slice(i)].join('/');
  }

  function activeDir() {
    const f = t.editor.file();
    const r = t.project.root();
    if (!f || !r || !/\.tuf$/i.test(f)) return '';
    const rel = slash(t.project.rel(f));
    return rel === slash(f) ? '' : dirOf(rel);
  }

  // The open file's window: its variable, and its middle for where a tgame picture starts.
  function windowInfo(which) {
    const code = t.editor.code() || '';
    if (which === 'tgame') {
      const m = /^\s*([A-Za-z_]\w*)\s*=\s*tgame\.window\(([^)]*)\)/m.exec(code);
      const nums = m ? [...m[2].matchAll(/(?:^|,)\s*(\d+)\s*(?=,|$)/g)].map((x) => +x[1]) : [];
      return { name: m ? m[1] : 'game', x: Math.round((nums[0] || 800) / 2), y: Math.round((nums[1] || 600) / 2) };
    }
    const m = /^\s*([A-Za-z_]\w*)\s*=\s*(?:mtgui|tgui|atgui)\.window\(/m.exec(code);
    return { name: m ? m[1] : 'app' };
  }

  function snippet(which, info, fromDir, win) {
    const v = varName(info.name);
    const paths = info.frames.map((f) => relFrom(fromDir, f));
    const q = (s) => `"${s}"`;
    let make;
    const lines = [];
    if (which === 'tgame') make = `${v} = ${win.name}:image(${q(paths[0])}, ${win.x}, ${win.y}, ${info.w})`;
    else if (which === 'mtgui') make = `${v} = ${win.name}:image ${q(paths[0])}`;
    else make = `${v} = ${win.name}:image(${q(paths[0])}, ${info.w * Math.max(1, Math.ceil(64 / info.w))})`;
    if (paths.length > 1) {
      const list = `${v}_pics = [${paths.map(q).join(', ')}]`;
      lines.push(list.length <= 56 ? list : `${v}_pics = [\n${paths.map((p) => `    ${q(p)}`).join(',\n')}\n]`);
    }
    lines.push(make);
    if (which === 'atgui') lines.push(`${v}:css "image-rendering: pixelated; border-radius: 0"`);
    if (paths.length > 1) {
      lines.push(`${v}_at = 0`, `${win.name}:every(1 / ${fps}, next_${v}_pic)`, '',
        `func next_${v}_pic():`, `    ${v}_at = (${v}_at + 1) % len(${v}_pics)`, `    ${v}:set ${v}_pics[${v}_at]`);
    }
    return lines.join('\n');
  }

  // A whole little program that shows the sprite, for "Try in a new file" (it lives in the project's top folder).
  function program(which, info) {
    const v = varName(info.name);
    const title = info.name.replace(/[_-]+/g, ' ').trim().replace(/^./, (c) => c.toUpperCase()) || 'Sprite';
    if (which === 'tgame') {
      const body = snippet('tgame', info, '', { name: 'game', x: 300, y: 200 });
      return `mention tgame\n\ngame = tgame.window("${title}", 600, 400)\ngame:background "navy"\n${body}\n\nwhile game:open():\n    dt = game:frame()\n` +
        `    if game:held("left"):\n        ${v}:move(-200 * dt, 0)\n    if game:held("right"):\n        ${v}:move(200 * dt, 0)\n`;
    }
    const body = snippet(which, info, '', { name: 'app' });
    return `mention ${which}\n\napp = ${which}.window("${title}", 400, 300)\napp:heading "${title}"\n${body}\n`;
  }

  const NOTES = {
    tgame: (info) => `It starts with its middle in the middle of the window.${info.scale === 1 && Math.max(info.w, info.h) < 48 ? ' Games draw pictures sharpest at the size they were saved, so use Scale up to make it bigger.' : ''}`,
    mtgui: () => 'App windows show a picture at the size it was saved. Use Scale up to make it bigger.',
    atgui: () => 'The css line keeps the pixels sharp when the picture is drawn bigger.',
  };

  // Code lines for a narrow panel: a line too long to fit wraps with a hanging indent, so its second half
  // can't be mistaken for a line of its own. The spaces stay in the text, for copying by hand.
  const codeLines = (code) => code.split('\n').map((ln, i, all) => {
    const n = ln.length - ln.trimStart().length + 2;
    return `<span class="ss-ln" style="padding-left:${n}ch;text-indent:-${n}ch">${esc(ln)}${i < all.length - 1 ? '\n' : ''}</span>`;
  }).join('');

  function setLib(id) {
    lib = id;
    t.storage.set('lib', id);
  }

  function renderCode() {
    if (!root) return;
    const body = $('.ss-code-body');
    if (!saved) { body.innerHTML = '<p class="ss-muted">Save your sprite, and the Tuff code that shows it appears here.</p>'; return; }
    const code = snippet(lib, saved, activeDir(), windowInfo(lib));
    body.innerHTML = `
      <div class="ss-seg ss-libs" role="tablist">${['tgame', 'mtgui', 'atgui'].map((l) => `<button data-lib="${l}" class="${l === lib ? 'on' : ''}" title="${{ tgame: 'Games', mtgui: 'App windows', atgui: 'Modern apps' }[l]}">${l}</button>`).join('')}</div>
      <pre class="ss-pre" aria-label="Tuff code">${codeLines(code)}</pre>
      <p class="ss-note">${esc(NOTES[lib](saved))}${saved.frames.length > 1 ? ` It shows the next picture ${fps} times a second.` : ''}</p>
      <div class="ss-row"><button class="ss-btn" data-a="copy">${icon('copy')}Copy</button><button class="ss-btn" data-a="insert">Insert</button><button class="ss-btn" data-a="try">${icon('page')}Try in a new file</button></div>`;
  }

  async function tryFile() {
    if (!saved || !t.project.write) return;
    const rel = `${varName(saved.name)}_${lib === 'tgame' ? 'game' : 'app'}.tuf`;
    const exists = (await t.project.files()).some((f) => slash(f.rel).toLowerCase() === rel.toLowerCase());
    if (exists && !made.has(rel)) {
      const ok = await t.ask({ title: `Replace ${rel}?`, confirm: true, okLabel: 'Replace' });
      if (!ok) return;
    }
    try {
      const full = await t.project.write(rel, program(lib, saved));
      made.add(rel);
      await t.openFile(full);
      t.toast(`Made ${rel}. Press Run to try it.`, 'ok', 3000);
    } catch (err) {
      t.toast(`Couldn't make ${rel}: ${err.message}`, 'error', 5000);
    }
  }

  // ---------------------------------------------------------------- the panel
  function onClick(e) {
    const b = e.target.closest('button');
    if (!b || b.disabled || !root.contains(b)) {
      if (!e.target.closest('.ss-menu')) closeMenu();
      return;
    }
    if (!b.closest('.ss-menu') && b.dataset.a !== 'open') closeMenu();
    const d = b.dataset;
    if (d.tool) return setTool(d.tool);
    if (d.color) return setColor(d.color);
    if (d.frame) return selectFrame(+d.frame);
    if (d.scale) return setScale(+d.scale);
    if (d.lib) { setLib(d.lib); return renderCode(); }
    if (d.open) return openPng(menuFiles[+d.open]);
    if (d.size) {
      const custom = $('.ss-custom');
      if (d.size === 'custom') {
        custom.classList.toggle('hidden');
        $('[data-f="cw"]').value = doc.w;
        $('[data-f="ch"]').value = doc.h;
        if (!custom.classList.contains('hidden')) $('[data-f="cw"]').focus();
        return syncSize();
      }
      custom.classList.add('hidden');
      resizeTo(+d.size, +d.size);
      return syncSize();
    }
    switch (d.a) {
      case 'new': return newSprite();
      case 'open': return toggleMenu();
      case 'resize': { resizeTo(+$('[data-f="cw"]').value, +$('[data-f="ch"]').value); $('.ss-custom').classList.add('hidden'); return syncSize(); }
      case 'mirror': return setMirror(!mirror);
      case 'undo': return undo();
      case 'redo': return redo();
      case 'add': case 'dup': case 'del': case 'left': case 'right': return frameOp(d.a);
      case 'play': return setPlaying(!playing);
      case 'save': return save();
      case 'copy': navigator.clipboard.writeText(snippet(lib, saved, activeDir(), windowInfo(lib))); t.toast('Copied.', 'ok', 1500); return;
      case 'insert': t.editor.insert(snippet(lib, saved, activeDir(), windowInfo(lib)) + '\n'); return;
      case 'try': return tryFile();
    }
  }

  function onChange(e) {
    const f = e.target.dataset.f;
    if (f === 'grid') { grid = e.target.checked; t.storage.set('grid', grid); render(); }
    if (f === 'onion') { onion = e.target.checked; t.storage.set('onion', onion); render(); }
    if (f === 'sheet') { sheet = e.target.checked; t.storage.set('sheet', sheet); whereText(); }
    if (f === 'picker') setColor(e.target.value, true);
    if (f === 'hex') applyHex();
    if (f === 'fps') {
      fps = clamp(Math.round(+e.target.value) || 8, 1, 30);
      e.target.value = fps;
      t.storage.set('fps', fps);
      restartPreview();
      renderCode();
    }
    if (f === 'name' || f === 'folder') whereText();
  }

  function applyHex() {
    const box = $('[data-f="hex"]');
    const hex = hexOk(box.value);
    if (hex) setColor(hex);
    else { box.value = color; t.toast('A colour code looks like #3574f0.', 'info', 2000); }
  }

  // Ctrl+Z and Ctrl+Y belong to the sprite while you're in this panel. The IDE catches keys on the document
  // first (Ctrl+Y would delete a line in the code editor), so this listens on the window, and only while focus
  // is inside the panel.
  function onKey(e) {
    if (!root || !root.contains(document.activeElement)) return;
    const el = e.target;
    const typing = el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !['checkbox', 'color', 'button'].includes(el.type));
    const ctrl = e.ctrlKey || e.metaKey;
    const k = e.key.toLowerCase();
    if (ctrl && !e.altKey && (k === 'z' || k === 'y')) {
      e.stopPropagation();
      if (typing) return; // text boxes keep their own undo
      e.preventDefault();
      if (k === 'y' || e.shiftKey) redo(); else undo();
      return;
    }
    if (typing) {
      if (e.key === 'Enter' && el.dataset.f === 'hex') { e.preventDefault(); applyHex(); }
      if (e.key === 'Enter' && (el.dataset.f === 'cw' || el.dataset.f === 'ch')) { e.preventDefault(); $('[data-a="resize"]').click(); }
      return;
    }
    if (ctrl || e.altKey || e.metaKey) return;
    if (e.key === 'Escape') { if (stroke) cancelStroke(); closeMenu(); return; }
    const tl = TOOLS.find((x) => x.key === e.key.toUpperCase());
    if (tl) { e.preventDefault(); setTool(tl.id); }
    else if (k === 'm') { e.preventDefault(); setMirror(!mirror); }
  }

  const html = () => `<div class="ss" tabindex="-1">
    <div class="ss-sec ss-top">
      <div class="ss-row">
        <button class="ss-btn" data-a="new" title="Start a new sprite (Undo brings the old one back)">${icon('page')}New</button>
        <button class="ss-btn" data-a="open" title="Edit a PNG from this project">${icon('folder')}Open</button>
        <span class="ss-grow"></span>
        <div class="ss-seg ss-sizes" role="group" aria-label="Size">${SIZES.map((s) => `<button data-size="${s}" title="${s} x ${s} pixels">${s}</button>`).join('')}<button data-size="custom" title="Choose your own width and height">Custom</button></div>
      </div>
      <div class="ss-row ss-custom hidden">
        <label>Width <input class="ss-in ss-num" type="number" min="1" max="${MAX_SIDE}" data-f="cw"></label>
        <label>Height <input class="ss-in ss-num" type="number" min="1" max="${MAX_SIDE}" data-f="ch"></label>
        <button class="ss-btn" data-a="resize">Resize</button>
      </div>
      <div class="ss-menu hidden"></div>
    </div>
    <div class="ss-sec ss-draw">
      <div class="ss-row ss-tools" role="toolbar" aria-label="Tools">${TOOLS.map((x) => `<button class="ss-ic" data-tool="${x.id}" title="${x.name} (${x.key})">${icon(x.id)}</button>`).join('')}<span class="ss-sep"></span><button class="ss-ic" data-a="mirror" title="Mirror: draw on the left and right side at once (M)">${icon('mirror')}</button></div>
      <div class="ss-hint"></div>
      <div class="ss-stage"><canvas class="ss-canvas"></canvas></div>
      <div class="ss-row ss-under">
        <button class="ss-ic" data-a="undo" title="Undo (Ctrl+Z)">${icon('undo')}</button>
        <button class="ss-ic" data-a="redo" title="Redo (Ctrl+Y)">${icon('redo')}</button>
        <label class="ss-check"><input type="checkbox" data-f="grid"${grid ? ' checked' : ''}>Grid</label>
        <label class="ss-check" title="Show the frame before this one, faintly"><input type="checkbox" data-f="onion"${onion ? ' checked' : ''}>Onion skin</label>
        <span class="ss-grow"></span>
        <span class="ss-pos"></span>
      </div>
    </div>
    <div class="ss-sec">
      <div class="ss-title">Colours</div>
      <div class="ss-palette">${PALETTE.map((c) => `<button data-color="${c}" title="${c}" style="--c:${c}"></button>`).join('')}</div>
      <div class="ss-row ss-current">
        <label class="ss-pick" title="Choose any colour"><input type="color" data-f="picker"></label>
        <input class="ss-in ss-hex" data-f="hex" spellcheck="false" maxlength="7" aria-label="Colour code">
        <div class="ss-recent-group"><span class="ss-label">Recent</span><div class="ss-recent"></div></div>
      </div>
    </div>
    <div class="ss-sec">
      <div class="ss-row ss-head">
        <div class="ss-title">Frames <span class="ss-count"></span></div>
        <span class="ss-grow"></span>
        <button class="ss-ic" data-a="left" title="Move this frame earlier">${icon('left')}</button>
        <button class="ss-ic" data-a="right" title="Move this frame later">${icon('right')}</button>
      </div>
      <div class="ss-frames"></div>
      <div class="ss-row ss-frame-btns">
        <button class="ss-btn" data-a="add" title="Add an empty frame after this one">${icon('plus')}Add</button>
        <button class="ss-btn" data-a="dup" title="Add a copy of this frame">${icon('copy')}Duplicate</button>
        <button class="ss-btn" data-a="del" title="Delete this frame">${icon('trash')}Delete</button>
      </div>
      <div class="ss-anim">
        <div class="ss-preview" title="Preview"><canvas></canvas></div>
        <div class="ss-anim-side">
          <label class="ss-speed">Speed <input class="ss-in ss-num" type="number" min="1" max="30" data-f="fps" value="${fps}"> frames a second</label>
          <button class="ss-btn" data-a="play">${icon('pause')}Pause</button>
          <span class="ss-muted ss-one-note">Add a frame to make an animation.</span>
        </div>
      </div>
    </div>
    <div class="ss-sec">
      <div class="ss-title">Save</div>
      <div class="ss-fields">
        <label>Name<input class="ss-in" data-f="name" value="sprite" spellcheck="false"></label>
        <label>Folder<input class="ss-in" data-f="folder" value="${esc(cleanFolder(t.storage.get('folder', 'sprites')) || '')}" spellcheck="false" placeholder="the project's top folder"></label>
      </div>
      <div class="ss-row ss-scale-row"><span class="ss-label">Scale up</span><div class="ss-seg">${SCALES.map((s) => `<button data-scale="${s}" title="${s === 1 ? 'True pixels: one pixel in the file for each pixel you drew' : `Each pixel becomes ${s} x ${s}, still sharp`}">${s}x</button>`).join('')}</div></div>
      <label class="ss-check ss-sheet"><input type="checkbox" data-f="sheet"${sheet ? ' checked' : ''}>Also save a sprite sheet (every frame side by side)</label>
      <div class="ss-row ss-save-row"><button class="btn sm primary" data-a="save">Save PNG</button></div>
      <div class="ss-where"></div>
    </div>
    <div class="ss-sec ss-code">
      <div class="ss-title">Use in code</div>
      <div class="ss-code-body"></div>
    </div>
  </div>`;

  const panel = t.panel('editor', {
    title: 'Sprite Studio',
    mount(el) {
      el.innerHTML = html();
      root = el.querySelector('.ss');
      view = root.querySelector('.ss-canvas');
      root.addEventListener('click', onClick);
      root.addEventListener('change', onChange);
      root.addEventListener('input', (e) => { if (e.target.dataset.f === 'name' || e.target.dataset.f === 'folder') whereText(); });
      root.addEventListener('pointerdown', (e) => {
        if (!e.target.closest('input, button, label, .ss-menu')) root.focus({ preventScroll: true });
      });
      view.addEventListener('pointerdown', onDown);
      view.addEventListener('pointermove', onMove);
      view.addEventListener('pointerup', onUp);
      view.addEventListener('pointercancel', () => cancelStroke());
      view.addEventListener('pointerleave', () => { if (!stroke) { hover = null; showPos(); schedule(); } });
      view.addEventListener('contextmenu', (e) => e.preventDefault());
      root.querySelector('.ss-code').addEventListener('pointerenter', () => saved && renderCode());
      window.addEventListener('keydown', onKey, true);
      ro = new ResizeObserver(() => layout());
      ro.observe(root);
      setTool('pencil');
      setColor(color);
      setScale(scale);
      renderRecent();
      renderCode();
      layout();
      changed();
      return {
        onShow() { requestAnimationFrame(layout); restartPreview(); renderCode(); },
        onHide() { clearInterval(timer); timer = null; if (stroke) onUp(); closeMenu(); },
      };
    },
  });
  t.command('open', 'Sprite Studio: Open', () => panel.toggle());

  return () => {
    window.removeEventListener('keydown', onKey, true);
    clearInterval(timer);
    cancelAnimationFrame(raf);
    ro?.disconnect();
  };
});
