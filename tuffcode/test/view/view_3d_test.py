"""(c) 3D: a three.js scene with 200 cubes, a first-person camera moved from Python, and raycast clicks.

Pygame style at 60 fps. Python walks the camera through a field of 200 cubes (a grid of 20 x 10, each
one spinning, so 200 updates plus the camera every frame) with a sun, shadows and fog. Then the camera
looks straight down at the grid and the page clicks the screen position of 20 random cubes: the page
raycasts each click, and Python checks the click event names the right cube. Last, the camera turns to
face single cubes and asks for a crosshair pick (the middle of the view), as a first-person game would.

    py -3 tuffcode/test/view/view_3d_test.py [--seconds 8] [--out result.json]
"""
import math
import random
import sys
import time

from harness import Checks, arg, finish, spread, tuff_view, watchdog

W, H = 1280, 720
CLICK = """
const el = tv.node(%d).el;
const r = el.getBoundingClientRect();
el.dispatchEvent(new MouseEvent('click', { clientX: r.left + %f, clientY: r.top + %f, bubbles: true }));
"""


def main():
    checks = Checks("3d")
    seconds = float(arg("--seconds", 8))
    view = tuff_view.View("Tuff view: 3D (200 cubes)", W, H, on_top=True)
    t0 = time.perf_counter()
    scene = view.scene(bg="#9cc9ee", fog=["#9cc9ee", 20, 70], fov=70, shadows=True, cx=0, cy=1.7, cz=12)
    view.obj(scene, "hemi", intensity=1.2)
    view.obj(scene, "sun", x=12, y=20, z=8, intensity=2.2, shadow=True, area=30)
    view.obj(scene, "plane", w=120, h=120, rx=-90, color="#5b8c4a", shadow=True)
    rng = random.Random(3)
    cubes = []
    for i in range(200):
        gx, gz = i % 20, i // 20
        x, z = (gx - 9.5) * 2.5, (gz - 4.5) * 2.5 - 4
        cube = view.obj(scene, "box", x=x, y=0.6, z=z, w=1.2, h=1.2, d=1.2, color=f"hsl({rng.randrange(360)},60%,55%)",
                        shadow=True)
        cubes.append((cube, x, z))
    first = view.ask(scene, "pick")  # waits until three.js has loaded and the scene exists
    build_s = time.perf_counter() - t0
    view.page_stats(reset=True)
    time.sleep(1)
    display_fps = view.page_stats(reset=True)["fps"]

    # Walk: a loop around the field, looking where it goes, with a little head bob; every cube spins.
    view.fps = 60
    work, gaps = [], []
    start_stats = dict(view.stats)
    start = last = time.perf_counter()
    view.frame()
    while time.perf_counter() - start < seconds:
        a = time.perf_counter()
        t = a - start
        ang = t * 0.5
        cx, cz = math.sin(ang) * 16, math.cos(ang) * 16 - 4
        yaw = math.degrees(ang) - 90  # facing along the walk (yaw 0 looks down -z, yaw 90 down -x)
        view.set(scene, cx=cx, cy=1.7 + math.sin(t * 8) * 0.05, cz=cz, yaw=yaw, pitch=-8 + math.sin(t * 0.7) * 4)
        for i, (cube, x, z) in enumerate(cubes):
            view.set(cube, ry=(t * 60 + i * 7) % 360, y=0.6 + 0.15 * math.sin(t * 3 + i))
        b = time.perf_counter()
        view.frame()
        c = time.perf_counter()
        work.append((b - a) * 1000)
        gaps.append((c - last) * 1000)
        last = c
    elapsed = time.perf_counter() - start
    page = view.page_stats(reset=True)
    st = {k: view.stats[k] - start_stats[k] for k in ("flushes", "bytes", "flush_ms", "sends", "send_ms")}
    flush_ms = st["flush_ms"] / max(1, st["flushes"])
    walk = {
        "cubes": len(cubes), "seconds": round(elapsed, 2), "python_fps": round(len(work) / elapsed, 1),
        "python_frame_ms": spread([w + flush_ms for w in work]), "python_flush_ms_per_frame": round(flush_ms, 3),
        "frame_gap_ms": spread(gaps), "bridge_send_ms_per_batch": round(st["send_ms"] / max(1, st["sends"]), 3),
        "bytes_per_batch": round(st["bytes"] / max(1, st["flushes"])),
        "page_fps": round(page["fps"], 1), "page_batches_per_s": round(page["batches"] / page["seconds"], 1),
        "page_gap_ms": {"median": round(page["gap_median_ms"], 2), "p95": round(page["gap_p95_ms"], 2),
                        "p99": round(page["gap_p99_ms"], 2), "max": round(page["gap_max_ms"], 2)},
        "page_apply_ms_per_batch": round(page["apply_ms_per_batch"], 3),
        "page_draw_ms_per_frame": round(page["draw_ms_per_frame"], 3),
    }
    print(f"  walk: {walk}", flush=True)

    # Clicks: look straight down from above the field, stop the spinning, click 20 cubes on screen.
    for cube, x, z in cubes:
        view.set(cube, ry=0, y=0.6)
    view.set(scene, cx=0, cy=40, cz=-4, yaw=0, pitch=-90)
    view.frame()
    clicked = []
    view.on("click", lambda e: clicked.append(e))
    picks = rng.sample(range(200), 20)
    want = []
    for i in picks:
        cube, x, z = cubes[i]
        sx, sy = view.ask(scene, "project", x, 1.2, z)
        want.append(int(cube))
        view.js(CLICK % (scene, sx, sy))
        view.frame()
    deadline = time.perf_counter() + 2
    while len(clicked) < len(want) and time.perf_counter() < deadline:
        view.frame()
    got = [e.get("id") for e in clicked]

    # Crosshair: stand at the edge of the field, face a cube, pick the middle of the view.
    cross_ok = 0
    pick_ms = []
    for i in rng.sample(range(180, 200), 10):
        cube, x, z = cubes[i]
        view.set(scene, cx=x, cy=1.7, cz=z + 3.2, look=[x, 0.6, z])
        a = time.perf_counter()
        hit = view.ask(scene, "pick")
        pick_ms.append((time.perf_counter() - a) * 1000)
        cross_ok += hit and hit.get("id") == int(cube)
    view.close()

    checks.check(first is not None and "id" in first, "three.js loaded and the scene answers a pick")
    checks.check(display_fps > 50, f"the page draws the 3D scene at the display's rate ({display_fps:.0f} fps)")
    checks.check(walk["python_fps"] >= 58, f"Python holds 60 fps moving the camera and 200 cubes ({walk['python_fps']})")
    checks.check(walk["page_batches_per_s"] >= 58, f"the page applies ~60 batches a second ({walk['page_batches_per_s']})")
    checks.check(walk["page_fps"] >= display_fps * 0.95, f"the page keeps drawing at the display's rate ({walk['page_fps']} of {display_fps:.0f})")
    checks.check(walk["python_frame_ms"]["p95"] < 16.7 / 2, f"Python's work per frame stays under half a frame (p95 {walk['python_frame_ms']['p95']} ms)")
    checks.check(got == want, f"20 raycast clicks each named the cube under them ({sum(g == w for g, w in zip(got, want))}/20)")
    checks.check(all(e.get("point") and abs(e["point"][1] - 1.2) < 0.01 for e in clicked), "each click carries the 3D point it hit (top face, y = 1.2)")
    checks.check(cross_ok == 10, f"crosshair picks found the cube in front of the camera ({cross_ok}/10)")
    numbers = {"build_seconds": round(build_s, 3), "display_fps": round(display_fps, 1), "walk_60": walk,
               "click_hits": f"{sum(g == w for g, w in zip(got, want))}/20", "crosshair_pick_ms": spread(pick_ms)}
    return finish(checks, numbers)


if __name__ == "__main__":
    watchdog(90, "3d")
    sys.exit(tuff_view.run(main))
