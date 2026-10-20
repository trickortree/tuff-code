"""tgame: games for Tuff, in 2D (like pygame) and 3D (three.js), shown in a web view by tuff_view.

    mention tgame
    game = tgame.window("Snake", 600, 400)     # 2D: shapes, text and pictures on a canvas
    world = tgame.world("Axe Sim")             # 3D: a sky, the ground, objects and a player

A game runs in either of two styles, and they mix:
    while game:open():                         # the pygame style: a loop of your own
        dt = game:frame()
    game:every_frame(step)                     # the callback style: func step(dt):

Everything here runs on the Tuff thread (tuff_view.run gives it to the program). The page only draws.
Positions, collisions, animations, timers and the player all live here, so the program always sees the
world the page shows. Each object keeps its own copy of what it sent, and only changes are sent, once
per frame.
"""
import base64
import collections
import json
import math
import os
import random
import struct
import sys
import time

# ---------------------------------------------------------------- what tgame knows

COLORS = {
    # tgui's colors, so the same names look the same in apps and games
    "blue": "#3574f0", "purple": "#8b5cf6", "pink": "#ec4899", "red": "#e5484d", "orange": "#f97316",
    "yellow": "#e2a508", "green": "#22a35a", "teal": "#14b8a6", "white": "#ffffff", "black": "#000000",
    "gray": "#8a8d94", "grey": "#8a8d94",
    # and some for games
    "brown": "#8b5a2b", "gold": "#f2c230", "lime": "#84cc16", "cyan": "#22d3ee", "navy": "#1e3a8a",
    "sky": "#87ceeb", "sand": "#e8d39a", "grass": "#5fa83f", "leaf": "#4f9d3a", "wood": "#a0703c",
    "stone": "#9a9a92", "water": "#2f7fc8", "snow": "#f4f7fb", "silver": "#c0c6cf",
    "dark green": "#2f6b2f", "dark gray": "#3b3f46", "dark grey": "#3b3f46", "light gray": "#c9ccd1",
    "light grey": "#c9ccd1", "dark blue": "#1d3f8f", "light blue": "#8ec5ff",
}
COLOR_HELP = "red, orange, yellow, green, teal, blue, purple, pink, white, black, gray, brown, gold, sky, sand, grass, wood, stone"

# Built-in sounds: notes for the page's synth, [frequency, start, seconds, wave, volume, end frequency].
SOUNDS = {
    "beep": [[880, 0, 0.12, "square", 1]],
    "coin": [[988, 0, 0.07, "square", 0.9], [1319, 0.07, 0.28, "square", 0.9]],
    "jump": [[260, 0, 0.2, "square", 0.9, 720]],
    "hit": [[220, 0, 0.14, "square", 0.9, 55], [2400, 0, 0.09, "noise", 0.7, 300]],
    "boom": [[1600, 0, 0.7, "noise", 1, 50], [90, 0, 0.55, "sine", 1, 28]],
    "chop": [[2200, 0, 0.08, "noise", 1, 600], [190, 0, 0.1, "triangle", 1, 80]],
    "laser": [[1500, 0, 0.22, "sawtooth", 0.6, 180]],
    "pop": [[520, 0, 0.08, "sine", 1, 1300]],
    "click": [[2000, 0, 0.03, "square", 0.5]],
    "step": [[900, 0, 0.06, "noise", 0.5, 150]],
    "powerup": [[300, 0, 0.45, "square", 0.6, 1500]],
    "win": [[523, 0, 0.12, "square", 0.8], [659, 0.12, 0.12, "square", 0.8], [784, 0.24, 0.12, "square", 0.8],
            [1047, 0.36, 0.4, "square", 0.8]],
    "lose": [[392, 0, 0.22, "triangle", 1], [330, 0.22, 0.22, "triangle", 1], [262, 0.44, 0.5, "triangle", 1, 200]],
}
SOUND_FILES = (".wav", ".mp3", ".ogg", ".m4a")
IMAGE_FILES = (".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp", ".svg")
MODEL_FILES = (".glb",)

SKIES = {
    # sky: [top, horizon, below]; fog color; sun color and brightness; hemisphere sky/ground color and brightness;
    # where the sun is; how far you can see
    "day": {"sky": ["#2f80d8", "#bfe2ff", "#a7c79a"], "fog": "#cfe8ff", "sun": ("#fff4e0", 2.6),
            "hemi": ("#dcefff", "#5a7a48", 1.15), "at": (30, 60, 22), "far": 170},
    "sunset": {"sky": ["#24306a", "#ff9858", "#5b3f52"], "fog": "#e8946a", "sun": ("#ffc08a", 2.4),
               "hemi": ("#ffe0c8", "#55465c", 1.15), "at": (-60, 22, -25), "far": 150},
    "dawn": {"sky": ["#5c6fb4", "#ffc6c0", "#9b8f9a"], "fog": "#f2c9c4", "sun": ("#ffd9c4", 1.8),
             "hemi": ("#ffe2da", "#4d4a56", 0.95), "at": (70, 14, 20), "far": 150},
    "night": {"sky": ["#03050c", "#18213c", "#080b14"], "fog": "#121a30", "sun": ("#a8b8ff", 0.55),
              "hemi": ("#3a4a85", "#0c0c14", 0.55), "at": (25, 50, -30), "far": 110},
    "cloudy": {"sky": ["#7d8794", "#c9cfd6", "#8e968c"], "fog": "#c3c9cf", "sun": ("#f0f2f5", 1.2),
               "hemi": ("#e3e7ec", "#59604f", 1.25), "at": (20, 60, 30), "far": 120},
    "space": {"sky": ["#000000", "#05060d", "#000000"], "fog": None, "sun": ("#ffffff", 2.4),
              "hemi": ("#4050a0", "#101010", 0.35), "at": (40, 30, 30), "far": 0},
}
KIT = ("tree", "pine", "rock", "bush", "flower", "house", "hut", "sign", "crate", "fence", "coin")
HOLDABLE = ("axe", "pickaxe", "sword", "torch", "hammer")
EDGE_MODES = ("bounce", "wrap", "stop", "none")
PLAYER_MODES = ("first person", "third person")
ALIGNS = ("left", "center", "centre", "right")

# Methods people coming from other engines guess, and the tgame name (for "Use :box instead").
HINTS = {
    "game": {"rect": "box", "rectangle": "box", "square": "box", "oval": "circle", "ellipse": "circle", "label": "text",
             "sprite": "image", "picture": "image", "draw_text": "text", "is_open": "open", "running": "open", "update": "frame",
             "tick": "frame", "key_down": "held", "is_pressed": "held", "key_pressed": "pressed", "on_click": "clicked",
             "play": "sound", "play_sound": "sound", "bg": "background", "fill": "background", "quit": "close", "wait": "after",
             "keydown": "on_key", "on_keypress": "on_key"},
    "world": {"cube": "box", "ball": "sphere", "add": "spawn", "model": "spawn", "make": "spawn", "floor": "ground",
              "camera": "camera_at", "is_open": "open", "running": "open", "update": "frame", "key_down": "held",
              "on_click": "clicked", "play": "sound", "quit": "close", "rect": "box", "text": "hud", "label": "hud",
              "keydown": "on_key", "raycast": "looking_at", "ray": "looking_at", "pick": "looking_at"},
    "sprite": {"goto": "move_to", "go_to": "move_to", "position": "move_to", "rotate": "turn", "rotation": "angle",
               "collide": "touches", "collides": "touches", "colliding": "touches", "hits": "touches", "touching": "touches",
               "velocity": "speed", "fill": "color", "colour": "color", "text": "set", "on_click": "clicked", "delete": "remove",
               "destroy": "remove", "kill": "remove", "wrap": "on_edge", "bounce": "on_edge", "keep_on_screen": "on_edge"},
    "object": {"goto": "move_to", "go_to": "move_to", "position": "move_to", "rotate": "turn", "rotation": "angle",
               "collide": "touches", "collides": "touches", "touching": "touches", "hits": "touches", "velocity": "speed",
               "colour": "color", "on_click": "clicked", "delete": "remove", "destroy": "remove", "kill": "remove",
               "text": "label", "name": "label", "chop": "shake", "topple": "fall"},
    "player": {"goto": "move_to", "position": "move_to", "speed": "walk_speed", "jump_power": "jump_height",
               "holds": "hold", "equip": "hold", "aim": "looking_at", "target": "looking_at"},
}

KEY_CODES = {"Space": "space", "ArrowUp": "up", "ArrowDown": "down", "ArrowLeft": "left", "ArrowRight": "right",
             "Enter": "enter", "NumpadEnter": "enter", "Escape": "escape", "Tab": "tab", "Backspace": "backspace",
             "ShiftLeft": "shift", "ShiftRight": "shift", "ControlLeft": "ctrl", "ControlRight": "ctrl",
             "AltLeft": "alt", "AltRight": "alt", "Delete": "delete", "Minus": "-", "Equal": "=", "Comma": ",",
             "Period": ".", "Slash": "/", "Semicolon": ";", "Quote": "'", "BracketLeft": "[", "BracketRight": "]",
             "Backslash": "\\", "Backquote": "`"}
KEY_ALIASES = {" ": "space", "spacebar": "space", "space bar": "space", "esc": "escape", "return": "enter",
               "control": "ctrl", "arrowup": "up", "arrowdown": "down", "arrowleft": "left", "arrowright": "right",
               "arrow up": "up", "arrow down": "down", "arrow left": "left", "arrow right": "right", "up arrow": "up",
               "down arrow": "down", "left arrow": "left", "right arrow": "right", "del": "delete",
               "left mouse": "mouse", "left click": "mouse", "click": "mouse", "mouse left": "mouse",
               "right click": "right mouse", "mouse right": "right mouse", "middle click": "middle mouse"}
NAMED_KEYS = {"space", "enter", "escape", "tab", "backspace", "shift", "ctrl", "alt", "delete", "up", "down", "left",
              "right", "mouse", "right mouse", "middle mouse"} | {f"f{i}" for i in range(1, 13)}
MOUSE_BUTTONS = {0: "mouse", 1: "middle mouse", 2: "right mouse"}
# For the autopilot (tests): what the browser says for a key: (key, code).
KEY_EVENTS = {"space": (" ", "Space"), "up": ("ArrowUp", "ArrowUp"), "down": ("ArrowDown", "ArrowDown"),
              "left": ("ArrowLeft", "ArrowLeft"), "right": ("ArrowRight", "ArrowRight"), "enter": ("Enter", "Enter"),
              "escape": ("Escape", "Escape"), "tab": ("Tab", "Tab"), "shift": ("Shift", "ShiftLeft"),
              "ctrl": ("Control", "ControlLeft"), "alt": ("Alt", "AltLeft"), "backspace": ("Backspace", "Backspace")}

GRAVITY = 22.0
MISSING = object()


def norm_key(name):
    """The name tgame uses for a key ("space", "a", "up", "mouse"...), or None if it isn't one."""
    t = str(name).strip().lower()
    t = KEY_ALIASES.get(t, t)
    if t in NAMED_KEYS or (len(t) == 1 and t.isprintable() and not t.isspace()):
        return t
    return None


def key_of_event(e):
    """The tgame name of the key in a keydown/keyup event (by its place on the keyboard, so Shift doesn't matter)."""
    code = e.get("code") or ""
    if code.startswith("Key") and len(code) == 4:
        return code[3].lower()
    if code.startswith("Digit") and len(code) == 6:
        return code[5]
    if code.startswith("Numpad") and code[6:].isdigit():
        return code[6:]
    if code in KEY_CODES:
        return KEY_CODES[code]
    if code[:1] == "F" and code[1:].isdigit():
        return code.lower()
    return norm_key(e.get("key") or "")


def tidy(v):
    """A number as Tuff shows it nicely: 3 decimals at most, whole numbers without .0."""
    v = round(v, 3) + 0.0
    return int(v) if v.is_integer() else v


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ease(t):
    return t * t * (3 - 2 * t)


def image_size(path):
    """(width, height) of a picture file, read from its header, or None."""
    try:
        with open(path, "rb") as f:
            data = f.read(256 * 1024)
    except OSError:
        return None
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:2] == b"BM":
            w, h = struct.unpack("<ii", data[18:26])
            return abs(w), abs(h)
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            kind = data[12:16]
            if kind == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if kind == b"VP8L":
                bits = struct.unpack("<I", data[21:25])[0]
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if kind == b"VP8X":
                return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if data[:2] == b"\xff\xd8":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    except (struct.error, IndexError):
        pass
    return None


def euler(heading, tilt_axis, tilt, pitch):
    """three.js rotation (x, y, z in degrees, XYZ order) for: pitch about the object's own x, then its heading
    (degrees clockwise seen from above), then a tilt of `tilt` degrees about a level axis in the world."""
    if not tilt and not pitch:
        return 0.0, -heading, 0.0

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    h = math.radians(-heading)
    c, s = math.cos(h), math.sin(h)
    m = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    if pitch:
        p = math.radians(pitch)
        c, s = math.cos(p), math.sin(p)
        m = mul(m, [[1, 0, 0], [0, c, -s], [0, s, c]])
    if tilt:
        kx, kz = tilt_axis
        t = math.radians(tilt)
        c, s, v = math.cos(t), math.sin(t), 1 - math.cos(t)
        r = [[c + kx * kx * v, -kz * s, kx * kz * v],
             [kz * s, c, -kx * s],
             [kz * kx * v, kx * s, c + kz * kz * v]]
        m = mul(r, m)
    m13 = clamp(m[0][2], -1.0, 1.0)
    ry = math.asin(m13)
    if abs(m13) < 0.9999999:
        rx, rz = math.atan2(-m[1][2], m[2][2]), math.atan2(-m[0][1], m[0][0])
    else:
        rx, rz = math.atan2(m[2][1], m[1][1]), 0.0
    return math.degrees(rx), math.degrees(ry), math.degrees(rz)


class Methods(dict):
    """A thing's :methods. A name people often guess (like :rect) explains which one to use instead."""
    __slots__ = ("hints", "what", "rt")

    def get(self, name, default=None):
        fn = dict.get(self, name)
        if fn is not None:
            return fn
        alt = self.hints.get(str(name).lower()) if self.hints else None
        if alt and alt in self:
            what, rt = self.what, self.rt

            def hint(*_args):
                raise rt.error(f"{what} doesn't have :{name}. Use :{alt} instead.")
            return hint
        return default


def methods(obj, kind, names, rt):
    m = Methods((name, getattr(obj, attr)) for name, attr in names)
    m.hints = HINTS.get(kind)
    m.what = f"{'An' if kind[:1] in 'aeiou' else 'A'} {kind}"
    m.rt = rt
    return m


def thing_of(v):
    """The tgame object behind a Tuff value (a sprite, an object, the player, a group), or None."""
    return getattr(v, "tg", None)


# ---------------------------------------------------------------- the library

class Lib:
    def __init__(self, rt):
        self.rt = rt
        self.game = None

    def check_fn(self, fn, what):
        if self.rt.callable(fn):
            return fn
        raise self.rt.error(f"{what} needs a function name, like step (without brackets).")

    def open_game(self, cls, title, width, height, label):
        rt = self.rt
        if self.game is not None:
            raise rt.error("A program can only open one game window. Use the one you made.")
        width, height = rt.number(width, label), rt.number(height, label)
        if width < 100 or height < 100:
            raise rt.error(f"{label} needs a width and height of at least 100.")
        self.game = cls(self, rt.text(title), int(width), int(height))
        return self.game.native

    def window(self, title="My Game", width=800, height=600):
        return self.open_game(Game2D, title, width, height, "tgame.window")

    def world(self, title="My World", width=960, height=600):
        return self.open_game(World3D, title, width, height, "tgame.world")


