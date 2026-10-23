# tuff_view: the web view engine (wave 1)

`tuff_view.py` (repo root) is the engine that **atgui** (apps) and **tgame** (2D and 3D games) will sit on.
A window is a web page shown by [pywebview](https://pywebview.flowrl.com): Edge WebView2 on Windows, WKWebView on a Mac.
The page (`tuff_view_web/engine.js`) keeps a retained scene and draws it at the display's own rate.
Python only sends what changed, once per frame.

These tests are Python scripts, not Tuff programs yet. Each one opens a real window, runs by itself, measures, and closes.

```
py -3 tuffcode/test/view/run_all.py [--sweep] [--out-dir folder]   # everything, about 80 s
py -3 tuffcode/test/view/view_ui_test.py                           # or one at a time
py -3 tuffcode/test/view/freeze.py                                 # the PyInstaller proof, about 30 s
```

Don't cover the test windows while they run. Chromium stops drawing a page that's completely covered.
The 2D, 3D and latency windows ask to stay on top.

| File | What it proves |
| --- | --- |
| `view_ui_test.py` | **(a)** 50 DOM widgets; click, type, tick and key round trips; bubbling; mouse and wheel; errors reported once (an object that can't be made, once, not again for what's inside it) |
| `view_2d_stress.py` | **(b)** 300 sprites moved by Python every frame at 60 fps (`--sweep`: 1000, 2000, 5000); a negative-radius circle; 1,000 shapes made and removed leave no ids behind |
| `view_3d_test.py` | **(c)** three.js, 200 cubes, a first-person camera moved from Python, raycast clicks, crosshair picks |
| `view_latency.py` | **(d)** one event, page → Python → page, in both loop styles, plus `ask()` |
| `view_close_test.py` | Closing the window ends the program cleanly in every loop style; a crash closes it too. The close handler runs at any moment: closed before the page is ready, closed behind a handler waiting in `frame()`, and before the window has gone (the process ended right then, like Cmd+Q), with no stall while the program is calling the window. A tgame program closed the instant its window appears still runs the code after its loop |
| `view_window_test.py` | Frameless, not resizable, `.png`/`.ico`/`TUFF_APP_ICON` icons, title, resize, no WebView2, no pywebview (Win32 checks) |
| `view_server_test.py` | The page's file server, with no window: it serves a file with its token, and a dropped connection prints no traceback |
| `freeze.py` | **(5)** The 3D test frozen with PyInstaller `--onefile --windowed`, then run |
| `harness.py`, `run_all.py` | Shared helpers, the runner |

## Measured on this PC

i9-12900K, RX 7900 XTX, Windows 11, a monitor that WebView2 drives at **~132 Hz**. Python 3.12.10, pywebview 6.2.1, WebView2 155.0.4283.62.
The last full run: **79 checks passed, 0 failed**; the numbers below are from an earlier one (62 checks). The frozen exe passed 9/9.

**Target met: 60 fps for (b) and (c), with Python using about 3% of each frame.**

| | Python fps | Python's time per frame (median / p95) | Batches the page applied per s | Page draws per s |
| --- | --- | --- | --- | --- |
| (b) 300 sprites, 60 fps | **60.0** | 0.49 / 0.52 ms | 60.1 | 131.7 (display rate) |
| (b) 300 sprites, unpaced (`fps=0`) | **725.6** | 0.44 / 0.49 ms | 725.5 | 130.9 |
| (b) 1000 sprites, 60 fps | 60.0 | 1.5 / 1.6 ms | 60.2 | 131.9 |
| (b) 2000 sprites, 60 fps | 60.0 | 3.0 / 3.2 ms | 60.3 | 132.0 |
| (b) 5000 sprites, 60 fps | 59.8 | 7.6 / 12.3 ms | 59.8 | 128.3 |
| (c) 200 cubes + camera, 60 fps | **59.9** | 0.33 / 0.37 ms | 60.0 | 132.0 (display rate) |

"Python's time per frame" is the program's own work (moving everything) plus `flush()` (building and queuing the batch).
It doesn't include the sleep.

- **Frame pacing:** for (b), the gap between frames had a median of 16.69 ms and a p95 of 17.01 ms. The page's own frame gaps had a median of 7.6 ms and a p95 of 8.4 ms, so no frames were dropped.
- **Batch size:** a 300-sprite batch is 19 KB of JSON. The page applies it in 0.023 ms and draws the canvas in 0.13 ms.
- **Send cost:** the bridge's `run_js` takes 1.2 ms for each batch, on the sender thread, not the Tuff thread.
- **At 5000 sprites** (327 KB per batch), `json.dumps` is most of Python's 7.6 ms and `run_js` takes 15 ms. That's where a packed "move many" command would be the next step. Nothing below that needs it.
- **(c) clicks:** 20 of 20 raycast clicks named the cube under them, each with the 3D point it hit. 10 of 10 crosshair picks were right, and `ask(scene, "pick")` takes a median of 1.1 ms.

| (d) and (a): round trips | median | p95 | max |
| --- | --- | --- | --- |
| Callback style (`loop()`): page event → Python handler → DOM change seen by the page | **1.4 ms** | 1.8 ms | 3.7 ms |
| Pygame style (`frame()` at 60 fps): the same, handled at the next frame | 9.4 ms | 17.1 ms | 17.5 ms |
| `ask()`: Python → page → Python, timed from Python | 1.4 ms | 3.6 ms | 23 ms |
| (a) Click a widget → Python → its new text in the DOM (51 widgets) | 1.5 ms | 2.5 ms | 6.8 ms |

- **Pygame style:** the extra time is the wait for the next tick, on average half a frame. That's how a polling loop works.
- **Opening a window:** the first `View()` takes 0.84–1.6 s until the page is ready. three.js loads on first use in about 45 ms.
- **Closing:** after WM_CLOSE (what the X button sends), `run()` returns in about 300 ms in every loop style. That's mostly pywebview shutting WebView2 down: it waits for the browser process and deletes the profile folder. The Tuff thread sees the close straight away, as the window starts closing, and the window goes once the close handlers have run.

A first micro-benchmark of plain pywebview had already shown the bridge wasn't the problem, so no fallback was needed:

| | median |
| --- | --- |
| `run_js("apply(0)")` | 0.34 ms |
| `run_js` with an 11 KB batch | 0.42 ms |
| `evaluate_js` with an 11 KB batch | 0.50 ms |
| A `js_api` call from JS, until its promise resolved | 0.6 ms |

So the design was about latency and correctness, not speed:
- **One batch per frame:** one `run_js` per frame, with no `eval` wrapper.
- **Sets merged:** several changes to the same object in a frame become one.
- **A sender thread** keeps `run_js` off the Tuff thread (see below).
- **Sequence numbers** keep events in order.
- **Discrete events go at once;** mouse movement is merged once per animation frame.

## Architecture

### Threads

```
main thread   tuff_view.run() → webview.start(): the window system. (On Windows, pywebview runs WinForms on
              its own STA thread and the main thread waits on it; on a Mac, Cocoa runs on the main thread.)
"tuff"        ALL program code: the Tuff program, every handler, every-frame function, frame(), loop().
"tuff-view-send"  takes queued batches and calls window.run_js (blocks ~1 ms each). Daemon.
pywebview's   one new thread per page→Python call (js_api) and per window event (closed...). They only
threads       append to a queue under a lock and wake the Tuff thread, and tell the mouse hold when the page
              holds the mouse or lets go (so Escape lets go at once, even while the program is busy).
"tuff-view-mouse" while a first-person game holds the mouse (Windows, Mac) and its window is in front: keeps the
              cursor in the window and adds up its moves. Daemon.
"tuff-view-files" a ThreadingHTTPServer on 127.0.0.1 serving the page and the program's assets.
```

- **Why the program moves off the main thread:** `webview.start()` refuses to run anywhere but the main thread, and Cocoa needs it.
- **`run(main)`:** starts `main` on the Tuff thread. When the program makes its first `View`, the main thread opens the window and runs the window system until the window closes.
- **Why a sender thread:** pywebview's `run_js` blocks until the page ran the script. On Windows it waits on a semaphore that closing the window never releases. Run from the Tuff thread, a send in flight at close could hang the program.
- **Backpressure:** `frame()` waits only if Python is more than `max_ahead = 2` batches ahead of the page. If the page falls behind, Python slows to its pace instead of piling up latency.
- **Closing:** pywebview's `closing` event (on the GUI thread, before the window goes) marks the view closed and queues the `close` event. While a close handler is registered, the window waits there for it, at most `CLOSE_GRACE` (2 s), because Cmd+Q on a Mac, or logging off Windows, ends the process as soon as the window is gone.
  - **No deadlock:** it doesn't wait while the Tuff thread is inside a call to the window (`resize`, `set_title`, `destroy`...: on Windows they wait for the GUI thread), and no new call starts once the window is closing.
  - **At any moment:** a window closed before its page was ready still gives a `View`, a closed one, so the program can register its handlers; the first `frame()` or `loop()` runs them. A close stuck in a batch that a handler waiting in `frame()` unwound (an atgui popup) is handled by `frame()`, `loop()` or `run()` on the way out. The close handlers run once.
- **The exit guard:** if one of pywebview's own threads is still stuck 2 s after the window closed, `run()` flushes the output and ends the process with `os._exit`. That covers pywebview's per-call threads, which aren't daemons. It never fired in testing.

### The bridge

**Python → page.** Changes collect in a buffer. Repeated `set()`s on one object in a frame merge into one, and other commands keep their order. `flush()` (called by `frame()` and `loop()`) turns the buffer into one JSON batch `[seq, [cmd, ...]]`. The sender thread sends all queued batches in one call:

```
window.run_js("__tv.apply([[seq, [cmd, ...]], ...])")      # a JS literal, no eval, no JSON.parse
["c", id, kind, type, parent, props|null]   create (kind: el, canvas, shape, scene, obj)
["s", id, props]                            set
["r", id]                                   remove (and everything inside it)
["k", id, method, args]                     call a method (id 0 = the window)
["k", id, method, args, tag]                ask: the page answers with a {type:"reply", tag, value, error} event
["j", code]                                 run JavaScript, in order, with `tv` = window.tuffView
```

- **Ids** are small integers chosen by Python, so nothing waits for an answer to create something.
- **The page applies a batch as soon as it arrives.** Drawing happens at the next animation frame.
- **When a command needs three.js** before it has loaded, the rest of the queue waits for it. Order is kept.
- **A command that fails** sends an `error` event. It's reported once, and the batch goes on.
- **An object that couldn't be made** (a 3D scene without WebGL, an unknown kind): commands for it, and for what goes inside it, are skipped quietly, so its one error isn't buried under a "there's no object N" for each of them.
- **A 2D shape that can't be drawn** is reported once and skipped; the shapes after it are still drawn. A circle's negative radius draws nothing.

**Page → Python.**

- **One handshake:** `pywebview.api.ready({w, h, dpr, webgl, ua})`. `View()` blocks until it arrives (at most 30 s).
- **Events:** after that, every send is `pywebview.api.ev(seq, [event, ...])`.
- **Out-of-order calls:** pywebview runs each call on a new thread, so calls can arrive out of order. Python puts them back in order by `seq`.
- **What's sent when:** clicks, keys, typing and custom events go in the same JS task (one call per task). Mouse movement, wheel and resize are merged and sent once per animation frame. Mouse movement keeps the latest x/y and the summed `dx`/`dy`, for mouse look.
- **Where events wait:** in a queue until the Tuff thread collects them in `frame()` or `loop()`. Replies to `ask()` skip that queue.

**Files.**

- **What's served:** `tuff_view_web/` and the program's `assets` folder, from `http://127.0.0.1:<random port>/<random token>/`.
- **Who can read them:** requests need the token and a `127.0.0.1`/`localhost` Host header, and nothing outside those two folders is served.
- **Why a real http address:**
  - Chromium won't load ES modules (three.js 0.186 is ESM only) from `file://`.
  - An image loaded from `file://` can't become a WebGL texture.
  - pywebview's own server (bottle) only serves one folder.
- **WebView2 profile:** each run gets a fresh, private profile folder under `%TEMP%\tuff-view`. pywebview deletes it on close. When a browser process still holds a file, the next program sweeps the folder.

### The scene (all in `engine.js`)

| kind | parent | properties |
| --- | --- | --- |
| `el` (type = tag) | an `el` or 0 (the window) | `text`, `html`, `class` (Python `cls`), `style` (dict, merged, or a CSS string), `attrs`, `show`, `before` (create only), and any DOM property (`value`, `checked`, `disabled`, `src`, `placeholder`, `type`, `id`...) |
| `canvas` | an `el` or 0 | `bg`, `cx`/`cy` (world point at the top-left), `zoom`, `fit: [w, h]` (letterboxed logical size), `smooth` (false for pixel art), plus `el` properties. Fills its parent by default. |
| `shape` (2D) | a `canvas` | `rect` (`w h radius`), `circle` (`r`), `ellipse` (`w h`), `line`/`poly` (`points lw stroke`), `text` (`text size font bold`), `image` (`src w h frame=[sx,sy,sw,sh]`). All: `x y z rot sx sy scale alpha ax ay color stroke lw visible pick nudge` (`[dx, dy]`: drawn that far from `x, y` without moving it there). `x, y` is the centre by default (`ax = ay = 0.5`); text defaults to its top-left corner. |
| `scene` (3D) | an `el` or 0 | `bg`, `fog: [color, near, far]`, `fov near far`, camera `cx cy cz yaw pitch roll` (degrees; yaw 0 looks down −z, positive turns left), `look: [x,y,z]`, `shadows`, `lighting` (`simple`, the default, or `modern`: ACES filmic tone mapping, an environment map made from the sky with PMREM, a softer hemisphere light, sun shadows that follow the camera; a graphics failure falls back to simple quietly) |
| `obj` (3D) | a `scene` or an `obj` | `box` (`w h d`), `sphere` (`r seg`), `plane` (`w h`), `cylinder` (`r` or `rt rb`, `h seg`), `cone`, `torus` (`r tube`), `capsule`, `group`, lights `ambient`, `hemi` (`ground`), `sun` (`shadow area`), `point` (`distance`). All: `x y z rx ry rz sx sy sz scale visible pick look shadow camera` (true = attached to the camera, for a held axe). Material: `color opacity emissive rough metal wireframe flat mat` (`standard`, `lambert`, `phong`, `toon`, `basic`) and `texture repeat side`. Lights: `color intensity`. |
| `obj` `terrain` | a `scene` | Land: `size` (metres across, centred on its position), `n` (points along a side), `heights` (n × n, row by row from −z to +z, each row from −x to +x), `style` (`grass desert snow rocky autumn`), `shadow`. Vertex colours by height, slope and the water near it, times a soft grain texture; earth sides and scenery land past its edges (not pickable). New heights update only the rows that changed. Picking walks the heightfield (fast enough for a brush) |
| `obj` `water` | a `scene` | `y` (its level), `r` (a lake's radius; 0 = a sea, `size` across), `color opacity`. Slightly see-through; with modern lighting it reflects the sky |

- **The page draws every animation frame,** but only canvases and scenes that changed.
- **Shared geometry:** meshes of the same size share one geometry.
- **Image and texture caches:** images and textures are cached by URL, and the scene redraws when one finishes loading.

Methods (`call`/`ask`):

| On | Method |
| --- | --- |
| Elements | any DOM method (`focus`, `select`, `scrollIntoView`, `getBoundingClientRect` via `ask`...), plus `move(parent, before)` |
| Canvas | `pick(x, y)` |
| Scene | `pick(x?, y?)` gives `{id, point, dist, path}`; with no point it picks the middle of the view, like a crosshair |
| Scene | `project(x, y, z)` gives the screen `[x, y]` |
| Scene | `lock` (pointer lock) |
| Window (id 0) | `css(text)`, `cursor(value)`, `unlock`, `stats(reset)` |

### Events (dicts; `type` plus these fields)

| type | fields |
| --- | --- |
| `click` `dblclick` `mousedown` `mouseup` | `id` (the nearest object), `path` (that object, then its parents), `x y` (window CSS px), `button`, `shift ctrl alt meta`. Over a canvas also `cx cy` (world). Over a scene, the hit object leads `path`, plus `point dist`. |
| `mousemove` | `x y dx dy` (merged per animation frame) |
| `wheel` | `dx dy x y path` |
| `keydown` / `keyup` | `key code` (+ `repeat` and `typing` on keydown: true when the key went to a text box, not a checkbox or slider), `shift ctrl alt meta` |
| `input` / `change` | `id path value` (checkboxes: true/false) |
| `submit` | `id path` |
| `resize` | `w h` |
| `focus` / `blur` | none. `blur` also releases every held key and button. |
| `lock` | `locked` |
| `close` | none |
| `error` | `message where stack`. Errors also go to `on_error`, once each. |
| anything else | whatever custom page JS emits with `tv.emit(type, data)` |

## The Python API, for wave 2

```python
import tuff_view as tv

tv.run(main, *args)            # main thread only; runs main on the Tuff thread; returns its value
                               #   (None if it ended because the window closed); re-raises its errors
tv.View(title="Tuff", width=900, height=600, icon=None, resizable=True, frameless=False, fps=60,
        background="#0b0e14", assets=None, on_error=None, debug=False, **options)
    # icon: .png or .ico (Windows); default TUFF_APP_ICON, else the Tuff dots icon
    # assets: folder served to the page (view.url(path) gives a file's address)
    # on_error(exc, where): called once per distinct error; default prints a traceback to stderr
    # **options: passed to webview.create_window (on_top, min_size, x, y, hidden, focus, text_select...)
    # Raises ViewError: outside run(), a second window, no WebView2 (with the download link),
    #   no pywebview, or the page not starting within 30 s.
    # Closed before its page was ready, it still comes back (is_open False): the first frame() or loop()
    #   runs the close handlers registered by then.

# scene (Tuff thread)
view.create(kind, type_=None, parent=0, **props) -> Node   # Node is an int (its id) with methods
view.el(tag, parent=0, **props)   view.canvas(parent=0, **props)   view.shape(canvas, type_, **props)
view.scene(parent=0, **props)     view.obj(parent, type_, **props)
view.set(id, **props)    view.remove(id)    view.call(id, method, *args)
view.ask(id, method, *args, timeout=5.0) -> value     # sends now, waits ~1 ms; ViewError if it failed
view.js(code)            view.url(path)     view.flush()
node.set(**props)  node.call(...)  node.ask(...)  node.on(type, fn)  node.remove()

# input
view.on(type, fn, id=None)   # fn(event); with an id: that object and what's inside it (nearest handler wins)
view.every_frame(fn)         # fn(dt), in loop()
view.events()                # this frame's events (pygame style)
view.key_down("w" | "KeyW" | "space" | "up" | "Enter")    view.mouse_down(0 | "left")
view.mouse_delta() -> (dx, dy) since the last call       view.mouse, view.buttons, view.size, view.values, view.info

# loops
view.frame() -> dt   # flush, pace to view.fps, collect input; raises ViewClosed once the window has closed
view.loop()          # callback style until the window closes; events handled the moment they arrive
view.fps = 30        # 0 = unpaced;  view.max_ahead = 2

# window
view.is_open  view.set_title(t)  view.resize(w, h)  view.move(x, y)  view.minimize()  view.maximize()
view.restore()  view.fullscreen()  view.close()  view.page_stats(reset=False)  view.stats
view.page_png()      # tests: a PNG of the whole page, elements too (WebView2's DevTools screenshot; None elsewhere)
tv.ViewError, tv.ViewClosed (a BaseException), tv.FAILED, tv.WEB_DIR
```

**Errors:**

- **Reported once:** an error is reported once for the same place and the same message, through `on_error`.
- **Every-frame functions:** one that fails is switched off, like tgui's `:every`.
- **Event handlers:** they stay on, but a repeat of the same error isn't reported again.
- **`FAILED`:** a callback can return `tuff_view.FAILED` to say "I already reported my error". That's what wrapping the Runtime's `rt.call` needs.

### Wiring it into Tuff (wave 2; I didn't touch tuff.py)

1. **Run the program on the Tuff thread.** When it imports `atgui` or `tgame`, `tuff.py` has to run the program inside `tuff_view.run`.
   - The detection can be the same regex `build.js` uses: `^\s*(import|mention)\s+(atgui|tgame)\b`.
   - For example, in `main()`: `code = tuff_view.run(run_file, path) if uses_view else run_file(path)`.
   - `ViewClosed` is a `BaseException`, so `call_python`'s `except Exception` and `rt.call` let it through. `run()` turns it into `None`, which `sys.exit` treats as 0.
   - Ctrl+C now arrives on the main thread, inside `run()`, not in `run_file`. Catch `KeyboardInterrupt` around `tuff_view.run` and return 130, as `run_file` does today.
2. **The library:**
   - Open with `View(..., assets=interp.base_dir, on_error=...)`. `on_error` should call `report()` on a `TuffError`.
   - Register `rt.on_finish(view.loop)`. A program that only sets up handlers then stays alive until its window closes, like tgui's `mainloop` finish hook.
   - Wrap Tuff functions so they raise `TuffError`, or use `lambda e: None if rt.call(fn, ev)[0] else tuff_view.FAILED`.
   - Turn event dicts into Tuff data objects.
3. **Build exe (`build.js`)** for programs that use `atgui` or `tgame`:
   - Ship `tuff_view.py` and `tuff_view_web/` with the runtime files.
   - Add `--add-data <runtime>/tuff_view_web;tuff_view_web` and `--hidden-import tuff_view`.
   - Make sure the build Python has pywebview (`pip install pywebview` next to `pyinstaller`).
   - **No other hidden imports are needed** (see below). Windowed by default.
4. **Running from the IDE:** the user's Python needs pywebview too. With it missing, `View()` raises "App and game windows need pywebview. Install it with:  py -m pip install pywebview" (`python3 -m pip ...` on a Mac). The IDE may want to install it on first use, like the build tools.

## Packaging proof (step 5)

`freeze.py` builds `view_3d_test.py` like this:

```
py -3 -m PyInstaller --onefile --windowed --name tuff_view_3d --paths <repo> --paths tuffcode/test/view
    --add-data "<repo>/tuff_view_web;tuff_view_web" tuffcode/test/view/view_3d_test.py
```

Then it runs the .exe, with no console, writing its result with `--out`.

**Result: the frozen test passed 9/9.**
- It held 59.7 fps, with 20/20 clicks and 10/10 crosshair picks.
- It passed again when started from outside the repo.
- The build took 9.6 s.

| | Size |
| --- | --- |
| `tuff_view_3d.exe` | **11.76 MB** |
| An empty `--onefile --windowed` program | 6.97 MB |
| Added by pywebview, pythonnet and `tuff_view_web` | **+4.8 MB** |

The biggest additions, compressed:

| Part | Compressed size |
| --- | --- |
| OpenSSL | ~2.1 MB. pywebview's `http.py` imports `ssl` at the top, so it can't be excluded. |
| three.js | 0.4 MB |
| pythonnet's `Python.Runtime.dll` | 0.18 MB |
| `Microsoft.Web.WebView2.Core.dll` | 0.13 MB |
| `WebView2Loader.dll` for x64, x86 and arm64 | 0.07 MB each |
| bottle, cffi and the rest | the remainder |

**Hidden imports needed: none** (PyInstaller 6.22.3 with pyinstaller-hooks-contrib 2026.8). Three hooks cover everything:
- pywebview's own hook (`webview/__pyinstaller`) collects its DLLs and its JS.
- hooks-contrib's `hook-clr` collects `Python.Runtime.dll`.
- `hook-clr_loader` collects `ClrLoader.dll`.

The "missing module System.*" lines in PyInstaller's warnings are .NET namespaces that pythonnet loads at run time, and are harmless.

**On the user's PC (Windows)** the app needs:
- the .NET Framework 4.6.2 or later (built into Windows 10 and 11);
- the Edge **WebView2 Runtime**. It's evergreen and built into Windows 11. Windows 10 normally has it through Edge updates.
- Without WebView2, `View()` raises a clear error with the link https://go.microsoft.com/fwlink/p/?LinkId=2124703.

**Mac (not tried: no Mac here).**
- **Packages:** pywebview needs `pyobjc-core`, `pyobjc-framework-Cocoa`, `-WebKit`, `-Quartz`, `-Security` and `-UniformTypeIdentifiers`.
- **Building:** pywebview's docs suggest py2app. PyInstaller `--windowed` makes a `.app` too. Whether it needs extra hidden imports for PyObjC is untested.
- **Signing:** PyInstaller ad-hoc signs (`codesign -s -`) what it builds on macOS, which Apple Silicon needs. TuffCode's existing Mac signature check should cover it. Re-sign ad hoc if anything is changed after the build.
- **Loading the page:** WKWebView would block `http://127.0.0.1` through App Transport Security. pywebview's Cocoa backend sets `NSAllowsArbitraryLoads` in the running bundle's Info.plist, so the local server works without a custom Info.plist.
- **Closing on a Mac:**
  - The last window closing stops the app loop and `start()` returns, as on Windows.
  - **Cmd+Q terminates the process outright** (pywebview's `applicationShouldTerminate_`, then `exit()`). It fires `closing` first, and the window waits there for the close handlers, so they should have run. Not tried on a Mac; on Windows, ending the process the moment the window has gone shows they have.
- **What the code skips on a Mac:** the `.ico`/`.png` window icon, the profile folder and the 1 ms timer code are Windows only. A Mac has no per-window icons, and the Dock icon comes from the `.app`.

## Research notes (pywebview 6.2.1, read from its docs and source)

- **Threads:**
  - `webview.start()` raises unless it's called on the thread named MainThread.
  - On Windows, `start()` creates the WinForms app on a new .NET STA thread, and the main thread waits on it.
  - On a Mac, `NSApp.run()` runs on the main thread.
  - `js_api` and `expose` calls each run on a **new, non-daemon `threading.Thread`**. The docs say "executed in separate threads and are not thread-safe". After the function returns, pywebview resolves the JS promise with another `evaluate_js`.
  - Window events (`closed`, `loaded`, `resized`...) also get a thread each.
  - `closing`, `before_show`, `before_load` and `initialized` run on the GUI thread and can return False to cancel.
- **`evaluate_js` vs `run_js`:**
  - `evaluate_js` wraps the script in `eval("<escaped string>")` plus `JSON.stringify` of the result, and blocks the caller until the page ran it. On Windows that means an `Invoke` onto the UI thread, `ExecuteScriptAsync`, and a semaphore.
  - `run_js` skips the wrapper. On Windows it still blocks for the result.
  - Costs are in the table above.
- **Local files:**
  - A relative URL makes pywebview start its bottle server.
  - `file://` is "possible but discouraged" in the docs.
  - Chromium blocks ES modules and WebGL textures from `file://`, hence our own server.
- **No WebView2:**
  - pywebview's `_is_chromium()` looks for the EdgeUpdate client keys (runtime, beta, dev, canary; at least 86.0.622) and .NET 4.6.2.
  - Failing that, it falls back to **MSHTML (IE11)** with a deprecation warning. That fallback also writes `FEATURE_BROWSER_EMULATION` and `FEATURE_96DPI_PIXEL` for the exe under `HKCU\Software\Microsoft\Internet Explorer\Main\FeatureControl`.
  - `tuff_view` checks the same keys **before** pywebview loads its Windows backend and raises its own error, so neither the IE window nor the registry write happens. It also refuses an `mshtml` or `cef` renderer in the `initialized` event.
  - A fixed-version runtime (`webview.settings["WEBVIEW2_RUNTIME_PATH"]`) skips the check.
  - Tested by faking a missing runtime, not by uninstalling it.
- **Private mode:**
  - `private_mode=True` (the default) gives each run a throwaway profile, so `localStorage` and cookies don't persist.
  - The origin's port changes every run anyway. If atgui wants saved settings, they belong in a file on the Python side.

## Not done, or worth knowing

- **One window per program** for now. A second `View()` raises `ViewError`. Dialogs can be in-page HTML.
- **No veto of the X button.** `closing` can't be vetoed from Tuff code: a program can react to `close`, but not cancel it. A cross-thread veto risked deadlocks. The window only waits (at most 2 s) for the close handlers to finish.
- **Smoothing:** the page draws at the display rate (~132 Hz here), but it shows Python's positions as they arrive, 60 times a second. There's no interpolation between frames yet. If motion looks steppy on high-refresh screens, an opt-in `smooth` on canvases and scenes (lerp `x y z rot` over one Python frame, adding ~16 ms of delay) is the next step.
- **No packed bulk-move command.** It isn't needed at the targets: 5000 sprites still held 60 fps.
- **No glTF models** (would need three's `GLTFLoader` from `examples/jsm`) and **no audio**. Those are for wave 2 if tgame needs them.
- **Synthetic input:** the UI and 3D tests click and type with DOM events made in the page. The OS input layer was only exercised by the close test (a real WM_CLOSE) and the window test (real Win32 styles and icons).
- **A removed object:** setting a property on an object after removing it reports one error ("there's no object N"). Python doesn't silently drop it. (tgame's sprites and objects don't send anything once removed.) `remove()` forgets the id everywhere in Python, so making and removing objects all day doesn't grow its bookkeeping.
- **Space and the arrow keys** don't scroll the page or press a focused button, since games play with them. An app turns that off from its page JS with `tv.gameKeys = false`, as atgui does, so Space presses its buttons and the arrows scroll.
- **A covered or minimized window** stops drawing (Chromium pauses animation frames). Python keeps running and the page should keep applying batches, so it catches up when shown. This wasn't measured.
- **Ctrl+C:** pywebview swaps in its own Ctrl+C handler while the window is open, which closes the window. `tuff_view` puts the old handler back afterwards.
- **What pywebview installs** (`py -3 -m pip install --user pywebview`): pywebview 6.2.1, pythonnet 3.2.1, clr_loader 0.3.1, cffi 2.1.1, pycparser 3.11, bottle 0.13.4, proxy_tools 0.1.0 and typing_extensions 4.16.0. That's 5.4 MB in the user site-packages. pywebview's 2.4 MB of that includes the WebView2 DLLs and an Android jar.
- **three.js** is the npm package `three` 0.186.1: `build/three.module.js` and `build/three.core.js`, 2.1 MB unminified, with its MIT `LICENSE` in `tuff_view_web/three/`. The tarball's sha512 matched the registry's integrity value.
