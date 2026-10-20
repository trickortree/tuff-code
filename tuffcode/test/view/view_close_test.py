"""(e) Closing: closing the window ends the program cleanly, in each loop style.

Runs itself as a child process once per case and checks how the child ends. In the close cases the
child sends its own window WM_CLOSE (what the title bar's X sends) after a second and a half:
  - frame:   a pygame-style `while True: view.frame()` loop  -> frame() raises ViewClosed, exit 0;
  - loop:    every-frame function + loop()                    -> loop() returns, exit 0;
  - idle:    handlers only, loop() waiting for events          -> loop() returns, exit 0;
  - program: the program closes the window itself and returns 5 -> exit 5;
  - crash:   the program's loop raises an error                 -> window closes, error shown once, exit 1.

    py -3 tuffcode/test/view/view_close_test.py [--out result.json]
"""
import ctypes
import os
import subprocess
import sys
import threading
import time

from harness import Checks, finish, tuff_view, watchdog

CASES = {"frame": 0, "loop": 0, "idle": 0, "program": 5, "crash": 1}


def close_later(title, delay):
    """Send the window WM_CLOSE, the message its X button sends."""
    def go():
        time.sleep(delay)
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
        user32.PostMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
        hwnd = user32.FindWindowW(None, title)
        print(f"posting WM_CLOSE to {hwnd} at {time.perf_counter():.3f}", flush=True)
        user32.PostMessageW(hwnd, 0x0010, None, None)

    threading.Thread(target=go, daemon=True).start()


def child(case):
    title = f"Tuff view close test: {case} {os.getpid()}"

    def main():
        view = tuff_view.View(title, 420, 240)
        view.el("div", text=f"closing in 1.5 s ({case})", style={"padding": "20px"})
        view.on("close", lambda e: print("close handler ran", flush=True))
        if case in ("frame", "loop", "idle"):
            close_later(title, 1.5)
        if case == "frame":
            while True:
                view.frame()
        elif case == "loop":
            view.every_frame(lambda dt: None)
            view.loop()
        elif case == "idle":
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


def parent():
    checks = Checks("close")
    numbers = {}
    for case, want in CASES.items():
        start = time.perf_counter()
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", case], capture_output=True, text=True, timeout=40)
        took = time.perf_counter() - start
        out, err = p.stdout, p.stderr
        numbers[case] = {"exit": p.returncode, "seconds": round(took, 2)}
        if case in ("frame", "loop", "idle"):
            posted = float(out.split("at ")[1].split()[0]) if "posting WM_CLOSE" in out else None
            ended = float(out.split("run() returned")[1].split("at ")[1].split()[0]) if "run() returned" in out else None
            gone = round((ended - posted) * 1000) if posted and ended else None
            numbers[case]["close_to_return_ms"] = gone
            checks.check(p.returncode == want and "close handler ran" in out and gone is not None and gone < 2000,
                         f"{case}: closing the window ended the program (exit {p.returncode}, run() returned {gone} ms after WM_CLOSE)")
        elif case == "program":
            checks.check(p.returncode == want and "program kept going after close()" in out,
                         f"program: view.close() then return 5 (exit {p.returncode})")
        else:
            checks.check(p.returncode == want and err.count("RuntimeError: the program's loop failed") == 1,
                         f"crash: window closed, error shown once, exit {p.returncode}")
        checks.check(took < 15, f"{case}: the process was gone {took:.1f} s after it started")
        if p.returncode != want:
            print(out[-800:], err[-1500:], flush=True)
    return finish(checks, numbers)


if __name__ == "__main__":
    if "--child" in sys.argv:
        watchdog(30, "close child")
        sys.exit(child(sys.argv[sys.argv.index("--child") + 1]))
    watchdog(240, "close")
    sys.exit(parent())
