"""tuff.py --check on atgui programs: mistakes it must catch, and correct code it must not flag.

    py -3 tuffcode/test/atgui/check_test.py [--out result.json]

Each case is a small program; the checker runs on it as `tuff.py --check` would (in a subprocess).
Cases that name picture files are written to a folder outside %TEMP% (the IDE checks unsaved code in
%TEMP%, where pictures next to the file can't be checked, so the checker skips them there).
"""
import json
import os
import subprocess
import sys
import tempfile
import itertools
from concurrent.futures import ThreadPoolExecutor

COUNT = itertools.count(1)

HERE = os.path.dirname(os.path.abspath(__file__))
TUFF = os.path.abspath(os.path.join(HERE, "..", "..", "..", "tuff.py"))
APP = 'mention atgui\napp = atgui.window("T")\n'
GO = "\nfunc go():\n    say 1\n"

CATCH = [
    ("window method typo", APP + 'app:hedding "Hi"\n', "A window doesn't have :hedding. Did you mean :heading?"),
    ("button method typo", APP + 'b = app:button("Go", go)\nb:disabel' + GO, "A button doesn't have :disabel. Did you mean :disable?"),
    ("card method typo", APP + 'c = app:card\nc:buton("x")\n', "A card doesn't have :buton. Did you mean :button?"),
    ("chained item method typo", APP + 'nav = app:list()\nnav:add("x"):icn "sun"\n', "An item doesn't have :icn. Did you mean :icon?"),
    ("tab page method typo", APP + 't = app:tabs()\np = t:tab "A"\np:opne\n', "A tab doesn't have :opne. Did you mean"),
    ("page in a card", APP + 'c = app:card\nc:page "P"\n', "A card doesn't have :page."),
    ("modal method typo", APP + 'd = app:modal("Rename")\nd:opne\n', "A modal doesn't have :opne. Did you mean :open?"),
    ("timer method typo", APP + 't = app:every(1, go)\nt:stopp' + GO, "A timer doesn't have :stopp. Did you mean :stop?"),
    ("menu method typo", APP + 'm = app:menu()\nm:itme("Copy", go)' + GO, "A menu doesn't have :itme. Did you mean :item?"),
    ("too many inputs", APP + 'app:heading("a", "b")\n', "window:heading got the wrong number of inputs (2)."),
    ("too few inputs", APP + 's = app:slider(0, 9)\ns:set\n', "slider:set got the wrong number of inputs (0)."),
    ("bare input on :value", APP + 's = app:slider(0, 10)\nsay s:value - 1\n', "s:value doesn't take an input, so what comes after it was read as one."),
    ("atgui.window typo", 'mention atgui\napp = atgui.windw("T")\n', "atgui doesn't have 'windw'. It has: window."),
    ("atgui.window with 4 inputs", 'mention atgui\napp = atgui.window("T", 1, 2, 3)\n', "atgui.window() got the wrong number of inputs (4)."),
    ("dot on the window", APP + 'app.button("Go", go)' + GO, "Only libraries use '.', and this is a window. For methods use ':', like app:button"),
    ("library used without mention", 'app = atgui.window("T")\n', "'atgui' is a library. Add  import atgui  at the top"),
    ("unknown button style", APP + 'app:button("Go", go, "big")' + GO, "'big' isn't a button style. Use one of: primary, secondary, outline, ghost, success, danger, gradient."),
    ("unknown button style later", APP + 'b = app:button("Go", go)\nb:style "huge"' + GO, "'huge' isn't a button style."),
    ("unknown badge style", APP + 'app:badge("New", "shiny")\n', "'shiny' isn't a badge style."),
    ("style name typo", APP + 'c = app:card\nc:style("radus", 12)\n', "'radus' isn't a style I know. Did you mean \"radius\"?"),
    ("hover style name typo", APP + 'c = app:card\nc:style("hover backgrund", "#222")\n', "'backgrund' isn't a style I know. Did you mean \"background\"?"),
    ("style with one input on a card", APP + 'c = app:card\nc:style "radius"\n', "card:style needs a name and a value"),
    ("unknown spinner style", APP + 's = app:spinner("Wait")\ns:style "bars"\n', "A spinner's style can be \"ring\" or \"dots\"."),
    ("unknown theme", APP + 'app:theme "blue"\n', 'The theme can be "dark", "light" or "system".'),
    ("unknown accent", APP + 'app:accent "purpel"\n', "'purpel' isn't an accent color."),
    ("unknown icon", APP + 'r = app:row\nr:icon "serch"\n', "There's no icon called 'serch'. Did you mean \"search\"?"),
    ("unknown icon on a button", APP + 'app:button("Go", go):icon "sned"' + GO, "There's no icon called 'sned'. Did you mean \"send\"?"),
    ("window icon that isn't .png or .ico", APP + 'app:icon "logo.jpg"\n', "Couldn't use 'logo.jpg' as the window's icon. Use a .png or .ico file."),
    ("image that isn't a picture", APP + 'app:image("notes.txt")\n', "'notes.txt' isn't a picture."),
    ("missing image file", APP + 'app:image("no-such-cat.png", 200)\n', "Couldn't find the image 'no-such-cat.png'.", "project"),
    ("unknown animation", APP + 'c = app:card\nc:animate "fly"\n', "There's no animation called 'fly'."),
    ("unknown toast style", APP + 'app:toast("Hi", "great")\n', "A toast's style can be info, success, warning, error."),
    ("unknown chart kind", APP + 'app:chart([1, 2], "pie")\n', 'A chart can be "line" or "bar".'),
    ("unknown key", APP + 'app:key("ctrl+banana", go)' + GO, "'ctrl+banana' isn't a key I know."),
    ("sidebar on the top", APP + 'app:sidebar(200, "top")\n', 'A sidebar goes on the "left" or the "right".'),
    ("unknown align", APP + 'r = app:row\nr:align "diagonal"\n', "align can be start, center, end or stretch."),
    ("unknown justify", APP + 'r = app:row\nr:justify "spread"\n', "justify can be start, center, end, between, around or evenly."),
    ("button function asks for 2 inputs", APP + 'app:button("Go", go)\nfunc go(a, b):\n    say a\n', "go() needs 2 inputs, but a button click only gives it 1 (the button's text)."),
    ("hover function asks for 2 inputs", APP + 'c = app:card\nc:hover lit\nfunc lit(a, b):\n    say a\n', "lit() needs 2 inputs, but :hover only gives it 1 (true or false)."),
    ("key function asks for an input", APP + 'app:key("ctrl+s", save)\nfunc save(x):\n    say x\n', "save() needs 1 input, but :key doesn't give it any. Write it as: func save():"),
    ("timer function asks for an input", APP + 'app:every(1, tick)\nfunc tick(n):\n    say n\n', "tick() needs 1 input, but :every doesn't give it any."),
    ("change function asks for 2 inputs", APP + 'n = app:list(["A"])\nn:change picked\nfunc picked(a, b):\n    say a\n', "picked() needs 2 inputs, but :change only gives it 1 (the new value)."),
    ("handler passed with brackets", APP + 'app:button("Go", go())' + GO, "Pass the function's name without brackets: go, not go()."),
    ("method passed as a handler", APP + 'app:button("Quit", app:close)\n', "app:close runs right away here, while this line runs."),
    ("text passed as a handler", APP + 'b = app:button("Go")\nb:clicked "go"' + GO, "This needs a function name, not text."),
    ("missing event function", APP + 'b = app:button("Go")\nb:clicked launch_now\n', "I don't know what 'launch_now' is. Make it with func, like: func launch_now():"),
    ("wait in an event function", APP + 'app:button("Go", go)\nfunc go():\n    wait(1)\n', "wait() freezes the window"),
    ("input in an event function", APP + 'app:button("Go", go)\nfunc go():\n    name = input "Name? "\n', "input reads from the console and freezes the window"),
    ("dropdown set to a missing choice", APP + 'd = app:dropdown(["S", "M"])\nd:set "L"\n', "'L' isn't one of this dropdown's choices: S, M."),
    ("typed text + a number", APP + 'box = app:input "Age"\nsay box:value() + 1\n', "box:value() is typed text, so + sticks them together"),
    ("method on what :value gives", APP + 'sw = app:switch("On", true)\nsw:value():upper\n', "True/false doesn't have any :methods."),
]

