// The Tuff Debugger (1.5.0). A breakpoint is a red dot in the gutter of a .tuf file (click the glyph margin, or F9),
// in any file the program imports too; they stay for the session, also in files whose tabs are closed. Debug (the bug
// next to Run, Shift+F9) runs the program with the debugger: it stops at breakpoints, the line it's on is lit (and its
// file opens, when it's another one), and the debug pane beside the Run output has the toolbar (Continue F5, Step Over
// F10, Step Into F11, Step Out Shift+F11, Pause, Stop), the Variables panel and the call stack. Watch it run shows each
// line as it runs, at a speed the slider sets. The program's say and input stay in the Run window, as in any run.
// The program talks to this through main.js (debug.js), in the JSON lines tuff.py's "the debugger" section lists.
(() => {
  const api = window.tuff;
  let ide = null;
  let monaco = null;
  let editor = null;

  // Watch it run: the seconds a line is shown for, from the slider's slow (1) to fast (10).
  const SPEEDS = [2, 1.4, 1, 0.7, 0.5, 0.35, 0.24, 0.15, 0.08, 0.03];
  const delayOf = (speed) => SPEEDS[Math.min(Math.max(Math.round(speed) || 5, 1), 10) - 1];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const basename = (p) => String(p || '').split(/[\\/]/).filter(Boolean).pop() || '';
  // A file's key: the same file however its path is written (Windows ignores case, and takes / for \).
  const key = (p) => (api?.platform === 'win32' ? String(p).replace(/\//g, '\\').toLowerCase() : String(p));
  const isTuf = (p) => /\.tuf$/i.test(p || '');
  // A model's file: its tab's path (a tab renamed in the project tree keeps its model, whose uri has the old path), or
  // its uri's for one with no tab yet (attach, as the tab opens).
  const modelPath = (model) => (model && !model.isDisposed() && model.uri.scheme === 'file' ? ide?.pathOf?.(model) || model.uri.fsPath : null);

  // The step buttons' pictures (the others are MingCute's): an arc over a line, an arrow into it, and one out of it.
  const svg = (body) => `<svg viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;
  const STROKE = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  const ICONS = {
    next: svg(`<path ${STROKE} d="M4.5 13a7.5 7.5 0 0 1 14.6-2.4"/><path ${STROKE} d="M20 6v5h-5"/><circle cx="12" cy="19" r="2" fill="currentColor"/>`),
    stepIn: svg(`<path ${STROKE} d="M12 3v10m-4.5-4.5L12 13l4.5-4.5"/><circle cx="12" cy="19.5" r="2" fill="currentColor"/>`),
    stepOut: svg(`<path ${STROKE} d="M12 14V4M7.5 8.5L12 4l4.5 4.5"/><circle cx="12" cy="19.5" r="2" fill="currentColor"/>`),
    watch: svg(`<path ${STROKE} d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle ${STROKE} cx="12" cy="12" r="3"/>`),
  };
  const BUTTONS = [
    ['continue', 'Continue (F5): run on to the next breakpoint', () => TuffIcon('play-fill')],
    ['next', 'Step Over (F10): run this line, then pause', () => ICONS.next],
    ['stepIn', 'Step Into (F11): go into the function this line calls', () => ICONS.stepIn],
    ['stepOut', 'Step Out (Shift+F11): finish this function, then pause', () => ICONS.stepOut],
    ['pause', 'Pause', () => TuffIcon('pause-line')],
    ['stop', 'Stop (Ctrl+F2)', () => TuffIcon('stop-fill')],
  ];

  // ---------- breakpoints ----------
  // Each file's: its lines while its tab is closed, or the decorations that hold them while it's open (they move with
  // their lines as the code changes). off: lines the program never stops on (it says so, see placed). While a run is
  // debugged, version: its model's as the run started (or as its tab opened), and changed: its code has changed
  // since, so the program's lines aren't the editor's any more (see edited).
  const files = new Map(); // key -> { path, lines: Set, model, ids, off: Set, version, changed }

  function entry(path) {
    const k = key(path);
    let e = files.get(k);
    if (!e) files.set(k, (e = { path, lines: new Set(), model: null, ids: [], off: new Set(), version: null, changed: false }));
    return e;
  }

  const has = (path, n) => { const e = files.get(key(path)); return !!e && linesOf(e).has(n); };

  function linesOf(e) {
    if (!e.model) return new Set(e.lines);
    const out = new Set();
    for (const id of e.ids) {
      const r = e.model.getDecorationRange(id);
      if (r) out.add(r.startLineNumber);
    }
    return out;
  }

  function draw(e, lines = linesOf(e)) {
    e.lines = lines;
    for (const n of [...e.off]) if (!lines.has(n)) e.off.delete(n);
    if (!e.model) return;
    e.ids = e.model.deltaDecorations(e.ids, [...lines].sort((a, b) => a - b).map((n) => ({
      range: new monaco.Range(n, 1, n, 1),
      options: {
        glyphMarginClassName: e.off.has(n) ? 'dbg-bp off' : 'dbg-bp',
        glyphMarginHoverMessage: { value: e.off.has(n) ? "The program never stops on this line. Click to take the breakpoint away."
          : 'A breakpoint: the debugger stops the program here. Click to take it away.' },
        stickiness: monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
      },
    })));
  }

  // A .tuf file's model (its tab opening): its breakpoints go on it, and come off it again when it closes.
  function attach(model) {
    const path = modelPath(model);
    if (!isTuf(path)) return;
    const e = entry(path);
    e.model = model;
    e.ids = [];
    if (live() && !e.changed) e.version = model.getAlternativeVersionId(); // (opened while it's debugged: the code it ran)
    draw(e, new Set([...e.lines].filter((n) => n <= model.getLineCount())));
    model.onDidChangeContent(() => {
      if (!live() || e.model !== model || e.version === null) return;
      const changed = model.getAlternativeVersionId() !== e.version; // (an edit undone is the same code again)
      if (changed === e.changed) return;
      e.changed = changed;
      if (!changed) api.debug.send({ cmd: 'setBreakpoints', file: e.path, lines: [...linesOf(e)].sort((a, b) => a - b) }); // (ones put in meanwhile)
      renderStatus();
    });
    model.onWillDispose(() => {
      e.lines = linesOf(e);
      e.model = null;
      e.ids = [];
      e.version = null;
    });
  }

  // A file whose code has changed since the debugged run started: the program runs it as it was, so the editor's line
  // numbers aren't its own. Its breakpoints stay as the program has them until the next Debug.
  const edited = () => live() && [...files.values()].some((e) => e.changed);

  function toggle(path, n) {
    const e = entry(path);
    const lines = linesOf(e);
    if (lines.has(n)) lines.delete(n);
    else lines.add(n);
    e.off.delete(n);
    draw(e, lines);
    if (live() && !e.changed) api.debug.send({ cmd: 'setBreakpoints', file: e.path, lines: [...lines].sort((a, b) => a - b) });
  }

  function toggleHere() {
    // (Design Studio or Tuff Engine in front: the code editor is hidden, and may hold another file)
    if (ide.studioVisible() || ide.engineVisible()) { ide.toast('Show the code (click its tab) to put a breakpoint on a line.'); return; }
    const model = editor?.getModel();
    const path = modelPath(model);
    if (!isTuf(path)) { ide.toast('Breakpoints go on the lines of a .tuf file.'); return; }
    toggle(path, editor.getPosition().lineNumber);
  }

  // A file's breakpoints on these lines (Auto Code Sort puts each back on its own line, ide.js). The lines they were
  // hollow on aren't theirs any more: the program says again at the next Debug.
  function setLines(path, lines) {
    const e = entry(path);
    const set = new Set(lines);
    e.off.clear();
    draw(e, set);
    if (live() && !e.changed) api.debug.send({ cmd: 'setBreakpoints', file: e.path, lines: [...set].sort((a, b) => a - b) });
  }

  // Where the program says each breakpoint stops: one on a blank line, a comment or a func line moves to the
  // statement it stops on, and one where it never stops (a kind's fields) is drawn hollow, until it stops there.
  // (Not in a file changed since the run started: the program's lines aren't the editor's.)
  function placed({ file, lines }) {
    const e = entry(file);
    if (e.changed) return;
    const now = linesOf(e);
    let changed = false;
    for (const [asked, at] of lines || []) {
      if (!now.has(asked)) continue;
      if (at === null) { if (!e.off.has(asked)) { e.off.add(asked); changed = true; } continue; }
      if (e.off.delete(asked)) changed = true; // (code written there since)
      if (at !== asked) { now.delete(asked); now.add(at); changed = true; }
    }
    if (changed) draw(e, now);
  }

  // A widget's own line in a Design Studio program, where its gear opens the widget's customizer (studio.js): a click
  // there is Studio's, unless the line has a red dot (F9 puts one there).
  const studios = (model, n) => !!window.TuffStudio?.ownsGlyph?.(model, n);

  // The faint dot under the mouse in the glyph margin, where a click adds a breakpoint.
  const hinted = { model: null, ids: [], line: 0 };
  function hint(n) {
    if (hinted.model && !hinted.model.isDisposed()) hinted.model.deltaDecorations(hinted.ids, []);
    Object.assign(hinted, { model: null, ids: [], line: n });
    const model = editor.getModel();
    const path = modelPath(model);
    if (!n || !isTuf(path) || has(path, n) || studios(model, n)) return;
    hinted.model = model;
    hinted.ids = model.deltaDecorations([], [{ range: new monaco.Range(n, 1, n, 1), options: {
      glyphMarginClassName: 'dbg-bp hint', glyphMarginHoverMessage: { value: 'Click to add a breakpoint: the debugger stops the program on this line.' } } }]);
  }

  function setupEditor() {
    const glyph = monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN;
    monaco.editor.getModels().forEach(attach);
    monaco.editor.onDidCreateModel(attach);
    // A click in the glyph margin: on a red dot it takes the breakpoint away, anywhere else it puts one there, but
    // not on a widget's own line (Design Studio's gear). The dot comes or goes once every listener has seen the
    // click, so Design Studio's sees the line as it was (it leaves a line with a dot alone).
    editor.onMouseDown((ev) => {
      if (ev.target.type !== glyph || !ev.target.position) return;
      const model = editor.getModel();
      const path = modelPath(model);
      const n = ev.target.position.lineNumber;
      if (!isTuf(path) || (!has(path, n) && studios(model, n))) return;
      Promise.resolve().then(() => {
        toggle(path, n);
        hint(0);
      });
    });
    editor.onMouseMove((ev) => {
      const n = ev.target.type === glyph && ev.target.position ? ev.target.position.lineNumber : 0;
      if (n !== hinted.line) hint(n);
    });
    editor.onMouseLeave(() => hint(0));
    editor.addAction({
      id: 'tuff.toggleBreakpoint',
      label: 'Toggle Breakpoint',
      contextMenuGroupId: '9_debug',
      contextMenuOrder: 0,
      precondition: 'editorLangId == tuff',
      run: toggleHere,
    });
  }

  // ---------- a debugged run ----------
  const S = {
    id: 0, // the debugged run's id (TuffIDE's), or 0
    state: 'off', // off, starting, running, paused or ended
    watching: false, // Watch it run
    speed: 5,
    msg: null, // the paused (or Watch it run's) message on show
    frame: 0, // the call stack's frame the Variables panel shows
    seen: null, // each value shown at the last step, by its path: the ones that change are marked
    asking: false, // Pause while input() waits for an answer
    idle: false, // ...or while nothing runs, until something happens in the program's window
    pausing: false,
    code: null, // how it ended
  };
  const live = () => S.state === 'starting' || S.state === 'running' || S.state === 'paused';
  // Continue: while paused, or to call off a Pause that hasn't happened yet.
  const canContinue = () => S.state === 'paused' || (S.state === 'running' && S.pausing);

  let watchNext = false; // the run start() starts is watched (its tuff:run-started takes it)
  async function start(how = 'continue', watch = false) {
    const file = ide.runTarget();
    if (!isTuf(file)) { ide.toast('Open a .tuf file to debug it.'); return; }
    const first = [...files.values()].map((e) => ({ cmd: 'setBreakpoints', file: e.path, lines: [...linesOf(e)] })).filter((m) => m.lines.length);
    first.push(watch ? { cmd: 'watch', delay: delayOf(S.speed) } : { cmd: how });
    for (const e of files.values()) Object.assign(e, { version: e.model ? e.model.getAlternativeVersionId() : null, changed: false });
    watchNext = watch;
    await ide.runFile(file, { debug: { first } });
  }

  function cmd(name) {
    if (name === 'stop') { ide.stopRun(); return; }
    if (name === 'continue' && S.state === 'running') { // (a Pause that hasn't happened yet: it's called off)
      Object.assign(S, { pausing: false, asking: false, idle: false });
      api.debug.send({ cmd: 'continue' });
      render(false);
      return;
    }
    if (name === 'continue' && S.watching) api.debug.send({ cmd: 'watch', delay: delayOf(S.speed) }); // (on at the slider's speed)
    else api.debug.send({ cmd: name });
    if (name === 'pause') { S.pausing = true; renderBar(); renderStatus(); }
  }

  // Step Over, Into: one step while paused; when nothing is being debugged, a new run that pauses on its first line.
  function step(name) {
    if (S.state === 'paused') { if (S.msg?.reason !== 'error') cmd(name); }
    else if (!live()) start(name);
  }

  // The eye: Watch it run on or off while it's debugged, or a new run that's watched.
  function watch(on = !(live() && S.watching)) {
    if (!live()) { if (on) start('continue', true); return; }
    S.watching = on;
    api.debug.send({ cmd: 'watch', delay: on ? delayOf(S.speed) : 0 }); // (off while paused keeps it paused)
    if (!on && S.state === 'running') { S.msg = null; clearLine(); }
    render(false);
  }

  window.addEventListener('tuff:run-started', (ev) => {
    const { id, debug } = ev.detail || {};
    const watching = !!debug && watchNext;
    watchNext = false;
    clearLine();
    if (!debug) {
      Object.assign(S, { id: 0, state: 'off', msg: null, watching });
      show(false);
      render(false);
      return;
    }
    Object.assign(S, { id, state: 'starting', msg: null, watching, frame: 0, seen: null, asking: false, idle: false, pausing: false, code: null });
    show(true);
    render(false);
  });
  window.addEventListener('tuff:run-finished', (ev) => { if (S.id && live()) ended(ev.detail?.code); });
  // Another folder opened (New Project, Open Folder, ide.js): the program being debugged is the old project's, so it
  // stops, and what it still sends on its way out is left alone.
  window.addEventListener('tuff:folder-opened', () => { if (live()) { ide.stopRun(); ended(-1); } });

  // A file or folder renamed in the project tree (ide.js): its breakpoints go with it.
  window.addEventListener('tuff:renamed', (ev) => {
    const { from, to } = ev.detail || {};
    if (!from || !to) return;
    const k = key(from);
    const sep = api?.platform === 'win32' ? '\\' : '/';
    for (const [old, e] of [...files]) {
      if (old !== k && !old.startsWith(k + sep)) continue;
      files.delete(old);
      e.path = to + e.path.slice(from.length);
      files.set(key(e.path), e);
    }
  });

  function onEvent(msg) {
    if (!S.id || msg.id !== S.id) return;
    if (msg.event === 'breakpoints') { placed(msg); return; }
    if (!live()) return; // (one that comes after the run has ended, or after Stop)
    if (msg.event === 'paused') paused(msg);
    else if (msg.event === 'watch') watched(msg);
    else if (msg.event === 'running') running();
    else if (msg.event === 'scopes') scopes(msg);
    else if (msg.event === 'asking' || msg.event === 'idle') { S[msg.event] = true; renderStatus(); }
    else if (msg.event === 'ended') ended(msg.code);
  }

  function paused(msg) {
    Object.assign(S, { state: 'paused', msg, frame: 0, asking: false, idle: false, pausing: false });
    showLine(msg.file, msg.line, msg.reason === 'error' ? 'error' : 'paused', true);
    render(true);
  }

  // Watch it run's next line: its names are drawn once a frame, however fast the lines come. (One sent before Watch it
  // run was turned off is left alone.)
  let drawing = false;
  function watched(msg) {
    if (!S.watching) return;
    Object.assign(S, { state: 'running', msg, frame: 0 });
    showLine(msg.file, msg.line, 'watch', false);
    if (drawing) return;
    drawing = true;
    requestAnimationFrame(() => { drawing = false; render(true); });
  }

  function running() {
    Object.assign(S, { state: 'running', asking: false, idle: false });
    if (!S.watching) { S.msg = null; clearLine(); }
    render(false);
  }

  function scopes(msg) {
    if (S.state !== 'paused' || !S.msg) return;
    S.msg = { ...S.msg, scopes: msg.scopes };
    S.frame = msg.frame;
    renderVars(false);
    renderStack();
  }

  function ended(code) {
    if (!live()) return;
    Object.assign(S, { state: 'ended', msg: null, watching: false, asking: false, idle: false, pausing: false, code: code ?? null });
    clearLine();
    render(false);
  }

  // A frame of the call stack: its line, and its names.
  function pick(i) {
    const f = S.state === 'paused' && S.msg?.stack?.find((x) => x.index === i);
    if (!f) return;
    S.frame = i;
    api.debug.send({ cmd: 'frame', index: i });
    showLine(f.file, f.line, i ? 'frame' : S.msg.reason === 'error' ? 'error' : 'paused', true);
    renderStack();
  }

  // ---------- the line it's on ----------
  let lit = { model: null, ids: [] };
  let litSeq = 0;
  async function showLine(file, n, kind, focus) {
    const seq = ++litSeq;
    // (with a dialog open, New Project or Search Everywhere say, the line is lit and shown, and the keyboard stays there)
    const take = focus && !ide.overlayOpen?.();
    // (Design Studio or Tuff Engine in front: the code goes in front, even when the editor has the file already)
    if (key(modelPath(editor.getModel()) || '') !== key(file) || ide.studioVisible() || ide.engineVisible()) {
      await ide.openFile(file, 0, { focus: take });
      if (seq !== litSeq) return;
    }
    const model = editor.getModel();
    if (key(modelPath(model) || '') !== key(file)) return;
    clearLine();
    n = Math.min(Math.max(1, n), model.getLineCount());
    const ruler = { error: '#f75464', watch: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#3574f0', frame: '#5fb865' }[kind] || '#e5c07b';
    lit = { model, ids: model.deltaDecorations([], [{ range: new monaco.Range(n, 1, n, 1), options: {
      isWholeLine: true, className: `dbg-line ${kind}`, glyphMarginClassName: `dbg-at ${kind}`,
      overviewRuler: { color: ruler, position: monaco.editor.OverviewRulerLane.Full } } }]) };
    if (focus) {
      editor.setPosition({ lineNumber: n, column: 1 });
      if (take) editor.focus();
    }
    editor.revealLineInCenterIfOutsideViewport(n);
  }

  function clearLine() {
    litSeq++;
    if (lit.model && !lit.model.isDisposed()) lit.model.deltaDecorations(lit.ids, []);
    lit = { model: null, ids: [] };
  }

  // ---------- the debug pane ----------
  const el = {};
  let rows = []; // the Variables panel's rows: { path, more, open }

  function mk(tag, cls) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    return node;
  }

  function makePane() {
    const split = document.getElementById('run-split');
    el.resizer = mk('div', 'resizer vertical hidden');
    el.resizer.id = 'debug-resizer';
    el.pane = mk('section', 'hidden');
    el.pane.id = 'debug-pane';
    el.bar = mk('div', 'dbg-bar');
    el.buttons = {};
    for (const [act, title, icon] of BUTTONS) {
      const b = el.buttons[act] = mk('button', 'dbg-b');
      b.dataset.act = act;
      b.title = title;
      b.innerHTML = icon();
      el.bar.appendChild(b);
    }
    el.bar.appendChild(mk('span', 'dbg-sep'));
    const eye = el.buttons.watch = mk('button', 'dbg-b');
    eye.dataset.act = 'watch';
    eye.title = 'Watch it run: show each line as it runs, slow enough to follow';
    eye.innerHTML = ICONS.watch;
    el.bar.appendChild(eye);
    el.speed = mk('label', 'dbg-speed');
    el.speed.title = 'How fast Watch it run goes';
    el.slider = mk('input');
    Object.assign(el.slider, { type: 'range', min: '1', max: '10', step: '1', value: String(S.speed) });
    el.slider.setAttribute('aria-label', 'Watch it run speed');
    const slow = mk('span');
    slow.textContent = 'Slow';
    const fast = mk('span');
    fast.textContent = 'Fast';
    el.speed.append(slow, el.slider, fast);
    el.bar.appendChild(el.speed);
    const close = el.buttons.close = mk('button', 'dbg-b');
    close.dataset.act = 'close';
    close.title = 'Close the debugger';
    close.innerHTML = TuffIcon('close-line');
    el.bar.appendChild(close);
    el.status = mk('div', 'dbg-status');
    el.status.setAttribute('aria-live', 'polite');
    const body = mk('div', 'dbg-body');
    const section = (cls, title) => {
      const sec = mk('div', `dbg-sec ${cls}`);
      const h = mk('div', 'dbg-h');
      h.textContent = title;
      const list = mk('div', 'dbg-list');
      sec.append(h, list);
      body.appendChild(sec);
      return list;
    };
    el.vars = section('vars', 'Variables');
    el.stack = section('stack', 'Call stack');
    el.pane.append(el.bar, el.status, body);
    split?.append(el.resizer, el.pane);

    el.bar.addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-act]');
      if (!b || b.disabled) return;
      const act = b.dataset.act;
      if (act === 'watch') watch();
      else if (act === 'close') show(false);
      else cmd(act);
    });
    el.slider.addEventListener('input', () => {
      S.speed = +el.slider.value;
      if (S.watching && S.state === 'running') api.debug.send({ cmd: 'watch', delay: delayOf(S.speed) });
      clearTimeout(el.saveTimer);
      el.saveTimer = setTimeout(() => ide.saveSettings({ debugSpeed: S.speed }), 500);
    });
    el.vars.addEventListener('click', (ev) => {
      const row = rows[+ev.target.closest('.dbg-var')?.dataset.i];
      if (row && row.more) api.debug.send({ cmd: 'expand', path: row.path, open: !row.open });
    });
    el.stack.addEventListener('click', (ev) => {
      const f = ev.target.closest('.dbg-frame[data-i]');
      if (f) pick(+f.dataset.i);
    });
    el.resizer.addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      el.resizer.classList.add('dragging');
      const move = (e) => {
        const box = split.getBoundingClientRect();
        const w = Math.max(300, Math.min(box.right - e.clientX, box.width * 0.75));
        document.documentElement.style.setProperty('--debug-w', `${Math.round(w)}px`);
      };
      const up = () => {
        el.resizer.classList.remove('dragging');
        removeEventListener('mousemove', move);
        removeEventListener('mouseup', up);
        ide.saveSettings({ debugW: document.documentElement.style.getPropertyValue('--debug-w') });
      };
      addEventListener('mousemove', move);
      addEventListener('mouseup', up);
    });
  }

  function show(on) {
    el.pane?.classList.toggle('hidden', !on);
    el.resizer?.classList.toggle('hidden', !on);
    if (!on) return;
    // Room for the names: a Run panel that's been made short grows a little while it's debugged (not saved).
    const root = document.documentElement.style;
    if ((parseInt(root.getPropertyValue('--bottom-h'), 10) || 230) < 280) root.setProperty('--bottom-h', '300px');
  }

  function render(stepped) {
    renderBar();
    renderStatus();
    renderVars(stepped);
    renderStack();
  }

  function renderBar() {
    if (!el.buttons) return;
    const paused = S.state === 'paused';
    const stepping = paused && S.msg?.reason !== 'error';
    const on = { continue: canContinue(), next: stepping, stepIn: stepping, stepOut: stepping, pause: S.state === 'running', stop: live(), watch: true, close: !live() };
    for (const [act, b] of Object.entries(el.buttons)) b.disabled = !on[act];
    el.buttons.watch.classList.toggle('on', S.watching);
    el.buttons.close.classList.toggle('hidden', live());
    el.speed.classList.toggle('off', !S.watching);
    document.getElementById('btn-debug')?.classList.toggle('on', live());
  }

  function renderStatus() {
    if (!el.status) return;
    const m = S.msg;
    const where = m && `line ${m.line} of ${basename(m.file)}`;
    let text = '';
    let note = '';
    if (S.state === 'starting') text = 'Starting the debugger…';
    else if (S.state === 'running') {
      text = S.asking ? 'The program is waiting for an answer in the Run window. It pauses once you type one.'
        : S.idle ? 'Your program is waiting for something to happen in its window. It pauses on the next line it runs.'
          : S.pausing ? 'Pausing…' : S.watching ? (m ? `Watching it run: ${where}.` : 'Watching it run.') : 'Running. It stops at your breakpoints, or press Pause.';
    } else if (S.state === 'paused') {
      if (m.reason === 'error') {
        text = `Stopped by an error on ${where}: ${m.error || ''}`;
        // (one in a function the program's window calls, a button's, say: it's shown and the window goes on)
        note = `The names are as they were when it went wrong. ${m.ends === false ? 'Continue lets the program carry on: its window keeps running.' : 'Continue ends the program.'}`;
      } else text = m.reason === 'breakpoint' ? `Stopped at a breakpoint on ${where}.` : `Paused on ${where}.`;
      if (m.window === 'tk') note = `${note} Its window can't move or redraw while the program is paused.`.trim();
    } else if (S.state === 'ended') {
      text = S.code === 0 ? 'The program has finished.' : S.code === 130 || S.code < 0 ? 'The program was stopped.' : 'The program has ended.';
    }
    if (edited()) note = `${note} You've changed the code since it started. Debug again to run your changes.`.trim();
    el.status.classList.toggle('error', S.state === 'paused' && m?.reason === 'error');
    el.status.innerHTML = esc(text) + (note ? `<span class="note">${esc(note)}</span>` : '');
  }

  const typeText = (v) => (v.type === 'list' || v.type === 'dictionary' ? `${v.type} (${v.more})` : v.type);

  function renderVars(stepped) {
    if (!el.vars) return;
    rows = [];
    const m = S.msg;
    if (!m) {
      el.vars.innerHTML = S.state === 'off' || S.state === 'ended' ? '' : '<div class="dbg-empty">The names show here when the program pauses.</div>';
      return;
    }
    const seen = new Map();
    const html = [];
    const walk = (vars, path, depth) => {
      for (const v of vars) {
        const p = [...path, v.name];
        const k = p.join('\u0000');
        seen.set(k, v.value);
        const changed = stepped && S.seen && S.seen.get(k) !== v.value;
        const open = !!v.kids;
        const i = rows.push({ path: p, more: v.more || 0, open }) - 1;
        html.push(`<div class="dbg-var${v.more ? ' can' : ''}${changed ? ' changed' : ''}" data-i="${i}" style="--d:${depth}">`
          + `<span class="tw">${v.more ? (open ? '▾' : '▸') : ''}</span><span class="nm">${esc(v.name)}</span>`
          + `<span class="vl" title="${esc(v.value)}">${esc(v.value)}</span><span class="ty">${esc(typeText(v))}</span></div>`);
        if (open) {
          walk(v.kids, p, depth + 1);
          if (v.more > v.kids.length) html.push(`<div class="dbg-empty" style="padding-left:${26 + (depth + 1) * 14}px">…and ${v.more - v.kids.length} more</div>`);
        }
      }
    };
    for (const scope of m.scopes || []) {
      html.push(`<div class="dbg-scope">${esc(scope.top ? `${scope.name}'s top level` : `In ${scope.name}()`)}</div>`);
      if (!scope.vars.length) html.push('<div class="dbg-empty">No names yet.</div>');
      walk(scope.vars, [scope.top ? 'top' : 'local'], 0);
    }
    if (stepped) S.seen = seen;
    el.vars.innerHTML = html.join('');
  }

  function renderStack() {
    if (!el.stack) return;
    const m = S.msg;
    if (!m || !m.stack) { el.stack.innerHTML = ''; return; }
    const html = [];
    m.stack.forEach((f, n) => {
      if (m.hidden && n === m.stack.length - 1) html.push(`<div class="dbg-frame more">…and ${m.hidden} more calls</div>`);
      html.push(`<div class="dbg-frame${f.index === S.frame ? ' sel' : ''}" data-i="${f.index}" title="${esc(f.file)}">`
        + `<span class="fn">${esc(f.top ? 'top level' : `${f.name}()`)}</span><span class="at">${esc(basename(f.file))}:${f.line}</span></div>`);
    });
    el.stack.innerHTML = html.join('');
  }

  // ---------- commands ----------
  function addCommands() {
    const add = (id, def) => ide.addCommand(id, def);
    add('debug', { label: 'Debug Current File', sc: 'Shift+F9', run: () => start('continue') });
    add('watchRun', { label: 'Watch It Run', run: () => watch(true) });
    add('debugContinue', { label: 'Continue', sc: 'F5', run: () => (canContinue() ? cmd('continue') : live() ? null : start('continue')) });
    add('stepOver', { label: 'Step Over', sc: 'F10', run: () => step('next') });
    add('stepInto', { label: 'Step Into', sc: 'F11', run: () => step('stepIn') });
    add('stepOut', { label: 'Step Out', sc: 'Shift+F11', run: () => { if (S.state === 'paused' && S.msg?.reason !== 'error') cmd('stepOut'); } });
    add('debugPause', { label: 'Pause the Program', run: () => { if (S.state === 'running') cmd('pause'); } });
    add('toggleBreakpoint', { label: 'Toggle Breakpoint', sc: 'F9', run: toggleHere });
  }

  window.TuffDebug = {
    async init(ideApi) {
      ide = ideApi;
      S.speed = +ide.settings().debugSpeed || 5;
      if (ide.settings().debugW) document.documentElement.style.setProperty('--debug-w', ide.settings().debugW);
      makePane();
      addCommands();
      document.getElementById('btn-debug')?.addEventListener('click', () => start('continue'));
      api.debug?.onEvent(onEvent);
      render(false);
      monaco = await ide.monacoReady();
      editor = ide.editor();
      setupEditor();
    },
    start,
    toggle,
    setLines,
    // A red dot on this line of the model (Design Studio leaves a click on one to the debugger, studio.js).
    hasBreakpoint: (model, n) => isTuf(modelPath(model)) && has(modelPath(model), n),
    // The breakpoints, by file: [{ path, lines }] (for the tests, Learn and Auto Code Sort).
    breakpoints: () => [...files.values()].map((e) => ({ path: e.path, lines: [...linesOf(e)].sort((a, b) => a - b) })).filter((b) => b.lines.length),
    state: () => ({ state: S.state, watching: S.watching, reason: S.msg?.reason ?? null, file: S.msg?.file ?? null, line: S.msg?.line ?? null, frame: S.frame }),
  };
})();
