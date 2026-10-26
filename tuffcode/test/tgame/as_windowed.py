"""Runs a Build exe launcher (tuff_app.py, from build_exe_pack_test.mjs's stand-in app folder) the way an app with no
console runs it, but without opening anything: its error box (Windows' MessageBox, a Mac's alert) is stood in for and
what it would say goes in a JSON file, written again after each box (the app may end with os._exit).

    py -3 as_windowed.py <tuff_app.py> <out.json> [none|crash|thread|hook|twice|stuck] [console]

The mode makes a problem inside Tuff itself, not in the program: crash raises from the runtime, thread raises in a
thread, hook hands one to sys.excepthook, twice raises the same one in two threads, and stuck ends tuff_view.run the way
it does when pywebview's threads are stuck (os._exit), with a stand-in window. console runs it with its console.
"""
import ctypes
import json
import os
import runpy
import subprocess
import sys
import threading

launcher, out_path = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "none"
console = "console" in sys.argv[4:]
boxes = []
state = {"code": None, "boxes": boxes, "windowed": None}


def record():
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def box(title, text):
    boxes.append({"title": title, "text": text})
    record()


class _User32:
    def MessageBoxW(self, hwnd, text, title, flags):
        box(title, text)
        return 1  # OK


class _Dlls:
    user32 = _User32()


ctypes.windll = _Dlls()
_run = subprocess.run


def _alert(cmd, *args, **kwargs):
    if cmd and cmd[0] == "osascript":
        box("Something went wrong", cmd[-1])
        return subprocess.CompletedProcess(cmd, 0)
    return _run(cmd, *args, **kwargs)


subprocess.run = _alert
# A built game or console app has no tkinter (build.js leaves it out), so tuff.report's own tkinter box can't show.
sys.modules["tkinter"] = None
sys.modules["tkinter.messagebox"] = None
sys.path.insert(0, os.path.dirname(os.path.abspath(launcher)))
import tuff  # noqa: E402 (the launcher's own copy, from its folder)

real_run_program = tuff.run_program


def boom():
    raise RuntimeError("the engine broke")


def in_thread():
    t = threading.Thread(target=boom)
    t.start()
    t.join()


def stuck():
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))  # a console app has none
    import tuff_view

    class Window:  # stands in for tuff_view.View: nothing opens
        def close(self):
            pass

        def _closing(self):
            pass

    def main():
        tuff_view._runner.view = Window()
        boom()

    tuff_view._stuck_threads = lambda timeout: True
    return tuff_view.run(main)


def run_program(path):
    if mode == "crash":
        boom()
    elif mode == "thread":
        in_thread()
    elif mode == "twice":
        in_thread()
        in_thread()
    elif mode == "hook":
        try:
            boom()
        except RuntimeError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)
    elif mode == "stuck":
        return stuck()
    return real_run_program(path)


tuff.run_program = run_program
if not console:
    sys.stdout = None  # what an app with no console starts with: tuff.setup_streams sees it and sets WINDOWED
try:
    runpy.run_path(launcher, run_name="__main__")
except SystemExit as exc:
    state["code"] = exc.code
state["windowed"] = tuff.WINDOWED
record()
