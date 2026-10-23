# Tuff language guide

Tuff is a small, beginner-friendly language made for TuffCode. Files end in `.tuf`. It reads a lot like Python, but it is **not** Python, so read the table and the two rules below before writing any Tuff. Then run the `tuff_check` tool on everything you write.

## Tuff is not Python
| Instead of (Python) | Write (Tuff) |
| --- | --- |
| `print("hi")` | `say "hi"` (`print(a, b)` also works) |
| `name = input("Name? ")` | `name = input "Name? "` on its own line (see "Asking questions") |
| `def greet(name):` | `func greet(name):` |
| `True`, `False`, `None` | `true`, `false`, `nil` |
| `x == y`, `x != y` | `x is y`, `x is not y` (`==` and `!=` also work) |
| `x ** 2` | `x ^ 2` |
| `x // 2` | `floor(x / 2)` (or `int(x / 2)`, which drops the decimals toward zero) |
| `x++`, `x %= 3` | `x += 1`, `x = x % 3` (only `+= -= *= /=` exist) |
| `str(x)`, `int(s)`, `float(s)` | `str(x)` and `text(x)` both work; `number(s)` or `num(s)` (a decimal only if the text has a "."); `int(s)` for a whole number. There's no `float`. |
| `f"Hi {name}"`, `.format()` | `"Hi " + name`. Numbers join on their own (`"Score: " + 5`), but put sums in brackets: `"Score: " + (score + 1)` |
| `items.append(x)` | `items:add(x)` |
| `s.upper()`, `s.strip()` | `s:upper()`, `s:trim()` |
| `x in items`, `"a" in s` | `items:has(x)`, `s:has("a")` (`in` only appears in `for` loops) |
| `range(3)` gives 0, 1, 2 | `range(3)` gives 1, 2, 3, and `range(1, 3)` gives 1, 2, 3: both ends are included |
| `for i in range(len(items)):` | `for item in items:`, or `for i in range(0, len(items) - 1):` |
| `thing.method()` | `thing:method()`, with no spaces around the `:` (only libraries use a dot: `mtgui.window(...)`) |
| `&&`, `\|\|`, `!` | `and`, `or`, `not` |
| `1 < x < 9` | `x > 1 and x < 9` |
| `a, b = 1, 2` | one per line: `a = 1`, then `b = 2` |
| `pass` | `nil` (a line that does nothing) |
| `.5`, `1e3`, `1_000` | `0.5`, `1000` |
| `[0] * 3` | `[0, 0, 0]` |
| default or keyword inputs, `global` | plain inputs only; `global` isn't needed (see rule 2) |
| `print(x, end="")` | an error: build the whole line with `+` first, or add to a shown line with `line:append(...)` |
| `import random`, `import math` | nothing to import. Built in: `random(a, b)`, `sqrt`, `floor`, `ceil`, `round`, `abs`, `min`, `max`, `sum`, `average`, `pi`. There's no sin, cos, tan, log or exp, no `random.choice` (use `items[random(0, len(items) - 1)]`) and no shuffle |
| `requests.get(url)`, `json.loads(...)` | `mention tap`, then `res = tap.get(url)` and `res:json` (see "tap") |
| `import pygame` | `mention tgame`, then `game = tgame.window("Title", 800, 600)` (see "tgame") |
| dictionaries, classes, `try`/`except`, `lambda`, slices like `s[1:3]`, `sort()`, `split()`, `exit()` | not in Tuff (see "What Tuff can't do") |

These words are keywords and can't be names: `func return if elif else then while for in break continue and or not is true false nil say input flush import mention`.

## Two rules that trip everyone up
**Rule 1: a method's input without brackets takes the rest of the line.** When what follows a method's name could start a value (a name, a number, text, `-`, `[`, `not`, `true`, `false` or `nil`), that and the rest of the line are the method's input. `items:has x and ready` means `items:has(x and ready)`, and `say slider:value - 1` gives the slider an input of `-1`. Anything else ends the call: `stack:pop + 10` is normal maths. So whenever more of the line follows a method call, put its inputs in brackets, even empty ones:
```tuff
items = ["eggs"]
ready = true
if items:has("eggs") and ready:
    say "go"
level = 5
say level - 1
```
- With `slider = app:slider(0, 10)`, write `slider:value() - 1`.
- Brackets are only optional when the method call ends the line, like `app:heading "Hi"` or `box:set "Done"`.
- An input that *starts* with a bracket counts as the method's own brackets: `label:set (score) + " points"` means `label:set(score) + " points"`. Wrap the whole input instead: `label:set(text(score) + " points")`.

**Rule 2: names are shared.** A variable made at the top of the program can be changed by any function. Inside a function, `x = 5` (or `for x in ...`) changes the top-level `x` if that already exists when the function runs. Otherwise `x` is a scratch name that only lives inside the function, and disappears when it ends. So:
- give every top-level variable its starting value near the top of the program (`score = 0`), before calling functions that use it;
- give each function's scratch values names that aren't used anywhere else (`total_count`, not `i`, if the top level has an `i`);
- never use a built-in's name for your own variable: `sum = 0` replaces `sum()` everywhere. The built-ins are `print`, `text`, `str`, `number`, `num`, `int`, `len`, `round`, `random`, `wait`, `range`, `clear`, `sqrt`, `abs`, `floor`, `ceil`, `min`, `max`, `sum`, `average`, `pi`, `err` and `all`.

## Basics
```tuff
# comments start with #
say "Hello"                 # show a line
name = input "Your name? "  # ask a question (always gives back text)
score = 10
score += 5                  # also -= *= /=
if score is 15:             # 'then' works instead of ':' (so does 'then:')
    say "fifteen"
elif score > 20:            # 'else if' works too
    say "big"
else:
    say "small"
for n in range(1, 3):       # 1, 2, 3
    say n
while score > 0:
    score -= 1
    if score is 3:
        break               # 'continue' works too
func double(n):
    n * 2                   # a function gives back its last value; 'return' also works
say double(4)
```
- **Blocks:** blocks are indented 4 spaces after a line ending in `:` (or `then`). 2 spaces or a tab also work, as long as the lines of a block line up. A one-line block also works, `if score > 3: say "big"`, but always put a space after the `:`. `if score > 3:say "big"` is read as a method call.
- **Line breaks:** a line can only continue onto the next one inside brackets, like a list written over several lines.
- **True and false:**
  - `and`, `or` and `not` work as you'd expect.
  - `nil`, `false`, `0`, `""` and `[]` count as false, and everything else counts as true.
  - `and` and `or` give back one of their sides, so `name = typed or "nobody"` gives a default.
- **Comparing:**
  - Compare with `is`, `is not`, `==`, `!=`, `<`, `>`, `<=` and `>=`.
  - Different kinds of value are never equal: `"5" is 5` and `true is 1` are both false. Comparing text with a number is always a mistake, so `tuff_check` reports it.
  - Comparing text with a number using `<` is an error.
  - Text compares alphabetically, capitals first (`"Banana" < "apple"`), so two typed answers compare as text: `"10" > "9"` is false. Turn them into numbers first.

### Asking questions
`input` isn't an ordinary function: everything after it on the line is its question. Give it a line of its own and store the answer: `answer = input "Again? "`, then `while answer is "y":`. The only other safe place is directly inside a call, like `number(input "Age? ")`. `while input "More? " is "y":` asks the question `false`, and `input("x") + "!"` is an error. The answer keeps any spaces typed around it, so trim it before comparing: `answer = answer:trim()`.

