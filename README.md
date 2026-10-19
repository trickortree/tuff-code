# TuffCode

**TuffCode** is a desktop IDE for **Tuff**, a small programming language that's easy to read and fun to learn. It looks and feels like PyCharm and comes with an animated intro, a built-in tutorial, a visual Design Studio for app windows, and a one-click `.exe` builder.

```tuff
mention mtgui

app = mtgui.window("Hello")
app:heading "Hi there!"
name = app:input "Your name"
hello = app:text ""

func greet():
    hello:set "Hey " + name:value + "!"

app:button("Say hi", greet)
```

## Features

- **PyCharm-style IDE:** project tree, tabs, Monaco editor with Tuff highlighting, autocomplete and hover help, a Run window with input, Search Everywhere (double Shift), and PyCharm shortcuts.
- **Learn Tuff:** a step-by-step tutorial that checks your answers.
  - Basics: 9 lessons.
  - Section 2, apps with tgui: 8 lessons.
  - Section 2.2, modern apps with mtgui: 4 lessons.
- **tgui and mtgui:** real desktop windows with buttons, text boxes, switches, checkboxes, dropdowns, sliders, progress bars, spinners, clocks, cards and rows. mtgui adds gradients, gloss, shine and glow. Anything animated has `:speed`.
- **Design Studio** (`Ctrl+Shift+D`): build windows by clicking. Every change is written straight into your code.
- **Gear in the margin:** hover a UI line and click the gear to change its settings without typing.
- **Auto Code Sort** (`Ctrl+Alt+L`): fixes indentation, puts imports first and functions last, tidies spacing and adds notes. It checks the result with the interpreter first, so it never breaks working code.
- **Build .exe** (`Ctrl+F9`): turn any program into a Windows app with your own name and icon. The build log explains each step in plain English.
- **Auto-updates:** checks this repo for new releases every 1, 2, 4 or 8 hours (2 by default) and can install them in the background.

## Running it

You need [Node.js](https://nodejs.org) (for the IDE) and [Python 3](https://python.org) (to run Tuff programs).

```bash
cd tuffcode
npm install
npm start
```

On Windows you can also double-click `tuffcode/TuffCode.cmd` after `npm install`.

You can also run a Tuff program without the IDE:

```bash
python tuff.py myprogram.tuf
```

## The Tuff language at a glance

| Idea | Tuff |
| --- | --- |
| Show text | `say "Hello"` |
| Variables | `score = 10`, `score += 5` |
| Ask a question | `name = input "Name? "` |
| Math | `+ - * / % ^`, `sqrt`, `abs`, `round`, `min`, `max`, `sum`, `average`, `pi` |
| Decisions | `if answer is "yes":` (or `then` instead of `:`), `elif`, `else` |
| Loops | `for i in range(1, 10):`, `while x > 0:` |
| Functions | `func double(n):` gives back its last value, or use `return` |
| Live lines | `line = say "Loading"`, then `line:rewrite "Done!"` |
| Clearing | `flush`, `clear(all)`, `clear(2)` |
| Libraries | `import anims` or `mention anims` (same thing): `anims`, `tgui`, `mtgui` |

## Project layout

- `tuff.py`: the Tuff interpreter
- `tuff_tgui.py`: the tgui and mtgui libraries (built on tkinter, no extra installs)
- `tuffcode/`: the Electron IDE
  - `main.js`: the window, files and running programs
  - `build.js`: the `.exe` builder (PyInstaller)
  - `updater.js`: the auto-updater
  - `renderer/`: the IDE's interface, including the editor, Design Studio, tutorial, intro and Auto Code Sort

## Releasing an update

Bump `version` in `tuffcode/package.json`, commit, then tag and push it:

```bash
git tag v1.0.1
git push origin main --tags
```

Installed copies of TuffCode find the new tag on their next update check.
