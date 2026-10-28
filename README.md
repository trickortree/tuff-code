# TuffCode

**TuffCode** is a desktop IDE for **Tuff**, a small programming language that's easy to read and fun to learn. It looks and feels like PyCharm and comes with an animated intro, a built-in tutorial, a visual Design Studio for app windows, Tuff Engine for games, and a one-click `.exe` builder.

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

## Download

Get the newest version from the [Releases page](https://github.com/trickortree/tuff-code/releases/latest):

| System | File |
| --- | --- |
| **Windows** (10 and 11) | `TuffCode-Setup-<version>.exe` |
| **Mac with Apple Silicon** (M1 and newer) | `TuffCode-<version>-mac-arm64.dmg` |
| **Mac with an Intel chip** | `TuffCode-<version>-mac-x64.dmg` |

The Mac version needs macOS 13 (Ventura) or newer. The Mac files are built on GitHub's Macs and added to a release after the Windows installer. If a release doesn't list them yet, check back later.

To find which Mac you have, open the Apple menu and choose **About This Mac**. The **Chip** line says Apple (M1, M2…) or Intel.

**Installing on a Mac:** open the `.dmg` and drag TuffCode into Applications. TuffCode isn't signed with a paid Apple developer ID yet, so the first time you open it, macOS refuses. To let it open:
1. Try to open TuffCode once and close the warning.
2. Open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to TuffCode.
3. Confirm with your password.

You only do this once. On a Mac, TuffCode tells you when there's a new version and opens its download page. It can't replace itself the way the Windows version does.

**Windows:** if SmartScreen says "Windows protected your PC", click **More info → Run anyway**.

## Features

- **PyCharm-style IDE:** project tree, tabs, Monaco editor with Tuff highlighting, autocomplete and hover help, a Run window with input, Search Everywhere (double Shift), and PyCharm shortcuts.
- **Learn Tuff:** a step-by-step tutorial that checks your answers. Every section after Basics is optional.
  - Basics: 10 lessons (the newest: checking answers with `err`).
  - Section 1.5, colours, big letters and animations in the Run window: 5 lessons.
  - Section 1.6, the toolbox (dictionaries, text tools, sorting, files, try and catch): 5 lessons.
  - Section 1.7, the workshop (text templates, kinds, your own files, music, a terminal game, sprite sheets): 7 lessons.
  - Section 2, apps with tgui: 8 lessons.
  - Section 2.1, modern apps with mtgui: 4 lessons.
  - Section 2.2, advanced apps with atgui: 8 lessons.
  - Section 3, the internet with tap: 7 lessons.
  - Section 4, games with tgame: 9 lessons, including Tuff Engine.
  - Section 5, drawing with tdraw: 5 lessons.
- **tgui and mtgui:** real desktop windows with buttons, text boxes, switches, checkboxes, dropdowns, sliders, progress bars, spinners, clocks, cards and rows. mtgui adds gradients, gloss, shine and glow. Anything animated has `:speed`.
- **atgui:** modern app windows made of real HTML and CSS, the kind of apps Claude or Codex are: sidebars, lists, chat bubbles, tables, charts, markdown, menus, pop-ups, toasts, key shortcuts, animations, glass and gradients, a custom title bar. Everything from mtgui works too.
- **tgame:** games, like pygame. 2D sprites, keys, the mouse, collisions and sounds, or 3D worlds with a sky, an island, trees, rocks and houses, `.glb` models and a first- or third-person player. Write a `while game:open():` loop or use events. Build them visually in Tuff Engine.
- **tap:** the web from Tuff, like Python's `requests`: `tap.get`, `post`, `put`, `delete`, with JSON as data objects (`user:get("name")`).
- **Design Studio** (`Ctrl+Shift+D`): build windows by clicking. Every change is written straight into your code.
- **Tuff Engine** (`Ctrl+Shift+G`): build tgame games by clicking and dragging, with ready-made players, coins and enemies. The preview is the real game engine, and every change is real Tuff code.
- **Gear in the margin:** hover a UI line and click the gear to change its settings without typing.
- **Auto Code Sort** (`Ctrl+Alt+L`): fixes indentation, puts imports first and functions last, tidies spacing and adds notes. It checks the result with the interpreter first, so it never breaks working code.
- **Build .exe** (`Ctrl+F9`): turn any program into a Windows app with your own name and icon (on a Mac, into a Mac app). The build log explains each step in plain English.
- **Auto-updates:** checks this repo for new releases every 1, 2, 4 or 8 hours (2 by default). On Windows it can install them in the background.
- **Plugins** (`Alt+3`): a marketplace for extra tools in a sidebar on the right: the Snippet Library, API Explorer (try a web API, click a value and get the tap code), Sprite Studio (pixel art for games and apps) and Sound Lab (game sound effects as .wav).
- **Tuff Agents** (`Ctrl+Shift+A`): an AI chat sidebar that runs Claude Code, Codex or Antigravity on your project. They learn Tuff through TuffCode's MCP tools (see below) and share one chat.
  - **Ask, Plan or Edit:** Ask explains and offers changes ("Edit it for me"); Plan makes a plan first ("Go ahead"); Edit changes your files.
  - **`/` commands:** `/compact` sums up a long chat for every agent, plus `/plan`, `/model opus`, `/codex` and more (`/help`).
  - **Explain** on a Tuff error in the Run window asks the agent what went wrong.
- **Tuff AI (preview):** an offline helper that runs on your own computer, with no account. Download its model once (1.3 GB) from the Tuff AI tab. It's an untrained preview for now; every program it writes is checked by Tuff first.

## Using AI agents with Tuff (MCP)

AI agents don't know Tuff, so TuffCode includes an MCP server that teaches them. MCP is the standard way agents plug into tools. It gives an agent:
- the Tuff guide;
- 8 example apps;
- a checker that catches unknown names and methods that don't exist;
- a runner.

In TuffCode, open Tuff Agents and click the plug button. There you can check the tools work, connect each agent with one click, or copy the commands to set it up by hand. Full instructions, including Claude Desktop, Cursor and VS Code, are in [tuffcode/mcp/README.md](tuffcode/mcp/README.md).

## Running it

You need [Node.js](https://nodejs.org) 22.12 or newer (for the IDE) and [Python 3](https://python.org) (to run Tuff programs).

```bash
cd tuffcode
npm install
npm start
```

`npm start` downloads Electron the first time (`npm install` doesn't, since Electron 42). On Windows you can also just double-click `tuffcode/TuffCode.cmd`: it runs `npm install` and gets Electron by itself when they're needed.

**Updating a copy like this from 1.0.3 to 1.0.4:** 1.0.4 runs on a newer Electron, which 1.0.3's updater can't install by itself. On Windows, if the update says npm couldn't install the new parts, close TuffCode and double-click `tuffcode/TuffCode.cmd`. On a Mac, if TuffCode doesn't open again after the update, run `npm start` in `tuffcode/`: it downloads the new Electron.

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
| Numbers and text | `number("42")` (or `num`), `int("3.7")` is 3, `text(5)` (or `str`). Text that isn't a number gives `err`: `if num(answer) is err:` |
| Decisions | `if answer is "yes":` (or `then`, or `then:`), `elif`, `else` |
| Loops | `for i in range(1, 10):`, `while x > 0:` |
| Functions | `func double(n):` gives back its last value, or use `return` |
| Live lines | `line = say "Loading"`, then `line:rewrite "Done!"` |
| Clearing | `flush`, `clear(all)`, `clear(2)` |
| Libraries | `import anims` or `mention anims` (same thing): `anims`, `tgui`, `mtgui`, `atgui`, `tgame`, `tap` |

## Project layout

- `tuff.py`: the Tuff interpreter
- `tuff_tgui.py`: the tgui and mtgui libraries (built on tkinter, no extra installs)
- `tuff_tap.py`: tap (HTTP, standard library only)
- `tuff_view.py` and `tuff_view_web/`: the web view engine (pywebview, three.js) under `tuff_atgui.py` (atgui) and `tuff_tgame.py` (tgame)
- `tuff-ai/`: Tuff AI's test set (Tuff Bench) and the model bake-off
- `tuffcode/`: the Electron IDE
  - `main.js`: the window, files and running programs
  - `build.js`: the `.exe` builder (PyInstaller)
  - `updater.js`: the auto-updater
  - `renderer/`: the IDE's interface, including the editor, Design Studio, Tuff Engine (`js/tuff-engine.js`, with its game preview in `engine-host/`), tutorial, intro and Auto Code Sort

## Releasing an update

1. Bump `version` in `tuffcode/package.json` (and `package-lock.json`, and `VERSION` in `tuffcode/mcp/tuff-mcp.js`), then merge to `main`.
2. Build the Windows installer with `npm run dist` in `tuffcode/`.
3. Publish a GitHub release for the tag `v<version>` with `TuffCode-Setup-<version>.exe`, its `.blockmap` and `latest.yml` from `build/installer/`.
4. Publishing the release starts the **Mac build** workflow (`.github/workflows/mac.yml`). It builds the Apple Silicon and Intel apps on GitHub's Macs, tests them, and adds the `.dmg`, `.zip` and `latest-mac.yml` files to the same release.

Installed copies of TuffCode find the new release on their next update check.
