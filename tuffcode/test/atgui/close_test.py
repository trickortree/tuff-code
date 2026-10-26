"""app:closed when the window closes, at every moment it can, with the window's close simulated: no window opens.

    py -3 tuffcode/test/atgui/close_test.py [--out result.json]

Each case runs a real .tuf program through tuff.py, in a child process with no console window. In the child,
tuff_view.View._open (the real window) is replaced by a stand-in that does what pywebview does when the window's X
is clicked: its closing event on the window's own thread (View._on_closing, which waits for the close handlers),
then the window is gone, then its closed event. pywebview can't even load there (sys.modules["webview"] is None),
so nothing can open a window: this runs while someone uses the computer. run_all.py's osclose does the same with
real windows. CLOSE_LIMIT and CLOSE_GRACE are shortened here (LIMIT and GRACE, below).

  appears     closed the instant the window appears (its page not ready): app:closed ran once, before it went
  ready       closed as its page got ready, before the first frame: the same
  runs        closed while its timer runs: the same
  gone        the process ended the moment the window went (Cmd+Q on a Mac, logging off Windows): app:closed was done
  gone_early  the same, closed the instant the window appeared
  self        the program closes its own window (app:close): app:closed ran once
  top         the same from the top-level code, after a popup (answered here) opened the window
  asking      closed while a popup in the top-level code waits for its answer: app:closed ran once, the rest didn't
  popup       app:closed asks first (app:confirm, app:ask, app:alert): nobody can answer, so they're dismissed at
              once, and the file it saves after them is saved
  stuck       app:closed loops forever: stopped LIMIT s in, with a Tuff error on the loop's line; the program ends
  asleep      app:closed waits (wait(60)), which nothing can stop: the program is ended LIMIT + GRACE s in (exit 1)
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OSCLOSE = os.path.join(HERE, "programs", "osclose.tuf")
LIMIT, GRACE = 1.5, 1.0

HEAD = """mention atgui

app = atgui.window("atgui close test", 420, 300)
ticks = 0
app:heading "Close me"
app:every(0.05, tick)
app:closed bye

func tick():
    ticks += 1
    if ticks == 1:
        say "running"
"""
PROGRAMS = {
    "self": HEAD + """app:after(0.3, done)

func done():
    app:close

func bye():
    say "closed"
""",
    "top": """mention atgui

app = atgui.window("atgui close test", 420, 300)
app:closed bye
app:alert "Hello"
say "answered"
app:close

func bye():
    say "closed"
""",
    "asking": """mention atgui

app = atgui.window("atgui close test", 420, 300)
app:closed bye
say "asking"
sure = app:confirm("Ready?")
say "answered"

func bye():
    say "closed by the system"
""",
    "popup": HEAD + """
func bye():
    ok = app:confirm("Save your changes?")
    name = app:ask("Your name?")
    app:alert "Bye!"
    file.write("closed.txt", "confirm " + ok + ", ask [" + name + "]")
    say "saved"
""",
    "stuck": HEAD + """
func bye():
    say "saving"
    n = 0
    while true:
        n += 1
""",
    "asleep": HEAD + """
func bye():
    say "saving"
    wait(60)
    say "woke up"
