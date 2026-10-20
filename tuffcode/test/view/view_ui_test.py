"""(a) UI: 50 DOM widgets, events round trip.

Callback style (what atgui will use): handlers registered with on(), then loop(). A script in the page
clicks, types into and ticks every widget; each Python handler changes the page, and the page times
each round trip, from its click to seeing Python's change in the DOM. Also checks bubbling to a parent's
handler, held keys, input values, and that a failing handler or every-frame function is reported once.

    py -3 tuffcode/test/view/view_ui_test.py [--out result.json]
"""
import json
import sys
import time

from harness import Checks, finish, spread, tuff_view, watchdog

CSS = """
body { background: #0b0e14; }
.grid { position: absolute; inset: 0; padding: 16px; display: grid; gap: 8px;
        grid-template-columns: repeat(5, 1fr); align-content: start; overflow: auto; }
.w { background: #141924; border: 1px solid #2c3546; border-radius: 8px; padding: 8px 10px; color: #eef1f7;
     font: 13px 'Segoe UI', system-ui, sans-serif; min-height: 20px; }
button.w { cursor: pointer; text-align: left; }
button.w:hover { background: #222a38; }
input.w { outline: none; }
input.w:focus { border-color: #3b82f6; }
.mirror { color: #8b93a7; font-size: 12px; }
#status { grid-column: 1 / -1; color: #22c55e; }
"""

DRIVER = """
const W = %s;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
// Do something to the page, then time how long until Python's answer shows up in `watch`.
function roundTrip(watch, action) {
  return new Promise((resolve) => {
    const t0 = performance.now();
    const mo = new MutationObserver(() => { mo.disconnect(); clearTimeout(timer); resolve(performance.now() - t0); });
    const timer = setTimeout(() => { mo.disconnect(); resolve(-1); }, 2000);
    mo.observe(watch, { childList: true, characterData: true, subtree: true });
    action();
  });
}
async function go() {
  const lat = [];
  for (const id of W.buttons) { const el = tv.node(id).el; lat.push(await roundTrip(el, () => el.click())); await wait(5); }
  for (const id of W.cards) { const inner = tv.node(id).el.firstChild; lat.push(await roundTrip(tv.node(id).el, () => inner.click())); await wait(5); }
  for (let i = 0; i < W.inputs.length; i++) {
    const el = tv.node(W.inputs[i]).el;
    lat.push(await roundTrip(tv.node(W.mirrors[i]).el, () => { el.value = 'hello ' + i; el.dispatchEvent(new Event('input', { bubbles: true })); }));
    await wait(5);
  }
  for (let i = 0; i < W.checks.length; i++) {
    const el = tv.node(W.checks[i]).el;
    lat.push(await roundTrip(tv.node(W.checkMirrors[i]).el, () => el.click()));
    await wait(5);
  }
  const status = tv.node(W.status).el;
  lat.push(await roundTrip(status, () => dispatchEvent(new KeyboardEvent('keydown', { key: 'k', code: 'KeyK', bubbles: true }))));
  await wait(50);
  tv.emit('held', {});
  await wait(50);
  dispatchEvent(new KeyboardEvent('keyup', { key: 'k', code: 'KeyK', bubbles: true }));
  await wait(50);
  for (let i = 0; i < 3; i++) { tv.node(W.broken).el.click(); await wait(20); }
  await wait(100);
  const texts = W.buttons.map((id) => tv.node(id).el.textContent);
  tv.emit('driver', { lat, texts });
}
go();
"""


