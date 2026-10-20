"""Run one real .tuf program in a real atgui window, drive it from inside the page, and report.

    py -3 drive.py program.tuf [--driver driver.js] [--out result.json] [--shots folder] [--timeout 40]

The program runs exactly as `tuff.py program.tuf` runs it (through tuff_view.run). This script only wraps
tuff_view.View so that, when the window opens, it can add a driver script to the page. The driver clicks,
types and presses keys with real DOM events (so they go through the engine's bridge and atgui's handlers,
like a person's would), and can ask for screenshots, which WebView2 takes through the DevTools protocol.

Driver scripts get `T` (helpers, below) and `tv` (the engine). They end with T.done(result); a program
that drives itself (app:after + app:close) needs no driver at all.

Result JSON: {code, stdout, stderr, result, seconds, ready_s, painted_s, shots, page}
"""
import base64
import io
import json
import os
import sys
import threading
import time

STARTED = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)

import tuff  # noqa: E402
import tuff_view  # noqa: E402

HELPERS = r"""
const T = window.__T = {
  q: (s) => document.querySelector(s),
  qa: (s) => [...document.querySelectorAll(s)],
  wait: (ms) => new Promise((r) => setTimeout(r, ms)),
  frame: () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  async until(fn, ms = 4000) {
    const t0 = performance.now();
    while (performance.now() - t0 < ms) { let v = null; try { v = fn(); } catch (e) { v = null; } if (v) return v; await T.wait(8); }
    return null;
  },
  find(sel, text) {
    const all = T.qa(sel);
    return all.find((e) => e.textContent.trim() === text) || all.find((e) => e.textContent.includes(text)) || null;
  },
  point(el) { const r = el.getBoundingClientRect(); return { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, bubbles: true, composed: true }; },
  click(el, opts = {}) {
    const p = { ...T.point(el), ...opts };
    el.dispatchEvent(new PointerEvent('pointerdown', p));
    el.dispatchEvent(new PointerEvent('pointerup', p));
    el.click();
  },
  dblclick(el) { el.dispatchEvent(new MouseEvent('dblclick', T.point(el))); },
  right(el) { const p = T.point(el); el.dispatchEvent(new PointerEvent('pointerdown', { ...p, button: 2 })); el.dispatchEvent(new MouseEvent('contextmenu', { ...p, button: 2, cancelable: true })); },
  hover(el, on = true) {
    const ev = on ? 'pointerover' : 'pointerout';
    el.dispatchEvent(new PointerEvent(ev, { ...T.point(el), relatedTarget: on ? document.body : document.body }));
  },
  type(el, text) {
    el.focus();
    el.value = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  },
  key(key, opts = {}, el = null) {
    const code = opts.code || (key.length === 1 ? (/[a-z]/i.test(key) ? 'Key' + key.toUpperCase() : /\d/.test(key) ? 'Digit' + key : '') : key);
    (el || document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', { key, code, bubbles: true, cancelable: true, composed: true, ...opts }));
  },
  // Do something, then time how long until `watch` changes (a round trip through Python), in ms; -1 if it never does.
  watch(watch, action, ms = 3000) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      const mo = new MutationObserver(() => { mo.disconnect(); clearTimeout(timer); resolve(performance.now() - t0); });
      const timer = setTimeout(() => { mo.disconnect(); resolve(-1); }, ms);
      mo.observe(watch, { childList: true, characterData: true, subtree: true, attributes: true });
      action();
    });
  },
  spread(xs) {
    const s = xs.filter((x) => x >= 0).sort((a, b) => a - b);
    const at = (q) => s.length ? +s[Math.min(s.length - 1, Math.floor(s.length * q))].toFixed(2) : null;
    return { n: s.length, median: at(0.5), p95: at(0.95), max: s.length ? +s[s.length - 1].toFixed(2) : null };
  },
  shot(name) { return new Promise((r) => { T._ack = r; tv.emit('test-shot', { name }); }); },
  log(...a) { tv.emit('test-log', { text: a.map(String).join(' ') }); },
  done(result) { tv.emit('test-done', { result }); },
};
"""

WRAP = r"""
(async () => {
  await T.until(() => window.__at && document.querySelector('.at-app'), 20000);
  await T.frame();
  tv.emit('test-painted', { t: Date.now() });
  try {
%s
  } catch (err) {
    T.done({ error: String(err && err.stack || err) });
  }
})();
"""


