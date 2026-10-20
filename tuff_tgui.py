"""tgui (Tuff GUI) and mtgui (Modern Tuff GUI): desktop apps for Tuff, built on tkinter so they need no installs.

mtgui is the same library with modern=True: anti-aliased gradient shapes, gloss, shine and glow.
"""
import datetime
import math
import os
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

THEMES = {
    "dark": {"bg": "#1e1f22", "surface": "#2b2d30", "raised": "#3c3f45", "border": "#4e5157",
             "text": "#e3e5e8", "muted": "#9da0a8", "field": "#17181b"},
    "light": {"bg": "#f3f4f6", "surface": "#ffffff", "raised": "#e6e8ec", "border": "#cdd0d6",
              "text": "#1f2023", "muted": "#6c707e", "field": "#ffffff"},
}
MODERN_THEMES = {
    "dark": {"bg": "#0b0e14", "surface": "#141924", "raised": "#222a38", "border": "#2c3546",
             "text": "#eef1f7", "muted": "#8b93a7", "field": "#0f131b"},
    "light": {"bg": "#eef1f7", "surface": "#ffffff", "raised": "#dfe4ee", "border": "#cdd4e1",
              "text": "#141924", "muted": "#5f6880", "field": "#ffffff"},
}
ACCENTS = {"blue": "#3574f0", "purple": "#8b5cf6", "pink": "#ec4899", "red": "#e5484d",
           "orange": "#f97316", "yellow": "#e2a508", "green": "#22a35a", "teal": "#14b8a6"}
GRADIENTS = {"blue": ("#3b82f6", "#06b6d4"), "purple": ("#8b5cf6", "#ec4899"), "pink": ("#ec4899", "#f97316"),
             "red": ("#ef4444", "#f97316"), "orange": ("#f97316", "#f43f5e"), "yellow": ("#eab308", "#f97316"),
             "green": ("#22c55e", "#14b8a6"), "teal": ("#14b8a6", "#3b82f6")}
NAMED_COLORS = {**ACCENTS, "white": "#ffffff", "black": "#000000", "gray": "#8a8d94"}
BUTTON_STYLES = ("primary", "secondary", "outline", "ghost", "success", "danger")
CLOCK_STYLES = ("analog", "digital")
FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
SCALE = 1.0


def px(n):
    return int(round(n * SCALE))


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def mix(a, b, t):
    return hexc(x + (y - x) * t for x, y in zip(rgb(a), rgb(b)))


def is_dark(h):
    r, g, b = rgb(h)
    return 0.299 * r + 0.587 * g + 0.114 * b < 150


def ease_out(t):
    return 1 - (1 - t) ** 3


def round_rect(c, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, splinesteps=20, **kw)


# ---------------------------------------------------------------- anti-aliased painter (mtgui)

_IMG_CACHE = {}


def smooth_shape(master, w, h, r, c1, c2=None, bg="#000000", gloss=0.0, shine=None, border=None, bw=1.0, vertical=False):
    """Render a rounded rectangle with soft edges, a gradient, gloss and an optional shine band."""
    w, h = max(2, int(w)), max(2, int(h))
    r = min(r, w / 2, h / 2)
    key = (w, h, round(r, 1), c1, c2, bg, round(gloss, 3), None if shine is None else round(shine, 3), border, bw, vertical)
    img = _IMG_CACHE.get(key)
    if img is not None:
        return img
    A, B, BG = rgb(c1), rgb(c2 or c1), rgb(bg)
    BO = rgb(border) if border else None
    bg_hex = hexc(BG)
    span = w + h * 0.7
    rows = []
    for y in range(h):
        yc = y + 0.5
        cy = r if yc < r else (h - r if yc > h - r else yc)
        g = gloss * max(0.0, 1 - yc / (h * 0.55)) if gloss else 0.0
        row = []
        for x in range(w):
            xc = x + 0.5
            cx = r if xc < r else (w - r if xc > w - r else xc)
            if cx == xc or cy == yc:
                d = -min(xc, w - xc, yc, h - yc)
            else:
                d = math.hypot(xc - cx, yc - cy) - r
            cov = 0.5 - d
            if cov <= 0:
                row.append(bg_hex)
                continue
            cov = 1.0 if cov > 1 else cov
            t = (yc / h) if vertical else (xc / w)
            col = [A[i] + (B[i] - A[i]) * t for i in range(3)]
            k = g
            if shine is not None:
                s = abs((xc + yc * 0.7) / span - shine)
                if s < 0.1:
                    k += (1 - s / 0.1) * 0.38
            if k:
                col = [c + (255 - c) * min(k, 0.9) for c in col]
            if BO is not None:
                inside = -d
                kb = bw + 0.5 - inside
                if kb > 0:
                    kb = 1.0 if kb > 1 else kb
                    col = [c + (o - c) * kb for c, o in zip(col, BO)]
            row.append(hexc(BG[i] + (col[i] - BG[i]) * cov for i in range(3)))
        rows.append("{" + " ".join(row) + "}")
    img = tk.PhotoImage(master=master, width=w, height=h)
    img.put(" ".join(rows))
    if len(_IMG_CACHE) > 400:
        _IMG_CACHE.clear()
    _IMG_CACHE[key] = img
    return img


def smooth_circle(master, d, color, bg, ring=None, ring_w=0):
    return smooth_shape(master, d, d, d / 2, color, bg=bg, border=ring, bw=ring_w)


# ---------------------------------------------------------------- default icon

def default_icon(master):
    # A program built into an app by TuffCode carries the icon picked for it (TUFF_APP_ICON, set by
    # the app's launcher), so its windows show that icon instead of the Tuff placeholder below.
    custom = os.environ.get("TUFF_APP_ICON")
    if custom and os.path.isfile(custom):
        try:
            return tk.PhotoImage(master=master, file=custom)
        except tk.TclError:
            pass
    size, bg = 32, "#0b1226"
    top, bottom = rgb("#3574f0"), rgb("#22d3ee")
    dots = [(x, y) for y in (7, 12) for x in (6, 11, 16, 21, 26)] + [(16, y) for y in (17, 22, 27)]
    rows = []
    for y in range(size):
        t = y / (size - 1)
        dot = hexc(a + (b - a) * t for a, b in zip(top, bottom))
        rows.append("{" + " ".join(
            dot if any(abs(x - dx) <= 1 and abs(y - dy) <= 1 for dx, dy in dots) else bg for x in range(size)) + "}")
    img = tk.PhotoImage(master=master, width=size, height=size)
    img.put(" ".join(rows))
    r = 7
    for y in range(size):
        for x in range(size):
            cx = min(max(x, r), size - 1 - r)
            cy = min(max(y, r), size - 1 - r)
            if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                img.transparency_set(x, y, True)
    return img


def prepare_process(title):
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        app_id = "Tuff." + ("".join(ch for ch in title if ch.isalnum())[:40] or "App")
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


