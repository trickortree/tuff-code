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
import atexit
import base64
import collections
import errno
import json
import math
import os
import queue
import random
import re
import selectors
import socket
import struct
import sys
import threading
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
# Files a splash screen can't show (game:splash "intro.mp4"): anything else that isn't a picture is text to show.
NOT_PICTURES = SOUND_FILES + MODEL_FILES + (".mp4", ".webm", ".mov", ".avi", ".mkv", ".txt", ".tuf", ".pdf", ".ico")

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
KIT = ("tree", "pine", "rock", "bush", "flower", "house", "hut", "sign", "crate", "fence", "coin", "chest", "person", "key")
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
               "destroy": "remove", "kill": "remove", "wrap": "on_edge", "keep_on_screen": "on_edge",
               # sprite-sheet animation (1.5.0)
               "animate": "play", "play_animation": "play", "add_animation": "animation", "anim": "animation",
               "set_frame": "frame", "goto_frame": "frame", "show_frame": "frame", "sheet": "frames",
               "sprite_sheet": "frames", "spritesheet": "frames", "on_end": "on_done",
               "on_finish": "on_done", "on_finished": "on_done", "on_complete": "on_done", "on_animation_end": "on_done",
               "stop_animation": "stop"},
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
UI_HINTS = {"overlay": "screen", "popup": "screen", "dialog": "screen", "modal": "screen",
            "start_menu": "start_screen", "click_to_play": "start_screen", "ui": "panel",
            "gui": "panel", "toolbar": "panel", "sidebar": "panel"}
# ... and for splash screens and main menus (game:splash, game:main_menu).
UI_HINTS.update({"title_screen": "splash", "intro": "splash", "logo": "splash", "splash_screen": "splash",
                 "splashscreen": "splash", "logo_screen": "splash", "intro_screen": "splash", "menu": "main_menu",
                 "home_screen": "main_menu", "menu_screen": "main_menu", "mainmenu": "main_menu",
                 "title_menu": "main_menu", "home_menu": "main_menu"})
HINTS["game"].update(UI_HINTS)
HINTS["world"].update(UI_HINTS)
# The mouse in a 3D world: locked for looking around, or free (world:lock_mouse...), and the names people guess.
MOUSE_NAMES = ("lock_mouse", "unlock_mouse", "mouse_locked", "auto_lock")
HINTS["world"].update({
    "release_mouse": "unlock_mouse", "free_mouse": "unlock_mouse", "show_cursor": "unlock_mouse", "show_mouse": "unlock_mouse",
    "unlock_cursor": "unlock_mouse", "unlock_pointer": "unlock_mouse", "exit_pointer_lock": "unlock_mouse",
    "release_pointer": "unlock_mouse", "capture_mouse": "lock_mouse", "hide_cursor": "lock_mouse", "hide_mouse": "lock_mouse",
    "lock_cursor": "lock_mouse", "lock_pointer": "lock_mouse", "pointer_lock": "lock_mouse", "request_pointer_lock": "lock_mouse",
    "grab_mouse": "lock_mouse", "is_mouse_locked": "mouse_locked", "mouse_is_locked": "mouse_locked", "is_locked": "mouse_locked",
    "locked": "mouse_locked", "cursor_locked": "mouse_locked", "pointer_locked": "mouse_locked", "click_to_lock": "auto_lock",
    "lock_on_click": "auto_lock", "autolock": "auto_lock", "auto_lock_mouse": "auto_lock"})
NEEDS_3D.update(dict.fromkeys(MOUSE_NAMES, "Locking the mouse is for looking around in a 3D world. Make the game with "
                                           "tgame.world(...) and give it a player: world:player(\"first person\")."))

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


def song_of(v):
    """The tmusic song behind a Tuff value (tmusic.song: game:music(song) and game:sound(song) play it), or None."""
    return getattr(v, "song", None)


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
        ("splash", "splash"), ("main_menu", "main_menu"),
    ]

    def __init__(self, lib, title, width, height):
        import tuff_view
        self.tv = tuff_view
        self.lib, self.rt = lib, lib.rt
        self.W, self.H = width, height
        self.save_file = SavedData(self, title)  # game:save and game:load (saved game data) keep this first title
        self.ui = None  # the game's menus (GameUI), once game:panel or a screen made them
        self.closed = self.close_seen = False
        self.down, self.just = set(), set()
        self.input_paused = False  # this frame's keys and clicks were a screen's: the game was paused, or they hid one
        self.lock_click = False  # this frame's click is the one that locks the mouse for looking around
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
        self.flipping = False  # a picture has played frames (sprite:play): the page's canvases hear about pausing
        self.net = None  # its multiplayer (Net), once it hosts, joins or shares something
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
        if self.flipping:
            self.flip_pause()
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
        ui = self.ui
        hides = ui.hides if ui is not None else 0
        self.input_paused, self.lock_click = self.is_paused, False
        self.handle(self.view.events())
        if self.ui is not None and self.ui.hides != hides:  # a key hid a screen (E in on_key closed a note): that's all it did
            self.input_paused = True
        if self.autopilot:
            self.autopilot.tick(t)
        if self.closed or not self.view.is_open:
            self.closed = True
            return 0
        if self.net is not None:  # what the other players said and did: messages, who came and went, where they are
            self.net.frame(real)
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

    def flip_pause(self):
        """Pictures that play frames (sprite:play) step through them by themselves in the page (flip.js), and hold
        still while the game is paused: the game's canvas and the HUD's say so (data-paused, as a world's scene does
        for anim.js)."""
        paused = bool(self.is_paused)
        for layer in ([] if self.three_d else [self]) + ([self.hud_layer] if self.hud_layer is not None else []):
            if getattr(layer, "flip_paused", False) != paused:
                layer.flip_paused = paused
                self.view.set(layer.node, attrs={"data-paused": paused})

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
                if e.get("locks") and not self.fake_lock:  # the page asked to lock the mouse in this click
                    self.lock_click = True
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
                self.on_lock()
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
            elif t == "tg-lock":  # the page asked to lock the mouse (a start screen's click, world:lock_mouse...)
                self.lock_asks += 1
                if ui is not None:
                    ui.lock_asks += 1
            elif t == "tg-splash" and ui is not None:  # a splash screen ended, or all of them did
                ui.splash_event(e)
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
        song = song_of(name)
        if song is not None:  # tmusic's song (1.5.0): it plays once, and the game goes on
            url = self.song_url(song)
            if url is not None:
                self.sound_count += 1
                self.view.call(0, "sound", f"s{self.sound_count}", url, 1, False)
            return None
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
        song = song_of(file)  # a sound file, or tmusic's song (1.5.0)
        url = self.song_url(song) if song is not None else self.file_url(file, "music", SOUND_FILES)[0]
        if url is None:
            return
        self.view.call(0, "sound_stop", "music")
        self.view.call(0, "sound", "music", url, 0.6, True)

    def song_url(self, song):
        """The page's address for a tmusic song's .wav, which tmusic makes once and keeps in a folder of its own: the
        window shares that folder with its page. None in Tuff Engine's preview, which plays no sound (so it doesn't
        spend the time making it)."""
        song.ready()
        if SCENE is not None:
            return None
        folder, name = os.path.split(song.wav())
        self.tv.share("music", folder)
        return self.view.shared_url("music", name)

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
        if self.net is not None:
            self.net.stop()  # a host says goodbye to the other players first
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
        """Removes every sprite and object the program made (the player and a countdown stay). What it removes stops
        moving by itself as it goes (it leaves self.movers)."""
        for thing in list(self.things):
            thing.remove()
        self.things = {}

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

    # ---- splash screens and the main menu (Splashes and MainMenu, after StartScreen)
    lock_asks = 0  # times the page asked the browser to lock the mouse (for the autopilot's reports)

    def splash(self, what=None, seconds=2):
        """A splash screen at the start of the game, before any main menu or start screen: a picture file from the
        project folder (shown fitted, on black) or some text. game:splash() is "Made with Tuff"."""
        ui = self.menus()
        if self.rt.callable(what):
            raise self.rt.error("game:splash takes a picture file or some text, then how many seconds it shows, "
                                "like game:splash(\"logo.png\", 3). The game starts by itself after the splash screens.")
        secs = self.num(seconds, ":splash")
        if not secs > 0:
            raise self.rt.error(":splash needs a number of seconds above 0, like game:splash(\"logo.png\", 3).")
        if self.rt.plain(what) is None:
            ui.splashes().add("tuff", None, secs, "Made with Tuff")
            return None
        text = ui.lib.text(what)
        low = text.strip().lower()
        if low.endswith(IMAGE_FILES):
            url, _ = self.file_url(text, "picture", IMAGE_FILES)
            ui.splashes().add("picture", url, secs, text.strip())
        elif low.endswith(NOT_PICTURES):
            raise self.rt.error(f"'{text.strip()}' can't be a splash screen. Use a picture from your project folder "
                                "(.png, .jpg or .gif), or some text.")
        else:
            ui.splashes().add("text", text, secs, text)
        return None

    def main_menu(self, title=None):
        """A main menu: a screen with a big title and wide buttons, shown when the game starts (after the splash
        screens), with the game paused and the mouse free until menu:hide()."""
        ui = self.menus()
        if self.rt.callable(title):
            raise self.rt.error("A main menu's input is its title, like: menu = game:main_menu(\"My Game\"). "
                                "Then add buttons to it: menu:button(\"Play\", play).")
        return MainMenu(ui, self.view.title if title is None else ui.lib.text(title)).native()

    def on_lock(self):
        """The page's mouse lock changed (World3D keeps track of why)."""

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

# How heavy things are (kg) in a 3D world's physics, when the program doesn't say (thing:weight). The kit's models
# weigh what they'd weigh as they're made (more or less with :scale, by how much more or less of it there is); the
# shapes (box, ball, cylinder, cone, plane) and models from files weigh 50 kg a cubic metre, so a 1 m box is 50 kg.
# The player is 70 kg (it shoves light things out of its way and can't budge heavy ones), a ragdoll 70 kg and a car
# 1200 kg. thing:push's numbers are the speed it gives a 50 kg thing like a 1 m box (physics.js's PUSH_KG), so a
# heavier one goes slower and a lighter one faster (and boxes and balls move just as they did before things had
# weights), and on_hit's strength is in the same units. The player can grab (player:can_grab) things up to GRAB_KG.
KIT_WEIGHT = {"tree": 400, "pine": 300, "rock": 300, "bush": 8, "flower": 0.3, "house": 6000, "hut": 1500, "sign": 15,
              "crate": 25, "fence": 20, "coin": 0.05, "chest": 40, "person": 70, "key": 0.1}
SHAPE_DENSITY = 50
PUSH_KG = 50
PLAYER_KG = 70
GRAB_KG = 100


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
        self.moved_in = 0  # the batch that took the program's last move of its body to the page (see phys_moved)

    def phys_name(self):
        """What it's called in a message ("box:mass needs...")."""
        return self.kind

    def phys_changed(self):
        if self.game.phys is not None:
            self.game.phys.sync(self)

    def dynamic(self):
        return self.phys_kind == "dynamic" and self.game.phys is not None

    def phys_moved(self):
        """The program moved its body (or set its speed): the page's reports from before that reached the page are
        old, and don't put it back (a ball sent back up as it lands isn't sent up twice)."""
        if self.dynamic() and self.game.phys.live:
            self.moved_in = self.game.view.batch

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

    def weight(self, kg=MISSING):
        return self.set_weight(kg, "weight", f"{self.EXAMPLE}:weight({'50' if self.D == 3 else '2'})")

    def mass(self, kg=MISSING):  # the same as weight, by its physics name
        return self.set_weight(kg, "mass", f"{self.EXAMPLE}:mass(2)")

    def set_weight(self, kg, name, example):
        """thing:weight(kg) sets how heavy it is; thing:weight() gives it back (its own, or the one it has by
        default: see KIT_WEIGHT)."""
        if kg is MISSING:
            return tidy(round(self.weight_now(), 3))
        m = self.num(kg, f":{name}")
        if m <= 0:
            raise self.rt.error(f"{self.phys_name()}:{name} needs a number above 0, like {example}.")
        self.mass_ = m
        self.phys_changed()
        return self.native

    def weight_now(self):
        return self.mass_ if self.mass_ is not None else self.default_weight()

    def default_weight(self):
        """How heavy it is when the program doesn't say, in kg: in 2D, 1 kg for every 50 x 50 pixels (Rapier's own,
        from its shape: a line is a capsule 4 pixels thick)."""
        if self.shape == "line":
            (ax, ay), (bx, by) = self.points
            return max(0.01, (4 * math.hypot(bx - ax, by - ay) * self.k + 4 * math.pi) / 2500)
        hw, hh = self.half()
        area = math.pi * hw * hh if self.shape == "circle" else 4 * hw * hh
        return max(0.01, area / 2500)

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
            self.phys_moved()
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
                "auto_weight": tidy(round(self.default_weight(), 3)),
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
        return self.make("image", x, y, {"src": url, "w": w, "h": h, "file": g.rt.text(file), "pic": (nw, nh),
                                         "sized": width is not None}).native

    def clear_layer(self):
        """hud:clear(): removes what the program drew on it. tgame's own (the "E: Talk" hint, the crosshair, the pause
        screen) stay, as with game:clear."""
        for s in list(self.sprites):
            if s.layer is self and s in self.game.things:
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
        ("physics", "physics"), ("weight", "weight"), ("mass", "mass"), ("bounce", "bounce"), ("friction", "friction"), ("push", "kick"),
        ("velocity", "velocity"), ("on_hit", "on_hit"), ("sleep", "sleep"), ("wake", "wake"),
        # 1.5.0: sprite-sheet animation (a picture cut into frames)
        ("frames", "frames"), ("frame", "frame"), ("animation", "animation"), ("play", "play"), ("stop", "stop_frames"),
        ("on_done", "on_done"),
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
        self.pic = props.pop("pic", None)  # a picture's own size (width, height), for cutting it into frames
        self.sized = props.pop("sized", False)  # its width was given (game:image's, or :size): frames keep it
        self.sheet = None  # a picture cut into frames (Flipbook), once :frames cut it
        self.done_fns = []  # :on_done's functions, for an animation that plays once
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
        if self.dynamic():  # its body goes there; a shake only nudges where it's drawn
            self.send(x=self.x, y=self.y, nudge=[self.dx, self.dy])
            self.phys_moved()
            return
        self.send(x=self.x + self.dx, y=self.y + self.dy)

    def push_rot(self):
        self.send(rot=self.rot)
        self.phys_moved()

    def moved(self):
        if self.edge != "none":
            self.apply_edge(False)
        self.push()

    def busy(self):
        if self.vx or self.vy or self.spin_speed or self.anims or (self.sheet is not None and self.sheet.once()):
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
        self.push_rot()
        return self.native

    def turn_to(self, degrees):
        self.rot = self.num(degrees, ":turn_to") % 360
        self.push_rot()
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
            self.push_rot()
        return self.native

    def speed(self, vx=MISSING, vy=0):
        if vx is MISSING:  # how fast it goes (pixels a second)
            return tidy(math.hypot(*self.velocity_now()))
        v = [self.num(vx, ":speed"), self.num(vy, ":speed")]
        if self.dynamic():
            self.vel = v
            self.game.phys.send("velocity", int(self.node), *v)
            self.phys_moved()
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
            self.sized = True
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
            if self.game.phys is not None and self.phys_sent is not None:
                self.game.phys.forget(self)  # a hit it was in still names it

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
            self.pic = image_size(full) or self.pic  # a sprite sheet's frames are cut from the picture it shows now
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

    # ---- sprite-sheet animation: a picture cut into a grid of frames (Flipbook)
    def picture_only(self, what):
        if self.shape != "image":
            also = " To stop a sprite moving, use sprite:speed(0, 0)." if what == ":stop" else ""
            raise self.rt.error(f"Only pictures have frames ({what}). Make one with game:image(\"hero_sheet.png\", 100, 300), "
                                f"then cut it into frames with hero:frames(4).{also}")

    def flipbook(self, what):
        """Its frames, for :frame, :animation and :play: the picture has to be cut into frames first."""
        self.picture_only(what)
        if self.sheet is None:
            raise self.rt.error(f"{what} needs the picture cut into frames first: hero:frames(4) for 4 frames side by side, "
                                "or hero:frames(4, 2) for 4 across and 2 down.")
        return self.sheet

    def whole(self, v, what, message):
        n = self.num(v, what)
        if n != int(n) or n < 1:
            raise self.rt.error(message)
        return int(n)

    def frame_number(self, v, what):
        """A frame of its picture: a whole number from 1 to how many frames it has."""
        f = self.sheet
        count = f.cols * f.rows
        n = self.num(v, what)
        if n != int(n) or n < 1:
            raise self.rt.error(f"{what}: frames are numbered from 1 (the top left one), so there's no frame {tidy(n)}.")
        if n > count:
            raise self.rt.error(f"{what}: this picture has {count} frame{'s' if count != 1 else ''} (1 to {count}), "
                                f"so there's no frame {tidy(n)}.")
        return int(n)

    def frames(self, across, down=1):
        """sprite:frames(4) or (4, 2): cuts its picture (a sprite sheet) into frames, so many across and so many
        down, numbered from 1 left to right, then the next row. It shows frame 1, as big as the width the picture was
        given (or one frame's own size), and anything playing stops. Animations it made before stay."""
        self.picture_only(":frames")
        how = (":frames needs how many frames across, then how many down (1 if you leave it out), as whole numbers "
               "from 1, like hero:frames(4) or hero:frames(4, 2).")
        cols, rows = self.whole(across, ":frames", how), self.whole(down, ":frames", how)
        if cols * rows > MAX_FRAMES:
            raise self.rt.error(f":frames can cut a picture into {MAX_FRAMES} frames at most, not {cols * rows}.")
        nw, nh = self.pic or (self.w, self.h)
        fw, fh = nw / cols, nh / rows
        self.w = self.w if self.sized else fw
        self.h = self.w * fh / fw if fw else self.w
        named = self.sheet.named if self.sheet is not None else {}
        self.sheet = Flipbook(cols, rows, named)
        self.send(cells=[cols, rows], cell=1, play=None, w=self.w, h=self.h)
        if self.phys_kind is not None:
            self.phys_changed()  # one frame is its size now: its body's too
        self.busy()
        return self.native

    def frame(self, number=MISSING):
        """sprite:frame(3) shows frame 3 (and stops what's playing). sprite:frame() gives the frame it shows now."""
        if number is MISSING:
            self.picture_only(":frame")
            return 1 if self.sheet is None else self.sheet.showing(self.game.clock)
        f = self.flipbook(":frame")
        n = self.frame_number(number, ":frame")
        if f.playing is not None or f.cell != n:  # standing still with hero:frame(1) every frame sends nothing new
            f.playing, f.cell = None, n
            self.send(play=None, cell=n)
            self.busy()
        return self.native

    def animation(self, name, frames, speed=10):
        """sprite:animation("walk", [1, 2, 3, 4], 10): names some of its frames, in the order they show, and how many
        a second (10 if you leave it out). Making one that's playing starts it again with its new frames."""
        f = self.flipbook(":animation")
        key = self.rt.plain(name)
        if not isinstance(key, str) or not key.strip():
            raise self.rt.error(":animation needs a name as text first, then the frames and how many a second, like "
                                "hero:animation(\"walk\", [1, 2, 3, 4], 10).")
        items = self.rt.plain(frames)
        if not isinstance(items, list):
            raise self.rt.error(f":animation needs its frames as a list, like hero:animation(\"{key}\", [1, 2, 3, 4], 10).")
        if not items:
            raise self.rt.error(f":animation needs at least one frame, like hero:animation(\"{key}\", [1, 2, 3, 4], 10).")
        nums = [self.frame_number(v, ":animation") for v in items]
        fps = self.num(speed, ":animation")
        if fps <= 0:
            raise self.rt.error(f":animation's speed is how many frames a second, above 0, like hero:animation(\"{key}\", "
                                "[1, 2, 3, 4], 10).")
        f.named[key] = (nums, fps)
        if f.playing == key:
            self.start_animation(key, f.loop)
        return self.native

    def play(self, name, loop=True):
        """sprite:play("walk") plays an animation again and again; sprite:play("jump", false) plays it once and stays
        on its last frame (then :on_done's functions run). Playing the one that's playing already carries on, so it can
        go in every frame of a loop."""
        f = self.flipbook(":play")
        key = self.rt.plain(name)
        if not isinstance(key, str):
            raise self.rt.error(f":play needs the name of an animation as text, like hero:play(\"walk\"), not {self.rt.what(key)}.")
        if key not in f.named:
            raise self.rt.error(no_animation(key, list(f.named)))
        again = self.rt.plain(loop)
        if not isinstance(again, bool):
            raise self.rt.error(f":play's second input is true (again and again, the same as leaving it out) or false "
                                f"(once), like hero:play(\"{key}\", false).")
        if f.playing != key or f.loop != again:
            self.start_animation(key, again)
        return self.native

    def start_animation(self, key, loop):
        f = self.sheet
        frames, fps = f.named[key]
        count = f.cols * f.rows
        over = next((n for n in frames if n > count), None)
        if over is not None:  # :frames cut the picture into fewer frames after the animation was made
            raise self.rt.error(f"The animation \"{key}\" shows frame {over}, but this picture has {count} frames now (1 to {count}).")
        f.playing, f.loop, f.at = key, loop, self.game.clock
        self.send(play=[frames, tidy(fps), loop])
        self.game.flipping = True  # the page needs to know when the game pauses (Game.flip_pause)
        self.busy()

    def stop_frames(self):
        """sprite:stop() stops the animation playing, on the frame it shows."""
        self.picture_only(":stop")
        f = self.sheet
        if f is not None and f.playing is not None:
            f.cell, f.playing = f.showing(self.game.clock), None
            self.send(play=None, cell=f.cell)
            self.busy()
        return self.native

    def on_done(self, fn):
        """sprite:on_done(landed): runs landed(sprite, name) when an animation that plays once (:play(name, false))
        has shown its last frame."""
        self.picture_only(":on_done")
        self.done_fns.append(self.game.lib.check_fn(fn, ":on_done"))
        return self.native

    def animation_done(self):
        f = self.sheet
        name = f.playing
        f.playing, f.cell = None, f.named[name][0][-1]
        self.send(play=None, cell=f.cell)  # it stays on its last frame (the page shows it already)
        for fn in list(self.done_fns):
            self.game.fire(fn, self.native, name)

    # ---- every frame, while it moves by itself
    def tick(self, dt):
        moved = glided = False
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
                moved = glided = True
            elif a[0] == "shake":
                self.dx = math.sin(a[1] * 70) * 6 * (1 - t)
                moved = True
            if t >= 1:
                self.anims.remove(a)
                if a[0] == "shake":
                    self.dx = 0.0
        if moved and self.dynamic() and not glided:  # physics moves it: a shake only nudges where it's drawn
            self.send(nudge=[self.dx, self.dy])
        elif moved:
            if self.edge != "none":
                self.apply_edge(True)
            self.push()
            if self.dynamic():  # a glide carries it: no speed builds up meanwhile
                self.game.phys.send("velocity", int(self.node), 0, 0)
        f = self.sheet
        if f is not None and f.once() and f.ended(self.game.clock):
            self.animation_done()  # last: its functions may move it, play another or remove it
        self.busy()


MAX_FRAMES = 10000  # the most frames sprite:frames cuts a picture into


def no_animation(name, names):
    """sprite:play's message for an animation it hasn't made (with "did you mean")."""
    if not names:
        return (f"There's no animation called \"{name}\". Make it first, like "
                f"hero:animation(\"{name}\", [1, 2, 3, 4], 10), then hero:play(\"{name}\").")
    shown = ", ".join(f'"{n}"' for n in names)
    return f"There's no animation called \"{name}\". This picture has {shown}.{did_you_mean(name, names)}"


