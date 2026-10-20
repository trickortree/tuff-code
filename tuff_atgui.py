"""atgui (advanced Tuff GUI): modern desktop apps for Tuff, made of real HTML and CSS in a native window.

It sits on tuff_view (the web view engine): every widget is a DOM element that Python creates and changes
through the engine's batched commands, and events come back through the engine's bridge. Tuff code never
writes HTML: it calls app:button(...), card:style("radius", 12) and so on. Experts can still use
w:css("...") and app:html("...").

The window is opened when the program's top-level code has finished (or when something needs it sooner,
like app:ask), so the whole first screen arrives in one batch, with the right theme, size, icon and frame.
Until then every change is recorded and replayed in order. After that, the program's own thread runs the
engine's loop(), and every event function runs there.
"""
import itertools
import json
import math
import os
import re
import sys
import threading
import time
import urllib.parse
import webbrowser

# ---------------------------------------------------------------- looks

DARK = {"bg": "#0e1013", "side": "#121418", "surface": "#171a1f", "raised": "#1f232a", "field": "#111317",
        "hover": "rgba(255,255,255,0.06)", "press": "rgba(255,255,255,0.1)", "border": "rgba(255,255,255,0.08)",
        "border-strong": "rgba(255,255,255,0.15)", "text": "#ececef", "muted": "#9ca2ad", "faint": "#6c727d",
        "shadow": "0 1px 2px rgba(0,0,0,0.35), 0 1px 1px rgba(0,0,0,0.2)",
        "shadow-lg": "0 18px 50px -12px rgba(0,0,0,0.65), 0 4px 14px rgba(0,0,0,0.35)",
        "code-bg": "#0b0d10", "scrim": "rgba(4,5,8,0.55)", "tip": "#2a2e36", "tip-text": "#f3f4f6"}
LIGHT = {"bg": "#f6f6f7", "side": "#eeeef1", "surface": "#ffffff", "raised": "#f1f2f4", "field": "#ffffff",
         "hover": "rgba(0,0,0,0.045)", "press": "rgba(0,0,0,0.08)", "border": "rgba(0,0,0,0.09)",
         "border-strong": "rgba(0,0,0,0.17)", "text": "#18191c", "muted": "#5c626d", "faint": "#8d939d",
         "shadow": "0 1px 2px rgba(16,24,40,0.07), 0 1px 1px rgba(16,24,40,0.04)",
         "shadow-lg": "0 18px 50px -12px rgba(16,24,40,0.28), 0 4px 14px rgba(16,24,40,0.1)",
         "code-bg": "#f4f5f7", "scrim": "rgba(15,18,25,0.32)", "tip": "#1d2026", "tip-text": "#f3f4f6"}
THEMES = ("dark", "light", "system")
ACCENTS = {"blue": ("#3b82f6", "#06b6d4"), "purple": ("#8b5cf6", "#ec4899"), "pink": ("#ec4899", "#f97316"),
           "red": ("#ef4444", "#f97316"), "orange": ("#f97316", "#f43f5e"), "yellow": ("#eab308", "#f97316"),
           "green": ("#22c55e", "#14b8a6"), "teal": ("#14b8a6", "#3b82f6"), "indigo": ("#6366f1", "#a855f7"),
           "gray": ("#71717a", "#a1a1aa")}
NAMED_COLORS = {name: pair[0] for name, pair in ACCENTS.items()}
NAMED_COLORS.update({"white": "#ffffff", "black": "#000000", "grey": "#71717a",
                     "accent": "var(--accent)", "text": "var(--text)", "muted": "var(--muted)", "faint": "var(--faint)",
                     "background": "var(--bg)", "surface": "var(--surface)", "raised": "var(--raised)",
                     "border": "var(--border)", "transparent": "transparent", "none": "transparent"})
FONT = ('"Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", '
        'Arial, sans-serif')
MONO = '"Cascadia Code", "Cascadia Mono", Consolas, "SF Mono", Menlo, "Liberation Mono", monospace'
FONTS = {"system": FONT, "default": FONT, "mono": MONO, "code": MONO,
         "serif": 'Charter, "Iowan Old Style", Georgia, Cambria, "Times New Roman", serif',
         "rounded": 'ui-rounded, "SF Pro Rounded", "Segoe UI Variable Display", Nunito, "Segoe UI", system-ui, sans-serif'}
BUTTON_STYLES = ("primary", "secondary", "outline", "ghost", "success", "danger", "gradient")
BADGE_STYLES = ("accent", "gray", "success", "warning", "danger", "info", "outline")
TOAST_STYLES = ("info", "success", "warning", "error")
CHART_KINDS = ("line", "bar")
ANIMATIONS = ("fade-in", "fade-out", "slide-up", "slide-down", "slide-left", "slide-right", "pop", "zoom-in",
              "zoom-out", "bounce", "shake", "pulse", "spin", "wiggle", "float", "blink", "none")
ALIGN = {"start": "flex-start", "left": "flex-start", "top": "flex-start", "center": "center", "middle": "center",
         "end": "flex-end", "right": "flex-end", "bottom": "flex-end", "stretch": "stretch", "fill": "stretch",
         "baseline": "baseline"}
JUSTIFY = {"start": "flex-start", "left": "flex-start", "top": "flex-start", "center": "center", "middle": "center",
           "end": "flex-end", "right": "flex-end", "bottom": "flex-end", "between": "space-between",
           "around": "space-around", "evenly": "space-evenly", "space-between": "space-between"}
IMAGE_EXTS = (".png", ".gif", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".ico", ".avif")


def _gear():
    """A gear for the "settings" icon, worked out rather than drawn by hand."""
    pts = []
    for i in range(8):
        a = i * math.pi / 4
        for da, r in ((-0.24, 7.2), (-0.15, 9.6), (0.15, 9.6), (0.24, 7.2)):
            pts.append((12 + r * math.cos(a + da), 12 + r * math.sin(a + da)))
    return "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"


def _star():
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 9.6 if i % 2 == 0 else 4.4
        pts.append((12 + r * math.cos(a), 12.6 + r * math.sin(a)))
    return "M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z"


def _rays():
    out = []
    for i in range(8):
        a = i * math.pi / 4
        out.append(f"M{12 + 7 * math.cos(a):.2f} {12 + 7 * math.sin(a):.2f}L{12 + 9.6 * math.cos(a):.2f} {12 + 9.6 * math.sin(a):.2f}")
    return "".join(out)


# A small icon set drawn for atgui on a 24 x 24 grid (stroked, round ends). Each is SVG path data, or
# whole SVG shapes when it starts with "<".
ICONS = {
    "home": "M3 10.5 12 3l9 7.5M5.5 9v11h4.5v-6h4v6h4.5V9",
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20.5 20.5-4.6-4.6"/>',
    "settings": f'<path d="{_gear()}"/><circle cx="12" cy="12" r="3.2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/>',
    "users": '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 7.8M18 14.2a6.5 6.5 0 0 1 3.5 5.8"/>',
    "chat": "M21 11.5a8.5 8.5 0 0 1-12.3 7.6L3.5 20.5l1.4-4.7A8.5 8.5 0 1 1 21 11.5z",
    "message": "M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-9l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z",
    "send": "M21.5 2.5 10.6 13.4M21.5 2.5 14.6 21.5l-4-8.1-8.1-4z",
    "plus": "M12 5v14M5 12h14",
    "minus": "M5 12h14",
    "x": "M6 6l12 12M18 6 6 18",
    "check": "M4.5 12.5l5 5L19.5 7",
    "chevron-down": "m6 9 6 6 6-6",
    "chevron-up": "m6 15 6-6 6 6",
    "chevron-left": "m15 6-6 6 6 6",
    "chevron-right": "m9 6 6 6-6 6",
    "arrow-up": "M12 19V5M6 11l6-6 6 6",
    "arrow-down": "M12 5v14M6 13l6 6 6-6",
    "arrow-left": "M19 12H5M11 6l-6 6 6 6",
    "arrow-right": "M5 12h14M13 6l6 6-6 6",
    "menu": "M4 6.5h16M4 12h16M4 17.5h16",
    "more": "M5 12h.01M12 12h.01M19 12h.01",
    "more-vertical": "M12 5h.01M12 12h.01M12 19h.01",
    "bell": "M6 9a6 6 0 0 1 12 0c0 6.5 2.5 8.5 2.5 8.5h-17S6 15.5 6 9M10.2 21a2 2 0 0 0 3.6 0",
    "star": _star(),
    "heart": "M12 20.5S3 15.2 3 9.2A4.7 4.7 0 0 1 12 7a4.7 4.7 0 0 1 9 2.2c0 6-9 11.3-9 11.3z",
    "trash": "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
    "edit": "M4 20h4.5L19.5 9 15 4.5 4 15.5zM13 6.5l4.5 4.5",
    "compose": "M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6M18.4 3.6a2.1 2.1 0 0 1 3 3L13 15l-4 1 1-4z",
    "copy": '<rect x="8.5" y="8.5" width="12" height="12" rx="2.5"/><path d="M15.5 8.5V6A2.5 2.5 0 0 0 13 3.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5"/>',
    "download": "M12 4v11M7 10l5 5 5-5M5 20h14",
    "upload": "M12 15V4M7 9l5-5 5 5M5 20h14",
    "folder": "M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2.5 2.5h7A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z",
    "file": "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5",
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="16" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "unlock": '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 7.7-1.5"/>',
    "sun": f'<circle cx="12" cy="12" r="4"/><path d="{_rays()}"/>',
    "moon": "M20 14.5A8.5 8.5 0 1 1 9.5 4a6.6 6.6 0 0 0 10.5 10.5z",
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8h.01"/>',
    "warning": "M12 3.8 2.6 19.6h18.8zM12 10v4M12 17h.01",
    "error": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.3h.01"/>',
    "success": '<circle cx="12" cy="12" r="9"/><path d="m8 12.3 2.8 2.8L16.2 9.6"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.3a2.5 2.5 0 1 1 3.4 2.4c-.6.3-1 .9-1 1.6v.7M12 17h.01"/>',
    "bolt": "M13.5 2.5 4.5 14h7l-1 7.5 9-11.5h-7z",
    "sparkle": "M12 3c.7 4.6 2.4 6.3 7 7-4.6.7-6.3 2.4-7 7-.7-4.6-2.4-6.3-7-7 4.6-.7 6.3-2.4 7-7zM19 16.5c.3 1.6.9 2.2 2.5 2.5-1.6.3-2.2.9-2.5 2.5-.3-1.6-.9-2.2-2.5-2.5 1.6-.3 2.2-.9 2.5-2.5z",
    "chart": "M4 20V12M10 20V5M16 20v-9M21.5 20h-19",
    "trend": "M3 17l6-6 4 4 8-8M15 7h6v6",
    "activity": "M3 12h4l3-8 4 16 3-8h4",
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "list": "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
    "layers": "M12 3 2.5 8 12 13l9.5-5zM2.5 12.5 12 17.5l9.5-5M2.5 16.5 12 21.5l9.5-5",
    "play": "M7 4.5v15L19 12z",
    "pause": "M8 5v14M16 5v14",
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "refresh": "M20 11.5A8 8 0 1 0 17.7 17M20 4.5v7h-7",
    "link": "M10 14a4.2 4.2 0 0 0 6 0l3-3a4.2 4.2 0 0 0-6-6l-1 1M14 10a4.2 4.2 0 0 0-6 0l-3 3a4.2 4.2 0 0 0 6 6l1-1",
    "image": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="9.5" r="1.8"/><path d="m21 15.5-5-5L5 20"/>',
    "code": "m8.5 7-5 5 5 5M15.5 7l5 5-5 5",
    "terminal": '<rect x="2.5" y="4" width="19" height="16" rx="2.5"/><path d="m7 9 3 3-3 3M12.5 15h4.5"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "logout": "M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3.5",
    "filter": "M3.5 5h17l-6.5 8v5.5l-4 2V13z",
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "bookmark": "M6 3.5h12v17l-6-4-6 4z",
    "cloud": "M7 19a5 5 0 1 1 .9-9.9 6.3 6.3 0 0 1 11.6 1.4A4.3 4.3 0 0 1 18.5 19z",
    "camera": '<path d="M4 7.5h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.2" r="3.6"/>',
    "mic": '<rect x="9" y="3" width="6" height="11.5" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5v3.5"/>',
    "attach": "M20.5 11.5 12.4 19.6a5.2 5.2 0 0 1-7.4-7.4l8.4-8.4a3.4 3.4 0 0 1 4.8 4.8L9.9 17a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6",
    "sidebar": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M9 4v16"/>',
    "cart": '<path d="M2.5 3.5h2.7l2.4 11.2a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 2-1.5L21 8H6.1"/><circle cx="10" cy="20" r="1.2"/><circle cx="17" cy="20" r="1.2"/>',
    "dollar": "M12 2.5v19M16.5 6.5c-.6-1.5-2.3-2.5-4.5-2.5-2.8 0-4.5 1.5-4.5 3.4C7.5 12 16.5 10 16.5 15.6c0 2-1.9 3.4-4.5 3.4-2.4 0-4.2-1.1-4.8-2.8",
    "flag": "M5 21V4M5 4.5h12.5l-2.5 4 2.5 4H5",
    "pin": '<path d="M12 21s-7-6.1-7-12a7 7 0 0 1 14 0c0 5.9-7 12-7 12z"/><circle cx="12" cy="9" r="2.6"/>',
    "bot": '<rect x="4" y="8" width="16" height="12" rx="3.5"/><path d="M12 4.5V8M9 13.5h.01M15 13.5h.01M9.5 17h5M2 13v2.5M22 13v2.5"/>',
    "smile": '<circle cx="12" cy="12" r="9"/><path d="M8.5 14.5a4.6 4.6 0 0 0 7 0M9 9.5h.01M15 9.5h.01"/>',
    "dot": '<circle cx="12" cy="12" r="4" fill="currentColor"/>',
    "window-minimize": "M6 12h12",
    "window-maximize": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "window-restore": '<rect x="5.5" y="8.5" width="10" height="10" rx="1.5"/><path d="M8.5 8.5V7A1.5 1.5 0 0 1 10 5.5h7A1.5 1.5 0 0 1 18.5 7v7a1.5 1.5 0 0 1-1.5 1.5h-1.5"/>',
    "window-close": "M7 7l10 10M17 7 7 17",
}
ICON_ALIASES = {"close": "x", "cross": "x", "tick": "check", "gear": "settings", "cog": "settings", "delete": "trash",
                "bin": "trash", "pencil": "edit", "new": "compose", "add": "plus", "remove": "minus", "dots": "more",
                "alert": "warning", "danger": "error", "ok": "success", "question": "help", "lightning": "bolt",
                "ai": "sparkle", "magic": "sparkle", "stats": "chart", "graph": "trend", "photo": "image",
                "picture": "image", "attachment": "attach", "paperclip": "attach", "robot": "bot", "location": "pin",
                "money": "dollar", "message-square": "message", "email": "mail", "person": "user", "people": "users",
                "next": "chevron-right", "back": "chevron-left", "up": "chevron-up", "down": "chevron-down"}
ICON_NAMES = tuple(n for n in ICONS if not n.startswith("window-")) + tuple(ICON_ALIASES)
TOAST_ICONS = {"info": "info", "success": "success", "warning": "warning", "error": "error"}


def _vars(theme):
    return "".join(f"--{k}:{v};" for k, v in theme.items())