OK = [
    ("every widget, layout and method", APP + '''app:title "Kitchen sink"
more = app:menu()
more:item("Share", copied)
app:size(900, 600)
app:theme "system"
app:accent "#ff8800"
app:font "rounded"
app:css ".at-card { border-width: 2px }"
side = app:sidebar(220, "right")
side:heading "Side"
nav = side:list(["One", "Two"])
nav:add("Three"):icon("star"):badge "2"
nav:change picked
nav:set "Two"
say nav:value()
say nav:items()
top = app:row
top:gap 12
top:align "center"
top:justify "between"
top:button("", go, "ghost"):icon "plus"
top:icon("search", 18)
top:avatar("Ada Lovelace", "pink")
top:badge("New", "success"):icon "check"
grid = app:grid(3)
c = grid:card
c:style("span", 2)
c:style("hover shadow", "glow")
c:style("pressed scale", 0.98)
c:style("letter-spacing", 1)
c:style("gradient", ["#6366f1", "#ec4899"])
c:style("glass", true)
c:css "outline: 1px dashed red"
c:animate("pop", 0.4, "forever")
c:tooltip "Hello"
c:clicked go
c:hover lit
c:menu more
c:grow
c:fill
c:width 300
c:height "50%"
col = c:column
col:heading "Title"
col:text("Body"):color "muted"
col:small "Hint"
box = col:input "Name"
box:change typed
box:enter typed
box:focus
box:focus lit
box:password
area = col:textarea "Message"
area:enter typed
check = col:checkbox("Remember", true)
sw = col:switch("Dark", false)
sw:change lit
sw:flip
say check:value() and sw:value()
s = col:slider(0, 10, 5)
s:change moved
say s:value() + 1
d = col:dropdown(["S", "M"], "M")
d:options(["S", "M", "L"])
d:set "L"
d:change typed
t = app:table(["Name", "Role"])
r = t:add(["Ada", "Admin"])
r:set(["Ada", "Owner"])
t:change row_picked
tabs = app:tabs()
home = tabs:tab "Home"
home:opened go
home:heading "Home"
tabs:tab "More"
tabs:open "More"
tabs:change typed
say tabs:value()
sc = app:scroll()
sc:to_bottom
sp = app:split(200)
sp:column
sp:column
app:image("https://example.com/cat.png", 120)
app:progress(40):set 80
spin = app:spinner("Thinking", 18)
spin:style "dots"
spin:stop
app:divider
app:space 20
md = app:markdown "# Hi"
md:add " there"
code = app:code("say 1", "tuff")
code:set "say 2"
app:html("<b>bold</b>"):set "<i>it</i>"
ch = app:chart([1, 3, 2], "bar")
ch:add 5
app:icon "search"
m = app:menu()
m:item("Copy", copied):icon "copy"
m:divider
m:item("Delete", copied, "danger")
dlg = app:modal("Rename")
dlg:input "New name"
dlg:closed go
dlg:open
dlg:close
app:toast("Saved", "success")
app:key("ctrl+shift+n", go)
app:key("escape", go)
app:key("f5", go)
tm = app:every(1, go)
tm:stop
tm:start
app:after(0.5, go)
app:closed go
if app:confirm "Sure?":
    say app:ask "Name?"
app:alert "Done"

func go():
    say 1

func lit(on):
    say on

func typed(t):
    say t

func moved(n):
    say n + 1

func picked(name):
    say name

func row_picked(cells):
    say cells[0]

func copied(what):
    say what
'''),
    ("frameless with a title bar", APP + 'app:frameless\nbar = app:titlebar("Notes")\nbar:input "Search"\nbar:set "Notes!"\napp:minimize\napp:maximize\n'),
    ("button functions with and without the text", APP + 'app:button("A", one)\napp:button("B", two)\nfunc one():\n    say 1\nfunc two(name):\n    say name\n'),
    ("the guide's habit: self-test", APP + 'n = app:text "0"\napp:after(0.5, selftest)\nfunc selftest():\n    say n:value()\n    app:close\n'),
    ("mtgui's pages and gradient", APP + 'app:gradient("#00c6ff", "#7b2ff7")\nhome = app:page "Home"\nhome:heading "Home"\n'
                                         'menu = app:page "Menu"\nmenu:opened shown\nhome:open\nsay menu:showing()\n'
                                         'func shown():\n    say 1\n'),
    ("toggle (tgui's name for a switch)", APP + 't = app:toggle("Wi-Fi", true)\nsay t:value()\n'),
    ("window icon file in temp", APP + 'app:icon "logo.png"\n'),
    ("examples: chat", None, "examples/chat.tuf"),
    ("examples: settings", None, "examples/settings.tuf"),
    ("examples: dashboard", None, "examples/dashboard.tuf"),
]