def make_library(rt):
    lib = Lib(rt)
    return {"window": rt.builtin("tgame.window", lib.window), "world": rt.builtin("tgame.world", lib.world)}


# ---------------------------------------------------------------- what every game window has

class Game:
    KIND = "game"
    three_d = False
    NAMES = [
        ("open", "is_open"), ("frame", "frame"), ("every_frame", "every_frame"), ("on_key", "on_key"),
        ("clicked", "on_clicked"), ("held", "held"), ("pressed", "pressed"), ("mouse_x", "mouse_x"),
        ("mouse_y", "mouse_y"), ("after", "after"), ("every", "every"), ("time", "time"), ("fps", "fps"),
        ("pause", "pause"), ("resume", "resume"), ("paused", "paused"), ("game_over", "game_over"),
        ("sound", "sound"), ("beep", "beep"), ("music", "music"), ("stop_music", "stop_music"),
        ("volume", "volume"), ("title", "set_title"), ("close", "close"), ("width", "width"),
        ("height", "height"), ("background", "background"), ("random_spot", "random_spot"),
        ("group", "group"), ("hud", "get_hud"), ("clear", "clear"),
    ]

    def __init__(self, lib, title, width, height):
        import tuff_view
        self.tv = tuff_view
        self.lib, self.rt = lib, lib.rt
        self.W, self.H = width, height
        self.closed = self.close_seen = False
        self.down, self.just = set(), set()
        self.ticks, self.key_fns, self.click_fns, self.timers = [], [], [], []
        self.clock = 0.0
        self.last = None
        self.started = time.perf_counter()
        self.stamps = collections.deque(maxlen=240)
        self.frames = 0
        self.work = collections.deque(maxlen=600)    # seconds of the program's own work between frames
        self.engine = collections.deque(maxlen=600)  # seconds tgame spends each frame (input, movers, player)
        self.work_from = None
        self.is_paused = False
        self.over_fn = None
        self.screen = []  # the pause / game over screen's shapes
        self.showing = None  # what that screen says
        self.movers = set()
        # Every sprite and object the program made and hasn't removed, oldest first (a dict used as an ordered
        # set, so :remove lets go of a thing at once: a game that makes and removes bullets all day stays small).
        self.things = {}
        self.by_node = {}
        self.hud_layer = None
        self.wheel = 0.0
        self.locked = False
        self.fake_lock = False
        self.blurs = 0
        self.sound_count = 0
        self.base = getattr(getattr(self.rt, "interp", None), "base_dir", None) or os.getcwd()
        self.autopilot = Autopilot.load(self)
        # Sound may start without a click first (games often beep before anyone clicks).
        os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                              "--disable-features=ElasticOverscroll --autoplay-policy=no-user-gesture-required")
        options = {"on_top": True} if self.autopilot and self.autopilot.on_top else {}
        try:
            self.view = tuff_view.View(title, width, height, assets=self.base, on_error=self.engine_error,
                                       background=self.BACKGROUND, **options)
        except tuff_view.ViewError as exc:
            raise self.rt.error(str(exc))
        # The window's size includes its title bar and borders: grow it so the game itself gets the size asked for.
        iw, ih = self.view.size
        if iw and ih and (abs(iw - width) > 1 or abs(ih - height) > 1):
            self.view.resize(width + (width - iw), height + (height - ih))
        self.native = self.rt.native(self.KIND, methods(self, self.KIND, self.NAMES, self.rt),
                                     lambda nested=False: f"<{self.KIND} {self.W}x{self.H}>")
        self.native.tg = self
        self.rt.on_finish(self.mainloop)
        self.setup()

    # ---- helpers
    def engine_error(self, exc, where):
        sys.stderr.write(f"Tuff error: the game window had a problem ({where}): {exc}\n")
        sys.stderr.flush()

    def num(self, v, what):
        return self.rt.number(v, what)

    def color(self, v, what="color"):
        t = self.rt.text(v).strip().lower()
        if t in COLORS:
            return COLORS[t]
        if t[:1] == "#" and len(t) in (4, 7) and all(c in "0123456789abcdef" for c in t[1:]):
            return t
        raise self.rt.error(f"'{t}' isn't a color tgame knows. Try {COLOR_HELP}, or a hex code like \"#ff8800\".")

    def file_url(self, name, what, exts):
        """The page's address for a file in the project folder (a picture, a sound, a model)."""
        rel = self.rt.text(name).strip()
        if not rel.lower().endswith(exts):
            raise self.rt.error(f"'{rel}' isn't a {what} file tgame can use. Use {', '.join(exts[:-1])} or {exts[-1]}.")
        full = rel if os.path.isabs(rel) else os.path.join(self.base, rel)
        if not os.path.isfile(full):
            raise self.rt.error(f"Couldn't find the {what} '{rel}'. Put it in your project folder, next to your .tuf file.")
        try:
            return self.view.url(full), full
        except self.tv.ViewError:
            raise self.rt.error(f"The {what} '{rel}' has to be inside your project folder.")

    def fire(self, fn, *args):
        return self.rt.call(fn, *args)[0]

    def adopt(self, thing):
        self.things[thing] = None
        return thing

    # ---- the loop
    def is_open(self):
        if not self.view.is_open:  # closed with its X, even in a loop that never calls game:frame()
            self.closed = True
        return not self.closed

    def frame(self):
        if self.closed:
            if self.close_seen:
                raise self.tv.ViewClosed()
            self.close_seen = True
            return 0
        return self.step()

    def step(self):
        """One frame: send the changes, wait for the next tick, handle input, move what moves by itself."""
        now = time.perf_counter()
        if self.work_from is not None:
            self.work.append(now - self.work_from)
        try:
            self.view.frame()
        except self.tv.ViewClosed:
            self.closed = True
            return 0
        t = time.perf_counter()
        real = min(0.1, t - self.last) if self.last else 0.0
        self.last = t
        self.stamps.append(t)
        self.frames += 1
        self.just = set()
        self.wheel = 0.0
        self.handle(self.view.events())
        if self.autopilot:
            self.autopilot.tick(t)
        if self.closed or not self.view.is_open:
            self.closed = True
            return 0
        dt = 0.0 if self.is_paused else real
        if dt:
            self.clock += dt
            self.run_timers()
            for thing in list(self.movers):
                if thing.alive:
                    thing.tick(dt)
                else:
                    self.movers.discard(thing)
        self.update(dt, real)
        self.engine.append(time.perf_counter() - t)
        # Every-frame functions run while the game is paused too, with dt 0 (what game:frame() gives a loop then),
        # so a step function can still see the key that resumes the game.
        for fn in list(self.ticks):
            if not self.fire(fn, dt) and fn in self.ticks:
                self.ticks.remove(fn)  # a function that fails is switched off, like tgui's :every
        self.work_from = time.perf_counter()
        return dt

    def mainloop(self):
        """After the program's last line: keep the game running until its window closes."""
        try:
            while not self.closed:
                self.step()
        except KeyboardInterrupt:
            pass

    def update(self, dt, real):
        """What a 2D game or a 3D world does every frame besides moving things (the camera, the player)."""

    def every_frame(self, fn):
        self.ticks.append(self.lib.check_fn(fn, ":every_frame"))

    def after(self, seconds, fn):
        fn = self.lib.check_fn(fn, ":after")
        self.timers.append([self.clock + max(0.0, self.num(seconds, ":after")), None, fn])

    def every(self, seconds, fn):
        fn = self.lib.check_fn(fn, ":every")
        gap = max(0.01, self.num(seconds, ":every"))
        self.timers.append([self.clock + gap, gap, fn])

    def run_timers(self):
        due = [t for t in self.timers if t[0] <= self.clock]
        for t in sorted(due, key=lambda t: t[0]):
            if t[1] is None:
                self.timers.remove(t)
                self.fire(t[2])
            else:
                t[0] = max(t[0] + t[1], self.clock - t[1])
                if not self.fire(t[2]) and t in self.timers:
                    self.timers.remove(t)

    def time(self):
        return tidy(self.clock)

    def fps(self):
        s = self.stamps
        if len(s) < 2:
            return 0
        recent = [x for x in s if x >= s[-1] - 1.0]
        if len(recent) < 2:
            return 0
        return round((len(recent) - 1) / (recent[-1] - recent[0]))

    # ---- input
    def handle(self, events):
        for e in events:
            t = e.get("type")
            if t == "keydown":
                name = key_of_event(e)
                if not name:
                    continue
                fresh = name not in self.down
                self.down.add(name)
                if fresh and not e.get("repeat"):
                    self.just.add(name)
                    self.key_pressed(name)
            elif t == "keyup":
                name = key_of_event(e)
                self.down.discard(name)
            elif t == "mousedown":
                name = MOUSE_BUTTONS.get(e.get("button", 0), "mouse")
                self.down.add(name)
                self.just.add(name)
            elif t == "mouseup":
                self.down.discard(MOUSE_BUTTONS.get(e.get("button", 0), "mouse"))
            elif t == "blur":  # the window lost focus: keys held now come up without telling us
                self.down.clear()
                self.blurs += 1
            elif t == "click":
                self.clicked_at(e)
            elif t == "wheel":
                self.wheel += e.get("dy", 0) or 0
            elif t == "lock":
                self.locked = bool(e.get("locked"))
                self.lock_changed()
            elif t == "model":  # a .glb finished loading: now its size is known, for collisions and its label
                thing = self.by_node.get(e.get("id"))
                if thing is not None and e.get("size"):
                    thing.dims = tuple(max(0.01, float(v)) for v in e["size"])
                    thing.push()
            elif t == "close":
                self.closed = True

    def key_pressed(self, name):
        if self.over_fn is not None and name in ("space", "enter", "r"):
            self.restart()
            return
        for key, fn in list(self.key_fns):
            if key == name or key == "any":
                self.fire(fn, name)

    def lock_changed(self):
        pass

    def key(self, name, what):
        k = norm_key(self.rt.text(name))
        if k is None:
            raise self.rt.error(f"{what}: '{self.rt.text(name)}' isn't a key tgame knows. Try a letter, a number, "
                                "space, enter, escape, shift, up, down, left, right, or \"mouse\".")
        return k

    def on_key(self, key, fn):
        k = "any" if self.rt.text(key).strip().lower() == "any" else self.key(key, ":on_key")
        self.key_fns.append((k, self.lib.check_fn(fn, ":on_key")))

    def on_clicked(self, fn):
        self.click_fns.append(self.lib.check_fn(fn, ":clicked"))

    def held(self, key):
        return self.key(key, ":held") in self.down

    def pressed(self, key):
        return self.key(key, ":pressed") in self.just

    # ---- pause, game over
    def pause(self, message="Paused"):
        shown = ("pause", self.rt.text(message))
        self.is_paused = True
        self.over_fn = None
        if self.showing != shown:  # a loop that pauses every frame doesn't rebuild the screen every frame
            self.show_screen(shown[1], None, None)
            self.showing = shown

    def resume(self):
        self.is_paused = False
        self.over_fn = None
        self.showing = None
        for s in self.screen:
            s.remove()
        self.screen = []

    def paused(self):
        return self.is_paused

    def game_over(self, message="", restart=None):
        if restart is not None:
            restart = self.lib.check_fn(restart, ":game_over")
        shown = ("over", self.rt.text(message) if message is not None else "", restart is not None)
        self.is_paused = True
        if self.showing != shown:
            self.show_screen("Game over", shown[1], "Press space to play again" if restart is not None else None)
            self.showing = shown
        self.over_fn = restart

    def restart(self):
        fn = self.over_fn
        self.resume()
        if fn is not None:
            self.fire(fn)

    def show_screen(self, title, message, hint):
        hud = self.hud()
        for s in self.screen:
            s.remove()
        W, H = self.W, self.H
        big = min(64, W / max(4, len(title)) * 1.4)
        text = {"bold": True, "ax": 0.5, "ay": 0.5, "z": 1e6 + 1}
        self.screen = [hud.make("rect", W / 2, H / 2, {"w": W * 3, "h": H * 3, "color": "#000000", "alpha": 0.55, "z": 1e6}, own=False),
                       hud.make("text", W / 2, H / 2 - (24 if message else 0), {**text, "text": title, "size": big, "color": "#ffffff"}, own=False)]
        if message:
            self.screen.append(hud.make("text", W / 2, H / 2 + big * 0.6, {**text, "text": message, "size": 24, "color": "#ffe9a8"}, own=False))
        if hint:
            self.screen.append(hud.make("text", W / 2, H / 2 + big * 0.6 + 40, {**text, "text": hint, "size": 18, "bold": False,
                                                                                "color": "#cfd3da"}, own=False))

    # ---- sound
    def sound(self, name):
        n = self.rt.text(name).strip()
        low = n.lower()
        if low in SOUNDS:
            self.view.call(0, "tones", SOUNDS[low], 0.3)
            return None
        if low.endswith(SOUND_FILES):
            url, _ = self.file_url(n, "sound", SOUND_FILES)
            self.sound_count += 1
            self.view.call(0, "sound", f"s{self.sound_count}", url, 1, False)
            return None
        raise self.rt.error(f"'{n}' isn't one of tgame's sounds ({', '.join(SOUNDS)}). "
                            "Or play a .wav, .mp3 or .ogg file from your project folder.")

    def beep(self, pitch=440, seconds=0.15):
        pitch = clamp(self.num(pitch, ":beep"), 20, 20000)
        seconds = clamp(self.num(seconds, ":beep"), 0.01, 10)
        self.view.call(0, "tones", [[pitch, 0, seconds, "square", 1]], 0.25)

    def music(self, file):
        url, _ = self.file_url(file, "music", SOUND_FILES)
        self.view.call(0, "sound_stop", "music")
        self.view.call(0, "sound", "music", url, 0.6, True)

    def stop_music(self):
        self.view.call(0, "sound_stop", "music")

    def volume(self, percent):
        self.view.call(0, "sound_volume", clamp(self.num(percent, ":volume"), 0, 100) / 100)

    # ---- the window
    def set_title(self, text):
        self.view.set_title(self.rt.text(text))

    def close(self):
        self.view.close()
        self.closed = True

    def width(self):
        return self.W

    def height(self):
        return self.H

    def get_hud(self):
        return self.hud().native

    def group(self):
        return Group(self).native

    def clear(self):
        """Removes every sprite and object the program made (the player stays)."""
        for thing in list(self.things):
            thing.remove()
        self.things = {}
        self.movers = set()

    def stats(self):
        """Numbers for the autopilot's reports."""
        def spread(xs):
            xs = sorted(x * 1000 for x in xs)
            return (round(xs[len(xs) // 2], 3), round(xs[min(len(xs) - 1, int(len(xs) * 0.95))], 3)) if xs else (None, None)

        (tm, tp), (em, ep) = spread(self.work), spread(self.engine)
        return {"fps": self.fps(), "frames": self.frames, "tuff_ms_median": tm, "tuff_ms_p95": tp,
                "engine_ms_median": em, "engine_ms_p95": ep}


# ---------------------------------------------------------------- 2D

class Layer:
    """A canvas full of sprites: the game itself, or the HUD on top of it."""

    def __init__(self, game, scrolls):
        self.game = game
        self.scrolls = scrolls  # the game's own layer moves with game:camera; the HUD doesn't
        self.cx = self.cy = 0.0
        self.sprites = []

    def to_layer(self, px, py):
        """A point in the window (CSS pixels) as a point on this layer."""
        g = self.game
        w, h = g.view.size
        k = min(w / g.W, h / g.H) or 1
        ox, oy = (w - g.W * k) / 2, (h - g.H * k) / 2
        return (px - ox) / k + self.cx, (py - oy) / k + self.cy

    def to_window(self, x, y):
        g = self.game
        w, h = g.view.size
        k = min(w / g.W, h / g.H) or 1
        ox, oy = (w - g.W * k) / 2, (h - g.H * k) / 2
        return (x - self.cx) * k + ox, (y - self.cy) * k + oy

    def make(self, shape, x, y, props, own=True):
        """A sprite on this layer. own=False: one of tgame's own (the pause screen, the crosshair), which
        game:clear leaves alone."""
        s = Sprite(self, shape, x, y, props)
        if own:
            self.game.adopt(s)
        return s

    def place(self, args, defaults, what):
        """The inputs of a maker: x, y (or one spot [x, y] in place of both), then the rest, with the defaults
        filled in. Left-out inputs are MISSING, and only ever at the end."""
        g = self.game
        given = [a for a in args if a is not MISSING]
        if not given:
            x, y, rest = g.W / 2, g.H / 2, []
        elif isinstance(g.rt.plain(given[0]), list):
            spot = g.rt.plain(given[0])
            if len(spot) != 2:
                raise g.rt.error(f":{what} needs a spot like [100, 50].")
            x, y, rest = spot[0], spot[1], given[1:]
        elif len(given) == 1:
            first = '"Hi", ' if what == "text" else ""
            raise g.rt.error(f":{what} needs both x and y, like ({first}100, 50), or one spot like [100, 50].")
        else:
            x, y, rest = given[0], given[1], given[2:]
        if len(rest) > len(defaults):
            raise g.rt.error(f":{what} got too many inputs.")
        return g.num(x, f":{what}"), g.num(y, f":{what}"), list(rest) + list(defaults[len(rest):])

    # what both the game and the HUD can make
    def box(self, x=MISSING, y=MISSING, width=MISSING, height=MISSING, color=MISSING):
        g = self.game
        x, y, (width, height, color) = self.place([x, y, width, height, color], (40, 40, "white"), "box")
        w, h = g.num(width, ":box"), g.num(height, ":box")
        return self.make("rect", x, y, {"w": w, "h": h, "color": g.color(color)}).native

    def circle(self, x=MISSING, y=MISSING, radius=MISSING, color=MISSING):
        g = self.game
        x, y, (radius, color) = self.place([x, y, radius, color], (20, "white"), "circle")
        return self.make("circle", x, y, {"r": max(0, g.num(radius, ":circle")), "color": g.color(color)}).native

    def line(self, x1=0, y1=0, x2=100, y2=100, color="white"):
        g = self.game
        x1, y1, x2, y2 = (g.num(v, ":line") for v in (x1, y1, x2, y2))
        return self.make("line", x1, y1, {"points": [[0, 0], [x2 - x1, y2 - y1]], "lw": 3, "color": g.color(color)}).native

    def text(self, words="", x=MISSING, y=MISSING, size=MISSING, color=MISSING):
        g = self.game
        x, y, (size, color) = self.place([x, y, size, color], (24, "white"), "text")
        return self.make("text", x, y, {"text": g.rt.text(words), "size": g.num(size, ":text"), "bold": True,
                                        "color": g.color(color), "ax": 0.5, "ay": 0.5}).native

    def image(self, file, x=MISSING, y=MISSING, width=MISSING):
        g = self.game
        x, y, (width,) = self.place([x, y, width], (None,), "image")
        url, full = g.file_url(file, "picture", IMAGE_FILES)
        nw, nh = image_size(full) or (64, 64)
        w = nw if width is None else g.num(width, ":image")
        h = nh * (w / nw) if nw else w
        return self.make("image", x, y, {"src": url, "w": w, "h": h, "file": g.rt.text(file)}).native

    def clear_layer(self):
        for s in list(self.sprites):
            if s.layer is self:
                s.remove()


class Hud(Layer):
    """A layer on top of everything that the camera doesn't move: scores, lives, messages."""
    NAMES = [("text", "text"), ("box", "box"), ("circle", "circle"), ("line", "line"), ("image", "image"),
             ("clear", "clear_layer")]

    def __init__(self, game):
        super().__init__(game, scrolls=False)
        self.node = game.view.canvas(0, fit=[game.W, game.H], style={"pointerEvents": "none"})
        self.native = game.rt.native("hud", methods(self, "hud", self.NAMES, game.rt), lambda nested=False: "<hud>")
        self.native.tg = self


class Game2D(Game, Layer):
    KIND = "game"
    BACKGROUND = "#101218"
    NAMES = Game.NAMES + [("box", "box"), ("circle", "circle"), ("line", "line"), ("text", "text"), ("image", "image"),
                          ("camera", "camera")]

    def __init__(self, lib, title, width, height):
        Layer.__init__(self, self, scrolls=True)
        Game.__init__(self, lib, title, width, height)

    def setup(self):
        self.bg = self.BACKGROUND
        self.node = self.view.canvas(0, bg=self.bg, fit=[self.W, self.H])

    def hud(self):
        if self.hud_layer is None:
            self.hud_layer = Hud(self)
        return self.hud_layer

    def background(self, color):
        self.bg = self.color(color)
        self.view.set(self.node, bg=self.bg)

    def camera(self, x=MISSING, y=MISSING):
        x, y, _ = self.place([x, y], (), "camera")
        self.cx, self.cy = x - self.W / 2, y - self.H / 2
        self.view.set(self.node, cx=self.cx, cy=self.cy)

    def mouse_x(self):
        return tidy(self.to_layer(*self.view.mouse)[0])

    def mouse_y(self):
        return tidy(self.to_layer(*self.view.mouse)[1])

    def random_spot(self, grid=None):
        if grid is None:
            m = 20
            return [random.randint(m, max(m, self.W - m)) + int(self.cx), random.randint(m, max(m, self.H - m)) + int(self.cy)]
        g = self.num(grid, ":random_spot")
        if g <= 0:
            raise self.rt.error(":random_spot needs a grid size above 0, like 20.")
        cols, rows = max(1, int(self.W // g)), max(1, int(self.H // g))
        return [tidy(random.randrange(cols) * g + g / 2 + self.cx), tidy(random.randrange(rows) * g + g / 2 + self.cy)]

    def clicked_at(self, e):
        if self.over_fn is not None:
            self.restart()
            return
        if self.is_paused:
            return
        hit = None
        layers = ([self.hud_layer] if self.hud_layer else []) + [self]
        for layer in layers:
            x, y = layer.to_layer(e.get("x", 0), e.get("y", 0))
            for s in sorted((s for s in layer.sprites if s.alive and not s.hidden and s.click_fns),
                            key=lambda s: (s.z, s.order), reverse=True):
                if s.contains(x, y):
                    hit = s
                    break
            if hit:
                break
        if hit:
            for fn in list(hit.click_fns):
                self.fire(fn, hit.native)
        if self.click_fns:
            x, y = self.to_layer(e.get("x", 0), e.get("y", 0))
            for fn in list(self.click_fns):
                self.fire(fn, tidy(x), tidy(y))

    def view_rect(self):
        return self.cx, self.cy, self.cx + self.W, self.cy + self.H


class Sprite:
    """A shape, some text or a picture in a 2D game (or on a HUD)."""
    NAMES = [
        ("x", "get_x"), ("y", "get_y"), ("spot", "spot"), ("move", "move"), ("move_to", "move_to"), ("glide", "glide"),
        ("forward", "forward"), ("turn", "turn"), ("turn_to", "turn_to"), ("angle", "angle"), ("spin", "spin"),
        ("point_at", "point_at"), ("speed", "speed"), ("on_edge", "on_edge"), ("on_screen", "on_screen"),
        ("touches", "touches"), ("distance", "distance"), ("size", "size"), ("scale", "set_scale"),
        ("color", "set_color"), ("layer", "set_layer"), ("flip", "flip"), ("align", "align"), ("hide", "hide"),
        ("show", "show"), ("remove", "remove"), ("set", "set"), ("get", "get"), ("value", "value"),
        ("clicked", "clicked"), ("shake", "shake"),
    ]
    counter = 0

    def __init__(self, layer, shape, x, y, props):
        g = layer.game
        self.game, self.layer, self.shape = g, layer, shape
        self.rt = g.rt
        self.x, self.y = float(x), float(y)
        self.rot = 0.0
        self.k = 1.0
        self.mirror = 1
        self.z = props.get("z", 0)
        Sprite.counter += 1
        self.order = Sprite.counter
        self.w = props.get("w", 0)
        self.h = props.get("h", 0)
        self.r = props.get("r", 0)
        self.points = props.get("points")
        self.words = props.get("text", "")
        self.size_ = props.get("size", 24)
        self.ax = props.get("ax", 0.5)  # where x is across a text: 0 its left edge, 0.5 its middle, 1 its right edge
        self.file = props.pop("file", None)
        self.vx = self.vy = self.spin_speed = 0.0
        self.edge = "none"
        self.anims = []
        self.data = {}
        self.click_fns = []
        self.alive = True
        self.hidden = False
        self.dx = self.dy = 0.0  # a shake's offset, drawn but not where the sprite is
        self.node = g.view.shape(layer.node, shape, x=self.x, y=self.y, **props)
        layer.sprites.append(self)
        g.by_node[int(self.node)] = self
        self.native = g.rt.native("sprite", methods(self, "sprite", self.NAMES, g.rt), self.show_text)
        self.native.tg = self

    def show_text(self, nested=False):
        what = {"rect": "box", "text": f"text \"{self.words}\""}.get(self.shape, self.shape)
        return f"<{what} at {tidy(self.x)}, {tidy(self.y)}>"

    def num(self, v, what):
        return self.rt.number(v, what)

    def send(self, **props):
        """Send changes to the page. A removed sprite sends nothing: the page has let it go, and a bullet that is
        still in the program's list after :remove just stays gone."""
        if self.alive:
            self.game.view.set(self.node, **props)

    def push(self):
        self.send(x=self.x + self.dx, y=self.y + self.dy)

    def moved(self):
        if self.edge != "none":
            self.apply_edge(False)
        self.push()

    def busy(self):
        if self.vx or self.vy or self.spin_speed or self.anims:
            self.game.movers.add(self)
        else:
            self.game.movers.discard(self)

    # ---- size and collisions (rotation is left out: boxes stay boxes)
    def half(self):
        k = self.k
        if self.shape == "circle":
            return self.r * k, self.r * k
        if self.shape == "text":
            return len(self.words) * self.size_ * 0.29 * k, self.size_ * 0.5 * k
        if self.shape == "line":
            (ax, ay), (bx, by) = self.points
            return (abs(bx - ax) / 2 + 2) * k, (abs(by - ay) / 2 + 2) * k
        return self.w * k / 2, self.h * k / 2

    def center(self):
        if self.shape == "line":
            (ax, ay), (bx, by) = self.points
            return self.x + (ax + bx) / 2 * self.k, self.y + (ay + by) / 2 * self.k
        if self.shape == "text" and self.ax != 0.5:  # aligned left or right: the words sit beside x, not around it
            return self.x + (0.5 - self.ax) * 2 * self.half()[0] * self.mirror, self.y
        return self.x, self.y

    def contains(self, x, y):
        cx, cy = self.center()
        if self.shape == "circle":
            return (x - cx) ** 2 + (y - cy) ** 2 <= (self.r * self.k) ** 2
        hw, hh = self.half()
        return abs(x - cx) <= hw and abs(y - cy) <= hh

    def overlaps(self, o):
        ax, ay = self.center()
        bx, by = o.center()
        if self.shape == "circle" and o.shape == "circle":
            return (ax - bx) ** 2 + (ay - by) ** 2 < (self.r * self.k + o.r * o.k) ** 2
        if self.shape == "circle" or o.shape == "circle":
            c, b = (self, o) if self.shape == "circle" else (o, self)
            cx, cy = c.center()
            bcx, bcy = b.center()
            hw, hh = b.half()
            px, py = clamp(cx, bcx - hw, bcx + hw), clamp(cy, bcy - hh, bcy + hh)
            return (cx - px) ** 2 + (cy - py) ** 2 < (c.r * c.k) ** 2
        aw, ah = self.half()
        bw, bh = o.half()
        return abs(ax - bx) < aw + bw and abs(ay - by) < ah + bh

    # ---- where it is
    def get_x(self):
        return tidy(self.x)

    def get_y(self):
        return tidy(self.y)

    def spot(self):
        return [tidy(self.x), tidy(self.y)]

    def xy(self, x, y, what):
        xv = self.rt.plain(x)
        if isinstance(xv, list):
            if len(xv) < 2 or y is not MISSING:
                raise self.rt.error(f":{what} takes x and y, like (100, 50), or one spot like [100, 50].")
            return self.num(xv[0], f":{what}"), self.num(xv[1], f":{what}")
        if y is MISSING:
            raise self.rt.error(f":{what} needs both x and y, like (100, 50), or one spot like [100, 50].")
        return self.num(x, f":{what}"), self.num(y, f":{what}")

    def move(self, dx, dy=0):
        self.x += self.num(dx, ":move")
        self.y += self.num(dy, ":move")
        self.moved()
        return self.native

    def move_to(self, x, y=MISSING):
        self.x, self.y = self.xy(x, y, "move_to")
        self.anims = [a for a in self.anims if a[0] != "glide"]
        self.moved()
        return self.native

    def glide(self, x, y=MISSING, seconds=MISSING):
        if isinstance(self.rt.plain(x), list) and seconds is MISSING:
            y, seconds = MISSING, y
        tx, ty = self.xy(x, y, "glide")
        secs = 1.0 if seconds is MISSING else max(0.01, self.num(seconds, ":glide"))
        self.anims = [a for a in self.anims if a[0] != "glide"]
        self.anims.append(["glide", 0.0, secs, self.x, self.y, tx, ty])
        self.busy()
        return self.native

    def forward(self, distance):
        d = self.num(distance, ":forward")
        a = math.radians(self.rot)
        self.x += math.cos(a) * d
        self.y += math.sin(a) * d
        self.moved()
        return self.native

    def turn(self, degrees):
        self.rot = (self.rot + self.num(degrees, ":turn")) % 360
        self.send(rot=self.rot)
        return self.native

    def turn_to(self, degrees):
        self.rot = self.num(degrees, ":turn_to") % 360
        self.send(rot=self.rot)
        return self.native

    def angle(self):
        return tidy(self.rot)

    def spin(self, degrees_per_second):
        self.spin_speed = self.num(degrees_per_second, ":spin")
        self.busy()
        return self.native

    def point_at(self, x, y=MISSING):
        o = thing_of(x)
        if isinstance(o, Sprite):
            tx, ty = o.center()
        else:
            tx, ty = self.xy(x, y, "point_at")
        cx, cy = self.center()
        if tx != cx or ty != cy:
            self.rot = math.degrees(math.atan2(ty - cy, tx - cx)) % 360
            self.send(rot=self.rot)
        return self.native

    def speed(self, vx, vy=0):
        self.vx, self.vy = self.num(vx, ":speed"), self.num(vy, ":speed")
        self.busy()
        return self.native

    def on_edge(self, mode):
        m = self.rt.text(mode).strip().lower()
        if m not in EDGE_MODES:
            raise self.rt.error(f":on_edge can be \"bounce\", \"wrap\", \"stop\" (stay on screen) or \"none\", not \"{m}\".")
        self.edge = m
        if m != "none":
            self.apply_edge(False)
            self.push()
        return self.native

    def apply_edge(self, moving):
        x0, y0, x1, y1 = self.layer.view_rect() if self.layer is self.game else (0, 0, self.game.W, self.game.H)
        hw, hh = self.half()
        cx, cy = self.center()
        ox, oy = cx - self.x, cy - self.y
        if self.edge == "wrap":
            if cx - hw > x1:
                self.x = x0 - hw - ox
            elif cx + hw < x0:
                self.x = x1 + hw - ox
            if cy - hh > y1:
                self.y = y0 - hh - oy
            elif cy + hh < y0:
                self.y = y1 + hh - oy
            return
        if cx - hw < x0:
            self.x = x0 + hw - ox
            if self.edge == "bounce" and self.vx < 0:
                self.vx = -self.vx
        elif cx + hw > x1:
            self.x = x1 - hw - ox
            if self.edge == "bounce" and self.vx > 0:
                self.vx = -self.vx
        if cy - hh < y0:
            self.y = y0 + hh - oy
            if self.edge == "bounce" and self.vy < 0:
                self.vy = -self.vy
        elif cy + hh > y1:
            self.y = y1 - hh - oy
            if self.edge == "bounce" and self.vy > 0:
                self.vy = -self.vy

    def on_screen(self):
        x0, y0, x1, y1 = self.layer.view_rect() if self.layer is self.game else (0, 0, self.game.W, self.game.H)
        hw, hh = self.half()
        cx, cy = self.center()
        return cx + hw >= x0 and cx - hw <= x1 and cy + hh >= y0 and cy - hh <= y1

    # ---- other sprites
    def touches(self, other):
        v = self.rt.plain(other)
        g = thing_of(v)
        if isinstance(g, Group):
            v = g.items
        if isinstance(v, list):
            for item in v:
                s = thing_of(item)
                if isinstance(s, Sprite) and s is not self and s.alive and not s.hidden and self.overlaps(s):
                    return item
            return None
        if not isinstance(g, Sprite):
            raise self.rt.error(f"sprite:touches needs another sprite, a list of sprites or a group, not {self.rt.what(v)}.")
        return bool(self.alive and not self.hidden and g is not self and g.alive and not g.hidden and self.overlaps(g))

    def distance(self, other, y=MISSING):
        o = thing_of(other)
        if isinstance(o, Sprite):
            tx, ty = o.center()
        else:
            tx, ty = self.xy(other, y, "distance")
        cx, cy = self.center()
        return tidy(math.hypot(tx - cx, ty - cy))

    # ---- how it looks
    def size(self, a, b=MISSING):
        a = self.num(a, ":size")
        if self.shape in ("rect", "image"):
            self.w, self.h = a, (self.num(b, ":size") if b is not MISSING else a)
            self.send(w=self.w, h=self.h)
        elif self.shape == "circle":
            self.r = max(0, a)  # shrunk below 0 it's gone: nothing to see, click or touch
            self.send(r=self.r)
        elif self.shape == "text":
            self.size_ = a
            self.send(size=a)
        else:
            self.send(lw=a)
        return self.native

    def set_scale(self, k):
        self.k = self.num(k, ":scale")
        self.send(scale=self.k)
        return self.native

    def set_color(self, color):
        self.send(color=self.game.color(color))
        return self.native

    def set_layer(self, n):
        self.z = self.num(n, ":layer")
        self.send(z=self.z)
        return self.native

    def flip(self):
        self.mirror = -self.mirror
        self.send(sx=self.mirror)
        return self.native

    def align(self, how):
        a = self.rt.text(how).strip().lower()
        if a not in ALIGNS:
            raise self.rt.error(":align can be \"left\", \"center\" or \"right\".")
        if self.shape != "text":
            raise self.rt.error("Only text can be aligned.")
        self.ax = {"left": 0, "right": 1}.get(a, 0.5)
        self.send(ax=self.ax)  # clicks, :touches and :on_edge follow it through center()
        return self.native

    def hide(self):
        self.hidden = True
        self.send(visible=False)
        return self.native

    def show(self):
        self.hidden = False
        self.send(visible=True)
        return self.native

    def remove(self):
        if self.alive:
            self.alive = False
            self.game.view.remove(self.node)
            self.game.movers.discard(self)
            self.game.by_node.pop(int(self.node), None)
            self.game.things.pop(self, None)
            if self in self.layer.sprites:
                self.layer.sprites.remove(self)

    # ---- its own values, and text
    def set(self, a, b=MISSING):
        if b is not MISSING:
            name = self.rt.plain(a)
            if not isinstance(name, str):
                raise self.rt.error(f"sprite:set(name, value) needs the name as text, like \"hp\", not {self.rt.what(name)}.")
            self.data[name] = self.rt.plain(b)
            return self.native
        if self.shape == "text":
            self.words = self.rt.text(a)
            self.send(text=self.words)
        elif self.shape == "image":
            url, full = self.game.file_url(a, "picture", IMAGE_FILES)
            self.send(src=url)
        else:
            raise self.rt.error("Only text and pictures can :set something new. To keep a value on a sprite, "
                                "give it a name, like sprite:set(\"hp\", 3).")
        return self.native

    def get(self, name):
        return self.data.get(self.rt.plain(name))

    def value(self):
        if self.shape != "text":
            raise self.rt.error("Only text has a :value (its words).")
        return self.words

    def clicked(self, fn):
        self.click_fns.append(self.game.lib.check_fn(fn, ":clicked"))
        return self.native

    def shake(self):
        self.anims = [a for a in self.anims if a[0] != "shake"]
        self.anims.append(["shake", 0.0, 0.35])
        self.busy()
        return self.native

    # ---- every frame, while it moves by itself
    def tick(self, dt):
        moved = False
        if self.vx or self.vy:
            self.x += self.vx * dt
            self.y += self.vy * dt
            moved = True
        if self.spin_speed:
            self.rot = (self.rot + self.spin_speed * dt) % 360
            self.send(rot=self.rot)
        for a in list(self.anims):
            a[1] += dt
            t = min(1.0, a[1] / a[2])
            if a[0] == "glide":
                e = ease(t)
                self.x, self.y = a[3] + (a[5] - a[3]) * e, a[4] + (a[6] - a[4]) * e
                moved = True
            elif a[0] == "shake":
                self.dx = math.sin(a[1] * 70) * 6 * (1 - t)
                moved = True
            if t >= 1:
                self.anims.remove(a)
                if a[0] == "shake":
                    self.dx = 0.0
        if moved:
            if self.edge != "none":
                self.apply_edge(True)
            self.push()
        self.busy()


class Group:
    """A list of sprites or objects that move, hide and show together."""
    NAMES = [("add", "add"), ("remove", "take"), ("has", "has"), ("items", "get_items"), ("count", "count"),
             ("move", "move"), ("hide", "hide"), ("show", "show"), ("clear", "clear"), ("color", "color")]

    def __init__(self, game):
        self.game = game
        self.items = []
        if game is None:
            return
        self.native = game.rt.native("group", methods(self, "group", self.NAMES, game.rt),
                                     lambda nested=False: f"<group of {len(self.live())}>")
        self.native.tg = self

    def live(self):
        self.items = [i for i in self.items if getattr(thing_of(i), "alive", False)]
        return self.items

    def member(self, item, what):
        t = thing_of(item)
        if not isinstance(t, (Sprite, Thing)):
            raise self.game.rt.error(f"group:{what} needs a sprite or an object, not {self.game.rt.what(item)}.")
        return t

    def add(self, item):
        self.member(item, "add")
        if not any(i is item for i in self.items):
            self.items.append(item)
        return self.native

    def take(self, item):
        self.items = [i for i in self.items if i is not item]
        return self.native

    def has(self, item):
        return any(i is item for i in self.live())

    def get_items(self):
        return list(self.live())

    def count(self):
        return len(self.live())

    def move(self, dx, dy=0, dz=0):
        for i in self.live():
            t = thing_of(i)
            if isinstance(t, Thing):
                t.move(dx, dy, dz)
            else:
                t.move(dx, dy)
        return self.native

    def hide(self):
        for i in self.live():
            thing_of(i).hide()
        return self.native

    def show(self):
        for i in self.live():
            thing_of(i).show()
        return self.native

    def clear(self):
        for i in self.live():
            thing_of(i).remove()
        self.items = []
        return self.native

    def color(self, c):
        for i in self.live():
            thing_of(i).set_color(c)
        return self.native


# ---------------------------------------------------------------- 3D

class World3D(Game):
    KIND = "world"
    three_d = True
    BACKGROUND = "#87ceeb"
    NAMES = Game.NAMES + [
        ("sky", "sky"), ("fog", "fog"), ("sun", "sun"), ("light", "light"), ("ground", "ground"),
        ("island", "island"), ("box", "box"), ("sphere", "sphere"), ("cylinder", "cylinder"), ("cone", "cone"),
        ("plane", "plane"), ("spawn", "spawn"), ("player", "player"), ("camera_at", "camera_at"),
        ("look_at", "look_at"), ("follow", "follow"), ("orbit", "orbit"), ("looking_at", "looking_at"),
    ]

    def setup(self):
        v = self.view
        self.cam = [0.0, 1.7, 8.0]
        self.cam_yaw = 0.0  # heading, degrees clockwise from looking down -z
        self.cam_pitch = -8.0
        self.cam_mode = "fixed"
        self.cam_target = None
        self.cam_look = None
        self.orbit_state = None
        self.the_player = None
        self.island_r = None
        self.fog_far = None
        self.sky_name = "day"
        self.scene = v.scene(0, fov=70, near=0.1, far=900, shadows=True, cx=0, cy=1.7, cz=8, yaw=0, pitch=-8)
        self.hemi = v.obj(self.scene, "hemi")
        self.sun_node = v.obj(self.scene, "sun", shadow=True, area=45)
        self.sun_strength = 1.0
        self.apply_sky("day")
        self.camera_dirty = True
        self.crosshair = None
        self.hint = None

    def hud(self):
        if self.hud_layer is None:
            self.hud_layer = Hud(self)
        return self.hud_layer

    def apply_sky(self, name):
        s = SKIES[name]
        self.sky_name = name
        far = self.fog_far if self.fog_far is not None else s["far"]
        self.view.set(self.scene, sky=s["sky"], bg=s["sky"][1], fog=[s["fog"], far * 0.3, far] if (s["fog"] and far) else None)
        self.view.set(self.hemi, color=s["hemi"][0], ground=s["hemi"][1], intensity=s["hemi"][2])
        x, y, z = s["at"]
        self.view.set(self.sun_node, color=s["sun"][0], intensity=s["sun"][1] * self.sun_strength, x=x, y=y, z=z)

    # ---- sky, light, ground
    def sky(self, preset):
        name = self.rt.text(preset).strip().lower()
        if name not in SKIES:
            raise self.rt.error(f"The sky can be {', '.join(SKIES)}, not \"{name}\".")
        self.apply_sky(name)

    def background(self, color):
        c = self.color(color)
        self.view.set(self.scene, sky=None, bg=c)

    def fog(self, distance):
        d = self.num(distance, ":fog")
        self.fog_far = max(0.0, d)
        s = SKIES[self.sky_name]
        self.view.set(self.scene, fog=[s["fog"] or "#ffffff", d * 0.3, d] if d > 0 else None)

    def sun(self, brightness):
        self.sun_strength = max(0.0, self.num(brightness, ":sun"))
        self.view.set(self.sun_node, intensity=SKIES[self.sky_name]["sun"][1] * self.sun_strength)

    def light(self, x=MISSING, y=MISSING, z=MISSING, color=MISSING):
        x, y, z, (color,) = self.where([x, y, z, color], ("white",), "light")
        t = Thing(self, "light", x, y, z, (0.3, 0.3, 0.3), [("sphere", {"r": 0.15, "color": self.color(color),
                                                                         "emissive": self.color(color), "mat": "basic"}, True)])
        t.solid_ = False
        t.light = self.view.obj(t.node, "point", y=0.15, color=self.color(color), intensity=30, distance=30)
        return t.native

    def ground(self, color="grass", size=400):
        c = self.color(color)
        sz = self.num(size, ":ground")
        t = Thing(self, "ground", 0, 0, 0, (sz, 0.01, sz), [("plane", {"w": sz, "h": sz, "rx": -90, "color": c, "shadow": True}, True)])
        t.solid_ = False
        t.floor = True
        return t.native

    def island(self, size=80):
        r = max(6.0, self.num(size, ":island") / 2)
        self.island_r = r
        parts = [
            ("cylinder", {"r": r, "h": 3, "y": -1.5, "seg": 28, "color": COLORS["grass"], "flat": True, "shadow": True}, True),
            ("cylinder", {"rt": r + 3.5, "rb": r + 5, "h": 3, "y": -1.62, "seg": 28, "color": COLORS["sand"], "flat": True}, False),
            ("plane", {"w": 1400, "h": 1400, "rx": -90, "y": -0.55, "color": "#2f7fc8", "opacity": 0.92, "rough": 0.35}, False),
        ]
        t = Thing(self, "island", 0, 0, 0, (r * 2, 0.01, r * 2), parts)
        t.solid_ = False
        t.floor = True
        return t.native

    # ---- making objects
    def where(self, args, defaults, what):
        """The inputs of a 3D method: x, y, z (or one spot [x, y, z] in place of all three), then the rest, with
        the defaults filled in. Left-out inputs are MISSING, and only ever at the end."""
        given = [a for a in args if a is not MISSING]
        if not given:
            return 0.0, 0.0, 0.0, list(defaults)
        first = self.rt.plain(given[0])
        if isinstance(first, list):
            if len(first) == 2:
                first = [first[0], 0, first[1]]
            if len(first) != 3:
                raise self.rt.error(f":{what} needs a spot like [3, 0, -5] (x, height, z).")
            coords, rest = first, given[1:]
        elif len(given) < 3:
            raise self.rt.error(f":{what} needs x, y and z (y is the height: 0 is the ground), or one spot like [3, 0, -5].")
        else:
            coords, rest = given[:3], given[3:]
        if len(rest) > len(defaults):
            raise self.rt.error(f":{what} got too many inputs.")
        x, y, z = (self.num(v, f":{what}") for v in coords)
        return x, y, z, list(rest) + list(defaults[len(rest):])

    def sizes(self, size, what, three=True):
        v = self.rt.plain(size)
        if isinstance(v, list):
            nums = [self.num(n, f":{what}") for n in v]
            if three and len(nums) == 3:
                return nums
            if not three and len(nums) == 2:
                return nums
            raise self.rt.error(f":{what}'s size is one number, or {'[width, height, depth]' if three else '[width, height]'}.")
        n = self.num(v, f":{what}")
        return [n, n, n] if three else [n, n]

    def primitive(self, kind, args, default_size):
        x, y, z, (size, color) = self.where(args, (default_size, "white"), kind)
        c = self.color(color)
        if kind == "box":
            w, h, d = self.sizes(size, kind)
            part = ("box", {"w": w, "h": h, "d": d, "y": h / 2, "color": c, "shadow": True}, True)
        elif kind == "sphere":
            n = self.num(size, ":sphere") if not isinstance(self.rt.plain(size), list) else self.sizes(size, kind)[0]
            w = h = d = n
            part = ("sphere", {"r": n / 2, "y": n / 2, "seg": 24, "color": c, "shadow": True}, True)
        elif kind == "plane":
            w, d = self.sizes(size, kind, three=False)
            h = 0.02
            part = ("plane", {"w": w, "h": d, "rx": -90, "y": 0.03, "color": c, "shadow": True, "side": "both"}, True)
        else:
            w, h = self.sizes(size, kind, three=False)
            d = w
            props = {"h": h, "y": h / 2, "seg": 20, "color": c, "shadow": True}
            props.update({"r": w / 2} if kind == "cylinder" else {"r": w / 2})
            part = (kind, props, True)
        t = Thing(self, kind, x, y, z, (w, h, d), [part])
        if kind == "plane":
            t.solid_ = False
        return t.native

    def box(self, x=MISSING, y=MISSING, z=MISSING, size=MISSING, color=MISSING):
        return self.primitive("box", [x, y, z, size, color], 1)

    def sphere(self, x=MISSING, y=MISSING, z=MISSING, size=MISSING, color=MISSING):
        return self.primitive("sphere", [x, y, z, size, color], 1)

    def cylinder(self, x=MISSING, y=MISSING, z=MISSING, size=MISSING, color=MISSING):
        return self.primitive("cylinder", [x, y, z, size, color], 1)

    def cone(self, x=MISSING, y=MISSING, z=MISSING, size=MISSING, color=MISSING):
        return self.primitive("cone", [x, y, z, size, color], 1)

    def plane(self, x=MISSING, y=MISSING, z=MISSING, size=MISSING, color=MISSING):
        return self.primitive("plane", [x, y, z, size, color], 4)

    def spawn(self, name, x=MISSING, y=MISSING, z=MISSING):
        n = self.rt.text(name).strip()
        low = n.lower()
        if x is MISSING:
            x = self.random_spot()
        x, y, z, _ = self.where([x, y, z], (), "spawn")
        if low.endswith(MODEL_FILES):
            url, _ = self.file_url(n, "model", MODEL_FILES)
            t = Thing(self, "model", x, y, z, (1, 1, 1), [("model", {"src": url}, True)])
            return t.native
        if low not in KIT:
            raise self.rt.error(f"tgame doesn't have a \"{n}\" to spawn. It has: {', '.join(KIT)}. "
                                "Or spawn a .glb model from your project folder.")
        size, body, parts, solid = kit(low)
        t = Thing(self, low, x, y, z, size, parts, body=body)
        t.solid_ = solid
        t.heading = random.uniform(0, 360) if low in ("tree", "pine", "rock", "bush", "flower") else 0.0
        t.push_rotation()
        return t.native

    # ---- the camera and the player
    def player(self, mode="first person"):
        m = self.rt.text(mode).strip().lower().replace("-", " ").replace("_", " ")
        if m in ("first", "fps", "1st person"):
            m = "first person"
        if m in ("third", "3rd person"):
            m = "third person"
        if m not in PLAYER_MODES:
            raise self.rt.error(f"The player can be \"first person\" or \"third person\", not \"{m}\".")
        if self.the_player is not None:
            raise self.rt.error("This world already has a player.")
        self.the_player = Player(self, m)
        self.cam_mode = "player"
        self.view.set(self.scene, clicklock=True)
        return self.the_player.native

    def camera_at(self, x=MISSING, y=MISSING, z=MISSING):
        x, y, z, _ = self.where([x, y, z], (), "camera_at")
        if self.cam_mode == "player":
            raise self.rt.error("The player has the camera. Use player:move_to to move the player instead.")
        self.cam_mode = "fixed"
        self.cam = [x, y, z]
        if self.cam_look is not None:
            self.aim(*self.cam_look)
        self.camera_dirty = True

    def look_at(self, x=MISSING, y=MISSING, z=MISSING):
        t = thing_of(x)
        if isinstance(t, (Thing, Player)):
            tx, ty, tz = t.x, t.y + t.height() * 0.5, t.z
        else:
            tx, ty, tz, _ = self.where([x, y, z], (), "look_at")
        self.cam_look = (tx, ty, tz)
        if self.cam_mode in ("fixed", "follow"):
            self.cam_mode = "fixed"
            self.aim(tx, ty, tz)
            self.camera_dirty = True

    def aim(self, tx, ty, tz):
        dx, dy, dz = tx - self.cam[0], ty - self.cam[1], tz - self.cam[2]
        flat = math.hypot(dx, dz)
        if flat > 1e-6 or abs(dy) > 1e-6:
            self.cam_yaw = math.degrees(math.atan2(dx, -dz))
            self.cam_pitch = math.degrees(math.atan2(dy, flat))

    def follow(self, target, distance=7, height=3):
        t = thing_of(target)
        if not isinstance(t, (Thing, Player)):
            raise self.rt.error(f"world:follow needs an object to follow, not {self.rt.what(target)}.")
        if self.cam_mode == "player":
            raise self.rt.error("The player has the camera, so the world can't follow something else.")
        self.cam_mode = "follow"
        self.cam_target = (t, self.num(distance, ":follow"), self.num(height, ":follow"))
        self.camera_dirty = True

    def orbit(self, x=MISSING, y=MISSING, z=MISSING):
        t = thing_of(x)
        if self.cam_mode == "player":
            raise self.rt.error("The player has the camera, so the world can't orbit.")
        if isinstance(t, (Thing, Player)):
            target = t
        else:
            target = tuple(self.where([x, y, z], (), "orbit")[:3])
        dist = max(4.0, math.dist(self.cam, self.point_of(target)))
        self.cam_mode = "orbit"
        self.orbit_state = {"target": target, "yaw": self.cam_yaw + 180, "elev": 25.0, "dist": dist}
        self.camera_dirty = True

    def point_of(self, target):
        if isinstance(target, (Thing, Player)):
            return target.x, target.y + target.height() * 0.5, target.z
        return target

    def looking_at(self, reach=None):
        if self.closed:
            return None
        hit = self.view.ask(self.scene, "pick")
        if not hit or hit.get("id") is None:
            return None
        if reach is not None and hit.get("dist") is not None and hit["dist"] > self.num(reach, ":looking_at"):
            return None
        t = self.thing_at(hit.get("path") or [hit["id"]])
        return t.native if t is not None and not getattr(t, "floor", False) else None

    def thing_at(self, path):
        for i in path:
            t = self.by_node.get(i)
            if t is not None and t.alive:
                return t
        return None

    def mouse_x(self):
        return tidy(self.view.mouse[0])

    def mouse_y(self):
        return tidy(self.view.mouse[1])

    def random_spot(self, radius=None):
        if radius is not None:
            r = max(0.5, self.num(radius, ":random_spot"))
        elif self.island_r:
            r = self.island_r * 0.85
        else:
            r = 30.0
        solid = [t for t in self.things if isinstance(t, Thing) and t.alive and t.solid_ and not getattr(t, "floor", False)]
        p = self.the_player
        best = None
        for _ in range(40):
            ang, dist = random.uniform(0, math.tau), r * math.sqrt(random.random())
            x, z = math.cos(ang) * dist, math.sin(ang) * dist
            if p is not None and math.hypot(x - p.x, z - p.z) < 3:
                continue
            if all(math.hypot(x - t.x, z - t.z) > 1.2 + max(t.dims[0], t.dims[2]) * 0.5 * max(t.k) for t in solid):
                best = (x, z)
                break
            best = best or (x, z)
        x, z = best or (0.0, 0.0)
        return [tidy(x), 0, tidy(z)]

    def clicked_at(self, e):
        if self.over_fn is not None:
            self.restart()
            return
        if self.is_paused:
            return
        t = self.thing_at(e.get("path") or [])
        if t is not None and t.click_fns:
            for fn in list(t.click_fns):
                self.fire(fn, t.native)
        if self.click_fns:
            pt = e.get("point")
            args = [tidy(v) for v in pt] if pt else [None, None, None]
            for fn in list(self.click_fns):
                self.fire(fn, *args)

    def lock_changed(self):
        if self.hint is not None:
            self.hint.hide() if (self.locked or self.fake_lock) else self.hint.show()

    def update(self, dt, real):
        p = self.the_player
        if p is not None:
            p.update(dt, real)
            return
        mode = self.cam_mode
        if mode == "follow":
            t, dist, height = self.cam_target
            if not t.alive:
                self.cam_mode = "fixed"
                return
            hd = math.radians(t.heading)
            fx, fz = math.sin(hd), -math.cos(hd)
            want = (t.x - fx * dist, t.y + height, t.z - fz * dist)
            k = 1 - math.exp(-8 * real) if self.last else 1
            self.cam = [c + (w - c) * k for c, w in zip(self.cam, want)]
            self.aim(t.x, t.y + t.height() * 0.6, t.z)
            self.camera_dirty = True
        elif mode == "orbit":
            o = self.orbit_state
            dx, dy = self.view.mouse_delta()
            if "mouse" in self.down:
                o["yaw"] += dx * 0.35
                o["elev"] = clamp(o["elev"] + dy * 0.3, -5, 85)
            if self.wheel:
                o["dist"] = clamp(o["dist"] * (1.0012 ** self.wheel), 2, 400)
            tx, ty, tz = self.point_of(o["target"])
            yaw, el = math.radians(o["yaw"]), math.radians(o["elev"])
            self.cam = [tx + math.sin(yaw) * math.cos(el) * o["dist"], ty + math.sin(el) * o["dist"],
                        tz - math.cos(yaw) * math.cos(el) * o["dist"]]
            self.aim(tx, ty, tz)
            self.camera_dirty = True
        if self.camera_dirty:
            self.push_camera()

    def push_camera(self):
        self.view.set(self.scene, cx=self.cam[0], cy=self.cam[1], cz=self.cam[2], yaw=-self.cam_yaw, pitch=self.cam_pitch)
        self.camera_dirty = False

    def get_hud(self):
        return self.hud().native

    def stats(self):
        out = super().stats()
        p = self.the_player
        out["camera"] = [round(v, 3) for v in self.cam] + [round(self.cam_yaw, 2), round(self.cam_pitch, 2)]
        if p is not None:
            out["player"] = [round(p.x, 3), round(p.y, 3), round(p.z, 3), round(p.heading, 2), round(p.pitch, 2)]
        return out


def kit(name):
    """A built-in low-poly model: (size, solid body, parts, solid). Parts are (type, engine props, main part?)."""
    rnd = random.random
    shade = lambda base, spread=0.08: _shade(base, (rnd() - 0.5) * 2 * spread)
    if name == "tree":
        leaf = shade("#4f9d3a")
        return ((2.2, 3.4, 2.2), (0.5, 3.4, 0.5), [
            ("cylinder", {"rt": 0.17, "rb": 0.26, "h": 1.7, "y": 0.85, "seg": 7, "color": "#7a5230", "flat": True, "shadow": True}, False),
            ("sphere", {"r": 0.95, "y": 2.2, "seg": 7, "color": leaf, "flat": True, "shadow": True}, True),
            ("sphere", {"r": 0.7, "x": 0.45, "y": 2.75, "z": 0.15, "seg": 6, "color": _shade(leaf, 0.06), "flat": True, "shadow": True}, True),
            ("sphere", {"r": 0.62, "x": -0.4, "y": 2.65, "z": -0.25, "seg": 6, "color": _shade(leaf, -0.05), "flat": True, "shadow": True}, True),
        ], True)
    if name == "pine":
        leaf = shade("#2f6b3a")
        return ((2.3, 3.9, 2.3), (0.5, 3.9, 0.5), [
            ("cylinder", {"rt": 0.14, "rb": 0.2, "h": 1.0, "y": 0.5, "seg": 6, "color": "#6b4428", "flat": True, "shadow": True}, False),
            ("cone", {"r": 1.15, "h": 1.5, "y": 1.6, "seg": 7, "color": leaf, "flat": True, "shadow": True}, True),
            ("cone", {"r": 0.9, "h": 1.3, "y": 2.45, "seg": 7, "color": _shade(leaf, 0.05), "flat": True, "shadow": True}, True),
            ("cone", {"r": 0.6, "h": 1.1, "y": 3.25, "seg": 7, "color": _shade(leaf, 0.1), "flat": True, "shadow": True}, True),
        ], True)
    if name == "rock":
        s = 0.8 + rnd() * 0.5
        return ((1.3 * s, 0.85 * s, 1.2 * s), None, [
            ("sphere", {"r": 0.65 * s, "y": 0.3 * s, "sy": 0.7, "seg": 5, "color": shade("#8e8e86", 0.1), "flat": True, "shadow": True}, True),
        ], True)
    if name == "bush":
        leaf = shade("#3f8a35")
        return ((1.5, 0.95, 1.5), None, [
            ("sphere", {"r": 0.55, "y": 0.45, "seg": 6, "color": leaf, "flat": True, "shadow": True}, True),
            ("sphere", {"r": 0.42, "x": 0.45, "y": 0.35, "z": 0.1, "seg": 6, "color": _shade(leaf, 0.06), "flat": True, "shadow": True}, True),
            ("sphere", {"r": 0.4, "x": -0.4, "y": 0.33, "z": -0.15, "seg": 6, "color": _shade(leaf, -0.05), "flat": True, "shadow": True}, True),
        ], False)
    if name == "flower":
        petal = random.choice(["#ff5d8f", "#ffd23f", "#ffffff", "#b388ff", "#ff8a3d"])
        return ((0.3, 0.5, 0.3), None, [
            ("cylinder", {"r": 0.025, "h": 0.42, "y": 0.21, "seg": 5, "color": "#3f8a35"}, False),
            ("sphere", {"r": 0.1, "y": 0.45, "seg": 6, "color": petal, "flat": True}, True),
        ], False)
    if name == "house":
        return ((3.2, 3.6, 3.2), (3.0, 2.2, 3.0), [
            ("box", {"w": 3, "h": 2.2, "d": 3, "y": 1.1, "color": "#e9dcc4", "flat": True, "shadow": True}, True),
            ("cone", {"r": 2.55, "h": 1.4, "y": 2.9, "ry": 45, "seg": 4, "color": "#b5483b", "flat": True, "shadow": True}, False),
            ("box", {"w": 0.7, "h": 1.25, "d": 0.06, "y": 0.62, "z": 1.51, "color": "#6b4428"}, False),
            ("box", {"w": 0.55, "h": 0.5, "d": 0.06, "x": -0.85, "y": 1.35, "z": 1.51, "color": "#9fd3ff", "emissive": "#1d3550"}, False),
            ("box", {"w": 0.55, "h": 0.5, "d": 0.06, "x": 0.85, "y": 1.35, "z": 1.51, "color": "#9fd3ff", "emissive": "#1d3550"}, False),
        ], True)
    if name == "hut":
        return ((2.8, 3.1, 2.8), (2.4, 1.7, 2.4), [
            ("cylinder", {"r": 1.25, "h": 1.7, "y": 0.85, "seg": 9, "color": "#a0703c", "flat": True, "shadow": True}, True),
            ("cone", {"r": 1.75, "h": 1.4, "y": 2.35, "seg": 9, "color": "#d9b45a", "flat": True, "shadow": True}, False),
            ("box", {"w": 0.6, "h": 1.1, "d": 0.08, "y": 0.55, "z": 1.22, "color": "#4a2f1a"}, False),
        ], True)
    if name == "sign":
        return ((1.2, 1.6, 0.2), (0.3, 1.6, 0.2), [
            ("cylinder", {"r": 0.06, "h": 1.2, "y": 0.6, "seg": 6, "color": "#6b4428"}, False),
            ("box", {"w": 1.2, "h": 0.6, "d": 0.08, "y": 1.25, "color": "#c08a4d", "flat": True, "shadow": True}, True),
        ], True)
    if name == "crate":
        return ((0.9, 0.9, 0.9), None, [
            ("box", {"w": 0.9, "h": 0.9, "d": 0.9, "y": 0.45, "color": "#b07a42", "flat": True, "shadow": True}, True),
            ("box", {"w": 0.94, "h": 0.12, "d": 0.94, "y": 0.06, "color": "#7a5230"}, False),
            ("box", {"w": 0.94, "h": 0.12, "d": 0.94, "y": 0.84, "color": "#7a5230"}, False),
        ], True)
    if name == "fence":
        return ((2.0, 1.0, 0.16), None, [
            ("box", {"w": 0.14, "h": 1.0, "d": 0.14, "x": -0.93, "y": 0.5, "color": "#8a6038"}, False),
            ("box", {"w": 0.14, "h": 1.0, "d": 0.14, "x": 0.93, "y": 0.5, "color": "#8a6038"}, False),
            ("box", {"w": 2.0, "h": 0.12, "d": 0.08, "y": 0.75, "color": "#b5895a", "shadow": True}, True),
            ("box", {"w": 2.0, "h": 0.12, "d": 0.08, "y": 0.4, "color": "#b5895a", "shadow": True}, True),
        ], True)
    if name == "coin":
        return ((0.7, 1.3, 0.12), None, [
            ("cylinder", {"r": 0.32, "h": 0.08, "y": 0.9, "rx": 90, "seg": 18, "color": "#f2c230", "emissive": "#5a4300",
                          "metal": 0.6, "rough": 0.35}, True),
        ], False)
    raise KeyError(name)


def held_parts(name):
    """A thing the player holds, built so its handle is at (0, 0, 0) and it points up."""
    handle = ("cylinder", {"r": 0.017, "h": 0.6, "y": 0.22, "seg": 6, "color": "#8a5a32"}, False)
    if name == "axe":
        return [handle, ("box", {"w": 0.15, "h": 0.1, "d": 0.025, "x": 0.055, "y": 0.47, "color": "#aeb5bf", "metal": 0.35,
                                 "rough": 0.5, "flat": True}, True)]
    if name == "pickaxe":
        return [handle, ("box", {"w": 0.4, "h": 0.045, "d": 0.04, "y": 0.5, "color": "#9aa1ab", "metal": 0.7, "rough": 0.35}, True)]
    if name == "sword":
        return [("box", {"w": 0.045, "h": 0.16, "d": 0.03, "y": 0.0, "color": "#5a3a22"}, False),
                ("box", {"w": 0.18, "h": 0.035, "d": 0.04, "y": 0.09, "color": "#c9a227"}, False),
                ("box", {"w": 0.055, "h": 0.55, "d": 0.015, "y": 0.38, "color": "#d7dde5", "metal": 0.8, "rough": 0.25}, True)]
    if name == "hammer":
        return [handle, ("box", {"w": 0.2, "h": 0.1, "d": 0.1, "y": 0.5, "color": "#7d838c", "metal": 0.6}, True)]
    return [("cylinder", {"r": 0.03, "h": 0.45, "y": 0.18, "seg": 6, "color": "#6b4428"}, False),
            ("sphere", {"r": 0.06, "y": 0.43, "seg": 8, "color": "#ffb347", "emissive": "#ff7a00", "mat": "basic"}, True)]


def _shade(hex_color, amount):
    """A color a little lighter (amount > 0) or darker."""
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    if amount >= 0:
        rgb = [round(c + (255 - c) * amount) for c in rgb]
    else:
        rgb = [round(c * (1 + amount)) for c in rgb]
    return "#" + "".join(f"{clamp(c, 0, 255):02x}" for c in rgb)


class Thing:
    """An object in a 3D world: a shape, a model from the kit, the ground, a light or something held."""
    NAMES = [
        ("x", "get_x"), ("y", "get_y"), ("z", "get_z"), ("spot", "spot"), ("move", "move"), ("move_to", "move_to"),
        ("glide", "glide"), ("forward", "forward"), ("turn", "turn"), ("turn_to", "turn_to"), ("angle", "angle"),
        ("spin", "spin"), ("look_at", "look_at"), ("speed", "speed"), ("shake", "shake"), ("fall", "fall"),
        ("fallen", "is_fallen"), ("grow", "grow"), ("regrow", "regrow"), ("swing", "swing"), ("size", "size"),
        ("scale", "set_scale"),
        ("color", "set_color"), ("glow", "glow"), ("hide", "hide"), ("show", "show"), ("remove", "remove"),
        ("solid", "solid"), ("touches", "touches"), ("distance", "distance"), ("label", "label"),
        ("clicked", "clicked"), ("set", "set"), ("get", "get"),
    ]

    def __init__(self, world, kind, x, y, z, size, parts, body=None, parent=None, pick=True, camera=False):
        self.world = self.game = world
        self.rt = world.rt
        self.kind = kind
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.heading = 0.0
        self.tilt = 0.0
        self.tilt_axis = (1.0, 0.0)
        self.pitch = 0.0
        self.k = [1.0, 1.0, 1.0]
        self.dims = size
        self.body = body  # the part that's solid, when it's smaller than the whole (a tree's trunk)
        self.solid_ = True
        self.alive = True
        self.hidden = False
        self.fallen = False
        self.vx = self.vy = self.vz = self.spin_speed = 0.0
        self.anims = []
        self.data = {}
        self.click_fns = []
        self.label_node = None
        self.label_text = ""
        v = world.view
        props = {"x": self.x, "y": self.y, "z": self.z}
        if camera:
            props["camera"] = True
        self.node = v.obj(parent or world.scene, "group", **props)
        world.by_node[int(self.node)] = self
        self.parts = []
        for type_, p, main in parts:
            p = dict(p)
            if not pick:
                p["pick"] = False
            node = v.obj(self.node, type_, **p)
            world.by_node[int(node)] = self
            self.parts.append((node, main))
        if not pick:
            v.set(self.node, pick=False)
        if parent is None and not camera:
            world.adopt(self)
        self.native = world.rt.native("object", methods(self, "object", self.NAMES, world.rt), self.show_text)
        self.native.tg = self

    def show_text(self, nested=False):
        return f"<{self.kind} at {tidy(self.x)}, {tidy(self.y)}, {tidy(self.z)}>"

    def num(self, v, what):
        return self.rt.number(v, what)

    def height(self):
        return self.dims[1] * self.k[1]

    # ---- sending changes
    def send(self, node, **props):
        """Send changes to one of its parts in the page. A removed object sends nothing: the page has let it go."""
        if self.alive:
            self.world.view.set(node, **props)

    def push(self):
        self.send(self.node, x=self.x, y=self.y, z=self.z)
        if self.label_node is not None:
            top = self.y + (0.9 if self.fallen else self.height() + 0.25)
            self.send(self.label_node, x=self.x, y=top, z=self.z)

    def push_rotation(self):
        rx, ry, rz = euler(self.heading, self.tilt_axis, self.tilt, self.pitch)
        self.send(self.node, rx=rx, ry=ry, rz=rz)

    def push_scale(self):
        self.send(self.node, sx=self.k[0], sy=self.k[1], sz=self.k[2])

    def busy(self):
        if self.vx or self.vy or self.vz or self.spin_speed or self.anims:
            self.world.movers.add(self)
        else:
            self.world.movers.discard(self)

    # ---- where it is
    def get_x(self):
        return tidy(self.x)

    def get_y(self):
        return tidy(self.y)

    def get_z(self):
        return tidy(self.z)

    def spot(self):
        return [tidy(self.x), tidy(self.y), tidy(self.z)]

    def move(self, dx, dy=0, dz=0):
        self.x += self.num(dx, ":move")
        self.y += self.num(dy, ":move")
        self.z += self.num(dz, ":move")
        self.push()
        return self.native

    def move_to(self, x, y=MISSING, z=MISSING):
        self.x, self.y, self.z, _ = self.world.where([x, y, z], (), "move_to")
        self.anims = [a for a in self.anims if a[0] != "glide"]
        self.push()
        return self.native

    def glide(self, x, y=MISSING, z=MISSING, seconds=MISSING):
        tx, ty, tz, (secs,) = self.world.where([x, y, z, seconds], (1.0,), "glide")
        secs = max(0.01, self.num(secs, ":glide"))
        self.anims = [a for a in self.anims if a[0] != "glide"]
        self.anims.append(["glide", 0.0, secs, (self.x, self.y, self.z), (tx, ty, tz)])
        self.busy()
        return self.native

    def forward(self, distance):
        d = self.num(distance, ":forward")
        h = math.radians(self.heading)
        self.x += math.sin(h) * d
        self.z -= math.cos(h) * d
        self.push()
        return self.native

    def turn(self, degrees):
        self.heading = (self.heading + self.num(degrees, ":turn")) % 360
        self.push_rotation()
        return self.native

    def turn_to(self, degrees):
        self.heading = self.num(degrees, ":turn_to") % 360
        self.push_rotation()
        return self.native

    def angle(self):
        return tidy(self.heading)

    def spin(self, degrees_per_second):
        self.spin_speed = self.num(degrees_per_second, ":spin")
        self.busy()
        return self.native

    def look_at(self, x, y=MISSING, z=MISSING):
        t = thing_of(x)
        if isinstance(t, (Thing, Player)):
            tx, tz = t.x, t.z
        else:
            tx, _, tz, _ = self.world.where([x, y, z], (), "look_at")
        if (tx, tz) != (self.x, self.z):
            self.heading = math.degrees(math.atan2(tx - self.x, -(tz - self.z))) % 360
            self.push_rotation()
        return self.native

    def speed(self, vx, vy=0, vz=0):
        self.vx, self.vy, self.vz = self.num(vx, ":speed"), self.num(vy, ":speed"), self.num(vz, ":speed")
        self.busy()
        return self.native

    # ---- animations
    def away_from_viewer(self):
        w = self.world
        vx, vz = (w.the_player.x, w.the_player.z) if w.the_player else (w.cam[0], w.cam[2])
        dx, dz = self.x - vx, self.z - vz
        d = math.hypot(dx, dz)
        if d < 1e-6:
            a = random.uniform(0, math.tau)
            return math.cos(a), math.sin(a)
        return dx / d, dz / d

    def shake(self):
        if self.fallen:
            return self.native
        dx, dz = self.away_from_viewer()
        self.anims = [a for a in self.anims if a[0] != "shake"]
        self.anims.append(["shake", 0.0, 0.45, (dz, -dx)])  # rock sideways to the viewer
        self.busy()
        return self.native

    def fall(self):
        if self.fallen or any(a[0] == "fall" for a in self.anims):
            return self.native
        dx, dz = self.away_from_viewer()
        self.anims = [a for a in self.anims if a[0] not in ("shake", "grow")]
        self.anims.append(["fall", 0.0, 1.1, (dz, -dx)])
        self.was_solid = self.solid_
        self.solid_ = False
        self.busy()
        return self.native

    def is_fallen(self):
        """True from :fall until it stands up again (:regrow)."""
        return self.fallen or any(a[0] == "fall" for a in self.anims)

    def grow(self):
        target = list(self.k)
        self.anims = [a for a in self.anims if a[0] != "grow"]
        self.anims.append(["grow", 0.0, 0.8, target])
        self.k = [0.05, 0.05, 0.05]
        self.push_scale()
        self.busy()
        return self.native

    def regrow(self, seconds=5):
        wait = max(0.0, self.num(seconds, ":regrow"))
        falling = next((a for a in self.anims if a[0] == "fall"), None)
        if falling:
            wait += max(0.0, falling[2] - falling[1])
        self.anims = [a for a in self.anims if a[0] != "regrow"]
        self.anims.append(["regrow", 0.0, max(0.01, wait)])
        self.busy()
        return self.native

    def swing(self):
        self.anims = [a for a in self.anims if a[0] != "swing"]
        self.anims.append(["swing", 0.0, 0.32])
        self.busy()
        return self.native

    def stand_up(self):
        self.fallen = False
        self.tilt = 0.0
        if getattr(self, "was_solid", None) is not None:
            self.solid_ = self.was_solid
        self.push_rotation()
        self.push()

    def tick(self, dt):
        moved = rotated = False
        if self.vx or self.vy or self.vz:
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.z += self.vz * dt
            moved = True
        if self.spin_speed:
            self.heading = (self.heading + self.spin_speed * dt) % 360
            rotated = True
        for a in list(self.anims):
            a[1] += dt
            t = min(1.0, a[1] / a[2])
            kind = a[0]
            if kind == "glide":
                e = ease(t)
                (x0, y0, z0), (x1, y1, z1) = a[3], a[4]
                self.x, self.y, self.z = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e, z0 + (z1 - z0) * e
                moved = True
            elif kind == "shake":
                self.tilt_axis = a[3]
                self.tilt = math.sin(a[1] * 42) * 7 * (1 - t)
                rotated = True
            elif kind == "fall":
                self.tilt_axis = a[3]
                self.tilt = 88 * t * t
                rotated = True
                if t >= 1:
                    self.fallen = True
                    moved = True  # the label goes down too
            elif kind == "grow":
                e = 1 - (1 - t) ** 3
                self.k = [0.05 + (k - 0.05) * e for k in a[3]]
                self.push_scale()
                moved = True
            elif kind == "swing":
                self.pitch = -75 * math.sin(math.pi * t)
                rotated = True
            elif kind == "regrow" and t >= 1:
                self.anims.remove(a)
                self.stand_up()
                self.grow()
                continue
            if t >= 1:
                self.anims.remove(a)
                if kind == "shake":
                    self.tilt = 0.0
                elif kind == "swing":
                    self.pitch = 0.0
        if moved:
            self.push()
        if rotated:
            self.push_rotation()
        self.busy()

    # ---- how it looks
    def size(self, w, h=MISSING, d=MISSING):
        wv = self.rt.plain(w)
        if isinstance(wv, list):
            w, h, d = (wv + [MISSING, MISSING])[:3]
        w = self.num(w, ":size")
        h = w if h is MISSING else self.num(h, ":size")
        d = w if d is MISSING else self.num(d, ":size")
        bw, bh, bd = self.size_base()
        self.k = [w / bw if bw else 1, h / bh if bh else 1, d / bd if bd else 1]
        self.push_scale()
        self.push()
        return self.native

    def size_base(self):
        return self.dims

    def set_scale(self, n):
        n = self.num(n, ":scale")
        self.k = [n, n, n]
        self.push_scale()
        self.push()
        return self.native

    def set_color(self, color):
        c = self.world.color(color)
        for node, main in self.parts:
            if main:
                self.send(node, color=c)
        return self.native

    def glow(self, color="white"):
        name = self.rt.text(color).strip().lower()
        c = "#000000" if name in ("none", "off", "") else self.world.color(color)
        for node, main in self.parts:
            if main:
                self.send(node, emissive=c)
        return self.native

    def hide(self):
        self.hidden = True
        self.send(self.node, visible=False)
        if self.label_node is not None:
            self.send(self.label_node, visible=False)
        return self.native

    def show(self):
        self.hidden = False
        self.send(self.node, visible=True)
        if self.label_node is not None and self.label_text:
            self.send(self.label_node, visible=True)
        return self.native

    def remove(self):
        if not self.alive:
            return
        self.alive = False
        w = self.world
        w.view.remove(self.node)
        if self.label_node is not None:
            w.view.remove(self.label_node)
        w.movers.discard(self)
        w.things.pop(self, None)
        for node in [self.node] + [n for n, _ in self.parts]:
            w.by_node.pop(int(node), None)

    def solid(self, on=True):
        self.solid_ = self.rt.truthy(on)
        return self.native

    # ---- other objects
    def box3(self, body=False):
        w, h, d = (self.body or self.dims) if body else self.dims
        kx, ky, kz = self.k
        if self.fallen:
            return (self.x - 0.01, self.y, self.z - 0.01, self.x + 0.01, self.y + 0.01, self.z + 0.01)
        hw, hd = w * kx / 2, d * kz / 2
        if 45 < self.heading % 180 < 135:
            hw, hd = hd, hw
        return (self.x - hw, self.y, self.z - hd, self.x + hw, self.y + h * ky, self.z + hd)

    def touches(self, other):
        v = self.rt.plain(other)
        g = thing_of(v)
        if isinstance(g, Group):
            v = g.items
        if isinstance(v, list):
            for item in v:
                t = thing_of(item)
                if isinstance(t, (Thing, Player)) and t is not self and t.alive and not t.hidden and boxes_touch(self.box3(), t.box3()):
                    return item
            return None
        if not isinstance(g, (Thing, Player)):
            raise self.rt.error(f"object:touches needs another object, the player, a list or a group, not {self.rt.what(v)}.")
        return bool(self.alive and not self.hidden and g is not self and g.alive and not g.hidden
                    and boxes_touch(self.box3(), g.box3()))

    def distance(self, other, y=MISSING, z=MISSING):
        t = thing_of(other)
        if isinstance(t, (Thing, Player)):
            tx, ty, tz = t.x, t.y, t.z
        else:
            tx, ty, tz, _ = self.world.where([other, y, z], (), "distance")
        return tidy(math.dist((self.x, self.y, self.z), (tx, ty, tz)))

    def label(self, text):
        t = self.rt.text(text)
        self.label_text = t
        w = self.world
        if self.label_node is None:
            if not t or not self.alive:
                return self.native
            self.label_node = w.view.obj(w.scene, "label", text=t)
            self.push()
        else:
            self.send(self.label_node, text=t)
        self.send(self.label_node, visible=bool(t) and not self.hidden)
        return self.native

    def clicked(self, fn):
        self.click_fns.append(self.world.lib.check_fn(fn, ":clicked"))
        return self.native

    def set(self, name, value):
        n = self.rt.plain(name)
        if not isinstance(n, str):
            raise self.rt.error(f"object:set(name, value) needs the name as text, like \"hp\", not {self.rt.what(n)}.")
        self.data[n] = self.rt.plain(value)
        return self.native

    def get(self, name):
        return self.data.get(self.rt.plain(name))


def boxes_touch(a, b):
    return a[0] < b[3] and b[0] < a[3] and a[1] < b[4] and b[1] < a[4] and a[2] < b[5] and b[2] < a[5]


class Player:
    """The one you play as: the camera in first person, or a little figure the camera follows in third person.

    WASD or the arrow keys walk (Shift runs), Space jumps, and the mouse looks around once the game is clicked
    (Escape lets go of the mouse). Solid objects block the way, and the player can stand on top of them."""
    NAMES = [
        ("x", "get_x"), ("y", "get_y"), ("z", "get_z"), ("spot", "spot"), ("move_to", "move_to"),
        ("turn_to", "turn_to"), ("angle", "angle"), ("walk_speed", "walk_speed"), ("jump_height", "jump_height"),
        ("jump", "jump"), ("hold", "hold"), ("looking_at", "looking_at"), ("touches", "touches"),
        ("distance", "distance"), ("hide", "hide"), ("show", "show"),
    ]
    RADIUS = 0.32
    TALL = 1.75
    EYE = 1.6

    def __init__(self, world, mode):
        self.world = world
        self.rt = world.rt if world else None
        self.mode = mode
        self.x = self.y = self.z = 0.0
        self.heading = 0.0
        self.pitch = 0.0
        self.vy = 0.0
        self.on_ground = True
        self.speed = 5.0
        self.jump_v = math.sqrt(2 * GRAVITY * 1.2)
        self.alive = True
        self.hidden = False
        self.held = None
        self.body = None
        if world is None:
            return
        self.cam_pos = None
        self.native = world.rt.native("player", methods(self, "player", self.NAMES, world.rt),
                                      lambda nested=False: f"<player at {tidy(self.x)}, {tidy(self.y)}, {tidy(self.z)}>")
        self.native.tg = self
        if mode == "third person":
            self.body = Thing(world, "player", 0, 0, 0, (0.6, self.TALL, 0.6), [
                ("capsule", {"r": 0.3, "h": 0.75, "y": 0.72, "seg": 10, "color": "#3574f0", "flat": True, "shadow": True}, True),
                ("sphere", {"r": 0.22, "y": 1.48, "seg": 12, "color": "#f1c9a5", "shadow": True}, False),
                ("box", {"w": 0.28, "h": 0.08, "d": 0.06, "y": 1.52, "z": -0.2, "color": "#2b2b2b"}, False),
            ], pick=False)
            self.body.solid_ = False
            world.things.pop(self.body, None)
        hud = world.hud()
        if mode == "first person":
            world.crosshair = hud.make("circle", world.W / 2, world.H / 2, {"r": 3.5, "color": "#ffffff", "stroke": "#000000",
                                                                            "lw": 1.5, "alpha": 0.85, "z": 5e5}, own=False)
        world.hint = hud.make("text", world.W / 2, world.H - 26, {"text": "Click the game to look around with the mouse (Esc lets go)",
                                                                  "size": 15, "bold": False, "color": "#ffffff", "alpha": 0.8,
                                                                  "ax": 0.5, "ay": 0.5, "z": 5e5}, own=False)
        if world.autopilot:
            world.hint.hide()
        self.place_camera(1)

    def height(self):
        return self.TALL

    def box3(self):
        r = self.RADIUS
        return (self.x - r, self.y, self.z - r, self.x + r, self.y + self.TALL, self.z + r)

    # ---- what Tuff can ask
    def get_x(self):
        return tidy(self.x)

    def get_y(self):
        return tidy(self.y)

    def get_z(self):
        return tidy(self.z)

    def spot(self):
        return [tidy(self.x), tidy(self.y), tidy(self.z)]

    def move_to(self, x, y=MISSING, z=MISSING):
        self.x, self.y, self.z, _ = self.world.where([x, y, z], (), "move_to")
        self.vy = 0.0
        self.place_camera(1)
        return self.native

    def turn_to(self, degrees):
        self.heading = self.rt.number(degrees, ":turn_to") % 360
        self.place_camera(1)
        return self.native

    def angle(self):
        return tidy(self.heading)

    def walk_speed(self, speed):
        self.speed = max(0.0, self.rt.number(speed, ":walk_speed"))
        return self.native

    def jump_height(self, height):
        self.jump_v = math.sqrt(2 * GRAVITY * max(0.0, self.rt.number(height, ":jump_height")))
        return self.native

    def jump(self):
        if self.on_ground:
            self.vy = self.jump_v
            self.on_ground = False
        return self.native

    def hold(self, item="axe"):
        name = self.rt.text(item).strip().lower()
        if name not in HOLDABLE:
            raise self.rt.error(f"The player can hold: {', '.join(HOLDABLE)}. Not \"{name}\".")
        if self.held is not None:
            self.held.remove()
        w = self.world
        if self.mode == "first person":
            # Low on the right of the view, leaning in a little, like it's held in the right hand.
            self.held = Thing(w, name, 0.38, -0.5, -0.72, (0.3, 0.7, 0.1), held_parts(name), pick=False, camera=True)
            self.held.heading = -15
            self.held.tilt, self.held.tilt_axis = 18, (0.0, 1.0)
        else:
            self.held = Thing(w, name, 0.38, 0.75, -0.1, (0.3, 0.8, 0.1), held_parts(name), parent=self.body.node, pick=False)
        self.held.solid_ = False
        self.held.push_rotation()
        return self.held.native

    def looking_at(self, reach=None):
        return self.world.looking_at(reach)

    def touches(self, other):
        v = self.rt.plain(other)
        g = thing_of(v)
        if isinstance(g, Group):
            v = g.items
        if isinstance(v, list):
            for item in v:
                t = thing_of(item)
                if isinstance(t, Thing) and t.alive and not t.hidden and boxes_touch(self.box3(), t.box3()):
                    return item
            return None
        if not isinstance(g, Thing):
            raise self.rt.error(f"player:touches needs an object, a list or a group, not {self.rt.what(v)}.")
        return bool(g.alive and not g.hidden and boxes_touch(self.box3(), g.box3()))

    def distance(self, other, y=MISSING, z=MISSING):
        t = thing_of(other)
        if isinstance(t, Thing):
            tx, ty, tz = t.x, t.y, t.z
        else:
            tx, ty, tz, _ = self.world.where([other, y, z], (), "distance")
        return tidy(math.dist((self.x, self.y, self.z), (tx, ty, tz)))

    def hide(self):
        self.hidden = True
        if self.body is not None:
            self.body.hide()
        return self.native

    def show(self):
        self.hidden = False
        if self.body is not None:
            self.body.show()
        return self.native

    # ---- walking, every frame
    def solids(self):
        return [t for t in self.world.things if isinstance(t, Thing) and t.alive and t.solid_ and not t.hidden]

    def blocked(self, x, z, y, solids):
        r = self.RADIUS
        for t in solids:
            b = t.box3(body=True)
            if x + r > b[0] and x - r < b[3] and z + r > b[2] and z - r < b[5] and y + self.TALL > b[1] and y + 0.3 < b[4]:
                return True
        return False

    def floor_at(self, x, z, y, solids):
        """The highest floor under the player's feet: the ground (0), or the top of something solid."""
        best = 0.0
        r = self.RADIUS * 0.8
        for t in solids:
            b = t.box3(body=True)
            if x + r > b[0] and x - r < b[3] and z + r > b[2] and z - r < b[5] and b[4] <= y + 0.35:
                best = max(best, b[4])
        return best

    def update(self, dt, real):
        w = self.world
        look = w.locked or w.fake_lock
        mdx, mdy = w.view.mouse_delta()
        if look and not w.is_paused:
            self.heading = (self.heading + mdx * 0.15) % 360
            if self.mode == "first person":
                self.pitch = clamp(self.pitch - mdy * 0.15, -85, 85)
            else:
                self.pitch = clamp(self.pitch - mdy * 0.1, -40, 30)
        if dt:
            self.walk(dt)
        self.place_camera(real)

    def walk(self, dt):
        w = self.world
        down = w.down
        turn = (("right" in down) - ("left" in down))
        fwd = (("w" in down or "up" in down) - ("s" in down or "down" in down))
        side = ("d" in down) - ("a" in down)
        if self.mode == "third person" and not (w.locked or w.fake_lock):
            turn += side  # A and D turn too, until the mouse is locked
            side = 0
        if turn:
            self.heading = (self.heading + turn * 130 * dt) % 360
        h = math.radians(self.heading)
        fx, fz = math.sin(h), -math.cos(h)
        rx, rz = math.cos(h), math.sin(h)
        mx, mz = fx * fwd + rx * side, fz * fwd + rz * side
        n = math.hypot(mx, mz)
        solids = self.solids()
        if n:
            sp = self.speed * (1.7 if "shift" in down else 1.0) * dt / n
            nx, nz = self.x + mx * sp, self.z + mz * sp
            if not self.blocked(nx, self.z, self.y, solids):
                self.x = nx
            elif self.try_step(nx, self.z, solids):
                pass
            if not self.blocked(self.x, nz, self.y, solids):
                self.z = nz
            else:
                self.try_step(self.x, nz, solids)
            self.keep_inside()
        if "space" in w.just and self.on_ground:
            self.vy = self.jump_v
            self.on_ground = False
        self.vy -= GRAVITY * dt
        ny = self.y + self.vy * dt
        floor = self.floor_at(self.x, self.z, max(self.y, ny), solids)
        if ny <= floor:
            ny, self.vy, self.on_ground = floor, 0.0, True
        else:
            self.on_ground = False
            if self.vy > 0 and self.blocked(self.x, self.z, ny, solids):
                ny, self.vy = self.y, 0.0  # bumped a ceiling
        self.y = ny
        if self.body is not None:
            self.body.x, self.body.y, self.body.z, self.body.heading = self.x, self.y, self.z, self.heading
            self.body.push()
            self.body.push_rotation()

    def try_step(self, x, z, solids):
        """Walk up onto something low (a step, a crate) instead of stopping."""
        for t in solids:
            b = t.box3(body=True)
            r = self.RADIUS
            if x + r > b[0] and x - r < b[3] and z + r > b[2] and z - r < b[5] and 0 < b[4] - self.y <= 0.45:
                if not self.blocked(x, z, b[4], solids):
                    self.x, self.z, self.y = x, z, b[4]
                    return True
        return False

    def keep_inside(self):
        w = self.world
        edge = (w.island_r + 2.5) if w.island_r else 300.0
        d = math.hypot(self.x, self.z)
        if d > edge:
            self.x, self.z = self.x * edge / d, self.z * edge / d

    def place_camera(self, real):
        w = self.world
        if self.mode == "first person":
            w.cam = [self.x, self.y + self.EYE, self.z]
            w.cam_yaw, w.cam_pitch = self.heading, self.pitch
        else:
            h = math.radians(self.heading)
            back, up = 6.0, 2.6 - self.pitch * 0.06
            want = [self.x - math.sin(h) * back, self.y + up, self.z + math.cos(h) * back]
            k = 1 - math.exp(-10 * real) if self.cam_pos is not None else 1
            self.cam_pos = want if self.cam_pos is None else [c + (t - c) * k for c, t in zip(self.cam_pos, want)]
            w.cam = list(self.cam_pos)
            w.aim(self.x, self.y + 1.3, self.z)
        w.push_camera()


# ---------------------------------------------------------------- the autopilot (tests)

class Autopilot:
    """Plays a game by itself for the tests: TUFF_TGAME_AUTOPILOT names a JSON file of timed steps.

    {"on_top": true, "out": "folder", "timeout": 20, "steps": [
        {"at": 0.5, "key": "right"}, {"at": 1, "hold": "w", "for": 0.8}, {"at": 1.2, "keydown": "a"}, {"keyup": ...},
        {"at": 2, "click": [x, y]} (window pixels), {"click_world": [x, y]} (a 2D game's own units),
        {"click_center": true}, {"look": [dx, dy]} (mouse movement), {"lock": true} (act as if the mouse were locked),
        {"call": "tuff_function"}, {"say": "text"}, {"mark": true} (start measuring), {"shot": "name.png"},
        {"dump": "name.json"} (add "memory": true to count the sprites and objects still in memory), {"close": true}]}

    Keys, clicks and mouse movement are made in the page, so they travel the same way real ones do.
    """
    ENV = "TUFF_TGAME_AUTOPILOT"

    @classmethod
    def load(cls, game):
        path = os.environ.get(cls.ENV)
        if not path:
            return None
        with open(path, encoding="utf-8") as f:
            return cls(game, json.load(f), os.path.dirname(os.path.abspath(path)))

    def __init__(self, game, plan, here):
        self.game = game
        self.on_top = plan.get("on_top", True)
        self.out = plan.get("out") or here
        os.makedirs(self.out, exist_ok=True)
        self.steps = sorted(plan.get("steps", []), key=lambda s: s.get("at", 0))
        self.timeout = plan.get("timeout", 60)
        self.marked = None
        self.t0 = None
        if "seed" in plan:
            random.seed(plan["seed"])

    def tick(self, now):
        """Run the steps that are due. Their times count from the game's first frame."""
        g = self.game
        if self.t0 is None:
            self.t0 = now
        t = now - self.t0
        if t > self.timeout:
            print(f"[autopilot] timed out after {self.timeout} s", flush=True)
            g.close()
            return
        while self.steps and self.steps[0].get("at", 0) <= t:
            step = self.steps.pop(0)
            try:
                self.run(step, t)
            except Exception as exc:  # a test step must never stop the game
                print(f"[autopilot] step {step} failed: {exc}", flush=True)
            if g.closed:
                return

    def key_js(self, kind, name):
        key, code = KEY_EVENTS.get(name, (name, f"Key{name.upper()}" if len(name) == 1 and name.isalpha()
                                          else f"Digit{name}" if len(name) == 1 and name.isdigit() else name))
        return f"window.dispatchEvent(new KeyboardEvent({json.dumps(kind)}, {{key: {json.dumps(key)}, code: {json.dumps(code)}, bubbles: true}}));"

    def click_js(self, x, y):
        return (f"const x = {x}, y = {y}; const el = document.elementFromPoint(x, y) || document.body;"
                "const o = {clientX: x, clientY: y, bubbles: true, button: 0};"
                "el.dispatchEvent(new PointerEvent('pointerdown', o)); el.dispatchEvent(new PointerEvent('pointerup', o));"
                "el.dispatchEvent(new MouseEvent('click', o));")

    def run(self, step, t):
        g = self.game
        v = g.view
        if "key" in step:
            v.js(self.key_js("keydown", step["key"]))
            self.steps.insert(0, {"at": t + 0.05, "keyup": step["key"]})
        if "keydown" in step:
            v.js(self.key_js("keydown", step["keydown"]))
        if "keyup" in step:
            v.js(self.key_js("keyup", step["keyup"]))
        if "hold" in step:
            v.js(self.key_js("keydown", step["hold"]))
            self.steps.append({"at": t + step.get("for", 0.5), "keyup": step["hold"]})
            self.steps.sort(key=lambda s: s.get("at", 0))
        if "click" in step:
            v.js(self.click_js(*step["click"]))
        if "click_world" in step:
            v.js(self.click_js(*g.to_window(*step["click_world"])))
        if step.get("click_center"):
            w, h = v.size
            v.js(self.click_js(w / 2, h / 2))
        if "press_mouse" in step or "release_mouse" in step:
            kind = "pointerdown" if "press_mouse" in step else "pointerup"
            w, h = v.size
            v.js(f"const el = document.elementFromPoint({w / 2}, {h / 2}) || document.body;"
                 f"el.dispatchEvent(new PointerEvent('{kind}', {{clientX: {w / 2}, clientY: {h / 2}, bubbles: true, button: 0}}));")
        if "look" in step:
            dx, dy = step["look"]
            w, h = v.size
            v.js(f"window.dispatchEvent(new PointerEvent('pointermove', {{clientX: {w / 2}, clientY: {h / 2}, movementX: {dx}, movementY: {dy}, bubbles: true}}));")
        if "lock" in step:
            g.fake_lock = bool(step["lock"])
            g.lock_changed()
        if "call" in step:
            fn = g.rt.interp.globals.vars.get(step["call"])
            if fn is not None:
                g.fire(fn)
        if "tuff" in step:  # a line of Tuff, run at the top of the program (like moving the food somewhere known)
            interp = g.rt.interp
            tuff = sys.modules[type(interp).__module__]
            try:
                interp.run_block(tuff.Parser(tuff.tokenize(step["tuff"])).program(), interp.globals)
            except tuff.TuffError as err:
                print(f"[autopilot] {step['tuff']}: {err.msg}", flush=True)
        if "say" in step:
            print(step["say"], flush=True)
        if step.get("mark"):
            g.work.clear()
            g.engine.clear()
            self.marked = time.perf_counter()
            self.marked_frames = g.frames
            v.page_stats(reset=True)
        if "shot" in step:
            data = v.ask(0, "snapshot", timeout=10)
            if data and data.startswith("data:image/png;base64,"):
                with open(os.path.join(self.out, step["shot"]), "wb") as f:
                    f.write(base64.b64decode(data.split(",", 1)[1]))
        if "dump" in step:
            with open(os.path.join(self.out, step["dump"]), "w", encoding="utf-8") as f:
                json.dump(self.state(step.get("memory")), f, indent=2)
        if step.get("close"):
            g.close()

    def state(self, memory=False):
        g = self.game
        out = g.stats()
        out["kept"] = len(g.things)  # sprites and objects tgame still holds (removed ones shouldn't be here)
        out["view_nodes"] = len(g.view._parents)  # objects the window engine still knows about
        if memory:  # sprites and objects still in Python's memory, after a garbage collection (slow: tests only)
            import gc
            gc.collect()
            out["in_memory"] = sum(1 for o in gc.get_objects() if isinstance(o, (Sprite, Thing)))
        if self.marked is not None:
            secs = time.perf_counter() - self.marked
            out["measured_seconds"] = round(secs, 2)
            out["python_fps"] = round((g.frames - self.marked_frames) / secs, 1) if secs > 0 else 0
        try:
            out["page"] = g.view.page_stats()
        except Exception as exc:
            out["page"] = {"error": str(exc)}
        try:
            out["sound"] = g.view.ask(0, "sound_state")
        except Exception:
            pass
        out["time"] = g.time()
        out["blurs"] = g.blurs  # times the window lost focus (that lets go of held keys)
        out["paused"] = g.is_paused
        out["locked"] = g.locked
        out["things"] = len([t for t in g.things if t.alive])
        out["texts"] = [s.words for s in g.things if isinstance(s, Sprite) and s.alive and s.shape == "text"]
        if g.hud_layer is not None:
            out["hud_texts"] = [s.words for s in g.hud_layer.sprites if s.alive and s.shape == "text" and not s.hidden]
        out["labels"] = [t.label_text for t in g.things if isinstance(t, Thing) and t.alive and t.label_text]
        out["fallen"] = len([t for t in g.things if isinstance(t, Thing) and t.alive and t.fallen])
        out["sprites"] = [[s.shape, round(s.x, 2), round(s.y, 2)] for s in g.things if isinstance(s, Sprite) and s.alive][:400]
        out["objects"] = [[t.kind, round(t.x, 2), round(t.y, 2), round(t.z, 2), t.fallen, t.data]
                          for t in g.things if isinstance(t, Thing) and t.alive][:400]
        return out


# ---------------------------------------------------------------- for tuff.py --check

# What each method gives back, so the checker knows what a variable holds ("$number", "$text", "$bool",
# "$list", or another tgame kind). Left out: it depends (like :touches, :get or :looking_at).
_SETTERS = ("move", "move_to", "glide", "forward", "turn", "turn_to", "spin", "point_at", "speed", "on_edge", "size",
            "scale", "color", "layer", "flip", "align", "hide", "show", "set", "clicked", "shake", "look_at", "fall",
            "grow", "regrow", "swing", "glow", "solid", "label")
GIVES = {
    "game": {"open": "$bool", "frame": "$number", "held": "$bool", "pressed": "$bool", "mouse_x": "$number",
             "mouse_y": "$number", "time": "$number", "fps": "$number", "paused": "$bool", "width": "$number",
             "height": "$number", "random_spot": "$list", "group": "group", "hud": "hud", "box": "sprite",
             "circle": "sprite", "line": "sprite", "text": "sprite", "image": "sprite"},
    "world": {"open": "$bool", "frame": "$number", "held": "$bool", "pressed": "$bool", "mouse_x": "$number",
              "mouse_y": "$number", "time": "$number", "fps": "$number", "paused": "$bool", "width": "$number",
              "height": "$number", "random_spot": "$list", "group": "group", "hud": "hud", "light": "object",
              "ground": "object", "island": "object", "box": "object", "sphere": "object", "cylinder": "object",
              "cone": "object", "plane": "object", "spawn": "object", "player": "player"},
    "sprite": {"x": "$number", "y": "$number", "spot": "$list", "angle": "$number", "on_screen": "$bool",
               "distance": "$number", "value": "$text", **{m: "sprite" for m in _SETTERS}},
    "object": {"x": "$number", "y": "$number", "z": "$number", "spot": "$list", "angle": "$number",
               "distance": "$number", "fallen": "$bool", **{m: "object" for m in _SETTERS}},
    "player": {"x": "$number", "y": "$number", "z": "$number", "spot": "$list", "angle": "$number",
               "distance": "$number", "hold": "object", "move_to": "player", "turn_to": "player",
               "walk_speed": "player", "jump_height": "player", "jump": "player", "hide": "player", "show": "player"},
    "hud": {"text": "sprite", "box": "sprite", "circle": "sprite", "line": "sprite", "image": "sprite"},
    "group": {"items": "$list", "count": "$number", "has": "$bool", "add": "group", "remove": "group",
              "move": "group", "hide": "group", "show": "group", "clear": "group", "color": "group"},
}
# Events: method -> (where the function goes, how many inputs the function is given, what they are).
_EVENTS = {"every_frame": (0, 1, "1 input (the seconds since the last frame)"), "on_key": (1, 1, "1 input (the key's name)"),
           "after": (1, 0, "no inputs"), "every": (1, 0, "no inputs"), "game_over": (1, 0, "no inputs")}
HANDLERS = {
    "game": {**_EVENTS, "clicked": (0, 2, "2 inputs (x and y)")},
    "world": {**_EVENTS, "clicked": (0, 3, "3 inputs (the x, y and z it clicked)")},
    "sprite": {"clicked": (0, 1, "1 input (the sprite)")},
    "object": {"clicked": (0, 1, "1 input (the object)")},
}
# Inputs written as text that have to be one of a set of names: (kind, method) -> {input position: what}.
_MAKERS_2D = {"box": {4: "color"}, "circle": {3: "color"}, "line": {4: "color"}, "text": {4: "color"}, "image": {0: "image"}}
VALUES = {
    **{(k, m): v for k in ("game", "hud") for m, v in _MAKERS_2D.items()},
    **{("world", m): {i: "color" for i in range(1, 5)} for m in ("box", "sphere", "cylinder", "cone", "plane")},
    ("game", "background"): {0: "color"}, ("world", "background"): {0: "color"}, ("world", "ground"): {0: "color"},
    ("world", "light"): {1: "color", 3: "color"}, ("world", "sky"): {0: "sky"}, ("world", "spawn"): {0: "spawn"},
    ("world", "player"): {0: "player"}, ("sprite", "color"): {0: "color"}, ("object", "color"): {0: "color"},
    ("object", "glow"): {0: "glow"}, ("group", "color"): {0: "color"}, ("sprite", "on_edge"): {0: "edge"},
    ("sprite", "align"): {0: "align"}, ("player", "hold"): {0: "hold"},
    **{(k, m): {0: "key"} for k in ("game", "world") for m in ("held", "pressed")},
    **{(k, "on_key"): {0: "anykey"} for k in ("game", "world")},
    **{(k, "sound"): {0: "sound"} for k in ("game", "world")},
    **{(k, "music"): {0: "music"} for k in ("game", "world")},
}


def check_value(kind, method, index, value, base_dir=None):
    """For tuff.py --check: what's wrong with this text input (a problem message), or None if it's fine."""
    what = VALUES.get((kind, method), {}).get(index)
    if what is None or not isinstance(value, str):
        return None
    low = value.strip().lower()

    def file_problem(exts, word):
        if not low.endswith(exts):
            return f"'{value}' isn't a {word} file tgame can use. Use {', '.join(exts[:-1])} or {exts[-1]}."
        if base_dir and not os.path.isabs(value) and not os.path.isfile(os.path.join(base_dir, value)):
            return f"Couldn't find the {word} '{value}'. Put it in your project folder, next to your .tuf file."
        return None

    if what in ("color", "glow"):
        if what == "glow" and low in ("none", "off", ""):
            return None
        ok = low in COLORS or (low[:1] == "#" and len(low) in (4, 7) and all(c in "0123456789abcdef" for c in low[1:]))
        return None if ok else f"'{value}' isn't a color tgame knows. Try {COLOR_HELP}, or a hex code like \"#ff8800\"."
    if what == "sky":
        return None if low in SKIES else f"The sky can be {', '.join(SKIES)}, not \"{value}\"."
    if what == "edge":
        return None if low in EDGE_MODES else ":on_edge can be \"bounce\", \"wrap\", \"stop\" (stay on screen) or \"none\"."
    if what == "align":
        return None if low in ALIGNS else ":align can be \"left\", \"center\" or \"right\"."
    if what == "player":
        m = low.replace("-", " ").replace("_", " ")
        ok = m in PLAYER_MODES or m in ("first", "third", "fps", "1st person", "3rd person")
        return None if ok else f"The player can be \"first person\" or \"third person\", not \"{value}\"."
    if what == "hold":
        return None if low in HOLDABLE else f"The player can hold: {', '.join(HOLDABLE)}. Not \"{value}\"."
    if what == "spawn":
        if low.endswith(MODEL_FILES):
            return file_problem(MODEL_FILES, "model")
        return None if low in KIT else f"tgame doesn't have a \"{value}\" to spawn. It has: {', '.join(KIT)}."
    if what in ("key", "anykey"):
        if what == "anykey" and low == "any":
            return None
        return None if norm_key(value) else (f"'{value}' isn't a key tgame knows. Try a letter, a number, space, enter, "
                                             "escape, shift, up, down, left, right, or \"mouse\".")
    if what == "sound":
        if low in SOUNDS:
            return None
        if low.endswith(SOUND_FILES):
            return file_problem(SOUND_FILES, "sound")
        return f"'{value}' isn't one of tgame's sounds ({', '.join(SOUNDS)}). Or play a .wav, .mp3 or .ogg file from your project folder."
    if what == "music":
        return file_problem(SOUND_FILES, "music")
    if what == "image":
        return file_problem(IMAGE_FILES, "picture")
    return None


def tables():
    """For tuff.py --check, without opening a window: tgame's functions, every kind's methods, what they give
    back, the events, the hints for guessed names, and check_value for text inputs."""

    class FakeRt:
        def builtin(self, name, fn):
            return fn

    def probe(cls):
        return object.__new__(cls)

    kinds = {}
    for kind, cls in (("game", Game2D), ("world", World3D), ("sprite", Sprite), ("object", Thing),
                      ("player", Player), ("hud", Hud), ("group", Group)):
        obj = probe(cls)
        kinds[kind] = {name: getattr(obj, attr) for name, attr in cls.NAMES}
    return {"lib": make_library(FakeRt()), "kinds": kinds, "gives": GIVES, "handlers": HANDLERS, "hints": HINTS,
            "check": check_value}
