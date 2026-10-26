"""tuff_view: the web view engine under atgui (apps) and tgame (2D and 3D games).

A window is a web page shown by pywebview: Edge WebView2 on Windows, WKWebView on a Mac. The page
(tuff_view_web/engine.js) keeps a retained scene, made of DOM elements, 2D canvases full of shapes and
three.js scenes, and draws it at the display's own rate. Python only sends changes, in one batch per
frame, and gets input back as batched events.

Threads: the window system needs the main thread, so run(main) starts the program on a thread of its
own, the Tuff thread, and gives the main thread to the window. Every callback, event handler and
per-frame function runs on the Tuff thread, inside frame() or loop(). Other threads only fill queues, and hold the
mouse for looking around or let go of it (_MouseHold), as the page says.
"""
import atexit
import http.server
import itertools
import json
import logging
import mimetypes
import os
import queue
import secrets
import shutil
import signal
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse

WEB_DIR = os.path.join(getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__)), "tuff_view_web")
DEFAULT_ICON = os.path.join(WEB_DIR, "icon.png")
OPEN_TIMEOUT = 30
# How long a closing window waits for the program's close handlers before it goes (see View._on_closing).
CLOSE_GRACE = 2.0
WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WEBVIEW2_MISSING = ("This program shows its window with Microsoft Edge WebView2, which isn't installed on this PC. "
                    f"Install the WebView2 Runtime from {WEBVIEW2_URL} and run it again.")
KEY_ALIASES = {"space": " ", "up": "arrowup", "down": "arrowdown", "left": "arrowleft", "right": "arrowright",
               "esc": "escape", "return": "enter", "ctrl": "control", "del": "delete"}
BUTTONS = {"left": 0, "middle": 1, "right": 2}
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
        ".svg": "image/svg+xml", ".ico": "image/x-icon", ".bmp": "image/bmp", ".wav": "audio/wav", ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".mp4": "video/mp4", ".webm": "video/webm", ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json", ".bin": "application/octet-stream", ".woff": "font/woff", ".woff2": "font/woff2",
        ".ttf": "font/ttf", ".otf": "font/otf"}
NO_HANDLERS = {}

# A callback that has already reported its own error (like the Runtime's rt.call) can return FAILED:
# the engine then treats it as failed, without reporting it a second time.
FAILED = object()


class _MouseHold:
    """The mouse held in the window for looking around (a first-person game), done here instead of with the
    browser's pointer lock and its "To show your cursor, press Esc" banner. The page hides the cursor and stands in
    for the lock (engine.js, nativeMouse); this, while the game's window is the one in front, keeps the cursor in the
    window, puts it back in the middle after every move and adds up how far it went, for View.mouse_delta. Windows:
    user32 (the cursor kept inside the window too); macOS: Quartz, and AppKit for the window. Elsewhere, where those
    don't work, or with TUFF_VIEW_POINTER_LOCK=1, None, and the browser's own lock is used.

    TUFF_VIEW_HOLD=0 (the tests' autopilot) leaves the real mouse alone: the page still stands in for the lock, and
    the moves come from the page's events."""

    RATE = 1 / 240  # how often it looks where the cursor went

    @classmethod
    def make(cls, view):
        if os.environ.get("TUFF_VIEW_POINTER_LOCK") == "1":
            return None
        try:
            hold = _WinHold(view) if sys.platform == "win32" else _MacHold(view) if sys.platform == "darwin" else None
        except Exception:
            return None
        if hold is not None:
            atexit.register(hold.stop)  # however the program ends, the cursor is let go
        return hold

    def __init__(self, view):
        self.view = view
        self.real = os.environ.get("TUFF_VIEW_HOLD") != "0"
        self.on = False      # the page holds the mouse
        self.active = False  # ...and so does the computer: the moves come from here, not from the page
        self.want = False    # what the page said last (View._on_events keeps it in the page's order)
        self.done = False    # the window closed or the program is ending: it's never held again
        self.lock = threading.Lock()
        self.stop_ev = threading.Event()
        self.thread = None

    def sync(self):
        """Hold the mouse or let go of it, as the page said last. This runs on the thread that hears it from the page
        (pywebview's, see View._on_events), not the program's: Escape and the window losing the focus let go at once,
        even while the program is busy or stuck in a loop with no frames, as with the browser's own lock."""
        with self.lock:
            on = self.want and not self.done
            if on == self.on:
                return
            self.on = on
            if on and self.real:
                self.stop_ev = threading.Event()  # each hold has its own, so one that's ending can't be woken up again
                self.thread = threading.Thread(target=self.run, args=(self.stop_ev,), name="tuff-view-mouse", daemon=True)
                self.thread.start()
            elif not on:
                self.stop_ev.set()
                if self.thread is not None and self.thread is not threading.current_thread():
                    self.thread.join(1.0)
                self.thread = None
                self.active = False
                self.let_go()

    def stop(self):
        """Let go for good: the window closed, or the program is ending."""
        self.done = True
        self.sync()

    def run(self, stop):
        home = None
        try:
            while not stop.is_set():
                if not self.ours():  # another window is in front: let go until ours is again
                    if home is not None:
                        self.let_go()
                        home = None
                        self.active = False
                elif home is None:
                    home = self.start()
                    self.active = home is not None
                else:
                    x, y = self.where()
                    dx, dy = x - home[0], y - home[1]
                    if dx or dy:
                        self.put(home[0], home[1])
                        self.view._moved(dx / home[2], dy / home[2])
                    home = self.refresh(home)
                stop.wait(self.RATE)
        except Exception:
            pass  # held no more; the page's moves are used again
        finally:
            self.active = False
            self.let_go()