## Numbers
- **Maths:** `+ - * /`, `%` (remainder) and `^` (power, so `2 ^ 10` is 1024). There are no chained comparisons.
- **Decimals:**
  - `/` always gives a decimal: `7 / 2` is 3.5, and `10 / 5` shows as 2 but is still a decimal.
  - So does anything worked out from a decimal: `/=`, `average(...)`, `round(x, 2)`, `number("2.0")`, `abs(-1.0)`, or a sum with a decimal in it.
  - A decimal can't be a list position or repeat text. Use `floor(...)` to get a whole number.
- **Showing decimals:** decimals show every digit: `0.1 + 0.2` shows 0.30000000000000004, and `1 / 3` shows 0.3333333333333333. Round any worked-out decimal before showing it, with `round(x, 2)` or `one_decimal` / `as_money` from "Patterns". Whole numbers show without `.0`.
- **Built in:** `round(x)`, `round(x, 2)`, `floor`, `ceil`, `abs`, `sqrt`, `min`, `max`, `sum`, `average` (give several numbers or one list), and `pi`.
  - `round` rounds exact halves to the even number: `round(2.5)` is 2 and `round(82.25, 1)` is 82.2. For money and grades, use `round_half_up` from "Patterns".
- **Random numbers:**
  - `random(1, 6)` gives a whole number from 1 to 6, both included. `random(10)` gives 1 to 10.
  - It needs whole numbers, and `random()` with no inputs is an error.
  - For a decimal, divide: `random(0, 100) / 100`.
- **Typed numbers:** `input` always gives text, so `"5" + 1` is `"51"` and `"5" * 2` is `"55"`.
  - Turn it into a number first: `number("42")` is 42 and `number("4.5")` is 4.5. Spaces around the number are ignored: `number(" 5 ")` is 5. `num(...)` is a short name for `number(...)`.
  - `int(...)` gives a whole number, dropping the decimals toward zero: `int("42")` is 42, `int(3.7)` and `int("3.7")` are 3, `int(-2.9)` is -2. `str(...)` is the same as `text(...)`.
  - Text that isn't a number gives **`err`** instead of a number: `number("abc")`, `num("abc")` and `int("abc")` are all `err`. Check before using it: `if num(answer) is err:`. An `err` counts as false in an `if`.
  - Using an `err` in maths or a function stops the program and says why: "Can't use + here, because one side is err: number() couldn't turn 'abc' into a number." (`say`, `print` and `text(...)` just show it as `err`.)
  - Anything else that isn't text or a number stops the program: `num(nil)`, `num([5])`, or a text box itself (`num(box)` instead of `num(box:value())`).

## Text
- **Joining:** join with `+`: `"Hi " + name + "!"`. Anything joined with text becomes text: numbers, true/false, nil and even lists.
  - `+` works left to right, so `"Total: " + a + b` gives "Total: 23". Put the maths in brackets: `"Total: " + (a + b)`.
- **Repeating and letters:**
  - `"ha" * 3` is `"hahaha"`. The number must be whole, and 0 or less gives `""`.
  - Use `len(t)`, `t[0]`, and `t[-1]` for the last letter.
  - `for letter in t:` goes through it.
  - A letter can't be changed in place; build new text with `+`.
- **Methods:** `t:upper()`, `t:lower()`, `t:trim()` (removes spaces at both ends) and `t:has("x")` (true or false). They give back new text; `t:trim()` on its own line changes nothing, so write `t = t:trim()`.
- **Escapes:**
  - `"line 1\nline 2"`, `"tab\there"`, `"say \"hi\""` and `"back\\slash"`.
  - Single quotes work too: `'it\'s'`.
  - A backslash before any other letter stays as it is, but `\n` and `\t` still mean a new line and a tab, so write file paths with forward slashes: `"pics/cat.png"`.
- **Not in Tuff:** split, replace, join, slicing (`t[1:3]`) and formatting. Build text with `+` and loops instead.

## Lists
```tuff
items = ["milk", "eggs"]
items:add("bread")          # add to the end
items:remove("milk")        # remove by VALUE: only the first match, an error if it isn't there
last = items:pop()          # take off the last item and give it back (an error if the list is empty)
say items:has("eggs")       # true
say items[0]                # the first item; items[-1] is the last
items[0] = "cheese"         # change an item
say len(items)
for item in items:
    say item
both = items + ["jam"]      # join two lists (makes a new list)
```
- **Positions:** positions go from 0 to `len(items) - 1`, and `range(0, len(items) - 1)` gives every position.
- **Ranges:** `range(10, 1, -3)` gives 10, 7, 4, 1, and `range(5, 1)` gives an empty list.
- **Removing:**
  - `:pop` always takes the last item, and giving it a position is an error.
  - To remove by position, see `remove_at` in "Patterns".
  - To remove every copy of a value: `while items:has(x):` then `items:remove(x)`.
- **Joining:** `+` only joins lists when both sides are lists. `items + "jam"` turns the whole list into text, so use `items:add("jam")`.
- **Sharing:** lists are shared, not copied. After `b = a`, adding to `b` also changes `a`. Make a copy with `b = a + []`; lists inside it are still shared.
- **What lists hold:** lists can hold anything, including other lists (`grid[0][1] = 9`), and can be written over several lines.
- **Showing a list:** `say ["a", "b"]` shows `["a", "b"]`, with text items in quotes, and so does a list joined with text. To show the items without quotes, `say` each one in a loop.
- **Not in Tuff:** there's no sort and there are no dictionaries. Keep two lists side by side instead, like `names` and `scores`.

## Functions
- `func name(a, b):` then an indented body. The last line's value is given back automatically. A loop gives back nil, and `say` gives back the line it showed (so a function ending in `say w * h` gives back the text "12", not a number). End with `return value` when the answer matters.
- A function with no inputs can leave out the brackets when it's made (`func greet:`), but calling it always needs them: `greet()`. `greet` on its own line does nothing.
- Call a function with exactly as many inputs as it has. There are no default or keyword inputs.
- `return` only works inside a function.
- **Make every function at the top level of the file**, not inside another function or inside `if`, `for` or `while`. Top-level functions can be used anywhere, even above where they're written. A function made inside a block or another function only exists there, and only once its line has run.
- Inputs belong to the function. Any other name follows rule 2.
- Functions can call themselves, but only about 100 calls deep. Use a loop for anything that could go deeper.

## Live lines and clearing (console programs)
```tuff
line = say "Loading"
wait(1)                     # pause for 1 second
line:rewrite("Done!")       # replace a line you already showed
line:append(" (in 1 s)")    # add to the end of it
say line:text()             # what the line says now
flush                       # clear the whole screen
clear(2)                    # remove the last 2 lines; clear(all) is the same as flush
```
`say` and `print(...)` both give back the line they showed, so `say print(1, 2)` shows "1 2" twice.

## Libraries
`import x` and `mention x` mean the same thing. Put them at the top. Library functions use a dot and always need brackets, even with no inputs: `anims.loading()`. On its own, `anims.loading` does nothing.
- **anims** shows console animations. They stop everything else while they play, so don't use them in window apps.
  - `anims.loading(text, seconds)` (defaults: "Loading", 2)
  - `anims.bar(text, seconds, width)` (defaults: "Working", 2, 20)
  - `anims.type(text, seconds_per_letter)`: the text is required; 0.04 by default, and bigger is slower
  - `anims.countdown(start, then)` (defaults: 3, "Go!"): shows start, start - 1 … 1, one per second, then replaces the line with the text `then`
- **tgui**: real desktop app windows. **mtgui**: the same widgets with a modern look (gradients, gloss, glow). Use mtgui unless asked otherwise.
- **tap** gets and sends things on the web (HTTP), like Python's requests. See below.
- **atgui** ("advanced tgui") makes apps that look like the Claude or Codex desktop apps: sidebars, lists, chat bubbles, dashboards, menus and pop-ups, all styled from Tuff. See below.
- **tgame** makes games, like pygame: 2D sprites, keys, the mouse, collisions and sounds, or a 3D world with a player. See below.

