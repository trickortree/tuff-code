"""(d) Latency: one event from the page to Python and back.

The page sends a "ping" event every 20-30 ms; Python answers each one by changing an element's text, and
the page times each round trip, from sending the ping to seeing the new text in the DOM. Measured three
ways:
  - ask(): Python to the page and back, timed from Python (what a pick or a measurement costs);
  - pygame style (frame() at 60 fps): handled at the next frame, so up to one frame (16.7 ms) more;
  - callback style (loop(), what atgui uses): handled as soon as it arrives.

    py -3 tuffcode/test/view/view_latency.py [--pings 200] [--out result.json]
"""
import sys
import time

from harness import Checks, arg, finish, spread, tuff_view, watchdog

DRIVER = """
const label = tv.node(%d).el;
const sent = new Map();
const times = [];
new MutationObserver(() => {
  const n = +label.textContent;
  if (sent.has(n)) { times.push(performance.now() - sent.get(n)); sent.delete(n); }
}).observe(label, { childList: true, characterData: true, subtree: true });
let n = 0;
// 20-30 ms apart at random, so pings land at every point of Python's 60 fps frame, not a few fixed ones.
(function next() {
  if (n === %d) {
    setTimeout(() => tv.emit('pings-done', { times, lost: sent.size }), 300);
    return;
  }
  n++;
  sent.set(n, performance.now());
  tv.emit('ping', { n });
  setTimeout(next, 20 + Math.random() * 10);
})();
"""


def main():
    checks = Checks("latency")
    pings = int(arg("--pings", 200))
    view = tuff_view.View("Tuff view: latency", 640, 360, on_top=True)
    label = view.el("div", text="0", style={"font": "48px Segoe UI, sans-serif", "padding": "40px", "color": "#eef1f7"})
    results = {}

    # ask(): a cheap method call there and back, timed from Python.
    ask_ms = []
    view.ask(label, "getAttribute", "class")
    for _ in range(pings):
        a = time.perf_counter()
        view.ask(label, "getAttribute", "class")
        ask_ms.append((time.perf_counter() - a) * 1000)

    # Pygame style: the program reads view.events() after each frame().
    view.js(DRIVER % (label, pings))
    while "pygame" not in results:
        view.frame()
        for e in view.events():
            if e["type"] == "ping":
                label.set(text=str(e["n"]))
            elif e["type"] == "pings-done":
                results["pygame"] = e

    # Callback style: handlers, then loop() until the last answer closes the window.
    def done(e):
        results["callback"] = e
        view.close()

    view.on("ping", lambda e: label.set(text=str(e["n"])))
    view.on("pings-done", done)
    view.js(DRIVER % (label, pings))
    view.loop()

    cb, pg = results["callback"], results["pygame"]
    numbers = {"pings": pings, "ask_ms": spread(ask_ms), "pygame_60fps_ms": spread(pg["times"]), "callback_ms": spread(cb["times"])}
    checks.check(len(cb["times"]) == pings and cb["lost"] == 0, f"callback style answered every ping ({len(cb['times'])}/{pings})")
    checks.check(len(pg["times"]) == pings and pg["lost"] == 0, f"pygame style answered every ping ({len(pg['times'])}/{pings})")
    checks.check(numbers["callback_ms"]["median"] < 5, f"callback round trip median under 5 ms ({numbers['callback_ms']['median']} ms)")
    checks.check(numbers["pygame_60fps_ms"]["p95"] < 16.7 + 8, f"pygame round trip within a frame plus a bit (p95 {numbers['pygame_60fps_ms']['p95']} ms)")
    checks.check(numbers["ask_ms"]["median"] < 5, f"ask() round trip median under 5 ms ({numbers['ask_ms']['median']} ms)")
    for k in ("ask_ms", "pygame_60fps_ms", "callback_ms"):
        print(f"  {k}: {numbers[k]}", flush=True)
    return finish(checks, numbers)


if __name__ == "__main__":
    watchdog(90, "latency")
    sys.exit(tuff_view.run(main))
