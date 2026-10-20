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
| `x // 2`, `int(x)` on a number | `floor(x / 2)`, `floor(x)` (for numbers 0 or more) |
| `x++`, `x %= 3` | `x += 1`, `x = x % 3` (only `+= -= *= /=` exist) |
| `str(x)`, `int(s)` or `float(s)` on text | `text(x)`, `number(s)` (whole only if the text has no ".") |
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
- never use a built-in's name for your own variable: `sum = 0` replaces `sum()` everywhere. The built-ins are `print`, `text`, `number`, `len`, `round`, `random`, `wait`, `range`, `clear`, `sqrt`, `abs`, `floor`, `ceil`, `min`, `max`, `sum`, `average`, `pi` and `all`.

## Basics
```tuff
# comments start with #
say "Hello"                 # show a line
name = input "Your name? "  # ask a question (always gives back text)
score = 10
score += 5                  # also -= *= /=
if score is 15:             # 'then' works instead of ':'
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
  - Turn it into a number first: `number("42")` is 42 and `number("4.5")` is 4.5. Spaces around the number are ignored: `number(" 5 ")` is 5.
  - But `number("abc")` **stops the program** with an error, so check typed text first (`is_number` in "Patterns").

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
- **What windows can't do:** there's no drawing (no canvas, shapes or moving sprites) and no sound. The only keyboard input is typing in a text box and pressing Enter. The only mouse input is clicking buttons, switches, checkboxes, sliders and dropdowns. Keep this in mind before planning a game.

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
# Is this text a number? (number() stops the program on bad text)
func is_number(t):
    t = t:trim()
    num_digits = 0
    num_dots = 0
    num_pos = 0
    for num_ch in t:
        if "0123456789":has(num_ch):
            num_digits += 1
        elif num_ch is ".":
            num_dots += 1
        elif not (num_ch is "-" and num_pos is 0):
            return false
        num_pos += 1
    return num_digits > 0 and num_dots <= 1

# Keep asking until the answer is a number (console programs)
func ask_number(question):
    an_asked = input question
    while not is_number(an_asked):
        say "Please type a number."
        an_asked = input question
    return number(an_asked)

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
In a window app, check a text box before using it: `if not is_number(bill:value()): status:set "Type a number"`.

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
- drawing, sound, or keyboard and mouse events (see "How a window app runs");
- `exit()`, or Python modules.

There's no date or time function either. A clock widget's `:value` gives the time of day, and `wait(seconds)` pauses a console program.
