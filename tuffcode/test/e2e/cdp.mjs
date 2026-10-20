// Tiny Chrome DevTools Protocol driver for the e2e suites: connects to a TuffCode started by launch.mjs
// and drives it like a person would (real key presses, mouse moves and clicks), checking the page as it goes.
// No packages needed: Node 22+ has WebSocket built in.
import fs from 'node:fs';
import path from 'node:path';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const KEYS = {
  Enter: { key: 'Enter', code: 'Enter', keyCode: 13, text: '\r' },
  Backspace: { key: 'Backspace', code: 'Backspace', keyCode: 8 },
  Escape: { key: 'Escape', code: 'Escape', keyCode: 27 },
  Tab: { key: 'Tab', code: 'Tab', keyCode: 9 },
  ArrowDown: { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40 },
  ArrowUp: { key: 'ArrowUp', code: 'ArrowUp', keyCode: 38 },
  Shift: { key: 'Shift', code: 'ShiftLeft', keyCode: 16 },
  Delete: { key: 'Delete', code: 'Delete', keyCode: 46 },
  End: { key: 'End', code: 'End', keyCode: 35 },
  Home: { key: 'Home', code: 'Home', keyCode: 36 },
};
// The editing command each key does in a Mac text box (see key() below).
const MAC_EDITING = { Backspace: ['deleteBackward'], Delete: ['deleteForward'] };

// The IDE has loaded: folder open, editor and plugins ready, intro and boot fade done. Clicks through
// the intro if it plays (it does once per version, and the scratch settings don't say which one was seen).
const READY = `(() => {
  const intro = document.querySelector('#intro');
  if (intro && !intro.classList.contains('hidden')) { document.querySelector('#intro-start')?.click(); return 'intro'; }
  return !!(window.TuffIDE?.root?.() && window.monaco && document.querySelector('#tree .tree-row') && !document.body.classList.contains('booting') && document.querySelector('#pl-refresh')?.onclick) ? 'ready' : 'loading';
})()`;

async function findPage(port, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = targets.find((x) => x.type === 'page' && x.url.includes('index.html'));
      if (page) return page;
    } catch {}
    await sleep(500);
  }
  throw new Error(`No TuffCode window on DevTools port ${port} after ${ms / 1000} s`);
}

