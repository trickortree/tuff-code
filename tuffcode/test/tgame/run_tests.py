"""tgame's tests: real .tuf games in real windows. Each game plays itself with tgame's autopilot (keys, clicks
and mouse movement made in the page, so they travel the way real ones do), takes screenshots, writes what it
sees to JSON, and closes. The checks read the program's output, those JSON files and the screenshots.

    py -3 tuffcode/test/tgame/run_tests.py [test ...] [--out-dir folder] [--runtime path/to/tuff-runtime.exe]

--runtime runs the games with a frozen Tuff runtime instead of Python + tuff.py. Screenshots and results go to
--out-dir (default: tuffcode/test/tgame/out). Don't cover the windows while the tests run: a covered page stops
drawing. Uses Pillow to read screenshots when it's installed, or a slower built-in PNG reader.
"""
import base64
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAMES = os.path.join(HERE, "games")
TUFF = os.path.join(REPO, "tuff.py")
NOTICE = "Tuff Engine is here: open this game in TuffCode's Tuff Engine tab (Ctrl+Shift+G) to build it visually."
sys.path.insert(0, REPO)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else default


OUT = os.path.abspath(arg("--out-dir", os.path.join(HERE, "out")))
RUNTIME = os.path.abspath(arg("--runtime")) if arg("--runtime") else None
# The games' windows open out of sight, never take the focus and make no sound (tuff_view's _quiet_window), so the
# tests can run while someone uses the computer. TUFF_TEST_QUIET=0 shows them.
os.environ.setdefault("TUFF_TEST_QUIET", "1")


class Checks:
    def __init__(self):
        self.passed = self.failed = 0
        self.failures = []

    def check(self, ok, what, got=None):
        ok = bool(ok)
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(what)
        print(f"  {'ok  ' if ok else 'FAIL'} {what}" + ("" if ok or got is None else f"\n         got: {str(got)[:600]}"), flush=True)
        return ok


class Played:
    """What a run left behind: exit code, output lines, errors, the JSON dumps and the screenshots."""

    def __init__(self, code, out, err, dumps, shots, seconds):
        self.code, self.out, self.err, self.dumps, self.shots, self.seconds = code, out, err, dumps, shots, seconds
        # A frozen runtime (not the IDE, not windowed) ends with this, waiting for Enter; its input is empty here.
        self.lines = [line for line in out.splitlines() if line.strip() and line.strip() != "Press Enter to close..."]


def tuff_cmd():
    return [RUNTIME] if RUNTIME else [sys.executable, TUFF]


def play(name, program, steps, timeout=60, seed=1, env=None, hold_mouse=False):
    """Run a game with a list of autopilot steps; returns Played. hold_mouse: tuff_view holds the real mouse when
    the game locks it (the tests leave it alone otherwise)."""
    os.makedirs(OUT, exist_ok=True)
    plan = {"on_top": True, "out": OUT, "seed": seed, "steps": steps, "hold_mouse": hold_mouse,
            "timeout": max([s.get("at", 0) for s in steps] + [0]) + 15}
    plan_file = os.path.join(OUT, f"{name}.plan.json")
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    for s in steps:
        for key in ("dump", "shot"):
            if key in s and os.path.exists(os.path.join(OUT, s[key])):
                os.remove(os.path.join(OUT, s[key]))
    full_env = {**os.environ, "TUFF_TGAME_AUTOPILOT": plan_file, "PYTHONIOENCODING": "utf-8", **(env or {})}
    if hold_mouse and os.environ.get("TUFF_TEST_REAL_MOUSE") == "1":
        full_env["TUFF_TEST_QUIET"] = "0"  # it holds the real mouse: a window in front, for real
    full_env.pop("TUFF_IDE", None)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(tuff_cmd() + [program], cwd=os.path.dirname(program), env=full_env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        code, out, err = "timeout", (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "timed out"
    secs = time.perf_counter() - t0
    dumps, shots = {}, {}
    for s in steps:
        if "dump" in s:
            try:
                with open(os.path.join(OUT, s["dump"]), encoding="utf-8") as f:
                    dumps[s["dump"]] = json.load(f)
            except (OSError, ValueError):
                dumps[s["dump"]] = {}
        if "shot" in s and os.path.exists(os.path.join(OUT, s["shot"])):
            shots[s["shot"]] = os.path.join(OUT, s["shot"])
    return Played(code, out, err, dumps, shots, secs)


# ---------------------------------------------------------------- reading screenshots

def png_rgb(path):
    """(width, height, get(x, y) -> (r, g, b)) for a PNG."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        px = img.load()
        return img.width, img.height, lambda x, y: px[x, y]
    except ImportError:
        pass
    data = open(path, "rb").read()
    pos, idat = 8, b""
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            w, h, _depth, ctype = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
    raw = zlib.decompress(idat)
    bpp = 4 if ctype == 6 else 3
    stride = w * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, lambda x, y: tuple(rows[y][x * bpp:x * bpp + 3])


def color_share(path, rgb, tol=40, box=None, step=3):
    """The share of pixels (0..1) within `tol` of a color, in box=(x0, y0, x1, y1) as fractions of the picture."""
    try:
        w, h, get = png_rgb(path)
    except Exception:
        return 0.0
    x0, y0, x1, y1 = box or (0, 0, 1, 1)
    hits = total = 0
    for y in range(int(y0 * h), int(y1 * h), step):
        for x in range(int(x0 * w), int(x1 * w), step):
            p = get(x, y)
            total += 1
            if all(abs(p[k] - rgb[k]) <= tol for k in range(3)):
                hits += 1
    return hits / max(1, total)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def first_line_is_notice(c, r):
    c.check(r.lines[:1] == [NOTICE], "the first line is the Tuff Engine notice (plain text, the output is a pipe)", r.lines[:2])


def clean_exit(c, r):
    c.check(r.code == 0, f"it ran and closed by itself (exit {r.code}, {r.seconds:.1f} s)", r.err[-800:])
    c.check("Tuff error" not in r.err and "Traceback" not in r.err, "no errors", r.err[-800:])


def game(name):
    return os.path.join(GAMES, name)


# ---------------------------------------------------------------- the games

def t_snake(c):
    r = play("snake", game("snake.tuf"), [
        {"at": 0.25, "tuff": "food:move_to(250, 210)"},
        {"at": 0.8, "dump": "snake_eat.json"},
        {"at": 0.82, "shot": "snake.png"},
        {"at": 0.85, "key": "down"},
        {"at": 1.3, "dump": "snake_down.json"},
        {"at": 2.6, "dump": "snake_over.json"},
        {"at": 2.65, "shot": "snake_over.png"},
        {"at": 2.7, "key": "space"},
        {"at": 2.95, "dump": "snake_again.json"},
        {"at": 3.0, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    eat, down, over, again = (r.dumps.get(k, {}) for k in ("snake_eat.json", "snake_down.json", "snake_over.json", "snake_again.json"))
    rects = lambda d: [s for s in d.get("sprites", []) if s[0] == "rect"]
    c.check("Score: 1" in eat.get("texts", []), "the snake ate the food in front of it: Score: 1", eat.get("texts"))
    c.check(len(rects(eat)) == 4, "it grew: 3 parts plus the food", rects(eat))
    head_x = rects(eat)[1][1] if len(rects(eat)) > 1 else None
    c.check(head_x is not None and head_x > 250, f"it kept moving right (head at x {head_x})", rects(eat))
    heads = [s for s in rects(down)[1:2]]
    c.check(heads and heads[0][2] > 210, "after the down arrow it moves down", rects(down))
    c.check(over.get("paused") and "Game over" in over.get("hud_texts", []) and "Score: 1" in over.get("hud_texts", []),
            "running into the bottom wall shows Game over with the score", over.get("hud_texts"))
    c.check(again.get("paused") is False and "Score: 0" in again.get("texts", []) and len(rects(again)) == 3,
            "space plays again: the score is 0 and the snake is short again", (again.get("paused"), again.get("texts"), rects(again)))
    c.check(eat.get("fps", 0) >= 55, f"it runs at 60 fps ({eat.get('fps')})", eat.get("fps"))
    shot = r.shots.get("snake.png")
    c.check(shot and color_share(shot, hexrgb("#14213d")) > 0.5, "the screenshot shows the dark blue board", shot)
    c.check(shot and color_share(shot, hexrgb("#e2a508"), 30) > 0.0005, "and the yellow head", shot)
    c.check(r.shots.get("snake_over.png") and color_share(r.shots["snake_over.png"], (255, 255, 255), 30, (0.3, 0.3, 0.7, 0.6)) > 0.005,
            "the game over screenshot shows the big white title", r.shots.get("snake_over.png"))


def t_breakout(c):
    r = play("breakout", game("breakout.tuf"), [
        {"at": 0.2, "hold": "left", "for": 0.3},
        {"at": 0.6, "dump": "breakout_left.json"},
        {"at": 1.6, "dump": "breakout_hit.json"},
        {"at": 1.65, "shot": "breakout.png"},
        {"at": 1.7, "tuff": "lives = 1"},
        {"at": 1.72, "tuff": "ball:move_to(320, 495)"},
        {"at": 2.0, "dump": "breakout_over.json"},
        {"at": 2.05, "shot": "breakout_over.png"},
        {"at": 2.1, "key": "space"},
        {"at": 2.3, "dump": "breakout_again.json"},
        {"at": 2.4, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = r.dumps
    paddle = lambda k: next((s for s in d.get(k, {}).get("sprites", []) if s[0] == "rect" and s[2] == 450), None)
    p = paddle("breakout_left.json")
    c.check(p and p[1] < 300, f"holding left moves the paddle left (x {p and p[1]})", p)
    hit = d.get("breakout_hit.json", {})
    texts = " ".join(hit.get("texts", []))
    c.check("Score: " in texts and "Score: 0 " not in texts, "the ball broke a brick: the score went up", texts)
    bricks = len([s for s in hit.get("sprites", []) if s[0] == "rect" and s[2] < 200])
    c.check(bricks < 40, f"a brick is gone ({bricks} of 40 left)", bricks)
    over = d.get("breakout_over.json", {})
    c.check(over.get("paused") and "Game over" in over.get("hud_texts", []), "losing the last ball shows Game over", over.get("hud_texts"))
    again = d.get("breakout_again.json", {})
    left = len([s for s in again.get("sprites", []) if s[0] == "rect" and s[2] < 200])
    c.check(not again.get("paused") and left == 40, f"space starts again with all 40 bricks ({left})", (again.get("paused"), left))
    shot = r.shots.get("breakout.png")
    c.check(shot and color_share(shot, hexrgb("#e5484d"), 30, (0, 0, 1, 0.3)) > 0.01, "the screenshot shows the red bricks", shot)


def t_snake3d(c):
    r = play("snake3d", game("snake3d.tuf"), [
        {"at": 0.2, "tuff": "apple:move_to(0, 0, 1)"},
        {"at": 0.75, "dump": "snake3d_eat.json"},
        {"at": 0.8, "key": "right"},
        {"at": 1.4, "dump": "snake3d_turn.json"},
        {"at": 1.45, "shot": "snake3d.png"},
        {"at": 3.6, "dump": "snake3d_over.json"},
        {"at": 3.65, "shot": "snake3d_over.png"},
        {"at": 3.7, "key": "space"},
        {"at": 3.9, "dump": "snake3d_again.json"},
        {"at": 4.0, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = r.dumps
    boxes = lambda k: [o for o in d.get(k, {}).get("objects", []) if o[0] == "box" and o[1:4] != [0, 0, -11]]
    eat = d.get("snake3d_eat.json", {})
    c.check("Apples: 1" in eat.get("hud_texts", []), "the snake ate the apple: Apples: 1", eat.get("hud_texts"))
    segs = [o for o in boxes("snake3d_eat.json") if abs(o[1]) < 10.5 and abs(o[3]) < 10.5]
    c.check(len(segs) == 3, f"and grew to 3 parts ({len(segs)})", segs)
    turn = [o for o in boxes("snake3d_turn.json") if abs(o[1]) < 10.5 and abs(o[3]) < 10.5]
    c.check(turn and turn[0][1] > 0.5, "after the right arrow the head moves along +x", turn[:1])
    cam = d.get("snake3d_turn.json", {}).get("camera")
    c.check(cam and cam[0] < turn[0][1] if turn and cam else False, "the camera follows behind the head", (cam, turn[:1]))
    over = d.get("snake3d_over.json", {})
    c.check(over.get("paused") and "Game over" in over.get("hud_texts", []), "hitting the fence ends the game", over.get("hud_texts"))
    again = d.get("snake3d_again.json", {})
    c.check(not again.get("paused") and "Apples: 0" in again.get("hud_texts", []), "space plays again", again.get("hud_texts"))
    shot = r.shots.get("snake3d.png")
    c.check(shot and color_share(shot, (125, 140, 20), 50) > 0.002, "the screenshot shows the lime snake", shot)


def t_axe(c):
    r = play("axe_sim", game("axe_sim.tuf"), [
        {"at": 0.2, "lock": True},
        {"at": 0.3, "shot": "axe_sim_start.png"},
        {"at": 0.4, "hold": "w", "for": 0.5},
        {"at": 1.1, "dump": "axe_walk.json"},
        {"at": 1.2, "click_center": True},
        {"at": 1.45, "click_center": True},
        {"at": 1.55, "shot": "axe_sim_shake.png"},
        {"at": 1.7, "click_center": True},
        {"at": 2.0, "shot": "axe_sim_falling.png"},
        {"at": 3.3, "dump": "axe_fallen.json"},
        {"at": 3.35, "shot": "axe_sim_fallen.png"},
        {"at": 3.1, "click_center": True},
        {"at": 3.3, "look": [600, 0]},
        {"at": 3.5, "dump": "axe_look.json"},
        {"at": 3.55, "shot": "axe_sim_look.png"},
        {"at": 3.6, "look": [-600, 0]},
        {"at": 9.0, "dump": "axe_regrown.json"},
        {"at": 9.05, "shot": "axe_sim_regrown.png"},
        {"at": 9.2, "close": True},
    ], seed=7)
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = r.dumps
    walk = d.get("axe_walk.json", {})
    pl = walk.get("player") or [0, 0, 0]
    c.check(-3.2 < pl[2] < -2.0, f"holding W walks forward ({pl[2]:.2f} along z)", pl)
    fallen = d.get("axe_fallen.json", {})
    c.check("Logs: 1" in fallen.get("hud_texts", []), "three chops felled the pine in front: Logs: 1", fallen.get("hud_texts"))
    c.check(fallen.get("fallen") == 1, "the tree is lying on the ground", fallen.get("fallen"))
    pine = next((o for o in fallen.get("objects", []) if o[0] == "pine" and o[1:4] == [0, 0, -6]), None)
    c.check(pine and pine[4], "it's the pine at (0, 0, -6)", pine)
    c.check(fallen.get("labels") == ["Chop the trees!"], "its hit counter label went away (only the sign's is left)", fallen.get("labels"))
    look = d.get("axe_look.json", {})
    c.check(look.get("player") and 80 < look["player"][3] < 100, "moving the mouse turns the player (about 90 degrees)", look.get("player"))
    regrown = d.get("axe_regrown.json", {})
    c.check(regrown.get("fallen") == 0, "5 seconds later the tree has grown back", regrown.get("fallen"))
    c.check("Logs: 1" in regrown.get("hud_texts", []), "and the log count stayed (a click on the fallen tree did nothing)", regrown.get("hud_texts"))
    c.check(walk.get("fps", 0) >= 55, f"it runs at 60 fps ({walk.get('fps')})", walk.get("fps"))
    c.check(walk.get("sound", {}).get("context") in ("running", "none"), "sound isn't blocked", walk.get("sound"))
    start = r.shots.get("axe_sim_start.png")
    c.check(start and color_share(start, hexrgb("#5fa83f"), 45, (0, 0.6, 1, 1)) > 0.2, "the screenshot shows the grass", start)
    c.check(start and color_share(start, (120, 180, 235), 60, (0, 0, 1, 0.25)) > 0.3, "and the sky", start)


def t_features_2d(c):
    r = play("features_2d", game("features_2d.tuf"), [
        {"at": 0.3, "key": "a"}, {"at": 0.4, "key": "b"},
        {"at": 0.5, "click_world": [100, 100]},
        {"at": 0.6, "click_world": [600, 350]},
        {"at": 0.7, "key": "space"}, {"at": 0.8, "key": "space"},
        {"at": 0.9, "hold": "x", "for": 0.5},
        {"at": 1.6, "call": "report"},
        {"at": 1.65, "shot": "features_2d.png"},
        {"at": 1.7, "call": "pause_now"},
        {"at": 1.9, "shot": "features_2d_paused.png"},
        {"at": 1.95, "dump": "features_2d.json"},
        {"at": 2.0, "call": "resume_now"},
        {"at": 2.2, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    want = [
        "wide edge true false", "spot [300, 200]", "touch box ball true", "touch box dot false", "dot hits group true",
        "ball hits list true", "group moved 310 330 count 2", "hp 3 missing nil", "title Features!", "angle 90",
        "point 270", "forward [50, 290]", "distance 5", "grid 10 10", "kept 5", "wrapped 645",
        "say a sprite <box at 310, 200>", "clicked the star at [100, 100]", "clicks 2", "keys abspacespacex",
        "presses 2", "held for a while true", "ticks true", "after true", "glided [500, 300]", "ball moving true",
        "time true", "fps true", "width 640 height 400", "paused false", "paused true", "paused false",
    ]
    got = r.lines[1:]
    blurs = r.dumps.get("features_2d.json", {}).get("blurs")
    for line in want:
        c.check(line in got, f"says: {line}", ([g for g in got if g.split(" ")[0] == line.split(" ")[0]] or got[-5:], f"window lost focus {blurs} times"))
    shot = r.shots.get("features_2d.png")
    c.check(shot and color_share(shot, (250, 196, 40), 30) > 0.002, "the star pictures are drawn", shot)
    c.check(shot and color_share(shot, hexrgb("#14b8a6"), 30) > 0.002, "and the teal box", shot)
    paused = r.shots.get("features_2d_paused.png")
    c.check(paused and color_share(paused, hexrgb("#202830"), 12) < 0.2, "the pause screen darkens the game", paused)
    snd = r.dumps.get("features_2d.json", {}).get("sound", {})
    c.check(snd.get("context") == "running", "sound plays without a click first (the audio context is running)", snd)


def t_features_3d(c):
    r = play("features_3d", game("features_3d.tuf"), [
        {"at": 0.3, "shot": "features_3d.png"},
        {"at": 0.35, "call": "model_check"},
        {"at": 0.4, "call": "look"},
        {"at": 0.5, "click_center": True},
        {"at": 1.0, "call": "look"},
        {"at": 1.1, "call": "chop"},
        {"at": 2.4, "call": "check_fall"},
        {"at": 3.9, "call": "check_regrow"},
        {"at": 3.95, "dump": "f3d_fixed.json"},
        {"at": 4.0, "call": "orbit"},
        {"at": 4.1, "press_mouse": True},
        {"at": 4.2, "look": [200, 40]},
        {"at": 4.3, "look": [200, 0]},
        {"at": 4.4, "release_mouse": True},
        {"at": 4.6, "dump": "f3d_orbit.json"},
        {"at": 4.65, "shot": "features_3d_orbit.png"},
        {"at": 4.7, "call": "follow"},
        {"at": 5.6, "dump": "f3d_follow.json"},
        {"at": 5.7, "call": "other_sky"},
        {"at": 5.9, "shot": "features_3d_night.png"},
        {"at": 6.0, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    want = ["kit 11", "spot [0, 0, -4]", "touch red blue false", "touch red tall false", "touch red blue now true",
            "distance 5", "list hit true", "hp 5", "angle 180", "look 0", "look right 90",
            "say an object <box at 0, 0, -4>", "looking at red true", "far true", "clicked red 1 on its front true",
            "the model is 2 tall true false", "fallen true", "fallen now true", "regrown true", "hat spun true", "glided [2, 0, -6]", "hidden red false"]
    got = r.lines[1:]
    for line in want:
        c.check(line in got, f"says: {line}", [g for g in got if g.split(" ")[0] == line.split(" ")[0]] or got[-5:])
    fixed = r.dumps.get("f3d_fixed.json", {}).get("camera")
    orbit = r.dumps.get("f3d_orbit.json", {}).get("camera")
    follow = r.dumps.get("f3d_follow.json", {}).get("camera")
    c.check(fixed and fixed[:3] == [0, 2, 3], "camera_at put the camera at (0, 2, 3)", fixed)
    c.check(orbit and fixed and orbit[:3] != fixed[:3], "orbit: dragging the mouse swings the camera around the box", (fixed, orbit))
    c.check(follow and orbit and follow[:3] != orbit[:3], "follow: the camera moves behind the spinning cone", (orbit, follow))
    shot = r.shots.get("features_3d.png")
    c.check(shot and color_share(shot, (180, 33, 24), 40, (0.3, 0.3, 0.7, 0.8)) > 0.01, "the red box is in the middle of the view", shot)
    c.check(shot and color_share(shot, (170, 114, 22), 25, (0.2, 0.3, 0.4, 0.5)) > 0.01, "the .glb model is drawn (its yellow top)", shot)
    night = r.shots.get("features_3d_night.png")
    c.check(night and color_share(night, (20, 30, 60), 40, (0, 0, 1, 0.3)) > 0.3, "the night sky is dark", night)


def t_player_3d(c):
    r = play("player_3d", game("player_3d.tuf"), [
        {"at": 0.3, "hold": "w", "for": 1.0},
        {"at": 1.5, "call": "where"},
        {"at": 1.55, "dump": "player_blocked.json"},
        {"at": 1.6, "shot": "player_3d.png"},
        {"at": 1.7, "hold": "w", "for": 0.3},
        {"at": 1.75, "key": "space"},
        {"at": 2.6, "call": "where"},
        {"at": 2.65, "dump": "player_on_crate.json"},
        {"at": 2.7, "tuff": "player:move_to(3, 0, 1.6)"},
        {"at": 2.72, "tuff": "player:turn_to(0)"},
        {"at": 2.8, "hold": "w", "for": 0.5},
        {"at": 3.5, "hold": "d", "for": 0.7},
        {"at": 4.4, "call": "where"},
        {"at": 4.5, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    blocked = r.dumps.get("player_blocked.json", {}).get("player") or [0, 0, 0]
    c.check(-2.4 < blocked[2] < -2.0 and blocked[1] == 0, f"walking into the crate stops at it (z {blocked[2]})", blocked)
    top = r.dumps.get("player_on_crate.json", {}).get("player") or [0, 0, 0]
    c.check(abs(top[1] - 0.9) < 0.01 and top[2] < -2.5, f"a jump forward lands on top of the crate (y {top[1]})", top)
    c.check("got the coin" in r.lines, "walking into the coin picks it up", r.lines[-4:])
    where = [line for line in r.lines if line.startswith("player ")]
    c.check(len(where) == 3 and 80 < float(where[-1].split()[-1]) < 105, "holding D turns the player right (third person)", where)
    c.check(r.lines[-1] == "the window closed, coins 1", "the code after the loop runs once the window closes", r.lines[-1:])
    shot = r.shots.get("player_3d.png")
    c.check(shot and color_share(shot, (32, 58, 116), 30) > 0.001, "the screenshot shows the player's blue shirt", shot)


def t_callback(c):
    r = play("callback", game("callback.tuf"), [
        {"at": 0.3, "key": "space"}, {"at": 0.5, "key": "space"},
        {"at": 0.6, "hold": "right", "for": 0.5},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    c.check(r.lines[1:] == ["set up", "frames true, jumps 2, moved true"],
            "every_frame, on_key and after all ran, and game:close ended it", r.lines)


def t_errors(c):
    r = play("errors", game("errors.tuf"), [])
    first_line_is_notice(c, r)
    c.check(r.code == 0, f"an error in an every-frame function doesn't stop the game (exit {r.code})", r.err[-500:])
    c.check(r.err.count("Tuff error on line 10") == 1, "it's reported once, with its line", r.err[-500:])
    c.check(r.lines[1:] == ["item 2", "still running"], "then that function is switched off and the timer still runs", r.lines)
    r = play("top_error", game("top_error.tuf"), [])
    c.check(r.code == 1 and "Tuff error on line 11" in r.err, f"an error in the main loop stops the program (exit {r.code})", r.err[-500:])
    c.check(r.seconds < 15, f"and its window closes with it ({r.seconds:.1f} s)", r.seconds)


def t_churn(c):
    """A long 2D game: bullets made and removed all the time, and still moved after :remove; a ball shrunk below 0;
    text aligned left and right."""
    r = play("churn", game("churn.tuf"), [
        {"at": 0.3, "click_world": [150, 40]}, {"at": 0.4, "call": "clicks"},
        {"at": 0.5, "click_world": [5, 40]}, {"at": 0.6, "call": "clicks"},
        {"at": 0.7, "click_world": [340, 260]}, {"at": 0.8, "call": "clicks"},
        {"at": 0.9, "click_world": [395, 260]}, {"at": 1.0, "call": "clicks"},
        {"at": 1.5, "dump": "churn_a.json", "memory": True},
        {"at": 1.55, "shot": "churn.png"},
        {"at": 3.5, "call": "report"},
        {"at": 3.55, "dump": "churn_b.json", "memory": True},
        {"at": 3.6, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    c.check(r.lines[1:5] == ['hits ["Start the game"]', "hits []", 'hits ["Quit"]', "hits []"],
            "text aligned left or right is clicked where its words are drawn, not around x", r.lines[1:5])
    c.check("made true, shrunk true" in r.lines, "over 1,000 bullets made and removed, and the ball shrank below 0", r.lines[-3:])
    a, b = r.dumps.get("churn_a.json", {}), r.dumps.get("churn_b.json", {})
    c.check(b.get("kept", 1e9) < 250 and b.get("view_nodes", 1e9) < 260,
            f"after 2,000 bullets, tgame and the window only hold the live ones ({b.get('kept')} sprites, {b.get('view_nodes')} ids)",
            (b.get("kept"), b.get("view_nodes"), b.get("things")))
    c.check(a.get("in_memory", 1e9) < 400 and b.get("in_memory", 1e9) < 400,
            f"memory stays flat: {a.get('in_memory')} sprites in memory at 1.5 s, {b.get('in_memory')} at 3.5 s",
            (a.get("in_memory"), b.get("in_memory")))
    shot = r.shots.get("churn.png")
    c.check(shot and color_share(shot, hexrgb("#3574f0"), 30, (0.7, 0.42, 0.8, 0.58)) > 0.5,
            "the box made after the shrunk ball is still drawn", shot)
    c.check(shot and color_share(shot, hexrgb("#e5484d"), 30, (0.2, 0.43, 0.3, 0.57)) < 0.01, "and the ball is gone", shot)


def t_pause_key(c):
    r = play("pause_key", game("pause_key.tuf"), [
        {"at": 0.4, "key": "p"}, {"at": 0.7, "call": "report"},
        {"at": 0.9, "key": "p"}, {"at": 1.2, "call": "report"},
        {"at": 1.3, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    c.check(r.lines[1:] == ["paused true, ran while paused true", "paused false, ran while paused true"],
            "an every-frame function runs while paused, so its P key pauses and then resumes the game", r.lines)


def t_mouse_hold(c):
    """A first-person game holds the mouse itself, not with the browser's pointer lock (which shows "To show your
    cursor, press Esc" over the game): a click holds it (world:mouse_locked is true, the cursor is hidden), moving the
    mouse turns the player, and Escape lets go of it. With TUFF_TEST_REAL_MOUSE=1 it takes the real mouse for a second
    (kept inside the window and put back in the middle); without it, the real cursor is left alone and the page gets
    the moves."""
    if os.name != "nt":
        c.check(True, "not Windows: skipped (the Mac holds it with Quartz)")
        return
    real = os.environ.get("TUFF_TEST_REAL_MOUSE") == "1"  # it takes the real mouse for a second: only when asked
    r = play("mouse_hold", game("mouse_hold.tuf"), [
        {"at": 0.5, "front": real},
        {"at": 0.6, "js": "tv.emit('tg-autopilot', {message: 'focus ' + document.hasFocus()})"},
        {"at": 0.7, "click_center": True}, {"at": 0.9, "call": "report"}, {"at": 1.0, "hold_report": True},
        {"at": 1.05, "js": "tv.emit('tg-autopilot', {message: 'look ' + JSON.stringify({held: document.pointerLockElement"
                           " !== null, hidden: getComputedStyle(document.body).cursor, browser_lock: /native code/.test("
                           "Element.prototype.requestPointerLock)})})"},
        {"at": 1.1, "nudge_mouse": [120, 0]}, {"at": 1.3, "nudge_mouse": [120, 0]}, {"at": 1.5, "call": "report"},
        {"at": 1.55, "hold_report": True},
        {"at": 1.6, "key": "escape"}, {"at": 1.9, "call": "report"}, {"at": 2.0, "hold_report": True},
        {"at": 2.1, "nudge_mouse": [120, 0]}, {"at": 2.3, "call": "report"}, {"at": 2.35, "hold_report": True},
        {"at": 2.4, "close": True},
    ], hold_mouse=real)
    clean_exit(c, r)
    holds = [json.loads(line.split("hold ", 1)[1]) for line in r.lines if line.startswith("[autopilot] hold ")]
    said = [line for line in r.lines if line.startswith("locked ")]
    look = next((json.loads(line.split("look ", 1)[1]) for line in r.lines if line.startswith("[autopilot] look ")), {})
    print(f"         {autopilot_said(r, 'focus')} {holds} {said} {look}")
    if len(holds) < 4 or len(said) < 4:
        c.check(False, "the game reported how it holds the mouse", r.lines)
        return
    c.check(look == {"held": True, "hidden": "none", "browser_lock": False}, "a click on the game: the page acts as if the mouse were locked "
            "(no browser lock, so no banner), and hides the cursor", look)
    a0, a1, a2, a3 = (float(s.rsplit(" ", 1)[1]) for s in said[:4])
    if not real:
        moved = [[b["cursor"][0] - a["cursor"][0], b["cursor"][1] - a["cursor"][1]] for a, b in ((holds[0], holds[1]), (holds[2], holds[3]))]
        c.check(moved[0] != [240, 0] and moved[1] != [120, 0], "the real cursor is left alone (TUFF_TEST_REAL_MOUSE=1 moves it): "
                "the moves go to the page", moved)
        c.check(said[0].startswith("locked true") and holds[0]["page"] and not holds[0]["active"],
                "a click on the game holds the mouse: world:mouse_locked is true (the real one isn't taken)", [said[0], holds[0]])
        c.check(abs(a1 - a0) > 5, "moving the mouse turns the player", said[:2])
        c.check(said[2].startswith("locked false") and not holds[2]["page"], "Escape lets go of it", [said[2], holds[2]])
        c.check(abs(a3 - a2) < 0.5, "once it's let go, moving the mouse doesn't turn the player", [said[2], said[3]])
        return
    if not holds[0].get("front"):
        c.check(False, "the test window came in front, to take the real mouse", holds[0])
        return
    state = [{k: h.get(k) for k in ("page", "active", "front", "inside", "middle")} for h in holds]
    c.check(said[0].startswith("locked true") and state[0] == {"page": True, "active": True, "front": True, "inside": True, "middle": True},
            "a click on the game holds the mouse: world:mouse_locked is true, the cursor is kept inside the window, in its middle",
            [said[0], holds[0]])
    c.check(abs(a1 - a0) > 5 and holds[1].get("middle"), "moving the real mouse turns the player, and the cursor goes back to the middle",
            [said[0], said[1], holds[1]])
    c.check(said[2].startswith("locked false") and not holds[2]["page"] and not holds[2]["active"] and not holds[2]["inside"],
            "Escape lets go of it: unlocked, and the cursor is free to leave the window", [said[2], holds[2]])
    c.check(abs(a3 - a2) < 0.5, "once it's let go, moving the mouse doesn't turn the player", [said[2], said[3]])


def t_mouse_busy(c):
    """Escape lets go of the held mouse at once, even while the program is busy and draws no frames (a handler that
    waits, or a loop with no world:frame()): the page's word goes straight to the hold, not through the program."""
    if os.name != "nt" and sys.platform != "darwin":
        c.check(True, "not Windows or a Mac: skipped (the browser's own lock is used)")
        return
    r = play("mouse_busy", game("mouse_hold.tuf"), [
        {"at": 0.5, "click_center": True}, {"at": 0.7, "call": "report"}, {"at": 0.75, "watch_hold": True},
        {"at": 0.8, "js": "setTimeout(() => window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', "
                          "bubbles: true})), 600)"},
        {"at": 0.85, "tuff": 'say "busy start"\nwait(2)\nsay "busy end"'},  # the program busy: no frames for 2 s
        {"at": 0.9, "call": "report"}, {"at": 1.0, "close": True},
    ])
    clean_exit(c, r)
    said = [line for line in r.lines if line.startswith(("locked ", "busy ", "[autopilot] hold watch"))]
    c.check(said[:1] and said[0].startswith("locked true"), "a click on the game holds the mouse", said)
    c.check([line for line in said if not line.startswith("locked ")] == ["busy start", '[autopilot] hold watch {"page": false}', "busy end"],
            "Escape while the program is busy lets go of the mouse right away, not when the program draws its next frame", said)
    locked = [line for line in said if line.startswith("locked ")]
    c.check(len(locked) == 2 and locked[1].startswith("locked false"), "and once the program goes on, world:mouse_locked() is false", said)


def t_mouse_focus(c):
    """The mouse is held only while the game's window has the focus, as with the browser's lock: world:lock_mouse() with
    another window in front (from a timer, at the start, while the player is in another program) doesn't take it, and
    the next click on the game does."""
    if os.name != "nt" and sys.platform != "darwin":
        c.check(True, "not Windows or a Mac: skipped (the browser's own lock is used)")
        return
    page = ("tv.emit('tg-autopilot', {message: 'page ' + JSON.stringify({held: document.pointerLockElement !== null, "
            "cursor: getComputedStyle(document.body).cursor})})")
    r = play("mouse_focus", game("mouse_hold.tuf"), [
        {"at": 0.4, "js": "document.hasFocus = () => false"},  # another window is in front of the game's
        {"at": 0.5, "call": "lock_now"}, {"at": 0.8, "call": "report"}, {"at": 0.85, "js": page},
        {"at": 0.9, "js": "delete document.hasFocus"},  # and now the game's is
        {"at": 1.0, "click_center": True}, {"at": 1.2, "call": "report"}, {"at": 1.25, "js": page},
        {"at": 1.3, "close": True},
    ])
    clean_exit(c, r)
    said = [line for line in r.lines if line.startswith("locked ")]
    pages = [json.loads(line.split("page ", 1)[1]) for line in r.lines if line.startswith("[autopilot] page ")]
    c.check(said[:1] and said[0].startswith("locked false") and pages[:1] and not pages[0]["held"] and pages[0]["cursor"] != "none",
            "world:lock_mouse() while the game's window doesn't have the focus leaves the mouse free (and the cursor showing)",
            [said, pages])
    c.check(said[1:2] and said[1].startswith("locked true") and pages[1:2] and pages[1]["held"],
            "the next click on the game holds it", [said, pages])


def t_mouse_panel(c):
    """With the mouse held for looking around, a click goes to the game even where a menu's card covers the middle of
    the screen (world:panel("center")), as with the browser's lock: it throws the crate the player holds, and
    world:clicked runs."""
    if os.name != "nt" and sys.platform != "darwin":
        c.check(True, "not Windows or a Mac: skipped (the browser's own lock is used)")
        return
    r = play("mouse_panel", game("mouse_panel.tuf"), [
        {"at": 0.5, "click": [120, 120]}, {"at": 0.8, "look": [0, 150]}, {"at": 1.3, "key": "e"},
        {"at": 1.7, "call": "report"}, {"at": 1.75, "shot": "mouse_panel.png"},
        {"at": 1.8, "click_center": True}, {"at": 2.1, "call": "report"}, {"at": 2.2, "close": True},
    ])
    clean_exit(c, r)
    said = [line for line in r.lines if line.startswith("clicks ")]
    c.check(said[:1] and said[0].startswith("clicks 1, holding <box"),
            "a click on the game holds the mouse (world:clicked runs), and E picks up the crate", said)
    c.check(said[1:2] == ["clicks 2, holding nil"],
            "a click with the card under the crosshair goes to the game: it throws the crate, and world:clicked runs", said)


def window_of(pid, title):
    """The visible top-level window with this title that belongs to this process (Windows), or None."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value == title and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(each), 0)
    return found[0] if found else None


def t_close(c):
    """A loop that never calls game:frame() (it waits instead) still ends when the window's X closes it."""
    if os.name != "nt":
        c.check(True, "not Windows: skipped the WM_CLOSE check")
        return
    env = {k: v for k, v in os.environ.items() if k not in ("TUFF_TGAME_AUTOPILOT", "TUFF_IDE")}
    env["PYTHONIOENCODING"] = "utf-8"
    import threading
    proc = subprocess.Popen(tuff_cmd() + [game("close_wait.tuf")], cwd=GAMES, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    lines = []

    def read():
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    hwnd = None
    deadline = time.monotonic() + 30
    while (hwnd is None or "looping" not in lines) and time.monotonic() < deadline and proc.poll() is None:
        hwnd = hwnd or window_of(proc.pid, "tgame close without frame")
        time.sleep(0.05)
    c.check(hwnd is not None and "looping" in lines, "its window opened and the loop is running", lines)
    time.sleep(0.5)
    closed_at = time.monotonic()
    if hwnd is not None:
        import ctypes
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, what the X button sends
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    took = time.monotonic() - closed_at
    reader.join(5)
    err = proc.stderr.read()
    c.check(proc.returncode == 0 and took < 5 and "the loop ended" in lines and "Tuff error" not in err,
            f"closing the window ended game:open() and the program ({took:.1f} s, exit {proc.returncode})", (lines[-3:], err[-300:]))


def t_hud_3d(c):
    r = play("hud_3d", game("hud_3d.tuf"), [
        {"at": 0.5, "click": [80, 40]}, {"at": 0.7, "say": "--"},
        {"at": 0.8, "click_center": True}, {"at": 1.0, "say": "--"},
        {"at": 1.2, "dump": "hud3d_a.json", "memory": True},
        {"at": 1.25, "shot": "hud_3d.png"},
        {"at": 2.6, "call": "report"},
        {"at": 2.65, "dump": "hud3d_b.json", "memory": True},
        {"at": 2.7, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    c.check(r.lines[1:4] == ["HUD button clicked", "world clicked", "--"],
            "a click on a HUD button in 3D runs its :clicked (and the world's), not the box's behind it", r.lines[1:4])
    c.check(r.lines[4:7] == ["red box clicked", "world clicked", "--"], "a click on the box still clicks the box", r.lines[4:7])
    c.check("made true" in r.lines, "over 300 coins made and removed (and moved and labelled after :remove)", r.lines[-2:])
    a, b = r.dumps.get("hud3d_a.json", {}), r.dumps.get("hud3d_b.json", {})
    c.check(b.get("kept", 1e9) < 30 and b.get("view_nodes", 1e9) < 60,
            f"tgame and the window only hold the live objects ({b.get('kept')} objects, {b.get('view_nodes')} ids)", b.get("objects"))
    c.check(a.get("in_memory", 1e9) < 40 and b.get("in_memory", 1e9) < 40,
            f"memory stays flat: {a.get('in_memory')} objects in memory at 1.2 s, {b.get('in_memory')} at 2.6 s",
            (a.get("in_memory"), b.get("in_memory")))
    shot = r.shots.get("hud_3d.png")
    c.check(shot and color_share(shot, (180, 33, 24), 40, (0.4, 0.4, 0.6, 0.8)) > 0.01, "the shapes with size lists are drawn (the red box)", shot)


# The kit as 1.1.0 made it (random.random() giving 0.5, so a rock is 1.05 times its usual size): size, solid body,
# solid. Games made then must not change.
KIT_1_1 = {"tree": ((2.2, 3.4, 2.2), (0.5, 3.4, 0.5), True), "pine": ((2.3, 3.9, 2.3), (0.5, 3.9, 0.5), True),
           "rock": ((1.365, 0.8925, 1.26), None, True), "bush": ((1.5, 0.95, 1.5), None, False),
           "flower": ((0.3, 0.5, 0.3), None, False), "house": ((3.2, 3.6, 3.2), (3.0, 2.2, 3.0), True),
           "hut": ((2.8, 3.1, 2.8), (2.4, 1.7, 2.4), True), "sign": ((1.2, 1.6, 0.2), (0.3, 1.6, 0.2), True),
           "crate": ((0.9, 0.9, 0.9), None, True), "fence": ((2.0, 1.0, 0.16), None, True), "coin": ((0.7, 1.3, 0.12), None, False)}


def kit_sizes(c):
    import random
    import tuff_tgame
    real = random.random
    random.random = lambda: 0.5
    try:
        made = {name: tuff_tgame.kit(name) for name in tuff_tgame.KIT}
    finally:
        random.random = real
    same = lambda a, b: a is b is None or (a is not None and b is not None and all(abs(x - y) < 1e-9 for x, y in zip(a, b)))
    changed = {n: (made[n][0], made[n][1], made[n][3]) for n, (size, body, solid) in KIT_1_1.items()
               if not (same(made[n][0], size) and same(made[n][1], body) and made[n][3] == solid)}
    c.check(list(tuff_tgame.KIT[:11]) == list(KIT_1_1) and not changed,
            "the kit's 11 models from 1.1.0 keep their names, sizes, solid bodies and solidness", changed)
    c.check(made["person"][0] == (0.7, 1.75, 0.5) and made["chest"][0] == (0.9, 0.75, 0.6), "and the person and the chest are new",
            {n: made[n][0] for n in ("person", "chest")})
    c.check(all(p.get("shadow") for n in made for _, p, _ in made[n][2]), "every part of every model casts shadows")
    styles = {n: next((p["anim"] for _, p, _ in made[n][2] if "anim" in p), None) for n in made}
    c.check(styles["tree"] == "tree" and styles["coin"] == "coin" and styles["house"] is None and styles["person"][:2] == ["person", "leg_l"],
            "trees, bushes, flowers and coins move by themselves in the page, houses don't, a person's parts say which limb they are", styles)
    c.check('Did you mean "walk"?' in tuff_tgame.animation_problem("wlak"), "thing:animate with a misspelt name says which one it means",
            tuff_tgame.animation_problem("wlak"))


def changed_pixels(a, b, box=(0, 0, 1, 1), step=2):
    """How many pixels (every `step`-th, in box) differ between two pictures of the same size."""
    try:
        w, h, get_a = png_rgb(a)
        _, _, get_b = png_rgb(b)
    except Exception:
        return -1
    return sum(1 for y in range(int(box[1] * h), int(box[3] * h), step) for x in range(int(box[0] * w), int(box[2] * w), step)
               if max(abs(p - q) for p, q in zip(get_a(x, y), get_b(x, y))) > 12)


def t_people(c):
    """The kit's people from every side, the same pictures every time (out/people_*.png: look at them after a change
    to person_parts): three standing from the front, a close-up of the shoulders and arms, one walking from the side,
    one waving, from the back, two ragdolls (one pushed over), and the player in third person holding an axe."""
    shots = ["people_front.png", "people_close.png", "people_side.png", "people_wave.png", "people_back.png", "people_ragdoll.png"]
    steps = [{"at": 0.4, "call": "push"}]
    for i, (fn, shot) in enumerate(zip(["front", "close", "side", "wave", "back", "ragdolls"], shots)):
        steps += [{"at": 0.7 + i * 0.35, "call": fn}, {"at": 0.95 + i * 0.35, "shot": shot}]
    r = play("people", game("people_showcase.tuf"), steps + [{"at": 3.0, "close": True}])
    clean_exit(c, r)
    c.check(all(r.shots.get(s) for s in shots), "a picture from every side", [s for s in shots if not r.shots.get(s)])
    r = play("people_player", game("people_player.tuf"), [
        {"at": 0.7, "shot": "people_player.png"}, {"at": 0.8, "hold": "w", "for": 0.6}, {"at": 1.2, "shot": "people_player_walk.png"},
        {"at": 1.6, "close": True}])
    clean_exit(c, r)
    c.check(r.shots.get("people_player.png") and r.shots.get("people_player_walk.png"), "the player holding an axe, standing and walking",
            r.shots)


def t_models(c):
    """games/models.tuf, every model in the kit (the pictures, out/models_*.png, are worth a look after a change to the
    kit); they move by themselves in the page (anim.js): people breathe, wave and walk, trees sway, coins spin and bob,
    and nothing moves while the game is paused. The kit's sizes are the same as in 1.1.0, so older games don't change."""
    kit_sizes(c)
    r = play("models", game("models.tuf"), [
        {"at": 0.6, "shot": "models.png"}, {"at": 0.8, "shot": "models_later.png"},
        {"at": 0.85, "tuff": 'game:lighting "modern"'}, {"at": 1.25, "shot": "models_modern.png"},
        {"at": 1.3, "tuff": 'game:lighting "simple"'},
        {"at": 1.35, "tuff": "game:camera_at(0, 1.5, 1.2)"}, {"at": 1.37, "tuff": "game:look_at(0, 1.0, -2)"},
        {"at": 1.7, "shot": "models_people.png"},
        {"at": 1.75, "call": "walk"}, {"at": 2.35, "shot": "models_walking.png"},
        {"at": 2.4, "call": "still"},
        {"at": 2.5, "tuff": "game:pause()"}, {"at": 3.3, "shot": "models_paused.png"}, {"at": 3.8, "shot": "models_paused_later.png"},
        {"at": 3.9, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    c.check(any(line.startswith("animate <person at") for line in r.lines), "thing:animate gives back the thing", r.lines[-3:])
    shot = r.shots.get("models.png")
    c.check(shot and color_share(shot, (167, 77, 65), 30, (0.36, 0.32, 0.5, 0.43)) > 0.3, "the house has its red roof", shot)
    c.check(shot and color_share(shot, (212, 178, 99), 30, (0.5, 0.35, 0.62, 0.47)) > 0.15, "the hut has its straw roof", shot)
    c.check(shot and color_share(shot, (76, 140, 56), 25, (0.15, 0.33, 0.25, 0.45)) > 0.1, "the tree has its leaves", shot)
    moving = changed_pixels(shot, r.shots.get("models_later.png"))
    c.check(moving > 150, f"a fifth of a second later the people, trees and coin have moved ({moving} pixels changed)", moving)
    still = changed_pixels(r.shots.get("models_paused.png"), r.shots.get("models_paused_later.png"))
    c.check(0 <= still < 60, f"while the game is paused nothing moves ({still} pixels changed in half a second)", still)
    # The player in third person swaps its axe for a sword and walks: the sword goes up and down with its hand (the
    # page moves what it holds now, not the axe that's gone).
    r = play("models_held", game("models_held.tuf"), [
        {"at": 0.5, "dump": "mh_axe.json"}, {"at": 0.6, "tuff": 'player:hold("sword")'},
        {"at": 0.7, "hold": "w", "for": 0.8}, {"at": 1.2, "dump": "mh_sword.json"}, {"at": 1.25, "shot": "models_held.png"},
        {"at": 1.6, "close": True}])
    clean_exit(c, r)
    axe, sword = [((r.dumps.get(n, {}).get("page") or {}).get("anim") or {}) for n in ("mh_axe.json", "mh_sword.json")]
    c.check(axe.get("held") == 1 and sword.get("held") == 1 and sword.get("stale") == 0,
            "a thing the player holds moves with its hand, and so does the one it holds after a swap (not the one that's gone)", (axe, sword))


def t_terrain(c):
    """The land (world:terrain): the player walks up a hill and stops at a lake's shore and at the land's edge;
    things made at y 0 stand on it; every y a program gives or reads is the height above the land; and a game that
    changes the land every frame keeps 60 fps."""
    r = play("terrain_walk", game("terrain_walk.tuf"), [
        {"at": 0.3, "call": "report"}, {"at": 0.35, "dump": "tw_start.json"}, {"at": 0.4, "shot": "terrain_walk.png"},
        {"at": 0.6, "hold": "w", "for": 1.8},
        {"at": 3.0, "call": "where"}, {"at": 3.05, "dump": "tw_hill.json"}, {"at": 3.1, "shot": "terrain_walk_hill.png"},
        {"at": 3.3, "tuff": "player:turn_to(90)"}, {"at": 3.35, "tuff": "player:move_to(15, 0, 0)"},
        {"at": 3.5, "hold": "w", "for": 2.4},
        {"at": 6.4, "call": "where"}, {"at": 6.45, "dump": "tw_lake.json"}, {"at": 6.5, "shot": "terrain_walk_lake.png"},
        {"at": 6.7, "tuff": "player:move_to(95, 0, -50)"},
        {"at": 6.8, "hold": "w", "for": 1.2},
        {"at": 8.4, "call": "where"}, {"at": 8.45, "dump": "tw_edge.json"}, {"at": 8.5, "shot": "terrain_walk_edge.png"},
        {"at": 8.6, "call": "moved"}, {"at": 8.7, "call": "glided"},
        {"at": 8.8, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    got = r.lines[1:]
    for line in ["hill top 5.951", "at the box 5.951", "box y 0 spot [0, 0, -14]", "ball y 3", "tree y 0", "later y 0",
                 "player y 0", "slid y 0", "glided y 0 at -26"]:
        c.check(line in got, f"says: {line}", [g for g in got if g.split(" ")[0] == line.split(" ")[0]] or got[-5:])
    c.check(any(g.startswith("moved y 0 ground 4.") for g in got), "move_to(x, 0, z) on a slope puts it on the land there", got[-4:])
    bottom = [float(g.split()[-1]) for g in got if g.startswith("lake bottom ")]
    c.check(bottom and -3.1 < bottom[0] < -2.7, "a lake 3 deep digs the land 3 down in its middle", bottom)
    start = r.dumps.get("tw_start.json", {})
    objs = {o[0] + str(o[1]): o for o in start.get("objects", [])}
    box, ball = objs.get("box0.0"), objs.get("sphere-10.0")
    c.check(box and abs(box[2] - 5.951) < 0.01, "inside, the box at y 0 is at the hill's height (5.95)", box)
    c.check(ball and ball[2] > 3.5, "the ball at y 3 is 3 above the land, not 3 above 0", ball)
    p0 = start.get("player") or [0, 0, 0]
    hill = r.dumps.get("tw_hill.json", {}).get("player") or [0, 0, 0]
    c.check(hill[2] < -6 and hill[1] > p0[1] + 3.5, f"walking forward climbs the hill (height {p0[1]} -> {hill[1]})", (p0, hill))
    lake = r.dumps.get("tw_lake.json", {}).get("player") or [0, 0, 0]
    c.check(19 < lake[0] < 23.5 and abs(lake[2]) < 0.05 and lake[1] > -0.4,
            f"the lake's shore stops the player (x {lake[0]}, the water starts at about 22)", lake)
    edge = r.dumps.get("tw_edge.json", {}).get("player") or [0, 0, 0]
    c.check(98.5 < edge[0] <= 99.41, f"the player can't walk off the land's edge (x {edge[0]} of 100)", edge)
    shot = r.shots.get("terrain_walk.png")
    c.check(shot and color_share(shot, (115, 165, 75), 45, (0, 0.55, 1, 1)) > 0.5, "the screenshot shows the grassy hill", shot)
    c.check(shot and color_share(shot, (180, 50, 55), 50, (0.4, 0.15, 0.6, 0.35)) > 0.01, "and the red box on top of it", shot)
    shot = r.shots.get("terrain_walk_lake.png")
    c.check(shot and color_share(shot, (40, 120, 160), 50, (0.2, 0.7, 0.8, 1)) > 0.3, "at the shore, the lake's water is in front", shot)
    shot = r.shots.get("terrain_walk_edge.png")
    c.check(shot and color_share(shot, (115, 165, 75), 50, (0, 0.6, 1, 1)) > 0.4,
            "at the edge the land goes on to the horizon (no looking into nothing)", shot)
    # A game that digs: a brush raising the land every frame, on the biggest land (254 x 254 points)
    r = play("terrain_dig", game("terrain_dig.tuf"), [
        {"at": 1.0, "call": "start"}, {"at": 1.3, "mark": True}, {"at": 4.3, "dump": "terrain_dig.json"},
        {"at": 4.35, "shot": "terrain_dig.png"}, {"at": 4.5, "close": True}], timeout=90)
    clean_exit(c, r)
    d = r.dumps.get("terrain_dig.json", {})
    page = d.get("page") or {}
    c.check((d.get("python_fps") or 0) >= 55 and page.get("apply_ms_per_batch", 99) < 4,
            f"raising the land every frame: {d.get('python_fps')} fps, the page applies each frame's heights in "
            f"{round(page.get('apply_ms_per_batch', 0), 2)} ms", {k: page.get(k) for k in ("fps", "apply_ms_per_batch", "batches")})
    shot = r.shots.get("terrain_dig.png")
    c.check(shot and color_share(shot, (130, 130, 125), 35, (0, 0.5, 0.7, 0.62)) > 0.1, "the ridge it raised is drawn", shot)


def t_terrain_look(c):
    """How the land looks: every style, simple and modern lighting, switching back and forth, at noon and at sunset.
    The pictures are in out/ (terrain_*.png) to look at."""
    steps = [{"at": 0.8, "shot": "terrain_modern.png"},
             {"at": 0.9, "tuff": 'world:lighting "simple"'}, {"at": 1.3, "shot": "terrain_simple.png"},
             {"at": 1.4, "tuff": 'world:lighting "modern"'}, {"at": 1.8, "shot": "terrain_modern_again.png"}]
    at = 1.9
    for style in ("desert", "snow", "rocky", "autumn", "grass"):
        steps += [{"at": at, "tuff": f'land:style "{style}"'}, {"at": at + 0.4, "shot": f"terrain_{style}.png"}]
        at += 0.5
    steps += [{"at": at, "tuff": 'world:sky "sunset"'}, {"at": at + 0.4, "shot": "terrain_sunset_modern.png"},
              {"at": at + 0.5, "tuff": 'world:lighting "simple"'}, {"at": at + 0.9, "shot": "terrain_sunset_simple.png"},
              {"at": at + 1.0, "tuff": "world:camera_at(8, 2.2, 40)"}, {"at": at + 1.02, "tuff": "world:look_at(25, 0, 15)"},
              {"at": at + 1.04, "tuff": 'world:sky "day"'}, {"at": at + 1.06, "tuff": 'world:lighting "modern"'},
              {"at": at + 1.5, "shot": "terrain_lake.png"}, {"at": at + 1.7, "close": True}]
    r = play("terrain_look", game("terrain_look.tuf"), steps)
    first_line_is_notice(c, r)
    clean_exit(c, r)
    shots = r.shots
    c.check(len(shots) == 11, f"every picture was taken ({len(shots)} of 11)", sorted(shots))

    def mean(name, box=(0.45, 0.72, 1, 1)):  # land only: below the lake, right of the river
        try:
            w, h, get = png_rgb(shots[name])
        except Exception:
            return (0, 0, 0)
        px = [get(x, y) for y in range(int(box[1] * h), int(box[3] * h), 4) for x in range(int(box[0] * w), int(box[2] * w), 4)]
        return tuple(round(sum(p[k] for p in px) / max(1, len(px))) for k in range(3))

    looks = {name: mean(f"terrain_{name}.png") for name in ("modern", "simple", "modern_again", "desert", "snow", "rocky",
                                                              "autumn", "grass", "sunset_modern", "sunset_simple")}
    print(f"  COLORS {json.dumps(looks)}", flush=True)
    g = looks["grass"]
    c.check(g[1] > g[0] + 30 and g[1] > g[2] + 50, "grass is green", g)
    d = looks["desert"]
    c.check(d[0] > 170 and d[0] > d[2] + 40 and d[1] > d[2] + 20, "desert is sandy", d)
    s = looks["snow"]
    c.check(min(s) > 185 and max(s) - min(s) < 40, "snow is white", s)
    k = looks["rocky"]
    c.check(max(k) - min(k) < 45 and 90 < k[1] < 200, "rocky is grey", k)
    a = looks["autumn"]
    c.check(a[0] > a[1] + 25 and a[1] > a[2] + 25, "autumn is orange and gold", a)
    diff = lambda x, y: sum(abs(p - q) for p, q in zip(looks[x], looks[y]))
    c.check(diff("modern", "simple") > 15 and diff("modern", "modern_again") < 8,
            "modern and simple lighting look different, and switching back gives modern again",
            (looks["modern"], looks["simple"], looks["modern_again"]))
    c.check(diff("sunset_modern", "sunset_simple") > 15, "at sunset too", (looks["sunset_modern"], looks["sunset_simple"]))
    shot = shots.get("terrain_lake.png")
    c.check(shot and color_share(shot, (60, 140, 175), 60, (0.3, 0.4, 0.7, 0.5)) > 0.3, "the lake has water in it", shot)
    c.check(shot and color_share(shot, (215, 200, 150), 45, (0, 0.38, 1, 0.55)) > 0.03, "with a sandy shore", shot)
    c.check(shot and color_share(shot, (110, 115, 115), 45, (0.25, 0.15, 0.45, 0.4)) > 0.05,
            "behind it, the mountain is rocky", shot)


def t_no_webgl(c):
    """Without WebGL (as on some school PCs and virtual machines), a 3D world stops with one plain message."""
    if os.name != "nt":
        c.check(True, "not Windows: skipped the no-WebGL check")
        return
    r = play("no_webgl", game("hud_3d.tuf"), [{"at": 1.0, "close": True}],
             env={"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--disable-3d-apis"})
    c.check(r.code == 1 and r.err.count("Tuff error") == 1 and "can't show 3D worlds" in r.err and "line 5" in r.err,
            f"one clear error, on the tgame.world line, instead of one for every object (exit {r.code})", r.err[-600:])


# ---------------------------------------------------------------- physics (Rapier, in the page)

def bodies(d, kind):
    """A dump's physics things of a kind: 3D [kind, x, y above the land, z, speed, heading, up (1 upright, 0 on its
    side)], 2D [shape, x, y, angle, speed]."""
    return [b for b in ((d.get("physics") or {}).get("bodies") or []) if b[0] == kind]


def said(r, start):
    """The last line the game said that starts with these words, as its words, or []."""
    lines = [line for line in r.lines if line.startswith(start)]
    return lines[-1].split() if lines else []


def page_physics(d):
    return (d.get("page") or {}).get("physics")


def t_physics(c):
    """3D physics: a crate falls and lands on the land (and a box on a hill), a bouncy ball bounces lower each time,
    pausing the game pauses physics, a tower of boxes stands until it's pushed, a crate's on_hit says what hit it, an
    explosion scatters boxes, and ragdolls stand until they're pushed or hit, then flop and lie on the ground. Things
    asleep, hidden or fallen off the world aren't drawn again."""
    r = play("physics_drop", game("physics_drop.tuf"), [
        {"at": 0.3, "dump": "pd_start.json"},
        {"at": 0.8, "tuff": "lifted = world:box(-3, 0, 4, 1, \"gold\"):physics()"},
        {"at": 1.3, "tuff": "lifted:move_to(-3, 5, 4)"}, {"at": 1.4, "dump": "pd_lifted.json"},
        # (The ball's second bounce is about 3 s after Rapier has loaded, which takes up to half a second.)
        {"at": 4.2, "call": "report"}, {"at": 4.25, "dump": "pd_end.json"}, {"at": 4.3, "shot": "physics_drop.png"},
        {"at": 4.4, "tuff": "world:pause()"}, {"at": 4.5, "dump": "pd_pause1.json"}, {"at": 5.1, "dump": "pd_pause2.json"},
        {"at": 5.2, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    start, end = r.dumps.get("pd_start.json", {}), r.dumps.get("pd_end.json", {})
    c.check(page_physics(start) in ("loading", None) or page_physics(start).get("dim") == 3,
            "the page loads 3D physics (Rapier) for a world that uses it", page_physics(start))
    crate0, crate1 = (bodies(start, "crate") or [None])[0], (bodies(end, "crate") or [None])[0]
    c.check(crate0 and crate1 and crate0[2] > 4.5 and abs(crate1[2]) < 0.03 and crate1[4] < 0.05,
            f"a crate made 6 above the land falls and comes to rest on it (y {crate1 and crate1[2]})", (crate0, crate1))
    box = (bodies(end, "box") or [None])[0]
    c.check(box and abs(box[2]) < 0.3 and box[4] < 0.05 and "3.96" in " ".join(said(r, "hill crate")),
            "a box dropped on a hill lands on the hill (the land is a heightfield of its own heights)", (box, said(r, "hill crate")))
    lifted, landed = (bodies(r.dumps.get("pd_lifted.json", {}), "box") or [None, None])[-1], (bodies(end, "box") or [None, None])[-1]
    c.check(lifted and landed and lifted[1] == -3 and 3 < lifted[2] <= 5 and abs(landed[2]) < 0.05 and abs(landed[1] + 3) < 0.3,
            "move_to puts a physics thing somewhere (5 up) and it falls from there", (lifted, landed))
    try:
        peaks = json.loads(" ".join(said(r, "peaks")[1:]))
    except ValueError:
        peaks = []
    c.check(len(peaks) >= 2 and peaks[0] > 7 and all(b < a * 0.7 for a, b in zip(peaks, peaks[1:])),
            f"a ball with bounce 0.7 bounces lower each time ({peaks})", peaks)
    c.check(int((said(r, "hits") or ["", "0"])[1]) >= 2, "its on_hit runs for each bounce", said(r, "hits"))
    p1, p2 = page_physics(r.dumps.get("pd_pause1.json", {})) or {}, page_physics(r.dumps.get("pd_pause2.json", {})) or {}
    c.check(p1.get("paused") and p1.get("steps") == p2.get("steps"), "world:pause() pauses physics too", (p1, p2))
    shot = r.shots.get("physics_drop.png")
    c.check(shot and color_share(shot, (125, 80, 45), 45, (0.3, 0.5, 0.5, 0.7)) > 0.01, "the screenshot shows the crate on the land", shot)

    r = play("physics_tower", game("physics_tower.tuf"), [
        {"at": 2.0, "call": "report"}, {"at": 2.05, "shot": "physics_tower.png"},
        {"at": 2.1, "call": "topple"}, {"at": 2.2, "call": "boom"},
        {"at": 4.2, "call": "report"}, {"at": 4.25, "call": "spread"}, {"at": 4.3, "shot": "physics_tower_after.png"},
        {"at": 4.5, "close": True}])
    clean_exit(c, r)
    tops = [line.split() for line in r.lines if line.startswith("tower top")]
    c.check(len(tops) == 2 and abs(float(tops[0][3]) - 3) < 0.05, "a tower of 4 boxes stands (its top stays 3 up)", tops)
    c.check(len(tops) == 2 and float(tops[1][3]) < 1.5 and float(tops[1][5]) > 1, "pushed, it falls over", tops)
    hits = [line for line in r.lines if line.startswith("the crate was hit by")]
    c.check(hits and hits[0].startswith("the crate was hit by <sphere") and float(hits[0].split()[-1]) > 5,
            "on_hit gets what hit it and how hard (a heavy ball falling on the crate; resting where it was made isn't a hit)", hits[:3])
    near = said(r, "ring nearest")
    c.check(near and float(near[-1]) > 4.5, f"world:explode throws the boxes around it away (the nearest went from 3 to {near and near[-1]})", near)

    r = play("physics_ragdoll", game("physics_ragdoll.tuf"), [
        {"at": 1.0, "dump": "pr_start.json"}, {"at": 1.05, "shot": "physics_ragdoll_stand.png"},
        {"at": 1.2, "call": "shove"}, {"at": 1.3, "call": "drop"},
        {"at": 4.5, "call": "report"}, {"at": 4.55, "dump": "pr_end.json"}, {"at": 4.6, "shot": "physics_ragdoll.png"},
        {"at": 4.8, "close": True}])
    clean_exit(c, r)
    before, after = bodies(r.dumps.get("pr_start.json", {}), "ragdoll"), bodies(r.dumps.get("pr_end.json", {}), "ragdoll")
    c.check(len(before) == 3 and before[0][4] == 0 and before[0][6] > 0.99 and before[2][6] > 0.99,
            "ragdolls made on the ground stand still until something happens", before)
    c.check(len(before) == 3 and (before[1][2] > 0.2 or before[1][4] > 1), "one made in the air falls", before)
    c.check(len(after) == 3 and all(abs(b[2]) < 0.05 and b[6] < 0.5 for b in after),
            "pushed, hit by a ball, or fallen, each one ends up lying on the ground", after)
    shot = r.shots.get("physics_ragdoll.png")
    c.check(shot and color_share(shot, (40, 90, 200), 50, (0.3, 0.4, 0.7, 0.7)) > 0.001, "the screenshot shows the blue one lying there", shot)

    r = play("physics_reset", game("physics_reset.tuf"), [
        {"at": 0.8, "call": "topple"}, {"at": 1.0, "call": "grow_it"}, {"at": 2.0, "call": "drop_ball"},
        {"at": 2.6, "dump": "px_grown.json"}, {"at": 2.65, "dump": "px_lost.json"},
        {"at": 3.0, "call": "bring_back"}, {"at": 3.2, "dump": "px_lying.json"},
        {"at": 3.3, "call": "shake_it"}, {"at": 3.5, "dump": "px_shaking.json"}, {"at": 4.2, "dump": "px_shaken.json"},
        {"at": 4.4, "dump": "px_back.json"}, {"at": 5.6, "call": "report"}, {"at": 5.65, "shot": "physics_reset.png"},
        {"at": 5.8, "close": True}])
    clean_exit(c, r)
    words = said(r, "resets")
    resets, doubles = (int(words[1]), int(words[3])) if len(words) > 3 else (0, -1)
    c.check(resets >= 2 and doubles == 0,
            f"a ball the program sends back up as it lands goes up once a fall ({resets} times, {doubles} twice in a row): the "
            "page's report from before the move doesn't put it back down", words)
    lost, back = (bodies(r.dumps.get("px_lost.json", {}), "box") or [[]])[-1], (bodies(r.dumps.get("px_back.json", {}), "box") or [[]])[-1]
    c.check(len(lost) > 2 and lost[2] < -300 and len(back) > 4 and abs(back[2]) < 0.05 and back[4] < 0.2 and abs(back[1] - 3) < 0.3,
            f"a box that fell off the world (y {lost[2] if len(lost) > 2 else '?'}), put back with move_to, falls and lands again "
            f"(y {back[2] if len(back) > 2 else '?'})", (lost, back))
    grown = ([b for b in bodies(r.dumps.get("px_grown.json", {}), "sphere") if abs(b[1] - 6) < 1] or [[]])[0]
    c.check(len(grown) > 2 and abs(grown[2]) < 0.05, f"a ball that grows as it falls keeps falling and lands (y {grown[2] if len(grown) > 2 else '?'})", grown)
    poles = [(bodies(r.dumps.get(f"px_{n}.json", {}), "box") or [[]])[0] for n in ("lying", "shaking", "shaken")]
    c.check(all(len(p) > 6 for p in poles) and all(abs(p[6]) < 0.3 and abs(p[2]) < 0.3 for p in poles)
            and math.dist(poles[0][1:4:2], poles[2][1:4:2]) < 0.3,
            "a pole lying on its side that shakes stays lying where it was (a shake only tilts how it's drawn)", poles)
    hits = [line for line in r.lines if line.startswith("the crate was hit by")]
    c.check(hits and all(h.startswith("the crate was hit by <sphere") for h in hits),
            "a bullet removed just as it hits a crate: the crate's on_hit still gets the bullet (not nil)", hits[:3])
    shot = r.shots.get("physics_reset.png")
    c.check(shot and color_share(shot, (200, 60, 60), 60, (0.3, 0.2, 0.7, 0.7)) > 0.001, "the screenshot shows the red ball", shot)

    # Nothing moving, nothing to draw: once physics has put 48 boxes to sleep, the page stops drawing the world.
    rest = perf(c, "physics_rest", "physics_rest.tuf", [{"at": 3.5, "mark": True}, {"at": 4.5, "dump": "physics_rest.json"},
                                                         {"at": 4.6, "close": True}], "48 boxes asleep")
    awake = (rest.get("physics") or {}).get("awake")
    c.check(awake == 0 and rest["page_draws_per_s"] < 5,
            f"48 boxes asleep ({awake} awake): the page draws {rest['page_draws_per_s']} times a second", rest)
    # Nor once they've gone: hidden (settled, or as it falls) or fallen off the world, their bodies are switched off.
    gone = perf(c, "physics_gone", "physics_gone.tuf", [{"at": 1.2, "call": "hide_faller"}, {"at": 3.0, "call": "hide_boxes"},
                                                       {"at": 3.5, "mark": True}, {"at": 4.5, "dump": "physics_gone.json"},
                                                       {"at": 4.6, "close": True}], "8 boxes gone")
    awake = (gone.get("physics") or {}).get("awake")
    c.check(awake == 0 and gone["page_draws_per_s"] < 5,
            f"7 boxes hidden and one fallen off the world aren't moving ({awake} awake): the page draws "
            f"{gone['page_draws_per_s']} times a second", gone)


def t_physics_player(c):
    """The player and physics: walking into a crate pushes it, the player stands on a physics box and jumps off it
    (with Space, and with player:jump() in an every-frame function), a ball falling on the player is an on_hit, a
    move_to in an every-frame function puts the player there (the page's next report doesn't put it back), and a
    kinematic lift carries the player up."""
    r = play("physics_player", game("physics_player.tuf"), [
        {"at": 0.6, "call": "where"},
        {"at": 0.7, "hold": "w", "for": 1.5},
        {"at": 2.4, "call": "where"}, {"at": 2.45, "dump": "pp_push.json"}, {"at": 2.5, "shot": "physics_player.png"},
        {"at": 2.6, "call": "stand"},
        {"at": 3.8, "call": "where"}, {"at": 3.85, "dump": "pp_stand.json"},
        {"at": 3.9, "key": "space"}, {"at": 4.2, "dump": "pp_jump.json"},
        {"at": 5.2, "tuff": "hop = true"}, {"at": 5.5, "dump": "pp_hop.json"},
        {"at": 6.4, "tuff": "player:move_to(6, 0, 8)"}, {"at": 6.5, "call": "drop"},
        {"at": 8.0, "tuff": "warp = true"}, {"at": 8.3, "call": "where"}, {"at": 8.35, "dump": "pp_warp.json"},
        {"at": 8.4, "tuff": "lift:glide(10, 2, 4, 1)"}, {"at": 9.8, "call": "where"}, {"at": 9.85, "dump": "pp_lift.json"},
        {"at": 10.0, "close": True}])
    clean_exit(c, r)
    push = r.dumps.get("pp_push.json", {})
    crate, p = (bodies(push, "crate") or [None])[0], push.get("player") or [0, 0, 0]
    c.check(crate and crate[3] < -2 and p[2] < 0 and p[2] > crate[3] + 0.5,
            f"walking into a crate pushes it along (it went from z 1 to {crate and crate[3]}, the player is behind it)", (crate, p))
    stand = r.dumps.get("pp_stand.json", {})
    sp = stand.get("player") or [0, 0, 0]
    c.check(0.85 < sp[1] < 1.0 and stand.get("on_ground"), f"the player stands on a physics box (y {sp[1]}), on the ground there", stand.get("player"))
    jump = (r.dumps.get("pp_jump.json", {}).get("player") or [0, 0, 0])
    c.check(jump[1] > 1.5, f"and can jump off it (y {jump[1]})", jump)
    hop = (r.dumps.get("pp_hop.json", {}).get("player") or [0, 0, 0])
    c.check(hop[1] > 1.5, f"player:jump() in an every-frame function jumps off it too, every time (y {hop[1]})", hop)
    c.check(any(line.startswith("the player was hit by <sphere") for line in r.lines), "a ball falling on the player: player:on_hit runs",
            r.lines[-4:])
    warp = (r.dumps.get("pp_warp.json", {}).get("player") or [0, 0, 0])
    c.check(abs(warp[0] - 10) < 0.2 and abs(warp[2] - 4) < 0.2,
            f"player:move_to in an every-frame function puts the player there, and it stays (x {warp[0]}, z {warp[2]})", warp)
    lift = (r.dumps.get("pp_lift.json", {}).get("player") or [0, 0, 0])
    c.check(2.2 < lift[1] < 2.45 and abs(lift[0] - 10) < 0.2, f"a kinematic lift gliding up carries the player up with it (y {lift[1]})", lift)
    shot = r.shots.get("physics_player.png")
    c.check(shot and color_share(shot, (125, 80, 45), 45, (0.35, 0.5, 0.65, 0.9)) > 0.05, "the screenshot shows the crate in front", shot)


def t_physics_car(c):
    """world:car: W drives it forward, W with A turns it left, S brakes and backs up, it stays on its wheels, and the
    camera follows it."""
    r = play("physics_car", game("physics_car.tuf"), [
        {"at": 1.0, "call": "report"}, {"at": 1.05, "dump": "pc_start.json"},
        {"at": 1.1, "hold": "w", "for": 3.0}, {"at": 3.0, "shot": "physics_car.png"},
        {"at": 4.0, "call": "report"}, {"at": 4.05, "dump": "pc_fwd.json"},
        {"at": 4.1, "hold": "w", "for": 1.6}, {"at": 4.15, "hold": "a", "for": 1.5},
        {"at": 5.8, "call": "report"}, {"at": 5.85, "dump": "pc_turn.json"},
        {"at": 6.0, "hold": "s", "for": 2.0}, {"at": 8.1, "call": "report"},
        {"at": 8.3, "close": True}])
    clean_exit(c, r)
    car0 = (bodies(r.dumps.get("pc_start.json", {}), "car") or [None])[0]
    fwd = (bodies(r.dumps.get("pc_fwd.json", {}), "car") or [None])[0]
    turn = (bodies(r.dumps.get("pc_turn.json", {}), "car") or [None])[0]
    c.check(car0 and abs(car0[2]) < 0.05 and car0[6] > 0.99, "the car stands on its wheels on the land", car0)
    reports = [line.split() for line in r.lines if line.startswith("car ")]
    speed = [float(w[-2]) for w in reports]
    c.check(fwd and fwd[3] < -12 and len(speed) == 4 and speed[1] > 25,
            f"holding W drives it forward (z {fwd and fwd[3]}, {speed[1] if len(speed) > 1 else '?'} km/h)", reports)
    c.check(turn and 180 < turn[5] < 330 and turn[6] > 0.9, f"with A it turns left (facing {turn and turn[5]}) and stays on its wheels", turn)
    c.check(len(speed) == 4 and speed[3] < 0, "S brakes, then backs up (km/h below 0)", speed)
    camera = r.dumps.get("pc_fwd.json", {}).get("camera") or [0, 0, 0]
    c.check(fwd and 4 < math.dist(camera[:3], [fwd[1], fwd[2], fwd[3]]) < 12, "the camera follows it from behind", (camera, fwd))
    shot = r.shots.get("physics_car.png")
    c.check(shot and color_share(shot, (200, 50, 60), 60, (0.3, 0.35, 0.7, 0.8)) > 0.02, "the screenshot shows the red car ahead", shot)

    # The player gets in (standing in front of the car), drives off, looks around on the way, brakes, and gets out
    # (in an every-frame function, in a frame that takes a while).
    r = play("physics_drive", game("physics_drive.tuf"), [
        {"at": 0.8, "call": "report"}, {"at": 0.85, "dump": "pv_start.json"},
        {"at": 0.9, "call": "get_in"}, {"at": 1.0, "lock": True},
        {"at": 1.1, "hold": "w", "for": 2.6}, {"at": 3.75, "hold": "space", "for": 0.9},
        {"at": 1.5, "look": [300, 0]}, {"at": 1.8, "look": [300, 40]}, {"at": 2.1, "look": [300, 40]},
        {"at": 2.5, "dump": "pv_driving.json"},
        {"at": 4.6, "call": "report"}, {"at": 4.65, "dump": "pv_drive.json"},
        {"at": 4.7, "tuff": "leave = true"},
        {"at": 5.2, "call": "report"}, {"at": 5.25, "dump": "pv_out.json"}, {"at": 5.3, "shot": "physics_drive.png"},
        {"at": 5.5, "close": True}])
    clean_exit(c, r)
    start, driving = r.dumps.get("pv_start.json", {}), r.dumps.get("pv_driving.json", {})
    drove, out = r.dumps.get("pv_drive.json", {}), r.dumps.get("pv_out.json", {})
    p0, p1 = start.get("player") or [0, 0, 0, 0], out.get("player") or [0, 0, 0, 0]
    car = (bodies(drove, "car") or [None])[0]  # just before the player gets out
    c.check(car and car[3] < -9 and int((said(r, "car") or ["0"])[-1]) == 0,
            f"the car drives on through where the player got in (z {car and car[3]}): the player isn't left standing there, and nothing hits it",
            (car, said(r, "car")))
    c.check(start.get("player_shown") is True and driving.get("player_shown") is False and out.get("player_shown") is True,
            "the player's figure isn't left standing there either: it's hidden while it drives, and back when it gets out",
            [d.get("player_shown") for d in (start, driving, out)])
    c.check(car and math.dist((p1[0], p1[2]), (car[1], car[3])) < 3 and math.dist((p1[0], p1[2]), (p0[0], p0[2])) > 4,
            f"car:drive(false) in an every-frame function: the player gets out beside the car's door (at {p1[:3]}, the car at {car and car[1:4]})",
            (p0, p1, car))
    c.check(abs((p1[3] - p0[3] + 180) % 360 - 180) < 1,
            f"moving the mouse while driving doesn't turn the player: it gets out facing the way it did ({p0[3]} -> {p1[3]})", (p0, p1))


def car_reports(r):
    """The car_enter game's reports: [{"car": [x, y, z], "player": [x, y, z], "in": bool, "driven": bool, "ins": n,
    "outs": n}, ...]."""
    out = []
    for line in r.lines:
        m = re.match(r"car \[(.*?)\] player \[(.*?)\] in (\w+) driven (\w+) ins (\d+) outs (\d+)", line)
        if m:
            out.append({"car": [float(v) for v in m[1].split(",")], "player": [float(v) for v in m[2].split(",")],
                        "in": m[3] == "true", "driven": m[4] == "true", "ins": int(m[5]), "outs": int(m[6])})
    return out


def t_car_enter(c):
    """Getting into a car with F (1.3.0): nothing happens far from it; next to it the hint says "F: Get in" and F gets
    in (the player's figure goes, car:on_enter runs, player:in_car() and car:driven() say so); W drives it with the
    player in it (player:spot() goes with the car); and F gets out beside its door (car:on_exit runs, the figure's
    back, and the car stays parked)."""
    r = play("car_enter", game("car_enter.tuf"), [
        {"at": 0.6, "dump": "ce_far.json"}, {"at": 0.65, "key": "f"}, {"at": 0.9, "call": "report"},
        {"at": 1.0, "tuff": "player:move_to(-2.3, 0, 0)"}, {"at": 1.3, "dump": "ce_near.json"},
        {"at": 1.35, "key": "f"}, {"at": 1.6, "call": "report"}, {"at": 1.65, "dump": "ce_in.json"},
        {"at": 1.7, "hold": "w", "for": 2.0}, {"at": 3.75, "hold": "space", "for": 0.6},
        {"at": 3.9, "call": "report"}, {"at": 3.95, "shot": "car_enter_driving.png"},
        {"at": 4.5, "key": "f"}, {"at": 4.8, "call": "report"}, {"at": 4.85, "dump": "ce_out.json"},
        {"at": 4.9, "shot": "car_enter_out.png"}, {"at": 6.0, "call": "report"}, {"at": 6.1, "close": True}])
    clean_exit(c, r)
    reps = car_reports(r)
    far, near, inside, out = (r.dumps.get(n, {}) for n in ("ce_far.json", "ce_near.json", "ce_in.json", "ce_out.json"))
    hint = lambda d: (d.get("interact") or {}).get("hint")
    c.check(len(reps) == 5 and not reps[0]["in"] and reps[0]["ins"] == 0 and hint(far) is None,
            "far from the car there's no hint, and F does nothing", (reps[:1], hint(far)))
    c.check(hint(near) == "F: Get in", 'next to its door the hint says "F: Get in"', hint(near))
    c.check(len(reps) > 1 and reps[1]["in"] and reps[1]["driven"] and reps[1]["ins"] == 1 and inside.get("player_shown") is False
            and hint(inside) == "F: Get out",
            "F gets in: player:in_car() and car:driven() are true, car:on_enter ran, the figure is hidden, and the hint says F: Get out",
            (reps[1:2], inside.get("player_shown"), hint(inside)))
    c.check(len(reps) > 2 and reps[2]["car"][2] < -6 and math.dist(reps[2]["car"][::2], reps[2]["player"][::2]) < 0.2,
            "W drives it (the car's way forward), and player:spot() goes with the car", reps[2:3])
    c.check(len(reps) > 3 and not reps[3]["in"] and not reps[3]["driven"] and reps[3]["outs"] == 1 and out.get("player_shown") is True,
            "F again gets out: car:on_exit ran, player:in_car() is false, and the figure is back", (reps[3:4], out.get("player_shown")))
    gap = math.dist(reps[3]["car"][::2], reps[3]["player"][::2]) if len(reps) > 3 else None
    c.check(gap is not None and 1.5 < gap < 3.2, f"the player gets out beside the car ({gap and round(gap, 2)} m from its middle)", reps[3:4])
    c.check(len(reps) > 4 and math.dist(reps[3]["car"], reps[4]["car"]) < 0.3, "the car stays parked where it was left", reps[3:])
    shot = r.shots.get("car_enter_driving.png")
    c.check(shot and color_share(shot, (53, 116, 240), 60, (0.3, 0.35, 0.7, 0.8)) > 0.02, "the camera follows the blue car while it drives", shot)

    # A game that uses F itself keeps it: its own F gets in and out with car:drive (tgame's F doesn't undo it in the
    # same frame), and car:on_enter runs for car:drive() too.
    r = play("car_own_f", game("car_own_f.tuf"), [
        {"at": 0.6, "key": "f"}, {"at": 0.9, "call": "report"}, {"at": 0.95, "dump": "cf_in.json"},
        {"at": 1.2, "key": "f"}, {"at": 1.5, "call": "report"}, {"at": 1.55, "dump": "cf_out.json"}, {"at": 1.8, "close": True}])
    clean_exit(c, r)
    own = [line for line in r.lines if line.startswith("own in")]
    c.check(own == ["own in true ins 1", "own in false ins 1"], "the game's own F gets in and out (and on_enter ran for car:drive())", own)
    c.check((r.dumps.get("cf_in.json", {}).get("interact") or {}).get("driving") is True, "it's driving after the game's own F", r.dumps.get("cf_in.json", {}).get("interact"))


def t_weight(c):
    """Things weigh what they are (1.3.0): thing:weight() gives it (and sets it), the same push sends a light box off and
    hardly moves a heavy one, and the player shoves a crate out of its way but can't move a big stone box."""
    r = play("weight", game("weight.tuf"), [
        {"at": 0.8, "call": "report"}, {"at": 0.85, "call": "kick"}, {"at": 2.3, "call": "report"},
        {"at": 2.4, "hold": "w", "for": 1.4}, {"at": 4.0, "call": "report"},
        {"at": 4.1, "call": "to_stone"}, {"at": 4.4, "hold": "w", "for": 1.4}, {"at": 6.0, "call": "report"},
        {"at": 6.2, "close": True}])
    clean_exit(c, r)
    weights = said(r, "weights")
    c.check(weights == ["weights", "6.25", "200", "25", "400", "1200", "70", "70"],
            "a 0.5 m box weighs 6.25 kg (50 kg a cubic metre), one set to 200 is 200, a crate 25, a 2 m box 400, a car 1200, a ragdoll and the player 70",
            weights)
    spots = []
    for line in r.lines:
        m = re.match(r"light \[(.*?)\] heavy \[(.*?)\] crate \[(.*?)\] stone \[(.*?)\] player \[(.*?)\]", line)
        if m:
            spots.append([[float(v) for v in m[i].split(",")] for i in range(1, 6)])
    c.check(len(spots) == 4, "four reports", r.lines[-6:])
    if len(spots) == 4:
        moved = lambda i, a, b: math.dist(spots[a][i], spots[b][i])
        c.check(moved(0, 0, 1) > 3 and moved(1, 0, 1) < 0.4,
                f"the same push sends the light box {moved(0, 0, 1):.2f} m and the 200 kg one {moved(1, 0, 1):.2f} m", spots[:2])
        c.check(moved(2, 1, 2) > 1.5, f"walking into the crate shoves it {moved(2, 1, 2):.2f} m", (spots[1][2], spots[2][2]))
        c.check(moved(3, 2, 3) < 0.6 and spots[3][4][2] > -1.8,
                f"the 400 kg stone box hardly moves ({moved(3, 2, 3):.2f} m): it stops the player", (spots[2][3], spots[3][3], spots[3][4]))


def t_sign_text(c):
    """A sign's words are written on its board (1.3.0), on both sides, as big as fit (a long one wraps onto more
    lines): a 'writing' in the page, no label over it (other things' labels still float), and new words redraw it."""
    page = ("const live = [...tv.objs.values()].filter((n) => n.obj && !n.dead);"
            "tv.emit('tg-autopilot', {message: 'writing ' + JSON.stringify(live.filter((n) => n.type === 'writing').map((n) => n.p.text))"
            " + ' labels ' + live.filter((n) => n.type === 'label').length})")
    r = play("sign_text", game("sign_text.tuf"), [
        {"at": 0.7, "js": page}, {"at": 0.8, "shot": "sign_text.png"}, {"at": 0.9, "call": "change"}, {"at": 1.1, "js": page},
        {"at": 1.2, "call": "behind"}, {"at": 1.45, "shot": "sign_text_back.png"}, {"at": 1.7, "close": True}])
    clean_exit(c, r)
    pages = [line[len("[autopilot] "):] for line in r.lines if line.startswith("[autopilot] writing ")]
    c.check(len(pages) == 2 and pages[0] == 'writing ["SHOP","Welcome to Tuff Town, population 3","Open"] labels 1',
            "each sign's words are written on its board, and only the crate's label floats", pages[:1])
    c.check(len(pages) == 2 and pages[1].startswith('writing ["SHOP","Welcome to Tuff Town, population 3","Closed"]'),
            "sign:label with new words writes them on the board", pages[1:])
    for name, side in (("sign_text.png", "front"), ("sign_text_back.png", "back")):
        shot = r.shots.get(name)
        dark = shot and color_share(shot, (58, 36, 20), 34, (0.2, 0.25, 0.8, 0.55))
        c.check(shot and dark > 0.01, f"the letters show on the boards from the {side} ({dark and round(dark, 3)} of it)", shot)


def t_people_style(c):
    """People dressed in code (1.3.0): a person, a ragdoll and the player in third person get a shirt, trousers, skin,
    hair (a style and a colour), shoes and sleeves, and change them while the game runs; only people have clothes."""
    r = play("people_style", game("people_style.tuf"), [
        {"at": 0.7, "shot": "people_style.png"}, {"at": 0.8, "dump": "ps_before.json"}, {"at": 0.85, "call": "restyle"},
        {"at": 1.2, "shot": "people_style_after.png"}, {"at": 1.25, "dump": "ps_after.json"},
        {"at": 1.3, "tuff": 'world:box(0, 0, 9, 1, "red"):shirt("blue")'}, {"at": 1.7, "close": True}])
    first, after = r.shots.get("people_style.png"), r.shots.get("people_style_after.png")
    # Their shirts, behind the player, in the light they're in: red, blue, then purple and yellow.
    left, right = (0.43, 0.42, 0.48, 0.5), (0.52, 0.42, 0.565, 0.5)
    red, blue, purple, yellow = (150, 50, 50), (35, 75, 150), (90, 60, 155), (140, 100, 12)
    c.check(first and color_share(first, red, 45, left, 1) > 0.012 and color_share(first, blue, 45, right, 1) > 0.012,
            "the person wears its red shirt and the ragdoll its blue one", first)
    c.check(after and color_share(after, purple, 45, left, 1) > 0.05 and color_share(after, red, 45, left, 1) < 0.03
            and color_share(after, yellow, 45, right, 1) > 0.012,
            "restyled while it runs: the person's shirt is purple now, and the ragdoll's yellow", after)
    before_n, after_n = [len((r.dumps.get(n, {}).get("page") or {}).get("objs") or []) or r.dumps.get(n, {}).get("view_nodes")
                         for n in ("ps_before.json", "ps_after.json")]
    c.check(before_n and after_n and abs(before_n - after_n) < 12, f"the old clothes go when new ones come ({before_n} -> {after_n} objects)",
            (before_n, after_n))
    c.check(any("Only people have clothes and hair" in line for line in r.lines + r.err.splitlines()),
            "a box's shirt says only people have clothes", r.lines[-3:])


def t_physics_2d(c):
    """2D physics: a ball bounces on a static floor and its on_hit runs, a box lands on the floor, a line falls flat,
    a push sends the ball up, a ball that shakes as it flies up keeps flying, and the window's edges are walls."""
    r = play("physics_2d", game("physics_2d.tuf"), [
        {"at": 1.5, "call": "launch"}, {"at": 1.6, "call": "shake_it"}, {"at": 2.4, "dump": "p2_shake.json"},
        {"at": 3.0, "call": "report"}, {"at": 3.05, "dump": "p2_rest.json"}, {"at": 3.1, "shot": "physics_2d.png"},
        {"at": 3.2, "call": "kick"}, {"at": 3.25, "tuff": "box:push(9000, 0)"},
        {"at": 3.6, "call": "report"}, {"at": 4.6, "dump": "p2_wall.json"},
        {"at": 4.8, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    rest = r.dumps.get("p2_rest.json", {})
    c.check((page_physics(rest) or {}).get("dim") == 2, "the page loads 2D physics (rapier2d)", page_physics(rest))
    balls = [line.split() for line in r.lines if line.startswith("ball ")]
    c.check(balls and int(balls[0][-1]) >= 2, f"the ball bounces on the floor: its on_hit ran {balls and balls[0][-1]} times, "
            "with the floor", balls)
    box = (bodies(rest, "box") or [None, None])
    c.check(len(box) == 2 and abs(box[1][2] - 530) < 2 and abs(box[1][3]) < 2, "the box lands flat on the floor (y 530)", box)
    line = (bodies(rest, "line") or [None])[0]
    c.check(line and abs(line[2] - 558) < 3, "a line falls and lies on the floor", line)
    shaker = ([b for b in bodies(r.dumps.get("p2_shake.json", {}), "circle") if abs(b[1] - 80) < 5] or [None])[0]
    c.check(shaker and shaker[2] < 250, f"a ball sent flying up that shakes keeps flying (the shake is only drawn): it's high up "
            f"(y {shaker and shaker[2]}), not held back and dropped", shaker)
    ys = [float(b[2].strip("[],")) for b in balls]
    c.check(len(ys) == 2 and ys[1] < ys[0] - 50, f"ball:push(200, -300) sends it up (y {ys})", balls)
    wall = (bodies(r.dumps.get("p2_wall.json", {}), "box") or [None, None])
    c.check(len(wall) == 2 and 620 < wall[1][1] <= 771 and abs(wall[1][2] - 530) < 2,
            f"game:walls(true): a box pushed hard bounces off the window's edge and stays on the floor (x {wall[1] and wall[1][1]})", wall)
    shot = r.shots.get("physics_2d.png")
    c.check(shot and color_share(shot, hexrgb("#f97316"), 30) > 0.003 and color_share(shot, hexrgb("#e5484d"), 30) > 0.001,
            "the screenshot shows the ball and the box", shot)


def t_physics_off(c):
    """A game that never uses physics never loads it (no Rapier in its page), and Tuff Engine's preview (--scene)
    keeps the physics settings without simulating anything."""
    r = play("physics_off_3d", game("hud_3d.tuf"), [{"at": 0.8, "dump": "physics_off_3d.json"}, {"at": 0.9, "close": True}])
    d = r.dumps.get("physics_off_3d.json", {})
    c.check(r.code == 0 and "page" in d and page_physics(d) is None and d.get("physics") is None,
            "a 3D world without physics doesn't load Rapier", (r.code, page_physics(d)))
    r = play("physics_off_2d", game("snake.tuf"), [{"at": 0.5, "dump": "physics_off_2d.json"}, {"at": 0.6, "close": True}])
    d = r.dumps.get("physics_off_2d.json", {})
    c.check(r.code == 0 and "page" in d and page_physics(d) is None, "nor does a 2D game", (r.code, page_physics(d)))
    for name, want in (("physics_2d.tuf", {"floor": ("static", None, None), "ball": ("dynamic", None, 0.8), "box": ("dynamic", 3, None)}),
                       ("physics_drop.tuf", {"crate": ("dynamic", 2, None), "ball": ("dynamic", None, 0.7)})):
        code, _out, err, dump, _secs = scene(game(name))
        things = {t.get("var"): t for t in dump.get("things") or []}
        got = {v: things.get(v, {}).get("physics") for v in want}
        ok = all(g and (g["kind"], g["mass"], g["bounce"]) == w for g, w in zip(got.values(), want.values()))
        c.check(code == 0 and ok, f"--scene {name}: things have their physics settings", got)
        sent = [cmd for cmd in dump.get("batch") or [] if (cmd[0] == "k" and cmd[2] == "physics")
                or (cmd[0] in ("c", "s") and isinstance(cmd[-1], dict) and "phys" in cmd[-1])]
        c.check(code == 0 and not sent, f"--scene {name}: nothing for physics is sent (the preview doesn't simulate)", sent[:3])
        start = things.get("crate") or things.get("ball") or {}
        c.check(start.get("y") in (6, 100), f"--scene {name}: things are where the code puts them", start.get("y"))


# ---------------------------------------------------------------- effects: slow motion, a shake, pop text, weather, the time of day

def mean_rgb(path, box=(0, 0, 1, 1), step=4):
    """The average color (r, g, b) in box=(x0, y0, x1, y1), as fractions of the picture."""
    try:
        w, h, get = png_rgb(path)
    except Exception:
        return (0, 0, 0)
    px = [get(x, y) for y in range(int(box[1] * h), int(box[3] * h), step) for x in range(int(box[0] * w), int(box[2] * w), step)]
    return tuple(round(sum(p[k] for p in px) / max(1, len(px))) for k in range(3))


def greyness(rgb):
    return max(rgb) - min(rgb)  # 0 for grey, more the more colourful


def fx_of(d):
    return d.get("effects") or {}


def reports(r, start="at "):
    """The game's report lines ("at 1.2 ticks 3 slider ...") as dicts of their numbers."""
    out = []
    for line in r.lines:
        if line.startswith(start):
            words = line.split()
            out.append({words[i]: float(words[i + 1]) for i in range(0, len(words) - 1, 2)})
    return out


def t_fx_slow_mo(c):
    """Slow motion: world:slow_mo(0.3, 2) slows the game clock, its timers, things that glide by themselves and physics
    to 30% for 2 s, then it eases back; slow_mo(0.5) with no seconds lasts until slow_mo(1); pausing holds the slow
    motion's time; a speed out of range is a kid-friendly error. Models that move by themselves move as smoothly in slow
    motion."""
    r = play("fx_slow_mo", game("fx_slow_mo.tuf"), [
        {"at": 0.5, "call": "report"}, {"at": 0.55, "dump": "fxs_start.json"},
        {"at": 0.6, "call": "slow"}, {"at": 0.9, "call": "report"}, {"at": 0.95, "dump": "fxs_slow1.json"},
        {"at": 1.9, "call": "report"}, {"at": 1.95, "dump": "fxs_slow2.json"},
        {"at": 3.5, "call": "report"}, {"at": 3.55, "dump": "fxs_back1.json"},
        {"at": 4.5, "call": "report"}, {"at": 4.55, "dump": "fxs_back2.json"},
        {"at": 4.6, "call": "forever"}, {"at": 6.0, "dump": "fxs_forever.json"},
        {"at": 6.1, "call": "normal"}, {"at": 7.0, "dump": "fxs_normal.json"},
        {"at": 7.1, "tuff": "world:slow_mo(0.3, 5)"}, {"at": 7.2, "tuff": "world:pause()"}, {"at": 7.4, "dump": "fxs_pause1.json"},
        {"at": 8.4, "dump": "fxs_pause2.json"}, {"at": 8.5, "tuff": "world:resume()"},
        {"at": 8.6, "tuff": "world:slow_mo(0)"}, {"at": 8.7, "tuff": "world:shake(5)"},
        {"at": 8.8, "close": True}])
    first_line_is_notice(c, r)
    c.check(r.code == 0 and "Traceback" not in r.err, f"it ran and closed by itself (exit {r.code}, {r.seconds:.1f} s)", r.err[-800:])
    rep = reports(r)
    c.check(len(rep) == 5, "the game reported five times", r.lines)
    if len(rep) == 5:
        normal, slow, back = rep[0]["at"], rep[2]["at"] - rep[1]["at"], rep[4]["at"] - rep[3]["at"]
        c.check(0.22 <= slow <= 0.42, f"in slow motion the game clock goes about 0.3 s a second ({slow:.2f})", rep)
        c.check(0.85 <= back <= 1.15, f"after 2 s it's back to normal speed ({back:.2f} s a second)", rep)
        c.check(normal > 0.35, "before it, the clock went at normal speed", rep[0])
        ticks = rep[2]["ticks"] - rep[1]["ticks"]
        c.check(ticks <= 2, f"a timer every 0.25 s ran {ticks:.0f} times in that slow second (not 4)", rep)
        slid, slid_back = rep[2]["slider"] - rep[1]["slider"], rep[4]["slider"] - rep[3]["slider"]
        c.check(0 < slid < slid_back * 0.5, f"a box gliding by itself slowed down too ({slid:.2f} m, then {slid_back:.2f} m a second)", rep)
        fell, fell_back = rep[1]["ball"] - rep[2]["ball"], rep[3]["ball"] - rep[4]["ball"]
        c.check(0 < fell < fell_back * 0.5, f"so did a ball falling with physics ({fell:.2f} m, then {fell_back:.2f} m a second)", rep)
    s1, s2 = fx_of(r.dumps.get("fxs_slow1.json", {})), fx_of(r.dumps.get("fxs_slow2.json", {}))
    c.check(abs(s1.get("speed", 0) - 0.3) < 0.02 and (s1.get("page") or {}).get("speed") == s1.get("speed"),
            "the game's speed is 0.3, in tgame and in the page (physics and animation use its clock)", s1)
    p1, p2 = page_physics(r.dumps.get("fxs_slow1.json", {})) or {}, page_physics(r.dumps.get("fxs_slow2.json", {})) or {}
    steps = (p2.get("steps") or 0) - (p1.get("steps") or 0)
    c.check(8 <= steps <= 30, f"physics took {steps} steps of 1/60 s in that second (about 18, not 60)", (p1, p2))
    c.check(fx_of(r.dumps.get("fxs_back2.json", {})).get("speed") == 1 and s2.get("slow"),
            "slow motion ends by itself after its seconds", (s2, fx_of(r.dumps.get("fxs_back2.json", {}))))
    c.check(fx_of(r.dumps.get("fxs_forever.json", {})).get("speed") == 0.5, "slow_mo(0.5) with no seconds keeps going",
            fx_of(r.dumps.get("fxs_forever.json", {})))
    c.check(fx_of(r.dumps.get("fxs_normal.json", {})).get("speed") == 1, "and slow_mo(1) ends it", fx_of(r.dumps.get("fxs_normal.json", {})))
    a, b = fx_of(r.dumps.get("fxs_pause1.json", {})), fx_of(r.dumps.get("fxs_pause2.json", {}))
    c.check(a.get("slow") and a.get("slow") == b.get("slow") and (b.get("page") or {}).get("paused"),
            "while the game is paused, slow motion's seconds wait too", (a.get("slow"), b.get("slow")))
    c.check(any(":slow_mo needs a speed from 0.05 to 1 (0.3 is 30%, 1 is normal speed), like world:slow_mo(0.3, 2)." in line for line in r.lines),
            "world:slow_mo(0) says what speeds it takes", r.lines[-4:])
    c.check(any(":shake needs a strength from 0 to 2" in line for line in r.lines), "world:shake(5) says what strengths it takes", r.lines[-4:])

    r = play("fx_slow_sway", game("fx_slow_sway.tuf"), [
        {"at": 1.0, "mark": True}, {"at": 3.0, "dump": "fxs_sway.json"}, {"at": 3.1, "tuff": "world:slow_mo(0.2)"},
        {"at": 3.3, "mark": True}, {"at": 5.3, "dump": "fxs_sway_slow.json"}, {"at": 5.4, "close": True}])
    clean_exit(c, r)
    rate = lambda d: round((d.get("page") or {}).get("draws", 0) / max(0.001, (d.get("page") or {}).get("seconds", 1)), 1)
    normal, slow = rate(r.dumps.get("fxs_sway.json", {})), rate(r.dumps.get("fxs_sway_slow.json", {}))
    c.check(normal > 25 and slow > normal * 0.75 and fx_of(r.dumps.get("fxs_sway_slow.json", {})).get("speed") == 0.2,
            f"in slow motion a swaying tree and a breathing person move as smoothly as before: the page draws them {slow} "
            f"times a second ({normal} at normal speed)", (normal, slow))


def t_fx_shake_pop(c):
    """world:shake shakes the camera for its seconds and stops; world:pop_text floats text up from a thing or a spot,
    on top of everything, and it's gone after about a second (it waits while the game is paused)."""
    r = play("fx_shake_pop", game("fx_shake_pop.tuf"), [
        {"at": 0.5, "shot": "fx_still1.png"}, {"at": 0.55, "shot": "fx_still2.png"},
        {"at": 0.6, "call": "boom"}, {"at": 0.75, "shot": "fx_shake1.png"}, {"at": 0.8, "shot": "fx_shake2.png"},
        {"at": 0.85, "dump": "fx_shaking.json"},
        {"at": 1.9, "dump": "fx_shaken.json"}, {"at": 1.95, "shot": "fx_after1.png"}, {"at": 2.0, "shot": "fx_after2.png"},
        {"at": 2.1, "call": "got"}, {"at": 2.3, "shot": "fx_pop.png"}, {"at": 2.35, "dump": "fx_pops.json"},
        {"at": 3.6, "dump": "fx_popped.json"},
        {"at": 3.7, "call": "got"}, {"at": 3.75, "tuff": "world:pause()"}, {"at": 5.0, "dump": "fx_pop_paused.json"},
        {"at": 5.1, "tuff": "world:resume()"}, {"at": 6.6, "dump": "fx_pop_resumed.json"},
        {"at": 6.7, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    still = changed_pixels(r.shots.get("fx_still1.png"), r.shots.get("fx_still2.png"))
    shaking = changed_pixels(r.shots.get("fx_shake1.png"), r.shots.get("fx_shake2.png"))
    after = changed_pixels(r.shots.get("fx_after1.png"), r.shots.get("fx_after2.png"))
    c.check(shaking > max(2000, still * 5), f"world:shake moves the view ({shaking} pixels changed in 0.05 s, {still} without it)", (still, shaking))
    c.check(0 <= after < max(400, shaking * 0.1), f"and stops after its second ({after} pixels changed)", after)
    c.check((fx_of(r.dumps.get("fx_shaking.json", {})).get("page") or {}).get("shaking") == 1
            and (fx_of(r.dumps.get("fx_shaken.json", {})).get("page") or {}).get("shaking") == 0,
            "the page shakes it for that long", (fx_of(r.dumps.get("fx_shaking.json", {})), fx_of(r.dumps.get("fx_shaken.json", {}))))
    pop = r.shots.get("fx_pop.png")
    c.check(pop and color_share(pop, hexrgb(tuff_tgame_color("gold")), 40, (0.5, 0.1, 0.9, 0.7)) > 0.004,
            "the screenshot shows the gold +10 over the coin", pop)
    c.check(pop and color_share(pop, hexrgb(tuff_tgame_color("pink")), 40, (0.3, 0.0, 0.7, 0.6)) > 0.003,
            "and the pink text from a spot", pop)
    n = lambda name: (fx_of(r.dumps.get(name, {})).get("page") or {}).get("pops")
    c.check(n("fx_pops.json") == 3 and n("fx_popped.json") == 0, f"three pop texts float up and are gone after about a second ({n('fx_pops.json')}, then {n('fx_popped.json')})",
            (n("fx_pops.json"), n("fx_popped.json")))
    c.check(n("fx_pop_paused.json") == 3 and n("fx_pop_resumed.json") == 0, "while the game is paused they wait, then finish",
            (n("fx_pop_paused.json"), n("fx_pop_resumed.json")))


def tuff_tgame_color(name):
    import tuff_tgame
    return tuff_tgame.COLORS[name]


def t_fx_weather(c):
    """world:weather: rain falls (streaks) from a grey, darker sky into thicker fog and the ground looks wet; a
    stronger rain has more drops; snow drifts down from a pale sky; "none" clears it. Wrong weather names are
    caught with "did you mean", and a 2D game is told the weather needs a 3D world."""
    r = play("fx_weather", game("fx_weather.tuf"), [
        {"at": 0.5, "shot": "fx_weather_clear.png"},
        {"at": 0.6, "call": "rain"}, {"at": 1.2, "shot": "fx_weather_rain.png"}, {"at": 1.25, "dump": "fxw_rain.json"},
        {"at": 1.3, "call": "storm"}, {"at": 1.8, "shot": "fx_weather_storm.png"}, {"at": 1.85, "dump": "fxw_storm.json"},
        {"at": 1.9, "call": "snow"}, {"at": 2.6, "shot": "fx_weather_snow.png"}, {"at": 2.65, "dump": "fxw_snow.json"},
        {"at": 2.7, "call": "clear"}, {"at": 3.2, "shot": "fx_weather_after.png"}, {"at": 3.25, "dump": "fxw_clear.json"},
        {"at": 3.3, "call": "rain"}, {"at": 3.4, "tuff": 'world:sky "sunset"'}, {"at": 3.8, "shot": "fx_weather_rain_sunset.png"},
        {"at": 3.9, "tuff": 'world:weather("hail")'},
        {"at": 4.0, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    top = (0, 0, 1, 0.12)
    clear, rain, snow, after = (mean_rgb(r.shots.get(f"fx_weather_{k}.png", ""), top) for k in ("clear", "rain", "snow", "after"))
    c.check(greyness(clear) > 60 and clear[2] > clear[0] + 40, f"the clear sky is blue {clear}", clear)
    c.check(greyness(rain) < greyness(clear) * 0.5 and sum(rain) < sum(clear), f"in the rain it's greyer and darker {rain}", (clear, rain))
    c.check(greyness(snow) < greyness(clear) * 0.6 and sum(snow) > sum(rain), f"in the snow it's paler {snow}", (rain, snow))
    c.check(abs(sum(after) - sum(clear)) < 30, f"weather \"none\" brings the clear sky back {after}", (clear, after))
    w = lambda name: (fx_of(r.dumps.get(name, {})).get("page") or {})
    c.check(w("fxw_rain.json").get("weather") == ["rain"] and w("fxw_rain.json").get("drops") == 1700 and w("fxw_rain.json").get("wet") == [1],
            "rain: 1,700 drops fall around the camera and the ground is wet", w("fxw_rain.json"))
    c.check(w("fxw_storm.json").get("drops") == 3400, "rain at strength 2 has twice the drops", w("fxw_storm.json"))
    c.check(w("fxw_snow.json").get("weather") == ["snow"] and w("fxw_snow.json").get("wet") == [], "snow: flakes, and the ground dries",
            w("fxw_snow.json"))
    c.check(w("fxw_clear.json").get("weather") == [] and w("fxw_clear.json").get("drops") == 0, "\"none\" stops it", w("fxw_clear.json"))
    sunset = mean_rgb(r.shots.get("fx_weather_rain_sunset.png", ""), (0, 0.25, 1, 0.4))
    c.check(greyness(sunset) < 90, f"a sky picked while it rains is rainy too {sunset}", sunset)
    c.check(any('The weather can be "rain", "snow" or "none", not "hail".' in line for line in r.lines), "world:weather(\"hail\") says what it can be",
            r.lines[-3:])
    r = play("fx_weather_2d", game("pause_key.tuf"), [{"at": 0.3, "tuff": 'game:weather("rain")'}, {"at": 0.4, "close": True}])
    c.check(any("The weather needs a 3D world. Make the game with tgame.world(...) for rain or snow." in line for line in r.lines),
            "game:weather in a 2D game says it needs a 3D world", r.lines[-3:])


def t_fx_day(c):
    """world:time_of_day jumps to an hour (noon is blue, sunset is orange, midnight is dark with stars) and
    world:time_of_day() gives it back; world:day_cycle(4) goes round a whole day in 4 s (it waits while the game is
    paused) and day_cycle(0) stops it; world:sky picks a sky and stops the day."""
    r = play("fx_day", game("fx_day.tuf"), [
        {"at": 0.3, "call": "report"},
        {"at": 0.4, "call": "noon"}, {"at": 0.8, "shot": "fx_day_noon.png"},
        {"at": 0.9, "call": "sunset"}, {"at": 1.3, "shot": "fx_day_sunset.png"},
        {"at": 1.4, "call": "midnight"}, {"at": 1.8, "shot": "fx_day_night.png"}, {"at": 1.85, "dump": "fxd_night.json"},
        {"at": 1.9, "call": "report"},
        {"at": 2.0, "call": "fast"}, {"at": 3.0, "call": "report"}, {"at": 3.05, "dump": "fxd_fast.json"},
        {"at": 3.1, "call": "stop"}, {"at": 3.2, "call": "report"}, {"at": 4.2, "call": "report"},
        {"at": 4.3, "call": "pick"}, {"at": 4.4, "dump": "fxd_pick.json"}, {"at": 4.45, "call": "report"},
        {"at": 4.5, "call": "fast"}, {"at": 4.6, "tuff": "world:pause()"}, {"at": 4.7, "call": "report"}, {"at": 5.5, "call": "report"},
        {"at": 5.6, "tuff": "world:day_cycle(1)"}, {"at": 5.7, "tuff": "world:time_of_day(30)"},
        {"at": 5.8, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    hours = [float(line.split()[1]) for line in r.lines if line.startswith("hour ")]
    c.check(len(hours) == 8, "the game reported the hour eight times", hours)
    if len(hours) == 8:
        c.check(hours[0] == 9 and hours[1] == 0, f"time_of_day() gives the hour (9 for a day sky, then 0 at midnight) {hours[:2]}", hours)
        c.check(10.5 <= hours[2] <= 13.5, f"day_cycle(4) went from 6 to about noon in a second ({hours[2]})", hours)
        c.check(hours[3] == hours[4], f"day_cycle(0) stops the time where it is ({hours[3]}, a second later {hours[4]})", hours)
        c.check(hours[5] == 9, "world:sky(\"day\") picks the sky (and the day stops)", hours)
        c.check(abs(hours[6] - hours[7]) < 0.05, f"while the game is paused the day waits ({hours[6]}, then {hours[7]})", hours)
    noon, sunset, night = (r.shots.get(f"fx_day_{k}.png") for k in ("noon", "sunset", "night"))
    sky_noon, glow = mean_rgb(noon, (0, 0, 1, 0.12)), mean_rgb(sunset, (0, 0.28, 1, 0.38))
    c.check(sky_noon[2] > sky_noon[0] + 60, f"noon's sky is blue {sky_noon}", sky_noon)
    c.check(glow[0] > glow[2] + 30, f"sunset's sky glows orange by the horizon {glow}", glow)
    dark = mean_rgb(night, (0, 0, 1, 0.3))
    c.check(sum(dark) < 120, f"midnight is dark {dark}", dark)
    stars = color_share(night, (230, 235, 245), 60, (0, 0, 1, 0.3), step=1) if night else 0
    c.check(stars > 0.0005, f"with stars in it ({stars * 100:.2f}% of the sky)", stars)
    d = fx_of(r.dumps.get("fxd_night.json", {}))
    c.check(d.get("stars") == 1 and (d.get("page") or {}).get("stars") == [1], "the page shows its stars at full brightness", d)
    pick = fx_of(r.dumps.get("fxd_pick.json", {}))
    c.check(pick.get("hour") is None and pick.get("stars") == 0, "a sky picked has no stars", pick)
    c.check(any(":day_cycle needs how many seconds a whole day takes (2 or more)" in line for line in r.lines), "world:day_cycle(1) says what it takes", r.lines[-3:])
    c.check(any(":time_of_day needs an hour from 0 to 24 (18 is 6 pm)" in line for line in r.lines), "world:time_of_day(30) says what it takes", r.lines[-3:])


def t_fx_2d(c):
    """2D: game:slow_mo slows sprites that move by themselves and the clock, game:shake shakes the game (not its
    HUD), and game:pop_text floats text up from a spot or over a sprite, and it's gone after about a second."""
    r = play("fx_2d", game("fx_2d.tuf"), [
        {"at": 0.4, "call": "report"}, {"at": 1.4, "call": "report"},
        {"at": 1.5, "call": "slow"}, {"at": 1.7, "call": "report"}, {"at": 2.7, "call": "report"},
        {"at": 3.6, "call": "report"}, {"at": 4.6, "call": "report"},
        {"at": 4.7, "shot": "fx_2d_still.png"}, {"at": 4.8, "call": "boom"}, {"at": 4.95, "shot": "fx_2d_shake1.png"},
        {"at": 5.0, "shot": "fx_2d_shake2.png"}, {"at": 6.0, "shot": "fx_2d_after.png"},
        {"at": 6.1, "call": "pops"}, {"at": 6.3, "shot": "fx_2d_pop.png"}, {"at": 6.35, "dump": "fx2_pops.json"},
        {"at": 7.6, "dump": "fx2_popped.json"},
        {"at": 7.7, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    rep = reports(r)
    c.check(len(rep) == 6, "the game reported six times", r.lines)
    if len(rep) == 6:
        normal, slow, back = rep[1]["at"] - rep[0]["at"], rep[3]["at"] - rep[2]["at"], rep[5]["at"] - rep[4]["at"]
        c.check(0.9 <= normal <= 1.1 and 0.18 <= slow <= 0.35 and 0.9 <= back <= 1.1,
                f"the game clock goes 1 s a second, then about 0.25 in slow motion, then 1 again ({normal:.2f}, {slow:.2f}, {back:.2f})", rep)
    still, shake1, shake2 = r.shots.get("fx_2d_still.png"), r.shots.get("fx_2d_shake1.png"), r.shots.get("fx_2d_shake2.png")
    moved = changed_pixels(shake1, shake2, box=(0, 0.2, 1, 1))
    c.check(moved > 1500, f"game:shake moves the game ({moved} pixels changed in 0.05 s)", moved)
    hud = changed_pixels(still, shake1, box=(0.04, 0.02, 0.22, 0.1), step=1)
    c.check(0 <= hud < 40, f"but not its HUD ({hud} pixels of the score changed)", hud)
    pop = r.shots.get("fx_2d_pop.png")
    c.check(pop and color_share(pop, hexrgb(tuff_tgame_color("gold")), 40, (0.35, 0.3, 0.65, 0.55)) > 0.01,
            "the screenshot shows the gold +100 floating up", pop)
    p1, p2 = fx_of(r.dumps.get("fx2_pops.json", {})).get("pops"), fx_of(r.dumps.get("fx2_popped.json", {})).get("pops")
    c.check(p1 == 2 and p2 == 0, f"two pop texts, gone after about a second ({p1}, then {p2})", (p1, p2))
# ---------------------------------------------------------------- level pieces: jump pads, boost pads, moving platforms

def numbers_after(r, start):
    """The numbers in the last line the game said that starts with these words."""
    out = []
    for w in said(r, start)[len(start.split()):]:
        try:
            out.append(float(w.strip("[],")))
        except ValueError:
            pass
    return out


def autopilot_said(r, words):
    return [line for line in r.lines if line.startswith("[autopilot]") and words in line]


def light_share(path, box, step=3):
    """The share of pixels in a box that are much lighter than grass (red over 150 and green over 190)."""
    try:
        w, h, get = png_rgb(path)
    except Exception:
        return 0.0
    x0, y0, x1, y1 = box
    hits = total = 0
    for y in range(int(y0 * h), int(y1 * h), step):
        for x in range(int(x0 * w), int(x1 * w), step):
            p = get(x, y)
            total += 1
            hits += p[0] > 150 and p[1] > 190
    return hits / max(1, total)


def t_level_pads(c):
    """A jump pad launches the player up (power 15: about 5 m, with physics on) and a physics crate dropped on another
    one, a paused game launches nobody (resuming does), and a boost pad turned to face +x shoots the player that way.
    A pad in view glows at the game's speed (slower in slow motion), drawn about 60 times a second, not at the display's
    full rate. The Snowy obstacle course example's boost pad shoots the player down the course."""
    r = play("level_pads", game("level_pads.tuf"), [
        {"at": 0.5, "shot": "level_pads.png"},
        {"at": 0.6, "hold": "w", "for": 0.9},
        {"at": 2.6, "call": "report"},
        {"at": 2.7, "tuff": "world:pause()"}, {"at": 2.8, "tuff": "player:move_to(0, 0, 2)"}, {"at": 2.85, "call": "reset"},
        {"at": 3.3, "dump": "lp_paused.json"},
        {"at": 3.4, "tuff": "world:resume()"}, {"at": 3.8, "dump": "lp_resumed.json"},
        {"at": 4.6, "call": "to_boost"}, {"at": 4.72, "shot": "level_pads_boost.png"},
        {"at": 6.2, "call": "report"}, {"at": 6.25, "dump": "lp_end.json"},
        {"at": 6.4, "close": True}])
    clean_exit(c, r)
    first = [line.split() for line in r.lines if line.startswith("peak ")]
    peak = float(first[0][1]) if first else 0
    c.check(4.6 < peak < 6, f"walking onto a jump pad (power 15) launches the player about 5 m up (peak {peak})", first[:1])
    crate = float(first[-1][4]) if first else 0
    c.check(crate > 4.2, f"a physics crate dropped on a jump pad (power 10) is launched up too (it fell from 3, got to {crate})", first[-1:])
    paused, resumed = r.dumps.get("lp_paused.json", {}), r.dumps.get("lp_resumed.json", {})
    py0, py1 = (paused.get("player") or [0, 9])[1], (resumed.get("player") or [0, 0])[1]
    c.check(paused.get("paused") and py0 < 0.3, f"in a paused game a jump pad launches nobody (the player stays at y {py0})", paused.get("player"))
    c.check(py1 > 1.5, f"... and once it's resumed, it does (y {py1})", resumed.get("player"))
    end = numbers_after(r, "player")
    c.check(len(end) == 3 and end[0] > 3 and abs(end[2] + 4) < 1,
            f"a boost pad turned to face +x shoots the player along +x (from x -6 to {end[:1]})", end)
    shot = r.shots.get("level_pads.png")
    c.check(shot and color_share(shot, (60, 235, 170), 70, (0.3, 0.55, 0.7, 1)) > 0.004,
            "the screenshot shows the jump pad glowing green", shot)
    c.check(shot and color_share(shot, (255, 140, 40), 70, (0, 0.45, 0.5, 0.8)) > 0.0008,
            "... and the boost pad glowing orange", shot)
    boosted = r.shots.get("level_pads_boost.png")
    c.check(boosted and light_share(boosted, (0, 0.62, 1, 1), step=1) > 0.0005,  # plain grass there has none
            "boosted, the screen streaks: light speed lines over the grass at its edges", boosted)

    r = play("level_pad_idle", game("level_pad_idle.tuf"), [
        {"at": 1.0, "mark": True}, {"at": 1.05, "dump": "lpi_start.json"}, {"at": 3.0, "dump": "lpi_normal.json"},
        {"at": 3.05, "tuff": "world:slow_mo(0.2)"}, {"at": 3.2, "mark": True}, {"at": 3.25, "dump": "lpi_slow1.json"},
        {"at": 5.25, "dump": "lpi_slow2.json"}, {"at": 5.4, "close": True}])
    clean_exit(c, r)
    page = lambda name: r.dumps.get(name, {}).get("page") or {}
    rate = lambda name: round(page(name).get("draws", 0) / max(0.001, page(name).get("seconds", 1)), 1)
    clock = lambda name: ((page(name).get("level") or {}).get("pads") or [0])[0]
    c.check(rate("lpi_normal.json") <= 80 and rate("lpi_slow2.json") <= 80,
            f"a jump pad in view glows and its rings rise about 60 times a second, not at a fast screen's full rate (the page "
            f"draws {rate('lpi_normal.json')} times a second, {page('lpi_normal.json').get('fps', 0):.0f} frames)",
            (page("lpi_normal.json"), page("lpi_slow2.json")))
    normal, slow = clock("lpi_normal.json") - clock("lpi_start.json"), clock("lpi_slow2.json") - clock("lpi_slow1.json")
    c.check(1.5 < normal < 2.3 and 0.2 < slow < 0.7,
            f"... at the game's speed: in 2 s its glow goes on {normal:.2f} s, and {slow:.2f} s in slow motion (0.2)", (normal, slow))
    # The Snowy obstacle course example (TUFF_GAME_EXAMPLES) runs towards -z: start, jump pad, ledge, lift, key, door,
    # chest. Its boost pad, on the ledge, shoots the player along it towards the lift, not back off its front edge.
    course = next((g for g in game_examples() or [] if g["id"] == "snow_course"), None)
    if course is None:
        c.check(game_examples() is None, "the examples have the Snowy obstacle course", None)
        return
    path = os.path.join(OUT, "snow_course.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(course["code"])
    r = play("snow_course", path, [
        {"at": 1.0, "tuff": 'say "pad " + boost:spot()'}, {"at": 1.05, "tuff": "player:move_to(boost:x(), boost:y() + 0.05, boost:z())"},
        {"at": 1.65, "tuff": 'say "boosted " + player:spot()'}, {"at": 1.8, "close": True}])
    clean_exit(c, r)
    pad, boosted = numbers_after(r, "pad"), numbers_after(r, "boosted")
    ledge = (-17, -11)  # game:box(0, 0, -14, [8, 3, 6]): from z -17 to -11
    c.check(len(pad) == 3 and ledge[0] + 1.6 <= pad[2] <= ledge[1] - 1.6, f"its boost pad is all on the ledge (z {pad[2:]})", pad)
    c.check(len(pad) == 3 and len(boosted) == 3 and boosted[2] < pad[2] - 4 and abs(boosted[0] - pad[0]) < 1,
            f"... and shoots the player along it towards the lift (-z: from z {pad[2:]} to {boosted[2:]})", (pad, boosted))


def t_level_lift(c):
    """thing:path: a lift goes along its path and back (ping-pong) with the player standing on it, across and up and
    down, never falling through or sliding off; a platform goes round its spots (loop); path() stops one where it is;
    a path to one spot goes there and stays; and a path with the wrong inputs says what's wrong. With physics on, a crate
    rides it too, and the player riding it pushes a physics crate on it by walking into it."""
    r = play("level_lift", game("level_lift.tuf"), [
        {"at": 2.0, "call": "stop_it"}, {"at": 3.0, "dump": "ll_stopped.json"},
        {"at": 3.5, "tuff": "lift:path(5, 3)"}, {"at": 3.55, "tuff": "lift:path([[1, 2]], 0)"},
        {"at": 3.6, "tuff": "lift:path([[1, 2, 3]], 2, \"zigzag\")"},
        {"at": 5.4, "shot": "level_lift.png"},
        {"at": 8.6, "call": "report"}, {"at": 8.65, "dump": "ll_end.json"}, {"at": 8.8, "close": True}])
    clean_exit(c, r)
    gap = numbers_after(r, "gap")
    c.check(len(gap) == 3 and gap[0] > -0.05 and gap[1] < 0.05,
            f"the player rides the lift across, up and back down without sinking into it or lifting off it (gap {gap[:2]})", gap)
    c.check(len(gap) == 3 and gap[2] < 0.05, f"... and moves along with it, staying where it stood on it (drift {gap[2:]})", gap)
    c.check(said(r, "lift seen")[2:] == ["[0,", "1,", "2,", "1]"], "the lift goes to each spot, then back (ping-pong)", said(r, "lift seen"))
    c.check(said(r, "ring seen")[2:] == ["[0,", "1,", "2,", "3,", "0]"], "the loop platform goes round its spots, back to the first", said(r, "ring seen"))
    stopped, still = numbers_after(r, "stopped at"), numbers_after(r, "stopper")
    c.check(len(stopped) == 3 and 7 < stopped[0] < 13 and stopped == still, f"path() stops it where it is (x {stopped[:1]}, later {still[:1]})",
            (stopped, still))
    slide = numbers_after(r, "slide")
    c.check(slide == [-10, 0, 6], "a path to one spot goes there and stays", slide)
    c.check(autopilot_said(r, "box:path needs a list of spots to go to, like box:path([[0, 2, 0], [10, 2, 0]], 3)."),
            "lift:path(5, 3) says it needs a list of spots", r.lines[-8:])
    c.check(autopilot_said(r, "box:path needs a speed above 0 (metres a second)"), "a speed of 0 says it needs one above 0", r.lines[-8:])
    c.check(autopilot_said(r, 'A path can go "ping-pong" (there and back again) or "loop"'), "a mode it doesn't know says the two it can be",
            r.lines[-8:])
    shot = r.shots.get("level_lift.png")
    c.check(shot and color_share(shot, hexrgb("#9a9a92"), 40, (0.2, 0.3, 0.8, 1)) > 0.03 and color_share(shot, (40, 85, 170), 45) > 0.001,
            "the screenshot shows the player (blue) riding the stone lift", shot)

    # The crate on the lift as the page draws it, every display frame: how far it sinks into it or lifts off it, from
    # where it sat at the start. (Python's crate:y() comes from a physics report a frame or two old, while lift:y() is
    # now, so in Python a rising lift seems to have the crate a few centimetres sunk into it.) The lift is drawn where
    # Python puts it, 60 times a second, and the crate smoothly by physics, so on a faster screen the two can be one
    # Python frame of the lift's move apart (2.5 m/s / 60: 4 cm, a little more when a Python frame is late); a
    # screenshot holds Python up for longer, so the crate is measured before the screenshot. A crate that bounced or
    # sank would be a good deal further off than that. The same goes for sliding along it.
    record = ("const ph = [...tv.objs.values()].filter((n) => n.phys && n.obj && !n.dead);"
              "const crate = ph.find((n) => n.phys.kind === 'dynamic'), lift = ph.find((n) => n.phys.kind === 'kinematic');"
              "const w = window.__llp = {low: 99, high: -99, slid: 0, frames: 0, found: !!(crate && lift)}; let d0 = null, x0 = null;"
              "const tick = () => { if (crate && lift) { const d = crate.obj.position.y - lift.obj.position.y;"
              " const dx = crate.obj.position.x - lift.obj.position.x; if (d0 === null) { d0 = d; x0 = dx; }"
              " w.low = Math.min(w.low, d - d0); w.high = Math.max(w.high, d - d0); w.slid = Math.max(w.slid, Math.abs(dx - x0)); w.frames++; }"
              " requestAnimationFrame(tick); }; requestAnimationFrame(tick);")
    r = play("level_lift_physics", game("level_lift_physics.tuf"), [
        {"at": 0.8, "js": record},
        {"at": 6.85, "js": "tv.emit('tg-autopilot', {message: 'drawn ' + JSON.stringify(window.__llp)})"},
        {"at": 6.9, "shot": "level_lift_physics.png"}, {"at": 7.0, "call": "report"}, {"at": 7.05, "dump": "llp_end.json"},
        {"at": 7.2, "close": True}])
    clean_exit(c, r)
    g = numbers_after(r, "gap")  # the player's lowest and highest over the lift's top, the crate's, how far the crate slid
    c.check(len(g) == 5 and g[0] > -0.05 and g[1] < 0.05, f"with physics on, the player rides it too (gap {g[:2]})", g)
    drawn = next((json.loads(line.split("drawn ", 1)[1]) for line in r.lines if line.startswith("[autopilot] drawn ")), {})
    c.check(drawn.get("found") and drawn.get("frames", 0) > 100 and drawn["low"] > -0.08 and drawn["high"] < 0.08,
            f"a physics crate on it rides along, across, up and back down, staying on its top as it's drawn: no bouncing "
            f"(from where it sat: {drawn.get('low', 0):.3f} to {drawn.get('high', 0):.3f} m in {drawn.get('frames')} frames)", drawn)
    c.check(drawn.get("slid", 1) < 0.12, f"... without sliding along it (it slid {drawn.get('slid', 0):.3f} m as it's drawn)", drawn)
    c.check(len(g) == 5 and g[2] > -0.2 and g[3] < 0.2 and g[4] < 0.3,
            f"... and in Python too, give or take a frame or two of the lift's move (y {g[2:4]}, slid {g[4:]})", g)
    shot = r.shots.get("level_lift_physics.png")
    c.check(shot and color_share(shot, (125, 80, 45), 50, (0.2, 0.2, 0.8, 0.9)) > 0.005, "the screenshot shows the crate on the lift", shot)

    r = play("level_lift_push", game("level_lift_push.tuf"), [
        {"at": 0.8, "call": "report"}, {"at": 1.0, "hold": "w", "for": 1.2}, {"at": 2.4, "call": "report"},
        {"at": 2.6, "close": True}])
    clean_exit(c, r)
    g = numbers_after(r, "player")  # the player's spot, the crate's and the lift's
    c.check(len(g) == 9 and g[5] < -3 and g[2] > g[5] + 0.5,
            f"riding a moving platform, the player walks into a physics crate on it and pushes it along (it went from z -2 "
            f"to {g[5:6]}, the player is behind it)", g)
    c.check(len(g) == 9 and g[6] > 0.5 and g[0] > 0.5, f"... and rides along with the platform (x {g[:1]}, the lift's {g[6:7]})", g)

    # A Python frame 0.2 s late as the platform slows down to stop: the page slows it down and stops it there itself,
    # rather than going on past the end and being pulled back (that jolt slid the crate 26 cm).
    r = play("level_lift_hitch", game("level_lift_hitch.tuf"), [
        {"at": 1.0, "call": "go"}, {"at": 6.5, "call": "report"}, {"at": 6.7, "close": True}])
    clean_exit(c, r)
    slid = numbers_after(r, "slid")  # how far the crate slid on it, where the lift stopped, where the crate is
    c.check(len(slid) == 3 and slid[1] == 8 and abs(slid[0]) < 0.15,
            f"a late frame as a platform stops doesn't jolt it: a physics crate on it slides {slid[:1]} m (it slid 0.26)", slid)


# ---------------------------------------------------------------- menus, buttons and screens (atgui on a game)

ACCENT = (59, 130, 246)  # atgui's blue: primary buttons, the start screen's hint
CARD = (23, 26, 31)      # atgui's dark surface: a screen's card


def ui_of(d):
    return d.get("ui") or {}


def screen_shown(d, title):
    return any(s["title"] == title and s["shown"] for s in ui_of(d).get("screens", []))


def preview_leaves_menus_out(c, name):
    """tuff.py --scene (Tuff Engine's preview) runs a game with menus without a crash, and leaves the menus out."""
    code, out, err, d, secs = scene(game(name))
    batch = json.dumps(d.get("batch", []))
    c.check(code == 0 and d.get("stopped") == "end" and d.get("error") is None and d.get("things"),
            f"tuff.py --scene previews {name} without errors ({len(d.get('things', []))} things, {secs:.1f} s)",
            (d.get("stopped"), d.get("error"), err[-300:]))
    c.check("at-" not in batch and "tg-" not in batch, "the preview leaves the menus out (no atgui elements in its batch)")


def t_ui_2d(c):
    """games/ui_2d.tuf: a start screen the autopilot clicks to enter, a panel button that changes the score (and isn't
    a click on the game), a shop screen that pauses the game, a name box whose keys don't move the player, and a game
    over screen with Play again and Main menu (then Enter starts again)."""
    r = play("ui_2d", game("ui_2d.tuf"), [
        {"at": 0.3, "hold": "right", "for": 0.4},
        {"at": 0.8, "dump": "ui2d_start.json"}, {"at": 0.9, "shot": "ui2d_start.png"},
        {"at": 1.0, "click_ui": "Click to play"},
        {"at": 1.2, "dump": "ui2d_playing.json"},
        {"at": 1.25, "hold": "right", "for": 0.4},
        {"at": 1.8, "dump": "ui2d_moved.json"},
        {"at": 1.9, "click_ui": "+1"}, {"at": 2.0, "click_ui": "+1"}, {"at": 2.1, "click_ui": "+1"},
        {"at": 2.2, "click": [700, 120]},
        {"at": 2.35, "dump": "ui2d_score.json"}, {"at": 2.4, "shot": "ui2d_panel.png"}, {"at": 2.45, "call": "report"},
        {"at": 2.5, "click_ui": "Shop"},
        {"at": 2.6, "hold": "right", "for": 0.4},
        {"at": 3.0, "dump": "ui2d_shop.json"}, {"at": 3.05, "shot": "ui2d_shop.png"},
        {"at": 3.1, "click_ui": "Faster (2)"},
        {"at": 3.2, "click_ui": "Close"},
        {"at": 3.4, "dump": "ui2d_closed.json"},
        {"at": 3.5, "click_ui": "Your name"},
        {"at": 3.6, "type": "dddd", "for": 0.5},
        {"at": 3.9, "dump": "ui2d_typing.json"},
        {"at": 4.2, "click": [700, 120]},
        {"at": 4.3, "hold": "d", "for": 0.3},
        {"at": 4.8, "dump": "ui2d_after.json"},
        {"at": 4.9, "call": "lose"},
        {"at": 5.3, "dump": "ui2d_over.json"}, {"at": 5.35, "shot": "ui2d_over.png"},
        {"at": 5.4, "click_ui": "Play again"},
        {"at": 5.6, "dump": "ui2d_again.json"},
        {"at": 5.7, "call": "lose"},
        {"at": 5.9, "click_ui": "Main menu"},
        {"at": 6.1, "dump": "ui2d_menu.json"},
        {"at": 6.2, "key": "enter"},
        {"at": 6.4, "dump": "ui2d_enter.json"}, {"at": 6.45, "call": "report"},
        {"at": 6.5, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = {k[5:-5]: v for k, v in r.dumps.items()}
    x = {k: (v.get("sprites") or [[None, None]])[0][1] for k, v in d.items()}  # the player is the first sprite made
    start = d.get("start", {})
    c.check(screen_shown(start, "Star Catcher") and start.get("paused") and start.get("time") == 0 and x.get("start") == 400,
            "the start screen shows over the game, which waits: time 0, and holding right doesn't move the player",
            (ui_of(start).get("screens"), start.get("paused"), start.get("time"), x.get("start")))
    playing = d.get("playing", {})
    c.check(not screen_shown(playing, "Star Catcher") and playing.get("paused") is False,
            "clicking it (click_ui \"Click to play\") hides it and the game runs", ui_of(playing).get("screens"))
    c.check((x.get("moved") or 0) > 440, f"then the player moves (x {x.get('moved')})", x.get("moved"))
    c.check("Stars: 3" in ui_of(d.get("score", {})).get("texts", []), "three clicks on the panel's +1 button set its heading to Stars: 3",
            ui_of(d.get("score", {})).get("texts"))
    c.check("stars 3, game clicks 1, starts 1" in r.lines, "the panel's clicks aren't the game's (1 game click: the one on the game)", r.lines)
    shop = d.get("shop", {})
    c.check(screen_shown(shop, "Shop") and shop.get("paused") and x.get("shop") == x.get("moved"),
            "the Shop button shows the shop, which pauses the game: holding right doesn't move the player",
            (ui_of(shop).get("screens"), shop.get("paused"), x.get("shop"), x.get("moved")))
    c.check(abs((shop.get("time") or 0) - (d.get("score", {}).get("time") or 0)) < 0.35, "and the game's clock waits",
            (d.get("score", {}).get("time"), shop.get("time")))
    closed = d.get("closed", {})
    c.check(not screen_shown(closed, "Shop") and closed.get("paused") is False and "Stars: 1" in ui_of(closed).get("texts", []),
            "buying in the shop spends 2 stars, and Close hides it and the game goes on", (ui_of(closed).get("texts"), closed.get("paused")))
    typing = d.get("typing", {})
    c.check(ui_of(typing).get("inputs") == ["dddd"] and x.get("typing") == x.get("closed") and typing.get("down") == [],
            "keys typed into the name box (D, held) go in the box and don't move the player",
            (ui_of(typing).get("inputs"), x.get("closed"), x.get("typing"), typing.get("down")))
    c.check((x.get("after") or 0) > (x.get("typing") or 0) + 20, "after a click on the game, D moves the player again", (x.get("typing"), x.get("after")))
    over = d.get("over", {})
    c.check(screen_shown(over, "Game over") and over.get("paused") and "Stars caught: 1" in ui_of(over).get("texts", []),
            "the game over screen shows the score and pauses the game", (ui_of(over).get("texts"), over.get("paused")))
    again = d.get("again", {})
    c.check(not screen_shown(again, "Game over") and again.get("paused") is False and x.get("again") == 400
            and "Stars: 0" in ui_of(again).get("texts", []), "Play again hides it and starts over", (ui_of(again).get("texts"), x.get("again")))
    c.check(screen_shown(d.get("menu", {}), "Star Catcher") and d.get("menu", {}).get("paused"),
            "Main menu shows the start screen again", ui_of(d.get("menu", {})).get("screens"))
    enter = d.get("enter", {})
    c.check(not screen_shown(enter, "Star Catcher") and enter.get("paused") is False and r.lines[-1:] == ["stars 0, game clicks 2, starts 2"],
            "and Enter starts the game (start:clicked runs again)", (ui_of(enter).get("screens"), r.lines[-1:]))
    shots = r.shots
    c.check(shots.get("ui2d_start.png") and color_share(shots["ui2d_start.png"], ACCENT, 50, (0.38, 0.6, 0.62, 0.72)) > 0.2,
            "the start screen's picture has its hint, a blue button in the middle", shots.get("ui2d_start.png"))
    c.check(shots.get("ui2d_panel.png") and color_share(shots["ui2d_panel.png"], ACCENT, 40, (0.01, 0.09, 0.08, 0.17)) > 0.3,
            "the panel's +1 button is drawn at the top left, in atgui's blue", shots.get("ui2d_panel.png"))
    c.check(shots.get("ui2d_shop.png") and color_share(shots["ui2d_shop.png"], CARD, 12, (0.3, 0.3, 0.7, 0.7)) > 0.3,
            "the shop is a card in the middle (atgui's dark surface)", shots.get("ui2d_shop.png"))
    preview_leaves_menus_out(c, "ui_2d.tuf")


def t_ui_3d(c):
    """games/ui_3d.tuf, a first-person world: click to play (that click asks the page to lock the mouse), a panel
    button that changes the coins (once the mouse is let go: while it's locked, clicks are the game's), B opens a shop
    that pauses the world (no walking, no looking around, and the mouse is let go), buying changes the panel, W typed
    into the chat box doesn't walk, Escape shows a pause menu."""
    r = play("ui_3d", game("ui_3d.tuf"), [
        {"at": 0.3, "hold": "w", "for": 0.4},
        {"at": 0.9, "dump": "ui3d_start.json"}, {"at": 1.2, "shot": "ui3d_start.png"},
        {"at": 1.3, "click_ui": "Click to play"},
        {"at": 1.5, "dump": "ui3d_playing.json"},
        {"at": 1.6, "hold": "w", "for": 0.5},
        {"at": 2.3, "dump": "ui3d_walked.json"},
        {"at": 2.32, "js": "document.exitPointerLock()"},  # the player lets go of the mouse, to use the panel
        {"at": 2.35, "click_ui": "Chop"}, {"at": 2.45, "click_ui": "Chop"}, {"at": 2.55, "click_ui": "Chop"},
        {"at": 2.8, "shot": "ui3d_panel.png"},
        {"at": 2.85, "lock": True},
        {"at": 2.9, "key": "b"},
        {"at": 3.1, "hold": "w", "for": 0.5},
        {"at": 3.2, "look": [300, 0]},
        {"at": 3.5, "shot": "ui3d_shop.png"},
        {"at": 3.8, "dump": "ui3d_shop.json"},
        {"at": 3.9, "click_ui": "Buy for 15"},
        {"at": 4.1, "click_ui": "Close"},
        {"at": 4.3, "dump": "ui3d_closed.json"},
        {"at": 4.35, "lock": False},
        {"at": 4.4, "click_ui": "Say something"},
        {"at": 4.5, "type": "w", "for": 0.6},
        {"at": 4.8, "dump": "ui3d_typing.json"},
        {"at": 5.3, "key": "escape"},
        {"at": 5.8, "shot": "ui3d_pause.png"}, {"at": 5.9, "dump": "ui3d_pause.json"},
        {"at": 6.0, "click_ui": "Resume"},
        {"at": 6.2, "dump": "ui3d_resumed.json"},
        {"at": 6.4, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = {k[5:-5]: v for k, v in r.dumps.items()}
    z = {k: (v.get("player") or [None] * 5)[2] for k, v in d.items()}
    start = d.get("start", {})
    c.check(screen_shown(start, "Chop! Chop!") and start.get("paused") and start.get("time") == 0 and z.get("start") == 0,
            "the start screen shows over the world, which waits: holding W doesn't walk",
            (ui_of(start).get("screens"), start.get("paused"), z.get("start")))
    playing = d.get("playing", {})
    c.check(not screen_shown(playing, "Chop! Chop!") and playing.get("paused") is False and ui_of(playing).get("lock_asks", 0) >= 1,
            "clicking it starts the game, and that same click asks the page to lock the mouse for looking around",
            (ui_of(playing).get("screens"), ui_of(playing).get("lock_asks"), playing.get("locked")))
    c.check((z.get("walked") or 0) < -1, f"then W walks (z {z.get('walked')})", z.get("walked"))
    c.check("Coins: 15" in ui_of(d.get("shop", {})).get("texts", []), "three clicks on the panel's Chop button make Coins: 15",
            ui_of(d.get("shop", {})).get("texts"))
    shop = d.get("shop", {})
    heading = lambda k: (d.get(k, {}).get("player") or [0] * 5)[3]
    c.check(screen_shown(shop, "Shop") and shop.get("paused") and z.get("shop") == z.get("walked") and heading("shop") == heading("walked"),
            "B shows the shop, which pauses the world: W doesn't walk and the mouse doesn't turn the player",
            (shop.get("paused"), z.get("walked"), z.get("shop"), heading("walked"), heading("shop")))
    c.check(not shop.get("locked"), "and the mouse is let go, to use the shop", shop.get("locked"))
    closed = d.get("closed", {})
    texts = ui_of(closed).get("texts", [])
    c.check(not screen_shown(closed, "Shop") and closed.get("paused") is False and "Coins: 0" in texts and "Stone axe" in texts,
            "buying the stone axe changes the panel (coins and badge), and Close goes back to the game", texts)
    typing = d.get("typing", {})
    c.check(ui_of(typing).get("inputs") == ["w"] and z.get("typing") == z.get("closed") and typing.get("down") == [],
            "W typed (and held) in the chat box goes in the box and doesn't walk",
            (ui_of(typing).get("inputs"), z.get("closed"), z.get("typing"), typing.get("down")))
    pause, resumed = d.get("pause", {}), d.get("resumed", {})
    c.check(screen_shown(pause, "Paused") and pause.get("paused") and not screen_shown(resumed, "Paused") and resumed.get("paused") is False,
            "Escape shows the pause menu (the program's on_key), and its Resume button hides it", (pause.get("paused"), resumed.get("paused")))
    shots = r.shots
    c.check(shots.get("ui3d_start.png") and color_share(shots["ui3d_start.png"], ACCENT, 50, (0.42, 0.6, 0.58, 0.68)) > 0.2,
            "the start screen's picture has its hint over the dimmed world", shots.get("ui3d_start.png"))
    c.check(shots.get("ui3d_panel.png") and color_share(shots["ui3d_panel.png"], ACCENT, 40, (0.015, 0.14, 0.075, 0.19)) > 0.3,
            "the panel's Chop button is drawn over the sky", shots.get("ui3d_panel.png"))
    c.check(shots.get("ui3d_shop.png") and color_share(shots["ui3d_shop.png"], CARD, 12, (0.3, 0.3, 0.7, 0.7)) > 0.3,
            "the shop is a card in the middle", shots.get("ui3d_shop.png"))
    preview_leaves_menus_out(c, "ui_3d.tuf")


# ---------------------------------------------------------------- splash screens, main menus and the mouse

def splash_of(d):
    return ui_of(d).get("splash") or {}


def dumps_by_name(r):
    """A run's dumps by their name without the prefix ("m3d_note.json" -> "note"); a missing one is {}."""
    import collections
    return collections.defaultdict(dict, {k.split("_", 1)[1][:-5]: v for k, v in r.dumps.items()})


def menu_shown(d, title):
    return any(s["title"] == title and s["shown"] and s.get("main") for s in ui_of(d).get("screens", []))


def t_menu_2d(c):
    """games/menu_2d.tuf: three splash screens (a picture, some text, "Made with Tuff") play in order over a black
    window, Space skips the first, the others end by themselves; the main menu waits behind them and shows after them
    with the game paused; its clicks aren't the game's; How to play changes its text and Play starts the game; P
    brings the menu back; Quit closes the game."""
    r = play("menu_2d", game("menu_2d.tuf"), [
        {"at": 0.6, "dump": "m2d_logo.json"}, {"at": 0.65, "shot": "m2d_logo.png"},
        {"at": 0.9, "key": "space"},
        {"at": 1.6, "dump": "m2d_text.json"}, {"at": 1.65, "shot": "m2d_text.png"},
        {"at": 3.0, "dump": "m2d_tuff.json"}, {"at": 3.05, "shot": "m2d_tuff.png"},
        {"at": 4.8, "dump": "m2d_menu.json"}, {"at": 4.85, "shot": "m2d_menu.png"},
        {"at": 4.9, "hold": "right", "for": 0.3},
        {"at": 5.3, "click": [60, 470]},
        {"at": 5.4, "click_ui": "How to play"},
        {"at": 5.6, "dump": "m2d_how.json"},
        {"at": 5.7, "click_ui": "Play"},
        {"at": 5.9, "dump": "m2d_play.json"},
        {"at": 6.0, "hold": "right", "for": 0.4},
        {"at": 6.6, "dump": "m2d_moved.json"},
        {"at": 6.7, "click": [700, 120]},
        {"at": 6.8, "key": "p"},
        {"at": 7.0, "dump": "m2d_back.json"}, {"at": 7.05, "call": "report"},
        {"at": 7.2, "click_ui": "Quit"},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = dumps_by_name(r)
    x = {k: (v.get("sprites") or [[None, None]])[0][1] for k, v in d.items()}  # the player is the first sprite made
    logo, text, tuff, menu = d["logo"], d["text"], d["tuff"], d["menu"]
    c.check(splash_of(logo).get("items") == ["logo.png", "Pip Studio presents", "Made with Tuff"],
            "game:splash queues a picture, some text and game:splash() (\"Made with Tuff\"), in order", splash_of(logo).get("items"))
    c.check(splash_of(logo).get("playing") and splash_of(logo).get("ended") == [] and logo.get("paused") and logo.get("time") == 0
            and menu_shown(logo, "Star Hopper"),
            "the first plays at the start, with the game paused (time 0) and the main menu waiting behind it",
            (splash_of(logo), logo.get("paused"), logo.get("time")))
    c.check(splash_of(text).get("ended") == ["skipped"], "Space skips the picture (3 s) to the text", splash_of(text).get("ended"))
    c.check(splash_of(tuff).get("ended") == ["skipped", "timed"] and splash_of(tuff).get("playing"),
            "the text ends by itself after its 1.2 s, and Made with Tuff plays", splash_of(tuff))
    c.check(not splash_of(menu).get("playing") and splash_of(menu).get("ended") == ["skipped", "timed", "timed"]
            and menu_shown(menu, "Star Hopper") and menu.get("paused") and menu.get("time") == 0,
            "after the last one the main menu shows, and the game stays paused", (splash_of(menu), menu.get("paused"), menu.get("time")))
    how = d.get("how", {})
    c.check("Arrow keys move. Catch the gold stars." in ui_of(how).get("texts", []) and menu_shown(how, "Star Hopper")
            and how.get("time") == 0 and x.get("how") == x.get("menu") == 400,
            "How to play changes the menu's text; the menu stays and holding right doesn't move the player",
            (ui_of(how).get("texts"), x.get("menu"), x.get("how")))
    playing = d.get("play", {})
    c.check(not menu_shown(playing, "Star Hopper") and playing.get("paused") is False, "Play hides the menu and the game runs",
            ui_of(playing).get("screens"))
    c.check((x.get("moved") or 0) > (x.get("play") or 0) + 40, f"then the player moves (x {x.get('moved')})", (x.get("play"), x.get("moved")))
    back = d.get("back", {})
    c.check(menu_shown(back, "Star Hopper") and back.get("paused"), "P shows the main menu again (menu:show), pausing the game",
            ui_of(back).get("screens"))
    c.check("plays 1, game clicks 1" in r.lines, "the clicks on the splash screens and the menu aren't the game's (1 game click: the one on the game)",
            r.lines)
    shots = r.shots
    s = shots.get("m2d_logo.png")
    c.check(s and color_share(s, (51, 120, 239), 60, (0.36, 0.3, 0.64, 0.7)) > 0.05 and color_share(s, (0, 0, 0), 6, (0, 0, 0.2, 0.2)) > 0.95,
            "the picture splash: the logo in the middle, on black", s)
    s = shots.get("m2d_text.png")
    c.check(s and color_share(s, (255, 255, 255), 30, (0.2, 0.43, 0.8, 0.58)) > 0.08 and color_share(s, (0, 0, 0), 6, (0, 0, 1, 0.35)) > 0.98,
            "the text splash: big white words in the middle, on black", s)
    s = shots.get("m2d_tuff.png")
    c.check(s and color_share(s, (44, 158, 239), 70, (0.36, 0.4, 0.46, 0.6)) > 0.05 and color_share(s, (230, 238, 252), 50, (0.48, 0.47, 0.64, 0.58)) > 0.08,
            "Made with Tuff: the dotted T in Tuff's blue, and the word Tuff", s)
    s = shots.get("m2d_menu.png")
    c.check(s and color_share(s, ACCENT, 50, (0.3, 0.5, 0.7, 0.56)) > 0.5, "the main menu's Play button is wide, in the middle, in atgui's blue", s)
    preview_leaves_menus_out(c, "menu_2d.tuf")


MOUSE_PROBE = ("const s = [...tv.objs.values()].find((n) => n.kind === 'scene');"
               "tv.emit('tg-autopilot', { message: 'mouse ' + JSON.stringify({ clicklock: !!s.clicklock, "
               "want: s.el.hasAttribute('data-tg-want'), locked: !!document.pointerLockElement }) });")
# The browser saying no to locking the mouse (as one does outside a click), and then allowing it again.
REFUSE_LOCK = ("window.__lockWas = Element.prototype.requestPointerLock;"
               "Element.prototype.requestPointerLock = function () { return Promise.reject(new DOMException('not now', 'NotAllowedError')); };")
ALLOW_LOCK = "Element.prototype.requestPointerLock = window.__lockWas;"


def t_menu_3d(c):
    """games/menu_3d.tuf, a first-person world: a click skips the splash; the main menu shows with the world paused and
    the mouse free, and its clicks (Settings and its Back, the backdrop) never lock it or reach the game; Play hides
    it and asks to lock the mouse in that click; E opens a note that lets go of the mouse, and Close locks it again;
    world:unlock_mouse frees it for good (a note no longer locks it again), world:auto_lock(false) stops clicks from
    locking it (and Play), world:lock_mouse asks for it (or the next click on the game does), world:mouse_locked."""
    r = play("menu_3d", game("menu_3d.tuf"), [
        {"at": 0.7, "dump": "m3d_splash.json"}, {"at": 0.75, "shot": "m3d_splash.png"},
        {"at": 0.9, "click_center": True},
        {"at": 1.8, "dump": "m3d_menu.json"}, {"at": 1.85, "shot": "m3d_menu.png"},
        {"at": 1.9, "hold": "w", "for": 0.3},
        {"at": 2.3, "click": [480, 580]},
        {"at": 2.4, "click_ui": "Settings"},
        {"at": 2.6, "dump": "m3d_settings.json"}, {"at": 2.65, "shot": "m3d_settings.png"},
        {"at": 2.8, "click_ui": "Back"},
        {"at": 3.0, "dump": "m3d_back.json"},
        {"at": 3.1, "click_ui": "Play"},
        {"at": 3.3, "dump": "m3d_play.json"},
        {"at": 3.35, "lock": True},
        {"at": 3.4, "hold": "w", "for": 0.4},
        {"at": 3.9, "dump": "m3d_walked.json"},
        {"at": 3.95, "key": "escape"},
        {"at": 4.0, "key": "e"},
        {"at": 4.2, "dump": "m3d_note.json"}, {"at": 4.25, "shot": "m3d_note.png"},
        {"at": 4.3, "click_ui": "Close"},
        {"at": 4.5, "dump": "m3d_closed.json"},
        {"at": 4.6, "call": "free"},
        {"at": 4.7, "dump": "m3d_free.json"},
        {"at": 4.8, "key": "e"},
        {"at": 4.9, "click_ui": "Close"},
        {"at": 5.1, "dump": "m3d_free_note.json"},
        {"at": 5.2, "call": "manual"},
        {"at": 5.25, "js": REFUSE_LOCK},
        {"at": 5.3, "call": "grab"},
        {"at": 5.5, "dump": "m3d_grab.json"}, {"at": 5.55, "js": MOUSE_PROBE},
        {"at": 5.6, "click_center": True},
        {"at": 5.7, "js": ALLOW_LOCK},
        {"at": 5.8, "dump": "m3d_next.json"},
        {"at": 5.9, "call": "free"},
        {"at": 6.0, "click_center": True},
        {"at": 6.2, "dump": "m3d_nolock.json"},
        {"at": 6.3, "key": "m"},
        {"at": 6.4, "click_ui": "Play"},
        {"at": 6.6, "dump": "m3d_manual.json"}, {"at": 6.65, "call": "report"},
        {"at": 6.8, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = dumps_by_name(r)
    names = ("splash", "menu", "settings", "back", "play", "walked", "note", "closed", "free", "free_note", "grab", "next",
             "nolock", "manual")
    z = {k: (d[k].get("player") or [None] * 5)[2] for k in names}
    mouse = {k: d[k].get("mouse") or {} for k in names}
    asks = {k: mouse[k].get("asks") for k in names}
    splash, menu = d["splash"], d["menu"]
    c.check(splash_of(splash).get("playing") and splash.get("paused") and splash.get("time") == 0 and not mouse["splash"].get("locked"),
            "the splash plays first: the world is paused and the mouse free", (splash_of(splash), splash.get("paused"), mouse["splash"]))
    c.check(splash_of(menu).get("ended") == ["skipped"] and menu_shown(menu, "Forest Notes") and menu.get("paused") and menu.get("time") == 0,
            "a click skips it, and the main menu shows with the world paused", (splash_of(menu), ui_of(menu).get("screens")))
    c.check(not mouse["menu"].get("locked") and not menu.get("locked") and asks["menu"] == 0,
            "the click on the splash didn't lock the mouse (or ask to)", (mouse["menu"], menu.get("locked")))
    settings, back = d.get("settings", {}), d.get("back", {})
    c.check(screen_shown(settings, "Settings") and menu_shown(settings, "Forest Notes") and settings.get("paused"),
            "Settings opens a screen over the main menu", ui_of(settings).get("screens"))
    c.check(not screen_shown(back, "Settings") and menu_shown(back, "Forest Notes") and back.get("time") == 0 and z.get("back") == z.get("menu") == 0,
            "Back closes it, the menu stays, and W held on the menu didn't walk", (ui_of(back).get("screens"), z.get("menu"), z.get("back")))
    c.check(all(asks[k] == 0 and not mouse[k].get("locked") and not d[k].get("locked") for k in ("settings", "back")),
            "the menu's clicks (its backdrop, Settings, Back) never lock the mouse or ask to", {k: (mouse[k], d[k].get("locked")) for k in ("settings", "back")})
    playing = d.get("play", {})
    m = mouse["play"]
    c.check(not menu_shown(playing, "Forest Notes") and playing.get("paused") is False, "Play hides the main menu and the world runs",
            ui_of(playing).get("screens"))
    c.check(asks["play"] == 1 and (m.get("locked") or m.get("want")),
            "and that click asks the page to lock the mouse for looking around (locked now, or on the next click)", m)
    c.check((z.get("walked") or 0) < (z.get("play") or 0) - 0.5, f"W walks (z {z.get('walked')})", (z.get("play"), z.get("walked")))
    note = d.get("note", {})
    c.check(screen_shown(note, "A note") and note.get("paused") and not mouse["note"].get("locked") and not note.get("locked")
            and mouse["note"].get("relock"), "E opens the note: the world pauses and the mouse is let go", (mouse["note"], note.get("locked")))
    closed = d.get("closed", {})
    c.check(not screen_shown(closed, "A note") and closed.get("paused") is False and asks["closed"] == asks["note"] + 1
            and mouse["closed"].get("locked"), "Close hides it and locks the mouse again, as it was", (mouse["note"], mouse["closed"]))
    free = mouse["free"]
    c.check(not free.get("locked") and not free.get("want") and not free.get("relock") and not d["free"].get("locked"),
            "world:unlock_mouse frees it (mouse_locked() is false)", free)
    c.check(asks["free_note"] == asks["free"] and not mouse["free_note"].get("locked"),
            "and keeps it free: the note opens and closes without locking it again", (mouse["free"], mouse["free_note"]))
    grab = mouse["grab"]
    probe = next((json.loads(line.split("mouse ", 1)[1]) for line in r.lines if line.startswith("[autopilot] mouse ")), {})
    c.check(grab.get("auto") is False and probe.get("clicklock") is False,
            "world:auto_lock(false): clicks on the game no longer lock the mouse (the page's scene too)", (grab, probe))
    c.check(asks["grab"] == asks["free_note"] + 1 and grab.get("want") and probe.get("want") and not grab.get("locked"),
            "world:lock_mouse asks to lock it now; when the browser says no, the next click on the game will", (grab, probe))
    c.check(asks["next"] == asks["grab"] + 1, "... and that next click does ask, even with auto_lock(false)", (asks["grab"], asks["next"]))
    nolock = d.get("nolock", {})
    c.check(asks["nolock"] == asks["next"] and not nolock.get("locked") and not mouse["nolock"].get("locked"),
            "after world:unlock_mouse with auto_lock(false), a click on the game leaves the mouse free", mouse["nolock"])
    manual = d.get("manual", {})
    c.check(not menu_shown(manual, "Forest Notes") and asks["manual"] == asks["nolock"] and not manual.get("locked"),
            "M shows the menu again, and with auto_lock(false) Play doesn't lock the mouse", (mouse["manual"], ui_of(manual).get("screens")))
    c.check("plays 2, game clicks 2, locked false" in r.lines,
            "world:mouse_locked() says false; only the two clicks on the world were the game's (not Escape, the menus' or the splash's)",
            [x for x in r.lines if x.startswith("plays")])
    shots = r.shots
    s = shots.get("m3d_splash.png")
    c.check(s and color_share(s, (255, 255, 255), 30, (0.2, 0.44, 0.8, 0.58)) > 0.08 and color_share(s, (0, 0, 0), 6, (0, 0, 1, 0.35)) > 0.98,
            "the splash covers the world in black, with its words in the middle", s)
    s = shots.get("m3d_menu.png")
    c.check(s and color_share(s, ACCENT, 50, (0.33, 0.51, 0.67, 0.57)) > 0.5, "the main menu's Play button over the dimmed world", s)
    s = shots.get("m3d_settings.png")
    c.check(s and color_share(s, CARD, 12, (0.3, 0.36, 0.7, 0.64)) > 0.3, "the Settings screen is a card over the main menu", s)
    s = shots.get("m3d_note.png")
    c.check(s and color_share(s, CARD, 12, (0.3, 0.38, 0.7, 0.62)) > 0.3, "the note is a card in the middle", s)
    preview_leaves_menus_out(c, "menu_3d.tuf")


def t_menu_start(c):
    """games/menu_start.tuf: a splash screen before a start screen (game:start_screen works as before): Enter during
    the splash only skips it (the start screen stays, nothing locks), then Enter starts the game, runs start:clicked
    and asks the page to lock the mouse."""
    r = play("menu_start", game("menu_start.tuf"), [
        {"at": 0.5, "dump": "mst_splash.json"},
        {"at": 0.6, "key": "enter"},
        {"at": 1.4, "dump": "mst_start.json"}, {"at": 1.45, "shot": "mst_start.png"},
        {"at": 1.6, "key": "enter"},
        {"at": 1.8, "dump": "mst_play.json"}, {"at": 1.85, "call": "report"},
        {"at": 2.0, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    d = dumps_by_name(r)
    splash, start, playing = d["splash"], d["start"], d["play"]
    c.check(splash_of(splash).get("playing") and screen_shown(splash, "Cave Run") and splash.get("paused"),
            "the splash plays over the start screen, which waits", (splash_of(splash), ui_of(splash).get("screens")))
    c.check(splash_of(start).get("ended") == ["skipped"] and screen_shown(start, "Cave Run") and start.get("paused") and start.get("time") == 0
            and ui_of(start).get("lock_asks") == 0, "Enter skips the splash only: the start screen still shows, and nothing asked to lock the mouse",
            (splash_of(start), ui_of(start).get("screens"), ui_of(start).get("lock_asks")))
    c.check(not screen_shown(playing, "Cave Run") and playing.get("paused") is False and ui_of(playing).get("lock_asks", 0) >= 1
            and "starts 1" in r.lines, "then Enter starts the game as before: start:clicked runs and the page is asked to lock the mouse",
            (ui_of(playing).get("screens"), ui_of(playing).get("lock_asks"), r.lines[-2:]))
    s = r.shots.get("mst_start.png")
    c.check(s and color_share(s, ACCENT, 50, (0.4, 0.6, 0.6, 0.72)) > 0.15, "the start screen's hint shows once the splash is gone", s)


# ---------------------------------------------------------------- Tuff Engine's preview (tuff.py --scene)

def scene(program, source=None, env=None, timeout=30):
    """tuff.py --scene <program> <source> <out.json>: (exit code, stdout, stderr, the dump or {}, seconds)."""
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, "scene_" + os.path.basename(source or program).replace(".tuf", ".json"))
    if os.path.exists(out):
        os.remove(out)
    full_env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})}
    full_env.pop("TUFF_TGAME_AUTOPILOT", None)
    t0 = time.perf_counter()
    p = subprocess.run(tuff_cmd() + ["--scene", program, source or program, out], cwd=os.path.dirname(program), env=full_env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    secs = time.perf_counter() - t0
    try:
        with open(out, encoding="utf-8") as f:
            dump = json.load(f)
    except (OSError, ValueError):
        dump = {}
    return p.returncode, p.stdout, p.stderr, dump, secs


def scene_source(name, code):
    path = os.path.join(OUT, name)
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


def t_scene(c):
    """tuff.py --scene runs a game's setup with no window (Tuff Engine's preview): the engine commands it would send,
    and every thing it made with the line that made it, for the test games and both Tuff Engine templates."""
    def run(name, want_stopped, want_mode):
        code, out, err, d, secs = scene(game(name))
        c.check(code == 0 and not out.strip() and "Traceback" not in err and "Tuff error" not in err,
                f"{name}: --scene exits 0 in {secs:.1f} s and prints nothing (no notice, no say lines)", (code, out[:200], err[-400:]))
        c.check(d.get("v") == 1 and d.get("mode") == want_mode and d.get("stopped") == want_stopped and d.get("error") is None,
                f"{name}: a {want_mode} dump that stopped at the {want_stopped}", {k: d.get(k) for k in ("v", "mode", "stopped", "error")})
        batch = d.get("batch") or []
        c.check(batch and batch[0][0] == "c" and not any(cmd[0] == "j" for cmd in batch),
                f"{name}: {len(batch)} engine commands, starting with the {'scene' if want_mode == '3d' else 'canvas'}", batch[:2])
        return d, batch

    def thing(d, var):
        return next((t for t in d.get("things", []) if t.get("var") == var), {})

    def made_by(d, made):
        return [t for t in d.get("things", []) if t.get("made") == made]

    # snake: things made by start() keep both lines; food is moved by start(), so its spot differs from its line
    d, batch = run("snake.tuf", "end", "2d")
    c.check(d.get("size") == [600, 400] and d.get("title") == "Snake" and d.get("roots") == {"view": 1, "hud": None}
            and d.get("canvas") == {"cx": 0, "cy": 0}, "snake: the size, title, roots and 2D camera", {k: d.get(k) for k in ("size", "title", "roots", "canvas")})
    label, food = thing(d, "score_label"), thing(d, "food")
    c.check(label.get("kind") == "text" and label.get("made") == [5] and label.get("layer") == "game" and label.get("ids") == [2]
            and label.get("drag") == "xy", "snake: score_label is a text made on line 5", label)
    c.check(food.get("made") == [6] and food.get("x", 0) % 20 == 10 and food.get("y", 0) % 20 == 10,
            "snake: food (line 6) is where start() moved it, on the 20-grid", food)
    body = made_by(d, [52, 15])
    c.check(len(body) == 2 and [b["kind"] for b in body] == ["box", "box"] and body[0]["x"] == 150,
            "snake: the 2 body boxes were made by start() on line 52, at line 15", body)
    c.check(["s", 1, {"bg": "#14213d"}] in batch, "snake: the background is in the batch", batch[:3])

    # axe_sim: a loop game, a first-person player holding an axe, a HUD, things made in for loops
    d, batch = run("axe_sim.tuf", "loop", "3d")
    p = d.get("player") or {}
    held = p.get("held") or {}
    c.check(p.get("mode") == "first person" and p.get("made") == [6] and p.get("ids") == [] and held.get("name") == "axe"
            and held.get("made") == [7] and len(held.get("ids", [])) == 3, "axe_sim: the first-person player (line 6) holds the axe (line 7)", p)
    c.check(d.get("camera") == {"cx": 0, "cy": 1.6, "cz": 0, "yaw": 0, "pitch": 0}, "axe_sim: the camera is the player's eye", d.get("camera"))
    c.check(isinstance(d.get("roots", {}).get("hud"), int) and d["roots"]["view"] == 1, "axe_sim: the scene and the HUD are the roots", d.get("roots"))
    island = [t for t in d.get("things", []) if t.get("kind") == "island"]
    c.check(len(island) == 1 and island[0]["drag"] is None and island[0]["made"] == [5], "axe_sim: one island, not draggable", island)
    kinds = {}
    for t in d.get("things", []):
        kinds.setdefault((t["kind"], tuple(t["made"])), []).append(t)
    c.check(len(kinds.get(("rock", (15, 16)), [])) == 6 and len(kinds.get(("tree", (17, 18)), [])) == 20
            and len(kinds.get(("pine", (20, 21)), [])) == 10, "axe_sim: 6 rocks, 20 trees and 10 pines made in their for loops",
            {f"{k[0]} {list(k[1])}": len(v) for k, v in kinds.items()})
    near = thing(d, "near")
    c.check(near.get("kind") == "pine" and near.get("made") == [23] and near.get("x") == 0 and near.get("z") == -6 and near.get("drag") == "xz"
            and near.get("dims") and near.get("k") == [1, 1, 1] and len(near.get("ids", [])) >= 2,
            "axe_sim: near is a pine on line 23 at (0, 0, -6) with its size and its group and parts", near)
    hud = [t for t in d.get("things", []) if t.get("layer") == "hud"]
    c.check([t.get("made") for t in hud] == [[9], [10]], "axe_sim: the two HUD texts, not the crosshair or the hint", hud)
    hidden = [cmd[1] for cmd in batch if cmd[0] == "s" and cmd[2].get("visible") is False]
    c.check(len(hidden) >= 2, "axe_sim: the crosshair and the mouse hint are hidden in a preview", hidden)
    c.check(batch[-1][0] == "s" and batch[-1][1] == 1 and "cx" in batch[-1][2], "axe_sim: the starting camera is the last command", batch[-1])

    d, batch = run("breakout.tuf", "loop", "2d")
    bricks = made_by(d, [31, 18, 19, 20])
    c.check(len(bricks) == 40 and thing(d, "paddle").get("made") == [5], "breakout: 40 bricks made by start() on line 31, and the paddle", len(bricks))

    d, batch = run("features_2d.tuf", "end", "2d")
    star = thing(d, "star")
    srcs = [cmd[5].get("src") for cmd in batch if cmd[0] == "c" and cmd[3] == "image"]
    c.check(star.get("kind") == "image" and srcs == ["asset:star.png", "asset:star.png"], "features_2d: pictures are asset:star.png", srcs)
    c.check(thing(d, "title").get("layer") == "hud" and d.get("roots", {}).get("hud") == 2, "features_2d: the HUD text is on the hud layer", thing(d, "title"))
    lines = [t for t in d.get("things", []) if t.get("kind") == "line"]
    c.check(len(lines) == 1 and lines[0]["made"] == [14] and lines[0]["var"] is None, "features_2d: the unnamed line on line 14", lines)
    c.check(["k", 0, "sound", ["s1", "asset:blip.wav", 1, False]] in batch, "features_2d: sound files are asset: too", [b for b in batch if b[0] == "k"])
    c.check(thing(d, "box").get("x") == 310, "features_2d: what the setup did (group:move) is in the dump", thing(d, "box"))

    d, batch = run("features_3d.tuf", "end", "3d")
    model = thing(d, "tower")
    c.check(model.get("kind") == "model" and any(cmd[0] == "c" and cmd[5] and cmd[5].get("src") == "asset:tower.glb" for cmd in batch),
            "features_3d: the .glb is asset:tower.glb", model)
    ground = [t for t in d.get("things", []) if t.get("kind") == "ground"]
    c.check(len(ground) == 1 and ground[0]["drag"] is None, "features_3d: the ground isn't draggable", ground)
    c.check(len(made_by(d, [17, 18])) == 11, "features_3d: the 11 kit things from the for loop", len(made_by(d, [17, 18])))
    cam = d.get("camera") or {}
    c.check(cam.get("cx") == 0 and cam.get("cy") == 2 and cam.get("cz") == 3 and cam.get("pitch", 0) < 0 and d.get("player") is None,
            "features_3d: camera_at and look_at give the starting camera", cam)
    c.check("terrain" not in d and d.get("lighting") == "simple" and not any("ground" in t for t in d.get("things", []))
            and not any(cmd[0] == "c" and cmd[3] in ("terrain", "water") for cmd in batch),
            "features_3d: a world without land has no terrain in its dump, and simple lighting", d.get("lighting"))

    # The land: the terrain and its water in the batch, the land as a thing, its heights and every edit with its line
    d, batch = run("terrain_walk.tuf", "end", "3d")
    land = d.get("terrain") or {}
    c.check(land.get("var") == "land" and land.get("made") == [7] and land.get("size") == 200 and land.get("n") == 134
            and len(land.get("heights") or []) == 134 * 134 and land.get("style") == "grass" and land.get("sea") is None
            and land.get("lakes") == [{"x": 30, "z": 0, "r": 10, "level": -0.2}],
            "terrain_walk: the land (line 7), 200 wide, 134 x 134 heights, its lake", {k: v for k, v in land.items() if k not in ("heights", "edits")})
    edits = [(e.get("op"), e.get("made")) for e in land.get("edits", [])]
    c.check(edits == [("style", [8]), ("hill", [9]), ("mountain", [10]), ("dip", [11]), ("lake", [12]), ("valley", [13]),
                      ("raise", [14]), ("raise", [15]), ("lower", [16]), ("smooth", [17]), ("flatten", [18]), ("raise", [24])],
            "terrain_walk: every edit, in order, with the line that made it", edits)
    stroke = (land.get("edits") or [{}] * 8)[7]
    c.check(stroke.get("args") == [[[-30, 30], [-26, 32], [-22, 35]], 8, 1.5] and land["edits"][1].get("args") == [0, -14, 30, 6],
            "terrain_walk: an edit's inputs as the code wrote them (a stroke's spots too)", stroke)
    item = d.get("things", [{}])[0]
    c.check(item.get("kind") == "terrain" and item.get("drag") is None and item.get("var") == "land" and item.get("made") == [7]
            and item.get("i") == 0 and item.get("ids") == land.get("ids") and len(item.get("ids", [])) == 2,
            "terrain_walk: the land is the first thing (not draggable), with its water's id", item)
    box = thing(d, "on_hill")
    c.check(box.get("y") == 0 and abs(box.get("ground", 0) - 5.951) < 0.01 and thing(d, "floating").get("y") == 3
            and thing(d, "later").get("y") == 0, "terrain_walk: things' y is their height above the land, with the land's height", box)
    made = {cmd[3]: cmd for cmd in batch if cmd[0] == "c" and cmd[3] in ("terrain", "water")}
    heights = [cmd for cmd in batch if cmd[0] == "s" and "heights" in cmd[2]]
    c.check(made.get("terrain", [0] * 6)[5] == {"size": 200, "n": 134, "style": "grass", "shadow": True}
            and made.get("water", [0] * 6)[5] == {"x": 30, "z": 0, "y": -0.2, "r": 10}
            and len(heights) == 1 and heights[0][2]["heights"] == land.get("heights"),
            "terrain_walk: the batch makes the terrain and the lake's water, and sends the heights once", (made, len(heights)))
    c.check(any(cmd[0] == "s" and cmd[1] == 1 and cmd[2].get("lighting") == "modern" for cmd in batch) and d.get("lighting") == "modern",
            "terrain_walk: modern lighting is on the scene", d.get("lighting"))
    p = d.get("player") or {}
    c.check(p.get("y") == 0 and p.get("ground") == 0.145 and (d.get("camera") or {}).get("cy") == 1.745,
            "terrain_walk: the player starts standing on the land, its eye 1.6 above it", (p, d.get("camera")))
    for name, code, line, msg in [
            ("two", 'w = tgame.world("x")\na = w:terrain(100)\nb = w:terrain(100)\n', 4,
             "A world has one terrain. Change it with land:hill, land:raise and so on."),
            ("size", 'w = tgame.world("x")\na = w:terrain(5)\n', 3, ":terrain needs a size from 10 to 1000"),
            ("lake", 'w = tgame.world("x")\na = w:terrain(100)\na:lake(0, 0, 10, 0)\n', 4, ":lake needs a depth above 0"),
            ("spot", 'w = tgame.world("x")\na = w:terrain(100)\na:hill(5)\n', 4, ":hill needs x and z (where on the land)"),
            ("stroke", 'w = tgame.world("x")\na = w:terrain(100)\na:raise([[1, 2], [3]], 4, 1)\n', 4, ":raise needs spots like [[1, 2], [3, 2]]"),
            ("style", 'w = tgame.world("x")\na = w:terrain(100)\na:style "gras"\n', 4, 'Did you mean "grass"?'),
            ("lighting", 'w = tgame.world("x")\nw:lighting "modren"\n', 3, 'Did you mean "modern"?')]:
        e = scene(scene_source(f"scene_land_{name}.tuf", "mention tgame\n" + code))[3].get("error") or {}
        c.check(e.get("line") == line and msg in e.get("message", ""), f"a mistake with the land: {msg}", e)

    # The two Tuff Engine templates: every thing is on its own top-level line, named, at its line's numbers
    d, batch = run("coin_dash.tuf", "end", "2d")
    want = [("score_label", "text", 400, 30, 6), ("player", "box", 400, 520, 7), ("coin", "circle", 200, 200, 9),
            ("enemy", "box", 100, 80, 10), ("ball", "circle", 600, 300, 11)]
    got = [(t.get("var"), t.get("kind"), t.get("x"), t.get("y"), (t.get("made") or [None])[0]) for t in d.get("things", [])]
    c.check(got == want, "coin_dash: score_label, player, coin, enemy and ball at their lines' numbers", got)
    d, batch = run("island_walk.tuf", "end", "3d")
    want = [(None, "island", 0, 0, 5), ("score_label", "text", 90, 30, 8), ("coin", "coin", 4, -8, 10), ("tree", "tree", -5, -10, 12),
            ("hut", "hut", 8, -16, 14), ("enemy", "box", -12, -20, 15)]
    got = [(t.get("var"), t.get("kind"), t.get("x"), t.get("z") if t.get("layer") == "world" else t.get("y"), (t.get("made") or [None])[0])
           for t in d.get("things", [])]
    c.check(got == want, "island_walk: the island, score_label, coin, tree, hut and enemy at their lines' numbers", got)
    c.check((d.get("player") or {}).get("made") == [9] and (d.get("player") or {}).get("held") is None, "island_walk: the player on line 9", d.get("player"))
    tables = d.get("tables") or {}
    c.check(tables.get("colors", {}).get("gold") == "#f2c230" and "sunset" in tables.get("skies", []) and "coin" in tables.get("kit", [])
            and "axe" in tables.get("hold", []) and "lose" in tables.get("sounds", []) and tables.get("edges") == ["bounce", "wrap", "stop", "none"],
            "the dump has tgame's tables for the editor's menus", {k: len(v) for k, v in tables.items()})

    # The editor's unsaved text: the source is another file, and the game's own folder still finds its pictures
    src = scene_source("scene_unsaved.tuf", 'mention tgame\n\ngame = tgame.window("Unsaved", 300, 200)\npic = game:image("star.png", 50, 50)\n')
    code, out, err, d, secs = scene(game("features_2d.tuf"), src)
    c.check(d.get("title") == "Unsaved" and thing(d, "pic").get("kind") == "image" and d.get("stopped") == "end",
            "the code comes from the source file; pictures are found next to the game file", (d.get("stopped"), d.get("error")))

    # What a preview never does: wait, ask for input, go on the internet, or run another library's window
    src = scene_source("scene_waits.tuf", 'mention tgame\nmention anims\nwait(20)\nname = input("Name? ")\nanims.loading("Loading", 20)\n'
                                          'say "hello"\ngame = tgame.window("Hi " + name, 300, 200)\n')
    code, out, err, d, secs = scene(src)
    c.check(code == 0 and secs < 5 and d.get("title") == "Hi " and not out.strip(), f"wait, input and anims don't wait ({secs:.1f} s)", (code, d.get("title"), out[:100]))
    src = scene_source("scene_tap.tuf", 'mention tgame\nmention tap\ngame = tgame.window("Net", 300, 200)\nr = tap.get("http://example.invalid/")\n')
    code, out, err, d, secs = scene(src)
    c.check(d.get("stopped") == "error" and (d.get("error") or {}).get("line") == 4 and "doesn't go on the internet" in (d.get("error") or {}).get("message", ""),
            "tap doesn't go on the internet", d.get("error"))
    src = scene_source("scene_tgui.tuf", 'mention tgame\nmention tgui\napp = tgui.window("App")\n')
    c.check(scene(src)[3].get("stopped") == "other-window", "a file that also opens a tgui window runs nothing", None)
    src = scene_source("scene_nogame.tuf", 'say "no game"\n')
    c.check(scene(src)[3].get("stopped") == "nogame", "a file without tgame: nogame", None)
    src = scene_source("scene_nowindow.tuf", 'mention tgame\nx = 1\n')
    c.check(scene(src)[3].get("stopped") == "nowindow", "tgame without a window: nowindow", None)

    # Errors: the line and message, and the things made before it
    src = scene_source("scene_error.tuf", 'mention tgame\n\ngame = tgame.window("Oops", 400, 300)\na = game:box(10, 10)\nb = game:circle(20, 20, 5, "nocolour")\n')
    code, out, err, d, secs = scene(src)
    e = d.get("error") or {}
    c.check(code == 0 and d.get("stopped") == "error" and e.get("line") == 5 and "isn't a color" in e.get("message", "")
            and [t.get("var") for t in d.get("things", [])] == ["a"], "an error gives its line and message, with the things made before it", (d.get("stopped"), e))
    src = scene_source("scene_return.tuf", 'mention tgame\ngame = tgame.window("R")\nreturn 3\n')
    e = scene(src)[3].get("error") or {}
    c.check(e.get("line") == 3 and "return" in e.get("message", ""), "a return outside a function is an error on its line", e)
    # Pictures come from the game's folder or a folder inside it: one in the folder above (../) is refused, even
    # though it's there, and the message says where it has to be (the same words as --check)
    up = os.path.join(OUT, "up")
    os.makedirs(up, exist_ok=True)
    with open(os.path.join(GAMES, "star.png"), "rb") as f, open(os.path.join(OUT, "star_up.png"), "wb") as g:
        g.write(f.read())
    src = os.path.join(up, "scene_up.tuf")
    with open(src, "w", encoding="utf-8") as f:
        f.write('mention tgame\ngame = tgame.window("Up", 300, 200)\nok = game:box(10, 10)\npic = game:image("../star_up.png", 50, 50)\n')
    e = scene(src)[3].get("error") or {}
    c.check(e.get("line") == 4 and e.get("message") == "The picture '../star_up.png' has to be next to your .tuf file, or in a folder inside it.",
            "a picture in the folder above the game (../) is refused, saying where it has to be", e)
    src = scene_source("scene_big.tuf",'mention tgame\ngame = tgame.window("Big", 400, 300)\nfor i in range(1, 100000):\n    game:box(i % 400, 10)\n')
    code, out, err, d, secs = scene(src)
    c.check(d.get("stopped") == "too-big" and d.get("batch") == [] and d.get("things") == [] and secs < 5,
            f"a setup that makes too much stops early as too-big ({secs:.1f} s)", (d.get("stopped"), len(d.get("batch") or []), secs))
    # Memory, not only time: the preview runs by itself whenever the code changes, so a setup that would build
    # something huge (a range of 100 million numbers is 4.6 GB, text doubled 40 times far more) stops early as
    # "too-much", showing what was made before it. A long loop that fits in the time is still fine.
    for name, setup in [("range", "for i in range(1, 100000000):\n    x = i\n"), ("text", 's = "a" * 1000000000\n'),
                        ("doubled", 's = "ab"\nfor i in range(1, 40):\n    s = s + s\n'), ("list", "l = [1, 2]\nfor i in range(1, 40):\n    l = l + l\n")]:
        src = scene_source(f"scene_huge_{name}.tuf", f'mention tgame\ngame = tgame.window("Huge", 400, 300)\nfirst = game:box(10, 10)\n{setup}last = game:box(50, 50)\n')
        code, out, err, d, secs = scene(src)
        c.check(code == 0 and d.get("stopped") == "too-much" and [t.get("var") for t in d.get("things", [])] == ["first"] and secs < 4,
                f"a huge {name} in the setup stops the preview as too-much in {secs:.1f} s, with what was made before it", (d.get("stopped"), d.get("error"), secs))
    src = scene_source("scene_huge_first.tuf", 'mention tgame\nr = range(1, 100000000)\ngame = tgame.window("Huge", 400, 300)\n')
    c.check(scene(src)[3].get("stopped") == "too-much", "too-much even before the game's window is made", None)
    src = scene_source("scene_long_loop.tuf", 'mention tgame\ngame = tgame.window("Long", 400, 300)\nfor i in range(1, 1000000):\n    x = i\nb = game:box(10, 10)\n')
    code, out, err, d, secs = scene(src)
    c.check(d.get("stopped") == "end" and [t.get("var") for t in d.get("things", [])] == ["b"], f"a loop over a million numbers still previews ({secs:.1f} s)", (d.get("stopped"), secs))
    # Only a newline ends a line, as in the editor: a form feed, U+2028, NEL or a vertical tab inside a text or a
    # comment leaves the line numbers alone, so every thing is made on the line the editor shows (Tuff Engine finds
    # things by that line: a drag must change the thing's own line). On a line of its own it's an error on that line.
    for ch in ("\x0c", " ", "\x85", "\x0b"):
        src = scene_source("scene_breaks.tuf", f'mention tgame\n# a{ch}b\ngame = tgame.window("G", 800, 600)\nsay "x{ch}y"\n'
                                               f'coin = game:circle(200, 200, 14, "gold")\nenemy = game:box(100, 80, 40, 40, "red")\n')
        d = scene(src)[3]
        made = [(t.get("var"), t.get("made")) for t in d.get("things", [])]
        c.check(d.get("stopped") == "end" and made == [("coin", [5]), ("enemy", [6])], f"U+{ord(ch):04X} in a comment and a text: coin and enemy are made on lines 5 and 6", (d.get("stopped"), made))
        src = scene_source("scene_break_line.tuf", f'mention tgame\n{ch}\ngame = tgame.window("G", 800, 600)\n')
        e = scene(src)[3].get("error") or {}
        c.check(e.get("line") == 2 and f"U+{ord(ch):04X}" in e.get("message", ""), f"U+{ord(ch):04X} on a line of its own: an error on line 2", e)
    p = subprocess.run(tuff_cmd() + ["--scene", game("snake.tuf")], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.returncode == 2 and "--scene needs" in p.stderr, "--scene without its three files says what it needs", p.stderr[:200])
    code, out, err, d, secs = scene(game("coin_dash.tuf"), env={"TUFF_IDE": "1"})
    c.check(code == 0 and out == "" and d.get("stopped") == "end", "in the IDE's environment too, --scene shows nothing (no notice line)", out[:200])


# ---------------------------------------------------------------- the yellow notice

def t_notice(c):
    import tuff
    src = os.path.join(GAMES, "callback.tuf")
    plan = os.path.join(OUT, "notice.plan.json")
    os.makedirs(OUT, exist_ok=True)
    with open(plan, "w") as f:
        json.dump({"on_top": True, "steps": []}, f)
    env = {**os.environ, "TUFF_IDE": "1", "PYTHONIOENCODING": "utf-8", "TUFF_TGAME_AUTOPILOT": plan}
    p = subprocess.run(tuff_cmd() + [src], cwd=GAMES, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
    b = base64.b64encode(NOTICE.encode()).decode()
    c.check(p.stdout.startswith(f"\x1b]tuff;say;0;{b};notice\x07\n"), "in the IDE it's the first output, a say line with the notice style", p.stdout[:120])
    c.check(f"\x1b]tuff;say;1;{base64.b64encode(b'set up').decode()}\x07" in p.stdout, "the program's own lines still start at 1, with no style", p.stdout[:300])

    class FakeTerminal(io.StringIO):
        def isatty(self):
            return True

    old, sys.stdout = sys.stdout, FakeTerminal()
    try:
        tuff.Console(first_id=0).say(tuff.TGAME_NOTICE, "notice")
        tty = sys.stdout.getvalue()
        sys.stdout = io.StringIO()
        tuff.Console().say("plain", None)
        plain = sys.stdout.getvalue()
    finally:
        sys.stdout = old
    c.check(tty == f"\x1b[33m{NOTICE}\x1b[0m\n", "in a real terminal it's yellow (ANSI 33)", repr(tty))
    c.check(plain == "plain\n", "ordinary lines are unchanged", repr(plain))
    c.check(tuff.TGAME_NOTICE == NOTICE, "the text is the one constant, TGAME_NOTICE", tuff.TGAME_NOTICE)
    p = subprocess.run(tuff_cmd() + ["--check", src], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.stdout.strip() == "OK", "--check doesn't show it", p.stdout[:200])
    other = os.path.join(OUT, "no_tgame.tuf")
    with open(other, "w") as f:
        f.write('say "no game here"\n')
    p = subprocess.run(tuff_cmd() + [other], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.stdout.replace("\nPress Enter to close...", "").strip() == "no game here", "programs without tgame don't show it", p.stdout[:200])
    import tuff_view
    saved = (tuff.WINDOWED, tuff_view.run, sys.stdout)
    try:
        tuff.WINDOWED = True
        tuff_view.run = lambda *a: 0
        sys.stdout = io.StringIO()
        tuff.run_program(src)
        windowed = sys.stdout.getvalue()
    finally:
        tuff.WINDOWED, tuff_view.run, sys.stdout = saved
    c.check(NOTICE not in windowed, "a built app with no console (--windowed) doesn't show it", windowed[:200])


def t_mcp(c):
    """tuff_run through the MCP server: the notice line comes through screen() as plain text."""
    prog = os.path.join(OUT, "mcp_game.tuf")
    with open(prog, "w") as f:
        f.write('mention tgame\n\ngame = tgame.window("MCP", 300, 200)\nsay "hi"\n\nfunc done():\n    game:close()\n\ngame:after(0.5, done)\n')
    server = os.path.join(REPO, "tuffcode", "mcp", "tuff-mcp.js")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tuff_run", "arguments": {"file": prog, "timeout_seconds": 30}}}]
    env = {**os.environ, "TUFF_CMD": json.dumps(tuff_cmd() if RUNTIME else ["py", "-3", "-u", TUFF] if os.name == "nt" else ["python3", "-u", TUFF])}
    try:
        p = subprocess.Popen(["node", server], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", env=env)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the MCP check")
        return
    text = ""
    try:
        for m in msgs:
            p.stdin.write(json.dumps(m) + "\n")
        p.stdin.flush()
        deadline = time.time() + 60
        while time.time() < deadline:  # the server quits when its input ends, so keep it open until it answers
            line = p.stdout.readline()
            if not line:
                break
            reply = json.loads(line)
            if reply.get("id") == 2:
                text = reply["result"]["content"][0]["text"]
                break
    finally:
        p.stdin.close()
        p.wait(10)
    c.check(text.startswith(f"{NOTICE}\nhi\n\nExit code 0."), "tuff_run shows the notice, then the program's lines", text[:300])


# ---------------------------------------------------------------- the editor's docs and the guide

LOAD_LANG = """
const fs = require('fs'), vm = require('vm');
const window = {};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), { window });
const snippets = [];
let provider = null;
const monaco = { languages: { register() {}, setMonarchTokensProvider() {}, setLanguageConfiguration() {},
  registerHoverProvider() {}, registerDefinitionProvider() {}, registerReferenceProvider() {}, registerRenameProvider() {},
  registerDocumentSymbolProvider() {}, registerSignatureHelpProvider() {}, registerColorProvider() {},
  registerCompletionItemProvider(_id, p) {
    provider = p;
    const model = { getWordUntilPosition: () => ({ startColumn: 1, endColumn: 1 }), getLineContent: () => '', getValue: () => '', getLinesContent: () => [] };
    for (const s of p.provideCompletionItems(model, { lineNumber: 1, column: 1 }).suggestions) if (s.kind === 'Snippet') snippets.push([s.label, s.insertText]);
  },
  CompletionItemKind: new Proxy({}, { get: (_t, k) => k }), CompletionItemInsertTextRule: {}, IndentAction: {}, SymbolKind: {} },
  editor: { defineTheme() {} } };
window.defineTuffTheme = () => {};
try { window.registerTuff(monaco, '#3574f0'); } catch (e) { console.error(e); }
const after = (src) => provider.provideCompletionItems({ getWordUntilPosition: () => ({ startColumn: 5, endColumn: 5 }),
  getLineContent: () => 'app:', getValue: () => src, getLinesContent: () => src.split('\\n') }, { lineNumber: 1, column: 5 }).suggestions.map((s) => s.label);
console.log(JSON.stringify({ libs: window.TUFF_LIBS, docs: window.TUFF_DOCS, methods: window.TUFF_METHOD_DOCS, snippets,
  plain: after('app = tgui.window()\\n'), games: after('mention tgame\\n'), ui: after('mention tgame\\nbar = game:panel("top left")\\n') }));
"""


# ---------------------------------------------------------------- talking, grabbing, doors and keys

def ix(d):
    """A dump's talking, grabbing, doors and keys (Interaction.state)."""
    return d.get("interact") or {}


def t_ix_grab(c):
    """player:can_grab: looking at a physics crate, E picks it up and it floats in front of the player (following the
    view), a click throws it far, E drops what's held, and with can_grab(false) E grabs nothing."""
    look = [{"at": 0.4, "lock": True}, {"at": 0.5, "look": [0, 200]}]
    r = play("ix_grab", game("ix_grab.tuf"), look + [
        {"at": 1.6, "dump": "ixg_aim.json"}, {"at": 1.7, "key": "e"},
        {"at": 2.6, "call": "report"}, {"at": 2.65, "dump": "ixg_held.json"},
        {"at": 2.7, "look": [0, -200]}, {"at": 3.6, "call": "report"}, {"at": 3.65, "dump": "ixg_up.json"},
        {"at": 3.7, "shot": "ix_grab.png"},
        {"at": 3.8, "click_center": True}, {"at": 3.9, "dump": "ixg_thrown.json"},
        {"at": 5.4, "call": "report"}, {"at": 5.45, "dump": "ixg_landed.json"},
        {"at": 5.5, "tuff": "player:move_to(-3, 0, 3)"}, {"at": 5.6, "look": [0, 230]},
        {"at": 6.3, "key": "e"}, {"at": 6.8, "dump": "ixg_ball.json"}, {"at": 6.9, "key": "e"},
        {"at": 7.0, "dump": "ixg_dropped.json"}, {"at": 7.1, "call": "no_grab"}, {"at": 7.2, "key": "e"},
        {"at": 7.4, "dump": "ixg_off.json"}, {"at": 7.5, "close": True}])
    clean_exit(c, r)
    aim = ix(r.dumps.get("ixg_aim.json", {}))
    c.check(aim.get("grab") and aim.get("hint") == "E: Grab", "looking at a physics crate within 3 m, the hint says \"E: Grab\"", aim)
    held = r.dumps.get("ixg_held.json", {})
    crate = (bodies(held, "crate") or [None])[0]
    c.check(ix(held).get("held") == "crate" and any(line.startswith("holding <crate") for line in r.lines),
            "E picks it up: player:holding() gives the crate", (ix(held), r.lines[-3:]))
    c.check(crate and crate[2] > 0.1 and abs(crate[1]) < 0.3 and 1.6 < crate[3] < 2.6, f"it floats in front of the player (y {crate and crate[2]})", crate)
    c.check(ix(held).get("hint") == "E: Drop     Click: Throw", "the hint says E drops it and a click throws it", ix(held).get("hint"))
    up = (bodies(r.dumps.get("ixg_up.json", {}), "crate") or [None])[0]
    c.check(up and crate and up[2] > crate[2] + 0.7, f"looking up, it goes up with the view (y {up and up[2]})", (crate, up))
    thrown = r.dumps.get("ixg_thrown.json", {})
    landed = (bodies(r.dumps.get("ixg_landed.json", {}), "crate") or [None])[0]
    c.check(ix(thrown).get("held") is None and landed and landed[3] < -6,
            f"a click throws it: it flies off and lands far away (z {landed and landed[3]})", (ix(thrown), landed))
    c.check(any(line.startswith("holding nothing") for line in r.lines), "then player:holding() gives nil", r.lines[-3:])
    c.check(ix(r.dumps.get("ixg_ball.json", {})).get("held") == "sphere", "E picks up a ball too", ix(r.dumps.get("ixg_ball.json", {})))
    c.check(ix(r.dumps.get("ixg_dropped.json", {})).get("held") is None, "E again drops it", ix(r.dumps.get("ixg_dropped.json", {})))
    off = ix(r.dumps.get("ixg_off.json", {}))
    c.check(off.get("held") is None and not off.get("grab") and off.get("hint") is None,
            "with player:can_grab(false), E grabs nothing and there's no hint", off)
    shot = r.shots.get("ix_grab.png")
    c.check(shot and color_share(shot, (125, 80, 45), 45, (0.3, 0.2, 0.7, 0.8)) > 0.05, "the screenshot shows the crate held up in front", shot)

    # Holding the crate, the mouse is let go (Escape, or another window); the click on the game that locks it again
    # isn't a throw. The next click (locked) is.
    r = play("ix_relock", game("ix_grab.tuf"), look + [
        {"at": 1.6, "key": "e"}, {"at": 2.0, "dump": "ixr_held.json"}, {"at": 2.05, "lock": False},
        {"at": 2.1, "click_center": True}, {"at": 2.5, "dump": "ixr_relocked.json"},
        {"at": 2.6, "lock": True}, {"at": 2.7, "click_center": True}, {"at": 3.0, "dump": "ixr_thrown.json"},
        {"at": 3.1, "close": True}])
    clean_exit(c, r)
    held, relocked, thrown = (ix(r.dumps.get(f"ixr_{n}.json", {})).get("held") for n in ("held", "relocked", "thrown"))
    c.check(held == "crate" and relocked == "crate", "the click that locks the mouse again doesn't throw the crate", (held, relocked))
    c.check(thrown is None, "the next click throws it", thrown)


def t_ix_talk(c):
    """npc:say and npc:on_talk: a speech bubble over a person (for 4 s, or for good with 0), "E: Talk" near someone
    with an on_talk and E runs it; E talks first, then opens a door in reach, then grabs."""
    r = play("ix_talk", game("ix_talk.tuf"), [
        {"at": 0.8, "dump": "ixt_start.json"}, {"at": 0.85, "shot": "ix_talk.png"},
        {"at": 1.0, "key": "e"}, {"at": 1.3, "dump": "ixt_talked.json"}, {"at": 1.35, "shot": "ix_talk_thanks.png"},
        {"at": 1.4, "call": "short"}, {"at": 1.6, "dump": "ixt_short.json"}, {"at": 2.8, "dump": "ixt_gone.json"},
        {"at": 2.9, "call": "leave"}, {"at": 3.1, "dump": "ixt_door.json"}, {"at": 3.15, "key": "e"},
        {"at": 3.5, "dump": "ixt_opened.json"},
        {"at": 3.6, "call": "no_door"}, {"at": 3.7, "lock": True}, {"at": 3.75, "look": [0, 250]},
        {"at": 4.5, "dump": "ixt_grab.json"}, {"at": 4.6, "close": True}])
    clean_exit(c, r)
    start = ix(r.dumps.get("ixt_start.json", {}))
    c.check(start.get("bubbles") == ["Hi! Find my lost cat.", "I'm too far away to talk to."], "npc:say shows a speech bubble over each one", start)
    c.check(start.get("hint") == "E: Talk", "near someone with an on_talk (and a door and a crate), the hint says \"E: Talk\"", start.get("hint"))
    talked = ix(r.dumps.get("ixt_talked.json", {}))
    c.check("talked 1" in r.lines and "the far one talked" not in r.lines, "E runs the near one's on_talk (not the far one's)", r.lines[-3:])
    c.check("Thanks! It ran into the woods." in talked.get("bubbles", []) and "Hi! Find my lost cat." not in talked.get("bubbles", []),
            "saying something new changes the bubble", talked)
    c.check("Bye!" in ix(r.dumps.get("ixt_short.json", {})).get("bubbles", []) and
            ix(r.dumps.get("ixt_gone.json", {})).get("bubbles") == ["I'm too far away to talk to."],
            "npc:say(text, 1) goes after a second; npc:say(text, 0) stays", (ix(r.dumps.get("ixt_short.json", {})), ix(r.dumps.get("ixt_gone.json", {}))))
    door = ix(r.dumps.get("ixt_door.json", {}))
    c.check(door.get("hint") == "E: Open", "with nobody to talk to, a door in reach comes next: \"E: Open\"", door.get("hint"))
    opened = ix(r.dumps.get("ixt_opened.json", {}))
    c.check(opened.get("doors") and opened["doors"][0]["open"] and opened.get("hint") == "E: Close",
            "E opens it (and then the hint says \"E: Close\")", opened)
    c.check(ix(r.dumps.get("ixt_grab.json", {})).get("hint") == "E: Grab", "with no door either, looking at the crate: \"E: Grab\"",
            ix(r.dumps.get("ixt_grab.json", {})).get("hint"))
    shot = r.shots.get("ix_talk.png")
    c.check(shot and color_share(shot, (255, 255, 255), 8, (0.3, 0.0, 0.7, 0.5)) > 0.01, "the screenshot shows a white speech bubble over the person", shot)
    shot = r.shots.get("ix_talk_thanks.png")
    c.check(shot and color_share(shot, (255, 255, 255), 10, (0.44, 0.84, 0.56, 0.9)) > 0.01, "and the \"E: Talk\" hint at the bottom", shot)

    # games/ix_note.tuf: E talks to a sign, whose on_talk shows a note; the next E hides it in on_key, and only that.
    # Then the same with a note that doesn't pause the game (calm).
    for name, calm, what in (("ix_note", [], ""), ("ix_note_calm", [{"at": 0.5, "call": "calm"}], " (a note that doesn't pause the game)")):
        r = play(name, game("ix_note.tuf"), calm + [
            {"at": 0.8, "dump": "ixn_start.json"},
            {"at": 1.0, "key": "e"}, {"at": 1.3, "call": "report"},
            {"at": 1.5, "key": "e"}, {"at": 1.8, "call": "report"}, {"at": 1.85, "dump": "ixn_hidden.json"},
            {"at": 2.0, "call": "to_door"}, {"at": 2.2, "key": "e"}, {"at": 2.7, "call": "report"}, {"at": 2.75, "dump": "ixn_door.json"},
            {"at": 2.9, "key": "e"}, {"at": 3.4, "dump": "ixn_opened.json"}, {"at": 3.5, "close": True}])
        clean_exit(c, r)
        start = r.dumps.get("ixn_start.json", {})
        if not calm:
            c.check(ix(start).get("hint") == "E: Talk" and "E: Talk" in start.get("hud_texts", []) and "Talks: 0" in start.get("hud_texts", []),
                    "a HUD cleared and drawn again every frame (hud:clear) keeps the \"E: Talk\" hint", (ix(start).get("hint"), start.get("hud_texts")))
        talks = [line for line in r.lines if line.startswith("talks ")]
        c.check(talks[:1] == ["talks 1, note shown true"], f"E talks to the sign, and its on_talk shows a note{what}", talks)
        c.check(talks[1:2] == ["talks 1, note shown false"] and "talk 2" not in r.lines,
                f"the E that hides the note (in on_key) only hides it: it doesn't talk again and show the note again{what}", talks)
        c.check("E: Talk" in r.dumps.get("ixn_hidden.json", {}).get("hud_texts", []), f"and the hint is back once the note is gone{what}",
                r.dumps.get("ixn_hidden.json", {}).get("hud_texts"))
        door = ix(r.dumps.get("ixn_door.json", {})).get("doors") or [{}]
        c.check(talks[2:3] == ["talks 1, note shown false"] and not door[0].get("open"),
                f"next to a door, the E that hides the note doesn't open the door too{what}", (talks, door))
        opened = ix(r.dumps.get("ixn_opened.json", {})).get("doors") or [{}]
        c.check(opened[0].get("open"), f"the next E opens it{what}", opened)


def t_ix_door(c):
    """world:door: walking into it swings it open away from the player, the player walks through and it shuts again;
    a door that needs a key says "Locked!" with the key's name and is in the player's way until the player walks into
    the key (it disappears), then E opens it; door:turn, door:open() (pushing a physics crate), door:close(), door:lock()
    (in the way again) and door:unlock()."""
    r = play("ix_door", game("ix_door.tuf"), [
        {"at": 0.6, "dump": "ixd_start.json"},
        {"at": 0.8, "hold": "w", "for": 1.4}, {"at": 1.6, "dump": "ixd_opening.json"},
        {"at": 2.4, "call": "report"}, {"at": 2.45, "dump": "ixd_through.json"}, {"at": 2.5, "tuff": "player:turn_to(180)"},
        {"at": 2.7, "shot": "ix_door_open.png"},
        {"at": 6.6, "dump": "ixd_shut.json"},
        {"at": 6.7, "tuff": "player:move_to(6, 0, 2.2)"}, {"at": 6.8, "tuff": "player:turn_to(0)"},
        {"at": 7.0, "key": "e"}, {"at": 7.2, "dump": "ixd_locked.json"}, {"at": 7.25, "shot": "ix_door_locked.png"},
        {"at": 7.3, "hold": "w", "for": 0.8}, {"at": 8.2, "dump": "ixd_gate_wall.json"},
        {"at": 8.3, "tuff": "player:move_to(3, 0, 4)"}, {"at": 8.6, "dump": "ixd_key.json"},
        {"at": 8.7, "tuff": "player:move_to(6, 0, 2.2)"}, {"at": 8.9, "key": "e"}, {"at": 9.8, "dump": "ixd_unlocked.json"},
        {"at": 9.85, "shot": "ix_door_gate.png"},
        {"at": 9.9, "call": "push_crate"}, {"at": 10.9, "dump": "ixd_side.json"}, {"at": 11.0, "call": "shut_side"},
        {"at": 11.1, "call": "lock_door"}, {"at": 11.2, "tuff": "player:move_to(0, 0, 2.2)"}, {"at": 11.4, "key": "e"},
        {"at": 11.6, "dump": "ixd_relocked.json"}, {"at": 11.7, "hold": "w", "for": 0.8}, {"at": 12.6, "dump": "ixd_door_wall.json"},
        {"at": 12.65, "tuff": "player:move_to(0, 0, 2.2)"}, {"at": 12.7, "call": "unlock_door"}, {"at": 12.8, "key": "e"},
        {"at": 13.4, "dump": "ixd_reopened.json"}, {"at": 13.5, "close": True}])
    clean_exit(c, r)
    doors = lambda name: ix(r.dumps.get(name, {})).get("doors") or [{}, {}, {}]
    start = doors("ixd_start.json")
    c.check(len(start) == 3 and all(d["angle"] == 0 and not d["open"] for d in start) and start[1]["locked"] and not start[0]["locked"],
            "three doors start shut; the one that needs a key is locked", start)
    opening = doors("ixd_opening.json")[0]
    c.check(opening.get("open") and opening.get("angle", 0) < -40, f"walking into a door swings it open, away from the player (angle {opening.get('angle')})", opening)
    through = (r.dumps.get("ixd_through.json", {}).get("player") or [0, 0, 0])
    c.check(through[2] < -1.5, f"the player walks through the doorway (z {through[2]})", through)
    shut = doors("ixd_shut.json")[0]
    c.check(not shut.get("open") and shut.get("angle") == 0, "a few seconds after the player's gone through, it shuts again", shut)
    locked = r.dumps.get("ixd_locked.json", {})
    c.check(ix(locked).get("note") == "Locked! You need the gold key." and not doors("ixd_locked.json")[1].get("open"),
            "E at a locked door says \"Locked!\" and the key's name, and it stays shut", ix(locked).get("note"))
    wall = r.dumps.get("ixd_gate_wall.json", {}).get("player") or [0, 0, 0]
    c.check(wall[2] > 0.3 and not doors("ixd_gate_wall.json")[1].get("open"),
            f"walking into it doesn't get the player through: a shut door is in the way (z {wall[2]}, the door's at 0)", wall)
    key = ix(r.dumps.get("ixd_key.json", {}))
    c.check(key.get("keys") == ["key"] and key.get("note") == "You got the gold key!" and not doors("ixd_key.json")[1].get("locked"),
            "walking into the key picks it up (and the door it opens isn't locked any more)", key)
    objs = [o for o in r.dumps.get("ixd_key.json", {}).get("objects", []) if o[0] == "key"]
    c.check(objs and "gold key" not in r.dumps.get("ixd_key.json", {}).get("labels", ["gold key"]) or objs, "the key is still the program's, hidden", objs)
    gate = doors("ixd_unlocked.json")[1]
    c.check(gate.get("open") and abs(gate.get("angle", 0)) > 90, "then E opens it", gate)
    side = doors("ixd_side.json")[2]
    crate = (bodies(r.dumps.get("ixd_side.json", {}), "crate") or [None])[0]
    c.check(side.get("open") and crate and (abs(crate[1] + 6.6) > 0.3 or abs(crate[3] + 0.4) > 0.3),
            f"door:open() on a turned door swings it, and it pushes a physics crate out of its way ({crate})", (side, crate))
    relocked = r.dumps.get("ixd_relocked.json", {})
    c.check(doors("ixd_relocked.json")[0].get("locked") and not doors("ixd_relocked.json")[0].get("open") and ix(relocked).get("note") == "Locked!",
            "door:lock() locks it (E says \"Locked!\")", (doors("ixd_relocked.json")[0], ix(relocked).get("note")))
    wall = r.dumps.get("ixd_door_wall.json", {}).get("player") or [0, 0, 0]
    c.check(wall[2] > 0.3 and not doors("ixd_door_wall.json")[0].get("open"),
            f"... and walking into it, the player stays in front of it (z {wall[2]})", wall)
    c.check(doors("ixd_reopened.json")[0].get("open"), "door:unlock() and it opens again", doors("ixd_reopened.json")[0])
    shot = r.shots.get("ix_door_open.png")
    c.check(shot and color_share(shot, (110, 75, 40), 45, (0.2, 0.1, 0.8, 0.9)) > 0.02, "the screenshot shows the wooden door open behind the player", shot)
    shot = r.shots.get("ix_door_locked.png")
    c.check(shot and color_share(shot, (229, 72, 77), 50, (0.2, 0.0, 0.8, 0.9)) > 0.05, "the locked one is red, shut in front of the player", shot)
    code, _, err, d, _ = scene(game("ix_door.tuf"))
    things = {t.get("var"): t for t in d.get("things", [])}
    c.check(code == 0 and d.get("stopped") == "end" and all(things.get(v, {}).get("kind") == "door" for v in ("door", "gate", "side"))
            and things.get("key", {}).get("kind") == "key" and len(things.get("door", {}).get("ids", [])) > 10,
            "Tuff Engine's preview shows the doors (with their swinging part) and the key", (code, err[-300:], list(things)))


def t_editor(c):
    import tuff_tgame
    lang = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")
    try:
        p = subprocess.run(["node", "-e", LOAD_LANG, lang], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the editor checks")
        return
    t = json.loads(p.stdout)
    tables = tuff_tgame.tables()
    c.check(sorted(t["libs"].get("tgame", {})) == sorted(tables["lib"]), "TUFF_LIBS has tgame.window and tgame.world", t["libs"].get("tgame"))
    c.check("tgame" in t["docs"], "TUFF_DOCS explains mention tgame", None)
    names = sorted({m for kind in tables["kinds"].values() for m in kind})
    missing = [m for m in names if m not in t["methods"]]
    c.check(not missing, f"every tgame method ({len(names)}) has hover docs", missing)
    shared = [m for m in names if m in t["methods"] and "tgame" not in t["methods"][m][1] and "tgame" not in t["methods"][m][0]]
    c.check(not shared, "names tgame shares with tgui and tap mention what they do in tgame", shared)
    c.check("button" in t["plain"] and "frame" not in t["plain"] and "spawn" not in t["plain"],
            "after app: in a file without tgame, the list leaves out tgame's own methods", [m for m in t["plain"] if m in ("frame", "spawn", "button")])
    c.check("frame" in t["games"] and "spawn" in t["games"] and "button" in t["games"], "in a tgame file it offers them all", len(t["games"]))
    ui = ("panel", "screen", "start_screen", "shown")
    c.check(all(m in t["methods"] and "tgame" in t["methods"][m][1] for m in ui), "game:panel, :screen, :start_screen and :shown have tgame hover docs",
            [m for m in ui if m not in t["methods"]])
    c.check(all(m in t["games"] for m in ui), "a tgame file offers them after a ':'", [m for m in ui if m not in t["games"]])
    intro = ("splash", "main_menu", "lock_mouse", "unlock_mouse", "mouse_locked", "auto_lock")
    c.check(all(m in t["methods"] and t["methods"][m][1].startswith("tgame") for m in intro) and all(m in t["games"] for m in intro)
            and not any(m in t["plain"] for m in intro),
            "game:splash, :main_menu and the world's mouse methods have tgame hover docs, offered in tgame files only",
            [m for m in intro if m not in t["methods"] or m not in t["games"] or m in t["plain"]])
    # The physics methods, from the checker's own tables (they're there before tgame's tables list them).
    import tuff
    physics = sorted({m for kind in tuff.PHYSICS_INPUTS.values() for m in kind})
    c.check(all(m in t["methods"] and "tgame" in t["methods"][m][1] for m in physics), f"tgame's physics methods ({len(physics)}: physics, push, on_hit, car...) have tgame hover docs",
            [m for m in physics if m not in t["methods"] or "tgame" not in t["methods"][m][1]])
    c.check(all(m in t["games"] for m in physics) and not any(m in t["plain"] for m in ("physics", "push", "ragdoll")),
            "a tgame file offers them after a ':', and a file without tgame doesn't", [m for m in physics if m not in t["games"]])
    c.check("In tgame:" in t["methods"]["animate"][1] and "In atgui:" in t["methods"]["animate"][1], ":animate's hover says what it does in tgame and in atgui", t["methods"]["animate"])
    # The game kit's names, from the checker's own tables too (before and after tgame's tables list them).
    kit = sorted({m for kind in tuff.KIT_INPUTS.values() for m in kind})
    c.check(all(m in t["methods"] and "tgame" in t["methods"][m][1] for m in kit), f"the game kit's methods ({len(kit)}: slow_mo, health_bar, countdown, door, path...) have tgame hover docs",
            [m for m in kit if m not in t["methods"] or "tgame" not in t["methods"][m][1]])
    c.check(all(m in t["games"] for m in kit) and not any(m in t["plain"] for m in ("slow_mo", "minimap", "jump_pad", "can_grab")),
            "a tgame file offers them after a ':', and a file without tgame doesn't", [m for m in kit if m not in t["games"]])
    c.check("textarea" in t["ui"] and "switch" in t["ui"] and "textarea" not in t["games"],
            "with a panel or screen in it, a tgame file offers atgui's widgets too (and only then)", [m for m in ("textarea", "switch") if m not in t["ui"]])
    games = [(label, text) for label, text in t["snippets"] if label.startswith("tgame")]
    c.check(len(games) == 2, "there are 2D and 3D starter snippets", [g[0] for g in games])
    import re
    folder = os.path.join(OUT, "snippets")
    os.makedirs(folder, exist_ok=True)
    for label, text in games:
        code = re.sub(r"\$\{\d+:([^}]*)\}", r"\1", text).replace("$0", "nil")
        path = os.path.join(folder, label.replace(" ", "_") + ".tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(r.returncode == 0, f"the '{label}' snippet passes --check", (r.stdout + r.stderr)[:400])
        run = play(label.replace(" ", "_"), path, [{"at": 0.6, "shot": label.replace(" ", "_") + ".png"}, {"at": 0.8, "close": True}])
        c.check(run.code == 0 and "Tuff error" not in run.err, f"and runs ({run.seconds:.1f} s)", run.err[-400:])


def pop_sizes(text):
    """The sizes pop_text is given in some code or docs: the number after its color, like the 40 in
    world:pop_text("+10", coin:spot(), "gold", 40)."""
    import re
    sizes = []
    for m in re.finditer(r":pop_text\(", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        size = re.search(r'"[^"]*"\s*,\s*(-?[\d.]+)\s*$', text[m.end():i - 1])
        if size:
            sizes.append(float(size.group(1)))
    return sizes


def t_guide(c):
    """Every example in the guide's tgame section passes --check and runs (a window opens and is closed), and every
    place that teaches pop_text gives it a size in pixels."""
    import re
    # pop_text's size is how tall the text is on screen, in pixels (34 is normal in 3D, 32 in 2D): 2 is a dash.
    js = os.path.join(REPO, "tuffcode", "renderer", "js")
    taught = {"the guide": os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md"), "the hover docs": os.path.join(js, "tuff-lang.js"),
              "the examples": os.path.join(js, "tuff-templates.js"), "What's New": os.path.join(js, "whats-new.js")}
    taught.update({f"games/{n}": os.path.join(GAMES, n) for n in os.listdir(GAMES) if n.endswith(".tuf")})
    sizes = {where: pop_sizes(open(path, encoding="utf-8").read()) for where, path in taught.items()}
    sizes["the checker's good snippets"] = pop_sizes("\n".join(GOOD_SNIPPETS))
    small = {where: s for where, s in sizes.items() if any(v < 8 for v in s)}
    c.check(sum(len(s) for s in sizes.values()) >= 6 and not small,
            f"pop_text's size is in pixels wherever it's taught ({sum(len(s) for s in sizes.values())} sizes, none under 8)", small)
    guide = open(os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md"), encoding="utf-8").read()
    start = guide.find("\n### tgame")
    end = guide.find("\n## ", start + 1)
    section = guide[start:end] if start >= 0 else ""
    blocks = re.findall(r"```tuff\n(.*?)```", section, re.S)
    c.check(len(blocks) >= 3, f"the guide has a tgame section with examples ({len(blocks)})", len(blocks))
    folder = os.path.join(GAMES)  # next to star.png and blip.wav, like a project
    for i, code in enumerate(blocks, 1):
        path = os.path.join(folder, f"_guide_{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            r = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
            c.check(r.returncode == 0, f"guide example {i} passes --check", (r.stdout + r.stderr)[:500])
            run = play(f"guide_{i}", path, [{"at": 0.3, "key": "space"}, {"at": 0.5, "click_center": True},
                                             {"at": 0.9, "shot": f"guide_{i}.png"}, {"at": 1.2, "close": True}])
            c.check(run.code == 0 and "Tuff error" not in run.err and "Traceback" not in run.err,
                    f"guide example {i} runs ({run.seconds:.1f} s)", run.err[-500:])
        finally:
            os.remove(path)


# ---------------------------------------------------------------- the checker

GOOD = ["snake.tuf", "breakout.tuf", "snake3d.tuf", "axe_sim.tuf", "features_2d.tuf", "features_3d.tuf", "player_3d.tuf",
        "perf_2d.tuf", "perf_2d_speed.tuf", "perf_3d.tuf", "perf_3d_move.tuf", "callback.tuf", "errors.tuf", "top_error.tuf",
        "churn.tuf", "pause_key.tuf", "hud_3d.tuf", "terrain_walk.tuf", "terrain_look.tuf", "terrain_dig.tuf",
        "ui_2d.tuf", "ui_3d.tuf", "physics_drop.tuf", "physics_tower.tuf", "physics_player.tuf", "physics_car.tuf",
        "physics_ragdoll.tuf", "physics_2d.tuf",
        "fx_slow_mo.tuf", "fx_shake_pop.tuf", "fx_weather.tuf", "fx_day.tuf", "fx_2d.tuf",
        "ix_grab.tuf", "ix_talk.tuf", "ix_door.tuf", "ix_note.tuf",
        "level_pads.tuf", "level_lift.tuf", "level_lift_physics.tuf",
        "menu_2d.tuf", "menu_3d.tuf", "menu_start.tuf",
        "net_host.tuf", "net_join.tuf", "net_host_2d.tuf", "net_join_2d.tuf", "net_room.tuf"]
BAD = [
    ('world = tgame.world("x")\nd = world:door(0, 0, 0)\nd:shut()\n', "A door doesn't have :shut. Use :close instead."),
    ('world = tgame.world("x")\nworld:door(0, 0, 0, "purpel")\n', "'purpel' isn't a color tgame knows."),
    ('world = tgame.world("x")\np = world:player()\np:pick_up()\n', "A player doesn't have :pick_up. Use :can_grab instead."),
    ('game = tgame.window("x")\ngame:rect(1, 2)\n', "A game doesn't have :rect. Use :box instead."),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:moov(1, 2)\n', "A sprite doesn't have :moov. Did you mean :move?"),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:move(1, 2, 3)\n', "sprite:move got the wrong number of inputs (3)."),
    ('game = tgame.window("x")\ngame:box(1, 2, 3, 4, "redd")\n', "'redd' isn't a color tgame knows."),
    ('game = tgame.window("x")\ngame:background "bleu"\n', "'bleu' isn't a color tgame knows."),
    ('game = tgame.window("x")\nif game:held("spacee"):\n    say 1\n', "'spacee' isn't a key tgame knows."),
    ('game = tgame.window("x")\ngame:sound "kaboom"\n', "'kaboom' isn't one of tgame's sounds"),
    ('game = tgame.window("x")\ngame:sound "missing.wav"\n', "Couldn't find the sound 'missing.wav'."),
    ('game = tgame.window("x")\ngame:image("nope.png", 1, 2)\n', "Couldn't find the picture 'nope.png'."),
    ('game = tgame.window("x")\ngame:image("cat.txt", 1, 2)\n', "'cat.txt' isn't a picture file tgame can use."),
    # The game window only loads files from the .tuf's folder and the folders inside it. These files are there
    # (out/checker/../../games), but outside: they'd fail when the game runs.
    ('game = tgame.window("x")\ngame:image("../../games/star.png", 1, 2)\n',
     "The picture '../../games/star.png' has to be next to your .tuf file, or in a folder inside it."),
    ('game = tgame.window("x")\ngame:sound "../../games/blip.wav"\n', "The sound '../../games/blip.wav' has to be next to your .tuf file"),
    ('w = tgame.world("x")\nw:spawn("art/../../../games/tower.glb")\n', "The model 'art/../../../games/tower.glb' has to be next to your .tuf file"),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:on_edge "bonce"\n', ":on_edge can be \"bounce\""),
    ('w = tgame.world("x")\nw:sky "sunny"\n', "The sky can be day, sunset, dawn, night, cloudy, space"),
    ('w = tgame.world("x")\nw:spawn("palm")\n', "tgame doesn't have a \"palm\" to spawn."),
    ('w = tgame.world("x")\nw:player "second person"\n', "The player can be \"first person\" or \"third person\""),
    ('w = tgame.world("x")\np = w:player()\np:hold "bow"\n', "The player can hold: axe"),
    ('w = tgame.world("x")\nw:circle(1, 2, 3)\n', "A world doesn't have :circle."),
    ('w = tgame.world("x")\nw:cube(1, 2, 3)\n', "A world doesn't have :cube. Use :box instead."),
    ('w = tgame.world("x")\nt = w:spawn("tree")\nt:chop()\n', "An object doesn't have :chop. Use :shake instead."),
    ('w = tgame.world("x")\np = w:player()\np:speed(3)\n', "A player doesn't have :speed. Use :walk_speed instead."),
    ('game = tgame.window("x")\ngame:every_frame(step())\nfunc step(dt):\n    nil\n', "Pass the function's name without brackets: step, not step()."),
    ('game = tgame.window("x")\ngame:every_frame step\nfunc step(a, b):\n    nil\n', "step() needs 2 inputs, but game:every_frame gives it 1 input"),
    ('game = tgame.window("x")\ngame:on_key("space", jump)\nfunc jump(a, b):\n    nil\n', "jump() needs 2 inputs, but game:on_key gives it 1 input"),
    ('game = tgame.window("x")\ngame:clicked hit\nfunc hit(a, b, c):\n    nil\n', "hit() needs 3 inputs, but game:clicked gives it 2 inputs"),
    ('w = tgame.world("x")\nt = w:box(0, 0, 0)\nt:clicked hit\nfunc hit(a, b):\n    nil\n', "hit() needs 2 inputs, but t:clicked gives it 1 input"),
    ('game = tgame.window("x")\ngame:after(1, "done")\n', "This needs a function name, not text."),
    ('game = tgame.window("x")\ngame:every_frame step\nfunc step(dt):\n    wait(1)\n', "wait() freezes the game"),
    ('game = tgame.window("x")\ngame:every_frame step\n', "I don't know what 'step' is."),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:remove 5\n', "b:remove doesn't take an input"),
    ('things = []\nfor t in things:\n    t:wobble()\n', "Nothing in Tuff has :wobble."),
    ('game = tgame.window("x")\nx = game:frame()\nx:add(1)\n', "A number doesn't have any :methods."),
    ('game = tgame.window("x")\nhud = game:hud()\nhud:sky "day"\n', "A hud doesn't have :sky."),
    ('game = tgame.window("x")\ng = game:group()\ng:append(game:box(1, 2))\n', "A group doesn't have :append."),
    ('game = tgame.windw("x")\n', "tgame doesn't have 'windw'. It has: window, world."),
    ('game = tgame.window(1, 2, 3, 4)\n', "tgame.window() got the wrong number of inputs (4)."),
    # The land and the lighting
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:style "gras"\n',
     "The land's style can be grass, desert, snow, rocky or autumn, not \"gras\". Did you mean \"grass\"?"),
    ('w = tgame.world("x")\nland = w:terrain(100, "beach")\n', "The land's style can be grass, desert, snow, rocky or autumn"),
    ('w = tgame.world("x")\nw:lighting "modren"\n', "The lighting can be \"simple\" or \"modern\", not \"modren\". Did you mean \"modern\"?"),
    ('w = tgame.world("x")\nland = w:terrain()\nland:hil(1, 2)\n', "A terrain doesn't have :hil. Did you mean :hill?"),
    ('w = tgame.world("x")\nland = w:terrain()\nland:pond(1, 2)\n', "A terrain doesn't have :pond. Use :lake instead."),
    ('w = tgame.world("x")\nland = w:terrain()\nland:hill(1, 2, 3, 4, 5)\n', "land:hill needs 4 inputs (x, z, size and height), but got 5."),
    ('w = tgame.world("x")\nland = w:terrain()\nland:water()\n', "land:water needs 1 input (the sea's height), but got 0."),
    ('w = tgame.world("x")\nw:land(100)\n', "A world doesn't have :land. Use :terrain instead."),
    # The land (world:terrain) and the lighting: names with "did you mean", each method's input count (a brush
    # stroke is a list of spots in place of x and z), and one terrain per world.
    ('w = tgame.world("x")\nw:lighting "realistic"\n', 'The lighting can be "simple" or "modern", not "realistic". Did you mean "modern"?'),
    ('w = tgame.world("x")\nw:lighting "modrn"\n', 'not "modrn". Did you mean "modern"?'),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:style "sandy"\n',
     'The land\'s style can be grass, desert, snow, rocky or autumn, not "sandy". Did you mean "desert"?'),
    ('w = tgame.world("x")\nland = w:terrain(100, "gras")\n', 'not "gras". Did you mean "grass"?'),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:style "lava"\n', 'The land\'s style can be grass, desert, snow, rocky or autumn, not "lava".'),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:hill(20, -10, 30)\n', "land:hill needs 4 inputs (x, z, size and height), but got 3."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:valley(-60, 0, 60, 10, 18)\n', "land:valley needs 6 inputs (x1, z1, x2, z2, width and depth), but got 5."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:smooth(5, 5, 8, 2)\n', "land:smooth needs 3 inputs (x, z and size), but got 4."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:raise([[1, 2], [3, 2]], 8)\n', "land:raise needs 3 inputs here (the spots, size and amount), but got 2."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:flatten([[1, 2], [3, 2]], 1, 8, 0)\n', "land:flatten needs 3 inputs here (the spots, size and height), but got 4."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:water()\n', "land:water needs 1 input (the sea's height), but got 0."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:pond(1, 2, 3, 4)\n', "A terrain doesn't have :pond. Use :lake instead."),
    ('w = tgame.world("x")\nland = w:terrain(100)\nland:hils(1, 2, 3, 4)\n', "A terrain doesn't have :hils. Did you mean :hill?"),
    ('w = tgame.world("x")\nland = w:terrain(100)\nw:terrain(50)\n',
     "A world has one terrain, and line 3 already made it. Change it with land:hill, land:raise and so on."),
    ('w = tgame.world("x")\nw:landscape(100)\n', "A world doesn't have :landscape. Use :terrain instead."),
    ('w = tgame.world("x")\nw:terrain(100, "grass", 3)\n', "world:terrain got the wrong number of inputs (3)."),
    ('game = tgame.window("x")\ngame:terrain(100)\n', "A game doesn't have :terrain."),
    ('game = tgame.window("x")\ngame:panel "top lft"\n', 'not "top lft". Did you mean "top left"?'),
    ('w = tgame.world("x")\nw:panel("middle", 3)\n', "w:panel got the wrong number of inputs (2)."),
    ('game = tgame.window("x")\ngame:menu "Shop"\n', "A game doesn't have :menu. Use :main_menu instead."),
    ('w = tgame.world("x")\nw:title_screen "Go"\n', "A world doesn't have :title_screen. Use :splash instead."),
    # Menus, buttons and screens: where a panel goes (with "did you mean"), the inputs of game:panel, game:screen
    # and game:start_screen, the widgets on them (checked like atgui's), and widgets asked of the game or the HUD.
    ('game = tgame.window("x")\nbar = game:panel("top-centre")\n',
     'A panel can go at "top left", "top", "top right", "left", "center", "right", "bottom left", "bottom" or "bottom right", '
     'not "top-centre". Did you mean "top"?'),
    ('game = tgame.window("x")\nbar = game:panel("middel")\n', 'not "middel". Did you mean "center"?'),
    ('w = tgame.world("x")\nbar = w:panel("upper right")\n', 'not "upper right". Did you mean "top right"?'),
    ('game = tgame.window("x")\nbar = game:panel("sideways")\n', 'A panel can go at "top left"'),
    ('game = tgame.window("x")\nbar = game:panel("top", "left")\n', "game:panel got the wrong number of inputs (2)."),
    ('game = tgame.window("x")\nbar = game:panel(10)\n', "A panel's input is where it goes, written as text"),
    ('game = tgame.window("x")\nshop = game:screen("Shop", "no")\n', "A screen's second input is whether it pauses the game while it shows: true or false"),
    ('game = tgame.window("x")\nshop = game:screen("Shop", true, 3)\n', "game:screen got the wrong number of inputs (3)."),
    ('game = tgame.window("x")\nfunc go():\n    nil\nshop = game:screen(go)\n', "A screen's first input is its title"),
    ('w = tgame.world("x")\nfunc go():\n    nil\nstart = w:start_screen("Go", go)\n',
     "A start screen takes a title and a hint, both text, like: start = w:start_screen(\"My Game\", \"Click to play\")."),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nbar:buton("Shop")\n', "A panel doesn't have :buton. Did you mean :button?"),
    ('game = tgame.window("x")\nshop = game:screen("Shop")\nshop:shwo()\n', "A screen doesn't have :shwo. Did you mean :show?"),
    ('w = tgame.world("x")\nstart = w:start_screen("Go")\nstart:opn()\n', "A screen doesn't have :opn."),
    ('game = tgame.window("x")\nshop = game:screen("Shop")\nshop:close()\n', "A screen doesn't have :close. Use :hide instead."),
    ('game = tgame.window("x")\nshop = game:screen("Shop")\nif shop:visible():\n    nil\n', "A screen doesn't have :visible. Use :shown instead."),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nb = bar:button("Shop")\nb:wobble()\n', "A button doesn't have :wobble."),
    ('game = tgame.window("x")\nshop = game:screen("Shop")\nbox = shop:input("Name")\nbox:set(1, 2)\n', "input:set got the wrong number of inputs (2)."),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nbar:button("Shop", go, "shiny")\nfunc go():\n    nil\n', "'shiny' isn't a button style."),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nbar:button("Shop", go)\nfunc go(a, b):\n    nil\n',
     "go() needs 2 inputs, but a button click only gives it 1"),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nbar:button("Shop", go())\nfunc go():\n    nil\n',
     "Pass the function's name without brackets: go, not go()."),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nbar:button("Shop", go)\nfunc go():\n    wait(1)\n',
     "wait() freezes the game: nothing moves or redraws until it's over. To do something later, use game:after(seconds, fn)."),
    ('game = tgame.window("x")\nbar = game:panel("top left")\nbar:icon "hom"\n', "There's no icon called 'hom'. Did you mean \"home\"?"),
    ('game = tgame.window("x")\ngame:button("Shop")\n',
     "A game doesn't have :button. Buttons, text boxes and other widgets go on a panel or a screen: bar = game:panel(\"top left\"), then bar:button(...)"),
    ('w = tgame.world("x")\nw:slider(0, 10, 5)\n', "A world doesn't have :slider. Buttons, text boxes and other widgets go on a panel or a screen"),
    ('game = tgame.window("x")\nhud = game:hud()\nhud:button("Shop")\n', "A hud doesn't have :button. The HUD only draws."),
    ('game = tgame.window("x")\ngame:menu("Shop")\n', "A game doesn't have :menu. Use :main_menu instead."),
    ('w = tgame.world("x")\nw:title_screen("Go")\n', "A world doesn't have :title_screen. Use :splash instead."),
    # Splash screens, main menus and the mouse: names people guess, each one's inputs, and the mouse in a 2D game.
    ('game = tgame.window("x")\ngame:intro("logo.png")\n', "A game doesn't have :intro. Use :splash instead."),
    ('w = tgame.world("x")\nhome = w:home_screen("Go")\n', "A world doesn't have :home_screen. Use :main_menu instead."),
    ('game = tgame.window("x")\ngame:splash("nope.png")\n', "Couldn't find the picture 'nope.png'."),
    ('game = tgame.window("x")\ngame:splash("intro.mp4", 3)\n', "'intro.mp4' can't be a splash screen. Use a picture from your project folder"),
    ('game = tgame.window("x")\nfunc go():\n    nil\ngame:splash(go)\n', "game:splash takes a picture file or some text, then how many seconds it shows"),
    ('game = tgame.window("x")\ngame:splash("Pip Studio", "long")\n', "game:splash's second input is how many seconds it shows: a number above 0"),
    ('w = tgame.world("x")\nw:splash("Pip Studio", 0)\n', "w:splash's second input is how many seconds it shows: a number above 0"),
    ('game = tgame.window("x")\ngame:splash("a", 2, 3)\n', "game:splash got the wrong number of inputs (3)."),
    ('game = tgame.window("x")\nmenu = game:main_menu("Go", "Play")\n',
     'game:main_menu got the wrong number of inputs (2). It takes its title, like: menu = game:main_menu("My Game")'),
    ('w = tgame.world("x")\nfunc play():\n    nil\nmenu = w:main_menu(play)\n', "A main menu's input is its title, like: menu = w:main_menu(\"My Game\")."),
    ('game = tgame.window("x")\nmenu = game:main_menu("Go")\nmenu:buton("Play")\n', "A screen doesn't have :buton. Did you mean :button?"),
    ('game = tgame.window("x")\nmenu = game:main_menu("Go")\nmenu:close()\n', "A screen doesn't have :close. Use :hide instead."),
    ('w = tgame.world("x")\nw:release_mouse()\n', "A world doesn't have :release_mouse. Use :unlock_mouse instead."),
    ('w = tgame.world("x")\nw:capture_mouse()\n', "A world doesn't have :capture_mouse. Use :lock_mouse instead."),
    ('w = tgame.world("x")\nw:hide_cursor()\n', "A world doesn't have :hide_cursor. Use :lock_mouse instead."),
    ('w = tgame.world("x")\nif w:is_locked():\n    nil\n', "A world doesn't have :is_locked. Use :mouse_locked instead."),
    ('w = tgame.world("x")\nw:lock_mouse true\n', "w:lock_mouse doesn't take an input"),
    ('w = tgame.world("x")\nw:auto_lock "off"\n', "w:auto_lock takes true or false (without quotes), like: w:auto_lock(false)"),
    ('w = tgame.world("x")\nlocked = w:mouse_locked()\nlocked:add(1)\n', "True/false doesn't have any :methods."),
    ('game = tgame.window("x")\ngame:lock_mouse()\n', "Locking the mouse is for looking around in a 3D world. Make the game with tgame.world(...)"),
    ('game = tgame.window("x")\nif game:mouse_locked():\n    nil\n', "Locking the mouse is for looking around in a 3D world."),
    # physics
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:physics("dinamic")\n', 'not "dinamic". Did you mean "dynamic"?'),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:physics "bouncy"\n', 'A thing\'s physics can be "dynamic" (it falls and can be pushed)'),
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:rigidbody()\n', "An object doesn't have :rigidbody. Use :physics instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:apply_impulse(0, 5, 0)\n', "An object doesn't have :apply_impulse. Use :push instead."),
    ('game = tgame.window("x")\nb = game:circle(1, 2)\nb:restitution(0.5)\n', "A sprite doesn't have :restitution. Use :bounce instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:on_hit(go)\nfunc go(a, b, c):\n    nil\n', "go() needs 3 inputs"),
    ('w = tgame.world("x")\nw:car(0, 0, 0, "redd")\n', "'redd' isn't a color tgame knows."),
    # Physics: the kinds of physics (with "did you mean"), each method's inputs, numbers that can't be right, names
    # people guess, what on_hit gives its function, and a car or a ragdoll in a 2D game.
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:physics("frozen")\n',
     'A thing\'s physics can be "dynamic" (it falls and can be pushed), "static" (it stays where it is), "kinematic" (your code moves it) '
     'or "off", not "frozen". Did you mean "static"?'),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:physics("immovable")\n', 'not "immovable". Did you mean "static"?'),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:physics "dynamc"\n', 'not "dynamc". Did you mean "dynamic"?'),
    ('game = tgame.window("x")\nball = game:circle(1, 2, 3)\nball:physics("bouncy")\n', 'A thing\'s physics can be "dynamic"'),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:physics("dynamic", 2)\n',
     'crate:physics got the wrong number of inputs (2). It takes nothing, or the kind of physics, like: crate:physics() or crate:physics("static")'),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:mass(0)\n', "crate:mass needs a number above 0, like crate:mass(2)."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:mass(-2)\n', "crate:mass needs a number above 0, like crate:mass(2)."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:mass "heavy"\n', "crate:mass needs a number above 0, like crate:mass(2)."),
    ('w = tgame.world("x")\nball = w:sphere(0, 6, 0, 1)\nball:bounce(1.5)\n', "ball:bounce needs a number from 0 (no bounce) to 1 (it bounces right back up), like ball:bounce(0.6)."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1)\ncrate:friction(-1)\n', "crate:friction needs a number from 0 (slippery, like ice) up, like crate:friction(0.4)."),
    ('game = tgame.window("x")\nball = game:circle(1, 2, 3):physics()\nball:push(1, 2, 3)\n',
     "ball:push got the wrong number of inputs (3). It takes x and y: how hard to push it each way, like: ball:push(200, -300)"),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1)\ncrate:sleep 3\n', "crate:sleep doesn't take an input, so what comes after it was read as one."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1)\ncrate:apply_impulse(0, 1, 0)\n', "An object doesn't have :apply_impulse. Use :push instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1)\ncrate:restitution(0.5)\n', "An object doesn't have :restitution. Use :bounce instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1)\ncrate:on_collision(hit)\nfunc hit(a, b):\n    nil\n', "An object doesn't have :on_collision. Use :on_hit instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1)\ncrate:on_hit(hit)\nfunc hit(a, b, n):\n    nil\n',
     "hit() needs 3 inputs, but crate:on_hit gives it 2 inputs (the thing that hit it and how hard). Write it as: func hit(a, b):"),
    ('w = tgame.world("x")\np = w:player()\np:on_hit(hit())\nfunc hit(a, b):\n    nil\n', "Pass the function's name without brackets: hit, not hit()."),
    ('w = tgame.world("x")\nw:physics()\n',
     "A world doesn't have :physics. Each thing turns its own on, like crate:physics(), and w:gravity(-9.8) changes how strong gravity is."),
    ('w = tgame.world("x")\nw:explosion(0, 0, 0, 10, 5)\n', "A world doesn't have :explosion. Use :explode instead."),
    ('w = tgame.world("x")\nw:gravity()\n', "w:gravity got the wrong number of inputs (0)."),
    ('w = tgame.world("x")\ncar = w:vehicle(0, 1, 10)\n', "A world doesn't have :vehicle. Use :car instead."),
    ('w = tgame.world("x")\ncar = w:car(0, 1, 10, "red")\ncar:accelerate(2)\n', "A car doesn't have :accelerate. Use :engine instead."),
    ('w = tgame.world("x")\ncar = w:car(0, 1, 10, "red")\ncar:speed(3)\n',
     "car:speed got the wrong number of inputs (1). It takes nothing: it gives back how fast it goes, in km/h, like: say car:speed()"),
    ('w = tgame.world("x")\ncar = w:car(0, 1, 10, "red")\ncar:honk()\n', "A car doesn't have :honk."),
    ('w = tgame.world("x")\ndummy = w:ragdoll(0, 0, 0)\ndummy:drive()\n', "A ragdoll doesn't have :drive."),
    ('w = tgame.world("x")\nb = w:box(0, 1, 0):physics()\nb:drive()\n', "An object doesn't have :drive."),
    ('game = tgame.window("x")\ncar = game:car(100, 100)\n', 'The car needs a 3D world. Make the game with tgame.world, like: world = tgame.world("Physics Fun")'),
    ('game = tgame.window("x")\ndummy = game:ragdoll(100, 100)\n', "The ragdoll needs a 3D world."),
    ('game = tgame.window("x")\ngame:edges(true)\n', "A game doesn't have :edges. Use :walls instead."),
    ('w = tgame.world("x")\nhero = w:spawn("hut")\nhero:animate("dance")\n',
     'A character\'s animation can be "auto", "walk", "idle", "wave" or "none", not "dance".'),
    ('w = tgame.world("x")\nhero = w:spawn("hut")\nhero:animate "running"\n', 'not "running". Did you mean "walk"?'),
    # the effects
    ('w = tgame.world("x")\nw:weather("hail")\n', 'The weather can be "rain", "snow" or "none", not "hail".'),
    ('w = tgame.world("x")\nw:weather "snwo"\n', 'not "snwo". Did you mean "snow"?'),
    ('w = tgame.world("x")\nw:slowmo(0.3, 2)\n', "A world doesn't have :slowmo. Use :slow_mo instead."),
    ('game = tgame.window("x")\ngame:screen_shake(1)\n', "A game doesn't have :screen_shake. Use :shake instead."),
    ('w = tgame.world("x")\nw:day_night_cycle(60)\n', "A world doesn't have :day_night_cycle. Use :day_cycle instead."),
    ('w = tgame.world("x")\nw:pop_text("+1", 0, 1, 0, "golden")\n', "'golden' isn't a color tgame knows."),
    ('game = tgame.window("x")\ngame:pop_text("+1", 10, 20, "purpel")\n', "'purpel' isn't a color tgame knows."),
    ('w = tgame.world("x")\nw:shake(1, 2, 3)\n', "w:shake got the wrong number of inputs (3)."),
    # Level pieces: how a path goes (with "did you mean"), the inputs of a pad and a path, and names people guess.
    ('w = tgame.world("x")\nlift = w:box(0, 2, 0)\nlift:path([[0, 2, 0], [5, 2, 0]], 3, "zigzag")\n',
     'A path can go "ping-pong" (there and back again) or "loop" (round and round, back to the first spot), not "zigzag".'),
    ('w = tgame.world("x")\nlift = w:box(0, 2, 0)\nlift:path([[0, 2, 0], [5, 2, 0]], 3, "loopp")\n', 'not "loopp". Did you mean "loop"?'),
    ('w = tgame.world("x")\npad = w:jump_pad(0, 0, 0, 15, 2)\n', "w:jump_pad got the wrong number of inputs (5)."),
    ('w = tgame.world("x")\nw:trampoline(0, 0, 0)\n', "A world doesn't have :trampoline. Use :jump_pad instead."),
    ('w = tgame.world("x")\nw:speed_pad(0, 0, 0)\n', "A world doesn't have :speed_pad. Use :boost_pad instead."),
    ('w = tgame.world("x")\nlift = w:box(0, 2, 0)\nlift:waypoints([[0, 2, 0]])\n', "An object doesn't have :waypoints. Use :path instead."),
    # The game kit: effects, the HUD, interaction and level pieces. Each maker and method's inputs, the weathers,
    # corners and path modes (with "did you mean"), numbers that can't be right, colors, what each event gives
    # its function, names people guess, and the 3D-only ones in a 2D game.
    ('w = tgame.world("x")\nw:weather("rian")\n', 'not "rian". Did you mean "rain"?'),
    ('w = tgame.world("x")\nw:weather "fog"\n', 'The weather can be "rain", "snow" or "none", not "fog".'),
    ('w = tgame.world("x")\nw:weather("snow", 5)\n',
     'w:weather needs a strength from 0 to 2 after the kind (1 is normal), like w:weather("snow", 1.5).'),
    ('w = tgame.world("x")\nw:shake(3)\n', 'w:shake needs a number from 0 to 2 (1 is a good shake), like w:shake(0.5).'),
    ('w = tgame.world("x")\nw:shake(0.5, 0)\n', 'w:shake needs how long it shakes, in seconds (more than 0), like w:shake(1, 1.5).'),
    ('w = tgame.world("x")\nw:slow_mo(0)\n',
     'w:slow_mo needs a speed from 0.05 to 1 (0.3 is 30% of the speed, 1 is normal again), like w:slow_mo(0.3, 2).'),
    ('w = tgame.world("x")\nw:slow_mo(2, 3)\n',
     'w:slow_mo needs a speed from 0.05 to 1 (0.3 is 30% of the speed, 1 is normal again), like w:slow_mo(0.3, 2).'),
    ('w = tgame.world("x")\nw:slow_mo(0.01)\n', 'w:slow_mo needs a speed from 0.05 to 1'),
    ('game = tgame.window("x")\ngame:slow_mo(1.5)\n', 'game:slow_mo needs a speed from 0.05 to 1'),
    ('w = tgame.world("x")\nw:slow_mo(0.3, -1)\n', 'w:slow_mo needs how many seconds it lasts, 0 or more, like w:slow_mo(0.3, 2).'),
    ('w = tgame.world("x")\nw:slowmo(0.3)\n', "A world doesn't have :slowmo. Use :slow_mo instead."),
    ('game = tgame.window("x")\ngame:slow_motion(0.3)\n', "A game doesn't have :slow_motion. Use :slow_mo instead."),
    ('w = tgame.world("x")\nw:screen_shake(1)\n', "A world doesn't have :screen_shake. Use :shake instead."),
    ('w = tgame.world("x")\nw:pop_text("+10", 0, 2)\n',
     'w:pop_text got the wrong number of inputs (3). It takes the text, x, y and z, then a color and a size, like: w:pop_text("+10", 0, 2, 0)'),
    ('w = tgame.world("x")\nw:pop_text("+10", 0, 2, 0, "glod")\n', "'glod' isn't a color tgame knows."),
    ('w = tgame.world("x")\nc = w:spawn("coin")\nw:pop_text("+10", c:spot(), "glod")\n', "'glod' isn't a color tgame knows."),
    ('game = tgame.window("x")\ngame:pop_text("+10", 400, 300, "glod")\n', "'glod' isn't a color tgame knows."),
    ('game = tgame.window("x")\ngame:pop_text("+10", 400)\n',
     'game:pop_text got the wrong number of inputs (2). It takes the text, x and y, then a color and a size, like: game:pop_text("+10", 400, 300)'),
    ('w = tgame.world("x")\nw:floating_text("+10", 0, 2, 0)\n', "A world doesn't have :floating_text. Use :pop_text instead."),
    ('w = tgame.world("x")\nw:time_of_day(25)\n', 'w:time_of_day needs an hour from 0 to 24 (18 is 6 pm), like w:time_of_day(18).'),
    ('w = tgame.world("x")\nw:day_cycle(-5)\n',
     'w:day_cycle needs how many seconds a whole day takes, 2 or more (0 stops it), like w:day_cycle(120).'),
    ('w = tgame.world("x")\nw:day_cycle(1)\n',
     'w:day_cycle needs how many seconds a whole day takes, 2 or more (0 stops it), like w:day_cycle(120).'),
    ('w = tgame.world("x")\nw:day_cycle(0.5)\n', 'w:day_cycle needs how many seconds a whole day takes, 2 or more'),
    ('w = tgame.world("x")\nw:pop_text("+10", 0, 2, 0, "gold", 0)\n',
     'w:pop_text needs a size above 0: how tall the text is on screen, in pixels (34 is normal), like w:pop_text("+10", 0, 2, 0, "gold", 40).'),
    ('w = tgame.world("x")\nw:pop_text("+10", [0, 2, 0], "gold", -3)\n', 'w:pop_text needs a size above 0'),
    ('w = tgame.world("x")\nc = w:spawn("coin")\nw:pop_text("+10", c, "gold", 0)\n', 'w:pop_text needs a size above 0'),
    ('w = tgame.world("x")\nc = w:spawn("coin")\nw:pop_text("+10", c, "glod")\n', "'glod' isn't a color tgame knows."),
    ('game = tgame.window("x")\nb = game:box(1, 2)\ngame:pop_text("hit", b, "red", 0)\n', 'game:pop_text needs a size above 0'),
    ('game = tgame.window("x")\ngame:pop_text("+10", 400, 300, "gold", 0)\n',
     'game:pop_text needs a size above 0: how tall the text is on screen, in pixels (32 is normal), like game:pop_text("+10", 400, 300, "gold", 40).'),
    ('w = tgame.world("x")\nw:day_night_cycle(120)\n', "A world doesn't have :day_night_cycle. Use :day_cycle instead."),
    ('game = tgame.window("x")\ngame:weather("rain")\n',
     'The weather needs a 3D world. Make the game with tgame.world, like: world = tgame.world("My Game"), then world:weather("rain")'),
    ('game = tgame.window("x")\ngame:minimap()\n',
     'The minimap needs a 3D world. Make the game with tgame.world, like: world = tgame.world("My Game"), then map = world:minimap()'),
    ('game = tgame.window("x")\ngame:door(1, 2, 3)\n', 'A door needs a 3D world.'),
    ('game = tgame.window("x")\ngame:jump_pad(1, 2, 3)\n', 'A jump pad needs a 3D world.'),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:health_bar(0)\n',
     'e:health_bar needs a number above 0: the most health it can have, like e:health_bar(100).'),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:take_damage(10)\n', "An object doesn't have :take_damage. Use :hurt instead."),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:hp()\n', "An object doesn't have :hp. Use :health instead."),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:health(5)\n',
     'e:health got the wrong number of inputs (1). It takes nothing: it gives back how much health it has, like: say e:health()'),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:on_death(gone)\nfunc gone(a, b):\n    nil\n',
     'gone() needs 2 inputs, but e:on_death gives it'),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:on_death(gone())\nfunc gone():\n    nil\n',
     "Pass the function's name without brackets: gone, not gone()."),
    ('w = tgame.world("x")\ne = w:spawn("person")\ne:on_die(gone)\nfunc gone():\n    nil\n',
     "An object doesn't have :on_die. Use :on_death instead."),
    ('game = tgame.window("x")\ns = game:box(1, 2, 3, 4)\ns:healthbar(10)\n', "A sprite doesn't have :healthbar. Use :health_bar instead."),
    ('game = tgame.window("x")\nclock = game:countdown(60, done)\nfunc done(t):\n    nil\n',
     'done() needs 1 input, but game:countdown gives it no inputs. Write it as: func done():'),
    ('game = tgame.window("x")\nclock = game:countdown()\n',
     'game:countdown got the wrong number of inputs (0). It takes how many seconds, then the name of a function to run at 0, like: clock = game:countdown(60, times_up)'),
    ('game = tgame.window("x")\nclock = game:timer(60)\n', "A game doesn't have :timer. Use :countdown instead."),
    ('game = tgame.window("x")\nclock = game:countdown(60)\nclock:time_left()\n',
     "A countdown doesn't have :time_left. Use :left instead."),
    ('game = tgame.window("x")\nclock = game:countdown(60)\nclock:add()\n',
     'clock:add got the wrong number of inputs (0). It takes how many seconds to add, like: clock:add(5)'),
    ('game = tgame.window("x")\nclock = game:countdown(60)\nclock:explode()\n', "A countdown doesn't have :explode."),
    ('w = tgame.world("x")\nc = w:spawn("chest")\na = w:arrow_to()\n',
     'w:arrow_to got the wrong number of inputs (0). It takes the thing to point at, like: arrow = w:arrow_to(chest)'),
    ('w = tgame.world("x")\nc = w:spawn("chest")\na = w:waypoint(c)\n', "A world doesn't have :waypoint. Use :arrow_to instead."),
    ('w = tgame.world("x")\nc = w:spawn("chest")\na = w:arrow_to(c)\na:remove()\n', "An arrow doesn't have :remove. Use :hide instead."),
    ('w = tgame.world("x")\nm = w:minimap(180, "top middle")\n',
     'A minimap can go in the top right, top left, bottom left or bottom right corner, not "top middle".'),
    ('w = tgame.world("x")\nm = w:minimap(180, "top lfet")\n', 'not "top lfet". Did you mean "top left"?'),
    ('w = tgame.world("x")\nm = w:minimap("top left")\n',
     'w:minimap takes its size first, then the corner, like: map = w:minimap(180, "top left")'),
    ('w = tgame.world("x")\nm = w:minimap(180, "top left", 3)\n', 'w:minimap got the wrong number of inputs (3).'),
    ('w = tgame.world("x")\nm = w:radar()\n', "A world doesn't have :radar. Use :minimap instead."),
    ('w = tgame.world("x")\nm = w:minimap()\nc = w:spawn("coin")\nm:add(c)\n', "A minimap doesn't have :add. Use :mark instead."),
    ('w = tgame.world("x")\nm = w:minimap()\nc = w:spawn("coin")\nm:mark(c, "glod")\n', "'glod' isn't a color tgame knows."),
    ('w = tgame.world("x")\nm = w:minimap()\nm:zoom(0)\n', 'm:zoom needs a number above 0 (2 shows twice as close), like m:zoom(2).'),
    ('w = tgame.world("x")\np = w:player()\np:grab()\n', "A player doesn't have :grab. Use :can_grab instead."),
    ('w = tgame.world("x")\np = w:player()\np:can_grab(true, 3)\n',
     'p:can_grab got the wrong number of inputs (2). It takes nothing, or false to turn grabbing off, like: p:can_grab()'),
    ('w = tgame.world("x")\np = w:player()\np:held_item()\n', "A player doesn't have :held_item. Use :holding instead."),
    ('w = tgame.world("x")\nn = w:spawn("person")\nn:speak("Hi")\n', "An object doesn't have :speak. Use :say instead."),
    ('w = tgame.world("x")\nn = w:spawn("person")\nn:say()\n',
     'n:say got the wrong number of inputs (0). It takes the words, then how many seconds the bubble stays (0 keeps it), like: n:say("Hi! Find my lost cat.")'),
    ('w = tgame.world("x")\nn = w:spawn("person")\nn:on_talk(talk)\nfunc talk(a, b):\n    nil\n',
     'talk() needs 2 inputs, but n:on_talk gives it no inputs. Write it as: func talk():'),
    ('w = tgame.world("x")\nn = w:spawn("person")\nn:on_interact(talk)\nfunc talk():\n    nil\n',
     "An object doesn't have :on_interact. Use :on_talk instead."),
    ('w = tgame.world("x")\nd = w:door(0, 0)\n',
     'w:door got the wrong number of inputs (2). It takes x, y and z, then a color, like: door = w:door(0, 0, -5)'),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5, "glod")\n', "'glod' isn't a color tgame knows."),
    ('w = tgame.world("x")\nd = w:door([0, 0, -5], "glod")\n', "'glod' isn't a color tgame knows."),
    ('w = tgame.world("x")\nd = w:gate(0, 0, -5)\n', "A world doesn't have :gate. Use :door instead."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:shut()\n', "A door doesn't have :shut. Use :close instead."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:needs("key")\n',
     'd:needs takes the key itself, not its name, like: key = world:spawn("key", 3, 0, 3), then d:needs(key)'),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nk = w:spawn("key")\nd:unlock_with(k)\n',
     "A door doesn't have :unlock_with. Use :needs instead."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:open(1)\n',
     'd:open got the wrong number of inputs (1). It takes nothing, like: d:open()'),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:fly()\n', "A door doesn't have :fly."),
    # A door has no health, and a car or a ragdoll always uses physics, so it can't move along a path.
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:health_bar(50)\n',
     "A door doesn't have health, so it can't have :health_bar. It opens and closes (d:open(), d:close()), and d:needs(key) "
     "locks it until the player has the key."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:hurt(1)\n', "A door doesn't have health, so it can't have :hurt."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nsay d:health()\n', "A door doesn't have health, so it can't have :health."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:on_death(gone)\nfunc gone():\n    nil\n',
     "A door doesn't have health, so it can't have :on_death."),
    ('w = tgame.world("x")\nd = w:door(0, 0, -5)\nd:damage(3)\n', "A door doesn't have health, so it can't have :damage."),
    ('w = tgame.world("x")\ncar = w:car(0, 1, 0)\ncar:path([[0, 1, 0], [10, 1, 0]], 3)\n',
     "A car always uses physics (it drives on its wheels), so it can't move along a path. Push it with car:push(0, 4, -6), "
     "or let the player drive it with car:drive()."),
    ('w = tgame.world("x")\ndummy = w:ragdoll(0, 0, 0)\ndummy:path([[0, 1, 0]])\n',
     "A ragdoll always uses physics (that's what makes it flop), so it can't move along a path. Push it with dummy:push(0, 4, -6)."),
    ('w = tgame.world("x")\np = w:jump_pad(0, 0)\n',
     'w:jump_pad got the wrong number of inputs (2). It takes x, y and z, then how hard it launches things up (m/s), like: pad = w:jump_pad(0, 0, 5, 15)'),
    ('w = tgame.world("x")\np = w:jump_pad(0, 0, 5, 0)\n',
     'w:jump_pad needs how hard it launches things, a number above 0, like w:jump_pad(0, 0, 5, 15).'),
    ('w = tgame.world("x")\np = w:jump_pad([0, 0, 5], -3)\n', 'w:jump_pad needs how hard it launches things, a number above 0'),
    ('w = tgame.world("x")\np = w:trampoline(0, 0, 5)\n', "A world doesn't have :trampoline. Use :jump_pad instead."),
    ('w = tgame.world("x")\np = w:boost_pad(0, 0, 10, 0)\n',
     'w:boost_pad needs how hard it boosts, a number above 0, like w:boost_pad(0, 0, 10, 20).'),
    ('w = tgame.world("x")\np = w:speed_pad(0, 0, 10)\n', "A world doesn't have :speed_pad. Use :boost_pad instead."),
    ('w = tgame.world("x")\nlift = w:box(0, 2, 0, 4)\nlift:path([[0, 2, 0], [10, 2, 0]], 3, "sideways")\n',
     'A path can go "ping-pong" (there and back again) or "loop" (round and round, back to the first spot), not "sideways".'),
    ('w = tgame.world("x")\nlift = w:box(0, 2, 0, 4)\nlift:waypoints([[0, 2, 0], [10, 2, 0]], 3)\n',
     "An object doesn't have :waypoints. Use :path instead."),
    ('w = tgame.world("x")\nlift = w:box(0, 2, 0, 4)\nlift:path([[0, 2, 0]], 3, "loop", 4)\n',
     'lift:path got the wrong number of inputs (4).'),
    ('w = tgame.world("x")\nk = w:spawn("kee")\n', 'tgame doesn\'t have a "kee" to spawn.'),
    # Multiplayer: names, messages and addresses as text, what :send and :share carry, the events' functions.
    ('w = tgame.world("x")\nw:host(5)\n', 'w:host needs the room\'s name as text, like w:host("Tag"), not a number.'),
    ('w = tgame.world("x")\nw:join("Tag", 2)\n', "w:join got the wrong number of inputs (2). It takes nothing (the first room it finds)"),
    ('game = tgame.window("x")\nscore = 3\ngame:send(score)\n', 'game:send needs the message as text, like game:send("score", 10), not a number.'),
    ('game = tgame.window("x")\ngame:send("me", game)\n', "game:send can send numbers, text, true/false, lists and tables, not a game."),
    ('w = tgame.world("x")\nw:share("coins")\n', "w:share got the wrong number of inputs (1). It takes a name, then its value"),
    ('w = tgame.world("x")\nb = w:box(0, 0, 0)\nw:share("box", b)\n', "w:share can share numbers, text, true/false, lists and tables, not an object."),
    ('w = tgame.world("x")\nsay w:shared()\n', "w:shared got the wrong number of inputs (0)."),
    ('w = tgame.world("x")\nw:my_name("")\n', 'w:my_name needs the name, like w:my_name("Sam")'),
    ('w = tgame.world("x")\nfunc got(a, b, c, d):\n    say a\nw:on_message(got)\n', "got() needs 4 inputs, but w:on_message gives it 3 inputs"),
    ('w = tgame.world("x")\nfunc hi(name):\n    say name\nw:on_join(hi())\n', "Pass the function's name without brackets: hi, not hi()."),
    ('game = tgame.window("x")\nfor p in game:others():\n    say p\n', "The other players are people in a 3D world."),
    ('w = tgame.world("x")\nw:connect()\n', "A world doesn't have :connect. Use :join instead."),
    ('w = tgame.world("x")\nif w:is_host():\n    say 1\n', "A world doesn't have :is_host. Use :hosting instead."),
    ('game = tgame.window("x")\ngame:broadcast("hi")\n', "A game doesn't have :broadcast. Use :send instead."),
    ('game = tgame.window("x")\ngame:on_receive(got)\n', "A game doesn't have :on_receive. Use :on_message instead."),
]


# Correct code the checker must accept: tgame methods on values it can't see (in a list, a function's input),
# spots in place of x and y, chained setters, every event with fewer inputs than it gives.
GOOD_SNIPPETS = [
    'w = tgame.world("x")\ntrees = [w:spawn("tree"), w:spawn("pine", [1, 0, 2])]\nfor t in trees:\n    t:shake()\n    t:label "hi"\n',
    'game = tgame.window("x")\nb = game:box([10, 20], 5, 5, "red"):color("#ff8800")\nb:move_to(game:random_spot())\nsay b:x() + 1\n',
    'game = tgame.window("x")\nfunc hit(s):\n    s:remove()\nfunc tap(x):\n    say x\nfunc key():\n    nil\n'
    'game:box(1, 2):clicked hit\ngame:clicked tap\ngame:on_key("any", key)\ngame:game_over("Bye", key)\n',
    'w = tgame.world("x")\np = w:player "third person"\na = p:hold "sword"\na:swing()\nseen = w:looking_at(4)\nif seen:\n    seen:fall()\n',
    'game = tgame.window("x")\nwhile game:open():\n    dt = game:frame()\n    if game:pressed("space") or game:held("mouse"):\n        game:sound "jump"\n',
    # Only a newline ends a line: text holding U+2028, U+0085 or a form feed (pasted from a web page) stays one text.
    'game = tgame.window("x")\nsay "hidden breaks in text"\ngame:text("a b\u0085c\x0cd", 10, 10)\n',
    # Pictures in a folder inside the game's folder are fine, even written with a ../ that stays inside.
    'game = tgame.window("x")\ngame:image("art/star.png", 1, 2)\ngame:image("art/../art/star.png", 3, 4)\n',
    # The land: chained edits, a stroke, a spot from random_spot, the number height_at gives
    'w = tgame.world("x")\nw:lighting "Modern"\nland = w:terrain(150, "snow"):hill(0, 0, 20, 5)\n'
    'land:raise([[1, 2], [3, 4]], 6, 1):smooth(1, 2, 6):water(-2)\nh = land:height_at(w:random_spot())\nsay h + 1\n',
    # The land: every method once (a brush stroke too), styles and lightings in any case, height_at as a number.
    'world = tgame.world("My World", 960, 600)\nworld:sky "day"\nworld:lighting "modern"\nland = world:terrain(200)\n'
    'land:style "grass"\nland:hill(20, -10, 30, 8)\nland:mountain(-40, -50, 60, 35)\nland:dip(10, 25, 16, 3)\n'
    'land:lake(-20, 30, 36, 4)\nland:valley(-60, 0, 60, 10, 18, 6)\nland:raise(5, 5, 8, 1.5)\nland:lower(5, 5, 8, 1.5)\n'
    'land:smooth(5, 5, 8)\nland:flatten(5, 5, 8, 2)\nland:raise([[1, 2], [3, 2], [5, 3]], 8, 1.5)\nland:water(-1)\n'
    'h = land:height_at(12, 4)\nsay h + 1\nland:style "Snow"\nworld:lighting "Simple"\n',
    # A stroke built in a loop, a function's inputs, the player's x and z, a style as world:terrain's second input,
    # and a chain on the land it gives back.
    'w = tgame.world("x")\nland = w:terrain(120, "desert")\nstroke = []\nfor i in range(1, 5):\n    stroke:add([i * 2, 0])\n'
    'land:lower(stroke, 6, 1)\nfunc dig(x, y, z):\n    land:lower(x, z, 4, 0.5)\nw:clicked dig\np = w:player()\n'
    'say land:height_at(p:x(), p:z())\n',
    'w = tgame.world("x")\nw:terrain(80, "autumn"):hill(0, 0, 20, 4)\nw:island(60)\n',
    # Menus, buttons and screens: a panel at every place (in any case, with - or _), chained widgets, a start screen
    # with only a title, screens that pause or not, and :shown as true or false.
    'game = tgame.window("x")\nfor place in ["top left", "top", "top right", "left", "center", "right", "bottom left", "bottom", "bottom right"]:\n'
    '    game:panel(place):small place\ngame:panel "Top-Left"\ngame:panel("bottom_right"):card():text "Hi"\n'
    'start = game:start_screen("Go!")\nstart:text "Dodge the rocks."\nshop = game:screen()\nquiet = game:screen("Map", false)\n'
    'quiet:hide()\nif shop:shown() and not quiet:shown():\n    say "shop"\nstart:show()\n',
    # A whole game's UI: a click-to-play start screen, a HUD panel with a button and a progress bar, a pausing shop
    # with a row, a text box, a slider (its :change), a dropdown, a switch and tabs, and a game over screen.
    'game = tgame.world("Chop! Chop!", 960, 600)\nplayer = game:player("first person")\n'
    'start = game:start_screen("Chop! Chop!", "Click to play")\nstart:text "Chop trees for coins, buy better axes."\n'
    'bar = game:panel("top left")\ncoins_label = bar:heading "Coins: 0"\nbar:button("Shop", open_shop):icon "cart"\nhp = bar:progress(100)\n'
    'shop = game:screen("Shop")\nrow = shop:row()\nrow:button("Stone Axe (15)", buy_stone)\nrow:badge("New", "success")\n'
    'name_box = shop:input("Your name")\nname_box:enter named\nvolume = shop:slider(0, 100, 50)\nvolume:change volume_changed\n'
    'size = shop:dropdown(["Small", "Big"], "Small")\nmusic = shop:switch("Music", true)\ntabs = shop:tabs()\ntabs:tab("Axes"):text "Sharp"\n'
    'shop:button("Close", close_shop, "secondary")\nshop:hide()\nover = game:screen("Game over")\nover:hide()\n'
    'over:button("Play again", again):style("radius", 20)\ncoins = 0\n'
    'func open_shop():\n    shop:show()\nfunc close_shop():\n    shop:hide()\nfunc buy_stone(text):\n    coins_label:set "Coins: " + coins\n'
    '    hp:set 50\nfunc named(text):\n    say text\nfunc volume_changed(v):\n    game:volume v\nfunc again():\n    over:hide()\n    start:show()\n'
    'func step(dt):\n    if shop:shown() and size:value() is "Big" and music:value():\n        say name_box:value()\ngame:every_frame step\n',
    # Physics in 3D: every method in each way it's written (a spot for x, y and z, physics() chained, spin with one
    # input or three, velocity() as a list), a car, a ragdoll, explode, animate, and on_hit on a thing and the player.
    'world = tgame.world("Physics Fun", 960, 600)\nworld:gravity(-9.8)\nland = world:terrain(200)\ncrate = world:box(0, 6, 0, 1, "wood")\n'
    'crate:physics()\ncrate:physics("Static")\ncrate:physics "kinematic"\ncrate:physics("off")\ncrate:mass(2)\ncrate:bounce(0.6)\n'
    'crate:bounce 1\ncrate:friction(0)\ncrate:push(0, 5, -3)\ncrate:push([0, 5, -3])\ncrate:spin(0, 2, 0)\ncrate:spin 90\n'
    'crate:velocity(0, 0, -4)\nv = crate:velocity()\nsay v[0]\ncrate:on_hit(bumped)\ncrate:sleep()\ncrate:wake()\n'
    'ball = world:sphere(2, 10, 0, 0.5, "red"):physics()\nball:bounce(0.8):mass(1):push(1, 0, 0)\nworld:explode(0, 0, 0, 12, 8)\n'
    'world:explode([0, 0, 0], 12, 8)\nworld:explode(ball:spot(), 5)\ncar = world:car(0, 1, 10, "red")\ncar:drive()\ncar:drive(false)\n'
    'car:engine(1)\nsay car:speed() + 1\ncar:flip()\ncar:push(0, 4, -6)\ncar:on_hit(bumped)\ncar:move_to(0, 1, 10)\n'
    'dummy = world:ragdoll(5, 0, 0, "blue")\ndummy:push(0, 4, -6)\ndummy:on_hit(bumped)\nhero = world:spawn("hut", 1, 0, 1)\n'
    'hero:animate("walk")\nhero:animate "None"\nplayer = world:player("third person")\nplayer:on_hit(ouch)\n'
    'func bumped(other, strength):\n    say strength\nfunc ouch(other):\n    say "ouch"\nwhile world:open():\n    world:frame()\n',
    # The other words tgame knows for the kinds of physics (any case): on, falls and fall (dynamic), fixed, still and
    # solid (static), none and no (off).
    'w = tgame.world("x")\ncrate = w:box(0, 6, 0, 1, "wood")\ncrate:physics("on")\ncrate:physics("Falls")\ncrate:physics "fall"\n'
    'crate:physics("fixed")\ncrate:physics("still")\ncrate:physics("SOLID")\ncrate:physics("none")\ncrate:physics("no")\n'
    'car = w:car(0, 1, 10)\ncar:physics("on")\ndummy = w:ragdoll(5, 0, 0)\ndummy:physics("falls")\n',
    'game = tgame.window("x")\nfloor = game:box(400, 580, 800, 40, "gray"):physics("Fixed")\nball = game:circle(1, 2, 3):physics("on")\n',
    # Physics in 2D: gravity, walls, a static floor, a ball that bounces and is pushed, its velocity, on_hit, explode.
    'game = tgame.window("Bouncy", 800, 600)\ngame:gravity(900)\ngame:walls(true)\n'
    'floor = game:box(400, 580, 800, 40, "gray"):physics("static")\nball = game:circle(400, 100, 20, "red"):physics()\n'
    'ball:bounce(0.8)\nball:push(200, -300)\nball:push([200, -300])\nball:velocity(0, -200)\nsay ball:velocity()\n'
    'ball:on_hit(boing)\ngame:explode(400, 300, 600, 200)\nfunc boing(other, strength):\n    game:sound "pop"\n'
    'game:every_frame step\nfunc step(dt):\n    nil\n',
    'w = tgame.world("x")\ncoin = w:spawn("coin")\nw:slow_mo(0.3, 2)\nw:slow_mo(1)\nw:shake(0.5)\nw:shake(1, 1.5)\n'
    'w:pop_text("+10", 0, 1, 0)\nw:pop_text("+10", [0, 1, 0], "gold", 40)\nw:pop_text("+1", coin, "gold")\n'
    'w:weather("rain")\nw:weather("snow", 1.5)\nw:weather "none"\nw:day_cycle(120)\nw:day_cycle(0)\nw:time_of_day(18)\n'
    'hour = w:time_of_day()\nsay hour + 1\n'
    'game = tgame.window("x")\nball = game:circle(100, 100, 10)\ngame:slow_mo(0.5)\ngame:shake(2, 1)\n'
    'game:pop_text("+1", 100, 50)\ngame:pop_text("+1", 100, 50, "gold", 40)\ngame:pop_text("hit", ball)\n',
    # The game kit's numbers at the ends of what they can be: slow motion from 0.05 to 1 (for 0 seconds or more), a
    # minimap from 60 to 600 pixels, a day of 2 seconds or more (0 stops it); and a car or a ragdoll told to stop a
    # path (there's none to stop: that's fine).
    'w = tgame.world("x")\nw:slow_mo(0.05)\nw:slow_mo(1, 0)\nw:slow_mo(0.5, 10)\nm = w:minimap(60)\nm = w:minimap(600, "top left")\n'
    'w:day_cycle(2)\nw:day_cycle(0)\nw:day_cycle(600)\ncar = w:car(0, 1, 10)\ncar:path()\ndummy = w:ragdoll(5, 0, 0)\ndummy:path()\n',
    'game = tgame.window("x")\ngame:slow_mo(0.05, 1)\ngame:slow_mo(1)\n',
    # Level pieces: pads with and without a power (a spot for x, y and z), turned, recoloured and on a path, and paths
    # in every way they're written (a speed, a mode in any case, spots built in a loop, path() to stop, chained).
    'world = tgame.world("Parkour", 960, 600)\nland = world:terrain(200)\npad = world:jump_pad(0, 0, 5, 15)\n'
    'boost = world:boost_pad([0, 0, 10], 20)\nboost:turn(90)\nboost:color("purple")\nworld:jump_pad(4, 0, 4):path([[4, 0, 4], [8, 0, 4]], 1)\n'
    'lift = world:box(0, 2, 0, [4, 0.4, 4], "stone")\nlift:path([[0, 2, 0], [10, 2, 0], [10, 6, 0]], 3)\n'
    'lift:path([[0, 2, 0], [10, 2, 0]], 3, "loop")\nlift:path([[0, 2, 0], [10, 2, 0]], 3, "Ping-Pong")\nspots = []\n'
    'for i in range(1, 4):\n    spots:add([i * 3, 1, 0])\nring = world:box(0, 1, 0, 2):path(spots, 2, "round and round")\n'
    'say ring:x() + lift:spot()[1]\nlift:path()\nplayer = world:player()\n',
    # The game kit in 3D: every maker and method in each way it's written (a spot for x, y and z, colors, the
    # weathers and corners, "loop"), a key, a door that needs it, on_death, on_talk and the countdown's function.
    'world = tgame.world("Kit", 960, 600)\nland = world:terrain(160)\nworld:slow_mo(0.3, 2)\nworld:slow_mo(1)\n'
    'world:shake(0.5)\nworld:shake(1, 1.5)\nworld:pop_text("+10", 0, 2, 0)\nworld:pop_text("+10", 0, 2, 0, "gold", 40)\n'
    'world:weather("rain")\nworld:weather("Snow", 1.5)\nworld:weather "none"\nworld:day_cycle(120)\nworld:day_cycle(0)\n'
    'world:time_of_day(18)\nenemy = world:spawn("person", 4, 0, 2)\nenemy:health_bar(100)\nenemy:hurt(10)\nenemy:heal(5)\n'
    'say enemy:health() + 1\nenemy:on_death(gone)\nclock = world:countdown(60, times_up)\nclock:add(5)\nclock:stop()\n'
    'say clock:left() + 1\nchest = world:spawn("chest", 10, 0, 10)\narrow = world:arrow_to(chest)\narrow:hide()\n'
    'arrow:show()\nworld:arrow_to(enemy)\nmap = world:minimap()\nmap = world:minimap(180, "top left")\n'
    'map:mark(chest, "gold")\nmap:unmark(chest)\nmap:zoom(2)\nplayer = world:player()\nplayer:can_grab()\n'
    'player:can_grab(false)\nheld = player:holding()\nnpc = world:spawn("person", 4, 0, 2)\n'
    'npc:say("Hi! Find my lost cat.")\nnpc:say("Bye", 0)\nnpc:on_talk(talk)\nworld:pop_text("+1", npc:spot(), "gold")\n'
    'door = world:door(0, 0, -5)\ndoor2 = world:door(0, 0, -15, "wood")\ndoor:open()\ndoor:close()\ndoor:turn(90)\n'
    'key = world:spawn("key", 3, 0, 3)\ndoor:needs(key)\ndoor:lock()\ndoor:unlock()\ndoor:on_talk(talk)\n'
    'pad = world:jump_pad(0, 0, 5, 15)\nboost = world:boost_pad(0, 0, 10, 20)\nboost:turn(90)\n'
    'lift = world:box(0, 2, 0, [4, 0.4, 4], "stone")\nlift:path([[0, 2, 0], [10, 2, 0], [10, 6, 0]], 3)\n'
    'lift:path([[0, 2, 0], [10, 2, 0]], 3, "loop")\nlift:path()\npad2 = world:jump_pad([0, 0, 8], 12)\nfunc gone():\n'
    '    say "gone"\nfunc times_up():\n    world:pause("Time\'s up!")\nfunc talk():\n    npc:say("Thanks!")\n'
    'while world:open():\n    world:frame()\n',
    # And in 2D: slow_mo, shake, pop_text (a spot for x and y), a sprite's health bar and a countdown.
    'game = tgame.window("Kit 2D", 800, 600)\nhero = game:box(400, 300, 40, 40, "blue")\nhero:health_bar(3)\nhero:hurt(1)\n'
    'hero:on_death(lost)\ngame:slow_mo(0.5, 1)\ngame:shake(1)\ngame:pop_text("+10", 400, 300)\n'
    'game:pop_text("Ouch", hero:x(), hero:y(), "red", 30)\ngame:pop_text("Ouch", hero:spot(), "red")\n'
    'clock = game:countdown(30, lost)\nfunc lost():\n    game:pause("Game over")\n',
    # Splash screens, a main menu and the mouse: every way they're written (a picture in a folder, text, nothing,
    # nil with seconds), the menu's widgets, mouse_locked as true or false, auto_lock with a variable.
    'world = tgame.world("Forest Notes")\nplayer = world:player("first person")\nworld:splash("art/star.png", 2.5)\n'
    'world:splash("Pip Studio presents")\nworld:splash()\nworld:splash(nil, 1)\nmenu = world:main_menu("Forest Notes")\n'
    'menu:text "Find the note."\nmenu:button("Play", play)\nrow = menu:row()\nrow:button("Settings", settings, "secondary")\n'
    'menu:button("Quit", quit, "ghost")\nnote = world:screen("A note")\nnote:button("Close", close_note)\nnote:hide()\n'
    'free = false\nworld:auto_lock(not free)\nworld:auto_lock false\n'
    'func play():\n    menu:hide()\n    world:lock_mouse()\nfunc settings():\n    nil\nfunc quit():\n    world:close()\n'
    'func close_note():\n    note:hide()\nfunc key(name):\n    if name is "e" and not note:shown():\n        world:unlock_mouse()\n'
    '        note:show()\n    if name is "m":\n        menu:show()\n    if world:mouse_locked() == false:\n        say "free"\n'
    'world:on_key("any", key)\nwhile world:open():\n    world:frame()\n',
    'game = tgame.window("Star Hopper", 800, 500)\ngame:splash("Made by me", 3)\nmenu = game:main_menu()\nmenu:button("Play", go)\n'
    'func go():\n    menu:hide()\ngame:every_frame step\nfunc step(dt):\n    if game:paused():\n        say "menu"\n',
    # Multiplayer: host or join (by name, by address, or any room), every event with fewer inputs than it gives, values
    # of any kind sent and shared, the other players' people as objects, the names a list.
    'w = tgame.world("Tag")\nme = w:player("third person")\nw:my_name("Sam")\nif w:hosting():\n    w:join()\nelse:\n    w:host()\n'
    'w:join("Tag")\nw:join("192.168.1.20")\nw:host("Sam\'s room")\n'
    'func got(message, value):\n    say message\nfunc hi(name):\n    w:send("hello", [1, "two", true])\nfunc bye():\n    say "bye"\n'
    'w:on_message(got)\nw:on_join(hi)\nw:on_leave(bye)\nw:share("coins", w:shared("coins", 0) + 1)\nw:send("ping")\n'
    'for p in w:others():\n    if me:touches(p):\n        say p:get("name") + " is it"\n    p:animate("wave")\n'
    'say len(w:players()) + " playing"\nif w:connected():\n    w:leave()\nname = w:my_name()\n',
    'game = tgame.window("Dots")\ngame:join()\nme = game:circle(100, 100, 10, "blue")\nfriend = game:circle(-50, -50, 10, "red")\n'
    'func got(message, value, sender):\n    if message == "at":\n        friend:move_to(value[0], value[1])\n'
    'game:on_message(got)\nfunc step(dt):\n    game:send("at", [me:x(), me:y()])\ngame:every_frame(step)\n',
]


def game_examples():
    """The games the MCP server's tuff_examples gives agents and TuffCode offers as examples (TUFF_GAME_EXAMPLES in
    renderer/js/tuff-templates.js), or None without Node."""
    templates = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-templates.js")
    load = "const window = {}; require('vm').runInNewContext(require('fs').readFileSync(process.argv[1], 'utf8'), { window }); " \
           "console.log(JSON.stringify(window.TUFF_GAME_EXAMPLES || []))"
    try:
        return json.loads(subprocess.run(["node", "-e", load, templates], capture_output=True, text=True, encoding="utf-8", timeout=60).stdout)
    except FileNotFoundError:
        return None


def t_checker(c):
    for name in GOOD:
        p = subprocess.run(tuff_cmd() + ["--check", os.path.join(GAMES, name)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"--check accepts {name}", (p.stdout + p.stderr)[:400])
    folder = os.path.join(HERE, "out", "checker")
    os.makedirs(os.path.join(folder, "art"), exist_ok=True)  # never in the temp folder: there the checker leaves file names alone
    with open(os.path.join(GAMES, "star.png"), "rb") as f, open(os.path.join(folder, "art", "star.png"), "wb") as g:
        g.write(f.read())
    for i, src in enumerate(GOOD_SNIPPETS):
        path = os.path.join(folder, f"good{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0, f"--check accepts snippet {i + 1}: {src.splitlines()[1][:60]}", (p.stdout + p.stderr)[:400])
    # The games the MCP server's tuff_examples gives agents (renderer/js/tuff-templates.js, TUFF_GAME_EXAMPLES).
    games = game_examples()
    if games is None:
        c.check(True, "Node isn't installed: skipped the MCP's game examples")
    if games is not None:
        c.check(any("terrain(" in g["code"] for g in games), "the MCP's game examples have a world with land (terrain)", [g["id"] for g in games])
        c.check(any(all(m in g["code"] for m in (":start_screen(", ":panel(", ":button(", ":screen(")) for g in games),
                "... and a game with a start screen, a panel with a button and a screen", [g["id"] for g in games])
    for g in games or []:
        path = os.path.join(folder, f"example_{g['id']}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(g["code"])
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0, f"--check accepts the MCP example {g['name']}", (p.stdout + p.stderr)[:400])
    for i, (src, want) in enumerate(BAD):
        path = os.path.join(folder, f"bad{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 1 and want in p.stderr, f"--check catches: {want}", p.stderr[:400])
    # A 3D-only kit name in a 2D game: "needs a 3D world" is the error the editor shows (its first), and the only one.
    for i, line in enumerate(['game:weather("rain")', "game:minimap()", "game:arrow_to(star)", "game:jump_pad(1, 2, 3)",
                              "game:time_of_day(18)", "game:boost_pad(1, 2, 3)", "game:day_cycle(60)"]):
        path = os.path.join(folder, f"flat{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'mention tgame\ngame = tgame.window("x")\nstar = game:circle(1, 2, 3)\n{line}\n')
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        first = next((x for x in p.stderr.splitlines() if x.startswith("Tuff error")), "")
        c.check(p.returncode == 1 and "needs a 3D world" in first and "doesn't have" not in p.stderr,
                f"{line} in a 2D game: the error is that it needs a 3D world, and nothing else", p.stderr[:400])
    # The game kit once tgame has it itself: its own names win (here a countdown it calls a "timer", with a :pause of
    # its own), the kit's checks still run on them, and "key" is a kit model either way.
    import tuff
    import tuff_tgame

    def pause():
        return None

    own = tuff_tgame.tables()
    landed = {**own, "kinds": {**own["kinds"], "world": {**own["kinds"]["world"], "countdown": lambda seconds, fn=None: None},
                               "timer": {"pause": pause}},
              "gives": {**own["gives"], "world": {**own["gives"]["world"], "countdown": "timer"}}}
    tg = tuff.with_gamekit(landed, tuff_tgame)
    c.check(tg["gives"]["world"]["countdown"] == "timer" and {"pause", "add", "stop", "left"} <= set(tg["kinds"]["timer"])
            and "timer" in tg["kit_kinds"] and tg["handlers"]["timer"] == {} and tg["handlers"]["world"]["countdown"][0] == 1,
            "with_gamekit keeps tgame's own names (a countdown it calls a timer) and fills in the rest", sorted(tg["kinds"]["timer"]))
    c.check(tg["check"]("world", "spawn", 0, "key") is None and tg["check"]("world", "spawn", 0, "kee"), 'world:spawn("key") is fine before tgame lists it', None)


# ---------------------------------------------------------------- saved game data (game:save, game:load)

# Every game these tests run keeps its saves in out/saves, never in the real TuffSaves folder (the guide's high score
# game saves too). t_saves gives each of its runs a folder of its own.
os.environ.setdefault("TUFF_SAVE_DIR", os.path.join(OUT, "saves"))


def save_dir(name):
    """An empty folder for a test's saves (TUFF_SAVE_DIR), in out/saves_test."""
    import shutil
    path = os.path.join(OUT, "saves_test", name)
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    return path


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def same_json(a, b):
    """The same JSON, types and all (in Python, True == 1 and 1 == 1.0)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# What games/save_data.tuf's show_all says before anything is saved, and after save_all (the list gets "more" added
# after it's loaded, which doesn't change what's saved).
SAVE_DEFAULTS = ["best 0", "name nobody", "done false", "nothing false 5", "list []", "stats none", "missing none nil false"]
SAVE_SHOWN = ["best 42", "name Ada Lovelace", "done true", "nothing true nil", 'list [1, 2.5, "three", [4, 5], false, "more"] 6 5',
              'stats 3 Ada ["sword", "key"] 7.5', "missing none nil false"]
SAVE_FILE = {"best": 42, "name": "Ada Lovelace", "done": True, "nothing": None, "list": [1, 2.5, "three", [4, 5], False],
             "stats": {"level": 3, "name": "Ada", "items": ["sword", "key"], "pet": {"hp": 7.5}}}
SAVE_ERRORS = [
    ('game:save("fn", show_all)', "game:save can keep numbers, text, true/false, lists and tables, not a function."),
    ('game:save("sprite", [1, label])', "game:save can keep numbers, text, true/false, lists and tables, not a sprite."),
    ('game:save(5, "best")', 'game:save needs the save\'s name as text first, like game:save("best", score), not a number.'),
    ('game:save("  ", 1)', 'A save needs a name, like "best"'),
    ('say game:load(true)', 'game:load needs the save\'s name as text first, like best = game:load("best", 0), not true/false.'),
    ('game:store("best", 1)', "A game doesn't have :store. Use :save instead."),
    ('game:read("best")', "A game doesn't have :read. Use :load instead."),
]
SAVE_CHECK_GOOD = [
    # Every way the four are written, in 2D (with a table from tap) and in 3D.
    'mention tap\ngame = tgame.window("Saves", 400, 300)\nbest = game:load("best", 0)\nif game:saved("best"):\n    say best + 1\n'
    'game:save("best", best)\ngame:save("name", "Ada")\ngame:save("list", [1, [2, "three"]])\ngame:save("flag", true)\n'
    'game:save("none", nil)\nline = say "hi"\ngame:save("line", line)\nstats = tap.data()\nstats:set("level", 3)\n'
    'game:save("stats", stats)\ns = game:load("stats")\nsay s:get("level")\nhas = game:saved("x")\nif has and best > 2:\n'
    '    say "yes"\ngame:forget("best")\ngame:forget()\ngame:forget\nfunc step(dt):\n    game:save("time", game:time())\n'
    'game:every_frame step\n',
    'world = tgame.world("Saves 3D")\nvisits = world:load("visits", 0) + 1\nworld:save("visits", visits)\n'
    'if world:saved("visits"):\n    world:forget("visits")\nworld:save("spot", world:player():spot())\n',
]
SAVE_CHECK_BAD = [
    ('game = tgame.window("x")\ngame:save("best")\n',
     'game:save got the wrong number of inputs (1). It takes a name, then what to save, like: game:save("best", score)'),
    ('game = tgame.window("x")\nscore = 5\ngame:save(score, "best")\n',
     'game:save needs the save\'s name as text first, like game:save("best", score), not a number.'),
    ('game = tgame.window("x")\ngame:save("step", step)\nfunc step(dt):\n    nil\n',
     "game:save can keep numbers, text, true/false, lists and tables, not a function."),
    ('game = tgame.window("x")\nb = game:box(1, 2)\ngame:save("b", b)\n', "game:save can keep numbers, text, true/false, lists and tables, not a sprite."),
    ('w = tgame.world("x")\nw:save("p", w:player())\n', "w:save can keep numbers, text, true/false, lists and tables, not a player."),
    ('game = tgame.window("x")\ngame:save("lib", tgame)\n', "game:save can keep numbers, text, true/false, lists and tables, not a library."),
    ('game = tgame.window("x")\ngame:save("", 1)\n', 'A save needs a name, like "best": game:save("best", score)'),
    ('game = tgame.window("x")\nx = game:load()\n', "game:load got the wrong number of inputs (0). It takes the save's name, then what to give back"),
    ('game = tgame.window("x")\nx = game:load(3)\n', 'game:load needs the save\'s name as text first, like best = game:load("best", 0), not a number.'),
    ('game = tgame.window("x")\nx = game:load("a", 1, 2)\n', "game:load got the wrong number of inputs (3)."),
    ('game = tgame.window("x")\nsay game:saved()\n', 'game:saved got the wrong number of inputs (0). It takes the save\'s name, like: game:saved("best")'),
    ('game = tgame.window("x")\nif game:saved(true):\n    say 1\n', "game:saved needs the save's name as text first"),
    ('game = tgame.window("x")\ngame:forget("a", "b")\n', "game:forget got the wrong number of inputs (2). It takes the save's name, or nothing to forget every save"),
    ('game = tgame.window("x")\ngame:forget([1])\n', "game:forget needs the save's name as text first"),
    ('game = tgame.window("x")\ngame:store("best", 1)\n', "A game doesn't have :store. Use :save instead."),
    ('game = tgame.window("x")\ngame:save_data("best", 1)\n', "A game doesn't have :save_data. Use :save instead."),
    ('w = tgame.world("x")\nsay w:read("best")\n', "A world doesn't have :read. Use :load instead."),
    ('game = tgame.window("x")\nx = game:get_data("best")\n', "A game doesn't have :get_data. Use :load instead."),
    ('game = tgame.window("x")\ngame:delete("best")\n', "A game doesn't have :delete. Use :forget instead."),
    ('game = tgame.window("x")\ngame:reset_save()\n', "A game doesn't have :reset_save. Use :forget instead."),
    ('game = tgame.window("x")\nenemy = game:box(1, 2)\ngame:delete(enemy)\n',
     "A game doesn't have :delete. To take enemy out of the game, use enemy:remove()."),
    ('game = tgame.window("x")\nx = game:saved("a")\nx:add(1)\n', "True/false doesn't have any :methods."),
]


def t_saves(c):
    """Saved game data: game:save keeps a number, text, true/false, nil, a list and a table (with a list and a table in
    it); after the game restarts game:load gives them back (lists as lists, tables as data objects), with defaults for
    what was never saved; :saved and :forget; friendly errors; a damaged save file is set aside and the game starts
    fresh; a game with another title (a 3D world) never mixes with it; --scene never saves; and the checker."""
    folder = save_dir("main")
    env = {"TUFF_SAVE_DIR": folder}
    file, other = os.path.join(folder, "Save Test.json"), os.path.join(folder, "Other Save Test.json")
    tries = [{"at": 0.8 + i * 0.05, "tuff": src} for i, (src, _want) in enumerate(SAVE_ERRORS)]
    r = play("save_1", game("save_data.tuf"), [{"at": 0.3, "call": "show_all"}, {"at": 0.5, "call": "save_all"},
                                               {"at": 0.7, "call": "show_all"}, *tries, {"at": 1.4, "close": True}], env=env)
    first_line_is_notice(c, r)
    clean_exit(c, r)
    said = [line for line in r.lines[1:] if not line.startswith("[autopilot]")]
    c.check(said[:1] == ["run 1"], "the first run finds nothing saved: run 1", said[:1])
    c.check(said[1:8] == SAVE_DEFAULTS, "before anything is saved, game:load gives the default (nil without one) and game:saved is false", said[1:8])
    c.check(said[8:16] == ["saved"] + SAVE_SHOWN, "game:save keeps a number, text, true, nil, a list and a table, and game:load gives them back",
            said[8:16])
    errors = [line for line in r.lines if line.startswith("[autopilot]")]
    for src, want in SAVE_ERRORS:
        c.check(any(line.startswith(f"[autopilot] {src}: ") and want in line for line in errors), f"{src}: {want}", errors)
    data = read_json(file)
    c.check(same_json(data, {"game": "Save Test", "saves": {"runs": 1, **SAVE_FILE}}),
            "the saves are one JSON file named after the game's title (not what game:title changed the window to), with nothing the errors tried", data)
    c.check(sorted(os.listdir(folder)) == ["Save Test.json"], "nothing else is in the folder (no temporary files left behind)", os.listdir(folder))

    o = play("save_other_1", game("save_other.tuf"), [{"at": 0.5, "close": True}], env=env)
    clean_exit(c, o)
    c.check(o.lines[1:] == ["other best nil false", "other visits 1"], "a game with another title (a 3D world) doesn't see Save Test's saves", o.lines)

    r = play("save_2", game("save_data.tuf"), [{"at": 0.3, "call": "show_all"}, {"at": 0.5, "call": "forget_some"},
                                               {"at": 0.7, "close": True}], env=env)
    clean_exit(c, r)
    c.check(r.lines[1:2] == ["run 2"], "run again, the game finds what it saved last time (runs is 1 + 1)", r.lines[1:2])
    c.check(r.lines[2:9] == SAVE_SHOWN, "everything comes back the same after the restart (and the other game's best, 7, didn't get in)", r.lines[2:9])
    c.check(r.lines[9:] == ["forgot best false 0 true"], "game:forget(\"best\") forgets just that one (and a name never saved is fine)", r.lines[9:])
    data = read_json(file) or {}
    c.check(same_json(data.get("saves"), {"runs": 2, **{k: v for k, v in SAVE_FILE.items() if k != "best"}}), "the file forgot it too", data)

    before, when = open(file, "rb").read(), os.path.getmtime(file)
    code, _out, err, d, _secs = scene(game("save_data.tuf"), env=env)
    batch = json.dumps(d.get("batch") or [])
    c.check(code == 0 and d.get("stopped") == "end" and "Tuff error" not in err and "Traceback" not in err,
            "--scene previews a game that saves and loads", (code, d.get("stopped"), err[-400:]))
    c.check('"Run 1"' in batch and '"Run 3"' not in batch, "in --scene, game:load gives the default even with saves there (the preview says Run 1)",
            [x for x in ("Run 1", "Run 2", "Run 3") if f'"{x}"' in batch])
    c.check(open(file, "rb").read() == before and os.path.getmtime(file) == when, "and --scene leaves the save file alone", None)
    empty = save_dir("scene")
    code, _out, err, d, _secs = scene(game("save_data.tuf"), env={"TUFF_SAVE_DIR": empty})
    c.check(code == 0 and not os.listdir(empty), "--scene with nothing saved writes nothing", os.listdir(empty))

    o = play("save_other_2", game("save_other.tuf"), [{"at": 0.5, "close": True}], env=env)
    clean_exit(c, o)
    c.check(o.lines[1:] == ["other best 7 false", "other visits 2"], "the 3D world keeps its own saves across runs too", o.lines)
    c.check(same_json((read_json(other) or {}).get("saves"), {"best": 7, "visits": 2}), "in a file of its own, Other Save Test.json", read_json(other))

    r = play("save_3", game("save_data.tuf"), [{"at": 0.3, "call": "forget_all"}, {"at": 0.5, "close": True}], env=env)
    clean_exit(c, r)
    c.check(r.lines[1:] == ["run 3", "forgot all false false nil"], "game:forget() forgets every save the game has", r.lines)
    c.check(not os.path.exists(file) and os.path.exists(other), "its file is gone, and the other game's saves are still there", os.listdir(folder))

    # A damaged save file: set aside as .bad (with a note on stderr), and the game starts with nothing saved.
    folder = save_dir("damaged")
    file = os.path.join(folder, "Save Test.json")
    for i, broken in enumerate(('{"game": "Save Test", "saves": {"runs": 4', "[1, 2, 3]", "\xff\xfe not text")):
        with open(file, "wb") as f:
            f.write(broken.encode("latin-1"))
        r = play(f"save_damaged_{i}", game("save_data.tuf"), [{"at": 0.3, "call": "show_all"}, {"at": 0.5, "close": True}],
                 env={"TUFF_SAVE_DIR": folder})
        what = ("cut off", "JSON but not a save file", "not text")[i]
        c.check(r.code == 0 and "Traceback" not in r.err and r.lines[1:3] == ["run 1", "best 0"],
                f"a damaged save file ({what}) doesn't stop the game: it starts with nothing saved", (r.code, r.lines[1:3], r.err[-400:]))
        c.check(f'The saved data for "Save Test" was damaged, so the game starts with nothing saved. The old file is kept as {file}.bad.' in r.err,
                "a note on stderr says so, and where the old file is", r.err[-400:])
        c.check(open(file + ".bad", "rb").read() == broken.encode("latin-1") and same_json((read_json(file) or {}).get("saves"), {"runs": 1}),
                "the old file is kept as Save Test.json.bad, and a new one is saved", sorted(os.listdir(folder)))

    # The checker: every way the four are written passes, and their mistakes are caught.
    check_dir = os.path.join(HERE, "out", "checker")
    os.makedirs(check_dir, exist_ok=True)
    for name in ("save_data.tuf", "save_other.tuf"):
        p = subprocess.run(tuff_cmd() + ["--check", game(name)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"--check accepts {name}", (p.stdout + p.stderr)[:400])
    for i, src in enumerate(SAVE_CHECK_GOOD):
        path = os.path.join(check_dir, f"save_good{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0, f"--check accepts saves snippet {i + 1}", (p.stdout + p.stderr)[:400])
    for i, (src, want) in enumerate(SAVE_CHECK_BAD):
        path = os.path.join(check_dir, f"save_bad{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 1 and want in p.stderr, f"--check catches: {want}", p.stderr[:400])


# ---------------------------------------------------------------- performance

def perf(c, name, program, steps, label):
    r = play(name, game(program), steps, timeout=90)
    clean_exit(c, r)
    d = r.dumps.get(f"{name}.json", {})
    page = d.get("page") or {}
    numbers = {"python_fps": d.get("python_fps"), "tuff_ms_median": d.get("tuff_ms_median"), "tuff_ms_p95": d.get("tuff_ms_p95"),
               "engine_ms_median": d.get("engine_ms_median"), "engine_ms_p95": d.get("engine_ms_p95"),
               "page_fps": round(page.get("fps", 0), 1), "page_batches_per_s": round(page.get("batches", 0) / max(0.001, page.get("seconds", 1)), 1),
               "page_draw_ms": round(page.get("draw_ms_per_frame", 0), 3), "page_apply_ms": round(page.get("apply_ms_per_batch", 0), 3),
               "page_draws_per_s": round(page.get("draws", 0) / max(0.001, page.get("seconds", 1)), 1), "objects": page.get("objects")}
    if isinstance(page.get("physics"), dict):
        numbers["physics"] = page["physics"]
    print(f"  NUMBERS {label}: {json.dumps(numbers)}", flush=True)
    c.check((d.get("python_fps") or 0) >= 55, f"{label}: the Tuff program runs at {d.get('python_fps')} fps (want 60)", numbers)
    return numbers


def t_perf(c):
    walk = [{"at": 0.5, "lock": True}, {"at": 1.0, "mark": True}, {"at": 1.1, "hold": "w", "for": 4.5}]
    walk += [{"at": 1.2 + i * 0.25, "look": [40 if i % 8 < 4 else -40, 6 if i % 4 < 2 else -6]} for i in range(18)]
    results = {
        "2d_tuff_moves_200": perf(c, "perf_2d", "perf_2d.tuf", [{"at": 1.0, "mark": True}, {"at": 6.0, "dump": "perf_2d.json"},
                                                                {"at": 6.05, "shot": "perf_2d.png"}, {"at": 6.2, "close": True}],
                                  "200 sprites moved by Tuff code"),
        "2d_speed_200": perf(c, "perf_2d_speed", "perf_2d_speed.tuf", [{"at": 1.0, "mark": True}, {"at": 6.0, "dump": "perf_2d_speed.json"},
                                                                       {"at": 6.2, "close": True}], "200 sprites moving by :speed"),
        "3d_fp_300": perf(c, "perf_3d", "perf_3d.tuf", walk + [{"at": 6.0, "dump": "perf_3d.json"}, {"at": 6.05, "shot": "perf_3d.png"},
                                                               {"at": 6.2, "close": True}], "300 objects, first-person walk"),
        "3d_tuff_moves_300": perf(c, "perf_3d_move", "perf_3d_move.tuf", walk + [{"at": 6.0, "dump": "perf_3d_move.json"},
                                                                                 {"at": 6.05, "shot": "perf_3d_move.png"}, {"at": 6.2, "close": True}],
                                  "300 boxes moved by Tuff code, first-person walk"),
    }
    with open(os.path.join(OUT, "perf.json"), "w") as f:
        json.dump(results, f, indent=2)
    fp = results["3d_fp_300"]
    c.check(fp["page_draws_per_s"] <= 80,
            f"300 objects from the kit: the page draws {fp['page_draws_per_s']} times a second, as often as the world changes "
            f"({fp['page_draw_ms']} ms a display frame): swaying trees don't make a fast screen draw it at its full rate", fp)


# ---------------------------------------------------------------- the HUD: health bars, countdowns, arrows, minimaps

GREEN_BAR, RED_BAR, GOLD = hexrgb("#3ccf6e"), hexrgb("#ef4b4b"), hexrgb("#f2c230")


def t_hud_health_3d(c):
    """games/hud_health_3d.tuf: bars over a falling physics crate and a labelled guard, and the player's along the
    bottom; :hurt and :heal (health stays from 0 to the most), :on_death once each time the health runs out."""
    r = play("hud_health_3d", game("hud_health_3d.tuf"), [
        {"at": 0.3, "tuff": "crate:hurt(30)"},
        {"at": 0.4, "tuff": "guard:hurt(20)"},
        {"at": 0.45, "tuff": "me:hurt(25)"},
        {"at": 1.5, "shot": "hud_health_3d.png"},
        {"at": 1.55, "call": "report"},
        {"at": 1.6, "tuff": "guard:hurt(40)"},
        {"at": 1.65, "tuff": "guard:hurt(5)"},
        {"at": 1.7, "tuff": "guard:heal(10)"},
        {"at": 1.75, "tuff": "guard:hurt(10)"},
        {"at": 1.8, "tuff": "crate:heal(500)"},
        {"at": 1.85, "tuff": "me:hurt(80)"},
        {"at": 2.5, "shot": "hud_health_3d_after.png"},
        {"at": 2.55, "call": "report"},
        {"at": 2.6, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    c.check("crate 70 guard 30 me 75 deaths 0" in r.lines, ":hurt takes health off (crate 70, guard 30, player 75)", r.lines)
    c.check(r.lines.count("gone guard") == 2 and "crate 100 guard 0 me 0 deaths 2" in r.lines,
            "at 0 :on_death runs (once: hurting it more doesn't run it again), :heal tops up to the most, and a heal "
            "and another hurt run it again", r.lines)
    shot, after = r.shots.get("hud_health_3d.png"), r.shots.get("hud_health_3d_after.png")
    c.check(shot and color_share(shot, GREEN_BAR, 30, (0.25, 0.15, 0.75, 0.6), 2) > 0.0008,
            "green bars float over the crate and the guard", shot)
    c.check(shot and color_share(shot, GREEN_BAR, 30, (0, 0.85, 0.35, 1), 2) > 0.01,
            "the player's bar is along the bottom left", shot)
    c.check(after and color_share(after, GREEN_BAR, 30, (0, 0.85, 0.35, 1), 2) < 0.002,
            "and it's empty once the player's health is gone", after)


def t_hud_health_2d(c):
    """games/hud_health_2d.tuf: bars over sprites (a moving one too), and the countdown: it stops while the game is
    paused, turns red under 10 seconds, runs its function at 0, and starts again with clock:add."""
    r = play("hud_health_2d", game("hud_health_2d.tuf"), [
        {"at": 0.3, "tuff": "hero:hurt(4)"},
        {"at": 0.35, "tuff": "slime:hurt(1)"},
        {"at": 0.8, "shot": "hud_health_2d.png"},
        {"at": 0.85, "call": "report"},
        {"at": 0.9, "tuff": "game:pause()"},
        {"at": 2.0, "call": "report"},
        {"at": 2.1, "tuff": "game:resume()"},
        {"at": 2.2, "tuff": "slime:hurt(5)"},
        {"at": 2.5, "shot": "hud_health_2d_after.png"},
        {"at": 4.8, "call": "report"},
        {"at": 4.85, "tuff": "clock:add(1)"},
        {"at": 6.4, "call": "report"},
        {"at": 6.5, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    reports = [line for line in r.lines if line.startswith("hero ")]
    c.check(reports[:2] == ["hero 6 slime 2 left 3 dead 0 ends 0"] * 2,
            "health goes down, and the countdown holds still while the game is paused", reports)
    c.check("gone slime" in r.lines and reports[2:3] == ["hero 6 slime 0 left 0 dead 1 ends 1"],
            "the slime's :on_death ran, and at 0 the countdown ran its function", reports)
    c.check(reports[3:4] == ["hero 6 slime 0 left 0 dead 1 ends 2"] and "times up 2" in r.lines,
            "clock:add gave it more time, and it ran out again", reports)
    shot, after = r.shots.get("hud_health_2d.png"), r.shots.get("hud_health_2d_after.png")
    c.check(shot and color_share(shot, GREEN_BAR, 30, (0.15, 0.45, 0.85, 0.65), 2) > 0.002,
            "green bars over the hero and the slime", shot)
    c.check(shot and color_share(shot, GREEN_BAR, 30, (0.1, 0.18, 0.35, 0.32), 2) > 0.002,
            "and over the bat, which moves", shot)
    c.check(shot and color_share(shot, RED_BAR, 40, (0.7, 0, 1, 0.17), 2) > 0.003,
            "the countdown is in the top right, red under 10 seconds", shot)
    c.check(after and color_share(after, GREEN_BAR, 30, (0.55, 0.45, 0.85, 0.65), 2) < 0.0005,
            "the slime's bar went with it when :on_death hid it", after)

    # games/hud_clock_clear.tuf: game:clear() (the next level) doesn't stop a countdown of 2 s.
    r = play("hud_clock_clear", game("hud_clock_clear.tuf"), [
        {"at": 0.5, "call": "next_level"}, {"at": 1.3, "call": "report"}, {"at": 2.6, "call": "report"}, {"at": 2.7, "close": True}])
    clean_exit(c, r)
    reports = [line for line in r.lines if line.startswith("left ")]
    c.check(reports == ["left 1 ends 0", "left 0 ends 1"] and "times up 1" in r.lines,
            "after game:clear() the countdown keeps going, and runs its function at 0", r.lines)


def t_hud_arrow(c):
    """games/hud_arrow.tuf: the arrow over the chest in view, at the left edge when the camera looks right, along the
    bottom when the chest is behind, hidden, and pointing at a spot."""
    r = play("hud_arrow", game("hud_arrow.tuf"), [
        {"at": 0.8, "shot": "hud_arrow_over.png"},
        {"at": 0.85, "tuff": "world:look_at(30, 1, 6)"},
        {"at": 1.1, "shot": "hud_arrow_side.png"},
        {"at": 1.15, "tuff": "world:look_at(0, 1, 40)"},
        {"at": 1.4, "shot": "hud_arrow_behind.png"},
        {"at": 1.45, "tuff": "arrow:hide()"},
        {"at": 1.7, "shot": "hud_arrow_hidden.png"},
        {"at": 1.75, "tuff": "world:look_at(0, 1, 0)"},
        {"at": 1.8, "tuff": "world:arrow_to(-12, 0, -4)"},
        {"at": 1.85, "tuff": "arrow:show()"},
        {"at": 2.1, "shot": "hud_arrow_spot.png"},
        {"at": 2.2, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    s = r.shots
    c.check(s.get("hud_arrow_over.png") and color_share(s["hud_arrow_over.png"], GOLD, 30, (0.4, 0.15, 0.6, 0.5), 2) > 0.002,
            "in view, the arrow is over the chest", s.get("hud_arrow_over.png"))
    c.check(s.get("hud_arrow_side.png") and color_share(s["hud_arrow_side.png"], GOLD, 30, (0, 0, 0.1, 1), 2) > 0.002,
            "looking away to the right, it waits at the left edge", s.get("hud_arrow_side.png"))
    c.check(s.get("hud_arrow_behind.png") and color_share(s["hud_arrow_behind.png"], GOLD, 30, (0.4, 0.8, 0.6, 1), 2) > 0.002,
            "with the chest behind, it's along the bottom", s.get("hud_arrow_behind.png"))
    c.check(s.get("hud_arrow_hidden.png") and color_share(s["hud_arrow_hidden.png"], GOLD, 30, (0.4, 0.8, 0.6, 1), 2) < 0.0003,
            "arrow:hide hides it", s.get("hud_arrow_hidden.png"))
    c.check(s.get("hud_arrow_spot.png") and color_share(s["hud_arrow_spot.png"], GOLD, 30, (0, 0.1, 0.45, 0.6), 2) > 0.001,
            "world:arrow_to(x, y, z) points at a spot, and arrow:show shows it again", s.get("hud_arrow_spot.png"))


def t_hud_minimap(c):
    """games/hud_minimap.tuf: the round map in the top right under the countdown, with the lake, the marks (gold,
    and a red one), the player; zoomed in; then moved to the bottom left while the player walks."""
    r = play("hud_minimap", game("hud_minimap.tuf"), [
        {"at": 1.0, "shot": "hud_minimap.png"},
        {"at": 1.05, "tuff": "map:zoom(2)"},
        {"at": 1.3, "shot": "hud_minimap_zoom.png"},
        {"at": 1.35, "tuff": "world:minimap(220, \"bottom left\")"},
        {"at": 1.4, "hold": "w", "for": 0.6},
        {"at": 2.3, "shot": "hud_minimap_moved.png"},
        {"at": 2.4, "close": True},
    ])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    s = r.shots
    box = (0.77, 0.11, 0.99, 0.46)  # 180 pixels across, under the countdown, in a 900 x 560 window
    shot = s.get("hud_minimap.png")
    water = shot and (color_share(shot, hexrgb("#2f7fc8"), 30, box, 2) + color_share(shot, hexrgb("#4f9fe3"), 30, box, 2))
    c.check(water and water > 0.02, f"the map shows the lake ({water and round(water, 3)})", shot)
    c.check(shot and color_share(shot, GOLD, 30, box, 1) > 0.001, "gold dots for the coins", shot)
    c.check(shot and color_share(shot, hexrgb("#e5484d"), 30, box, 1) > 0.0005, "a red dot for the rock", shot)
    c.check(shot and color_share(shot, (245, 245, 245), 45, box, 1) > 0.02, "a white rim and the player's arrow", shot)
    c.check(shot and color_share(shot, (255, 255, 255), 20, (0.8, 0, 1, 0.1), 1) > 0.005, "the countdown above it", shot)
    zoom = s.get("hud_minimap_zoom.png")
    zw = zoom and (color_share(zoom, hexrgb("#2f7fc8"), 30, box, 2) + color_share(zoom, hexrgb("#4f9fe3"), 30, box, 2))
    c.check(zw and zw > water, f"map:zoom(2) shows the lake bigger ({zw and round(zw, 3)})", zoom)
    moved = s.get("hud_minimap_moved.png")
    lake = lambda shot, box: color_share(shot, hexrgb("#2f7fc8"), 30, box, 2) + color_share(shot, hexrgb("#4f9fe3"), 30, box, 2)
    c.check(moved and color_share(moved, (245, 245, 245), 45, (0, 0.5, 0.3, 1), 1) > 0.02 and lake(moved, (0, 0.5, 0.3, 1)) > 0.02
            and lake(moved, (0.78, 0.12, 0.99, 0.32)) < 0.002,
            "world:minimap(220, \"bottom left\") moves it to the bottom left", moved)

    # games/hud_drive.tuf: where the map and the arrow measure from (the page's TgHud.viewer), against where the
    # player and the car are.
    probe = ("const h = document.querySelector('tg-hud'); const v = h.viewer(tv.objs.get(h.opts.view)).at;"
             "tv.emit('tg-autopilot', {message: 'viewer ' + v.x.toFixed(2) + ' ' + v.z.toFixed(2)});")
    r = play("hud_drive", game("hud_drive.tuf"), [
        {"at": 0.8, "call": "report"}, {"at": 0.8, "js": probe},
        {"at": 0.9, "call": "get_in"}, {"at": 1.0, "hold": "w", "for": 2.4},
        {"at": 3.6, "call": "report"}, {"at": 3.6, "js": probe},
        {"at": 3.8, "call": "get_out"}, {"at": 4.1, "call": "report"}, {"at": 4.1, "js": probe},
        {"at": 4.3, "close": True}])
    clean_exit(c, r)
    viewers = [[float(v) for v in line.split()[2:4]] for line in r.lines if line.startswith("[autopilot] viewer ")]
    spots = [[float(v) for v in line.translate(str.maketrans("[],", "   ")).split()[1:] if v != "player"]
             for line in r.lines if line.startswith("car [")]  # the car's x, y, z, then the player's
    near = lambda i, at, most: len(viewers) > i and len(spots) > i and math.dist(viewers[i], (spots[i][at], spots[i][at + 2])) < most
    c.check(near(0, 3, 0.3), "made before the third-person player, they measure from its figure (not the camera behind it)",
            (viewers, spots))
    c.check(near(1, 0, 2.5) and len(spots) > 1 and math.dist(spots[0][:3:2], spots[1][:3:2]) > 5,
            "while it drives, from the car (not from where it got in)", (viewers, spots))
    c.check(near(2, 3, 0.3), "and once it's out, from its figure again", (viewers, spots))

    # games/hud_ragdoll.tuf: the minimap (180 px, top right, the player in its middle) with a ragdoll marked red at
    # (12, 0, -12) and a rock gold at (-12, 0, -12): both dots 21.6 px up and 21.6 px to the side of the middle.
    r = play("hud_ragdoll", game("hud_ragdoll.tuf"), [{"at": 1.2, "shot": "hud_ragdoll.png"}, {"at": 1.3, "close": True}])
    clean_exit(c, r)
    shot = r.shots.get("hud_ragdoll.png")
    red = hexrgb("#e5484d")
    c.check(shot and color_share(shot, GOLD, 40, (0.846, 0.125, 0.876, 0.172), 1) > 0.05, "the rock's dot is up and to the left", shot)
    c.check(shot and color_share(shot, red, 40, (0.893, 0.125, 0.923, 0.172), 1) > 0.05,
            "the ragdoll's dot is where it stands, up and to the right (not in the middle)", shot)

    # games/hud_panel.tuf: a panel in the top right, a countdown and a minimap. In the top 200 pixels of the page's HUD,
    # nothing is drawn under the panel (`under`), and the first row drawn on (`first`, the countdown's top) is just
    # under the panel's bottom; once the panel's hidden, it's back at the top.
    probe = ("const h = document.querySelector('tg-hud'); const d = document.querySelector('.tg-ui .tg-dock-top-right').getBoundingClientRect();"
             "const c = h.canvas.getBoundingClientRect(); const k = h.canvas.width / c.width; const W = h.canvas.width, H = Math.round(200 * k);"
             "const a = h.ctx.getImageData(0, 0, W, H).data; let under = 0, first = -1;"
             "for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { if (a[(y * W + x) * 4 + 3] <= 8) continue;"
             " const px = c.left + x / k, py = c.top + y / k; if (first < 0) first = Math.round(py - c.top);"
             " if (px >= d.left && px <= d.right && py >= d.top && py <= d.bottom) under++; }"
             "tv.emit('tg-autopilot', {message: 'panel ' + JSON.stringify({tall: Math.round(d.height), bottom: Math.round(d.bottom - c.top), under, first})});")
    r = play("hud_panel", game("hud_panel.tuf"), [
        {"at": 1.0, "js": probe}, {"at": 1.1, "shot": "hud_panel.png"},
        {"at": 1.2, "call": "hide_bar"}, {"at": 1.5, "js": probe}, {"at": 1.6, "close": True}])
    clean_exit(c, r)
    panels = [json.loads(line.split("panel ", 1)[1]) for line in r.lines if line.startswith("[autopilot] panel ")]
    shown, hidden = (panels + [{}, {}])[:2]
    c.check(shown.get("tall", 0) > 20 and shown.get("under") == 0 and 0 < shown.get("first", 0) - shown.get("bottom", 0) < 20,
            "the countdown and the minimap go under a panel in the top right, not under it", panels)
    c.check(hidden.get("tall") == 0 and 10 <= hidden.get("first", 0) <= 18, "with the panel hidden, the countdown is at the top again", panels)


def t_hud_checker(c):
    """--check knows the HUD's names, what they give back and what their functions get; their mistakes have
    kid-friendly messages, when checking and when running."""
    for name in ("hud_health_3d.tuf", "hud_health_2d.tuf", "hud_arrow.tuf", "hud_minimap.tuf", "hud_clock_clear.tuf",
                 "hud_drive.tuf", "hud_ragdoll.tuf", "hud_panel.tuf"):
        p = subprocess.run(tuff_cmd() + ["--check", game(name)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"--check accepts {name}", (p.stdout + p.stderr)[:400])
    folder = os.path.join(OUT, "hud")
    os.makedirs(folder, exist_ok=True)
    bad = [
        ('w = tgame.world("x")\nm = w:minimap(180, "middle")\n', "A minimap can go in the top right, top left, bottom left or bottom right corner"),
        ('w = tgame.world("x")\nm = w:minimap()\ncoin = w:spawn("coin")\nm:mark(coin, "goldd")\n', "'goldd' isn't a color tgame knows."),
        ('game = tgame.window("x")\nb = game:box(1, 2)\nb:damage(3)\n', "A sprite doesn't have :damage. Use :hurt instead."),
        ('w = tgame.world("x")\nt = w:timer(30)\n', "A world doesn't have :timer. Use :countdown instead."),
        ('game = tgame.window("x")\nclock = game:countdown(10)\nsay clock:time_left()\n', "A countdown doesn't have :time_left. Use :left instead."),
        ('game = tgame.window("x")\nclock = game:countdown(10, done)\nfunc done(a, b):\n    nil\n', "done() needs 2 inputs, but game:countdown gives it no inputs"),
        ('w = tgame.world("x")\ne = w:spawn("person")\ne:on_death(gone)\nfunc gone(a, b):\n    nil\n', "gone() needs 2 inputs, but e:on_death gives it 1 input"),
        ('w = tgame.world("x")\na = w:arrow_to(1, 2, 3)\na:hide(1)\n', "a:hide got the wrong number of inputs (1)."),
        ('w = tgame.world("x")\nm = w:map()\n', "A world doesn't have :map. Use :minimap instead."),
        ('w = tgame.world("x")\nm = w:minimap(50)\n',
         "w:minimap needs its size in pixels first, from 60 to 600 (180 is normal), like map = w:minimap(180)."),
        ('w = tgame.world("x")\nm = w:minimap(1000, "top left")\n', "w:minimap needs its size in pixels first, from 60 to 600"),
    ]
    for i, (src, want) in enumerate(bad):
        path = os.path.join(folder, f"bad{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 1 and want in p.stderr, f"--check catches: {want}", p.stderr[:400])
    running = [
        ('w = tgame.world("x")\ncrate = w:spawn("crate")\ncrate:hurt(5)\n', "crate:hurt needs health first. Give it a health bar, like crate:health_bar(100)."),
        ('game = tgame.window("x")\ngame:minimap()\n', "The minimap needs a 3D world. Make the game with tgame.world(...) for one."),
        ('game = tgame.window("x")\nb = game:box(1, 2)\nb:health_bar(10)\nb:hurt(-2)\n', "box:hurt needs a number of 0 or more. To heal it, use :heal."),
        ('w = tgame.world("x")\nm = w:minimap(180, "middle")\n', "A minimap can go in the top right, top left, bottom left or bottom right corner, not \"middle\"."),
    ]
    for i, (src, want) in enumerate(running):
        path = os.path.join(folder, f"run{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        run = play(f"hud_run{i}", path, [{"at": 0.5, "close": True}])
        c.check(run.code == 1 and want in run.err, f"running it says: {want}", run.err[-400:])


# ---------------------------------------------------------------- multiplayer (game:host, game:join...)

# The tests' rooms stay on this computer (127.0.0.1: no firewall questions), on ports of their own, away from a real
# game someone might be hosting meanwhile.
os.environ.setdefault("TUFF_NET_LOCAL", "1")
os.environ.setdefault("TUFF_NET_PORT", "47900")


def start_play(name, program, steps, seed=1, env=None):
    """play()'s start, without waiting for the game: games that play together start one after another, then
    finish_play waits for each."""
    os.makedirs(OUT, exist_ok=True)
    plan = {"on_top": True, "out": OUT, "seed": seed, "steps": steps,
            "timeout": max([s.get("at", 0) for s in steps] + [0]) + 15}
    plan_file = os.path.join(OUT, f"{name}.plan.json")
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    for s in steps:
        for key in ("dump", "shot"):
            if key in s and os.path.exists(os.path.join(OUT, s[key])):
                os.remove(os.path.join(OUT, s[key]))
    full_env = {**os.environ, "TUFF_TGAME_AUTOPILOT": plan_file, "PYTHONIOENCODING": "utf-8", **(env or {})}
    full_env.pop("TUFF_IDE", None)
    p = subprocess.Popen(tuff_cmd() + [program], cwd=os.path.dirname(program), env=full_env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    return p, steps, time.perf_counter()


def finish_play(started, timeout=60):
    p, steps, t0 = started
    try:
        out, err = p.communicate(timeout=max(1, timeout - (time.perf_counter() - t0)))
        code = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
        code, err = "timeout", "timed out"
    dumps, shots = {}, {}
    for s in steps:
        if "dump" in s:
            try:
                with open(os.path.join(OUT, s["dump"]), encoding="utf-8") as f:
                    dumps[s["dump"]] = json.load(f)
            except (OSError, ValueError):
                dumps[s["dump"]] = {}
        if "shot" in s and os.path.exists(os.path.join(OUT, s["shot"])):
            shots[s["shot"]] = os.path.join(OUT, s["shot"])
    return Played(code, out, err, dumps, shots, time.perf_counter() - t0)


def play_together(*games, gap=0.4):
    """Games that play together: (name, program, steps, env) each, started `gap` seconds apart (the host first)."""
    started = []
    for name, program, steps, env in games:
        started.append(start_play(name, program, steps, env=env))
        time.sleep(gap)
    return [finish_play(s) for s in started]


def net_of(d):
    return d.get("net") or {}


def t_net(c):
    """Two 3D games on this computer: one hosts a room, the other finds it (world:join()) and goes in. Each sees the
    other's player as a person with their name over it, walking where they walk; messages go both ways; a shared
    value the host changes reaches the other game; and when the joining game closes, the host hears it leave."""
    port = {"TUFF_NET_PORT": "47910"}
    host, joiner = play_together(
        ("net_host", game("net_host.tuf"), [
            {"at": 0.5, "dump": "net_host_start.json"}, {"at": 4.5, "call": "show"}, {"at": 4.6, "dump": "net_host_in.json"},
            {"at": 5.0, "hold": "w", "for": 1.0}, {"at": 11.5, "dump": "net_host_after.json"}, {"at": 11.6, "call": "show"},
            {"at": 12.0, "close": True}], port),
        ("net_join", game("net_join.tuf"), [
            {"at": 2.5, "dump": "net_join_in.json"}, {"at": 2.6, "call": "hit"}, {"at": 3.4, "call": "show"},
            {"at": 3.5, "dump": "net_join_shared.json"}, {"at": 3.55, "shot": "net_join.png"},
            {"at": 8.0, "dump": "net_join_walked.json"}, {"at": 8.05, "shot": "net_join_walked.png"},
            {"at": 8.5, "close": True}], port))
    clean_exit(c, host)
    clean_exit(c, joiner)
    start = net_of(host.dumps.get("net_host_start.json", {}))
    c.check("hosting true" in host.lines and start.get("state") == "in" and start.get("room") == "Test Room",
            "world:host(\"Test Room\") hosts at once: world:hosting() is true on the next line", (host.lines[:4], start))
    said = net_of(host.dumps.get("net_host_in.json", {})).get("said", [])
    c.check('Hosting "Test Room" on this computer' in said and "Sam joined" in said,
            "the HUD says it's hosting the room (on this computer, in a test), then that Sam joined", said)
    inside = net_of(joiner.dumps.get("net_join_in.json", {}))
    c.check(inside.get("state") == "in" and inside.get("room") == "Test Room" and inside.get("players") == ["Player 1", "Sam"],
            "world:join() finds the room on its own and goes in, as Sam (world:my_name), after Player 1 (the host)", inside)
    c.check("joined Player 1" in joiner.lines and "joined Sam" in host.lines,
            "on_join runs on both: the host hears Sam come in, and Sam hears of the host already there", (host.lines, joiner.lines))
    c.check("got welcome Sam from Player 1" in joiner.lines,
            "a message the host sends (world:send(\"welcome\", name)) reaches Sam's on_message", joiner.lines)
    c.check("got hit 2 from Sam" in host.lines,
            "a message Sam sends (world:send(\"hit\", 2)) reaches the host's on_message, with who sent it", host.lines)
    c.check("score 7" in joiner.lines and net_of(joiner.dumps.get("net_join_shared.json", {})).get("shared", {}).get("score") == 7,
            "world:share on the host (5, then 5 + Sam's 2) reaches Sam's world:shared(\"score\")", (joiner.lines, inside.get("shared")))
    others = inside.get("others") or []
    c.check(len(others) == 1 and others[0][0] == "Player 1" and abs(others[0][1]) < 0.3 and abs(others[0][3]) < 0.3 and others[0][5],
            "Sam's world shows the host's player as a person called Player 1, where the host stands (0, 0, 0)", others)
    labels = joiner.dumps.get("net_join_in.json", {}).get("labels", [])
    c.check("Player 1" not in labels, "... a person of tgame's own, like the player's figure (not among the program's things)", labels)
    walked = net_of(joiner.dumps.get("net_join_walked.json", {})).get("others") or []
    c.check(len(walked) == 1 and walked[0][3] < -3.5 and abs(walked[0][1]) < 0.5,
            "when the host walks forward (W for a second), Sam sees its person walk there too (z from 0 to about -5)", walked)
    hothers = net_of(host.dumps.get("net_host_in.json", {})).get("others") or []
    c.check(len(hothers) == 1 and hothers[0][0] == "Sam" and abs(hothers[0][1] - 3) < 0.3 and abs(hothers[0][3] - 2) < 0.3,
            "the host's world shows Sam where Sam stands (3, 0, 2)", hothers)
    c.check("others 1" in host.lines and 'players ["Player 1", "Sam"]' in host.lines, "world:others() and world:players() on the host", host.lines)
    after = net_of(host.dumps.get("net_host_after.json", {}))
    c.check("left Sam" in host.lines and after.get("players") == ["Player 1"] and not after.get("others"),
            "when Sam's game closes, the host hears it leave (on_leave), and its person goes", (host.lines[-4:], after))
    shot, walked_shot = joiner.shots.get("net_join.png"), joiner.shots.get("net_join_walked.png")
    c.check(shot and walked_shot and changed_pixels(shot, walked_shot) > 0.002,
            "Sam's screenshots differ once the host's person has walked away", (shot, walked_shot))


def t_net_2d(c):
    """Two 2D games: the joining one goes straight to an address (game:join("127.0.0.1")), messages carry lists, a
    value the joining game shares before it's in fills in only what the room doesn't have, and when the host closes
    the other game hears that the host left."""
    port = {"TUFF_NET_PORT": "47930"}
    host, joiner = play_together(
        ("net_host_2d", game("net_host_2d.tuf"), [{"at": 6.5, "call": "show"}, {"at": 7.0, "close": True}], port),
        ("net_join_2d", game("net_join_2d.tuf"), [
            {"at": 2.5, "call": "move"}, {"at": 3.0, "dump": "net_join_2d_in.json"}, {"at": 3.1, "call": "show"},
            {"at": 10.0, "dump": "net_join_2d_after.json"}, {"at": 10.1, "call": "show"}, {"at": 10.5, "close": True}], port))
    clean_exit(c, host)
    clean_exit(c, joiner)
    inside = net_of(joiner.dumps.get("net_join_2d_in.json", {}))
    c.check(inside.get("state") == "in" and inside.get("room") == "Net 2D" and inside.get("players") == ["Ana", "Player 2"],
            "game:join(\"127.0.0.1\") goes straight to that computer's room (named after the game: game:host() with no name); "
            "the host is Ana, the joining game Player 2", inside)
    c.check("got at [120, 80] from Player 2" in host.lines, "a list sent with a message arrives as a list", host.lines)
    c.check("got hello [1, 2, 3] from Ana" in joiner.lines, "the host's message reaches the joining game", joiner.lines)
    c.check("level 3 lives 5" in joiner.lines and "level 3 lives 5" in host.lines,
            "the room's level (3) wins over one shared before joining (1), and lives the room didn't have (5) fill in, for both",
            (host.lines, joiner.lines))
    after = net_of(joiner.dumps.get("net_join_2d_after.json", {}))
    c.check("left Ana" in joiner.lines and after.get("state") == "off" and "The host left the game" in after.get("said", []),
            "when the host closes, the other game hears it leave (on_leave) and says \"The host left the game\"", (joiner.lines[-4:], after))
    c.check("connected false" in joiner.lines and after.get("players") == ["Player 2"],
            "then game:connected() is false, and game:players() is only itself", (joiner.lines, after.get("players")))


def t_net_rooms(c):
    """Rooms by name, with four games: two rooms on this computer, two games that join "Blue Room" by its name go in
    that one (not the other), two players with the same name get different names, and Tuff Engine's preview (--scene)
    never opens a room."""
    port = {"TUFF_NET_PORT": "47950"}

    def host(name, room):
        return (name, game("net_room.tuf"), [{"at": 0.1, "tuff": f'game:host("{room}")'}, {"at": 4.5, "dump": f"{name}.json"},
                                              {"at": 9.0, "close": True}], port)

    def joiner(name):
        return (name, game("net_room.tuf"), [{"at": 0.1, "tuff": 'game:my_name("Kim")'}, {"at": 0.15, "tuff": 'game:join("blue  ROOM")'},
                                              {"at": 3.0, "dump": f"{name}.json"}, {"at": 7.0, "close": True}], port)

    red, blue, a, b = play_together(host("net_red", "Red Room"), host("net_blue", "Blue Room"), joiner("net_a"), joiner("net_b"))
    for r in (red, blue, a, b):
        clean_exit(c, r)
    na, nb = net_of(a.dumps.get("net_a.json", {})), net_of(b.dumps.get("net_b.json", {}))
    c.check(na.get("room") == "Blue Room" and nb.get("room") == "Blue Room",
            "game:join(\"blue  ROOM\") finds the room called Blue Room (big or small letters, spaces)", (na, nb))
    c.check(net_of(red.dumps.get("net_red.json", {})).get("players") == ["Player 1"], "... and nobody goes in the other room",
            net_of(red.dumps.get("net_red.json", {})))
    c.check(sorted([na.get("name"), nb.get("name")]) == ["Kim", "Kim 2"] and
            net_of(blue.dumps.get("net_blue.json", {})).get("players") == ["Player 1", "Kim", "Kim 2"],
            "two players both called Kim are Kim and Kim 2, everywhere", (na.get("name"), nb.get("name"), net_of(blue.dumps.get("net_blue.json", {}))))
    code, out, err, dump, secs = scene(game("net_host.tuf"), env={"TUFF_NET_PORT": "47970"})
    c.check(code == 0 and dump.get("error") is None and dump.get("stopped") == "end" and "Hosting" not in json.dumps(dump.get("batch")),
            "in Tuff Engine's preview (--scene), world:host does nothing (and says nothing on the HUD)", (code, err[-300:], dump.get("error")))


TOOLBOX_PROGRAM = '''ages = {"sam": 14, "ann": 12}
ages["bob"] = 15
say ages
for name in ages:
    say name + " is " + ages[name]
say ages:get("zed", 0)
ages:remove("ann")
say ages:keys()
say len(ages)
nested = {
    "red": [3, 4],
    "blue": {"x": 1}
}
say nested["red"][1] + nested["blue"]["x"]
s = "hello world"
say s[0:4] + "|" + s[6:] + "|" + s[:1] + "|" + s[-3:]
say [1, 2, 3, 4, 5][1:3]
say "a,b,c":split(",")
say s:replace("world", "Tuff")
say ["x", "y"]:join(", ")
say s:starts("hell") and s:ends("ld")
say s:find("o") + s:count("l")
say "7":pad_left(3, "0") + "hi":pad_right(4) + "|"
say text(3.14159, 2)
nums = [5, 3, 9, 1]
nums:sort()
say nums
nums:reverse()
say nums
func by_len(w):
    len(w)
words = ["ccc", "a", "bb"]
words:sort(by_len)
say words
file.write("tb_notes.txt", "one\\ntwo")
file.add("tb_notes.txt", "three")
say file.lines("tb_notes.txt")
file.save("tb_data.json", {"name": "Sam", "scores": [1, 2]})
data = file.load("tb_data.json")
say data["name"] + data["scores"][1]
say file.load("tb_missing.json", [])
file.delete("tb_notes.txt")
say file.exists("tb_notes.txt")
try:
    say file.read("tb_nope.txt")
catch problem:
    say "caught " + problem:starts("Couldn't find")
try:
    x = 1 / 0
catch:
    say "caught 2"
catch = 3
say catch
say sin(90) + cos(180)
say round(log(100, 10), 6)
r = random()
say r >= 0 and r <= 1
say len(today()) + len(now())
say date():has("weekday")
'''
TOOLBOX_OUTPUT = ['{"sam": 14, "ann": 12, "bob": 15}', "sam is 14", "ann is 12", "bob is 15", "0", '["sam", "bob"]', "2", "5",
                  "hello|world|he|rld", "[2, 3, 4]", '["a", "b", "c"]', "hello Tuff", "x, y", "true", "7", "007hi  |", "3.14",
                  "[1, 3, 5, 9]", "[9, 5, 3, 1]", '["a", "bb", "ccc"]', '["one", "two", "three"]', "Sam2", "[]", "false",
                  "caught true", "caught 2", "3", "0", "2", "true", "18", "true"]
# The checker on 1.4.0 mistakes: (code, part of the message it gives)
TOOLBOX_MISTAKES = [
    ('d = {"a": 1}\nsay d:valuez()', "Did you mean :values?"),
    ('s = "abc"\nsay s:startswith("a")', ":starts"),
    ('items = [3, 1]\nitems:sort(1, 2)', None),
    ('try:\n    say 1\nsay 2', "needs a catch: block"),
    ('d = {"a": 1}\nsay d:keys(1)', "doesn't take an input"),
    ('say file.reed("x.txt")', "file doesn't have 'reed'"),
]


def t_toolbox(c):
    """1.4.0, the Toolbox Update: dictionaries, parts [a:b], text tools, sorting, files and JSON, try/catch, date/time
    and maths, run for real, then the checker on the same program and on mistakes."""
    folder = os.path.join(HERE, "out", "toolbox")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "toolbox.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TOOLBOX_PROGRAM)
    p = subprocess.run(tuff_cmd() + [path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    got = p.stdout.splitlines()
    c.check(p.returncode == 0, "the toolbox program runs to the end", (p.stdout + p.stderr)[-600:])
    for i, want in enumerate(TOOLBOX_OUTPUT):
        c.check(i < len(got) and got[i] == want, f"line {i + 1}: {want}", got[i] if i < len(got) else "(missing)")
    c.check(not os.path.exists(os.path.join(folder, "tb_notes.txt")) and os.path.exists(os.path.join(folder, "tb_data.json")),
            "file.delete deleted the notes, and file.save left its JSON next to the program")
    p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.stdout.strip() == "OK", "--check accepts all of it", (p.stdout + p.stderr)[:600])
    for i, (code, want) in enumerate(TOOLBOX_MISTAKES):
        bad = os.path.join(folder, f"mistake{i}.tuf")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        p = subprocess.run(tuff_cmd() + ["--check", bad], capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = p.stdout + p.stderr
        if want is None:
            c.check(True, f"--check runs on: {code.splitlines()[-1]}")
        else:
            c.check(want in out, f"--check on {code.splitlines()[-1]!r} says {want!r}", out[:300])


# The 1.4.0 review's fixes: 1.3.6 programs that must still work, and the toolbox's edges.
TOOLBOX_FIXES = '''names = ["Ann", "Bob", "Cat"]
order = [2, 0, 1]
say names[order:pop]
stack = [0]
say names[stack:pop + 1]
word = "hi"
pairs = []
pairs:add [word:upper, 1]
say pairs
catch = []
catch:add("trout")
say catch
try = [3]
try:add(4)
say try
func wave(n):
    sin = n * 2
    return sin
say wave(2)
say sin(90)
s = "hello world"
n = 4
say s[:n]
say s[0:len(s) - 7]
i = 1
say s[i + 1:i + 3]
say s[:s:find(" ") - 1]
func make():
    return {"a": 1}
d = make()
say d:size()
loop = [1]
loop:add(loop)
say loop
say log(1000, 10)
say log(8, 2)
say text(-0.001, 2)
r = random(0.5)
say r >= 0 and r <= 0.5
w = random(1, 12 / 2)
say w is floor(w)
try:
    say tan(90)
catch problem:
    say problem
yes = 1 is 1
k = {}
try:
    k[yes] = 1
catch problem:
    say problem
file.save("tbf.json", {1: "one"})
back = file.load("tbf.json")
try:
    say back[1]
catch problem:
    say problem
say back["1"]
file.delete("tbf.json")
board = ["", "", ""]
moves = [0, 2]
board[moves:pop] = "X"
say board
counts = {}
word = "Hi"
counts[word:lower] = 1
counts[word:lower] += 1
say counts
email = "sam@mail.com"
say email[email:find("@") + 1:len(email) - 1]
line = "Sam Smith"
n = len(line) - 1
say line[line:find(" "):n]
items = [5, 6, 7, 8]
say items[items:find(6):items:find(8)]
stack = [1, 2]
say items[1 + stack:pop]
name = "Bob"
cache = {"user_bob": 7}
say cache["user_" + name:lower]
say {names[0]:items[0]}
calls = 0
func pick():
    calls += 1
    return "user_bob"
cache[pick()] += 1
say cache["user_bob"] + calls * 100
func grab(catch):
    catch:add(1)
    return catch
say grab([])
func nothing():
    return nil
try:
    say email[0:nothing()]
catch problem:
    say problem
say len(text(2 ^ 20000)) > 4300
'''
TOOLBOX_FIXES_OUTPUT = ["Bob", "Bob", '[["HI", 1]]', '["trout"]', "[3, 4]", "4", "1", "hello", "hello", "llo", "hello", "1",
                        "[1, [...]]", "3", "3", "0.00", "true", "true",
                        "tan(90) has no answer: at 90 degrees (and 270) the line is straight up.",
                        "A dictionary's keys can be text or numbers, not true/false.",
                        'back doesn\'t have the number 1, but it has "1" (text). Keys that come back from file.load are always text: use back["1"] or back[text(1)].',
                        "one", '["", "", "X"]', '{"hi": 2}', "mail.com", " Smith", "[6, 7, 8]", "8", "7", '{"Ann": 5}', "108", "[1]",
                        "The positions in [start:end] must be whole numbers, not nil.", "true"]
TOOLBOX_FIXES_CHECKS = [
    ('d = {"a": 1}\nsay d:get()', "d:get takes 1 or 2 inputs, not 0."),
    ('s = "abc"\nsay s:replace("a")', "s:replace takes 2 inputs, not 1."),
    ('s = "abc"\nsay s[0:"b"]', "The positions in [start:end] must be whole numbers, not text."),
    ('d = {[1]: 2}', "A dictionary's keys can be text or numbers, not a list."),
    ('x = {"a": nope}', "I don't know what 'nope' is."),
    ('s = "abc"\nsay s[0:nope]', "I don't know what 'nope' is."),
    ('try:\n    x = 1\ncatch err:\n    say err', "err is Tuff's own value"),
    ('time.sleep(1)', "Tuff has no time.sleep."),
    ('d = {"a": 1}\nsay d.a', 'Read a value with [ ], like d["a"]'),
    ('func f():\n    file = "x"\n    return file\nsay file.read("a.txt")', "OK"),
    ('names = ["a"]\norder = [0]\nsay names[order:pop]', "OK"),
    ('func f():\n    date = 5\n    return date\nsay date()', "OK"),  # at the top, date is the built-in
    ('t = {"a": 1}\nfunc show():\n    return {"b": 2}\nt:set "c", 3', None),
    ('s = "hello"\nfirst = "2"\nsay s[first:n]', "The positions in [start:end] must be whole numbers, not text."),
    ('board = ["", ""]\nmoves = [1]\nboard[moves:pop] = "X"\nsay board', "OK"),
    ('func f(log):\n    return log(1)\nlog = 5\nsay f(sqrt)', "OK"),
    ('func f():\n    cos = 3\n    return cos\nvalues = [30, 60]\nsay [cos(30), f()]', "OK"),
    ('mention file\nsay file.exists("x.txt")', "OK"),
    ('try:\n    x = 1\nexcept:\n    x = 2', "Write the catch line as catch: or catch problem:"),
]


def t_toolbox_fixes(c):
    """The 1.4.0 review's fixes: a:b inside [ ] is still 1.3.6's method call when what's before it isn't a number,
    try and catch still work as variables, sin/cos/tan stay a function's own, keys are text or numbers, and
    TUFF_NO_WRITES / TUFF_BASE_DIR (tuff_run for AI agents) keep writes in memory and find the project's files."""
    folder = os.path.join(HERE, "out", "toolbox_fixes")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "fixes.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TOOLBOX_FIXES)
    p = subprocess.run(tuff_cmd() + [path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    got = p.stdout.splitlines()
    c.check(p.returncode == 0, "the fixes program runs to the end", (p.stdout + p.stderr)[-600:])
    for i, want in enumerate(TOOLBOX_FIXES_OUTPUT):
        c.check(i < len(got) and got[i] == want, f"fixes line {i + 1}: {want}", got[i] if i < len(got) else "(missing)")
    p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.stdout.strip() == "OK", "--check accepts the fixes program", (p.stdout + p.stderr)[:600])
    for i, (code, want) in enumerate(TOOLBOX_FIXES_CHECKS):
        bad = os.path.join(folder, f"check{i}.tuf")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        p = subprocess.run(tuff_cmd() + ["--check", bad], capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = p.stdout + p.stderr
        if want is None:
            c.check("Traceback" not in out, f"--check runs on: {code.splitlines()[-1]}", out[:300])
        else:
            c.check(want in out, f"--check on {code.splitlines()[-1]!r} says {want!r}", out[:300])
    # TUFF_NO_WRITES=1: writes stay in memory for the run; TUFF_BASE_DIR: a snippet reads the project's files
    project = os.path.join(folder, "project")
    os.makedirs(project, exist_ok=True)
    with open(os.path.join(project, "data.txt"), "w", encoding="utf-8") as f:
        f.write("from the project\n")
    for name in ("made.txt", "data.json"):
        if os.path.exists(os.path.join(project, name)):
            os.remove(os.path.join(project, name))
    snippet = os.path.join(folder, "snippet.tuf")
    with open(snippet, "w", encoding="utf-8") as f:
        f.write('say file.read("data.txt"):trim()\nfile.write("made.txt", "hi")\nfile.add("made.txt", "there")\n'
                'say file.lines("made.txt")\nfile.save("data.json", {"n": 1})\nsay file.load("data.json")["n"]\n'
                'file.delete("data.txt")\nsay file.exists("data.txt")\n')
    env = {**os.environ, "TUFF_NO_WRITES": "1", "TUFF_BASE_DIR": project}
    p = subprocess.run(tuff_cmd() + [snippet], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    c.check(p.stdout.splitlines() == ["from the project", '["hi", "there"]', "1", "false"],
            "with TUFF_NO_WRITES and TUFF_BASE_DIR a snippet reads the project's file and its own writes", p.stdout + p.stderr)
    c.check(os.path.exists(os.path.join(project, "data.txt")) and not os.path.exists(os.path.join(project, "made.txt"))
            and not os.path.exists(os.path.join(project, "data.json")), "...and nothing on disk changed")


TESTS = {"snake": t_snake, "breakout": t_breakout, "snake3d": t_snake3d, "axe": t_axe, "features_2d": t_features_2d,
         "toolbox": t_toolbox, "toolbox_fixes": t_toolbox_fixes,
         "features_3d": t_features_3d, "player_3d": t_player_3d, "callback": t_callback, "errors": t_errors,
         "models": t_models, "people": t_people,
         "churn": t_churn, "pause_key": t_pause_key, "close": t_close, "hud_3d": t_hud_3d, "terrain": t_terrain,
         "terrain_look": t_terrain_look, "no_webgl": t_no_webgl, "ui_2d": t_ui_2d, "ui_3d": t_ui_3d,
         "menu_2d": t_menu_2d, "menu_3d": t_menu_3d, "menu_start": t_menu_start, "mouse_hold": t_mouse_hold,
         "mouse_busy": t_mouse_busy, "mouse_focus": t_mouse_focus, "mouse_panel": t_mouse_panel,
         "physics": t_physics, "physics_player": t_physics_player, "physics_car": t_physics_car, "physics_2d": t_physics_2d,
         "physics_off": t_physics_off,
         "saves": t_saves,
         "fx_slow_mo": t_fx_slow_mo, "fx_shake_pop": t_fx_shake_pop, "fx_weather": t_fx_weather, "fx_day": t_fx_day, "fx_2d": t_fx_2d,
         "ix_grab": t_ix_grab, "ix_talk": t_ix_talk, "ix_door": t_ix_door,
         "physics_off": t_physics_off, "level_pads": t_level_pads, "level_lift": t_level_lift,
         "scene": t_scene, "notice": t_notice, "mcp": t_mcp, "checker": t_checker, "editor": t_editor, "guide": t_guide, "perf": t_perf}
TESTS.update({"hud_health_3d": t_hud_health_3d, "hud_health_2d": t_hud_health_2d, "hud_arrow": t_hud_arrow,
              "hud_minimap": t_hud_minimap, "hud_checker": t_hud_checker})
TESTS.update({"net": t_net, "net_2d": t_net_2d, "net_rooms": t_net_rooms})
TESTS.update({"car_enter": t_car_enter, "weight": t_weight, "sign_text": t_sign_text, "people_style": t_people_style})


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--") and a not in (arg("--out-dir"), arg("--runtime"))]
    unknown = [n for n in names if n not in TESTS]
    if unknown:
        print(f"No test called {', '.join(unknown)}. Tests: {', '.join(TESTS)}")
        return 2
    total = Checks()
    rows = []
    for name in names or TESTS:
        print(f"== {name}", flush=True)
        c = Checks()
        t0 = time.perf_counter()
        try:
            TESTS[name](c)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            c.check(False, f"{name} crashed: {exc}")
        rows.append((name, c.passed, c.failed, time.perf_counter() - t0))
        total.passed += c.passed
        total.failed += c.failed
    print("\n== summary", flush=True)
    for name, p, f, secs in rows:
        print(f"  {name:12} {p:3} passed {f:3} failed  {secs:5.1f} s", flush=True)
    print(f"  total: {total.passed} passed, {total.failed} failed (screenshots and results in {OUT})", flush=True)
    return 0 if total.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