class Flipbook:
    """A picture cut into a grid of frames (sprite:frames), the animations it has (sprite:animation: a name, its
    frames and how many a second) and the one playing (sprite:play). The page steps through the frames by itself
    (tuff_view_web/flip.js) by the game's clock, so they slow down in slow motion and hold still while the game is
    paused. Python goes by the same clock (game:time) to know the frame it shows (sprite:frame()) and when one that
    plays once has shown its last frame (sprite:on_done)."""

    def __init__(self, cols, rows, named=None):
        self.cols, self.rows = cols, rows
        self.named = named if named is not None else {}  # name -> (its frames, how many a second)
        self.playing = None  # the animation playing, or None
        self.loop = True     # it plays again and again (False: once)
        self.at = 0.0        # the game's time when it started
        self.cell = 1        # the frame it shows while nothing plays

    def once(self):
        """Playing an animation that plays once: Python watches for its end (a loop needs nothing each frame)."""
        return self.playing is not None and not self.loop

    def steps(self, clock):
        frames, fps = self.named[self.playing]
        return int((clock - self.at) * fps + 1e-6), frames

    def showing(self, clock):
        if self.playing is None:
            return self.cell
        i, frames = self.steps(clock)
        return frames[i % len(frames)] if self.loop else frames[min(i, len(frames) - 1)]

    def ended(self, clock):
        i, frames = self.steps(clock)
        return i >= len(frames)


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
        ("door", "door"),
        ("jump_pad", "jump_pad"), ("boost_pad", "boost_pad"),
        ("lock_mouse", "lock_mouse"), ("unlock_mouse", "unlock_mouse"), ("mouse_locked", "mouse_locked"),
        ("auto_lock", "auto_lock"),
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
        self.interact = None  # talking, grabbing, doors and keys (Interaction), once something uses them

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
        t.floor_color = c  # for a minimap (the HUD)
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
        look = person_look() if low == "person" else None
        size, body, parts, solid = kit(low, look)
        t = Thing(self, low, x, y, z, size, parts, body=body)
        t.look = look
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
    # ---- talking, grabbing, doors and keys (see Interaction)
    def interaction(self):
        if self.interact is None:
            self.interact = Interaction(self)
        return self.interact

    def door(self, x=MISSING, y=MISSING, z=MISSING, color=MISSING):
        x, y, z, (color,) = self.where([x, y, z, color], ("wood",), "door")
        return Door(self, x, self.above(x, y, z), z, color).native
    # ---- level pieces: jump pads, boost pads and things on paths (Level, after the ragdoll)
    def level(self):
        """The world's level pieces, made by the first one."""
        if getattr(self, "level_", None) is None:
            self.level_ = Level(self)
        return self.level_

    def jump_pad(self, x=MISSING, y=MISSING, z=MISSING, power=MISSING):
        return self.level().make_pad("jump", [x, y, z, power])

    def boost_pad(self, x=MISSING, y=MISSING, z=MISSING, power=MISSING):
        return self.level().make_pad("boost", [x, y, z, power])

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
        self.view.set(self.scene, clicklock=self.clicks_lock())
        if getattr(self, "hud_js", None) is not None:  # a minimap or an arrow made first measures from the player now
            self.hud_js.player()
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
            no_click = not (self.clicks_lock() or self.lock_want)  # world:auto_lock(false): a click doesn't lock it
            self.hint.hide() if (self.locked or self.fake_lock or covered or no_click) else self.hint.show()

    # ---- the mouse: locked for looking around, or free (to read a note, use a shop or a menu)
    auto_lock_on = None  # world:auto_lock(on); None: a click on the game locks the mouse once there's a player
    lock_want = False  # world:lock_mouse() the browser hasn't allowed yet: the next click on the game locks it
    freeing = False  # tgame let go of the mouse itself, so the unlock coming isn't the player's Escape
    fake_freed = False  # a screen let go of the autopilot's pretend lock: it comes back when the lock is asked again
    escaped_at = -1e9  # when the player let go of the mouse with Escape
    escaped = False  # the player let go of it with Escape, and nothing has locked it since
    asked_at = -1e9  # when the page was last asked to lock it
    mouse_js = False  # MOUSE_JS is on the page

    def lock_mouse(self):
        """Lock the mouse for looking around: now if the page allows it (tuff_view's hold: while the game's window has
        the focus; the browser's own lock: in a click or a key press, or just after one), or else on the next click on
        the game. Under a screen, once the last screen hides. After the player let go of it with Escape, only their
        next click on the game locks it (as browsers want), so a program that asks every frame doesn't take the mouse
        straight back, or ask the page 60 times a second."""
        ui = self.ui
        if ui is not None and ui.showing:
            ui.relock = True
        elif not self.mouse_locked():
            if self.escaped or (self.lock_want and time.perf_counter() - self.asked_at < 1.0):
                self.want(True)
            else:
                self.want_lock()
        self.lock_changed()

    def unlock_mouse(self):
        """Let go of the mouse, and keep it free until lock_mouse or a click on the game."""
        self.want(False)
        if self.ui is not None:
            self.ui.relock = self.ui.menu_played = False
        self.free_mouse()
        self.fake_freed = False
        self.lock_changed()

    def mouse_locked(self):
        return bool(self.locked or self.fake_lock)

    def auto_lock(self, on=True):
        """Whether a click on the game locks the mouse (it does once there's a player): world:auto_lock(false)
        leaves locking to the program (world:lock_mouse)."""
        self.auto_lock_on = self.rt.truthy(on)
        self.view.set(self.scene, clicklock=self.auto_lock_on)
        self.lock_changed()

    def clicks_lock(self):
        return self.the_player is not None if self.auto_lock_on is None else self.auto_lock_on

    def mouse_held(self):
        """Is the mouse locked (or the autopilot acting as if it were), or did the player let go of it with Escape a
        moment ago? The same Escape often opens a pause menu, and the lock comes back when it closes."""
        return self.locked or self.fake_lock or time.perf_counter() - self.escaped_at < 0.6

    def want(self, on):
        """The next click on the game locks the mouse, even with auto_lock(false) (MOUSE_JS)."""
        if on != self.lock_want:
            self.lock_want = on
            if SCENE is None:
                self.view.set(self.scene, attrs={"data-tg-want": True if on else None})

    def want_lock(self):
        self.want(True)
        self.ask_lock()

    def ask_lock(self):
        """Ask the page to lock the mouse now. The browser allows it only in a click or a key press, or just after
        one, which is when this runs: a menu's button was clicked, or a screen's Close."""
        if SCENE is not None or self.closed:
            return
        self.mouse_page()
        self.view.js("window.__tgMouse.lock()")
        self.asked_at = time.perf_counter()
        if self.fake_freed:  # the autopilot acted as if it was locked: it is again, as a browser allows it here
            self.fake_freed, self.fake_lock = False, True

    def free_mouse(self):
        if self.locked:
            self.freeing = True
        if SCENE is None:
            self.view.call(0, "unlock")
        if self.fake_lock:
            self.fake_lock, self.fake_freed = False, True

    def mouse_page(self):
        if not self.mouse_js and SCENE is None:
            self.mouse_js = True
            self.view.js(MOUSE_JS)

    def on_lock(self):
        if self.locked:
            self.want(False)
            self.escaped = False
            ui = self.ui
            # Locked under a screen (asked for just before it showed): let go again until it's gone. A start
            # screen's own click locks it on purpose, as it hides.
            if ui is not None and ui.showing and not any(isinstance(s, StartScreen) and s.is_shown for s in ui.screens):
                self.free_mouse()
                ui.relock = True
        elif self.freeing:
            self.freeing = False
        else:
            self.escaped_at = time.perf_counter()
            self.escaped = True

    def covered(self, showing):
        """A screen, the main menu or a splash showed or hid (GameUI.changed). The mouse is free while any of them
        shows; when the last one goes, the lock comes back if it was locked before, and after a main menu (its Play
        button starts the game) if a click on the game locks it."""
        ui = self.ui
        if showing:
            if self.mouse_held():
                self.free_mouse()
                ui.relock = True
            return
        lock = ui.relock or (ui.menu_played and self.clicks_lock())
        ui.relock = ui.menu_played = False
        if lock:
            self.want_lock()

    def mouse_state(self):
        """For the autopilot's reports."""
        return {"locked": self.mouse_locked(), "asks": self.lock_asks, "want": self.lock_want, "auto": self.clicks_lock(),
                "relock": bool(self.ui is not None and self.ui.relock)}

    def update(self, dt, real):
        if self.interact is not None:
            self.interact.update(dt)
        if getattr(self, "level_", None) is not None:  # platforms move and pads launch, before the player walks
            self.level_.frame(dt)
        if self.driving is not None:
            self.drive_keys()
        p = self.the_player
        if p is not None:
            p.update(dt, real)
            car = self.driving
            if car is not None:  # in the car: the player is where the car is (player:x, a game on the network)
                p.x, p.y, p.z, p.heading = car.x, car.y, car.z, car.heading % 360
            elif self.phys is not None:
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


def kit(name, look=None):
    """A built-in model: (size, solid body, parts, solid). Parts are (type, engine props, main part?); every part
    casts and gets shadows, and colours vary a little from one model to the next. A part's "anim" says how the page
    moves the model (tuff_view_web/anim.js): a "tree", "pine", "bush" or "flower" sways in the wind, a "coin" spins
    and bobs, and each part of a "person" says which limb it is and where it turns ([style, role, pivot]). A person
    is dressed in `look` (person_look)."""
    if name == "person":
        return (0.7, 1.75, 0.5), None, dressed(look or person_look()), True
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
            ("cylinder", {"rt": 0.055, "rb": 0.065, "h": 1.0, "y": 0.5, "z": -0.07, "seg": 8, "color": "#6b4428", "rough": 0.95}, False),
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
    if name == "key":
        # An old gold key floating upright (it spins and bobs like a coin): a ring to hold, a shaft and its teeth.
        gold = {"color": "#f2c230", "emissive": "#5a4200", "metal": 0.55, "rough": 0.3}
        return ((0.4, 1.2, 0.1), None, [
            ("torus", {"r": 0.11, "tube": 0.032, "y": 1.0, "seg": 28, **gold, "anim": "coin"}, True),
            ("sphere", {"r": 0.045, "y": 0.87, "seg": 10, **gold}, True),
            ("cylinder", {"r": 0.026, "h": 0.4, "y": 0.66, "seg": 10, **gold}, True),
            ("box", {"w": 0.1, "h": 0.045, "d": 0.035, "x": 0.06, "y": 0.5, **gold}, True),
            ("box", {"w": 0.07, "h": 0.04, "d": 0.035, "x": 0.045, "y": 0.58, **gold}, True),
        ], False)
    raise KeyError(name)


# A person's joints, standing (feet at 0, facing -z, its right +x): where its limbs turn. The kit's person, the
# player in third person and the ragdoll are all made by person_parts, so they look alike.
NECK, SHOULDER, ELBOW, HIP, KNEE = 1.4, (0.262, 1.27), 1.02, (0.094, 0.76), 0.43
HEAD = (1.555, 0.178)  # its head's middle, and how round it is
WAIST = 0.855  # where its shirt meets its trousers, under a belt
CHEST = (0.212, 0.188)  # how wide its body is at the shoulders and at the waist (half)
SHIRTS = ("#e5484d", "#3574f0", "#2fa36b", "#f2a33a", "#8e5bd8", "#14b8a6")
SKINS = ("#f1c9a5", "#e0ac7e", "#c68a5c", "#8d5a3b", "#ffd9b8")
HAIRS = ("#2b2018", "#5a3a22", "#a8692e", "#e3c06b", "#1c1c1c", "#b5482b")
PANTS = ("#2f3e5c", "#3b3b44", "#5b4636", "#24456b")
SHOES = ("#3a2a22", "#26262c", "#f4f1ea", "#c8473a", "#2f6fd0")
HAIR_STYLES = ("short", "swoop", "bob", "ponytail", "buns", "curly", "spiky")


LOOK_KEYS = ("shirt", "skin", "hair", "pants", "style", "sleeves", "shoes")
LOOK_METHODS = ("shirt", "pants", "skin", "hair", "shoes", "sleeves")
SLEEVES = ("long", "rolled")
# Words people use for a look, as tgame's own: hair styles, sleeves, and skin and hair colours (other colours are
# the game's colour names or "#rrggbb").
HAIR_WORDS = {"pony": "ponytail", "pony tail": "ponytail", "tail": "ponytail", "bun": "buns", "afro": "curly",
              "curls": "curly", "mop": "curly", "spikes": "spiky", "mohawk": "spiky", "quiff": "swoop", "fringe": "bob",
              "long": "bob"}
SLEEVE_WORDS = {"short": "rolled", "rolled up": "rolled", "rolled-up": "rolled", "up": "rolled", "full": "long"}
SKIN_COLORS = {"pale": "#ffd9b8", "light": "#f1c9a5", "fair": "#f1c9a5", "tan": "#e0ac7e", "medium": "#c68a5c",
               "olive": "#c68a5c", "brown": "#8d5a3b", "dark": "#8d5a3b"}
HAIR_COLORS = {"black": "#1c1c1c", "dark brown": "#2b2018", "brown": "#5a3a22", "blonde": "#e3c06b",
               "blond": "#e3c06b", "ginger": "#b5482b", "auburn": "#a8692e", "red": "#b5482b", "grey": "#9a9a9e",
               "gray": "#9a9a9e", "white": "#eeeeee"}


def person_look(shirt=None, skin=None, hair=None, pants=None, style=None, sleeves=None, shoes=None):
    """A person's look for person_parts: what's given, and the rest picked at random."""
    pick = random.choice
    return {"shirt": shirt or pick(SHIRTS), "skin": skin or pick(SKINS), "hair": hair or pick(HAIRS),
            "pants": pants or pick(PANTS), "style": style or pick(HAIR_STYLES),
            "sleeves": sleeves or pick(("long", "long", "rolled")), "shoes": shoes or pick(SHOES)}


def dressed(look):
    """A person's parts in a look (person_look), each casting a shadow, as a model's parts are."""
    return [(type_, {"shadow": True, **p}, main) for type_, p, main in person_parts(**look)]


def person_parts(shirt=None, skin=None, hair=None, pants=None, style=None, sleeves=None, shoes=None):
    """A chunky toy person (the kit's, the player in third person, and the ragdoll's look), facing -z like
    everything that walks forward: shoes, legs that bend at the knee, hips with a belt, a broad body with round
    shoulders the arms hang from, arms that bend at the elbow, mitten hands, a short neck and a big friendly head
    (eyes, eyebrows, a nose and a smile) with one of a few hair styles. Long sleeves or rolled up to the elbow.

    Each part tells anim.js which part it is and where it turns ([style, role, pivot, the pivot of the limb it hangs
    from]): a thigh turns at the hip and its shin at the knee (and with the thigh), an upper arm at the shoulder and
    its forearm and hand at the elbow, the head at the neck. The shirt's parts are the main ones (person:color)."""
    look = person_look(shirt, skin, hair, pants, style, sleeves, shoes)
    shirt, skin, hair, pants, style, sleeves, shoes = (look[k] for k in LOOK_KEYS)
    sx, sy = SHOULDER
    hx, hy = HIP
    parts = []

    def part(type_, role, main=False, **p):
        # Parts that look the same share a material in the page ("share"): a crowd draws about as fast as before.
        side = -1 if role.endswith("_l") else 1
        pivots = {"leg": [[hx * side, hy, 0]], "shin": [[hx * side, KNEE, 0], [hx * side, hy, 0]],
                  "arm": [[sx * side, sy, 0]], "forearm": [[sx * side, ELBOW, 0], [sx * side, sy, 0]],
                  "head": [[0, NECK, 0]]}.get(role.split("_")[0], [None])
        parts.append((type_, {**p, "share": True, "anim": ["person", role] + pivots}, main))

    cloth, soft = {"rough": 0.88}, {"rough": 0.6}
    for side, x in (("l", -1), ("r", 1)):  # its right is +x (it faces -z)
        # A leg: the thigh's round ends are the hip and the knee, so it bends without a gap. The shin goes down into
        # a big round shoe.
        part("capsule", "leg_" + side, r=0.086, h=hy - KNEE, x=hx * x, y=(hy + KNEE) / 2, seg=10, color=pants, **cloth)
        part("capsule", "shin_" + side, r=0.084, h=KNEE - 0.11, x=hx * x, y=(KNEE + 0.11) / 2, seg=10, color=pants, **cloth)
        part("sphere", "shin_" + side, r=0.1, x=hx * x, y=0.062, z=-0.045, sx=1.02, sy=0.62, sz=1.42, seg=12, color=shoes, rough=0.55)
    for side, x in (("l", -1), ("r", 1)):
        # An arm grows out of the round end of the shoulders: its top is the shoulder, so it turns there without a
        # gap, and it hangs flush against the body. The elbow is the upper arm's other end.
        part("capsule", "arm_" + side, True, r=0.077, h=sy - ELBOW, x=sx * x, y=(sy + ELBOW) / 2, seg=10, color=shirt, **cloth)
        part("capsule", "forearm_" + side, sleeves == "long", r=0.073, h=0.2, x=sx * x, y=ELBOW - 0.1, seg=10,
             color=shirt if sleeves == "long" else skin, **(cloth if sleeves == "long" else soft))
        part("sphere", "forearm_" + side, r=0.088, x=sx * x, y=0.765, sx=0.84, sy=1.08, sz=1.02, seg=12, color=skin, **soft)
        part("sphere", "forearm_" + side, r=0.036, x=(sx - 0.03) * x, y=0.8, z=-0.066, sy=1.2, seg=8, color=skin, **soft)
    # The hips (their round ends are the hip joints), a belt where the shirt meets the trousers, and its buckle.
    part("capsule", "body", r=0.088, h=hx * 2, y=hy, rz=90, sz=1.25, seg=12, color=pants, **cloth)
    part("cylinder", "body", r=CHEST[1] + 0.008, h=0.055, y=WAIST, sz=0.68, seg=16, color="#3d2b20", rough=0.7)
    part("box", "body", w=0.075, h=0.052, d=0.02, y=WAIST, z=-(CHEST[1] + 0.008) * 0.68 - 0.002, color="#e8b84a", metal=0.4, rough=0.35)
    # A broad body, a little wider at the top, rounded over at the top, with a round shoulder each side that the arm
    # grows out of (the round ends of a bar across the shoulders), and a short neck.
    part("cylinder", "torso", True, rt=CHEST[0], rb=CHEST[1], h=sy - WAIST, y=(sy + WAIST) / 2, sz=0.64, seg=16, color=shirt, **cloth)
    part("sphere", "torso", True, r=CHEST[0], y=sy, sy=0.46, sz=0.64, seg=16, color=shirt, **cloth)
    part("capsule", "torso", True, r=0.087, h=sx * 2, y=sy, rz=90, seg=12, color=shirt, **cloth)
    part("cylinder", "torso", rt=0.058, rb=0.066, h=0.12, y=NECK - 0.01, seg=12, color=_shade(skin, -0.08), **soft)
    # The head: big and round, with eyes (a white and a pupil, big enough to see from afar), eyebrows, a little nose
    # and a smile (a ring sunk into the face, its lower half showing). The face is laid out on a head 0.17 round, and
    # grows with the head (k).
    y, r = HEAD
    k = r / 0.17
    part("sphere", "head", r=r, y=y, sx=1.06, seg=20, color=skin, **soft)
    for x in (-0.064 * k, 0.064 * k):
        part("sphere", "head", r=0.043 * k, x=x, y=y + 0.002 * k, z=-0.151 * k, sx=0.9, sy=1.18, sz=0.5, seg=12, color="#ffffff", rough=0.4)
        part("sphere", "head", r=0.025 * k, x=x * 0.94, y=y - 0.003 * k, z=-0.167 * k, sy=1.2, sz=0.55, seg=10, color="#1b1b24", rough=0.25)
        part("capsule", "head", r=0.012 * k, h=0.05 * k, x=x * 1.03, y=y + 0.075 * k, z=-0.139 * k, rz=90 - (8 if x > 0 else -8), sz=0.7,
             seg=6, color=_shade(hair, -0.35), rough=0.8)
    part("sphere", "head", r=0.027 * k, y=y - 0.035 * k, z=-0.168 * k, sy=0.85, seg=10, color=_shade(skin, -0.07), **soft)
    part("torus", "head", r=0.045 * k, tube=0.011 * k, y=y - 0.055 * k, z=-0.144 * k, seg=20, color="#7a2e2a", rough=0.6)
    for type_, p in hair_parts(style, y, k):
        part(type_, "head", **p, color=hair, rough=0.75)
    return parts


