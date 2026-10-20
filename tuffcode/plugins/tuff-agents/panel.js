// Tuff Agents: a chat sidebar that runs Claude Code, Codex or Antigravity on your project.
// The agents get TuffCode's MCP tools (the Tuff language guide, examples, check and run).
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
  };
  let root = null;
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
          <button class="ta-ib" data-a="menu" title="More">⋯</button>
          <div class="ta-menu hidden"></div>
        </div>
        <div class="ta-status"></div>
        <div class="ta-msgs" aria-live="polite"></div>
        <div class="ta-compose">
          <div class="ta-ctx"></div>
          <textarea rows="3" spellcheck="true" placeholder="Ask about your code…"></textarea>
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
    $('[data-a="menu"]', root).onclick = (e) => { e.stopPropagation(); toggleMenu(); };
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
    for (const a of S.agents.filter((x) => x.installed)) {
      t.agents.connection(a.id).then((c) => { S.conn[a.id] = c.connected; renderStatus(); }).catch(() => {});
    }
  }

  function renderAgents() {
    const box = $('.ta-agents', root);
    box.innerHTML = ORDER.map((id) => {
      const a = S.agents?.find((x) => x.id === id);
      const state = !S.agents ? 'checking' : a?.installed ? 'ready' : 'missing';
      const title = !S.agents ? 'Checking…' : a?.installed ? `${a.name}${a.version ? ` ${a.version}` : ''}` : `${a?.name || id} isn't installed`;
      return `<button role="tab" data-id="${id}" class="${id === S.agent ? 'on' : ''}" title="${esc(title)}" aria-selected="${id === S.agent}"><i class="dot ${state}"></i>${SHORT[id]}</button>`;
    }).join('');
    $$('button', box).forEach((b) => (b.onclick = () => { S.agent = b.dataset.id; t.storage.set('agent', S.agent); renderAgents(); renderStatus(); renderMsgs(); }));
  }

  function renderMode() {
    $$('.ta-mode button', root).forEach((b) => { b.classList.toggle('on', b.dataset.m === S.mode); b.setAttribute('aria-checked', b.dataset.m === S.mode); });
    $('.ta-hint', root).textContent = S.mode === 'edit' ? 'Can change your files' : "Won't change your files";
    $('textarea', root).placeholder = S.mode === 'edit' ? 'Tell the agent what to change…' : 'Ask about your code…';
  }

  function renderStatus() {
    const box = $('.ta-status', root);
    const a = current();
    if (!S.agents) { box.innerHTML = '<div class="ta-note">Looking for AI agents on this PC…</div>'; return; }
    if (!a?.installed) {
      box.innerHTML = `<div class="ta-card">
        <b>${esc(a?.name || S.agent)} isn't installed</b>
        <p>Install it once, then come back. TuffCode runs it for you right here.</p>
        <div class="ta-cmd"><code>${esc(a?.install || '')}</code><button data-a="copy-install">Copy</button></div>
        <div class="ta-btns"><button class="btn sm" data-a="site">Website</button><button class="btn sm" data-a="recheck">Check again</button></div>
      </div>`;
    } else if (S.agent !== 'claude' && S.conn[S.agent] === false && !S.dismissed[S.agent]) {
      box.innerHTML = `<div class="ta-card">
        <b>Teach ${esc(a.name)} about Tuff</b>
        <p>Connect TuffCode's tools so ${esc(a.name)} can read the Tuff guide and check and run your programs. This adds a "tuffcode" tool server to its settings. You can remove it any time from the ⋯ menu.</p>
        <div class="ta-btns"><button class="btn sm primary" data-a="connect">Connect</button><button class="btn sm" data-a="dismiss">Not now</button></div>
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
    };
  }

  async function connect(on) {
    const a = current();
    try {
      const c = await t.agents.connect(a.id, on);
      S.conn[a.id] = c.connected;
      t.toast(on ? `${a.name} can now use TuffCode's Tuff tools.` : `Removed TuffCode's tools from ${a.name}.`, 'ok');
    } catch (err) {
      t.toast(String(err.message).replace(/^Error invoking remote method '[^']+': (Error: )?/, ''), 'error', 7000);
    }
    renderStatus();
  }

  function toggleMenu() {
    const m = $('.ta-menu', root);
    const a = current();
    const items = [['new', 'New chat']];
    if (a?.installed) items.push(S.conn[a.id] ? ['disconnect', `Remove TuffCode tools from ${a.name}`] : ['connect', `Add TuffCode tools to ${a.name}${a.id === 'claude' ? ' everywhere' : ''}`]);
    items.push(['recheck', 'Look for agents again']);
    m.innerHTML = items.map(([id, label]) => `<button data-m="${id}">${esc(label)}</button>`).join('');
    m.classList.toggle('hidden');
    m.onclick = (e) => {
      const id = e.target.closest('button')?.dataset.m;
      m.classList.add('hidden');
      if (id === 'new') { if (S.run) stop(); S.msgs = []; S.sessions = {}; renderMsgs(); }
      if (id === 'connect') connect(true);
      if (id === 'disconnect') connect(false);
      if (id === 'recheck') refreshAgents();
    };
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
      <div class="ta-who">${esc(SHORT[m.agent])}${m.mode === 'edit' ? ' · Edit' : ''}</div>
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

  function buildPrompt(text) {
    const file = t.editor.file();
    const parts = [
      "You're helping someone inside TuffCode, the code editor for the Tuff programming language (.tuf files). They may be a beginner, so explain things simply and keep code short and readable. Write Tuff unless they ask for another language.",
      "TuffCode gives you MCP tools named tuffcode: call tuff_reference before writing Tuff, tuff_examples for app patterns, and tuff_check on any Tuff code you write or change. If those tools aren't there: Tuff is like Python but uses say to print, 'is' for ==, func instead of def, ':' for methods (app:button) and range(1, 3) includes 3.",
      S.mode === 'edit'
        ? 'You may change files in the project folder to do what they ask. Afterwards, say in a sentence or two what you changed.'
        : "Don't change any files. Answer in the chat, and put code in ```tuff blocks so they can insert it.",
      `Project folder: ${t.project.root()}`,
    ];
    if (file && S.useFile) parts.push(`Open file: ${t.project.rel(file)}\n\`\`\`${/\.tuf$/i.test(file) ? 'tuff' : ''}\n${trim(t.editor.code(), 24000)}\n\`\`\``);
    const lines = t.editor.selectionLines();
    if (S.useSel && lines) parts.push(`They selected lines ${lines[0]} to ${lines[1]}:\n\`\`\`\n${trim(t.editor.selection(), 8000)}\n\`\`\``);
    if (!(S.agent === 'claude' && S.sessions.claude)) {
      const history = S.msgs.slice(-9, -1).map((m) => `${m.role === 'user' ? 'Them' : 'You'}: ${trim(m.text, 1500)}`).join('\n');
      if (history) parts.push(`Earlier in this chat:\n${history}`);
    }
    parts.push(`Their message:\n${text}`);
    return parts.join('\n\n');
  }

  async function send(text) {
    text = String(text || '').trim();
    const a = current();
    if (!text || S.run) return;
    if (!a?.installed) { renderStatus(); t.toast(`${a?.name || 'That agent'} isn't installed yet.`, 'error'); return; }
    const file = t.editor.file();
    const lines = t.editor.selectionLines();
    const ctx = [file && S.useFile ? short(file) : '', lines && S.useSel ? `lines ${lines[0]}–${lines[1]}` : ''].filter(Boolean).join(', ');
    S.msgs.push({ role: 'user', text, ctx: ctx ? `with ${ctx}` : '' });
    const prompt = buildPrompt(text);
    const msg = { role: 'agent', agent: S.agent, mode: S.mode, text: '', tools: [], status: 'running' };
    S.msgs.push(msg);
    const runId = `run-${Date.now()}`;
    S.run = { id: runId, msg, changed: false };
    const ta = $('textarea', root);
    ta.value = '';
    ta.style.height = 'auto';
    renderMsgs();
    updateSend();
    try {
      await t.agents.run({ runId, agent: S.agent, prompt, root: t.project.root(), mode: S.mode, session: S.agent === 'claude' ? S.sessions.claude : null });
    } catch (err) {
      onEvent({ runId, kind: 'done', ok: false, error: err.message });
    }
  }

  function onEvent(ev) {
    if (!S.run || ev.runId !== S.run.id) return;
    const m = S.run.msg;
    switch (ev.kind) {
      case 'session': S.sessions[m.agent] = ev.id; break;
      case 'delta': m.text += ev.text; break;
      case 'break': if (m.text && !/\n\n$/.test(m.text)) m.text += '\n\n'; break;
      case 'text': m.text += (m.text && !/\n\n$/.test(m.text) ? '\n\n' : '') + ev.text; break;
      case 'tool': {
        const d = describeTool(ev.name, ev.input);
        m.tools.push({ text: d.text, ok: null });
        if (d.changes) S.run.changed = true;
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
        if (ev.session) S.sessions[m.agent] = ev.session;
        for (const x of m.tools) if (x.ok === null) x.ok = ev.ok;
        finish();
        break;
      default: break;
    }
    rerender(m);
  }

  function finish() {
    const changed = S.run.changed || S.run.msg.mode === 'edit';
    S.run = null;
    updateSend();
    if (changed) t.reloadChanged();
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
  }

  return () => {
    off?.();
    clearInterval(ctxTimer);
    if (S.run) t.agents.stop(S.run.id);
  };
});
