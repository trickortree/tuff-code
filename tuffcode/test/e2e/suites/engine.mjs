// Tuff Engine, the visual game editor tab (renderer/js/tuff-engine.js), driven like a kid would: real clicks on the
// tiles, real drags in the preview (the real engine in tuffview://, see engine-host.mjs), real keys. It checks the code
// it writes line for line (the templates are the judge's files), that each action is one Ctrl+Z step, that code typed
// in the editor shows up in the scene, Play (the real game window, played by tgame's autopilot), the notice's "Open
// Tuff Engine" button, the templates, the 3D world, the start cards, and "Ask an agent" through Tuff Agents (with the
// stand-in agents). Screenshots of the walkthrough go to test/e2e/out/engine/.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { REPO, python } from '../launch.mjs';

// tgame's autopilot plays the game Play starts (TUFF_TGAME_AUTOPILOT reaches the run through the app's environment):
// the coin onto the player (a point), the enemy onto the player (game over), Space (play again), the right arrow held.
const PLAY = fs.mkdtempSync(path.join(os.tmpdir(), 'tuffcode-engine-play-'));
const PLAN = path.join(PLAY, 'plan.json');
fs.writeFileSync(PLAN, JSON.stringify({ on_top: false, timeout: 20, out: PLAY, steps: [
  // Room between steps for a slow machine (a CI Mac draws a few frames a second).
  { at: 0.4, dump: 'start.json' },
  { at: 0.5, tuff: 'coin:move_to(player:spot())' },
  { at: 1.1, dump: 'coin.json' },
  { at: 1.2, tuff: 'enemy:move_to(player:spot())' },
  { at: 1.9, dump: 'over.json' },
  { at: 2.0, key: 'space' },
  { at: 2.6, dump: 'again.json' },
  { at: 2.7, hold: 'right', for: 0.5 },
  { at: 3.5, dump: 'moved.json' },
  { at: 3.6, shot: 'play.png' },
  { at: 3.8, close: true },
] }));

export const meta = { title: 'Tuff Engine: the visual game editor tab', timeout: 600000, env: { TUFF_TGAME_AUTOPILOT: PLAN } };

const GAMES = path.join(REPO, 'tuffcode', 'test', 'tgame', 'games');
const repoGame = (name) => fs.readFileSync(path.join(GAMES, name), 'utf8').replace(/\r\n/g, '\n');
const firstDiff = (a, b) => {
  const x = String(a).split('\n');
  const y = String(b).split('\n');
  for (let i = 0; i < Math.max(x.length, y.length); i++) if (x[i] !== y[i]) return `line ${i + 1}: ${JSON.stringify(x[i])} / ${JSON.stringify(y[i])}`;
  return 'same';
};
const changedLines = (a, b) => {
  const x = a.split('\n');
  const y = b.split('\n');
  if (x.length !== y.length) return null;
  return x.map((l, i) => (l !== y[i] ? [i + 1, l, y[i]] : null)).filter(Boolean);
};

