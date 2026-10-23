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
import re
import struct
import sys
import time

import tuff_atgui as atgui  # a game's menus are atgui's own widgets (GameUI, near the end)

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
KIT = ("tree", "pine", "rock", "bush", "flower", "house", "hut", "sign", "crate", "fence", "coin", "chest", "person")
# How a model from the kit can move by itself (thing:animate): "auto" is the model's own (a person walks while it
# moves and stands breathing when it doesn't; trees sway; coins spin), "none" holds it still.
ANIMATIONS = ("auto", "walk", "idle", "wave", "none")
HOLDABLE = ("axe", "pickaxe", "sword", "torch", "hammer")
EDGE_MODES = ("bounce", "wrap", "stop", "none")
PLAYER_MODES = ("first person", "third person")
ALIGNS = ("left", "center", "centre", "right")
TERRAIN_STYLES = ("grass", "desert", "snow", "rocky", "autumn")
LIGHTINGS = ("simple", "modern")
# Where game:panel pins a panel, and other words for the same places ("centre", "middle", "top center"...).
ANCHORS = ("top left", "top", "top right", "left", "center", "right", "bottom left", "bottom", "bottom right")
ANCHOR_WORDS = {"centre": "center", "middle": "center", "mid": "center", "centered": "center", "upper": "top",
                "lower": "bottom"}
# What thing:physics(kind) can make a thing: falls and gets pushed, never moves, moved by the program, or no body.
PHYSICS_KINDS = ("dynamic", "static", "kinematic", "off")
PHYSICS_WORDS = {"on": "dynamic", "falls": "dynamic", "fall": "dynamic", "fixed": "static", "still": "static",
                 "solid": "static", "none": "off", "no": "off"}
# Kit models that get a capsule for a body when they use physics (people and creatures), not a box.
CAPSULE_KINDS = ("person", "character", "villager", "npc", "enemy", "zombie", "robot", "knight", "player")

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
              "keydown": "on_key", "raycast": "looking_at", "ray": "looking_at", "pick": "looking_at",
              "land": "terrain", "landscape": "terrain", "heightmap": "terrain", "lights": "lighting", "shading": "lighting"},
    "terrain": {"height": "height_at", "get_height": "height_at", "ground_at": "height_at", "texture": "style",
                "theme": "style", "biome": "style", "mound": "hill", "bump": "hill", "peak": "mountain", "hole": "dip",
                "pit": "dip", "crater": "dip", "pond": "lake", "sea": "water", "ocean": "water", "trench": "valley",
                "canyon": "valley", "river": "valley", "dig": "lower", "sculpt": "raise", "paint": "raise", "up": "raise",
                "down": "lower", "level": "flatten", "flat": "flatten", "soften": "smooth", "blur": "smooth"},
    "sprite": {"goto": "move_to", "go_to": "move_to", "position": "move_to", "rotate": "turn", "rotation": "angle",
               "collide": "touches", "collides": "touches", "colliding": "touches", "hits": "touches", "touching": "touches",
               "fill": "color", "colour": "color", "text": "set", "on_click": "clicked", "delete": "remove",
               "destroy": "remove", "kill": "remove", "wrap": "on_edge", "keep_on_screen": "on_edge"},
    "object": {"goto": "move_to", "go_to": "move_to", "position": "move_to", "rotate": "turn", "rotation": "angle",
               "collide": "touches", "collides": "touches", "touching": "touches", "hits": "touches",
               "colour": "color", "on_click": "clicked", "delete": "remove", "destroy": "remove", "kill": "remove",
               "text": "label", "name": "label", "chop": "shake", "topple": "fall"},
    "player": {"goto": "move_to", "position": "move_to", "speed": "walk_speed", "jump_power": "jump_height",
               "holds": "hold", "equip": "hold", "aim": "looking_at", "target": "looking_at", "on_collision": "on_hit",
               "on_collide": "on_hit", "collided": "on_hit"},
}
# Physics names people bring from other engines (Unity, Godot, pygame's pymunk...), for sprites and objects alike.
PHYSICS_HINTS = {"rigidbody": "physics", "rigid_body": "physics", "add_physics": "physics", "enable_physics": "physics",
                 "use_physics": "physics", "body": "physics", "impulse": "push", "apply_impulse": "push", "add_force": "push",
                 "apply_force": "push", "force": "push", "kick": "push", "throw": "push", "weight": "mass",
                 "bounciness": "bounce", "restitution": "bounce", "elasticity": "bounce", "on_collision": "on_hit",
                 "on_collide": "on_hit", "on_contact": "on_hit", "collided": "on_hit", "on_bump": "on_hit",
                 "torque": "spin", "apply_torque": "spin", "add_torque": "spin", "linear_velocity": "velocity",
                 "set_velocity": "velocity", "freeze": "sleep", "unfreeze": "wake", "wake_up": "wake"}
HINTS["sprite"].update(PHYSICS_HINTS)
HINTS["object"].update(PHYSICS_HINTS)
HINTS["world"].update({"set_gravity": "gravity", "explosion": "explode", "blast": "explode", "bomb": "explode",
                       "vehicle": "car", "kart": "car", "buggy": "car", "doll": "ragdoll", "dummy": "ragdoll"})
HINTS["game"].update({"set_gravity": "gravity", "explosion": "explode", "blast": "explode", "bomb": "explode",
                      "edges": "walls", "borders": "walls", "bounds": "walls", "screen_walls": "walls"})
HINTS["car"] = {**HINTS["object"], "accelerate": "engine", "power": "engine", "throttle": "engine", "control": "drive",
                "steer": "drive", "drive_with_keys": "drive", "reset": "flip", "unflip": "flip", "upright": "flip",
                "kmh": "speed", "mph": "speed"}
HINTS["ragdoll"] = {**HINTS["object"], "hit": "push", "flop": "push"}
# What a 2D game can't make, with what to do instead.
NEEDS_3D = {"car": "The car needs a 3D world. Make the game with tgame.world(...) to drive one.",
            "ragdoll": "A ragdoll needs a 3D world. Make the game with tgame.world(...) for one."}
# Names people guess for menus, the same in 2D and 3D.
UI_HINTS = {"menu": "screen", "overlay": "screen", "popup": "screen", "dialog": "screen", "modal": "screen",
            "title_screen": "start_screen", "start_menu": "start_screen", "main_menu": "start_screen",
            "splash": "start_screen", "splash_screen": "start_screen", "click_to_play": "start_screen", "ui": "panel",
            "gui": "panel", "toolbar": "panel", "sidebar": "panel"}
HINTS["game"].update(UI_HINTS)
HINTS["world"].update(UI_HINTS)

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


def did_you_mean(word, options):
    """' Did you mean "grass"?' for a name close to one of the options, or ''."""
    import difflib
    close = difflib.get_close_matches(word, options, 1, 0.6)
    return f" Did you mean \"{close[0]}\"?" if close else ""


def style_problem(name):
    return (f"The land's style can be {', '.join(TERRAIN_STYLES[:-1])} or {TERRAIN_STYLES[-1]}, not \"{name}\"."
            + did_you_mean(name, TERRAIN_STYLES))


def lighting_problem(name):
    return f"The lighting can be \"simple\" or \"modern\", not \"{name}\".{did_you_mean(name, LIGHTINGS)}"


def anchor_name(text):
    """Where a panel goes ("top left", "center"...) for what a program wrote ("Top-Left", "centre", "top middle",
    "left top"...), or None."""
    words = [ANCHOR_WORDS.get(w, w) for w in re.split(r"[\s_-]+", str(text).strip().lower()) if w]
    if len(words) > 1:
        words = [w for w in words if w != "center"] or ["center"]  # "top center" is the top, "center center" the middle
    if len(words) == 2 and words[0] in ("left", "right") and words[1] in ("top", "bottom"):
        words.reverse()
    name = " ".join(words)
    return name if name in ANCHORS else None


