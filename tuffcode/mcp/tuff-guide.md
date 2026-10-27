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
| `f"Hi {name}"` | the same: `f"Hi {name}, you have {score + 1}"` (see "Text templates"), or join with `+`: `"Hi " + name`. Numbers join on their own (`"Score: " + 5`), but put sums in brackets: `"Score: " + (score + 1)` |
| `items.append(x)` | `items:add(x)` |
| `s.upper()`, `s.strip()` | `s:upper()`, `s:trim()` |
| `x in items`, `"a" in s` | `items:has(x)`, `s:has("a")`, `ages:has("sam")` (`in` only appears in `for` loops) |
| `d = {"a": 1}`, `d["a"]`, `d.get("a", 0)` | the same braces and `[ ]`; `d:get("a", 0)`, `d:keys()`, `d:values()`, `d:remove("a")` |
| `s[1:3]` (end not included) | `s[1:3]` includes position 3, like `range`; `s[:3]`, `s[2:]`, `s[-2:]`, `s[i + 1:j]` |
| `s.split(",")`, `", ".join(items)`, `s.replace(a, b)` | `s:split(",")`, `items:join(", ")`, `s:replace(a, b)` |
| `items.sort()`, `sorted(items, key=f)` | `items:sort()`, `items:sort(f)`, `items:reverse()` |
| `open("f.txt").read()`, `json.dump` | `file.read("f.txt")`, `file.write`, `file.lines`, `file.save("f.json", data)`, `file.load` |
| `try:` / `except Exception as e:` | `try:` / `catch e:` (`e` is the message, as text; any name that isn't Tuff's own, like `err` or `text`) |
| `f"{x:.2f}"`, `f"{n:03}"`, `.format()` | formats by example: `f"{x:0.00}"`, `f"{n:000}"`, `f"{price:money}"`, `f"{name:10}"` (see "Text templates"); `text(x, 2)` also works |
| `range(3)` gives 0, 1, 2 | `range(3)` gives 1, 2, 3, and `range(1, 3)` gives 1, 2, 3: both ends are included |
| `for i in range(len(items)):` | `for item in items:`, or `for i in range(0, len(items) - 1):` |
| `thing.method()` | `thing:method()`, with no spaces around the `:` (only libraries and your own files use a dot: `mtgui.window(...)`, `money.as_money(5)`) |
| `import money` / `from money import as_money` (your own money.py) | `import money` loads your money.tuf; then `money.as_money(5)` and `money.rate` (see "Your own files") |
| `&&`, `\|\|`, `!` | `and`, `or`, `not` |
| `1 < x < 9` | `x > 1 and x < 9` |
| `a, b = 1, 2` | one per line: `a = 1`, then `b = 2` |
| `pass` | `nil` (a line that does nothing) |
| `.5`, `1e3`, `1_000` | `0.5`, `1000` |
| `[0] * 3` | `[0, 0, 0]` |
| default or keyword inputs, `global` | plain inputs only; `global` isn't needed (see rule 2) |
| `print(x, end="")` | an error: build the whole line with `+` first, or add to a shown line with `line:append(...)` |
| `import random`, `import math`, `import time` | nothing to import. Built in: `random(a, b)` (and `random()` for a decimal from 0 to 1), `sqrt`, `floor`, `ceil`, `round`, `abs`, `min`, `max`, `sum`, `average`, `pi`, `sin`/`cos`/`tan` (in degrees), `log`, `now()`, `today()`, `date()`, `time()`. There's no exp, no `random.choice` (use `items[random(0, len(items) - 1)]`) and no shuffle |
| `requests.get(url)`, `json.loads(...)` | `mention tap`, then `res = tap.get(url)` and `res:json` (see "tap") |
| `import pygame` | `mention tgame`, then `game = tgame.window("Title", 800, 600)` (see "tgame") |
| classes, `lambda`, `exit()` | not in Tuff (see "What Tuff can't do") |

These words are keywords and can't be names: `func return if elif else then while for in break continue and or not is true false nil say input flush import mention`.

## Two rules that trip everyone up
**Rule 1: a method's input without brackets takes the rest of the line.** When what follows a method's name could start a value (a name, a number, text, `-`, `[`, `{`, `not`, `true`, `false` or `nil`), that and the rest of the line are the method's input. `items:has x and ready` means `items:has(x and ready)`, and `say slider:value - 1` gives the slider an input of `-1`. Anything else ends the call: `stack:pop + 10` is normal maths. So whenever more of the line follows a method call, put its inputs in brackets, even empty ones:
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

**Rule 2: names are shared (within a file).** A variable made at the top of the program can be changed by any function in the same file. (Each of your own files has a top level of its own: see "Your own files".) Inside a function, `x = 5` (or `for x in ...`) changes the top-level `x` if that already exists when the function runs. Otherwise `x` is a scratch name that only lives inside the function, and disappears when it ends. So:
- give every top-level variable its starting value near the top of the program (`score = 0`), before calling functions that use it;
- give each function's scratch values names that aren't used anywhere else (`total_count`, not `i`, if the top level has an `i`);
- never use a built-in's name for your own variable: `sum = 0` replaces `sum()` everywhere. The built-ins are `print`, `text`, `str`, `number`, `num`, `int`, `len`, `round`, `random`, `wait`, `range`, `clear`, `sqrt`, `abs`, `floor`, `ceil`, `min`, `max`, `sum`, `average`, `pi`, `sin`, `cos`, `tan`, `log`, `now`, `today`, `time`, `date`, `file`, `err` and `all`.

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
  - `random()` gives a decimal from 0 to 1, and `random(0.5)` a decimal from 0 to 0.5.
  - When either end has digits after the point, `random(a, b)` gives a decimal in between: `random(0.5, 2.5)`. Otherwise it gives a whole number, even from a decimal like `12 / 2` or `1.0`: `random(1, 12 / 2)` is a whole number from 1 to 6.
- **Typed numbers:** `input` always gives text, so `"5" + 1` is `"51"` and `"5" * 2` is `"55"`.
  - Turn it into a number first: `number("42")` is 42 and `number("4.5")` is 4.5. Spaces around the number are ignored: `number(" 5 ")` is 5. `num(...)` is a short name for `number(...)`.
  - `int(...)` gives a whole number, dropping the decimals toward zero: `int("42")` is 42, `int(3.7)` and `int("3.7")` are 3, `int(-2.9)` is -2. `str(...)` is the same as `text(...)`.
  - Text that isn't a number gives **`err`** instead of a number: `number("abc")`, `num("abc")` and `int("abc")` are all `err`. Check before using it: `if num(answer) is err:`. An `err` counts as false in an `if`.
  - Using an `err` in maths or a function stops the program and says why: "Can't use + here, because one side is err: number() couldn't turn 'abc' into a number." (`say`, `print` and `text(...)` just show it as `err`.)
  - Anything else that isn't text or a number stops the program: `num(nil)`, `num([5])`, or a text box itself (`num(box)` instead of `num(box:value())`).

## Text
- **Joining:** join with `+`: `"Hi " + name + "!"`. Anything joined with text becomes text: numbers, true/false, nil and even lists.
  - `+` works left to right, so `"Total: " + a + b` gives "Total: 23". Put the maths in brackets: `"Total: " + (a + b)`, or use a text template, which needs none: `f"Total: {a + b}"`.
- **Repeating and letters:**
  - `"ha" * 3` is `"hahaha"`. The number must be whole, and 0 or less gives `""`.
  - Use `len(t)`, `t[0]`, and `t[-1]` for the last letter. `t[0:2]` is the first three letters (see "Text tools and parts").
  - `for letter in t:` goes through it.
  - A letter can't be changed in place; build new text with `+` or `t:replace(...)`.