export default async (t, ctx) => {
  const ev = (js) => t.eval(js);
  const check = (ok, label, got) => t.check(label, ok, got);
  const waitFor = (js, ms = 15000) => t.waitFor(js, ms, 100);
  const dbg = () => ev('window.TuffEngine.debug()');
  const visible = () => ev(`!document.querySelector('#engine').classList.contains('hidden')`);
  // The scene is up to date: it was made from the code as it is now, and the preview has drawn it.
  const settle = (ms = 20000) => waitFor(`(() => { const d = window.TuffEngine.debug(); return d.dumpCurrent && !d.busy && d.loadSeq > 0 && d.loadedSeq === d.loadSeq; })()`, ms);
  // (scrolled into the middle first: the Inspector and the tiles scroll, and toasts sit at the bottom)
  const rect = (sel) => ev(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); el?.scrollIntoView({ block: 'center' }); const r = el?.getBoundingClientRect(); return r && r.width ? [r.left, r.top, r.width, r.height] : null; })()`);
  const clickSel = async (sel) => {
    const r = await rect(sel);
    if (!r) throw new Error(`Nothing to click: ${sel}`);
    await t.click(r[0] + r[2] / 2, r[1] + r[3] / 2);
  };
  const ask = (what, extra = {}) => ev(`window.TuffEngine.test.ask(${JSON.stringify(what)}, ${JSON.stringify(extra)})`);
  const stats = async () => (await ask('stats')).value;
  // Where dump thing i (or 'player') is, in the IDE window.
  const onScreen = async (i) => {
    const f = await rect('#en-frame');
    const p = (await ask('screen', { i })).value;
    return p ? [f[0] + p[0], f[1] + p[1]] : null;
  };
  const thingOf = (key) => ev(`window.TuffEngine.test.thingsOf(${JSON.stringify(key)})[0]`);
  const key = async (k, code, keyCode, mods = 0) => {
    await t.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', modifiers: mods, windowsVirtualKeyCode: keyCode, key: k, code });
    await t.send('Input.dispatchKeyEvent', { type: 'keyUp', modifiers: mods, windowsVirtualKeyCode: keyCode, key: k, code });
    await t.sleep(80);
  };
  const CTRL = 2;
  // The IDE's own shortcuts (Ctrl+S, Ctrl+Shift+D/G) are Cmd on a Mac; Tuff Engine's own take Ctrl or Cmd.
  const IDE = process.platform === 'darwin' ? 4 : CTRL;
  const SHIFT = 8;
  const drag = async (x0, y0, x1, y1, steps = 10) => {
    await t.move(x0, y0);
    await t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: x0, y: y0, button: 'left', buttons: 1, clickCount: 1 });
    for (let s = 1; s <= steps; s++) await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x0 + ((x1 - x0) * s) / steps, y: y0 + ((y1 - y0) * s) / steps, button: 'left', buttons: 1 });
    await t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x1, y: y1, button: 'left', buttons: 0, clickCount: 1 });
    await t.sleep(150);
  };
  await ev(`(() => { window.__toasts = []; new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => n.classList?.contains('toast') && window.__toasts.push(n.textContent)))).observe(document.querySelector('#toasts'), { childList: true }); return 1; })()`);
  const toasts = () => ev('window.__toasts.slice()');

  // ================================================================ the tab
  const kid = path.join(ctx.root, 'kid.tuf');
  fs.writeFileSync(kid, '');
  for (const [dir, file] of [['sprites', 'star.png'], ['sounds', 'blip.wav']]) {
    fs.mkdirSync(path.join(ctx.root, dir), { recursive: true });
    fs.copyFileSync(path.join(GAMES, file), path.join(ctx.root, dir, file));
  }
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'demo.tuf'))}); await window.TuffIDE.openFile(${JSON.stringify(kid)}); window.__kid = await window.TuffIDE.getModel(${JSON.stringify(kid)}); window.__code = () => window.__kid.getValue().replace(/\\r\\n/g, '\\n'); return 1; })()`);
  await t.sleep(300);
  const code = () => ev('window.__code()');
  check(await ev(`(() => { const b = document.querySelector('#toolstrip .ts-btn[data-tool="engine"]'); return !!(b && b.querySelector('svg path') && /Ctrl\\+Shift\\+G/.test(b.title)); })()`),
    'the left toolstrip has a gamepad button for Tuff Engine (an inline SVG, so it shows on a Mac too)', null);
  await t.key('G', IDE | SHIFT);
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 5000);
  const tabs = await ev(`[...document.querySelectorAll('#tabs .tab')].map((x) => ({ text: x.textContent.trim(), cls: x.className }))`);
  check(await visible() && await ev(`document.querySelector('#monaco').classList.contains('hidden')`) && /engine-tab/.test(tabs[0]?.cls) && /active/.test(tabs[0]?.cls) && tabs[0].text === 'Tuff Engine' && !tabs.slice(1).some((x) => /active/.test(x.cls)),
    'Ctrl+Shift+G opens Tuff Engine as a tab like Design Studio (first, active; the file tabs are not)', tabs);
  check(await ev(`window.TuffIDE.engineVisible() && typeof window.TuffIDE.openEngine === 'function' && typeof window.TuffIDE.scene === 'function'`), 'TuffIDE has openEngine, engineVisible and scene (for Learn and plugins)', null);
  await t.shot('engine_start_card.png');
  const card = await ev(`document.querySelector('#en-start:not(.hidden)')?.textContent || ''`);
  check(/Make a 2D game here/.test(card) && /Make a 3D world here/.test(card) && /New game from a template/.test(card), 'an empty file shows the start card: Make a 2D game, Make a 3D world, New game from a template', card);
  // The open file follows the Engine while it shows (agents and plugins get the game, not demo.tuf).
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid)})`);
  check(await ev(`window.TuffIDE.activeFile()`) === kid, 'TuffIDE.activeFile() is the game while Tuff Engine shows', await ev(`window.TuffIDE.activeFile()`));

  // ================================================================ a 2D game, as a kid makes it
  await clickSel('#en-start [data-a="2d"]');
  await waitFor(`window.__code().includes('tgame.window')`, 5000);
  const blank2d = 'mention tgame\n\ngame = tgame.window("My Game", 800, 600)\ngame:background "navy"\n';
  check(await code() === blank2d, 'Make a 2D game here writes four lines (mention tgame, the game, a navy background)', await code());
  check(await settle(), 'the scene comes back from tuff.py --scene and the preview draws it', await dbg());
  let st = await stats();
  check(st?.mode === '2d' && st.sceneBg === '#1e3a8a', 'the preview is the real engine: a navy 800 × 600 game area', st);
  check(await ev(`document.querySelector('#en-kind').textContent`) === '2D game 800×600', 'the bar says what it is: 2D game 800×600', await ev(`document.querySelector('#en-kind').textContent`));
  await t.shot('engine_2d_empty.png');

  const versions = [];
  for (const id of ['player', 'coin', 'enemy', 'ball']) {
    versions.push(await code());
    await clickSel(`.en-tile[data-tile="${id}"]`);
    await waitFor(`window.__code() !== ${JSON.stringify(versions[versions.length - 1])}`, 5000);
  }
  const coinDash = repoGame('coin_dash.tuf').replace('"Coin Dash"', '"My Game"');
  check(await code() === coinDash, 'Player, Coin, Enemy and Ball write exactly coin_dash.tuf (but the title): pieces, registrations, behaviour functions, play_again', firstDiff(await code(), coinDash));
  check(await settle(), 'the scene catches up', await dbg());
  st = await stats();
  const d1 = await dbg();
  check(st.things === 5 && d1.behaviours.map((b) => b.type).join() === 'arrows,collect,chase,hurts', 'the preview has the five things, and Tuff Engine knows their four behaviours', { things: st.things, beh: d1.behaviours.map((b) => b.id) });
  const objs = await ev(`[...document.querySelectorAll('#en-objects .sd-layer')].map((r) => r.dataset.key)`);
  check(objs.join() === 'root,v:score_label,v:player,v:coin,v:enemy,v:ball', 'Objects lists the game, then each thing in line order', objs);
  await t.shot('engine_2d_pieces.png');
  // One Ctrl+Z step per tile: undo the Ball, then redo it.
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(versions[3])}`, 4000);
  check(await code() === versions[3], 'Ctrl+Z takes away the Ball (one tile is one undo step)', firstDiff(await code(), versions[3]));
  await t.key('y', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(coinDash)}`, 4000);
  check(await code() === coinDash, 'Ctrl+Y puts it back', firstDiff(await code(), coinDash));
  await settle();

  // Click the coin in the preview, then drag it.
  const coinI = await thingOf('v:coin');
  const [cx, cy] = await onScreen(coinI);
  await t.click(cx, cy);
  await waitFor(`window.TuffEngine.debug().sel === 'v:coin'`, 4000);
  const insp = await ev(`document.querySelector('#en-inspector .in-head')?.textContent || ''`);
  st = await stats();
  check((await dbg()).sel === 'v:coin' && /Circle/.test(insp) && st.sel2d === true && st.sel.join() === String(coinI), 'a real click on the coin selects it: the Inspector shows it and the preview outlines it', { insp, st });
  const fr = await rect('#en-frame');
  const k = fr[2] / 800; // frame px per game unit
  const before = await code();
  await drag(cx, cy, cx + 100 * k, cy + 50 * k);
  await waitFor(`window.__code() !== ${JSON.stringify(before)}`, 5000);
  const dragged = changedLines(before, await code());
  check(dragged && dragged.length === 2 && dragged[0][2] === 'coin = game:circle(300, 250, 14, "gold")' && dragged[1][2] === '    coin:move_to(300, 250)',
    "dragging the coin 100 right and 50 down changes only its line (and play_again's coin line, so Space puts it back there)", dragged);
  await settle();
  await t.shot('engine_2d_dragged.png');
  check(await ev(`document.activeElement === document.querySelector('#en-stage')`), 'after the drag the stage has the keys again (the preview gives focus back)', await ev('document.activeElement?.id || document.activeElement?.tagName'));

  // ---------------- Play: the real game, with the coin where the kid dragged it
  const py = ctx.packaged ? null : python();
  const canPlay = ctx.packaged || (py && spawnSync(py[0], [...py.slice(1), '-c', 'import webview'], { windowsHide: true }).status === 0);
  if (!canPlay) t.skip('Play', 'the Python that runs tuff.py has no pywebview (py -m pip install pywebview)');
  else {
    const playW = await ev(`document.querySelector('#en-play').offsetWidth`);
    await clickSel('#en-play');
    await waitFor(`document.querySelector('#en-play').classList.contains('stop')`, 10000);
    const stopW = await ev(`document.querySelector('#en-play').offsetWidth`);
    check(/Stop/.test(await ev(`document.querySelector('#en-play').textContent`)) && stopW === playW && await visible(), `Play runs the game and turns into Stop, just as wide (${playW} px), and Tuff Engine stays open`, { playW, stopW });
    await waitFor(`!!document.querySelector('#run-output .tline.notice')`, 30000);
    const notice = await ev(`(() => { const s = document.querySelector('#run-output .tline.notice'); const b = s && s.querySelector('button.open-engine'); return s && { text: s.textContent, label: b && b.dataset.label, after: b && getComputedStyle(b, '::after').content, title: b && b.title }; })()`);
    check(notice && /^Tuff Engine is here: open this game in TuffCode's Tuff Engine tab \(Ctrl\+Shift\+G\) to build it visually\.$/.test(notice.text) && notice.label === 'Open Tuff Engine' && notice.after === '"Open Tuff Engine"',
      "the run's yellow notice says Tuff Engine is here, with an Open Tuff Engine button drawn by CSS (so Learn's checks never read it)", notice);
    const finished = await waitFor(`!document.querySelector('#en-play').classList.contains('stop')`, 60000);
    const out = await ev(`document.querySelector('#run-output').innerText`);
    check(finished && /exit code 0/.test(out) && /Play/.test(await ev(`document.querySelector('#en-play').textContent`)), 'the game played and closed (exit code 0), and Stop is Play again', out.slice(-300));
    const dump = (n) => { try { return JSON.parse(fs.readFileSync(path.join(PLAY, n), 'utf8')); } catch { return null; } };
    const [d0, dc, dov, dag, dmv] = ['start.json', 'coin.json', 'over.json', 'again.json', 'moved.json'].map(dump);
    const playerX = (d) => d?.sprites?.find((s) => s[0] === 'rect' && Math.abs(s[2] - 520) < 2 && s[1] >= 350)?.[1];
    check(d0?.texts?.includes('Score: 0') && dc?.texts?.includes('Score: 1'), 'in the real game the player collects the coin: Score 0 → 1', { start: d0?.texts, coin: dc?.texts });
    check(dov?.paused === true && dag?.paused === false && dag?.texts?.includes('Score: 0'), 'the enemy touching the player is game over, and Space plays again with the score back to 0', { over: dov?.paused, again: dag?.paused, texts: dag?.texts });
    check(playerX(dmv) > playerX(dag) + 50, `holding the right arrow moves the player (x ${playerX(dag)} → ${playerX(dmv)})`, { again: dag?.sprites, moved: dmv?.sprites });
    if (fs.existsSync(path.join(PLAY, 'play.png'))) fs.copyFileSync(path.join(PLAY, 'play.png'), path.join(ctx.out, 'engine_play_real_game.png'));
    // The notice's button opens the game in Tuff Engine (from the code tab).
    await clickSel('#tabs .tab:not(.engine-tab):not(.studio-tab)');
    await waitFor(`document.querySelector('#engine').classList.contains('hidden')`, 3000);
    await clickSel('#run-output button.open-engine');
    await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 4000);
    check(await visible() && (await dbg()).file === kid, "the notice's Open Tuff Engine button opens this game in Tuff Engine", await dbg());
  }
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  check(await code() === before, 'Ctrl+Z undoes the drag in one step', firstDiff(await code(), before));
  await settle();
  check((await ask('pos', { i: coinI })).value?.x === 200, 'and the preview shows the coin back where it was', (await ask('pos', { i: coinI })).value);

  // Nudging with the arrow keys: 1, Shift 10. Each press is one step.
  await ev(`window.TuffEngine.test.select('v:player')`);
  await ev(`document.querySelector('#en-stage').focus()`);
  await key('ArrowRight', 'ArrowRight', 39);
  await key('ArrowUp', 'ArrowUp', 38, SHIFT);
  await waitFor(`/player = game:box\\(401, 510, /.test(window.__code())`, 4000);
  check(/player = game:box\(401, 510, 50, 50, "lime"\)/.test(await code()) && /player:move_to\(401, 510\)/.test(await code()), 'the arrow keys nudge the selected thing (Right +1, Shift+Up -10)', (await code()).split('\n')[6]);
  await t.key('z', CTRL);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  check(await code() === before, 'and two Ctrl+Z put it back', firstDiff(await code(), before));
  await settle();

  // The Inspector: the enemy chases at 200 instead of 120 (one number in enemy_chase).
  await ev(`window.TuffEngine.test.select('v:enemy')`);
  await t.sleep(150);
  const speedInput = await ev(`(() => { const b = [...document.querySelectorAll('#en-inspector .en-beh')].find((x) => x.dataset.beh === 'chase'); const i = b && b.querySelector('input[type="number"]'); if (!i) return null; i.id = 'en-test-speed'; return i.value; })()`);
  check(speedInput === '120', 'the enemy shows its behaviours: Chases player (speed 120)', await ev(`[...document.querySelectorAll('#en-inspector .en-beh-h')].map((x) => x.textContent)`));
  // The Inspector can redraw just after (a scene refresh landing), which makes a new field: find it again then.
  let speedRect = null;
  for (let tries = 0; tries < 20 && !speedRect; tries++) {
    speedRect = await ev(`(() => { const b = [...document.querySelectorAll('#en-inspector .en-beh')].find((x) => x.dataset.beh === 'chase'); const i = b && b.querySelector('input[type="number"]'); if (!i) return null; i.id = 'en-test-speed'; i.scrollIntoView({ block: 'center' }); const r = i.getBoundingClientRect(); return r.width ? [r.left, r.top] : null; })()`);
    if (!speedRect) await t.sleep(100);
  }
  await t.click(speedRect[0] + 20, speedRect[1] + 10);
  await key('a', 'KeyA', 65, CTRL);
  await ev(`document.activeElement?.select?.(); 1`); // a made-up Ctrl+A selects nothing in a Mac text box
  await t.type('200', 30);
  await waitFor(`window.__code().includes('enemy:forward(200 * dt)')`, 4000);
  const speedLines = changedLines(before, await code());
  check(speedLines && speedLines.length === 1 && speedLines[0][2] === '    enemy:forward(200 * dt)', 'typing 200 in Chases → speed changes one number in enemy_chase', speedLines);
  check(await ev(`document.activeElement?.id === 'en-test-speed'`), 'and the field keeps the focus while the code and the preview catch up', await ev('document.activeElement?.className'));
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  await settle();

  // Rename: everywhere in one step; the Engine comment follows, the function keeps its name.
  await ev(`window.TuffEngine.test.select('v:coin')`);
  await t.sleep(100);
  await clickSel('#en-name');
  await key('a', 'KeyA', 65, CTRL);
  await ev(`document.activeElement?.select?.(); 1`); // a made-up Ctrl+A selects nothing in a Mac text box
  await t.type('gem', 30);
  await t.key('Enter');
  await waitFor(`window.__code().includes('gem = game:circle')`, 4000);
  const renamed = await code();
  check(/# Tuff Engine: player collects gem\nfunc coin_collect\(dt\):\n    if gem:touches\(player\):/.test(renamed) && /gem:move_to\(200, 200\)/.test(renamed) && !/\bcoin\b/.test(renamed.replace(/coin_collect|"coin"/g, '')),
    'renaming the coin to gem renames every use, updates the Engine comment, and keeps coin_collect', renamed.split('\n').filter((l) => /gem|coin/.test(l)));
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  check(await code() === before, 'one Ctrl+Z undoes the rename', firstDiff(await code(), before));
  await settle();

  // Duplicate (Ctrl+D) the coin: coin1, with its own collect function, and play_again puts it back too.
  await ev(`window.TuffEngine.test.select('v:coin')`);
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('d', CTRL);
  await waitFor(`window.__code().includes('coin1 = ')`, 4000);
  const dup = await code();
  check(/coin1 = game:circle\(230, 230, 14, "gold"\)/.test(dup) && /game:every_frame coin1_collect/.test(dup) && /# Tuff Engine: player collects coin1\nfunc coin1_collect\(dt\):/.test(dup) && /coin1:move_to\(230, 230\)/.test(dup) && (await dbg()).sel === 'v:coin1',
    'Ctrl+D duplicates the coin 30 px away, with its own Collect it, and selects the copy', dup.split('\n').filter((l) => /coin1/.test(l)));
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  await settle();

  // Delete the enemy (the Delete key): its line, both behaviours and play_again go; Ctrl+Z brings all back.
  await ev(`window.TuffEngine.test.select('v:enemy')`);
  await ev(`document.querySelector('#en-stage').focus()`);
  await key('Delete', 'Delete', 46);
  await waitFor(`!window.__code().includes('enemy')`, 4000);
  const noEnemy = await code();
  check(!/enemy|play_again/.test(noEnemy) && /coin_collect/.test(noEnemy) && (await toasts()).some((x) => /Removed enemy\. Ctrl\+Z brings it back/.test(x)),
    'Delete removes the enemy, its Chases and Game over, and play_again (nothing needs it now)', { left: noEnemy.split('\n').filter((l) => /enemy|play/.test(l)), toasts: await toasts() });
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  check(await code() === before, 'and Ctrl+Z brings every line back', firstDiff(await code(), before));
  await settle();

  // Events: a key handler, written in one step with its function.
  await ev(`window.TuffEngine.test.select('root')`);
  await t.sleep(150);
  const evBefore = await code();
  await clickSel('#en-inspector [data-a="key"]');
  await waitFor(`window.__code().includes('on_space')`, 4000);
  const withKey = await code();
  check(/game:every_frame enemy_hurts\ngame:on_key\("space", on_space\)\n/.test(withKey) && /\nfunc on_space\(key\):\n    say "You pressed " \+ key\n$/.test(withKey), '+ When a key is pressed writes game:on_key("space", on_space) and func on_space(key)', withKey.slice(-200));
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(evBefore)}`, 4000);
  check(await code() === evBefore, 'in one undo step (the Studio takes two)', firstDiff(await code(), evBefore));
  await settle();

  // The game's own settings: a black background is one line.
  await clickSel('#en-inspector .en-swatches .pf-chip[title="black"]');
  await waitFor(`window.__code().includes('game:background "black"')`, 4000);
  const bg = changedLines(before, await code());
  check(bg && bg.length === 1 && bg[0][2] === 'game:background "black"', 'the Game: picking black writes game:background "black"', bg);
  await settle();
  check((await stats()).sceneBg === '#000000', 'and the preview turns black', await stats());
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  await settle();

  // Screen text: the HUD and its text, in one step.
  await clickSel('.en-tile[data-tile="hudtext"]');
  await waitFor(`window.__code().includes('hud_text')`, 4000);
  const hudCode = await code();
  check(/game:background "navy"\nhud = game:hud\(\)\nscore = 0\n/.test(hudCode) && /ball:on_edge "bounce"\nhud_text = hud:text\("Lives: 3", 90, 30, 22, "white"\)\n/.test(hudCode), 'Screen text writes hud = game:hud() with the settings, and hud_text = hud:text("Lives: 3", …) with the things', hudCode.split('\n').slice(2, 16));
  await settle();
  const hudObjs = await ev(`[...document.querySelectorAll('#en-objects .sd-cat, #en-objects .sd-layer')].map((r) => r.dataset.key || r.textContent)`);
  check(hudObjs.indexOf('Screen') > 0 && hudObjs.indexOf('v:hud_text') > hudObjs.indexOf('Screen'), 'Objects lists it under Screen', hudObjs);
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  await settle();

  // Assets: the pictures and sounds next to the game.
  await clickSel('.en-left .en-tabs button[data-tab="assets"]');
  await waitFor(`document.querySelectorAll('#en-assets .en-asset').length >= 2`, 6000);
  const assets = await ev(`[...document.querySelectorAll('#en-assets .en-asset')].map((r) => ({ name: r.querySelector('.en-asset-n').textContent, img: r.querySelector('img')?.naturalWidth || 0, add: !!r.querySelector('[data-a="add"]'), copy: !!r.querySelector('[data-a="copy"]') }))`);
  const star = assets.find((a) => a.name === 'sprites/star.png');
  const blip = assets.find((a) => a.name === 'sounds/blip.wav');
  check(star && star.img > 0 && star.add && blip && blip.copy, 'Assets lists sprites/star.png (with its picture) and sounds/blip.wav (with a copy button)', assets);
  await clickSel('#en-assets .en-asset [data-a="add"]');
  await waitFor(`window.__code().includes('sprites/star.png')`, 4000);
  const starLine = (await code()).split('\n').find((l) => /star/.test(l));
  check(/^star = game:image\("sprites\/star\.png", 400, 300\)$/.test(starLine), 'Add puts the picture in the game: star = game:image("sprites/star.png", 400, 300)', starLine);
  await settle();
  check((await stats()).things === 6 && !(await dbg()).banner, 'and the preview draws it (from tuffview://app/project/)', { stats: await stats(), banner: (await dbg()).banner });
  await t.shot('engine_2d_assets.png');
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(before)}`, 4000);
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  check(await ev(`!!document.querySelector('.en-tile[data-tile="pic:sprites/star.png"]')`), 'the picture is a tile in Add too', null);
  await settle();
  check(/^OK/.test(ctx.tuffCheck((fs.writeFileSync(path.join(ctx.tmp, 'kid_check.tuf'), await code()), path.join(ctx.tmp, 'kid_check.tuf'))).trim()), 'the game passes tuff --check', ctx.tuffCheck(path.join(ctx.tmp, 'kid_check.tuf')));

  // ================================================================ code typed in the editor shows up
  const typed = before.replace('ball:on_edge "bounce"\n', 'ball:on_edge "bounce"\nfor i in range(1, 3):\n    game:box(600 + i * 50, 500, 30, 30, "orange")\nwall = game:box(700, 100, 40, 40, "orange")\n');
  await ev(`window.__kid.setValue(${JSON.stringify(typed)})`);
  await settle();
  const d2 = await dbg();
  const group = d2.groups[0];
  check(d2.keys.includes('v:wall') && group && group.n === 3 && group.why === 'inside a for loop', 'code typed in the editor shows up: a new box line, and 3 boxes from a for loop as "Made by your code"', { keys: d2.keys, groups: d2.groups });
  const groupRow = await ev(`[...document.querySelectorAll('#en-objects .en-group')].map((r) => r.textContent)`);
  check(groupRow.length === 1 && /3 × box/.test(groupRow[0]) && /inside a for loop \(line 14\)/.test(groupRow[0]), 'Objects lists them as "3 × box · inside a for loop (line 14)"', groupRow);
  const loopI = (await ev(`window.TuffEngine.test.thingsOf(${JSON.stringify(group.key)})`))[0];
  const [lx, ly] = await onScreen(loopI);
  const beforeLoopDrag = await code();
  await drag(lx, ly, lx + 60, ly - 60, 6);
  await t.sleep(600);
  check((await dbg()).sel === group.key && await code() === beforeLoopDrag && /Made by your code on line 14 \(inside a for loop\)/.test(await ev(`document.querySelector('#en-inspector').textContent`)),
    "a box made by the loop is picked but doesn't move: the Inspector says where it comes from", { sel: (await dbg()).sel, insp: (await ev(`document.querySelector('#en-inspector').textContent`)).slice(0, 200) });
  await t.shot('engine_2d_made_by_code.png');
  await ev(`window.__kid.setValue(${JSON.stringify(typed.replace('wall = game:box(700, 100, 40, 40, "orange")', 'wall = game:box(700, 100, 40, 40, "orangey")'))})`);
  await waitFor(`/Line 16/.test(window.TuffEngine.debug().banner)`, 15000);
  const banner = (await dbg()).banner;
  check(/Line 16: .*orangey.*The things made before that line are shown/.test(banner) && await ev(`!!document.querySelector('#en-banner [data-a="code"]')`), 'a mistake shows a banner: "Line 16: …", with Show in code', banner);
  await ev(`window.__kid.setValue(${JSON.stringify(before)})`);
  await settle();
  check(!(await dbg()).banner, 'and it goes when the code is right again', (await dbg()).banner);


  // ================================================================ Ask an agent
  await ev(`document.querySelector('#en-ask').click()`);
  await waitFor(`!!document.querySelector('.en-askbox')`, 3000);
  const modal = await ev(`(() => { const m = document.querySelector('.en-askbox'); return { btns: [...m.querySelectorAll('[data-mode]')].map((b) => [b.textContent, b.classList.contains('primary')]), chips: [...m.querySelectorAll('.modal-choices button')].map((b) => b.textContent) }; })()`);
  check(modal.btns.map((b) => b[0]).join() === 'Plan,Ask,Edit' && modal.btns[2][1] && modal.chips.length === 3, 'Ask an agent: a box with ideas and three buttons in the order Plan, Ask, Edit (Edit first choice)', modal);
  await ev(`document.querySelector('.modal-choices button').click()`);
  await ev(`document.querySelector('.en-askbox [data-mode="edit"]').click()`);
  await t.sleep(400);
  check((await toasts()).some((x) => /Turn on Tuff Agents in Plugins \(Alt\+3\) to ask an agent/.test(x)) && await ev(`!document.querySelector('#view-plugins').classList.contains('hidden') && !document.querySelector('#sidebar').classList.contains('collapsed')`),
    'with Tuff Agents off, it says to turn it on and opens Plugins', await toasts());
  await ev(`document.querySelector('.en-askbox [data-a="x"]')?.click(); 1`);

  // Turn Tuff Agents on (the stand-in agents), then ask about the game in main.tuf: the agent gets a note about Tuff Engine.
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"] .dot.ready')`, 20000);
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);
  check(await ev(`typeof window.tuffAskAgent === 'function'`), 'Tuff Agents gives Tuff Engine its window.tuffAskAgent hook', null);
  const main = path.join(ctx.root, 'main.tuf');
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(main)})`);
  await waitFor(`!!document.querySelector('#en-start [data-a="2d"]')`, 5000);
  await clickSel('#en-start [data-a="2d"]');
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(main)})).getValue().replace(/\\r\\n/g, '\\n').includes('tgame.window'))()`, 4000);
  await settle();
  await key('s', 'KeyS', 83, IDE); // Ctrl+S isn't the Engine's: it saves, as everywhere
  await waitFor(`(async () => (await window.tuff.fs.readFile(${JSON.stringify(main)})).includes('tgame.window'))()`, 5000);
  check(fs.readFileSync(main, 'utf8').includes('tgame.window'), 'Ctrl+S in Tuff Engine saves, like everywhere else', fs.readFileSync(main, 'utf8'));
  const runsBefore = ctx.readLog('claude').filter((l) => l.prompt).length;
  await ev(`document.querySelector('#en-ask').click()`);
  await waitFor(`!!document.querySelector('.en-askbox textarea')`, 3000);
  await ev(`(() => { const ta = document.querySelector('.en-askbox textarea'); ta.value = 'make the coin bigger every time I collect it'; return 1; })()`);
  await ev(`document.querySelector('.en-askbox [data-mode="edit"]').click()`);
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(main)})).getValue().replace(/\\r\\n/g, '\\n').includes('added by the agent'))()`, 30000);
  const run = ctx.readLog('claude').filter((l) => l.prompt).slice(runsBefore).pop() || {};
  const userMsg = await ev(`[...document.querySelectorAll('.ta-msg.user')].pop()?.textContent || ''`);
  check(/\(From TuffCode: they're building main\.tuf in Tuff Engine, TuffCode's visual game editor, as a 2D game\./.test(run.prompt || '') && /put new lines above any while game:open\(\): loop/.test(run.prompt || '') && /<message>\nmake the coin bigger every time I collect it\n<\/message>/.test(run.prompt || ''),
    'Edit sends the request to the agent with a note about Tuff Engine before the message', (run.prompt || '').slice(-900));
  check(/Open file: main\.tuf/.test(run.prompt || '') && (run.args || [])[(run.args || []).indexOf('--permission-mode') + 1] === 'acceptEdits' && /make the coin bigger/.test(userMsg) && !/From TuffCode/.test(userMsg) && /with main\.tuf/.test(userMsg),
    'in Edit mode, with the game as the open file; the chat shows the request but not the note', { args: run.args, userMsg });
  await settle();
  check(/added by the agent/.test(await ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(main)})).getValue().replace(/\\r\\n/g, '\\n'))()`)) && await visible() && (await dbg()).dumpCurrent,
    "the agent's change to main.tuf reaches Tuff Engine, and the scene refreshes by itself", await dbg());

  // Room for the 3D world: the side panels close.
  await ev(`(() => { window.TuffIDE.showSideView('plugins', false); document.querySelector('#toolstrip-right .ts-btn.active')?.click(); return 1; })()`);
  await t.sleep(400);

  // ================================================================ templates and a 3D world
  const tpl = await ev('window.TuffEngine.templates().map((t) => ({ id: t.id, name: t.name, code: t.code }))');
  check(tpl.map((x) => x.name).join(' | ') === 'Empty 2D game | Empty 3D world | Coin Dash (2D) | Island Walk (3D)', 'four templates: Empty 2D game, Empty 3D world, Coin Dash, Island Walk', tpl.map((x) => x.name));
  check(tpl.find((x) => x.id === 'coin_dash').code === repoGame('coin_dash.tuf') && tpl.find((x) => x.id === 'island_walk').code === repoGame('island_walk.tuf'),
    'the Coin Dash and Island Walk templates are exactly games/coin_dash.tuf and island_walk.tuf (which tgame plays)', null);
  await clickSel('#en-templates');
  await waitFor(`document.querySelectorAll('.sd-modal .sd-tcard').length === 4`, 3000);
  await t.shot('engine_templates.png');
  await ev(`document.querySelector('.sd-tcard[data-id="island_walk"] [data-a="new"]').click()`);
  const island = path.join(ctx.root, 'island_walk.tuf');
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(island)}`, 6000);
  check(fs.existsSync(island) && fs.readFileSync(island, 'utf8') === repoGame('island_walk.tuf') && await ev(`document.querySelector('#en-file').value`) === island,
    'New file makes island_walk.tuf with the template and opens it in Tuff Engine', await ev(`document.querySelector('#en-file').value`));
  check(await settle(25000), 'the 3D world loads', await dbg());
  // GitHub's Intel Macs have no WebGL: there Tuff Engine says it can't show 3D, and only the code is checked.
  const gl = (await dbg()).webgl !== false;
  if (!gl) {
    const banner = await ev(`document.querySelector('#en-banner')?.textContent || ''`);
    check(/can't show 3D worlds/.test(banner), 'with no WebGL, Tuff Engine says this computer can\'t show 3D worlds (2D still works)', banner.slice(0, 200));
  } else {
    await t.sleep(500);
    st = await stats();
    const d3 = await dbg();
    check(st.mode === '3d' && st.sceneBg === '#bfe2ff' && st.marker === true && d3.keys.join() === 'v:score_label,v:player,v:coin,v:tree,v:hut,v:enemy' && await ev(`document.querySelector('#en-kind').textContent`) === '3D world',
      "it's a 3D world in the real engine: the day sky, the player's start marker, and every thing", { st, keys: d3.keys });
    await t.shot('engine_3d_island_walk.png');
    const treeI = await thingOf('v:tree');
    const [tx, ty] = await onScreen(treeI);
    await t.click(tx, ty);
    await waitFor(`window.TuffEngine.debug().sel === 'v:tree'`, 4000);
    const treeBeh = await ev(`[...document.querySelectorAll('#en-inspector .en-beh-h')].map((x) => x.textContent)`);
    check((await dbg()).sel === 'v:tree' && treeBeh.some((x) => /Falls over when clicked \(grows back in 5 s\)/.test(x)), 'a real click on the tree selects it; it falls over when clicked (its behaviour)', treeBeh);
    const before3 = fs.readFileSync(island, 'utf8');
    const islandModel = () => ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(island)})).getValue().replace(/\\r\\n/g, '\\n'))()`);
    const hutI = await thingOf('v:hut');
    const [hx, hy] = await onScreen(hutI);
    await drag(hx, hy, hx - 120, hy, 10);
    await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(island)})).getValue().replace(/\\r\\n/g, '\\n') !== ${JSON.stringify(before3)})()`, 5000);
    const hutLines = changedLines(before3, await islandModel());
    check(hutLines && hutLines.length === 1 && /^hut = game:spawn\("hut", -?\d+(\.5)?, 0, -?\d+(\.5)?\)$/.test(hutLines[0][2]) && !/"hut", 8, 0, -16/.test(hutLines[0][2]),
      'dragging the hut moves it over the ground: one line, x and z snapped to 0.5', hutLines);
    await settle();
    await t.shot('engine_3d_dragged.png');
    await ev(`document.querySelector('#en-stage').focus()`);
    await t.key('z', CTRL);
    await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(island)})).getValue().replace(/\\r\\n/g, '\\n') === ${JSON.stringify(before3)})()`, 4000);
    check(await islandModel() === before3, 'Ctrl+Z undoes it', firstDiff(await islandModel(), before3));
    await clickSel('#en-cam [data-cam="game"]');
    await t.sleep(300);
    st = await stats();
    check(st.camMode === 'game' && st.marker === false, "the Game camera shows what the game shows when it starts", st);
    await t.shot('engine_3d_game_camera.png');
    await clickSel('#en-cam [data-cam="editor"]');
    await settle();
    // The World's sky.
    await ev(`window.TuffEngine.test.select('root')`);
    await t.sleep(150);
    await ev(`(() => { const s = [...document.querySelectorAll('#en-inspector select')].find((x) => [...x.options].some((o) => o.value === 'sunset')); s.value = 'sunset'; s.dispatchEvent(new Event('change')); return 1; })()`);
    await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(island)})).getValue().includes('game:sky "sunset"'))()`, 4000);
    const skyLines = changedLines(before3, await islandModel());
    check(skyLines && skyLines.length === 1 && skyLines[0][2] === 'game:sky "sunset"', 'the World: Sky → Sunset changes the sky line', skyLines);
    await settle();
    check((await stats()).sceneBg !== '#bfe2ff', 'and the preview gets the sunset sky', await stats());
    await t.shot('engine_3d_sunset.png');
    await ev(`document.querySelector('#en-stage').focus()`);
    await t.key('z', CTRL);
    await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(island)})).getValue().replace(/\\r\\n/g, '\\n') === ${JSON.stringify(before3)})()`, 4000);
    await settle();

  }
  // A 3D world from the start card: the island, a player and a tree.
  const kid3 = path.join(ctx.root, 'kid3d.tuf');
  fs.writeFileSync(kid3, '');
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid3)})`);
  await waitFor(`!!document.querySelector('#en-start [data-a="3d"]')`, 5000);
  await clickSel('#en-start [data-a="3d"]');
  const m3 = () => ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid3)})).getValue().replace(/\\r\\n/g, '\\n'))()`);
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid3)})).getValue().replace(/\\r\\n/g, '\\n').includes('tgame.world'))()`, 4000);
  await settle(25000);
  for (const id of ['player', 'chop', 'pine']) {
    const was = await m3();
    await clickSel(`.en-tile[data-tile="${id}"]`);
    await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid3)})).getValue().replace(/\\r\\n/g, '\\n') !== ${JSON.stringify(was)})()`, 4000);
  }
  const w3 = await m3();
  check(/game = tgame\.world\("My World", 960, 600\)\ngame:sky "day"\ngame:island\(80\)\nplayer = game:player\("first person"\)\ntree = game:spawn\("tree", -5, 0, -10\)\ntree:clicked tree_chop\npine = game:spawn\("pine", -?[\d.]+, 0, -?[\d.]+\)\n/.test(w3) && /# Tuff Engine: tree falls over when clicked\nfunc tree_chop\(thing\):/.test(w3),
    'Make a 3D world here, then Player, Choppable tree and Pine write the island, the player, a tree that falls over and a pine', w3);
  await settle(25000);
  await t.sleep(600);
  st = await stats();
  if (gl) check(st.mode === '3d' && st.marker === true && st.things >= 3, 'the preview shows the island, the player and the trees', st);
  await ev(`window.TuffEngine.test.select('v:tree')`);
  await t.sleep(400);
  await t.shot('engine_3d_world.png');
  check(/^OK/.test(ctx.tuffCheck((fs.writeFileSync(path.join(ctx.tmp, 'kid3_check.tuf'), w3), path.join(ctx.tmp, 'kid3_check.tuf'))).trim()), 'the 3D world passes tuff --check', ctx.tuffCheck(path.join(ctx.tmp, 'kid3_check.tuf')));
  // A template "Use here": it asks first, replaces the code in one step, and the scene goes from 3D to 2D.
  await clickSel('#en-templates');
  await waitFor(`document.querySelectorAll('.sd-modal .sd-tcard').length === 4`, 3000);
  await ev(`document.querySelector('.sd-tcard[data-id="coin_dash"] [data-a="here"]').click()`);
  await waitFor(`!document.querySelector('#modal').classList.contains('hidden')`, 3000);
  const askText = await ev(`document.querySelector('#modal-title').textContent + ' / ' + document.querySelector('#modal-ok').textContent`);
  check(askText === 'Replace the code in kid3d.tuf with the Coin Dash (2D) template? (Ctrl+Z undoes it.) / Replace', 'Use here asks first: "Replace the code in kid3d.tuf with the Coin Dash (2D) template? (Ctrl+Z undoes it.)"', askText);
  await clickSel('#modal-ok');
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid3)})).getValue().includes('Coin Dash'))()`, 4000);
  check(await m3() === repoGame('coin_dash.tuf'), 'Replace puts Coin Dash in the file', firstDiff(await m3(), repoGame('coin_dash.tuf')));
  await settle(25000);
  st = await stats();
  check(st.mode === '2d' && st.things === 5 && st.scene === null, 'and the preview goes from the 3D world to the 2D game', st);
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid3)})).getValue().includes('tgame.world'))()`, 4000);
  check(await m3() === w3, 'one Ctrl+Z brings the 3D world back', firstDiff(await m3(), w3));
  await settle(25000);

  // ================================================================ start cards, Design Studio, the round trip
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(path.join(ctx.root, 'demo.tuf'))})`);
  await waitFor(`/This is an app, not a game/.test(document.querySelector('#en-start')?.textContent || '')`, 5000);
  check(await ev(`!!document.querySelector('#en-start [data-a="studio"]')`), 'an mtgui file says "This is an app, not a game." with Open in Design Studio', await ev(`document.querySelector('#en-start').textContent`));
  await clickSel('#en-start [data-a="studio"]');
  await waitFor(`!document.querySelector('#studio').classList.contains('hidden')`, 4000);
  check(!(await visible()) && await ev(`document.querySelector('#sd-file').value`) === path.join(ctx.root, 'demo.tuf') && /^tab studio-tab active/.test(await ev(`[...document.querySelectorAll('#tabs .tab')].map((x) => x.className).filter((c) => /active/.test(c)).join('|')`)),
    'which opens Design Studio (and hides Tuff Engine, whose tab stays)', await ev(`[...document.querySelectorAll('#tabs .tab')].map((x) => x.className)`));
  // The Studio's own left tabs don't reach into Tuff Engine (they once took over its Add / Objects / Assets).
  const engTab = await ev(`document.querySelector('.en-left .en-tabs button.on')?.dataset.tab`);
  await clickSel('#studio .sd-tabs button[data-tab="layers"]');
  await clickSel('#studio .sd-tabs button[data-tab="add"]');
  check(await ev(`document.querySelector('.en-left .en-tabs button.on')?.dataset.tab`) === engTab && await ev(`[...document.querySelectorAll('.en-left .en-pane')].filter((p) => !p.classList.contains('hidden')).map((p) => p.dataset.pane).join()`) === engTab,
    "Design Studio's Add and Layers tabs leave Tuff Engine's tabs alone", engTab);
  await ev(`window.TuffIDE.openStudio(${JSON.stringify(kid)})`);
  await waitFor(`/This is a game/.test(document.querySelector('#sd-stage')?.textContent || '')`, 4000);
  await clickSel('#sd-stage [data-a="engine"]');
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 4000);
  check(await visible() && (await dbg()).file === kid, 'Design Studio on a game says "This is a game" and opens it in Tuff Engine', await dbg());
  // A game in a folder of its own can't reach sprites/ at the project's top: Assets counts what's out of reach.
  fs.mkdirSync(path.join(ctx.root, 'levels'), { recursive: true });
  const level = path.join(ctx.root, 'levels', 'level1.tuf');
  fs.writeFileSync(level, 'mention tgame\n\ngame = tgame.window("Level 1", 800, 600)\n');
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(level)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(level)}`, 4000);
  await clickSel('.en-left .en-tabs button[data-tab="assets"]');
  await waitFor(`/in other folders/.test(document.querySelector('#en-assets').textContent)`, 5000);
  const reach = await ev(`document.querySelector('#en-assets').textContent`);
  check(/No pictures next to level1\.tuf yet/.test(reach) && /1 more picture is in other folders\. Save it next to level1\.tuf \(in sprites\/\) to use it\./.test(reach) && /1 more sound is in other folders/.test(reach),
    'a game in levels/ gets "1 more picture is in other folders. Save it next to level1.tuf (in sprites/) to use it."', reach);
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(kid)}`, 4000);

  const games = fs.readdirSync(GAMES).filter((f) => f.endsWith('.tuf'));
  const trip = await ev(`(() => { const out = { lines: 0, bad: [] }; for (const [name, code] of ${JSON.stringify(games.map((g) => [g, repoGame(g)]))}) { const P = window.TuffEngine.parse(code); for (const n of P.nodes) { out.lines++; const l = window.TuffEngine.lineFor(n); if (l !== P.lines[n.line - 1]) out.bad.push(name + ':' + n.line + ' ' + l); } } return out; })()`);
  check(trip.lines > 40 && !trip.bad.length, `lineFor gives back every line Tuff Engine reads in games/*.tuf unchanged (${trip.lines} lines, ${games.length} games)`, trip.bad.slice(0, 5));
  const fx = await ev(`['coin_dash', 'island_walk'].every((id) => { const c = window.TuffEngine.templates().find((t) => t.id === id).code.split('\\n'); return window.TuffEngine.fixups(c).join('\\n') === c.join('\\n'); })`);
  check(fx, "fixups leaves the templates as they are (they're already right)", null);

  // ================================================================ what the kid wrote stays, and the kid's pace
  // Edits made on a scratch model with Tuff Engine's own Edits (what the Inspector and the tiles call), checked line
  // for line. The tab keeps showing kid.tuf.
  const edit = (src, fn) => ev(`(() => {
    const E = window.TuffEngine;
    const m = window.monaco.editor.createModel(${JSON.stringify(src)});
    m.setEOL(0);
    const was = E.test.useModel(m, ${JSON.stringify(path.join(ctx.root, 'scratch.tuf'))});
    try { (${fn})(E.parse(m.getValue()), E.test.edits, m); return m.getValue(); } finally { E.test.useModel(...was); m.dispose(); }
  })()`);
  const tplCode = (id) => ev(`window.TuffEngine.templates().find((x) => x.id === ${JSON.stringify(id)}).code`);
  // A behaviour's settings change only its own lines: the kid's comments in its function stay (spec §8.2).
  const commented = coinDash.replace('func player_arrows(dt):\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n',
    'func player_arrows(dt):\n    # TODO: make it faster when I get a power-up\n    if game:held("left"):\n        player:move(-300 * dt, 0)   # left\n\n');
  const faster = await edit(commented, `(P, E) => E.setBehaviour(P, P.behaviours.find((b) => b.type === 'arrows'), { S: 400 })`);
  check(changedLines(commented, faster)?.length === 4 && faster.includes('    # TODO: make it faster when I get a power-up\n    if game:held("left"):\n        player:move(-400 * dt, 0)   # left\n\n'),
    "Speed 300 → 400 in a commented player_arrows changes its four numbers; the kid's comment line, '# left' and the blank line stay", changedLines(commented, faster));
  const updown = await edit(commented, `(P, E) => E.setBehaviour(P, P.behaviours.find((b) => b.type === 'arrows'), { dirs: 'updown' })`);
  check(updown.includes('    # TODO: make it faster when I get a power-up\n\n    if game:held("up"):') && !/held\("(left|right)"\)/.test(updown), 'Up/down takes away just the left and right lines', updown.split('\n').slice(19, 27));
  // play_again follows where things start, and keeps the comments at the ends of its lines.
  const paNote = coinDash.replace('    coin:move_to(200, 200)\n', '    coin:move_to(200, 200)  # back to the start\n');
  const paMoved = await edit(paNote, `(P, E) => E.setArgs(P, P.byVar.coin, { x: 300, y: 300 })`);
  const paBall = await edit(paNote, `(P, E) => E.setArgs(P, P.byVar.ball, { x: 650, y: 350 })`);
  check(changedLines(paNote, paMoved)?.[1]?.[2] === '    coin:move_to(300, 300)  # back to the start' && changedLines(paNote, paBall)?.length === 1,
    "the coin moved to 300, 300: play_again's line follows and keeps its comment; moving the ball (no behaviour) leaves play_again alone", { coin: changedLines(paNote, paMoved), ball: changedLines(paNote, paBall) });
  // After the game loop: that code runs once the window has closed, so it isn't the thing's setup.
  const loopGame = 'mention tgame\n\ngame = tgame.window("G", 800, 600)\ngame:background "navy"\ncoin = game:circle(200, 200, 14, "gold")\n\nwhile game:open():\n    game:frame()\n\n# after the window closes\ncoin:hide()\ngame:background "black"\nsay "Thanks for playing"\n';
  const loopRed = await edit(loopGame, `(P, E) => E.setSetting(P, [['background', ['red']]])`);
  const loopShow = await edit(loopGame, `(P, E) => E.setProp(P, P.byVar.coin, 'hide', [])`);
  check(changedLines(loopGame, loopRed)?.[0]?.[2] === 'game:background "red"' && changedLines(loopGame, loopRed)?.[0]?.[0] === 4 && loopShow.endsWith('# after the window closes\ncoin:hide()\ngame:background "black"\nsay "Thanks for playing"\n') && /"gold"\)\ncoin:hide\(\)\n\nwhile/.test(loopShow),
    'Background and Hidden at start change the setup above the game loop, never the lines after it', { red: changedLines(loopGame, loopRed), hide: loopShow.split('\n').slice(3, 7) });
  // Names in other languages: renaming pi leaves pièce alone.
  const accents = 'mention tgame\n\ngame = tgame.window("G", 800, 600)\npi = game:circle(100, 100, 10, "gold")\npièce = 3\nsay pièce\n';
  const renamedPi = await edit(accents, `(P, E) => E.rename(P, P.byVar.pi, 'disc')`);
  check(renamedPi === accents.replace('pi = game', 'disc = game'), 'renaming pi to disc changes pi only: pièce, a name of its own in Tuff, stays', firstDiff(accents.replace('pi = game', 'disc = game'), renamedPi));
  // The screen layer: a new Screen text goes under the 3D score, not on top of it.
  const islandCode = await tplCode('island_walk');
  const hudText = await edit(islandCode, `(P, E) => E.add(P, 'hudtext')`);
  check(hudText.includes('\nhud_text = hud:text("Lives: 3", 90, 64, 22, "white")\n'), 'Island Walk, then Screen text: it goes under the score (90, 64), not on it (90, 30)', hudText.split('\n').filter((l) => /hud:text/.test(l)));
  // A Coin and an Enemy added before the Player get their behaviours from it.
  const late = await edit(await tplCode('blank2d'), `(P, E, m) => { for (const id of ['coin', 'enemy', 'player']) E.add(window.TuffEngine.parse(m.getValue()), id); }`);
  const lateP = await ev(`window.TuffEngine.parse(${JSON.stringify(late)}).behaviours.map((b) => b.type).sort().join()`);
  check(lateP === 'arrows,chase,collect,hurts' && /func play_again\(\):/.test(late) && (await toasts()).includes('Coin and enemy work with player now.'),
    'Coin, Enemy, then Player: the Player gives the coin Collect it and the enemy Chases and Game over, and says so', { lateP, toasts: (await toasts()).slice(-3) });
  check(/^OK/.test(ctx.tuffCheck((fs.writeFileSync(path.join(ctx.tmp, 'late_check.tuf'), late), path.join(ctx.tmp, 'late_check.tuf'))).trim()), 'and that game passes tuff --check', ctx.tuffCheck(path.join(ctx.tmp, 'late_check.tuf')));

  // Number fields at a kid's pace: the code follows the field, and everything typed before it's left is one Ctrl+Z.
  await ev(`window.TuffEngine.test.select('v:enemy')`);
  await t.sleep(200);
  const slowBefore = await code();
  await ev(`(() => { const b = [...document.querySelectorAll('#en-inspector .en-beh')].find((x) => x.dataset.beh === 'chase'); b.querySelector('input[type="number"]').id = 'en-test-slow'; return 1; })()`);
  await t.click(...(await rect('#en-test-slow')).slice(0, 2).map((v, j) => v + (j ? 10 : 20)));
  await t.key('a', CTRL); // (t.key selects all on a Mac too)
  const seen = [];
  for (const ch of '250') {
    await t.type(ch, 0);
    await t.sleep(450);
    seen.push((await code()).match(/enemy:forward\((\d+) \* dt\)/)?.[1]);
  }
  check(seen.join() === '2,25,250', `typed slowly (450 ms a key) in Chases → speed, the code follows the field: ${seen.join(', ')}`, seen);
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(slowBefore)}`, 4000);
  check(await code() === slowBefore, 'and one Ctrl+Z takes the whole 250 back to 120', firstDiff(await code(), slowBefore));
  await settle();
  // The game's Width: no error for the 1 and the 10 of 1000 while typing, and one step.
  const widthField = `(() => { const i = [...document.querySelectorAll('#en-inspector .en-num')].find((l) => l.textContent.trim().startsWith('Width')).querySelector('input'); i.id = 'en-test-width'; return 1; })()`;
  await ev(`window.TuffEngine.test.select('root')`);
  await t.sleep(200);
  await ev(widthField);
  const nToasts = (await toasts()).length;
  await t.click(...(await rect('#en-test-width')).slice(0, 2).map((v, j) => v + (j ? 10 : 20)));
  await t.key('a', CTRL);
  for (const ch of '1000') { await t.type(ch, 0); await t.sleep(450); }
  await waitFor(`window.__code().includes('tgame.window("My Game", 1000, 600)')`, 3000);
  const typedToasts = (await toasts()).slice(nToasts);
  check(/tgame\.window\("My Game", 1000, 600\)/.test(await code()) && !typedToasts.length, 'typing 1000 slowly in Width writes 1000, with no error for the 1 and the 10 on the way', { toasts: typedToasts, line: (await code()).split('\n')[2] });
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(slowBefore)}`, 4000);
  check(await code() === slowBefore, 'one Ctrl+Z puts 800 back', firstDiff(await code(), slowBefore));
  await settle();
  await ev(widthField);
  await t.click(...(await rect('#en-test-width')).slice(0, 2).map((v, j) => v + (j ? 10 : 20)));
  await t.key('a', CTRL);
  const nToasts2 = (await toasts()).length;
  for (const ch of '50') { await t.type(ch, 0); await t.sleep(400); }
  await key('Tab', 'Tab', 9);
  await t.sleep(400);
  const smallToasts = (await toasts()).slice(nToasts2);
  check(smallToasts.length === 1 && /A game is at least 100 wide/.test(smallToasts[0]) && await code() === slowBefore && await ev(`document.querySelector('#en-test-width')?.value`) === '800',
    'leaving Width at 50 says once that a game is at least 100 wide, and the field goes back to 800', { smallToasts, value: await ev(`document.querySelector('#en-test-width')?.value`) });
  await settle();

  // Things a function made: Objects and the Inspector give the line once.
  const snakeFile = path.join(ctx.root, 'snake.tuf');
  fs.copyFileSync(path.join(GAMES, 'snake.tuf'), snakeFile);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(snakeFile)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(snakeFile)}`, 5000);
  await settle(25000);
  await waitFor(`document.querySelectorAll('#en-objects .en-group').length > 0`, 8000);
  const snakeRows = await ev(`[...document.querySelectorAll('#en-objects .en-group .what')].map((r) => r.textContent)`);
  const startGroup = (await dbg()).groups.find((g) => g.why === 'made by start()');
  if (startGroup) await ev(`window.TuffEngine.test.select(${JSON.stringify(startGroup.key)})`);
  await t.sleep(150);
  const groupTip = await ev(`document.querySelector('#en-inspector .in-tip')?.textContent || ''`);
  check(snakeRows.includes('made by start() (line 52)') && !snakeRows.some((r) => /on line \d+ \(line/.test(r)) && /^Made by your code on line 52 \(made by start\(\)\)\./.test(groupTip),
    'snake.tuf: Objects says "made by start() (line 52)" and the Inspector "Made by your code on line 52 (made by start())", the line once each', { snakeRows, groupTip });
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(kid)}`, 5000);
  await settle();

  // The title bar's Run, the status bar and the window's title follow the game Tuff Engine shows.
  await ev(`window.TuffIDE.openFile(${JSON.stringify(main)}).then(() => 1)`);
  await waitFor(`document.querySelector('#engine').classList.contains('hidden')`, 3000);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid)})`);
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 3000);
  await t.sleep(300);
  const chrome = await ev(`({ run: document.querySelector('#runconfig-name').textContent, path: document.querySelector('#sb-path').textContent, title: document.title })`);
  await clickSel('#runconfig-widget');
  const runItem = await ev(`document.querySelector('#context-menu:not(.hidden) .mi')?.textContent || ''`);
  await ev(`document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); 1`);
  check(chrome.run === 'kid.tuf' && /kid\.tuf$/.test(chrome.path) && /– kid\.tuf –/.test(chrome.title) && /Run 'kid\.tuf'/.test(runItem),
    "with main.tuf's tab open and Tuff Engine on kid.tuf: the title bar's Run, its menu, the status bar and the window title all say kid.tuf", { chrome, runItem });

  // Edit > Undo while Tuff Engine shows undoes the game's last change, not the hidden code tab's typing.
  const notes = path.join(ctx.root, 'notes.tuf');
  await ev(`window.TuffIDE.openFile(${JSON.stringify(notes)}).then(() => 1)`);
  await waitFor(`document.querySelector('#engine').classList.contains('hidden')`, 3000);
  await ev(`(() => { const e = window.TuffIDE.editor(); const m = e.getModel(); e.setPosition({ lineNumber: m.getLineCount(), column: m.getLineMaxColumn(m.getLineCount()) }); e.focus(); return 1; })()`);
  await t.type('\nsay "my work"', 30);
  await t.sleep(300);
  const notesModel = `(async () => (await window.TuffIDE.getModel(${JSON.stringify(notes)})).getValue().replace(/\\r\\n/g, '\\n'))()`;
  const notesTyped = await ev(notesModel);
  await clickSel('.tab.engine-tab');
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 3000);
  const preBox = await code();
  await clickSel('.en-tile[data-tile="box"]');
  await waitFor(`window.__code() !== ${JSON.stringify(preBox)}`, 4000);
  const menuItem = async (label) => {
    await ev(`[...document.querySelectorAll('.menu-root > button')].find((b) => b.textContent === 'Edit').click()`);
    await t.sleep(150);
    const r = await ev(`(() => { const m = [...document.querySelectorAll('.menu-root.open .mi')].find((x) => x.querySelector('span').textContent === ${JSON.stringify(label)}); const b = m?.getBoundingClientRect(); return b ? [b.left + b.width / 2, b.top + b.height / 2] : null; })()`);
    await t.click(r[0], r[1]);
    await t.sleep(300);
  };
  await menuItem('Undo');
  await waitFor(`window.__code() === ${JSON.stringify(preBox)}`, 3000);
  check(await code() === preBox && await ev(notesModel) === notesTyped && await visible(), 'Edit > Undo takes away the Box in the game, and leaves the typing in notes.tuf (the hidden code tab)', { game: firstDiff(await code(), preBox), notes: await ev(notesModel) });
  await menuItem('Delete Line');
  check(await ev(notesModel) === notesTyped && await code() === preBox && await visible(), "Edit > Delete Line while Tuff Engine shows deletes nothing (there's no line on screen)", await ev(notesModel));
  await menuItem('Find…');
  await waitFor(`document.querySelector('#engine').classList.contains('hidden') && !!document.querySelector('.find-widget.visible')`, 3000);
  check(await ev(`document.querySelector('#engine').classList.contains('hidden') && window.TuffIDE.editor().getModel().uri.fsPath.toLowerCase() === ${JSON.stringify(kid.toLowerCase())} && !!document.querySelector('.find-widget.visible')`),
    "Edit > Find… opens the game's code (kid.tuf), with the find box", await ev(`window.TuffIDE.editor().getModel().uri.fsPath`));
  await key('Escape', 'Escape', 27);

  // The game's file tab closed while Tuff Engine shows it: the next click still does what it says.
  await ev(`window.TuffIDE.openFile(${JSON.stringify(notes)}).then(() => 1)`); // another tab is the active one, so Tuff Engine stays open
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid)})`);
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 3000);
  await settle();
  const preClose = await code();
  await ev(`(() => { [...document.querySelectorAll('#tabs .tab')].find((x) => x.title === ${JSON.stringify(kid)}).querySelector('.x').click(); return 1; })()`);
  await t.sleep(400);
  check(await visible() && !(await ev(`[...document.querySelectorAll('#tabs .tab')].some((x) => x.title === ${JSON.stringify(kid)})`)), "kid.tuf's tab is closed and Tuff Engine still shows the game", null);
  await clickSel('.en-tile[data-tile="circle"]');
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid)})).getValue().includes('circle = game:circle(400, 300, 20, "teal")'))()`, 5000);
  const afterClose = await ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kid)})).getValue().replace(/\\r\\n/g, '\\n'))()`);
  check(afterClose.includes('circle = game:circle(400, 300, 20, "teal")\n') && afterClose.replace('circle = game:circle(400, 300, 20, "teal")\n', '') === preClose,
    'one click on Circle opens the file again and adds the circle (the click is not lost)', firstDiff(preClose, afterClose));
  await ev(`(async () => { window.__kid = await window.TuffIDE.getModel(${JSON.stringify(kid)}); return 1; })()`);
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(preClose)}`, 4000);
  await settle();

  // Ask an agent: when Tuff Agents couldn't send it (an agent is still replying), the box and the words stay.
  await ev(`(() => { window.__realAsk = window.tuffAskAgent; window.__asked = []; window.tuffAskAgent = async (text) => { window.__asked.push(text); return false; }; return 1; })()`);
  await ev(`document.querySelector('#en-ask').click()`);
  await waitFor(`!!document.querySelector('.en-askbox textarea')`, 3000);
  await ev(`(() => { document.querySelector('.en-askbox textarea').value = 'and add three lives please'; return 1; })()`);
  await clickSel('.en-askbox [data-mode="edit"]');
  await t.sleep(300);
  check(await ev(`!!document.querySelector('.en-askbox') && document.querySelector('.en-askbox textarea').value === 'and add three lives please' && !document.querySelector('.en-askbox [data-mode="edit"]').disabled`) && (await ev('window.__asked')).length === 1,
    "Ask an agent: when it couldn't be sent, the box stays open with what the kid wrote", await ev('window.__asked'));
  await ev(`(() => { document.querySelector('.en-askbox [data-a="x"]')?.click(); if (window.__realAsk) window.tuffAskAgent = window.__realAsk; else delete window.tuffAskAgent; return 1; })()`);

  // The smallest window (900 × 560) with Learn open: Code and Play still show, in 2D and in 3D.
  await ev(`window.TuffIDE.showSideView('learn', true); 1`);
  fs.mkdirSync(path.join(ctx.root, 'lessons'), { recursive: true });
  const lessonFile = path.join(ctx.root, 'lessons', 'tgame-08-engine.tuf');
  fs.writeFileSync(lessonFile, coinDash);
  const islandFile = path.join(ctx.root, 'island_small.tuf');
  fs.writeFileSync(islandFile, islandCode);
  const fits = [];
  for (const [w, h] of [[900, 560], [960, 600], [1280, 720]]) {
    await t.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 0, mobile: false });
    for (const f of [lessonFile, islandFile]) {
      await ev(`window.TuffIDE.openEngine(${JSON.stringify(f)})`);
      await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(f)} && !!window.TuffEngine.debug().mode`, 5000);
      await t.sleep(400);
      fits.push(await ev(`(() => { const r = (s) => document.querySelector(s).getBoundingClientRect(); const p = r('#en-play'); const c = r('#en-code'); const hit = document.elementFromPoint(p.left + p.width / 2, p.top + p.height / 2); return { size: '${w}x${h}', mode: window.TuffEngine.debug().mode, engine: Math.round(r('#engine').width), play: p.right <= innerWidth && p.width > 20 && !!hit?.closest('#en-play'), code: c.right <= p.left && c.width > 20, templates: r('#en-templates').width > 0 }; })()`));
    }
    if (w === 900) await t.shot('engine_small_window_learn.png');
  }
  await t.send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 880, deviceScaleFactor: 0, mobile: false });
  await ev(`window.TuffIDE.showSideView('learn', false); 1`);
  check(fits.length === 6 && fits.every((f) => f.play && f.code) && fits.filter((f) => f.size === '1280x720').every((f) => f.templates),
    'with Learn open, Tuff Engine shows Code and Play at 900 × 560 and 960 × 600 (about 500 px), for the lesson game and a 3D world; at 1280 × 720 nothing is hidden', fits);

  // The gamepad never opens an empty Tuff Engine: a game it showed that's gone gives way to the .tuf tab that's open.
  const gone = path.join(ctx.root, 'gone.tuf');
  fs.writeFileSync(gone, coinDash);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(gone)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(gone)}`, 5000);
  await clickSel('.tab.engine-tab .x');
  await waitFor(`!document.querySelector('.tab.engine-tab')`, 3000);
  await ev(`(() => { [...document.querySelectorAll('#tabs .tab')].find((x) => x.title === ${JSON.stringify(gone)})?.querySelector('.x').click(); return 1; })()`);
  await t.sleep(300);
  fs.rmSync(gone);
  const fresh = path.join(ctx.root, 'fresh.tuf');
  fs.writeFileSync(fresh, '');
  await ev(`window.TuffIDE.openFile(${JSON.stringify(fresh)}).then(() => 1)`);
  const nToasts3 = (await toasts()).length;
  await clickSel('#toolstrip .ts-btn[data-tool="engine"]');
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(fresh)} && !!document.querySelector('#en-start:not(.hidden) [data-a="2d"]')`, 5000);
  check(await ev(`window.TuffEngine.debug().file`) === fresh && !(await toasts()).slice(nToasts3).some((x) => /Couldn't open/.test(x)) && await ev(`!!document.querySelector('#en-start:not(.hidden) [data-a="2d"]')`),
    "the gamepad, after the game Tuff Engine showed was deleted: it opens the .tuf tab that's open (its start card), not a blank tab", { file: await ev(`window.TuffEngine.debug().file`), toasts: (await toasts()).slice(nToasts3) });
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kid)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(kid)}`, 5000);
  await settle();

  // ================================================================ full size, leaving and closing
  await ev(`document.querySelector('#en-stage').focus()`);
  await key('F11', 'F11', 122);
  await t.sleep(200);
  check(await ev(`document.querySelector('#app').classList.contains('studio-full') && getComputedStyle(document.querySelector('#sidebar')).display === 'none' && getComputedStyle(document.querySelector('#tabs')).display === 'none'`), 'F11: Full size gives Tuff Engine the whole window', null);
  await t.shot('engine_full_size.png');
  await key('F11', 'F11', 122);
  await t.sleep(200);
  check(await ev(`!document.querySelector('#app').classList.contains('studio-full') && getComputedStyle(document.querySelector('#tabs')).display !== 'none'`), 'and F11 again gives it back', null);
  // The IDE's own shortcuts still work from Tuff Engine (Ctrl+D is Duplicate there, Ctrl+Shift+D isn't).
  await ev(`window.TuffEngine.test.select('v:coin')`);
  await ev(`document.querySelector('#en-stage').focus()`);
  const beforeKeys = await code();
  await t.key('D', IDE | SHIFT);
  await waitFor(`!document.querySelector('#studio').classList.contains('hidden')`, 4000);
  check(!(await visible()) && await code() === beforeKeys, 'Ctrl+Shift+D from Tuff Engine opens Design Studio (and duplicates nothing)', firstDiff(await code(), beforeKeys));
  await t.key('G', IDE | SHIFT);
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 4000);
  check(await visible(), 'and Ctrl+Shift+G comes back', null);
  await clickSel('#tabs .tab:not(.engine-tab):not(.studio-tab)');
  await waitFor(`document.querySelector('#engine').classList.contains('hidden')`, 3000);
  check(!(await visible()) && await ev(`!document.querySelector('#monaco').classList.contains('hidden') && !document.querySelector('.tab.engine-tab').classList.contains('active') && !!document.querySelector('#tabs .tab.active:not(.engine-tab)')`),
    'clicking a file tab leaves Tuff Engine for the code', await ev(`[...document.querySelectorAll('#tabs .tab')].map((x) => x.className)`));
  await clickSel('.tab.engine-tab');
  await waitFor(`!document.querySelector('#engine').classList.contains('hidden')`, 3000);
  check(await visible(), 'clicking its tab comes back', null);
  await clickSel('.tab.engine-tab .x');
  await waitFor(`!document.querySelector('.tab.engine-tab')`, 3000);
  check(!(await visible()) && !(await ev(`!!document.querySelector('.tab.engine-tab')`)), 'its X closes the tab', null);

  // A new, empty folder (opened from the project menu's recent folders): the gamepad makes main.tuf and opens it on
  // the start card, not on an empty Tuff Engine (and not on the last folder's game).
  const emptyDir = path.join(ctx.tmp, 'new game');
  fs.mkdirSync(emptyDir, { recursive: true });
  await ev(`window.TuffIDE.saveSettings({ recent: [${JSON.stringify(emptyDir)}, ...(window.TuffIDE.settings().recent || [])] })`);
  await clickSel('#project-widget');
  await t.sleep(200);
  const recentAt = await ev(`(() => { const m = [...document.querySelectorAll('#context-menu .mi')].find((x) => x.querySelector('span').textContent === 'new game'); const b = m?.getBoundingClientRect(); return b ? [b.left + b.width / 2, b.top + b.height / 2] : null; })()`);
  await t.click(recentAt[0], recentAt[1]);
  await waitFor(`window.TuffIDE.root() === ${JSON.stringify(emptyDir)}`, 5000);
  await t.sleep(300);
  await clickSel('#toolstrip .ts-btn[data-tool="engine"]');
  const newMain = path.join(emptyDir, 'main.tuf');
  await waitFor(`!!document.querySelector('#en-start:not(.hidden) [data-a="2d"]')`, 6000);
  check(fs.existsSync(newMain) && await ev(`window.TuffEngine.debug().file`) === newMain && /Make a game in main\.tuf/.test(await ev(`document.querySelector('#en-start').textContent`)),
    'in a new, empty folder the gamepad makes main.tuf and opens it on the start card (Make a 2D game here)', { exists: fs.existsSync(newMain), file: await ev(`window.TuffEngine.debug().file`), card: await ev(`document.querySelector('#en-start').textContent`) });
  const errors = t.events.filter((x) => /tuff-engine.js|engine-host|host.js|Tuff Engine/.test(x));
  check(!errors.length, 'no errors in the page', errors);
  fs.rmSync(PLAY, { recursive: true, force: true });
};
