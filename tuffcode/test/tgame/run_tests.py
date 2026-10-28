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
        {"at": 3.9, "tuff": "report_next = true"}, {"at": 3.95, "shot": "car_enter_driving.png"},
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
    # The report while it drives comes from the game's every-frame function (report_next), after tgame has put the
    # player where the car is, so both spots are from one frame. Asked with "call", earlier in a frame, the player was
    # where the car was a frame before: 0.13 m or more at driving speed, more after a slow frame, and now and then
    # over the 0.2 m allowed.
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
    it); after the game restarts game:load gives them back (lists as lists, tables as dictionaries), with defaults for
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
la = [1, 2]
lb = []
say names[(la + lb):pop]
say la
stacks = []
say items[len(stacks) > 0 and stacks[0]:pop or 0]
func refill():
    say "refilling"
    return [2]
k = 1
say items[k or refill():pop]
say email[email:find("@"):len(email) - 1]
say {"name":line[0:2]}
order = nil
try:
    say names[order:pop]
catch problem:
    say problem
'''
TOOLBOX_FIXES_OUTPUT = ["Bob", "Bob", '[["HI", 1]]', '["trout"]', "[3, 4]", "4", "1", "hello", "hello", "llo", "hello", "1",
                        "[1, [...]]", "3", "3", "0.00", "true", "true",
                        "tan(90) has no answer: at 90 degrees (and 270) the line is straight up.",
                        "A dictionary's keys can be text or numbers, not true/false.",
                        'back doesn\'t have the number 1, but it has "1" (text). Keys that come back from file.load or a web page\'s JSON are always text: use back["1"] or back[text(1)].',
                        "one", '["", "", "X"]', '{"hi": 2}', "mail.com", " Smith", "[6, 7, 8]", "8", "7", '{"Ann": 5}', "108", "[1]",
                        "The positions in [start:end] must be whole numbers, not nil.", "true",
                        "Cat", "[1, 2]", "5", "6", "@mail.com", '{"name": "Sam"}', "order is nil, so it's not a position, and it has no :pop."]
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
    # 1.4.1: board[moves:pop] = "X" is checked like the read form
    ('board = ["", ""]\nboard[nope:pop] = "X"', "I don't know what 'nope' is."),
    ('word = "ab"\nmoves = [1]\nword[moves:pop] = "X"', "You can only set items in a list, not in text."),
    ('board = ["", ""]\ni = 0\nj = 1\nboard[i:j] = "X"', "A part like [1:3] can't be changed with =."),
    # ... when it can't be told yet whether it's a part or 1.3.6's method call: what's wrong either way
    ('func f(order):\n    names = ["a"]\n    say names[order:pop + nope]\nf([0])', "I don't know what 'nope' is."),
    ('func f(order):\n    names = ["a", "b"]\n    say names[order:pop + 1]\nf([0])', "OK"),
    # ... 1.3.6's reading gets [ ]'s own checks, and a bare input there is named after its list again
    ('names = ["a", "b"]\nwords = ["x", "y"]\nsay names[words:join]', "List positions must be whole numbers, not text."),
    ('names = ["a", "b"]\nq = [1]\nsay names[q:pop -1]', "q:pop doesn't take an input, so what comes after it was read as one. Write q:pop() instead."),
    ('names = ["a", "b"]\nq = [1]\nnames[q:pop -1] = "c"', "q:pop doesn't take an input, so what comes after it was read as one. Write q:pop() instead."),
    # a for loop at the top named after a built-in replaces it
    ('for file in ["a.txt", "b.txt"]:\n    say file\nsay file.read("c.txt")', "replaces it everywhere, so file.read on line 3 won't work"),
    ('for file in file.lines("list.txt"):\n    say file.read(file)', "so file.read on line 2 won't work"),
    ('for time in [1, 2]:\n    say time\nsay time()', "so time() on line 3 won't work"),
    ('for log in range(3):\n    say log\nsay log(100)', "so log() on line 3 won't work"),
    ('for date in ["a"]:\n    say date()', "so date() on line 2 won't work"),
    ('for date in []:\n    say date()\nsay date()', "OK"),
    ('for log in [print]:\n    log("x")', "OK"),
    # dictionary keys outside { }: d[key] = v, d[key], :get, :set, :has and :remove
    ('d = {"a": 1}\nd[true] = 2', "A dictionary's keys can be text or numbers, not true/false."),
    ('d = {"a": 1}\nsay d[nil]', "A dictionary's keys can be text or numbers, not nil."),
    ('d = {"a": 1}\nsay d:get(nil)', "A dictionary's keys can be text or numbers, not nil."),
    ('d = {"a": 1}\nd:set([1], 2)', "A dictionary's keys can be text or numbers, not a list."),
    ('d = {"a": 1}\nsay d:has(1 is 1)', "A dictionary's keys can be text or numbers, not true/false."),
    ('d = {"a": 1}\nd:remove(false)', "A dictionary's keys can be text or numbers, not true/false."),
    ('d = {0.5: "half"}\nsay d[1 / 2]', "OK"),
    ('d = {}\ntry:\n    d[true] = 1\ncatch problem:\n    say problem', "OK"),
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
    c.check(p.stdout.splitlines()[:4] == ["from the project", '["hi", "there"]', "1", "false"],  # (a built runtime adds "Press Enter")
            "with TUFF_NO_WRITES and TUFF_BASE_DIR a snippet reads the project's file and its own writes", p.stdout + p.stderr)
    c.check(os.path.exists(os.path.join(project, "data.txt")) and not os.path.exists(os.path.join(project, "made.txt"))
            and not os.path.exists(os.path.join(project, "data.json")), "...and nothing on disk changed")


LOOKS_PROGRAM = '''mention anims
name = input:color("Name? ", "green")
say "Hi " + name
anims.loading("Pulling info...", 0.2, "sky")
anims.countdown(1, "Go!", "lime", "bold")
print:pen("cyan")
again = input "Again? "
anims.loading("With the pen", 0.1)
'''
LOOKS_CHECKS = [
    ('x = input:color("Hi? ", "gren")', 'input:color doesn\'t know "gren". Did you mean "green"?'),
    ('x = input:color("Hi? ", "explode")', 'input:color sets colours and styles. Animations like "explode" go on say:ascii or say:color.'),
    ('x = input:ascii("Hi")', "input has one method, :color"),
    ('x = input:color "Hi"', "Put input:color's question and look in brackets"),
    ('mention anims\nanims.loading("Hi", "gren")', 'anims.loading doesn\'t know "gren". Did you mean "green"?'),
    ('mention anims\nanims.loading("Hi", "fade")', 'anims.loading sets colours and styles.'),
    ('mention anims\nanims.countdown(3, "Go!", "lime")\nx = input:color("Name? ", "green", "bold")', "OK"),
]


def t_looks(c):
    """1.4.1: input:color's question and anims' lines take looks (colours, rainbow, styles), and print:pen colours
    them too. What TuffCode's Run panel is sent (TUFF_IDE=1), read without opening anything."""
    import base64
    import re
    folder = os.path.join(HERE, "out", "looks")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "looks.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(LOOKS_PROGRAM)
    p = subprocess.run(tuff_cmd() + [path], input="Sam\nyes\n", capture_output=True, text=True, encoding="utf-8", timeout=60,
                       env={**os.environ, "TUFF_IDE": "1"})
    c.check(p.returncode == 0, "the looks program runs to the end", (p.stdout + p.stderr)[-500:])
    sent = []
    for kind, args in re.findall(r"\x1b\]tuff;(\w+);([^\x07]*)\x07", p.stdout):
        parts = args.split(";")
        text = base64.b64decode(parts[0 if kind == "prompt" else 1]).decode("utf-8")
        style = parts[1 if kind == "prompt" else 2] if len(parts) > (1 if kind == "prompt" else 2) else ""
        sent.append((kind, text, json.loads(base64.b64decode(style[5:])) if style.startswith("rich:") else {}))
    prompts = [s for s in sent if s[0] == "prompt"]
    c.check(prompts and prompts[0][1] == "Name? " and prompts[0][2].get("fg") == "#22a35a",
            'input:color("Name? ", "green") sends its question in green, on the answer\'s line', prompts[:1])
    loading = [s for s in sent if s[0] == "say" and "Pulling info" in s[1]]
    c.check(loading and loading[0][2].get("fg") == "#87ceeb", 'anims.loading("Pulling info...", 0.2, "sky") is sky blue', loading[:1])
    count = [s for s in sent if s[0] == "say" and s[1] == "1"]
    c.check(count and count[0][2].get("fg") == "#84cc16" and count[0][2].get("bold") == 1, "anims.countdown takes lime and bold after its inputs", count[:1])
    c.check(len(prompts) > 1 and prompts[1][1] == "Again? " and prompts[1][2].get("fg") == "#22d3ee",
            "with print:pen on, a plain input's question has the pen's look", prompts[1:2])
    pen = [s for s in sent if s[0] == "say" and "With the pen" in s[1]]
    c.check(pen and pen[0][2].get("fg") == "#22d3ee", "with print:pen on, anims' lines have the pen's look", pen[:1])
    plain_run = subprocess.run(tuff_cmd() + [path], input="Sam\nyes\n", capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(plain_run.stdout.startswith("Name? Hi Sam"), "in a pipe the question is plain text", plain_run.stdout[:80])
    for i, (code, want) in enumerate(LOOKS_CHECKS):
        bad = os.path.join(folder, f"check{i}.tuf")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        out = subprocess.run(tuff_cmd() + ["--check", bad], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(want in out.stdout + out.stderr, f"--check on {code.splitlines()[-1]!r} says {want!r}", (out.stdout + out.stderr)[:300])


# 1.4.1: a Tuff function can call itself thousands of times. A Tuff call is 7 to 14 of Python's, whose limit is 1000,
# so one used to stop after about 100 calls of itself ("called itself too many times"). tuff.py runs a program on a
# thread with a big stack and a higher limit now (run_deep).
DEEP_PROGRAM = '''func depth(n):
    if n == 0:
        return 0
    return 1 + depth(n - 1)
say depth(5000)
say depth(10000)
func walk(n, seen):
    for i in [n]:
        if i > 0:
            seen:add(i)
            walk(i - 1, seen)
    return seen
say len(walk(6000, []))
func is_even(n):
    if n == 0:
        return true
    return is_odd(n - 1)
func is_odd(n):
    if n == 0:
        return false
    return is_even(n - 1)
say is_even(7000)
name = input "Name? "
say "Hi " + name:trim()
'''
DEEP_RUNAWAY = '''func forever(n):
    return forever(n + 1)
try:
    forever(1)
catch problem:
    say "caught: " + problem
say "still going"
forever(1)
say "never shown"
'''
DEEP_SCENE = '''mention tgame
func depth(n):
    if n == 0:
        return 0
    return 1 + depth(n - 1)
game = tgame.window("Deep", 300, 200)
label = game:text("deep " + depth(5000), 150, 100)
'''
# Ctrl+C, as Python's signal handler gives it to the main thread (_thread.interrupt_main), 1.5 s into the run.
CTRL_C = ("import sys, threading, _thread\nsys.path.insert(0, sys.argv[1])\nimport tuff\n"
          "threading.Timer(1.5, _thread.interrupt_main).start()\nsys.exit(tuff.run_program(sys.argv[2]))\n")


def t_recursion(c):
    """Console only, no window: a function calls itself 5000 and 10000 times (in a loop and through two functions
    too) and input still works; one that never stops gives the same friendly message as before, which try/catch
    catches; --check, the --scene preview, and Ctrl+C (130, also in the middle of a wait or an input)."""
    folder = os.path.join(HERE, "out", "recursion")
    os.makedirs(folder, exist_ok=True)

    def write(name, code):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return path

    deep, runaway = write("deep.tuf", DEEP_PROGRAM), write("runaway.tuf", DEEP_RUNAWAY)
    t0 = time.perf_counter()
    p = subprocess.run(tuff_cmd() + [deep], input="Sam\n", capture_output=True, text=True, encoding="utf-8", timeout=120)
    got = [line for line in p.stdout.splitlines() if line.strip() and line.strip() != "Press Enter to close..."]
    c.check(p.returncode == 0 and "Tuff error" not in p.stderr, f"the deep program runs to the end ({time.perf_counter() - t0:.1f} s)",
            (p.stdout + p.stderr)[-600:])
    c.check(got[:4] == ["5000", "10000", "6000", "true"], "depth(5000), depth(10000), 6000 deep in a loop, 7000 through two functions", got[:4])
    c.check(got[-1:] == ["Name? Hi Sam"], "input works on the program's thread", got[-1:])
    t0 = time.perf_counter()
    p = subprocess.run(tuff_cmd() + [runaway], capture_output=True, text=True, encoding="utf-8", timeout=120, stdin=subprocess.DEVNULL)
    secs = time.perf_counter() - t0
    c.check(p.stdout.splitlines()[:2] == ["caught: forever() called itself too many times.", "still going"],
            "try/catch catches a function that never stops", p.stdout[:300])
    c.check(p.returncode == 1 and "Tuff error on line 2: forever() called itself too many times." in p.stderr
            and "Traceback" not in p.stderr and "never shown" not in p.stdout,
            "without try it stops the program with the friendly message on its line (exit code 1)", (p.returncode, p.stderr[-600:]))
    c.check(secs < 20, f"...twice, in {secs:.1f} s")
    for path in (deep, runaway):
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.stdout.strip() == "OK", f"--check accepts {os.path.basename(path)}", (p.stdout + p.stderr)[:400])
    code, out, err, d, secs = scene(write("deep_scene.tuf", DEEP_SCENE))
    c.check(code == 0 and d.get("error") is None and d.get("stopped") == "end" and "deep 5000" in json.dumps(d.get("batch")),
            f"the --scene preview runs a setup that calls a function 5000 deep ({secs:.1f} s)", (d.get("error"), d.get("stopped"), err[-300:]))
    d = scene(write("runaway_scene.tuf", 'mention tgame\ngame = tgame.window("R")\nfunc forever(n):\n    return forever(n + 1)\nforever(1)\n'))[3]
    e = d.get("error") or {}
    c.check(e.get("line") == 4 and e.get("message") == "forever() called itself too many times.",
            "...and says a function that never stops called itself too many times, on its line", e)
    if RUNTIME:
        c.check(True, "a built runtime can't be given a pretend Ctrl+C: skipped those")
        return
    for name, code_text in (("busy.tuf", 'n = 0\nwhile true:\n    n += 1\n    if n % 100000 == 0:\n        say n\n'),
                            ("nap.tuf", 'say "napping"\nwait(30)\nsay "awake"\n')):
        t0 = time.perf_counter()
        p = subprocess.run([sys.executable, "-c", CTRL_C, REPO, write(name, code_text)], capture_output=True, text=True,
                           encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
        secs = time.perf_counter() - t0
        c.check(p.returncode == 130 and secs < 10 and "awake" not in p.stdout and "Traceback" not in p.stderr and "Fatal" not in p.stderr,
                f"Ctrl+C stops {name} with exit code 130 ({secs:.1f} s)", (p.returncode, p.stderr[-400:]))
    # Waiting for input that never comes (its stdin stays open): the program's thread can't be stopped, so the process ends.
    ask = write("ask.tuf", 'say "asking"\nname = input "Name? "\nsay "never " + name\n')
    with open(os.path.join(folder, "ask.out"), "w+", encoding="utf-8") as out, open(os.path.join(folder, "ask.err"), "w+", encoding="utf-8") as err:
        t0 = time.perf_counter()
        proc = subprocess.Popen([sys.executable, "-c", CTRL_C, REPO, ask], stdin=subprocess.PIPE, stdout=out, stderr=err)
        try:
            code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = "timeout"
        secs = time.perf_counter() - t0
        proc.stdin.close()
        out.seek(0)
        err.seek(0)
        said, problems = out.read(), err.read()
    c.check(code == 130 and "asking" in said and "never" not in said and "Fatal" not in problems and "Traceback" not in problems,
            f"Ctrl+C stops a program waiting for input with exit code 130 ({secs:.1f} s)", (code, said[-200:], problems[-400:]))


DEEP_GAME = '''mention tgame
func depth(n):
    if n == 0:
        return 0
    return 1 + depth(n - 1)
game = tgame.window("Deep", 300, 200)
say "setup " + depth(5000)
func later():
    say "later " + depth(5000)
    game:close()
game:after(0.5, later)
'''


DEEP_DRAW = '''mention tdraw
func depth(n):
    if n == 0:
        return 0
    return 1 + depth(n - 1)
pen = tdraw.pen()
pen:speed "instant"
func tree(size, level):
    if level > 0:
        pen:forward(size)
        pen:left(30)
        tree(size * 0.7, level - 1)
        pen:right(60)
        tree(size * 0.7, level - 1)
        pen:left(30)
        pen:back(size)
tree(80, 6)
say "deep " + depth(3000)
'''


def t_recursion_window(c):
    """Opens windows. A game (its program runs on tuff_view's thread): the setup and a game:after function both call a
    function 5000 deep. A tdraw drawing (tkinter keeps the main thread): a recursive tree, and 3000 deep there too
    (on Python 3.12 and newer, where the main thread can go that deep)."""
    folder = os.path.join(HERE, "out", "recursion")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "deep_game.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(DEEP_GAME)
    r = play("recursion_window", path, [{"at": 4, "close": True}])
    c.check(r.code == 0 and "Tuff error" not in r.err, f"the deep game runs and closes ({r.seconds:.1f} s)", (r.code, r.err[-400:]))
    c.check("setup 5000" in r.lines and "later 5000" in r.lines, "its setup and its game:after function both went 5000 deep", r.lines)
    path = os.path.join(folder, "deep_draw.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(DEEP_DRAW)
    env = {**os.environ, "TUFF_TDRAW_CLOSE_AFTER": "0.5", "PYTHONIOENCODING": "utf-8"}
    env.pop("TUFF_IDE", None)
    p = subprocess.run(tuff_cmd() + [path], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       env=env, stdin=subprocess.DEVNULL)
    c.check(p.returncode == 0 and "Tuff error" not in p.stderr and "Traceback" not in p.stderr,
            "the tdraw drawing draws its recursive tree and closes", (p.returncode, (p.stdout + p.stderr)[-400:]))
    if RUNTIME or sys.version_info >= (3, 12):
        c.check("deep 3000" in p.stdout, "...and its function went 3000 deep on the main thread", p.stdout[-300:])


# Pictures in the folder above the program ("../") stay refused for tgame and atgui: their window serves only the .tuf's
# folder and the folders inside it, and a built app takes only those (build.js). --check says so in the run's words.
UP_TGAME = 'mention tgame\ngame = tgame.window("x")\npic = "../art/star.png"\nstar = game:image(pic, 1, 2)\n'
UP_ATGUI = 'mention atgui\napp = atgui.window("x")\npic = "../art/star.png"\nlogo = app:image(pic, 100)\n'
UP_TGAME_SAYS = "The picture '../art/star.png' has to be next to your .tuf file, or in a folder inside it."
UP_ATGUI_SAYS = ("'../art/star.png' is outside the folder your .tuf file is in, so atgui can't show it. "
                 "Put the picture next to your .tuf file, or in a folder inside it.")
UP_CHECKS = [  # (code, what --check says, or "OK")
    (UP_TGAME, UP_TGAME_SAYS),
    ('mention tgame\ngame = tgame.window("x")\ntune = "../art/blip.wav"\ngame:sound tune\n', "The sound '../art/blip.wav' has to be next to"),
    (UP_ATGUI, UP_ATGUI_SAYS),
    ('mention atgui\napp = atgui.window("x")\nme = app:avatar("../art/star.png")\n', UP_ATGUI_SAYS),
    ('mention atgui\napp = atgui.window("x")\nme = app:avatar("Sam Smith")\nme:set "../art/star.png"\n', UP_ATGUI_SAYS),
    ('mention atgui\napp = atgui.window("x")\nme = app:avatar("Sam Smith", "blue")\nme:set "SS"\n', "OK"),
    ('mention atgui\napp = atgui.window("x")\nme = app:avatar("star.png")\n', "OK"),
    ('mention tgame\ngame = tgame.window("x")\nstar = game:image("..art/star.png", 1, 2)\n', "OK"),  # a folder inside called "..art"
    ('mention atgui\napp = atgui.window("x")\npic = "..art/star.png"\nlogo = app:image(pic, 100)\n', "OK"),
    ('mention atgui\napp = atgui.window("x")\npic = "../art/star.png"\npic = "star.png"\nlogo = app:image(pic, 100)\n', "OK"),  # set twice: unknown
    ('mention tgame\ngame = tgame.window("x")\nfunc show(pic):\n    return game:image(pic, 1, 2)\nshow("star.png")\n', "OK"),
]


def t_pictures_up(c):
    """Console only, no window: a picture in the folder above (../) is refused when the program runs (tgame through
    --scene, atgui's image_url) and by --check in the same words, also when a variable set once holds the path and for
    an atgui avatar; a folder inside whose name starts with two dots is fine both ways."""
    root = os.path.join(HERE, "out", "pictures_up")  # never in the temp folder: there the checker leaves file names alone
    folder = os.path.join(root, "game")
    for sub in ("art", os.path.join("game", "..art")):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    for where in (os.path.join(root, "art"), os.path.join(folder, "..art"), folder):
        with open(os.path.join(GAMES, "star.png"), "rb") as f, open(os.path.join(where, "star.png"), "wb") as g:
            g.write(f.read())
    for i, (code, want) in enumerate(UP_CHECKS):
        path = os.path.join(folder, f"up{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = (p.stdout + p.stderr).strip()
        lines = " / ".join(code.strip().splitlines()[2:])  # after the mention and the window
        if want == "OK":
            c.check(out == "OK", f"--check accepts: {lines}", out[:400])
        else:
            c.check(p.returncode == 1 and want in out, f"--check on {lines!r} says {want[:40]!r}...", out[:400])
    # The run: tgame through Tuff Engine's preview (its Recorder refuses the same files as the window)...
    d = scene(os.path.join(folder, "up0.tuf"))[3]
    e = d.get("error") or {}
    c.check(e.get("line") == 4 and e.get("message") == UP_TGAME_SAYS, "running it, tgame says the same on the same line", e)
    d = scene(os.path.join(folder, "up7.tuf"))[3]
    c.check(d.get("error") is None and d.get("stopped") == "end", 'running it, tgame shows "..art/star.png"', d.get("error"))
    # ...and atgui's image_url, which every atgui picture goes through (no window needed).
    import tuff
    import tuff_atgui
    lib = tuff_atgui.Lib(tuff.Interpreter("", folder).rt)
    up_full = os.path.join(root, "art", "star.png")
    for path, want, label in (("../art/star.png", UP_ATGUI_SAYS, "../art/star.png"),
                              (up_full, UP_ATGUI_SAYS.replace("../art/star.png", up_full), "the full path of ../art/star.png"),
                              ("..art/star.png", "assets/..art/star.png", "..art/star.png"), ("star.png", "assets/star.png", "star.png")):
        try:
            got = lib.image_url(path)
        except tuff.TuffError as err:
            got = err.msg
        c.check(got == want, f"running it, atgui's image_url gives {want[:44]!r}... for {label}", got)


# ---------------------------------------------------------------- the compiled interpreter (1.5.0)

# Runs one program for the differential test: random numbers start the same, now(), today(), date() and time() give
# fixed answers, and wait() and animations take no time, so a program gives the same output every time. The rest is
# tuff.py's own main(): TUFF_SLOW=1 (in the environment) runs the old tree walker, and without it the compiled runtime.
INTERP_DRIVER = r'''import os, random, sys, time
sys.path.insert(0, sys.argv[1])
import tuff
random.seed(5)
time.sleep = lambda seconds: None
init = tuff.Interpreter.__init__
def fixed(self, *args, **kwargs):
    init(self, *args, **kwargs)
    when = {"now": lambda: "10:30:00", "today": lambda: "2026-10-26", "time": lambda: 1.25,
            "date": lambda: {"year": 2026, "month": 10, "day": 26, "weekday": "Monday", "hour": 10, "minute": 30, "second": 0}}
    for name, fn in when.items():
        (self.own_names if name in tuff.OWN_NAME_BUILTINS else self.globals).vars[name].fn = fn
def no_wait(self, seconds):
    sys.stdout.flush()
    max(0, float(seconds))
    for hook in self.rt.wait_hooks:
        hook()
tuff.Interpreter.__init__ = fixed
tuff.Interpreter.b_wait = no_wait
sys.argv = ["tuff.py"] + sys.argv[2:]
sys.exit(tuff.main())
'''
INTERP_ANSWERS = "Sam\n7\nyes\n3\nno\n12\n5\nquit\n"
WINDOW_LIBRARY = re.compile(r"^[ \t]*(?:import|mention)[ \t]+(?:tgui|mtgui|atgui|tgame|tdraw|tap)\b", re.M)  # tap: the internet
# Small programs for the corners: where an error is reported (line and column), try/catch, return, break and continue
# in and out of loops and functions, what a function gives back, live lines, own-name built-ins, the two readings of
# x[a:b], dictionaries, numbers and text. Most stop at an error at the end, so each one checks one more message.
INTERP_CASES = [
    'say nope', 'x = 1\nsay x + nope', 'func f(a):\n    return a + missing\nsay f(1)', 'func f(a):\n    return a * 2\nsay f(1, 2)',
    'say len(1, 2)', 'say len(5)', 'items = [1, 2]\nsay items[5]', 'items = [1, 2]\nitems[2] = 3', 's = "hi"\ns[0] = "H"',
    'd = {"a": 1}\nsay d["b"]', 'd = {"1": "one"}\nsay d[1]', 'say 1 / 0', 'x = 5 % 0', 'say (-8) ^ (1 / 3)', 'say 2 ^ 0.5',
    'say "a" - 1', 'say true + 1', 'say [1] < [2]', 'x = 5\nx += "a"\nsay x\nx -= 1', 'for i in 5:\n    say i',
    'for i in nil:\n    say i', 'x = 5\nx()', 'len = 3\nsay len("abc")', 'say num("x") + 1', 'n = int("abc")\nsay n * 2',
    'say -"a"', 'say -[1]', 'say {[1]: 2}', 'k = {}\nk[true] = 1', 'x = nil\nsay "abc"[1:x]', 'say "abc"["a":2]',
    'n = 5\nsay n[1:2]', 'x = 5\nsay x.y', 'say anims.loading', 'import nothing', 'mention anims\nsay anims.nope',
    'items = [1]\nitems:append(2)', 'say "abc":nope()', 'x = 5\nsay x:upper()', 'say [[1], 2]:sort()',
    'func by(x):\n    return [x]\nitems = [2, 1]\nitems:sort(by)', 'func by(a, b):\n    return a\nitems = [2, 1]\nitems:sort(by)',
    'say [1, 2]:pop(0)', 'say []:pop()', 'x = [1]\nx:remove(5)', 'd = {}\nd:remove("a")', 'clear(-1)', 'say random(5, 1)',
    'say sqrt(-1)', 'say tan(90)', 'say log(0)', 'say round("a")', 'say min()', 'say text(1, 200)', 'say range(1, 10, 0)',
    'break', 'continue', 'return 5', 'say "before"\nfunc f():\n    break\nf()',
    'func f():\n    continue\nfor i in range(1, 3):\n    say i\n    f()\n    say "never"',
    'func forever(n):\n    return forever(n + 1)\nforever(1)', 'func a(n):\n    return b(n + 1)\nfunc b(n):\n    return a(n + 1)\nsay a(1)',
    'x = 1\nif x:\n    y = 2\nsay y + z', 'say "a" * "b"', 'say "ab" * 3 + 3 * "c"', 'say "x" * 600000000',
    'items = [1, 2, 3]\nsay items[1.5]', 'items = [1, 2, 3]\nsay items["a"]', 'say err + 1', 'x = err\nsay x:upper()',
    'say input:color("Name? ", "gren")', 'say:color("hi", "nocolor")', 'print:pen("bogus")', 'l = say "hi"\nl:play("nothing")',
    'l = say "hi"\nl:rewrite()', 'say 1 < "a"', 'x = [1, 2]\nx += 3', 'x = 4\nx /= 0', 'items = [1]\nitems[0] /= 0',
    'd = {"a": 1}\nd["b"] += 1', 'd = {"a": 1}\nd[[1]] = 2', 'x = nil\nsay x + 1', 'say [1, 2] + [3]\nsay [1] + 2',
    'say 1 < 2 < 3', 'func f():\n    for x in 5:\n        say x\nf()', 'x = 0\nwhile x < nope:\n    x += 1',
    'if false:\n    say 1\nelif nil:\n    say 2\nelse:\n    say 3 + nil', 'func f(print):\n    print(1)\nf(5)',
    'items = [1, 2]\nsay items[0] + items[1] * items[-1] - items[-2] / 2\nsay items[2 - 5]',
    'try:\n    say 1 / 0\ncatch p:\n    say p\n    say nope', 'for i in range(1, 3):\n    say i\n    return',
    'if true:\n    break', 'try:\n    break\ncatch:\n    say "no"', 'say 10 ^ 400 / 3', 'say 2 ^ 99999 * 1.5',
    'func f():\n    return 1\nsay f()\nfunc f():\n    return 2\nsay f()', 'say later(2)\nfunc later(x):\n    return x * 3',
    'if true:\n    func inner():\n        return 1\nsay inner()', 'x = 1\nsay x:nope', 'say {"a": 1}:sort()',
    # what a function gives back
    'func a():\n    x = 5\nfunc b():\n    if true:\n        7\nfunc c():\n    for i in range(1, 2):\n        i\nfunc d():\n    say "d"\n'
    'func e():\n    return\nfunc g():\n    while false:\n        say 1\nfunc h():\n    try:\n        8\n    catch:\n        9\n'
    'say a()\nsay b()\nsay c()\nsay d()\nsay e()\nsay g()\nsay h()',
    'func f(n):\n    while true:\n        n += 1\n        if n > 5:\n            return n\nsay f(1)',
    'func grade(s):\n    if s >= 90:\n        return "A"\n    elif s >= 80:\n        return "B"\n    else:\n        for i in range(1, 3):\n'
    '            if i == 2:\n                return "C" + i\nsay grade(95)\nsay grade(85)\nsay grade(10)',
    'func f():\n    try:\n        return 1 / 0\n    catch p:\n        return "caught " + p\nsay f()',
    'func f(n):\n    for i in range(1, 10):\n        for j in range(1, 10):\n            if i * j == n:\n                return [i, j]\n    return nil\n'
    'say f(12)\nsay f(97)',
    # loops: break, continue, and the ones that come from a function called inside the loop (as before)
    'for i in range(1, 3):\n    for j in range(1, 3):\n        if j == 2:\n            break\n        say i + " " + j',
    'for i in range(1, 5):\n    try:\n        if i == 3:\n            break\n        say 10 / (i - 2)\n    catch p:\n        say "caught " + p',
    'for i in range(1, 4):\n    try:\n        x = 1 / (i - 2)\n    catch:\n        continue\n    say i',
    'n = 0\nfunc skip():\n    continue\nwhile n < 3:\n    n += 1\n    if n == 2:\n        skip()\n    say n',
    'func by(x):\n    break\nfor i in range(1, 3):\n    say i\n    [2, 1]:sort(by)\nsay "out"',
    'func stop():\n    break\nfor i in range(1, 5):\n    say "loop " + i\n    if i == 2:\n        stop()\nsay "after"',
    'n = 0\nwhile true:\n    n += 1\n    if n % 2 == 0:\n        continue\n    if n > 9:\n        break\n    say n',
    'items = [1, 2, 3]\nfor x in items:\n    items:add(x)\nsay items', 'for k in {"a": 1, "b": 2}:\n    say k',
    'for ch in "hey":\n    say ch', 'for i in range(10, 1, -3):\n    say i\nfor i in range(3, 1):\n    say i\nsay range(5)',
    'i = 100\nfunc f():\n    for i in range(1, 3):\n        say i\nf()\nsay i',
    'x = 0\nwhile x < 3 and true:\n    x += 1\nsay x\nsay (nil or "default")\nsay (0 and 5)\nsay not ""\nsay not [1]\nsay 1 is not 2',
    'total = 0\nfor i in range(1, 100000):\n    if i % 3 == 0 or i % 5 == 0:\n        total += i\nsay total',
    's = ""\nfor i in range(1, 200):\n    s += text(i % 10)\nsay len(s)\nsay s[0:20]',
    'if 1 < 2 then say "yes"\nwhile false: say "no"\nfor i in [1]: say i',
    # names: rule 2, functions inside functions, own-name built-ins, try and catch as names
    'total = 0\nfunc add(n):\n    total += n\nadd(5)\nadd(2)\nsay total',
    'func make():\n    count = 0\n    func inc():\n        count += 1\n        return count\n    return inc\nc = make()\nsay c()\nsay c()',
    'func f():\n    num = 5\n    return num\nsay f()\nsay num("3") + 1\nnum = 2\nsay num',
    'func t():\n    time = 3\n    return time\nsay t()\nsay time()\ntime = 5\nsay time', 'err = "custom"\nsay err',
    'problem = "old"\nfunc f():\n    try:\n        x = 1 / 0\n    catch problem:\n        say problem\nf()\nsay problem',
    'func f(len):\n    return len\nsay f(3)\nsay len("ab")', 'func greet:\n    say "hi"\ngreet()',
    'func perms(items):\n    if len(items) <= 1:\n        return [items]\n    out = []\n    for i in range(0, len(items) - 1):\n'
    '        rest = []\n        for j in range(0, len(items) - 1):\n            if j != i:\n                rest:add(items[j])\n'
    '        for p in perms(rest):\n            out:add([items[i]] + p)\n    return out\nsay perms([1, 2, 3])',
    # values: numbers, text, lists, dictionaries, err, live lines
    'say 1 == 1.0\nsay 1 is true\nsay "a" < "b"\nsay [1] == [1]\nsay {"a": 1} == {"a": 1}\nsay nil == nil\nsay 0.1 + 0.2\n'
    'say 7 / 2\nsay 7 % 3\nsay -7 % 3\nsay 2 ^ 10\nsay 10 / 4 * 2\nsay 5 is 5.0\nsay "5" is 5\nsay true is 1\nsay nil is false',
    'say 3.0\nsay 2 ^ 100\nsay 1 / 3\nsay round(2.5)\nsay round(3.14159, 2)\nsay floor(-2.5)\nsay 10 - 0.1\nsay 2 ^ -1\n'
    'say (-2) ^ 2\nsay -2 ^ 2\nsay 0.1 * 3\nsay 1 - 1 - 1\nsay 2 * 3 + 4 * 5 - 6 / 3 % 4',
    'x = 3\nx *= 2\nx /= 4\nx -= 0.5\nsay x\ns = "a"\ns += "b"\ns += 1\nsay s\ns *= 2\nsay s\nn = 7\nn -= 10\nsay n',
    'say "a" + 1 + 2\nsay 1 + 2 + "a"\nsay "x" * 3\nsay "abc":upper()\nsay "  hi ":trim()\nsay "a,b":split(",")\n'
    'say ["a", "b"]:join("-")\nsay "hello":find("l")\nsay "hello":count("l")\nsay "7":pad_left(3, "0")\nsay "a" * 0\nsay "ab" * -1',
    's = "hello world"\nsay s[0:4]\nsay s[:4]\nsay s[6:]\nsay s[-5:]\nsay s[3:1]\nitems = [1, 2, 3, 4]\nsay items[1:2]\nsay items[-2:]\n'
    'i = 1\nsay s[i + 1:i + 3]\nsay s[:s:find(" ") - 1]',
    'board = ["", "", ""]\nmoves = [0, 2]\nboard[moves:pop] = "X"\nsay board\norder = [1]\nsay board[order:pop]\nstack = [nil]\nsay board[stack:pop]',
    'd = {}\nd["a"] = 1\nd["a"] += 1\nd:set("b", 2)\nsay d\nsay d:get("c", 0)\nsay d:has("a")\nsay d:keys()\nsay d:values()\nsay len(d)\n'
    'd:remove("a")\nsay d\ncounts = {}\nfor w in ["a", "b", "a"]:\n    if counts:has(w):\n        counts[w] += 1\n    else:\n'
    '        counts[w] = 1\nsay counts\nsay counts:size()',
    'd = {1: "one", 2.5: "x"}\nsay d[1]\nsay d[2.5]\nd[1.0] = "uno"\nsay d\nsay {"a": [1, {"b": nil}]}',
    'items = [1, 2, 3]\nitems[-1] = 9\nitems[0] += 5\nsay items\ngrid = [[0, 0], [0, 0]]\ngrid[1][0] = 5\nsay grid\nsay grid[1][0] + 1',
    'say [1, 2]:join(", ")\nsay [1, [2, 3]]\nl = [1]\nl:add(l)\nsay l\nx = [1, 2]\nsay x:add(3):add(4)',
    'func by_len(w):\n    return len(w)\nwords = ["ccc", "a", "bb"]\nwords:sort(by_len)\nsay words\nwords:reverse()\nsay words\n'
    'nums = [3, 1, 2]\nsay nums:sort()\nsay nums:find(2)\nsay nums:has(5)\nsay [true, 2, "b", "A"]:sort()',
    'x = num("hi")\nif x is err:\n    say "not a number"\nsay x == err\nsay x != 5\nsay text(x)\nsay [x]\nsay int("4.7")\nsay number(" 8 ")',
    'bar = say "Loading"\nfor i in range(1, 3):\n    bar:rewrite "Loading" + "." * i\nbar:append "!"\nsay bar\nsay bar:text()\n'
    'x = bar + " ok"\nsay x\nbar:clear\nsay len(bar:text())\nbar:rewrite("Done", "lime")',
    'l = say "hi"\nsay l == "hi"\nsay l is "hi"\nsay "hi" == l\nsay l < "z"\nn = say 5\nsay n + 1\nsay n * 2\nsay l[1]\nsay l[0:0]\n'
    'say len(l)\nfor ch in l:\n    say ch\nd = {l: 1}\nsay d["hi"]\nsay -n',
    'items = []\nitems:add say "added"\nsay items\nprint("a", 1, true, nil, [1, "b"])\nprint()',
    'print:pen("red")\nsay "pen"\nx = input "With pen? "\nprint:pen()\nsay "plain"\nsay:color("c", "blue")\nsay:ascii("Hi")\nprint:ascii("Yo", "small")',
    'name = input "Name? "\nage = number(input("Age? "))\nsay name + " " + age\nok = input\nsay ok\nx = input:color("Q? ", "green")\nsay x',
    'say "a"\nsay "b"\nclear(1)\nsay "c"\nflush\nsay "d"\nclear(all)\nsay pi',
    'mention anims\nanims.loading("Hi", 0.2)\nanims.bar("B", 0.1)\nl = anims.type("typed", 0)\nanims.countdown(2, "Go")\nsay l:text()',
    'file.write("a.txt", "one")\nfile.add("a.txt", "two")\nsay file.read("a.txt")\nsay file.lines("a.txt")\nsay file.exists("a.txt")\n'
    'file.save("d.json", {"x": [1, 2]})\nsay file.load("d.json")\nfile.delete("a.txt")\nsay file.exists("a.txt")\nsay file.read("a.txt")',
    'say random(1, 6)\nsay random()\nsay random(0.5, 2.5)\nsay random(3)\nsay now()\nsay today()\nsay time()\nsay date()',
    'say sin(30)\nsay cos(60)\nsay log(100, 10)\nsay log(8, 2)\nsay sqrt(2)\nsay abs(-3)\nsay ceil(2.1)\nsay min(3, 1, 2)\n'
    'say max([4, 9])\nsay sum([1, 2])\nsay average(1, 2)\nwait(0)\nwait("x")',
    'func d(n):\n    if n == 0:\n        return 0\n    return d(n - 1) + 1\nsay d(9000)\ntry:\n    say d(20000)\ncatch p:\n    say p',
    'say ' + ' + '.join(['1'] * 400), 'say ' + '(' * 120 + '1' + ')' * 120, 'x = [' + ', '.join(str(i) for i in range(300)) + ']\nsay len(x)',
    'catch = []\ncatch:add("trout")\nsay catch\ntry = [3]\ntry:add(4)\nsay try',
    # the quick paths' edges: a number or text written in the program on either side, x += with each kind of value
    'say 5 == "a"\nsay "a" == 5\nsay "5" != 5\nsay "a" < "b"\nsay "b" >= "a"\nsay "x" + 1\nsay 1 + "x"\nsay "a" + "b"\nsay nil == "a"\nsay "a" + nil',
    'say "5" < 3', 'say 3 < "5"', 'say nil < 1', 'say 2 - "a"', 'say "a" * 2.5', 'say 7 % 0.0', 'say 0 / 0', 'x = 0\nsay 5 / x',
    'n = 5\nn += "x"\nsay n\ns = "a"\ns += 1\nsay s\ns += nil\nsay s\ns -= 1', 'x = 2\nx /= 0', 'x = "a"\nx *= 3\nsay x\nx *= "b"',
    'total = 0\nfunc add():\n    total += 1\n    total += "!"\nadd()\nsay total\nfunc more():\n    missing += 1\nmore()',
    'x = true\nx += 1', 'l = say "hi"\nl += "!"\nsay l\nm = say 4\nm += 1\nsay m',
    'say 5:has(1)', 'say [1]:upper()', 'say {"a": 1}:find("a")', 'd = {}\nsay d:has([1])', 'say "abc":has(1)\nsay "a1c":has(1)',
    'l = say "hi"\nsay l:upper()', 'd = {"a": 1}\nsay d:get([1])', 'd = {"a": 1}\nsay d:get("b", 5)\nsay d:get("b")\nd:set("c", 3)\nsay d\nd:set([1], 2)',
    'd = {"a": 1}\nsay d:keys(1)', 'say "Hi":lower()\nsay " x ":trim()\nsay "abc":starts("a")\nsay "abc":ends(1)\nsay "banana":count("a")\nsay "abc":find("z")',
    'say len("a")\nsay len("a", "b")', 'say len()\nsay len("ab")', 'say random(1, 1)\nsay random(1, 2, 3)',
    'func f(a):\n    return a\nsay f(1)\nsay f()', 'func f():\n    return 1\nx = f\nsay x()\nsay x(1)',
    'items = [1, 2, 3]\nitems[1] = "b"\nitems[-3] = "a"\nsay items\nitems[3] = 0', 'd = {}\nd[1] = "one"\nd["1"] = "text"\nd[1.5] = "x"\nsay d',
    's = "abc"\nsay s[0] + s[-1]\nsay s[3]', 'items = [[1, 2], [3, 4]]\nsay items[1][-1]\nsay items[2][0]',
    'func outer():\n    for i in range(1, 3):\n        func inner():\n            return i * 10\n        say inner()\n    return "end"\nsay outer()',
    'func f(n):\n    while true:\n        try:\n            if n > 2:\n                break\n            n += 1\n        catch:\n            say "no"\n    return n\nsay f(0)',
    'func f():\n    for i in range(1, 3):\n        try:\n            return i / 0\n        catch p:\n            continue\n    return "after"\nsay f()',
]
# The quick check for speed: generous limits, and the compiled runtime at least twice as fast as the tree walker.
INTERP_PERF = {
    "while": "i = 0\ntotal = 0\nwhile i < 300000:\n    total += i % 7\n    i += 1\nsay total\n",
    "for": "total = 0\nfor i in range(1, 1000000):\n    total += i % 7\nsay total\n",
    "calls": "func fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\nsay fib(25)\n",
}


def interp_corpus():
    """(name, program) for every console program there is: the repo's .tuf files, the guide's examples, Learn's lessons
    (example, starter and solution), the toolbox, looks and recursion tests' programs and INTERP_CASES. tgame programs
    come back separately, for the --scene preview. Programs that open a window or use the internet are left out."""
    console, games = [], []

    def add(name, code):
        if not code or not code.strip():
            return
        if re.search(r"^[ \t]*(?:import|mention)[ \t]+tgame\b", code, re.M) and not re.search(
                r"^[ \t]*(?:import|mention)[ \t]+(?:tgui|mtgui|atgui|tdraw|tap)\b", code, re.M):
            games.append((name, code))
        elif not WINDOW_LIBRARY.search(code):
            console.append((name, code))

    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "out", ".git", "dist", "build", ".claude")]
        for n in sorted(files):
            if n.endswith(".tuf"):
                with open(os.path.join(root, n), encoding="utf-8") as f:
                    add(os.path.relpath(os.path.join(root, n), REPO).replace(os.sep, "/"), f.read())
    guide = open(os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md"), encoding="utf-8").read()
    for i, code in enumerate(re.findall(r"```tuff\n(.*?)```", guide, re.S), 1):
        add(f"guide {i}", code)
    learn = os.path.join(REPO, "tuffcode", "renderer", "js", "learn.js")
    load = ("const vm = require('vm'), fs = require('fs'); const el = {addEventListener() {}, querySelector: () => null, "
            "querySelectorAll: () => [], classList: {add() {}, remove() {}, toggle() {}}, style: {}, appendChild() {}};"
            "const window = {tuff: {}, addEventListener() {}};"
            "const document = {querySelector: () => null, querySelectorAll: () => [], createElement: () => el, body: el, addEventListener() {}};"
            "vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {window, document, console, setTimeout, clearTimeout,"
            " TuffIcon: () => '', localStorage: {getItem: () => null, setItem() {}}});"
            "console.log(JSON.stringify(window.TuffLearn.sections()))")
    try:
        sections = json.loads(subprocess.run(["node", "-e", load, learn], capture_output=True, text=True, encoding="utf-8",
                                             timeout=60).stdout)
    except (FileNotFoundError, ValueError):
        sections = None
    for s in sections or []:
        for lesson in s["lessons"]:
            for part in ("example", "starter", "solution"):
                add(f"learn {lesson['id']} {part}", lesson.get(part))
    for name in ("TOOLBOX_PROGRAM", "TOOLBOX_FIXES", "LOOKS_PROGRAM", "DEEP_PROGRAM", "DEEP_RUNAWAY", "DEEP_SCENE", "NUMBERS_PROGRAM",
                 "KINDS_PROGRAM", "KINDS_SAVE", "KINDS_HOOKS", "KINDS_SCENE", "TMUSIC_PROGRAM", "TMUSIC_GAME"):
        add(name.lower(), globals()[name])
    for i, mistake in enumerate(TMUSIC_MISTAKES):
        add(f"tmusic_mistakes {i}", "mention tmusic\n" + mistake[0] + "\n")
    for i, code in enumerate(TMUSIC_GOOD):
        add(f"tmusic_good {i}", "mention tmusic\n" + code + "\n")
    for name in ("TOOLBOX_MISTAKES", "TOOLBOX_FIXES_CHECKS", "LOOKS_CHECKS", "NUMBERS_ERRORS", "NUMBERS_CHECKS", "KINDS_ERRORS", "KINDS_CHECKS"):
        for i, (code, *_) in enumerate(globals()[name]):
            add(f"{name.lower()} {i}", code + "\n")
    for i, code in enumerate(INTERP_CASES):
        add(f"case {i}", code + "\n")
    return console, games, sections is not None


def interp_run(folder, code, slow, env=None, timeout=60, files=None, main="program.tuf"):
    """Runs a program with INTERP_DRIVER in its own folder: (exit code, stdout, stderr), with the folder's path taken out.
    files: more files to write there first (1.5.0: the program's own files it imports), and main: the program's name."""
    os.makedirs(folder, exist_ok=True)
    for rel, text in (files or {}).items():
        os.makedirs(os.path.dirname(os.path.join(folder, rel)), exist_ok=True)
        with open(os.path.join(folder, rel), "w", encoding="utf-8") as f:
            f.write(text)
    path = os.path.join(folder, main)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    full = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW", "TUFF_NO_WRITES", "TUFF_BASE_DIR")}
    full.update({"PYTHONIOENCODING": "utf-8", **(env or {})})
    if slow:
        full["TUFF_SLOW"] = "1"
    try:
        p = subprocess.run([sys.executable, "-c", INTERP_DRIVER, REPO, path], input=INTERP_ANSWERS, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, env=full, cwd=folder)
        out = (p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired:
        out = ("timeout", "", "")

    def tidy(text):
        if not isinstance(text, str):
            return text
        text = text.replace(folder, "<folder>").replace(folder.replace("\\", "/"), "<folder>")
        # A Python crash (a bug in Tuff, like 10 ^ 400 / 3's OverflowError in 1.4.1) lists Python's own calls, which
        # are different in each runtime: what matters is that both crash with the same error.
        return re.sub(r"Traceback \(most recent call last\):\n(?:[ \t].*\n)*", "Traceback: ", text)
    return tuple(tidy(x) for x in out)


def t_interp(c):
    """1.5.0's compiled interpreter: every console program there is (the repo's .tuf files, the guide's and Learn's
    examples, the toolbox, looks and recursion tests' programs and the corner cases above) gives exactly the same
    output, errors (line and column) and exit code as the old tree walker (TUFF_SLOW=1); so does Tuff Engine's --scene
    preview of every tgame program (its line tracking too). Then the step hooks the debugger will use, atgui's
    app:closed time limit, library callbacks (Runtime.call), and a quick check that it's faster."""
    from concurrent.futures import ThreadPoolExecutor
    console, games, learned = interp_corpus()
    c.check(learned, "Learn's lessons were read from learn.js (with Node)")
    c.check(len(console) >= 150 and len(games) >= 60, f"the corpus: {len(console)} console programs and {len(games)} tgame programs",
            (len(console), len(games)))
    folder = os.path.join(HERE, "out", "interp")

    def both(job):
        i, (name, code) = job
        return name, [interp_run(os.path.join(folder, mode, str(i)), code, mode == "slow") for mode in ("slow", "fast")]

    with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as pool:
        results = list(pool.map(both, enumerate(console)))
    differ = [(name, slow, fast) for name, (slow, fast) in results if slow != fast]
    timeouts = [name for name, (slow, fast) in results if "timeout" in (slow[0], fast[0])]
    c.check(not differ, f"{len(results)} console programs give the same output, errors and exit code in both runtimes",
            ", ".join(name for name, _s, _f in differ) + "\n" + "\n".join(f"{name}:\n  slow {slow!r}\n  fast {fast!r}"[:700]
                                                                     for name, slow, fast in differ[:2]))
    c.check(not timeouts, "...and none of them hangs", timeouts)
    errors = sum(1 for _, (slow, _f) in results if "Tuff error" in slow[2])
    c.check(errors >= 100, f"...{errors} of them stop with a Tuff error, which is on the same line and column in both", errors)
    crashes = [name for name, (slow, fast) in results if "Traceback" in slow[2] + fast[2]]
    c.check(not crashes, "...and none of them crash in Python (10 ^ 400 / 3 and 2 ^ 99999 * 1.5 did, before 1.5.0's numbers fix)", crashes)
    # 1.5.0: programs in several files (import money.tuf), the modules test's: the same output, and errors in the same file,
    # line and column, in both.
    projects = modules_projects()
    runs = [(name, [interp_run(os.path.join(folder, "files_" + mode, str(i)), files["shop.tuf"], mode == "slow", files=files, main="shop.tuf")
                    for mode in ("slow", "fast")]) for i, (name, files) in enumerate(projects)]
    differ = [(name, slow, fast) for name, (slow, fast) in runs if slow != fast]
    c.check(not differ and len(runs) >= 20, f"{len(runs)} programs in several files give the same output, errors and exit code in both runtimes",
            "\n".join(f"{name}:\n  slow {slow!r}\n  fast {fast!r}"[:700] for name, slow, fast in differ[:2]))
    # In TuffCode's Run panel (TUFF_IDE=1): the lines, rewrites, looks and prompts it's sent are the same too.
    ide = [(n, code) for n, code in console if n in ("looks_program", "toolbox_program") or "rewrite" in code or "print:pen" in code][:40]
    same = [n for i, (n, code) in enumerate(ide) if interp_run(os.path.join(folder, "ide_slow", str(i)), code, True, env={"TUFF_IDE": "1"})
            != interp_run(os.path.join(folder, "ide_fast", str(i)), code, False, env={"TUFF_IDE": "1"})]
    c.check(len(ide) >= 10 and not same, f"with TUFF_IDE=1, {len(ide)} programs send TuffCode the same lines in both", same[:5])

    def preview(job):
        i, (name, code) = job
        dumps = []
        for mode in ("slow", "fast"):
            where = os.path.join(folder, "scene_" + mode, str(i))
            os.makedirs(where, exist_ok=True)
            for pic in ("star.png", "blip.wav"):
                if os.path.exists(os.path.join(GAMES, pic)) and not os.path.exists(os.path.join(where, pic)):
                    with open(os.path.join(GAMES, pic), "rb") as f, open(os.path.join(where, pic), "wb") as g:
                        g.write(f.read())
            path, out = os.path.join(where, "game.tuf"), os.path.join(where, "scene.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            if os.path.exists(out):
                os.remove(out)
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            env.pop("TUFF_TGAME_AUTOPILOT", None)
            env.pop("TUFF_SLOW", None)
            if mode == "slow":
                env["TUFF_SLOW"] = "1"
            p = subprocess.run([sys.executable, TUFF, "--scene", path, path, out], cwd=where, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL)
            try:
                with open(out, encoding="utf-8") as f:
                    dumps.append((p.returncode, f.read().replace(where.replace("\\", "\\\\"), "<folder>").replace(where.replace("\\", "/"), "<folder>")))
            except OSError:
                dumps.append((p.returncode, None))
        return name, dumps

    with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as pool:
        previews = list(pool.map(preview, enumerate(games)))
    differ = [(name, d) for name, d in previews if d[0] != d[1] or d[0][1] is None]
    c.check(not differ, f"Tuff Engine's --scene preview of {len(previews)} tgame programs makes the same things, from the same lines, in both",
            "\n".join(f"{name}: {str(d[0])[:300]} / {str(d[1])[:300]}" for name, d in differ[:3]))
    made = sum(1 for _, d in previews if d[1][1] and '"made"' in d[1][1])
    c.check(made >= 30, f"...{made} of them say which line made each thing", made)
    interp_hooks(c)
    interp_speed(c)


def interp_hooks(c):
    """In this process: the step hooks (the debugger's hook point), atgui's app:closed limit, Runtime.call."""
    import contextlib
    import io
    import tuff
    import tuff_atgui
    src = ("total = 0\nfunc add(n):\n    total += n\n    return total\nfor i in range(1, 3):\n    add(i)\n"
           "func stuck():\n    n = 0\n    while true:\n        n += 1\nfunc two(a, b):\n    return a + b\nfunc bad():\n    return nope\n")
    for slow in (True, False):
        mode = "the tree walker" if slow else "the compiled runtime"
        old = os.environ.pop("TUFF_SLOW", None)
        if slow:
            os.environ["TUFF_SLOW"] = "1"
        try:
            interp = tuff.Interpreter(src, HERE)
        finally:
            os.environ.pop("TUFF_SLOW", None)
            if old is not None:
                os.environ["TUFF_SLOW"] = old
        c.check(interp.fast is not slow, f"TUFF_SLOW={'1' if slow else '(none)'} gives {mode}")
        program = tuff.Parser(tuff.tokenize(src)).program()
        seen = []
        interp.step_hooks.append(lambda s, env: seen.append(s.line))
        interp.run_block(program, interp.globals)
        c.check(seen == [1, 2, 5, 6, 3, 4, 6, 3, 4, 6, 3, 4, 7, 11, 13] and interp.globals.vars["total"] == 6,
                f"{mode}: a step hook sees every statement, in the order they run", seen)
        interp.step_hooks.clear()

        def stop_at_4(s, env):
            if s.line == 4:
                raise tuff.TuffError("Stopped by the debugger.")
        interp.step_hooks.append(stop_at_4)
        try:
            interp.invoke(interp.globals.vars["add"], [1])
            got = None
        except tuff.TuffError as err:
            got = (err.line, err.col, err.msg)
        interp.step_hooks.remove(stop_at_4)
        c.check(got == (4, 5, "Stopped by the debugger."), f"{mode}: a hook's error stops the program on the statement's line", got)
        lib = tuff_atgui.Lib(interp.rt)
        err = io.StringIO()
        t0 = time.perf_counter()
        with contextlib.redirect_stderr(err):
            ok = lib.fire_by(interp.globals.vars["stuck"], 0.3, "app:closed's function took too long.")
        secs = time.perf_counter() - t0
        c.check(ok is False and secs < 5 and "app:closed's function took too long." in err.getvalue() and "line 10" in err.getvalue()
                and not interp.step_hooks, f"{mode}: atgui stops app:closed's function after its time limit ({secs:.1f} s)", err.getvalue()[-300:])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            calls = (interp.rt.call(interp.globals.vars["two"], 2, 3, 99), interp.rt.call(interp.globals.vars["bad"]))
        c.check(calls == ((True, 5), (False, None)) and "Tuff error on line 14: I don't know what 'nope' is." in err.getvalue(),
                f"{mode}: Runtime.call (library callbacks) drops extra inputs and reports errors", (calls, err.getvalue()[-200:]))


def interp_speed(c):
    folder = os.path.join(HERE, "out", "interp", "speed")
    os.makedirs(folder, exist_ok=True)
    for name, code in INTERP_PERF.items():
        path = os.path.join(folder, f"{name}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        times, outs = {}, {}
        for mode in ("slow", "fast"):
            env = {**os.environ}
            env.pop("TUFF_SLOW", None)
            if mode == "slow":
                env["TUFF_SLOW"] = "1"
            t0 = time.perf_counter()
            p = subprocess.run(tuff_cmd() + [path], capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
                               stdin=subprocess.DEVNULL)
            times[mode], outs[mode] = time.perf_counter() - t0, p.stdout.strip().splitlines()[:1]
        c.check(outs["fast"] == outs["slow"] and times["fast"] < 5 and times["fast"] * 2 < times["slow"],
                f"{name}: {times['slow']:.2f} s with the tree walker, {times['fast']:.2f} s compiled ({times['slow'] / max(times['fast'], 0.001):.1f}x)",
                (outs, times))
    # The debugger's hook point, off and on: in this process, the while loop without a step hook, then with one that
    # does nothing (each of its 600,000 statements calls it).
    import tuff
    os.environ.pop("TUFF_SLOW", None)
    src = INTERP_PERF["while"].replace("say total\n", "")
    program = tuff.Parser(tuff.tokenize(src)).program()
    secs = []
    for hooked in (False, True):
        interp = tuff.Interpreter(src, folder)
        if hooked:
            interp.step_hooks.append(lambda s, env: None)
        t0 = time.perf_counter()
        interp.run_block(program, interp.globals)
        secs.append(time.perf_counter() - t0)
    c.check(secs[0] < secs[1] and secs[0] < 2, f"with no step hook the loop takes {secs[0]:.2f} s, with a do-nothing one {secs[1]:.2f} s", secs)


# ---------------------------------------------------------------- text templates (1.5.0)

FSTRINGS_PROGRAM = r'''name = "Sam"
score = 9
say f"{name} has {score + 1} points"
price = 6.375
qty = 2
say f"Total: {price * qty:money}"
say f"{2.675:0.00}|{1.005:0.00}|{0.125:0.00}|{2.5:0}|{-2.5:0}|{82.25:0.0}|{-0.001:0.00}|{1 / 3:0.000}|{0.1 + 0.2:0.00}"
say f"{7:000}|{-7:000}|{1234:000}|{7.6:000}|{5.5:000.00}|{2 ^ 70:0}"
say f"{1234.5:money}|{-1.5:money}|{0:money}|{1000000:money}|{0.005:money}|{-0.004:money}"
say f"[{name:6}][{score:4}][{name:>6}][{score:<4}][{"toolong":3}][{2.5:5}]"
say f"{name:upper()} {name:lower} {{braces}} }}{{"
ages = {"sam": 14}
say f'{ages["sam"]}, {ages:get("ann", 0)}, { {"a": 1}["a"] }, {ages:get("sam"):000}'
say f"{[1, "two", 3.5]} {nil} {true} {num("x")} {ages}"
say f"tab\there \"quoted\" it's C:\{name}\files"
say f"{f"{score:00}":>4}|{f'{name}'}|{"a:b"}|{"}"}"
say f""
say f"plain"
say f"{name}"[0] + f"{score}":upper()
say len(f"{name}{name}")
words = ["a", "b"]
say f"{words:join(", ")} and {words[0]:upper()}"
func greet(who):
    return f"Hi {who}!"
say greet(f"{name}")
f = 5
say f + 1
answer = input f"Price for {name}? "
say f"You typed {num(answer):money}"
'''
FSTRINGS_OUTPUT = ["Sam has 10 points", "Total: $12.75", "2.68|1.01|0.13|3|-3|82.3|0.00|0.333|0.30",
                   "007|-007|1234|008|005.50|1180591620717411303424", "$1,234.50|-$1.50|$0.00|$1,000,000.00|$0.01|$0.00",
                   "[Sam   ][   9][   Sam][9   ][toolong][  2.5]", "SAM sam {braces} }{", "14, 0, 1, 014",
                   '[1, "two", 3.5] nil true err {"sam": 14}', 'tab\there "quoted" it\'s C:\\Sam\\files', "  09|Sam|a:b|}", "",
                   "plain", "S9", "6", "a, b and A", "Hi Sam!", "6", "Price for Sam? You typed $1,234.57"]
# Mistakes in a template: (code, line, column, what the run says, what --check says: None for the same, "OK" when
# only the run can tell). The column is inside the text, at the bad part, so the editor's squiggle lands there.
FSTRINGS_ERRORS = [
    ('name = "Sam"\nsay f"Hi {nmae}!"', 2, 11, "I don't know what 'nmae' is. Did you mean 'name'?", None),
    ('name = "Sam"\nsay f"Hi {name"', 2, 10, "This { has no } to close it. To show a { itself, write {{.", None),
    ('name = "Sam"\nsay f"Hi {name}', 2, 5, 'This text is missing its closing "', None),
    ('say f"a } b"', 1, 9, "A } on its own can't go in a text template. To show one, write }}.", None),
    ('say f"{}"', 1, 7, "These { } have nothing in them.", None),
    ('x = 1.5\nsay f"{x:.2f}"', 2, 10, "'.2f' isn't a format. Formats look like 0.00", None),
    ('x = 1.5\nsay f"{x:.2f}"', 2, 10, "Here, write {x:0.00}.", None),
    ('n = 7\nsay f"{n:05d}"', 2, 10, "Here, write {n:00000}.", None),
    ('x = 1\nsay f"{x:}"', 2, 9, "Put a format after the ':'", None),
    ('say f"{1:2000}"', 1, 10, "2000 is too wide: a width can be up to 1000.", None),
    ('x = "abc"\nsay f"{x:0.00}"', 2, 10, 'The format 0.00 only works on numbers, but this is text ("abc").',
     "The format 0.00 only works on numbers, but x is text."),
    ('x = 2\nsay f"{x + }"', 2, 12, "I expected a value here, but found }.", None),
    ('x = 2\nsay f"{x y}"', 2, 10, "I didn't expect y here. The { } in a text template hold one value each", None),
    ('say f"{len("ab"}"', 1, 11, "This ( needs a ) before the } that ends the { }.", None),
    ('say f"{1 # note}"', 1, 10, "A # comment can't go inside the { } of a text template.", None),
    ('x = 3\nsay f"{x:upper()}"', 2, 9, "A number doesn't have any :methods.", None),
    ('say f"{f"{zz}"}"', 1, 11, "I don't know what 'zz' is.", None),
    ('say f"ok" + f"{num("x"):0.00}"', 1, 25, "The value for the format 0.00 is err", "OK"),
    ('func show(p):\n    say f"{p} costs {p:money}"\nshow("tea")', 2, 24, "The format money only works on numbers", "OK"),
]
# The checker on the code in templates: (code, part of what --check says, or "OK").
FSTRINGS_CHECKS = [
    ('a = input "Price? "\nsay f"{a:money}"', "a is text. input gives text, so turn it into a number first: {num(a):money}."),
    ('func f2():\n    t = 1\nsay f"{t}"', "'t' is only set inside f2(), so it only exists there."),
    ('x = [1]\nsay f"{x:size()}"', "A list doesn't have :size."),
    ('say f"{len(1, 2)}"', "len() got the wrong number of inputs (2)."),
    ('say f"{[1]:money} {true:000} {nil:0.0}"', "The format money only works on numbers, but this is a list."),
    ('a = 1\nb = 2\nsay f"Total: " + a + b', 'or use a text template: f"Total: {a + b}"'),
    ('x = "5"\nsay f"{num(x):0.00} {x:3} {x:>3}"', "OK"),
    ('func g(n):\n    return f"{n:0.0}"\nsay g(2)', "OK"),
    ('items = [1]\nfor i in items:\n    say f"{i:000}"', "OK"),
    ('d = {}\nsay f"{d:get("k", 1):0.0} {nil:5}|{true:<6}"', "OK"),
    ('f = 5\nsay f + 1', "OK"),
    ('mention tgame\ngame = tgame.window("x")\nscore = 0\nlabel = game:text(f"Score: {score:000}", 300, 30)\nlabel:set f"Score: {score + 1}"', "OK"),
]
# The editor (renderer/js/tuff-lang.js): the code in a template's { } is code for completions and rename, its f has a
# hover, and Monarch colours the { } as code and comes back to the root after the line.
FSTRINGS_LANG = r"""
const fs = require('fs'), vm = require('vm');
const window = {}, ctx = { window };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
let monarch = null, hover = null, completion = null;
const monaco = { Range: class { constructor(...a) { this.a = a; } }, editor: { defineTheme() {} }, languages: {
  register() {}, setMonarchTokensProvider(_id, def) { monarch = def; }, setLanguageConfiguration() {},
  registerHoverProvider(_id, p) { hover = hover || p; }, registerDefinitionProvider() {}, registerReferenceProvider() {},
  registerRenameProvider() {}, registerDocumentSymbolProvider() {}, registerSignatureHelpProvider() {}, registerColorProvider() {},
  registerCompletionItemProvider(_id, p) { completion = p; },
  CompletionItemKind: new Proxy({}, { get: (_t, k) => k }), CompletionItemInsertTextRule: {}, IndentAction: {}, SymbolKind: {} } };
window.defineTuffTheme = () => {};
window.registerTuff(monaco, '#3574f0');
const model = (src, col) => { const lines = src.split('\n'); return { getLinesContent: () => lines, getLineContent: (n) => lines[n - 1],
  getValue: () => src, getWordUntilPosition: () => ({ startColumn: col || 1, endColumn: col || 1 }),
  getWordAtPosition: ({ lineNumber, column }) => { for (const m of lines[lineNumber - 1].matchAll(/\w+/g))
    if (m.index < column && column <= m.index + m[0].length) return { word: m[0], startColumn: m.index + 1, endColumn: m.index + 1 + m[0].length };
    return null; } }; };
const rules = (s) => monarch.tokenizer[s].flatMap((r) => (r.include ? rules(r.include.slice(1)) : [r]));
function colours(src) { // the first rule that matches wins, as in Monarch
  const stack = ['root'], out = [];
  for (const line of src.split('\n')) {
    const toks = [];
    for (let i = 0; i < line.length;) {
      const r = rules(stack[stack.length - 1]).find((x) => { const re = new RegExp(x[0].source.replace('@symbols', monarch.symbols.source), 'y'); re.lastIndex = i; const m = re.exec(line); return m && m[0].length && (x.m = m[0]); });
      if (!r) { i++; continue; }
      const a = r[1]?.cases ? r[1].cases['@default'] : r[1];
      toks.push(`${r.m}=${Array.isArray(a) ? a.join('+') : a}`);
      if (r[2] === '@pop') stack.pop(); else if (r[2]) stack.push(r[2].slice(1));
      i += r.m.length;
    }
    out.push({ toks, state: stack.join('>') });
  }
  return out;
}
const ids = (src) => ctx.tuffIdents(model(src)).map((x) => `${x.name}@${x.start}`).join(' ');
const c = colours('say f"Hi {name:upper()} {{x}} {score + 1:0.00} {d:get("k")}!" + "plain"\nx = 1');
const c2 = colours(`say f'{ {"a": 1}["a"]:money}' + f"{f'{x}'}"\nx = 2`);
const inside = completion.provideCompletionItems(model('say f"{name:', 13), { lineNumber: 1, column: 13 }).suggestions;
console.log(JSON.stringify({
  kinds: ctx.tuffScan('say f"a{x}b"').kinds.join(''),
  code: ctx.insideStringOrComment('say f"Hi {name:'), text: ctx.insideStringOrComment('say f"Hi {name} '),
  plain: ctx.insideStringOrComment('say "Hi {name:'), dict: ctx.insideStringOrComment('say f"{ {"a": 1}["a"] } '),
  ids: ids('name = 1\nsay f"Hi {name} and {score + 1:0.00}"'), fvar: ids('f = 2\nsay f"f{f}"'), none: ids('say "{name}" + f"{{name}}"'),
  hover: hover.provideHover(model('say f"Hi {name}"'), { lineNumber: 1, column: 5 })?.contents[0].value,
  nohover: hover.provideHover(model('f = 1\nsay f + 1'), { lineNumber: 2, column: 5 }),
  snippet: completion.provideCompletionItems(model(''), { lineNumber: 1, column: 1 }).suggestions.find((s) => s.label === 'f"..."')?.insertText,
  methods: inside.some((s) => s.label === 'upper'),
  colours: c[0].toks, states: [c[0].state, c[1].state, c2[0].state, c2[1].state], next: c2[1].toks[0],
}));
"""


def t_fstrings(c):
    """Console only, no window: 1.5.0's text templates (f"..."). A program with every format, {{ }}, quotes and
    dictionaries in the { } and templates inside templates runs, and --check accepts it; each mistake stops the run
    and --check with the same message, on its line and at its column inside the text; the checker walks the code in
    the { }; Tuff Engine's --scene preview runs templates (and stops one that doubles its text); and the editor's
    tuff-lang.js reads the { } as code (with Node)."""
    folder = os.path.join(HERE, "out", "fstrings")
    os.makedirs(folder, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("TUFF_IDE", None)

    def write(name, code):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        return path

    def where(stderr):
        """The line, column and message of the first "Tuff error" (the column from the ^ under the line)."""
        lines = stderr.splitlines()
        first = next((i for i, x in enumerate(lines) if x.startswith("Tuff error on line ")), None)
        if first is None:
            return None, None, stderr.strip()
        head, msg = lines[first][len("Tuff error on line "):].split(": ", 1)
        gutter = f"  {head} | "
        caret = lines[first + 2] if first + 2 < len(lines) and lines[first + 2].strip() == "^" else ""
        return int(head), (caret.index("^") - len(gutter) + 1) if caret else None, msg

    path = write("fstrings.tuf", FSTRINGS_PROGRAM.rstrip("\n"))
    p = subprocess.run(tuff_cmd() + [path], input="1234.567\n", capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    got = p.stdout.splitlines()
    c.check(p.returncode == 0 and "Tuff error" not in p.stderr, "the templates program runs to the end", (p.stdout + p.stderr)[-600:])
    for i, want in enumerate(FSTRINGS_OUTPUT):
        c.check(i < len(got) and got[i] == want, f"line {i + 1}: {want}", got[i] if i < len(got) else "(missing)")
    p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    c.check(p.stdout.strip() == "OK", "--check accepts all of it", (p.stdout + p.stderr)[:600])

    for i, (code, line, col, says, check_says) in enumerate(FSTRINGS_ERRORS):
        bad = write(f"mistake{i}.tuf", code)
        shown = code.splitlines()[line - 1].strip()
        p = subprocess.run(tuff_cmd() + [bad], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env, stdin=subprocess.DEVNULL)
        at = where(p.stderr)
        c.check(p.returncode == 1 and at[:2] == (line, col) and says in at[2], f"running {shown!r} stops at {line}:{col}: {says[:60]!r}", at)
        p = subprocess.run(tuff_cmd() + ["--check", bad], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        if check_says == "OK":
            c.check(p.stdout.strip() == "OK", f"--check can't know it before the run, and says OK: {shown!r}", (p.stdout + p.stderr)[:300])
        else:
            at = where(p.stderr)
            c.check(p.returncode == 1 and at[:2] == (line, col) and (check_says or says) in at[2],
                    f"--check on {shown!r} says it at {line}:{col} too", at)

    for i, (code, want) in enumerate(FSTRINGS_CHECKS):
        bad = write(f"check{i}.tuf", code)
        p = subprocess.run(tuff_cmd() + ["--check", bad], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        out = (p.stdout + p.stderr).strip()
        shown = code.splitlines()[-1].strip()
        if want == "OK":
            c.check(out == "OK", f"--check accepts: {shown}", out[:300])
        else:
            c.check(p.returncode == 1 and want in out, f"--check on {shown!r} says {want[:50]!r}", out[:300])

    # Tuff Engine's preview: a setup with templates, and one that keeps doubling its text with a template stops as too-much.
    src = write("fstrings_scene.tuf", 'mention tgame\ngame = tgame.window("T", 300, 200)\nscore = 7\n'
                                      'label = game:text(f"Score: {score:000}", 150, 30)\nsay f"made {score}"')
    code, out, err, d, secs = scene(src)
    c.check(code == 0 and d.get("error") is None and d.get("stopped") == "end" and "Score: 007" in json.dumps(d.get("batch")),
            f"the --scene preview runs a setup with templates ({secs:.1f} s)", (d.get("error"), d.get("stopped"), err[-300:]))
    src = write("fstrings_huge.tuf", 'mention tgame\ngame = tgame.window("Huge", 400, 300)\nfirst = game:box(10, 10)\n'
                                     's = "ab"\nfor i in range(1, 40):\n    s = f"{s}{s}"\nlast = game:box(50, 50)')
    code, out, err, d, secs = scene(src)
    c.check(code == 0 and d.get("stopped") == "too-much" and [t.get("var") for t in d.get("things", [])] == ["first"] and secs < 4,
            f"...and text doubled by a template stops it as too-much in {secs:.1f} s", (d.get("stopped"), d.get("error"), secs))

    lang = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")
    try:
        p = subprocess.run(["node", "-e", FSTRINGS_LANG, lang], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the editor checks")
        return
    try:
        t = json.loads(p.stdout)
    except ValueError:
        c.check(False, "the editor checks ran", (p.stdout + p.stderr)[-600:])
        return
    c.check(t["kinds"] == "ccccsssscsss", 'the editor reads say f"a{x}b" as code, text, then x as code', t["kinds"])
    c.check(t["code"] is False and t["text"] is True and t["plain"] is True and t["dict"] is True,
            "after f\"Hi {name: it's in code (so completions work), after the } it's text again", [t[k] for k in ("code", "text", "plain", "dict")])
    c.check(t["methods"], 'typing f"{name: offers the methods', t["methods"])
    c.check(t["ids"] == "name@1 name@11 score@22" and t["fvar"] == "f@1 f@9" and t["none"] == "",
            "rename and find uses see the names in { } (not the f, plain text or {{ }})", [t["ids"], t["fvar"], t["none"]])
    c.check('f"{name} has' in (t["hover"] or "") and t["nohover"] is None, "the f of a template has a hover, and a variable called f doesn't",
            [t["hover"], t["nohover"]])
    c.check(t["snippet"] == 'f"${1:Hello} {${2:name}\\}$0"', 'there is an f"..." snippet', t["snippet"])
    toks = t["colours"]
    c.check(all(x in toks for x in ('f"=string', "{=delimiter.curly", "name=identifier", ":upper=delimiter+method", "score=identifier",
                                    ":0.00=string.escape", "{{=string.escape", "k=string", "!=string")),
            "the colours: the code in { } as code, its format and {{ }} as escapes, a string inside as a string", toks)
    c.check(t["states"] == ["root", "root", "root", "root"] and t["next"] == "x=identifier",
            "after a template (with a dictionary or another template in it) the next line is code again", [t["states"], t["next"]])


# ---------------------------------------------------------------- 1.5.0: sprite sheets (sprite:frames, :animation, :play)
# games/hero_sheet.png is 4 frames across and 2 down, 32 x 32 pixels each, every frame its own colour (FRAME_COLORS)
# with a white dot that moves along.
FRAME_COLORS = ["#e5484d", "#f97316", "#e2a508", "#22a35a", "#14b8a6", "#3574f0", "#8b5cf6", "#ec4899"]

FRAMES_SCENE = """mention tgame

game = tgame.window("Frames", 600, 400)
hero = game:image("hero_sheet.png", 100, 300, 64)
hero:frames(4, 2)
hero:animation("walk", [1, 2, 3, 4], 10)
hero:animation("jump", range(5, 8), 12)
hero:play("walk")
hero:flip()
coin = game:image("hero_sheet.png", 300, 100)
coin:frames(4, 2)
coin:frame(6)
badge = game:hud():image("hero_sheet.png", 40, 40, 16)
badge:frames(4)
plain = game:image("hero_sheet.png", 500, 100)

while game:open():
    dt = game:frame()
"""

# Run headless (headless.py: every frame is 1/60 s): a walk played every frame carries on, a jump plays once and its
# on_done function runs, stop holds the frame, and pausing holds everything, the page's canvases too.
FRAMES_RUN = """mention tgame

game = tgame.window("Flip", 400, 300)
hero = game:image("hero_sheet.png", 100, 100, 64)
hero:frames(4, 2)
hero:animation("walk", [1, 2, 3, 4], 10)
hero:animation("jump", [5, 6, 7, 8], 20)
hero:play("walk")
say "start " + hero:frame()
coin = game:hud():image("hero_sheet.png", 30, 30)
coin:frames(4, 2)
coin:animation("spin", [5, 6], 4)
coin:play("spin")
paused_frames = 0
stage = "walk"

func landed(who, name):
    say "done " + name + " " + who:frame() + " at " + round(game:time(), 2)
    who:play("walk")
    say "then " + who:frame()

hero:on_done(landed)

func step(dt):
    if stage is "walk":
        hero:play("walk")
    if stage is "paused":
        paused_frames += 1
        if paused_frames is 30:
            say "while paused " + hero:frame()
            game:resume()
            stage = "after pause"

func check():
    say "at 0.25 " + hero:frame()
    stage = "jump"
    hero:play("jump", false)
    say "jump " + hero:frame()

func halt():
    hero:stop()
    say "stopped " + hero:frame()

func later():
    say "still " + hero:frame()
    hero:play("walk")
    stage = "paused"
    say "before pause " + hero:frame()
    game:pause("Paused")

func finish():
    say "end " + coin:frame()
    game:close()

game:every_frame step
game:after(0.25, check)
game:after(0.82, halt)
game:after(1.2, later)
game:after(1.55, finish)
"""

# Mistakes when it runs (Tuff Engine's preview shows the same error, on the same line): (code after the hero is made
# and cut into 4 x 2 frames, the line, the message).
FRAMES_RUN_ERRORS = [
    ('b = game:box(1, 2)\nb:frames(4)\n', 6, "Only pictures have frames (:frames)."),
    ('b = game:box(1, 2)\nb:stop()\n', 6, "To stop a sprite moving, use sprite:speed(0, 0)."),
    ('pic = game:image("hero_sheet.png", 1, 2)\npic:frame(2)\n', 6, ":frame needs the picture cut into frames first"),
    ('hero:frames(0)\n', 5, ":frames needs how many frames across"),
    ('hero:frames(10000, 2)\n', 5, ":frames can cut a picture into 10000 frames at most, not 20000."),
    ('hero:frame(9)\n', 5, ":frame: this picture has 8 frames (1 to 8), so there's no frame 9."),
    ('hero:frame(0)\n', 5, ":frame: frames are numbered from 1 (the top left one), so there's no frame 0."),
    ('hero:animation("walk", [1, 9], 10)\n', 5, "there's no frame 9"),
    ('hero:animation("walk", [], 10)\n', 5, ':animation needs at least one frame, like hero:animation("walk", [1, 2, 3, 4], 10).'),
    ('hero:animation("walk", 3, 10)\n', 5, ':animation needs its frames as a list, like hero:animation("walk", [1, 2, 3, 4], 10).'),
    ('hero:animation("walk", [1, 2], 0)\n', 5, ":animation's speed is how many frames a second, above 0"),
    ('hero:animation(5, [1, 2], 10)\n', 5, ":animation needs a name as text first"),
    ('hero:play("walk")\n', 5, 'There\'s no animation called "walk". Make it first, like hero:animation("walk", [1, 2, 3, 4], 10)'),
    ('hero:animation("walk", [1, 2], 10)\nhero:play("wlak")\n', 6, 'There\'s no animation called "wlak". This picture has "walk". Did you mean "walk"?'),
    ('hero:animation("walk", [1, 2], 10)\nhero:play("walk", "once")\n', 6, ":play's second input is true (again and again"),
    ('hero:animation("jump", [5, 6], 10)\nhero:frames(4)\nhero:play("jump")\n', 7,
     'The animation "jump" shows frame 5, but this picture has 4 frames now (1 to 4).'),
    ('hero:on_done("landed")\n', 5, ":on_done needs a function name"),
]

# The checker: what it accepts (every :animation it can't read, or a file of the program's own, keeps it quiet about
# :play's names), and the mistakes it's sure of. After a window and hero = game:image("hero_sheet.png", 100, 100, 64).
FRAMES_GOOD = [
    'hero:frames(4, 2)\nhero:animation("walk", [1, 2, 3, 4], 10)\nhero:play("walk")\n',
    'hero:frames(4)\nhero:animation("walk", range(1, 4))\nhero:play("walk", false)\nhero:stop()\nn = hero:frame()\nhero:frame(n + 1)\n',
    'hero:frames(4)\nfunc make(name):\n    hero:animation(name, [1, 2], 8)\nmake("walk")\nhero:play("walk")\n',
    'hero:frames(4)\nfunc landed(who, name):\n    who:play("idle")\nhero:animation("idle", [1], 1)\nhero:on_done(landed)\n',
    'hero:frames(4)\nfunc landed():\n    say "done"\nhero:on_done(landed)\n',
    'hero:frames(4)\nhero:animation("walk", [1, 2], 10)\nstate = "walk"\nhero:play(state)\n',
    'hero:frames(4)\nfor n in ["a", "b"]:\n    hero:animation(n, [1], 2)\nhero:play("c")\n',
    'hero:frames(4)\nhero:animation("walk", [1, 2], 10)\nhero:play("walk", true)\nx = hero:frames(2):frame(2)\n',
    'hero:frames(4)\nhero:animation("walk", [1, 2], 0.5)\nhero:animation("all", [4, 3, 2, 1, 2, 3])\n',
    'hero:frames(4)\nname = "run"\nhero:animation(name, [1, 2], 8)\nhero:play(name)\n',
    'hud = game:hud()\nicon = hud:image("hero_sheet.png", 30, 30)\nicon:frames(4, 2)\nicon:frame(8)\n',
    'w = tgame.world("x")\nbadge = w:hud():image("hero_sheet.png", 40, 40)\nbadge:frames(4, 2)\nbadge:animation("spin", [5, 6], 4)\nbadge:play("spin")\n',
]
FRAMES_BAD = [
    ('hero:frames(0)\n', "hero:frames needs how many frames across, then how many down (1 if you leave it out), as whole numbers from 1"),
    ('hero:frames(4, -1)\n', "hero:frames needs how many frames across"),
    ('hero:frames(2.5)\n', "hero:frames needs how many frames across"),
    ('hero:frames(4)\nhero:frame(0)\n', "Frames are numbered from 1 (the top left one), so there's no frame 0."),
    ('hero:frames(4)\nhero:animation("walk", [0, 1, 2], 10)\n', "so there's no frame 0."),
    ('hero:frames(4)\nhero:animation("walk", [1, 1.5], 10)\n', "so there's no frame 1.5."),
    ('hero:frames(4)\nhero:animation("walk", [], 10)\n', "An animation needs at least one frame"),
    ('hero:frames(4)\nhero:animation("walk", [1, 2], 0)\n', "hero:animation's last input is how many frames a second, above 0"),
    ('hero:frames(4)\nhero:animation("walk", [1, 2], -3)\n', "hero:animation's last input is how many frames a second, above 0"),
    ('hero:frames(4)\nhero:animation(3, [1, 2], 10)\n', "hero:animation needs a name as text first"),
    ('hero:frames(4)\nhero:animation("walk", 4, 10)\n', "hero:animation needs its frames as a list"),
    ('hero:frames(4)\nhero:animation("walk", [1, 2], 10)\nhero:play("wlak")\n',
     'There\'s no animation called "wlak". This program makes "walk". Did you mean "walk"?'),
    ('hero:frames(4)\nhero:play("walk")\n', 'There\'s no animation called "walk". Make it first, like hero:animation("walk", [1, 2, 3, 4], 10)'),
    ('hero:frames(4)\nname = "run"\nhero:animation(name, [1, 2], 8)\nhero:play("walk")\n', 'There\'s no animation called "walk". This program makes "run".'),
    ('hero:frames(4)\nhero:animation("walk", [1, 2], 10)\nhero:play("walk", "once")\n', "hero:play's second input is true"),
    ('hero:frames(4)\nfunc landed(a, b, c):\n    say a\nhero:on_done(landed)\n', "landed() needs 3 inputs, but hero:on_done gives it 2 inputs"),
    ('hero:frames(4)\nhero:on_done(landed)\n', "I don't know what 'landed' is."),
    ('hero:frames(4)\nhero:on_done(landed())\nfunc landed():\n    say 1\n', "Pass the function's name without brackets"),
    ('hero:animate("walk")\n', "A sprite doesn't have :animate. Use :play instead."),
    ('hero:sprite_sheet(4)\n', "A sprite doesn't have :sprite_sheet. Use :frames instead."),
    ('hero:on_finish(done)\n', "A sprite doesn't have :on_finish. Use :on_done instead."),
    ('hero:frames(4, 2, 1)\n', "sprite:frames got the wrong number of inputs (3)."),
    ('hero:play()\n', "sprite:play got the wrong number of inputs (0)."),
    ('hero:animation("walk")\n', "sprite:animation got the wrong number of inputs (1)."),
    ('w = tgame.world("x")\nt = w:box(0, 0, 0)\nt:frames(4)\n', "An object doesn't have :frames."),
]


def headless(name, code, frames=0, events=None):
    """Runs a tgame program with no window (headless.py): (exit code, its say lines, stderr, every frame's changes),
    or None with --runtime (headless.py needs tuff.py)."""
    if RUNTIME:
        return None
    folder = os.path.join(OUT, "frames")
    path = os.path.join(folder, name + ".tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    out = os.path.join(folder, name + ".json")
    args = [sys.executable, os.path.join(HERE, "headless.py"), path, out, str(frames)]
    if events:
        with open(os.path.join(folder, name + ".events.json"), "w", encoding="utf-8") as f:
            json.dump(events, f)
        args.append(os.path.join(folder, name + ".events.json"))
    p = subprocess.run(args, cwd=folder, capture_output=True, text=True, encoding="utf-8", timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return p.returncode, [x for x in p.stdout.splitlines() if x.strip()], p.stderr, read_json(out) or []


def frame_sets(cmds, node, keys=("cells", "cell", "play", "attrs")):
    """[(the frame it went in, its changes)] for one object, keeping only these keys."""
    out, frame = [], 0
    for cmd in cmds:
        if cmd[0] == "f":
            frame = cmd[1] + 1
        elif cmd[0] == "s" and cmd[1] == node and any(k in cmd[2] for k in keys):
            out.append((frame, {k: v for k, v in cmd[2].items() if k in keys}))
    return out


def t_frames(c):
    """1.5.0, headless (no window): sprite sheets. Tuff Engine's preview (--scene) sends the grid, the frame and the
    animation playing; a run (headless.py, 1/60 s a frame) plays, carries on, plays once and runs on_done, stops and
    pauses; the mistakes a run finds, and those the checker is sure of; the page's flip.js in Node; the editor's docs;
    the guide's example; and Sprite Studio's "Use in code"."""
    folder = os.path.join(OUT, "frames")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(GAMES, "hero_sheet.png"), "rb") as f, open(os.path.join(folder, "hero_sheet.png"), "wb") as g:
        g.write(f.read())
    # Tuff Engine's preview: what the setup sends
    src = os.path.join(folder, "frames_scene.tuf")
    with open(src, "w", encoding="utf-8") as f:
        f.write(FRAMES_SCENE)
    code, out, err, d, secs = scene(src)
    c.check(code == 0 and d.get("stopped") == "loop" and d.get("error") is None, f"--scene runs the setup ({secs:.1f} s)", (d.get("stopped"), d.get("error"), err[-300:]))
    batch = d.get("batch") or []
    things = {t.get("var"): t for t in d.get("things", [])}
    ids = {name: (things.get(name, {}).get("ids") or [None])[0] for name in ("hero", "coin", "badge", "plain")}
    sets = {name: [cmd[2] for cmd in batch if cmd[0] == "s" and cmd[1] == i] for name, i in ids.items()}
    hero = sets["hero"][-1] if sets["hero"] else {}
    c.check(hero.get("cells") == [4, 2] and hero.get("cell") == 1 and hero.get("play") == [[1, 2, 3, 4], 10, True]
            and hero.get("w") == 64 and hero.get("h") == 64 and hero.get("sx") == -1,
            "hero: 4 x 2 frames, walk playing at 10 a second, one frame 64 wide (and 64 high), and :flip still mirrors it", hero)
    coin = sets["coin"][-1] if sets["coin"] else {}
    c.check(coin.get("cells") == [4, 2] and coin.get("cell") == 6 and coin.get("play") is None and coin.get("w") == 32 and coin.get("h") == 32,
            "coin (no width given): frame 6, one frame's own size (32 x 32)", coin)
    badge = sets["badge"][-1] if sets["badge"] else {}
    c.check(things.get("badge", {}).get("layer") == "hud" and badge.get("cells") == [4, 1] and badge.get("w") == 16 and badge.get("h") == 32,
            "badge on the HUD: 4 frames in a row, 16 wide (and 32 high, the shape of one frame)", badge)
    plain = [cmd for cmd in batch if cmd[0] in ("c", "s") and cmd[1] == ids["plain"]]
    c.check(plain and not any(k in cmd[-1] for cmd in plain for k in ("cells", "cell", "play", "pic", "sized")),
            "a picture never cut into frames sends what it always did", plain)
    want = {"cells": [4, 2], "frame": 1, "playing": "walk", "loop": True,
            "animations": {"walk": {"frames": [1, 2, 3, 4], "fps": 10}, "jump": {"frames": [5, 6, 7, 8], "fps": 12}}}
    c.check(things.get("hero", {}).get("frames") == want and things.get("coin", {}).get("frames", {}).get("frame") == 6
            and "frames" not in things.get("plain", {}), "the dump has each sheet's grid, frame and animations", things.get("hero", {}).get("frames"))
    # Mistakes, when it runs
    for i, (more, line, msg) in enumerate(FRAMES_RUN_ERRORS):
        path = os.path.join(folder, f"run_error{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write('mention tgame\ngame = tgame.window("x")\nhero = game:image("hero_sheet.png", 100, 100, 64)\nhero:frames(4, 2)\n' + more)
        e = scene(path)[3].get("error") or {}
        c.check(e.get("line") == line and msg in e.get("message", ""), f"running it: {msg[:70]}", e)
    # A run, with no window
    run = headless("frames_run", FRAMES_RUN)
    if run is None:
        c.check(True, "--runtime: skipped the headless run (it needs tuff.py)")
    else:
        rc, said, err, cmds = run
        c.check(rc == 0 and "Tuff error" not in err and "Traceback" not in err, "the headless run ends cleanly", err[-500:])
        c.check(said == ["start 1", "at 0.25 3", "jump 5", "done jump 8 at 0.45", "then 1", "stopped 4", "still 4", "before pause 1",
                         "while paused 1", "end 5"],
                "walk carries on when played every frame, jump plays once then on_done runs, stop holds, a pause holds (the frames it said)", said)
        hero_id = next((cmd[1] for cmd in cmds if cmd[0] == "c" and cmd[3] == "image"), None)
        got = frame_sets(cmds, hero_id)
        walk, jump = [[1, 2, 3, 4], 10, True], [[5, 6, 7, 8], 20, False]
        c.check([g[1].get("play", "-") for g in got] == [walk, jump, walk, None, walk],
                "the page hears of each play once (not every frame), the end of the jump, the stop and the walk again", got)
        c.check(len(got) == 5 and got[0][0] == 0 and got[1][0] == 16 and got[2][0] == 28 and got[2][1].get("cell") == 8 and got[3][1].get("cell") == 4,
                "on the frames it happened in: the jump at 0.25 s, its end at 0.45 s (on frame 8), the stop on frame 4", got)
        paused = [(f, cmd[1], cmd[2]["attrs"]) for f, cmd in enumerate_frames(cmds) if cmd[0] == "s" and "attrs" in cmd[2]]
        c.check([p[2] for p in paused] == [{"data-paused": True}] * 2 + [{"data-paused": False}] * 2 and {p[1] for p in paused} == {1, 3}
                and paused[0][0] == 73 and paused[2][0] == 102,
                "pausing tells the game's canvas and the HUD's (data-paused), and resuming takes it off again", paused)
        rc, said, err, cmds = headless("frames_still", 'mention tgame\ngame = tgame.window("x")\nb = game:box(1, 2)\nb:speed(10, 0)\n'
                                                       'func step(dt):\n    nil\ngame:every_frame step\ngame:pause()\n', frames=20)
        c.check(rc == 0 and not any(cmd[0] == "s" and "attrs" in cmd[2] for cmd in cmds),
                "a game without sprite sheets sends nothing new when it pauses", [cmd for cmd in cmds if cmd[0] == "s"][:6])
    # The checker
    for i, src in enumerate(FRAMES_GOOD):
        path = os.path.join(folder, f"good{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write('mention tgame\ngame = tgame.window("x")\nhero = game:image("hero_sheet.png", 100, 100, 64)\n' + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"--check accepts: {' / '.join(src.strip().splitlines())[:80]}", (p.stdout + p.stderr)[:400])
    for i, (src, want) in enumerate(FRAMES_BAD):
        path = os.path.join(folder, f"bad{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write('mention tgame\ngame = tgame.window("x")\nhero = game:image("hero_sheet.png", 100, 100, 64)\n' + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 1 and want in p.stderr, f"--check catches: {want[:80]}", p.stderr[:400])
    # A file of the program's own could make more animations: then :play's name isn't checked
    with open(os.path.join(folder, "moves.tuf"), "w", encoding="utf-8") as f:
        f.write('func add_moves(who):\n    who:animation("walk", [1, 2], 10)\n')
    path = os.path.join(folder, "own_file.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write('mention tgame\nimport moves\ngame = tgame.window("x")\nhero = game:image("hero_sheet.png", 100, 100, 64)\n'
                'hero:frames(4)\nhero:play("walk")\n')
    p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check("no animation called" not in p.stderr, "with a file of its own imported, --check doesn't say :play's animation is missing", p.stderr[:300])
    # The page's side, in Node
    try:
        p = subprocess.run(["node", os.path.join(HERE, "flip_test.mjs"), os.path.join(REPO, "tuff_view_web", "flip.js")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        seen = json.loads(p.stdout or "{}")
    except FileNotFoundError:
        seen = None
        c.check(True, "Node isn't installed: skipped flip.js and the editor's docs")
    if seen is not None:
        c.check(seen.get("whole") is None and seen.get("cell6") == [32, 32, 32, 32] and seen.get("not_loaded") is None
                and seen.get("own_frame") == [10, 20, 30, 40],
                "flip.js: frame 6 of 4 x 2 is the second row's second (32, 32); a picture not cut (or not loaded) is drawn whole", seen)
        c.check([seen.get(k) for k in ("start", "at_025", "paused", "after_pause")] == [1, 3, 3, 1] and seen.get("rect_025") == [64, 0, 32, 32]
                and seen.get("dirty_while_paused") is False,
                "flip.js: walk at 10 a second shows frame 3 at 0.25 s, holds still while paused, and goes on after", seen)
        c.check([seen.get(k) for k in ("jump_start", "jump_mid", "jump_end", "playing_after_jump", "after_end")] == [5, 7, 8, 0, 8],
                "flip.js: a jump played once stays on its last frame and stops stepping", seen)
        c.check(seen.get("after_gap") == 2, "flip.js: after a 5 s gap (a hidden window) it steps 0.1 s, not 5", seen.get("after_gap"))
        c.check(seen.get("info") == {"playing": 2, "shown": [[2, 2], [3, 1]]} and seen.get("info_gone") == {"playing": 0, "shown": []},
                "flip.js: its stats list the sheets and their frames, and let removed ones go", (seen.get("info"), seen.get("info_gone")))
        # engine.js itself, in a pretend page: tgame's commands in, drawImage calls out
        p = subprocess.run(["node", os.path.join(HERE, "engine_flip_test.mjs"), os.path.join(REPO, "tuff_view_web", "engine.js")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        try:
            page = json.loads(p.stdout or "{}")
        except ValueError:
            page = {}
        src = lambda name: (page.get(name) or [None] * 9)[1:5]  # noqa: E731 (the part of the picture it drew)
        c.check(page.get("errors") == [] and len(page.get("whole") or []) == 5, "engine.js draws a picture never cut into frames whole, as before",
                (page.get("whole"), page.get("errors"), p.stderr[-300:]))
        c.check(src("cell6") == [32, 32, 32, 32] and (page.get("cell6") or [0] * 9)[7:] == [64, 64],
                "engine.js draws frame 6's part of the picture, 64 x 64 on screen", page.get("cell6"))
        c.check(src("walk_025") == [64, 0, 32, 32] and src("after_pause") == [96, 0, 32, 32] and page.get("paused_same") is True
                and page.get("paused_draws") == 1, "engine.js steps the walk to frame 3, holds still (drawing nothing new) while the canvas is "
                "paused, then goes on to frame 4", page)
        c.check(src("stopped") == [64, 32, 32, 32] and page.get("stats") == {"playing": 0, "shown": [[2, 7]]},
                "engine.js shows the frame a stop gives (7), and its stats say so", (page.get("stopped"), page.get("stats")))
        # The editor's hover docs and completions
        p = subprocess.run(["node", "-e", LOAD_LANG, os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        t = json.loads(p.stdout)
        docs = t["methods"]
        c.check(all(docs.get(m, ["", ""])[1].startswith("tgame") for m in ("frames", "animation", "on_done"))
                and all(m in t["games"] and m not in t["plain"] for m in ("frames", "animation", "on_done")),
                "frames, animation and on_done have tgame hover docs, offered after ':' in tgame files only", {m: docs.get(m) for m in ("frames", "animation", "on_done")})
        c.check("hero:frame(3)" in docs["frame"][1] and docs["frame"][0] == "game:frame()" and 'hero:play("jump", false)' in docs["play"][1]
                and docs["play"][1].startswith("Plays an animation on a line") and "hero:stop()" in docs["stop"][1] and docs["stop"][0] == "spinner:stop",
                "frame, play and stop keep their docs and add a sprite sheet's", {m: docs[m] for m in ("frame", "play", "stop")})
        import tuff_tgame
        sprite = sorted(tuff_tgame.tables()["kinds"]["sprite"])
        c.check(not [m for m in sprite if m not in docs], "every sprite method has hover docs", [m for m in sprite if m not in docs])
    # The guide's example: --check, and a headless run where Space jumps and right walks
    guide = open(os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md"), encoding="utf-8").read()
    start = guide.find("\n#### Animated pictures (sprite sheets)")
    blocks = re.findall(r"```tuff\n(.*?)```", guide[start:guide.find("\n#### ", start + 1)], re.S) if start >= 0 else []
    c.check(len(blocks) == 1 and ":frames(" in blocks[0], "the guide's tgame section has a sprite sheet example", len(blocks))
    if blocks:
        path = os.path.join(folder, "guide_sheet.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(blocks[0])
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0, "the guide's sprite sheet example passes --check", (p.stdout + p.stderr)[:400])
        run = headless("guide_sheet", blocks[0], frames=90, events={"10": [{"type": "keydown", "code": "Space"}], "12": [{"type": "keyup", "code": "Space"}],
                                                                    "40": [{"type": "keydown", "code": "ArrowRight"}], "70": [{"type": "keyup", "code": "ArrowRight"}]})
        if run is not None:
            rc, said, err, cmds = run
            hero_id = next((cmd[1] for cmd in cmds if cmd[0] == "c" and cmd[3] == "image"), None)
            plays = [(f, s.get("play", "-"), s.get("cell")) for f, s in frame_sets(cmds, hero_id)]
            jump, walk = [[5, 6, 7, 8], 12, False], [[1, 2, 3, 4], 10, True]
            c.check(rc == 0 and "Tuff error" not in err, "and runs headless for 90 frames", err[-400:])
            c.check(plays == [(0, None, 1), (10, jump, None), (30, None, 1), (40, walk, None), (70, None, 1)],
                    "standing on frame 1, Space jumps once (landed after its 4 frames at 12 a second: 20 frames), right walks, "
                    "letting go stands (and standing every frame sends nothing new)", plays)
    # Sprite Studio's "Use in code" for a game: the sheet, cut into frames and played (not a timer swapping pictures)
    panel = open(os.path.join(REPO, "tuffcode", "plugins", "sprite-studio", "panel.js"), encoding="utf-8").read()
    c.check(":frames(${n})" in panel and ":animation(${q(info.name)}, ${list}, ${fps})" in panel and ":play(${q(info.name)})" in panel,
            "Sprite Studio writes :frames, :animation and :play for a game", None)
    code = 'walk = game:image("walk_sheet.png", 300, 200, 64)\nwalk:frames(4)\nwalk:animation("walk", [1, 2, 3, 4], 8)\nwalk:play("walk")\n'
    with open(os.path.join(folder, "walk_sheet.png"), "wb") as f, open(os.path.join(GAMES, "hero_sheet.png"), "rb") as g:
        f.write(g.read())
    path = os.path.join(folder, "studio.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write('mention tgame\n\ngame = tgame.window("Walk", 600, 400)\n' + code)
    p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.returncode == 0, "the code it writes passes --check", (p.stdout + p.stderr)[:300])


def enumerate_frames(cmds):
    """(the frame each command went in, the command), leaving out the frame markers."""
    frame = 0
    for cmd in cmds:
        if cmd[0] == "f":
            frame = cmd[1] + 1
        else:
            yield frame, cmd


def t_frames_window(c):
    """1.5.0, in a real window: games/frames.tuf shows the frame tgame says it shows (each frame of hero_sheet.png is its
    own colour), the page steps a walk by itself while Python's frame() follows the same clock, a jump plays once
    and on_done runs, and a pause holds the page's frames still."""
    r = play("frames", game("frames.tuf"), [
        {"at": 0.4, "call": "hold"}, {"at": 0.7, "shot": "frames_hold.png"},
        {"at": 0.8, "call": "walk"}, {"at": 1.3, "dump": "frames_walk1.json"}, {"at": 1.55, "dump": "frames_walk2.json"},
        {"at": 1.8, "dump": "frames_walk3.json"},
        {"at": 2.0, "call": "pause"}, {"at": 2.2, "dump": "frames_paused1.json"}, {"at": 3.2, "dump": "frames_paused2.json"},
        {"at": 3.3, "shot": "frames_paused.png"}, {"at": 3.4, "call": "resume"},
        {"at": 3.6, "call": "jump"}, {"at": 4.5, "dump": "frames_jumped.json"}, {"at": 4.6, "shot": "frames_jumped.png"},
        {"at": 4.8, "close": True}])
    first_line_is_notice(c, r)
    clean_exit(c, r)
    hero_box = (0.4, 0.3, 0.6, 0.7)
    hold = r.shots.get("frames_hold.png")
    c.check(hold and color_share(hold, hexrgb(FRAME_COLORS[1]), 40, hero_box) > 0.4,
            "hero:frame(2) shows frame 2 (orange) and only that part of the picture", hold and color_share(hold, hexrgb(FRAME_COLORS[1]), 40, hero_box))
    c.check(hold and color_share(hold, hexrgb(FRAME_COLORS[5]), 40, (0.02, 0.04, 0.16, 0.22)) > 0.2,
            "the HUD's coin shows frame 6 (blue)", hold and color_share(hold, hexrgb(FRAME_COLORS[5]), 40, (0.02, 0.04, 0.16, 0.22)))

    def frames_of(name):
        d = r.dumps.get(name, {})
        py = {f[0]: f[1] for f in d.get("frames", [])}
        page = {s[0]: s[1] for s in ((d.get("page") or {}).get("flip") or {}).get("shown", [])}
        return py, page

    walk = [frames_of(f"frames_walk{i}.json") for i in (1, 2, 3)]
    hero_id = min((k for py, _ in walk for k in py), default=None)
    pairs = [(py.get(hero_id), page.get(hero_id)) for py, page in walk]
    order = [1, 2, 3, 4]
    near = all(a in order and b in order and (order.index(a) - order.index(b)) % 4 in (0, 1, 3) for a, b in pairs)
    c.check(near and len({p[1] for p in pairs}) >= 2, "walking, the page steps by itself and Python's hero:frame() agrees (within a frame)", pairs)
    p1, p2 = frames_of("frames_paused1.json"), frames_of("frames_paused2.json")
    c.check(p1[1].get(hero_id) is not None and p1[1].get(hero_id) == p2[1].get(hero_id) and p1[0].get(hero_id) == p2[0].get(hero_id),
            "paused for a second, the page's frame and Python's stay where they were", (p1, p2))
    c.check(any(line.startswith("done jump") for line in r.lines), "the jump played once and on_done ran", r.lines)
    jumped = frames_of("frames_jumped.json")
    shot = r.shots.get("frames_jumped.png")
    c.check(jumped[0].get(hero_id) == 8 and jumped[1].get(hero_id) == 8 and shot and color_share(shot, hexrgb(FRAME_COLORS[7]), 40, hero_box) > 0.4,
            "after the jump it stays on frame 8 (pink), in Python, in the page and on screen", jumped)


# ---------------------------------------------------------------- numbers and library calls (1.5.0)

TOO_BIG_SUM = "That number is too big to work out. Whole numbers can be any size"
# Maths that stopped with a Python traceback (OverflowError) before 1.5.0, or with "round() failed: cannot convert
# float infinity to integer" and the like: (code, (line, column, how the error starts)), the same in both runtimes.
NUMBERS_ERRORS = [
    ("say 10 ^ 400 / 3", (1, 14, TOO_BIG_SUM)), ("say 2 ^ 99999 * 1.5", (1, 15, TOO_BIG_SUM)),
    ("x = 2 ^ 99999\nx *= 1.5", (2, 1, TOO_BIG_SUM)), ("x = 2 ^ 99999\nx += 0.5", (2, 1, TOO_BIG_SUM)),
    ("x = 10 ^ 400\nx /= 3", (2, 1, TOO_BIG_SUM)), ("x = 10 ^ 400\nsay x - 0.5", (2, 7, TOO_BIG_SUM)),
    ("x = 10 ^ 400\nsay x % 1.5", (2, 7, TOO_BIG_SUM)), ("x = 10 ^ 400\nsay 1.5 % x", (2, 9, TOO_BIG_SUM)),
    ("x = 10 ^ 400\nsay x + 0.5 * 2", (2, 7, TOO_BIG_SUM)), ("say 10.0 ^ 400", (1, 10, TOO_BIG_SUM)),
    ("x = 10 ^ 400\nsay x ^ 0.5", (2, 7, TOO_BIG_SUM)), ('say "Total: " + 10 ^ 400 / 3', (1, 26, TOO_BIG_SUM)),
    ("func f(n):\n    return n * 1.5\nsay f(2 ^ 99999)", (2, 14, TOO_BIG_SUM)),
    ('say f"{2 ^ 99999 * 1.5:0.00}"', (1, 18, TOO_BIG_SUM)), ("n = 10 ^ 400\nfor i in [1, 2]:\n    n /= 2", (3, 5, TOO_BIG_SUM)),
    ("big = [10 ^ 400]\nbig[0] /= 3", (2, 1, TOO_BIG_SUM)), ('d = {"x": 10 ^ 400}\nd["x"] *= 1.5', (2, 1, TOO_BIG_SUM)),
    ("say [2 ^ 99999 * 0.5]", (1, 16, TOO_BIG_SUM)), ("say -(2 ^ 99999) / 7", (1, 18, TOO_BIG_SUM)),
    ("say 0 ^ -1", (1, 7, "0 ^ -1 has no answer: it's the same as dividing by zero.")),
    ("say 0.0 ^ -2.5", (1, 9, "0 ^ -2.5 has no answer")),
    ("say round(10.0 ^ 308 * 10)", (1, 10, "That number is too big for round() to work out.")),
    ("say int(10.0 ^ 308 * 10)", (1, 8, "That number is too big for int() to work out.")),
    ("say floor(10.0 ^ 308 * 10)", (1, 10, "That number is too big for floor() to work out.")),
    ("say sqrt(2 ^ 99999)", (1, 9, "That number is too big for sqrt() to work out.")),
    ("say sum(2 ^ 99999, 0.5)", (1, 8, "That number is too big for sum() to work out.")),
    ("say average(2 ^ 99999, 1)", (1, 12, "That number is too big for average() to work out.")),
    ("say range(2 ^ 99999)", (1, 10, "That number is too big for range() to work out.")),
    ("wait(2 ^ 99999)", (1, 5, "That number is too big for wait() to work out.")),
    ("say random(0.5, 2 ^ 99999)", (1, 11, "That number is too big for random() to work out.")),
    ("say sin(2 ^ 99999)", (1, 8, "That number is too big for sin() to work out.")),
    ("say sin(10.0 ^ 308 * 10)", (1, 8, "sin(inf) has no answer.")),
    ("x = [1, 2]\nsay x[2 ^ 99999]", (2, 6, "That position is far outside this list (it has 2 items, starting at 0).")),
    ('say "ab" * 2 ^ 99999', (1, 10, "That text would be far too long to make.")),
]
# Big numbers that work: whole numbers of any size, every digit of them, and catch getting the message.
NUMBERS_PROGRAM = '''say 2 ^ 100
say text(10 ^ 25, 2)
say text(-7, 3)
say len(text(2 ^ 99999))
say text(2 ^ 99999, 1):ends(".0")
say "" * 2 ^ 99999 + "empty"
say len("ab" * 0)
say number("1.0e999") is err
say num("2.5e3")
say 2 ^ 99999 > 1.5
say 2 ^ 99999 / 2 ^ 99998
say 2 ^ -99999
say min(2 ^ 99999, 0.5)
say log(2 ^ 99999, 2)
say (2 ^ 99999) % 7
say round(2 ^ 99999 * 1) == 2 ^ 99999
say f"{2 ^ 70:000}"
try:
    say 10 ^ 400 / 3
catch problem:
    say problem:starts("That number is too big to work out.")
total = 0
for i in range(1, 3):
    try:
        total += 10 ^ 400 / 3
    catch:
        total += 1
say total
'''
NUMBERS_OUTPUT = ["1267650600228229401496703205376", "10000000000000000000000000.00", "-7.000", "30103", "true", "empty", "0",
                  "true", "2500", "true", "2", "0", "0.5", "99999", "1", "true", "1180591620717411303424", "true", "3"]
# The checker: a sum of numbers written in the program that's too big is certain to stop the program (code, what
# --check says first, or "OK"). In try: it may be on purpose, and with a variable only the run can tell.
NUMBERS_CHECKS = [
    ("say 10 ^ 400 / 3", (1, 14, TOO_BIG_SUM)),
    ("x = 2 ^ 99999 * 1.5 + 1", (1, 15, TOO_BIG_SUM)),
    ("func half():\n    return -(10 ^ 400) / 2\nsay half()", (2, 24, TOO_BIG_SUM)),
    ('say "Big: " + 10.0 ^ 400', (1, 20, TOO_BIG_SUM)),
    ("try:\n    say 10 ^ 400 / 3\ncatch problem:\n    say problem", "OK"),
    ("say 2 ^ 99999\nsay 10 ^ 300 * 10\nsay 1 / 3 * 2 ^ 1000\nsay 2 ^ -5000", "OK"),
    ("x = 10 ^ 400\nsay x / 3", "OK"),
    ("say 2 ^ 2000000 * 1.5", "OK"),  # (too long to work out while checking: the run says so)
]


def numbers_runtime(slow):
    """A tuff.Interpreter for the tree walker (slow) or the compiled runtime."""
    import tuff
    old = os.environ.pop("TUFF_SLOW", None)
    if slow:
        os.environ["TUFF_SLOW"] = "1"
    try:
        return tuff.Interpreter("", HERE)
    finally:
        os.environ.pop("TUFF_SLOW", None)
        if old is not None:
            os.environ["TUFF_SLOW"] = old


def numbers_run(code, slow, names=None):
    """Runs code in this process: (line, column, message) of its Tuff error, or None. names: values to start with."""
    import tuff
    interp = numbers_runtime(slow)
    interp.globals.vars.update(names or {})
    try:
        interp.run_block(tuff.Parser(tuff.tokenize(code)).program(), interp.globals)
    except tuff.TuffError as err:
        return err.line, err.col, err.msg
    return None


def numbers_library(rt):
    """A headless stand-in for a library: a window and a sprite with methods (new functions for each object, as tgame
    makes them), a method of a Python object, a function wrapped like tdraw's guard, and a library function."""
    import functools
    import tuff
    seen = {"frames": 0, "x": 0}

    class Box:
        def x(self):
            return seen["x"]

    def frame():
        seen["frames"] += 1
        return True

    def move(dx, dy=0):
        seen["x"] += dx

    def guarded(fn):
        @functools.wraps(fn)
        def run(*args):
            return fn(*args)
        return run

    def make(text, color="white"):
        return text

    return seen, {"game": rt.native("window", {"frame": frame}), "player": rt.native("sprite", {"move": move, "x": Box().x}),
                  "pen": rt.native("pen", {"go": guarded(lambda steps: steps)}),
                  "lib": tuff.Module("lib", {"make": rt.builtin("lib.make", make)})}


def t_numbers(c):
    """1.5.0's two rough edges. Numbers: a sum too big for a decimal (10 ^ 400 / 3, 2 ^ 99999 * 1.5) and the maths
    built-ins given one stop with a Tuff error on the right line and column in both runtimes (they were a Python
    traceback), whole numbers show every digit, and --check finds a too-big sum of numbers written in the program.
    Library calls: how many inputs a library's function takes is worked out once (fits_inputs), with the same answers
    as inspect.signature and the same messages, and game:frame() and player:move() are several times quicker."""
    import functools
    import inspect
    import tuff
    for code, (line, col, msg) in NUMBERS_ERRORS:
        got = [numbers_run(code, slow) for slow in (True, False)]
        c.check(got[0] == got[1] and got[0] and got[0][:2] == (line, col) and got[0][2].startswith(msg),
                f"{code.splitlines()[-1]!r} stops on line {line}, column {col}: {msg[:50]}", got)
    folder = os.path.join(HERE, "out", "numbers")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "numbers.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(NUMBERS_PROGRAM)
    for slow in (True, False):
        env = {k: v for k, v in os.environ.items() if k != "TUFF_SLOW"}
        if slow:
            env["TUFF_SLOW"] = "1"
        p = subprocess.run(tuff_cmd() + [path], capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
                           stdin=subprocess.DEVNULL)
        got = p.stdout.splitlines()
        c.check(p.returncode == 0 and got[:len(NUMBERS_OUTPUT)] == NUMBERS_OUTPUT,
                f"{'the tree walker' if slow else 'the compiled runtime'}: big whole numbers work and show every digit, and catch gets the message",
                [(i + 1, want, got[i] if i < len(got) else None) for i, want in enumerate(NUMBERS_OUTPUT)
                 if i >= len(got) or got[i] != want][:4] or p.stderr[-400:])
    bad = os.path.join(folder, "too_big.tuf")
    with open(bad, "w", encoding="utf-8") as f:
        f.write("say 10 ^ 400 / 3\n")
    p = subprocess.run(tuff_cmd() + [bad], capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
    c.check(p.returncode == 1 and "Traceback" not in p.stderr and p.stderr.startswith(f"Tuff error on line 1: {TOO_BIG_SUM}")
            and "               ^" in p.stderr, "tuff.py: say 10 ^ 400 / 3 is a Tuff error with the line and a ^ under the /", p.stderr[-500:])
    # the checker
    p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    c.check(p.stdout.strip() == "OK", "--check accepts the big numbers program", (p.stdout + p.stderr)[:600])
    for code, want in NUMBERS_CHECKS:
        problems = tuff.Checker(tuff.Parser(tuff.tokenize(code)).program(), folder).run()
        if want == "OK":
            c.check(not problems, f"--check says nothing about {code.splitlines()[-1]!r}", problems)
        else:
            run = numbers_run(code, False)
            c.check(problems and problems[0][:2] == want[:2] and problems[0][2].startswith(want[2]) and run and run[:2] == want[:2],
                    f"--check on {code.splitlines()[-1]!r}: line {want[0]}, column {want[1]} (where the run stops too)", (problems, run))
    # fits_inputs: the same answers as inspect.signature(fn).bind(...), for every shape a library's function can have
    def by_inspect(fn, n):
        try:
            inspect.signature(fn).bind(*([None] * n))
            return True
        except TypeError:
            return False
        except ValueError:
            return None

    class K:
        def m0(self): pass
        def m2(self, a, b=1): pass
        def mv(self, *a): pass
        def mk(self, *, k): pass
        def mkd(self, *, k=1): pass
        @classmethod
        def cm(cls, a): pass

    def wrap(fn):
        @functools.wraps(fn)
        def run(*args):
            return fn(*args)
        return run

    def tagged(a, b):
        pass

    def bare():
        pass

    tagged.note = "an attribute of its own"
    late = lambda a, b: 0  # noqa: E731
    late.__defaults__ = (5,)
    shapes = [lambda: 0, lambda a: 0, lambda a, b=2: 0, lambda *a: 0, lambda a, *b: 0, lambda a, /, b: 0, lambda a, *, k: 0,
              lambda a, *, k=1: 0, lambda a=1, b=2, c=3: 0, lambda **kw: 0, lambda a, **kw: 0, K().m0, K().m2, K().mv, K().mk,
              K().mkd, K().cm, K.m2, wrap(lambda a, b=1: 0), wrap(K().m2), wrap(wrap(lambda a: 0)), tagged, late, bare,
              types_method(bare), len, print, functools.partial(lambda a, b: 0, 1), [].append, int, K()]
    differ = [(fn, n, by_inspect(fn, n), tuff.fits_inputs(fn, n)) for fn in shapes for n in range(5)
              if tuff.fits_inputs(fn, n) not in (None, by_inspect(fn, n)) or tuff.accepts(fn, n) != (by_inspect(fn, n) is not False)]
    known = sum(1 for fn in shapes if tuff.fits_inputs(fn, 1) is not None)
    c.check(not differ and known >= 24, f"fits_inputs agrees with inspect.signature on {len(shapes)} kinds of function, "
            f"{known} of them without asking it", differ[:4])
    # Library objects' methods and library functions, in both runtimes: right answers, the same messages for a wrong
    # number of inputs, and inspect.signature isn't asked (it was, on every call)
    loop = "i = 0\nwhile i < 300:\n    game:frame()\n    player:move(2)\n    say lib.make(\"hi\") + pen:go(3) + player:x()\n    i += 1\n"
    calls = []
    signature = inspect.signature
    inspect.signature = lambda *a, **k: calls.append(a) or signature(*a, **k)
    try:
        for slow in (True, False):
            mode = "the tree walker" if slow else "the compiled runtime"
            interp = numbers_runtime(slow)
            seen, names = numbers_library(interp.rt)
            interp.globals.vars.update(names)
            interp.console.say = lambda text, *a, **k: None
            del calls[:]
            interp.run_block(tuff.Parser(tuff.tokenize(loop)).program(), interp.globals)
            c.check(seen == {"frames": 300, "x": 600} and not calls,
                    f"{mode}: 1,500 library calls, and inspect.signature isn't asked once", (seen, len(calls)))
            wrong = [numbers_run(code, slow, numbers_library(numbers_runtime(slow).rt)[1]) for code in
                     ("x = 1\nplayer:move()", "game:frame(1)", "say lib.make()", "say pen:go(1, 2)", "player:move(1, 2, 3)")]
            c.check(wrong == [(2, 7, "sprite:move got the wrong number of inputs (0)."), (1, 5, "window:frame got the wrong number of inputs (1)."),
                              (1, 13, "lib.make() got the wrong number of inputs (0)."), (1, 8, "pen:go got the wrong number of inputs (2)."),
                              (1, 7, "sprite:move got the wrong number of inputs (3).")],
                    f"{mode}: a wrong number of inputs gives the same message as before, on the same line", wrong)
    finally:
        inspect.signature = signature
    # Speed: 200,000 library method calls with fits_inputs, and (a tenth as many) the old way, asking inspect each
    # time, less the time the same loop takes with no calls in it
    keep = tuff.fits_inputs

    def timed(slow, n, body, old=False):
        interp = numbers_runtime(slow)
        interp.globals.vars.update(numbers_library(interp.rt)[1])
        program = tuff.Parser(tuff.tokenize(f"i = 0\nwhile i < {n}:\n{body}    i += 1\n")).program()
        if old:
            tuff.fits_inputs = lambda fn, count: None
        try:
            t0 = time.perf_counter()
            interp.run_block(program, interp.globals)
            return time.perf_counter() - t0
        finally:
            tuff.fits_inputs = keep

    calls = "    game:frame()\n    player:move(1, 2)\n"
    for slow in (True, False):
        new = (timed(slow, 200_000, calls) - timed(slow, 200_000, "")) / 400_000 * 1e6
        old = (timed(slow, 20_000, calls, old=True) - timed(slow, 20_000, "")) / 40_000 * 1e6
        c.check(new * 2 < old, f"{'the tree walker' if slow else 'the compiled runtime'}: a library method call takes "
                f"{new:.2f} us, and {old:.2f} us asking inspect each time as before ({old / max(new, 0.01):.1f}x)", (new, old))


def types_method(fn):
    """fn as a method of some object (here one with no place for the object, which inspect can't make a signature for)."""
    import types
    return types.MethodType(fn, object())


# ---------------------------------------------------------------- 1.5.0: your own files as libraries (import money.tuf)

# A shop in five files: money.tuf and tax.tuf next to it, and fmt.tuf and table.tuf in libs/ (table.tuf imports fmt.tuf
# from there). (A library's name winning over a file is in MODULES_ERRORS: --check says so.)
MODULES_FILES = {
    "shop.tuf": '''import money.tuf
mention tax.tuf
import fmt.tuf
import table.tuf
import anims
say money.as_money(6.375)
say money.rate
say tax.total(10)
money.set_rate(0.5)
say money.rate
say tax.total(10)
rate = 99
say money.with_tax(10)
say money
say anims
say tax.money is money
say fmt.stars(3) + " " + table.row(["a", "b"])
prices = [3, 10, 7]
prices:sort(money.biggest_first)
say prices
func shout(t):
    return t:upper() + "!"
say money.apply(shout, "hi")
func later():
    import fmt.tuf
    return fmt.stars(2)
say later()
try:
    import extras.tuf
catch problem:
    say problem
say money.counter()
say money.counter()
say money.count
say f"{money.rate:0.00} and {rate}"
''',
    "money.tuf": '''# Money helpers for the shop
say "money.tuf starts"
rate = 0.2
count = 0

# 6.375 -> "$6.38"
func as_money(x):
    return f"{x:money}"

func with_tax(price):
    scratch = price * rate
    return price + scratch

func set_rate(new_rate):
    rate = new_rate

func biggest_first(n):
    return -n

func apply(f, x):
    return f(x)

func counter():
    count += 1
    return count
''',
    "tax.tuf": 'import money.tuf\nsay "tax.tuf starts"\nfunc total(x):\n    return money.as_money(money.with_tax(x))\n',
    "libs/fmt.tuf": 'func stars(n):\n    return "*" * n\n',
    "libs/table.tuf": 'import fmt.tuf\nfunc row(cells):\n    return fmt.stars(1) + " " + cells:join(" | ")\n',
}
MODULES_OUTPUT = ["money.tuf starts", "tax.tuf starts", "$6.38", "0.2", "$12.00", "0.5", "$15.00", "15", "<file money.tuf>",
                  "<library anims>", "true", "*** * a | b", "[10, 7, 3]", "HI!", "**",
                  "There's no extras.tuf next to shop.tuf (or in a libs folder there), and extras isn't one of Tuff's libraries "
                  "(anims, tgui, mtgui, tap, atgui, tgame, tdraw, tterm, tmusic).", "1", "2", "2", "0.50 and 99"]
MONEY = 'rate = 0.2\nfunc as_money(x):\n    return f"{x:money}"\nfunc show():\n    secret = 1\n    return secret\n'
# Mistakes: (the files, where the run stops: (the file it names, line, column, part of the message), or "OK", and part of
# what --check on shop.tuf says, or "OK" when only the run can know). shop.tuf is the program.
MODULES_ERRORS = [
    ({"shop.tuf": 'say 1\nimport nothere.tuf\n'}, ("", 2, 1, "There's no nothere.tuf next to shop.tuf (or in a libs folder there), and "
                                                         "nothere isn't one of Tuff's libraries"), None),
    ({"shop.tuf": 'import mony.tuf\n', "money.tuf": MONEY}, ("", 1, 1, "There's no mony.tuf next to shop.tuf (or in a libs folder there). "
                                                                   "Did you mean money (money.tuf)?"), None),
    ({"shop.tuf": 'import Money.tuf\n', "money.tuf": MONEY}, ("", 1, 1, "There's no Money.tuf next to shop.tuf (or in a libs folder there). "
                                                                    "Did you mean money (money.tuf)?"), None),
    ({"shop.tuf": 'import tgaem\n'}, ("", 1, 1, "Did you mean Tuff's library tgame?"), None),
    ({"shop.tuf": 'import random\n', "random.tuf": 'x = 1\n'}, ("", 1, 1, "random is one of Tuff's built-in functions, so a file called "
                                                                          "random.tuf can't be imported by that name."), None),
    ({"shop.tuf": 'import random\n'}, ("", 1, 1, "random is built into Tuff, so there's nothing to import: use it straight away, like random()."), None),
    ({"shop.tuf": 'import math\n'}, ("", 1, 1, "and Tuff doesn't need math: sqrt, floor"), None),
    ({"shop.tuf": 'import money.tuf\nsay 1\n', "money.tuf": 'import shop.tuf\n'},
     ("money.tuf", 1, 1, "shop.tuf and money.tuf import each other (shop.tuf → money.tuf → shop.tuf), so neither can finish loading."), None),
    ({"shop.tuf": 'import shop.tuf\n'}, ("", 1, 1, "shop.tuf imports itself."), None),
    ({"shop.tuf": 'import money.tuf\n', "money.tuf": 'x = 1\nimport tax.tuf\n', "tax.tuf": 'import money.tuf\n'},
     ("tax.tuf", 1, 1, "money.tuf and tax.tuf import each other (money.tuf → tax.tuf → money.tuf)"), None),
    ({"shop.tuf": 'import money.tuf\nimport tax.tuf\n', "money.tuf": 'import tax.tuf\n', "tax.tuf": 'import fmt.tuf\n', "fmt.tuf": 'import money.tuf\n'},
     ("fmt.tuf", 1, 1, "These files import each other in a circle (money.tuf → tax.tuf → fmt.tuf → money.tuf)"), None),
    ({"shop.tuf": 'import money.tuf\nmoney.go()\n', "money.tuf": 'func go():\n    import shop.tuf\n'},
     ("money.tuf", 2, 5, "shop.tuf and money.tuf import each other (shop.tuf → money.tuf → shop.tuf)"), "OK"),
    ({"shop.tuf": 'import money.tuf\n', "money.tuf": 'x = 1\nfunc f(:\n'},
     ("money.tuf", 2, 8, "Function inputs must be simple names."), "money.tuf has a mistake on line 2, so import money.tuf stops the program there: "
                                                                    "Function inputs must be simple names."),
    ({"shop.tuf": 'say 1\nimport money.tuf\n', "money.tuf": 'x = 1\ny = x / 0\n'}, ("money.tuf", 2, 7, "You can't divide by zero."), "OK"),
    ({"shop.tuf": 'import money.tuf\nsay money.half("a")\n', "money.tuf": 'func half(n):\n    return n / 2\n'},
     ("money.tuf", 2, 14, "Can't divide text and a number."), "OK"),
    ({"shop.tuf": 'import money.tuf\nfunc bad(x):\n    return x + nope\nsay money.apply(bad, 1)\n', "money.tuf": 'func apply(f, x):\n    return f(x)\n'},
     ("", 3, 16, "I don't know what 'nope' is."), None),
    ({"shop.tuf": 'import money.tuf\nsay money.as_mony(1)\n', "money.tuf": MONEY}, ("", 2, 10, "money.tuf doesn't have 'as_mony'. Did you mean 'as_money'?"), None),
    ({"shop.tuf": 'import money.tuf\nsay money.secret\n', "money.tuf": MONEY}, ("", 2, 10, "money.tuf doesn't have 'secret'. It has: as_money, rate, show."), None),
    ({"shop.tuf": 'import money.tuf\nsay money.as_money(1, 2)\n', "money.tuf": MONEY},
     ("", 2, 19, "as_money() needs 1 input, but got 2."), "money.as_money() needs 1 input, but got 2."),
    ({"shop.tuf": 'import money.tuf\nsay money.rate()\n', "money.tuf": MONEY},
     ("", 2, 15, "0.2 isn't a function, so it can't be called with ( )."), "money.rate is a number in money.tuf, not a function, so it can't be called"),
    ({"shop.tuf": 'import money.tuf\nmoney.rate = 2\n', "money.tuf": MONEY},
     ("", 2, 1, "money.rate belongs to money.tuf, so it can't be changed from this file. Give money.tuf a function that changes it, "
                "like func set_rate(new_rate):"), None),
    ({"shop.tuf": 'import money.tuf\nsay rate\n', "money.tuf": MONEY}, ("", 2, 5, "I don't know what 'rate' is."), None),
    ({"shop.tuf": 'total = 5\nimport money.tuf\nsay money.show_total()\n', "money.tuf": 'func show_total():\n    return total\n'},
     ("money.tuf", 2, 12, "I don't know what 'total' is."), "OK"),
    ({"shop.tuf": 'import money.tuf\n', "money.tuf": 'say "in money"\nreturn 5\n'},
     ("money.tuf", 2, 1, "'return' can only be used inside a function."), "OK"),
    ({"shop.tuf": 'import anims\nsay anims\n', "anims.tuf": 'say "mine"\n'},
     "OK", "OK"),  # (import anims is the library; import anims.tuf would be the file)
    ({"shop.tuf": 'mention file\nsay file.exists("x.txt")\n', "file.tuf": 'say "mine"\n'},
     "OK", "OK"),
    ({"shop.tuf": 'try:\n    import extras.tuf\ncatch:\n    say "no extras"\n'}, "OK", "OK"),
]
# What --check accepts in a program that uses its files (with MODULES_FILES' money.tuf and libs/fmt.tuf).
MODULES_GOOD = [
    'import money.tuf\nsay money.as_money(1) + money.as_money(money.rate)\n',
    'import money.tuf\nx = money.with_tax(2) + 1\nsay x\n',
    'import money.tuf\nf = money.as_money\nsay f(2)\n',
    'import money.tuf\nfunc go():\n    return money.counter()\nsay go()\n',
    'import fmt.tuf\nsay fmt.stars(2)\n',
    'import money.tuf\nsay "Rate: " + (money.rate + 1)\n',
    'import money.tuf\nprices = [1, 2]\nprices:sort(money.biggest_first)\nsay prices\n',
    'mention tax.tuf\nsay tax.money.rate\n',
]

# The editor: tuff-lang.js with a stand-in TuffIDE that reads a project's files (shop.tuf open, money.tuf on disk).
MODULES_LANG = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]);
const window = { TuffIDE: {
  readText: async (p) => (Object.hasOwn(files, p) ? files[p] : null),
  readDir: async (dir) => Object.keys(files).filter((p) => p.slice(0, p.lastIndexOf('\\')) === dir).map((p) => ({ name: p.slice(p.lastIndexOf('\\') + 1), isDir: false }))
    .concat(Object.keys(files).some((p) => p.startsWith(dir + '\\libs\\')) && !dir.endsWith('libs') ? [{ name: 'libs', isDir: true }] : []),
} }, ctx = { window };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
let monarch = null, hover = null, completion = null, signature = null;
const monaco = { Range: class { constructor(...a) { this.a = a; } }, editor: { defineTheme() {} }, languages: {
  register() {}, setMonarchTokensProvider(_id, def) { monarch = def; }, setLanguageConfiguration() {},
  registerHoverProvider(_id, p) { hover = hover || p; }, registerDefinitionProvider() {}, registerReferenceProvider() {},
  registerRenameProvider() {}, registerDocumentSymbolProvider() {}, registerSignatureHelpProvider(_id, p) { signature = p; }, registerColorProvider() {},
  registerCompletionItemProvider(_id, p) { completion = p; },
  CompletionItemKind: new Proxy({}, { get: (_t, k) => k }), CompletionItemInsertTextRule: {}, IndentAction: {}, SymbolKind: {} } };
window.defineTuffTheme = () => {};
window.registerTuff(monaco, '#3574f0');
const SHOP = 'C:\\proj\\shop.tuf';
const model = (src, col) => { const lines = src.split('\n'); return { uri: { scheme: 'file', fsPath: SHOP }, getLinesContent: () => lines,
  getLineContent: (n) => lines[n - 1], getValue: () => src, getWordUntilPosition: () => ({ startColumn: col || 1, endColumn: col || 1 }),
  getWordAtPosition: ({ lineNumber, column }) => { for (const m of lines[lineNumber - 1].matchAll(/\w+/g))
    if (m.index < column && column <= m.index + m[0].length) return { word: m[0], startColumn: m.index + 1, endColumn: m.index + 1 + m[0].length };
    return null; } }; };
(async () => {
  const src = 'import money.tuf\nimport fmt.tuf\nsay money.';
  const after = await completion.provideCompletionItems(model(src, 11), { lineNumber: 3, column: 11 });
  const asMoney = after.suggestions.find((s) => s.label === 'as_money');
  const libs = await completion.provideCompletionItems(model('import fmt.tuf\nsay fmt.', 9), { lineNumber: 2, column: 9 });
  const imports = await completion.provideCompletionItems(model('import ', 8), { lineNumber: 1, column: 8 });
  const onHover = await hover.provideHover(model('import money.tuf\nsay money.as_money(1)'), { lineNumber: 2, column: 12 });
  const valueHover = await hover.provideHover(model('import money.tuf\nsay money.rate'), { lineNumber: 2, column: 12 });
  const sig = await signature.provideSignatureHelp(model('import money.tuf\nsay money.as_money('), { lineNumber: 2, column: 20 });
  const plain = await completion.provideCompletionItems(model('say nothing.', 13), { lineNumber: 1, column: 13 });
  const toks = [];
  const rule = monarch.tokenizer.root.find((r) => String(r[0]) === String(/(import|mention)(\s+)([a-zA-Z_]\w*)/));
  console.log(JSON.stringify({
    labels: after.suggestions.map((s) => s.label), doc: asMoney && asMoney.documentation, detail: asMoney && asMoney.detail,
    insert: asMoney && asMoney.insertText, libs: libs.suggestions.map((s) => s.label + '|' + s.detail),
    imports: imports.suggestions.map((s) => s.label), hover: onHover && onHover.contents.map((c) => c.value).join(' / '),
    valueHover: valueHover && valueHover.contents.map((c) => c.value).join(' / '),
    sig: sig && sig.value.signatures[0].label, sigDoc: sig && sig.value.signatures[0].documentation, plain: plain.suggestions.length,
    wants: [window.tuffWantsSuggest(model('import money.tuf\nmoney.'), { lineNumber: 2, column: 7 }), window.tuffWantsSuggest(model('x = 1\nx.'), { lineNumber: 2, column: 3 })],
    rule: rule ? rule[1] : null, importDoc: window.TUFF_DOCS.import[1],
  }));
})();
"""


def modules_project(name, files):
    """Writes a project's files into out/modules/<name> (a fresh folder): its full path."""
    import shutil
    folder = os.path.join(HERE, "out", "modules", name)
    shutil.rmtree(folder, ignore_errors=True)
    for rel, code in files.items():
        path = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
    return folder


def modules_projects():
    """(name, files) for every project above, for the interp test's differential runs."""
    return [("modules shop", MODULES_FILES)] + [(f"modules mistake {i}", files) for i, (files, _r, _c) in enumerate(MODULES_ERRORS)]


def first_error(stderr):
    """The first "Tuff error ...": (the file it names, or "" for the program, line, column from the ^, message)."""
    lines = stderr.splitlines()
    first = next((i for i, x in enumerate(lines) if x.startswith("Tuff error")), None)
    if first is None:
        return None
    m = re.match(r"Tuff error(?: in (.+?))? on line (\d+): (.*)$", lines[first])
    if not m:
        return ("", None, None, lines[first])
    gutter = f"  {m.group(2)} | "
    caret = lines[first + 2] if first + 2 < len(lines) and lines[first + 2].strip() == "^" else ""
    return (m.group(1) or "", int(m.group(2)), (caret.index("^") - len(gutter) + 1) if caret else None, m.group(3))


def t_modules(c):
    """Console only, no window: 1.5.0's own files as libraries. A shop in five files runs the same in both runtimes (each
    file has its own top level and runs once, values are read live, libs/ works, a library's name wins); every mistake
    (no file, a built-in's name, files that import each other, errors inside an imported file, names it doesn't have,
    money.rate = 2) stops the run on the right file, line and column, and --check says what it can be sure of (and --as
    checks a copy as if it were the real file); TuffCode's error protocol names the file; TUFF_BASE_DIR, tuff_check and
    tuff_run through the MCP server, Tuff Engine's --scene preview, with_imports, the editor (Node) and Build exe
    (build_exe_pack_test.mjs, no PyInstaller and no windows)."""
    env = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW", "TUFF_BASE_DIR", "TUFF_NO_WRITES")}
    env["PYTHONIOENCODING"] = "utf-8"

    def run(folder, file="shop.tuf", slow=False, more=None, args=()):
        e = {**env, **({"TUFF_SLOW": "1"} if slow else {}), **(more or {})}
        return subprocess.run(tuff_cmd() + list(args) + [os.path.join(folder, file)], cwd=folder, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60, env=e, stdin=subprocess.DEVNULL)

    def check_out(folder, file="shop.tuf", args=None):
        """--check on a file of the folder (or with these inputs): (exit code, what it says)."""
        p = subprocess.run(tuff_cmd() + ["--check"] + (list(args) if args else [os.path.join(folder, file)]), cwd=folder, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60, env=env)
        return p.returncode, (p.stdout + p.stderr).strip()

    shop = modules_project("shop", MODULES_FILES)
    for slow in (False, True):
        p = run(shop, slow=slow)
        got = p.stdout.splitlines()
        c.check(p.returncode == 0 and got == MODULES_OUTPUT, f"the shop in five files runs ({'tree walker' if slow else 'compiled'}): "
                "money.tuf starts once, money.rate is read live, shop.tuf's rate is its own, libs/ and a library's name win",
                [x for x in got if x not in MODULES_OUTPUT] or (p.stdout + p.stderr)[-800:])
    for rel in MODULES_FILES:
        code, out = check_out(os.path.dirname(os.path.join(shop, *rel.split("/"))), os.path.basename(rel))
        c.check(code == 0 and out == "OK", f"--check accepts {rel}, checked on its own", out[:400])
    for i, code_text in enumerate(MODULES_GOOD):
        folder = modules_project(f"good{i}", {**{k: v for k, v in MODULES_FILES.items() if k != "shop.tuf"}, "shop.tuf": code_text})
        code, out = check_out(folder)
        c.check(code == 0 and out == "OK", f"--check accepts: {code_text.splitlines()[-1]}", out[:300])

    for i, (files, ran, checks) in enumerate(MODULES_ERRORS):
        folder = modules_project(f"mistake{i}", files)
        shown = files["shop.tuf"].strip().splitlines()[-1]
        both = [run(folder, slow=slow) for slow in (False, True)]
        if ran == "OK":
            c.check(all(p.returncode == 0 and "Tuff error" not in p.stderr for p in both), f"{shown!r} runs (in both runtimes)",
                    both[0].stderr[-300:])
        else:
            at = [first_error(p.stderr) for p in both]
            ok = all(a is not None and a[:3] == ran[:3] and ran[3] in a[3] for a in at) and at[0] == at[1]
            c.check(ok and all(p.returncode == 1 for p in both),
                    f"{shown!r} stops in {ran[0] or 'shop.tuf'} at {ran[1]}:{ran[2]}: {ran[3][:70].replace('→', '->')!r} (the same in both runtimes)", at)
        code, out = check_out(folder)
        if checks == "OK":
            c.check(code == 0 and out == "OK", f"...and --check can't be sure of it, so it says OK", out[:300])
        else:
            want = checks or ran[3]
            c.check(code == 1 and want in out, f"...and --check says {want[:70].replace('→', '->')!r}", out[:400])

    # --as: TuffCode checks a copy of the editor's text (a temp file) as if it were the real file, so imports resolve.
    folder = modules_project("as", {"shop.tuf": "", "money.tuf": MONEY})
    os.makedirs(OUT, exist_ok=True)
    copy = os.path.join(OUT, "modules_copy.tuf")
    with open(copy, "w", encoding="utf-8") as f:
        f.write('import money.tuf\nsay money.as_mony(1)\n')
    code, out = check_out(folder, args=(copy, "--as", os.path.join(folder, "shop.tuf")))
    c.check(code == 1 and "money.tuf doesn't have 'as_mony'. Did you mean 'as_money'?" in out, "--check copy --as shop.tuf finds money.tuf next to shop.tuf", out[:300])
    tmp = tempfile.mkdtemp(prefix="tuff-modules-")
    try:
        lone = os.path.join(tmp, "check.tuf")
        with open(lone, "w", encoding="utf-8") as f:
            f.write('import money.tuf\nsay money.as_mony(1)\nimport random\n')
        code, out = check_out(tmp, args=(lone,))
        c.check(code == 1 and "random is built into Tuff" in out and "money" not in out,
                "a temp file with no --as can't know its folder: only a built-in's name is flagged", out[:300])
        # TUFF_BASE_DIR (tuff_run's snippets): a program in a temp folder imports the project's files.
        with open(lone, "w", encoding="utf-8") as f:
            f.write('import money.tuf\nsay money.as_money(2)\n')
        p = run(tmp, "check.tuf", more={"TUFF_BASE_DIR": shop})
        c.check(p.returncode == 0 and p.stdout.splitlines() == ["money.tuf starts", "$2.00"], "with TUFF_BASE_DIR, a snippet imports the project's money.tuf",
                (p.stdout + p.stderr)[-300:])
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # TuffCode's Run panel (TUFF_IDE=1): an error in money.tuf adds money.tuf's full path to the error message's escape
    # code (ide.js marks that file); one in the program has no path, exactly as before.
    folder = modules_project("ide", MODULES_ERRORS[14][0])
    p = run(folder, more={"TUFF_IDE": "1"})
    m = re.search(r"\x1b\]tuff;error;([^\x07]*)\x07", p.stdout)
    parts = m.group(1).split(";") if m else []
    c.check(len(parts) == 4 and parts[:2] == ["2", "14"] and base64.b64decode(parts[3]).decode() == os.path.join(folder, "money.tuf")
            and base64.b64decode(parts[2]).decode() == "Can't divide text and a number.",
            "TUFF_IDE=1: the error's escape code has its line, column, message and money.tuf's path", parts)
    folder = modules_project("ide_main", MODULES_ERRORS[15][0])
    p = run(folder, more={"TUFF_IDE": "1"})
    m = re.search(r"\x1b\]tuff;error;([^\x07]*)\x07", p.stdout)
    c.check(m and len(m.group(1).split(";")) == 3 and m.group(1).startswith("3;16;"), "...and one in the program itself has no path (as in 1.4)",
            m and m.group(1))

    # In this process: with_imports (what decides whether a program needs the window engine's thread) reads the files a
    # program imports, and the ones they import; the debugger's step hooks see each file's statements, and file_of names the file.
    import tuff
    folder = modules_project("threads", {"game.tuf": "import level.tuf\nsay 1\n", "level.tuf": "import libs_too.tuf\nmention tgame\n",
                                         "libs/libs_too.tuf": "import tgui\n", "other.tuf": "mention atgui\n"})
    every = tuff.with_imports(os.path.join(folder, "game.tuf"), "import level.tuf\nsay 1\n")
    c.check(tuff.VIEW_IMPORT.search(every) and tuff.TK_IMPORT.search(every) and "atgui" not in every,
            "with_imports: a tgame or tgui import in a file the program imports (or that file imports) counts, and others don't", every)
    old = os.environ.pop("TUFF_SLOW", None)
    try:
        for slow in (False, True):
            if slow:
                os.environ["TUFF_SLOW"] = "1"
            path = os.path.join(shop, "shop.tuf")
            src = 'import money.tuf\nsay money.with_tax(1)\n'
            interp = tuff.Interpreter(src, shop)
            interp.path = path
            seen = []
            interp.step_hooks.append(lambda s, e: seen.append((os.path.basename(tuff.file_of(e)) or "shop.tuf", s.line)))
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                interp.run_block(tuff.Parser(tuff.tokenize(src)).program(), interp.globals)
            c.check(("money.tuf", 11) in seen and ("money.tuf", 12) in seen and seen[0] == ("shop.tuf", 1) and seen[-1][0] == "money.tuf",
                    f"{'the tree walker' if slow else 'compiled'}: a step hook sees money.tuf's statements, and file_of says they're money.tuf's", seen[:8])
            os.environ.pop("TUFF_SLOW", None)
    finally:
        if old is not None:
            os.environ["TUFF_SLOW"] = old

    # Tuff Engine's --scene preview: a game whose things are made by a function in its own level.tuf; an error in that
    # file names it; and a file it imports that opens another kind of window stops the preview before anything runs.
    folder = modules_project("scene", {"mods_game.tuf": 'mention tgame\nimport level.tuf\ngame = tgame.window("Mods", 400, 300)\nlevel.build(game)\nsay "made"\n',
                                       "level.tuf": 'func build(game):\n    game:box(10, 10)\n    game:box(50, 50)\n'})
    code, out, err, d, secs = scene(os.path.join(folder, "mods_game.tuf"))
    things = [(t.get("kind"), t.get("made")) for t in d.get("things", [])]
    c.check(code == 0 and d.get("error") is None and d.get("stopped") == "end" and things == [("box", [4, 2]), ("box", [4, 3])],
            f"--scene runs a game whose level.tuf makes its things, made by the game's line 4 ({secs:.1f} s)", (things, d.get("error"), d.get("stopped"), err[-300:]))
    folder = modules_project("scene_error", {"mods_error.tuf": 'mention tgame\nimport level.tuf\ngame = tgame.window("Mods", 400, 300)\nlevel.build(game)\n',
                                             "level.tuf": 'func build(game):\n    game:box(10, 10)\n    x = nope\n'})
    code, out, err, d, secs = scene(os.path.join(folder, "mods_error.tuf"))
    c.check((d.get("error") or {}).get("message", "").startswith("In level.tuf, line 3: I don't know what 'nope' is.") and (d.get("error") or {}).get("line") is None,
            "...an error in level.tuf says it's in level.tuf (and gives no line of the game's own)", d.get("error"))
    folder = modules_project("scene_window", {"mods_window.tuf": 'mention tgame\nimport menus.tuf\ngame = tgame.window("Mods", 400, 300)\n',
                                              "menus.tuf": 'import tgui\nwin = tgui.window("Not in a preview")\n'})
    code, out, err, d, secs = scene(os.path.join(folder, "mods_window.tuf"))
    c.check(d.get("stopped") == "other-window", "...and a file it imports that uses tgui stops the preview before it runs (no window)", d.get("stopped"))

    # The MCP server (agents): tuff_check of a "code" snippet checks its imports in the project, and tuff_run runs one.
    mcp = os.path.join(REPO, "tuffcode", "mcp", "tuff-mcp.js")
    calls = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tuff_check", "arguments": {"code": "import money.tuf\nsay money.as_mony(1)\n"}}},
             {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "tuff_run", "arguments": {"code": "import money.tuf\nsay money.as_money(3)\n"}}}]
    try:
        p = subprocess.Popen(["node", mcp], stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=shop, text=True, encoding="utf-8",
                             env={**env, "TUFF_CMD": json.dumps(tuff_cmd())})
    except FileNotFoundError:
        p = None
        c.check(True, "Node isn't installed: skipped the MCP checks")
    if p is not None:
        replies = {}
        try:
            for x in calls:
                p.stdin.write(json.dumps(x) + "\n")
            p.stdin.flush()
            deadline = time.time() + 90
            while time.time() < deadline and not (2 in replies and 3 in replies):  # the server quits when its input ends
                line = p.stdout.readline()
                if not line:
                    break
                reply = json.loads(line)
                replies[reply.get("id")] = reply
        finally:
            p.stdin.close()
            p.wait(10)
        text = lambda i: (((replies.get(i) or {}).get("result") or {}).get("content") or [{}])[0].get("text", "")
        c.check("money.tuf doesn't have 'as_mony'. Did you mean 'as_money'?" in text(2), "MCP tuff_check: a snippet's imports are checked in the project", text(2)[:300])
        c.check("money.tuf starts\n$3.00" in text(3), "MCP tuff_run: a snippet imports the project's money.tuf", text(3)[:300])

    # The editor (renderer/js/tuff-lang.js, in Node): money. offers money.tuf's functions (their comments as the docs)
    # and values, import offers the project's files, and the hover and signature help know them too.
    lang = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")
    project = {"C:\\proj\\shop.tuf": "import money.tuf\n", "C:\\proj\\money.tuf": MODULES_FILES["money.tuf"],
               "C:\\proj\\libs\\fmt.tuf": "# Stars in a row\nfunc stars(n):\n    return \"*\" * n\n", "C:\\proj\\notes.txt": "",
               "C:\\proj\\random.tuf": "", "C:\\proj\\tgame.tuf": ""}
    try:
        p = subprocess.run(["node", "-e", MODULES_LANG, lang, json.dumps(project)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        t = json.loads(p.stdout)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the editor checks")
        t = None
    except ValueError:
        c.check(False, "the editor checks ran", (p.stdout + p.stderr)[-600:])
        t = None
    if t:
        c.check(t["labels"] == ["as_money", "with_tax", "set_rate", "biggest_first", "apply", "counter", "rate", "count"],
                "money. offers money.tuf's functions, then its values", t["labels"])
        c.check(t["doc"] == '6.375 -> "$6.38"' and t["detail"] == "money.as_money(x)" and t["insert"] == "as_money($0)",
                "...with the comment above each function as its doc", [t["doc"], t["detail"], t["insert"]])
        c.check(t["libs"] == ["stars|fmt.stars(n)"], "fmt. finds libs/fmt.tuf", t["libs"])
        c.check(t["imports"][:3] == ["money.tuf", "tgame.tuf", "fmt.tuf"] and "shop.tuf" not in t["imports"] and "random.tuf" not in t["imports"]
                and t["imports"].count("tgame") == 1 and "anims" in t["imports"],
                "import offers money.tuf, tgame.tuf and fmt.tuf (from libs/), not shop.tuf itself or a built-in's name, then the libraries",
                t["imports"])
        c.check("money.as_money(x)" in (t["hover"] or "") and '6.375 -> "$6.38"' in t["hover"] and "money.tuf, line 7" in t["hover"],
                "hovering money.as_money shows how to call it, its doc and where it is", t["hover"])
        c.check("money.rate" in (t["valueHover"] or ""), "...and money.rate is a value", t["valueHover"])
        c.check(t["sig"] == "money.as_money(x)" and t["sigDoc"] == '6.375 -> "$6.38"', "typing money.as_money( shows its inputs", [t["sig"], t["sigDoc"]])
        c.check(t["plain"] == 0 and t["wants"] == [True, False], "money. opens the list (x. doesn't, and nothing. offers nothing)", [t["plain"], t["wants"]])
        c.check(t["rule"] == ["keyword", "", "library"] and "money.tuf" in t["importDoc"], "import money.tuf colours money like a library, and import's doc tells of files",
                [t["rule"], t["importDoc"][:120]])

    # The guide's example (money.tuf and shop.tuf, written to their own files) runs and gives what its comments say.
    guide = open(os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md"), encoding="utf-8").read()
    start = guide.find("\n## Your own files")
    section = guide[start:guide.find("\n## ", start + 1)] if start >= 0 else ""
    blocks = re.findall(r"```tuff\n(.*?)```", section, re.S)
    named = {re.match(r"# (\w+\.tuf)", b).group(1): b for b in blocks if re.match(r"# (\w+\.tuf)", b)}
    folder = modules_project("guide", named)
    p = run(folder) if "shop.tuf" in named else None
    want = [x.split("#")[1].strip() for x in named.get("shop.tuf", "").splitlines() if x.startswith("say") and "#" in x]
    c.check(p is not None and p.returncode == 0 and p.stdout.splitlines() == want and len(want) >= 4,
            f"the guide's money.tuf and shop.tuf run and say what their comments say ({len(want)} lines)", p and (p.stdout + p.stderr)[-400:])
    code, out = check_out(folder) if named else (1, "")
    c.check(code == 0 and out == "OK", "...and --check accepts them", out[:300])

    # Build exe: build_exe_pack_test.mjs packs a program that imports its files (no PyInstaller, nothing opens).
    try:
        p = subprocess.run(["node", os.path.join(HERE, "build_exe_pack_test.mjs")], capture_output=True, text=True, encoding="utf-8", timeout=300,
                           env={k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_BASE_DIR")})
        section = p.stdout[p.stdout.find("== Build exe: a program that imports its own files"):]
        section = section[:section.find("build_exe_pack:")]
        c.check(p.returncode == 0 and section.count("  ok  ") >= 6 and "FAIL" not in section,
                "Build exe packs the files a program imports, runs it in the app, and stops on a mistake in one (build_exe_pack_test.mjs)",
                (section or p.stdout)[-900:] + p.stderr[-300:])
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped Build exe")


# ---------------------------------------------------------------- 1.5.0: kinds, your own objects (kind Pet:)

KINDS_PROGRAM = '''say Pet("Early")
kind Pet:
    name = "?"
    hunger = 5
    toys = []
    friend = nil
    func feed(amount):
        my.hunger -= amount
        if my.hunger < 0:
            my.hunger = 0
        return my.hunger
    func play(toy):
        my.toys:add(toy)
        my:feed(-1)
    func hello():
        if my.friend is nil:
            return f"{my.name} has no friend yet"
        return f"{my.name} and {my.friend.name} are friends"
    func later():
        func shout():
            return my.name:upper()
        return shout()
kind Counter:
    func count_to(n):
        total = 0
        for i in range(1, n):
            if i == 3:
                continue
            if i > 5:
                break
            total += i
        return total
    func risky():
        try:
            return 1 / 0
        catch problem:
            return "caught: " + problem
rex = Pet("Rex")
ann = Pet("Ann", 2)
say rex:feed(3)
rex.hunger += 1
ann:play("ball")
ann:play("rope")
say rex
say ann
say rex.toys
rex.friend = ann
say rex:hello()
say ann:hello()
say rex.friend.toys:join(", ")
rex.friend.hunger = 9
say ann.hunger
best = rex
best.name = "Rexy"
say rex.name
say rex is best
say rex is Pet("Rexy")
say [rex, ann]:has(ann)
say [ann, rex]:find(rex)
say Counter():count_to(10)
say Counter():risky()
say rex:later()
pets = [Pet("Cat", 7), rex, Pet("Bo", 1)]
func by_hunger(p):
    return p.hunger
pets:sort(by_hunger)
say pets[0].name + " " + pets[-1].name
say f"{rex.name:6}|{rex.hunger:>3}|{ann}"
say "Pet: " + Pet("Z")
say text(Pet("Y", 0))
rex.friend = rex
say rex
kind = "dog"
say kind:upper()
my = [4]
my:add(5)
say my
func check(p):
    p.name = p.name + "!"
    return p.name
say check(ann)
groups = {"pets": [Pet("Q")]}
say groups["pets"][0].name
groups["pets"][0].toys:add("bone")
say groups["pets"][0].toys[0]
say Pet("A") != Pet("A")
say Counter()
'''
KINDS_OUTPUT = ['Pet(name: "Early", hunger: 5, toys: [], friend: nil)', "2", 'Pet(name: "Rex", hunger: 3, toys: [], friend: nil)',
                'Pet(name: "Ann", hunger: 4, toys: ["ball", "rope"], friend: nil)', "[]", "Rex and Ann are friends",
                "Ann has no friend yet", "ball, rope", "9", "Rexy", "true", "false", "true", "1", "12",
                "caught: You can't divide by zero.", "REXY", "Bo Cat",
                'Rexy  |  3|Pet(name: "Ann", hunger: 9, toys: ["ball", "rope"], friend: nil)', 'Pet: Pet(name: "Z", hunger: 5, toys: [], friend: nil)',
                'Pet(name: "Y", hunger: 0, toys: [], friend: nil)', 'Pet(name: "Rexy", hunger: 3, toys: [], friend: Pet(...))', "DOG",
                "[4, 5]", "Ann!", "Q", "bone", "true", "Counter()"]
# Mistakes: (code, line, column, what the run says, what --check says: None for the same, "OK" when only the run can tell).
KINDS_PET = 'kind Pet:\n    name = "?"\n    hunger = 5\n    func feed():\n        my.hunger -= 1\n    func eat(food):\n        my.hunger -= food\n'
KINDS_ERRORS = [
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex.hungr', 9, 8, "Pet doesn't have a field 'hungr'. Did you mean 'hunger'?", None),
    (KINDS_PET + 'rex = Pet("Rex")\nrex.hungr = 3', 9, 1, "Pet doesn't have a field 'hungr'. Did you mean 'hunger'?", None),
    (KINDS_PET + 'rex = Pet("Rex")\nrex:fead()', 9, 4, "Pet doesn't have an action 'fead'. Did you mean 'feed'?", None),
    (KINDS_PET + 'rex = Pet("Rex", 2, 3)', 8, 10, "Pet has 2 fields (name and hunger), so Pet() takes up to 2 inputs, one for each field in order, but got 3.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nrex:feed(1)', 9, 4, "rex:feed() needs 0 inputs, but got 1.", None),
    (KINDS_PET + 'pets = [Pet()]\npets[0]:eat()', 9, 8, "pets[0]:eat() needs 1 input, but got 0.", "OK"),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex:feed - 1', 9, 8, "rex:feed doesn't take an input, so what comes after it was read as one. Write rex:feed() instead.", None),
    ('kind Node:\n    value = 0\n    next = Node()\nsay Node(1, nil)\nsay Node()', 3, 16, "Node() was made inside itself too many times. Does a field of Node start with a new Node()?", "OK"),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex:hunger()', 9, 8, "hunger is a field of Pet, not an action, so it's read with a dot, like rex.hunger", None),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex.feed', 9, 8, "feed is an action of Pet, so it's called with ':', like rex:feed()", None),
    (KINDS_PET + 'say Pet.name', 8, 8, "Pet is a kind, not an object made from it. Make one first, like pet = Pet(...), then use pet.name.", None),
    (KINDS_PET + 'Pet:feed()', 8, 4, "Pet is a kind, not an object made from it.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nsay len(rex)', 9, 8, "len() needs text, a list or a dictionary, not a Pet.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex["name"]', 9, 8, "Can't use [ ] on a Pet. Use its fields with a dot, like rex.name.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nrex["hunger"] = 1', 9, 1, "You can only set items in a list, not in a Pet. Use its fields with a dot, like rex.hunger = ...", None),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex + 1', 9, 9, "Can't add a Pet and a number.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex < 1', 9, 9, "Can't compare a Pet with a number using <.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nfor x in rex:\n    say x', 9, 1, "Can't loop over a Pet.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nsay rex[0:1]', 9, 8, "Only text and lists have parts like [1:3], not a Pet.", None),
    (KINDS_PET + 'rex = Pet("Rex")\nd = {"best": rex}\nd[rex] = 1', 10, 1, "A dictionary's keys can be text or numbers, not a Pet.",
     "A dictionary's keys can be text or numbers, not a Pet."),  # (--check points at the key, as for any key)
    (KINDS_PET + 'say [Pet("a"), Pet("b")]:sort()', 8, 25, "The list has a Pet, which can't be sorted.", "OK"),
    ('kind Pet:\n    name = "?"\n    func f():\n        say name\nPet():f()', 4, 13, "I don't know what 'name' is. To use this Pet's field, write my.name", None),
    ('say my.x', 1, 5, "I don't know what 'my' is. my is the object itself, so it only works inside a kind's actions", None),
    ('func f(p):\n    return p.nmae\nkind Pet:\n    name = "?"\nsay f(Pet())', 2, 13, "Pet doesn't have a field 'nmae'. Did you mean 'name'?",
     "Nothing in this program has a field 'nmae'. Did you mean 'name'?"),
    ('func f(p):\n    p:fead()\nkind Pet:\n    func feed():\n        say 1\nf(Pet())', 2, 6, "Pet doesn't have an action 'fead'. Did you mean 'feed'?",
     "Nothing in Tuff has :fead. Did you mean :feed?"),
    ('kind Pet:\n    func f():\n        return my:g()\nPet():f()', 3, 18, "Pet doesn't have an action 'g'. Its actions are: f.", None),
    ('kind Box:\n    func f():\n        return 1\nsay Box(1)', 4, 8, "Box has no fields, so Box() takes no inputs, but got 1.", None),
    ('kind Owl:\n    n = 1\nsay Owl() - 1', 3, 11, "Can't subtract an Owl and a number.", None),
    ('kind Pet:\n    items = nope\nPet()', 2, 13, "I don't know what 'nope' is.", None),
    ('x = 5\nx.y = 3', 2, 1, "Only objects made from a kind have fields to set with '.', and this is a number.", None),
    ('d = {}\nd.y = 3', 2, 1, 'A dictionary\'s values are set with [ ], like d["y"] = ...', None),
    ('kind Owl:\n    n = 1\no = Owl()\no.n = o\nfile.save("o.json", o)', 5, 10, "file.save can't save an Owl that holds itself.", "OK"),
    ('kind Owl:\n    n = 1\nfile.save("o.json", Owl)', 3, 10, "file.save keeps text, numbers, true/false, nil, lists, dictionaries and objects made from a kind, not the kind Owl.", "OK"),
    ('kind Pet:\n    name = "?"\nrex = Pet()\nsay rex()', 4, 8, "isn't a function, so it can't be called with ( ).", "'rex' is a Pet, not a function"),
    # what the parser says (the run and --check alike)
    ('kind Pet:\n    name = "?"\nkind Pet:\n    age = 1', 3, 6, "There are two kinds called Pet. This one would replace the one on line 1.", None),
    ('func f():\n    kind Pet:\n        name = "?"', 2, 5, "Make a kind at the top of the program, not inside a function or a block.", None),
    ('kind Pet:\n    say "hi"', 2, 5, "A kind holds fields (like name = \"?\") and actions (like func feed():), and nothing else.", None),
    ('kind Pet:\n    hunger += 1', 2, 5, "A field gets the value a new Pet starts with, using =, like hunger = 0.", None),
    ('kind Pet:\n    name = 1\n    name = 2', 3, 5, "Pet already has a field called name.", None),
    ('kind Pet:\n    name = 1\n    func name():\n        return 1', 3, 5, "Pet already has a field called name.", None),
    ('kind Pet:\n    func f():\n        my = 3', 3, 9, "Inside an action, my is this Pet itself, so it can't be given a value.", None),
    ('kind Pet:\n    func f(my):\n        say 1', 2, 5, "An action's inputs can't be called my", None),
    ('kind Pet:\n    func f():\n        for my in [1]:\n            say my', 3, 9, "Inside an action, my is this Pet itself", None),
    ('kind Pet(Animal):\n    name = 1', 1, 9, "A kind can't be made from another kind: Tuff has no inheritance.", None),
    ('kind text:\n    name = 1', 1, 6, "text is Tuff's own function, so a kind can't be called that. Give it a name of its own, like Text.", None),
    ('kind tgame:\n    name = 1', 1, 6, "tgame is Tuff's own library", None),
    ('class Pet:\n    name = 1', 1, 1, "Tuff has no classes. To make your own kind of object, write: kind Pet:", None),
    ('kind Pet\n    name = 1', 1, 9, "Expected ':' after the kind's name, like: kind Pet:", None),
]
# The checker: (code, part of what --check says, or "OK": correct code it must never flag).
KINDS_CHECKS = [
    ('kind Pet:\n    name = "?"\nfunc show(p):\n    say p.name\n    p.name = "x"\nshow(Pet())', "OK"),
    ('kind Pet:\n    name = "?"\nfor p in [Pet()]:\n    say p.name', "OK"),
    ('kind Pet:\n    func feed():\n        say 1\nfunc f(p):\n    p:feed()\nf(Pet())', "OK"),
    ('rex = Pet("Rex")\nsay rex.name\nkind Pet:\n    name = "?"', "OK"),
    ('kind Bag:\n    items = []\n    func add(x):\n        my.items:add(x)\n    func play(x):\n        return my.items:has(x)\nb = Bag()\nb:add(1)\nsay b:play(1)', "OK"),
    ('kind Note:\n    text = ""\n    len = 0\nn = Note("hi", 2)\nsay n.text + n.len\nsay len(n.text)', "OK"),
    ('kind Pet:\n    name = "?"\nx = Pet()\nx = {"name": 1}\nsay x["name"]', "OK"),
    ('kind Pet:\n    name = "?"\n    toys = []\nrex = Pet()\nrex.toys:add(1)\nsay rex.toys[0] + 1\nsay f"{rex}" + rex', "OK"),
    ('kind Pet:\n    name = "?"\n    func later():\n        func shout():\n            return my.name:upper()\n        return shout()\nsay Pet():later()', "OK"),
    ('kind = "dog"\nsay kind:upper()\nmy = [1]\nmy:add(2)\nsay my', "OK"),
    ('kind = {"a": 1}\nsay kind["a"]\nfunc f(my):\n    return my + 1\nsay f(1)', "OK"),
    ('kind Pet:\n    name = "?"\nsay Pet() is nil\nsay [Pet()]:has(Pet())', "OK"),
    ('mention tgame\ngame = tgame.window("x")\nkind Enemy:\n    x = 0\n    body = nil\n    func spawn():\n        my.body = game:box(my.x, 10, 5, 5)\n'
     '        my.body:move(1, 0)\ne = Enemy(5)\ne:spawn()', "OK"),
    ('kind Pet:\n    name = "?"\nd = file.load("x.json", {})\nsay d.name', "OK"),
    ('kind Pet:\n    hunger = 5\n    func feed():\n        my.hunger -= 1\n        hunger = 2\n        return hunger', "OK"),
    ('kind Pet:\n    name = "?"\nrex = Pet()\nrex.name = 5\nsay rex.name - 1', "OK"),
    # mistakes only --check finds this way
    ('kind Pet:\n    name = "?"\nPet = 5\nsay Pet("x")', "Pet is a kind, and giving it a value replaces it"),
    ('kind Pet:\n    name = "?"\nfunc Pet():\n    return 1', "There's a kind called Pet on line 1, and a function with the same name"),
    ('kind Pet:\n    name = "?"\nsay self.name', "Tuff has no classes: make a kind (kind Pet:), and in its actions the object itself is my"),
    ('kind Pet:\n    name = "?"\nrex = Pet()\nsay number(rex)', "number() needs text or a number, not a Pet."),
    ('kind Pet:\n    name = "?"\nsay feed()', "I don't know what 'feed' is."),
]
# Saved objects: a program with the kind gets objects back (a field the file doesn't have starts with its kind's
# value), one without it gets the dictionary.
KINDS_SAVE = '''kind Pet:
    name = "?"
    hunger = 5
    toys = []
pets = [Pet("Rex", 2), Pet("Ann")]
pets[1].toys:add("ball")
file.save("pets.json", {"pets": pets, "count": 2})
data = file.load("pets.json")
say data["pets"][1]
say data["pets"][0].hunger + 1
say data["count"]
'''
KINDS_SAVE_FILE = {"pets": [{"$kind": "Pet", "name": "Rex", "hunger": 2, "toys": []}, {"$kind": "Pet", "name": "Ann", "hunger": 5, "toys": ["ball"]}],
                   "count": 2}
KINDS_LOAD_NEWER = 'kind Pet:\n    name = "?"\n    age = 1\nsay file.load("pets.json")["pets"][0]\nsay file.load("pets.json")["pets"][1].age + 1\n'
KINDS_LOAD_NONE = 'd = file.load("pets.json")\nsay d["pets"][0]\nsay d["pets"][0]["$kind"]\nfile.save("again.json", d)\n'
KINDS_HOOKS = 'kind Pet:\n    hunger = 5\n    func feed():\n        my.hunger -= 1\n        return my.hunger\nrex = Pet()\nrex:feed()\n'
KINDS_SCENE = '''mention tgame
game = tgame.window("Kinds", 400, 300)
kind Enemy:
    x = 0
    hp = 3
    body = nil
    func spawn():
        my.body = game:box(my.x, 100, 20, 20, "red")
        return my
enemies = []
for i in range(1, 3):
    enemies:add(Enemy(i * 100):spawn())
say len(enemies)
'''
# The editor (renderer/js/tuff-lang.js), with Node: rex. offers Pet's fields and rex: its actions, a kind's name has
# a hover with its fields, kind and my are Tuff's words only where they mean that, and (when monaco-editor is
# installed) Monaco's own Monarch tokenizer accepts the colours and gives them.
KINDS_LANG = r"""
const fs = require('fs'), vm = require('vm'), path = require('path'), url = require('url');
const window = {}, ctx = { window };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
let monarch = null, hovers = [], completion = null, signature = null, symbols = null, definition = null;
const monaco = { Range: class { constructor(...a) { this.a = a; } }, editor: { defineTheme() {} }, languages: {
  register() {}, setMonarchTokensProvider(_id, def) { monarch = def; }, setLanguageConfiguration() {},
  registerHoverProvider(_id, p) { hovers.push(p); }, registerDefinitionProvider(_id, p) { definition = p; }, registerReferenceProvider() {},
  registerRenameProvider() {}, registerDocumentSymbolProvider(_id, p) { symbols = p; }, registerSignatureHelpProvider(_id, p) { signature = p; },
  registerColorProvider() {}, registerCompletionItemProvider(_id, p) { completion = p; },
  CompletionItemKind: new Proxy({}, { get: (_t, k) => k }), CompletionItemInsertTextRule: {}, IndentAction: {}, SymbolKind: new Proxy({}, { get: (_t, k) => k }) } };
window.defineTuffTheme = () => {};
window.registerTuff(monaco, '#3574f0');
const model = (src, col) => { const lines = src.split('\n'); return { getLinesContent: () => lines, getLineContent: (n) => lines[n - 1],
  getValue: () => src, getLineMaxColumn: (n) => lines[n - 1].length + 1, uri: 'x', getWordUntilPosition: () => ({ startColumn: col || 1, endColumn: col || 1 }),
  getWordAtPosition: ({ lineNumber, column }) => { for (const m of lines[lineNumber - 1].matchAll(/\w+/g))
    if (m.index < column && column <= m.index + m[0].length) return { word: m[0], startColumn: m.index + 1, endColumn: m.index + 1 + m[0].length };
    return null; } }; };
const SRC = 'kind Pet:\n    name = "?"\n    hunger = 5\n    func feed():\n        my.hunger -= 1\n    func eat(food):\n        my.hunger -= food\n'
  + 'kind Owl:\n    wise = true\nrex = Pet("Rex")\nrex:feed()\nsay rex.hunger\nfunc show(p):\n    say p.name\n';
const n = SRC.split('\n').length; // the line after SRC
const labels = (src, line, col) => completion.provideCompletionItems(model(src, col), { lineNumber: line, column: col }).suggestions.map((s) => s.label);
const hover = (src, line, col) => { for (const h of hovers) { const r = h.provideHover(model(src), { lineNumber: line, column: col }); if (r) return r.contents.map((c) => c.value).join('\n'); } return null; };
const ids = (src) => ctx.tuffIdents(model(src)).map((x) => `${x.name}@${x.line}:${x.start}`).join(' ');
const sig = (src, line, col) => signature.provideSignatureHelp(model(src), { lineNumber: line, column: col })?.value.signatures[0].label;
const out = {
  kinds: ctx.tuffKinds(model(SRC)).map((k) => `${k.name}[${k.fields.map((f) => f.name + '=' + f.value)}|${k.actions.map((a) => a.name + '(' + a.params + ')')}]${k.line}-${k.end}`),
  fieldsRex: labels(SRC + 'say rex.', n, 9), fieldsMy: labels(SRC.replace('my.hunger -= 1', 'my.'), 5, 12),
  fieldsAny: labels(SRC + 'say p.', n, 7), actionsRex: labels(SRC + 'rex:', n, 5),
  actionsAny: labels(SRC + 'p:', n, 3).filter((l) => ['feed', 'eat', 'upper', 'add'].includes(l)),
  top: labels(SRC, n, 1).filter((l) => ['Pet', 'Owl', 'feed', 'eat', 'show'].includes(l)),
  hoverKind: hover(SRC, 10, 8), hoverField: hover(SRC, 12, 10), hoverAction: hover(SRC, 11, 6), hoverMy: hover(SRC, 5, 9),
  hoverWord: hover('kind Pet:\n    x = 1', 1, 2), hoverOwnKind: hover('kind = "dog"\nsay kind', 2, 6),
  ids: ids(SRC), own: ids('kind = "dog"\nsay kind\nmy = 2\nsay my'), rename: ids('name = 1\nkind Pet:\n    name = name\nsay name'),
  wants: [window.tuffWantsSuggest(model(SRC + 'say rex.'), { lineNumber: n, column: 9 }), window.tuffWantsSuggest(model('say rex.'), { lineNumber: 1, column: 9 })],
  sigKind: sig(SRC + 'x = Pet(', n, 9), sigAction: sig(SRC + 'rex:eat(', n, 9),
  def: definition.provideDefinition(model(SRC), { lineNumber: 10, column: 8 })?.range.a,
  symbols: symbols.provideDocumentSymbols(model(SRC)).map((s) => `${s.name}:${s.kind}`),
  snippet: completion.provideCompletionItems(model(''), { lineNumber: 1, column: 1 }).suggestions.find((s) => s.label === 'kind')?.insertText,
  words: [!!window.TUFF_DOCS.kind, !!window.TUFF_DOCS.my, window.TUFF_KEYWORDS.includes('kind'), window.TUFF_KEYWORDS.includes('my')],
};
async function real() { // Monaco's own Monarch: the tokenizer compiles, and colours these lines
  const dir = process.argv[2];
  if (!dir || !fs.existsSync(path.join(dir, 'esm'))) return null;
  const base = path.join(dir, 'esm', 'vs', 'editor', 'standalone', 'common', 'monarch');
  const { compile } = await import(url.pathToFileURL(path.join(base, 'monarchCompile.js')).href);
  const { MonarchTokenizer } = await import(url.pathToFileURL(path.join(base, 'monarchLexer.js')).href);
  const here = (x) => (x && x.constructor && x.constructor.name === 'RegExp' ? new RegExp(x.source, x.flags) // (made in the vm's realm)
    : Array.isArray(x) ? x.map(here) : x && typeof x === 'object' ? Object.fromEntries(Object.entries(x).map(([k, v]) => [k, here(v)])) : x);
  const t = new MonarchTokenizer({}, {}, 'tuff', compile('tuff', here(monarch)), { getValue: () => 20000, onDidChangeConfiguration: () => ({ dispose() {} }) });
  let state = t.getInitialState();
  const lines = [];
  for (const line of ['kind Pet:', '        my.hunger -= 1', 'rex = Pet("Rex")', 'say rex.hunger', 'w = tgame.window("x")', 'kind = "dog"',
    'say kind:upper()', 'my = 3', 'say f"{my.name}"']) {
    const r = t.tokenize(line, true, state);
    state = r.endState;
    lines.push(r.tokens.map((tok, i) => `${line.slice(tok.offset, r.tokens[i + 1]?.offset ?? line.length)}=${tok.type.replace(/\.tuff$/, '')}`)
      .filter((x) => !/^\s*=/.test(x)).join(' '));
  }
  return lines;
}
real().then((r) => { out.real = r; console.log(JSON.stringify(out)); }, (e) => { out.real = 'ERROR ' + e.message; console.log(JSON.stringify(out)); });
"""


def t_kinds(c):
    """Console only, no window: 1.5.0's kinds (kind Pet:, Pet("Rex"), rex.hunger, rex:feed(), my). A program with
    fields, actions, my, objects in lists, sorting and the soft words used as variables runs the same in both
    runtimes and --check accepts it; each mistake stops the run and --check with the same message at the same place;
    correct code the checker can't see the kind of is never flagged; objects save and load (a program with the kind
    gets objects back, one without it a dictionary); the step hooks see actions; Tuff Engine's --scene preview runs a
    kind's actions; and the editor's tuff-lang.js knows kinds (with Node)."""
    folder = os.path.join(HERE, "out", "kinds")
    os.makedirs(folder, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for k in ("TUFF_IDE", "TUFF_SLOW", "TUFF_NO_WRITES"):
        env.pop(k, None)

    def write(name, code):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code if code.endswith("\n") else code + "\n")
        return path

    def run(path, slow=False, extra=None, check=False):
        e = {**env, **({"TUFF_SLOW": "1"} if slow else {}), **(extra or {})}
        return subprocess.run(tuff_cmd() + (["--check"] if check else []) + [path], capture_output=True, text=True, encoding="utf-8",
                              timeout=60, env=e, cwd=folder, stdin=subprocess.DEVNULL)

    def where(stderr):
        """The line, column and message of the first "Tuff error" (the column from the ^ under the line)."""
        lines = stderr.splitlines()
        first = next((i for i, x in enumerate(lines) if x.startswith("Tuff error on line ")), None)
        if first is None:
            return None, None, stderr.strip()
        head, msg = lines[first][len("Tuff error on line "):].split(": ", 1)
        caret = lines[first + 2] if first + 2 < len(lines) and lines[first + 2].strip() == "^" else ""
        return int(head), (caret.index("^") - len(f"  {head} | ") + 1) if caret else None, msg

    path = write("kinds.tuf", KINDS_PROGRAM)
    for slow in (False, True):
        p = run(path, slow)
        got = p.stdout.splitlines()
        mode = "the tree walker" if slow else "the compiled runtime"
        c.check(p.returncode == 0 and got == KINDS_OUTPUT, f"{mode} runs the kinds program: {len(KINDS_OUTPUT)} lines as expected",
                [(i + 1, a, b) for i, (a, b) in enumerate(zip(got + [None] * 40, KINDS_OUTPUT)) if a != b][:4] or (p.stdout + p.stderr)[-500:])
    p = run(path, check=True)
    c.check(p.stdout.strip() == "OK", "--check accepts all of it", (p.stdout + p.stderr)[:600])

    for i, (code, line, col, says, check_says) in enumerate(KINDS_ERRORS):
        bad = write(f"mistake{i}.tuf", code)
        shown = code.splitlines()[line - 1].strip()
        runs = [where(run(bad, slow).stderr) for slow in (False, True)]
        c.check(runs[0] == runs[1] and runs[0][:2] == (line, col) and says in runs[0][2],
                f"running {shown!r} stops at {line}:{col} in both runtimes: {says[:60]!r}", runs)
        p = run(bad, check=True)
        if check_says == "OK":
            c.check(p.stdout.strip() == "OK", f"--check can't know it before the run, and says OK: {shown!r}", (p.stdout + p.stderr)[:300])
        else:
            at = where(p.stderr)
            c.check(p.returncode == 1 and at[0] == line and (check_says or says) in at[2] and (check_says is not None or at[1] == col),
                    f"--check on {shown!r} says it on line {line} too" + ("" if check_says else f" (at {line}:{col})"), at)

    for i, (code, want) in enumerate(KINDS_CHECKS):
        p = run(write(f"check{i}.tuf", code), check=True)
        out = (p.stdout + p.stderr).strip()
        shown = code.splitlines()[-1].strip()
        if want == "OK":
            c.check(out == "OK", f"--check accepts: {shown}", out[:300])
        else:
            c.check(p.returncode == 1 and want in out, f"--check on {shown!r} says {want[:50]!r}", out[:300])

    # Saving and loading objects, with writes on and in memory (TUFF_NO_WRITES, like tuff_run).
    for name in ("pets.json", "again.json"):
        if os.path.exists(os.path.join(folder, name)):
            os.remove(os.path.join(folder, name))
    p = run(write("save.tuf", KINDS_SAVE))
    c.check(p.stdout.splitlines() == ['Pet(name: "Ann", hunger: 5, toys: ["ball"])', "3", "2"],
            "file.load gives back Pet objects in a program that has kind Pet", (p.stdout + p.stderr)[-400:])
    c.check(same_json(read_json(os.path.join(folder, "pets.json")), KINDS_SAVE_FILE),
            'file.save keeps each object as a dictionary that starts with "$kind"', read_json(os.path.join(folder, "pets.json")))
    p = run(write("newer.tuf", KINDS_LOAD_NEWER))
    c.check(p.stdout.splitlines() == ['Pet(name: "Rex", age: 1)', "2"],
            "a kind that changed since (a new field, one gone) loads old saves: the new field starts with its value", (p.stdout + p.stderr)[-400:])
    p = run(write("nokind.tuf", KINDS_LOAD_NONE))
    c.check(p.stdout.splitlines() == ['{"$kind": "Pet", "name": "Rex", "hunger": 2, "toys": []}', "Pet"]
            and same_json(read_json(os.path.join(folder, "again.json")), KINDS_SAVE_FILE),
            "in a program without the kind it's a dictionary, and saving it again keeps it the same", (p.stdout + p.stderr)[-400:])
    os.remove(os.path.join(folder, "pets.json"))
    for slow in (False, True):
        p = run(os.path.join(folder, "save.tuf"), slow, {"TUFF_NO_WRITES": "1"})
        c.check(p.stdout.splitlines() == ['Pet(name: "Ann", hunger: 5, toys: ["ball"])', "3", "2"] and not os.path.exists(os.path.join(folder, "pets.json")),
                f"with writes kept in memory (TUFF_NO_WRITES=1, {'the tree walker' if slow else 'compiled'}) objects save and load too",
                (p.stdout + p.stderr)[-300:])

    # The debugger's hook point sees the statements in an action, in both runtimes.
    import tuff
    for slow in (True, False):
        old = os.environ.pop("TUFF_SLOW", None)
        if slow:
            os.environ["TUFF_SLOW"] = "1"
        try:
            interp = tuff.Interpreter(KINDS_HOOKS, folder)
        finally:
            os.environ.pop("TUFF_SLOW", None)
            if old is not None:
                os.environ["TUFF_SLOW"] = old
        seen = []
        interp.step_hooks.append(lambda s, env: seen.append(s.line))
        interp.run_block(tuff.Parser(tuff.tokenize(KINDS_HOOKS)).program(), interp.globals)
        rex = interp.globals.vars["rex"]
        c.check(seen == [1, 6, 7, 4, 5] and rex.fields == {"hunger": 4},
                f"{'the tree walker' if slow else 'the compiled runtime'}: a step hook sees the action's statements as they run", (seen, rex.fields))

    # Tuff Engine's preview runs a kind's actions, which make the game's things.
    code, out, err, d, secs = scene(write("kinds_scene.tuf", KINDS_SCENE))
    c.check(code == 0 and d.get("error") is None and d.get("stopped") == "end" and len(d.get("things", [])) == 3,
            f"the --scene preview runs actions that make boxes ({secs:.1f} s)", (d.get("error"), d.get("stopped"), len(d.get("things", [])), err[-300:]))

    lang = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")
    monaco_dir = os.environ.get("TUFF_MONACO") or os.path.join(REPO, "tuffcode", "node_modules", "monaco-editor")
    try:
        p = subprocess.run(["node", "-e", KINDS_LANG, lang, monaco_dir], capture_output=True, text=True, encoding="utf-8", timeout=60)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the editor checks")
        return
    try:
        t = json.loads(p.stdout)
    except ValueError:
        c.check(False, "the editor checks ran", (p.stdout + p.stderr)[-600:])
        return
    c.check(t["kinds"] == ['Pet[name="?",hunger=5|feed(),eat(food)]1-7', "Owl[wise=true|]8-9"],
            "tuffKinds reads each kind's fields (with their starting values) and actions", t["kinds"])
    c.check(t["fieldsRex"] == ["name", "hunger"] and t["fieldsMy"] == ["name", "hunger"] and t["fieldsAny"] == ["name", "hunger", "wise"],
            "after rex. (and my. in an action) come Pet's fields; after p. every kind's", [t["fieldsRex"], t["fieldsMy"], t["fieldsAny"]])
    c.check(t["actionsRex"] == ["feed", "eat"] and t["actionsAny"][:2] == ["feed", "eat"] and {"upper", "add"} <= set(t["actionsAny"]),
            "after rex: come only Pet's actions; after p: the actions first, then the other methods", [t["actionsRex"], t["actionsAny"]])
    c.check(t["top"] == ["show", "Pet", "Owl"], "a line's completions offer the kinds (Pet(...)) and functions, not the actions", t["top"])
    c.check("kind Pet:" in (t["hoverKind"] or "") and "hunger = 5" in t["hoverKind"] and "func eat(food)" in t["hoverKind"],
            "hovering a kind's name shows its fields and actions", t["hoverKind"])
    c.check("A field of Pet" in (t["hoverField"] or "") and "rex:feed()" in (t["hoverAction"] or "") and "This Pet itself" in (t["hoverMy"] or ""),
            "hovering rex.hunger, rex:feed and my says what they are", [t["hoverField"], t["hoverAction"], t["hoverMy"]])
    c.check("kind Pet:" in (t["hoverWord"] or "") and t["hoverOwnKind"] is None,
            "the word kind has a hover, and a variable called kind doesn't", [t["hoverWord"], t["hoverOwnKind"]])
    c.check(t["ids"] == "Pet@1:6 food@6:14 food@7:22 Owl@8:6 rex@10:1 Pet@10:7 rex@11:1 rex@12:5 show@13:6 p@13:11 p@14:9"
            and t["own"] == "kind@1:1 kind@2:5 my@3:1 my@4:5" and t["rename"] == "name@1:1 Pet@2:6 name@3:12 name@4:5",
            "rename and find uses: kind and my are names only outside kinds, and a field isn't the variable with its name",
            [t["ids"], t["own"], t["rename"]])
    c.check(t["wants"] == [True, False], "typing rex. opens the list in a file with kinds (and not in one without)", t["wants"])
    c.check(t["sigKind"] == "Pet(name, hunger)" and t["sigAction"] == "Pet:eat(food)", "Pet( and rex:eat( show their inputs",
            [t["sigKind"], t["sigAction"]])
    c.check(t["def"] == [1, 6, 1, 9] and t["symbols"] == ["Pet:Class", "Pet:feed:Method", "Pet:eat:Method", "Owl:Class", "rex:Variable", "show:Function"],
            "go to definition finds kind Pet:, and the outline lists kinds and their actions", [t["def"], t["symbols"]])
    c.check(t["snippet"] == 'kind ${1:Pet}:\n    ${2:name} = ${3:"?"}\n    func ${4:feed}():\n        $0' and t["words"] == [True, True, True, True],
            "there is a kind snippet, and kind and my are Tuff's words with docs", [t["snippet"], t["words"]])
    if t["real"] is None:
        c.check(True, "monaco-editor isn't installed here: skipped the Monarch check")
        return
    want = ["kind=keyword Pet=function.decl :=source", "my=keyword .=delimiter hunger=identifier -==operator 1=number",
            'rex=identifier Pet=function (=delimiter.parenthesis "Rex"=string )=delimiter.parenthesis', "say=keyword rex=identifier .=delimiter hunger=identifier",
            'w=identifier tgame=library .=delimiter window=function (=delimiter.parenthesis "x"=string )=delimiter.parenthesis',
            'kind=identifier "dog"=string', "say=keyword kind=identifier :=delimiter upper=method ()=delimiter.parenthesis", "my=identifier 3=number",
            'say=keyword f"=string {=delimiter.curly my=keyword .=delimiter name=identifier }=delimiter.curly "=string']
    c.check(t["real"] == want, "Monaco's Monarch colours kind Pet: and my.hunger as Tuff's words, a field as a name, and a variable called kind as a variable",
            [(a, b) for a, b in zip(t["real"] if isinstance(t["real"], list) else [t["real"]], want) if a != b])


# ---------------------------------------------------------------- 1.5.0: tterm, terminal games
# A program that moves with keys from screen:press: right on frames 1 and 2, down held on frame 5, space and right on
# frame 9, q (which stops it) on frame 20.
TTERM_PROGRAM = """mention tterm
screen = tterm.screen(12, 5)
x = 1
y = 2
jumps = 0
frames = 0
total = 0
func step(dt):
    frames += 1
    total += dt
    if screen:pressed("right"):
        x += 1
    if screen:held("down"):
        y += 1
    if screen:pressed("space"):
        jumps += 1
    screen:clear()
    screen:box(0, 0, 12, 5, "gray")
    screen:text(1, 0, f"{jumps}", "gold")
    screen:put(x, y, "@", "lime")
    if screen:pressed("q"):
        screen:stop()
screen:press("right")
screen:press("right")
screen:press("down", 5)
screen:press("space", 9)
screen:press("right", 9)
screen:press("q", 20)
screen:every_frame(step)
say f"x {x} y {y} jumps {jumps} frames {frames} time {total:0.00}"
say screen:get(x, y) + screen:get(0, 0) + screen:get(99, 0) + "|" + screen
"""
TTERM_FRAME = ["┌1─────────┐", "│          │", "│          │", "│   @      │", "└──────────┘"]
TTERM_AFTER = ["x 4 y 3 jumps 1 frames 20 time 1.00", "@┌|<screen 12x5>"]
# Mistakes the run stops at, on their line: (program, line, what it says).
TTERM_ERRORS = [
    ('mention tterm\nscreen = tterm.screen(10, 4)\nscreen:put(1, 1, "ab")', 3, "screen:put draws one character"),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nscreen:text(1, 1, "hi", "limme")', 3, 'doesn\'t know the colour "limme". Did you mean "lime"?'),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nsay screen:held("spcae")', 3, 'isn\'t a key tterm knows. Did you mean "space"?'),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nscreen:every_frame("step")', 3, "screen:every_frame needs a function's name"),
    ('mention tterm\nscreen = tterm.screen(0, 4)', 2, "tterm.screen's width goes from 1 to 200"),
    ('mention tterm\nscreen = tterm.screen("big", 4)', 2, "tterm.screen's width needs a number, not text"),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nscreen:put("a", 1, "@")', 3, "screen:put needs numbers for x and y, not text"),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nscreen:press("any")', 3, "screen:press needs a real key"),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nfunc step(dt):\n    screen:put(2, 1, "@")\n    say nope\nscreen:every_frame(step)', 5,
     "I don't know what 'nope' is"),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nfunc step(dt):\n    screen:every_frame(step)\nscreen:every_frame(step)', 4,
     "screen:every_frame is already running"),
    ('mention tterm\nscreen = tterm.screen(10, 4)\nscreen:draw(1, 1)', 3, "A screen doesn't have :draw."),
]
# --check: (code after a screen and a step function, what it says, or "OK").
TTERM_HEAD = "mention tterm\nscreen = tterm.screen(20, 10)\nfunc step(dt):\n    screen:clear()\n"
TTERM_CHECKS = [
    ('screen:draw(1, 2, "@")', "A screen doesn't have :draw."), ("screen:put(1, 2)", "screen:put got the wrong number of inputs (2)."),
    ('screen:put(1, 2, "@", "limme")', 'screen:put doesn\'t know the colour "limme". Did you mean "lime"?'),
    ('screen:box(0, 0, 5, 5, "grey9")', 'screen:box doesn\'t know the colour "grey9"'),
    ('say screen:pressed("spcae")', '"spcae" isn\'t a key tterm knows. Did you mean "space"?'),
    ('say screen:held("shift")', "a terminal doesn't tell a program about shift on its own"),
    ('say screen:pressed("escape")', 'Esc ends screen:every_frame, so screen:pressed("escape") is never true'),
    ('screen:press("any")', "screen:press needs a real key"), ('screen:put(1, 1, "ab")', "screen:put draws one character"),
    ('screen:put(1, 1, "")', "screen:put needs a character to draw"),
    ("screen:every_frame(step())", "Pass the function's name without brackets: step, not step()"),
    ('screen:every_frame("step")', "This needs a function name, not text."),
    ("func two(a, b):\n    say a\nscreen:every_frame(two)", "two() needs 2 inputs, but screen:every_frame only gives it 1"),
    ("n = 5\nscreen:every_frame(n)", "screen:every_frame needs a function's name"),
    ("screen:every_frame(screen:clear())", "screen:clear runs right away here"),
    ("s = tterm.screen(0, 10)", "tterm.screen's width goes from 1 to 200"), ("s = tterm.screen(20, -3)", "tterm.screen's height goes from 1 to 100"),
    ("s = tterm.scren(20, 10)", "tterm doesn't have 'scren'. It has: screen."), ("s = tterm.screen(1, 2, 3)", "tterm.screen() got the wrong number of inputs (3)."),
    ("screen()", "'screen' is a tterm screen, not a function"), ("screen:stop 5", "Write screen:stop() instead."),
    ("x = tterm.screen\nx:put(1, 1, \"@\")", "is the function tterm.screen itself"),
    ("screen:every_frame(step)", "OK"), ('screen:put(1.5, 2, "é", "#ff8800")', "OK"), ('screen:put(1, 2, "🐍")', "OK"),
    ('screen:put(1, 2, "👍🏽")', "OK"), ('screen:text(0, 0, f"x {1}", "dark green")', "OK"), ('say screen:get(1, 1) + "!"', "OK"),
    ('if screen:pressed("any"):\n    say 1', "OK"), ('screen:press("down", 30)', "OK"), ('screen:press(" ")', "OK"), ("screen:stop()", "OK"),
    ("screen:stop", "OK"), ("screen:clear", "OK"), ("s = tterm.screen()", "OK"), ("func one():\n    say 1\nscreen:every_frame(one)", "OK"),
    ('k = "x"\nsay screen:held(k)', "OK"), ("say screen", "OK"), ("screen:box(-1, -1, 100, 3)", "OK"), ('say screen:pressed("Left")', "OK"),
    ("func make():\n    return step\nscreen:every_frame(make())", "OK"), ("screen:every_frame(print)", "OK"),
]
# The editor (tuff-lang.js, with Node): the library, hovers, completions in a tterm file and in another, and the snippet.
TTERM_LANG = r"""
const fs = require('fs'), vm = require('vm');
const window = {}, ctx = { window };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
let hover = null, completion = null, monarch = null;
const monaco = { Range: class { constructor(...a) { this.a = a; } }, editor: { defineTheme() {} }, languages: {
  register() {}, setMonarchTokensProvider(_id, def) { monarch = def; }, setLanguageConfiguration() {},
  registerHoverProvider(_id, p) { hover = hover || p; }, registerDefinitionProvider() {}, registerReferenceProvider() {},
  registerRenameProvider() {}, registerDocumentSymbolProvider() {}, registerSignatureHelpProvider() {}, registerColorProvider() {},
  registerCompletionItemProvider(_id, p) { completion = p; },
  CompletionItemKind: new Proxy({}, { get: (_t, k) => k }), CompletionItemInsertTextRule: {}, IndentAction: {}, SymbolKind: {} } };
window.defineTuffTheme = () => {};
window.registerTuff(monaco, '#3574f0');
const model = (src, col) => { const lines = src.split('\n'); return { getLinesContent: () => lines, getLineContent: (n) => lines[n - 1],
  getValue: () => src, getWordUntilPosition: () => ({ startColumn: col || 1, endColumn: col || 1 }),
  getWordAtPosition: ({ lineNumber, column }) => { for (const m of lines[lineNumber - 1].matchAll(/\w+/g))
    if (m.index < column && column <= m.index + m[0].length) return { word: m[0], startColumn: m.index + 1, endColumn: m.index + 1 + m[0].length };
    return null; } }; };
const names = (src) => { const lines = src.split('\n'); const col = lines[lines.length - 1].length + 1;
  return completion.provideCompletionItems(model(src, col), { lineNumber: lines.length, column: col }).suggestions.map((s) => s.label); };
const hoverAt = (src, column) => { const h = hover.provideHover(model(src), { lineNumber: 1, column }); return h ? h.contents.map((x) => x.value).join(' | ') : null; };
const term = names('mention tterm\nscreen = tterm.screen(40, 20)\nscreen:');
const plain = names('items = [1]\nitems:');
const game = names('mention tgame\ngame = tgame.window("G")\ngame:');
const snippet = completion.provideCompletionItems(model('', 1), { lineNumber: 1, column: 1 }).suggestions.find((s) => s.label === 'tterm game');
console.log(JSON.stringify({
  libs: Object.keys(window.TUFF_LIBS), lib: window.TUFF_LIBS.tterm, doc: window.TUFF_DOCS.tterm,
  libNames: names('mention tterm\ns = tterm.'), mentions: names('mention '),
  term, plain, game, snippet: snippet && snippet.insertText, highlighted: monarch.libs.includes('tterm'),
  hoverPut: hoverAt('screen:put(1, 2, "@")', 9), hoverPressed: hoverAt('screen:pressed("a")', 10),
  hoverScreen: hoverAt('s = tterm.screen(4, 4)', 12),
}));
"""
# The Run panel's side (tterm.js, with Node and a stand-in for the page): a live screen takes the keys at once, sends
# each one over stdin as a line (down, again as it repeats, up), Esc lets go, clicking elsewhere lets go, the second
# player's copy and an ended game take none, and the IDE's own shortcuts (Ctrl+...) pass through.
TTERM_PANEL = r"""
const fs = require('fs'), vm = require('vm');
let active = null;
const document = { get activeElement() { return active; }, querySelectorAll: (sel) => spans.filter((s) => sel === '.tscreen.live' && s.classList.has('live') && s.classList.has('tscreen')) };
const spans = [];
function makeSpan() {
  const handlers = {};
  const classes = new Set();
  const span = { dataset: {}, tabIndex: 0, handlers,
    classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c),
                 toggle: (c, on) => { if (on === undefined ? !classes.has(c) : on) classes.add(c); else classes.delete(c); return classes.has(c); } },
    addEventListener: (k, fn) => { handlers[k] = fn; },
    focus() { if (active !== span) { active = span; handlers.focus?.(); } },
    blur() { if (active === span) { active = null; handlers.blur?.(); } } };
  span.classList.has = (c) => classes.has(c);
  spans.push(span);
  return span;
}
const window = {};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), { window, document });
const T = window.TuffTerm;
const sent = [];
const send = (line) => sent.push(line.replace('\x1b', 'ESC').replace('\x07', 'BEL').trim());
const key = (span, kind, k, code, extra = {}) => { const e = { key: k, code, preventDefault() { this.prevented = true; }, stopPropagation() {}, ...extra };
  span.handlers[kind](e); return !!e.prevented; };
const out = {};
const a = makeSpan();
T.screen(a, { screen: 1, live: 1 }, send);
out.autoFocus = active === a;
out.hintPlaying = a.dataset.hint;
out.left = key(a, 'keydown', 'ArrowLeft', 'ArrowLeft');
key(a, 'keydown', 'ArrowLeft', 'ArrowLeft', { repeat: true });
key(a, 'keyup', 'ArrowLeft', 'ArrowLeft');
key(a, 'keydown', 'A', 'KeyA');
key(a, 'keyup', 'a', 'KeyA');
key(a, 'keydown', ' ', 'Space');
out.ctrlPassed = !key(a, 'keydown', 's', 'KeyS', { ctrlKey: true });
out.f10Passed = !key(a, 'keydown', 'F10', 'F10');
out.shiftPassed = !key(a, 'keydown', 'Shift', 'ShiftLeft');
a.blur();
out.hintAfterBlur = a.dataset.hint;
a.handlers.mousedown({ preventDefault() {} });
out.clickFocus = active === a;
key(a, 'keydown', 'Escape', 'Escape');
out.escLetGo = active !== a;
out.sent = sent.slice();
T.screen(a, { screen: 1 }, send);
out.notLive = !a.classList.has('live') && a.dataset.hint === undefined && a.tabIndex === -1;
sent.length = 0;
out.deadKey = !key(a, 'keydown', 'ArrowUp', 'ArrowUp') && sent.length === 0;
const b = makeSpan();
T.screen(b, { screen: 1, live: 1 }, null);
out.secondPlayer = !b.classList.has('live') && active !== b;
const c = makeSpan();
T.screen(c, { screen: 1, live: 1 }, send);
T.ended();
out.ended = !c.classList.has('live') && active !== c;
out.keyNames = ['ArrowUp', 'Enter', 'Tab', 'Backspace', 'Delete', '7', '!', 'é', 'Shift', 'F5', 'Escape'].map((k) => T.keyName({ key: k }));
console.log(JSON.stringify(out));
"""


def tterm_run(code, name, env=None, stdin="", slow=False):
    """Runs a tterm program with no one to press keys (stdout and stdin are pipes): (exit code, stdout, stderr, seconds)."""
    folder = os.path.join(HERE, "out", "tterm")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    full = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW")}
    full.update({"PYTHONIOENCODING": "utf-8", **(env or {})})
    if slow:
        full["TUFF_SLOW"] = "1"
    t0 = time.perf_counter()
    p = subprocess.run(tuff_cmd() + [path], input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, env=full, cwd=folder)
    return p.returncode, p.stdout, p.stderr, time.perf_counter() - t0


def tterm_messages(raw):
    """The Run panel's messages in some output: [(kind, id, text, look or None)]."""
    out = []
    for kind, rest in re.findall(r"\x1b\]tuff;(\w+);([^\x07]*)\x07", raw):
        parts = rest.split(";")
        text = base64.b64decode(parts[1]).decode("utf-8") if kind in ("say", "rewrite") and len(parts) > 1 else ""
        look = None
        if len(parts) > 2 and parts[2].startswith("rich:"):
            look = json.loads(base64.b64decode(parts[2][5:]).decode("utf-8"))
        out.append((kind, parts[0], text, look))
    return out


def tterm_in_process(c):
    """tuff_tterm.py's own parts, in this process: the keys a terminal sends, Windows' key codes, held from repeats,
    wide characters, a terminal's drawing (only what changed), and the keys the Run panel sends."""
    import tuff
    import tuff_tterm as tt
    c.check(tt.term_keys("\x1b[A\x1b[B\x1b[C\x1b[D\x1bOA\x1b[3~ \r\t\x7fqQ\x1b") ==
            ["up", "down", "right", "left", "up", "delete", "space", "enter", "tab", "backspace", "q", "q", "escape"],
            "a Mac or Linux terminal's keys: arrows (both ways), delete, space, enter, tab, backspace, letters and Esc",
            tt.term_keys("\x1b[A\x1b[B\x1b[C\x1b[D\x1bOA\x1b[3~ \r\t\x7fqQ\x1b"))
    c.check(tt.term_keys("\x1b[1;2A\x1bx") == ["up", "x"], "...shift+up is up, and Alt with a key (ESC x) is the key, not Esc",
            tt.term_keys("\x1b[1;2A\x1bx"))
    c.check([tt.vk_key(v, ch) for v, ch in ((0x25, ""), (0x26, ""), (0x20, " "), (0x0D, "\r"), (0x1B, "\x1b"), (0x41, "A"), (0x31, "!"),
                                             (0x31, ""), (0x63, "3"), (0x10, ""), (0xBA, ";")) ] ==
            ["left", "up", "space", "enter", "escape", "a", "!", "1", "3", None, ";"],
            "Windows' console keys: arrows, space, enter, Esc, letters (Shift doesn't change them), what a key types, the number pad, not Shift")
    r = tt.Repeats()
    first = r.events(["right"], 10.0)
    still = r.events([], 10.2)
    again = r.events(["right"], 10.25)
    gone = r.events([], 10.5)
    c.check(first == [("down", "right")] and still == [] and again == [("down", "right")] and gone == [("up", "right")],
            "in a terminal a key counts as held until a moment after it last came (it comes again as it repeats)", (first, still, again, gone))
    c.check(tt.glyphs("a🐍é́👍🏽中\x07") == [("a", 1), ("🐍", 2), ("é́", 1), ("👍🏽", 2), ("中", 2), (" ", 1)],
            "text in cells: an emoji or a Chinese letter is two cells wide, accents and skin tones stay with their letter, a control character is a space",
            tt.glyphs("a🐍é́👍🏽中\x07"))
    for word, want in (("Space", "space"), (" ", "space"), ("ArrowLeft", "left"), ("esc", "escape"), ("Q", "q"), ("any", "any"),
                       ("shift", None), ("", None), ("ab", None)):
        c.check(tt.key_name(word) == want, f"the key {word!r} is {want!r}", tt.key_name(word))
    # A terminal's drawing, with the console's writes kept here.
    interp = tuff.Interpreter("", HERE)
    written = []
    interp.console.write = written.append
    lib = tt.Lib(interp.rt)
    lib.place = "terminal"
    s = tt.Screen(lib, 6, 3)
    s.put(1, 1, "@", "lime")
    s.put(0, 2, "🐍")
    s.put(1, 2, "x")
    s.show()
    first = "".join(written)
    lime = tuff.ansi_color(tuff.TEXT_COLORS["lime"])
    c.check(first.startswith("\x1b[2J\x1b[H") and f"\x1b[2;1H {lime}@\x1b[39m    \x1b[0m\x1b[K" in first and first.endswith("\x1b[4;1H")
            and "\x1b[3;1H🐍    \x1b[0m\x1b[K" in first and interp.console.rows == 3,
            "a terminal: the first frame clears it and draws each row in its colours (an emoji covers two cells); the cursor waits below", repr(first))
    written.clear()
    s.show()
    c.check(written == [], "...an unchanged screen draws nothing", written)
    s.put(4, 0, "#", "red")
    s.show()
    again = "".join(written)
    c.check(again.startswith("\x1b7\x1b[1;1H") and again.endswith("\x1b8") and "\x1b[2;1H" not in again and "\x1b[2J" not in again,
            "...a change draws only its row, and the cursor goes back where it was", repr(again))
    written.clear()
    interp.console.rows = 0  # what the program's clear() leaves
    s.show()
    c.check(written == [], "...after the program's clear() it stays away until it changes", written)
    s.put(5, 0, "!")
    s.show()
    c.check("".join(written).startswith("\x1b[2J"), "...and then it's drawn whole again", repr("".join(written))[:200])
    s.press("a")
    s.press("b", 5)
    s.press("c")
    s.press("d", 3)
    c.check([k for _, k in s.queue] == ["a", "d", "b", "c"] and [f for f, _ in s.queue] == [1, 3, 5, 6],
            "screen:press: the next frame without a key, or the one it says (in frame order)", s.queue)
    m = [tt.KEY_LINE.fullmatch(x) for x in ("\x1b]tuff;key;down;left\x07", "\x1b]tuff;key;up;;\x07", "\x1b]tuff;key;none\x07", "typed")]
    c.check(m[0].groups() == ("down", "left") and m[1].groups() == ("up", ";") and m[2].groups() == ("none", None) and m[3] is None,
            "the Run panel's key lines (the ; key too), and a typed answer isn't one", [x and x.groups() for x in m])
    if os.name == "nt":
        import ctypes
        rec = tt.console_record()
        key = rec._fields_[1][1]._fields_[0][1]
        c.check(ctypes.sizeof(rec) == 20 and rec.event.offset == 4 and ctypes.sizeof(key) == 16 and key.vk.offset == 6 and key.char.offset == 10
                and key.state.offset == 12, "Windows' console input record has the layout Windows gives it (20 bytes, the key's code at 6)",
                (ctypes.sizeof(rec), rec.event.offset, ctypes.sizeof(key)))
        r, w = os.pipe()
        os.write(w, b"abc")
        waiting = tt.pipe_waiting(r)
        os.read(r, 3)
        os.close(w)
        closed = tt.pipe_waiting(r)
        os.close(r)
        c.check(waiting == 3 and closed is None, "Windows: a pipe's waiting bytes are counted without waiting, and its end is seen", (waiting, closed))

    # The game loop as in a terminal, with keys from a stand-in for the terminal: right held for 3 frames, then let go.
    class Keys:
        gone = False

        def __init__(self):
            self.polls, self.started, self.stopped = 0, False, False

        def start(self):
            self.started = True

        def poll(self):
            self.polls += 1
            return {3: [("down", "right")], 6: [("up", "right")]}.get(self.polls, [])

        def stop(self):
            self.stopped = True
    src = ('mention tterm\nscreen = tterm.screen(8, 2)\nx = 0\nn = 0\nfunc step(dt):\n    n += 1\n    if screen:held("right"):\n'
           '        x += 1\n    screen:clear()\n    screen:put(x, 0, "@")\n    if n is 8:\n        screen:stop()\nscreen:every_frame(step)\n')
    interp = tuff.Interpreter(src, HERE)
    written = []
    interp.console.write = written.append
    program = tuff.Parser(tuff.tokenize(src)).program()
    interp.run_block(program[:1], interp.globals)
    lib = interp.globals.vars["tterm"].members["screen"].fn.__self__
    lib.place, keys = "terminal", Keys()
    lib.input = keys
    t0 = time.perf_counter()
    interp.run_block(program[1:], interp.globals)
    secs = time.perf_counter() - t0
    shown = "".join(written)
    c.check(interp.globals.vars["x"] == 3 and interp.globals.vars["n"] == 8 and keys.started and keys.stopped and 0.3 < secs < 2
            and shown.count("@") >= 3 and lib.running is None,
            f"a terminal's game loop: 20 frames a second ({secs:.2f} s for 8), a held key moves it, and the keys are put back when it stops",
            (interp.globals.vars["x"], interp.globals.vars["n"], keys.started, keys.stopped, secs))


def t_tterm(c):
    """Console only, no window: 1.5.0's tterm (terminal games). With no one to press keys (a pipe), screen:press gives
    frames their keys, the frames don't wait for the clock and only the final screen shows, in both runtimes; a game
    with no stop ends by itself; mistakes stop the run on their line and --check finds the certain ones; in TuffCode's
    Run panel protocol (TUFF_IDE=1, keys sent over stdin) it moves with held keys, Esc ends it and input() gets the
    answer typed during it; with stdin closed (tuff_run) it runs at once and says the screen once; the Snake starter;
    tuff_tterm.py's parts in this process; the editor and the Run panel's side with Node; and Build exe packs it."""
    if hasattr(sys.stdout, "reconfigure"):  # box lines and emoji in what it prints, on a console that can't show them
        sys.stdout.reconfigure(errors="backslashreplace")
    code, out, err, secs = tterm_run(TTERM_PROGRAM, "moves.tuf")
    lines = out.splitlines()
    c.check(code == 0 and lines[:5] == [r.rstrip() for r in TTERM_FRAME] and lines[5:] == TTERM_AFTER,
            f"a pipe: the keys from screen:press move it, and only the final screen shows, as text ({secs:.1f} s)", out + err)
    slow = interp_run(os.path.join(HERE, "out", "tterm", "slow"), TTERM_PROGRAM, True)
    fast = interp_run(os.path.join(HERE, "out", "tterm", "fast"), TTERM_PROGRAM, False)
    c.check(slow == fast and slow[0] == 0, "...the same in the tree walker (TUFF_SLOW=1) and the compiled runtime", (slow, fast))

    idle = "mention tterm\nscreen = tterm.screen(5, 2)\nn = 0\nfunc step(dt):\n    n += 1\nscreen:every_frame(step)\nsay n\n"
    code, out, err, secs = tterm_run(idle, "idle.tuf")
    c.check(code == 0 and out.strip().splitlines()[-1] == "100" and secs < 10, f"a game that never stops ends by itself after 100 frames ({secs:.1f} s)", out + err)
    busy = idle.replace("    n += 1\n", "    n += 1\n    screen:press(\"x\")\n")
    code, out, err, secs = tterm_run(busy, "busy.tuf")
    c.check(code == 0 and out.strip().splitlines()[-1] == "5000" and secs < 30, f"...and one that presses a key every frame ends after 5000 ({secs:.1f} s)", out + err)
    later = idle.replace("screen:every_frame", 'screen:press("x", 150)\nscreen:every_frame')
    code, out, err, secs = tterm_run(later, "later.tuf")
    c.check(code == 0 and out.strip().splitlines()[-1] == "250", "...100 frames after the last key (one on frame 150)", out + err)
    loop = ("mention tterm\nscreen = tterm.screen(8, 1)\nfor i in range(0, 7):\n    screen:clear()\n    screen:put(i, 0, \"*\")\n"
            "    wait(0.01)\nsay \"done\"\n")
    code, out, err, secs = tterm_run(loop, "loop.tuf")
    c.check(code == 0 and out.splitlines() == ["done", "       *"], "a loop of its own (with wait) shows only how it ended, when the program ends", out + err)

    for i, (prog, line, says) in enumerate(TTERM_ERRORS):
        runs = [tterm_run(prog + "\n", f"error{i}.tuf", slow=slow) for slow in (False, True)]
        code, out, err, _ = runs[0]
        shown = prog.splitlines()[line - 1].strip()
        c.check(code == 1 and f"Tuff error on line {line}: " in err and says in err and runs[0][:3] == runs[1][:3],
                f"{shown!r} stops on line {line}: {says[:50]!r} (in both runtimes)", (err, runs[1][2]))
    code, out, err, _ = tterm_run(TTERM_ERRORS[8][0] + "\n", "error_frame.tuf")
    c.check(out.splitlines()[:2] == ["", "  @"], "...an error inside the game shows the screen as it was first", out)

    # The Run panel (TUFF_IDE=1): keys come over stdin as lines, as tterm.js sends them.
    ide_prog = ('mention tterm\nscreen = tterm.screen(16, 3)\nx = 1\nhits = 0\nfunc step(dt):\n    if screen:held("right"):\n        x += 1\n'
                '    if screen:pressed("space"):\n        hits += 1\n    screen:clear()\n    screen:put(x, 1, "@", "lime")\n'
                'screen:every_frame(step)\nsay f"moved {x > 4} hits {hits}"\nname = input "Name? "\nsay "hi " + name\n')
    folder = os.path.join(HERE, "out", "tterm")
    path = os.path.join(folder, "ide.tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ide_prog)
    env = {**{k: v for k, v in os.environ.items() if k != "TUFF_SLOW"}, "TUFF_IDE": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.Popen(tuff_cmd() + [path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=folder)
    got = []
    import threading
    reader = threading.Thread(target=lambda: got.append(p.stdout.read()), daemon=True)
    reader.start()

    def send(line):
        p.stdin.write(line.encode("utf-8"))
        p.stdin.flush()
    try:
        time.sleep(1.0)
        send("\x1b]tuff;key;down;right\x07\n")
        time.sleep(0.5)
        send("\x1b]tuff;key;up;right\x07\n\x1b]tuff;key;down;space\x07\n\x1b]tuff;key;up;space\x07\n")
        time.sleep(0.3)
        send("Sam\n")
        time.sleep(0.2)
        send("\x1b]tuff;key;down;escape\x07\n")
        p.wait(15)
    except (subprocess.TimeoutExpired, OSError):
        p.kill()
    reader.join(5)
    p.stdin.close()
    p.stderr.close()
    raw = got[0].decode("utf-8", errors="replace") if got else ""
    msgs = tterm_messages(raw)
    screens = [m for m in msgs if m[3] and m[3].get("screen")]
    said = [m[2] for m in msgs if m[0] == "say" and not (m[3] and m[3].get("screen"))]
    c.check(p.returncode == 0 and screens and screens[0][0] == "say" and screens[0][3].get("live") == 1 and screens[0][3]["w"] == 16
            and all(m[0] == "rewrite" and m[1] == screens[0][1] for m in screens[1:]),
            "the Run panel: the screen is a say line marked as a live screen (16 across), rewritten in place", [m[:2] for m in screens[:5]])
    c.check(screens and "live" not in screens[-1][3] and screens[-1][3].get("runs") and screens[-1][3]["runs"][0][3] == tuff_tterm_lime(),
            "...the last frame isn't live any more (the panel lets go of the keys), and its colours are runs", screens[-1][3] if screens else None)
    c.check(said[:1] == ["moved true hits 1"] and said[1:] == ["hi Sam"],
            "...a held key moves it, a press counts once, Esc ends the game, and input() gets the answer typed while it ran", said)
    c.check(len(screens) < 120, f"...it only sends a frame that changed ({len(screens)} for about 2 seconds)", len(screens))

    # tuff_run: TUFF_IDE=1 with the answers given and stdin closed. No one can press a key, so it runs at once.
    code, out, err, secs = tterm_run(TTERM_PROGRAM, "tuff_run.tuf", env={"TUFF_IDE": "1", "TUFF_ECHO_INPUT": "1"}, stdin="Sam\n")
    msgs = tterm_messages(out)
    screens = [m for m in msgs if m[3] and m[3].get("screen")]
    c.check(code == 0 and len(screens) == 1 and [r.rstrip() for r in screens[0][2].split("\n")] == [r.rstrip() for r in TTERM_FRAME]
            and "live" not in screens[0][3] and secs < 10,
            f"tuff_run (stdin closed): it runs at once and says the final screen once ({secs:.1f} s)", [m[:3] for m in msgs])

    # The Snake starter: down on frame 2 turns it, it goes down to the wall and the game is over; Esc stops it.
    with open(os.path.join(GAMES, "tterm_snake.tuf"), encoding="utf-8") as f:
        snake = f.read()
    c.check(subprocess.run(tuff_cmd() + ["--check", os.path.join(GAMES, "tterm_snake.tuf")], capture_output=True, text=True,
                           encoding="utf-8").stdout.strip() == "OK", "--check accepts the Snake starter (games/tterm_snake.tuf)")
    turned = snake.replace("draw()\nscreen:every_frame(step)", 'screen:press("down", 2)\ndraw()\nscreen:every_frame(step)')
    code, out, err, _ = tterm_run(turned, "snake_down.tuf")
    rows = out.splitlines()
    c.check(code == 0 and len(rows) >= 18 and rows[14][8] == "@" and rows[13][8] == "o" and rows[12][8] == "o" and "GAME OVER" in rows[8]
            and rows[-1] == "Game over! You scored 0." and rows[16].strip() == "arrows: steer   esc: stop",
            "the Snake starter: a key turns it down, it hits the bottom wall and the game is over", out + err)
    stopped = snake.replace("draw()\nscreen:every_frame(step)", 'screen:press("escape", 4)\ndraw()\nscreen:every_frame(step)')
    code, out, err, _ = tterm_run(stopped, "snake_esc.tuf")
    c.check(code == 0 and out.splitlines()[-1] == "You stopped with 0 points." and "GAME OVER" not in out, "...and Esc stops it", out + err)

    folder = os.path.join(HERE, "out", "tterm")
    for i, (code_, want) in enumerate(TTERM_CHECKS):
        path = os.path.join(folder, f"check{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(TTERM_HEAD + code_ + "\n")
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        shown = code_.splitlines()[-1].strip()
        if want == "OK":
            c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"--check accepts: {shown}", (p.stdout + p.stderr)[:300])
        else:
            c.check(p.returncode == 1 and want in p.stderr, f"--check on {shown!r} says {want[:55]!r}", p.stderr[:300])

    console, _games, _learned = interp_corpus()
    names = [n for n, src in console if "mention tterm" in src]
    c.check("tuffcode/test/tgame/games/tterm_snake.tuf" in names and sum(n.startswith("guide ") for n in names) >= 2,
            "the interp test's corpus runs the Snake starter and the guide's tterm examples in both runtimes", names)

    tterm_in_process(c)

    try:
        p = subprocess.run(["node", "-e", TTERM_LANG, os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        q = subprocess.run(["node", "-e", TTERM_PANEL, os.path.join(REPO, "tuffcode", "renderer", "js", "tterm.js")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the editor and Run panel checks")
        p = q = None
    if p is not None:
        try:
            t = json.loads(p.stdout)
        except ValueError:
            t = None
        c.check(t is not None, "the editor checks ran", (p.stdout + p.stderr)[-600:])
        t = t or {}
        c.check("tterm" in t.get("libs", []) and t.get("highlighted") and "tterm" in t.get("mentions", []) and t.get("libNames") == ["screen"],
                "the editor knows tterm: highlighted, offered after mention, and tterm. offers screen", [t.get("mentions"), t.get("libNames")])
        want = {"put", "text", "box", "clear", "get", "pressed", "held", "press", "every_frame", "stop"}
        c.check(want <= set(t.get("term", [])), "screen: in a tterm file offers all ten methods", sorted(want - set(t.get("term", []))))
        c.check(not {"put", "press"} & set(t.get("plain", [])) and not {"put", "press"} & set(t.get("game", [])),
                "...and tterm's own (put, press) don't crowd other files", [x for x in ("put", "press") if x in t.get("plain", []) + t.get("game", [])])
        c.check((t.get("hoverPut") or "").startswith("```tuff\nscreen:put(x, y, \"@\", \"lime\")") and "In tterm, screen:pressed" in (t.get("hoverPressed") or "")
                and "A grid of letters" in (t.get("hoverScreen") or ""),
                "hovers: screen:put, screen:pressed (after tgame's) and tterm.screen", [t.get("hoverPut"), t.get("hoverPressed"), t.get("hoverScreen")])
        snip = t.get("snippet") or ""
        if snip:
            snip_code = re.sub(r"\$\{\d+:([^}]*)\}", r"\1", snip).replace("$0", "")
            path = os.path.join(folder, "snippet.tuf")
            with open(path, "w", encoding="utf-8") as f:
                f.write(snip_code)
            chk = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
            run = tterm_run(snip_code, "snippet_run.tuf")
        c.check(snip and chk.stdout.strip() == "OK" and run[0] == 0 and "@" in run[1], "the 'tterm game' snippet passes --check and runs", snip)
    if q is not None:
        try:
            u = json.loads(q.stdout)
        except ValueError:
            u = None
        c.check(u is not None, "the Run panel checks ran", (q.stdout + q.stderr)[-600:])
        u = u or {}
        c.check(u.get("autoFocus") and u.get("hintPlaying") == "Esc to let go", "the Run panel: a game that starts takes the keys at once", u)
        c.check(u.get("sent") == ["ESC]tuff;key;down;leftBEL", "ESC]tuff;key;down;leftBEL", "ESC]tuff;key;up;leftBEL", "ESC]tuff;key;down;aBEL",
                                  "ESC]tuff;key;up;aBEL", "ESC]tuff;key;down;spaceBEL", "ESC]tuff;key;noneBEL", "ESC]tuff;key;down;escapeBEL",
                                  "ESC]tuff;key;noneBEL"] and u.get("left"),
                "...each key goes over stdin: down (and again as it repeats), up, letters in lower case, none when it lets go, and Esc", u.get("sent"))
        c.check(u.get("ctrlPassed") and u.get("f10Passed") and u.get("shiftPassed"), "...Ctrl+S, F10 and Shift go on to the IDE", u)
        c.check(u.get("hintAfterBlur") == "Click to play" and u.get("clickFocus") and u.get("escLetGo"),
                "...clicking elsewhere lets go (\"Click to play\"), a click takes the keys again, and Esc lets go", u)
        c.check(u.get("notLive") and u.get("deadKey") and u.get("secondPlayer") and u.get("ended"),
                "...a finished game, the second player's copy and an ended run take no keys", u)
        c.check(u.get("keyNames") == ["up", "enter", "tab", "backspace", "delete", "7", "!", "é", None, None, "escape"],
                "...key names as tuff_tterm.py's: what a key types, or its name; none for Shift and F5", u.get("keyNames"))

    build = open(os.path.join(REPO, "tuffcode", "build.js"), encoding="utf-8").read()
    pkg = json.load(open(os.path.join(REPO, "tuffcode", "package.json"), encoding="utf-8"))
    html = open(os.path.join(REPO, "tuffcode", "renderer", "index.html"), encoding="utf-8").read()
    c.check("'tuff_tterm.py'" in build and "'--hidden-import', 'tuff_tterm'" in build and "&& !usesTerm" in build,
            "Build exe packs tuff_tterm.py for a tterm game, as a console app", None)
    c.check(all("--hidden-import tuff_tterm" in pkg["scripts"][s] for s in ("build:runtime", "build:runtime:mac"))
            and any(r.get("from") == "../tuff_tterm.py" for r in pkg["build"]["extraResources"]),
            "TuffCode's own runtime has tuff_tterm (and Build exe's copy of the files)", None)
    c.check(html.index("js/tterm.js") < html.index("js/ide.js"), "index.html loads tterm.js before ide.js", None)


def tuff_tterm_lime():
    import tuff
    return tuff.TEXT_COLORS["lime"]


# ---------------------------------------------------------------- tmusic, music from notes (1.5.0)

# No test here makes a sound: TUFF_NO_SOUND=1 for everything these tests run, and a program's output goes to a pipe,
# where tmusic plays nothing anyway. Songs are made in out/music, not in the temporary folder's tuff-music.
os.environ.setdefault("TUFF_NO_SOUND", "1")
os.environ.setdefault("TUFF_MUSIC_DIR", os.path.join(OUT, "music"))

TMUSIC_PROGRAM = '''mention tmusic
song = tmusic.song(120)
say song
song:track("piano", "C4 E4 G4 E4 | F4 A4 C5 .")
song:track("bass", "C2*4 | F2*4", 60)
song:track("drums", "kick hat snare hat | kick+crash hat snare hat")
say song
say song:length()
say tmusic.song(90):track("pluck", "C4 D4/2 E4/2 F4*1.5 G4*3/2"):length()
fast = tmusic.song(400)
fast:track("chip", "c#5 Eb5 b4+d5")
say fast:length()
tmusic.play("C4 E4 G4")
tmusic.play("A3 . A3*2", "organ", 200)
tmusic.play(fast)
song:play()
song:loop()
song:stop()
song:save("theme.wav")
say file.exists("theme.wav")
quiet = tmusic.song(60)
quiet:track("flute", ". . .")
say quiet:length()
try:
    tmusic.play("C4 C9# G4")
catch problem:
    say problem
try:
    empty = tmusic.song()
    empty:play()
catch problem:
    say problem
say "end"
'''
TMUSIC_OUTPUT = ["<song: 0 tracks, 0 seconds>", "<song: 3 tracks, 4 seconds>", "4", "3.333", "0.45", "true", "3",
                 "\"C9#\" (note 2) has its # after the octave (it goes before, like C#4), and there's no octave 9: octaves go "
                 "from 0 to 8 (C4 is middle C).",
                 'This song has no tracks yet. Add one first, like song:track("piano", "C4 E4 G4").', "end"]
# The note reader: (notes, drums?, how many beats, the notes as (start, beats, pitches)), with fractions as text.
TMUSIC_NOTES = [
    ("C4 D4 E4 F4 G4 A4 B4 C5", False, "8", [(str(i), "1", (p,)) for i, p in enumerate([60, 62, 64, 65, 67, 69, 71, 72])]),
    ("c#4 Db4 e#4 Fb4 B#3 Cb5", False, "6", [(str(i), "1", (p,)) for i, p in enumerate([61, 61, 65, 64, 60, 71])]),
    ("A0 C8 A4", False, "3", [("0", "1", (21,)), ("1", "1", (108,)), ("2", "1", (69,))]),
    ("C4 E4/2 .*2 G4+B4*3/2", False, "5", [("0", "1", (60,)), ("1", "1/2", (64,)), ("7/2", "3/2", (67, 71))]),
    ("| C4*1.5 | . |\n E4/4 |", False, "11/4", [("0", "3/2", (60,)), ("5/2", "1/4", (64,))]),
    ("kick+hat snare/2 . CRASH*2", True, "9/2", [("0", "1", ("kick", "hat")), ("1", "1/2", ("snare",)), ("5/2", "2", ("crash",))]),
    (". . .", False, "3", []),
]
# Mistakes in notes: (notes, drums?, who, what tmusic says, where in the text the note starts).
TMUSIC_NOTE_ERRORS = [
    ("C4 E4 C9# G4", False, "tmusic.play", "\"C9#\" (note 3) has its # after the octave (it goes before, like C#4), and there's no "
                                           "octave 9: octaves go from 0 to 8 (C4 is middle C).", 6),
    ("C4#", False, "tmusic.play", '"C4#" has its # after the octave: write C#4.', 0),
    ("C9", False, "tmusic.play", "\"C9\": octaves go from 0 to 8 (C4 is middle C), so there's no C9.", 0),
    ("E4 G", False, "tmusic.play", '"G" (note 2) needs its octave after it, like G4 (C4 is middle C).', 3),
    ("H4", False, "tmusic.play", '"H4" isn\'t a note. A note is a letter from A to G, then # (sharp) or b (flat) if it needs one', 0),
    ("C4, E4", False, "tmusic.play", '"C4," (note 1): put spaces between notes, not commas, like "C4 E4 G4".', 0),
    ("C4*", False, "tmusic.play", '"C4*": put a number after the *, like C4*2 (twice as long) or C4/2 (half as long).', 0),
    ("C4/0", False, "tmusic.play", '"C4/0" would last 0 beats.', 0),
    ("C4 *2", False, "tmusic.play", '"*2" (note 2) needs a note before the *, like C4*2 (or .*2 for a rest).', 3),
    ("C4+", False, "tmusic.play", '"C4+": a chord needs a note on each side of its +, like C4+E4+G4.', 0),
    ("C4+.", False, "tmusic.play", "\"C4+.\": a rest (.) can't be part of a chord.", 0),
    ("C##4", False, "tmusic.play", '"C##4" has more than one # or b. A note has one at most, like C#4 or Db4.', 0),
    ("C4.", False, "tmusic.play", '"C4." isn\'t a note. For a note one and a half times as long, write C4*1.5.', 0),
    ("C4*2E4", False, "tmusic.play", '"C4*2E4": put a space between two notes, like "C4*2 E4".', 0),
    ("C4 kick", False, "tmusic.play", '"kick" (note 2) is a drum. Drums go in a track of their own, like tmusic.play("kick hat snare hat", "drums").', 3),
    ("C4 snare", False, "song:track", 'like song:track("drums", "kick hat snare hat").', 3),
    ("", False, "tmusic.play", 'tmusic.play needs some notes, like tmusic.play("C4 E4 G4").', 0),
    (" | | ", False, "song:track", 'song:track needs some notes, like song:track("piano", "C4 E4 G4").', 0),
    ("kick C4", True, "song:track", '"C4" (note 2) is a note, but this is a drums track. Drums are kick, snare, hat, clap, tom and crash', 5),
    ("kick kik", True, "song:track", '"kik" (note 2) isn\'t a drum. Did you mean "kick"?', 5),
]
# The test song for the .wav: every instrument and every drum, 9 beats at 150 beats a minute (3.6 seconds). Its
# SHA-256 only changes when the synth does (then tuff_tmusic.SYNTH goes up too).
TMUSIC_SONG = [("piano", "C4 E4 G4 E4 | F4+A4 C5/2 B4/2 . C5*2", 100), ("chip", "c#5/2 Eb5/2 G5 . b4*1.5 D5/2", 60),
               ("bass", "C2*2 F2*2 | G1*3/2 C2*5/2", 80), ("pluck", "G3 . B3 D4 | G4*4", 90),
               ("bell", "E6 . B5*2 | .*2 E6/3 G6/3 B6/3", 50), ("organ", "C4+E4+G4*4 | B3+D4+G4*4", 40),
               ("flute", ". . G5*2 | A5 G5 E5*2", 70), ("drums", "kick hat snare hat | kick+crash clap tom hat/2 hat/2", 100)]
TMUSIC_SONG_HASH = "02effbde46c073972ec66059a4580f9ce40b7deaf1de2460c51efd0f355150a9"
# Mistakes in a program: (code after "mention tmusic", line, column, what the run and --check say, whether the run can
# be tried here (a game's can't: it opens a window), whether --check finds it too).
TMUSIC_MISTAKES = [
    ('tmusic.play("C4 E4 C9# G4")', 2, 20, '"C9#" (note 3) has its # after the octave', True, True),
    ('tmusic.play("C4 E4 G")', 2, 20, '"G" (note 3) needs its octave after it, like G4', True, True),
    ('tmusic.play("C4 E4", "guitar")', 2, 22, 'tmusic doesn\'t have the instrument "guitar". Did you mean "pluck"?', True, True),
    ('tmusic.play("piano", "C4 E4")', 2, 12, 'tmusic.play takes the notes first, then the instrument', True, True),
    ('tmusic.play("C4", "piano", 900)', 2, 28, "tmusic.play can be from 20 to 400 beats a minute (120 is a usual speed), so 900 is too fast.", True, True),
    ('tmusic.play(5)', 2, 13, 'tmusic.play needs the notes as text, like tmusic.play("C4 E4 G4"), not a number.', True, True),
    ('tmusic.song("fast")', 2, 13, "tmusic.song needs a speed in beats a minute, as a number, like tmusic.song(120), not text.", True, True),
    ('tmusic.song(5)', 2, 13, "tmusic.song can be from 20 to 400 beats a minute (120 is a usual speed), so 5 is too slow.", True, True),
    ('song = tmusic.song(120)\nsong:track("drums", "kick snare C4")', 3, 33, '"C4" (note 3) is a note, but this is a drums track.', True, True),
    ('song = tmusic.song(120)\nsong:track("piano", "C4 E4", 150)', 3, 30, "A track's volume goes from 0 to 100 (100 if you leave it out), not 150.", True, True),
    ('song = tmusic.song(120)\nsong:track("piano", "C4", "loud")', 3, 27, "A track's volume is a number from 0 to 100", True, True),
    ('song = tmusic.song(120)\nsong:track("C4 E4", "piano")', 3, 5, "song:track takes the instrument first, then the notes", True, True),
    ('song = tmusic.song(120)\nsong:track(5, "C4")', 3, 12, "song:track needs the instrument's name as text first", True, True),
    ('song = tmusic.song(120)\nsong:save("theme.mp3")', 3, 11, 'song:save makes a .wav file, like song:save("theme.wav"), not "theme.mp3".', True, True),
    ('song = tmusic.song(120)\nsong:shuffle()', 3, 5, "A song doesn't have :shuffle. Try one of: track, play, loop, stop, save, length.", True, True),
    ('song = tmusic.song(120)\nsong:lop()', 3, 5, "A song doesn't have :lop. Did you mean :loop?", True, True),
    ('song = tmusic.song(120)\nsong:track("piano")', 3, 5, "song:track got the wrong number of inputs (1).", True, True),
    ('tune = "C4 E4 G#9"\ntmusic.play(tune, "bell")', 3, 13, "\"G#9\" (note 3): octaves go from 0 to 8 (C4 is middle C), so there's no G#9.", True, True),
    ('tmusic.plya("C4")', 2, 7, "tmusic doesn't have 'plya'. It has: play, song.", True, True),
    ('song = tmusic.song(120)\nsong:track("piano", "C4*1000 C4*1000")', 3, 1,
     "These notes would play for 16 minutes 40 seconds: song:track makes songs up to 5 minutes long.", True, False),
    ('song = tmusic.song()\nsong:play()', 3, 1, 'This song has no tracks yet. Add one first, like song:track("piano", "C4 E4 G4").', True, False),
    ('mention tgame\ngame = tgame.window("x")\nsong = tmusic.song()\nsong:track("chip", "C5")\nfunc step(dt):\n    song:play()\ngame:every_frame(step)',
     7, 9, "song:play waits until the music ends, so the game freezes until then. Play a song in a game with game:sound(song)", False, True),
    ('mention tgame\ngame = tgame.window("x")\nfunc hit(x, y):\n    tmusic.play("C5 G5")\ngame:clicked(hit)',
     5, 16, "tmusic.play waits until the music ends, so the game freezes until then.", False, True),
]
# Programs --check has to accept (each after "mention tmusic").
TMUSIC_GOOD = [
    'func jam(s, notes):\n    s:track("piano", notes)\n    s:loop()\nsong = tmusic.song(100)\njam(song, "C4 E4")\nsong:stop()',
    'kit = "drums"\nbeat = tmusic.song()\nbeat:track(kit, "kick snare")\nbeat:track("Drums", "kick+hat . clap/2 tom/2")',
    'for name in ["piano", "chip"]:\n    tmusic.play("C4 E4", name)',
    'song = tmusic.song(120):track("bell", "C5 E5")\nsay song:length() + 1\ntmusic.play(song)\ntmusic.play(song:track("bass", "C2"))',
    'notes = "C4"\nnotes += " Z9"\ntmusic.play(notes)',
    'try:\n    tmusic.play("C9#")\n    song = tmusic.song(999)\ncatch problem:\n    say problem',
    'mention tgame\ngame = tgame.window("x")\nsong = tmusic.song()\nsong:track("chip", "C5")\ngame:music(song)\ngame:sound(song)\nsong:save("a.wav")\n'
    'func step(dt):\n    game:sound(song)\ngame:every_frame(step)',
    'speed = 90\nsong = tmusic.song(speed)\nsong:track("organ", "c4 e4 g4", speed - 40)\nsong:save("Out.WAV")',
]
# Tuff Engine's preview and a run with no window (headless.py) of a game with a song.
TMUSIC_GAME = '''mention tgame
mention tmusic
game = tgame.window("Tune", 300, 200)
theme = tmusic.song(140)
theme:track("chip", "E5 G5 A5 G5 | E5 D5 C5 .")
theme:track("drums", "kick hat snare hat | kick hat snare hat")
ding = tmusic.song(240)
ding:track("bell", "E6 B6*2")
game:music(theme)
count = 0
while game:open():
    game:frame()
    count += 1
    if count == 3:
        game:sound(ding)
    if count == 5:
        game:close()
say "frames " + count
'''
# The editor (renderer/js/tuff-lang.js): tmusic's functions, a song's methods in a file that mentions tmusic, the
# snippet, and the hover on a note in a tmusic string.
TMUSIC_LANG = r"""
const fs = require('fs'), vm = require('vm');
const window = {}, ctx = { window };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
let monarch = null, hover = null, completion = null;
const monaco = { Range: class { constructor(...a) { this.a = a; } }, editor: { defineTheme() {} }, languages: {
  register() {}, setMonarchTokensProvider(_id, def) { monarch = def; }, setLanguageConfiguration() {},
  registerHoverProvider(_id, p) { hover = hover || p; }, registerDefinitionProvider() {}, registerReferenceProvider() {},
  registerRenameProvider() {}, registerDocumentSymbolProvider() {}, registerSignatureHelpProvider() {}, registerColorProvider() {},
  registerCompletionItemProvider(_id, p) { completion = p; },
  CompletionItemKind: new Proxy({}, { get: (_t, k) => k }), CompletionItemInsertTextRule: {}, IndentAction: {}, SymbolKind: {} } };
window.defineTuffTheme = () => {};
window.registerTuff(monaco, '#3574f0');
const model = (src, col) => { const lines = src.split('\n'); return { getLinesContent: () => lines, getLineContent: (n) => lines[n - 1],
  getValue: () => src, getWordUntilPosition: () => ({ startColumn: col || 1, endColumn: col || 1 }),
  getWordAtPosition: ({ lineNumber, column }) => { for (const m of lines[lineNumber - 1].matchAll(/\w+/g))
    if (m.index < column && column <= m.index + m[0].length) return { word: m[0], startColumn: m.index + 1, endColumn: m.index + 1 + m[0].length };
    return null; } }; };
const line = 'song:track("piano", "C#4 Bb3*2 | . C4+E4+G4/2 kick")';
const at = (s) => line.indexOf(s) + 1;
const tip = (src, col) => { const h = hover.provideHover(model(src), { lineNumber: 1, column: col }); return h ? [h.contents[1].value, h.range.a] : null; };
const labels = (src, col, ln = 1) => completion.provideCompletionItems(model(src, col), { lineNumber: ln, column: col }).suggestions.map((s) => s.label);
console.log(JSON.stringify({
  sharp: tip(line, at('#4')), flat: tip(line, at('Bb3') + 3), rest: tip(line, at('. C4')), chord: tip(line, at('E4+')),
  drum: tip(line, at('kick')), instrument: tip(line, at('piano')), play: tip('tmusic.play("C4 E4")', 14), plain: tip('say "C4 E4"', 7),
  lib: tip('mention tmusic', 10), fn: tip('tmusic.play("C4")', 9),
  song: labels('mention tmusic\nsong = tmusic.song(120)\nsong:', 6, 3), other: labels('x = [1]\nx:', 3, 2),
  funcs: labels('mention tmusic\ntmusic.', 8, 2), mention: labels('mention ', 9),
  snippet: completion.provideCompletionItems(model(''), { lineNumber: 1, column: 1 }).suggestions.find((s) => s.label === 'tmusic')?.insertText,
  libs: monarch.libs,
}));
"""


def tmusic_run(folder, name, code, env=None, args=(), timeout=60):
    """Runs a program (or --check) through a pipe, so no sound: (exit code, stdout, stderr, seconds)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    full = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW", "TUFF_NO_WRITES")}
    full.update({"PYTHONIOENCODING": "utf-8", **(env or {})})
    full = {k: v for k, v in full.items() if v is not None}
    t0 = time.perf_counter()
    p = subprocess.run(tuff_cmd() + [*args, path], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       env=full, cwd=folder, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout, p.stderr, time.perf_counter() - t0


def tuff_error_at(stderr):
    """The first Tuff error's (line, column, message): the column from the ^ under the line, or None."""
    lines = stderr.splitlines()
    first = next((i for i, x in enumerate(lines) if x.startswith("Tuff error on line ")), None)
    if first is None:
        return None, None, stderr.strip()
    head, msg = lines[first][len("Tuff error on line "):].split(": ", 1)
    caret = lines[first + 2] if first + 2 < len(lines) and lines[first + 2].strip() == "^" else ""
    return int(head), (caret.index("^") - len(f"  {head} | ") + 1) if caret else None, msg


def tmusic_players(c, tm):
    """A terminal's players, with stand-ins for winsound and afplay, so nothing plays: winsound's one sound at a time
    (a tune cuts a loop off, and the loop comes back after it), the loops stopping at the program's end (after a game's
    window), and afplay on a thread of its own. Then where the sound goes for a pipe, TUFF_NO_SOUND and the preview."""
    import threading
    import types
    calls, waits, hooks = [], [], []
    rt = types.SimpleNamespace(finish_hooks=hooks, on_finish=hooks.append,
                               interp=types.SimpleNamespace(b_wait=waits.append, console=types.SimpleNamespace(write=calls.append)))
    fake = types.ModuleType("winsound")
    fake.SND_FILENAME, fake.SND_ASYNC, fake.SND_NODEFAULT, fake.SND_LOOP = 0x20000, 1, 2, 8
    fake.PlaySound = lambda path, flags: calls.append((path, flags & 8 and "loop"))
    real = sys.modules.get("winsound")
    old_where = tm.Player.where
    sys.modules["winsound"] = fake
    try:
        tm.Player.where = lambda self: "winsound"
        p = tm.Player(rt)
        p.play("s1", "loop.wav", 2, loop=True)
        p.play("s2", "tune.wav", 1.5)
        c.check(calls == [("loop.wav", "loop"), ("tune.wav", 0), ("loop.wav", "loop")] and waits == [1.5],
                "winsound: a loop, then a tune played once (waiting 1.5 s), then the loop comes back", (calls, waits))
        del calls[:]
        p.stop("s1")
        p.play("s2", "tune.wav", 1)
        c.check(calls == [(None, 0), ("tune.wav", 0)] and not p.loops, "...and once the loop is stopped, it doesn't come back", calls)
        p.play("s1", "loop.wav", 2, loop=True)
        del calls[:]
        later = lambda: calls.append("the game's window ran")
        hooks.append(later)
        for hook in hooks:  # the program's end, as run_file goes through them
            hook()
        c.check(calls == ["the game's window ran", (None, 0)] and not p.loops,
                "at the program's end the loop stops, after a game's window that was added after it", calls)
        procs = []

        class Proc:
            def __init__(self, args, **_kw):
                self.args, self.done = args, threading.Event()
                procs.append(self)

            def wait(self):
                self.done.wait(5)

            def poll(self):
                return 0 if self.done.is_set() else None

            def terminate(self):
                self.done.set()
        old_popen = tm.subprocess.Popen
        tm.subprocess.Popen = Proc
        try:
            tm.Player.where = lambda self: "afplay"
            q = tm.Player(rt)
            q.play("s1", "loop.wav", 2, loop=True)
            for _ in range(100):
                if procs:
                    break
                time.sleep(0.01)
            q.stop("s1")
            time.sleep(0.1)
            c.check(len(procs) == 1 and procs[0].args == ["afplay", "loop.wav"] and procs[0].done.is_set() and not q.running,
                    "afplay plays a loop on a thread of its own, and song:stop() stops it", [x.args for x in procs])
        finally:
            tm.subprocess.Popen = old_popen
    finally:
        tm.Player.where = old_where
        if real is not None:
            sys.modules["winsound"] = real
        else:
            sys.modules.pop("winsound", None)
    saved = {k: os.environ.get(k) for k in ("TUFF_NO_SOUND", "TUFF_SCENE")}
    try:
        modes = []
        for env in ({"TUFF_NO_SOUND": "1"}, {"TUFF_SCENE": "1"}, {}):
            for k in saved:
                os.environ.pop(k, None)
            os.environ.update(env)
            modes.append(tm.Player(rt).mode if not sys.stdout.isatty() or env else None)
        c.check(modes == [None, None, None], "no sound with TUFF_NO_SOUND=1, in Tuff Engine's preview, or in a pipe", modes)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def t_tmusic(c):
    """1.5.0, console only (no window and no sound: a pipe and TUFF_NO_SOUND=1): tmusic. The note reader, its mistakes
    and a fuzz of it; the synth's .wav (its format, its length and a hash that stays the same); songs kept by their
    notes; a program in both runtimes; the mistakes the run and --check find (at the note itself) and programs --check
    accepts; a pipe doesn't wait; the Run panel's music messages (TUFF_IDE=1, still a pipe); a game's music (headless.py
    and --scene); the window's shared folder; the editor's docs and hovers (Node); and the guide's examples."""
    import fractions
    import hashlib
    import random as rnd
    import shutil
    import urllib.request
    import wave
    import tuff_tmusic as tm
    folder = os.path.join(OUT, "tmusic")
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    music = os.path.join(folder, "music")
    F = fractions.Fraction

    # ---- the notes
    for text, drums, beats, want in TMUSIC_NOTES:
        events, total = tm.read_notes(text, drums)
        got = [(str(s), str(b), p) for s, b, p in events]
        c.check(got == want and total == F(beats), f"the notes {text!r} read as they should ({beats} beats)", (got, total))
    for text, drums, who, says, at in TMUSIC_NOTE_ERRORS:
        try:
            tm.read_notes(text, drums, who)
            got = None
        except tm.MusicError as err:
            got = (err.msg, err.at)
        c.check(got is not None and says in got[0] and got[1] == at, f"{text!r} stops with: {says[:70]}", got)
    c.check(tm.find_instrument(" Piano ") == "piano" and tm.find_instrument("DRUMS") == "drums", "instruments in any case, with spaces around")
    try:
        tm.find_instrument("guitar")
        got = None
    except tm.MusicError as err:
        got = err.msg
    c.check(got == 'tmusic doesn\'t have the instrument "guitar". Did you mean "pluck"? Instruments: piano, chip, bass, pluck, bell, organ, flute and drums.',
            "an instrument it doesn't have: the closest one, and all of them", got)
    # A fuzz: anything typed gives notes or a MusicError (never a crash), and notes made at random read back as made.
    rng = rnd.Random(15)
    crashes = []
    for i in range(3000):
        text = "".join(rng.choice("ABCDEFGabcdefg#b0123456789*/.+|, x-kh") for _ in range(rng.randint(0, 14)))
        for drums in (False, True):
            try:
                tm.read_notes(text, drums)
            except tm.MusicError as err:
                if err.at is None or not 0 <= err.at <= len(text):
                    crashes.append((text, "at", err.at))
            except Exception as exc:
                crashes.append((text, repr(exc)))
    c.check(not crashes, "a fuzz of 6,000 random note texts: notes or a clear mistake, never a crash", crashes[:5])
    wrong = []
    for i in range(400):
        words, beats, pitches = [], F(0), []
        for _ in range(rng.randint(1, 12)):
            if rng.random() < 0.15:
                word, ps = ".", []
            else:
                ps = [(rng.choice("CDEFGAB"), rng.choice(["", "#", "b"]), rng.randint(0, 8)) for _ in range(rng.choice([1, 1, 1, 3]))]
                word = "+".join(f"{l}{a}{o}" for l, a, o in ps)
            k = rng.choice(["", "*2", "/2", "*1.5", "/3", "*3/2"])
            words.append(word + k)
            beats += {"": F(1), "*2": F(2), "/2": F(1, 2), "*1.5": F(3, 2), "/3": F(1, 3), "*3/2": F(3, 2)}[k]
            pitches += [12 * (o + 1) + "C D EF G A B".index(l) + {"#": 1, "b": -1, "": 0}[a] for l, a, o in ps]
        text = rng.choice([" ", "  ", " | "]).join(words)
        events, total = tm.read_notes(text)
        if total != beats or [p for _s, _b, ps in events for p in ps] != pitches:
            wrong.append(text)
    c.check(not wrong, "400 random tunes (notes, chords, rests, lengths) read back exactly as they were made", wrong[:3])

    # ---- the synth's .wav
    tracks = []
    for instrument, notes, volume in TMUSIC_SONG:
        events, beats = tm.read_notes(notes, instrument == "drums", "song:track")
        tracks.append((instrument, volume / 100, events, beats))
    t0 = time.perf_counter()
    data = tm.wav_bytes(tm.render(tracks, 150))
    secs = time.perf_counter() - t0
    with wave.open(io.BytesIO(data)) as w:
        shape = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype())
    c.check(data[:4] == b"RIFF" and data[8:16] == b"WAVEfmt " and shape == (1, 2, 22050, 79380, "NONE"),
            "the test song is a .wav: mono, 16-bit, 22,050 a second, 3.6 seconds (9 beats at 150)", shape)
    c.check(hashlib.sha256(data).hexdigest() == TMUSIC_SONG_HASH, "...and it's the same sound as always (its SHA-256)", hashlib.sha256(data).hexdigest())
    c.check(tm.wav_bytes(tm.render(tracks, 150)) == data and secs < 5, f"...and the same again when it's made again ({secs:.2f} s)", secs)
    peak = max(abs(v) for v in tm.render(tracks, 150))
    c.check(27000 < peak <= 27852, "the loudest moment is turned down to 85% of the most a .wav holds", peak)
    long_song = [("piano", 1.0, *tm.read_notes("C4 E4 G4 C5 | F4 A4 C5 . " * 15, False)),
                 ("drums", 1.0, *tm.read_notes("kick hat snare hat " * 30, True)),
                 ("bass", 0.8, *tm.read_notes("C2*4 F2*4 " * 15, False))]
    t0 = time.perf_counter()
    pcm = tm.render(long_song, 120)
    secs = time.perf_counter() - t0
    c.check(len(pcm) == 60 * 22050 and secs < 10, f"a minute of music with three tracks takes {secs:.2f} s to make", (len(pcm), secs))

    # ---- a program, in both runtimes, through a pipe
    outs = {}
    for slow in (True, False):
        where = os.path.join(folder, "slow" if slow else "fast")
        code, out, err, secs = tmusic_run(where, "song.tuf", TMUSIC_PROGRAM, {"TUFF_SLOW": "1" if slow else None, "TUFF_MUSIC_DIR": music})
        outs[slow] = (code, out, err)
        if slow:
            continue
        c.check(code == 0 and out.splitlines() == TMUSIC_OUTPUT, f"the tmusic program runs and says what it should ({secs:.1f} s)", (out + err)[-800:])
        saved = os.path.join(where, "theme.wav")
        made = sorted(os.listdir(music)) if os.path.isdir(music) else []
        c.check(os.path.isfile(saved) and len(made) == 1 and open(saved, "rb").read() == open(os.path.join(music, made[0]), "rb").read(),
                "song:save wrote theme.wav, the song tmusic made once and keeps (only that one: in a pipe, play makes nothing)", made)
    c.check(outs[True] == outs[False], "the tree walker (TUFF_SLOW=1) gives exactly the same", outs[True][1:])
    code, out, err, _s = tmusic_run(folder, "song.tuf", TMUSIC_PROGRAM, args=["--check"])
    c.check(code == 0 and out.strip() == "OK", "--check accepts the program (its mistakes are inside try: blocks)", (out + err)[:400])
    # The same notes again make no new file; the file's name is the notes', and the folder keeps the newest songs.
    again = 'mention tmusic\nsong = tmusic.song(120)\nsong:track("piano", "C4 E4 G4 E4 | F4 A4 C5 .")\nsong:track("bass", "C2*4 | F2*4", 60)\n' \
            'song:track("drums", "kick  hat snare hat | kick+crash hat snare hat")\nsong:save("again.wav")\n'
    tmusic_run(folder, "again.tuf", again, {"TUFF_MUSIC_DIR": music})
    c.check(len(os.listdir(music)) == 1 and os.path.isfile(os.path.join(folder, "again.wav")),
            "the same notes in another run (spaced differently) use the song tmusic made before", os.listdir(music))
    crowd = os.path.join(folder, "crowd")
    os.makedirs(crowd)
    for i in range(tm.KEEP + 5):
        with open(os.path.join(crowd, f"song-{i:02}.wav"), "wb") as f:
            f.write(b"x")
        os.utime(os.path.join(crowd, f"song-{i:02}.wav"), (1_000_000 + i, 1_000_000 + i))
    with open(os.path.join(crowd, "mine.wav"), "wb") as f:
        f.write(b"x")
    tm.tidy(crowd, os.path.join(crowd, "song-44.wav"))
    left = sorted(os.listdir(crowd))
    c.check(len(left) == tm.KEEP + 1 and "mine.wav" in left and "song-04.wav" not in left and "song-05.wav" in left,
            f"the songs' folder keeps the newest {tm.KEEP} songs (and nothing that isn't one of tmusic's)", left[:3])
    # Agents' tuff_run (TUFF_NO_WRITES=1) and Tuff Engine's preview write nothing.
    tmusic_run(folder, "nowrite.tuf", 'mention tmusic\ns = tmusic.song()\ns:track("bell", "C5")\ns:save("never.wav")\n',
               {"TUFF_NO_WRITES": "1", "TUFF_MUSIC_DIR": os.path.join(folder, "music_nowrite")})
    c.check(not os.path.exists(os.path.join(folder, "never.wav")) and not os.path.exists(os.path.join(folder, "music_nowrite")),
            "with TUFF_NO_WRITES=1 (tuff_run), song:save writes nothing and makes nothing")

    # ---- mistakes: the run and --check say the same
    for i, (code_text, line, col, says, run_it, check_it) in enumerate(TMUSIC_MISTAKES):
        src = "mention tmusic\n" + code_text + "\n"
        shown = code_text.splitlines()[line - 2].strip()
        if run_it:
            code, out, err, _s = tmusic_run(folder, f"bad{i}.tuf", src, {"TUFF_MUSIC_DIR": music})
            at = tuff_error_at(err)
            c.check(code == 1 and at[0] == line and says in at[2], f"running {shown!r} stops on line {line}: {says[:60]!r}", at)
        code, out, err, _s = tmusic_run(folder, f"bad{i}.tuf", src, args=["--check"])
        at = tuff_error_at(err)
        if check_it:
            c.check(code == 1 and at[:2] == (line, col) and says in at[2], f"--check on {shown!r} says it at {line}:{col}", at)
        else:
            c.check(out.strip() == "OK", f"--check can't know {shown!r} before the run, and says OK", (out + err)[:300])
    for i, code_text in enumerate(TMUSIC_GOOD):
        code, out, err, _s = tmusic_run(folder, f"good{i}.tuf", "mention tmusic\n" + code_text + "\n", args=["--check"])
        c.check(code == 0 and out.strip() == "OK", f"--check accepts: {code_text.splitlines()[-1][:60]}", (out + err)[:300])

    # ---- where the sound goes: nowhere in a pipe, a message to the Run panel in TuffCode
    quiet = os.path.join(folder, "music_pipe")
    long_play = 'mention tmusic\nlong = tmusic.song(60)\nlong:track("piano", "C4*60")\nlong:play()\ntmusic.play("C4*30", "bell", 60)\n' \
                'long:loop()\nlong:stop()\nsay "done"\n'
    code, out, err, secs = tmusic_run(folder, "pipe.tuf", long_play, {"TUFF_NO_SOUND": None, "TUFF_MUSIC_DIR": quiet})
    c.check(code == 0 and out.strip() == "done" and secs < 5 and not os.path.exists(quiet),
            f"in a pipe, a minute of music plays nothing and doesn't wait: done in {secs:.1f} s, with no sound made", (out + err, secs))
    ide = 'mention tmusic\nsay "start"\ntmusic.play("C5 E5 G5", "chip", 240)\nsay "after"\nbeat = tmusic.song(240)\n' \
          'beat:track("drums", "kick hat")\nbeat:loop()\nbeat:stop()\n'
    code, out, err, secs = tmusic_run(folder, "ide.tuf", ide, {"TUFF_NO_SOUND": None, "TUFF_IDE": "1", "TUFF_MUSIC_DIR": music})
    sent = re.findall(r"\x1b\]tuff;music;(\w+);([^;\x07]*)(?:;([^;\x07]*);(\d))?\x07", out)
    files = [base64.b64decode(m[2]).decode("utf-8") for m in sent if m[0] == "play"]
    lengths = []
    for f in files:
        try:
            with wave.open(f) as w:
                lengths.append(w.getnframes() / w.getframerate())
        except (OSError, EOFError, wave.Error):
            lengths.append(None)
    said = re.findall(r"\x1b\]tuff;say;\d+;([^;\x07]*)", out)
    c.check(code == 0 and [(m[0], m[1], m[3]) for m in sent] == [("play", "s1", "0"), ("play", "s2", "1"), ("stop", "s2", "")]
            and [base64.b64decode(s).decode() for s in said] == ["start", "after"],
            "with TUFF_IDE=1, TuffCode's Run panel is sent music;play for the tune, music;play to loop the song, then music;stop",
            (sent, out[-300:], err[-300:]))
    c.check(all(os.path.isabs(f) and os.path.dirname(f) == music for f in files) and len(lengths) == 2 and abs(lengths[0] - 0.75) < 0.001 and lengths[1] == 0.5,
            "...with each song's .wav (made in tmusic's folder, 0.75 and 0.5 seconds long)", (files, lengths))
    c.check(0.75 <= secs < 5, f"...and tmusic.play waited until its tune ended ({secs:.2f} s for 0.75 s of notes)", secs)
    tmusic_players(c, tm)

    # ---- a game's music: --scene makes nothing, a run with no window (headless.py) sends the page the songs
    game_dir = os.path.join(folder, "game")
    os.makedirs(game_dir)
    src = os.path.join(game_dir, "tune_game.tuf")
    with open(src, "w", encoding="utf-8") as f:
        f.write(TMUSIC_GAME)
    preview_music = os.path.join(folder, "music_scene")
    code, out, err, d, secs = scene(src, env={"TUFF_MUSIC_DIR": preview_music})
    c.check(code == 0 and d.get("error") is None and d.get("stopped") == "loop" and not os.path.exists(preview_music)
            and not any(cmd[0] == "k" and "sound" in cmd[2] for cmd in d.get("batch", [])),
            f"Tuff Engine's preview runs a game with songs, and makes and plays none ({secs:.1f} s)", (d.get("error"), d.get("stopped"), err[-300:]))
    os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
    run = headless("tmusic_game", TMUSIC_GAME, 20)
    if run is None:
        c.check(True, "--runtime: skipped the headless run (it needs tuff.py)")
    else:
        rc, lines, err, cmds = run
        sounds = [cmd[3] for cmd in cmds if cmd[0] == "k" and cmd[2] == "sound"]
        names = [s[1].split("/")[-1] for s in sounds]
        c.check(rc == 0 and lines == ["frames 5"] and len(sounds) == 2 and sounds[0][0] == "music" and sounds[0][2:] == [0.6, True]
                and sounds[1][0].startswith("s") and sounds[1][2:] == [1, False] and all(s[1].startswith("shared:music/song-") for s in sounds),
                "game:music(song) loops the song in the game's page, and game:sound(song) plays one once", (sounds, err[-300:]))
        c.check(all(os.path.isfile(os.path.join(os.environ["TUFF_MUSIC_DIR"], n)) for n in names), "...as the .wav files tmusic made", names)
    # The window's file server: a shared folder's files, by name, and nothing outside it.
    import tuff_view
    files = tuff_view._file_server()
    token = "tmusic-test"
    files.roots[token] = (tuff_view.WEB_DIR, None)
    tuff_view.share("music", os.environ["TUFF_MUSIC_DIR"])
    song_file = sorted(n for n in os.listdir(os.environ["TUFF_MUSIC_DIR"]) if n.endswith(".wav"))[0]
    view = object.__new__(tuff_view.View)
    view._base = f"http://127.0.0.1:{files.server_address[1]}/{token}/"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(url):
        try:
            with opener.open(url, timeout=10) as r:
                return r.status, r.headers.get("Content-Type"), r.read()
        except urllib.error.HTTPError as err:
            return err.code, None, b""
    status, kind, body = fetch(view.shared_url("music", song_file))
    with open(os.path.join(os.environ["TUFF_MUSIC_DIR"], song_file), "rb") as f:
        c.check(status == 200 and kind == "audio/wav" and body == f.read(), "the game's page gets a song's .wav from the shared folder", (status, kind))
    outside = [fetch(view._base + p)[0] for p in ("shared/music/../tmusic/song.tuf", "shared/music/%2e%2e/tmusic/song.tuf", "shared/nope/" + song_file)]
    c.check(outside == [404, 404, 404], "...and nothing outside it, or from a folder that isn't shared", outside)
    try:
        view.shared_url("music", "../game/tune_game.tuf")
        refused = False
    except tuff_view.ViewError:
        refused = True
    c.check(refused and tuff_view.Recorder().shared_url("music", song_file) == f"shared:music/{song_file}",
            "shared_url refuses a file outside the folder, and the preview's recorder names it shared:music/...")
    del files.roots[token]

    # ---- the editor and the guide
    lang = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-lang.js")
    try:
        p = subprocess.run(["node", "-e", TMUSIC_LANG, lang], capture_output=True, text=True, encoding="utf-8", timeout=60)
        t = json.loads(p.stdout)
    except FileNotFoundError:
        t = None
        c.check(True, "Node isn't installed: skipped the editor checks")
    except ValueError:
        t = None
        c.check(False, "the editor checks ran", (p.stdout + p.stderr)[-600:])
    if t:
        c.check(t["sharp"] == ["C sharp in octave 4 (277.2 Hz), 1 beat.", [1, 22, 1, 25]] and t["flat"][0] == "B flat in octave 3 (233.1 Hz), 2 beats."
                and t["rest"][0] == "A rest: 1 beat of quiet." and t["drum"][0] == "The kick drum, 1 beat."
                and t["chord"][0].startswith("A chord: C in octave 4 (261.6 Hz, middle C), E in octave 4") and t["chord"][0].endswith("0.5 beats."),
                "hovering a note in a song:track string says what it is: C#4, Bb3*2, a rest, a chord, a drum", [t[k] for k in ("sharp", "flat", "rest", "chord", "drum")])
        c.check(t["play"][0].startswith("C in octave 4") and t["instrument"] is None and t["plain"] is None,
                "...and in tmusic.play's notes, but not on the instrument or in other text", [t["play"], t["instrument"], t["plain"]])
        c.check(t["lib"] and "Music from notes" in t["lib"][0] and t["fn"] and "waits until they end" in t["fn"][0],
                "mention tmusic and tmusic.play have hovers", [t["lib"], t["fn"]])
        c.check(set(tm.tables()["kinds"]["song"]) <= set(t["song"]) and not {"track", "loop", "length"} & set(t["other"]),
                "a file that mentions tmusic is offered a song's methods after ':', and other files aren't offered tmusic's own", (t["song"][:8], t["other"][:8]))
        c.check(t["funcs"] == ["play", "song"] and "tmusic" in t["mention"] and "tmusic" in t["libs"] and "tmusic.song(" in (t["snippet"] or ""),
                "tmusic. offers play and song, mention offers tmusic, it's coloured as a library, and there's a snippet", [t["funcs"], t["snippet"]])
    guide = open(os.path.join(REPO, "tuffcode", "mcp", "tuff-guide.md"), encoding="utf-8").read()
    start = guide.find("\n### tmusic")
    section = guide[start:guide.find("\n### ", start + 1)] if start >= 0 else ""
    blocks = re.findall(r"```tuff\n(.*?)```", section, re.S)
    c.check(len(blocks) >= 2 and "is middle C" in section and "In a file or a pipe" in section, f"the guide has a tmusic section ({len(blocks)} examples)")
    for i, code_text in enumerate(blocks, 1):
        where = os.path.join(folder, f"guide{i}")
        code, out, err, _s = tmusic_run(where, "guide.tuf", code_text, args=["--check"])
        c.check(code == 0 and out.strip() == "OK", f"the guide's tmusic example {i} passes --check", (out + err)[:300])
        if "tgame" in code_text:
            code, out, err, d, secs = scene(os.path.join(where, "guide.tuf"))
            c.check(code == 0 and d.get("error") is None, f"...and Tuff Engine's preview runs it ({secs:.1f} s)", (d.get("error"), err[-300:]))
        else:
            code, out, err, secs = tmusic_run(where, "guide.tuf", code_text, {"TUFF_MUSIC_DIR": music})
            c.check(code == 0 and "Tuff error" not in err and os.path.isfile(os.path.join(where, "theme.wav")),
                    f"...and runs, saving theme.wav ({secs:.1f} s)", (out + err)[-300:])


# ---------------------------------------------------------------- the debugger (1.5.0)

# A shop in two files: a kind, a list, a dictionary, a function called in a loop, and money.tuf with a top level of
# its own. The line numbers matter: the checks below name them.
DEBUG_MAIN = '''import money.tuf
kind Pet:
    name = "?"
    hunger = 5
    toys = []
    func feed(amount):
        my.hunger -= amount
        return my.hunger

total = 0
items = ["milk", "eggs"]
ages = {"sam": 14, "ann": 12}
rex = Pet("Rex")
func add(n):
    total += n
    return total

for i in range(1, 3):
    add(i)
rex:feed(2)
say money.with_tax(10)
say total
'''
DEBUG_MONEY = '''rate = 0.2

func with_tax(price):
    extra = price * rate
    return price + extra
'''
# Step Into from the start, then into, over and out of functions, an action and the other file: (the step, the
# file and line it stops on). A loop going round again stops on its own line (18) before its first statement.
DEBUG_STEPS = [("stepIn", "main", 1), ("stepIn", "money", 1), ("stepOut", "main", 10), ("next", "main", 11), ("next", "main", 12),
               ("next", "main", 13), ("next", "main", 18), ("next", "main", 19), ("stepIn", "main", 15), ("stepOut", "main", 18),
               ("next", "main", 19), ("next", "main", 18), ("next", "main", 19), ("next", "main", 20), ("stepIn", "main", 7),
               ("next", "main", 8), ("next", "main", 21), ("stepIn", "money", 4), ("stepOut", "main", 22)]
DEBUG_COUNT = 'count = 3\nwhile count > 0:\n    say count\n    count -= 1\nsay "Liftoff!"\n'
DEBUG_ERROR = 'func half(x):\n    y = x * 2\n    return y + nope\nitems = [1, 2, 3]\nsay "start"\nsay half(items[0])\nsay "never"\n'
DEBUG_ASK = 'name = input "Name? "\nsay "Hi " + name\nsize = len(name)\nsay size\n'


class DebugLink:
    """TuffCode's side of the debugger, for one run of a program: a server on this computer that the program connects
    to (TUFF_DEBUG, or --debug with arg=True), the commands it's sent and the messages it sends back. Every wait has a
    time limit, so a run that gets stuck fails its checks instead of hanging the tests."""

    def __init__(self, folder, main, slow=False, env=None, arg=False):
        import queue
        import socket
        import threading
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(30)
        port = str(self.srv.getsockname()[1])
        full = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW", "TUFF_DEBUG", "TUFF_NO_WRITES", "TUFF_BASE_DIR")}
        full.update({"PYTHONIOENCODING": "utf-8", "TUFF_NO_SOUND": "1", **(env or {})})
        if slow:
            full["TUFF_SLOW"] = "1"
        if not arg:
            full["TUFF_DEBUG"] = port
        path = os.path.join(folder, main)
        self.proc = subprocess.Popen(tuff_cmd() + (["--debug", port] if arg else []) + [path], cwd=folder, env=full,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                     encoding="utf-8", errors="replace")
        self.out, self.err, self.log = [], [], []
        for stream, into in ((self.proc.stdout, self.out), (self.proc.stderr, self.err)):
            threading.Thread(target=lambda s=stream, i=into: i.extend(s), daemon=True).start()
        self.msgs = queue.Queue()
        try:
            self.conn, _ = self.srv.accept()
        except OSError:
            self.conn = None
            return
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        try:
            for line in self.conn.makefile("r", encoding="utf-8"):
                self.msgs.put(json.loads(line))
        except (OSError, ValueError):
            pass
        self.msgs.put(None)

    def send(self, cmd, **fields):
        try:
            self.conn.sendall((json.dumps({"cmd": cmd, **fields}) + "\n").encode("utf-8"))
        except (OSError, AttributeError):
            pass

    def answer(self, text):
        """Types an answer for input()."""
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()

    def next(self, *events, timeout=20):
        """The next message that's one of these events (the others go in self.log too), or None after timeout s."""
        import queue
        end = time.monotonic() + timeout
        while self.conn is not None:
            try:
                m = self.msgs.get(timeout=max(0.01, end - time.monotonic()))
            except queue.Empty:
                return None
            if m is None:
                self.msgs.put(None)
                return None
            self.log.append(m)
            if m.get("event") in events:
                return m
        return None

    def finish(self, timeout=30):
        """Waits for the program to end: (exit code, what it said, its errors). One still running is stopped (None)."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            code = self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            code = None
        time.sleep(0.1)  # (the last of its output)
        self.close()
        return code, "".join(self.out), "".join(self.err)

    def close(self):
        for s, shut in ((self.conn, True), (self.srv, False)):
            try:
                if s and shut:
                    s.shutdown(2)  # (SHUT_RDWR: read()'s file of it would keep it open)
                if s:
                    s.close()
            except OSError:
                pass
        if self.proc.poll() is None:
            self.proc.kill()


def debug_names(msg, scope=-1):
    """{name: value as shown} of one of a paused (or watch, or scopes) message's scopes: the last is the file's top level."""
    scopes = (msg or {}).get("scopes") or []
    return {v["name"]: v["value"] for v in scopes[scope]["vars"]} if scopes else {}


def debug_var(msg, name, scope=-1):
    scopes = (msg or {}).get("scopes") or []
    return next((v for v in scopes[scope]["vars"] if v["name"] == name), None) if scopes else None


def debug_where(msg, folder):
    """(the file's name without .tuf, the line) a message is at, like ("main", 15)."""
    if not msg:
        return None
    return os.path.splitext(os.path.relpath(msg["file"], folder))[0].replace(os.sep, "/"), msg["line"]


def debug_project(name, files):
    folder = os.path.join(OUT, "debug", name)
    os.makedirs(folder, exist_ok=True)
    for rel, code in files.items():
        with open(os.path.join(folder, rel), "w", encoding="utf-8", newline="") as f:
            f.write(code)
    return folder


def debug_steps(c, slow, mode):
    """The shop, stepped through: into money.tuf's top level and out of it, over and into functions, an action, the
    other file's function, and a loop going round."""
    folder = debug_project(f"steps_{mode}", {"main.tuf": DEBUG_MAIN, "money.tuf": DEBUG_MONEY})
    link = DebugLink(folder, "main.tuf", slow)
    got, at = [], {}
    link.send("stepIn")
    msg = link.next("paused")
    for i, (cmd, file, line) in enumerate(DEBUG_STEPS):
        where = debug_where(msg, folder)
        got.append(where)
        at[where] = msg
        if where != (file, line) or i + 1 == len(DEBUG_STEPS):
            break
        link.send(DEBUG_STEPS[i + 1][0])
        msg = link.next("paused")
    want = [(file, line) for _cmd, file, line in DEBUG_STEPS]
    c.check(got == want, f"{mode}: Step Into, Over and Out stop where they should, in both files and as the loop goes round", (got, want))
    feed = at.get(("main", 7))
    c.check(feed and [f["name"] for f in feed["stack"]] == ["Pet:feed", "main.tuf"] and feed["stack"][1]["line"] == 20
            and debug_names(feed, 0).get("amount") == "2" and (debug_var(feed, "my", 0) or {}).get("type") == "Pet",
            f"{mode}: in an action, the call stack has it and the line that called it, and its names have my (a Pet)", feed and (feed["stack"], feed["scopes"][0]))
    tax = at.get(("money", 4))
    c.check(tax and [f["name"] for f in tax["stack"]] == ["with_tax", "main.tuf"] and debug_names(tax, 0) == {"price": "10"}
            and debug_names(tax) == {"rate": "0.2"} and tax["scopes"][-1]["name"] == "money.tuf",
            f"{mode}: in money.tuf's function, its names and then money.tuf's own top level (not main.tuf's)", tax and tax["scopes"])
    top = at.get(("money", 1))
    c.check(top and [f["name"] for f in top["stack"]] == ["money.tuf", "main.tuf"] and top["stack"][0]["top"],
            f"{mode}: money.tuf's top-level code is in the call stack while it's imported", top and top["stack"])
    loop = at.get(("main", 18))
    c.check(loop and debug_names(loop).get("i") == "3" and debug_names(loop).get("total") == "3",
            f"{mode}: on the loop's own line as it goes round, i is the next item already", loop and debug_names(loop))
    link.send("continue")
    end = link.next("ended")
    code, out, err = link.finish()
    c.check(end and end.get("code") == 0 and code == 0 and out.splitlines() == ["12", "6"],
            f"{mode}: Continue runs it to the end, with its output as usual", (end, code, out, err[-300:]))


def debug_breakpoints(c, slow, mode, crlf=False):
    """Breakpoints in both files, the Variables panel's values (kinds' objects, lists and dictionaries open up), the
    call stack's frames, and breakpoints changed while it runs."""
    nl = "\r\n" if crlf else "\n"
    folder = debug_project(f"breaks_{mode}{'_crlf' if crlf else ''}", {"main.tuf": DEBUG_MAIN.replace("\n", nl),
                                                                       "money.tuf": DEBUG_MONEY.replace("\n", nl)})
    main, money = os.path.join(folder, "main.tuf"), os.path.join(folder, "money.tuf")
    link = DebugLink(folder, "main.tuf", slow)
    link.send("setBreakpoints", file=main, lines=[15])
    link.send("continue")
    first = link.next("paused")
    names = debug_names(first)
    c.check(first and first["reason"] == "breakpoint" and debug_where(first, folder) == ("main", 15) and first["col"] == 5,
            f"{mode}{' (CRLF lines)' if crlf else ''}: it stops at a breakpoint in a function, on the editor's line", first and (first["reason"], first["file"], first["line"]))
    if crlf:
        link.close()
        return
    c.check(first and [(f["name"], f["line"]) for f in first["stack"]] == [("add", 15), ("main.tuf", 19)],
            f"{mode}: the call stack is the function and the line that called it", first and first["stack"])
    c.check(debug_names(first, 0) == {"n": "1"} and names.get("total") == "0" and names.get("items") == '["milk", "eggs"]'
            and names.get("ages") == '{"sam": 14, "ann": 12}' and names.get("rex") == 'Pet(name: "Rex", hunger: 5, toys: [])'
            and "add" not in names and "Pet" not in names and "print" not in names and names.get("money") == "<file money.tuf>",
            f"{mode}: the function's names, then the file's own top-level ones as say shows them (not its functions, kinds or built-ins)", (first or {}).get("scopes"))
    kinds = {k: (debug_var(first, k) or {}).get("type") for k in ("total", "items", "ages", "rex", "money")}
    sizes = {k: (debug_var(first, k) or {}).get("more") for k in ("items", "ages", "rex")}
    c.check(kinds == {"total": "number", "items": "list", "ages": "dictionary", "rex": "Pet", "money": "file"}
            and sizes == {"items": 2, "ages": 2, "rex": 3}, f"{mode}: each value says what it is, and how much is inside it", (kinds, sizes))
    link.send("expand", path=["top", "rex"], open=True)
    opened = link.next("scopes")
    rex = debug_var(opened, "rex") or {}
    c.check([(k["name"], k["value"], k["type"]) for k in rex.get("kids", [])] == [("name", "Rex", "text"), ("hunger", "5", "number"), ("toys", "[]", "list")],
            f"{mode}: an object opens to show its fields (its text as say shows it)", rex)
    link.send("expand", path=["top", "items"], open=True)
    link.send("expand", path=["top", "ages"], open=True)
    link.next("scopes")
    opened = link.next("scopes")
    items, ages = debug_var(opened, "items") or {}, debug_var(opened, "ages") or {}
    c.check([(k["name"], k["value"]) for k in items.get("kids", [])] == [("0", "milk"), ("1", "eggs")]
            and [(k["name"], k["value"]) for k in ages.get("kids", [])] == [('"sam"', "14"), ('"ann"', "12")],
            f"{mode}: a list opens to its items and a dictionary to its keys", (items, ages))
    link.send("frame", index=1)
    frame = link.next("scopes")
    c.check(frame and frame["frame"] == 1 and len(frame["scopes"]) == 1 and debug_names(frame).get("i") == "1",
            f"{mode}: another frame of the call stack shows its own names", frame)
    link.send("continue")
    again = link.next("paused")
    c.check(again and debug_where(again, folder) == ("main", 15) and debug_names(again, 0) == {"n": "2"} and debug_names(again)["total"] == "1"
            and (debug_var(again, "rex") or {}).get("kids"), f"{mode}: Continue stops there again the next time, with the new values (and rex still open)",
            again and again["scopes"])
    link.send("setBreakpoints", file=main, lines=[])
    link.send("setBreakpoints", file=money, lines=[4])
    link.send("continue")
    tax = link.next("paused")
    c.check(tax and debug_where(tax, folder) == ("money", 4) and debug_names(tax, 0) == {"price": "10"} and debug_names(tax) == {"rate": "0.2"},
            f"{mode}: breakpoints changed while it runs: it goes on past the old one and stops in money.tuf", tax and (tax["file"], tax["line"], tax["scopes"]))
    link.send("continue")
    end = link.next("ended")
    code, out, _err = link.finish()
    c.check(end and code == 0 and out.splitlines() == ["12", "6"], f"{mode}: ...then it ends as usual", (end, code, out))


def debug_errors(c, slow, mode):
    """Pause on error: in a function, in another file and at the top level it stops on the error's line with the
    names as they were; an error caught by try doesn't stop it."""
    folder = debug_project(f"errors_{mode}", {"main.tuf": DEBUG_ERROR})
    link = DebugLink(folder, "main.tuf", slow)
    link.send("continue")
    msg = link.next("paused")
    c.check(msg and msg["reason"] == "error" and (msg["line"], msg["col"]) == (3, 16) and "I don't know what 'nope' is" in msg.get("error", "")
            and [(f["name"], f["line"]) for f in msg["stack"]] == [("half", 3), ("main.tuf", 6)]
            and debug_names(msg, 0) == {"x": "1", "y": "2"} and debug_names(msg).get("items") == "[1, 2, 3]" and msg.get("ends") is True,
            f"{mode}: an error pauses on its line before the program ends (and says it ends it), with the function's names still there", msg)
    err_now = "".join(link.err)
    c.check("Tuff error on line 3" in err_now, f"{mode}: ...and the error is already in the Run window while it's paused", err_now[-300:])
    link.send("continue")
    end = link.next("ended")
    code, out, err = link.finish()
    c.check(end and end["code"] == 1 and code == 1 and out.splitlines() == ["start"] and "Tuff error on line 3" in err,
            f"{mode}: Continue then ends it, as the error would have", (end, code, out, err[-200:]))

    bad_money = DEBUG_MONEY.replace("price + extra", "price + extra + oops")
    folder = debug_project(f"errors_file_{mode}", {"main.tuf": DEBUG_MAIN, "money.tuf": bad_money})
    link = DebugLink(folder, "main.tuf", slow)
    link.send("continue")
    msg = link.next("paused")
    c.check(msg and msg["reason"] == "error" and debug_where(msg, folder) == ("money", 5) and debug_names(msg, 0) == {"price": "10", "extra": "2"}
            and debug_names(msg) == {"rate": "0.2"} and msg.get("ends") is True, f"{mode}: an error in money.tuf pauses there, with its names",
            msg and (msg["file"], msg["line"], msg["scopes"], msg.get("ends")))
    link.send("continue")
    code, _out, err = link.finish()
    c.check(code == 1 and "Tuff error in money.tuf on line 5" in err, f"{mode}: ...and is reported in money.tuf", err[-200:])

    folder = debug_project(f"errors_top_{mode}", {"main.tuf": 'n = 5\nsay n\nsay n + "x" * nope\n',
                                                  "caught.tuf": 'try:\n    say 1 / 0\ncatch problem:\n    say "caught"\nsay "after"\n'})
    link = DebugLink(folder, "main.tuf", slow)
    link.send("continue")
    msg = link.next("paused")
    c.check(msg and msg["reason"] == "error" and msg["line"] == 3 and debug_names(msg) == {"n": "5"} and len(msg["scopes"]) == 1 and msg.get("ends") is True,
            f"{mode}: an error at the top level pauses too", msg)
    link.send("continue")
    link.finish()
    link = DebugLink(folder, "caught.tuf", slow)
    link.send("continue")
    end = link.next("paused", "ended")
    code, out, _err = link.finish()
    c.check(end and end["event"] == "ended" and code == 0 and out.splitlines() == ["caught", "after"],
            f"{mode}: an error that try catches doesn't pause", (end, out))


def debug_input(c, slow, mode):
    """input() while debugging: the answer is typed in the Run window as usual, and Pause while it waits says so."""
    folder = debug_project(f"input_{mode}", {"main.tuf": DEBUG_ASK})
    main = os.path.join(folder, "main.tuf")
    link = DebugLink(folder, "main.tuf", slow)
    link.send("setBreakpoints", file=main, lines=[3])
    link.send("continue")
    time.sleep(0.3)
    link.answer("Sam")
    msg = link.next("paused")
    c.check(msg and msg["line"] == 3 and debug_names(msg) == {"name": "Sam"} and (debug_var(msg, "name") or {}).get("type") == "text",
            f"{mode}: input() gets its answer while debugging, and the Variables panel shows it as text, as say does", msg and msg["scopes"])
    link.send("continue")
    code, out, _err = link.finish()
    c.check(code == 0 and "Hi Sam" in out and out.splitlines()[-1] == "3", f"{mode}: ...and the program goes on as usual", out)

    link = DebugLink(folder, "main.tuf", slow)
    link.send("continue")
    time.sleep(0.4)
    link.send("pause")
    asking = link.next("asking", "paused", timeout=5)
    c.check(asking and asking["event"] == "asking", f"{mode}: Pause while input() waits says it's waiting for an answer", asking)
    link.answer("Ann")
    msg = link.next("paused")
    c.check(msg and msg["reason"] == "pause" and msg["line"] == 2 and debug_names(msg) == {"name": "Ann"},
            f"{mode}: ...and pauses on the next line once there is one", msg)
    link.send("continue")
    code, out, _err = link.finish()
    c.check(code == 0 and "Hi Ann" in out, f"{mode}: ...then goes on", out)


def debug_watch(c, slow, mode):
    """Watch it run: every statement in turn at a readable speed, the loop's own line each time round, the names as
    they change; Pause and Continue in it, and its speed changed while it runs."""
    folder = debug_project(f"watch_{mode}", {"main.tuf": DEBUG_COUNT, "long.tuf": "n = 0\nwhile n < 100000:\n    n += 1\nsay n\n"})
    link = DebugLink(folder, "main.tuf", slow)
    link.send("watch", delay=0.01)
    seen = []
    while True:
        msg = link.next("watch", "paused", "ended")
        if not msg or msg["event"] != "watch":
            break
        seen.append((msg["line"], debug_names(msg).get("count")))
    code, out, _err = link.finish()
    c.check([line for line, _n in seen] == [1, 2, 3, 4, 2, 3, 4, 2, 3, 4, 5] and msg and msg["event"] == "ended",
            f"{mode}: it shows every line as it runs, and the while line each time the loop goes round", seen)
    c.check([n for line, n in seen if line == 3] == ["3", "2", "1"] and seen[0][1] is None,
            f"{mode}: ...with the Variables panel's values as they change", seen)
    c.check(code == 0 and out.splitlines() == ["3", "2", "1", "Liftoff!"], f"{mode}: ...and its output as usual", out)

    link = DebugLink(folder, "long.tuf", slow)
    link.send("watch", delay=0.3)
    first = link.next("watch")
    t0 = time.monotonic()
    second = link.next("watch")
    gap = time.monotonic() - t0
    c.check(first and second and gap > 0.2, f"{mode}: slow is slow enough to read: {gap:.2f} s a line at 0.3", gap)
    link.send("watch", delay=0.02)
    time.sleep(0.6)
    link.send("pause")
    msg = link.next("paused", timeout=10)
    shown = sum(1 for m in link.log if m.get("event") == "watch")
    c.check(msg and msg["reason"] == "pause" and msg["line"] in (2, 3) and 5 <= shown <= 120,
            f"{mode}: faster when the speed changes ({shown} lines in 0.6 s), and Pause stops it where it is", (msg and msg["line"], shown))
    link.send("watch", delay=0)
    still = link.next("running", "watch", timeout=0.5)
    c.check(still is None, f"{mode}: turning Watch it run off while paused keeps it paused", still)
    link.send("continue")
    end = link.next("ended", timeout=30)
    later = sum(1 for m in link.log if m.get("event") == "watch") - shown
    code, out, _err = link.finish()
    c.check(end and code == 0 and out.strip() == "100000" and later == 0, f"{mode}: ...and Continue then runs it at full speed", (end, later, out))


def debug_loops(c, slow, mode):
    """A loop written on one line (while n < 3: n += 1): a breakpoint on it stops each time round, as on a loop
    written over several lines, and Step Over goes round it once a step."""
    folder = debug_project(f"loops_{mode}", {"while.tuf": "n = 0\nwhile n < 3: n += 1\nsay n\n",
                                             "for.tuf": "total = 0\nfor i in range(1, 3): total += i\nsay total\n"})
    for name, var, want, said in (("while", "n", ["0", "1", "2"], "3"), ("for", "total", ["0", "1", "3"], "6")):
        link = DebugLink(folder, name + ".tuf", slow)
        link.send("setBreakpoints", file=os.path.join(folder, name + ".tuf"), lines=[2])
        link.send("continue")
        hits = []
        for _i in range(6):
            msg = link.next("paused", "ended")
            if not msg or msg["event"] == "ended":
                break
            hits.append((msg["reason"], msg["line"], debug_names(msg).get(var)))
            link.send("continue")
        code, out, _err = link.finish()
        c.check(hits == [("breakpoint", 2, v) for v in want] and code == 0 and out.strip() == said,
                f"{mode}: a breakpoint on a {name} loop written on one line stops each time round", (hits, code, out))
    link = DebugLink(folder, "while.tuf", slow)
    link.send("stepIn")
    steps = []
    for _i in range(8):
        msg = link.next("paused", "ended")
        if not msg or msg["event"] == "ended":
            break
        steps.append((msg["line"], debug_names(msg).get("n")))
        link.send("next")
    code, out, _err = link.finish()
    c.check(steps == [(1, None), (2, "0"), (2, "1"), (2, "2"), (3, "3")] and code == 0 and out.strip() == "3",
            f"{mode}: ...and Step Over goes round it once a step", (steps, code, out))
    deeper = (("a loop's later line", "total = 0\nfor i in range(1, 3):\n    total += i\n    say total\nsay \"done\"\n",
               4, "total", ["1", "3", "6"], "1\n3\n6\ndone"),
              ("a loop in a function", "func count(n):\n    i = 0\n    while i < n:\n        i += 1\n        say i\n    return i\n\ncount(3)\n",
               5, "i", ["1", "2", "3"], "1\n2\n3"),
              ("a loop in a loop", "for a in range(2):\n    for b in range(2):\n        c = a * 10 + b\n        say c\n",
               4, "c", ["11", "12", "21", "22"], "11\n12\n21\n22"),
              ("an if in a loop", "for a in range(1, 3):\n    b = a * 2\n    if b > 0: say b\n", 3, "b", ["2", "4", "6"], "2\n4\n6"))
    for i, (what, src, line, var, want, said) in enumerate(deeper):
        name = f"deeper{i}.tuf"
        folder = debug_project(f"loops_{mode}", {name: src})
        link = DebugLink(folder, name, slow)
        link.send("setBreakpoints", file=os.path.join(folder, name), lines=[line])
        link.send("continue")
        hits = []
        for _i in range(8):
            msg = link.next("paused", "ended")
            if not msg or msg["event"] == "ended":
                break
            hits.append((msg["reason"], msg["line"], debug_names(msg, 0).get(var)))
            link.send("continue")
        code, out, _err = link.finish()
        c.check(hits == [("breakpoint", line, v) for v in want] and code == 0 and out.strip() == said,
                f"{mode}: a breakpoint on {what}, not its first, stops each time round too (Continue, not just once)", (hits, code, out))


def debug_more(c):
    """Pause and Stop in a busy loop and in wait(), a function deep inside itself, tterm and tmusic programs, TuffCode
    going away, --debug, no TuffCode to connect to, and the connect message."""
    folder = debug_project("more", {
        "busy.tuf": "n = 0\nwhile true:\n    n += 1\n",
        "slow.tuf": 'say "waiting"\nwait(30)\nsay "done"\n',
        "deep.tuf": "func down(n):\n    if n is 0:\n        return 0\n    return down(n - 1) + 1\nsay down(100)\n",
        "term.tuf": "mention tterm\nscreen = tterm.screen(5, 2)\nn = 0\nfunc step(dt):\n    n += 1\n    if n is 3:\n        screen:put(0, 0, nope)\n"
                    "screen:every_frame(step)\nsay n\n",
        "count.tuf": DEBUG_COUNT,
        "music.tuf": 'mention tmusic\nsong = tmusic.song(120)\nsong:track("piano", "C4 E4 G4")\ntmusic.play("C4 E4")\nsay song:length()\n',
    })
    link = DebugLink(folder, "busy.tuf")
    link.send("continue")
    time.sleep(0.4)
    link.send("pause")
    msg = link.next("paused", timeout=5)
    c.check(msg and msg["reason"] == "pause" and msg["line"] in (2, 3) and int(debug_names(msg).get("n", "0")) > 0,
            "Pause stops a loop that never ends, where it is", msg and (msg["line"], debug_names(msg)))
    t0 = time.monotonic()
    link.send("stop")
    end = link.next("ended", timeout=5)
    code, _out, _err = link.finish(timeout=10)
    c.check(end and code == 130 and time.monotonic() - t0 < 5, f"Stop ends it at once ({time.monotonic() - t0:.1f} s)", (end, code))

    link = DebugLink(folder, "slow.tuf")
    link.send("continue")
    time.sleep(0.5)
    t0 = time.monotonic()
    link.send("pause")
    msg = link.next("paused", timeout=5)
    c.check(msg and msg["line"] == 2 and time.monotonic() - t0 < 2, f"Pause stops wait(30) on its line straight away ({time.monotonic() - t0:.1f} s)", msg)
    link.send("stop")
    code, out, _err = link.finish(timeout=10)
    c.check(code == 130 and "done" not in out, "...and Stop ends it", (code, out))

    deep = os.path.join(folder, "deep.tuf")
    link = DebugLink(folder, "deep.tuf")
    link.send("setBreakpoints", file=deep, lines=[3])
    link.send("continue")
    msg = link.next("paused")
    stack = (msg or {}).get("stack", [])
    c.check(len(stack) == 40 and msg.get("hidden") == 62 and stack[0]["name"] == "down" and stack[-1]["name"] == "deep.tuf"
            and stack[1]["line"] == 4 and debug_names(msg, 0) == {"n": "0"},
            "a function 101 calls deep: the call stack lists the newest 39 and the program's own top level, and says how many more", (len(stack), msg and msg.get("hidden")))
    link.send("frame", index=5)
    frame = link.next("scopes")
    c.check(frame and debug_names(frame, 0) == {"n": "5"}, "...and each of them has its own n", frame)
    link.send("continue")
    code, out, _err = link.finish()
    c.check(code == 0 and out.strip() == "100", "...then it ends as usual", out)

    term = os.path.join(folder, "term.tuf")
    link = DebugLink(folder, "term.tuf")
    link.send("setBreakpoints", file=term, lines=[5])
    link.send("continue")
    msg = link.next("paused")
    c.check(msg and msg["line"] == 5 and [f["name"] for f in msg["stack"]] == ["step", "term.tuf"] and msg["stack"][1]["line"] == 8
            and debug_names(msg, 0) == {"dt": debug_names(msg, 0).get("dt")} and debug_names(msg).get("n") == "0",
            "tterm: a breakpoint in a game's frame function stops it there, called by screen:every_frame", msg and (msg["stack"], msg["scopes"]))
    link.send("setBreakpoints", file=term, lines=[])
    link.send("continue")
    msg = link.next("paused")
    c.check(msg and msg["reason"] == "error" and msg["line"] == 7 and debug_names(msg).get("n") == "3" and msg.get("ends") is True,
            "tterm: an error in the frame function pauses there, with n as it was (it ends the game)", msg and (msg["reason"], msg["line"], debug_names(msg), msg.get("ends")))
    link.send("continue")
    code, _out, err = link.finish()
    c.check(code == 1 and "Tuff error on line 7" in err, "...then the game ends with its error", err[-200:])

    music = os.path.join(folder, "music.tuf")
    link = DebugLink(folder, "music.tuf", env={"TUFF_MUSIC_DIR": os.path.join(folder, "music")})
    link.send("setBreakpoints", file=music, lines=[5])
    link.send("continue")
    msg = link.next("paused")
    song = debug_var(msg, "song") or {}
    c.check(msg and msg["line"] == 5 and song.get("type") == "song", "tmusic: it stops after the music played, and a song is a song", msg and msg["scopes"])
    link.send("continue")
    code, out, _err = link.finish()
    c.check(code == 0 and out.strip(), "...and goes on to the end", out)

    count = os.path.join(folder, "count.tuf")
    link = DebugLink(folder, "count.tuf")
    link.send("setBreakpoints", file=count, lines=[3])
    link.send("continue")
    msg = link.next("paused")
    link.conn.shutdown(2)  # TuffCode closed (or crashed) while the program was paused
    code, out, _err = link.finish()
    c.check(msg and code == 0 and out.splitlines() == ["3", "2", "1", "Liftoff!"], "TuffCode going away while it's paused: the program runs on to its end",
            (msg and msg["line"], code, out))

    link = DebugLink(folder, "count.tuf", arg=True)
    link.send("watch", delay=0.001)
    end = link.next("ended")
    code, out, _err = link.finish()
    c.check(end and code == 0 and out.splitlines()[-1] == "Liftoff!" and sum(m["event"] == "watch" for m in link.log) == 11,
            "tuff.py --debug PORT file.tuf works the same as TUFF_DEBUG", (end, code, out))

    full = {**os.environ, "PYTHONIOENCODING": "utf-8", "TUFF_DEBUG": "1"}
    full.pop("TUFF_IDE", None)
    p = subprocess.run(tuff_cmd() + [count], cwd=folder, env=full, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, stdin=subprocess.DEVNULL)
    c.check(p.returncode == 0 and p.stdout.splitlines() == ["3", "2", "1", "Liftoff!"] and
            p.stderr.strip() == "The debugger couldn't start, so the program runs as usual.",
            "with nothing to connect to, the program runs as usual (and says so once)", (p.returncode, p.stdout, p.stderr))


def debug_places(c):
    """Where a breakpoint stops (the breakpoints message): a blank line, a func line and an action's, a kind and its
    fields, and the lines a list goes on over."""
    folder = debug_project("places", {"main.tuf": DEBUG_MAIN, "money.tuf": DEBUG_MONEY,
                                      "list.tuf": 'numbers = [\n    1,\n    2\n]\nsay numbers\n# the end\n\n'})
    main, lst = os.path.join(folder, "main.tuf"), os.path.join(folder, "list.tuf")
    link = DebugLink(folder, "main.tuf")
    link.send("setBreakpoints", file=main, lines=[2, 3, 6, 9, 14, 17, 22, 99])
    link.send("setBreakpoints", file=lst, lines=[2, 3, 5, 6])
    a, b = link.next("breakpoints"), link.next("breakpoints")
    c.check(a and a["lines"] == [[2, None], [3, None], [6, 7], [9, 10], [14, 15], [17, 18], [22, 22], [99, None]],
            "breakpoints stop on the next statement from a blank line, inside a func from its line, and nowhere on a kind", a)
    c.check(b and b["lines"] == [[2, 1], [3, 1], [5, 5], [6, None]], "...on a list's first line from the lines it goes on over, and nowhere after the end", b)
    hits = []
    for _i in range(12):
        link.send("continue")
        msg = link.next("paused", "ended")
        if not msg or msg["event"] == "ended":
            break
        hits.append((msg["line"], msg["reason"]))
    code, _out, _err = link.finish()
    c.check([line for line, _r in hits] == [10, 18, 15, 18, 15, 18, 15, 7, 22] and all(r == "breakpoint" for _l, r in hits) and code == 0,
            "...and they stop there as it runs: the for line each time round, the function's and the action's first lines", hits)


def debug_speed(c):
    """In this process: no debugger, no step hook; with one, a loop's statements are checked quickly (with no
    breakpoints, or many on other lines)."""
    import contextlib
    import io
    import tuff
    folder = debug_project("speed", {"plain.tuf": 'x = 1\nsay x\n'})
    made = []
    init = tuff.Interpreter.__init__

    def spy(self, *args, **kwargs):
        init(self, *args, **kwargs)
        made.append(self)
    tuff.Interpreter.__init__ = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            tuff.run_file(os.path.join(folder, "plain.tuf"))
    finally:
        tuff.Interpreter.__init__ = init
    c.check(tuff.DEBUGGER is None and len(made) == 1 and type(made[0]) is tuff.Interpreter and not made[0].step_hooks,
            "with no debugger, a program gets the usual interpreter, with no step hook", [(type(m).__name__, m.step_hooks) for m in made])

    class Quiet:
        """Stands in for TuffCode's line: takes every message, sends none."""

        def sendall(self, data):
            pass

        def makefile(self, *args, **kwargs):
            return io.StringIO("")

        def close(self):
            pass

    src = INTERP_PERF["while"].replace("say total\n", "")
    program = tuff.Parser(tuff.tokenize(src)).program()
    secs = []
    for many in (None, False, True):
        if many is None:
            interp = tuff.Interpreter(src, folder)
        else:
            dbg = tuff.Debugger(Quiet())
            time.sleep(0.05)  # (its reader thread finds nothing and goes)
            dbg.gone, dbg.started = False, True
            dbg.go("continue", 1)
            interp = tuff.DebugInterpreter(src, folder)
            interp.path = os.path.join(folder, "loop.tuf")
            if many:
                dbg.set_breakpoints(interp.path, list(range(10, 600)))
            dbg.attach(interp)
        t0 = time.perf_counter()
        interp.run_block(program, interp.globals)
        secs.append(time.perf_counter() - t0)
    c.check(secs[1] < secs[0] * 4 + 0.2 and secs[2] < secs[1] * 1.5 + 0.2,
            f"600,000 statements: {secs[0]:.2f} s with no debugger, {secs[1]:.2f} s with it, {secs[2]:.2f} s with 590 breakpoints elsewhere", secs)


def debug_values(c):
    """In this process: a value in the Variables panel is shown as say shows it (text as it is, and in quotes inside
    a list or a dictionary), on one line, and cut short when it's long."""
    import tuff
    values = ["Sam", "5", "", ["milk", 5, True], {"sam": "14", "n": [1.5, None]}, [["a"], {}]]
    shown = [tuff.debug_text(v) for v in values]
    c.check(shown == [tuff.to_text(v) for v in values] and shown[:2] == ["Sam", "5"] and shown[3] == '["milk", 5, true]',
            "values as say shows them: text as it is, and in quotes inside a list or a dictionary", shown)
    c.check(tuff.debug_text("two\nlines\tand a tab") == "two\\nlines\\tand a tab" and tuff.debug_text("x" * 500) == "x" * tuff.DEBUG_TEXT + "…"
            and tuff.debug_text(["y" * 500]) == '["' + "y" * (tuff.DEBUG_TEXT - 2) + "…",
            "...on one line, and cut short when long", (tuff.debug_text("two\nlines\tand a tab"), tuff.debug_text(["y" * 500])[-8:]))


def debug_windows(c):
    """In this process, with no window: the functions a window calls. An error in one (a tgui button's, through
    Runtime.call) pauses there and says the program carries on; Pause while nothing runs (the window waiting for a
    click) says so, and pauses in the next function the window calls; and the time limits a window puts on its
    closed function (atgui's, and tuff_view's once the window has gone) leave out the time it was paused."""
    import contextlib
    import io
    import queue
    import socket
    import threading
    import tuff
    import tuff_atgui
    import tuff_view
    src = 'func clicked():\n    say "clicked"\n    say nope\nfunc closed():\n    n = 1\n    n += 1\nsay "ready"\n'
    path = os.path.join(debug_project("windows", {"main.tuf": src}), "main.tuf")
    ide, prog = socket.socketpair()
    msgs, hold = queue.Queue(), [0.0]

    def tuffcode():  # TuffCode's side: it continues each pause, hold[0] s later
        try:
            for line in ide.makefile("r", encoding="utf-8"):
                msg = json.loads(line)
                msgs.put(msg)
                if msg.get("event") == "paused":
                    time.sleep(hold[0])
                    ide.sendall(b'{"cmd": "continue"}\n')
        except (OSError, ValueError):
            pass

    def until(event, timeout=10):
        """The messages from the program up to the next one of this event (all of them, after timeout s)."""
        seen, end = [], time.monotonic() + timeout
        while not seen or seen[-1].get("event") != event:
            try:
                seen.append(msgs.get(timeout=max(0.01, end - time.monotonic())))
            except queue.Empty:
                break
        return seen

    def brief(seen):
        return [(m.get("event"), m.get("reason"), m.get("line"), m.get("ends")) for m in seen]

    dbg = tuff.Debugger(prog)
    threading.Thread(target=tuffcode, daemon=True).start()
    ide.sendall(b'{"cmd": "continue"}\n')
    tuff.DEBUGGER = dbg
    said = io.StringIO()
    try:
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(io.StringIO()):
            dbg.begin()
            code = tuff.run_file(path)  # (its top level ends: a window would wait for clicks now)
            interp = dbg.interp
            until("running")
            ide.sendall(b'{"cmd": "pause"}\n')
            idle = until("idle", timeout=5)
            clicked = interp.rt.call(interp.globals.vars["clicked"])  # a click, the way tgui calls a button's function
            click = until("running") + until("running")
            ide.sendall((json.dumps({"cmd": "setBreakpoints", "file": path, "lines": [5]}) + "\n").encode("utf-8"))
            until("breakpoints")
            hold[0], before = 0.5, tuff.debug_paused()
            closed = tuff_atgui.Lib(interp.rt).fire_by(interp.globals.vars["closed"], 0.3, "closed() ran too long")
            closing = until("running")
            held, hold[0] = tuff.debug_paused() - before, 0.0
            view = tuff_view.View.__new__(tuff_view.View)  # (no window: only its close's clock)
            view._close_finished = False
            view._close_started = time.monotonic() - tuff_view.CLOSE_LIMIT - tuff_view.CLOSE_GRACE - 0.2
            view._close_paused = before  # (closed() was paused 0.5 s since)
            spared = not view._close_overdue()
            view._close_paused = tuff.debug_paused()
            overdue = view._close_overdue()
    finally:
        tuff.DEBUGGER = None
        dbg.end(0)
        ide.close()
    c.check(code == 0 and brief(idle) == [("idle", None, None, None)], "Pause while nothing runs (a window waiting for a click) says so", idle)
    c.check(brief(click) == [("paused", "pause", 2, None), ("running", None, None, None), ("paused", "error", 3, False), ("running", None, None, None)]
            and [f["name"] for f in click[0]["stack"]] == ["clicked"],
            "...it pauses in the next function the window calls (the top level has ended), and an error there pauses and says the program carries on",
            (brief(click), click and click[0].get("stack")))
    c.check(clicked == (False, None) and said.getvalue().split() == ["ready", "clicked"], "...and the program does carry on, as the window would",
            (clicked, said.getvalue()))
    c.check(closed is True and brief(closing) == [("paused", "breakpoint", 5, None), ("running", None, None, None)] and held >= 0.5,
            f"atgui's time limit on app:closed's function leaves out the {held:.2f} s it was paused at a breakpoint", (closed, brief(closing)))
    c.check(spared and overdue, "...and so does tuff_view's, once the window has gone (a function still running past it ends the program)",
            (spared, overdue))


DEBUG_RELAY = r"""
// main.js's side (debug.js), with a real program: it connects, gets its first messages, and what it says comes back.
const { spawn } = require('child_process');
const net = require('net');
const path = require('path');
const debug = require(process.argv[1]);
const [python, tuffPy, folder] = process.argv.slice(2);
const main = path.join(folder, 'main.tuf');
const events = [];
let child = null;
const done = (out) => { console.log(JSON.stringify({ ...out, events })); process.exit(0); };
setTimeout(() => { if (child) child.kill(); done({ timeout: true }); }, 30000);
const refused = (port) => new Promise((resolve) => {
  const sock = net.connect(port, '127.0.0.1', () => { sock.destroy(); resolve(false); });
  sock.on('error', () => resolve(true));
});
(async () => {
  const oldPort = await debug.open([{ cmd: 'continue' }], () => events.push('old'));  // a run replaced before its program connects
  const port = await debug.open([{ cmd: 'setBreakpoints', file: main, lines: [15] }, { cmd: 'continue' }], (msg) => {
    events.push(msg.event + (msg.line ? ':' + msg.line : ''));
    if (msg.event === 'paused') { debug.send({ cmd: 'setBreakpoints', file: main, lines: [] }); debug.send({ cmd: 'continue' }); }
  });
  const oldGone = await refused(oldPort);
  let out = '';
  child = spawn(python, [tuffPy, main], { cwd: folder, env: { ...process.env, TUFF_DEBUG: String(port), PYTHONIOENCODING: 'utf-8' }, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.on('data', (d) => (out += d));
  child.on('close', (code) => setTimeout(async () => done({ code, out, oldGone, sent: debug.send({ cmd: 'continue' }), closed: await refused(port) }), 300));
})();
"""


def debug_relay(c):
    """main.js's side, with Node: debug.js's server gives the program its first messages and passes on what it says."""
    folder = debug_project("relay", {"main.tuf": DEBUG_MAIN, "money.tuf": DEBUG_MONEY})
    relay = os.path.join(REPO, "tuffcode", "debug.js")
    if RUNTIME:
        c.check(True, "debug.js with Node: skipped with --runtime (it runs tuff.py)")
        return
    try:
        p = subprocess.run(["node", "-e", DEBUG_RELAY, relay, sys.executable, TUFF, folder], capture_output=True, text=True,
                           encoding="utf-8", timeout=60, env={**os.environ, "TUFF_NO_SOUND": "1"})
        got = json.loads(p.stdout.strip().splitlines()[-1])
    except (FileNotFoundError, ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        got = {"error": str(exc), "stderr": locals().get("p") and p.stderr[-400:]}
    c.check(not got.get("timeout") and got.get("code") == 0 and got.get("events") == ["breakpoints", "running", "paused:15", "breakpoints",
                                                                                     "running", "ended"] and got.get("out", "").split() == ["12", "6"],
            "debug.js: the program connects, gets its breakpoints and the start, pauses, is sent Continue, and ends", got)
    c.check(got.get("oldGone") is True and got.get("closed") is True and got.get("sent") is False,
            "...a new run closes the last one's server, a server takes one program, and nothing is sent once it's gone", got)


# The renderer's side (renderer/js/debugger.js), with Node and stand-ins for the page, Monaco and TuffIDE, and Design
# Studio's own studio.js: breakpoints from the gutter and F9 (a widget's own line left to Studio's gear, its other
# lines and a red dot to the debugger's click, whichever listener goes first), moving with the code and kept while a
# tab is closed, and going with a file or folder renamed in the project tree; Debug's first messages; the paused line,
# the Variables panel and the call stack; the toolbar's commands; where the program says breakpoints stop; Watch it
# run and the eye; pause on error (an error that ends the program, and one a window carries on after); Pause while
# nothing runs; the code changed while it's debugged; and a run without the debugger.
DEBUG_UI = r"""
const fs = require('fs'), vm = require('vm');
const MAIN = 'C:\\proj\\main.tuf', MONEY = 'C:\\proj\\money.tuf', SHOP = 'C:\\proj\\shop.tuf';
class ClassList {
  constructor(el) { this.el = el; }
  get set() { return new Set(this.el.className.split(/\s+/).filter(Boolean)); }
  contains(c) { return this.set.has(c); }
  add(...cs) { const s = this.set; cs.forEach((c) => s.add(c)); this.el.className = [...s].join(' '); }
  remove(...cs) { const s = this.set; cs.forEach((c) => s.delete(c)); this.el.className = [...s].join(' '); }
  toggle(c, on) { if (on === undefined ? !this.contains(c) : on) this.add(c); else this.remove(c); }
}
class El {
  constructor(tag) { this.tagName = tag; this.className = ''; this.classList = new ClassList(this); this.dataset = {}; this.children = []; this.listeners = {};
    this.attrs = {}; this.innerHTML = ''; this.textContent = ''; this.title = ''; this.disabled = false; this.style = { setProperty() {} }; }
  append(...cs) { cs.forEach((c) => this.children.push(c)); }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  fire(type, target) { (this.listeners[type] || []).forEach((fn) => fn({ target, preventDefault() {} })); }
}
const target = (cls, dataset) => ({ closest: (sel) => (sel.includes(cls) ? { dataset, disabled: false } : null) });
const byId = { 'run-split': new El('div'), 'btn-debug': new El('button') };
const rootStyle = new Map([['--bottom-h', '230px']]);
const document = { createElement: (t) => new El(t), getElementById: (id) => byId[id] || null, querySelector: () => null, addEventListener() {},
  documentElement: { style: { getPropertyValue: (k) => rootStyle.get(k) || '', setProperty: (k, v) => rootStyle.set(k, v) } } };
const listeners = {};
const sent = [], runs = [], opened = [], toasts = [], commands = {};
let onEvent = null, runId = 6;
class Model {
  constructor(path, n, text = '') { this.uri = { scheme: 'file', fsPath: path }; this.n = n; this.text = text; this.ver = 1; this.decos = new Map(); this.seq = 0;
    this.disposed = false; this.bye = []; this.changes = []; this.subscribed = 0; }
  isDisposed() { return this.disposed; }
  getLineCount() { return this.n; }
  getValue() { return this.text; }
  getVersionId() { return this.ver; }
  getAlternativeVersionId() { return this.ver; }
  getLanguageId() { return 'tuff'; }
  deltaDecorations(old, add) { old.forEach((id) => this.decos.delete(id)); return add.map((d) => { const id = 'd' + ++this.seq; this.decos.set(id, d); return id; }); }
  getDecorationRange(id) { const d = this.decos.get(id); return d ? { startLineNumber: d.range.a[0] } : null; }
  getLineDecorations(n) { return [...this.decos.values()].filter((d) => d.range.a[0] === n).map((d) => ({ options: d.options })); }
  onDidChangeContent(fn) { this.changes.push(fn); this.subscribed++; return { dispose: () => { this.changes = this.changes.filter((f) => f !== fn); } }; }
  edit(by = 1) { this.ver += by; this.changes.forEach((fn) => fn()); } // (by -1: the edit undone)
  onWillDispose(fn) { this.bye.push(fn); }
  dispose() { this.bye.forEach((fn) => fn()); this.disposed = true; }
  shift(from, by) { for (const d of this.decos.values()) if (d.range.a[0] >= from) d.range.a[0] += by; }
  classes() { return [...this.decos.values()].map((d) => [d.range.a[0], d.options.glyphMarginClassName || '', d.options.className || '']); }
}
const created = [];
let models = [new Model(MAIN, 22)];
// The editor: its listeners in the order they were added, as Monaco calls them. Design Studio's customizer can't be
// drawn here (it throws once it starts to): it's seen opening by the change listener it puts on the model first.
const ed = { model: models[0], pos: { lineNumber: 1, column: 1 }, on: { down: [], move: [], leave: [], model: [] }, errors: [], actions: [], focused: 0,
  getModel() { return this.model; }, onMouseDown(fn) { this.on.down.push(fn); }, onMouseMove(fn) { this.on.move.push(fn); },
  onMouseLeave(fn) { this.on.leave.push(fn); }, onDidChangeModel(fn) { this.on.model.push(fn); },
  fire(type, ev) { for (const fn of this.on[type]) { try { fn(ev); } catch (err) { if (!String(fn).includes('openCustomizer')) this.errors.push(String(err.stack || err)); } } },
  deltaDecorations(old, add) { return this.model.deltaDecorations(old, add); },
  addAction(a) { this.actions.push(a); }, getPosition() { return this.pos; },
  setPosition(p) { this.pos = p; }, revealLineInCenterIfOutsideViewport() {}, focus() { this.focused++; } };
const monaco = { Range: class { constructor(...a) { this.a = a; } },
  editor: { TrackedRangeStickiness: { NeverGrowsWhenTypingAtEdges: 1 }, MouseTargetType: { GUTTER_GLYPH_MARGIN: 2 }, OverviewRulerLane: { Full: 7 },
    getModels: () => models.filter((m) => !m.disposed), onDidCreateModel: (fn) => created.push(fn) } };
const newModel = (path, n, text) => { const m = new Model(path, n, text); models.push(m); created.forEach((fn) => fn(m)); return m; };
// Tabs renamed in the project tree: the tab's path changes, its model (and the model's uri) stays, as in ide.js.
const renamed = new Map();
const pathOf = (m) => renamed.get(m) || m.uri.fsPath;
const settings = {};
let overlay = false, shown = null; // a dialog open (TuffIDE.overlayOpen), and Design Studio or Tuff Engine on screen
const ide = { settings: () => settings, saveSettings: (p) => Object.assign(settings, p), toast: (m) => toasts.push(m), runTarget: () => MAIN,
  studioVisible: () => shown === 'studio', engineVisible: () => shown === 'engine', overlayOpen: () => overlay,
  pathOf: (m) => (models.includes(m) && !m.disposed ? pathOf(m) : null),
  runFile: async (p, opts) => { runs.push([p, opts]); return ++runId; }, stopRun: () => sent.push({ stop: true }),
  openFile: async (p, line, opts) => { opened.push([p, line, opts && opts.focus]); ed.model = models.find((m) => pathOf(m) === p && !m.disposed) || newModel(p, 5); return {}; },
  addCommand: (id, def) => { commands[id] = def; }, monacoReady: async () => monaco, editor: () => ed, activeFile: () => pathOf(ed.model) };
const window = { tuff: { platform: 'win32', debug: { send: async (m) => sent.push(m), onEvent: (fn) => { onEvent = fn; } } },
  addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); } };
const ctx = { window, document, console, setTimeout, clearTimeout, TuffIcon: (n) => `<svg data-i="${n}"></svg>`,
  getComputedStyle: () => ({ getPropertyValue: () => '#3574f0' }), requestAnimationFrame: (fn) => fn(), addEventListener() {}, removeEventListener() {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx); // studio.js, then debugger.js, as index.html has them
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const D = window.TuffDebug;
const tick = () => new Promise((r) => setTimeout(r, 5));
const glyph = async (n) => { ed.fire('down', { target: { type: 2, position: { lineNumber: n } } }); await tick(); };
const hover = (n) => ed.fire('move', { target: { type: 2, position: { lineNumber: n } } });
const fire = (type, detail) => (listeners[type] || []).forEach((fn) => fn({ detail }));
const split = byId['run-split'];
const pane = () => split.children.find((c) => c.className.includes('') && c.tagName === 'section');
const part = (cls) => pane().children.find((c) => c.className.split(' ').includes(cls));
const body = () => part('dbg-body');
const list = (i) => body().children[i].children[1];
const bar = () => part('dbg-bar');
const button = (act) => bar().children.find((b) => b.dataset.act === act);
const click = (act) => bar().fire('click', target('[data-act]', { act }));
const enabled = () => Object.fromEntries(bar().children.filter((b) => b.dataset.act).map((b) => [b.dataset.act, !b.disabled]));
const lit = (m) => m.classes().filter((c) => c[2].includes('dbg-line'));
const dots = (m) => m.classes().filter((c) => c[1].includes('dbg-bp')).map((c) => c[0] + ':' + c[1]);
const status = () => part('dbg-status').innerHTML;
const out = {};
(async () => {
  window.TuffStudio.init(ide);
  await D.init(ide);
  await tick();
  out.commands = Object.fromEntries(Object.entries(commands).map(([id, c]) => [id, c.sc || '']));
  out.action = ed.actions.map((a) => a.label);
  out.hidden = pane().classList.contains('hidden');
  await glyph(15);
  out.click = D.breakpoints();
  out.dot = models[0].classes().filter((c) => c[0] === 15);
  ed.pos = { lineNumber: 19, column: 1 };
  commands.toggleBreakpoint.run();
  out.f9 = D.breakpoints();
  commands.toggleBreakpoint.run();
  out.f9off = D.breakpoints();
  models[0].shift(10, 2);
  out.moved = D.breakpoints();
  models[0].shift(12, -2);
  models[0].dispose();
  out.closed = D.breakpoints();
  const again = newModel(MAIN, 22);
  ed.model = again;
  out.reopened = again.classes().filter((c) => c[1].includes('dbg-bp'));
  commands.debug.run();
  await tick();
  out.first = runs[0];
  fire('tuff:run-started', { id: runId, file: MAIN, debug: true });
  out.shown = !pane().classList.contains('hidden') && byId['btn-debug'].classList.contains('on');
  out.starting = status();
  const stack = [{ index: 0, name: 'add', file: MAIN, line: 15, col: 5, top: false }, { index: 1, name: 'main.tuf', file: MAIN, line: 19, col: 5, top: true }];
  const scopes = [{ name: 'add', top: false, vars: [{ name: 'n', value: '1', type: 'number' }] },
    { name: 'main.tuf', top: true, vars: [{ name: 'total', value: '0', type: 'number' }, { name: 'items', value: '["milk", "eggs"]', type: 'list', more: 2 },
      { name: 'rex', value: 'Pet(name: "Rex", hunger: 5, toys: [])', type: 'Pet', more: 3 }] }];
  onEvent({ id: runId - 1, event: 'paused', reason: 'step', file: MAIN, line: 2, stack, scopes });
  out.otherRun = status();
  onEvent({ id: runId, event: 'paused', reason: 'breakpoint', file: MAIN, line: 15, col: 5, stack, scopes, frame: 0 });
  await tick();
  out.paused = { status: status(), vars: list(0).innerHTML, stack: list(1).innerHTML, line: lit(again), on: enabled() };
  click('next');
  list(0).fire('click', target('.dbg-var', { i: '3' }));
  list(1).fire('click', target('.dbg-frame', { i: '1' }));
  await tick();
  out.sentPaused = sent.slice();
  out.frameLine = lit(again);
  onEvent({ id: runId, event: 'scopes', frame: 1, scopes: [scopes[1]] });
  out.frameVars = list(0).innerHTML;
  onEvent({ id: runId, event: 'running' });
  out.running = { status: status(), line: lit(again).length, vars: list(0).innerHTML };
  const changed = [{ name: 'add', top: false, vars: [{ name: 'n', value: '2', type: 'number' }] }, scopes[1]];
  onEvent({ id: runId, event: 'paused', reason: 'step', file: MONEY, line: 4, col: 5, stack: [{ index: 0, name: 'with_tax', file: MONEY, line: 4, top: false }, stack[1]],
    scopes: changed });
  await tick();
  out.money = { opened: opened.slice(-1)[0], line: lit(models.find((m) => m.uri.fsPath === MONEY)),
    changed: (list(0).innerHTML.match(/dbg-var[^"]*changed/g) || []).length };
  ed.model = again;
  sent.length = 0;
  await glyph(9);
  await glyph(3);
  out.sentLive = sent.slice();
  onEvent({ id: runId, event: 'breakpoints', file: MAIN, lines: [[3, null], [9, 10], [15, 15]] });
  out.placed = { bps: D.breakpoints(), classes: dots(again) };
  sent.length = 0;
  commands.watchRun.run();
  onEvent({ id: runId, event: 'watch', file: MAIN, line: 18, col: 1, stack: [stack[1]], scopes: [scopes[1]] });
  await tick();
  out.watch = { sent: sent.slice(), status: status(), line: lit(again), focus: opened.slice(-1)[0] };
  onEvent({ id: runId, event: 'paused', reason: 'error', file: MAIN, line: 16, col: 12, error: "I don't know what 'nope' is.", ends: true, stack, scopes });
  await tick();
  out.error = { status: status(), cls: part('dbg-status').className, on: enabled(), line: lit(again) };
  sent.length = 0;
  commands.debugContinue.run();
  out.continueWatching = sent.slice();
  onEvent({ id: runId, event: 'paused', reason: 'error', file: MAIN, line: 16, col: 12, error: "I don't know what 'nope' is.", ends: false, stack, scopes });
  await tick();
  out.carriesOn = status();
  onEvent({ id: runId, event: 'ended', code: 1 });
  out.ended = { status: status(), line: lit(again).length, close: !button('close').classList.contains('hidden'),
    debugOn: byId['btn-debug'].classList.contains('on'), eye: button('watch').classList.contains('on'), state: D.state() };
  onEvent({ id: runId, event: 'breakpoints', file: MAIN, lines: [[3, 3]] });
  out.solid = dots(again);
  onEvent({ id: runId, event: 'watch', file: MAIN, line: 18, col: 1, stack: [stack[1]], scopes: [scopes[1]] });
  out.late = { state: D.state().state, line: lit(again).length };
  fire('tuff:run-started', { id: runId + 1, file: MAIN, debug: false });
  out.normalRun = pane().classList.contains('hidden');
  commands.stepOver.run();
  await tick();
  out.stepStart = runs[runs.length - 1];

  // ---- the eye: a run that's watched, ended, and the eye again
  const before = runs.length;
  click('watch');
  await tick();
  fire('tuff:run-started', { id: runId, file: MAIN, debug: true });
  out.eye = { run: runs.length - before, first: runs[runs.length - 1][1].debug.first.slice(-1)[0], on: button('watch').classList.contains('on') };
  onEvent({ id: runId, event: 'watch', file: MAIN, line: 18, col: 1, stack: [stack[1]], scopes: [scopes[1]] });
  await tick();
  click('watch'); // off while it runs
  onEvent({ id: runId, event: 'watch', file: MAIN, line: 19, col: 5, stack: [stack[1]], scopes: [scopes[1]] }); // (on its way already)
  await tick();
  out.eyeOff = { sent: sent.slice(-1)[0], watching: D.state().watching, line: lit(again).length, status: status(), vars: list(0).innerHTML };
  click('watch'); // on again
  onEvent({ id: runId, event: 'ended', code: 0 });
  out.eyeEnded = { on: button('watch').classList.contains('on'), watching: D.state().watching };
  click('watch');
  await tick();
  out.eyeAgain = { runs: runs.length - before, first: runs[runs.length - 1][1].debug.first.slice(-1)[0] };
  fire('tuff:run-started', { id: runId, file: MAIN, debug: true });

  // ---- Pause while nothing runs (a window waiting for a click), and Continue calling it off
  onEvent({ id: runId, event: 'running' });
  click('watch'); // (Watch it run off)
  sent.length = 0;
  click('pause');
  out.pausing = { status: status(), on: enabled() };
  onEvent({ id: runId, event: 'idle' });
  out.idle = { status: status(), on: enabled() };
  click('continue');
  out.calledOff = { sent: sent.slice(), status: status(), on: enabled() };
  sent.length = 0;
  click('pause');
  commands.debugContinue.run(); // (F5 too)
  out.f5Off = sent.slice();

  // ---- the code changed while it's debugged
  onEvent({ id: runId, event: 'paused', reason: 'breakpoint', file: MAIN, line: 15, col: 5, stack, scopes });
  await tick();
  again.edit();
  out.edited = status();
  sent.length = 0;
  const dotsBefore = D.breakpoints();
  await glyph(20);
  out.editedSent = { sent: sent.slice(), bps: D.breakpoints(), before: dotsBefore };
  onEvent({ id: runId, event: 'breakpoints', file: MAIN, lines: [[20, null]] });
  out.editedPlaced = dots(again);
  again.edit(-1); // undone: the code the program runs again
  out.undone = status();
  await glyph(20);
  out.undoneSent = sent.slice();
  onEvent({ id: runId, event: 'ended', code: 0 });

  // ---- a file and a folder renamed in the project tree
  const tools = newModel('C:\\proj\\lib\\tools.tuf', 10);
  ed.model = tools;
  await glyph(3);
  renamed.set(tools, 'C:\\proj\\kit\\tools.tuf');
  fire('tuff:renamed', { from: 'C:\\proj\\lib', to: 'C:\\proj\\kit' });
  await glyph(5);
  out.renamedDir = D.breakpoints().filter((b) => /tools/.test(b.path));
  renamed.set(tools, 'C:\\proj\\kit\\gears.tuf');
  fire('tuff:renamed', { from: 'C:\\proj\\kit\\tools.tuf', to: 'C:\\proj\\kit\\gears.tuf' });
  out.renamedFile = D.breakpoints().filter((b) => /tools|gears/.test(b.path));
  ide.runTarget = () => 'C:\\proj\\kit\\gears.tuf';
  commands.debug.run();
  await tick();
  out.renamedRun = runs[runs.length - 1][1].debug.first.filter((m) => /tools|gears/.test(m.file || ''));
  fire('tuff:run-started', { id: runId, file: 'C:\\proj\\kit\\gears.tuf', debug: true });
  onEvent({ id: runId, event: 'paused', reason: 'breakpoint', file: 'C:\\proj\\kit\\gears.tuf', line: 3, col: 1,
    stack: [{ index: 0, name: 'gears.tuf', file: 'C:\\proj\\kit\\gears.tuf', line: 3, top: true }], scopes: [] });
  await tick();
  out.renamedLit = { line: lit(tools), status: status() };
  onEvent({ id: runId, event: 'ended', code: 0 });
  tools.dispose();
  const back = newModel('C:\\proj\\kit\\gears.tuf', 10);
  out.renamedReopened = dots(back);
  ide.runTarget = () => MAIN;

  // ---- Design Studio's gear: a widget's own line is Studio's (its customizer), its other lines take breakpoints
  const shop = newModel(SHOP, 6, 'import tgui\nwin = tgui.window("Shop")\ntitle = win:heading("Hi")\ntitle:color "red"\nbtn = win:button("Buy")\nwin:show()\n');
  ed.model = shop;
  const customizer = async (fn) => { const was = shop.subscribed; await fn(); return shop.subscribed > was; };
  const gear = () => shop.classes().filter((c) => c[1].includes('tuff-gear')).map((c) => c[0]);
  hover(3);
  out.gear = { on: gear(), hint: dots(shop) };
  out.gearClick = { customizer: await customizer(() => glyph(3)), bps: D.breakpoints().filter((b) => b.path === SHOP) };
  hover(4);
  out.propClick = { gear: gear(), hint: dots(shop), customizer: await customizer(() => glyph(4)), bps: D.breakpoints().filter((b) => b.path === SHOP) };
  ed.pos = { lineNumber: 5, column: 1 };
  commands.toggleBreakpoint.run(); // F9 on the button's own line
  hover(5);
  out.dotLine = { gear: gear(), customizer: await customizer(() => glyph(5)), bps: D.breakpoints().filter((b) => b.path === SHOP) };
  commands.toggleBreakpoint.run();
  ed.on.down.reverse(); // (the debugger's listener first: the same either way)
  out.reversed = { customizer: await customizer(() => glyph(5)), bps: D.breakpoints().filter((b) => b.path === SHOP) };
  out.studioWidget = { customizer: await customizer(() => glyph(3)), bps: D.breakpoints().filter((b) => b.path === SHOP) };
  ed.on.down.reverse();

  // ---- a pause while a dialog is open (New Project, Search Everywhere...): the line is lit, the keyboard stays there
  commands.debug.run();
  await tick();
  fire('tuff:run-started', { id: runId, file: MAIN, debug: true });
  const money = models.find((m) => m.uri.fsPath === MONEY && !m.disposed);
  const at = (line) => ({ index: 0, name: 'money.tuf', file: MONEY, line, top: true });
  overlay = true;
  const focused = ed.focused;
  onEvent({ id: runId, event: 'paused', reason: 'breakpoint', file: MONEY, line: 2, col: 1, stack: [at(2)], scopes: [] });
  await tick();
  out.dialog = { opened: opened.slice(-1)[0], focused: ed.focused - focused, line: lit(money), pos: ed.pos, status: status() };
  onEvent({ id: runId, event: 'paused', reason: 'step', file: MONEY, line: 3, col: 1, stack: [at(3)], scopes: [] }); // (the file on screen)
  await tick();
  out.dialogSame = { focused: ed.focused - focused, line: lit(money), pos: ed.pos };
  overlay = false;
  onEvent({ id: runId, event: 'paused', reason: 'step', file: MONEY, line: 4, col: 1, stack: [at(4)], scopes: [] });
  await tick();
  out.noDialog = { focused: ed.focused - focused, line: lit(money) };

  // ---- F9 while Design Studio or Tuff Engine shows (the code editor hidden): only a toast
  ed.model = again;
  ed.pos = { lineNumber: 7, column: 1 };
  const bpsBefore = JSON.stringify(D.breakpoints());
  const toastsAt = toasts.length;
  shown = 'studio';
  commands.toggleBreakpoint.run();
  const studioSame = JSON.stringify(D.breakpoints()) === bpsBefore;
  shown = 'engine';
  commands.toggleBreakpoint.run();
  shown = null;
  out.hiddenF9 = { same: [studioSame, JSON.stringify(D.breakpoints()) === bpsBefore], toasts: toasts.splice(toastsAt) };
  commands.toggleBreakpoint.run();
  out.shownF9 = D.breakpoints().find((b) => b.path === MAIN).lines;
  commands.toggleBreakpoint.run();

  // ---- Auto Code Sort puts each breakpoint back on its line (TuffDebug.setLines, ide.js)
  onEvent({ id: runId, event: 'breakpoints', file: MAIN, lines: [[3, null]] }); // (hollow: the program never stops there)
  sent.length = 0;
  D.setLines(MAIN, [4, 12, 12, 21]);
  out.setLines = { bps: D.breakpoints().find((b) => b.path === MAIN).lines, dots: dots(again), sent: sent.slice() };
  again.edit();
  sent.length = 0;
  D.setLines(MAIN, [5]);
  out.setLinesEdited = { bps: D.breakpoints().find((b) => b.path === MAIN).lines, sent: sent.slice() };
  again.edit(-1);

  // ---- another folder opened (New Project, Open Folder): the program being debugged stops
  sent.length = 0;
  fire('tuff:folder-opened', { dir: 'C:\\other' });
  out.folder = { sent: sent.slice(), state: D.state().state, status: status(), line: lit(money).length };
  const openedAt = opened.length;
  onEvent({ id: runId, event: 'paused', reason: 'breakpoint', file: MONEY, line: 2, col: 1, stack: [at(2)], scopes: [] }); // (on its way already)
  await tick();
  out.folderLate = { state: D.state().state, opened: opened.length - openedAt, line: lit(money).length };
  sent.length = 0;
  fire('tuff:folder-opened', { dir: 'C:\\another' });
  out.folderIdle = sent.slice();
  out.toasts = toasts;
  out.errors = ed.errors;
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ crash: String(e.stack || e) })); });
"""


def debug_ui(c):
    """The renderer's side of the debugger (renderer/js/debugger.js, with studio.js), with Node (see DEBUG_UI)."""
    js = os.path.join(REPO, "tuffcode", "renderer", "js")
    try:
        p = subprocess.run(["node", "-e", DEBUG_UI, os.path.join(js, "debugger.js"), os.path.join(js, "studio.js")], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        got = json.loads(p.stdout.strip().splitlines()[-1])
    except (FileNotFoundError, ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        got = {"crash": str(exc), "stderr": locals().get("p") and p.stderr[-500:]}
    if not c.check("crash" not in got, "debugger.js runs with Node's stand-ins for the page, Monaco and TuffIDE (and Design Studio's studio.js)", got.get("crash")):
        return
    main, money, shop = "C:\\proj\\main.tuf", "C:\\proj\\money.tuf", "C:\\proj\\shop.tuf"
    gears = "C:\\proj\\kit\\gears.tuf"
    c.check(got["commands"] == {"debug": "Shift+F9", "watchRun": "", "debugContinue": "F5", "stepOver": "F10", "stepInto": "F11",
                                "stepOut": "Shift+F11", "debugPause": "", "toggleBreakpoint": "F9"} and got["action"] == ["Toggle Breakpoint"] and got["hidden"],
            "its commands and keys (Debug, Watch it run, F5, F10, F11, Shift+F11, Pause, F9) and the editor's menu entry; the pane starts hidden",
            (got["commands"], got["action"]))
    c.check(got["click"] == [{"path": main, "lines": [15]}] and got["dot"] == [[15, "dbg-bp", ""]],
            "a click in the gutter's glyph margin puts a red dot (a breakpoint) on that line", (got["click"], got["dot"]))
    c.check(got["f9"] == [{"path": main, "lines": [15, 19]}] and got["f9off"] == got["click"], "F9 adds and takes away one on the cursor's line",
            (got["f9"], got["f9off"]))
    c.check(got["moved"] == [{"path": main, "lines": [17]}] and got["closed"] == got["click"] and [r[0] for r in got["reopened"]] == [15],
            "breakpoints move with their lines as the code changes, and stay while the tab is closed and opened again", (got["moved"], got["closed"], got["reopened"]))
    c.check(got["first"] == [main, {"debug": {"first": [{"cmd": "setBreakpoints", "file": main, "lines": [15]}, {"cmd": "continue"}]}}],
            "Debug runs the file with the debugger: its breakpoints first, then continue", got["first"])
    c.check(got["shown"] and "Starting the debugger" in got["starting"] and "Starting" in got["otherRun"],
            "the debug pane opens and the Debug button lights up; messages from another run are left alone", (got["shown"], got["starting"], got["otherRun"]))
    pz = got["paused"]
    c.check("Stopped at a breakpoint on line 15 of main.tuf." in pz["status"] and pz["line"] == [[15, "dbg-at paused", "dbg-line paused"]]
            and pz["on"] == {"continue": True, "next": True, "stepIn": True, "stepOut": True, "pause": False, "stop": True, "watch": True, "close": False},
            "paused: it says where and why, lights the line, and the toolbar's Continue and steps work (not Pause)", pz)
    c.check("In add()" in pz["vars"] and "main.tuf&#39;s top level" in pz["vars"] and ">n<" in pz["vars"] and ">rex<" in pz["vars"] and "▸" in pz["vars"]
            and "list (2)" in pz["vars"] and "Pet(name: &quot;Rex&quot;" in pz["vars"],
            "the Variables panel: the function's names, then the file's top level, and the values that open", pz["vars"][:800])
    c.check("add()" in pz["stack"] and "main.tuf:15" in pz["stack"] and "top level" in pz["stack"] and "main.tuf:19" in pz["stack"] and 'dbg-frame sel" data-i="0"' in pz["stack"],
            "the call stack: the function and its line, then the top level and the line that called it", pz["stack"])
    c.check(got["sentPaused"] == [{"cmd": "next"}, {"cmd": "expand", "path": ["top", "rex"], "open": True}, {"cmd": "frame", "index": 1}]
            and got["frameLine"] == [[19, "dbg-at frame", "dbg-line frame"]] and "In add()" not in got["frameVars"],
            "Step Over, opening rex, and another frame of the call stack (its line lit, its names shown) go to the program", (got["sentPaused"], got["frameLine"]))
    c.check("Running" in got["running"]["status"] and got["running"]["line"] == 0 and "show here when the program pauses" in got["running"]["vars"],
            "running again: the line goes dark and the names wait for the next pause", got["running"])
    mo = got["money"]
    c.check(mo["opened"] == [money, 0, True] and mo["line"] == [[4, "dbg-at paused", "dbg-line paused"]] and mo["changed"] == 1,
            "paused in money.tuf: that file opens with the line lit, and a value that changed is marked", mo)
    c.check(got["sentLive"] == [{"cmd": "setBreakpoints", "file": main, "lines": [9, 15]}, {"cmd": "setBreakpoints", "file": main, "lines": [3, 9, 15]}],
            "breakpoints changed while debugging go to the program at once", got["sentLive"])
    c.check(got["placed"]["bps"] == [{"path": main, "lines": [3, 10, 15]}] and "3:dbg-bp off" in got["placed"]["classes"] and "10:dbg-bp" in got["placed"]["classes"],
            "where the program says they stop: one on a blank line moves to the next statement, one where it never stops is hollow", got["placed"])
    w = got["watch"]
    c.check(w["sent"] == [{"cmd": "watch", "delay": 0.5}] and "Watching it run: line 18 of main.tuf." in w["status"] and w["line"] == [[18, "dbg-at watch", "dbg-line watch"]],
            "Watch it run: on at the slider's speed, each line lit as it runs, without taking the keyboard", w)
    e = got["error"]
    c.check("Stopped by an error on line 16 of main.tuf: I don&#39;t know what &#39;nope&#39; is." in e["status"] and "Continue ends the program." in e["status"]
            and "error" in e["cls"] and e["on"]["continue"] and not e["on"]["next"] and not e["on"]["stepIn"] and e["line"] == [[16, "dbg-at error", "dbg-line error"]],
            "pause on error: the error and its line in red, with Continue (to end it) and no steps", e)
    c.check(got["continueWatching"] == [{"cmd": "watch", "delay": 0.5}], "Continue while watching goes on watching", got["continueWatching"])
    c.check("Continue lets the program carry on: its window keeps running." in got["carriesOn"] and "Continue ends" not in got["carriesOn"],
            "...and an error in a function the program's window calls says Continue lets the program carry on", got["carriesOn"])
    en = got["ended"]
    c.check("The program has ended." in en["status"] and en["line"] == 0 and en["close"] and not en["debugOn"] and not en["eye"] and not en["state"]["watching"],
            "ended: it says so, the line goes dark, the eye goes out, and the pane can be closed", en)
    c.check("3:dbg-bp" in got["solid"] and "3:dbg-bp off" not in got["solid"], "a hollow breakpoint is a red dot again once the program says it stops there", got["solid"])
    c.check(got["late"] == {"state": "ended", "line": 0}, "a message that comes after the run has ended is left alone", got["late"])
    c.check(got["normalRun"] and got["stepStart"][1]["debug"]["first"][-1] == {"cmd": "next"} and not got["toasts"],
            "a run without the debugger closes the pane, and F10 with nothing debugged starts and pauses on the first line", (got["normalRun"], got["stepStart"]))
    c.check(got["eye"] == {"run": 1, "first": {"cmd": "watch", "delay": 0.5}, "on": True},
            "the eye, with nothing debugged, starts a run that's watched, and lights up", got["eye"])
    off = got["eyeOff"]
    c.check(off["sent"] == {"cmd": "watch", "delay": 0} and not off["watching"] and off["line"] == 0 and "Running. It stops" in off["status"]
            and "show here when the program pauses" in off["vars"],
            "the eye again while it runs: Watch it run goes off, and a line it had sent already isn't shown", off)
    c.check(got["eyeEnded"] == {"on": False, "watching": False} and got["eyeAgain"] == {"runs": 2, "first": {"cmd": "watch", "delay": 0.5}},
            "once a watched run has ended the eye goes out, and the eye starts the next one", (got["eyeEnded"], got["eyeAgain"]))
    nothing = {"continue": True, "next": False, "stepIn": False, "stepOut": False, "pause": True, "stop": True, "watch": True, "close": False}
    c.check(got["pausing"]["status"] == "Pausing…" and got["pausing"]["on"] == nothing
            and got["idle"]["status"] == "Your program is waiting for something to happen in its window. It pauses on the next line it runs."
            and got["idle"]["on"] == nothing, "Pause while nothing runs: it says the program waits for its window, and Continue can call the Pause off",
            (got["pausing"], got["idle"]))
    co = got["calledOff"]
    c.check(co["sent"] == [{"cmd": "pause"}, {"cmd": "continue"}] and "Running. It stops" in co["status"] and not co["on"]["continue"]
            and got["f5Off"] == [{"cmd": "pause"}, {"cmd": "continue"}], "...Continue (or F5) calls it off, and it runs on", (co, got["f5Off"]))
    es = got["editedSent"]
    c.check("You&#39;ve changed the code since it started. Debug again to run your changes." in got["edited"] and es["sent"] == []
            and es["bps"] == [{"path": main, "lines": [3, 10, 15, 20]}] and "20:dbg-bp" in got["editedPlaced"],
            "the code changed while it's debugged: it says so, and breakpoints put in it wait for the next Debug (the program runs it as it was)",
            (got["edited"], es, got["editedPlaced"]))
    c.check("changed the code" not in got["undone"] and got["undoneSent"] == [{"cmd": "setBreakpoints", "file": main, "lines": [3, 10, 15, 20]},
                                                                            {"cmd": "setBreakpoints", "file": main, "lines": [3, 10, 15]}],
            "...the change undone, they go to the program again", (got["undone"], got["undoneSent"]))
    c.check(got["renamedDir"] == [{"path": "C:\\proj\\kit\\tools.tuf", "lines": [3, 5]}] and got["renamedFile"] == [{"path": gears, "lines": [3, 5]}],
            "breakpoints go with a folder or a file renamed in the project tree, and are put on and taken off at its new path", (got["renamedDir"], got["renamedFile"]))
    c.check(got["renamedRun"] == [{"cmd": "setBreakpoints", "file": gears, "lines": [3, 5]}] and got["renamedLit"]["line"] == [[3, "dbg-at paused", "dbg-line paused"]]
            and "line 3 of gears.tuf" in got["renamedLit"]["status"] and got["renamedReopened"] == ["3:dbg-bp", "5:dbg-bp"],
            "...Debug sends them for the renamed file, its paused line is lit in the renamed tab, and they're there when it opens again",
            (got["renamedRun"], got["renamedLit"], got["renamedReopened"]))
    c.check(got["gear"] == {"on": [3], "hint": []} and got["gearClick"] == {"customizer": True, "bps": []},
            "Design Studio: a widget's own line has its gear, and a click there opens its customizer, not a breakpoint", (got["gear"], got["gearClick"]))
    c.check(got["propClick"] == {"gear": [], "hint": ["4:dbg-bp hint"], "customizer": False, "bps": [{"path": shop, "lines": [4]}]},
            "...on a line that sets something on it (title:color) a click puts a breakpoint, and doesn't open the customizer", got["propClick"])
    c.check(got["dotLine"] == {"gear": [], "customizer": False, "bps": [{"path": shop, "lines": [4]}]},
            "...a red dot put on its own line with F9 has no gear, and a click takes it away (no customizer)", got["dotLine"])
    c.check(got["reversed"] == {"customizer": False, "bps": [{"path": shop, "lines": [4]}]}
            and got["studioWidget"] == {"customizer": True, "bps": [{"path": shop, "lines": [4]}]},
            "...the same with the debugger's listener first", (got["reversed"], got["studioWidget"]))
    dl = got["dialog"]
    c.check(dl["opened"] == [money, 0, False] and dl["focused"] == 0 and dl["line"] == [[2, "dbg-at paused", "dbg-line paused"]]
            and dl["pos"] == {"lineNumber": 2, "column": 1} and "Stopped at a breakpoint on line 2 of money.tuf." in dl["status"],
            "a pause while a dialog is open (New Project, Search Everywhere, What's New...) opens the file, lights the line and fills the pane, "
            "and leaves the keyboard in the dialog", dl)
    c.check(got["dialogSame"] == {"focused": 0, "line": [[3, "dbg-at paused", "dbg-line paused"]], "pos": {"lineNumber": 3, "column": 1}}
            and got["noDialog"] == {"focused": 1, "line": [[4, "dbg-at paused", "dbg-line paused"]]},
            "...in the file on screen too; with no dialog open the keyboard goes to the paused line", (got["dialogSame"], got["noDialog"]))
    c.check(got["hiddenF9"] == {"same": [True, True], "toasts": ["Show the code (click its tab) to put a breakpoint on a line."] * 2} and got["shownF9"] == [3, 7, 10, 15],
            "F9 while Design Studio or Tuff Engine shows (the code editor hidden) only says to show the code; with the code on screen it puts a breakpoint",
            (got["hiddenF9"], got["shownF9"]))
    c.check(got["setLines"] == {"bps": [4, 12, 21], "dots": ["4:dbg-bp", "12:dbg-bp", "21:dbg-bp"], "sent": [{"cmd": "setBreakpoints", "file": main, "lines": [4, 12, 21]}]}
            and got["setLinesEdited"] == {"bps": [5], "sent": []},
            "TuffDebug.setLines (Auto Code Sort putting breakpoints back on their lines) draws them, none hollow, and sends them while it's debugged "
            "(not once the code has changed since it started)", (got["setLines"], got["setLinesEdited"]))
    fo = got["folder"]
    c.check(fo["sent"] == [{"stop": True}] and fo["state"] == "ended" and "The program was stopped." in fo["status"] and fo["line"] == 0
            and got["folderLate"] == {"state": "ended", "opened": 0, "line": 0} and got["folderIdle"] == [],
            "another folder opened (New Project, Open Folder) stops the program being debugged, a pause on its way after is left alone, "
            "and with nothing debugged nothing happens", (fo, got["folderLate"], got["folderIdle"]))
    c.check(got["errors"] == [], "nothing the debugger does throws", got["errors"])


# A file's whole new text in one go (ide.js's editsTo: a reload after another program changed the file, Replace in
# Files, a plugin's replaceAll, and Auto Code Sort), with Monaco's own text model and undo in Node: breakpoints (made as
# debugger.js makes them) and the cursor stay on the lines they're on, and one undo takes it back. ide.js's own
# editsTo and autoSort are taken from its source. One edit over the whole file put every dot on whatever line then
# held its old place in the text.
DEBUG_EDITS = r"""
const fs = require('fs'), path = require('path'), url = require('url');
const [ideFile, sortFile, dir] = process.argv.slice(1);
(async () => {
  if (!dir || !fs.existsSync(path.join(dir, 'esm'))) { console.log(JSON.stringify({ real: null })); return; }
  const imp = (p) => import(url.pathToFileURL(path.join(dir, 'esm', 'vs', p)).href);
  const { TextModel } = await imp('editor/common/model/textModel.js');
  const { Range } = await imp('editor/common/core/range.js');
  const { UndoRedoService } = await imp('platform/undoRedo/common/undoRedoService.js');
  const any = () => new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => '' : k === 'then' ? undefined : k === 'dispose' ? () => {} : k === 'languageId' ? 'tuff' : any()),
    apply: () => any(), construct: () => any() });
  const undo = new UndoRedoService({}, {});
  const make = (text) => new TextModel(text, 'tuff', TextModel.DEFAULT_CREATION_OPTIONS, null, undo, any(), any(), { createInstance: (C, ...a) => new C(...a, any(), any(), any(), any()) });
  // ide.js's own functions, from its source: each from its first line to the } under it
  const src = fs.readFileSync(ideFile, 'utf8').replace(/\r\n/g, '\n');
  const fn = (head) => { const at = src.indexOf(head); return at < 0 ? '' : src.slice(at, src.indexOf('\n  }\n', at) + 4); };
  const out = { real: true, found: [!!fn('function editsTo('), !!fn('async function autoSort(')] };
  const DOT = { glyphMarginClassName: 'dbg-bp', stickiness: 1 }; // (NeverGrowsWhenTypingAtEdges, as debugger.js has it)
  const dots = (m, lines, old = []) => m.deltaDecorations(old, lines.map((n) => ({ range: new Range(n, 1, n, 1), options: DOT })));
  const lineOf = (m, id) => m.getDecorationRange(id).startLineNumber;
  // The cursor, as Monaco brings it back after an edit made on the model: from a marker that grows at both ends.
  const cursor = (m, line, column) => {
    let id = m.deltaDecorations([], [{ range: new Range(line, column, line, column), options: { stickiness: 0 } }])[0];
    return { getModel: () => m, getPosition: () => { const r = m.getDecorationRange(id); return { lineNumber: r.startLineNumber, column: r.startColumn }; },
      setPosition: (p) => { id = m.deltaDecorations([id], [{ range: new Range(p.lineNumber, p.column, p.lineNumber, p.column), options: { stickiness: 0 } }])[0]; } };
  };
  // (without editsTo, the one edit over the whole file it replaced: what these checks see then)
  const whole = (m, text) => [{ range: m.getFullModelRange(), text }];
  const editsTo = out.found[0] ? new Function('window', `${fn('function editsTo(')}\nreturn editsTo;`)({ monaco: { Range } }) : whole;
  // One whole-file change as ide.js makes it (its own undo step): where the dots and the cursor are, and the text after
  // one undo.
  const change = async (before, after, lines, at, edits = editsTo) => {
    const m = make(before);
    const ids = dots(m, lines);
    const ed = cursor(m, ...at);
    m.pushStackElement();
    m.pushEditOperations([], edits(m, after), () => null);
    m.pushStackElement();
    const r = { same: m.getValue() === after, dots: ids.map((id) => [lineOf(m, id), m.getLineContent(lineOf(m, id)).trim()]), cursor: ed.getPosition() };
    await m.undo();
    r.undone = m.getValue() === before;
    return r;
  };
  const PROG = 'score = 0\nfor i in range(1, 4):\n    score += i\n    say score\nsay "done"\n';
  out.reloadWhole = await change(PROG, '# my game\n' + PROG, [3, 4], [4, 5], whole); // (the old way)
  out.reload = await change(PROG, '# my game\n' + PROG, [3, 4], [4, 5]); // another program put a line on top
  out.replace = await change(PROG, PROG.replace(/score/g, 'points'), [2, 3, 5], [5, 3]); // Replace in Files: four lines
  const SHOP = 'name = "Shop"\nprice = 3\nsay name\nsay price\nsay "bye"\n';
  // a plugin's replaceAll (Tuff Agents) adding a function, the cursor at the start of the line after it
  out.plugin = await change(SHOP, 'name = "Shop"\nprice = 3\nfunc tax(p):\n    return p * 1.2\nsay name\nsay price\nsay "bye"\n', [1, 3, 5], [3, 1]);
  out.cut = await change(PROG, 'score = 0\nsay "done"\n', [1, 5], [5, 2]); // lines taken away in the middle
  out.cutEnd = await change(PROG, 'score = 0\nfor i in range(1, 4):\n', [1, 2], [2, 4]); // ...and at the end

  // Pairs of short texts (made of a few lines, LF and CRLF): the edits make exactly the new text, one undo takes them
  // back, and a dot or the cursor (at the start or the end) on a line both keep stays on it: at the start, at the end,
  // or any line when they have as many lines. (A dot on an empty last line that lines go after moves down with them,
  // as when Enter is typed there.)
  let seed = 7;
  const rand = (n) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
  const WORDS = ['a', 'b', 'say x', '', '    c'];
  const textOf = (k, eol) => Array.from({ length: k }, () => WORDS[rand(WORDS.length)]).join(eol) + (rand(2) ? eol : '');
  const bad = [];
  let tried = 0;
  for (let i = 0; i < 1500 && bad.length < 5; i++) {
    const eol = rand(3) ? '\n' : '\r\n';
    const before = textOf(rand(6), eol);
    const after = textOf(rand(6), eol);
    const m = make(before);
    const old = m.getLinesContent();
    const next = after.split(/\r?\n/);
    let a = 0;
    while (a < old.length && a < next.length && old[a] === next[a]) a++;
    let b = 0;
    while (b < old.length - a && b < next.length - a && old[old.length - 1 - b] === next[next.length - 1 - b]) b++;
    const kept = old.map((l, k) => k + 1).filter((n) => (old.length === next.length ? old[n - 1] === next[n - 1] : n <= a || n > old.length - b)
      && !(old[n - 1] === '' && n === old.length && b === 0 && a === old.length));
    const to = (n) => (old.length === next.length || n <= a ? n : n + next.length - old.length);
    const ids = dots(m, kept);
    const marks = kept.map((n) => [n, m.deltaDecorations([], [{ range: new Range(n, 1, n, 1), options: { stickiness: 0 } }])[0],
      m.deltaDecorations([], [{ range: new Range(n, m.getLineMaxColumn(n), n, m.getLineMaxColumn(n)), options: { stickiness: 0 } }])[0]]);
    m.pushStackElement();
    m.pushEditOperations([], editsTo(m, after), () => null);
    m.pushStackElement();
    tried++;
    const want = after.split(/\r?\n/).join(m.getEOL());
    const moved = kept.filter((n, k) => lineOf(m, ids[k]) !== to(n));
    const cursorMoved = marks.filter(([n, s, e]) => { const rs = m.getDecorationRange(s), re = m.getDecorationRange(e);
      return rs.startLineNumber !== to(n) || rs.startColumn !== 1 || re.startLineNumber !== to(n) || re.startColumn !== m.getLineMaxColumn(to(n)); }).map(([n]) => n);
    const text = m.getValue();
    await m.undo();
    if (text !== want || moved.length || cursorMoved.length || m.getValue() !== before) bad.push({ before, after, text, moved, cursorMoved, undone: m.getValue() === before });
  }
  out.pairs = { tried, bad };

  // Auto Code Sort itself (ide.js's autoSort, with autosort.js and a TuffDebug with breakpoints() and setLines): each
  // dot goes back on its own line, the cursor stays on a line the sort left alone and goes to its own line otherwise,
  // and one undo takes it all back, the dots too (redo sorts them again).
  const FILE = 'C:\\proj\\main.tuf';
  const sortCase = async (before, lines, at) => {
    const m = make(before);
    let ids = dots(m, lines);
    const ed = cursor(m, ...at);
    const texts = lines.map((n) => m.getLineContent(n).replace(/\s+/g, ''));
    const atText = m.getLineContent(at[0]).trim();
    let calls = 0;
    const window = {
      TuffSort: require(sortFile),
      TuffDebug: { breakpoints: () => [{ path: FILE, lines: [...new Set(ids.map((id) => lineOf(m, id)))].sort((x, y) => x - y) }],
        setLines: (p, ls) => { calls++; ids = dots(m, ls, ids); } },
    };
    const api = { checkSource: async () => ({ ok: true }) };
    const autoSort = new Function('window', 'editor', 'api', 'toast', 'samePath', 'ext', 'activeTab', 'editsTo', `${fn('async function autoSort(')}\nreturn autoSort;`)(
      window, ed, api, () => {}, (x, y) => x.toLowerCase() === y.toLowerCase(), (p) => (p.match(/\.([^.]+)$/) || [, ''])[1], () => null, editsTo);
    await autoSort({ path: FILE, model: m }, { quiet: true });
    const r = { calls, dots: ids.map((id, k) => [lineOf(m, id), m.getLineContent(lineOf(m, id)).replace(/\s+/g, '') === texts[k]]),
      cursor: ed.getPosition(), cursorLine: m.getLineContent(ed.getPosition().lineNumber).trim() === atText };
    await m.undo();
    r.undone = m.getValue() === before;
    r.undoDots = ids.map((id) => lineOf(m, id));
    await m.redo();
    r.redoDots = ids.map((id) => lineOf(m, id));
    return r;
  };
  const MESSY = 'name = input("Name? ")\nif name is "Sam":\n  say "hi Sam"\nelse:\n  say "hello " + name\nsay "bye"\n';
  out.sortIndent = await sortCase(MESSY, [3, 5, 6], [6, 5]);
  out.sortIndentCursor = await sortCase(MESSY, [5], [5, 3]);
  // functions go last and imports first, each part gets a header, x=1 becomes x = 1
  out.sortMoved = await sortCase('func greet(who):\n  say "hi " + who\nx=1\nimport tgui\ngreet("Sam")\nsay x\n', [2, 3, 6], [6, 1]);
  // the same line in a function and in the main program, and in two functions: each dot goes with its own one
  out.sortSame = await sortCase('func a():\n    say x\nx = 1\nsay x\n', [2, 4], [4, 1]);
  out.sortTwo = await sortCase('func a():\n    say "hi"\nfunc b():\n    say "hi"\na()\nb()\n', [2, 4], [4, 1]);
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ crash: String(e.stack || e) })); });
"""


def debug_edits(c):
    """A file's whole new text in one go keeps breakpoints and the cursor on their lines (ide.js's editsTo and Auto Code
    Sort), with Monaco's own text model in Node (see DEBUG_EDITS)."""
    js = os.path.join(REPO, "tuffcode", "renderer", "js")
    monaco_dir = os.environ.get("TUFF_MONACO") or os.path.join(REPO, "tuffcode", "node_modules", "monaco-editor")
    try:
        p = subprocess.run(["node", "-e", DEBUG_EDITS, os.path.join(js, "ide.js"), os.path.join(js, "autosort.js"), monaco_dir], capture_output=True, text=True,
                           encoding="utf-8", timeout=120)
        got = json.loads(p.stdout.strip().splitlines()[-1])
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the whole-file edit checks")
        return
    except (ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        got = {"crash": str(exc), "stderr": locals().get("p") and p.stderr[-500:]}
    if not c.check("crash" not in got, "the whole-file edit checks run (ide.js's editsTo and autoSort with Monaco's own text model)", got):
        return
    if got["real"] is None:
        c.check(True, "monaco-editor isn't installed here: skipped the whole-file edit checks")
        return
    c.check(got["found"] == [True, True], "ide.js has editsTo (a file's whole new text, over only the lines that change) and autoSort", got["found"])
    c.check(got["reloadWhole"]["dots"] == [[3, "for i in range(1, 4):"], [4, "score += i"]],
            "(one edit over the whole file, as before, puts the breakpoints on other lines: this check sees it)", got["reloadWhole"])
    c.check(got["reload"] == {"same": True, "dots": [[4, "score += i"], [5, "say score"]], "cursor": {"lineNumber": 5, "column": 5}, "undone": True},
            "a reload after another program put a line on top: the breakpoints and the cursor move down with their lines, and one undo takes it back",
            got["reload"])
    c.check(got["replace"] == {"same": True, "dots": [[2, "for i in range(1, 4):"], [3, "points += i"], [5, 'say "done"']], "cursor": {"lineNumber": 5, "column": 3},
                               "undone": True},
            "Replace in Files changing four lines: breakpoints between them and on them stay on their lines", got["replace"])
    c.check(got["plugin"] == {"same": True, "dots": [[1, 'name = "Shop"'], [5, "say name"], [7, 'say "bye"']], "cursor": {"lineNumber": 5, "column": 1}, "undone": True},
            "a plugin's replaceAll adding a function (Tuff Agents): the breakpoints and the cursor after it move down with their lines", got["plugin"])
    c.check(got["cut"] == {"same": True, "dots": [[1, "score = 0"], [2, 'say "done"']], "cursor": {"lineNumber": 2, "column": 2}, "undone": True}
            and got["cutEnd"] == {"same": True, "dots": [[1, "score = 0"], [2, "for i in range(1, 4):"]], "cursor": {"lineNumber": 2, "column": 4}, "undone": True},
            "lines taken away, in the middle and at the end: the ones left keep their breakpoints and the cursor", (got["cut"], got["cutEnd"]))
    c.check(got["pairs"] == {"tried": 1500, "bad": []},
            "1500 pairs of short texts (LF and CRLF): the edits make exactly the new text, one undo takes them back, and dots and the cursor on the "
            "lines kept stay on them", got["pairs"])
    si, sc, sm = got["sortIndent"], got["sortIndentCursor"], got["sortMoved"]
    c.check(si == {"calls": 1, "dots": [[3, True], [5, True], [6, True]], "cursor": {"lineNumber": 6, "column": 5}, "cursorLine": True, "undone": True,
                   "undoDots": [3, 5, 6], "redoDots": [3, 5, 6]}
            and sc["dots"] == [[5, True]] and sc["cursorLine"] and sc["undone"],
            "Auto Code Sort fixing the indentation: each breakpoint stays on its line, the cursor on a line it left alone stays put (and one on a "
            "line it changed stays on that line), and one undo takes it back", (si, sc))
    c.check(sm == {"calls": 1, "dots": [[12, True], [5, True], [7, True]], "cursor": {"lineNumber": 7, "column": 1}, "cursorLine": True, "undone": True,
                   "undoDots": [2, 3, 6], "redoDots": [12, 5, 7]},
            "Auto Code Sort moving functions last and imports first (and x=1 to x = 1): each breakpoint goes back on its own line, the cursor too, "
            "and undo puts the breakpoints back where they were (redo where the sort put them)", sm)
    ss, s2 = got["sortSame"], got["sortTwo"]
    c.check(ss["dots"] == [[8, True], [3, True]] and ss["cursor"]["lineNumber"] == 3 and ss["undoDots"] == [2, 4]
            and s2["dots"] == [[8, True], [12, True]] and s2["cursor"]["lineNumber"] == 12 and s2["undoDots"] == [2, 4],
            "...with the same line in a function and in the main program, or in two functions, each breakpoint (and the cursor) goes with its own one",
            (ss, s2))


def t_debug(c):
    """Console only, no window: 1.5.0's debugger, with this test as TuffCode (DebugLink). In both runtimes:
    breakpoints in two files and the Variables panel's values (kinds' objects, lists and dictionaries open up), the
    call stack and its frames' names, Step Over, Into and Out across functions, an action and an imported file, pause
    on error, input() while debugging, Watch it run, and loops written on one line. Then Pause and Stop, a deep call
    stack, tterm and tmusic programs, TuffCode going away, --debug, where breakpoints stop, its speed, values as say
    shows them, the functions a window calls (with no window), main.js's side (debug.js) and the editor's and the
    debug pane's (debugger.js, with Design Studio's studio.js), both with Node, and a file's whole new text keeping
    breakpoints on their lines (ide.js, with Monaco's own text model)."""
    for slow in (False, True):
        mode = "the tree walker" if slow else "compiled"
        debug_breakpoints(c, slow, mode)
        debug_steps(c, slow, mode)
        debug_errors(c, slow, mode)
        debug_input(c, slow, mode)
        debug_watch(c, slow, mode)
        debug_loops(c, slow, mode)
    debug_breakpoints(c, False, "compiled", crlf=True)
    debug_places(c)
    debug_more(c)
    debug_speed(c)
    debug_values(c)
    debug_windows(c)
    debug_relay(c)
    debug_ui(c)
    debug_edits(c)


# ---------------------------------------------------------------- New Project's starters (1.5.0)

STARTERS_DIR = os.path.join(REPO, "tuffcode", "starters")
# An atgui program with no window at all, for a starter's self-test: pywebview can't load, and a stand-in takes the
# window's place (as in test/atgui/close_test.py), clicking a popup's OK or Yes as soon as it shows.
STARTERS_NO_WINDOW = r"""
import json, os, sys, time
sys.modules["webview"] = None
sys.path.insert(0, sys.argv[1])
import tuff, tuff_view

class FakeWindow:
    def __init__(self, view):
        self.view, self.seq = view, 0
    def run_js(self, code):
        for _seq, cmds in json.loads(code[len("__tv.apply("):-1]):
            for cmd in cmds:
                if cmd[0] == "s" and str(cmd[2].get("html", "")) in ("<span>OK</span>", "<span>Yes</span>"):
                    self.seq += 1
                    self.view._on_events(self.seq, [{"type": "click", "path": [cmd[1]]}])
    def destroy(self):
        self.view._on_closing()
    def __getattr__(self, name):
        return lambda *args: None

def stand_in(view):
    view._win = FakeWindow(view)
    view._on_ready({"w": 460, "h": 640})
    deadline = time.monotonic() + 20
    while not view._closed and time.monotonic() < deadline:
        time.sleep(0.01)
    view._on_closed()

tuff_view.View._open = stand_in
sys.argv = [os.path.join(sys.argv[1], "tuff.py"), sys.argv[2]]
sys.exit(tuff.main())
"""
# A tdraw program with stand-ins for tkinter and turtle, so no window opens: it counts what the pen did.
STARTERS_NO_TK = r"""
import collections, json, os, sys, types
calls = collections.Counter()
class Fake:
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        def call(*args, **kwargs):
            calls[name] += 1
            return [] if name in ("turtles", "find_all") else 0.0 if name in ("xcor", "ycor") else None
        return call
tk, turtle = types.ModuleType("tkinter"), types.ModuleType("turtle")
tk.Tk, tk.Canvas, tk.TclError = Fake, Fake, type("TclError", (Exception,), {})
turtle.TurtleScreen, turtle.RawTurtle, turtle.Terminator = Fake, Fake, type("Terminator", (Exception,), {})
sys.modules["tkinter"], sys.modules["turtle"] = tk, turtle
sys.path.insert(0, sys.argv[1])
import tuff
sys.argv = [os.path.join(sys.argv[1], "tuff.py"), sys.argv[2]]
code = tuff.main()
print("PEN " + json.dumps(calls), flush=True)
sys.exit(code)
"""
# The Habit Tracker's habits.tuf on its own, in a console program: streaks across months and leap years, the
# chart's week, and saving.
STARTERS_HABITS = """import habits.tuf
run = habits.Habit("Run", ["2026-10-25", "2026-10-26", "2026-10-27"])
say run:streak("2026-10-27")
say run:streak("2026-10-28")
say run:streak("2026-10-29")
say habits.Habit("Leap", ["2028-02-28", "2028-02-29", "2028-03-01"]):streak("2028-03-01")
say habits.Habit("New year", ["2025-12-31", "2026-01-01"]):streak("2026-01-01")
say habits.day_number("2026-03-01") - habits.day_number("2026-02-28")
say habits.day_number("2100-03-01") - habits.day_number("2100-02-28")
say habits.day_number("2000-03-01") - habits.day_number("2000-02-28")
say habits.last_week([run], "2026-10-27")
say len(habits.load())
run:toggle("2026-10-28")
habits.save([run])
say habits.load()[0]
"""
# The Habit Tracker's window, driven from inside (app:after): add, a name that's there already, tick, delete (its
# confirm answered Yes), untick.
STARTERS_HABITS_UI = """

func selftest():
    say len(my_habits)
    new_name:set "Stretch"
    add_habit()
    new_name:set "stretch"
    add_habit()
    say len(my_habits)
    tick("Stretch")
    say summary:value()
    say week:value()
    say done_bar:value()
    delete_habit("Read 10 pages")
    say habit_list:items()
    tick("Stretch")
    say habit_called("Stretch"):done_on(today())
    app:close

app:after(0.3, selftest)
"""
# Coin Collector, driven from inside: a coin put on the hero is picked up, then the time runs out.
STARTERS_COINS = """

func selftest():
    first = coins:items()[0]
    first:move_to(hero:x(), hero:y())
    game:after(0.2, report)

func report():
    say f"score {score}, coins {coins:count()}, bugs {bugs:count()}, paused {game:paused()}"
    times_up()
    say f"best {best}, paused {game:paused()}"
    game:close()

game:after(0.5, selftest)
"""


def starters_copy(sid):
    """A fresh copy of a starter in OUT/starters/<id> (runs leave saves behind): its folder."""
    import shutil
    folder = os.path.join(OUT, "starters", sid)
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(os.path.join(STARTERS_DIR, sid), folder)
    return folder


def starters_env():
    """A plain pipe: no Run panel, no sound, and games' saves and songs in the test's own folder."""
    env = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW", "TUFF_NO_WRITES", "TUFF_BASE_DIR")}
    env.update({"PYTHONIOENCODING": "utf-8", "TUFF_NO_SOUND": "1", "TUFF_SAVE_DIR": os.path.join(OUT, "starters", "saves"),
                "TUFF_MUSIC_DIR": os.path.join(OUT, "starters", "music")})
    return env


def starters_run(folder, stdin="", args=None, env=None, main="main.tuf", timeout=90):
    """Runs a program in its folder, with its answers through a pipe: (exit code, stdout, stderr, seconds)."""
    t0 = time.perf_counter()
    p = subprocess.run(args or tuff_cmd() + [main], input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=folder, env={**starters_env(), **(env or {})}, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, time.perf_counter() - t0


def starters_add(folder, code_text, main="main.tuf"):
    with open(os.path.join(folder, main), "a", encoding="utf-8") as f:
        f.write(code_text)


def starters_snake(c, extra):
    """Snake through a pipe, with screen:press keys (and anything else) put in just before screen:every_frame:
    (exit code, stdout, stderr, the final screen's rows, the folder). Food the checks don't place goes in the top left
    corner, out of every check's way: nothing seeds random() in a pipe, and a * on the snake's row would be eaten."""
    folder = starters_copy("snake")
    path = os.path.join(folder, "main.tuf")
    with open(path, encoding="utf-8") as f:
        code_text = f.read()
    hook = "start()\nscreen:every_frame(step)"
    spot = "food = [random(1, width - 2), random(1, height - 2)]"
    c.check(hook in code_text and spot in code_text, "snake: main.tuf starts the game with start() and screen:every_frame(step), "
            "and puts the food anywhere with random()", None)
    with open(path, "w", encoding="utf-8") as f:  # (only the first spot: the one after it, for food on the snake, stays random)
        f.write(code_text.replace(spot, "food = [1, 1]", 1).replace(hook, "start()\n" + extra + "screen:every_frame(step)"))
    code, out, err, _s = starters_run(folder)
    lines = out.splitlines()
    top = next((i for i, x in enumerate(lines) if x.startswith("┌")), None)
    return code, out, err, lines[top:top + 16] if top is not None else [], folder


def starters_weather(c, folder, stdin="Testville\nAtlantis\n\n", first=0):
    """Weather against a stand-in for Open-Meteo on this computer: the copy's two addresses point at it. Its three days
    start first days from today here: they're the place's own days (timezone=auto), so far away they can start
    tomorrow (1) or yesterday (-1)."""
    import datetime
    import http.server
    import threading
    import urllib.parse
    asked = []
    days = [(datetime.date.today() + datetime.timedelta(days=first + i)).isoformat() for i in range(3)]

    class Answer(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(u.query)
            asked.append((u.path, q))
            if u.path == "/geo":
                body = {"results": [{"name": "Testville", "country": "Nowhere Land", "latitude": 51.5, "longitude": -0.12}]} \
                    if q.get("name") == ["Testville"] else {"generationtime_ms": 0.4}
            else:
                body = {"current": {"temperature_2m": 12.6, "apparent_temperature": 10.2, "relative_humidity_2m": 81, "weather_code": 61,
                                    "wind_speed_10m": 14.4},
                        "daily": {"time": days, "weather_code": [61, 3, 0],
                                  "temperature_2m_max": [14.1, 15.9, 17.4], "temperature_2m_min": [8.2, 9.6, 7.5]}}
            data = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        path = os.path.join(folder, "main.tuf")
        with open(path, encoding="utf-8") as f:
            code_text = f.read()
        urls = ('"https://geocoding-api.open-meteo.com/v1/search"', '"https://api.open-meteo.com/v1/forecast"')
        c.check(all(u in code_text for u in urls), "weather: asks Open-Meteo's places and forecast addresses", None)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code_text.replace(urls[0], f'"{base}/geo"').replace(urls[1], f'"{base}/forecast"'))
        result = starters_run(folder, stdin)
    finally:
        server.shutdown()
    return result, asked


# The file run last, before and after another folder opens: ide.js's runTarget, rerun, buildTarget and openStudio (cut
# from its source) with no .tuf tab open.
STALE_RUN = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8').replace(/\r\n/g, '\n');
const line = (head) => { const at = src.indexOf(head); return at < 0 ? '' : src.slice(at, src.indexOf('\n', at)); };
const fn = (head) => { const at = src.indexOf(head); return at < 0 ? '' : src.slice(at, src.indexOf('\n  }\n', at) + 4); };
const state = { root: 'C:\\Old', lastRunFile: 'C:\\Old\\main.tuf' };
let did = [];
const f = new Function('state', 'engine', 'studio', 'SEP', 'activeTab', 'ext', 'join', 'runCurrent', 'saveAll', 'startRun', 'hideMenus', 'api', 'showStudio',
  [line('const isUnder = '), line('const lastRun = '), fn('function runTarget('), fn('async function rerun('), fn('function buildTarget('),
    fn('async function openStudio('), 'return { runTarget, rerun, buildTarget, openStudio };'].join('\n'))(
  state, { visible: false, file: null }, { file: null }, '\\', () => null, (p) => (p.match(/\.([^.\\]+)$/) || [, ''])[1], (a, b) => `${a}\\${b}`,
  () => did.push('current'), async () => {}, (p) => did.push('start', p), () => {}, { fs: { exists: async () => true } }, (p) => did.push(p));
(async () => {
  const out = [];
  for (const root of ['C:\\Old', 'C:\\Other']) {
    state.root = root;
    const r = { run: f.runTarget() };
    did = [];
    await f.rerun();
    r.rerun = did;
    r.build = f.buildTarget();
    did = [];
    await f.openStudio();
    r.studio = did[0];
    out.push(r);
  }
  console.log(JSON.stringify(out));
})().catch((e) => console.log(JSON.stringify({ crash: String(e.stack || e) })));
"""


def t_starters(c):
    """1.5.0, no window and no sound: New Project's starters (tuffcode/starters). Each is listed with its picture and
    passes --check. The console ones run in a pipe with their answers; Snake (tterm) with screen:press keys; Coin
    Collector (tgame) in Tuff Engine's preview and through headless.py; the Habit Tracker (atgui) with a stand-in for
    its window, and the Drawing (tdraw) with a stand-in pen; Weather against a stand-in weather service, and with no
    internet. Then the create logic and the gallery in Node (new_project_harness.js), and how the IDE and the built
    app find the starters."""
    import datetime
    import shutil
    import socket
    import wave
    root = os.path.join(OUT, "starters")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    with open(os.path.join(STARTERS_DIR, "starters.json"), encoding="utf-8") as f:
        listed = json.load(f)
    ids = [s.get("id") for s in listed]
    c.check(ids == ["blank", "hello", "quiz", "habits", "shop", "snake", "coins", "music", "drawing", "weather"], "starters.json lists the 10 starters", ids)
    for s in listed:
        sid = s.get("id")
        c.check(os.path.isfile(os.path.join(STARTERS_DIR, sid, "main.tuf")) and os.path.isfile(os.path.join(STARTERS_DIR, f"{sid}.svg"))
                and s.get("name") and s.get("about") and isinstance(s.get("tags"), list) and re.fullmatch(r"#[0-9a-f]{6}", s.get("color", ""))
                and all(isinstance(u, str) and u for u in s.get("uses", [])),
                f"{sid}: main.tuf, a picture, a name, an about line, tags, what it uses (for the search) and a colour", s)
    uses = {s.get("id"): s.get("uses", []) for s in listed}
    c.check(all(lib in uses.get(sid, []) for sid, lib in (("snake", "tterm"), ("coins", "tgame"), ("music", "tmusic"), ("drawing", "tdraw"),
                                                             ("weather", "tap"), ("habits", "atgui"), ("habits", "import"), ("shop", "import"))),
            "searching for a library finds the starters that use it (starters.json's uses: tterm, tgame, tmusic, tdraw, tap, atgui, import)", uses)
    left = [os.path.relpath(os.path.join(d, f), STARTERS_DIR) for d, _dirs, files in os.walk(STARTERS_DIR) for f in files
            if f in ("best.json", "habits.json", "receipt.txt", "my_tune.wav", ".DS_Store") or "__pycache__" in d]
    c.check(not left, "no starter has a file a run leaves behind (it would go into every new project)", left)
    for d, _dirs, files in os.walk(STARTERS_DIR):
        for f in sorted(files):
            if f.endswith(".tuf"):  # in its own folder, so import money.tuf finds money.tuf
                p = subprocess.run(tuff_cmd() + ["--check", f], cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   env=starters_env(), stdin=subprocess.DEVNULL, timeout=60)
                c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"{os.path.relpath(os.path.join(d, f), STARTERS_DIR)} passes --check",
                        (p.stdout + p.stderr)[:400])

    # ---- console starters, through a pipe
    code, out, err, _s = starters_run(starters_copy("blank"))
    c.check(code == 0 and out == "" and err == "", "blank: runs, and says nothing (it's all comments)", (code, out, err))
    folder = starters_copy("hello")
    code, out, err, _s = starters_run(folder, "Sam\n12\n")
    c.check(code == 0 and "Nice to meet you, Sam!" in out and "In ten years you'll be 22." in out and "TUFF IS FUN!" in out
            and out.count("Counting: ") == 3 and "This line is purple." in out and "Bye for now, Sam!" in out and not err,
            "hello: asks a name and an age, counts, shouts and says goodbye", (out + err)[-600:])
    code, out, err, _s = starters_run(folder, "  \nold\n")
    c.check(code == 0 and "Nice to meet you, friend!" in out and "That isn't a number, but that's OK." in out,
            "hello: no name is 'friend', and an age that isn't a number is fine", (out + err)[-400:])
    folder = starters_copy("quiz")
    code, out, err, _s = starters_run(folder, "42\n MARS \n6\nhoney\nThe Pacific Ocean\n")
    c.check(code == 0 and out.count("Right!") == 4 and "Not quite: it's 8." in out and "You got 4 out of 5 (80%)." in out and "Well done!" in out,
            "quiz: answers count in any case and with spaces, a wrong one shows the answer, and the score is a percent", (out + err)[-600:])
    code, out, err, _s = starters_run(folder, "forty-two\nmars\neight\nhoney\npacific\n")
    c.check(code == 0 and "You got 5 out of 5 (100%)." in out and "A perfect score!" in out, "quiz: every answer in a question's list counts", (out + err)[-300:])
    folder = starters_copy("shop")
    code, out, err, _s = starters_run(folder, "1\n3\n9\n2\n5\n4\n2\nx\n3\n0\n\n")
    receipt = ""
    if os.path.isfile(os.path.join(folder, "receipt.txt")):
        with open(os.path.join(folder, "receipt.txt"), encoding="utf-8") as f:
            receipt = f.read()
    c.check(code == 0 and "Added 3 x Apple. Basket so far: $1.35" in out and "There's no number 9 on the shelf." in out
            and "Sorry, there are only 4 left." in out and "There's no number x on the shelf." in out and "Type how many you'd like" in out
            and "Thanks for shopping!" in out, "shop: buys with money.tuf's prices, and turns down what isn't on the shelf or in stock", (out + err)[-800:])
    c.check(re.search(r"3 x Apple +\$1\.35", receipt) and re.search(r"2 x Cheese +\$7\.60", receipt) and re.search(r"Subtotal +\$8\.95", receipt)
            and re.search(r"Tax \(20%\) +\$1\.79", receipt) and re.search(r"Total +\$10\.74", receipt),
            "shop: the receipt (money.tuf's tax and as_money) is in receipt.txt", receipt)
    folder = starters_copy("shop")
    code, out, err, _s = starters_run(folder, "\n")
    c.check(code == 0 and "Nothing in the basket" in out and not os.path.exists(os.path.join(folder, "receipt.txt")),
            "shop: paying for nothing writes no receipt", (out + err)[-300:])
    folder = starters_copy("music")
    code, out, err, secs = starters_run(folder, "1\ni\nchip\n2\nw\nC4 E4 G4 C5*2\nw\nH4 C4\ni\ntrumpet\ns\nb\nzz\n9\nq\n")
    try:
        with wave.open(os.path.join(folder, "my_tune.wav")) as w:
            seconds = w.getnframes() / w.getframerate()
    except (OSError, wave.Error, EOFError):
        seconds = None
    c.check(code == 0 and "Playing Twinkle Twinkle on the piano..." in out and "Playing Ode to Joy on the chip..." in out
            and "There's no trumpet, so it's still chip." in out and "Playing the band..." in out
            and out.count("Type a number or a letter from the list.") == 2 and out.rstrip().endswith("Bye!") and not err,
            "music: plays tunes, changes the instrument, plays the band, and asks again after a wrong choice", (out + err)[-800:])
    c.check("Those notes didn't work:" in out and '"H4" (note 1) isn\'t a note' in out, "music: a mistake in typed notes is shown, and it carries on", out[-600:])
    c.check(seconds is not None and abs(seconds - 2.5) < 0.1 and "Saved my_tune.wav (2.5 seconds)" in out,
            "music: saves the last tune (C4 E4 G4 C5*2) as my_tune.wav, 2.5 seconds long", (seconds, out[-300:]))
    c.check(secs < 30, f"music: in a pipe nothing plays, so nothing waits ({secs:.1f} s)", secs)

    # ---- Weather: a stand-in weather service, then no internet (a proxy that refuses), with the real addresses
    weekday = lambda days_on: (datetime.date.today() + datetime.timedelta(days=days_on)).strftime("%A")  # in days from today here
    (code, out, err, _s), asked = starters_weather(c, starters_copy("weather"))
    forecast = next((q for p, q in asked if p == "/forecast"), {})
    c.check(code == 0 and "Testville, Nowhere Land" in out and "Now: Light rain, 13°C (feels like 10°C)" in out
            and "Wind 14 km/h, humidity 81%" in out and re.search(r"Today +Light rain +8 to 14°C", out) and re.search(r"Tomorrow +Cloudy +10 to 16°C", out)
            and re.search(rf"\n +{weekday(2)} +Clear sky +8 to 17°C", out) and not err,
            f"weather: finds the place, then shows the weather now and for three days (the third is {weekday(2)})", (out + err)[-800:])
    c.check(forecast.get("latitude") == ["51.5"] and forecast.get("longitude") == ["-0.12"] and "weather_code" in forecast.get("current", [""])[0]
            and "temperature_2m_max" in forecast.get("daily", [""])[0], "weather: asks for the forecast where the place is", asked)
    c.check("I couldn't find a place called Atlantis. Check the spelling?" in out and out.rstrip().endswith("Bye!"),
            "weather: a place that isn't there says so, and Enter stops", out[-300:])
    # Far away it can be tomorrow already (Sydney, seen from London in the evening), or still yesterday: the days are
    # the place's own, so the third one is named from the place's today
    for first, where in ((1, "a day ahead of this computer"), (-1, "a day behind it")):
        (code, out, err, _s), _asked = starters_weather(c, starters_copy("weather"), "Testville\n\n", first)
        c.check(code == 0 and re.search(r"Today +Light rain", out) and re.search(r"Tomorrow +Cloudy", out)
                and re.search(rf"\n +{weekday(first + 2)} +Clear sky +8 to 17°C", out) and not err,
                f"weather: for a place {where}, Today and Tomorrow are its own, and the third day is {weekday(first + 2)}", (out + err)[-500:])
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    proxy = f"http://127.0.0.1:{s.getsockname()[1]}"  # nothing answers there once it's closed
    s.close()
    code, out, err, _s = starters_run(starters_copy("weather"), "London\n\n", env={"HTTPS_PROXY": proxy, "HTTP_PROXY": proxy, "https_proxy": proxy,
                                                                                  "http_proxy": proxy, "NO_PROXY": "", "no_proxy": ""})
    c.check(code == 0 and "Couldn't get the weather:" in out and "Check that the computer is on the internet" in out and out.rstrip().endswith("Bye!")
            and "Tuff error" not in err, "weather: with no internet, try and catch say so kindly, and it carries on", (out + err)[-500:])

    # ---- the Habit Tracker: habits.tuf on its own, then the window with a stand-in for it
    folder = starters_copy("habits")
    with open(os.path.join(folder, "check_habits.tuf"), "w", encoding="utf-8") as f:
        f.write(STARTERS_HABITS)
    code, out, err, _s = starters_run(folder, main="check_habits.tuf")
    c.check(code == 0 and out.splitlines() == ["3", "3", "0", "3", "2", "1", "1", "2", "[0, 0, 0, 0, 1, 1, 1]", "3",
                                               'Habit(name: "Run", days: ["2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28"])'],
            "habits.tuf: streaks (a day not ticked yet doesn't break one; months, years and leap days), the week, three to start and "
            "saving Habits in habits.json", (out + err)[-600:])
    if RUNTIME:
        c.check(True, "the Habit Tracker's and the Drawing's stand-in runs need tuff.py: skipped with --runtime")
    else:
        folder = starters_copy("habits")
        starters_add(folder, STARTERS_HABITS_UI)
        code, out, err, secs = starters_run(folder, args=[sys.executable, "-c", STARTERS_NO_WINDOW, REPO, "main.tuf"])
        said = out.splitlines()
        saved = read_json(os.path.join(folder, "habits.json")) or []
        c.check(code == 0 and not err and len(said) == 7 and said[:2] == ["3", "4"] and re.fullmatch(r"\w+ \d+ \w+: 1 of 4 done", said[2])
                and said[3:] == ["[0, 0, 0, 0, 0, 0, 1]", "25", '["Drink water", "Go for a walk", "Stretch"]', "false"],
                f"habits: the window (a stand-in) adds a habit but not the same one twice, ticks it, deletes one after Yes, and unticks ({secs:.1f} s)",
                (out + err)[-800:])
        c.check([h.get("name") for h in saved] == ["Drink water", "Go for a walk", "Stretch"] and all(h.get("$kind") == "Habit" for h in saved)
                and saved[2].get("days") == [], "habits: every change is saved in habits.json, as Habits", saved)
        # ---- the Drawing, with a stand-in pen
        code, out, err, _s = starters_run(starters_copy("drawing"), args=[sys.executable, "-c", STARTERS_NO_TK, REPO, "main.tuf"])
        pen = json.loads(out.split("PEN ", 1)[1]) if "PEN " in out else {}
        c.check(code == 0 and not err.strip() and pen.get("forward", 0) > 100 and pen.get("begin_fill") == 5 and pen.get("dot") == 2
                and pen.get("write") == 1 and pen.get("onclick") == 1 and pen.get("mainloop") == 1,
                "drawing: draws with a stand-in pen (no window): the spiral, 5 stars, the moon, the words, and waits for clicks", (pen, err[-300:]))

    # ---- Snake, through a pipe with screen:press keys
    code, out, err, screen, folder = starters_snake(c, "")
    c.check(code == 0 and len(screen) == 16 and "GAME OVER" in "\n".join(screen) and "Score 0  Best 0" in screen[0] and screen[-1].startswith("└")
            and out.rstrip().endswith("Thanks for playing! Your best is 0.") and not os.path.exists(os.path.join(folder, "best.json")),
            "snake: with no keys it runs into the wall: game over, and nothing is saved", out[-900:])
    code, out, err, screen, folder = starters_snake(c, "food = [12, 8]\n")
    c.check(code == 0 and "Score 1  Best 1" in screen[0] and read_json(os.path.join(folder, "best.json")) == 1
            and out.rstrip().endswith("Your best is 1."), "snake: it eats the food in its way, grows, and the best score is saved in best.json", out[-900:])
    code, out, err, screen, folder = starters_snake(c, 'food = [12, 8]\nscreen:press("space", 90)\nscreen:press("up", 100)\n')
    c.check(code == 0 and "@" in screen[1] and "GAME OVER" in "\n".join(screen) and "Best 1" in screen[0] and read_json(os.path.join(folder, "best.json")) == 1,
            "snake: Space plays again after game over, and the new snake turns up into the top wall", out[-900:])
    for key in ("q", "escape"):  # after eating once: the new best counts, though the snake never hit anything
        code, out, err, screen, folder = starters_snake(c, f'food = [12, 8]\nscreen:press("{key}", 40)\n')
        c.check(code == 0 and "GAME OVER" not in "\n".join(screen) and "Score 1  Best 1" in screen[0] and read_json(os.path.join(folder, "best.json")) == 1
                and out.rstrip().endswith("Your best is 1."), f"snake: {'Q' if key == 'q' else 'Esc'} stops the game mid-game, and keeps the new best score",
                out[-900:])

    # ---- Coin Collector: Tuff Engine's preview, then headless.py with a self-test
    folder = starters_copy("coins")
    code, out, err, d, secs = scene(os.path.join(folder, "main.tuf"))
    things = {t.get("var"): t for t in d.get("things", []) if t.get("var")}
    c.check(code == 0 and d.get("error") is None and d.get("mode") == "2d" and d.get("title") == "Coin Collector" and "hero" in things,
            f"coins: Tuff Engine's preview runs it ({secs:.1f} s), with the hero", {k: d.get(k) for k in ("error", "mode", "title", "stopped")})
    if not RUNTIME:
        folder = starters_copy("coins")
        starters_add(folder, STARTERS_COINS)
        with open(os.path.join(folder, "events.json"), "w", encoding="utf-8") as f:
            json.dump({"3": [{"type": "keydown", "code": "Space"}], "4": [{"type": "keyup", "code": "Space"}],
                       "10": [{"type": "keydown", "code": "ArrowRight"}], "25": [{"type": "keyup", "code": "ArrowRight"}]}, f)
        code, out, err, secs = starters_run(folder, args=[sys.executable, os.path.join(HERE, "headless.py"), "main.tuf", "out.json", "900", "events.json"])
        cmds = read_json(os.path.join(folder, "out.json")) or []
        images = {cmd[1]: cmd[5].get("src") for cmd in cmds if cmd[0] == "c" and len(cmd) > 5 and cmd[3] == "image"}
        hero = next((i for i, src in images.items() if src == "asset:pictures/hero.png"), None)
        walked = any(cmd[0] == "s" and cmd[1] == hero and (cmd[2].get("play") or [None])[0] == [1, 2, 3, 4] for cmd in cmds)
        texts = [cmd[2]["text"] for cmd in cmds if cmd[0] == "s" and "text" in cmd[2]]
        m = re.search(r"^score (\d+), coins 5, bugs 1, paused false\nbest (\d+), paused true$", out, re.M)
        c.check(code == 0 and "Tuff error" not in err and m and int(m.group(1)) >= 1 and m.group(1) == m.group(2),
                f"coins: headless, Space starts it, a coin on the hero is picked up (a new one comes), and when the time's up the game ends ({secs:.1f} s)",
                (out + err)[-600:])
        c.check(set(images.values()) == {"asset:pictures/hero.png", "asset:pictures/coin.png", "asset:pictures/bug.png"} and walked and "Coins: 1" in texts,
                "coins: the pictures come from the pictures folder, the hero walks while an arrow is held, and the score goes up", (images, texts[:6]))
        saves = read_json(os.path.join(root, "saves", "Coin Collector.json")) or {}
        c.check(m and saves.get("saves", {}).get("best") == int(m.group(2)), "coins: the best score is saved with game:save", saves)
    with open(os.path.join(STARTERS_DIR, "coins", "main.tuf"), encoding="utf-8") as f:
        coins_code = f.read()
    c.check(re.search(r"[\"'](\./)?pictures[\"'\\/]", coins_code, re.I), "coins: Build exe takes the pictures folder along (the code names it in a path)", None)

    # ---- the create logic and the gallery, in Node
    app = os.path.join(REPO, "tuffcode")
    try:
        for js in ("starters.js", os.path.join("renderer", "js", "new-project.js"), os.path.join("test", "e2e", "suites", "newproject.mjs")):
            p = subprocess.run(["node", "--check", os.path.join(app, js)], capture_output=True, text=True, encoding="utf-8", timeout=60)
            c.check(p.returncode == 0, f"node --check {js}", p.stderr[-400:])
        p = subprocess.run(["node", os.path.join(HERE, "new_project_harness.js"), os.path.join(root, "harness")], capture_output=True, text=True,
                           encoding="utf-8", timeout=180)
        results = json.loads(p.stdout)
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped the New Project harness")
        results = []
    except ValueError:
        c.check(False, "the New Project harness ran", (p.stdout + p.stderr)[-800:])
        results = []
    for ok, what, got in results:
        c.check(ok, f"New Project: {what}", got)

    # ---- how the IDE and the built app find them
    def text_of(*parts):
        with open(os.path.join(app, *parts), encoding="utf-8") as f:
            return f.read()
    build = json.loads(text_of("package.json"))["build"]
    c.check({"from": "starters", "to": "starters"} in build["extraResources"] and "starters.js" in build["files"],
            "the built app has resources/starters (extraResources) and starters.js", build["extraResources"][-2:])
    main = text_of("main.js")
    c.check("require('./starters')" in main and "path.join(process.resourcesPath, 'starters')" in main
            and all(f"'starters:{n}'" in main for n in ("list", "check", "create", "pickFolder")),
            "main.js finds the starters (resources/starters when built) and answers the gallery's calls", None)
    c.check(re.search(r"const SAMPLE_MAIN = `[^`]*# Want a head start\? File > New Project\.\.\. has starter projects", main),
            "a first run's HelloTuff points to File > New Project... (its main.tuf is what opens first)", None)
    c.check("starters: { list: invoke('starters:list')" in text_of("preload.js"), "preload.js gives the page the starters calls", None)
    html = text_of("renderer", "index.html")
    c.check('<script src="js/new-project.js"></script>' in html and 'id="es-new-project"' in html,
            "index.html loads new-project.js, and the empty editor has a New Project… button", None)
    ide = text_of("renderer", "js", "ide.js")
    c.check("newProject: { label: 'New Project…'" in ide and "['File', ['newProject'," in ide and "{ label: 'New Project…', run: commands.newProject.run }" in ide
            and "window.TuffNewProject?.isOpen()" in ide and "openFolder: (dir) => openFolder(dir)" in ide,
            "ide.js: New Project… is a command (so Search Everywhere finds it), first in the File menu and the project menu, and "
            "the IDE's shortcuts wait while it's open", None)
    c.check("if (process.platform !== 'darwin') { Menu.setApplicationMenu(null); return; }" in main,
            "main.js sets no menu on Windows and Linux: the keys of Electron's default one (Ctrl+W closes the window, Ctrl+R reloads it) "
            "would work in the gallery, where the IDE's own shortcuts wait", None)
    # After New Project or Open Folder the file run last is the old project's: with no .tuf tab open, Run (and Debug),
    # Rerun, Design Studio and Build go to the new folder's main.tuf instead (ide.js's own functions, from its source).
    try:
        p = subprocess.run(["node", "-e", STALE_RUN, os.path.join(app, "renderer", "js", "ide.js")], capture_output=True, text=True, encoding="utf-8", timeout=60)
        got = json.loads(p.stdout.strip().splitlines()[-1])
    except FileNotFoundError:
        got = None
    except (ValueError, IndexError) as exc:
        got = {"crash": str(exc), "stderr": p.stderr[-500:]}
    if got is not None:
        old, other = "C:\\Old\\main.tuf", "C:\\Other\\main.tuf"
        c.check(got == [{"run": old, "rerun": ["start", old], "build": old, "studio": old}, {"run": None, "rerun": ["current"], "build": other, "studio": other}],
                "ide.js: after another folder opens, Run, Rerun, Design Studio and Build leave the old project's file run last alone", got)


# ---------------------------------------------------------------- Learn's Section 1.7, the Workshop (1.5.0)

# What the Workshop lessons' console examples and solutions say (through a pipe: no sound, no one to press keys).
LEARN_150_SAYS = {
    ("workshop-templates", "example"): "Sam has 10 points\nTwo of them: $12.75\n0.33 and 007\n[Sam   ] [   9]",
    ("workshop-templates", "solution"): "popcorn  $1.20\napple    $0.45\njuice    $1.85\nTotal:   $3.50",
    ("workshop-kinds", "example"): 'Rex\'s hunger: 6\nAnn\'s hunger: 2\nPet(name: "Rex", hunger: 6)',
    ("workshop-kinds", "solution"): "Holes and Wonder: 582 pages",
    ("workshop-actions", "example"): "Rex played\nRex's hunger: 4",
    ("workshop-actions", "solution"): "Sam has 3 hp left",
    ("workshop-files", "example"): "Price: $6.38\nWith tax: $7.65\nThe tax rate is 0.2",
    ("workshop-files", "solution"): "3 tickets: $16.20",
    ("workshop-music", "example"): "That song is 8 seconds long",
    ("workshop-music", "solution"): "",
}
_SNACKS = 'snacks = {"popcorn": 1.2, "apple": 0.45, "juice": 1.85}\n'
_BOOK = 'kind Book:\n    title = ""\n    pages = 0\n\n'
_BOOKS = _BOOK + 'holes = Book("Holes", 272)\nwonder = Book("Wonder", 310)\n'
_HERO = 'kind Hero:\n    name = "?"\n    hp = 10\n'
_SCREEN = 'mention tterm\nscreen = tterm.screen(20, 10)\nx = 10\ny = 5\n\nfunc step(dt):\n'
_SHEET = 'mention tgame\ngame = tgame.window("Walker", 600, 300)\nhero = game:image("walker.png", 300, 200, 96)\n'
_WALK = _SHEET + 'hero:frames(4)\nhero:animation("walk", [1, 2, 3, 4], 8)\n'


def _boxed(arrows):
    """The terminal game with these lines for the up and down arrows, in its box (walls at y = 0 and y = 9)."""
    return _SCREEN + arrows + '    screen:clear()\n    screen:box(0, 0, 20, 10, "gray")\n    screen:put(x, y, "@", "lime")\n\nscreen:every_frame(step)\n'


def _walks(lines):
    """The sprite sheet game with these lines in its loop, after dt = game:frame()."""
    return _WALK + 'while game:open():\n    dt = game:frame()\n' + lines


# The terminal game with up and down the wrong way round (y goes down the screen), and with its stops on the walls.
_TTERM_SWAPPED = _boxed('    if screen:pressed("up") and y < 8:\n        y += 1\n    if screen:pressed("down") and y > 1:\n        y -= 1\n')
_TTERM_WALLS = _boxed('    if screen:pressed("up") and y > 0:\n        y -= 1\n    if screen:pressed("down") and y < 9:\n        y += 1\n')
_TTERM_NAMES = _boxed('    if screen:pressed("Up") and y > 1:\n        y -= 1\n    if screen:pressed("arrow down") and y < 8:\n        y += 1\n')
# The sprite sheet game with frame 1 only before the loop (the walk never stops), and on every frame (it never starts).
_SHEETS_BEFORE = _WALK + 'hero:frame(1)\nwhile game:open():\n    dt = game:frame()\n    if game:held("right"):\n        hero:play("walk")\n'
_SHEETS_ALWAYS = _WALK + 'while game:open():\n    dt = game:frame()\n    if game:held("right"):\n        hero:play("walk")\n    hero:frame(1)\n'
# ...and with each arrow's own if playing the walk, then frame 1 under an else: under the right arrow's if alone, that
# else runs while left is held too, so going left it never walks. After an if and an elif, it runs only when neither is.
_HELD_LEFT = '    if game:held("left"):\n        hero:move(-150 * dt, 0)\n        hero:play("walk")\n'
_HELD_RIGHT = _HELD_LEFT.replace("left", "right").replace("-150", "150")
_ELSE_STILL = '    else:\n        hero:frame(1)\n'
_SHEETS_ELSE = _walks(_HELD_LEFT + _HELD_RIGHT + _ELSE_STILL)
_SHEETS_ELIF = _walks(_HELD_LEFT + _HELD_RIGHT.replace("if", "elif", 1) + _ELSE_STILL)
# ...and frame 1 under an if of its own that checks only that right isn't held: true while left is held too.
_SHEETS_IF_NOT = _walks(_HELD_LEFT + _HELD_RIGHT + '    if not game:held("right"):\n        hero:frame(1)\n')
# The mistakes a learner is likely to make in each lesson's task: programs that run (so Learn checks them, instead of
# pointing at an error), and how the hint its check gives starts.
LEARN_150_MISTAKES = [
    ("workshop-templates", _SNACKS + 'for snack in snacks:\n    say "{snack:8} {snacks[snack]:money}"\n', "Put an f right before the quotes"),
    ("workshop-templates", _SNACKS + 'for snack in snacks:\n    say snack + " " + text(snacks[snack], 2)\n', "Make each line with a template"),
    ("workshop-templates", _SNACKS + 'for snack in snacks:\n    say f"{snack:8} {snacks[snack]}"\n', "Show the prices as money"),
    ("workshop-templates", _SNACKS + 'for snack in snacks:\n    say f"{snack:8} {snacks[snack]:money}"\n', "Then add the prices up"),
    ("workshop-templates", _SNACKS + 'total = 0\nfor snack in snacks:\n    total += snacks[snack]\n    say f"{snack:8} {snacks[snack]:money}"\n'
                                     'say "Total: " + total\n', "Say the total as money too"),
    ("workshop-templates", _SNACKS + 'total = 0\nfor snack in snacks:\n    total += snacks[snack]\n    say f"{snack:8} {snacks[snack]:money}"\n'
                                     'say "Total: $" + total\n', "Say the total as money too"),  # Total: $3.5
    ("workshop-templates", 'snacks = {"popcorn": 1.2, "apple": 0.45, "juice": 1.85, "nuts": 2}\nfor snack in snacks:\n'
                           '    say f"{snack:8} {snacks[snack]:money}"\n', "Then add the prices up"),  # four lines of money, but no total
    ("workshop-templates", _SNACKS + 'total = 0\nfor snack in snacks:\n    total += snacks[snack]\n    say f"{snack:8} {snacks[snack]:money}"\n'
                                     'say f"Total: ${total:0.0}"\n', "Say the total as money too"),  # Total: $3.5
    ("workshop-templates", _SNACKS + 'for snack in snacks:\n    say f"{snack:8} ${snacks[snack]:0.00}"\n', "Then add the prices up"),  # $ and {x:0.00}: money
    ("workshop-kinds", 'holes = {"title": "Holes", "pages": 272}\nsay holes["pages"]\n', "Start your own kind"),
    ("workshop-kinds", 'kind Book:\n    title = ""\n\nholes = Book("Holes")\nwonder = Book("Wonder")\nsay holes.title + wonder.title\n', "Give Book two fields"),
    ("workshop-kinds", _BOOK + 'holes = Book("Holes", 272)\nsay holes.pages\n', "Make two of them"),
    ("workshop-kinds", _BOOK + 'holes = Book("Holes", 272)\nwonder = Book("Wonder", 310)\nsay holes\nsay wonder\n', "Read a field with a dot"),
    ("workshop-kinds", _BOOK + 'holes = Book("Holes", 272)\nwonder = Book("Wonder", 310)\nsay f"{holes.title} has {holes.pages} pages"\n'
                               'say f"{wonder.title} has {wonder.pages} pages"\n', "Add the two books' pages together"),
    ("workshop-kinds", _BOOKS + 'say holes.title + ": " + holes.pages + " pages"\nsay wonder.title + ": " + wonder.pages + " pages"\n',
     "Add the two books' pages together"),  # + only joins text here
    ("workshop-kinds", _BOOKS + 'say holes.title + " and " + wonder.title\n', "Add the two books' pages together"),
    ("workshop-kinds", _BOOKS + 'say "They have " + holes.pages + wonder.pages + " pages"\n', "After words, + joins each number on"),  # 272310
    ("workshop-actions", _HERO + '\nfunc hurt(damage):\n    sam.hp -= damage\n\nsam = Hero("Sam")\nhurt(3)\nhurt(4)\nsay sam.hp\n', "Move the func into the kind"),
    ("workshop-actions", _HERO + '    func hurt(damage):\n        sam.hp -= damage\n\nsam = Hero("Sam")\nsam:hurt(3)\nsam:hurt(4)\nsay sam.hp\n',
     "In the action, take the damage off the hero's own hp"),
    ("workshop-actions", _HERO + '    func hurt(damage):\n        my.hp -= damage\n\nsam = Hero("Sam")\nsay sam.hp\n', "Run the action on your hero"),
    ("workshop-actions", _HERO + '    func hurt(damage):\n        my.hp -= damage\n\nsam = Hero("Sam")\nsam:hurt(3)\nsay sam.hp\n', "Hurt your hero twice"),
    ("workshop-files", 'say f"{3 * 4.5 * 1.2:money}"\n', "Load the file first"),
    ("workshop-files", 'import money.tuf\nsay money.as_money(3 * 4.5)\n', "Add the tax with money.with_tax"),
    ("workshop-files", 'import money.tuf\nsay money.with_tax(3 * 4.5)\n', "Show it as money"),
    ("workshop-files", 'import money.tuf\nsay money.as_money(3 * 4.5 * money.rate)\n', "Add the tax with money.with_tax"),  # only the tax, $2.70
    ("workshop-files", 'import money.tuf\nsay money.as_money(3 * 4.5 + money.rate)\n', "Add the tax with money.with_tax"),  # $13.70
    ("workshop-files", 'import money.tuf\nsay 3 * 4.5 * (1 + money.rate)\n', "Show it as money"),  # 16.2: the tax is on, but not as money
    ("workshop-music", 'mention tmusic\nsong = tmusic.song(120)\nsong:track("piano", "C4 E4 G4")\nsong:track("bass", "C3*3")\nsong:play()\n', "Play a tune first"),
    ("workshop-music", 'mention tmusic\ntmusic.play("C4 E4 G4", "piano")\ntmusic.play("C3*3", "bass")\n', "Make a song"),
    ("workshop-music", 'mention tmusic\ntmusic.play("C4 E4", "piano")\nsong = tmusic.song(120)\nsong:track("piano", "C4 E4 G4")\nsong:play()\n', "Give it two tracks"),
    ("workshop-music", 'mention tmusic\ntmusic.play("C4 E4", "piano")\nsong = tmusic.song(120)\nsong:track("piano", "C4 E4 G4")\n'
                       'song:track("bass", "C3*3")\n', "Play the song after its tracks"),
    ("workshop-tterm", _SCREEN + '    if screen:pressed("up"):\n        y -= 1\n    screen:clear()\n    screen:put(x, y, "@")\n\nscreen:every_frame(step)\n',
     "Now the down arrow"),
    ("workshop-tterm", _SCREEN + '    if screen:pressed("up"):\n        x -= 1\n    if screen:pressed("down"):\n        x += 1\n    screen:clear()\n'
                                 '    screen:put(x, y, "@")\n\nscreen:every_frame(step)\n', "Up goes towards the top"),
    ("workshop-tterm", _SCREEN + '    if screen:pressed("up"):\n        y -= 1\n    if screen:pressed("down"):\n        y += 1\n    screen:clear()\n'
                                 '    screen:put(x, y, "@")\n\nscreen:every_frame(step)\n', "Keep the @ inside the box"),
    ("workshop-tterm", _TTERM_SWAPPED, "Up goes towards the top"),
    ("workshop-tterm", _TTERM_WALLS, "The box's top wall is at y = 0, so stop the @ at 1"),
    ("workshop-tterm", _TTERM_WALLS.replace("y > 0", "y > 1"), "The box's bottom wall is at y = 9, so stop the @ at 8"),
    ("workshop-sheets", _SHEET + 'while game:open():\n    game:frame()\nhero:frames(4)\n', "Cut it into frames before the game starts"),
    ("workshop-sheets", _SHEET + 'hero:frames(4)\nwhile game:open():\n    game:frame()\n', "Name the walk and its frames"),
    ("workshop-sheets", _SHEET + 'hero:frames(4)\nhero:animation("walk", [1, 2, 3, 4], 8)\nhero:play("walk")\nwhile game:open():\n    game:frame()\n',
     "Play the walk in the loop"),
    ("workshop-sheets", _SHEET + 'hero:frames(4)\nhero:animation("walk", [1, 2, 3, 4], 8)\nwhile game:open():\n    dt = game:frame()\n'
                                 '    if game:held("right"):\n        hero:play("walk")\n', "When no arrow is held"),
    ("workshop-sheets", _SHEETS_BEFORE, "When no arrow is held"),
    ("workshop-sheets", _SHEETS_ALWAYS, "Put hero:frame(1) under else:"),
    ("workshop-sheets", _SHEETS_ELSE, "The else runs while left is held too"),
    ("workshop-sheets", _walks(_HELD_RIGHT + _HELD_LEFT + _ELSE_STILL), "The else runs while right is held too"),
    ("workshop-sheets", _SHEETS_IF_NOT, "When left is held, if not game:held(\"right\") is true too"),
    ("workshop-sheets", _walks(_HELD_LEFT + _HELD_RIGHT + '    if not game:held("left"): hero:frame(1)\n'), "When right is held, if not game:held(\"left\")"),
]
# Other right ways to do the tasks, which the checks must accept: each runs, and its check says it's done.
LEARN_150_GOOD = [
    ("workshop-templates", _SNACKS + 'say f"popcorn  {snacks["popcorn"]:money}"\nsay f"apple    {snacks["apple"]:money}"\n'
                           'say f"juice    {snacks["juice"]:money}"\nsay f"Total:   {snacks["popcorn"] + snacks["apple"] + snacks["juice"]:money}"\n'),
    ("workshop-templates", _SNACKS + "total = 0\nfor snack in snacks:\n    total += snacks[snack]\n    say f'{snack:8} {snacks[snack]:money}'\n"
                           "say f'Total:   {total:money}'\n"),
    ("workshop-templates", _SNACKS + 'total = 0\nfor snack in snacks:\n    total += snacks[snack]\n    say f"{snack:8} {snacks[snack]:money}"\n'
                           'say f"Total:   ${total:0.00}"\n'),  # the lesson's {x:0.00}, after a $
    ("workshop-kinds", _BOOKS + 'total = holes.pages\ntotal = total + wonder.pages\nsay total\n'),
    ("workshop-kinds", _BOOKS + 'total = 0\nfor book in [holes, wonder]:\n    total += book.pages\nsay "Pages: " + total\n'),
    ("workshop-kinds", _BOOKS + 'say "They have " + (holes.pages + wonder.pages) + " pages"\n'),
    ("workshop-actions", _HERO + '    func hurt(damage):\n        my.hp -= damage\n\nsam = Hero("Sam")\nfor i in range(1, 2):\n    sam:hurt(3)\n'
                         'say f"{sam.name} has {sam.hp} hp left"\n'),
    ("workshop-actions", _HERO + '    func heal(amount):\n        my.hp += amount\n    func hurt(damage):\n        my.hp -= damage\n\nsam = Hero("Sam")\n'
                         'sam:hurt(3)\nsam:hurt(4)\nsay f"{sam.name} has {sam.hp} hp left"\n'),
    ("workshop-files", 'import money.tuf\n\nsay f"3 tickets: {money.with_tax(3 * 4.5):money}"\n'),  # Lesson 1's :money
    ("workshop-files", 'import money.tuf\n\nsay money.as_money(3 * 4.5 * (1 + money.rate))\n'),  # the tax from money.rate
    ("workshop-files", 'import money.tuf\n\nprice = 3 * 4.5\ntax = price * money.rate\nsay "3 tickets: " + money.as_money(price + tax)\n'),
    ("workshop-files", 'import money.tuf\n\nsay f"3 tickets: ${money.with_tax(3 * 4.5):0.00}"\n'),  # Lesson 1's $ and {x:0.00}
    ("workshop-tterm", _TTERM_NAMES),
    ("workshop-tterm", _boxed('    if screen:pressed("up") and y >= 2: y -= 1\n    if screen:pressed("down") and y <= 7: y = y + 1\n')),
    ("workshop-tterm", _boxed('    if screen:pressed("up"):\n        y -= 1\n    elif screen:pressed("down"):\n        y += 1\n'
                              '    if y < 1:\n        y = 1\n    if y > 8:\n        y = 8\n')),
    ("workshop-sheets", _SHEET + 'hero:frames 4\nhero:animation("walk", [1, 2, 3, 4], 8)\nwhile game:open():\n    dt = game:frame()\n'
                                 '    if game:held("right"):\n        hero:move(150 * dt, 0)\n        hero:play "walk"\n    else:\n        hero:frame 1\n'),
    ("workshop-sheets", _WALK + 'while game:open():\n    dt = game:frame()\n    if game:held("left") or game:held("right"): hero:play("walk")\n'
                                '    else: hero:frame(1)\n'),
    ("workshop-sheets", _SHEETS_ELIF),
    ("workshop-sheets", _walks(_HELD_LEFT + '    else:\n        if game:held("right"):\n            hero:move(150 * dt, 0)\n'
                               '            hero:play("walk")\n        else:\n            hero:frame(1)\n')),  # an else inside an else
    ("workshop-sheets", _walks(_HELD_LEFT + _HELD_RIGHT + '    if not game:held("left") and not game:held("right"):\n        hero:frame(1)\n')),
    ("workshop-sheets", _walks(_HELD_LEFT + _HELD_RIGHT + '    if not game:held("left"):\n        if not game:held("right"):\n            hero:frame(1)\n')),
    ("workshop-sheets", _walks(_HELD_LEFT + '    elif not game:held("right"):\n        hero:frame(1)\n'
                               '    else:\n        hero:move(150 * dt, 0)\n        hero:play("walk")\n')),  # (after the if for left)
]
# Slips in these lessons that stop the run, so Learn only shows what the run says: (the program, with money.tuf next to
# it, and what both runtimes and --check say).
LEARN_150_SLIPS = [
    (_HERO + '    func hurt(damage):\n        self.hp -= damage\n\nsam = Hero("Sam")\nsam:hurt(3)\n',
     "I don't know what 'self' is. Tuff has no classes: make a kind (kind Pet:), and in its actions the object itself is my, like my.hunger."),
    ('import money.tuf\n\nsay as_money(with_tax(3 * 4.5))\n', "I don't know what 'as_money' is. It's in money.tuf, so write money.as_money"),
    ('import money.tuf\n\nsay money.as_money(3 * 4.5 * (1 + rate))\n', "I don't know what 'rate' is. It's in money.tuf, so write money.rate"),
]


def learn_150_write(folder, files):
    """Writes a lesson's own files (text, or {"base64": ...} for a picture) into folder."""
    os.makedirs(folder, exist_ok=True)
    for name, data in (files or {}).items():
        if isinstance(data, dict):
            with open(os.path.join(folder, name), "wb") as f:
                f.write(base64.b64decode(data["base64"]))
        else:
            with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
                f.write(data)


def learn_150_game(folder, name, code, frames, events=None, slow=False):
    """A tgame lesson's program, run by headless.py in folder (no window): (exit code, say lines, stderr, the
    commands it sent the page)."""
    path = os.path.join(folder, name + ".tuf")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    out = os.path.join(folder, name + ".json")
    args = [sys.executable, os.path.join(HERE, "headless.py"), path, out, str(frames)]
    if events:
        with open(os.path.join(folder, name + ".events.json"), "w", encoding="utf-8") as f:
            json.dump(events, f)
        args.append(os.path.join(folder, name + ".events.json"))
    env = {k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_SLOW", "TUFF_TGAME_AUTOPILOT")}
    env.update(PYTHONIOENCODING="utf-8", TUFF_NO_SOUND="1", **({"TUFF_SLOW": "1"} if slow else {}))
    p = subprocess.run(args, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env,
                       stdin=subprocess.DEVNULL)
    return p.returncode, [x for x in p.stdout.splitlines() if x.strip()], p.stderr, read_json(out) or []


def learn_150_plays(cmds):
    """[(frame, what :play sent, the frame shown)] for the first picture a game made."""
    pic = next((cmd[1] for cmd in cmds if cmd[0] == "c" and cmd[3] == "image"), None)
    return [(f, s.get("play", "-"), s.get("cell")) for f, s in frame_sets(cmds, pic)]


def learn_150_png(data):
    """An 8-bit PNG read the way the game window has to read it, every chunk's CRC checked and every row unfiltered:
    (width, height, rows of pixels, how see-through a pixel is from 0 to 255), or None if it doesn't read. (tgame
    itself only reads the header, so a run doesn't notice a broken picture: the window just shows nothing.)"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, head, trns = 8, b"", None, b""
    while pos + 12 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if data[pos + 8 + n:pos + 12 + n] != struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF):
            return None
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"tRNS":
            trns = body
        pos += 12 + n
    if not head or head[2] != 8 or head[3] not in (0, 2, 3, 4, 6) or head[6] != 0:
        return None
    w, h, ctype = head[0], head[1], head[3]
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return None
    if len(raw) != h * (w * bpp + 1):
        return None
    rows, prev = [], bytearray(w * bpp)
    for y in range(h):
        start = y * (w * bpp + 1)
        how, line = raw[start], bytearray(raw[start + 1:start + 1 + w * bpp])
        for x in range(len(line)):
            a, b = line[x - bpp] if x >= bpp else 0, prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if how > 4:
                return None
            if how == 4:
                p = a + b - c
                near = a if abs(p - a) <= abs(p - b) and abs(p - a) <= abs(p - c) else b if abs(p - b) <= abs(p - c) else c
            else:
                near = (0, a, b, (a + b) // 2)[how]
            line[x] = (line[x] + near) & 255
        rows.append([tuple(line[i:i + bpp]) for i in range(0, len(line), bpp)])
        prev = line

    def alpha(px):
        if ctype == 3:
            return trns[px[0]] if px[0] < len(trns) else 255
        return px[-1] if ctype in (4, 6) else 255
    return w, h, rows, alpha


def t_learn_150(c):
    """1.5.0, headless: Learn's Section 1.7, the Workshop (text templates, kinds, actions, your own files, tmusic, tterm
    and sprite sheets). learn.js, in Node (learn_test.mjs), lists it after Toolbox. Every lesson's example, starter and
    solution passes --check and runs the same in both runtimes, saying what it should (the game with headless.py, so no
    window, and music through a pipe, so no sound); each check accepts its solution and the other right ways above, run
    for real, and gives its hint for the starter, for empty code and for the mistakes above (played, the terminal game's
    and the sprite sheet's really go wrong); the slips that stop a run get the same help from both runtimes and --check;
    Start lesson writes a lesson's own files (money.tuf and the sprite sheet walker.png) next to its file, where the
    solutions run; and a run that was stopped isn't judged, though a real error still is."""
    import shutil
    import tuff_tgame
    folder = os.path.join(HERE, "out", "learn_150")  # never in the temp folder: there --check can't see money.tuf
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    learn = os.path.join(REPO, "tuffcode", "renderer", "js", "learn.js")
    quiet = {"TUFF_NO_SOUND": "1", "TUFF_MUSIC_DIR": os.path.join(folder, "music")}

    def node(plan):
        path = os.path.join(folder, "plan.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan, f)
        p = subprocess.run(["node", os.path.join(HERE, "learn_test.mjs"), learn, path], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        try:
            return json.loads(p.stdout)
        except ValueError:
            return {"error": (p.stdout + p.stderr)[-800:]}

    try:
        got = node({})
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped Learn's Workshop lessons")
        return
    titles = [s["title"] for s in got.get("sections", [])]
    c.check(titles[2:4] == ["Section 1.6 · Toolbox", "Section 1.7 · Workshop"], "learn.js lists Section 1.7 · Workshop right after Toolbox",
            got.get("error") or titles)
    work = next((s for s in got.get("sections", []) if s["id"] == "workshop"), None)
    if work is None:
        return
    lessons = work["lessons"]
    ids = [l["id"] for l in lessons]
    c.check(work["optional"] and ids == ["workshop-templates", "workshop-kinds", "workshop-actions", "workshop-files", "workshop-music",
                                         "workshop-tterm", "workshop-sheets"],
            "...an optional section of 7 lessons: templates, kinds, actions, your own files, music, a terminal game, sprite sheets", ids)
    c.check([l["file"] for l in lessons] == [f"workshop-{i:02}-{l['id'][len('workshop-'):]}.tuf" for i, l in enumerate(lessons, 1)],
            "...whose files are lessons/workshop-01-templates.tuf and so on", [l["file"] for l in lessons])
    heads = [(l["starter"].splitlines() or [""])[0] for l in lessons]
    c.check(heads == [f"# Section 1.7, Lesson {i}: {l['title']}" for i, l in enumerate(lessons, 1)],
            "each starter begins '# Section 1.7, Lesson N: <its title>'", heads)
    c.check(all(l["task"] and l["body"].count("<p>") >= 2 and l["example"] and l["solution"] for l in lessons),
            "each has a body, an example, a task, a starter and a solution")
    words = " ".join(" ".join(str(l[k]) for k in ("title", "body", "task", "example", "starter", "solution")) for l in lessons)
    c.check(not re.search(r"python|pyinstaller|\bpip\b", words, re.I), "...and none of them mentions Python, pip or PyInstaller")
    body = {l["id"]: l["body"] for l in lessons}
    c.check(all("Start lesson puts" in body[i] for i in ("workshop-files", "workshop-sheets")) and "Learn has put" not in words,
            "the two lessons with files of their own say Start lesson puts them in the lessons folder (they aren't there before)")
    c.check("Section 4" in body["workshop-sheets"] and "install from Plugins" in body["workshop-sheets"] and "<code>|</code> is a bar line" in body["workshop-music"],
            "the sprite sheet lesson says what its game is (Section 4 has more) and that Sprite Studio is a plugin; the music one says what | is")
    own = {l["id"]: l["files"] or {} for l in lessons}
    c.check({i: sorted(f) for i, f in own.items() if f} == {"workshop-files": ["money.tuf"], "workshop-sheets": ["walker.png"]},
            "two lessons have files of their own: money.tuf for your own files, walker.png for sprite sheets", {i: sorted(f) for i, f in own.items()})
    learn_150_write(folder, own["workshop-sheets"])
    pic = learn_150_png(base64.b64decode(own["workshop-sheets"]["walker.png"]["base64"]))
    c.check(pic is not None and pic[:2] == (384, 96) and tuff_tgame.image_size(os.path.join(folder, "walker.png")) == (384, 96),
            "walker.png reads whole, as the game window reads it (every CRC and row): 384 x 96, 4 frames of 96 x 96", pic and pic[:2])
    if pic:
        rows, alpha = pic[2], pic[3]
        frames = [[tuple(row[i * 96:(i + 1) * 96]) for row in rows] for i in range(4)]
        shown = [sum(alpha(px) > 0 for row in f for px in row) for f in frames]
        c.check(all(alpha(f[0][0]) == 0 and alpha(f[95][95]) == 0 for f in frames) and all(2000 < n < 6000 for n in shown)
                and len(set(map(tuple, frames))) == 4, "...each frame see-through around a walker of its own (4 different frames)", shown)

    # Each lesson's code, next to its own files: --check, and a run in both runtimes.
    outputs = {}  # (lesson, part) -> what it said, for its check
    for l in lessons:
        where = os.path.join(folder, l["id"])
        learn_150_write(where, own[l["id"]])
        game = "mention tgame" in l["example"]
        for part in ("example", "starter", "solution"):
            path = os.path.join(where, part + ".tuf")
            with open(path, "w", encoding="utf-8") as f:
                f.write(l[part])
            p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=where,
                               stdin=subprocess.DEVNULL)
            c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"{l['id']} {part} passes --check", (p.stdout + p.stderr)[:300])
            if game:
                run = learn_150_game(where, "run_" + part, l[part], 10)
                outputs[(l["id"], part)] = "\n".join(run[1])
                c.check(run[0] == 0 and not run[2].strip(), "...and runs headless, with no window", run[2][-300:])
                continue
            slow, fast = [interp_run(os.path.join(where, mode + "_" + part), l[part], mode == "slow", env=quiet, files=own[l["id"]])
                          for mode in ("slow", "fast")]
            outputs[(l["id"], part)] = fast[1]
            want = LEARN_150_SAYS.get((l["id"], part))
            c.check(fast[0] == 0 and not fast[2].strip() and slow == fast and (want is None or fast[1].strip() == want),
                    f"...and runs the same in both runtimes{', saying ' + repr(want[:40]) if want else ''}", (slow, fast))

    # The terminal game: the up and down arrows move the @, and the box's walls stop it (screen:press gives a frame a key).
    tterm = next(l for l in lessons if l["id"] == "workshop-tterm")
    c.check(outputs.get(("workshop-tterm", "example"), "").rstrip().endswith("You stopped at 3."), "the tterm example ends 'You stopped at 3.'",
            outputs.get(("workshop-tterm", "example"), "")[-200:])
    # The same for a game that writes the keys as "Up" and "arrow down" (its check accepts it, below), and for two
    # mistakes its check finds: up and down swapped, and stops that let the @ onto the walls.
    games = [("the tterm solution", tterm["solution"], 1, 8, "against the box"), ('"Up" and "arrow down"', _TTERM_NAMES, 1, 8, "too"),
             ("up and down swapped", _TTERM_SWAPPED, 8, 1, "the wrong way"), ("stops at y > 0 and y < 9", _TTERM_WALLS, 0, 9, "onto the walls")]
    for i, (name, game_code, up_row, down_row, how) in enumerate(games):
        for key, want in (("up", up_row), ("down", down_row)):
            keys = "".join(f'screen:press("{key}", {n})\n' for n in range(2, 30, 2))
            code = game_code.replace("screen:every_frame(step)", keys + "screen:every_frame(step)")
            runs = [interp_run(os.path.join(folder, f"tterm{i}_{key}_{mode}"), code, mode == "slow") for mode in ("slow", "fast")]
            rows = [r for r, line in enumerate(runs[1][1].splitlines()) if "@" in line]
            c.check(runs[0] == runs[1] and runs[1][0] == 0 and rows == [want],
                    f"{name}: pressing {key} 14 times takes the @ to row {want}, {how}", (rows, runs[1][1][-400:]))

    # The sprite sheet game, headless: the example walks by itself; the solution walks while an arrow is held.
    sheets = next(l for l in lessons if l["id"] == "workshop-sheets")
    where = os.path.join(folder, "workshop-sheets")
    code, out, err, d, secs = scene(os.path.join(where, "example.tuf"))
    hero = next((t for t in d.get("things", []) if t.get("var") == "hero"), {})
    c.check(d.get("error") is None and hero.get("frames") == {"cells": [4, 1], "frame": 1, "playing": "walk", "loop": True,
                                                                 "animations": {"walk": {"frames": [1, 2, 3, 4], "fps": 8}}},
            "Tuff Engine's preview of the sprite sheet example: 4 frames, walk playing", (d.get("error"), hero.get("frames")))
    walk = [[1, 2, 3, 4], 8, True]
    runs = [learn_150_game(where, "example_" + mode, sheets["example"], 30, slow=mode == "slow") for mode in ("slow", "fast")]
    c.check(runs[1][0] == 0 and not runs[1][2].strip() and learn_150_plays(runs[1][3]) == [(0, walk, 1)]
            and learn_150_plays(runs[0][3]) == learn_150_plays(runs[1][3]),
            "the example runs headless in both runtimes, walking from the start", (learn_150_plays(runs[1][3]), runs[1][2][-300:]))
    keys = {"10": [{"type": "keydown", "code": "ArrowRight"}], "40": [{"type": "keyup", "code": "ArrowRight"}],
            "50": [{"type": "keydown", "code": "ArrowLeft"}], "60": [{"type": "keyup", "code": "ArrowLeft"}]}
    runs = [learn_150_game(where, "solution_" + mode, sheets["solution"], 80, keys, slow=mode == "slow") for mode in ("slow", "fast")]
    plays = [learn_150_plays(r[3]) for r in runs]
    c.check(runs[1][0] == 0 and not runs[1][2].strip() and plays[0] == plays[1]
            and plays[1] == [(0, None, 1), (10, walk, None), (40, None, 1), (50, walk, None), (60, None, 1)],
            "the solution, headless in both runtimes: frame 1 standing, the walk while right or left is held, frame 1 again after",
            (plays, runs[1][2][-300:]))
    # Two mistakes its check finds, with right held from frame 10 to 40.
    learn_150_write(os.path.join(folder, "sheets_mistakes"), own["workshop-sheets"])
    held = {"10": [{"type": "keydown", "code": "ArrowRight"}], "40": [{"type": "keyup", "code": "ArrowRight"}]}
    run = learn_150_game(os.path.join(folder, "sheets_mistakes"), "before", _SHEETS_BEFORE, 60, held)
    c.check(run[0] == 0 and learn_150_plays(run[3]) == [(0, None, 1), (10, walk, None)],
            "hero:frame(1) only before the loop: the walk starts, and never stops after right is let go", learn_150_plays(run[3]))
    run = learn_150_game(os.path.join(folder, "sheets_mistakes"), "always", _SHEETS_ALWAYS, 60, held)
    plays = learn_150_plays(run[3])
    c.check(run[0] == 0 and len(plays) > 1 and plays[1][0] == 10 and all(p[1:] == (None, 1) for p in plays),
            "hero:frame(1) on every frame: while right is held it's frame 1 every time, so it never walks", plays[:4])
    # With the solution's keys: an else under the right arrow's if alone walks going right, but going left it's frame 1
    # every time. As an elif, it walks both ways, as the solution does.
    run = learn_150_game(os.path.join(folder, "sheets_mistakes"), "else", _SHEETS_ELSE, 80, keys)
    plays = learn_150_plays(run[3])
    c.check(run[0] == 0 and plays == [(0, None, 1), (10, walk, None), (40, None, 1)] + [(f, None, 1) for f in range(50, 60)],
            "an else under the right arrow's if alone: it walks going right, but going left it's frame 1 every time", plays)
    run = learn_150_game(os.path.join(folder, "sheets_mistakes"), "elif", _SHEETS_ELIF, 80, keys)
    c.check(run[0] == 0 and learn_150_plays(run[3]) == [(0, None, 1), (10, walk, None), (40, None, 1), (50, walk, None), (60, None, 1)],
            "...and with elif for the right arrow, it walks both ways", learn_150_plays(run[3]))
    run = learn_150_game(os.path.join(folder, "sheets_mistakes"), "if_not", _SHEETS_IF_NOT, 80, keys)
    c.check(run[0] == 0 and learn_150_plays(run[3]) == [(0, None, 1), (10, walk, None), (40, None, 1)] + [(f, None, 1) for f in range(50, 60)],
            "frame 1 under if not game:held(\"right\") of its own: going left it's frame 1 every time too", learn_150_plays(run[3]))

    # Learn's checks (in Node), with what the programs really said: the mistakes above, and the other right ways.
    def ran(where, lesson, code):
        if "mention tgame" in code:
            learn_150_write(where, own[lesson])
            run = learn_150_game(where, "program", code, 5)
            return run[0], "\n".join(run[1]), run[2]
        return interp_run(where, code, False, env=quiet, files=own[lesson])

    mistakes = [ran(os.path.join(folder, "mistake", str(i)), lesson, code) for i, (lesson, code, _h) in enumerate(LEARN_150_MISTAKES)]
    good = [ran(os.path.join(folder, "good", str(i)), lesson, code) for i, (lesson, code) in enumerate(LEARN_150_GOOD)]
    jobs = [{"id": l["id"], "src": l[part], "out": outputs.get((l["id"], part), "")} for l in lessons for part in ("solution", "starter")]
    jobs += [{"id": l["id"], "src": "", "out": ""} for l in lessons]
    jobs += [{"id": lesson, "src": code, "out": run[1]} for (lesson, code, _h), run in zip(LEARN_150_MISTAKES, mistakes)]
    jobs += [{"id": lesson, "src": code, "out": run[1]} for (lesson, code), run in zip(LEARN_150_GOOD, good)]
    verdicts = node({"checks": jobs}).get("verdicts") or [None] * len(jobs)
    n, m = len(lessons), len(LEARN_150_MISTAKES)
    for i, l in enumerate(lessons):
        solution, starter, empty = verdicts[2 * i], verdicts[2 * i + 1], verdicts[2 * n + i]
        c.check(solution is True and isinstance(starter, str) and not starter.startswith("THREW") and isinstance(empty, str)
                and not empty.startswith("THREW"), f"{l['id']}: its check accepts the solution, and gives the starter a hint: {starter}",
                (solution, starter, empty))

    def shown(code):
        """The program on one line, without the lines they all have (like the terminal game's screen:clear())."""
        same = ("mention", "kind", "snacks =", "screen", "x = ", "y = ", "func step")
        return " / ".join(x.strip() for x in code.splitlines() if x.strip() and not x.strip().startswith(same))[-90:]

    for (lesson, code, hint), run, verdict in zip(LEARN_150_MISTAKES, mistakes, verdicts[3 * n:3 * n + m]):
        c.check(run[0] == 0 and isinstance(verdict, str) and verdict.startswith(hint),
                f"{lesson}: '{shown(code)}' runs, and the check says: {hint}", (run[0], run[2][-200:], verdict))
    for (lesson, code), run, verdict in zip(LEARN_150_GOOD, good, verdicts[3 * n + m:]):
        c.check(run[0] == 0 and not run[2].strip() and verdict is True, f"{lesson}: '{shown(code)}' runs, and the check accepts it",
                (run[0], run[2][-200:], verdict))

    # Slips that stop the run, where Learn shows the run's message: both runtimes, and --check, say what to write.
    for i, (code, says) in enumerate(LEARN_150_SLIPS):
        where = os.path.join(folder, "slip", str(i))
        runs = [interp_run(where, code, mode == "slow", env=quiet, files=own["workshop-files"]) for mode in ("slow", "fast")]
        p = subprocess.run(tuff_cmd() + ["--check", os.path.join(where, "program.tuf")], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=where, stdin=subprocess.DEVNULL)
        firsts = [first_error(err) or ("", 1, None, "") for err in (runs[0][2], runs[1][2], p.stderr)]
        c.check(runs[0] == runs[1] and runs[1][0] == 1 and [f[3] for f in firsts] == [says] * 3 and len({f[1] for f in firsts}) == 1,
                f"'{code.splitlines()[(firsts[1][1] or 1) - 1].strip()}' stops the run, and both runtimes and --check say: {says[:60]}...",
                ([f[1:] for f in firsts], runs[1][2][-300:]))

    # Start lesson in a project (its folder has a space in its name): the lesson's file, and its own files next to it.
    project = os.path.join(folder, "My Project")
    os.makedirs(project)
    lessons_dir = os.path.join(project, "lessons")
    got = node({"starts": [{"root": project, "id": "workshop-files"}, {"root": project, "id": "workshop-sheets"},
                           {"root": project, "id": "workshop-templates"}]}).get("starts") or [{}] * 3
    files, sheet, plain = got
    c.check(files.get("calls") == [["createDir", "lessons"], ["writeFile", "lessons/workshop-04-files.tuf"], ["writeFile", "lessons/money.tuf"],
                                   ["refreshTree"], ["openFile", "lessons/workshop-04-files.tuf"]],
            "Start lesson on 'Your own files' makes lessons/, the lesson's file and money.tuf next to it, then opens the lesson", files)
    with open(os.path.join(lessons_dir, "money.tuf"), encoding="utf-8") as f:
        c.check(f.read() == own["workshop-files"]["money.tuf"], "...with the money.tuf the lesson has")
    with open(os.path.join(lessons_dir, "walker.png"), "rb") as f:
        same = f.read() == base64.b64decode(own["workshop-sheets"]["walker.png"]["base64"])
    c.check(sheet.get("calls") == [["writeFile", "lessons/workshop-07-sheets.tuf"], ["plugins.writeFile", "lessons/walker.png", "base64"],
                                   ["refreshTree"], ["openFile", "lessons/workshop-07-sheets.tuf"]] and same,
            "Start lesson on 'Animated pictures' writes walker.png (as base64, inside the project) next to its file", (sheet, same))
    c.check(plain.get("calls") == [["writeFile", "lessons/workshop-01-templates.tuf"], ["refreshTree"], ["openFile", "lessons/workshop-01-templates.tuf"]],
            "...and a lesson without files of its own writes only its file", plain)
    # The solutions, in the lesson files there: they find money.tuf and walker.png.
    files_lesson = next(l for l in lessons if l["id"] == "workshop-files")
    runs = [interp_run(lessons_dir, files_lesson["solution"], mode == "slow", env=quiet, main="workshop-04-files.tuf") for mode in ("slow", "fast")]
    c.check(runs[0] == runs[1] and runs[1][0] == 0 and runs[1][1].strip() == "3 tickets: $16.20",
            "the 'Your own files' solution, in lessons/workshop-04-files.tuf, imports the money.tuf Learn wrote", runs[1])
    run = learn_150_game(lessons_dir, "workshop-07-sheets", sheets["solution"], 20, {"5": [{"type": "keydown", "code": "ArrowRight"}]})
    c.check(run[0] == 0 and learn_150_plays(run[3]) == [(0, None, 1), (5, walk, None)],
            "the 'Animated pictures' solution, in lessons/, walks with the walker.png Learn wrote", (learn_150_plays(run[3]), run[2][-300:]))
    # Starting again keeps what the learner changed, and brings back a file they deleted.
    with open(os.path.join(lessons_dir, "money.tuf"), "a", encoding="utf-8") as f:
        f.write("\nfunc half(price):\n    return price / 2\n")
    again, back = node({"starts": [{"root": project, "id": "workshop-files"},
                                   {"root": project, "id": "workshop-sheets", "remove": ["walker.png"]}]}).get("starts") or [{}] * 2
    with open(os.path.join(lessons_dir, "money.tuf"), encoding="utf-8") as f:
        changed = f.read()
    c.check(again.get("calls") == [["openFile", "lessons/workshop-04-files.tuf"]] and changed.endswith("return price / 2\n"),
            "starting a lesson again changes nothing: the money.tuf the learner added to stays as it is", again)
    c.check(back.get("calls", [])[:1] == [["plugins.writeFile", "lessons/walker.png", "base64"]] and os.path.isfile(os.path.join(lessons_dir, "walker.png")),
            "...and a lesson file it needs that was deleted comes back", back)
    # A run of a lesson's file that was stopped (Stop ends it with -1, the debugger's own stop with 130) isn't judged:
    # the status line keeps what it said, or stays empty. A real error still is one.
    templates = next(l for l in lessons if l["id"] == "workshop-templates")
    hint = verdicts[1]  # the starter's, from above
    error = "Your program hit an error. Click the red message in the Run window to jump to it."
    runs =[(-1, "", ""), (0, templates["starter"], outputs[("workshop-templates", "starter")]), (-1, "", ""), (130, "", ""), (1, "", ""),
            (0, templates["solution"], outputs[("workshop-templates", "solution")]), (-1, "", "")]
    said = (node({"runs": [{"root": project, "id": "workshop-templates", "runs": [{"code": n, "src": s, "out": o} for n, s, o in runs]}]})
            .get("runs") or [None])[0]
    c.check(said == [None, hint, hint, hint, error, "Nice! Lesson complete.", "Nice! Lesson complete."],
            "a lesson's run that was stopped (exit code -1 or 130) leaves what Learn says as it was; a real error (1) still says so", said)
    # The e2e test knows the new section too.
    with open(os.path.join(HERE, "..", "e2e", "suites", "learn-sections.mjs"), encoding="utf-8") as f:
        suite = f.read()
    c.check("'Section 1.7 · Workshop'" in suite and "'workshop'" in suite, "learn-sections.mjs (the e2e test) knows Section 1.7 · Workshop")


# ---------------------------------------------------------------- Build exe, with its packing tool stood in for (1.5.0)

def t_build_pack(c):
    """No window, no packing tool: build_exe_pack_test.mjs runs tuffcode/build.js with PyInstaller stood in for, lays the
    app out as its .exe unpacks it and runs it with the launcher build.js wrote. 1.5.0: a built app run as the real one
    runs (frozen, unpacked afresh each time, started from another folder) keeps what it saves in "<its name> files"
    beside its .exe, or in TuffApps when it can't write there, and reads it back; and a project folder with ; in its
    path packs."""
    sep = ";" if os.name == "nt" else ":"
    try:
        p = subprocess.run(["node", os.path.join(HERE, "build_exe_pack_test.mjs")], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, env={k: v for k, v in os.environ.items() if k not in ("TUFF_IDE", "TUFF_BASE_DIR")})
    except FileNotFoundError:
        c.check(True, "Node isn't installed: skipped Build exe")
        return

    def section(title):
        """What build_exe_pack_test.mjs said under == Build exe: title."""
        at = p.stdout.find(f"== Build exe: {title}")
        rest = p.stdout[at:] if at >= 0 else ""
        ends = [i for i in (rest.find("\n== ", 1), rest.find("build_exe_pack:")) if i > 0]
        return rest[:min(ends)] if ends else rest

    saves = section("a built app keeps what it saves")
    c.check(saves.count("  ok  ") >= 9 and "FAIL" not in saves,
            "a built app (run as the real one runs) keeps what it saves in a folder of its own beside its .exe (other files "
            "beside it aren't taken for its own), or in TuffApps when it can't write there, reads it back the next time it "
            "starts, starts from the files packed with it, and imports its own .tuf files from the app; not built, a program's "
            "files stay next to it", (saves or p.stdout)[-1500:] + p.stderr[-300:])
    semi = section(f"a project folder with {sep} in its path")
    c.check(semi.count("  ok  ") >= 6 and "FAIL" not in semi,
            f"a project folder with {sep} in its path builds: every --add-data has one {sep} (it packs copies of the files), and the "
            "app's name drops it", (semi or p.stdout)[-1500:] + p.stderr[-300:])


TESTS = {"snake": t_snake, "breakout": t_breakout, "snake3d": t_snake3d, "axe": t_axe, "features_2d": t_features_2d,
         "toolbox": t_toolbox, "toolbox_fixes": t_toolbox_fixes, "looks": t_looks,
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
TESTS.update({"recursion": t_recursion, "recursion_window": t_recursion_window, "pictures_up": t_pictures_up})  # 1.4.1
TESTS.update({"interp": t_interp})  # 1.5.0
TESTS.update({"fstrings": t_fstrings})  # 1.5.0
TESTS.update({"frames": t_frames, "frames_window": t_frames_window})  # 1.5.0: sprite sheets
TESTS.update({"numbers": t_numbers})  # 1.5.0: too-big numbers, quicker library calls
TESTS.update({"modules": t_modules})  # 1.5.0: your own files as libraries (import money.tuf)
TESTS.update({"kinds": t_kinds})  # 1.5.0: your own objects
TESTS.update({"tterm": t_tterm})  # 1.5.0: terminal games
TESTS.update({"tmusic": t_tmusic})  # 1.5.0: music from notes
TESTS.update({"debug": t_debug})  # 1.5.0: the debugger
TESTS.update({"starters": t_starters})  # 1.5.0: New Project's starters
TESTS.update({"learn_150": t_learn_150})  # 1.5.0: Learn's Section 1.7, the Workshop
TESTS.update({"build_pack": t_build_pack})  # 1.5.0: Build exe with its packing tool stood in for (a built app's own files)


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