CSS = """
.at-app{%(dark)s --accent:#3b82f6;--accent-2:#06b6d4;--on-accent:#fff;--font:%(font)s;--mono:%(mono)s;
 --radius:9px;--radius-lg:14px;--green:#22c55e;--yellow:#eab308;--red:#ef4444;--blue:#3b82f6;
 --accent-soft:color-mix(in srgb,var(--accent) 15%%,transparent);--accent-line:color-mix(in srgb,var(--accent) 55%%,transparent);
 position:absolute;inset:0;display:flex;flex-direction:column;background:var(--bg);color:var(--text);
 font:14px/1.45 var(--font);-webkit-font-smoothing:antialiased;color-scheme:dark;overflow:hidden}
.at-app.at-light{%(light)s color-scheme:light}
@media (prefers-color-scheme:light){.at-app.at-system{%(light)s color-scheme:light}}
.at-app *,.at-app *::before,.at-app *::after{box-sizing:border-box}
.at-app ::selection{background:color-mix(in srgb,var(--accent) 35%%,transparent)}
.at-app ::-webkit-scrollbar{width:10px;height:10px}
.at-app ::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--text) 16%%,transparent);border-radius:10px;border:3px solid transparent;background-clip:content-box}
.at-app ::-webkit-scrollbar-thumb:hover{background-color:color-mix(in srgb,var(--text) 28%%,transparent)}
.at-app ::-webkit-scrollbar-track,.at-app ::-webkit-scrollbar-corner{background:transparent}
.at-w{flex-shrink:0;min-width:0;transition:background-color .18s,color .18s,border-color .18s,box-shadow .18s,opacity .18s,scale .16s,translate .18s,rotate .18s,border-radius .18s,filter .18s}
.at-body{flex:1;display:flex;min-height:0;position:relative}
.at-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:12px;padding:24px 28px;overflow:auto;--self:flex-start}
.at-col{display:flex;flex-direction:column;gap:10px;--self:flex-start}
.at-row{display:flex;flex-direction:row;align-items:center;gap:8px;--self:auto}
.at-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));align-items:start;--self:start}
.at-col>.at-grow{flex:1 1 auto;min-height:0}
.at-row>.at-grow,.at-split>.at-grow{flex:1 1 0;min-width:0}
.at-fill{align-self:stretch!important}
.at-row>.at-fill{flex:1 1 0}
.at-scroll{flex:1 1 auto;min-height:0;overflow:auto;padding:2px}
.at-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:18px;box-shadow:var(--shadow)}
.at-card.at-clickable{cursor:pointer}
.at-card.at-clickable:hover{border-color:var(--border-strong)}
.at-side{display:flex;flex-direction:column;gap:6px;width:250px;flex-shrink:0;padding:14px 12px;background:var(--side);overflow:auto;--self:flex-start}
.at-side.at-left{border-right:1px solid var(--border)}
.at-side.at-right{border-left:1px solid var(--border);order:2}
.at-split{display:flex;flex-direction:row;min-height:0;flex:1 1 auto;gap:0;--self:auto;align-items:stretch}
.at-split>.at-col,.at-split>.at-scroll{padding:16px}
.at-handle{width:9px;margin:0 -4px;flex-shrink:0;cursor:col-resize;position:relative;z-index:2}
.at-handle::after{content:"";position:absolute;top:0;bottom:0;left:4px;width:1px;background:var(--border);transition:background-color .15s}
.at-handle:hover::after,.at-handle.at-dragging::after{background:var(--accent);width:2px;left:3.5px}
.at-heading{font-size:22px;line-height:1.25;font-weight:650;letter-spacing:-.015em;margin:0}
.at-text{font-size:14px;color:var(--text);overflow-wrap:anywhere}
.at-small{font-size:12.5px;color:var(--muted);overflow-wrap:anywhere}
.at-heading,.at-text,.at-small{white-space:pre-wrap}
.at-self{align-self:var(--self)}
.at-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:34px;padding:0 14px;border-radius:var(--radius);
 border:1px solid transparent;font:550 13.5px/1 var(--font);cursor:pointer;white-space:nowrap;user-select:none;outline:none;
 align-self:var(--self);background:var(--raised);color:var(--text)}
.at-btn:focus-visible{box-shadow:0 0 0 2px var(--bg),0 0 0 4px var(--accent-line)}
.at-btn:active{scale:.97}
.at-btn .at-i{width:16px;height:16px;flex-shrink:0}
.at-btn.at-only-icon{width:34px;padding:0}
.at-btn.at-only-icon .at-i{width:18px;height:18px}
.at-btn.at-primary{background:var(--accent);color:var(--on-accent);box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 1px 2px rgba(0,0,0,.25)}
.at-btn.at-primary:hover{background:color-mix(in srgb,var(--accent) 86%%,#fff)}
.at-btn.at-gradient{background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;box-shadow:inset 0 1px 0 rgba(255,255,255,.22),0 4px 14px -4px color-mix(in srgb,var(--accent) 60%%,transparent)}
.at-btn.at-gradient:hover{filter:brightness(1.08)}
.at-btn.at-secondary{background:var(--raised);border-color:var(--border)}
.at-btn.at-secondary:hover{background:color-mix(in srgb,var(--raised) 80%%,var(--text) 8%%)}
.at-btn.at-outline{background:transparent;border-color:var(--border-strong)}
.at-btn.at-outline:hover{background:var(--hover)}
.at-btn.at-ghost{background:transparent;color:var(--text)}
.at-btn.at-ghost:hover{background:var(--hover)}
.at-btn.at-success{background:var(--green);color:#fff}
.at-btn.at-success:hover{background:color-mix(in srgb,var(--green) 86%%,#fff)}
.at-btn.at-danger{background:var(--red);color:#fff}
.at-btn.at-danger:hover{background:color-mix(in srgb,var(--red) 86%%,#fff)}
.at-btn:disabled,.at-btn.at-disabled{opacity:.45;pointer-events:none}
.at-input,.at-textarea{width:100%%;height:36px;padding:0 12px;background:var(--field);color:var(--text);border:1px solid var(--border-strong);
 border-radius:var(--radius);font:14px/1.45 var(--font);outline:none;user-select:text}
.at-textarea{height:auto;min-height:38px;max-height:220px;padding:8px 12px;resize:none;field-sizing:content;display:block}
.at-input::placeholder,.at-textarea::placeholder{color:var(--faint)}
.at-input:hover,.at-textarea:hover{border-color:color-mix(in srgb,var(--text) 25%%,transparent)}
.at-input:focus,.at-textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.at-input:disabled,.at-textarea:disabled{opacity:.5}
.at-row>.at-input,.at-row>.at-textarea,.at-row>.at-slider,.at-row>.at-progress{flex:1 1 160px;width:auto}
.at-check{display:inline-flex;align-items:center;gap:10px;cursor:pointer;user-select:none;align-self:var(--self);min-height:24px}
.at-check input{position:absolute;opacity:0;width:1px;height:1px;margin:0;pointer-events:none}
.at-box{width:18px;height:18px;border-radius:5px;border:1.5px solid var(--border-strong);background:var(--field);display:grid;place-items:center;flex-shrink:0;transition:background-color .15s,border-color .15s}
.at-box::after{content:"";width:9px;height:5px;border:2px solid var(--on-accent);border-top:0;border-right:0;rotate:-45deg;translate:0 -1px;scale:0;transition:scale .15s}
.at-check input:checked+.at-box{background:var(--accent);border-color:var(--accent)}
.at-check input:checked+.at-box::after{scale:1}
.at-track{width:36px;height:20px;border-radius:20px;background:color-mix(in srgb,var(--text) 18%%,transparent);position:relative;flex-shrink:0;transition:background-color .18s}
.at-track::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.35);transition:translate .2s cubic-bezier(.3,1.4,.5,1)}
.at-check input:checked+.at-track{background:var(--accent)}
.at-check input:checked+.at-track::after{translate:16px 0}
.at-check input:focus-visible+.at-box,.at-check input:focus-visible+.at-track{box-shadow:0 0 0 3px var(--accent-soft)}
.at-check.at-disabled{opacity:.45;pointer-events:none}
.at-card>.at-switch,.at-dialog-body>.at-switch,.at-side>.at-switch,.at-tabpage>.at-switch{align-self:stretch;justify-content:space-between}
.at-row>.at-text,.at-row>.at-small,.at-row>.at-heading,.at-row>.at-md{flex-shrink:1}
.at-card .at-heading,.at-dialog .at-heading{font-size:17px}
.at-side .at-heading{font-size:18px}
.at-slider{-webkit-appearance:none;appearance:none;width:100%%;height:20px;background:transparent;outline:none;margin:0;cursor:pointer;--p:0%%}
.at-slider::-webkit-slider-runnable-track{height:5px;border-radius:5px;background:linear-gradient(90deg,var(--accent) var(--p),color-mix(in srgb,var(--text) 15%%,transparent) var(--p))}
.at-slider::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;border-radius:50%%;background:#fff;margin-top:-5.5px;box-shadow:0 0 0 1px rgba(0,0,0,.08),0 1px 4px rgba(0,0,0,.4);transition:scale .15s}
.at-slider:hover::-webkit-slider-thumb{scale:1.12}
.at-slider:focus-visible::-webkit-slider-thumb{box-shadow:0 0 0 4px var(--accent-soft)}
.at-slider:disabled{opacity:.45}
.at-dropdown{justify-content:space-between;min-width:150px;background:var(--field);border-color:var(--border-strong);font-weight:450}
.at-dropdown:hover{border-color:color-mix(in srgb,var(--text) 25%%,transparent)}
.at-dropdown .at-i{color:var(--muted)}
.at-dropdown.at-open{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.at-list{display:flex;flex-direction:column;gap:2px;outline:none}
.at-item{display:flex;align-items:center;gap:10px;min-height:36px;padding:6px 10px;border-radius:8px;cursor:pointer;color:var(--text);content-visibility:auto;contain-intrinsic-size:auto 36px}
.at-item:hover{background:var(--hover)}
.at-item.at-selected{background:var(--accent-soft);color:var(--text)}
.at-item.at-selected .at-item-icon{color:var(--accent)}
.at-item-icon{display:grid;place-items:center;color:var(--muted)}
.at-item-icon .at-i{width:17px;height:17px}
.at-item-main{flex:1;min-width:0;display:flex;flex-direction:column}
.at-item-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}
.at-item-sub{font-size:12.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.at-table-wrap{overflow:auto;border:1px solid var(--border);border-radius:var(--radius-lg);background:var(--surface)}
.at-table{width:100%%;border-collapse:collapse;font-size:13.5px}
.at-table th{position:sticky;top:0;background:var(--surface);text-align:left;font-weight:600;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;padding:10px 14px;border-bottom:1px solid var(--border);z-index:1}
.at-table td{padding:10px 14px;border-bottom:1px solid var(--border)}
.at-table tr:last-child td{border-bottom:0}
.at-table tbody tr{cursor:pointer;transition:background-color .12s}
.at-table tbody tr:hover{background:var(--hover)}
.at-table tbody tr.at-selected{background:var(--accent-soft)}
.at-tabs{display:flex;flex-direction:column;gap:14px;min-height:0;--self:flex-start}
.at-tabbar{display:flex;gap:2px;border-bottom:1px solid var(--border);flex-shrink:0}
.at-tab{position:relative;background:none;border:0;color:var(--muted);font:550 13.5px var(--font);padding:9px 12px 11px;cursor:pointer;border-radius:8px 8px 0 0;outline:none}
.at-tab:hover{color:var(--text);background:var(--hover)}
.at-tab::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;background:var(--accent);scale:0 1;transition:scale .2s}
.at-tab.at-active{color:var(--text)}
.at-tab.at-active::after{scale:1 1}
.at-tabpage{flex:1 1 auto;min-height:0}
.at-icon{display:inline-grid;place-items:center;align-self:var(--self);color:inherit;line-height:0}
.at-i{width:1em;height:1em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;overflow:visible}
.at-icon .at-i{width:100%%;height:100%%}
.at-image{display:block;max-width:100%%;border-radius:var(--radius);align-self:var(--self);object-fit:cover}
.at-avatar{width:34px;height:34px;border-radius:50%%;display:grid;place-items:center;flex-shrink:0;font:650 13px/1 var(--font);color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-2));overflow:hidden;align-self:var(--self);user-select:none}
.at-avatar img{width:100%%;height:100%%;object-fit:cover}
.at-badge{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 9px;border-radius:22px;font:600 11.5px/1 var(--font);white-space:nowrap;align-self:var(--self);background:var(--accent-soft);color:color-mix(in srgb,var(--accent) 70%%,var(--text))}
.at-badge.at-gray{background:color-mix(in srgb,var(--text) 9%%,transparent);color:var(--muted)}
.at-badge.at-success{background:color-mix(in srgb,var(--green) 16%%,transparent);color:color-mix(in srgb,var(--green) 75%%,var(--text))}
.at-badge.at-warning{background:color-mix(in srgb,var(--yellow) 18%%,transparent);color:color-mix(in srgb,var(--yellow) 70%%,var(--text))}
.at-badge.at-danger{background:color-mix(in srgb,var(--red) 16%%,transparent);color:color-mix(in srgb,var(--red) 72%%,var(--text))}
.at-badge.at-info{background:color-mix(in srgb,var(--blue) 16%%,transparent);color:color-mix(in srgb,var(--blue) 72%%,var(--text))}
.at-badge.at-outline{background:transparent;border:1px solid var(--border-strong);color:var(--muted)}
.at-badge .at-i{width:12px;height:12px}
.at-progress{height:6px;border-radius:6px;background:color-mix(in srgb,var(--text) 12%%,transparent);overflow:hidden;width:100%%}
.at-bar{height:100%%;width:0;border-radius:6px;background:linear-gradient(90deg,var(--accent),color-mix(in srgb,var(--accent) 60%%,var(--accent-2)));transition:width .35s cubic-bezier(.2,.8,.2,1)}
.at-spinner{display:inline-flex;align-items:center;gap:10px;color:var(--muted);align-self:var(--self)}
.at-ring{width:var(--s,22px);height:var(--s,22px);border-radius:50%%;border:2.5px solid color-mix(in srgb,var(--text) 14%%,transparent);border-top-color:var(--accent);animation:at-spin .8s linear infinite}
.at-spinner.at-stopped .at-ring{animation-play-state:paused;opacity:.4}
@keyframes at-spin{to{rotate:360deg}}
.at-dots{display:inline-flex;gap:4px;align-items:center;height:18px}
.at-dots span{width:7px;height:7px;border-radius:50%%;background:var(--muted);animation:at-bounce 1.2s infinite ease-in-out}
.at-dots span:nth-child(2){animation-delay:.15s}.at-dots span:nth-child(3){animation-delay:.3s}
@keyframes at-bounce{0%%,60%%,100%%{translate:0 0;opacity:.45}30%%{translate:0 -5px;opacity:1}}
.at-divider{height:1px;background:var(--border);flex-shrink:0;align-self:stretch}
.at-row>.at-divider{width:1px;height:auto;align-self:stretch}
.at-md{user-select:text;line-height:1.6;overflow-wrap:anywhere}
.at-md>*:first-child{margin-top:0}.at-md>*:last-child{margin-bottom:0}
.at-md p{margin:0 0 .7em}.at-md h1,.at-md h2,.at-md h3,.at-md h4{margin:1em 0 .45em;line-height:1.3;letter-spacing:-.01em}
.at-md h1{font-size:1.6em}.at-md h2{font-size:1.3em}.at-md h3{font-size:1.1em}.at-md h4{font-size:1em}
.at-md ul,.at-md ol{margin:0 0 .7em;padding-left:1.4em}.at-md li{margin:.2em 0}
.at-md a{color:var(--accent);text-decoration:none}.at-md a:hover{text-decoration:underline}
.at-md blockquote{margin:0 0 .7em;padding:.1em 0 .1em 1em;border-left:3px solid var(--border-strong);color:var(--muted)}
.at-md hr{border:0;border-top:1px solid var(--border);margin:1em 0}
.at-md code{font:.88em var(--mono);background:color-mix(in srgb,var(--text) 9%%,transparent);padding:.15em .4em;border-radius:5px}
.at-md table{border-collapse:collapse;margin:0 0 .7em;font-size:.95em}
.at-md th,.at-md td{border:1px solid var(--border);padding:6px 10px;text-align:left}
.at-md th{background:var(--raised)}
.at-codeblock{background:var(--code-bg);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden;user-select:text;margin:0 0 .7em}
.at-md .at-codeblock code{background:none;padding:0;border-radius:0;font-size:inherit}
.at-code-head{display:flex;align-items:center;justify-content:space-between;padding:6px 8px 6px 14px;font:12px var(--font);color:var(--muted);border-bottom:1px solid var(--border);user-select:none}
.at-copy{display:inline-flex;align-items:center;gap:6px;background:none;border:0;color:var(--muted);font:12px var(--font);padding:4px 8px;border-radius:6px;cursor:pointer}
.at-copy:hover{background:var(--hover);color:var(--text)}
.at-copy .at-i{width:14px;height:14px}
.at-codeblock pre{margin:0;padding:12px 14px;overflow:auto;font:13px/1.55 var(--mono);color:var(--text);tab-size:4}
.at-k{color:#c792ea}.at-s{color:#9ece6a}.at-n{color:#ff9e64}.at-c{color:#6b7280;font-style:italic}.at-f{color:#7aa2f7}
.at-light .at-k{color:#8b3fd9}.at-light .at-s{color:#3c7d1e}.at-light .at-n{color:#c2410c}.at-light .at-f{color:#2563eb}
@media (prefers-color-scheme:light){.at-system .at-k{color:#8b3fd9}.at-system .at-s{color:#3c7d1e}.at-system .at-n{color:#c2410c}.at-system .at-f{color:#2563eb}}
.at-chart{width:100%%;height:100px;display:block;color:var(--accent);overflow:visible}
.at-chart-box{min-width:0}
.at-layer{position:absolute;inset:0;pointer-events:none;z-index:50}
.at-layer>*{pointer-events:auto}
.at-overlay{position:absolute;inset:0;background:var(--scrim);backdrop-filter:blur(3px);display:grid;place-items:center;padding:24px;opacity:0;transition:opacity .18s}
.at-overlay.at-shown{opacity:1}
.at-dialog{width:min(440px,100%%);max-height:100%%;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:16px;box-shadow:var(--shadow-lg);padding:20px 22px;display:flex;flex-direction:column;gap:12px;scale:.96;translate:0 6px;transition:scale .2s cubic-bezier(.2,.9,.3,1.1),translate .2s}
.at-overlay.at-shown .at-dialog{scale:1;translate:0 0}
.at-dialog-title{font-size:17px;font-weight:650}
.at-dialog-title:empty{display:none}
.at-dialog-body{display:flex;flex-direction:column;gap:12px;--self:flex-start}
.at-actions{justify-content:flex-end;margin-top:4px}
.at-menu{position:absolute;min-width:180px;max-width:320px;max-height:70vh;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:11px;padding:5px;box-shadow:var(--shadow-lg);display:none;flex-direction:column;opacity:0;scale:.97;transform-origin:top left;transition:opacity .12s,scale .12s}
.at-menu.at-open{display:flex}
.at-menu.at-shown{opacity:1;scale:1}
.at-mi{display:flex;align-items:center;gap:9px;padding:7px 10px;border-radius:7px;cursor:pointer;font-size:13.5px;white-space:nowrap;color:var(--text)}
.at-mi:hover,.at-mi.at-hot{background:var(--hover)}
.at-mi .at-i{width:16px;height:16px;color:var(--muted)}
.at-mi.at-danger{color:var(--red)}.at-mi.at-danger .at-i{color:var(--red)}
.at-mi.at-checked::after{content:"";margin-left:auto;width:9px;height:5px;border:2px solid var(--accent);border-top:0;border-right:0;rotate:-45deg;translate:0 -2px}
.at-msep{height:1px;background:var(--border);margin:5px 4px}
.at-toasts{position:absolute;right:18px;bottom:18px;display:flex;flex-direction:column;gap:8px;align-items:flex-end;z-index:60;pointer-events:none}
.at-toast{pointer-events:auto;display:flex;align-items:center;gap:10px;min-width:220px;max-width:380px;padding:11px 14px;border-radius:12px;background:var(--surface);border:1px solid var(--border);box-shadow:var(--shadow-lg);font-size:13.5px;animation:at-toast-in .28s cubic-bezier(.2,.9,.3,1.15)}
.at-toast .at-i{width:18px;height:18px;flex-shrink:0;color:var(--accent)}
.at-toast.at-success .at-i{color:var(--green)}.at-toast.at-warning .at-i{color:var(--yellow)}.at-toast.at-error .at-i{color:var(--red)}
.at-toast.at-leaving{animation:at-toast-out .22s ease-in forwards}
@keyframes at-toast-in{from{opacity:0;translate:0 12px;scale:.97}}
@keyframes at-toast-out{to{opacity:0;translate:16px 0}}
.at-tip{position:fixed;z-index:100;pointer-events:none;background:var(--tip);color:var(--tip-text);font:500 12px/1.35 var(--font);padding:6px 9px;border-radius:7px;box-shadow:0 6px 18px rgba(0,0,0,.3);max-width:260px;opacity:0;translate:0 3px;transition:opacity .12s,translate .12s;white-space:pre-wrap}
.at-tip.at-shown{opacity:1;translate:0 0}
.at-titlebar{height:40px;flex-shrink:0;display:flex;align-items:center;gap:10px;padding-left:14px;background:var(--side);border-bottom:1px solid var(--border);user-select:none}
.at-tb-title{font-size:13px;font-weight:600;color:var(--muted);pointer-events:none;white-space:nowrap}
.at-tb-slot{flex:1;display:flex;align-items:center;gap:8px;height:100%%;min-width:0;--self:auto}
.at-tb-buttons{display:flex;height:100%%;align-self:stretch}
.at-wb{width:46px;height:100%%;display:grid;place-items:center;background:none;border:0;color:var(--muted);cursor:default;outline:none}
.at-wb .at-i{width:16px;height:16px;stroke-width:1.4}
.at-wb:hover{background:var(--hover);color:var(--text)}
.at-wb.at-close:hover{background:#e81123;color:#fff}
.at-grip{position:absolute;z-index:200}
.at-grip-r{top:0;right:0;width:5px;bottom:8px;cursor:ew-resize}
.at-grip-b{left:0;right:8px;bottom:0;height:5px;cursor:ns-resize}
.at-grip-rb{right:0;bottom:0;width:12px;height:12px;cursor:nwse-resize}
.at-html{min-width:0}
.at-space{flex-shrink:0}
""" % {"dark": _vars(DARK), "light": _vars(LIGHT), "font": FONT, "mono": MONO}