""",
}
STUCK_LINE = PROGRAMS["stuck"].splitlines().index("        n += 1") + 1


class FakeWindow:
    """pywebview's window, as far as View uses it: the page's changes go nowhere, except that a popup's OK button is
    clicked as soon as it's made, and destroy() closes it the way the real one does on Windows (the window's thread
    runs the closing event while the caller waits for it)."""

    def __init__(self, view):
        self.view = view
        self.seq = 0  # the page's calls are numbered, from 1

    def run_js(self, code):
        batches = json.loads(code[len("__tv.apply("):-1])
        for _seq, cmds in batches:
            for cmd in cmds:
                if cmd[0] == "s" and "<span>OK</span>" in str(cmd[2].get("html", "")):
                    self.seq += 1
                    self.view._on_events(self.seq, [{"type": "click", "path": [cmd[1]]}])
        return None

    def destroy(self):
        self.view._on_closing()

    def __getattr__(self, name):  # set_title, resize, move, minimize...
        return lambda *args: None


def child(case, program):
    sys.modules["webview"] = None  # pywebview can't load: no window can open, whatever happens below
    sys.path.insert(0, REPO)
    import tuff
    import tuff_view
    tuff_view.CLOSE_LIMIT, tuff_view.CLOSE_GRACE = LIMIT, GRACE

    def mark(what):
        print(f"[window] {what} {time.perf_counter():.3f}", flush=True)

    real_exit = os._exit

    def exit_now(code):  # how tuff_view ends a program stuck in its close handler: note when
        mark("ended")
        real_exit(code)
    os._exit = exit_now

    def stand_in(view):
        """Main thread, in place of View._open: the window opens, and is closed as its X closes it."""
        view._win = FakeWindow(view)
        if case not in ("appears", "gone_early"):
            view._on_ready({"w": 420, "h": 300})
        if case in ("self", "top"):
            deadline = time.monotonic() + 10
            while not view._closed and time.monotonic() < deadline:
                time.sleep(0.01)
        else:
            if case not in ("appears", "gone_early", "ready"):
                deadline = time.monotonic() + 10
                while view.stats["frames"] < 5 and time.monotonic() < deadline:
                    time.sleep(0.01)
            mark("WM_CLOSE")
            view._on_closing()  # pywebview's closing event: the window waits here for the close handlers
            mark("gone")
            if case in ("gone", "gone_early"):
                os._exit(7)  # what Cmd+Q or logging off does once the window has gone
        view._on_closed()  # pywebview's closed event, and the end of View._open

    tuff_view.View._open = stand_in
    sys.argv = [os.path.join(REPO, "tuff.py"), program]
    code = tuff.main()
    mark("ended")
    return code


class Results:
    def __init__(self):
        self.passed = self.failed = 0
        self.failures = []

    def check(self, ok, what, got=None):
        ok = bool(ok)
        self.passed += ok
        self.failed += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {what}" + ("" if ok or got is None else f"\n        got: {str(got)[:900]}"), flush=True)
        if not ok:
            self.failures.append(what)
        return ok


def run_case(case, program, folder):
    env = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_NO_WRITES", "TUFF_BASE_DIR")}
    env["PYTHONIOENCODING"] = "utf-8"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window, even when started from a program without one
    start = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", case, program], cwd=folder, env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=30, creationflags=flags)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        code, out, err = "timeout", exc.stdout or "", exc.stderr or ""
        out, err = (x.decode("utf-8", "replace") if isinstance(x, bytes) else x for x in (out, err))
    took = time.perf_counter() - start
    lines = [x for x in out.replace("\r\n", "\n").split("\n") if x.strip()]
    marks = {x.split()[1]: float(x.split()[2]) for x in lines if x.startswith("[window] ")}
    said = [x for x in lines if not x.startswith("[window] ")]
    return {"code": code, "lines": lines, "said": said, "marks": marks, "err": err, "took": took}


def main():
    R = Results()
    numbers = {}
    folder = tempfile.mkdtemp(prefix="tuff-atgui-close-")
    paths = {}
    for name, src in PROGRAMS.items():
        paths[name] = os.path.join(folder, f"closed_{name}.tuf")
        with open(paths[name], "w", encoding="utf-8") as f:
            f.write(src)
    print("== close_test.py: app:closed, with the window's close simulated (no window opens)", flush=True)

    def before_gone(r, said="closed by the system"):
        """The program said `said` before the window went (the stand-in's "gone" line)."""
        lines = r["lines"]
        gone = next((i for i, x in enumerate(lines) if x.startswith("[window] gone")), None)
        return said in lines and gone is not None and lines.index(said) < gone

    for case in ("appears", "ready", "runs"):
        r = run_case(case, OSCLOSE, folder)
        ok = (r["code"] == 0 and r["said"] and r["said"][-1] == "closed by the system" and r["said"].count("closed by the system") == 1
              and set(r["said"]) <= {"running", "closed by the system"} and r["err"] == "")
        R.check(ok, f"{case}: app:closed ran once and the program ended cleanly (exit {r['code']})", r)
        R.check(before_gone(r), f"{case}: app:closed had finished before the window went", r["lines"])
        if "ended" in r["marks"] and "WM_CLOSE" in r["marks"]:
            numbers[f"{case}_close_to_end_s"] = round(r["marks"]["ended"] - r["marks"]["WM_CLOSE"], 3)

    for case in ("gone", "gone_early"):
        r = run_case(case, OSCLOSE, folder)
        R.check(r["code"] == 7 and before_gone(r), f"{case}: the process ended the moment the window went, and app:closed "
                f"had already run ({'the instant it appeared' if case == 'gone_early' else 'while its timer ran'})", r)

    r = run_case("self", paths["self"], folder)
    R.check(r["code"] == 0 and r["said"].count("closed") == 1 and r["err"] == "",
            f"self: app:close closed it, and app:closed ran once (exit {r['code']})", r)

    r = run_case("top", paths["top"], folder)
    R.check(r["code"] == 0 and r["said"] == ["answered", "closed"] and r["err"] == "",
            f"top: app:alert opened the window, app:close in the top-level code closed it, and app:closed ran once "
            f"(exit {r['code']})", r)

    r = run_case("asking", paths["asking"], folder)
    R.check(r["code"] == 0 and r["said"] == ["asking", "closed by the system"] and r["err"] == "" and before_gone(r),
            f"asking: closed while app:confirm waited in the top-level code, app:closed ran once, before the window went, "
            f"and the code after the popup didn't run (exit {r['code']})", r)

    saved = os.path.join(folder, "closed.txt")
    r = run_case("popup", paths["popup"], folder)
    text = None
    if os.path.isfile(saved):
        with open(saved, encoding="utf-8") as f:
            text = f.read()
    R.check(r["code"] == 0 and "saved" in r["said"] and r["err"] == "" and before_gone(r, "saved"),
            f"popup: app:confirm, app:ask and app:alert in app:closed didn't wait for an answer (exit {r['code']})", r)
    R.check(text == "confirm false, ask []", "popup: ...they gave a dismissed popup's answers, and the file after them was saved", text)

    r = run_case("stuck", paths["stuck"], folder)
    want = (f"Tuff error on line {STUCK_LINE}: bye(), your app:closed function, was still running {LIMIT:g} seconds after the "
            "window closed, so it was stopped. Look for a loop that never ends.")
    m = r["marks"]
    stopped = round(m["ended"] - m["WM_CLOSE"], 3) if "ended" in m and "WM_CLOSE" in m else None
    R.check(r["code"] == 0 and r["err"].count("Tuff error") == 1 and want in r["err"] and "saving" in r["said"],
            f"stuck: an endless loop in app:closed was stopped, with an error on its line ({STUCK_LINE}), and the program ended", r)
    R.check(stopped is not None and LIMIT <= stopped < LIMIT + 1.0 and m.get("gone", 99) - m.get("WM_CLOSE", 0) < GRACE + 0.3,
            f"stuck: the window went after {GRACE:g} s, and the program ended {stopped} s after the close (limit {LIMIT:g} s)", m)
    numbers["stuck_s"] = stopped

    r = run_case("asleep", paths["asleep"], folder)
    want = (f"Tuff error: the window closed, but your app:closed function was still running {LIMIT + GRACE:g} "
            "seconds later, so the program was stopped.")
    m = r["marks"]
    stopped = round(m["ended"] - m["WM_CLOSE"], 3) if "ended" in m and "WM_CLOSE" in m else None
    R.check(r["code"] == 1 and want in r["err"] and "woke up" not in r["said"] and "saving" in r["said"],
            f"asleep: app:closed stuck in wait(60) can't be stopped, so the program was ended, and said why (exit {r['code']})", r)
    R.check(stopped is not None and LIMIT + GRACE <= stopped < LIMIT + GRACE + 1.0,
            f"asleep: ...{stopped} s after the close (the limit, {LIMIT:g} s, then {GRACE:g} s more)", m)
    numbers["asleep_s"] = stopped

    for path in list(paths.values()) + [saved]:
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        os.rmdir(folder)
    except OSError:
        pass
    print(f"\nclose: {R.passed} passed, {R.failed} failed", flush=True)
    print("NUMBERS " + json.dumps(numbers), flush=True)
    if "--out" in sys.argv:
        with open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8") as f:
            json.dump({"passed": R.passed, "failed": R.failed, "failures": R.failures, "numbers": numbers}, f, indent=2)
    return 0 if R.failed == 0 else 1


if __name__ == "__main__":
    if "--child" in sys.argv:
        i = sys.argv.index("--child")
        sys.exit(child(sys.argv[i + 1], sys.argv[i + 2]))
    sys.exit(main())
