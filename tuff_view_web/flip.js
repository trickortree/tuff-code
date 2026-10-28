// tgame's sprite sheets in the page: a picture cut into a grid of frames (sprite:frames), showing one of them, or
// playing an animation (sprite:play) that steps through its frames by itself, every frame, with no work for Python.
// An image shape's props say which: `cells` is [across, down] (null: the whole picture), `cell` the frame it shows,
// numbered from 1 (left to right, then the next row down), and `play` is [frames, frames a second, loop] while an
// animation plays (null when none does). One that plays once stays on its last frame.
//
// The steps go by the game's clock (fx.js's time(), which slow motion slows) and hold still while the game is paused
// (tgame puts data-paused on the canvas). Python goes by the same clock, so sprite:frame() and :on_done agree with
// what the page shows. engine.js calls changed() when a shape's props change, step() before it draws each frame,
// and rect() for the part of the picture to draw. Nothing here touches the page, so the tests run it in Node.

const playing = new Set();  // image shapes with an animation playing
const sheets = new Set();   // image shapes cut into frames (for info)

export function changed(s, props) {
  if ('cells' in props) {
    if (props.cells) sheets.add(s);
    else sheets.delete(s);
  }
  if (!('play' in props)) return;
  const play = props.play;
  if (play && play[0] && play[0].length) {
    s.flip = { t: 0, at: null, cell: play[0][0] };  // a new animation (or the same one again) starts at its first frame
    playing.add(s);
  } else {
    s.flip = null;
    playing.delete(s);
  }
}

// Every playing animation's frame for this moment: game is the game's clock, in ms. If it ever fails, it stops (the
// error goes out once) and the pictures stay on the frames they show.
let broken = false;

export function step(game) {
  if (broken) return;
  try {
    stepAll(game);
  } catch (err) {
    broken = true;
    throw err;
  }
}

function stepAll(game) {
  for (const s of playing) {
    const f = s.flip;
    const p = s.p;
    if (s.dead || !f || !p.play) { playing.delete(s); continue; }
    const host = s.host;
    const paused = !!(host && host.el && host.el.hasAttribute && host.el.hasAttribute('data-paused'));
    if (f.at !== null && !paused) f.t += Math.min(0.1, Math.max(0, (game - f.at) / 1000));  // a long gap is a short step
    f.at = game;
    const [frames, fps, loop] = p.play;
    const n = frames.length;
    const i = Math.floor(f.t * fps + 1e-6);
    const cell = frames[loop ? i % n : Math.min(i, n - 1)];
    if (cell !== f.cell) {
      f.cell = cell;
      if (host) host.dirty = true;
    }
    if (!loop && i >= n) playing.delete(s);  // played once: it stays on its last frame
  }
}

// The frame a shape shows now.
export function shown(s) {
  return s.flip ? s.flip.cell : s.p.cell;
}

// The part of the picture to draw, [x, y, width, height] in the picture's own pixels, or null for all of it: the
// shape's own `frame` if it has one, or the frame of its grid that it shows. img is the loaded picture (or null).
export function rect(s, img) {
  const p = s.p;
  if (p.frame) return p.frame;
  const g = p.cells;
  if (!g || !img || !img.naturalWidth) return null;
  const cols = Math.max(1, Math.floor(g[0]) || 1);
  const rows = Math.max(1, Math.floor(g[1]) || 1);
  const w = img.naturalWidth / cols;
  const h = img.naturalHeight / rows;
  const k = Math.min(cols * rows, Math.max(1, Math.floor(shown(s)) || 1)) - 1;
  return [(k % cols) * w, Math.floor(k / cols) * h, w, h];
}

// For the page's stats (the tests): how many play, and each sheet's id with the frame it shows.
export function info() {
  for (const s of sheets) if (s.dead) sheets.delete(s);
  return { playing: playing.size, shown: [...sheets].map((s) => [s.id, shown(s)]) };
}
