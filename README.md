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

## Download

Get the newest version from the [Releases page](https://github.com/trickortree/tuff-code/releases/latest):

| System | File |
| --- | --- |
| **Windows** (10 and 11) | `TuffCode-Setup-<version>.exe` |
| **Mac with Apple Silicon** (M1 and newer) | `TuffCode-<version>-mac-arm64.dmg` |
| **Mac with an Intel chip** | `TuffCode-<version>-mac-x64.dmg` |

To find which Mac you have, open the Apple menu and choose **About This Mac**. The **Chip** line says Apple (M1, M2…) or Intel.

**Installing on a Mac:** open the `.dmg` and drag TuffCode into Applications. TuffCode isn't signed with a paid Apple developer ID yet, so the first time you open it, macOS refuses. To let it open:
1. Try to open TuffCode once and close the warning.
2. Open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to TuffCode.
3. Confirm with your password.

You only do this once. On a Mac, TuffCode tells you when there's a new version and opens its download page. It can't replace itself the way the Windows version does.

**Windows:** if SmartScreen says "Windows protected your PC", click **More info → Run anyway**.

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
- **Build .exe** (`Ctrl+F9`): turn any program into a Windows app with your own name and icon (on a Mac, into a Mac app). The build log explains each step in plain English.
- **Auto-updates:** checks this repo for new releases every 1, 2, 4 or 8 hours (2 by default). On Windows it can install them in the background.
- **Plugins** (`Alt+3`): a marketplace for extra tools in a sidebar on the right, like the Snippet Library.
- **Tuff Agents** (`Ctrl+Shift+A`): an AI chat sidebar that runs Claude Code, Codex or Antigravity on your project. They learn Tuff through TuffCode's MCP tools (see below).

## Using AI agents with Tuff (MCP)

AI agents don't know Tuff, so TuffCode includes an MCP server that teaches them. MCP is the standard way agents plug into tools. It gives an agent:
- the Tuff guide;
- 8 example apps;
- a checker that catches unknown names and methods that don't exist;
- a runner.

In TuffCode, open Tuff Agents and click the plug button. There you can check the tools work, connect each agent with one click, or copy the commands to set it up by hand. Full instructions, including Claude Desktop, Cursor and VS Code, are in [tuffcode/mcp/README.md](tuffcode/mcp/README.md).

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

1. Bump `version` in `tuffcode/package.json` (and `package-lock.json`, and `VERSION` in `tuffcode/mcp/tuff-mcp.js`), then merge to `main`.
2. Build the Windows installer with `npm run dist` in `tuffcode/`.
3. Publish a GitHub release for the tag `v<version>` with `TuffCode-Setup-<version>.exe`, its `.blockmap` and `latest.yml` from `build/installer/`.
4. Publishing the release starts the **Mac build** workflow (`.github/workflows/mac.yml`). It builds the Apple Silicon and Intel apps on GitHub's Macs, tests them, and adds the `.dmg`, `.zip` and `latest-mac.yml` files to the same release.

Installed copies of TuffCode find the new release on their next update check.