class Lib:
    def __init__(self, rt, modern):
        self.rt = rt
        self.modern = modern
        self.root = None

    def fire(self, fn, *args):
        """Run a click/change handler. Returns False if a Tuff error happened."""
        if fn is None:
            return True
        if callable(fn):
            fn(*args)
            return True
        return self.rt.call(fn, *args)[0]

    def check_fn(self, fn, what):
        if fn is None or callable(fn) or self.rt.callable(fn):
            return fn
        raise self.rt.error(f"{what} needs a function name, like clicked (without the brackets).")

    def color(self, value, app):
        value = self.rt.text(value).strip().lower()
        if value == "accent":
            return app.accent
        if value in ("text", "muted"):
            return app.t[value]
        if value in NAMED_COLORS:
            return NAMED_COLORS[value]
        if len(value) == 7 and value.startswith("#"):
            try:
                rgb(value)
                return value
            except ValueError:
                pass
        raise self.rt.error(f"'{value}' isn't a color I know. Try {', '.join(ACCENTS)} or a hex code like \"#ff8800\".")

    def speed(self, value, what):
        v = self.rt.number(value, what)
        if v <= 0:
            raise self.rt.error(f"{what} needs a speed above 0. 1 is normal, 2 is twice as fast, 0.5 is half speed.")
        return float(v)

    def mainloop(self):
        if self.root is not None:
            try:
                self.root.mainloop()
            except KeyboardInterrupt:
                pass


# ---------------------------------------------------------------- containers

class Container:
    side = "top"

    def bg(self):
        raise NotImplementedError

    def pack_child(self, widget):
        if widget.hidden:
            return
        if self.side == "top":
            widget.outer.pack(side="top", anchor="w", fill="x" if widget.fill else None, pady=(0, px(widget.gap)))
        else:
            widget.outer.pack(side="left", anchor="center", padx=(0, px(10)))

    def repack(self):
        for child in self.children:
            child.outer.pack_forget()
        for child in self.children:
            self.pack_child(child)

    def clear_children(self):
        for child in list(self.children):
            child.remove()

    def child_methods(self):
        lib, rt = self.app.lib, self.app.lib.rt

        def make(cls, *args):
            return cls(self, *args).native()

        def button(text="Button", fn=None, style="primary"):
            style = rt.text(style).lower()
            if style not in BUTTON_STYLES:
                raise rt.error(f"'{style}' isn't a button style. Use one of: {', '.join(BUTTON_STYLES)}.")
            return make(Button, rt.text(text), lib.check_fn(fn, "A button"), style)

        def slider(low=0, high=100, value=None):
            low, high = rt.number(low, "A slider"), rt.number(high, "A slider")
            if high <= low:
                raise rt.error("A slider's highest value must be bigger than its lowest value.")
            return make(Slider, low, high, low if value is None else rt.number(value, "A slider"))

        def clock(style="analog", size=160):
            style = rt.text(style).lower()
            if style not in CLOCK_STYLES:
                raise rt.error("A clock can be \"analog\" or \"digital\".")
            return make(Clock, style, rt.number(size, "A clock"))

        def dropdown(options=None, value=None):
            items = rt_list(rt, options, "A dropdown")
            if not items:
                raise rt.error("A dropdown needs a list of choices, like app:dropdown([\"Small\", \"Large\"]).")
            chosen = rt.text(value) if value is not None else items[0]
            return make(Dropdown, items, chosen)

        def page(*_args):
            raise rt.error(f"A {self.kind} doesn't have :page. Pages go straight on the window, like: home = app:page \"Home\"")

        return {
            "heading": lambda text="": make(Label, rt.text(text), "heading"),
            "text": lambda text="": make(Label, rt.text(text), "text"),
            "small": lambda text="": make(Label, rt.text(text), "small"),
            "button": button,
            "input": lambda placeholder="": make(Input, rt.text(placeholder)),
            "toggle": lambda label="", on=False: make(Toggle, rt.text(label), rt.truthy(on)),
            "checkbox": lambda label="", on=False: make(Checkbox, rt.text(label), rt.truthy(on)),
            "dropdown": dropdown,
            "slider": slider,
            "progress": lambda value=0: make(Progress, rt.number(value, "A progress bar")),
            "spinner": lambda label="", size=28: make(Spinner, rt.text(label), rt.number(size, "A spinner")),
            "clock": clock,
            "image": lambda path, width=None: make(Image, path, None if width is None else rt.number(width, "An image")),
            "divider": lambda: make(Divider),
            "space": lambda size=12: make(Space, rt.number(size, "A space")),
            "row": lambda: make(Row),
            "card": lambda: make(Card),
            "page": page,
            "clear": self.clear_children,
        }


def rt_list(rt, value, what):
    if isinstance(value, list):
        return [rt.text(v) for v in value]
    if value is None:
        return []
    raise rt.error(f"{what} needs a list, like [\"One\", \"Two\"].")


class Widget:
    fill = False
    gap = 10
    kind = "widget"
    speed = 1.0

    def __init__(self, parent):
        self.parent = parent
        self.app = parent.app
        self.lib = self.app.lib
        self.hidden = False
        self.app.widgets.append(self)

    @property
    def modern(self):
        return self.app.lib.modern

    def attach(self):
        self.parent.children.append(self)
        self.parent.pack_child(self)
        self.paint()

    def bgc(self):
        return self.parent.bg()

    def alive(self):
        try:
            return bool(self.outer.winfo_exists())
        except tk.TclError:
            return False

    def paint(self):
        pass

    def hide(self):
        self.hidden = True
        self.outer.pack_forget()

    def show(self):
        if self.hidden:
            self.hidden = False
            self.parent.repack()

    def remove(self):
        for child in list(getattr(self, "children", [])):
            child.remove()
        if self in self.parent.children:
            self.parent.children.remove(self)
        if self in self.app.widgets:
            self.app.widgets.remove(self)
        self.outer.destroy()

    def set_speed(self, value):
        self.speed = self.lib.speed(value, f"{self.kind}:speed")

    def methods(self):
        return {"hide": self.hide, "show": self.show, "remove": self.remove}

    def native(self):
        return self.lib.rt.native(self.kind, self.methods())


class Row(Widget, Container):
    kind = "row"
    side = "left"
    fill = True

    def __init__(self, parent):
        Widget.__init__(self, parent)
        self.children = []
        self.outer = self.inner = tk.Frame(parent.inner, bd=0, highlightthickness=0)
        self.attach()

    def bg(self):
        return self.bgc()

    def paint(self):
        self.outer.configure(bg=self.bgc())

    def methods(self):
        return {**self.child_methods(), **Widget.methods(self)}