def hair_parts(style, y, k=1.0):
    """A hair style's parts on a head whose middle is at y (k: how big the head is, 1 for 0.17 round): a cap over
    the top and back, and what makes the style."""
    def at(type_, **p):
        return (type_, {key: v * k if key in ("r", "h", "x", "z") else y + v * k if key == "y" else v for key, v in p.items()})
    cap = at("sphere", r=0.181, y=0.03, z=0.022, sx=1.07, sy=0.88, seg=20)
    if style == "curly":  # a big round mop
        return [at("sphere", r=0.2, y=0.05, z=0.03, sx=1.06, sy=0.84, seg=14),
                at("sphere", r=0.15, y=-0.01, z=0.09, sx=1.28, sy=0.92, seg=12)]
    if style == "bob":  # down to the chin all round the back, with a fringe
        return [cap, at("sphere", r=0.185, y=-0.015, z=0.065, sx=1.04, sy=0.95, seg=18),
                at("sphere", r=0.15, y=0.085, z=-0.015, sx=1.12, sy=0.42, sz=0.95, seg=14)]
    if style == "ponytail":
        return [cap, at("capsule", r=0.055, h=0.16, y=-0.03, z=0.2, rx=-18, seg=10), at("sphere", r=0.05, y=0.06, z=0.175, seg=10)]
    if style == "buns":
        return [cap, at("sphere", r=0.068, x=-0.13, y=0.125, z=0.02, seg=12), at("sphere", r=0.068, x=0.13, y=0.125, z=0.02, seg=12)]
    if style == "spiky":
        return [cap] + [at("cone", r=0.06, h=0.12, x=x, y=0.15, z=z, rx=rx, rz=rz, seg=6, flat=True)
                        for x, z, rx, rz in ((-0.07, -0.02, -15, 25), (0.0, -0.05, -25, 0), (0.07, -0.02, -15, -25))]
    if style == "swoop":  # swept up and over at the front
        return [cap, at("sphere", r=0.1, x=0.03, y=0.125, z=-0.054, sx=1.5, sy=0.62, sz=0.9, rz=-14, seg=14)]
    return [cap, at("sphere", r=0.12, x=-0.02, y=0.105, z=-0.057, sx=1.35, sy=0.45, sz=0.72, rz=8, seg=14)]


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
        ("physics", "physics"), ("weight", "weight"), ("mass", "mass"), ("bounce", "bounce"), ("friction", "friction"), ("push", "kick"),
        ("velocity", "velocity"), ("on_hit", "on_hit"), ("sleep", "sleep"), ("wake", "wake"),
        ("say", "say"), ("on_talk", "on_talk"),
        ("path", "path"),
        ("shirt", "shirt"), ("pants", "pants"), ("skin", "skin"), ("hair", "hair"), ("shoes", "shoes"),
        ("sleeves", "sleeves"),
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
        self.writing = None  # a sign's words, on its board (label)
        self.look = None  # a person's clothes and hair (person_look): the kit's person, the player's figure
        self.pickable = pick
        self.glow_color = None
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
        self.phys_moved()

    def push_label(self):
        if self.label_node is not None:
            top = self.y + (0.9 if self.fallen else self.height() + 0.25)
            self.send(self.label_node, x=self.x, y=top, z=self.z)

    def push_rotation(self, anim=False):
        """Sends how it's turned. A thing physics moves turns its body only when the program turns it (turn, look_at);
        a shake's or a fall's tilt (anim) only tilts how it's drawn (its wobble), not its body."""
        dyn = self.dynamic()
        if dyn:
            self.send(self.node, wobble=self.wobble())
            if anim:
                return
        tilt, pitch = (0.0, 0.0) if dyn else (self.tilt, self.pitch)
        if self.quat is not None and not tilt and not pitch:  # tumbled by physics: as it lies
            rx, ry, rz = euler_of_quat(self.quat)
        else:
            rx, ry, rz = euler(self.heading, self.tilt_axis, tilt, pitch)
        self.send(self.node, rx=rx, ry=ry, rz=rz)
        self.phys_moved()

    def wobble(self):
        """A shake's or a fall's tilt as a turn about its level axis in the world ([x, y, z, w]), or None."""
        if not self.tilt:
            return None
        kx, kz = self.tilt_axis
        h = math.radians(self.tilt) / 2
        return [round(kx * math.sin(h), 5), 0.0, round(kz * math.sin(h), 5), round(math.cos(h), 5)]

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
        base = {"mass": tidy(round(self.weight_now(), 3)), "bounce": self.bounce_, "friction": self.friction_,
                "hits": bool(self.hit_fns)}
        if kind is None:
            if getattr(self, "floor", False):
                half = self.dims[0] / 2
                if self.kind == "island":  # the grass's cylinder, its top at 0
                    return {**base, "kind": "static", "shape": "cylinder", "size": [1.5, tidy(half)], "cy": -1.5}
                return {**base, "kind": "static", "shape": "box", "size": [tidy(half), 0.5, tidy(self.dims[2] / 2)], "cy": -0.5}
            if not self.solid_ or self.fallen:
                return None
            kind = "static"
        if kind == "static" and getattr(self, "route", None) is not None:  # on a path (Route): it carries what's on it
            kind = "kinematic"
        shape, size, cy = self.phys_shape(kind)
        return {**base, "kind": kind, "shape": shape, "size": size, "cy": cy}

    def default_weight(self):
        """How heavy it is when the program doesn't say (see KIT_WEIGHT), in kg."""
        kx, ky, kz = self.k
        if self.kind in KIT_WEIGHT:
            return KIT_WEIGHT[self.kind] * kx * ky * kz
        w, h, d = self.dims
        if self.kind == "sphere":
            volume = math.pi / 6 * (w * max(kx, ky, kz)) ** 3
        elif self.kind in ("cylinder", "cone"):
            volume = math.pi / 4 * (w * max(kx, kz)) ** 2 * h * ky / (3 if self.kind == "cone" else 1)
        else:
            volume = w * kx * max(h * ky, 0.02) * d * kz
        return max(0.01, volume * SHAPE_DENSITY)

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
        self.push_rotation(anim=True)
        self.push_label() if self.dynamic() else self.push()

    def tick(self, dt):
        moved = rotated = glided = False
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
                moved = glided = True
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
        if moved and self.dynamic() and not glided:  # physics moves it: a grow or a fall only changes how it looks
            self.push_label()
        elif moved:
            self.push()
            if self.dynamic():  # a glide carries it: no speed builds up meanwhile
                self.game.phys.send("velocity", int(self.node), 0, 0, 0)
        if rotated:
            self.push_rotation(anim=True)
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
        if self.look is not None:  # a person's main parts are its shirt
            self.look["shirt"] = c
        for node, main in self.parts:
            if main:
                self.send(node, color=c)
        return self.native

    def glow(self, color="white"):
        name = self.rt.text(color).strip().lower()
        c = "#000000" if name in ("none", "off", "") else self.world.color(color)
        self.glow_color = None if c == "#000000" else c
        for node, main in self.parts:
            if main:
                self.send(node, emissive=c)
        return self.native

    # ---- a person's look: the kit's person, the player's figure (player:shirt...) and a ragdoll (Ragdoll.restyle)
    def shirt(self, color):
        return self.dress("shirt", shirt=self.world.color(color))

    def pants(self, color):
        return self.dress("pants", pants=self.world.color(color))

    def skin(self, color):
        name = self.rt.text(color).strip().lower()
        return self.dress("skin", skin=SKIN_COLORS.get(name) or self.world.color(color))

    def shoes(self, color):
        return self.dress("shoes", shoes=self.world.color(color))

    def hair(self, a, b=MISSING):
        """person:hair("curly"), person:hair("brown") or both, either way round: a style and a colour."""
        change = {}
        for v in (a, b):
            if v is MISSING:
                continue
            word = self.rt.text(v).strip().lower()
            style = HAIR_WORDS.get(word, word)
            if style in HAIR_STYLES and "style" not in change:
                change["style"] = style
            elif "hair" not in change:
                change["hair"] = HAIR_COLORS.get(word) or self.world.color(v)
            else:
                raise self.rt.error(f"{self.kind}:hair takes a style ({', '.join(HAIR_STYLES)}) and a colour, like "
                                    f"{self.kind}:hair(\"curly\", \"brown\").")
        return self.dress("hair", **change)

    def sleeves(self, how):
        word = self.rt.text(how).strip().lower()
        word = SLEEVE_WORDS.get(word, word)
        if word not in SLEEVES:
            raise self.rt.error(f"Sleeves can be \"long\" or \"short\" (rolled up to the elbow), not \"{word}\".")
        return self.dress("sleeves", sleeves=word)

    def dress(self, what, **change):
        if self.look is None:
            raise self.rt.error(f"Only people have clothes and hair: :{what} works on a person (world:spawn(\"person\", "
                                f"x, y, z)), a ragdoll or the player in third person, not a {self.kind}.")
        if any(self.look.get(k) != v for k, v in change.items()):
            self.look.update(change)
            self.restyle()
        return self.native

    def restyle(self):
        """Dressed again in its look: its old parts go and new ones come (anim.js looks at a model's parts again)."""
        w = self.world
        if not self.alive:  # (removed: the page has let its parts go)
            return
        for node, _ in self.parts:
            w.view.remove(node)
            w.by_node.pop(int(node), None)
        self.parts = []
        for type_, p, main in dressed(self.look):
            if main and self.glow_color:
                p = {**p, "emissive": self.glow_color}
            node = w.view.obj(self.node, type_, **p, **({} if self.pickable else {"pick": False}))
            w.by_node[int(node)] = self
            self.parts.append((node, main))

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
        for node in [self.node] + [n for n, _ in self.parts] + ([self.writing] if self.writing is not None else []):
            w.by_node.pop(int(node), None)
        if w.phys is not None:
            w.phys.dirty.discard(self)  # its body went with its object
            if self.phys_sent is not None:
                w.phys.forget(self)
            if w.driving is self:  # the player gets out where the car was
                self.drive(False)

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
        if self.kind == "sign":  # a sign's words are written on its board (both sides), not over it
            if not self.alive:
                return self.native
            if self.writing is None:
                self.writing = w.view.obj(self.node, "writing", text=t, w=1.02, h=0.44, d=0.066, y=1.25,
                                          color="#3a2414")
                w.by_node[int(self.writing)] = self
            else:
                self.send(self.writing, text=t)
            return self.native
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

    # ---- talking (see Interaction)
    def say(self, text, seconds=4):
        self.world.interaction().say(self, text, seconds)
        return self.native

    def on_talk(self, fn):
        self.world.interaction().on_talk(self, fn)
        return self.native
    # ---- moving along a path by itself (Route, with the level pieces)
    def path(self, spots=MISSING, speed=MISSING, how=MISSING):
        return self.world.level().set_route(self, spots, speed, how)


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
        ("can_grab", "can_grab"), ("holding", "holding"), ("weight", "weight"), ("in_car", "in_car"),
        ("shirt", "shirt"), ("pants", "pants"), ("skin", "skin"), ("hair", "hair"), ("shoes", "shoes"),
        ("sleeves", "sleeves"),
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
        self.phys_ground = -1.0  # the game's time when physics last said it stands on something physics moves
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
        self.kg = PLAYER_KG
        if mode == "third person":
            look = person_look("#3574f0", "#f1c9a5", "#5a3a22", "#2f3e5c", "short", "long", "#3a2a22")
            self.body = Thing(world, "player", 0, 0, 0, (0.6, self.TALL, 0.6), dressed(look), pick=False)
            self.body.look = look
            self.body.solid_ = False
            world.things.pop(self.body, None)
            if world.driving is not None:  # it starts in a car (car:drive() came first)
                self.body.hide()
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
        elif world.driving is not None and world.crosshair is not None:  # it starts in a car: back when it gets out
            world.crosshair.hide()
            world.car_hid = [world.crosshair]
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
        if self.grounded():
            self.vy = self.jump_v
            self.on_ground = False
        return self.native

    def grounded(self):
        """On the ground, for a jump: on the land or something solid, or (physics said so a moment ago) on a thing
        physics moves, which Python's walking doesn't see under it."""
        return self.on_ground or (self.vy <= 0 and self.world.clock - self.phys_ground < 0.15)

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
            # In the right hand as it hangs: the page (anim.js) moves it with the hand, gripped upright in the fist.
            self.held = Thing(w, name, SHOULDER[0], 0.765, 0, (0.3, 0.8, 0.1), held_parts(name), parent=self.body.node, pick=False)
        self.held.solid_ = False
        self.held.push_rotation()
        if SCENE is not None: SCENE.held_made = list(SCENE.interp.lines)
        return self.held.native

    def looking_at(self, reach=None):
        return self.world.looking_at(reach)

    # ---- grabbing (see Interaction)
    def can_grab(self, on=True):
        self.world.interaction().can_grab(self.rt.truthy(on))
        return self.native

    def holding(self):
        it = self.world.interact
        return it.held.native if it is not None and it.held is not None else None

    def in_car(self):
        return self.world.driving is not None

    def weight(self, kg=MISSING):
        """How heavy the player is (70 kg): the heavier, the harder it shoves physics things it walks into."""
        if kg is MISSING:
            return tidy(self.kg)
        m = self.rt.number(kg, ":weight")
        if m <= 0:
            raise self.rt.error("player:weight needs a number above 0, like player:weight(70).")
        self.kg = m
        self.world.physics_on().send("player_weight", m)
        return self.native

    # ---- how the player looks in third person: its figure's (Thing.shirt...)
    def dress_body(self, what, *args):
        if self.body is None:
            raise self.rt.error(f"player:{what} changes how the player looks, and in first person nobody sees it. "
                                "Make the player with world:player(\"third person\") to see it.")
        getattr(self.body, what)(*args)
        return self.native

    def shirt(self, color):
        return self.dress_body("shirt", color)

    def pants(self, color):
        return self.dress_body("pants", color)

    def skin(self, color):
        return self.dress_body("skin", color)

    def hair(self, a, b=MISSING):
        return self.dress_body("hair", a, b)

    def shoes(self, color):
        return self.dress_body("shoes", color)

    def sleeves(self, how):
        return self.dress_body("sleeves", how)

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
        if self.body is not None and self.world.driving is None:  # (in a car, it shows when it gets out)
            self.body.show()
        return self.native

    # ---- walking, every frame
    def solids(self):
        """What stops the player here: solid things, except what physics moves (the page's physics stops the player
        at those, and pushes them). A kinematic thing is here: the program moves it, so a lift carries the player.
        So is a door that's shut (a locked one stays shut), unless it shut on the player: then it can walk out."""
        out = [t for t in self.world.things if isinstance(t, Thing) and t.alive and t.solid_ and not t.hidden
               and t.phys_kind != "dynamic"]
        it = self.world.interact
        if it is not None:
            out += [d.panel for d in it.doors if d.shut() and not boxes_touch(self.box3(), d.panel.box3())]
        return out

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
            w.view.mouse_delta()  # and the mouse's moves go (kept, they'd spin the view on getting out)
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
        if "space" in w.just and self.grounded():
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
    them back. A thing moved by the program (move_to, glide...) goes on from there in the page, and the reports from
    before the page had that move (each says the last batch it had) leave the thing be.

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
        # Things removed in the last frames, by their object's id: the page reports a hit a few steps after it
        # starts, so a bullet removed as it hits is still what hit the target. {id: (thing, frame it went)}
        self.gone = {}
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
        if self.gone:
            self.gone = {i: g for i, g in self.gone.items() if self.game.frames - g[1] < 30}
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
            if self.game.driving is not None:  # in a car (from the start): its capsule stays out of the way
                self.send("player_off")
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
        hasn't made yet. Standing on a physics thing, it's on the ground. Not when the program has just moved the
        player (move_to, getting out of a car): that goes to the page next, and the capsule's spot is the old one."""
        done, x, y, z, grounded = rep
        if p.teleported or done < self.first_seq or self.sent is None or self.game.driving is not None:
            return
        while self.moves and self.moves[0][0] <= done:
            self.moves.popleft()
        for _, d in self.moves:
            x, y, z = x + d[0], y + d[1], z + d[2]
        p.x, p.y, p.z = x, y, z
        self.sent = (x, y, z)
        if grounded and p.vy <= 0:
            p.vy, p.on_ground, p.phys_ground = 0.0, True, self.game.clock

    # ---- what the page says
    def who(self, i):
        """The thing a body in a report belongs to (0: the player; -1: a wall)."""
        g = self.game
        if i == 0:
            return getattr(g, "the_player", None)
        land = getattr(g, "land", None)
        if land is not None and i == int(land.node):
            return land
        t = g.by_node.get(i)
        return t if t is not None or i not in self.gone else self.gone[i][0]

    def forget(self, t):
        """t was removed: for a few frames more, a hit it was in still names it."""
        self.gone[int(t.node)] = (t, self.game.frames)

    def report(self, e):
        g = self.game
        seen = e.get("seq")  # the last batch the page had applied: a thing moved in a later one isn't there yet
        for b in e.get("b") or ():
            t = g.by_node.get(b[0])
            if t is not None and t.alive and hasattr(t, "from_physics") and (seen is None or seen >= t.moved_in):
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
    Space brakes) and the camera, which follows it from behind. car:speed is how fast it goes, in km/h.

    In a world with a player, the player gets in by walking up to it and pressing F (Interaction says "F: Get in"),
    and F again gets out, beside the driver's door; car:drive() starts the game with the player in it. car:on_enter
    and car:on_exit run when the player gets in and out, and car:driven() says whether it's being driven."""
    KIND = "car"
    NAMES = [(n, "car_speed" if n == "speed" else a) for n, a in Thing.NAMES if n not in LOOK_METHODS] + [
        ("drive", "drive"), ("engine", "engine"), ("flip", "flip"), ("on_enter", "on_enter"), ("on_exit", "on_exit"),
        ("driven", "is_driven")]
    EXAMPLE = "car"
    MASS = 1200
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
        self.enter_fns, self.exit_fns = [], []
        world.physics_on().sync(self)
        world.interaction().cars.append(self)  # the player gets in with F

    def can_have_physics(self, kind):
        if kind != "dynamic":
            raise self.rt.error("A car always uses physics (it drives on its wheels).")

    def phys_spec(self):
        if not self.alive or self.world.phys is None:
            return None
        return {"kind": "dynamic", "shape": "car", "size": self.HALF, "cy": self.CY, "wheel_r": self.WHEEL_R,
                "rest": self.REST, "mass": self.weight_now(), "bounce": self.bounce_, "friction": self.friction_,
                "hits": bool(self.hit_fns), "wheels": [[int(n), *xyz] for n, xyz in zip(self.wheel_nodes, self.WHEELS)]}

    def default_weight(self):
        return self.MASS

    def from_physics(self, b):
        """Like an object's, and the car's speed (km/h, forward)."""
        Thing.from_physics(self, b)
        self.kmh = b[11] if len(b) > 11 else 0.0

    def car_speed(self):
        return tidy(self.kmh)

    def drive(self, on=True):
        """The player gets in (or the keys drive it, with no player) or out. car:on_enter and car:on_exit run when the
        player gets in and out, however it happens (F, this, the car being removed)."""
        w = self.world
        ph = w.physics_on()
        p = w.the_player
        fire = None
        if self.rt.truthy(on):
            if w.driving is self:
                return self.native
            if w.driving is not None:
                w.driving.drive(False)
            w.driving = self
            w.drove_frame = w.frames  # an F the program used for this isn't Interaction's F too
            if w.cam_mode != "player":
                w.cam_mode = "drive"
            w.camera_dirty = False
            ph.send("chase", int(self.node))
            if p is not None:  # in the car: its figure and its capsule aren't left standing where it got in
                if p.body is not None:
                    p.body.hide()
                # In first person, what it holds and the crosshair go too (they're on the camera, behind the car).
                w.car_hid = [s for s in (p.held if p.mode == "first person" else None, w.crosshair)
                             if s is not None and not s.hidden]
                for s in w.car_hid:
                    s.hide()
                ph.send("player_off")
                fire = self.enter_fns
        elif w.driving is self:
            w.driving = None
            w.drove_frame = w.frames
            self.controls = (0, 0, 1)  # parked: the brake stays on, so it doesn't roll away down a hill
            ph.send("drive", int(self.node), 0, 0, 1)
            ph.send("chase", None)
            if w.cam_mode == "drive":
                w.cam_mode = "fixed"
                w.push_camera()  # the camera stays where it was, behind the car
            if p is not None:  # out of the car, beside its door
                p.x, p.y, p.z = self.exit_spot(p)
                p.vy = 0.0
                p.heading = self.heading % 360  # facing the way the car faces
                p.teleported = True  # its capsule comes back there (player_to)
                if p.body is not None and not p.hidden:
                    p.body.show()
                for s in getattr(w, "car_hid", None) or ():
                    if getattr(s, "alive", True) and not p.hidden:
                        s.show()
                w.car_hid = []
                p.place_camera(1)
                fire = self.exit_fns
        if getattr(w, "hud_js", None) is not None:
            w.hud_js.player()  # the minimap and the arrow measure from the car while it's driven
        for fn in list(fire or ()):
            w.fire(fn, self.native)
        return self.native

    def exit_spot(self, p):
        """Where the player gets out: beside the driver's door (its left), or the other door, behind it or in front of
        it when something solid is in the way, standing on whatever is there."""
        solids = p.solids()
        h = math.radians(self.heading)
        rx, rz = math.cos(h), math.sin(h)  # the car's right, along the ground
        fx, fz = math.sin(h), -math.cos(h)  # its front
        spots = [(-rx * 2.2, -rz * 2.2), (rx * 2.2, rz * 2.2), (-fx * 3.4, -fz * 3.4), (fx * 3.4, fz * 3.4)]
        for dx, dz in spots:
            x, z = self.x + dx, self.z + dz
            y = max(self.world.ground_y(x, z), p.floor_at(x, z, self.y + 0.4, solids))
            if not p.blocked(x, z, y, solids):
                return x, y, z
        x, z = self.x + spots[0][0], self.z + spots[0][1]
        return x, max(self.world.ground_y(x, z), self.y), z

    def get_in(self):
        """The player gets in (F next to it), with the sound of its door."""
        w = self.world
        if w.driving is self or not self.alive:
            return
        w.view.call(0, "tones", INTERACT_SOUNDS["car door"], 0.25)
        self.drive(True)

    def get_out(self):
        w = self.world
        if w.driving is not self:
            return
        w.view.call(0, "tones", INTERACT_SOUNDS["car door"], 0.25)
        self.drive(False)

    def on_enter(self, fn):
        self.enter_fns.append(self.world.lib.check_fn(fn, ":on_enter"))
        return self.native

    def on_exit(self, fn):
        self.exit_fns.append(self.world.lib.check_fn(fn, ":on_exit"))
        return self.native

    def is_driven(self):
        return self.world.driving is self

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
# middle when it stands (feet at 0), mass (kg), and which part of a person (person_parts) it's dressed as. They're a
# little slimmer than the person they look like, so parts that aren't joined don't touch as it stands. And its
# joints: the two parts, where they meet (the person's own joints), "ball" (turns any way) or "hinge" (bends one way,
# about x: forward is more), and how far a hinge bends.
_SX, _SY = SHOULDER
_HX, _HY = HIP
_BEND = WAIST + 0.025  # where its body bends at the waist: the chest's box starts a little above it, so bending
#                        doesn't push the chest into the tops of its legs
RAGDOLL = (
    ("head", "ball", 0.165, (0, HEAD[0], 0), 1.0, "head"),
    ("chest", "box", (0.17, (_SY - _BEND - 0.05) / 2, 0.125), (0, (_SY + _BEND + 0.05) / 2, 0), 3.0, "torso"),
    ("hips", "box", (0.16, 0.1, 0.115), (0, _BEND - 0.06, 0), 2.0, "body"),
    ("left arm", "capsule", ((_SY - ELBOW) / 2, 0.07), (-_SX, (_SY + ELBOW) / 2, 0), 0.6, "arm_l"),
    ("right arm", "capsule", ((_SY - ELBOW) / 2, 0.07), (_SX, (_SY + ELBOW) / 2, 0), 0.6, "arm_r"),
    ("left hand", "capsule", (0.13, 0.065), (-_SX, ELBOW - 0.1, 0), 0.4, "forearm_l"),
    ("right hand", "capsule", (0.13, 0.065), (_SX, ELBOW - 0.1, 0), 0.4, "forearm_r"),
    ("left leg", "capsule", ((_HY - KNEE) / 2, 0.08), (-_HX, (_HY + KNEE) / 2, 0), 1.2, "leg_l"),
    ("right leg", "capsule", ((_HY - KNEE) / 2, 0.08), (_HX, (_HY + KNEE) / 2, 0), 1.2, "leg_r"),
    ("left foot", "capsule", ((KNEE - 0.084) / 2, 0.08), (-_HX, (KNEE + 0.084) / 2, 0), 0.8, "shin_l"),
    ("right foot", "capsule", ((KNEE - 0.084) / 2, 0.08), (_HX, (KNEE + 0.084) / 2, 0), 0.8, "shin_r"),
)
RAGDOLL_JOINTS = (
    ("chest", "head", (0, NECK, 0), "ball", None),
    ("chest", "hips", (0, _BEND, 0), "hinge", (-0.8, 0.3)),
    ("chest", "left arm", (-_SX, _SY, 0), "ball", None),
    ("chest", "right arm", (_SX, _SY, 0), "ball", None),
    ("left arm", "left hand", (-_SX, ELBOW, 0), "hinge", (0, 2.0)),
    ("right arm", "right hand", (_SX, ELBOW, 0), "hinge", (0, 2.0)),
    ("hips", "left leg", (-_HX, _HY, 0), "hinge", (-0.5, 1.2)),
    ("hips", "right leg", (_HX, _HY, 0), "hinge", (-0.5, 1.2)),
    ("left leg", "left foot", (-_HX, KNEE, 0), "hinge", (-2.0, 0)),
    ("right leg", "right foot", (_HX, KNEE, 0), "hinge", (-2.0, 0)),
)
RAGDOLL_MASS = sum(p[4] for p in RAGDOLL)  # its parts' own masses, which are shared out like this
RAGDOLL_KG = 70  # how heavy it is, unless the program says (dummy:weight)


class Ragdoll(Thing):
    """world:ragdoll: a person made of parts held together by joints (a ball for the head, boxes for the chest and
    hips, capsules for the arms and legs), dressed like the kit's person (in the shirt colour it's given, with hair
    and a face). Made standing on the ground, it stands still until something hits it or it's pushed, then flops
    over; made in the air, it falls. Its x and z are its chest's, its y its lowest part's; a push goes to its chest."""
    KIND = "ragdoll"
    EXAMPLE = "dummy"

    def __init__(self, world, x, y, z, color):
        super().__init__(world, "ragdoll", x, y, z, (0.6, 1.7, 0.3),
                         [("group", {"x": at[0], "y": at[1], "z": at[2]}, False) for _, _, _, at, _, _ in RAGDOLL])
        self.look = person_look(world.color(color))
        self.restyle()
        self.phys_kind = "dynamic"
        self.standing = self.y - self.ground() < 0.05  # on the ground: it stands until something knocks it over
        world.physics_on().sync(self)

    def can_have_physics(self, kind):
        if kind != "dynamic":
            raise self.rt.error("A ragdoll always uses physics (that's what makes it flop).")

    def default_weight(self):
        return RAGDOLL_KG * self.k[0] * self.k[1] * self.k[2]

    def restyle(self):
        """Dressed in its look: each physics part is a group where its body is (physics moves it), holding the
        person's parts for that part of the body, where they are on the person. Dressed again, its old clothes go."""
        w = self.world
        if not self.alive:
            return
        groups = self.parts[:len(RAGDOLL)]
        for node, _ in self.parts[len(RAGDOLL):]:
            w.view.remove(node)
            w.by_node.pop(int(node), None)
        self.parts = list(groups)
        by_role = {}
        for type_, p, main in person_parts(**self.look):
            by_role.setdefault(p["anim"][1], []).append((type_, {k: v for k, v in p.items() if k != "anim"}, main))
        for (node, _), (_, _, _, at, _, role) in zip(groups, RAGDOLL):
            for type_, p, main in by_role[role]:
                if main and self.glow_color:
                    p = {**p, "emissive": self.glow_color}
                p = {**p, "x": p.get("x", 0) - at[0], "y": p.get("y", 0) - at[1], "z": p.get("z", 0) - at[2], "shadow": True}
                child = w.view.obj(node, type_, **p)
                w.by_node[int(child)] = self
                self.parts.append((child, main))

    def phys_spec(self):
        if not self.alive or self.world.phys is None:
            return None
        names = [p[0] for p in RAGDOLL]
        scale = self.weight_now() / RAGDOLL_MASS
        return {"kind": "dynamic", "shape": "ragdoll", "main": names.index("chest"), "bounce": self.bounce_,
                "friction": self.friction_, "hits": bool(self.hit_fns), "stand": self.standing,
                "parts": [[int(node), shape, size, list(at), round(mass * scale, 4)]
                          for (node, _), (_, shape, size, at, mass, _) in zip(self.parts, RAGDOLL)],
                "joints": [[names.index(a), names.index(b), list(at), kind, list(lim) if lim else None]
                           for a, b, at, kind, lim in RAGDOLL_JOINTS]}


# ---------------------------------------------------------------- talking, grabbing, doors and keys (3D)

TALK_REACH = 3.0  # how near the player has to be to talk to someone (npc:on_talk) or to grab something
DOOR_REACH = 2.5  # how near a door has to be for E to open or close it
CAR_REACH = 1.8   # how near a car's side the player has to be for F to get in
HOLD_AT = 2.2     # how far in front of the player's eyes a held thing floats
THROW = 13.0      # how fast a thrown thing flies off (metres a second)
# Little sounds for the page's synth (like SOUNDS): a door swinging open, banging shut, rattling when it's locked, a
# thing picked up and thrown.
INTERACT_SOUNDS = {
    "open": [[300, 0, 0.22, "triangle", 0.45, 150], [700, 0, 0.12, "noise", 0.18, 200]],
    "shut": [[120, 0, 0.14, "sine", 1, 55], [900, 0, 0.06, "noise", 0.5, 150]],
    "locked": [[220, 0, 0.06, "square", 0.45], [180, 0.08, 0.07, "square", 0.45]],
    "grab": [[440, 0, 0.07, "sine", 0.7, 760]],
    "throw": [[1100, 0, 0.2, "noise", 0.55, 250]],
    "car door": [[160, 0, 0.09, "square", 0.5, 90], [700, 0.02, 0.05, "noise", 0.35, 200]],
}


def name_of(t):
    """What a message calls a thing: its label ("Gold Key"), or what it is ("key")."""
    return t.label_text.strip() or t.kind


def door_local(heading, dx, dz):
    """A world offset in a door's own space (x along the door, z through it), for a door facing `heading`."""
    h = math.radians(heading)
    return dx * math.cos(h) + dz * math.sin(h), -dx * math.sin(h) + dz * math.cos(h)


def door_world(heading, lx, lz):
    """A door's own offset as a world one (door_local the other way)."""
    h = math.radians(heading)
    return lx * math.cos(h) - lz * math.sin(h), lx * math.sin(h) + lz * math.cos(h)


