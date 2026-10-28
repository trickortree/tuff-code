"""tdraw: drawing with a pen for Tuff (1.3.5). The pen is a turtle you move and turn; it draws as it goes.

    mention tdraw
    pen = tdraw.pen()            # opens the drawing window, with the pen in the middle facing right
    pen:color "rainbow"
    for i in range(1, 100):
        pen:forward(i * 3)
        pen:right(59)

The middle of the window is 0, 0; x goes right and y goes up. Colours are the same names as everywhere in Tuff (or
"#rrggbb"), plus "rainbow", which changes colour as the pen moves. Built on Python's turtle module (tkinter), so it
ships wherever tgui does. The window stays open after the program ends, until it's closed.
"""
import colorsys
import functools
import math
import os
import sys
import time
import tkinter as tk
import turtle

BG = "#1e1f22"
SPEEDS = {"slow": 3, "normal": 6, "fast": 10, "instant": 0}
# A pen's methods (the checker knows them from here too).
PEN_METHODS = ("forward", "back", "left", "right", "go", "jump", "home", "face", "up", "down", "color", "width", "speed",
               "circle", "square", "triangle", "polygon", "star", "dot", "write", "hide", "show", "shape", "x", "y")
# The looks pen:shape takes (1.5.0): Tuff's word, then turtle's own name for it.
PEN_SHAPES = {"turtle": "turtle", "arrow": "classic", "big arrow": "arrow", "circle": "circle", "square": "square", "triangle": "triangle"}
CLOSED = "The drawing window was closed, so the drawing stopped."


def hue(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 0.75, 1.0)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


class Lib:
    def __init__(self, rt, colors):
        self.rt, self.colors = rt, colors
        self.root = self.screen = self.canvas = None
        self.closed = False
        self.last_update = 0.0
        self.instant = False
        self.click_fn = None

    # ---- the window
    def ensure(self):
        if self.screen is not None:
            if self.closed:
                raise self.rt.error("The drawing window was closed.")
            return
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        self.root = tk.Tk()
        self.root.title("Tuff drawing")
        self.root.configure(bg=BG)
        self.canvas = tk.Canvas(self.root, width=640, height=640, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.screen = turtle.TurtleScreen(self.canvas)
        self.screen.bgcolor(BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.update()
        self.rt.on_finish(self.mainloop)
        self.rt.on_wait(self.pump)

    def guard(self, fn):
        """A tdraw function or pen method: once the window is closed, the drawing stops with a plain message."""
        @functools.wraps(fn)
        def run(*args):
            if self.closed:
                raise self.rt.error(CLOSED)
            try:
                return fn(*args)
            except (tk.TclError, turtle.Terminator):
                self.closed = True
                raise self.rt.error(CLOSED)
        return run

    def test_close(self):
        items = self.canvas.find_all()
        kinds = {}
        for i in items:
            kinds[self.canvas.type(i)] = kinds.get(self.canvas.type(i), 0) + 1
        print("tdraw drew: " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())), flush=True)
        self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    def mainloop(self):
        if self.root is not None and not self.closed:
            close_after = os.environ.get("TUFF_TDRAW_CLOSE_AFTER")  # tests: after the program ends, close and say what was drawn
            if close_after:
                self.root.after(int(float(close_after) * 1000), self.test_close)
            try:
                self.screen.update()
                self.root.mainloop()
            except (KeyboardInterrupt, tk.TclError):
                pass

    def pump(self):
        """While the program waits (wait(1)), the window keeps drawing and stays responsive."""
        if self.root is not None and not self.closed:
            try:
                self.screen.update()
            except tk.TclError:
                self.closed = True

    def refresh(self):
        """With speed "instant" the pen doesn't animate: the window catches up a few times a second."""
        if self.instant and time.perf_counter() - self.last_update > 0.03:
            self.last_update = time.perf_counter()
            self.pump()

    def color(self, value, what):
        v = " ".join(self.rt.text(value).strip().lower().split())
        if v in self.colors:
            return self.colors[v]
        if v.startswith("#") and len(v) in (4, 7) and all(c in "0123456789abcdef" for c in v[1:]):
            return v if len(v) == 7 else "#" + "".join(c * 2 for c in v[1:])
        raise self.rt.error(f'{what} doesn\'t know the colour "{self.rt.text(value)}". Try red, gold, sky, lime, pink, "rainbow" or a code like "#ff8800".')

    # ---- tdraw.something
    def make_pen(self):
        self.ensure()
        return Pen(self).native()

    def background(self, color):
        self.ensure()
        self.screen.bgcolor(self.color(color, "tdraw.background"))
        self.refresh()

    def clear(self):
        self.ensure()
        for t in self.screen.turtles():
            t.clear()
        self.refresh()

    def title(self, text):
        self.ensure()
        self.root.title(self.rt.text(text))

    def size(self, width, height):
        self.ensure()
        w, h = int(self.rt.number(width, "tdraw.size")), int(self.rt.number(height, "tdraw.size"))
        self.canvas.configure(width=w, height=h)
        self.root.geometry(f"{w}x{h}")
        self.pump()

    def on_click(self, fn):
        self.ensure()
        if not self.rt.callable(fn):
            raise self.rt.error("tdraw.on_click needs a function name, like clicked (without the brackets). It gets x and y.")
        self.screen.onclick(lambda x, y: self.rt.call(fn, round(x), round(y)))

    def members(self):
        b, g = self.rt.builtin, self.guard
        return {
            "pen": b("tdraw.pen", g(self.make_pen)),
            "background": b("tdraw.background", g(self.background)),
            "clear": b("tdraw.clear", g(self.clear)),
            "title": b("tdraw.title", g(self.title)),
            "size": b("tdraw.size", g(self.size)),
            "on_click": b("tdraw.on_click", g(self.on_click)),
        }