def anchor_problem(name):
    return (f"A panel can go at the top left, top, top right, left, center, right, bottom left, bottom or bottom right, "
            f"not \"{name}\".{did_you_mean(str(name).strip().lower(), ANCHORS)}")


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
        if self.what == "A game" and str(name).lower() in NEEDS_3D:
            message, rt = NEEDS_3D[str(name).lower()], self.rt

            def needs_3d(*_args):
                raise rt.error(message)
            return needs_3d
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
        ("group", "group"), ("hud", "get_hud"), ("clear", "clear"), ("panel", "panel"), ("screen", "make_screen"),
        ("start_screen", "start_screen"),
        ("slow_mo", "slow_mo"), ("shake", "shake"), ("pop_text", "pop_text"),
    ]

    def __init__(self, lib, title, width, height):
        import tuff_view
        self.tv = tuff_view
        self.lib, self.rt = lib, lib.rt
        self.W, self.H = width, height
        self.ui = None  # the game's menus (GameUI), once game:panel or a screen made them
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
        self.phys = None  # the game's physics (Physics), once something uses it
        self.fx = None  # its effects (Effects): slow motion, a shake, pop text, weather, the time of day
        self.base = getattr(getattr(self.rt, "interp", None), "base_dir", None) or os.getcwd()
        if SCENE is not None:
            self.autopilot = None
            self.view = tuff_view.Recorder(title, width, height, assets=self.base, on_create=SCENE.created)
            SCENE.game = self
        else:
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
        """Problems the game window finds: a picture, sound or model that won't load, or a bug in the page or in tgame.
        They go through tuff.py's report() like any Tuff error: the Run window shows them, and so does a built app's
        error box (build.js's launcher wraps report()), which is all a game with no console has."""
        import re
        import urllib.parse
        err_type = type(self.rt.error(""))
        if not isinstance(exc, err_type):
            where = re.sub(r"^the window \((.*)\)$", r"\1", where)
            # The page names files by their address (http://127.0.0.1:port/token/assets/broken.png): use the file's name.
            detail, files = re.subn(r"\S*/assets/([^\s?#]+)\S*", lambda m: "'" + urllib.parse.unquote(m.group(1)) + "'", str(exc))
            hint = " Check that the file opens on its own, or save it again." if files else ""
            exc = self.rt.error(f"The game window had a problem ({where}): {detail.rstrip('.')}.{hint}")
        tuff = sys.modules.get(type(self.rt).__module__)  # tuff.py (__main__ when it's run directly)
        report = getattr(tuff, "report", None)
        if report is not None:
            report(exc, self.rt.interp.src)
        else:
            sys.stderr.write(f"Tuff error: {exc}\n")
            sys.stderr.flush()

    def num(self, v, what):
        return self.rt.number(v, what)

    @property
    def is_paused(self):
        """Paused by game:pause or game:game_over, or by a screen that pauses while it shows (game:resume doesn't
        resume a game that a screen holds: hiding the screen does)."""
        return self.program_paused or (self.ui is not None and self.ui.pausing)

    @is_paused.setter
    def is_paused(self, on):
        self.program_paused = on

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
        except self.tv.ViewError:  # the window only serves files in the .tuf's folder and the folders inside it
            raise self.rt.error(f"The {what} '{rel}' has to be next to your .tuf file, or in a folder inside it.")

    def fire(self, fn, *args):
        return self.rt.call(fn, *args)[0]

    def adopt(self, thing):
        self.things[thing] = None
        return thing

    # ---- the loop
    def is_open(self):
        if SCENE is not None: SCENE.stop("loop")
        if not self.view.is_open:  # closed with its X, even in a loop that never calls game:frame()
            self.closed = True
        return not self.closed

    def frame(self):
        if SCENE is not None: SCENE.stop("loop")
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
        if self.phys is not None:
            self.phys.frame()
        if self.fx is not None:
            self.fx.before_frame()
        self.before_frame()
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
        if self.fx is not None:
            dt = self.fx.frame(dt, real)  # slow motion slows everything that goes by dt
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
        if SCENE is not None: SCENE.stopped = SCENE.stopped or "end"; return
        try:
            while not self.closed:
                self.step()
        except KeyboardInterrupt:
            pass

    def update(self, dt, real):
        """What a 2D game or a 3D world does every frame besides moving things (the camera, the player)."""

    def before_frame(self):
        """Changes kept back until the frame is sent (a 3D world's land, which many edits can change at once)."""

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
        ui = self.ui
        for e in events:
            t = e.get("type")
            if ui is not None and t in UI_EVENTS and ui.handle(e):  # it was on the menus: it isn't the game's
                if t == "mouseup":
                    self.down.discard(MOUSE_BUTTONS.get(e.get("button", 0), "mouse"))
                continue
            if t == "keydown":
                name = key_of_event(e)
                if not name or (e.get("typing") and name != "escape"):
                    continue  # no key, or one typed into a text box on the menus: it doesn't move the player
                if ui is not None and name not in self.down and not e.get("repeat") and ui.start_key(name):
                    continue  # Enter or Space on a start screen starts the game, and that's all it does
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
                    if self.phys is not None:
                        self.phys.dirty.add(thing)  # its body is the model's size too
            elif t == "phys" and self.phys is not None:  # where physics moved things this frame, and what hit what
                self.phys.report(e)
            elif t == "tg-lock" and ui is not None:  # the page asked to lock the mouse (a start screen's click)
                ui.lock_asks += 1
            elif t == "tg-autopilot":
                print(f"[autopilot] {e.get('message')}", flush=True)
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

    # ---- effects (Effects): slow motion, a shake, pop text
    def effects(self):
        if self.fx is None:
            self.fx = Effects(self)
        return self.fx

    def slow_mo(self, speed=0.3, seconds=None):
        self.effects().slow_mo(speed, seconds)

    def shake(self, strength=0.5, seconds=0.4):
        self.effects().shake(strength, seconds)

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

    # ---- physics
    def physics_on(self):
        """The game's physics, started the first time something uses it (that's when the page loads Rapier)."""
        if self.phys is None:
            self.phys = Physics(self)
        return self.phys

    def gravity(self, strength):
        g = self.num(strength, ":gravity")
        self.physics_on().set_gravity(g)

    # ---- menus, buttons and screens: atgui's widgets on the game
    def menus(self):
        if self.ui is None:
            self.ui = GameUI(self)
        return self.ui

    def panel(self, anchor="top left"):
        ui = self.menus()
        where = anchor_name(ui.lib.text(anchor))
        if where is None:
            raise self.rt.error(anchor_problem(ui.lib.text(anchor)))
        return Panel(ui, where).native()

    def make_screen(self, title="", pauses=True):
        ui = self.menus()
        return Screen(ui, ui.lib.text(title), self.rt.truthy(pauses)).native()

    def start_screen(self, title=None, hint="Click to play"):
        ui = self.menus()
        return StartScreen(ui, self.view.title if title is None else ui.lib.text(title), ui.lib.text(hint)).native()

    def stats(self):
        """Numbers for the autopilot's reports."""
        def spread(xs):
            xs = sorted(x * 1000 for x in xs)
            return (round(xs[len(xs) // 2], 3), round(xs[min(len(xs) - 1, int(len(xs) * 0.95))], 3)) if xs else (None, None)

        (tm, tp), (em, ep) = spread(self.work), spread(self.engine)
        return {"fps": self.fps(), "frames": self.frames, "tuff_ms_median": tm, "tuff_ms_p95": tp,
                "engine_ms_median": em, "engine_ms_p95": ep}


# ---------------------------------------------------------------- effects: slow motion, a shake, pop text, weather, the time of day

WEATHERS = ("rain", "snow", "none")
WEATHER_WORDS = {"rainy": "rain", "raining": "rain", "storm": "rain", "stormy": "rain", "drizzle": "rain", "showers": "rain",
                 "wet": "rain", "snowy": "snow", "snowing": "snow", "blizzard": "snow", "snowfall": "snow", "clear": "none",
                 "sunny": "none", "off": "none", "nothing": "none", "dry": "none", "stop": "none", "no": "none", "": "none"}
# The day, hour by hour: the sky it looks like then. Between two hours the sky is a mix of the two.
DAY = ((0, "night"), (4.5, "night"), (6.5, "dawn"), (8.5, "day"), (16, "day"), (18.5, "sunset"), (20.5, "night"), (24, "night"))
# The hour a day_cycle or time_of_day starts from, for the sky the world has (a "day" sky is the morning).
SKY_HOURS = {"day": 9, "sunset": 18.5, "dawn": 6.5, "night": 0, "cloudy": 12, "space": 12}
POP_SECONDS = 1.1  # how long pop text floats before it's gone
# Names people guess for the effects, and the tgame name (for "Use :slow_mo instead").
FX_HINTS = {"slowmo": "slow_mo", "slow_motion": "slow_mo", "slowmotion": "slow_mo", "bullet_time": "slow_mo",
            "time_scale": "slow_mo", "timescale": "slow_mo", "set_time_scale": "slow_mo", "slow_down": "slow_mo",
            "camera_shake": "shake", "screen_shake": "shake", "shake_camera": "shake", "shake_screen": "shake",
            "screenshake": "shake", "quake": "shake", "earthquake": "shake", "float_text": "pop_text",
            "floating_text": "pop_text", "damage_text": "pop_text", "popup_text": "pop_text", "pop_up_text": "pop_text",
            "text_pop": "pop_text", "damage_number": "pop_text", "popup_number": "pop_text", "score_popup": "pop_text"}
HINTS["game"].update(FX_HINTS)
HINTS["world"].update({**FX_HINTS, "rain": "weather", "snow": "weather", "set_weather": "weather", "climate": "weather",
                       "precipitation": "weather", "day_night": "day_cycle", "day_night_cycle": "day_cycle",
                       "daynight": "day_cycle", "daylight_cycle": "day_cycle", "time_cycle": "day_cycle",
                       "night_cycle": "day_cycle", "cycle": "day_cycle", "set_time": "time_of_day", "hour": "time_of_day",
                       "time_of_the_day": "time_of_day", "set_hour": "time_of_day", "daytime": "time_of_day",
                       "clock_time": "time_of_day"})
NEEDS_3D.update({"weather": "The weather needs a 3D world. Make the game with tgame.world(...) for rain or snow.",
                 "day_cycle": "Day and night need a 3D world, with a sky. Make the game with tgame.world(...) for them.",
                 "time_of_day": "The time of day needs a 3D world, with a sky. Make the game with tgame.world(...) for it."})


def weather_problem(name):
    return (f"The weather can be \"rain\", \"snow\" or \"none\", not \"{name}\"."
            + did_you_mean(str(name).strip().lower(), WEATHERS))


def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _hex(c):
    return "#" + "".join(f"{round(clamp(v, 0.0, 1.0) * 255):02x}" for v in c)


def mix_color(a, b, t):
    """The color a part t (0 to 1) of the way from a to b (hex colors; None stays None)."""
    if a is None or b is None:
        return a or b
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def sun_at(hour):
    """Where the light comes from at an hour: the sun rises in the east at 6, is high at noon and sets in the west at
    18, and the moon goes on round (lower) through the night, so shadows turn smoothly all day."""
    h = hour % 24
    turn = math.radians(90 + (h - 6) / 12 * 180)
    up = math.sin((h - 6) / 12 * math.pi)
    el = math.radians(15 + (50 * up if up > 0 else -35 * up))
    return (70 * math.cos(el) * math.sin(turn), 70 * math.sin(el), -70 * math.cos(el) * math.cos(turn))


class Effects:
    """A game's effects, made the first time the program uses one: slow motion (the frame's dt, so the game clock,
    timers, things that move by themselves and the player slow down, and the page's clock for physics and animation),
    shaking the camera (3D) or the game (2D), text that pops up from a spot and floats away, and in a 3D world the
    weather and the time of day (the sky, the sun, the light and the fog, worked out here and sent like world:sky's).

    The page draws its part in tuff_view_web/fx.js (the shake, pop text in 3D, rain and snow, the wet ground, the
    stars). Pop text in 2D is sprites. Everything holds still while the game is paused, and in Tuff Engine's preview
    (tuff.py --scene) nothing goes to the page but the sky."""

    def __init__(self, game):
        self.game = game
        self.live = SCENE is None
        self.speed = 1.0           # how fast the game runs now (slow motion eases it down and back)
        self.slow = None           # [the speed it eases to, real seconds left (None: until slow_mo(1))]
        self.sent = {"speed": 1.0, "pause": False}
        self.pops = []             # 2D: [text, its shadow, age, x, y, size]
        self.weather_ = "none"
        self.strength = 1.0
        self.hour = None           # the time of day (0-24), once day_cycle or time_of_day set it
        self.cycle = 0.0           # seconds for a whole day (0: the time holds still)
        self.sky_due = 0.0         # seconds until the day's sky goes again
        self.look_sent = None      # what the sky was made from last time (to notice world:sky, :fog, :sun, :terrain)
        self.stars = 0.0

    def send(self, op, *args):
        if self.live and not self.game.closed:
            self.game.view.call(0, "fx", op, *args)

    def target(self):
        """The page's node that shakes: a world's scene, or a 2D game's canvas."""
        g = self.game
        return int(g.scene if g.three_d else g.node)

    # ---- every frame
    def frame(self, dt, real):
        """The frame's dt at the game's speed (0 while paused), after slow motion and the time of day moved on."""
        g = self.game
        if not g.is_paused and real:
            want = 1.0
            if self.slow is not None:
                want, left = self.slow
                if left is not None:
                    self.slow[1] = left - real
                    if self.slow[1] <= 0:
                        self.slow, want = None, 1.0
            if self.speed != want:  # quickly into slow motion, gently back out of it
                self.speed += (want - self.speed) * min(1.0, real * (25 if want < self.speed else 6))
                if abs(self.speed - want) < 0.003:
                    self.speed = want
        dt *= self.speed
        if dt and self.hour is not None and self.cycle:
            self.hour = (self.hour + dt * 24 / self.cycle) % 24
            self.sky_due -= dt
        if self.pops:
            self.move_pops(dt)
        return dt

    def before_frame(self):
        """Before the frame goes: the game's speed and pausing for the page, and the sky when it changed."""
        g = self.game
        paused = bool(g.is_paused)
        if paused != self.sent["pause"]:
            self.sent["pause"] = paused
            self.send("pause", paused)
        if abs(self.speed - self.sent["speed"]) > 0.002 or (self.speed == 1.0 != self.sent["speed"]):
            self.sent["speed"] = self.speed
            self.send("speed", round(self.speed, 4))
        if g.three_d and (self.hour is not None or self.weather_ != "none"):
            due = self.hour is not None and self.cycle and self.sky_due <= 0
            if due or self.look_sent != self.look_key():
                self.show_sky()

    # ---- slow motion
    def slow_mo(self, speed, seconds):
        g = self.game
        k = g.num(speed, ":slow_mo")
        if not 0.05 <= k <= 1:
            raise g.rt.error(f":slow_mo needs a speed from 0.05 to 1 (0.3 is 30%, 1 is normal speed), like "
                             f"{g.KIND}:slow_mo(0.3, 2).")
        secs = None if seconds is None else g.num(seconds, ":slow_mo")
        if secs is not None and secs < 0:
            raise g.rt.error(":slow_mo needs how many seconds it lasts (0 or more), like "
                             f"{g.KIND}:slow_mo(0.3, 2).")
        self.slow = None if k == 1 else [k, secs or None]

    # ---- shaking
    def shake(self, strength, seconds):
        g = self.game
        s = g.num(strength, ":shake")
        secs = g.num(seconds, ":shake")
        if not 0 <= s <= 2:
            raise g.rt.error(f":shake needs a strength from 0 to 2 (0.5 is a bump, 2 is an earthquake), like {g.KIND}:shake(0.5).")
        if secs <= 0:
            raise g.rt.error(f":shake needs how long it shakes, in seconds (more than 0), like {g.KIND}:shake(1, 1.5).")
        self.send("shake", self.target(), s, min(secs, 60))

    # ---- pop text
    def pop_text(self, text, x, y, z, color, size):
        g = self.game
        words = g.rt.text(text)
        c = g.color(color)
        px = g.num(size, ":pop_text")
        if px <= 0:
            raise g.rt.error(f":pop_text needs a size above 0 (how tall the text is), like {g.KIND}:pop_text(\"+10\", "
                             + ("0, 1, 0, \"gold\", 40)." if g.three_d else "100, 50, \"gold\", 40)."))
        if g.three_d:
            self.send("pop", self.target(), words, x, y, z, c, min(px, 400))
            return
        common = {"text": words, "size": px, "bold": True, "ax": 0.5, "ay": 0.5}
        shadow = g.make("text", x + px * 0.06, y + px * 0.06, {**common, "color": "#000000", "alpha": 0.55, "z": 1e5}, own=False)
        front = g.make("text", x, y, {**common, "color": c, "z": 1e5 + 1}, own=False)
        self.pops.append([front, shadow, 0.0, x, y, px])
        while len(self.pops) > 80:
            for s in self.pops.pop(0)[:2]:
                s.remove()

    def move_pops(self, dt):
        """2D pop text floats up and fades (its sprites are tgame's own: game:clear leaves them to finish)."""
        keep = []
        for pop in self.pops:
            front, shadow, age, x, y, px = pop
            age += dt
            if age >= POP_SECONDS:
                front.remove()
                shadow.remove()
                continue
            f = age / POP_SECONDS
            rise = (1 - (1 - f) ** 3) * max(40.0, px * 1.6)
            alpha = 1.0 if f < 0.55 else 1 - (f - 0.55) / 0.45
            grow = 1 + 0.3 * math.sin(min(1.0, f / 0.22) * math.pi)
            front.send(y=y - rise, alpha=round(alpha, 3), scale=round(grow, 3))
            shadow.send(y=y - rise + px * 0.06, alpha=round(alpha * 0.55, 3), scale=round(grow, 3))
            pop[2] = age
            keep.append(pop)
        self.pops = keep

    # ---- the weather (3D)
    def weather(self, kind, strength):
        g = self.game
        name = g.rt.text(kind).strip().lower()
        name = WEATHER_WORDS.get(name, name)
        if name not in WEATHERS:
            raise g.rt.error(weather_problem(name))
        k = g.num(strength, ":weather")
        if not 0 <= k <= 2:
            raise g.rt.error(":weather needs a strength from 0 to 2 (1 is normal), like world:weather(\"rain\", 1.5).")
        self.weather_, self.strength = (name, k) if k > 0 else ("none", 0.0)
        self.send("weather", self.target(), self.weather_, self.strength)
        self.sky_changed()
        if self.weather_ == "none" and self.hour is None:
            self.show_sky()  # back to the plain sky, which the world shows again from now on

    def grounds(self):
        """The page's nodes of the ground: the land, world:ground and world:island (they look wet in the rain)."""
        g = self.game
        ids = [int(t.node) for t in g.things if getattr(t, "floor", False) and t.alive]
        if g.land is not None:
            ids.append(int(g.land.node))
        return ids

    # ---- the time of day (3D)
    def day_cycle(self, seconds):
        g = self.game
        secs = g.num(seconds, ":day_cycle")
        if secs != 0 and secs < 2:
            raise g.rt.error(":day_cycle needs how many seconds a whole day takes (2 or more), like world:day_cycle(120). "
                             "world:day_cycle(0) stops the time where it is.")
        if self.hour is None:
            self.hour = float(SKY_HOURS.get(g.sky_name, 12))
        self.cycle = float(secs)
        self.sky_changed()

    def time_of_day(self, hour):
        g = self.game
        if hour is None:
            return tidy(self.hour if self.hour is not None else SKY_HOURS.get(g.sky_name, 12))
        h = g.num(hour, ":time_of_day")
        if not 0 <= h <= 24:
            raise g.rt.error(":time_of_day needs an hour from 0 to 24 (18 is 6 pm), like world:time_of_day(18).")
        self.hour = h % 24
        self.sky_changed()
        return None

    def chose_sky(self):
        """world:sky: a sky the program picks stops the day where it is (the weather still changes it)."""
        self.hour, self.cycle = None, 0.0
        self.look_sent = None
        if self.stars:
            self.stars = 0.0
            self.send("stars", self.target(), 0)

    # ---- the sky they make
    def sky_changed(self):
        """The sky goes again before the next frame (in Tuff Engine's preview, which has no frames, right away)."""
        self.look_sent = None
        if not self.live:
            self.show_sky()

    def look_key(self):
        """What the sky is made from, besides the time: when one of these changes, the sky goes again."""
        g = self.game
        land = g.land.size if g.land is not None else None
        return (g.sky_name, g.fog_far, g.sun_strength, land, self.weather_, self.strength, len(self.grounds()))

    def day_look(self, hour):
        """The sky at an hour, as SKIES has them: a mix of the two skies either side of it in DAY."""
        h = hour % 24
        a, b, t = "night", "night", 0.0
        for (h0, s0), (h1, s1) in zip(DAY, DAY[1:]):
            if h0 <= h <= h1:
                a, b, t = s0, s1, ease((h - h0) / (h1 - h0))
                break
        A, B = SKIES[a], SKIES[b]

        def lerp(p, q):
            return p + (q - p) * t
        return {"sky": [mix_color(p, q, t) for p, q in zip(A["sky"], B["sky"])], "fog": mix_color(A["fog"], B["fog"], t),
                "sun": (mix_color(A["sun"][0], B["sun"][0], t), lerp(A["sun"][1], B["sun"][1])),
                "hemi": (mix_color(A["hemi"][0], B["hemi"][0], t), mix_color(A["hemi"][1], B["hemi"][1], t),
                         lerp(A["hemi"][2], B["hemi"][2])),
                "at": sun_at(h), "far": lerp(A["far"], B["far"]), "stars": (a == "night") * (1 - t) + (b == "night") * t}

    def weathered(self, look):
        """The sky with the weather: rain makes it greyer and darker, with less sun and thicker fog that hides the
        stars; snow makes it paler, with a little less sun and some fog."""
        k = self.strength if self.weather_ != "none" else 0.0
        if not k:
            return look
        w = min(1.0, k)
        rain = self.weather_ == "rain"

        def grey(c):
            r, g_, b = _rgb(c)
            lum = 0.3 * r + 0.59 * g_ + 0.11 * b
            if rain:
                return mix_color(c, _hex([lum * 0.72, lum * 0.75, lum * 0.8]), 0.78 * w)
            lum = min(1.0, lum * 1.05 + 0.18)
            return mix_color(c, _hex([lum * 0.97, lum * 0.99, lum]), 0.75 * w)
        out = dict(look)
        out["sky"] = [grey(c) for c in look["sky"]]
        out["fog"] = grey(look["fog"]) if look["fog"] else None
        out["sun"] = (grey(look["sun"][0]), look["sun"][1] * (1 - (0.6 if rain else 0.3) * w))
        out["hemi"] = (grey(look["hemi"][0]), look["hemi"][1], look["hemi"][2] * ((1 - 0.1 * w) if rain else (1 + 0.05 * w)))
        out["thick"] = 1 + (0.9 if rain else 0.55) * k  # the fog comes this many times closer
        out["stars"] = look.get("stars", 0) * (1 - w)
        return out

    def show_sky(self):
        """Sends the sky (as World3D.apply_sky does) for the time of day and the weather."""
        g = self.game
        self.look_sent = self.look_key()
        base = self.day_look(self.hour) if self.hour is not None else {**SKIES[g.sky_name], "stars": 0.0}
        s = self.weathered(base)
        far = g.fog_far if g.fog_far is not None else g.sky_far(s)
        far = far / s.get("thick", 1)
        g.view.set(g.scene, sky=s["sky"], bg=s["sky"][1], fog=[s["fog"], far * 0.3, far] if (s["fog"] and far) else None)
        g.view.set(g.hemi, color=s["hemi"][0], ground=s["hemi"][1], intensity=s["hemi"][2])
        x, y, z = s["at"]
        g.view.set(g.sun_node, color=s["sun"][0], intensity=s["sun"][1] * g.sun_strength, x=x, y=y, z=z)
        stars = round(s["stars"], 3)
        if stars != self.stars:
            self.stars = stars
            self.send("stars", self.target(), stars)
        self.send("wet", self.target(), min(1.0, self.strength) if self.weather_ == "rain" else 0, self.grounds())
        # The next sky goes when the day has moved on a little (every frame for a day of a few seconds).
        self.sky_due = min(0.1, self.cycle / 1200) if self.cycle else 0.0

    def state(self):
        """For the autopilot's reports: Python's side and the page's."""
        out = {"speed": round(self.speed, 3), "slow": self.slow and [self.slow[0], self.slow[1] and round(self.slow[1], 2)],
               "weather": self.weather_, "strength": self.strength,
               "hour": None if self.hour is None else round(self.hour, 3), "cycle": self.cycle, "stars": self.stars,
               "pops": len(self.pops)}
        if self.live and not self.game.closed:
            try:
                out["page"] = self.game.view.ask(0, "fx", "info")
            except Exception as exc:
                out["page"] = {"error": str(exc)}
        return out


# ---------------------------------------------------------------- physics on sprites and objects

def physics_problem(word):
    return (f"Physics can be \"dynamic\" (it falls and gets pushed), \"static\" (it never moves), \"kinematic\" (your code "
            f"moves it) or \"off\", not \"{word}\".{did_you_mean(word, PHYSICS_KINDS)}")


class Physical:
    """What sprites (2D) and objects (3D) share for physics. A thing with a body of its own (thing:physics()) is in the
    page's physics (Rapier, see Physics): a dynamic one falls, tumbles, bounces and gets pushed, and the page tells
    Python where it went every frame; a static one never moves; a kinematic one is moved by the program and pushes
    dynamic ones out of its way. push, spin and velocity work on dynamic ones."""
    D = 3  # numbers in a push, a velocity, a position (a sprite's: 2)
    EXAMPLE = "crate"

    def phys_init(self):
        self.phys_kind = None  # its own body: None, "dynamic", "static" or "kinematic"
        self.mass_ = self.bounce_ = self.friction_ = None
        self.hit_fns = []
        self.vel = [0.0] * self.D  # its speed, as physics last reported it
        self.phys_sent = None  # its body, as the page last heard of it

    def phys_name(self):
        """What it's called in a message ("box:mass needs...")."""
        return self.kind

    def phys_changed(self):
        if self.game.phys is not None:
            self.game.phys.sync(self)

    def dynamic(self):
        return self.phys_kind == "dynamic" and self.game.phys is not None

    def need_dynamic(self, what):
        if self.dynamic():
            return
        n = self.phys_name()
        if self.phys_kind is None:
            raise self.rt.error(f"{n}:{what} works on things with physics. Turn it on first, like {self.EXAMPLE}:physics().")
        raise self.rt.error(f"A {self.phys_kind} {n} doesn't move by itself, so :{what} can't move it. "
                            f"{n}:physics() lets it fall and be pushed.")

    def phys_vector(self, args, what, example):
        """D numbers (or one list of them), for push, spin and velocity."""
        rt = self.rt
        given = [a for a in args if a is not MISSING]
        if len(given) == 1 and isinstance(rt.plain(given[0]), list):
            given = list(rt.plain(given[0]))
        if len(given) != self.D:
            raise rt.error(f"{self.phys_name()}:{what} needs {'x, y and z' if self.D == 3 else 'x and y'}, like {example}.")
        return [rt.number(v, f":{what}") for v in given]

    def physics(self, kind=MISSING):
        rt = self.rt
        if kind is MISSING:
            k = "dynamic"
        elif isinstance(rt.plain(kind), bool):
            k = "dynamic" if rt.plain(kind) else "off"
        else:
            k = rt.text(kind).strip().lower()
            k = PHYSICS_WORDS.get(k, k)
            if k not in PHYSICS_KINDS:
                raise rt.error(physics_problem(k))
        self.can_have_physics(k)
        ph = self.game.physics_on()
        was = self.phys_kind
        self.phys_kind = None if k == "off" else k
        if k == "dynamic":
            self.stop_moving()  # from now on physics moves it
        elif was == "dynamic":
            self.push()  # it stays where physics left it
            self.after_physics()
        ph.sync(self)
        return self.native

    def can_have_physics(self, kind):
        pass

    def stop_moving(self):
        self.vx = self.vy = self.spin_speed = 0.0
        if self.D == 3:
            self.vz = 0.0
        self.busy()

    def after_physics(self):
        pass

    def mass(self, kg):
        m = self.num(kg, ":mass")
        if m <= 0:
            raise self.rt.error(f"{self.phys_name()}:mass needs a number above 0, like {self.EXAMPLE}:mass(2).")
        self.mass_ = m
        self.phys_changed()
        return self.native

    def bounce(self, amount=MISSING):
        v = self.rt.plain(amount)
        if amount is MISSING or isinstance(v, (str, bool)) or not 0 <= self.num(amount, ":bounce") <= 1:
            edges = " To bounce off the window's edges, use :on_edge(\"bounce\")." if self.D == 2 else ""
            raise self.rt.error(f"{self.phys_name()}:bounce needs how bouncy it is, from 0 to 1, like "
                                f"{self.EXAMPLE}:bounce(0.6).{edges}")
        self.bounce_ = self.num(amount, ":bounce")
        self.phys_changed()
        return self.native

    def friction(self, amount):
        f = self.num(amount, ":friction")
        if f < 0:
            raise self.rt.error(f"{self.phys_name()}:friction needs a number of 0 or more, like {self.EXAMPLE}:friction(0.4).")
        self.friction_ = f
        self.phys_changed()
        return self.native

    def kick(self, x, y=MISSING, z=MISSING):  # thing:push (push() sends where a thing is)
        v = self.phys_vector([x, y, z], "push", f"{self.EXAMPLE}:push(0, 5, -3)" if self.D == 3 else "ball:push(200, -300)")
        self.need_dynamic("push")
        self.game.phys.send("push", int(self.node), *v)
        return self.native

    def velocity(self, x=MISSING, y=MISSING, z=MISSING):
        if x is MISSING:
            return [tidy(v) for v in self.velocity_now()]
        v = self.phys_vector([x, y, z], "velocity", f"{self.EXAMPLE}:velocity(0, 0, -4)" if self.D == 3 else "ball:velocity(100, 0)")
        if self.dynamic():
            self.vel = list(v)
            self.game.phys.send("velocity", int(self.node), *v)
        else:  # without physics, it moves that fast by itself (like :speed)
            self.set_speed(v)
        return self.native

    def velocity_now(self):
        """Its speed each way: physics's, or the one it moves by itself."""
        if self.dynamic():
            return self.vel
        return [self.vx, self.vy] + ([self.vz] if self.D == 3 else [])

    def set_speed(self, v):
        self.vx, self.vy = v[0], v[1]
        if self.D == 3:
            self.vz = v[2]
        self.busy()

    def on_hit(self, fn):
        self.hit_fns.append(self.game.lib.check_fn(fn, ":on_hit"))
        self.phys_changed()  # its body reports hits now
        return self.native

    def sleep(self):
        self.need_dynamic("sleep")
        self.game.phys.send("sleep", int(self.node))
        return self.native

    def wake(self):
        self.need_dynamic("wake")
        self.game.phys.send("wake", int(self.node))
        return self.native

    def phys_dump(self):
        """For Tuff Engine (tuff.py --scene): its physics settings, or None."""
        if self.phys_kind is None:
            return None
        return {"kind": self.phys_kind, "mass": tidy(self.mass_) if self.mass_ is not None else None,
                "bounce": tidy(self.bounce_) if self.bounce_ is not None else None,
                "friction": tidy(self.friction_) if self.friction_ is not None else None}


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

    def sprite_at(self, e):
        """The topmost sprite on this layer that has a :clicked function, under a click (window pixels), or None."""
        x, y = self.to_layer(e.get("x", 0), e.get("y", 0))
        for s in sorted((s for s in self.sprites if s.alive and not s.hidden and s.click_fns),
                        key=lambda s: (s.z, s.order), reverse=True):
            if s.contains(x, y):
                return s
        return None

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
                          ("camera", "camera"), ("gravity", "gravity"), ("explode", "explode"), ("walls", "walls")]

    def __init__(self, lib, title, width, height):
        Layer.__init__(self, self, scrolls=True)
        Game.__init__(self, lib, title, width, height)

    def explode(self, x=MISSING, y=MISSING, strength=MISSING, radius=MISSING):
        x, y, (strength, radius) = self.place([x, y, strength, radius], (600, 150), "explode")
        s, r = self.num(strength, ":explode"), self.num(radius, ":explode")
        if r <= 0:
            raise self.rt.error(":explode needs a radius above 0 (how far it reaches), like game:explode(400, 300, 600, 150).")
        self.physics_on().send("explode", x, y, s, r)

    def walls(self, on=True):
        """The window's edges as walls that physics sprites bounce off (or not, with game:walls(false))."""
        ph = self.physics_on()
        ph.walls_ = self.rt.truthy(on)
        ph.send("walls", ph.walls_, self.W, self.H)

    def pop_text(self, text="", x=MISSING, y=MISSING, color=MISSING, size=MISSING):
        t = thing_of(x)
        if isinstance(t, Sprite):  # over a sprite: game:pop_text("+1", coin)
            given = [a for a in (y, color, size) if a is not MISSING]
            if len(given) > 2:
                raise self.rt.error(":pop_text got too many inputs.")
            color, size = given + ["white", 32][len(given):]
            x, y = t.x, t.y - max(t.h, t.r * 2, t.size_ if t.shape == "text" else 0) * t.k / 2 - 8
        else:
            x, y, (color, size) = self.place([x, y, color, size], ("white", 32), "pop_text")
        self.effects().pop_text(text, x, y, None, color, size)

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
        for layer in ([self.hud_layer] if self.hud_layer else []) + [self]:
            hit = layer.sprite_at(e)
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


class Sprite(Physical):
    """A shape, some text or a picture in a 2D game (or on a HUD)."""
    NAMES = [
        ("x", "get_x"), ("y", "get_y"), ("spot", "spot"), ("move", "move"), ("move_to", "move_to"), ("glide", "glide"),
        ("forward", "forward"), ("turn", "turn"), ("turn_to", "turn_to"), ("angle", "angle"), ("spin", "spin"),
        ("point_at", "point_at"), ("speed", "speed"), ("on_edge", "on_edge"), ("on_screen", "on_screen"),
        ("touches", "touches"), ("distance", "distance"), ("size", "size"), ("scale", "set_scale"),
        ("color", "set_color"), ("layer", "set_layer"), ("flip", "flip"), ("align", "align"), ("hide", "hide"),
        ("show", "show"), ("remove", "remove"), ("set", "set"), ("get", "get"), ("value", "value"),
        ("clicked", "clicked"), ("shake", "shake"),
        ("physics", "physics"), ("mass", "mass"), ("bounce", "bounce"), ("friction", "friction"), ("push", "kick"),
        ("velocity", "velocity"), ("on_hit", "on_hit"), ("sleep", "sleep"), ("wake", "wake"),
    ]
    D = 2
    EXAMPLE = "ball"
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
        self.phys_init()
        self.spin_rate = 0.0  # physics: how fast it turns (degrees a second), as the page last reported
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

    # ---- physics (see Physical)
    def phys_name(self):
        return {"rect": "box"}.get(self.shape, self.shape)

    def can_have_physics(self, kind):
        if self.layer is not self.game:
            raise self.rt.error("Only sprites in the game can use physics, not the ones on the HUD.")

    def kick(self, x, y=MISSING):
        return Physical.kick(self, x, y)

    def velocity(self, x=MISSING, y=MISSING):
        return Physical.velocity(self, x, y)

    def phys_spec(self):
        """Its body for the page (physics.js), in the game's pixels: a box, a ball, or a line's capsule."""
        if not self.alive or self.phys_kind is None or self.game.phys is None:
            return None
        k = self.k
        if self.shape == "circle":
            shape, size = "ball", tidy(max(0.5, self.r * k))
        elif self.shape == "line":
            (ax, ay), (bx, by) = self.points
            length = math.hypot(bx - ax, by - ay) * k
            turn = math.degrees(math.atan2(by - ay, bx - ax)) - 90  # a capsule lies along its own y
            shape, size = "capsule", [tidy(length / 2), 2, tidy((ax + bx) / 2 * k), tidy((ay + by) / 2 * k), tidy(turn)]
        else:
            hw, hh = self.half()
            shape, size = "box", [tidy(hw), tidy(hh)]
        return {"kind": self.phys_kind, "shape": shape, "size": size, "mass": self.mass_, "bounce": self.bounce_,
                "friction": self.friction_, "hits": bool(self.hit_fns)}

    def from_physics(self, b):
        """Where physics moved it: [id, x, y, angle, vx, vy, spin] (it isn't sent back)."""
        self.x, self.y, self.rot = b[1], b[2], b[3] % 360
        self.vel = [b[4], b[5]]
        self.spin_rate = b[6]

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
        n = self.num(degrees_per_second, ":spin")
        if self.dynamic():  # with physics it's a twist (an angular kick), like 3D's
            self.game.phys.send("spin", int(self.node), n)
            return self.native
        self.spin_speed = n
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

    def speed(self, vx=MISSING, vy=0):
        if vx is MISSING:  # how fast it goes (pixels a second)
            return tidy(math.hypot(*self.velocity_now()))
        v = [self.num(vx, ":speed"), self.num(vy, ":speed")]
        if self.dynamic():
            self.vel = v
            self.game.phys.send("velocity", int(self.node), *v)
            return self.native
        self.vx, self.vy = v
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
        if self.phys_kind is not None:
            self.phys_changed()  # its body's size too
        return self.native

    def set_scale(self, k):
        self.k = self.num(k, ":scale")
        self.send(scale=self.k)
        if self.phys_kind is not None:
            self.phys_changed()
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
            if self.dynamic():  # a glide carries it: no speed builds up meanwhile
                self.game.phys.send("velocity", int(self.node), 0, 0)
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
        ("terrain", "terrain"), ("lighting", "lighting"), ("gravity", "gravity"), ("explode", "explode"),
        ("car", "car"), ("ragdoll", "ragdoll"),
        ("weather", "weather"), ("day_cycle", "day_cycle"), ("time_of_day", "time_of_day"),
    ]

    def setup(self):
        v = self.view
        if v.info.get("webgl") is False:  # the page found no WebGL: three.js can't draw anything here
            v.close()
            raise self.rt.error("This computer can't show 3D worlds: its 3D graphics (WebGL) aren't working. "
                                "2D games (tgame.window) still work, and updating the graphics driver may help.")
        self.cam = [0.0, 1.7, 8.0]
        self.cam_yaw = 0.0  # heading, degrees clockwise from looking down -z
        self.cam_pitch = -8.0
        self.cam_mode = "fixed"
        self.cam_target = None
        self.cam_look = None
        self.orbit_state = None
        self.the_player = None
        self.driving = None  # the car the keys drive (car:drive)
        self.island_r = None
        self.land = None  # the Terrain, once world:terrain made it
        self.lighting_name = "simple"
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
        far = self.fog_far if self.fog_far is not None else self.sky_far(s)
        self.view.set(self.scene, sky=s["sky"], bg=s["sky"][1], fog=[s["fog"], far * 0.3, far] if (s["fog"] and far) else None)
        self.view.set(self.hemi, color=s["hemi"][0], ground=s["hemi"][1], intensity=s["hemi"][2])
        x, y, z = s["at"]
        self.view.set(self.sun_node, color=s["sun"][0], intensity=s["sun"][1] * self.sun_strength, x=x, y=y, z=z)

    def sky_far(self, s):
        """How far a sky's fog lets you see: further on a big land, so its hills don't vanish in the fog."""
        if self.land is not None and s["far"]:
            return max(s["far"], self.land.size * 1.5)
        return s["far"]

    # ---- sky, light, ground
    def sky(self, preset):
        name = self.rt.text(preset).strip().lower()
        if name not in SKIES:
            raise self.rt.error(f"The sky can be {', '.join(SKIES)}, not \"{name}\".")
        if self.fx is not None:
            self.fx.chose_sky()
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

    def lighting(self, name):
        n = self.rt.text(name).strip().lower()
        if n not in LIGHTINGS:
            raise self.rt.error(lighting_problem(n))
        self.lighting_name = n
        self.view.set(self.scene, lighting=n)

    def light(self, x=MISSING, y=MISSING, z=MISSING, color=MISSING):
        x, y, z, (color,) = self.where([x, y, z, color], ("white",), "light")
        y = self.above(x, y, z)
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

    def terrain(self, size=200, style="grass"):
        if self.land is not None:
            raise self.rt.error("A world has one terrain. Change it with land:hill, land:raise and so on.")
        sz = self.num(size, ":terrain")
        if not 10 <= sz <= 1000:
            raise self.rt.error(":terrain needs a size from 10 to 1000 (how wide the land is), like world:terrain(200).")
        name = self.rt.text(style).strip().lower()
        if name not in TERRAIN_STYLES:
            raise self.rt.error(style_problem(name))
        self.land = Terrain(self, sz, name)
        if self.phys is not None:
            self.phys.dirty.add(self.land)
        s = SKIES[self.sky_name]
        if self.fog_far is None and s["fog"] and s["far"]:
            far = self.sky_far(s)
            self.view.set(self.scene, fog=[s["fog"], far * 0.3, far])
        # Sun shadows over the land, not only near its middle (modern lighting moves them with the camera instead).
        self.view.set(self.sun_node, area=max(45, min(150, sz / 2 + 10)))
        return self.land.native

    # ---- the land under things: every y a program gives or reads is the height above it
    def ground_y(self, x, z):
        """The land's height at x, z: 0 without a terrain."""
        return self.land.at(x, z) if self.land is not None else 0.0

    def above(self, x, y, z):
        """Where a y the program gave (the height above the land) really is."""
        return y + self.land.at(x, z) if self.land is not None else y

    def before_frame(self):
        if self.is_paused != getattr(self, "page_paused", False) and SCENE is None:
            self.page_paused = self.is_paused  # the page's animations (anim.js) hold still while the game is paused
            self.view.set(self.scene, attrs={"data-paused": self.page_paused})
        if self.land is not None and self.land.dirty:
            self.land.push()

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
            shape = "[width, height, depth]" if three else "[width, depth]" if what == "plane" else "[width, height]"
            raise self.rt.error(f":{what}'s size is one number, or {shape}.")
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
        t = Thing(self, kind, x, self.above(x, y, z), z, (w, h, d), [part])
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
        y = self.above(x, y, z)
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

    # ---- physics
    def explode(self, x=MISSING, y=MISSING, z=MISSING, strength=MISSING, radius=MISSING):
        x, y, z, (strength, radius) = self.where([x, y, z, strength, radius], (10, 6), "explode")
        s, r = self.num(strength, ":explode"), self.num(radius, ":explode")
        if r <= 0:
            raise self.rt.error(":explode needs a radius above 0 (how far it reaches), like world:explode(0, 0, 0, 12, 8).")
        self.physics_on().send("explode", x, self.above(x, y, z), z, s, r)

    def car(self, x=MISSING, y=MISSING, z=MISSING, color=MISSING):
        x, y, z, (color,) = self.where([x, y, z, color], ("red",), "car")
        return Car(self, x, self.above(x, y, z), z, color).native

    def ragdoll(self, x=MISSING, y=MISSING, z=MISSING, color=MISSING):
        x, y, z, (color,) = self.where([x, y, z, color], ("blue",), "ragdoll")
        return Ragdoll(self, x, self.above(x, y, z), z, color).native

    # ---- effects (Effects): pop text, the weather, the time of day
    def pop_text(self, text="", x=MISSING, y=MISSING, z=MISSING, color=MISSING, size=MISSING):
        t = thing_of(x)
        if isinstance(t, (Thing, Player)):  # over a thing: world:pop_text("+1", coin)
            given = [a for a in (y, z, color, size) if a is not MISSING]
            if len(given) > 2:
                raise self.rt.error(":pop_text got too many inputs.")
            color, size = given + ["white", 34][len(given):]
            x, y, z = t.x, t.y + t.height() + 0.15, t.z
        else:
            x, y, z, (color, size) = self.where([x, y, z, color, size], ("white", 34), "pop_text")
            y = self.above(x, y, z)
        self.effects().pop_text(text, x, y, z, color, size)

    def weather(self, kind="rain", strength=1):
        self.effects().weather(kind, strength)

    def day_cycle(self, seconds=120):
        self.effects().day_cycle(seconds)

    def time_of_day(self, hour=None):
        if hour is None and self.fx is None:
            return tidy(SKY_HOURS.get(self.sky_name, 12))
        return self.effects().time_of_day(hour)

    def stop_chase(self):
        """The camera stops following the car it drives (the program put the camera somewhere else)."""
        if self.cam_mode == "drive":
            self.cam_mode = "fixed"
            if self.phys is not None:
                self.phys.send("chase", None)

    def drive_keys(self):
        """The keys, as the controls of the car being driven (sent when they change)."""
        car = self.driving
        if not car.alive:
            self.driving = None
            self.stop_chase()
            return
        d = self.down
        controls = (0, 0, 0) if self.is_paused else (
            ("w" in d or "up" in d) - ("s" in d or "down" in d), ("a" in d or "left" in d) - ("d" in d or "right" in d),
            int("space" in d))
        if controls != car.controls:
            car.controls = controls
            self.phys.send("drive", int(car.node), *controls)

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
        if SCENE is not None: SCENE.player_made = list(SCENE.interp.lines)
        self.cam_mode = "player"
        self.view.set(self.scene, clicklock=True)
        return self.the_player.native

    def camera_at(self, x=MISSING, y=MISSING, z=MISSING):
        x, y, z, _ = self.where([x, y, z], (), "camera_at")
        if self.cam_mode == "player":
            raise self.rt.error("The player has the camera. Use player:move_to to move the player instead.")
        self.stop_chase()
        self.cam_mode = "fixed"
        self.cam = [x, self.above(x, y, z), z]
        if self.cam_look is not None:
            self.aim(*self.cam_look)
        self.camera_dirty = True

    def look_at(self, x=MISSING, y=MISSING, z=MISSING):
        t = thing_of(x)
        if isinstance(t, (Thing, Player)):
            tx, ty, tz = t.x, t.y + t.height() * 0.5, t.z
        else:
            tx, ty, tz, _ = self.where([x, y, z], (), "look_at")
            ty = self.above(tx, ty, tz)
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
        self.stop_chase()
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
            tx, ty, tz, _ = self.where([x, y, z], (), "orbit")
            target = (tx, self.above(tx, ty, tz), tz)
        dist = max(4.0, math.dist(self.cam, self.point_of(target)))
        self.stop_chase()
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
        self.before_frame()  # the land as it is now, so it hides what's behind a hill
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
        land = self.land
        if land is not None and radius is None:
            r = land.size / 2 * 0.85
        solid = [t for t in self.things if isinstance(t, Thing) and t.alive and t.solid_ and not getattr(t, "floor", False)]
        p = self.the_player
        best = None
        for _ in range(40):
            if land is not None:  # on the land (a square), and not in its water
                half = min(r, land.size / 2 * 0.95)
                x, z = random.uniform(-half, half), random.uniform(-half, half)
                if (radius is not None and math.hypot(x, z) > r) or land.water_at(x, z) is not None:
                    continue
            else:
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
        # The HUD is on top, so a button on it gets the click instead of the object behind it. Not while the mouse
        # is locked for looking around: then the pointer is hidden and a click aims with the middle of the view.
        hit = None
        if self.hud_layer is not None and not (self.locked or self.fake_lock):
            hit = self.hud_layer.sprite_at(e)
        if hit is not None:
            for fn in list(hit.click_fns):
                self.fire(fn, hit.native)
        else:
            t = self.thing_at(e.get("path") or [])
            if t is not None and t.click_fns:
                for fn in list(t.click_fns):
                    self.fire(fn, t.native)
        if self.click_fns:
            pt = e.get("point")
            if pt and self.land is not None:  # the height above the land, like every y a program reads
                pt = [pt[0], pt[1] - self.land.at(pt[0], pt[2]), pt[2]]
            args = [tidy(v) for v in pt] if pt else [None, None, None]
            for fn in list(self.click_fns):
                self.fire(fn, *args)

    def lock_changed(self):
        if self.hint is not None:  # "Click the game to look around": not while it's locked, or under a screen
            covered = self.ui is not None and self.ui.showing
            self.hint.hide() if (self.locked or self.fake_lock or covered) else self.hint.show()

    def update(self, dt, real):
        if self.driving is not None:
            self.drive_keys()
        p = self.the_player
        if p is not None:
            p.update(dt, real)
            if self.phys is not None:
                self.phys.player_sync(p)
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


def _noise(x, z, seed):
    """Smooth value noise from 0 to 1 at (x, z): the same every run for the same seed."""
    ix, iz = math.floor(x), math.floor(z)
    fx, fz = ease(x - ix), ease(z - iz)

    def corner(i, j):
        h = (i * 374761393 + j * 668265263 + seed * 1442695041) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((h ^ (h >> 16)) & 0xFFFF) / 65535

    a, b, c, d = corner(ix, iz), corner(ix + 1, iz), corner(ix, iz + 1), corner(ix + 1, iz + 1)
    return a + (b - a) * fx + (c - a) * fz + (a - b - c + d) * fx * fz


class Terrain:
    """The land of a 3D world: a square of heights centred on 0, 0, that hills, lakes and brushes change.

    The heights live here (the player walks on them, things stand on them) and go to the page once per frame when
    they changed. Every edit uses the same smooth falloff, weight (1 - (d / r)²)² within r of its middle, so Tuff
    Engine's brush can do the same maths on its own copy while someone paints."""
    NAMES = [("style", "set_style"), ("hill", "hill"), ("mountain", "mountain"), ("dip", "dip"), ("lake", "lake"),
             ("valley", "valley"), ("raise", "raise_land"), ("lower", "lower_land"), ("smooth", "smooth"),
             ("flatten", "flatten"), ("water", "water"), ("height_at", "height_at")]
    WET = 0.15  # water this deep stops the player (the shore's edge is fine to stand in)

    def __init__(self, world, size, style):
        self.world, self.rt = world, world.rt
        self.size = float(size)
        self.n = n = clamp(int(math.floor(size / 1.5 + 0.5)) + 1, 65, 257)
        self.step = self.size / (n - 1)
        self.h = [0.0] * (n * n)  # row by row from -z to +z, each row from -x to +x
        self.sent = [0] * (n * n)  # the same, as the page gets them: kept up to date point by point as edits go
        self.style_name = style
        self.lakes = []  # [x, z, r, level, water node]
        self.sea = None  # [level, water node]
        self.edits = []  # for Tuff Engine (tuff.py --scene): each edit and the lines that made it
        self.alive = True
        self.phys_sent = None  # with physics on, the land is a heightfield of its own heights (physics.js)
        self.dirty = True  # the heights go with the first frame, after the setup's edits
        self.node = world.view.obj(world.scene, "terrain", size=self.size, n=n, style=style, shadow=True)
        self.native = world.rt.native("terrain", methods(self, "terrain", self.NAMES, world.rt), self.show_text)
        self.native.tg = self

    def show_text(self, nested=False):
        return f"<terrain {tidy(self.size)} wide>"

    def phys_spec(self):
        return {"kind": "static", "shape": "land"} if self.world.phys is not None else None

    def heights(self):
        """The heights to the hundredth of a metre (whole ones as 0, not 0.0: most of the land is often flat)."""
        return list(self.sent)

    def changed(self, k):
        v = round(self.h[k], 2)
        self.sent[k] = int(v) if v == int(v) else v

    def push(self):
        self.dirty = False
        self.world.view.set(self.node, heights=self.heights())

    # ---- the land's height
    def at(self, x, z):
        """The height at x, z, between the four points around it (bilinear); outside the square, the edge's."""
        n, half = self.n, self.size / 2
        fx = clamp((x + half) / self.step, 0.0, n - 1.0)
        fz = clamp((z + half) / self.step, 0.0, n - 1.0)
        i, j = min(int(fx), n - 2), min(int(fz), n - 2)
        tx, tz = fx - i, fz - j
        h, k = self.h, j * n + i
        a, b, c, d = h[k], h[k + 1], h[k + n], h[k + n + 1]
        return a + (b - a) * tx + (c - a) * tz + (a - b - c + d) * tx * tz

    def water_at(self, x, z):
        """The level of the water over the land at x, z (a lake's or the sea's), or None where it's dry."""
        g = self.at(x, z)
        level = self.sea[0] if self.sea is not None and g < self.sea[0] else None
        for lx, lz, r, lv, _ in self.lakes:
            if g < lv and (x - lx) ** 2 + (z - lz) ** 2 < (r * 1.04) ** 2 and (level is None or lv > level):
                level = lv
        return level

    def height_at(self, x, z=MISSING):
        x, z, _ = self.point([x, z], (), "height_at", "land:height_at(12, 4)")
        return tidy(self.at(x, z))

    # ---- reading an edit's inputs
    def point(self, args, defaults, what, example):
        """x, z (or one spot [x, z], or [x, y, z] from :random_spot) and the numbers after them, with the defaults
        for the ones left out. Gives (x, z, [numbers])."""
        rt = self.rt
        given = [a for a in args if a is not MISSING]
        first = rt.plain(given[0]) if given else None
        if isinstance(first, list):
            if len(first) not in (2, 3):
                raise rt.error(f":{what} needs a spot like [10, -5] (x and z), like {example}.")
            x, z, rest = first[0], first[-1], given[1:]
        elif len(given) < 2:
            raise rt.error(f":{what} needs x and z (where on the land), like {example}.")
        else:
            x, z, rest = given[0], given[1], given[2:]
        if len(rest) > len(defaults):
            raise rt.error(f":{what} got too many inputs.")
        nums = [rt.number(v, f":{what}") for v in list(rest) + list(defaults[len(rest):])]
        return rt.number(x, f":{what}"), rt.number(z, f":{what}"), nums

    def stroke(self, args, defaults, what, example):
        """A brush's inputs: one spot (x, z or [x, z]), or a stroke (a list of [x, z] spots), then the numbers.
        Gives ([(x, z), ...], [numbers])."""
        rt = self.rt
        first = rt.plain(args[0])
        if isinstance(first, list) and first and all(isinstance(rt.plain(p), list) for p in first):
            spots = []
            for p in first:
                p = rt.plain(p)
                if len(p) not in (2, 3):
                    raise rt.error(f":{what} needs spots like [[1, 2], [3, 2]] (each one x and z), like {example}.")
                spots.append((rt.number(p[0], f":{what}"), rt.number(p[-1], f":{what}")))
            rest = [a for a in args[1:] if a is not MISSING]
            if len(rest) > len(defaults):
                raise rt.error(f":{what} got too many inputs.")
            return spots, [rt.number(v, f":{what}") for v in rest + list(defaults[len(rest):])]
        x, z, nums = self.point(args, defaults, what, example)
        return [(x, z)], nums

    def radius(self, size, what, example):
        if size <= 0:
            raise self.rt.error(f":{what} needs a size above 0 (how wide it is), like {example}.")
        return size / 2

    # ---- changing the heights
    def points(self, x0, z0, x1, z1):
        """The grid's points inside a box: (index, x, z)."""
        n, step, half = self.n, self.step, self.size / 2
        i0, i1 = max(0, math.ceil((x0 + half) / step)), min(n - 1, math.floor((x1 + half) / step))
        j0, j1 = max(0, math.ceil((z0 + half) / step)), min(n - 1, math.floor((z1 + half) / step))
        for j in range(j0, j1 + 1):
            pz, row = j * step - half, j * n
            for i in range(i0, i1 + 1):
                yield row + i, i * step - half, pz

    def dab(self, x, z, r, fn):
        """Every point within r of (x, z) changes by fn(weight, index, x, z), the weight (1 - (d / r)²)²."""
        h, rr = self.h, r * r
        for k, px, pz in self.points(x - r, z - r, x + r, z + r):
            d2 = (px - x) ** 2 + (pz - z) ** 2
            if d2 < rr:
                q = 1 - d2 / rr
                h[k] += fn(q * q, k, px, pz)
                self.changed(k)

    def smooth_dab(self, x, z, r):
        """Each point moves toward the average of its 4 neighbours (as they were before this dab), by its weight."""
        old, n = self.h[:], self.n

        def toward(w, k, _px, _pz):
            i, j = k % n, k // n
            avg = (old[k - 1 if i > 0 else k] + old[k + 1 if i < n - 1 else k]
                   + old[k - n if j > 0 else k] + old[k + n if j < n - 1 else k]) / 4
            return (avg - old[k]) * w
        self.dab(x, z, r, toward)

    def riders(self, x0, z0, x1, z1):
        """What stands in this part of the land (objects and the player), with the land's height under each."""
        w = self.world
        out = [(t, self.at(t.x, t.z)) for t in w.things if isinstance(t, Thing) and t.alive and t.on_land
               and not getattr(t, "floor", False) and t.phys_kind != "dynamic"  # physics moves those with the land
               and x0 <= t.x <= x1 and z0 <= t.z <= z1]
        p = w.the_player
        if p is not None and x0 <= p.x <= x1 and z0 <= p.z <= z1:
            out.append((p, self.at(p.x, p.z)))
        return out

    def edit(self, op, args, box, change):
        """One edit: change() changes the heights inside box (x0, z0, x1, z1). Things standing there go up and
        down with the land, so their height above it stays what the program said."""
        riders = self.riders(*box)
        change()
        for t, before in riders:
            d = self.at(t.x, t.z) - before
            if d:
                t.y += d
                if isinstance(t, Player):
                    if t.body is not None:
                        t.body.y = t.y
                        t.body.push()
                    t.place_camera(1)
                else:
                    t.push()
        self.dirty = True
        if SCENE is not None:
            self.edits.append({"op": op, "args": [self.rt.plain(a) for a in args if a is not MISSING],
                               "made": list(SCENE.interp.lines)})
        return self.native

    def bump(self, op, args, x, z, r, fn):
        return self.edit(op, args, (x - r, z - r, x + r, z + r), lambda: self.dab(x, z, r, fn))

    def hill(self, x, z=MISSING, size=MISSING, height=MISSING):
        args, ex = [x, z, size, height], "land:hill(20, -10, 30, 8)"
        cx, cz, (sz, tall) = self.point(args, (30, 8), "hill", ex)
        return self.bump("hill", args, cx, cz, self.radius(sz, "hill", ex), lambda w, *_: tall * w)

    def dip(self, x, z=MISSING, size=MISSING, depth=MISSING):
        args, ex = [x, z, size, depth], "land:dip(10, 25, 16, 3)"
        cx, cz, (sz, deep) = self.point(args, (16, 3), "dip", ex)
        return self.bump("dip", args, cx, cz, self.radius(sz, "dip", ex), lambda w, *_: -deep * w)

    def mountain(self, x, z=MISSING, size=MISSING, height=MISSING):
        args, ex = [x, z, size, height], "land:mountain(-40, -50, 60, 35)"
        cx, cz, (sz, tall) = self.point(args, (60, 30), "mountain", ex)
        r = self.radius(sz, "mountain", ex)
        seed = (round(cx * 10) * 73856093 ^ round(cz * 10) * 19349663 ^ round(sz * 10) * 83492791) & 0x7FFFFFFF
        cell = max(2.0, sz / 8)

        def ridge(x, z, s):
            return 1 - abs(2 * _noise(x, z, s) - 1)

        def peak(w, _k, px, pz):  # a sharper top than a hill's, and rough: ridges in two sizes, and bumps
            fx, fz = px / cell, pz / cell
            rough = 0.5 * ridge(fx, fz, seed) + 0.3 * ridge(fx * 2.1, fz * 2.1, seed + 1) + 0.2 * _noise(fx * 4.3, fz * 4.3, seed + 2)
            return tall * w ** 1.5 * (0.75 + 0.25 * rough)
        return self.bump("mountain", args, cx, cz, r, peak)

    def lake(self, x, z=MISSING, size=MISSING, depth=MISSING):
        args, ex = [x, z, size, depth], "land:lake(-20, 30, 36, 4)"
        cx, cz, (sz, deep) = self.point(args, (30, 4), "lake", ex)
        r = self.radius(sz, "lake", ex)
        if deep <= 0:
            raise self.rt.error(f":lake needs a depth above 0 (how deep the water is), like {ex}.")
        level = self.at(cx, cz) - 0.2  # the water sits just below the ground that was there

        def dig():
            self.dab(cx, cz, r, lambda w, *_: -deep * w)
            w = self.world
            self.lakes.append([cx, cz, r, level, w.view.obj(w.scene, "water", x=cx, z=cz, y=level, r=r)])
        return self.edit("lake", args, (cx - r, cz - r, cx + r, cz + r), dig)

    def valley(self, x1, z1=MISSING, x2=MISSING, z2=MISSING, width=MISSING, depth=MISSING):
        ex = "land:valley(-60, 0, 60, 10, 18, 6)"
        rt = self.rt
        args = [x1, z1, x2, z2, width, depth]
        given = [a for a in args if a is not MISSING]
        if given and isinstance(rt.plain(given[0]), list):  # two spots: valley([x1, z1], [x2, z2], width, depth)
            ax, az, _ = self.point(given[:1], (), "valley", ex)
            if len(given) < 2 or not isinstance(rt.plain(given[1]), list):
                raise rt.error(f":valley needs where it starts and where it ends, like {ex}.")
            bx, bz, _ = self.point(given[1:2], (), "valley", ex)
            rest = given[2:]
        elif len(given) < 4:
            raise rt.error(f":valley needs where it starts (x1, z1) and where it ends (x2, z2), like {ex}.")
        else:
            ax, az, bx, bz = (rt.number(v, ":valley") for v in given[:4])
            rest = given[4:]
        if len(rest) > 2:
            raise rt.error(":valley got too many inputs.")
        width, depth = [rt.number(v, ":valley") for v in list(rest) + [12, 5][len(rest):]]
        r = self.radius(width, "valley", ex)
        dx, dz = bx - ax, bz - az
        ll = dx * dx + dz * dz

        def carve():
            h, rr = self.h, r * r
            for k, px, pz in self.points(min(ax, bx) - r, min(az, bz) - r, max(ax, bx) + r, max(az, bz) + r):
                t = clamp(((px - ax) * dx + (pz - az) * dz) / ll, 0.0, 1.0) if ll else 0.0
                d2 = (px - ax - dx * t) ** 2 + (pz - az - dz * t) ** 2
                if d2 < rr:
                    q = 1 - d2 / rr
                    h[k] -= depth * q * q
                    self.changed(k)
        return self.edit("valley", args, (min(ax, bx) - r, min(az, bz) - r, max(ax, bx) + r, max(az, bz) + r), carve)

    def brush(self, op, args, defaults, example, fn):
        """raise, lower, smooth and flatten: one dab, or a stroke (a dab at each spot, in order)."""
        spots, nums = self.stroke(args, defaults, op, example)
        r = self.radius(nums[0], op, example)

        def paint():
            for x, z in spots:
                fn(x, z, r, *nums[1:])
        xs, zs = [s[0] for s in spots], [s[1] for s in spots]
        return self.edit(op, args, (min(xs) - r, min(zs) - r, max(xs) + r, max(zs) + r), paint)

    def raise_land(self, x, z=MISSING, size=MISSING, amount=MISSING):
        return self.brush("raise", [x, z, size, amount], (8, 1), "land:raise(5, 5, 8, 1.5)",
                          lambda x, z, r, a: self.dab(x, z, r, lambda w, *_: a * w))

    def lower_land(self, x, z=MISSING, size=MISSING, amount=MISSING):
        return self.brush("lower", [x, z, size, amount], (8, 1), "land:lower(5, 5, 8, 1.5)",
                          lambda x, z, r, a: self.dab(x, z, r, lambda w, *_: -a * w))

    def smooth(self, x, z=MISSING, size=MISSING):
        return self.brush("smooth", [x, z, size], (8,), "land:smooth(5, 5, 8)", lambda x, z, r: self.smooth_dab(x, z, r))

    def flatten(self, x, z=MISSING, size=MISSING, height=MISSING):
        h = self.h
        return self.brush("flatten", [x, z, size, height], (8, 0), "land:flatten(5, 5, 8, 2)",
                          lambda x, z, r, to: self.dab(x, z, r, lambda w, k, *_: (to - h[k]) * w))

    # ---- how it looks, and its water
    def set_style(self, name):
        n = self.rt.text(name).strip().lower()
        if n not in TERRAIN_STYLES:
            raise self.rt.error(style_problem(n))
        self.style_name = n
        self.world.view.set(self.node, style=n)
        if SCENE is not None:
            self.edits.append({"op": "style", "args": [n], "made": list(SCENE.interp.lines)})
        return self.native

    def water(self, level):
        lv = self.rt.number(level, ":water")
        w = self.world
        if self.sea is None:  # the sea reaches past the land's edges, out to the fog
            self.sea = [lv, w.view.obj(w.scene, "water", x=0, z=0, y=lv, r=0, size=self.size * 4)]
        else:
            self.sea[0] = lv
            w.view.set(self.sea[1], y=lv)
        if SCENE is not None:
            self.edits.append({"op": "water", "args": [self.rt.plain(level)], "made": list(SCENE.interp.lines)})
        return self.native

    def node_ids(self):
        return [int(self.node)] + [int(lake[4]) for lake in self.lakes] + ([int(self.sea[1])] if self.sea else [])

    def dump(self, var, made):
        """What Tuff Engine's preview knows about the land (tuff.py --scene)."""
        hs = self.heights()
        return {"var": var, "ids": self.node_ids(), "made": made, "size": tidy(self.size), "n": self.n,
                "style": self.style_name, "heights": hs, "low": min(hs), "high": max(hs),
                "lakes": [{"x": tidy(x), "z": tidy(z), "r": tidy(r), "level": tidy(lv)} for x, z, r, lv, _ in self.lakes],
                "sea": tidy(self.sea[0]) if self.sea is not None else None, "edits": self.edits}


def animation_problem(name):
    return (f"object:animate can be \"walk\", \"idle\", \"wave\", \"auto\" or \"none\", not \"{name}\"."
            + did_you_mean(name, ANIMATIONS))


def kit(name):
    """A built-in model: (size, solid body, parts, solid). Parts are (type, engine props, main part?); every part
    casts and gets shadows, and colours vary a little from one model to the next. A part's "anim" says how the page
    moves the model (tuff_view_web/anim.js): a "tree", "pine", "bush" or "flower" sways in the wind, a "coin" spins
    and bobs, and each part of a "person" says which limb it is and where it turns ([style, role, pivot])."""
    size, body, parts, solid = _kit(name)
    return size, body, [(type_, {"shadow": True, **p}, main) for type_, p, main in parts], solid


def _kit(name):
    rnd = random.random
    shade = lambda base, spread=0.08: _shade(base, (rnd() - 0.5) * 2 * spread)
    if name == "tree":
        leaf = shade("#4f9d3a")
        bark = shade("#7a5230", 0.06)
        parts = [
            ("cylinder", {"rt": 0.15, "rb": 0.22, "h": 1.8, "y": 0.9, "seg": 10, "color": bark, "rough": 0.95, "anim": "tree"}, False),
            ("cylinder", {"rt": 0.21, "rb": 0.34, "h": 0.32, "y": 0.16, "seg": 10, "color": _shade(bark, -0.1), "rough": 0.95}, False),
            ("cylinder", {"rt": 0.035, "rb": 0.075, "h": 0.62, "x": 0.25, "y": 1.6, "rz": -45, "seg": 6, "color": bark, "rough": 0.95}, False),
        ]
        # Clumps of leaves, lighter at the top, each tree's a little differently placed.
        for r, x, y, z, light in ((0.88, 0, 2.22, 0, 0), (0.62, 0.56, 2.52, 0.24, 0.07), (0.6, -0.52, 2.46, -0.3, -0.07),
                                  (0.54, -0.22, 2.34, 0.55, -0.02), (0.5, 0.04, 2.92, -0.06, 0.14)):
            parts.append(("sphere", {"r": r, "x": x + (rnd() - 0.5) * 0.12, "y": y, "z": z + (rnd() - 0.5) * 0.12, "sy": 0.92, "seg": 14,
                                     "color": _shade(leaf, light), "rough": 0.7}, True))
        return ((2.2, 3.4, 2.2), (0.5, 3.4, 0.5), parts, True)
    if name == "pine":
        leaf = shade("#2f6b3a")
        bark = shade("#6b4428", 0.06)
        parts = [("cylinder", {"rt": 0.1, "rb": 0.19, "h": 1.3, "y": 0.65, "seg": 8, "color": bark, "rough": 0.95, "anim": "pine"}, False)]
        for i, (r, h, y) in enumerate([(1.15, 1.3, 1.3), (0.95, 1.15, 1.95), (0.72, 1.0, 2.6), (0.46, 0.9, 3.25)]):
            parts.append(("cone", {"r": r, "h": h, "y": y, "seg": 11, "ry": rnd() * 32, "color": _shade(leaf, -0.05 + i * 0.05),
                                   "rough": 0.8, "flat": True}, True))
        return ((2.3, 3.9, 2.3), (0.5, 3.9, 0.5), parts, True)
    if name == "rock":
        s = 0.8 + rnd() * 0.5
        stone = shade(random.choice(["#8e8e86", "#8a8478", "#80868a"]), 0.08)
        turn, lean = rnd() * 360, (rnd() - 0.5) * 14
        parts = [
            ("sphere", {"r": 0.65, "y": 0.26 * s, "sx": s, "sy": 0.7 * s, "sz": 0.92 * s, "ry": turn, "rz": lean, "seg": 8,
                        "color": stone, "rough": 0.95, "flat": True}, True),
            ("sphere", {"r": 0.36, "x": 0.44 * s, "y": 0.08 * s, "z": 0.3 * s, "sx": s, "sy": 0.7 * s, "sz": 0.9 * s, "ry": turn + 40,
                        "seg": 6, "color": _shade(stone, -0.08), "rough": 0.95, "flat": True}, True),
        ]
        if rnd() < 0.5:  # some have moss on top: the same shape, a little smaller, poking out of the top
            parts.append(("sphere", {"r": 0.65, "y": 0.33 * s, "sx": 0.84 * s, "sy": 0.62 * s, "sz": 0.78 * s, "ry": turn, "rz": lean,
                                     "seg": 8, "color": shade("#5d7f3a", 0.06), "rough": 1, "flat": True}, False))
        return ((1.3 * s, 0.85 * s, 1.2 * s), None, parts, True)
    if name == "bush":
        leaf = shade("#3f8a35")
        parts = [
            ("sphere", {"r": 0.55, "y": 0.45, "sy": 0.9, "seg": 14, "color": leaf, "rough": 0.75, "anim": "bush"}, True),
            ("sphere", {"r": 0.42, "x": 0.45, "y": 0.34, "z": 0.1, "seg": 12, "color": _shade(leaf, 0.07), "rough": 0.75}, True),
            ("sphere", {"r": 0.4, "x": -0.42, "y": 0.32, "z": -0.15, "seg": 12, "color": _shade(leaf, -0.07), "rough": 0.75}, True),
            ("sphere", {"r": 0.34, "x": 0.02, "y": 0.34, "z": 0.42, "seg": 12, "color": _shade(leaf, 0.03), "rough": 0.75}, True),
            ("sphere", {"r": 0.3, "x": -0.08, "y": 0.66, "z": -0.05, "seg": 12, "color": _shade(leaf, 0.12), "rough": 0.75}, True),
        ]
        if rnd() < 0.45:  # berries
            berry = random.choice(["#d63a4a", "#7a4ad6", "#f2f2f2"])
            for bx, by, bz in ((0.32, 0.55, 0.32), (-0.4, 0.5, 0.2), (0.6, 0.38, -0.12), (-0.15, 0.32, 0.72)):
                parts.append(("sphere", {"r": 0.045, "x": bx, "y": by, "z": bz, "seg": 8, "color": berry, "rough": 0.35}, False))
        return ((1.5, 0.95, 1.5), None, parts, False)
    if name == "flower":
        petal = random.choice(["#ff5d8f", "#ffd23f", "#ffffff", "#b388ff", "#ff8a3d"])
        middle = "#7a4a1e" if petal == "#ffd23f" else "#ffc93d"
        parts = [
            ("cylinder", {"r": 0.018, "h": 0.42, "y": 0.21, "seg": 6, "color": "#3f8a35", "anim": "flower"}, False),
            ("sphere", {"r": 0.06, "x": 0.055, "y": 0.13, "sx": 1.6, "sy": 0.3, "sz": 0.7, "rz": 25, "seg": 8, "color": "#4a9a3c"}, False),
        ]
        for ry in (0, 60, 120):  # three crossed ovals make six petals
            parts.append(("sphere", {"r": 0.1, "y": 0.43, "sy": 0.22, "sz": 0.38, "ry": ry, "seg": 10, "color": _shade(petal, (rnd() - 0.5) * 0.08),
                                     "rough": 0.6}, True))
        parts.append(("sphere", {"r": 0.04, "y": 0.445, "sy": 0.7, "seg": 8, "color": middle, "rough": 0.9}, False))
        return ((0.3, 0.5, 0.3), None, parts, False)
    if name == "house":
        wall = shade("#ece0c8", 0.04)
        trim = shade("#7a5536", 0.06)
        frame = "#f4efe6"
        roof = shade(random.choice(["#b5483b", "#a8443a", "#9c4c3c"]), 0.05)
        glass = {"color": "#a9d8f5", "emissive": "#1d3550", "rough": 0.1, "metal": 0.3}
        parts = [
            ("box", {"w": 3.12, "h": 0.24, "d": 3.12, "y": 0.12, "color": shade("#8f8a80", 0.05), "rough": 0.95}, False),
            ("box", {"w": 3, "h": 1.98, "d": 3, "y": 1.21, "color": wall, "rough": 0.9}, True),
            # The roof's two slopes and its ridge, over the gables: a prism along x (a 3-sided cylinder on its side) in
            # the walls' colour.
            ("box", {"w": 3.5, "h": 0.1, "d": 2.26, "y": 2.93, "z": 0.86, "rx": 38.9, "color": roof, "rough": 0.75}, False),
            ("box", {"w": 3.5, "h": 0.1, "d": 2.26, "y": 2.93, "z": -0.86, "rx": -38.9, "color": roof, "rough": 0.75}, False),
            ("box", {"w": 3.6, "h": 0.1, "d": 0.2, "y": 3.63, "color": _shade(roof, -0.25), "rough": 0.8}, False),
            ("cylinder", {"r": 1, "h": 2.98, "seg": 3, "y": 2.64, "rx": -90, "rz": -90, "sx": 1.72, "sz": 0.86, "color": wall,
                          "rough": 0.9, "flat": True}, True),
            ("box", {"w": 0.34, "h": 0.9, "d": 0.34, "x": 0.85, "y": 3.05, "z": -0.55, "color": shade("#9a5a44", 0.06), "rough": 0.95}, False),
            ("box", {"w": 0.42, "h": 0.08, "d": 0.42, "x": 0.85, "y": 3.52, "z": -0.55, "color": "#5d5d5d", "rough": 0.9}, False),
            # the door, its frame, its knob and a step
            ("box", {"w": 0.86, "h": 1.36, "d": 0.05, "y": 0.9, "z": 1.51, "color": trim, "rough": 0.85}, False),
            ("box", {"w": 0.7, "h": 1.24, "d": 0.06, "y": 0.86, "z": 1.52, "color": shade("#6b4428", 0.06), "rough": 0.85}, False),
            ("sphere", {"r": 0.045, "x": 0.24, "y": 0.84, "z": 1.565, "seg": 10, "color": "#d9b45a", "metal": 0.8, "rough": 0.3,
                        "emissive": "#3a2a00"}, False),
            ("box", {"w": 1.0, "h": 0.12, "d": 0.32, "y": 0.06, "z": 1.66, "color": "#9a958b", "rough": 0.95}, False),
        ]
        for cx in (-1.46, 1.46):  # timber corners
            for cz in (-1.46, 1.46):
                parts.append(("box", {"w": 0.16, "h": 1.98, "d": 0.16, "x": cx, "y": 1.21, "z": cz, "color": trim, "rough": 0.85}, False))
        for wx in (-0.85, 0.85):  # front windows: frame, glass, cross bars, sill
            parts += [
                ("box", {"w": 0.66, "h": 0.62, "d": 0.05, "x": wx, "y": 1.45, "z": 1.51, "color": frame, "rough": 0.7}, False),
                ("box", {"w": 0.54, "h": 0.5, "d": 0.05, "x": wx, "y": 1.45, "z": 1.525, **glass}, False),
                ("box", {"w": 0.04, "h": 0.5, "d": 0.03, "x": wx, "y": 1.45, "z": 1.555, "color": frame, "rough": 0.7}, False),
                ("box", {"w": 0.54, "h": 0.04, "d": 0.03, "x": wx, "y": 1.45, "z": 1.555, "color": frame, "rough": 0.7}, False),
                ("box", {"w": 0.74, "h": 0.06, "d": 0.14, "x": wx, "y": 1.12, "z": 1.56, "color": trim, "rough": 0.85}, False),
            ]
        for sx in (-1.51, 1.51):  # a window on each side
            parts += [
                ("box", {"w": 0.05, "h": 0.62, "d": 0.66, "x": sx, "y": 1.45, "color": frame, "rough": 0.7}, False),
                ("box", {"w": 0.05, "h": 0.5, "d": 0.54, "x": sx * 1.01, "y": 1.45, **glass}, False),
                ("box", {"w": 0.03, "h": 0.5, "d": 0.04, "x": sx * 1.02, "y": 1.45, "color": frame, "rough": 0.7}, False),
            ]
        return ((3.2, 3.6, 3.2), (3.0, 2.2, 3.0), parts, True)
    if name == "hut":
        thatch = shade("#d9b45a", 0.06)
        return ((2.8, 3.1, 2.8), (2.4, 1.7, 2.4), [
            ("cylinder", {"r": 1.32, "h": 0.2, "y": 0.1, "seg": 16, "color": shade("#8f8a80", 0.05), "rough": 0.95, "flat": True}, False),
            ("cylinder", {"r": 1.25, "h": 1.5, "y": 0.95, "seg": 18, "color": shade("#b07d45", 0.06), "rough": 0.95}, True),
            ("torus", {"r": 1.265, "tube": 0.035, "y": 0.55, "rx": 90, "seg": 36, "color": "#6e4a26", "rough": 0.9}, False),
            ("torus", {"r": 1.265, "tube": 0.035, "y": 1.4, "rx": 90, "seg": 36, "color": "#6e4a26", "rough": 0.9}, False),
            ("cone", {"r": 1.8, "h": 1.0, "y": 2.15, "seg": 18, "color": thatch, "rough": 1, "flat": True}, False),
            ("cone", {"r": 1.25, "h": 1.1, "y": 2.55, "seg": 18, "ry": 10, "color": _shade(thatch, 0.07), "rough": 1, "flat": True}, False),
            ("cylinder", {"r": 0.05, "h": 0.22, "y": 3.05, "seg": 6, "color": "#6e4a26"}, False),
            ("box", {"w": 0.74, "h": 1.24, "d": 0.1, "y": 0.82, "z": 1.2, "color": "#8a6038", "rough": 0.9}, False),
            ("box", {"w": 0.58, "h": 1.08, "d": 0.1, "y": 0.76, "z": 1.23, "color": "#4a2f1a", "rough": 0.9}, False),
        ], True)
    if name == "sign":
        board = shade("#c08a4d", 0.05)
        edge = _shade(board, -0.3)
        return ((1.2, 1.6, 0.2), (0.3, 1.6, 0.2), [
            ("cylinder", {"rt": 0.055, "rb": 0.065, "h": 1.5, "y": 0.75, "z": -0.07, "seg": 8, "color": "#6b4428", "rough": 0.95}, False),
            ("box", {"w": 1.12, "h": 0.52, "d": 0.06, "y": 1.25, "color": board, "rough": 0.85}, True),
            ("box", {"w": 1.1, "h": 0.014, "d": 0.066, "y": 1.25, "color": edge, "rough": 0.9}, False),
            ("box", {"w": 1.2, "h": 0.07, "d": 0.09, "y": 1.525, "color": edge, "rough": 0.85}, False),
            ("box", {"w": 1.2, "h": 0.07, "d": 0.09, "y": 0.975, "color": edge, "rough": 0.85}, False),
            ("box", {"w": 0.07, "h": 0.6, "d": 0.09, "x": -0.565, "y": 1.25, "color": edge, "rough": 0.85}, False),
            ("box", {"w": 0.07, "h": 0.6, "d": 0.09, "x": 0.565, "y": 1.25, "color": edge, "rough": 0.85}, False),
        ], True)
    if name == "crate":
        wood = shade("#b07a42", 0.05)
        edge = _shade(wood, -0.3)
        parts = [
            ("box", {"w": 0.84, "h": 0.84, "d": 0.84, "y": 0.45, "color": wood, "rough": 0.85}, True),
            ("box", {"w": 0.9, "h": 0.1, "d": 0.9, "y": 0.05, "color": edge, "rough": 0.85}, False),
            ("box", {"w": 0.9, "h": 0.1, "d": 0.9, "y": 0.85, "color": edge, "rough": 0.85}, False),
        ]
        for cx in (-0.4, 0.4):  # corner posts
            for cz in (-0.4, 0.4):
                parts.append(("box", {"w": 0.1, "h": 0.7, "d": 0.1, "x": cx, "y": 0.45, "z": cz, "color": edge, "rough": 0.85}, False))
        for f in (-0.43, 0.43):  # a brace across each side
            parts.append(("box", {"w": 0.98, "h": 0.09, "d": 0.03, "y": 0.45, "z": f, "rz": 45 * (1 if f > 0 else -1), "color": edge, "rough": 0.85}, False))
            parts.append(("box", {"w": 0.03, "h": 0.09, "d": 0.98, "x": f, "y": 0.45, "rx": 45 * (1 if f > 0 else -1), "color": edge, "rough": 0.85}, False))
        return ((0.9, 0.9, 0.9), None, parts, True)
    if name == "fence":
        wood = shade("#8a6038", 0.05)
        rail = shade("#b5895a", 0.05)
        parts = []
        for px in (-0.93, 0, 0.93):
            h = 0.92 if px else 0.86
            parts.append(("box", {"w": 0.14 if px else 0.1, "h": h, "d": 0.14 if px else 0.1, "x": px, "y": h / 2, "color": wood, "rough": 0.9}, False))
            parts.append(("cone", {"r": 0.1 if px else 0.071, "h": 0.1, "x": px, "y": h + 0.05, "ry": 45, "seg": 4, "color": wood, "rough": 0.9,
                                   "flat": True}, False))
        parts += [
            ("box", {"w": 2.0, "h": 0.12, "d": 0.06, "y": 0.72, "z": 0.05, "color": rail, "rough": 0.85}, True),
            ("box", {"w": 2.0, "h": 0.12, "d": 0.06, "y": 0.38, "z": 0.05, "color": _shade(rail, -0.06), "rough": 0.85}, True),
        ]
        return ((2.0, 1.0, 0.16), None, parts, True)
    if name == "coin":
        gold = {"color": "#f2c230", "emissive": "#6a5000", "metal": 0.45, "rough": 0.35}
        return ((0.7, 1.3, 0.12), None, [
            ("cylinder", {"r": 0.3, "h": 0.07, "y": 0.9, "rx": 90, "seg": 28, **gold, "anim": "coin"}, True),
            ("torus", {"r": 0.3, "tube": 0.035, "y": 0.9, "seg": 36, **gold}, True),
            ("cylinder", {"r": 0.16, "h": 0.1, "y": 0.9, "rx": 90, "seg": 6, **gold, "color": "#ffd95a", "flat": True}, True),
        ], False)
    if name == "chest":
        wood = shade("#9a6234", 0.05)
        iron = {"color": "#4a4d52", "metal": 0.6, "rough": 0.45}
        return ((0.9, 0.75, 0.6), None, [
            ("box", {"w": 0.86, "h": 0.42, "d": 0.56, "y": 0.21, "color": wood, "rough": 0.85}, True),
            ("cylinder", {"r": 0.28, "h": 0.86, "y": 0.42, "rz": 90, "seg": 18, "color": _shade(wood, 0.06), "rough": 0.85}, True),
            ("box", {"w": 0.08, "h": 0.44, "d": 0.58, "x": -0.3, "y": 0.21, **iron}, False),
            ("box", {"w": 0.08, "h": 0.44, "d": 0.58, "x": 0.3, "y": 0.21, **iron}, False),
            ("cylinder", {"r": 0.29, "h": 0.08, "x": -0.3, "y": 0.42, "rz": 90, "seg": 18, **iron}, False),
            ("cylinder", {"r": 0.29, "h": 0.08, "x": 0.3, "y": 0.42, "rz": 90, "seg": 18, **iron}, False),
            ("box", {"w": 0.12, "h": 0.15, "d": 0.05, "y": 0.42, "z": 0.29, "color": "#f2c230", "emissive": "#3a2a00", "metal": 0.7,
                     "rough": 0.3}, False),
        ], True)
    if name == "person":
        return ((0.7, 1.75, 0.5), None, person_parts(), True)
    raise KeyError(name)


def person_parts(shirt=None, skin=None, hair=None, pants=None):
    """A person (the kit's, and the player in third person), facing -z like everything that walks forward: legs,
    arms, hips, a body and a head. Each part tells anim.js which part it is and where it turns (hips, shoulders and
    the neck), so it can walk, breathe and wave."""
    shirt = shirt or random.choice(["#e5484d", "#3574f0", "#2fa36b", "#f2a33a", "#8e5bd8", "#14b8a6"])
    skin = skin or random.choice(["#f1c9a5", "#e0ac7e", "#c68a5c", "#8d5a3b", "#ffd9b8"])
    hair = hair or random.choice(["#2b2018", "#5a3a22", "#a8692e", "#e3c06b", "#1c1c1c", "#b5482b"])
    pants = pants or random.choice(["#2f3e5c", "#3b3b44", "#5b4636", "#24456b"])

    def part(type_, role, pivot, main=False, **p):
        return (type_, {**p, "anim": ["person", role, pivot]}, main)
    parts = []
    for side, x in (("l", -1), ("r", 1)):  # its right is +x (it faces -z)
        hip, shoulder = [0.1 * x, 0.8, 0], [0.29 * x, 1.38, 0]
        parts += [
            part("capsule", "leg_" + side, hip, r=0.085, h=0.56, x=0.1 * x, y=0.44, seg=12, color=pants, rough=0.9),
            part("sphere", "leg_" + side, hip, r=0.085, x=0.1 * x, y=0.055, z=-0.04, sy=0.6, sz=1.45, seg=10, color="#2a2522", rough=0.7),
            part("capsule", "arm_" + side, shoulder, True, r=0.065, h=0.46, x=0.29 * x, y=1.1, seg=10, color=shirt, rough=0.85),
            part("sphere", "arm_" + side, shoulder, r=0.068, x=0.29 * x, y=0.79, seg=10, color=skin, rough=0.7),
        ]
    neck = [0, 1.46, 0]
    parts += [
        part("cylinder", "body", None, rt=0.19, rb=0.18, h=0.16, y=0.82, seg=14, color=pants, rough=0.9),
        part("capsule", "torso", None, True, r=0.2, h=0.36, y=1.12, sz=0.72, seg=14, color=shirt, rough=0.85),
        part("sphere", "head", neck, r=0.18, y=1.57, seg=18, color=skin, rough=0.65),
        part("sphere", "head", neck, r=0.185, y=1.65, z=0.04, sy=0.78, seg=18, color=hair, rough=0.8),
        part("sphere", "head", neck, r=0.17, y=1.56, z=0.065, sy=0.9, seg=16, color=hair, rough=0.8),
        part("sphere", "head", neck, r=0.026, x=-0.065, y=1.59, z=-0.163, seg=8, color="#1d1d24", rough=0.3),
        part("sphere", "head", neck, r=0.026, x=0.065, y=1.59, z=-0.163, seg=8, color="#1d1d24", rough=0.3),
    ]
    return parts


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


class Thing(Physical):
    """An object in a 3D world: a shape, a model from the kit, the ground, a light or something held."""
    KIND = "object"
    NAMES = [
        ("x", "get_x"), ("y", "get_y"), ("z", "get_z"), ("spot", "spot"), ("move", "move"), ("move_to", "move_to"),
        ("glide", "glide"), ("forward", "forward"), ("turn", "turn"), ("turn_to", "turn_to"), ("angle", "angle"),
        ("spin", "spin"), ("look_at", "look_at"), ("speed", "speed"), ("shake", "shake"), ("fall", "fall"),
        ("fallen", "is_fallen"), ("grow", "grow"), ("regrow", "regrow"), ("swing", "swing"), ("size", "size"),
        ("scale", "set_scale"),
        ("animate", "animate"),
        ("color", "set_color"), ("glow", "glow"), ("hide", "hide"), ("show", "show"), ("remove", "remove"),
        ("solid", "solid"), ("touches", "touches"), ("distance", "distance"), ("label", "label"),
        ("clicked", "clicked"), ("set", "set"), ("get", "get"),
        ("physics", "physics"), ("mass", "mass"), ("bounce", "bounce"), ("friction", "friction"), ("push", "kick"),
        ("velocity", "velocity"), ("on_hit", "on_hit"), ("sleep", "sleep"), ("wake", "wake"),
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
        self.on_land = parent is None and not camera  # held things have their own x, y, z (in the hand)
        self.phys_init()
        self.quat = None  # how physics has turned it ([x, y, z, w]), once it has
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
        self.native = world.rt.native(self.KIND, methods(self, self.KIND, self.NAMES, world.rt), self.show_text)
        self.native.tg = self
        if world.phys is not None:
            world.phys.dirty.add(self)  # solid things get a body that doesn't move (once it's settled, at the frame)

    def show_text(self, nested=False):
        return f"<{self.kind} at {tidy(self.x)}, {tidy(self.y)}, {tidy(self.z)}>"

    def num(self, v, what):
        return self.rt.number(v, what)

    def height(self):
        return self.dims[1] * self.k[1]

    def ground(self):
        """The land's height under it (0 without a terrain). Its y, for the program, is how far above that it is."""
        land = self.world.land
        return land.at(self.x, self.z) if land is not None and self.on_land else 0.0

    # ---- sending changes
    def send(self, node, **props):
        """Send changes to one of its parts in the page. A removed object sends nothing: the page has let it go."""
        if self.alive:
            self.world.view.set(node, **props)

    def push(self):
        self.send(self.node, x=self.x, y=self.y, z=self.z)
        self.push_label()

    def push_label(self):
        if self.label_node is not None:
            top = self.y + (0.9 if self.fallen else self.height() + 0.25)
            self.send(self.label_node, x=self.x, y=top, z=self.z)

    def push_rotation(self):
        if self.quat is not None and not self.tilt and not self.pitch:  # tumbled by physics: as it lies
            rx, ry, rz = euler_of_quat(self.quat)
        else:
            rx, ry, rz = euler(self.heading, self.tilt_axis, self.tilt, self.pitch)
        self.send(self.node, rx=rx, ry=ry, rz=rz)

    def turn_by(self, degrees, to=None):
        """Turns it about the up axis (clockwise from above), however physics has turned it (to: to face that way)."""
        if self.quat is not None:
            self.quat = quat_mul(yaw_quat(-(degrees if to is None else to - self.heading)), self.quat)
            self.heading = heading_of(self.quat)
        else:
            self.heading = (self.heading + degrees) % 360 if to is None else to % 360
        self.push_rotation()

    # ---- physics (see Physical)
    def can_have_physics(self, kind):
        if not self.on_land:
            raise self.rt.error("Only things in the world can use physics, not something the player holds.")
        if getattr(self, "floor", False):
            raise self.rt.error(f"The {self.kind} is solid for physics already: it doesn't need :physics.")
        if kind != "off":
            self.solid_ = True

    def after_physics(self):
        self.push_rotation()

    def phys_spec(self):
        """Its body for the page (physics.js): its own (thing:physics), or a fixed one for something solid, the
        ground or the island. None: no body."""
        w = self.world
        if not self.alive or w.phys is None or not self.on_land:
            return None
        kind = self.phys_kind
        base = {"mass": self.mass_, "bounce": self.bounce_, "friction": self.friction_, "hits": bool(self.hit_fns)}
        if kind is None:
            if getattr(self, "floor", False):
                half = self.dims[0] / 2
                if self.kind == "island":  # the grass's cylinder, its top at 0
                    return {**base, "kind": "static", "shape": "cylinder", "size": [1.5, tidy(half)], "cy": -1.5}
                return {**base, "kind": "static", "shape": "box", "size": [tidy(half), 0.5, tidy(self.dims[2] / 2)], "cy": -0.5}
            if not self.solid_ or self.fallen:
                return None
            kind = "static"
        shape, size, cy = self.phys_shape(kind)
        return {**base, "kind": kind, "shape": shape, "size": size, "cy": cy}

    def phys_shape(self, kind):
        """(shape, size, how high its middle is above its position): a ball for a sphere, a cylinder or a cone for
        those, a capsule for a person, and a box for everything else (a fixed tree's is its trunk)."""
        kx, ky, kz = self.k
        w, h, d = self.body if kind == "static" and self.body else self.dims
        hy = max(h * ky, 0.02) / 2
        if self.kind == "sphere":
            r = w / 2 * max(kx, ky, kz)
            return "ball", tidy(r), tidy(r)
        if self.kind in ("cylinder", "cone"):
            return self.kind, [tidy(hy), tidy(w * max(kx, kz) / 2)], tidy(hy)
        if self.kind in CAPSULE_KINDS:
            r = max(w * kx, d * kz) / 2
            return "capsule", [tidy(max(0.01, hy - r)), tidy(r)], tidy(hy)
        return "box", [tidy(w * kx / 2), tidy(hy), tidy(d * kz / 2)], tidy(hy)

    def from_physics(self, b):
        """Where physics moved it: [id, x, y, z, qx, qy, qz, qw, vx, vy, vz] (it isn't sent back). y is its lowest point."""
        self.x, self.y, self.z = b[1], b[2], b[3]
        self.quat = b[4:8]
        self.heading = heading_of(self.quat)
        self.vel = b[8:11]
        self.push_label()  # its label follows it (the thing itself is where the page put it)

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
        return tidy(self.y - self.ground())

    def get_z(self):
        return tidy(self.z)

    def spot(self):
        return [tidy(self.x), tidy(self.y - self.ground()), tidy(self.z)]

    def move(self, dx, dy=0, dz=0):
        dx, dy, dz = self.num(dx, ":move"), self.num(dy, ":move"), self.num(dz, ":move")
        g = self.ground()
        self.x += dx
        self.z += dz
        self.y += dy + self.ground() - g  # over a hill, it keeps its height above the land
        self.push()
        return self.native

    def move_to(self, x, y=MISSING, z=MISSING):
        self.x, self.y, self.z, _ = self.world.where([x, y, z], (), "move_to")
        self.y += self.ground()
        self.anims = [a for a in self.anims if a[0] != "glide"]
        self.push()
        return self.native

    def glide(self, x, y=MISSING, z=MISSING, seconds=MISSING):
        tx, ty, tz, (secs,) = self.world.where([x, y, z, seconds], (1.0,), "glide")
        secs = max(0.01, self.num(secs, ":glide"))
        self.anims = [a for a in self.anims if a[0] != "glide"]
        # Heights above the land: a glide over a hill goes over it.
        self.anims.append(["glide", 0.0, secs, (self.x, self.y - self.ground(), self.z), (tx, ty, tz)])
        self.busy()
        return self.native

    def forward(self, distance):
        d = self.num(distance, ":forward")
        h = math.radians(self.heading)
        g = self.ground()
        self.x += math.sin(h) * d
        self.z -= math.cos(h) * d
        self.y += self.ground() - g
        self.push()
        return self.native

    def turn(self, degrees):
        self.turn_by(self.num(degrees, ":turn"))
        return self.native

    def turn_to(self, degrees):
        self.turn_by(0, to=self.num(degrees, ":turn_to"))
        return self.native

    def angle(self):
        return tidy(self.heading)

    def spin(self, a, b=MISSING, c=MISSING):
        if self.dynamic():  # a twist (an angular kick): about x, y and z, or one number about the up axis
            v = [0, self.num(a, ":spin"), 0] if b is MISSING and not isinstance(self.rt.plain(a), list) else \
                self.phys_vector([a, b, c], "spin", f"{self.EXAMPLE}:spin(0, 2, 0)")
            self.game.phys.send("spin", int(self.node), *v)
            return self.native
        if b is not MISSING or isinstance(self.rt.plain(a), list):
            raise self.rt.error(f"{self.kind}:spin(x, y, z) twists things with physics. Without physics it spins "
                                f"at so many degrees a second, like {self.kind}:spin(90).")
        self.spin_speed = self.num(a, ":spin")
        self.busy()
        return self.native

    def look_at(self, x, y=MISSING, z=MISSING):
        t = thing_of(x)
        if isinstance(t, (Thing, Player)):
            tx, tz = t.x, t.z
        else:
            tx, _, tz, _ = self.world.where([x, y, z], (), "look_at")
        if (tx, tz) != (self.x, self.z):
            self.turn_by(0, to=math.degrees(math.atan2(tx - self.x, -(tz - self.z))))
        return self.native

    def speed(self, vx=MISSING, vy=0, vz=0):
        if vx is MISSING:  # how fast it goes (metres a second)
            return tidy(math.hypot(*self.velocity_now()))
        v = [self.num(vx, ":speed"), self.num(vy, ":speed"), self.num(vz, ":speed")]
        if self.dynamic():
            self.vel = v
            self.game.phys.send("velocity", int(self.node), *v)
            return self.native
        self.vx, self.vy, self.vz = v
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
        if self.world.phys is not None:
            self.world.phys.dirty.add(self)  # a fallen tree is no longer in the way
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

    def animate(self, how="auto"):
        """How it moves by itself, in the page (anim.js): a person can "walk", "idle" (stand breathing) or "wave";
        "auto" is the model's own way (a person walks while it moves, trees sway, coins spin); "none" holds it still."""
        name = self.rt.text(how).strip().lower()
        if name not in ANIMATIONS:
            raise self.rt.error(animation_problem(name))
        if name in ("walk", "idle", "wave") and self.kind not in ("person", "player"):
            raise self.rt.error(f"Only a person can {name}: world:spawn(\"person\") makes one. This is a {self.kind}.")
        self.send(self.node, anim=name)
        return self.native

    def stand_up(self):
        self.fallen = False
        self.tilt = 0.0
        if getattr(self, "was_solid", None) is not None:
            self.solid_ = self.was_solid
        if self.world.phys is not None:
            self.world.phys.dirty.add(self)
        self.push_rotation()
        self.push()

    def tick(self, dt):
        moved = rotated = False
        if self.vx or self.vy or self.vz:
            g = self.ground()
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.z += self.vz * dt
            if self.world.land is not None:
                self.y += self.ground() - g
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
                self.y += self.ground()
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
            if self.dynamic():  # a glide carries it: no speed builds up meanwhile
                self.game.phys.send("velocity", int(self.node), 0, 0, 0)
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
        self.phys_changed()  # its body grows with it
        return self.native

    def size_base(self):
        return self.dims

    def set_scale(self, n):
        n = self.num(n, ":scale")
        self.k = [n, n, n]
        self.push_scale()
        self.push()
        self.phys_changed()
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
        if w.phys is not None:
            w.phys.dirty.discard(self)  # its body went with its object
            if w.driving is self:
                w.driving = None
                w.stop_chase()

    def solid(self, on=True):
        self.solid_ = self.rt.truthy(on)
        if self.world.phys is not None:
            self.world.phys.dirty.add(self)
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
            ty = self.world.above(tx, ty, tz)
        return tidy(math.dist((self.x, self.y, self.z), (tx, ty, tz)))

    def label(self, text):
        t = self.rt.text(text)
        self.label_text = t
        w = self.world
        if self.label_node is None:
            if not t or not self.alive:
                return self.native
            self.label_node = w.view.obj(w.scene, "label", text=t)
            self.push_label()
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
        ("distance", "distance"), ("hide", "hide"), ("show", "show"), ("on_hit", "on_hit"),
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
        self.hit_fns = []
        self.teleported = False  # moved somewhere by the program: physics puts its capsule there (no walking there)
        if world is None:
            return
        self.cam_pos = None
        self.native = world.rt.native("player", methods(self, "player", self.NAMES, world.rt),
                                      lambda nested=False: f"<player at {tidy(self.x)}, {tidy(self.y)}, {tidy(self.z)}>")
        self.native.tg = self
        if mode == "third person":
            parts = [(t, {**p, "shadow": True}, main) for t, p, main in person_parts("#3574f0", "#f1c9a5", "#5a3a22", "#2f3e5c")]
            self.body = Thing(world, "player", 0, 0, 0, (0.6, self.TALL, 0.6), parts, pick=False)
            self.body.solid_ = False
            world.things.pop(self.body, None)
        hud = world.hud()
        if mode == "first person":
            world.crosshair = hud.make("circle", world.W / 2, world.H / 2, {"r": 3.5, "color": "#ffffff", "stroke": "#000000",
                                                                            "lw": 1.5, "alpha": 0.85, "z": 5e5}, own=False)
        world.hint = hud.make("text", world.W / 2, world.H - 26, {"text": "Click the game to look around with the mouse (Esc lets go)",
                                                                  "size": 15, "bold": False, "color": "#ffffff", "alpha": 0.8,
                                                                  "ax": 0.5, "ay": 0.5, "z": 5e5}, own=False)
        if world.autopilot or SCENE is not None:
            world.hint.hide()
        if SCENE is not None and world.crosshair is not None:
            world.crosshair.hide()
        if world.land is not None:  # it starts standing on the land
            self.y = world.land.at(0, 0)
            if self.body is not None:
                self.body.y = self.y
                self.body.push()
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
        return tidy(self.y - self.world.ground_y(self.x, self.z))

    def get_z(self):
        return tidy(self.z)

    def spot(self):
        return [tidy(self.x), tidy(self.y - self.world.ground_y(self.x, self.z)), tidy(self.z)]

    def move_to(self, x, y=MISSING, z=MISSING):
        self.x, self.y, self.z, _ = self.world.where([x, y, z], (), "move_to")
        self.y = self.world.above(self.x, self.y, self.z)
        self.vy = 0.0
        self.teleported = True
        self.place_camera(1)
        return self.native

    def on_hit(self, fn):
        self.hit_fns.append(self.world.lib.check_fn(fn, ":on_hit"))
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
        if SCENE is not None: SCENE.held_made = list(SCENE.interp.lines)
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
            ty = self.world.above(tx, ty, tz)
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
        """What stops the player here: solid things, except what physics moves (the page's physics stops the player
        at those, and pushes them)."""
        return [t for t in self.world.things if isinstance(t, Thing) and t.alive and t.solid_ and not t.hidden
                and t.phys_kind not in ("dynamic", "kinematic")]

    def blocked(self, x, z, y, solids):
        r = self.RADIUS
        for t in solids:
            b = t.box3(body=True)
            if x + r > b[0] and x - r < b[3] and z + r > b[2] and z - r < b[5] and y + self.TALL > b[1] and y + 0.3 < b[4]:
                return True
        return False

    def wet(self, x, z, solids):
        """Would the player be standing in water here (a lake or the sea, deeper than the shore's edge)? Something
        solid over the water, like a bridge, is dry."""
        land = self.world.land
        if land is None:
            return False
        level = land.water_at(x, z)
        return level is not None and self.floor_at(x, z, self.y, solids) < level - land.WET

    def floor_at(self, x, z, y, solids):
        """The highest floor under the player's feet: the ground (0, or the land's height), or the top of something
        solid."""
        land = self.world.land
        best = land.at(x, z) if land is not None else 0.0
        r = self.RADIUS * 0.8
        for t in solids:
            b = t.box3(body=True)
            if x + r > b[0] and x - r < b[3] and z + r > b[2] and z - r < b[5] and b[4] <= y + 0.35:
                best = max(best, b[4])
        return best

    def update(self, dt, real):
        w = self.world
        if w.driving is not None:  # in the car: the keys and the camera are the car's
            return
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
        x0, z0 = self.x, self.z
        if n:
            sp = self.speed * (1.7 if "shift" in down else 1.0) * dt / n
            nx, nz = self.x + mx * sp, self.z + mz * sp
            # The shore stops the player like a wall (unless it's in the water already: then it can walk out).
            dry = w.land is None or not self.wet(self.x, self.z, solids)
            if dry and self.wet(nx, self.z, solids):
                pass
            elif not self.blocked(nx, self.z, self.y, solids):
                self.x = nx
            elif self.try_step(nx, self.z, solids):
                pass
            if dry and self.wet(self.x, nz, solids):
                pass
            elif not self.blocked(self.x, nz, self.y, solids):
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
        elif (w.land is not None and self.on_ground and self.vy <= 0
              and ny - floor <= math.hypot(self.x - x0, self.z - z0) * 1.5 + 0.02):
            ny, self.vy = floor, 0.0  # walking downhill: stay on the land instead of hopping down it
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
        if w.land is not None:  # the land's square: no walking off its edge
            half = w.land.size / 2 - 0.6
            self.x, self.z = clamp(self.x, -half, half), clamp(self.z, -half, half)
            return
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


# ---------------------------------------------------------------- physics (Rapier, in the page)

def quat_mul(a, b):
    """a then b... as three.js and Rapier do it: the rotation b, then a ([x, y, z, w])."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def yaw_quat(degrees):
    """A turn about the up axis (counterclockwise from above, like three.js's ry)."""
    h = math.radians(degrees) / 2
    return [0.0, math.sin(h), 0.0, math.cos(h)]


def heading_of(q):
    """The way something turned by q faces (its -z), as tgame's heading: degrees clockwise from above."""
    x, y, z, w = q
    fx, fz = -2 * (x * z + w * y), -(1 - 2 * (x * x + y * y))
    if abs(fx) < 1e-9 and abs(fz) < 1e-9:  # facing straight up or down: its up says where it faces
        fx, fz = -2 * (x * y - w * z), -2 * (y * z + w * x)
    return math.degrees(math.atan2(fx, -fz)) % 360


def euler_of_quat(q):
    """three.js rotation (x, y, z in degrees, XYZ order) for a quaternion."""
    x, y, z, w = q
    m11, m12, m13 = 1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)
    m22, m23 = 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)
    m32, m33 = 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)
    ry = math.asin(clamp(m13, -1.0, 1.0))
    if abs(m13) < 0.9999999:
        rx, rz = math.atan2(-m23, m33), math.atan2(-m12, m11)
    else:
        rx, rz = math.atan2(m32, m22), 0.0
    return math.degrees(rx), math.degrees(ry), math.degrees(rz)


