"""Shared bits for the tuff_view tests: find the engine, stop a stuck test, count checks, report numbers.

Each test opens a real window, runs by itself, prints its checks and numbers, and exits 0 when every
check passed. `--out file.json` also writes the result as JSON (a test frozen with --windowed has no
console, so that's how it reports).
"""
import json
import os
import statistics
import sys
import threading

if getattr(sys, "frozen", False):
    REPO = sys._MEIPASS
else:
    REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, REPO)

if sys.stdout is None:  # frozen with --windowed
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import tuff_view  # noqa: E402


def arg(name, default=None):
    """The value after --name on the command line."""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def watchdog(seconds, name):
    """End the process if the test hangs, so a broken bridge fails the run instead of blocking it."""
    def fire():
        print(f"FAIL {name}: still running after {seconds} s, stopping it", flush=True)
        write_out({"test": name, "passed": 0, "failed": 1, "timeout": True})
        os._exit(3)

    t = threading.Timer(seconds, fire)
    t.daemon = True
    t.start()


def spread(values):
    """Median, 95th percentile and worst of a list of numbers (milliseconds, usually)."""
    if not values:
        return {"n": 0}
    xs = sorted(values)
    return {"n": len(xs), "median": round(statistics.median(xs), 3), "p95": round(xs[min(len(xs) - 1, int(len(xs) * 0.95))], 3),
            "max": round(xs[-1], 3), "mean": round(sum(xs) / len(xs), 3)}


class Checks:
    def __init__(self, name):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.failures = []

    def check(self, ok, what):
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(what)
        print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
        return ok


def write_out(result):
    out = arg("--out")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)


def finish(checks, numbers):
    """Print the summary and the numbers; returns the exit code."""
    result = {"test": checks.name, "passed": checks.passed, "failed": checks.failed, "failures": checks.failures,
              "numbers": numbers}
    print(f"{checks.name}: {checks.passed} passed, {checks.failed} failed", flush=True)
    print("NUMBERS " + json.dumps(numbers), flush=True)
    write_out(result)
    return 0 if checks.failed == 0 else 1
