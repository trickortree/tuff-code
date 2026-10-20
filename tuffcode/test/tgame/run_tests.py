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
NOTICE = "Tuff Engine is coming soon: a visual way to make games with TuffCode."
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


def t_no_webgl(c):
    """Without WebGL (as on some school PCs and virtual machines), a 3D world stops with one plain message."""
    if os.name != "nt":
        c.check(True, "not Windows: skipped the no-WebGL check")
        return
    r = play("no_webgl", game("hud_3d.tuf"), [{"at": 1.0, "close": True}],
             env={"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--disable-3d-apis"})
    c.check(r.code == 1 and r.err.count("Tuff error") == 1 and "can't show 3D worlds" in r.err and "line 5" in r.err,
            f"one clear error, on the tgame.world line, instead of one for every object (exit {r.code})", r.err[-600:])


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
  plain: after('app = tgui.window()\\n'), games: after('mention tgame\\n') }));
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
        "churn.tuf", "pause_key.tuf", "hud_3d.tuf"]
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
]


def t_checker(c):
    for name in GOOD:
        p = subprocess.run(tuff_cmd() + ["--check", os.path.join(GAMES, name)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0 and p.stdout.strip() == "OK", f"--check accepts {name}", (p.stdout + p.stderr)[:400])
    folder = os.path.join(HERE, "out", "checker")
    os.makedirs(folder, exist_ok=True)  # never in the temp folder: there the checker leaves file names alone
    for i, src in enumerate(GOOD_SNIPPETS):
        path = os.path.join(folder, f"good{i}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write("mention tgame\n" + src)
        p = subprocess.run(tuff_cmd() + ["--check", path], capture_output=True, text=True, encoding="utf-8", timeout=60)
        c.check(p.returncode == 0, f"--check accepts snippet {i + 1}: {src.splitlines()[1][:60]}", (p.stdout + p.stderr)[:400])
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
         "churn": t_churn, "pause_key": t_pause_key, "close": t_close, "hud_3d": t_hud_3d, "no_webgl": t_no_webgl,
         "notice": t_notice, "mcp": t_mcp, "checker": t_checker, "editor": t_editor, "guide": t_guide, "perf": t_perf}


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
