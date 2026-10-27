"""tterm: terminal games for Tuff (1.5.0). A screen is a grid of letters the program draws on, and keys are read as
they're pressed, with no Enter: Snake, roguelikes, a text adventure with a map.

    mention tterm
    screen = tterm.screen(40, 20)
    x = 20
    func step(dt):
        if screen:held("right"):
            x += 1
        screen:clear()
        screen:put(x, 10, "@", "lime")
    screen:every_frame(step)        # step(dt) about 20 times a second, until screen:stop() or Esc

x goes right from 0 and y goes down from 0. Colours are Tuff's colour names (or "#rrggbb"). Where it runs:
- TuffCode's Run panel (TUFF_IDE=1): the screen is a say line whose look has "screen": 1, rewritten as it changes
  (ide.js and tterm.js draw it). Click it to play: its keys come back over stdin as lines like
  "\\x1b]tuff;key;down;left\\x07" (up when let go, none for all of them), among the answers to input(), and are read
  without waiting.
- A real terminal and a Build exe console app: ANSI colours at the top of the terminal, and the keys read straight
  from it (Windows' console input, or termios on a Mac and Linux). It's always put back after an error or Ctrl+C.
- Anywhere no one can press a key (a pipe or a file, an AI agent's tuff_run, tests): frames don't wait for the
  clock (each is 0.05 seconds of game time), screen:press("right") gives a frame its key, and screen:every_frame stops
  by itself 100 frames after the last key (or after 5000). Only how the screen ends is shown, as plain text.
"""
import atexit
import difflib
import json
import math
import os
import re
import shutil
import sys
import time
import unicodedata

FPS = 20
STEP = 1 / FPS
IDLE_FRAMES = 100  # with no one to press keys: frames it runs after the last key from screen:press (5 s of game time)
MOST_FRAMES = 5000  # ...and at most, so a run always ends
LONGEST_STEP = 0.5  # dt after a long pause (a slow frame, a breakpoint) is at most this
MOST_WIDTH, MOST_HEIGHT = 200, 100
# A screen's methods (the checker knows them from here too), where each one's colour goes, and what they give back.
SCREEN_METHODS = ("put", "text", "box", "clear", "get", "pressed", "held", "press", "every_frame", "stop")
COLOR_AT = {"put": 3, "text": 3, "box": 4}
GIVES = {"get": "$text", "pressed": "$bool", "held": "$bool"}
NAMED_KEYS = ("space", "enter", "escape", "tab", "backspace", "delete", "up", "down", "left", "right")
KEY_ALIASES = {" ": "space", "spacebar": "space", "space bar": "space", "esc": "escape", "return": "enter", "del": "delete",
               "arrowup": "up", "arrowdown": "down", "arrowleft": "left", "arrowright": "right", "arrow up": "up",
               "arrow down": "down", "arrow left": "left", "arrow right": "right", "up arrow": "up", "down arrow": "down",
               "left arrow": "left", "right arrow": "right"}
# Keys a terminal never tells a program about on their own.
NOT_KEYS = ("shift", "ctrl", "control", "alt", "option", "cmd", "command", "meta", "windows", "caps lock", "capslock",
            "mouse", "click", "left mouse", "right mouse")
BOX = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "across": "─", "down": "│"}
KEY_LINE = re.compile(r"\x1b\]tuff;key;(down|up|none)(?:;(.*))?\x07")  # what the Run panel sends for a key
PRESS_ANY = 'screen:press needs a real key, like screen:press("space") or screen:press("right").'
FRAME_FN = "screen:every_frame needs a function's name, like screen:every_frame(step), without brackets. It runs step(dt) about 20 times a second."


# ---------------------------------------------------------------- the checks the checker shares

def tuff_of(rt):
    """tuff.py (__main__ when it's run directly, tuff in a built app)."""
    return sys.modules.get(type(rt).__module__)


def key_name(word):
    """tterm's name for a key ("space", "a", "up", "any"...), or None if it isn't one."""
    t = " ".join(str(word).strip().lower().split()) if str(word).strip() else str(word)
    t = KEY_ALIASES.get(t, t)
    if t in NAMED_KEYS or t == "any" or (len(t) == 1 and t.isprintable() and not t.isspace()):
        return t
    return None


