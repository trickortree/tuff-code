// Tuff Engine's preview page on its own, before the tab: tuff.py --scene through the engine:scene IPC, and the host
// page (renderer/engine-host, served from tuffview://) in an iframe of the real IDE. It loads a 2D game and a 3D world,
// draws them with the real engine, answers picks made with real mouse clicks, reports drags (2D and 3D), orbits and
// zooms the 3D camera, keeps one WebGL context from one 3D load to the next, and serves only what it should.
import fs from 'node:fs';
import path from 'node:path';
import { REPO } from '../launch.mjs';

export const meta = { title: 'Tuff Engine: the preview page (tuffview://, engine:scene, picking and dragging)', timeout: 240000 };

const GAME_2D = `mention tgame

game = tgame.window("Coin Dash", 800, 600)
game:background "navy"
score = 0
score_label = game:text("Score: 0", 400, 30, 24, "white")
player = game:box(400, 520, 50, 50, "lime")
coin = game:circle(200, 200, 14, "gold")
enemy = game:box(100, 80, 40, 40, "red")
pic = game:image("sprites/star.png", 700, 500, 96)
for i in range(1, 3):
    game:box(500 + i * 60, 150, 30, 30, "orange")
hud = game:hud()
lives = hud:text("Lives: 3", 90, 570, 22, "white")
say "this never shows"

while game:open():
    game:frame()
`;

const GAME_3D = `mention tgame

game = tgame.world("Island Walk", 960, 600)
game:sky "day"
game:island(80)
hud = game:hud()
score_label = hud:text("Score: 0", 90, 30, 26, "white")
player = game:player("first person")
axe = player:hold("axe")
coin = game:spawn("coin", 4, 0, -8)
tree = game:spawn("tree", -5, 0, -10)
hut = game:spawn("hut", 8, 0, -16)
enemy = game:box(-12, 0, -20, 1, "red")
crate = game:box(0, 0, -4, 2, "wood")
`;

// The IDE page's side: an iframe on top of everything, a log of what it posts, and helpers.
const SETUP = (x, y) => `(() => {
  if (window.__eh) return 1;
  const f = document.createElement('iframe');
  f.src = 'tuffview://app/host/index.html';
  Object.assign(f.style, { position: 'fixed', left: '${x}px', top: '${y}px', width: '800px', height: '600px', border: '0', zIndex: 99999, background: '#202124' });
  const eh = window.__eh = { msgs: [], f };
  addEventListener('message', (e) => { if (e.source === f.contentWindow && e.data && e.data.tuffHost) eh.msgs.push(e.data); });
  eh.post = (m) => f.contentWindow.postMessage(m, '*');
  let tags = 0;
  eh.ask = (what, extra = {}) => new Promise((resolve) => {
    const tag = 'ask' + ++tags;
    eh.post({ tuffHost: 'ask', tag, what, ...extra });
    const t0 = Date.now();
    const iv = setInterval(() => {
      const m = eh.msgs.find((x) => x.tuffHost === 'reply' && x.tag === tag);
      if (m || Date.now() - t0 > 10000) { clearInterval(iv); resolve(m ? { value: m.value, error: m.error } : { error: 'no reply' }); }
    }, 25);
  });
  // The colors of a snapshot (a data: URL of the preview) at points given in the frame's CSS pixels.
  eh.colors = async (url, pts) => {
    const img = new Image();
    img.src = url;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0);
    const k = img.width / f.clientWidth;
    return pts.map(([px, py]) => [...g.getImageData(Math.round(px * k), Math.round(py * k), 1, 1).data].slice(0, 3));
  };
  document.body.append(f);
  return 1;
})()`;

