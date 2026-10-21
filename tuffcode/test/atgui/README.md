# atgui tests

atgui ("advanced Tuff GUI", `tuff_atgui.py`) makes modern app windows from Tuff: real HTML and CSS in a native
window, through the web view engine (`tuff_view.py`, see `../view/README.md`). These tests run real `.tuf`
programs in real windows. Each window opens for a few seconds and closes by itself.

```
py -3 tuffcode/test/atgui/run_all.py [--only check,widgets,...] [--out-dir folder]   # everything, about 50 s
py -3 tuffcode/test/atgui/check_test.py                                              # the checker cases only
node tuffcode/test/atgui/docs_test.mjs                                               # the editor's tables only
py -3 tuffcode/test/atgui/freeze.py                                                  # packaging proof, about 30 s
py -3 tuffcode/test/atgui/drive.py program.tuf [--driver driver.js] [--out r.json]   # one program
```

Don't cover the test windows while they run: Chromium stops drawing a page that's completely covered.
Results, numbers and screenshots go to `out/` (ignored by git).

## How a program is driven

`drive.py` runs a program exactly as `tuff.py program.tuf` does (through `tuff_view.run`). It only wraps
`tuff_view.View`, so that when the window opens it can add a driver script to the page. A driver clicks,
types, presses keys and hovers with real DOM events, so they go through the engine's bridge and atgui's
handlers like a person's would. It waits for each answer from the Tuff program (a change in the page),
times round trips with a MutationObserver, and asks for screenshots, which WebView2 takes through the
DevTools protocol (`Page.captureScreenshot`). `T.press(' ')` makes a real key press through DevTools too
(`Input.dispatchKeyEvent`), for what only a trusted key does, like Space pressing a focused button. A program that tests itself (`app:after` + `app:close`, as the
guide recommends) needs no driver. A watchdog ends a run that hangs.

Real focus events only fire while the window is the foreground one, so `widgets.js` sends `focusin` and
`focusout` itself. Everything after that (atgui's listener, the bridge, the Tuff function) is real.

| Step (`--only` name) | What it proves |
| --- | --- |
| `check` (`check_test.py`) | `tuff.py --check`: 51 atgui mistakes caught (method names, input counts, styles, icons, themes, keys, event functions...), 10 correct programs accepted, including a kitchen sink of every widget and method |
| `docs` (`docs_test.mjs`) | `tuff-lang.js` loads as the MCP server loads it; every atgui method (96 names) has a doc; shared docs kept their text; the snippet passes `--check` |
| `widgets` | Every widget and event through the page: the 29 lines the program says, in order (each event function's input included), and 45 checks of the page (styles, hover and pressed rules, tooltip, context menu, modal, Escape, markdown, code, pictures, split, glass, gradient, animation, escape hatches...) |
| `selftest` | A program that drives itself: `:set`, `:value`, `:add`, `:remove`, `:clear`, pages, timers and `app:closed` |
| `errors` | A mistake in a click, a keystroke and a timer function is reported once each, with its line, and the app keeps working |
| `popups` | `app:ask`, `app:confirm` (a real Space press on the focused Yes, and Escape for No) and `app:alert` in the top-level code; timers keep running meanwhile |
| `osclose` | Closing with WM_CLOSE (the X button), through plain `tuff.py`: exit 0, `app:closed` ran |
| `frameless` | `app:titlebar`: drag regions, the three buttons, maximize and restore (button and double-click), resize, close |
| `latency` | 100 clicks and 100 keystrokes, each timed from the DOM event to the Tuff function's change in the page |
| `biglist` | 1,000 list items in a scroll area: scrolled for 3 s, a step every frame, with the frames timed; then item 900 is picked |
| `chat`, `settings`, `dashboard` | The examples (each 30-60 lines, `--check` OK): used through the page and screenshotted |
| `guide` | Every ```tuff example in the guide's "### atgui" section passes `--check` and runs |
| `compat` | The guide's three mtgui examples, with `mention atgui`, pass `--check` and run unchanged |

## Measured on this PC

i9-12900K, Windows 11, a ~132 Hz display, Python 3.12.10, pywebview 6.2.1. Last full run: **116 passed, 0 failed**.

| | |
| --- | --- |
| A small app on screen, from starting Python | **0.93 s** (the program's top level 0.09 s, the engine's window 0.77 s, the first batch drawn 0.03 s) |
| The examples on screen | chat 0.96 s, settings 1.06 s, dashboard 1.01 s |
| 1,000 items on screen | 1.04 s; one batch of 309 KB, built in 1.4 ms of Python and applied by the page in 5 ms |
| Scrolling the 1,000 items | **131 fps** (the display's rate): frame gaps median 7.6 ms, p95 8.5 ms, worst 9.0 ms; no long frames |
| Click -> Tuff function -> page | **1.1 ms** median, 2.2 ms p95 |
| Keystroke -> `:change` -> page | 1.1 ms median, 2.2 ms p95 |
| Closing with the X button | the program ends 0.61 s later |
| Packaging (`freeze.py`) | the runtime and a Build-exe app both run atgui programs; the app is 11.95 MB |

About half of the window's 0.77 s is importing pywebview and pythonnet (0.5 s, measured with cached
bytecode); the rest is WebView2 starting and loading the page. atgui opens the window when the program's top
level ends, so the first screen arrives in one batch, with the theme, size, frame and icon already right.
