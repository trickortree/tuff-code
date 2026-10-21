"""Windows only: waits for a built app's error box ("Something went wrong", the MessageBox build.js's launcher shows),
prints what it says as JSON and closes it, the way someone would click OK.

    py -3 error_box.py <path of the .exe> [seconds to wait, default 30]

Only boxes of processes started from that .exe count (a --onefile app runs as two processes with the same path).
Prints {"found": false} if no box came up in time.
"""
import ctypes
import ctypes.wintypes as w
import json
import os
import sys
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM), w.LPARAM]
user32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [w.HWND]
user32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
user32.GetWindowTextLengthW.argtypes = [w.HWND]
user32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetDlgItem.argtypes = [w.HWND, ctypes.c_int]
user32.GetDlgItem.restype = w.HWND
user32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
kernel32.OpenProcess.restype = w.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
kernel32.CloseHandle.argtypes = [w.HANDLE]
EACH = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
WM_CLOSE = 0x0010
MESSAGE_TEXT = 0xFFFF  # a MessageBox's text is the static control with this id


def exe_of(pid):
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = w.DWORD(len(buf))
        return buf.value if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else None
    finally:
        kernel32.CloseHandle(handle)


def text_of(hwnd):
    if not hwnd:
        return ""
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def boxes(exe):
    found = []

    def each(hwnd, _):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value == "#32770" and user32.IsWindowVisible(hwnd):  # a dialog box
            pid = w.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            path = exe_of(pid.value)
            if path and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(exe)):
                found.append(hwnd)
        return True

    user32.EnumWindows(EACH(each), 0)
    return found


def main():
    exe = sys.argv[1]
    deadline = time.time() + (float(sys.argv[2]) if len(sys.argv) > 2 else 30)
    while time.time() < deadline:
        for hwnd in boxes(exe):
            title, text = text_of(hwnd), text_of(user32.GetDlgItem(hwnd, MESSAGE_TEXT))
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)  # what OK does
            print(json.dumps({"found": True, "title": title, "text": text}))
            return 0
        time.sleep(0.2)
    print(json.dumps({"found": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