# The page side of atgui, run once in the window (tv is the engine's window.tuffView). Widgets get a few
# element methods (atAnimate, atOpenMenu...) that Python calls through the engine's generic element calls,
# and page-only behaviour lives here: hover/focus/Enter/shortcut events, tooltips, menus, split handles,
# copy buttons, links, and keeping the page from reloading or navigating away.
JS = r"""
const at = window.__at = { keys: new Set(), menu: null, last: null, resize: null };
const emit = tv.emit;
const pathOf = (el) => { const out = []; for (; el && el !== document.body; el = el.parentNode) if (el._tv !== undefined) out.push(el._tv); return out; };
const near = (el, sel) => (el && el.closest ? el.closest(sel) : null);
const P = HTMLElement.prototype;

// icons: one sprite, used by <svg><use href="#at-i-name"/></svg>
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const box = document.createElementNS(NS, 'svg');
  box.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden');
  let html = '';
  for (const [name, d] of Object.entries(ICONS)) html += `<symbol id="at-i-${name}" viewBox="0 0 24 24">${d[0] === '<' ? d : `<path d="${d}"/>`}</symbol>`;
  box.innerHTML = html;
  document.body.appendChild(box);
})();

// ---- animations (Web Animations API)
const ANIMS = {
  'fade-in': [{ opacity: 0 }, { opacity: 1 }],
  'fade-out': [{ opacity: 1 }, { opacity: 0 }],
  'slide-up': [{ opacity: 0, translate: '0 14px' }, { opacity: 1, translate: '0 0' }],
  'slide-down': [{ opacity: 0, translate: '0 -14px' }, { opacity: 1, translate: '0 0' }],
  'slide-left': [{ opacity: 0, translate: '18px 0' }, { opacity: 1, translate: '0 0' }],
  'slide-right': [{ opacity: 0, translate: '-18px 0' }, { opacity: 1, translate: '0 0' }],
  'pop': [{ opacity: 0, scale: 0.85 }, { opacity: 1, scale: 1.03, offset: 0.7 }, { opacity: 1, scale: 1 }],
  'zoom-in': [{ opacity: 0, scale: 0.92 }, { opacity: 1, scale: 1 }],
  'zoom-out': [{ opacity: 1, scale: 1 }, { opacity: 0, scale: 0.92 }],
  'bounce': [{ translate: '0 0' }, { translate: '0 -10px', offset: 0.3 }, { translate: '0 0', offset: 0.55 }, { translate: '0 -4px', offset: 0.75 }, { translate: '0 0' }],
  'shake': [{ translate: '0 0' }, { translate: '-7px 0' }, { translate: '7px 0' }, { translate: '-5px 0' }, { translate: '5px 0' }, { translate: '-2px 0' }, { translate: '0 0' }],
  'pulse': [{ scale: 1 }, { scale: 1.06 }, { scale: 1 }],
  'spin': [{ rotate: '0deg' }, { rotate: '360deg' }],
  'wiggle': [{ rotate: '0deg' }, { rotate: '-6deg' }, { rotate: '6deg' }, { rotate: '-4deg' }, { rotate: '4deg' }, { rotate: '0deg' }],
  'float': [{ translate: '0 0' }, { translate: '0 -6px' }, { translate: '0 0' }],
  'blink': [{ opacity: 1 }, { opacity: 0.25 }, { opacity: 1 }],
};
const ANIM_MS = { 'spin': 900, 'pulse': 600, 'shake': 450, 'wiggle': 500, 'bounce': 700, 'float': 2200, 'blink': 1000, 'pop': 320 };
P.atAnimate = function (name, ms, times) {
  for (const a of this.getAnimations()) if (a.id === 'at') a.cancel();
  if (name === 'none') return null;
  const frames = ANIMS[name];
  if (!frames) throw new Error(`there's no animation called '${name}'`);
  const out = /out$/.test(name);
  const a = this.animate(frames, { duration: ms || ANIM_MS[name] || 260, easing: name === 'spin' ? 'linear' : 'cubic-bezier(.2,.8,.2,1)', iterations: times === -1 ? Infinity : (times || 1), fill: out ? 'forwards' : 'none' });
  a.id = 'at';
  return null;
};

// ---- state styles (hover, pressed, focus): one CSS rule per element and state
const sheet = new CSSStyleSheet();
document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
const rules = new Map();
P.atRule = function (state, prop, value) {
  const key = this._tv + ' ' + state;
  let rule = rules.get(key);
  if (!rule) {
    this.setAttribute('data-at', this._tv);
    const sel = { hover: ':hover', pressed: ':active', focus: ':focus-within', selected: '.at-selected' }[state] || ':hover';
    sheet.insertRule(`.at-app [data-at="${this._tv}"]${sel}{}`, sheet.cssRules.length);
    rule = sheet.cssRules[sheet.cssRules.length - 1];
    rules.set(key, rule);
  }
  if (value == null) rule.style.removeProperty(prop); else rule.style.setProperty(prop, value, 'important');
  return null;
};
P.atCss = function (text) { this.style.cssText += ';' + text; return null; };
P.atClass = function (name, on) { this.classList.toggle(name, !!on); return null; };
P.atOpen = function () {
  this.style.display = '';
  void this.offsetWidth;
  this.classList.add('at-shown');
  const f = this.querySelector('input:not([type=checkbox]),textarea');
  if (f) setTimeout(() => f.focus(), 30);
  return null;
};
P.atShut = function () {
  this.classList.remove('at-shown');
  setTimeout(() => { if (!this.classList.contains('at-shown')) this.style.display = 'none'; }, 200);
  return null;
};
P.atLeave = function (ms) { this.classList.add('at-leaving'); return null; };

// ---- scrolling
P.atToEnd = function (smooth) { this.scrollTo({ top: this.scrollHeight, behavior: smooth ? 'smooth' : 'instant' }); return null; };
P.atToTop = function (smooth) { this.scrollTo({ top: 0, behavior: smooth ? 'smooth' : 'instant' }); return null; };
P.atFocus = function () { this.focus(); if (this.setSelectionRange && /text|search|password|textarea/.test(this.type || 'textarea')) { const n = this.value.length; this.setSelectionRange(n, n); } return null; };

// ---- menus (context menus, dropdowns, m:open)
function closeMenu() {
  const m = at.menu;
  if (!m) return;
  at.menu = null;
  m.classList.remove('at-shown', 'at-open');
  if (m._anchor) m._anchor.classList.remove('at-open');
}
function placeMenu(m, x, y, below) {
  const layer = m.parentNode.getBoundingClientRect();
  m.classList.add('at-open');
  const r = m.getBoundingClientRect();
  if (below) { y = below.bottom + 4; x = below.left; m.style.minWidth = Math.max(180, below.width) + 'px'; if (y + r.height > innerHeight - 8) y = below.top - r.height - 4; }
  x = Math.max(8, Math.min(x, innerWidth - r.width - 8));
  y = Math.max(8, Math.min(y, innerHeight - r.height - 8));
  m.style.left = (x - layer.left) + 'px';
  m.style.top = (y - layer.top) + 'px';
  requestAnimationFrame(() => m.classList.add('at-shown'));
}
P.atOpenMenu = function (anchorId) {
  if (at.menu === this) { closeMenu(); return null; }
  closeMenu();
  const anchor = anchorId ? tv.node(anchorId).el : at.last;
  at.menu = this;
  this._anchor = anchorId ? anchor : null;
  if (this._anchor) this._anchor.classList.add('at-open');
  if (anchor && anchor.isConnected) placeMenu(this, 0, 0, anchor.getBoundingClientRect());
  else placeMenu(this, at.mx || 40, at.my || 40);
  return null;
};
P.atCloseMenu = function () { if (at.menu === this) closeMenu(); return null; };
addEventListener('pointerdown', (e) => {
  at.mx = e.clientX; at.my = e.clientY;
  const w = near(e.target, '.at-w');
  if (w) at.last = w;
  if (at.menu && !at.menu.contains(e.target) && !(at.menu._anchor && at.menu._anchor.contains(e.target))) closeMenu();
}, true);
addEventListener('click', (e) => { if (at.menu && near(e.target, '.at-mi')) setTimeout(closeMenu, 0); });
addEventListener('contextmenu', (e) => {
  const owner = near(e.target, '[data-at-menu]');
  if (!owner) return;
  e.preventDefault();
  closeMenu();
  const m = tv.node(+owner.getAttribute('data-at-menu')).el;
  at.menu = m;
  placeMenu(m, e.clientX, e.clientY);
  emit('at-context', { menu: m._tv, path: pathOf(e.target) });
});
addEventListener('blur', closeMenu);

// ---- hover, focus, Enter
document.addEventListener('pointerover', (e) => {
  const el = near(e.target, '[data-at-hover]');
  if (el && !(e.relatedTarget && el.contains(e.relatedTarget))) emit('at-hover', { id: el._tv, path: pathOf(el), on: true });
});
document.addEventListener('pointerout', (e) => {
  const el = near(e.target, '[data-at-hover]');
  if (el && !(e.relatedTarget && el.contains(e.relatedTarget))) emit('at-hover', { id: el._tv, path: pathOf(el), on: false });
});
document.addEventListener('focusin', (e) => { const el = near(e.target, '[data-at-focus]'); if (el && !(e.relatedTarget && el.contains(e.relatedTarget))) emit('at-focus', { id: el._tv, path: pathOf(el), on: true }); });
document.addEventListener('focusout', (e) => { const el = near(e.target, '[data-at-focus]'); if (el && !(e.relatedTarget && el.contains(e.relatedTarget))) emit('at-focus', { id: el._tv, path: pathOf(el), on: false }); });

// ---- keys: Enter in text boxes, shortcuts, Escape, and no reloading or going back
function combo(e) {
  let k = e.key.toLowerCase();
  if (/^Key[A-Z]$/.test(e.code)) k = e.code.slice(3).toLowerCase();
  else if (/^Digit\d$/.test(e.code)) k = e.code.slice(5);
  else k = { ' ': 'space', 'arrowup': 'up', 'arrowdown': 'down', 'arrowleft': 'left', 'arrowright': 'right', 'esc': 'escape', 'del': 'delete' }[k] || k;
  const mac = /Mac/.test(navigator.platform);
  return [(e.ctrlKey || (mac && e.metaKey)) && 'ctrl', e.altKey && 'alt', e.shiftKey && 'shift', k].filter(Boolean).join('+');
}
const BLOCKED = new Set(['f5', 'ctrl+r', 'ctrl+shift+r', 'f3', 'ctrl+f', 'ctrl+g', 'ctrl+p', 'ctrl+u', 'f7', 'alt+left', 'alt+right', 'ctrl+shift+i', 'f12', 'ctrl+=', 'ctrl+-', 'ctrl+0', 'browserback', 'browserforward', 'browserrefresh']);
addEventListener('keydown', (e) => {
  const t = e.target;
  if (e.key === 'Enter' && !e.isComposing && t && t.hasAttribute && t.hasAttribute('data-at-enter') && !(t.tagName === 'TEXTAREA' && e.shiftKey)) {
    e.preventDefault();
    emit('at-enter', { id: t._tv, path: pathOf(t), value: t.value });
    return;
  }
  if (e.key === 'Escape') {
    if (at.menu) { closeMenu(); e.preventDefault(); return; }
    const shown = document.querySelectorAll('.at-overlay.at-shown');
    const o = shown[shown.length - 1];
    if (o) { emit('at-dismiss', { id: o._tv, path: pathOf(o) }); e.preventDefault(); return; }
  }
  const c = combo(e);
  const typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
  if (at.keys.has(c) && (!typing || /ctrl|alt|^f\d|escape/.test(c))) {
    e.preventDefault();
    if (!e.repeat || /ctrl|alt/.test(c)) emit('at-key', { combo: c });
    return;
  }
  if (BLOCKED.has(c)) e.preventDefault();
}, true);
P.atKeys = function (list) { at.keys = new Set(list); return null; };
addEventListener('mouseup', (e) => { if (e.button === 3 || e.button === 4) e.preventDefault(); });
addEventListener('dragover', (e) => e.preventDefault());
addEventListener('drop', (e) => e.preventDefault());

// ---- links open in the browser (through Python), never inside the app
document.addEventListener('click', (e) => {
  const a = near(e.target, 'a[href]');
  if (!a) return;
  e.preventDefault();
  const href = a.getAttribute('href');
  if (/^(https?:|mailto:)/i.test(href)) emit('at-link', { href });
}, true);

// ---- overlays: a click on the dimmed part dismisses
document.addEventListener('pointerdown', (e) => {
  if (e.target.classList && e.target.classList.contains('at-overlay') && e.target.classList.contains('at-shown')) emit('at-dismiss', { id: e.target._tv, path: pathOf(e.target) });
});

// ---- copy buttons on code blocks
document.addEventListener('click', (e) => {
  const b = near(e.target, '.at-copy');
  if (!b) return;
  const pre = b.closest('.at-codeblock').querySelector('pre');
  const done = () => { const old = b.lastChild.textContent; b.lastChild.textContent = 'Copied'; setTimeout(() => { b.lastChild.textContent = old === 'Copied' ? 'Copy' : old; }, 1200); };
  if (navigator.clipboard) navigator.clipboard.writeText(pre.textContent).then(done, () => {});
});

// ---- sliders show how far along they are
document.addEventListener('input', (e) => { const t = e.target; if (t.classList && t.classList.contains('at-slider')) t.style.setProperty('--p', ((t.value - t.min) / ((t.max - t.min) || 1) * 100) + '%'); });

// ---- tooltips
let tip = null, tipFor = null, tipTimer = 0;
function hideTip() { clearTimeout(tipTimer); tipFor = null; if (tip) tip.classList.remove('at-shown'); }
document.addEventListener('pointerover', (e) => {
  const el = near(e.target, '[data-at-tip]');
  if (el === tipFor) return;
  hideTip();
  if (!el) return;
  tipFor = el;
  tipTimer = setTimeout(() => {
    if (!tip) { tip = document.createElement('div'); tip.className = 'at-tip'; (document.querySelector('.at-app') || document.body).appendChild(tip); }
    tip.textContent = el.getAttribute('data-at-tip');
    const r = el.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    let y = r.top - t.height - 8;
    if (y < 6) y = r.bottom + 8;
    tip.style.left = Math.max(6, Math.min(innerWidth - t.width - 6, r.left + r.width / 2 - t.width / 2)) + 'px';
    tip.style.top = y + 'px';
    tip.classList.add('at-shown');
  }, 450);
});
document.addEventListener('pointerdown', hideTip, true);
addEventListener('blur', hideTip);

// ---- split panes: drag the handle
document.addEventListener('pointerdown', (e) => {
  const h = near(e.target, '.at-handle');
  if (!h) return;
  const pane = h.previousElementSibling;
  if (!pane) return;
  e.preventDefault();
  h.setPointerCapture(e.pointerId);
  h.classList.add('at-dragging');
  const x0 = e.clientX;
  const w0 = pane.getBoundingClientRect().width;
  const max = h.parentNode.getBoundingClientRect().width - 120;
  const move = (ev) => { pane.style.width = Math.max(80, Math.min(max, w0 + ev.clientX - x0)) + 'px'; };
  const up = () => { h.classList.remove('at-dragging'); h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up); };
  h.addEventListener('pointermove', move);
  h.addEventListener('pointerup', up);
});

// ---- frameless windows: resize from the right and bottom edges (Python moves the real window)
P.atGrips = function () {
  for (const side of ['r', 'b', 'rb']) {
    const g = document.createElement('div');
    g.className = 'at-grip at-grip-' + side;
    g.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      g.setPointerCapture(e.pointerId);
      const sx = e.screenX, sy = e.screenY, w = innerWidth, h = innerHeight;
      let queued = null;
      const move = (ev) => {
        const size = { w: side === 'b' ? w : Math.max(320, w + ev.screenX - sx), h: side === 'r' ? h : Math.max(220, h + ev.screenY - sy) };
        if (!queued) requestAnimationFrame(() => { emit('at-resize', queued); queued = null; });
        queued = size;
      };
      const up = () => { g.removeEventListener('pointermove', move); g.removeEventListener('pointerup', up); };
      g.addEventListener('pointermove', move);
      g.addEventListener('pointerup', up);
    });
    this.appendChild(g);
  }
  return null;
};
"""


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def icon_svg(name, cls="at-i"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#at-i-{name}"/></svg>'


# ---------------------------------------------------------------- code highlighting and markdown

KEYWORDS = {
    "tuff": "func return if elif else then while for in break continue and or not is true false nil say input flush import mention",
    "python": "def return if elif else while for in break continue and or not is True False None import from as class try except "
              "finally with lambda pass yield global nonlocal raise assert del async await",
    "js": "function return if else while for in of break continue const let var new class this true false null undefined "
          "import export from async await try catch finally throw typeof instanceof switch case default",
    "shell": "if then else fi for do done while case esac function in echo cd export",
}
LANGS = {"tuff": "tuff", "tuf": "tuff", "py": "python", "python": "python", "js": "js", "javascript": "js", "ts": "js",
         "typescript": "js", "json": "js", "java": "js", "c": "js", "cpp": "js", "cs": "js", "go": "js", "rust": "js",
         "sh": "shell", "bash": "shell", "shell": "shell", "powershell": "shell", "ps1": "shell"}
TOKEN = re.compile(r'(?P<c>#[^\n]*|//[^\n]*|/\*.*?\*/)|(?P<s>"(?:\\.|[^"\\\n])*"?|\'(?:\\.|[^\'\\\n])*\'?|`(?:\\.|[^`\\])*`?)'
                   r'|(?P<n>\b\d+(?:\.\d+)?\b)|(?P<w>[A-Za-z_]\w*)(?P<p>\s*\()?', re.S)


def highlight(code, lang):
    """Code as HTML with a few colours. Unknown languages are only escaped."""
    lang = LANGS.get(str(lang or "").lower())
    if not lang:
        return esc(code)
    words = set(KEYWORDS[lang].split())
    hash_comments = lang in ("tuff", "python", "shell")
    out = []
    pos = 0
    for m in TOKEN.finditer(code):
        out.append(esc(code[pos:m.start()]))
        pos = m.end()
        text = m.group(0)
        if m.group("c") is not None:
            if text.startswith("#") != hash_comments:  # '#' isn't a comment in JS; '//' isn't in Python
                if text.startswith("#"):
                    out.append(esc(text[0]))
                    pos = m.start() + 1
                else:
                    out.append(esc(text[:1]))
                    pos = m.start() + 1
                continue
            out.append(f'<span class="at-c">{esc(text)}</span>')
        elif m.group("s") is not None:
            out.append(f'<span class="at-s">{esc(text)}</span>')
        elif m.group("n") is not None:
            out.append(f'<span class="at-n">{text}</span>')
        else:
            word, paren = m.group("w"), m.group("p") or ""
            if word in words:
                out.append(f'<span class="at-k">{word}</span>{esc(paren)}')
            elif paren:
                out.append(f'<span class="at-f">{word}</span>{esc(paren)}')
            else:
                out.append(word)
    out.append(esc(code[pos:]))
    return "".join(out)


def code_html(code, lang):
    label = esc(lang) if lang else "code"
    return (f'<div class="at-codeblock"><div class="at-code-head"><span>{label}</span>'
            f'<button class="at-copy" tabindex="-1">{icon_svg("copy")}<span>Copy</span></button></div>'
            f'<pre><code>{highlight(code, lang)}</code></pre></div>')


INLINE = [
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w_])__(?=\S)(.+?)(?<=\S)__(?![\w_])"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])"), r"<em>\1</em>"),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~"), r"<del>\1</del>"),
]
LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|mailto:)[^)\s]+)\)")