class Physics:
    """A game's physics: Rapier, stepping in the game's page (tuff_view_web/physics.js), started by the first thing
    that uses it. Python tells the page what each thing's body is (a `phys` property on its object: kind, shape,
    size, mass, bounce...) and sends the program's kicks, twists and explosions. Every frame the page sends back
    where the physics things went and what hit what (a "phys" event); the things keep those values and never send
    them back. A thing moved by the program (move_to, glide...) goes on from there in the page.

    In a 3D world, solid things (buildings, rocks, trees' trunks, things made solid), the land, the island and the
    ground become bodies that don't move, and the player becomes a capsule that walks into physics things, pushes
    them and stands on them: Python walks it as always, sends each step, and the page says where it ended up.

    In Tuff Engine's preview (tuff.py --scene) nothing is sent: the settings are only kept, for its Inspector."""

    def __init__(self, game):
        self.game = game
        self.d3 = game.three_d
        self.live = SCENE is None
        self.gravity_ = -9.8 if self.d3 else 900.0
        self.walls_ = False
        self.paused = False
        self.dirty = set()  # things whose body may have changed: they're checked once, at the frame
        # The player (3D): its moves the page hasn't made yet, [seq, (dx, dy, dz)], and where the page will have it
        self.seq = self.first_seq = 0
        self.moves = collections.deque()
        self.sent = None
        self.send("start", {"dim": 3 if self.d3 else 2, "gravity": self.gravity_})
        if self.d3:
            self.dirty.update(t for t in game.things if isinstance(t, Thing))
            if game.land is not None:
                self.dirty.add(game.land)

    def send(self, op, *args):
        if self.live and not self.game.closed:
            self.game.view.call(0, "physics", op, *args)

    def set_gravity(self, g):
        self.gravity_ = g
        self.send("gravity", g)

    def sync(self, t):
        """Tells the page what t's body is now, if that changed."""
        self.dirty.discard(t)
        spec = t.phys_spec() if t.alive else None
        if spec != t.phys_sent:
            t.phys_sent = spec
            if self.live and t.alive:
                self.game.view.set(t.node, phys=spec)

    def frame(self):
        """Before each frame goes: the bodies that changed, and pausing (physics stops while the game is paused)."""
        for t in list(self.dirty):
            self.sync(t)
        paused = bool(self.game.is_paused)
        if paused != self.paused:
            self.paused = paused
            self.send("pause", paused)

    # ---- the player's capsule (3D)
    def player_sync(self, p):
        """After the player walked: its move goes to the page (a teleport when the program moved it)."""
        at = (p.x, p.y, p.z)
        if self.sent is None or p.teleported:
            p.teleported = False
            self.seq += 1
            self.first_seq = self.seq  # reports from before it are about where it was
            self.moves.clear()
            self.sent = at
            self.send("player_to", self.seq, *at)
            return
        d = (at[0] - self.sent[0], at[1] - self.sent[1], at[2] - self.sent[2])
        if not any(d):
            return
        self.seq += 1
        self.moves.append((self.seq, d))
        self.sent = at
        self.send("player", self.seq, *d, *at)

    def player_report(self, p, rep):
        """Where the page's capsule is after the moves up to `done`: the player is there, plus the moves the page
        hasn't made yet. Standing on a physics thing, it's on the ground."""
        done, x, y, z, grounded = rep
        if done < self.first_seq or self.sent is None:
            return
        while self.moves and self.moves[0][0] <= done:
            self.moves.popleft()
        for _, d in self.moves:
            x, y, z = x + d[0], y + d[1], z + d[2]
        p.x, p.y, p.z = x, y, z
        self.sent = (x, y, z)
        if grounded and p.vy <= 0:
            p.vy, p.on_ground = 0.0, True

    # ---- what the page says
    def who(self, i):
        """The thing a body in a report belongs to (0: the player; -1: a wall)."""
        g = self.game
        if i == 0:
            return getattr(g, "the_player", None)
        land = getattr(g, "land", None)
        if land is not None and i == int(land.node):
            return land
        return g.by_node.get(i)

    def report(self, e):
        g = self.game
        for b in e.get("b") or ():
            t = g.by_node.get(b[0])
            if t is not None and t.alive and hasattr(t, "from_physics"):
                t.from_physics(b)
        p = e.get("p")
        if p and getattr(g, "the_player", None) is not None:
            self.player_report(g.the_player, p)
        c = e.get("c")
        if c and getattr(g, "cam_mode", None) == "drive":  # where the chase camera is
            g.cam, g.cam_yaw, g.cam_pitch = list(c[:3]), c[3] % 360, c[4]
        for a, b, strength in e.get("h") or ():
            self.hit(a, b, strength)

    def hit(self, a, b, strength):
        """Something hit something: each one with an on_hit function gets it, with the other and how hard (N·s)."""
        ta, tb = self.who(a), self.who(b)
        for me, other, oid in ((ta, tb, b), (tb, ta, a)):
            fns = getattr(me, "hit_fns", None)
            if not fns or not getattr(me, "alive", True):
                continue
            value = "wall" if oid == -1 else getattr(other, "native", None)
            for fn in list(fns):
                self.game.fire(fn, value, tidy(strength))

    def state(self):
        """For the autopilot's reports."""
        bodies = []
        for t in self.game.things:
            if not t.alive or t.phys_kind is None:
                continue
            if isinstance(t, Sprite):
                bodies.append([t.phys_name(), round(t.x, 2), round(t.y, 2), round(t.rot, 1), round(math.hypot(*t.vel), 2)])
            else:
                q = t.quat or [0, 0, 0, 1]
                up = 1 - 2 * (q[0] * q[0] + q[2] * q[2])  # 1: upright, 0: on its side, -1: upside down
                bodies.append([t.kind, round(t.x, 2), round(t.y - t.ground(), 3), round(t.z, 2), round(math.hypot(*t.vel), 2),
                               round(t.heading, 1), round(up, 3)])
        return {"gravity": self.gravity_, "walls": self.walls_, "bodies": bodies}