class Card(Widget, Container):
    kind = "card"

    def __init__(self, parent):
        Widget.__init__(self, parent)
        self.children = []
        self.pad = px(18)
        self.fill = parent.side == "top"
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, height=px(40), width=px(200))
        self.inner = tk.Frame(self.outer, bd=0, highlightthickness=0)
        self.win_id = self.outer.create_window(self.pad, self.pad, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self.sync, add="+")
        self.outer.bind("<Configure>", self.sync, add="+")
        self.attach()

    def bg(self):
        return self.app.t["surface"]

    def sync(self, _event=None):
        p = self.pad
        if self.fill:
            width = self.outer.winfo_width()
            if width > 2 * p:
                self.outer.itemconfigure(self.win_id, width=width - 2 * p)
        else:
            want = self.inner.winfo_reqwidth() + 2 * p
            if int(self.outer["width"]) != want:
                self.outer.configure(width=want)
        height = self.inner.winfo_reqheight() + 2 * p - px(10)
        if int(self.outer["height"]) != height:
            self.outer.configure(height=height)
        self.draw()

    def draw(self):
        c, t = self.outer, self.app.t
        c.delete("card")
        w = max(c.winfo_width(), int(c["width"])) if self.fill else int(c["width"])
        h = int(c["height"])
        round_rect(c, 1, 1, w - 1, h - 1, px(14), fill=t["surface"], outline=mix(t["surface"], t["border"], 0.6), tags="card")
        if self.modern and w > px(40):
            a, b = self.app.accent, self.app.accent2
            steps = max(2, (w - px(28)) // 4)
            for i in range(steps):
                x0 = px(14) + i * (w - px(28)) / steps
                x1 = px(14) + (i + 1) * (w - px(28)) / steps
                fade = 1 - abs(i / steps - 0.5) * 1.6
                col = mix(t["surface"], mix(a, b, i / steps), max(0.0, min(1.0, fade)))
                c.create_line(x0, 1, x1, 1, fill=col, width=px(2), tags="card")
        c.tag_lower("card")

    def paint(self):
        self.outer.configure(bg=self.bgc())
        self.inner.configure(bg=self.bg())
        self.draw()

    def methods(self):
        return {**self.child_methods(), **Widget.methods(self)}


class Page(Widget, Container):
    """One screen of a window. Only one page per window shows at a time; the first one made starts on screen."""
    kind = "page"
    fill = True
    gap = 0  # its children already leave a gap under themselves

    def __init__(self, parent, title):
        Widget.__init__(self, parent)
        self.children = []
        self.title = title
        self.on_open = None
        self.hidden = bool(self.app.pages)
        self.app.pages.append(self)
        self.outer = self.inner = tk.Frame(parent.inner, bd=0, highlightthickness=0)
        self.attach()

    def bg(self):
        return self.bgc()

    def paint(self):
        self.outer.configure(bg=self.bgc())

    def showing(self):
        return not self.hidden and self in self.app.pages

    def open(self):
        if self not in self.app.pages:
            raise self.lib.rt.error(f"The page '{self.title}' was removed, so it can't be opened.")
        if not self.hidden:
            return
        for page in self.app.pages:
            if page is not self and not page.hidden:
                page.hidden = True
                page.outer.pack_forget()
        self.hidden = False
        self.parent.repack()
        self.lib.fire(self.on_open)

    def show(self):
        self.open()

    def remove(self):
        if self in self.app.pages:
            self.app.pages.remove(self)
        Widget.remove(self)

    def methods(self):
        return {**self.child_methods(), **Widget.methods(self), "open": self.open, "showing": self.showing,
                "opened": lambda fn: setattr(self, "on_open", self.lib.check_fn(fn, ":opened"))}


# ---------------------------------------------------------------- widgets

class Label(Widget):
    sizes = {"heading": (20, "bold"), "text": (11, "normal"), "small": (9, "normal")}

    def __init__(self, parent, text, style):
        super().__init__(parent)
        self.kind = self.style = style
        self.color = None
        size, weight = self.sizes[style]
        if self.modern and style == "heading":
            size = 22
        self.fill = parent.side == "top"
        self.outer = tk.Frame(parent.inner, bd=0, highlightthickness=0)
        self.label = tk.Label(self.outer, text=text, font=(FONT, size, weight), anchor="w", justify="left", bd=0, padx=0, pady=0)
        self.label.pack(side="top", anchor="w", fill="x")
        self.bar = None
        if self.modern and style == "heading":
            self.bar = tk.Canvas(self.outer, bd=0, highlightthickness=0, width=px(44), height=px(4))
            self.bar.pack(side="top", anchor="w", pady=(px(4), 0))
        if self.fill:
            self.label.bind("<Configure>", lambda e: self.label.configure(wraplength=max(60, e.width - 2)))
        self.attach()

    def paint(self):
        bg = self.bgc()
        fg = self.color or (self.app.t["muted"] if self.style == "small" else self.app.t["text"])
        self.outer.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg)
        if self.bar is not None:
            self.bar.configure(bg=bg)
            self.bar.delete("all")
            self.bar_img = smooth_shape(self.bar, px(44), px(4), px(2), self.app.accent, self.app.accent2, bg=bg)
            self.bar.create_image(0, 0, image=self.bar_img, anchor="nw")

    def set_text(self, text):
        self.label.configure(text=self.lib.rt.text(text))

    def set_color(self, color):
        self.color = self.lib.color(color, self.app)
        self.paint()

    def methods(self):
        return {**super().methods(), "set": self.set_text, "value": lambda: self.label.cget("text"), "color": self.set_color}


