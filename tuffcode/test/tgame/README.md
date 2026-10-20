# tgame: games for Tuff

`tuff_tgame.py` (repo root) is **tgame**, "pygame but for Tuff", on the web view engine (`tuff_view.py`, see `../view/README.md`).
`tgame.window` is a 2D game on a canvas; `tgame.world` is a 3D world in three.js.
The language guide (`tuffcode/mcp/tuff-guide.md`, "### tgame") is the user's documentation.

These tests run **real .tuf games in real windows**. Each game plays itself with tgame's autopilot and closes.

```
py -3 tuffcode/test/tgame/run_tests.py [test ...] [--runtime build/runtime/tuff-runtime/tuff-runtime.exe] [--out-dir folder]
node tuffcode/test/tgame/build_exe_test.mjs          # Build exe for a game, then run the built app (about 30 s)
node tuffcode/test/e2e/run.mjs tgame                  # (in tuffcode/) the Run button and the yellow notice, in the IDE
```

Screenshots, the autopilot's plans and the games' JSON reports go to `tuffcode/test/tgame/out/` (ignored by git).
Don't cover the windows while the tests run: a covered page stops drawing.
`--runtime` runs every game with a frozen Tuff runtime instead of Python + `tuff.py`.

| Test | What it proves |
| --- | --- |
| `snake` | `games/snake.tuf` (the 2D example, ~40 lines): eating, growing, turning with the arrows, the wall ending the game, space playing again; 60 fps; the screenshot shows the board, the head and the game over title |
| `breakout` | `games/breakout.tuf`: holding a key, the ball breaking a brick (`touches` on a group), losing the last ball, playing again with all 40 bricks |
| `snake3d` | `games/snake3d.tuf`: a 3D snake with a follow camera: eating, growing, turning, hitting the fence, playing again |
| `axe` | `games/axe_sim.tuf`, the "Hypergamous Axe Sim": first person, walking with W, three clicks on the pine in front shake it and fell it, Logs: 1, mouse look, the tree growing back 5 s later; sky and grass in the screenshot |
| `features_2d` | Every 2D method once: sprites from a picture, spots, touches, groups, values, angles, `point_at`, `forward`, edges, clicks on a sprite and on the game, keys, held and pressed, timers, glide, speed, pause/resume, sound files and built-in sounds |
| `features_3d` | Shapes, the kit, a `.glb` model, labels, lights, fog, skies, `looking_at`, clicks on objects, fall/regrow, spin, glide, and the fixed, orbit and follow cameras |
| `player_3d` | Third person: solid things block the way, jumping onto a crate, picking up a coin, turning with D, and the code after the loop running once the window closes |
| `callback` | The callback style: `every_frame`, `on_key`, `after`, and `game:close` ending the program |
| `errors` | A failing every-frame function is reported once and switched off while the game goes on; an error in the main loop stops the program and closes its window |
| `notice` | The Tuff Engine line: first in the IDE's line protocol with the `notice` style, ANSI yellow in a terminal, plain in a pipe, never for `--check`, programs without tgame or a `--windowed` app |
| `mcp` | `tuff_run` through the MCP server shows the notice as a plain first line |
| `checker` | `--check` accepts every game here and correct snippets, and catches 34 kinds of mistake (wrong names with "Use :box instead", input counts, colors, keys, sounds, skies, missing files, event functions) |
| `editor` | `tuff-lang.js`: tgame's functions, docs for all 101 method names, completions that only offer tgame's own methods in files using tgame, and the 2D and 3D snippets (which pass `--check` and run) |
| `guide` | Every example in the guide's tgame section passes `--check` and runs |
| `perf` | Frame rates: 200 sprites moved by Tuff code, 200 moving by `:speed`, 300 objects with a first-person walk, 300 boxes moved by Tuff code |

## Measured on this PC

i9-12900K, RX 7900 XTX, Windows 11, a ~132 Hz display, Python 3.12.10, pywebview 6.2.1, WebView2 155.
The last full runs: **228 passed, 0 failed** with Python + `tuff.py`, and the same 228 through the frozen runtime
(`npm run build:runtime`). `build_exe_test.mjs`: 11/11. The IDE suite `e2e/suites/tgame.mjs`: 7/7.

All four performance programs are Tuff programs in the pygame style (`while game:open(): dt = game:frame()`):