class Car(Thing):
    """world:car: a car to drive. In the page it's Rapier's ray-cast vehicle: a body on four wheels that are rays with
    springs, so it rolls over the land, leans in corners and can roll over (car:flip puts it back on its wheels).
    car:drive gives it the keys (W or up goes, S or down brakes and then backs up, A and D or left and right steer,
    Space brakes) and the camera, which follows it from behind. car:speed is how fast it goes, in km/h."""
    KIND = "car"
    NAMES = [(n, "car_speed" if n == "speed" else a) for n, a in Thing.NAMES] + [
        ("drive", "drive"), ("engine", "engine"), ("flip", "flip")]
    EXAMPLE = "car"
    MASS = 150
    WHEEL_R = 0.36
    REST = 0.35  # the springs' length
    CY = 0.79    # the body's middle above the car's position (the ground under its wheels)
    HALF = [0.9, 0.32, 1.9]
    WHEELS = ((-0.82, 0.64, -1.25), (0.82, 0.64, -1.25), (-0.82, 0.64, 1.25), (0.82, 0.64, 1.25))  # front first (-z)

    def __init__(self, world, x, y, z, color):
        c = world.color(color)
        trim, light, back = "#2b2d31", "#fff6d8", "#d4202a"
        paint = {"color": c, "metal": 0.35, "rough": 0.38, "shadow": True}
        parts = [
            ("box", {"w": 1.8, "h": 0.52, "d": 3.8, "y": 0.74, **paint}, True),
            ("box", {"w": 1.46, "h": 0.44, "d": 1.8, "y": 1.2, "z": 0.2, "color": "#1f2a36", "metal": 0.6, "rough": 0.15,
                     "shadow": True}, False),
            ("box", {"w": 1.52, "h": 0.07, "d": 1.86, "y": 1.45, "z": 0.2, **paint}, True),
            ("box", {"w": 1.84, "h": 0.16, "d": 0.14, "y": 0.52, "z": -1.92, "color": trim}, False),
            ("box", {"w": 1.84, "h": 0.16, "d": 0.14, "y": 0.52, "z": 1.92, "color": trim}, False),
        ] + [("box", {"w": 0.34, "h": 0.13, "d": 0.05, "x": sx * 0.6, "y": 0.84, "z": -1.91, "color": light,
                      "emissive": "#fff2c0", "mat": "basic"}, False) for sx in (-1, 1)
             ] + [("box", {"w": 0.3, "h": 0.12, "d": 0.05, "x": sx * 0.62, "y": 0.86, "z": 1.91, "color": back,
                           "emissive": "#7a0a10"}, False) for sx in (-1, 1)]
        wheels = [("group", {"x": wx, "y": wy - 0.28, "z": wz}, False) for wx, wy, wz in self.WHEELS]
        super().__init__(world, "car", x, y, z, (1.9, 1.5, 3.9), parts + wheels)
        self.wheel_nodes = [node for node, _ in self.parts[len(parts):]]
        for wn in self.wheel_nodes:  # each wheel: a tyre and a hub, turned to roll along z
            for part in (world.view.obj(wn, "cylinder", r=self.WHEEL_R, h=0.26, rz=90, seg=22, color="#24262b", rough=0.92, shadow=True),
                         world.view.obj(wn, "cylinder", r=0.2, h=0.28, rz=90, seg=12, color="#c0c6cf", metal=0.7, rough=0.3)):
                world.by_node[int(part)] = self
        self.phys_kind = "dynamic"
        self.kmh = 0.0
        self.controls = (0, 0, 0)
        world.physics_on().sync(self)

    def can_have_physics(self, kind):
        if kind != "dynamic":
            raise self.rt.error("A car always uses physics (it drives on its wheels).")

    def phys_spec(self):
        if not self.alive or self.world.phys is None:
            return None
        return {"kind": "dynamic", "shape": "car", "size": self.HALF, "cy": self.CY, "wheel_r": self.WHEEL_R,
                "rest": self.REST, "mass": self.mass_ or self.MASS, "bounce": self.bounce_, "friction": self.friction_,
                "hits": bool(self.hit_fns), "wheels": [[int(n), *xyz] for n, xyz in zip(self.wheel_nodes, self.WHEELS)]}

    def from_physics(self, b):
        """Like an object's, and the car's speed (km/h, forward)."""
        Thing.from_physics(self, b)
        self.kmh = b[11] if len(b) > 11 else 0.0

    def car_speed(self):
        return tidy(self.kmh)

    def drive(self, on=True):
        w = self.world
        ph = w.physics_on()
        if self.rt.truthy(on):
            if w.driving is not None and w.driving is not self:
                w.driving.drive(False)
            w.driving = self
            if w.cam_mode != "player":
                w.cam_mode = "drive"
            w.camera_dirty = False
            ph.send("chase", int(self.node))
        elif w.driving is self:
            w.driving = None
            self.controls = (0, 0, 0)
            ph.send("drive", int(self.node), 0, 0, 0)
            ph.send("chase", None)
            if w.cam_mode == "drive":
                w.cam_mode = "fixed"
                w.push_camera()  # the camera stays where it was, behind the car
            p = w.the_player
            if p is not None:  # out of the car, beside its door
                h = math.radians(self.heading)
                p.x, p.z = self.x - math.cos(h) * 2.2, self.z - math.sin(h) * 2.2
                p.y, p.vy = w.ground_y(p.x, p.z), 0.0
                p.teleported = True
                p.place_camera(1)
        return self.native

    def engine(self, power):
        n = self.num(power, ":engine")
        if n < 0:
            raise self.rt.error("car:engine needs a number of 0 or more (1 is normal), like car:engine(1.5).")
        self.world.physics_on().send("engine", int(self.node), n)
        return self.native

    def flip(self):
        self.world.physics_on().send("flip", int(self.node))
        return self.native