class Button(Widget):
    kind = "button"

    def __init__(self, parent, text, fn, style):
        super().__init__(parent)
        self.text, self.fn, self.style = text, fn, style
        self.hover = self.down = False
        self.enabled = True
        self.shine = None
        self.shine_token = 0
        self.height = px(40) if self.modern else px(38)
        self.font = tkfont.Font(family=FONT, size=10, weight="bold")
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, cursor="hand2")
        self.resize()
        self.outer.bind("<Enter>", self.enter)
        self.outer.bind("<Leave>", lambda e: self.set_state(hover=False, down=False))
        self.outer.bind("<ButtonPress-1>", lambda e: self.set_state(down=True))
        self.outer.bind("<ButtonRelease-1>", self.release)
        self.attach()

    def resize(self):
        self.width = max(px(64), self.font.measure(self.text) + px(44 if self.modern else 40))
        self.outer.configure(width=self.width, height=self.height)

    def set_state(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        if self.alive():
            self.paint()

    def enter(self, _e):
        self.set_state(hover=True)
        if self.modern and self.enabled and self.style in ("primary", "success", "danger"):
            self.shine_token += 1
            token, start = self.shine_token, time.perf_counter()

            def step():
                if token != self.shine_token or not self.alive():
                    return
                t = (time.perf_counter() - start) / (0.55 / self.speed)
                if t >= 1:
                    self.shine = None
                    self.paint()
                    return
                self.shine = -0.15 + ease_out(t) * 1.3
                self.paint()
                self.outer.after(16, step)
            step()

    def release(self, _e):
        clicked = self.down and self.hover and self.enabled
        self.set_state(down=False)
        if clicked:
            self.lib.fire(self.fn)

    def colors(self):
        t, a, base, s = self.app.t, self.app.accent, self.bgc(), self.style
        a2 = self.app.accent2
        border = None
        if s == "primary":
            bg, bg2, fg = a, a2, "#ffffff"
        elif s == "success":
            bg, bg2, fg = GRADIENTS["green"][0], GRADIENTS["green"][1], "#ffffff"
        elif s == "danger":
            bg, bg2, fg = GRADIENTS["red"][0], "#f43f5e", "#ffffff"
        elif s == "secondary":
            bg, bg2, fg = t["raised"], t["raised"], t["text"]
        elif s == "outline":
            bg, bg2, fg, border = base, base, t["text"], t["border"]
        else:
            bg, bg2, fg = base, base, a
        if not self.modern:
            if s == "success":
                bg = ACCENTS["green"]
            elif s == "danger":
                bg = ACCENTS["red"]
            bg2 = bg
        if self.hover and self.enabled:
            if s in ("outline", "ghost"):
                bg = bg2 = mix(base, t["text"], 0.08)
            else:
                lift = "#ffffff" if is_dark(bg) else "#000000"
                bg, bg2 = mix(bg, lift, 0.12), mix(bg2, lift, 0.12)
        if self.down and self.enabled:
            bg, bg2 = mix(bg, "#000000", 0.12), mix(bg2, "#000000", 0.12)
        if not self.enabled:
            bg, bg2, fg = mix(bg, base, 0.55), mix(bg2, base, 0.55), mix(fg, base, 0.55)
            border = border and mix(border, base, 0.55)
        return bg, bg2, fg, border

    def paint(self):
        c = self.outer
        c.delete("all")
        base = self.bgc()
        c.configure(bg=base, cursor="hand2" if self.enabled else "arrow")
        bg, bg2, fg, border = self.colors()
        dy = 1 if self.down else 0
        if self.modern:
            fancy = self.style in ("primary", "success", "danger")
            self.img = smooth_shape(c, self.width, self.height - 1, px(12), bg, bg2, bg=base,
                                    gloss=0.14 if fancy and self.enabled else 0.0,
                                    shine=self.shine if fancy else None, border=border, bw=1)
            c.create_image(0, dy, image=self.img, anchor="nw")
        else:
            round_rect(c, 1, 1 + dy, self.width - 1, self.height - 1, px(10), fill=bg, outline=border or bg, width=1)
        c.create_text(self.width / 2, self.height / 2 + dy, text=self.text, fill=fg, font=self.font)

    def set_text(self, text):
        self.text = self.lib.rt.text(text)
        self.resize()
        self.paint()

    def set_style(self, style):
        style = self.lib.rt.text(style).lower()
        if style not in BUTTON_STYLES:
            raise self.lib.rt.error(f"'{style}' isn't a button style. Use one of: {', '.join(BUTTON_STYLES)}.")
        self.style = style
        self.paint()

    def on_click(self, fn):
        self.fn = self.lib.check_fn(fn, ":click")

    def methods(self):
        return {**super().methods(), "set": self.set_text, "value": lambda: self.text, "click": self.on_click,
                "style": self.set_style, "speed": self.set_speed, "disable": lambda: self.set_state(enabled=False),
                "enable": lambda: self.set_state(enabled=True)}


class Field(Widget):
    """Shared look for text boxes and dropdowns."""
    height_px = 40

    def draw_box(self, w, focused):
        c, t = self.outer, self.app.t
        c.delete("box")
        base = self.bgc()
        c.configure(bg=base)
        h = self.height
        if self.modern:
            border = self.app.accent if focused else t["border"]
            self.box_img = smooth_shape(c, w, h, px(12), t["field"], bg=base, border=border, bw=px(2) if focused else 1)
            c.create_image(0, 0, image=self.box_img, anchor="nw", tags="box")
        else:
            border = self.app.accent if focused else t["border"]
            round_rect(c, 1, 1, w - 1, h - 1, px(10), fill=t["field"], outline=border, width=2 if focused else 1, tags="box")
        c.tag_lower("box")


class Input(Field):
    kind = "input"

    def __init__(self, parent, placeholder):
        super().__init__(parent)
        self.placeholder = placeholder
        self.focused = self.ghost = False
        self.on_change = self.on_enter = None
        self.height = px(40)
        self.last_w = 0
        self.fill = parent.side == "top"
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, height=self.height, width=px(240), cursor="xterm")
        self.entry = tk.Entry(self.outer, relief="flat", bd=0, highlightthickness=0, font=(FONT, 11))
        self.win_id = self.outer.create_window(px(14), self.height / 2, window=self.entry, anchor="w")
        self.outer.bind("<Configure>", lambda e: self.paint() if e.width != self.last_w else None)
        self.outer.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", self.focus_in)
        self.entry.bind("<FocusOut>", self.focus_out)
        self.entry.bind("<KeyRelease>", self.key)
        self.entry.bind("<Return>", lambda e: self.lib.fire(self.on_enter, self.value()))
        self.show_ghost()
        self.attach()

    def show_ghost(self):
        if not self.entry.get() and self.placeholder:
            self.ghost = True
            self.entry.insert(0, self.placeholder)

    def focus_in(self, _e):
        self.focused = True
        if self.ghost:
            self.ghost = False
            self.entry.delete(0, "end")
        self.paint()

    def focus_out(self, _e):
        self.focused = False
        self.show_ghost()
        self.paint()

    def key(self, e):
        if e.keysym not in ("Return", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            self.lib.fire(self.on_change, self.value())

    def value(self):
        return "" if self.ghost else self.entry.get()

    def set_value(self, text):
        self.ghost = False
        self.entry.delete(0, "end")
        self.entry.insert(0, self.lib.rt.text(text))
        if not self.focused:
            self.show_ghost()
        self.paint()

    def paint(self):
        c, t = self.outer, self.app.t
        w = max(px(60), c.winfo_width() if self.fill else int(c["width"]))
        self.last_w = w
        self.draw_box(w, self.focused)
        self.entry.configure(bg=t["field"], fg=t["muted"] if self.ghost else t["text"], insertbackground=t["text"],
                             selectbackground=self.app.accent, selectforeground="#ffffff")
        c.itemconfigure(self.win_id, width=max(20, w - px(28)))

    def methods(self):
        lib = self.lib
        return {**super().methods(), "value": self.value, "set": self.set_value, "clear": lambda: self.set_value(""),
                "change": lambda fn: setattr(self, "on_change", lib.check_fn(fn, ":change")),
                "enter": lambda fn: setattr(self, "on_enter", lib.check_fn(fn, ":enter")),
                "focus": self.entry.focus_set}


class Dropdown(Field):
    kind = "dropdown"

    def __init__(self, parent, options, value):
        super().__init__(parent)
        self.options = options
        self.current = value if value in options else options[0]
        self.on_change = None
        self.popup = None
        self.height = px(40)
        self.font = tkfont.Font(family=FONT, size=11)
        self.fill = parent.side == "top"
        width = max(px(160), max(self.font.measure(o) for o in options) + px(56))
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, height=self.height, width=width, cursor="hand2")
        self.outer.bind("<Configure>", lambda e: self.paint())
        self.outer.bind("<Button-1>", lambda e: self.toggle_popup())
        self.attach()

    def width(self):
        return max(px(60), self.outer.winfo_width() if self.fill else int(self.outer["width"]))

    def paint(self):
        c, t = self.outer, self.app.t
        w = self.width()
        self.draw_box(w, self.popup is not None)
        c.delete("content")
        c.create_text(px(14), self.height / 2, text=self.current, anchor="w", fill=t["text"], font=self.font, tags="content")
        x, y = w - px(20), self.height / 2
        c.create_line(x - px(5), y - px(2), x, y + px(3), x + px(5), y - px(2), fill=t["muted"], width=px(2),
                      capstyle="round", joinstyle="round", tags="content")

    def toggle_popup(self):
        if self.popup is not None:
            self.close_popup()
            return
        t = self.app.t
        top = tk.Toplevel(self.outer)
        top.overrideredirect(True)
        top.configure(bg=t["border"])
        inner = tk.Frame(top, bg=t["surface"], bd=0)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        for option in self.options:
            item = tk.Label(inner, text=option, anchor="w", font=self.font, padx=px(12), pady=px(6),
                            bg=t["surface"], fg=t["text"], cursor="hand2")
            item.pack(fill="x")
            selected = option == self.current
            if selected:
                item.configure(fg=self.app.accent)
            item.bind("<Enter>", lambda e, w=item: w.configure(bg=mix(t["surface"], self.app.accent, 0.18)))
            item.bind("<Leave>", lambda e, w=item: w.configure(bg=t["surface"]))
            item.bind("<Button-1>", lambda e, o=option: self.choose(o))
        x = self.outer.winfo_rootx()
        y = self.outer.winfo_rooty() + self.height + px(4)
        top.geometry(f"{self.width()}x{top.winfo_reqheight()}+{x}+{y}")
        top.bind("<FocusOut>", lambda e: self.close_popup())
        top.bind("<Escape>", lambda e: self.close_popup())
        self.popup = top
        top.focus_force()
        self.paint()

    def close_popup(self):
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None
            if self.alive():
                self.paint()

    def choose(self, option):
        changed = option != self.current
        self.current = option
        self.close_popup()
        if changed:
            self.lib.fire(self.on_change, option)

    def set_value(self, value):
        value = self.lib.rt.text(value)
        if value not in self.options:
            raise self.lib.rt.error(f"'{value}' isn't one of this dropdown's choices: {', '.join(self.options)}.")
        self.current = value
        self.paint()

    def set_options(self, options):
        items = rt_list(self.lib.rt, options, "dropdown:options")
        if not items:
            raise self.lib.rt.error("A dropdown needs at least one choice.")
        self.options = items
        if self.current not in items:
            self.current = items[0]
        self.paint()

    def methods(self):
        return {**super().methods(), "value": lambda: self.current, "set": self.set_value, "options": self.set_options,
                "change": lambda fn: setattr(self, "on_change", self.lib.check_fn(fn, ":change"))}