def inline(text):
    """Markdown inside a line: `code`, **bold**, *italic*, ~~struck~~ and [links](https://...)."""
    codes = []

    def keep(m):
        codes.append(f"<code>{esc(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep, text)
    text = esc(text)
    text = LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    for pattern, repl in INLINE:
        text = pattern.sub(repl, text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def markdown(src):
    """A small Markdown to HTML converter: headings, paragraphs, lists, quotes, code blocks, tables, rules."""
    lines = str(src).replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    n = len(lines)

    def starts_block(line):
        return bool(re.match(r"^\s*(```|#{1,6}\s|>|([-*_])\s*\2\s*\2)", line) or LIST_ITEM.match(line))

    while i < n:
        line = lines[i]
        fence = re.match(r"^\s*```\s*([\w+#-]*)", line)
        if fence:
            body = []
            i += 1
            while i < n and not re.match(r"^\s*```\s*$", lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            out.append(code_html("\n".join(body), fence.group(1)))
            continue
        if not line.strip():
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", line)
        if h:
            level = min(4, len(h.group(1)))
            out.append(f"<h{level}>{inline(h.group(2))}</h{level}>")
            i += 1
            continue
        if re.match(r"^\s*([-*_])\s*(\1\s*){2,}$", line):
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith(">"):
            quote = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{markdown(chr(10).join(quote))}</blockquote>")
            continue
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", lines[i + 1]):
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table>")
            continue
        item = LIST_ITEM.match(line)
        if item:
            ordered = item.group(2)[0].isdigit()
            items = []
            while i < n:
                m = LIST_ITEM.match(lines[i])
                if m and (m.group(2)[0].isdigit()) == ordered:
                    items.append(m.group(3))
                elif m or not lines[i].strip() or starts_block(lines[i]):
                    break
                elif items:
                    items[-1] += "\n" + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x).replace(chr(10), '<br>')}</li>" for x in items) + f"</{tag}>")
            continue
        para = []
        while i < n and lines[i].strip() and not starts_block(lines[i]) and not (
                "|" in lines[i] and i + 1 < n and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1])):
            para.append(lines[i].strip())
            i += 1
        if not para:  # a line that looked like a block start but wasn't one
            para.append(lines[i].strip())
            i += 1
        out.append("<p>" + "<br>".join(inline(p) for p in para) + "</p>")
    return "".join(out)


def chart_svg(values, kind, uid=0):
    """A small chart (an area line or bars) as SVG that stretches to its box."""
    vals = [float(v) for v in values] or [0.0]
    hi, lo = max(vals), min(min(vals), 0.0)
    span = (hi - lo) or 1.0
    w, h = 100.0, 40.0
    if kind == "bar":
        n = len(vals)
        gap = 0.28 * w / n
        bw = w / n - gap
        bars = []
        for i, v in enumerate(vals):
            bh = max(0.6, (v - lo) / span * (h - 1))
            bars.append(f'<rect x="{i * w / n + gap / 2:.2f}" y="{h - bh:.2f}" width="{bw:.2f}" height="{bh:.2f}" rx="0.8" fill="currentColor"/>')
        body = "".join(bars)
    else:
        step = w / max(1, len(vals) - 1)
        pts = [(i * step, h - 1 - (v - lo) / span * (h - 4)) for i, v in enumerate(vals)]
        if len(pts) == 1:
            pts.append((w, pts[0][1]))
        line = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        body = (f'<defs><linearGradient id="at-fade{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" '
                f'stop-opacity=".3"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>'
                f'<polygon points="0,{h} {line} {w},{h}" fill="url(#at-fade{uid})"/>'
                f'<polyline points="{line}" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke" '
                f'stroke-linejoin="round" stroke-linecap="round"/>')
    return f'<svg class="at-chart" viewBox="0 0 {w:g} {h:g}" preserveAspectRatio="none">{body}</svg>'


# ---------------------------------------------------------------- colours and style names

def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def is_hex(text):
    return bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", text))


def on_color(h):
    """White or near-black text, whichever reads better on this colour."""
    try:
        r, g, b = hex_rgb(h)
    except ValueError:
        return "#ffffff"
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return "#111214" if lum > 0.62 else "#ffffff"


def system_light():
    """Is Windows using its light theme for apps?"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 1
    except OSError:
        return False


# Friendly style names -> (CSS property, what the value is). "px": numbers become pixels.
STYLES = {
    "background": ("background", "paint"), "bg": ("background", "paint"), "color": ("color", "color"),
    "text color": ("color", "color"), "gradient": ("background", "gradient"),
    "radius": ("border-radius", "px"), "corners": ("border-radius", "px"), "round": ("border-radius", "px"),
    "padding": ("padding", "px"), "margin": ("margin", "px"), "gap": ("gap", "px"),
    "width": ("width", "px"), "height": ("height", "px"), "min width": ("min-width", "px"), "max width": ("max-width", "px"),
    "min height": ("min-height", "px"), "max height": ("max-height", "px"),
    "border": ("border", "border"), "border color": ("border-color", "color"), "shadow": ("box-shadow", "shadow"),
    "blur": ("backdrop-filter", "blur"), "glass": ("backdrop-filter", "glass"), "opacity": ("opacity", "opacity"),
    "size": ("font-size", "px"), "font size": ("font-size", "px"), "text size": ("font-size", "px"),
    "weight": ("font-weight", "weight"), "bold": ("font-weight", "bold"), "italic": ("font-style", "italic"),
    "font": ("font-family", "font"), "align": ("text-align", "plain"), "text align": ("text-align", "plain"),
    "scale": ("scale", "plain"), "rotate": ("rotate", "deg"), "move": ("translate", "move"),
    "cursor": ("cursor", "plain"), "letter spacing": ("letter-spacing", "px"), "line height": ("line-height", "plain"),
    "underline": ("text-decoration", "underline"), "uppercase": ("text-transform", "upper"),
    "transition": ("transition-duration", "seconds"), "z": ("z-index", "plain"), "span": ("grid-column", "span"),
    "selectable": ("user-select", "select"), "wrap": ("white-space", "wrap"), "overflow": ("overflow", "plain"),
}
STATES = ("hover", "pressed", "focus", "selected")
SHADOWS = {"none": "none", "small": "var(--shadow)", "sm": "var(--shadow)",
           "medium": "0 6px 20px -6px rgba(0,0,0,.45), 0 2px 6px rgba(0,0,0,.2)",
           "md": "0 6px 20px -6px rgba(0,0,0,.45), 0 2px 6px rgba(0,0,0,.2)", "large": "var(--shadow-lg)", "lg": "var(--shadow-lg)",
           "glow": "0 0 0 1px color-mix(in srgb,var(--accent) 50%,transparent), 0 8px 30px -6px color-mix(in srgb,var(--accent) 60%,transparent)",
           "inner": "inset 0 2px 6px rgba(0,0,0,.25)"}


class Scene:
    """The window's objects, before and after the window opens.

    Until the window is open, every change is recorded with the same ids the engine will give it; open()
    replays them in order, so the program's first screen arrives in one batch."""

    def __init__(self):
        self.view = None
        self.ops = []
        self.ids = itertools.count(1)

    def el(self, tag, parent=0, **props):
        if self.view is not None:
            return int(self.view.el(tag, parent, **props))
        id_ = next(self.ids)
        self.ops.append(("el", id_, tag, int(parent or 0), props))
        return id_

    def set(self, id_, **props):
        if self.view is not None:
            self.view.set(id_, **props)
        else:
            self.ops.append(("set", id_, props))

    def remove(self, id_):
        if self.view is not None:
            self.view.remove(id_)
        else:
            self.ops.append(("remove", id_))

    def call(self, id_, method, *args):
        if self.view is not None:
            self.view.call(id_, method, *args)
        else:
            self.ops.append(("call", id_, method, args))

    def attach(self, view):
        ops, self.ops = self.ops, []
        self.view = view
        for op in ops:
            if op[0] == "el":
                got = int(view.el(op[2], op[3], **op[4]))
                if got != op[1]:
                    raise RuntimeError(f"atgui: the window gave object {got} where {op[1]} was expected")
            elif op[0] == "set":
                view.set(op[1], **op[2])
            elif op[0] == "remove":
                view.remove(op[1])
            elif op[0] == "js":
                view.js(op[1])
            else:
                view.call(op[1], op[2], *op[3])

    def js(self, code):
        if self.view is not None:
            self.view.js(code)
        else:
            self.ops.append(("js", code))


# ---------------------------------------------------------------- the library

NOTHING = object()  # an input that wasn't given (nil is a real value for some methods)
ROUTED = ("click", "dblclick", "input", "change", "at-enter", "at-hover", "at-focus", "at-context", "at-dismiss")
KEY_NAMES = {"esc": "escape", "return": "enter", "del": "delete", "spacebar": "space", "arrowup": "up",
             "arrowdown": "down", "arrowleft": "left", "arrowright": "right", "plus": "=", "pgup": "pageup", "pgdn": "pagedown"}
KEYS_OK = {"enter", "escape", "space", "tab", "up", "down", "left", "right", "delete", "backspace", "home", "end",
           "pageup", "pagedown", "insert"} | {f"f{i}" for i in range(1, 13)}
MODIFIERS = {"ctrl": "ctrl", "control": "ctrl", "cmd": "ctrl", "command": "ctrl", "meta": "ctrl", "mod": "ctrl",
             "alt": "alt", "option": "alt", "shift": "shift"}


def key_combo(text):
    """'Ctrl + S' -> 'ctrl+s', the way the page names a key press; None if it isn't a key."""
    raw = str(text).replace(" ", "").lower()
    if raw.endswith("++"):
        parts = raw[:-2].split("+") + ["="]
        parts = [p for p in parts if p] if parts[0] else parts[1:]
    else:
        parts = raw.split("+")
    if not parts or not parts[-1]:
        return None
    mods = set()
    for p in parts[:-1]:
        if p not in MODIFIERS:
            return None
        mods.add(MODIFIERS[p])
    key = KEY_NAMES.get(parts[-1], parts[-1])
    if not (len(key) == 1 or key in KEYS_OK):
        return None
    return "+".join([m for m in ("ctrl", "alt", "shift") if m in mods] + [key])


class Lib:
    """One per program: the window, the handlers for what happens in it, the timers, and error reporting."""

    def __init__(self, rt):
        self.rt = rt
        self.app = None
        self.view = None
        self.handlers = {}  # element id -> {event type: python function(event)}
        self.timers = []
        self.ticking = False
        self.reported = set()
        self.menus = {}
        self.tuff = sys.modules.get(type(rt).__module__)  # tuff.py itself, for report()
        self.error_type = type(rt.error(""))

    # ---- values from Tuff
    def text(self, v):
        v = self.rt.plain(v)
        return "" if v is None else self.rt.text(v)

    def num(self, v, what):
        return self.rt.number(v, what)

    def check_fn(self, fn, what):
        if fn is None or self.rt.callable(fn):
            return fn
        raise self.rt.error(f"{what} needs a function name, like clicked (without brackets).")

    def widget(self, v, kind, what):
        w = getattr(self.rt.plain(v), "at", None)
        if not isinstance(w, Widget) or (kind and w.kind != kind):
            raise self.rt.error(f"{what} needs {kind_name(kind)}, not {self.rt.what(v)}.")
        return w

    def color(self, value, what="This"):
        text = self.text(value).strip()
        low = text.lower()
        if low in NAMED_COLORS:
            return NAMED_COLORS[low]
        if is_hex(low) or low.startswith(("rgb", "hsl", "color-mix", "var(", "oklch")):
            return text
        raise self.rt.error(f"'{text}' isn't a color I know. Try {', '.join(ACCENTS)}, white, black, or a hex code like \"#ff8800\".")

    def image_url(self, path, what="An image"):
        text = self.text(path).strip()
        if re.match(r"^(https?:|data:)", text, re.I):
            return text
        base = os.path.abspath(self.rt.interp.base_dir)
        full = os.path.abspath(text if os.path.isabs(text) else os.path.join(base, text))
        if not os.path.isfile(full):
            raise self.rt.error(f"Couldn't find the image '{text}'. Put the picture in your project folder (next to your .tuf file).")
        if not full.lower().endswith(IMAGE_EXTS):
            raise self.rt.error(f"'{text}' isn't a picture. Use a .png, .jpg, .gif, .webp or .svg file.")
        rel = os.path.relpath(full, base)
        if rel.startswith(".."):
            raise self.rt.error(f"'{text}' is outside your project folder. Put the picture in your project folder.")
        return "assets/" + urllib.parse.quote(rel.replace(os.sep, "/"))

    # ---- events
    def on(self, id_, type_, fn):
        self.handlers.setdefault(id_, {})[type_] = fn

    def forget(self, widget):
        stack = [widget]
        while stack:
            w = stack.pop()
            w.dead = True
            self.handlers.pop(w.id, None)
            for extra in w.extra_ids:
                self.handlers.pop(extra, None)
            stack.extend(w.children)
            stack.extend(getattr(w, "pages", ()))

    def route(self, e):
        t = e.get("type")
        for i in e.get("path") or ():
            fns = self.handlers.get(i)
            if fns and t in fns:
                fns[t](e)
                return

    def fire(self, fn, *args):
        """Run an event function. A Tuff error is reported once (the same line and message only the first time)."""
        if fn is None:
            return True
        if callable(fn):
            fn(*args)
            return True
        try:
            self.rt.interp.invoke(fn, list(args), loose=True)
            return True
        except self.error_type as err:
            if err.line is None and getattr(fn, "line", None):
                err.line = fn.line
            self.report(err)
        except RecursionError:
            self.report(self.error_type(f"{getattr(fn, 'name', 'This function')}() called itself too many times.", getattr(fn, "line", None)))
        except Exception as exc:
            if type(exc).__name__ not in ("BreakSignal", "ContinueSignal", "ReturnSignal"):
                raise
            self.report(self.error_type("'break' and 'continue' can only be used inside a loop.", getattr(exc, "line", None), getattr(exc, "col", None)))
        return False

    def report(self, err):
        key = (err.line, err.col, err.msg)
        if key in self.reported:
            return
        self.reported.add(key)
        report = getattr(self.tuff, "report", None)
        if report is not None:
            report(err, self.rt.interp.src)
        else:
            sys.stderr.write(f"Tuff error: {err}\n")
            sys.stderr.flush()

    def view_error(self, exc, where):
        """Problems the engine found: errors in the page, or a bug in atgui itself."""
        if isinstance(exc, self.error_type):
            self.report(exc)
        else:
            self.report(self.error_type(f"atgui had a problem ({where}): {exc}"))

    # ---- timers
    # The engine's loop() only wakes up for every-frame functions it had when it last went to sleep, so the
    # timer tick is registered once, when the window opens, and stays. While no timer is waiting it runs at
    # IDLE_FPS, which keeps an idle app nearly asleep; a new timer is first looked at within 1 / IDLE_FPS s.
    IDLE_FPS = 20

    def add_timer(self, timer):
        self.timers.append(timer)
        if self.view is not None:
            self.view.fps = 60

    def start_timers(self):
        now = time.perf_counter()
        for t in self.timers:
            if t.due is None:
                t.due = now + t.period
        self.view.fps = 60 if self.timers else self.IDLE_FPS
        self.view.every_frame(self.tick)

    def tick(self, _dt=0.0):
        now = time.perf_counter()
        for t in list(self.timers):
            if not t.active:
                if t in self.timers:
                    self.timers.remove(t)
                continue
            if t.due is None:
                t.due = now + t.period
            if now < t.due:
                continue
            if t.repeat:
                t.due += t.period
                if now - t.due > t.period:  # far behind (a long event function): don't rush to catch up
                    t.due = now + t.period
            else:
                t.active = False
            if not self.fire(t.fn) and t.repeat:
                t.active = False  # a timer whose function fails stops for good
        if self.view is not None:
            self.view.fps = 60 if any(t.active for t in self.timers) else self.IDLE_FPS
        return None

    def after(self, seconds, fn):
        return Timer(self, seconds, fn, False)

    def wait_until(self, done):
        """Keep the window working (events, timers) until done() is true: for popups that wait for an answer."""
        self.app.open_window()
        view = self.view
        while not done():
            self.tick()
            view.fps = 60
            view.frame()  # raises ViewClosed once the window has closed, which ends the program

    def mainloop(self):
        app = self.app
        if app is None or app.closed:
            return
        app.open_window()
        self.view.loop()


