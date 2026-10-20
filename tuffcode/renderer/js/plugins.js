// Plugin host: loads installed plugins, gives them a small API, shows their panels in the
// right sidebar and draws the Plugins marketplace view. Plugin scripts call
// TuffPlugins.register(id, activate) and get the API object passed to activate.
(() => {
  const api = window.tuff;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  const H = {
    ide: null,
    list: { installed: [], available: [] },
    defs: new Map(), // id -> activate function from the plugin's script
    active: new Map(), // id -> { panels, commands, dispose }
    panels: new Map(), // "plugin:panel" -> { title, icon, el, mount, mounted, hooks }
    requested: new Set(),
    open: null,
    tab: 'market',
    query: '',
    busy: new Set(),
  };

  // An icon from a manifest or the marketplace is SVG text. It's drawn as a CSS mask so it takes the
  // button's color and can never run anything.
  const iconHtml = (svg, cls = 'pi') => {
    const ok = typeof svg === 'string' && /^<svg[\s>]/.test(svg.trim());
    const url = ok ? `url('data:image/svg+xml,${encodeURIComponent(svg.trim()).replace(/'/g, '%27')}')` : '';
    return `<span class="${cls}${ok ? '' : ' none'}" style="${ok ? `-webkit-mask-image:${url};mask-image:${url}` : ''}"></span>`;
  };

  window.TuffPlugins = {
    register(id, activate) {
      if (typeof activate !== 'function') return;
      H.defs.set(id, activate);
      const p = H.list.installed.find((x) => x.id === id);
      if (p?.enabled) activatePlugin(p);
    },
  };

  // ---------------------------------------------------------------- loading
  async function refresh(force) {
    try {
      H.list = await api.plugins.list(force);
    } catch (err) {
      H.ide.toast(`Couldn't load plugins: ${err.message}`, 'error');
    }
    sync();
    renderMarket();
  }

  function sync() {
    for (const p of H.list.installed) {
      if (p.enabled && !H.active.has(p.id)) load(p);
      if (!p.enabled && H.active.has(p.id)) deactivate(p.id);
    }
    for (const id of [...H.active.keys()]) if (!H.list.installed.some((p) => p.id === id)) deactivate(id);
  }

  function ensureStyle(p) {
    if (!p.style || $(`link[data-plugin="${CSS.escape(p.id)}"]`)) return;
    const l = document.createElement('link');
    l.rel = 'stylesheet';
    l.href = p.url + p.style;
    l.dataset.plugin = p.id;
    document.head.appendChild(l);
  }

  function load(p) {
    ensureStyle(p);
    if (H.defs.has(p.id)) return activatePlugin(p);
    if (H.requested.has(p.id)) return;
    H.requested.add(p.id);
    const s = document.createElement('script');
    s.src = p.url + (p.main || 'panel.js');
    s.dataset.plugin = p.id;
    s.onerror = () => H.ide.toast(`Couldn't load the ${p.name} plugin.`, 'error');
    document.body.appendChild(s);
  }

  function activatePlugin(p) {
    if (H.active.has(p.id)) return;
    ensureStyle(p);
    const rec = { panels: [], commands: [], dispose: null };
    H.active.set(p.id, rec);
    try {
      rec.dispose = H.defs.get(p.id)(makeApi(p, rec)) || null;
    } catch (err) {
      console.error(err);
      H.ide.toast(`The ${p.name} plugin crashed while starting: ${err.message}`, 'error', 6000);
    }
    renderStrip();
    const last = H.ide.settings().rightPanel;
    if (H.openWhenReady === p.id && rec.panels.length) {
      H.openWhenReady = null;
      openPanel(rec.panels[0]);
    } else if (last && rec.panels.includes(last) && !H.open) openPanel(last);
  }

  function deactivate(id) {
    const rec = H.active.get(id);
    if (!rec) return;
    try { if (typeof rec.dispose === 'function') rec.dispose(); } catch (err) { console.error(err); }
    for (const key of rec.panels) {
      if (H.open === key) closePanel();
      H.panels.get(key)?.el.remove();
      H.panels.delete(key);
    }
    for (const c of rec.commands) H.ide.removeCommand(c);
    H.active.delete(id);
    $(`link[data-plugin="${CSS.escape(id)}"]`)?.remove();
    renderStrip();
  }

  function makeApi(p, rec) {
    const ide = H.ide;
    const perms = p.permissions || [];
    return {
      id: p.id,
      manifest: p,
      panel(id, { title, icon, mount } = {}) {
        const key = `${p.id}:${id}`;
        const el = document.createElement('div');
        el.className = 'rb-panel hidden';
        el.dataset.panel = key;
        $('#rb-body').appendChild(el);
        H.panels.set(key, { key, pluginId: p.id, title: title || p.name, icon: icon || p.icon, el, mount, mounted: false, hooks: {} });
        rec.panels.push(key);
        renderStrip();
        return { open: () => openPanel(key), close: () => H.open === key && closePanel(), toggle: () => (H.open === key ? closePanel() : openPanel(key)), element: el, isOpen: () => H.open === key };
      },
      command(id, label, run, sc) {
        const full = `plugin.${p.id}.${id}`;
        ide.addCommand(full, { label, sc, run });
        rec.commands.push(full);
      },
      editor: {
        code: () => ide.activeCode(),
        selection: () => ide.selectionText(),
        selectionLines: () => ide.selectionLines(),
        file: () => ide.activeFile(),
        insert: (text) => ide.insertText(text),
        insertSnippet: (text) => ide.insertText(text, { snippet: true }),
        replaceAll: (text) => ide.replaceAllText(text),
      },
      project: {
        root: () => ide.root(),
        files: () => ide.listFiles(),
        read: (path) => api.fs.readFile(path),
        rel: (path) => ide.rel(path),
        // "files" permission: save text or base64 data (like a PNG or WAV) at a path inside the project.
        write: perms.includes('files') ? async (path, data, { encoding = 'utf8' } = {}) => {
          const saved = await api.plugins.writeFile(ide.root(), path, data, encoding);
          await ide.reloadChanged();
          return saved;
        } : undefined,
      },
      openFile: (path) => ide.openFile(path),
      run: (path) => ide.runFile(path),
      toast: (msg, kind, ms) => ide.toast(msg, kind, ms),
      ask: (opts) => ide.ask(opts),
      reloadChanged: () => ide.reloadChanged(),
      openExternal: (url) => ide.openExternal(url),
      storage: {
        get: (k, d) => ((ide.settings().pluginData || {})[p.id] || {})[k] ?? d,
        set: (k, v) => {
          const all = { ...(ide.settings().pluginData || {}) };
          all[p.id] = { ...(all[p.id] || {}), [k]: v };
          ide.saveSettings({ pluginData: all });
        },
      },
      tuff: { keywords: window.TUFF_KEYWORDS, docs: window.TUFF_DOCS, methods: window.TUFF_METHOD_DOCS, libs: window.TUFF_LIBS, templates: window.TUFF_TEMPLATES },
      agents: perms.includes('agents') ? api.agents : undefined,
      // "net" permission: web requests from the main process: request({ url, method, headers, body }).
      net: perms.includes('net') ? { request: (opts) => api.plugins.request(opts) } : undefined,
    };
  }

  // ---------------------------------------------------------------- right sidebar
  function openPanel(key) {
    const p = H.panels.get(key);
    if (!p) return;
    if (H.open && H.open !== key) {
      const old = H.panels.get(H.open);
      old?.el.classList.add('hidden');
      try { old?.hooks.onHide?.(); } catch {}
    }
    H.open = key;
    $('#rightbar').classList.remove('hidden');
    $('#rightbar-resizer').classList.remove('hidden');
    $('#rb-title').textContent = p.title;
    p.el.classList.remove('hidden');
    if (!p.mounted) {
      p.mounted = true;
      try { p.hooks = p.mount?.(p.el) || {}; } catch (err) { console.error(err); p.el.innerHTML = `<div class="rb-error">This panel crashed: ${esc(err.message)}</div>`; }
    }
    try { p.hooks.onShow?.(); } catch {}
    renderStrip();
    H.ide.saveSettings({ rightPanel: key });
  }

  function closePanel() {
    const p = H.panels.get(H.open);
    p?.el.classList.add('hidden');
    try { p?.hooks.onHide?.(); } catch {}
    H.open = null;
    $('#rightbar').classList.add('hidden');
    $('#rightbar-resizer').classList.add('hidden');
    renderStrip();
    H.ide.saveSettings({ rightPanel: null });
  }

  function renderStrip() {
    const strip = $('#toolstrip-right');
    strip.innerHTML = '';
    for (const p of H.panels.values()) {
      const b = document.createElement('button');
      b.className = 'ts-btn' + (H.open === p.key ? ' active' : '');
      b.title = p.title;
      b.innerHTML = iconHtml(p.icon);
      b.onclick = () => (H.open === p.key ? closePanel() : openPanel(p.key));
      strip.appendChild(b);
    }
    strip.classList.toggle('hidden', !H.panels.size);
  }

  function setupResizer() {
    const handle = $('#rightbar-resizer');
    const root = document.documentElement.style;
    const saved = H.ide.settings().rightW;
    if (saved) root.setProperty('--rightbar-w', saved);
    handle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      handle.classList.add('dragging');
      document.body.style.cursor = 'col-resize';
      const move = (ev) => {
        const w = Math.max(280, Math.min(760, $('#rightbar').getBoundingClientRect().right - ev.clientX));
        root.setProperty('--rightbar-w', `${w}px`);
      };
      const up = () => {
        handle.classList.remove('dragging');
        document.body.style.cursor = '';
        removeEventListener('mousemove', move);
        removeEventListener('mouseup', up);
        H.ide.saveSettings({ rightW: root.getPropertyValue('--rightbar-w') });
      };
      addEventListener('mousemove', move);
      addEventListener('mouseup', up);
    });
    $('#rb-hide').onclick = closePanel;
  }

  // ---------------------------------------------------------------- marketplace view
  function renderMarket() {
    const body = $('#pl-body');
    if (!body) return;
    if (!body.firstChild) {
      body.innerHTML = `
        <div class="pl-tabs"><button data-t="market">Marketplace</button><button data-t="installed">Installed</button></div>
        <label class="pl-search"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg><input id="pl-q" placeholder="Search plugins" spellcheck="false"></label>
        <div class="pl-list" id="pl-list"></div>
        <div class="pl-foot">Plugins run inside TuffCode and can read and change files in your projects. Only install ones you trust.
          <button class="pl-link" id="pl-make">Make your own plugin</button></div>`;
      $$('.pl-tabs button', body).forEach((b) => (b.onclick = () => { H.tab = b.dataset.t; renderMarket(); }));
      $('#pl-q', body).oninput = (e) => { H.query = e.target.value.trim().toLowerCase(); renderMarket(); };
      $('#pl-make', body).onclick = () => H.ide.openExternal('https://github.com/trickortree/tuff-code/blob/main/tuffcode/plugins/README.md');
    }
    $$('.pl-tabs button', body).forEach((b) => b.classList.toggle('on', b.dataset.t === H.tab));
    const installedById = new Map(H.list.installed.map((p) => [p.id, p]));
    let items = H.tab === 'installed' ? H.list.installed : H.list.available.map((a) => ({ ...a, ...(installedById.get(a.id) || {}), installed: installedById.has(a.id) }));
    if (H.query) items = items.filter((p) => `${p.name} ${p.description} ${(p.tags || []).join(' ')}`.toLowerCase().includes(H.query));
    const list = $('#pl-list', body);
    if (!items.length) {
      list.innerHTML = `<div class="pl-empty">${H.tab === 'installed' ? 'No plugins installed yet. Have a look in the Marketplace.' : 'No plugins match.'}</div>`;
      return;
    }
    list.innerHTML = '';
    for (const p of items) {
      const inst = installedById.get(p.id);
      const busy = H.busy.has(p.id);
      const card = document.createElement('div');
      card.className = 'pl-card' + (inst && !inst.enabled ? ' off' : '');
      card.dataset.id = p.id;
      card.innerHTML = `
        <div class="pl-ic">${iconHtml(p.icon)}</div>
        <div class="pl-info">
          <div class="pl-name"><b>${esc(p.name)}</b><span class="pl-ver">${esc(p.version || '')}</span></div>
          <div class="pl-by">by ${esc(p.author || 'someone')}${p.builtin ? ' · comes with TuffCode' : ''}</div>
          <p>${esc(p.description || '')}</p>
          ${(p.tags || []).length ? `<div class="pl-tags">${p.tags.map((t) => `<span>${esc(t)}</span>`).join('')}</div>` : ''}
          <div class="pl-btns">${!inst
            ? `<button class="btn sm primary" data-a="install" ${busy ? 'disabled' : ''}>${busy ? 'Installing…' : 'Install'}</button>`
            : `${inst.enabled && inst.panels?.length ? '<button class="btn sm primary" data-a="open">Open</button>' : ''}
               <button class="btn sm" data-a="toggle" ${busy ? 'disabled' : ''}>${inst.enabled ? 'Turn off' : 'Turn on'}</button>
               <button class="btn sm danger" data-a="uninstall" ${busy ? 'disabled' : ''}>Uninstall</button>`}</div>
        </div>`;
      card.onclick = (e) => {
        const a = e.target.closest('button')?.dataset.a;
        if (a) action(a, p.id);
      };
      list.appendChild(card);
    }
  }

  async function action(a, id) {
    if (a === 'open') {
      const key = [...H.panels.keys()].find((k) => k.startsWith(`${id}:`));
      if (key) openPanel(key);
      return;
    }
    H.busy.add(id);
    renderMarket();
    try {
      const name = H.list.available.find((p) => p.id === id)?.name || id;
      if (a === 'install') {
        H.list = await api.plugins.install(id);
        H.ide.toast(`Installed ${name}.`, 'ok');
      } else if (a === 'uninstall') {
        const ok = await H.ide.ask({ title: `Uninstall ${name}?`, confirm: true, okLabel: 'Uninstall' });
        if (!ok) return;
        H.list = await api.plugins.uninstall(id);
        H.ide.toast(`Uninstalled ${name}.`);
      } else if (a === 'toggle') {
        const on = !H.list.installed.find((p) => p.id === id)?.enabled;
        H.list = await api.plugins.setEnabled(id, on);
      }
      // A new plugin's panel opens as soon as the plugin has started (its script loads separately).
      if (a === 'install') H.openWhenReady = id;
      sync();
    } catch (err) {
      H.ide.toast(String(err.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, ''), 'error', 6000);
    } finally {
      H.busy.delete(id);
      renderMarket();
    }
  }

  window.TuffPluginHost = {
    async init(ide) {
      H.ide = ide;
      setupResizer();
      $('#pl-refresh').onclick = () => refresh(true);
      await refresh(false);
    },
    showMarket: () => renderMarket(),
    openPanel,
    closePanel,
    state: () => ({ installed: H.list.installed.map((p) => ({ id: p.id, enabled: p.enabled })), active: [...H.active.keys()], panels: [...H.panels.keys()], open: H.open }),
  };
})();