### tap
```tuff
mention tap

res = tap.get("https://api.github.com/users/octocat")
if res:ok:
    user = res:json                 # a JSON object comes back as a data object
    say user:get("name") + " has " + user:get("public_repos") + " public repos"
else:
    say "Error " + res:status

note = tap.data()                   # an empty data object, to send
note:set("title", "Hello")
note:set("tags", ["a", "b"])
sent = tap.post("https://httpbin.org/post", note)
say sent:status
```
- **Requests:** `tap.get(url)`, `tap.post(url, body)`, `tap.put(url, body)` and `tap.delete(url)`. Text is sent as plain text, and a data object or a list as JSON. Headers go last, as a data object: `tap.get(url, headers)`.
- **A response:** `res:status` (like 200 or 404), `res:ok` (true for 200 to 299), `res:text`, `res:json` and `res:header("Content-Type")` (nil if it isn't there).
- **Errors:** a 404 or 500 doesn't stop the program, so check `res:ok`. No internet, a bad address, no answer within 15 seconds, and `res:json` on something that isn't JSON do stop it with an error.
- **JSON:** `res:json` gives a data object for `{...}`, a list for `[...]`, or text, a number, true/false or nil.
- **Data objects:** `user:get("name")` (not `user["name"]`; nil if it's missing), `user:has("name")`, `user:keys()` (a list of the names), `user:size()` and `user:set("name", value)`. Objects inside are data objects too, and `say user` shows it as JSON. Loop over `user:keys()`, not `user`.
- **Waiting:** each call waits for the answer, and a window freezes while it waits.

### atgui
Modern app windows made of real HTML and CSS, without writing any HTML. Most of mtgui works the same (`heading`, `text`, `button`, `input`, `:set`, `:value`, `:change`, `app:every`, `app:ask`...; see "App windows" below), plus everything here.
```tuff
mention atgui

app = atgui.window("Notes", 900, 600)      # title, width, height (all optional)
app:accent "indigo"
side = app:sidebar(240)                     # a column down the left side
side:heading "Notes"
notes = side:list(["Ideas", "Shopping"])    # click an item to pick it
notes:change opened
title = app:heading "Ideas"
app:textarea "Write something"
row = app:row
row:button("Save", save, "primary"):icon "check"
row:button("Delete", delete_note, "danger")
app:key("ctrl+s", save)

func opened(name):                          # a list's :change gets the item's text
    title:set name

func save():
    app:toast("Saved " + title:value(), "success")

func delete_note():
    if app:confirm "Delete this note?":
        notes:remove title:value()
```
- **How it runs:** like mtgui, but the window opens once the top-level code has run (or at the first popup), so the first screen shows all at once. A Tuff error in an event function is shown once, with its line, and the app keeps going. One window per program: use `app:tabs()`, pages (`app:page "Home"`, as in mtgui), a sidebar list or `app:modal(...)` for more screens.
- **Widgets** go on the window, a `row`, `column`, `card`, `grid(3)` (3 columns), `scroll()`, `sidebar`, tab or modal: `heading`, `text`, `small`, `button(text, fn, style)`, `input`, `textarea`, `checkbox`, `switch` (or `toggle`), `slider(low, high, start)`, `dropdown(list, choice)`, `list(items)`, `table(["Name", "Role"])`, `tabs()`, `image(file or web address, width)`, `icon(name, size)`, `avatar("Ada Lovelace")`, `badge(text, style)`, `progress(percent)`, `spinner(label)`, `markdown(text)`, `code(text, language)`, `chart([3, 8, 5], "line")` (or `"bar"`), `divider`, `space 20` and `html(text)`.
  - Button styles: primary, secondary, outline, ghost, success, danger, gradient. Badge styles: accent, gray, success, warning, danger, info, outline. `spinner:style "dots"` makes a typing indicator.
  - Icons: home, search, settings, user, users, chat, message, send, plus, minus, x, check, chevron-down (and -up, -left, -right), arrow-up (and -down, -left, -right), menu, more, bell, star, heart, trash, edit, compose, copy, download, upload, folder, file, mail, calendar, clock, lock, sun, moon, info, warning, error, success, help, bolt, sparkle, chart, trend, activity, grid, list, layers, play, pause, stop, refresh, link, image, code, terminal, globe, logout, filter, eye, bookmark, cloud, camera, mic, attach, sidebar, cart, dollar, flag, pin, bot, smile and dot. `btn:icon "send"` puts one on a button (with `""` as the text, only the icon shows).
- **Layout:** the window, columns, cards and scrolls stack things down; a row puts them side by side.
  - `box:gap 12`, `box:padding 20`, `box:align "center"` (across: start, center, end, stretch), `box:justify "between"` (along: start, center, end, between, around, evenly).
  - `w:grow` takes the space left, `w:fill` stretches across, `w:width 200` and `w:height 120` (numbers are pixels; text like `"50%"` works too).
  - The window scrolls when things don't fit. A `scroll()` scrolls on its own and takes the space left, like a chat's messages: `msgs:to_bottom` scrolls to the end.
  - `app:sidebar(240)` (or `app:sidebar(240, "right")`) and `app:split(260)` (two panes with a handle to drag).
- **Changing things:** every widget has `:show`, `:hide` and `:remove`.
  - A list: `items:add("Inbox")` gives back the item, which takes `:icon`, `:small` (a second line) and `:badge`. Also `items:remove "Inbox"`, `items:set "Inbox"` (picks it), `items:value()`, `items:items()` and `items:clear`. A table: `t:add(["Ada", "Admin"])`.
  - Markdown, code and charts have `:add` (more at the end), so a reply can arrive bit by bit.
- **Events:** functions may leave out the input they're given.
  - `w:clicked fn` works on any widget, and a click's function gets the widget's text, so one function can serve many buttons.
  - `:change fn`; `box:enter fn` (in a textarea Enter sends and Shift+Enter starts a new line); `w:hover fn` and `box:focus fn` get true or false (`box:focus` on its own puts the cursor there).
  - `app:key("ctrl+s", fn)` for a key (also "escape", "f5", "ctrl+shift+n"), and `app:closed fn` when the window closes.
  - `app:every` and `app:after` give back a timer with `:stop` and `:start`.
- **Pop-ups:** `dlg = app:modal("Rename")`, add widgets to it, then `dlg:open`; Escape or a click outside closes it (`dlg:closed fn`). `m = app:menu()` with `m:item("Delete", fn, "danger")` and `m:divider`: `w:menu m` opens it on a right-click (the item's function gets the right-clicked list item's text), and `m:open` opens it under what was just clicked. `app:toast("Saved", "success")` (info, success, warning, error) and `w:tooltip "Hint"`.
- **Looks:**
  - `app:theme "light"` (dark, light or system), `app:accent "teal"` (the mtgui colors, indigo, gray or `"#rrggbb"`) and `app:font "rounded"` (system, rounded, serif, mono or a font's name).
  - `w:style(name, value)`: background, color, radius, padding, margin, border, shadow (small, medium, large, glow), size, bold, weight, opacity, glass (frosted), blur, gradient (`["#6366f1", "#ec4899"]`), width, height, scale, rotate, span (grid columns). Colors are the accent names, white, black, accent, muted, raised, surface or `"#rrggbb"`. Start the name with hover, pressed or focus: `btn:style("hover scale", 1.05)`.
  - `w:animate "slide-up"`: fade-in, fade-out, slide-up, slide-down, slide-left, slide-right, pop, zoom-in, zoom-out, bounce, shake, pulse, spin, wiggle, float, blink. `w:animate("pulse", 1, "forever")` repeats; `w:animate "none"` stops. Style changes fade smoothly on their own.
  - For experts: `w:css("letter-spacing: 2px")`, `app:css(".at-card { border-width: 2px }")` and `app:html("<b>Hi</b>")`.
- **The window:** `app:titlebar("My App")` (at the top of the program) swaps the system frame for a title bar you can add things to, with minimize, maximize and close. `app:frameless` has no title bar at all. `app:icon "logo.png"` sets the window's icon (a .png or .ico), but `app:icon "search"` shows a built-in icon.
```tuff
mention atgui

app = atgui.window("Timer", 420, 340)
app:theme "light"
app:accent "pink"
seconds = 0
card = app:card
card:style("radius", 20)
card:style("hover shadow", "glow")
shown = card:heading "0"
shown:style("size", 48)
row = card:row
row:button("Start", start, "gradient"):icon "play"
row:button("Reset", reset, "ghost")
clock = app:every(1, tick)
clock:stop
app:key("space", start)

func start():
    clock:start
    shown:animate "pop"

func tick():
    seconds += 1
    shown:set text(seconds)

func reset():
    clock:stop
    seconds = 0
    shown:set "0"
    app:toast("Back to 0", "info")
```
### tgame
```tuff
mention tgame

game = tgame.window("Catch", 600, 400)        # title, width, height (all optional)
game:background "navy"
basket = game:box(300, 370, 80, 20, "gold")   # x, y (its middle), width, height, color
basket:on_edge "stop"                         # it can't leave the screen
star = game:circle(300, 0, 12, "yellow")      # x, y, radius, color
score = 0
label = game:text("Score: 0", 300, 24)        # words, x, y, then size and color if you like

while game:open():                            # until the window is closed
    dt = game:frame()                         # draws a frame; dt is the seconds since the last one
    if game:held("left"):
        basket:move(-400 * dt, 0)
    if game:held("right"):
        basket:move(400 * dt, 0)
    star:move(0, 200 * dt)
    if star:touches(basket):
        score += 1
        label:set "Score: " + score
        game:sound "coin"
        star:move_to(random(20, 580), 0)
    elif star:y() > 400:
        star:move_to(random(20, 580), 0)
```
- **Where things are:** x and y are the middle of a sprite. (0, 0) is the top-left corner, and y goes down. A spot like `[100, 50]` works anywhere x and y do: `food:move_to(game:random_spot())`.
- **Sprites:** `game:box(x, y, width, height, color)`, `game:circle(x, y, radius, color)`, `game:line(x1, y1, x2, y2, color)`, `game:text(words, x, y, size, color)` and `game:image("ship.png", x, y, width)` (a .png, .jpg, .gif or .webp next to your .tuf file, or in a folder inside it like `"art/ship.png"`; not `"../ship.png"`).
- **Moving:** `:move(dx, dy)`, `:move_to(x, y)`, `:glide(x, y, seconds)`, `:turn(degrees)` (more than 0 turns right), `:turn_to`, `:point_at(x, y)`, `:forward(distance)` (the way it points), `:spin(degrees_per_second)`, and `:speed(vx, vy)`, which keeps it moving by itself. `:on_edge "bounce"` (or `"wrap"` or `"stop"`) says what it does at the screen's edge. Read where it is with `:x()`, `:y()`, `:spot()` and `:angle()`.
- **Looks:** `:color`, `:size`, `:scale 2`, `:layer 2` (higher layers are on top), `:flip()`, `:hide`, `:show` and `:remove` (a removed sprite is gone for good: changing it does nothing). Text changes with `label:set "Hi"`, and `label:align "left"` makes x its left edge.
- **Collisions:** `a:touches(b)` is true or false. Given a list or a group, it gives back the one it touches, or nil: `hit = ball:touches(bricks)`. Also `:distance(other)` and `:on_screen()`.
- **Keys and the mouse:** `game:held("left")` is true while a key is down, and `game:pressed("space")` only in the frame it went down. Keys are letters, numbers, space, enter, escape, shift, up, down, left and right; `"mouse"` is the mouse button. `game:mouse_x()` and `game:mouse_y()`.
- **Values on things:** `tree:set("hp", 3)` and `tree:get("hp")` (nil if it was never set).
- **More:** `hud = game:hud()` is a layer on top for drawn scores (real buttons and menus go on a panel or a screen: see "Menus, buttons and screens in games" below), `game:group()` holds things that move together (`:add`, `:move`, `:count`, `:clear`), `game:random_spot(20)` keeps to a grid of 20, `game:camera(x, y)` scrolls, `game:time()` and `game:fps()`.
- **Sound:** `game:sound "coin"` plays beep, coin, jump, hit, boom, chop, laser, pop, click, step, powerup, win or lose, or a .wav, .mp3 or .ogg file. `game:music "song.mp3"` repeats, and `game:stop_music()`.
- **Pause and game over:** `game:pause("Paused")`, `game:resume()` and `game:paused()`. `game:game_over("Score: 5", start)` stops the game and shows the message; pressing space then runs `start`, which should put everything back.

**The callback style.** Instead of a loop, give tgame functions to run. The program then keeps going until its window closes.
```tuff
mention tgame

game = tgame.window("Dodge", 400, 300)
player = game:box(200, 270, 30, 30, "lime")
player:on_edge "stop"
rocks = game:group()

func step(dt):                    # every frame, with the seconds since the last one
    if game:held("left"):
        player:move(-250 * dt, 0)
    if game:held("right"):
        player:move(250 * dt, 0)
    if player:touches(rocks):
        game:game_over("Hit by a rock!", start)

func drop():                      # every second
    rock = game:circle(random(10, 390), 0, 10, "gray")
    rock:speed(0, 150)
    rocks:add(rock)

func start():                     # space after a game over runs this
    rocks:clear()

func dash(key):                   # gets the key's name
    player:move_to(200, 270)

game:every_frame step
game:every(1, drop)
game:on_key("space", dash)
```
- `game:on_key("any", fn)` runs for every key. `game:clicked fn` gets x and y, and `sprite:clicked fn` gets the sprite. `game:after(seconds, fn)` and `game:every(seconds, fn)` work like an app's, and pause with the game. An every-frame function keeps running while the game is paused, with dt 0, so it can check for the key that resumes it.
- Don't use `wait` or `input` in a game: they freeze it. A game has one window: for buttons, text boxes and menus, use a panel or a screen (below), not an atgui or mtgui window.

**3D.** `tgame.world` makes a 3D world. y is height, and an object's y is where its bottom is, so 0 sits on the ground.
```tuff
mention tgame

game = tgame.world("Lumberjack")
game:sky "sunset"                      # day, sunset, dawn, night, cloudy or space
game:island(80)
player = game:player("first person")   # WASD walks, Space jumps, click the game to look around
axe = player:hold("axe")
logs = 0
logs_label = game:hud():text("Logs: 0", 90, 30)
for i in range(1, 15):
    tree = game:spawn("tree")           # somewhere random
    tree:clicked chop
game:spawn("hut", -6, 0, -10)          # x, y, z

func chop(tree):
    axe:swing()
    if tree:distance(player) < 4 and not tree:fallen():
        tree:shake()
        tree:fall()
        tree:regrow(5)
        logs += 1
        logs_label:set "Logs: " + logs

while game:open():
    game:frame()
```
- **The world:** `:sky`, `:fog(distance)` (0 is off), `:sun(brightness)`, `:light(x, y, z, color)`, `:ground(color)` and `:island(size)`, or `:terrain(size)` for land with hills, mountains and lakes, and `:lighting "modern"` (both below).
- **Shapes:** `game:box(x, y, z, size, color)`, and the same for `sphere`, `cylinder`, `cone` and `plane`. size is a number, or a list: `[width, height, depth]` for a box, `[width, height]` for a cylinder or cone, and `[width, depth]` for a plane.
- **Ready-made models:** `game:spawn("pine", x, y, z)` makes a tree, pine, rock, bush, flower, house, hut, sign, crate, fence or coin. Without a spot it picks a random one.
- **Objects** have the sprites' methods with a z added (`:move(dx, dy, dz)`, `:glide(x, y, z, seconds)`...), plus `:shake()`, `:fall()`, `:fallen()`, `:regrow(seconds)`, `:grow()`, `:swing()`, `:glow "gold"`, `:label "Oak"` (text above it) and `:solid false` (the player walks through it).
- **The player:** `"first person"` or `"third person"`. Solid things block the way and can be stood on. `player:walk_speed 6`, `:jump_height 2`, `:hold "sword"` (axe, pickaxe, sword, torch or hammer), and `game:looking_at()` is the object in the middle of the view, or nil.
- **Without a player:** `game:camera_at(x, y, z)` with `game:look_at(thing)`, or `game:follow(thing)` (behind it), or `game:orbit(thing)` (drag to turn around it).
- **Testing a game:** add `game:after(2, selftest)`, call your functions in `func selftest():`, `say` what you find, and end it with `game:close()`.

#### Menus, buttons and screens in games
Real buttons, text boxes and menus go on a **panel** (pinned to a place on the game) or a **screen** (a layer over the whole game, for a title screen, a shop, a pause menu or game over). They work in 2D and 3D, and they're atgui's own widgets, so they look and work exactly as in the atgui section.
```tuff
mention tgame

game = tgame.window("Apple Shop", 600, 400)
game:background "sky"
basket = game:box(300, 370, 80, 20, "wood")
basket:on_edge "stop"
apple = game:circle(300, 0, 12, "red")
coins = 0
speed = 300

start = game:start_screen("Apple Shop", "Click to play")   # the game waits until it's clicked
start:text "Catch apples with the arrow keys, then spend the coins in the shop."

bar = game:panel("top left")                  # real widgets, pinned to the top left
coins_label = bar:heading "Coins: 0"
bar:button("Shop", open_shop):icon "cart"

shop = game:screen("Shop")                    # over the whole game: it pauses the game while it shows
shop:text "A faster basket catches more apples."
shop:button("Faster basket (5 coins)", buy_faster)
shop:button("Back to the game", close_shop, "secondary")
shop:hide()                                   # screens start shown, so hide it until it's needed

func open_shop():
    shop:show()

func close_shop():
    shop:hide()

func buy_faster():
    if coins >= 5:
        coins -= 5
        speed += 150
        coins_label:set "Coins: " + coins
        game:sound "powerup"

func step(dt):                                # dt is 0 while a screen pauses the game
    if game:held("left"):
        basket:move(-speed * dt, 0)
    if game:held("right"):
        basket:move(speed * dt, 0)
    apple:move(0, 200 * dt)
    if apple:touches(basket):
        coins += 1
        coins_label:set "Coins: " + coins
        apple:move_to(random(20, 580), 0)
    elif apple:y() > 400:
        apple:move_to(random(20, 580), 0)

game:every_frame step
```
- **Click to play:** `start = game:start_screen("Title", "Click to play")` (the hint is optional) shows a title screen, and the game waits behind it. A click, Enter or Space hides it and starts the game. In a 3D world with a first- or third-person player, that click also locks the mouse for looking around. Add more to it like any screen (`start:text "..."`), and `start:show()` brings it back, like after game over.
- **Panels:** `bar = game:panel("top left")` pins a column of widgets to a place on the game: `"top left"`, `"top"`, `"top right"`, `"left"`, `"center"`, `"right"`, `"bottom left"`, `"bottom"` or `"bottom right"`. Clicks on its widgets go to them, and clicks anywhere else reach the game. Panels never pause. `bar:hide`, `bar:show` and `bar:clear` (empties it).
- **Screens:** `shop = game:screen("Shop")` covers the game with a dimmed layer, with the title on top and its widgets in the middle. It starts shown: `shop:hide()` it until it's needed, then `shop:show()`. `shop:shown()` is true while it shows. While a screen shows, the game is paused like `game:pause()` (dt is 0, nothing moves and timers wait), and it goes on when the screen hides. `game:screen("Map", false)` doesn't pause. A pause menu and a game over screen are screens too: `over = game:screen("Game over")`, then `over:button("Play again", again)`.
- **Every atgui widget works on a panel or a screen:** `heading`, `text`, `small`, `button(text, fn, style)`, `input`, `textarea`, `checkbox`, `switch`, `slider(low, high, start)`, `dropdown(list, choice)`, `list`, `table`, `tabs`, `card`, `row`, `column`, `grid`, `scroll`, `image`, `icon`, `progress(percent)`, `spinner`, `divider`, `space`, `badge` and `markdown`, with their methods: `:set`, `:value`, `:show`, `:hide`, `:disable`, `:style`, `:animate`, `:change fn`, `:clicked fn`... A slider runs a function with `:change`: `volume = menu:slider(0, 100, 80)`, then `volume:change set_volume`.
- **Events:** a widget's function runs between frames, like the game's other events, so it can change the game. Keys typed into a text box don't move the player. `game:hud()` stays for drawn scores; use a panel for anything to click.
```tuff
mention tgame

game = tgame.world("Forest Walk")
game:sky "sunset"
game:island(60)
player = game:player("first person")
start = game:start_screen("Forest Walk")      # its click also locks the mouse for looking around
for i in range(1, 12):
    game:spawn("pine")

menu = game:screen("Paused")                  # a pause menu: P opens and closes it
volume = menu:slider(0, 100, 80)
volume:change set_volume
menu:button("Resume", close_menu)
menu:hide()
game:on_key("p", toggle_menu)

func set_volume(level):
    game:volume level

func close_menu():
    menu:hide()

func toggle_menu():
    if menu:shown():
        menu:hide()
    else:
        menu:show()

while game:open():
    game:frame()
```

#### Land and lighting (3D)
`game:terrain(size)` makes land you shape with hills, mountains, dips, lakes and valleys, or paint with brushes.
```tuff
mention tgame

game = tgame.world("Hills and Lake")
game:sky "day"
game:lighting "modern"                    # soft light from the sky and sharper shadows
land = game:terrain(200)                  # flat land 200 wide, around 0, 0
land:style "grass"                        # grass, desert, snow, rocky or autumn
land:hill(20, -10, 30, 8)                 # x, z, size (how wide), height
land:mountain(-40, -50, 60, 35)           # x, z, size, height: rocky, with a snowy top
land:lake(-20, 30, 36, 4)                 # x, z, size, depth: a hollow with water in it
land:valley(-60, 0, 60, 10, 18, 6)        # from x1, z1 to x2, z2, then width and depth
land:raise([[0, -25], [6, -27], [12, -26]], 8, 1.5)   # a brush stroke: spots, size, amount
game:spawn("pine", 20, 0, -10)            # y 0 is on the land: this pine stands on the hilltop
player = game:player("third person")
height = game:hud():text("", 110, 30)

while game:open():
    game:frame()
    height:set "Height: " + round(land:height_at(player:x(), player:z()))
```
- **The land:** `land = game:terrain(size)` is a flat square of land, size wide, around 0, 0. `game:terrain(200, "snow")` gives it a style too. A world has one terrain: change it with the land's methods. Use it instead of `:ground` or `:island`.
- **Shapes:** `land:hill(x, z, size, height)`, `land:mountain(x, z, size, height)` (tall and rough, with a snowy top), `land:dip(x, z, size, depth)` (a hollow), `land:lake(x, z, size, depth)` (a hollow with water up to where the ground was) and `land:valley(x1, z1, x2, z2, width, depth)` (a trench from one spot to the other). size is how wide it is, and everything is in metres. Each one fades out smoothly toward its edge, and they happen in order, so a lake dug into a hill sits on the hill. A hill with a negative height is a dip.
- **Brushes:** `land:raise(x, z, size, amount)` and `land:lower(x, z, size, amount)` push the land up or down, `land:smooth(x, z, size)` evens out bumps, and `land:flatten(x, z, size, height)` moves it toward that height (a flat spot to build on). A list of `[x, z]` spots in place of x and z is a brush stroke: `land:lower([[0, 0], [4, 2], [8, 3]], 6, 1)`.
- **Water and height:** `land:water(-1)` is a sea everywhere lower than that height. `land:height_at(x, z)` is how high the land is there, as a number.
- **Styles:** `land:style "desert"`: grass (the default), desert, snow, rocky or autumn. Low ground by the water is sandy, steep slopes are rock, and in grass, rocky and snow, high peaks are snowy.
- **y is the height above the land.** With a terrain, every y you give (shapes, `:spawn`, `:light`, `:move_to`, `camera_at`, `look_at`, where the player starts) and every y you read (`:y()`, `:spot()`) counts up from the land at that x and z, so 0 stands on it, on a hilltop or at the bottom of a valley. Without a terrain nothing changes. `game:random_spot()` stays on dry land, and the player walks over the hills but can't walk off the edge or into the water.
- **Modern lighting:** `game:lighting "modern"` lights everything softly from the sky, like newer game engines do (tone mapping, and bigger, sharper shadows), so the land, the water and the models look richer. `"simple"` (the default) is the classic look. It can change while the game runs, and a computer that can't do it stays simple.

#### Physics
`thing:physics()` makes a thing real: it falls, bounces, tumbles, knocks into other things and gets pushed. It works in 3D (boxes, spheres, cylinders and `spawn` models) and in 2D (boxes and circles). A game that never uses physics works exactly as before.
```tuff
mention tgame

world = tgame.world("Crash Test")
world:sky "day"
land = world:terrain(120)                 # with physics on, the land is solid
hits = 0
label = world:hud():text("Hits: 0", 90, 30)
for i in range(0, 4):
    crate = world:box(0, i * 1.05, -10, 1, "wood")   # a tower of crates
    crate:physics()                       # it falls, tumbles and can be pushed
    crate:mass(2)                         # kg
    crate:on_hit(bumped)
ball = world:sphere(0, 1, 2, 1, "red"):physics()     # physics() gives back the thing
ball:mass(5)
ball:bounce(0.4)                          # 0 doesn't bounce, 1 bounces right back up
dummy = world:ragdoll(4, 0, -8, "blue")   # a person made of parts that flops when it's hit
car = world:car(-5, 1, 6, "orange")
car:drive()                               # the arrow keys or WASD drive it, and the camera follows

func bumped(other, strength):             # something hit a crate: what, and how hard
    if strength > 2:
        hits += 1
        label:set "Hits: " + hits

func kick(key):                           # Space rolls the ball at the tower
    ball:push(0, 2, -40)

func boom(key):                           # B blows everything away from the tower
    world:explode(0, 0, -10, 15, 8)

world:on_key("space", kick)
world:on_key("b", boom)

while world:open():
    world:frame()
```
- **Kinds of physics:** `thing:physics()` (or `"dynamic"`) falls and can be pushed, `thing:physics("static")` stays where it is but things bump into it and land on it (a floor, a wall), `"kinematic"` is moved only by your code but pushes other things, and `"off"` turns it off. It gives back the thing, so it chains: `ball = world:sphere(0, 5, 0, 1, "red"):physics()`.
- **What it's made of:** `:mass(2)` is how heavy it is in kg (by default it comes from its size), `:bounce(0.6)` how bouncy it is from 0 to 1, and `:friction(0.4)` how grippy it is (0 is slippery, like ice).
- **Moving it:** `:push(x, y, z)` kicks it (a bigger number kicks harder, and heavy things move less), `:spin(x, y, z)` sets it spinning, and `:velocity(x, y, z)` sets how fast it's moving each way. `:velocity()` gives back `[x, y, z]`. `:sleep()` stops it until something wakes it, and `:wake()` wakes it.
- **Hits:** `crate:on_hit(bumped)` runs `func bumped(other, strength):` when something hits it: `other` is what hit it and `strength` how hard (under 1 is a gentle touch). It works on the player too. `:touches`, `:x()`, `:y()`, `:spot()` always give where a physics thing really is.
- **The world:** with physics on, the land, the ground, the island, the buildings and every other solid thing stay put, and physics things land on them (water isn't solid). `world:gravity(-9.8)` is how strong gravity is (-9.8 is like on Earth and the default, 0 floats like in space). `world:explode(x, y, z, strength, radius)` pushes every physics thing near a spot away from it, less the further away it is.
- **The player** walks into physics things and pushes them, can stand on them, and gets knocked by them. Its keys work as before.
- **A car:** `car = world:car(x, y, z, "red")` is a car with four wheels, springy suspension and steering. `car:drive()` lets the arrow keys or WASD drive it while the camera follows, and `car:drive(false)` stops. `car:engine(2)` gives it more power (1 is normal), `car:speed()` is how fast it's going in km/h, and `car:flip()` puts it back on its wheels after a crash.
- **A ragdoll:** `dummy = world:ragdoll(x, y, z, "blue")` is a person made of jointed parts (a head, a body, arms and legs) that flops over when it's hit or pushed: `dummy:push(0, 4, -6)`.
- **2D:** the same methods with x and y, and y goes down the screen. `game:gravity(900)` is in pixels a second each second, and `game:walls(true)` makes the edges of the screen walls.
```tuff
mention tgame

game = tgame.window("Bouncy", 800, 600)
game:gravity(900)                         # pixels a second each second, down the screen
game:walls(true)                          # the edges of the screen are walls
floor = game:box(400, 580, 800, 40, "gray"):physics("static")   # it stays put
ball = game:circle(400, 100, 20, "red"):physics()
ball:bounce(0.8)
boings = 0
label = game:text("Boings: 0", 400, 30)

func boing(other, strength):
    boings += 1
    label:set "Boings: " + boings
    game:sound "pop"

func jump(key):
    ball:push(0, -300)                    # up is minus in 2D

ball:on_hit(boing)
game:on_key("space", jump)
```
- **Tips:** don't move a physics thing every frame with `:move_to`, `:move` or `:glide`: that fights the physics, and it jumps around. Push it or set its velocity instead. One `:move_to` is fine, like putting it back after it fell off the edge. Tuff Engine's preview doesn't simulate: press Play to see things fall.
- **Animation:** character models walk with swinging arms and legs when they move and breathe gently when they stand still, trees and bushes sway in the wind, water ripples and coins spin and bob, all by themselves. `thing:animate("wave")` picks what a character does: `"walk"`, `"idle"`, `"wave"` or `"none"`.

#### Games Tuff Engine can edit
TuffCode's Tuff Engine tab (`Ctrl+Shift+G`) builds tgame games by clicking and dragging, and writes everything as normal Tuff code. It can only show and edit simple top-level lines, so when you change a game someone is building in it:
- Make each new thing with **one top-level line and plain numbers**, like `coin = game:circle(200, 200, 14, "gold")` or `tree = game:spawn("tree", -5, 0, -10)`. Things made in a loop, a function or a chained line (`game:spawn("sign"):label "Hi"`) still work, but show as "Made by your code" and can't be dragged.
- Put new lines **above** any `while game:open():` loop.
- Make the land with one line (`land = game:terrain(200)`) and change it with **one top-level line per edit**, like `land:hill(20, -10, 30, 8)`, so Tuff Engine can list them under the land, change their numbers and remove them.
- Give a thing its physics with **one top-level line each, right after it**, like `crate:physics()`, `crate:mass(2)`, `crate:bounce(0.6)` or `crate:friction(0.4)`, so its Physics section in Tuff Engine shows and changes them.
- Add behaviour as a **func registered with one line**, like `game:every_frame coin_spin` or `coin:clicked coin_clicked`. Functions under a `# Tuff Engine:` comment were written by Tuff Engine, and it keeps that comment and `play_again` up to date as the game changes. Changing one is fine: Tuff Engine then shows it as the person's own code.

## App windows (tgui / mtgui)
```tuff
mention mtgui

app = mtgui.window("Greeter", 380, 420)   # title, width, height (all optional)
app:accent "purple"
app:heading "Hello!"
name = app:input "Your name"
hello = app:text ""
row = app:row                              # things in a row sit side by side
row:button("Say hi", greet, "primary")     # text, function to run (no brackets!), style
row:button("Clear", clear_all, "ghost")
name:enter greet                           # run greet when Enter is pressed

func greet():
    hello:set "Hey " + name:value() + "!"

func clear_all():
    name:clear
    hello:set ""
```

**How a window app runs**
- **Startup:** the window appears at `mtgui.window(...)`, but nothing in it works (no clicks, no timers) until the program's last line has run. After that, everything happens in event functions.
  - One exception: while a popup is open in the top-level code, timers already run. So set every variable your timers use before the popup, or start the timers after it.
- **Waiting:** don't use `wait`, `input` or `anims` in a window app, because they freeze the window. Instead:
  - ask a question with `app:ask "Your name?"`, which gives back the text (`""` if cancelled);
  - ask yes or no with `app:confirm "Sure?"`, which gives back true or false;
  - show a message with `app:alert "Saved!"`;
  - do something later with `app:after(seconds, fn)`.

  Popups wait until they're answered.
- **Closing:** closing the first window ends the program.
- **Errors:** if an event function hits an error, the error is shown, that function stops, and the app keeps running. A timer whose function errors stops for good.
- **What windows can't do:** there's no drawing (no canvas, shapes or moving sprites) and no sound. The only keyboard input is typing in a text box and pressing Enter. The only mouse input is clicking buttons, switches, checkboxes, sliders and dropdowns. For a game, use tgame instead.

**Widgets** are made on the window, a row, a card or a page. They are `heading`, `text`, `small`, `button`, `input`, `toggle`, `checkbox`, `dropdown`, `slider`, `progress`, `spinner`, `clock`, `image`, `divider`, `space`, `row` and `card`.
- **Variables:** keep the widgets you need later in variables: `score_label = app:text "0"`.
- **Defaults:**
  - `app:button("Button")` is a primary button that does nothing when clicked.
  - `app:slider(0, 100)` starts at the lowest value.
  - `app:progress(0)`, `app:space 12`.
  - `app:clock("analog", 160)` and `app:spinner("", 28)`.
  - `app:dropdown(["A", "B"])` starts on the first choice.
  - Toggles and checkboxes start off.
- **Buttons:**
  - The styles are primary, secondary, outline, ghost, success and danger. Give every button except the main one a style like "ghost" or "outline".
  - Change a button later with `btn:set "New text"`, `btn:style "danger"`, `btn:disable` and `btn:enable`. Only buttons can be disabled.
- **Every widget** has `:hide`, `:show` and `:remove`. The window, a row, a card, a page or a text box also has `:clear`.
- **Other methods:**
  - `box:focus` puts the cursor in a text box, and `box:set "hi"` replaces its text.
  - `clock:style "digital"` and `clock:set(10, 30)`.
  - `dropdown:options(["X", "Y"])`.
  - `spinner:start` and `:stop`.
  - `image:set "other.png"`.
- **Pictures:** `app:image("cat.png", 200)` shows a .png or .gif file next to your .tuf file, at most 200 wide. `app:icon "icon.png"` also takes .ico. JPEG doesn't work.

**Reading and changing values**
- `:value` gives:
  - a text box: its text, or `""` while its grey hint is showing;
  - a dropdown: the chosen option, always as text (number choices too);
  - a switch or checkbox: true or false;
  - a slider: a number, which is whole if its ends are whole (for decimals, use 0 to 100 and divide);
  - a progress bar: 0 to 100;
  - a label or button: its text, so `count:set count:value() + 1` gives "01". Keep numbers in variables instead;
  - a clock: the time, like `"14:05:09"`.
- `:set` changes the value, but it does **not** run `:change`. To set a switch or checkbox and run its `:change` too, use `switch:set(true, true)`.

### Events: what the function gets
Pass the function's **name**: `app:button("Go", go)`.
- With brackets (`go()`), `go` runs once right away and its answer is passed instead. That usually stops the program with "A button needs a function name"; if `go` gives back nil, the button quietly does nothing.
- `app:button("Quit", app:close)` closes the window straight away. Make a small function (`func quit(): app:close`) and pass `quit`.
- All of this goes for `:click`, `:change`, `:enter`, `:opened`, `:every` and `:after` too.

| Event | Runs when | The function gets |
| --- | --- | --- |
| `app:button("Go", go)` or `btn:click go` | the button is clicked | nothing: `func go():` |
| `box:change typed` | every key typed in a text box | the text |
| `box:enter done` | Enter is pressed in a text box | the text |
| `dropdown:change picked` | a different choice is picked | the choice, as text |
| `switch:change flipped` (toggle or checkbox) | it's switched by a click | true or false |
| `slider:change moved` | the slider is dragged | the number |
| `page:opened shown` | that page is opened with `:open` | nothing |
| `app:every(1, tick)` | every second | nothing |
| `app:after(2, done)` | once, 2 seconds later | nothing |

- A function can leave out the input an event gives: `func typed():` is fine, and it can read `box:value()` instead.
- A function must **not** ask for more inputs than its event gives. `func go(x):` on a button shows an error every time it's clicked, and the button does nothing.
- A button can't pass a value to its function, so make one small function per button: `func pick_red(): choose("red")`.

### Timers
`app:every(seconds, fn)` keeps going until the window closes and can't be stopped directly. Use a variable to pause it:
```tuff
mention mtgui

app = mtgui.window("Counter", 300, 220)
running = false
count = 0
shown = app:heading "0"
app:button("Start / stop", start_stop, "primary")
app:every(0.1, tick)

func start_stop():
    running = not running      # changes the running made at the top

func tick():
    if not running:
        return
    count += 1
    shown:set text(count)
```
Timers aren't exact: a 0.1 second timer can run a little slow, so a stopwatch made by counting ticks drifts slightly.

### Pages (several screens in one window)
```tuff
mention mtgui

app = mtgui.window("My Shop", 380, 420)
app:heading "My Shop"          # on the window itself: shows on every page
home = app:page "Home"         # the first page made shows first
home:button("Menu", go_menu, "primary")
menu = app:page "Menu"
menu:text "Margherita $8"
menu:button("Back", go_home, "ghost")
menu:opened menu_shown         # runs each time Menu opens

func go_menu():
    menu:open                  # shows Menu, hides the other pages

func go_home():
    home:open

func menu_shown():
    say "Menu opened"
```
- `page:showing` is true while that page is on screen. `page:show` does the same as `page:open`.
- Pages go straight on the window, not inside cards or rows, and hold widgets just like a card.
- The first page's `:opened` doesn't run at the start. Opening the page that's already showing doesn't run it again.

### Layout and size
- **No scrolling:** a window doesn't scroll, so anything that doesn't fit is cut off. Make the window tall enough. Allow roughly:

  | Widget | Height |
  | --- | --- |
  | heading | 58 |
  | text | 30 |
  | small text | 25 |
  | button, text box or dropdown | 50 |
  | toggle | 36 |
  | checkbox | 34 |
  | slider | 38 |
  | progress bar | 20 |
  | spinner | 40 |
  | divider | 11 |
  | digital clock | 84 |
  | analog clock | its size + 12 (172 by default) |
  | `app:space N` | N + 10 |

  - A card adds about 36 to what's inside it.
  - A row is as tall as its tallest item + 10.
  - Long text wraps, and each extra line adds about 20 (text) or 40 (heading).
  - Add about 40 for the window's own padding.
- **Rows never wrap:** the space across a window is its width minus 48. In a row:
  - a button is about its text's width + 44 (at least 64), plus a 10 gap;
  - a text box is 240;
  - a dropdown is at least 160;
  - a slider or progress bar is 220.

  Anything that doesn't fit gets squeezed and then disappears, so split long rows into two.
- **Columns:** going down the window, a card or a page, these stretch to the full width: text boxes, dropdowns, sliders, progress bars, dividers, labels, cards and rows. Buttons, toggles and clocks keep their own size, on the left.
- **Nesting:** rows and cards can go inside each other. But text in a card that sits in a row wraps very narrow, so keep it to a word or a number, or put the cards one under another.
- **Sizes:** there are no align options, and most widgets have no width option. `app:image(path, width)`, `app:clock(style, size)` and `app:spinner(label, size)` take a size, and `app:size(width, height)` changes the window.

### Looking good
- **Color:** use mtgui with an accent that suits the app.
  - `app:accent "teal"` takes blue, purple, pink, red, orange, yellow, green, teal, or `"#rrggbb"` with exactly 6 digits.
  - `app:gradient("#00c6ff", "#7b2ff7")` sets two colors; tgui only uses the first.
  - `label:color` also takes white, black and gray, and `"text"` puts it back to normal.
  - Windows are dark unless you use `app:theme "light"`.
- **Structure:**
  - start with a `heading`;
  - group related things in `card`s;
  - put buttons side by side in a `row`;
  - use one `primary` button per screen, and `ghost` or `outline` for the rest.
- **Details:** use `small` for hints, `label:color "red"` for warnings, and `app:divider` and `app:space 12` for breathing room.

## Patterns
Every one of these has been run and works. Their scratch names are unique (rule 2), so they never change your variables. Their own names (`is_number`, `as_money` and so on) become top-level names, so don't also use those names for variables.
```tuff
# Is this text a number? (number() gives err when it isn't)
func is_number(t):
    return number(t) is not err

# Keep asking until the answer is a number (console programs)
func ask_number(question):
    an_asked = num(input question)
    while an_asked is err:
        say "Please type a number."
        an_asked = num(input question)
    return an_asked

# Round like people expect: 2.25 -> 2.3, 1.005 -> 1.01 (always gives a decimal;
# for a whole number use floor(x + 0.5))
func round_half_up(x, places):
    rh_scale = 10 ^ places
    rh_n = floor(round(abs(x) * rh_scale, 6) + 0.5) / rh_scale
    if x < 0:
        return -rh_n
    return rh_n

# Always one decimal: 80 -> "80.0", 7 / 3 -> "2.3"
func one_decimal(x):
    od_n = round_half_up(x, 1)
    if od_n is floor(od_n):
        return text(od_n) + ".0"
    return text(od_n)

# Money: 6.375 -> "$6.38", 18 -> "$18.00", -1.5 -> "-$1.50"
func as_money(x):
    mo_cents = floor(round(abs(x) * 100, 6) + 0.5)
    mo_rest = mo_cents % 100
    mo_text = "$" + text(floor(mo_cents / 100)) + "."
    if mo_rest < 10:
        mo_text += "0"
    mo_text += text(mo_rest)
    if x < 0 and mo_cents > 0:
        return "-" + mo_text
    return mo_text

# Seconds as m:ss: 75 -> "1:15" (for 0 or more; stop a countdown at 0)
func clock_text(seconds):
    ct_min = floor(seconds / 60)
    ct_sec = floor(seconds % 60)
    if ct_sec < 10:
        return text(ct_min) + ":0" + text(ct_sec)
    return text(ct_min) + ":" + text(ct_sec)

# A new list without the item at a position: tasks = remove_at(tasks, 2)
# (it leaves the old list alone; for the last item use tasks:pop())
func remove_at(items, position):
    ra_kept = []
    ra_pos = 0
    for ra_item in items:
        if ra_pos is not position:
            ra_kept:add(ra_item)
        ra_pos += 1
    return ra_kept
```
In a window app, check a text box before using it: `if num(bill:value()) is err: status:set "Type a number"`.

## Making a good program
- Keep the program's state in a few top-level variables (`score`, `tasks`), each set near the top, and write one small function per action.
- A `refresh()` function that rewrites every label from that state keeps the screen right. Call it after each change.
- Check what people type, and show a friendly message instead of letting the program stop with an error.
- Use clear names, keep functions short, and follow the two rules above.

## Using the tools
- **`tuff_check`** checks code without running it. Run it on every file you write or change. It catches:
  - **Names:**
    - syntax mistakes;
    - names that are never set, or only set inside another function;
    - built-ins replaced by variables;
    - functions made twice.
  - **Calls and events:**
    - wrong input counts;
    - event functions that would crash, are passed with brackets, or use `wait` or `input`;
    - functions whose answer is used but never given back.
  - **Methods and values:**
    - methods a value doesn't have;
    - method inputs that swallowed the rest of the line;
    - unknown styles, colors, themes and dropdown choices;
    - wrong picture files.
  - **Python habits and type mixups:**
    - the `range(len(...))` off-by-one;
    - `random()` and `:pop(0)`;
    - text mixed with numbers, like typed answers used as numbers or `"Total: " + a + b`;
    - chained comparisons;
    - `or "y"` in a condition;
    - lines whose answer is thrown away.

  It only checks a widget's methods when it knows what the value is, so a widget kept in a list or passed into a function isn't checked. It can't catch:
  - mistakes that depend on values while running, like the contents of a list or a position past its end;
  - widgets that don't fit the window.
- **`tuff_run`** runs a console program with your answers. It shows the final Run window, with each answer after its question; lines changed with `:rewrite` or `clear` show their final state. If the program asks more questions than there are answers, it stops with an error saying so.
- **Testing a window program:** window programs open a real window, so test them with a self-test.
  1. Add `app:after(0.5, selftest)` just before the last line.
  2. Write `func selftest():` so that it calls your event functions, uses `say` to show what it finds, and ends with `app:close`.
  3. Run it with `tuff_run`. The window shows for under a second, and you get the `say` output.
  4. Remove the self-test afterwards.

## What Tuff can't do
Tuff has none of these:
- files (except pictures for `image` and `icon`), or the internet except through `tap`;
- dictionaries, classes, sorting, or exceptions (`try`);
- splitting, replacing or formatting text, or slices;
- random decimals (divide a whole number instead), or sin, cos, tan, log or exp;
- drawing, sound, or keyboard and mouse events in tgui and mtgui (see "How a window app runs"). atgui has key shortcuts, hover and clicks on any widget, and a game made with `tgame` has all of them;
- `exit()`, or Python modules.

There's no date or time function either. A clock widget's `:value` gives the time of day, and `wait(seconds)` pauses a console program.