class Switchy(Widget):
    """Base for toggles and checkboxes: an on/off value with a timed animation."""

    def __init__(self, parent, label, on):
        super().__init__(parent)
        self.label, self.on = label, on
        self.pos = 1.0 if on else 0.0
        self.on_change = None
        self.anim_token = 0
        self.font = tkfont.Font(family=FONT, size=11)

    def set_value(self, on, notify=False):
        self.on = self.lib.rt.truthy(on)
        self.anim_token += 1
        token, start, origin = self.anim_token, time.perf_counter(), self.pos
        target = 1.0 if self.on else 0.0
        duration = self.duration / self.speed

        def step():
            if token != self.anim_token or not self.alive():
                return
            t = min(1.0, (time.perf_counter() - start) / duration)
            self.pos = origin + (target - origin) * ease_out(t)
            self.paint()
            if t < 1:
                self.outer.after(12, step)
        step()
        if notify:
            self.lib.fire(self.on_change, self.on)

    def methods(self):
        return {**super().methods(), "value": lambda: self.on, "set": self.set_value, "speed": self.set_speed,
                "flip": lambda: self.set_value(not self.on, notify=True),
                "change": lambda fn: setattr(self, "on_change", self.lib.check_fn(fn, ":change"))}


class Toggle(Switchy):
    kind = "toggle"
    duration = 0.18

    def __init__(self, parent, label, on):
        super().__init__(parent, label, on)
        width = px(46) + (px(12) + self.font.measure(label) if label else 0)
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, width=width, height=px(26), cursor="hand2")
        self.outer.bind("<Button-1>", lambda e: self.set_value(not self.on, notify=True))
        self.attach()

    def paint(self):
        c, t = self.outer, self.app.t
        c.delete("all")
        base = self.bgc()
        c.configure(bg=base)
        off = t["raised"] if is_dark(t["bg"]) else t["border"]
        tw, th = px(44), px(24)
        if self.modern:
            c1 = mix(off, self.app.accent, self.pos)
            c2 = mix(off, self.app.accent2, self.pos)
            self.track = smooth_shape(c, tw, th, th / 2, c1, c2, bg=base, gloss=0.1 * self.pos)
            c.create_image(0, px(1), image=self.track, anchor="nw")
            d = th - px(6)
            self.knob = smooth_circle(c, d, "#ffffff", mix(c1, c2, 0.15 + 0.7 * self.pos))
            x = px(3) + self.pos * (tw - d - px(6))
            c.create_image(x, px(4), image=self.knob, anchor="nw")
        else:
            col = mix(off, self.app.accent, self.pos)
            round_rect(c, 1, px(3), px(43), px(23), px(10), fill=col, outline=col)
            x = px(12) + self.pos * px(20)
            c.create_oval(x - px(8), px(5), x + px(8), px(21), fill="#ffffff", outline="")
        if self.label:
            c.create_text(px(56), px(13), text=self.label, anchor="w", fill=t["text"], font=self.font)


class Checkbox(Switchy):
    kind = "checkbox"
    duration = 0.16

    def __init__(self, parent, label, on):
        super().__init__(parent, label, on)
        width = px(22) + (px(10) + self.font.measure(label) if label else 0)
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, width=width, height=px(24), cursor="hand2")
        self.outer.bind("<Button-1>", lambda e: self.set_value(not self.on, notify=True))
        self.attach()

    def paint(self):
        c, t = self.outer, self.app.t
        c.delete("all")
        base = self.bgc()
        c.configure(bg=base)
        s, y0 = px(20), px(2)
        if self.modern:
            fill1 = mix(t["field"], self.app.accent, self.pos)
            fill2 = mix(t["field"], self.app.accent2, self.pos)
            self.box = smooth_shape(c, s, s, px(6), fill1, fill2, bg=base,
                                    border=None if self.pos > 0.5 else t["border"], bw=1.5)
            c.create_image(0, y0, image=self.box, anchor="nw")
        else:
            fill = mix(t["field"], self.app.accent, self.pos)
            round_rect(c, 1, y0, s, y0 + s - 1, px(5), fill=fill, outline=t["border"] if self.pos < 0.5 else fill)
        if self.pos > 0.05:
            pts = [(px(5), y0 + px(10)), (px(9), y0 + px(14)), (px(16), y0 + px(6))]
            first = math.dist(pts[0], pts[1])
            total = first + math.dist(pts[1], pts[2])
            drawn = total * self.pos
            line = [pts[0]]
            if drawn <= first:
                k = drawn / first
                line.append((pts[0][0] + (pts[1][0] - pts[0][0]) * k, pts[0][1] + (pts[1][1] - pts[0][1]) * k))
            else:
                k = (drawn - first) / (total - first)
                line += [pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * k, pts[1][1] + (pts[2][1] - pts[1][1]) * k)]
            c.create_line(*[v for p in line for v in p], fill="#ffffff", width=px(2), capstyle="round", joinstyle="round")
        if self.label:
            c.create_text(px(30), px(12), text=self.label, anchor="w", fill=t["text"], font=self.font)