def kind_name(kind):
    return f"{'an' if kind[:1] in 'aeiou' else 'a'} {kind}"


class Timer:
    kind = "timer"

    def __init__(self, lib, seconds, fn, repeat):
        self.lib = lib
        self.period = max(0.0, float(seconds))
        self.fn = fn
        self.repeat = repeat
        self.active = True
        self.due = time.perf_counter() + self.period if lib.view is not None else None
        lib.add_timer(self)

    def stop(self):
        self.active = False

    def start(self):
        if not self.active:
            self.active = True
            self.due = time.perf_counter() + self.period if self.lib.view is not None else None
            if self not in self.lib.timers:
                self.lib.add_timer(self)

    def methods(self):
        return {"stop": self.stop, "start": self.start}

    def native(self):
        n = self.lib.rt.native("timer", self.methods())
        n.at = self
        return n


# ---------------------------------------------------------------- widgets

class Widget:
    """Something in the window. Its element (self.id) is made in its parent's slot unless `place` says where."""
    kind = "widget"
    tag = "div"
    cls = ""

    def __init__(self, parent, place=None, keep=True, tag=None, cls=None, **props):
        self.parent = parent
        self.app = parent.app
        self.lib = self.app.lib
        self.scene = self.app.scene
        self.rt = self.lib.rt
        self.dead = False
        self.children = []
        self.extra_ids = []
        self.click_fn = None
        self._native = None
        into, before = place if place else (parent.slot, None)
        if before:
            props["before"] = before
        self.id = self.scene.el(tag or self.tag, into, cls=("at-w " + (self.cls if cls is None else cls)).strip(), **props)
        self.slot = self.id
        self.kept = keep
        if keep:
            parent.children.append(self)
            added = getattr(parent, "added", None)
            if added:
                added(self)

    # ---- talking to the page
    def set(self, **props):
        if not self.dead:
            self.scene.set(self.id, **props)

    def call(self, method, *args):
        if not self.dead:
            self.scene.call(self.id, method, *args)

    def css_class(self, name, on=True):
        self.call("atClass", name, bool(on))

    def native(self):
        if self._native is None:
            self._native = self.rt.native(self.kind, self.methods())
            self._native.at = self
        return self._native

    def methods(self):
        return {"show": self.show, "hide": self.hide, "remove": self.remove, "style": self.style, "css": self.css,
                "animate": self.animate, "tooltip": self.tooltip, "clicked": self.clicked, "click": self.clicked,
                "hover": self.hover, "grow": self.grow, "fill": self.fill, "width": self.set_width,
                "height": self.set_height, "menu": self.set_menu}

    # ---- what every widget can do
    def show(self):
        self.set(show=True)

    def hide(self):
        self.set(show=False)

    def remove(self):
        if self.dead:
            return
        self.lib.forget(self)
        self.scene.remove(self.id)
        if self.kept and self in self.parent.children:
            self.parent.children.remove(self)
        gone = getattr(self.parent, "removed", None)
        if gone:
            gone(self)

    def style(self, name, value=NOTHING):
        if value is NOTHING:
            raise self.rt.error(f"{self.kind}:style needs a name and a value, like box:style(\"radius\", 12).")
        name = self.lib.text(name).strip().lower()
        state = None
        first, _, rest = name.partition(" ")
        if first in STATES and rest:
            state, name = first, rest.strip()
        for prop, css in css_values(self.lib, name, value):
            if state:
                self.call("atRule", state, prop, css)
            else:
                self.set(style={prop: css})
        return self.native()

    def css(self, text):
        self.call("atCss", self.lib.text(text))
        return self.native()

    def animate(self, name="fade-in", seconds=NOTHING, times=NOTHING):
        name = self.lib.text(name).strip().lower()
        if name not in ANIMATIONS:
            raise self.rt.error(f"There's no animation called '{name}'. Try one of: {', '.join(ANIMATIONS)}.")
        ms = 0 if seconds is NOTHING else max(0, self.lib.num(seconds, ":animate") * 1000)
        count = 1
        if times is not NOTHING:
            t = self.rt.plain(times)
            if isinstance(t, str) and t.strip().lower() == "forever":
                count = -1
            else:
                count = max(1, int(self.lib.num(times, ":animate")))
        self.call("atAnimate", name, ms, count)
        return self.native()

    def tooltip(self, text):
        t = self.lib.text(text)
        self.set(attrs={"data-at-tip": t or None})
        return self.native()

    def clicked(self, fn):
        self.click_fn = self.lib.check_fn(fn, ":clicked")
        self.lib.on(self.id, "click", lambda e: self.lib.fire(self.click_fn, self.click_value()))
        self.set(style={"cursor": "pointer"})
        if self.kind == "card":
            self.css_class("at-clickable")
        return self.native()

    def hover(self, fn):
        fn = self.lib.check_fn(fn, ":hover")
        self.set(attrs={"data-at-hover": True})
        self.lib.on(self.id, "at-hover", lambda e: self.lib.fire(fn, bool(e.get("on"))))
        return self.native()

    def grow(self):
        self.css_class("at-grow")
        return self.native()

    def fill(self):
        self.css_class("at-fill")
        return self.native()

    def set_width(self, size):
        self.set(style={"width": px(self.lib, size, ":width"), "flex": "none"})
        return self.native()

    def set_height(self, size):
        self.set(style={"height": px(self.lib, size, ":height"), "flex": "none"})
        return self.native()

    def set_menu(self, menu):
        m = self.lib.widget(menu, "menu", ":menu")
        self.set(attrs={"data-at-menu": m.id})
        return self.native()

    # ---- what an event function gets for this widget: a click (its text), a menu opened on it, a list's pick
    def click_value(self):
        get = self.methods().get("value") if hasattr(self, "methods") else None
        try:
            v = get() if get else None
        except Exception:
            v = None
        return v if isinstance(v, (str, int, float, bool, list)) else None

    def target_value(self):
        return None


def px(lib, v, what):
    v = lib.rt.plain(v)
    if isinstance(v, bool) or v is None:
        raise lib.rt.error(f"{what} needs a size: a number of pixels like 200, or text like \"50%\".")
    if isinstance(v, (int, float)):
        return f"{v:g}px"
    if isinstance(v, list):
        return " ".join(px(lib, x, what) for x in v)
    return str(v)


def css_values(lib, name, value):
    """[(CSS property, CSS value)] for a friendly style name, or a raw CSS property (one with a '-')."""
    rt = lib.rt
    v = rt.plain(value)
    if name not in STYLES:
        if "-" in name and re.fullmatch(r"-?[a-z][a-z0-9-]*", name):
            if v is None:
                return [(name, None)]
            unitless = name in ("opacity", "z-index", "flex", "flex-grow", "flex-shrink", "font-weight", "line-height", "order", "scale", "zoom")
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not unitless:
                return [(name, f"{v:g}px")]
            return [(name, lib.text(v))]
        import difflib
        hint = difflib.get_close_matches(name, list(STYLES), n=1, cutoff=0.6)
        extra = f" Did you mean \"{hint[0]}\"?" if hint else ""
        raise rt.error(f"'{name}' isn't a style I know.{extra} Try: background, color, radius, padding, border, shadow, "
                       f"size, bold, opacity, glass, gradient, width or height (or any CSS property, like \"letter-spacing\").")
    prop, how = STYLES[name]
    if v is None:
        return [(prop, None)] + ([("-webkit-backdrop-filter", None)] if prop == "backdrop-filter" else [])
    flag = rt.truthy(v)
    if how == "px":
        return [(prop, px(lib, v, f"style \"{name}\""))]
    if how == "color":
        return [(prop, lib.color(v))]
    if how == "paint":
        if isinstance(v, list):
            return [(prop, gradient(lib, v))]
        text = lib.text(v).strip()
        if " " in text and not text.lower().startswith(("linear-", "radial-", "conic-", "rgb", "hsl", "color-mix", "url(")):
            return [(prop, gradient(lib, text.split()))]
        if text.lower() in NAMED_COLORS or is_hex(text.lower()):
            return [(prop, lib.color(text))]
        return [(prop, text)]
    if how == "gradient":
        return [(prop, gradient(lib, v if isinstance(v, list) else lib.text(v).replace(",", " ").split()))]
    if how == "border":
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return [(prop, f"{v:g}px solid var(--border-strong)")]
        text = lib.text(v).strip()
        if text.lower() in ("none", "no", "false", "0"):
            return [(prop, "none")]
        if " " in text:
            return [(prop, text)]
        return [(prop, f"1px solid {lib.color(text)}")]
    if how == "shadow":
        if v is True:
            return [(prop, SHADOWS["medium"])]
        if v is False:
            return [(prop, "none")]
        text = lib.text(v).strip()
        return [(prop, SHADOWS.get(text.lower(), text))]
    if how == "blur":
        n = 12 if v is True else 0 if v is False else lib.num(v, "style \"blur\"")
        val = f"blur({n:g}px)" if n else "none"
        return [(prop, val), ("-webkit-backdrop-filter", val)]
    if how == "glass":
        if not flag:
            return [(prop, "none"), ("-webkit-backdrop-filter", "none")]
        n = 16 if v is True else lib.num(v, "style \"glass\"")
        val = f"blur({n:g}px) saturate(1.5)"
        return [(prop, val), ("-webkit-backdrop-filter", val),
                ("background", "color-mix(in srgb, var(--surface) 58%, transparent)"),
                ("border-color", "color-mix(in srgb, var(--text) 13%, transparent)")]
    if how == "opacity":
        n = lib.num(v, "style \"opacity\"")
        return [(prop, f"{(n / 100 if n > 1 else n):g}")]
    if how == "weight":
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return [(prop, f"{v:g}")]
        w = {"thin": "300", "light": "300", "normal": "400", "regular": "400", "medium": "500", "semibold": "600",
             "bold": "700", "heavy": "800", "black": "900"}.get(lib.text(v).strip().lower())
        if not w:
            raise rt.error("The weight can be light, normal, medium, semibold, bold or heavy (or a number like 600).")
        return [(prop, w)]
    if how == "bold":
        return [(prop, "700" if flag else "400")]
    if how == "italic":
        return [(prop, "italic" if flag else "normal")]
    if how == "underline":
        return [(prop, "underline" if flag else "none")]
    if how == "upper":
        return [(prop, "uppercase" if flag else "none")]
    if how == "select":
        return [(prop, "text" if flag else "none")]
    if how == "wrap":
        return [(prop, "pre-wrap" if flag else "nowrap")]
    if how == "font":
        return [(prop, font_stack(lib.text(v)))]
    if how == "deg":
        return [(prop, f"{lib.num(v, 'style rotate'):g}deg" if not isinstance(v, str) else v)]
    if how == "move":
        if isinstance(v, list) and len(v) == 2:
            return [(prop, f"{px(lib, v[0], 'move')} {px(lib, v[1], 'move')}")]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return [(prop, f"0 {v:g}px")]
        return [(prop, lib.text(v))]
    if how == "seconds":
        return [(prop, f"{lib.num(v, 'style transition'):g}s")]
    if how == "span":
        return [(prop, f"span {int(lib.num(v, 'style span'))}")]
    return [(prop, lib.text(v) if not isinstance(v, (int, float)) or isinstance(v, bool) else f"{v:g}")]


def gradient(lib, colors):
    cols = [lib.color(c) for c in colors]
    if len(cols) < 2:
        raise lib.rt.error("A gradient needs at least two colors, like [\"#6366f1\", \"#ec4899\"].")
    return f"linear-gradient(135deg, {', '.join(cols)})"


def font_stack(name):
    low = name.strip().lower()
    if low in FONTS:
        return FONTS[low]
    return f'"{name.strip()}", {FONT}'


class Label(Widget):
    """heading, text and small."""

    def __init__(self, parent, kind, text, place=None, keep=True):
        self.kind = kind
        super().__init__(parent, place=place, keep=keep, tag="h2" if kind == "heading" else "div", cls=f"at-{kind}", text=text)
        self.value_text = text

    def set_text(self, text):
        self.value_text = self.lib.text(text)
        self.set(text=self.value_text)
        return self.native()

    def get_text(self):
        return self.value_text

    def set_color(self, color):
        self.set(style={"color": self.lib.color(color)})
        return self.native()

    def methods(self):
        return {**super().methods(), "set": self.set_text, "value": self.get_text, "color": self.set_color}


class Button(Widget):
    kind = "button"
    tag = "button"

    def __init__(self, parent, text, fn, style, place=None, keep=True):
        self.variant = style
        super().__init__(parent, place=place, keep=keep, cls=f"at-btn at-{style}", type="button")
        self.focus_id = self.id
        self.label = text
        self.icon_name = None
        self.render()
        self.click_fn = fn
        self.lib.on(self.id, "click", lambda e: self.lib.fire(self.click_fn, self.label))

    def render(self):
        html = (icon_svg(self.icon_name) if self.icon_name else "") + (f"<span>{esc(self.label)}</span>" if self.label else "")
        self.set(html=html)
        self.css_class("at-only-icon", bool(self.icon_name and not self.label))

    def set_text(self, text):
        self.label = self.lib.text(text)
        self.render()
        return self.native()

    def get_text(self):
        return self.label

    def set_icon(self, name):
        self.icon_name = icon_name(self.lib, name)
        self.render()
        return self.native()

    def style(self, name, value=NOTHING):
        if value is not NOTHING:
            return super().style(name, value)
        style = self.lib.text(name).strip().lower()
        if style not in BUTTON_STYLES:
            raise self.rt.error(f"'{style}' isn't a button style. Use one of: {', '.join(BUTTON_STYLES)}.")
        self.css_class(f"at-{self.variant}", False)
        self.variant = style
        self.css_class(f"at-{style}", True)
        return self.native()

    def clicked(self, fn):
        self.click_fn = self.lib.check_fn(fn, ":clicked")
        return self.native()

    def disable(self):
        self.set(disabled=True)

    def enable(self):
        self.set(disabled=False)

    def focus(self, fn=NOTHING):
        return focus(self, fn)

    def methods(self):
        return {**super().methods(), "set": self.set_text, "value": self.get_text, "icon": self.set_icon,
                "disable": self.disable, "enable": self.enable, "focus": self.focus}


def icon_name(lib, name):
    n = lib.text(name).strip().lower()
    n = ICON_ALIASES.get(n, n)
    if n not in ICONS:
        import difflib
        hint = difflib.get_close_matches(n, list(ICON_NAMES), n=1, cutoff=0.6)
        raise lib.rt.error(f"There's no icon called '{n}'." + (f" Did you mean \"{hint[0]}\"?" if hint else
                           " Try home, search, settings, user, chat, send, plus, check, x, star, heart, trash, edit or bell."))
    return n


def focus(widget, fn):
    """box:focus puts the cursor in it; box:focus fn runs fn(true) when it gets the cursor and fn(false) when it loses it."""
    if fn is NOTHING:
        if not widget.dead:
            widget.scene.call(widget.focus_id, "atFocus")
        return None
    fn = widget.lib.check_fn(fn, ":focus")
    widget.set(attrs={"data-at-focus": True})
    widget.lib.on(widget.id, "at-focus", lambda e: widget.lib.fire(fn, bool(e.get("on"))))
    return widget.native()


class Input(Widget):
    kind = "input"
    tag = "input"
    cls = "at-input"

    def __init__(self, parent, placeholder, place=None, keep=True):
        props = {"type": "text", "placeholder": placeholder, "spellcheck": False, "autocomplete": "off"}
        if self.tag == "textarea":
            props = {"placeholder": placeholder, "rows": 1, "spellcheck": True}
        super().__init__(parent, place=place, keep=keep, **props)
        self.focus_id = self.id
        self.text = ""
        self.change_fn = None
        self.enter_fn = None
        self.lib.on(self.id, "input", self.typed)

    def typed(self, e):
        self.text = str(e.get("value") or "")
        if self.change_fn is not None:
            self.lib.fire(self.change_fn, self.text)

    def set_text(self, text):
        self.text = self.lib.text(text)
        self.set(value=self.text)
        return self.native()

    def get_text(self):
        return self.text

    def clear(self):
        self.set_text("")

    def change(self, fn):
        self.change_fn = self.lib.check_fn(fn, ":change")
        return self.native()

    def enter(self, fn):
        self.enter_fn = self.lib.check_fn(fn, ":enter")
        self.set(attrs={"data-at-enter": True})
        self.lib.on(self.id, "at-enter", self.pressed)
        return self.native()

    def pressed(self, e):
        if e.get("value") is not None:
            self.text = str(e.get("value"))
        self.lib.fire(self.enter_fn, self.text)

    def focus(self, fn=NOTHING):
        return focus(self, fn)

    def disable(self):
        self.set(disabled=True)

    def enable(self):
        self.set(disabled=False)

    def password(self):
        self.set(type="password")
        return self.native()

    def methods(self):
        m = {**super().methods(), "set": self.set_text, "value": self.get_text, "clear": self.clear, "change": self.change,
             "enter": self.enter, "focus": self.focus, "disable": self.disable, "enable": self.enable}
        if self.tag == "input":
            m["password"] = self.password
        return m