# A ragdoll's parts: name, shape, size (a ball's radius; a box's half sizes; a capsule's half length and radius), its
# middle when it stands (feet at 0), mass (kg), and what it's dressed in. And its joints: the two parts, where they
# meet, "ball" (turns any way) or "hinge" (bends one way, about x: forward is more), and how far a hinge bends.
RAGDOLL = (
    ("head", "ball", 0.13, (0, 1.56, 0), 1.0, "skin"),
    ("chest", "box", (0.18, 0.17, 0.11), (0, 1.24, 0), 3.0, "shirt"),
    ("hips", "box", (0.16, 0.12, 0.1), (0, 0.94, 0), 2.0, "pants"),
    ("left arm", "capsule", (0.11, 0.055), (-0.25, 1.24, 0), 0.6, "shirt"),
    ("right arm", "capsule", (0.11, 0.055), (0.25, 1.24, 0), 0.6, "shirt"),
    ("left hand", "capsule", (0.1, 0.05), (-0.25, 0.94, 0), 0.4, "skin"),
    ("right hand", "capsule", (0.1, 0.05), (0.25, 0.94, 0), 0.4, "skin"),
    ("left leg", "capsule", (0.15, 0.07), (-0.09, 0.6, 0), 1.2, "pants"),
    ("right leg", "capsule", (0.15, 0.07), (0.09, 0.6, 0), 1.2, "pants"),
    ("left foot", "capsule", (0.15, 0.06), (-0.09, 0.21, 0), 0.8, "pants"),
    ("right foot", "capsule", (0.15, 0.06), (0.09, 0.21, 0), 0.8, "pants"),
)
RAGDOLL_JOINTS = (
    ("chest", "head", (0, 1.42, 0), "ball", None),
    ("chest", "hips", (0, 1.06, 0), "hinge", (-0.8, 0.3)),
    ("chest", "left arm", (-0.25, 1.39, 0), "ball", None),
    ("chest", "right arm", (0.25, 1.39, 0), "ball", None),
    ("left arm", "left hand", (-0.25, 1.09, 0), "hinge", (0, 2.0)),
    ("right arm", "right hand", (0.25, 1.09, 0), "hinge", (0, 2.0)),
    ("hips", "left leg", (-0.09, 0.82, 0), "hinge", (-0.5, 1.2)),
    ("hips", "right leg", (0.09, 0.82, 0), "hinge", (-0.5, 1.2)),
    ("left leg", "left foot", (-0.09, 0.38, 0), "hinge", (-2.0, 0)),
    ("right leg", "right foot", (0.09, 0.38, 0), "hinge", (-2.0, 0)),
)
RAGDOLL_MASS = sum(p[4] for p in RAGDOLL)