class Slider(Widget):
    kind = "slider"

    def __init__(self, parent, low, high, value):
        super().__init__(parent)
        self.low, self.high = low, high
        self.whole = all(float(v).is_integer() for v in (low, high))
        self.val = self.clamp(value)
        self.on_change = None
        self.pad = px(11)
        self.fill = parent.side == "top"
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, height=px(28), width=px(220), cursor="hand2")
        self.outer.bind("<Configure>", lambda e: self.paint())
        self.outer.bind("<Button-1>", self.drag)
        self.outer.bind("<B1-Motion>", self.drag)
        self.attach()

    def clamp(self, v):
        v = min(self.high, max(self.low, v))
        return int(round(v)) if self.whole else round(v, 2)

    def width(self):
        return max(px(60), self.outer.winfo_width() if self.fill else int(self.outer["width"]))

    def drag(self, e):
        frac = (e.x - self.pad) / max(1, self.width() - 2 * self.pad)
        new = self.clamp(self.low + frac * (self.high - self.low))
        if new != self.val:
            self.val = new
            self.paint()
            self.lib.fire(self.on_change, self.val)

    def set_value(self, v):
        self.val = self.clamp(self.lib.rt.number(v, "slider:set"))
        self.paint()

    def paint(self):
        c, t, a = self.outer, self.app.t, self.app.accent
        c.delete("all")
        base = self.bgc()
        c.configure(bg=base)
        x0, x1 = self.pad, self.width() - self.pad
        x = x0 + (self.val - self.low) / (self.high - self.low) * (x1 - x0)
        mid = px(14)
        if self.modern:
            self.track = smooth_shape(c, x1 - x0, px(6), px(3), t["raised"], bg=base)
            c.create_image(x0, mid - px(3), image=self.track, anchor="nw")
            if x > x0 + px(6):
                self.fill_img = smooth_shape(c, x - x0, px(6), px(3), a, self.app.accent2, bg=t["raised"])
                c.create_image(x0, mid - px(3), image=self.fill_img, anchor="nw")
            d = px(20)
            self.knob = smooth_shape(c, d, d, d / 2, "#ffffff", bg=base, border=self.app.accent2, bw=px(3))
            c.create_image(x - d / 2, mid - d / 2, image=self.knob, anchor="nw")
        else:
            round_rect(c, x0, mid - px(2), x1, mid + px(2), px(2), fill=t["raised"], outline=t["raised"])
            if x > x0 + 1:
                round_rect(c, x0, mid - px(2), x, mid + px(2), px(2), fill=a, outline=a)
            r = px(9)
            c.create_oval(x - r, mid - r, x + r, mid + r, fill="#ffffff", outline=a, width=px(3))

    def methods(self):
        return {**super().methods(), "value": lambda: self.val, "set": self.set_value,
                "change": lambda fn: setattr(self, "on_change", self.lib.check_fn(fn, ":change"))}


class Progress(Widget):
    kind = "progress"

    def __init__(self, parent, value):
        super().__init__(parent)
        self.target = self.shown = max(0, min(100, value))
        self.anim_token = 0
        self.shimmer = 0.0
        self.fill = parent.side == "top"
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, height=px(10), width=px(220))
        self.outer.bind("<Configure>", lambda e: self.paint())
        self.attach()
        if self.modern:
            self.outer.after(40, self.shimmer_step)

    def shimmer_step(self):
        if not self.alive():
            return
        if 0 < self.shown < 100 and not self.hidden:
            self.shimmer = (self.shimmer + 0.02 * self.speed) % 1.4
            self.paint()
        self.outer.after(40, self.shimmer_step)

    def set_value(self, v):
        self.target = max(0, min(100, self.lib.rt.number(v, "progress:set")))
        self.anim_token += 1
        token, start, origin = self.anim_token, time.perf_counter(), self.shown
        duration = 0.35 / self.speed

        def step():
            if token != self.anim_token or not self.alive():
                return
            t = min(1.0, (time.perf_counter() - start) / duration)
            self.shown = origin + (self.target - origin) * ease_out(t)
            self.paint()
            if t < 1:
                self.outer.after(16, step)
        step()

    def paint(self):
        c, t, a = self.outer, self.app.t, self.app.accent
        c.delete("all")
        base = self.bgc()
        c.configure(bg=base)
        w = max(px(40), c.winfo_width() if self.fill else int(c["width"]))
        h = px(10)
        if self.modern:
            self.track = smooth_shape(c, w, h, h / 2, t["raised"], bg=base)
            c.create_image(0, 0, image=self.track, anchor="nw")
            if self.shown > 0:
                fw = max(h, int(w * self.shown / 100))
                self.bar = smooth_shape(c, fw, h, h / 2, a, self.app.accent2, bg=t["raised"], gloss=0.18,
                                        shine=self.shimmer - 0.2 if 0 < self.shown < 100 else None)
                c.create_image(0, 0, image=self.bar, anchor="nw")
        else:
            round_rect(c, 0, 1, w, h - 1, px(4), fill=t["raised"], outline=t["raised"])
            if self.shown > 0:
                round_rect(c, 0, 1, max(px(8), w * self.shown / 100), h - 1, px(4), fill=a, outline=a)

    def methods(self):
        return {**super().methods(), "value": lambda: round(self.target, 2), "set": self.set_value, "speed": self.set_speed}


class Spinner(Widget):
    kind = "spinner"

    def __init__(self, parent, label, size):
        super().__init__(parent)
        self.label = label
        self.size = px(max(12, size))
        self.angle = 0.0
        self.running = True
        self.last = time.perf_counter()
        self.font = tkfont.Font(family=FONT, size=11)
        width = self.size + (px(10) + self.font.measure(label) if label else 0)
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0, width=width, height=self.size + 2)
        self.attach()
        self.step()

    def step(self):
        if not self.alive():
            return
        now = time.perf_counter()
        if self.running:
            self.angle = (self.angle - (now - self.last) * 360 * self.speed) % 360
            self.paint()
        self.last = now
        self.outer.after(16, self.step)

    def paint(self):
        c, t = self.outer, self.app.t
        c.delete("all")
        c.configure(bg=self.bgc())
        s, w = self.size, max(2, px(3))
        box = (w, w + 1, s - w, s - w + 1)
        c.create_oval(*box, outline=mix(self.bgc(), t["border"], 0.6), width=w)
        if self.modern:
            parts = 14
            for i in range(parts):
                k = i / parts
                c.create_arc(*box, start=self.angle + k * 260, extent=260 / parts + 1, style="arc", width=w,
                             outline=mix(self.bgc(), mix(self.app.accent2, self.app.accent, k), 0.25 + 0.75 * k))
        else:
            c.create_arc(*box, start=self.angle, extent=100, style="arc", width=w, outline=self.app.accent)
        if self.label:
            c.create_text(s + px(10), s / 2 + 1, text=self.label, anchor="w", fill=t["text"], font=self.font)

    def methods(self):
        return {**super().methods(), "speed": self.set_speed,
                "stop": lambda: setattr(self, "running", False), "start": lambda: setattr(self, "running", True)}


