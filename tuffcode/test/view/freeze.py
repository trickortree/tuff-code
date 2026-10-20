"""Packaging proof: freeze the 3D test with PyInstaller (--onefile --windowed), run the .exe, check it passes.

Also freezes an empty windowed program the same way, so the size pywebview and tuff_view_web add can
be read off. Builds in a temporary folder, never in the repo.

    py -3 tuffcode/test/view/freeze.py [--work folder] [--keep]
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
# What PyInstaller can't see by itself. pywebview ships its own hook (webview/__pyinstaller: its DLLs and
# JS), and pyinstaller-hooks-contrib covers pythonnet and clr_loader, so nothing is needed today; this
# list is where a missing one would go.
HIDDEN_IMPORTS = []


def build(work, name, script, extra):
    args = [sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noconfirm", "--clean",
            "--log-level", "WARN", "--name", name, "--distpath", os.path.join(work, "dist"),
            "--workpath", os.path.join(work, "build"), "--specpath", work, *extra, script]
    for h in HIDDEN_IMPORTS:
        args[-1:-1] = ["--hidden-import", h]
    start = time.perf_counter()
    p = subprocess.run(args, capture_output=True, text=True)
    exe = os.path.join(work, "dist", name + (".exe" if os.name == "nt" else ""))
    if p.returncode != 0 or not os.path.exists(exe):
        print(p.stdout[-3000:], p.stderr[-3000:], flush=True)
        raise SystemExit(f"building {name} failed")
    return exe, time.perf_counter() - start


def main():
    work = sys.argv[sys.argv.index("--work") + 1] if "--work" in sys.argv else os.path.join(tempfile.gettempdir(), "tuff-view-freeze")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    empty = os.path.join(work, "empty.py")
    with open(empty, "w", encoding="utf-8") as f:
        f.write("import sys\nsys.exit(0)\n")
    base_exe, base_s = build(work, "empty", empty, [])
    exe, build_s = build(work, "tuff_view_3d", os.path.join(HERE, "view_3d_test.py"),
                         ["--paths", REPO, "--paths", HERE, "--add-data", f"{os.path.join(REPO, 'tuff_view_web')}{SEP}tuff_view_web"])
    out = os.path.join(work, "result.json")
    start = time.perf_counter()
    code = subprocess.run([exe, "--seconds", "4", "--out", out], timeout=180).returncode
    run_s = time.perf_counter() - start
    with open(out, encoding="utf-8") as f:
        result = json.load(f)
    size, base = os.path.getsize(exe), os.path.getsize(base_exe)
    summary = {"exe": exe, "exe_mb": round(size / 2**20, 2), "empty_exe_mb": round(base / 2**20, 2),
               "added_mb": round((size - base) / 2**20, 2), "build_seconds": round(build_s, 1),
               "run_seconds": round(run_s, 1), "exit": code, "passed": result["passed"], "failed": result["failed"],
               "hidden_imports": HIDDEN_IMPORTS, "numbers": result.get("numbers")}
    print("FREEZE " + json.dumps(summary, indent=2), flush=True)
    ok = code == 0 and result["failed"] == 0
    print(f"frozen 3D test: {'passed' if ok else 'FAILED'} ({result['passed']} checks passed, {result['failed']} failed); "
          f"{summary['exe_mb']} MB, {summary['added_mb']} MB more than an empty windowed program", flush=True)
    if "--keep" not in sys.argv:
        shutil.rmtree(os.path.join(work, "build"), ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