def key_problem(word, what):
    """Why this isn't a key tterm knows, or None when it is."""
    if key_name(word):
        return None
    low = " ".join(str(word).lower().split())
    if low in NOT_KEYS:
        return f'{what}("{word}"): a terminal doesn\'t tell a program about {low} on its own, so tterm can\'t either. Use a letter, a number, space, enter or the arrow keys.'
    hint = difflib.get_close_matches(low, NAMED_KEYS, n=1, cutoff=0.6)
    tip = f' Did you mean "{hint[0]}"?' if hint else ""
    return f'{what}: "{word}" isn\'t a key tterm knows.{tip} Keys: a letter, a number, space, enter, escape, tab, backspace, delete, up, down, left, right or "any".'


def color_problem(word, what, colors):
    """Why this isn't a colour, or None when it is."""
    v = " ".join(str(word).strip().lower().split())
    if v in colors or re.fullmatch(r"#(?:[0-9a-f]{3}|[0-9a-f]{6})", v):
        return None
    hint = difflib.get_close_matches(v, list(colors), n=1, cutoff=0.6)
    tip = f' Did you mean "{hint[0]}"?' if hint else ""
    return f'{what} doesn\'t know the colour "{word}".{tip} Try red, gold, lime, sky, pink, gray or a code like "#ff8800".'


def size_problem(value, what, most):
    """tterm.screen's width or height, when it can't be one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not 1 <= value <= most:
        return f"tterm.screen's {what} goes from 1 to {most}, like tterm.screen(40, 20)."
    return None


def char_problem(text):
    """Why screen:put can't draw this, or None: it draws one character."""
    n = len(glyphs(text.replace("\n", " ")))
    if n == 1:
        return None
    if not n:
        return 'screen:put needs a character to draw, like "@" (a space, " ", rubs a cell out).'
    return 'screen:put draws one character, like screen:put(x, y, "@"). For words, use screen:text(x, y, "...").'


def glyphs(text):
    """Text cut into what a terminal shows in one place: a letter with its accents, an emoji with its joins and skin
    tones. Each is (text, columns): 2 for wide ones (most emoji, Chinese and Japanese), 1 for the rest. A control
    character shows as a space."""
    out = []
    for ch in text:
        if out and (unicodedata.combining(ch) or ch in "\ufe0e\ufe0f\u200d" or 0x1F3FB <= ord(ch) <= 0x1F3FF
                    or out[-1][0].endswith("\u200d")):
            g, n = out[-1]
            out[-1] = (g + ch, 2 if n == 2 or ch == "\ufe0f" else n)
            continue
        if unicodedata.category(ch) == "Cc":
            ch = " "
        out.append((ch, 2 if ord(ch) >= 0x1100 and unicodedata.east_asian_width(ch) in ("W", "F") else 1))
    return out


def columns(g):
    if len(g) == 1 and ord(g) < 0x1100:
        return 1
    return 2 if "\ufe0f" in g or any(unicodedata.east_asian_width(c) in ("W", "F") for c in g) else 1


def u16(text):
    """Its length in JavaScript (the Run panel's colour runs count in UTF-16)."""
    return len(text.encode("utf-16-le")) // 2


# ---------------------------------------------------------------- reading keys

class NoKeys:
    """Nowhere to read keys from (a pipe or a file, tuff_run): only screen:press gives frames keys."""
    gone = True

    def start(self):
        pass

    def poll(self):
        return []

    def stop(self):
        pass


_PEEK = None


def pipe_waiting(fd):
    """How many bytes wait in a pipe, without waiting (Windows), or None once it's closed or if it isn't a pipe."""
    global _PEEK
    import ctypes
    import msvcrt
    from ctypes import wintypes
    if _PEEK is None:
        _PEEK = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
        _PEEK.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPDWORD]
        _PEEK.restype = wintypes.BOOL
    n = wintypes.DWORD()
    try:
        handle = msvcrt.get_osfhandle(fd)
    except OSError:
        return None
    if not _PEEK(handle, None, 0, None, ctypes.byref(n), None):
        return None
    return n.value