- **Methods:** `t:upper()`, `t:lower()`, `t:trim()` (removes spaces at both ends) and `t:has("x")` (true or false). They give back new text; `t:trim()` on its own line changes nothing, so write `t = t:trim()`.
- **Escapes:**
  - `"line 1\nline 2"`, `"tab\there"`, `"say \"hi\""` and `"back\\slash"`.
  - Single quotes work too: `'it\'s'`.
  - A backslash before any other letter stays as it is, but `\n` and `\t` still mean a new line and a tab, so write file paths with forward slashes: `"pics/cat.png"`.
- **More tools:** `t:split(",")`, `t:replace("a", "b")`, `items:join(", ")`, parts like `t[1:3]`, `t:starts`, `t:find`, `t:count`, `t:pad_left` and `text(x, 2)` (a number with 2 decimals) are in "Text tools and parts".

## Text templates
```tuff
name = "Sam"
score = 9
say f"{name} has {score + 1} points"    # Sam has 10 points
price = 6.375
say f"Total: {price * 2:money}"         # Total: $12.75
say f"{2.675:0.00} {7:000} {1 / 3:0.0}" # 2.68 007 0.3
say f"[{name:6}] [{score:4}]"           # [Sam   ] [   9]
say f"[{name:>6}] [{score:<4}]"         # [   Sam] [9   ]
say f"{name:upper()} likes {{braces}}"  # SAM likes {braces}
ages = {"sam": 14}
say f'{ages["sam"]}, {ages:get("ann", 0)}, { {"a": 1}["a"] }'   # 14, 0, 1
```
- **What goes in the { }:** any value or sum. It's worked out when the line runs and shown the way `say` shows it (`[1, 2]`, `true`, `nil`), so there's no `+` and no brackets to get wrong. The rest is ordinary text: `\n`, `\t` and `\"` work, and so do single quotes: `f'...'`.
- **Formats** go after a `:` at the end of the { }, written by example:
  - `0.00` rounds to 2 decimals (`0.0` to one, `0` to a whole number), and `000` shows at least 3 digits (7 is `007`; `000.0` does both). They round halves up, the way people do: 2.675 is 2.68 and 2.5 is 3 (`round` would give 2).
  - `money` is dollars and cents with commas: 1234.5 is `$1,234.50`, and -1.5 is `-$1.50`.
  - a width like `12` pads to 12 letters, with text on the left and numbers on the right, so columns line up. `>12` and `<12` choose the side. A longer value isn't cut.
  - `0.00`, `000` and `money` only work on numbers. Turn typed text into a number first: `{num(answer):0.00}`.
- **Format or method:** the format starts at the last `:` that isn't inside brackets or quotes, and only when what follows it is a format. So `{price:money}` and `{x:0.00}` are formats, and `{name:upper()}` and `{d:get("k")}` are method calls.
- **Inside the { }:** quotes can be the template's own (`f"{d:get("k")}"`). A dictionary needs a space after the template's brace, because `{{` shows a brace: `{ {"a": 1}["a"] }`.
- **Braces:** `{{` and `}}` show `{` and `}`.
- A template is one line, like any text, and a `#` can't go in its { }. A mistake inside the braces points at its place in the text: `f"{nmae}"` says "I don't know what 'nmae' is. Did you mean 'name'?", and a `{` without its `}` says so.

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
- **Showing a list:** `say ["a", "b"]` shows `["a", "b"]`, with text items in quotes, and so does a list joined with text. To show the items without quotes, join them: `say items:join(", ")`.
- **More tools:** `items:sort()` sorts a list (see "Sorting"), `items[1:3]` is a new list of positions 1 to 3 (see "Text tools and parts"), and `items:find(x)` gives where `x` is, or -1.
- **Values by name:** for a score per player, use a dictionary, like `scores = {"sam": 3}`, not two lists side by side (see "Dictionaries").

## Functions
- `func name(a, b):` then an indented body. The last line's value is given back automatically. A loop gives back nil, and `say` gives back the line it showed (so a function ending in `say w * h` gives back the text "12", not a number). End with `return value` when the answer matters.
- A function with no inputs can leave out the brackets when it's made (`func greet:`), but calling it always needs them: `greet()`. `greet` on its own line does nothing.
- Call a function with exactly as many inputs as it has. There are no default or keyword inputs.
- `return` only works inside a function.
- **Make every function at the top level of the file**, not inside another function or inside `if`, `for` or `while`. Top-level functions can be used anywhere, even above where they're written. A function made inside a block or another function only exists there, and only once its line has run.
- Inputs belong to the function. Any other name follows rule 2.
- Functions can call themselves up to about 10,000 calls deep (1.4.1; it was about 100). One that never stops ends with "f() called itself too many times.", which try/catch can catch.

## Dictionaries
```tuff
ages = {"sam": 14, "ann": 12}       # keys (text or numbers) and their values
say ages["sam"]                     # 14 (a key that isn't there stops the program: check first)
ages["bob"] = 15                    # adds a key, or changes it
if ages:has("ann"):
    say "Ann is " + ages["ann"]
say ages:get("zed", 0)              # the value, or 0 when the key isn't there
ages:remove("ann")
for name in ages:                   # a loop goes through the keys
    say name + " is " + ages[name]
say ages:keys()                     # ["sam", "bob"]
say ages:values()                   # [14, 15]
say len(ages)                       # 2 (ages:size() is the same)
```
- **Keys** are text or numbers. `true` or `false` as a key is an error.
- **Values** can be anything. A dictionary can hold lists and other dictionaries: `scores = {"red": [3, 4], "blue": [5]}`, then `scores["red"][1]`.
- Written over several lines inside `{ }`, it's one line of code.
- **Files:** save one with `file.save` (see "Files"), and load it back with `file.load`. A file keeps every key as text, so number keys come back as text: save `{1: "gold"}`, and after `file.load` read it with `d["1"]`, not `d[1]`. The error for a missing key says so.
- `:size()`, `:get`, `:has`, `:keys` and `:set("bob", 15)` work like a tap data object's (see "tap"), so a function can take either one.

## Text tools and parts
```tuff
s = "hello world"
say s[0:4]                          # "hello": positions 0 to 4, both included (like range)
say s[6:]                           # "world" (from 6 to the end); s[:4] is from the start
say s[-5:]                          # the last 5
say s[0:len(s) - 2]                 # "hello worl": all but the last letter
say "a,b,c":split(",")              # ["a", "b", "c"]; :split() splits at spaces
say s:replace("world", "Tuff")      # "hello Tuff"
say ["x", "y", "z"]:join(", ")      # "x, y, z"
say s:starts("hell")                # true (also :ends)
say s:find("o")                     # 4, or -1 if it isn't there (lists have :find too)
say s:count("l")                    # 3
say "7":pad_left(3, "0")            # "007" (also :pad_right(10) to line up columns)
say text(3.14159, 2)                # "3.14"
```
- **Parts** include both ends, like `range`. Either end can be left out (`s[:3]`, `s[2:]`) or worked out (`s[i + 1:j]`, `s[0:len(s) - 1]` is all of it).
- Parts work on lists too: `[1, 2, 3, 4, 5][1:3]` is `[2, 3, 4]`. A part is always new text or a new list; the old one doesn't change.
- **Parts or methods:** in an index (the `[ ]` right after a value, like `s[a:b]`), `a:b` is a part when `a` is a number. When `a` holds a list, text or a widget, it's a method call, as it always was: `names[order:pop]` uses the last item of `order` as the position.
- In a list you write (`[word:upper, 1]`), `a:b` is always a method call. After a method's name, `[` starts a list: `pairs:add [word:upper, 1]` adds that list.