// app: what launch() returned (port, out). Resolves to the driver `t` the suites get.
export async function connect(app, { timeout = 90000 } = {}) {
  const page = await findPage(app.port, timeout);
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = () => j(new Error('Could not connect to the TuffCode window')); });
  const events = [];
  const pending = new Map();
  let id = 0;
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) {
      events.push(`[console.${msg.params.type}] ` + msg.params.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 400));
    } else if (msg.method === 'Runtime.exceptionThrown') {
      events.push('[exception] ' + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text).slice(0, 400));
    }
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject, timer } = pending.get(msg.id);
      clearTimeout(timer);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    }
  };
  ws.onclose = () => { for (const p of pending.values()) { clearTimeout(p.timer); p.reject(new Error('The TuffCode window closed')); } pending.clear(); };
  // A page that never answers fails the call instead of hanging the run.
  const send = (method, params = {}, ms = 60000) => new Promise((resolve, reject) => {
    const mid = ++id;
    const timer = setTimeout(() => { pending.delete(mid); reject(new Error(`${method}: no answer after ${ms / 1000} s`)); }, ms);
    pending.set(mid, { resolve, reject, timer });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  await send('Runtime.enable');

  const t = {
    send,
    sleep,
    events,
    async eval(expr) {
      const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    },
    async waitFor(js, ms = 8000, every = 150) {
      const end = Date.now() + ms;
      while (Date.now() < end) { if (await t.eval(js)) return true; await sleep(every); }
      return false;
    },
    async ready(ms = 60000) {
      const end = Date.now() + ms;
      while (Date.now() < end) {
        let state = null;
        try { state = await t.eval(READY); } catch {}
        if (state === 'ready') {
          // The suites were written for the default 1400 x 880 window. On a smaller screen (a CI machine's)
          // Windows shrinks the window, so the page is laid out at that size instead.
          const [w, h] = await t.eval('[innerWidth, innerHeight]');
          if (w < 1400 || h < 880) await send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 880, deviceScaleFactor: 0, mobile: false });
          return;
        }
        await sleep(300);
      }
      throw new Error(`The IDE didn't finish loading in ${ms / 1000} s`);
    },
    // Reload the renderer (like Ctrl+R) and wait until the IDE is back.
    async reload() {
      await send('Page.reload', { ignoreCache: true });
      await sleep(1500);
      await t.ready();
      await sleep(1000);
    },
    // Ask for the window to come to the front. Resolves to whether the page has focus now.
    async focus() {
      try { await send('Page.bringToFront'); } catch {}
      for (let i = 0; i < 20; i++) { if (await t.eval('document.hasFocus()')) return true; await sleep(100); }
      return false;
    },
    async key(name, mods = 0) {
      const k = KEYS[name] || { key: name, code: 'Key' + name.toUpperCase(), keyCode: name.toUpperCase().charCodeAt(0) };
      // On a Mac, Chromium leaves editing in text boxes (select all, Backspace, Delete) to macOS, which never sees
      // these made-up key presses. Naming the editing command makes them work there as they do on Windows.
      // (Modifiers: 2 is Ctrl, 4 is Cmd.)
      const commands = process.platform !== 'darwin' ? undefined
        : name.toLowerCase() === 'a' && mods & 6 ? ['selectAll'] : !mods ? MAC_EDITING[name] : undefined;
      await send('Input.dispatchKeyEvent', { type: k.text ? 'keyDown' : 'rawKeyDown', modifiers: mods, windowsVirtualKeyCode: k.keyCode, key: k.key, code: k.code, text: mods ? undefined : k.text, commands });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', modifiers: mods, windowsVirtualKeyCode: k.keyCode, key: k.key, code: k.code });
      await sleep(60);
    },
    async type(text, delay = 80) {
      for (const ch of text) {
        if (ch === '\n') { await t.key('Enter'); continue; }
        await send('Input.dispatchKeyEvent', { type: 'keyDown', key: ch, text: ch, unmodifiedText: ch });
        await send('Input.dispatchKeyEvent', { type: 'keyUp', key: ch });
        await sleep(delay);
      }
    },
    async click(x, y) {
      await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
      await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
      await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
      await sleep(120);
    },
    async move(x, y) { await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y }); await sleep(120); },
    // Screenshot into this suite's out folder (a bare name) or anywhere (a full path). clip: { x, y, width, height[, scale] }.
    // A clip that doesn't fit the window falls back to the whole window: screenshots are for people, not checks.
    async shot(file, clip) {
      let r;
      try { r = await send('Page.captureScreenshot', { format: 'png', ...(clip ? { clip: { scale: 1, ...clip } } : {}) }); } catch {}
      if (!r?.data) r = await send('Page.captureScreenshot', { format: 'png' });
      const dest = path.isAbsolute(file) ? file : path.join(app.out, file);
      fs.writeFileSync(dest, Buffer.from(r.data, 'base64'));
      return dest;
    },
    // Monaco helpers
    async setCode(code) { await t.eval(`window.monaco.editor.getEditors()[0].getModel().setValue(${JSON.stringify(code)})`); },
    async code() { return t.eval(`window.monaco.editor.getEditors()[0].getModel().getValue()`); },
    async cursorEnd() { await t.eval(`(() => { const e = window.monaco.editor.getEditors()[0]; const m = e.getModel(); const l = m.getLineCount(); e.setPosition({ lineNumber: l, column: m.getLineMaxColumn(l) }); e.focus(); })()`); },
    async suggestOpen() { return t.eval(`!!document.querySelector('.suggest-widget.visible')`); },
    async suggestions() { return t.eval(`[...document.querySelectorAll('.suggest-widget.visible .monaco-list-row')].map(r => r.getAttribute('aria-label') || r.textContent).slice(0, 8)`); },
    close() { try { ws.close(); } catch {} },
  };
  return t;
}