class Ragdoll(Thing):
    """world:ragdoll: a person made of parts held together by joints (a ball for the head, boxes for the chest and
    hips, capsules for the arms and legs). Made standing on the ground, it stands still until something hits it or
    it's pushed, then flops over; made in the air, it falls. Its x and z are its chest's, its y its lowest part's; a
    push goes to its chest."""
    KIND = "ragdoll"
    EXAMPLE = "dummy"

    def __init__(self, world, x, y, z, color):
        dress = {"skin": "#f1c9a5", "shirt": world.color(color), "pants": "#3b4252"}
        parts = []
        for name, shape, size, (px, py, pz), _mass, wear in RAGDOLL:
            look = {"x": px, "y": py, "z": pz, "color": dress[wear], "rough": 0.7, "shadow": True}
            if shape == "ball":
                parts.append(("sphere", {"r": size, "seg": 16, **look}, wear == "shirt"))
            elif shape == "box":
                parts.append(("box", {"w": size[0] * 2, "h": size[1] * 2, "d": size[2] * 2, **look}, wear == "shirt"))
            else:
                parts.append(("capsule", {"r": size[1], "h": size[0] * 2, "seg": 10, **look}, wear == "shirt"))
        super().__init__(world, "ragdoll", x, y, z, (0.6, 1.7, 0.3), parts)
        head = self.parts[0][0]
        for ex in (-0.045, 0.045):  # eyes, on the head (they turn with it)
            world.by_node[int(world.view.obj(head, "sphere", r=0.022, x=ex, y=0.025, z=-0.115, seg=8, color="#1d2026"))] = self
        self.phys_kind = "dynamic"
        self.standing = self.y - self.ground() < 0.05  # on the ground: it stands until something knocks it over
        world.physics_on().sync(self)

    def can_have_physics(self, kind):
        if kind != "dynamic":
            raise self.rt.error("A ragdoll always uses physics (that's what makes it flop).")

    def phys_spec(self):
        if not self.alive or self.world.phys is None:
            return None
        names = [p[0] for p in RAGDOLL]
        scale = (self.mass_ / RAGDOLL_MASS) if self.mass_ else 1.0
        return {"kind": "dynamic", "shape": "ragdoll", "main": names.index("chest"), "bounce": self.bounce_,
                "friction": self.friction_, "hits": bool(self.hit_fns), "stand": self.standing,
                "parts": [[int(node), shape, size, list(at), round(mass * scale, 4)]
                          for (node, _), (_, shape, size, at, mass, _) in zip(self.parts, RAGDOLL)],
                "joints": [[names.index(a), names.index(b), list(at), kind, list(lim) if lim else None]
                           for a, b, at, kind, lim in RAGDOLL_JOINTS]}