class IdeKeys:
    """TuffCode's Run panel: keys come over stdin as lines, among the answers typed for input(). They're read as they
    come, without waiting (PeekNamedPipe on Windows, select elsewhere); the answers read with them wait in `lines`
    for input() (Console.readline). Once stdin closes (tuff_run gives its answers, then closes it) no key can come."""

    def __init__(self, console):
        self.console = console
        self.lines = []  # typed answers read with the keys, in order
        self.part = b""  # the start of a line still coming
        self.gone = False
        try:
            self.fd = sys.stdin.fileno()
        except (AttributeError, OSError, ValueError):
            self.fd, self.gone = None, True
        console.readline = self.readline
        self.poll()

    def start(self):
        pass

    def stop(self):
        pass

    def waiting(self):
        """The bytes waiting in stdin: b"" when none have come yet, None once it has closed."""
        if os.name == "nt":
            n = pipe_waiting(self.fd)
            if n is None:
                return None
            return os.read(self.fd, n) if n else b""
        import select
        if not select.select([self.fd], [], [], 0)[0]:
            return b""
        return os.read(self.fd, 4096) or None

    def poll(self):
        events = []
        while not self.gone:
            try:
                data = self.waiting()
            except (OSError, ValueError):
                data = None
            if data is None:
                self.gone = True
                break
            if not data:
                break
            self.part += data
            *whole, self.part = self.part.split(b"\n")
            for raw in whole:
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                m = KEY_LINE.fullmatch(line)
                if m is None:
                    self.lines.append(line + "\n")
                elif m.group(1) == "none":
                    events.append(("none", None))
                elif key_name(m.group(2) or ""):
                    events.append((m.group(1), key_name(m.group(2))))
        return events

    def readline(self):
        """input()'s answer: the ones read with the keys first. A key line that comes while input() waits (a key
        pressed just as the game ended) isn't an answer."""
        while True:
            if self.lines:
                line = self.lines.pop(0)
            elif self.part:
                line, self.part = self.part.decode("utf-8", errors="replace") + sys.stdin.readline(), b""
            else:
                line = sys.stdin.readline()
            if not KEY_LINE.match(line):
                return line


class Repeats:
    """A terminal only says when a key goes down, and again as it repeats while it's held: a key counts as held until
    a moment after it last came (long enough for the first repeat, which comes later than the rest)."""
    FIRST, AGAIN = 0.3, 0.15

    def __init__(self):
        self.until = {}

    def events(self, names, now):
        out = []
        for name in names:
            out.append(("down", name))
            self.until[name] = now + (self.AGAIN if name in self.until else self.FIRST)
        for name, t in list(self.until.items()):
            if t <= now:
                out.append(("up", name))
                del self.until[name]
        return out


TERM_ESCAPES = {"A": "up", "B": "down", "C": "right", "D": "left", "3~": "delete"}
TERM_CHARS = {"\r": "enter", "\n": "enter", "\t": "tab", "\x7f": "backspace", "\x08": "backspace", " ": "space"}


def term_keys(text):
    """The keys in what a Mac or Linux terminal sends: arrows come as ESC [ A and the like, Esc on its own."""
    names, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\x1b":
            m = re.match(r"\x1b[\[O]([0-9;]*)([A-Za-z~])", text[i:])
            if m:
                code = m.group(2) if m.group(2) != "~" else m.group(1).split(";")[0] + "~"
                if code in TERM_ESCAPES:
                    names.append(TERM_ESCAPES[code])
                i += m.end()
                continue
            if i + 1 < len(text) and text[i + 1].isprintable() and text[i + 1] not in "[O":
                i += 1  # Alt with a key (Option on a Mac): the key
                continue
            names.append("escape")
        elif c in TERM_CHARS:
            names.append(TERM_CHARS[c])
        elif c.isprintable():
            names.append(c.lower())
        i += 1
    return names


class TtyKeys:
    """A Mac or Linux terminal: no Enter needed and nothing echoed while the game runs (Ctrl+C still stops it), and
    put back as it was afterwards, after an error or Ctrl+C too."""
    gone = False

    def __init__(self, console):
        import codecs
        self.console = console
        self.fd = sys.stdin.fileno()
        self.old = None
        self.registered = False
        self.repeats = Repeats()
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def raw(self):
        import termios
        new = termios.tcgetattr(self.fd)
        new[3] &= ~(termios.ICANON | termios.ECHO)
        new[6][termios.VMIN], new[6][termios.VTIME] = 0, 0
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, new)  # (flushed: keys pressed before the game don't count)

    def start(self):
        import termios
        self.old = termios.tcgetattr(self.fd)
        if not self.registered:  # (stop puts it back first; this is for a way out that skips it)
            atexit.register(self.stop)
            self.registered = True
        self.raw()
        self.console.readline = self.readline
        self.console.write("\x1b[?25l")

    def poll(self):
        import select
        text = ""
        while select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, 1024)
            if not data:
                break
            text += self.decoder.decode(data)
        return self.repeats.events(term_keys(text), time.perf_counter())

    def readline(self):
        """input() while the game runs: the terminal works as usual for the answer."""
        import termios
        termios.tcsetattr(self.fd, termios.TCSANOW, self.old)
        self.console.write("\x1b[?25h")
        try:
            return sys.stdin.readline()
        finally:
            self.raw()
            self.console.write("\x1b[?25l")

    def stop(self):
        if self.old is None:
            return
        import termios
        try:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old)  # (flushed: the game's keys don't type later)
        except Exception:
            pass
        self.old = None
        self.console.readline = None
        self.console.write("\x1b[?25h")


