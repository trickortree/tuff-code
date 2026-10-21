(() => {
  const api = window.tuff;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  // ---------------------------------------------------------------- schema
  const STYLES = ['primary', 'secondary', 'outline', 'ghost', 'success', 'danger'];
  const COLORS = ['accent', 'muted', 'red', 'orange', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink', 'white'];
  const ACCENTS = ['blue', 'purple', 'pink', 'red', 'orange', 'yellow', 'green', 'teal'];
  const GRADIENTS = { blue: ['#3b82f6', '#06b6d4'], purple: ['#8b5cf6', '#ec4899'], pink: ['#ec4899', '#f97316'], red: ['#ef4444', '#f97316'],
    orange: ['#f97316', '#f43f5e'], yellow: ['#eab308', '#f97316'], green: ['#22c55e', '#14b8a6'], teal: ['#14b8a6', '#3b82f6'] };
  const FLAT = { blue: '#3574f0', purple: '#8b5cf6', pink: '#ec4899', red: '#e5484d', orange: '#f97316', yellow: '#e2a508', green: '#22a35a', teal: '#14b8a6' };

  // section: where a setting shows in the inspector (content, size, look, events)
  const A = (key, label, type, def, extra = {}) => ({ key, label, type, def, ...extra });
  const KINDS = {
    heading: { label: 'Heading', name: 'title', args: [A('text', 'Text', 'text', '', { init: 'Heading' })], props: ['color'] },
    text: { label: 'Text', name: 'label', args: [A('text', 'Text', 'text', '', { init: 'Some text' })], props: ['color'] },
    small: { label: 'Small text', name: 'note', args: [A('text', 'Text', 'text', '', { init: 'A small note' })], props: ['color'] },
    button: { label: 'Button', name: 'button', args: [A('text', 'Text', 'text', 'Button', { init: 'Click me' }), A('fn', 'When clicked', 'fn', '', { section: 'events' }), A('style', 'Style', 'style', 'primary', { options: STYLES, section: 'look' })], props: ['speed'] },
    input: { label: 'Text box', name: 'box', args: [A('placeholder', 'Hint text', 'text', '', { init: 'Type here' })], props: ['change', 'enter'] },
    toggle: { label: 'Switch', name: 'switch', args: [A('label', 'Label', 'text', '', { init: 'Switch' }), A('on', 'Starts on', 'bool', false)], props: ['speed', 'change'] },
    checkbox: { label: 'Checkbox', name: 'check', args: [A('label', 'Label', 'text', '', { init: 'Checkbox' }), A('on', 'Starts ticked', 'bool', false)], props: ['speed', 'change'] },
    dropdown: { label: 'Dropdown', name: 'choice', args: [A('options', 'Choices (comma separated)', 'list', [], { init: ['One', 'Two', 'Three'] }), A('value', 'Selected', 'text', '')], props: ['change'] },
    slider: { label: 'Slider', name: 'slider', args: [A('min', 'Lowest', 'number', 0), A('max', 'Highest', 'number', 100), A('value', 'Starts at', 'number', '', { init: 50 })], props: ['change'] },
    progress: { label: 'Progress bar', name: 'bar', args: [A('value', 'Percent', 'number', 0, { init: 50 })], props: ['speed'] },
    spinner: { label: 'Spinner', name: 'spinner', args: [A('label', 'Label', 'text', '', { init: 'Loading...' }), A('size', 'Size', 'number', 28, { section: 'look' })], props: ['speed'] },
    clock: { label: 'Clock', name: 'clock', args: [A('style', 'Style', 'segment', 'analog', { options: ['analog', 'digital'], section: 'look' }), A('size', 'Size', 'number', 160, { section: 'look' })], props: ['time', 'speed'] },
    image: { label: 'Image', name: 'picture', args: [A('path', 'Image file', 'text', '', { init: 'logo.png', hint: 'A .png or .gif in your project folder' }), A('width', 'Max width', 'number', '', { section: 'look' })], props: [] },
    divider: { label: 'Divider', name: null, args: [], props: [] },
    space: { label: 'Space', name: null, args: [A('size', 'Size', 'number', 12, { init: 20, section: 'look' })], props: [] },
    row: { label: 'Row', name: 'row', container: true, args: [], props: [] },
    card: { label: 'Card', name: 'card', container: true, args: [], props: [] },
    // A page of the window: only one shows at a time. Widgets on the window itself show on every page.
    page: { label: 'Page', name: 'page', container: true, args: [A('title', 'Page name', 'text', '', { init: 'Page 2' })], props: ['opened'] },
  };
  const WINDOW = { label: 'Window', args: [A('title', 'Title', 'text', 'My App'), A('width', 'Width', 'number', 420, { section: 'size' }), A('height', 'Height', 'number', 520, { section: 'size' })], props: ['theme', 'accent', 'gradient'] };
  const PROPS = {
    speed: { label: 'Animation speed', type: 'speed', method: 'speed', section: 'look', hint: '1 is normal, 2 is twice as fast, 0.5 is half speed' },
    color: { label: 'Text color', type: 'color', method: 'color', section: 'look' },
    time: { label: 'Start time', type: 'time', method: 'set', section: 'content', hint: 'Leave empty to show the real time' },
    theme: { label: 'Theme', type: 'segment', options: ['', 'dark', 'light'], names: { '': 'Default' }, method: 'theme', section: 'look' },
    accent: { label: 'Accent color', type: 'accent', method: 'accent', section: 'look' },
    gradient: { label: 'Custom gradient', type: 'gradient', method: 'gradient', section: 'look', modernOnly: true, hint: 'Overrides the accent colors in mtgui' },
    change: { label: 'When it changes', type: 'fn', method: 'change', section: 'events' },
    opened: { label: 'When this page opens', type: 'fn', method: 'opened', section: 'events' },
    enter: { label: 'When Enter is pressed', type: 'fn', method: 'enter', section: 'events' },
  };
  const CHANGE_LABELS = { input: 'When the text changes', toggle: 'When switched on or off', checkbox: 'When ticked or unticked', dropdown: 'When a choice is picked', slider: 'When it moves' };
  const SECTIONS = [['content', 'Content'], ['size', 'Size'], ['look', 'Look'], ['events', 'Events']];
  const SIZES = [['Small', 360, 480], ['Medium', 420, 560], ['Large', 560, 680], ['Wide', 800, 560]];
  const CATS = [
    ['Text', ['heading', 'text', 'small']],
    ['Buttons and inputs', ['button', 'input', 'toggle', 'checkbox', 'dropdown', 'slider']],
    ['Progress and time', ['progress', 'spinner', 'clock']],
    ['Layout', ['page', 'card', 'row', 'divider', 'space']],
    ['Media', ['image']],
  ];
  // Which bit of a widget's preview is its label, for double-click editing (argument index).
  const INLINE = { heading: 0, text: 0, small: 0, button: 0, toggle: 0, checkbox: 0, spinner: 0 };

  const svg = (d, extra = '') => `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"${extra}>${d}</svg>`;
  const ICONS = {
    heading: svg('<path d="M3.5 3v10M10.5 3v10M3.5 8h7M13 6.5v6"/>'),
    text: svg('<path d="M3 3.5h10M8 3.5v9.5"/>'),
    small: svg('<path d="M4.5 6.5h7M8 6.5v6"/>'),
    button: svg('<rect x="1.5" y="4.5" width="13" height="7" rx="3.5"/><path d="M5.5 8h5"/>'),
    input: svg('<rect x="1.5" y="4" width="13" height="8" rx="2"/><path d="M4.5 6.5v3"/>'),
    toggle: svg('<rect x="1.5" y="4.5" width="13" height="7" rx="3.5"/><circle cx="10.8" cy="8" r="1.9"/>'),
    checkbox: svg('<rect x="2.5" y="2.5" width="11" height="11" rx="2.5"/><path d="M5.5 8.2l1.8 1.8 3.3-3.6"/>'),
    dropdown: svg('<rect x="1.5" y="4" width="13" height="8" rx="2"/><path d="M9.5 7.2l1.4 1.4 1.4-1.4"/>'),
    slider: svg('<path d="M1.5 8h13"/><circle cx="6" cy="8" r="2.2" fill="currentColor" stroke="none"/>'),
    progress: svg('<rect x="1.5" y="6" width="13" height="4" rx="2"/><path d="M3.5 8h5.5" stroke-width="2.2"/>'),
    spinner: svg('<path d="M8 2.5a5.5 5.5 0 1 1-5.5 5.5"/>'),
    clock: svg('<circle cx="8" cy="8" r="5.8"/><path d="M8 4.8V8l2.2 1.6"/>'),
    image: svg('<rect x="1.5" y="2.5" width="13" height="11" rx="2"/><circle cx="5.8" cy="6.3" r="1.3"/><path d="M2 12l3.6-3.5 2.6 2.6 2-2 3.8 3.4"/>'),
    divider: svg('<path d="M2 8h12"/><path d="M2 4.5h12M2 11.5h12" opacity=".35"/>'),
    space: svg('<path d="M8 2v12M5.5 4.5L8 2l2.5 2.5M5.5 11.5L8 14l2.5-2.5"/>'),
    row: svg('<rect x="1.5" y="4" width="5.6" height="8" rx="1.4"/><rect x="8.9" y="4" width="5.6" height="8" rx="1.4"/>'),
    card: svg('<rect x="1.5" y="2.5" width="13" height="11" rx="2.6"/><path d="M4.5 6h7M4.5 9h4.5"/>'),
    page: svg('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M9.5 1.8v3.5H13"/><path d="M2.5 4v11.5h8"/>'),
    window: svg('<rect x="1.5" y="2.5" width="13" height="11" rx="2"/><path d="M1.5 5.5h13"/>'),
  };
  const UI = {
    undo: svg('<path d="M5.5 4L2.5 7l3 3"/><path d="M2.5 7H10a3.5 3.5 0 010 7H7"/>'),
    redo: svg('<path d="M10.5 4l3 3-3 3"/><path d="M13.5 7H6a3.5 3.5 0 000 7h3"/>'),
    minus: svg('<path d="M4 8h8"/>'),
    plus: svg('<path d="M4 8h8M8 4v8"/>'),
    up: svg('<path d="M8 13V3M4 7l4-4 4 4"/>'),
    down: svg('<path d="M8 3v10M4 9l4 4 4-4"/>'),
    dup: svg('<rect x="5" y="5" width="8.5" height="8.5" rx="1.8"/><path d="M11 3.2A1.8 1.8 0 009.5 2.5H4.3a1.8 1.8 0 00-1.8 1.8v5.2c0 .7.3 1.2.8 1.5"/>'),
    trash: svg('<path d="M2.5 4.5h11M6.5 4.5V3h3v1.5M4 4.5l.7 9h6.6l.7-9"/>'),
    code: svg('<path d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5"/>'),
    play: '<svg viewBox="0 0 16 16"><path fill="currentColor" d="M5 3.6c0-.8.9-1.3 1.6-.85l6.2 4.1c.6.4.6 1.3 0 1.7l-6.2 4.1C5.9 13.1 5 12.6 5 11.8z"/></svg>',
    grid: svg('<rect x="2" y="2" width="5" height="5" rx="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2"/><rect x="9" y="9" width="5" height="5" rx="1.2"/>'),
    search: svg('<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>'),
    close: svg('<path d="M4 4l8 8M12 4l-8 8"/>'),
    palette: svg('<path d="M8 1.8a6.2 6.2 0 100 12.4c1 0 1.4-.6 1.4-1.3 0-.9-.8-1.2-.8-2 0-.7.6-1.2 1.4-1.2h1.6a2.6 2.6 0 002.6-2.6C14.2 4.3 11.4 1.8 8 1.8z"/><circle cx="5" cy="7" r=".9" fill="currentColor"/><circle cx="7.6" cy="4.6" r=".9" fill="currentColor"/><circle cx="10.6" cy="5.6" r=".9" fill="currentColor"/>'),
    fit: svg('<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>'),
    arrow: svg('<path d="M6 3.5L10.5 8 6 12.5"/>'),
    expand: svg('<path d="M9.5 2.5h4v4M13.5 2.5L9 7M6.5 13.5h-4v-4M2.5 13.5L7 9"/>'),
    shrink: svg('<path d="M13.5 6.5h-4v-4M9.5 6.5l4.5-4.5M2.5 9.5h4v4M6.5 9.5L2 14"/>'),
  };
  const kindInfo = (n) => (n.kind === 'window' ? WINDOW : KINDS[n.kind]);
  const tipFor = (kind) => window.TUFF_METHOD_DOCS?.[kind]?.[1] || '';

  const TEMPLATES = window.TUFF_TEMPLATES || [];

  // ---------------------------------------------------------------- parsing
  function stripComment(line) {
    let quote = null;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (quote) {
        if (c === '\\') i++;
        else if (c === quote) quote = null;
      } else if (c === '"' || c === "'") quote = c;
      else if (c === '#') return { code: line.slice(0, i).trimEnd(), comment: line.slice(i) };
    }
    return { code: line.trimEnd(), comment: '' };
  }

  function splitTop(s) {
    const parts = [];
    let depth = 0, quote = null, cur = '';
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (quote) {
        cur += c;
        if (c === '\\') { cur += s[++i] ?? ''; continue; }
        if (c === quote) quote = null;
        continue;
      }
      if (c === '"' || c === "'") quote = c;
      else if (c === '(' || c === '[') depth++;
      else if (c === ')' || c === ']') depth--;
      else if (c === ',' && depth === 0) { parts.push(cur); cur = ''; continue; }
      cur += c;
    }
    if (cur.trim() || parts.length) parts.push(cur);
    return parts.map((p) => p.trim());
  }

  function closesAtEnd(s) {
    let depth = 0, quote = null;
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (quote) { if (c === '\\') i++; else if (c === quote) quote = null; continue; }
      if (c === '"' || c === "'") quote = c;
      else if (c === '(') depth++;
      else if (c === ')') { depth--; if (depth === 0) return i === s.length - 1; }
    }
    return false;
  }

  function parseValue(raw) {
    raw = raw.trim();
    if (!raw || raw === 'nil') return { kind: 'empty', value: '' };
    const str = raw.match(/^"((?:[^"\\]|\\.)*)"$/) || raw.match(/^'((?:[^'\\]|\\.)*)'$/);
    if (str) return { kind: 'string', value: str[1].replace(/\\(.)/g, (_, c) => ({ n: '\n', t: '\t' })[c] || c) };
    if (/^-?\d+(\.\d+)?$/.test(raw)) return { kind: 'number', value: Number(raw) };
    if (raw === 'true' || raw === 'false') return { kind: 'bool', value: raw === 'true' };
    if (raw.startsWith('[') && raw.endsWith(']')) {
      const items = splitTop(raw.slice(1, -1)).filter(Boolean).map(parseValue);
      if (items.every((v) => v.kind === 'string' || v.kind === 'number')) return { kind: 'list', value: items.map((v) => String(v.value)) };
    }
    if (/^[A-Za-z_]\w*$/.test(raw)) return { kind: 'name', value: raw };
    return { kind: 'raw', value: raw };
  }

  function parseArgs(rest) {
    rest = rest.trim();
    if (!rest) return [];
    if (rest.startsWith('(') && closesAtEnd(rest)) return splitTop(rest.slice(1, -1)).map(parseValue);
    return [parseValue(rest)];
  }

  const TYPE_OK = { text: ['string'], number: ['number'], bool: ['bool'], fn: ['name'], select: ['string'], style: ['string'], segment: ['string'], list: ['list'] };
  function valuesFor(info, args) {
    return info.args.map((a, i) => {
      const arg = args[i];
      if (!arg || arg.kind === 'empty') return undefined;
      if ((TYPE_OK[a.type] || []).includes(arg.kind)) return arg.value;
      return { raw: arg.kind === 'string' ? JSON.stringify(arg.value) : String(arg.value) };
    });
  }

  const UI_RE = new RegExp(`^(?:([A-Za-z_]\\w*)\\s*=\\s*)?([A-Za-z_]\\w*):(${Object.keys(KINDS).join('|')})\\b\\s*(.*)$`);
  const PROP_RE = /^([A-Za-z_]\w*):(speed|color|set|theme|accent|gradient|change|enter|opened)\b\s*(.*)$/;

  function parse(code) {
    const lines = code.split(/\r?\n/);
    const res = { lib: null, importLine: 0, win: null, nodes: [], byVar: {}, funcs: [], lineCount: lines.length };
    lines.forEach((full, i) => {
      const ln = i + 1;
      if (/^\s/.test(full) || !full.trim()) return;
      const { code: line, comment } = stripComment(full);
      let m;
      if ((m = line.match(/^func\s+([A-Za-z_]\w*)/))) { res.funcs.push({ name: m[1], line: ln }); return; }
      if ((m = line.match(/^(import|mention)\s+(m?tgui)\b/))) { res.lib = m[2]; res.importLine = ln; return; }
      if ((m = line.match(/^([A-Za-z_]\w*)\s*=\s*(m?tgui)\.window\b\s*(.*)$/))) {
        const args = parseArgs(m[3]);
        res.win = { kind: 'window', var: m[1], lib: m[2], line: ln, comment, values: valuesFor(WINDOW, args), props: {}, children: [] };
        res.byVar[m[1]] = res.win;
        return;
      }
      if ((m = line.match(UI_RE))) {
        const parent = res.byVar[m[2]];
        if (parent && (parent.kind === 'window' || KINDS[parent.kind]?.container) && (m[3] !== 'page' || parent.kind === 'window')) {
          const node = { kind: m[3], var: m[1] || null, parentVar: m[2], parent, line: ln, comment, values: valuesFor(KINDS[m[3]], parseArgs(m[4])), props: {}, children: [] };
          res.nodes.push(node);
          parent.children.push(node);
          if (node.var) res.byVar[node.var] = node;
          return;
        }
      }
      if ((m = line.match(PROP_RE))) {
        const owner = res.byVar[m[1]];
        if (!owner) return;
        const key = m[2] === 'set' ? (owner.kind === 'clock' ? 'time' : null) : m[2];
        if (key && kindInfo(owner).props.includes(key)) owner.props[key] = { line: ln, args: parseArgs(m[3]) };
      }
    });
    return res;
  }

  function propValue(node, key) {
    const p = node.props[key];
    if (key === 'gradient') return p ? p.args.map((a) => (a.kind === 'string' ? a.value : '')) : null;
    if (!p) return '';
    if (key === 'time') {
      const [h, mi] = p.args.map((a) => (a.kind === 'number' ? a.value : 0));
      return `${String(h ?? 0).padStart(2, '0')}:${String(mi ?? 0).padStart(2, '0')}`;
    }
    const a = p.args[0];
    return a && a.kind !== 'empty' ? a.value : '';
  }

  const isInside = (node, ancestor) => { for (let n = node?.parent; n; n = n.parent) if (n === ancestor) return true; return false; };
  const walk = (node, fn) => { fn(node); for (const c of node.children) walk(c, fn); };

  // ---------------------------------------------------------------- code generation
  function fmt(v, type) {
    if (v && typeof v === 'object' && 'raw' in v) return v.raw;
    if (type === 'number') return String(Number(v) || 0);
    if (type === 'bool') return v ? 'true' : 'false';
    if (type === 'fn') return v || 'nil';
    if (type === 'list') return '[' + (v || []).map((x) => JSON.stringify(String(x))).join(', ') + ']';
    return JSON.stringify(String(v ?? ''));
  }

  const isBlank = (v) => v === undefined || v === '' || v === null || (Array.isArray(v) && !v.length);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  function argText(info, values) {
    const parts = info.args.map((a, i) => values[i]);
    while (parts.length) {
      const i = parts.length - 1;
      const v = parts[i];
      if (isBlank(v) || (i > 0 && same(v, info.args[i].def))) parts.pop();
      else break;
    }
    const out = parts.map((v, i) => {
      const a = info.args[i];
      if (isBlank(v)) return a.type === 'fn' ? 'nil' : fmt(isBlank(a.def) ? (a.type === 'number' ? 0 : '') : a.def, a.type);
      return fmt(v, a.type);
    });
    if (!out.length) return '';
    if (out.length === 1 && /^("|-?\d)/.test(out[0])) return ' ' + out[0];
    return '(' + out.join(', ') + ')';
  }

  function lineFor(node, varName = node.var) {
    const comment = node.comment ? '  ' + node.comment : '';
    if (node.kind === 'window') return `${varName} = ${node.lib}.window${argText(WINDOW, node.values)}${comment}`;
    return `${varName ? varName + ' = ' : ''}${node.parentVar}:${node.kind}${argText(KINDS[node.kind], node.values)}${comment}`;
  }

  function propLine(varName, key, value) {
    const p = PROPS[key];
    if (key === 'time') {
      const [h, m] = String(value).split(':').map((x) => parseInt(x, 10) || 0);
      return `${varName}:set(${h}, ${m})`;
    }
    if (key === 'speed') return `${varName}:speed ${Number(value) || 1}`;
    if (key === 'change' || key === 'enter' || key === 'opened') return `${varName}:${key} ${value}`;
    if (key === 'gradient') return `${varName}:gradient(${JSON.stringify(value[0])}, ${JSON.stringify(value[1])})`;
    return `${varName}:${p.method} ${JSON.stringify(String(value))}`;
  }

  function takenNames(parsed, code) {
    const taken = new Set([...Object.keys(parsed.byVar), ...parsed.funcs.map((f) => f.name)]);
    for (const m of code.matchAll(/\b([A-Za-z_]\w*)\s*=(?!=)/g)) taken.add(m[1]);
    return taken;
  }

  function freeName(parsed, base, code) {
    const taken = takenNames(parsed, code);
    return taken.has(base) ? uniqueVar(parsed, base, code) : base;
  }

  function uniqueVar(parsed, base, code, extra = []) {
    const taken = takenNames(parsed, code);
    for (const n of extra) taken.add(n);
    for (let i = 1; ; i++) {
      const name = `${base}${i}`;
      if (!taken.has(name)) return name;
    }
  }

  // Rename identifiers in one line of code, skipping strings, comments, .members and :methods.
  function renameIdents(line, map) {
    let out = '';
    let quote = null;
    for (let i = 0; i < line.length;) {
      const c = line[i];
      if (quote) {
        out += c;
        if (c === '\\') { out += line[i + 1] ?? ''; i += 2; continue; }
        if (c === quote) quote = null;
        i++;
        continue;
      }
      if (c === '"' || c === "'") { quote = c; out += c; i++; continue; }
      if (c === '#') { out += line.slice(i); break; }
      const m = /^[A-Za-z_]\w*/.exec(line.slice(i));
      if (m) {
        const prev = line[i - 1];
        const own = Object.prototype.hasOwnProperty.call(map, m[0]);
        out += own && prev !== '.' && prev !== ':' ? map[m[0]] : m[0];
        i += m[0].length;
        continue;
      }
      out += c;
      i++;
    }
    return out;
  }

  // ---------------------------------------------------------------- applying edits
  function linesOf(node) {
    const set = new Set([node.line, ...Object.values(node.props).map((p) => p.line)]);
    for (const c of node.children) for (const l of linesOf(c)) set.add(l);
    return [...set].sort((a, b) => a - b);
  }
  const ownLast = (node) => Math.max(node.line, ...Object.values(node.props).map((p) => p.line));
  function uiLast(parsed, exclude) {
    const skip = new Set(exclude ? linesOf(exclude) : []);
    const all = [parsed.win.line, ...Object.values(parsed.win.props).map((p) => p.line)];
    for (const n of parsed.nodes) all.push(...linesOf(n));
    return Math.max(...all.filter((l) => !skip.has(l)));
  }

  // Line after which a new child goes, so it ends up at `index` among the container's children.
  function insertLine(parsed, container, index, exclude) {
    const sibs = container.children.filter((c) => c !== exclude);
    if (index < sibs.length) return Math.min(...linesOf(sibs[index])) - 1;
    if (container.kind === 'window') return uiLast(parsed, exclude);
    const skip = new Set(exclude ? linesOf(exclude) : []);
    return Math.max(...linesOf(container).filter((l) => !skip.has(l)));
  }

  // Collects line edits, then applies them to the model as one small change (one undo step).
  function makeEditor(model) {
    const eol = model.getEOL();
    const old = model.getLinesContent();
    const rep = new Map();
    const del = new Set();
    const ins = new Map();
    let tokens = 0;
    return {
      eol,
      line: (ln) => old[ln - 1] ?? '',
      replace(ln, text) { rep.set(ln, text); },
      insertAfter(ln, text) {
        const id = ++tokens;
        if (!ins.has(ln)) ins.set(ln, []);
        ins.get(ln).push({ id, text });
        return id;
      },
      remove(ln) { del.add(ln); },
      // finish(lines) -> lines: a last pass over the whole new text, inside the same undo step (Tuff Engine's fixups).
      commit(finish) {
        const out = [];
        const at = {};
        let count = 0;
        const push = (text) => { out.push(text); count += String(text).split(/\r?\n/).length; };
        const flush = (ln) => { for (const it of ins.get(ln) || []) { at[it.id] = count + 1; push(it.text); } };
        flush(0);
        old.forEach((text, i) => {
          const ln = i + 1;
          if (!del.has(ln)) push(rep.has(ln) ? rep.get(ln) : text);
          flush(ln);
        });
        let next = out.join(eol).split(/\r?\n/);
        if (finish) next = finish(next);
        let a = 0;
        while (a < old.length && a < next.length && old[a] === next[a]) a++;
        let b = 0;
        while (b < old.length - a && b < next.length - a && old[old.length - 1 - b] === next[next.length - 1 - b]) b++;
        if (a === old.length && a === next.length) return at;
        const oldMid = old.slice(a, old.length - b);
        const newMid = next.slice(a, next.length - b);
        const startOf = (i) => old.slice(0, i).reduce((s, l) => s + l.length + eol.length, 0);
        let start, end, text;
        if (!oldMid.length) {
          if (b > 0) { start = end = startOf(a); text = newMid.join(eol) + eol; }
          else { start = end = model.getValueLength(); text = eol + newMid.join(eol); }
        } else if (!newMid.length) {
          if (b > 0) { start = startOf(a); end = startOf(a + oldMid.length); }
          else { start = Math.max(0, startOf(a) - eol.length); end = model.getValueLength(); }
          text = '';
        } else {
          start = startOf(a);
          end = start + oldMid.join(eol).length;
          text = newMid.join(eol);
        }
        const s = model.getPositionAt(start);
        const e = model.getPositionAt(end);
        model.pushStackElement();
        model.pushEditOperations([], [{ range: new window.monaco.Range(s.lineNumber, s.column, e.lineNumber, e.column), text, forceMoveMarkers: true }], () => null);
        model.pushStackElement();
        return at;
      },
    };
  }

  const keyAt = (varName, line) => (varName ? `v:${varName}` : `l:${line}`);

  // Point a widget's line at a new container, keeping everything else exactly as it was typed:
  // "name = app:input ..." -> "name = home:input ...".
  function reparentLine(text, node, parentVar) {
    const re = new RegExp(`^(\s*(?:[A-Za-z_]\w*\s*=\s*)?)${node.parentVar}:`);
    return re.test(text) ? text.replace(re, `$1${parentVar}:`) : lineFor({ ...node, parentVar });
  }

  const Edits = {
    setValue(model, node, index, value) {
      const ed = makeEditor(model);
      node.values = [...node.values];
      node.values[index] = value;
      ed.replace(node.line, lineFor(node));
      ed.commit();
    },

    setValues(model, node, changes) {
      const ed = makeEditor(model);
      node.values = [...node.values];
      for (const [i, v] of Object.entries(changes)) node.values[i] = v;
      ed.replace(node.line, lineFor(node));
      ed.commit();
    },

    setProp(model, parsed, node, key, value) {
      const ed = makeEditor(model);
      const existing = node.props[key];
      const blank = value === '' || value === null || value === undefined || (key === 'speed' && Number(value) === 1 && !existing);
      if (blank) {
        if (existing) { ed.remove(existing.line); ed.commit(); }
        return node.var;
      }
      let varName = node.var;
      if (!varName) {
        varName = uniqueVar(parsed, KINDS[node.kind].name || node.kind, model.getValue());
        ed.replace(node.line, lineFor(node, varName));
      }
      const text = propLine(varName, key, value);
      if (existing) ed.replace(existing.line, text);
      else ed.insertAfter(ownLast(node), text);
      ed.commit();
      return varName;
    },

    // Give a node a variable name (if it has none) so code and children can refer to it.
    ensureVar(ed, parsed, node, code, extra = []) {
      if (node.var) return node.var;
      const name = uniqueVar(parsed, KINDS[node.kind].name || node.kind, code, extra);
      ed.replace(node.line, lineFor(node, name));
      return name;
    },

    insertAt(model, parsed, kind, container, index = Infinity, opts = {}) {
      const info = KINDS[kind];
      const ed = makeEditor(model);
      const code = model.getValue();
      const parentVar = Edits.ensureVar(ed, parsed, container, code);
      const varName = opts.name || (info.name ? uniqueVar(parsed, info.name, code, [parentVar]) : null);
      const node = { kind, parentVar, values: opts.values || info.args.map((a) => a.init ?? undefined), comment: '' };
      const id = ed.insertAfter(insertLine(parsed, container, index, null), lineFor(node, varName));
      const at = ed.commit();
      return keyAt(varName, at[id]);
    },

    moveTo(model, parsed, node, container, index) {
      if (container === node || isInside(container, node)) return keyOf(node);
      const ed = makeEditor(model);
      const lines = linesOf(node);
      const target = insertLine(parsed, container, index, node);
      const parentVar = container === node.parent ? node.parentVar : Edits.ensureVar(ed, parsed, container, model.getValue());
      const texts = lines.map((ln) => (ln === node.line && parentVar !== node.parentVar ? reparentLine(ed.line(ln), node, parentVar) : ed.line(ln)));
      for (const ln of lines) ed.remove(ln);
      const id = ed.insertAfter(target, texts.join(ed.eol));
      const at = ed.commit();
      return keyAt(node.var, at[id] + lines.indexOf(node.line));
    },

    duplicate(model, parsed, node) {
      const ed = makeEditor(model);
      const code = model.getValue();
      const taken = takenNames(parsed, code);
      const map = {};
      walk(node, (n) => {
        if (!n.var) return;
        const base = KINDS[n.kind].name || n.kind;
        let i = 1;
        while (taken.has(`${base}${i}`)) i++;
        map[n.var] = `${base}${i}`;
        taken.add(map[n.var]);
      });
      const lines = linesOf(node);
      const id = ed.insertAfter(Math.max(...lines), lines.map((ln) => renameIdents(ed.line(ln), map)).join(ed.eol));
      const at = ed.commit();
      return keyAt(node.var ? map[node.var] : null, at[id] + lines.indexOf(node.line));
    },

    wrap(model, parsed, node, kind) {
      const ed = makeEditor(model);
      const name = uniqueVar(parsed, KINDS[kind].name, model.getValue());
      ed.insertAfter(Math.min(...linesOf(node)) - 1, `${name} = ${node.parentVar}:${kind}`);
      ed.replace(node.line, reparentLine(ed.line(node.line), node, name));
      ed.commit();
      return `v:${name}`;
    },

    rename(model, parsed, node, name) {
      const ed = makeEditor(model);
      if (!node.var) {
        ed.replace(node.line, lineFor(node, name));
      } else {
        const map = { [node.var]: name };
        model.getLinesContent().forEach((text, i) => {
          const next = renameIdents(text, map);
          if (next !== text) ed.replace(i + 1, next);
        });
      }
      ed.commit();
      return `v:${name}`;
    },

    // First pages for a one-page app: what's already on the window moves onto a "Home" page,
    // and an empty second page is added after it. One undo step.
    makePages(model, parsed, homeName, secondName) {
      const ed = makeEditor(model);
      const win = parsed.win;
      const kids = win.children;
      const home = { kind: 'page', parentVar: win.var, values: ['Home'], comment: '' };
      const second = { kind: 'page', parentVar: win.var, values: ['Page 2'], comment: '' };
      if (kids.length) {
        ed.insertAfter(Math.min(...kids.flatMap(linesOf)) - 1, lineFor(home, homeName));
        for (const k of kids) ed.replace(k.line, reparentLine(ed.line(k.line), k, homeName));
        const id = ed.insertAfter(uiLast(parsed), lineFor(second, secondName));
        const at = ed.commit();
        return keyAt(secondName, at[id]);
      }
      ed.insertAfter(uiLast(parsed), [lineFor(home, homeName), lineFor(second, secondName)].join(ed.eol));
      ed.commit();
      return `v:${homeName}`;
    },

    remove(model, node) {
      const ed = makeEditor(model);
      for (const ln of linesOf(node)) ed.remove(ln);
      ed.commit();
    },

    addFunction(model, name, body) {
      const ed = makeEditor(model);
      const last = model.getLineCount();
      const blank = model.getLineContent(last).trim() === '';
      ed.insertAfter(last, `${blank ? '' : ed.eol}func ${name}():${ed.eol}    ${body || `say "${name} ran"`}`);
      ed.commit();
    },

    addWindow(model, lib) {
      const ed = makeEditor(model);
      const code = model.getValue();
      let at = 0;
      code.split(/\r?\n/).forEach((l, i) => { if (/^(import|mention)\s+\w+/.test(l)) at = i + 1; });
      const hasImport = new RegExp(`^(import|mention)\\s+${lib}\\b`, 'm').test(code);
      ed.insertAfter(at, `${hasImport ? '' : `mention ${lib}${ed.eol}`}${ed.eol}app = ${lib}.window("My App")${ed.eol}app:heading "Hello!"`);
      ed.commit();
    },

    setLib(model, parsed, lib) {
      const ed = makeEditor(model);
      if (parsed.importLine) ed.replace(parsed.importLine, ed.line(parsed.importLine).replace(/\bm?tgui\b/, lib));
      ed.replace(parsed.win.line, ed.line(parsed.win.line).replace(/\bm?tgui\.window/, `${lib}.window`));
      ed.commit();
    },

    replaceAll(model, text) {
      model.pushStackElement();
      model.pushEditOperations([], [{ range: model.getFullModelRange(), text }], () => null);
      model.pushStackElement();
    },
  };

  // ---------------------------------------------------------------- shared property form (Studio inspector + gear customizer)
  function keyOf(node) {
    if (!node) return null;
    if (node.kind === 'window') return 'window';
    return node.var ? `v:${node.var}` : `l:${node.line}`;
  }

  function findByKey(parsed, key) {
    if (!key || !parsed.win) return null;
    if (key === 'window') return parsed.win;
    if (key.startsWith('v:')) return parsed.byVar[key.slice(2)] || null;
    const ln = +key.slice(2);
    return parsed.nodes.find((n) => n.line === ln) || null;
  }

  function field(label, control, hint) {
    const wrap = document.createElement('div');
    wrap.className = 'pf';
    wrap.innerHTML = `<span class="pf-l">${esc(label)}</span>`;
    wrap.appendChild(control);
    if (hint) wrap.insertAdjacentHTML('beforeend', `<span class="pf-h">${esc(hint)}</span>`);
    return wrap;
  }

  function chips(options, value, onChange, render = (o) => esc(o)) {
    const el = document.createElement('div');
    el.className = 'pf-chips';
    for (const o of options) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pf-chip' + (o === value ? ' sel' : '');
      b.innerHTML = render(o);
      b.onclick = () => { $$('.pf-chip', el).forEach((x) => x.classList.toggle('sel', x === b)); onChange(o); };
      el.appendChild(b);
    }
    return el;
  }

  function control(type, value, opts, onChange) {
    let el;
    if (type === 'select') {
      el = document.createElement('select');
      for (const o of opts.options) {
        const op = document.createElement('option');
        op.value = o;
        op.textContent = o || '(default)';
        el.appendChild(op);
      }
      el.value = value ?? '';
      el.onchange = () => onChange(el.value);
    } else if (type === 'segment') {
      el = chips(opts.options, value ?? '', onChange, (o) => esc(opts.names?.[o] ?? (o.charAt(0).toUpperCase() + o.slice(1))));
      el.classList.add('seg');
    } else if (type === 'style') {
      el = chips(opts.options, value || 'primary', onChange, (o) => `<i class="sw-btn s-${o}"></i>${esc(o)}`);
    } else if (type === 'color') {
      el = chips(['', ...COLORS], value ?? '', onChange, (o) => `<i class="sw-dot" style="background:${o === '' ? 'transparent' : o === 'accent' ? 'var(--accent)' : o === 'muted' ? '#8b93a7' : o === 'white' ? '#fff' : FLAT[o]}"></i><span>${o || 'default'}</span>`);
      el.classList.add('swatches');
    } else if (type === 'accent') {
      el = document.createElement('div');
      el.className = 'pf-accent';
      const sw = chips(['', ...ACCENTS], ACCENTS.includes(value) || value === '' ? value : null, onChange, (o) => (o ? `<i class="sw-orb" style="background:linear-gradient(135deg,${GRADIENTS[o][0]},${GRADIENTS[o][1]})"></i>` : '<i class="sw-orb none"></i>'));
      sw.classList.add('orbs');
      $$('.pf-chip', sw).forEach((b, i) => { b.title = i ? ACCENTS[i - 1] : 'default'; });
      const hex = document.createElement('input');
      hex.type = 'text';
      hex.placeholder = '#hex';
      hex.spellcheck = false;
      hex.value = value && !ACCENTS.includes(value) ? value : '';
      hex.oninput = debounce(() => { if (/^#[0-9a-fA-F]{6}$/.test(hex.value)) onChange(hex.value); }, 300);
      el.append(sw, hex);
    } else if (type === 'gradient') {
      el = document.createElement('div');
      el.className = 'pf-gradient';
      const [a, b] = Array.isArray(value) ? value : ['', ''];
      el.innerHTML = `<input type="color" value="${esc(a || '#8b5cf6')}"><input type="color" value="${esc(b || '#ec4899')}"><span class="pf-gprev"></span><button type="button" class="pf-mini">${value ? 'Remove' : 'Use'}</button>`;
      const [c1, c2] = $$('input', el);
      const prev = $('.pf-gprev', el);
      const paint = () => { prev.style.background = `linear-gradient(90deg, ${c1.value}, ${c2.value})`; };
      paint();
      const push = debounce(() => onChange([c1.value, c2.value]), 200);
      c1.oninput = c2.oninput = () => { paint(); push(); };
      $('button', el).onclick = () => onChange(value ? null : [c1.value, c2.value]);
    } else if (type === 'bool') {
      el = document.createElement('label');
      el.className = 'switch';
      el.innerHTML = '<input type="checkbox"><span></span>';
      const box = el.querySelector('input');
      box.checked = !!value;
      box.onchange = () => onChange(box.checked);
    } else if (type === 'speed') {
      el = document.createElement('div');
      el.className = 'pf-speed';
      el.innerHTML = '<input type="range" min="0.25" max="4" step="0.25"><input type="number" min="0.1" max="20" step="0.25">';
      const [range, num] = el.querySelectorAll('input');
      range.value = num.value = value || 1;
      const push = debounce(() => onChange(num.value), 180);
      range.oninput = () => { num.value = range.value; push(); };
      num.oninput = () => { range.value = num.value; push(); };
    } else if (type === 'fn') {
      el = document.createElement('div');
      el.className = 'pf-fn';
      const sel = document.createElement('select');
      const opens = opts.opens || {};
      const pages = (opts.pages || []).filter((pg) => !Object.values(opens).includes(pg.var));
      for (const o of ['', ...opts.funcs, ...pages.map((pg) => `+page:${pg.var}`), '+new']) {
        const op = document.createElement('option');
        op.value = o;
        const pg = o.startsWith('+page:') && opts.pages.find((x) => `+page:${x.var}` === o);
        op.textContent = o === '' ? '(nothing)' : o === '+new' ? '+ New function…' : pg ? `→ Open page "${pg.title}"`
          : opens[o] ? `${o}() → opens page "${(opts.pages || []).find((x) => x.var === opens[o])?.title || opens[o]}"` : `${o}()`;
        sel.appendChild(op);
      }
      sel.value = value || '';
      sel.onchange = () => onChange(sel.value);
      el.appendChild(sel);
      if (value && opts.goToFunc) {
        const go = document.createElement('button');
        go.type = 'button';
        go.className = 'pf-mini';
        go.title = `Show func ${value}() in the code`;
        go.innerHTML = `${UI.code}`;
        go.onclick = () => opts.goToFunc(value);
        el.appendChild(go);
      }
    } else {
      el = document.createElement('input');
      el.type = type === 'number' ? 'number' : type === 'time' ? 'time' : 'text';
      el.spellcheck = false;
      if (type === 'list') el.value = (value || []).join(', ');
      else el.value = value ?? '';
      const push = debounce(() => {
        if (type === 'list') onChange(el.value.split(',').map((s) => s.trim()).filter(Boolean));
        else if (type === 'number') onChange(el.value === '' ? '' : Number(el.value));
        else onChange(el.value);
      }, type === 'time' ? 50 : 250);
      el.oninput = push;
    }
    return el;
  }

  function renderForm(host, ctx) {
    const { node, parsed } = ctx;
    host.innerHTML = '';
    const info = kindInfo(node);
    const groups = Object.fromEntries(SECTIONS.map(([k]) => [k, []]));
    const funcs = parsed.funcs.map((f) => f.name);
    const pages = (parsed.win?.children || []).filter((c) => c.kind === 'page' && c.var && c !== node).map((c) => ({ var: c.var, title: typeof c.values[0] === 'string' ? c.values[0] : c.var }));
    const opens = pageOpeners(ctx.model.getValue());
    // "Open page X": reuse a func that only opens that page, or write one like go_menu().
    const opener = (pageVar) => {
      const have = Object.keys(opens).find((f) => opens[f] === pageVar);
      return { name: have || freeName(parsed, `go_${pageVar}`, ctx.model.getValue()), make: !have, pageVar };
    };
    const goToFunc = ctx.goToFunc ? (name) => { const f = parsed.funcs.find((x) => x.name === name); if (f) ctx.goToFunc(f.line); } : null;
    const label = (typeof node.values[0] === 'string' && node.values[0]) || KINDS[node.kind]?.label || 'it';

    if (node.kind === 'window') {
      const w = typeof node.values[1] === 'number' ? node.values[1] : 420;
      const h = typeof node.values[2] === 'number' ? node.values[2] : 520;
      const cur = SIZES.find(([, sw, sh]) => sw === w && sh === h)?.[0];
      const presets = chips(SIZES.map((s) => s[0]), cur, (name) => {
        const [, sw, sh] = SIZES.find((s) => s[0] === name);
        ctx.apply((m, p, n) => Edits.setValues(m, n, { 1: sw, 2: sh }), true);
      }, (o) => { const s = SIZES.find((x) => x[0] === o); return `${esc(o)}<small>${s[1]}×${s[2]}</small>`; });
      presets.classList.add('sizes');
      groups.size.push(field('Presets', presets));
    }

    info.args.forEach((a, i) => {
      let value = node.values[i];
      let type = a.type;
      if (value && typeof value === 'object' && 'raw' in value) {
        type = 'raw';
        value = value.raw;
      }
      const shown = value === undefined ? (['bool', 'select', 'style', 'segment'].includes(a.type) ? a.def : '') : value;
      const ctl = control(type === 'raw' ? 'text' : type, shown, { options: a.options, funcs, goToFunc, pages, opens }, (v) => {
        if (type === 'raw') return ctx.apply((m, p, n) => Edits.setValue(m, n, i, v === '' ? undefined : { raw: v }));
        if (a.type === 'fn' && v.startsWith('+page:')) {
          const o = opener(v.slice(6));
          ctx.apply((m, p, n) => { Edits.setValue(m, n, i, o.name); if (o.make) Edits.addFunction(m, o.name, `${o.pageVar}:open`); }, true);
          if (o.make) ctx.toast?.(`Added func ${o.name}() that opens the page.`);
          return;
        }
        if (a.type === 'fn' && v === '+new') {
          const fname = freeName(parsed, `${node.var || 'button'}_clicked`, ctx.model.getValue());
          ctx.apply((m, p, n) => { Edits.setValue(m, n, i, fname); Edits.addFunction(m, fname, `say ${JSON.stringify(`${label} was clicked`)}`); }, true);
          ctx.toast?.(`Added func ${fname}() at the bottom of your code.`);
          return;
        }
        ctx.apply((m, p, n) => Edits.setValue(m, n, i, v === '' ? undefined : v));
      });
      groups[a.section || 'content'].push(field(type === 'raw' ? `${a.label} (code)` : a.label, ctl, a.hint));
    });

    for (const key of info.props) {
      const p = PROPS[key];
      if (p.modernOnly && parsed.win?.lib !== 'mtgui') continue;
      const title = key === 'change' ? CHANGE_LABELS[node.kind] || p.label : p.label;
      const ctl = control(p.type, propValue(node, key), { options: p.options, names: p.names, funcs, goToFunc, pages, opens }, (v) => {
        if (p.type === 'fn' && v.startsWith('+page:')) {
          const o = opener(v.slice(6));
          ctx.apply((m, pr, n) => {
            const name = Edits.setProp(m, pr, n, key, o.name);
            if (o.make) Edits.addFunction(m, o.name, `${o.pageVar}:open`);
            if (name && !n.var) ctx.rekey(`v:${name}`);
          }, true);
          return;
        }
        if (p.type === 'fn' && v === '+new') {
          const fname = freeName(parsed, `${node.var || KINDS[node.kind].name}_${key === 'enter' ? 'entered' : key === 'opened' ? 'opened' : 'changed'}`, ctx.model.getValue());
          ctx.apply((m, pr, n) => {
            const name = Edits.setProp(m, pr, n, key, fname);
            Edits.addFunction(m, fname, key === 'opened' ? `say ${JSON.stringify(`${label} opened`)}` : `say ${name}:value`);
            if (name && !n.var) ctx.rekey(`v:${name}`);
          }, true);
          ctx.toast?.(`Added func ${fname}() at the bottom of your code.`);
          return;
        }
        ctx.apply((m, pr, n) => {
          const name = Edits.setProp(m, pr, n, key, v);
          if (name && !n.var) ctx.rekey(`v:${name}`);
        }, p.type === 'gradient');
      });
      groups[p.section || 'look'].push(field(title, ctl, p.hint));
    }

    let any = false;
    for (const [k, title] of SECTIONS) {
      if (!groups[k].length) continue;
      any = true;
      const sec = document.createElement('section');
      sec.className = 'pf-sec';
      sec.innerHTML = `<div class="pf-sec-h">${esc(title)}</div>`;
      sec.append(...groups[k]);
      host.appendChild(sec);
    }
    if (!any) host.insertAdjacentHTML('beforeend', '<div class="pf-empty">Nothing to set here. Drag it to move it, or use the buttons below.</div>');
  }

  // ---------------------------------------------------------------- preview
  function nodeColor(node) {
    const c = propValue(node, 'color');
    if (!c) return '';
    if (c === 'accent') return 'var(--pv-a)';
    if (c === 'muted') return 'var(--pv-muted)';
    return FLAT[c] || (c === 'white' ? '#fff' : '');
  }

  function clockSvg(size) {
    const ticks = [...Array(60)].map((_, i) => {
      const a = (i * 6 - 90) * Math.PI / 180;
      const hour = i % 5 === 0;
      const r1 = hour ? 0.78 : 0.86;
      return `<line x1="${50 + 46 * r1 * Math.cos(a)}" y1="${50 + 46 * r1 * Math.sin(a)}" x2="${50 + 46 * 0.9 * Math.cos(a)}" y2="${50 + 46 * 0.9 * Math.sin(a)}" class="${hour ? 'tk-h' : 'tk'}"/>`;
    }).join('');
    return `<svg class="pv-clocksvg" viewBox="0 0 100 100" style="width:${size}px;height:${size}px"><circle cx="50" cy="50" r="47" class="face"/>${ticks}
      <line class="hh" x1="50" y1="50" x2="50" y2="28"/><line class="mh" x1="50" y1="50" x2="50" y2="18"/><line class="sh" x1="50" y1="50" x2="50" y2="14"/><circle cx="50" cy="50" r="3" class="dot"/></svg>`;
  }

  function previewNode(node, sel) {
    const v = (i) => node.values[i];
    const txt = (i, d = '') => (typeof v(i) === 'string' ? v(i) : v(i) && v(i).raw ? v(i).raw : d);
    const num = (i, d) => (typeof v(i) === 'number' ? v(i) : d);
    const speed = Number(propValue(node, 'speed')) || 1;
    const color = nodeColor(node);
    const el = document.createElement('div');
    el.className = `pv-node k-${node.kind}` + (keyOf(node) === sel ? ' sel' : '');
    el.dataset.key = keyOf(node);
    el.dataset.label = KINDS[node.kind].label + (node.var ? ` · ${node.var}` : '');
    switch (node.kind) {
      case 'heading': el.innerHTML = `<div class="pv-h" style="color:${color}">${esc(txt(0)) || '&nbsp;'}</div><i class="pv-hbar"></i>`; break;
      case 'text': el.innerHTML = `<div class="pv-t" style="color:${color}">${esc(txt(0)) || '&nbsp;'}</div>`; break;
      case 'small': el.innerHTML = `<div class="pv-s" style="color:${color}">${esc(txt(0)) || '&nbsp;'}</div>`; break;
      case 'button': el.innerHTML = `<span class="pv-btn s-${esc(v(2) || 'primary')}" style="--spd:${0.55 / speed}s">${esc(txt(0, 'Button'))}</span>`; break;
      case 'input': el.innerHTML = `<div class="pv-field ph">${esc(txt(0)) || '&nbsp;'}</div>`; break;
      case 'toggle':
      case 'checkbox': el.innerHTML = `<span class="pv-${node.kind}${v(1) === true ? ' on' : ''}" style="--spd:${(node.kind === 'toggle' ? 0.18 : 0.16) / speed}s"><i></i></span><span class="pv-lbl">${esc(txt(0))}</span>`; break;
      case 'dropdown': {
        const opts = Array.isArray(v(0)) ? v(0) : [];
        el.innerHTML = `<div class="pv-field pv-dd"><span>${esc(txt(1) || opts[0] || 'Choose…')}</span><svg viewBox="0 0 16 16"><path d="M4 6l4 4 4-4"/></svg></div>`;
        break;
      }
      case 'slider': {
        const lo = num(0, 0), hi = num(1, 100), val = num(2, lo);
        const pct = hi > lo ? Math.max(0, Math.min(100, ((val - lo) / (hi - lo)) * 100)) : 0;
        el.innerHTML = `<div class="pv-slider"><i style="width:${pct}%"></i><b style="left:${pct}%"></b></div>`;
        break;
      }
      case 'progress': el.innerHTML = `<div class="pv-progress"><i style="width:${Math.max(0, Math.min(100, num(0, 0)))}%;--spd:${1.6 / speed}s"></i></div>`; break;
      case 'spinner': el.innerHTML = `<span class="pv-spin" style="--spd:${1 / speed}s;--sz:${num(1, 28)}px"></span><span class="pv-lbl">${esc(txt(0))}</span>`; break;
      case 'clock': {
        const digital = v(0) === 'digital';
        el.innerHTML = digital ? '<div class="pv-digital">00:00:00</div>' : clockSvg(Math.min(220, num(1, 160)));
        el.dataset.clockSpeed = speed;
        el.dataset.clockStart = propValue(node, 'time');
        break;
      }
      case 'image': el.innerHTML = `<div class="pv-image" style="width:${Math.min(240, num(1, 120))}px"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M4 18l5-5 4 4 3-3 4 4"/></svg><span>${esc(txt(0, 'image'))}</span></div>`; break;
      case 'divider': el.innerHTML = '<div class="pv-divider"></div>'; break;
      case 'space': el.innerHTML = `<div class="pv-space" style="height:${Math.max(4, num(0, 12))}px"></div>`; break;
      case 'row':
      case 'card':
      case 'page': {
        const box = document.createElement('div');
        box.className = node.kind === 'row' ? 'pv-row' : node.kind === 'page' ? 'pv-page' : 'pv-card';
        if (!node.children.length) box.innerHTML = `<div class="pv-empty-slot">Drop things ${node.kind === 'page' ? 'onto this page' : `into this ${node.kind}`}</div>`;
        for (const c of node.children) box.appendChild(previewNode(c, sel));
        el.appendChild(box);
        break;
      }
      default: break;
    }
    return el;
  }

  function previewWindow(p, sel, pageKey) {
    const pages = p.win.children.filter((c) => c.kind === 'page');
    const showPage = pageKey !== undefined ? pageKey : pages[0] ? keyOf(pages[0]) : null;
    const modern = p.win.lib === 'mtgui';
    const theme = propValue(p.win, 'theme') || 'dark';
    const accent = propValue(p.win, 'accent') || 'blue';
    const custom = propValue(p.win, 'gradient');
    let [a1, a2] = modern ? GRADIENTS[accent] || GRADIENTS.blue : [FLAT[accent] || FLAT.blue, FLAT[accent] || FLAT.blue];
    if (/^#[0-9a-f]{6}$/i.test(accent)) a1 = a2 = accent;
    if (modern && custom && custom[0] && custom[1]) [a1, a2] = custom;
    const win = document.createElement('div');
    win.className = `pv-window ${modern ? 'modern' : 'classic'} theme-${theme}` + (sel === 'window' ? ' sel' : '');
    win.style.setProperty('--pv-a', a1);
    win.style.setProperty('--pv-a2', a2);
    const w = typeof p.win.values[1] === 'number' ? p.win.values[1] : 420;
    const h = typeof p.win.values[2] === 'number' ? p.win.values[2] : 520;
    win.style.width = `${Math.max(240, Math.min(1200, w))}px`;
    win.style.minHeight = `${Math.max(160, Math.min(1200, h))}px`;
    const title = typeof p.win.values[0] === 'string' ? p.win.values[0] : 'My App';
    win.innerHTML = `<div class="pv-titlebar" data-key="window"><img src="assets/icon.png" alt=""><span>${esc(title)}</span><i></i><i></i><i></i></div><div class="pv-body" data-key="window"></div>`;
    const body = win.querySelector('.pv-body');
    if (!p.win.children.length) body.innerHTML = '<div class="pv-empty-slot big">Drag widgets here from the left</div>';
    for (const n of p.win.children) if (n.kind !== 'page' || keyOf(n) === showPage) body.appendChild(previewNode(n, sel));
    return win;
  }

  function startClocks(root) {
    const started = performance.now();
    const now = new Date();
    const real = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
    const clocks = [...root.querySelectorAll('.pv-node.k-clock')];
    if (!clocks.length) return () => {};
    let raf;
    const loop = () => {
      for (const el of clocks) {
        const speed = Number(el.dataset.clockSpeed) || 1;
        const start = el.dataset.clockStart ? el.dataset.clockStart.split(':').reduce((h, m) => +h * 3600 + +m * 60) : real;
        const secs = (start + ((performance.now() - started) / 1000) * speed) % 86400;
        const digital = el.querySelector('.pv-digital');
        if (digital) {
          const s = Math.floor(secs);
          digital.textContent = `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
        } else {
          const rot = (q, deg) => el.querySelector(q)?.setAttribute('transform', `rotate(${deg} 50 50)`);
          rot('.hh', ((secs / 3600) % 12) * 30);
          rot('.mh', ((secs % 3600) / 60) * 6);
          rot('.sh', (secs % 60) * 6);
        }
      }
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(raf);
  }

  // ---------------------------------------------------------------- Design Studio
  const S = { file: null, model: null, sub: null, parsed: null, sel: 'window', zoom: 1, tab: 'add', search: '', stopClocks: () => {}, selfEdit: false };
  let ide = null;

  function host() { return $('#studio'); }

  function skeleton() {
    const st = ide.settings();
    S.zoom = Number(st.studioZoom) || 1;
    S.tab = st.studioTab === 'layers' ? 'layers' : 'add';
    host().innerHTML = `
      <div class="sd">
        <div class="sd-bar">
          <span class="sd-title" title="Design Studio">${UI.palette}<b>Design Studio</b></span>
          <select id="sd-file" title="Which file to design"></select>
          <div class="sd-seg" id="sd-libseg" title="Classic is tgui, Modern is mtgui (gradients, gloss and glow)">
            <button data-lib="tgui">Classic</button><button data-lib="mtgui">Modern</button>
          </div>
          <span class="sd-sep"></span>
          <button class="sd-ib" id="sd-undo" title="Undo (Ctrl+Z)">${UI.undo}</button>
          <button class="sd-ib" id="sd-redo" title="Redo (Ctrl+Y)">${UI.redo}</button>
          <span class="sd-sep"></span>
          <div class="sd-zoom">
            <button class="sd-ib" id="sd-zout" title="Zoom out (Ctrl+-)">${UI.minus}</button>
            <button class="sd-zval" id="sd-zval" title="Reset zoom (Ctrl+0)">100%</button>
            <button class="sd-ib" id="sd-zin" title="Zoom in (Ctrl+=)">${UI.plus}</button>
            <button class="sd-ib" id="sd-zfit" title="Fit to screen">${UI.fit}</button>
            <button class="sd-ib" id="sd-full" title="Full size: give the Studio the whole window (F11)">${UI.expand}</button>
          </div>
          <div class="sd-bar-r">
            <button class="btn sm" id="sd-templates" title="Templates">${UI.grid}<span class="lbl">Templates</span></button>
            <button class="btn sm" id="sd-code" title="Show the code">${UI.code}<span class="lbl">Code</span></button>
            <button class="btn sm primary" id="sd-run" title="Run app">${UI.play}<span class="lbl">Run app</span></button>
          </div>
        </div>
        <div class="sd-main">
          <aside class="sd-left">
            <div class="sd-tabs">
              <button data-tab="add" title="Add widgets">${UI.plus}<span class="lbl">Add</span></button><button data-tab="layers" title="Layers">${UI.grid}<span class="lbl">Layers</span></button>
            </div>
            <div class="sd-pane" data-pane="add">
              <label class="sd-search">${UI.search}<input id="sd-search" placeholder="Search widgets" spellcheck="false"></label>
              <div class="sd-palette" id="sd-palette"></div>
              <div class="sd-hint">Drag onto the window, or click to add to <b id="sd-target">the window</b>.</div>
            </div>
            <div class="sd-pane" data-pane="layers"><div class="sd-layers" id="sd-layers"></div></div>
          </aside>
          <section class="sd-canvas" id="sd-canvas" tabindex="0"><div class="sd-stage" id="sd-stage"></div></section>
          <aside class="sd-right" id="sd-inspector"></aside>
        </div>
        <div class="sd-float hidden" id="sd-float"></div>
        <div class="sd-drop hidden" id="sd-drop"></div>
      </div>`;
    $('#sd-code').onclick = () => ide.openFile(S.file);
    $('#sd-run').onclick = () => ide.runFile(S.file);
    $('#sd-file').onchange = (e) => show(e.target.value);
    $('#sd-undo').onclick = () => undoRedo('undo');
    $('#sd-redo').onclick = () => undoRedo('redo');
    $('#sd-zout').onclick = () => setZoom(S.zoom - 0.1);
    $('#sd-zin').onclick = () => setZoom(S.zoom + 0.1);
    $('#sd-zval').onclick = () => setZoom(1);
    $('#sd-zfit').onclick = fitZoom;
    $('#sd-full').onclick = toggleFull;
    syncFull();
    $('#sd-templates').onclick = openTemplates;
    $$('#sd-libseg button').forEach((b) => (b.onclick = () => switchLib(b.dataset.lib)));
    $$('.sd-tabs button').forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
    $('#sd-search').oninput = (e) => { S.search = e.target.value.trim().toLowerCase(); renderPalette(); };
    const canvas = $('#sd-canvas');
    canvas.addEventListener('scroll', positionFloat);
    canvas.addEventListener('wheel', (e) => { if (e.ctrlKey) { e.preventDefault(); setZoom(S.zoom + (e.deltaY < 0 ? 0.1 : -0.1)); } }, { passive: false });
    window.addEventListener('resize', positionFloat);
    setTab(S.tab);
    renderPalette();
  }

  function setTab(tab) {
    S.tab = tab;
    $('.sd-left')?.classList.toggle('layers', tab === 'layers');
    $$('.sd-tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
    $$('.sd-pane').forEach((p) => p.classList.toggle('hidden', p.dataset.pane !== tab));
    ide.saveSettings({ studioTab: tab });
  }

  function renderPalette() {
    const pal = $('#sd-palette');
    pal.innerHTML = '';
    const q = S.search;
    for (const [cat, kinds] of CATS) {
      const shown = kinds.filter((k) => !q || KINDS[k].label.toLowerCase().includes(q) || k.includes(q) || tipFor(k).toLowerCase().includes(q));
      if (!shown.length) continue;
      pal.insertAdjacentHTML('beforeend', `<div class="sd-cat">${esc(cat)}</div>`);
      const grid = document.createElement('div');
      grid.className = 'sd-tiles';
      for (const kind of shown) {
        const b = document.createElement('button');
        b.className = 'sd-tile';
        b.dataset.kind = kind;
        b.title = `${KINDS[kind].label}: ${tipFor(kind)}`;
        b.innerHTML = `<span class="ic">${ICONS[kind]}</span><span class="lbl">${esc(KINDS[kind].label)}</span>`;
        b.addEventListener('pointerdown', (e) => press(e, { kind }));
        grid.appendChild(b);
      }
      pal.appendChild(grid);
    }
    if (!pal.children.length) pal.innerHTML = '<div class="pf-empty">No widgets match.</div>';
  }

  async function fillFiles() {
    const sel = $('#sd-file');
    const files = (await ide.listFiles()).filter((f) => f.name.endsWith('.tuf') && !/^(dist|build)[\\/]/.test(f.rel));
    if (!files.some((f) => f.path === S.file)) files.unshift({ path: S.file, rel: ide.rel(S.file) });
    sel.innerHTML = files.map((f) => `<option value="${esc(f.path)}">${esc(f.rel)}</option>`).join('');
    sel.value = S.file;
  }

  async function show(file) {
    if (!host().firstChild) skeleton();
    if (file && file !== S.file) {
      S.file = file;
      S.sel = 'window';
    }
    S.model = await ide.getModel(S.file);
    if (!S.model) return;
    S.sub?.dispose();
    S.sub = S.model.onDidChangeContent(debounce(() => {
      if (ide.studioVisible()) render(!S.selfEdit);
      S.selfEdit = false;
    }, 120));
    fillFiles();
    render(true);
    requestAnimationFrame(() => {
      $('#sd-canvas')?.focus({ preventScroll: true });
      const win = $('#sd-stage .pv-window');
      const c = $('#sd-canvas').getBoundingClientRect();
      if (win && win.getBoundingClientRect().width > c.width - 48) fitZoom();
    });
  }

  function apply(fn, rerenderForm = false) {
    S.selfEdit = !rerenderForm;
    const node = findByKey(S.parsed, S.sel);
    fn(S.model, S.parsed, node);
  }

  // Run an edit that changes the structure, then select `key` (or what the edit returns).
  function edit(fn) {
    S.selfEdit = false;
    const key = fn();
    if (typeof key === 'string') S.sel = key;
  }

  function render(withForm = true) {
    S.parsed = parse(S.model.getValue());
    const p = S.parsed;
    const stage = $('#sd-stage');
    S.stopClocks();
    $$('#sd-libseg button').forEach((b) => b.classList.toggle('on', !!p.win && b.dataset.lib === p.win.lib));
    $('#sd-libseg').classList.toggle('off', !p.win);
    updateUndo();
    if (!p.win) {
      // A tgame file is a game: Tuff Engine is where it's built visually.
      const game = /^[ \t]*(?:import|mention)[ \t]+tgame\b/m.test(S.model.getValue());
      stage.innerHTML = `<div class="sd-none">${ICONS.window}<b>${game ? 'This is a game' : "This file doesn't have an app window yet"}</b><span>${game ? 'Games are built in Tuff Engine. Or start an app from a template, or add an empty window and drag widgets onto it.' : 'Start from a template, or add an empty window and drag widgets onto it.'}</span>
        <div>${game ? '<button class="btn primary" data-a="engine">Open in Tuff Engine</button>' : ''}<button class="btn${game ? '' : ' primary'}" data-a="tpl">Pick a template</button><button class="btn" data-lib="mtgui">Empty modern window</button><button class="btn" data-lib="tgui">Empty classic window</button></div></div>`;
      $('[data-a="engine"]', stage)?.addEventListener('click', () => ide.openEngine(S.file));
      $('[data-a="tpl"]', stage).onclick = openTemplates;
      $$('[data-lib]', stage).forEach((b) => (b.onclick = () => edit(() => Edits.addWindow(S.model, b.dataset.lib))));
      $('#sd-layers').innerHTML = '';
      $('#sd-inspector').innerHTML = '';
      $('#sd-float').classList.add('hidden');
      return;
    }
    if (!findByKey(p, S.sel)) S.sel = 'window';
    const sel = findByKey(p, S.sel);
    const target = sel.kind === 'window' || KINDS[sel.kind]?.container ? sel : sel.parent;
    $('#sd-target').textContent = target.kind === 'window' ? 'the window' : `${target.var || KINDS[target.kind].label.toLowerCase()}`;

    const page = currentPage(p);
    const win = previewWindow(p, S.sel, page ? keyOf(page) : null);
    const wrap = document.createElement('div');
    wrap.className = 'sd-pagewrap';
    wrap.append(pagesBar(p, page), win);
    stage.innerHTML = '';
    stage.appendChild(wrap);
    stage.style.zoom = S.zoom;
    $('#sd-zval').textContent = `${Math.round(S.zoom * 100)}%`;
    wireStage(stage);
    S.stopClocks = startClocks(stage);

    renderLayers();
    if (withForm) renderInspector();
    positionFloat();
  }

  function wireStage(stage) {
    stage.onclick = (e) => {
      if (D.justDropped) return;
      const el = e.target.closest('[data-key]');
      if (!el) { select('window'); return; }
      e.stopPropagation();
      const node = findByKey(S.parsed, el.dataset.key);
      if (node && (node.kind === 'toggle' || node.kind === 'checkbox') && S.sel === el.dataset.key) {
        el.querySelector('.pv-toggle, .pv-checkbox')?.classList.toggle('on');
      }
      select(el.dataset.key);
    };
    stage.ondblclick = (e) => {
      const el = e.target.closest('.pv-node');
      const node = el && findByKey(S.parsed, el.dataset.key);
      const label = e.target.closest('.pv-h, .pv-t, .pv-s, .pv-btn, .pv-lbl');
      if (node && label && INLINE[node.kind] !== undefined) startInline(label, node, INLINE[node.kind]);
    };
    stage.onmouseover = (e) => {
      const el = e.target.closest('.pv-node');
      $$('.pv-node.hov', stage).forEach((x) => x !== el && x.classList.remove('hov'));
      el?.classList.add('hov');
    };
    stage.onmouseleave = () => $$('.pv-node.hov', stage).forEach((x) => x.classList.remove('hov'));
    $$('.pv-node', stage).forEach((el) => el.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || e.target.closest('[contenteditable="plaintext-only"]') || e.target.closest('.pv-node') !== el) return;
      const key = el.dataset.key;
      press(e, { key });
      if (key !== S.sel) select(key);
    }));
  }

  // Double-click a label in the preview to edit it right there.
  function startInline(el, node, index) {
    const value = node.values[index];
    if (value && typeof value === 'object') { ide.toast('This text comes from code, so change it in the code.'); return; }
    const before = typeof value === 'string' ? value : el.textContent;
    el.contentEditable = 'plaintext-only';
    el.classList.add('editing');
    el.focus();
    getSelection().selectAllChildren(el);
    const finish = (save) => {
      el.onblur = el.onkeydown = null;
      el.contentEditable = 'false';
      el.classList.remove('editing');
      const text = el.textContent.replace(/\n/g, ' ');
      if (save && text !== before) edit(() => { Edits.setValue(S.model, node, index, text); return keyOf(node); });
      else el.textContent = before;
    };
    el.onkeydown = (e) => {
      e.stopPropagation();
      if (e.key === 'Enter') { e.preventDefault(); finish(true); }
      if (e.key === 'Escape') { e.preventDefault(); finish(false); }
    };
    el.onblur = () => finish(true);
  }

  function renderLayers() {
    const box = $('#sd-layers');
    box.innerHTML = '';
    const row = (node, depth) => {
      const b = document.createElement('div');
      b.className = 'sd-layer' + (keyOf(node) === S.sel ? ' sel' : '');
      b.dataset.key = keyOf(node);
      b.style.paddingLeft = `${8 + depth * 14}px`;
      const info = kindInfo(node);
      const what = node.kind !== 'window' && typeof node.values[0] === 'string' && node.values[0] ? node.values[0] : '';
      b.innerHTML = `<span class="ic">${ICONS[node.kind]}</span><span class="lb">${esc(info.label)}</span><span class="what">${esc(what)}</span><span class="nm">${esc(node.var || '')}</span>`;
      b.onclick = () => select(keyOf(node));
      if (node.kind !== 'window') b.onpointerdown = (e) => press(e, { key: keyOf(node) });
      b.onmouseenter = () => $(`#sd-stage .pv-node[data-key="${CSS.escape(keyOf(node))}"]`)?.classList.add('hov');
      b.onmouseleave = () => $$('#sd-stage .pv-node.hov').forEach((x) => x.classList.remove('hov'));
      box.appendChild(b);
      for (const c of node.children) row(c, depth + 1);
    };
    row(S.parsed.win, 0);
    box.insertAdjacentHTML('beforeend', '<div class="sd-hint">Drag layers to reorder them or move them into a card or row.</div>');
  }

  function renderInspector() {
    const node = findByKey(S.parsed, S.sel);
    const info = kindInfo(node);
    const box = $('#sd-inspector');
    box.innerHTML = `
      <div class="in-head">
        <span class="ic big">${ICONS[node.kind]}</span>
        <div class="in-id"><b>${esc(info.label)}</b>
          ${node.kind === 'window' ? `<span class="in-sub">${esc(node.var)} · ${node.lib === 'mtgui' ? 'modern' : 'classic'}</span>`
            : `<input class="in-name" id="in-name" spellcheck="false" value="${esc(node.var || '')}" placeholder="give it a name" title="The name your code uses for this. Renaming updates your code too.">`}
        </div>
      </div>
      <div class="in-tip">${esc(node.kind === 'window' ? 'The app window. Set its title, size and colors here.' : tipFor(node.kind))}</div>
      <div class="in-form" id="sd-props"></div>
      <div class="in-actions" id="sd-actions"></div>`;
    renderForm($('#sd-props'), {
      node, parsed: S.parsed, model: S.model, apply,
      rekey: (key) => { S.sel = key; },
      toast: (m) => ide.toast(m, 'ok', 3500),
      goToFunc: (line) => ide.goToLine(S.file, line),
    });
    const name = $('#in-name');
    if (name) {
      const commit = () => {
        const v = name.value.trim();
        if (v === (node.var || '')) return;
        if (!v) { name.value = node.var || ''; return ide.toast('Code needs a name to talk to this, so it keeps its old one.'); }
        if (!/^[A-Za-z_]\w*$/.test(v)) { name.value = node.var || ''; return ide.toast('Names use letters, numbers and _ and can\'t start with a number.', 'error'); }
        if ((window.TUFF_KEYWORDS || []).includes(v) || takenNames(S.parsed, S.model.getValue()).has(v)) { name.value = node.var || ''; return ide.toast(`'${v}' is already used. Pick another name.`, 'error'); }
        edit(() => Edits.rename(S.model, S.parsed, node, v));
      };
      name.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); name.blur(); } if (e.key === 'Escape') { name.value = node.var || ''; name.blur(); } };
      name.onblur = commit;
    }
    const act = $('#sd-actions');
    if (node.kind === 'window') {
      act.innerHTML = `<button class="btn sm" data-a="code">${UI.code}Show in code</button>`;
    } else {
      act.innerHTML = `<button class="btn sm" data-a="dup" title="Duplicate (Ctrl+D)">${UI.dup}Duplicate</button>
        <button class="btn sm" data-a="card" title="Put it inside a new card">Wrap in card</button>
        <button class="btn sm" data-a="row" title="Put it inside a new row">Wrap in row</button>
        <button class="btn sm" data-a="code">${UI.code}Show in code</button>
        <button class="btn sm danger" data-a="del" title="Delete (Del)">${UI.trash}Delete</button>`;
      $('[data-a="dup"]', act).onclick = () => duplicate(node);
      $('[data-a="card"]', act).onclick = () => edit(() => Edits.wrap(S.model, S.parsed, node, 'card'));
      $('[data-a="row"]', act).onclick = () => edit(() => Edits.wrap(S.model, S.parsed, node, 'row'));
      $('[data-a="del"]', act).onclick = () => removeNode(node);
    }
    $('[data-a="code"]', act).onclick = () => ide.goToLine(S.file, node.line);
  }

  // Selection bar docked at the top of the canvas: never covers a widget or a drop spot.
  function positionFloat() {
    const fl = $('#sd-float');
    if (!fl) return;
    const node = S.parsed && findByKey(S.parsed, S.sel);
    const el = node && node.kind !== 'window' && $(`#sd-stage .pv-node[data-key="${CSS.escape(S.sel)}"]`);
    if (!el || D.active) { fl.classList.add('hidden'); return; }
    const label = `${KINDS[node.kind].label}${node.var ? ` · ${node.var}` : ''}`;
    if (fl.dataset.key !== S.sel || fl.dataset.label !== label) {
      fl.dataset.key = S.sel;
      fl.dataset.label = label;
      fl.innerHTML = `<span class="sd-float-l"><span class="ic">${ICONS[node.kind]}</span>${esc(label)}</span><i class="sd-float-sep"></i><button data-a="up" title="Move up (Alt+↑)">${UI.up}</button><button data-a="down" title="Move down (Alt+↓)">${UI.down}</button>
        <button data-a="dup" title="Duplicate (Ctrl+D)">${UI.dup}</button><button data-a="code" title="Show in code">${UI.code}</button><button data-a="del" class="danger" title="Delete (Del)">${UI.trash}</button>`;
      fl.onclick = (e) => {
        const a = e.target.closest('button')?.dataset.a;
        const n = findByKey(S.parsed, S.sel);
        if (!a || !n) return;
        if (a === 'up' || a === 'down') moveBy(n, a === 'up' ? -1 : 1);
        if (a === 'dup') duplicate(n);
        if (a === 'del') removeNode(n);
        if (a === 'code') ide.goToLine(S.file, n.line);
      };
    }
    const c = $('#sd-canvas').getBoundingClientRect();
    const sdr = $('#studio').getBoundingClientRect();
    fl.classList.remove('hidden');
    fl.style.top = `${c.top - sdr.top + 10}px`;
    fl.style.left = `${c.left - sdr.left + Math.max(8, (c.width - fl.offsetWidth) / 2)}px`;
  }

  function select(key) {
    if (key === S.sel && findByKey(S.parsed, key)) return;
    S.sel = key;
    render(true);
  }

  // ---------------------------------------------------------------- pages
  const pagesOf = (p) => (p?.win ? p.win.children.filter((c) => c.kind === 'page') : []);
  const pageOf = (node) => { for (let n = node; n; n = n.parent) if (n.kind === 'page') return n; return null; };
  const slug = (t) => String(t).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').replace(/^(\d)/, 'p$1') || 'page';

  // The page showing in the canvas: the one holding the selection, else the last one picked, else the first.
  function currentPage(p) {
    const pages = pagesOf(p);
    if (!pages.length) return null;
    const fromSel = pageOf(findByKey(p, S.sel));
    if (fromSel) { S.page = keyOf(fromSel); return fromSel; }
    return pages.find((x) => keyOf(x) === S.page) || pages[0];
  }

  // Funcs whose whole body is "somepage:open", so events can say which page they open.
  function pageOpeners(code) {
    const out = {};
    for (const m of code.matchAll(/^func\s+([A-Za-z_]\w*)\s*\(\s*\)\s*:\s*\r?\n[ \t]+([A-Za-z_]\w*):open[ \t]*(?:#.*)?(?:\r?\n(?![ \t]+\S)|$)/gm)) out[m[1]] = m[2];
    return out;
  }

  function pagesBar(p, page) {
    const bar = document.createElement('div');
    bar.className = 'sd-pages';
    const pages = pagesOf(p);
    bar.innerHTML = pages.map((pg) => `<button class="sd-pg${pg === page ? ' on' : ''}" data-page="${esc(keyOf(pg))}" title="${esc(pg.var ? `${pg.var}  (open it with ${pg.var}:open)` : '')}">${ICONS.page}<span>${esc(typeof pg.values[0] === 'string' && pg.values[0] ? pg.values[0] : pg.var || 'Page')}</span></button>`).join('')
      + `<button class="sd-pg add" data-page="+" title="${pages.length ? 'Add another page' : 'Split this app into pages. What is here now becomes the Home page.'}">${UI.plus}<span>${pages.length ? 'Page' : 'Add pages'}</span></button>`;
    bar.onclick = (e) => {
      e.stopPropagation(); // the canvas treats clicks on empty space as "select the window"
      const b = e.target.closest('[data-page]');
      if (!b) return;
      if (b.dataset.page === '+') { addPage(); return; }
      S.page = b.dataset.page;
      S.sel = b.dataset.page;
      render(true);
    };
    return bar;
  }

  function addPage() {
    const p = S.parsed;
    if (!p?.win) return;
    const pages = pagesOf(p);
    const code = S.model.getValue();
    if (!pages.length) {
      const home = freeName(p, 'home', code);
      const second = freeName({ ...p, byVar: { ...p.byVar, [home]: 1 } }, 'page_2', code);
      edit(() => { const key = Edits.makePages(S.model, p, home, second); S.page = key; return key; });
      ide.toast('Made pages: everything that was here is on Home now. Buttons can open a page from their When clicked event.', 'ok', 5000);
      return;
    }
    let n = pages.length + 1;
    while (pages.some((pg) => pg.values[0] === `Page ${n}`)) n++;
    const title = `Page ${n}`;
    const name = freeName(p, slug(title), code);
    edit(() => { const key = Edits.insertAt(S.model, p, 'page', p.win, Infinity, { values: [title], name }); S.page = key; return key; });
  }

  function selectedContainer() {
    const sel = findByKey(S.parsed, S.sel) || S.parsed?.win;
    return sel.kind === 'window' || KINDS[sel.kind]?.container ? sel : sel.parent;
  }

  function add(kind) {
    if (!S.parsed?.win) return ide.toast('Add a window first.');
    if (kind === 'page') { addPage(); return; }
    const target = selectedContainer();
    const sel = findByKey(S.parsed, S.sel);
    // Clicking a tile adds it right after the selected widget, or at the end of the selected card/row/window.
    const index = sel && sel !== target ? target.children.indexOf(sel) + 1 : Infinity;
    edit(() => Edits.insertAt(S.model, S.parsed, kind, target, index));
  }

  function moveBy(node, dir) {
    const sibs = node.parent.children;
    const i = sibs.indexOf(node);
    const j = i + dir;
    if (j < 0 || j > sibs.length - 1) return;
    edit(() => Edits.moveTo(S.model, S.parsed, node, node.parent, j));
  }

  function duplicate(node) {
    edit(() => Edits.duplicate(S.model, S.parsed, node));
  }

  function removeNode(node) {
    const used = node.var && S.model.getValue().split(/\r?\n/).some((l, i) => !linesOf(node).includes(i + 1) && new RegExp(`\\b${node.var}\\b`).test(stripComment(l).code));
    edit(() => { Edits.remove(S.model, node); return keyOf(node.parent); });
    if (used) ide.toast(`Removed. Some code still mentions ${node.var}. Check the red marks when you run.`, 'error', 5000);
    else ide.toast(`Removed the ${KINDS[node.kind].label.toLowerCase()}. Ctrl+Z brings it back.`, 'info', 3000);
  }

  function switchLib(lib) {
    if (!S.parsed?.win || S.parsed.win.lib === lib) return;
    edit(() => { Edits.setLib(S.model, S.parsed, lib); return S.sel; });
  }

  function undoRedo(which) {
    if (!S.model) return;
    S.selfEdit = false;
    S.model[which]();
  }

  function updateUndo() {
    if (!S.model) return;
    $('#sd-undo').disabled = !S.model.canUndo();
    $('#sd-redo').disabled = !S.model.canRedo();
  }

  function setZoom(z) {
    S.zoom = Math.round(Math.max(0.3, Math.min(2.5, z)) * 10) / 10;
    $('#sd-stage').style.zoom = S.zoom;
    $('#sd-zval').textContent = `${Math.round(S.zoom * 100)}%`;
    ide.saveSettings({ studioZoom: S.zoom });
    positionFloat();
  }

  function toggleFull() {
    ide.setStudioFull(!ide.studioFull());
    syncFull();
    requestAnimationFrame(() => { positionFloat(); if (ide.studioFull()) fitZoom(); });
  }

  function syncFull() {
    const b = $('#sd-full');
    if (!b) return;
    const on = ide.studioFull();
    b.innerHTML = on ? UI.shrink : UI.expand;
    b.classList.toggle('on', on);
    b.title = on ? 'Exit full size (F11)' : 'Full size: give the Studio the whole window (F11)';
  }

  function fitZoom() {
    const win = $('#sd-stage .pv-window');
    if (!win) return;
    const c = $('#sd-canvas').getBoundingClientRect();
    const w = win.offsetWidth, h = win.offsetHeight;
    setZoom(Math.min(1.6, (c.width - 64) / w, (c.height - 72) / h));
  }

  // ---------------------------------------------------------------- drag and drop
  const D = { src: null, x0: 0, y0: 0, active: false, ghost: null, target: null, justDropped: false };

  const dragNode = () => (D.src?.key ? findByKey(S.parsed, D.src.key) : null);

  function press(e, src) {
    if (e.button !== 0) return;
    D.src = src;
    D.x0 = e.clientX;
    D.y0 = e.clientY;
    D.active = false;
    D.target = null;
    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', onDragEnd, { once: true });
  }

  function onDragMove(e) {
    if (!D.active) {
      if (Math.hypot(e.clientX - D.x0, e.clientY - D.y0) < 5) return;
      beginDrag();
    }
    D.ghost.style.transform = `translate(${e.clientX + 14}px, ${e.clientY + 12}px)`;
    D.target = dropTargetAt(e.clientX, e.clientY);
    showIndicator(D.target);
  }

  function beginDrag() {
    D.active = true;
    const node = dragNode();
    const kind = D.src.kind || node?.kind;
    if (!kind) return;
    D.ghost = document.createElement('div');
    D.ghost.className = 'sd-ghost';
    D.ghost.innerHTML = `<span class="ic">${ICONS[kind]}</span>${esc(KINDS[kind].label)}${node?.var ? `<span class="nm">${esc(node.var)}</span>` : ''}`;
    document.body.appendChild(D.ghost);
    document.body.classList.add('sd-dragging');
    if (node) $(`#sd-stage .pv-node[data-key="${CSS.escape(D.src.key)}"]`)?.classList.add('dragging');
    $('#sd-float').classList.add('hidden');
  }

  function onDragEnd() {
    window.removeEventListener('pointermove', onDragMove);
    const { active, target, src } = D;
    if (!src) return;
    D.src = null;
    D.ghost?.remove();
    D.ghost = null;
    D.active = false;
    document.body.classList.remove('sd-dragging');
    $$('.dragging, .drop-into').forEach((x) => x.classList.remove('dragging', 'drop-into'));
    $('#sd-drop').classList.add('hidden');
    if (!active) {
      if (src.kind) add(src.kind);
      return;
    }
    D.justDropped = true;
    setTimeout(() => { D.justDropped = false; }, 0);
    if (!target) { positionFloat(); return; }
    if (src.kind === 'page') addPage();
    else if (src.kind) edit(() => Edits.insertAt(S.model, S.parsed, src.kind, target.container, target.index));
    else {
      const node = findByKey(S.parsed, src.key);
      if (node) edit(() => Edits.moveTo(S.model, S.parsed, node, target.container, target.index));
    }
  }

  function allowed(container) {
    const n = dragNode();
    if ((n?.kind === 'page' || D.src?.kind === 'page') && container.kind !== 'window') return false;
    return !(n && (container === n || isInside(container, n)));
  }

  function dropTargetAt(x, y) {
    const el = document.elementFromPoint(x, y);
    if (!el || !S.parsed?.win) return null;
    const layer = el.closest('.sd-layer');
    if (layer) return layerTarget(layer, y);
    if (!el.closest('#sd-canvas')) return null;
    let box = el.closest('#sd-stage .pv-body, #sd-stage .pv-card, #sd-stage .pv-row');
    if (!box) {
      const body = $('#sd-stage .pv-body');
      return body ? boxTarget(body, S.parsed.win, x, y) : null;
    }
    // Near the edge of a card or row, drop next to it instead of into it.
    if (!box.classList.contains('pv-body')) {
      const own = box.closest('.pv-node');
      const r = own.getBoundingClientRect();
      if (y < r.top + 7 || y > r.bottom - 7) box = own.parentElement;
    }
    const ckey = box.classList.contains('pv-body') ? 'window' : box.closest('.pv-node')?.dataset.key;
    const container = findByKey(S.parsed, ckey);
    if (!container || !allowed(container)) return null;
    return boxTarget(box, container, x, y);
  }

  function boxTarget(box, container, x, y) {
    const horizontal = box.classList.contains('pv-row');
    const kids = [...box.children].filter((c) => c.classList.contains('pv-node') && !c.classList.contains('dragging'));
    let index = kids.length;
    for (let i = 0; i < kids.length; i++) {
      const r = kids[i].getBoundingClientRect();
      if (horizontal ? y < r.top || (y <= r.bottom && x < r.left + r.width / 2) : y < r.top + r.height / 2) { index = i; break; }
    }
    return { container, index, box, kids, horizontal };
  }

  function layerTarget(row, y) {
    const node = findByKey(S.parsed, row.dataset.key);
    const dragged = dragNode();
    if (!node || node === dragged) return null;
    const r = row.getBoundingClientRect();
    const zone = (y - r.top) / r.height;
    const isBox = node.kind === 'window' || KINDS[node.kind]?.container;
    let container, index;
    if (node.kind === 'window' || (isBox && zone > 0.28 && zone < 0.72)) {
      container = node;
      index = Infinity;
    } else {
      container = node.parent;
      const sibs = container.children.filter((c) => c !== dragged);
      index = sibs.indexOf(node) + (zone >= 0.5 ? 1 : 0);
    }
    if (!allowed(container)) return null;
    return { container, index, layerRow: row, into: container === node };
  }

  function showIndicator(t) {
    const ind = $('#sd-drop');
    $$('.drop-into').forEach((x) => x.classList.remove('drop-into'));
    if (!t) { ind.classList.add('hidden'); return; }
    const sd = $('#studio').getBoundingClientRect();
    const place = (left, top, width, height) => {
      ind.style.left = `${left - sd.left}px`;
      ind.style.top = `${top - sd.top}px`;
      ind.style.width = `${width}px`;
      ind.style.height = `${height}px`;
      ind.classList.remove('hidden');
    };
    if (t.layerRow) {
      const r = t.layerRow.getBoundingClientRect();
      if (t.into) { t.layerRow.classList.add('drop-into'); ind.classList.add('hidden'); return; }
      const before = t.index <= t.container.children.filter((c) => c !== dragNode()).indexOf(findByKey(S.parsed, t.layerRow.dataset.key));
      place(r.left + 8, (before ? r.top : r.bottom) - 1, r.width - 16, 2);
      return;
    }
    t.box.classList.add('drop-into');
    if (!t.kids.length) { ind.classList.add('hidden'); return; }
    if (t.horizontal) {
      const k = t.kids[Math.min(t.index, t.kids.length - 1)].getBoundingClientRect();
      place(t.index < t.kids.length ? k.left - 6 : k.right + 4, k.top, 2, k.height);
    } else {
      const br = t.box.getBoundingClientRect();
      const k = t.kids[Math.min(t.index, t.kids.length - 1)].getBoundingClientRect();
      place(br.left + 10, (t.index < t.kids.length ? k.top - 6 : k.bottom + 4), br.width - 20, 2);
    }
  }

  // ---------------------------------------------------------------- templates
  function openTemplates() {
    const box = document.createElement('div');
    box.className = 'sd-modal';
    box.innerHTML = `<div class="sd-mbox" role="dialog" aria-label="Templates">
      <div class="sd-mhead"><div><b>Start from a template</b><span>Every template is real Tuff code you can read and change.</span></div><button class="sd-ib" data-a="x" title="Close (Esc)">${UI.close}</button></div>
      <div class="sd-tgrid"></div></div>`;
    const grid = $('.sd-tgrid', box);
    for (const t of TEMPLATES) {
      const card = document.createElement('div');
      card.className = 'sd-tcard';
      const thumb = document.createElement('div');
      thumb.className = 'sd-thumb';
      const win = previewWindow(parse(t.code), null);
      win.style.zoom = 0.42;
      thumb.appendChild(win);
      card.appendChild(thumb);
      card.insertAdjacentHTML('beforeend', `<div class="sd-tinfo"><b>${esc(t.name)}</b><span>${esc(t.desc)}</span>
        <div class="sd-tbtns"><button class="btn sm primary" data-a="new">New file</button><button class="btn sm" data-a="here">Use in this file</button></div></div>`);
      $('[data-a="new"]', card).onclick = () => { close(); templateAsFile(t); };
      $('[data-a="here"]', card).onclick = async () => { close(); templateHere(t); };
      grid.appendChild(card);
    }
    const close = () => { box.remove(); document.removeEventListener('keydown', onKey, true); };
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
    document.addEventListener('keydown', onKey, true);
    box.onmousedown = (e) => { if (e.target === box) close(); };
    $('[data-a="x"]', box).onclick = close;
    host().appendChild(box);
  }

  async function templateHere(t) {
    const code = S.model.getValue().trim();
    if (code) {
      const ok = await ide.ask({ title: `Replace the code in ${ide.basename(S.file)} with the ${t.name} template? (Ctrl+Z undoes it.)`, confirm: true, okLabel: 'Replace' });
      if (!ok) return;
    }
    S.sel = 'window';
    edit(() => { Edits.replaceAll(S.model, t.code); return 'window'; });
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
    ide.openStudio(path);
  }

  // ---------------------------------------------------------------- keyboard (called by the IDE while the Studio is showing)
  function stepSelection(dir) {
    const order = [];
    walk(S.parsed.win, (n) => order.push(n));
    const i = order.findIndex((n) => keyOf(n) === S.sel);
    const next = order[Math.max(0, Math.min(order.length - 1, i + dir))];
    if (next) select(keyOf(next));
  }

  function onKey(e) {
    if (!S.parsed?.win || $('.sd-modal', host())) return false;
    if (e.target.closest?.('input, textarea, select, [contenteditable="plaintext-only"], [contenteditable="true"]')) return false;
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const ctrl = e.ctrlKey || e.metaKey;
    const node = findByKey(S.parsed, S.sel);
    const widget = node && node.kind !== 'window' ? node : null;
    if (ctrl && !e.shiftKey && k === 'z') { undoRedo('undo'); return true; }
    if (ctrl && (k === 'y' || (e.shiftKey && k === 'z'))) { undoRedo('redo'); return true; }
    if (ctrl && k === 'd') { if (widget) duplicate(widget); return true; }
    if (ctrl && (k === '=' || k === '+')) { setZoom(S.zoom + 0.1); return true; }
    if (ctrl && k === '-') { setZoom(S.zoom - 0.1); return true; }
    if (ctrl && k === '0') { setZoom(1); return true; }
    if (k === 'F11') { toggleFull(); return true; }
    if (ctrl || e.altKey && !['ArrowUp', 'ArrowDown'].includes(k)) return false;
    if (k === 'Delete' || k === 'Backspace') { if (widget) removeNode(widget); return true; }
    if (e.altKey && (k === 'ArrowUp' || k === 'ArrowDown')) { if (widget) moveBy(widget, k === 'ArrowUp' ? -1 : 1); return true; }
    if (k === 'ArrowUp' || k === 'ArrowDown') { stepSelection(k === 'ArrowUp' ? -1 : 1); return true; }
    if (k === 'Escape' && node?.parent) { select(keyOf(node.parent)); return true; }
    if (k === 'Enter' && widget && INLINE[widget.kind] !== undefined) {
      const label = $(`#sd-stage .pv-node[data-key="${CSS.escape(S.sel)}"] :is(.pv-h, .pv-t, .pv-s, .pv-btn, .pv-lbl)`);
      if (label) { startInline(label, widget, INLINE[widget.kind]); return true; }
    }
    return false;
  }

  // ---------------------------------------------------------------- gear customizer in the code editor
  const C = { node: null, model: null, line: 0, sub: null, decos: [] };
  let gearCache = { model: null, version: -1, parsed: null };

  function parsedFor(model) {
    if (gearCache.model !== model || gearCache.version !== model.getVersionId()) {
      gearCache = { model, version: model.getVersionId(), parsed: parse(model.getValue()) };
    }
    return gearCache.parsed;
  }

  function nodeAtLine(parsed, line) {
    if (parsed.win?.line === line) return parsed.win;
    const direct = parsed.nodes.find((n) => n.line === line);
    if (direct) return direct;
    return [parsed.win, ...parsed.nodes].find((n) => n && Object.values(n.props).some((p) => p.line === line)) || null;
  }

  function closeCustomizer() {
    $('#customizer')?.classList.add('hidden');
    C.sub?.dispose();
    C.sub = null;
    C.node = null;
  }

  function openCustomizer(model, line) {
    const parsed = parsedFor(model);
    const node = nodeAtLine(parsed, line);
    if (!node) return;
    C.model = model;
    C.key = keyOf(node);
    C.line = node.line;
    C.sub?.dispose();
    C.sub = model.onDidChangeContent(debounce(() => {
      if (C.selfEdit) { C.selfEdit = false; return; }
      drawCustomizer(false);
    }, 150));
    drawCustomizer(true);
  }

  function drawCustomizer(position) {
    const box = $('#customizer');
    const parsed = parse(C.model.getValue());
    const node = findByKey(parsed, C.key) || nodeAtLine(parsed, C.line);
    if (!node) return closeCustomizer();
    C.key = keyOf(node);
    const info = kindInfo(node);
    box.innerHTML = `<div class="cz-head"><span class="ic">${ICONS[node.kind]}</span><b>${esc(info.label)}</b><span class="nm">${esc(node.var || '')}</span>
      <button class="cz-x" title="Close (Esc)"><svg viewBox="0 0 12 12"><path d="M2 2l8 8M10 2l-8 8"/></svg></button></div>
      <div class="cz-body"></div>
      <div class="cz-foot"><span>Changes are written into your code.</span><button class="btn sm" data-a="studio">Open in Design Studio</button></div>`;
    renderForm($('.cz-body', box), {
      node, parsed, model: C.model,
      apply: (fn, rerender) => { C.selfEdit = !rerender; fn(C.model, parsed, node); },
      rekey: (key) => { C.key = key; },
      toast: (m) => ide.toast(m, 'ok', 3500),
    });
    $('.cz-x', box).onclick = closeCustomizer;
    $('[data-a="studio"]', box).onclick = () => {
      const file = ide.activeFile();
      closeCustomizer();
      S.sel = C.key;
      ide.openStudio(file);
    };
    box.classList.remove('hidden');
    if (position) {
      const editor = ide.editor();
      const pos = editor.getScrolledVisiblePosition({ lineNumber: node.line, column: 1 });
      const hostRect = $('#editor-host').getBoundingClientRect();
      const left = Math.min(Math.max(8, (pos?.left || 0) + 28), hostRect.width - box.offsetWidth - 12);
      let top = (pos?.top || 0) + (pos?.height || 20) + 4;
      if (top + box.offsetHeight > hostRect.height - 8) top = Math.max(8, (pos?.top || 0) - box.offsetHeight - 6);
      box.style.left = `${left}px`;
      box.style.top = `${top}px`;
    }
  }

  async function setupGear() {
    const monaco = await ide.monacoReady();
    const editor = ide.editor();
    let hoverLine = 0;
    editor.onMouseMove((e) => {
      const model = editor.getModel();
      const line = e.target.position?.lineNumber || 0;
      if (line === hoverLine) return;
      hoverLine = line;
      let decos = [];
      if (model && model.getLanguageId() === 'tuff' && line) {
        const node = nodeAtLine(parsedFor(model), line);
        if (node && node.line === line) {
          decos = [{ range: new monaco.Range(line, 1, line, 1), options: { glyphMarginClassName: 'tuff-gear', glyphMarginHoverMessage: { value: `Customize this ${kindInfo(node).label.toLowerCase()}` } } }];
        }
      }
      C.decos = editor.deltaDecorations(C.decos, decos);
    });
    editor.onMouseLeave(() => { hoverLine = 0; C.decos = editor.deltaDecorations(C.decos, []); });
    editor.onMouseDown((e) => {
      if (e.target.type === monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN && e.target.position) {
        const model = editor.getModel();
        if (model && nodeAtLine(parsedFor(model), e.target.position.lineNumber)) openCustomizer(model, e.target.position.lineNumber);
      }
    });
    editor.onDidChangeModel(closeCustomizer);
    document.addEventListener('mousedown', (e) => {
      const open = !$('#customizer').classList.contains('hidden');
      if (open && !e.target.closest('#customizer') && !e.target.closest('.margin')) closeCustomizer();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('#customizer').classList.contains('hidden')) closeCustomizer();
    });
  }

  window.TuffStudio = {
    init(ideApi) {
      ide = ideApi;
      setupGear();
    },
    show,
    onKey,
    closeCustomizer,
    parse,
    templates: () => TEMPLATES.map((t) => ({ ...t })),
    // Shared with Tuff Engine (tuff-engine.js), which reads and writes tgame code the same way.
    kit: { $, $$, esc, debounce, UI, stripComment, splitTop, closesAtEnd, parseValue, parseArgs, makeEditor, takenNames, freeName, uniqueVar, renameIdents, field, chips, control },
  };
})();