class TextArea(Input):
    kind = "textarea"
    tag = "textarea"
    cls = "at-textarea"


class Check(Widget):
    """checkbox and switch: a label with a real checkbox inside, so clicking the words works too."""
    tag = "label"

    def __init__(self, parent, kind, label, on):
        self.kind = kind
        super().__init__(parent, cls="at-check at-switch" if kind == "switch" else "at-check")
        self.on_value = bool(on)
        self.change_fn = None
        if kind == "switch":
            self.label_id = self.scene.el("span", self.id, cls="at-check-label", text=label)
        self.focus_id = self.scene.el("input", self.id, type="checkbox", checked=self.on_value)
        self.scene.el("span", self.id, cls="at-track" if kind == "switch" else "at-box")
        if kind != "switch":
            self.label_id = self.scene.el("span", self.id, cls="at-check-label", text=label)
        self.extra_ids.append(self.focus_id)
        self.lib.on(self.focus_id, "change", self.changed)

    def changed(self, e):
        self.on_value = bool(e.get("value"))
        if self.change_fn is not None:
            self.lib.fire(self.change_fn, self.on_value)

    def set_on(self, on, notify=False):
        self.on_value = self.rt.truthy(on)
        if not self.dead:
            self.scene.set(self.focus_id, checked=self.on_value)
        if self.rt.truthy(notify) and self.change_fn is not None:
            self.lib.fire(self.change_fn, self.on_value)
        return self.native()

    def get_on(self):
        return self.on_value

    def flip(self):
        self.set_on(not self.on_value, True)

    def change(self, fn):
        self.change_fn = self.lib.check_fn(fn, ":change")
        return self.native()

    def disable(self):
        self.css_class("at-disabled")
        if not self.dead:
            self.scene.set(self.focus_id, disabled=True)

    def enable(self):
        self.css_class("at-disabled", False)
        if not self.dead:
            self.scene.set(self.focus_id, disabled=False)

    def focus(self, fn=NOTHING):
        return focus(self, fn)

    def methods(self):
        return {**super().methods(), "set": self.set_on, "value": self.get_on, "flip": self.flip, "change": self.change,
                "disable": self.disable, "enable": self.enable, "focus": self.focus}


class Slider(Widget):
    kind = "slider"
    tag = "input"
    cls = "at-slider"

    def __init__(self, parent, low, high, value):
        self.low, self.high = low, high
        self.whole = all(isinstance(x, int) and not isinstance(x, bool) for x in (low, high))
        v = self.clamp(value)
        super().__init__(parent, type="range", min=low, max=high, step=1 if self.whole else "any", value=v,
                         style={"--p": self.percent(v)})
        self.focus_id = self.id
        self.number = v
        self.change_fn = None
        self.lib.on(self.id, "input", self.moved)

    def clamp(self, v):
        v = max(self.low, min(self.high, v))
        return int(round(v)) if self.whole else v

    def percent(self, v):
        return f"{(v - self.low) / ((self.high - self.low) or 1) * 100:g}%"

    def moved(self, e):
        try:
            v = float(e.get("value"))
        except (TypeError, ValueError):
            return
        self.number = self.clamp(v)
        if self.change_fn is not None:
            self.lib.fire(self.change_fn, self.number)

    def set_value(self, v):
        self.number = self.clamp(self.lib.num(v, "slider:set"))
        self.set(value=self.number, style={"--p": self.percent(self.number)})
        return self.native()

    def get_value(self):
        return self.number

    def change(self, fn):
        self.change_fn = self.lib.check_fn(fn, ":change")
        return self.native()

    def disable(self):
        self.set(disabled=True)

    def enable(self):
        self.set(disabled=False)

    def focus(self, fn=NOTHING):
        return focus(self, fn)

    def methods(self):
        return {**super().methods(), "set": self.set_value, "value": self.get_value, "change": self.change,
                "disable": self.disable, "enable": self.enable, "focus": self.focus}


class Menu(Widget):
    """A pop-up menu: m:item("Copy", copy), m:divider. Opened with m:open, or by right-clicking a widget given w:menu m."""
    kind = "menu"
    cls = "at-menu"

    def __init__(self, parent):
        super().__init__(parent, place=(parent.app.layer, None), keep=False)
        self.target = None
        self.lib.menus[self.id] = self

    def item(self, text, fn=None, style=NOTHING):
        fn = self.lib.check_fn(fn, "A menu item")
        style = "" if style is NOTHING else self.lib.text(style).strip().lower()
        if style not in ("", "danger", "normal"):
            raise self.rt.error("A menu item's style can be \"danger\" (in red), or leave it out.")
        return MenuItem(self, self.lib.text(text), fn, style == "danger").native()

    def divider(self):
        self.scene.el("div", self.id, cls="at-msep")

    def open(self):
        self.target = None
        self.call("atOpenMenu", 0)

    def close(self):
        self.call("atCloseMenu")

    def clear(self):
        for child in list(self.children):
            child.remove()

    def methods(self):
        return {"item": self.item, "divider": self.divider, "open": self.open, "close": self.close, "clear": self.clear,
                "remove": self.remove}


class MenuItem(Widget):
    kind = "menu item"
    cls = "at-mi"

    def __init__(self, menu, text, fn, danger):
        super().__init__(menu, cls="at-mi at-danger" if danger else "at-mi")
        self.menu = menu
        self.text = text
        self.icon_name = None
        self.click_fn = fn
        self.render()
        self.lib.on(self.id, "click", self.picked)

    def render(self):
        self.set(html=(icon_svg(self.icon_name) if self.icon_name else "") + f"<span>{esc(self.text)}</span>")

    def picked(self, e):
        self.menu.call("atCloseMenu")
        target = self.menu.target
        if callable(self.click_fn):
            self.click_fn()
        else:
            self.lib.fire(self.click_fn, target.target_value() if target is not None else None)

    def set_text(self, text):
        self.text = self.lib.text(text)
        self.render()
        return self.native()

    def get_text(self):
        return self.text

    def set_icon(self, name):
        self.icon_name = icon_name(self.lib, name)
        self.render()
        return self.native()

    def clicked(self, fn):
        self.click_fn = self.lib.check_fn(fn, ":clicked")
        return self.native()

    def methods(self):
        return {"set": self.set_text, "value": self.get_text, "icon": self.set_icon, "clicked": self.clicked,
                "click": self.clicked, "show": self.show, "hide": self.hide, "remove": self.remove}


class Dropdown(Widget):
    kind = "dropdown"
    tag = "button"
    cls = "at-btn at-dropdown"

    def __init__(self, parent, options, value):
        super().__init__(parent, type="button")
        self.focus_id = self.id
        self.options = []
        self.items = {}
        self.value_text = ""
        self.change_fn = None
        self.menu = Menu(self.app)
        self.lib.on(self.id, "click", lambda e: self.menu.call("atOpenMenu", self.id))
        self.set_options(options)
        self.choose(value if value in options else options[0], False)

    def render(self):
        self.set(html=f'<span>{esc(self.value_text)}</span>{icon_svg("chevron-down")}')

    def set_options(self, options):
        self.menu.clear()
        self.options = list(options)
        self.items = {}
        for opt in self.options:
            self.items[opt] = MenuItem(self.menu, opt, (lambda o=opt: self.choose(o, True)), False)
        if self.value_text and self.value_text not in self.options:
            self.choose(self.options[0], False)
        self.mark()

    def mark(self):
        for opt, item in self.items.items():
            item.css_class("at-checked", opt == self.value_text)

    def choose(self, option, notify):
        self.value_text = option
        self.render()
        self.mark()
        if notify and self.change_fn is not None:
            self.lib.fire(self.change_fn, option)

    def set_value(self, value):
        text = self.lib.text(value)
        if text not in self.options:
            raise self.rt.error(f"'{text}' isn't one of this dropdown's choices: {', '.join(self.options)}.")
        self.choose(text, False)
        return self.native()

    def get_value(self):
        return self.value_text

    def options_method(self, options):
        items = self.rt.plain(options)
        if not isinstance(items, list) or not items:
            raise self.rt.error("dropdown:options needs a list of choices, like [\"Small\", \"Large\"].")
        self.set_options([self.lib.text(x) for x in items])
        return self.native()

    def change(self, fn):
        self.change_fn = self.lib.check_fn(fn, ":change")
        return self.native()

    def disable(self):
        self.set(disabled=True)

    def enable(self):
        self.set(disabled=False)

    def focus(self, fn=NOTHING):
        return focus(self, fn)

    def remove(self):
        self.menu.remove()
        super().remove()

    def methods(self):
        return {**super().methods(), "set": self.set_value, "value": self.get_value, "options": self.options_method,
                "change": self.change, "disable": self.disable, "enable": self.enable, "focus": self.focus}


class Item(Widget):
    """One entry of a list."""
    kind = "item"
    cls = "at-item"

    def __init__(self, lst, text):
        super().__init__(lst)
        self.list = lst
        self.text = text
        self.sub = ""
        self.icon_name = None
        self.badge_text = ""
        self.render()

    def render(self):
        html = f'<span class="at-item-icon">{icon_svg(self.icon_name)}</span>' if self.icon_name else ""
        html += f'<div class="at-item-main"><div class="at-item-title">{esc(self.text)}</div>'
        if self.sub:
            html += f'<div class="at-item-sub">{esc(self.sub)}</div>'
        html += "</div>"
        if self.badge_text:
            html += f'<span class="at-badge">{esc(self.badge_text)}</span>'
        self.set(html=html)

    def set_text(self, text):
        self.text = self.lib.text(text)
        self.render()
        return self.native()

    def get_text(self):
        return self.text

    def set_icon(self, name):
        self.icon_name = icon_name(self.lib, name) if self.lib.text(name) else None
        self.render()
        return self.native()

    def set_badge(self, text):
        self.badge_text = self.lib.text(text)
        self.render()
        return self.native()

    def set_small(self, text):
        self.sub = self.lib.text(text)
        self.render()
        return self.native()

    def select(self):
        self.list.select(self)

    def clicked(self, fn):
        self.click_fn = self.lib.check_fn(fn, ":clicked")
        return self.native()

    def target_value(self):
        return self.text

    def methods(self):
        return {**super().methods(), "set": self.set_text, "value": self.get_text, "icon": self.set_icon,
                "badge": self.set_badge, "small": self.set_small, "select": self.select}


class ListBox(Widget):
    """A list you pick from: list:add("Inbox") gives back the item; list:change fn gets the picked item's text."""
    kind = "list"
    cls = "at-list"

    def __init__(self, parent, items):
        super().__init__(parent)
        self.by_id = {}
        self.selected = None
        self.change_fn = None
        self.lib.on(self.id, "click", self.clicked_item)
        for text in items:
            self.add(text)

    def added(self, item):
        self.by_id[item.id] = item

    def removed(self, item):
        self.by_id.pop(item.id, None)
        if self.selected is item:
            self.selected = None

    def find(self, x):
        w = getattr(self.rt.plain(x), "at", None)
        if isinstance(w, Widget):
            return w if w in self.children else None
        text = self.lib.text(x)
        return next((c for c in self.children if c.text == text), None)

    def clicked_item(self, e):
        item = next((self.by_id[i] for i in e.get("path") or () if i in self.by_id), None)
        if item is None:
            return
        self.select(item)
        if item.click_fn is not None:
            self.lib.fire(item.click_fn, item.target_value())
        if self.change_fn is not None:
            self.lib.fire(self.change_fn, item.target_value())

    def select(self, item):
        if self.selected is not None and not self.selected.dead:
            self.selected.css_class("at-selected", False)
        self.selected = item
        if item is not None:
            item.css_class("at-selected", True)

    def add(self, text):
        return Item(self, self.lib.text(text)).native()

    def remove_item(self, x=NOTHING):
        if x is NOTHING:
            return Widget.remove(self)
        item = self.find(x)
        if item is None:
            raise self.rt.error(f"That isn't in this {self.kind}.")
        item.remove()
        return None

    def clear(self):
        for item in list(self.children):
            item.remove()

    def set_value(self, x):
        if self.rt.plain(x) is None:
            self.select(None)
            return self.native()
        item = self.find(x)
        if item is None:
            raise self.rt.error(f"That isn't in this {self.kind}.")
        self.select(item)
        return self.native()

    def get_value(self):
        return self.selected.target_value() if self.selected is not None else None

    def items(self):
        return [c.target_value() for c in self.children]

    def change(self, fn):
        self.change_fn = self.lib.check_fn(fn, ":change")
        return self.native()

    def methods(self):
        return {**super().methods(), "add": self.add, "remove": self.remove_item, "clear": self.clear,
                "set": self.set_value, "value": self.get_value, "items": self.items, "change": self.change}


class TableRow(Item):
    kind = "table row"
    tag = "tr"
    cls = ""

    def __init__(self, table, cells):
        self.cells = cells
        Widget.__init__(self, table, tag="tr", cls="")
        self.list = table
        self.text = cells[0] if cells else ""
        self.render()

    def render(self):
        self.set(html="".join(f"<td>{esc(c)}</td>" for c in self.cells))

    def set_cells(self, cells):
        self.cells = self.list.cells_of(cells)
        self.text = self.cells[0] if self.cells else ""
        self.render()
        return self.native()

    def get_cells(self):
        return list(self.cells)

    def target_value(self):
        return list(self.cells)

    def methods(self):
        return {**Widget.methods(self), "set": self.set_cells, "value": self.get_cells, "select": self.select}


class Table(ListBox):
    """A table: table:add(["Ada", "Admin"]) adds a row; table:change fn gets the picked row as a list."""
    kind = "table"
    cls = "at-table-wrap"

    def __init__(self, parent, headers):
        Widget.__init__(self, parent)
        self.headers = headers
        table = self.scene.el("table", self.id, cls="at-table",
                              html="<thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr></thead>")
        self.slot = self.scene.el("tbody", table)
        self.by_id = {}
        self.selected = None
        self.change_fn = None
        self.lib.on(self.id, "click", self.clicked_item)

    def cells_of(self, cells):
        cells = self.rt.plain(cells)
        if not isinstance(cells, list):
            raise self.rt.error("A table row needs a list, like [\"Ada\", \"Admin\"].")
        return [self.lib.text(c) for c in cells]

    def add(self, cells):
        return TableRow(self, self.cells_of(cells)).native()

    def find(self, x):
        w = getattr(self.rt.plain(x), "at", None)
        if isinstance(w, Widget):
            return w if w in self.children else None
        v = self.rt.plain(x)
        if isinstance(v, list):
            cells = [self.lib.text(c) for c in v]
            return next((c for c in self.children if c.cells == cells), None)
        text = self.lib.text(x)
        return next((c for c in self.children if c.text == text), None)