class Interaction:
    """A world's talking, grabbing, doors and keys: made by the first npc:say, npc:on_talk, world:door or
    player:can_grab, and run every frame by World3D.update.

    E does the first of these that it can: talk to the nearest one with an on_talk within 3 m, open or close the
    nearest door within 2.5 m, or grab the physics thing the player is looking at within 3 m (with player:can_grab),
    unless it weighs more than GRAB_KG. F gets into the nearest car within 1.8 m of its side, and gets out again.
    A hint at the bottom says what E and F will do ("E: Talk", "F: Get in"). A held thing floats in front of the
    player (its speed is set toward that spot every frame, so it still bumps into things), a click throws it (a heavy
    thing not as far) and E drops it. Walking into a key
    (the kit's "key", or anything a door needs) picks it up, and walking into a door opens it, away from the player.
    Speech bubbles are drawn by the page (tuff_view_web/interact.js); this keeps them over whoever's talking."""

    def __init__(self, world):
        self.world = world
        self.grab_on = False
        self.held = None
        self.talkers = {}  # thing -> its on_talk functions
        self.doors = []
        self.cars = []     # cars the player can get into with F
        self.out_hint_until = None  # in a car: "F: Get out" shows for a few seconds after getting in
        self.keys = {}     # things the player picked up (a dict used as an ordered set)
        self.wanted = {}   # things a door needs: walking into them picks them up, like a key
        self.bubbles = {}  # thing -> [its bubble's node, when it goes (the game's clock) or None, its words, where it is]
        self.hint = self.hint_bg = self.note = self.note_bg = None
        self.hint_text = self.note_text = None
        self.note_until = 0.0

    # ---- what the program asks for
    def say(self, t, text, seconds):
        w = self.world
        words = w.rt.text(text)
        secs = w.num(seconds, ":say")
        if secs < 0:
            raise w.rt.error(":say needs how many seconds the bubble shows (0 keeps it), like npc:say(\"Hi!\", 3).")
        if not words.strip():
            self.unsay(t)
            return
        b = self.bubbles.get(t)
        if b is None:
            b = self.bubbles[t] = [w.view.obj(w.scene, "group", pick=False), None, "", None]
        b[1] = w.clock + secs if secs > 0 else None
        b[2] = words
        b[3] = None  # placed again below
        w.view.js(f"window.tgInteract && window.tgInteract.say(tv, {int(b[0])}, {json.dumps(words)})")
        self.follow(t, b)

    def unsay(self, t):
        b = self.bubbles.pop(t, None)
        if b is not None and not self.world.closed:
            self.world.view.remove(b[0])

    def on_talk(self, t, fn):
        self.talkers.setdefault(t, []).append(self.world.lib.check_fn(fn, ":on_talk"))

    def can_grab(self, on):
        self.grab_on = on
        if on:
            self.world.physics_on()  # what it grabs are physics things
        elif self.held is not None:
            self.drop()

    def is_locked(self, door):
        return door.locked_ or (door.need is not None and door.need not in self.keys)

    # ---- every frame
    def update(self, dt):
        w = self.world
        for t, b in list(self.bubbles.items()):
            if not t.alive or (b[1] is not None and w.clock >= b[1]):
                self.unsay(t)
            else:
                self.follow(t, b)
        if self.note_text is not None and w.clock >= self.note_until:
            self.show_note(None)
        p = w.the_player
        if p is None or w.closed:
            self.show_hint(None)
            return
        if w.is_paused:
            return
        mine = not w.input_paused
        # F gets in and out of cars, unless the program uses F itself (world:on_key("f", ...)), or got in or out
        # with car:drive this frame.
        f = mine and "f" in w.just and getattr(w, "drove_frame", -1) != w.frames and not any(k == "f" for k, _ in w.key_fns)
        if w.driving is not None:  # in a car: F gets out
            if self.out_hint_until is None:
                self.out_hint_until = w.clock + 4
            if f and p.alive:
                w.driving.get_out()
                self.show_hint(None)
            else:
                self.show_hint("F: Get out" if w.clock < self.out_hint_until else None)
            return  # (the F that got out doesn't get straight back in)
        self.out_hint_until = None
        self.pick_up(p)
        for d in self.doors:
            if d.alive:
                d.near_player(p, self)
        if self.held is not None:
            self.carry(p)
        do, what = self.choice(p)
        car = self.car_near(p) if self.held is None else None
        # An E that hid a screen (a note the program closes with E) only hides it, and the click that locks the mouse
        # again (after Escape) isn't a throw.
        if f and car is not None and not ("e" in w.just and do is not None):
            car.get_in()
            self.show_hint("F: Get out")
            return
        if mine and "e" in w.just and do is not None:
            do(what)
            do, what = self.choice(p)
        elif mine and "mouse" in w.just and self.held is not None and not w.lock_click:
            self.throw(p)
            do, what = self.choice(p)
        hint = self.hint_for(do, what)
        if car is not None:
            hint = f"{hint}     F: Get in" if hint else "F: Get in"
        self.show_hint(hint)

    def follow(self, t, b):
        """A bubble stays over the one talking (and hides with it)."""
        at = (t.x, t.y + (0.9 if t.fallen else t.height()) + 0.3, t.z, t.hidden)
        if at != b[3]:
            b[3] = at
            self.world.view.set(b[0], x=at[0], y=at[1], z=at[2], visible=not t.hidden)

    def choice(self, p):
        """What E does now: (a function, what it's given), or (None, None)."""
        if self.held is not None:
            return self.drop, None
        near = [(math.hypot(t.x - p.x, t.z - p.z), i, t) for i, t in enumerate(self.talkers)
                if t.alive and not t.hidden and self.talkers[t]]
        near = [n for n in near if n[0] <= TALK_REACH]
        if near:
            return self.talk, min(near)[2]
        doors = [(math.hypot(d.x - p.x, d.z - p.z), i, d) for i, d in enumerate(self.doors) if d.alive and not d.hidden]
        doors = [n for n in doors if n[0] <= DOOR_REACH]
        if doors:
            return self.use_door, min(doors)[2]
        if self.grab_on:
            t = self.aimed_at(p)
            if t is not None:
                return (self.too_heavy, t) if t.weight_now() > GRAB_KG else (self.grab, t)
        return None, None

    def car_near(self, p):
        """The nearest car the player is close enough to get into (within CAR_REACH of its side), or None."""
        best = None
        for car in self.cars:
            if not car.alive or car.hidden or abs(p.y - car.y) > 2.5:
                continue
            lx, lz = door_local(car.heading, p.x - car.x, p.z - car.z)
            gap = math.hypot(max(abs(lx) - car.HALF[0], 0), max(abs(lz) - car.HALF[2], 0))
            if gap <= CAR_REACH and (best is None or gap < best[0]):
                best = (gap, car)
        return best[1] if best else None

    def hint_for(self, do, what):
        if do is None:
            return None
        if do == self.drop:
            return "E: Drop     Click: Throw"
        if do == self.talk:
            return "E: Talk"
        if do == self.use_door:
            return "E: Close" if what.want else "E: Open"
        if do == self.too_heavy:
            return "Too heavy to lift"
        return "E: Grab"

    # ---- talking
    def talk(self, t):
        for fn in list(self.talkers.get(t, ())):
            self.world.fire(fn)

    # ---- grabbing and throwing
    def eyes(self, p):
        """Where the player looks from and which way: (x, y, z) and a direction (first person: the way it looks;
        third person: level, the way it faces)."""
        pitch = math.radians(clamp(p.pitch, -60, 60)) if p.mode == "first person" else 0.0
        h = math.radians(p.heading)
        f = (math.sin(h) * math.cos(pitch), math.sin(pitch), -math.cos(h) * math.cos(pitch))
        return (p.x, p.y + (p.EYE if p.mode == "first person" else 1.1), p.z), f

    def middle(self, t):
        return t.x, t.y + t.height() / 2, t.z

    def aimed_at(self, p):
        """The physics thing nearest along the player's view within reach (a thing counts if the view passes within
        its own size of its middle)."""
        o, f = self.eyes(p)
        best = None
        for t in self.world.things:
            if not isinstance(t, Thing) or isinstance(t, Car) or not t.alive or t.hidden or not t.dynamic():
                continue
            m = self.middle(t)
            d = (m[0] - o[0], m[1] - o[1], m[2] - o[2])
            along = d[0] * f[0] + d[1] * f[1] + d[2] * f[2]
            r = max(0.3, max(t.dims[0] * t.k[0], t.dims[1] * t.k[1], t.dims[2] * t.k[2]) / 2)
            if along <= 0 or along > TALK_REACH + r:
                continue
            off = math.dist(d, (f[0] * along, f[1] * along, f[2] * along))
            if off <= r * 0.9 + (0.15 if p.mode == "first person" else 0.6) and (best is None or along < best[0]):
                best = (along, t)
        return best[1] if best else None

    def grab(self, t):
        self.held = t
        self.world.view.call(0, "tones", INTERACT_SOUNDS["grab"], 0.2)

    def too_heavy(self, t):
        self.world.view.call(0, "tones", INTERACT_SOUNDS["locked"], 0.2)

    def drop(self, _=None):
        self.held = None

    def carry(self, p):
        """The held thing goes toward its spot in front of the player: its speed is set that way every frame."""
        t = self.held
        if not t.alive or t.hidden or not t.dynamic():
            self.held = None
            return
        o, f = self.eyes(p)
        want = (o[0] + f[0] * HOLD_AT, max(o[1] + f[1] * HOLD_AT, p.y + 0.2 + t.height() / 2), o[2] + f[2] * HOLD_AT)
        gap = [a - b for a, b in zip(want, self.middle(t))]
        if math.hypot(*gap) > 4.5:  # stuck behind something, or left behind: it's let go
            self.held = None
            return
        v = [g * 12 for g in gap]
        speed = math.hypot(*v)
        if speed > 18:
            v = [c * 18 / speed for c in v]
        t.vel = v
        self.world.phys.send("velocity", int(t.node), *v)

    def throw(self, p):
        t, self.held = self.held, None
        _, f = self.eyes(p)
        k = clamp(math.sqrt(PUSH_KG / max(t.weight_now(), 0.01)), 0.35, 1.0)  # a heavy thing doesn't go as far
        v = [f[0] * THROW * k, f[1] * THROW * k + (2.0 if p.mode == "first person" else 3.5), f[2] * THROW * k]
        t.vel = v
        self.world.phys.send("velocity", int(t.node), *v)
        self.world.view.call(0, "tones", INTERACT_SOUNDS["throw"], 0.2)

    # ---- doors and keys
    def use_door(self, d):
        if d.want:
            d.swing_to(0)
        elif self.is_locked(d):
            self.locked(d)
        else:
            d.open_from(self.world.the_player, auto=True)

    def locked(self, d):
        need = f" You need the {name_of(d.need)}." if d.need is not None and d.need not in self.keys else ""
        self.show_note("Locked!" + need)
        self.world.view.call(0, "tones", INTERACT_SOUNDS["locked"], 0.25)

    def pick_up(self, p):
        """Walking into a key (or something a door needs) picks it up: it disappears."""
        box = p.box3()
        for t in list(self.world.things):
            if not isinstance(t, Thing) or t in self.keys or not t.alive or t.hidden:
                continue
            if (t.kind == "key" or t in self.wanted) and boxes_touch(box, t.box3()):
                self.keys[t] = None
                if self.held is t:
                    self.held = None
                t.hide()
                self.world.view.call(0, "tones", SOUNDS["coin"], 0.3)
                self.show_note(f"You got the {name_of(t)}!")

    # ---- the hint and the messages on the HUD
    def pill(self, words, y, size, fg, sprites):
        """A line of words on a dark rounded box in the middle of the window, at y: (box, text), made or changed."""
        hud = self.world.hud()
        w, h = len(words) * size * 0.56 + 30, size + 18
        box, text = sprites
        if box is None:
            box = hud.make("rect", self.world.W / 2, y, {"w": w, "h": h, "radius": h / 2, "color": "#11141a",
                                                         "alpha": 0.62, "z": 5e5 + 1}, own=False)
            text = hud.make("text", self.world.W / 2, y, {"text": words, "size": size, "bold": True, "color": fg,
                                                          "ax": 0.5, "ay": 0.5, "z": 5e5 + 2}, own=False)
        else:
            box.w = w
            box.send(w=w, visible=True)
            text.words = words
            text.send(text=words, visible=True)
            box.hidden = text.hidden = False
        return box, text

    def show_hint(self, words):
        if words == self.hint_text:
            return
        self.hint_text = words
        if words is None:
            for s in (self.hint_bg, self.hint):
                if s is not None:
                    s.hide()
            return
        self.hint_bg, self.hint = self.pill(words, self.world.H - 70, 17, "#ffffff", (self.hint_bg, self.hint))

    def show_note(self, words):
        self.note_text = words
        if words is None:
            for s in (self.note_bg, self.note):
                if s is not None:
                    s.hide()
            return
        self.note_until = self.world.clock + 1.8
        self.note_bg, self.note = self.pill(words, self.world.H / 2 + 64, 22, "#ffe9a8", (self.note_bg, self.note))

    def state(self):
        """For the autopilot's reports."""
        return {"grab": self.grab_on, "held": self.held.kind if self.held is not None else None,
                "bubbles": [b[2] for t, b in self.bubbles.items() if t.alive], "hint": self.hint_text,
                "driving": self.world.driving is not None,
                "note": self.note_text, "keys": [t.kind for t in self.keys],
                "doors": [{"angle": round(d.angle, 1), "open": bool(d.want), "locked": self.is_locked(d)}
                          for d in self.doors if d.alive]}


class Door(Thing):
    """world:door: a door in its frame. The door itself swings on a hinge at its left side (seen from the front, which
    faces -z like everything; door:turn turns the whole doorway). tgame swings it a little every frame and, since a
    door turns physics on, it's a kinematic body there: it pushes physics things out of its way. Shut, it stops the
    player like anything solid (Player.solids). The player walking into it, or pressing E near it, opens it away from
    the player, and it shuts again a few seconds after the player's gone through; door:open() opens it until
    door:close(). A locked one (door:lock(), or door:needs(key) until the player has picked up that key) stays shut
    and says "Locked!"."""
    KIND = "door"
    NAMES = [(n, a) for n, a in Thing.NAMES if n not in LOOK_METHODS] + [("open", "open"), ("close", "close"), ("needs", "needs"), ("lock", "lock"),
                           ("unlock", "unlock")]
    EXAMPLE = "door"
    WIDE, TALL, THICK = 1.0, 2.0, 0.08  # the door itself (its frame is a little bigger)
    SWING = 100  # how far it opens (degrees)
    STAYS = 3.0  # seconds it stays open after the player went through

    def __init__(self, world, x, y, z, color):
        c = world.color(color)
        frame = {"color": _shade(c, -0.3), "rough": 0.85}
        parts = [
            ("box", {"w": 0.14, "h": 2.14, "d": 0.2, "x": -0.58, "y": 1.07, **frame}, False),
            ("box", {"w": 0.14, "h": 2.14, "d": 0.2, "x": 0.58, "y": 1.07, **frame}, False),
            ("box", {"w": 1.3, "h": 0.14, "d": 0.22, "y": 2.1, **frame}, False),
            ("box", {"w": 1.02, "h": 0.03, "d": 0.24, "y": 0.015, "color": "#8f8a80", "rough": 0.95}, False),
        ]
        super().__init__(world, "door", x, y, z, (1.3, 2.17, 0.24), [(t, {"shadow": True, **p}, m) for t, p, m in parts])
        self.solid_ = False   # the doorway is open: the door itself is what's in the way
        self.angle = 0.0      # how far it has swung (degrees, one way or the other)
        self.want = 0.0       # where it's swinging to (0: shut)
        self.swinging = None  # [from, to, seconds so far, seconds it takes]
        self.locked_ = False
        self.need = None
        self.close_at = None  # opened by the player: when it may shut again (the game's clock)
        self.at_door = False  # the player is in the doorway (so a locked door says so once each time)
        ph = world.physics_on()
        wood = {"rough": 0.8}
        knob = {"color": "#d9b45a", "metal": 0.8, "rough": 0.3, "emissive": "#3a2a00"}
        W, T, D = self.WIDE, self.TALL, self.THICK
        panel = [("box", {"w": W, "h": T, "d": D, "y": T / 2, "color": c, **wood}, True)]
        for py in (0.5, 1.45):  # two sunk panels on each side
            for pz in (-D / 2 - 0.005, D / 2 + 0.005):
                panel.append(("box", {"w": W * 0.66, "h": 0.66, "d": 0.012, "y": py, "z": pz, "color": _shade(c, -0.16),
                                      **wood}, False))
        for pz in (-D / 2 - 0.035, D / 2 + 0.035):
            panel.append(("sphere", {"r": 0.045, "x": W / 2 - 0.12, "y": 1.0, "z": pz, "seg": 10, **knob}, False))
        self.panel = Thing(world, "door panel", x, y, z, (W, T, D), [(t, {"shadow": True, **p}, m) for t, p, m in panel])
        world.things.pop(self.panel, None)  # it's the door's: a program only sees the door
        for node in [self.panel.node] + [n for n, _ in self.panel.parts]:
            world.by_node[int(node)] = self  # clicking it, looking at it or hitting it is the door
        self.panel.phys_kind = "kinematic"
        ph.dirty.add(self.panel)
        world.interaction().doors.append(self)
        self.place_panel()

    def can_have_physics(self, kind):
        raise self.rt.error("A door swings on its hinge by itself: it doesn't need :physics.")

    def place_panel(self):
        """The door where its hinge and its swing put it."""
        p = getattr(self, "panel", None)
        if p is None:
            return
        hx, hz = door_world(self.heading, -self.WIDE / 2, 0)
        ox, oz = door_world(self.heading + self.angle, self.WIDE / 2, 0)
        p.x, p.y, p.z = self.x + hx + ox, self.y, self.z + hz + oz
        p.heading = (self.heading + self.angle) % 360
        p.push()
        p.push_rotation()

    def push(self):
        super().push()
        self.place_panel()

    def push_rotation(self):
        super().push_rotation()
        self.place_panel()

    def swing_to(self, angle):
        if angle == self.want:
            return
        if not angle:
            self.close_at = None
            self.world.view.call(0, "tones", INTERACT_SOUNDS["shut"], 0.25)
        elif not self.want:
            self.world.view.call(0, "tones", INTERACT_SOUNDS["open"], 0.25)
        self.want = angle
        self.swinging = [self.angle, angle, 0.0, 0.75 if angle else 0.9]
        self.busy()

    def open_from(self, who, auto=False):
        """Opens away from who (the player), or one way if there's nobody."""
        side = door_local(self.heading, who.x - self.x, who.z - self.z)[1] if who is not None else -1.0
        self.swing_to(-self.SWING if side > 0 else self.SWING)
        self.close_at = self.world.clock + self.STAYS if auto else None

    def shut(self):
        """Shut (or nearly): the player can't walk through it (Player.solids). One that isn't locked opens as the
        player comes up to it, before the player gets to it."""
        return self.alive and not self.hidden and abs(self.angle) < 15

    def near_player(self, p, it):
        """The player walking into it opens it (or hears it's locked); opened by the player, it shuts again once the
        player has been gone a few seconds."""
        lx, lz = door_local(self.heading, p.x - self.x, p.z - self.z)
        at = abs(lx) < self.WIDE / 2 + 0.25 and abs(lz) < 1.1
        if at and not self.want:
            if it.is_locked(self):
                if not self.at_door:
                    it.locked(self)
            else:
                self.open_from(p, auto=True)
        self.at_door = at
        if self.close_at is not None:
            if abs(lx) < self.WIDE + 0.4 and abs(lz) < 1.4:
                self.close_at = self.world.clock + self.STAYS  # not while the player's in the way
            elif self.world.clock >= self.close_at:
                self.swing_to(0)

    def busy(self):
        if self.swinging is not None:
            self.world.movers.add(self)
        else:
            super().busy()

    def tick(self, dt):
        s = self.swinging
        if s is not None:
            s[2] += dt
            t = min(1.0, s[2] / s[3])
            # Opening, it swings a little past and settles back; shutting, it slows into its frame.
            k = 1.0 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2 if s[1] else ease(t)
            self.angle = s[0] + (s[1] - s[0]) * k
            if t >= 1:
                self.angle, self.swinging = s[1], None
            self.place_panel()
        super().tick(dt)

    # ---- what a program can do with it
    def open(self):
        if not self.want:
            self.open_from(self.world.the_player)
        self.close_at = None
        return self.native

    def close(self):
        self.swing_to(0)
        return self.native

    def needs(self, key):
        t = thing_of(key)
        if not isinstance(t, Thing) or isinstance(t, Door):
            raise self.rt.error("door:needs needs the thing that opens it, like door:needs(key) after "
                                f"key = world:spawn(\"key\", 3, 0, 3). Not {self.rt.what(key)}.")
        it = self.world.interaction()
        self.need = t
        it.wanted[t] = None
        if self.want and t not in it.keys:
            self.swing_to(0)
        return self.native

    def lock(self):
        self.locked_ = True
        self.swing_to(0)
        return self.native

    def unlock(self):
        self.locked_ = False
        self.need = None
        return self.native

    # ---- the door itself goes with its frame
    def set_color(self, color):
        self.panel.set_color(color)
        return self.native

    def hide(self):
        super().hide()
        self.panel.hide()
        return self.native

    def show(self):
        super().show()
        self.panel.show()
        return self.native

    def remove(self):
        if self.alive:
            super().remove()
            self.panel.remove()


HINTS["object"].update({"talk": "on_talk", "on_interact": "on_talk", "interact": "on_talk", "on_speak": "on_talk",
                        "on_chat": "on_talk", "speak": "say", "chat": "say", "bubble": "say", "speech": "say",
                        "dialog": "say", "dialogue": "say", "tell": "say"})
HINTS["door"] = {**HINTS["object"], "requires": "needs", "require": "needs", "need": "needs", "key": "needs",
                 "set_key": "needs", "needs_key": "needs", "shut": "close", "slam": "close", "swing_open": "open"}
HINTS["player"].update({"grab": "can_grab", "pick_up": "can_grab", "pickup": "can_grab", "carry": "can_grab",
                        "lift": "can_grab", "can_pick_up": "can_grab", "held_item": "holding", "carrying": "holding",
                        "held_thing": "holding", "grabbed": "holding", "throw": "can_grab"})
HINTS["world"].update({"gate": "door", "doorway": "door", "add_door": "door", "make_door": "door"})
# ---------------------------------------------------------------- level pieces: jump pads, boost pads, moving platforms

# How thing:path goes along its spots: there and back again ("ping-pong", what it does by itself) or round and round
# ("loop"), and other words people use for them.
PATH_MODES = ("ping-pong", "loop")
PATH_WORDS = {"pingpong": "ping-pong", "ping pong": "ping-pong", "back and forth": "ping-pong", "there and back": "ping-pong",
              "back": "ping-pong", "bounce": "ping-pong", "round": "loop", "around": "loop", "round and round": "loop",
              "circle": "loop", "cycle": "loop", "repeat": "loop", "loops": "loop", "looping": "loop"}
# A pad's whoosh when it launches something: a rush of air (noise opening up) over a tone that rises.
WHOOSH = {"jump": [[500, 0, 0.42, "noise", 1, 4200], [190, 0, 0.32, "sine", 0.55, 760]],
          "boost": [[900, 0, 0.5, "noise", 1, 6500], [240, 0, 0.38, "sawtooth", 0.22, 980]]}
# A pad's colours: its dark rim, its glow, and the lighter trim (a jump pad's ring, a boost pad's arrows).
PAD_LOOK = {"jump": ("#2b2f36", "#2ee6a6", "#b6ffe4"), "boost": ("#2b2f36", "#ff8a1f", "#ffe066")}
PAD_POWER = {"jump": 15, "boost": 20}
# Names people guess for the level pieces, and the tgame name.
HINTS["world"].update({"trampoline": "jump_pad", "jumppad": "jump_pad", "bounce_pad": "jump_pad", "launch_pad": "jump_pad",
                       "launcher": "jump_pad", "spring": "jump_pad", "springboard": "jump_pad", "booster": "boost_pad",
                       "boostpad": "boost_pad", "speed_pad": "boost_pad", "speed_boost": "boost_pad", "dash_pad": "boost_pad",
                       "boost": "boost_pad", "accelerator": "boost_pad", "speed_strip": "boost_pad"})
HINTS["object"].update({"waypoints": "path", "route": "path", "patrol": "path", "follow_path": "path", "move_along": "path",
                        "set_path": "path", "move_path": "path", "ping_pong": "path", "oscillate": "path",
                        "move_between": "path"})


def path_mode(text):
    """"ping-pong" or "loop" for what a program wrote ("Loop", "ping pong", "round and round"...), or None."""
    t = re.sub(r"[\s_]+", " ", str(text).strip().lower())
    t = PATH_WORDS.get(t, t)
    return t if t in PATH_MODES else None


def path_problem(name):
    return (f"A path can go \"ping-pong\" (there and back again) or \"loop\" (round and round, back to the first spot), "
            f"not \"{name}\".{did_you_mean(str(name).strip().lower(), PATH_MODES)}")


class Level:
    """A 3D world's level pieces, made by the first one: jump pads and boost pads (Pad), and things that move along a
    path by themselves (Route, thing:path), like a lift. Every frame, before the player walks (World3D.update), the
    things on paths move, carrying the player that stands on them and pushing it out of their way, then the pads launch
    whoever is on them, then a boost carries the player on until it fades. All of it holds still while the game is
    paused, and none of it needs physics. With physics on, a thing on a path is a kinematic body in the page, so the
    physics things on it ride along too, and a pad launches physics things as well as the player."""

    def __init__(self, world):
        self.world, self.rt = world, world.rt
        self.pads = []     # jump pads and boost pads, oldest first
        self.routes = {}   # thing -> its Route, in the order they started
        self.boost = None  # the player's speed from a boost pad ([x, z], metres a second) until it fades

    # ---- making them
    def make_pad(self, how, args):
        w = self.world
        what = f"{how}_pad"
        x, y, z, (power,) = w.where(args, (PAD_POWER[how],), what)
        p = self.rt.number(power, f":{what}")
        if p <= 0:
            raise self.rt.error(f":{what} needs a power above 0 (how fast it launches things, in metres a second), like "
                                f"world:{what}(0, 0, 5, {PAD_POWER[how]}).")
        pad = Pad(w, how, x, w.above(x, y, z), z, p)
        self.pads.append(pad)
        return pad.native

    def set_route(self, t, spots, speed, how):
        """thing:path(spots, speed, how): it moves along the spots by itself. thing:path() stops it where it is."""
        rt, n = self.rt, t.kind
        if spots is MISSING:
            self.stop(t)
            return t.native
        if not t.on_land:
            raise rt.error("Only things in the world can move along a path, not something the player holds.")
        if t.phys_kind == "dynamic" and n in ("car", "ragdoll"):  # always physics: it can't be turned off
            raise rt.error(f"A {n} always has physics (it falls and gets pushed), so it can't move along a path. Move it "
                           f"with {n}:push" + (", or drive it with car:drive()." if n == "car" else "."))
        if t.phys_kind == "dynamic":
            raise rt.error(f"{n}:path moves things that stay up by themselves, but this {n} has physics (it falls and "
                           f"gets pushed). Turn that off first with {n}:physics(\"off\"), or move it with {n}:push.")
        raw = rt.plain(spots)
        example = f"{n}:path([[0, 2, 0], [10, 2, 0]], 3)"
        if not isinstance(raw, list) or not raw:
            raise rt.error(f"{n}:path needs a list of spots to go to, like {example}.")
        if all(not isinstance(rt.plain(s), list) for s in raw) and len(raw) in (2, 3):
            raise rt.error(f"{n}:path needs a list of spots, each one [x, y, z], so one spot is [[x, y, z]]. Like {example}.")
        w = self.world
        at = []
        for i, s in enumerate(raw, 1):
            s = rt.plain(s)
            if isinstance(s, list) and len(s) == 2:  # [x, z]: on the land
                s = [s[0], 0, s[1]]
            if not isinstance(s, list) or len(s) != 3:
                got = f"has {len(s)} numbers" if isinstance(s, list) else f"is {rt.what(s)}"
                raise rt.error(f"Each spot on a path is [x, y, z] (y is the height above the ground), like [10, 2, 0]. "
                               f"Spot {i} {got}.")
            x, y, z = (rt.number(v, f"Spot {i} of {n}:path") for v in s)
            at.append((x, w.above(x, y, z), z))
        v = 3 if speed is MISSING else rt.number(speed, f"{n}:path's speed")
        if v <= 0:
            raise rt.error(f"{n}:path needs a speed above 0 (metres a second), like {example}.")
        loop = False
        if how is not MISSING:
            word = rt.text(how)
            mode = path_mode(word)
            if mode is None:
                raise rt.error(path_problem(word))
            loop = mode == "loop"
        if t.phys_kind == "kinematic":
            t.phys_kind = None  # it's kinematic for physics while it's on its path anyway; the player walks on it as on a solid thing
        t.route = Route(t, at, v, loop)
        self.routes.pop(t, None)
        self.routes[t] = t.route
        t.phys_changed()
        return t.native

    def stop(self, t):
        self.routes.pop(t, None)
        if getattr(t, "route", None) is not None:
            t.route = None
            if self.world.phys is not None:
                t.send(t.node, vel=[0, 0, 0], acc=[0, 0, 0, 0])
            t.phys_changed()  # a fixed body again, where it stopped

    # ---- every frame
    def frame(self, dt):
        if not dt:  # paused
            return
        w = self.world
        p = w.the_player if w.driving is None else None
        for t, route in list(self.routes.items()):
            if not t.alive or getattr(t, "route", None) is not route:
                self.routes.pop(t, None)
            else:
                self.move(t, route, dt, p)
        if self.pads:
            self.check_pads(dt, p)
        if p is not None and self.boost is not None:
            self.glide(p, dt)

    def move(self, t, route, dt, p):
        x0, y0, z0 = t.x, t.y, t.z
        solid = p is not None and t.solid_ and not t.hidden
        rides = solid and self.stands_on(p, t)
        (t.x, t.y, t.z), done = route.step(dt)
        t.push()
        if self.world.phys is not None:  # how fast it goes, so physics moves it smoothly between frames (physics.js's glide)
            t.send(t.node, vel=[tidy(v) for v in route.velocity()], acc=[tidy(a) for a in route.acceleration()] + [route.speed])
        if done:  # a path to one spot: it's there now
            self.stop(t)
        if not solid:
            return
        d = (t.x - x0, t.y - y0, t.z - z0)
        if rides:
            # On its top, where it is now. With physics on, the ride goes to the page with the player's walk, as one
            # move (the capsule doesn't bump into the platform: kinematic things are Python's), so riding, the player
            # still pushes the physics things it walks into.
            p.x, p.y, p.z = p.x + d[0], t.box3(body=True)[4], p.z + d[2]
        elif self.shove(p, t, d) and self.world.phys is not None:
            p.teleported = True  # pushed out of its way: the page's capsule goes there too, whatever's in the way

    def stands_on(self, p, t):
        """Is the player standing on t's top (feet on it, not jumping off)?"""
        b = t.box3(body=True)
        r = p.RADIUS * 0.8
        return (p.x + r > b[0] and p.x - r < b[3] and p.z + r > b[2] and p.z - r < b[5] and abs(p.y - b[4]) < 0.08
                and p.vy <= 0.5)

    def shove(self, p, t, d):
        """t moved into the player: if its top came up past the player's feet (no higher than a step), the player is
        on it now; if it came from the side, the player is pushed out of its way. True if the player moved."""
        b = t.box3(body=True)
        r = p.RADIUS
        if not (p.x + r > b[0] and p.x - r < b[3] and p.z + r > b[2] and p.z - r < b[5]):
            return False
        if p.y + p.TALL <= b[1] or p.y >= b[4]:  # over it or under it
            return False
        if b[4] - p.y <= 0.45 or (d[1] > 0 and b[1] <= p.y + 0.05):
            p.y, p.vy, p.on_ground = b[4], max(p.vy, 0.0), True
            return True
        if not (d[0] or d[2]):
            return False
        if d[0]:
            p.x = b[3] + r + 0.01 if d[0] > 0 else b[0] - r - 0.01
        if d[2]:
            p.z = b[5] + r + 0.01 if d[2] > 0 else b[2] - r - 0.01
        p.keep_inside()
        return True

    def check_pads(self, dt, p):
        w = self.world
        self.pads = [pad for pad in self.pads if pad.alive]
        things = None
        for pad in self.pads:
            for k in list(pad.cool):
                pad.cool[k] -= dt
                if pad.cool[k] <= 0:
                    del pad.cool[k]
            if pad.hidden:
                continue
            low, top = pad.y - 0.1, pad.y + pad.height()
            if (p is not None and "player" not in pad.cool and p.vy <= 0.5 and low <= p.y <= top + 0.12
                    and pad.over(p.x, p.z, p.RADIUS)):
                pad.throw_player(p, self)
            if w.phys is None:
                continue
            if things is None:  # the physics things, once a frame
                things = [t for t in w.things if isinstance(t, Thing) and t.alive and not t.hidden and t.dynamic()]
            for t in things:
                if t not in pad.cool and t.vel[1] < 1 and low - 0.05 <= t.y <= top + 0.25 and pad.over(t.x, t.z):
                    pad.throw(t)

    def glide(self, p, dt):
        """A boost pad's push: the player keeps going that way, slowing down (faster on the ground than in the air),
        stopped by walls."""
        vx, vz = self.boost
        solids = p.solids()
        nx, nz = p.x + vx * dt, p.z + vz * dt
        if not p.blocked(nx, p.z, p.y, solids):
            p.x = nx
        elif not p.try_step(nx, p.z, solids):
            vx = 0.0
        if not p.blocked(p.x, nz, p.y, solids):
            p.z = nz
        elif not p.try_step(p.x, nz, solids):
            vz = 0.0
        p.keep_inside()
        k = math.exp(-(2.2 if p.on_ground else 0.45) * dt)
        vx, vz = vx * k, vz * k
        self.boost = [vx, vz] if math.hypot(vx, vz) > 0.4 else None