# Windows' console: each key's down and up, read from the console's input as they come (in the old console window and
# in Windows Terminal).
VK_KEYS = {0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down", 0x20: "space", 0x0D: "enter", 0x1B: "escape",
           0x09: "tab", 0x08: "backspace", 0x2E: "delete"}
CTRL_ALT = 0x01 | 0x02 | 0x04 | 0x08  # right alt, left alt, right ctrl, left ctrl


def vk_key(vk, char):
    """tterm's name for a key from Windows' console: the arrows and the rest by their key code, letters by their key
    (Shift doesn't change them), and anything else by what it types."""
    if vk in VK_KEYS:
        return VK_KEYS[vk]
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x60 <= vk <= 0x69:  # the number pad
        return chr(vk - 0x30)
    if char and char.isprintable() and not char.isspace():
        return char.lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    return None


_RECORD = None


def console_record():
    """Windows' INPUT_RECORD (20 bytes): what kind of event, then a key's (KEY_EVENT_RECORD) or the focus's."""
    global _RECORD
    if _RECORD is None:
        import ctypes
        from ctypes import wintypes

        class KeyEvent(ctypes.Structure):
            _fields_ = [("down", wintypes.BOOL), ("repeats", wintypes.WORD), ("vk", wintypes.WORD), ("scan", wintypes.WORD),
                        ("char", wintypes.WCHAR), ("state", wintypes.DWORD)]

        class Event(ctypes.Union):
            _fields_ = [("key", KeyEvent), ("focus", wintypes.BOOL), ("room", ctypes.c_byte * 16)]

        class Record(ctypes.Structure):
            _fields_ = [("kind", wintypes.WORD), ("event", Event)]
        _RECORD = Record
    return _RECORD


class ConsoleKeys:
    gone = False

    def __init__(self, console):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.Record, self.console = ctypes, console_record(), console
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32 = k32
        k32.GetStdHandle.restype = wintypes.HANDLE
        k32.GetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
        k32.GetNumberOfConsoleInputEvents.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
        k32.ReadConsoleInputW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.LPDWORD]
        k32.FlushConsoleInputBuffer.argtypes = [wintypes.HANDLE]
        self.handle = k32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        if not k32.GetConsoleMode(self.handle, ctypes.byref(wintypes.DWORD())):
            raise OSError("stdin isn't a console")
        self.names = {}  # key code -> the name its key went down with, for when it comes up
        self.dword = wintypes.DWORD

    def start(self):
        self.k32.FlushConsoleInputBuffer(self.handle)  # keys pressed before the game don't count
        self.console.readline = self.readline
        self.console.write("\x1b[?25l")

    def poll(self):
        events = []
        n = self.dword()
        while self.k32.GetNumberOfConsoleInputEvents(self.handle, self.ctypes.byref(n)) and n.value:
            records = (self.Record * min(n.value, 64))()
            got = self.dword()
            if not self.k32.ReadConsoleInputW(self.handle, self.ctypes.cast(records, self.ctypes.c_void_p), len(records),
                                              self.ctypes.byref(got)):
                break
            for rec in records[:got.value]:
                if rec.kind == 0x0010 and not rec.event.focus:  # the window lost the focus: every key comes up
                    self.names.clear()
                    events.append(("none", None))
                if rec.kind != 0x0001:  # KEY_EVENT
                    continue
                k = rec.event.key
                if k.down:
                    char = k.char if k.char and k.char.isprintable() else ""
                    if k.state & CTRL_ALT and not char:  # Ctrl+S and the like aren't the game's
                        continue
                    name = vk_key(k.vk, char)
                    if name:
                        self.names[k.vk] = name
                        events.append(("down", name))
                elif k.vk in self.names:
                    events.append(("up", self.names.pop(k.vk)))
        return events

    def readline(self):
        self.console.write("\x1b[?25h")
        try:
            return sys.stdin.readline()
        finally:
            self.console.write("\x1b[?25l")

    def stop(self):
        try:
            self.k32.FlushConsoleInputBuffer(self.handle)  # the game's keys don't type into what comes next
        except Exception:
            pass
        self.names.clear()
        self.console.readline = None
        self.console.write("\x1b[?25h")