export default async (t, ctx) => {
  const ev = (js) => t.eval(js);
  const check = (ok, label, got) => t.check(label, ok, got);
  const FX = 120;
  const FY = 90;  // where the frame sits in the IDE window
  fs.mkdirSync(path.join(ctx.root, 'sprites'), { recursive: true });
  fs.copyFileSync(path.join(REPO, 'tuffcode', 'test', 'tgame', 'games', 'star.png'), path.join(ctx.root, 'sprites', 'star.png'));
  const file2d = path.join(ctx.root, 'coin_dash.tuf');
  const file3d = path.join(ctx.root, 'island_walk.tuf');
  fs.writeFileSync(file2d, GAME_2D);
  fs.writeFileSync(file3d, GAME_3D);

  // ---- engine:scene (tuff.py --scene) through the preload API
  const scene = async (file, code) => ev(`window.tuff.engine.scene(${JSON.stringify(file)}, ${JSON.stringify(code)})`);
  const d2 = await scene(file2d, GAME_2D);
  check(d2 && d2.mode === '2d' && d2.stopped === 'loop' && d2.things?.length === 9 && typeof d2.ms === 'number',
    `engine:scene gives the 2D dump: 9 things, stopped at the loop (${d2?.ms} ms)`, { mode: d2?.mode, stopped: d2?.stopped, n: d2?.things?.length, error: d2?.error, message: d2?.message });
  const imgCmd = (d2?.batch || []).find((c) => c[0] === 'c' && c[3] === 'image');
  check(imgCmd && imgCmd[5].src === 'asset:sprites/star.png', 'pictures come as asset:<path from the game folder>', imgCmd);
  const unsaved = await scene(file2d, GAME_2D.replace('"Coin Dash"', '"Not saved yet"'));
  check(unsaved.title === 'Not saved yet', "it runs the editor's text, not the file on disk", unsaved.title);
  const [a, b] = await Promise.all([scene(file2d, GAME_2D), scene(file2d, GAME_2D)]);
  check(a.superseded === true && b.mode === '2d', 'a newer request stops the one still running (it says superseded)', { a: Object.keys(a), b: b.mode });
  const slow = await scene(file2d, 'mention tgame\nwhile true:\n    x = 1\n');
  check(slow.stopped === 'timeout' && slow.ms >= 4900 && slow.ms < 9000, `a setup that never ends stops after 5 s (${slow.ms} ms)`, slow);
  const d3 = await scene(file3d, GAME_3D);
  check(d3.mode === '3d' && d3.stopped === 'end' && d3.player?.held?.name === 'axe' && d3.things?.length === 7,
    `engine:scene gives the 3D dump: the island, the HUD text, 5 objects, the player and the axe (${d3.ms} ms)`, { stopped: d3.stopped, n: d3.things?.length, error: d3.error });

  // ---- the host page in an iframe of the IDE
  await ev(SETUP(FX, FY));
  const waitMsg = (pred, ms = 15000) => t.waitFor(`window.__eh.msgs.some((m) => ${pred})`, ms);
  const msgs = (pred) => ev(`window.__eh.msgs.filter((m) => ${pred})`);
  const clear = () => ev('window.__eh.msgs.length = 0');
  const ready = await waitMsg(`m.tuffHost === 'ready'`);
  const readyMsg = (await msgs(`m.tuffHost === 'ready'`))[0];
  check(ready && typeof readyMsg?.webgl === 'boolean', `the host page loads from tuffview://app/host/ and says ready (WebGL: ${readyMsg?.webgl ? 'yes' : 'no'})`, readyMsg);
  const ask = (what, extra = {}) => ev(`window.__eh.ask(${JSON.stringify(what)}, ${JSON.stringify(extra)})`);
  const thing = (d, v) => d.things.find((x) => x.var === v);

  // What the scheme serves, and what it doesn't.
  const fetches = {};
  for (const [name, url] of Object.entries({
    engine: 'tuffview://app/engine/engine.js', three: 'tuffview://app/engine/three/three.module.js', host: 'tuffview://app/host/host.js',
    picture: 'tuffview://app/project/sprites/star.png', code: 'tuffview://app/project/coin_dash.tuf', up: 'tuffview://app/project/%2e%2e/%2e%2e/tuff.py',
    upEngine: 'tuffview://app/engine/..%2f..%2ftuff.py', other: 'tuffview://app/nothing/x.png' })) fetches[name] = (await ask('fetch', { url })).value;
  check(fetches.engine?.status === 200 && /javascript/.test(fetches.engine.type) && fetches.three?.status === 200 && fetches.host?.status === 200,
    'tuffview://app/ serves the engine, three.js and the host page', fetches);
  check(fetches.picture?.status === 200 && fetches.picture.type === 'image/png', 'and pictures in the open project', fetches.picture);
  check(fetches.code?.status === 404 && fetches.up?.status === 404 && fetches.upEngine?.status === 404 && fetches.other?.status === 404,
    'but not code files, nothing outside its folders, and no other areas', { code: fetches.code, up: fetches.up, upEngine: fetches.upEngine, other: fetches.other });

  // ---- 2D: load, draw, pick, drag
  const forLoad = (d) => {
    const copy = JSON.parse(JSON.stringify(d));
    for (const x of copy.things) if (x.made.length !== 1) x.drag = null;   // what the tab does for things made by loops
    return copy;
  };
  const load = async (d, seq, extra = {}) => {
    await clear();
    await ev(`window.__eh.post({ ...${JSON.stringify(forLoad(d))}, tuffHost: 'load', seq: ${seq}, gameDirRel: '', assetEpoch: 1, ...${JSON.stringify(extra)} })`);
    return waitMsg(`m.tuffHost === 'loaded' && m.seq === ${seq}`, 20000);
  };
  check(await load(d2, 1), 'the 2D dump loads (loaded)', await msgs(`m.tuffHost === 'error'`));
  await t.sleep(400);
  const errs = await msgs(`m.tuffHost === 'error'`);
  check(!errs.length, 'with no engine errors (the picture loads through tuffview://app/project/)', errs);
  let stats = (await ask('stats')).value;
  check(stats?.mode === '2d' && stats.sceneBg === '#1e3a8a' && stats.things === 9 && stats.b === 1e6,
    'the 2D game is in the engine: a navy canvas, 9 things, ids moved up by 1,000,000', stats);
  const coin = thing(d2, 'coin');
  const player = thing(d2, 'player');
  const shot = (await ask('snapshot')).value;
  const cols = await ev(`window.__eh.colors(${JSON.stringify(shot)}, [[760, 300], [200, 200], [400, 520], [700, 500]])`);
  const near = (c, hex, tol = 40) => { const n = parseInt(hex.slice(1), 16); return Math.abs(c[0] - (n >> 16)) + Math.abs(c[1] - ((n >> 8) & 255)) + Math.abs(c[2] - (n & 255)) <= tol; };
  check(near(cols[0], '#1e3a8a') && near(cols[1], '#f2c230') && near(cols[2], '#84cc16') && !near(cols[3], '#1e3a8a', 60),
    "the engine drew it: navy background, the gold coin, the lime player and the star picture where they are", cols);
  await t.shot('engine_host_2d.png', { x: FX, y: FY, width: 800, height: 600 });

  const screen = async (i) => (await ask('screen', { i })).value;
  const press = (x, y) => t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 });
  const moveTo = async (x0, y0, x1, y1, steps = 10) => {
    for (let s = 1; s <= steps; s++) await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x0 + ((x1 - x0) * s) / steps, y: y0 + ((y1 - y0) * s) / steps, button: 'left', buttons: 1 });
  };
  const release = (x, y) => t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1 });

  const [cx, cy] = await screen(coin.i);
  check(Math.abs(cx - 200) < 1 && Math.abs(cy - 200) < 1, 'the coin is at (200, 200) on screen (the frame is the game size)', [cx, cy]);
  await clear();
  await t.click(FX + cx, FY + cy);
  check(await waitMsg(`m.tuffHost === 'pick' && m.i === ${coin.i}`), 'a real click on the coin picks it (pick with its index)', await msgs('true'));
  check((await msgs(`m.tuffHost === 'focus'`)).length >= 1, 'and the page asks for focus back after the click', null);
  await clear();
  await t.move(FX + cx, FY + cy);
  await press(FX + cx, FY + cy);
  await moveTo(FX + cx, FY + cy, FX + cx + 100, FY + cy + 50);
  const live = (await ask('pos', { i: coin.i })).value;
  check(live && live.x === 300 && live.y === 250, 'dragging moves the coin live in the preview', live);
  await release(FX + cx + 100, FY + cy + 50);
  check(await waitMsg(`m.tuffHost === 'drag' && m.phase === 'end'`), 'releasing reports the drag', await msgs('true'));
  const drag = (await msgs(`m.tuffHost === 'drag'`))[0];
  check(drag && drag.i === coin.i && drag.dx === 100 && drag.dy === 50 && drag.alt === false, 'drag end: the coin, dx 100, dy 50 (game units)', drag);

  // Escape during a drag puts it back.
  const [px, py] = await screen(player.i);
  await clear();
  await t.move(FX + px, FY + py);
  await press(FX + px, FY + py);
  await moveTo(FX + px, FY + py, FX + px - 80, FY + py - 40, 6);
  await t.key('Escape');
  await release(FX + px - 80, FY + py - 40);
  await t.sleep(200);
  const back = (await ask('pos', { i: player.i })).value;
  const dragMsgs = await msgs(`m.tuffHost === 'drag'`);
  check(back?.x === 400 && back?.y === 520 && dragMsgs.length === 1 && dragMsgs[0].phase === 'cancel', 'Escape during a drag puts the player back (drag cancel, no end)', { back, dragMsgs });

  // A thing made by a loop: picked, but it doesn't move.
  const loopBox = d2.things.find((x) => x.made.length > 1);
  const [lx, ly] = await screen(loopBox.i);
  await clear();
  await t.move(FX + lx, FY + ly);
  await press(FX + lx, FY + ly);
  await moveTo(FX + lx, FY + ly, FX + lx + 60, FY + ly + 60, 6);
  await release(FX + lx + 60, FY + ly + 60);
  await t.sleep(150);
  const loopPos = (await ask('pos', { i: loopBox.i })).value;
  check((await msgs(`m.tuffHost === 'pick' && m.i === ${loopBox.i}`)).length === 1 && !(await msgs(`m.tuffHost === 'drag'`)).length && loopPos.x === loopBox.x,
    'a box made by a for loop is picked but not dragged', { loopPos, msgs: await msgs('true') });

  // The HUD is on top; empty space picks nothing; keys come back to the parent.
  const lives = thing(d2, 'lives');
  const [hx, hy] = await screen(lives.i);
  await clear();
  await t.click(FX + hx, FY + hy);
  check(await waitMsg(`m.tuffHost === 'pick' && m.i === ${lives.i}`), 'a click on the HUD text picks it', await msgs('true'));
  await clear();
  await t.click(FX + 300, FY + 400);
  check(await waitMsg(`m.tuffHost === 'pick' && m.i === null`), 'a click on empty space picks nothing (i: null)', await msgs('true'));
  await clear();
  await t.key('Delete');
  check(await waitMsg(`m.tuffHost === 'key' && m.key === 'Delete'`), 'a key pressed in the preview is sent to the parent', await msgs('true'));
  await ev(`window.__eh.post({ tuffHost: 'select', is: [${coin.i}] })`);
  await t.sleep(150);
  stats = (await ask('stats')).value;
  check(stats.sel2d === true && stats.sel.length === 1, 'select shows the 2D selection box', stats);
  await t.shot('engine_host_2d_selected.png', { x: FX, y: FY, width: 800, height: 600 });

  // A computer without WebGL (GitHub's Intel Macs) can't draw 3D: Tuff Engine says so (engine.mjs checks that).
  if (!readyMsg?.webgl) { t.info('No WebGL here, so the 3D checks are skipped; 2D was checked above.'); return; }

  // ---- 3D: load in a 960 x 600 frame shape, draw, pick, drag, orbit, zoom
  await ev(`Object.assign(window.__eh.f.style, { width: '800px', height: '500px' })`);
  check(await load(d3, 2, { cam: null }), 'the 3D dump loads (loaded)', await msgs(`m.tuffHost === 'error'`));
  await t.sleep(700);
  stats = (await ask('stats')).value;
  check(stats.mode === '3d' && stats.sceneBg === '#bfe2ff' && stats.marker === true && stats.cameraNodesVisible === false && stats.b === 2e6,
    "the 3D world is in the engine: the day sky, the player's start marker, the held axe hidden from the editor camera", stats);
  const fitted = (await msgs(`m.tuffHost === 'cam'`)).pop();
  check(fitted && Math.abs(fitted.tx - -2) < 0.01 && Math.abs(fitted.tz - -10) < 0.01 && fitted.el === 35 && fitted.dist > 12,
    'the camera is fitted around the world, and posted (cam)', fitted);
  const crate = thing(d3, 'crate');
  const shot3 = (await ask('snapshot')).value;
  const [sx, sy] = await screen(crate.i);
  const cols3 = await ev(`window.__eh.colors(${JSON.stringify(shot3)}, [[400, 6], [${sx}, ${sy}]])`);
  const woody = ([r, g, bl]) => r > g && g > bl && r - bl > 40;   // wood (#a0703c), lit and shaded by the sun
  check(near(cols3[0], '#bfe2ff', 60) && woody(cols3[1]), 'the engine drew it: the light sky at the top, the wooden crate where it is', cols3);
  await t.shot('engine_host_3d.png', { x: FX, y: FY, width: 800, height: 500 });

  // Where the crate is now: the camera can still be gliding into place on a slow machine, so wait until two
  // readings agree, and click there.
  let at = await screen(crate.i);
  for (let k = 0; k < 25; k++) {
    await t.sleep(200);
    const again = await screen(crate.i);
    const still = Math.abs(again[0] - at[0]) < 0.5 && Math.abs(again[1] - at[1]) < 0.5;
    at = again;
    if (still) break;
  }
  await clear();
  await t.click(FX + at[0], FY + at[1]);
  const pick3 = (await waitMsg(`m.tuffHost === 'pick' && m.i === ${crate.i}`)) && (await msgs(`m.tuffHost === 'pick'`))[0];
  check(pick3 && Array.isArray(pick3.point) && pick3.point.length === 3, 'a real click on the crate picks it, with the point it hit', await msgs('true'));
  const hudText = thing(d3, 'score_label');
  const [tx2, ty2] = await screen(hudText.i);
  await clear();
  await t.click(FX + tx2, FY + ty2);
  check(await waitMsg(`m.tuffHost === 'pick' && m.i === ${hudText.i}`), 'the HUD over the world is picked first', await msgs('true'));

  await clear();
  await t.move(FX + sx, FY + sy);
  await press(FX + sx, FY + sy);
  await moveTo(FX + sx, FY + sy, FX + sx + 90, FY + sy, 10);
  const moved3 = (await ask('pos', { i: crate.i })).value;
  await release(FX + sx + 90, FY + sy);
  const drag3 = (await waitMsg(`m.tuffHost === 'drag' && m.phase === 'end'`)) && (await msgs(`m.tuffHost === 'drag'`))[0];
  check(drag3 && drag3.i === crate.i && drag3.x > 1 && Number.isInteger(drag3.x * 2) && Math.abs(drag3.z - -4) <= 0.5 && moved3.x === drag3.x,
    'dragging the crate right moves it along x over the ground, snapped to 0.5, and reports where (drag end)', { drag3, moved3 });

  const [mx, my] = await screen('player');
  await clear();
  await t.move(FX + mx, FY + my);
  await press(FX + mx, FY + my);
  await moveTo(FX + mx, FY + my, FX + mx - 60, FY + my + 30, 8);
  await release(FX + mx - 60, FY + my + 30);
  const dragP = (await waitMsg(`m.tuffHost === 'drag' && m.phase === 'end'`)) && (await msgs(`m.tuffHost === 'drag'`))[0];
  check(dragP && dragP.i === 'player' && dragP.x < 0, "the player's start marker drags too (drag i: 'player')", dragP);

  await clear();
  await t.move(FX + 400, FY + 20);
  await press(FX + 400, FY + 20);
  await moveTo(FX + 400, FY + 20, FX + 500, FY + 20, 10);
  await release(FX + 500, FY + 20);
  await t.sleep(300);
  const orbit = (await msgs(`m.tuffHost === 'cam'`)).pop();
  check(orbit && Math.abs(orbit.az - -30) < 1.5 && !(await msgs(`m.tuffHost === 'pick' || m.tuffHost === 'drag'`)).length,
    'dragging the sky orbits the camera (az -30 for 100 px) without picking or dragging anything', { orbit, all: await msgs('true') });
  await clear();
  await t.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: FX + 400, y: FY + 250, deltaX: 0, deltaY: 200 });
  await t.sleep(400);
  const zoom = (await msgs(`m.tuffHost === 'cam'`)).pop();
  check(zoom && zoom.dist > orbit.dist * 1.2, 'the wheel zooms out (dist grows)', { before: orbit?.dist, after: zoom?.dist });

  await ev(`window.__eh.post({ tuffHost: 'select', is: [${crate.i}, 'player'] })`);
  await t.sleep(200);
  stats = (await ask('stats')).value;
  check(stats.outlines === 2, 'select draws a wire box on the crate and on the player marker', stats);
  await t.shot('engine_host_3d_selected.png', { x: FX, y: FY, width: 800, height: 500 });

  await ev(`window.__eh.post({ tuffHost: 'view', cam: 'game' })`);
  await t.sleep(300);
  stats = (await ask('stats')).value;
  check(stats.camMode === 'game' && stats.cameraNodesVisible === true && stats.marker === false, "the game camera shows the held axe and hides the start marker", stats);
  await clear();
  await t.click(FX + sx, FY + sy);
  check(!(await msgs(`m.tuffHost === 'pick'`)).length, 'and is view only: a click picks nothing', await msgs('true'));
  await t.shot('engine_host_3d_game_camera.png', { x: FX, y: FY, width: 800, height: 500 });
  await ev(`window.__eh.post({ tuffHost: 'view', cam: 'editor' })`);
  await t.sleep(200);

  // A second 3D load keeps the scene (and its WebGL context); the camera stays where it was.
  const before = (await ask('stats')).value;
  check(await load(d3, 3), 'loading the world again works', await msgs(`m.tuffHost === 'error'`));
  const again = (await ask('stats')).value;
  const kept = (await msgs(`m.tuffHost === 'cam'`)).pop();
  check(again.scene === before.scene && again.b === 3e6 && Math.abs(again.objs - before.objs) <= 4,
    'the 3D scene node is kept from one 3D load to the next (one WebGL context), with new ids for the rest', { before, again });
  check(kept && Math.abs(kept.dist - zoom.dist) < 0.01 && Math.abs(kept.az - zoom.az) < 0.01, 'and the camera stays where it was', { kept, zoom });

  // Back to 2D: the 3D scene goes.
  await ev(`Object.assign(window.__eh.f.style, { width: '800px', height: '600px' })`);
  check(await load(d2, 4), 'and back to the 2D game', null);
  const last = (await ask('stats')).value;
  check(last.mode === '2d' && last.scene === null && last.objs < 20, 'the 3D scene is gone, only the 2D game is left', last);
  const engineErrors = await msgs(`m.tuffHost === 'error'`);
  check(!engineErrors.length, 'no errors from the engine or the page', engineErrors);
  await ev('window.__eh.f.remove()');
};
