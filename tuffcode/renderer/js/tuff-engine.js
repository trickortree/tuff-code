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
    // The land (world:terrain) and its tools.
    land: svg('<path d="M1.5 13l4.2-6.8 2.6 3.6 2.2-2.8 4 6z"/><path d="M4.4 8.3l1.3.9 1.1-.8"/>'),
    raise: svg('<path d="M1.8 13.5c2.2-3 4.1-4.4 6.2-4.4s4 1.4 6.2 4.4"/><path d="M8 6.8V2.2M5.9 4.2L8 2.1l2.1 2.1"/>'),
    lower: svg('<path d="M1.8 8.6c2.2 3 4.1 4.4 6.2 4.4s4-1.4 6.2-4.4"/><path d="M8 2v4.6M5.9 4.6L8 6.7l2.1-2.1"/>'),
    smooth: svg('<path d="M1.8 6.2c1.5-1.6 2.7-1.6 4.1 0s2.7 1.6 4.1 0 2.7-1.6 4.2 0"/><path d="M1.8 11.8h12.4"/>'),
    flatten: svg('<path d="M1.8 13.2h12.4"/><rect x="4" y="6.2" width="8" height="3.8" rx="1"/><path d="M8 2.2v4"/>'),
    hill: svg('<path d="M1.5 12.5c1.8-5.4 11.2-5.4 13 0z"/>'),
    mountain: svg('<path d="M1.5 13L6.6 3.8l2.9 4.9 1.5-2.2 3.5 6.5z"/><path d="M5.1 6.6l1.5.9 1.3-.8"/>'),
    dip: svg('<path d="M1.5 6.5h3c1.2 4.6 5.8 4.6 7 0h3"/>'),
    lake: svg('<path d="M1.5 5.5h2.6c1.1 5.5 6.7 5.5 7.8 0h2.6"/><path d="M5.2 8h5.6"/>'),
    valley: svg('<path d="M1.5 3.5c3.4 0 4.1 9 6.5 9s3.1-9 6.5-9"/>'),
    water: svg('<path d="M1.5 6.3c1.4-1.3 2.9-1.3 4.3 0s2.9 1.3 4.4 0 2.9-1.3 4.3 0M1.5 10.3c1.4-1.3 2.9-1.3 4.3 0s2.9 1.3 4.4 0 2.9-1.3 4.3 0"/>'),
    // Physics: a car, a ragdoll, and the badge on things that use physics (a ball falling).
    car: svg('<path d="M1.5 11V8.8c0-.4.3-.8.7-.8h1.3l1.6-2.6c.2-.3.5-.4.8-.4h4.4c.3 0 .6.1.8.4L13 8h.8c.4 0 .7.4.7.8V11"/><circle cx="4.8" cy="11.3" r="1.6"/><circle cx="11.2" cy="11.3" r="1.6"/><path d="M6.4 11.3h3.2M5.6 8h4.8"/>'),
    ragdoll: svg('<circle cx="8" cy="3.3" r="1.8"/><path d="M8 5.1v5M4 7.6l4-1.2 4 1.8M8 10.1l-2.6 3.9M8 10.1l3 3.4"/>'),
    physics: svg('<circle cx="9.8" cy="9.8" r="3.7"/><path d="M2.5 2.5l3.2 3.2M2 6.8h2.6M6.8 2v2.6"/>'),
    // The game kit's level pieces: a door, a key, a jump pad, a boost pad, a moving platform and a person who talks.
    door: svg('<path d="M3.5 14.5V2.5h9v12"/><path d="M5.5 14.5V4.5h5v10"/><path d="M9 9.5h.01"/>'),
    key: svg('<circle cx="5" cy="8" r="2.8"/><path d="M7.8 8h6.7M12 8v2.5M14 8v2"/>'),
    jump_pad: svg('<path d="M2 13.5h12"/><rect x="3.5" y="10.5" width="9" height="3" rx="1"/><path d="M8 8V2.2M5.8 4.4L8 2.2l2.2 2.2"/>'),
    boost_pad: svg('<path d="M2 13.5h12"/><path d="M3 4.5l4 3.5-4 3.5M8.5 4.5l4 3.5-4 3.5"/>'),
    platform: svg('<rect x="3" y="8" width="10" height="2.5" rx="1"/><path d="M1.5 5h4M10.5 5h4M3.5 3l-2 2 2 2M12.5 3l2 2-2 2"/>'),
    person: svg('<circle cx="6" cy="4" r="2"/><path d="M2.5 14v-3a3.5 3.5 0 017 0v3"/><path d="M10 2.5h4.5v3.5h-2l-1.5 1.5V6H10z"/>'),
  };
  ICON.terrain = ICON.land;
  ICON.sphere = ICON.ball;
  ICON.spawn = ICON.model;
  ICON.lift = ICON.platform;

  // ---------------------------------------------------------------- reading the file
  const IMPORT_RE = /^(?:import|mention)\s+tgame\b/;
  const OTHER_RE = /^(?:import|mention)\s+(tgui|mtgui|atgui)\b/;
  const ANY_IMPORT_RE = /^(?:import|mention)\s+[A-Za-z_]\w*/;
  const GAME_RE = /^([A-Za-z_]\w*)\s*=\s*tgame\.(window|world)\b\s*(.*)$/;
  const SET_RE = /^([A-Za-z_]\w*):(background|sky|fog|sun|island|ground|lighting)\b\s*(.*)$/;
  // The land: land = world:terrain(200), then its own lines (land:hill(20, -10, 30, 8)...).
  const TERRAIN_RE = /^([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*):terrain\b\s*(.*)$/;
  const LAND_RE = /^([A-Za-z_]\w*):(style|hill|mountain|dip|lake|valley|raise|lower|smooth|flatten|water)\b\s*(.*)$/;
  const REG_RE = /^([A-Za-z_]\w*):(every_frame|on_key|every|after|clicked)\b\s*(.*)$/;
  const MAKE_RE = /^(?:([A-Za-z_]\w*)\s*=\s*)?([A-Za-z_]\w*):(box|circle|line|text|image|sphere|cylinder|cone|plane|spawn|light|player|hud|hold|car|ragdoll|door|jump_pad|boost_pad)\b\s*(.*)$/;
  const PROP_RE = /^([A-Za-z_]\w*):(speed|spin|on_edge|layer|turn_to|hide|label|solid|glow|align|scale|clicked|walk_speed|jump_height|move_to|physics|weight|mass|bounce|friction|drive|engine|say|path|needs|shirt|pants|skin|hair|shoes|sleeves)\b\s*(.*)$/;
  const FUNC_RE = /^func\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:\s*$/;
  const SCORE_RE = /^score\s*=\s*(-?\d+)\s*$/;
  const MARK_RE = /^#\s*Tuff Engine:/;
  const NAME_RE = /^[A-Za-z_]\w*$/;
  const K2D = ['box', 'circle', 'line', 'text', 'image', 'hud'];
  const K3D = ['box', 'sphere', 'cylinder', 'cone', 'plane', 'spawn', 'light', 'player', 'hud', 'car', 'ragdoll', 'door', 'jump_pad', 'boost_pad'];
  const KHUD = ['text', 'box', 'circle', 'line', 'image'];
  // The lines that belong to a thing (after its own line), by what it is. Physics lines (crate:physics(),
  // crate:weight(25) or crate:mass(25), crate:bounce(0.6), crate:friction(0.4)) belong to an object or a sprite; a car
  // has drive and engine, and its weight. A person's look (npc:shirt("red"), npc:hair("curly", "brown")...) belongs
  // to a person, a ragdoll and the player.
  const PHYSICS_PROPS = ['physics', 'weight', 'mass', 'bounce', 'friction'];
  const LOOKS = ['shirt', 'pants', 'skin', 'hair', 'shoes', 'sleeves'];
  // The game kit's: a person's speech bubble (npc:say("Hi!")), a moving platform's spots (lift:path(...)) and the key
  // a door needs (door:needs(key)). A jump pad and a boost pad are objects.
  const KIT_PROPS = ['say', 'path'];
  const PIECES = ['door', 'jump_pad', 'boost_pad'];
  const FAMILY = {
    sprite: ['speed', 'spin', 'on_edge', 'layer', 'turn_to', 'hide', 'align', 'clicked', ...PHYSICS_PROPS],
    object: ['speed', 'spin', 'turn_to', 'hide', 'label', 'solid', 'glow', 'scale', 'clicked', ...PHYSICS_PROPS, ...KIT_PROPS, ...LOOKS],
    player: ['move_to', 'turn_to', 'walk_speed', 'jump_height', 'weight', ...LOOKS],
    car: ['drive', 'engine', 'turn_to', 'clicked', 'weight', 'mass', 'bounce', 'friction'],
    ragdoll: ['clicked', 'weight', 'mass', 'bounce', 'friction', ...LOOKS],
    door: ['needs', 'turn_to', 'hide', 'clicked'],
  };
  const family = (n) => (['player', 'car', 'ragdoll', 'door'].includes(n.kind) ? n.kind : n.layer === 'world' ? 'object' : 'sprite');
  // The things the Inspector's Physics section is for (in 3D: everything in the world but a light; in 2D: the game's
  // sprites, not the screen's), and the kinds of physics it writes (Off is no line).
  const PHYSICS_THINGS = ['box', 'sphere', 'cylinder', 'cone', 'plane', 'spawn'];
  const PHYSICS_2D = ['box', 'circle', 'line', 'text', 'image'];
  const PHYSICS_KINDS = ['off', 'dynamic', 'static', 'kinematic'];
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
      if (node.kind === 'car') return { pre: 0, dim: 3, rest: [['color', 'red']] };
      if (node.kind === 'ragdoll') return { pre: 0, dim: 3, rest: [['color', 'blue']] };
      if (node.kind === 'door') return { pre: 0, dim: 3, rest: [['color', 'wood']] };
      if (node.kind === 'jump_pad') return { pre: 0, dim: 3, rest: [['power', 15]] };
      if (node.kind === 'boost_pad') return { pre: 0, dim: 3, rest: [['power', 20]] };
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
      land: null,
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
      // The land and its lines: its style, its water, and every edit (hill, lake, a brush stroke...) in order.
      if (is3d && !P.land && (m = c.match(TERRAIN_RE)) && m[2] === G && (!m[3] || (m[3].startsWith('(') && K.closesAtEnd(m[3])))) {
        const call = callOf(full, c, m[3]);
        P.land = { key: 'land', kind: 'terrain', var: m[1], line: ln, comment, call, args: call.vals, text: full, style: null, water: null, edits: [] };
        P.byLine[ln] = P.land;
        continue;
      }
      if (P.land && (m = c.match(LAND_RE)) && m[1] === P.land.var && (!m[3] || (m[3].startsWith('(') && K.closesAtEnd(m[3])) || !/[:(]/.test(m[3]))) {
        const call = callOf(full, c, m[3]);
        const e = { key: `le:${ln}`, op: m[2], line: ln, call, args: call.vals, text: full };
        if (e.op === 'style') P.land.style = e;
        else if (e.op === 'water') P.land.water = e;
        else P.land.edits.push(e);
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
          ...(p.sound && p.sound !== 'none' ? [[2, `${p.G}:sound ${JSON.stringify(p.sound)}`]] : []), [2, `${p.V}:move_to(${p.G}:random_spot())`],
          // A new spot on top of the player would be collected again straight away.
          [2, `while ${p.V}:touches(${p.C}):`], [3, `${p.V}:move_to(${p.G}:random_spot())`]];
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
    if (P.land) setup.push(landLast(P.land));
    return {
      setupEnd: Math.max(0, ...setup.filter(before)),
      settingsEnd: Math.max(P.game?.line || 0, ...settings),
      regEnd: Math.max(0, ...P.regs.filter((r) => r.owner === 'game').map((r) => r.line).filter(before)),
    };
  }
  const ownLast = (node) => Math.max(node.line, ...Object.values(node.props).map((p) => p.line), node.hold?.line || 0);
  const landLines = (L) => [L.line, L.style?.line, L.water?.line, ...L.edits.map((e) => e.line)].filter(Boolean);
  const landLast = (L) => Math.max(...landLines(L));

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
    if (key === 'land') return P.land;
    if (key.startsWith('le:')) return P.land?.edits.find((e) => e.line === +key.slice(3)) || null;
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

  // Every edit is one undo step, except while a number field is typed in (numbers()): S.typing is that field's step
  // during its edit, and its edits join one step (the 2, 25 and 250 of a slowly typed 250 are one Ctrl+Z) until the
  // field is left, or until something else changes the code in between.
  function commit(ed, blocks = []) {
    const finish = (lines) => fixups(blocks.reduce(appendBlock, lines));
    const step = S.typing;
    if (!step) { closeStep(); return ed.commit(finish); }
    const join = S.openStep === step && step.model === S.model && step.ver === S.model.getAlternativeVersionId();
    if (!join) closeStep();
    const at = ed.commit(finish, { open: !join, close: false });
    step.model = S.model;
    step.ver = S.model.getAlternativeVersionId();
    S.openStep = step;
    return at;
  }
  function closeStep() {
    const step = S.openStep;
    S.openStep = null;
    if (step?.model && !step.model.isDisposed()) step.model.pushStackElement();
  }

  const BASE = { box: 'box', circle: 'circle', line: 'line', text: 'words', image: 'picture', sphere: 'ball', cylinder: 'cylinder', cone: 'cone', plane: 'plane', spawn: 'thing', light: 'lamp', player: 'player', car: 'car', ragdoll: 'dummy', door: 'door', jump_pad: 'pad', boost_pad: 'boost' };
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
    // A free spot on the screen (the HUD) for new text or a picture: from (x, y) down, row by row, until nothing on
    // the screen is near it. (The 3D score and Screen text both start at 90, 30.)
    const onScreen = P.nodes.filter((n) => n.layer === 'hud' && isNum(n.pos.x) && isNum(n.pos.y)).map((n) => [n.pos.x, n.pos.y]);
    pl.hudSpot = (x, y) => {
      for (let i = 0; i < 12 && onScreen.some(([hx, hy]) => Math.abs(hx - x) < 150 && Math.abs(hy - y) < 30); i++) y += 34;
      onScreen.push([x, y]);
      return [x, y];
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
        const [sx, sy] = is3d ? pl.hudSpot(90, 30) : [Math.round(W / 2), 30];
        out.push(is3d ? `${pl.label} = ${pl.hud}:text("Score: 0", ${sx}, ${sy}, 26, "white")` : `${pl.label} = ${G}:text("Score: 0", ${sx}, ${sy}, 24, "white")`);
      }
      if (out.length) ed.insertAfter(Math.max(A.settingsEnd, P.hud?.line || 0), out.join('\n'));
      pl.scored = true;
    };
    // (One name for the whole edit: two enemies given Game over in one step share it.)
    pl.playAgain = () => (pl.pa = pl.pa || P.behaviours.find((b) => b.type === 'hurts')?.p.PA || (P.funcs.some((f) => f.name === 'play_again') ? 'play_again' : nm('play_again')));
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
    walk_speed: (a) => a[0] === 5, jump_height: (a) => a[0] === 1.2, physics: (a) => a[0] === 'off', drive: (a) => a[0] === false, engine: (a) => a[0] === 1,
  };
  // Physics, car and look lines always have brackets, like crate:physics(), crate:bounce(0.6) and npc:shirt("red").
  const PAREN = new Set([...PHYSICS_PROPS, 'drive', 'engine', ...KIT_PROPS, 'needs', ...LOOKS]);
  const propLine = (V, method, args) => (!args.length ? `${V}:${method}()` : args.length === 1 && !PAREN.has(method) ? `${V}:${method} ${fmt(args[0])}` : `${V}:${method}(${args.map(fmt).join(', ')})`);

  // A prop line (coin:spin 90): replaced where it is, or put after the thing's own lines; a default value removes it.
  function propEdit(pl, node, method, args) {
    const p = node.props[method];
    if (args === null || PROP_OFF[method]?.(args)) { if (p) pl.ed.remove(p.line); return; }
    const V = ensureVar(pl, node);
    if (p) pl.ed.replace(p.line, callText(p.call, args, { paren: PAREN.has(method) }));
    else pl.ed.insertAfter(ownLast(node), propLine(V, method, args));
  }

  // A thing on a path (lift:path([[0, 1, -6], [8, 1, -6]], 3)): the spots are places in the world, so when the thing
  // moves (from where it is to its new inputs, args), each spot moves by as much. Gives its path line written again,
  // null when it has no path or didn't move, or false when a spot comes from code (then the path stays as it is).
  function pathMoved(node, args) {
    const p = node.props.path;
    if (!p || p.args[0] === undefined || !['xy', 'spot'].includes(node.pos.form)) return null;
    const to = { ...node, args };
    readPos(to);
    if (!['xy', 'spot'].includes(to.pos.form)) return null;
    const [dx, dy, dz] = [to.pos.x - node.pos.x, (to.pos.y ?? 0) - (node.pos.y ?? 0), to.pos.z - node.pos.z];
    if (!dx && !dy && !dz) return null;
    const raw = p.args[0].raw || '';
    const spots = raw.startsWith('[') && raw.endsWith(']') ? K.splitTop(raw.slice(1, -1)).map(val) : [];
    if (!spots.length || !spots.every((s) => Array.isArray(s) && (s.length === 2 || s.length === 3))) return false;
    // (A spot on the land, [x, z], stays on it unless the thing went up or down.)
    const moved = spots.map((s) => (s.length === 3 ? [s[0] + dx, s[1] + dy, s[2] + dz] : dy ? [s[0] + dx, dy, s[1] + dz] : [s[0] + dx, s[1] + dz]));
    return callText(p.call, [moved, ...p.args.slice(1)], { paren: true });
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

  // A Coin or Enemy tile added before there was a Player got no behaviours (there was nothing to collect it or to
  // chase). The first Player gives them theirs, in the same step: the coin's Collect it, the enemy's Chases and Game
  // over. Only the tiles' own things count (a gold circle of 14, a red 40 × 40 box; in 3D a coin model and a red box
  // you walk through) that have none of those yet. Gives the toast that says so, or null.
  function connectWaiting(pl, V) {
    const { P, is3d } = pl;
    const has = (n, types) => P.behaviours.some((b) => b.V === n.var && types.includes(b.type));
    const coins = P.nodes.filter((n) => n.var && !has(n, ['collect']) && (is3d
      ? n.layer === 'world' && n.kind === 'spawn' && n.args[0] === 'coin'
      : n.layer === 'game' && n.kind === 'circle' && fieldOf(n, 'r') === 14 && fieldOf(n, 'color') === 'gold'));
    const enemies = P.nodes.filter((n) => n.var && !has(n, ['chase', 'hurts']) && (is3d
      ? n.layer === 'world' && n.kind === 'box' && fieldOf(n, 'size') === 1 && fieldOf(n, 'color') === 'red' && n.props.solid?.args[0] === false
      : n.layer === 'game' && n.kind === 'box' && fieldOf(n, 'w') === 40 && fieldOf(n, 'h') === 40 && fieldOf(n, 'color') === 'red'));
    for (const c of coins) pl.beh('collect', c.var, { C: V, P: 1, sound: 'coin' });
    for (const e of enemies) { pl.beh('chase', e.var, { T: V, S: is3d ? 2 : 120 }); pl.beh('hurts', e.var, { T: V, sound: 'lose' }); }
    const names = [...coins, ...enemies].map((n) => n.var);
    if (!names.length) return null;
    const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
    return `${cap(list)} ${names.length === 1 ? 'works' : 'work'} with ${V} now.`;
  }

  const KIT_NATURE = ['tree', 'pine', 'rock', 'bush', 'flower'];
  const KIT_BUILDINGS = ['house', 'hut', 'sign', 'crate', 'fence'];
  const SHAPES3 = { box: ['box', 'box', 'orange'], ball: ['sphere', 'ball', 'teal'], cylinder: ['cylinder', 'cylinder', 'gray'], cone: ['cone', 'cone', 'red'], plane: ['plane', 'plane', 'sand'] };

  // A key no door needs yet (spawn("key")), for a new door.
  const freeKey = (P) => P.nodes.find((m) => m.kind === 'spawn' && m.args[0] === 'key' && m.var
    && !P.nodes.some((d) => d.kind === 'door' && d.props.needs?.args[0]?.raw === m.var));

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
            const first = !firstMover(P);
            const n = nm('player');
            const [x, y] = freeSpot2(P, r(W / 2), r(H - 80));
            put(n, `${n} = ${G}:box(${x}, ${y}, 50, 50, "lime")`, `${n}:on_edge "stop"`);
            pl.beh('arrows', n, { S: 300, dirs: 'all' });
            if (first) say = connectWaiting(pl, n);
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
          // The player gets into cars with F; a car that starts driving (car:drive()) starts with the player in it.
          case 'player': {
            if (P.player) { ide.toast('This world has a player already. A world can have one.'); return null; }
            put(nm('player'), '');
            lines = [`${V} = ${G}:player("first person")`];
            const driven = P.nodes.find((m) => m.kind === 'car' && m.props.drive && m.props.drive.args[0] !== false);
            const inCar = driven ? `${cap(V)} starts in ${driven.var || 'the car'} (F gets out), and gets into cars with F.` : null;
            say = [inCar, connectWaiting(pl, V)].filter(Boolean).join(' ') || null;
            break;
          }
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
          // A car the player gets into with F. With no player yet, one comes with it, standing by its door, so the
          // game can be played straight away (nothing drives by itself when the game starts).
          case 'car': {
            const n = nm('car');
            put(n, `${n} = ${G}:car(${num(X)}, 1, ${num(Z)}, "red")`);
            if (!P.player) {
              // (A car that starts driving already has the player in it: then it starts there, not by this one.)
              const driven = P.nodes.find((m) => m.kind === 'car' && m.props.drive && m.props.drive.args[0] !== false);
              const p = nm('player');
              lines.push(`${p} = ${G}:player("first person")`);
              if (!driven) lines.push(`${p}:move_to(${num(X - 2.5)}, 0, ${num(Z)})`);
              say = [driven ? `${cap(p)} came too: it starts in ${driven.var || 'the car'} (F gets out), and gets into ${n} with F.`
                : `${cap(p)} came too: walk up to ${n} and press F to get in, and F again to get out.`, connectWaiting(pl, p)].filter(Boolean).join(' ');
            } else say = `Walk up to ${n} and press F to get in, and F again to get out.`;
            break;
          }
          case 'ragdoll': put(nm('dummy'), ''); lines = [`${V} = ${G}:ragdoll(${num(X)}, 0, ${num(Z)}, "blue")`]; break;
          // The game kit's level pieces. A door and a key find each other: a new door needs a key no door needs yet,
          // and a new key opens a door that doesn't need one yet (its door:needs line goes after the key's).
          case 'door': {
            const n = nm('door');
            const key = freeKey(P);
            put(n, `${n} = ${G}:door(${num(X)}, 0, ${num(Z)}, "wood")`);
            if (key) { lines.push(`${n}:needs(${key.var})`); say = `${cap(n)} needs ${key.var} now: it's locked until the player picks it up.`; }
            break;
          }
          case 'key': {
            const n = nm('key');
            const door = P.nodes.find((m) => m.kind === 'door' && m.var && !m.props.needs);
            put(n, `${n} = ${G}:spawn("key", ${num(X)}, 0, ${num(Z)})`);
            if (door) { lines.push(`${door.var}:needs(${n})`); say = `${cap(door.var)} needs ${n} now: it's locked until the player picks it up.`; }
            else say = 'Add a Door for the key to open.';
            break;
          }
          case 'jump_pad': put(nm('pad'), ''); lines = [`${V} = ${G}:jump_pad(${num(X)}, 0, ${num(Z)}, 15)`]; break;
          case 'boost_pad': put(nm('boost'), ''); lines = [`${V} = ${G}:boost_pad(${num(X)}, 0, ${num(Z)}, 20)`]; break;
          case 'platform': {
            const n = nm('lift');
            put(n, `${n} = ${G}:box(${num(X)}, 1, ${num(Z)}, [4, 0.4, 4], "stone")`, `${n}:path([[${num(X)}, 1, ${num(Z)}], [${num(X + 8)}, 1, ${num(Z)}]], 3)`);
            break;
          }
          case 'person': {
            const n = nm('person');
            put(n, `${n} = ${G}:spawn("person", ${num(X)}, 0, ${num(Z)})`, `${n}:say("Hi there!", 0)`);
            break;
          }
          case 'island': case 'ground':
            if (P.settings.island || P.settings.ground || P.land) return null;
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
        const [x, y] = id === 'hudtext' ? pl.hudSpot(90, 30) : [];
        put(n, id === 'hudtext' ? `${n} = ${hud}:text("Lives: 3", ${x}, ${y}, 22, "white")` : `${n} = ${hud}:box(${r(W / 2)}, ${r(H - 20)}, 200, 16, "green")`);
      } else if (id.startsWith('pic:')) {
        const rel = id.slice(4);
        const n = nm(rel.split('/').pop().replace(/\.[^.]+$/, ''));
        const wide = (S.picSize.get(rel)?.[0] || 0) > 160;
        if (is3d) {
          const hud = pl.needHud();
          const [x, y] = pl.hudSpot(90, 90);
          put(n, `${n} = ${hud}:image(${JSON.stringify(rel)}, ${x}, ${y}${wide ? ', 128' : ''})`);
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
    // 3D to x, z; patch can also name fields (x, y, w, color...). A thing on a path takes its path with it.
    setArgs(P, node, patch) {
      const pl = plan(P);
      const args = withArgs(node, patch);
      setNodeArgs(pl, node, args);
      const path = pathMoved(node, args);
      if (path) pl.ed.replace(node.props.path.line, path);
      pl.done();
      if (path === false) ide.toast(`${cap(node.var)}'s path has a spot that comes from code, so it stays where it was. Change its spots in the code.`, 'info', 5000);
      return node.key;
    },

    // The player's camera: switching to first person takes its clothes and hair lines out in the same step (nobody
    // sees them, and tgame stops a first-person player's player:shirt with a message).
    setPlayerMode(P, node, mode) {
      const pl = plan(P);
      setNodeArgs(pl, node, withArgs(node, { mode }));
      if (mode !== 'third person') for (const m of LOOKS) if (node.props[m]) pl.ed.remove(node.props[m].line);
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
      // One car has the arrow keys: Drive it on for this one takes the others' drive lines out.
      if (method === 'drive' && args && !PROP_OFF.drive(args)) for (const c of P.nodes) if (c !== node && c.kind === 'car' && c.props.drive) pl.ed.remove(c.props.drive.line);
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
      // (A copy of a car doesn't drive too: one car has the arrow keys. A copy on a path gets its own path, moved as
      // far as the copy is.)
      const path = pathMoved(node, args);
      const props = Object.entries(node.props).filter(([m]) => !(node.kind === 'car' && m === 'drive')).map(([, p]) => p)
        .sort((a, b) => a.line - b.line).map((p) => K.renameIdents(p === node.props.path && path ? path : P.lines[p.line - 1], map));
      pl.ed.insertAfter(ownLast(node), [lineFor(node, args, N), ...props].join('\n'));
      pl.done();
      if (path === false) ide.toast(`${cap(N)} has the same path as ${node.var}: a spot on it comes from code. Change its spots in the code.`, 'info', 5000);
      return `v:${N}`;
    },

    // Deletes a thing: its lines, its behaviours, other things' behaviours that need it (collect by, chase, game over),
    // and the lock of a door it opens (door:needs(key)).
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
      const locks = node.var ? P.nodes.filter((d) => d !== node && d.props.needs?.args[0]?.raw === node.var) : [];
      for (const b of [...own, ...needs]) behLines(P, b).forEach(del);
      for (const d of locks) del(d.props.needs.line);
      pl.done();
      const name = node.var || KIND_LABEL(node).toLowerCase();
      const still = node.var && S.model.getLinesContent().some((l) => wordRe(node.var).test(K.stripComment(l).code));
      if (still) ide.toast(`Removed. Some code still mentions ${node.var}. Check the red marks when you run.`, 'error', 5000);
      else if (needs.length || locks.length) {
        const by = new Map();
        for (const b of needs) { if (!by.has(b.V)) by.set(b.V, []); by.get(b.V).push(BEH[b.type].short); }
        for (const d of locks) { if (!by.has(d.var)) by.set(d.var, []); by.get(d.var).push('lock'); }
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

    // ---- the land (spec: Tuff Engine's Terrain tab). Every one of these is one line, and one Ctrl+Z.
    // Land: land = world:terrain(200) and its style, after the world's settings. With replace, it takes the place of
    // the island or the ground (in the same step).
    addLand(P, replace = false) {
      if (!P.game || P.game.mode !== '3d' || P.land) return null;
      const pl = plan(P);
      const V = pl.nm('land');
      const text = `${V} = ${pl.G}:terrain(200)\n${V}:style "grass"`;
      const old = replace ? P.settings.island || P.settings.ground : null;
      if (old) pl.ed.replace(old.line, text);
      else pl.ed.insertAfter(pl.A.settingsEnd, text);
      pl.done();
      return 'land';
    },

    // A new land line (land:hill(20, -10, 30, 8), a brush stroke...) after the land's last line. Gives its key.
    landEdit(P, op, args) {
      const L = P.land;
      if (!L) return null;
      const pl = plan(P);
      const id = pl.ed.insertAfter(landLast(L), landLine(L.var, op, args));
      const at = pl.done();
      return at && at[id] ? `le:${at[id]}` : 'land';
    },

    setLandEdit(P, e, args) {
      const pl = plan(P);
      pl.ed.replace(e.line, callText(e.call, args, { paren: true }));
      pl.done();
      return e.key;
    },

    removeLandEdit(P, e) {
      const pl = plan(P);
      pl.ed.remove(e.line);
      pl.done();
      ide.toast(`Removed the ${LAND_OPS[e.op].label.toLowerCase()}. Ctrl+Z brings it back.`, 'info', 3000);
      return 'land';
    },

    // The style: its own line (land:style "desert"), or the terrain's second input when that's where it is.
    setLandStyle(P, style) {
      const L = P.land;
      const pl = plan(P);
      if (L.style) pl.ed.replace(L.style.line, callText(L.style.call, [style]));
      else if (typeof L.args[1] === 'string') pl.ed.replace(L.line, callText(L.call, [L.args[0], style], { paren: true }));
      else pl.ed.insertAfter(L.line, `${L.var}:style ${fmt(style)}`);
      pl.done();
      return S.sel;
    },

    setLandSize(P, size) {
      const L = P.land;
      const pl = plan(P);
      const a = L.args.slice();
      a[0] = size;
      pl.ed.replace(L.line, callText(L.call, a, { paren: true }));
      pl.done();
      return 'land';
    },

    // A sea everywhere below a height (land:water(-1)), or none.
    setLandWater(P, level) {
      const L = P.land;
      const pl = plan(P);
      if (level === null) { if (L.water) pl.ed.remove(L.water.line); }
      else if (L.water) pl.ed.replace(L.water.line, callText(L.water.call, [level], { paren: true }));
      else pl.ed.insertAfter(landLast(L), landLine(L.var, 'water', [level]));
      pl.done();
      return S.sel;
    },

    // The land and all of its lines.
    removeLand(P) {
      const L = P.land;
      const pl = plan(P);
      for (const l of landLines(L)) pl.ed.remove(l);
      pl.done();
      const still = S.model.getLinesContent().some((l) => wordRe(L.var).test(K.stripComment(l).code));
      if (still) ide.toast(`Removed the land. Some code still mentions ${L.var}. Check the red marks when you run.`, 'error', 5000);
      else ide.toast('Removed the land. Ctrl+Z brings it back.', 'info', 3000);
      return 'root';
    },
  };

  // ---------------------------------------------------------------- the land's lines
  // What each land line is (and the Terrain tab's tool that writes it): its label, the inputs after its position
  // (their names, and the defaults tgame uses), and a tip. pos: 'xz' (x, z first), 'line' (x1, z1, x2, z2: a
  // valley), or 'spots' for a brush, which takes x, z or a stroke (a list of [x, z] spots).
  const LAND_OPS = {
    hill: { label: 'Hill', pos: 'xz', rest: [['Size', 30], ['Height', 8]], tip: 'A round hill' },
    mountain: { label: 'Mountain', pos: 'xz', rest: [['Size', 60], ['Height', 30]], tip: 'A tall, rocky peak with snow on top' },
    dip: { label: 'Dip', pos: 'xz', rest: [['Size', 16], ['Depth', 3]], tip: 'A hollow in the ground' },
    lake: { label: 'Lake', pos: 'xz', rest: [['Size', 30], ['Depth', 4]], tip: 'A hollow with water in it' },
    valley: { label: 'Valley', pos: 'line', rest: [['Width', 12], ['Depth', 5]], tip: 'A long trench: drag from where it starts to where it ends' },
    raise: { label: 'Raise', pos: 'spots', rest: [['Size', 8], ['Amount', 1]], tip: 'Drag to push the land up' },
    lower: { label: 'Lower', pos: 'spots', rest: [['Size', 8], ['Amount', 1]], tip: 'Drag to dig the land down' },
    smooth: { label: 'Smooth', pos: 'spots', rest: [['Size', 8]], tip: 'Drag to even out bumps' },
    flatten: { label: 'Flatten', pos: 'spots', rest: [['Size', 8], ['Height', 0]], tip: 'Drag to make the land as high as where you start' },
  };
  const BRUSHES = ['raise', 'lower', 'smooth', 'flatten'];
  const SHAPES = ['hill', 'mountain', 'dip', 'lake', 'valley'];
  const STYLES = { grass: '#5a9838', desert: '#dcb57a', snow: '#e8eef4', rocky: '#8a867c', autumn: '#c77537' };
  const landLine = (V, op, args) => (op === 'style' ? `${V}:style ${fmt(args[0])}` : `${V}:${op}(${args.map(fmt).join(', ')})`);

  // A land line read back: { spots: [[x, z]...] | null (x, z are separate inputs), x, z, x2, z2, nums: the rest
  // with tgame's defaults, at: where the rest start }. A stroke's spots are one input, a list of lists.
  function landRead(e) {
    const def = LAND_OPS[e.op];
    const a = e.args;
    const out = { spots: null, nums: [], at: 0, code: false };
    if (def.pos === 'line') {
      if (Array.isArray(a[0]) && Array.isArray(a[1])) { [out.x, out.z] = [a[0][0], a[0][a[0].length - 1]]; [out.x2, out.z2] = [a[1][0], a[1][a[1].length - 1]]; out.at = 2; out.pair = true; }
      else { [out.x, out.z, out.x2, out.z2] = a; out.at = 4; }
    } else if (Array.isArray(a[0])) { [out.x, out.z] = [a[0][0], a[0][a[0].length - 1]]; out.at = 1; out.spot = true; }
    else if (a[0] && a[0].raw && def.pos === 'spots') {
      try { out.spots = JSON.parse(a[0].raw); } catch { out.spots = null; }
      if (!Array.isArray(out.spots) || !out.spots.every((s) => Array.isArray(s) && s.every(isNum))) out.spots = null;
      out.at = 1;
      out.stroke = true;
    } else { [out.x, out.z] = a; out.at = 2; }
    out.code = !out.stroke && ![out.x, out.z, ...(def.pos === 'line' ? [out.x2, out.z2] : [])].every(isNum);
    out.nums = def.rest.map(([, d], j) => { const v = a[out.at + j]; return v === undefined ? d : v; });
    return out;
  }

  // Where an edit is on the land, for the preview's rings: [[x, z, r], ...].
  function landMarks(e) {
    const q = landRead(e);
    const r = isNum(q.nums[0]) ? Math.max(0.5, q.nums[0] / 2) : 4;
    if (q.stroke) return (q.spots || []).slice(0, 40).map(([x, z]) => [x, z, r]);
    if (q.code) return [];
    if (LAND_OPS[e.op].pos === 'line') return [[q.x, q.z, r], [q.x2, q.z2, r]];
    return [[q.x, q.z, r]];
  }

  function landSummary(e) {
    const q = landRead(e);
    if (q.stroke) return q.spots ? `${q.spots.length} ${q.spots.length === 1 ? 'spot' : 'spots'}` : 'a stroke';
    if (q.code) return 'from code';
    if (LAND_OPS[e.op].pos === 'line') return `${num(q.x)}, ${num(q.z)} → ${num(q.x2)}, ${num(q.z2)}`;
    return `${num(q.x)}, ${num(q.z)}`;
  }

  // ---------------------------------------------------------------- templates (spec §15)
  // coin_dash, island_walk and hills_lake are exactly test/tgame/games/coin_dash.tuf, island_walk.tuf and hills_lake.tuf
  // (an e2e check keeps them so).
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
        while coin:touches(player):
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
        while coin:touches(player):
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
    { id: 'hills_lake', name: 'Hills and Lake (3D)', desc: 'Land with a hill, a snowy mountain, a lake and a valley, in modern light. Climb the hill for the coin.', mode: '3d', icon: 'land',
      code: `mention tgame

game = tgame.world("Hills and Lake", 960, 600)
game:sky "day"
game:lighting "modern"
land = game:terrain(200)
land:style "grass"
land:hill(-24, -32, 40, 12)
land:mountain(26, -80, 64, 32)
land:lake(14, -14, 30, 3)
land:valley(44, 24, 76, -46, 16, 6)
hud = game:hud()
score = 0
score_label = hud:text("Score: 0", 90, 30, 26, "white")
player = game:player("first person")
player:move_to(0, 0, 12)
coin = game:spawn("coin", -24, 0, -32)
coin:spin 90
tree = game:spawn("tree", -8, 0, -4)
pine = game:spawn("pine", -34, 0, -24)
pine2 = game:spawn("pine", -16, 0, -44)
tree2 = game:spawn("tree", 34, 0, 0)
rock = game:spawn("rock", 2, 0, -32)

game:every_frame coin_collect

# Tuff Engine: player collects coin
func coin_collect(dt):
    if coin:touches(player):
        score += 1
        score_label:set "Score: " + score
        game:sound "coin"
        coin:move_to(game:random_spot())
        while coin:touches(player):
            coin:move_to(game:random_spot())
` },
  ];

  // ---------------------------------------------------------------- state
  const S = {
    file: null, model: null, sub: null, parsed: null, dump: null, dumpParsed: null, dumpVer: null, join: null, sceneVer: 0,
    sel: 'root', selfEdit: false, version: 0, ready: false, webgl: null, cams: new Map(), assetEpoch: 0, tables: null, busy: false,
    loadSeq: 0, loadedSeq: 0, hostFile: null, hostErr: null, camMode: 'editor', zoom: 'fit', tab: 'add', picSize: new Map(),
    files: [], log: [], asks: new Map(), askNo: 0, timer: null, frameRO: null, typing: null, openStep: null,
    // The Terrain tab's tool (null, or a LAND_OPS name) and each tool's own Size and Strength (or Height / Depth).
    tool: null, tools: {
      raise: { size: 12, amount: 1 }, lower: { size: 12, amount: 1 }, smooth: { size: 12 }, flatten: { size: 12 },
      hill: { size: 30, amount: 8 }, mountain: { size: 60, amount: 30 }, dip: { size: 16, amount: 3 }, lake: { size: 30, amount: 4 }, valley: { size: 18, amount: 6 },
    },
  };
  const host = () => $('#engine');
  const is3d = () => S.parsed?.game?.mode === '3d';
  // The code and its version as they are now: '' and -1 once the file's tab was closed (act() opens it again).
  const live = () => !!S.model && !S.model.isDisposed();
  const codeNow = () => (live() ? S.model.getValue() : '');
  const verNow = () => (live() ? S.model.getAlternativeVersionId() : -1);

  const KIND_LABEL = (n) => {
    if (n.kind === 'spawn') { const m = typeof n.args[0] === 'string' ? n.args[0] : ''; return /\.glb$/i.test(m) ? 'Model' : cap(m || 'Model'); }
    return { box: 'Box', circle: 'Circle', line: 'Line', text: 'Text', image: 'Picture', sphere: 'Ball', cylinder: 'Cylinder', cone: 'Cone', plane: 'Plane', light: 'Light', player: 'Player', car: 'Car', ragdoll: 'Ragdoll', door: 'Door', jump_pad: 'Jump pad', boost_pad: 'Boost pad' }[n.kind] || cap(n.kind);
  };
  // What kind of physics a thing's code gives it: 'off' (no line), 'dynamic', 'static', 'kinematic', or 'code' (worked
  // out by code). A car and a ragdoll always use physics.
  const physicsOf = (n) => {
    if (n.kind === 'car' || n.kind === 'ragdoll') return 'dynamic';
    const p = n.props.physics;
    if (!p) return 'off';
    const a = p.args[0];
    if (a === undefined) return 'dynamic';
    const k = typeof a === 'string' ? a.trim().toLowerCase() : null;
    return PHYSICS_KINDS.includes(k) ? k : 'code';
  };
  // Whether a thing uses physics, from its code (and, once tgame says so in the scene, from what it made: things made
  // by code too).
  const dumpPhysics = (t) => {
    const p = t.physics;
    const k = p && typeof p === 'object' ? p.kind ?? p.type : p;
    return !!p && k !== 'off';
  };
  const usesPhysics = (key, n) => (n && physicsOf(n) !== 'off') || (S.join?.byKey.get(key)?.things || []).some(dumpPhysics);
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
      case 'brush': onBrush(m); break;
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
    renderTerrain();
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
      else if (n && n.kind === 'terrain' && t.kind === 'terrain') { key = 'land'; J.drag.set(t.i, null); }
      else if (n && n.kind !== 'player' && n.kind !== 'terrain') {
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
    // (No line number: every place that shows this adds the line itself.)
    if (t.made.length > 1 && call && P.funcs.some((f) => f.name === call[1])) return `made by ${call[1]}()`;
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
    const land = d.terrain && J.byKey.get('land') ? d.terrain : null;
    const m = {
      tuffHost: 'load', seq: ++S.loadSeq, mode: d.mode, size: d.size, batch: d.batch, things, player, canvas: d.canvas, camera: d.camera, roots: d.roots,
      gameDirRel: ide.rel(dir).replace(/\\/g, '/'), assetEpoch: S.assetEpoch, camMode: S.camMode, select: selIs(), marks: selMarks(),
      terrain: land ? { ids: land.ids, size: land.size, n: land.n, heights: land.heights, lakes: land.lakes, sea: land.sea } : null, tool: toolMsg(),
    };
    if (S.hostFile !== S.file) m.cam = S.cams.get(S.file) || null; // the first load of a file fits the camera; later ones keep it
    S.hostFile = S.file;
    layoutFrame();
    hostPost(m);
  }

  function postSelect() { if (S.ready && S.loadSeq) hostPost({ tuffHost: 'select', is: selIs(), marks: selMarks() }); }

  // Rings on the land where the selected land line works (not while a tool paints: they'd be in the way).
  function selMarks() {
    if (!S.sel.startsWith('le:') || S.tool || !S.parsed) return [];
    const e = find(S.parsed, S.sel);
    return e ? landMarks(e) : [];
  }

  function onPick(m) {
    if (!S.join) return;
    const key = m.i === null ? 'root' : m.i === 'player' ? S.join.playerKey || 'root' : S.join.iToKey.get(m.i) || 'root';
    select(key);
  }

  function onDrag(m) {
    if (m.phase !== 'end' || !S.join || !S.model) return;
    const key = m.i === 'player' ? S.join.playerKey : S.join.iToKey.get(m.i);
    if (!key || key === 'root' || key.startsWith('g:')) return;
    // Lines may have moved since this scene was made: a name still finds its thing, a line number may not. (When the
    // file's tab was closed, act() opens it again and draws a new scene.)
    if (key.startsWith('l:') && (S.model.isDisposed() || S.dumpVer !== S.model.getAlternativeVersionId())) {
      if (S.model.isDisposed()) act(() => null); else requestScene();
      return;
    }
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

  // ---------------------------------------------------------------- the Terrain tab's tools in the preview
  // The host paints its own copy of the heights while the mouse is down (the same maths as tgame), and says what was
  // done when it's let go: brush { tool, spots: [[x, z], ...], size, amount }. Here that becomes one line.
  const toolMsg = () => (S.tool && is3d() && S.camMode === 'editor' && S.parsed?.land ? { kind: S.tool, size: S.tools[S.tool].size, amount: S.tools[S.tool].amount ?? 0 } : null);
  function postTool() { if (S.ready && S.loadSeq) hostPost({ tuffHost: 'tool', tool: toolMsg() }); }

  function setTool(tool) {
    S.tool = tool && LAND_OPS[tool] ? tool : null;
    postTool();
    postSelect();
    if (S.tab === 'terrain') renderTerrain();
    renderHint();
  }

  function onBrush(m) {
    const op = m.tool;
    if (!LAND_OPS[op] || !Array.isArray(m.spots) || !m.spots.length || !S.model) return;
    const r1 = (v) => +(+v).toFixed(1) || 0;
    const spots = m.spots.map(([x, z]) => [r1(x), r1(z)]);
    const size = +num(m.size);
    const amount = +num(m.amount);
    let args;
    if (op === 'valley') {
      const [a, b] = [spots[0], spots[spots.length - 1]];
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1) { ide.toast('Drag from where the valley starts to where it ends.', 'info', 3500); return; }
      args = [a[0], a[1], b[0], b[1], size, amount];
    } else if (BRUSHES.includes(op)) {
      const where = spots.length === 1 ? spots[0] : [spots];
      args = op === 'smooth' ? [...where, size] : [...where, size, amount];
    } else args = [...spots[spots.length - 1], size, amount];
    act((P) => (P.land ? Edits.landEdit(P, op, args) : null));
  }

  // ---------------------------------------------------------------- doing things
  // fn(P) does one edit on a fresh parse and gives the key to select. form: an Inspector field (the form keeps its
  // focus while the scene, Objects and the preview catch up); otherwise everything is drawn again.
  function act(fn, { form = false } = {}) {
    if (!S.model) return;
    if (S.model.isDisposed()) {
      // Its tab was closed while Tuff Engine showed it: open the file again, then do what the kid asked.
      const gone = S.model;
      if (ide.engineVisible()) show(S.file).then(() => { if (S.model && S.model !== gone && !S.model.isDisposed()) act(fn, { form }); });
      return;
    }
    S.parsed = parse(codeNow());
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
    if (!S.model || S.model.isDisposed()) return;
    closeStep();
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
    S.tab = ['add', 'objects', 'assets', 'terrain'].includes(st.engineTab) ? st.engineTab : 'add';
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
              <button data-tab="add" title="Add things">${UI.plus}<span class="lbl">Add</span></button><button data-tab="objects" title="Everything in the game">${UI.grid}<span class="lbl">Objects</span></button><button data-tab="assets" title="Pictures, sounds and models">${ICON.image}<span class="lbl">Assets</span></button><button data-tab="terrain" title="Shape the land: hills, lakes, valleys and brushes">${ICON.land}<span class="lbl">Terrain</span></button>
            </div>
            <div class="en-pane" data-pane="add"><div id="en-add"></div></div>
            <div class="en-pane" data-pane="objects"><div class="sd-layers" id="en-objects"></div></div>
            <div class="en-pane" data-pane="assets"><div class="en-assets" id="en-assets"></div></div>
            <div class="en-pane" data-pane="terrain"><div class="en-terrain" id="en-terrain"></div></div>
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
    sizeLeft($('.en-left'));
    const stage = $('#en-stage');
    stage.addEventListener('wheel', (e) => { if (e.ctrlKey && !is3d()) { e.preventDefault(); setZoom(zoomNow() * (e.deltaY < 0 ? 1.1 : 1 / 1.1)); } }, { passive: false });
    S.frameRO = new ResizeObserver(() => layoutFrame());
    S.frameRO.observe(stage);
    syncFull();
    setTab(S.tab);
  }

  // The Terrain tab is for 3D worlds; a 2D game shows Add instead (and keeps Terrain as the tab to come back to).
  function setTab(tab) {
    S.tab = tab;
    const shown = showTab();
    ide.saveSettings({ engineTab: tab });
    if (shown === 'assets') renderAssets();
    if (shown === 'terrain') renderTerrain();
  }
  function showTab() {
    const shown = S.tab === 'terrain' && S.parsed?.game && !is3d() ? 'add' : S.tab;
    if (shown !== 'terrain' && S.tool) setTool(null);
    $('.en-left')?.classList.toggle('layers', shown !== 'add');
    $$('.en-left .en-tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === shown));
    $$('.en-left .en-pane').forEach((p) => p.classList.toggle('hidden', p.dataset.pane !== shown));
    return shown;
  }

  function setCamMode(mode) {
    S.camMode = mode === 'game' ? 'game' : 'editor';
    $$('#en-cam button').forEach((b) => b.classList.toggle('on', b.dataset.cam === S.camMode));
    hostPost({ tuffHost: 'view', cam: S.camMode });
    postTool();
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
      closeStep();
      S.file = file;
      S.sel = 'root';
      S.dump = null;
      S.dumpParsed = null;
      S.dumpVer = null; // (the last file's version number could match this file's)
      S.join = null;
      S.hostErr = null;
      S.tool = null;
      if (S.loadSeq) $('#en-stage').classList.add('switching'); // the last file's scene hides until this one's is drawn
    }
    const want = S.file;
    const model = await ide.getModel(want);
    if (want !== S.file) return; // another file was asked for meanwhile: that show() draws it
    S.sub?.dispose();
    S.sub = null;
    if (!model) {
      // Nothing to edit. The last file's model goes too (edits would land in the wrong file), and the start card
      // offers what works without one: a template as a new file, or another file.
      ide.toast(`Couldn't open ${ide.basename(S.file)}.`, 'error');
      S.model = null;
      fillFiles();
      render(true);
      return;
    }
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
    closeStep();
    if (S.tool) setTool(null);
    $$('.sd-modal', host()).forEach((m) => m.remove());
  }

  // ---------------------------------------------------------------- drawing the tab
  function render(withForm = true) {
    if (S.model && S.model.isDisposed()) return;
    S.parsed = parse(codeNow());
    const P = S.parsed;
    const kind = $('#en-kind');
    const g = P.game;
    const [W, H] = g ? gameSize(P) : [0, 0];
    kind.textContent = !g ? '' : g.mode === '3d' ? '3D world' : `2D game ${W}×${H}`;
    $('#en-zoom').classList.toggle('hidden', !g || g.mode === '3d');
    $('#en-cam').classList.toggle('hidden', !g || g.mode !== '3d');
    $$('#en-cam button').forEach((b) => b.classList.toggle('on', b.dataset.cam === S.camMode));
    $('#en-undo').disabled = !S.model?.canUndo();
    $('#en-redo').disabled = !S.model?.canRedo();
    renderPlay();
    const start = !g || P.other;
    $('#en-stage').classList.toggle('start', !!start);
    renderStart();
    if (S.sel !== 'root' && !find(P, S.sel) && !(S.sel.startsWith('g:') && S.join?.byKey.has(S.sel))) S.sel = 'root';
    const three = g?.mode === '3d';
    $('.en-tabs [data-tab="terrain"]').classList.toggle('hidden', !three);
    $('.en-tabs').classList.toggle('four', three);
    if (S.tool && !(three && P.land)) setTool(null);
    showTab();
    renderAdd();
    renderTerrain();
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
    const tool = toolMsg() && LAND_OPS[S.tool];
    const how = !tool ? '' : S.tool === 'valley' ? 'Drag on the land from where the valley starts to where it ends'
      : BRUSHES.includes(S.tool) ? `Drag on the land to ${S.tool === 'raise' ? 'raise it' : S.tool === 'lower' ? 'dig it down' : S.tool === 'smooth' ? 'smooth it' : 'flatten it'}`
        : `Click on the land to put a ${tool.label.toLowerCase()} there`;
    h.classList.toggle('en-tooling', !!tool);
    h.textContent = !g || S.parsed.other ? '' : g.mode === '3d'
      ? S.camMode === 'game' ? "The game's camera when it starts. Switch to Editor to move things."
        : tool ? `${how} · Right-drag to look around · Esc puts the tool away`
          : 'Drag a thing to move it · Drag empty space to look around · Shift-drag to pan · Scroll to zoom'
      : 'Click to select · Drag to move · Arrow keys nudge (Shift ×10)';
  }

  function renderStart() {
    const box = $('#en-start');
    if (!box) return;
    const P = S.parsed;
    const show = !P.game || P.other;
    box.classList.toggle('hidden', !show);
    if (!show) return;
    if (!S.model) {
      box.innerHTML = `<div class="en-card">${ICON.pad}<b>Couldn't open ${esc(ide.basename(S.file || 'the game'))}</b><span>Start a new game from a template, or pick another file.</span>
        <div class="en-btns"><button class="btn primary" data-a="tpl">${UI.grid}New game from a template…</button></div>${filePick()}</div>`;
    } else if (P.other) {
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
      else if (d.stopped === 'too-much') html = 'Your code makes something too big for the preview before the game starts (like a very long range), so Tuff Engine stopped there. Press Play to run it.';
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
  // The left panel is as wide as it was last time (340 px at first): drag its right edge, from 260 to 560 px. The
  // handle is in the panel's row, not the panel (which scrolls), so it stays where the edge is.
  const LEFT_KEY = 'tuffcode.engine.leftWidth';
  function sizeLeft(left) {
    const main = left?.parentElement;
    if (!main) return;
    main.classList.add('en-main');
    const set = (w) => main.style.setProperty('--en-left-w', `${Math.round(Math.max(260, Math.min(560, w)))}px`);
    try { const w = +localStorage.getItem(LEFT_KEY); if (w) set(w); } catch { /* no storage: the usual width */ }
    const h = document.createElement('div');
    h.className = 'en-resize';
    h.title = 'Drag to make this panel wider or narrower';
    main.appendChild(h);
    h.onpointerdown = (e) => {
      e.preventDefault();
      h.setPointerCapture(e.pointerId);
      h.classList.add('on');
      const x0 = e.clientX;
      const w0 = left.getBoundingClientRect().width;
      h.onpointermove = (m) => set(w0 + m.clientX - x0);
      h.onpointerup = h.onpointercancel = () => {
        h.onpointermove = h.onpointerup = h.onpointercancel = null;
        h.classList.remove('on');
        layoutFrame();
        try { localStorage.setItem(LEFT_KEY, String(Math.round(left.getBoundingClientRect().width))); } catch { /* not kept */ }
      };
    };
  }

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
      ['Physics', [
        { id: 'car', label: 'Car', icon: ICON.car, tip: 'A car the player gets into with F and drives, with wheels and springs (press Play)' },
        { id: 'ragdoll', label: 'Ragdoll', icon: ICON.ragdoll, tip: 'A floppy person that falls over when it\'s hit (press Play)' },
      ]],
      ['Level pieces', [
        { id: 'door', label: 'Door', icon: ICON.door, tip: 'A door that swings open when the player walks into it (a Key can lock it)' },
        { id: 'key', label: 'Key', icon: ICON.key, tip: 'A key the player picks up to open a locked door' },
        { id: 'jump_pad', label: 'Jump pad', icon: ICON.jump_pad, tip: 'Launches the player up into the air (press Play)' },
        { id: 'boost_pad', label: 'Boost pad', icon: ICON.boost_pad, tip: 'Shoots the player forward the way it faces (press Play)' },
        { id: 'platform', label: 'Moving platform', icon: ICON.platform, tip: 'A platform that moves there and back, and the player rides it (press Play)' },
        { id: 'person', label: 'Talking person', icon: ICON.person, tip: 'A person with a speech bubble over them' },
      ]],
      ['Nature', kit(KIT_NATURE)],
      ['Buildings', kit(KIT_BUILDINGS)],
      ['Shapes', [
        { id: 'box', label: 'Box', icon: ICON.box }, { id: 'ball', label: 'Ball', icon: ICON.ball }, { id: 'cylinder', label: 'Cylinder', icon: ICON.cylinder },
        { id: 'cone', label: 'Cone', icon: ICON.cone }, { id: 'plane', label: 'Plane', icon: ICON.plane },
      ]],
      ['World', [
        { id: 'light', label: 'Light', icon: ICON.light, tip: 'A glowing lamp' },
        { id: 'land', label: 'Land', icon: ICON.land, tip: P.land ? 'Shape it in the Terrain tab' : 'Land to shape with hills, lakes and brushes (the Terrain tab)' },
        { id: 'island', label: 'Island', icon: ICON.island, tip: 'An island in the sea', off: !!(P.settings.island || P.settings.ground || P.land) },
        { id: 'ground', label: 'Ground', icon: ICON.ground, tip: 'Flat grass to stand on', off: !!(P.settings.island || P.settings.ground || P.land) },
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
        b.className = 'sd-tile en-tile en-pv';
        b.dataset.tile = t.id;
        b.title = t.tip ? `${t.label}: ${t.tip}` : t.label;
        b.disabled = !!t.off;
        // Its picture: a picture file's own, the engine's (pvPic), or its icon until that's ready.
        const pic = t.thumb ? null : pvPic(t);
        const shot = t.thumb ? `<img alt="" src="${esc(fileUrl(t.thumb))}">` : pic ? `<img alt="" src="${pic}">` : t.icon;
        b.innerHTML = `<span class="ic en-shot${t.thumb ? ' en-pic' : ''}${pic ? ' real' : ''}">${shot}</span><span class="lbl">${esc(t.label)}</span>`;
        b.onclick = () => clickTile(t.id);
        grid.appendChild(b);
      }
      box.appendChild(grid);
    }
    box.insertAdjacentHTML('beforeend', '<div class="sd-hint">Click to add it to your game. Then drag it where you want it.</div>');
    pvStart(P);
  }

  // ---------------------------------------------------------------- the Add tab's pictures
  // Each tile shows what it adds. In 3D the pictures come from the real game engine: a small program makes each tile's
  // thing (PV3) 40 m apart on grass, tuff.py --scene runs it like any game (ide.scene with its own 'previews' tag, so
  // it never stops the preview of the game being edited), and a second preview page out of sight (#en-pvframe, the
  // same host.js) draws it with its camera on each thing in turn and hands back a picture (ask 'snapshot'). The
  // island and the land get a little program each. They're made once, after the Add tab first shows, in the
  // background (and again when the project's models change); a tile shows its icon until its picture is ready. 2D
  // sprites and the screen's things are flat, so they're drawn here the way the game draws them (pvFlat).
  const PV = { key: null, pics: new Map(), flat: new Map(), job: null, frame: null, ready: null, asks: new Map(), askNo: 0, seq: 0, done: 0 };
  const PV_GAP = 40;
  const PV_AZ = { hut: 30, house: 30 };  // most things face -z (the camera looks at them from the front, a little to the side)
  // Small things that float: the camera looks at the thing itself (its middle, how big it is), not the space under it.
  const PV_AT = { coin: { y: 0.9, size: 0.8 }, key: { y: 0.78, size: 0.6 }, light: { y: 0.55, size: 0.7 } };
  const PV3 = {
    player: (X) => [`it = w:spawn("person", ${X}, 0, 0)`, 'it:shirt("#3574f0")', 'it:pants("#2f3e5c")', 'it:skin("#f1c9a5")', 'it:hair("short", "#5a3a22")', 'it:shoes("#3a2a22")'],
    coin: (X) => [`w:spawn("coin", ${X}, 0, 0)`],
    enemy: (X) => [`w:box(${X}, 0, 0, 1, "red")`],
    chop: (X) => [`w:spawn("tree", ${X}, 0, 0)`],
    car: (X) => [`w:car(${X}, 0, 0, "red")`],
    ragdoll: (X) => [`w:ragdoll(${X}, 0, 0, "blue")`],
    door: (X) => [`w:door(${X}, 0, 0, "wood")`],
    key: (X) => [`w:spawn("key", ${X}, 0, 0)`],
    jump_pad: (X) => [`w:jump_pad(${X}, 0, 0, 15)`],
    boost_pad: (X) => [`w:boost_pad(${X}, 0, 0, 20)`],
    platform: (X) => [`w:box(${X}, 1, 0, [4, 0.4, 4], "stone")`],
    person: (X) => [`w:spawn("person", ${X}, 0, 0)`],
    light: (X) => [`w:light(${X}, 0.4, 0, "gold")`],
    sign: (X) => [`it = w:spawn("sign", ${X}, 0, 0)`, 'it:label("Hello!")'],
  };
  const pvLines = (id, X) => {
    if (PV3[id]) return PV3[id](X);
    if (SHAPES3[id]) { const [kind, , color] = SHAPES3[id]; return [`w:${kind}(${X}, 0, 0, ${kind === 'plane' ? 4 : 1}, "${color}")`]; }
    if (KIT_NATURE.includes(id) || KIT_BUILDINGS.includes(id)) return [`w:spawn("${id}", ${X}, 0, 0)`];
    if (id.startsWith('glb:')) return [`w:spawn(${JSON.stringify(id.slice(4))}, ${X}, 0, 0)`];
    return null;
  };
  // The pictures' programs: the things on grass, the island, and some land with a hill and a lake.
  const pvHead = 'mention tgame\nw = tgame.world("Previews", 640, 480)\nw:sky "day"';
  const PV_WORLDS = {
    island: { src: `${pvHead}\nw:island(30)\n`, cam: { tx: 0, ty: 0, tz: 0, az: 210, el: 24, dist: 62 } },
    land: { src: `${pvHead}\nland = w:terrain(80)\nland:hill(-8, -6, 40, 9)\nland:lake(14, 12, 22, 3)\n`, cam: { tx: 0, ty: 2, tz: 0, az: 210, el: 28, dist: 82 } },
  };

  function pvKey(P) {
    const models = (S.assets?.models || []).filter((f) => f.reach).map((f) => f.rel).sort();
    // (A changed picture or sound doesn't change them: only the models do.)
    return JSON.stringify([P.game?.mode, S.file && ide.rel(S.file.replace(/[\\/][^\\/]*$/, '')), models, models.length ? S.assetEpoch : 0]);
  }

  // The picture for a tile: the engine's (3D), one drawn here (2D and the screen's), or null (its icon for now).
  function pvPic(t) {
    const is3 = S.parsed?.game?.mode === '3d';
    if (is3 && PV.pics.has(t.id)) return PV.pics.get(t.id);
    return pvFlat(t.id, is3);
  }

  // Starts making the 3D pictures if they aren't made (or being made) for this game folder and its models. They're
  // kept while a 2D game shows (pvPic doesn't use them there), so going back to a 3D world doesn't make them again.
  // A run that made none is tried again the next time the tab shows.
  function pvStart(P) {
    if (P.game?.mode !== '3d' || S.webgl === false || !S.file) return;
    const key = pvKey(P);
    if (PV.key === key) return;
    PV.key = key;
    PV.pics.clear();
    const ids = tilesFor(P).flatMap(([, tiles]) => tiles.map((t) => t.id)).filter((id) => pvLines(id, 0));
    const job = PV.job = pvMake(ids, key).catch(() => {}).finally(() => {
      if (PV.job !== job) return;
      PV.job = null;
      pvDrop();
      if (PV.key === key && !PV.pics.size) PV.key = null;
    });
  }

  async function pvMake(ids, key) {
    const file = S.file;
    const lines = [pvHead, 'w:ground("grass", 4000)'];
    const at = [];  // [tile id, the line its thing is made on (1-based)]
    ids.forEach((id, i) => {
      at.push([id, lines.join('\n').split('\n').length + 1]);
      lines.push(...pvLines(id, (i + 1) * PV_GAP));
    });
    const d = await ide.scene(file, `${lines.join('\n')}\n`, 'previews');
    if (PV.key !== key || !d || !Array.isArray(d.things) || !d.batch) return;
    const shots = [{ id: 'ground', cam: { tx: 0, ty: 0, tz: 0, az: 210, el: 20, dist: 9 } }];
    for (const [id, line] of at) {
      const t = d.things.find((x) => x.made?.[0] === line);
      if (!t || !t.dims) continue;
      const k = t.k || [1, 1, 1];
      const [w, h, dep] = [t.dims[0] * k[0], t.dims[1] * k[1], t.dims[2] * k[2]];
      const tile = PV_AT[id];
      // A model file's size is only known once it has loaded in the preview page (fit: framed then, from its box).
      if (id.startsWith('glb:')) { shots.push({ id, fit: t.i, cam: pvCam(id, [t.x, (t.y || 0) + 0.5, t.z], [1, 1, 1]) }); continue; }
      shots.push({ id, cam: pvCam(id, [t.x, (t.y || 0) + (tile ? tile.y : h / 2), t.z], [w, h, dep]) });
    }
    await pvShoot(d, shots, key);
    for (const [id, w] of Object.entries(PV_WORLDS)) {
      if (PV.key !== key) return;
      const dw = await ide.scene(file, w.src, 'previews');
      if (dw && Array.isArray(dw.batch)) await pvShoot(dw, [{ id, cam: w.cam }], key);
    }
  }

  // The camera for a thing whose middle is at `mid` and that is [w, h, d] big: in front of it, a little to the side
  // (the editor camera sees 70 degrees up and down: this far, the thing fills most of the picture).
  function pvCam(id, mid, [w, h, d]) {
    const tile = PV_AT[id];
    const size = tile ? tile.size : Math.max(Math.hypot(w, h, d) * 0.85, 0.4);  // corner to corner: a box's corners show
    const flat = h < 0.3 * Math.max(w, d);
    return { tx: mid[0], ty: mid[1], tz: mid[2], az: PV_AZ[id] ?? 210, el: flat ? 34 : 12, dist: Math.min(60, Math.max(1.1, size * 0.95 + 0.4)) };
  }

  // Waits (up to 4 s) for a model file to load in the preview page, and frames the camera on its box.
  async function pvFit(s) {
    for (let tries = 0; tries < 20; tries++) {
      const r = await pvAsk('box', { i: s.fit });
      const b = r.value;
      if (b && b.min && b.max) {
        const size = [0, 1, 2].map((j) => b.max[j] - b.min[j]);
        return pvCam(s.id, [0, 1, 2].map((j) => (b.min[j] + b.max[j]) / 2), size);
      }
      await new Promise((res) => setTimeout(res, 200));
    }
    return s.cam;
  }

  // Draws a dump in the out-of-sight preview page and takes a picture with each camera.
  async function pvShoot(d, shots, key) {
    if (!(await pvFrame())) return;
    const seq = ++PV.seq;
    const loaded = new Promise((resolve) => { PV.loaded = { seq, resolve }; setTimeout(resolve, 8000); });
    pvPost({
      tuffHost: 'load', seq, mode: d.mode, size: d.size, batch: d.batch, things: d.things.map((t) => ({ ...t, drag: null })), player: null,
      canvas: d.canvas, camera: d.camera, roots: d.roots, gameDirRel: ide.rel(S.file.replace(/[\\/][^\\/]*$/, '')).replace(/\\/g, '/'),
      assetEpoch: S.assetEpoch, camMode: 'editor', cam: shots[0].cam, select: [], marks: [], terrain: null, tool: null,
    });
    await loaded;
    for (const s of shots) {
      if (PV.key !== key) return;
      pvPost({ tuffHost: 'camera', cam: s.fit !== undefined ? await pvFit(s) : s.cam });
      const r = await pvAsk('snapshot');
      if (PV.key !== key) return;
      if (typeof r.value === 'string' && r.value.startsWith('data:image/')) {
        PV.pics.set(s.id, r.value);
        PV.done++;
        const el = $(`#en-add .en-tile[data-tile="${CSS.escape(s.id)}"] .en-shot`);
        if (el) { el.classList.add('real'); el.innerHTML = `<img alt="" src="${r.value}">`; }
      }
    }
  }

  function pvFrame() {
    if (PV.ready) return PV.ready;
    const f = PV.frame = document.createElement('iframe');
    f.id = 'en-pvframe';
    f.title = 'Tuff Engine pictures';
    f.setAttribute('aria-hidden', 'true');
    f.tabIndex = -1;
    f.src = 'tuffview://app/host/index.html';
    PV.ready = new Promise((resolve) => {
      PV.onReady = (ok) => resolve(ok);
      setTimeout(() => resolve(false), 15000);
    });
    document.body.appendChild(f);
    return PV.ready;
  }

  // The pictures are made: the out-of-sight page goes (with its WebGL), until more are wanted.
  function pvDrop() {
    PV.frame?.remove();
    PV.frame = PV.ready = PV.onReady = null;
    for (const r of PV.asks.values()) r({ error: 'gone' });
    PV.asks.clear();
  }

  function pvPost(m) { try { PV.frame?.contentWindow?.postMessage(m, '*'); } catch { /* gone */ } }
  function pvAsk(what, extra = {}) {
    return new Promise((resolve) => {
      const tag = `pv${++PV.askNo}`;
      PV.asks.set(tag, resolve);
      pvPost({ tuffHost: 'ask', tag, what, ...extra });
      setTimeout(() => { if (PV.asks.has(tag)) { PV.asks.delete(tag); resolve({ error: 'no reply' }); } }, 8000);
    });
  }
  function pvMessage(e) {
    if (!PV.frame || e.source !== PV.frame.contentWindow || !e.data || typeof e.data !== 'object') return;
    const m = e.data;
    if (m.tuffHost === 'ready') PV.onReady?.(m.webgl !== false);
    else if (m.tuffHost === 'loaded' && PV.loaded && m.seq === PV.loaded.seq) PV.loaded.resolve();
    else if (m.tuffHost === 'reply') { const r = PV.asks.get(m.tag); if (r) { PV.asks.delete(m.tag); r({ value: m.value, error: m.error }); } }
  }

  // A flat picture, drawn the way the game draws it: 2D sprites on the game's navy, and the screen's text and bars
  // over a sky (3D) or the navy (2D). null: nothing to draw (its icon shows).
  function pvFlat(id, is3) {
    const key = `${is3 ? 3 : 2}:${id}`;
    if (PV.flat.has(key)) return PV.flat.get(key);
    const col = (n) => colors()[n] || n;
    const W = 192;
    const H = 144;
    const c = document.createElement('canvas');
    c.width = W * 2;
    c.height = H * 2;
    const g = c.getContext('2d');
    g.scale(2, 2);
    const sky = () => { const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#8ec5ff'); gr.addColorStop(1, '#d9eeff'); g.fillStyle = gr; g.fillRect(0, 0, W, H); };
    const navy = () => { g.fillStyle = '#1b2440'; g.fillRect(0, 0, W, H); };
    const text = (s, px, color = '#ffffff') => {
      g.font = `bold ${px}px "Segoe UI", system-ui, sans-serif`;
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      g.lineWidth = px / 6;
      g.strokeStyle = 'rgba(0, 0, 0, 0.55)';
      g.strokeText(s, W / 2, H / 2);
      g.fillStyle = color;
      g.fillText(s, W / 2, H / 2);
    };
    const box = (w, h, color) => { g.fillStyle = col(color); g.fillRect((W - w) / 2, (H - h) / 2, w, h); };
    const ball = (r, color) => { g.fillStyle = col(color); g.beginPath(); g.arc(W / 2, H / 2, r, 0, Math.PI * 2); g.fill(); };
    let drawn = true;
    if (id === 'score' || id === 'hudtext') { (is3 ? sky : navy)(); text(id === 'score' ? 'Score: 0' : 'Lives: 3', 26); }
    else if (id === 'hudbox') { navy(); g.fillStyle = 'rgba(0, 0, 0, 0.4)'; g.fillRect(36, 64, 120, 16); g.fillStyle = col('green'); g.fillRect(36, 64, 120, 16); }
    else if (is3) drawn = false;
    else if (id === 'player') { navy(); box(56, 56, 'lime'); }
    else if (id === 'coin') { navy(); ball(22, 'gold'); }
    else if (id === 'enemy') { navy(); box(48, 48, 'red'); }
    else if (id === 'ball') { navy(); ball(16, 'white'); }
    else if (id === 'box') { navy(); box(56, 56, 'orange'); }
    else if (id === 'circle') { navy(); ball(30, 'teal'); }
    else if (id === 'line') { navy(); g.strokeStyle = col('white'); g.lineWidth = 3; g.beginPath(); g.moveTo(46, H / 2); g.lineTo(W - 46, H / 2); g.stroke(); }
    else if (id === 'text') { navy(); text('Hello!', 34); }
    else drawn = false;
    const url = drawn ? c.toDataURL('image/png') : null;
    PV.flat.set(key, url);
    return url;
  }

  async function clickTile(id) {
    if (id === 'draw') {
      if (ide.hasCommand('plugin.sprite-studio.open')) ide.runCommand('plugin.sprite-studio.open');
      else ide.showSideView('plugins', true);
      return;
    }
    if (id === 'pics') { setTab('assets'); return; }
    // Land: made here when nothing is in its way (an island or the ground: the Terrain tab offers to swap them).
    if (id === 'land') {
      setTab('terrain');
      const P = parse(codeNow());
      if (!P.land && !P.settings.island && !P.settings.ground) addLand(false);
      return;
    }
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
    // The land, and each of its lines under it (the order they're made in).
    if (P.land) {
      row('land', ICON.land, 'Land', landStyle(P.land), P.land.var, drawn('land') ? '' : 'en-dim');
      for (const e of P.land.edits) row(e.key, ICON[e.op], LAND_OPS[e.op].label, landSummary(e), '', 'en-edit').title = `Line ${e.line}: ${K.stripComment(e.text).code.trim().slice(0, 120)}`;
    }
    const whatOf = (n) => (n.kind === 'text' || n.kind === 'image' ? (typeof n.args[0] === 'string' ? n.args[0] : '') : n.kind === 'spawn' ? '' : typeof fieldOf(n, 'color') === 'string' ? fieldOf(n, 'color') : '');
    // A badge on the things that use physics: they fall and bump into things when the game runs (the preview doesn't).
    const badge = (b) => {
      b.querySelector('.lb').insertAdjacentHTML('afterend', `<span class="en-phys" title="Uses physics: it falls, bounces and gets pushed when you press Play (the preview doesn't move it)">${ICON.physics}physics</span>`);
      return b;
    };
    const main = P.nodes.filter((n) => n.layer !== 'hud' && n.kind !== 'player');
    for (const n of main) {
      const b = row(n.key, iconFor(n), KIND_LABEL(n), whatOf(n), n.var, drawn(n.key) ? '' : 'en-dim');
      b.title = drawn(n.key) ? '' : 'Not drawn yet';
      if (usesPhysics(n.key, n)) badge(b);
    }
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
        const b = row(gr.key, UI.code, `${count} × ${gr.kind}`, `${gr.why} (line ${gr.line})`, '', 'en-group');
        b.title = `Made by your code on line ${gr.line}: ${gr.why}`;
        if (usesPhysics(gr.key, null)) badge(b);
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

  // A row of small number inputs: [label, value, onChange(number), { step, min, tooSmall }]. The code follows the
  // field as it's typed in (a short pause writes it), and everything typed before the field is left is one undo step.
  // tooSmall: the message for a number under min. While typing, a smaller number (the 1 and 10 of 1000) just isn't
  // written yet; only a field left with one shows the message once, and goes back to the last number that was.
  function numbers(items) {
    const row = document.createElement('div');
    row.className = 'pf en-nums';
    for (const [label, value, onChange, o = {}] of items) {
      const l = document.createElement('label');
      l.className = 'en-num';
      l.innerHTML = `<span>${esc(label)}</span>`;
      const step = { model: null, ver: null };
      let good = isNum(value) ? +num(value) : '';
      const inp = K.control('number', good, {}, (v) => {
        if (v === '' && !o.blank) return;
        if (o.tooSmall && !(v >= o.min)) return;
        good = v;
        S.typing = document.activeElement === inp ? step : null;
        try { onChange(v); } finally { S.typing = null; }
      });
      const leave = () => { if (S.openStep === step) closeStep(); };
      inp.addEventListener('blur', leave);
      inp.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === 'Escape') leave(); });
      if (o.tooSmall) {
        inp.addEventListener('change', () => {
          if (inp.value !== '' && +inp.value >= o.min) return;
          if (inp.value !== '') ide.toast(o.tooSmall, 'error');
          inp.value = good;
        });
      }
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
    if (S.sel === 'land' && P.land) { box.append(...landCard(P)); return; }
    if (S.sel.startsWith('le:') && find(P, S.sel)) { box.append(...editCard(P, find(P, S.sel))); return; }
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
    const small = { min: 100, tooSmall: 'A game is at least 100 wide and 100 high.' };
    const setG = (patch) => act((Q) => Edits.setGame(Q, patch), { form: true });
    const sizes = K.chips(['600×400', '800×600', '960×540'], `${W}×${H}`, (o) => { const [w, h] = o.split('×').map(Number); act((Q) => Edits.setGame(Q, { width: w, height: h })); });
    sizes.classList.add('sizes');
    form.append(sec('Window', [
      fieldEl('Title', textEl(title, (v) => setG({ title: v }))),
      numbers([['Width', W, (v) => setG({ width: Math.round(v) }), small], ['Height', H, (v) => setG({ height: Math.round(v) }), small]]),
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
      // Simple is the default (no line); Modern writes game:lighting "modern".
      const lit = typeof s.lighting?.args[0] === 'string' ? s.lighting.args[0] : 'simple';
      const litSeg = K.control('segment', lit, { options: tbl('lightings', ['simple', 'modern']) }, (v) => set([['lighting', v === 'simple' ? null : [v]]], true));
      litSeg.id = 'en-lighting';
      look.push(fieldEl('Lighting', litSeg, 'Modern: softer light from the sky, and shiny water'));
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
      act((Q) => {
        if (K.takenNames(Q, Q.lines.join('\n')).has(v)) { back(`'${v}' is already used. Pick another name.`); return null; }
        const n = find(Q, key);
        return n ? Edits.rename(Q, n, v) : null;
      });
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
    else if (t && S.dumpVer === verNow() && ['xy', 'spot', 'line'].includes(q.form)) {
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
      form.append(sec('Start spot', [numbers([['X', sx, (v) => mt(v, playerStart(parse(codeNow()))[1])], ['Z', sz, (v) => mt(playerStart(parse(codeNow()))[0], v)]])]));
      const mode = typeof node.args[0] === 'string' ? node.args[0] : 'first person';
      const look = [
        // In first person nobody sees the player, so its clothes and hair lines go with the switch (one undo step).
        fieldEl('Camera', selectEl(tbl('players', ['first person', 'third person']).map((x) => [x, cap(x)]), mode, (v) => fieldAct(key, (Q, n) => Edits.setPlayerMode(Q, n, v), true))),
        numbers([
          ['Facing', isNum(node.props.turn_to?.args[0]) ? node.props.turn_to.args[0] : 0, (v) => setP('turn_to', [v3(v)])],
          ['Walk speed', isNum(node.props.walk_speed?.args[0]) ? node.props.walk_speed.args[0] : 5, (v) => setP('walk_speed', [v3(v)]), { step: 0.5, min: 0 }],
          ['Jump height', isNum(node.props.jump_height?.args[0]) ? node.props.jump_height.args[0] : 1.2, (v) => setP('jump_height', [v3(v)]), { step: 0.1, min: 0 }],
        ]),
        fieldEl('Holds', selectEl([['', 'Nothing'], ...tbl('hold', ['axe', 'pickaxe', 'sword', 'torch', 'hammer']).map((x) => [x, cap(x)])], node.hold?.item || '', (v) => act((Q) => Edits.setHold(Q, v || null)))),
      ];
      form.append(sec('Player', look));
      if (mode === 'third person') form.append(dressSection(node, setP));
      form.append(physicsSection(node, setP));
    } else if (node.kind === 'line') {
      form.append(sec('Where', [numbers([['X1', q.x1, (v) => setA({ x1: v2(v) })], ['Y1', q.y1, (v) => setA({ y1: v2(v) })], ['X2', q.x2, (v) => setA({ x2: v2(v) })], ['Y2', q.y2, (v) => setA({ y2: v2(v) })]])]));
    } else if (is3) {
      const disabled = !posOK;
      const cur = () => { const n = find(parse(codeNow()), key); return n ? n.pos : q; };
      const put3 = (k, v) => { const c = cur(); setA({ x: c.x ?? t?.x ?? 0, y: c.y ?? t?.y ?? 0, z: c.z ?? t?.z ?? 0, [k]: v3(v) }); };
      form.append(sec('Where', [numbers([['X', q.x ?? t?.x, (v) => put3('x', v), { step: 0.5, disabled }], ['Y (bottom)', q.y ?? t?.y, (v) => put3('y', v), { step: 0.5, disabled }], ['Z', q.z ?? t?.z, (v) => put3('z', v), { step: 0.5, disabled }]])]));
    } else {
      const disabled = !posOK;
      const cur = () => { const n = find(parse(codeNow()), key); return n ? n.pos : q; };
      const put2 = (k, v) => { const c = cur(); setA({ x: c.x ?? t?.x ?? 0, y: c.y ?? t?.y ?? 0, [k]: v2(v) }); };
      form.append(sec('Where', [numbers([['X', q.x ?? t?.x, (v) => put2('x', v), { disabled }], ['Y', q.y ?? t?.y, (v) => put2('y', v), { disabled }]])]));
    }
    // What it does comes first (Chases → speed), then how it looks, its physics, and how it moves by itself (not for a
    // thing physics moves, unless its code moves it already: that fights the physics, so it can be taken out here).
    const physical = node.kind === 'car' || node.kind === 'ragdoll';
    const piece = PIECES.includes(node.kind);  // a door and the pads stay where they're put
    const moves = !physical && !piece && (physicsOf(node) !== 'dynamic' || node.props.speed || node.props.spin);
    if (!hud && !physical && !piece && node.kind !== 'player' && node.kind !== 'light') form.append(behSection(P, node));
    if (node.kind !== 'player') form.append(lookSection(P, node, setA, setP));
    if (isPerson(node)) form.append(dressSection(node, setP));
    if (is3 ? PHYSICS_THINGS.includes(node.kind) || physical || piece : !hud && PHYSICS_2D.includes(node.kind)) form.append(physicsSection(node, setP));
    if (!hud && moves && node.kind !== 'player' && node.kind !== 'light') form.append(movesSection(node, setP));
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
    if (key === 'land') { landAct((Q) => Edits.removeLand(Q)); return; }
    if (key.startsWith('le:')) { act((Q) => { const e = find(Q, key); return e ? Edits.removeLandEdit(Q, e) : null; }); return; }
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
      const curSize = () => { const n = find(parse(codeNow()), node.key); const s = n && fieldOf(n, 'size'); return (Array.isArray(s) ? s : size).slice(); };
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
    if (k !== 'image' && k !== 'jump_pad' && k !== 'boost_pad') {  // a pad glows its own colors
      const c = f('color');
      kids.push(fieldEl(colorLabel('Color', c), colorPick(c, (v) => setA({ color: v }))));
    }
    // Which way it faces (thing:turn_to). A boost pad shoots the player that way; a jump pad is round.
    const angle = (title) => ['Angle', isNum(node.props.turn_to?.args[0]) ? node.props.turn_to.args[0] : 0, (v) => setP('turn_to', [v3(v)]), { title }];
    if (k === 'jump_pad' || k === 'boost_pad') {
      kids.push(numbers([['Power', f('power'), (v) => v > 0 && setA({ power: v3(v) }), { step: 1, min: 1, title: k === 'jump_pad' ? 'How hard it launches the player up, in metres a second' : 'How hard it shoots the player forward, in metres a second' }],
        ...(k === 'boost_pad' ? [angle('Which way it shoots the player, in degrees')] : [])]));
      return sec('Pad', kids);
    }
    if (k === 'car' || k === 'door') kids.push(numbers([angle('Which way it faces, in degrees')]));
    if (k === 'light' || k === 'car' || k === 'ragdoll' || k === 'door') return sec('Look', kids);
    if (!is3) {
      kids.push(numbers([
        ['Layer', isNum(node.props.layer?.args[0]) ? node.props.layer.args[0] : 0, (v) => setP('layer', [v2(v)]), { title: 'Higher layers are drawn on top' }],
        ['Angle', isNum(node.props.turn_to?.args[0]) ? node.props.turn_to.args[0] : 0, (v) => setP('turn_to', [v2(v)])],
      ]));
      if (k === 'text') kids.push(fieldEl('Align', K.control('segment', node.props.align?.args[0] || 'center', { options: ['left', 'center', 'right'] }, (v) => setP('align', [v]))));
    } else {
      kids.push(numbers([angle('Which way it faces, in degrees')]));
      const sign = k === 'spawn' && f('model') === 'sign';  // a sign's words are written on its board
      kids.push(fieldEl(sign ? 'Sign text' : 'Label', textEl(typeof node.props.label?.args[0] === 'string' ? node.props.label.args[0] : '', (v) => setP('label', [v])), sign ? 'Written on its board, on both sides' : 'Words shown above it'));
      const glow = typeof node.props.glow?.args[0] === 'string' ? node.props.glow.args[0] : 'none';
      kids.push(fieldEl(colorLabel('Glow', glow), colorPick(glow, (v) => setP('glow', [v]), { none: true })));
      kids.push(fieldEl('Solid', boolEl(node.props.solid?.args[0] !== false, (on) => setP('solid', [on])), 'Off: the player walks through it'));
    }
    kids.push(fieldEl('Hidden at start', boolEl(!!node.props.hide, (on) => setP('hide', on ? [] : null))));
    return sec('Size and look', kids);
  }

  // Physics: everything in a 3D world but a light (a box, ball, cylinder, cone, plane, kit model or model file), and
  // the game's sprites in 2D, is Off (no line), Falls (thing:physics()) or Fixed (thing:physics("static")), with
  // Weight (thing:weight, or a mass line the code has already), Bounce and Friction lines; empty is tgame's own (the
  // Weight field shows what it weighs as it is, from the scene). Off takes those lines out too. A car always uses
  // physics: Start in it (car:drive(): the player starts in it, F gets out), its engine and its weight. A ragdoll
  // always uses physics; the player shoves physics things as hard as its weight lets it; a door swings by itself; a
  // pad is Off or Fixed. Each change is one Ctrl+Z.
  function physicsSection(node, setP) {
    const kids = [];
    const v3 = (v) => +num(v);
    const is3 = node.layer === 'world' || node.kind === 'player';
    const preview = tip(is3 ? "The preview doesn't move it: press Play to see it fall and bump into things." : "The preview doesn't move it: press Play to see it fall and bounce.");
    const n0 = (m) => (isNum(node.props[m]?.args[0]) ? node.props[m].args[0] : '');
    const set = (m, ok) => (v) => { if (v === '') setP(m, null); else if (ok(v)) setP(m, [v3(v)]); };
    // What it weighs as it is (tgame's own, from the scene: a crate 25 kg, a car 1200), for the empty Weight field.
    const auto = { car: 1200, ragdoll: 70, player: 70 }[node.kind] ?? S.join?.byKey.get(node.key)?.things?.[0]?.physics?.auto_weight;
    const wm = node.props.weight || !node.props.mass ? 'weight' : 'mass';
    const weight = ['Weight', n0(wm), set(wm, (v) => v > 0), {
      blank: true, step: is3 ? 5 : 0.5, min: 0, placeholder: isNum(auto) ? String(+num(auto)) : 'auto',
      title: `How heavy it is, in kg: heavy things are hard to push. Empty: what it weighs as it is${isNum(auto) ? ` (${+num(auto)} kg)` : ''}`,
    }];
    const bounce = ['Bounce', n0('bounce'), set('bounce', (v) => v >= 0 && v <= 1), { blank: true, step: 0.1, min: 0, placeholder: 'auto', title: 'How bouncy it is, from 0 (no bounce) to 1' }];
    const friction = ['Friction', n0('friction'), set('friction', (v) => v >= 0), { blank: true, step: 0.1, min: 0, placeholder: 'auto', title: 'How grippy it is: 0 slides like ice' }];
    if (node.kind === 'car') {
      const drive = node.props.drive;
      const on = !!drive && drive.args[0] !== false;
      const engine = node.props.engine?.args[0];
      const player = !!S.parsed?.player;
      kids.push(tip(player ? 'The player walks up to it and presses F to get in, and F again to get out. It drives on the land and crashes into things.'
        : 'Add a Player: they walk up to it and press F to get in, and F again to get out.'));
      kids.push(fieldEl('Start in it', boolEl(on, (v) => setP('drive', v ? [] : null, true)), player ? 'The game starts with the player in it, driving (F gets out)' : 'The arrow keys or WASD drive it from the start'));
      kids.push(numbers([['Engine', isNum(engine) ? engine : 1, (v) => v > 0 && setP('engine', [v3(v)]), { step: 0.5, min: 0.1, title: 'How strong its engine is: 1 is normal' }], weight]));
      kids.push(preview);
      return sec('Car', kids);
    }
    if (node.kind === 'ragdoll') {
      kids.push(tip("A person made of jointed parts that flops over when it's hit or pushed. Push it in your code, like dummy:push(0, 4, -6)."));
      kids.push(numbers([weight, bounce, friction]));
      kids.push(preview);
      return sec('Physics', kids);
    }
    if (node.kind === 'player') {
      kids.push(tip("The player always uses physics: it walks into physics things and shoves them, as hard as its weight lets it (light things slide away, heavy ones don't budge)."));
      kids.push(numbers([weight]));
      return sec('Physics', kids);
    }
    if (node.kind === 'door') {
      kids.push(tip("A door swings on its hinge by itself: it pushes physics things out of its way, but it doesn't fall."));
      return sec('Physics', kids);
    }
    const pad = node.kind === 'jump_pad' || node.kind === 'boost_pad';
    const kind = physicsOf(node);
    const options = pad ? ['off', 'static'] : ['off', 'dynamic', 'static', ...(kind === 'kinematic' ? ['kinematic'] : [])];
    const names = { off: 'Off', dynamic: 'Falls', static: 'Fixed', kinematic: 'Moved by code' };
    const seg = K.control('segment', options.includes(kind) ? kind : null, { options, names }, (v) => {
      if (v === 'off') setP('physics', null, true, PHYSICS_PROPS.slice(1).map((m) => [m, null]));
      else setP('physics', v === 'dynamic' ? [] : [v], true);
    });
    seg.id = 'en-physics';
    $$('.pf-chip', seg).forEach((b, i) => { b.dataset.v = options[i]; });
    kids.push(fieldEl('Physics', seg, kind === 'code' ? 'Its physics comes from code' : kind === 'static' ? 'Fixed: it stays put, and things bump into it and land on it'
      : pad ? "A pad stays where it's put. Fixed: things land on it" : 'Falls: it falls, bounces, tumbles and gets pushed'));
    if (kind === 'off' || pad) return sec('Physics', kids);
    kids.push(numbers([weight, bounce, friction]));
    kids.push(preview);
    return sec('Physics', kids);
  }

  // A person's look: the kit's person (world:spawn("person")), a ragdoll and the player in third person. Each is a
  // line: npc:shirt("red"), npc:pants("black"), npc:skin("tan"), npc:hair("curly", "brown"), npc:shoes("white"),
  // npc:sleeves("short"). Left out, tgame picks (the player has a look of its own).
  const isPerson = (n) => n.kind === 'ragdoll' || (n.kind === 'spawn' && fieldOf(n, 'model') === 'person');
  const HAIR_STYLES = ['short', 'swoop', 'bob', 'ponytail', 'buns', 'curly', 'spiky'];
  const HAIR_WORDS = { pony: 'ponytail', 'pony tail': 'ponytail', tail: 'ponytail', bun: 'buns', afro: 'curly', curls: 'curly', mop: 'curly', spikes: 'spiky', mohawk: 'spiky', quiff: 'swoop', fringe: 'bob', long: 'bob' };  // tgame's HAIR_WORDS
  const SKINS = ['pale', 'light', 'tan', 'medium', 'brown', 'dark'];
  function dressSection(node, setP) {
    const kids = [];
    const a0 = (m) => (typeof node.props[m]?.args[0] === 'string' ? node.props[m].args[0] : '');
    const color = (label, m) => fieldEl(colorLabel(label, node.props[m]?.args[0]), colorPick(a0(m), (v) => setP(m, [v])));
    // hair takes a style and a colour, in either order: the one line keeps both.
    // (tgame's own words for styles count: "pony" is a ponytail. A hair line with something other than text in it
    // comes from code, and stays as it is.)
    const hairAll = node.props.hair?.args || [];
    const hairCode = hairAll.some((v) => typeof v !== 'string');
    const styleOf = (v) => { const w = v.trim().toLowerCase(); const s = HAIR_WORDS[w] || w; return HAIR_STYLES.includes(s) ? s : null; };
    const hairStyle = hairCode ? '' : hairAll.map(styleOf).find(Boolean) || '';
    const hairColor = hairCode ? '' : hairAll.find((v) => !styleOf(v)) || '';
    const setHair = (style, col) => setP('hair', style || col ? [style, col].filter(Boolean) : null);
    const unset = node.kind === 'player' ? 'As it is' : 'Random';
    const pick = (list, cur, run) => selectEl([['', unset], ...(cur && !list.includes(cur) ? [[cur, cur]] : []), ...list.map((x) => [x, cap(x)])], cur, run);
    kids.push(color('Shirt', 'shirt'));
    kids.push(color('Trousers', 'pants'));
    kids.push(fieldEl('Skin', pick(SKINS, a0('skin'), (v) => setP('skin', v ? [v] : null))));
    if (hairCode) kids.push(tip('Its hair comes from code: change it in its hair line.'));
    else {
      kids.push(fieldEl('Hair', pick(HAIR_STYLES, hairStyle, (v) => setHair(v, hairColor))));
      kids.push(fieldEl(colorLabel('Hair colour', hairColor || undefined), colorPick(hairColor, (v) => setHair(hairStyle, v))));
    }
    kids.push(color('Shoes', 'shoes'));
    const sl = a0('sleeves').toLowerCase();
    const sleeves = K.control('segment', sl === 'short' || sl === 'rolled' ? 'short' : sl === 'long' ? 'long' : null,
      { options: ['long', 'short'], names: { long: 'Long', short: 'Short' } }, (v) => setP('sleeves', [v]));
    kids.push(fieldEl('Sleeves', sleeves));
    return sec('Clothes and hair', kids);
  }

  function movesSection(node, setP) {
    const is3 = node.layer === 'world';
    const sp = node.props.speed?.args || [];
    const n0 = (i) => (isNum(sp[i]) ? sp[i] : 0);
    const kids = [];
    const cur = () => { const n = find(parse(codeNow()), node.key); const a = n?.props.speed?.args || []; return [0, 1, 2].map((i) => (isNum(a[i]) ? a[i] : 0)); };
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

  // ---------------------------------------------------------------- the land: the Terrain tab and its Inspector
  const landStyle = (L) => (typeof L.style?.args[0] === 'string' ? L.style.args[0] : typeof L.args[1] === 'string' ? L.args[1] : 'grass');
  const landAct = (fn, form = false) => act((Q) => (Q.land ? fn(Q, Q.land) : null), { form });

  function addLand(replace) {
    if (S.dump?.terrain && !S.parsed?.land) { ide.toast('This world already makes its land in the code (tgame allows one).', 'error'); return; }
    // The camera is fitted again, around the new land.
    S.cams.delete(S.file);
    S.hostFile = null;
    act((Q) => Edits.addLand(Q, replace));
  }

  function styleChips(cur) {
    const names = tbl('terrain_styles', Object.keys(STYLES));
    const el = K.chips(names, names.includes(cur) ? cur : null, (v) => landAct((Q) => Edits.setLandStyle(Q, v)), (o) => `<i class="sw-dot" style="background:${esc(STYLES[o] || '#8a8d94')}"></i>${esc(cap(o))}`);
    el.classList.add('swatches', 'en-styles');
    $$('.pf-chip', el).forEach((b, i) => { b.dataset.style = names[i]; });
    return el;
  }

  // A labelled slider that shows its number: for the Terrain tab's Size and Strength.
  function slider(label, value, [min, max, step], onInput) {
    const l = document.createElement('label');
    l.className = 'en-slider';
    l.innerHTML = `<span class="en-sl-h"><span>${esc(label)}</span><b></b></span><input type="range" min="${min}" max="${max}" step="${step}">`;
    const inp = $('input', l);
    const out = $('b', l);
    inp.value = value;
    out.textContent = num(+inp.value);
    inp.oninput = () => { out.textContent = num(+inp.value); onInput(+inp.value); };
    return l;
  }

  function waterField(L) {
    const level = L.water && isNum(L.water.args[0]) ? L.water.args[0] : null;
    const row = document.createElement('div');
    row.className = 'en-water';
    const sw = boolEl(!!L.water, (on) => landAct((Q) => Edits.setLandWater(Q, on ? -1 : null)));
    sw.title = 'A sea everywhere the land is lower than the sea level';
    const lv = numbers([['Sea level', level ?? -1, (v) => landAct((Q) => Edits.setLandWater(Q, +num(v)), true), { step: 0.5, disabled: !L.water || level === null, title: 'The sea fills the land up to this height' }]]);
    row.append(fieldEl('Sea', sw), lv);
    return row;
  }

  let terrainSig = '';
  function renderTerrain() {
    const box = $('#en-terrain');
    if (!box || !S.parsed) return;
    const P = S.parsed;
    const L = P.land;
    const old = P.settings.island ? 'island' : P.settings.ground ? 'ground' : '';
    const drawn = !!S.join?.byKey.get('land');
    // Drawn again only when what it shows changes (a slider being dragged must stay where it is).
    const sig = JSON.stringify([P.game?.mode, !!P.other, L && [L.var, landStyle(L), L.water?.args[0] ?? null, L.water ? 1 : 0], old, S.tool, drawn, !!S.dump]);
    if (sig === terrainSig && box.firstChild) return;
    terrainSig = sig;
    if (box.firstChild && box.contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
    box.innerHTML = '';
    if (!P.game || P.other || P.game.mode !== '3d') { box.innerHTML = '<div class="sd-hint">Land is for 3D worlds.</div>'; return; }
    if (!L && S.dump?.terrain) {
      const at = S.dump.terrain.made?.[0];
      box.innerHTML = `<div class="sd-hint">Your code makes this world's land${at ? ` on line ${at}` : ''}, in a way Tuff Engine can't shape. Shape it in the code, or make it with a line of its own like <code>land = game:terrain(200)</code>.</div>`;
      return;
    }
    if (!L) {
      const card = document.createElement('div');
      card.className = 'en-landcard';
      card.innerHTML = `<span class="ic big">${ICON.land}</span><b>Make some land</b><span>A square of land 200 wide to shape however you like: hills, mountains, lakes and valleys, with brushes or ready-made shapes.</span>`;
      if (old) card.insertAdjacentHTML('beforeend', `<span class="en-landnote">Your world stands on ${old === 'island' ? 'an island' : 'flat ground'}. The land can take its place.</span>`);
      const btns = document.createElement('div');
      btns.className = 'en-btns';
      btns.innerHTML = old ? `<button class="btn primary" data-a="swap">${ICON.land}Swap the ${old} for land</button><button class="btn sm" data-a="add">Keep the ${old} too</button>`
        : `<button class="btn primary" data-a="add">${ICON.land}Add land</button>`;
      $('[data-a="swap"]', btns)?.addEventListener('click', () => addLand(true));
      $('[data-a="add"]', btns).onclick = () => addLand(false);
      card.appendChild(btns);
      box.appendChild(card);
      return;
    }
    const grid = (title, ops) => {
      box.insertAdjacentHTML('beforeend', `<div class="sd-cat">${esc(title)}</div>`);
      const g = document.createElement('div');
      g.className = 'sd-tiles en-tools';
      for (const op of ops) {
        const b = document.createElement('button');
        b.className = `sd-tile en-tile en-tool${S.tool === op ? ' on' : ''}`;
        b.dataset.tool = op;
        b.title = `${LAND_OPS[op].label}: ${LAND_OPS[op].tip}`;
        b.setAttribute('aria-pressed', S.tool === op ? 'true' : 'false');
        b.innerHTML = `<span class="ic">${ICON[op]}</span><span class="lbl">${esc(LAND_OPS[op].label)}</span>`;
        b.onclick = () => setTool(S.tool === op ? null : op);
        g.appendChild(b);
      }
      box.appendChild(g);
    };
    grid('Brushes', BRUSHES);
    grid('Shapes', SHAPES);
    const set = document.createElement('div');
    set.className = 'en-toolset';
    if (!S.tool) set.innerHTML = '<div class="en-empty">Pick a brush or a shape, then drag or click on the land in the preview. Each one is a line of code, and Ctrl+Z takes it back.</div>';
    else {
      const t = S.tools[S.tool];
      const def = LAND_OPS[S.tool];
      set.insertAdjacentHTML('beforeend', `<div class="en-toolset-h"><span class="ic">${ICON[S.tool]}</span><b>${esc(def.label)}</b><span>${esc(def.tip)}</span></div>`);
      set.append(slider(S.tool === 'valley' ? 'Width' : 'Size', t.size, [2, 60, 1], (v) => { t.size = v; postTool(); }));
      if (S.tool === 'raise' || S.tool === 'lower') set.append(slider('Strength', t.amount, [0.2, 5, 0.1], (v) => { t.amount = v; postTool(); }));
      else if (SHAPES.includes(S.tool)) set.append(slider(def.rest[1][0], t.amount, [0.5, 40, 0.5], (v) => { t.amount = v; postTool(); }));
    }
    box.appendChild(set);
    if (S.dump && !drawn) box.insertAdjacentHTML('beforeend', '<div class="en-empty en-note">The land isn\'t in the preview yet (look for a mistake above it in the code), so the tools wait for it.</div>');
    box.insertAdjacentHTML('beforeend', '<div class="sd-cat">Style</div>');
    box.appendChild(styleChips(landStyle(L)));
    box.insertAdjacentHTML('beforeend', '<div class="sd-cat">Water</div>');
    box.appendChild(waterField(L));
    box.insertAdjacentHTML('beforeend', `<div class="sd-hint">Things stand on the land: their <b>y</b> is how high above it they are. Every shape is listed under <b>Land</b> in Objects.</div>`);
  }

  function editRow(e) {
    const row = document.createElement('div');
    row.className = 'en-erow';
    row.dataset.key = e.key;
    row.innerHTML = `<span class="ic">${ICON[e.op]}</span><span class="lb">${esc(LAND_OPS[e.op].label)}</span><span class="what">${esc(landSummary(e))}</span>`;
    row.title = `Line ${e.line}: ${K.stripComment(e.text).code.trim().slice(0, 120)}`;
    row.onclick = () => select(e.key);
    row.appendChild(xBtn((ev) => { ev.stopPropagation(); act((Q) => { const x = find(Q, e.key); return x ? Edits.removeLandEdit(Q, x) : null; }); }, `Remove this ${LAND_OPS[e.op].label.toLowerCase()}`));
    return row;
  }

  function landCard(P) {
    const L = P.land;
    const out = [head(ICON.land, 'Land', `${L.var} · world:terrain`)];
    out.push(tip('The ground of your world. Shape it in the Terrain tab, or change its lines here.'));
    const form = document.createElement('div');
    form.className = 'in-form';
    form.append(sec('Land', [
      numbers([['Size', isNum(L.args[0]) ? L.args[0] : 200, (v) => landAct((Q) => Edits.setLandSize(Q, Math.min(1000, Math.round(v))), true), { step: 10, min: 10, tooSmall: 'The land is at least 10 wide.', disabled: L.args[0] !== undefined && !isNum(L.args[0]), title: 'How wide the square of land is, in metres' }]]),
      fieldEl(`Style · ${landStyle(L)}`, styleChips(landStyle(L))),
    ]));
    const rows = L.edits.map(editRow);
    // Lines made by code (in a loop or a function) show too, but only the code changes them.
    const d = S.dump?.terrain;
    if (d && S.dumpVer === verNow()) {
      const mine = new Set(landLines(L));
      for (const x of d.edits || []) {
        if (!LAND_OPS[x.op] || (x.made.length === 1 && mine.has(x.made[0]))) continue;
        const r = document.createElement('div');
        r.className = 'en-erow en-yours';
        r.innerHTML = `<span class="ic">${ICON[x.op]}</span><span class="lb">${esc(LAND_OPS[x.op].label)}</span><span class="what">your code, line ${x.made[0]}</span>`;
        r.onclick = () => ide.goToLine(S.file, x.made[0]);
        r.title = 'Made by your code: change it in the code';
        rows.push(r);
      }
    }
    form.append(sec('Shapes and strokes', rows.length ? rows : [tip('Nothing yet: pick a brush or a shape in the Terrain tab.')]));
    form.append(sec('Water', [waterField(L)]));
    out.push(form);
    out.push(actions([
      ['Shape it', ICON.land, () => setTab('terrain'), '', 'Open the Terrain tab'],
      ['Show in code', UI.code, () => ide.goToLine(S.file, L.line)],
      ['Ask an agent about it', ICON.ask, () => openAsk('land')],
      ['Delete', UI.trash, () => removeKey('land'), 'danger', 'Delete the land and all its shapes (Del)'],
    ]));
    return out;
  }

  // A land line's inputs with some changed: x, z (x2, z2 for a valley's end), and n0, n1 (the inputs after them).
  function landArgs(e, patch) {
    const q = landRead(e);
    const def = LAND_OPS[e.op];
    const a = e.args.slice();
    if (['x', 'z', 'x2', 'z2'].some((k) => k in patch)) {
      const x = patch.x ?? q.x;
      const z = patch.z ?? q.z;
      if (def.pos === 'line') {
        const x2 = patch.x2 ?? q.x2;
        const z2 = patch.z2 ?? q.z2;
        if (q.pair) a.splice(0, 2, [x, z], [x2, z2]); else a.splice(0, 4, x, z, x2, z2);
      } else if (q.spot) a[0] = [x, z];
      else a.splice(0, 2, x, z);
    }
    def.rest.forEach(([, d], j) => {
      if (!(`n${j}` in patch)) return;
      for (let k = 0; k < j; k++) if (a[q.at + k] === undefined) a[q.at + k] = def.rest[k][1];
      a[q.at + j] = patch[`n${j}`];
    });
    return a;
  }

  function editCard(P, e) {
    const def = LAND_OPS[e.op];
    const q = landRead(e);
    const key = e.key;
    const out = [head(ICON[e.op], def.label, `${P.land.var}:${e.op} · line ${e.line}`)];
    out.push(tip(q.stroke ? `A ${def.label.toLowerCase()} brush stroke through ${q.spots ? q.spots.length : 'some'} spots on the land.` : `${def.tip}.`));
    const form = document.createElement('div');
    form.className = 'in-form';
    const setE = (patch) => act((Q) => { const x = find(Q, key); return x && x.op === e.op ? Edits.setLandEdit(Q, x, landArgs(x, patch)) : null; }, { form: true });
    const v3 = (v) => +num(v);
    const where = [];
    if (!q.stroke) {
      const o = { step: 0.5, disabled: q.code };
      if (def.pos === 'line') {
        where.push(numbers([['From X', q.x, (v) => setE({ x: v3(v) }), o], ['From Z', q.z, (v) => setE({ z: v3(v) }), o]]));
        where.push(numbers([['To X', q.x2, (v) => setE({ x2: v3(v) }), o], ['To Z', q.z2, (v) => setE({ z2: v3(v) }), o]]));
      } else where.push(numbers([['X', q.x, (v) => setE({ x: v3(v) }), o], ['Z', q.z, (v) => setE({ z: v3(v) }), o]]));
      if (q.code) where.push(tip('This spot comes from code.', 'en-note'));
      form.append(sec('Where', where));
    }
    const nums = def.rest.map(([name], j) => {
      const sizeLike = j === 0;
      const deep = e.op === 'lake' && j === 1;
      const o = sizeLike ? { step: 1, min: 0.5, tooSmall: `The ${name.toLowerCase()} is more than 0.` } : deep ? { step: 0.5, min: 0.1, tooSmall: 'A lake needs some depth.' } : { step: e.op === 'raise' || e.op === 'lower' ? 0.1 : 0.5 };
      const v = q.nums[j];
      return [name, isNum(v) ? v : '', (x) => setE({ [`n${j}`]: v3(x) }), { ...o, disabled: !isNum(v) }];
    });
    form.append(sec(def.label, [numbers(nums)]));
    out.push(form);
    out.push(actions([
      ['The land', ICON.land, () => select('land'), '', 'Back to the land'],
      ['Show in code', UI.code, () => ide.goToLine(S.file, e.line)],
      ['Remove', UI.trash, () => removeKey(key), 'danger', 'Remove this line (Del)'],
    ]));
    return out;
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
        <div class="sd-tbtns"><button class="btn sm primary" data-a="new">New file</button>${S.model ? '<button class="btn sm" data-a="here">Use here</button>' : ''}</div></div>`;
      $('[data-a="new"]', card).onclick = () => { close(); templateAsFile(t); };
      $('[data-a="here"]', card)?.addEventListener('click', () => { close(); templateHere(t); });
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
    if (S.model && !live()) await show(S.file); // its tab was closed: open it again first, so it asks before replacing
    if (!live()) return;
    if (codeNow().trim()) {
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
      if (n && n.op) sel = ` They have the ${LAND_OPS[n.op].label.toLowerCase()} on line ${n.line} selected (a line that shapes the land, ${P.land.var}).`;
      else if (n) sel = ` They have ${n.var || KIND_LABEL(n).toLowerCase()} selected (line ${n.line}).`;
      else if (about.startsWith('g:')) { const g = S.join?.groups.find((x) => x.key === about); if (g) sel = ` They have the ${g.kind}s made on line ${g.line} selected.`; }
    }
    return `(From TuffCode: they're building ${ide.rel(S.file)} in Tuff Engine, TuffCode's visual game editor, as a ${what}. Tuff Engine can only show and edit simple top-level lines, so: make each new thing with one top-level line and plain numbers, like coin = game:circle(200, 200, 14, "gold"); put new lines above any while game:open(): loop; add behaviour as a func registered with a line like game:every_frame coin_spin or coin:clicked coin_clicked.${P?.land ? ` The world's land is ${P.land.var} (world:terrain): shape it with top-level lines like ${P.land.var}:hill(20, -10, 30, 8), and remember every y is the height above the land.` : ''}${sel} Check the file with tuff_check when you're done.)`;
  }

  function openAsk(about) {
    const box = document.createElement('div');
    box.className = 'sd-modal';
    const n = about && about !== 'root' ? find(S.parsed, about) : null;
    const g = about && about.startsWith('g:') ? S.join?.groups.find((x) => x.key === about) : null;
    const subject = n ? (n.op ? `the ${LAND_OPS[n.op].label.toLowerCase()}` : n.var || KIND_LABEL(n).toLowerCase()) : g ? `the ${g.kind}s on line ${g.line}` : '';
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
    const btns = $$('[data-mode]', box);
    btns.forEach((b) => (b.onclick = async () => {
      const text = ta.value.trim();
      if (!text) { ta.focus(); ide.toast('Write what you want first.'); return; }
      if (typeof window.tuffAskAgent !== 'function') {
        ide.toast('Turn on Tuff Agents in Plugins (Alt+3) to ask an agent.', 'info', 5000);
        ide.showSideView('plugins', true);
        return;
      }
      S.lastAsk = { text, mode: b.dataset.mode, note: noteFor(about) };
      btns.forEach((x) => { x.disabled = true; });
      let sent;
      try { sent = await window.tuffAskAgent(text, { mode: b.dataset.mode, note: S.lastAsk.note }); } catch { sent = false; }
      // Not sent (an agent is still replying, or isn't ready: Tuff Agents' toast says which): the box and what the
      // kid wrote stay, to send again. Tuff Agents gives false then; anything else means it went.
      if (sent === false) {
        btns.forEach((x) => { x.disabled = false; });
        if (box.isConnected) ta.focus();
        return;
      }
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
    const landKey = S.sel === 'land' || S.sel.startsWith('le:');
    const thing = node && node !== P.game && !landKey ? node : null;
    if (ctrl && !e.shiftKey && !e.altKey && k === 'd') { if (thing) act((Q) => { const n = find(Q, thing.key); return n ? Edits.duplicate(Q, n) : null; }); return true; }
    if (ctrl || e.altKey) return false;
    if (k === 'Delete' || k === 'Backspace') { if (thing || (landKey && node)) removeKey(S.sel); return true; }
    // Escape puts a Terrain tool away first (and stops what it was painting).
    if (k === 'Escape' && S.tool) { hostPost({ tuffHost: 'cancel' }); setTool(null); return true; }
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
    window.addEventListener('message', pvMessage);
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
    // Edit > Undo and Redo while Tuff Engine shows (ide.js): the game's file, not the hidden code editor's.
    undo: () => undoRedo('undo'),
    redo: () => undoRedo('redo'),
    parse,
    lineFor: (node, args, name) => lineFor(node, args, name),
    fixups,
    templates: () => TEMPLATES.map((t) => ({ ...t })),
    landRead: (e) => landRead(e),
    // A snapshot for tests and DevTools.
    debug: () => ({
      file: S.file, sel: S.sel, ready: S.ready, webgl: S.webgl, busy: S.busy, version: S.version, loadSeq: S.loadSeq, loadedSeq: S.loadedSeq,
      mode: S.parsed?.game?.mode || null, stopped: S.dump?.stopped ?? null, error: S.dump?.error ?? null, ms: S.dump?.ms ?? null,
      things: S.dump?.things?.length ?? 0, keys: S.parsed?.nodes.map((n) => n.key) || [], groups: S.join?.groups.map((g) => ({ key: g.key, why: g.why, n: S.join.byKey.get(g.key)?.is.length })) || [],
      behaviours: S.parsed?.behaviours.map((b) => ({ id: b.id, type: b.type, V: b.V, p: b.p })) || [], banner: $('#en-banner')?.classList.contains('hidden') ? '' : $('#en-banner')?.textContent || '',
      zoom: S.zoom, camMode: S.camMode, cam: S.cams.get(S.file) || null, selIs: selIs(), lastAsk: S.lastAsk || null, dumpCurrent: live() && S.dumpVer === verNow(),
      previews: { made: PV.pics.size, busy: !!PV.job, frame: !!PV.frame }, tab: S.tab, tool: S.tool, land: S.parsed?.land ? { var: S.parsed.land.var, line: S.parsed.land.line, edits: S.parsed.land.edits.map((e) => ({ key: e.key, op: e.op })) } : null,
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