class Container(Widget):
    """Something widgets go in: the window, rows, columns, cards, grids, scroll areas, tabs, modals..."""
    cls = "at-col"

    def methods(self):
        return {**super().methods(), **self.child_methods()}

    def child_methods(self):
        return {
            "heading": self.mk_heading, "text": self.mk_text, "small": self.mk_small, "button": self.mk_button,
            "input": self.mk_input, "textarea": self.mk_textarea, "checkbox": self.mk_checkbox,
            "switch": self.mk_switch, "toggle": self.mk_switch, "slider": self.mk_slider,
            "dropdown": self.mk_dropdown, "list": self.mk_list, "table": self.mk_table, "tabs": self.mk_tabs,
            "card": self.mk_card, "row": self.mk_row, "column": self.mk_column, "grid": self.mk_grid,
            "scroll": self.mk_scroll, "split": self.mk_split, "image": self.mk_image, "icon": self.mk_icon,
            "avatar": self.mk_avatar, "progress": self.mk_progress, "spinner": self.mk_spinner,
            "divider": self.mk_divider, "space": self.mk_space, "badge": self.mk_badge, "markdown": self.mk_markdown,
            "code": self.mk_code, "html": self.mk_html, "chart": self.mk_chart,
            "clear": self.clear, "gap": self.set_gap, "padding": self.set_padding, "align": self.set_align,
            "justify": self.set_justify, "drag": self.drag,
        }

    # ---- making widgets
    def mk_heading(self, text=""):
        return Label(self, "heading", self.lib.text(text)).native()

    def mk_text(self, text=""):
        return Label(self, "text", self.lib.text(text)).native()

    def mk_small(self, text=""):
        return Label(self, "small", self.lib.text(text)).native()

    def mk_button(self, text="Button", fn=None, style="primary"):
        style = self.lib.text(style).strip().lower()
        if style not in BUTTON_STYLES:
            raise self.rt.error(f"'{style}' isn't a button style. Use one of: {', '.join(BUTTON_STYLES)}.")
        return Button(self, self.lib.text(text), self.lib.check_fn(fn, "A button"), style).native()

    def mk_input(self, placeholder=""):
        return Input(self, self.lib.text(placeholder)).native()

    def mk_textarea(self, placeholder=""):
        return TextArea(self, self.lib.text(placeholder)).native()

    def mk_checkbox(self, label="", on=False):
        return Check(self, "checkbox", self.lib.text(label), self.rt.truthy(on)).native()

    def mk_switch(self, label="", on=False):
        return Check(self, "switch", self.lib.text(label), self.rt.truthy(on)).native()

    def mk_slider(self, low=0, high=100, value=None):
        low, high = self.lib.num(low, "A slider"), self.lib.num(high, "A slider")
        if high <= low:
            raise self.rt.error("A slider's highest value must be bigger than its lowest value.")
        return Slider(self, low, high, low if value is None else self.lib.num(value, "A slider")).native()

    def mk_dropdown(self, options=None, value=None):
        items = self.rt.plain(options)
        if not isinstance(items, list) or not items:
            raise self.rt.error("A dropdown needs a list of choices, like app:dropdown([\"Small\", \"Large\"]).")
        items = [self.lib.text(x) for x in items]
        return Dropdown(self, items, items[0] if value is None else self.lib.text(value)).native()

    def mk_list(self, items=None):
        items = self.rt.plain(items)
        if items is not None and not isinstance(items, list):
            raise self.rt.error("A list widget takes a list of items, like app:list([\"Inbox\", \"Sent\"]), or nothing.")
        return ListBox(self, items or []).native()

    def mk_table(self, headers=None):
        heads = self.rt.plain(headers)
        if not isinstance(heads, list) or not heads:
            raise self.rt.error("A table needs its column names, like app:table([\"Name\", \"Role\"]).")
        return Table(self, [self.lib.text(h) for h in heads]).native()

    def mk_tabs(self):
        return Tabs(self).native()

    def mk_card(self):
        return Box(self, "card", "at-col at-card").native()

    def mk_row(self):
        return Box(self, "row", "at-row").native()

    def mk_column(self):
        return Box(self, "column", "at-col").native()

    def mk_grid(self, columns=None):
        g = Box(self, "grid", "at-grid")
        if columns is not None:
            n = int(self.lib.num(columns, "A grid"))
            if n < 1:
                raise self.rt.error("A grid needs 1 or more columns.")
            g.set(style={"grid-template-columns": f"repeat({n}, minmax(0, 1fr))"})
        return g.native()

    def mk_scroll(self):
        return Scroll(self).native()

    def mk_split(self, width=260):
        return Split(self, px(self.lib, width, "A split")).native()

    def mk_image(self, path, width=None):
        img = Image(self, self.lib.image_url(path))
        if width is not None:
            img.set(style={"width": px(self.lib, width, "An image")})
        return img.native()

    def mk_icon(self, name, size=20):
        return Icon(self, icon_name(self.lib, name), px(self.lib, size, "An icon")).native()

    def mk_avatar(self, text="", color=None):
        return Avatar(self, text, color).native()

    def mk_progress(self, value=0):
        return Progress(self, self.lib.num(value, "A progress bar")).native()

    def mk_spinner(self, label="", size=22):
        return Spinner(self, self.lib.text(label), self.lib.num(size, "A spinner")).native()

    def mk_divider(self):
        return Plain(self, "divider", "at-divider").native()

    def mk_space(self, size=12):
        s = Plain(self, "space", "at-space")
        n = px(self.lib, size, "A space")
        s.set(style={"height": n, "width": n})
        return s.native()

    def mk_badge(self, text="", style="accent"):
        return Badge(self, self.lib.text(text), badge_style(self.lib, style)).native()

    def mk_markdown(self, text=""):
        return Markdown(self, self.lib.text(text)).native()

    def mk_code(self, text="", language="tuff"):
        return Code(self, self.lib.text(text), self.lib.text(language).strip().lower()).native()

    def mk_html(self, html=""):
        return Html(self, self.lib.text(html)).native()

    def mk_chart(self, values=None, kind="line"):
        return Chart(self, values, kind).native()

    # ---- layout
    def clear(self):
        for child in list(self.children):
            child.remove()

    def set_gap(self, size):
        self.scene.set(self.slot, style={"gap": px(self.lib, size, ":gap")})
        return self.native()

    def set_padding(self, size):
        self.scene.set(self.slot, style={"padding": px(self.lib, size, ":padding")})
        return self.native()

    def set_align(self, where):
        w = ALIGN.get(self.lib.text(where).strip().lower())
        if not w:
            raise self.rt.error("align can be start, center, end or stretch.")
        if self.kind in ("row", "titlebar", "split"):
            self.scene.set(self.slot, style={"align-items": w})
        else:
            self.scene.set(self.slot, style={"align-items": w, "--self": w})
        return self.native()

    def set_justify(self, where):
        w = JUSTIFY.get(self.lib.text(where).strip().lower())
        if not w:
            raise self.rt.error("justify can be start, center, end, between, around or evenly.")
        self.scene.set(self.slot, style={"justify-content": w})
        return self.native()

    def drag(self):
        """Dragging this moves the window (for windows without a frame)."""
        self.scene.call(self.slot, "atClass", "pywebview-drag-region", True)
        return self.native()


class Box(Container):
    def __init__(self, parent, kind, cls, place=None, keep=True):
        self.kind = kind
        super().__init__(parent, place=place, keep=keep, cls=cls)


class Scroll(Container):
    kind = "scroll"
    cls = "at-col at-scroll"

    def to_bottom(self):
        self.call("atToEnd", True)

    def to_top(self):
        self.call("atToTop", True)

    def methods(self):
        return {**super().methods(), "to_bottom": self.to_bottom, "to_top": self.to_top}


class Split(Container):
    """Two panes side by side, with a handle between them to drag."""
    kind = "split"
    cls = "at-split"

    def __init__(self, parent, width):
        self.first_width = width
        super().__init__(parent)

    def added(self, child):
        if len(self.children) == 1:
            child.set(style={"width": self.first_width, "flex": "none"})
        elif len(self.children) == 2:
            self.extra_ids.append(self.scene.el("div", self.id, cls="at-handle", before=child.id))
            child.css_class("at-grow")


class Tabs(Widget):
    kind = "tabs"
    cls = "at-tabs"

    def __init__(self, parent):
        super().__init__(parent)
        self.bar = self.scene.el("div", self.id, cls="at-tabbar")
        self.pages = []
        self.current = None
        self.change_fn = None

    def tab(self, name):
        return Tab(self, self.lib.text(name)).native()

    def find(self, name):
        w = getattr(self.rt.plain(name), "at", None)
        if isinstance(w, Tab) and w in self.pages:
            return w
        text = self.lib.text(name)
        page = next((p for p in self.pages if p.name == text), None)
        if page is None:
            raise self.rt.error(f"There's no tab called '{text}'. The tabs are: {', '.join(p.name for p in self.pages)}.")
        return page

    def open(self, name):
        self.show_page(self.find(name), False)

    def show_page(self, page, notify):
        if page is self.current:
            return
        for p in self.pages:
            p.set(show=p is page)
            self.scene.call(p.button, "atClass", "at-active", p is page)
        self.current = page
        if page.opened_fn is not None:
            self.lib.fire(page.opened_fn)
        if notify and self.change_fn is not None:
            self.lib.fire(self.change_fn, page.name)

    def get_value(self):
        return self.current.name if self.current else None

    def change(self, fn):
        self.change_fn = self.lib.check_fn(fn, ":change")
        return self.native()

    def methods(self):
        return {**super().methods(), "tab": self.tab, "open": self.open, "value": self.get_value, "set": self.open,
                "change": self.change}


class Tab(Container):
    kind = "tab"
    cls = "at-col at-tabpage"

    def __init__(self, tabs, name):
        self.tabs = tabs
        self.name = name
        self.opened_fn = None
        super().__init__(tabs, place=(tabs.id, None), keep=False, show=not tabs.pages)
        self.button = self.scene.el("button", tabs.bar, cls="at-tab" + (" at-active" if not tabs.pages else ""), text=name, type="button")
        self.extra_ids.append(self.button)
        self.lib.on(self.button, "click", lambda e: self.tabs.show_page(self, True))
        if not tabs.pages:
            tabs.current = self
        tabs.pages.append(self)

    def open(self):
        self.tabs.show_page(self, False)

    def opened(self, fn):
        self.opened_fn = self.lib.check_fn(fn, ":opened")
        return self.native()

    def showing(self):
        return self.tabs.current is self

    def remove(self):
        if self.dead:
            return
        self.scene.remove(self.button)
        Widget.remove(self)
        if self in self.tabs.pages:
            self.tabs.pages.remove(self)
        if self.tabs.current is self:
            self.tabs.current = None
            if self.tabs.pages:
                self.tabs.show_page(self.tabs.pages[0], False)

    def methods(self):
        return {**super().methods(), "open": self.open, "opened": self.opened, "showing": self.showing}


class Plain(Widget):
    def __init__(self, parent, kind, cls):
        self.kind = kind
        super().__init__(parent, cls=cls)


class Image(Widget):
    kind = "image"
    tag = "img"
    cls = "at-image"

    def __init__(self, parent, url):
        super().__init__(parent, src=url, draggable=False, alt="")

    def set_image(self, path):
        self.set(src=self.lib.image_url(path))
        return self.native()

    def methods(self):
        return {**super().methods(), "set": self.set_image}


class Icon(Widget):
    kind = "icon"
    tag = "span"
    cls = "at-icon"

    def __init__(self, parent, name, size):
        self.name = name
        super().__init__(parent, html=icon_svg(name), style={"width": size, "height": size})

    def set_icon(self, name):
        self.name = icon_name(self.lib, name)
        self.set(html=icon_svg(self.name))
        return self.native()

    def get_icon(self):
        return self.name

    def set_color(self, color):
        self.set(style={"color": self.lib.color(color)})
        return self.native()

    def methods(self):
        return {**super().methods(), "set": self.set_icon, "value": self.get_icon, "color": self.set_color}


class Avatar(Widget):
    kind = "avatar"
    cls = "at-avatar"

    def __init__(self, parent, text, color):
        super().__init__(parent)
        self.value_text = ""
        self.set_value(text)
        if color is not None:
            self.set(style={"background": self.lib.color(color)})

    def set_value(self, text):
        t = self.lib.text(text).strip()
        self.value_text = t
        if t.lower().endswith(IMAGE_EXTS) or re.match(r"^https?:", t, re.I):
            self.set(html=f'<img src="{esc(self.lib.image_url(t))}" alt="">')
        else:
            words = [w for w in re.split(r"\s+", t) if w]
            initials = "".join(w[0] for w in words[:2]).upper() if len(words) > 1 else t[:2].upper()
            self.set(text=initials)
        return self.native()

    def get_value(self):
        return self.value_text

    def methods(self):
        return {**super().methods(), "set": self.set_value, "value": self.get_value}


class Progress(Widget):
    kind = "progress"
    cls = "at-progress"

    def __init__(self, parent, value):
        super().__init__(parent)
        self.bar = self.scene.el("div", self.id, cls="at-bar")
        self.number = 0
        self.set_value(value)

    def set_value(self, v):
        self.number = max(0, min(100, self.lib.num(v, "progress:set")))
        if not self.dead:
            self.scene.set(self.bar, style={"width": f"{self.number:g}%"})
        return self.native()

    def get_value(self):
        return self.number

    def methods(self):
        return {**super().methods(), "set": self.set_value, "value": self.get_value}


class Spinner(Widget):
    kind = "spinner"
    cls = "at-spinner"

    def __init__(self, parent, label, size):
        super().__init__(parent)
        self.label = label
        self.variant = "ring"
        self.size = size
        self.render()

    def render(self):
        spin = ('<span class="at-dots"><span></span><span></span><span></span></span>' if self.variant == "dots"
                else f'<span class="at-ring" style="--s:{self.size:g}px"></span>')
        self.set(html=spin + (f"<span>{esc(self.label)}</span>" if self.label else ""))

    def set_label(self, text):
        self.label = self.lib.text(text)
        self.render()
        return self.native()

    def get_label(self):
        return self.label

    def start(self):
        self.css_class("at-stopped", False)

    def stop(self):
        self.css_class("at-stopped", True)

    def style(self, name, value=NOTHING):
        if value is not NOTHING:
            return super().style(name, value)
        v = self.lib.text(name).strip().lower()
        if v not in ("ring", "dots"):
            raise self.rt.error("A spinner's style can be \"ring\" or \"dots\".")
        self.variant = v
        self.render()
        return self.native()

    def methods(self):
        return {**super().methods(), "set": self.set_label, "value": self.get_label, "start": self.start, "stop": self.stop}


def badge_style(lib, style):
    s = lib.text(style).strip().lower()
    s = {"primary": "accent", "error": "danger", "red": "danger", "green": "success", "yellow": "warning",
         "blue": "info", "grey": "gray", "neutral": "gray"}.get(s, s)
    if s not in BADGE_STYLES:
        raise lib.rt.error(f"'{s}' isn't a badge style. Use one of: {', '.join(BADGE_STYLES)}.")
    return s


class Badge(Widget):
    kind = "badge"
    tag = "span"

    def __init__(self, parent, text, style):
        self.variant = style
        super().__init__(parent, cls=f"at-badge at-{style}")
        self.label = text
        self.icon_name = None
        self.render()

    def render(self):
        self.set(html=(icon_svg(self.icon_name) if self.icon_name else "") + esc(self.label))

    def set_text(self, text):
        self.label = self.lib.text(text)
        self.render()
        return self.native()

    def get_text(self):
        return self.label

    def set_icon(self, name):
        self.icon_name = icon_name(self.lib, name)
        self.render()
        return self.native()

    def style(self, name, value=NOTHING):
        if value is not NOTHING:
            return super().style(name, value)
        s = badge_style(self.lib, name)
        self.css_class(f"at-{self.variant}", False)
        self.variant = s
        self.css_class(f"at-{s}", True)
        return self.native()

    def methods(self):
        return {**super().methods(), "set": self.set_text, "value": self.get_text, "icon": self.set_icon}


class Markdown(Widget):
    kind = "markdown"
    cls = "at-md"

    def __init__(self, parent, text):
        super().__init__(parent)
        self.source = ""
        self.set_text(text)

    def render(self):
        self.set(html=markdown(self.source))

    def set_text(self, text):
        self.source = self.lib.text(text)
        self.render()
        return self.native()

    def add(self, text):
        self.source += self.lib.text(text)
        self.render()
        return self.native()

    def get_text(self):
        return self.source

    def clear(self):
        self.set_text("")

    def methods(self):
        return {**super().methods(), "set": self.set_text, "add": self.add, "value": self.get_text, "clear": self.clear}


class Code(Markdown):
    kind = "code"
    cls = "at-code"

    def __init__(self, parent, text, language):
        self.language = language
        super().__init__(parent, text)

    def render(self):
        self.set(html=code_html(self.source, self.language))


class Html(Widget):
    kind = "html"
    cls = "at-html"

    def __init__(self, parent, html):
        super().__init__(parent)
        self.source = html
        self.set(html=html)

    def set_html(self, html):
        self.source = self.lib.text(html)
        self.set(html=self.source)
        return self.native()

    def get_html(self):
        return self.source

    def methods(self):
        return {**super().methods(), "set": self.set_html, "value": self.get_html}


class Chart(Widget):
    kind = "chart"
    cls = "at-chart-box"

    def __init__(self, parent, values, kind):
        k = parent.lib.text(kind).strip().lower()
        if k not in CHART_KINDS:
            raise parent.lib.rt.error("A chart can be \"line\" or \"bar\".")
        super().__init__(parent)
        self.chart_kind = k
        self.values = []
        self.set_values(values if values is not None else [])

    def render(self):
        self.set(html=chart_svg(self.values, self.chart_kind, self.id))

    def set_values(self, values):
        vals = self.rt.plain(values)
        if not isinstance(vals, list):
            raise self.rt.error("A chart needs a list of numbers, like [3, 8, 5, 12].")
        self.values = [self.lib.num(v, "A chart") for v in vals]
        self.render()
        return self.native()

    def add(self, value):
        self.values.append(self.lib.num(value, "chart:add"))
        self.render()
        return self.native()

    def get_values(self):
        return list(self.values)

    def methods(self):
        return {**super().methods(), "set": self.set_values, "add": self.add, "value": self.get_values}


class Modal(Container):
    """A dialog over the window: dlg = app:modal("Rename"), add things to it, then dlg:open."""
    kind = "modal"
    cls = "at-overlay"

    def __init__(self, app, title):
        super().__init__(app, place=(app.layer, None), keep=False, style={"display": "none"})
        box = self.scene.el("div", self.id, cls="at-dialog", role="dialog")
        self.title_id = self.scene.el("div", box, cls="at-dialog-title", text=title)
        self.slot = self.scene.el("div", box, cls="at-dialog-body")
        self.is_open = False
        self.closed_fn = None
        self.on_dismiss = None
        self.lib.on(self.id, "at-dismiss", self.dismissed)

    def dismissed(self, e):
        if self.on_dismiss is not None:
            self.on_dismiss()
        else:
            self.close()

    def open(self):
        if not self.is_open:
            self.is_open = True
            self.call("atOpen")

    def close(self):
        if self.is_open:
            self.is_open = False
            self.call("atShut")
            if self.closed_fn is not None:
                self.lib.fire(self.closed_fn)

    def closed(self, fn):
        self.closed_fn = self.lib.check_fn(fn, ":closed")
        return self.native()

    def set_title(self, text):
        if not self.dead:
            self.scene.set(self.title_id, text=self.lib.text(text))
        return self.native()

    def methods(self):
        return {**super().methods(), "open": self.open, "close": self.close, "closed": self.closed, "set": self.set_title}


class Titlebar(Container):
    """The title bar of a window without a frame: drag it to move the window; minimize, maximize and close buttons."""
    kind = "titlebar"
    cls = "at-titlebar pywebview-drag-region"

    def __init__(self, app, title):
        super().__init__(app, place=(app.id, app.body), keep=False)
        self.title_id = self.scene.el("span", self.id, cls="at-tb-title", text=title)
        self.slot = self.scene.el("div", self.id, cls="at-tb-slot pywebview-drag-region")
        buttons = self.scene.el("div", self.id, cls="at-tb-buttons")
        self.max_button = None
        for name, fn, extra, tip in (("window-minimize", app.minimize, "", "Minimize"),
                                     ("window-maximize", app.maximize, "", "Maximize"),
                                     ("window-close", app.close, " at-close", "Close")):
            b = self.scene.el("button", buttons, cls="at-wb" + extra, html=icon_svg(name), type="button", tabindex=-1,
                              attrs={"aria-label": tip})
            self.lib.on(b, "click", lambda e, fn=fn: fn())
            if name == "window-maximize":
                self.max_button = b
        self.lib.on(self.id, "dblclick", self.double)

    def double(self, e):
        if (e.get("path") or [None])[0] in (self.id, self.slot):
            self.app.maximize()

    def set_title(self, text):
        self.scene.set(self.title_id, text=self.lib.text(text))
        return self.native()

    def methods(self):
        return {**super().methods(), "set": self.set_title}