## Sorting
```tuff
nums = [5, 3, 9, 1]
nums:sort()                         # [1, 3, 5, 9], in place
nums:reverse()                      # [9, 5, 3, 1]
words = ["banana", "Apple", "cherry"]
words:sort()                        # A to Z, any case
func by_len(w):
    len(w)
words:sort(by_len)                  # sorts by what by_len gives back
```
- `:sort` and `:reverse` change the list itself (and give it back). To keep the old order too, sort a copy: `sorted = nums + []`, then `sorted:sort()`.
- Numbers come before text when a list has both.
- A dictionary can't be sorted, but its keys can: `names = ages:keys()`, then `names:sort()`.

## Files
```tuff
file.write("notes.txt", "first line")   # makes the file, or replaces what's in it
file.add("notes.txt", "another line")   # adds a line at the end
say file.read("notes.txt")              # all of it, as text
for line in file.lines("notes.txt"):    # its lines, as a list
    say line
if file.exists("notes.txt"):
    file.delete("notes.txt")
file.save("save.json", {"name": "Sam", "level": 3})    # any data (text, numbers, lists, dictionaries)
data = file.load("save.json", {})       # back again; {} if there's no file yet
```
- `file` is built in: there's nothing to mention. Files are in the program's own folder unless the path says otherwise.
- `file.save` writes JSON, so a dictionary's number keys come back from `file.load` as text: `data["1"]`, not `data[1]`.
- Tuff Engine's live preview keeps writes in memory: `file.write`, `file.add`, `file.save` and `file.delete` work while it runs (later reads see them), and no file on disk changes. Agents' `tuff_run` does the same (see "Using the tools").

## When something goes wrong: try and catch
```tuff
try:
    data = file.read("settings.txt")
catch problem:                      # problem (or no name) is what went wrong, as text
    say "No settings yet: " + problem
    data = ""
```
- Anything in `try:` that would stop the program (a missing file, a bad web request, dividing by zero...) runs `catch:` instead, and the program goes on.
- The problem's name can't be one of Tuff's own: `catch err:` is an error (`err` is what `num("abc")` gives), and so are `catch text:`, `catch len:`, `catch time:`, `catch file:` and the other built-ins' names. Call it something else, like `catch problem:`.
- `try:` and `catch:` start a block when the `:` ends the line or has a space after it, and so does `catch problem:`. With the `:` glued to a word, `try:say "hi"` is a one-line block too, unless the program gives `try` or `catch` a value (`catch = []`, `for catch in ...`, or a function input called `catch`): then it's a method call. So a variable called `try` or `catch` still works: `catch = []`, then `catch:add(1)`.

## Date, time and maths
```tuff
say now()                           # "14:05:09"
say today()                         # "2026-10-26"
d = date()                          # a dictionary: year, month, day, weekday, hour, minute, second
say "Happy " + d["weekday"]
start = time()                      # seconds since the program started
wait(1.5)
say "That took " + text(time() - start, 1) + " s"
say sin(90)                         # 1: sin, cos and tan take degrees
say log(1000, 10)                   # 3; log(x) is the natural log
say random()                        # a decimal from 0 to 1; random(0.5, 2.5) a decimal in that range
```
- `date()` gives a new dictionary each time, so read it once and use its keys: `d["hour"]`, `d["minute"]`.
- `tan(90)` is an error, because tan has no value there. `log` needs a number above 0.
- `random(6)` is a whole number from 1 to 6, and `random(0.5)` a decimal from 0 to 0.5. `random(a, b)` gives a decimal when either end has digits after the point, like `random(0.5, 2)`, and a whole number otherwise: `random(0, 10 / 2)` is a whole number from 0 to 5, because `10 / 2` (5) has no digits after the point.

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

## Colours, big letters and animations (console programs)
```tuff
say:color("Game over!", "red")                      # a coloured line
say:color("LEVEL UP!", "black", "lime", "bold")     # a 2nd colour is a bar behind the whole line
say:color("RAINBOW!", "rainbow")                    # every letter its own colour (it flows in TuffCode)
print:pen("cyan")                                   # every line after it in this look...
say "this is cyan"
print:pen()                                         # ...until print:pen() with nothing in it
say:ascii("TUFF")                                   # big letters made of blocks
say:ascii("HI", "wide", "gold")                     # fonts: block, wide, small, shadow, led, hash
say:ascii("GAME OVER", "red", "explode")            # plays an animation, then the program goes on
board = say:ascii(0, "small", "gold")
board:rewrite(42)                                   # a big line stays big (and keeps its look)
board:rewrite(43, "drop", "lime")                   # new text with an animation (and a new colour) in place
wait(3)
board:play("explode")                               # an animation on the line where it is, any time later
```
- `say` always shows a **new** line. To animate one that's already shown, use `line:play("explode")` or `line:rewrite("text", "glitch")`. `line:rewrite say:ascii(...)` says a second line, and the checker says so.
- `say:color`, `say:ascii` and `say:pen` are the same as `print:color`, `print:ascii` and `print:pen`.
- After the text come words, in any order:
  - **colours:** the same names as tgame (red, orange, yellow, gold, lime, green, teal, cyan, sky, blue, navy, purple, pink, white, gray, black, brown...) or `"#ff8800"`. The first is the letters', a second is the bar.
  - **styles:** `rainbow`, `bold`, `dim`, `italic`, `underline`.
  - **fonts** (say:ascii only): `block`, `wide`, `small`, `shadow`, `led`, `hash`.
  - **animations:** `fade`, `build`, `explode`, `assemble`, `type`, `glitch`, `drop`, `wave`.
- An animation plays when the line is said: about 1 to 2 seconds, and the program waits for it. `explode` leaves the line empty. Animations work on `say:color` lines too, like `say:color("Loading...", "type")`.
- `print:pen` takes colours and styles, not fonts or animations. It colours everything said after it: `say`, `print`, `input`'s questions and anims' lines.
- **A question in a look (1.4.1):** `name = input:color("Name? ", "green")` asks like `input`, with the question in colours, rainbow or styles (not animations: say the question with `say:color(..., "type")` first for that). It gives back what was typed.
- **Anims in a look (1.4.1):** look words go after an anim's usual inputs: `anims.loading("Pulling info...", "green")`, `anims.bar("Saving", 2, 20, "rainbow")`, `anims.countdown(3, "Go!", "lime", "bold")`.
- Where it shows:
  - **TuffCode's Run window:** all of it.
  - **A real terminal** (and a Build exe console app): ANSI colours, and animations play. Rainbow doesn't flow there.
  - **A file or pipe** (agents' tuff_run): plain text, and an animation shows only how it ends.
- Unknown words are mistakes, with a "did you mean": `say:color("x", "redd")`.

## Your own files (import money)
A program can be split into files. `import money` (or `mention money`) loads money.tuf, from the folder of the file that imports it, or from a folder called `libs` there. Then its functions and top-level values go after a dot, like a library's:
```tuff
# money.tuf
rate = 0.2

# 6.375 -> "$6.38" (the comment above a func is its help when you type money.)
func as_money(x):
    return f"{x:money}"

func with_tax(price):
    return price + price * rate

func set_rate(new_rate):
    rate = new_rate
```
```tuff
# shop.tuf, next to money.tuf
import money
say money.as_money(6.375)       # $6.38
say money.with_tax(10)          # 12
money.set_rate(0.5)
say money.rate                  # 0.5
rate = 1                        # shop.tuf's own rate: money.tuf's doesn't change
say money.with_tax(10)          # 15
```
- **Each file has its own top level.** Rule 2 works inside each file: a function in money.tuf uses and changes money.tuf's names, never shop.tuf's, so the same name in two files never clashes.
- **What other files see:** a file's functions, its top-level values and what it imports. The scratch names inside its functions only live there.
- **Changing a value:** `money.rate = 2` is an error. Change it with a function in money.tuf, like `set_rate` above.
- **Once:** a file's top-level code (like a `say` that isn't in a function) runs the first time it's imported. Importing it again, from any file, gives the same one.
- **Where:** the importing file's folder, then the `libs` folder there. A file in libs imports the other files in libs. The name is spelled exactly as the file is, capitals too, and must be a name Tuff can use (letters, numbers and _).
- **Libraries win:** `import tgame` is always Tuff's tgame, even with a tgame.tuf in the folder (`tuff_check` says so), so give your files other names. A built-in's name can't be one either: `import random` says random() is built in.
- **Two files can't import each other.** If shop.tuf imports money.tuf and money.tuf imports shop.tuf, neither can finish loading, and the error names them. Put what both need in a third file.
- **Mistakes in money.tuf** are reported there, with its own line: "Tuff error in money.tuf on line 4: ...", and in TuffCode that line jumps to money.tuf.
- **Files:** `file.read("prices.txt")` in money.tuf reads from the program's folder, like everywhere else.
- `tuff_check` on shop.tuf knows what money.tuf has: `money.as_mony` gives "money.tuf doesn't have 'as_mony'. Did you mean 'as_money'?", and wrong input counts are caught. Each file is checked on its own, so check money.tuf too. Build exe takes the files a program imports along with it.

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
- **tdraw** draws with a pen (a turtle), like Python's turtle: lines, shapes, fills, text and rainbow pens. See below.

