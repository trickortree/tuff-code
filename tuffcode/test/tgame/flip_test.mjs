// The page's side of sprite sheets (tuff_view_web/flip.js), in Node with no window: a picture cut into 4 x 2
// frames shows the right part of the picture, an animation steps by the game's clock (and holds still while the
// canvas says the game is paused), one that plays once stays on its last frame, and a long gap is a short step.
// It prints what it saw as JSON; run_tests.py (t_frames) checks it.   Usage: node flip_test.mjs path/to/flip.js
import { pathToFileURL } from 'node:url';

const flip = await import(pathToFileURL(process.argv[2]).href);
const seen = {};
let paused = false;
const canvas = { el: { hasAttribute: (a) => a === 'data-paused' && paused }, dirty: false };
const img = { naturalWidth: 128, naturalHeight: 64 };  // 4 across and 2 down: each frame 32 x 32

// engine.js's setShape: the props go on the shape, then flip.js hears about them.
function set(s, props) {
  Object.assign(s.p, props);
  flip.changed(s, props);
}
let clock = 0;
function run(seconds) {  // frames at 60 a second, by the game's clock (ms)
  const steps = Math.round(seconds * 60);
  for (let i = 0; i < steps; i++) {
    clock += 1000 / 60;
    flip.step(clock);
  }
}

const hero = { id: 2, p: { src: 'hero.png', cells: null, cell: 1, play: null, frame: null }, host: canvas };
seen.whole = flip.rect(hero, img);  // not cut yet: all of it
set(hero, { cells: [4, 2], cell: 6, play: null });
seen.cell6 = flip.rect(hero, img);
seen.not_loaded = flip.rect(hero, null);
set(hero, { cell: 1, play: [[1, 2, 3, 4], 10, true] });
flip.step(clock);
seen.start = flip.shown(hero);
run(0.25);
seen.at_025 = flip.shown(hero);
seen.rect_025 = flip.rect(hero, img);
canvas.dirty = false;
paused = true;
run(0.5);
seen.paused = flip.shown(hero);
seen.dirty_while_paused = canvas.dirty;
paused = false;
run(0.2);  // 0.45 s of play: frame index 4, round to the start
seen.after_pause = flip.shown(hero);
set(hero, { play: [[5, 6, 7, 8], 20, false] });  // once
flip.step(clock);
seen.jump_start = flip.shown(hero);
run(0.1);
seen.jump_mid = flip.shown(hero);
run(0.3);
seen.jump_end = flip.shown(hero);
seen.playing_after_jump = flip.info().playing;
set(hero, { play: null, cell: 8 });  // what tgame sends when it ends
seen.after_end = flip.shown(hero);
set(hero, { play: [[1, 2, 3, 4], 10, true] });
flip.step(clock);
clock += 5000;  // a hidden window: the next frame comes 5 s later
flip.step(clock);
seen.after_gap = flip.shown(hero);
set(hero, { frame: [10, 20, 30, 40] });
seen.own_frame = flip.rect(hero, img);
set(hero, { frame: null });
const coin = { id: 3, p: { src: 'coin.png', cells: [2, 1], cell: 2, play: null, frame: null }, host: canvas };
set(coin, { cells: [2, 1], play: [[1, 2], 4, true] });
seen.info = flip.info();
coin.dead = true;
hero.dead = true;
flip.step(clock);
seen.info_gone = flip.info();
console.log(JSON.stringify(seen));