class Tee(io.TextIOBase):
    def __init__(self, real):
        self.real = real
        self.buf = io.StringIO()

    def write(self, s):
        self.buf.write(s)
        try:
            self.real.write(s)
            self.real.flush()
        except Exception:
            pass
        return len(s)

    def flush(self):
        try:
            self.real.flush()
        except Exception:
            pass


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def screenshot(view, path):
    """A PNG of the page as WebView2 draws it (DevTools Page.captureScreenshot)."""
    from System import Func, Object  # pythonnet, loaded by pywebview
    form = view._win.native
    web = form.browser.webview
    box = {}

    def start():
        box["task"] = web.CoreWebView2.CallDevToolsProtocolMethodAsync("Page.captureScreenshot", '{"format":"png"}')
        return None
    form.Invoke(Func[Object](start))
    task = box["task"]
    if not task.Wait(15000):
        raise RuntimeError("the screenshot didn't come back")
    data = json.loads(str(task.Result))["data"]
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
    return path


def main():
    program = os.path.abspath(sys.argv[1])
    driver_path = arg("--driver")
    out = arg("--out")
    shots_dir = arg("--shots") or os.path.join(HERE, "out", "shots")
    timeout = float(arg("--timeout", "40"))
    driver = open(driver_path, encoding="utf-8").read() if driver_path else None
    state = {"result": None, "shots": [], "logs": [], "opening_s": None, "ready_s": None, "painted_s": None, "page": None}
    real_view = tuff_view.View

    class DrivenView(real_view):
        def __init__(self, *a, **k):
            state["opening_s"] = time.time() - STARTED  # the program's top level has run; the window opens now
            super().__init__(*a, **k)
            state["ready_s"] = time.time() - STARTED
            state["view"] = self
            self.on("test-painted", lambda e: state.update(painted_s=e["t"] / 1000 - STARTED, painted_at=e["t"] / 1000))
            self.on("test-log", lambda e: (state["logs"].append(e.get("text")),
                                           print("  [page] " + str(e.get("text")), file=sys.__stdout__, flush=True)))
            self.on("test-shot", self.take)
            self.on("test-done", self.finish)
            if driver is not None:
                self.js(HELPERS + WRAP % driver)
            else:
                self.js(HELPERS + WRAP % "")

        def take(self, e):
            os.makedirs(shots_dir, exist_ok=True)
            path = os.path.join(shots_dir, str(e.get("name")) + ".png")
            try:
                screenshot(self, path)
                state["shots"].append(path)
            except Exception as exc:
                state["logs"].append(f"screenshot failed: {exc}")
            self.js("window.__T._ack && window.__T._ack()")

        def finish(self, e):
            state["result"] = e.get("result")
            try:
                state["page"] = self.page_stats()
            except Exception:
                pass
            self.close()

    tuff_view.View = DrivenView

    def watchdog():
        print(f"FAIL: {os.path.basename(program)} still running after {timeout} s", flush=True)
        write(out, {"code": None, "timeout": True, "stdout": out_tee.buf.getvalue(), "stderr": err_tee.buf.getvalue(),
                    "result": state["result"], "logs": state["logs"]})
        os._exit(3)

    timer = threading.Timer(timeout, watchdog)
    timer.daemon = True
    timer.start()
    out_tee, err_tee = Tee(sys.stdout), Tee(sys.stderr)
    sys.stdout, sys.stderr = out_tee, err_tee
    t0 = time.perf_counter()
    code = tuff.run_program(program)
    seconds = time.perf_counter() - t0
    sys.stdout, sys.stderr = out_tee.real, err_tee.real
    view = state.pop("view", None)
    result = {"program": os.path.basename(program), "code": code, "stdout": out_tee.buf.getvalue(),
              "stderr": err_tee.buf.getvalue(), "result": state["result"], "seconds": round(seconds, 3),
              "started_at": STARTED, "opening_s": state["opening_s"], "ready_s": state["ready_s"],
              "painted_s": state["painted_s"], "painted_at": state.get("painted_at"), "shots": state["shots"],
              "logs": state["logs"], "page": state["page"], "python": view.stats if view is not None else None}
    write(out, result)
    return 0


def write(out, result):
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)


if __name__ == "__main__":
    sys.exit(main())