class Pen:
    def __init__(self, lib):
        self.lib, self.rt = lib, lib.rt
        self.t = turtle.RawTurtle(lib.screen)
        self.t.shape("turtle")
        self.t.color("#ffffff")
        self.t.pencolor("#ffffff")
        self.t.width(3)
        self.t.speed(SPEEDS["fast"])
        self.rainbow = False
        self.travelled = 0.0
        if lib.instant:
            self.t.speed(0)

    def num(self, v, what):
        return self.rt.number(v, what)

    def step(self, moved=0.0):
        if self.rainbow and moved:
            self.travelled += abs(moved)
            self.t.pencolor(hue(self.travelled / 600))
        self.lib.refresh()

    def walk(self, distance):
        """Moves in short pieces when the pen is rainbow, so the colour flows along the line."""
        if not self.rainbow or abs(distance) <= 12:
            self.t.forward(distance)
            self.step(distance)
            return
        pieces = max(2, int(abs(distance) // 12))
        for _ in range(pieces):
            self.t.forward(distance / pieces)
            self.step(distance / pieces)

    def forward(self, distance):
        self.walk(self.num(distance, "pen:forward"))

    def back(self, distance):
        self.walk(-self.num(distance, "pen:back"))

    def left(self, degrees=90):
        self.t.left(self.num(degrees, "pen:left"))
        self.step()

    def right(self, degrees=90):
        self.t.right(self.num(degrees, "pen:right"))
        self.step()

    def go(self, x, y):
        self.t.goto(self.num(x, "pen:go"), self.num(y, "pen:go"))
        self.step(1)

    def jump(self, x, y):
        down = self.t.isdown()
        self.t.penup()
        self.t.goto(self.num(x, "pen:jump"), self.num(y, "pen:jump"))
        if down:
            self.t.pendown()
        self.step()

    def home(self):
        self.jump(0, 0)
        self.t.setheading(0)

    def face(self, degrees):
        """0 is right, 90 is up, 180 is left, 270 is down."""
        self.t.setheading(self.num(degrees, "pen:face"))
        self.step()

    def up(self):
        self.t.penup()

    def down(self):
        self.t.pendown()

    def color(self, color, fill=None):
        word = " ".join(self.rt.text(color).strip().lower().split())
        self.rainbow = word == "rainbow"
        if self.rainbow:
            self.t.pencolor(hue(self.travelled / 600))
        else:
            self.t.pencolor(self.lib.color(color, "pen:color"))
        if fill is not None:
            self.t.fillcolor(self.lib.color(fill, "pen:color"))
        elif not self.rainbow:
            self.t.fillcolor(self.t.pencolor())

    def width(self, size):
        self.t.width(max(1, self.num(size, "pen:width")))

    def speed(self, how):
        v = self.rt.plain(how)
        if isinstance(v, str):
            word = v.strip().lower()
            if word not in SPEEDS:
                raise self.rt.error('pen:speed takes "slow", "normal", "fast" or "instant" (or a number from 1 to 10).')
            v = SPEEDS[word]
        else:
            v = int(self.num(v, "pen:speed"))
        self.lib.instant = v == 0
        self.lib.screen.tracer(0 if self.lib.instant else 1)
        self.t.speed(max(0, min(10, v)))

    def fill_shape(self, color, draw):
        if color is not None:
            self.t.fillcolor(self.lib.color(color, "the fill colour"))
        self.t.begin_fill()
        draw()
        self.t.end_fill()
        self.step()

    def circle(self, radius, fill=None):
        r = self.num(radius, "pen:circle")
        draw = lambda: self.t.circle(r)
        self.fill_shape(fill, draw) if fill is not None else (draw(), self.step(2 * math.pi * r))

    def polygon(self, sides, size, fill=None):
        n = int(self.num(sides, "pen:polygon"))
        if n < 3:
            raise self.rt.error("pen:polygon needs at least 3 sides, like pen:polygon(6, 50) for a hexagon.")
        size = self.num(size, "pen:polygon")

        def draw():
            for _ in range(n):
                self.walk(size)
                self.t.left(360 / n)
        self.fill_shape(fill, draw) if fill is not None else draw()

    def square(self, size, fill=None):
        self.polygon(4, size, fill)

    def triangle(self, size, fill=None):
        self.polygon(3, size, fill)

    def star(self, size, fill=None):
        size = self.num(size, "pen:star")

        def draw():
            for _ in range(5):
                self.walk(size)
                self.t.right(144)
        self.fill_shape(fill, draw) if fill is not None else draw()

    def dot(self, size=10, color=None):
        self.t.dot(max(1, self.num(size, "pen:dot")), self.lib.color(color, "pen:dot") if color is not None else self.t.pencolor())
        self.step()

    def write(self, text, size=18):
        self.t.write(self.rt.text(text), font=("Segoe UI" if sys.platform == "win32" else "Helvetica", int(self.num(size, "pen:write")), "bold"))
        self.step()

    def hide(self):
        self.t.hideturtle()

    def show(self):
        self.t.showturtle()

    def shape(self, look, size=None):
        """What the pen looks like (1.5.0): "turtle" (the start), "arrow", "big arrow", "circle", "square" or "triangle".
        A size after it makes it bigger or smaller (2 is twice as big). The drawing doesn't change."""
        word = " ".join(self.rt.text(look).strip().lower().split())
        if word not in PEN_SHAPES:
            raise self.rt.error('pen:shape takes "turtle", "arrow", "big arrow", "circle", "square" or "triangle" '
                                '(pen:hide() hides it).')
        self.t.shape(PEN_SHAPES[word])
        if size is not None:
            n = self.num(size, "pen:shape")
            if n <= 0:
                raise self.rt.error("pen:shape's size has to be more than 0.")
            self.t.shapesize(n, n)
        self.lib.refresh()

    def x(self):
        return round(self.t.xcor(), 2)

    def y(self):
        return round(self.t.ycor(), 2)

    def native(self):
        return self.rt.native("pen", {name: self.lib.guard(getattr(self, name)) for name in PEN_METHODS})


def make_library(rt, colors):
    return Lib(rt, colors).members()