# ---------------------------------------------------------------- menus, buttons and screens (atgui on a game)

# The page events that can be on the menus. One that is (its path goes through them) is theirs, not the game's.
UI_EVENTS = frozenset(atgui.ROUTED) | {"mousedown", "mouseup", "wheel"}

# How menus look on a game, on top of atgui's own look: see-through except where there's a widget, words that stay
# readable over a bright sky, panels pinned to their places, and screens on a dimmed, blurred backdrop.
UI_CSS = """
.at-app.tg-ui{background:transparent;pointer-events:none;z-index:10}
.tg-ui .tg-dock{position:absolute;display:flex;flex-direction:column;gap:10px;max-width:calc(100% - 28px);
 max-height:calc(100% - 28px);pointer-events:none}
.tg-ui .tg-panel{pointer-events:none;min-height:0;text-shadow:0 1px 2px rgba(0,0,0,.65),0 0 14px rgba(0,0,0,.35)}
.tg-ui .tg-panel :is(.at-btn,.at-input,.at-textarea,.at-check,.at-slider,.at-dropdown,.at-list,.at-table-wrap,.at-tabs,
 .at-card,.at-scroll,.at-chart-box,.at-html,.at-codeblock,.at-md a,[data-at-tip],[data-at-hover],[style*="cursor"]){pointer-events:auto}
.tg-ui .tg-panel :is(.at-card,.at-btn,.at-input,.at-textarea,.at-dropdown,.at-table-wrap,.at-list,.at-badge,.at-codeblock){text-shadow:none}
.tg-ui .tg-panel>.at-heading{font-size:20px;font-weight:700;letter-spacing:-.01em}
.tg-ui .tg-panel .at-small{color:rgba(236,237,240,.82)}
.tg-ui .tg-panel .at-badge{backdrop-filter:blur(8px) brightness(.45)}
.tg-ui .tg-panel :is(.at-progress,.at-slider){min-width:180px}
.tg-ui .tg-panel :is(.at-input,.at-textarea){min-width:210px}
.tg-ui .tg-panel .at-progress{height:8px;background:rgba(0,0,0,.4);box-shadow:inset 0 0 0 1px rgba(255,255,255,.14)}
.tg-ui .tg-panel>.at-card{background:color-mix(in srgb,var(--surface) 80%,transparent);backdrop-filter:blur(12px) saturate(1.4)}
.tg-ui .tg-dock-top-left{top:14px;left:14px;align-items:flex-start}
.tg-ui .tg-dock-top{top:14px;left:50%;translate:-50% 0;align-items:center}
.tg-ui .tg-dock-top-right{top:14px;right:14px;align-items:flex-end}
.tg-ui .tg-dock-left{top:50%;left:14px;translate:0 -50%;align-items:flex-start}
.tg-ui .tg-dock-center{top:50%;left:50%;translate:-50% -50%;align-items:center}
.tg-ui .tg-dock-right{top:50%;right:14px;translate:0 -50%;align-items:flex-end}
.tg-ui .tg-dock-bottom-left{bottom:14px;left:14px;align-items:flex-start;justify-content:flex-end}
.tg-ui .tg-dock-bottom{bottom:14px;left:50%;translate:-50% 0;align-items:center;justify-content:flex-end}
.tg-ui .tg-dock-bottom-right{bottom:14px;right:14px;align-items:flex-end;justify-content:flex-end}
.tg-ui :is(.tg-top,.tg-center,.tg-bottom){align-items:center;--self:center}
.tg-ui :is(.tg-top-right,.tg-right,.tg-bottom-right){align-items:flex-end;--self:flex-end}
.tg-ui .tg-center{text-align:center}
.tg-ui .tg-screen{pointer-events:auto;z-index:20;
 background:radial-gradient(120% 100% at 50% 42%,rgba(8,10,16,.4),rgba(3,4,7,.8));backdrop-filter:blur(6px)}
.tg-ui .tg-card{width:min(460px,100%);padding:26px 28px 24px;gap:16px;text-align:center;border-color:rgba(255,255,255,.1);
 box-shadow:0 30px 80px -24px rgba(0,0,0,.85),0 0 0 1px rgba(0,0,0,.35)}
.tg-ui .tg-screen-title{font-size:26px;font-weight:750;letter-spacing:-.02em}
.tg-ui .tg-card>.at-dialog-body{--self:stretch;gap:10px}
.tg-ui .tg-card .at-row{justify-content:center}
.tg-ui .tg-card .at-card{--self:center}
.tg-ui .tg-card>.at-dialog-body>.at-btn{height:40px;font-size:14.5px}
.tg-ui .tg-start{position:absolute;inset:0;z-index:30;pointer-events:auto;cursor:pointer;display:flex;flex-direction:column;
 align-items:center;justify-content:center;gap:12px;padding:40px 32px;text-align:center;opacity:0;transition:opacity .28s;
 background:radial-gradient(130% 110% at 50% 40%,rgba(10,13,22,.36),rgba(3,4,8,.86));backdrop-filter:blur(5px)}
.tg-ui .tg-start.at-shown{opacity:1}
.tg-ui .tg-title{margin:0;max-width:100%;font:800 clamp(36px,7.5vw,72px)/1.04 var(--font);letter-spacing:-.03em;color:#fff;
 overflow-wrap:anywhere;text-shadow:0 2px 0 rgba(0,0,0,.25),0 10px 40px rgba(0,0,0,.55)}
.tg-ui .tg-start-body{align-items:center;--self:center;max-width:min(560px,100%);gap:8px}
.tg-ui .tg-start-body>:is(.at-text,.at-small){font-size:16px;color:#d9dce3;text-shadow:0 1px 8px rgba(0,0,0,.5)}
.tg-ui .tg-start-body>.at-small{font-size:13.5px;color:var(--muted)}
.tg-ui .tg-start-body:empty{display:none}
.tg-ui .tg-hint{margin-top:18px;display:inline-flex;align-items:center;gap:11px;height:46px;padding:0 26px 0 22px;border-radius:999px;
 background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;font:650 15.5px/1 var(--font);letter-spacing:.01em;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 10px 30px -8px color-mix(in srgb,var(--accent) 70%,transparent)}
.tg-ui .tg-hint::before{content:"";border-left:10px solid #fff;border-top:6.5px solid transparent;border-bottom:6.5px solid transparent}
.tg-ui .tg-start:hover .tg-hint{filter:brightness(1.08)}
.tg-ui .tg-start.at-shown .tg-title{animation:tg-rise .55s cubic-bezier(.2,.8,.2,1) both}
.tg-ui .tg-start.at-shown .tg-start-body{animation:tg-rise .55s .06s cubic-bezier(.2,.8,.2,1) both}
.tg-ui .tg-start.at-shown .tg-hint{animation:tg-rise .55s .12s cubic-bezier(.2,.8,.2,1) both,tg-glow 2.4s .8s ease-in-out infinite}
@keyframes tg-rise{from{opacity:0;translate:0 14px}}
@keyframes tg-glow{50%{box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 0 0 7px color-mix(in srgb,var(--accent) 22%,transparent),
 0 10px 34px -6px color-mix(in srgb,var(--accent) 80%,transparent)}}
"""

# The page side of a game's menus (it runs after atgui's own, tuff_atgui.JS).
UI_JS = r"""
const tg = window.__tg = {};
const typing = (el) => el && (el.isContentEditable || el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !/^(checkbox|radio|range|button)$/i.test(el.type)));
// Lock the mouse for looking around (a 3D world with a player). The browser only allows that in the user's own click
// or key press, so it happens here, in the event, not after Python hears of it. If it isn't allowed, a click on the
// game locks it as usual.
tg.lock = () => {
  const s = [...tv.objs.values()].find((n) => n.kind === 'scene' && n.clicklock);
  if (!s || document.pointerLockElement === s.el) return null;
  tv.emit('tg-lock', {});
  try { const p = s.el.requestPointerLock(); if (p && p.catch) p.catch(() => {}); } catch (err) { /* not now */ }
  return null;
};
const WIDGETS = '.at-btn,.at-input,.at-textarea,.at-check,.at-slider,.at-dropdown,.at-list,.at-tabs,.at-table-wrap,.at-card';
addEventListener('pointerdown', (e) => {
  const start = e.target.closest && e.target.closest('.tg-start.at-shown');
  if (start && !e.target.closest(WIDGETS)) tg.lock();
}, true);
addEventListener('keydown', (e) => {
  if ((e.key === 'Enter' || e.key === ' ') && !e.repeat && !typing(e.target) && document.querySelector('.tg-start.at-shown')) tg.lock();
}, true);
// A clicked button, checkbox or slider keeps the keyboard, so Enter would press it again and the arrows would move it:
// give the keys back to the game. Text boxes keep them (typing in one doesn't move the player).
addEventListener('click', () => {
  const a = document.activeElement;
  if (a && a !== document.body && !typing(a) && a.closest && a.closest('.tg-ui')) a.blur();
});
HTMLElement.prototype.tgShut = function () {
  const a = document.activeElement;
  if (a && this.contains(a)) a.blur();
  return this.atShut();
};
"""


class GameUI:
    """A game's menus: atgui's own widgets, on the game's page, over the game.

    It stands in for atgui's window (App) as the widgets' app: their lib, their scene, the layer their menus open in.
    Its panels and screens are atgui containers, so everything atgui's containers make works in them and looks and
    behaves as it does in atgui. Their events come through the game's loop (Game.handle), so their functions run
    between frames, like the game's own events. Tuff Engine's preview (tuff.py --scene) leaves the menus out: their
    scene never gets a window, so nothing is sent."""

    def __init__(self, game):
        self.game = game
        self.rt = game.rt
        self.lib = atgui.Lib(game.rt)
        self.lib.app = self.app = self
        self.scene = atgui.Scene()
        if SCENE is None:
            self.scene.view = game.view  # the game's window is open already: changes go straight to it
        self.children, self.extra_ids = [], []
        self.dead = self.kept = False
        self._native = self.click_fn = None
        self.screens = []
        self.showing = self.pausing = False  # a screen shows; one that pauses shows
        self.relock = False  # a screen let go of the mouse, so it's locked again when the screens are gone
        self.lock_asks = 0
        atgui.add_to_page(self.scene, game=True)
        self.scene.call(0, "css", UI_CSS)
        self.scene.js(UI_JS)
        props = {}
        if not game.three_d:  # a 2D game keeps its shape in a bigger window (bars beside it): the menus stay on it
            W, H = game.W, game.H
            props["style"] = {"margin": "auto", "width": f"min(100vw, calc(100vh * {W} / {H}))",
                              "height": f"min(100vh, calc(100vw * {H} / {W}))"}
        self.id = self.slot = self.scene.el("div", 0, cls="at-app at-dark tg-ui", **props)
        self.layer = self.scene.el("div", self.id, cls="at-layer")  # for dropdowns' menus and tooltips, over the rest
        self.docks = {}  # anchor -> the place its panels go, one under another

    def dock(self, anchor):
        if anchor not in self.docks:
            self.docks[anchor] = self.scene.el("div", self.id, cls=f"tg-dock tg-dock-{anchor.replace(' ', '-')}",
                                               before=self.layer)
        return self.docks[anchor]

    def handle(self, e):
        """An event from the page: True when it was on the menus (their widgets get it, and the game doesn't)."""
        if self.id not in (e.get("path") or ()):
            return False
        if e.get("type") in atgui.ROUTED:
            self.lib.route(e)
        return True

    def start_key(self, name):
        """Enter or Space while a start screen shows: it starts the game. True when one did."""
        if name in ("enter", "space"):
            for s in reversed(self.screens):
                if isinstance(s, StartScreen) and s.is_shown:
                    s.start()
                    return True
        return False

    def removed(self, widget):
        if widget in self.screens:
            self.screens.remove(widget)
            self.changed()

    def changed(self):
        """A screen showed or hid. The game is paused while one that pauses shows; while any shows the mouse is free
        to use it (a locked one is let go, and locked again when the last screen goes)."""
        g = self.game
        shown = [s for s in self.screens if s.is_shown and not s.dead]
        self.showing = bool(shown)
        self.pausing = any(s.pauses for s in shown)
        if SCENE is None and not g.closed:
            if self.showing and g.locked:
                g.view.call(0, "unlock")
                self.relock = True
            elif not self.showing and self.relock:
                self.relock = False
                g.view.js("window.__tg.lock()")
        g.lock_changed()

    def state(self):
        """For the autopilot's reports: the screens, and the words and values on what shows."""
        texts, inputs, values = [], [], []

        def walk(w):
            for c in w.children:
                if isinstance(c, (atgui.Label, atgui.Badge)):
                    texts.append(c.value_text if isinstance(c, atgui.Label) else c.label)
                elif isinstance(c, atgui.Button):
                    texts.append(c.label)
                elif isinstance(c, atgui.Input):
                    inputs.append(c.text)
                elif isinstance(c, (atgui.Slider, atgui.Progress)):
                    values.append(c.number)
                walk(c)
        for w in self.children:
            if (isinstance(w, Screen) and w.is_shown) or (isinstance(w, Panel) and not w.hidden):
                walk(w)
        return {"screens": [{"title": s.title, "shown": s.is_shown, "pauses": s.pauses, "start": isinstance(s, StartScreen)}
                            for s in self.screens],
                "showing": self.showing, "pausing": self.pausing, "texts": texts, "inputs": inputs, "values": values,
                "lock_asks": self.lock_asks}


class Panel(atgui.Container):
    """game:panel("top left"): an atgui column pinned to a place on the game, a little in from its edges (panels at
    the same place go one under another). Clicks on its widgets go to them; clicks between them, and everywhere
    else, reach the game. Panels never pause it."""
    kind = "panel"

    def __init__(self, ui, anchor):
        super().__init__(ui, place=(ui.dock(anchor), None), cls=f"at-col tg-panel tg-{anchor.replace(' ', '-')}")
        self.hidden = False

    def show(self):
        if self.hidden:
            self.hidden = False
            self.set(show=True)
            self.call("atAnimate", "fade-in", 160, 1)

    def hide(self):
        self.hidden = True
        self.set(show=False)


class Screen(atgui.Container):
    """game:screen("Shop"): a layer over the whole game with atgui's modal look: what's added to it goes in a card in
    the middle, on a dimmed backdrop, under the title. It's made showing. One that pauses (the default) holds the
    game while it shows: dt is 0, timers wait and the player stands still."""
    kind = "screen"
    cls = "at-overlay tg-screen"

    def __init__(self, ui, title, pauses):
        self.ui, self.title, self.pauses = ui, title, pauses
        self.is_shown = False
        super().__init__(ui, place=(ui.id, ui.layer), style={"display": "none"})
        self.build(title)
        ui.screens.append(self)
        self.show()

    def build(self, title):
        box = self.scene.el("div", self.id, cls="at-dialog tg-card", role="dialog")
        self.title_id = self.scene.el("h2", box, cls="at-heading tg-screen-title", text=title, show=bool(title))
        self.slot = self.scene.el("div", box, cls="at-dialog-body")

    def show(self):
        if not self.is_shown and not self.dead:
            self.is_shown = True
            self.call("atOpen")
            self.ui.changed()

    def hide(self):
        if self.is_shown:
            self.is_shown = False
            self.call("tgShut")
            self.ui.changed()

    def shown(self):
        return self.is_shown

    def set_title(self, text):
        self.title = self.lib.text(text)
        if not self.dead:
            self.scene.set(self.title_id, text=self.title, show=bool(self.title))
        return self.native()

    def methods(self):
        return {**super().methods(), "show": self.show, "hide": self.hide, "shown": self.shown, "set": self.set_title}


class StartScreen(Screen):
    """game:start_screen("Chop! Chop!"): a screen that is all one button, with a big title, the hint and whatever the
    program adds between them. A click anywhere on it (or Enter or Space) hides it, and the game starts; in a 3D
    world with a player that click also locks the mouse for looking around. start:clicked fn runs fn then."""
    cls = "tg-screen tg-start"

    def __init__(self, ui, title, hint):
        self.hint = hint
        self.start_fn = None
        super().__init__(ui, title, True)

    def build(self, title):
        self.title_id = self.scene.el("h1", self.id, cls="tg-title", text=title, show=bool(title))
        self.slot = self.scene.el("div", self.id, cls="at-col tg-start-body")
        self.scene.el("div", self.id, cls="tg-hint", text=self.hint, show=bool(self.hint))
        self.lib.on(self.id, "click", lambda e: self.start())

    def start(self):
        if self.is_shown:
            self.hide()
            self.lib.fire(self.start_fn)

    def clicked(self, fn):
        self.start_fn = self.lib.check_fn(fn, ":clicked")
        return self.native()


# ---------------------------------------------------------------- Tuff Engine's preview (tuff.py --scene)
SCENE = None  # a Scene while tuff.py --scene runs a program's setup; None in every normal run


class SceneDone(BaseException):
    """Ends a preview where the game would start running: its loop, or the end of the program."""