| Program | Tuff fps | The program's own work per frame (median / p95) | tgame's work per frame | Page draws per s | Page draw per frame |
| --- | --- | --- | --- | --- | --- |
| 200 sprites, each moved by Tuff code (`s:move(vx[i] * dt, vy[i] * dt)`, wrapping at the edges) | **60.0** | 3.6 / 3.9 ms | 0.01 ms | 133 | 0.04 ms |
| The same 200 sprites moving by themselves (`s:speed(vx, vy)`, set once) | **60.0** | 0.08 / 0.10 ms | 0.29 ms | 132 | 0.04 ms |
| 300 objects from the kit on an island, first-person walk with mouse look | **60.0** | 0.09 / 0.13 ms | 0.39 ms | 133 | 0.59 ms |
| 300 boxes, each moved by Tuff code (`b:move_to(b:x(), up, b:z())`), first-person walk | **60.0** | 9.4 / 10.0 ms | 0.42 ms | 133 | 0.34 ms |

- **The Tuff interpreter is the bottleneck,** not the engine: about 18 µs per sprite for a `:move` with two list reads and two multiplications, and about 31 µs per box for three method calls. 60 fps has room for roughly 800 simple Tuff method calls a frame.
- **Batch-friendly calls** take that work out of Tuff: `:speed` (moves by itself every frame), `:spin`, `:glide`, `:on_edge`, and `group:move`, `group:hide`, `group:color` for many things at once. 200 sprites with `:speed` cost the program 0.08 ms a frame instead of 3.6 ms.
- tgame's own work (input, things that move by themselves, the player walking and colliding with 300 objects) stays under half a millisecond a frame.
- The page applies about 60 batches a second (one per frame) and draws at the display's rate; the 300-object island is about 1,260 three.js objects (each tree is a group of four meshes) and draws in 0.6 ms.

## The autopilot

`TUFF_TGAME_AUTOPILOT=plan.json` makes a game play itself. Its steps run at times counted from the first frame:

```json
{"on_top": true, "out": "folder", "seed": 1, "timeout": 20, "steps": [
  {"at": 0.5, "key": "right"}, {"at": 1, "hold": "w", "for": 0.8}, {"at": 1.2, "keydown": "a"}, {"at": 1.4, "keyup": "a"},
  {"at": 2, "click": [300, 200]}, {"at": 2.1, "click_world": [100, 100]}, {"at": 2.2, "click_center": true},
  {"at": 2.3, "press_mouse": true}, {"at": 2.4, "look": [200, 0]}, {"at": 2.5, "release_mouse": true}, {"at": 2.6, "lock": true},
  {"at": 3, "tuff": "food:move_to(250, 210)"}, {"at": 3.1, "call": "report"}, {"at": 3.2, "say": "a marker"},
  {"at": 3.3, "mark": true}, {"at": 4, "shot": "name.png"}, {"at": 4.1, "dump": "name.json"}, {"at": 5, "close": true}]}
```

Keys, clicks and mouse movement are made in the page, so they reach the game the same way real ones do.
`lock` makes the game act as if the mouse were locked (a test can't lock it). `tuff` runs a line of Tuff at the top of the program.
`dump` writes what the game is doing: frame rates, the page's own numbers, every sprite and object, the texts, the labels, the player and the camera.

## Example games

`games/snake.tuf`, `games/breakout.tuf`, `games/snake3d.tuf` and `games/axe_sim.tuf` are the examples. Play one with
`py -3 tuff.py tuffcode/test/tgame/games/axe_sim.tuf`. The other programs in `games/` are the tests' own.
`star.png`, `blip.wav` and `tower.glb` are small fixtures made with the standard library.

## Not done, or worth knowing

- **One window per program,** like tuff_view. No physics engine: collisions are boxes and circles (rotation is left out), and the player's are boxes too.
- **Restarting** is the program's own `start` function (`game:game_over(message, start)`); tgame doesn't rerun the whole program.
- **A Mac** hasn't run any of this. WKWebView may hold sound back until the first click or key press (the page retries then), and the window's size correction assumes pywebview's size includes the title bar, as on Windows.
- **Tests and focus:** a window that loses focus lets go of its held keys (that's right for a game), so another app popping up during a test can fail a "held" check; the reports say how often the window lost focus. Covered windows also stop drawing.
- `.glb` models: meshes, node transforms, base colors and packed pictures, but no animations, skins or morph targets.