class Clock(Widget):
    kind = "clock"

    def __init__(self, parent, style, size):
        super().__init__(parent)
        self.style = style
        self.size = px(max(60, size))
        self.running = True
        now = datetime.datetime.now()
        self.base = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6
        self.t0 = time.perf_counter()
        self.font = tkfont.Font(family=FONT, size=30, weight="bold")
        self.outer = tk.Canvas(parent.inner, bd=0, highlightthickness=0)
        self.resize()
        self.attach()
        self.tick()

    def resize(self):
        if self.style == "analog":
            self.outer.configure(width=self.size + 2, height=self.size + 2)
        else:
            self.outer.configure(width=self.font.measure("00:00:00") + px(36), height=self.font.metrics("linespace") + px(20))

    def seconds(self):
        if not self.running:
            return self.base % 86400
        return (self.base + (time.perf_counter() - self.t0) * self.speed) % 86400

    def rebase(self, value):
        self.base = value % 86400
        self.t0 = time.perf_counter()

    def tick(self):
        if not self.alive():
            return
        self.paint_time()
        self.outer.after(40 if self.style == "analog" else 200, self.tick)

    def paint(self):
        c, t = self.outer, self.app.t
        c.delete("all")
        base = self.bgc()
        c.configure(bg=base)
        if self.style == "analog":
            s = self.size
            cx = cy = s / 2 + 1
            r = s / 2 - px(3)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=t["surface"], outline=t["border"], width=1)
            if self.modern:
                segs = 72
                for i in range(segs):
                    k = i / segs
                    col = mix(self.app.accent, self.app.accent2, 1 - abs(k - 0.5) * 2)
                    c.create_arc(cx - r + px(2), cy - r + px(2), cx + r - px(2), cy + r - px(2),
                                 start=90 - k * 360, extent=-(360 / segs + 1), style="arc", width=px(3), outline=col)
            for i in range(60):
                ang = math.radians(i * 6 - 90)
                hour = i % 5 == 0
                r1, r2 = r * (0.78 if hour else 0.86), r * 0.9
                c.create_line(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang), cx + r2 * math.cos(ang), cy + r2 * math.sin(ang),
                              fill=t["text"] if hour else t["muted"], width=px(2) if hour else 1, capstyle="round")
        else:
            w, h = int(c["width"]), int(c["height"])
            if self.modern:
                self.face = smooth_shape(c, w, h, px(14), t["surface"], bg=base, border=mix(t["surface"], self.app.accent, 0.5), bw=1.5)
                c.create_image(0, 0, image=self.face, anchor="nw")
            else:
                round_rect(c, 1, 1, w - 1, h - 1, px(12), fill=t["surface"], outline=t["border"])
        self.paint_time()

    def paint_time(self):
        c, t = self.outer, self.app.t
        c.delete("time")
        secs = self.seconds()
        h, m, s = secs / 3600, (secs % 3600) / 60, secs % 60
        if self.style == "analog":
            size = self.size
            cx = cy = size / 2 + 1
            r = size / 2 - px(3)
            hands = (
                ((h % 12) / 12, r * 0.5, px(5), t["text"]),
                (m / 60, r * 0.72, px(3), t["text"]),
                (s / 60, r * 0.8, max(1, px(1.5)), self.app.accent2 if self.modern else self.app.accent),
            )
            for frac, length, width, color in hands:
                ang = frac * 2 * math.pi - math.pi / 2
                c.create_line(cx - length * 0.12 * math.cos(ang), cy - length * 0.12 * math.sin(ang),
                              cx + length * math.cos(ang), cy + length * math.sin(ang),
                              fill=color, width=width, capstyle="round", tags="time")
            dot = px(4)
            c.create_oval(cx - dot, cy - dot, cx + dot, cy + dot, fill=self.app.accent, outline="", tags="time")
        else:
            w, hgt = int(c["width"]), int(c["height"])
            color = self.app.accent2 if self.modern else t["text"]
            c.create_text(w / 2, hgt / 2, text=self.text(), fill=color, font=self.font, tags="time")

    def text(self):
        secs = int(self.seconds())
        return f"{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}"

    def set_time(self, hours, minutes=0, seconds=0):
        rt = self.lib.rt
        self.rebase(rt.number(hours, "clock:set") * 3600 + rt.number(minutes, "clock:set") * 60 + rt.number(seconds, "clock:set"))
        self.paint_time()

    def set_now(self):
        now = datetime.datetime.now()
        self.rebase(now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6)

    def set_clock_speed(self, value):
        current = self.seconds()
        self.speed = self.lib.speed(value, "clock:speed")
        self.rebase(current)

    def pause(self):
        self.base = self.seconds()
        self.running = False

    def resume(self):
        if not self.running:
            self.running = True
            self.t0 = time.perf_counter()

    def set_style(self, style):
        style = self.lib.rt.text(style).lower()
        if style not in CLOCK_STYLES:
            raise self.lib.rt.error("A clock can be \"analog\" or \"digital\".")
        self.style = style
        self.resize()
        self.paint()

    def methods(self):
        return {**super().methods(), "set": self.set_time, "now": self.set_now, "speed": self.set_clock_speed,
                "pause": self.pause, "resume": self.resume, "value": self.text, "style": self.set_style}


class Image(Widget):
    kind = "image"

    def __init__(self, parent, path, width):
        super().__init__(parent)
        self.max_width = width and px(width)
        self.outer = tk.Label(parent.inner, bd=0, highlightthickness=0)
        self.load(path)
        self.attach()

    def load(self, path):
        rt = self.lib.rt
        try:
            img = tk.PhotoImage(master=self.outer, file=rt.path(path))
        except tk.TclError:
            raise rt.error(f"Couldn't open the image '{rt.text(path)}'. Put a .png or .gif file in your project folder.")
        if self.max_width and img.width() > self.max_width:
            img = img.subsample(math.ceil(img.width() / self.max_width))
        self.img = img
        self.outer.configure(image=img)

    def paint(self):
        self.outer.configure(bg=self.bgc())

    def methods(self):
        return {**super().methods(), "set": self.load}


class Divider(Widget):
    kind = "divider"

    def __init__(self, parent):
        super().__init__(parent)
        self.fill = parent.side == "top"
        self.outer = tk.Frame(parent.inner, height=1 if self.fill else px(24), width=1, bd=0)
        self.attach()

    def paint(self):
        self.outer.configure(bg=mix(self.bgc(), self.app.t["border"], 0.7))


class Space(Widget):
    kind = "space"

    def __init__(self, parent, size):
        super().__init__(parent)
        size = max(0, px(size))
        self.outer = tk.Frame(parent.inner, height=size, width=size, bd=0)
        self.attach()

    def paint(self):
        self.outer.configure(bg=self.bgc())