MSVCRT_KEYS = {"H": "up", "P": "down", "K": "left", "M": "right", "S": "delete"}


class MsvcrtKeys:
    """Windows, when the console's own input can't be read: msvcrt's key presses (no ups, as in a Mac terminal)."""
    gone = False

    def __init__(self, console):
        self.console = console
        self.repeats = Repeats()

    def start(self):
        self.poll()
        self.console.readline = self.readline
        self.console.write("\x1b[?25l")

    def readline(self):
        self.console.write("\x1b[?25h")
        try:
            return sys.stdin.readline()
        finally:
            self.console.write("\x1b[?25l")

    def poll(self):
        import msvcrt
        names = []
        while msvcrt.kbhit():
            c = msvcrt.getwch()
            if c in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                if code in MSVCRT_KEYS:
                    names.append(MSVCRT_KEYS[code])
            elif c == "\x1b":
                names.append("escape")
            elif c in TERM_CHARS:
                names.append(TERM_CHARS[c])
            elif c.isprintable():
                names.append(c.lower())
        return self.repeats.events(names, time.perf_counter())

    def stop(self):
        try:
            self.poll()  # the game's keys don't type into what comes next
        except Exception:
            pass
        self.console.readline = None
        self.console.write("\x1b[?25h")


# ---------------------------------------------------------------- the library

class Lib:
    def __init__(self, rt):
        self.rt = rt
        self.tuff = tuff_of(rt)
        self.colors = getattr(self.tuff, "TEXT_COLORS", {})
        self.screens = []
        self.running = None  # the screen whose every_frame runs
        self.input = None  # where keys come from (made when they're first needed)
        self.place = None

    @property
    def console(self):
        return self.rt.interp.console

    def where(self):
        """"ide" (TuffCode's Run panel), "terminal" (a real one, or a Build exe's console) or "pipe" (anywhere else)."""
        if self.place is None:
            if getattr(self.tuff, "IDE", False):
                self.place = "ide"
            else:
                try:
                    tty = sys.stdout.isatty() and sys.stdin.isatty() and not getattr(self.tuff, "WINDOWED", False)
                except (AttributeError, ValueError):
                    tty = False
                self.place = "terminal" if tty else "pipe"
        return self.place

    def keys(self):
        if self.input is None:
            place = self.where()
            if place == "ide":
                self.input = IdeKeys(self.console)
            elif place == "terminal" and os.name == "nt":
                try:
                    self.input = ConsoleKeys(self.console)
                except Exception:
                    self.input = MsvcrtKeys(self.console)
            elif place == "terminal":
                try:
                    self.input = TtyKeys(self.console)
                except Exception:
                    self.input = NoKeys()
            else:
                self.input = NoKeys()
        return self.input

    def watched(self):
        """Is someone watching it frame by frame? Not in a pipe, or in the Run panel's protocol with stdin closed."""
        place = self.where()
        return place == "terminal" or (place == "ide" and not self.keys().gone)

    def size(self, v, what, most):
        v = self.rt.plain(v)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise self.rt.error(f"tterm.screen's {what} needs a number, not {self.rt.what(v)}. Like tterm.screen(40, 20).")
        msg = size_problem(v, what, most)
        if msg:
            raise self.rt.error(msg)
        return int(v)

    def make_screen(self, width=40, height=20):
        s = Screen(self, self.size(width, "width", MOST_WIDTH), self.size(height, "height", MOST_HEIGHT))
        if not self.screens:
            self.rt.on_finish(self.finish)
            self.rt.on_wait(self.waiting)
        self.screens.append(s)
        return s.native()

    def finish(self):
        """The program ended: each screen shows how it ended (in a pipe, that's the only time it shows)."""
        for s in self.screens:
            s.show(final=True)

    def waiting(self):
        """While the program waits (wait(0.1) in its own loop), its screens keep up with what it drew."""
        if self.running is not None:
            return
        if self.where() == "ide":
            self.keys().poll()  # (the keys aren't for anything here, but this sees stdin close)
        for s in self.screens:
            s.show()

    def members(self):
        return {"screen": self.rt.builtin("tterm.screen", self.make_screen)}


