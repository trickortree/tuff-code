// API Explorer: send a request to a web API, look through what comes back, and click any value to get
// the Tuff code that reaches it with tap. Requests go through t.net (the "net" permission); "Save as new
// file" uses t.project.write (the "files" permission).
// The Tuff-writing part at the top has no DOM in it, so Node can load this file for tests:
// require('panel.js') gives { code, explain, ... } when there's no TuffPlugins.
(() => {
  // ---------------------------------------------------------------- Tuff code from a request and a path
  const Tuff = (() => {
    const KEYWORDS = 'func return if elif else then while for in break continue and or not is true false nil say input flush import mention'.split(' ');
    const BUILTINS = 'print number num text str int len round random wait range clear sqrt abs floor ceil min max sum average pi err all'.split(' ');
    const LIBS = 'anims tgui mtgui tap atgui tgame'.split(' ');
    // Names the generated programs use themselves.
    const OWN = ['res', 'data', 'headers', 'body', 'answer'];
    const TAKEN = new Set([...KEYWORDS, ...BUILTINS, ...LIBS, ...OWN]);

    // A Tuff text literal. Tuff knows \n, \t, \" and \\; a line can't hold a real line break.
    const str = (s) => '"' + String(s)
      .replace(/\\/g, '\\\\').replace(/"/g, '\\"')
      .replace(/\r\n?/g, '\n').replace(/\n/g, '\\n').replace(/\t/g, '\\t')
      .replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, '') + '"';

    const clean = (raw) => String(raw).toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '').slice(0, 28).replace(/_$/, '');

    // A variable name made from a JSON name: temperature_2m, post_code, value_2fast. Never a keyword, a
    // built-in, a library or one of the program's own names, and never one already used.
    function ident(raw, used) {
      let n = clean(raw) || 'value';
      if (/^[0-9]/.test(n)) n = `value_${n}`;
      if (TAKEN.has(n)) n = `${n}_value`;
      let out = n;
      for (let i = 2; used.has(out); i++) out = `${n}_${i}`;
      used.add(out);
      return out;
    }

    // langs -> lang, abilities -> ability; a word that isn't plural gets _item: data -> data_item.
    function oneOf(word) {
      const w = clean(word) || 'item';
      if (/[^aeiou]ies$/.test(w) && w.length > 4) return w.slice(0, -3) + 'y';
      if (/(ss|us|is)$/.test(w) || !/s$/.test(w) || w.length <= 3) return `${w}_item`;
      return w.slice(0, -1);
    }

    // A path is a list of steps: { k: "name" } for a data object's value, { i: 0 } for a list position.
    // Tuff lists start at 0, like tap's lists: data:get("langs")[0] is the first one.
    const step = (s) => ('i' in s ? `[${s.i}]` : `:get(${str(s.k)})`);
    const reach = (path) => 'data' + path.map(step).join('');
    const lastKey = (path) => [...path].reverse().find((s) => 'k' in s);

    function valueName(path, used) {
      const last = path[path.length - 1];
      if ('k' in last) return ident(last.k, used);
      const key = lastKey(path);
      return ident(key ? oneOf(key.k) : 'item', used);
    }

    // What the whole program says before the value: "temperature_2m", "langs[1]", "data[0][2]".
    function label(path) {
      let at = path.length;
      while (at > 0 && 'i' in path[at - 1]) at--;
      const name = at > 0 ? String(path[at - 1].k) : 'data';
      return name + path.slice(at).map((s) => `[${s.i}]`).join('');
    }

    // Breadcrumb for people: current › temperature_2m, data › [1] › fact.
    const crumbs = (path) => (path.length ? path.map((s) => ('i' in s ? `[${s.i}]` : String(s.k))).join(' › ') : 'the whole answer');

    // A JSON value as Tuff: objects become data objects made with tap.data() and :set, lists stay lists.
    // Lines that make the data objects go into `lines`, children before their parents.
    function build(value, key, used, lines, rootName) {
      if (value === null) return 'nil';
      if (typeof value === 'boolean') return String(value);
      if (typeof value === 'number') {
        const s = String(value);
        if (!Number.isFinite(value) || /e/i.test(s)) throw new Error('Tuff has no way to write this number');
        return s;
      }
      if (typeof value === 'string') return str(value);
      if (Array.isArray(value)) {
        const one = oneOf(key);
        return `[${value.map((v) => build(v, one, used, lines, null)).join(', ')}]`;
      }
      const name = rootName || ident(key, used);
      const sets = Object.entries(value).map(([k, v]) => `${name}:set(${str(k)}, ${build(v, k, used, lines, null)})`);
      lines.push(`${name} = tap.data()`, ...sets);
      return name;
    }

    // The body of a POST or PUT. JSON objects and lists are built as Tuff values (tap sends them as JSON);
    // anything else JSON goes as text with a Content-Type header, and plain text as text.
    function bodyLines(req, used) {
      const text = String(req.body ?? '');
      if (!text.trim()) return { lines: [], expr: 'nil' };
      if (req.bodyType === 'json') {
        let value;
        try { value = JSON.parse(text); } catch { return { lines: [], expr: str(text), type: 'application/json' }; }
        if (value && typeof value === 'object') {
          try {
            const lines = [];
            const expr = build(value, 'body', used, lines, 'body');
            if (expr !== 'body') lines.push(`body = ${expr}`);
            return { lines, expr: 'body' };
          } catch { /* a number Tuff can't write: send the JSON as text instead */ }
        }
        return { lines: [], expr: str(JSON.stringify(value)), type: 'application/json' };
      }
      return { lines: [], expr: str(text) };
    }

    const FNS = { GET: 'get', POST: 'post', PUT: 'put', DELETE: 'delete' };

    // headers = ..., body = ..., then res = tap.get(...) (or post, put, delete).
    function requestLines(req, used) {
      const fn = FNS[String(req.method || 'GET').toUpperCase()] || 'get';
      const hdrs = (req.headers || []).map(([n, v]) => [String(n || '').trim(), String(v ?? '')]).filter(([n]) => n);
      const lines = [];
      const args = [str(req.url)];
      if (fn === 'post' || fn === 'put') {
        const b = bodyLines(req, used);
        lines.push(...b.lines);
        args.push(b.expr);
        if (b.type && !hdrs.some(([n]) => n.toLowerCase() === 'content-type')) hdrs.push(['Content-Type', b.type]);
      }
      if (hdrs.length) {
        lines.unshift('headers = tap.data()', ...hdrs.map(([n, v]) => `headers:set(${str(n)}, ${str(v)})`));
        args.push('headers');
      }
      lines.push(`res = tap.${fn}(${args.join(', ')})`);
      return lines;
    }

    // The code for one value. kind: "json" or "text" (what came back). whole: a complete program that
    // checks res:ok and says the value; otherwise just the lines that reach it.
    function code({ req, kind, path = [], value, whole = false }) {
      const used = new Set();
      const head = ['mention tap', ...(whole ? [''] : []), ...requestLines(req, used)];
      const body = [];
      if (kind === 'text') body.push(whole ? 'say res:text' : 'answer = res:text');
      else {
        body.push('data = res:json');
        if (path.length) {
          const v = valueName(path, used);
          body.push(`${v} = ${reach(path)}`);
          if (whole) {
            if (value && typeof value === 'object') body.push(`say ${str(label(path) + ':')}`, `say ${v}`);
            else body.push(`say ${str(label(path) + ': ')} + ${v}`);
          }
        } else if (whole) body.push('say data');
      }
      if (!whole) return [...head, ...body].join('\n') + '\n';
      return [...head, 'if res:ok:', ...body.map((l) => '    ' + l), 'else:', '    say "Something went wrong. The server answered " + res:status'].join('\n') + '\n';
    }

    // A name for a saved program: the value's name, or the website's.
    function fileBase({ req, path = [] }) {
      if (path.length) return valueName(path, new Set());
      let host = '';
      try { host = new URL(req.url).hostname.replace(/^(www|api)\./, '').split('.')[0]; } catch { /* keep "answer" */ }
      return ident(host || 'answer', new Set());
    }

    return { str, ident, reach, code, crumbs, fileBase, TAKEN };
  })();

  // ---------------------------------------------------------------- errors and answers, in plain words
  const Words = (() => {
    const STATUS = {
      200: 'OK', 201: 'Created', 202: 'Accepted', 204: 'No content',
      301: 'Moved', 302: 'Found elsewhere', 304: 'Not changed', 307: 'Moved for now', 308: 'Moved',
      400: 'Bad request', 401: 'Needs a login', 403: 'Not allowed', 404: 'Not found', 405: 'Wrong method',
      408: 'Took too long', 409: 'Clashes', 410: 'Gone', 418: "I'm a teapot", 422: "Couldn't use that", 429: 'Too many requests',
      500: 'Server error', 501: 'Not made yet', 502: 'Bad gateway', 503: 'Not available', 504: 'Took too long',
    };

    const statusName = (code, fallback) => STATUS[code] || fallback || '';

    // One line for an answer that isn't 2xx.
    function why(code, method) {
      if (code === 401) return 'This API wants a login or a key. Its docs say how to get one.';
      if (code === 403) return "The server understood, but won't let you have this.";
      if (code === 404) return "There's nothing at this address. Check the spelling of the part after the website's name.";
      if (code === 405) return `This address doesn't take ${method}. Try another method.`;
      if (code === 429) return 'Too many requests in a short time. Wait a minute, then try again.';
      if (code >= 500) return "Something went wrong on the server, not in your request. Try again later.";
      if (code >= 400) return "The server didn't like the request. Check the address, the headers and the body.";
      if (code >= 300) return 'The answer is somewhere else.';
      return '';
    }

    // An error from t.net.request (Chromium's net:: codes, or the host's own messages) as a title and a line.
    function explain(err, url) {
      const m = String(err?.message || err || '').replace(/^Error invoking remote method '[^']+': (Error: )?/, '');
      let host = 'that website';
      try { host = new URL(url).host || host; } catch { /* keep the words */ }
      const is = (re) => re.test(m);
      if (is(/within 15 seconds|ERR_TIMED_OUT|ERR_CONNECTION_TIMED_OUT/i)) {
        return { kind: 'timeout', title: 'No answer in time', text: `${host} didn't answer within 15 seconds. It might be busy or down. Try again in a moment.` };
      }
      if (is(/ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED|ERR_NETWORK_ACCESS_DENIED|ERR_ADDRESS_UNREACHABLE|ERR_NETWORK_IO_SUSPENDED|ERR_PROXY_CONNECTION_FAILED/i)) {
        return { kind: 'offline', title: 'No internet', text: "TuffCode couldn't reach the internet. Check your Wi-Fi or cable, then try again." };
      }
      if (is(/ERR_NAME_NOT_RESOLVED|ERR_NAME_RESOLUTION_FAILED|ENOTFOUND|EAI_AGAIN/i)) {
        return { kind: 'address', title: "Couldn't find that website", text: `There's no website called ${host}. Check the address for typos. If it's right, check your internet connection.` };
      }
      if (is(/ERR_CONNECTION_REFUSED|ECONNREFUSED/i)) {
        return { kind: 'refused', title: 'Nothing answered', text: `${host} turned the connection down. Check the address, and its port number if it has one.` };
      }
      if (is(/ERR_CERT|ERR_SSL|SSL|certificate/i)) {
        return { kind: 'secure', title: 'Not a safe connection', text: `${host}'s security certificate didn't check out, so TuffCode didn't connect.` };
      }
      if (is(/ERR_CONNECTION_RESET|ERR_CONNECTION_CLOSED|ERR_EMPTY_RESPONSE|ERR_CONNECTION_ABORTED|ECONNRESET/i)) {
        return { kind: 'dropped', title: 'The connection dropped', text: `${host} hung up before it answered. Try again.` };
      }
      if (is(/ERR_TOO_MANY_REDIRECTS/i)) {
        return { kind: 'redirects', title: 'Sent round in circles', text: `${host} kept sending the request somewhere else.` };
      }
      if (is(/Only http|ERR_INVALID_URL|Invalid URL|Failed to parse|ERR_UNSAFE_PORT|ERR_DISALLOWED_URL_SCHEME|ERR_UNKNOWN_URL_SCHEME/i)) {
        return { kind: 'address', title: "That isn't a web address", text: 'A web address starts with http:// or https://, like https://catfact.ninja/fact.' };
      }
      if (is(/header/i)) {
        return { kind: 'headers', title: "Couldn't send those headers", text: 'A header has a name or a value that can\'t be sent. Names use letters, numbers and dashes.' };
      }
      return { kind: 'other', title: "Couldn't send the request", text: m || 'Something went wrong.' };
    }

    // "https://catfact.ninja" -> fixed address, or a plain-words problem.
    function fixUrl(raw) {
      let u = String(raw || '').trim();
      if (!u) return { error: { kind: 'empty', title: 'Type a web address first', text: 'Like https://catfact.ninja/fact, or pick one from Examples.' } };
      if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(u)) {
        if (/^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?([/?#]|$)/i.test(u)) u = `http://${u}`;
        else if (/^[^\s/?#:@]+\.[a-z]{2,}(:\d+)?([/?#]|$)/i.test(u)) u = `https://${u}`;
      }
      let parsed = null;
      try { parsed = new URL(u); } catch { /* below */ }
      if (!parsed || !/^https?:$/.test(parsed.protocol) || !parsed.hostname || /\s/.test(u)) {
        return { error: { kind: 'address', title: "That isn't a web address", text: 'A web address starts with http:// or https://, like https://catfact.ninja/fact.' } };
      }
      return { url: u };
    }

    const size = (bytes) => (bytes < 1000 ? `${bytes} B` : bytes < 1e6 ? `${(bytes / 1000).toFixed(bytes < 1e4 ? 1 : 0)} KB` : `${(bytes / 1e6).toFixed(1)} MB`);
    const time = (ms) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);
    function ago(at, now = Date.now()) {
      const s = Math.max(0, Math.round((now - at) / 1000));
      if (s < 45) return 'just now';
      if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
      if (s < 86400) return `${Math.round(s / 3600)} h ago`;
      const d = Math.round(s / 86400);
      return d === 1 ? 'yesterday' : `${d} days ago`;
    }

    return { statusName, why, explain, fixUrl, size, time, ago };
  })();

  if (typeof TuffPlugins === 'undefined') {
    if (typeof module === 'object' && module.exports) module.exports = { ...Tuff, ...Words };
    return;
  }

  // ---------------------------------------------------------------- the panel
  TuffPlugins.register('api-explorer', (t) => {
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    const METHODS = ['GET', 'POST', 'PUT', 'DELETE'];
    const HAS_BODY = new Set(['POST', 'PUT']);
    const HISTORY_MAX = 20;
    const PAGE = 100; // tree rows shown at a time under one list or data object
    const enc = new TextEncoder();

    // Free, no key needed, and nothing changes: checked by hand, and by the e2e suite when it's online.
    const EXAMPLES = [
      { name: 'A GitHub user', note: 'Who is octocat?', url: 'https://api.github.com/users/octocat' },
      { name: 'A cat fact', note: 'A new fact every time', url: 'https://catfact.ninja/fact' },
      { name: 'A random joke', note: 'A setup and a punchline', url: 'https://official-joke-api.appspot.com/random_joke' },
      { name: 'Weather in London', note: 'The temperature right now', url: 'https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current=temperature_2m' },
      { name: 'A random dog photo', note: 'The web address of a picture', url: 'https://dog.ceo/api/breeds/image/random' },
      { name: 'Three cat facts', note: 'A list to look through', url: 'https://catfact.ninja/facts?limit=3' },
      { name: 'Pikachu', note: 'A big answer with lists inside', url: 'https://pokeapi.co/api/v2/pokemon/pikachu' },
      { name: 'Send a pretend post', note: 'POST with a JSON body. The test server only pretends to save it.', method: 'POST', url: 'https://jsonplaceholder.typicode.com/posts', bodyType: 'json', body: '{\n  "title": "Hello from Tuff",\n  "body": "My first post",\n  "userId": 1\n}' },
    ];

    const ICON = {
      chev: '<svg class="ax-ic" viewBox="0 0 16 16"><path d="M6 4l4 4-4 4"/></svg>',
      x: '<svg class="ax-ic" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
      plus: '<svg class="ax-ic" viewBox="0 0 16 16"><path d="M8 3.5v9M3.5 8h9"/></svg>',
      warn: '<svg class="ax-ic" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/><path d="M8 4.8v3.6M8 10.9v.1"/></svg>',
    };

    const S = {
      method: 'GET', url: '', headers: [], body: '', bodyType: 'json',
      showHeaders: false, showBody: false,
      view: 'examples', sub: 'tree',
      busy: false, started: 0, seq: 0,
      answer: null, error: null,
      sel: null, whole: false,
      open: new Set(), closed: new Set(), more: new Map(),
    };
    let root = null;
    let paths = [];
    let ticker = null;
    const $ = (sel) => root.querySelector(sel);

    const history = () => { const h = t.storage.get('history', []); return Array.isArray(h) ? h : []; };
    const setHistory = (h) => t.storage.set('history', h.slice(0, HISTORY_MAX));

    const panel = t.panel('main', {
      title: 'API Explorer',
      mount(el) {
        root = el;
        el.innerHTML = `<div class="ax">
          <form class="ax-bar" autocomplete="off">
            <select class="ax-method" aria-label="Method">${METHODS.map((m) => `<option>${m}</option>`).join('')}</select>
            <input class="ax-url" type="text" spellcheck="false" placeholder="https://catfact.ninja/fact" aria-label="Web address">
            <button class="ax-send btn sm primary" type="submit">Send</button>
          </form>
          <div class="ax-opts">
            <button type="button" class="ax-opt" data-a="headers">${ICON.chev}Headers<span class="ax-n"></span></button>
            <button type="button" class="ax-opt" data-a="body">${ICON.chev}Body</button>
          </div>
          <div class="ax-edit ax-hdrs hidden">
            <div class="ax-hrows"></div>
            <button type="button" class="ax-link" data-a="add-header">${ICON.plus}Add a header</button>
          </div>
          <div class="ax-edit ax-bodyed hidden">
            <div class="ax-seg ax-btype"><button type="button" data-bt="json">JSON</button><button type="button" data-bt="text">Text</button></div>
            <textarea class="ax-body" spellcheck="false" rows="5" aria-label="Body"></textarea>
            <div class="ax-bodyerr hidden"></div>
          </div>
          <div class="ax-tabs" role="tablist">
            <button type="button" data-v="answer">Answer</button>
            <button type="button" data-v="examples">Examples</button>
            <button type="button" data-v="history">History<span class="ax-n"></span></button>
          </div>
          <div class="ax-main"></div>
          <div class="ax-drawer hidden"></div>
        </div>`;
        wire();
        renderAll();
        return { onShow() { if (!S.url) $('.ax-url').focus(); } };
      },
    });
    t.command('open', 'API Explorer: Open', () => panel.toggle());

    // ---------------------------------------------------------------- events
    function wire() {
      $('.ax-bar').addEventListener('submit', (e) => { e.preventDefault(); send(); });
      $('.ax-method').addEventListener('change', (e) => setMethod(e.target.value));
      $('.ax-url').addEventListener('input', (e) => { S.url = e.target.value; });
      $('.ax-opts').addEventListener('click', (e) => {
        const a = e.target.closest('button')?.dataset.a;
        if (a === 'headers') { S.showHeaders = !S.showHeaders; if (S.showHeaders && !S.headers.length) S.headers.push({ name: '', value: '' }); renderEditors(); }
        if (a === 'body') { S.showBody = !S.showBody; renderEditors(); }
      });
      $('.ax-hdrs').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        if (b.dataset.a === 'add-header') { S.headers.push({ name: '', value: '' }); renderEditors(); root.querySelector('.ax-hrow:last-child input')?.focus(); }
        if (b.dataset.a === 'del-header') { S.headers.splice(+b.closest('.ax-hrow').dataset.i, 1); renderEditors(); }
      });
      $('.ax-hdrs').addEventListener('input', (e) => {
        const row = e.target.closest('.ax-hrow');
        if (row) S.headers[+row.dataset.i][e.target.dataset.f] = e.target.value;
        renderOpts();
      });
      $('.ax-hdrs').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); send(); } });
      $('.ax-btype').addEventListener('click', (e) => { const bt = e.target.closest('button')?.dataset.bt; if (bt) { S.bodyType = bt; renderEditors(); } });
      $('.ax-body').addEventListener('input', (e) => { S.body = e.target.value; $('.ax-bodyerr').classList.add('hidden'); });
      $('.ax-body').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); }
        if (e.key === 'Tab' && !e.shiftKey) { e.preventDefault(); document.execCommand('insertText', false, '  '); }
      });
      $('.ax-tabs').addEventListener('click', (e) => { const v = e.target.closest('button')?.dataset.v; if (v) { S.view = v; renderTabs(); renderMain(); } });
      $('.ax-main').addEventListener('click', onMainClick);
      $('.ax-main').addEventListener('keydown', onTreeKey);
      $('.ax-drawer').addEventListener('click', onDrawerClick);
    }

    function setMethod(m) {
      S.method = METHODS.includes(m) ? m : 'GET';
      if (HAS_BODY.has(S.method)) S.showBody = true;
      renderBar();
      renderEditors();
    }

    function onMainClick(e) {
      const b = e.target.closest('button');
      if (b?.dataset.sub) { S.sub = b.dataset.sub; renderMain(); return; }
      if (b?.dataset.a === 'retry') { send(); return; }
      if (b?.dataset.a === 'clear-history') { setHistory([]); renderTabs(); renderMain(); t.toast('History cleared.', 'ok', 1500); return; }
      if (b?.dataset.a === 'code-all') { select([], S.answer.isJson ? S.answer.json : S.answer.text, null); return; }
      if (b?.dataset.a === 'more') { const key = b.dataset.key; S.more.set(key, (S.more.get(key) || PAGE) + PAGE); refill(b.closest('.ax-kids')); return; }
      const ex = e.target.closest('[data-ex]');
      if (ex) { load(EXAMPLES[+ex.dataset.ex]); send(); return; }
      const h = e.target.closest('[data-h]');
      if (h) {
        const item = history()[+h.dataset.h];
        if (!item) return;
        load(item);
        // A GET only reads, so it goes again straight away. Anything else waits for Send, and so does a
        // request whose key or password wasn't kept.
        if (item.blanked) { S.showHeaders = true; renderEditors(); t.toast('Fill in the key or password again, then press Send.', 'info', 3500); }
        else if (item.method === 'GET') send();
        else { $('.ax-url').focus(); t.toast(`Loaded. Press Send to send this ${item.method} again.`, 'info', 2500); }
        return;
      }
      const row = e.target.closest('.ax-row');
      if (!row) return;
      if (e.target.closest('.ax-tog') && row.classList.contains('box')) { toggle(row); return; }
      const path = paths[+row.dataset.p];
      select(path, valueAt(path), row);
    }

    function onTreeKey(e) {
      const row = e.target.closest?.('.ax-row');
      if (!row) return;
      const rows = [...root.querySelectorAll('.ax-tree .ax-row')];
      const i = rows.indexOf(row);
      const go = (r) => { if (r) { r.focus(); e.preventDefault(); } };
      if (e.key === 'ArrowDown') go(rows[i + 1]);
      else if (e.key === 'ArrowUp') go(rows[i - 1]);
      else if (e.key === 'ArrowRight' && row.classList.contains('box') && !row.classList.contains('open')) { toggle(row); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') {
        if (row.classList.contains('open')) { toggle(row); e.preventDefault(); } else go(row.parentElement.closest('.ax-kids')?.previousElementSibling);
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const path = paths[+row.dataset.p];
        select(path, valueAt(path), row);
      }
    }

    async function onDrawerClick(e) {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.m) { S.whole = b.dataset.m === 'whole'; renderDrawer(); return; }
      const a = b.dataset.a;
      if (a === 'close-code') { S.sel = null; root.querySelector('.ax-row.sel')?.classList.remove('sel'); renderDrawer(); return; }
      const code = currentCode();
      if (a === 'copy') {
        try { await navigator.clipboard.writeText(code); t.toast('Copied.', 'ok', 1500); } catch { t.toast("Couldn't copy. Select the code and press Ctrl+C.", 'error'); }
      }
      if (a === 'insert') {
        // A file that already mentions tap doesn't need it again.
        const has = /^[ \t]*(mention|import)[ \t]+tap\b/m.test(t.editor.code() || '');
        const text = has ? code.replace(/^mention tap\n\n?/, '') : code;
        if (await t.editor.insert(text)) t.toast(S.whole ? 'Inserted the program.' : 'Inserted.', 'ok', 1500);
      }
      if (a === 'save') saveProgram(code);
    }

    // ---------------------------------------------------------------- sending
    function load(item) {
      S.method = METHODS.includes(item.method) ? item.method : 'GET';
      S.url = item.url || '';
      S.headers = (item.headers || []).map(([name, value]) => ({ name, value }));
      S.body = item.body || '';
      S.bodyType = item.bodyType === 'text' ? 'text' : 'json';
      S.showHeaders = S.headers.length > 0;
      S.showBody = HAS_BODY.has(S.method);
      $('.ax-url').value = S.url;
      $('.ax-body').value = S.body;
      renderBar();
      renderEditors();
    }

    function bodyProblem() {
      if (!HAS_BODY.has(S.method) || S.bodyType !== 'json' || !S.body.trim()) return null;
      try { JSON.parse(S.body); return null; } catch (err) {
        const where = /line (\d+) column (\d+)/.exec(err.message);
        return `This isn't JSON yet${where ? ` (look at line ${where[1]}, letter ${where[2]})` : ''}. Names and text need "double quotes", with commas between the values. Or pick Text to send it as it is.`;
      }
    }

    async function send() {
      if (S.busy) return;
      S.url = $('.ax-url').value;
      const fixed = Words.fixUrl(S.url);
      if (fixed.error) { showError(fixed.error, null); return; }
      if (fixed.url !== S.url.trim()) $('.ax-url').value = fixed.url;
      S.url = fixed.url;
      const headerRows = S.headers.map((h) => [h.name.trim(), h.value]).filter(([n]) => n);
      const bad = headerRows.find(([n, v]) => !/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(n) || /[\r\n]/.test(v));
      if (bad) { showError({ kind: 'headers', title: "Couldn't send those headers", text: `"${bad[0]}" can't be sent. Header names use letters, numbers and dashes, like Accept or X-Api-Key.` }, null); return; }
      const problem = bodyProblem();
      if (problem) { S.showBody = true; renderEditors(); const box = $('.ax-bodyerr'); box.textContent = problem; box.classList.remove('hidden'); $('.ax-body').focus(); return; }

      const withBody = HAS_BODY.has(S.method) && S.body !== '';
      const req = { method: S.method, url: S.url, headers: headerRows, body: HAS_BODY.has(S.method) ? S.body : '', bodyType: S.bodyType };
      const headers = Object.fromEntries(headerRows);
      if (withBody && !headerRows.some(([n]) => n.toLowerCase() === 'content-type')) headers['Content-Type'] = S.bodyType === 'json' ? 'application/json' : 'text/plain; charset=utf-8';

      const seq = ++S.seq;
      S.busy = true;
      S.started = Date.now();
      S.error = null;
      S.sel = null;
      S.view = 'answer';
      renderAll();
      clearInterval(ticker);
      ticker = setInterval(() => { const s = root.querySelector('.ax-secs'); if (s) s.textContent = `${Math.floor((Date.now() - S.started) / 1000)} s`; }, 500);
      let res = null;
      let err = null;
      try {
        res = await t.net.request({ url: req.url, method: req.method, headers, body: withBody ? S.body : undefined });
      } catch (e) {
        err = e;
      }
      if (seq !== S.seq) return;
      clearInterval(ticker);
      S.busy = false;
      if (err) {
        const ex = Words.explain(err, req.url);
        showError(ex, req);
        remember(req, { error: ex.title });
        return;
      }
      S.answer = makeAnswer(req, res);
      S.open = new Set();
      S.closed = new Set();
      S.more = new Map();
      S.sub = 'tree';
      remember(req, { status: res.status, ms: res.ms });
      renderAll();
    }

    function makeAnswer(req, res) {
      const text = String(res.text ?? '');
      const type = Object.entries(res.headers || {}).find(([k]) => k.toLowerCase() === 'content-type')?.[1] || '';
      let json;
      let isJson = false;
      if (text.trim() && (/json/i.test(type) || /^\s*[[{]/.test(text))) {
        try { json = JSON.parse(text); isJson = true; } catch { /* shown as text */ }
      }
      return { req, status: res.status, statusText: res.statusText, ok: res.ok, ms: res.ms, bytes: enc.encode(text).length, cut: !!res.cut, headers: res.headers || {}, type, text, json, isJson };
    }

    function showError(ex, req) {
      S.error = { ...ex, req };
      S.answer = null;
      S.sel = null;
      S.view = 'answer';
      renderAll();
    }

    // History lives in TuffCode's settings file, so keys and passwords in headers aren't kept: their
    // names are, with an empty value to fill in again.
    const SECRET = /authorization|cookie|token|secret|password|api[-_]?key|^x-.*key$/i;
    function remember(req, result) {
      const same = (h) => h.method === req.method && h.url === req.url && (h.body || '') === (req.body || '');
      const headers = req.headers.map(([n, v]) => [n, SECRET.test(n) ? '' : v]);
      const item = { method: req.method, url: req.url, headers, body: (req.body || '').slice(0, 20000), bodyType: req.bodyType, ...result, at: Date.now() };
      if (headers.some(([n, v], i) => v !== req.headers[i][1])) item.blanked = true;
      setHistory([item, ...history().filter((h) => !same(h))]);
      renderTabs();
    }

    // ---------------------------------------------------------------- code
    function select(path, value, row) {
      root.querySelector('.ax-row.sel')?.classList.remove('sel');
      row?.classList.add('sel');
      S.sel = { path, value };
      renderDrawer();
    }

    function currentCode() {
      const a = S.answer;
      if (!a || !S.sel) return '';
      return Tuff.code({ req: a.req, kind: a.isJson ? 'json' : 'text', path: S.sel.path, value: S.sel.value, whole: S.whole });
    }

    async function saveProgram(code) {
      if (!t.project.write) { t.toast('Saving files needs the "files" permission.', 'error'); return; }
      if (!t.project.root()) { t.toast('Open a folder first.', 'error'); return; }
      const base = Tuff.fileBase({ req: S.answer.req, path: S.sel.path });
      const names = new Set((await t.project.files()).map((f) => String(f.rel).replace(/\\/g, '/').toLowerCase()));
      let name = `${base}.tuf`;
      for (let i = 2; names.has(name.toLowerCase()); i++) name = `${base}_${i}.tuf`;
      try {
        const saved = await t.project.write(name, code);
        await t.openFile(saved);
        t.toast(`Saved ${name}. Press Run to try it.`, 'ok', 3000);
      } catch (err) {
        t.toast(`Couldn't save ${name}: ${String(err.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, '')}`, 'error', 5000);
      }
    }

    // ---------------------------------------------------------------- drawing
    function renderAll() { renderBar(); renderEditors(); renderTabs(); renderMain(); renderDrawer(); }

    function renderBar() {
      $('.ax-method').value = S.method;
      if ($('.ax-url').value !== S.url) $('.ax-url').value = S.url;
      const b = $('.ax-send');
      b.disabled = S.busy;
      b.textContent = S.busy ? 'Sending…' : 'Send';
    }

    function renderOpts() {
      const n = S.headers.filter((h) => h.name.trim()).length;
      const opts = $('.ax-opts');
      opts.querySelector('[data-a="headers"] .ax-n').textContent = n ? ` ${n}` : '';
      opts.querySelector('[data-a="headers"]').classList.toggle('on', S.showHeaders);
      const bodyBtn = opts.querySelector('[data-a="body"]');
      bodyBtn.classList.toggle('hidden', !HAS_BODY.has(S.method));
      bodyBtn.classList.toggle('on', S.showBody);
    }

    function renderEditors() {
      renderOpts();
      $('.ax-hdrs').classList.toggle('hidden', !S.showHeaders);
      $('.ax-hrows').innerHTML = S.headers.map((h, i) => `<div class="ax-hrow" data-i="${i}">
          <input data-f="name" spellcheck="false" placeholder="Name" aria-label="Header name" value="${esc(h.name)}">
          <input data-f="value" spellcheck="false" placeholder="Value" aria-label="Header value" value="${esc(h.value)}">
          <button type="button" class="ax-ib" data-a="del-header" title="Remove this header" aria-label="Remove this header">${ICON.x}</button>
        </div>`).join('');
      const showBody = S.showBody && HAS_BODY.has(S.method);
      $('.ax-bodyed').classList.toggle('hidden', !showBody);
      root.querySelectorAll('.ax-btype button').forEach((b) => b.classList.toggle('on', b.dataset.bt === S.bodyType));
      const ta = $('.ax-body');
      if (ta.value !== S.body) ta.value = S.body;
      ta.placeholder = S.bodyType === 'json' ? '{ "title": "Hello" }' : 'Some text to send';
    }

    function renderTabs() {
      root.querySelectorAll('.ax-tabs button').forEach((b) => {
        b.classList.toggle('on', b.dataset.v === S.view);
        b.setAttribute('role', 'tab');
        b.setAttribute('aria-selected', String(b.dataset.v === S.view));
      });
      const n = history().length;
      $('.ax-tabs [data-v="history"] .ax-n').textContent = n ? ` ${n}` : '';
    }

    function renderMain() {
      const main = $('.ax-main');
      main.scrollTop = 0;
      if (S.view === 'examples') main.innerHTML = examplesHtml();
      else if (S.view === 'history') main.innerHTML = historyHtml();
      else renderAnswer(main);
    }

    function examplesHtml() {
      return `<div class="ax-note">Free web APIs that need no key. Click one to send it.</div>
        <div class="ax-list">${EXAMPLES.map((ex, i) => `<button type="button" class="ax-item" data-ex="${i}">
          <span class="ax-item-h"><b>${esc(ex.name)}</b><span class="ax-meth m-${(ex.method || 'GET').toLowerCase()}">${ex.method || 'GET'}</span></span>
          <span class="ax-item-s">${esc(ex.note)}</span>
          <span class="ax-item-u">${esc(ex.url.replace(/^https?:\/\//, ''))}</span>
        </button>`).join('')}</div>`;
    }

    function historyHtml() {
      const h = history();
      if (!h.length) return '<div class="ax-empty">Nothing here yet. The last 20 requests you send show up here.</div>';
      const now = Date.now();
      return `<div class="ax-list">${h.map((item, i) => {
        const status = item.error ? `<span class="ax-hs bad">${esc(item.error)}</span>` : `<span class="ax-hs ${klass(item.status)}">${esc(item.status)}</span>`;
        return `<button type="button" class="ax-item ax-hitem" data-h="${i}" title="${esc(item.url)}">
          <span class="ax-item-h"><span class="ax-meth m-${esc(String(item.method).toLowerCase())}">${esc(item.method)}</span><span class="ax-item-u">${esc(String(item.url).replace(/^https?:\/\//, ''))}</span></span>
          <span class="ax-item-s">${status}<span>${esc(Words.ago(item.at, now))}</span>${item.ms != null ? `<span>${esc(Words.time(item.ms))}</span>` : ''}</span>
        </button>`;
      }).join('')}</div>
      <div class="ax-foot"><button type="button" class="btn sm" data-a="clear-history">Clear history</button></div>`;
    }

    const klass = (code) => (code >= 200 && code < 300 ? 'ok' : code >= 400 ? 'bad' : 'mid');

    function renderAnswer(main) {
      if (S.busy) {
        main.innerHTML = `<div class="ax-wait"><span>Waiting for an answer from ${esc(hostOf(S.url))}</span><span class="ax-secs">0 s</span></div>`;
        return;
      }
      if (S.error) {
        main.innerHTML = `<div class="ax-err" data-kind="${esc(S.error.kind)}">
          <div class="ax-err-h">${ICON.warn}<b>${esc(S.error.title)}</b></div>
          <p>${esc(S.error.text)}</p>
          ${S.error.req ? '<div><button type="button" class="btn sm" data-a="retry">Try again</button></div>' : ''}
        </div>`;
        return;
      }
      const a = S.answer;
      if (!a) {
        main.innerHTML = '<div class="ax-empty">Nothing sent yet. Type a web address and press Send, or pick one from Examples.</div>';
        return;
      }
      const name = Words.statusName(a.status, a.statusText);
      const why = a.ok ? '' : Words.why(a.status, a.req.method);
      const nHeaders = Object.keys(a.headers).length;
      const subs = [[a.isJson ? 'tree' : 'text', a.isJson ? 'Tree' : 'Text'], ...(a.isJson ? [['raw', 'Raw']] : []), ['headers', `Headers <span class="ax-n">${nHeaders}</span>`]];
      if (!subs.some(([id]) => id === S.sub)) S.sub = subs[0][0];
      main.innerHTML = `<div class="ax-status">
          <span class="ax-code ${klass(a.status)}">${esc(a.status)}${name ? ` ${esc(name)}` : ''}</span>
          <span class="ax-meta">${esc(Words.time(a.ms))}</span><span class="ax-meta">${esc(Words.size(a.bytes))}</span>
          <button type="button" class="ax-link ax-codeall" data-a="code-all">Tuff code</button>
        </div>
        ${why ? `<p class="ax-why">${esc(why)}</p>` : ''}
        <div class="ax-sub">${subs.map(([id, label]) => `<button type="button" data-sub="${id}" class="${S.sub === id ? 'on' : ''}">${label}</button>`).join('')}</div>
        <div class="ax-view"></div>`;
      const view = main.querySelector('.ax-view');
      const cut = a.cut ? '<div class="ax-note">The answer was too big, so only its first 2 MB are shown.</div>' : '';
      if (S.sub === 'tree') {
        paths = [];
        view.innerHTML = '<div class="ax-note">Click a value to get the Tuff code that reaches it.</div><div class="ax-tree" role="tree"></div>';
        const tree = view.querySelector('.ax-tree');
        tree.append(node(undefined, a.json, [], 0));
        tree.querySelector('.ax-row').tabIndex = 0;
        if (S.sel) {
          const k = JSON.stringify(S.sel.path);
          const i = paths.findIndex((p) => JSON.stringify(p) === k);
          if (i >= 0) tree.querySelector(`.ax-row[data-p="${i}"]`)?.classList.add('sel');
        }
      } else if (S.sub === 'text' || S.sub === 'raw') {
        view.innerHTML = `${cut}<pre class="ax-raw"></pre>`;
        const shown = a.text.length > 300000 ? `${a.text.slice(0, 300000)}\n…` : a.text;
        view.querySelector('pre').textContent = shown || '(The answer is empty.)';
        view.querySelector('pre').classList.toggle('empty', !shown);
      } else {
        view.innerHTML = `<div class="ax-heads">${Object.entries(a.headers).map(([k, v]) => `<div><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join('') || '<div class="ax-empty">No headers came back.</div>'}</div>`;
      }
    }

    const hostOf = (u) => { try { return new URL(u).host; } catch { return 'the server'; } };

    // ---------------------------------------------------------------- the JSON tree
    const isBox = (v) => v !== null && typeof v === 'object';
    const pkey = (path) => JSON.stringify(path);
    const count = (v) => (Array.isArray(v) ? v.length : Object.keys(v).length);
    const isOpen = (path, depth, v) => S.open.has(pkey(path)) || (!S.closed.has(pkey(path)) && (depth === 0 || (depth === 1 && count(v) <= 25)));

    function valueAt(path) {
      let v = S.answer?.json;
      for (const s of path) v = v == null ? undefined : 'i' in s ? v[s.i] : v[s.k];
      return v;
    }

    function span(cls, text) {
      const s = document.createElement('span');
      s.className = cls;
      s.textContent = text;
      return s;
    }

    function valueSpan(v) {
      if (v === null) return span('ax-v nil', 'nil');
      if (Array.isArray(v)) return span('ax-v sum', v.length ? `[ ${v.length} item${v.length === 1 ? '' : 's'} ]` : '[ empty list ]');
      if (typeof v === 'object') { const n = count(v); return span('ax-v sum', n ? `{ ${n} value${n === 1 ? '' : 's'} }` : '{ empty }'); }
      if (typeof v === 'string') return span('ax-v str', JSON.stringify(v.length > 400 ? `${v.slice(0, 400)}…` : v));
      if (typeof v === 'number') return span('ax-v num', String(v));
      return span('ax-v bool', String(v));
    }

    function node(key, v, path, depth) {
      const wrap = document.createElement('div');
      wrap.className = 'ax-node';
      const row = document.createElement('div');
      row.className = 'ax-row' + (isBox(v) ? ' box' : '');
      row.style.setProperty('--d', depth);
      row.dataset.p = paths.push(path) - 1;
      row.tabIndex = -1;
      row.setAttribute('role', 'treeitem');
      const tog = span('ax-tog', '');
      if (isBox(v)) tog.innerHTML = ICON.chev;
      row.append(tog);
      if (key !== undefined) {
        row.append(span(typeof key === 'number' ? 'ax-k ax-i' : 'ax-k', String(key)));
        row.append(span('ax-colon', ':'));
      }
      const val = valueSpan(v);
      if (typeof v === 'string' && v.length > 40) row.title = v.length > 2000 ? `${v.slice(0, 2000)}…` : v;
      row.append(val);
      wrap.append(row);
      if (isBox(v)) {
        const kids = document.createElement('div');
        kids.className = 'ax-kids';
        kids.setAttribute('role', 'group');
        wrap.append(kids);
        if (isOpen(path, depth, v)) { row.classList.add('open'); row.setAttribute('aria-expanded', 'true'); fill(kids, v, path, depth + 1); } else row.setAttribute('aria-expanded', 'false');
      }
      return wrap;
    }

    function fill(kids, v, path, depth) {
      kids.textContent = '';
      const keys = Array.isArray(v) ? v.map((_, i) => i) : Object.keys(v);
      const limit = S.more.get(pkey(path)) || PAGE;
      const frag = document.createDocumentFragment();
      for (const k of keys.slice(0, limit)) frag.append(node(k, v[k], [...path, typeof k === 'number' ? { i: k } : { k }], depth));
      if (keys.length > limit) {
        const more = document.createElement('button');
        more.type = 'button';
        more.className = 'ax-more';
        more.style.setProperty('--d', depth);
        more.dataset.a = 'more';
        more.dataset.key = pkey(path);
        more.textContent = `Show ${Math.min(PAGE, keys.length - limit)} more (${keys.length.toLocaleString()} in all)`;
        frag.append(more);
      }
      kids.append(frag);
      kids.dataset.depth = depth;
    }

    function refill(kids) {
      const row = kids.previousElementSibling;
      const path = paths[+row.dataset.p];
      fill(kids, valueAt(path), path, +kids.dataset.depth);
    }

    function toggle(row) {
      const path = paths[+row.dataset.p];
      const k = pkey(path);
      const kids = row.nextElementSibling;
      if (row.classList.contains('open')) {
        row.classList.remove('open');
        row.setAttribute('aria-expanded', 'false');
        kids.textContent = '';
        S.open.delete(k);
        S.closed.add(k);
      } else {
        row.classList.add('open');
        row.setAttribute('aria-expanded', 'true');
        S.closed.delete(k);
        S.open.add(k);
        fill(kids, valueAt(path), path, +row.style.getPropertyValue('--d') + 1);
      }
    }

    // ---------------------------------------------------------------- the code drawer
    const HL_WORDS = new Set(['mention', 'import', 'if', 'else', 'elif', 'say', 'not', 'and', 'or', 'true', 'false', 'nil', 'func', 'return', 'for', 'in', 'while']);
    function highlight(code) {
      let out = '';
      let prev = '';
      const re = /"(?:\\.|[^"\\])*"|\b\d+(?:\.\d+)?\b|[A-Za-z_]\w*|[\s\S]/g;
      let m;
      while ((m = re.exec(code))) {
        const s = m[0];
        if (s[0] === '"') out += `<span class="s">${esc(s)}</span>`;
        else if (/^\d/.test(s)) out += `<span class="n">${s}</span>`;
        else if (/^[A-Za-z_]/.test(s)) out += HL_WORDS.has(s) ? `<span class="k">${s}</span>` : prev === ':' || prev === '.' ? `<span class="f">${s}</span>` : s === 'tap' ? `<span class="l">${s}</span>` : s;
        else out += esc(s);
        prev = s;
      }
      return out;
    }

    // One block per line, so a long line wraps under itself (indented a bit further) instead of
    // scrolling sideways in a narrow sidebar. Copy and Insert use the real lines.
    const codeLines = (code) => code.replace(/\n$/, '').split('\n')
      .map((line) => `<span class="ln" style="--i:${line.length - line.trimStart().length}">${highlight(line)}</span>`).join('');

    function renderDrawer() {
      const d = $('.ax-drawer');
      const a = S.answer;
      if (!S.sel || !a) { d.classList.add('hidden'); d.innerHTML = ''; return; }
      const code = currentCode();
      const listed = S.sel.path.some((s) => 'i' in s);
      d.classList.remove('hidden');
      d.innerHTML = `<div class="ax-dh">
          <b>Tuff code</b><span class="ax-path" title="${esc(Tuff.crumbs(S.sel.path))}">${esc(Tuff.crumbs(S.sel.path))}</span>
          <button type="button" class="ax-ib" data-a="close-code" title="Close" aria-label="Close">${ICON.x}</button>
        </div>
        <div class="ax-seg ax-mode"><button type="button" data-m="short" class="${S.whole ? '' : 'on'}">Short</button><button type="button" data-m="whole" class="${S.whole ? 'on' : ''}">Whole program</button></div>
        <pre class="ax-pre"><code>${codeLines(code)}</code></pre>
        ${listed ? '<div class="ax-note ax-tip">Tuff lists start at 0, so [0] is the first item and [1] the second.</div>' : ''}
        <div class="ax-dbtns">
          <button type="button" class="btn sm" data-a="copy">Copy</button>
          <button type="button" class="btn sm primary" data-a="insert">Insert</button>
          ${S.whole ? '<button type="button" class="btn sm" data-a="save">Save as new file</button>' : ''}
        </div>`;
    }

    return () => clearInterval(ticker);
  });
})();
