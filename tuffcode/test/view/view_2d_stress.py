"""(b) 2D stress: 300 moving sprites, with Python moving every one of them every frame.

Pygame style: the program calls frame() in a loop at 60 fps. 100 rectangles, 100 circles and 100
rotating images (the Tuff icon, loaded from the assets folder) bounce around a canvas that fills the
window. Measures the frame rate Python reaches, Python's own time per frame (moving the sprites plus
sending the batch), how many batches the page applies per second, and the page's own drawing rate.
Then runs the same scene unpaced (fps=0) to see how far the bridge can go, and with --sweep tries
more sprites.

    py -3 tuffcode/test/view/view_2d_stress.py [--seconds 10] [--sweep] [--out result.json]
"""
import math
import random
import sys
import time

from harness import Checks, arg, finish, spread, tuff_view, watchdog

W, H = 1280, 720


def make_sprites(view, canvas, count):
    rng = random.Random(7)
    icon = view.url("icon.png")
    sprites = []
    for i in range(count):
        kind = ("rect", "circle", "image")[i % 3]
        props = {"x": rng.uniform(40, W - 40), "y": rng.uniform(40, H - 40), "z": i % 5}
        if kind == "rect":
            props.update(w=rng.uniform(10, 30), h=rng.uniform(10, 30), color=f"hsl({rng.randrange(360)},70%,60%)", radius=3)
        elif kind == "circle":
            props.update(r=rng.uniform(5, 14), color=f"hsl({rng.randrange(360)},80%,65%)")
        else:
            props.update(src=icon, w=24, h=24)
        node = view.shape(canvas, kind, **props)
        speed = rng.uniform(60, 220)
        angle = rng.uniform(0, math.tau)
        sprites.append([node, props["x"], props["y"], math.cos(angle) * speed, math.sin(angle) * speed, kind == "image"])
    return sprites


def move(view, sprites, dt, t):
    """Bounce every sprite off the edges and send its new position (images also spin)."""
    w, h = view.size
    for s in sprites:
        node, x, y, vx, vy, spin = s
        x += vx * dt
        y += vy * dt
        if x < 0 or x > w:
            vx = -vx
            x = min(max(x, 0), w)
        if y < 0 or y > h:
            vy = -vy
            y = min(max(y, 0), h)
        s[1], s[2], s[3], s[4] = x, y, vx, vy
        if spin:
            view.set(node, x=x, y=y, rot=(t * 90) % 360)
        else:
            view.set(node, x=x, y=y)


def run_phase(view, sprites, seconds, fps):
    """Run the loop for a while; returns Python's frame times, work times and the page's numbers."""
    view.fps = fps
    view.page_stats(reset=True)
    start_stats = dict(view.stats)
    work = []
    gaps = []
    start = time.perf_counter()
    last = start
    view.frame()
    while time.perf_counter() - start < seconds:
        t0 = time.perf_counter()
        move(view, sprites, min(0.05, t0 - last), t0 - start)
        t1 = time.perf_counter()
        view.frame()
        t2 = time.perf_counter()
        work.append((t1 - t0) * 1000)
        gaps.append((t2 - last) * 1000)
        last = t2
    elapsed = time.perf_counter() - start
    page = view.page_stats(reset=True)
    st = {k: view.stats[k] - start_stats[k] for k in ("frames", "flushes", "bytes", "flush_ms", "sends", "send_ms")}
    flush_ms = st["flush_ms"] / max(1, st["flushes"])
    return {
        "sprites": len(sprites), "target_fps": fps, "seconds": round(elapsed, 2),
        "python_fps": round(len(work) / elapsed, 1),
        "python_frame_ms": spread([w + flush_ms for w in work]),
        "python_move_ms": spread(work),
        "python_flush_ms_per_frame": round(flush_ms, 3),
        "frame_gap_ms": spread(gaps),
        "bridge_send_ms_per_batch": round(st["send_ms"] / max(1, st["sends"]), 3),
        "bytes_per_batch": round(st["bytes"] / max(1, st["flushes"])),
        "page_fps": round(page["fps"], 1),
        "page_batches_per_s": round(page["batches"] / page["seconds"], 1),
        "page_gap_ms": {"median": round(page["gap_median_ms"], 2), "p95": round(page["gap_p95_ms"], 2),
                        "p99": round(page["gap_p99_ms"], 2), "max": round(page["gap_max_ms"], 2)},
        "page_apply_ms_per_batch": round(page["apply_ms_per_batch"], 3),
        "page_draw_ms_per_frame": round(page["draw_ms_per_frame"], 3),
    }