class Screen:
    def __init__(self, lib, w, h):
        self.lib, self.rt = lib, lib.rt if lib else None
        self.w, self.h = w, h
        self.cells = [[" "] * w for _ in range(h)]
        self.colors = [[None] * w for _ in range(h)]
        self.dirty = True  # changed since it was last shown
        self.frame = 0  # frames since the first every_frame
        self.queue = []  # [frame, key] from screen:press, in frame order
        self.down = set()  # keys held down now
        self.pressed_now, self.held_now = set(), set()
        self.given = False
        self.stopping = False
        self.line = None  # the Run panel: the say line it is; a terminal: the rows on screen; a pipe: True once printed
        self.row = 0  # the Run panel: where its line is (Console.rows when it was said)
        self.sent = None

    # ---- inputs
    def at(self, x, y, what, names="x and y"):
        """The cell for x, y, rounded down (2.7 is in cell 2), or None for one that's endlessly far away."""
        x, y = self.rt.plain(x), self.rt.plain(y)
        for v in (x, y):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise self.rt.error(f"{what} needs numbers for {names}, not {self.rt.what(v)}.")
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return math.floor(x), math.floor(y)

    def color(self, value, what):
        if self.rt.plain(value) is None:
            return None
        word = " ".join(self.rt.text(value).strip().lower().split())
        if word in self.lib.colors:
            return self.lib.colors[word]
        msg = color_problem(self.rt.text(value), what, self.lib.colors)
        if msg:
            raise self.rt.error(msg)
        return word if len(word) == 7 else "#" + "".join(c * 2 for c in word[1:])

    def key(self, value, what):
        name = key_name(self.rt.text(value))
        if name is None:
            raise self.rt.error(key_problem(self.rt.text(value), what))
        return name

    def set(self, c, r, g, color):
        if 0 <= c < self.w and 0 <= r < self.h:
            self.cells[r][c], self.colors[r][c] = g, color
            self.dirty = True

    # ---- drawing
    def put(self, x, y, char, color=None):
        where = self.at(x, y, "screen:put")
        char = self.rt.text(char)
        msg = char_problem(char)
        if msg:
            raise self.rt.error(msg)
        color = self.color(color, "screen:put")
        if where:
            self.set(where[0], where[1], glyphs(char.replace("\n", " "))[0][0], color)

    def text(self, x, y, words, color=None):
        where = self.at(x, y, "screen:text")
        color = self.color(color, "screen:text")
        if where is None:
            return
        c0, r = where
        for line in self.rt.text(words).split("\n"):
            c = c0
            if 0 <= r < self.h:
                for g, n in glyphs(line):
                    if c >= self.w:
                        break
                    self.set(c, r, g, color)
                    if n == 2:  # a wide one covers the next cell too
                        self.set(c + 1, r, " ", color)
                    c += n
            r += 1

    def box(self, x, y, width, height, color=None):
        """A border round width by height cells, with its top left corner at x, y. One cell wide or high, a line."""
        where = self.at(x, y, "screen:box")
        size = self.at(width, height, "screen:box(x, y, width, height)", "width and height")
        color = self.color(color, "screen:box")
        if where is None or size is None or size[0] < 1 or size[1] < 1:
            return
        (c0, r0), (w, h) = where, size
        c1, r1 = c0 + w - 1, r0 + h - 1
        across = range(max(c0 + (h > 1 and w > 1), 0), min(c1 - (h > 1 and w > 1), self.w - 1) + 1)  # (only what's on the screen)
        down = range(max(r0 + 1, 0), min(r1 - 1, self.h - 1) + 1)
        if h == 1:
            for c in across:
                self.set(c, r0, BOX["across"], color)
        elif w == 1:
            for r in range(max(r0, 0), min(r1, self.h - 1) + 1):
                self.set(c0, r, BOX["down"], color)
        else:
            for c in across:
                self.set(c, r0, BOX["across"], color)
                self.set(c, r1, BOX["across"], color)
            for r in down:
                self.set(c0, r, BOX["down"], color)
                self.set(c1, r, BOX["down"], color)
            self.set(c0, r0, BOX["tl"], color)
            self.set(c1, r0, BOX["tr"], color)
            self.set(c0, r1, BOX["bl"], color)
            self.set(c1, r1, BOX["br"], color)

    def clear(self):
        self.cells = [[" "] * self.w for _ in range(self.h)]
        self.colors = [[None] * self.w for _ in range(self.h)]
        self.dirty = True

    def get(self, x, y):
        """The character at x, y: " " for an empty cell, "" off the screen."""
        where = self.at(x, y, "screen:get")
        if where is None or not (0 <= where[0] < self.w and 0 <= where[1] < self.h):
            return ""
        return self.cells[where[1]][where[0]]

    # ---- keys
    def pressed(self, key):
        """Did the key go down since the last frame? (A held key's repeats count, as in a text box.)"""
        name = self.key(key, "screen:pressed")
        return bool(self.pressed_now) if name == "any" else name in self.pressed_now

    def held(self, key):
        name = self.key(key, "screen:held")
        return bool(self.held_now) if name == "any" else name in self.held_now

    def press(self, key, frame=None):
        """Gives a frame a key, as if it was pressed then: the next frame without one, or that frame (counting from 1,
        the first frame of every_frame). For tests, and anywhere no one can press keys."""
        name = self.key(key, "screen:press")
        if name == "any":
            raise self.rt.error(PRESS_ANY)
        if frame is None:
            at = max(self.queue[-1][0] if self.queue else 0, self.frame) + 1
        else:
            f = self.rt.plain(frame)
            if isinstance(f, bool) or not isinstance(f, (int, float)) or not math.isfinite(f):
                raise self.rt.error("screen:press(key, frame) needs a frame number, like screen:press(\"down\", 30).")
            at = max(math.floor(f), self.frame + 1)
        i = len(self.queue)
        while i and self.queue[i - 1][0] > at:
            i -= 1
        self.queue.insert(i, [at, name])

    def take(self, events):
        """A new frame's keys. Gives True when Esc was pressed."""
        pressed = set()
        for kind, name in events:
            if kind == "down":
                pressed.add(name)
                self.down.add(name)
            elif kind == "up":
                self.down.discard(name)
            else:
                self.down.clear()
        self.given = False  # a key from screen:press came this frame
        while self.queue and self.queue[0][0] <= self.frame:
            pressed.add(self.queue.pop(0)[1])
            self.given = True
        self.pressed_now, self.held_now = pressed, self.down | pressed
        return "escape" in pressed

    # ---- the game loop
    def every_frame(self, fn):
        if not self.rt.callable(fn):
            raise self.rt.error(FRAME_FN)
        lib = self.lib
        if lib.running is not None:
            raise self.rt.error("screen:every_frame is already running: it runs until screen:stop() or Esc. Start it once, after setting up the game.")
        keys = lib.keys()
        lib.running, self.stopping = self, False
        self.down.clear()
        frames, last_key = 0, self.frame  # (the frame the last key from screen:press came on)
        try:
            keys.start()
            keys.poll()  # keys pressed before the game don't count
            last = next_at = time.perf_counter()
            while True:
                fast = keys.gone  # no one can press a key: the frames don't wait for the clock
                dt = STEP
                if not fast:
                    while True:
                        left = next_at - time.perf_counter()
                        if left <= 0:
                            break
                        time.sleep(min(0.01, left))  # short naps: Ctrl+C gets in between them
                    now = time.perf_counter()
                    if frames:
                        dt = min(now - last, LONGEST_STEP)
                    last, next_at = now, max(next_at + STEP, now)
                events = keys.poll()
                self.frame += 1
                frames += 1
                if self.take(events):
                    break
                if self.given:
                    last_key = self.frame
                self.rt.interp.invoke(fn, [dt], loose=True)
                if self.stopping:
                    break
                if not fast:
                    self.show()
                elif (not self.queue and self.frame - last_key >= IDLE_FRAMES) or frames >= MOST_FRAMES:
                    break
        finally:
            lib.running = None
            self.down.clear()
            self.pressed_now, self.held_now = set(), set()
            try:
                keys.stop()
            finally:
                self.show(final=True)
        return None

    def stop(self):
        """Ends screen:every_frame after this frame."""
        self.stopping = True

    # ---- showing it
    def row_cells(self, r):
        """A row's (character, colour) pairs as they show: a wide one covers the cell after it."""
        out, skip = [], False
        for c in range(self.w):
            if skip:
                skip = False
                continue
            g = self.cells[r][c]
            out.append((g, self.colors[r][c]))
            skip = columns(g) == 2
        return out

    def show(self, final=False):
        """Shows the screen if it changed: in the Run panel, a terminal, or (only at the end) a pipe."""
        lib = self.lib
        if not final and not lib.watched():
            return
        place = lib.where()
        if place == "ide":
            self.show_ide(lib.running is self and not lib.keys().gone)
        elif place == "terminal":
            self.show_terminal()
        elif self.dirty or self.line is None:
            lib.console.say("\n".join("".join(g for g, _ in self.row_cells(r)).rstrip() for r in range(self.h)))
            self.line, self.dirty = True, False

    def show_ide(self, live):
        """A say line whose look says it's a screen (ide.js richLine colours it, tterm.js takes its keys), rewritten
        in place as it changes."""
        con = self.lib.console
        if self.line is not None and not self.dirty and self.sent and self.sent[2] == live:
            return
        if self.line is not None and con.rows < self.row + self.h:  # the program's clear() took it away: a new line
            self.line = None
        rows, runs = [], []
        for r in range(self.h):
            text, pos = "", 0
            for g, color in self.row_cells(r):
                n = u16(g)
                if color and runs and runs[-1][0] == r and runs[-1][3] == color and runs[-1][1] + runs[-1][2] == pos:
                    runs[-1][2] += n
                elif color:
                    runs.append([r, pos, n, color])
                text += g
                pos += n
            rows.append(text)
        text = "\n".join(rows)
        data = {"screen": 1, "w": self.w, "h": self.h, "runs": runs or None, "live": 1 if live else None, "anim": 1}
        style = "rich:" + self.lib.tuff.b64(json.dumps({k: v for k, v in data.items() if v}, separators=(",", ":")))
        self.dirty = False
        if self.line is None:
            self.line, self.row = con.next_id, con.rows
            con.next_id += 1
            con.write(f"\x1b]tuff;say;{self.line};{self.lib.tuff.b64(text)};{style}\x07\n")
            con.rows += self.h
        elif (text, runs, live) != self.sent:
            con.write(f"\x1b]tuff;rewrite;{self.line};{self.lib.tuff.b64(text)};{style}\x07")
        self.sent = (text, runs, live)

    def show_terminal(self):
        """At the top of the terminal (cleared the first time), drawing only the rows that changed. The cursor stays
        below it, where the program's say lines go."""
        con, tuff = self.lib.console, self.lib.tuff
        if not self.dirty and self.line is not None:  # (after the program's clear() too: it's gone until it changes)
            return
        # Drawn from nothing the first time, after the program's clear(), or once what it said has scrolled it away.
        fresh = self.line is None or con.rows < self.h or (con.rows > self.h and con.rows >= shutil.get_terminal_size((80, 24)).lines - 1)
        rows = []
        for r in range(self.h):
            s, now = "", None
            for g, color in self.row_cells(r):
                if color != now:
                    s += tuff.ansi_color(color) if color else "\x1b[39m"
                    now = color
                s += g
            rows.append(s + "\x1b[0m")
        if fresh:
            out = "\x1b[2J\x1b[H" + "".join(f"\x1b[{r + 1};1H{row}\x1b[K" for r, row in enumerate(rows)) + f"\x1b[{self.h + 1};1H"
            con.rows = self.h
        else:
            changed = [r for r in range(self.h) if rows[r] != self.line[r]]
            if not changed:
                self.dirty = False
                return
            out = "\x1b7" + "".join(f"\x1b[{r + 1};1H{rows[r]}\x1b[K" for r in changed) + "\x1b8"
        con.write(out)
        self.line, self.dirty = rows, False

    def native(self):
        return self.rt.native("screen", {name: getattr(self, name) for name in SCREEN_METHODS},
                              show=lambda nested: f"<screen {self.w}x{self.h}>")


def make_library(rt):
    return Lib(rt).members()


def tables():
    """What the checker knows: the screen's methods (stand-ins, for how many inputs each takes) and the checks it
    shares with the runtime."""
    stand_in = Screen(None, 1, 1)
    return {"methods": {name: getattr(stand_in, name) for name in SCREEN_METHODS}, "color_at": COLOR_AT, "gives": GIVES,
            "key_problem": key_problem, "key_name": key_name, "color_problem": color_problem, "size_problem": size_problem,
            "char_problem": char_problem, "press_any": PRESS_ANY, "frame_fn": FRAME_FN,
            "most": {"width": MOST_WIDTH, "height": MOST_HEIGHT}}