class _WinHold(_MouseHold):
    def __init__(self, view):
        super().__init__(view)
        import ctypes
        from ctypes import wintypes
        self.ct, self.wt = ctypes, wintypes
        self.u = u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetForegroundWindow.restype = wintypes.HWND
        for name in ("GetClientRect", "ClientToScreen", "GetCursorPos"):
            getattr(u, name).restype = wintypes.BOOL
        u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        u.ClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
        self.dpi = getattr(u, "GetDpiForWindow", None)  # Windows 10 and later
        if self.dpi is not None:
            self.dpi.restype, self.dpi.argtypes = ctypes.c_uint, [wintypes.HWND]
        self.checked = 0.0

    def ours(self):
        hwnd = self.view._hwnd
        return bool(hwnd) and (self.u.GetForegroundWindow() or 0) == hwnd

    def area(self):
        """The window's inside, on the screen: its rectangle and its middle."""
        hwnd, w = self.view._hwnd, self.wt
        r, tl, br = w.RECT(), w.POINT(0, 0), w.POINT(0, 0)
        if not self.u.GetClientRect(hwnd, self.ct.byref(r)) or r.right - r.left < 4 or r.bottom - r.top < 4:
            return None
        br.x, br.y = r.right, r.bottom
        self.u.ClientToScreen(hwnd, self.ct.byref(tl))
        self.u.ClientToScreen(hwnd, self.ct.byref(br))
        return w.RECT(tl.x, tl.y, br.x, br.y)

    def start(self):
        r = self.area()
        if r is None:
            return None
        self.u.ClipCursor(self.ct.byref(r))
        scale = (self.dpi(self.view._hwnd) or 96) / 96 if self.dpi else 1.0  # screen pixels to the page's
        home = ((r.left + r.right) // 2, (r.top + r.bottom) // 2, max(0.5, scale), (r.left, r.top, r.right, r.bottom))
        self.put(home[0], home[1])
        self.checked = time.monotonic()
        return home

    def refresh(self, home):
        """Now and then: the window moved or changed size, so it's held in its new place."""
        if time.monotonic() - self.checked < 0.25:
            return home
        self.checked = time.monotonic()
        r = self.area()
        if r is None or (r.left, r.top, r.right, r.bottom) == home[3]:
            return home
        return self.start()

    def where(self):
        p = self.wt.POINT()
        self.u.GetCursorPos(self.ct.byref(p))
        return p.x, p.y

    def put(self, x, y):
        self.u.SetCursorPos(int(x), int(y))

    def let_go(self):
        try:
            self.u.ClipCursor(None)
        except Exception:
            pass


class _MacHold(_MouseHold):
    def __init__(self, view):
        super().__init__(view)
        import ctypes
        import ctypes.util

        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        class CGRect(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]

        self.ct, self.Point = ctypes, CGPoint
        self.cg = cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices")
                                               or "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        self.cf = cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation")
                                               or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        cg.CGEventCreate.restype, cg.CGEventCreate.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
        cg.CGEventGetLocation.restype, cg.CGEventGetLocation.argtypes = CGPoint, [ctypes.c_void_p]
        cg.CGWarpMouseCursorPosition.restype, cg.CGWarpMouseCursorPosition.argtypes = ctypes.c_int32, [CGPoint]
        cg.CGAssociateMouseAndMouseCursorPosition.restype = ctypes.c_int32
        cg.CGAssociateMouseAndMouseCursorPosition.argtypes = [ctypes.c_int32]
        cg.CGMainDisplayID.restype, cg.CGMainDisplayID.argtypes = ctypes.c_uint32, []
        cg.CGDisplayBounds.restype, cg.CGDisplayBounds.argtypes = CGRect, [ctypes.c_uint32]
        cf.CFRelease.restype, cf.CFRelease.argtypes = None, [ctypes.c_void_p]
        import AppKit  # PyObjC, which pywebview's Mac windows are made with
        self.app = AppKit.NSApplication.sharedApplication()
        self.checked = 0.0
        self.where()  # these work here, or the browser's lock is used
        self.middle()
        self.ours()

    def ours(self):
        """The game's window is the one in front, with the keys (the page also lets go when it loses the focus)."""
        win = self.view._win.native  # pywebview's NSWindow
        return bool(self.app.isActive() and win.isKeyWindow())

    def middle(self):
        """The middle of the window's inside, as Quartz counts: in points, down from the top of the main screen (AppKit
        counts up from its bottom)."""
        win = self.view._win.native
        r = win.contentRectForFrameRect_(win.frame())
        top = self.cg.CGDisplayBounds(self.cg.CGMainDisplayID()).h  # the main screen, the one with the menu bar
        return r.origin.x + r.size.width / 2, top - (r.origin.y + r.size.height / 2)

    def start(self):
        x, y = self.middle()
        self.put(x, y)
        self.checked = time.monotonic()
        return (x, y, 1.0)  # Quartz counts in points, as the page does

    def refresh(self, home):
        """Now and then: the window moved or changed size, so it's held in its new middle."""
        if time.monotonic() - self.checked < 0.25:
            return home
        self.checked = time.monotonic()
        x, y = self.middle()
        return home if abs(x - home[0]) < 1 and abs(y - home[1]) < 1 else self.start()

    def where(self):
        e = self.cg.CGEventCreate(None)
        if not e:
            raise OSError("no mouse")
        try:
            p = self.cg.CGEventGetLocation(e)
            return p.x, p.y
        finally:
            self.cf.CFRelease(e)

    def put(self, x, y):
        self.cg.CGWarpMouseCursorPosition(self.Point(x, y))
        self.cg.CGAssociateMouseAndMouseCursorPosition(1)  # without this, a warp freezes the mouse for a moment

    def let_go(self):
        pass


class ViewError(Exception):
    """Something went wrong with a window (it couldn't open, a file is missing...)."""


class ViewClosed(BaseException):
    """Raised by frame() once the window has closed (after the close handlers ran), to end the program.

    It's a BaseException so a library's `except Exception` (like tuff.py's call_python) lets it through;
    run() catches it and returns normally.
    """


# ---------------------------------------------------------------- running a program

class _Runner:
    def __init__(self):
        self.requests = queue.Queue()
        self.thread = None
        self.view = None


_runner = None


