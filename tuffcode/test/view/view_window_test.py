"""(f) Window options and failures (Windows): frameless, not resizable, icons, title, resize, no WebView2.

Runs itself as a child process once per case and looks at the real window with Win32 calls:
  - options:  frameless + not resizable + a .png icon -> no caption or sizing border, the icon is ours;
  - ico:      a .ico icon                             -> the icon is ours;
  - built:    TUFF_APP_ICON (what a built app sets)   -> its windows use that icon by default;
  - missing:  as if WebView2 weren't installed        -> a clear error, no window, exit 1;
  - nopywebview: as if pywebview weren't installed    -> the install command for this computer, no window, exit 1;
  - outside:  View() without run()                    -> a clear error.

    py -3 tuffcode/test/view/view_window_test.py [--out result.json]
"""
import ctypes
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from ctypes import wintypes

from harness import Checks, finish, tuff_view, watchdog

COLORS = {"options": (230, 30, 200), "ico": (30, 200, 90), "built": (250, 160, 20)}


def png(size, rgb):
    raw = b"".join(b"\x00" + bytes(rgb + (255,)) * size for _ in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def ico(size, rgb):
    data = png(size, rgb)
    return struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), 22) + data


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", wintypes.LONG), ("bmWidth", wintypes.LONG), ("bmHeight", wintypes.LONG),
                ("bmWidthBytes", wintypes.LONG), ("bmPlanes", wintypes.WORD), ("bmBitsPixel", wintypes.WORD),
                ("bmBits", ctypes.c_void_p)]


def win32():
    user32, gdi32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.SendMessageW.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p)
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetIconInfo.argtypes = (ctypes.c_void_p, ctypes.POINTER(ICONINFO))
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    gdi32.GetObjectW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.argtypes = (ctypes.c_void_p,)
    gdi32.SelectObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    gdi32.GetPixel.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
    gdi32.GetPixel.restype = wintypes.DWORD
    gdi32.DeleteDC.argtypes = (ctypes.c_void_p,)
    gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
    return user32, gdi32


