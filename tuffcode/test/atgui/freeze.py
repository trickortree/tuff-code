"""Packaging proof for atgui: the IDE's runtime and a Build-exe app, frozen with PyInstaller, then run.

    py -3 tuffcode/test/atgui/freeze.py [--work folder] [--keep]

1. The runtime, as `npm run build:runtime` makes it (--onedir --console), runs programs/selftest.tuf: the
   program tests itself in a real window and closes, so its output can be checked.
2. An app, as Build exe makes it (build.js: --onefile --windowed, a launcher, program.tuf packed in), from
   programs/selftest.tuf too: it must open its window, close itself and exit 0.

atgui sits on tuff_view, which ships with every atgui or tgame program. That part is shared with tgame, so
it isn't in package.json or build.js on this branch; the flags it needs are TUFF_VIEW below, and they are
what the coordinator adds once (see the branch report). Builds in a temporary folder, never in the repo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SEP = ";" if os.name == "nt" else ":"
EXE = ".exe" if os.name == "nt" else ""
TUFF_VIEW = ["--hidden-import", "tuff_view", "--add-data", f"{os.path.join(REPO, 'tuff_view_web')}{SEP}tuff_view_web"]
SELFTEST = os.path.join(HERE, "programs", "selftest.tuf")
WANT = ["2", "Ada", "true", "C", '["B", "C"]', "[]", "Hello **there**", "more opened", "false", "true", "closed"]


def pyinstaller(args, what):
    start = time.perf_counter()
    p = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stdout[-3000:], p.stderr[-3000:], flush=True)
        raise SystemExit(f"building {what} failed")
    return time.perf_counter() - start


def main():
    work = sys.argv[sys.argv.index("--work") + 1] if "--work" in sys.argv else os.path.join(tempfile.gettempdir(), "tuff-atgui-freeze")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    results = {}
    passed = failed = 0

    def check(ok, what, got=None):
        nonlocal passed, failed
        passed += bool(ok)
        failed += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {what}" + ("" if ok or got is None else f"\n        got: {str(got)[:800]}"), flush=True)

    # 1. The runtime: package.json's build:runtime flags (with this branch's --hidden-import tuff_atgui), plus tuff_view's.
    rt_s = pyinstaller(["--onedir", "--console", "--name", "tuff-runtime", "--paths", REPO, "--hidden-import", "tuff_tgui",
                        "--hidden-import", "tuff_tap", "--hidden-import", "tuff_atgui", "--hidden-import", "ssl",
                        "--hidden-import", "certifi", *TUFF_VIEW, "--distpath", os.path.join(work, "runtime"),
                        "--workpath", os.path.join(work, "rt-work"), "--specpath", work, os.path.join(REPO, "tuff.py")], "the runtime")
    runtime = os.path.join(work, "runtime", "tuff-runtime", "tuff-runtime" + EXE)
    start = time.perf_counter()
    p = subprocess.run([runtime, SELFTEST], capture_output=True, text=True, encoding="utf-8", timeout=90, stdin=subprocess.DEVNULL,
                       env={**os.environ, "TUFF_IDE": ""})
    out = [x for x in p.stdout.replace("\r\n", "\n").split("\n") if x.strip() and not x.startswith("Press Enter")]
    check(p.returncode == 0 and out == WANT, f"the runtime runs an atgui program in a real window ({time.perf_counter() - start:.1f} s)",
          (p.returncode, out, p.stderr[-800:]))
    results["runtime_build_s"] = round(rt_s, 1)

    # 2. A Build-exe app: build.js's launcher and flags for a program that says "mention atgui", plus tuff_view's.
    app = os.path.join(work, "app")
    os.makedirs(app)
    for f in ("tuff.py", "tuff_tgui.py", "tuff_tap.py", "tuff_atgui.py", "tuff_view.py"):
        shutil.copy(os.path.join(REPO, f), app)
    shutil.copy(SELFTEST, os.path.join(app, "program.tuf"))
    launcher = os.path.join(app, "tuff_app.py")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write("import os, sys\nbase = getattr(sys, \"_MEIPASS\", os.path.dirname(os.path.abspath(__file__)))\nimport tuff\n"
                "sys.argv = [sys.argv[0], os.path.join(base, \"program.tuf\")]\nsys.exit(tuff.main())\n")
    exe_s = pyinstaller(["--onefile", "--windowed", "--name", "AtguiApp", "--distpath", os.path.join(work, "dist"),
                         "--workpath", os.path.join(app, "work"), "--specpath", app,
                         "--add-data", f"{os.path.join(app, 'program.tuf')}{SEP}.", "--exclude-module", "tkinter",
                         "--exclude-module", "tuff_tgui", "--exclude-module", "tuff_tap", "--hidden-import", "tuff_atgui",
                         *TUFF_VIEW, launcher], "the app")
    exe = os.path.join(work, "dist", "AtguiApp" + EXE)
    start = time.perf_counter()
    code = subprocess.run([exe], timeout=90).returncode
    run_s = time.perf_counter() - start
    check(code == 0 and run_s < 30, f"the built app opens its window, tests itself, closes and exits 0 ({run_s:.1f} s)", code)
    results.update({"app_build_s": round(exe_s, 1), "app_run_s": round(run_s, 1), "app_mb": round(os.path.getsize(exe) / 2**20, 2)})
    print("FREEZE " + json.dumps(results), flush=True)
    print(f"atgui freeze: {passed} passed, {failed} failed", flush=True)
    if "--keep" not in sys.argv:
        shutil.rmtree(work, ignore_errors=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