class Route:
    """thing:path: a thing going along spots by itself at a speed, there and back again or round and round, in a
    straight line from each spot to the next (first from where it is to the first spot). It gets going and slows down
    gently where the path turns sharply (at the ends, at a corner), so what rides on it doesn't slide off, and goes
    straight on through gentle bends. Every spot is where it is in the world (its height above the land when the path
    was given)."""
    EASE = 0.8   # seconds to get up to speed, or to stop
    SHARP = 45   # a turn of more degrees than this stops it at the spot

    def __init__(self, thing, spots, speed, loop):
        self.speed = speed
        self.last = spots[0]  # where it stays once it's there, on a path to one spot
        order = spots + ([spots[0]] if loop else spots[-2::-1])
        self.cycle = [(a, b) for a, b in zip(order, order[1:]) if math.dist(a, b) > 1e-6]
        here = (thing.x, thing.y, thing.z)
        first = (here, spots[0])
        self.k = -1  # which leg of the cycle it's on (-1: on its way to the first spot)
        self.leg = None
        if math.dist(*first) > 1e-6:
            self.enter(first, None, self.cycle[0] if self.cycle else None)
        elif self.cycle:
            self.k = 0
            self.enter(self.cycle[0], None, self.cycle[1 % len(self.cycle)])
        self.t = 0.0

    def turn(self, a, b):
        """How many degrees the path turns going from leg a to leg b."""
        u = [a[1][i] - a[0][i] for i in range(3)]
        v = [b[1][i] - b[0][i] for i in range(3)]
        n = math.hypot(*u) * math.hypot(*v)
        return math.degrees(math.acos(clamp(sum(x * y for x, y in zip(u, v)) / n, -1.0, 1.0))) if n else 0.0

    def enter(self, leg, before, after):
        """Starts a leg: before and after are the legs either side of it (None: it starts from still, or stops)."""
        length = math.dist(*leg)
        ease = min(self.EASE, length / self.speed)
        start = before is None or self.turn(before, leg) > self.SHARP
        end = after is None or self.turn(leg, after) > self.SHARP
        self.leg = (leg, length, length / self.speed + ease / 2 * (start + end), ease, start, end)

    def along(self, t):
        """How far along its leg it is t seconds in."""
        _, length, secs, ease, start, end = self.leg
        v, a = self.speed, self.speed / ease if ease else 0.0
        if start and t < ease:
            return 0.5 * a * t * t
        if end and t > secs - ease:
            return length - 0.5 * a * (secs - t) ** 2
        return (0.5 * v * ease if start else 0.0) + v * (t - (ease if start else 0.0))

    def velocity(self):
        """How fast it's going each way now (metres a second)."""
        if self.leg is None:
            return 0.0, 0.0, 0.0
        (a, b), length, secs, ease, start, end = self.leg
        t, v = self.t, self.speed
        if start and t < ease:
            v *= t / ease
        elif end and t > secs - ease:
            v *= max(0.0, secs - t) / ease
        return tuple((b[i] - a[i]) / length * v for i in range(3))

    def acceleration(self):
        """How fast its speed changes each way now (metres a second, each second): getting going or slowing down at
        the ends and corners, else nothing."""
        if self.leg is None:
            return 0.0, 0.0, 0.0
        (a, b), length, secs, ease, start, end = self.leg
        k = self.speed / ease if ease else 0.0
        f = k if start and self.t < ease else -k if end and self.t > secs - ease else 0.0
        return tuple((b[i] - a[i]) / length * f for i in range(3))

    def step(self, dt):
        """Goes on dt seconds: (where it is now, whether it has finished: a path to one spot)."""
        if self.leg is None:
            return self.last, True
        self.t += dt
        while self.t >= self.leg[2]:
            self.t -= self.leg[2]
            if not self.cycle:  # it only had to get to its one spot
                self.leg = None
                return self.last, True
            before = self.leg[0]
            self.k = (self.k + 1) % len(self.cycle)
            self.enter(self.cycle[self.k], before, self.cycle[(self.k + 1) % len(self.cycle)])
        (a, b), length = self.leg[0], self.leg[1]
        f = clamp(self.along(self.t) / length, 0.0, 1.0) if length else 1.0
        return tuple(a[i] + (b[i] - a[i]) * f for i in range(3)), False


class Pad(Thing):
    """world:jump_pad and world:boost_pad: a glowing pad on the ground. It's an object, so it can be moved, turned,
    hidden, coloured or put on a path. Whoever touches a jump pad, the player or a physics thing, is launched up at its
    power (metres a second); a boost pad shoots them forward the way it faces (pad:turn aims it), a little up too. The
    page makes them look alive (level.js): a jump pad's glow breathes and rings rise from it, a boost pad's arrows light
    up one after another the way it points, and each flashes with a whoosh when it launches something."""
    COOL = 0.4  # seconds before a pad launches the same thing again (it's still leaving)

    def __init__(self, world, how, x, y, z, power):
        rim, glow, trim = PAD_LOOK[how]
        base = {"color": rim, "metal": 0.5, "rough": 0.4, "shadow": True}
        lit = {"color": glow, "emissive": glow, "rough": 0.35}
        if how == "jump":
            size = (2.2, 0.16, 2.2)
            parts = [("cylinder", {"r": 1.1, "h": 0.12, "y": 0.06, "seg": 40, **base}, False),
                     ("cylinder", {"r": 0.86, "h": 0.05, "y": 0.135, "seg": 40, **lit}, True),
                     ("torus", {"r": 0.98, "tube": 0.05, "seg": 48, "rx": 90, "y": 0.13, "color": trim, "emissive": trim}, False)]
        else:
            size = (2.0, 0.16, 3.2)
            parts = [("box", {"w": 2.0, "h": 0.12, "d": 3.2, "y": 0.06, **base}, False),
                     ("box", {"w": 1.56, "h": 0.04, "d": 2.9, "y": 0.13, **lit}, True)]
            for tip in (0.45, -0.35, -1.15):  # three arrows, back to front, pointing the way it faces (-z)
                for side in (-1, 1):
                    parts.append(("box", {"w": 0.15, "h": 0.03, "d": 0.67, "x": side * 0.25, "y": 0.165, "z": tip + 0.225,
                                          "ry": side * 48, "color": trim, "emissive": trim}, False))
        super().__init__(world, "pad", x, y, z, size, parts)
        self.how, self.power = how, power
        self.cool = {}  # what it launched lately ("player", or the thing): the seconds before it can again
        self.whooshed = -1.0  # the game's clock at its last whoosh
        ids = [int(node) for node, _ in self.parts]
        glows, arrows = (ids[1:3], []) if how == "jump" else (ids[1:2], ids[2:])
        world.view.js(f"window.tuffLevel && window.tuffLevel.pad(tv.node({int(self.node)}), {json.dumps(how)}, "
                      f"{json.dumps(glows)}, {json.dumps(arrows)})")

    def show_text(self, nested=False):
        return f"<{self.how} pad at {tidy(self.x)}, {tidy(self.y)}, {tidy(self.z)}>"

    def can_have_physics(self, kind):
        if kind in ("dynamic", "kinematic"):
            raise self.rt.error("A pad stays where it's put, so it can't fall or be pushed. Move it with pad:move_to, "
                                "or make it move by itself with pad:path.")
        Thing.can_have_physics(self, kind)

    def phys_shape(self, kind):
        if self.how == "jump":  # round
            kx, ky, kz = self.k
            hy = self.dims[1] * ky / 2
            return "cylinder", [tidy(hy), tidy(self.dims[0] * max(kx, kz) / 2)], tidy(hy)
        return Thing.phys_shape(self, kind)

    def size(self, w, h=MISSING, d=MISSING):
        if h is MISSING and d is MISSING and not isinstance(self.rt.plain(w), list):  # one number: how wide, still flat
            n = self.num(w, ":size")
            return Thing.size(self, n, self.dims[1], n * self.dims[2] / self.dims[0])
        return Thing.size(self, w, h, d)

    def set_color(self, color):
        c = self.world.color(color)
        for node, main in self.parts:
            if main:
                self.send(node, color=c, emissive=c)  # it glows in its new colour
        return self.native

    def facing(self):
        h = math.radians(self.heading)
        return math.sin(h), -math.cos(h)

    def over(self, x, z, r=0.0):
        """Is x, z (something r across... its radius) over the pad?"""
        dx, dz = x - self.x, z - self.z
        kx, _, kz = self.k
        if self.how == "jump":
            return math.hypot(dx, dz) <= self.dims[0] * max(kx, kz) / 2 + r * 0.5
        h = math.radians(self.heading)
        across, along = dx * math.cos(h) + dz * math.sin(h), dx * math.sin(h) - dz * math.cos(h)
        return abs(across) <= self.dims[0] * kx / 2 + r * 0.5 and abs(along) <= self.dims[2] * kz / 2 + r * 0.5

    def throw_player(self, p, level):
        if self.how == "jump":
            p.vy = self.power
        else:
            fx, fz = self.facing()
            level.boost = [fx * self.power, fz * self.power]
            p.vy = max(p.vy, min(7.0, 2.5 + self.power * 0.12))  # a little hop: it flies, rather than slides
            self.world.view.js(f"window.tuffLevel && window.tuffLevel.streak(tv.node({int(self.world.scene)}))")
        p.on_ground = False
        self.cool["player"] = self.COOL
        self.whoosh()

    def throw(self, t):
        """A physics thing on it: launched like the player (it keeps its speed across a jump pad)."""
        vx, vy, vz = (list(t.vel) + [0.0, 0.0, 0.0])[:3]
        if self.how == "jump":
            v = [vx, self.power, vz]
        else:
            fx, fz = self.facing()
            v = [fx * self.power, max(vy, 3.0), fz * self.power]
        t.vel = v
        self.world.phys.send("velocity", int(t.node), *v)
        self.cool[t] = self.COOL
        self.whoosh()

    def whoosh(self):
        w = self.world
        if w.clock - self.whooshed < 0.15:  # a few at once (a pile of boxes) make one whoosh
            return
        self.whooshed = w.clock
        w.view.call(0, "tones", WHOOSH[self.how], 0.3)
        w.view.js(f"window.tuffLevel && window.tuffLevel.whoosh({int(self.node)})")


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
  if ((e.key === 'Enter' || e.key === ' ') && !e.repeat && !typing(e.target) && document.querySelector('.tg-start.at-shown')
      && !document.querySelector('.tg-splashes.tg-playing')) tg.lock();  // a key during a splash screen only skips it
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
        self.shown, self.hides = [], 0  # the screens that show; how many times one hid (Game.step)
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
        if self.splash_playing():  # any key skips a splash screen (the page does it), and that's all it does
            return True
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
        self.hides += sum(1 for s in self.shown if s not in shown)
        self.shown = shown
        self.showing = bool(shown)
        self.pausing = any(s.pauses for s in shown)
        if SCENE is None and not g.closed and g.three_d:
            g.covered(self.showing)  # the mouse: World3D.covered
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
        return {"screens": [{"title": s.title, "shown": s.is_shown, "pauses": s.pauses, "start": isinstance(s, StartScreen),
                             "main": isinstance(s, MainMenu)} for s in self.screens if not isinstance(s, Splashes)],
                "showing": self.showing, "pausing": self.pausing, "texts": texts, "inputs": inputs, "values": values,
                "lock_asks": self.lock_asks, "splash": self.splash_state()}

    # ---- splash screens and main menus (Splashes and MainMenu, below)
    splash_layer = None  # the splash screens (game:splash), once there are some
    menu_played = False  # a main menu hid: when nothing covers the game, the mouse locks for looking around (3D)
    intro_css = False  # MENU_CSS and MENU_JS are on the page

    def intro_page(self):
        if not self.intro_css:
            self.intro_css = True
            self.scene.call(0, "css", MENU_CSS)
            self.scene.js(MENU_JS)

    def splashes(self):
        self.intro_page()
        if self.splash_layer is None:
            self.splash_layer = Splashes(self)
        return self.splash_layer

    def splash_playing(self):
        return self.splash_layer is not None and self.splash_layer.is_shown

    def splash_event(self, e):
        if self.splash_layer is not None and e.get("id") == self.splash_layer.id:
            self.splash_layer.event(e)

    def splashes_done(self):
        """The last splash screen ended: a main menu or start screen behind it comes in as if it just showed."""
        for s in self.screens:
            if s.is_shown and not s.dead and isinstance(s, (StartScreen, MainMenu)):
                s.call("atClass", "at-shown", False)
                s.call("atOpen")

    def splash_state(self):
        s = self.splash_layer
        if s is None:
            return None
        return {"playing": s.is_shown, "items": list(s.items), "ended": list(s.ended)}


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


# ---------------------------------------------------------------- splash screens, main menus and the mouse

# How they look (on top of UI_CSS). Splash screens: black over the whole window, each picture or text fading in and
# out in turn while it drifts a little closer. The main menu: the game dimmed and blurred, a big title, and wide
# buttons one under another in the middle. Both come in after GameUI's own CSS, the first time a game makes one.
MENU_CSS = """
.tg-ui .tg-splashes{position:fixed;inset:0;z-index:40;pointer-events:auto;background:#000;overflow:hidden;cursor:default;
 transition:opacity .5s ease}
.tg-ui .tg-splashes.tg-leaving{opacity:0;pointer-events:none}
.tg-ui .tg-splash{position:absolute;inset:0;display:none;align-items:center;justify-content:center;opacity:0;
 transition:opacity .45s ease}
.tg-ui .tg-splash.tg-on{opacity:1}
.tg-ui .tg-splash>*{animation:tg-drift var(--secs,2s) linear both}
@keyframes tg-drift{from{transform:scale(.97)}to{transform:scale(1.015)}}
.tg-ui .tg-splash-img{display:block;max-width:86%;max-height:80%;object-fit:contain;user-select:none;-webkit-user-drag:none}
.tg-ui .tg-splash-text{max-width:min(88%,1000px);font:800 clamp(30px,6.2vw,72px)/1.1 var(--font);letter-spacing:-.03em;
 color:#fff;text-align:center;text-wrap:balance;overflow-wrap:anywhere;white-space:pre-wrap}
.tg-ui .tg-made{display:flex;align-items:center;gap:clamp(16px,3vw,30px)}
.tg-ui .tg-made-t{height:clamp(64px,16vh,116px);width:auto;flex-shrink:0;overflow:visible}
.tg-ui .tg-made-t circle{transform-box:fill-box;transform-origin:center}
.tg-ui .tg-splash.tg-on .tg-made-t circle{animation:tg-dot .6s cubic-bezier(.2,.8,.3,1.25) both;animation-delay:var(--d)}
@keyframes tg-dot{from{opacity:0;transform:scale(.15)}}
.tg-ui .tg-made-words{display:flex;flex-direction:column;align-items:flex-start;gap:6px;text-align:left}
.tg-ui .tg-made-with{font:650 clamp(11px,1.8vh,14px)/1 var(--font);letter-spacing:.34em;text-transform:uppercase;color:#7d879c;
 padding-left:.18em}
.tg-ui .tg-made-name{font:800 clamp(52px,12.5vh,100px)/.92 var(--font);letter-spacing:-.045em;padding-right:.06em;
 background:linear-gradient(115deg,#fff 32%,#b9d3ff 70%,#7fe3f5);-webkit-background-clip:text;background-clip:text;
 -webkit-text-fill-color:transparent}
.tg-ui .tg-splash.tg-on .tg-made-words{animation:tg-rise .7s .28s cubic-bezier(.2,.8,.2,1) both}
.tg-ui .tg-main{position:absolute;inset:0;z-index:19;pointer-events:auto;display:flex;overflow:auto;padding:32px 28px;opacity:0;
 transition:opacity .2s;backdrop-filter:blur(7px) saturate(1.15);
 background:radial-gradient(110% 85% at 50% 40%,rgba(9,12,22,.3),rgba(3,4,8,.86)),linear-gradient(rgba(0,0,0,.1),rgba(0,0,0,.4))}
.tg-ui .tg-main.at-shown{opacity:1}
.tg-ui .tg-main-box{margin:auto;max-width:100%;display:flex;flex-direction:column;align-items:center;gap:30px;text-align:center}
.tg-ui .tg-main-title{font-size:clamp(40px,8.6vw,92px);max-width:min(92vw,900px);text-wrap:balance}
.tg-ui .tg-main-title::after{content:"";display:block;width:64px;height:4px;margin:22px auto 0;border-radius:4px;
 background:linear-gradient(90deg,var(--accent),var(--accent-2));box-shadow:0 0 22px color-mix(in srgb,var(--accent) 70%,transparent)}
.tg-ui .tg-main-body{width:min(360px,100%);--self:stretch;gap:12px;text-align:center}
.tg-ui .tg-main-body:empty{display:none}
.tg-ui .tg-main-body>:is(.at-text,.at-heading){color:#e6e9f0;text-shadow:0 1px 10px rgba(0,0,0,.5)}
.tg-ui .tg-main-body>.at-text{font-size:16px}
.tg-ui .tg-main-body>.at-small{font-size:13.5px;color:#a7aebb}
.tg-ui .tg-main-body>:is(.at-image,.at-badge,.at-icon,.at-spinner,.at-avatar){align-self:center}
.tg-ui .tg-main-body .at-btn{height:50px;border-radius:12px;font:650 16px/1 var(--font);gap:9px}
.tg-ui .tg-main-body .at-btn .at-i{width:18px;height:18px}
.tg-ui .tg-main-body .at-btn.at-primary{background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 62%,var(--accent-2)));
 box-shadow:inset 0 1px 0 rgba(255,255,255,.22),0 12px 30px -10px color-mix(in srgb,var(--accent) 75%,transparent)}
.tg-ui .tg-main-body .at-btn:is(.at-secondary,.at-outline,.at-ghost){background:rgba(255,255,255,.07);color:#eef1f6;
 border-color:rgba(255,255,255,.14);backdrop-filter:blur(8px)}
.tg-ui .tg-main-body .at-btn:hover{translate:0 -1px;filter:brightness(1.08)}
.tg-ui .tg-main-body .at-btn:is(.at-secondary,.at-outline,.at-ghost):hover{background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.26)}
.tg-ui .tg-main-body>.at-row{justify-content:center;gap:10px}
.tg-ui .tg-main-body>.at-row>.at-btn{flex:1 1 0}
.tg-ui .tg-main-body .at-card{text-align:left;background:color-mix(in srgb,var(--surface) 82%,transparent);backdrop-filter:blur(12px)}
.tg-ui .tg-main.at-shown .tg-main-title{animation:tg-rise .6s cubic-bezier(.2,.8,.2,1) both}
.tg-ui .tg-main.at-shown .tg-main-body>*{animation:tg-rise .5s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(.08s + var(--n,7) * 45ms)}
""" + "".join(f".tg-ui .tg-main-body>:nth-child({i + 1}){{--n:{i}}}\n" for i in range(7))

# The page side of splash screens: a layer plays its pictures and texts in turn. Each fades in, stays and fades out in
# its seconds (a picture waits until it has loaded), and a click or a key skips to the next. Python hears when each
# one ends ('tg-splash' with i), and when they all have (done, with how many there were): then the layer fades away.
MENU_JS = r"""
(() => {
  const FADE = 450, QUICK = 220;
  HTMLElement.prototype.tgSplash = function () {
    const layer = this;
    layer.classList.remove('tg-leaving');
    layer.classList.add('tg-playing');
    layer.style.display = '';
    if (layer._next) return null;  // playing already: it gets to the new one in turn
    const next = () => {
      const all = [...layer.children].filter((x) => x.classList.contains('tg-splash'));
      const item = all.find((x) => !x.classList.contains('tg-done'));
      if (!item) {
        layer._next = layer._skip = null;
        layer.classList.remove('tg-playing');
        layer.classList.add('tg-leaving');
        setTimeout(() => { if (!layer._next) { layer.style.display = 'none'; layer.classList.remove('tg-leaving'); } }, 520);
        tv.emit('tg-splash', { id: layer._tv, done: true, n: all.length });
        return;
      }
      const ms = Math.max(600, (+item.dataset.secs || 2) * 1000);
      const fade = Math.min(FADE, ms / 4);
      let timer = 0, over = false, shown = false;
      const end = (skipped) => {
        if (over) return;
        over = true;
        clearTimeout(timer);
        const out = shown ? (skipped ? QUICK : fade) : 0;
        item.style.transitionDuration = out + 'ms';
        item.classList.remove('tg-on');
        setTimeout(() => {
          item.classList.add('tg-done');
          item.style.display = 'none';
          tv.emit('tg-splash', { id: layer._tv, i: all.indexOf(item), skipped });
          next();
        }, out);
      };
      const start = () => {
        if (over) return;
        shown = true;
        item.style.setProperty('--secs', ms + 'ms');
        item.style.display = 'flex';
        void item.offsetWidth;
        item.style.transitionDuration = fade + 'ms';
        item.classList.add('tg-on');
        timer = setTimeout(() => end(false), ms - fade);
      };
      layer._skip = () => end(true);
      const img = item.querySelector('img');
      if (img && !img.complete && img.decode) Promise.race([img.decode().catch(() => {}), new Promise((r) => setTimeout(r, 1500))]).then(start);
      else start();
    };
    layer._next = next;
    next();
    return null;
  };
  // A click on a splash screen, or any key: the next one.
  const playing = () => document.querySelector('.tg-splashes.tg-playing');
  addEventListener('pointerdown', (e) => { const l = playing(); if (l && l._skip && l.contains(e.target)) l._skip(); }, true);
  addEventListener('keydown', (e) => { const l = playing(); if (l && l._skip && !e.repeat) l._skip(); }, true);
})();
"""

# The page side of the mouse in a 3D world (World3D.ask_lock). The browser only locks it in a click or a key press,
# or just after one, so world:lock_mouse() and a screen that gives the lock back ask right then; if the browser says
# no, the next click on the game locks it (the scene's data-tg-want), even after world:auto_lock(false).
MOUSE_JS = r"""
const m = window.__tgMouse = {};
const world = () => [...tv.objs.values()].find((n) => n.kind === 'scene');
m.lock = () => {
  const s = world();
  if (!s || document.pointerLockElement === s.el) return null;
  tv.emit('tg-lock', {});
  try { const p = s.el.requestPointerLock(); if (p && p.catch) p.catch(() => {}); } catch (err) { /* not now: the next click */ }
  return null;
};
addEventListener('pointerdown', (e) => {
  const n = e.target && e.target._tv !== undefined ? tv.objs.get(e.target._tv) : null;
  if (n && n.kind === 'scene' && !n.clicklock && n.el.hasAttribute('data-tg-want')) {
    if (document.pointerLockElement !== n.el) e.tvLocks = true;  // its mousedown says it locks the mouse (engine.js)
    m.lock();
  }
}, true);
"""


def made_with_tuff():
    """game:splash() with nothing: Tuff's dotted T (TuffCode's icon), its dots popping in one after another, and
    "Made with Tuff"."""
    dots = [(28 + 9 * c, 23.5 + 9 * r) for r in range(3) for c in range(9)]
    dots += [(55 + 9 * c, 50.5 + 9 * r) for r in range(7) for c in range(3)]
    circles = "".join(f'<circle cx="{x:g}" cy="{y:g}" r="3.1" style="--d:{round((x - 28) / 9 * 16 + (y - 23.5) / 9 * 30)}ms"/>'
                      for x, y in dots)
    return ('<div class="tg-made"><svg class="tg-made-t" viewBox="22 17 84 94" aria-hidden="true"><defs>'
            '<linearGradient id="tg-made-g" gradientUnits="userSpaceOnUse" x1="23.5" y1="19" x2="104.5" y2="109">'
            '<stop offset="0" stop-color="#3574f0"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs>'
            f'<g fill="url(#tg-made-g)">{circles}</g></svg><div class="tg-made-words"><span class="tg-made-with">Made with</span>'
            '<span class="tg-made-name">Tuff</span></div></div>')


class Splashes(Screen):
    """game:splash(...): the splash screens, one black layer over the whole window that plays its pictures and texts
    in turn when the game starts, before any main menu or start screen (those wait behind it). Each fades in and out
    in its seconds, and a click or any key skips to the next. The page times them and says when each one ends; while
    they play the game is paused and the mouse is free, like under any screen."""
    kind = "splash"
    cls = "tg-splashes"

    def __init__(self, ui):
        self.items, self.ended = [], []  # what each one shows, in order; how the ones that played ended
        super().__init__(ui, "", True)

    def build(self, title):
        self.title_id = None

    def add(self, kind, value, seconds, label):
        """One more splash screen: a "picture" (its address), some "text", or "tuff" (Made with Tuff)."""
        item = self.scene.el("div", self.id, cls="tg-splash", attrs={"data-secs": tidy(min(seconds, 60)), "data-kind": kind})
        if kind == "picture":
            self.scene.el("img", item, cls="tg-splash-img", src=value, alt="", draggable=False)
        elif kind == "text":
            self.scene.el("div", item, cls="tg-splash-text", text=value)
        else:
            self.scene.set(item, html=made_with_tuff())
        self.items.append(label)
        self.show()
        self.call("tgSplash")  # the page plays it after the ones before it

    def show(self):
        if not self.is_shown and not self.dead:
            self.is_shown = True
            self.ui.changed()

    def hide(self):
        """Splash screens end by themselves (event)."""

    def event(self, e):
        if e.get("done"):
            if self.is_shown and (e.get("n") or 0) >= len(self.items):  # else one came since, and the page plays it
                self.is_shown = False
                self.ui.changed()
                self.ui.splashes_done()
        elif "i" in e and len(self.ended) < len(self.items):
            self.ended.append("skipped" if e.get("skipped") else "timed")

    def set_title(self, text):
        return self.native()