class Sidebar(Container):
    kind = "sidebar"
    cls = "at-col at-side"

    def __init__(self, app, width, side):
        super().__init__(app, place=(app.body, app.slot if side == "left" else None), keep=False,
                         cls=f"at-col at-side at-{side}", style={"width": width})


class Toast(Widget):
    kind = "toast"

    def __init__(self, app, text, style, seconds):
        super().__init__(app, place=(app.toasts, None), keep=False, cls=f"at-toast at-{style}",
                         html=icon_svg(TOAST_ICONS[style]) + f"<span>{esc(text)}</span>")
        self.lib.after(seconds, self.leave)

    def leave(self):
        self.call("atLeave")
        self.lib.after(0.24, self.remove)


class App(Container):
    """The window. Widgets made straight on it go in its main area; it also has the window's own settings."""
    kind = "window"

    def __init__(self, lib, title, width, height):
        self.lib, self.app, self.rt = lib, self, lib.rt
        self.scene = Scene()
        self.children = []
        self.extra_ids = []
        self.dead = False
        self.kept = False
        self._native = None
        self.click_fn = None
        self.title_text = title
        self.width, self.height = int(width), int(height)
        self.theme_name = "dark"
        self.icon_path = None
        self.frameless = False
        self.closed = False
        self.close_fn = None
        self.keys = {}
        self.maximized = False
        self.titlebar_widget = None
        self.sidebars = {}
        self.hwnd = None
        self.scene.call(0, "css", CSS)
        self.scene.js("const ICONS = " + json.dumps(ICONS) + ";\n" + JS)
        self.id = self.scene.el("div", 0, cls="at-app at-dark")
        self.body = self.scene.el("div", self.id, cls="at-body")
        self.slot = self.scene.el("div", self.body, cls="at-main")
        self.layer = self.scene.el("div", self.id, cls="at-layer")
        self.toasts = self.scene.el("div", self.layer, cls="at-toasts")
        lib.app = self
        lib.rt.on_finish(lib.mainloop)

    # ---- opening the window (at the end of the program's top level, or when a popup needs it)
    def open_window(self):
        if self.scene.view is not None:
            return
        import tuff_view
        lib = self.lib
        light = self.theme_name == "light" or (self.theme_name == "system" and system_light())
        if self.frameless:
            try:
                import webview
                webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True  # buttons in a title bar don't drag it
            except ImportError:
                pass
        else:
            self.style_titlebar_soon(light)
        view = tuff_view.View(self.title_text, self.width, self.height, icon=self.icon_path, frameless=self.frameless,
                              background=(LIGHT if light else DARK)["bg"], assets=lib.rt.interp.base_dir,
                              on_error=lib.view_error, min_size=(min(self.width, 340), min(self.height, 220)))
        lib.view = view
        for t in ROUTED:
            view.on(t, lib.route)
        view.on("at-key", self.key_pressed)
        view.on("at-link", self.link)
        view.on("at-context", self.context)
        view.on("at-resize", lambda e: view.resize(e.get("w"), e.get("h")))
        view.on("close", self.window_closed)
        if self.frameless:
            self.scene.ops.append(("call", self.id, "atGrips", ()))
        self.scene.attach(view)
        lib.start_timers()

    def style_titlebar_soon(self, light):
        """Windows: colour the window's own title bar to match the theme, as soon as the window exists."""
        if sys.platform != "win32":
            return

        def find():
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and not self.closed:
                hwnd = find_window(self.title_text)
                if hwnd:
                    self.hwnd = hwnd
                    color_titlebar(hwnd, light)
                    return
                time.sleep(0.005)
        threading.Thread(target=find, name="atgui-titlebar", daemon=True).start()

    # ---- events that belong to the whole window
    def key_pressed(self, e):
        fn = self.keys.get(e.get("combo"))
        if fn is not None:
            self.lib.fire(fn)

    def link(self, e):
        href = str(e.get("href") or "")
        if re.match(r"^(https?:|mailto:)", href, re.I):
            threading.Thread(target=webbrowser.open, args=(href,), daemon=True).start()

    def context(self, e):
        menu = self.lib.menus.get(e.get("menu"))
        if menu is None:
            return
        ids = {}
        for w in self.all_widgets():
            ids[w.id] = w
        menu.target = next((ids[i] for i in e.get("path") or () if i in ids), None)

    def all_widgets(self):
        stack = list(self.children) + list(self.sidebars.values())
        if self.titlebar_widget:
            stack.append(self.titlebar_widget)
        while stack:
            w = stack.pop()
            yield w
            stack.extend(w.children)
            stack.extend(getattr(w, "pages", ()))

    def window_closed(self, e):
        self.closed = True
        if self.close_fn is not None:
            self.lib.fire(self.close_fn)

    # ---- the window's own methods
    def methods(self):
        return {**self.child_methods(), "title": self.set_title, "size": self.set_size, "icon": self.icon,
                "theme": self.set_theme, "accent": self.set_accent, "font": self.set_font, "frameless": self.set_frameless,
                "titlebar": self.titlebar, "sidebar": self.sidebar, "modal": self.modal, "menu": self.menu,
                "toast": self.toast, "alert": self.alert, "confirm": self.confirm, "ask": self.ask, "every": self.every,
                "after": self.after, "key": self.key, "closed": self.on_closed, "close": self.close,
                "minimize": self.minimize, "maximize": self.maximize, "style": self.style, "css": self.global_css}

    def native(self):
        if self._native is None:
            self._native = self.rt.native("window", self.methods())
            self._native.at = self
        return self._native

    def set(self, **props):
        self.scene.set(self.id, **props)

    def call(self, method, *args):
        self.scene.call(self.id, method, *args)

    def set_title(self, text):
        self.title_text = self.lib.text(text)
        if self.titlebar_widget is not None:
            self.titlebar_widget.set_title(self.title_text)
        if self.lib.view is not None:
            self.lib.view.set_title(self.title_text)

    def set_size(self, width, height):
        self.width = int(self.lib.num(width, "window:size"))
        self.height = int(self.lib.num(height, "window:size"))
        if self.lib.view is not None:
            self.lib.view.resize(self.width, self.height)

    def icon(self, name, size=20):
        """app:icon "logo.png" sets the window's icon; app:icon "search" shows a built-in icon, like row:icon."""
        text = self.lib.text(name).strip()
        if not (text.lower().endswith(IMAGE_EXTS) or "/" in text or "\\" in text):
            return self.mk_icon(name, size)
        full = self.rt.path(text)
        if not os.path.isfile(full):
            raise self.rt.error(f"Couldn't find the icon '{text}'. Put the picture in your project folder.")
        if not full.lower().endswith((".png", ".ico")):
            raise self.rt.error(f"Couldn't use '{text}' as the window's icon. Use a .png or .ico file.")
        if self.lib.view is not None:
            raise self.rt.error("Set the window's icon at the top of your program, before the window opens.")
        self.icon_path = full
        return None

    def set_theme(self, name):
        name = self.lib.text(name).strip().lower()
        if name not in THEMES:
            raise self.rt.error("The theme can be \"dark\", \"light\" or \"system\".")
        for t in THEMES:
            self.call("atClass", f"at-{t}", t == name)
        self.theme_name = name
        if self.hwnd:
            color_titlebar(self.hwnd, name == "light" or (name == "system" and system_light()))

    def set_accent(self, color, second=NOTHING):
        text = self.lib.text(color).strip().lower()
        if text in ACCENTS:
            main, other = ACCENTS[text]
        else:
            main = self.lib.color(color)
            if not is_hex(main):
                raise self.rt.error(f"'{text}' isn't an accent color. Try {', '.join(ACCENTS)} or a hex code like \"#ff8800\".")
            other = main
        if second is not NOTHING:
            other = self.lib.color(second)
        self.set(style={"--accent": main, "--accent-2": other, "--on-accent": on_color(main) if is_hex(main) else "#fff"})

    def set_font(self, name):
        self.set(style={"--font": font_stack(self.lib.text(name))})

    def set_frameless(self):
        if self.lib.view is not None:
            raise self.rt.error("Make the window frameless at the top of your program, before it opens.")
        self.frameless = True

    def titlebar(self, title=NOTHING):
        if self.titlebar_widget is not None:
            return self.titlebar_widget.native()
        if self.lib.view is not None:
            raise self.rt.error("Make the title bar at the top of your program, before the window opens.")
        self.frameless = True
        self.titlebar_widget = Titlebar(self, self.title_text if title is NOTHING else self.lib.text(title))
        return self.titlebar_widget.native()

    def sidebar(self, width=250, side="left"):
        side = self.lib.text(side).strip().lower()
        if side not in ("left", "right"):
            raise self.rt.error("A sidebar goes on the \"left\" or the \"right\".")
        if side in self.sidebars:
            raise self.rt.error(f"This window already has a sidebar on the {side}.")
        bar = Sidebar(self, px(self.lib, width, "A sidebar"), side)
        self.sidebars[side] = bar
        return bar.native()

    def modal(self, title=""):
        return Modal(self, self.lib.text(title)).native()

    def menu(self):
        return Menu(self).native()

    def toast(self, text, style="info"):
        style = self.lib.text(style).strip().lower()
        style = {"danger": "error", "ok": "success", "warn": "warning"}.get(style, style)
        if style not in TOAST_STYLES:
            raise self.rt.error(f"A toast's style can be {', '.join(TOAST_STYLES)}.")
        Toast(self, self.lib.text(text), style, 3.6)

    def every(self, seconds, fn):
        fn = self.lib.check_fn(fn, ":every")
        return Timer(self.lib, max(0.01, self.lib.num(seconds, ":every")), fn, True).native()

    def after(self, seconds, fn):
        fn = self.lib.check_fn(fn, ":after")
        return Timer(self.lib, max(0.0, self.lib.num(seconds, ":after")), fn, False).native()

    def key(self, combo, fn):
        c = key_combo(self.lib.text(combo))
        if c is None:
            raise self.rt.error(f"'{self.lib.text(combo)}' isn't a key I know. Write keys like \"ctrl+s\", \"escape\", \"f5\" or \"ctrl+shift+n\".")
        self.keys[c] = self.lib.check_fn(fn, ":key")
        self.call("atKeys", sorted(self.keys))

    def on_closed(self, fn):
        self.close_fn = self.lib.check_fn(fn, ":closed")

    def close(self):
        self.closed = True
        if self.lib.view is not None:
            self.lib.view.close()

    def minimize(self):
        if self.lib.view is not None:
            self.lib.view.minimize()

    def maximize(self):
        if self.lib.view is None:
            return
        if self.maximized:
            self.lib.view.restore()
        else:
            self.lib.view.maximize()
        self.maximized = not self.maximized
        tb = self.titlebar_widget
        if tb is not None and tb.max_button:
            self.scene.set(tb.max_button, html=icon_svg("window-restore" if self.maximized else "window-maximize"))

    def global_css(self, text):
        self.scene.call(0, "css", self.lib.text(text))

    # ---- popups that wait for an answer
    def dialog(self, message, buttons, field=False):
        dlg = Modal(self, "")
        Label(dlg, "text", self.lib.text(message))
        box = Input(dlg, "") if field else None
        row = Box(dlg, "row", "at-row at-actions")
        answer = {}
        first = None
        for text, value, style in buttons:
            b = Button(row, text, (lambda *_, v=value: answer.setdefault("value", v)), style)
            first = first or b
        cancel = buttons[-1][1]
        if box is not None:
            box.set(attrs={"data-at-enter": True})
            self.lib.on(box.id, "at-enter", lambda e: answer.setdefault("value", "<field>"))
        dlg.on_dismiss = lambda: answer.setdefault("value", cancel)
        dlg.open()
        if box is None:
            first.focus()
        self.lib.wait_until(lambda: "value" in answer)
        dlg.is_open = False
        dlg.call("atShut")
        self.lib.after(0.25, dlg.remove)
        value = answer["value"]
        return box.text if value == "<field>" else value

    def alert(self, message):
        self.dialog(message, [("OK", True, "primary")])

    def confirm(self, message):
        return bool(self.dialog(message, [("Yes", True, "primary"), ("No", False, "ghost")]))

    def ask(self, question):
        value = self.dialog(question, [("OK", "<field>", "primary"), ("Cancel", None, "ghost")], field=True)
        return value if isinstance(value, str) else ""


# ---------------------------------------------------------------- the native title bar (Windows)

def find_window(title):
    """This process's top-level window with this title, or None."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    pid = os.getpid()
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == title:
                found.append(hwnd)
                return False
        return True
    user32.EnumWindows(proc(each), 0)
    return found[0] if found else None


def color_titlebar(hwnd, light):
    """Dark or light title bar, and on Windows 11 the same colour as the app's background."""
    import ctypes
    from ctypes import wintypes
    try:
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(0 if light else 1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (and its number on older Windows 10)
            if dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(on), 4) == 0:
                break
        r, g, b = hex_rgb((LIGHT if light else DARK)["bg"])
        caption = ctypes.c_int(r | (g << 8) | (b << 16))
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 35, ctypes.byref(caption), 4)  # DWMWA_CAPTION_COLOR (Windows 11)
    except Exception:
        pass


# ---------------------------------------------------------------- what Tuff sees

def make_library(rt):
    lib = Lib(rt)

    def window(title="My App", width=900, height=620):
        if lib.app is not None:
            raise rt.error("An atgui program has one window. For more screens use app:tabs() or a sidebar list, "
                           "and for a pop-up use app:modal(...).")
        return App(lib, rt.text(title), rt.number(width, "atgui.window"), rt.number(height, "atgui.window")).native()

    return {"window": rt.builtin("atgui.window", window)}


# What each maker gives back, for tuff.py --check (method name -> kind of widget).
MAKES = {"heading": "heading", "text": "text", "small": "small", "button": "button", "input": "input",
         "textarea": "textarea", "checkbox": "checkbox", "switch": "switch", "toggle": "switch", "slider": "slider",
         "dropdown": "dropdown", "list": "list", "table": "table", "tabs": "tabs", "card": "card", "row": "row",
         "column": "column", "grid": "grid", "scroll": "scroll", "split": "split", "image": "image", "icon": "icon",
         "avatar": "avatar", "progress": "progress", "spinner": "spinner", "divider": "divider", "space": "space",
         "badge": "badge", "markdown": "markdown", "code": "code", "html": "html", "chart": "chart"}
# Methods of a particular kind that make something else.
MAKES_ON = {"window": {"titlebar": "titlebar", "sidebar": "sidebar", "modal": "modal", "menu": "menu",
                       "every": "timer", "after": "timer"},
            "list": {"add": "item"}, "table": {"add": "table row"}, "tabs": {"tab": "tab"}, "menu": {"item": "menu item"}}
# Methods that give back the widget they were called on, so they can be chained.
SELF_METHODS = {"style", "css", "animate", "tooltip", "clicked", "click", "hover", "grow", "fill", "width", "height",
                "menu", "gap", "padding", "align", "justify", "drag", "set", "icon", "badge", "small", "change", "enter",
                "color", "password", "opened", "closed", "options"}
TEXT_VALUES = {"heading", "text", "small", "button", "input", "textarea", "dropdown", "badge", "markdown", "code",
               "html", "item", "menu item", "avatar", "spinner", "icon"}
BOOL_VALUES = {"checkbox", "switch"}
NUMBER_VALUES = {"slider", "progress"}
# What each event function is given (how many inputs, and how to describe it), and which input is the function.
EVENTS = {"clicked": (0, "a click", 0), "hover": (1, ":hover", 0), "focus": (1, ":focus", 0), "key": (0, ":key", 1),
          "closed": (0, ":closed", 0), "item": (1, "a menu item", 1)}


def tables():
    """For tuff.py --check, without opening a window: atgui's functions, and every kind's methods with their inputs."""

    def blank(cls, **fields):
        obj = cls.__new__(cls)
        obj.__dict__.update(fields)
        return obj

    kinds = {"window": blank(App).methods()}
    for kind in ("heading", "text", "small"):
        kinds[kind] = blank(Label, kind=kind).methods()
    for kind in ("checkbox", "switch"):
        kinds[kind] = blank(Check, kind=kind).methods()
    for kind in ("card", "row", "column", "grid"):
        kinds[kind] = blank(Box, kind=kind).methods()
    for cls in (Button, Input, TextArea, Slider, Dropdown, ListBox, Item, Table, TableRow, Tabs, Tab, Scroll, Split,
                Image, Icon, Avatar, Progress, Spinner, Badge, Markdown, Code, Html, Chart, Modal, Titlebar, Sidebar,
                Menu, MenuItem, Timer):
        kinds[cls.kind] = blank(cls).methods()
    kinds["divider"] = blank(Plain, kind="divider").methods()
    kinds["space"] = blank(Plain, kind="space").methods()

    def window(title="My App", width=900, height=620):
        return None

    return {"lib": {"window": window}, "kinds": kinds, "makes": MAKES, "makes_on": MAKES_ON,
            "self_methods": SELF_METHODS, "text_values": TEXT_VALUES, "bool_values": BOOL_VALUES,
            "number_values": NUMBER_VALUES, "events": EVENTS, "button_styles": BUTTON_STYLES,
            "badge_styles": BADGE_STYLES, "toast_styles": TOAST_STYLES, "themes": THEMES, "accents": tuple(ACCENTS),
            "icons": ICON_NAMES, "animations": ANIMATIONS, "styles": tuple(STYLES), "states": STATES,
            "charts": CHART_KINDS}
