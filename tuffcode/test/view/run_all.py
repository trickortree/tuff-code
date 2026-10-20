"""Run every tuff_view test, one after another, and sum up the checks.

Each test opens a real window on this screen for a few seconds and closes it by itself; don't cover
the windows while they run (a covered page stops drawing). Results go to --out-dir as JSON.

    py -3 tuffcode/test/view/run_all.py [--out-dir folder] [--sweep]
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = ["view_ui_test.py", "view_2d_stress.py", "view_3d_test.py", "view_latency.py", "view_close_test.py",
         "view_window_test.py"]


def main():
    out_dir = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(tempfile.gettempdir(), "tuff-view-results")
    os.makedirs(out_dir, exist_ok=True)
    passed = failed = 0
    rows = []
    for test in TESTS:
        name = os.path.splitext(test)[0]
        out = os.path.join(out_dir, name + ".json")
        if os.path.exists(out):
            os.remove(out)
        args = [sys.executable, os.path.join(HERE, test), "--out", out]
        if test == "view_2d_stress.py" and "--sweep" in sys.argv:
            args.append("--sweep")
        print(f"== {test}", flush=True)
        start = time.perf_counter()
        code = subprocess.run(args, cwd=HERE).returncode
        took = time.perf_counter() - start
        try:
            with open(out, encoding="utf-8") as f:
                result = json.load(f)
        except (OSError, ValueError):
            result = {"passed": 0, "failed": 1}
        p, fl = result.get("passed", 0), result.get("failed", 0) or (1 if code else 0)
        passed += p
        failed += fl
        rows.append((test, p, fl, code, took))
    print("\n== summary", flush=True)
    for test, p, fl, code, took in rows:
        print(f"  {test:22} {p:3} passed {fl:3} failed  exit {code}  {took:5.1f} s", flush=True)
    print(f"  total: {passed} passed, {failed} failed (results in {out_dir})", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
