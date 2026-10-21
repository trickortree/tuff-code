"""(e) Closing: closing the window ends the program cleanly, in each loop style, at any moment, and the close
handlers always run.

Runs itself as a child process once per case and checks how the child ends. In the close cases the
child sends its own window WM_CLOSE (what the title bar's X sends) after a second and a half:
  - frame:   a pygame-style `while True: view.frame()` loop  -> frame() raises ViewClosed, exit 0;
  - loop:    every-frame function + loop()                    -> loop() returns, exit 0;
  - idle:    handlers only, loop() waiting for events          -> loop() returns, exit 0;
  - program: the program closes the window itself and returns 5 -> exit 5;
  - crash:   the program's loop raises an error                 -> window closes, error shown once, exit 1.
And the moments that once lost the close:
  - early:   WM_CLOSE the instant the window is on screen, before its page is ready -> View() still comes back
             (closed), so the close handler registered after it runs; exit 0;
  - queued:  the close arrives in the same batch as an event whose handler waits in frame(), as an atgui popup
             does -> ViewClosed unwinds that batch, and the close handler still runs; exit 0;
  - grace:   the process is ended the moment its window has gone (Cmd+Q on a Mac, logging off Windows) -> a
             close handler that takes 0.3 s had already finished; exit 7 (the child ending itself);
  - calls:   closed while the program calls the window all the time (set_title, resize: on Windows each waits
             for the window's thread) -> the closing window doesn't wait for the handler then, so no 2 s stall;
  - tgame:   a tgame program (through tuff.py) closed the instant its window appears, and 0.15 s later, still
             runs the code after its `while game:open():` loop, tgame's way to react to the window closing.

    py -3 tuffcode/test/view/view_close_test.py [--out result.json]
"""
import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time

from harness import REPO, Checks, finish, tuff_view, watchdog

CASES = {"frame": 0, "loop": 0, "idle": 0, "program": 5, "crash": 1, "early": 0, "queued": 0, "grace": 7, "calls": 0}
TGAME = """mention tgame

game = tgame.window("TITLE", 300, 200)
ball = game:circle(20, 100, 10, "red")
while game:open():
    dt = game:frame()
    ball:move(60 * dt, 0)
say "the loop ended"
"""


def user32():
    u = ctypes.windll.user32
    u.FindWindowW.restype = ctypes.c_void_p
    u.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
    u.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
    u.IsWindow.argtypes = u.IsWindowVisible.argtypes = (ctypes.c_void_p,)
    return u


def on_screen(title, timeout=30):
    """The window with this title once it's visible (polled every millisecond), or None."""
    u = user32()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = u.FindWindowW(None, title)
        if hwnd and u.IsWindowVisible(hwnd):
            return hwnd
        time.sleep(0.001)
    return None


def close_later(title, delay):
    """Send the window WM_CLOSE, the message its X button sends."""
    def go():
        time.sleep(delay)
        hwnd = user32().FindWindowW(None, title)
        print(f"posting WM_CLOSE to {hwnd} at {time.perf_counter():.3f}", flush=True)
        user32().PostMessageW(hwnd, 0x0010, None, None)

    threading.Thread(target=go, daemon=True).start()


def close_on_sight(title):
    """Send the window WM_CLOSE the instant it's on screen, long before its page is ready."""
    def go():
        hwnd = on_screen(title)
        print(f"posting WM_CLOSE to {hwnd} at {time.perf_counter():.3f}", flush=True)
        user32().PostMessageW(hwnd, 0x0010, None, None)

    threading.Thread(target=go, daemon=True).start()


def end_when_gone(title):
    """End this process the moment its window has gone, as Cmd+Q on a Mac or logging off Windows does."""
    def go():
        u = user32()
        hwnd = on_screen(title)
        while u.IsWindow(hwnd) and u.IsWindowVisible(hwnd):
            time.sleep(0.001)
        print("the window has gone: ending the process", flush=True)
        os._exit(7)

    threading.Thread(target=go, daemon=True).start()


def child(case):
    title = f"Tuff view close test: {case} {os.getpid()}"

    def main():
        if case == "early":
            close_on_sight(title)
        elif case == "grace":
            end_when_gone(title)
        view = tuff_view.View(title, 420, 240)
        if case == "early":
            print(f"View() came back, is_open {view.is_open}", flush=True)
        view.el("div", text=f"closing in 1.5 s ({case})", style={"padding": "20px"})

        def closed(e):
            if case == "grace":
                time.sleep(0.3)  # a close handler with something to do, like saving a file
            print("close handler ran", flush=True)
        view.on("close", closed)
        if case in ("frame", "loop", "idle", "grace", "calls"):
            close_later(title, 1.5)
        if case in ("frame", "early"):
            while True:
                view.frame()
        elif case in ("loop", "grace"):
            view.every_frame(lambda dt: None)
            view.loop()
        elif case == "calls":
            def busy(dt):  # the Tuff thread is nearly always inside a call to the window
                for i in range(20):
                    view.set_title(title)
                    view.resize(420 + i % 2, 240)
            view.every_frame(busy)
            view.loop()
        elif case == "idle":
            view.loop()
        elif case == "queued":
            def wait_for_answer(e):  # an atgui popup opened by a click waits for its answer like this
                while True:
                    view.frame()
            view.on("ping", wait_for_answer)
            for _ in range(30):
                view.frame()
            with view._cond:
                view._inbox.append({"type": "ping"})  # an event waiting while the program was busy
            close_later(title, 0)
            while view.is_open:  # the close arrives behind it, so the next batch holds both
                time.sleep(0.01)
            view.loop()
        elif case == "program":
            for _ in range(60):
                view.frame()
            view.close()
            print("program kept going after close()", flush=True)
            return 5
        elif case == "crash":
            for i in range(10 ** 9):
                view.frame()
                if i == 60:
                    raise RuntimeError("the program's loop failed")
        return 0

    code = tuff_view.run(main)
    print(f"run() returned {code} at {time.perf_counter():.3f}", flush=True)
    return code