### tdraw
```tuff
mention tdraw
tdraw.background("navy")    # optional: the window's colour (also tdraw.title, tdraw.size(w, h), tdraw.clear())
pen = tdraw.pen()           # opens the drawing window; the pen starts at 0, 0 (the middle), facing right
pen:speed "instant"         # "slow", "normal", "fast" (the start) or "instant" (no animation), or 1-10
pen:color "rainbow"         # a colour name, "#rrggbb", or "rainbow" (changes as it moves)
pen:width(3)
for i in range(1, 100):
    pen:forward(i * 3)      # moves and draws; pen:back(n)
    pen:right(59)           # turns, in degrees; pen:left(n). 90 if left out
pen:jump(150, 200)          # moves without drawing; pen:go(x, y) draws to there
pen:color("pink", "gold")   # line colour, then fill colour
pen:star(100, "gold")       # a colour after the size fills it
pen:circle(40)              # also pen:square(80), pen:triangle(80), pen:polygon(6, 40), pen:dot(20, "red")
pen:write("Hello", 24)
pen:hide()                  # hides the turtle; pen:show() brings it back

func clicked(x, y):
    pen:go(x, y)
tdraw.on_click(clicked)     # runs clicked(x, y) on each click
```
- x goes right and y goes **up** (unlike tgame, where y goes down). The window is 640 by 640, so ±320 reaches the edges.
- More pen methods: `pen:up()`, `pen:down()`, `pen:home()`, `pen:face(degrees)` (0 right, 90 up), `pen:x()`, `pen:y()`.
- The window stays open after the program ends, until it's closed. `wait()` keeps it drawing while the program waits.
- Several pens can draw at once: call `tdraw.pen()` again.
- For big drawings, use `pen:speed "instant"`, or they take a while to animate.

