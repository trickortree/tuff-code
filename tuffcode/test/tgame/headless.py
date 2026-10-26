"""Runs a tgame program with no window, for tests that must not open one: tuff_view's Recorder stands in for the
game window, every frame is exactly 1/60 of a second of tgame's time, and what the program sent the page goes to a
JSON file (each frame's changes merged, as the page would get them, with ["f", n] where frame n ends).

    py -3 headless.py program.tuf out.json [frames] [events.json]

frames: close the game after this many frames (0 or left out: when the program closes it, or after a minute).
events.json: {"frame number": [events the page would send, like {"type": "keydown", "code": "Space"}], ...}.
The program's say lines go to stdout and its errors to stderr, as in a real run.
"""
import json
import os
import sys
import time
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, REPO)
import tuff  # noqa: E402
import tuff_tgame  # noqa: E402
import tuff_view  # noqa: E402

program, out = sys.argv[1], sys.argv[2]
last = int(sys.argv[3]) if len(sys.argv) > 3 and int(sys.argv[3]) > 0 else 3600
script = {}
if len(sys.argv) > 4:
    with open(sys.argv[4], encoding="utf-8") as f:
        script = {int(k): v for k, v in json.load(f).items()}

now = [0.0]  # tgame's clock: it moves on 1/60 of a second at each frame, however fast this runs
tuff_tgame.time = types.SimpleNamespace(perf_counter=lambda: now[0], monotonic=time.monotonic, sleep=time.sleep)
views = []


class Headless(tuff_view.Recorder):
    """The game window, without one."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frames = 0
        views.append(self)

    def frame(self):
        if self._sets:
            self._move_sets()
        self._cmds.append(["f", self.frames])
        self.frames += 1
        now[0] += 1 / 60
        self._frame_events = script.get(self.frames, [])
        if self.frames >= last:
            self._closed = True
        return 0.0


tuff_view.View = Headless
tuff.setup_streams()
code = tuff.run_file(program)
with open(out, "w", encoding="utf-8") as f:
    json.dump(views[0].record() if views else [], f)
sys.exit(code)