def tgame_case(checks, numbers):
    """A tgame program closed the instant its window appears, and 0.15 s later, runs the code after its loop."""
    env = {k: v for k, v in os.environ.items() if k not in ("TUFF_TGAME_AUTOPILOT", "TUFF_IDE")}
    env["PYTHONIOENCODING"] = "utf-8"
    folder = tempfile.mkdtemp(prefix="tuff-view-close-")
    for delay in (0.0, 0.15):
        title = f"Tuff view close test: tgame {os.getpid()} {delay}"
        prog = os.path.join(folder, "close_early.tuf")
        with open(prog, "w", encoding="utf-8") as f:
            f.write(TGAME.replace("TITLE", title))
        start = time.perf_counter()
        p = subprocess.Popen([sys.executable, os.path.join(REPO, "tuff.py"), prog], cwd=folder, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        hwnd = on_screen(title)
        time.sleep(delay)
        if hwnd:
            user32().PostMessageW(hwnd, 0x0010, None, None)
        try:
            out, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
        took = time.perf_counter() - start
        numbers[f"tgame_{delay}"] = {"exit": p.returncode, "seconds": round(took, 2)}
        what = "the instant its window appeared" if not delay else f"{delay} s after its window appeared"
        checks.check(hwnd is not None and p.returncode == 0 and out.strip().endswith("the loop ended") and "Tuff error" not in err,
                     f"tgame: closed {what}, the code after its loop still ran (exit {p.returncode})")
        if p.returncode != 0 or not out.strip().endswith("the loop ended"):
            print(out[-800:], err[-1500:], flush=True)
    try:
        os.remove(prog)
        os.rmdir(folder)
    except OSError:
        pass


def parent():
    checks = Checks("close")
    numbers = {}
    for case, want in CASES.items():
        start = time.perf_counter()
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", case], capture_output=True, text=True, timeout=40)
        took = time.perf_counter() - start
        out, err = p.stdout, p.stderr
        numbers[case] = {"exit": p.returncode, "seconds": round(took, 2)}
        if case in ("frame", "loop", "idle", "early", "calls"):
            posted = float(out.split("at ")[1].split()[0]) if "posting WM_CLOSE" in out else None
            ended = float(out.split("run() returned")[1].split("at ")[1].split()[0]) if "run() returned" in out else None
            gone = round((ended - posted) * 1000) if posted and ended else None
            numbers[case]["close_to_return_ms"] = gone
            ok = p.returncode == want and "close handler ran" in out and gone is not None and gone < 2000
            if case == "early":
                checks.check(ok and "View() came back, is_open False" in out,
                             f"early: closed before its page was ready, View() came back closed and the close handler "
                             f"registered after it ran (exit {p.returncode}, run() returned {gone} ms after WM_CLOSE)")
            elif case == "calls":
                checks.check(ok, f"calls: closed while it calls the window all the time, the close handler ran with no "
                                 f"stall (exit {p.returncode}, run() returned {gone} ms after WM_CLOSE)")
            else:
                checks.check(ok, f"{case}: closing the window ended the program (exit {p.returncode}, run() returned {gone} ms after WM_CLOSE)")
        elif case == "queued":
            checks.check(p.returncode == want and out.count("close handler ran") == 1,
                         f"queued: the close behind a handler waiting in frame() still ran its handler, once (exit {p.returncode})")
        elif case == "grace":
            ran, gone = out.find("close handler ran"), out.find("the window has gone")
            checks.check(p.returncode == want and 0 <= ran < gone,
                         f"grace: a 0.3 s close handler had finished before the window went (exit {p.returncode})")
        elif case == "program":
            checks.check(p.returncode == want and "program kept going after close()" in out,
                         f"program: view.close() then return 5 (exit {p.returncode})")
        else:
            checks.check(p.returncode == want and err.count("RuntimeError: the program's loop failed") == 1,
                         f"crash: window closed, error shown once, exit {p.returncode}")
        checks.check(took < 15, f"{case}: the process was gone {took:.1f} s after it started")
        if p.returncode != want:
            print(out[-800:], err[-1500:], flush=True)
    tgame_case(checks, numbers)
    return finish(checks, numbers)


if __name__ == "__main__":
    if "--child" in sys.argv:
        watchdog(30, "close child")
        sys.exit(child(sys.argv[sys.argv.index("--child") + 1]))
    watchdog(300, "close")
    sys.exit(parent())