def check(code=None, path=None, folder=None):
    if path is None:
        d = folder or tempfile.mkdtemp(prefix="atgui-check-")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"case{next(COUNT)}.tuf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
    r = subprocess.run([sys.executable, TUFF, "--check", path], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    project = os.path.join(HERE, "out", "check-project")  # outside %TEMP%, so picture files are checked
    tmp = tempfile.TemporaryDirectory(prefix="atgui-check-")
    jobs = []
    for case in CATCH:
        name, code, want = case[:3]
        jobs.append(("catch", name, want, (code, None, project if len(case) > 3 else tmp.name)))
    for case in OK:
        name, code = case[:2]
        path = os.path.join(HERE, case[2]) if len(case) > 2 else None
        jobs.append(("ok", name, None, (code, path, tmp.name)))
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda j: check(*j[3]), jobs))
    passed = failed = 0
    failures = []
    for (what, name, want, _), (code, out) in zip(jobs, results):
        ok = (code == 1 and want in out) if what == "catch" else (code == 0 and out == "OK")
        label = f"--check catches {name}" if what == "catch" else f"--check accepts {name}"
        print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"\n        got: {out[:400]}"), flush=True)
        passed += ok
        failed += not ok
        if not ok:
            failures.append(label)
    tmp.cleanup()
    print(f"check: {passed} passed, {failed} failed", flush=True)
    if "--out" in sys.argv:
        with open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8") as f:
            json.dump({"test": "check", "passed": passed, "failed": failed, "failures": failures}, f, indent=2)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