# ---------------------------------------------------------------- windows

class DialogBox(Container):
    def __init__(self, app, top):
        self.app = app
        self.children = []
        top.configure(bg=self.bg())
        self.inner = tk.Frame(top, bg=self.bg(), bd=0)
        self.inner.pack(fill="both", expand=True, padx=px(22), pady=(px(20), px(10)))

    def bg(self):
        return self.app.t["surface"]


class App(Container):
    kind = "window"

    def __init__(self, lib, title, width, height):
        global SCALE
        self.lib = lib
        self.app = self
        self.children = []
        self.widgets = []
        self.pages = []
        self.themes = MODERN_THEMES if lib.modern else THEMES
        self.t = self.themes["dark"]
        self.accent, self.accent2 = GRADIENTS["blue"] if lib.modern else (ACCENTS["blue"], ACCENTS["blue"])
        self.closed = False
        first = lib.root is None
        if first:
            prepare_process(title)
            self.win = tk.Tk()
            self.win.withdraw()
            SCALE = max(1.0, self.win.winfo_fpixels("1i") / 96)
            lib.root = self.win
            lib.rt.on_finish(lib.mainloop)
        else:
            self.win = tk.Toplevel(lib.root)
            self.win.withdraw()
        self.win.title(title)
        self.win.geometry(f"{px(width)}x{px(height)}")
        self.win.minsize(px(220), px(140))
        self.icon_img = default_icon(self.win)
        self.win.iconphoto(first, self.icon_img)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.inner = tk.Frame(self.win, bd=0, highlightthickness=0)
        self.inner.pack(fill="both", expand=True, padx=px(24), pady=(px(22), px(12)))
        self.paint_all()
        self.center()
        self.win.deiconify()
        self.win.lift()

    def bg(self):
        return self.t["bg"]

    def center(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")

    def paint_all(self):
        self.widgets = [w for w in self.widgets if w.alive()]
        self.win.configure(bg=self.t["bg"])
        self.inner.configure(bg=self.t["bg"])
        for w in self.widgets:
            w.paint()

    def set_title(self, text):
        self.win.title(self.lib.rt.text(text))

    def set_icon(self, path):
        rt = self.lib.rt
        full = rt.path(path)
        if not os.path.exists(full):
            raise rt.error(f"Couldn't find the icon '{rt.text(path)}'. Put the image in your project folder.")
        try:
            if full.lower().endswith(".ico"):
                self.win.iconbitmap(full)
            else:
                self.icon_img = tk.PhotoImage(master=self.win, file=full)
                self.win.iconphoto(self.win is self.lib.root, self.icon_img)
        except tk.TclError:
            raise rt.error(f"Couldn't use '{rt.text(path)}' as an icon. Use a .png, .gif or .ico file.")

    def set_size(self, width, height):
        rt = self.lib.rt
        self.win.geometry(f"{px(rt.number(width, ':size'))}x{px(rt.number(height, ':size'))}")

    def set_theme(self, name):
        name = self.lib.rt.text(name).lower()
        if name not in self.themes:
            raise self.lib.rt.error("The theme can be \"dark\" or \"light\".")
        self.t = self.themes[name]
        self.paint_all()

    def set_accent(self, color):
        name = self.lib.rt.text(color).strip().lower()
        if self.lib.modern and name in GRADIENTS:
            self.accent, self.accent2 = GRADIENTS[name]
        else:
            self.accent = self.lib.color(color, self)
            self.accent2 = mix(self.accent, "#ffffff", 0.25) if self.lib.modern else self.accent
        self.paint_all()

    def set_gradient(self, first, second):
        self.accent = self.lib.color(first, self)
        self.accent2 = self.lib.color(second, self) if self.lib.modern else self.accent
        self.paint_all()

    def add_page(self, title="Page"):
        return Page(self, self.lib.rt.text(title)).native()

    def every(self, seconds, fn):
        fn = self.lib.check_fn(fn, ":every")
        ms = max(10, int(self.lib.rt.number(seconds, ":every") * 1000))

        def tick():
            if not self.closed and self.lib.fire(fn):
                self.win.after(ms, tick)
        self.win.after(ms, tick)

    def after(self, seconds, fn):
        fn = self.lib.check_fn(fn, ":after")
        ms = max(0, int(self.lib.rt.number(seconds, ":after") * 1000))
        self.win.after(ms, lambda: None if self.closed else self.lib.fire(fn))

    def close(self):
        if not self.closed:
            self.closed = True
            self.win.destroy()

    def dialog(self, message, buttons, ask=False):
        result = {"value": None}
        top = tk.Toplevel(self.win)
        top.withdraw()
        top.title(self.win.title())
        top.transient(self.win)
        top.resizable(False, False)
        top.iconphoto(False, self.icon_img)
        box = DialogBox(self, top)
        Label(box, self.lib.rt.text(message), "text")
        field = Input(box, "") if ask else None
        row = Row(box)

        def choose(value):
            result["value"] = field.value() if value == "<field>" else value
            top.destroy()

        for text, value, style in buttons:
            Button(row, text, lambda v=value: choose(v), style)
        cancel = None if ask else buttons[-1][1]
        if field:
            field.on_enter = lambda _v: choose("<field>")
        else:
            top.bind("<Return>", lambda e: choose(buttons[0][1]))
        top.bind("<Escape>", lambda e: choose(cancel))
        top.protocol("WM_DELETE_WINDOW", lambda: choose(cancel))
        top.update_idletasks()
        w, h = max(px(340), top.winfo_reqwidth()), top.winfo_reqheight()
        x = self.win.winfo_rootx() + (self.win.winfo_width() - w) // 2
        y = self.win.winfo_rooty() + (self.win.winfo_height() - h) // 3
        top.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        top.deiconify()
        top.grab_set()
        (field.entry if field else top).focus_set()
        top.wait_window()
        self.widgets = [w for w in self.widgets if w.alive()]
        return result["value"]

    def alert(self, message):
        self.dialog(message, [("OK", True, "primary")])

    def confirm(self, message):
        return bool(self.dialog(message, [("Yes", True, "primary"), ("No", False, "outline")]))

    def ask(self, question):
        value = self.dialog(question, [("OK", "<field>", "primary"), ("Cancel", None, "outline")], ask=True)
        return value if isinstance(value, str) else ""

    def native(self):
        return self.lib.rt.native("window", {
            **self.child_methods(),
            "page": self.add_page,
            "title": self.set_title, "icon": self.set_icon, "size": self.set_size,
            "theme": self.set_theme, "accent": self.set_accent, "gradient": self.set_gradient,
            "every": self.every, "after": self.after, "close": self.close,
            "alert": self.alert, "confirm": self.confirm, "ask": self.ask,
        })


def make_library(rt, modern=False):
    lib = Lib(rt, modern)
    name = "mtgui" if modern else "tgui"

    def window(title="My App", width=420, height=520):
        return App(lib, rt.text(title), rt.number(width, f"{name}.window"), rt.number(height, f"{name}.window")).native()

    return {"window": rt.builtin(f"{name}.window", window)}