def run(main, *args):
    """Run main(*args) on the Tuff thread and give the main thread to the window system.

    Returns what main returned. Its errors are raised again here; ViewClosed (the window was closed) is
    a normal end. Call this from the main thread, before any window opens.
    """
    global _runner
    if threading.current_thread() is not threading.main_thread():
        raise ViewError("tuff_view.run() has to be called from the main thread.")
    runner = _runner = _Runner()
    outcome = {}

    def tuff_thread():
        try:
            try:
                outcome["value"] = main(*args)
            except ViewClosed:
                outcome["value"] = None
                if runner.view is not None:
                    runner.view._closing()  # the program ended because its window closed: its close handlers run
        except ViewClosed:
            pass
        except BaseException as exc:
            outcome["error"] = exc
        finally:
            if runner.view is not None:
                runner.view.close()
            runner.requests.put(("done", None))

    runner.thread = threading.Thread(target=tuff_thread, name="tuff", daemon=True)
    runner.thread.start()
    try:
        while True:
            try:
                kind, view = runner.requests.get(timeout=0.25)
            except queue.Empty:
                continue
            if kind == "done":
                break
            view._open()  # blocks until the window closes
    finally:
        _runner = None
    runner.thread.join()
    if runner.view is not None and _stuck_threads(2.0):
        # pywebview answers each page call on a thread of its own. If one of them got stuck while the window
        # was closing, Python would wait for it forever on the way out, so end the process here instead.
        if isinstance(outcome.get("error"), Exception):  # it can't be raised now: shown the way Python shows one
            sys.excepthook(type(outcome["error"]), outcome["error"], outcome["error"].__traceback__)
        sys.stdout.flush()
        sys.stderr.flush()
        value = outcome.get("value")
        os._exit(1 if "error" in outcome else value if isinstance(value, int) else 0)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def _stuck_threads(timeout):
    """pywebview's own threads still running after `timeout` seconds (a thread's target is kept while it runs)."""
    def pywebview_threads():
        return [th for th in threading.enumerate() if not th.daemon and th.is_alive()
                and getattr(getattr(th, "_target", None), "__module__", "").startswith("webview")]

    deadline = time.monotonic() + timeout
    for th in pywebview_threads():
        th.join(max(0.0, deadline - time.monotonic()))
    return pywebview_threads()


def _no_pywebview():
    """What to do when pywebview isn't installed, with the command for this computer (a Mac has python3, not py)."""
    python = "py" if sys.platform == "win32" else "python3"
    return f"App and game windows need pywebview. Install it with:  {python} -m pip install pywebview"


QUIET_FLAGS = ["--mute-audio", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
               "--disable-background-timer-throttling"]


def _quiet_window():
    """The window options for a test's window (TUFF_TEST_QUIET=1, which the test runners set), so the tests can run
    while someone uses the computer: past the right of every screen, never taking the focus or staying on top, and
    silent. The page still draws there (Chromium would pause a window it thinks is hidden) and acts as if it had the
    focus (View.__init__)."""
    args = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "").split()
    off = [a for a in args if a.startswith("--disable-features=")]
    features = [f for a in off for f in a.split("=", 1)[1].split(",") if f] + ["CalculateNativeWinOcclusion"]
    args = [a for a in args if a not in off and a not in QUIET_FLAGS] + QUIET_FLAGS
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = " ".join(args + ["--disable-features=" + ",".join(dict.fromkeys(features))])
    if sys.platform != "win32":
        # A Mac's window has to be on a screen (pywebview looks for the screen it's on: off them all, it can't open),
        # so it only stays out of the way of the windows in front.
        return {"on_top": False}
    try:
        import ctypes
        metric = ctypes.windll.user32.GetSystemMetrics
        x, y = metric(76) + metric(78) + 400, metric(77)  # the virtual screen's left + its width, its top
    except Exception:
        x, y = 20000, 0
    return {"x": x, "y": y, "focus": False, "on_top": False}


def _prepare_process(title):
    if sys.platform != "win32":
        return
    import ctypes
    try:
        app_id = "Tuff." + ("".join(ch for ch in title if ch.isalnum())[:40] or "App")
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


WEBVIEW2_KEYS = ("{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}", "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",  # runtime, beta
                 "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}", "{65C35B14-6C1D-4122-AC46-7148CC9D6497}")  # dev, canary