### tap
```tuff
mention tap

res = tap.get("https://api.github.com/users/octocat")
if res:ok:
    user = res:json                 # a JSON object comes back as a dictionary
    say user["name"] + " has " + user["public_repos"] + " public repos"
else:
    say "Error " + res:status

note = {"title": "Hello", "tags": ["a", "b"]}   # a dictionary is sent as JSON
sent = tap.post("https://httpbin.org/post", note)
say sent:status
```
- **Requests:** `tap.get(url)`, `tap.post(url, body)`, `tap.put(url, body)` and `tap.delete(url)`. Text is sent as plain text, and a dictionary or a list as JSON. Headers go last, as a dictionary: `tap.get(url, {"Accept": "text/csv"})`.
- **A response:** `res:status` (like 200 or 404), `res:ok` (true for 200 to 299), `res:text`, `res:json` and `res:header("Content-Type")` (nil if it isn't there).
- **Errors:** a 404 or 500 doesn't stop the program, so check `res:ok`. No internet, a bad address, no answer within 15 seconds, and `res:json` on something that isn't JSON do stop it with an error.
- **JSON:** `res:json` gives a dictionary for `{...}`, a list for `[...]`, or text, a number, true/false or nil.
- **What :json gives is an ordinary dictionary** (see "Dictionaries"): `user["name"]`, `user:get("name")` (nil if it's missing), `user:has("name")`, `user:keys()`, `len(user)`, and `user["name"] = value`. Objects inside are dictionaries too: `user["address"]["city"]`. `for name in user:` goes through its names. JSON's names are always text, so a name like `"1"` is read with `user["1"]`.
- **tap.data()** is an empty dictionary, the same as `{}`. Older programs used it with `:set` to build what they send, and they still work.
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
- **Objects** have the sprites' methods with a z added (`:move(dx, dy, dz)`, `:glide(x, y, z, seconds)`...), plus `:shake()`, `:fall()`, `:fallen()`, `:regrow(seconds)`, `:grow()`, `:swing()`, `:glow "gold"`, `:label "Oak"` (text above it) and `:solid false` (the player walks through it). A sign's label is written on its board instead, on both sides, as big as fits (long words wrap): `sign:label("Shop")`.
- **People's looks (3D):** a person (`world:spawn("person", x, y, z)`), a ragdoll and the player in third person can be dressed: `npc:shirt("red")`, `npc:pants("black")`, `npc:skin("tan")` (pale, light, tan, medium, brown, dark, or any colour), `npc:hair("curly", "blonde")` (a style: short, swoop, bob, ponytail, buns, curly or spiky, and a colour: black, brown, blonde, ginger, grey or any colour; one or both), `npc:shoes("white")` and `npc:sleeves("short")` (or `"long"`). They can change while the game runs. Left out, tgame picks a look.
- **The player:** `"first person"` or `"third person"`. Solid things block the way and can be stood on. `player:walk_speed 6`, `:jump_height 2`, `:hold "sword"` (axe, pickaxe, sword, torch or hammer), and `game:looking_at()` is the object in the middle of the view, or nil.
- **Without a player:** `game:camera_at(x, y, z)` with `game:look_at(thing)`, or `game:follow(thing)` (behind it), or `game:orbit(thing)` (drag to turn around it).
- **Testing a game:** add `game:after(2, selftest)`, call your functions in `func selftest():`, `say` what you find, and end it with `game:close()`.

#### Animated pictures (sprite sheets)
A sprite sheet is one picture with every frame of a character in it, in a grid. Cut it into frames, name some of them as animations, and play them: the game window steps through the frames by itself.
```tuff
mention tgame

game = tgame.window("Hero", 600, 400)
hero = game:image("hero_sheet.png", 300, 200, 64)   # one frame will be 64 wide
hero:frames(4, 2)                                   # 4 across, 2 down: frames 1 to 8
hero:animation("walk", [1, 2, 3, 4], 10)            # a name, its frames, how many a second
hero:animation("jump", [5, 6, 7, 8], 12)
jumping = false

func landed(who, name):                             # "jump" has shown its last frame
    jumping = false

hero:on_done(landed)

while game:open():
    dt = game:frame()
    moving = false
    if game:held("left"):
        hero:move(-200 * dt, 0)
        moving = true
    if game:held("right"):
        hero:move(200 * dt, 0)
        moving = true
    if game:pressed("space") and not jumping:
        jumping = true
        hero:play("jump", false)                    # once: it stays on frame 8, then landed runs
    if not jumping:
        if moving:
            hero:play("walk")                       # already playing: it carries on
        else:
            hero:frame(1)                           # standing still
```
- **Frames:** `hero:frames(4)` cuts a picture into 4 frames side by side, and `hero:frames(4, 2)` into 4 across and 2 down. Every frame is the same size. They're numbered from 1, left to right, then the next row down. After `:frames` the sprite is one frame big: as wide as the width `game:image` was given (or one frame's own size without one), and `:touches` uses that size.
- **One frame:** `hero:frame(3)` shows frame 3 and stops any animation. `hero:frame()` gives the frame it shows now.
- **Animations:** `hero:animation("walk", [1, 2, 3, 4], 10)` names frames in the order they show, and how many show a second (10 if you leave it out). Any frames work, in any order: `[1, 2, 3, 2]`, or `range(5, 8)`. Make the animations after `:frames`.
- **Playing:** `hero:play("walk")` plays again and again. Playing the animation that's already playing carries on, so it can go in every frame of a loop. `hero:play("jump", false)` plays once and stays on its last frame, then `hero:on_done(landed)` runs `landed(sprite, name)` (a function can leave out the inputs it doesn't need: `func landed():` works too). `hero:stop()` stops on the frame it shows.
- Animations go by the game's time: they hold still while the game is paused and slow down in `game:slow_mo`. Pictures on the HUD (`hud:image`) animate the same way, in a 2D game or a 3D world. 3D worlds have no flat pictures in the world itself, so sprite sheets are for 2D games and HUDs.
- **Sprite Studio** (in TuffCode's sidebar) draws the frames and saves them with a sprite sheet, and its "Use in code" writes these lines for you.

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

#### Saving
`game:save(name, value)` keeps a value on the computer, so the game remembers it the next time it runs, even after it was closed: a high score between games, the level someone reached (their progress), their settings. It works the same in 2D and 3D.
```tuff
mention tgame

game = tgame.window("Star Catcher", 600, 400)
best = game:load("best", 0)                   # what an earlier game saved, or 0 the first time
score = 0
label = game:text("Score: 0", 300, 24)
best_label = game:text("Best: " + best, 300, 54, 18, "gold")
basket = game:box(300, 370, 80, 20, "wood")
basket:on_edge "stop"
star = game:circle(300, 0, 12, "yellow")

func step(dt):
    if game:held("left"):
        basket:move(-400 * dt, 0)
    if game:held("right"):
        basket:move(400 * dt, 0)
    star:move(0, 220 * dt)
    if star:touches(basket):
        score += 1
        label:set "Score: " + score
        star:move_to(random(20, 580), 0)
    elif star:y() > 400:                      # missed it: game over
        if score > best:                      # a new high score: keep it for next time
            best = score
            game:save("best", best)
            best_label:set "Best: " + best
        star:move_to(random(20, 580), 0)
        game:game_over("Score: " + score, again)

func again():                                 # space after game over
    score = 0
    label:set "Score: 0"

func reset_best(key):                         # R forgets the high score
    game:forget("best")
    best = 0
    best_label:set "Best: 0"

game:every_frame step
game:on_key("r", reset_best)
```
- **Saving:** `game:save("best", score)` saves right away (there's nothing else to do before the game closes). It keeps numbers, text, true/false, nil, lists and tables, inside each other too: `game:save("unlocked", ["forest", "cave"])`. A table is a dictionary, like `game:save("stats", {"level": 3, "coins": 20})`, or a tap data object. Saving a function, a sprite or an object is an error: save the numbers you need instead, like `game:save("x", player:x())`.
- **Loading:** `game:load("best", 0)` gives back what was saved under that name, or the second input when nothing was saved yet (nil if you leave it out). Lists come back as lists, and tables as dictionaries (with `:get`, `:has`, `:keys`, `:set` and `:size`, as before): `stats = game:load("stats")`, then `stats["level"]` or `stats:get("level")`. Like `file.save`, a save keeps keys as text, so a number key comes back as text. `game:saved("best")` is true when something is saved under that name.
- **Forgetting:** `game:forget("best")` forgets one save, and `game:forget()` forgets every save the game has (a "reset progress" button).
- **Where saves go:** one file per game, named after the title in `tgame.window("Star Catcher")` (changing it later with `game:title` doesn't move the saves), in a TuffSaves folder in the user's own data folder. The same game run from TuffCode or built with Build exe shares its saves, and games with other titles never see them, so give each game its own title. Tuff Engine's preview never saves: there `game:load` always gives the default.
#### Splash screens, main menus and the mouse
Splash screens play when the game starts, then a main menu waits for Play. In 3D, the mouse is free on menus and screens (to click buttons and read notes) and locked for looking around in the game.
```tuff
mention tgame

world = tgame.world("Forest Notes")
world:sky "sunset"
world:island(60)
player = world:player("first person")
sign = world:spawn("sign", 0, 0, -6)
sign:label "Press E to read"
for i in range(1, 10):
    world:spawn("pine")

world:splash("logo.png", 3)               # a picture next to your .tuf file, for 3 seconds
world:splash("Pip Studio presents")       # big text, for 2 seconds
world:splash()                            # "Made with Tuff"

menu = world:main_menu("Forest Notes")    # after the splashes: the game waits and the mouse is free
menu:text "Find the note by the old sign."
menu:button("Play", play)
menu:button("Quit", quit, "secondary")

note = world:screen("A note")             # a screen frees the mouse while it shows
note:text "Meet me by the old hut at sunset."
note:button("Close", close_note)
note:hide()

func play():
    menu:hide()                           # the game starts, and the mouse locks for looking around

func quit():
    world:close()

func close_note():
    note:hide()                           # the mouse locks again, as it was before the note

func key(name):
    if name is "e" and player:distance(sign) < 4:
        note:show()
    if name is "m":
        menu:show()                       # back to the main menu, with the mouse free

world:on_key("any", key)

while world:open():
    world:frame()
```
- **Splash screens:** `game:splash("logo.png", 3)` shows a picture from your project folder (.png, .jpg or .gif, fitted on black), and `game:splash("Pip Studio presents")` shows big text, each for its seconds (2 if you leave them out). Several play in order when the game starts, before the main menu or start screen. Each fades in and out, and a click or any key skips to the next. `game:splash()` shows "Made with Tuff". While they play the game is paused and the mouse is free.
- **Main menu:** `menu = game:main_menu("My Game")` is a screen styled as a game's main menu: a big title, and what you add under it (`menu:button`, `menu:text`, `menu:image`, rows, cards...) in a column with wide buttons. It shows when the game starts (after the splash screens), with the game paused and the mouse free: its clicks never reach the game or lock the mouse. `menu:hide()` starts the game; in a 3D world with a player, the click that hid it also locks the mouse for looking around. `menu:show()` brings it back, like from a pause menu. Other screens (Settings, How to play) show over it.
- **The mouse (3D):** with a player, a click on the game locks the mouse for looking around, and Escape frees it. Every screen, the main menu and the splash screens free it while they show, and lock it again when the last one hides if it was locked before. Panels don't: while it's locked, a click is the game's, even over a panel's button.
- **Your own control:** `world:unlock_mouse()` frees it and keeps it free until `world:lock_mouse()` or a click on the game. `world:lock_mouse()` locks it (right away while the game's window is in front, or else on the next click on the game). `world:mouse_locked()` is true or false. `world:auto_lock(false)` stops clicks on the game from locking it, so only your code does; `world:auto_lock(true)` turns it back on.
- `game:start_screen` still works as before, and splash screens play before it too.

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
`thing:physics()` makes a thing real: it falls, bounces, tumbles, knocks into other things and gets pushed. It works on everything in a 3D world (boxes, spheres, cylinders, cones, planes and `spawn` models, people and signs too) and in 2D (boxes, circles, lines, text and pictures). Things weigh what they are, so heavy things are hard to push. A game that never uses physics works exactly as before.
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
    crate:weight(20)                      # kg: light enough to knock over
    crate:on_hit(bumped)
ball = world:sphere(0, 1, 2, 1, "red"):physics()     # physics() gives back the thing
ball:weight(80)                           # a heavy ball
ball:bounce(0.4)                          # 0 doesn't bounce, 1 bounces right back up
dummy = world:ragdoll(4, 0, -8, "blue")   # a person made of parts that flops when it's hit
car = world:car(-5, 1, 6, "orange")
player = world:player("third person")
player:move_to(-7.5, 0, 6)                # by the car: F gets in, and F again gets out

func bumped(other, strength):             # something hit a crate: what, and how hard
    if strength > 2:
        hits += 1
        label:set "Hits: " + hits

func kick(key):                           # K rolls the ball at the tower
    ball:push(0, 1, -15)                  # it weighs 80 kg, so it goes a bit slower than that

func boom(key):                           # B blows everything away from the tower
    world:explode(0, 0, -10, 15, 8)

world:on_key("k", kick)
world:on_key("b", boom)

while world:open():
    world:frame()
```
- **Kinds of physics:** `thing:physics()` (or `"dynamic"`) falls and can be pushed, `thing:physics("static")` stays where it is but things bump into it and land on it (a floor, a wall), `"kinematic"` is moved only by your code but pushes other things (and carries the player standing on it, like a lift), and `"off"` turns it off (`"on"` and `"falls"` mean dynamic too, `"fixed"` and `"solid"` static, `"none"` off). It gives back the thing, so it chains: `ball = world:sphere(0, 5, 0, 1, "red"):physics()`.
- **What it's made of:** `:weight(25)` is how heavy it is in kg (`:mass` is the same). By default things weigh what they are: a crate 25 kg, a chest 40, a person 70, a rock 300, a tree 400, a house 6000, and the shapes 50 kg a cubic metre (a 1 m box is 50 kg); `:scale` makes them heavier or lighter. `:weight()` gives it back. `:bounce(0.6)` is how bouncy it is from 0 to 1, and `:friction(0.4)` how grippy it is (0 is slippery, like ice).
- **Moving it:** `:push(x, y, z)` kicks it: the numbers are the speed it gives a 50 kg thing (a 1 m box), so a heavier thing moves less and a lighter one flies off faster. (Before 1.3.0 a 1 m box weighed 1 kg: a game that sets `:mass` numbers from then needs about 50 times them now.) `:spin(x, y, z)` sets it spinning, and `:velocity(x, y, z)` sets how fast it's moving each way (whatever it weighs). `:velocity()` gives back `[x, y, z]`. `:sleep()` stops it until something wakes it, and `:wake()` wakes it.
- **Hits:** `crate:on_hit(bumped)` runs `func bumped(other, strength):` when something hits it: `other` is what hit it and `strength` how hard (under 1 is a gentle touch; heavy and fast things hit harder). It works on the player too. `:touches`, `:x()`, `:y()`, `:spot()` always give where a physics thing really is.
- **The world:** with physics on, the land, the ground, the island, the buildings and every other solid thing stay put, and physics things land on them (water isn't solid). `world:gravity(-9.8)` is how strong gravity is (-9.8 is like on Earth and the default, 0 floats like in space). `world:explode(x, y, z, strength, radius)` pushes every physics thing near a spot away from it, less the further away it is.
- **The player** walks into physics things and shoves them as hard as a person can (it weighs 70 kg): a crate slides away, a 300 kg rock doesn't budge. `player:weight(90)` makes it shove harder. It can stand on physics things and gets knocked by them. Its keys work as before. With `player:can_grab()` it can lift things up to 100 kg ("Too heavy to lift" over that), and a heavy thing doesn't fly as far when it's thrown.
- **A car:** `car = world:car(x, y, z, "red")` is a car with four wheels, springy suspension and steering. It weighs 1200 kg, so it shoves crates and ragdolls out of its way. The player walks up to it and presses **F** to get in ("F: Get in" shows): the arrow keys or WASD drive it and the camera follows. F again gets out, beside the driver's door, and the car stays parked. `car:drive()` starts the game with the player in it (with no player, the keys drive it from the start), and `car:drive(false)` gets out. `car:on_enter(got_in)` and `car:on_exit(got_out)` run when the player gets in and out (with F or `car:drive`), and `car:driven()` and `player:in_car()` say whether it's in. A game that uses F itself (`world:on_key("f", ...)`) keeps it: then F doesn't get in cars, so use `car:drive()` there. `car:engine(2)` gives it more power (1 is normal), `car:speed()` is how fast it's going in km/h, and `car:flip()` puts it back on its wheels after a crash.
- **A ragdoll:** `dummy = world:ragdoll(x, y, z, "blue")` is a person made of jointed parts (a head, a body, arms and legs) that flops over when it's hit or pushed: `dummy:push(0, 4, -6)`. It weighs 70 kg and dresses like a person (`dummy:shirt("red")`, `dummy:hair("ponytail")`).
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

#### Game kit
Ready-made pieces that make a game feel finished: **effects** (slow motion, a shaking camera, floating text, rain and snow, day and night), the **HUD** (health bars, a countdown, an arrow to a thing, a minimap), **interaction** (picking things up, people who talk, doors and keys) and **level pieces** (jump pads, boost pads, moving platforms). Each is one line, and each works without physics turned on.
```tuff
mention tgame

world = tgame.world("Treasure Hunt")
world:sky "day"
land = world:terrain(120)
land:hill(20, -10, 18, 5)
world:weather("rain", 0.5)                # "rain", "snow" or "none", then how strong (0 to 2)
world:day_cycle(180)                      # morning to night and back every 3 minutes
player = world:player("third person")
player:can_grab()                         # E picks up the thing you look at, a click throws it
map = world:minimap()                     # a round map in the top right

guide = world:spawn("person", 4, 0, -4)
guide:say("My treasure is behind that door. Find the key!")
guide:on_talk(talk)                       # walk up to them and press E
key = world:spawn("key", -10, 0, -14)     # walking into it picks it up
map:mark(key, "gold")
arrow = world:arrow_to(key)               # an arrow at the screen's edge, with how far it is
door = world:door(0, 0, -20, "wood")      # it swings open when you walk into it
door:needs(key)                           # locked until you have the key
chest = world:spawn("chest", 0, 0, -26)

guard = world:spawn("person", -6, 0, -8)
guard:health_bar(3)                       # a bar over it, full at 3
guard:clicked hit
guard:on_death(beaten)

pad = world:jump_pad(12, 0, -4, 14)       # launches you up, 14 m/s
boost = world:boost_pad(-4, 0, 6, 20)     # shoots you forward the way it faces: on towards the door
lift = world:box(-16, 0.5, -4, [4, 0.4, 4], "stone")
lift:path([[-16, 0.5, -4], [-16, 5, -4], [-26, 5, -4]], 2)   # there and back at 2 m/s, and you ride it
crate = world:box(2, 0, 2, 1, "wood"):physics()             # something to grab and throw

coins = world:group()
for spot in [[6, 0, 6], [-8, 0, 2], [-26, 5, -4]]:
    coins:add(world:spawn("coin", spot))
clock = world:countdown(90, times_up)     # top right, red under 10 s
found = false

func talk():
    guide:say("The key is by the big rock. Watch out for the guard!", 5)

func hit(thing):
    if thing:distance(player) < 4:
        guard:hurt(1)                     # the bar shrinks and flashes
        world:pop_text("-1", guard:spot(), "red")

func beaten():
    world:pop_text("Beaten!", guard:spot(), "gold")
    guard:hide()

func times_up():
    world:pause("Out of time!")

func step(dt):
    got = player:touches(coins)
    if got:
        world:pop_text("+5 s", got:spot(), "gold")
        coins:remove(got)
        got:remove()
        clock:add(5)
    if not found and player:touches(chest):
        found = true
        clock:stop()
        world:slow_mo(0.3, 2)             # everything at 30% for 2 seconds
        world:shake(0.6)
        world:pop_text("Treasure!", chest:spot(), "gold", 60)   # 60 pixels tall
        world:arrow_to(chest)

world:every_frame step

while world:open():
    world:frame()
```
- **Effects:** `world:slow_mo(0.3, 2)` runs everything (the game clock, things that move, physics, animation) at 30% for 2 seconds, then eases back (the speed is from 0.05 to 1), and `world:slow_mo(1)` ends it. `world:shake(0.5)` shakes the camera (0 to 2) for a moment, `world:shake(1, 1.5)` for 1.5 seconds. `world:pop_text("+10", x, y, z)` floats text up from a spot (a spot works too: `coin:spot()`), then fades; a color and a size come after: `world:pop_text("+10", coin:spot(), "gold", 40)`. The size is how tall the text is on screen, **in pixels** (34 if you leave it out, 32 in 2D), so 2 is a tiny dash. 2D games have `game:slow_mo`, `game:shake` and `game:pop_text("+10", x, y, "gold", 30)` too.
- **Weather and time (3D):** `world:weather("rain")` (falling streaks, a darker sky, thicker fog, wet ground), `"snow"` (drifting flakes, a paler sky) or `"none"`, then how strong it is from 0 to 2: `world:weather("snow", 1.5)`. `world:day_cycle(120)` goes morning, noon, sunset, night (with stars), dawn and back over 120 seconds (2 or more), and the sky, the sun, the light and the fog follow; `world:day_cycle(0)` stops it where it is, and `world:time_of_day(18)` jumps to 6 pm (0 to 24).
- **Health bars:** `enemy:health_bar(100)` puts a bar over a sprite or an object (not a door; in 3D it faces the camera), full at 100. `enemy:hurt(10)` takes some off (it shrinks and flashes), `enemy:heal(5)` gives some back, `enemy:health()` is how much is left, and `enemy:on_death(gone)` runs `func gone():` once, when it reaches 0.
- **A countdown:** `clock = game:countdown(60, times_up)` shows a timer in the top right that ticks down, turns red under 10 seconds and runs `func times_up():` at 0. `clock:add(5)` adds seconds, `clock:stop()` stops it, and `clock:left()` is how many seconds are left. It works in 2D and 3D, pauses with the game, and keeps going through `game:clear()`. A panel in the top right stays there, and the countdown (and a minimap in that corner) go under it.
- **Finding things (3D):** `arrow = world:arrow_to(chest)` is an arrow at the edge of the screen that points at a thing, with how far it is ("24 m"); when the thing is in view it sits over it. `arrow:hide()`, `arrow:show()`, and `world:arrow_to(other)` points it at something else. `map = world:minimap()` is a round map of the land and its water with the player as an arrow; its size (180 pixels, from 60 to 600) and a corner are optional: `world:minimap(200, "top left")` (`"top right"`, `"top left"`, `"bottom left"` or `"bottom right"`). `map:mark(coin, "gold")` adds a dot that follows a thing, `map:unmark(coin)` takes it off, and `map:zoom(2)` shows twice as close. While the player drives a car, the arrow and the map measure from the car.
- **Picking things up (3D):** `player:can_grab()` lets E pick up the physics thing the player is looking at (within 3 m): it floats in front of them, a click throws it (not the click that locks the mouse again after Escape) and E again drops it. `player:holding()` is the thing (or nil), and `player:can_grab(false)` turns it off.
- **People who talk (3D):** `npc = world:spawn("person", 4, 0, 2)`, then `npc:say("Hi!")` shows a speech bubble over it for 4 seconds (a second input is how many, 0 keeps it). `npc:on_talk(talk)` runs `func talk():` when the player is within 3 m and presses E ("E: Talk" shows).
- **Doors and keys (3D):** `door = world:door(x, y, z)` is a door in a frame (a color is optional: `"wood"`) that swings open when the player walks into it or presses E near it, and closes after a while. `door:open()`, `door:close()` and `door:turn(90)`. `key = world:spawn("key", 3, 0, 3)` is a small gold key that spins; `door:needs(key)` locks the door until the player has walked into the key (it disappears), and a locked door shows "Locked!" and the key's name. `door:lock()` and `door:unlock()` too. E talks to the nearest person first, then opens a door, then grabs. An E that hides a screen (a note your `on_key` function closes) only hides it.
- **Level pieces (3D):** `world:jump_pad(x, y, z, 15)` is a glowing pad that launches the player (and physics things) up at 15 m/s. `boost = world:boost_pad(x, y, z, 20)` shoots the player forward the way it faces, and `boost:turn(90)` aims it. Any object (not a car or a ragdoll: they always use physics) moves along spots with `lift:path([[0, 2, 0], [10, 2, 0], [10, 6, 0]], 3)`: there and back at 3 m/s, or round and round with `"loop"` as a third input. The player rides it (and physics things do too), and `lift:path()` stops it.
- **Tips:** y is the height above the land here too, and a paused game pauses all of these. Make a door, a pad, a key or a person with one top-level line so Tuff Engine can show it, and keep `:say` and `:path` lines right after the thing.

#### Multiplayer
Games on the same network (the same Wi-Fi, or cables to the same router) can play together. One game **hosts** a room, the others **join** it. In a 3D world, everyone else's player shows up in your world as a person with their name over their head, walking where they walk. Messages and shared values work in 2D and 3D.
```tuff
mention tgame

world = tgame.world("Tag")
world:sky "day"
world:ground "grass"
me = world:player("third person")
me:move_to(random(-8, 8), 0, random(-8, 8))   # everyone starts somewhere else
label = world:hud():text("", 480, 570, 22, "white")
last_tag = 0

menu = world:main_menu("Tag")
menu:button("Host a game", host_game)
menu:button("Join a game", join_game, "secondary")

func host_game():
    world:host("Tag")                         # a room the others on this network can find
    world:share("it", world:my_name())        # the host starts as "it" (everyone sees shared values)
    menu:hide()

func join_game():
    world:join()                              # finds a room on this network and goes in
    menu:hide()

func got(message, value, sender):             # a message from another player
    if message == "tag" and value == world:my_name():
        last_tag = world:time()               # just tagged: no tagging back for 2 seconds
        world:shake(0.6)

func left(name):                              # a player left: if they were "it", the host is now
    if world:hosting() and world:shared("it", "") == name:
        world:share("it", world:my_name())

func step(dt):
    it = world:shared("it", "")
    label:set "It: " + it
    if it == world:my_name() and world:time() - last_tag > 2:
        for p in world:others():              # the other players' people
            if me:distance(p) < 1.5:
                last_tag = world:time()
                world:send("tag", p:get("name"))
                world:share("it", p:get("name"))

world:on_message(got)
world:on_leave(left)
world:every_frame step
```
- **Hosting:** `game:host("Tag")` makes a room called Tag (`game:host()` names it after the game's title). `game:hosting()` is true from the next line. The first time a computer hosts, Windows may ask whether TuffCode can use the network: choose **Allow** (private networks are enough). The top of the window says "Hosting "Tag" on 192.168.1.20" for a few seconds: that's the address others can join by.
- **Joining:** `game:join()` looks for a room on the network and goes in (one for the same game first). `game:join("Tag")` goes in the room called Tag, and `game:join("192.168.1.20")` goes straight to that computer (for networks that hide rooms, like some school Wi-Fi). Joining takes a moment: the game keeps running meanwhile ("Looking for a game to join..." shows at the top), and `game:connected()` is true once it's in. A game hosts or joins, not both: `game:leave()` leaves the room first (a host leaving closes the room for everyone).
- **Players:** `game:players()` is a list of everyone's names, yours too, the host's first. Names are "Player 1" (the host), "Player 2" and so on, or what each game chose with `game:my_name("Sam")` (two Sams become Sam and Sam 2). `game:my_name()` gives your own. `game:on_join(fn)` runs `func fn(name):` for each other player who comes in (and, when you join, for each player already there), and `game:on_leave(fn)` runs `func fn(name):` when one goes, or when the host leaves (then for everyone).
- **Messages:** `game:send("score", 10)` sends a message to every other player, with a value if you like (numbers, text, true/false, lists and tables, like `game:send("at", [me:x(), me:y()])`). `game:on_message(fn)` runs `func fn(message, value, sender):` for each one that arrives: the message, its value (nil if none) and the sender's name. Messages sent before the game is in a room wait until it's in; in no room at all, they go nowhere.
- **Shared values:** `game:share("coins", 5)` sets a value every player sees, and `game:shared("coins", 0)` reads it (the second input until someone shares it). The host keeps them, so a player who joins later gets them all. Values shared before joining only fill in what the room doesn't have yet: the room's own values win.
- **Other players (3D):** each other player's player is a person in your world, in their own shirt color (the host's blue, then red, green, orange...), with their name over its head. It walks where they walk and hides when they hide. `world:others()` is a list of them, as objects: `me:distance(p)`, `me:touches(p)`, `p:get("name")` (their name), `p:animate("wave")`. They don't block the way (`p:solid(true)` if they should), and `game:clear()` leaves them.
- **2D:** there's no player in 2D, so nobody shows up by themselves: send where your sprite is (`game:send("at", [me:x(), me:y()])` every frame) and move a sprite for them in `on_message`.
- **Trying it alone:** in TuffCode, a file that uses `:host(` or `:join(` gets a **Run a second player** button (two people) right after Run, and in the run options menu. It runs another copy of the same game beside the first, so host in one window and join in the other (with a Host/Join menu like the Tag game's, click Host in one and Join in the other). If the game isn't running yet, it starts both. The Run panel puts a P1 or P2 chip on each line, so you can tell which copy said what. The button stops only the second player; Stop, a new Run and closing TuffCode end both.
- **Tips:** try it with two computers on the same network: run the game in TuffCode on each, then host on one and join on the other. On one computer, use Run a second player, or run a copy made with Build exe beside it (games built with Build exe host and join too). Tuff Engine's preview never hosts or joins.

#### Games Tuff Engine can edit
TuffCode's Tuff Engine tab (`Ctrl+Shift+G`) builds tgame games by clicking and dragging, and writes everything as normal Tuff code. It can only show and edit simple top-level lines, so when you change a game someone is building in it:
- Make each new thing with **one top-level line and plain numbers**, like `coin = game:circle(200, 200, 14, "gold")` or `tree = game:spawn("tree", -5, 0, -10)`. Things made in a loop, a function or a chained line (`game:spawn("sign"):label "Hi"`) still work, but show as "Made by your code" and can't be dragged.
- Put new lines **above** any `while game:open():` loop.
- Make the land with one line (`land = game:terrain(200)`) and change it with **one top-level line per edit**, like `land:hill(20, -10, 30, 8)`, so Tuff Engine can list them under the land, change their numbers and remove them.
- Give a thing its physics with **one top-level line each, right after it**, like `crate:physics()`, `crate:weight(25)`, `crate:bounce(0.6)` or `crate:friction(0.4)`, so its Physics section in Tuff Engine shows and changes them. A person's look works the same way (`npc:shirt("red")` right after it) for its Clothes and hair section.
- Make a door, a key, a jump pad, a boost pad or a talking person with **one top-level line**, like `door = game:door(0, 0, -5)`, and put its `door:needs(key)`, `npc:say("Hi!")` or `lift:path(...)` line **right after it**, so Tuff Engine's 3D Add tab and its Objects list show them. Write a path's spots as numbers, like `lift:path([[0, 1, -6], [8, 1, -6]], 3)`, so moving the platform in Tuff Engine moves its spots with it.
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

# Money: 6.375 -> "$6.38", 18 -> "$18.00", -1.5 -> "-$1.50" (f"{x:money}" does it too, with commas)
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

## How fast Tuff is
- Since 1.5.0, Tuff turns each part of a program into quick code once, before it runs it, instead of working out what every line means each time it runs. Loops are 3 to 6 times faster than in 1.4: a million steps take about half a second.
- Everything else is the same: the answers, the error messages, and the line and column each error points at.
- A function can call itself about 10,000 calls deep (see "Functions").
- To build a long text in a loop, add the pieces to a list and join them at the end (`parts:add(word)`, then `parts:join(" ")`). Adding to the text itself copies all of it every time.
- When you run Tuff in a terminal, `TUFF_SLOW=1` runs a program with the old way instead, for 1.5 only. Use it to check whether something that changed is the new speed-up's fault.
```tuff
# A million steps, and how long they took
start = time()
total = 0
for i in range(1, 1000000):
    total += i % 7
say total
say "That took " + round(time() - start, 2) + " seconds"
```

## Making a good program
- Keep the program's state in a few top-level variables (`score`, `tasks`), each set near the top, and write one small function per action.
- A `refresh()` function that rewrites every label from that state keeps the screen right. Call it after each change.
- Check what people type, and show a friendly message instead of letting the program stop with an error.
- Use clear names, keep functions short, and follow the two rules above.
- When a program grows to a few hundred lines, move each group of functions that belong together into a file of its own, like money.tuf (see "Your own files").

## Using the tools
- **`tuff_check`** checks code without running it. Run it on every file you write or change. It catches:
  - **Names:**
    - syntax mistakes;
    - names that are never set, or only set inside another function;
    - built-ins replaced by variables;
    - functions made twice;
    - your own files: an import with no file to load, files that import each other, a file named like a library, and names or input counts another file doesn't have (`money.as_mony`).
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
    - `:pop(0)`;
    - text mixed with numbers, like typed answers used as numbers or `"Total: " + a + b`;
    - a template's number format on text, like `f"{name:0.00}"`;
    - chained comparisons;
    - `or "y"` in a condition;
    - lines whose answer is thrown away.

  It only checks a widget's methods when it knows what the value is, so a widget kept in a list or passed into a function isn't checked. It can't catch:
  - mistakes that depend on values while running, like the contents of a list or a position past its end;
  - widgets that don't fit the window.
- **`tuff_run`** runs a console program with your answers. It shows the final Run window, with each answer after its question; lines changed with `:rewrite` or `clear` show their final state. If the program asks more questions than there are answers, it stops with an error saying so.
  - **Files:** writes stay in memory for that run. `file.write`, `file.add`, `file.save` and `file.delete` work, and later reads in the same run see them, but nothing is saved and no file on disk changes. To change the user's files, edit them yourself.
  - **Folders:** with `"code"`, relative paths are in the project folder, so a snippet can read the project's files and import its own .tuf files (`import money`). With `"file"`, they're in that file's folder.
  - When you run Tuff another way (in a terminal), set `TUFF_NO_WRITES=1` for the same in-memory writes, and `TUFF_BASE_DIR=<folder>` to make relative paths start in that folder instead of the program's.
- **Testing a window program:** window programs open a real window, so test them with a self-test.
  1. Add `app:after(0.5, selftest)` just before the last line.
  2. Write `func selftest():` so that it calls your event functions, uses `say` to show what it finds, and ends with `app:close`.
  3. Run it with `tuff_run`. The window shows for under a second, and you get the `say` output.
  4. Remove the self-test afterwards.

## What Tuff can't do
Tuff has none of these:
- the internet except through `tap`, or files outside text and JSON (`file`);
- classes, or `lambda` (give a function's name instead, like `words:sort(by_len)`);
- tuples or sets (use lists and dictionaries);
- default or keyword inputs;
- exp, or other maths beyond sin, cos, tan, log and sqrt;
- formats beyond a template's (`0.00`, `000`, `money` and a width), `text(x, 2)` and `:pad_left` / `:pad_right`;
- drawing, sound, or keyboard and mouse events in tgui and mtgui (see "How a window app runs"). atgui has key shortcuts, hover and clicks on any widget, and a game made with `tgame` has all of them;
- `exit()`, or Python modules.

For dates and times there's `now()`, `today()`, `date()` and `time()`, and `wait(seconds)` pauses a console program.
