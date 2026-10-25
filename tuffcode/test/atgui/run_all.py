"""Run every atgui test: the checker cases, then real .tuf programs in real windows, one at a time.

    py -3 tuffcode/test/atgui/run_all.py [--only name,name] [--out-dir folder]

Each program runs through drive.py, which runs it exactly as `tuff.py program.tuf` would and lets a driver
script (programs/*.js, examples/*.js) click, type and press keys in the page. Windows open for a few seconds
and close by themselves; don't cover them while they run (a covered page stops drawing). Results, numbers
and screenshots go to tuffcode/test/atgui/out/ (--out-dir to change it). Exits 1 if anything failed.
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# The windows open out of sight, never take the focus and make no sound (tuff_view's _quiet_window), so the
# tests can run while someone uses the computer. TUFF_TEST_QUIET=0 shows them.
os.environ.setdefault("TUFF_TEST_QUIET", "1")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TUFF = os.path.join(REPO, "tuff.py")
GUIDE = os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md")
OUT = os.path.abspath(sys.argv[sys.argv.index("--out-dir") + 1]) if "--out-dir" in sys.argv else os.path.join(HERE, "out")
SHOTS = os.path.join(OUT, "shots")
ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
ENV = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}  # time it as people run it
ENV["PYTHONIOENCODING"] = "utf-8"
CLOSE_AFTER_PAINT = "await T.wait(600);\nawait T.shot(SHOT);\nT.done({ ok: true });\n"


class Results:
    def __init__(self):
        self.rows = []
        self.passed = self.failed = 0
        self.numbers = {}

    def check(self, ok, what, got=None):
        ok = bool(ok)
        self.passed += ok
        self.failed += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {what}" + ("" if ok or got is None else f"\n        got: {str(got)[:600]}"), flush=True)
        return ok


def drive(name, program, driver=None, timeout=60):
    """Run one program in its window; returns drive.py's result, with spawn_to_paint_s added."""
    out = os.path.join(OUT, name + ".json")
    if os.path.exists(out):
        os.remove(out)
    args = [sys.executable, os.path.join(HERE, "drive.py"), program, "--out", out, "--shots", SHOTS, "--timeout", str(timeout)]
    if driver:
        args += ["--driver", driver]
    spawned = time.time()
    proc = subprocess.run(args, cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        with open(out, encoding="utf-8") as f:
            result = json.load(f)
    except (OSError, ValueError):
        result = {"code": None, "stdout": proc.stdout, "stderr": proc.stderr, "result": None, "logs": []}
    result["exit"] = proc.returncode
    if result.get("painted_at"):
        result["spawn_to_paint_s"] = round(result["painted_at"] - spawned, 3)
    return result


def window_of(pid, title):
    """The top-level window with this title that belongs to this process (Windows), or None."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value == title and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(each), 0)
    return found[0] if found else None


def os_close(when):
    """Run programs/osclose.tuf through plain tuff.py and send its window WM_CLOSE (what the X sends), `when`:
    "appears" (the instant it does), "loads" (0.15 s later), "runs" (once its timer said "running") or "gone"
    (like "runs", then the process is ended as soon as the window has gone)."""
    import ctypes
    import threading
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    proc = subprocess.Popen([sys.executable, TUFF, "tuffcode/test/atgui/programs/osclose.tuf"], cwd=REPO, env=ENV,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    out, err = [], []

    def read_out():
        for line in proc.stdout:
            out.append(line.rstrip("\r\n"))
    readers = [threading.Thread(target=read_out, daemon=True),
               threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True)]
    for t in readers:
        t.start()
    hwnd = None
    deadline = time.monotonic() + 20
    while hwnd is None and time.monotonic() < deadline and proc.poll() is None:
        hwnd = window_of(proc.pid, "atgui close test")
        if hwnd is None:
            time.sleep(0.005)
    if when == "loads":
        time.sleep(0.15)
    elif when in ("runs", "gone"):
        while "running" not in out and time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.01)
        time.sleep(0.2)
    result = {"hwnd": hwnd, "gone_ms": None}
    closed_at = time.perf_counter()
    if hwnd is not None:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        if when == "gone":
            while user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd) and time.perf_counter() - closed_at < 10:
                time.sleep(0.001)
            result["gone_ms"] = round((time.perf_counter() - closed_at) * 1000)
            proc.kill()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    result["took"] = time.perf_counter() - closed_at
    for t in readers:
        t.join(5)
    result.update(code=proc.returncode, lines=[x for x in out if x.strip()], err="".join(err))
    return result


def lines(text):
    return [x for x in text.replace("\r\n", "\n").split("\n") if x.strip()]


def wants(name):
    return ONLY is None or name in ONLY


def main():
    os.makedirs(SHOTS, exist_ok=True)
    R = Results()
    started = time.perf_counter()

    if wants("check"):
        print("== checker (check_test.py)", flush=True)
        if os.path.exists(os.path.join(OUT, "check.json")):
            os.remove(os.path.join(OUT, "check.json"))
        p = subprocess.run([sys.executable, os.path.join(HERE, "check_test.py"), "--out", os.path.join(OUT, "check.json")],
                           cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8")
        try:
            c = json.load(open(os.path.join(OUT, "check.json"), encoding="utf-8"))
        except (OSError, ValueError):
            c = {"passed": 0, "failed": 1, "failures": [p.stdout[-800:]]}
        R.check(c["failed"] == 0, f"--check: {c['passed']} cases right, {c['failed']} wrong", c.get("failures"))
        R.numbers["check_cases"] = c["passed"] + c["failed"]

    if wants("docs"):
        print("== the editor's tables (docs_test.mjs)", flush=True)
        try:
            p = subprocess.run(["node", os.path.join(HERE, "docs_test.mjs")], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8")
            m = re.search(r"docs: (\d+) passed, (\d+) failed", p.stdout)
            R.check(p.returncode == 0 and m, f"tuff-lang.js knows atgui ({m.group(1) if m else 0} checks)", p.stdout[-800:] + p.stderr[-400:])
        except OSError:
            print("  skip: node isn't installed", flush=True)

    if wants("widgets"):
        print("== programs/widgets.tuf: every widget, through real DOM events", flush=True)
        r = drive("widgets", "tuffcode/test/atgui/programs/widgets.tuf", "tuffcode/test/atgui/programs/widgets.js")
        R.check(r.get("code") == 0 and r.get("exit") == 0, "ran and closed (exit 0)", r.get("exit"))
        R.check(r.get("stderr", "x") == "", "no errors", r.get("stderr"))
        want = ["add_one 1", "add_one 2", "named Named", "typed hi", "entered hi", "sent hello", "ticked true",
                "switched false", "slid 7", "picked Blue", "chose Banana", "row Alan 41", "tab Two", "hover true",
                "hover false", "card clicked", "hover true", "hover false", "renamed Cherry", "focused true",
                "focused false", "shortcut", "modal closed", "values hi true false 7 Blue Banana Two",
                '["Banana", "Cherry", "Date"]', "76", "Blue", "switched false", "9"]
        R.check(lines(r.get("stdout", "")) == want, "every event function ran once, in order, with the right input",
                lines(r.get("stdout", "")))
        checks = ((r.get("result") or {}).get("checks")) or {}
        for k, v in checks.items():
            R.check(v, f"page: {k}")
        R.check(len(checks) >= 25, f"all page checks came back ({len(checks)})")

    if wants("selftest"):
        print("== programs/selftest.tuf: a program that drives itself (no page driver)", flush=True)
        r = drive("selftest", "tuffcode/test/atgui/programs/selftest.tuf")
        want = ["2", "Ada", "true", "C", '["B", "C"]', "[]", "Hello **there**", "more opened", "false", "true", "closed"]
        R.check(r.get("code") == 0 and r.get("stderr") == "", "ran, closed itself, no errors", (r.get("exit"), r.get("stderr")))
        R.check(lines(r.get("stdout", "")) == want, ":set, :value, :add, :remove, :clear, timers and app:closed", lines(r.get("stdout", "")))

    if wants("errors"):
        print("== programs/errors.tuf: mistakes in event functions", flush=True)
        r = drive("errors", "tuffcode/test/atgui/programs/errors.tuf", "tuffcode/test/atgui/programs/errors.js")
        err = r.get("stderr", "")
        R.check(r.get("code") == 0, "the app kept running and closed normally", r.get("exit"))
        R.check(lines(r.get("stdout", "")) == ["still working"] * 3, "a good button still works between the broken ones", r.get("stdout"))
        for line, what in ((13, "a click"), (19, "a keystroke"), (22, "a timer")):
            n = err.count(f"Tuff error on line {line}:")
            R.check(n == 1, f"{what}'s error is reported once (3+ times it happened), with its line ({line})", f"{n}x\n{err}")
        R.check(err.count("Tuff error") == 3, "nothing else was reported", err)

    if wants("popups"):
        print("== programs/popups.tuf: ask, confirm and alert in the top-level code", flush=True)
        r = drive("popups", "tuffcode/test/atgui/programs/popups.tuf", "tuffcode/test/atgui/programs/popups.js")
        R.check(r.get("code") == 0 and r.get("stderr") == "", "ran and closed itself, no errors", (r.get("exit"), r.get("stderr")))
        R.check(lines(r.get("stdout", "")) == ["Hi Ada", "true", "false", "after alert", "true"],
                "each popup gave its answer, and timers ran while they were open", lines(r.get("stdout", "")))

    if wants("frameless"):
        print("== programs/frameless.tuf: a window without a frame, with atgui's title bar", flush=True)
        r = drive("frameless", "tuffcode/test/atgui/programs/frameless.tuf", "tuffcode/test/atgui/programs/frameless.js")
        logged = next((x for x in r.get("logs", []) if x.startswith("checks ")), "checks {}")
        checks = json.loads(logged[7:])
        for k, v in checks.items():
            R.check(v, f"page: {k}")
        R.check(len(checks) == 10, "all frameless checks came back", checks)
        R.check(r.get("code") == 0 and lines(r.get("stdout", "")) == ["closed"], "the close button closed it and app:closed ran", (r.get("exit"), r.get("stdout")))

    if wants("osclose") and os.name == "nt":
        print("== programs/osclose.tuf: closed with WM_CLOSE (the window's X), through plain tuff.py", flush=True)
        # At every moment the window can be closed: the instant it appears (its page isn't ready yet, which once
        # made app:closed never run), while its page loads, and while its timer runs. Then once more, ending the
        # process the moment its window has gone, as Cmd+Q on a Mac or logging off Windows does.
        for when, what in (("appears", "the instant its window appears"), ("loads", "0.15 s later, while its page loads"),
                           ("runs", "while its timer runs"), ("gone", "and the process ended the moment its window was gone")):
            r = os_close(when)
            R.check(r["hwnd"] is not None, f"{when}: its window opened")
            if when == "gone":
                R.check("closed by the system" in r["lines"],
                        f"gone: app:closed had run when the window went, {r['gone_ms']} ms after WM_CLOSE", r["lines"])
                R.numbers["close_window_gone_ms"] = r["gone_ms"]
                continue
            R.check(r["code"] == 0 and r["lines"] and r["lines"][-1] == "closed by the system"
                    and r["lines"].count("closed by the system") == 1 and set(r["lines"]) <= {"running", "closed by the system"}
                    and r["err"] == "", f"{when}: closed {what}: app:closed ran once and the program ended cleanly "
                    f"{r['took']:.2f} s after WM_CLOSE", (r["code"], r["lines"], r["err"]))
            if when == "runs":
                R.numbers["close_after_wm_close_s"] = round(r["took"], 2)

    if wants("latency"):
        print("== programs/latency.tuf: round trips", flush=True)
        r = drive("latency", "tuffcode/test/atgui/programs/latency.tuf", "tuffcode/test/atgui/programs/latency.js")
        res = r.get("result") or {}
        R.check(res.get("count") == "100" and res.get("mirror_ok"), "100 clicks counted, 100 keystrokes mirrored", res)
        R.check((res.get("click_ms") or {}).get("median", 99) < 10, f"click -> Tuff -> page {res.get('click_ms')} ms")
        R.check((res.get("key_ms") or {}).get("median", 99) < 10, f"keystroke -> Tuff -> page {res.get('key_ms')} ms")
        R.numbers["latency"] = {"click_ms": res.get("click_ms"), "key_ms": res.get("key_ms")}
        R.numbers["open_small"] = {k: r.get(k) for k in ("spawn_to_paint_s", "opening_s", "ready_s", "painted_s")}
        R.check((r.get("spawn_to_paint_s") or 99) < 2.5, f"a small app is on screen {r.get('spawn_to_paint_s')} s after starting Python")

    if wants("biglist"):
        print("== programs/biglist.tuf: 1,000 items", flush=True)
        r = drive("biglist", "tuffcode/test/atgui/programs/biglist.tuf", "tuffcode/test/atgui/programs/biglist.js")
        res = r.get("result") or {}
        R.check(res.get("items") == 1000 and res.get("second_lines") == 100, "1,000 items, 100 with a second line", res)
        disp = (res.get("display_gap_ms") or {}).get("median") or 16.7
        gaps = res.get("gap_ms") or {}
        # Out of sight (TUFF_TEST_QUIET), the window is on no screen, so its frames aren't timed to one: now and then
        # one comes a display frame late. On a screen, nearly all come at the display's rate.
        late = 2.0 if os.environ.get("TUFF_TEST_QUIET") == "1" else 1.5
        R.check((gaps.get("p95") or 99) <= disp * late + 2 and res.get("long_frames", 99) <= 3,
                f"scrolling keeps the display's rate: {res.get('scroll_fps')} fps, frame gaps {gaps} ms "
                f"(display {disp} ms), {res.get('long_frames')} long frames")
        R.check(res.get("picked") == "Picked Item 900" and res.get("selected"), f"picking item 900 works ({res.get('pick_ms')} ms)", res)
        page = r.get("page") or {}
        R.numbers["biglist"] = {**{k: res.get(k) for k in ("scroll_fps", "gap_ms", "display_gap_ms", "long_frames", "pick_ms")},
                                "open": {k: r.get(k) for k in ("spawn_to_paint_s", "opening_s", "ready_s", "painted_s")},
                                "first_batch_kb": round(((r.get("python") or {}).get("bytes") or 0) / 1024, 1),
                                "python_flush_ms": round((r.get("python") or {}).get("flush_ms") or 0, 2),
                                "page_apply_ms_per_batch": page.get("apply_ms_per_batch"), "page_objects": page.get("objects")}
        R.check((r.get("spawn_to_paint_s") or 99) < 3.5, f"the 1,000-item app is on screen {r.get('spawn_to_paint_s')} s after starting Python")

    for name, needs in (("chat", ("sent", "typingShown", "replied", "cleared")),
                        ("settings", ("isLight", "purple", "flipped", "toast", "popup", "deleted")),
                        ("dashboard", ("changed", "toast", "selected"))):
        if not wants(name):
            continue
        print(f"== examples/{name}.tuf", flush=True)
        prog = f"tuffcode/test/atgui/examples/{name}.tuf"
        chk = subprocess.run([sys.executable, TUFF, "--check", prog], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8")
        R.check(chk.returncode == 0 and chk.stdout.strip() == "OK", "--check says OK", chk.stdout + chk.stderr)
        with open(os.path.join(REPO, prog), encoding="utf-8") as f:
            n_lines = len(f.read().splitlines())
        R.check(30 <= n_lines <= 60, f"{n_lines} lines long")
        r = drive(name, prog, f"tuffcode/test/atgui/examples/{name}.js")
        res = r.get("result") or {}
        R.check(r.get("code") == 0 and r.get("stderr") == "", "ran and closed, no errors", (r.get("exit"), r.get("stderr")))
        for k in needs:
            R.check(res.get(k), f"page: {k}", res)
        R.check(os.path.isfile(os.path.join(SHOTS, name + ".png")), f"screenshot out/shots/{name}.png")
        R.numbers.setdefault("open_examples", {})[name] = r.get("spawn_to_paint_s")

    if wants("guide"):
        print("== the guide's atgui examples", flush=True)
        with open(GUIDE, encoding="utf-8") as f:
            guide = f.read().replace("\r\n", "\n")
        m = re.search(r"\n### atgui\n(.*?)(?=\n## |\n### (?!atgui))", guide, re.S)
        blocks = re.findall(r"```tuff\n(.*?)```", m.group(1), re.S) if m else []
        R.check(len(blocks) >= 2, f"the guide's atgui section has {len(blocks)} examples")
        gdir = os.path.join(OUT, "guide")
        os.makedirs(gdir, exist_ok=True)
        for i, code in enumerate(blocks, 1):
            prog = os.path.join(gdir, f"example{i}.tuf")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(code)
            chk = subprocess.run([sys.executable, TUFF, "--check", prog], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8")
            R.check(chk.returncode == 0 and chk.stdout.strip() == "OK", f"example {i}: --check says OK", chk.stdout + chk.stderr)
            driver = os.path.join(gdir, f"example{i}.js")
            with open(driver, "w", encoding="utf-8") as f:
                f.write(CLOSE_AFTER_PAINT.replace("SHOT", json.dumps(f"guide-example{i}")))
            r = drive(f"guide{i}", prog, driver)
            R.check(r.get("code") == 0 and r.get("stderr") == "" and (r.get("result") or {}).get("ok"),
                    f"example {i}: runs in a real window, no errors", (r.get("exit"), r.get("stderr"), r.get("result")))

    if wants("compat"):
        print("== the guide's mtgui examples, with mention atgui", flush=True)
        with open(GUIDE, encoding="utf-8") as f:
            guide = f.read().replace("\r\n", "\n")
        blocks = [b for b in re.findall(r"```tuff\n(.*?)```", guide, re.S) if "mention mtgui" in b]
        R.check(len(blocks) >= 3, f"the guide has {len(blocks)} mtgui examples")
        cdir = os.path.join(OUT, "compat")
        os.makedirs(cdir, exist_ok=True)
        for i, code in enumerate(blocks, 1):
            prog = os.path.join(cdir, f"mtgui{i}.tuf")
            with open(prog, "w", encoding="utf-8") as f:
                f.write(code.replace("mention mtgui", "mention atgui").replace("mtgui.window", "atgui.window"))
            chk = subprocess.run([sys.executable, TUFF, "--check", prog], cwd=REPO, env=ENV, capture_output=True, text=True, encoding="utf-8")
            R.check(chk.returncode == 0 and chk.stdout.strip() == "OK", f"mtgui example {i}: --check says OK as atgui", chk.stdout + chk.stderr)
            driver = os.path.join(cdir, f"mtgui{i}.js")
            with open(driver, "w", encoding="utf-8") as f:
                f.write(CLOSE_AFTER_PAINT.replace("SHOT", json.dumps(f"compat-mtgui{i}")))
            r = drive(f"compat{i}", prog, driver)
            R.check(r.get("code") == 0 and r.get("stderr") == "" and (r.get("result") or {}).get("ok"),
                    f"mtgui example {i}: runs as atgui, no errors", (r.get("exit"), r.get("stderr"), r.get("result")))

    took = time.perf_counter() - started
    print(f"\natgui: {R.passed} passed, {R.failed} failed in {took:.0f} s (results and screenshots in {OUT})", flush=True)
    print("NUMBERS " + json.dumps(R.numbers), flush=True)
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"passed": R.passed, "failed": R.failed, "seconds": round(took, 1), "numbers": R.numbers}, f, indent=2)
    return 0 if R.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
