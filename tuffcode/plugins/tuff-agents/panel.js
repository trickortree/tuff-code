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

  const ORDER = ['claude', 'codex', 'antigravity'];
  const SHORT = { claude: 'Claude', codex: 'Codex', antigravity: 'Antigravity' };
  const SUGGEST = [
    ['Explain this file', 'Explain what this file does, step by step, in simple words.'],
    ['Find bugs', 'Look for bugs or mistakes in this code and explain how to fix them.'],
    ['Make it nicer', 'Suggest ways to make this app look and feel nicer.'],
    ['Teach me something', 'Teach me one new Tuff trick that would help with this code, with a short example.'],
  ];
  const NAME = { claude: 'Claude Code', codex: 'Codex', antigravity: 'Antigravity' };
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

  function quick(text) {
    panel.open();
    setTimeout(() => send(text), 50);
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
          <div class="ta-ctx"></div>
          <textarea rows="3" spellcheck="true" placeholder="Ask about your code…"></textarea>
          <div class="ta-opts">
            <div class="ta-dd" data-o="model"></div>
            <div class="ta-dd" data-o="effort"></div>
          </div>
          <div class="ta-row">
            <div class="ta-mode" role="radiogroup" aria-label="What the agent may do">
              <button data-m="ask" title="Explains and suggests. Won't change your files.">Ask</button>
              <button data-m="edit" title="Can change files in this project to do what you ask.">Edit</button>
            </div>
            <span class="ta-hint"></span>
            <button class="ta-send" title="Send (Enter)">Send</button>
          </div>
        </div>
      </div>`;
    const ta = $('textarea', root);
    ta.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(ta.value); }
    });
    ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = `${Math.min(220, ta.scrollHeight)}px`; });
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
    renderAgents();
    renderMode();
    renderMsgs();
    updateCtx();
  }

  const current = () => S.agents?.find((a) => a.id === S.agent);

  async function refreshAgents() {
    S.agents = null;
    renderAgents();
    renderStatus();
    try {
      S.agents = await t.agents.detect();
    } catch (err) {
      S.agents = [];
      t.toast(`Couldn't look for agents: ${err.message}`, 'error');
    }
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
    renderPick();
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
  function picked(id = S.agent) {
    const list = S.models[id] || {};
    const p = S.pick[id] || {};
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
  const LEVEL_BARS = { minimal: 1, low: 1, medium: 2, high: 3, xhigh: 4, max: 5, ultra: 5 };
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
      return `<button role="tab" data-id="${id}" class="${id === S.agent ? 'on' : ''}" data-title="${esc(title)}" title="${esc(locked ? 'Wait for the reply to finish, or press Stop' : title)}" aria-selected="${id === S.agent}"${locked ? ' disabled' : ''}><i class="dot ${state}"></i>${SHORT[id]}</button>`;
    }).join('');
    $$('button', box).forEach((b) => (b.onclick = () => {
      if (S.run && b.dataset.id !== S.agent) return;
      S.agent = b.dataset.id;
      t.storage.set('agent', S.agent);
      if (S.view === 'setup') showSetup(false);
      renderAgents();
      renderStatus();
      renderMsgs();
      renderPick();
    }));
  }

  function renderMode() {
    $$('.ta-mode button', root).forEach((b) => { b.classList.toggle('on', b.dataset.m === S.mode); b.setAttribute('aria-checked', b.dataset.m === S.mode); });
    $('.ta-hint', root).textContent = S.mode === 'edit' ? 'Can change your files' : "Won't change your files";
    $('textarea', root).placeholder = S.mode === 'edit' ? 'Tell the agent what to change…' : 'Ask about your code…';
  }

  function renderStatus() {
    const box = $('.ta-status', root);
    const a = current();
    if (!S.agents) { box.innerHTML = `<div class="ta-note">Looking for AI agents on this ${document.documentElement.classList.contains('mac') ? 'Mac' : 'PC'}…</div>`; return; }
    if (!a?.installed) {
      box.innerHTML = `<div class="ta-card">
        <b>${esc(a?.name || S.agent)} isn't installed</b>
        <p>Install it once, then come back. TuffCode runs it for you right here.${INSTALL_TIP[S.agent] || ''}</p>
        <div class="ta-cmd"><code>${esc(a?.install || '')}</code><button data-a="copy-install">Copy</button></div>
        <div class="ta-btns"><button class="btn sm" data-a="site">Website</button><button class="btn sm" data-a="recheck">Check again</button></div>
      </div>`;
    } else if (S.auth[S.agent] === false) {
      box.innerHTML = `<div class="ta-card">
        <b>Sign in to ${esc(a.name)}</b>
        <p>${signInText(a)} A window opens and your browser does the rest.</p>
        <div class="ta-btns"><button class="btn sm primary" data-a="signin">Sign in</button><button class="btn sm" data-a="recheck">Check again</button></div>
      </div>`;
    } else if (S.agent !== 'claude' && S.conn[S.agent] === false && !S.dismissed[S.agent]) {
      box.innerHTML = `<div class="ta-card">
        <b>Teach ${esc(a.name)} about Tuff</b>
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
    };
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
    if (a?.installed) items.push(S.conn[a.id] ? ['disconnect', `Remove TuffCode tools from ${a.name}`] : ['connect', `Add TuffCode tools to ${a.name}${a.id === 'claude' ? ' everywhere' : ''}`]);
    items.push(['recheck', 'Look for agents again']);
    m.innerHTML = items.map(([id, label]) => `<button data-m="${id}">${esc(label)}</button>`).join('');
    m.classList.toggle('hidden');
    m.onclick = (e) => {
      const id = e.target.closest('button')?.dataset.m;
      m.classList.add('hidden');
      if (id === 'new') { if (S.run) stop(); S.msgs = []; S.sessions = {}; S.used = {}; renderMsgs(); renderPick(); }
      if (id === 'setup') showSetup(true);
      if (id === 'connect') connect(true);
      if (id === 'disconnect') connect(false);
      if (id === 'recheck') refreshAgents();
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
        ${ORDER.map(agentSetupHtml).join('')}
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
    return ORDER.map((id) => part(id, NAME[id], `
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
        <span>It can see the file you have open. Switch to <b>Edit</b> to let it change files for you.</span>
        <div class="ta-sugg">${SUGGEST.map(([label], i) => `<button data-s="${i}">${esc(label)}</button>`).join('')}</div>
        <button class="ta-link" data-setup>${PLUG}Set up and check agent tools</button>
      </div>`;
      return;
    }
    box.innerHTML = S.msgs.map((m, i) => msgHtml(m, i)).join('');
    box.scrollTop = box.scrollHeight;
  }

  function msgHtml(m, i) {
    if (m.role === 'user') {
      return `<div class="ta-msg user" data-i="${i}"><div class="ta-bubble">${esc(m.text).replace(/\n/g, '<br>')}</div>${m.ctx ? `<div class="ta-with">${esc(m.ctx)}</div>` : ''}</div>`;
    }
    const tools = m.tools.map((x) => `<div class="ta-tool ${x.ok === false ? 'bad' : x.ok ? 'ok' : 'run'}"><i></i><span>${esc(x.text)}</span></div>`).join('');
    const status = m.status === 'running' ? '<div class="ta-typing"><i></i><i></i><i></i></div>'
      : m.status === 'stopped' ? '<div class="ta-small">Stopped.</div>'
        : m.status === 'error' ? `<div class="ta-err">${esc(m.error)}</div>` : '';
    const notes = (m.notes || []).map((n) => `<div class="ta-small">${esc(n)}</div>`).join('');
    return `<div class="ta-msg agent" data-i="${i}">
      <div class="ta-who">${esc(SHORT[m.agent])}${m.model ? ` · ${esc(m.model)}` : ''}${m.mode === 'edit' ? ' · Edit' : ''}</div>
      ${tools ? `<div class="ta-tools">${tools}</div>` : ''}
      <div class="ta-md">${md(m.text)}</div>${notes}${status}</div>`;
  }

  function rerender(m) {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const box = $('.ta-msgs', root);
      const i = S.msgs.indexOf(m);
      const el = box.querySelector(`.ta-msg[data-i="${i}"]`);
      const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
      if (el) el.outerHTML = msgHtml(m, i); else renderMsgs();
      if (atBottom) box.scrollTop = box.scrollHeight;
    });
  }

  function onMsgClick(e) {
    if (e.target.closest('[data-setup]')) { showSetup(true); return; }
    const s = e.target.closest('[data-s]');
    if (s) { send(SUGGEST[+s.dataset.s][1]); return; }
    const b = e.target.closest('[data-code]');
    if (!b) return;
    const code = b.closest('.ta-code').querySelector('code').textContent;
    if (b.dataset.code === 'copy') { navigator.clipboard.writeText(code); t.toast('Copied.', 'ok', 1500); }
    if (b.dataset.code === 'insert') t.editor.insert(code);
  }

  // Small markdown: code blocks (with Copy / Insert), headings, lists, `code`, **bold** and *italics*.
  function md(src) {
    if (!src) return '';
    const parts = [];
    const re = /```([\w+-]*)[^\n]*\n?([\s\S]*?)(?:```|$)/g;
    let last = 0;
    let m;
    while ((m = re.exec(src))) {
      parts.push(prose(src.slice(last, m.index)));
      parts.push(`<div class="ta-code"><div class="ta-code-h"><span>${esc(m[1] || 'code')}</span><button data-code="copy">Copy</button><button data-code="insert" title="Insert at the cursor in the editor">Insert</button></div><pre><code>${esc(m[2].replace(/\n$/, ''))}</code></pre></div>`);
      last = re.lastIndex;
      if (m.index === re.lastIndex) break;
    }
    parts.push(prose(src.slice(last)));
    return parts.join('');
  }

  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>');
  }

  function prose(text) {
    const out = [];
    let list = null;
    let para = [];
    const flushPara = () => { if (para.length) out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = []; };
    const flushList = () => { if (list) out.push(`<${list.tag}>${list.items.map((x) => `<li>${inline(x)}</li>`).join('')}</${list.tag}>`); list = null; };
    for (const raw of text.split('\n')) {
      const line = raw.trimEnd();
      let m;
      if (!line.trim()) { flushPara(); flushList(); continue; }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flushPara(); flushList(); out.push(`<h4>${inline(m[2])}</h4>`); continue; }
      if ((m = line.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/))) {
        flushPara();
        const tag = m[1] ? 'ol' : 'ul';
        if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
        list.items.push(m[2]);
        continue;
      }
      flushList();
      para.push(line);
    }
    flushPara();
    flushList();
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

  // bare: just the message (no open file, selection or chat history), for the tools test.
  function buildPrompt(text, { mode = S.mode, bare = false } = {}) {
    const file = t.editor.file();
    const parts = [
      "You're helping someone inside TuffCode, the code editor for the Tuff programming language (.tuf files). They may be a beginner, so explain things simply and keep code short and readable. Write Tuff unless they ask for another language.",
      "TuffCode gives you MCP tools named tuffcode: call tuff_reference before writing Tuff, tuff_examples for app patterns, and tuff_check on any Tuff code you write or change. If those tools aren't there: Tuff is like Python but uses say to print, 'is' for ==, func instead of def, ':' for methods (app:button) and range(1, 3) includes 3.",
      mode === 'edit'
        ? 'You may change files in the project folder to do what they ask. Afterwards, say in a sentence or two what you changed.'
        : "Don't change any files. Answer in the chat, and put code in ```tuff blocks so they can insert it.",
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
    const earlier = S.msgs.slice(0, -1).filter((m) => !m.test && (m.role === 'user' || m.status !== 'running'));
    const others = earlier.some((m) => m.role === 'agent' && m.agent !== me);
    const running = picked(me).model?.name || S.used[me];
    parts.push(`You are ${NAME[me]}${running ? `, running as ${running}` : ''}. ${others
      ? 'This chat is shared: the person can switch between AI agents (Claude Code, Codex and Antigravity) at any time, and you all work on the same project. Replies marked with another agent\'s name were written by that agent, not by you. Treat them as a teammate\'s work: build on it, and don\'t take credit for it or "correct" who wrote it.'
      : 'The person can also switch to other AI agents (Claude Code, Codex, Antigravity) in this chat.'}`);
    // Agents that keep their own session (Claude Code, Antigravity) already remember their turns,
    // so they get what happened since they last answered. Only turns that really reached their
    // session count (a run stopped or failed before it started doesn't). Others get the recent chat.
    const mine = earlier.map((m) => m.role === 'agent' && m.agent === me && m.inSession).lastIndexOf(true);
    const resumes = ['claude', 'antigravity'].includes(me) && S.sessions[me] && mine >= 0;
    const who = (m) => {
      if (m.role === 'user') return 'Them';
      const name = `${NAME[m.agent]}${m.name ? ` (${m.name})` : ''}`;
      return m.agent === me ? `You (${name})` : name;
    };
    const line = (m) => {
      const did = m.role === 'agent' ? [...new Set((m.tools || []).filter((x) => x.ok !== false && /^(Wrote|Changed)\b/.test(x.text)).map((x) => x.text))] : [];
      return `${who(m)}: ${trim(m.text || (m.error ? `(stopped: ${m.error})` : '(no reply)'), 1500)}${did.length ? `\n  [${did.join('; ')}]` : ''}`;
    };
    // Newest first until the budget is used up, so a long stretch with another agent can't make the
    // prompt huge. Antigravity gets less: its prompt goes on the command line.
    const pool = resumes ? earlier.slice(mine + 1) : earlier.slice(-10);
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
    parts.push(`Their new message. This is what to answer now:\n<message>\n${text}\n</message>`);
    return parts.join('\n\n');
  }

  // opts.test: the "Test it" run from Agent tools. It always asks (never edits), sends no file or
  // history, keeps whatever you were typing, and reports which TuffCode tools the agent used.
  async function send(text, opts = {}) {
    text = String(text || '').trim();
    const a = current();
    if (!text || S.run) return;
    if (!a?.installed) { renderStatus(); t.toast(`${a?.name || 'That agent'} isn't installed yet.`, 'error'); return; }
    if (S.auth[a.id] === false) { showSetup(false); renderStatus(); t.toast(`Sign in to ${a.name} first (the card at the top).`, 'error'); return; }
    const test = !!opts.test;
    const mode = test ? 'ask' : S.mode;
    const file = t.editor.file();
    const lines = t.editor.selectionLines();
    const ctx = test ? '' : [file && S.useFile ? short(file) : '', lines && S.useSel ? `lines ${lines[0]}–${lines[1]}` : ''].filter(Boolean).join(', ');
    S.msgs.push({ role: 'user', text: test ? `Test ${a.name}'s TuffCode tools` : text, ctx: ctx ? `with ${ctx}` : '', test });
    const prompt = buildPrompt(text, { mode, bare: test });
    const { model, effort } = picked();
    // model: what the reply header shows ('Opus 5.5 · High'); name: just the model, for other agents.
    const msg = { role: 'agent', agent: S.agent, mode, text: '', tools: [], status: 'running', model: [model?.name, effort?.name].filter(Boolean).join(' · '), name: model?.name || '', picked: !!model, effort: effort?.name || '', test };
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
      await t.agents.run({ runId, agent: S.agent, prompt, root: t.project.root(), mode, session: !test && ['claude', 'antigravity'].includes(S.agent) ? S.sessions[S.agent] : null, model: model?.id || '', effort: effort?.id || '' });
    } catch (err) {
      onEvent({ runId, kind: 'done', ok: false, error: err.message });
    }
  }

  function onEvent(ev) {
    if (!S.run || ev.runId !== S.run.id) return;
    const m = S.run.msg;
    switch (ev.kind) {
      case 'session': // the run reached the agent's session; a test run never becomes the chat's session
        if (!S.run.test) { S.sessions[m.agent] = ev.id; m.inSession = true; }
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
      case 'done':
        m.status = ev.ok ? 'done' : 'error';
        if (!ev.ok) m.error = m.error || ev.error || 'Something went wrong.';
        if (ev.session && !S.run.test) { S.sessions[m.agent] = ev.session; m.inSession = true; }
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

  function stop() {
    if (!S.run) return;
    t.agents.stop(S.run.id);
    S.run.msg.status = 'stopped';
    const m = S.run.msg;
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
    clearInterval(ctxTimer);
    if (S.run) t.agents.stop(S.run.id);
  };
});
