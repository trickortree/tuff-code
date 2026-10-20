"""The page's file server (no window needed): it still serves files, and a dropped connection prints
nothing. The window resets kept-alive connections it no longer wants, and Python used to print a
traceback for each one in the middle of the program's own output.

    py -3 tuffcode/test/view/view_server_test.py [--out result.json]
"""
import contextlib
import io
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
import tuff_view  # noqa: E402

passed = failed = 0


def check(ok, what):
    global passed, failed
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if ok:
        passed += 1
    else:
        failed += 1


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    err = io.StringIO()
    with tempfile.TemporaryDirectory() as web, contextlib.redirect_stderr(err):
        with open(os.path.join(web, "page.html"), "w", encoding="utf-8") as f:
            f.write("<p>hi</p>")
        srv = tuff_view._Files()
        srv.roots["token"] = (web, None)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/token/page.html", timeout=5) as r:
                got = (r.status, r.read())
        except OSError as e:
            got = (None, repr(e))
        for _ in range(3):  # half a request, then a reset, as a window dropping a connection does
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(b"GET /token/page.html HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n" % port)
            time.sleep(0.1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            s.close()
        time.sleep(0.5)
        srv.shutdown()
        srv.server_close()
    check(got == (200, b"<p>hi</p>"), f"a file is served with its token ({got[0]})")
    check(err.getvalue() == "", "three dropped connections print nothing" + ("" if not err.getvalue() else f": {err.getvalue()[:200]!r}"))
    print(f"view_server_test: {passed} passed, {failed} failed", flush=True)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"passed": passed, "failed": failed}, f)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