def look(title):
    """What Windows says about the window: style flags, its big icon (size and middle pixel), title, size."""
    user32, gdi32 = win32()
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None
    style = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    out = {"caption": bool(style & 0x00C00000 == 0x00C00000), "sizing": bool(style & 0x00040000)}
    hicon = user32.SendMessageW(hwnd, 0x007F, 1, 0)  # WM_GETICON, ICON_BIG
    info = ICONINFO()
    if hicon and user32.GetIconInfo(hicon, ctypes.byref(info)):
        bmp = BITMAP()
        gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bmp))
        dc = gdi32.CreateCompatibleDC(None)
        gdi32.SelectObject(dc, info.hbmColor)
        c = gdi32.GetPixel(dc, bmp.bmWidth // 2, bmp.bmHeight // 2)
        gdi32.DeleteDC(dc)
        gdi32.DeleteObject(info.hbmColor)
        gdi32.DeleteObject(info.hbmMask)
        out["icon"] = [bmp.bmWidth, (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)]
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    out["title"] = buf.value
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    out["rect"] = [r.right - r.left, r.bottom - r.top]
    return out


def child(case, icon_path):
    title = f"Tuff view window test: {case} {os.getpid()}"
    report = {}

    def main():
        if case == "missing":
            tuff_view._webview2_version = lambda: None
        if case == "nopywebview":
            sys.modules["webview"] = None  # `import webview` fails, as in a Python without pywebview
        kw = {}
        if case == "options":
            kw = {"frameless": True, "resizable": False, "icon": icon_path}
        elif case == "ico":
            kw = {"icon": icon_path}
        view = tuff_view.View(title, 480, 320, **kw)
        view.el("div", text=case, style={"padding": "20px"})
        for _ in range(10):
            view.frame()
        report["before"] = look(title)
        view.set_title(title + " (renamed)")
        view.resize(520, 360)
        for _ in range(20):
            view.frame()
        report["after"] = look(title + " (renamed)")
        report["page_size"] = list(view.size)
        report["dpr"] = view.info.get("dpr")
        report["webview2"] = view.info.get("webview2")
        view.close()

    try:
        tuff_view.run(main)
    except tuff_view.ViewError as err:
        report["error"] = str(err)
    report["windows_left"] = bool(look(title))
    print("REPORT " + json.dumps(report), flush=True)
    return 1 if "error" in report else 0


def parent():
    checks = Checks("window")
    numbers = {}
    folder = tempfile.mkdtemp(prefix="tuff-view-icons-")
    icons = {"options": os.path.join(folder, "icon.png"), "ico": os.path.join(folder, "icon.ico"),
             "built": os.path.join(folder, "app_icon.png")}
    with open(icons["options"], "wb") as f:
        f.write(png(64, COLORS["options"]))
    with open(icons["ico"], "wb") as f:
        f.write(ico(48, COLORS["ico"]))
    with open(icons["built"], "wb") as f:
        f.write(png(128, COLORS["built"]))
    for case in ("options", "ico", "built", "missing", "nopywebview"):
        env = dict(os.environ)
        if case == "built":
            env["TUFF_APP_ICON"] = icons["built"]
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--child", case, icons.get(case, "")],
                           capture_output=True, text=True, timeout=60, env=env)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("REPORT ")), None)
        r = json.loads(line[7:]) if line else {}
        numbers[case] = r
        if not line:
            print(p.stdout[-1500:], p.stderr[-1500:], flush=True)
        if case == "missing":
            checks.check(p.returncode == 1 and "WebView2" in r.get("error", "") and not r.get("windows_left"),
                         f"missing: no WebView2 gives a clear error and no window ({r.get('error', '')[:70]}...)")
            continue
        if case == "nopywebview":
            checks.check(p.returncode == 1 and r.get("error", "").startswith("App and game windows need pywebview")
                         and "py -m pip install pywebview" in r.get("error", "") and not r.get("windows_left"),
                         f"no pywebview: the error says how to install it here, and no window ({r.get('error')})")
            continue
        before, after = r.get("before") or {}, r.get("after") or {}
        icon = before.get("icon")
        want = list(COLORS[case])
        checks.check(p.returncode == 0 and before and after, f"{case}: the window opened and closed (exit {p.returncode})")
        checks.check(icon is not None and list(icon[1]) == want, f"{case}: the window shows our icon ({icon} vs color {want})")
        if case == "options":
            checks.check(not before.get("caption") and not before.get("sizing"),
                         f"options: frameless and not resizable (caption {before.get('caption')}, sizing border {before.get('sizing')})")
        else:
            checks.check(before.get("caption") and before.get("sizing"), f"{case}: a normal window has a caption and a sizing border")
        checks.check(after.get("title", "").endswith("(renamed)"), "set_title() renamed the window")
        dpr = r.get("dpr") or 1
        checks.check(abs(after.get("rect", [0])[0] - 520 * dpr) <= 2 * dpr, f"resize() made it 520 wide ({after.get('rect')} at dpr {dpr})")
        if case == "options":
            checks.check(r.get("page_size") == [520, 360], f"the page saw the resize ({r.get('page_size')})")
    try:
        tuff_view.View("outside run()")
        outside = None
    except tuff_view.ViewError as err:
        outside = str(err)
    checks.check(outside and "run(" in outside, f"outside: View() without run() explains itself ({outside})")
    real = sys.platform
    try:
        sys.platform = "darwin"
        mac = tuff_view._no_pywebview()
    finally:
        sys.platform = real
    checks.check("python3 -m pip install pywebview" in mac and " py -m" not in mac,
                 f"no pywebview on a Mac: the command is python3, which a Mac has ({mac})")
    shutil.rmtree(folder, ignore_errors=True)
    return finish(checks, numbers)


if __name__ == "__main__":
    if sys.platform != "win32":
        print("window test: skipped (Windows only)")
        sys.exit(0)
    if "--child" in sys.argv:
        watchdog(40, "window child")
        i = sys.argv.index("--child")
        sys.exit(child(sys.argv[i + 1], sys.argv[i + 2] if len(sys.argv) > i + 2 else ""))
    watchdog(200, "window")
    sys.exit(parent())
