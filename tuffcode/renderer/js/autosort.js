// Auto Code Sort: re-indents Tuff code, puts imports first and functions last, tidies spacing and adds notes.
(function (root) {
  const INDENT = 4;
  const HEADER_RE = /^#\s*──\s.*──+\s*$/;
  const NOTE_RE = /^#\s*↳\s/;

  // Split a line into code and comment, ignoring # inside strings.
  function splitComment(text) {
    let quote = null;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quote) {
        if (c === '\\') i++;
        else if (c === quote) quote = null;
      } else if (c === '"' || c === "'") quote = c;
      else if (c === '#') return { code: text.slice(0, i).trimEnd(), comment: text.slice(i) };
    }
    return { code: text.trimEnd(), comment: '' };
  }

  // Apply fn to the parts of code that are outside string literals.
  function outsideStrings(code, fn) {
    let out = '', buf = '', quote = null;
    for (let i = 0; i < code.length; i++) {
      const c = code[i];
      if (quote) {
        out += c;
        if (c === '\\' && i + 1 < code.length) { out += code[++i]; continue; }
        if (c === quote) quote = null;
      } else if (c === '"' || c === "'") {
        out += fn(buf) + c;
        buf = '';
        quote = c;
      } else buf += c;
    }
    return out + fn(buf);
  }

  function bracketDelta(code) {
    let d = 0;
    outsideStrings(code, (part) => {
      for (const c of part) {
        if (c === '(' || c === '[') d++;
        else if (c === ')' || c === ']') d--;
      }
      return part;
    });
    return d;
  }

  function isOpener(code) {
    return /^(if|elif|while|for|func)\b.*(:|\bthen)$/.test(code) || /^else\s*(:|then)?$/.test(code) || /^else\s+if\b.*(:|\bthen)$/.test(code);
  }

  function tidy(text) {
    const { code, comment } = splitComment(text);
    let c = code;
    let fixes = 0;
    if (c) {
      const before = c;
      c = outsideStrings(c, (part) => part.replace(/,(?=[^\s)\]])/g, ', ').replace(/[ \t]{2,}/g, ' '));
      c = c.replace(/^([A-Za-z_]\w*(?:\[[^\]]*\])?)\s*(\+=|-=|\*=|\/=|=)(?!=)\s*/, '$1 $2 ');
      if (c !== before) fixes++;
    }
    let note = comment;
    if (note && /^#[^\s#!─↳]/.test(note)) { note = '# ' + note.slice(1); fixes++; }
    const line = c && note ? `${c}  ${note}` : c || note;
    return { line, fixes };
  }

  function reindent(lines) {
    const out = [];
    const stack = [{ w: 0, forced: false }];
    let prevOpener = false, prevW = 0, depth = 0, changed = 0, fixes = 0;
    for (const raw of lines) {
      const expanded = raw.replace(/^[ \t]+/, (m) => m.replace(/\t/g, ' '.repeat(INDENT)));
      const text = expanded.trim();
      if (!text) {
        out.push({ level: -1, text: '' });
        while (stack.length > 1 && stack[stack.length - 1].forced) stack.pop();
        prevOpener = false;
        continue;
      }
      const w = expanded.length - expanded.trimStart().length;
      if (depth > 0) {
        out.push({ level: stack.length, text, cont: true, orig: raw });
        depth += bracketDelta(splitComment(text).code);
        continue;
      }
      const { code } = splitComment(text);
      const isComment = !code;
      let level;
      if (prevOpener) {
        stack.push(w > prevW ? { w, forced: false } : { w: prevW, forced: true });
        level = stack.length - 1;
      } else if (isComment) {
        let n = stack.length;
        while (n > 1 && !stack[n - 1].forced && w < stack[n - 1].w) n--;
        level = n - 1;
      } else {
        while (stack.length > 1) {
          const top = stack[stack.length - 1];
          if (top.forced ? (w < top.w || /^(elif|else|func|import|mention)\b/.test(code)) : w < top.w) stack.pop();
          else break;
        }
        const top = stack[stack.length - 1];
        if (!top.forced && w > top.w) stack.push({ w, forced: false });
        level = stack.length - 1;
      }
      out.push({ level, text, orig: raw });
      if (!isComment) {
        prevOpener = isOpener(code);
        prevW = w;
        depth = Math.max(0, bracketDelta(code));
      }
    }
    const lines2 = out.map((l) => {
      if (l.level < 0) return { level: -1, text: '' };
      const t = l.cont ? { line: l.text, fixes: 0 } : tidy(l.text);
      fixes += t.fixes;
      const line = ' '.repeat(l.level * INDENT) + t.line;
      if (line !== l.orig.replace(/\s+$/, '')) changed++;
      return { level: l.cont ? Math.max(1, l.level) : l.level, text: line, cont: l.cont };
    });
    return { lines: lines2, changed, fixes };
  }

  function chunkify(lines) {
    const chunks = [];
    let pending = [];
    let blankBefore = false;
    let current = null;
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (l.level === -1) {
        const next = lines.slice(i + 1).find((x) => x.level !== -1);
        if (current && next && next.level > 0) { current.lines.push(''); continue; }
        if (pending.length) { chunks.push({ type: 'comments', lines: pending, blankBefore }); pending = []; }
        current = null;
        blankBefore = true;
        continue;
      }
      if (l.level > 0 || l.cont) {
        if (current) current.lines.push(l.text);
        else chunks.push({ type: 'main', lines: [...pending, l.text], blankBefore }), (pending = []), (blankBefore = false);
        continue;
      }
      const body = l.text.trim();
      if (body.startsWith('#')) { pending.push(l.text); continue; }
      const type = /^(import|mention)\s/.test(body) ? 'import' : /^func\s/.test(body) ? 'func' : 'main';
      current = { type, head: body, comments: pending, lines: [l.text], blankBefore };
      chunks.push(current);
      pending = [];
      blankBefore = false;
    }
    if (pending.length) chunks.push({ type: 'comments', lines: pending, blankBefore });
    for (const c of chunks) while (c.lines && c.lines[c.lines.length - 1] === '') c.lines.pop();
    return chunks;
  }

  function header(name) {
    const base = `# ── ${name} `;
    return base + '─'.repeat(Math.max(3, 44 - base.length));
  }

  function plural(n, word) {
    return `${n} ${word}${Number(n) === 1 ? '' : 's'}`;
  }

  function functionNote(name, params, mainText, allText) {
    const n = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const notes = [];
    const str = `("(?:[^"\\\\]|\\\\.)*"|'(?:[^'\\\\]|\\\\.)*')`;
    let m;
    const btn = new RegExp(`:button\\s*\\(\\s*${str}\\s*,\\s*${n}\\b`, 'g');
    while ((m = btn.exec(allText))) notes.push(`Runs when the ${m[1].replace(/^'|'$/g, '"')} button is clicked.`);
    const every = new RegExp(`:every\\s*\\(\\s*([\\d.]+)\\s*,\\s*${n}\\b`, 'g');
    while ((m = every.exec(allText))) notes.push(`Runs every ${plural(m[1], 'second')}.`);
    const after = new RegExp(`:after\\s*\\(\\s*([\\d.]+)\\s*,\\s*${n}\\b`, 'g');
    while ((m = after.exec(allText))) notes.push(`Runs once, ${plural(m[1], 'second')} after it's set up.`);
    const evt = new RegExp(`\\b([A-Za-z_]\\w*):(change|enter|click)\\s*\\(?\\s*${n}\\b`, 'g');
    while ((m = evt.exec(allText))) {
      notes.push({ change: `Runs when ${m[1]} changes.`, enter: `Runs when Enter is pressed in ${m[1]}.`, click: `Runs when ${m[1]} is clicked.` }[m[2]]);
    }
    const calls = (allText.match(new RegExp(`(?<!func\\s+)\\b${n}\\s*\\(`, 'g')) || []).length;
    if (!notes.length) {
      if (calls) notes.push(`Used ${calls === 1 ? 'once' : `${calls} times`} in your code.`);
      else notes.push('Not used anywhere yet.');
    }
    const unique = [...new Set(notes)];
    let note = unique.slice(0, 2).join(' ');
    if (params.length) note += ` Takes: ${params.join(', ')}.`;
    return `# ↳ ${note}`;
  }

  function sort(source) {
    const eol = source.includes('\r\n') ? '\r\n' : '\n';
    const original = source.split(/\r?\n/);
    const cleaned = original.filter((l) => !HEADER_RE.test(l.trim()) && !NOTE_RE.test(l.trim()));
    const removedNotes = original.length - cleaned.length;
    const { lines, changed, fixes } = reindent(cleaned);
    const chunks = chunkify(lines);

    const intro = [];
    let i = 0;
    while (i < chunks.length && chunks[i].type === 'comments') intro.push(chunks[i++]);
    const rest = chunks.slice(i);
    const imports = [];
    const seen = new Set();
    for (const c of rest.filter((c) => c.type === 'import')) {
      if (seen.has(c.head)) continue;
      seen.add(c.head);
      imports.push(c);
    }
    const funcs = rest.filter((c) => c.type === 'func');
    const main = rest.filter((c) => c.type === 'main' || c.type === 'comments');

    const order = (c) => rest.indexOf(c);
    const moved = imports.some((c, k) => k > 0 && order(c) < order(imports[k - 1]))
      || (imports.length && main.some((c) => order(c) < order(imports[imports.length - 1])))
      || (funcs.length && main.some((c) => order(c) > order(funcs[0])));

    const allText = cleaned.join('\n');
    const mainText = main.map((c) => [...(c.comments || []), ...c.lines].join('\n')).join('\n');
    const sections = [imports.length, main.length, funcs.length].filter(Boolean).length;
    const withHeaders = sections >= 2;
    const out = [];
    const blank = () => { if (out.length && out[out.length - 1] !== '') out.push(''); };

    for (const c of intro) { if (c.blankBefore) blank(); out.push(...c.lines); }
    if (imports.length) {
      blank();
      if (withHeaders) out.push(header('Libraries'));
      for (const c of imports) out.push(...c.comments, ...c.lines);
    }
    if (main.length) {
      blank();
      if (withHeaders) out.push(header('Main program'));
      main.forEach((c, k) => {
        if (k > 0 && c.blankBefore) blank();
        out.push(...(c.comments || []), ...c.lines);
      });
    }
    let notesAdded = 0;
    if (funcs.length) {
      blank();
      if (withHeaders) out.push(header('Functions'));
      funcs.forEach((c, k) => {
        if (k > 0) blank();
        const m = c.head.match(/^func\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?/);
        if (m) {
          out.push(functionNote(m[1], (m[2] || '').split(',').map((s) => s.trim()).filter(Boolean), mainText, allText));
          notesAdded++;
        }
        out.push(...c.comments, ...c.lines);
      });
    }
    while (out.length && out[out.length - 1] === '') out.pop();
    while (out.length && out[0] === '') out.shift();
    const code = out.join(eol) + eol;

    const summary = [];
    if (changed) summary.push(`fixed indentation on ${plural(changed, 'line')}`);
    if (moved) summary.push('moved imports to the top and functions to the bottom');
    if (notesAdded > removedNotes) summary.push(`added ${plural(notesAdded - Math.min(notesAdded, removedNotes), 'note')}`);
    else if (notesAdded) summary.push('refreshed the notes');
    if (fixes) summary.push(`tidied spacing on ${plural(fixes, 'line')}`);
    return { code, summary };
  }

  const api = { sort };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TuffSort = api;
})(typeof window !== 'undefined' ? window : globalThis);
