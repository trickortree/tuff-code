// New Project (File > New Project…, 1.5.0): a gallery of starters, real projects to grow (tuffcode/starters, copied
// by starters.js). Pick one, name it and choose where it goes; Create makes a new folder with its files, opens it as
// the project and opens its main.tuf. A name that's taken is never overwritten: the dialog offers a free one
// ("Snake 2"). The arrow keys move between the cards (Up and Down work in the search box too), Enter creates and Esc
// closes. The folder picked last is remembered (settings.newProjectFolder); Documents/TuffProjects is the default.
(() => {
  const api = window.tuff;
  const ide = () => window.TuffIDE;
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const icon = (name) => (window.TuffIcon ? window.TuffIcon(name) : '');
  const basename = (p) => String(p).split(/[\\/]/).filter(Boolean).pop() || String(p);

  const S = {
    box: null, // the dialog, while it's open
    starters: null, // from starters:list, kept once they've loaded
    home: '', // where projects go by default (Documents/TuffProjects)
    folder: '', // where this one goes
    shown: [], // the starters the search leaves, in order
    sel: null, // the chosen starter's id
    typed: false, // the name was typed, so choosing another starter keeps it
    status: null, // the last check of the name: { ok, target } or { problem } or { taken, free }
    seq: 0, // the newest check: older answers are dropped
    choosing: null, // the last choose() while it fills in the name, so Create waits for it
    timer: null,
    busy: false,
    back: null, // what had the focus before, to give it back
  };
  const starter = () => (S.starters || []).find((s) => s.id === S.sel) || null;
  const nameBox = () => $('#np-name', S.box);

  async function open() {
    if (S.box) { $('#np-q', S.box).focus(); return; }
    S.back = document.activeElement;
    S.typed = false;
    S.status = null;
    S.busy = false;
    S.box = document.createElement('div');
    S.box.id = 'new-project';
    S.box.innerHTML = `<div class="np-box" role="dialog" aria-modal="true" aria-labelledby="np-title">
      <div class="np-head">
        <div class="np-titles"><b id="np-title">New Project</b><span>Start from a real project: run it, read it, make it yours.</span></div>
        <label class="np-search">${icon('search-line')}<input id="np-q" type="text" placeholder="Search starters" spellcheck="false" autocomplete="off" aria-label="Search starters" /></label>
        <button class="st-x" data-a="close" title="Close (Esc)">${icon('close-line')}</button>
      </div>
      <div class="np-grid" id="np-grid" role="listbox" aria-label="Starters"></div>
      <div class="np-foot">
        <div class="np-fields">
          <label class="np-field"><span class="np-label">Project name</span><input id="np-name" type="text" spellcheck="false" autocomplete="off" maxlength="80" /></label>
          <div class="np-field"><span class="np-label">Folder</span><div class="np-where"><span id="np-folder"></span><button class="btn sm" data-a="change">Change…</button></div></div>
        </div>
        <div class="np-bottom">
          <div class="np-status" id="np-status" aria-live="polite"></div>
          <button class="btn" data-a="cancel">Cancel</button>
          <button class="btn primary" data-a="create" id="np-create" disabled>Create</button>
        </div>
      </div>
    </div>`;
    document.body.appendChild(S.box);
    wire();
    $('#np-q', S.box).focus();
    if (!S.starters?.length) {
      try {
        const got = await api.starters.list();
        S.starters = got.starters || [];
        S.home = got.folder || '';
      } catch {
        S.starters = [];
      }
    }
    if (!S.box) return; // closed while they loaded
    const saved = ide()?.settings?.()?.newProjectFolder;
    S.folder = typeof saved === 'string' && saved && (await api.fs.exists(saved)) ? saved : S.home;
    if (!S.box) return;
    showFolder();
    S.sel = null;
    render(); // chooses the first starter, and fills in its name
  }

  function close(restore = true) {
    if (!S.box) return;
    S.box.remove();
    S.box = null;
    S.seq++;
    clearTimeout(S.timer);
    const back = S.back;
    S.back = null;
    if (!restore) return;
    if (back && back.isConnected && back !== document.body && back.focus) back.focus();
    else ide()?.editor?.()?.focus();
  }

  function wire() {
    const box = S.box;
    box.addEventListener('keydown', onKey);
    box.addEventListener('mousedown', (e) => { if (e.target === box) close(); });
    box.addEventListener('click', (e) => {
      const card = e.target.closest('.np-card');
      if (card) { choose(card.dataset.id, { focus: true }); return; }
      const a = e.target.closest('[data-a]')?.dataset.a;
      if (a === 'close' || a === 'cancel') close();
      else if (a === 'change') pickFolder();
      else if (a === 'create') create();
      else if (a === 'free' && S.status?.free) useName(S.status.free);
    });
    box.addEventListener('dblclick', (e) => { if (e.target.closest('.np-card')) create(); });
    $('#np-q', box).addEventListener('input', render);
    nameBox().addEventListener('input', () => {
      S.typed = nameBox().value.trim() !== ''; // emptied: choosing a starter fills it in again
      clearTimeout(S.timer);
      S.timer = setTimeout(check, 120);
    });
  }

  // The cards the search leaves. Every word typed has to be in a starter's name, about line or tags.
  function render() {
    if (!S.box) return;
    const q = $('#np-q', S.box).value.trim();
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const all = S.starters || [];
    S.shown = all.filter((s) => words.every((w) => `${s.name} ${s.about} ${s.tags.join(' ')}`.toLowerCase().includes(w)));
    const grid = $('#np-grid', S.box);
    grid.innerHTML = '';
    for (const s of S.shown) {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'np-card';
      card.dataset.id = s.id;
      card.setAttribute('role', 'option');
      if (s.color) card.style.setProperty('--np-tint', s.color);
      card.innerHTML = `<span class="np-pic">${s.picture || icon('file-line')}</span><span class="np-info"><b>${esc(s.name)}</b>`
        + `<span class="np-about">${esc(s.about)}</span>${s.tags.length ? `<span class="np-tags">${s.tags.map((t) => `<span>${esc(t)}</span>`).join('')}</span>` : ''}</span>`;
      grid.appendChild(card);
    }
    if (!S.shown.length) {
      grid.innerHTML = `<div class="np-none">${all.length ? `No starter matches “${esc(q)}”.` : 'The starters are missing. Reinstalling TuffCode brings them back.'}</div>`;
    }
    if (S.shown.some((s) => s.id === S.sel)) mark();
    else choose(S.shown[0]?.id || null);
  }

  // Shows which card is chosen: one card at a time takes Tab (the chosen one), and it scrolls into view.
  function mark(focus = false) {
    for (const card of S.box.querySelectorAll('.np-card')) {
      const on = card.dataset.id === S.sel;
      card.classList.toggle('sel', on);
      card.setAttribute('aria-selected', on ? 'true' : 'false');
      card.tabIndex = on ? 0 : -1;
      if (on) {
        card.scrollIntoView?.({ block: 'nearest' });
        if (focus) card.focus();
      }
    }
  }

  function choose(id, { focus = false } = {}) {
    S.choosing = picked(id, focus);
    return S.choosing;
  }

  async function picked(id, focus) {
    if (!S.box) return;
    S.sel = id;
    mark(focus);
    const s = starter();
    if (s && !S.typed) {
      // The starter's own name, or a free one ("Snake 2") when the folder has that one already.
      const n = ++S.seq;
      const res = await api.starters.check(S.folder, s.project);
      if (!S.box || n !== S.seq || S.sel !== id || S.typed) return;
      nameBox().value = res.taken && res.free ? res.free : s.project;
    }
    await check();
  }

  // Checks the name in the folder (starters:check) and says what Create will do.
  async function check() {
    if (!S.box) return null;
    clearTimeout(S.timer);
    const n = ++S.seq;
    const res = S.sel ? await api.starters.check(S.folder, nameBox().value) : { ok: false, problem: '' };
    if (!S.box || n !== S.seq) return S.status;
    S.status = res;
    showStatus();
    return res;
  }

  function showStatus() {
    const el = $('#np-status', S.box);
    const res = S.status || {};
    el.className = 'np-status' + (res.taken ? ' taken' : res.problem ? ' bad' : '');
    if (S.busy) el.textContent = 'Making the project…';
    else if (res.ok) el.innerHTML = `Makes <code>${esc(res.target)}</code>`;
    else if (res.taken) el.innerHTML = `There's already a “${esc(basename(res.target))}” there.${res.free ? ` <button type="button" data-a="free">Use “${esc(res.free)}”</button>` : ''}`;
    else el.textContent = res.problem || '';
    el.title = res.ok ? res.target : '';
    const create = $('#np-create', S.box);
    create.disabled = S.busy || !S.sel || !(res.ok || (res.taken && res.free));
    create.textContent = S.busy ? 'Creating…' : 'Create';
  }

  function showFolder() {
    const el = $('#np-folder', S.box);
    el.innerHTML = `<bdi>${esc(S.folder)}</bdi>`;
    el.title = S.folder;
  }

  function useName(name) {
    const box = nameBox();
    box.value = name;
    S.typed = true;
    box.focus();
    check();
  }

  async function pickFolder() {
    const dir = await api.starters.pickFolder(S.folder);
    if (!dir || !S.box) return;
    S.folder = dir;
    showFolder();
    if (S.typed) await check();
    else await choose(S.sel);
  }

  async function create() {
    if (S.busy || !S.box) return;
    await S.choosing; // a card double-clicked, or Enter right after an arrow key: its name first
    const s = starter();
    if (!s || !S.box) return;
    const res = await check(); // the name as it is now
    if (!S.box || S.busy) return;
    if (res?.taken && res.free) { useName(res.free); return; } // Enter on a taken name offers the free one first
    if (!res?.ok) { nameBox().focus(); return; }
    S.busy = true;
    showStatus();
    let made;
    try {
      made = await api.starters.create(s.id, S.folder, nameBox().value);
    } catch (err) {
      made = { ok: false, problem: String(err?.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, '') };
    }
    S.busy = false;
    if (!S.box) return;
    if (!made?.ok) {
      S.status = made || { ok: false, problem: 'Something went wrong.' };
      showStatus();
      return;
    }
    const folder = S.folder;
    close(false);
    const I = ide();
    I.saveSettings?.({ newProjectFolder: folder === S.home ? null : folder });
    await I.openFolder(made.dir);
    await I.openFile(made.main);
    I.toast(`Made ${basename(made.dir)} from the ${s.name} starter. Press Shift+F10 to run it.`, 'ok', 5000);
  }

  // How many cards fit across: the ones on the first card's row.
  function columns() {
    const cards = [...S.box.querySelectorAll('.np-card')];
    let n = 0;
    for (const card of cards) {
      if (card.offsetTop !== cards[0].offsetTop) break;
      n++;
    }
    return Math.max(1, n);
  }

  function move(by, focus) {
    if (!S.shown.length) return;
    const at = S.shown.findIndex((s) => s.id === S.sel);
    const to = Math.max(0, Math.min(S.shown.length - 1, at < 0 ? 0 : at + by));
    if (to !== at) choose(S.shown[to].id, { focus });
    else if (focus) mark(true);
  }

  function onKey(e) {
    const t = e.target;
    const inSearch = t.id === 'np-q';
    const onCard = !!t.closest?.('.np-card');
    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close();
    } else if (e.key === 'Enter' && plain && !e.shiftKey && (inSearch || onCard || t.id === 'np-name')) {
      e.preventDefault();
      create();
    } else if (e.key === 'Tab') {
      // Tab stays in the dialog: from the last thing back to the first, and the other way with Shift.
      const stops = [...S.box.querySelectorAll('input, button')].filter((el) => !el.disabled && el.tabIndex >= 0);
      const i = stops.indexOf(t);
      if (e.shiftKey && i <= 0) { e.preventDefault(); stops[stops.length - 1]?.focus(); }
      else if (!e.shiftKey && i === stops.length - 1) { e.preventDefault(); stops[0]?.focus(); }
    } else if (onCard && plain && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) {
      e.preventDefault();
      const cols = columns();
      move({ ArrowLeft: -1, ArrowRight: 1, ArrowUp: -cols, ArrowDown: cols, Home: -Infinity, End: Infinity }[e.key], true);
    } else if (inSearch && plain && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault();
      move(e.key === 'ArrowDown' ? columns() : -columns(), false);
    } else if (onCard && plain && e.key.length === 1 && e.key !== ' ') {
      $('#np-q', S.box).focus(); // typing on a card searches
    }
  }

  document.getElementById('es-new-project')?.addEventListener('click', () => open());
  window.TuffNewProject = { open, close, isOpen: () => !!S.box };
})();