def _webview2_version():
    """The installed Edge WebView2 Runtime's version, or None (Windows).

    Checked before pywebview loads its Windows backend: without WebView2 that backend falls back to
    Internet Explorer's engine (which can't run the page) and switches python.exe to IE mode in the registry.
    """
    import winreg
    for key in WEBVIEW2_KEYS:
        for root, path in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"),
                           (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients"),
                           (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\EdgeUpdate\Clients")):
            try:
                with winreg.OpenKey(root, path + "\\" + key) as k:
                    version = str(winreg.QueryValueEx(k, "pv")[0])
            except OSError:
                continue
            if version and version != "0.0.0.0":
                return version
    return None


PROFILES = os.path.join(tempfile.gettempdir(), "tuff-view")


def _profile_dir():
    """A fresh WebView2 profile folder for this run (Windows). pywebview deletes it when the window closes;
    when that fails because a browser process still holds a file, a later program sweeps it up."""
    try:
        for name in os.listdir(PROFILES):
            pid = name.split("-")[0]
            if pid.isdigit() and not _running(int(pid)):
                shutil.rmtree(os.path.join(PROFILES, name), ignore_errors=True)
    except OSError:
        pass
    return os.path.join(PROFILES, f"{os.getpid()}-{secrets.token_hex(4)}")


def _running(pid):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = wintypes.DWORD()
    try:
        k32.GetExitCodeProcess(handle, ctypes.byref(code))
    finally:
        k32.CloseHandle(handle)
    return code.value == 259  # STILL_ACTIVE


def _fine_timers(on):
    """Windows wakes sleeping threads every 15.6 ms unless a program asks for 1 ms; frame pacing needs 1 ms."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        (ctypes.windll.winmm.timeBeginPeriod if on else ctypes.windll.winmm.timeEndPeriod)(1)
    except Exception:
        pass


# ---------------------------------------------------------------- serving the page and the program's files

def _inside(path, folder):
    try:
        return os.path.commonpath([os.path.normcase(path), os.path.normcase(folder)]) == os.path.normcase(folder)
    except ValueError:
        return False


class _Files(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FileHandler)
        self.roots = {}  # secret token -> (page folder, assets folder or None)

    def handle_error(self, request, client_address):
        # The window dropping a connection (closing, reloading, or a kept-alive one it no longer wants) is
        # normal. Python would print a traceback for it in the middle of the program's own output.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class _FileHandler(http.server.BaseHTTPRequestHandler):
    """Serves tuff_view_web/ and the program's assets folder, only to this machine and only with the token.

    A real http:// address (rather than file://) lets the page load ES modules (three.js) and use images
    as WebGL textures.
    """
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.serve(True)

    def do_HEAD(self):
        self.serve(False)

    def serve(self, body):
        port = self.server.server_address[1]
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return self.send_error(403)
        parts = urllib.parse.urlsplit(self.path).path.split("/", 2)
        if len(parts) < 3 or parts[1] not in self.server.roots:
            return self.send_error(404)
        web, assets = self.server.roots[parts[1]]
        rel = urllib.parse.unquote(parts[2])
        base = web
        if rel.startswith("assets/"):
            base, rel = assets, rel[len("assets/"):]
        if not base:
            return self.send_error(404)
        full = os.path.abspath(os.path.join(base, *rel.split("/")))
        if not _inside(full, base) or not os.path.isfile(full):
            return self.send_error(404)
        ctype = MIME.get(os.path.splitext(full)[1].lower()) or mimetypes.guess_type(full)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(os.path.getsize(full)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if body:
            with open(full, "rb") as f:
                shutil.copyfileobj(f, self.wfile)


_files = None
_files_lock = threading.Lock()


def _file_server():
    global _files
    with _files_lock:
        if _files is None:
            _files = _Files()
            threading.Thread(target=_files.serve_forever, name="tuff-view-files", daemon=True).start()
        return _files


# ---------------------------------------------------------------- objects in the window

class Node(int):
    """An object in the window: an element, a canvas, a 2D shape, a 3D scene or a 3D object.

    It is its own id, so it can be passed anywhere an id can (as a parent, in a View method...).
    """

    def __new__(cls, view, id_):
        node = int.__new__(cls, id_)
        node.view = view
        return node

    def set(self, **props):
        self.view.set(self, **props)
        return self

    def call(self, method, *args):
        self.view.call(self, method, *args)

    def ask(self, method, *args, timeout=5.0):
        return self.view.ask(self, method, *args, timeout=timeout)

    def on(self, type_, fn):
        self.view.on(type_, fn, self)
        return self

    def remove(self):
        self.view.remove(self)


def _props(props):
    if "cls" in props:
        props["class"] = props.pop("cls")
    return props


def _json_default(value):
    if isinstance(value, (set, frozenset)):
        return list(value)
    raise TypeError(f"{type(value).__name__} values can't be sent to the window")


class _Api:
    """What the page can call. pywebview runs each call on a new thread, so these only fill queues."""

    def __init__(self, view):
        self._view = view

    def ready(self, info):
        self._view._on_ready(info)

    def ev(self, seq, events):
        self._view._on_events(seq, events)


class View:
    """A window showing a web page that Python fills with elements, 2D shapes and 3D objects.

    Make it on the Tuff thread (inside run()). Then either call frame() in a loop (pygame style) or
    register functions with on() / every_frame() and call loop() (callback style); both can be mixed.
    """

    max_ahead = 2  # batches Python may be ahead of the page before frame() waits for it
    _hold = None  # the mouse held for looking around (_MouseHold), where the computer can do that
    _hwnd = 0  # the window's handle (Windows)
    _mlock = threading.Lock()  # the mouse's moves are added up on two threads

    def __init__(self, title="Tuff", width=900, height=600, icon=None, resizable=True, frameless=False, fps=60,
                 background="#0b0e14", assets=None, on_error=None, debug=False, **options):
        runner = _runner
        if runner is None:
            raise ViewError("Windows open inside tuff_view.run(...), which gives the window system the main thread.")
        if threading.current_thread() is not runner.thread:
            raise ViewError("Open the window from the program's own thread (the one tuff_view.run started).")
        if runner.view is not None:
            raise ViewError("This program already has a window. For now a program can open one window.")
        self.title = str(title)
        self.fps = fps
        self.on_error = on_error
        self.size = (int(width), int(height))
        self.mouse = (0, 0)
        self.buttons = set()
        self.values = {}  # element id -> its value, from the last input/change event
        self.info = {}
        self.stats = {"frames": 0, "flushes": 0, "commands": 0, "bytes": 0, "flush_ms": 0.0,
                      "sends": 0, "send_ms": 0.0, "events": 0}
        self._debug = debug
        self._thread = runner.thread
        self._cond = threading.Condition()
        self._ready = threading.Event()
        self._closed = False
        self._close_done = False      # the close handlers have started (they run once)
        self._close_finished = False  # ...and finished
        self._in_call = 0             # calls into pywebview's window in progress (see _window_call)
        self._failure = None
        self._win = None
        self._ids = itertools.count(1)
        self._cmds = []
        self._sets = {}
        self._kids = {}     # id -> the ids made inside it
        self._parents = {}  # id -> the id it was made in (0: the window)
        self._seq = 0
        self._outbox = []
        self._queued = self._sent = 0
        self._inbox = []
        self._pending = {}
        self._next_in = 1
        self._replies = {}
        self._tags = itertools.count(1)
        self._handlers = {}
        self._ticks = []
        self._reported = set()
        self._frame_events = []
        self._next_tick = None
        self._last_frame = None
        self._keys = {}  # code -> key, for the keys held down
        self._mdx = self._mdy = 0.0
        self._assets = os.path.abspath(assets) if assets else None
        icon = icon or os.environ.get("TUFF_APP_ICON") or DEFAULT_ICON
        self._icon = icon if os.path.isfile(icon) else None
        self._quiet = os.environ.get("TUFF_TEST_QUIET") == "1"
        if self._quiet:
            options = {**options, **_quiet_window()}
        self._window_args = dict(width=int(width), height=int(height), resizable=bool(resizable),
                                 frameless=bool(frameless), easy_drag=False, background_color=background, **options)
        files = _file_server()
        token = secrets.token_urlsafe(16)
        files.roots[token] = (WEB_DIR, self._assets)
        self._base = f"http://127.0.0.1:{files.server_address[1]}/{token}/"
        runner.view = self
        runner.requests.put(("window", self))
        deadline = time.monotonic() + OPEN_TIMEOUT
        while not self._ready.wait(0.1):
            if time.monotonic() > deadline:
                self.close()
                raise ViewError("The window opened but its page didn't start. If this keeps happening, reinstall "
                                f"the Microsoft Edge WebView2 Runtime ({WEBVIEW2_URL}).")
        if self._failure:
            raise self._failure
        # A window closed before its page was ready (its X clicked the moment it appeared) still gives a View, a
        # closed one, rather than raising ViewClosed: the program can then register its close handlers (atgui's
        # app:closed), and the first frame() or loop() runs them before the program ends.
        threading.Thread(target=self._send_loop, name="tuff-view-send", daemon=True).start()
        if self._quiet:
            self.js("document.hasFocus = () => true;")  # a quiet test's window never gets the focus: act as if it had
        self._hold = _MouseHold.make(self)
        if self._hold is not None:
            self.js("tv.nativeMouse(true)")  # the page stands in for the browser's pointer lock (no banner)

    # ------------------------------------------------ the window (main thread and pywebview's threads)

    def _open(self):
        """Main thread: make the window and run the window system until it closes."""
        try:
            import webview
        except ImportError:
            self._fail(ViewError(_no_pywebview()))
            return
        if sys.platform == "win32" and not webview.settings.get("WEBVIEW2_RUNTIME_PATH"):
            self.info["webview2"] = _webview2_version()
            if not self.info["webview2"]:
                self._fail(ViewError(WEBVIEW2_MISSING))
                return
        _prepare_process(self.title)
        _fine_timers(True)
        if not self._debug:
            # pywebview warns on stderr when it can't delete the profile folder; _profile_dir cleans those up.
            logging.getLogger("pywebview").setLevel(logging.ERROR)
        sigint = signal.getsignal(signal.SIGINT)
        try:
            self._win = webview.create_window(self.title, self._base + "index.html", js_api=_Api(self), **self._window_args)
            self._win.events.initialized += self._on_initialized
            self._win.events.before_show += self._on_before_show
            self._win.events.shown += self._on_shown
            if not self._window_args.get("confirm_close"):  # with a "Quit?" question, closing can still be cancelled
                self._win.events.closing += self._on_closing
            self._win.events.closed += self._on_closed
            webview.start(private_mode=True, debug=self._debug,
                          storage_path=_profile_dir() if sys.platform == "win32" else None)
        except Exception as exc:
            self._fail(ViewError(f"The window couldn't open: {exc}"))
        finally:
            signal.signal(signal.SIGINT, sigint)  # pywebview swaps in its own Ctrl+C handler
            _fine_timers(False)
            self._on_closed()

    def _on_initialized(self, renderer):
        # Without WebView2, pywebview falls back to Internet Explorer's engine, which can't run the page.
        if renderer in ("mshtml", "cef"):
            self._fail(ViewError(WEBVIEW2_MISSING))
            return False
        return True

    def _on_before_show(self, window):
        # pywebview only takes .ico files on Windows; this also takes the .png a built app carries (TUFF_APP_ICON).
        if sys.platform != "win32" or not self._icon:
            return
        try:
            from System.Drawing import Bitmap, Icon
            if self._icon.lower().endswith(".ico"):
                window.native.Icon = Icon(self._icon)
            else:
                window.native.Icon = Icon.FromHandle(Bitmap(self._icon).GetHicon())
        except Exception:
            pass

    def _on_shown(self, window=None):
        # TuffCode's Run button starts programs with no console window (SW_HIDE in their start-up info), and
        # Windows applies that to a program's first shown window too: the window was there but invisible. Only
        # the first show is overridden, so showing it again makes it appear.
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = self._hwnd = int((window or self._win).native.Handle.ToInt64())
            user32 = ctypes.windll.user32
            if not user32.IsWindowVisible(hwnd):
                user32.ShowWindow(hwnd, 5)  # SW_SHOW
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _on_ready(self, info):
        self.info.update(info or {})
        self.size = (self.info.get("w", self.size[0]), self.info.get("h", self.size[1]))
        self._ready.set()

    def _on_events(self, seq, events):
        with self._cond:
            self._pending[seq] = events
            if len(self._pending) > 64:  # a call went missing: don't hold everything else back for it
                self._next_in = min(self._pending)
            held = False
            while self._next_in in self._pending:
                for e in self._pending.pop(self._next_in):
                    if e.get("type") == "reply":
                        self._replies[e.get("tag")] = e
                    else:
                        self._inbox.append(e)
                        if e.get("type") == "capture" and self._hold is not None:  # the page holds the mouse, or lets go
                            self._hold.want, held = bool(e.get("on")), True
                self._next_in += 1
            self._cond.notify_all()
        if held:
            self._hold.sync()  # now, not when the program next collects its events: it may be busy

    def _on_closing(self):
        """The GUI thread, as the window starts to close (its X, Alt+F4, the taskbar, Cmd+Q, logging off...).

        The close is noted now, not when the window is gone, and the window waits (at most CLOSE_GRACE s) for the
        program's close handlers to run. Quitting a Mac app with Cmd+Q, or logging off Windows, can end the process
        as soon as its window has gone, before a handler that only started then had a chance to finish.
        """
        self._on_closed()
        if not self._handlers.get(None, NO_HANDLERS).get("close"):
            return None
        deadline = time.monotonic() + CLOSE_GRACE
        with self._cond:
            # Not while the program is calling the window (on Windows that call waits for this very thread).
            while not self._close_finished and not self._in_call and self._thread.is_alive():
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                self._cond.wait(left)
        return None  # False would cancel the close

    def _on_closed(self):
        with self._cond:
            if self._closed:
                return
            self._closed = True
            self._inbox.append({"type": "close"})
            self._cond.notify_all()
        if self._hold is not None:
            self._hold.stop()
        if not self._debug:
            # pywebview answers the page's last calls on threads of its own, and one that lands after the window
            # is gone logs "Cannot access a disposed object" with a traceback. That's only noise once it's closed.
            logging.getLogger("pywebview").setLevel(logging.CRITICAL)
        self._ready.set()

    def _fail(self, err):
        self._failure = err
        self._ready.set()

    def _send_loop(self):
        while True:
            with self._cond:
                while not self._outbox and not self._closed:
                    self._cond.wait()
                if self._closed:
                    return
                parts, self._outbox = self._outbox, []
            t0 = time.perf_counter()
            try:
                self._win.run_js("__tv.apply([" + ",".join(parts) + "])")
            except Exception as exc:
                with self._cond:
                    if not self._closed:
                        self._inbox.append({"type": "error", "message": str(exc), "where": "sending changes to the window"})
            with self._cond:
                self._sent += len(parts)
                self.stats["sends"] += 1
                self.stats["send_ms"] += (time.perf_counter() - t0) * 1000
                self._cond.notify_all()

    # ------------------------------------------------ changing the scene (Tuff thread)

    def create(self, kind, type_=None, parent=0, **props):
        """Add an object: kind is "el" (an HTML element; type_ is its tag), "canvas", "shape" (2D; in a canvas),
        "scene" (three.js) or "obj" (3D; in a scene or a group). Returns its Node."""
        if self._sets:
            self._move_sets()
        node = Node(self, next(self._ids))
        parent = int(parent or 0)
        self._cmds.append(["c", int(node), kind, type_, parent, _props(props) or None])
        self._kids.setdefault(parent, set()).add(int(node))
        self._parents[int(node)] = parent
        return node

    def el(self, tag="div", parent=0, **props):
        return self.create("el", tag, parent, **props)

    def canvas(self, parent=0, **props):
        return self.create("canvas", None, parent, **props)

    def shape(self, canvas, type_, **props):
        return self.create("shape", type_, canvas, **props)

    def scene(self, parent=0, **props):
        """A three.js scene. Besides its camera, sky and fog, lighting="modern" (tone mapping, light from the sky,
        shadows that follow the camera) or "simple" (the default)."""
        return self.create("scene", None, parent, **props)

    def obj(self, parent, type_, **props):
        """A 3D object in a scene or a group: a shape, a group, a light, a label, a model, "terrain" (a square of
        land: size, n, heights (n * n, row by row from -z to +z), style) or "water" (a lake: r; a sea: r=0, size)."""
        return self.create("obj", type_, parent, **props)

    def set(self, id_, **props):
        """Change an object's properties. Changes to the same object in one frame are merged into one."""
        p = self._sets.get(id_)
        if p is None:
            self._sets[id_] = _props(props)
            return
        for k, v in _props(props).items():
            old = p.get(k)
            p[k] = {**old, **v} if isinstance(v, dict) and isinstance(old, dict) else v

    def remove(self, id_):
        """Remove an object and everything inside it."""
        id_ = int(id_)
        self._sets.pop(id_, None)
        if self._sets:
            self._move_sets()
        self._cmds.append(["r", id_])
        # Forget it everywhere, its parent's list too, so a program that makes and removes things all the time
        # doesn't keep every id it ever made.
        siblings = self._kids.get(self._parents.get(id_))
        if siblings is not None:
            siblings.discard(id_)
        stack = [id_]
        while stack:
            i = stack.pop()
            stack.extend(self._kids.pop(i, ()))
            self._parents.pop(i, None)
            self._handlers.pop(i, None)
            self.values.pop(i, None)

    def call(self, id_, method, *args):
        """Call a method of an object in the page (id 0: the window itself), in order with the other changes."""
        if self._sets:
            self._move_sets()
        self._cmds.append(["k", int(id_ or 0), method, list(args)])

    def ask(self, id_, method, *args, timeout=5.0):
        """Like call(), but sends now and waits for the result (input that arrives meanwhile is kept for later)."""
        self._check_thread()
        if self._closed:
            return None
        tag = next(self._tags)
        if self._sets:
            self._move_sets()
        self._cmds.append(["k", int(id_ or 0), method, list(args), tag])
        self.flush()
        deadline = time.perf_counter() + timeout
        with self._cond:
            while tag not in self._replies:
                left = deadline - time.perf_counter()
                if self._closed:
                    return None
                if left <= 0:
                    raise ViewError(f"The window didn't answer {method} in time.")
                self._cond.wait(left)
            reply = self._replies.pop(tag)
        if reply.get("error"):
            raise ViewError(reply["error"])
        return reply.get("value")

    def js(self, code):
        """Run JavaScript in the page, in order with the other changes. It gets `tv` (window.tuffView)."""
        if self._sets:
            self._move_sets()
        self._cmds.append(["j", str(code)])

    def url(self, path):
        """The address the page uses for a file in the assets folder (an image, a sound, a texture...)."""
        if not self._assets:
            raise ViewError("This window wasn't given an assets folder.")
        full = os.path.abspath(os.path.join(self._assets, path))
        if not _inside(full, self._assets) or not os.path.isfile(full):
            raise ViewError(f"Couldn't find '{path}'. Put the file in {self._assets}.")
        return self._base + "assets/" + urllib.parse.quote(os.path.relpath(full, self._assets).replace(os.sep, "/"))

    def _move_sets(self):
        cmds = self._cmds
        for i, p in self._sets.items():
            cmds.append(["s", i, p])
        self._sets = {}

    def flush(self):
        """Send the changes made so far now. frame() and loop() do this for you."""
        if self._closed:
            self._cmds = []
            self._sets = {}
            return
        if self._sets:
            self._move_sets()
        if not self._cmds:
            return
        t0 = time.perf_counter()
        self._seq += 1
        data = json.dumps([self._seq, self._cmds], separators=(",", ":"), default=_json_default)
        count = len(self._cmds)
        self._cmds = []
        with self._cond:
            self._outbox.append(data)
            self._queued += 1
            self._cond.notify_all()
        st = self.stats
        st["flushes"] += 1
        st["commands"] += count
        st["bytes"] += len(data)
        st["flush_ms"] += (time.perf_counter() - t0) * 1000

    # ------------------------------------------------ input

    def on(self, type_, fn, id_=None):
        """Call fn(event) for each event of this type: one object's (and what's inside it), or with no id any.

        Types: click, dblclick, mousedown, mouseup, mousemove, wheel, keydown, keyup, input, change, submit,
        resize, focus, blur, lock, close, error, and any custom type the page emits.
        """
        self._handlers.setdefault(int(id_) if id_ else None, {}).setdefault(type_, []).append(fn)

    def every_frame(self, fn):
        """Call fn(dt) once per frame in loop(), with the seconds since the last frame."""
        self._ticks.append(fn)

    def events(self):
        """The events of the last frame (pygame style)."""
        return self._frame_events

    def key_down(self, name):
        """Is this key held? Takes a key ("a", "Enter", "space", "up") or a key code ("KeyW", "ArrowUp")."""
        n = str(name).lower()
        n = KEY_ALIASES.get(n, n)
        keys = self._keys
        return n in keys or n in keys.values() or ("key" + n) in keys or ("digit" + n) in keys

    def mouse_down(self, button=0):
        return BUTTONS.get(button, button) in self.buttons

    def mouse_delta(self):
        """How far the mouse moved since the last call (works with the pointer locked, for mouse look)."""
        with self._mlock:
            d = (self._mdx, self._mdy)
            self._mdx = self._mdy = 0.0
        return d

    def _moved(self, dx, dy):
        with self._mlock:
            self._mdx += dx
            self._mdy += dy

    def _collect(self):
        with self._cond:
            evs, self._inbox = self._inbox, []
        if not evs:
            return
        self._frame_events.extend(evs)
        self.stats["events"] += len(evs)
        for e in evs:
            t = e.get("type")
            if t == "mousemove":
                self.mouse = (e["x"], e["y"])
                if not (self._hold is not None and self._hold.active):  # (held, it measures the moves itself)
                    self._moved(e.get("dx", 0), e.get("dy", 0))
            elif t == "keydown":
                self._keys[str(e.get("code") or e.get("key")).lower()] = str(e.get("key")).lower()
            elif t == "keyup":
                self._keys.pop(str(e.get("code") or e.get("key")).lower(), None)
            elif t == "mousedown":
                self.buttons.add(e.get("button", 0))
            elif t == "mouseup":
                self.buttons.discard(e.get("button", 0))
            elif t == "blur":
                self._keys.clear()
                self.buttons.clear()
            elif t == "resize":
                self.size = (e["w"], e["h"])
            elif t in ("input", "change"):
                self.values[e.get("id")] = e.get("value")
            elif t == "error":
                self._report(f"the window ({e.get('where') or 'page'})", ViewError(e.get("message", "")))
            self._dispatch(e)

    def _dispatch(self, e):
        t = e.get("type")
        if t == "close":
            if self._close_done:
                return
            self._close_done = True
            try:
                self._handle(e, t)
            finally:
                with self._cond:
                    self._close_finished = True
                    self._cond.notify_all()
            return
        self._handle(e, t)

    def _closing(self):
        """Once the window has closed, run the close handlers now if they haven't run yet.

        frame() and loop() call this as they end, because the close event can be stuck further up: in the batch
        that _collect() was going through when a handler waited in frame() (an atgui popup does) and the window
        closed. ViewClosed then unwinds that batch, and without this the close handlers would never run.
        """
        if self._closed and not self._close_done:
            self._dispatch({"type": "close"})

    def _handle(self, e, t):
        for i in e.get("path") or ():
            fns = self._handlers.get(i, NO_HANDLERS).get(t)
            if fns:
                for fn in list(fns):
                    self._safe(fn, e, f"a {t} handler")
                break
        for fn in list(self._handlers.get(None, NO_HANDLERS).get(t, ())):
            self._safe(fn, e, f"a {t} handler")

    def _safe(self, fn, arg, where):
        try:
            return fn(arg) is not FAILED
        except ViewClosed:
            raise
        except Exception as exc:
            self._report(where, exc)
            return False

    def _report(self, where, exc):
        """Report an error once: the same error from the same place every frame is only shown the first time."""
        key = (where, type(exc).__name__, str(exc))
        if key in self._reported:
            return
        self._reported.add(key)
        if self.on_error:
            try:
                self.on_error(exc, where)
                return
            except Exception:
                pass
        sys.stderr.write(f"Error in {where}:\n" + "".join(traceback.format_exception(exc)))
        sys.stderr.flush()

    # ------------------------------------------------ the two loop styles

    def frame(self):
        """One tick of a pygame-style loop: send this frame's changes, wait for the next tick, collect input.

        Returns the seconds since the last frame. Once the window has closed it raises ViewClosed, which
        ends the program (run() treats it as a normal end).
        """
        self._check_thread()
        if self._closed:
            self._collect()
            self._closing()
            raise ViewClosed()
        self.flush()
        self._wait_room()
        self._sleep_until(self._tick())
        self._frame_events = []
        self._collect()
        self.stats["frames"] += 1
        if self._closed:
            self._closing()
            raise ViewClosed()
        now = time.perf_counter()
        dt = now - self._last_frame if self._last_frame else 0.0
        self._last_frame = now
        return dt

    def loop(self):
        """Callback style: run the every-frame functions and the event handlers until the window closes.

        Events are handled as soon as they arrive, not at the next frame, so UIs answer within a millisecond
        or two. With no every-frame functions it just waits for events. A function that fails is reported
        once and switched off.
        """
        self._check_thread()
        last = time.perf_counter()
        while not self._closed:
            if self._ticks:
                now = time.perf_counter()
                dt, last = now - last, now
                self._frame_events = []
                for fn in list(self._ticks):
                    if not self._safe(fn, dt, "an every-frame function") and fn in self._ticks:
                        self._ticks.remove(fn)
                self.stats["frames"] += 1
            self.flush()
            self._wait_room()
            deadline = self._tick() if self._ticks else None
            while not self._closed and self._wait_events(deadline):
                self._collect()
                self.flush()
        self._collect()
        self._closing()

    def _tick(self):
        """When the next frame is due. Running late by over a frame restarts the clock instead of rushing."""
        now = time.perf_counter()
        if not self.fps:
            return now
        period = 1.0 / self.fps
        nxt = (self._next_tick or now) + period
        if now - nxt > period:
            nxt = now
        self._next_tick = nxt
        return nxt

    def _sleep_until(self, when):
        left = when - time.perf_counter()
        if left > 0:
            time.sleep(left)

    def _wait_events(self, deadline):
        with self._cond:
            while not self._inbox and not self._closed:
                if deadline is None:
                    self._cond.wait()
                    continue
                left = deadline - time.perf_counter()
                if left <= 0:
                    return False
                self._cond.wait(left)
            return True

    def _wait_room(self):
        with self._cond:
            while self._queued - self._sent >= self.max_ahead and not self._closed:
                self._cond.wait(0.1)

    def _check_thread(self):
        if threading.current_thread() is not self._thread:
            raise ViewError("Use the window from the program's own thread (the one tuff_view.run started).")

    # ------------------------------------------------ the window itself

    @property
    def is_open(self):
        return not self._closed

    @property
    def batch(self):
        """The number of the batch that changes made now go to the page in (the page counts the batches it has
        applied, so an event it sends can say whether it saw them)."""
        return self._seq + 1

    def page_stats(self, reset=False):
        """The page's own numbers: frames drawn per second, frame gaps, time spent applying and drawing."""
        return self.ask(0, "stats", bool(reset))

    def page_png(self, timeout=15.0):
        """A PNG of the whole page as the window shows it, elements included (the page's own snapshot has only its
        canvases and 3D scenes): WebView2's DevTools screenshot, for tests. None where it can't be taken (not on
        Windows, or the window is closing)."""
        if sys.platform != "win32":
            return None
        with self._cond:
            if self._closed or self._win is None:
                return None
            self._in_call += 1  # like _window_call: a closing window doesn't wait for the GUI thread meanwhile
        try:
            import base64
            from System import Func, Object  # pythonnet, which pywebview loads on Windows
            form = self._win.native
            web = form.browser.webview
            box = {}

            def start():
                box["task"] = web.CoreWebView2.CallDevToolsProtocolMethodAsync("Page.captureScreenshot", '{"format":"png"}')
                return None
            form.Invoke(Func[Object](start))
            if not box["task"].Wait(int(timeout * 1000)):
                return None
            return base64.b64decode(json.loads(str(box["task"].Result))["data"])
        except Exception:
            return None
        finally:
            with self._cond:
                self._in_call -= 1
                self._cond.notify_all()

    def _window_call(self, method, *args):
        """Call a method of pywebview's window, unless the window has closed (or started to).

        On Windows such a call waits for the window's own thread, so a closing window, which waits on that thread
        for the close handlers, doesn't wait while one is in progress (see _on_closing). An error from a window
        that closed meanwhile is dropped: there's nothing left to change.
        """
        with self._cond:
            if self._closed or self._win is None:
                return
            self._in_call += 1
        try:
            getattr(self._win, method)(*args)
        except Exception:
            if not self._closed:
                raise
        finally:
            with self._cond:
                self._in_call -= 1
                self._cond.notify_all()

    def set_title(self, title):
        self.title = str(title)
        self._window_call("set_title", self.title)

    def resize(self, width, height):
        self._window_call("resize", int(width), int(height))

    def move(self, x, y):
        self._window_call("move", int(x), int(y))

    def minimize(self):
        self._window_call("minimize")

    def maximize(self):
        self._window_call("maximize")

    def restore(self):
        self._window_call("restore")

    def fullscreen(self):
        """Switch full screen on or off."""
        self._window_call("toggle_fullscreen")

    def close(self):
        """Close the window. The next frame() raises ViewClosed; loop() returns."""
        if self._closed:
            return
        if self._win is not None:
            try:
                self._window_call("destroy")
            except Exception:
                pass
            with self._cond:
                deadline = time.monotonic() + 5
                while not self._closed and time.monotonic() < deadline:
                    self._cond.wait(0.1)
        self._on_closed()


class Recorder(View):
    """Tuff Engine's preview (tuff.py --scene): keeps every command a program's setup sends. No window, no sound.

    It doesn't call View.__init__ (that opens a window): it sets just the state the inherited create, el, canvas,
    shape, scene, obj, set, remove, call, _move_sets, on, every_frame, events, key_down, mouse_down, mouse_delta
    and is_open use. Pictures, sounds and models come back as "asset:<path in the assets folder>"."""

    def __init__(self, title="Tuff", width=900, height=600, assets=None, on_create=None, **_ignored):
        self.title = str(title)
        self.size = (int(width), int(height))
        self.mouse = (0, 0)
        self.buttons = set()
        self.values = {}
        self.info = {"webgl": True}
        self.stats = {}
        self._closed = False
        self._ids = itertools.count(1)
        self._cmds, self._sets, self._kids, self._parents, self._handlers = [], {}, {}, {}, {}
        self._ticks, self._frame_events, self._keys = [], [], {}
        self._mdx = self._mdy = 0.0
        self._assets = os.path.abspath(assets) if assets else None
        self._on_create = on_create

    def create(self, kind, type_=None, parent=0, **props):
        node = super().create(kind, type_, parent, **props)
        if self._on_create:
            self._on_create(int(node))
        return node

    def ask(self, id_, method, *args, timeout=5.0):
        return None

    def js(self, code):
        pass

    def url(self, path):
        if not self._assets:
            raise ViewError("This window wasn't given an assets folder.")
        full = os.path.abspath(os.path.join(self._assets, path))
        if not _inside(full, self._assets) or not os.path.isfile(full):
            raise ViewError(f"Couldn't find '{path}'. Put the file in {self._assets}.")
        return "asset:" + os.path.relpath(full, self._assets).replace(os.sep, "/")

    def flush(self): pass
    def frame(self): return 0.0
    def loop(self): pass
    def page_stats(self, reset=False): return {}
    def page_png(self, timeout=15.0): return None
    def set_title(self, title): self.title = str(title)
    def resize(self, width, height): pass
    def move(self, x, y): pass
    def minimize(self): pass
    def maximize(self): pass
    def restore(self): pass
    def fullscreen(self): pass
    def close(self): self._closed = True

    def record(self):
        """Every command so far, in order (the changes still being merged go last, as a frame would send them)."""
        if self._sets:
            self._move_sets()
        return self._cmds
