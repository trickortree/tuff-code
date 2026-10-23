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


def play(name, program, steps, timeout=60, seed=1, env=None):
    """Run a game with a list of autopilot steps; returns Played."""
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
    c.check(shot and color_share(shot, (32, 58, 116), 30) > 0.002, "the screenshot shows the player's blue shirt", shot)


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
    explosion scatters boxes, and ragdolls stand until they're pushed or hit, then flop and lie on the ground."""
    r = play("physics_drop", game("physics_drop.tuf"), [
        {"at": 0.3, "dump": "pd_start.json"},
        {"at": 0.8, "tuff": "lifted = world:box(-3, 0, 4, 1, \"gold\"):physics()"},
        {"at": 1.3, "tuff": "lifted:move_to(-3, 5, 4)"}, {"at": 1.4, "dump": "pd_lifted.json"},
        {"at": 3.5, "call": "report"}, {"at": 3.55, "dump": "pd_end.json"}, {"at": 3.6, "shot": "physics_drop.png"},
        {"at": 3.7, "tuff": "world:pause()"}, {"at": 3.8, "dump": "pd_pause1.json"}, {"at": 4.4, "dump": "pd_pause2.json"},
        {"at": 4.5, "close": True}])
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


def t_physics_player(c):
    """The player and physics: walking into a crate pushes it, the player stands on a physics box and jumps off it,
    and a ball falling on the player is an on_hit."""
    r = play("physics_player", game("physics_player.tuf"), [
        {"at": 0.6, "call": "where"},
        {"at": 0.7, "hold": "w", "for": 1.5},
        {"at": 2.4, "call": "where"}, {"at": 2.45, "dump": "pp_push.json"}, {"at": 2.5, "shot": "physics_player.png"},
        {"at": 2.6, "call": "stand"},
        {"at": 3.8, "call": "where"}, {"at": 3.85, "dump": "pp_stand.json"},
        {"at": 3.9, "key": "space"}, {"at": 4.2, "dump": "pp_jump.json"},
        {"at": 5.0, "tuff": "player:move_to(6, 0, 8)"}, {"at": 5.1, "call": "drop"},
        {"at": 6.6, "close": True}])
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
    c.check(any(line.startswith("the player was hit by <sphere") for line in r.lines), "a ball falling on the player: player:on_hit runs",
            r.lines[-4:])
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


def t_physics_2d(c):
    """2D physics: a ball bounces on a static floor and its on_hit runs, a box lands on the floor, a line falls flat,
    a push sends the ball up, and the window's edges are walls."""
    r = play("physics_2d", game("physics_2d.tuf"), [
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
    button that changes the coins, B opens a shop that pauses the world (no walking, no looking around, and the mouse
    is let go), buying changes the panel, W typed into the chat box doesn't walk, Escape shows a pause menu."""
    r = play("ui_3d", game("ui_3d.tuf"), [
        {"at": 0.3, "hold": "w", "for": 0.4},
        {"at": 0.9, "dump": "ui3d_start.json"}, {"at": 1.2, "shot": "ui3d_start.png"},
        {"at": 1.3, "click_ui": "Click to play"},
        {"at": 1.5, "dump": "ui3d_playing.json"},
        {"at": 1.6, "hold": "w", "for": 0.5},
        {"at": 2.3, "dump": "ui3d_walked.json"},
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


def t_guide(c):
    """Every example in the guide's tgame section passes --check and runs (a window opens and is closed)."""
    import re
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
        "physics_ragdoll.tuf", "physics_2d.tuf"]
BAD = [
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
    ('game = tgame.window("x")\ngame:menu "Shop"\n', "A game doesn't have :menu. Use :screen instead."),
    ('w = tgame.world("x")\nw:title_screen "Go"\n', "A world doesn't have :title_screen. Use :start_screen instead."),
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
    ('game = tgame.window("x")\ngame:menu("Shop")\n', "A game doesn't have :menu. Use :screen instead."),
    ('w = tgame.world("x")\nw:title_screen("Go")\n', "A world doesn't have :title_screen. Use :start_screen instead."),
    # physics
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:physics("dinamic")\n', 'not "dinamic". Did you mean "dynamic"?'),
    ('game = tgame.window("x")\nb = game:box(1, 2)\nb:physics "bouncy"\n', 'Physics can be "dynamic" (it falls and gets pushed)'),
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:rigidbody()\n', "An object doesn't have :rigidbody. Use :physics instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:apply_impulse(0, 5, 0)\n', "An object doesn't have :apply_impulse. Use :push instead."),
    ('game = tgame.window("x")\nb = game:circle(1, 2)\nb:restitution(0.5)\n', "A sprite doesn't have :restitution. Use :bounce instead."),
    ('w = tgame.world("x")\ncrate = w:box(0, 0, 0)\ncrate:on_hit(go)\nfunc go(a, b, c):\n    nil\n', "go() needs 3 inputs"),
    ('w = tgame.world("x")\nw:car(0, 0, 0, "redd")\n', "'redd' isn't a color tgame knows."),
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
]


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
    templates = os.path.join(REPO, "tuffcode", "renderer", "js", "tuff-templates.js")
    load = "const window = {}; require('vm').runInNewContext(require('fs').readFileSync(process.argv[1], 'utf8'), { window }); " \
           "console.log(JSON.stringify(window.TUFF_GAME_EXAMPLES || []))"
    try:
        games = json.loads(subprocess.run(["node", "-e", load, templates], capture_output=True, text=True, encoding="utf-8", timeout=60).stdout)
    except FileNotFoundError:
        games = None
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
               "objects": page.get("objects")}
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


TESTS = {"snake": t_snake, "breakout": t_breakout, "snake3d": t_snake3d, "axe": t_axe, "features_2d": t_features_2d,
         "features_3d": t_features_3d, "player_3d": t_player_3d, "callback": t_callback, "errors": t_errors,
         "models": t_models,
         "churn": t_churn, "pause_key": t_pause_key, "close": t_close, "hud_3d": t_hud_3d, "terrain": t_terrain,
         "terrain_look": t_terrain_look, "no_webgl": t_no_webgl, "ui_2d": t_ui_2d, "ui_3d": t_ui_3d,
         "physics": t_physics, "physics_player": t_physics_player, "physics_car": t_physics_car, "physics_2d": t_physics_2d,
         "physics_off": t_physics_off,
         "scene": t_scene, "notice": t_notice, "mcp": t_mcp, "checker": t_checker, "editor": t_editor, "guide": t_guide, "perf": t_perf}


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