class Scene:
    """What a program's setup made, for Tuff Engine (TuffCode's game editor). tuff.py --scene runs the setup with a
    tuff_view.Recorder for a window, and dump() gives the commands it sent plus every thing it made, each with the
    stack of lines that were running when it was made."""
    MAX_THINGS, MAX_CMDS = 3000, 60000
    MAX_NODES = 20000  # stop early: a setup that makes this much is shown as "too big" anyway

    def __init__(self, interp):
        self.interp, self.game, self.stopped = interp, None, None
        self.made = {}  # node id -> the lines being run when it was made (made[0]: the top-level line)
        self.player_made = self.held_made = None

    def created(self, node_id):
        self.made[node_id] = list(self.interp.lines)
        if len(self.made) > self.MAX_NODES or (self.game is not None and len(self.game.things) > self.MAX_THINGS):
            self.stop("too-big")

    def stop(self, why):
        self.stopped = self.stopped or why
        raise SceneDone()

    def dump(self, error):
        g = self.game
        if g is None:
            return {"stopped": "error" if error else "nowindow", "error": error}
        land = getattr(g, "land", None)
        if g.three_d:
            try:
                g.before_frame()  # the land's heights, after every edit the setup made
                g.push_camera()  # the starting camera, as the first frame would send it
            except Exception:
                pass
        batch = g.view.record()
        names = {id(v.tg): name for name, v in self.interp.globals.vars.items() if getattr(v, "tg", None) is not None}
        parts = {}  # id(thing) -> its node ids (an object's group, then its parts)
        for node_id, t in g.by_node.items():
            parts.setdefault(id(t), []).append(int(node_id))

        def ids_of(t):
            return sorted(parts.get(id(t), [int(t.node)]))

        things = []
        for t in list(g.things):
            if isinstance(t, Sprite):
                item = {"kind": {"rect": "box"}.get(t.shape, t.shape), "layer": "hud" if t.layer is g.hud_layer else "game",
                        "ids": [int(t.node)], "x": tidy(t.x), "y": tidy(t.y), "z": 0, "dims": None, "k": None,
                        "heading": tidy(t.rot), "drag": "xy"}
            else:
                # y is the height above the land, as the program wrote it; "ground" is the land's height there.
                item = {"kind": t.kind, "layer": "world", "ids": ids_of(t), "x": tidy(t.x), "y": tidy(t.y - t.ground()),
                        "z": tidy(t.z), "dims": [tidy(v) for v in t.dims], "k": [tidy(v) for v in t.k],
                        "heading": tidy(t.heading), "drag": None if getattr(t, "floor", False) else "xz"}
                if land is not None:
                    item["ground"] = tidy(t.ground())
            if land is not None and int(land.node) < item["ids"][0] and not any(x["kind"] == "terrain" for x in things):
                things.append(self.land_item(land, names, len(things)))  # in the order things were made
            item.update(i=len(things), hidden=bool(t.hidden), made=self.made.get(int(t.node), []), var=names.get(id(t)))
            physics = t.phys_dump()  # what thing:physics, :mass, :bounce and :friction set (nothing simulates here)
            if physics is not None:
                item["physics"] = physics
            things.append(item)
        if land is not None and not any(x["kind"] == "terrain" for x in things):
            things.append(self.land_item(land, names, len(things)))
        out = {"mode": "3d" if g.three_d else "2d", "title": g.view.title, "size": [g.W, g.H],
               "stopped": "error" if error else (self.stopped or "end"), "error": error, "batch": batch,
               "roots": {"view": int(g.scene) if g.three_d else int(g.node),
                         "hud": int(g.hud_layer.node) if g.hud_layer is not None else None},
               "canvas": None if g.three_d else {"cx": tidy(g.cx), "cy": tidy(g.cy)},
               "things": things, "player": None, "camera": None}
        if g.three_d:
            p = g.the_player
            if p is not None:
                held = None
                if p.held is not None:
                    held = {"name": p.held.kind, "ids": ids_of(p.held), "made": self.held_made or []}
                out["player"] = {"mode": p.mode, "x": tidy(p.x), "y": tidy(p.y - g.ground_y(p.x, p.z)), "z": tidy(p.z),
                                 "heading": tidy(p.heading), "made": self.player_made or [],
                                 "ids": ids_of(p.body) if p.body is not None else [], "held": held}
                if land is not None:
                    out["player"]["ground"] = tidy(land.at(p.x, p.z))
            out["camera"] = {"cx": tidy(g.cam[0]), "cy": tidy(g.cam[1]), "cz": tidy(g.cam[2]), "yaw": tidy(-g.cam_yaw),
                             "pitch": tidy(g.cam_pitch)}
            if land is not None:
                out["terrain"] = land.dump(names.get(id(land)), self.made.get(int(land.node), []))
            out["lighting"] = g.lighting_name
        if self.stopped == "too-big" or len(things) > self.MAX_THINGS or len(batch) > self.MAX_CMDS:
            out.update(stopped="too-big", batch=[], things=[], player=None)
            if "terrain" in out:
                out["terrain"] = None
        return out

    def land_item(self, land, names, i):
        """The land as one of the things (it can't be dragged); out["terrain"] has its heights and edits."""
        hs = land.h
        return {"kind": "terrain", "layer": "world", "ids": land.node_ids(), "x": 0, "y": 0, "z": 0,
                "dims": [tidy(land.size), tidy(max(hs) - min(hs)), tidy(land.size)], "k": [1, 1, 1], "heading": 0,
                "drag": None, "i": i, "hidden": False, "made": self.made.get(int(land.node), []), "var": names.get(id(land))}


def start_scene(interp):
    global SCENE
    SCENE = Scene(interp)
    return SCENE


def editor_tables():
    """The names Tuff Engine offers in its menus, from the same tables a run uses."""
    return {"colors": COLORS, "skies": list(SKIES), "kit": list(KIT), "hold": list(HOLDABLE), "sounds": list(SOUNDS),
            "edges": list(EDGE_MODES), "players": list(PLAYER_MODES), "terrain_styles": list(TERRAIN_STYLES),
            "lightings": list(LIGHTINGS), "anchors": list(ANCHORS), "physics": list(PHYSICS_KINDS),
            "weathers": list(WEATHERS)}


# ---------------------------------------------------------------- the autopilot (tests)

class Autopilot:
    """Plays a game by itself for the tests: TUFF_TGAME_AUTOPILOT names a JSON file of timed steps.

    {"on_top": true, "out": "folder", "timeout": 20, "steps": [
        {"at": 0.5, "key": "right"}, {"at": 1, "hold": "w", "for": 0.8}, {"at": 1.2, "keydown": "a"}, {"keyup": ...},
        {"at": 2, "click": [x, y]} (window pixels), {"click_world": [x, y]} (a 2D game's own units),
        {"click_center": true}, {"look": [dx, dy]} (mouse movement), {"lock": true} (act as if the mouse were locked),
        {"click_ui": "Play"} (the first button, item, tab or text box showing on the game's menus with these words, or
        a text box's placeholder: exactly, or else containing them), {"type": "wasd", "for": 0.5} (keys typed into the
        text box that has the keys, let go after "for" seconds),
        {"call": "tuff_function"}, {"say": "text"}, {"mark": true} (start measuring), {"shot": "name.png"} (with
        menus: the whole page as the window shows it), {"dump": "name.json"} (add "memory": true to count the
        sprites and objects still in memory), {"close": true}]}

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
        """Run the steps that are due. Their times count from the game's first frame.

        One moment of the plan per frame: steps with the same time run together, and a later one waits for the next
        frame even when it's due too. On a slow machine several can be due at once, and the game needs a frame to
        react to one (a collision, a key) before the next step looks at it."""
        g = self.game
        if self.t0 is None:
            self.t0 = now
        t = now - self.t0
        if t > self.timeout:
            print(f"[autopilot] timed out after {self.timeout} s", flush=True)
            g.close()
            return
        at = None
        while self.steps and self.steps[0].get("at", 0) <= t and (at is None or self.steps[0].get("at", 0) == at):
            step = self.steps.pop(0)
            at = step.get("at", 0)
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
        # A real click somewhere else takes the keys from a text box: so does this one.
        return (f"const x = {x}, y = {y}; const el = document.elementFromPoint(x, y) || document.body;"
                "const o = {clientX: x, clientY: y, bubbles: true, button: 0};"
                "const a = document.activeElement; if (a && a !== document.body && !a.contains(el) && a.blur) a.blur();"
                "el.dispatchEvent(new PointerEvent('pointerdown', o)); el.dispatchEvent(new PointerEvent('pointerup', o));"
                "el.dispatchEvent(new MouseEvent('click', o));")

    def click_ui_js(self, words):
        """A click in the middle of the first widget on the game's menus that shows these words (see the class), the
        way click_js clicks. A text box is found by its placeholder too, and gets the keys as a real click gives them."""
        return ("const want = " + json.dumps(str(words).strip().lower()) + ";"
                "const ui = document.querySelector('.tg-ui');"
                "const seen = (el) => (el.checkVisibility ? el.checkVisibility() : el.getClientRects().length > 0) && !el.closest('.tg-screen:not(.at-shown)');"
                "const field = (el) => el.matches('.at-input, .at-textarea');"
                "const words = (el) => ((field(el) ? el.placeholder || el.value : el.textContent) || '').trim().toLowerCase();"
                "const all = ui ? [...ui.querySelectorAll('.at-btn, .at-item, .at-mi, .at-tab, .at-check, .at-table tbody tr, .tg-hint, .at-input, .at-textarea')].filter(seen) : [];"
                "const el = all.find((w) => words(w) === want) || all.find((w) => words(w).includes(want));"
                "if (!el) { tv.emit('tg-autopilot', { message: `nothing on the game's menus says \"${want}\"` }); return; }"
                "const r = el.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height / 2;"
                "const hit = document.elementFromPoint(x, y) || el; const o = {clientX: x, clientY: y, bubbles: true, button: 0};"
                "const a = document.activeElement; if (a && a !== document.body && !a.contains(hit) && a.blur) a.blur();"
                "hit.dispatchEvent(new PointerEvent('pointerdown', o)); hit.dispatchEvent(new PointerEvent('pointerup', o));"
                "if (field(el)) el.focus();"
                "hit.dispatchEvent(new MouseEvent('click', o));")

    def type_js(self, kind, text):
        """Keys pressed (kind "keydown") or let go ("keyup") in the element that has the keys; pressing one types it
        into a text box. Letting go uses the element they were pressed in."""
        return ("const kind = " + json.dumps(kind) + ";"
                "const el = (kind === 'keydown' ? (window.__tgTyped = document.activeElement) : window.__tgTyped) || document.body;"
                "for (const ch of " + json.dumps(str(text)) + ") {"
                "  const code = /[a-z]/i.test(ch) ? 'Key' + ch.toUpperCase() : /[0-9]/.test(ch) ? 'Digit' + ch : ch === ' ' ? 'Space' : '';"
                "  el.dispatchEvent(new KeyboardEvent(kind, {key: ch, code, bubbles: true}));"
                "  if (kind === 'keydown' && /^(INPUT|TEXTAREA)$/.test(el.tagName)) { el.value += ch; el.dispatchEvent(new Event('input', {bubbles: true})); }"
                "}")

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
        if "click_ui" in step:
            v.js(self.click_ui_js(step["click_ui"]))
        if "type" in step:
            v.js(self.type_js("keydown", step["type"]))
            self.steps.append({"at": t + step.get("for", 0.05), "type_up": step["type"]})
            self.steps.sort(key=lambda s: s.get("at", 0))
        if "type_up" in step:
            v.js(self.type_js("keyup", step["type_up"]))
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
            # The page's snapshot has its canvases and 3D scenes; a game with menus needs the whole page.
            png = v.page_png() if g.ui is not None else None
            if png is None:
                data = v.ask(0, "snapshot", timeout=10)
                if data and data.startswith("data:image/png;base64,"):
                    png = base64.b64decode(data.split(",", 1)[1])
            if png:
                with open(os.path.join(self.out, step["shot"]), "wb") as f:
                    f.write(png)
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
        out["down"] = sorted(g.down)  # the keys the game sees held
        if g.ui is not None:
            out["ui"] = g.ui.state()
        out["things"] = len([t for t in g.things if t.alive])
        out["texts"] = [s.words for s in g.things if isinstance(s, Sprite) and s.alive and s.shape == "text"]
        if g.hud_layer is not None:
            out["hud_texts"] = [s.words for s in g.hud_layer.sprites if s.alive and s.shape == "text" and not s.hidden]
        out["labels"] = [t.label_text for t in g.things if isinstance(t, Thing) and t.alive and t.label_text]
        out["fallen"] = len([t for t in g.things if isinstance(t, Thing) and t.alive and t.fallen])
        out["sprites"] = [[s.shape, round(s.x, 2), round(s.y, 2)] for s in g.things if isinstance(s, Sprite) and s.alive][:400]
        out["objects"] = [[t.kind, round(t.x, 2), round(t.y, 2), round(t.z, 2), t.fallen, t.data]
                          for t in g.things if isinstance(t, Thing) and t.alive][:400]
        out["physics"] = g.phys.state() if g.phys is not None else None
        out["effects"] = g.fx.state() if g.fx is not None else None
        if g.three_d and g.the_player is not None:
            out["on_ground"] = g.the_player.on_ground
        return out


# ---------------------------------------------------------------- for tuff.py --check

# What each method gives back, so the checker knows what a variable holds ("$number", "$text", "$bool",
# "$list", or another tgame kind). Left out: it depends (like :touches, :get or :looking_at).
# (:speed and :velocity are left out: with no inputs they give how fast it goes.)
_SETTERS = ("move", "move_to", "glide", "forward", "turn", "turn_to", "spin", "point_at", "on_edge", "size",
            "scale", "color", "layer", "flip", "align", "hide", "show", "set", "clicked", "shake", "look_at", "fall",
            "grow", "regrow", "swing", "glow", "solid", "label", "physics", "mass", "bounce", "friction", "push",
            "on_hit", "sleep", "wake")
_OBJECT_GIVES = {"x": "$number", "y": "$number", "z": "$number", "spot": "$list", "angle": "$number",
                 "distance": "$number", "fallen": "$bool"}
# game:panel gives a "panel" and game:screen and game:start_screen a "screen": atgui containers (tables()["ui_kinds"] has
# their methods; what those make is atgui's, as tuff_atgui.MAKES says).
_MENUS = {"panel": "panel", "screen": "screen", "start_screen": "screen"}
GIVES = {
    "game": {"open": "$bool", "frame": "$number", "held": "$bool", "pressed": "$bool", "mouse_x": "$number",
             "mouse_y": "$number", "time": "$number", "fps": "$number", "paused": "$bool", "width": "$number",
             "height": "$number", "random_spot": "$list", "group": "group", "hud": "hud", "box": "sprite",
             "circle": "sprite", "line": "sprite", "text": "sprite", "image": "sprite", **_MENUS},
    "world": {"open": "$bool", "frame": "$number", "held": "$bool", "pressed": "$bool", "mouse_x": "$number",
              "mouse_y": "$number", "time": "$number", "fps": "$number", "paused": "$bool", "width": "$number",
              "height": "$number", "random_spot": "$list", "group": "group", "hud": "hud", "light": "object",
              "ground": "object", "island": "object", "box": "object", "sphere": "object", "cylinder": "object",
              "cone": "object", "plane": "object", "spawn": "object", "player": "player", "terrain": "terrain",
              "car": "car", "ragdoll": "ragdoll", **_MENUS,
              "time_of_day": "$number"},
    "screen": {"shown": "$bool"},
    "terrain": {"height_at": "$number", **{m: "terrain" for m, _ in Terrain.NAMES if m != "height_at"}},
    "sprite": {"x": "$number", "y": "$number", "spot": "$list", "angle": "$number", "on_screen": "$bool",
               "distance": "$number", "value": "$text", **{m: "sprite" for m in _SETTERS}},
    "object": {**_OBJECT_GIVES, **{m: "object" for m in _SETTERS}},
    "car": {**_OBJECT_GIVES, **{m: "car" for m in _SETTERS}, "speed": "$number", "drive": "car", "engine": "car",
            "flip": "car"},
    "ragdoll": {**_OBJECT_GIVES, **{m: "ragdoll" for m in _SETTERS}},
    "player": {"x": "$number", "y": "$number", "z": "$number", "spot": "$list", "angle": "$number",
               "distance": "$number", "hold": "object", "move_to": "player", "turn_to": "player",
               "walk_speed": "player", "jump_height": "player", "jump": "player", "hide": "player", "show": "player",
               "on_hit": "player"},
    "hud": {"text": "sprite", "box": "sprite", "circle": "sprite", "line": "sprite", "image": "sprite"},
    "group": {"items": "$list", "count": "$number", "has": "$bool", "add": "group", "remove": "group",
              "move": "group", "hide": "group", "show": "group", "clear": "group", "color": "group"},
}
# Events: method -> (where the function goes, how many inputs the function is given, what they are).
_EVENTS = {"every_frame": (0, 1, "1 input (the seconds since the last frame)"), "on_key": (1, 1, "1 input (the key's name)"),
           "after": (1, 0, "no inputs"), "every": (1, 0, "no inputs"), "game_over": (1, 0, "no inputs")}
_HIT = (0, 2, "2 inputs (the thing that hit it and how hard)")
HANDLERS = {
    "game": {**_EVENTS, "clicked": (0, 2, "2 inputs (x and y)")},
    "world": {**_EVENTS, "clicked": (0, 3, "3 inputs (the x, y and z it clicked)")},
    "sprite": {"clicked": (0, 1, "1 input (the sprite)"), "on_hit": _HIT},
    "object": {"clicked": (0, 1, "1 input (the object)"), "on_hit": _HIT},
    "car": {"clicked": (0, 1, "1 input (the car)"), "on_hit": _HIT},
    "ragdoll": {"clicked": (0, 1, "1 input (the ragdoll)"), "on_hit": _HIT},
    "player": {"on_hit": _HIT},
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
    ("sprite", "align"): {0: "align"}, ("player", "hold"): {0: "hold"}, ("world", "terrain"): {1: "terrain style"},
    ("terrain", "style"): {0: "terrain style"}, ("world", "lighting"): {0: "lighting"},
    **{(k, "physics"): {0: "physics"} for k in ("sprite", "object", "car", "ragdoll")},
    **{("world", m): {1: "color", 3: "color"} for m in ("car", "ragdoll")},
    **{(k, "color"): {0: "color"} for k in ("car", "ragdoll")}, **{(k, "glow"): {0: "glow"} for k in ("car", "ragdoll")},
    **{(k, m): {0: "key"} for k in ("game", "world") for m in ("held", "pressed")},
    **{(k, "on_key"): {0: "anykey"} for k in ("game", "world")},
    **{(k, "sound"): {0: "sound"} for k in ("game", "world")},
    **{(k, "music"): {0: "music"} for k in ("game", "world")},
    **{(k, "panel"): {0: "anchor"} for k in ("game", "world")},
    ("world", "weather"): {0: "weather"}, ("world", "pop_text"): {4: "color"}, ("game", "pop_text"): {3: "color"},
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
        # The game window only loads files from the .tuf's folder and the folders inside it (Game.file_url).
        path = value.strip()
        if not os.path.isabs(path):
            outside = os.path.normpath(path).replace("\\", "/").split("/")[0] == ".."
        else:
            try:
                folder = os.path.normcase(os.path.abspath(base_dir)) if base_dir else None
                outside = folder is not None and os.path.commonpath([os.path.normcase(os.path.abspath(path)), folder]) != folder
            except ValueError:  # another drive
                outside = True
        if outside:
            return f"The {word} '{path}' has to be next to your .tuf file, or in a folder inside it."
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
    if what == "terrain style":
        return None if low in TERRAIN_STYLES else style_problem(low)
    if what == "lighting":
        return None if low in LIGHTINGS else lighting_problem(low)
    if what == "anchor":
        return None if anchor_name(value) else anchor_problem(value.strip())
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
    if what == "physics":
        return None if PHYSICS_WORDS.get(low, low) in PHYSICS_KINDS else physics_problem(low)
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
    if what == "weather":
        return None if WEATHER_WORDS.get(low, low) in WEATHERS else weather_problem(value)
    if what == "image":
        return file_problem(IMAGE_FILES, "picture")
    return None


def tables():
    """For tuff.py --check, without opening a window: tgame's functions, every kind's methods, what they give
    back, the events, the hints for guessed names, and check_value for text inputs. "ui_kinds" has the methods of
    a game's panels and screens (atgui containers, so they aren't among tgame's own kinds), and "anchors" the
    places a panel can go."""

    class FakeRt:
        def builtin(self, name, fn):
            return fn

    def probe(cls):
        return object.__new__(cls)

    kinds = {}
    for kind, cls in (("game", Game2D), ("world", World3D), ("sprite", Sprite), ("object", Thing),
                      ("player", Player), ("hud", Hud), ("group", Group), ("terrain", Terrain), ("car", Car),
                      ("ragdoll", Ragdoll)):
        obj = probe(cls)
        kinds[kind] = {name: getattr(obj, attr) for name, attr in cls.NAMES}
    ui_kinds = {"panel": probe(Panel).methods(), "screen": probe(StartScreen).methods()}
    return {"lib": make_library(FakeRt()), "kinds": kinds, "gives": GIVES, "handlers": HANDLERS, "hints": HINTS,
            "check": check_value, "ui_kinds": ui_kinds, "anchors": ANCHORS, "physics_kinds": PHYSICS_KINDS,
            "physics_words": PHYSICS_WORDS, "needs_3d": NEEDS_3D, "weathers": WEATHERS}
