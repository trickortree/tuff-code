// Tuff Agents: a chat sidebar that runs Claude Code, Codex or Antigravity on your project.
// The agents get TuffCode's MCP tools (the Tuff language guide, examples, check and run).
// The plug button opens "Agent tools": a check that the tools work, connecting each agent, and
// commands for setting the tools up by hand.
TuffPlugins.register('tuff-agents', (t) => {
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const $ = (s, el) => el.querySelector(s);
  const $$ = (s, el) => [...el.querySelectorAll(s)];
  const short = (p) => (p ? String(p).split(/[\\/]/).pop() : '');
  const trim = (s, n) => (s.length > n ? `${s.slice(0, n)}\n… (cut off, ${s.length - n} more characters)` : s);

  const ORDER = ['claude', 'codex', 'antigravity', 'tuffai'];
  const CLI = ['claude', 'codex', 'antigravity']; // the agents TuffCode's MCP tools get connected to
  const SHORT = { claude: 'Claude', codex: 'Codex', antigravity: 'Antigravity', tuffai: 'Tuff AI' };
  const SUGGEST = [
    ['Explain this file', 'Explain what this file does, step by step, in simple words.', 'book', 'Step by step, in simple words'],
    ['Find bugs', 'Look for bugs or mistakes in this code and explain how to fix them.', 'bug', 'And how to fix them'],
    ['Make it nicer', 'Suggest ways to make this app look and feel nicer.', 'spark', 'Ideas for looks and feel'],
    ['Teach me something', 'Teach me one new Tuff trick that would help with this code, with a short example.', 'cap', 'One new Tuff trick'],
  ];
  // Small line icons (16x16, stroked).
  const ICONS = {
    book: '<path d="M3 3.5h4a2 2 0 0 1 2 2V13a1.5 1.5 0 0 0-1.5-1.5H3zM13 3.5H9a2 2 0 0 0-2 2V13a1.5 1.5 0 0 1 1.5-1.5H13z"/>',
    bug: '<rect x="5" y="5.5" width="6" height="7.5" rx="3"/><path d="M8 5.5V13M5 8.5H2.5M13.5 8.5H11M5.5 11.5l-2 1.5M10.5 11.5l2 1.5M6 5.5 4.5 3.5M10 5.5l1.5-2"/>',
    spark: '<path d="M8 2.5l1.3 3.7 3.7 1.3-3.7 1.3L8 12.5l-1.3-3.7L3 7.5l3.7-1.3z"/><path d="M12.5 11.5l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5-1.5-.5 1.5-.5z"/>',
    cap: '<path d="M1.5 6.5 8 3.5l6.5 3L8 9.5z"/><path d="M4 8v3c1 1 2.5 1.5 4 1.5s3-.5 4-1.5V8M14.5 6.5v4"/>',
    file: '<path d="M4 2h5l3 3v9H4z"/><path d="M9 2v3h3"/>',
    pencil: '<path d="M10.5 3 13 5.5 6 12.5H3.5V10z"/>',
    play: '<path d="M5 3.5v9l7-4.5z"/>',
    check: '<path d="M8 2 13 4v4c0 3-2.2 5-5 6-2.8-1-5-3-5-6V4z"/><path d="m5.8 8 1.6 1.6L10.4 6.4"/>',
    search: '<circle cx="7" cy="7" r="4"/><path d="m10 10 3.5 3.5"/>',
    list: '<path d="M6 4h7.5M6 8h7.5M6 12h7.5M2.5 4h.01M2.5 8h.01M2.5 12h.01"/>',
    globe: '<circle cx="8" cy="8" r="5.5"/><path d="M2.5 8h11M8 2.5c1.8 2 1.8 9 0 11M8 2.5c-1.8 2-1.8 9 0 11"/>',
    copy: '<rect x="5.5" y="5.5" width="7.5" height="7.5" rx="1.5"/><path d="M10.5 5.5V4A1.5 1.5 0 0 0 9 2.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1.5"/>',
    insert: '<path d="M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10"/>',
    apply: '<path d="m3.5 8.5 3 3 6-7"/>',
    cloud: '<path d="M4.5 12.5a3 3 0 0 1-.4-6 4 4 0 0 1 7.8.8 2.6 2.6 0 0 1-.4 5.2z"/><path d="M8 7v4M6.5 9.5 8 11l1.5-1.5"/>',
    chip: '<rect x="4" y="4" width="8" height="8" rx="1.5"/><path d="M6 1.5V4M10 1.5V4M6 12v2.5M10 12v2.5M1.5 6H4M1.5 10H4M12 6h2.5M12 10h2.5"/>',
    offline: '<path d="M2.5 8a8 8 0 0 1 11 0M4.5 10a5 5 0 0 1 7 0M8 12.5h.01"/><path d="M2.5 2.5l11 11"/>',
    info: '<circle cx="8" cy="8" r="5.5"/><path d="M8 7.5v3.5M8 5h.01"/>',
    bulb: '<path d="M6.2 12.5h3.6M6.7 14.5h2.6"/><path d="M8 1.5a4.5 4.5 0 0 0-2.6 8.2c.5.4.8.9.8 1.5v.3h3.6v-.3c0-.6.3-1.1.8-1.5A4.5 4.5 0 0 0 8 1.5z"/>',
    warn: '<path d="M8 2.5 14 13H2z"/><path d="M8 6.5v3M8 11.5h.01"/>',
  };
  const icon = (n, cls = 'ta-ic') => `<svg class="${cls}" viewBox="0 0 16 16" aria-hidden="true">${ICONS[n] || ''}</svg>`;
  const toolIcon = (text) => icon(/^(Changed|Wrote)\b/.test(text) ? 'pencil' : /^Ran\b/.test(text) ? 'play' : /^Checked\b/.test(text) ? 'check'
    : /^(Searched the project|Looked through)/.test(text) ? 'search' : /web/i.test(text) ? 'globe' : /^Planned/.test(text) ? 'list'
      : /Tuff (guide|examples)/.test(text) ? 'book' : 'file', 'ta-tool-ic');
  // Tuff code in replies is coloured like the editor. Monaco colours it once; the result is kept, so a
  // reply that's still streaming doesn't flicker.
  const lit = new Map();
  function colorize(scope) {
    const m = window.monaco;
    if (!m?.editor?.colorize) return;
    for (const el of scope.querySelectorAll('.ta-code[data-lang="tuff"] pre code:not(.lit)')) {
      const src = decodeURIComponent(el.closest('.ta-code').dataset.src || '');
      if (lit.has(src)) { el.innerHTML = lit.get(src); el.classList.add('lit'); continue; }
      m.editor.colorize(src, 'tuff', { tabSize: 4 }).then((raw) => {
        // Plain spaces and newlines (not &nbsp; and <br>), so code copied by hand from the chat runs.
        const html = raw.replace(/&nbsp;| /g, ' ').replace(/<br\/?>/g, '\n').replace(/\n$/, '');
        if (lit.size > 300) lit.clear();
        lit.set(src, html);
        if (el.isConnected) { el.innerHTML = html; el.classList.add('lit'); }
      }).catch(() => {});
    }
  }
  const NAME = { claude: 'Claude Code', codex: 'Codex', antigravity: 'Antigravity', tuffai: 'Tuff AI' };
  const GB = (n) => `${(n / 1e9).toFixed(1)} GB`;
  const PLUG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v5M15 3v5M6.5 8h11v3.5a5.5 5.5 0 0 1-11 0z"/><path d="M12 17v4"/></svg>';
  const STEPS = {
    start: "TuffCode's tools start up",
    tools: 'Agents can see all 4 tools',
    guide: 'The Tuff guide loads',
    examples: 'The example apps load',
    check: 'The checker spots a mistake',
    run: 'A Tuff program runs',
  };
  const TEST_PROMPT = 'This is a quick test of your TuffCode tools. 1) Call the tuff_reference tool. 2) Call the tuff_check tool on this code: say "Hello". 3) Reply with one short sentence saying which TuffCode tools worked. Don\'t change any files.';
  const cleanErr = (err) => String(err?.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, '');

  const S = {
    agents: null,
    agent: t.storage.get('agent', 'claude'),
    mode: t.storage.get('mode', 'ask'),
    conn: {},
    dismissed: t.storage.get('dismissed', {}),
    msgs: [],
    sessions: {},
    run: null,
    useFile: true,
    useSel: true,
    busy: false,
    view: 'chat', // or 'setup'
    check: null, // last tools check: { running } or { ok, steps }
    setup: null, // commands for setting the tools up by hand
    tested: {}, // agent id -> { ok, text } from "Test it"
    openMan: new Set(), // which "by hand" sections are open
    busyAgent: null, // agent being connected or removed
    auth: {}, // agent id -> signed in? (true / false / null when it can't tell)
    pick: t.storage.get('pick', {}), // agent id -> { model, effort } chosen for it ('' = the agent's default)
    models: {}, // agent id -> what it offers, as it reports it: { models, efforts }, { loading } or { error }
    used: {}, // agent id -> what its Default model turned out to be (from the agent itself), e.g. 'Opus 5.5'
    ai: null, // Tuff AI: { runtime, models, downloading, ram } from ai.js
    aiProg: null, // the model download: { got, total, done, error }
  };
  let root = null;
  let dd = null; // the Model and Thinking dropdowns
  let ctxTimer = null;
  let raf = 0;

  const panel = t.panel('chat', {
    title: 'Tuff Agents',
    mount(el) {
      root = el;
      build();
      refreshAgents();
      return {
        onShow: () => { updateCtx(); clearInterval(ctxTimer); ctxTimer = setInterval(updateCtx, 1500); setTimeout(() => $('textarea', root)?.focus(), 30); },
        onHide: () => clearInterval(ctxTimer),
      };
    },
  });
  t.command('open', 'Tuff Agents: Open', () => panel.toggle(), 'Ctrl+Shift+A');
  t.command('explain', 'Tuff Agents: Explain this code', () => quick('Explain what this code does, step by step, in simple words.'));
  t.command('fix', 'Tuff Agents: Find and fix bugs', () => quick('Look for bugs or mistakes in this code and explain how to fix them.'));

  const off = t.agents.onEvent(onEvent);
  const offAi = t.agents.ai?.onProgress((p) => {
    S.aiProg = p;
    if (p.done) {
      if (p.error) t.toast(p.error, 'error', 7000);
      else if (!p.stopped) t.toast(`${S.ai?.models[0]?.name || 'The model'} is downloaded, so Tuff AI is ready. Ask it anything about Tuff.`, 'ok', 5000);
      refreshAgents();
    } else if (S.agent === 'tuffai') renderStatus();
  });
  // The Run panel's Explain button on a Tuff error.
  window.tuffExplainError = (error) => quick(`I ran my program and got this error. Explain in simple words what's wrong and how to fix it:\n\`\`\`\n${error.trim()}\n\`\`\``);
  // Tuff Engine's "Ask an agent": opts.mode ('plan' | 'ask' | 'edit') and opts.note (added to the prompt, not shown in the chat).
  window.tuffAskAgent = (text, opts = {}) => quick(text, opts);

  async function quick(text, opts = {}) {
    panel.open();
    // The first time the panel opens, it's still looking for agents. Wait for that, or send() thinks
    // the agent isn't installed.
    if (!S.agents) await looking;
    if (S.view === 'setup') showSetup(false);
    if (S.run) { t.toast('Wait for the reply to finish, or press Stop, then try again.'); return; }
    send(text, opts);
  }

  // ---------------------------------------------------------------- layout
  function build() {
    root.innerHTML = `
      <div class="ta">
        <div class="ta-top">
          <div class="ta-agents" role="tablist" aria-label="Agent"></div>
          <button class="ta-ib" data-a="setup" title="Agent tools: set up and check (MCP)">${PLUG}</button>
          <button class="ta-ib" data-a="menu" title="More">⋯</button>
          <div class="ta-menu hidden"></div>
        </div>
        <div class="ta-status"></div>
        <div class="ta-msgs" aria-live="polite"></div>
        <div class="ta-setup hidden"></div>
        <div class="ta-compose">
          <div class="ta-slash hidden" role="listbox" aria-label="Commands"></div>
          <div class="ta-ctx"></div>
          <textarea rows="3" spellcheck="true" placeholder="Ask about your code…"></textarea>
          <div class="ta-row">
            <div class="ta-mode" role="radiogroup" aria-label="What the agent may do">
              <button data-m="plan" title="Plan: makes a step-by-step plan first. Nothing changes until you click Go ahead.">Plan</button>
              <button data-m="ask" title="Ask: explains and suggests, and asks before changing anything. Won't change your files.">Ask</button>
              <button data-m="edit" title="Edit: can change files in this project to do what you ask.">Edit</button>
            </div>
            <div class="ta-opts">
              <div class="ta-dd" data-o="model"></div>
              <div class="ta-dd" data-o="effort"></div>
            </div>
            <span class="ta-hint"></span>
            <button class="ta-send" title="Send (Enter)" aria-label="Send">Send</button>
          </div>
        </div>
      </div>`;
    const ta = $('textarea', root);
    ta.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (slashKey(e)) return;
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(ta.value); }
    });
    ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = `${Math.min(220, ta.scrollHeight)}px`; renderSlash(); });
    ta.addEventListener('blur', () => setTimeout(() => { slash.open = false; renderSlash(); }, 120));
    $('.ta-slash', root).addEventListener('mousedown', (e) => {
      const b = e.target.closest('[data-cmd]');
      if (!b) return;
      e.preventDefault();
      pickSlash(b.dataset.cmd);
    });
    ta.addEventListener('focus', updateCtx);
    $('.ta-send', root).onclick = () => (S.run ? stop() : send(ta.value));
    $$('.ta-mode button', root).forEach((b) => (b.onclick = () => { S.mode = b.dataset.m; t.storage.set('mode', S.mode); renderMode(); }));
    const choose = (key) => (v) => {
      if (S.run) return;
      S.pick = { ...S.pick, [S.agent]: { ...(S.pick[S.agent] || {}), [key]: v } };
      t.storage.set('pick', S.pick);
      renderPick();
    };
    dd = {
      model: dropdown($('.ta-dd[data-o="model"]', root), { label: 'Model', title: 'Which model the agent uses', onPick: choose('model') }),
      effort: dropdown($('.ta-dd[data-o="effort"]', root), { label: 'Thinking', title: 'How long the model thinks before it answers. Higher is slower but more careful.', onPick: choose('effort') }),
    };
    $('[data-a="menu"]', root).onclick = (e) => { e.stopPropagation(); toggleMenu(); };
    $('[data-a="setup"]', root).onclick = () => showSetup(S.view !== 'setup');
    const setupBox = $('.ta-setup', root);
    setupBox.addEventListener('click', onSetupClick);
    setupBox.addEventListener('toggle', (e) => {
      const d = e.target.closest?.('details[data-m]');
      if (d) d.open ? S.openMan.add(d.dataset.m) : S.openMan.delete(d.dataset.m);
    }, true);
    root.addEventListener('mousedown', (e) => { if (!e.target.closest('.ta-menu, [data-a="menu"]')) $('.ta-menu', root).classList.add('hidden'); });
    $('.ta-msgs', root).addEventListener('click', onMsgClick);
    // A reply is drawn again on every event, so remember which of its folds are open.
    $('.ta-msgs', root).addEventListener('toggle', (e) => {
      const d = e.target.closest?.('details[data-fold]');
      const m = d && S.msgs[+d.closest('.ta-msg')?.dataset.i];
      if (m) m.open = { ...(m.open || {}), [d.dataset.fold]: d.open };
    }, true);
    renderAgents();
    renderMode();
    renderMsgs();
    updateCtx();
  }

  const current = () => S.agents?.find((a) => a.id === S.agent);
  const isLocal = (id) => id === 'tuffai';

  let looking = Promise.resolve(); // settles once the latest look for agents has filled in S.agents
  async function refreshAgents() {
    S.agents = null;
    renderAgents();
    renderStatus();
    let found;
    looking = new Promise((r) => (found = r));
    try {
      S.agents = await t.agents.detect();
    } catch (err) {
      S.agents = [];
      t.toast(`Couldn't look for agents: ${err.message}`, 'error');
    }
    found();
    renderAgents();
    renderStatus();
    renderSetup();
    for (const a of S.agents.filter((x) => x.installed)) {
      t.agents.connection(a.id).then((c) => { S.conn[a.id] = c.connected; renderStatus(); renderSetup(); }).catch(() => {});
    }
    for (const id of ['claude', 'codex']) {
      if (!S.agents.find((x) => x.id === id)?.installed) continue;
      t.agents.signedIn(id).then((v) => { S.auth[id] = v; renderStatus(); renderSetup(); }).catch(() => {});
    }
    for (const a of S.agents.filter((x) => x.installed)) loadModels(a.id, true);
    t.agents.ai?.status().then((s) => { S.ai = s; renderStatus(); }).catch(() => {});
    renderPick();
    renderMode();
  }

  // Asks the agent which models and thinking levels it offers.
  function loadModels(id, fresh = false) {
    if (!t.agents.models) return;
    S.models[id] = { loading: true };
    if (id === S.agent) renderPick();
    t.agents.models(id, fresh)
      .then((r) => { S.models[id] = r; })
      .catch((err) => { S.models[id] = { error: cleanErr(err) }; })
      .finally(() => { if (id === S.agent) renderPick(); });
  }

  // The model the agent will use (null = its default) and the thinking levels on offer for it.
  // Tuff AI has one model, Pumice 1, and always a level: the one picked, or its default.
  function picked(id = S.agent) {
    const list = S.models[id] || {};
    const p = S.pick[id] || {};
    if (isLocal(id)) {
      const model = (list.models || []).find((m) => m.id === p.model) || (list.models || [])[0] || null;
      const efforts = model?.efforts || [];
      return { list, model, efforts, effort: efforts.find((e) => e.id === p.effort) || efforts.find((e) => e.id === model?.defaultEffort) || null };
    }
    const model = (list.models || []).find((m) => m.id === p.model) || null;
    let efforts = model ? model.efforts : list.efforts || [];
    if (!model && !efforts.length) { // default model: offer every level the agent knows
      const seen = new Map();
      for (const m of list.models || []) for (const e of m.efforts) seen.set(e.id, e);
      efforts = [...seen.values()];
    }
    const effort = efforts.find((e) => e.id === p.effort) || null;
    return { list, model, efforts, effort };
  }

  // ---------------------------------------------------------------- dropdowns
  // TuffCode's own dropdown (a system <select> can't be styled). It opens upwards from the message
  // box and works from the keyboard: arrows, Home/End, Enter or Space to pick, Esc to close.
  function dropdown(box, { label, title, onPick }) {
    box.innerHTML = `<button type="button" class="ta-dd-btn" aria-haspopup="listbox" aria-expanded="false" title="${esc(title)}"><span class="ta-dd-k">${esc(label)}</span><span class="ta-dd-v"></span><svg class="ta-dd-chev" viewBox="0 0 16 16"><path d="M4.5 9.5L8 6l3.5 3.5"/></svg></button><div class="ta-dd-menu hidden" role="listbox" aria-label="${esc(label)}"></div>`;
    const btn = $('.ta-dd-btn', box);
    const menu = $('.ta-dd-menu', box);
    let items = [];
    let value = '';
    let hot = -1;
    const isOpen = () => !menu.classList.contains('hidden');
    const draw = () => {
      menu.innerHTML = items.map((it, i) => `<div role="option" class="ta-dd-opt${it.id === value ? ' on' : ''}${i === hot ? ' hot' : ''}" data-i="${i}" data-v="${esc(it.id)}" aria-selected="${it.id === value}">${it.icon || ''}<span class="ta-dd-txt"><b>${esc(it.name)}</b>${it.sub ? `<small>${esc(it.sub)}</small>` : ''}</span><svg class="ta-dd-tick" viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7"/></svg></div>`).join('');
      menu.querySelector('.hot')?.scrollIntoView({ block: 'nearest' });
    };
    const outside = (e) => { if (!box.contains(e.target)) close(); };
    function close() {
      if (!isOpen()) return;
      menu.classList.add('hidden');
      btn.setAttribute('aria-expanded', 'false');
      document.removeEventListener('mousedown', outside, true);
    }
    function open() {
      if (btn.disabled || !items.length) return;
      for (const other of Object.values(dd || {})) if (other.box !== box) other.close();
      hot = Math.max(0, items.findIndex((it) => it.id === value));
      menu.classList.remove('hidden', 'flip');
      btn.setAttribute('aria-expanded', 'true');
      draw();
      // Keep the menu inside the panel: open it leftwards if it would run off the right edge.
      if (menu.getBoundingClientRect().right > root.getBoundingClientRect().right - 6) menu.classList.add('flip');
      document.addEventListener('mousedown', outside, true);
    }
    const pick = (i) => { const it = items[i]; close(); btn.focus(); if (it && it.id !== value) onPick(it.id); };
    btn.onclick = () => (isOpen() ? close() : open());
    btn.onkeydown = (e) => {
      if (!isOpen()) {
        if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); e.stopPropagation(); open(); }
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') hot = (hot + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      else if (e.key === 'Home') hot = 0;
      else if (e.key === 'End') hot = items.length - 1;
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); pick(hot); return; }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return; }
      else if (e.key === 'Tab') { close(); return; }
      else return;
      e.preventDefault();
      e.stopPropagation();
      draw();
    };
    menu.onmousedown = (e) => e.preventDefault();
    menu.onclick = (e) => { const o = e.target.closest('.ta-dd-opt'); if (o) pick(+o.dataset.i); };
    menu.onmousemove = (e) => {
      const o = e.target.closest('.ta-dd-opt');
      if (!o || +o.dataset.i === hot) return;
      hot = +o.dataset.i;
      menu.querySelectorAll('.ta-dd-opt').forEach((x) => x.classList.toggle('hot', +x.dataset.i === hot));
    };
    return {
      box,
      close,
      set({ list, val, text, disabled, tip }) {
        items = list;
        value = val;
        $('.ta-dd-v', box).textContent = text;
        btn.disabled = !!disabled;
        btn.title = tip || title;
        if (disabled) close();
        else if (isOpen()) draw();
      },
    };
  }

  const MODEL_ICON = '<svg class="ta-dd-ic" viewBox="0 0 16 16"><path d="M8 1.5l1.7 4.8L14.5 8l-4.8 1.7L8 14.5l-1.7-4.8L1.5 8l4.8-1.7z"/></svg>';
  const LEVEL_BARS = { off: 0, minimal: 1, low: 1, medium: 2, high: 3, xhigh: 4, max: 5, ultra: 5 };
  const LEVEL_SUB = { minimal: 'Fastest', low: 'Quick answers', medium: 'Balanced', high: 'Thinks it through', xhigh: 'Thinks longer', max: 'Most thorough', ultra: 'Deepest and slowest' };
  const levelIcon = (id) => `<span class="ta-dd-lv" aria-hidden="true">${[1, 2, 3, 4, 5].map((n) => `<i class="${n <= (LEVEL_BARS[id] || 0) ? 'on' : ''}" style="height:${4 + n * 2}px"></i>`).join('')}</span>`;

  function renderPick() {
    const box = $('.ta-opts', root);
    if (!box || !dd) return;
    const a = current();
    const { list, model, efforts, effort } = picked();
    box.classList.toggle('hidden', !a?.installed);
    if (list.loading) {
      dd.model.set({ list: [], val: '', text: 'Loading…', disabled: true });
      dd.effort.set({ list: [], val: '', text: 'Loading…', disabled: true });
      return;
    }
    const wait = S.run ? 'Wait for the reply to finish (or press Stop) to change this.' : '';
    if (isLocal(S.agent)) {
      // Pumice 1 and its own levels: Off, Low, Medium, High, with no "Default" entry (a level is always on).
      dd.model.set({
        list: (list.models || []).map((m) => ({ id: m.id, name: m.name, sub: m.sub || '', icon: MODEL_ICON })),
        val: model?.id || '',
        text: model?.name || 'Pumice 1',
        disabled: !!S.run || !!list.error,
        tip: list.error ? `Couldn't get the model list: ${list.error}` : wait || `${model?.name || 'Pumice 1'}: ${model?.sub || ''}`,
      });
      dd.effort.set({
        list: efforts.map((e) => ({ id: e.id, name: e.id === model?.defaultEffort ? `${e.name} (default)` : e.name, sub: e.sub || '', icon: levelIcon(e.id) })),
        val: effort?.id || '',
        text: effort?.name || 'Off',
        disabled: !!S.run || !efforts.length,
        tip: wait || `How hard ${model?.name || 'Pumice 1'} thinks before it answers. Higher is slower but more careful.`,
      });
      return;
    }
    const used = S.used[S.agent];
    dd.model.set({
      list: [
        { id: '', name: 'Default', sub: `${NAME[S.agent]} picks${used ? ` (last time: ${used})` : ''}`, icon: MODEL_ICON },
        ...(list.models || []).map((m) => ({ id: m.id, name: m.name, sub: m.sub || '', icon: MODEL_ICON })),
      ],
      val: model?.id || '',
      text: model?.name || (used ? `Default · ${used}` : 'Default'),
      disabled: !!S.run || !!list.error,
      tip: list.error ? `Couldn't get the model list: ${list.error}` : wait,
    });
    const def = model?.defaultEffort ? (efforts.find((e) => e.id === model.defaultEffort)?.name || model.defaultEffort) : '';
    dd.effort.set({
      list: [
        { id: '', name: def ? `Default (${def})` : 'Default', sub: def ? `${model.name}'s usual level` : 'The model decides', icon: levelIcon(def ? model.defaultEffort : '') },
        ...efforts.map((e) => ({ id: e.id, name: e.name, sub: LEVEL_SUB[e.id] || '', icon: levelIcon(e.id) })),
      ],
      val: effort?.id || '',
      text: effort?.name || (def ? `Default (${def})` : 'Default'),
      disabled: !!S.run || !efforts.length,
      tip: !efforts.length ? "This model doesn't have thinking levels." : wait,
    });
  }

  // While an agent is answering, its tab, model and thinking level stay as they are.
  function renderLock() {
    $$('.ta-agents button', root).forEach((b) => {
      b.disabled = !!S.run && b.dataset.id !== S.agent;
      b.title = b.disabled ? 'Wait for the reply to finish, or press Stop' : b.dataset.title || b.title;
    });
    renderPick();
  }

  // Each agent's desktop app keeps its own copy of the agent, which TuffCode finds and uses.
  const INSTALL_TIP = {
    claude: ' Have the Claude desktop app? Open its Code tab once (that sets up Claude Code), then click Check again.',
    codex: ' Have the Codex app? Open it once and sign in, then click Check again.',
  };
  function signInText(a) {
    const p = a.path || '';
    if (a.id === 'claude') return `TuffCode found Claude Code${/[\\/]Claude[\\/]claude-code[\\/]/.test(p) ? ' from your Claude desktop app' : ''}, but it isn't signed in for use outside that app. Sign in once with your Claude account.`;
    if (a.id === 'codex') return `TuffCode found Codex${/[\\/]OpenAI[\\/]Codex[\\/]/.test(p) ? ' from your Codex app' : ''}, but it isn't signed in. Sign in once with your ChatGPT account.`;
    return `${esc(a.name)} isn't signed in.`;
  }

  async function signInAgent(id) {
    try {
      await t.agents.signIn(id);
      t.toast('A sign-in window opened. Finish in your browser, then click Check again.', 'ok', 8000);
    } catch (err) {
      t.toast(cleanErr(err), 'error', 7000);
    }
  }

  function renderAgents() {
    const box = $('.ta-agents', root);
    box.innerHTML = ORDER.map((id) => {
      const a = S.agents?.find((x) => x.id === id);
      const state = !S.agents ? 'checking' : a?.installed ? 'ready' : 'missing';
      const title = !S.agents ? 'Checking…' : a?.installed ? `${a.name}${a.version ? ` ${a.version}` : ''}` : `${a?.name || id} isn't installed`;
      const locked = !!S.run && id !== S.agent;
      return `<button role="tab" data-id="${id}" class="${id === S.agent ? 'on' : ''}" data-title="${esc(title)}" title="${esc(locked ? 'Wait for the reply to finish, or press Stop' : title)}" aria-selected="${id === S.agent}"${locked ? ' disabled' : ''}><i class="dot ${state}"></i><span class="ta-tab-n">${SHORT[id]}</span></button>`;
    }).join('');
    $$('button', box).forEach((b) => (b.onclick = () => selectAgent(b.dataset.id)));
  }

  function selectAgent(id) {
    if (S.run && id !== S.agent) return;
    S.agent = id;
    t.storage.set('agent', S.agent);
    if (S.view === 'setup') showSetup(false);
    renderAgents();
    renderStatus();
    renderMsgs();
    renderPick();
    renderMode();
  }

  function newChat() {
    if (S.run) stop();
    S.msgs = [];
    S.sessions = {};
    S.used = {};
    renderMsgs();
    renderPick();
  }

  // ---------------------------------------------------------------- "/" commands in the message box
  const COMMANDS = [
    ['/help', 'Show these commands'],
    ['/new', 'Start a new chat'],
    ['/compact', 'Shrink the chat into a short summary every agent shares'],
    ['/ask', 'Ask mode. Add a message to send it, like /ask why is this slow?'],
    ['/plan', 'Plan mode: a plan first, nothing changes until Go ahead'],
    ['/edit', 'Edit mode: the agent may change your files'],
    ['/claude', 'Switch to Claude Code'],
    ['/codex', 'Switch to Codex'],
    ['/antigravity', 'Switch to Antigravity'],
    ['/tuffai', 'Switch to Tuff AI (runs on this computer)'],
    ['/model', 'Pick a model by name, like /model opus'],
    ['/explain', 'Explain the open file'],
    ['/fix', 'Find and fix bugs in the open file'],
    ['/tools', 'Set up and check agent tools'],
  ];
  const TAKES_TEXT = new Set(['/ask', '/plan', '/edit', '/claude', '/codex', '/antigravity', '/tuffai', '/model']);
  const slash = { open: false, hot: 0, list: [] };

  function renderSlash() {
    const box = $('.ta-slash', root);
    const v = $('textarea', root).value;
    const m = /^\/(\S*)$/.exec(v);
    slash.list = m ? COMMANDS.filter(([c]) => c.startsWith(`/${m[1].toLowerCase()}`)) : [];
    slash.open = !!slash.list.length && document.activeElement === $('textarea', root);
    slash.hot = Math.min(slash.hot, Math.max(0, slash.list.length - 1));
    box.classList.toggle('hidden', !slash.open);
    box.innerHTML = slash.list.map(([c, d], i) => `<div role="option" class="ta-slash-opt${i === slash.hot ? ' hot' : ''}" data-cmd="${c}" aria-selected="${i === slash.hot}"><b>${c}</b><span>${esc(d)}</span></div>`).join('');
  }

  // Arrow keys, Tab and Enter in the command list. Returns true when it handled the key.
  function slashKey(e) {
    renderSlash(); // the list must match what's in the box right now
    if (!slash.open) return false;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      slash.hot = (slash.hot + (e.key === 'ArrowDown' ? 1 : -1) + slash.list.length) % slash.list.length;
      renderSlash();
      return true;
    }
    if (e.key === 'Escape') { e.preventDefault(); slash.open = false; $('.ta-slash', root).classList.add('hidden'); return true; }
    if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
      e.preventDefault();
      // Enter on a command that's already typed out runs it; otherwise the highlighted one is filled in.
      // Filling in never runs anything, so /n + Tab can't clear the chat.
      const ta = $('textarea', root);
      const typed = ta.value.trim().toLowerCase();
      const cmd = slash.list[slash.hot][0];
      if (e.key === 'Enter' && COMMANDS.some(([c]) => c === typed)) send(typed);
      else { ta.value = TAKES_TEXT.has(cmd) ? `${cmd} ` : cmd; renderSlash(); }
      return true;
    }
    return false;
  }

  function pickSlash(cmd) {
    const ta = $('textarea', root);
    if (TAKES_TEXT.has(cmd)) {
      ta.value = `${cmd} `;
      ta.focus();
      renderSlash();
      return;
    }
    send(cmd);
  }

  // A line from TuffCode itself in the chat (not sent to any agent).
  function note(text) {
    S.msgs.push({ role: 'note', text });
    renderMsgs();
  }

  function clearInput() {
    const ta = $('textarea', root);
    ta.value = '';
    ta.style.height = 'auto';
    slash.open = false;
    renderSlash();
  }

  function command(text) {
    const cmd = text.split(/\s/)[0].toLowerCase();
    const arg = text.slice(cmd.length).trim();
    clearInput();
    if (cmd === '/help') return note(`Commands:\n${COMMANDS.map(([c, d]) => `${c}: ${d}`).join('\n')}`);
    if (cmd === '/new' || cmd === '/clear') return newChat();
    if (cmd === '/compact') return compact();
    if (['/ask', '/plan', '/edit'].includes(cmd)) {
      if (current()?.local && cmd !== '/ask') return note("Tuff AI only answers. Click Apply on its code to use it, or switch to another agent to plan or edit.");
      S.mode = cmd.slice(1);
      t.storage.set('mode', S.mode);
      renderMode();
      return arg ? send(arg) : null;
    }
    const agent = { '/claude': 'claude', '/codex': 'codex', '/antigravity': 'antigravity', '/agy': 'antigravity', '/tuffai': 'tuffai', '/tuff': 'tuffai' }[cmd];
    if (agent) {
      if (S.run) return note('Wait for the reply to finish, or press Stop, before switching agents.');
      selectAgent(agent);
      return arg ? send(arg) : null;
    }
    if (cmd === '/model') return pickModel(arg);
    if (cmd === '/explain') return send(SUGGEST[0][1]);
    if (cmd === '/fix') return send(SUGGEST[1][1]);
    if (cmd === '/tools' || cmd === '/setup') return showSetup(true);
    return note(`There's no ${cmd} command. Type /help to see them all.`);
  }

  function pickModel(name) {
    const list = S.models[S.agent]?.models || [];
    if (!name) return note(`Models for ${NAME[S.agent]}: ${list.map((m) => m.name).join(', ') || 'none listed'}. Pick one with /model <name>.`);
    const q = name.toLowerCase();
    const m = list.find((x) => x.name.toLowerCase() === q || x.id.toLowerCase() === q) || list.find((x) => x.name.toLowerCase().includes(q) || x.id.toLowerCase().includes(q));
    if (!m) return note(`${NAME[S.agent]} has no model called "${name}". It has: ${list.map((x) => x.name).join(', ') || 'none listed'}.`);
    S.pick = { ...S.pick, [S.agent]: { ...(S.pick[S.agent] || {}), model: m.id } };
    t.storage.set('pick', S.pick);
    renderPick();
    return note(`${NAME[S.agent]} will use ${m.name}.`);
  }

  // /compact: the agent sums up the chat so far. From then on, agents get that summary plus what came after,
  // and agents that keep their own session start a fresh one from it.
  const COMPACT_PROMPT = 'Summarize this whole chat so far for the team of agents, so the summary can replace it. In at most 10 short bullet points: what the person is making and asked for, what was decided, what each agent did (name them, and the files they changed), and what is still open. Write only the summary.';
  function compact() {
    if (S.run) return;
    // Tuff AI only reads the last few messages, so its summary would leave the rest of the chat out.
    if (current()?.local) return note('Tuff AI can only see the last few messages, so it can\'t sum up the chat. Switch to Claude, Codex or Antigravity, then type /compact.');
    if (chatSoFar(true).length < 2) return note('Nothing to compact yet.');
    send(COMPACT_PROMPT, { compact: true });
  }

  // What the agents get as the chat so far: from the last /compact summary on, without TuffCode's own notes,
  // "Test it" runs, or a reply still being written. all: including the newest message.
  function chatSoFar(all = false) {
    const msgs = all ? S.msgs : S.msgs.slice(0, -1);
    const from = msgs.map((m) => !!m.summary).lastIndexOf(true);
    return msgs.slice(Math.max(0, from)).filter((m) => m.role !== 'note' && !m.test && !(m.compacting && !m.summary) && (m.role === 'user' || m.status !== 'running'));
  }

  function renderMode() {
    // Tuff AI only answers: it doesn't change files itself (its code gets an Apply button).
    const local = !!current()?.local;
    const mode = local ? 'ask' : S.mode;
    $$('.ta-mode button', root).forEach((b) => {
      b.classList.toggle('on', b.dataset.m === mode);
      b.setAttribute('aria-checked', b.dataset.m === mode);
      b.disabled = local && b.dataset.m !== 'ask';
    });
    $('.ta-hint', root).textContent = mode === 'edit' ? 'Can change your files' : mode === 'plan' ? 'Plans first, changes nothing yet' : "Won't change your files";
    $('textarea', root).placeholder = mode === 'edit' ? 'Tell the agent what to change…' : mode === 'plan' ? 'What should the agent plan?' : 'Ask about your code…';
  }

  function renderStatus() {
    const box = $('.ta-status', root);
    const a = current();
    if (!S.agents) { box.innerHTML = `<div class="ta-note">Looking for AI agents on this ${document.documentElement.classList.contains('mac') ? 'Mac' : 'PC'}…</div>`; return; }
    if (a?.local && !a.installed) {
      box.innerHTML = aiCard();
    } else if (!a?.installed) {
      box.innerHTML = `<div class="ta-card">
        <b class="ta-card-h">${esc(a?.name || S.agent)} isn't installed</b>
        <p>Install it once, then come back. TuffCode runs it for you right here.${INSTALL_TIP[S.agent] || ''}</p>
        <div class="ta-cmd"><code>${esc(a?.install || '')}</code><button data-a="copy-install">Copy</button></div>
        <div class="ta-btns"><button class="btn sm" data-a="site">Website</button><button class="btn sm" data-a="recheck">Check again</button></div>
      </div>`;
    } else if (S.auth[S.agent] === false) {
      box.innerHTML = `<div class="ta-card">
        <b class="ta-card-h">Sign in to ${esc(a.name)}</b>
        <p>${signInText(a)} A window opens and your browser does the rest.</p>
        <div class="ta-btns"><button class="btn sm primary" data-a="signin">Sign in</button><button class="btn sm" data-a="recheck">Check again</button></div>
      </div>`;
    } else if (CLI.includes(S.agent) && S.agent !== 'claude' && S.conn[S.agent] === false && !S.dismissed[S.agent]) {
      box.innerHTML = `<div class="ta-card">
        <b class="ta-card-h">Teach ${esc(a.name)} about Tuff</b>
        <p>Connect TuffCode's tools so ${esc(a.name)} can read the Tuff guide and check and run your programs. This adds a "tuffcode" tool server to its settings${S.agent === 'antigravity' ? ' and lets it use those tools without asking' : ''}. You can remove it any time from the ⋯ menu.</p>
        <div class="ta-btns"><button class="btn sm primary" data-a="connect">Connect</button><button class="btn sm" data-a="setup">How it works</button><button class="btn sm" data-a="dismiss">Not now</button></div>
      </div>`;
    } else {
      box.innerHTML = '';
    }
    box.onclick = async (e) => {
      const act = e.target.closest('button')?.dataset.a;
      if (act === 'copy-install') { navigator.clipboard.writeText(a.install); t.toast('Copied. Paste it in a terminal.', 'ok', 2500); }
      if (act === 'site') t.openExternal(a.url);
      if (act === 'recheck') refreshAgents();
      if (act === 'dismiss') { S.dismissed[S.agent] = true; t.storage.set('dismissed', S.dismissed); renderStatus(); }
      if (act === 'connect') connect(true);
      if (act === 'setup') showSetup(true);
      if (act === 'signin') signInAgent(S.agent);
      if (act === 'ai-get') {
        S.aiProg = { got: 0, total: S.ai?.models[0]?.size || 0, done: false };
        renderStatus();
        t.agents.ai.download(S.ai?.models[0]?.id).catch(() => {});
      }
      if (act === 'ai-cancel') t.agents.ai.cancel();
    };
  }

  // Tuff AI before its model is downloaded: what it is, what it needs, and the download.
  function aiCard() {
    const s = S.ai;
    if (!s) return '<div class="ta-note">Checking Tuff AI…</div>';
    if (!s.runtime) return '<div class="ta-card"><b>Tuff AI isn\'t in this copy of TuffCode</b><p>Its engine wasn\'t included. Update TuffCode to get it.</p></div>';
    const m = s.models[0];
    const p = S.aiProg && !S.aiProg.done ? S.aiProg : null;
    if (p) {
      const pct = p.total ? Math.floor((100 * p.got) / p.total) : 0;
      return `<div class="ta-card ta-ai"><b class="ta-card-h">Downloading ${esc(m.name)}… ${pct}%</b>
        <div class="ta-prog"><i style="width:${pct}%"></i></div>
        <p>${GB(p.got)} of ${GB(p.total)}. You can keep coding. If it stops, it carries on from here next time.</p>
        <div class="ta-btns"><button class="btn sm" data-a="ai-cancel">Stop</button></div></div>`;
    }
    const low = s.ram.free < s.ram.need;
    return `<div class="ta-card ta-ai">
      <b class="ta-card-h">Tuff AI <span class="ta-tag">preview</span></b>
      <p>Runs on this computer: no account, and no internet once it's downloaded. Its model is ${esc(m.name)}, TuffCode's own. It isn't trained on Tuff yet, so expect mistakes. TuffCode checks every program it writes.</p>
      <div class="ta-chips">
        <span>${icon('cloud')}Download: ${GB(m.size)}</span>
        <span class="${low ? 'ta-warn' : ''}">${icon('chip')}Needs ${GB(s.ram.need)} free memory</span>
        <span>${icon('offline')}Works offline</span>
      </div>
      <p class="${low ? 'ta-warn' : 'tas-small'}">It needs about ${GB(s.ram.need)} of free memory while it answers (${GB(s.ram.free)} free right now${low ? '. Close some apps first' : ''}).</p>
      ${m.base ? `<p class="tas-small ta-credit">${esc(m.name)} · based on ${esc(m.base)}${m.licence ? ` (${esc(m.licence)})` : ''}</p>` : ''}
      <div class="ta-btns"><button class="btn sm primary" data-a="ai-get">Download ${esc(m.name)} (${GB(m.size)})</button><button class="btn sm" data-a="recheck">Check again</button></div>
    </div>`;
  }

  async function connect(on, id = S.agent) {
    const a = S.agents?.find((x) => x.id === id);
    if (!a) return;
    try {
      const c = await t.agents.connect(a.id, on);
      S.conn[a.id] = c.connected;
      t.toast(on ? `${a.name} can now use TuffCode's Tuff tools.` : `Removed TuffCode's tools from ${a.name}.`, 'ok');
    } catch (err) {
      t.toast(cleanErr(err), 'error', 7000);
    }
    renderStatus();
  }

  function toggleMenu() {
    const m = $('.ta-menu', root);
    const a = current();
    const items = [['new', 'New chat'], ['setup', 'Agent tools: set up and check']];
    if (a?.local && a.installed) items.push(['ai-remove', `Delete ${S.ai?.models[0]?.name || "Tuff AI's model"} (${GB(S.ai?.models[0]?.size || 0)})`]);
    else if (a?.installed) items.push(S.conn[a.id] ? ['disconnect', `Remove TuffCode tools from ${a.name}`] : ['connect', `Add TuffCode tools to ${a.name}${a.id === 'claude' ? ' everywhere' : ''}`]);
    items.push(['recheck', 'Look for agents again']);
    m.innerHTML = items.map(([id, label]) => `<button data-m="${id}">${esc(label)}</button>`).join('');
    m.classList.toggle('hidden');
    m.onclick = (e) => {
      const id = e.target.closest('button')?.dataset.m;
      m.classList.add('hidden');
      if (id === 'new') newChat();
      if (id === 'setup') showSetup(true);
      if (id === 'connect') connect(true);
      if (id === 'disconnect') connect(false);
      if (id === 'recheck') refreshAgents();
      if (id === 'ai-remove') t.ask({ title: `Delete ${S.ai?.models[0]?.name || 'the model'}, Tuff AI's model? You can download it again later.`, confirm: true, okLabel: 'Delete' }).then((ok) => ok && t.agents.ai.remove(S.ai?.models[0]?.id).then(refreshAgents));
    };
  }

  // ---------------------------------------------------------------- agent tools: set up and check (MCP)
  function showSetup(on) {
    S.view = on ? 'setup' : 'chat';
    for (const sel of ['.ta-status', '.ta-msgs', '.ta-compose']) $(sel, root).classList.toggle('hidden', on);
    $('.ta-setup', root).classList.toggle('hidden', !on);
    $('[data-a="setup"]', root).classList.toggle('on', on);
    if (!on) { setTimeout(() => $('textarea', root)?.focus(), 30); return; }
    renderSetup();
    if (!S.setup) t.agents.mcpSetup().then((x) => { S.setup = x; renderSetup(); }).catch(() => {});
    for (const a of (S.agents || []).filter((x) => x.installed)) {
      t.agents.connection(a.id).then((c) => { S.conn[a.id] = c.connected; renderSetup(); renderStatus(); }).catch(() => {});
    }
    if (!S.check) runCheck();
  }

  async function runCheck() {
    S.check = { running: true };
    renderSetup();
    try {
      S.check = await t.agents.mcpCheck();
    } catch (err) {
      S.check = { ok: false, steps: [{ id: 'start', ok: false, detail: cleanErr(err), ms: 0 }] };
    }
    renderSetup();
  }

  function testAgent(id) {
    if (S.run) { t.toast('Wait until the agent has finished first.'); return; }
    S.agent = id;
    t.storage.set('agent', id);
    showSetup(false);
    renderAgents();
    renderStatus();
    send(TEST_PROMPT, { test: true });
  }

  function renderSetup() {
    if (S.view !== 'setup' || !root) return;
    const box = $('.ta-setup', root);
    const scroll = box.scrollTop;
    const c = S.check;
    const steps = c?.running
      ? '<li class="run"><i></i><div><b>Checking…</b><span>Starting the tools the way your agents do.</span></div></li>'
      : (c?.steps || []).map((st) => `<li class="${st.ok ? 'ok' : 'bad'}"><i></i><div><b>${esc(STEPS[st.id] || 'Check')}</b>`
        + `<span>${esc(st.detail)}${st.ms >= 500 ? ` (${(st.ms / 1000).toFixed(1)} s)` : ''}</span></div></li>`).join('');
    const verdict = !c || c.running ? ''
      : c.ok ? '<p class="tas-ok">All good. Every agent connected below can use these tools.</p>'
        : "<p class=\"tas-bad\">Something isn't working. The red step says what went wrong. If it keeps happening, reinstall TuffCode.</p>";
    box.innerHTML = `
      <div class="tas-head"><button class="ta-ib" data-s="back" title="Back to the chat">←</button><b>Agent tools</b></div>
      <p class="tas-intro">AI agents learn Tuff from TuffCode's tools: the Tuff guide, example apps, a checker and a runner. They plug in through <b>MCP</b>, the standard way AI agents use tools.</p>
      <section>
        <h4><span>1</span>Check the tools work</h4>
        <p>Starts TuffCode's tools exactly the way your agents do, then tries every one.</p>
        <button class="btn sm primary" data-s="check"${c?.running ? ' disabled' : ''}>${c && !c.running ? 'Check again' : 'Run the check'}</button>
        ${steps ? `<ol class="tas-steps">${steps}</ol>` : ''}${verdict}
      </section>
      <section>
        <h4><span>2</span>Connect your agents</h4>
        ${CLI.map(agentSetupHtml).join('')}
      </section>
      <section>
        <h4><span>3</span>Or set it up by hand</h4>
        <p>For an agent you use in a terminal, or another app. Paste a command into ${document.documentElement.classList.contains('mac') ? 'Terminal' : 'Command Prompt or PowerShell'}.</p>
        ${manualHtml()}
      </section>`;
    box.scrollTop = scroll;
  }

  function agentSetupHtml(id) {
    const a = S.agents?.find((x) => x.id === id);
    const name = a?.name || NAME[id];
    const conn = S.conn[id];
    let state = 'Looking…';
    let ok = false;
    let body = '';
    let btns = [];
    if (S.agents && !a?.installed) {
      state = 'Not installed';
      body = `<p>Install it once, then come back here.${INSTALL_TIP[id] || ''}</p><div class="ta-cmd"><code>${esc(a?.install || '')}</code><button data-copy="${esc(a?.install || '')}">Copy</button></div>`;
      btns = [['site', 'Website']];
    } else if (a?.installed && S.auth[id] === false) {
      state = 'Not signed in';
      body = `<p>${signInText(a)}</p>`;
      btns = [['signin', 'Sign in', 'primary'], ['recheck', 'Check again']];
    } else if (a?.installed && id === 'claude') {
      ok = true;
      state = conn ? 'Ready here, in the Claude app and the terminal' : 'Ready in this panel';
      body = `<p>Claude gets the tools automatically in this panel. ${conn ? 'They’re also added to the Claude app (chat and Code tab) and <code>claude</code> in your terminal. Restart the Claude app if it doesn’t show “tuffcode” yet.' : 'Add them to the Claude app (chat and Code tab) and <code>claude</code> in your terminal too. Restart the Claude app afterwards.'}</p>`;
      btns = [['test', 'Test it', 'primary'], conn ? ['off', 'Remove from the Claude app'] : ['on', 'Add to the Claude app']];
    } else if (a?.installed) {
      ok = !!conn;
      state = conn === undefined ? 'Checking…' : conn ? 'Connected' : 'Not connected';
      const where = id === 'codex' ? 'here, in the Codex app and in your terminal. Restart the Codex app if it doesn’t show “tuffcode” yet' : 'here and in your terminal';
      body = conn ? `<p>${esc(name)} can use the Tuff tools ${where}.</p>`
        : `<p>Connect once so ${esc(name)} can read the Tuff guide and check and run your programs${id === 'codex' ? ', here and in the Codex app' : ''}. This adds a "tuffcode" tool server to its settings${id === 'antigravity' ? ' and lets it use those tools without asking' : ''}.</p>`;
      btns = conn ? [['test', 'Test it', 'primary'], ['off', 'Remove']] : conn === false ? [['on', 'Connect', 'primary']] : [];
    }
    const test = S.tested[id];
    return `<div class="tas-agent" data-id="${id}">
      <div class="tas-ah"><i class="dot${a?.installed ? ' ready' : ''}"></i><b>${esc(name)}</b><span class="tas-state${ok ? ' ok' : ''}">${esc(state)}</span></div>
      ${body}
      ${btns.length ? `<div class="ta-btns">${btns.map(([act, label, cls]) => `<button class="btn sm${cls ? ` ${cls}` : ''}" data-s="${act}" data-id="${id}"${S.busyAgent === id || (act === 'test' && S.run) ? ' disabled' : ''}>${esc(label)}</button>`).join('')}</div>` : ''}
      ${test ? `<div class="tas-test ${test.ok ? 'ok' : 'bad'}">${esc(test.text)}</div>` : ''}
    </div>`;
  }

  function manualHtml() {
    const m = S.setup;
    if (!m) return '<p>Loading…</p>';
    const cmd = (c, cls = '') => `<div class="ta-cmd${cls}"><code>${esc(c)}</code><button data-copy="${esc(c)}">Copy</button></div>`;
    const part = (key, title, inner) => `<details class="tas-man" data-m="${key}"${S.openMan.has(key) ? ' open' : ''}><summary>${esc(title)}</summary><div>${inner}</div></details>`;
    return CLI.map((id) => part(id, NAME[id], `
        <p>1. Add TuffCode's tools:</p>${cmd(m.agents[id].add)}
        <p>2. Check they're there:</p>${cmd(m.agents[id].check)}
        <p>3. Ask ${esc(NAME[id])}: <i>“Use the tuff_reference tool, then make me a small Tuff app.”</i> If it reads the Tuff guide first, it's working.</p>
        <p class="tas-small">To remove them: <code>${esc(m.agents[id].remove)}</code></p>`)).join('')
      + part('other', 'Other apps (Claude Desktop, Cursor, Windsurf…)', `
        <p>Add this to the app's MCP settings file, for example <code>claude_desktop_config.json</code> or <code>.cursor/mcp.json</code>, then restart the app. In VS Code's <code>mcp.json</code>, write <code>"servers"</code> instead of <code>"mcpServers"</code>.</p>
        ${cmd(m.json, ' tall')}`)
      + '<p class="tas-small">These paths point at this copy of TuffCode. If you move or reinstall it, connect again or copy the new commands.</p>';
  }

  async function onSetupClick(e) {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    if (b.dataset.copy !== undefined) { navigator.clipboard.writeText(b.dataset.copy); t.toast('Copied. Paste it in a terminal.', 'ok', 2500); return; }
    const id = b.dataset.id;
    switch (b.dataset.s) {
      case 'back': showSetup(false); break;
      case 'check': runCheck(); break;
      case 'test': testAgent(id); break;
      case 'signin': signInAgent(id); break;
      case 'recheck': refreshAgents(); break;
      case 'site': t.openExternal(S.agents?.find((x) => x.id === id)?.url); break;
      case 'on':
      case 'off':
        S.busyAgent = id;
        renderSetup();
        await connect(b.dataset.s === 'on', id);
        S.busyAgent = null;
        renderSetup();
        break;
      default: break;
    }
  }

  // ---------------------------------------------------------------- context chips
  function updateCtx() {
    if (!root) return;
    const box = $('.ta-ctx', root);
    const file = t.editor.file();
    const lines = t.editor.selectionLines();
    const chips = [];
    if (file) chips.push(`<button class="${S.useFile ? 'on' : ''}" data-c="file" title="Send this file with your message">${esc(short(file))}</button>`);
    if (lines) chips.push(`<button class="${S.useSel ? 'on' : ''}" data-c="sel" title="Send the selected lines too">Lines ${lines[0]}${lines[1] !== lines[0] ? `–${lines[1]}` : ''}</button>`);
    const html = chips.join('');
    if (box.dataset.html !== html) {
      box.dataset.html = html;
      box.innerHTML = html;
      $$('button', box).forEach((b) => (b.onclick = () => {
        if (b.dataset.c === 'file') S.useFile = !S.useFile;
        else S.useSel = !S.useSel;
        box.dataset.html = '';
        updateCtx();
      }));
    }
  }

  // ---------------------------------------------------------------- messages
  function renderMsgs() {
    const box = $('.ta-msgs', root);
    if (!S.msgs.length) {
      const a = current();
      box.innerHTML = `<div class="ta-empty">
        <div class="ta-empty-ic"></div>
        <b>Ask ${esc(a?.name || 'an agent')} anything about your Tuff code</b>
        <span>${a?.local ? 'It runs on this computer and checks the code it writes. Its code gets an <b>Apply</b> button.' : 'It can see the file you have open. Switch to <b>Edit</b> to let it change files for you.'}</span>
        <div class="ta-sugg">${SUGGEST.map(([label, , ic, sub], i) => `<button data-s="${i}">${icon(ic)}<span><b>${esc(label)}</b><small>${esc(sub)}</small></span></button>`).join('')}</div>
        <button class="ta-link" data-setup>${PLUG}Set up and check agent tools</button>
      </div>`;
      return;
    }
    box.innerHTML = S.msgs.map((m, i) => msgHtml(m, i)).join('');
    colorize(box);
    box.scrollTop = box.scrollHeight;
  }

  function msgHtml(m, i) {
    // Messages before the latest /compact summary stay visible, faded: agents now get the summary instead.
    const old = i < S.msgs.map((x) => !!x.summary).lastIndexOf(true) ? ' ta-old' : '';
    if (m.role === 'note') return `<div class="ta-msg note${old}" data-i="${i}"><div class="ta-notebox">${esc(m.text)}</div></div>`;
    if (m.role === 'user') {
      return `<div class="ta-msg user${old}" data-i="${i}"><div class="ta-bubble">${esc(m.text).replace(/\n/g, '<br>')}</div>${m.ctx ? `<div class="ta-with">${esc(m.ctx)}</div>` : ''}</div>`;
    }
    const tools = m.tools.map((x) => `<div class="ta-tool ${x.ok === false ? 'bad' : x.ok ? 'ok' : 'run'}">${toolIcon(x.text)}<span>${esc(x.text)}</span><i></i></div>`).join('');
    const typing = (label, tag = 'div') => `<${tag} class="ta-typing"><i></i><i></i><i></i><span>${esc(label)}</span></${tag}>`;
    // While it thinks, the thinking's own fold carries the "Thinking…" label instead.
    const thinking = m.status === 'running' && !!m.thinkFrom;
    const status = m.status === 'running' ? (thinking ? '' : typing(m.stage || (m.text ? 'Writing' : m.tools.length ? 'Working' : 'Thinking')))
      : m.status === 'stopped' ? '<div class="ta-small ta-stopped">Stopped.</div>'
        : m.status === 'error' ? `<div class="ta-err">${icon('warn')}<span>${esc(m.error)}</span></div>` : '';
    const notes = (m.notes || []).map((n) => `<div class="ta-small ta-note-l">${icon('info')}<span>${esc(n)}</span></div>`).join('');
    return `<div class="ta-msg agent${m.status === 'running' ? ' live' : ''}${m.summary ? ' summary' : ''}${old}" data-i="${i}">
      <div class="ta-head"><div class="ta-who">${m.summary ? '<span class="ta-who-s">Chat summary · </span>' : ''}<span class="ta-who-n">${esc(SHORT[m.agent])}</span>${m.model ? `<span class="ta-who-m"> · ${esc(m.model)}</span>` : ''}${m.mode === 'edit' ? '<span class="ta-who-e"> · Edit</span>' : m.mode === 'plan' ? '<span class="ta-who-p"> · Plan</span>' : ''}</div></div>
      <div class="ta-body">${foldsHtml(m, thinking, typing)}${tools ? `<div class="ta-tools">${tools}</div>` : ''}
      <div class="ta-md">${md(m.text)}</div>${notes}${status}${followUp(m, i)}</div></div>`;
  }

  // Tuff AI's request as the improver rewrote it (with its own plan at Medium and High), and its thinking.
  // Both start folded; the reply remembers which ones you opened.
  function foldsHtml(m, thinking, typing) {
    const fold = (key, cls, summary, body) => `<details class="ta-fold ${cls}" data-fold="${key}"${m.open?.[key] ? ' open' : ''}><summary>${summary}</summary><div class="ta-fold-b">${body}</div></details>`;
    const out = [];
    if (m.improved) {
      const plan = String(m.plan || '').replace(/(```|\*\*Answer|Answer:)[\s\S]*$/, '').trim();
      // The model reads "```tuff block"; people read "Tuff code block".
      out.push(fold('improved', 'ta-improved', `${icon('spark')}<span>Made your request clearer</span>`,
        `${prose(m.improved.replace(/```tuff (block|example)/g, 'Tuff code $1'))}${plan ?`<div class="ta-fold-h">${esc(m.name || 'Pumice 1')} rewrote it as</div>${prose(plan)}` : ''}`));
    }
    if (m.thought) {
      const secs = Math.max(1, Math.round((m.thinkMs || 0) / 1000));
      out.push(fold('thought', 'ta-thought', thinking ? typing('Thinking…', 'span') : `${icon('bulb')}<span>Thought for ${secs} s</span>`, esc(m.thought.trim())));
    }
    return out.join('');
  }

  // Under the latest reply: Plan answers get "Go ahead", and an Ask answer that offers a change (code, or
  // "want me to…?") gets "Edit it for me". Both send one message in Edit mode; the chosen mode stays.
  // They go to the selected agent, so they only show while the agent that wrote the reply is selected.
  const offersChange = (text) => /```/.test(text || '') || /\b(want|like) me to\b|\b(shall|should) I\b|make (that|this|the|these) changes?/i.test(text || '');
  function followUp(m, i) {
    if (i !== S.msgs.length - 1 || m.test || S.run || m.status !== 'done' || !CLI.includes(m.agent) || m.agent !== S.agent) return '';
    const act = m.mode === 'plan' ? ['go', 'Go ahead', 'The agent makes the planned changes'] : m.mode !== 'edit' && offersChange(m.text) ? ['do-edit', 'Edit it for me', 'The agent makes this change in your files'] : null;
    return act ? `<div class="ta-acts"><button class="btn sm primary" data-act="${act[0]}">${act[1]}</button><span>${act[2]}</span></div>` : '';
  }

  function rerender(m) {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const box = $('.ta-msgs', root);
      const i = S.msgs.indexOf(m);
      const el = box.querySelector(`.ta-msg[data-i="${i}"]`);
      const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
      if (el) el.outerHTML = msgHtml(m, i); else renderMsgs();
      colorize(box);
      if (atBottom) box.scrollTop = box.scrollHeight;
    });
  }

  function onMsgClick(e) {
    if (e.target.closest('[data-setup]')) { showSetup(true); return; }
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'go') { send('Go ahead with the plan.', { mode: 'edit' }); return; }
    if (act === 'do-edit') { send('Yes please, make that change for me.', { mode: 'edit' }); return; }
    const s = e.target.closest('[data-s]');
    if (s) { send(SUGGEST[+s.dataset.s][1]); return; }
    const a = e.target.closest('.ta-a');
    if (a) {
      e.preventDefault();
      if (a.dataset.file) t.openFile(a.dataset.file, +a.dataset.line || 0);
      else if (a.dataset.url) {
        const url = a.dataset.url;
        t.ask({ title: `Open ${url.length > 90 ? url.slice(0, 87) + '…' : url} in your web browser?`, confirm: true, okLabel: 'Open' }).then((ok) => ok && t.openWeb(url));
      }
      return;
    }
    const b = e.target.closest('[data-code]');
    if (!b) return;
    const code = decodeURIComponent(b.closest('.ta-code').dataset.src || '');
    if (b.dataset.code === 'copy') { navigator.clipboard.writeText(code); t.toast('Copied.', 'ok', 1500); }
    if (b.dataset.code === 'insert') t.editor.insert(code);
    if (b.dataset.code === 'apply') {
      const file = t.editor.file();
      if (!file) { t.toast('Open the file to change first.', 'error'); return; }
      t.ask({ title: `Replace all of ${short(file)} with this code? Ctrl+Z undoes it.`, confirm: true, okLabel: 'Replace' }).then((ok) => ok && t.editor.replaceAll(code));
    }
  }

  // Small markdown: code blocks (with Copy / Insert), and prose() for everything between them.
  function md(src) {
    if (!src) return '';
    const parts = [];
    const re = /```([\w+-]*)[^\n]*\n?([\s\S]*?)(?:```|$)/g;
    let last = 0;
    let m;
    while ((m = re.exec(src))) {
      parts.push(prose(src.slice(last, m.index)));
      const code = m[2].replace(/\n$/, '');
      const lang = (m[1] || '').toLowerCase() || (/^\s*(say|mention|import|func)\b/m.test(code) ? 'tuff' : '');
      const html = lang === 'tuff' && lit.has(code) ? lit.get(code) : esc(code);
      parts.push(`<div class="ta-code" data-lang="${esc(lang || 'code')}" data-src="${encodeURIComponent(code)}"><div class="ta-code-h"><span class="ta-lang"><i></i>${esc(lang === 'tuff' ? 'Tuff' : lang || 'code')}</span><button data-code="copy" title="Copy">${icon('copy')}Copy</button><button data-code="insert" title="Insert at the cursor in the editor">${icon('insert')}Insert</button>${/^(tuff)?$/i.test(lang) && t.editor.replaceAll ? `<button data-code="apply" class="ta-apply" title="Replace the open file with this code">${icon('apply')}Apply</button>` : ''}</div><pre><code${html !== esc(code) ? ' class="lit"' : ''}>${html}</code></pre></div>`);
      last = re.lastIndex;
      if (m.index === re.lastIndex) break;
    }
    parts.push(prose(src.slice(last)));
    return parts.join('');
  }

  // One line of text: `code`, [links](…), <web addresses>, **bold**, *italics*, ~~struck~~ and \escapes.
  // Escapes and code spans are read first, left to right as Markdown does: \` is a backtick, and a
  // backslash inside `code` is just a backslash. Then links, then styles. Each becomes a placeholder
  // (NUL n NUL, or SOH n SOH for an escape), so its inside isn't read again. A link's text is styled on its
  // own, so `code` and **bold** work there too, and its address is read as it was written.
  function inline(s) {
    const keep = [];
    const raw = [];
    const hold = (html, src = '', mark = '\u0000') => { raw.push(src); return `${mark}${keep.push(html) - 1}${mark}`; };
    // A link's address as written. In a web address \_ means _ (a URL has no backslashes), but in a file
    // path a backslash is a folder separator (C:\Users\_drafts), so it stays.
    const address = (h) => {
      const web = /^\s*https?:/i.test(h);
      return h.replace(/([\u0000\u0001])(\d+)\1/g, (_, mark, i) => (web && mark === '\u0001' ? raw[+i].slice(1) : raw[+i]));
    };
    const style = (x, links) => {
      // Addresses can hold (balanced) brackets, like https://en.wikipedia.org/wiki/Tuff_(rock), but a bare
      // one ends before a lone ")" (see https://x.com), a full stop, or the ** of **https://x.com**.
      if (links) x = x
        .replace(/!?\[([^\]]+)\]\(\s*(?:<([^>]+)>|((?:[^()\s]|\([^()\s]*\))+))(?:\s+"[^"]*")?\s*\)/g, (_, text, inAngles, href) => hold(link(style(text, false), address(inAngles || href))))
        .replace(/<((?:https?|file):\/\/[^>\s\u0000]+)>/gi, (_, href) => { const to = address(href); return hold(link(esc(to), to)); })
        .replace(/(?<![a-z\d])https?:\/\/(?:[^\s<>()"'`\u0000]|\([^\s<>()"'`\u0000]*\))*(?:[^\s<>()"'`\u0000.,;:!?*~]|\([^\s<>()"'`\u0000]*\))/gi, (m, at, all) => {
          // _https://x.com_ and __https://x.com__: the closing underscores are style, not address.
          const u = m.match(/_+$/)?.[0] || '';
          const tail = u && all.slice(0, at).endsWith(u) ? u : '';
          const to = address(m.slice(0, m.length - tail.length));
          return hold(link(esc(to), to)) + tail;
        });
      return esc(x)
        .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
        .replace(/(^|[^\w])__([^_]+)__(?=$|[^\w])/g, '$1<b>$2</b>')
        .replace(/~~([^~]+)~~/g, '<s>$1</s>')
        .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>')
        .replace(/(^|[\s(])_([^_\s][^_]*)_(?=$|[\s).,;:!?])/g, '$1<i>$2</i>');
    };
    let out = style(String(s).replace(/[\u0000\u0001]/g, '')
      .replace(/\\([\\`*_[\]()#+\-.!~|>])|`([^`]+)`/g, (m, c, code) => (c ? hold(esc(c), m, '\u0001') : hold(`<code>${esc(code)}</code>`, m))), true);
    // A link holds its text, which can hold code: put them back until none are left.
    while (/([\u0000\u0001])\d+\1/.test(out)) out = out.replace(/([\u0000\u0001])(\d+)\1/g, (_, mark, i) => keep[+i]);
    return out;
  }

  // A link in a reply, around label (HTML, already styled). Files (file:///…, a path, "main.tuf:12") open
  // in the editor, at the line if one is given; ones outside the project ask first (fileQuestion). Web
  // pages (http and https only) ask first, because they open in the browser. Anything else (javascript:,
  // data:…) is shown as plain text.
  function link(label, href) {
    const to = linkTarget(href);
    if (!to) return label;
    if (to.url) return `<a class="ta-a web" data-url="${esc(to.url)}" title="${esc(to.url)}">${label}</a>`;
    return `<a class="ta-a file" data-file="${esc(to.file)}"${to.line ? ` data-line="${to.line}"` : ''} title="Open ${esc(short(to.file))}${to.line ? `, line ${to.line}` : ''}">${label}</a>`;
  }

  function linkTarget(href) {
    let h = String(href || '').trim();
    if (/^https?:\/\/[^/\s]/i.test(h)) return { url: h };
    let line = 0;
    const hash = h.match(/#L?(\d+)(?:[-:]L?\d+)?$/i);
    if (hash) { line = +hash[1]; h = h.slice(0, hash.index); }
    const lc = !line && h.match(/^(.*\.\w+):(\d+)(?::\d+)?$/); // main.tuf:12 or main.tuf:12:5
    if (lc) { h = lc[1]; line = +lc[2]; }
    if (/^file:\/\//i.test(h)) {
      try { h = decodeURIComponent(h.replace(/^file:\/\/(localhost)?/i, '')); } catch { return null; }
      if (/^\/[a-z]:[\\/]/i.test(h)) h = h.slice(1); // file:///C:/… → C:/…
    } else if (/^[a-z][\w+.-]*:/i.test(h) && !/^[a-z]:[\\/]/i.test(h)) return null; // another scheme, not a drive
    if (!h || h.startsWith('#')) return null;
    const root = t.project.root();
    const abs = /^([a-z]:[\\/]|[\\/])/i.test(h);
    if (!abs && !root) return null;
    let file = abs ? h : `${root.replace(/[\\/]+$/, '')}/${h.replace(/^\.[\\/]/, '')}`;
    // One kind of slash, the one the project uses, so an open tab is found again instead of opened twice.
    if (/^[a-z]:/i.test(file) || (root || '').includes('\\')) file = file.replace(/\//g, '\\');
    return { file, line };
  }

  // Lines of text between code blocks: headings, lists (numbered ones keep their numbers, indented items
  // are a list inside the item above), tables, > quotes, --- lines and paragraphs.
  function prose(text) {
    const out = [];
    // The list being read: lists[0] is the outer one, the last is the one the next item may join. An
    // indented item starts a list inside the item above it, so the outer numbers still count 1, 2, 3.
    let lists = [];
    let para = [];
    let quote = [];
    const flushPara = () => { if (para.length) out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = []; };
    const flushQuote = () => { if (quote.length) out.push(`<blockquote>${quote.map(inline).join('<br>')}</blockquote>`); quote = []; };
    const listHtml = (l) => `<${l.tag}${l.start > 1 ? ` start="${l.start}"` : ''}>${l.items.map((x) => `<li>${x.lines.map(inline).join('<br>')}${x.kids.map(listHtml).join('')}</li>`).join('')}</${l.tag}>`;
    const flushList = () => {
      if (lists.length) out.push(listHtml(lists[0]));
      lists = [];
    };
    const flush = () => { flushPara(); flushQuote(); flushList(); };
    const cells = (row) => row.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((c) => c.trim());
    const lines = text.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trimEnd();
      let m;
      if (!line.trim()) { flush(); continue; }
      // A table: a row of | cells, then a |---|---| line.
      if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(lines[i + 1] || '')) {
        flush();
        const head = cells(line);
        const rows = [];
        for (i += 2; i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i]); i++) rows.push(cells(lines[i]));
        i--;
        out.push(`<div class="ta-table"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${head.map((_, k) => `<td>${inline(r[k] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
        continue;
      }
      if ((m = line.match(/^(#{1,6})\s+(.*)$/))) { flush(); out.push(`<h4>${inline(m[2].replace(/\s#+$/, ''))}</h4>`); continue; }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); out.push('<hr>'); continue; }
      if ((m = line.match(/^\s*>\s?(.*)$/))) { flushPara(); flushList(); quote.push(m[1]); continue; }
      flushQuote();
      if ((m = line.match(/^(\s*)(?:[-*+•]|(\d+)[.)])\s+(.*)$/))) {
        flushPara();
        const indent = m[1].length;
        const tag = m[2] ? 'ol' : 'ul';
        const fresh = () => ({ tag, start: m[2] ? +m[2] : 1, indent, items: [] });
        // Out of the inner lists this item is left of ("2. Step two" after its indented bullets).
        while (lists.length > 1 && indent < lists[lists.length - 1].indent - 1) lists.pop();
        let l = lists[lists.length - 1];
        if (l && indent >= l.indent + 2) {
          // Indented under the item above: a list inside that item, numbered or not as its own items are.
          const inner = fresh();
          l.items[l.items.length - 1].kids.push(inner);
          lists.push((l = inner));
        } else if (l && l.tag !== tag) {
          if (lists.length === 1) { flushList(); l = null; } else {
            // Bullets after numbers (or the other way) inside an item: a new list next to the first.
            const inner = fresh();
            const above = lists[lists.length - 2];
            above.items[above.items.length - 1].kids.push(inner);
            lists[lists.length - 1] = l = inner;
          }
        }
        if (!l) lists = [(l = fresh())];
        l.items.push({ lines: [m[3]], kids: [] });
        continue;
      }
      // An indented line under a list item belongs to that item (the innermost one).
      if (lists.length && /^\s{2,}\S/.test(line)) { const l = lists[lists.length - 1]; l.items[l.items.length - 1].lines.push(line.trim()); continue; }
      flushList();
      para.push(line);
    }
    flush();
    return out.join('');
  }

  // ---------------------------------------------------------------- running
  function describeTool(name, input = {}) {
    const n = String(name || '').replace(/^mcp__tuffcode__/, '');
    const file = short(input.file_path || input.path || input.file || input.notebook_path);
    const map = {
      Read: `Read ${file || 'a file'}`,
      Edit: `Changed ${file || 'a file'}`,
      MultiEdit: `Changed ${file || 'a file'}`,
      Write: `Wrote ${file || 'a file'}`,
      Bash: `Ran ${String(input.command || 'a command').slice(0, 70)}`,
      Glob: 'Looked through the project',
      Grep: 'Searched the project',
      LS: 'Looked through the project',
      WebSearch: 'Searched the web',
      WebFetch: 'Read a web page',
      TodoWrite: 'Planned the steps',
      tuff_reference: 'Read the Tuff guide',
      tuff_examples: 'Looked at Tuff examples',
      tuff_check: `Checked ${input.file ? short(input.file) : 'the code'} for mistakes`,
      tuff_run: `Ran ${input.file ? short(input.file) : 'the program'}`,
    };
    return { text: map[n] || n.replace(/^mcp__\w+?__/, ''), changes: /^(Edit|MultiEdit|Write|NotebookEdit)$/.test(n) };
  }

  // Tuff AI is a small model that reads slowly on a laptop CPU, so it gets a short prompt. The panel sends
  // the question's parts, and ai.js turns them into a clearer task (the improver), with the Tuff guide's
  // basics and the sections that match.
  function aiParts(text) {
    const parts = { question: text };
    const file = t.editor.file();
    if (file && S.useFile) Object.assign(parts, { file: short(file), code: String(t.editor.code() ?? '').slice(0, 60000) });
    const lines = t.editor.selectionLines();
    if (S.useSel && lines) parts.selection = { from: lines[0], to: lines[1], text: t.editor.selection() };
    const err = file && S.useFile ? lastRunError(parts.code) : '';
    if (err) parts.runError = err;
    const earlier = chatSoFar().slice(-6);
    const said = [];
    let used = 0;
    for (let i = earlier.length - 1; i >= 0; i--) {
      const m = earlier[i];
      const l = m.summary ? `Summary of the chat before this: ${trim(m.text, 1200)}` : `${m.role === 'user' ? 'Them' : m.agent === 'tuffai' ? 'You' : NAME[m.agent]}: ${trim(m.text || '', 600)}`;
      if (used + l.length > 2000) break;
      said.unshift(l);
      used += l.length;
    }
    if (said.length) parts.history = said;
    return parts;
  }

  // The Tuff error from the last run in the Run panel, if it's about the open file as it is now: the line
  // the error quotes ("  3 | for n in range(1, 3)") must still be that line of the file.
  function lastRunError(code) {
    const errs = [...document.querySelectorAll('#run-output .err')];
    let at = errs.length - 1;
    while (at >= 0 && !/Tuff error on line \d+/.test(errs[at].textContent)) at--;
    if (at < 0) return '';
    // The error can come in more than one piece; leave out the Explain button's text.
    const text = errs.slice(at).map((s) => [...s.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('')).join('').replace(/\r\n/g, '\n').trim();
    const m = /Tuff error on line (\d+)[^\n]*\n\s*\1 \| ([^\n]*)/.exec(text);
    const line = m ? String(code || '').split(/\r?\n/)[+m[1] - 1] : null;
    return m && line != null && line.trim() === m[2].trim() ? text : '';
  }

  // bare: just the message (no open file, selection or chat history), for the tools test.
  // full: the whole chat since the last summary (for /compact), not just what's new to this agent.
  function buildPrompt(text, { mode = S.mode, bare = false, full = false, note = '' } = {}) {
    if (isLocal(S.agent)) return text; // its parts go separately (aiParts)
    const file = t.editor.file();
    const parts = [
      "You're helping someone inside TuffCode, the code editor for the Tuff programming language (.tuf files). They may be a beginner, so explain things simply and keep code short and readable. Write Tuff unless they ask for another language.",
      "TuffCode gives you MCP tools named tuffcode: call tuff_reference before writing Tuff, tuff_examples for app patterns, and tuff_check on any Tuff code you write or change. If those tools aren't there: Tuff is like Python but uses say to print, 'is' for ==, func instead of def, ':' for methods (app:button) and range(1, 3) includes 3.",
      mode === 'edit'
        ? 'You may change files in the project folder to do what they ask. Afterwards, say in a sentence or two what you changed.'
        : mode === 'plan'
          ? "Don't change any files yet. Make a short, numbered plan in plain words: what you'd change, in which files, and why. Then ask if they want you to go ahead."
          : "Don't change any files. Answer and explain in the chat. If their code needs changing, say briefly what you'd change and why (a short ```tuff snippet is fine), then ask if they'd like you to make the change for them. Don't paste a whole rewritten program unless they ask for one.",
      `Project folder: ${t.project.root()}`,
    ];
    if (bare) {
      parts.push(`Their message:\n${text}`);
      return parts.join('\n\n');
    }
    if (file && S.useFile) parts.push(`Open file: ${t.project.rel(file)}\n\`\`\`${/\.tuf$/i.test(file) ? 'tuff' : ''}\n${trim(t.editor.code(), 24000)}\n\`\`\``);
    const lines = t.editor.selectionLines();
    if (S.useSel && lines) parts.push(`They selected lines ${lines[0]} to ${lines[1]}:\n\`\`\`\n${trim(t.editor.selection(), 8000)}\n\`\`\``);
    // One chat, several agents: whoever answers needs to know who said what, and what happened
    // while another agent had the floor.
    const me = S.agent;
    // "Test it" runs are diagnostics, not part of the conversation.
    const earlier = chatSoFar();
    const others = earlier.some((m) => m.role === 'agent' && m.agent !== me);
    const running = picked(me).model?.name || S.used[me];
    parts.push(`You are ${NAME[me]}${running ? `, running as ${running}` : ''}. You're one of a team of AI agents in TuffCode (Claude Code, Codex, Antigravity and Tuff AI) that work on the same project together, one at a time: the person picks who answers each message. This chat is the team's shared memory. Every earlier line below is labelled with who wrote it ("Them" is the person; "You" is you).${others
      ? ' Lines labelled with another agent\'s name were written by that agent. When one of them says something about itself, like "I\'m Opus 5.5" or "I\'m Codex", it\'s true for that agent: it isn\'t about you, and it isn\'t a mistake to correct. Treat their work as a teammate\'s: build on it, and don\'t take credit for it or argue about who wrote it.'
      : ''}`);
    // Agents that keep their own session (Claude Code, Antigravity) already remember their turns,
    // so they get what happened since they last answered. Only turns that really reached their
    // session count (a run stopped or failed before it started doesn't). Others get the recent chat.
    const mine = earlier.map((m) => m.role === 'agent' && m.agent === me && m.inSession).lastIndexOf(true);
    const resumes = !full && ['claude', 'antigravity'].includes(me) && S.sessions[me] && mine >= 0;
    const who = (m) => {
      if (m.role === 'user') return 'Them';
      const name = `${NAME[m.agent]}${m.name ? ` (${m.name})` : ''}`;
      return m.agent === me ? `You (${name})` : name;
    };
    const line = (m) => {
      if (m.summary) return `Summary of the chat before this point, written by ${who(m)} when the person used /compact:\n${trim(m.text, 4000)}`;
      const did = m.role === 'agent' ? [...new Set((m.tools || []).filter((x) => x.ok !== false && /^(Wrote|Changed)\b/.test(x.text)).map((x) => x.text))] : [];
      return `${who(m)}: ${trim(m.text || (m.error ? `(stopped: ${m.error})` : '(no reply)'), 1500)}${did.length ? `\n  [${did.join('; ')}]` : ''}`;
    };
    // Newest first until the budget is used up, so a long stretch with another agent can't make the
    // prompt huge. Antigravity gets less: its prompt goes on the command line.
    const pool = full ? earlier : resumes ? earlier.slice(mine + 1) : earlier.slice(-10);
    const budget = me === 'antigravity' ? 12000 : 30000;
    const kept = [];
    let used = 0;
    for (let i = pool.length - 1; i >= 0; i--) {
      const l = line(pool[i]);
      if (used + l.length > budget && kept.length) break;
      kept.unshift(l);
      used += l.length;
    }
    const dropped = pool.length - kept.length;
    const said = (dropped ? `(${dropped} earlier message${dropped > 1 ? 's' : ''} left out)\n` : '') + kept.join('\n');
    if (kept.length) parts.push(`${resumes ? 'Since you last answered, this happened in the chat' : 'Earlier in this chat'} (for context only: all of it has been answered already):\n<chat>\n${said}\n</chat>`);
    if (note && !bare) parts.push(note);
    parts.push(`Their new message. This is what to answer now:\n<message>\n${text}\n</message>`);
    return parts.join('\n\n');
  }

  // opts.test: the "Test it" run from Agent tools. It always asks (never edits), sends no file or
  // history, keeps whatever you were typing, and reports which TuffCode tools the agent used.
  async function send(text, opts = {}) {
    text = String(text || '').trim();
    const a = current();
    if (!text || S.run) return;
    if (text.startsWith('/') && !opts.test && !opts.compact) { command(text); return; }
    if (!a?.installed) { renderStatus(); t.toast(`${a?.name || 'That agent'} isn't installed yet.`, 'error'); return; }
    if (S.auth[a.id] === false) { showSetup(false); renderStatus(); t.toast(`Sign in to ${a.name} first (the card at the top).`, 'error'); return; }
    const test = !!opts.test;
    const compacting = !!opts.compact;
    // Tuff AI never edits files itself: its code gets an Apply button instead.
    const mode = test || compacting || a.local ? 'ask' : opts.mode || S.mode;
    const file = t.editor.file();
    const lines = t.editor.selectionLines();
    const ctx = test || compacting ? '' : [file && S.useFile ? short(file) : '', lines && S.useSel ? `lines ${lines[0]}–${lines[1]}` : ''].filter(Boolean).join(', ');
    if (compacting) S.msgs.push({ role: 'note', text: `${a.name} is summing up the chat (/compact)…` });
    else S.msgs.push({ role: 'user', text: test ? `Test ${a.name}'s TuffCode tools` : text, ctx: ctx ? `with ${ctx}` : '', test });
    const prompt = buildPrompt(text, { mode, bare: test, full: compacting, note: opts.note });
    const parts = a.local ? aiParts(text) : null;
    const { model, effort } = picked();
    // Pumice 1 with thinking off is just "Pumice 1".
    const level = a.local && effort?.id === 'off' ? null : effort;
    // model: what the reply header shows ('Opus 5.5 · High'); name: just the model, for other agents.
    const msg = { role: 'agent', agent: S.agent, mode, text: '', tools: [], status: 'running', model: [model?.name, level?.name].filter(Boolean).join(' · '), name: model?.name || '', picked: !!model, effort: level?.name || '', test, compacting };
    S.msgs.push(msg);
    const runId = `run-${Date.now()}`;
    S.run = { id: runId, msg, changed: false, test, mcp: new Set() };
    if (!test) {
      const ta = $('textarea', root);
      ta.value = '';
      ta.style.height = 'auto';
    }
    renderMsgs();
    updateSend();
    try {
      await t.agents.run({ runId, agent: S.agent, prompt, root: t.project.root(), mode, session: !test && !compacting && ['claude', 'antigravity'].includes(S.agent) ? S.sessions[S.agent] : null, model: model?.id || '', effort: effort?.id || '', ...(parts ? { ai: parts } : {}) });
    } catch (err) {
      onEvent({ runId, kind: 'done', ok: false, error: err.message });
    }
  }

  function onEvent(ev) {
    if (!S.run || ev.runId !== S.run.id) return;
    const m = S.run.msg;
    switch (ev.kind) {
      case 'session': // the run reached the agent's session; a test run never becomes the chat's session
        if (!S.run.test && !m.compacting) { S.sessions[m.agent] = ev.id; m.inSession = true; }
        break;
      case 'model': // the model that really answered (Claude Code says so when it starts)
        // S.used is what Default turned out to be, so only a Default run updates it.
        if (!m.picked) { S.used[m.agent] = ev.name; m.name = ev.name; m.model = [ev.name, m.effort].filter(Boolean).join(' · '); }
        renderPick();
        break;
      case 'delta': m.text += ev.text; break;
      case 'break': if (m.text && !/\n\n$/.test(m.text)) m.text += '\n\n'; break;
      case 'text': m.text += (m.text && !/\n\n$/.test(m.text) ? '\n\n' : '') + ev.text; break;
      case 'tool': {
        const d = describeTool(ev.name, ev.input);
        m.tools.push({ text: d.text, ok: null });
        if (d.changes) S.run.changed = true;
        if (/^mcp__tuffcode__/.test(ev.name || '')) S.run.mcp.add(ev.name.replace(/^mcp__tuffcode__/, ''));
        break;
      }
      case 'tool_result': {
        const last = [...m.tools].reverse().find((x) => x.ok === null);
        if (last) last.ok = ev.ok;
        break;
      }
      case 'note': m.notes = [...(m.notes || []), ev.text]; break;
      case 'error': m.error = ev.text; break;
      // Tuff AI: what it's doing now, its thinking, and the request as the improver rewrote it.
      case 'stage': m.stage = ev.text; break;
      case 'thinking':
        if (!m.thinkFrom) m.thinkFrom = Date.now();
        m.thought = (m.thought || '') + (m.thinkGap ? '\n\n' : '') + ev.text;
        m.thinkGap = false;
        break;
      case 'thought': m.thinkMs = (m.thinkMs || 0) + (ev.ms || 0); m.thinkFrom = 0; m.thinkGap = true; break;
      case 'improved': m.improved = ev.text; break;
      case 'plan': m.plan = (m.plan || '') + ev.text; break;
      case 'done':
        endThinking(m);
        m.status = ev.ok ? 'done' : 'error';
        if (!ev.ok) m.error = m.error || ev.error || 'Something went wrong.';
        if (ev.session && !S.run.test && !m.compacting) { S.sessions[m.agent] = ev.session; m.inSession = true; }
        for (const x of m.tools) if (x.ok === null) x.ok = ev.ok;
        finish();
        break;
      default: break;
    }
    rerender(m);
  }

  function finish() {
    const r = S.run;
    const changed = r.changed || r.msg.mode === 'edit';
    S.run = null;
    updateSend();
    // A finished /compact: its reply becomes the summary every agent gets instead of the chat before it, and
    // agents that keep their own session start a new one from it.
    if (r.msg.compacting && r.msg.status === 'done' && r.msg.text.trim()) {
      r.msg.summary = true;
      S.sessions = {};
      renderMsgs();
    }
    if (changed) t.reloadChanged();
    if (r.test) {
      const id = r.msg.agent;
      const used = [...r.mcp];
      const ok = used.length > 0 && r.msg.status === 'done';
      const text = ok ? `Test passed: ${NAME[id]} used ${used.join(' and ')}.`
        : used.length ? `${NAME[id]} reached the tools, but the test didn't finish.`
          : `${NAME[id]} didn't use TuffCode's tools.${id === 'claude' ? '' : ' Connect them first.'}`;
      S.tested[id] = { ok, text };
      t.toast(text, ok ? 'ok' : 'error', 6000);
      renderSetup();
    }
  }

  // A reply that ends (or is stopped) while it's still thinking: the time so far counts.
  function endThinking(m) {
    if (m.thinkFrom) m.thinkMs = (m.thinkMs || 0) + Date.now() - m.thinkFrom;
    m.thinkFrom = 0;
  }

  function stop() {
    if (!S.run) return;
    t.agents.stop(S.run.id);
    S.run.msg.status = 'stopped';
    const m = S.run.msg;
    endThinking(m);
    finish();
    rerender(m);
  }

  function updateSend() {
    const b = $('.ta-send', root);
    b.textContent = S.run ? 'Stop' : 'Send';
    b.classList.toggle('stop', !!S.run);
    b.title = S.run ? 'Stop the agent' : 'Send (Enter)';
    renderLock();
  }

  return () => {
    off?.();
    offAi?.();
    delete window.tuffExplainError;
    delete window.tuffAskAgent;
    clearInterval(ctxTimer);
    if (S.run) t.agents.stop(S.run.id);
  };
});