class MainMenu(Screen):
    """game:main_menu("Forest Walk"): a game's main menu, a screen with a big title over the dimmed game and what
    the program adds under it (its buttons wide, one under another). It shows when the game starts, after any splash
    screens, with the game paused behind it and the mouse free: clicks on it are never the game's, and never lock the
    mouse. menu:hide() starts the game; in a 3D world with a player that also locks the mouse for looking around (in
    the click on the menu's button that hid it: World3D.covered). menu:show() brings it back, like from a pause menu.
    Other screens show over it."""
    cls = "tg-screen tg-main"

    def __init__(self, ui, title):
        super().__init__(ui, title, True)

    def build(self, title):
        box = self.scene.el("div", self.id, cls="tg-main-box")
        self.title_id = self.scene.el("h1", box, cls="tg-title tg-main-title", text=title, show=bool(title))
        self.slot = self.scene.el("div", box, cls="at-col tg-main-body")

    def show(self):
        if not self.is_shown and not self.dead:
            self.ui.menu_played = False
        super().show()

    def hide(self):
        if self.is_shown:
            self.ui.menu_played = True  # the game starts (or goes on)
        super().hide()


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
                f = t.sheet
                if f is not None:  # a picture cut into frames (sprite:frames), its animations and the one playing
                    item["frames"] = {"cells": [f.cols, f.rows], "frame": f.showing(g.clock), "playing": f.playing,
                                      "loop": f.loop, "animations": {n: {"frames": fr, "fps": tidy(fps)}
                                                                     for n, (fr, fps) in f.named.items()}}
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


# ---------------------------------------------------------------- saved game data (game:save, game:load)

SAVE_ENV = "TUFF_SAVE_DIR"  # a folder to keep every game's saves in instead of the usual one (the tests use it)
SAVE_KEEPS = "numbers, text, true/false, lists and tables"
# Names people guess for the four (from other engines, and from Python's files), with the tgame name. game:clear isn't
# here: it's tgame's own (it removes everything the program made).
SAVE_HINTS = {
    "store": "save", "write": "save", "save_data": "save", "save_game": "save", "savegame": "save", "set_data": "save",
    "persist": "save", "remember": "save", "read": "load", "get_data": "load", "load_data": "load", "load_game": "load",
    "loadgame": "load", "read_data": "load", "recall": "load", "restore": "load", "has_save": "saved",
    "has_saved": "saved", "is_saved": "saved", "has_data": "saved", "save_exists": "saved", "delete": "forget",
    "delete_save": "forget", "delete_data": "forget", "reset_save": "forget", "reset_saves": "forget",
    "clear_save": "forget", "clear_saves": "forget", "clear_data": "forget", "remove_save": "forget", "erase": "forget",
    "unsave": "forget", "wipe": "forget",
}
HINTS["game"].update(SAVE_HINTS)
HINTS["world"].update(SAVE_HINTS)
# Names Windows keeps for itself: a file can't be called one of these, whatever comes after the dot.
_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def save_folder():
    """Where games keep their saves: TuffSaves in the user's data folder (%APPDATA% on Windows, Application Support
    on a Mac, ~/.local/share elsewhere), or the folder TUFF_SAVE_DIR names."""
    own = os.environ.get(SAVE_ENV, "").strip()
    if own:
        return os.path.abspath(os.path.expanduser(own))
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = xdg if os.path.isabs(xdg) else os.path.join(home, ".local", "share")
    return os.path.join(base, "TuffSaves")