PIXEL_JS = """requestAnimationFrame(() => requestAnimationFrame(() => {
  const c = tv.node(%d).el, f = Math.min(c.width / 200, c.height / 100);
  const x = Math.round((c.width - 200 * f) / 2 + 150 * f), y = Math.round((c.height - 100 * f) / 2 + 50 * f);
  tv.emit('pixel', { rgb: [...c.getContext('2d').getImageData(x, y, 1, 1).data].slice(0, 3) });
}));"""


def edge_cases(view, checks):
    """A circle with a negative radius mustn't stop the shapes after it from drawing, and shapes made and
    removed all the time mustn't pile up in the engine's bookkeeping."""
    errors = []
    view.on("error", lambda e: errors.append(e.get("message")))
    top = view.canvas(bg="#000000", fit=[200, 100])
    view.shape(top, "circle", x=50, y=50, r=-5, color="#ff0000")  # a ball that shrank below 0
    view.shape(top, "rect", x=150, y=50, w=40, h=40, color="#00ff00")  # drawn after it
    probe = {}
    view.on("pixel", lambda e: probe.update(e))
    for _ in range(5):
        view.frame()
    view.js(PIXEL_JS % int(top))
    deadline = time.perf_counter() + 3
    while "rgb" not in probe and time.perf_counter() < deadline:
        view.frame()
    checks.check(probe.get("rgb") == [0, 255, 0] and not errors,
                 f"a circle with a negative radius draws nothing, and the box after it is still drawn ({probe.get('rgb')}, errors {errors})")
    kids = lambda: sum(len(k) for k in view._kids.values())  # noqa: E731
    before = (kids(), len(view._parents))
    for _ in range(20):
        made = [view.shape(top, "rect", x=10, y=10, w=2, h=2) for _ in range(50)]
        view.frame()
        for n in made:
            n.remove()
    view.frame()
    after = (kids(), len(view._parents))
    checks.check(after == before, f"1,000 shapes made and removed leave nothing behind in Python (ids kept: {before} -> {after})")
    top.remove()


def main():
    checks = Checks("2d")
    seconds = float(arg("--seconds", 10))
    view = tuff_view.View("Tuff view: 2D stress (300 sprites)", W, H, assets=tuff_view.WEB_DIR, on_top=True)
    canvas = view.canvas(bg="#0b0e14")
    hud = view.el("div", style={"position": "absolute", "left": "10px", "top": "8px", "color": "#eef1f7",
                                "font": "13px Segoe UI, sans-serif", "pointer-events": "none"})
    view.frame()
    idle = view.page_stats(reset=True)
    time.sleep(1)
    display_fps = view.page_stats(reset=True)["fps"]
    sprites = make_sprites(view, canvas, 300)
    hud.set(text="300 sprites, moved by Python every frame")
    paced = run_phase(view, sprites, seconds, 60)
    print(f"  paced at 60: {paced}", flush=True)
    unpaced = run_phase(view, sprites, min(4.0, seconds), 0)
    print(f"  unpaced: {unpaced}", flush=True)
    sweep = []
    if "--sweep" in sys.argv:
        for count in (1000, 2000, 5000):
            more = make_sprites(view, canvas, count - len(sprites))
            hud.set(text=f"{count} sprites")
            res = run_phase(view, sprites + more, 4.0, 60)
            print(f"  {count} sprites at 60: {res}", flush=True)
            sweep.append(res)
            for s in more:
                s[0].remove()
    edge_cases(view, checks)
    view.close()

    checks.check(idle is not None and display_fps > 50, f"the page draws at the display's rate ({display_fps:.0f} fps)")
    checks.check(paced["python_fps"] >= 58, f"Python holds 60 fps with 300 sprites ({paced['python_fps']})")
    checks.check(paced["page_batches_per_s"] >= 58, f"the page applies ~60 batches a second ({paced['page_batches_per_s']})")
    checks.check(paced["page_fps"] >= display_fps * 0.95, f"the page keeps drawing at the display's rate ({paced['page_fps']} of {display_fps:.0f})")
    checks.check(paced["python_frame_ms"]["p95"] < 16.7 / 2, f"Python's work per frame stays under half a frame (p95 {paced['python_frame_ms']['p95']} ms)")
    checks.check(paced["frame_gap_ms"]["p95"] < 20, f"frames come every ~16.7 ms (p95 gap {paced['frame_gap_ms']['p95']} ms)")
    numbers = {"display_fps": round(display_fps, 1), "paced_60": paced, "unpaced": unpaced, "sweep": sweep}
    return finish(checks, numbers)


if __name__ == "__main__":
    watchdog(240 if "--sweep" in sys.argv else 90, "2d")
    sys.exit(tuff_view.run(main))
