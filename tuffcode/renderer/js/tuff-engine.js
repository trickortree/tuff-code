// Tuff Engine: the visual game editor, a centre pseudo-tab next to Design Studio (ide.js showEngine). It edits tgame
// games, 2D (tgame.window) and 3D (tgame.world).
//   - The code is the only source of truth. Every action is one small edit of the file's Monaco model (studio.js
//     makeEditor, so it is one Ctrl+Z step), and fixups() keeps the code the Engine owns right inside that same step.
//   - The scene is the real game engine: `tuff.py --scene` runs the program's setup with no window (TuffIDE.scene),
//     and renderer/engine-host/host.js draws what it made in an iframe (its API is at the top of host.js).
//   - Only simple top-level lines are edited (coin = game:circle(200, 200, 14, "gold")). Everything else stays exactly
//     as typed and shows as read-only "Made by your code". Things are named by keys: 'root' (the game), v:<name>,
//     l:<line> (no name), g:<line>:<kind> (made by code).
//   - Ready-made pieces (Player, Coin, Enemy, ...) come with small behaviour functions (BEH). They are recognised again
//     by their bodies, not by comments, so code an agent writes that matches counts too.
// Tests: test/e2e/suites/engine.mjs.
(() => {
  'use strict';
  const api = window.tuff;
  const K = window.TuffStudio.kit;
  const { $, $$, esc } = K;
  const UI = K.UI;
  let ide = null;

  // ---------------------------------------------------------------- icons
  const svg = (d) => `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const dot = (x, y) => `<circle cx="${x}" cy="${y}" r=".7" fill="currentColor" stroke="none"/>`;
  const ICON = {
    pad: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6.5h8a4 4 0 014 4v.6a2.9 2.9 0 01-5.1 1.9L11.6 12H8.4l-1.3 1A2.9 2.9 0 012 11.1v-.6a4 4 0 014-4z"/><path d="M6.2 8.6v3M4.7 10.1h3"/><circle cx="13" cy="9.4" r=".7"/><circle cx="14.6" cy="11" r=".7"/></svg>',
    game: svg('<rect x="1.5" y="3" width="13" height="10" rx="2"/><path d="M4.5 10.5l2.5-3 2 2 1.5-1.5 2 2.5"/>'),
    world: svg('<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2.2 2.2 2.2 9.8 0 12M8 2C5.8 4.2 5.8 11.8 8 14"/>'),
    player: svg(`<rect x="3" y="3" width="10" height="10" rx="2.2"/>${dot(6.3, 7)}${dot(9.7, 7)}<path d="M6.2 10h3.6"/>`),
    coin: svg('<circle cx="8" cy="8" r="5.5"/><circle cx="8" cy="8" r="2.8"/>'),
    enemy: svg(`<path d="M3 13.5V7.5a5 5 0 0110 0v6l-1.7-1.3-1.6 1.3L8 12.2l-1.7 1.3-1.6-1.3z"/>${dot(6.2, 7.6)}${dot(9.8, 7.6)}`),
    ball: svg('<circle cx="8" cy="8" r="5.5"/><path d="M3.3 6.4c3 1.1 6.4 1.1 9.4 0M3.3 9.6c3-1.1 6.4-1.1 9.4 0"/>'),
    score: svg('<path d="M5 2.5h6v3.5a3 3 0 01-6 0z"/><path d="M5 4H3a2 2 0 002 3M11 4h2a2 2 0 01-2 3M8 9v3M5.5 13.5h5"/>'),
    box: svg('<rect x="3" y="3" width="10" height="10" rx="1.5"/>'),
    circle: svg('<circle cx="8" cy="8" r="5.5"/>'),
    line: svg('<path d="M3 13L13 3"/>'),
    text: svg('<path d="M3 3.5h10M8 3.5v9.5"/>'),
    image: svg('<rect x="1.5" y="2.5" width="13" height="11" rx="2"/><circle cx="5.8" cy="6.3" r="1.3"/><path d="M2 12l3.6-3.5 2.6 2.6 2-2 3.8 3.4"/>'),
    draw: svg('<path d="M3 13l1-3.5 7-7 2.5 2.5-7 7z"/><path d="M9.5 4l2.5 2.5"/>'),
    hudtext: svg('<rect x="1.5" y="2.5" width="13" height="11" rx="2"/><path d="M4.5 5.5h4"/>'),
    hudbox: svg('<rect x="1.5" y="2.5" width="13" height="11" rx="2"/><rect x="4" y="9.5" width="8" height="2" rx="1"/>'),
    tree: svg('<circle cx="8" cy="6.5" r="4.5"/><path d="M8 11v3.5"/>'),
    pine: svg('<path d="M8 1.8L3.8 8h2.4L3.3 11.8h9.4L9.8 8h2.4z"/><path d="M8 11.8v2.6"/>'),
    rock: svg('<path d="M2.5 12.5l2-5 3-3 3.5 1.5 2.5 3.5.5 3z"/>'),
    bush: svg('<path d="M2.6 12.5a3 3 0 011.9-5 3 3 0 015-1.6 3 3 0 014 3 2.5 2.5 0 01-.5 3.6z"/>'),
    flower: svg('<circle cx="8" cy="5.5" r="1.6"/><path d="M8 7.1V14M8 11c-1.4-1.5-2.8-1.6-4-1.1M8 3.9V2M6.4 5.5H4.6M11.4 5.5H9.6"/>'),
    house: svg('<path d="M2.5 7.5L8 3l5.5 4.5M4 6.5v7h8v-7"/><path d="M7 13.5v-3h2v3"/>'),
    hut: svg('<path d="M2 9l6-6 6 6M4 8v5.5h8V8"/>'),
    sign: svg('<rect x="2.5" y="3" width="11" height="6" rx="1"/><path d="M8 9v5"/>'),
    crate: svg('<rect x="2.5" y="2.5" width="11" height="11" rx="1"/><path d="M2.5 2.5l11 11M13.5 2.5l-11 11"/>'),
    fence: svg('<path d="M4 14V4.2l1-1.4 1 1.4V14M10 14V4.2l1-1.4 1 1.4V14M2 7h12M2 11h12"/>'),
    cylinder: svg('<ellipse cx="8" cy="4" rx="5" ry="2"/><path d="M3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4"/>'),
    cone: svg('<path d="M8 2l5 10c0 1.1-2.2 2-5 2s-5-.9-5-2z"/>'),
    plane: svg('<path d="M1.5 11l4-5.5h9l-4 5.5z"/>'),
    light: svg('<path d="M6 12.5h4M6.5 14.5h3M8 1.8a4.2 4.2 0 00-2.4 7.6c.5.4.9 1 .9 1.6V11h3v-.4c0-.6.4-1.2.9-1.6A4.2 4.2 0 008 1.8z"/>'),
    island: svg('<path d="M1.5 11.5c2 1.5 4 1.5 6.5 0s4.5-1.5 6.5 0"/><path d="M4.5 10a3.5 3.5 0 017 0"/><path d="M8 7V3.5l2.5 1"/>'),
    ground: svg('<path d="M1.5 10.5h13M3 13h10"/><path d="M5 10.5V8M8 10.5V7M11 10.5V8.5"/>'),
    model: svg('<path d="M8 1.8l5.5 3v6.4L8 14.2l-5.5-3V4.8z"/><path d="M2.5 4.8L8 8l5.5-3.2M8 8v6.2"/>'),
    hold: svg('<path d="M4 14L11 4"/><path d="M9 3.5c1.5-1 3.5-.5 4.5 1-1 .3-2.4 1.3-3 2.5z"/>'),
    sound: svg('<path d="M2.5 6v4h2.5L8.5 13V3L5 6z"/><path d="M11 5.5a3.5 3.5 0 010 5"/>'),
    ask: svg('<path d="M2.5 4a1.5 1.5 0 011.5-1.5h8A1.5 1.5 0 0113.5 4v5.5A1.5 1.5 0 0112 11H7l-3 2.5V11a1.5 1.5 0 01-1.5-1.5z"/><path d="M5.5 6.8h5"/>'),
    stop: '<svg viewBox="0 0 16 16"><rect x="4" y="4" width="8" height="8" rx="1.5" fill="currentColor" stroke="none"/></svg>',
    cam: svg('<rect x="1.5" y="4.5" width="9.5" height="7" rx="1.5"/><path d="M11 7l3.5-2v6L11 9"/>'),
    warn: svg('<path d="M8 2.2l6 10.6H2z"/><path d="M8 6.5v3"/>') + '',
  };
  ICON.sphere = ICON.ball;
  ICON.spawn = ICON.model;

  // ---------------------------------------------------------------- reading the file
  const IMPORT_RE = /^(?:import|mention)\s+tgame\b/;
  const OTHER_RE = /^(?:import|mention)\s+(tgui|mtgui|atgui)\b/;
  const ANY_IMPORT_RE = /^(?:import|mention)\s+[A-Za-z_]\w*/;
  const GAME_RE = /^([A-Za-z_]\w*)\s*=\s*tgame\.(window|world)\b\s*(.*)$/;
  const SET_RE = /^([A-Za-z_]\w*):(background|sky|fog|sun|island|ground)\b\s*(.*)$/;
  const REG_RE = /^([A-Za-z_]\w*):(every_frame|on_key|every|after|clicked)\b\s*(.*)$/;
  const MAKE_RE = /^(?:([A-Za-z_]\w*)\s*=\s*)?([A-Za-z_]\w*):(box|circle|line|text|image|sphere|cylinder|cone|plane|spawn|light|player|hud|hold)\b\s*(.*)$/;
  const PROP_RE = /^([A-Za-z_]\w*):(speed|spin|on_edge|layer|turn_to|hide|label|solid|glow|align|scale|clicked|walk_speed|jump_height|move_to)\b\s*(.*)$/;
  const FUNC_RE = /^func\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:\s*$/;
  const SCORE_RE = /^score\s*=\s*(-?\d+)\s*$/;
  const MARK_RE = /^#\s*Tuff Engine:/;
  const NAME_RE = /^[A-Za-z_]\w*$/;
  const K2D = ['box', 'circle', 'line', 'text', 'image', 'hud'];
  const K3D = ['box', 'sphere', 'cylinder', 'cone', 'plane', 'spawn', 'light', 'player', 'hud'];
  const KHUD = ['text', 'box', 'circle', 'line', 'image'];
  const FAMILY = {
    sprite: ['speed', 'spin', 'on_edge', 'layer', 'turn_to', 'hide', 'align', 'clicked'],
    object: ['speed', 'spin', 'turn_to', 'hide', 'label', 'solid', 'glow', 'scale', 'clicked'],
    player: ['move_to', 'turn_to', 'walk_speed', 'jump_height'],
  };
  const family = (n) => (n.kind === 'player' ? 'player' : n.layer === 'world' ? 'object' : 'sprite');
  const BUILTINS = ['print', 'number', 'num', 'text', 'str', 'int', 'len', 'round', 'random', 'wait', 'range', 'clear', 'sqrt', 'abs', 'floor', 'ceil', 'min', 'max', 'sum', 'average', 'err', 'all'];
  const LIBS = ['tgame', 'tgui', 'mtgui', 'atgui', 'tap', 'anims'];
  const KEYWORDS = () => window.TUFF_KEYWORDS || [];

  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const range = (a, b) => { const out = []; for (let i = a; i <= b; i++) out.push(i); return out; };
  const cap = (s) => String(s).charAt(0).toUpperCase() + String(s).slice(1);
  const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
  // A whole name in a line of code. Tuff's names can hold letters in any language, so \b (A-Z only) would find coin
  // inside coinça.
  const wordRe = (name) => new RegExp(String.raw`(?<![\p{L}\p{N}_])${name}(?![\p{L}\p{N}_])`, 'u');
  // A number as code: at most 2 decimals, and never -0.
  const num = (n) => { const v = +(+n).toFixed(2); return String(Object.is(v, -0) ? 0 : v); };

  // One input as a value: a number, a string, a bool, a spot (a list of numbers), or { raw } for anything else (a
  // name, a sum, a call), which is always written back exactly as it was typed.
  function val(text) {
    const t = String(text).trim();
    if (!t) return undefined;
    if (t.startsWith('[') && t.endsWith(']')) {
      const items = K.splitTop(t.slice(1, -1));
      const vs = items.map(val);
      return items.length && vs.every(isNum) ? vs : { raw: t };
    }
    const p = K.parseValue(t);
    if (p.kind === 'number' || p.kind === 'string' || p.kind === 'bool') return p.value;
    return { raw: t };
  }

  function fmt(v) {
    if (v === undefined || v === null) return 'nil';
    if (typeof v === 'number') return num(v);
    if (typeof v === 'string') return JSON.stringify(v);
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (Array.isArray(v)) return `[${v.map(fmt).join(', ')}]`;
    return v.raw !== undefined ? v.raw : 'nil';
  }

  // Split a call's inputs on top-level commas, keeping each one's own text and spacing.
  function splitRaw(s) {
    if (!s.trim()) return [];
    const parts = [];
    let depth = 0;
    let quote = null;
    let cur = '';
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (quote) {
        cur += c;
        if (c === '\\') { cur += s[++i] ?? ''; continue; }
        if (c === quote) quote = null;
        continue;
      }
      if (c === '"' || c === "'") quote = c;
      else if (c === '(' || c === '[' || c === '{') depth++;
      else if (c === ')' || c === ']' || c === '}') depth--;
      else if (c === ',' && depth === 0) { parts.push(cur); cur = ''; continue; }
      cur += c;
    }
    parts.push(cur);
    return parts;
  }

  // A call as typed: the head (everything before its inputs), each input's text, and what follows (spaces and a
  // comment). form: 'paren' (inputs in brackets), 'bare' (one input after a space) or 'none'.
  function callOf(full, code, rest) {
    const head = code.slice(0, code.length - rest.length);
    const tail = full.slice(code.length);
    let form = 'none';
    let pieces = [];
    if (rest) {
      if (rest.startsWith('(') && K.closesAtEnd(rest)) { form = 'paren'; pieces = splitRaw(rest.slice(1, -1)); }
      else { form = 'bare'; pieces = [rest]; }
    }
    return { head, form, pieces, tail, vals: pieces.map(val) };
  }

  // A call written back. Inputs that didn't change keep their own text and spacing, so an unchanged call comes back
  // exactly as it was typed. paren: brackets even for one input (makers always use them); otherwise one input goes
  // bare (coin:spin 90), several in brackets, none as ().
  function callText(call, vals, { paren = false, head = call.head } = {}) {
    vals = vals.slice();
    while (vals.length && vals[vals.length - 1] === undefined) vals.pop();
    const keep = (i) => i < call.vals.length && same(call.vals[i], vals[i]);
    if (call.form === 'bare' && vals.length === 1 && !paren) return head + (keep(0) ? call.pieces[0] : fmt(vals[0])) + call.tail;
    if (call.form !== 'paren') {
      const h = head.replace(/\s+$/, '');
      if (!vals.length) return `${h}${call.form === 'none' && head === call.head ? '' : '()'}${call.tail}`;
      if (vals.length === 1 && !paren) return `${h} ${fmt(vals[0])}${call.tail}`;
      return `${h}(${vals.map(fmt).join(', ')})${call.tail}`;
    }
    const parts = vals.map((v, i) => {
      if (keep(i)) return call.pieces[i];
      if (i < call.pieces.length) { const p = call.pieces[i]; return p.match(/^\s*/)[0] + fmt(v) + p.match(/\s*$/)[0]; }
      return (i ? ' ' : '') + fmt(v);
    });
    return `${head}(${parts.join(',')})${call.tail}`;
  }

  // Where a maker's inputs are: `pre` inputs before the position, the position (2D: x, y or a spot [x, y]; 3D: x, y, z
  // or a spot [x, z] / [x, y, z]; a line: x1, y1, x2, y2), then the rest, with tgame's defaults.
  function shapeOf(node) {
    if (node.layer === 'world') {
      if (node.kind === 'spawn') return { pre: 1, dim: 3, rest: [] };
      if (node.kind === 'player') return { pre: 1, dim: 0, rest: [] };
      if (node.kind === 'light') return { pre: 0, dim: 3, rest: [['color', 'white']] };
      return { pre: 0, dim: 3, rest: [['size', node.kind === 'plane' ? 4 : 1], ['color', 'white']] };
    }
    switch (node.kind) {
      case 'line': return { pre: 0, dim: 'line', rest: [['color', 'white']] };
      case 'text': return { pre: 1, dim: 2, rest: [['size', 24], ['color', 'white']] };
      case 'image': return { pre: 1, dim: 2, rest: [['width', undefined]] };
      case 'circle': return { pre: 0, dim: 2, rest: [['r', 20], ['color', 'white']] };
      default: return { pre: 0, dim: 2, rest: [['w', 40], ['h', 40], ['color', 'white']] };
    }
  }
  const PRE = { text: 'words', image: 'file', spawn: 'model', player: 'mode' };
  const PRE_DEF = { words: '', file: '', model: 'tree', mode: 'first person' };

  // node.pos: { form: 'xy' (separate numbers) | 'spot' | 'line' | 'none' (no position: the middle, or a random spot
  // for a spawn) | 'code' (worked out by code), x, y, z, n (how many inputs the position takes), rest (where the
  // inputs after it start) }.
  function readPos(node) {
    const sh = shapeOf(node);
    const a = node.args;
    const pos = { form: 'none', n: 0 };
    if (sh.dim === 'line') {
      const v = [0, 1, 2, 3].map((j) => (a[j] === undefined ? [0, 0, 100, 100][j] : a[j]));
      pos.form = v.every(isNum) ? 'line' : 'code';
      [pos.x1, pos.y1, pos.x2, pos.y2] = v;
      if (pos.form === 'line') { pos.x = (v[0] + v[2]) / 2; pos.y = (v[1] + v[3]) / 2; }
      pos.n = 4;
    } else if (sh.dim) {
      const first = a[sh.pre];
      if (first === undefined) pos.form = 'none';
      else if (Array.isArray(first)) {
        pos.n = 1;
        if (sh.dim === 2 && first.length === 2) { pos.form = 'spot'; [pos.x, pos.y] = first; }
        else if (sh.dim === 3 && (first.length === 2 || first.length === 3)) {
          pos.form = 'spot';
          pos.spot = first.length;
          [pos.x, pos.y, pos.z] = first.length === 2 ? [first[0], 0, first[1]] : first;
        } else pos.form = 'code';
      } else {
        const nums = a.slice(sh.pre, sh.pre + sh.dim);
        if (nums.length === sh.dim && nums.every(isNum)) { pos.form = 'xy'; pos.n = sh.dim; [pos.x, pos.y, pos.z] = nums; }
        else {
          // A spot worked out by code (game:random_spot()) is one input; names or sums for x and y are several.
          pos.form = 'code';
          const spotLike = first && first.raw && /[([]/.test(first.raw) && a.length - sh.pre <= sh.rest.length + 1;
          pos.n = spotLike ? 1 : sh.dim;
        }
      }
    }
    pos.rest = sh.pre + pos.n;
    node.shape = sh;
    node.pos = pos;
  }

  function fieldOf(node, k) {
    if (k === PRE[node.kind]) return node.args[0] === undefined ? PRE_DEF[k] : node.args[0];
    const j = node.shape.rest.findIndex(([n]) => n === k);
    if (j >= 0) { const v = node.args[node.pos.rest + j]; return v === undefined ? node.shape.rest[j][1] : v; }
    return node.pos[k];
  }

  // The node's inputs with some fields changed: words/file/model/mode, x, y, z (all three given for a position from
  // code or from nowhere), x1..y2, and the rest by name. Missing inputs before a changed one get their defaults.
  function withArgs(node, patch) {
    const sh = node.shape;
    const pos = node.pos;
    const a = node.args.slice();
    const pre = PRE[node.kind];
    if (pre && pre in patch) a[0] = patch[pre];
    let restAt = pos.rest;
    if (sh.dim === 'line') {
      const keys = ['x1', 'y1', 'x2', 'y2'];
      if (keys.some((k) => k in patch)) keys.forEach((k, j) => { a[j] = k in patch ? patch[k] : a[j] === undefined ? [0, 0, 100, 100][j] : a[j]; });
      restAt = 4;
    } else if (sh.dim && ('x' in patch || 'y' in patch || 'z' in patch)) {
      const x = 'x' in patch ? patch.x : pos.x;
      const y = 'y' in patch ? patch.y : pos.y ?? 0;
      const z = 'z' in patch ? patch.z : pos.z;
      let put;
      if (pos.form === 'spot') put = [sh.dim === 2 ? [x, y] : pos.spot === 2 && y === 0 ? [x, z] : [x, y, z]];
      else put = sh.dim === 2 ? [x, y] : [x, y, z];
      if (pre && a[0] === undefined) a[0] = PRE_DEF[pre];
      a.splice(sh.pre, pos.n, ...put);
      restAt = sh.pre + put.length;
    }
    sh.rest.forEach(([k], j) => {
      if (!(k in patch)) return;
      for (let q = 0; q < j; q++) if (a[restAt + q] === undefined) a[restAt + q] = sh.rest[q][1];
      a[restAt + j] = patch[k];
    });
    while (a.length && a[a.length - 1] === undefined) a.pop();
    return a;
  }

  // A thing's line written back: the same text when nothing changed, its inputs in brackets when they did.
  function lineFor(node, args = node.args, name = node.var) {
    const head = name === node.var ? node.call.head : `${name ? `${name} = ` : ''}${node.owner}:${node.kind}${node.call.form === 'bare' ? ' ' : ''}`;
    return callText(node.call, args, { paren: !same(args, node.args), head });
  }

  // Reads the top-level lines of a program the way studio.js parse does (indented lines only for function bodies).
  function parse(code) {
    const lines = String(code ?? '').split(/\r?\n/);
    const P = {
      lines, lineCount: lines.length, importLine: 0, lastImport: 0, other: null, game: null, settings: {}, regs: [], nodes: [],
      byVar: {}, byLine: {}, hud: null, player: null, funcs: [], scoreLine: 0, score: null, loopLine: 0, gameLoop: 0, behaviours: [], busy: new Set(),
    };
    let fn = null;
    for (let i = 0; i < lines.length; i++) {
      const ln = i + 1;
      const full = lines[i];
      const indented = /^\s/.test(full);
      if (fn && (indented || !full.trim())) {
        if (full.trim()) { fn.body.push({ line: ln, indent: full.match(/^[ \t]*/)[0].length, text: full }); fn.end = ln; }
        continue;
      }
      fn = null;
      if (indented || !full.trim()) continue;
      const { code: c, comment } = K.stripComment(full);
      if (!c) continue;
      let m;
      if ((m = c.match(FUNC_RE))) {
        fn = { name: m[1], line: ln, params: m[2].split(',').map((s) => s.trim()).filter(Boolean), end: ln, body: [], mark: MARK_RE.test(lines[i - 1] ?? '') ? ln - 1 : 0 };
        P.funcs.push(fn);
        continue;
      }
      if (ANY_IMPORT_RE.test(c)) {
        P.lastImport = ln;
        if (IMPORT_RE.test(c) && !P.importLine) P.importLine = ln;
        if ((m = c.match(OTHER_RE)) && !P.other) P.other = m[1];
        continue;
      }
      if (!P.loopLine && /^while\b/.test(c)) P.loopLine = ln;
      if (!P.gameLoop && /^while\b/.test(c) && isGameLoop(lines, i, c)) P.gameLoop = ln;
      // What comes after the game's loop runs only once its window has closed: it isn't how the game starts, so it
      // isn't read as a thing's setup, and Inspector edits never touch it (spec §8.2). Functions still count.
      if (P.gameLoop && ln > P.gameLoop) continue;
      if ((m = c.match(GAME_RE))) {
        const call = callOf(full, c, m[3]);
        P.game = { key: 'root', kind: 'game', var: m[1], mode: m[2] === 'world' ? '3d' : '2d', line: ln, comment, call, args: call.vals, text: full };
        P.byVar[m[1]] = P.game;
        continue;
      }
      if (!P.game) continue;
      const G = P.game.var;
      const is3d = P.game.mode === '3d';
      if ((m = c.match(SET_RE)) && m[1] === G) {
        const call = callOf(full, c, m[3]);
        P.settings[m[2]] = { line: ln, call, args: call.vals };
        if (m[2] === 'island' || m[2] === 'ground') P.byLine[ln] = { key: 'root', kind: m[2], floor: true };
        continue;
      }
      if ((m = c.match(REG_RE)) && m[1] === G) {
        const call = callOf(full, c, m[3]);
        const last = call.vals[call.vals.length - 1];
        P.regs.push({ line: ln, owner: 'game', method: m[2], call, args: call.vals, fn: last && last.raw && NAME_RE.test(last.raw) ? last.raw : null });
        continue;
      }
      if ((m = c.match(MAKE_RE))) {
        const [, v, owner, kind, rest] = m;
        let layer = null;
        if (owner === G) { if ((is3d ? K3D : K2D).includes(kind)) layer = kind === 'hud' ? 'hud' : is3d ? 'world' : 'game'; }
        else if (P.hud && owner === P.hud.var && KHUD.includes(kind)) layer = 'hud';
        else if (P.player && P.player.var && owner === P.player.var && kind === 'hold') layer = 'world';
        if (layer) {
          const simple = !rest || (rest.startsWith('(') && K.closesAtEnd(rest)) || !/[:(]/.test(rest);
          if (!simple) { P.busy.add(ln); continue; }
          const call = callOf(full, c, rest);
          if (kind === 'hud') { if (v) P.hud = { var: v, line: ln, call }; continue; }
          if (kind === 'hold') {
            P.player.hold = { line: ln, var: v || null, call, item: typeof call.vals[0] === 'string' ? call.vals[0] : 'axe' };
            continue;
          }
          const node = { key: v ? `v:${v}` : `l:${ln}`, kind, var: v || null, owner, layer, line: ln, comment, call, args: call.vals, props: {}, text: full };
          const before = v && P.byVar[v];
          if (before && P.nodes.includes(before)) before.key = `l:${before.line}`; // a name used again: the newer line has it
          readPos(node);
          P.nodes.push(node);
          P.byLine[ln] = node;
          if (v) P.byVar[v] = node;
          if (kind === 'player') P.player = node;
          continue;
        }
      }
      if ((m = c.match(PROP_RE))) {
        const owner = P.byVar[m[1]];
        if (owner && P.nodes.includes(owner) && FAMILY[family(owner)].includes(m[2]) && (m[2] !== 'align' || owner.kind === 'text') && (m[2] !== 'scale' || owner.kind === 'spawn')) {
          const call = callOf(full, c, m[3]);
          owner.props[m[2]] = { line: ln, call, args: call.vals };
          if (m[2] === 'clicked') {
            const f = call.vals[0];
            P.regs.push({ line: ln, owner: owner.key, node: owner, method: 'clicked', call, args: call.vals, fn: f && f.raw && NAME_RE.test(f.raw) ? f.raw : null });
          }
          continue;
        }
      }
      if (SCORE_RE.test(c)) P.scoreLine = ln;
    }
    if (P.scoreLine) {
      const label = scoreLabel(P);
      if (label) P.score = { line: P.scoreLine, labelVar: label.var, label };
    }
    P.behaviours = recognise(P);
    return P;
  }

  // A top-level while loop is the game's loop when it asks game:open() or calls game:frame(): where tgame's preview
  // stops (a while loop that only sets things up runs to its end, and the setup goes on after it).
  function isGameLoop(lines, i, c) {
    if (/:(?:open|frame)\s*\(/.test(c)) return true;
    for (let j = i + 1; j < lines.length && (/^\s/.test(lines[j]) || !lines[j].trim()); j++) if (/:frame\s*\(/.test(K.stripComment(lines[j]).code)) return true;
    return false;
  }

  const scoreLabel = (P) => P.nodes.find((n) => n.kind === 'text' && n.var && typeof n.args[0] === 'string' && n.args[0].startsWith('Score: ')) || null;

  // ---------------------------------------------------------------- behaviours: the exact code (spec §10)
  // body(p): the function's lines as [level, text]. read(texts, fn): the parameters read back out of a body (texts
  // without indents), or null. A body is recognised when body(read(it)) gives it back, line for line and level for level.
  const ID = /([A-Za-z_]\w*)/.source;
  const RX = (s) => new RegExp(`^${s.replace(/\{ID\}/g, ID)}$`);
  const BEH = {
    arrows: {
      suffix: 'arrows', arg: 'dt', short: 'Moves with the arrow keys',
      desc: (p) => `${p.V} moves with the arrow keys`,
      label: () => 'Moves with the arrow keys',
      body(p) {
        const out = [];
        const moves = { left: `-${num(p.S)} * dt, 0`, right: `${num(p.S)} * dt, 0`, up: `0, -${num(p.S)} * dt`, down: `0, ${num(p.S)} * dt` };
        const keys = p.dirs === 'leftright' ? ['left', 'right'] : p.dirs === 'updown' ? ['up', 'down'] : ['left', 'right', 'up', 'down'];
        for (const k of keys) out.push([1, `if ${p.G}:held("${k}"):`], [2, `${p.V}:move(${moves[k]})`]);
        return out;
      },
      read(L) {
        let G = null;
        let V = null;
        let S = null;
        const keys = new Set();
        for (const t of L) {
          let m;
          if ((m = RX(String.raw`if {ID}:held\("(left|right|up|down)"\):`).exec(t))) { G = m[1]; keys.add(m[2]); }
          else if ((m = RX(String.raw`{ID}:move\(-?([\d.]+) \* dt, 0\)`).exec(t)) || (m = RX(String.raw`{ID}:move\(0, -?([\d.]+) \* dt\)`).exec(t))) { V = m[1]; S = +m[2]; }
        }
        const dirs = keys.size === 4 ? 'all' : keys.size === 2 && keys.has('left') && keys.has('right') ? 'leftright' : keys.size === 2 && keys.has('up') && keys.has('down') ? 'updown' : null;
        return G && V && S && dirs ? { G, V, S, dirs } : null;
      },
    },
    collect: {
      suffix: 'collect', arg: 'dt', short: 'Collect it',
      desc: (p) => `${p.C} collects ${p.V}`,
      label: (p) => `Collect it (by ${p.C}, +${p.P}, ${p.sound})`,
      body(p) {
        return [[1, `if ${p.V}:touches(${p.C}):`], [2, `score += ${num(p.P)}`], [2, `${p.L}:set "Score: " + score`],
          ...(p.sound && p.sound !== 'none' ? [[2, `${p.G}:sound ${JSON.stringify(p.sound)}`]] : []), [2, `${p.V}:move_to(${p.G}:random_spot())`]];
      },
      read(L) {
        const p = { sound: 'none' };
        for (const t of L) {
          let m;
          if ((m = RX(String.raw`if {ID}:touches\({ID}\):`).exec(t))) { p.V = m[1]; p.C = m[2]; }
          else if ((m = /^score \+= (\d+)$/.exec(t))) p.P = +m[1];
          else if ((m = RX(String.raw`{ID}:set "Score: " \+ score`).exec(t))) p.L = m[1];
          else if ((m = RX(String.raw`{ID}:sound "([^"\\]*)"`).exec(t))) p.sound = m[2];
          else if ((m = RX(String.raw`{ID}:move_to\({ID}:random_spot\(\)\)`).exec(t))) p.G = m[2];
        }
        return p.V && p.C && p.P && p.L && p.G ? p : null;
      },
    },
    chase: {
      suffix: 'chase', arg: 'dt', short: 'Chases',
      desc: (p) => `${p.V} chases ${p.T}`,
      label: (p) => `Chases ${p.T} (speed ${num(p.S)})`,
      body: (p) => [[1, `${p.V}:${p.look ? 'look_at' : 'point_at'}(${p.T})`], [1, `${p.V}:forward(${num(p.S)} * dt)`]],
      read(L) {
        const p = {};
        for (const t of L) {
          let m;
          if ((m = RX(String.raw`{ID}:(point_at|look_at)\({ID}\)`).exec(t))) { p.V = m[1]; p.look = m[2] === 'look_at'; p.T = m[3]; }
          else if ((m = RX(String.raw`{ID}:forward\(([\d.]+) \* dt\)`).exec(t))) p.S = +m[2];
        }
        return p.V && p.T && p.S ? p : null;
      },
    },
    hurts: {
      suffix: 'hurts', arg: 'dt', short: 'Game over',
      desc: (p) => `game over when ${p.V} touches ${p.T}`,
      label: (p) => `Game over when it touches ${p.T}`,
      body(p) {
        return [[1, `if ${p.V}:touches(${p.T}) and not ${p.G}:paused():`], ...(p.sound && p.sound !== 'none' ? [[2, `${p.G}:sound ${JSON.stringify(p.sound)}`]] : []),
          [2, p.scored ? `${p.G}:game_over("Score: " + score, ${p.PA})` : `${p.G}:game_over("Try again!", ${p.PA})`]];
      },
      read(L) {
        const p = { sound: 'none' };
        for (const t of L) {
          let m;
          if ((m = RX(String.raw`if {ID}:touches\({ID}\) and not {ID}:paused\(\):`).exec(t))) { p.V = m[1]; p.T = m[2]; p.G = m[3]; }
          else if ((m = RX(String.raw`{ID}:sound "([^"\\]*)"`).exec(t))) p.sound = m[2];
          else if ((m = RX(String.raw`{ID}:game_over\("Score: " \+ score, {ID}\)`).exec(t))) { p.PA = m[2]; p.scored = true; }
          else if ((m = RX(String.raw`{ID}:game_over\("Try again!", {ID}\)`).exec(t))) { p.PA = m[2]; p.scored = false; }
        }
        return p.V && p.T && p.G && p.PA ? p : null;
      },
    },
    falls: {
      suffix: 'chop', arg: 'thing', short: 'Falls over',
      desc: (p) => `${p.V} falls over when clicked`,
      label: (p) => `Falls over when clicked (grows back in ${num(p.secs)} s)`,
      body: (p) => [[1, `if not ${p.T}:fallen():`], [2, `${p.T}:shake()`], [2, `${p.T}:fall()`], [2, `${p.T}:regrow(${num(p.secs)})`]],
      read(L, fn) {
        let secs = null;
        for (const t of L) { const m = RX(String.raw`{ID}:regrow\(([\d.]+)\)`).exec(t); if (m) secs = +m[2]; }
        return fn.params[0] && secs ? { T: fn.params[0], secs } : null;
      },
    },
  };
  const PA_MARK = '# Tuff Engine: play again after a game over';
  const PA_LINE = /^(?:score = 0|[A-Za-z_]\w*:set "Score: 0"|[A-Za-z_]\w*:move_to\(-?[\d.]+(?:, -?[\d.]+){1,2}\)|return)$/;

  // A function body as "level|text" lines, ignoring blank and comment lines (levels count up from the first line's indent).
  function levels(fn) {
    const rows = fn.body.map((b) => ({ indent: b.indent, code: K.stripComment(b.text).code.trim() })).filter((b) => b.code);
    const indents = [...new Set(rows.map((r) => r.indent))].sort((a, b) => a - b);
    return rows.map((r) => `${indents.indexOf(r.indent) + 1}|${r.code}`);
  }
  const bodyLines = (type, p) => BEH[type].body(p).map(([l, t]) => `${'    '.repeat(l)}${t}`);

  function recognise(P) {
    const out = [];
    const seen = new Set();
    const fnBy = new Map(P.funcs.map((f) => [f.name, f]));
    for (const reg of P.regs) {
      const f = reg.fn && fnBy.get(reg.fn);
      if (!f || f.params.length !== 1) continue;
      const types = reg.owner === 'game' && reg.method === 'every_frame' ? ['arrows', 'collect', 'chase', 'hurts'] : reg.node && reg.method === 'clicked' ? ['falls'] : [];
      if (!types.length) continue;
      const lv = levels(f);
      const texts = lv.map((x) => x.slice(x.indexOf('|') + 1));
      for (const type of types) {
        const p = BEH[type].read(texts, f);
        if (!p) continue;
        if (type === 'falls') p.V = reg.node.var;
        if (!same(lv, BEH[type].body(p).map(([l, t]) => `${l}|${t}`))) continue;
        const node = type === 'falls' ? reg.node : P.byVar[p.V];
        if (!node || !P.nodes.includes(node) || seen.has(`${type}:${f.name}`)) break;
        seen.add(`${type}:${f.name}`);
        out.push({ id: `${type}:${f.name}`, type, reg, fn: f, p, node, V: p.V });
        break;
      }
    }
    return out;
  }

  // Which play_again line a line is: the thing a move_to moves (its spot changes), or the line itself.
  const paKey = (code) => code.replace(/^([A-Za-z_]\w*:move_to)\(.*$/, '$1');

  function ownedPlayAgain(P, f) {
    return !!(f && f.mark && P.lines[f.mark - 1].trim() === PA_MARK && f.body.every((b) => PA_LINE.test(K.stripComment(b.text).code.trim())));
  }

  function playerStart(P) {
    const a = P.player?.props.move_to?.args || [];
    if (Array.isArray(a[0])) return a[0].length === 2 ? [a[0][0], a[0][1]] : [a[0][0], a[0][2]];
    return isNum(a[0]) && isNum(a[2]) ? [a[0], a[2]] : [0, 0];
  }

  // What play_again does: the Score back to 0, and every thing with a behaviour back where it started.
  function playAgainBody(P) {
    const out = [];
    if (P.score) out.push('score = 0', `${P.score.labelVar}:set "Score: 0"`);
    if (P.game.mode === '3d' && P.player?.var && P.behaviours.some((b) => b.type === 'hurts')) {
      const [sx, sz] = playerStart(P);
      out.push(`${P.player.var}:move_to(${num(sx)}, 0, ${num(sz)})`);
    }
    const moving = new Set(P.behaviours.filter((b) => ['arrows', 'collect', 'chase', 'hurts'].includes(b.type)).map((b) => b.V));
    for (const n of P.nodes) {
      if (!n.var || !moving.has(n.var) || n.kind === 'player' || n.kind === 'line' || !['xy', 'spot'].includes(n.pos.form)) continue;
      out.push(n.layer === 'world' ? `${n.var}:move_to(${num(n.pos.x)}, ${num(n.pos.y)}, ${num(n.pos.z)})` : `${n.var}:move_to(${num(n.pos.x)}, ${num(n.pos.y)})`);
    }
    return out.length ? out : ['return'];
  }

  // A block of lines at the end of the file: after a blank line, and before the file's last newline.
  function appendBlock(lines, block) {
    const out = lines.slice();
    const nl = out.length > 1 && out[out.length - 1] === '';
    const end = nl ? out.length - 1 : out.length;
    const blank = end === 0 || !out[end - 1].trim();
    out.splice(end, 0, ...(blank ? [] : ['']), ...block);
    return out;
  }

  // Keeps the code the Engine owns right, as the last step of every Engine edit (inside the same undo step):
  // play_again exists while a "game over" behaviour does (and its body follows where things start), and each
  // "# Tuff Engine:" comment above a recognised behaviour says what it does now (renames skip comments).
  // A pure function of the lines; code typed in the code tab is only touched by the next Engine edit.
  function fixups(lines) {
    const P = parse(lines.join('\n'));
    if (!P.game) return lines;
    const rep = new Map();
    const del = new Set();
    const after = new Map();
    let tail = null;
    const hurts = P.behaviours.filter((b) => b.type === 'hurts');
    if (hurts.length) {
      const name = hurts[0].p.PA;
      const f = P.funcs.find((x) => x.name === name);
      if (!f) tail = [PA_MARK, `func ${name}():`, ...playAgainBody(P).map((t) => `    ${t}`)];
      else if (ownedPlayAgain(P, f)) {
        // Written again only when it changes, in its own indent, and each line keeps the comment at its end (found by
        // what the line is: score = 0, the label's set, or which thing it moves).
        const ind = f.body[0]?.text.match(/^[ \t]*/)[0] || '    ';
        const tails = new Map(f.body.map((b) => { const { code } = K.stripComment(b.text); return [paKey(code.trim()), b.text.slice(code.length)]; }));
        const body = playAgainBody(P).map((t) => `${ind}${t}${tails.get(paKey(t)) || ''}`);
        if (!same(f.body.map((b) => b.text), body)) {
          for (const l of range(f.line + 1, f.end)) del.add(l);
          after.set(f.line, body);
        }
      }
    } else {
      for (const f of P.funcs) {
        if (!ownedPlayAgain(P, f)) continue;
        const own = new Set([f.mark, ...range(f.line, f.end)]);
        const word = wordRe(f.name);
        if (lines.some((l, i) => !own.has(i + 1) && word.test(K.stripComment(l).code))) continue;
        for (const l of own) del.add(l);
        if (f.mark > 1 && !lines[f.mark - 2].trim()) del.add(f.mark - 1);
      }
    }
    for (const b of P.behaviours) {
      if (!b.fn.mark) continue;
      const want = `# Tuff Engine: ${BEH[b.type].desc(b.p)}`;
      if (lines[b.fn.mark - 1] !== want) rep.set(b.fn.mark, want);
    }
    if (!rep.size && !del.size && !after.size && !tail) return lines;
    let out = [];
    lines.forEach((t, i) => {
      const ln = i + 1;
      if (!del.has(ln)) out.push(rep.has(ln) ? rep.get(ln) : t);
      if (after.has(ln)) out.push(...after.get(ln));
    });
    if (tail) out = appendBlock(out, tail);
    return out;
  }

  // Where new lines go (spec §11.1): setupEnd (things), settingsEnd (settings, the HUD, the Score), regEnd (registrations).
  function anchors(P) {
    const before = (l) => l > 0 && (!P.loopLine || l < P.loopLine);
    const settings = Object.values(P.settings).map((s) => s.line).filter(before);
    const setup = [P.importLine, P.game?.line, ...settings, P.hud?.line, P.scoreLine, P.player?.hold?.line];
    for (const n of P.nodes) setup.push(n.line, ...Object.values(n.props).map((p) => p.line));
    return {
      setupEnd: Math.max(0, ...setup.filter(before)),
      settingsEnd: Math.max(P.game?.line || 0, ...settings),
      regEnd: Math.max(0, ...P.regs.filter((r) => r.owner === 'game').map((r) => r.line).filter(before)),
    };
  }
  const ownLast = (node) => Math.max(node.line, ...Object.values(node.props).map((p) => p.line), node.hold?.line || 0);

  function gameSize(P, d = null) {
    if (d && Array.isArray(d.size) && d.mode === P.game?.mode) return d.size;
    const g = P.game;
    const is3d = g?.mode === '3d';
    const w = isNum(g?.args[1]) ? g.args[1] : is3d ? 960 : 800;
    const h = isNum(g?.args[2]) ? g.args[2] : 600;
    return [w, h];
  }

  function find(P, key) {
    if (!key || !P.game) return null;
    if (key === 'root') return P.game;
    if (key.startsWith('v:')) { const n = P.byVar[key.slice(2)]; return n && P.nodes.includes(n) && n.key === key ? n : null; }
    if (key.startsWith('l:')) { const n = P.byLine[+key.slice(2)]; return n && P.nodes.includes(n) ? n : null; }
    return null;
  }

  // ---------------------------------------------------------------- writing edits (spec §11)
  function namer(P) {
    const taken = K.takenNames(P, P.lines.join('\n'));
    for (const k of [...KEYWORDS(), ...BUILTINS, ...LIBS]) taken.add(k);
    return (base) => {
      let b = String(base).replace(/\W+/g, '_').replace(/^(\d)/, 'pic_$1') || 'thing';
      if (!NAME_RE.test(b)) b = `thing_${b}`;
      let name = b;
      for (let i = 1; taken.has(name); i++) name = `${b}${i}`;
      taken.add(name);
      return name;
    };
  }

  function commit(ed, blocks = []) {
    return ed.commit((lines) => fixups(blocks.reduce(appendBlock, lines)));
  }

  const BASE = { box: 'box', circle: 'circle', line: 'line', text: 'words', image: 'picture', sphere: 'ball', cylinder: 'cylinder', cone: 'cone', plane: 'plane', spawn: 'thing', light: 'lamp', player: 'player' };
  const baseFor = (n) => (n.kind === 'spawn' && typeof n.args[0] === 'string' ? n.args[0].replace(/\.glb$/i, '').split(/[\\/]/).pop() : BASE[n.kind] || 'thing');

  // An edit in progress: one makeEditor, names that stay free inside it, and what goes at the end of the file.
  function plan(P) {
    const ed = K.makeEditor(S.model);
    const nm = namer(P);
    const A = anchors(P);
    const G = P.game?.var;
    const is3d = P.game?.mode === '3d';
    const [W] = gameSize(P);
    const pl = { P, ed, nm, A, G, is3d, blocks: [], regs: [], hud: P.hud?.var || null, label: P.score?.labelVar || null, scored: !!P.score };
    pl.needHud = () => {
      if (!pl.hud) { pl.hud = nm('hud'); ed.insertAfter(A.settingsEnd, `${pl.hud} = ${G}:hud()`); }
      return pl.hud;
    };
    pl.needScore = () => {
      if (P.score || pl.scored) return;
      if (is3d) pl.needHud();
      const out = [];
      if (!P.scoreLine) out.push('score = 0');
      const have = scoreLabel(P);
      if (have) pl.label = have.var;
      else {
        pl.label = nm('score_label');
        out.push(is3d ? `${pl.label} = ${pl.hud}:text("Score: 0", 90, 30, 26, "white")` : `${pl.label} = ${G}:text("Score: 0", ${Math.round(W / 2)}, 30, 24, "white")`);
      }
      if (out.length) ed.insertAfter(Math.max(A.settingsEnd, P.hud?.line || 0), out.join('\n'));
      pl.scored = true;
    };
    pl.playAgain = () => P.behaviours.find((b) => b.type === 'hurts')?.p.PA || (P.funcs.some((f) => f.name === 'play_again') ? 'play_again' : nm('play_again'));
    // A behaviour's function (at the end of the file) and its registration. falls is registered by a prop line
    // (V:clicked V_chop), which it gives back for the caller to put with V's lines.
    pl.beh = (type, V, params) => {
      const fn = nm(`${V}_${BEH[type].suffix}`);
      const p = { ...params, V, G };
      if (type === 'falls') p.T = p.T || 'thing';
      if (type === 'chase') p.look = is3d;
      if (type === 'hurts') { p.PA = p.PA || pl.playAgain(); p.scored = p.scored ?? pl.scored; }
      if (type === 'collect') { pl.needScore(); p.L = pl.label; }
      pl.blocks.push([`# Tuff Engine: ${BEH[type].desc(p)}`, `func ${fn}(${type === 'falls' ? p.T : BEH[type].arg}):`, ...bodyLines(type, p)]);
      if (type === 'falls') return `${V}:clicked ${fn}`;
      pl.regs.push(`${G}:every_frame ${fn}`);
      return null;
    };
    pl.reg = (line) => pl.regs.push(line);
    pl.done = () => {
      if (pl.regs.length) ed.insertAfter(A.regEnd || A.setupEnd, (A.regEnd ? '' : '\n') + pl.regs.join('\n'));
      return commit(ed, pl.blocks);
    };
    return pl;
  }

  // Gives an unnamed thing a name (name = in front of its line), inside the edit; the name is kept on the node so a
  // line rewritten in the same edit keeps it.
  function ensureVar(pl, node) {
    if (node.var || node._var) return node.var || node._var;
    node._var = pl.nm(baseFor(node));
    pl.ed.replace(node.line, lineFor(node, node._args || node.args, node._var));
    return node._var;
  }
  function setNodeArgs(pl, node, args) {
    node._args = args;
    pl.ed.replace(node.line, lineFor(node, args, node._var || node.var));
  }

  const PROP_OFF = {
    speed: (a) => a.every((v) => v === 0), spin: (a) => a[0] === 0, on_edge: (a) => a[0] === 'none', layer: (a) => a[0] === 0, turn_to: (a) => a[0] === 0,
    label: (a) => a[0] === '', glow: (a) => a[0] === '' || a[0] === 'none', solid: (a) => a[0] === true, align: (a) => a[0] === 'center', scale: (a) => a[0] === 1,
    walk_speed: (a) => a[0] === 5, jump_height: (a) => a[0] === 1.2,
  };
  const propLine = (V, method, args) => (!args.length ? `${V}:${method}()` : args.length === 1 ? `${V}:${method} ${fmt(args[0])}` : `${V}:${method}(${args.map(fmt).join(', ')})`);

  // A prop line (coin:spin 90): replaced where it is, or put after the thing's own lines; a default value removes it.
  function propEdit(pl, node, method, args) {
    const p = node.props[method];
    if (args === null || PROP_OFF[method]?.(args)) { if (p) pl.ed.remove(p.line); return; }
    const V = ensureVar(pl, node);
    if (p) pl.ed.replace(p.line, callText(p.call, args));
    else pl.ed.insertAfter(ownLast(node), propLine(V, method, args));
  }

  function settingLine(G, method, args) {
    if (method === 'island' || method === 'ground') return `${G}:${method}(${args.map(fmt).join(', ')})`;
    return propLine(G, method, args);
  }
  function settingEdit(pl, method, args) {
    const s = pl.P.settings[method];
    if (args === null) { if (s) pl.ed.remove(s.line); return; }
    if (s) pl.ed.replace(s.line, callText(s.call, args));
    else pl.ed.insertAfter(pl.A.settingsEnd, settingLine(pl.G, method, args));
  }

  // A behaviour's function body changed to want ([level, text] rows), line by line: comment lines, blank lines and the
  // comments at the ends of lines stay as they are (spec §8.2), and so does each line's own indent. The code lines
  // that stay the same are found first; between them, old and new lines pair up in order (a new speed changes a line
  // where it is), and what's left over goes (Left/right only: the up and down lines) or comes in after the line before.
  function rewriteBody(pl, fn, want) {
    const rows = fn.body.map((b) => {
      const { code } = K.stripComment(b.text);
      return { line: b.line, indent: b.text.match(/^[ \t]*/)[0], code: code.trim(), tail: b.text.slice(code.length) };
    }).filter((r) => r.code);
    const widths = [...new Set(rows.map((r) => r.indent.length))].sort((a, b) => a - b);
    rows.forEach((r) => { r.level = widths.indexOf(r.indent.length) + 1; });
    const indentFor = (level) => rows.find((r) => r.level === level)?.indent ?? '    '.repeat(level);
    const a = rows.map((r) => `${r.level}|${r.code}`);
    const b = want.map(([l, t]) => `${l}|${t}`);
    // The longest run of lines that stay (a and b are a few lines each).
    const L = a.map(() => new Array(b.length + 1).fill(0));
    L.push(new Array(b.length + 1).fill(0));
    for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const keep = [];
    for (let i = 0, j = 0; i < a.length && j < b.length;) {
      if (a[i] === b[j]) { keep.push([i, j]); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
    }
    keep.push([a.length, b.length]);
    let prev = fn.line;
    let i = 0;
    let j = 0;
    for (const [ki, kj] of keep) {
      for (; i < ki && j < kj; i++, j++) {
        const r = rows[i];
        const [level, text] = want[j];
        pl.ed.replace(r.line, `${level === r.level ? r.indent : indentFor(level)}${text}${r.tail}`);
        prev = r.line;
      }
      for (; i < ki; i++) pl.ed.remove(rows[i].line);
      for (; j < kj; j++) pl.ed.insertAfter(prev, `${indentFor(want[j][0])}${want[j][1]}`);
      if (ki < rows.length) prev = rows[ki].line;
      i = ki + 1;
      j = kj + 1;
    }
  }

  // The lines of a behaviour: its registration, the Engine comment, the function, and the blank line before them.
  function behLines(P, b) {
    const out = [b.reg.line, ...range(b.fn.line, b.fn.end)];
    if (b.fn.mark) out.push(b.fn.mark);
    const top = b.fn.mark || b.fn.line;
    if (top > 1 && !P.lines[top - 2].trim()) out.push(top - 1);
    return out;
  }

  function freeSpot2(P, x, y, layer = 'game') {
    for (let i = 0; i < 10 && P.nodes.some((n) => n.layer === layer && n.pos.x === x && n.pos.y === y); i++) { x += 30; y += 30; }
    return [x, y];
  }
  function freeSpot3(P, x, z) {
    for (let i = 0; i < 10 && P.nodes.some((n) => n.layer === 'world' && n.pos.x === x && n.pos.z === z); i++) x += 1.5;
    return [x, z];
  }
  const snap = (v, s = 0.5) => { const r = Math.round(v / s) * s; return +r.toFixed(2) || 0; };
  const firstMover = (P) => P.behaviours.find((b) => b.type === 'arrows' && b.node.var)?.V || null;
  const target3 = (P) => P.player?.var || null;

  const KIT_NATURE = ['tree', 'pine', 'rock', 'bush', 'flower'];
  const KIT_BUILDINGS = ['house', 'hut', 'sign', 'crate', 'fence'];
  const SHAPES3 = { box: ['box', 'box', 'orange'], ball: ['sphere', 'ball', 'teal'], cylinder: ['cylinder', 'cylinder', 'gray'], cone: ['cone', 'cone', 'red'], plane: ['plane', 'plane', 'sand'] };

  const Edits = {
    // A tile from Add (spec §9.1, §9.2): its lines, its behaviours and what it needs, as one undo step. Gives the new key.
    add(P, id) {
      if (!P.game) return null;
      const pl = plan(P);
      const { G, nm, is3d } = pl;
      const [W, H] = gameSize(P);
      const r = Math.round;
      let lines = null;
      let V = null;
      let say = null;
      const put = (name, first, ...more) => { V = name; lines = [first, ...more]; };
      if (!is3d) {
        switch (id) {
          case 'player': {
            const n = nm('player');
            const [x, y] = freeSpot2(P, r(W / 2), r(H - 80));
            put(n, `${n} = ${G}:box(${x}, ${y}, 50, 50, "lime")`, `${n}:on_edge "stop"`);
            pl.beh('arrows', n, { S: 300, dirs: 'all' });
            break;
          }
          case 'coin': {
            const C = firstMover(P);
            const n = nm('coin');
            const [x, y] = freeSpot2(P, r(W / 4), r(H / 3));
            if (C) pl.needScore();
            put(n, `${n} = ${G}:circle(${x}, ${y}, 14, "gold")`);
            if (C) pl.beh('collect', n, { C, P: 1, sound: 'coin' });
            else say = 'Add a Player so the coin can be collected.';
            break;
          }
          case 'enemy': {
            const T = firstMover(P);
            const n = nm('enemy');
            const [x, y] = freeSpot2(P, r(W / 8), 80);
            put(n, `${n} = ${G}:box(${x}, ${y}, 40, 40, "red")`);
            if (T) { pl.beh('chase', n, { T, S: 120 }); pl.beh('hurts', n, { T, sound: 'lose' }); }
            else say = 'Add a Player first: the enemy needs someone to chase.';
            break;
          }
          case 'ball': {
            const n = nm('ball');
            const [x, y] = freeSpot2(P, r((3 * W) / 4), r(H / 2));
            put(n, `${n} = ${G}:circle(${x}, ${y}, 12, "white")`, `${n}:speed(200, 150)`, `${n}:on_edge "bounce"`);
            break;
          }
          case 'score': pl.needScore(); pl.done(); return pl.label ? `v:${pl.label}` : null;
          case 'box': case 'circle': case 'line': case 'text': {
            const [x, y] = freeSpot2(P, r(W / 2), r(H / 2));
            const n = nm(id === 'text' ? 'words' : id);
            if (id === 'box') put(n, `${n} = ${G}:box(${x}, ${y}, 40, 40, "orange")`);
            if (id === 'circle') put(n, `${n} = ${G}:circle(${x}, ${y}, 20, "teal")`);
            if (id === 'line') put(n, `${n} = ${G}:line(${x - 50}, ${y}, ${x + 50}, ${y}, "white")`);
            if (id === 'text') put(n, `${n} = ${G}:text("Hello!", ${x}, ${y}, 32, "white")`);
            break;
          }
          default: break;
        }
      } else {
        const cam = S.cams.get(S.file) || { tx: 0, tz: -6 };
        const [X, Z] = freeSpot3(P, snap(cam.tx), snap(cam.tz));
        switch (id) {
          case 'player':
            if (P.player) { ide.toast('This world has a player already. A world can have one.'); return null; }
            put(nm('player'), '');
            lines = [`${V} = ${G}:player("first person")`];
            break;
          case 'coin': {
            const T = target3(P);
            const n = nm('coin');
            const [x, z] = freeSpot3(P, 4, -8);
            if (T) pl.needScore();
            put(n, `${n} = ${G}:spawn("coin", ${num(x)}, 0, ${num(z)})`, `${n}:spin 90`);
            if (T) pl.beh('collect', n, { C: T, P: 1, sound: 'coin' });
            else say = 'Add a Player so the coin can be collected.';
            break;
          }
          case 'enemy': {
            const T = target3(P);
            const n = nm('enemy');
            const [x, z] = freeSpot3(P, -12, -20);
            put(n, `${n} = ${G}:box(${num(x)}, 0, ${num(z)}, 1, "red")`, `${n}:solid false`);
            if (T) { pl.beh('chase', n, { T, S: 2 }); pl.beh('hurts', n, { T, sound: 'lose' }); }
            else say = 'Add a Player first: the enemy needs someone to chase.';
            break;
          }
          case 'chop': {
            const n = nm('tree');
            const [x, z] = freeSpot3(P, -5, -10);
            put(n, `${n} = ${G}:spawn("tree", ${num(x)}, 0, ${num(z)})`);
            lines.push(pl.beh('falls', n, { secs: 5 }));
            break;
          }
          case 'score': pl.needScore(); pl.done(); return pl.label ? `v:${pl.label}` : null;
          case 'light': put(nm('lamp'), ''); lines = [`${V} = ${G}:light(${num(X)}, 3, ${num(Z)}, "gold")`]; break;
          case 'island': case 'ground':
            if (P.settings.island || P.settings.ground) return null;
            settingEdit(pl, id, id === 'island' ? [80] : ['grass', 400]);
            pl.done();
            return 'root';
          default:
            if (KIT_NATURE.includes(id) || KIT_BUILDINGS.includes(id)) { put(nm(id), ''); lines = [`${V} = ${G}:spawn("${id}", ${num(X)}, 0, ${num(Z)})`]; }
            else if (SHAPES3[id]) {
              const [kind, base, color] = SHAPES3[id];
              put(nm(base), '');
              lines = [`${V} = ${G}:${kind}(${num(X)}, 0, ${num(Z)}, ${kind === 'plane' ? 4 : 1}, "${color}")`];
            }
            break;
        }
      }
      if (id === 'hudtext' || id === 'hudbox') {
        const hud = pl.needHud();
        const n = nm(id === 'hudtext' ? 'hud_text' : 'bar');
        put(n, id === 'hudtext' ? `${n} = ${hud}:text("Lives: 3", 90, 30, 22, "white")` : `${n} = ${hud}:box(${r(W / 2)}, ${r(H - 20)}, 200, 16, "green")`);
      } else if (id.startsWith('pic:')) {
        const rel = id.slice(4);
        const n = nm(rel.split('/').pop().replace(/\.[^.]+$/, ''));
        const wide = (S.picSize.get(rel)?.[0] || 0) > 160;
        if (is3d) {
          const hud = pl.needHud();
          put(n, `${n} = ${hud}:image(${JSON.stringify(rel)}, 90, 90${wide ? ', 128' : ''})`);
        } else {
          const [x, y] = freeSpot2(P, r(W / 2), r(H / 2));
          put(n, `${n} = ${G}:image(${JSON.stringify(rel)}, ${x}, ${y}${wide ? ', 128' : ''})`);
        }
      } else if (id.startsWith('glb:') && is3d) {
        const rel = id.slice(4);
        const cam = S.cams.get(S.file) || { tx: 0, tz: -6 };
        const [x, z] = freeSpot3(P, snap(cam.tx), snap(cam.tz));
        const n = nm(rel.split('/').pop().replace(/\.[^.]+$/, ''));
        put(n, `${n} = ${G}:spawn(${JSON.stringify(rel)}, ${num(x)}, 0, ${num(z)})`);
      }
      if (!lines) return null;
      pl.ed.insertAfter(pl.A.setupEnd, lines.filter((l) => l !== null).join('\n'));
      pl.done();
      if (say) ide.toast(say, 'info', 4500);
      return `v:${V}`;
    },

    // Moves a thing (a drag, the arrow keys, the X and Y fields): 2D by dx, dy (a line moves all four numbers),
    // 3D to x, z; patch can also name fields (x, y, w, color...).
    setArgs(P, node, patch) {
      const pl = plan(P);
      setNodeArgs(pl, node, withArgs(node, patch));
      pl.done();
      return node.key;
    },

    setGame(P, patch) {
      const g = P.game;
      const pl = plan(P);
      const is3d = g.mode === '3d';
      const a = g.args.slice();
      const def = [is3d ? 'My World' : 'My Game', is3d ? 960 : 800, 600];
      ['title', 'width', 'height'].forEach((k, i) => {
        if (!(k in patch)) return;
        for (let q = 0; q < i; q++) if (a[q] === undefined) a[q] = def[q];
        a[i] = patch[k];
      });
      pl.ed.replace(g.line, callText(g.call, a, { paren: true }));
      pl.done();
      return 'root';
    },

    setProp(P, node, method, args, extra = null) {
      const pl = plan(P);
      propEdit(pl, node, method, args);
      if (extra) for (const [m, a] of extra) propEdit(pl, node, m, a);
      pl.done();
      return node._var ? `v:${node._var}` : node.key;
    },

    setSetting(P, changes) {
      const pl = plan(P);
      for (const [method, args] of changes) settingEdit(pl, method, args);
      pl.done();
      return 'root';
    },

    setHold(P, item) {
      const player = P.player;
      if (!player) return null;
      const pl = plan(P);
      const h = player.hold;
      if (!item) { if (h) pl.ed.remove(h.line); }
      else if (h) pl.ed.replace(h.line, callText(h.call, [item]));
      else {
        const V = ensureVar(pl, player);
        pl.ed.insertAfter(ownLast(player), `${pl.nm(item)} = ${V}:hold(${JSON.stringify(item)})`);
      }
      pl.done();
      return player._var ? `v:${player._var}` : player.key;
    },

    duplicate(P, node) {
      if (node.kind === 'player') { ide.toast('A world can have one player.'); return null; }
      const pl = plan(P);
      const N = pl.nm(node.var || baseFor(node));
      const map = node.var ? { [node.var]: N } : {};
      for (const b of P.behaviours.filter((x) => x.node === node)) {
        const fn = pl.nm(`${N}_${BEH[b.type].suffix}`);
        map[b.fn.name] = fn;
        const p = { ...b.p, V: N };
        pl.blocks.push([`# Tuff Engine: ${BEH[b.type].desc(p)}`, `func ${fn}(${b.fn.params[0]}):`, ...bodyLines(b.type, p)]);
        if (b.type !== 'falls') pl.reg(`${pl.G}:every_frame ${fn}`);
      }
      const q = node.pos;
      let args = node.args;
      if (node.kind === 'line' && q.form === 'line') args = withArgs(node, { x1: q.x1 + 30, y1: q.y1 + 30, x2: q.x2 + 30, y2: q.y2 + 30 });
      else if (['xy', 'spot'].includes(q.form)) args = withArgs(node, node.layer === 'world' ? { x: q.x + 2 } : { x: q.x + 30, y: q.y + 30 });
      const props = Object.values(node.props).sort((a, b) => a.line - b.line).map((p) => K.renameIdents(P.lines[p.line - 1], map));
      pl.ed.insertAfter(ownLast(node), [lineFor(node, args, N), ...props].join('\n'));
      pl.done();
      return `v:${N}`;
    },

    // Deletes a thing: its lines, its behaviours, and other things' behaviours that need it (collect by, chase, game over).
    remove(P, node) {
      const sc = P.score && P.score.label === node;
      if (sc) {
        const user = P.behaviours.find((b) => b.type === 'collect' || (b.type === 'hurts' && b.p.scored));
        if (user) { ide.toast(`${cap(user.V)}'s ${BEH[user.type].short} uses the score. Remove that first.`, 'error', 5000); return null; }
      }
      const pl = plan(P);
      const gone = new Set();
      const del = (l) => { if (l && !gone.has(l)) { gone.add(l); pl.ed.remove(l); } };
      del(node.line);
      for (const p of Object.values(node.props)) del(p.line);
      if (node.hold) del(node.hold.line);
      if (sc) del(P.scoreLine);
      const own = P.behaviours.filter((b) => b.node === node);
      const needs = node.var ? P.behaviours.filter((b) => b.node !== node && ((b.type === 'collect' && b.p.C === node.var) || ((b.type === 'chase' || b.type === 'hurts') && b.p.T === node.var))) : [];
      for (const b of [...own, ...needs]) behLines(P, b).forEach(del);
      pl.done();
      const name = node.var || KIND_LABEL(node).toLowerCase();
      const still = node.var && S.model.getLinesContent().some((l) => wordRe(node.var).test(K.stripComment(l).code));
      if (still) ide.toast(`Removed. Some code still mentions ${node.var}. Check the red marks when you run.`, 'error', 5000);
      else if (needs.length) {
        const by = new Map();
        for (const b of needs) { if (!by.has(b.V)) by.set(b.V, []); by.get(b.V).push(BEH[b.type].short); }
        const parts = [...by].map(([v, s]) => `${v}'s ${s.join(' and ')}`);
        ide.toast(`Removed ${name}, and ${parts.join(' and ')}, which needed it. Ctrl+Z brings it back.`, 'info', 5000);
      } else ide.toast(`Removed ${name}. Ctrl+Z brings it back.`, 'info', 3000);
      return 'root';
    },

    rename(P, node, name) {
      const pl = plan(P);
      if (!node.var) pl.ed.replace(node.line, lineFor(node, node.args, name));
      else {
        const map = { [node.var]: name };
        P.lines.forEach((l, i) => { const n = K.renameIdents(l, map); if (n !== l) pl.ed.replace(i + 1, n); });
      }
      pl.done();
      return `v:${name}`;
    },

    addBehaviour(P, node, type, params) {
      const pl = plan(P);
      const V = ensureVar(pl, node);
      if (type === 'arrows' && !node.props.on_edge) propEdit(pl, node, 'on_edge', ['stop']);
      const prop = pl.beh(type, V, params);
      if (prop) {
        if (node.props.clicked) pl.ed.replace(node.props.clicked.line, prop);
        else pl.ed.insertAfter(ownLast(node), prop);
      }
      pl.done();
      return `v:${V}`;
    },

    // A behaviour's parameters changed: only the lines of its function that change are written again.
    setBehaviour(P, b, params) {
      const pl = plan(P);
      rewriteBody(pl, b.fn, BEH[b.type].body({ ...b.p, ...params }));
      pl.done();
      return b.node.key;
    },

    removeBehaviour(P, b) {
      const pl = plan(P);
      new Set(behLines(P, b)).forEach((l) => pl.ed.remove(l));
      pl.done();
      return b.node.key;
    },

    removeReg(P, reg) {
      const pl = plan(P);
      pl.ed.remove(reg.line);
      pl.done();
      if (reg.fn) ide.toast(`func ${reg.fn}() is still in your code.`, 'info', 3500);
    },

    // Events (spec §10.4). slot: { type: 'click', node } | { type: 'key', reg?, key } | { type: 'every', reg?, n } |
    // { type: 'gameclick', reg? }. value: a function's name, '' (nothing) or '+new' (a new function, in the same step).
    setEvent(P, slot, value, change = {}) {
      const pl = plan(P);
      const { G, is3d } = pl;
      let fn = value;
      const key = change.key ?? slot.key;
      const n = change.n ?? slot.n;
      if (value === '+new') {
        if (slot.type === 'click') {
          const V = ensureVar(pl, slot.node);
          fn = pl.nm(`${V}_clicked`);
          pl.blocks.push([`func ${fn}(thing):`, '    thing:shake()', `    ${G}:sound "pop"`]);
        } else if (slot.type === 'key') {
          fn = pl.nm(key === 'any' ? 'on_any_key' : `on_${key}`);
          pl.blocks.push([`func ${fn}(key):`, '    say "You pressed " + key']);
        } else if (slot.type === 'every') {
          fn = pl.nm(n === 1 ? 'every_second' : `every_${num(n).replace('.', '_')}_seconds`);
          pl.blocks.push([`func ${fn}():`, '    say "tick"']);
        } else if (slot.type === 'gameclick') {
          fn = pl.nm('game_clicked');
          pl.blocks.push(is3d ? [`func ${fn}(x, y, z):`, '    say "Clicked at " + x + ", " + y + ", " + z'] : [`func ${fn}(x, y):`, '    say "Clicked at " + x + ", " + y']);
        }
      }
      const was = slot.type === 'click' ? slot.node.props.clicked : slot.reg;
      if (!fn) {
        if (slot.type === 'click') propEdit(pl, slot.node, 'clicked', null);
        else if (slot.reg) pl.ed.remove(slot.reg.line);
        pl.done();
        const old = was && (was.fn || was.args?.[0]?.raw);
        if (old) ide.toast(`func ${old}() is still in your code.`, 'info', 3500);
        return slot.node ? slot.node.key : 'root';
      }
      const f = { raw: fn };
      if (slot.type === 'click') propEdit(pl, slot.node, 'clicked', [f]);
      else {
        const args = slot.type === 'key' ? [key, f] : slot.type === 'every' ? [n, f] : [f];
        const method = slot.type === 'key' ? 'on_key' : slot.type === 'every' ? 'every' : 'clicked';
        if (slot.reg) pl.ed.replace(slot.reg.line, callText(slot.reg.call, args));
        else pl.reg(method === 'clicked' ? `${G}:clicked ${fn}` : `${G}:${method}(${args.map(fmt).join(', ')})`);
      }
      pl.done();
      if (value === '+new') ide.toast(`Added func ${fn}() at the bottom of your code.`, 'ok', 3500);
      return slot.node ? (slot.node._var ? `v:${slot.node._var}` : slot.node.key) : 'root';
    },

    // The game itself (spec §11.3): mention tgame if it's missing, then the game's lines.
    addGame(P, mode) {
      const ed = K.makeEditor(S.model);
      const nm = namer(P);
      const at = P.lastImport || 0;
      const G = nm('game');
      const out = [];
      if (!P.importLine) out.push('mention tgame');
      if (at || out.length) out.push('');
      if (mode === '3d') out.push(`${G} = tgame.world("My World", 960, 600)`, `${G}:sky "day"`, `${G}:island(80)`);
      else out.push(`${G} = tgame.window("My Game", 800, 600)`, `${G}:background "navy"`);
      if ((P.lines[at] ?? '').trim()) out.push('');
      ed.insertAfter(at, out.join('\n'));
      commit(ed);
      return 'root';
    },

    replaceAll(text) {
      S.model.pushStackElement();
      S.model.pushEditOperations([], [{ range: S.model.getFullModelRange(), text }], () => null);
      S.model.pushStackElement();
      return 'root';
    },

    addImport(P) {
      const ed = K.makeEditor(S.model);
      ed.insertAfter(0, 'mention tgame\n');
      ed.commit();
      return 'root';
    },
  };

  // ---------------------------------------------------------------- templates (spec §15)
  // coin_dash and island_walk are exactly test/tgame/games/coin_dash.tuf and island_walk.tuf (an e2e check keeps them so).
  const TEMPLATES = [
    { id: 'blank2d', name: 'Empty 2D game', desc: 'A navy 800 × 600 game area, ready for a Player, Coins and Enemies.', mode: '2d', icon: 'game',
      code: 'mention tgame\n\ngame = tgame.window("My Game", 800, 600)\ngame:background "navy"\n' },
    { id: 'blank3d', name: 'Empty 3D world', desc: 'A sunny island to walk around, seen through the player\'s eyes.', mode: '3d', icon: 'island',
      code: 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\ngame:island(80)\nplayer = game:player("first person")\n' },
    { id: 'coin_dash', name: 'Coin Dash (2D)', desc: 'Arrow keys move, coins score, the enemy chases you. Space plays again.', mode: '2d', icon: 'coin',
      code: `mention tgame

game = tgame.window("Coin Dash", 800, 600)
game:background "navy"
score = 0
score_label = game:text("Score: 0", 400, 30, 24, "white")
player = game:box(400, 520, 50, 50, "lime")
player:on_edge "stop"
coin = game:circle(200, 200, 14, "gold")
enemy = game:box(100, 80, 40, 40, "red")
ball = game:circle(600, 300, 12, "white")
ball:speed(200, 150)
ball:on_edge "bounce"

game:every_frame player_arrows
game:every_frame coin_collect
game:every_frame enemy_chase
game:every_frame enemy_hurts

# Tuff Engine: player moves with the arrow keys
func player_arrows(dt):
    if game:held("left"):
        player:move(-300 * dt, 0)
    if game:held("right"):
        player:move(300 * dt, 0)
    if game:held("up"):
        player:move(0, -300 * dt)
    if game:held("down"):
        player:move(0, 300 * dt)

# Tuff Engine: player collects coin
func coin_collect(dt):
    if coin:touches(player):
        score += 1
        score_label:set "Score: " + score
        game:sound "coin"
        coin:move_to(game:random_spot())

# Tuff Engine: enemy chases player
func enemy_chase(dt):
    enemy:point_at(player)
    enemy:forward(120 * dt)

# Tuff Engine: game over when enemy touches player
func enemy_hurts(dt):
    if enemy:touches(player) and not game:paused():
        game:sound "lose"
        game:game_over("Score: " + score, play_again)

# Tuff Engine: play again after a game over
func play_again():
    score = 0
    score_label:set "Score: 0"
    player:move_to(400, 520)
    coin:move_to(200, 200)
    enemy:move_to(100, 80)
` },
    { id: 'island_walk', name: 'Island Walk (3D)', desc: 'Walk an island, collect the spinning coin, chop the tree, dodge the red box.', mode: '3d', icon: 'tree',
      code: `mention tgame

game = tgame.world("Island Walk", 960, 600)
game:sky "day"
game:island(80)
hud = game:hud()
score = 0
score_label = hud:text("Score: 0", 90, 30, 26, "white")
player = game:player("first person")
coin = game:spawn("coin", 4, 0, -8)
coin:spin 90
tree = game:spawn("tree", -5, 0, -10)
tree:clicked tree_chop
hut = game:spawn("hut", 8, 0, -16)
enemy = game:box(-12, 0, -20, 1, "red")
enemy:solid false

game:every_frame coin_collect
game:every_frame enemy_chase
game:every_frame enemy_hurts

# Tuff Engine: player collects coin
func coin_collect(dt):
    if coin:touches(player):
        score += 1
        score_label:set "Score: " + score
        game:sound "coin"
        coin:move_to(game:random_spot())

# Tuff Engine: tree falls over when clicked
func tree_chop(thing):
    if not thing:fallen():
        thing:shake()
        thing:fall()
        thing:regrow(5)

# Tuff Engine: enemy chases player
func enemy_chase(dt):
    enemy:look_at(player)
    enemy:forward(2 * dt)

# Tuff Engine: game over when enemy touches player
func enemy_hurts(dt):
    if enemy:touches(player) and not game:paused():
        game:sound "lose"
        game:game_over("Score: " + score, play_again)

# Tuff Engine: play again after a game over
func play_again():
    score = 0
    score_label:set "Score: 0"
    player:move_to(0, 0, 0)
    coin:move_to(4, 0, -8)
    enemy:move_to(-12, 0, -20)
` },
  ];

  // ---------------------------------------------------------------- state
  const S = {
    file: null, model: null, sub: null, parsed: null, dump: null, dumpParsed: null, dumpVer: null, join: null, sceneVer: 0,
    sel: 'root', selfEdit: false, version: 0, ready: false, webgl: null, cams: new Map(), assetEpoch: 0, tables: null, busy: false,
    loadSeq: 0, loadedSeq: 0, hostFile: null, hostErr: null, camMode: 'editor', zoom: 'fit', tab: 'add', picSize: new Map(),
    files: [], log: [], asks: new Map(), askNo: 0, timer: null, frameRO: null,
  };
  const host = () => $('#engine');
  const is3d = () => S.parsed?.game?.mode === '3d';

  const KIND_LABEL = (n) => {
    if (n.kind === 'spawn') { const m = typeof n.args[0] === 'string' ? n.args[0] : ''; return /\.glb$/i.test(m) ? 'Model' : cap(m || 'Model'); }
    return { box: 'Box', circle: 'Circle', line: 'Line', text: 'Text', image: 'Picture', sphere: 'Ball', cylinder: 'Cylinder', cone: 'Cone', plane: 'Plane', light: 'Light', player: 'Player' }[n.kind] || cap(n.kind);
  };
  const iconFor = (n) => (n.kind === 'spawn' ? ICON[typeof n.args[0] === 'string' ? n.args[0] : ''] || ICON.model : n.layer === 'hud' && n.kind === 'text' ? ICON.hudtext : ICON[n.kind] || ICON.box);

  // ---------------------------------------------------------------- the frame (host.js)
  const frame = () => $('#en-frame');
  function hostPost(m) { try { frame()?.contentWindow?.postMessage(m, '*'); } catch { /* the frame is gone */ } }
  function hostAsk(what, extra = {}) {
    return new Promise((resolve) => {
      const tag = `en${++S.askNo}`;
      S.asks.set(tag, resolve);
      hostPost({ tuffHost: 'ask', tag, what, ...extra });
      setTimeout(() => { if (S.asks.has(tag)) { S.asks.delete(tag); resolve({ error: 'no reply' }); } }, 10000);
    });
  }

  function onMessage(e) {
    const f = frame();
    if (!f || e.source !== f.contentWindow || !e.data || typeof e.data !== 'object' || !e.data.tuffHost) return;
    const m = e.data;
    if (m.tuffHost !== 'reply') { S.log.push(m); if (S.log.length > 200) S.log.shift(); }
    switch (m.tuffHost) {
      case 'ready': S.ready = true; S.webgl = m.webgl; postLoad(); renderBanner(); break;
      case 'loaded':
        S.loadedSeq = m.seq;
        if (m.seq === S.loadSeq) $('#en-stage')?.classList.remove('switching');
        if (S.hostErr && m.seq) { S.hostErr = null; renderBanner(); }
        break;
      case 'pick': onPick(m); break;
      case 'drag': onDrag(m); break;
      case 'cam': if (S.hostFile) S.cams.set(S.hostFile, { tx: m.tx, ty: m.ty, tz: m.tz, az: m.az, el: m.el, dist: m.dist }); break;
      case 'key': onHostKey(m); break;
      case 'wheel': if (m.ctrl && !is3d()) setZoom(zoomNow() * (m.dy < 0 ? 1.1 : 1 / 1.1)); break;
      case 'focus': $('#en-stage')?.focus({ preventScroll: true }); break;
      case 'error': S.hostErr = m.message || 'unknown error'; renderBanner(); break;
      case 'reply': { const r = S.asks.get(m.tag); if (r) { S.asks.delete(m.tag); r({ value: m.value, error: m.error }); } break; }
      default: break;
    }
  }

  // ---------------------------------------------------------------- the scene: tuff.py --scene, then a load
  function requestScene() {
    clearTimeout(S.timer);
    S.timer = setTimeout(sceneNow, 350);
  }

  async function sceneNow() {
    clearTimeout(S.timer);
    const model = S.model;
    const file = S.file;
    if (!model || model.isDisposed() || !ide.engineVisible()) return;
    const ver = model.getAlternativeVersionId();
    const src = model.getValue();
    const P = parse(src);
    if (!P.game || P.other) { S.busy = false; pill(false); return; } // the start card shows; nothing to draw
    S.busy = true;
    pill(true);
    let d;
    try { d = await ide.scene(file, src); } catch (err) { d = { stopped: 'crashed', message: err.message }; }
    if (!d || d.superseded || file !== S.file || model !== S.model || model.isDisposed() || ver !== model.getAlternativeVersionId()) return; // a newer one is on its way
    S.busy = false;
    pill(false);
    S.tables = d.tables || S.tables;
    S.dump = d;
    S.dumpParsed = P;
    S.dumpVer = ver;
    S.version++;
    S.join = join();
    postLoad();
    renderBanner();
    if (S.parsed) { renderObjects(); if (S.sel !== 'root' && !find(S.parsed, S.sel) && !S.sel.startsWith('g:')) S.sel = 'root'; }
    // The Inspector's hints follow the new scene, unless someone is typing in it.
    if (!S.selfEdit && !$('#en-inspector')?.contains(document.activeElement)) renderInspector();
    renderAdd();
    layoutFrame();
  }

  // Which dump things belong to which key: editable things to their node, the rest grouped by the line that made
  // them (spec §8.3). Picks and selections go through this.
  function join() {
    const d = S.dump;
    const P = S.dumpParsed;
    const J = { byKey: new Map(), iToKey: new Map(), drag: new Map(), groups: [], playerKey: null, playerDrag: false };
    if (!d || !Array.isArray(d.things) || !P) return J;
    const entry = (key) => { if (!J.byKey.has(key)) J.byKey.set(key, { key, is: [], things: [] }); return J.byKey.get(key); };
    for (const t of d.things) {
      const m0 = t.made?.[0];
      const n = t.made?.length === 1 ? P.byLine[m0] : null;
      let key;
      if (n && n.floor) { key = 'root'; J.drag.set(t.i, null); }
      else if (n && n.kind !== 'player') {
        key = n.key;
        J.drag.set(t.i, n.pos.form === 'code' ? null : t.drag || null);
      } else {
        key = `g:${m0 ?? 0}:${t.kind}`;
        J.drag.set(t.i, null);
        if (!J.byKey.has(key)) J.groups.push({ key, line: m0 || 0, kind: t.kind, layer: t.layer, why: whyFor(P, t) });
      }
      const e = entry(key);
      e.is.push(t.i);
      e.things.push(t);
      J.iToKey.set(t.i, key);
    }
    if (d.player && P.player && d.player.made?.[0] === P.player.line) {
      J.playerKey = P.player.key;
      const e = entry(P.player.key);
      e.is = ['player'];
      e.player = d.player;
      J.playerDrag = true;
    }
    return J;
  }

  function whyFor(P, t) {
    const m0 = t.made?.[0];
    const text = K.stripComment(P.lines[m0 - 1] || '').code.trim();
    const w = /^(for|while|if)\b/.exec(text);
    if (w) return w[1] === 'for' ? 'inside a for loop' : w[1] === 'while' ? 'inside a while loop' : 'inside an if';
    const call = /^(?:[A-Za-z_]\w*\s*=\s*)?([A-Za-z_]\w*)\s*\(/.exec(text);
    if (t.made.length > 1 && call && P.funcs.some((f) => f.name === call[1])) return `made by ${call[1]}() on line ${m0}`;
    if (t.made.length > 1) return 'made by a function';
    return 'this line does more than one thing';
  }

  function selIs() {
    if (!S.join || S.sel === 'root') return [];
    return S.join.byKey.get(S.sel)?.is || [];
  }

  function postLoad() {
    const d = S.dump;
    if (!S.ready || !d || !d.mode || !Array.isArray(d.batch) || !S.join) return;
    const J = S.join;
    const things = d.things.map((t) => ({ ...t, drag: J.drag.has(t.i) ? J.drag.get(t.i) : null }));
    const player = d.player ? { ...d.player, drag: J.playerDrag && S.dumpParsed?.player?.var ? 'xz' : null } : null;
    const dir = S.file.replace(/[\\/][^\\/]*$/, '');
    const m = {
      tuffHost: 'load', seq: ++S.loadSeq, mode: d.mode, size: d.size, batch: d.batch, things, player, canvas: d.canvas, camera: d.camera, roots: d.roots,
      gameDirRel: ide.rel(dir).replace(/\\/g, '/'), assetEpoch: S.assetEpoch, camMode: S.camMode, select: selIs(),
    };
    if (S.hostFile !== S.file) m.cam = S.cams.get(S.file) || null; // the first load of a file fits the camera; later ones keep it
    S.hostFile = S.file;
    layoutFrame();
    hostPost(m);
  }

  function postSelect() { if (S.ready && S.loadSeq) hostPost({ tuffHost: 'select', is: selIs() }); }

  function onPick(m) {
    if (!S.join) return;
    const key = m.i === null ? 'root' : m.i === 'player' ? S.join.playerKey || 'root' : S.join.iToKey.get(m.i) || 'root';
    select(key);
  }

  function onDrag(m) {
    if (m.phase !== 'end' || !S.join || !S.model) return;
    const key = m.i === 'player' ? S.join.playerKey : S.join.iToKey.get(m.i);
    if (!key || key === 'root' || key.startsWith('g:')) return;
    // Lines may have moved since this scene was made: a name still finds its thing, a line number may not.
    if (key.startsWith('l:') && S.dumpVer !== S.model.getAlternativeVersionId()) { requestScene(); return; }
    act((P) => {
      const node = find(P, key);
      if (!node) return null;
      if (node.kind === 'player') {
        const old = node.props.move_to?.args;
        const y = isNum(old?.[1]) && !Array.isArray(old?.[0]) ? old[1] : 0;
        return Edits.setProp(P, node, 'move_to', [snap(m.x, 0.01), y, snap(m.z, 0.01)]);
      }
      return Edits.setArgs(P, node, dragPatch(node, m));
    });
  }

  function dragPatch(node, m) {
    const t = S.join?.byKey.get(node.key)?.things?.[0];
    const q = node.pos;
    if (node.layer !== 'world') {
      const dx = Math.round(m.dx || 0);
      const dy = Math.round(m.dy || 0);
      if (node.kind === 'line') return { x1: q.x1 + dx, y1: q.y1 + dy, x2: q.x2 + dx, y2: q.y2 + dy };
      const x = isNum(q.x) ? q.x : t?.x ?? 0;
      const y = isNum(q.y) ? q.y : t?.y ?? 0;
      return { x: Math.round(x + dx), y: Math.round(y + dy) };
    }
    const y = isNum(q.y) ? q.y : t?.y ?? 0;
    return { x: snap(m.x, 0.01), y, z: snap(m.z, 0.01) };
  }

  // ---------------------------------------------------------------- doing things
  // fn(P) does one edit on a fresh parse and gives the key to select. form: an Inspector field (the form keeps its
  // focus while the scene, Objects and the preview catch up); otherwise everything is drawn again.
  function act(fn, { form = false } = {}) {
    if (!S.model) return;
    if (S.model.isDisposed()) { if (ide.engineVisible()) show(S.file); return; } // its tab was closed: open it again
    S.parsed = parse(S.model.getValue());
    const before = S.model.getAlternativeVersionId();
    S.selfEdit = form;
    let key;
    try { key = fn(S.parsed); } catch (err) {
      S.selfEdit = false;
      console.error(err);
      ide.toast(`Tuff Engine couldn't do that: ${err.message}`, 'error', 6000);
      return;
    }
    if (typeof key === 'string') S.sel = key;
    if (S.model.getAlternativeVersionId() === before) { S.selfEdit = false; render(true); }
  }

  function select(key) {
    if (key === S.sel) { postSelect(); return; }
    S.sel = key || 'root';
    renderObjects();
    renderInspector();
    postSelect();
  }

  function undoRedo(which) {
    if (!S.model) return;
    S.selfEdit = false;
    S.model[which]();
  }

  async function play() {
    if (ide.isRunning()) { ide.stopRun(); return; }
    if (!S.file) return;
    await ide.runFile(S.file);
    renderPlay();
  }

  // ---------------------------------------------------------------- the tab
  function skeleton() {
    const st = ide.settings();
    S.zoom = st.engineZoom === 'fit' || st.engineZoom === undefined ? 'fit' : Number(st.engineZoom) || 'fit';
    S.tab = ['add', 'objects', 'assets'].includes(st.engineTab) ? st.engineTab : 'add';
    host().innerHTML = `
      <div class="sd en">
        <div class="sd-bar">
          <span class="sd-title" title="Tuff Engine">${ICON.pad}<b>Tuff Engine</b></span>
          <select id="en-file" title="Which game to edit"></select>
          <span class="en-kind" id="en-kind"></span>
          <span class="sd-sep"></span>
          <button class="sd-ib" id="en-undo" title="Undo (Ctrl+Z)">${UI.undo}</button>
          <button class="sd-ib" id="en-redo" title="Redo (Ctrl+Y)">${UI.redo}</button>
          <span class="sd-sep"></span>
          <div class="sd-zoom" id="en-zoom">
            <button class="sd-ib" id="en-zout" title="Zoom out (Ctrl+-)">${UI.minus}</button>
            <button class="sd-zval" id="en-zval" title="Actual size (Ctrl+0)">Fit</button>
            <button class="sd-ib" id="en-zin" title="Zoom in (Ctrl+=)">${UI.plus}</button>
            <button class="sd-ib" id="en-zfit" title="Fit to the screen">${UI.fit}</button>
          </div>
          <div class="sd-seg" id="en-cam" title="Editor: look around freely. Game: what the game shows when it starts.">
            <button data-cam="editor">Editor</button><button data-cam="game">Game</button>
          </div>
          <button class="sd-ib" id="en-full" title="Full size: give Tuff Engine the whole window (F11)">${UI.expand}</button>
          <div class="sd-bar-r">
            <button class="btn sm" id="en-templates" title="Start from a template">${UI.grid}<span class="lbl">Templates</span></button>
            <button class="btn sm" id="en-ask" title="Ask an AI agent in Tuff Agents to change the game">${ICON.ask}<span class="lbl">Ask an agent</span></button>
            <button class="btn sm" id="en-code" title="Show the code">${UI.code}<span class="lbl">Code</span></button>
            <button class="btn sm primary" id="en-play" title="Play: run the real game (Shift+F10)">${UI.play}<span class="lbl">Play</span></button>
          </div>
        </div>
        <div class="sd-main">
          <aside class="sd-left en-left">
            <div class="en-tabs">
              <button data-tab="add" title="Add things">${UI.plus}<span class="lbl">Add</span></button><button data-tab="objects" title="Everything in the game">${UI.grid}<span class="lbl">Objects</span></button><button data-tab="assets" title="Pictures, sounds and models">${ICON.image}<span class="lbl">Assets</span></button>
            </div>
            <div class="en-pane" data-pane="add"><div id="en-add"></div></div>
            <div class="en-pane" data-pane="objects"><div class="sd-layers" id="en-objects"></div></div>
            <div class="en-pane" data-pane="assets"><div class="en-assets" id="en-assets"></div></div>
          </aside>
          <section class="en-stage" id="en-stage" tabindex="-1">
            <div class="en-scroll" id="en-scroll"><iframe id="en-frame" src="tuffview://app/host/index.html" title="Game preview"></iframe></div>
            <div class="en-start hidden" id="en-start"></div>
            <div class="en-banner hidden" id="en-banner" role="status"></div>
            <div class="en-pill hidden" id="en-pill">Updating…</div>
            <div class="en-hint" id="en-hint"></div>
          </section>
          <aside class="sd-right" id="en-inspector"></aside>
        </div>
      </div>`;
    $('#en-file').onchange = (e) => ide.openEngine(e.target.value);
    $('#en-undo').onclick = () => undoRedo('undo');
    $('#en-redo').onclick = () => undoRedo('redo');
    $('#en-zout').onclick = () => setZoom(zoomNow() / 1.25);
    $('#en-zin').onclick = () => setZoom(zoomNow() * 1.25);
    $('#en-zval').onclick = () => setZoom(1);
    $('#en-zfit').onclick = () => setZoom('fit');
    $('#en-full').onclick = toggleFull;
    $$('#en-cam button').forEach((b) => (b.onclick = () => setCamMode(b.dataset.cam)));
    $('#en-templates').onclick = openTemplates;
    $('#en-ask').onclick = () => openAsk(null);
    $('#en-code').onclick = () => ide.openFile(S.file);
    $('#en-play').onclick = play;
    $$('.en-left .en-tabs button').forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
    const stage = $('#en-stage');
    stage.addEventListener('wheel', (e) => { if (e.ctrlKey && !is3d()) { e.preventDefault(); setZoom(zoomNow() * (e.deltaY < 0 ? 1.1 : 1 / 1.1)); } }, { passive: false });
    S.frameRO = new ResizeObserver(() => layoutFrame());
    S.frameRO.observe(stage);
    syncFull();
    setTab(S.tab);
  }

  function setTab(tab) {
    S.tab = tab;
    $('.en-left')?.classList.toggle('layers', tab !== 'add');
    $$('.en-left .en-tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
    $$('.en-left .en-pane').forEach((p) => p.classList.toggle('hidden', p.dataset.pane !== tab));
    ide.saveSettings({ engineTab: tab });
    if (tab === 'assets') renderAssets();
  }

  function setCamMode(mode) {
    S.camMode = mode === 'game' ? 'game' : 'editor';
    $$('#en-cam button').forEach((b) => b.classList.toggle('on', b.dataset.cam === S.camMode));
    hostPost({ tuffHost: 'view', cam: S.camMode });
    renderHint();
  }

  const zoomNow = () => (S.zoom === 'fit' ? S.fitK || 1 : S.zoom);
  function setZoom(z) {
    S.zoom = z === 'fit' ? 'fit' : Math.round(Math.max(0.25, Math.min(3, z)) * 100) / 100;
    ide.saveSettings({ engineZoom: S.zoom });
    layoutFrame();
  }

  function toggleFull() {
    ide.setStudioFull(!ide.studioFull());
    syncFull();
  }
  function syncFull() {
    const b = $('#en-full');
    if (!b) return;
    const on = ide.studioFull();
    b.innerHTML = on ? UI.shrink : UI.expand;
    b.classList.toggle('on', on);
    b.title = on ? 'Exit full size (F11)' : 'Full size: give Tuff Engine the whole window (F11)';
  }

  // The frame is the game's shape, as big as fits (2D can zoom instead).
  function layoutFrame() {
    const stage = $('#en-stage');
    const f = frame();
    if (!stage || !f || !S.parsed?.game) return;
    const [W, H] = gameSize(S.parsed, S.dump);
    const roomW = Math.max(60, stage.clientWidth - 48);
    const roomH = Math.max(60, stage.clientHeight - 84);
    S.fitK = Math.min(roomW / W, roomH / H);
    const k = !is3d() && S.zoom !== 'fit' ? S.zoom : S.fitK;
    f.style.width = `${Math.max(1, Math.round(W * k))}px`;
    f.style.height = `${Math.max(1, Math.round(H * k))}px`;
    const zv = $('#en-zval');
    if (zv) { zv.textContent = S.zoom === 'fit' ? 'Fit' : `${Math.round(k * 100)}%`; zv.title = S.zoom === 'fit' ? `Fitted (${Math.round(k * 100)}%). Click for actual size (Ctrl+0)` : 'Actual size (Ctrl+0)'; }
  }

  async function fillFiles() {
    const sel = $('#en-file');
    if (!sel) return;
    const all = (await ide.listFiles()).filter((f) => f.name.endsWith('.tuf') && !/^(dist|build)[\\/]/.test(f.rel));
    const games = new Set();
    await Promise.all(all.slice(0, 80).map(async (f) => {
      try { if (/^[ \t]*(?:import|mention)[ \t]+tgame\b/m.test(await api.fs.readFile(f.path))) games.add(f.path); } catch { /* unreadable */ }
    }));
    if (!all.some((f) => f.path === S.file)) all.unshift({ path: S.file, rel: ide.rel(S.file) });
    all.sort((a, b) => a.rel.localeCompare(b.rel));
    const opt = (f) => `<option value="${esc(f.path)}">${esc(f.rel)}</option>`;
    const g = all.filter((f) => games.has(f.path));
    const o = all.filter((f) => !games.has(f.path));
    sel.innerHTML = g.length ? `<optgroup label="Games">${g.map(opt).join('')}</optgroup>${o.length ? `<optgroup label="Other files">${o.map(opt).join('')}</optgroup>` : ''}` : o.map(opt).join('');
    sel.value = S.file;
    S.files = all;
    const pick = $('#en-start select');
    if (pick) { pick.innerHTML = sel.innerHTML; pick.value = S.file; }
  }

  async function show(file) {
    if (!host().firstChild) skeleton();
    if (file && file !== S.file) {
      S.file = file;
      S.sel = 'root';
      S.dump = null;
      S.dumpParsed = null;
      S.join = null;
      S.hostErr = null;
      if (S.loadSeq) $('#en-stage').classList.add('switching'); // the last file's scene hides until this one's is drawn
    }
    const want = S.file;
    const model = await ide.getModel(want);
    if (want !== S.file) return; // another file was asked for meanwhile: that show() draws it
    if (!model) { ide.toast(`Couldn't open ${ide.basename(S.file)}.`, 'error'); return; }
    S.sub?.dispose();
    S.model = model;
    S.sub = model.onDidChangeContent(K.debounce(() => {
      if (!ide.engineVisible() || model !== S.model) return;
      render(!S.selfEdit);
      S.selfEdit = false;
      requestScene();
    }, 120));
    fillFiles();
    render(true);
    sceneNow();
    if (S.tab === 'assets') renderAssets(); else listAssets();
    requestAnimationFrame(() => $('#en-stage')?.focus({ preventScroll: true }));
  }

  function hide() {
    clearTimeout(S.timer);
    $$('.sd-modal', host()).forEach((m) => m.remove());
  }

  // ---------------------------------------------------------------- drawing the tab
  function render(withForm = true) {
    if (!S.model || S.model.isDisposed()) return;
    S.parsed = parse(S.model.getValue());
    const P = S.parsed;
    const kind = $('#en-kind');
    const g = P.game;
    const [W, H] = g ? gameSize(P) : [0, 0];
    kind.textContent = !g ? '' : g.mode === '3d' ? '3D world' : `2D game ${W}×${H}`;
    $('#en-zoom').classList.toggle('hidden', !g || g.mode === '3d');
    $('#en-cam').classList.toggle('hidden', !g || g.mode !== '3d');
    $$('#en-cam button').forEach((b) => b.classList.toggle('on', b.dataset.cam === S.camMode));
    $('#en-undo').disabled = !S.model.canUndo();
    $('#en-redo').disabled = !S.model.canRedo();
    renderPlay();
    const start = !g || P.other;
    $('#en-stage').classList.toggle('start', !!start);
    renderStart();
    if (S.sel !== 'root' && !find(P, S.sel) && !(S.sel.startsWith('g:') && S.join?.byKey.has(S.sel))) S.sel = 'root';
    renderAdd();
    renderObjects();
    if (withForm) renderInspector();
    renderBanner();
    renderHint();
    layoutFrame();
    postSelect();
  }

  function renderPlay() {
    const b = $('#en-play');
    if (!b) return;
    const run = !!ide.isRunning();
    b.innerHTML = run ? `${ICON.stop}<span class="lbl">Stop</span>` : `${UI.play}<span class="lbl">Play</span>`;
    b.title = run ? 'Stop the game' : 'Play: run the real game (Shift+F10)';
    b.classList.toggle('stop', run);
  }

  function pill(on) { $('#en-pill')?.classList.toggle('hidden', !on); }

  function renderHint() {
    const h = $('#en-hint');
    if (!h) return;
    const g = S.parsed?.game;
    h.textContent = !g || S.parsed.other ? '' : g.mode === '3d'
      ? S.camMode === 'game' ? "The game's camera when it starts. Switch to Editor to move things." : 'Drag a thing to move it · Drag empty space to look around · Shift-drag to pan · Scroll to zoom'
      : 'Click to select · Drag to move · Arrow keys nudge (Shift ×10)';
  }

  function renderStart() {
    const box = $('#en-start');
    if (!box) return;
    const P = S.parsed;
    const show = !P.game || P.other;
    box.classList.toggle('hidden', !show);
    if (!show) return;
    if (P.other) {
      const studio = P.other !== 'atgui';
      box.innerHTML = `<div class="en-card">${ICON.game}<b>This is an app, not a game.</b><span>Tuff Engine makes tgame games. ${esc(ide.basename(S.file))} uses ${esc(P.other)}, which opens an app window${studio ? ': Design Studio builds those' : ''}.</span>
        <div class="en-btns">${studio ? `<button class="btn primary" data-a="studio">${UI.palette}Open in Design Studio</button>` : ''}<button class="btn" data-a="tpl">${UI.grid}New game from a template…</button></div>${filePick()}</div>`;
    } else {
      box.innerHTML = `<div class="en-card">${ICON.pad}<b>Make a game in ${esc(ide.basename(S.file))}</b><span>Tuff Engine writes real Tuff code as you click and drag. Start with an empty game area, or open a ready-made game.</span>
        <div class="en-btns"><button class="btn primary" data-a="2d">${ICON.game}Make a 2D game here</button><button class="btn" data-a="3d">${ICON.island}Make a 3D world here</button></div>
        <div class="en-btns"><button class="btn" data-a="tpl">${UI.grid}New game from a template…</button></div>${filePick()}</div>`;
      $('[data-a="2d"]', box).onclick = () => act((Q) => Edits.addGame(Q, '2d'));
      $('[data-a="3d"]', box).onclick = () => act((Q) => Edits.addGame(Q, '3d'));
    }
    $('[data-a="studio"]', box)?.addEventListener('click', () => ide.openStudio(S.file));
    $('[data-a="tpl"]', box).onclick = openTemplates;
    const pick = $('select', box);
    if (pick) {
      pick.innerHTML = $('#en-file').innerHTML;
      pick.value = S.file;
      pick.onchange = () => ide.openEngine(pick.value);
    }
  }
  const filePick = () => '<label class="en-pickfile">Or edit another file <select title="Which file to edit"></select></label>';

  function renderBanner() {
    const b = $('#en-banner');
    if (!b) return;
    const d = S.dump;
    const P = S.parsed;
    let html = '';
    let line = 0;
    let studio = false;
    let addImport = false;
    if (P?.game && !P.importLine && !P.other) { html = 'This game needs <code>mention tgame</code> at the top before it can run.'; addImport = true; }
    else if (P?.game && !P.other && d) {
      if (d.stopped === 'error' && d.error) {
        line = d.error.line || 0;
        html = `${line ? `Line ${line}: ` : ''}${esc(String(d.error.message || '').replace(/\.\s*$/, ''))}. The things made before that line are shown.`;
      } else if (d.stopped === 'timeout') html = 'Your code took more than 5 seconds before the game started, so Tuff Engine stopped it. Press Play to run it.';
      else if (d.stopped === 'other-window') { html = 'Tuff Engine shows tgame games. This file also opens a tgui, mtgui or atgui window.'; studio = true; }
      else if (d.stopped === 'too-big') html = 'This game makes too many things to show them all here. Press Play to see it.';
      else if (d.stopped === 'crashed') html = `The preview couldn't run: ${esc(d.message || 'something went wrong')}`;
      else if (S.webgl === false && d.mode === '3d') html = "This computer can't show 3D worlds: its 3D graphics (WebGL) aren't working. 2D games still work.";
      else if (S.hostErr) html = `The preview couldn't draw something: ${esc(S.hostErr)}`;
    }
    b.classList.toggle('hidden', !html);
    if (!html) { b.innerHTML = ''; return; }
    b.innerHTML = `${ICON.warn}<span>${html}</span>${line ? '<button class="btn sm" data-a="code">Show in code</button>' : ''}${studio ? '<button class="btn sm" data-a="studio">Open in Design Studio</button>' : ''}${addImport ? '<button class="btn sm" data-a="import">Add it</button>' : ''}`;
    $('[data-a="code"]', b)?.addEventListener('click', () => ide.goToLine(S.file, line));
    $('[data-a="studio"]', b)?.addEventListener('click', () => ide.openStudio(S.file));
    $('[data-a="import"]', b)?.addEventListener('click', () => act((Q) => Edits.addImport(Q)));
  }

  // ---------------------------------------------------------------- Add
  function tilesFor(P) {
    const g = P.game;
    if (!g) return [];
    const pics = S.assets?.pictures?.filter((f) => f.reach) || [];
    const models = S.assets?.models?.filter((f) => f.reach) || [];
    const sprite = ide.hasCommand('plugin.sprite-studio.open');
    const pictureTiles = pics.map((f) => ({ id: `pic:${f.rel}`, label: f.rel.split('/').pop(), icon: ICON.image, tip: `Add ${f.rel}`, thumb: f.path }));
    const draw = { id: 'draw', label: sprite ? 'Draw a sprite' : 'Get Sprite Studio', icon: ICON.draw, tip: sprite ? 'Draw a picture in Sprite Studio' : 'Sprite Studio is a plugin: turn it on in Plugins' };
    if (g.mode !== '3d') {
      return [
        ['Game pieces', [
          { id: 'player', label: 'Player', icon: ICON.player, tip: 'A box the arrow keys move' },
          { id: 'coin', label: 'Coin', icon: ICON.coin, tip: 'The player collects it for a point' },
          { id: 'enemy', label: 'Enemy', icon: ICON.enemy, tip: 'Chases the player: game over when it catches them' },
          { id: 'ball', label: 'Ball', icon: ICON.ball, tip: 'Bounces around by itself' },
          { id: 'score', label: 'Score', icon: ICON.score, tip: P.score ? 'This game has a score already' : 'A score and the text that shows it', off: !!P.score },
        ]],
        ['Shapes', [
          { id: 'box', label: 'Box', icon: ICON.box }, { id: 'circle', label: 'Circle', icon: ICON.circle },
          { id: 'line', label: 'Line', icon: ICON.line }, { id: 'text', label: 'Text', icon: ICON.text },
        ]],
        ['Pictures', [...pictureTiles, draw]],
        ['Screen', [
          { id: 'hudtext', label: 'Screen text', icon: ICON.hudtext, tip: 'Text on top that the camera never moves (lives, a timer)' },
          { id: 'hudbox', label: 'Screen box', icon: ICON.hudbox, tip: 'A bar on top (health, power)' },
        ]],
      ];
    }
    const kit = (names) => names.map((n) => ({ id: n, label: cap(n), icon: ICON[n] || ICON.model }));
    return [
      ['Game pieces', [
        { id: 'player', label: 'Player', icon: ICON.player, tip: P.player ? 'This world has its player' : 'You, walking around (WASD, Space jumps)', off: !!P.player },
        { id: 'coin', label: 'Coin', icon: ICON.coin, tip: 'A spinning coin the player collects' },
        { id: 'enemy', label: 'Enemy', icon: ICON.enemy, tip: 'Chases the player: game over when it catches them' },
        { id: 'chop', label: 'Choppable tree', icon: ICON.tree, tip: 'Falls over when clicked, and grows back' },
        { id: 'score', label: 'Score', icon: ICON.score, tip: P.score ? 'This world has a score already' : 'A score on the screen', off: !!P.score },
      ]],
      ['Nature', kit(KIT_NATURE)],
      ['Buildings', kit(KIT_BUILDINGS)],
      ['Shapes', [
        { id: 'box', label: 'Box', icon: ICON.box }, { id: 'ball', label: 'Ball', icon: ICON.ball }, { id: 'cylinder', label: 'Cylinder', icon: ICON.cylinder },
        { id: 'cone', label: 'Cone', icon: ICON.cone }, { id: 'plane', label: 'Plane', icon: ICON.plane },
      ]],
      ['World', [
        { id: 'light', label: 'Light', icon: ICON.light, tip: 'A glowing lamp' },
        { id: 'island', label: 'Island', icon: ICON.island, tip: 'An island in the sea', off: !!(P.settings.island || P.settings.ground) },
        { id: 'ground', label: 'Ground', icon: ICON.ground, tip: 'Flat grass to stand on', off: !!(P.settings.island || P.settings.ground) },
      ]],
      ...(models.length ? [['Models', models.map((f) => ({ id: `glb:${f.rel}`, label: f.rel.split('/').pop(), icon: ICON.model, tip: `Add ${f.rel}` }))]] : []),
      ['Screen', [{ id: 'hudtext', label: 'Screen text', icon: ICON.hudtext, tip: 'Text on top of the world (lives, a timer)' }, ...(pictureTiles.length ? [{ id: 'pics', label: 'Pictures', icon: ICON.image, tip: 'Pictures go on the screen: see Assets', off: false }] : [])]],
    ];
  }

  function renderAdd() {
    const box = $('#en-add');
    if (!box || !S.parsed) return;
    const P = S.parsed;
    box.innerHTML = '';
    if (!P.game || P.other) { box.innerHTML = '<div class="sd-hint">Make a game first: the buttons are in the middle.</div>'; return; }
    for (const [cat, tiles] of tilesFor(P)) {
      box.insertAdjacentHTML('beforeend', `<div class="sd-cat">${esc(cat)}</div>`);
      const grid = document.createElement('div');
      grid.className = 'sd-tiles';
      for (const t of tiles) {
        const b = document.createElement('button');
        b.className = 'sd-tile en-tile';
        b.dataset.tile = t.id;
        b.title = t.tip ? `${t.label}: ${t.tip}` : t.label;
        b.disabled = !!t.off;
        b.innerHTML = `<span class="ic${t.thumb ? ' en-pic' : ''}">${t.thumb ? `<img alt="" src="${esc(fileUrl(t.thumb))}">` : t.icon}</span><span class="lbl">${esc(t.label)}</span>`;
        b.onclick = () => clickTile(t.id);
        grid.appendChild(b);
      }
      box.appendChild(grid);
    }
    box.insertAdjacentHTML('beforeend', '<div class="sd-hint">Click to add it to your game. Then drag it where you want it.</div>');
  }

  async function clickTile(id) {
    if (id === 'draw') {
      if (ide.hasCommand('plugin.sprite-studio.open')) ide.runCommand('plugin.sprite-studio.open');
      else ide.showSideView('plugins', true);
      return;
    }
    if (id === 'pics') { setTab('assets'); return; }
    if (id.startsWith('pic:')) await picSize(id.slice(4));
    act((P) => Edits.add(P, id));
  }

  // ---------------------------------------------------------------- Objects
  function renderObjects() {
    const box = $('#en-objects');
    if (!box || !S.parsed) return;
    const P = S.parsed;
    box.innerHTML = '';
    if (!P.game || P.other) { box.innerHTML = '<div class="sd-hint">Nothing here yet.</div>'; return; }
    const J = S.join;
    const drawn = (key) => !J || !S.dump || J.byKey.has(key);
    const row = (key, icon, label, what, name, cls = '') => {
      const b = document.createElement('div');
      b.className = `sd-layer ${cls}${key === S.sel ? ' sel' : ''}`;
      b.dataset.key = key;
      b.innerHTML = `<span class="ic">${icon}</span><span class="lb">${esc(label)}</span><span class="what">${esc(what || '')}</span><span class="nm">${esc(name || '')}</span>`;
      b.onclick = () => select(key);
      box.appendChild(b);
      return b;
    };
    row('root', P.game.mode === '3d' ? ICON.world : ICON.game, P.game.mode === '3d' ? 'World' : 'Game', typeof P.game.args[0] === 'string' ? P.game.args[0] : '', P.game.var, 'en-root');
    const whatOf = (n) => (n.kind === 'text' || n.kind === 'image' ? (typeof n.args[0] === 'string' ? n.args[0] : '') : n.kind === 'spawn' ? '' : typeof fieldOf(n, 'color') === 'string' ? fieldOf(n, 'color') : '');
    const main = P.nodes.filter((n) => n.layer !== 'hud' && n.kind !== 'player');
    for (const n of main) row(n.key, iconFor(n), KIND_LABEL(n), whatOf(n), n.var, drawn(n.key) ? '' : 'en-dim').title = drawn(n.key) ? '' : 'Not drawn yet';
    if (P.player) {
      const n = P.player;
      row(n.key, ICON.player, 'Player', `${typeof n.args[0] === 'string' ? n.args[0] : 'first person'}${n.hold ? ` · holds ${n.hold.item}` : ''}`, n.var, drawn(n.key) ? '' : 'en-dim');
    }
    const hud = P.nodes.filter((n) => n.layer === 'hud');
    if (hud.length) {
      box.insertAdjacentHTML('beforeend', '<div class="sd-cat">Screen</div>');
      for (const n of hud) row(n.key, iconFor(n), KIND_LABEL(n), whatOf(n), n.var, drawn(n.key) ? '' : 'en-dim');
    }
    const groups = J?.groups || [];
    if (groups.length) {
      box.insertAdjacentHTML('beforeend', '<div class="sd-cat">Made by your code</div>');
      for (const gr of groups) {
        const count = J.byKey.get(gr.key)?.is.length || 0;
        row(gr.key, UI.code, `${count} × ${gr.kind}`, `${gr.why} (line ${gr.line})`, '', 'en-group').title = `Made by your code on line ${gr.line}: ${gr.why}`;
      }
    }
    box.insertAdjacentHTML('beforeend', '<div class="sd-hint">Things your game makes while it runs show up when you press Play.</div>');
  }

  // ---------------------------------------------------------------- Assets (spec §13)
  const PIC_EXT = /\.(png|gif|jpe?g|webp|bmp|svg)$/i;
  const SOUND_EXT = /\.(wav|mp3|ogg|m4a)$/i;
  const MODEL_EXT = /\.glb$/i;
  const fileUrl = (abs) => {
    let p = String(abs).replace(/\\/g, '/');
    if (!p.startsWith('/')) p = `/${p}`;
    return `file://${p.split('/').map((s) => (/^[A-Za-z]:$/.test(s) ? s : encodeURIComponent(s))).join('/')}?v=${S.assetEpoch}`;
  };

  async function listAssets() {
    if (!S.file) return;
    const file = S.file;
    const dir = file.replace(/[\\/][^\\/]*$/, '');
    const lower = dir.toLowerCase();
    let files = [];
    try { files = await ide.listFiles(); } catch { files = []; }
    if (file !== S.file) return null;
    const out = { pictures: [], sounds: [], models: [] };
    for (const f of files) {
      const kind = PIC_EXT.test(f.name) ? 'pictures' : SOUND_EXT.test(f.name) ? 'sounds' : MODEL_EXT.test(f.name) ? 'models' : null;
      if (!kind) continue;
      // tgame finds files in the game's own folder and the folders inside it (like Sprite Studio's outOfReach).
      const reach = f.path.length > dir.length + 1 && f.path.slice(0, dir.length).toLowerCase() === lower && /[\\/]/.test(f.path[dir.length]);
      out[kind].push({ ...f, reach, rel: reach ? f.path.slice(dir.length + 1).replace(/\\/g, '/') : f.rel.replace(/\\/g, '/') });
    }
    const first = (pre) => (a, b) => (b.rel.startsWith(pre) - a.rel.startsWith(pre)) || a.rel.localeCompare(b.rel);
    out.pictures.sort(first('sprites/'));
    out.sounds.sort(first('sounds/'));
    out.models.sort(first('models/'));
    S.assets = out;
    renderAdd();
    return out;
  }

  function picSize(rel) {
    if (S.picSize.has(rel)) return Promise.resolve(S.picSize.get(rel));
    const f = S.assets?.pictures.find((x) => x.rel === rel);
    if (!f) return Promise.resolve(null);
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => { const s = [img.naturalWidth, img.naturalHeight]; S.picSize.set(rel, s); resolve(s); };
      img.onerror = () => resolve(null);
      img.src = fileUrl(f.path);
    });
  }

  async function renderAssets() {
    const box = $('#en-assets');
    if (!box) return;
    const file = S.file;
    const A = await listAssets();
    if (!A || file !== S.file) return; // the file changed while the list was read: a newer render follows
    const P = S.parsed;
    const G = P?.game?.var || 'game';
    const base = ide.basename(S.file || 'game.tuf');
    box.innerHTML = '';
    const section = (title, list, kind) => {
      const inReach = list.filter((f) => f.reach);
      const away = list.length - inReach.length;
      box.insertAdjacentHTML('beforeend', `<div class="sd-cat">${esc(title)}</div>`);
      if (!inReach.length) box.insertAdjacentHTML('beforeend', `<div class="en-empty">No ${title.toLowerCase()} next to ${esc(base)} yet.</div>`);
      for (const f of inReach) {
        const row = document.createElement('div');
        row.className = 'en-asset';
        const thumb = kind === 'pictures' ? `<img class="en-thumb" alt="" src="${esc(fileUrl(f.path))}">` : `<span class="ic">${kind === 'sounds' ? ICON.sound : ICON.model}</span>`;
        const btn = kind === 'sounds' ? `<button class="pf-mini" data-a="copy" title="Copy the code that plays it">${UI.dup}</button>`
          : kind === 'models' && !is3d() ? '' : `<button class="pf-mini" data-a="add" title="Add it to the game">${UI.plus}</button>`;
        row.innerHTML = `${thumb}<span class="en-asset-n" title="${esc(f.rel)}">${esc(f.rel)}</span>${btn}`;
        $('[data-a="add"]', row)?.addEventListener('click', () => clickTile(`${kind === 'pictures' ? 'pic' : 'glb'}:${f.rel}`));
        $('[data-a="copy"]', row)?.addEventListener('click', () => {
          navigator.clipboard.writeText(`${G}:sound ${JSON.stringify(f.rel)}`).then(() => ide.toast('Copied. Paste it where the sound should play.', 'ok', 2500), () => ide.toast("Couldn't copy.", 'error'));
        });
        if (kind === 'pictures') $('img', row).onload = (e) => S.picSize.set(f.rel, [e.target.naturalWidth, e.target.naturalHeight]);
        box.appendChild(row);
      }
      if (away) box.insertAdjacentHTML('beforeend', `<div class="en-empty">${away} more ${away === 1 ? title.toLowerCase().replace(/s$/, '') + ' is' : title.toLowerCase() + ' are'} in other folders. Save ${away === 1 ? 'it' : 'them'} next to ${esc(base)}${kind === 'pictures' ? ' (in sprites/)' : kind === 'sounds' ? ' (in sounds/)' : ''} to use ${away === 1 ? 'it' : 'them'}.</div>`);
    };
    section('Pictures', A.pictures, 'pictures');
    section('Sounds', A.sounds, 'sounds');
    if (is3d()) section('Models', A.models, 'models');
    const foot = document.createElement('div');
    foot.className = 'en-btns en-assets-foot';
    foot.innerHTML = `<button class="btn sm" data-a="sprite">${ICON.draw}Draw a sprite</button><button class="btn sm" data-a="sound">${ICON.sound}Make a sound</button>`;
    $('[data-a="sprite"]', foot).onclick = () => (ide.hasCommand('plugin.sprite-studio.open') ? ide.runCommand('plugin.sprite-studio.open') : ide.showSideView('plugins', true));
    $('[data-a="sound"]', foot).onclick = () => (ide.hasCommand('plugin.sound-lab.open') ? ide.runCommand('plugin.sound-lab.open') : ide.showSideView('plugins', true));
    box.appendChild(foot);
  }

  // ---------------------------------------------------------------- the Inspector (spec §9)
  const colors = () => S.tables?.colors || FALLBACK_COLORS;
  const FALLBACK_COLORS = { blue: '#3574f0', purple: '#8b5cf6', pink: '#ec4899', red: '#e5484d', orange: '#f97316', yellow: '#e2a508', green: '#22a35a', teal: '#14b8a6', white: '#ffffff', black: '#000000', gray: '#8a8d94', brown: '#8b5a2b', gold: '#f2c230', lime: '#84cc16', cyan: '#22d3ee', navy: '#1e3a8a', sky: '#87ceeb', sand: '#e8d39a', grass: '#5fa83f', leaf: '#4f9d3a', wood: '#a0703c', stone: '#9a9a92', water: '#2f7fc8', snow: '#f4f7fb', silver: '#c0c6cf', 'dark green': '#2f6b2f', 'dark gray': '#3b3f46', 'light gray': '#c9ccd1', 'dark blue': '#1d3f8f', 'light blue': '#8ec5ff' };
  const tbl = (k, d) => S.tables?.[k] || d;

  function sec(title, kids) {
    const s = document.createElement('section');
    s.className = 'pf-sec';
    s.innerHTML = `<div class="pf-sec-h">${esc(title)}</div>`;
    for (const k of kids) if (k) s.append(k);
    return s;
  }
  function fieldEl(label, control, hint) { return K.field(label, control, hint); }

  // A row of small number inputs: [label, value, onChange(number), { step, min }].
  function numbers(items) {
    const row = document.createElement('div');
    row.className = 'pf en-nums';
    for (const [label, value, onChange, o = {}] of items) {
      const l = document.createElement('label');
      l.className = 'en-num';
      l.innerHTML = `<span>${esc(label)}</span>`;
      const inp = K.control('number', isNum(value) ? +num(value) : '', {}, (v) => { if (v === '' && !o.blank) return; onChange(v); });
      if (o.step) inp.step = o.step;
      if (o.min !== undefined) inp.min = o.min;
      if (o.disabled) inp.disabled = true;
      if (o.title) inp.title = o.title;
      if (o.placeholder) inp.placeholder = o.placeholder;
      l.appendChild(inp);
      row.appendChild(l);
    }
    return row;
  }

  function colorPick(value, onChange, { none = false } = {}) {
    const t = colors();
    const names = Object.keys(t).filter((n) => !/grey/.test(n));
    const cur = typeof value === 'string' ? value : '';
    const el = document.createElement('div');
    el.className = 'en-colors';
    const opts = none ? ['none', ...names] : names;
    const sw = K.chips(opts, opts.includes(cur) ? cur : cur === '' && none ? 'none' : null, onChange, (o) => (o === 'none' ? '<i class="sw-dot en-none"></i>' : `<i class="sw-dot" style="background:${esc(t[o])}"></i>`));
    sw.classList.add('en-swatches');
    $$('.pf-chip', sw).forEach((b, i) => { b.title = opts[i]; b.setAttribute('aria-label', opts[i]); });
    const hex = document.createElement('input');
    hex.type = 'text';
    hex.placeholder = '#hex';
    hex.spellcheck = false;
    hex.value = /^#/.test(cur) ? cur : '';
    hex.oninput = K.debounce(() => { const v = hex.value.trim(); if (/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(v)) onChange(v); }, 300);
    el.append(sw, hex);
    return el;
  }
  const colorLabel = (label, v) => `${label}${typeof v === 'string' ? ` · ${v}` : v && v.raw ? ' (from code)' : ''}`;

  function selectEl(options, value, onChange) {
    const s = document.createElement('select');
    for (const o of options) {
      const [v, label, off] = Array.isArray(o) ? o : [o, o];
      const op = document.createElement('option');
      op.value = v;
      op.textContent = label;
      if (off) op.disabled = true;
      s.appendChild(op);
    }
    s.value = value ?? '';
    s.onchange = () => onChange(s.value);
    return s;
  }

  function boolEl(on, onChange) { return K.control('bool', on, {}, onChange); }
  function textEl(value, onChange) { return K.control('text', value, {}, onChange); }

  // fn picker (Studio's control): (nothing), the functions that fit this event, + New function…
  function fnPick(value, inputs, onChange) {
    const funcs = S.parsed.funcs.filter((f) => f.params.length <= inputs).map((f) => f.name);
    if (value && !funcs.includes(value)) funcs.push(value);
    return K.control('fn', value || '', { funcs, goToFunc: (name) => { const f = S.parsed.funcs.find((x) => x.name === name); if (f) ide.goToLine(S.file, f.line); } }, onChange);
  }

  function actions(btns) {
    const act0 = document.createElement('div');
    act0.className = 'in-actions';
    for (const [label, icon, run, cls = '', title = ''] of btns) {
      const b = document.createElement('button');
      b.className = `btn sm ${cls}`;
      b.innerHTML = `${icon || ''}${esc(label)}`;
      if (title) b.title = title;
      b.onclick = run;
      act0.appendChild(b);
    }
    return act0;
  }

  // An edit from a field: the form keeps its focus. A key, not a node: the node is found again in a fresh parse.
  const fieldAct = (key, fn, rerender = false) => act((P) => { const n = find(P, key); return n ? fn(P, n) : null; }, { form: !rerender });

  function renderInspector() {
    const box = $('#en-inspector');
    if (!box || !S.parsed) return;
    const P = S.parsed;
    box.innerHTML = '';
    if (!P.game || P.other) return;
    if (S.sel.startsWith('g:')) { box.append(...groupCard(P)); return; }
    const node = find(P, S.sel);
    if (!node || node === P.game) { box.append(...rootCard(P)); return; }
    box.append(...nodeCard(P, node));
  }

  function head(icon, title, sub, nameEl) {
    const h = document.createElement('div');
    h.className = 'in-head';
    h.innerHTML = `<span class="ic big">${icon}</span><div class="in-id"><b>${esc(title)}</b>${sub ? `<span class="in-sub">${esc(sub)}</span>` : ''}</div>`;
    if (nameEl) $('.in-id', h).appendChild(nameEl);
    return h;
  }
  const tip = (text, cls = '') => { const d = document.createElement('div'); d.className = `in-tip ${cls}`; d.textContent = text; return d; };

  function groupCard(P) {
    const g = S.join?.groups.find((x) => x.key === S.sel);
    if (!g) { S.sel = 'root'; return rootCard(P); }
    const count = S.join.byKey.get(g.key)?.is.length || 0;
    return [
      head(UI.code, `${count} × ${g.kind}`, 'Made by your code'),
      tip(`Made by your code on line ${g.line} (${g.why}). Tuff Engine shows it but doesn't change it: change it in the code.`),
      actions([['Show in code', UI.code, () => ide.goToLine(S.file, g.line)], ['Ask an agent about it', ICON.ask, () => openAsk(g.key)]]),
    ];
  }

  function rootCard(P) {
    const g = P.game;
    const is3 = g.mode === '3d';
    const key = 'root';
    const [W, H] = gameSize(P);
    const out = [head(is3 ? ICON.world : ICON.game, is3 ? 'World' : 'Game', `${g.var} · tgame.${is3 ? 'world' : 'window'}`)];
    out.push(tip(is3 ? 'The 3D world: its window, sky and light.' : 'The game area: its window and background.'));
    const form = document.createElement('div');
    form.className = 'in-form';
    const title = typeof g.args[0] === 'string' ? g.args[0] : '';
    const sizeOk = (v) => { if (!(v >= 100)) { ide.toast('A game is at least 100 wide and 100 high.', 'error'); return false; } return true; };
    const setG = (patch) => act((Q) => Edits.setGame(Q, patch), { form: true });
    const sizes = K.chips(['600×400', '800×600', '960×540'], `${W}×${H}`, (o) => { const [w, h] = o.split('×').map(Number); act((Q) => Edits.setGame(Q, { width: w, height: h })); });
    sizes.classList.add('sizes');
    form.append(sec('Window', [
      fieldEl('Title', textEl(title, (v) => setG({ title: v }))),
      numbers([['Width', W, (v) => sizeOk(v) && setG({ width: Math.round(v) }), { min: 100 }], ['Height', H, (v) => sizeOk(v) && setG({ height: Math.round(v) }), { min: 100 }]]),
      fieldEl('Size', sizes),
    ]));
    const set = (changes, rerender = false) => act((Q) => Edits.setSetting(Q, changes), { form: !rerender });
    const s = P.settings;
    if (!is3) {
      const bg = s.background?.args[0];
      form.append(sec('Look', [fieldEl(colorLabel('Background', bg ?? 'default'), colorPick(bg, (v) => set([['background', [v]]], true)))]));
    } else {
      const sky = s.sky ? s.sky.args[0] : s.background ? '' : 'day';
      const skySel = selectEl([...tbl('skies', ['day', 'sunset', 'dawn', 'night', 'cloudy', 'space']).map((x) => [x, cap(x)]), ['', 'Plain colour']], typeof sky === 'string' ? sky : '', (v) => {
        if (v) set([['sky', [v]], ['background', null]], true);
        else set([['background', ['#123456']], ['sky', null]], true);
      });
      const look = [fieldEl('Sky', skySel)];
      if (!s.sky && s.background) look.push(fieldEl(colorLabel('Plain colour', s.background.args[0]), colorPick(s.background.args[0], (v) => set([['background', [v]]], true))));
      look.push(numbers([
        ['Fog', isNum(s.fog?.args[0]) ? s.fog.args[0] : '', (v) => set([['fog', v === '' ? null : [v]]]), { blank: true, min: 0, title: 'How far you can see. Empty: the sky\'s own fog' }],
        ['Sun', isNum(s.sun?.args[0]) ? s.sun.args[0] : 1, (v) => set([['sun', v === 1 || v === '' ? null : [v]]]), { step: 0.1, min: 0, blank: true }],
      ]));
      if (s.island) look.push(numbers([['Island size', isNum(s.island.args[0]) ? s.island.args[0] : 80, (v) => set([['island', [v]]]), { min: 12 }]]));
      if (s.ground) {
        const gc = s.ground.args[0] ?? 'grass';
        look.push(fieldEl(colorLabel('Ground colour', gc), colorPick(gc, (v) => set([['ground', [v, isNum(s.ground.args[1]) ? s.ground.args[1] : 400]]], true))));
        look.push(numbers([['Ground size', isNum(s.ground.args[1]) ? s.ground.args[1] : 400, (v) => set([['ground', [typeof gc === 'string' ? gc : 'grass', v]]]), { min: 1 }]]));
      }
      form.append(sec('Look', look));
    }
    form.append(eventsSection(P));
    out.push(form);
    out.push(actions([['Show in code', UI.code, () => ide.goToLine(S.file, g.line)], ['Ask an agent', ICON.ask, () => openAsk('root')]]));
    return out;
  }

  const KEYS = ['any', 'space', 'enter', 'up', 'down', 'left', 'right', ...'abcdefghijklmnopqrstuvwxyz', ...'0123456789'];
  function eventsSection(P) {
    const is3 = P.game.mode === '3d';
    const kids = [];
    const ev = (slot, value, change) => act((Q) => {
      const reg = slot.reg ? Q.regs.find((r) => r.line === slot.reg.line && r.method === slot.reg.method) : null;
      return Edits.setEvent(Q, { ...slot, reg }, value, change);
    });
    const regRow = (reg, label, extra) => {
      const row = document.createElement('div');
      row.className = 'en-ev';
      const l = document.createElement('span');
      l.className = 'en-ev-l';
      l.textContent = label;
      row.appendChild(l);
      if (extra) row.appendChild(extra);
      return row;
    };
    for (const reg of P.regs.filter((r) => r.owner === 'game' && r.method === 'on_key')) {
      const key = typeof reg.args[0] === 'string' ? reg.args[0] : '';
      const wrap = document.createElement('div');
      wrap.className = 'en-evrow';
      wrap.append(selectEl(KEYS.includes(key) ? KEYS : [key, ...KEYS], key, (k) => ev({ type: 'key', reg, key }, reg.fn, { key: k })),
        fnPick(reg.fn, 1, (v) => ev({ type: 'key', reg, key }, v)), xBtn(() => act((Q) => Edits.removeReg(Q, Q.regs.find((r) => r.line === reg.line)))));
      kids.push(regRow(reg, 'When a key is pressed', wrap));
    }
    for (const reg of P.regs.filter((r) => r.owner === 'game' && r.method === 'every')) {
      const n = isNum(reg.args[0]) ? reg.args[0] : 1;
      const wrap = document.createElement('div');
      wrap.className = 'en-evrow';
      const sec0 = numbers([['Seconds', n, (v) => v > 0 && ev({ type: 'every', reg, n }, reg.fn, { n: v }), { step: 0.5, min: 0.1 }]]);
      wrap.append(sec0, fnPick(reg.fn, 0, (v) => ev({ type: 'every', reg, n }, v)), xBtn(() => act((Q) => Edits.removeReg(Q, Q.regs.find((r) => r.line === reg.line)))));
      kids.push(regRow(reg, 'Every few seconds', wrap));
    }
    const gc = P.regs.find((r) => r.owner === 'game' && r.method === 'clicked');
    kids.push(fieldEl('When the game is clicked', fnPick(gc?.fn, is3 ? 3 : 2, (v) => ev({ type: 'gameclick', reg: gc }, v))));
    const add = document.createElement('div');
    add.className = 'en-btns';
    add.innerHTML = '<button class="btn sm" data-a="key">+ When a key is pressed</button><button class="btn sm" data-a="every">+ Every second</button>';
    $('[data-a="key"]', add).onclick = () => ev({ type: 'key', key: 'space' }, '+new');
    $('[data-a="every"]', add).onclick = () => ev({ type: 'every', n: 1 }, '+new');
    kids.push(add);
    // Every-frame functions that aren't a behaviour Tuff Engine knows, and timers it doesn't edit.
    const known = new Set(P.behaviours.map((b) => b.reg.line));
    for (const reg of P.regs.filter((r) => r.owner === 'game' && (r.method === 'every_frame' || r.method === 'after') && !known.has(r.line))) {
      const row = document.createElement('div');
      row.className = 'en-beh en-yours';
      row.innerHTML = `<div class="en-beh-h"><span>${reg.method === 'after' ? `After ${isNum(reg.args[0]) ? num(reg.args[0]) : '…'} s` : 'Every frame'} → ${esc(reg.fn || '?')}() <i>(your code)</i></span></div>`;
      const h = $('.en-beh-h', row);
      if (reg.fn) h.appendChild(miniBtn(UI.code, `Show func ${reg.fn}()`, () => { const f = P.funcs.find((x) => x.name === reg.fn); ide.goToLine(S.file, f ? f.line : reg.line); }));
      h.appendChild(xBtn(() => act((Q) => Edits.removeReg(Q, Q.regs.find((r) => r.line === reg.line))), 'Remove the line that runs it (the function stays)'));
      kids.push(row);
    }
    return sec('Events', kids);
  }

  const miniBtn = (icon, title, run) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'pf-mini'; b.title = title; b.innerHTML = icon; b.onclick = run; return b; };
  const xBtn = (run, title = 'Remove') => miniBtn(UI.close, title, run);

  function nodeCard(P, node) {
    const key = node.key;
    const is3 = node.layer === 'world';
    const hud = node.layer === 'hud';
    const out = [];
    const name = document.createElement('input');
    name.className = 'in-name';
    name.id = 'en-name';
    name.spellcheck = false;
    name.value = node.var || '';
    name.placeholder = 'give it a name';
    name.title = 'The name your code uses for this. Renaming updates your code too.';
    const commitName = () => {
      const v = name.value.trim();
      if (v === (node.var || '')) return;
      const back = (msg, kind = 'error') => { name.value = node.var || ''; ide.toast(msg, kind); };
      if (!v) return back('Code needs a name to talk to this, so it keeps its old one.', 'info');
      if (!NAME_RE.test(v)) return back("Names use letters, numbers and _ and can't start with a number.");
      if (KEYWORDS().includes(v) || BUILTINS.includes(v) || LIBS.includes(v)) return back(`'${v}' is part of Tuff. Pick another name.`);
      const fresh = parse(S.model.getValue());
      if (K.takenNames(fresh, S.model.getValue()).has(v)) return back(`'${v}' is already used. Pick another name.`);
      act((Q) => { const n = find(Q, key); return n ? Edits.rename(Q, n, v) : null; });
    };
    name.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); name.blur(); } if (e.key === 'Escape') { name.value = node.var || ''; name.blur(); } };
    name.onblur = commitName;
    const sub = node.kind === 'player' ? `${typeof node.args[0] === 'string' ? node.args[0] : 'first person'}` : hud ? 'on the screen' : '';
    out.push(head(iconFor(node), KIND_LABEL(node), sub, name));
    // Hints about where it is.
    const t = S.join?.byKey.get(key)?.things?.[0];
    const q = node.pos;
    const notes = [];
    if (node.kind === 'spawn' && q.form === 'none') notes.push('Random spot (changes every run). Drag it to give it a spot.');
    if (q.form === 'code') notes.push('This spot comes from code.');
    else if (t && S.dumpVer === S.model.getAlternativeVersionId() && ['xy', 'spot', 'line'].includes(q.form)) {
      const far = Math.abs((t.x ?? 0) - q.x) > 0.5 || Math.abs((t.y ?? 0) - (q.y ?? 0)) > 0.5 || (is3 && Math.abs((t.z ?? 0) - (q.z ?? 0)) > 0.5);
      if (far && node.kind !== 'line') notes.push('Your code moves this when the game starts.');
    }
    if (!S.join?.byKey.has(key) && S.dump) notes.push("Not drawn yet: it's made after the game starts, or after a mistake.");
    for (const n of notes) out.push(tip(n, 'en-note'));
    if (q.form === 'code' && t) out.push(actions([['Use numbers', UI.fit, () => act((Q) => { const n = find(Q, key); return n ? Edits.setArgs(Q, n, is3 ? { x: snap(t.x, 0.01), y: snap(t.y, 0.01), z: snap(t.z, 0.01) } : { x: Math.round(t.x), y: Math.round(t.y) }) : null; }), '', 'Write where it is now as numbers, so you can drag it']]));

    const form = document.createElement('div');
    form.className = 'in-form';
    const setA = (patch) => fieldAct(key, (Q, n) => Edits.setArgs(Q, n, patch));
    const setP = (method, args, rerender = false, extra = null) => fieldAct(key, (Q, n) => Edits.setProp(Q, n, method, args, extra), rerender);
    const v2 = (v) => Math.round(v);
    const v3 = (v) => +num(v);
    const posOK = ['xy', 'spot', 'none'].includes(q.form);
    if (node.kind === 'player') {
      const [sx, sz] = playerStart(P);
      const mt = (x, z) => { const old = node.props.move_to?.args; const y = isNum(old?.[1]) && !Array.isArray(old?.[0]) ? old[1] : 0; setP('move_to', [v3(x), y, v3(z)]); };
      form.append(sec('Start spot', [numbers([['X', sx, (v) => mt(v, playerStart(parse(S.model.getValue()))[1])], ['Z', sz, (v) => mt(playerStart(parse(S.model.getValue()))[0], v)]])]));
      const mode = typeof node.args[0] === 'string' ? node.args[0] : 'first person';
      const look = [
        fieldEl('Camera', selectEl(tbl('players', ['first person', 'third person']).map((x) => [x, cap(x)]), mode, (v) => setA({ mode: v }))),
        numbers([
          ['Facing', isNum(node.props.turn_to?.args[0]) ? node.props.turn_to.args[0] : 0, (v) => setP('turn_to', [v3(v)])],
          ['Walk speed', isNum(node.props.walk_speed?.args[0]) ? node.props.walk_speed.args[0] : 5, (v) => setP('walk_speed', [v3(v)]), { step: 0.5, min: 0 }],
          ['Jump height', isNum(node.props.jump_height?.args[0]) ? node.props.jump_height.args[0] : 1.2, (v) => setP('jump_height', [v3(v)]), { step: 0.1, min: 0 }],
        ]),
        fieldEl('Holds', selectEl([['', 'Nothing'], ...tbl('hold', ['axe', 'pickaxe', 'sword', 'torch', 'hammer']).map((x) => [x, cap(x)])], node.hold?.item || '', (v) => act((Q) => Edits.setHold(Q, v || null)))),
      ];
      form.append(sec('Player', look));
    } else if (node.kind === 'line') {
      form.append(sec('Where', [numbers([['X1', q.x1, (v) => setA({ x1: v2(v) })], ['Y1', q.y1, (v) => setA({ y1: v2(v) })], ['X2', q.x2, (v) => setA({ x2: v2(v) })], ['Y2', q.y2, (v) => setA({ y2: v2(v) })]])]));
    } else if (is3) {
      const disabled = !posOK;
      const cur = () => { const n = find(parse(S.model.getValue()), key); return n ? n.pos : q; };
      const put3 = (k, v) => { const c = cur(); setA({ x: c.x ?? t?.x ?? 0, y: c.y ?? t?.y ?? 0, z: c.z ?? t?.z ?? 0, [k]: v3(v) }); };
      form.append(sec('Where', [numbers([['X', q.x ?? t?.x, (v) => put3('x', v), { step: 0.5, disabled }], ['Y (bottom)', q.y ?? t?.y, (v) => put3('y', v), { step: 0.5, disabled }], ['Z', q.z ?? t?.z, (v) => put3('z', v), { step: 0.5, disabled }]])]));
    } else {
      const disabled = !posOK;
      const cur = () => { const n = find(parse(S.model.getValue()), key); return n ? n.pos : q; };
      const put2 = (k, v) => { const c = cur(); setA({ x: c.x ?? t?.x ?? 0, y: c.y ?? t?.y ?? 0, [k]: v2(v) }); };
      form.append(sec('Where', [numbers([['X', q.x ?? t?.x, (v) => put2('x', v), { disabled }], ['Y', q.y ?? t?.y, (v) => put2('y', v), { disabled }]])]));
    }
    // What it does comes first (Chases → speed), then how it looks and how it moves by itself.
    if (!hud && node.kind !== 'player' && node.kind !== 'light') form.append(behSection(P, node));
    if (node.kind !== 'player') form.append(lookSection(P, node, setA, setP));
    if (!hud && node.kind !== 'player' && node.kind !== 'light') form.append(movesSection(node, setP));
    if (node.kind !== 'player' && node.kind !== 'light') {
      const clicked = node.props.clicked?.args[0]?.raw || '';
      form.append(sec('Events', [fieldEl('When clicked', fnPick(clicked, 1, (v) => act((Q) => { const n = find(Q, key); return n ? Edits.setEvent(Q, { type: 'click', node: n }, v) : null; })))]));
    }
    out.push(form);
    const btns = [];
    if (node.kind !== 'player') btns.push(['Duplicate', UI.dup, () => act((Q) => { const n = find(Q, key); return n ? Edits.duplicate(Q, n) : null; }), '', 'Duplicate (Ctrl+D)']);
    btns.push(['Show in code', UI.code, () => ide.goToLine(S.file, node.line)]);
    btns.push(['Ask an agent about it', ICON.ask, () => openAsk(key)]);
    btns.push(['Delete', UI.trash, () => removeKey(key), 'danger', 'Delete (Del)']);
    out.push(actions(btns));
    return out;
  }

  function removeKey(key) {
    act((Q) => { const n = find(Q, key); return n ? Edits.remove(Q, n) : null; });
  }

  function lookSection(P, node, setA, setP) {
    const kids = [];
    const is3 = node.layer === 'world';
    const k = node.kind;
    const f = (name) => fieldOf(node, name);
    const v2 = (v) => Math.round(v);
    const v3 = (v) => +num(v);
    if (k === 'text') {
      kids.push(fieldEl('Words', textEl(typeof f('words') === 'string' ? f('words') : '', (v) => setA({ words: v }))));
      kids.push(numbers([['Size', f('size'), (v) => v > 0 && setA({ size: v2(v) }), { min: 1 }]]));
    }
    if (k === 'image') {
      const pics = (S.assets?.pictures || []).filter((x) => x.reach).map((x) => x.rel);
      const cur = typeof f('file') === 'string' ? f('file') : '';
      kids.push(fieldEl('Picture', selectEl(pics.includes(cur) ? pics : [cur, ...pics], cur, (v) => setA({ file: v }))));
      kids.push(numbers([['Width', isNum(f('width')) ? f('width') : '', (v) => setA({ width: v === '' ? undefined : v2(v) }), { blank: true, min: 1, title: "Empty: the picture's own width", placeholder: 'its own' }]]));
    }
    if (!is3 && (k === 'box')) kids.push(numbers([['Width', f('w'), (v) => v >= 0 && setA({ w: v2(v) }), { min: 0 }], ['Height', f('h'), (v) => v >= 0 && setA({ h: v2(v) }), { min: 0 }]]));
    if (!is3 && k === 'circle') kids.push(numbers([['Radius', f('r'), (v) => v >= 0 && setA({ r: v2(v) }), { min: 0 }]]));
    if (k === 'spawn') {
      const models = tbl('kit', [...KIT_NATURE, ...KIT_BUILDINGS, 'coin']);
      const glbs = (S.assets?.models || []).filter((x) => x.reach).map((x) => x.rel);
      const cur = typeof f('model') === 'string' ? f('model') : '';
      const opts = [...models.map((m) => [m, cap(m)]), ...glbs.map((m) => [m, m])];
      if (cur && !opts.some(([v]) => v === cur)) opts.unshift([cur, cur]);
      kids.push(fieldEl('Model', selectEl(opts, cur, (v) => setA({ model: v }))));
      kids.push(numbers([['Scale', isNum(node.props.scale?.args[0]) ? node.props.scale.args[0] : 1, (v) => v > 0 && setP('scale', [v3(v)]), { step: 0.25, min: 0.1 }]]));
    }
    if (is3 && ['box', 'sphere', 'cylinder', 'cone', 'plane'].includes(k)) {
      const size = f('size');
      const list = Array.isArray(size);
      const dims = k === 'box' ? ['Width', 'Height', 'Depth'] : k === 'plane' ? ['Width', 'Depth'] : k === 'sphere' ? null : ['Width', 'Height'];
      // The list as it is now (another of its fields may have just changed it).
      const curSize = () => { const n = find(parse(S.model.getValue()), node.key); const s = n && fieldOf(n, 'size'); return (Array.isArray(s) ? s : size).slice(); };
      if (list && dims) kids.push(numbers(dims.map((lab, j) => [lab, size[j], (v) => { if (!(v > 0)) return; const s = curSize(); s[j] = v3(v); setA({ size: s }); }, { step: 0.5, min: 0.1 }])));
      else kids.push(numbers([['Size', isNum(size) ? size : '', (v) => v > 0 && setA({ size: v3(v) }), { step: 0.5, min: 0.1, disabled: !isNum(size) && size !== undefined }]]));
      if (dims) {
        kids.push(fieldEl('Different sizes', boolEl(list, (on) => fieldAct(node.key, (Q, n) => {
          const cur = fieldOf(n, 'size');
          const base = isNum(cur) ? cur : Array.isArray(cur) ? cur[0] : 1;
          return Edits.setArgs(Q, n, { size: on ? dims.map(() => base) : base });
        }, true)), k === 'box' ? 'Width, height and depth' : k === 'plane' ? 'Width and depth' : 'Width and height'));
      }
    }
    if (k !== 'image') {
      const c = f('color');
      kids.push(fieldEl(colorLabel('Color', c), colorPick(c, (v) => setA({ color: v }))));
    }
    if (k === 'light') return sec('Look', kids);
    if (!is3) {
      kids.push(numbers([
        ['Layer', isNum(node.props.layer?.args[0]) ? node.props.layer.args[0] : 0, (v) => setP('layer', [v2(v)]), { title: 'Higher layers are drawn on top' }],
        ['Angle', isNum(node.props.turn_to?.args[0]) ? node.props.turn_to.args[0] : 0, (v) => setP('turn_to', [v2(v)])],
      ]));
      if (k === 'text') kids.push(fieldEl('Align', K.control('segment', node.props.align?.args[0] || 'center', { options: ['left', 'center', 'right'] }, (v) => setP('align', [v]))));
    } else {
      kids.push(numbers([['Angle', isNum(node.props.turn_to?.args[0]) ? node.props.turn_to.args[0] : 0, (v) => setP('turn_to', [v3(v)]), { title: 'Which way it faces, in degrees' }]]));
      kids.push(fieldEl('Label', textEl(typeof node.props.label?.args[0] === 'string' ? node.props.label.args[0] : '', (v) => setP('label', [v])), 'Words shown above it'));
      const glow = typeof node.props.glow?.args[0] === 'string' ? node.props.glow.args[0] : 'none';
      kids.push(fieldEl(colorLabel('Glow', glow), colorPick(glow, (v) => setP('glow', [v]), { none: true })));
      kids.push(fieldEl('Solid', boolEl(node.props.solid?.args[0] !== false, (on) => setP('solid', [on])), 'Off: the player walks through it'));
    }
    kids.push(fieldEl('Hidden at start', boolEl(!!node.props.hide, (on) => setP('hide', on ? [] : null))));
    return sec('Size and look', kids);
  }

  function movesSection(node, setP) {
    const is3 = node.layer === 'world';
    const sp = node.props.speed?.args || [];
    const n0 = (i) => (isNum(sp[i]) ? sp[i] : 0);
    const kids = [];
    const cur = () => { const n = find(parse(S.model.getValue()), node.key); const a = n?.props.speed?.args || []; return [0, 1, 2].map((i) => (isNum(a[i]) ? a[i] : 0)); };
    const speed = (j, v) => { const s = cur().slice(0, is3 ? 3 : 2); s[j] = is3 ? +num(v) : Math.round(v); setP('speed', s); };
    kids.push(fieldEl('Moves by itself', numbers(is3
      ? [['vx', n0(0), (v) => speed(0, v)], ['vy', n0(1), (v) => speed(1, v)], ['vz', n0(2), (v) => speed(2, v)]]
      : [['vx', n0(0), (v) => speed(0, v)], ['vy', n0(1), (v) => speed(1, v)]]), is3 ? 'Units per second' : 'Pixels per second'));
    kids.push(numbers([['Spins', isNum(node.props.spin?.args[0]) ? node.props.spin.args[0] : 0, (v) => setP('spin', [is3 ? +num(v) : Math.round(v)]), { title: 'Degrees per second' }]]));
    if (!is3) {
      const edge = typeof node.props.on_edge?.args[0] === 'string' ? node.props.on_edge.args[0] : 'none';
      kids.push(fieldEl('At the edges', K.control('segment', edge, { options: ['none', 'stop', 'bounce', 'wrap'] }, (v) => {
        const extra = (v === 'bounce' || v === 'wrap') && !node.props.speed ? [['speed', [150, 120]]] : null;
        setP('on_edge', [v], true, extra);
      })));
    }
    return sec('Moves', kids);
  }

  function behSection(P, node) {
    const kids = [];
    const is3 = node.layer === 'world';
    const list = P.behaviours.filter((b) => b.node === node);
    const named = P.nodes.filter((n) => n.var && n !== node && n.layer !== 'hud').map((n) => n.var);
    const sounds = () => [...tbl('sounds', ['coin', 'lose']), 'none', ...(S.assets?.sounds || []).filter((x) => x.reach).map((x) => x.rel)];
    const setB = (b, params) => act((Q) => { const x = Q.behaviours.find((y) => y.id === b.id); return x ? Edits.setBehaviour(Q, x, params) : null; }, { form: true });
    for (const b of list) {
      const box = document.createElement('div');
      box.className = 'en-beh';
      box.dataset.beh = b.type;
      box.innerHTML = `<div class="en-beh-h"><span>${esc(BEH[b.type].label(b.p))}</span></div>`;
      const h = $('.en-beh-h', box);
      h.appendChild(miniBtn(UI.code, `Show func ${b.fn.name}()`, () => ide.goToLine(S.file, b.fn.line)));
      h.appendChild(xBtn(() => act((Q) => { const x = Q.behaviours.find((y) => y.id === b.id); return x ? Edits.removeBehaviour(Q, x) : null; }), 'Remove this behaviour'));
      const p = b.p;
      const opts = (cur) => (named.includes(cur) ? named : [cur, ...named]);
      if (b.type === 'arrows') {
        box.append(numbers([['Speed', p.S, (v) => v > 0 && setB(b, { S: Math.round(v) }), { min: 1 }]]));
        box.append(K.control('segment', p.dirs, { options: ['all', 'leftright', 'updown'], names: { all: 'All four', leftright: 'Left/right', updown: 'Up/down' } }, (v) => setB(b, { dirs: v })));
      } else if (b.type === 'collect') {
        box.append(fieldEl('By', selectEl(opts(p.C), p.C, (v) => setB(b, { C: v }))));
        box.append(numbers([['Points', p.P, (v) => v >= 1 && setB(b, { P: Math.round(v) }), { min: 1 }]]));
        box.append(fieldEl('Sound', selectEl(sounds().includes(p.sound) ? sounds() : [p.sound, ...sounds()], p.sound, (v) => setB(b, { sound: v }))));
      } else if (b.type === 'chase') {
        box.append(fieldEl('Chases', selectEl(opts(p.T), p.T, (v) => setB(b, { T: v }))));
        box.append(numbers([['Speed', p.S, (v) => v > 0 && setB(b, { S: is3 ? +num(v) : Math.round(v) }), { step: is3 ? 0.5 : 10, min: 0.1 }]]));
      } else if (b.type === 'hurts') {
        box.append(fieldEl('Touches', selectEl(opts(p.T), p.T, (v) => setB(b, { T: v }))));
        box.append(fieldEl('Sound', selectEl(sounds().includes(p.sound) ? sounds() : [p.sound, ...sounds()], p.sound, (v) => setB(b, { sound: v }))));
      } else if (b.type === 'falls') {
        box.append(numbers([['Grows back after (s)', p.secs, (v) => v > 0 && setB(b, { secs: +num(v) }), { step: 0.5, min: 0.1 }]]));
      }
      kids.push(box);
    }
    // Add a behaviour (the defaults are the tiles').
    const have = new Set(list.map((b) => b.type));
    const mover = is3 ? target3(P) : firstMover(P);
    const types = is3 ? ['collect', 'chase', 'hurts', 'falls'] : ['arrows', 'collect', 'chase', 'hurts'];
    const names = { arrows: 'Moves with the arrow keys', collect: 'Collect it', chase: 'Chases…', hurts: 'Game over when it touches…', falls: 'Falls over when clicked' };
    const needs = { collect: true, chase: true, hurts: true };
    const items = types.filter((t) => !have.has(t)).map((t) => [t, needs[t] && (!mover || mover === node.var) ? `${names[t]} (add a ${is3 ? 'Player' : 'Player with arrow keys'} first)` : names[t], needs[t] && (!mover || mover === node.var)]);
    if (items.length) {
      const sel = selectEl([['', '+ Add behaviour…'], ...items], '', (type) => {
        if (!type) return;
        const params = type === 'arrows' ? { S: 300, dirs: 'all' } : type === 'collect' ? { C: mover, P: 1, sound: 'coin' } : type === 'chase' ? { T: mover, S: is3 ? 2 : 120 } : type === 'hurts' ? { T: mover, sound: 'lose' } : { secs: 5 };
        act((Q) => { const n = find(Q, node.key); return n ? Edits.addBehaviour(Q, n, type, params) : null; });
      });
      sel.className = 'en-addbeh';
      kids.push(sel);
    }
    return sec('Behaviours', kids);
  }

  // ---------------------------------------------------------------- templates gallery
  function openTemplates() {
    const box = document.createElement('div');
    box.className = 'sd-modal';
    box.innerHTML = `<div class="sd-mbox" role="dialog" aria-label="Game templates">
      <div class="sd-mhead"><div><b>Start from a game</b><span>Every template is real Tuff code you can read and change.</span></div><button class="sd-ib" data-a="x" title="Close (Esc)">${UI.close}</button></div>
      <div class="sd-tgrid"></div></div>`;
    const grid = $('.sd-tgrid', box);
    for (const t of TEMPLATES) {
      const card = document.createElement('div');
      card.className = 'sd-tcard en-tcard';
      card.dataset.id = t.id;
      card.innerHTML = `<div class="en-tthumb">${ICON[t.icon] || ICON.game}<span>${t.mode === '3d' ? '3D' : '2D'}</span></div><div class="sd-tinfo"><b>${esc(t.name)}</b><span>${esc(t.desc)}</span>
        <div class="sd-tbtns"><button class="btn sm primary" data-a="new">New file</button><button class="btn sm" data-a="here">Use here</button></div></div>`;
      $('[data-a="new"]', card).onclick = () => { close(); templateAsFile(t); };
      $('[data-a="here"]', card).onclick = () => { close(); templateHere(t); };
      grid.appendChild(card);
    }
    const close = () => { box.remove(); document.removeEventListener('keydown', onEsc, true); };
    const onEsc = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', onEsc, true);
    box.onmousedown = (e) => { if (e.target === box) close(); };
    $('[data-a="x"]', box).onclick = close;
    host().appendChild(box);
  }

  async function templateHere(t) {
    if (S.model.getValue().trim()) {
      const ok = await ide.ask({ title: `Replace the code in ${ide.basename(S.file)} with the ${t.name} template? (Ctrl+Z undoes it.)`, confirm: true, okLabel: 'Replace' });
      if (!ok) return;
    }
    S.sel = 'root';
    S.hostFile = null; // fit the camera around the new world
    act(() => Edits.replaceAll(t.code));
  }

  async function templateAsFile(t) {
    const dir = ide.root();
    let name = `${t.id}.tuf`;
    for (let i = 2; await api.fs.exists(ide.join(dir, name)); i++) name = `${t.id}${i}.tuf`;
    const path = ide.join(dir, name);
    await api.fs.createFile(path);
    await api.fs.writeFile(path, t.code);
    await ide.refreshTree();
    ide.toast(`Made ${name} from the ${t.name} template.`, 'ok');
    ide.openEngine(path);
  }

  // ---------------------------------------------------------------- Ask an agent (spec §14)
  function noteFor(about) {
    const P = S.parsed;
    const what = P?.game?.mode === '3d' ? '3D world' : '2D game';
    let sel = '';
    if (about && about !== 'root') {
      const n = find(P, about);
      if (n) sel = ` They have ${n.var || KIND_LABEL(n).toLowerCase()} selected (line ${n.line}).`;
      else if (about.startsWith('g:')) { const g = S.join?.groups.find((x) => x.key === about); if (g) sel = ` They have the ${g.kind}s made on line ${g.line} selected.`; }
    }
    return `(From TuffCode: they're building ${ide.rel(S.file)} in Tuff Engine, TuffCode's visual game editor, as a ${what}. Tuff Engine can only show and edit simple top-level lines, so: make each new thing with one top-level line and plain numbers, like coin = game:circle(200, 200, 14, "gold"); put new lines above any while game:open(): loop; add behaviour as a func registered with a line like game:every_frame coin_spin or coin:clicked coin_clicked.${sel} Check the file with tuff_check when you're done.)`;
  }

  function openAsk(about) {
    const box = document.createElement('div');
    box.className = 'sd-modal';
    const n = about && about !== 'root' ? find(S.parsed, about) : null;
    const g = about && about.startsWith('g:') ? S.join?.groups.find((x) => x.key === about) : null;
    const subject = n ? (n.var || KIND_LABEL(n).toLowerCase()) : g ? `the ${g.kind}s on line ${g.line}` : '';
    box.innerHTML = `<div class="sd-mbox en-askbox" role="dialog" aria-label="Ask an agent">
      <div class="sd-mhead"><div><b>Ask an agent${subject ? ` about ${esc(subject)}` : ''}</b><span>Your AI agent in Tuff Agents changes ${esc(ide.basename(S.file))}, and the scene updates by itself.</span></div><button class="sd-ib" data-a="x" title="Close (Esc)">${UI.close}</button></div>
      <div class="en-ask">
        <textarea id="en-ask-text" rows="4" spellcheck="true" placeholder="${subject ? `What should ${esc(subject)} do?` : 'What should change? Like: make the coin bigger every time I collect it'}"></textarea>
        <div class="modal-choices"></div>
        <div class="en-ask-btns"><span>Plan makes a plan, Ask explains, Edit changes your code.</span><button class="btn" data-mode="plan">Plan</button><button class="btn" data-mode="ask">Ask</button><button class="btn primary" data-mode="edit">Edit</button></div>
      </div></div>`;
    const ta = $('textarea', box);
    const chips = $('.modal-choices', box);
    for (const c of ['Add a coin that moves', 'Make it harder over time', 'Add 3 lives']) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = c;
      b.onclick = () => { ta.value = c; ta.focus(); };
      chips.appendChild(b);
    }
    const close = () => { box.remove(); document.removeEventListener('keydown', onEsc, true); };
    const onEsc = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', onEsc, true);
    box.onmousedown = (e) => { if (e.target === box) close(); };
    $('[data-a="x"]', box).onclick = close;
    $$('[data-mode]', box).forEach((b) => (b.onclick = () => {
      const text = ta.value.trim();
      if (!text) { ta.focus(); ide.toast('Write what you want first.'); return; }
      if (typeof window.tuffAskAgent !== 'function') {
        ide.toast('Turn on Tuff Agents in Plugins (Alt+3) to ask an agent.', 'info', 5000);
        ide.showSideView('plugins', true);
        return;
      }
      S.lastAsk = { text, mode: b.dataset.mode, note: noteFor(about) };
      window.tuffAskAgent(text, { mode: b.dataset.mode, note: S.lastAsk.note });
      close();
    }));
    ta.onkeydown = (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('[data-mode="edit"]', box).click(); } };
    host().appendChild(box);
    ta.focus();
  }

  // ---------------------------------------------------------------- keys (spec §11.5)
  function onKey(e) {
    if (!S.model || !host()?.firstChild) return false;
    if (!$('#modal')?.classList.contains('hidden') || $('.sd-modal', host())) return false;
    if (e.target?.closest?.('input, textarea, select, [contenteditable="true"], [contenteditable="plaintext-only"]')) return false;
    if (e.target?.closest?.('#rightbar, #sidebar, #bottom-panel, .monaco-editor')) return false;
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const ctrl = e.ctrlKey || e.metaKey;
    if (ctrl && !e.shiftKey && k === 'z') { undoRedo('undo'); return true; }
    if (ctrl && (k === 'y' || (e.shiftKey && k === 'z'))) { undoRedo('redo'); return true; }
    if (k === 'F10' && e.shiftKey) { play(); return true; }
    if (k === 'F11') { toggleFull(); return true; }
    const P = S.parsed;
    if (!P?.game || P.other) return false;
    if (ctrl && !is3d() && (k === '=' || k === '+')) { setZoom(zoomNow() * 1.25); return true; }
    if (ctrl && !is3d() && k === '-') { setZoom(zoomNow() / 1.25); return true; }
    if (ctrl && !is3d() && k === '0') { setZoom(1); return true; }
    const node = find(P, S.sel);
    const thing = node && node !== P.game ? node : null;
    if (ctrl && !e.shiftKey && !e.altKey && k === 'd') { if (thing) act((Q) => { const n = find(Q, thing.key); return n ? Edits.duplicate(Q, n) : null; }); return true; }
    if (ctrl || e.altKey) return false;
    if (k === 'Delete' || k === 'Backspace') { if (thing) removeKey(thing.key); return true; }
    if (k === 'Escape') { hostPost({ tuffHost: 'cancel' }); select('root'); return true; }
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(k)) {
      if (!thing) return true;
      nudge(thing, k, e.shiftKey);
      return true;
    }
    return false;
  }

  function nudge(node, k, big) {
    const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[k];
    const key = node.key;
    act((P) => {
      const n = find(P, key);
      if (!n) return null;
      if (n.kind === 'player') {
        const [sx, sz] = playerStart(P);
        const s = big ? 2 : 0.5;
        return Edits.setProp(P, n, 'move_to', [snap(sx + dir[0] * s, 0.01), 0, snap(sz + dir[1] * s, 0.01)]);
      }
      const q = n.pos;
      if (q.form === 'code') { ide.toast('This spot comes from code. Use numbers (on the right) first.'); return null; }
      if (n.layer === 'world') {
        if (q.form === 'none') return null;
        const s = big ? 2 : 0.5;
        return Edits.setArgs(P, n, { x: snap(q.x + dir[0] * s, 0.01), y: q.y ?? 0, z: snap(q.z + dir[1] * s, 0.01) });
      }
      const s = big ? 10 : 1;
      if (n.kind === 'line') return Edits.setArgs(P, n, { x1: q.x1 + dir[0] * s, y1: q.y1 + dir[1] * s, x2: q.x2 + dir[0] * s, y2: q.y2 + dir[1] * s });
      if (q.form === 'none') return null;
      return Edits.setArgs(P, n, { x: q.x + dir[0] * s, y: q.y + dir[1] * s });
    });
  }

  // A key pressed in the preview: ours if onKey wants it, otherwise the IDE's (Ctrl+S, Alt+4...).
  function onHostKey(m) {
    if (m.key === 'Escape') { onKey({ key: 'Escape', target: null }); return; }
    const ev = { key: m.key, code: m.code, ctrlKey: !!m.ctrl, shiftKey: !!m.shift, altKey: !!m.alt, metaKey: !!m.meta, target: null };
    if (onKey(ev)) return;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: m.key, code: m.code, ctrlKey: !!m.ctrl, shiftKey: !!m.shift, altKey: !!m.alt, metaKey: !!m.meta, bubbles: true, cancelable: true }));
  }

  // ---------------------------------------------------------------- setup
  function init(ideApi) {
    ide = ideApi;
    window.addEventListener('message', onMessage);
    window.addEventListener('tuff:run-finished', renderPlay);
    api.fs.onChanged?.(({ paths = [], overflow }) => {
      if (!S.file || !host()?.firstChild) return;
      const dir = S.file.replace(/[\\/][^\\/]*$/, '').toLowerCase();
      const hit = overflow || paths.some((p) => p.toLowerCase().startsWith(dir) && (PIC_EXT.test(p) || SOUND_EXT.test(p) || MODEL_EXT.test(p)));
      if (!hit) return;
      S.assetEpoch++;
      S.picSize.clear();
      if (ide.engineVisible()) { requestScene(); if (S.tab === 'assets') renderAssets(); else listAssets(); }
    });
  }

  window.TuffEngine = {
    init,
    show,
    hide,
    onKey,
    parse,
    lineFor: (node, args, name) => lineFor(node, args, name),
    fixups,
    templates: () => TEMPLATES.map((t) => ({ ...t })),
    // A snapshot for tests and DevTools.
    debug: () => ({
      file: S.file, sel: S.sel, ready: S.ready, webgl: S.webgl, busy: S.busy, version: S.version, loadSeq: S.loadSeq, loadedSeq: S.loadedSeq,
      mode: S.parsed?.game?.mode || null, stopped: S.dump?.stopped ?? null, error: S.dump?.error ?? null, ms: S.dump?.ms ?? null,
      things: S.dump?.things?.length ?? 0, keys: S.parsed?.nodes.map((n) => n.key) || [], groups: S.join?.groups.map((g) => ({ key: g.key, why: g.why, n: S.join.byKey.get(g.key)?.is.length })) || [],
      behaviours: S.parsed?.behaviours.map((b) => ({ id: b.id, type: b.type, V: b.V, p: b.p })) || [], banner: $('#en-banner')?.classList.contains('hidden') ? '' : $('#en-banner')?.textContent || '',
      zoom: S.zoom, camMode: S.camMode, cam: S.cams.get(S.file) || null, selIs: selIs(), lastAsk: S.lastAsk || null, dumpCurrent: !!S.model && S.dumpVer === S.model.getAlternativeVersionId(),
    }),
    // For the e2e suite: drive the frame and read what happened.
    test: {
      ask: (what, extra) => hostAsk(what, extra),
      log: () => S.log.slice(),
      clearLog: () => { S.log.length = 0; },
      select: (key) => select(key),
      keyOf: (i) => S.join?.iToKey.get(i) ?? null,
      thingsOf: (key) => S.join?.byKey.get(key)?.is || [],
      dump: () => S.dump,
      sceneNow: () => sceneNow(),
      edits: Edits,
      act: (fn) => act(fn),
      noteFor: (about) => noteFor(about),
      parsed: () => S.parsed,
      // Edits work on this model (a Monaco model, or a stand-in with the same methods) without the tab showing.
      // Gives the model and file it replaced, to put back with useModel(...was).
      useModel: (model, file) => { const was = [S.model, S.file]; S.model = model; if (file) S.file = file; return was; },
    },
  };
})();
