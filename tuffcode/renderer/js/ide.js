(() => {
  const api = window.tuff;
  const $ = (s) => document.querySelector(s);
  const SEP = api.sep;

  const state = {
    settings: {},
    root: null,
    tabs: [],
    active: null,
    accent: null,
    running: false,
    runId: 0,
    lastRunFile: null,
    fontSize: 14,
  };
  const tree = { children: new Map(), expanded: new Set(), selected: null, justOpened: null };
  let editor = null;
  let monacoReady = null;

  // ---------- helpers ----------
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const basename = (p) => p.split(/[\\/]/).filter(Boolean).pop() || p;
  const dirname = (p) => p.replace(/[\\/][^\\/]*[\\/]?$/, '');
  const join = (a, b) => a.replace(/[\\/]+$/, '') + SEP + b;
  const rel = (p) => (state.root && p.startsWith(state.root) ? p.slice(state.root.length).replace(/^[\\/]/, '') : p);
  const ext = (p) => (basename(p).match(/\.([^.]+)$/) || [, ''])[1].toLowerCase();
  const isUnder = (p, dir) => p === dir || p.startsWith(dir + SEP);
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  const LANGS = { tuf: 'tuff', py: 'python', js: 'javascript', ts: 'typescript', json: 'json', md: 'markdown', html: 'html', css: 'css', xml: 'xml', yml: 'yaml', yaml: 'yaml', txt: 'plaintext', env: 'ini', ini: 'ini', cfg: 'ini', toml: 'ini', sh: 'shell', bat: 'bat', cmd: 'bat', ps1: 'powershell' };
  const LANG_NAMES = { tuff: 'Tuff', python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript', json: 'JSON', markdown: 'Markdown', html: 'HTML', css: 'CSS', xml: 'XML', yaml: 'YAML', plaintext: 'Plain text', ini: 'Settings (.env / .ini)', shell: 'Shell', bat: 'Batch', powershell: 'PowerShell' };
  const langFor = (p) => LANGS[ext(p)] || 'plaintext';

  function fileIcon(name, isDir, open) {
    if (isDir) {
      return open
        ? '<svg class="fi" viewBox="0 0 16 16"><path style="fill:#9aa7b0;stroke:none" d="M1.5 3.5a1 1 0 011-1h3.6l1.5 1.5h5.4a1 1 0 011 1V6H4.2a1 1 0 00-.95.68L1.5 12z"/><path style="fill:#b6c2cb;stroke:none" d="M3.6 6.5h11.3l-2 6.3a1 1 0 01-.95.7H1.6z"/></svg>'
        : '<svg class="fi" viewBox="0 0 16 16"><path style="fill:#9aa7b0;stroke:none" d="M1.5 3.5a1 1 0 011-1h3.6l1.5 1.5h5.9a1 1 0 011 1v7.5a1 1 0 01-1 1h-11a1 1 0 01-1-1z"/></svg>';
    }
    switch (ext(name)) {
      case 'tuf':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="13" height="13" rx="3.5" style="fill:var(--accent);stroke:none"/><path d="M5 5.2h6M8 5.2v6.3" style="stroke:#fff;stroke-width:1.9"/></svg>';
      case 'py':
        return '<svg class="fi" viewBox="0 0 16 16"><path style="fill:#3d7ab8;stroke:none" d="M8 1.5c-3 0-3 1.3-3 2.5v1.5h3v.5H3.8C2.3 6 1.5 7 1.5 9s.8 3 2.3 3H5v-1.8c0-1.3 1-2.2 2.2-2.2h3c1 0 1.8-.8 1.8-1.8V4c0-1.4-1.3-2.5-4-2.5z"/><path style="fill:#f4c542;stroke:none" d="M8 14.5c3 0 3-1.3 3-2.5v-1.5H8V10h4.2c1.5 0 2.3-1 2.3-3s-.8-3-2.3-3H11v1.8c0 1.3-1 2.2-2.2 2.2h-3C4.8 8 4 8.8 4 9.8V12c0 1.4 1.3 2.5 4 2.5z"/></svg>';
      case 'js':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="13" height="13" rx="2" style="fill:#e8c547;stroke:none"/><path d="M7.5 6v4.5a1.5 1.5 0 01-3 0M12 6.5c-.3-.6-.9-.8-1.4-.8-.8 0-1.3.5-1.3 1.1 0 1.5 2.8.9 2.8 2.6 0 .7-.6 1.3-1.5 1.3-.7 0-1.3-.3-1.6-1" style="stroke:#222;stroke-width:1.2"/></svg>';
      case 'json':
        return '<svg class="fi" viewBox="0 0 16 16"><path d="M5.5 2.5c-1.5 0-2 .5-2 2v1.5c0 1-.5 2-1.5 2 1 0 1.5 1 1.5 2v1.5c0 1.5.5 2 2 2M10.5 2.5c1.5 0 2 .5 2 2v1.5c0 1 .5 2 1.5 2-1 0-1.5 1-1.5 2v1.5c0 1.5-.5 2-2 2" style="stroke:#e5a64b;stroke-width:1.5"/></svg>';
      case 'md':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="3.5" width="13" height="9" rx="1.5" style="stroke:#6ea8f0"/><path d="M4 10V6l2 2 2-2v4M11 6v4m-1.5-1.5L11 10l1.5-1.5" style="stroke:#6ea8f0"/></svg>';
      default:
        return '<svg class="fi" viewBox="0 0 16 16"><path d="M4 1.5h5l3.5 3.5v9a.5.5 0 01-.5.5H4a.5.5 0 01-.5-.5V2a.5.5 0 01.5-.5z" style="stroke:#9da0a8"/><path d="M9 1.5V5h3.5M5.5 8h5M5.5 10.5h5" style="stroke:#9da0a8"/></svg>';
    }
  }

  function toast(msg, kind = 'info', ms = 3200, action = null) {
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.innerHTML = `<span class="dot"></span><span>${esc(msg)}</span>`;
    if (action) {
      const b = document.createElement('button');
      b.className = 't-act';
      b.textContent = action.label;
      b.onclick = () => { el.remove(); action.run(); };
      el.appendChild(b);
    }
    $('#toasts').appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 220); }, ms);
  }

  // ---------- modal ----------
  // choices: optional [{ label, apply(name) -> name, matches(name) -> bool }] shown as chips under the input.
  function ask({ title, value = '', confirm = false, okLabel = 'OK', validate, selectStem, choices }) {
    return new Promise((resolve) => {
      const modal = $('#modal'), input = $('#modal-input'), err = $('#modal-error'), chips = $('#modal-choices');
      $('#modal-title').textContent = title;
      $('#modal-ok').textContent = okLabel;
      input.classList.toggle('hidden', confirm);
      input.value = value;
      err.textContent = '';
      chips.classList.toggle('hidden', !choices);
      chips.innerHTML = '';
      const markChip = () => [...chips.children].forEach((b, i) => b.classList.toggle('sel', choices[i].matches(input.value.trim())));
      for (const c of choices || []) {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = c.label;
        b.onmousedown = (e) => e.preventDefault();
        b.onclick = () => {
          input.value = c.apply(input.value.trim());
          const dot = input.value.lastIndexOf('.');
          input.focus();
          input.setSelectionRange(0, dot > 0 ? dot : input.value.length);
          markChip();
        };
        chips.appendChild(b);
      }
      input.oninput = choices ? markChip : null;
      if (choices) markChip();
      modal.classList.remove('hidden');
      if (!confirm) {
        input.focus();
        const dot = value.lastIndexOf('.');
        input.setSelectionRange(0, selectStem && dot > 0 ? dot : value.length);
      } else {
        $('#modal-ok').focus();
      }
      const done = (result) => {
        modal.classList.add('hidden');
        input.removeEventListener('keydown', onKey);
        $('#modal-ok').onclick = $('#modal-cancel').onclick = modal.onmousedown = document.onkeydown = null;
        resolve(result);
      };
      const submit = () => {
        if (confirm) return done(true);
        const v = input.value.trim();
        const problem = validate ? validate(v) : null;
        if (problem) { err.textContent = problem; return; }
        done(v);
      };
      const onKey = (e) => {
        if (e.key === 'Enter') { e.preventDefault(); submit(); }
        if (e.key === 'Escape') { e.preventDefault(); done(null); }
      };
      input.addEventListener('keydown', onKey);
      if (confirm) document.onkeydown = onKey;
      $('#modal-ok').onclick = submit;
      $('#modal-cancel').onclick = () => done(null);
      modal.onmousedown = (e) => { if (e.target === modal) done(null); };
    });
  }
  const validName = (v) => (!v ? 'Name cannot be empty' : /[<>:"/\\|?*]/.test(v) ? 'Name contains invalid characters' : null);

  // ---------- context menu / dropdowns ----------
  function showMenu(x, y, items) {
    const m = $('#context-menu');
    m.innerHTML = '';
    for (const it of items) {
      if (it === 'sep') { m.appendChild(document.createElement('hr')); continue; }
      const b = document.createElement('button');
      b.className = 'mi' + (it.danger ? ' danger' : '');
      b.innerHTML = `<span>${esc(it.label)}</span>${it.sc ? `<span class="sc">${esc(it.sc)}</span>` : ''}`;
      b.onclick = () => { hideMenus(); it.run(); };
      m.appendChild(b);
    }
    m.classList.remove('hidden');
    const r = m.getBoundingClientRect();
    m.style.left = Math.min(x, innerWidth - r.width - 6) + 'px';
    m.style.top = Math.min(y, innerHeight - r.height - 6) + 'px';
  }
  function hideMenus() {
    $('#context-menu').classList.add('hidden');
    document.querySelectorAll('.menu-root.open').forEach((m) => { m.classList.remove('open'); m.querySelector('.dropdown')?.remove(); });
  }
  document.addEventListener('mousedown', (e) => {
    if (!e.target.closest('#context-menu, .menu-root')) hideMenus();
  });
  window.addEventListener('blur', hideMenus);

  // ---------- accent ----------
  function applyAccent(acc) {
    state.accent = acc;
    document.documentElement.style.setProperty('--accent', acc.a);
    document.documentElement.style.setProperty('--accent-2', acc.b);
    if (editor) {
      window.defineTuffTheme(window.monaco, acc.a);
      window.monaco.editor.setTheme('tuff-dark');
    }
  }
  const accentById = (id) => window.TUFF_ACCENTS.find((a) => a.id === id) || window.TUFF_ACCENTS[0];

  // ---------- monaco ----------
  function loadMonaco() {
    return new Promise((resolve) => {
      const base = new URL('../node_modules/monaco-editor/min/', location.href).href;
      window.MonacoEnvironment = { getWorkerUrl: () => base + 'vs/base/worker/workerMain.js' };
      window.require.config({ paths: { vs: base + 'vs' } });
      window.require(['vs/editor/editor.main'], () => {
        const monaco = window.monaco;
        window.registerTuff(monaco, state.accent.a);
        editor = monaco.editor.create($('#monaco'), {
          model: null,
          theme: 'tuff-dark',
          fontFamily: '"JetBrains Mono", "Cascadia Code", Consolas, monospace',
          fontLigatures: true,
          fontSize: state.fontSize,
          lineHeight: Math.round(state.fontSize * 1.6),
          minimap: { enabled: !!state.settings.minimap },
          wordWrap: state.settings.wordWrap ? 'on' : 'off',
          automaticLayout: true,
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          renderLineHighlight: 'all',
          scrollBeyondLastLine: false,
          padding: { top: 8 },
          bracketPairColorization: { enabled: true },
          guides: { indentation: true, bracketPairs: 'active' },
          mouseWheelZoom: true,
          stickyScroll: { enabled: true },
          fixedOverflowWidgets: true,
          glyphMargin: true,
          autoIndent: 'full',
        });
        editor.onDidChangeCursorPosition((e) => { $('#sb-pos').textContent = `${e.position.lineNumber}:${e.position.column}`; });
        // ':' and '.' open the method/library list only where it makes sense, and close
        // any list that was already showing otherwise (so Enter after "else:" is a newline).
        editor.onDidType((text) => {
          if (text !== ':' && text !== '.') return;
          const model = editor.getModel();
          if (!model || model.getLanguageId() !== 'tuff') return;
          const want = window.tuffWantsSuggest(model, editor.getPosition());
          setTimeout(() => editor.trigger('tuff', want ? 'editor.action.triggerSuggest' : 'hideSuggestWidget', {}), 0);
        });
        // Backspacing over the ':' or '.' that opened the suggestion list closes the list too.
        editor.onKeyDown((e) => {
          if (e.keyCode !== monaco.KeyCode.Backspace) return;
          const pos = editor.getPosition();
          const ch = pos.column > 1 ? editor.getModel().getLineContent(pos.lineNumber)[pos.column - 2] : '';
          if (ch === ':' || ch === '.') setTimeout(() => editor.trigger('tuff', 'hideSuggestWidget'), 0);
        });
        editor.addAction({
          id: 'tuff.autosort',
          label: 'Auto Code Sort',
          contextMenuGroupId: '1_modification',
          contextMenuOrder: 0,
          precondition: 'editorLangId == tuff',
          run: () => autoSort(),
        });
        editor.onDidChangeConfiguration(() => {
          const fs = editor.getOption(monaco.editor.EditorOption.fontSize);
          if (fs !== state.fontSize) { state.fontSize = fs; saveSettings({ fontSize: fs }); }
        });
        resolve(monaco);
      });
    });
  }

  // ---------- settings ----------
  const saveSettings = (patch) => {
    Object.assign(state.settings, patch);
    return api.settings.set(patch);
  };
  const persistSession = debounce(() => {
    saveSettings({ lastFolder: state.root, openTabs: state.tabs.map((t) => t.path), activeTab: state.active });
  }, 300);

  // ---------- project tree ----------
  async function loadChildren(dir) {
    try {
      tree.children.set(dir, await api.fs.readDir(dir));
    } catch {
      tree.children.delete(dir);
      tree.expanded.delete(dir);
    }
  }

  function treeRow(e, depth, isRoot) {
    const r = document.createElement('div');
    r.className = 'tree-row' + (isRoot ? ' root' : '') + (tree.selected === e.path ? ' selected' : '');
    r.style.paddingLeft = 6 + depth * 16 + 'px';
    r.dataset.path = e.path;
    if (e.isDir) r.dataset.dir = '1';
    const open = tree.expanded.has(e.path);
    r.innerHTML =
      `<svg class="tw ${e.isDir ? (open ? 'open' : '') : 'none'}" viewBox="0 0 16 16"><path d="M6 4l4 4-4 4"/></svg>` +
      fileIcon(e.name, e.isDir, open) +
      `<span class="name">${esc(e.name)}</span>` +
      (isRoot ? `<span class="hint">${esc(e.path)}</span>` : '');
    return r;
  }

  function treeChildren(dir, depth) {
    const wrap = document.createElement('div');
    wrap.className = 'tree-children' + (tree.justOpened === dir ? ' anim' : '');
    for (const e of tree.children.get(dir) || []) {
      wrap.appendChild(treeRow(e, depth));
      if (e.isDir && tree.expanded.has(e.path)) wrap.appendChild(treeChildren(e.path, depth + 1));
    }
    return wrap;
  }

  function renderTree() {
    const el = $('#tree');
    const scroll = el.scrollTop;
    el.innerHTML = '';
    if (!state.root) return;
    el.appendChild(treeRow({ name: basename(state.root), path: state.root, isDir: true }, 0, true));
    if (tree.expanded.has(state.root)) el.appendChild(treeChildren(state.root, 1));
    el.scrollTop = scroll;
    tree.justOpened = null;
  }

  async function toggleDir(p, force) {
    const open = force ?? !tree.expanded.has(p);
    if (open) {
      if (!tree.children.has(p)) await loadChildren(p);
      tree.expanded.add(p);
      tree.justOpened = p;
    } else {
      tree.expanded.delete(p);
    }
    renderTree();
  }

  async function refreshTree() {
    for (const dir of [...tree.expanded]) await loadChildren(dir);
    filesCache = null;
    renderTree();
  }

  function selectInTree(p) {
    tree.selected = p;
    document.querySelectorAll('.tree-row.selected').forEach((r) => r.classList.remove('selected'));
    const row = [...document.querySelectorAll('.tree-row')].find((r) => r.dataset.path === p);
    if (row) { row.classList.add('selected'); row.scrollIntoView({ block: 'nearest' }); }
  }

  $('#tree').addEventListener('click', (e) => {
    const row = e.target.closest('.tree-row');
    if (!row) return;
    const p = row.dataset.path;
    selectInTree(p);
    if (row.dataset.dir) toggleDir(p);
    else openFile(p);
  });

  $('#tree').addEventListener('contextmenu', (e) => {
    const row = e.target.closest('.tree-row');
    if (!row) return;
    e.preventDefault();
    const p = row.dataset.path;
    selectInTree(p);
    const isRoot = p === state.root;
    const items = [];
    if (row.dataset.dir) {
      items.push({ label: 'New File…', sc: 'Ctrl+Alt+N', run: () => newEntry(false, p) }, { label: 'New Folder', run: () => newEntry(true, p) }, 'sep');
    } else {
      items.push({ label: 'Open', run: () => openFile(p) });
      if (ext(p) === 'tuf') items.push({ label: `Run '${basename(p)}'`, sc: 'Shift+F10', run: async () => { await saveAll(); startRun(p); } });
      items.push('sep');
    }
    items.push({ label: 'Copy Path', run: () => navigator.clipboard.writeText(p) });
    items.push({ label: 'Reveal in Explorer', run: () => api.fs.reveal(p) });
    if (!isRoot) {
      items.push('sep', { label: 'Rename…', sc: 'Shift+F6', run: () => renameEntry(p) });
      items.push({ label: 'Delete', sc: 'Delete', danger: true, run: () => trashEntry(p) });
    }
    showMenu(e.clientX, e.clientY, items);
  });

  $('#tree').addEventListener('keydown', (e) => {
    const rows = [...document.querySelectorAll('.tree-row')];
    const i = rows.findIndex((r) => r.dataset.path === tree.selected);
    const cur = rows[i];
    const go = (r) => { if (r) { e.preventDefault(); selectInTree(r.dataset.path); } };
    if (e.key === 'ArrowDown') go(rows[Math.min(i + 1, rows.length - 1)] || rows[0]);
    else if (e.key === 'ArrowUp') go(rows[Math.max(i - 1, 0)]);
    else if (!cur) return;
    else if (e.key === 'ArrowRight' && cur.dataset.dir) { e.preventDefault(); toggleDir(cur.dataset.path, true); }
    else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (cur.dataset.dir && tree.expanded.has(cur.dataset.path)) toggleDir(cur.dataset.path, false);
      else if (cur.dataset.path !== state.root) selectInTree(dirname(cur.dataset.path));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      cur.dataset.dir ? toggleDir(cur.dataset.path) : openFile(cur.dataset.path);
    } else if (e.key === 'Delete' && cur.dataset.path !== state.root) { e.preventDefault(); trashEntry(cur.dataset.path); }
    else if (e.key === 'F6' && e.shiftKey && cur.dataset.path !== state.root) { e.preventDefault(); renameEntry(cur.dataset.path); }
  });

  function targetDir() {
    const s = tree.selected;
    if (!s) return state.root;
    const row = [...document.querySelectorAll('.tree-row')].find((r) => r.dataset.path === s);
    return row && row.dataset.dir ? s : dirname(s) || state.root;
  }

  // File types offered when making a new file. A name typed without an extension becomes a .tuf file
  // unless "Other" is picked, so Makefile, .env, notes.txt and friends are all fine.
  const stemOf = (n) => (n.startsWith('.') && n.indexOf('.', 1) < 0 ? '' : n.replace(/\.[^.]*$/, ''));
  const withExt = (e) => (n) => `${stemOf(n) || 'untitled'}.${e}`;
  const FILE_TYPES = [
    { label: 'Tuff', apply: withExt('tuf'), matches: (n) => ext(n) === 'tuf' },
    { label: 'Text', apply: withExt('txt'), matches: (n) => ext(n) === 'txt' },
    { label: 'Markdown', apply: withExt('md'), matches: (n) => ext(n) === 'md' },
    { label: 'JSON', apply: withExt('json'), matches: (n) => ext(n) === 'json' },
    { label: '.env', apply: (n) => (!stemOf(n) || stemOf(n) === 'untitled' ? '.env' : `${stemOf(n)}.env`), matches: (n) => ext(n) === 'env' },
    { label: 'Other', apply: (n) => stemOf(n) || n, matches: (n) => !!n && !['tuf', 'txt', 'md', 'json', 'env'].includes(ext(n)) },
  ];

  async function newEntry(isDir, base = targetDir()) {
    let name = await ask({
      title: isDir ? 'New Folder' : 'New File',
      value: isDir ? '' : 'untitled.tuf',
      validate: validName,
      selectStem: !isDir,
      choices: isDir ? null : FILE_TYPES,
    });
    if (!name) return;
    const p = join(base, name);
    try {
      isDir ? await api.fs.createDir(p) : await api.fs.createFile(p);
    } catch (err) {
      return toast(cleanErr(err), 'error');
    }
    await loadChildren(base);
    tree.expanded.add(base);
    filesCache = null;
    renderTree();
    selectInTree(p);
    if (!isDir) openFile(p);
  }

  async function renameEntry(p) {
    const old = basename(p);
    const name = await ask({ title: `Rename '${old}'`, value: old, validate: validName, selectStem: true, okLabel: 'Rename' });
    if (!name || name === old) return;
    const np = join(dirname(p), name);
    try {
      await api.fs.rename(p, np);
    } catch (err) {
      return toast(cleanErr(err), 'error');
    }
    for (const t of state.tabs) {
      if (isUnder(t.path, p)) {
        t.path = np + t.path.slice(p.length);
        window.monaco.editor.setModelLanguage(t.model, langFor(t.path));
      }
    }
    if (state.active && isUnder(state.active, p)) state.active = np + state.active.slice(p.length);
    if (state.lastRunFile && isUnder(state.lastRunFile, p)) state.lastRunFile = np + state.lastRunFile.slice(p.length);
    tree.expanded = new Set([...tree.expanded].map((d) => (isUnder(d, p) ? np + d.slice(p.length) : d)));
    for (const k of [...tree.children.keys()]) if (isUnder(k, p)) tree.children.delete(k);
    await refreshTree();
    selectInTree(np);
    renderTabs();
    updateChrome();
    persistSession();
  }

  async function trashEntry(p) {
    const ok = await ask({ title: `Move '${basename(p)}' to the Recycle Bin?`, confirm: true, okLabel: 'Delete' });
    if (!ok) return;
    for (const t of state.tabs.filter((t) => isUnder(t.path, p))) closeTab(t, { save: false });
    try {
      await api.fs.trash(p);
    } catch (err) {
      return toast(cleanErr(err), 'error');
    }
    tree.expanded = new Set([...tree.expanded].filter((d) => !isUnder(d, p)));
    await refreshTree();
    toast(`Moved '${basename(p)}' to the Recycle Bin`);
  }

  const cleanErr = (err) => String(err.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, '');

  // ---------- folders ----------
  async function openFolder(dir, { restore } = {}) {
    await saveAll();
    for (const t of [...state.tabs]) closeTab(t, { save: false, quiet: true });
    state.root = dir;
    tree.children.clear();
    tree.expanded = new Set([dir]);
    tree.selected = null;
    filesCache = null;
    await loadChildren(dir);
    renderTree();
    const name = basename(dir);
    $('#project-name').textContent = name;
    const initials = name.replace(/[^A-Za-z0-9 _-]/g, '').split(/[\s_-]+|(?=[A-Z])/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
    $('#proj-badge').textContent = initials || name.slice(0, 2).toUpperCase();
    const recent = [dir, ...(state.settings.recent || []).filter((r) => r !== dir)].slice(0, 8);
    await saveSettings({ lastFolder: dir, recent });
    if (restore) {
      for (const p of restore.tabs || []) if (await api.fs.exists(p)) await openFile(p, { focus: false, quiet: true });
      const act = state.tabs.find((t) => t.path === restore.active);
      if (act) activate(act, false);
    }
    updateChrome();
  }

  async function pickFolder() {
    const dir = await api.project.openFolder();
    if (dir) await openFolder(dir);
  }

  // ---------- tabs / editor ----------
  const activeTab = () => state.tabs.find((t) => t.path === state.active) || null;
  const isDirty = (t) => t.model.getAlternativeVersionId() !== t.saved;

  async function openFile(p, { focus = true, quiet = false, background = false } = {}) {
    let t = state.tabs.find((x) => x.path === p);
    if (!t) {
      let content;
      try {
        content = await api.fs.readFile(p);
      } catch (err) {
        if (!quiet) toast(`Could not open ${basename(p)}: ${cleanErr(err)}`, 'error');
        return;
      }
      const monaco = await monacoReady;
      if (state.tabs.some((x) => x.path === p)) return openFile(p, { focus, background });
      const uri = monaco.Uri.file(p);
      monaco.editor.getModel(uri)?.dispose();
      const model = monaco.editor.createModel(content, langFor(p), uri);
      model.updateOptions({ tabSize: tabSize(), insertSpaces: true });
      t = { path: p, model, saved: model.getAlternativeVersionId(), view: null };
      const tab = t;
      model.onDidChangeContent(() => scheduleCheck(tab));
      scheduleCheck(tab);
      model.onDidChangeContent(() => {
        renderTabs();
        autosave();
        window.monaco.editor.setModelMarkers(model, 'tuff', []);
      });
      state.tabs.push(t);
    }
    if (background) {
      renderTabs();
      return t;
    }
    activate(t, focus);
    return t;
  }

  // ---------- design studio view ----------
  const studio = { open: false, visible: false, file: null };

  function showStudio(file) {
    studio.open = true;
    studio.visible = true;
    if (file) studio.file = file;
    $('#studio').classList.remove('hidden');
    $('#monaco').classList.add('hidden');
    $('#breadcrumbs').classList.add('hidden');
    if (!state.running) showBottom(false);
    window.TuffStudio?.closeCustomizer();
    renderTabs();
    updateChrome();
    window.TuffStudio.show(studio.file);
  }

  function hideStudio() {
    if (!studio.visible) return;
    studio.visible = false;
    $('#studio').classList.add('hidden');
    $('#monaco').classList.remove('hidden');
    $('#breadcrumbs').classList.remove('hidden');
  }

  function closeStudio() {
    hideStudio();
    studio.open = false;
    renderTabs();
    updateChrome();
  }

  async function openStudio(file) {
    hideMenus();
    const t = activeTab();
    let target = file || studio.file || (t && ext(t.path) === 'tuf' ? t.path : null) || state.lastRunFile;
    if (!target || !(await api.fs.exists(target))) target = join(state.root, 'main.tuf');
    showStudio(target);
  }

  function activate(t, focus = true) {
    hideStudio();
    const cur = activeTab();
    if (cur && cur !== t) cur.view = editor.saveViewState();
    state.active = t.path;
    editor.setModel(t.model);
    if (t.view) editor.restoreViewState(t.view);
    if (focus) editor.focus();
    selectInTree(t.path);
    renderTabs();
    updateChrome();
    persistSession();
    const pos = editor.getPosition();
    if (pos) $('#sb-pos').textContent = `${pos.lineNumber}:${pos.column}`;
  }

  async function closeTab(t, { save = true } = {}) {
    if (save && isDirty(t)) await saveTab(t);
    const i = state.tabs.indexOf(t);
    if (i < 0) return;
    state.tabs.splice(i, 1);
    closedTabs.push(t.path);
    if (closedTabs.length > 20) closedTabs.shift();
    live.problems.delete(t.path);
    if (state.active === t.path) {
      const next = state.tabs[i] || state.tabs[i - 1];
      if (next) activate(next);
      else { state.active = null; editor?.setModel(null); }
    }
    t.model.dispose();
    renderTabs();
    updateChrome();
    persistSession();
  }

  async function saveTab(t) {
    const version = t.model.getAlternativeVersionId();
    try {
      await api.fs.writeFile(t.path, t.model.getValue());
      t.saved = version;
    } catch (err) {
      toast(`Could not save ${basename(t.path)}: ${cleanErr(err)}`, 'error');
    }
  }

  async function saveAll() {
    await Promise.all(state.tabs.filter(isDirty).map(saveTab));
    renderTabs();
  }
  const autosave = debounce(saveAll, 1500);

  function renderTabs() {
    const el = $('#tabs');
    el.innerHTML = '';
    if (studio.open) {
      const tab = document.createElement('div');
      tab.className = 'tab studio-tab' + (studio.visible ? ' active' : '');
      tab.title = 'Design Studio';
      tab.innerHTML = '<span class="fl st-ic">&#xE790;</span><span>Design Studio</span><button class="x" title="Close"><svg viewBox="0 0 10 10"><path d="M2 2l6 6M8 2l-6 6"/></svg></button>';
      tab.onmousedown = (e) => {
        if (e.button === 1) { e.preventDefault(); closeStudio(); }
        else if (e.button === 0 && !e.target.closest('.x')) showStudio();
      };
      tab.querySelector('.x').onclick = (e) => { e.stopPropagation(); closeStudio(); };
      el.appendChild(tab);
    }
    for (const t of state.tabs) {
      const tab = document.createElement('div');
      tab.className = 'tab' + (t.path === state.active && !studio.visible ? ' active' : '') + (isDirty(t) ? ' dirty' : '');
      tab.title = t.path;
      tab.innerHTML = `${fileIcon(basename(t.path))}<span>${esc(basename(t.path))}</span><button class="x" title="Close (Ctrl+F4)"><svg viewBox="0 0 10 10"><path d="M2 2l6 6M8 2l-6 6"/></svg></button>`;
      tab.onmousedown = (e) => {
        if (e.button === 1) { e.preventDefault(); closeTab(t); }
        else if (e.button === 0 && !e.target.closest('.x')) activate(t);
      };
      tab.querySelector('.x').onclick = (e) => { e.stopPropagation(); closeTab(t); };
      tab.oncontextmenu = (e) => {
        e.preventDefault();
        showMenu(e.clientX, e.clientY, [
          { label: 'Close', sc: 'Ctrl+F4', run: () => closeTab(t) },
          { label: 'Close Other Tabs', run: () => state.tabs.filter((x) => x !== t).forEach((x) => closeTab(x)) },
          { label: 'Close All Tabs', run: () => [...state.tabs].forEach((x) => closeTab(x)) },
          'sep',
          { label: 'Copy Path', run: () => navigator.clipboard.writeText(t.path) },
          { label: 'Reveal in Explorer', run: () => api.fs.reveal(t.path) },
        ]);
      };
      el.appendChild(tab);
    }
    el.querySelector('.tab.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  function cycleTab(dir) {
    if (state.tabs.length < 2) return;
    const i = state.tabs.findIndex((t) => t.path === state.active);
    activate(state.tabs[(i + dir + state.tabs.length) % state.tabs.length]);
  }

  function crumbs(p) {
    const parts = [basename(state.root), ...rel(p).split(/[\\/]/).filter(Boolean)];
    return parts.map((x) => `<span>${esc(x)}</span>`).join('<span class="sep">›</span>');
  }

  function updateChrome() {
    const t = activeTab();
    updateProblems();
    $('#empty-state').classList.toggle('hidden', !!t || studio.visible);
    $('#breadcrumbs').innerHTML = t ? crumbs(t.path) : '';
    $('#sb-path').innerHTML = t ? crumbs(t.path) : state.root ? `<span>${esc(basename(state.root))}</span>` : '';
    $('#sb-lang').textContent = t ? LANG_NAMES[langFor(t.path)] : 'Tuff';
    $('#sb-eol').textContent = t && t.model.getEOL() === '\n' ? 'LF' : 'CRLF';
    const runFile = t && ext(t.path) === 'tuf' ? t.path : state.lastRunFile;
    $('#runconfig-name').textContent = runFile ? basename(runFile) : 'Current File';
    document.title = t ? `${basename(state.root)} – ${basename(t.path)} – TuffCode` : `${basename(state.root || '')} – TuffCode`;
  }

  // ---------- live checking ----------
  // Tuff checks .tuf files a moment after you stop typing and marks the first mistake.
  const live = { timers: new Map(), problems: new Map() };
  const closedTabs = [];

  function scheduleCheck(t) {
    if (state.settings.liveCheck === false || ext(t.path) !== 'tuf') return;
    clearTimeout(live.timers.get(t.path));
    live.timers.set(t.path, setTimeout(() => runCheck(t), 650));
  }

  async function runCheck(t) {
    if (!state.tabs.includes(t) || t.model.isDisposed()) return;
    const version = t.model.getVersionId();
    const r = await api.checkSource(t.model.getValue());
    if (!state.tabs.includes(t) || t.model.isDisposed() || t.model.getVersionId() !== version) return;
    const monaco = window.monaco;
    if (r.ok || r.unknown || !r.line) {
      live.problems.delete(t.path);
      monaco.editor.setModelMarkers(t.model, 'tuff-live', []);
    } else {
      const line = Math.min(r.line, t.model.getLineCount());
      const max = t.model.getLineMaxColumn(line);
      const col = Math.max(1, Math.min(r.col || 1, max));
      const word = t.model.getWordAtPosition({ lineNumber: line, column: col });
      const message = r.text || r.message;
      live.problems.set(t.path, { line, col, message });
      monaco.editor.setModelMarkers(t.model, 'tuff-live', [{
        severity: monaco.MarkerSeverity.Error, message, source: 'Tuff',
        startLineNumber: line, startColumn: word ? word.startColumn : Math.max(1, col - 1),
        endLineNumber: line, endColumn: word ? word.endColumn : Math.min(max, col + 1),
      }]);
    }
    updateProblems();
  }

  function updateProblems() {
    const el = $('#sb-problems');
    const t = activeTab();
    if (!t || studio.visible || ext(t.path) !== 'tuf' || state.settings.liveCheck === false) { el.className = 'hidden'; return; }
    const p = live.problems.get(t.path);
    el.className = p ? 'bad' : 'ok';
    el.textContent = p ? `Line ${p.line}: ${p.message}` : 'No mistakes';
    el.title = p ? 'Jump to the mistake' : 'Tuff checks your code as you type';
  }

  function setLiveCheck(on) {
    saveSettings({ liveCheck: on });
    for (const t of state.tabs) {
      if (on) scheduleCheck(t);
      else { window.monaco?.editor.setModelMarkers(t.model, 'tuff-live', []); live.problems.delete(t.path); }
    }
    updateProblems();
  }

  async function reopenClosedTab() {
    while (closedTabs.length) {
      const p = closedTabs.pop();
      if (state.tabs.some((t) => t.path === p)) continue;
      if (await api.fs.exists(p)) { await openFile(p); return; }
    }
    toast('No closed tabs to reopen.');
  }

  function toggleZen() {
    const on = $('#app').classList.toggle('zen');
    if (on) toast('Zen mode. Ctrl+Alt+Z brings everything back.', 'info', 3000);
    editor?.layout();
  }

  // ---------- find in files ----------
  const find = { case: false, word: false, re: false, timer: 0, seq: 0, results: [], total: 0 };

  function findPattern() {
    const q = $('#ff-q').value;
    if (!q) return null;
    let source = find.re ? q : q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (find.word) source = `\\b(?:${source})\\b`;
    try { new RegExp(source); } catch { return { error: true }; }
    return { source, flags: find.case ? 'g' : 'gi' };
  }

  function openFind() {
    showSideView('find', true);
    const sel = editor && activeTab() ? editor.getModel().getValueInRange(editor.getSelection()) : '';
    if (sel && !sel.includes('\n')) $('#ff-q').value = sel;
    $('#ff-q').focus();
    $('#ff-q').select();
    runFind();
  }

  async function runFind() {
    const p = findPattern();
    const sum = $('#ff-sum');
    if (!p) { find.results = []; renderFind(); sum.textContent = ''; return; }
    if (p.error) { sum.textContent = "That pattern isn't a valid regular expression."; return; }
    const seq = ++find.seq;
    sum.textContent = 'Searching…';
    let r;
    try { r = await api.fs.search(state.root, p.source, p.flags); } catch (err) { sum.textContent = cleanErr(err); return; }
    if (seq !== find.seq) return;
    // Open tabs may have changes that aren't saved yet, so search what's in the editor for those.
    const re = new RegExp(p.source, p.flags);
    for (const t of state.tabs) {
      const matches = [];
      t.model.getLinesContent().forEach((line, i) => {
        re.lastIndex = 0;
        let m;
        while ((m = re.exec(line))) { if (!m[0]) { re.lastIndex++; continue; } matches.push({ line: i + 1, col: m.index + 1, len: m[0].length, preview: line.slice(0, 300) }); }
      });
      r.results = r.results.filter((g) => g.path !== t.path);
      if (matches.length && isUnder(t.path, state.root)) r.results.push({ path: t.path, rel: rel(t.path), matches });
    }
    r.results.sort((a, b) => a.rel.localeCompare(b.rel));
    find.results = r.results;
    find.total = r.results.reduce((n, g) => n + g.matches.length, 0);
    sum.textContent = find.total ? `${find.total} match${find.total === 1 ? '' : 'es'} in ${r.results.length} file${r.results.length === 1 ? '' : 's'}${r.truncated ? ' (showing the first 2000)' : ''}` : 'No matches.';
    renderFind();
  }

  function renderFind() {
    const box = $('#ff-results');
    box.innerHTML = '';
    for (const g of find.results) {
      const head = document.createElement('div');
      head.className = 'ff-file';
      head.innerHTML = `${fileIcon(basename(g.path), false)}<span class="nm">${esc(basename(g.path))}</span><span class="dir">${esc(dirname(g.rel))}</span><span class="n">${g.matches.length}</span>`;
      head.onclick = () => openFile(g.path);
      box.appendChild(head);
      for (const m of g.matches.slice(0, 200)) {
        const row = document.createElement('div');
        row.className = 'ff-hit';
        const start = Math.max(0, m.col - 1 - 40);
        const pre = m.preview.slice(start, m.col - 1);
        row.innerHTML = `<span class="ln">${m.line}</span><span class="tx">${start ? '…' : ''}${esc(pre.trimStart())}<mark>${esc(m.preview.slice(m.col - 1, m.col - 1 + m.len))}</mark>${esc(m.preview.slice(m.col - 1 + m.len))}</span>`;
        row.onclick = async () => {
          await goToLine(g.path, m.line, m.col);
          editor.setSelection(new window.monaco.Range(m.line, m.col, m.line, m.col + m.len));
        };
        box.appendChild(row);
      }
    }
  }

  async function replaceAllInFiles() {
    const p = findPattern();
    if (!p || p.error || !find.total) return toast('Search for something first.');
    const rep = $('#ff-r').value;
    const files = find.results.length;
    const ok = await ask({ title: `Replace ${find.total} match${find.total === 1 ? '' : 'es'} in ${files} file${files === 1 ? '' : 's'} with "${rep}"?`, confirm: true, okLabel: 'Replace all' });
    if (!ok) return;
    const re = new RegExp(p.source, p.flags);
    for (const g of find.results) {
      const t = state.tabs.find((x) => x.path === g.path);
      if (t) {
        const text = t.model.getValue();
        const next = text.replace(re, find.re ? rep : () => rep);
        if (next !== text) {
          t.model.pushEditOperations([], [{ range: t.model.getFullModelRange(), text: next }], () => null);
          await saveTab(t);
        }
      } else {
        await api.fs.replaceInFile(g.path, p.source, p.flags, rep, find.re);
      }
    }
    renderTabs();
    toast(`Replaced in ${files} file${files === 1 ? '' : 's'}. Ctrl+Z undoes it in open files.`, 'ok', 4000);
    runFind();
  }

  // ---------- run ----------
  function setRunning(on) {
    state.running = on;
    $('#btn-run').classList.toggle('running', on);
    $('#btn-run').title = on ? 'Stop (Ctrl+F2)' : 'Run (Shift+F10)';
    const s = $('#sb-run-status');
    s.classList.toggle('running', on);
    s.textContent = on ? `Running ${basename(state.lastRunFile)}` : '';
  }

  let oscBuf = '';
  let runInput = null;
  const runLines = new Map();
  const decode64 = (s) => new TextDecoder().decode(Uint8Array.from(atob(s), (c) => c.charCodeAt(0)));

  function appendNode(node) {
    const out = $('#run-output');
    const stick = out.scrollTop + out.clientHeight >= out.scrollHeight - 8;
    out.insertBefore(node, runInput);
    if (stick) out.scrollTop = out.scrollHeight;
    return node;
  }

  function appendOut(text, cls) {
    const span = document.createElement('span');
    if (cls) span.className = cls;
    span.textContent = text;
    return appendNode(span);
  }

  function handleOsc(kind, args) {
    if (kind === 'say') {
      const span = appendOut(decode64(args[1] || ''), 'tline');
      runLines.set(args[0], span);
    } else if (kind === 'rewrite') {
      const span = runLines.get(args[0]);
      if (!span) return;
      span.textContent = decode64(args[1] || '');
      const now = performance.now();
      const rapid = now - (span.lastRewrite || 0) < 400;
      span.lastRewrite = now;
      span.classList.remove('flash');
      if (!rapid) {
        void span.offsetWidth;
        span.classList.add('flash');
      }
    } else if (kind === 'error') {
      markError(state.lastRunFile, +args[0], +args[1], decode64(args[2] || ''));
    } else if (kind === 'clear') {
      clearOutput(args[0] === 'all' ? Infinity : +args[0]);
    }
  }

  function clearOutput(count) {
    const out = $('#run-output');
    const nodes = [...out.childNodes].filter((n) => n !== runInput);
    const text = nodes.map((n) => n.textContent).join('');
    let keep = 0;
    if (count !== Infinity) {
      let idx = text.length;
      let target = text.endsWith('\n') ? count + 1 : count;
      while (target > 0) {
        idx = idx > 0 ? text.lastIndexOf('\n', idx - 1) : -1;
        if (idx === -1) break;
        target -= 1;
      }
      keep = idx === -1 ? 0 : idx + 1;
    }
    let pos = 0;
    for (const n of nodes) {
      const len = n.textContent.length;
      if (pos + len <= keep) { pos += len; continue; }
      if (pos < keep) n.textContent = n.textContent.slice(0, keep - pos);
      else n.remove();
      pos += len;
    }
  }

  function handleStdout(chunk) {
    const data = oscBuf + chunk;
    oscBuf = '';
    const re = /\x1b\]tuff;(\w+);([^\x07]*)\x07/g;
    let last = 0;
    let m;
    while ((m = re.exec(data))) {
      if (m.index > last) appendOut(data.slice(last, m.index));
      handleOsc(m[1], m[2].split(';'));
      last = re.lastIndex;
    }
    let rest = data.slice(last);
    const partial = rest.indexOf('\x1b');
    if (partial !== -1) {
      oscBuf = rest.slice(partial);
      rest = rest.slice(0, partial);
    }
    if (rest) appendOut(rest);
    if (runInput && rest && !rest.endsWith('\n')) runInput.focus();
  }

  function handleStderr(text) {
    const span = appendOut(text, 'err');
    const m = text.match(/Tuff error on line (\d+)/);
    if (m && state.lastRunFile) {
      const file = state.lastRunFile;
      span.classList.add('clickable');
      span.title = 'Jump to this line';
      span.onclick = () => goToLine(file, +m[1]);
    }
  }

  async function goToLine(file, line, col = 1) {
    await openFile(file);
    editor.revealLineInCenter(line);
    editor.setPosition({ lineNumber: line, column: col });
    editor.focus();
  }

  function markError(file, line, col, message) {
    const t = state.tabs.find((x) => x.path === file);
    if (!t || !line) return;
    const monaco = window.monaco;
    const word = t.model.getWordAtPosition({ lineNumber: line, column: col });
    monaco.editor.setModelMarkers(t.model, 'tuff', [{
      severity: monaco.MarkerSeverity.Error,
      message,
      startLineNumber: line,
      startColumn: word ? word.startColumn : col,
      endLineNumber: line,
      endColumn: word ? word.endColumn : t.model.getLineMaxColumn(line),
    }]);
  }

  function clearMarkers(file) {
    const t = state.tabs.find((x) => x.path === file);
    if (t) window.monaco?.editor.setModelMarkers(t.model, 'tuff', []);
  }

  function createRunInput() {
    runInput = document.createElement('input');
    runInput.id = 'run-input';
    runInput.spellcheck = false;
    runInput.autocomplete = 'off';
    runInput.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const v = runInput.value;
      runInput.value = '';
      appendOut(v + '\n', 'in');
      api.run.input(v + '\n');
    });
    $('#run-output').appendChild(runInput);
  }

  function runOutputText() {
    return [...$('#run-output').children]
      .filter((el) => el.tagName === 'SPAN' && !el.classList.contains('cmd') && !el.classList.contains('done'))
      .map((el) => el.textContent)
      .join('');
  }

  function startRun(file) {
    state.lastRunFile = file;
    state.runId += 1;
    showBottom(true);
    oscBuf = '';
    runLines.clear();
    runInput = null;
    $('#run-output').innerHTML = '';
    setBottomTab('run');
    createRunInput();
    clearMarkers(file);
    $('#run-tab-name').innerHTML = `${fileIcon(basename(file))}<span>${esc(basename(file))}</span>`;
    setRunning(true);
    updateChrome();
    api.run.start(file, state.runId);
  }

  async function runCurrent() {
    const t = activeTab();
    const file = t && ext(t.path) === 'tuf' ? t.path : state.lastRunFile;
    if (!file) return toast('Open a .tuf file to run it.');
    if (state.settings.sortOnRun) {
      const tab = state.tabs.find((x) => x.path === file);
      if (tab) await autoSort(tab, { quiet: true });
    }
    await saveAll();
    startRun(file);
  }

  // ---------- auto code sort ----------
  async function autoSort(t = activeTab(), { quiet = false } = {}) {
    if (!t || ext(t.path) !== 'tuf') {
      if (!quiet) toast('Auto code sort works on .tuf files.');
      return;
    }
    const model = t.model;
    const before = model.getValue();
    const result = window.TuffSort.sort(before);
    if (result.code === before) {
      if (!quiet) toast('Your code is already nice and tidy.', 'ok');
      return;
    }
    const [was, now] = await Promise.all([api.checkSource(before), api.checkSource(result.code)]);
    if (was.ok && !now.ok) {
      toast('Auto code sort stopped: tidying this file would break it, so nothing was changed.', 'error', 6000);
      return;
    }
    if (model.getValue() !== before) return;
    const onScreen = editor.getModel() === model;
    const pos = onScreen ? editor.getPosition() : null;
    model.pushStackElement();
    model.pushEditOperations([], [{ range: model.getFullModelRange(), text: result.code }], () => null);
    model.pushStackElement();
    if (onScreen && pos) editor.setPosition({ lineNumber: Math.min(pos.lineNumber, model.getLineCount()), column: 1 });
    const what = result.summary.length ? result.summary.join(', ') : 'tidied up';
    const text = `Auto code sort: ${what.charAt(0).toUpperCase() + what.slice(1)}.`;
    if (!was.ok && now.ok) toast(`${text} That also fixed the mistake in your code.`, 'ok', 6000);
    else if (!now.ok) toast(`${text} There's still a mistake: ${now.message.replace(/^Tuff error /, '')}`, 'error', 7000);
    else if (!quiet) toast(text, 'ok', 5000, { label: 'Undo', run: () => { editor.focus(); editor.trigger('toast', 'undo', null); } });
  }

  async function rerun() {
    if (!state.lastRunFile) return runCurrent();
    await saveAll();
    startRun(state.lastRunFile);
  }

  api.run.onData(({ id, stream, text }) => {
    if (id !== state.runId) return;
    if (stream === 'stdout') handleStdout(text);
    else if (stream === 'stderr') handleStderr(text);
    else appendOut(text, 'cmd');
  });
  api.run.onExit(({ id, code }) => {
    if (id !== state.runId) return;
    const output = runOutputText();
    runInput?.remove();
    runInput = null;
    appendOut(`\nProcess finished with exit code ${code}\n`, 'done' + (code ? ' bad' : ''));
    setRunning(false);
    window.dispatchEvent(new CustomEvent('tuff:run-finished', { detail: { file: state.lastRunFile, code, output } }));
  });
  $('#run-output').addEventListener('mouseup', () => {
    if (runInput && !getSelection().toString()) runInput.focus();
  });

  // ---------- build ----------
  const BUILD_STEPS = [
    ['python', 'Find Python'],
    ['check', 'Check your code for mistakes'],
    ['tools', 'Get the build tools ready'],
    ['pack', 'Pack your program'],
    ['build', 'Build your .exe'],
  ];
  const bd = { file: null, icon: null, windowed: true, building: false, steps: {}, last: null };
  const exeName = (n) => n.replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, ' ').trim().slice(0, 60) || 'MyTuffApp';
  const buildPrefs = () => (state.settings.builds || {})[state.root] || {};

  function setBottomTab(tab) {
    document.querySelectorAll('.bp-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.bp-actions').forEach((s) => s.classList.toggle('hidden', s.dataset.for !== tab));
    $('#run-output').classList.toggle('hidden', tab !== 'run');
    $('#build-output').classList.toggle('hidden', tab !== 'build');
    $('#run-tab-name').classList.toggle('hidden', tab !== 'run');
  }
  document.querySelectorAll('.bp-tab').forEach((b) => (b.onclick = () => setBottomTab(b.dataset.tab)));

  function buildTarget() {
    const t = activeTab();
    if (t && ext(t.path) === 'tuf') return t.path;
    return state.lastRunFile || join(state.root, 'main.tuf');
  }

  async function refreshIconPreview() {
    $('#bd-icon').src = (await api.build.iconPreview(bd.icon)) || 'assets/icon.svg';
  }

  function updateBuildDialog() {
    document.querySelectorAll('.bd-type').forEach((b) => b.classList.toggle('sel', (b.dataset.windowed === '1') === bd.windowed));
    $('#bd-dest').textContent = join(join(state.root, 'dist'), `${exeName($('#bd-name').value)}.exe`);
  }

  async function openBuildDialog(file) {
    if (bd.building) {
      showBottom(true);
      setBottomTab('build');
      return toast('A build is already running.');
    }
    hideMenus();
    await saveAll();
    bd.file = file || buildTarget();
    if (!(await api.fs.exists(bd.file))) return toast('Open a .tuf file to build it.');
    const prefs = buildPrefs();
    const t = state.tabs.find((x) => x.path === bd.file);
    const src = t ? t.model.getValue() : await api.fs.readFile(bd.file);
    bd.icon = prefs.icon && (await api.fs.exists(prefs.icon)) ? prefs.icon : null;
    bd.windowed = prefs.windowed ?? /^\s*(import|mention)\s+m?tgui\b/m.test(src);
    const titled = src.match(/m?tgui\.window\(\s*["']([^"']+)["']/);
    $('#bd-name').value = prefs.name || titled?.[1] || basename(state.root);
    $('#bd-file').innerHTML = `${fileIcon(basename(bd.file))}<span>${esc(rel(bd.file))}</span>`;
    updateBuildDialog();
    await refreshIconPreview();
    $('#build-dialog').classList.remove('hidden');
    $('#bd-name').focus();
    $('#bd-name').select();
  }

  const closeBuildDialog = () => $('#build-dialog').classList.add('hidden');

  function startBuildFromDialog() {
    const name = exeName($('#bd-name').value);
    saveSettings({ builds: { ...(state.settings.builds || {}), [state.root]: { name, icon: bd.icon, windowed: bd.windowed } } });
    closeBuildDialog();
    runBuild({ file: bd.file, name, icon: bd.icon, windowed: bd.windowed, iconSrc: $('#bd-icon').src });
  }

  async function runBuild(params) {
    if (bd.building) return;
    await saveAll();
    bd.building = true;
    bd.last = params;
    bd.steps = Object.fromEntries(BUILD_STEPS.map(([id, label]) => [id, { state: 'pending', label }]));
    $('#bo-empty').classList.add('hidden');
    $('#bo-main').classList.remove('hidden');
    $('#bo-icon').src = params.iconSrc || 'assets/icon.svg';
    $('#bo-title').textContent = `Building ${params.name}.exe`;
    $('#bo-sub').textContent = `${rel(params.file)} · ${params.windowed ? 'Window app' : 'Console app'}`;
    $('#bo-result').innerHTML = '';
    $('#bo-log').textContent = '';
    renderBuildSteps();
    showBottom(true);
    setBottomTab('build');
    $('.run-widget').classList.add('building');
    api.build.start({ file: params.file, root: state.root, name: params.name, icon: params.icon, windowed: params.windowed });
  }

  function renderBuildSteps() {
    const icons = {
      done: '<svg viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7"/></svg>',
      error: '<svg viewBox="0 0 16 16"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/></svg>',
    };
    $('#bo-steps').innerHTML = BUILD_STEPS.map(([id]) => {
      const s = bd.steps[id];
      return `<li class="${s.state}"><span class="si">${icons[s.state] || ''}</span><span><span class="sl">${esc(s.label)}</span>${s.detail ? `<span class="sd">${esc(s.detail)}</span>` : ''}</span></li>`;
    }).join('');
  }

  function finishBuild(ev) {
    bd.building = false;
    $('.run-widget').classList.remove('building');
    const r = $('#bo-result');
    if (ev.ok) {
      $('#bo-title').textContent = `${basename(ev.exe)} is ready`;
      r.innerHTML = `<div class="bo-card ok"><div class="bc-text"><b>Your app is ready!</b>
        <div class="bc-msg">${(ev.size / 1048576).toFixed(1)} MB · built in ${ev.seconds}s · ${ev.windowed ? 'window app' : 'console app'}</div><code></code></div>
        <div class="bc-actions"><button class="btn primary" data-a="open">Open app</button><button class="btn" data-a="folder">Show in folder</button></div></div>`;
      r.querySelector('code').textContent = ev.exe;
      r.querySelector('[data-a="open"]').onclick = () => api.build.openPath(ev.exe);
      r.querySelector('[data-a="folder"]').onclick = () => api.fs.reveal(ev.exe);
      toast(`Built ${basename(ev.exe)}`, 'ok');
      refreshTree();
    } else {
      $('#bo-title').textContent = 'Build failed';
      r.innerHTML = `<div class="bo-card bad"><div class="bc-text"><b>The build didn't finish</b><div class="bc-msg"></div></div>
        <div class="bc-actions"><button class="btn" data-a="retry">Try again</button></div></div>`;
      r.querySelector('.bc-msg').textContent = ev.message;
      r.querySelector('[data-a="retry"]').onclick = () => runBuild(bd.last);
    }
    window.dispatchEvent(new CustomEvent('tuff:build-finished', { detail: { ok: ev.ok, file: bd.last?.file } }));
  }

  api.build.onEvent((ev) => {
    if (ev.type === 'step') {
      bd.steps[ev.id] = { state: ev.state, label: ev.label, detail: ev.detail };
      renderBuildSteps();
    } else if (ev.type === 'log') {
      const log = $('#bo-log');
      const stick = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
      log.textContent += ev.text + '\n';
      if (stick) log.scrollTop = log.scrollHeight;
    } else if (ev.type === 'tuff-error') {
      const m = ev.text.match(/Tuff error on line (\d+): ([^\n]*)/);
      if (m && bd.last) markError(bd.last.file, +m[1], 1, m[2]);
    } else if (ev.type === 'done') {
      finishBuild(ev);
    }
  });

  $('#bd-icon-pick').onclick = async () => {
    const p = await api.build.chooseIcon(state.root);
    if (p) {
      bd.icon = p;
      refreshIconPreview();
    }
  };
  $('#bd-icon-reset').onclick = () => { bd.icon = null; refreshIconPreview(); };
  document.querySelectorAll('.bd-type').forEach((b) => (b.onclick = () => { bd.windowed = b.dataset.windowed === '1'; updateBuildDialog(); }));
  $('#bd-name').addEventListener('input', updateBuildDialog);
  $('#bd-name').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); startBuildFromDialog(); } });
  $('#build-dialog').addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); closeBuildDialog(); } });
  $('#build-dialog').addEventListener('mousedown', (e) => { if (e.target.id === 'build-dialog') closeBuildDialog(); });
  $('#bd-x').onclick = $('#bd-cancel').onclick = closeBuildDialog;
  $('#bd-go').onclick = startBuildFromDialog;
  $('#build-again').onclick = () => (bd.last ? runBuild(bd.last) : openBuildDialog());
  $('#build-cancel').onclick = () => api.build.cancel();
  $('#bo-details-toggle').onclick = (e) => {
    e.currentTarget.classList.toggle('open');
    $('#bo-log').classList.toggle('hidden');
  };

  // ---------- panels ----------
  function showBottom(on) {
    $('#bottom-panel').classList.toggle('hidden', !on);
    $('#bottom-resizer').classList.toggle('hidden', !on);
    document.querySelector('.ts-btn[data-tool="run"]').classList.toggle('active', on);
  }
  const toggleBottom = () => showBottom($('#bottom-panel').classList.contains('hidden'));

  let sideView = 'project';
  function showSideView(view, force) {
    const sb = $('#sidebar');
    const show = force ?? (sb.classList.contains('collapsed') || sideView !== view);
    sideView = view;
    sb.classList.toggle('collapsed', !show);
    sb.classList.toggle('learn', view === 'learn');
    document.querySelectorAll('#sidebar > .side-view').forEach((v) => v.classList.toggle('hidden', v.id !== `view-${view}`));
    document.querySelectorAll('.ts-btn[data-tool="project"], .ts-btn[data-tool="learn"], .ts-btn[data-tool="plugins"]').forEach((b) => {
      b.classList.toggle('active', show && b.dataset.tool === view);
    });
    if (show && view === 'project') $('#tree').focus();
    if (show && view === 'plugins') window.TuffPluginHost?.showMarket();
  }
  const toggleSidebar = (force) => showSideView('project', force);

  function makeResizer(handle, onMove, onDone) {
    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      handle.classList.add('dragging');
      document.body.style.cursor = getComputedStyle(handle).cursor;
      const move = (ev) => onMove(ev);
      const up = () => {
        handle.classList.remove('dragging');
        document.body.style.cursor = '';
        removeEventListener('mousemove', move);
        removeEventListener('mouseup', up);
        onDone();
      };
      addEventListener('mousemove', move);
      addEventListener('mouseup', up);
    });
  }
  const rootStyle = document.documentElement.style;
  makeResizer($('#sidebar-resizer'), (e) => {
    const w = Math.max(160, Math.min(600, e.clientX - $('#sidebar').getBoundingClientRect().left));
    rootStyle.setProperty('--sidebar-w', w + 'px');
  }, () => saveSettings({ sidebarW: rootStyle.getPropertyValue('--sidebar-w') }));
  makeResizer($('#bottom-resizer'), (e) => {
    const h = Math.max(90, Math.min(innerHeight - 220, $('#main').getBoundingClientRect().bottom - e.clientY));
    rootStyle.setProperty('--bottom-h', h + 'px');
  }, () => saveSettings({ bottomH: rootStyle.getPropertyValue('--bottom-h') }));

  // ---------- commands ----------
  const ed = (id) => () => { if (!editor || !activeTab()) return; editor.focus(); editor.trigger('menu', id, null); };
  const zoom = (d) => () => {
    state.fontSize = d === 0 ? 14 : Math.max(9, Math.min(32, state.fontSize + d));
    editor?.updateOptions({ fontSize: state.fontSize, lineHeight: Math.round(state.fontSize * 1.6) });
    saveSettings({ fontSize: state.fontSize });
  };

  const commands = {
    newFile: { label: 'New File…', sc: 'Ctrl+Alt+N', run: () => newEntry(false) },
    newFolder: { label: 'New Folder', run: () => newEntry(true) },
    openFolder: { label: 'Open Folder…', sc: 'Ctrl+O', run: pickFolder },
    saveAll: { label: 'Save All', sc: 'Ctrl+S', run: async () => { await saveAll(); toast('All files saved', 'ok', 1600); } },
    closeTab: { label: 'Close Tab', sc: 'Ctrl+F4', run: () => activeTab() && closeTab(activeTab()) },
    exit: { label: 'Exit', run: async () => { await saveAll(); api.win.close(); } },
    undo: { label: 'Undo', sc: 'Ctrl+Z', run: ed('undo') },
    redo: { label: 'Redo', sc: 'Ctrl+Shift+Z', run: ed('redo') },
    find: { label: 'Find…', sc: 'Ctrl+F', run: ed('actions.find') },
    replace: { label: 'Replace…', sc: 'Ctrl+R', run: ed('editor.action.startFindReplaceAction') },
    comment: { label: 'Comment with Line Comment', sc: 'Ctrl+/', run: ed('editor.action.commentLine') },
    autoSort: { label: 'Auto Code Sort', sc: 'Ctrl+Alt+L', run: () => autoSort() },
    dupLine: { label: 'Duplicate Line', sc: 'Ctrl+D', run: ed('editor.action.copyLinesDownAction') },
    deleteLine: { label: 'Delete Line', sc: 'Ctrl+Y', run: ed('editor.action.deleteLines') },
    selectAll: { label: 'Select All', sc: 'Ctrl+A', run: ed('editor.action.selectAll') },
    toggleProject: { label: 'Project Tool Window', sc: 'Alt+1', run: () => toggleSidebar() },
    toggleRun: { label: 'Run Tool Window', sc: 'Alt+4', run: toggleBottom },
    learn: { label: 'Learn Tuff', sc: 'Alt+2', run: () => showSideView('learn') },
    plugins: { label: 'Plugins', sc: 'Alt+3', run: () => showSideView('plugins') },
    studio: { label: 'Design Studio', sc: 'Ctrl+Shift+D', run: () => openStudio() },
    searchEverywhere: { label: 'Search Everywhere', sc: 'Double Shift', run: () => openSearch('all') },
    goToFile: { label: 'Go to File…', sc: 'Ctrl+Shift+N', run: () => openSearch('files') },
    findInFiles: { label: 'Find in Files…', sc: 'Ctrl+Shift+F', run: openFind },
    goToSymbol: { label: 'Go to Function or Widget…', sc: 'Ctrl+Shift+O', run: ed('editor.action.quickOutline') },
    goToDefinition: { label: 'Go to Definition', sc: 'F12', run: ed('editor.action.revealDefinition') },
    findUses: { label: 'Find All Uses', sc: 'Shift+F12', run: ed('editor.action.goToReferences') },
    renameSymbol: { label: 'Rename Everywhere…', sc: 'F2', run: ed('editor.action.rename') },
    reopenTab: { label: 'Reopen Closed Tab', sc: 'Ctrl+Shift+T', run: reopenClosedTab },
    zen: { label: 'Zen Mode', sc: 'Ctrl+Alt+Z', run: toggleZen },
    liveCheck: { label: 'Check for Mistakes as You Type (on/off)', run: () => { setLiveCheck(state.settings.liveCheck === false); toast(state.settings.liveCheck === false ? 'Live checking is off.' : 'Live checking is on.'); } },
    nextTab: { label: 'Next Tab', sc: 'Ctrl+Tab', run: () => cycleTab(1) },
    prevTab: { label: 'Previous Tab', sc: 'Ctrl+Shift+Tab', run: () => cycleTab(-1) },
    zoomIn: { label: 'Increase Font Size', sc: 'Ctrl+=', run: zoom(1) },
    zoomOut: { label: 'Decrease Font Size', sc: 'Ctrl+-', run: zoom(-1) },
    zoomReset: { label: 'Reset Font Size', sc: 'Ctrl+0', run: zoom(0) },
    settings: { label: 'Settings…', sc: 'Ctrl+Alt+S', run: openSettings },
    accent: { label: 'Change Accent Color', run: cycleAccent },
    devtools: { label: 'Toggle Developer Tools', sc: 'Ctrl+Shift+I', run: () => api.win.devtools() },
    run: { label: 'Run Current File', sc: 'Shift+F10', run: runCurrent },
    rerun: { label: 'Rerun', sc: 'Ctrl+F5', run: rerun },
    stop: { label: 'Stop', sc: 'Ctrl+F2', run: () => api.run.stop() },
    build: { label: 'Build .exe…', sc: 'Ctrl+F9', run: () => openBuildDialog() },
    replayIntro: { label: 'Replay Intro', run: playIntro },
    about: { label: 'About TuffCode', run: () => toast(`TuffCode ${state.version} — the IDE for the Tuff language. github.com/trickortree/tuff-code`, 'info', 6000) },
    checkUpdates: { label: 'Check for Updates…', run: () => { openSettings(); showSettingsPage('updates'); api.update.check(); } },
  };

  const keymap = {
    'Ctrl+Alt+S': 'settings', 'Ctrl+Alt+L': 'autoSort', 'Ctrl+S': 'saveAll', 'Ctrl+O': 'openFolder', 'Ctrl+Alt+N': 'newFile', 'Ctrl+F4': 'closeTab', 'Ctrl+W': 'closeTab',
    'Ctrl+Shift+N': 'goToFile', 'Ctrl+E': 'goToFile', 'Alt+1': 'toggleProject', 'Alt+2': 'learn', 'Alt+3': 'plugins', 'Alt+4': 'toggleRun', 'Ctrl+Shift+D': 'studio',
    'Shift+F10': 'run', 'Ctrl+Shift+F10': 'run', 'Ctrl+F5': 'rerun', 'Ctrl+F2': 'stop', 'Ctrl+F9': 'build',
    'Ctrl+Tab': 'nextTab', 'Ctrl+Shift+Tab': 'prevTab', 'Ctrl+Shift+I': 'devtools', 'F12': 'goToDefinition',
    'Ctrl+Shift+F': 'findInFiles', 'Ctrl+Shift+T': 'reopenTab', 'Ctrl+Alt+Z': 'zen',
    'Ctrl+=': 'zoomIn', 'Ctrl++': 'zoomIn', 'Ctrl+Shift++': 'zoomIn', 'Ctrl+-': 'zoomOut', 'Ctrl+0': 'zoomReset',
    'Ctrl+D': 'dupLine', 'Ctrl+Y': 'deleteLine', 'Ctrl+Shift+Z': 'redo', 'Ctrl+R': 'replace',
  };

  const menus = [
    ['File', ['newFile', 'newFolder', 'openFolder', 'sep', 'saveAll', 'closeTab', 'sep', 'settings', 'sep', 'exit']],
    ['Edit', ['undo', 'redo', 'sep', 'find', 'replace', 'findInFiles', 'sep', 'renameSymbol', 'autoSort', 'comment', 'dupLine', 'deleteLine', 'selectAll']],
    ['View', ['toggleProject', 'learn', 'plugins', 'toggleRun', 'studio', 'sep', 'zen', 'zoomIn', 'zoomOut', 'zoomReset', 'sep', 'settings', 'devtools']],
    ['Go', ['searchEverywhere', 'goToFile', 'goToSymbol', 'sep', 'goToDefinition', 'findUses', 'sep', 'reopenTab', 'nextTab', 'prevTab']],
    ['Run', ['run', 'rerun', 'stop', 'sep', 'build', 'sep', 'liveCheck']],
    ['Help', ['learn', 'replayIntro', 'sep', 'checkUpdates', 'about']],
  ];

  function buildMenubar() {
    const bar = $('#menubar');
    for (const [name, ids] of menus) {
      const root = document.createElement('div');
      root.className = 'menu-root';
      const btn = document.createElement('button');
      btn.textContent = name;
      root.appendChild(btn);
      const open = () => {
        hideMenus();
        root.classList.add('open');
        const dd = document.createElement('div');
        dd.className = 'dropdown';
        for (const id of ids) {
          if (id === 'sep') { dd.appendChild(document.createElement('hr')); continue; }
          const c = commands[id];
          const mi = document.createElement('button');
          mi.className = 'mi';
          mi.innerHTML = `<span>${esc(c.label)}</span>${c.sc ? `<span class="sc">${esc(c.sc)}</span>` : ''}`;
          mi.onclick = () => { hideMenus(); c.run(); };
          dd.appendChild(mi);
        }
        root.appendChild(dd);
      };
      btn.onclick = () => (root.classList.contains('open') ? hideMenus() : open());
      btn.onmouseenter = () => { if (document.querySelector('.menu-root.open') && !root.classList.contains('open')) open(); };
      bar.appendChild(root);
    }
  }

  // ---------- settings window ----------
  const tabSize = () => state.settings.tabSize || 4;

  function renderSettings() {
    const sw = $('#st-swatches');
    sw.innerHTML = '';
    for (const acc of window.TUFF_ACCENTS) {
      const b = document.createElement('button');
      b.className = 'st-sw' + (acc.id === state.accent.id ? ' sel' : '');
      b.innerHTML = `<span class="orb" style="background:linear-gradient(135deg,${acc.a},${acc.b})"></span><span>${esc(acc.name)}</span>`;
      b.onclick = () => { applyAccent(acc); saveSettings({ accent: acc.id }); renderSettings(); };
      sw.appendChild(b);
    }
    $('#st-font').value = state.fontSize;
    document.querySelectorAll('#st-tab button').forEach((b) => b.classList.toggle('sel', +b.dataset.v === tabSize()));
    $('#st-wrap').checked = !!state.settings.wordWrap;
    $('#st-minimap').checked = !!state.settings.minimap;
    $('#up-auto-check').checked = state.settings.autoCheckUpdates !== false;
    $('#up-auto').checked = state.settings.autoUpdate !== false;
    $('#up-hours').value = String([1, 2, 4, 8].includes(Number(state.settings.updateHours)) ? state.settings.updateHours : 2);
    $('#st-sort-run').checked = !!state.settings.sortOnRun;
    $('#st-live').checked = state.settings.liveCheck !== false;
  }

  function openSettings() {
    hideMenus();
    renderSettings();
    $('#settings').classList.remove('hidden');
    document.querySelector('.st-box').focus();
  }
  function closeSettings() {
    $('#settings').classList.add('hidden');
    editor?.focus();
  }
  function showSettingsPage(page) {
    document.querySelectorAll('.st-nav button').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
    document.querySelectorAll('.st-page').forEach((s) => s.classList.toggle('hidden', s.dataset.page !== page));
  }

  document.querySelectorAll('.st-nav button').forEach((b) => (b.onclick = () => showSettingsPage(b.dataset.page)));
  $('#st-x').onclick = $('#st-done').onclick = closeSettings;
  $('#settings').addEventListener('mousedown', (e) => { if (e.target.id === 'settings') closeSettings(); });
  $('#settings').addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); closeSettings(); } });
  $('#st-replay').onclick = () => { closeSettings(); playIntro(); };
  $('#st-font').addEventListener('change', (e) => {
    const v = Math.round(+e.target.value);
    if (v >= 9 && v <= 32 && v !== state.fontSize) zoom(v - state.fontSize)();
    e.target.value = state.fontSize;
  });
  document.querySelectorAll('#st-tab button').forEach((b) => (b.onclick = () => {
    const v = +b.dataset.v;
    saveSettings({ tabSize: v });
    for (const t of state.tabs) t.model.updateOptions({ tabSize: v, insertSpaces: true });
    $('#sb-indent').textContent = `${v} spaces`;
    renderSettings();
  }));
  $('#st-wrap').onchange = (e) => {
    saveSettings({ wordWrap: e.target.checked });
    editor?.updateOptions({ wordWrap: e.target.checked ? 'on' : 'off' });
  };
  $('#st-minimap').onchange = (e) => {
    saveSettings({ minimap: e.target.checked });
    editor?.updateOptions({ minimap: { enabled: e.target.checked } });
  };

  // ---------- updates ----------
  const upd = { state: null, toldReady: false, toldAvailable: false };

  function updateText(s) {
    if (!s) return 'Not checked yet.';
    switch (s.status) {
      case 'checking': return 'Checking for updates…';
      case 'up-to-date': return 'You have the latest version.';
      case 'available': return `Version ${s.latest.version} is available.`;
      case 'downloading': return `Downloading version ${s.latest?.version}…${s.detail ? ` ${s.detail}` : ''}`;
      case 'installing': return s.detail || 'Installing the update…';
      case 'ready': return `Version ${s.ready} is installed. Restart TuffCode to use it.`;
      case 'error': return `Couldn't update: ${s.error}`;
      default: return 'Not checked yet.';
    }
  }

  async function updateAction() {
    const s = upd.state;
    if (s?.status === 'ready') {
      await saveAll();
      api.update.restart();
    } else if (s?.status === 'available') {
      api.update.install();
    } else {
      api.update.check();
    }
  }

  function onUpdate(s) {
    upd.state = s;
    $('#up-status').textContent = updateText(s);
    const busy = ['checking', 'downloading', 'installing'].includes(s.status);
    const btn = $('#up-check');
    btn.disabled = busy;
    btn.textContent = s.status === 'ready' ? 'Restart now' : s.status === 'available' ? 'Install update' : 'Check for updates';
    const sb = $('#sb-update');
    const show = ['available', 'downloading', 'installing', 'ready'].includes(s.status);
    sb.classList.toggle('hidden', !show);
    sb.classList.toggle('busy', busy);
    sb.textContent = s.status === 'ready' ? '↑ Restart to update' : s.status === 'available' ? `↑ Update to ${s.latest.version}` : 'Updating…';
    sb.title = updateText(s);
    if (s.status === 'ready' && !upd.toldReady) {
      upd.toldReady = true;
      toast(`TuffCode ${s.ready} is ready. Restart to finish updating.`, 'ok', 10000, { label: 'Restart', run: updateAction });
    }
    if (s.status === 'available' && !upd.toldAvailable) {
      upd.toldAvailable = true;
      toast(`TuffCode ${s.latest.version} is available.`, 'info', 10000, { label: 'Update', run: updateAction });
    }
  }

  api.update.onStatus(onUpdate);
  $('#up-check').onclick = updateAction;
  $('#sb-update').onclick = updateAction;
  $('#up-repo').onclick = () => api.openRepo('https://github.com/trickortree/tuff-code');
  $('#up-auto-check').onchange = (e) => saveSettings({ autoCheckUpdates: e.target.checked });
  $('#up-auto').onchange = (e) => saveSettings({ autoUpdate: e.target.checked });
  $('#up-hours').onchange = async (e) => {
    await saveSettings({ updateHours: Number(e.target.value) });
    api.update.reschedule();
  };
  $('#st-sort-run').onchange = (e) => saveSettings({ sortOnRun: e.target.checked });
  $('#st-live').onchange = (e) => setLiveCheck(e.target.checked);

  function cycleAccent() {
    const list = window.TUFF_ACCENTS;
    const next = list[(list.indexOf(state.accent) + 1) % list.length];
    applyAccent(next);
    saveSettings({ accent: next.id });
    toast(`Accent: ${next.name}`, 'info', 1400);
  }

  // ---------- search everywhere ----------
  let filesCache = null;
  const se = { mode: 'all', items: [], sel: 0 };

  function fuzzy(q, text) {
    const t = text.toLowerCase();
    let qi = 0, score = 0, last = -2;
    const idx = [];
    for (let i = 0; i < t.length && qi < q.length; i++) {
      if (t[i] === q[qi]) {
        idx.push(i);
        score += (i === last + 1 ? 6 : 1) + (i === 0 || /[\W_]/.test(t[i - 1]) ? 4 : 0);
        last = i;
        qi++;
      }
    }
    if (qi < q.length) return null;
    if (t.startsWith(q)) score += 12;
    return { score: score - t.length * 0.05, idx };
  }
  const hl = (text, idx) => [...text].map((c, i) => (idx && idx.includes(i) ? `<mark>${esc(c)}</mark>` : esc(c))).join('');

  async function openSearch(mode) {
    hideMenus();
    se.mode = mode;
    $('#search-everywhere').classList.remove('hidden');
    const input = $('#se-input');
    input.value = '';
    input.focus();
    renderSE();
    if (!filesCache && state.root) {
      filesCache = await api.fs.listAll(state.root);
      renderSE();
    }
  }
  const closeSearch = () => $('#search-everywhere').classList.add('hidden');

  function renderSE() {
    document.querySelectorAll('.se-tabs span').forEach((s, i) => s.classList.toggle('active', ['all', 'files', 'actions'][i] === se.mode));
    let q = $('#se-input').value.trim().toLowerCase();
    let mode = se.mode;
    if (q.startsWith('/')) { mode = 'actions'; q = q.slice(1); }
    const items = [];
    if (mode !== 'actions') {
      const files = filesCache || [];
      if (!q) {
        const recent = [...state.tabs].reverse().map((t) => ({ name: basename(t.path), path: t.path, rel: rel(t.path) }));
        const rest = files.filter((f) => !state.tabs.some((t) => t.path === f.path));
        for (const f of [...recent, ...rest].slice(0, 30)) items.push({ kind: 'file', f, nameHtml: esc(f.name) });
      } else {
        const scored = [];
        for (const f of files) {
          const m = fuzzy(q, f.name);
          const mr = m ? null : fuzzy(q, f.rel);
          if (m) scored.push({ f, s: m.score + 20, nameHtml: hl(f.name, m.idx) });
          else if (mr) scored.push({ f, s: mr.score, nameHtml: esc(f.name) });
        }
        scored.sort((a, b) => b.s - a.s);
        for (const x of scored.slice(0, 40)) items.push({ kind: 'file', f: x.f, nameHtml: x.nameHtml });
      }
    }
    if (mode !== 'files') {
      const acts = [];
      for (const [id, c] of Object.entries(commands)) {
        if (!q) { if (mode === 'actions') acts.push({ c, s: 0, html: esc(c.label) }); continue; }
        const m = fuzzy(q, c.label);
        if (m) acts.push({ c, s: m.score, html: hl(c.label, m.idx), id });
      }
      acts.sort((a, b) => b.s - a.s);
      for (const a of acts.slice(0, 20)) items.push({ kind: 'action', c: a.c, html: a.html });
    }
    se.items = items;
    se.sel = 0;
    const ul = $('#se-results');
    ul.innerHTML = '';
    if (!items.length) {
      ul.innerHTML = `<li class="empty">${filesCache || mode === 'actions' ? 'Nothing found' : 'Indexing…'}</li>`;
      return;
    }
    items.forEach((it, i) => {
      const li = document.createElement('li');
      if (it.kind === 'file') {
        li.innerHTML = `${fileIcon(it.f.name)}<span>${it.nameHtml}</span><span class="sub">${esc(dirname(it.f.rel) || basename(state.root))}</span>`;
      } else {
        li.innerHTML = `<svg class="fi" viewBox="0 0 16 16"><path d="M3 8h10M9 4l4 4-4 4"/></svg><span>${it.html}</span><span class="sub">${esc(it.c.sc || '')}</span>`;
      }
      li.onmousemove = () => setSel(i);
      li.onclick = () => pickSE(i);
      ul.appendChild(li);
    });
    setSel(0);
  }

  function setSel(i) {
    se.sel = i;
    document.querySelectorAll('#se-results li').forEach((li, j) => li.classList.toggle('sel', i === j));
    document.querySelectorAll('#se-results li')[i]?.scrollIntoView({ block: 'nearest' });
  }

  function pickSE(i) {
    const it = se.items[i];
    if (!it) return;
    closeSearch();
    if (it.kind === 'file') openFile(it.f.path);
    else it.c.run();
  }

  $('#se-input').addEventListener('input', renderSE);
  $('#se-input').addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel(Math.min(se.sel + 1, se.items.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(Math.max(se.sel - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); pickSE(se.sel); }
    else if (e.key === 'Escape') { e.preventDefault(); closeSearch(); editor?.focus(); }
    else if (e.key === 'Tab') {
      e.preventDefault();
      const modes = ['all', 'files', 'actions'];
      se.mode = modes[(modes.indexOf(se.mode) + (e.shiftKey ? 2 : 1)) % 3];
      renderSE();
    }
  });
  document.querySelectorAll('.se-tabs span').forEach((s, i) => (s.onclick = () => { se.mode = ['all', 'files', 'actions'][i]; renderSE(); $('#se-input').focus(); }));
  $('#search-everywhere').addEventListener('mousedown', (e) => { if (e.target.id === 'search-everywhere') closeSearch(); });

  // ---------- keyboard ----------
  const overlayOpen = () => !$('#modal').classList.contains('hidden') || !$('#settings').classList.contains('hidden') || !$('#build-dialog').classList.contains('hidden') || !$('#search-everywhere').classList.contains('hidden') || !$('#intro').classList.contains('hidden');
  let shiftClean = false;
  let lastShift = 0;

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Shift') { if (!e.repeat) shiftClean = true; return; }
    shiftClean = false;
    if (e.key === 'Escape') hideMenus();
    if (overlayOpen()) return;
    if (studio.visible && window.TuffStudio?.onKey(e)) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    const key = e.key.length === 1 ? e.key.toUpperCase() : e.key;
    const combo = [(e.ctrlKey || e.metaKey) && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', key].filter(Boolean).join('+');
    const id = keymap[combo];
    if (id) {
      e.preventDefault();
      e.stopPropagation();
      commands[id].run();
    }
  }, true);

  document.addEventListener('keyup', (e) => {
    if (e.key !== 'Shift' || !shiftClean || overlayOpen()) return;
    const now = performance.now();
    if (now - lastShift < 400) { lastShift = 0; openSearch('all'); }
    else lastShift = now;
  });
  document.addEventListener('mousedown', () => { shiftClean = false; }, true);

  // ---------- chrome wiring ----------
  $('#win-min').onclick = () => api.win.minimize();
  $('#win-max').onclick = () => api.win.toggleMaximize();
  $('#win-close').onclick = commands.exit.run;
  $('#titlebar .tb-drag').ondblclick = () => api.win.toggleMaximize();
  const setMaxIcon = (max) => {
    $('#win-max').innerHTML = `<span class="fl">${max ? '&#xE923;' : '&#xE922;'}</span>`;
    $('#win-max').title = max ? 'Restore Down' : 'Maximize';
  };
  api.win.onMaximized(setMaxIcon);
  api.win.onBlur(() => saveAll());

  $('#btn-run').onclick = () => (state.running ? api.run.stop() : runCurrent());
  $('#run-rerun').onclick = rerun;
  $('#run-stop2').onclick = () => api.run.stop();
  $('#run-clear').onclick = () => {
    $('#run-output').innerHTML = '';
    if (runInput) $('#run-output').appendChild(runInput);
  };
  $('#bottom-hide').onclick = () => showBottom(false);
  $('#sidebar-hide').onclick = () => toggleSidebar(false);
  $('#btn-search').onclick = () => openSearch('all');
  $('#btn-settings').onclick = openSettings;
  $('#tree-new-file').onclick = () => newEntry(false);
  $('#tree-refresh').onclick = refreshTree;
  $('#tree-collapse').onclick = () => { tree.expanded = new Set([state.root]); renderTree(); };
  document.querySelectorAll('.ts-btn').forEach((b) => {
    b.onclick = () => ({ project: () => toggleSidebar(), learn: () => showSideView('learn'), studio: () => openStudio(), plugins: () => showSideView('plugins'), run: toggleBottom })[b.dataset.tool]();
  });
  $('#learn-hide').onclick = () => showSideView('learn', false);
  $('#pl-hide').onclick = () => showSideView('plugins', false);
  $('#ff-hide').onclick = () => showSideView('find', false);
  $('#ff-q').addEventListener('input', () => { clearTimeout(find.timer); find.timer = setTimeout(runFind, 250); });
  $('#ff-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') runFind(); if (e.key === 'Escape') showSideView('find', false); });
  for (const [id, key] of [['#ff-case', 'case'], ['#ff-word', 'word'], ['#ff-re', 're']]) {
    $(id).onclick = () => { find[key] = !find[key]; $(id).classList.toggle('on', find[key]); runFind(); };
  }
  $('#ff-replace').onclick = replaceAllInFiles;
  $('#sb-problems').onclick = () => {
    const t = activeTab();
    const p = t && live.problems.get(t.path);
    if (p) goToLine(t.path, p.line, p.col);
  };

  $('#project-widget').onclick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const recent = (state.settings.recent || []).filter((p) => p !== state.root);
    showMenu(r.left, r.bottom + 4, [
      { label: 'Open Folder…', sc: 'Ctrl+O', run: pickFolder },
      { label: 'New File…', sc: 'Ctrl+Alt+N', run: () => newEntry(false) },
      ...(recent.length ? ['sep', ...recent.map((p) => ({ label: basename(p), sc: p.length > 38 ? '…' + p.slice(-36) : p, run: () => openFolder(p) }))] : []),
    ]);
  };
  $('#runconfig-widget').onclick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const t = activeTab();
    const cur = t && ext(t.path) === 'tuf' ? t.path : state.lastRunFile;
    showMenu(r.left, r.bottom + 4, [
      state.running
        ? { label: 'Stop', sc: 'Ctrl+F2', run: () => api.run.stop() }
        : { label: cur ? `Run '${basename(cur)}'` : 'Run Current File', sc: 'Shift+F10', run: runCurrent },
      { label: 'Rerun', sc: 'Ctrl+F5', run: rerun },
      'sep',
      { label: 'Build .exe…', sc: 'Ctrl+F9', run: () => openBuildDialog() },
      'sep',
      { label: 'Show Run Window', sc: 'Alt+4', run: () => showBottom(true) },
    ]);
  };

  // ---------- intro ----------
  function enterIDE() {
    document.body.classList.remove('booting', 'enter');
    void document.body.offsetWidth;
    document.body.classList.add('enter');
    setTimeout(() => document.body.classList.remove('enter'), 1400);
  }

  async function playIntro() {
    await saveAll();
    await window.TuffIntro.play({ initial: state.accent, onReveal: enterIDE });
    await saveSettings({ introSeen: true });
    editor?.focus();
  }

  window.TuffIDE = {
    root: () => state.root,
    join,
    settings: () => state.settings,
    saveSettings,
    toast,
    refreshTree,
    openFile: (p) => openFile(p),
    runFile: async (p) => { await saveAll(); startRun(p); },
    openBuild: (p) => openBuildDialog(p),
    editor: () => editor,
    getModel: async (p) => (await openFile(p, { background: true, quiet: true }))?.model,
    listFiles: () => api.fs.listAll(state.root),
    rel,
    basename,
    goToLine,
    ask,
    openStudio,
    showSideView,
    activeCode: () => activeTab()?.model.getValue() ?? '',
    selectionText: () => (editor && activeTab() ? editor.getModel().getValueInRange(editor.getSelection()) : ''),
    selectionLines: () => {
      if (!editor || !activeTab()) return null;
      const s = editor.getSelection();
      return s.isEmpty() ? null : [s.startLineNumber, s.endLineNumber];
    },
    insertText: async (text, { snippet = false } = {}) => {
      const t = activeTab();
      if (!editor || !t) { toast('Open a file first.'); return false; }
      if (studio.visible) activate(t);
      editor.focus();
      if (snippet) editor.getContribution('snippetController2').insert(text);
      else editor.executeEdits('plugin', [{ range: editor.getSelection(), text, forceMoveMarkers: true }]);
      editor.pushUndoStop();
      return true;
    },
    // Reload open files that changed on disk (an agent edited them) unless they have unsaved changes.
    reloadChanged: async () => {
      for (const t of state.tabs) {
        if (isDirty(t)) continue;
        const disk = await api.fs.readFile(t.path).catch(() => null);
        const norm = (s) => s.replace(/\r\n/g, '\n');
        if (disk === null || norm(disk) === norm(t.model.getValue())) continue;
        t.model.pushEditOperations([], [{ range: t.model.getFullModelRange(), text: disk }], () => null);
        t.saved = t.model.getAlternativeVersionId();
      }
      renderTabs();
      filesCache = null;
      await refreshTree();
    },
    addCommand: (id, def) => { commands[id] = def; if (def.sc) keymap[def.sc] = id; },
    removeCommand: (id) => { const sc = commands[id]?.sc; if (sc && keymap[sc] === id) delete keymap[sc]; delete commands[id]; },
    openExternal: (url) => api.openRepo(url),
    studioVisible: () => studio.visible,
    activeFile: () => activeTab()?.path || null,
    monacoReady: () => monacoReady,
  };

  // ---------- boot ----------
  async function boot() {
    state.settings = await api.settings.get();
    const s = state.settings;
    state.version = await api.version();
    $('#sb-brand').textContent = `TuffCode ${state.version}`;
    $('#up-version').textContent = state.version;
    api.update.state().then((u) => u.status !== 'idle' && onUpdate(u));
    state.fontSize = s.fontSize || 14;
    if (s.sidebarW) rootStyle.setProperty('--sidebar-w', s.sidebarW);
    if (s.bottomH) rootStyle.setProperty('--bottom-h', s.bottomH);
    applyAccent(accentById(s.accent));
    $('#sb-indent').textContent = `${tabSize()} spaces`;
    buildMenubar();
    api.win.isMaximized().then(setMaxIcon);

    monacoReady = loadMonaco();
    const last = s.lastFolder && (await api.fs.exists(s.lastFolder)) ? s.lastFolder : null;
    const root = last || (await api.project.default());
    const firstRun = !s.introSeen;

    window.TuffStudio.init(window.TuffIDE);
    if (firstRun) {
      const introDone = playIntro();
      await openFolder(root);
      window.TuffLearn.init(window.TuffIDE);
      showSideView('learn', true);
      await openFile(join(root, 'main.tuf'), { focus: false, quiet: true });
      await introDone;
    } else {
      window.TuffLearn.init(window.TuffIDE);
      await openFolder(root, { restore: last ? { tabs: s.openTabs, active: s.activeTab } : null });
      if (!state.tabs.length && !last) await openFile(join(root, 'main.tuf'), { quiet: true });
      enterIDE();
      editor?.focus();
    }
    window.TuffPluginHost?.init(window.TuffIDE);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
