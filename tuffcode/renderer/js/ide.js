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
    running2: false, // "Run a second player": a second copy of the program
    run2Id: 0,
    lastRunFile: null,
    fontSize: 14,
  };
  const tree = { children: new Map(), expanded: new Set(), selected: null, justOpened: null };
  let editor = null;
  let monacoReady = null;

  // ---------- Mac and Linux ----------
  // A Mac keeps its own traffic-light buttons in the title bar (see main.js).
  if (api.platform === 'darwin') document.documentElement.classList.add('mac');
  // Words that differ by system.
  const BUILD_WORD = api.platform === 'win32' ? '.exe' : 'app';
  const REVEAL = api.platform === 'darwin' ? 'Reveal in Finder' : api.platform === 'win32' ? 'Reveal in File Explorer' : 'Open Containing Folder';
  // "Build .exe" is Windows talk; elsewhere the same feature builds an app.
  if (api.platform !== 'win32') {
    const words = () => {
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walk.nextNode(); n; n = walk.nextNode()) if (n.nodeValue.includes('.exe')) n.nodeValue = n.nodeValue.replace(/\ban \.exe\b/g, 'an app').replace(/\.exe\b/g, 'app');
      for (const el of document.querySelectorAll('[title*=".exe"]')) el.title = el.title.replace(/\.exe\b/g, 'app');
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', words); else words();
  }
  // The .fl icons are glyphs from Windows' Segoe Fluent Icons font, which other systems don't have.
  // There, each one is swapped for a drawn icon of the same meaning.
  if (api.platform !== 'win32') {
    const svg = (d) => `<svg class="fl-svg" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
    const ICONS = {
      '': svg('<path d="M4 6l4 4 4-4"/>'), // chevron down
      '': svg('<circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2L13.5 13.5"/>'), // search
      '': svg('<path d="M8 2a6 6 0 100 12c1 0 1.4-.7 1.1-1.5-.4-1 .2-1.9 1.3-1.9H12a2 2 0 002-2A6 6 0 008 2z"/><circle cx="5" cy="7" r=".8"/><circle cx="7.5" cy="4.8" r=".8"/><circle cx="10.5" cy="5.6" r=".8"/>'), // palette
      '': svg('<path d="M3 8h10"/>'),
      '': svg('<rect x="3.5" y="3.5" width="9" height="9"/>'),
      '': svg('<rect x="3.5" y="5.5" width="7" height="7"/><path d="M5.5 5.5V3.5h7v7h-2"/>'),
      '': svg('<path d="M4 4l8 8M12 4l-8 8"/>'),
    };
    const swap = (root) => {
      for (const el of root.querySelectorAll ? root.querySelectorAll('.fl') : []) {
        const g = el.textContent.trim();
        if (ICONS[g]) el.innerHTML = ICONS[g];
      }
    };
    const start = () => {
      swap(document);
      new MutationObserver((list) => { for (const m of list) for (const n of m.addedNodes) if (n.nodeType === 1) { if (n.classList?.contains('fl')) swap(n.parentNode); else swap(n); } })
        .observe(document.body, { childList: true, subtree: true });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }

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
    const n = name.toLowerCase();
    switch (n.startsWith('.env') ? 'env' : n === 'makefile' ? 'makefile' : ext(name)) {
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
      case 'env': case 'ini': case 'cfg': case 'conf': case 'toml': case 'yml': case 'yaml': case 'properties': case 'editorconfig':
        return '<svg class="fi" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.3" style="stroke:#8fa1b3;stroke-width:2.4;stroke-dasharray:2.08 2.08;stroke-dashoffset:1.04;stroke-linecap:butt"/><circle cx="8" cy="8" r="2.9" style="stroke:#8fa1b3;stroke-width:2.4"/></svg>';
      case 'png': case 'jpg': case 'jpeg': case 'gif': case 'bmp': case 'ico': case 'webp': case 'svg':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5" style="stroke:#4fb39a"/><circle cx="5.5" cy="6" r="1.3" style="fill:#4fb39a;stroke:none"/><path d="M2 12.5l4-4 3 3 2-2 3.5 3.5" style="stroke:#4fb39a"/></svg>';
      case 'makefile':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="13" height="13" rx="2" style="fill:#6d8086;stroke:none"/><path d="M4.5 11V5l3.5 4 3.5-4v6" style="stroke:#fff;stroke-width:1.5"/></svg>';
      case 'gitignore': case 'gitattributes': case 'gitmodules':
        return '<svg class="fi" viewBox="0 0 16 16"><circle cx="5" cy="3.8" r="1.6" style="stroke:#f0643c"/><circle cx="5" cy="12.2" r="1.6" style="stroke:#f0643c"/><circle cx="11" cy="6" r="1.6" style="stroke:#f0643c"/><path d="M5 5.4v5.2M11 7.6c0 2.2-2.6 2.6-4.6 3.6" style="stroke:#f0643c"/></svg>';
      case 'sh': case 'bat': case 'cmd':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="2.5" width="13" height="11" rx="2" style="stroke:#7fb36a"/><path d="M4.5 6.5l2 1.5-2 1.5M8 10h3.5" style="stroke:#7fb36a"/></svg>';
      case 'ps1':
        return '<svg class="fi" viewBox="0 0 16 16"><rect x="1.5" y="2.5" width="13" height="11" rx="2" style="fill:#2c5a9e;stroke:none"/><path d="M4.5 6.5l2 1.5-2 1.5M8 10h3.5" style="stroke:#fff"/></svg>';
      case 'html': case 'htm': case 'xml':
        return '<svg class="fi" viewBox="0 0 16 16"><path d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5M9 3l-2 10" style="stroke:#e8774c"/></svg>';
      case 'css':
        return '<svg class="fi" viewBox="0 0 16 16"><path d="M6.5 2.5l-1.5 11M11 2.5l-1.5 11M3 6h10.5M2.5 10h10.5" style="stroke:#57a6e8"/></svg>';
      case 'txt': case 'log':
        return '<svg class="fi" viewBox="0 0 16 16"><path d="M4 1.5h5l3.5 3.5v9a.5.5 0 01-.5.5H4a.5.5 0 01-.5-.5V2a.5.5 0 01.5-.5z" style="stroke:#9da0a8"/><path d="M9 1.5V5h3.5M5.5 8h5M5.5 10.5h5" style="stroke:#9da0a8"/></svg>';
      default:
        return '<svg class="fi" viewBox="0 0 16 16"><path d="M4 1.5h5l3.5 3.5v9a.5.5 0 01-.5.5H4a.5.5 0 01-.5-.5V2a.5.5 0 01.5-.5z" style="stroke:#9da0a8"/><path d="M9 1.5V5h3.5" style="stroke:#9da0a8"/></svg>';
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
          scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10, useShadows: false },
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
    r.className = 'tree-row' + (isRoot ? ' root' : '') + (tree.selected === e.path ? ' selected' : '') + (tree.fresh?.has(e.path) ? ' fresh' : '');
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
    const known = new Set([...tree.children.values()].flat().map((e) => e.path));
    for (const dir of [...tree.expanded]) await loadChildren(dir);
    filesCache = null;
    // Files that just appeared get a short highlight so you can see where they went.
    tree.fresh = new Set([...tree.children.values()].flat().map((e) => e.path).filter((p) => known.size && !known.has(p)));
    renderTree();
    tree.fresh = null;
  }

  // ---------- files changed outside TuffCode ----------
  // main.js watches the open folder, so files an agent (or Explorer/Finder, or anything else) makes,
  // changes or deletes show up straight away, and open tabs follow along unless you've edited them.
  const norm = (s) => s.replace(/\r\n/g, '\n');
  async function reloadFromDisk(tabs) {
    for (const t of [...tabs]) { // a copy: closing a tab meanwhile changes state.tabs
      if (t.model.isDisposed() || isDirty(t)) continue;
      const disk = await api.fs.readFile(t.path).catch(() => null);
      // Check again: the tab may have been closed or typed in while the file was being read.
      if (!state.tabs.includes(t) || t.model.isDisposed() || isDirty(t)) continue;
      if (disk === null || norm(disk) === norm(t.model.getValue())) continue;
      t.model.pushStackElement(); // the reload is its own undo step
      t.model.pushEditOperations([], [{ range: t.model.getFullModelRange(), text: disk }], () => null);
      t.model.pushStackElement();
      t.saved = t.model.getAlternativeVersionId();
    }
    state.tabs.forEach(syncDirty);
  }
  let diskTimer = null;
  let diskAll = false;
  const diskChanged = new Set();
  api.fs.onChanged?.(({ root, paths, overflow, gone }) => {
    if (root !== state.root) return;
    if (gone) toast(`The folder ${basename(root)} was moved or deleted. Open it again from File > Open Folder.`, 'error', 10000);
    for (const p of paths) diskChanged.add(p.toLowerCase());
    if (overflow) diskAll = true;
    clearTimeout(diskTimer);
    diskTimer = setTimeout(async () => {
      const changed = [...diskChanged];
      const all = diskAll;
      diskChanged.clear();
      diskAll = false;
      await refreshTree();
      // A changed folder counts for the files inside it (some systems only report the folder).
      const hit = (p) => changed.some((c) => p === c || p.startsWith(c + SEP));
      await reloadFromDisk(all ? state.tabs : state.tabs.filter((t) => hit(t.path.toLowerCase())));
    }, 120);
  });

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
    items.push({ label: REVEAL, run: () => api.fs.reveal(p) });
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
    api.fs.watch?.(dir);
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
  // Updates just the unsaved dot, so typing and saving don't rebuild (and re-animate) the tab bar.
  const syncDirty = (t) => t.el?.classList.toggle('dirty', isDirty(t));

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
        syncDirty(tab);
        autosave();
        window.monaco.editor.setModelMarkers(model, 'tuff', []);
        clearTimeout(secondTimer);
        secondTimer = setTimeout(updateSecond, 300); // the file may start or stop using game:host / game:join
      });
      state.tabs.push(t);
    }
    if (background) {
      renderTabs();
      updateChrome(); // Tuff Engine's game may be the file on screen
      return t;
    }
    activate(t, focus);
    return t;
  }

  // ---------- design studio view ----------
  const studio = { open: false, visible: false, file: null, el: null };

  function showStudio(file) {
    hideEngine();
    studio.open = true;
    studio.visible = true;
    $('#app').classList.add('studio-on');
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
    $('#app').classList.remove('studio-on');
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

  // ---------- tuff engine view ----------
  // The second centre pseudo-tab, built like the Studio's: Tuff Engine (tuff-engine.js) edits a tgame game.
  const engine = { open: false, visible: false, file: null, el: null };
  const PAD_ICON = '<svg viewBox="0 0 20 20"><path d="M6 6.5h8a4 4 0 014 4v.6a2.9 2.9 0 01-5.1 1.9L11.6 12H8.4l-1.3 1A2.9 2.9 0 012 11.1v-.6a4 4 0 014-4z"/><path d="M6.2 8.6v3M4.7 10.1h3"/><circle cx="13" cy="9.4" r=".7"/><circle cx="14.6" cy="11" r=".7"/></svg>';

  function showEngine(file) {
    hideStudio();
    engine.open = true;
    engine.visible = true;
    $('#app').classList.add('engine-on');
    if (file) engine.file = file;
    $('#engine').classList.remove('hidden');
    $('#monaco').classList.add('hidden');
    $('#breadcrumbs').classList.add('hidden');
    if (!state.running) showBottom(false);
    window.TuffStudio?.closeCustomizer();
    renderTabs();
    updateChrome();
    window.TuffEngine.show(engine.file);
  }

  function hideEngine() {
    if (!engine.visible) return;
    engine.visible = false;
    $('#app').classList.remove('engine-on');
    $('#engine').classList.add('hidden');
    $('#monaco').classList.remove('hidden');
    $('#breadcrumbs').classList.remove('hidden');
    window.TuffEngine?.hide();
  }

  function closeEngine() {
    hideEngine();
    engine.open = false;
    renderTabs();
    updateChrome();
  }

  // Which game to show: the first of these that is there (so a deleted game Tuff Engine showed last never hides the
  // tab that's open now): the file asked for, the last game it showed and the file run last (in this folder), the
  // open .tuf tab, main.tuf. Then the project's first game, or its first .tuf. A folder with no .tuf at all gets an
  // empty main.tuf, so Tuff Engine opens on its start card ("Make a 2D game here") instead of an empty tab.
  async function openEngine(file) {
    hideMenus();
    const t = activeTab();
    const here = (p) => (p && state.root && isUnder(p, state.root) ? p : null);
    const want = [file, here(engine.file), t && ext(t.path) === 'tuf' ? t.path : null, here(state.lastRunFile), state.root && join(state.root, 'main.tuf')];
    let target = null;
    for (const p of want) if (p && (await api.fs.exists(p))) { target = p; break; }
    if (!target && state.root) {
      const tufs = (await api.fs.listAll(state.root)).filter((f) => f.name.endsWith('.tuf') && !/^(dist|build)[\\/]/.test(f.rel)).sort((a, b) => a.rel.localeCompare(b.rel));
      for (const f of tufs.slice(0, 80)) {
        try { if (/^[ \t]*(?:import|mention)[ \t]+tgame\b/m.test(await api.fs.readFile(f.path))) { target = f.path; break; } } catch { /* unreadable */ }
      }
      target = target || tufs[0]?.path || null;
      if (!target) {
        target = join(state.root, 'main.tuf');
        try { await api.fs.createFile(target); } catch { /* made meanwhile */ }
        await refreshTree();
      }
    }
    if (!target) { toast('Open a folder first.'); return; }
    showEngine(target);
  }

  function activate(t, focus = true) {
    hideStudio();
    hideEngine();
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

  // Cmd+Q, the Mac's red button or logging out close the window without going through Exit, so
  // whatever the autosave hasn't written yet is written synchronously as the page goes away.
  window.addEventListener('beforeunload', () => {
    const dirty = state.tabs.filter(isDirty);
    if (dirty.length) api.fs.writeFilesSync?.(dirty.map((t) => ({ path: t.path, content: t.model.getValue() })));
  });

  async function saveTab(t) {
    const version = t.model.getAlternativeVersionId();
    t.model.pushStackElement(); // the next edit starts a new undo step, so Ctrl+Z lands on exactly what was saved
    try {
      await api.fs.writeFile(t.path, t.model.getValue());
      t.saved = version;
    } catch (err) {
      toast(`Could not save ${basename(t.path)}: ${cleanErr(err)}`, 'error');
    }
  }

  async function saveAll() {
    await Promise.all(state.tabs.filter(isDirty).map(saveTab));
    state.tabs.forEach(syncDirty);
  }
  const autosave = debounce(saveAll, 1500);

  // A tab element for renderTabs. Only a tab that wasn't there before (no previous element) gets the
  // 'enter' fade-in. It keeps 'enter' until the fade ends, so a second rebuild straight away doesn't cancel it.
  function tabEl(prev, cls) {
    const tab = document.createElement('div');
    const fresh = !prev || prev.classList.contains('enter');
    tab.className = cls + (fresh ? ' enter' : '');
    if (fresh) tab.onanimationend = (e) => e.animationName === 'tabin' && tab.classList.remove('enter');
    return tab;
  }

  // Rebuilds the tab bar (when tabs open, close, rename or switch). Typing and saving only call syncDirty.
  function renderTabs() {
    const el = $('#tabs');
    el.innerHTML = '';
    if (studio.open) {
      const tab = studio.el = tabEl(studio.el, 'tab studio-tab' + (studio.visible ? ' active' : ''));
      tab.title = 'Design Studio';
      tab.innerHTML = '<span class="fl st-ic">&#xE790;</span><span>Design Studio</span><button class="x" title="Close"><svg viewBox="0 0 10 10"><path d="M2 2l6 6M8 2l-6 6"/></svg></button>';
      tab.onmousedown = (e) => {
        if (e.button === 1) { e.preventDefault(); closeStudio(); }
        else if (e.button === 0 && !e.target.closest('.x')) showStudio();
      };
      tab.querySelector('.x').onclick = (e) => { e.stopPropagation(); closeStudio(); };
      el.appendChild(tab);
    } else studio.el = null;
    if (engine.open) {
      const tab = engine.el = tabEl(engine.el, 'tab engine-tab' + (engine.visible ? ' active' : ''));
      tab.title = 'Tuff Engine';
      tab.innerHTML = `<span class="st-ic">${PAD_ICON}</span><span>Tuff Engine</span><button class="x" title="Close"><svg viewBox="0 0 10 10"><path d="M2 2l6 6M8 2l-6 6"/></svg></button>`;
      tab.onmousedown = (e) => {
        if (e.button === 1) { e.preventDefault(); closeEngine(); }
        else if (e.button === 0 && !e.target.closest('.x')) showEngine();
      };
      tab.querySelector('.x').onclick = (e) => { e.stopPropagation(); closeEngine(); };
      el.appendChild(tab);
    } else engine.el = null;
    for (const t of state.tabs) {
      const tab = t.el = tabEl(t.el, 'tab' + (t.path === state.active && !studio.visible && !engine.visible ? ' active' : '') + (isDirty(t) ? ' dirty' : ''));
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
          { label: REVEAL, run: () => api.fs.reveal(t.path) },
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

  // While Tuff Engine shows, its game is the file on screen: the title bar's Run runs it, and the status bar and the
  // window title name it (TuffIDE.activeFile() says the same). Otherwise it's the code tab's file.
  function runTarget() {
    const t = activeTab();
    return (engine.visible && engine.file) || (t && ext(t.path) === 'tuf' ? t.path : state.lastRunFile);
  }
  function shownTab() {
    return (engine.visible && engine.file && state.tabs.find((x) => x.path === engine.file)) || activeTab();
  }

  function updateChrome() {
    const t = activeTab();
    const s = shownTab();
    updateProblems();
    $('#empty-state').classList.toggle('hidden', !!t || studio.visible || engine.visible);
    $('#breadcrumbs').innerHTML = t ? crumbs(t.path) : '';
    $('#sb-path').innerHTML = s ? crumbs(s.path) : state.root ? `<span>${esc(basename(state.root))}</span>` : '';
    $('#sb-lang').textContent = s ? LANG_NAMES[langFor(s.path)] : 'Tuff';
    $('#sb-eol').textContent = s && s.model.getEOL() === '\n' ? 'LF' : 'CRLF';
    const runFile = runTarget();
    $('#runconfig-name').textContent = runFile ? basename(runFile) : 'Current File';
    updateSecond();
    document.title = s ? `${basename(state.root)} – ${basename(s.path)} – TuffCode` : `${basename(state.root || '')} – TuffCode`;
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
    if (!t || studio.visible || engine.visible || ext(t.path) !== 'tuf' || state.settings.liveCheck === false) { el.className = 'hidden'; return; }
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
    state.tabs.forEach(syncDirty);
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

  // "Run a second player": the button beside Run plays and stops the second copy, the same way.
  function setRunning2(on) {
    state.running2 = on;
    $('#btn-run2').classList.toggle('running', on);
    $('#btn-run2').title = on ? 'Stop the second player' : SECOND_TITLE;
    updateSecond();
  }

  // Shown for a file that hosts or joins a multiplayer room, and while a second player runs (so it can be stopped).
  const SECOND_TITLE = 'Run a second player: another copy of this game, to host in one and join in the other';
  const MULTIPLAYER = /:(host|join)\s*[("]/;
  let secondTimer = null;
  function updateSecond() {
    const file = runTarget();
    const t = file && state.tabs.find((x) => x.path === file);
    $('#btn-run2').classList.toggle('hidden', !state.running2 && !(t && MULTIPLAYER.test(t.model.getValue())));
  }

  let runInput = null;
  const decode64 = (s) => new TextDecoder().decode(Uint8Array.from(atob(s), (c) => c.charCodeAt(0)));
  // The two copies of the program in the Run panel: the run (1) and the second player (2). Each has its own say
  // lines and half-read escape codes. Once a second player runs, the panel gets .two and every line a P1 or P2 chip
  // (data-who, drawn by CSS, so runOutputText() never sees it); the second player's spans are .p2.
  const copies = { 1: { who: 1, osc: '', lines: new Map() }, 2: { who: 2, osc: '', lines: new Map() } };
  const resetCopy = (c) => { c.osc = ''; c.lines.clear(); };
  const saidBy = (node, c) => !!node.classList?.contains('p2') === (c.who === 2);

  function appendNode(node) {
    const out = $('#run-output');
    const stick = out.scrollTop + out.clientHeight >= out.scrollHeight - 8;
    out.insertBefore(node, runInput);
    if (stick) out.scrollTop = out.scrollHeight;
    return node;
  }

  function appendOut(text, cls, c = copies[1]) {
    const span = document.createElement('span');
    if (cls) span.className = cls;
    if (c.who === 2) span.classList.add('p2');
    span.textContent = text;
    if (text) {
      // A line the other copy left half-written ends here, so the two never share a line.
      const prev = runInput ? runInput.previousSibling : $('#run-output').lastChild;
      let fresh = !prev || prev.nodeName === 'BR' || prev.textContent.endsWith('\n');
      if (!fresh && !saidBy(prev, c)) {
        appendNode(document.createElement('br'));
        fresh = true;
      }
      if (fresh && text[0] !== '\n') span.dataset.who = c.who;
    }
    return appendNode(span);
  }

  // Plain output, a span per line, so each line gets its chip.
  function appendLines(text, cls, c) {
    for (const piece of text.split(/(?<=\n)/)) appendOut(piece, cls, c);
  }

  function handleOsc(kind, args, c) {
    if (kind === 'say') {
      // say;<id>;<b64>[;<style>]: "notice" is the yellow line a tgame program starts with. The second player
      // leaves it out: the first copy has said it.
      if (c.who === 2 && args[2] === 'notice') return 'skip';
      const span = appendOut(decode64(args[1] || ''), args[2] === 'notice' ? 'tline notice' : 'tline', c);
      c.lines.set(args[0], span);
      // tgame's notice gets a button that opens the game in Tuff Engine.
      if (args[2] === 'notice' && /^Tuff Engine/.test(span.textContent)) {
        const file = state.lastRunFile;
        const b = document.createElement('button');
        b.className = 'explain-err open-engine';
        b.dataset.label = 'Open Tuff Engine'; // drawn by CSS, so runOutputText() (Learn checks) never sees it
        b.title = 'Open this game in Tuff Engine';
        b.onclick = (e) => { e.stopPropagation(); openEngine(file); };
        span.append(b);
      }
    } else if (kind === 'rewrite') {
      const span = c.lines.get(args[0]);
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
      clearOutput(args[0] === 'all' ? Infinity : +args[0], c);
    }
  }

  // A copy's clear takes away its own lines, not the other copy's.
  function clearOutput(count, c = copies[1]) {
    const out = $('#run-output');
    const nodes = [...out.childNodes].filter((n) => n !== runInput && n.nodeName !== 'BR' && saidBy(n, c));
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

  function handleStdout(chunk, c = copies[1]) {
    const data = c.osc + chunk;
    c.osc = '';
    const re = /\x1b\]tuff;(\w+);([^\x07]*)\x07/g;
    let last = 0;
    let m;
    while ((m = re.exec(data))) {
      if (m.index > last) appendLines(data.slice(last, m.index), '', c);
      const skipped = handleOsc(m[1], m[2].split(';'), c) === 'skip';
      last = re.lastIndex;
      if (skipped && data[last] === '\n') last += 1; // the end of the line it left out
    }
    let rest = data.slice(last);
    const partial = rest.indexOf('\x1b');
    if (partial !== -1) {
      c.osc = rest.slice(partial);
      rest = rest.slice(0, partial);
    }
    if (rest) appendLines(rest, '', c);
    if (c.who === 1 && runInput && rest && !rest.endsWith('\n')) runInput.focus();
  }

  function handleStderr(text, c = copies[1]) {
    const span = appendOut(text, 'err', c);
    const m = text.match(/Tuff error on line (\d+)/);
    if (m && state.lastRunFile) {
      const file = state.lastRunFile;
      span.classList.add('clickable');
      span.title = 'Jump to this line';
      span.onclick = () => goToLine(file, +m[1]);
      // Tuff Agents sets this when it's on: ask the chosen agent what the error means.
      if (window.tuffExplainError) {
        const b = document.createElement('button');
        b.className = 'explain-err';
        b.textContent = 'Explain';
        b.title = 'Ask the AI in Tuff Agents what this error means';
        b.onclick = (e) => { e.stopPropagation(); window.tuffExplainError?.(text); };
        span.append(b);
      }
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

  // What the program said (the first copy: Learn checks it).
  function runOutputText() {
    return [...$('#run-output').children]
      .filter((el) => el.tagName === 'SPAN' && !['cmd', 'done', 'p2'].some((k) => el.classList.contains(k)))
      .map((el) => el.textContent)
      .join('');
  }

  // A new run starts over with one copy: main.js ends the second player too.
  function startRun(file) {
    state.lastRunFile = file;
    state.runId += 1;
    if (state.running2) {
      state.run2Id += 1; // what it says on its way out isn't shown
      setRunning2(false);
    }
    showBottom(true);
    resetCopy(copies[1]);
    resetCopy(copies[2]);
    runInput = null;
    $('#run-output').innerHTML = '';
    $('#run-output').classList.remove('two');
    setBottomTab('run');
    createRunInput();
    clearMarkers(file);
    $('#run-tab-name').innerHTML = `${fileIcon(basename(file))}<span>${esc(basename(file))}</span>`;
    setRunning(true);
    updateChrome();
    api.run.start(file, state.runId);
  }

  async function runCurrent() {
    const file = runTarget();
    if (!file) return toast('Open a .tuf file to run it.');
    if (state.settings.sortOnRun) {
      const tab = state.tabs.find((x) => x.path === file);
      if (tab) await autoSort(tab, { quiet: true });
    }
    await saveAll();
    startRun(file);
  }

  // "Run a second player": another copy of the same game beside the first, to try a multiplayer game alone (host in
  // one window, join in the other). It runs the file on screen; if that isn't running yet, Run starts it first.
  // While the second player runs, the button stops it (and only it).
  async function runSecond() {
    if (state.running2) return api.run2.stop();
    const file = runTarget();
    if (!file) return toast('Open a .tuf file to run it.');
    if (!state.running || state.lastRunFile !== file) {
      await runCurrent();
      if (!state.running) return;
    } else {
      await saveAll();
    }
    state.run2Id += 1;
    resetCopy(copies[2]);
    showBottom(true);
    setBottomTab('run');
    $('#run-output').classList.add('two');
    setRunning2(true);
    api.run2.start(file, state.run2Id);
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
    appendOut('\n', 'done');
    appendOut(`Process finished with exit code ${code}\n`, 'done' + (code ? ' bad' : ''));
    setRunning(false);
    window.dispatchEvent(new CustomEvent('tuff:run-finished', { detail: { file: state.lastRunFile, code, output } }));
  });
  api.run2.onData(({ id, stream, text }) => {
    if (id !== state.run2Id) return;
    if (stream === 'stdout') handleStdout(text, copies[2]);
    else if (stream === 'stderr') handleStderr(text, copies[2]);
    else appendOut(text, 'cmd', copies[2]);
  });
  api.run2.onExit(({ id, code }) => {
    if (id !== state.run2Id) return;
    appendOut('\n', 'done', copies[2]);
    appendOut(`The second player finished with exit code ${code}\n`, 'done' + (code ? ' bad' : ''), copies[2]);
    setRunning2(false);
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
    ['build', api.platform === 'win32' ? 'Build your .exe' : 'Build your app'],
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
    $('#bd-icon').src = (await api.build.iconPreview(bd.icon)) || 'assets/icon.png';
  }

  function updateBuildDialog() {
    document.querySelectorAll('.bd-type').forEach((b) => b.classList.toggle('sel', (b.dataset.windowed === '1') === bd.windowed));
    const suffix = api.platform === 'win32' ? '.exe' : (api.platform === 'darwin' && bd.windowed ? '.app' : '');
    $('#bd-dest').textContent = join(join(state.root, 'dist'), `${exeName($('#bd-name').value)}${suffix}`);
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
    $('#bo-icon').src = params.iconSrc || 'assets/icon.png';
    $('#bo-title').textContent = `Building ${params.name}${api.platform === 'win32' ? '.exe' : ''}`;
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
  // The Edit menu's commands work on the code on screen. While Tuff Engine or Design Studio shows, the code editor is
  // hidden (and may hold another file): Undo and Redo are the view's own, Find and Replace open the view's file in
  // the editor first, and the line commands do nothing, so nothing changes where you can't see it.
  const ed = (id) => () => {
    const view = engine.visible ? { file: engine.file, api: window.TuffEngine } : studio.visible ? { file: studio.file, api: window.TuffStudio } : null;
    if (view) {
      if (id === 'undo' || id === 'redo') { view.api?.[id]?.(); return; }
      if ((id !== 'actions.find' && id !== 'editor.action.startFindReplaceAction') || !view.file) return;
      return openFile(view.file).then((t) => { if (t) { editor.focus(); editor.trigger('menu', id, null); } });
    }
    if (!editor || !activeTab()) return;
    editor.focus();
    editor.trigger('menu', id, null);
  };
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
    engine: { label: 'Tuff Engine', sc: 'Ctrl+Shift+G', run: () => openEngine() },
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
    build: { label: `Build ${BUILD_WORD}…`, sc: 'Ctrl+F9', run: () => openBuildDialog() },
    replayIntro: { label: 'Replay Intro', run: playIntro },
    whatsNew: { label: "What's New", run: () => window.TuffWhatsNew?.show(state.version) || toast(`There are no notes for TuffCode ${state.version}.`, 'info') },
    about: { label: 'About TuffCode', run: () => toast(`TuffCode ${state.version} — the IDE for the Tuff language. github.com/trickortree/tuff-code`, 'info', 6000) },
    checkUpdates: { label: 'Check for Updates…', run: () => { openSettings(); showSettingsPage('updates'); api.update.check(); } },
  };

  const keymap = {
    'Ctrl+Alt+S': 'settings', 'Ctrl+Alt+L': 'autoSort', 'Ctrl+S': 'saveAll', 'Ctrl+O': 'openFolder', 'Ctrl+Alt+N': 'newFile', 'Ctrl+F4': 'closeTab', 'Ctrl+W': 'closeTab',
    'Ctrl+Shift+N': 'goToFile', 'Ctrl+E': 'goToFile', 'Alt+1': 'toggleProject', 'Alt+2': 'learn', 'Alt+3': 'plugins', 'Alt+4': 'toggleRun', 'Ctrl+Shift+D': 'studio', 'Ctrl+Shift+G': 'engine',
    'Shift+F10': 'run', 'Ctrl+Shift+F10': 'run', 'Ctrl+F5': 'rerun', 'Ctrl+F2': 'stop', 'Ctrl+F9': 'build',
    'Ctrl+Tab': 'nextTab', 'Ctrl+Shift+Tab': 'prevTab', 'Ctrl+Shift+I': 'devtools', 'F12': 'goToDefinition',
    'Ctrl+Shift+F': 'findInFiles', 'Ctrl+Shift+T': 'reopenTab', 'Ctrl+Alt+Z': 'zen',
    'Ctrl+=': 'zoomIn', 'Ctrl++': 'zoomIn', 'Ctrl+Shift++': 'zoomIn', 'Ctrl+-': 'zoomOut', 'Ctrl+0': 'zoomReset',
    'Ctrl+D': 'dupLine', 'Ctrl+Y': 'deleteLine', 'Ctrl+Shift+Z': 'redo', 'Ctrl+R': 'replace',
  };

  const menus = [
    ['File', ['newFile', 'newFolder', 'openFolder', 'sep', 'saveAll', 'closeTab', 'sep', 'settings', 'sep', 'exit']],
    ['Edit', ['undo', 'redo', 'sep', 'find', 'replace', 'findInFiles', 'sep', 'renameSymbol', 'autoSort', 'comment', 'dupLine', 'deleteLine', 'selectAll']],
    ['View', ['toggleProject', 'learn', 'plugins', 'toggleRun', 'studio', 'engine', 'sep', 'zen', 'zoomIn', 'zoomOut', 'zoomReset', 'sep', 'settings', 'devtools']],
    ['Go', ['searchEverywhere', 'goToFile', 'goToSymbol', 'sep', 'goToDefinition', 'findUses', 'sep', 'reopenTab', 'nextTab', 'prevTab']],
    ['Run', ['run', 'rerun', 'stop', 'sep', 'build', 'sep', 'liveCheck']],
    ['Help', ['learn', 'replayIntro', 'whatsNew', 'sep', 'checkUpdates', 'about']],
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
      case 'available': return `Version ${s.latest.version} is available.${s.detail ? ` ${s.detail}` : ''}`;
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
    const mac = api.platform === 'darwin'; // a Mac downloads updates from the release page
    btn.textContent = s.status === 'ready' ? 'Restart now' : s.status === 'available' ? (mac ? 'Download update' : 'Install update') : 'Check for updates';
    if (s.status === 'up-to-date' && s.detail) $('#up-status').textContent = s.detail;
    const sb = $('#sb-update');
    const show = ['available', 'downloading', 'installing', 'ready'].includes(s.status);
    sb.classList.toggle('hidden', !show);
    sb.classList.toggle('busy', busy);
    sb.textContent = s.status === 'ready' ? '↑ Restart to update' : s.status === 'available' ? `↑ ${mac ? 'Download' : 'Update to'} ${s.latest.version}` : 'Updating…';
    sb.title = updateText(s);
    if (s.status === 'ready' && !upd.toldReady) {
      upd.toldReady = true;
      toast(`TuffCode ${s.ready} is ready. Restart to finish updating.`, 'ok', 10000, { label: 'Restart', run: updateAction });
    }
    if (s.status === 'available' && !upd.toldAvailable) {
      upd.toldAvailable = true;
      toast(`TuffCode ${s.latest.version} is available.`, 'info', 10000, { label: mac ? 'Download' : 'Update', run: updateAction });
    }
    if (mac && s.status === 'available' && s.detail && s.detail !== upd.toldDetail) {
      upd.toldDetail = s.detail;
      toast(s.detail, 'info', 10000);
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

  // A box you type in that isn't the code editor: Tuff Agents' message box, a plugin's field, the Run
  // window's input, a name in Design Studio. (Monaco's own text area and its find box are the editor.)
  const inTextBox = (el) => !!el?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"])') && !el.closest('.monaco-editor');
  // The shortcuts that still work while you type in one of those boxes: ones for the whole app. The others
  // work on the code (Ctrl+Y deletes a line, Ctrl+D copies one, Ctrl+Shift+Z redoes, Ctrl+R, Ctrl+Alt+L, F12)
  // and moved you into the editor, so a Ctrl+Z after them undid code too. In a box they stay the box's own.
  // Ctrl+Alt ones (Settings, New File, Zen) stay out too: on Windows Ctrl+Alt is AltGr, which types ł, ż, ś.
  const APP_WIDE = new Set(['saveAll', 'openFolder', 'closeTab', 'goToFile', 'findInFiles', 'reopenTab', 'nextTab', 'prevTab',
    'toggleProject', 'learn', 'plugins', 'toggleRun', 'studio', 'engine', 'run', 'rerun', 'stop', 'build', 'devtools', 'zoomIn', 'zoomOut', 'zoomReset']);
  function worksInTextBox(id, combo, e) {
    // On a Mac, Ctrl+letter in a text box is the box's editing (Ctrl+A, Ctrl+E, Ctrl+K, Ctrl+Y...); shortcuts are Cmd.
    if (api.platform === 'darwin' && e.ctrlKey && !e.metaKey && /^Key/.test(e.code)) return false;
    if (e.altKey && /^Numpad/.test(e.code)) return false; // Alt with the number pad types a character (Alt+0233 is é)
    if (APP_WIDE.has(id)) return true;
    // A plugin's own shortcut (Ctrl+Shift+A opens Tuff Agents) works too, unless it's a box's own key.
    return id.startsWith('plugin.') && !/^Ctrl\+Alt\+|^Ctrl\+[ACVXYZ]$|^Ctrl\+Shift\+Z$/.test(combo);
  }

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
    if (engine.visible && window.TuffEngine?.onKey(e)) { e.preventDefault(); e.stopPropagation(); return; }
    // On a Mac, Option turns keys into characters (Option+S is ß, Option+3 is # on a UK keyboard).
    // With Cmd or Ctrl held nothing gets typed, so there the physical key names the shortcut; a bare
    // Option+key is left alone so people can type those characters.
    const phys = /^Key([A-Z])$/.exec(e.code)?.[1] ?? /^Digit(\d)$/.exec(e.code)?.[1];
    const key = (api.platform === 'darwin' && e.altKey && (e.metaKey || e.ctrlKey) && phys) || (e.key.length === 1 ? e.key.toUpperCase() : e.key);
    const combo = [(e.ctrlKey || e.metaKey) && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', key].filter(Boolean).join('+');
    const id = keymap[combo];
    if (id && (!inTextBox(e.target) || worksInTextBox(id, combo, e))) {
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
  api.win.onFullScreen?.((on) => document.documentElement.classList.toggle('fullscreen', !!on));
  api.win.onBlur(() => saveAll());

  $('#btn-run').onclick = () => (state.running ? api.run.stop() : runCurrent());
  $('#btn-run2').onclick = runSecond;
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
    b.onclick = () => ({ project: () => toggleSidebar(), learn: () => showSideView('learn'), studio: () => openStudio(), engine: () => openEngine(), plugins: () => showSideView('plugins'), run: toggleBottom })[b.dataset.tool]();
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
    const cur = runTarget();
    showMenu(r.left, r.bottom + 4, [
      state.running
        ? { label: 'Stop', sc: 'Ctrl+F2', run: () => api.run.stop() }
        : { label: cur ? `Run '${basename(cur)}'` : 'Run Current File', sc: 'Shift+F10', run: runCurrent },
      { label: 'Rerun', sc: 'Ctrl+F5', run: rerun },
      ...(!$('#btn-run2').classList.contains('hidden')
        ? [{ label: state.running2 ? 'Stop the Second Player' : 'Run a Second Player', run: runSecond }] : []),
      'sep',
      { label: `Build ${BUILD_WORD}…`, sc: 'Ctrl+F9', run: () => openBuildDialog() },
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
    await saveSettings({ introSeen: true, introVersion: state.version });
    editor?.focus();
  }

  // While Tuff Engine shows, the file it edits counts as the open file (for plugins and agents).
  const engineTab = () => (engine.visible && engine.file ? state.tabs.find((x) => x.path === engine.file) || null : null);

  window.TuffIDE = {
    root: () => state.root,
    join,
    settings: () => state.settings,
    saveSettings,
    toast,
    refreshTree,
    // With a line, the cursor goes there (a link like "main.tuf:12" in an agent's reply).
    openFile: async (p, line) => {
      const tab = await openFile(p);
      if (tab && line > 0) { editor.revealLineInCenter(line); editor.setPosition({ lineNumber: line, column: 1 }); editor.focus(); }
      return tab;
    },
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
    // Full size: the Studio takes over everything but the title bar and the right sidebar.
    studioFull: () => $('#app').classList.contains('studio-full'),
    setStudioFull: (on) => {
      $('#app').classList.toggle('studio-full', on);
      saveSettings({ studioFull: on });
      editor?.layout();
    },
    activeCode: () => (engineTab() || activeTab())?.model.getValue() ?? '',
    selectionText: () => (engineTab() ? '' : editor && activeTab() ? editor.getModel().getValueInRange(editor.getSelection()) : ''),
    selectionLines: () => {
      if (engineTab() || !editor || !activeTab()) return null;
      const s = editor.getSelection();
      return s.isEmpty() ? null : [s.startLineNumber, s.endLineNumber];
    },
    insertText: async (text, { snippet = false } = {}) => {
      const t = engineTab() || activeTab();
      if (!editor || !t) { toast('Open a file first.'); return false; }
      if (studio.visible || engine.visible) activate(t);
      editor.focus();
      if (snippet) editor.getContribution('snippetController2').insert(text);
      else editor.executeEdits('plugin', [{ range: editor.getSelection(), text, forceMoveMarkers: true }]);
      editor.pushUndoStop();
      return true;
    },
    // Replaces the whole open file, as one step Ctrl+Z undoes.
    replaceAllText: async (text) => {
      const t = engineTab() || activeTab();
      if (!editor || !t) { toast('Open a file first.'); return false; }
      if (studio.visible || engine.visible) activate(t);
      editor.focus();
      editor.pushUndoStop();
      editor.executeEdits('plugin', [{ range: t.model.getFullModelRange(), text, forceMoveMarkers: true }]);
      editor.pushUndoStop();
      return true;
    },
    // Reload open files that changed on disk (an agent edited them) unless they have unsaved changes.
    reloadChanged: async () => {
      await reloadFromDisk(state.tabs);
      await refreshTree();
    },
    addCommand: (id, def) => { commands[id] = def; if (def.sc) keymap[def.sc] = id; },
    removeCommand: (id) => { const sc = commands[id]?.sc; if (sc && keymap[sc] === id) delete keymap[sc]; delete commands[id]; },
    openExternal: (url) => api.openRepo(url),
    openWeb: (url) => api.openWeb(url),
    studioVisible: () => studio.visible,
    activeFile: () => engineTab()?.path || activeTab()?.path || null,
    monacoReady: () => monacoReady,
    // Tuff Engine
    openEngine,
    engineVisible: () => engine.visible,
    scene: (file, source, tag) => api.engine.scene(file, source, tag),
    stopRun: () => api.run.stop(),
    isRunning: () => !!state.running,
    runCommand: (id) => commands[id]?.run(),
    hasCommand: (id) => !!commands[id],
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
    $('#app').classList.toggle('studio-full', !!s.studioFull);
    $('#sb-indent').textContent = `${tabSize()} spaces`;
    buildMenubar();
    api.win.isMaximized().then(setMaxIcon);

    monacoReady = loadMonaco();
    const last = s.lastFolder && (await api.fs.exists(s.lastFolder)) ? s.lastFolder : null;
    const root = last || (await api.project.default());
    const firstRun = !s.introSeen;
    // After an update the intro plays once more, but nothing else starts over: the folder, tabs,
    // Learn Tuff progress, settings and plugins all carry on (they live in userData, which updates keep).
    const updated = !firstRun && s.introVersion !== state.version;
    const before = s.introVersion; // (the intro saves the new one when it ends)

    window.TuffStudio.init(window.TuffIDE);
    window.TuffEngine?.init(window.TuffIDE);
    window.TuffWhatsNew?.init({ openWeb: (url) => api.openWeb(url), focusEditor: () => editor?.focus() });
    if (firstRun) {
      const introDone = playIntro();
      await openFolder(root);
      window.TuffLearn.init(window.TuffIDE);
      showSideView('learn', true);
      await openFile(join(root, 'main.tuf'), { focus: false, quiet: true });
      await introDone;
    } else {
      const introDone = updated ? playIntro() : null;
      window.TuffLearn.init(window.TuffIDE);
      await openFolder(root, { restore: last ? { tabs: s.openTabs, active: s.activeTab } : null });
      if (!state.tabs.length && !last) await openFile(join(root, 'main.tuf'), { quiet: true });
      if (introDone) {
        await introDone;
        // Updated from a version that played the intro before: "Here's what's changed!", once.
        if (before) await window.TuffWhatsNew?.maybeShow(state.version, s, saveSettings);
      } else {
        enterIDE();
        editor?.focus();
      }
    }
    window.TuffPluginHost?.init(window.TuffIDE);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