def main():
    checks = Checks("ui")
    errors = []
    t0 = time.perf_counter()
    view = tuff_view.View("Tuff view: UI test", 1100, 760, on_error=lambda exc, where: errors.append((where, str(exc))))
    open_s = time.perf_counter() - t0
    view.call(0, "css", CSS)
    grid = view.el("div", cls="grid")
    status = view.el("div", grid, id="status", text="Waiting for the driver…")
    counts = {}
    buttons, cards, inputs, mirrors, checks_, check_mirrors = [], [], [], [], [], []

    def count(e):
        counts[e["id"]] = counts.get(e["id"], 0) + 1

    for i in range(20):
        b = view.el("button", grid, cls="w", text=f"Button {i}")
        b.on("click", lambda e, b=b, i=i: (count(e), b.set(text=f"Button {i}: clicked")))
        buttons.append(b)
    for i in range(10):
        c = view.el("div", grid, cls="w")
        view.el("span", c, text=f"Card {i} (click the text)")
        c.on("click", lambda e, c=c, i=i: (counts.__setitem__(int(c), counts.get(int(c), 0) + 1), c.set(text=f"Card {i}: clicked via bubbling")))
        cards.append(c)
    for i in range(10):
        inp = view.el("input", grid, cls="w", placeholder=f"Field {i}")
        m = view.el("div", grid, cls="w mirror", text="…")
        inp.on("input", lambda e, m=m: (count(e), m.set(text="typed: " + e["value"])))
        inputs.append(inp)
        mirrors.append(m)
    for i in range(10):
        box = view.el("input", grid, cls="w", type="checkbox")
        m = view.el("div", grid, cls="w mirror", text="unticked")
        box.on("change", lambda e, m=m: (count(e), m.set(text="ticked" if e["value"] else "unticked")))
        checks_.append(box)
        check_mirrors.append(m)
    widgets = len(buttons) + len(cards) + len(inputs) + len(checks_)

    broken = view.el("button", grid, cls="w", text="Broken handler")
    broken.on("click", lambda e: 1 / 0)
    ticks = {"n": 0}

    def bad_tick(dt):
        ticks["n"] += 1
        raise RuntimeError("every-frame function that always fails")

    view.every_frame(bad_tick)
    keys_seen = []
    held = {}
    view.on("keydown", lambda e: (keys_seen.append(e["key"]), status.set(text=f"Key down: {e['key']}")))
    view.on("held", lambda e: held.setdefault("during", view.key_down("k")))
    result = {}

    def driver_done(e):
        result.update(e)
        held["after"] = view.key_down("k")
        view.close()

    view.on("driver", driver_done)
    view.js(DRIVER % json.dumps({"buttons": buttons, "cards": cards, "inputs": inputs, "mirrors": mirrors,
                                  "checks": checks_, "checkMirrors": check_mirrors, "status": status, "broken": broken}))
    t1 = time.perf_counter()
    view.loop()
    run_s = time.perf_counter() - t1

    lat = result.get("lat", [])
    checks.check(widgets == 50, f"made 50 widgets ({widgets})")
    checks.check(bool(result), "the page's driver finished")
    checks.check(len(lat) == 51 and all(x >= 0 for x in lat), f"all 51 round trips came back ({sum(x >= 0 for x in lat)}/{len(lat)})")
    ids = buttons + cards + inputs + checks_
    checks.check(all(counts.get(int(i)) == 1 for i in ids), f"each widget's handler ran exactly once ({sum(counts.get(int(i)) == 1 for i in ids)}/50)")
    checks.check(result.get("texts") == [f"Button {i}: clicked" for i in range(20)], "every button shows Python's new text")
    checks.check(all(view.values.get(int(inputs[i])) == f"hello {i}" for i in range(10)), "view.values has what was typed in each field")
    checks.check(all(view.values.get(int(c)) is True for c in checks_), "view.values has every checkbox ticked")
    checks.check(keys_seen == ["k"], f"one keydown reached Python ({keys_seen})")
    checks.check(held.get("during") is True and held.get("after") is False, f"key_down('k') while held, not after keyup ({held})")
    broken_reports = [w for w, m in errors if "click handler" in w]
    tick_reports = [w for w, m in errors if "every-frame" in w]
    checks.check(len(broken_reports) == 1, f"a handler failing 3 times is reported once ({len(broken_reports)})")
    checks.check(len(tick_reports) == 1 and ticks["n"] == 1, f"a failing every-frame function is reported once and switched off (ran {ticks['n']}x)")
    checks.check(not view.is_open, "closing the window ended loop()")
    numbers = {"open_seconds": round(open_s, 3), "driver_seconds": round(run_s, 3),
               "round_trip_ms": spread([x for x in lat if x >= 0]), "python": view.stats}
    print(f"  window open in {open_s:.2f} s; click -> Python -> DOM round trip {numbers['round_trip_ms']}", flush=True)
    return finish(checks, numbers)


if __name__ == "__main__":
    watchdog(60, "ui")
    sys.exit(tuff_view.run(main))