def save_file_name(title):
    """A game's save file: its title, made safe for a file name on every system ("Coin Dash.json")."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", str(title))
    name = " ".join(name.split())[:100].strip(". ")  # Windows drops dots and spaces at the end; a Mac hides a dot first
    if not name:
        name = "Untitled game"
    if name.split(".")[0].upper() in _DEVICE_NAMES:
        name += "_"
    return name + ".json"


def tuff_value(v):
    """A saved JSON value as Tuff has it: arrays come back as lists, and an object as a dictionary (1.4.0), so
    stats["level"] works. A table a 1.3.6 game saved from tap.data() reads the same way it did, since a dictionary has
    :get, :has, :keys, :set and :size too. Always a new copy: changing what :load gave doesn't change what's saved."""
    if isinstance(v, list):
        return [tuff_value(x) for x in v]
    if isinstance(v, dict):
        return {k: tuff_value(x) for k, x in v.items()}
    return v


class SavedData:
    """A game's saves (game:save, game:load, game:saved and game:forget): names and values in one JSON file, read the
    first time the game asks and written each time it saves something new, by writing a whole new file and putting it
    in the old one's place (so a crash mid-write never leaves half a file). The file is named after the title the
    game was made with (game:title doesn't change it), so a game run from TuffCode and the same game built with Build
    exe share their saves, and games with other titles never see them. A damaged file is set aside as .bad and the
    game starts with nothing saved. Tuff Engine's preview (tuff.py --scene) never reads or writes it: there :save
    does nothing and :load gives the default."""

    def __init__(self, game, title):
        self.game, self.rt, self.title = game, game.rt, str(title)
        self.values = None  # name -> its JSON value, once the file was read
        self.folder = self.path = None
        self.told = set()  # notes already shown (a folder that can't be written is said once, not on every save)

    @property
    def off(self):
        return SCENE is not None or os.environ.get("TUFF_SCENE") == "1"

    def what(self, method):
        return f"{self.game.KIND}:{method}"

    def note(self, text):
        if text not in self.told:
            self.told.add(text)
            sys.stderr.write(text + "\n")
            sys.stderr.flush()

    # ---- what a program gives
    def name_of(self, name, method, example):
        n = self.rt.plain(name)
        if not isinstance(n, str):
            raise self.rt.error(f"{self.what(method)} needs the save's name as text first, like {example}, not {self.rt.what(n)}.")
        if not n.strip():
            raise self.rt.error(f"A save needs a name, like \"best\": {example}")
        return n

    def keepable(self, v, inside=(), method="save"):
        """The JSON value for a Tuff value :save can keep: numbers, text, true/false, nil, lists and tables
        (dictionaries), inside each other too. A dictionary's number keys are kept as text, as
        file.save keeps them (JSON's names are text). Anything else is a Tuff error on the :save line. game:send and
        game:share take the same values (method: which one it is, for the message)."""
        rt = self.rt
        v = rt.plain(v)
        if v is None or isinstance(v, (bool, str)):
            return v
        verb = "keep" if method == "save" else "send" if method == "send" else "share"
        if isinstance(v, (int, float)):
            if v != v or v in (math.inf, -math.inf):
                raise rt.error(f"{self.what(method)} can only {verb} ordinary numbers, not {rt.text(v)}.")
            return v
        if isinstance(v, (list, dict)):
            if any(x is v for x in inside):
                raise rt.error(f"{self.what(method)} can't {verb} a list or table that holds itself.")
            inside = (*inside, v)
            if isinstance(v, list):
                return [self.keepable(x, inside, method) for x in v]
            return {rt.text(k): self.keepable(x, inside, method) for k, x in v.items()}
        raise rt.error(f"{self.what(method)} can {verb} {SAVE_KEEPS}, not {rt.what(v)}.")

    # ---- the file
    def read(self):
        if self.values is None:
            self.folder = save_folder()
            self.path = os.path.join(self.folder, save_file_name(self.title))
            self.values = {}
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                saves = data.get("saves") if isinstance(data, dict) else None
                if not isinstance(saves, dict):
                    raise ValueError("not a save file")
                self.values = saves
            except FileNotFoundError:
                pass
            except (OSError, ValueError):  # not JSON, not text, not a save file, or it can't be opened
                self.set_aside()
        return self.values

    def set_aside(self):
        if os.environ.get("TUFF_NO_WRITES") == "1":
            return
        bad = self.path + ".bad"
        try:
            os.replace(self.path, bad)
            kept = f" The old file is kept as {bad}."
        except OSError:
            kept = ""
        self.note(f"The saved data for \"{self.title}\" was damaged, so the game starts with nothing saved.{kept}")

    def write(self):
        if os.environ.get("TUFF_NO_WRITES") == "1":  # tuff_run for AI agents: saves stay in memory, like file.write's
            return
        import tempfile
        text = json.dumps({"game": self.title, "saves": self.values}, ensure_ascii=False, indent=2) + "\n"
        tmp = None
        try:
            os.makedirs(self.folder, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=os.path.basename(self.path) + ".", suffix=".tmp", dir=self.folder)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            for attempt in range(6):  # on Windows, a virus scanner reading the old file holds it for a moment
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.02 * (attempt + 1))
            tmp = None
        except OSError as exc:
            self.note(f"Couldn't save \"{self.title}\"'s data in {self.folder} ({exc.strerror or exc}). The game goes on, "
                      "and remembers what it saved until it closes.")
        finally:
            if tmp is not None:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def remove_file(self):
        if os.environ.get("TUFF_NO_WRITES") == "1":
            return
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            self.note(f"Couldn't forget \"{self.title}\"'s saves in {self.folder} ({exc.strerror or exc}).")

    # ---- game:save, game:load, game:saved and game:forget
    def save(self, name, value):
        name = self.name_of(name, "save", f'{self.what("save")}("best", score)')
        kept = self.keepable(value)
        if self.off:
            return None
        values = self.read()
        if name in values and json.dumps(values[name]) == json.dumps(kept):
            return None  # the same as what's saved (a game saving its score every frame doesn't write every frame)
        values[name] = kept
        self.write()
        return None

    def load(self, name, default=None):
        name = self.name_of(name, "load", f'best = {self.what("load")}("best", 0)')
        if self.off:
            return default
        values = self.read()
        return tuff_value(values[name]) if name in values else default

    def saved(self, name):
        name = self.name_of(name, "saved", f'{self.what("saved")}("best")')
        return False if self.off else name in self.read()

    def forget(self, name=MISSING):
        if name is not MISSING:
            name = self.name_of(name, "forget", f'{self.what("forget")}("best") (or nothing, to forget every save)')
        if self.off:
            return None
        values = self.read()
        if name is MISSING:
            values.clear()
            self.remove_file()
        elif name in values:
            del values[name]
            if values:
                self.write()
            else:
                self.remove_file()
        return None


class GameSaves:
    """What every game window and world gets for its saves (Game takes these methods, just below)."""
    NAMES = [("save", "save_value"), ("load", "load_value"), ("saved", "has_saved"), ("forget", "forget_saved")]

    def saves(self):
        if getattr(self, "save_file", None) is None:  # made by Game.__init__; this is for a game made some other way
            self.save_file = SavedData(self, self.view.title)
        return self.save_file

    def save_value(self, name, value):
        return self.saves().save(name, value)

    def load_value(self, name, default=None):
        return self.saves().load(name, default)

    def has_saved(self, name):
        return self.saves().saved(name)

    def forget_saved(self, name=MISSING):
        return self.saves().forget(name)


for _attr in ("saves", *(attr for _, attr in GameSaves.NAMES)):
    setattr(Game, _attr, getattr(GameSaves, _attr))
for _cls in (Game2D, World3D):
    _cls.NAMES = _cls.NAMES + GameSaves.NAMES


# ---------------------------------------------------------------- the autopilot (tests)

class Autopilot:
    """Plays a game by itself for the tests: TUFF_TGAME_AUTOPILOT names a JSON file of timed steps.

    {"on_top": true, "out": "folder", "timeout": 20, "steps": [
        {"at": 0.5, "key": "right"}, {"at": 1, "hold": "w", "for": 0.8}, {"at": 1.2, "keydown": "a"}, {"keyup": ...},
        {"at": 2, "click": [x, y]} (window pixels), {"click_world": [x, y]} (a 2D game's own units),
        {"click_center": true}, {"look": [dx, dy]} (mouse movement), {"lock": true} (act as if the mouse were locked),
        {"nudge_mouse": [dx, dy]}, {"hold_report": true}, {"watch_hold": true}, {"front": true} (the mouse held for
        looking around: see hold_step),
        {"click_ui": "Play"} (the first button, item, tab or text box showing on the game's menus with these words, or
        a text box's placeholder: exactly, or else containing them), {"type": "wasd", "for": 0.5} (keys typed into the
        text box that has the keys, let go after "for" seconds),
        {"call": "tuff_function"}, {"say": "text"}, {"js": "code"} (run in the page, where
        tv.emit('tg-autopilot', {message}) prints a line), {"mark": true} (start measuring), {"shot": "name.png"} (with
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
        self.hold_mouse = bool(plan.get("hold_mouse"))
        if not self.hold_mouse:  # the tests leave the real mouse alone, unless they test holding it
            os.environ["TUFF_VIEW_HOLD"] = "0"
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

    def hold_step(self, v, step):
        """{"front": true} brings the window in front of the others (as a click on it would); {"nudge_mouse": [dx, dy]}
        moves the real cursor as a hand would, when the plan holds the real mouse ("hold_mouse"), or else the page gets
        the move (as with "look"); {"hold_report": true} prints
        "[autopilot] hold {...}": whether the page and the computer hold the mouse, the window is in front, the cursor
        is kept inside the window, it's back in the middle, and where it is (Windows); {"watch_hold": true} prints
        "[autopilot] hold watch {"page": ...}" each time the page holds the mouse or lets go, from a thread of its own,
        so it's heard even while the program is busy."""
        if "nudge_mouse" in step and not self.hold_mouse:  # only a plan that holds the real mouse moves the real cursor
            v.js(self.look_js(v, *step["nudge_mouse"]))
            return
        hold = getattr(v, "_hold", None)
        if step.get("watch_hold") and hold is not None:
            import threading

            def watch(was=hold.on):
                while not self.game.closed:
                    if hold.on != was:
                        was = hold.on
                        print("[autopilot] hold watch " + json.dumps({"page": was}), flush=True)
                    time.sleep(0.01)
            threading.Thread(target=watch, name="tgame-autopilot-watch", daemon=True).start()
            return
        if sys.platform != "win32" or hold is None:
            if step.get("hold_report"):
                print("[autopilot] hold " + json.dumps({"none": True}), flush=True)
            return
        import ctypes
        from ctypes import wintypes
        u = hold.u
        if step.get("front") and v._hwnd:  # Windows lets the window in front give it away: borrow its input for that
            k = ctypes.WinDLL("kernel32")
            u.GetWindowThreadProcessId.restype = wintypes.DWORD
            u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
            them, me = u.GetWindowThreadProcessId(u.GetForegroundWindow(), None), k.GetCurrentThreadId()
            u.AttachThreadInput(me, them, True)
            try:
                u.SetForegroundWindow(wintypes.HWND(v._hwnd))
                u.BringWindowToTop(wintypes.HWND(v._hwnd))
            finally:
                u.AttachThreadInput(me, them, False)
            return
        if "nudge_mouse" in step:
            x, y = hold.where()
            hold.put(x + step["nudge_mouse"][0], y + step["nudge_mouse"][1])
            return
        clip = wintypes.RECT()
        u.GetClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
        u.GetClipCursor(ctypes.byref(clip))
        area = hold.area() if v._hwnd else None
        inside = area is not None and (clip.left, clip.top, clip.right, clip.bottom) == (area.left, area.top, area.right, area.bottom)
        x, y = hold.where()
        middle = area is not None and abs(x - (area.left + area.right) // 2) <= 1 and abs(y - (area.top + area.bottom) // 2) <= 1
        print("[autopilot] hold " + json.dumps({"page": hold.on, "active": hold.active, "front": hold.ours(),
                                                "inside": inside, "middle": middle, "cursor": [x, y]}), flush=True)

    def look_js(self, v, dx, dy):
        """The mouse moved by dx, dy, in the page (it counts for looking around, without moving the real cursor)."""
        w, h = v.size
        return (f"window.dispatchEvent(new PointerEvent('pointermove', {{clientX: {w / 2}, clientY: {h / 2}, movementX: {dx}, "
                f"movementY: {dy}, bubbles: true}}));")

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
            v.js(self.look_js(v, *step["look"]))
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
        if "js" in step:  # JavaScript in the page; tv.emit('tg-autopilot', {message}) prints what it finds
            v.js(step["js"])
        if "nudge_mouse" in step or step.get("hold_report") or step.get("front") or step.get("watch_hold"):
            self.hold_step(v, step)
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
        if g.three_d:
            out["mouse"] = g.mouse_state()  # world:mouse_locked(), the locks asked, world:auto_lock...
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
        # pictures cut into frames: [its node, the frame it shows, the animation playing (or None)]
        out["frames"] = [[int(s.node), s.sheet.showing(g.clock), s.sheet.playing] for s in g.things
                         if isinstance(s, Sprite) and s.alive and s.sheet is not None][:400]
        out["objects"] = [[t.kind, round(t.x, 2), round(t.y, 2), round(t.z, 2), t.fallen, t.data]
                          for t in g.things if isinstance(t, Thing) and t.alive][:400]
        out["physics"] = g.phys.state() if g.phys is not None else None
        out["effects"] = g.fx.state() if g.fx is not None else None
        if getattr(g, "interact", None) is not None:
            out["interact"] = g.interact.state()
        if getattr(g, "net", None) is not None:
            out["net"] = g.net.state_dump()
        if g.three_d and g.the_player is not None:
            out["on_ground"] = g.the_player.on_ground
            body = g.the_player.body  # third person: the figure the camera follows
            out["player_shown"] = body is not None and not body.hidden
        return out


# ---------------------------------------------------------------- for tuff.py --check

# What each method gives back, so the checker knows what a variable holds ("$number", "$text", "$bool",
# "$list", or another tgame kind). Left out: it depends (like :touches, :get or :looking_at).
# (:speed and :velocity are left out: with no inputs they give how fast it goes.)
_SETTERS = ("move", "move_to", "glide", "forward", "turn", "turn_to", "spin", "point_at", "on_edge", "size",
            "scale", "color", "layer", "flip", "align", "hide", "show", "set", "clicked", "shake", "look_at", "fall",
            "grow", "regrow", "swing", "glow", "solid", "label", "physics", "bounce", "friction", "push",
            "on_hit", "sleep", "wake")
_LOOKS = ("shirt", "pants", "skin", "hair", "shoes", "sleeves")  # a person's look (Thing.shirt...): give the thing back
_OBJECT_GIVES = {"x": "$number", "y": "$number", "z": "$number", "spot": "$list", "angle": "$number",
                 "distance": "$number", "fallen": "$bool"}
# game:panel gives a "panel" and game:screen and game:start_screen a "screen": atgui containers (tables()["ui_kinds"] has
# their methods; what those make is atgui's, as tuff_atgui.MAKES says).
_MENUS = {"panel": "panel", "screen": "screen", "start_screen": "screen", "main_menu": "screen"}
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
              "time_of_day": "$number", "mouse_locked": "$bool"},
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
    **{(k, "splash"): {0: "splash"} for k in ("game", "world")},
}
# Talking, grabbing, doors and keys (Interaction, Door).
for _k in ("object", "car", "ragdoll"):
    GIVES[_k].update({"say": _k, "on_talk": _k})
GIVES["world"]["door"] = "door"
GIVES["player"]["can_grab"] = "player"
GIVES["door"] = {**_OBJECT_GIVES, **{m: "door" for m in _SETTERS}, "say": "door", "on_talk": "door",
                 **{m: "door" for m in ("open", "close", "needs", "lock", "unlock")}}
for _k in ("object", "car", "ragdoll", "door"):
    HANDLERS.setdefault(_k, {})["on_talk"] = (0, 0, "no inputs")
HANDLERS["door"].update({"clicked": (0, 1, "1 input (the door)"), "on_hit": _HIT})
VALUES.update({("world", "door"): {3: "color", 1: "color"}, ("door", "color"): {0: "color"}, ("door", "glow"): {0: "glow"}})

# Saved game data (GameSaves, above): game:saved gives true or false. game:load is left out: it gives back whatever
# was saved.
for _kind in ("game", "world"):
    GIVES[_kind]["saved"] = "$bool"
# The level pieces: world:jump_pad and world:boost_pad make objects, thing:path gives the thing back, and its third
# input is how it goes ("ping-pong" or "loop").
GIVES["world"].update({"jump_pad": "object", "boost_pad": "object"})
GIVES["object"]["path"] = "object"
VALUES[("object", "path")] = {2: "path"}
# 1.3.0: getting in and out of cars, and how people look.
GIVES["car"].update({"on_enter": "car", "on_exit": "car", "driven": "$bool"})
GIVES["player"]["in_car"] = "$bool"
HANDLERS["car"].update({"on_enter": (0, 1, "1 input (the car)"), "on_exit": (0, 1, "1 input (the car)")})
for _k in ("object", "ragdoll", "player"):
    GIVES[_k].update({m: _k for m in _LOOKS})
    VALUES.update({(_k, "shirt"): {0: "color"}, (_k, "pants"): {0: "color"}, (_k, "shoes"): {0: "color"},
                   (_k, "skin"): {0: "skin"}, (_k, "hair"): {0: "hair", 1: "hair"}, (_k, "sleeves"): {0: "sleeves"}})
# 1.5.0: sprite-sheet animation. sprite:frame is left out (frame() gives a number, frame(3) the sprite); on_done's
# function gets the sprite and the animation's name.
GIVES["sprite"].update({m: "sprite" for m in ("frames", "animation", "play", "stop", "on_done")})
HANDLERS["sprite"]["on_done"] = (0, 2, "2 inputs (the sprite and the animation's name)")


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
    if what == "corner":  # world:minimap's (the HUD, at the end)
        return None if corner_name(value) else corner_problem(value.strip())
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
    if what in ("skin", "hair"):
        named = SKIN_COLORS if what == "skin" else HAIR_COLORS
        if low in named or low in COLORS or (low[:1] == "#" and len(low) in (4, 7) and all(c in "0123456789abcdef" for c in low[1:])):
            return None
        if what == "hair" and HAIR_WORDS.get(low, low) in HAIR_STYLES:
            return None
        if what == "skin":
            return f"'{value}' isn't a skin colour tgame knows. Try {', '.join(SKIN_COLORS)}, or a hex code like \"#e0ac7e\"."
        return (f"'{value}' isn't a hair style or colour tgame knows. Styles: {', '.join(HAIR_STYLES)}. Colours: "
                f"{', '.join(c for c in HAIR_COLORS if c not in ('blond', 'gray'))}, or a hex code.")
    if what == "sleeves":
        return None if SLEEVE_WORDS.get(low, low) in SLEEVES else f"Sleeves can be \"long\" or \"short\", not \"{value}\"."
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
    if what == "path":
        return None if path_mode(value) else path_problem(value.strip())
    if what == "splash":  # a picture file, or any other text to show
        if low.endswith(IMAGE_FILES):
            return file_problem(IMAGE_FILES, "picture")
        if low.endswith(NOT_PICTURES):
            return f"'{value.strip()}' can't be a splash screen. Use a picture from your project folder (.png, .jpg or .gif), or some text."
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
                      ("ragdoll", Ragdoll), ("door", Door)):
        obj = probe(cls)
        kinds[kind] = {name: getattr(obj, attr) for name, attr in cls.NAMES}
    kinds.update({kind: {name: getattr(probe(cls), attr) for name, attr in cls.NAMES} for kind, cls in HUD_KINDS})
    ui_kinds = {"panel": probe(Panel).methods(), "screen": probe(StartScreen).methods()}
    return {"lib": make_library(FakeRt()), "kinds": kinds, "gives": GIVES, "handlers": HANDLERS, "hints": HINTS,
            "check": check_value, "ui_kinds": ui_kinds, "anchors": ANCHORS, "physics_kinds": PHYSICS_KINDS,
            "physics_words": PHYSICS_WORDS, "needs_3d": NEEDS_3D, "weathers": WEATHERS}


# ---------------------------------------------------------------- the HUD: health bars, countdowns, arrows, minimaps
# Health for sprites, objects and the player (thing:health_bar, :hurt, :heal, :health, :on_death), game:countdown,
# world:arrow_to and world:minimap. The page draws them (tuff_view_web/hud.js): one <tg-hud> element over the game,
# whose methods tgame calls like any element's. Bars, the arrow and the map follow things where the page has them,
# so they keep up with physics too, with nothing sent each frame.

CORNERS = ("top right", "top left", "bottom left", "bottom right")
HUD_GOLD = "#f2c230"  # the arrow's colour, and a mark's unless the program gives one


def corner_name(text):
    """Which corner a minimap goes in ("top right"...) for what a program wrote ("Top-Right", "right top"...), or None."""
    name = anchor_name(text)
    return name if name in CORNERS else None


def corner_problem(name):
    return (f"A minimap can go in the top right, top left, bottom left or bottom right corner, not \"{name}\"."
            + did_you_mean(str(name).strip().lower(), CORNERS))


class HudPage:
    """The page's side of the HUD: a <tg-hud> element (hud.js) over the game, under its HUD layer and its menus."""

    def __init__(self, game):
        self.game = game
        under = [int(game.hud_layer.node)] if game.hud_layer is not None else []
        if game.ui is not None and SCENE is None:
            under.append(int(game.ui.id))
        self.node = game.view.el("tg-hud", 0, **({"before": min(under)} if under else {}))
        view = int(game.scene) if game.three_d else int(game.node)
        game.view.call(self.node, "setup", {"three_d": game.three_d, "view": view, "size": [game.W, game.H]})

    def call(self, method, *args):
        self.game.view.call(self.node, method, *args)

    def player(self):
        """Tells the page where the map and the arrow measure from: the car the player drives, the player's figure in
        third person, or (0) the camera. Sent again when that changes (the player is made, gets in or out of a car)."""
        car, p = getattr(self.game, "driving", None), getattr(self.game, "the_player", None)
        body = p.body if p is not None else None
        self.call("player", int(car.node) if car is not None else int(body.node) if body is not None else 0)


def hud_page(game):
    if getattr(game, "hud_js", None) is None:
        game.hud_js = HudPage(game)
    return game.hud_js


class Health:
    """Health, for sprites (2D), objects (3D: cars and ragdolls too) and the player. thing:health_bar(100) gives it
    100 health and a bar over it (an object's faces the camera; the player's goes along the bottom of the screen);
    :hurt takes some off (the bar shrinks and flashes), :heal gives some back, :health is how much it has, and its
    :on_death functions run once when it reaches 0 (again only if it's healed and runs out again)."""
    NAMES = [("health_bar", "health_bar"), ("hurt", "hurt"), ("heal", "heal"), ("health", "health"),
             ("on_death", "on_death")]
    HELPERS = ("hp_game", "hp_name", "hp_need", "hp_amount", "hp_send")

    def hp_game(self):
        return self.world if isinstance(self, Player) else self.game

    def hp_name(self):
        return "player" if isinstance(self, Player) else self.phys_name()

    def hp_need(self, what):
        if getattr(self, "hp_most", None) is None:
            n = self.hp_name()
            raise self.rt.error(f"{n}:{what} needs health first. Give it a health bar, like {n}:health_bar(100).")

    def hp_amount(self, amount, what, other):
        n = self.rt.number(amount, f":{what}")
        if n < 0:
            raise self.rt.error(f"{self.hp_name()}:{what} needs a number of 0 or more. To {other} it, use :{other}.")
        return n

    def hp_send(self, flash=None):
        kind = "player" if isinstance(self, Player) else "3d" if isinstance(self, Thing) else "2d"
        label = getattr(self, "label_node", None)  # an object's bar goes over its label
        hud_page(self.hp_game()).call("bar", "player" if kind == "player" else int(self.node),
                                      {"kind": kind, "value": tidy(self.hp), "most": tidy(self.hp_most), "flash": flash,
                                       "label": int(label) if label is not None else 0})

    def health_bar(self, most=100):
        m = self.rt.number(most, ":health_bar")
        if m <= 0:
            n = self.hp_name()
            raise self.rt.error(f"{n}:health_bar needs the most health it can have, above 0, like {n}:health_bar(100).")
        self.hp_most = self.hp = float(m)  # full (again)
        self.hp_out = False
        self.hp_send()
        return self.native

    def hurt(self, amount):
        self.hp_need("hurt")
        n = self.hp_amount(amount, "hurt", "heal")
        if self.hp_out or not n:
            return self.native
        self.hp = max(0.0, self.hp - n)
        self.hp_send("hurt")
        if self.hp <= 0:
            self.hp_out = True
            for fn in list(getattr(self, "death_fns", ())):
                self.hp_game().fire(fn, self.native)
        return self.native

    def heal(self, amount):
        self.hp_need("heal")
        n = self.hp_amount(amount, "heal", "hurt")
        if not n or self.hp >= self.hp_most:
            return self.native
        self.hp = min(self.hp_most, self.hp + n)
        self.hp_out = False
        self.hp_send("heal")
        return self.native

    def health(self):
        self.hp_need("health")
        return tidy(self.hp)

    def on_death(self, fn):
        fn = self.hp_game().lib.check_fn(fn, ":on_death")
        if getattr(self, "death_fns", None) is None:
            self.death_fns = []
        self.death_fns.append(fn)
        return self.native


class Countdown:
    """game:countdown(60, times_up): a timer in the top right that counts down on the game's clock (so it stops while
    the game is paused), turns red under 10 seconds and runs times_up() at 0. A game has one: making it again starts
    it again. It's one of the game's movers while it runs."""
    NAMES = [("add", "add"), ("stop", "stop"), ("left", "left")]

    def __init__(self, game):
        self.game, self.rt = game, game.rt
        self.alive = True
        self.secs = 0.0
        self.fn = None
        self.running = False
        self.shown = None
        self.native = game.rt.native("countdown", methods(self, "countdown", self.NAMES, game.rt),
                                     lambda nested=False: f"<countdown, {self.left()} s left>")
        self.native.tg = self

    def start(self, seconds, fn):
        self.secs, self.fn, self.running = float(seconds), fn, seconds > 0
        self.shown = None
        self.send()
        self.busy()

    def busy(self):
        if self.running:
            self.game.movers.add(self)
        else:
            self.game.movers.discard(self)

    def send(self):
        """The whole seconds left, to the page, when they change."""
        shown = self.left()
        if shown != self.shown:
            self.shown = shown
            hud_page(self.game).call("countdown", {"left": shown})

    def tick(self, dt):
        self.secs -= dt
        if self.secs > 0:
            self.send()
            return
        self.secs = 0.0
        self.running = False
        self.busy()
        self.send()
        if self.fn is not None:
            self.game.fire(self.fn)

    def add(self, seconds):
        finished = self.secs <= 0 and not self.running
        self.secs = max(0.0, self.secs + self.rt.number(seconds, ":add"))
        if finished and self.secs > 0 and self.shown is not None:
            self.running = True  # it had run out: more time starts it again
        self.send()
        self.busy()
        return self.native

    def stop(self):
        self.running = False
        self.busy()
        return self.native

    def left(self):
        return math.ceil(max(0.0, self.secs) - 1e-9)


class Arrow:
    """world:arrow_to(chest): an arrow that points the way to something, with how far away it is: over it while it's
    in view, at the edge of the screen when it isn't, and along the bottom when it's behind you. A world has one:
    world:arrow_to(other) points it at something else. It can point at a spot too, like world:arrow_to(10, 0, -20)."""
    NAMES = [("hide", "hide"), ("show", "show")]

    def __init__(self, world):
        self.world, self.rt = world, world.rt
        self.shown = True
        self.target = None
        self.native = world.rt.native("arrow", methods(self, "arrow", self.NAMES, world.rt), lambda nested=False: "<arrow>")
        self.native.tg = self

    def point(self, args):
        w = self.world
        t = thing_of(args[0])
        if isinstance(t, Player):
            raise self.rt.error("world:arrow_to shows the player the way to something else, like world:arrow_to(chest).")
        if isinstance(t, Thing):
            if not t.alive:
                raise self.rt.error("world:arrow_to can't point at something that was removed.")
            if not t.on_land:
                raise self.rt.error("world:arrow_to points at things in the world, not at something the player holds.")
            self.target = {"id": int(t.node)}
        else:
            v = self.rt.plain(args[0])
            if not isinstance(v, list) and not isinstance(v, (int, float)):
                raise self.rt.error(f"world:arrow_to needs a thing to point at, like world:arrow_to(chest), or a spot "
                                    f"like [10, 0, -20], not {self.rt.what(v)}.")
            x, y, z, _ = w.where(args, (), "arrow_to")
            self.target = {"at": [tidy(x), tidy(w.above(x, y, z)), tidy(z)]}
        hud_page(w).player()
        self.send()

    def send(self):
        hud_page(self.world).call("arrow", {**self.target, "shown": self.shown, "color": HUD_GOLD})

    def hide(self):
        self.shown = False
        self.send()
        return self.native

    def show(self):
        self.shown = True
        self.send()
        return self.native


class Minimap:
    """world:minimap(): a round map in a corner, north up: the land around the player (its colours and its water),
    the player as an arrow, and a dot for each thing map:mark gave it (one too far away waits at the map's edge).
    map:zoom(2) shows things twice as big. A world has one: world:minimap(240, "top left") changes it."""
    NAMES = [("mark", "mark"), ("unmark", "unmark"), ("zoom", "zoom")]

    def __init__(self, world):
        self.world, self.rt = world, world.rt
        self.size, self.corner, self.k = 180, "top right", 1.0
        self.marks = {}  # node id -> colour
        self.native = world.rt.native("minimap", methods(self, "minimap", self.NAMES, world.rt), lambda nested=False: "<minimap>")
        self.native.tg = self

    def floors(self):
        """The world's ground and islands, for the map (the page finds a terrain by itself)."""
        out = []
        for t in self.world.things:
            if isinstance(t, Thing) and t.alive and getattr(t, "floor", False):
                if t.kind == "island":
                    out.append({"island": tidy(t.dims[0] / 2)})
                else:
                    out.append({"ground": tidy(t.dims[0]), "color": getattr(t, "floor_color", None) or COLORS["grass"]})
        return out

    def send(self):
        page = hud_page(self.world)
        page.player()
        page.call("minimap", {"size": self.size, "corner": self.corner, "zoom": self.k, "floors": self.floors()})

    def thing(self, v, what):
        t = thing_of(v)
        if not isinstance(t, Thing) or not t.on_land:
            raise self.rt.error(f"map:{what} needs a thing in the world, like map:{what}(coin), not {self.rt.what(v)}.")
        return t

    def mark(self, thing, color=HUD_GOLD):
        t = self.thing(thing, "mark")
        c = self.world.color(color)
        self.marks[int(t.node)] = c
        hud_page(self.world).call("mark", int(t.node), c)
        return self.native

    def unmark(self, thing):
        t = self.thing(thing, "unmark")
        if self.marks.pop(int(t.node), None) is not None:
            hud_page(self.world).call("unmark", int(t.node))
        return self.native

    def zoom(self, k):
        n = self.rt.number(k, ":zoom")
        if n <= 0:
            raise self.rt.error("map:zoom needs a number above 0: 2 shows things twice as big, 0.5 shows twice as far.")
        self.k = clamp(n, 0.05, 50)
        self.send()
        return self.native


def countdown(self, seconds, fn=None):  # game:countdown and world:countdown
    secs = self.num(seconds, ":countdown")
    if secs < 0:
        raise self.rt.error(":countdown needs how many seconds it counts down from, like game:countdown(60, times_up).")
    if fn is not None:
        fn = self.lib.check_fn(fn, ":countdown")
    if getattr(self, "the_countdown", None) is None:
        self.the_countdown = Countdown(self)
    self.the_countdown.start(secs, fn)
    return self.the_countdown.native


def arrow_to(self, x, y=MISSING, z=MISSING):  # world:arrow_to
    if getattr(self, "the_arrow", None) is None:
        self.the_arrow = Arrow(self)
    self.the_arrow.point([x, y, z])
    return self.the_arrow.native


def minimap(self, size=180, corner="top right"):  # world:minimap
    s = self.num(size, ":minimap")
    if not 60 <= s <= 600:
        raise self.rt.error(":minimap needs a size from 60 to 600 (how many pixels across), like world:minimap(180).")
    where = corner_name(self.rt.text(corner))
    if where is None:
        raise self.rt.error(corner_problem(self.rt.text(corner)))
    if getattr(self, "the_map", None) is None:
        self.the_map = Minimap(self)
    m = self.the_map
    m.size, m.corner = tidy(s), where
    m.send()
    return m.native


# The HUD's names on the kinds that have them: health on sprites, objects (cars and ragdolls too) and the player.
Game.countdown, World3D.arrow_to, World3D.minimap = countdown, arrow_to, minimap
Game2D.NAMES = Game2D.NAMES + [("countdown", "countdown")]
World3D.NAMES = World3D.NAMES + [("countdown", "countdown"), ("arrow_to", "arrow_to"), ("minimap", "minimap")]
for _cls in (Sprite, Thing, Car, Player):  # a ragdoll has an object's names
    _cls.NAMES = _cls.NAMES + Health.NAMES
for _cls in (Sprite, Thing, Player):
    for _attr in [a for _, a in Health.NAMES] + list(Health.HELPERS):
        setattr(_cls, _attr, getattr(Health, _attr))
HUD_KINDS = (("countdown", Countdown), ("arrow", Arrow), ("minimap", Minimap))

NEEDS_3D.update({"arrow_to": "The arrow needs a 3D world. Make the game with tgame.world(...) to point the way to things.",
                 "minimap": "The minimap needs a 3D world. Make the game with tgame.world(...) for one."})
_HEALTH_HINTS = {"damage": "hurt", "take_damage": "hurt", "harm": "hurt", "hp": "health", "get_health": "health",
                 "life": "health", "healthbar": "health_bar", "hp_bar": "health_bar", "life_bar": "health_bar",
                 "lifebar": "health_bar", "max_health": "health_bar", "set_health": "health_bar", "cure": "heal",
                 "restore": "heal", "on_die": "on_death", "on_dead": "on_death", "died": "on_death",
                 "when_dead": "on_death", "on_killed": "on_death"}
for _kind in ("sprite", "object", "car", "ragdoll", "player"):
    HINTS[_kind].update({k: v for k, v in _HEALTH_HINTS.items() if k not in HINTS[_kind]})
_TIMER_HINTS = {"timer": "countdown", "count_down": "countdown", "countdown_timer": "countdown"}
HINTS["game"].update(_TIMER_HINTS)
HINTS["world"].update({**_TIMER_HINTS, "compass": "arrow_to", "waypoint": "arrow_to", "pointer": "arrow_to",
                       "point_to": "arrow_to", "arrow": "arrow_to", "map": "minimap", "mini_map": "minimap",
                       "radar": "minimap"})
HINTS["countdown"] = {"pause": "stop", "end": "stop", "time_left": "left", "remaining": "left", "seconds": "left",
                      "time": "left", "add_time": "add", "extend": "add", "plus": "add"}
HINTS["arrow"] = {"remove": "hide", "visible": "show"}
HINTS["minimap"] = {"dot": "mark", "add": "mark", "track": "mark", "pin": "mark", "remove": "unmark",
                    "untrack": "unmark", "zoom_in": "zoom", "scale": "zoom"}

GIVES["game"]["countdown"] = "countdown"
GIVES["world"].update({"countdown": "countdown", "arrow_to": "arrow", "minimap": "minimap"})
for _kind in ("sprite", "object", "car", "ragdoll", "player"):
    GIVES[_kind].update({"health_bar": _kind, "hurt": _kind, "heal": _kind, "health": "$number", "on_death": _kind})
GIVES.update({"countdown": {"left": "$number", "add": "countdown", "stop": "countdown"},
              "arrow": {"hide": "arrow", "show": "arrow"},
              "minimap": {"mark": "minimap", "unmark": "minimap", "zoom": "minimap"}})
for _kind in ("game", "world"):
    HANDLERS[_kind]["countdown"] = (1, 0, "no inputs")
for _kind in ("sprite", "object", "car", "ragdoll", "player"):
    HANDLERS.setdefault(_kind, {})["on_death"] = (0, 1, f"1 input (the {_kind} whose health ran out)")
VALUES.update({("world", "minimap"): {1: "corner"}, ("minimap", "mark"): {1: "color"}})


# ---------------------------------------------------------------- multiplayer: games on the same network (1.3.0)
# game:host(name) makes a room that other games on the same network (the same Wi-Fi, or cables to the same router)
# can find, and game:join() finds one and goes in: game:join("Tag") looks for the room called Tag, and
# game:join("192.168.1.20") goes straight to that computer. The host's game keeps the room: every message goes
# through it, it keeps the shared values (game:share, game:shared) and it tells everyone who comes and goes. In a 3D
# world each player's player shows up in everyone else's world as a person with their name over their head, walking
# where they walk (world:others() gives them to the program).
#
# The sockets live on a thread of their own (NetLink), which never runs Tuff. What it hears waits in a queue that
# the game empties at each frame (Net.frame), so on_message, on_join and on_leave run between frames, like on_key.
# Messages are lines of JSON over TCP. Finding rooms is UDP: a joining game asks "who's hosting?" across the
# network (and on this computer), and each host answers with its room's name and port.

NET_VERSION = 1
NET_PORT = 47800  # finding rooms (UDP); a host takes the first free TCP port after it (47801...)
# The UDP ports hosts answer on, after NET_PORT: the first free one each (a second host on the same computer can't
# share the first: Windows would give each question to only one of them). Joining games ask on all of them.
NET_FIND_PORTS = (0, 10, 11, 12, 13)
NET_PORT_ENV = "TUFF_NET_PORT"  # another first port (the tests use their own, away from real games)
NET_LOCAL_ENV = "TUFF_NET_LOCAL"  # "1": only games on this computer (quiet tests: no firewall questions)
NET_SEND_EVERY = 0.05  # where the player is goes out 20 times a second while it moves (and each second when not)
NET_MAX_PLAYERS = 16
NET_LINE_MAX = 1 << 20  # a line longer than this (a megabyte) isn't a game's: the connection goes
NET_NAME_MAX = 24
# Shirts for the players' people, in the order they join: the host's is the blue the player's own figure has.
NET_SHIRTS = ("#3574f0", "#e5484d", "#2fa36b", "#f2a33a", "#8e5bd8", "#14b8a6", "#ec4899", "#e2a508")
NET_ADDRESS = re.compile(r"^\s*(localhost|\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?\s*$", re.I)
_WOULD_BLOCK = {getattr(errno, n) for n in ("EINPROGRESS", "EWOULDBLOCK", "EALREADY") if hasattr(errno, n)} | {10035}
# Names people guess for these (Roblox, Godot, socket libraries...), with the tgame name.
NET_HINTS = {
    "host_game": "host", "create_room": "host", "make_room": "host", "start_server": "host",
    "create_server": "host", "open_room": "host", "start_host": "host", "host_room": "host", "create_game": "host",
    "connect": "join", "join_game": "join", "join_room": "join", "find_game": "join", "find_room": "join",
    "connect_to": "join", "disconnect": "leave", "leave_game": "leave", "leave_room": "leave",
    "quit_game": "leave", "exit_room": "leave", "is_connected": "connected", "online": "connected",
    "is_online": "connected", "in_room": "connected", "is_host": "hosting", "is_server": "hosting",
    "am_host": "hosting", "is_hosting": "hosting", "player_list": "players", "get_players": "players",
    "list_players": "players", "everyone": "players", "set_name": "my_name", "name": "my_name", "nickname": "my_name",
    "username": "my_name", "player_name": "my_name", "set_nickname": "my_name", "broadcast": "send",
    "emit": "send", "send_message": "send", "message": "send", "tell": "send", "rpc": "send",
    "on_receive": "on_message", "on_received": "on_message", "on_data": "on_message", "on_msg": "on_message",
    "received": "on_message", "on_event": "on_message", "listen": "on_message", "on_player_join": "on_join",
    "on_player_joined": "on_join", "on_joined": "on_join", "on_connect": "on_join", "player_joined": "on_join",
    "on_player_leave": "on_leave", "on_player_left": "on_leave", "on_left": "on_leave", "on_disconnect": "on_leave",
    "player_left": "on_leave", "sync": "share", "set_shared": "share", "share_value": "share", "set_var": "share",
    "get_shared": "shared", "shared_value": "shared", "get_var": "shared", "other_players": "others",
    "remote_players": "others", "get_others": "others", "opponents": "others",
}


def net_base_port():
    try:
        port = int(os.environ.get(NET_PORT_ENV) or NET_PORT)
    except ValueError:
        port = NET_PORT
    return port if 1024 <= port <= 65000 else NET_PORT


def net_local():
    """Whether rooms stay on this computer: TUFF_NET_LOCAL=1, or a quiet test run (TUFF_TEST_QUIET=1) that doesn't
    say. A room on this computer only listens on 127.0.0.1, which never asks the firewall."""
    own = os.environ.get(NET_LOCAL_ENV)
    if own is not None:
        return own.strip() == "1"
    return os.environ.get("TUFF_TEST_QUIET") == "1"


def local_ips():
    """This computer's addresses on its networks (not 127.0.0.1), the one it reaches other computers with first."""
    ips = []
    try:  # no packet goes out: connecting a UDP socket only picks the way it would go
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    seen = []
    for ip in ips:
        if ip not in seen and not ip.startswith(("127.", "169.254.", "0.")):
            seen.append(ip)
    return seen


def net_address(text):
    """(ip, port or None) for an address written as text ("192.168.1.20", "localhost:47801"), or None for a room's name."""
    m = NET_ADDRESS.match(text)
    if not m:
        return None
    ip = "127.0.0.1" if m.group(1).lower() == "localhost" else m.group(1)
    if any(int(n) > 255 for n in ip.split(".")):
        return None
    port = int(m.group(2)) if m.group(2) else None
    return ip, (port if port is None or 0 < port < 65536 else None)


def same_room(a, b):
    return " ".join(str(a).lower().split()) == " ".join(str(b).lower().split())


class _Conn:
    """One TCP connection: what came in that isn't a whole line yet, and what's still to go out."""
    __slots__ = ("sock", "buf", "out", "id", "events", "to", "ended", "key")

    def __init__(self, sock):
        self.sock, self.buf, self.out = sock, bytearray(), bytearray()
        self.id = None
        self.events = 0
        self.to = None
        self.ended = False
        self.key = None  # where a joining game's connection goes: (ip, port)


class NetLink(threading.Thread):
    """The sockets of a game in a room, on a thread of their own: a host's (it keeps the room) or a joining game's.
    It never runs Tuff. What it hears goes into `inbox` as events for the game's frame, and what the game says comes
    in through say() (which wakes it).

    The host is player 1. It relays every message, keeps the shared values (each change goes out to everyone in the
    order the host saw it, back to the one who made it too) and remembers where each player last was, for players
    who come later. A joining game asks the network for rooms, picks one (the room it was told to look for, or one
    for the same game, or the first to answer), and goes in."""

    def __init__(self, role, title, name, room=None, address=None, listener=None, shared=None):
        super().__init__(name=f"tgame-net-{role}", daemon=True)
        self.role, self.title, self.my_name = role, title, name
        self.room, self.address = room, address
        self.inbox = queue.Queue()
        self.outbox = collections.deque()
        self.lock = threading.Lock()
        self.stopping = False
        self.local = net_local()
        self.base = net_base_port()
        self.sel = selectors.DefaultSelector()
        self.wake_r, self.wake_w = socket.socketpair()
        for s in (self.wake_r, self.wake_w):
            s.setblocking(False)
        self.sel.register(self.wake_r, selectors.EVENT_READ, self.on_wake)
        self.udp = None
        self.conns = []
        # host
        self.listener = listener
        self.players = {1: name}
        self.next_id = 2
        self.shared = dict(shared or {})
        self.last_pos = {}
        # joining
        self.conn = None  # the connection to the host, once one is being made
        self.joined = False
        self.found, self.first_found, self.next_ask, self.asks = {}, None, 0.0, 0
        self.bad = {}  # rooms that didn't let us in, for a few seconds
        self.waiting = collections.deque(maxlen=200)  # messages said before the host let us in
        self.hello_by = 0.0

    # ---- the game's side (the Tuff thread)
    def say(self, op):
        with self.lock:
            self.outbox.append(op)
        self.poke()

    def poke(self):
        try:
            self.wake_w.send(b"!")
        except OSError:  # its buffer is full (it's waking anyway), or it's closed
            pass

    def stop(self):
        self.stopping = True
        self.poke()

    # ---- the thread
    def post(self, e):
        self.inbox.put(e)

    def run(self):
        try:
            if self.role == "host":
                self.start_host()
            else:
                self.start_join()
            while not self.stopping:
                timeout = self.tick()
                for key, mask in self.sel.select(timeout):
                    key.data(mask)
                    if self.stopping:
                        break
        except Exception as exc:  # anything at all: the game hears it, and the game goes on
            self.post({"t": "error", "why": str(exc) or type(exc).__name__})
        finally:
            self.shut()

    def tick(self):
        """Work done on time, not when a socket says something: asking for rooms, and giving up on a slow host.
        Gives how long the thread can wait for its sockets."""
        if self.role == "host" or self.joined:
            return 1.0
        now = time.monotonic()
        if self.conn is not None:
            if now > (self.conn.to if self.conn.to is not None else self.hello_by):
                self.failed("slow")  # it didn't answer, or didn't let us in
            return 0.1
        if now >= self.next_ask:
            self.ask()
            self.next_ask = now + 0.5
        if self.first_found is not None and now - self.first_found >= 0.3:
            self.pick()
        return max(0.01, min(self.next_ask - now, 0.1))

    def on_wake(self, mask):
        try:
            while self.wake_r.recv(4096):
                pass
        except OSError:
            pass
        while True:
            with self.lock:
                if not self.outbox:
                    break
                op = self.outbox.popleft()
            if self.role == "host":
                self.host_op(op)
            elif self.joined:
                self.write(self.conn, op)
            elif op.get("t") == "msg":
                self.waiting.append(op)  # it goes once the host lets us in (where the player is goes again by itself)
            elif op.get("t") == "name":
                self.my_name = op.get("name")

    def shut(self):
        """Closing down: a host tells everyone the room is closing (so their games say "The host left"), and every
        socket closes."""
        for c in list(self.conns):
            try:
                if self.role == "host" and c.id is not None:
                    c.out += self.line({"t": "end"})
                c.sock.setblocking(True)
                c.sock.settimeout(0.2)
                if c.out:
                    c.sock.sendall(bytes(c.out))
            except OSError:
                pass
            try:
                c.sock.close()
            except OSError:
                pass
        self.conns = []
        for s in (self.listener, self.udp, self.wake_r, self.wake_w):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
        try:
            self.sel.close()
        except Exception:
            pass

    # ---- lines of JSON
    @staticmethod
    def line(obj):
        return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    def add(self, sock, to=None):
        sock.setblocking(False)
        c = _Conn(sock)
        c.to = to
        self.conns.append(c)
        if to is None:
            self.watch(c, selectors.EVENT_READ)
        else:  # a connection being made: it's ready to write once it's made (or failed)
            self.watch(c, selectors.EVENT_WRITE)
        return c

    def watch(self, c, events):
        if events == c.events:
            return
        if c.events:
            self.sel.modify(c.sock, events, lambda mask, c=c: self.on_conn(c, mask))
        else:
            self.sel.register(c.sock, events, lambda mask, c=c: self.on_conn(c, mask))
        c.events = events

    def write(self, c, obj):
        if c is None or c not in self.conns:
            return
        c.out += self.line(obj)
        if len(c.out) > 8 * NET_LINE_MAX:  # it isn't reading what it's sent: let it go
            self.drop(c)
            return
        self.flush(c)

    def flush(self, c):
        try:
            while c.out:
                n = c.sock.send(c.out)
                if not n:
                    break
                del c.out[:n]
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            self.drop(c)
            return
        if c.to is None:
            self.watch(c, selectors.EVENT_READ | (selectors.EVENT_WRITE if c.out else 0))

    def on_conn(self, c, mask):
        if c not in self.conns:
            return
        if c.to is not None:  # a connection to a host being made: made, or not
            self.connected(c)
            return
        if mask & selectors.EVENT_WRITE:
            self.flush(c)
        if mask & selectors.EVENT_READ and c in self.conns:
            try:
                data = c.sock.recv(65536)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                data = b""
            if not data:
                self.drop(c)
                return
            c.buf += data
            while c in self.conns:
                i = c.buf.find(b"\n")
                if i < 0:
                    break
                raw = bytes(c.buf[:i])
                del c.buf[:i + 1]
                try:
                    m = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue
                if isinstance(m, dict):
                    if self.role == "host":
                        self.host_line(c, m)
                    else:
                        self.join_line(c, m)
            if len(c.buf) > NET_LINE_MAX:
                self.drop(c)

    def drop(self, c):
        if c not in self.conns:
            return
        self.conns.remove(c)
        try:
            self.sel.unregister(c.sock)
        except (KeyError, ValueError, OSError):
            pass
        try:
            c.sock.close()
        except OSError:
            pass
        if self.role == "host":
            if c.id in self.players:
                name = self.players.pop(c.id)
                self.last_pos.pop(c.id, None)
                out = {"t": "left", "id": c.id, "name": name}
                self.to_all(out)
                self.post(out)
        elif c is self.conn:
            self.conn = None
            if self.joined:
                self.joined = False
                self.post({"t": "lost", "why": "end" if c.ended else "lost"})
                self.stopping = True
            else:
                self.failed("closed", c)

    # ---- the host
    def start_host(self):
        self.listener.setblocking(False)
        self.port = self.listener.getsockname()[1]
        self.sel.register(self.listener, selectors.EVENT_READ, self.on_accept)
        for off in NET_FIND_PORTS:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                u.bind(("127.0.0.1" if self.local else "", self.base + off))
            except OSError:  # another host on this computer has it
                u.close()
                continue
            u.setblocking(False)
            self.udp = u
            self.sel.register(u, selectors.EVENT_READ, self.on_find)
            break
        # (with every port taken, games can still join by this computer's address)
        ips = [] if self.local else local_ips()
        self.post({"t": "hosting", "port": self.port, "ips": ips, "findable": self.udp is not None})

    def on_accept(self, mask):
        while True:
            try:
                sock, _ = self.listener.accept()
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            self.add(sock)

    def on_find(self, mask):
        while True:
            try:
                data, addr = self.udp.recvfrom(2048)
            except (BlockingIOError, InterruptedError):
                return
            except ConnectionResetError:  # Windows: an answer earlier didn't arrive (the asker has gone)
                continue
            except OSError:
                return
            try:
                m = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("tuff") == "find":
                reply = {"tuff": "room", "v": NET_VERSION, "room": self.room, "game": self.title, "port": self.port,
                         "players": len(self.players), "host": self.players.get(1)}
                try:
                    self.udp.sendto(json.dumps(reply, ensure_ascii=False).encode("utf-8"), addr)
                except OSError:
                    pass

    def to_all(self, obj, but=None):
        for c in list(self.conns):
            if c.id is not None and c is not but:
                self.write(c, obj)

    def unique(self, name, pid):
        name = " ".join(str(name).split())[:NET_NAME_MAX] or f"Player {pid}"
        taken = {n.lower() for i, n in self.players.items() if i != pid}
        if name.lower() not in taken:
            return name
        n = 2
        while f"{name} {n}".lower() in taken:
            n += 1
        return f"{name} {n}"

    def host_line(self, c, m):
        t = m.get("t")
        if c.id is None:
            if t == "hello":
                self.welcome(c, m)
            return
        if t == "msg":
            out = {"t": "msg", "from": c.id, "m": m.get("m"), "v": m.get("v")}
            self.to_all(out, but=c)
            self.post(out)
        elif t == "pos":
            out = {"t": "pos", "id": c.id, "p": m.get("p")}
            self.last_pos[c.id] = out["p"]
            self.to_all(out, but=c)
            self.post(out)
        elif t == "share" and isinstance(m.get("k"), str):
            self.shared[m["k"]] = m.get("v")
            out = {"t": "shared", "k": m["k"], "v": m.get("v"), "by": c.id}
            self.to_all(out)
            self.post(out)
        elif t == "name":
            self.rename(c.id, m.get("name"))

    def welcome(self, c, m):
        if len(self.players) >= NET_MAX_PLAYERS:
            c.out += self.line({"t": "full"})
            self.flush(c)
            self.drop(c)
            return
        c.id = self.next_id
        self.next_id += 1
        name = self.unique(m.get("name") or f"Player {c.id}", c.id)
        self.players[c.id] = name
        self.write(c, {"t": "welcome", "id": c.id, "name": name, "room": self.room, "game": self.title,
                       "players": [[i, n] for i, n in self.players.items()], "shared": self.shared,
                       "pos": {str(i): p for i, p in self.last_pos.items()}})
        out = {"t": "joined", "id": c.id, "name": name}
        self.to_all(out, but=c)
        self.post(out)

    def rename(self, pid, name):
        if pid not in self.players or not isinstance(name, str):
            return
        name = self.unique(name, pid)
        self.players[pid] = name
        out = {"t": "renamed", "id": pid, "name": name}
        self.to_all(out)
        self.post(out)

    def host_op(self, op):
        t = op.get("t")
        if t == "msg":
            self.to_all({"t": "msg", "from": 1, "m": op.get("m"), "v": op.get("v")})
        elif t == "pos":
            self.last_pos[1] = op.get("p")
            self.to_all({"t": "pos", "id": 1, "p": op.get("p")})
        elif t == "share":
            self.shared[op["k"]] = op.get("v")
            out = {"t": "shared", "k": op["k"], "v": op.get("v"), "by": 1}
            self.to_all(out)
            self.post(out)
        elif t == "name":
            self.rename(1, op.get("name"))

    # ---- a joining game
    def start_join(self):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        u.bind(("127.0.0.1" if self.local else "", 0))
        u.setblocking(False)
        self.udp = u
        self.sel.register(u, selectors.EVENT_READ, self.on_rooms)
        if self.address is not None:
            ip, port = self.address
            self.targets = [ip]
            if port is not None:  # the whole address: straight there
                self.connect((ip, port))
                return
        elif self.local:
            self.targets = ["127.0.0.1"]
        else:
            nets = {ip.rsplit(".", 1)[0] + ".255" for ip in local_ips()}  # each network's own broadcast (a /24 guess)
            self.targets = ["255.255.255.255", *sorted(nets), "127.0.0.1"]
        self.post({"t": "looking"})

    def ask(self):
        self.asks += 1
        ask = json.dumps({"tuff": "find", "v": NET_VERSION}).encode("utf-8")
        for ip in self.targets:
            for off in NET_FIND_PORTS:
                try:
                    self.udp.sendto(ask, (ip, self.base + off))
                except OSError:  # that network isn't there (or a broadcast isn't allowed): the others still go
                    pass
        if self.address is not None and self.conn is None and (self.address[1] is not None or self.asks % 3 == 0):
            # No answer from that computer yet: its firewall may only let the game itself in. Try the game's port.
            self.connect((self.address[0], self.address[1] or self.base + 1))

    def on_rooms(self, mask):
        while True:
            try:
                data, addr = self.udp.recvfrom(4096)
            except (BlockingIOError, InterruptedError):
                return
            except ConnectionResetError:
                continue
            except OSError:
                return
            try:
                m = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            if not isinstance(m, dict) or m.get("tuff") != "room" or not isinstance(m.get("port"), int):
                continue
            key = (addr[0], m["port"])
            if self.bad.get(key, 0) > time.monotonic() or self.conn is not None:
                continue
            if self.room is not None and not same_room(m.get("room", ""), self.room):
                continue
            self.found[key] = m
            if self.first_found is None:
                self.first_found = time.monotonic()

    def pick(self):
        """The room to go in, of those that answered: one for the same game first (another game's room is still a
        room), then the one with fewest players."""
        rooms = sorted(self.found.items(), key=lambda kv: (not same_room(kv[1].get("game", ""), self.title),
                                                           kv[1].get("players", 0), kv[0][0] != "127.0.0.1"))
        self.found, self.first_found = {}, None
        if rooms:
            self.connect(rooms[0][0])

    def connect(self, key):
        if self.conn is not None:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)  # a computer that doesn't answer mustn't hold up the thread (tick gives up on it)
        try:
            err = s.connect_ex(key)
        except OSError as exc:
            err = exc.errno or -1
        if err not in (0, *_WOULD_BLOCK):
            s.close()
            self.bad[key] = time.monotonic() + 2
            return
        self.conn = self.add(s, to=time.monotonic() + 3)
        self.conn.key = key
        self.post({"t": "connecting", "to": key[0]})

    def connected(self, c):
        try:
            err = c.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        except OSError as exc:
            err = exc.errno or -1
        if err:
            self.failed("refused", c)
            return
        try:
            c.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        c.to = None
        self.hello_by = time.monotonic() + 5
        self.watch(c, selectors.EVENT_READ)
        self.write(c, {"t": "hello", "v": NET_VERSION, "name": self.my_name, "game": self.title})

    def failed(self, why, c=None):
        """A room that didn't let us in (it's gone, it's full, it answered too slowly): look again."""
        c = c or self.conn
        if c is not None:
            if c.key is not None:
                self.bad[c.key] = time.monotonic() + 3
            self.conn = None
            if c in self.conns:
                self.drop(c)
        self.conn = None
        self.next_ask = 0.0
        self.post({"t": "looking", "why": why})

    def join_line(self, c, m):
        t = m.get("t")
        if t == "welcome" and not self.joined:
            self.joined = True
            self.post(m)
            for op in self.waiting:
                self.write(c, op)
            self.waiting.clear()
        elif t == "full":
            self.post({"t": "refused", "why": "full"})
            self.stopping = True
        elif t == "end":
            c.ended = True
        elif self.joined:
            self.post(m)


class Net:
    """A game's multiplayer (game:host, game:join and the rest), on the Tuff thread: who's in the room, the shared
    values, the other players' people in a 3D world, and the functions that run when something happens. NetLink
    does the talking. A message on the HUD says what's going on (hosting, looking, who came and went)."""

    def __init__(self, game):
        self.game, self.rt = game, game.rt
        self.link = None
        self.role = None  # "host" or "join", while the game is in a room or looking for one
        self.state = "off"  # "off", "looking" (or "connecting") and "in"
        self.me = 1
        self.own_name = None  # what the program called its player (game:my_name)
        self.room = None
        self.players = {}  # player number -> name, everyone in the room, this game too
        self.values = {}  # the shared values as this game sees them: the room's, and its own changes on their way
        self.pending = collections.Counter()  # this game's changes the host hasn't sent back yet, by name
        self.early = set()  # names shared before the game was in its room: they fill in what the room doesn't have
        self.people = {}  # player number -> their person (a 3D world)
        self.msg_fns, self.join_fns, self.leave_fns = [], [], []
        self.sent, self.sent_at = None, 0.0
        self.pill, self.pill_text, self.pill_until = (None, None), None, None
        self.said = collections.deque(maxlen=12)  # what the HUD said lately (for the autopilot's reports)
        self.address = None  # the host's address, for the pill
        atexit.register(self.stop)

    # ---- helpers
    @property
    def off(self):
        return SCENE is not None or os.environ.get("TUFF_SCENE") == "1"

    def what(self, method):
        return f"{self.game.KIND}:{method}"

    def name(self):
        return self.players.get(self.me) or self.own_name or "Player 1"

    def text_input(self, v, method, example, what="name"):
        t = self.rt.plain(v)
        if not isinstance(t, str):
            raise self.rt.error(f"{self.what(method)} needs the {what} as text, like {example}, not {self.rt.what(t)}.")
        return t

    def title(self):
        saves = getattr(self.game, "save_file", None)
        return saves.title if saves is not None else self.game.view.title

    def busy(self, method):
        if self.role == "host":
            raise self.rt.error(f"This game is hosting \"{self.room}\" already. Use {self.what('leave')}() first to "
                                f"{'host another room' if method == 'host' else 'join another game'}.")
        if self.role == "join":
            raise self.rt.error(f"This game is {'in a room' if self.state == 'in' else 'looking for a room'} already. "
                                f"Use {self.what('leave')}() first to {'host one' if method == 'host' else 'join another'}.")

    def fire(self, fns, *args):
        for fn in list(fns):
            self.game.fire(fn, *args)
            if self.game.closed:
                return

    # ---- game:host, game:join, game:leave
    def host(self, room=MISSING):
        g = self.game
        title = self.title()
        if room is MISSING or room is None:
            room = title
        room = " ".join(self.text_input(room, "host", f'{self.what("host")}("{title}")', "room's name").split())
        if not room:
            raise self.rt.error(f"A room needs a name, like {self.what('host')}(\"{title}\").")
        self.busy("host")
        if self.off:
            return None
        listener = self.listen()
        self.role, self.state, self.room, self.me = "host", "in", room, 1
        self.players = {1: self.own_name or "Player 1"}
        self.pending.clear()
        self.early.clear()
        self.link = NetLink("host", title, self.players[1], room=room, listener=listener, shared=self.values)
        self.link.start()
        self.dress_player()
        self.say(f"Hosting \"{room}\"", None)
        return None

    def listen(self):
        """The host's TCP socket, made here so game:hosting() is true from the line after game:host. The first free
        port after the one rooms are found on."""
        bind = "127.0.0.1" if net_local() else ""
        base = net_base_port()
        last = None
        for port in [*range(base + 1, base + 10), 0]:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: never share a port another game has
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                else:  # elsewhere this only lets a port be used again right after a game closed
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((bind, port))
                s.listen(16)
                return s
            except OSError as exc:
                last = exc
                s.close()
        raise self.rt.error(f"This computer wouldn't let the game host a room ({getattr(last, 'strerror', None) or last}).")

    def join(self, where=MISSING):
        title = self.title()
        room = address = None
        if where is not MISSING and where is not None:
            text = self.text_input(where, "join", f'{self.what("join")}("192.168.1.20") or {self.what("join")}("{title}")',
                                   "room's name or the host's address")
            address = net_address(text)
            if address is None:
                room = " ".join(text.split())
                if not room:
                    raise self.rt.error(f"{self.what('join')}() finds any room, and {self.what('join')}(\"{title}\") the room "
                                        "called that. Give it a name, or nothing.")
        self.busy("join")
        if self.off:
            return None
        self.role, self.state, self.room, self.address = "join", "looking", room, address
        self.players = {}
        self.pending.clear()
        self.early = set(self.values)
        self.link = NetLink("join", title, self.own_name, room=room, address=address)
        self.link.start()
        self.say(f"Looking for \"{room}\"..." if room else f"Looking for {address[0]}..." if address else
                 "Looking for a game to join...", None)
        return None

    def leave(self):
        if self.link is None and self.role is None:
            return None
        self.stop()
        was = self.role
        self.gone_all()
        self.role, self.state, self.link = None, "off", None
        self.say("You left the game" if was == "join" else "The room is closed", 2.5)
        return None

    def stop(self):
        link = self.link
        if link is not None:
            link.stop()
            if link.is_alive() and link is not threading.current_thread():
                link.join(0.5)  # a host says goodbye to everyone before the window closes

    def gone_all(self):
        """Everyone else has gone (this game left, or the room closed): their people go, and on_leave runs for each."""
        others = [(i, n) for i, n in sorted(self.players.items()) if i != self.me]
        for pid in list(self.people):
            self.remove_person(pid)
        self.players = {self.me: self.name()} if self.players else {}
        for _, n in others:
            self.fire(self.leave_fns, n)

    # ---- what the program asks
    def connected(self):
        return self.state == "in"

    def hosting(self):
        return self.role == "host" and self.state == "in"

    def player_names(self):
        if not self.players:
            return [self.name()]
        return [n for _, n in sorted(self.players.items())]

    def my_name(self, name=MISSING):
        if name is MISSING or name is None:
            return self.name()
        n = " ".join(self.text_input(name, "my_name", f'{self.what("my_name")}("Sam")').split())
        if not n:
            raise self.rt.error(f"Your name can't be empty: {self.what('my_name')}(\"Sam\")")
        if len(n) > NET_NAME_MAX:
            raise self.rt.error(f"Names can be up to {NET_NAME_MAX} letters long, so they fit over a player's head. "
                                f"\"{n[:NET_NAME_MAX]}\" would fit.")
        self.own_name = n
        if self.link is not None:
            self.link.say({"t": "name", "name": n})
        if self.players:
            self.players[self.me] = n
        return n

    def send(self, message, value=None):
        m = self.text_input(message, "send", f'{self.what("send")}("hello") or {self.what("send")}("score", 10)', "message")
        v = self.game.saves().keepable(value, method="send")
        if self.link is None or self.off:
            return None  # not in a room: there's nobody to send it to
        self.link.say({"t": "msg", "m": m, "v": v})
        return None

    def share(self, name, value):
        k = self.text_input(name, "share", f'{self.what("share")}("coins", 5)')
        if not k.strip():
            raise self.rt.error(f"A shared value needs a name, like {self.what('share')}(\"coins\", 5).")
        v = self.game.saves().keepable(value, method="share")
        self.values[k] = v
        if self.link is not None and self.state == "in":
            self.pending[k] += 1
            self.link.say({"t": "share", "k": k, "v": v})
        elif self.role == "join":
            self.early.add(k)  # the room's own value wins when the game gets in (this one fills in if it has none)
        return None

    def shared(self, name, default=None):
        k = self.text_input(name, "shared", f'coins = {self.what("shared")}("coins", 0)')
        return tuff_value(self.values[k]) if k in self.values else default  # a table comes as a dictionary, like a save's

    def on(self, fns, fn, method):
        fns.append(self.game.lib.check_fn(fn, f":{method}"))
        return None

    def others(self):
        return [t.native for pid, t in sorted(self.people.items()) if t.alive and pid in self.players]

    # ---- every frame
    def frame(self, real):
        link = self.link
        if link is not None:
            for _ in range(2000):
                try:
                    e = link.inbox.get_nowait()
                except queue.Empty:
                    break
                self.event(e)
                if self.game.closed or self.link is not link:
                    break
        if self.link is not None and self.state == "in":
            self.send_spot()
        if self.people:
            self.move_people(real)
        if self.pill_until is not None and time.monotonic() >= self.pill_until:
            self.say(None)

    def event(self, e):
        t = e.get("t")
        if t == "hosting":
            ips = e.get("ips") or []
            self.address = ips[0] if ips else None
            where = f" on {self.address}" if self.address else " on this computer"
            self.say(f"Hosting \"{self.room}\"{where}", 6)
        elif t == "looking" and self.state == "connecting":
            self.state = "looking"
        elif t == "connecting":
            self.state = "connecting"
        elif t == "welcome":
            self.welcome(e)
        elif t == "joined":
            pid, name = e.get("id"), str(e.get("name"))
            self.players[pid] = name
            self.say(f"{name} joined", 2.5)
            self.fire(self.join_fns, name)
        elif t == "left":
            pid = e.get("id")
            name = self.players.pop(pid, None) or str(e.get("name"))
            self.remove_person(pid)
            self.say(f"{name} left", 2.5)
            self.fire(self.leave_fns, name)
        elif t == "renamed":
            pid, name = e.get("id"), str(e.get("name"))
            if pid in self.players:
                self.players[pid] = name
            if pid == self.me:
                self.own_name = name
            person = self.people.get(pid)
            if person is not None and person.alive:
                person.data["name"] = name
                person.label(name)
        elif t == "msg":
            sender = self.players.get(e.get("from"), "Someone")
            self.fire(self.msg_fns, e.get("m"), tuff_value(e.get("v")), sender)
        elif t == "pos":
            if e.get("id") != self.me:
                self.place(e.get("id"), e.get("p"))
        elif t == "shared":
            k, by = e.get("k"), e.get("by")
            if by == self.me and self.pending[k] > 0:
                self.pending[k] -= 1
            if self.pending[k] <= 0:
                self.pending.pop(k, None)
                self.values[k] = e.get("v")
        elif t == "lost":
            self.state = "off"
            self.gone_all()
            self.role, self.link = None, None
            self.say("The host left the game" if e.get("why") == "end" else "Lost the connection to the game", 4)
        elif t == "refused":
            self.role, self.state, self.link = None, "off", None
            self.say("That game is full", 4)
        elif t == "error":
            self.role, self.state, self.link = None, "off", None
            self.say("Multiplayer stopped working", 4)
            self.game.engine_error(self.rt.error(f"Multiplayer stopped working: {e.get('why')}"), "multiplayer")

    def welcome(self, e):
        self.state, self.me, self.room = "in", e.get("id"), e.get("room")
        self.players = {int(i): str(n) for i, n in e.get("players", [])}
        shared = e.get("shared") or {}
        mine = {k: self.values[k] for k in self.early if k in self.values and k not in shared}
        self.values = {**shared, **mine}
        self.early.clear()
        for k, v in mine.items():  # what this game shared before it got in, that the room didn't have yet
            self.pending[k] += 1
            self.link.say({"t": "share", "k": k, "v": v})
        self.sent = None  # where the player is goes out at once
        for pid, p in (e.get("pos") or {}).items():
            if int(pid) != self.me:
                self.place(int(pid), p)
        self.dress_player()
        self.say(f"Joined \"{self.room}\"", 3)
        for pid, name in sorted(self.players.items()):
            if pid != self.me:
                self.fire(self.join_fns, name)

    # ---- people (a 3D world)
    def send_spot(self):
        g = self.game
        p = getattr(g, "the_player", None)
        if p is None:
            return
        now = time.monotonic()
        if now - self.sent_at < NET_SEND_EVERY:
            return
        hidden = p.hidden or getattr(g, "driving", None) is not None  # in a car (cars aren't shared): not walking about
        spot = [round(p.x, 3), round(p.y, 3), round(p.z, 3), round(p.heading, 1), 0 if hidden else 1]
        if spot == self.sent and now - self.sent_at < 1.0:
            return
        self.sent, self.sent_at = spot, now
        self.link.say({"t": "pos", "p": spot})

    def dress_player(self):
        """The player's own figure (third person) wears the shirt the others see it in."""
        body = getattr(getattr(self.game, "the_player", None), "body", None)
        if body is not None and body.alive:
            c = NET_SHIRTS[(self.me - 1) % len(NET_SHIRTS)]
            if body.look is not None:  # it stays that colour when the program changes its look
                body.look["shirt"] = c
            for node, main in body.parts:
                if main:
                    body.send(node, color=c)

    def place(self, pid, p):
        g = self.game
        if not g.three_d or not isinstance(pid, int) or not isinstance(p, list) or len(p) < 4:
            return
        try:
            spot = [float(v) for v in p[:4]] + [bool(p[4]) if len(p) > 4 else True]
        except (TypeError, ValueError):
            return
        person = self.people.get(pid)
        if person is None or not person.alive:
            person = self.people[pid] = self.make_person(pid, spot)
        person.net_to = spot

    def make_person(self, pid, spot):
        g = self.game
        pick = random.Random(pid * 7919 + 17).choice  # the same person on every screen
        parts = [(t, {**p, "shadow": True}, main) for t, p, main in person_parts(
            NET_SHIRTS[(pid - 1) % len(NET_SHIRTS)], pick(SKINS), pick(HAIRS), pick(PANTS), pick(HAIR_STYLES),
            pick(("long", "long", "rolled")), pick(SHOES))]
        x, y, z, heading, shown = spot
        t = Thing(g, "person", x, y, z, (0.7, 1.75, 0.5), parts)
        g.things.pop(t, None)  # tgame's own, like the player's figure: game:clear leaves the other players
        t.solid_ = False  # walk through each other (touches still sees them)
        t.heading = heading % 360
        t.push_rotation()
        name = self.players.get(pid, f"Player {pid}")
        t.data["name"] = name
        t.label(name)
        t.net_shown = True
        if not shown:
            t.hide()
            t.net_shown = False
        return t

    def remove_person(self, pid):
        t = self.people.pop(pid, None)
        if t is not None and t.alive:
            t.remove()

    def move_people(self, real):
        """Each other player's person goes smoothly to where they last were (a few frames behind: they're heard 20
        times a second), and straight there when that's far (they jumped onto a pad, or moved to a new spot)."""
        k = 1 - math.exp(-14 * real) if real else 1.0
        for pid, t in list(self.people.items()):
            if not t.alive:
                del self.people[pid]  # the program removed them: they come back with their next move
                continue
            x, y, z, heading, shown = t.net_to
            if shown != t.net_shown:
                t.net_shown = shown
                t.show() if shown else t.hide()
            far = math.dist((t.x, t.y, t.z), (x, y, z)) > 8
            if (x, y, z) != (t.x, t.y, t.z):
                if far or abs(x - t.x) + abs(y - t.y) + abs(z - t.z) < 0.002:
                    t.x, t.y, t.z = x, y, z
                else:
                    t.x += (x - t.x) * k
                    t.y += (y - t.y) * k
                    t.z += (z - t.z) * k
                t.push()
            turn = ((heading - t.heading + 180) % 360) - 180
            if turn:
                t.heading = heading % 360 if far or abs(turn) < 0.2 else (t.heading + turn * k) % 360
                t.push_rotation()

    # ---- the message on the HUD
    def say(self, words, seconds=3.0):
        """A line on a dark pill at the top of the window, for `seconds` (None: until the next one). None hides it."""
        if self.off:
            return
        g = self.game
        box, text = self.pill
        self.pill_text = words
        self.pill_until = None if words is None or seconds is None else time.monotonic() + seconds
        if words is None:
            for s in (box, text):
                if s is not None and s.alive:
                    s.hide()
            return
        self.said.append(words)
        size = 16
        w, h = len(words) * size * 0.56 + 30, size + 16
        if box is None or not box.alive:
            hud = g.hud()
            box = hud.make("rect", g.W / 2, 30, {"w": w, "h": h, "radius": h / 2, "color": "#11141a", "alpha": 0.62,
                                                 "z": 5e5 + 1}, own=False)
            text = hud.make("text", g.W / 2, 30, {"text": words, "size": size, "bold": True, "color": "#ffffff",
                                                  "ax": 0.5, "ay": 0.5, "z": 5e5 + 2}, own=False)
        else:
            box.w = w
            box.send(w=w, visible=True)
            text.words = words
            text.send(text=words, visible=True)
            box.hidden = text.hidden = False
        self.pill = (box, text)

    def state_dump(self):
        """For the autopilot's reports."""
        return {"state": self.state, "role": self.role, "me": self.me, "name": self.name(), "room": self.room,
                "players": self.player_names(), "shared": dict(self.values), "pending": dict(self.pending),
                "message": self.pill_text, "said": list(self.said),
                "others": [[t.data.get("name"), round(t.x, 2), round(t.y, 2), round(t.z, 2), round(t.heading, 1),
                            not t.hidden] for _, t in sorted(self.people.items()) if t.alive]}


class GameNet:
    """What every game window and world gets for multiplayer (Game takes these methods, just below; world:others
    is a 3D world's)."""
    NAMES = [("host", "net_host"), ("join", "net_join"), ("leave", "net_leave"), ("connected", "net_connected"),
             ("hosting", "net_hosting"), ("players", "net_players"), ("my_name", "net_my_name"), ("send", "net_send"),
             ("on_message", "on_message"), ("on_join", "on_join"), ("on_leave", "on_leave"), ("share", "net_share"),
             ("shared", "net_shared")]

    def network(self):
        if getattr(self, "net", None) is None:
            self.net = Net(self)
        return self.net

    def net_host(self, name=MISSING):
        return self.network().host(name)

    def net_join(self, where=MISSING):
        return self.network().join(where)

    def net_leave(self):
        return self.network().leave()

    def net_connected(self):
        return self.network().connected()

    def net_hosting(self):
        return self.network().hosting()

    def net_players(self):
        return self.network().player_names()

    def net_my_name(self, name=MISSING):
        return self.network().my_name(name)

    def net_send(self, message, value=None):
        return self.network().send(message, value)

    def on_message(self, fn):
        net = self.network()
        return net.on(net.msg_fns, fn, "on_message")

    def on_join(self, fn):
        net = self.network()
        return net.on(net.join_fns, fn, "on_join")

    def on_leave(self, fn):
        net = self.network()
        return net.on(net.leave_fns, fn, "on_leave")

    def net_share(self, name, value):
        return self.network().share(name, value)

    def net_shared(self, name, default=None):
        return self.network().shared(name, default)

    def net_others(self):
        return self.network().others()


for _attr in ("network", "net_others", *(attr for _, attr in GameNet.NAMES)):
    setattr(Game, _attr, getattr(GameNet, _attr))
Game2D.NAMES = Game2D.NAMES + GameNet.NAMES
World3D.NAMES = World3D.NAMES + GameNet.NAMES + [("others", "net_others")]
HINTS["game"].update({k: v for k, v in NET_HINTS.items() if v != "others" and k not in HINTS["game"]})
HINTS["world"].update({k: v for k, v in NET_HINTS.items() if k not in HINTS["world"]})
NEEDS_3D["others"] = ("The other players are people in a 3D world. Make the game with tgame.world(...) and give it a "
                      "player, or in 2D use game:players() for their names and game:on_message to hear where they are.")
for _kind in ("game", "world"):
    GIVES[_kind].update({"connected": "$bool", "hosting": "$bool", "players": "$list", "my_name": "$text"})
    HANDLERS[_kind].update({"on_message": (0, 3, "3 inputs (the message, the value sent with it and who sent it)"),
                            "on_join": (0, 1, "1 input (the name of the player who joined)"),
                            "on_leave": (0, 1, "1 input (the name of the player who left)")})
GIVES["world"]["others"] = "$list"
