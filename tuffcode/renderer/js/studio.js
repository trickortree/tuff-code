(() => {
  const api = window.tuff;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  // ---------------------------------------------------------------- schema
  const STYLES = ['primary', 'secondary', 'outline', 'ghost', 'success', 'danger'];
  const COLORS = ['accent', 'muted', 'red', 'orange', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink', 'white'];
  const ACCENTS = ['blue', 'purple', 'pink', 'red', 'orange', 'yellow', 'green', 'teal'];
  const GRADIENTS = { blue: ['#3b82f6', '#06b6d4'], purple: ['#8b5cf6', '#ec4899'], pink: ['#ec4899', '#f97316'], red: ['#ef4444', '#f97316'],
    orange: ['#f97316', '#f43f5e'], yellow: ['#eab308', '#f97316'], green: ['#22c55e', '#14b8a6'], teal: ['#14b8a6', '#3b82f6'] };
  const FLAT = { blue: '#3574f0', purple: '#8b5cf6', pink: '#ec4899', red: '#e5484d', orange: '#f97316', yellow: '#e2a508', green: '#22a35a', teal: '#14b8a6' };

  const A = (key, label, type, def, extra = {}) => ({ key, label, type, def, ...extra });
  const KINDS = {
    heading: { label: 'Heading', name: 'title', args: [A('text', 'Text', 'text', '', { init: 'Heading' })], props: ['color'] },
    text: { label: 'Text', name: 'label', args: [A('text', 'Text', 'text', '', { init: 'Some text' })], props: ['color'] },
    small: { label: 'Small text', name: 'note', args: [A('text', 'Text', 'text', '', { init: 'A small note' })], props: ['color'] },
    button: { label: 'Button', name: 'button', args: [A('text', 'Text', 'text', 'Button', { init: 'Click me' }), A('fn', 'When clicked, run', 'fn', ''), A('style', 'Style', 'select', 'primary', { options: STYLES })], props: ['speed'] },
    input: { label: 'Text box', name: 'box', args: [A('placeholder', 'Hint text', 'text', '', { init: 'Type here' })], props: [] },
    toggle: { label: 'Switch', name: 'switch', args: [A('label', 'Label', 'text', '', { init: 'Switch' }), A('on', 'Starts on', 'bool', false)], props: ['speed'] },
    checkbox: { label: 'Checkbox', name: 'check', args: [A('label', 'Label', 'text', '', { init: 'Checkbox' }), A('on', 'Starts ticked', 'bool', false)], props: ['speed'] },
    dropdown: { label: 'Dropdown', name: 'choice', args: [A('options', 'Choices (comma separated)', 'list', [], { init: ['One', 'Two', 'Three'] }), A('value', 'Selected', 'text', '')], props: [] },
    slider: { label: 'Slider', name: 'slider', args: [A('min', 'Lowest', 'number', 0), A('max', 'Highest', 'number', 100), A('value', 'Starts at', 'number', '', { init: 50 })], props: [] },
    progress: { label: 'Progress bar', name: 'bar', args: [A('value', 'Percent', 'number', 0, { init: 50 })], props: ['speed'] },
    spinner: { label: 'Spinner', name: 'spinner', args: [A('label', 'Label', 'text', '', { init: 'Loading...' }), A('size', 'Size', 'number', 28)], props: ['speed'] },
    clock: { label: 'Clock', name: 'clock', args: [A('style', 'Style', 'select', 'analog', { options: ['analog', 'digital'] }), A('size', 'Size', 'number', 160)], props: ['time', 'speed'] },
    image: { label: 'Image', name: 'picture', args: [A('path', 'Image file', 'text', '', { init: 'logo.png' }), A('width', 'Max width', 'number', '')], props: [] },
    divider: { label: 'Divider', name: null, args: [], props: [] },
    space: { label: 'Space', name: null, args: [A('size', 'Size', 'number', 12, { init: 20 })], props: [] },
    row: { label: 'Row', name: 'row', container: true, args: [], props: [] },
    card: { label: 'Card', name: 'card', container: true, args: [], props: [] },
  };
  const WINDOW = { label: 'Window', args: [A('title', 'Title', 'text', 'My App'), A('width', 'Width', 'number', 420), A('height', 'Height', 'number', 520)], props: ['theme', 'accent'] };
  const PROPS = {
    speed: { label: 'Animation speed', type: 'speed', method: 'speed', hint: '1 is normal, 2 is twice as fast, 0.5 is half speed' },
    color: { label: 'Text color', type: 'select', options: ['', ...COLORS], method: 'color' },
    time: { label: 'Start time', type: 'time', method: 'set', hint: 'Leave empty to show the real time' },
    theme: { label: 'Theme', type: 'select', options: ['', 'dark', 'light'], method: 'theme' },
    accent: { label: 'Accent color', type: 'select', options: ['', ...ACCENTS], method: 'accent' },
  };
  const ICONS = {
    heading: 'H', text: 'T', small: 't', button: '▭', input: '⌨', toggle: '◐', checkbox: '☑', dropdown: '▾', slider: '⊶',
    progress: '▬', spinner: '◌', clock: '◷', image: '▣', divider: '—', space: '↕', row: '⇿', card: '▢', window: '❐',
  };
  const kindInfo = (n) => (n.kind === 'window' ? WINDOW : KINDS[n.kind]);

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

  const TYPE_OK = { text: ['string'], number: ['number'], bool: ['bool'], fn: ['name'], select: ['string'], list: ['list'] };
  function valuesFor(info, args) {
    return info.args.map((a, i) => {
      const arg = args[i];
      if (!arg || arg.kind === 'empty') return undefined;
      if ((TYPE_OK[a.type] || []).includes(arg.kind)) return arg.value;
      return { raw: arg.kind === 'string' ? JSON.stringify(arg.value) : String(arg.value) };
    });
  }

  const UI_RE = new RegExp(`^(?:([A-Za-z_]\\w*)\\s*=\\s*)?([A-Za-z_]\\w*):(${Object.keys(KINDS).join('|')})\\b\\s*(.*)$`);

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
        if (parent && (parent.kind === 'window' || KINDS[parent.kind]?.container)) {
          const node = { kind: m[3], var: m[1] || null, parentVar: m[2], parent, line: ln, comment, values: valuesFor(KINDS[m[3]], parseArgs(m[4])), props: {}, children: [] };
          res.nodes.push(node);
          parent.children.push(node);
          if (node.var) res.byVar[node.var] = node;
          return;
        }
      }
      if ((m = line.match(/^([A-Za-z_]\w*):(speed|color|set|theme|accent)\b\s*(.*)$/))) {
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
    if (!p) return '';
    if (key === 'time') {
      const [h, mi] = p.args.map((a) => (a.kind === 'number' ? a.value : 0));
      return `${String(h ?? 0).padStart(2, '0')}:${String(mi ?? 0).padStart(2, '0')}`;
    }
    const a = p.args[0];
    return a && a.kind !== 'empty' ? a.value : '';
  }

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
    if (node.kind === 'window') return `${node.var} = ${node.lib}.window${argText(WINDOW, node.values)}${comment}`;
    return `${varName ? varName + ' = ' : ''}${node.parentVar}:${node.kind}${argText(KINDS[node.kind], node.values)}${comment}`;
  }

  function propLine(varName, key, value) {
    const p = PROPS[key];
    if (key === 'time') {
      const [h, m] = String(value).split(':').map((x) => parseInt(x, 10) || 0);
      return `${varName}:set(${h}, ${m})`;
    }
    if (key === 'speed') return `${varName}:speed ${Number(value) || 1}`;
    return `${varName}:${p.method} ${JSON.stringify(String(value))}`;
  }

  function freeName(parsed, base, code) {
    const taken = new Set([...Object.keys(parsed.byVar), ...parsed.funcs.map((f) => f.name)]);
    for (const m of code.matchAll(/\b([A-Za-z_]\w*)\s*=/g)) taken.add(m[1]);
    return taken.has(base) ? uniqueVar(parsed, base, code) : base;
  }

  function uniqueVar(parsed, base, code) {
    const taken = new Set([...Object.keys(parsed.byVar), ...parsed.funcs.map((f) => f.name)]);
    for (const m of code.matchAll(/\b([A-Za-z_]\w*)\s*=/g)) taken.add(m[1]);
    for (let i = 1; ; i++) {
      const name = `${base}${i}`;
      if (!taken.has(name)) return name;
    }
  }

  // ---------------------------------------------------------------- applying edits
  function linesOf(node) {
    const set = new Set([node.line, ...Object.values(node.props).map((p) => p.line)]);
    for (const c of node.children) for (const l of linesOf(c)) set.add(l);
    return [...set].sort((a, b) => a - b);
  }
  const ownLast = (node) => Math.max(node.line, ...Object.values(node.props).map((p) => p.line));
  const subtreeLast = (node) => Math.max(...linesOf(node));
  function uiLast(parsed) {
    const all = [parsed.win.line, ...Object.values(parsed.win.props).map((p) => p.line)];
    for (const n of parsed.nodes) all.push(...linesOf(n));
    return Math.max(...all);
  }

  function makeEditor(model) {
    const monaco = window.monaco;
    const eol = model.getEOL();
    const ops = [];
    const max = (ln) => model.getLineMaxColumn(ln);
    const R = (a, b, c, d) => new monaco.Range(a, b, c, d);
    return {
      replace(ln, text) { ops.push({ range: R(ln, 1, ln, max(ln)), text }); },
      insertAfter(ln, text) {
        if (ln <= 0) ops.push({ range: R(1, 1, 1, 1), text: text + eol });
        else ops.push({ range: R(ln, max(ln), ln, max(ln)), text: eol + text });
      },
      remove(ln) {
        const count = model.getLineCount();
        if (ln < count) ops.push({ range: R(ln, 1, ln + 1, 1), text: '' });
        else if (ln > 1) ops.push({ range: R(ln - 1, max(ln - 1), ln, max(ln)), text: '' });
        else ops.push({ range: R(1, 1, 1, max(1)), text: '' });
      },
      commit() {
        if (!ops.length) return;
        model.pushStackElement();
        model.pushEditOperations([], ops.map((o) => ({ ...o, forceMoveMarkers: true })), () => null);
        model.pushStackElement();
      },
    };
  }

  const Edits = {
    setValue(model, node, index, value) {
      const ed = makeEditor(model);
      node.values = [...node.values];
      node.values[index] = value;
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
      let ownerLine = null;
      if (!varName) {
        varName = uniqueVar(parsed, KINDS[node.kind].name || node.kind, model.getValue());
        ownerLine = lineFor(node, varName);
      }
      const text = propLine(varName, key, value);
      if (existing) {
        ed.replace(existing.line, text);
        if (ownerLine) ed.replace(node.line, ownerLine);
      } else {
        const after = ownLast(node);
        if (ownerLine && after === node.line) ed.replace(node.line, ownerLine + model.getEOL() + text);
        else {
          if (ownerLine) ed.replace(node.line, ownerLine);
          ed.insertAfter(after, text);
        }
      }
      ed.commit();
      return varName;
    },

    add(model, parsed, kind, container) {
      const info = KINDS[kind];
      const ed = makeEditor(model);
      let parentVar = container.var;
      let containerLine = null;
      if (!parentVar) {
        parentVar = uniqueVar(parsed, KINDS[container.kind].name, model.getValue());
        containerLine = lineFor(container, parentVar);
      }
      const varName = info.name ? uniqueVar({ ...parsed, byVar: { ...parsed.byVar, [parentVar]: 1 } }, info.name, model.getValue()) : null;
      const node = { kind, parentVar, values: info.args.map((a) => a.init ?? undefined), comment: '' };
      const text = lineFor(node, varName);
      const after = container.kind === 'window' ? uiLast(parsed) : subtreeLast(container);
      if (containerLine && after === container.line) ed.replace(container.line, containerLine + model.getEOL() + text);
      else {
        if (containerLine) ed.replace(container.line, containerLine);
        ed.insertAfter(after, text);
      }
      ed.commit();
      return varName ? `v:${varName}` : `l:${after + 1}`;
    },

    remove(model, node) {
      const ed = makeEditor(model);
      for (const ln of linesOf(node).reverse()) ed.remove(ln);
      ed.commit();
    },

    move(model, node, dir) {
      const sibs = node.parent.children;
      const i = sibs.indexOf(node);
      const other = sibs[i + dir];
      if (!other) return false;
      const lines = linesOf(node);
      const text = lines.map((ln) => model.getLineContent(ln)).join(model.getEOL());
      const ed = makeEditor(model);
      for (const ln of [...lines].reverse()) ed.remove(ln);
      if (dir < 0) ed.insertAfter(Math.min(...linesOf(other)) - 1, text);
      else ed.insertAfter(subtreeLast(other), text);
      ed.commit();
      return true;
    },

    addFunction(model, name) {
      const ed = makeEditor(model);
      const last = model.getLineCount();
      const blank = model.getLineContent(last).trim() === '';
      ed.insertAfter(last, `${blank ? '' : model.getEOL()}func ${name}():${model.getEOL()}    say "${name} ran"`);
      ed.commit();
    },

    addWindow(model, lib) {
      const ed = makeEditor(model);
      const code = model.getValue();
      const lines = code.split(/\r?\n/);
      let at = 0;
      lines.forEach((l, i) => { if (/^(import|mention)\s+\w+/.test(l)) at = i + 1; });
      const eol = model.getEOL();
      const hasImport = new RegExp(`^(import|mention)\\s+${lib}\\b`, 'm').test(code);
      const text = `${hasImport ? '' : `import ${lib}${eol}`}${eol}app = ${lib}.window("My App")${eol}app:heading "Hello!"`;
      ed.insertAfter(at, text);
      ed.commit();
    },
  };

  // ---------------------------------------------------------------- shared property form
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
    const wrap = document.createElement('label');
    wrap.className = 'pf';
    wrap.innerHTML = `<span class="pf-l">${esc(label)}</span>`;
    wrap.appendChild(control);
    if (hint) wrap.insertAdjacentHTML('beforeend', `<span class="pf-h">${esc(hint)}</span>`);
    return wrap;
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
    } else if (type === 'bool') {
      el = document.createElement('span');
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
      el = document.createElement('select');
      const options = ['', ...opts.funcs, '+new'];
      for (const o of options) {
        const op = document.createElement('option');
        op.value = o;
        op.textContent = o === '' ? '(nothing)' : o === '+new' ? '+ New function…' : o;
        el.appendChild(op);
      }
      el.value = value || '';
      el.onchange = () => onChange(el.value);
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
    info.args.forEach((a, i) => {
      let value = node.values[i];
      let type = a.type;
      if (value && typeof value === 'object' && 'raw' in value) {
        type = 'raw';
        value = value.raw;
      }
      const shown = value === undefined ? (a.type === 'bool' || a.type === 'select' ? a.def : '') : value;
      const ctl = control(type === 'raw' ? 'text' : type, shown,
        { options: a.options, funcs: parsed.funcs.map((f) => f.name) },
        (v) => {
          if (type === 'raw') return ctx.apply((m, p, n) => Edits.setValue(m, n, i, v === '' ? undefined : { raw: v }));
          if (a.type === 'fn' && v === '+new') {
            const fname = freeName(parsed, node.var ? `${node.var}_clicked` : 'clicked', ctx.model.getValue());
            ctx.apply((m, p, n) => { Edits.setValue(m, n, i, fname); Edits.addFunction(m, fname); }, true);
            return;
          }
          ctx.apply((m, p, n) => Edits.setValue(m, n, i, v === '' ? undefined : v));
        });
      host.appendChild(field(type === 'raw' ? `${a.label} (code)` : a.label, ctl));
    });
    for (const key of info.props) {
      const p = PROPS[key];
      const ctl = control(p.type, propValue(node, key), { options: p.options }, (v) => {
        ctx.apply((m, pr, n) => {
          const name = Edits.setProp(m, pr, n, key, v);
          if (name && !n.var) ctx.rekey(`v:${name}`);
        });
      });
      host.appendChild(field(p.label, ctl, p.hint));
    }
    if (!info.args.length && !info.props.length) host.insertAdjacentHTML('beforeend', '<div class="pf-empty">Nothing to set here.</div>');
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
      case 'card': {
        const box = document.createElement('div');
        box.className = node.kind === 'row' ? 'pv-row' : 'pv-card';
        if (!node.children.length) box.innerHTML = `<div class="pv-empty-slot">Empty ${node.kind}. Select it and add things.</div>`;
        for (const c of node.children) box.appendChild(previewNode(c, sel));
        el.appendChild(box);
        break;
      }
      default: break;
    }
    return el;
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
          const rot = (sel, deg) => el.querySelector(sel)?.setAttribute('transform', `rotate(${deg} 50 50)`);
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
  const S = { file: null, model: null, sub: null, parsed: null, sel: 'window', stopClocks: () => {}, selfEdit: false };
  let ide = null;

  function host() { return $('#studio'); }

  function skeleton() {
    host().innerHTML = `
      <div class="sd">
        <div class="sd-bar">
          <span class="fl sd-logo">&#xE790;</span><b>Design Studio</b>
          <select id="sd-file" title="Which file to design"></select>
          <span class="sd-lib" id="sd-lib"></span>
          <span class="sd-tip">Everything you change here is written into your code. Ctrl+Z undoes it.</span>
          <div class="sd-bar-r">
            <button class="btn sm" id="sd-code">View code</button>
            <button class="btn sm primary" id="sd-run"><svg viewBox="0 0 16 16"><path d="M5 3.6c0-.8.9-1.3 1.6-.85l6.2 4.1c.6.4.6 1.3 0 1.7l-6.2 4.1C5.9 13.1 5 12.6 5 11.8z"/></svg>Run app</button>
          </div>
        </div>
        <div class="sd-main">
          <aside class="sd-left">
            <div class="sd-h">Add to <span id="sd-target">window</span></div>
            <div class="sd-palette" id="sd-palette"></div>
            <div class="sd-h">Layers</div>
            <div class="sd-layers" id="sd-layers"></div>
          </aside>
          <section class="sd-canvas" id="sd-canvas"></section>
          <aside class="sd-right">
            <div class="sd-h" id="sd-props-title">Window</div>
            <div class="sd-props" id="sd-props"></div>
            <div class="sd-actions" id="sd-actions"></div>
          </aside>
        </div>
      </div>`;
    $('#sd-code').onclick = () => ide.openFile(S.file);
    $('#sd-run').onclick = () => ide.runFile(S.file);
    $('#sd-file').onchange = (e) => show(e.target.value);
    const pal = $('#sd-palette');
    for (const [kind, info] of Object.entries(KINDS)) {
      const b = document.createElement('button');
      b.className = 'sd-pal';
      b.innerHTML = `<span class="ic">${ICONS[kind]}</span>${esc(info.label)}`;
      b.onclick = () => add(kind);
      pal.appendChild(b);
    }
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
  }

  function apply(fn, rerenderForm = false) {
    S.selfEdit = !rerenderForm;
    const node = findByKey(S.parsed, S.sel);
    fn(S.model, S.parsed, node);
  }

  function render(withForm = true) {
    S.parsed = parse(S.model.getValue());
    const p = S.parsed;
    const canvas = $('#sd-canvas');
    S.stopClocks();
    if (!p.win) {
      $('#sd-lib').textContent = '';
      canvas.innerHTML = `<div class="sd-none"><b>This file doesn't have an app window yet</b><span>Add one to start designing. You can always switch between tgui and mtgui later.</span>
        <div><button class="btn primary" data-lib="mtgui">Add an mtgui window (fancy)</button><button class="btn" data-lib="tgui">Add a tgui window</button></div></div>`;
      canvas.querySelectorAll('[data-lib]').forEach((b) => (b.onclick = () => { S.selfEdit = false; Edits.addWindow(S.model, b.dataset.lib); }));
      $('#sd-layers').innerHTML = '';
      $('#sd-props').innerHTML = '';
      $('#sd-actions').innerHTML = '';
      return;
    }
    if (!findByKey(p, S.sel)) S.sel = 'window';
    const sel = findByKey(p, S.sel);
    const modern = p.win.lib === 'mtgui';
    $('#sd-lib').textContent = modern ? 'mtgui · modern' : 'tgui';
    $('#sd-lib').className = 'sd-lib' + (modern ? ' modern' : '');
    const target = sel.kind === 'window' || KINDS[sel.kind]?.container ? sel : sel.parent;
    $('#sd-target').textContent = target.kind === 'window' ? 'window' : target.var || KINDS[target.kind].label.toLowerCase();

    const theme = propValue(p.win, 'theme') || 'dark';
    const accent = propValue(p.win, 'accent') || 'blue';
    const [a1, a2] = modern ? GRADIENTS[accent] || GRADIENTS.blue : [FLAT[accent] || FLAT.blue, FLAT[accent] || FLAT.blue];
    const win = document.createElement('div');
    win.className = `pv-window ${modern ? 'modern' : 'classic'} theme-${theme}` + (S.sel === 'window' ? ' sel' : '');
    win.style.setProperty('--pv-a', a1);
    win.style.setProperty('--pv-a2', a2);
    const w = typeof p.win.values[1] === 'number' ? p.win.values[1] : 420;
    const h = typeof p.win.values[2] === 'number' ? p.win.values[2] : 520;
    win.style.width = `${Math.max(240, Math.min(900, w))}px`;
    win.style.minHeight = `${Math.max(160, Math.min(1000, h))}px`;
    const title = typeof p.win.values[0] === 'string' ? p.win.values[0] : 'My App';
    win.innerHTML = `<div class="pv-titlebar" data-key="window"><img src="assets/icon.svg" alt=""><span>${esc(title)}</span><i></i><i></i><i></i></div><div class="pv-body" data-key="window"></div>`;
    const body = win.querySelector('.pv-body');
    for (const n of p.win.children) body.appendChild(previewNode(n, S.sel));
    canvas.innerHTML = '';
    canvas.appendChild(win);
    canvas.onclick = (e) => {
      const el = e.target.closest('[data-key]');
      if (!el) return;
      e.stopPropagation();
      const node = findByKey(S.parsed, el.dataset.key);
      if (node && (node.kind === 'toggle' || node.kind === 'checkbox') && S.sel === el.dataset.key) {
        el.querySelector('.pv-toggle, .pv-checkbox')?.classList.toggle('on');
      }
      select(el.dataset.key);
    };
    S.stopClocks = startClocks(canvas);

    renderLayers();
    if (withForm) renderProps();
  }

  function renderLayers() {
    const box = $('#sd-layers');
    box.innerHTML = '';
    const row = (node, depth) => {
      const b = document.createElement('button');
      b.className = 'sd-layer' + (keyOf(node) === S.sel ? ' sel' : '');
      b.style.paddingLeft = `${8 + depth * 14}px`;
      const info = kindInfo(node);
      b.innerHTML = `<span class="ic">${ICONS[node.kind]}</span><span>${esc(info.label)}</span><span class="nm">${esc(node.var || '')}</span>`;
      b.onclick = () => select(keyOf(node));
      box.appendChild(b);
      for (const c of node.children) row(c, depth + 1);
    };
    row(S.parsed.win, 0);
  }

  function renderProps() {
    const node = findByKey(S.parsed, S.sel);
    const info = kindInfo(node);
    $('#sd-props-title').innerHTML = `${esc(info.label)} <span class="nm">${esc(node.var || '')}</span>`;
    renderForm($('#sd-props'), {
      node, parsed: S.parsed, model: S.model, apply,
      rekey: (key) => { S.sel = key; },
    });
    const act = $('#sd-actions');
    act.innerHTML = '';
    if (node.kind === 'window') {
      const lib = node.lib === 'mtgui' ? 'tgui' : 'mtgui';
      act.innerHTML = `<button class="btn sm" data-a="lib">Switch to ${lib}</button><button class="btn sm" data-a="code">Show in code</button>`;
      act.querySelector('[data-a="lib"]').onclick = () => switchLib(lib);
    } else {
      act.innerHTML = `<button class="btn sm" data-a="up" title="Move up">↑ Up</button><button class="btn sm" data-a="down" title="Move down">↓ Down</button>
        <button class="btn sm" data-a="code">Show in code</button><button class="btn sm danger" data-a="del">Delete</button>`;
      act.querySelector('[data-a="up"]').onclick = () => { S.selfEdit = false; Edits.move(S.model, node, -1); };
      act.querySelector('[data-a="down"]').onclick = () => { S.selfEdit = false; Edits.move(S.model, node, 1); };
      act.querySelector('[data-a="del"]').onclick = () => removeNode(node);
    }
    act.querySelector('[data-a="code"]').onclick = () => ide.goToLine(S.file, node.line);
  }

  function select(key) {
    S.sel = key;
    render(true);
  }

  function add(kind) {
    const sel = findByKey(S.parsed, S.sel) || S.parsed?.win;
    if (!S.parsed?.win) return ide.toast('Add a window first.');
    const target = sel.kind === 'window' || KINDS[sel.kind]?.container ? sel : sel.parent;
    S.selfEdit = false;
    S.sel = Edits.add(S.model, S.parsed, kind, target);
  }

  function removeNode(node) {
    const used = node.var && S.model.getValue().split(/\r?\n/).some((l, i) => !linesOf(node).includes(i + 1) && new RegExp(`\\b${node.var}\\b`).test(stripComment(l).code));
    S.selfEdit = false;
    S.sel = keyOf(node.parent);
    Edits.remove(S.model, node);
    if (used) ide.toast(`Removed. Some code still mentions ${node.var}. Check the red marks when you run.`, 'error', 5000);
  }

  function switchLib(lib) {
    const ed = makeEditor(S.model);
    const p = S.parsed;
    if (p.importLine) {
      const line = S.model.getLineContent(p.importLine);
      ed.replace(p.importLine, line.replace(/\bm?tgui\b/, lib));
    }
    ed.replace(p.win.line, S.model.getLineContent(p.win.line).replace(/\bm?tgui\.window/, `${lib}.window`));
    S.selfEdit = false;
    ed.commit();
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
    closeCustomizer,
    parse,
  };
})();
