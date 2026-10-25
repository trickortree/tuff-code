// Tuff Engine, the visual game editor tab (renderer/js/tuff-engine.js), driven like a kid would: real clicks on the
// tiles, real drags in the preview (the real engine in tuffview://, see engine-host.mjs), real keys. It checks the code
// it writes line for line (the templates are the judge's files), that each action is one Ctrl+Z step, that code typed
// in the editor shows up in the scene, Play (the real game window, played by tgame's autopilot), the notice's "Open
// Tuff Engine" button, the templates, the 3D world, the land (the Terrain tab and modern lighting), the start cards,
// and "Ask an agent" through Tuff Agents (with the stand-in agents). Screenshots of the walkthrough go to
// test/e2e/out/engine/.
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
  // GitHub's Intel Mac runner is several times slower than a PC (and has no WebGL): every wait gets longer there.
  const SLOW = ctx.ci && process.platform === 'darwin' && process.arch === 'x64' ? 4 : 1;
  const waitFor = (js, ms = 15000) => t.waitFor(js, ms * SLOW, 100);
  const dbg = () => ev('window.TuffEngine.debug()');
  const visible = () => ev(`!document.querySelector('#engine').classList.contains('hidden')`);
  // The scene is up to date: it was made from the code as it is now, and the preview has drawn it.
  const settle = (ms = 20000) => waitFor(`(() => { const d = window.TuffEngine.debug(); return d.dumpCurrent && !d.busy && d.loadSeq > 0 && d.loadedSeq === d.loadSeq; })()`, ms);
  // After an undo, settle on a scene loaded since (seq is loadSeq from before it). An undo brings back the code's
  // version number, so an older scene can look current while the Inspector's redraw for the undo is still to come.
  const settleSince = async (seq) => { await waitFor(`window.TuffEngine.debug().loadSeq > ${seq}`); await settle(); };
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
    // Short pauses, like a hand: a slow machine's preview otherwise sees the press, the moves and the release at once.
    await t.sleep(80);
    for (let s = 1; s <= steps; s++) {
      await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x0 + ((x1 - x0) * s) / steps, y: y0 + ((y1 - y0) * s) / steps, button: 'left', buttons: 1 });
      await t.sleep(25);
    }
    await t.sleep(80);
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
  check(!(await ev(`!!document.querySelector('.en-tile[data-tile="car"], .en-tile[data-tile="ragdoll"]')`)), "a 2D game's Add tab has no Car or Ragdoll (they need a 3D world)", null);
  check(!(await ev(`!!document.querySelector('.en-tile[data-tile="door"], .en-tile[data-tile="jump_pad"], .en-tile[data-tile="platform"], .en-tile[data-tile="person"]')`)), "... and no Level pieces (doors, pads, platforms and people are 3D)", null);

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
  // 2D sprites can have physics too (1.3.0): the ball's Inspector has Physics, and the Add tab's tiles show the game's
  // own shapes and colours.
  await ev(`window.TuffEngine.test.select('v:ball')`);
  check(await waitFor(`!!document.querySelector('#en-physics .pf-chip[data-v="dynamic"]')`, 4000).then(() => true, () => false), "a 2D ball's Inspector has Physics (Off, Falls, Fixed)", null);
  await ev(`window.TuffEngine.test.select('root')`);
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  const pics2d = await ev(`['player', 'coin', 'enemy', 'ball', 'box', 'circle', 'text'].filter((id) => /^data:image\\/png/.test(document.querySelector('#en-add .en-tile[data-tile="' + id + '"] .en-shot.real img')?.src || ''))`);
  check(pics2d.length === 7, "the 2D Add tab's tiles show pictures of what they add", pics2d);
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
  await waitFor(`window.__code() !== ${JSON.stringify(before)}`, 10000);
  const dragged = changedLines(before, await code());
  check(dragged && dragged.length === 2 && dragged[0][2] === 'coin = game:circle(300, 250, 14, "gold")' && dragged[1][2] === '    coin:move_to(300, 250)',
    "dragging the coin 100 right and 50 down changes only its line (and play_again's coin line, so Space puts it back there)", dragged);
  await settle();
  await t.shot('engine_2d_dragged.png');
  check(await ev(`document.activeElement === document.querySelector('#en-stage')`), 'after the drag the stage has the keys again (the preview gives focus back)', await ev('document.activeElement?.id || document.activeElement?.tagName'));

  // ---------------- Play: the real game, with the coin where the kid dragged it
  const py = ctx.packaged ? null : python();
  const canPlay = ctx.packaged || (py && spawnSync(py[0], [...py.slice(1), '-c', 'import webview'], { windowsHide: true }).status === 0);
  // Code Tuff Engine wrote, played in tgame by its autopilot (steps: dumps, held keys, close): what it printed and
  // its dumps. null when this Python can't play games (and on a packaged app, whose Play is tested above).
  const playCode = (name, src, steps) => {
    if (!py || !canPlay) return null;
    const dir = fs.mkdtempSync(path.join(PLAY, `${name}-`));
    const file = path.join(dir, `${name}.tuf`);
    fs.writeFileSync(file, src);
    const plan = path.join(dir, 'plan.json');
    fs.writeFileSync(plan, JSON.stringify({ on_top: false, timeout: 20, out: dir, steps }));
    const env = { ...process.env, TUFF_TGAME_AUTOPILOT: plan, PYTHONIOENCODING: 'utf-8' };
    delete env.TUFF_IDE;
    const r = spawnSync(py[0], [...py.slice(1), path.join(REPO, 'tuff.py'), file], { cwd: dir, encoding: 'utf8', timeout: 60000, windowsHide: true, env });
    const dump = (n) => { try { return JSON.parse(fs.readFileSync(path.join(dir, n), 'utf8')); } catch { return null; } };
    return { code: r.status, out: `${r.stdout || ''}${r.stderr || ''}`, dump };
  };
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
  // Plugins (opened above) closes again: on a small screen, with Tuff Agents on the right as well, it left the
  // start card no room. Then wait for its button to be really there, with a size.
  await ev(`window.TuffIDE.showSideView('plugins', false); 1`);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(main)})`);
  await waitFor(`(() => { const b = document.querySelector('#en-start [data-a="2d"]'); return !!b && b.getBoundingClientRect().width > 0; })()`, 15000);
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
  check(tpl.map((x) => x.name).join(' | ') === 'Empty 2D game | Empty 3D world | Coin Dash (2D) | Island Walk (3D) | Hills and Lake (3D)', 'five templates: Empty 2D game, Empty 3D world, Coin Dash, Island Walk, Hills and Lake', tpl.map((x) => x.name));
  check(tpl.find((x) => x.id === 'coin_dash').code === repoGame('coin_dash.tuf') && tpl.find((x) => x.id === 'island_walk').code === repoGame('island_walk.tuf') && tpl.find((x) => x.id === 'hills_lake').code === repoGame('hills_lake.tuf'),
    'the Coin Dash, Island Walk and Hills and Lake templates are exactly games/coin_dash.tuf, island_walk.tuf and hills_lake.tuf (which tgame plays)', null);
  await clickSel('#en-templates');
  await waitFor(`document.querySelectorAll('.sd-modal .sd-tcard').length === 5`, 3000);
  await t.shot('engine_templates.png');
  await ev(`document.querySelector('.sd-tcard[data-id="island_walk"] [data-a="new"]').click()`);
  const island = path.join(ctx.root, 'island_walk.tuf');
  // (On a Mac the temp folder is reached through /var, a link to /private/var: compare the real paths.)
  const samePath = (x, y) => { try { return fs.realpathSync(x) === fs.realpathSync(y); } catch { return x === y; } };
  await waitFor(`(window.TuffEngine.debug().file || '').endsWith('island_walk.tuf')`, 6000);
  check(fs.existsSync(island) && fs.readFileSync(island, 'utf8') === repoGame('island_walk.tuf') && samePath(await ev(`document.querySelector('#en-file').value`), island),
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
  await waitFor(`document.querySelectorAll('.sd-modal .sd-tcard').length === 5`, 3000);
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

  // ================================================================ physics: the Inspector's Physics section, Car and Ragdoll
  // A box gets its physics in its Inspector: Off, Falls (crate:physics()) or Fixed (crate:physics("static")), then
  // Bounce typed in (crate:bounce(0.6)), each one line right after the box and one Ctrl+Z; Off takes them all out.
  // Objects badges the things that use physics, and the 3D Add tab has Car (the player gets in with F) and Ragdoll.
  // The preview doesn't simulate, so the code, the Inspector and tuff --check are checked (the scene shows the
  // physics lines once tgame's runtime has them; before that, it stops at the first one with a banner).
  const physFile = path.join(ctx.root, 'phys.tuf');
  const physStart = 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\ngame:island(80)\ncrate = game:box(0, 2, -6, 1, "wood")\n';
  fs.writeFileSync(physFile, physStart);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(physFile)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(physFile)}`, 6000);
  await settle(25000);
  const mp = () => ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(physFile)})).getValue().replace(/\\r\\n/g, '\\n'))()`);
  const mpIs = (want) => waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(physFile)})).getValue().replace(/\\r\\n/g, '\\n') === ${JSON.stringify(want)})()`, 6000);
  const mpNot = (was) => waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(physFile)})).getValue().replace(/\\r\\n/g, '\\n') !== ${JSON.stringify(was)})()`, 6000);
  const physUi = () => ev(`(() => { const p = document.querySelector('#en-physics'); const s = p?.closest('.pf-sec'); return p ? { chips: [...p.querySelectorAll('.pf-chip')].map((b) => b.dataset.v + ':' + b.textContent + (b.classList.contains('sel') ? '*' : '')).join(), nums: [...s.querySelectorAll('.en-num span')].map((x) => x.textContent).join() } : null; })()`);
  const badged = () => ev(`[...document.querySelectorAll('#en-objects .sd-layer')].filter((r) => r.querySelector('.en-phys')).map((r) => r.dataset.key).join()`);
  const physUndo = async (want) => { await ev(`document.querySelector('#en-stage').focus()`); await t.key('z', CTRL); await mpIs(want); };
  await ev(`window.TuffEngine.test.select('v:crate')`);
  await waitFor(`!!document.querySelector('#en-physics')`, 4000);
  let pu = await physUi();
  check(pu?.chips === 'off:Off*,dynamic:Falls,static:Fixed' && pu.nums === '' && await badged() === '', "a box's Inspector has a Physics section: Off (chosen), Falls and Fixed, and Objects badges nothing yet", { pu, badged: await badged() });
  await clickSel('#en-physics .pf-chip[data-v="dynamic"]');
  await mpNot(physStart);
  const falls = await mp();
  check(falls === `${physStart}crate:physics()\n`, 'Falls writes crate:physics() right after the box', firstDiff(falls, `${physStart}crate:physics()\n`));
  await waitFor(`document.querySelector('#en-physics .pf-chip.sel')?.dataset.v === 'dynamic'`, 4000);
  pu = await physUi();
  check(pu?.nums === 'Weight,Bounce,Friction' && await badged() === 'v:crate', 'then it has Weight, Bounce and Friction, and Objects shows a physics badge on the crate', { pu, badged: await badged() });
  await settle(25000);
  const weightBox = () => ev(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span')?.textContent === 'Weight'); const i = l && l.querySelector('input'); return i ? { value: i.value, placeholder: i.placeholder, title: i.title } : null; })()`);
  await waitFor(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span')?.textContent === 'Weight'); return l?.querySelector('input')?.placeholder === '50'; })()`, 8000);
  const wb = await weightBox();
  check(wb?.value === '' && wb.placeholder === '50' && /50 kg/.test(wb.title), "Weight is empty with what the 1 m box weighs as it is: 50 (kg)", wb);
  let bounceRect = null;
  for (let tries = 0; tries < 20 && !bounceRect; tries++) {
    bounceRect = await ev(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span')?.textContent === 'Bounce'); const i = l && l.querySelector('input'); if (!i) return null; i.id = 'en-test-bounce'; i.scrollIntoView({ block: 'center' }); const r = i.getBoundingClientRect(); return r.width ? [r.left, r.top] : null; })()`);
    if (!bounceRect) await t.sleep(100);
  }
  await t.click(bounceRect[0] + 20, bounceRect[1] + 10);
  await t.type('0.6', 60);
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(physFile)})).getValue().includes('crate:bounce(0.6)'))()`, 4000);
  await ev(`document.querySelector('#en-stage').focus()`);
  const bounced = await mp();
  check(bounced === `${falls}crate:bounce(0.6)\n`, 'typing 0.6 in Bounce writes crate:bounce(0.6) under it', firstDiff(bounced, `${falls}crate:bounce(0.6)\n`));
  // Weight typed in: crate:weight(80), one more line; one Ctrl+Z takes it out.
  await ev(`window.TuffEngine.test.select('v:crate')`);
  let weightRect = null;
  for (let tries = 0; tries < 20 && !weightRect; tries++) {
    weightRect = await ev(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span')?.textContent === 'Weight'); const i = l && l.querySelector('input'); if (!i) return null; i.scrollIntoView({ block: 'center' }); const r = i.getBoundingClientRect(); return r.width ? [r.left, r.top] : null; })()`);
    if (!weightRect) await t.sleep(100);
  }
  await t.click(weightRect[0] + 20, weightRect[1] + 10);
  await t.type('80', 60);
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(physFile)})).getValue().includes('crate:weight(80)'))()`, 4000);
  await ev(`document.querySelector('#en-stage').focus()`);
  const weighed = await mp();
  check(weighed === `${bounced}crate:weight(80)\n`, 'typing 80 in Weight writes crate:weight(80) under it', firstDiff(weighed, `${bounced}crate:weight(80)\n`));
  await physUndo(bounced);
  check(await mp() === bounced, 'one Ctrl+Z takes the weight out again', firstDiff(await mp(), bounced));
  await clickSel('.en-left .en-tabs button[data-tab="objects"]');
  await ev(`document.querySelector('#en-physics')?.scrollIntoView({ block: 'center' }); 1`);
  await t.shot('engine_physics_box.png');
  await clickSel('#en-physics .pf-chip[data-v="static"]');
  await mpNot(bounced);
  const fixedLines = changedLines(bounced, await mp());
  check(fixedLines?.length === 1 && fixedLines[0][2] === 'crate:physics("static")', 'Fixed changes that one line to crate:physics("static")', fixedLines);
  await physUndo(bounced);
  check(await mp() === bounced, 'one Ctrl+Z makes it fall again', firstDiff(await mp(), bounced));
  await ev(`window.TuffEngine.test.select('v:crate')`);
  await waitFor(`!!document.querySelector('#en-physics .pf-chip[data-v="off"]')`, 4000);
  await clickSel('#en-physics .pf-chip[data-v="off"]');
  await mpIs(physStart);
  check(await mp() === physStart, 'Off takes its physics lines out (physics and bounce), in one step', firstDiff(await mp(), physStart));
  await waitFor(`!document.querySelector('#en-objects .en-phys')`, 4000);
  check(await badged() === '', 'and the badge goes', await badged());
  await physUndo(bounced);
  check(await mp() === bounced, 'one Ctrl+Z brings them both back', firstDiff(await mp(), bounced));
  await settle(25000);

  // Car and Ragdoll, in the Add tab's Physics tiles. A car the player gets into with F (1.3.0): with no player yet, the
  // Car tile brings one, standing by its door, and nothing drives by itself when the game starts.
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  const physTiles = await ev(`(() => { const c = [...document.querySelectorAll('#en-add .sd-cat')].find((x) => x.textContent === 'Physics'); const g = c?.nextElementSibling; return g ? [...g.querySelectorAll('.en-tile')].map((b) => b.dataset.tile + ':' + b.textContent).join() : null; })()`);
  check(physTiles === 'car:Car,ragdoll:Ragdoll', "a 3D world's Add tab has Physics tiles: Car and Ragdoll", physTiles);
  await clickSel('.en-tile[data-tile="car"]');
  await mpNot(bounced);
  const withCar = await mp();
  const carAdded = withCar.slice(bounced.length);
  const carM = /^car = game:car\((-?[\d.]+), 1, (-?[\d.]+), "red"\)\nplayer = game:player\("first person"\)\nplayer:move_to\((-?[\d.]+), 0, (-?[\d.]+)\)\n$/.exec(carAdded);
  const carSay = (await toasts()).filter((x) => /press F/.test(x)).pop() || '';
  check(withCar.startsWith(bounced) && carM && +carM[3] === +carM[1] - 2.5 && +carM[4] === +carM[2] && (await dbg()).sel === 'v:car' && /^Player came too: walk up to car and press F to get in/.test(carSay),
    'Car writes car = game:car(x, 1, z, "red"), and a player by its door (no car:drive(): nothing drives by itself), selects the car, and says F gets in', { carAdded, carSay });
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].some((h) => h.textContent === 'Car')`, 4000);
  await settle(25000);
  const carUi = await ev(`(() => { const s = [...document.querySelectorAll('#en-inspector .pf-sec')].find((x) => x.querySelector('.pf-sec-h')?.textContent === 'Car'); const nums = [...(s?.querySelectorAll('.en-num') || [])].map((l) => [l.querySelector('span').textContent, l.querySelector('input').value, l.querySelector('input').placeholder]); return { secs: [...document.querySelectorAll('#en-inspector .pf-sec-h')].map((h) => h.textContent).join(), text: s?.textContent || '', nums }; })()`);
  check(/Start in it/.test(carUi.text) && /presses F to get in/.test(carUi.text) && JSON.stringify(carUi.nums) === '[["Engine","1",""],["Weight","","1200"]]' && !/Behaviours|Moves/.test(carUi.secs),
    "the car's Inspector has a Car section (F gets in, Start in it, Engine 1, Weight 1200 as it is), and no Behaviours or Moves", carUi);
  check((await badged()).split(',').includes('v:car'), 'Objects badges the car: it always uses physics', await badged());
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  await clickSel('.en-tile[data-tile="ragdoll"]');
  await mpNot(withCar);
  const withDummy = await mp();
  check(withDummy.startsWith(withCar) && /^dummy = game:ragdoll\(-?[\d.]+, 0, -?[\d.]+, "blue"\)\n$/.test(withDummy.slice(withCar.length)), 'Ragdoll writes dummy = game:ragdoll(x, 0, z, "blue")', withDummy.slice(withCar.length));
  // A ragdoll dresses like a person: its Clothes and hair section writes dummy:hair("curly").
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].some((h) => h.textContent === 'Clothes and hair')`, 4000);
  const dressUi = await ev(`(() => { const s = [...document.querySelectorAll('#en-inspector .pf-sec')].find((x) => x.querySelector('.pf-sec-h')?.textContent === 'Clothes and hair'); return [...(s?.querySelectorAll('.pf-l') || [])].map((x) => x.textContent.split(' · ')[0]).join(); })()`);
  check(dressUi === 'Shirt,Trousers,Skin,Hair,Hair colour,Shoes,Sleeves', "the ragdoll's Inspector has Clothes and hair: shirt, trousers, skin, hair, hair colour, shoes and sleeves", dressUi);
  await ev(`(() => { const f = [...document.querySelectorAll('#en-inspector .pf')].find((x) => x.querySelector('.pf-l')?.textContent === 'Hair'); const s = f.querySelector('select'); s.value = 'curly'; s.dispatchEvent(new Event('change')); })()`);
  await mpNot(withDummy);
  const curly = await mp();
  check(curly === `${withDummy}dummy:hair("curly")\n`, 'choosing Curly writes dummy:hair("curly") under it', firstDiff(curly, `${withDummy}dummy:hair("curly")\n`));
  await settle(25000);
  await t.shot('engine_physics.png');
  check(/^OK/.test(ctx.tuffCheck((fs.writeFileSync(path.join(ctx.tmp, 'phys_check.tuf'), curly), path.join(ctx.tmp, 'phys_check.tuf'))).trim()), 'the physics and the look the Inspector and the tiles wrote pass tuff --check', ctx.tuffCheck(path.join(ctx.tmp, 'phys_check.tuf')));
  await physUndo(withDummy);
  await physUndo(withCar);
  check(await mp() === withCar, 'two Ctrl+Z take the hair and the ragdoll away', firstDiff(await mp(), withCar));
  // A car can be turned: its Look section has an Angle (car:turn_to, which tgame turns its body by too).
  await ev(`window.TuffEngine.test.select('v:car')`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].some((h) => h.textContent === 'Car')`, 4000);
  const carLook = await ev(`(() => { const s = [...document.querySelectorAll('#en-inspector .pf-sec')].find((x) => x.querySelector('.pf-sec-h')?.textContent === 'Look'); return [...(s?.querySelectorAll('.en-num span') || [])].map((x) => x.textContent).join(); })()`);
  check(carLook === 'Angle', "the car's Look section has an Angle, so it can face any way", carLook);
  // At Play the player walks up to the car, presses F to get in and drives off, and F gets out.
  check(/^OK/.test(ctx.tuffCheck((fs.writeFileSync(path.join(ctx.tmp, 'car_player.tuf'), withCar), path.join(ctx.tmp, 'car_player.tuf'))).trim()), 'and that world passes tuff --check', ctx.tuffCheck(path.join(ctx.tmp, 'car_player.tuf')));
  const rode = playCode('car_player', withCar, [{ at: 0.6, dump: 'a.json' }, { at: 0.8, key: 'f' }, { at: 1.1, dump: 'b.json' }, { at: 1.2, hold: 'w', for: 1.0 },
    { at: 2.4, key: 'f' }, { at: 2.7, dump: 'c.json' }, { at: 2.9, close: true }]);
  if (rode) {
    const ix = (n) => rode.dump(n)?.interact || {};
    check(rode.code === 0 && ix('a.json').hint === 'F: Get in' && ix('a.json').driving === false && ix('b.json').driving === true && ix('c.json').driving === false,
      'at Play the player starts by the car ("F: Get in"), F gets in and F again gets out', { code: rode.code, a: ix('a.json'), b: ix('b.json'), c: ix('c.json'), out: rode.out.slice(-300) });
  }
  // Start in it: the game starts with the player in the car (car:drive()). One car at a time: Start in it on for a
  // second car takes the first car's car:drive() out.
  const driveOn = () => ev(`(() => { const f = [...document.querySelectorAll('#en-inspector .pf')].find((x) => x.querySelector('.pf-l')?.textContent === 'Start in it'); const s = f?.querySelector('.switch'); if (s) s.id = 'en-test-drive'; return s ? s.querySelector('input').checked : null; })()`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-l')].some((x) => x.textContent === 'Start in it')`, 4000);
  check(await driveOn() === false, "car's Start in it is off", await driveOn());
  await clickSel('#en-test-drive');
  await mpNot(withCar);
  const startIn = await mp();
  const wantStart = withCar.replace(/(car = game:car\([^\n]*\)\n)/, '$1car:drive()\n');
  check(startIn === wantStart, 'Start in it on writes car:drive() under the car', firstDiff(startIn, wantStart));
  const started = playCode('car_start', startIn, [{ at: 0.6, dump: 'a.json' }, { at: 0.8, close: true }]);
  if (started) check(started.code === 0 && started.dump('a.json')?.interact?.driving === true, 'at Play the game starts with the player in the car', { code: started.code, ix: started.dump('a.json')?.interact, out: started.out.slice(-300) });
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  await clickSel('.en-tile[data-tile="car"]');
  await mpNot(startIn);
  const twoCars = await mp();
  check(/^car1 = game:car\(-?[\d.]+, 1, -?[\d.]+, "red"\)\n$/.test(twoCars.slice(startIn.length)) && (await dbg()).sel === 'v:car1', 'a second Car is just a car (the world has its player)', twoCars.slice(startIn.length));
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-l')].some((x) => x.textContent === 'Start in it')`, 4000);
  check(await driveOn() === false, "car1's Start in it is off", await driveOn());
  await clickSel('#en-test-drive');
  await mpNot(twoCars);
  const swapped = await mp();
  check(swapped === `${twoCars.replace('car:drive()\n', '')}car1:drive()\n`, 'Start in it on for car1 writes car1:drive() and takes car:drive() out, in one step: the player starts in one car', firstDiff(swapped, `${twoCars.replace('car:drive()\n', '')}car1:drive()\n`));
  await ev(`window.TuffEngine.test.select('v:car')`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-l')].some((x) => x.textContent === 'Start in it')`, 4000);
  check(await driveOn() === false, "and car's Inspector shows its Start in it off", await driveOn());
  await physUndo(twoCars);
  check(await mp() === twoCars, 'one Ctrl+Z puts the player back in car', firstDiff(await mp(), twoCars));
  await physUndo(startIn);
  await physUndo(withCar);
  // ================================================================ the Add tab: a wider panel, whole names, real pictures
  // The left panel is 340 px (wider than Design Studio's 240) and every tile's name shows whole (they wrap, nothing
  // is cut off with "..."). Each 3D tile gets a real picture from the game engine (a second preview page out of sight
  // draws them, and goes when they're made), and the preview of the game being edited carries on as it was.
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  const panel = await ev(`(() => { const l = document.querySelector('.en-left'); const lbls = [...document.querySelectorAll('#en-add .en-tile .lbl')]; return { w: Math.round(l.getBoundingClientRect().width), handle: !!l.querySelector('.en-resize'), cut: lbls.filter((x) => x.scrollWidth > x.clientWidth + 1 || getComputedStyle(x).textOverflow === 'ellipsis').map((x) => x.textContent), n: lbls.length }; })()`);
  check(panel.w >= 330 && panel.handle && panel.n > 25 && !panel.cut.length, `the Add panel is ${panel.w} px wide (drag its edge for more), and none of its ${panel.n} names is cut off`, panel);
  const picsDone = await waitFor(`(() => { const d = window.TuffEngine.debug().previews; return d.made >= 25 && !d.busy; })()`, 45000).then(() => true, () => false);
  const pics = await ev(`(() => { const tiles = [...document.querySelectorAll('#en-add .en-tile')]; const real = tiles.filter((b) => /^data:image\\/png/.test(b.querySelector('.en-shot.real img')?.src || '')).map((b) => b.dataset.tile); return { real, d: window.TuffEngine.debug().previews, frame: !!document.querySelector('#en-pvframe') }; })()`);
  const want = ['player', 'coin', 'car', 'ragdoll', 'door', 'jump_pad', 'person', 'tree', 'rock', 'house', 'sign', 'crate', 'box', 'ball', 'cone', 'island', 'ground', 'land'];
  check(picsDone && want.every((id) => pics.real.includes(id)) && !pics.frame, `every 3D tile gets a real picture from the engine (${pics.real.length} of them), and the out-of-sight page goes when they're made`, { missing: want.filter((id) => !pics.real.includes(id)), ...pics });
  check((await dbg()).loadedSeq === (await dbg()).loadSeq && !(await dbg()).banner, "making the pictures doesn't stop the game's own preview", await dbg());
  await t.shot('engine_add_pictures.png');
  await ev(`document.querySelector('.en-left').scrollTop = 640; 1`);
  await t.shot('engine_add_pictures_2.png');
  await ev(`document.querySelector('.en-left').scrollTop = 1400; 1`);
  await t.shot('engine_add_pictures_3.png');
  await ev(`document.querySelector('.en-left').scrollTop = 0; 1`);
  // A sign's words are written on its board: its Inspector calls the field "Sign text".
  await clickSel('.en-tile[data-tile="sign"]');
  await mpNot(withCar);
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-l')].some((x) => x.textContent === 'Sign text')`, 4000);
  const signUi = await ev(`(() => { const f = [...document.querySelectorAll('#en-inspector .pf')].find((x) => x.querySelector('.pf-l')?.textContent === 'Sign text'); return f ? f.textContent : null; })()`);
  check(/Written on its board/.test(signUi || ''), "a sign's Inspector has Sign text (written on its board), not a floating Label", signUi);
  // Physics on everything: a cone has its Physics section too, and a door says why it has none.
  await physUndo(withCar);
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  await clickSel('.en-tile[data-tile="cone"]');
  await mpNot(withCar);
  await waitFor(`!!document.querySelector('#en-physics')`, 4000);
  check(await ev(`!!document.querySelector('#en-physics .pf-chip[data-v="dynamic"]')`), 'a cone has Physics in its Inspector (Off, Falls, Fixed): everything in the world can', null);
  await physUndo(withCar);
  const physBanner = (await dbg()).banner;
  if (physBanner) t.info(`the scene stops at the physics lines until tgame's runtime has them: ${physBanner.slice(0, 120)}`);

  // ================================================================ the game kit: the 3D Add tab's Level pieces
  // Door, Key (it locks the door: door:needs(key) after the key), Jump pad, Boost pad, Moving platform (a stone box and
  // its lift:path line) and Talking person (a person and its npc:say line), each one undo step, and what they write
  // passes tuff --check. Objects lists them, and a door's and a pad's Inspector has no Behaviours or Moves.
  const kitFile = path.join(ctx.root, 'kit.tuf');
  const kitStart = 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\ngame:island(80)\n';
  fs.writeFileSync(kitFile, kitStart);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(kitFile)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(kitFile)}`, 6000);
  await settle(25000);
  const mk = () => ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kitFile)})).getValue().replace(/\\r\\n/g, '\\n'))()`);
  const mkNot = (was) => waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kitFile)})).getValue().replace(/\\r\\n/g, '\\n') !== ${JSON.stringify(was)})()`, 6000);
  const mkIs = (want) => waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kitFile)})).getValue().replace(/\\r\\n/g, '\\n') === ${JSON.stringify(want)})()`, 6000);
  await clickSel('.en-left .en-tabs button[data-tab="add"]');
  const kitTiles = await ev(`(() => { const c = [...document.querySelectorAll('#en-add .sd-cat')].find((x) => x.textContent === 'Level pieces'); const g = c?.nextElementSibling; return g ? [...g.querySelectorAll('.en-tile')].map((b) => b.dataset.tile + ':' + b.textContent).join() : null; })()`);
  check(kitTiles === 'door:Door,key:Key,jump_pad:Jump pad,boost_pad:Boost pad,platform:Moving platform,person:Talking person', "a 3D world's Add tab has Level pieces: Door, Key, Jump pad, Boost pad, Moving platform and Talking person", kitTiles);
  const N = '-?[\\d.]+';
  const kitSteps = [
    ['door', `^door = game:door\\(${N}, 0, ${N}, "wood"\\)\\n$`, 'Door writes door = game:door(x, 0, z, "wood")'],
    ['key', `^key = game:spawn\\("key", ${N}, 0, ${N}\\)\\ndoor:needs\\(key\\)\\n$`, 'Key writes key = game:spawn("key", x, 0, z), then door:needs(key): the door is locked until the player has it'],
    ['jump_pad', `^pad = game:jump_pad\\(${N}, 0, ${N}, 15\\)\\n$`, 'Jump pad writes pad = game:jump_pad(x, 0, z, 15)'],
    ['boost_pad', `^boost = game:boost_pad\\(${N}, 0, ${N}, 20\\)\\n$`, 'Boost pad writes boost = game:boost_pad(x, 0, z, 20)'],
    ['platform', `^lift = game:box\\((${N}), 1, (${N}), \\[4, 0\\.4, 4\\], "stone"\\)\\nlift:path\\(\\[\\[\\1, 1, \\2\\], \\[${N}, 1, \\2\\]\\], 3\\)\\n$`, 'Moving platform writes a stone box, then lift:path([[x, 1, z], [x + 8, 1, z]], 3)'],
    ['person', `^person = game:spawn\\("person", ${N}, 0, ${N}\\)\\nperson:say\\("Hi there!", 0\\)\\n$`, 'Talking person writes person = game:spawn("person", x, 0, z), then person:say("Hi there!", 0)'],
  ];
  let kitCode = kitStart;
  for (const [tile, re, what] of kitSteps) {
    await clickSel('.en-left .en-tabs button[data-tab="add"]');
    await clickSel(`.en-tile[data-tile="${tile}"]`);
    await mkNot(kitCode);
    const now = await mk();
    const added = now.slice(kitCode.length);
    check(now.startsWith(kitCode) && new RegExp(re).test(added), what, added);
    kitCode = now;
    await settle(25000);
  }
  const kitObjects = await ev(`[...document.querySelectorAll('#en-objects .sd-layer')].map((r) => r.dataset.key).join()`);
  check(['v:door', 'v:key', 'v:pad', 'v:boost', 'v:lift', 'v:person'].every((k) => kitObjects.split(',').includes(k)), 'Objects lists the door, the key, both pads, the platform and the person', kitObjects);
  await ev(`window.TuffEngine.test.select('v:door')`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].some((h) => h.textContent === 'Look')`, 4000);
  const doorSecs = await ev(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].map((h) => h.textContent).join()`);
  check(!/Behaviours|Moves/.test(doorSecs), "a door's Inspector has no Behaviours or Moves", doorSecs);
  await ev(`window.TuffEngine.test.select('v:pad')`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .en-num span')].some((x) => x.textContent === 'Power')`, 4000);
  const padPower = await ev(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span')?.textContent === 'Power'); return l?.querySelector('input')?.value; })()`);
  check(padPower === '15', "a jump pad's Inspector shows its Power (15)", padPower);
  await t.shot('engine_level_pieces.png');
  const kitCheck = path.join(ctx.tmp, 'kit_check.tuf');
  fs.writeFileSync(kitCheck, kitCode);
  check(/^OK/.test(ctx.tuffCheck(kitCheck).trim()), 'the level pieces the tiles wrote pass tuff --check', ctx.tuffCheck(kitCheck));
  const beforePerson = kitCode.slice(0, kitCode.indexOf('person = '));
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await mkIs(beforePerson);
  check(await mk() === beforePerson, 'one Ctrl+Z takes the talking person and its speech bubble away', firstDiff(await mk(), beforePerson));
  const kitBanner = (await dbg()).banner;
  if (kitBanner) t.info(`the scene stops at the level pieces until tgame's runtime has them: ${kitBanner.slice(0, 120)}`);
  await settle(25000);

  // Turning a boost pad and a door: their Inspector has an Angle, typed in like a kid (boost:turn_to 90 right after
  // the pad), so a boost pad shoots the player the way the kid wants and a door fits a wall that runs along z.
  const angleIn = async (text) => {
    let r = null;
    for (let tries = 0; tries < 20 && !r; tries++) {
      r = await ev(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span')?.textContent === 'Angle'); const i = l && l.querySelector('input'); if (!i) return null; i.id = 'en-test-angle'; i.scrollIntoView({ block: 'center' }); const b = i.getBoundingClientRect(); return b.width ? [b.left, b.top] : null; })()`);
      if (!r) await t.sleep(100);
    }
    if (!r) return false;
    await t.click(r[0] + 20, r[1] + 10);
    await key('a', 'KeyA', 65, CTRL);
    await ev(`document.activeElement?.select?.(); 1`);
    await t.type(text, 30);
    return true;
  };
  const inspSecs = () => ev(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].map((h) => h.textContent).join()`);
  await ev(`window.TuffEngine.test.select('v:boost')`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .en-num span')].some((x) => x.textContent === 'Power')`, 4000);
  check(await angleIn('90'), "a boost pad's Inspector has an Angle (which way it shoots the player)", await inspSecs());
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kitFile)})).getValue().includes('boost:turn_to 90'))()`, 4000);
  await ev(`document.querySelector('#en-stage').focus()`);
  const boostLine = kitCode.split('\n').find((l) => l.startsWith('boost = '));
  const turnedBoost = await mk();
  check(turnedBoost === beforePerson.replace(`${boostLine}\n`, `${boostLine}\nboost:turn_to 90\n`), 'typing 90 in it writes boost:turn_to 90 right after the boost pad', firstDiff(turnedBoost, beforePerson.replace(`${boostLine}\n`, `${boostLine}\nboost:turn_to 90\n`)));
  await settle(25000);
  const boostHeading = await ev(`(() => { const i = window.TuffEngine.test.thingsOf('v:boost')[0]; return window.TuffEngine.test.dump()?.things?.[i]?.heading ?? null; })()`);
  check(boostHeading === 90, 'and the preview turns it', boostHeading);
  await ev(`window.TuffEngine.test.select('v:door')`);
  await waitFor(`[...document.querySelectorAll('#en-inspector .pf-sec-h')].some((h) => h.textContent === 'Look')`, 4000);
  check(await angleIn('90'), "a door's Inspector has an Angle too", await inspSecs());
  await waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(kitFile)})).getValue().includes('door:turn_to 90'))()`, 4000);
  await ev(`document.querySelector('#en-stage').focus()`);
  const turnedDoor = await mk();
  check(turnedDoor === turnedBoost.replace('door:needs(key)\n', 'door:needs(key)\ndoor:turn_to 90\n'), 'typing 90 writes door:turn_to 90 after its lines, so it fits a wall that runs along z', firstDiff(turnedDoor, turnedBoost.replace('door:needs(key)\n', 'door:needs(key)\ndoor:turn_to 90\n')));
  const turnedCheck = path.join(ctx.tmp, 'kit_turned.tuf');
  fs.writeFileSync(turnedCheck, turnedDoor);
  check(/^OK/.test(ctx.tuffCheck(turnedCheck).trim()), 'the turned door and boost pad pass tuff --check', ctx.tuffCheck(turnedCheck));
  // (Only the steps that happened are undone, so a failure here doesn't undo the tiles above.)
  for (const changed of [turnedBoost !== beforePerson, turnedDoor !== turnedBoost]) if (changed) await t.key('z', CTRL);
  await mkIs(beforePerson);
  check(await mk() === beforePerson, 'two Ctrl+Z turn them back', firstDiff(await mk(), beforePerson));
  await settle(25000);

  // A moving platform's path goes with it: its spots are places in the world, so moving the platform moves each spot
  // by as much, in the same step (otherwise at Play it slides back to where it was put). Shift+Right nudges it 2.
  const n2 = (v) => String(+(+v).toFixed(2));
  const liftLine = kitCode.split('\n').find((l) => l.startsWith('lift = '));
  const [, liftX, liftZ] = liftLine.match(/^lift = game:box\((-?[\d.]+), 1, (-?[\d.]+),/);
  const pathFor = (x, z) => `lift:path([[${n2(x)}, 1, ${n2(z)}], [${n2(+x + 8)}, 1, ${n2(z)}]], 3)`;
  await ev(`window.TuffEngine.test.select('v:lift')`);
  await ev(`document.querySelector('#en-stage').focus()`);
  await key('ArrowRight', 'ArrowRight', 39, SHIFT);
  await mkNot(beforePerson);
  const nudgedLift = await mk();
  const nudgedLines = changedLines(beforePerson, nudgedLift)?.map((l) => l[2]);
  check(nudgedLines?.join('\n') === `lift = game:box(${n2(+liftX + 2)}, 1, ${liftZ}, [4, 0.4, 4], "stone")\n${pathFor(+liftX + 2, liftZ)}`, "Shift+Right nudges the platform 2 along, and its path's spots with it", nudgedLines);
  await settle(25000);
  const liftAt = gl ? await onScreen(await thingOf('v:lift')) : null;
  if (liftAt) {
    await drag(liftAt[0], liftAt[1], liftAt[0] + 110, liftAt[1] + 40, 10);
    await mkNot(nudgedLift);
    const draggedLift = changedLines(nudgedLift, await mk())?.map((l) => l[2]);
    const dm = draggedLift?.[0]?.match(/^lift = game:box\((-?[\d.]+), 1, (-?[\d.]+), \[4, 0\.4, 4\], "stone"\)$/);
    check(dm && draggedLift.length === 2 && draggedLift[1] === pathFor(dm[1], dm[2]), "dragging the platform moves it, and its path's spots with it, in one line each", draggedLift);
    if (await mk() !== nudgedLift) { await ev(`document.querySelector('#en-stage').focus()`); await t.key('z', CTRL); }
    await mkIs(nudgedLift);
    check(await mk() === nudgedLift, 'one Ctrl+Z puts the platform and its path back', firstDiff(await mk(), nudgedLift));
  }
  if (nudgedLift !== beforePerson) { await ev(`document.querySelector('#en-stage').focus()`); await t.key('z', CTRL); }
  await mkIs(beforePerson);
  check(await mk() === beforePerson, 'one Ctrl+Z undoes the nudge, path and all', firstDiff(await mk(), beforePerson));
  await settle(25000);

  // Deleting the key takes the door:needs(key) line it wrote with it (or the door would need a key that's gone, and
  // the game would stop there), and says so.
  await ev(`window.TuffEngine.test.select('v:key')`);
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('Delete');
  await mkNot(beforePerson);
  const noKey = await mk();
  const keyLine = kitCode.split('\n').find((l) => l.startsWith('key = '));
  check(noKey === beforePerson.replace(`${keyLine}\ndoor:needs(key)\n`, ''), "Delete on the key takes its line and the door's door:needs(key) out, in one step", firstDiff(noKey, beforePerson.replace(`${keyLine}\ndoor:needs(key)\n`, '')));
  const keySay = (await toasts()).filter((x) => /^Removed/.test(x)).pop();
  check(keySay === "Removed key, and door's lock, which needed it. Ctrl+Z brings it back.", 'and says the door has no lock now', keySay);
  const noKeyCheck = path.join(ctx.tmp, 'kit_no_key.tuf');
  fs.writeFileSync(noKeyCheck, noKey);
  check(/^OK/.test(ctx.tuffCheck(noKeyCheck).trim()), 'what is left passes tuff --check', ctx.tuffCheck(noKeyCheck));
  const noKeyRun = playCode('kit_no_key', noKey, [{ at: 0.6, dump: 'a.json' }, { at: 0.8, close: true }]);
  if (noKeyRun) check(noKeyRun.code === 0 && !/Tuff error/.test(noKeyRun.out) && noKeyRun.dump('a.json'), 'and it plays (no "I don\'t know what \'key\' is")', noKeyRun.out.slice(-300));
  if (noKey !== beforePerson) { await ev(`document.querySelector('#en-stage').focus()`); await t.key('z', CTRL); }
  await mkIs(beforePerson);
  check(await mk() === beforePerson, 'one Ctrl+Z brings the key and its lock back', firstDiff(await mk(), beforePerson));
  await settle(25000);

  // ================================================================ the land: the Terrain tab, its tools, Lighting, Hills and Lake
  // A world on an island: the Terrain tab offers to swap the island for land (one step), then the brush, a hill, a
  // valley and the style each write one line (one Ctrl+Z each), the preview paints live, the Objects list and the
  // Inspector change and remove the land's lines, the World gets modern lighting, and the template is a real game.
  const landFile = path.join(ctx.root, 'land.tuf');
  const landStart = 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\ngame:island(80)\nplayer = game:player("first person")\n';
  fs.writeFileSync(landFile, landStart);
  await ev(`window.TuffIDE.openEngine(${JSON.stringify(landFile)})`);
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(landFile)}`, 6000);
  await settle(25000);
  const ml = () => ev(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(landFile)})).getValue().replace(/\\r\\n/g, '\\n'))()`);
  const mlIs = (want) => waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(landFile)})).getValue().replace(/\\r\\n/g, '\\n') === ${JSON.stringify(want)})()`, 6000);
  const mlNot = (was) => waitFor(`(async () => (await window.TuffIDE.getModel(${JSON.stringify(landFile)})).getValue().replace(/\\r\\n/g, '\\n') !== ${JSON.stringify(was)})()`, 6000);
  // Where a point of the land is in the IDE window.
  const landSpot = async (x, z) => {
    const f = await rect('#en-frame');
    const p = (await ask('spot', { x, z })).value;
    return p ? [f[0] + p[0], f[1] + p[1]] : null;
  };
  const landH = async (x, z) => (await ask('height', { x, z })).value;
  const undoKey = async () => { await ev(`document.querySelector('#en-stage').focus()`); await t.key('z', CTRL); };
  check(await ev(`!document.querySelector('.en-tabs [data-tab="terrain"]').classList.contains('hidden') && document.querySelector('.en-tabs').classList.contains('four')`), 'a 3D world has a fourth tab: Terrain', null);
  await clickSel('.en-left .en-tabs button[data-tab="terrain"]');
  const startText = await ev(`document.querySelector('#en-terrain').textContent`);
  check(/Make some land/.test(startText) && /Swap the island for land/.test(startText) && /Keep the island too/.test(startText), 'with no land, the Terrain tab offers Make some land, and to swap the island for it', startText);
  await t.shot('engine_terrain_start.png');
  await clickSel('#en-terrain [data-a="swap"]');
  const withLand = 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\nland = game:terrain(200)\nland:style "grass"\nplayer = game:player("first person")\n';
  await mlIs(withLand);
  check(await ml() === withLand, 'Swap the island for land writes land = game:terrain(200) and land:style "grass" where the island was', firstDiff(await ml(), withLand));
  await undoKey();
  await mlIs(landStart);
  check(await ml() === landStart, 'one Ctrl+Z brings the island back', firstDiff(await ml(), landStart));
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('y', CTRL);
  await mlIs(withLand);
  await settle(25000);
  await t.sleep(500);
  st = await stats();
  if (gl) check(st.land?.drawn === true && st.land.size === 200 && st.cam?.dist >= 70, 'the preview draws the land, and the camera steps back to see it', st);
  const tools = await ev(`[...document.querySelectorAll('#en-terrain .en-tool')].map((b) => b.dataset.tool).join()`);
  check(tools === 'raise,lower,smooth,flatten,hill,mountain,dip,lake,valley', 'the Terrain tab has the brushes (Raise, Lower, Smooth, Flatten) and the shapes (Hill, Mountain, Dip, Lake, Valley)', tools);

  // Raise: a drag paints the land live, and writes one line when it's let go.
  await clickSel('#en-terrain .en-tool[data-tool="raise"]');
  const sliders = await ev(`[...document.querySelectorAll('#en-terrain .en-slider')].map((l) => l.textContent + '=' + l.querySelector('input').min + '..' + l.querySelector('input').max).join(' | ')`);
  check((await dbg()).tool === 'raise' && /^Size12=2\.\.60 \| Strength1=0\.2\.\.5$/.test(sliders) && /Drag on the land to raise it/.test(await ev(`document.querySelector('#en-hint').textContent`)),
    'Raise turns on with its Size (2-60) and Strength (0.2-5) sliders, and the hint says how', { sliders, hint: await ev(`document.querySelector('#en-hint').textContent`) });
  await t.shot('engine_terrain_tools.png');
  let was = await ml();
  if (gl) {
    const b0 = await landSpot(-30, 10);
    const b1 = await landSpot(-6, 10);
    const h0 = await landH(-18, 10);
    await drag(b0[0], b0[1], b1[0], b1[1], 14);
    const h1 = await landH(-18, 10);
    await mlNot(was);
    const added = (await ml()).split('\n').filter((l) => !was.split('\n').includes(l));
    check(added.length === 1 && /^land:raise\(\[\[-?[\d.]+, -?[\d.]+\](, \[-?[\d.]+, -?[\d.]+\]){2,}\], 12, 1\)$/.test(added[0]) && (await ml()).split('\n')[6] === added[0],
      'a drag with Raise writes one land:raise line with the stroke\'s spots, after the land\'s lines', added);
    check(h1 > h0 + 1, `and the preview's land rose while it was dragged (${h0} -> ${h1?.toFixed?.(2)})`, { h0, h1 });
    check((await dbg()).sel.startsWith('le:'), 'the new line is selected', (await dbg()).sel);
    await settle();
    await t.shot('engine_terrain_raised.png');
    await undoKey();
    await mlIs(was);
    check(await ml() === was, 'one Ctrl+Z undoes the whole stroke', firstDiff(await ml(), was));
    await settle();
    // A click with Hill puts a hill there.
    await clickSel('#en-terrain .en-tool[data-tool="hill"]');
    const hs = await landSpot(24, -16);
    await t.click(hs[0], hs[1]);
    await mlNot(was);
    const hillLine = (await ml()).split('\n')[6];
    const hm = /^land:hill\((-?[\d.]+), (-?[\d.]+), 30, 8\)$/.exec(hillLine);
    check(hm && Math.abs(+hm[1] - 24) < 2 && Math.abs(+hm[2] + 16) < 2, 'a click with Hill writes land:hill(x, z, 30, 8) where it was clicked', hillLine);
    await settle();
    // A drag with Valley carves one from where it starts to where it ends.
    await clickSel('#en-terrain .en-tool[data-tool="valley"]');
    was = await ml();
    const v0 = await landSpot(-40, -30);
    const v1 = await landSpot(-4, -40);
    await drag(v0[0], v0[1], v1[0], v1[1], 12);
    await mlNot(was);
    const valleyLine = (await ml()).split('\n')[7];
    const vm = /^land:valley\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+), (-?[\d.]+), 18, 6\)$/.exec(valleyLine);
    check(vm && Math.abs(+vm[1] + 40) < 3 && Math.abs(+vm[3] + 4) < 3, 'a drag with Valley writes land:valley(x1, z1, x2, z2, 18, 6) from its start to its end', valleyLine);
    await settle();
    await ev(`document.querySelector('#en-stage').focus()`);
    await t.key('Escape');
    check((await dbg()).tool === null && !(await ev(`!!document.querySelector('#en-terrain .en-tool.on')`)), 'Escape puts the tool away', await dbg());
  }
  // Style: a chip changes the style line.
  was = await ml();
  await clickSel('#en-terrain .en-styles [data-style="desert"]');
  await mlNot(was);
  const styleLines = changedLines(was, await ml());
  check(styleLines && styleLines.length === 1 && styleLines[0][2] === 'land:style "desert"', 'the Desert style changes the land:style line', styleLines);
  await settle();
  await t.shot('engine_terrain_desert.png');
  // Lighting: Modern in the World's Inspector.
  await ev(`window.TuffEngine.test.select('root')`);
  await t.sleep(200);
  was = await ml();
  await clickSel('#en-lighting .pf-chip:nth-child(2)');
  await mlNot(was);
  const litAdded = (await ml()).split('\n');
  check(litAdded[4] === 'game:lighting "modern"' && litAdded.length === was.split('\n').length + 1, 'Lighting: Modern in the World writes game:lighting "modern" with its settings', litAdded.slice(0, 7));
  await settle();
  if (gl) check((await stats()).modern === true, 'and the preview has modern lighting', await stats());
  // The Objects list: the land and its lines; a line selected, changed and removed in the Inspector.
  await clickSel('.en-left .en-tabs button[data-tab="objects"]');
  const objRows = await ev(`[...document.querySelectorAll('#en-objects .sd-layer')].map((r) => r.dataset.key + ':' + r.querySelector('.lb').textContent).join()`);
  check(/^root:World,land:Land(,le:\d+:(Hill|Valley))*,v:player:Player$/.test(objRows), 'Objects lists the land with its lines under it', objRows);
  if (gl) {
    const hillKey = (await dbg()).land.edits.find((e) => e.op === 'hill').key;
    await clickSel(`#en-objects .sd-layer[data-key="${hillKey}"]`);
    await waitFor(`window.TuffEngine.debug().sel === ${JSON.stringify(hillKey)}`, 3000);
    const fields = await ev(`[...document.querySelectorAll('#en-inspector .en-num span')].map((x) => x.textContent).join()`);
    check(fields === 'X,Z,Size,Height', 'its Inspector has X, Z, Size and Height', fields);
    await t.shot('engine_terrain_inspector.png');
    was = await ml();
    await ev(`(() => { const l = [...document.querySelectorAll('#en-inspector .en-num')].find((x) => x.querySelector('span').textContent === 'Height'); const i = l.querySelector('input'); i.focus(); i.value = '12'; i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); i.blur(); return 1; })()`);
    await mlNot(was);
    const hl = changedLines(was, await ml());
    check(hl && hl.length === 1 && /^land:hill\(-?[\d.]+, -?[\d.]+, 30, 12\)$/.test(hl[0][2]), 'changing Height to 12 changes the hill\'s line', hl);
    was = await ml();
    await clickSel('#en-inspector .in-actions .btn.danger');
    await mlNot(was);
    check(!/land:hill/.test(await ml()) && (await dbg()).sel === 'land', 'Remove takes the hill\'s line out (and selects the land)', await ml());
    await undoKey();
    await mlIs(was);
    check(await ml() === was, 'Ctrl+Z brings it back', firstDiff(await ml(), was));
  }
  check(/^OK/.test(ctx.tuffCheck((fs.writeFileSync(path.join(ctx.tmp, 'land_check.tuf'), await ml()), path.join(ctx.tmp, 'land_check.tuf'))).trim()), 'the land the Terrain tab wrote passes tuff --check', ctx.tuffCheck(path.join(ctx.tmp, 'land_check.tuf')));

  // The Hills and Lake template: a new file that tgame plays (games/hills_lake.tuf), with land and modern light.
  await clickSel('#en-templates');
  await waitFor(`document.querySelectorAll('.sd-modal .sd-tcard').length === 5`, 3000);
  await ev(`document.querySelector('.sd-tcard[data-id="hills_lake"] [data-a="new"]').click()`);
  const hillsFile = path.join(ctx.root, 'hills_lake.tuf');
  await waitFor(`window.TuffEngine.debug().file === ${JSON.stringify(hillsFile)}`, 6000);
  check(fs.existsSync(hillsFile) && fs.readFileSync(hillsFile, 'utf8') === repoGame('hills_lake.tuf'), 'Hills and Lake (3D) makes hills_lake.tuf from the template', null);
  check(/^OK/.test(ctx.tuffCheck(hillsFile).trim()), 'and its code passes tuff --check', ctx.tuffCheck(hillsFile));
  await settle(25000);
  await t.sleep(800);
  const dh = await dbg();
  check(!dh.error && dh.land?.edits.map((e) => e.op).join() === 'hill,mountain,lake,valley' && dh.behaviours.length === 1, 'it has the land with a hill, a mountain, a lake and a valley, and the coin to collect', dh);
  if (gl) {
    st = await stats();
    check(st.land?.drawn && st.modern === true && st.land.high > 20, 'the preview shows the land (the mountain is tall) in modern light', st);
  }
  await clickSel('.en-left .en-tabs button[data-tab="terrain"]');
  await t.shot('engine_terrain_hills_lake.png');
  await clickSel('.en-left .en-tabs button[data-tab="add"]');

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
  const fx = await ev(`['coin_dash', 'island_walk', 'hills_lake'].every((id) => { const c = window.TuffEngine.templates().find((t) => t.id === id).code.split('\\n'); return window.TuffEngine.fixups(c).join('\\n') === c.join('\\n'); })`);
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
  // A moving platform's path moves with it, in the same step: X, Y and Z (a drag and a nudge do the same), and
  // Duplicate (the copy gets its own path, 2 along). Spots on the land ([x, z]) move too; a spot from code can't, so
  // that path stays as it is and Tuff Engine says so.
  const liftSrc = 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\ngame:island(80)\nlift = game:box(0, 1, -6, [4, 0.4, 4], "stone")\nlift:path([[0, 1, -6], [8, 1, -6]], 3)\n';
  const liftLines = (src) => changedLines(liftSrc, src)?.map((l) => l[2]).join('\n');
  const liftMoved = await edit(liftSrc, `(P, E) => E.setArgs(P, P.byVar.lift, { x: 10, y: 1, z: -20 })`);
  check(liftLines(liftMoved) === 'lift = game:box(10, 1, -20, [4, 0.4, 4], "stone")\nlift:path([[10, 1, -20], [18, 1, -20]], 3)', "the platform moved to 10, 1, -20: its path's spots move with it", liftLines(liftMoved));
  const liftUp = await edit(liftSrc, `(P, E) => E.setArgs(P, P.byVar.lift, { x: 0, y: 4, z: -6 })`);
  check(liftLines(liftUp) === 'lift = game:box(0, 4, -6, [4, 0.4, 4], "stone")\nlift:path([[0, 4, -6], [8, 4, -6]], 3)', 'Y (bottom) 4: its path goes up too', liftLines(liftUp));
  const liftTwin = await edit(liftSrc, `(P, E) => E.duplicate(P, P.byVar.lift)`);
  check(liftTwin === `${liftSrc}lift1 = game:box(2, 1, -6, [4, 0.4, 4], "stone")\nlift1:path([[2, 1, -6], [10, 1, -6]], 3)\n`, 'Duplicate: the copy gets its own path, 2 along like the copy (not the same track)', firstDiff(liftTwin, `${liftSrc}lift1 = game:box(2, 1, -6, [4, 0.4, 4], "stone")\nlift1:path([[2, 1, -6], [10, 1, -6]], 3)\n`));
  const landLift = liftSrc.replace('[[0, 1, -6], [8, 1, -6]]', '[[0, -6], [8, -6]]');
  const landMoved = await edit(landLift, `(P, E) => E.setArgs(P, P.byVar.lift, { x: 2, y: 1, z: -8 })`);
  check(changedLines(landLift, landMoved)?.[1]?.[2] === 'lift:path([[2, -8], [10, -8]], 3)', 'spots on the land ([x, z]) move along the land', changedLines(landLift, landMoved));
  const codeLift = liftSrc.replace('lift:path([[0, 1, -6], [8, 1, -6]], 3)', 'lift:path([[0, 1, -6], [far, 1, -6]], 3)').replace('lift = ', 'far = 8\nlift = ');
  const codeMoved = await edit(codeLift, `(P, E) => E.setArgs(P, P.byVar.lift, { x: 10, y: 1, z: -20 })`);
  const pathSay = (await toasts()).pop();
  check(changedLines(codeLift, codeMoved)?.length === 1 && pathSay === "Lift's path has a spot that comes from code, so it stays where it was. Change its spots in the code.", 'a path with a spot from code (far) stays as it is, and Tuff Engine says so', { lines: changedLines(codeLift, codeMoved), pathSay });
  const liftPlay = playCode('lift_moved', liftMoved, [{ at: 0.5, dump: 'a.json' }, { at: 2.4, dump: 'b.json' }, { at: 2.6, close: true }]);
  if (liftPlay) {
    const at = (n) => liftPlay.dump(n)?.objects?.find((o) => o[0] === 'box');
    const [la, lb] = [at('a.json'), at('b.json')];
    check(liftPlay.code === 0 && la && lb && Math.abs(la[3] + 20) < 0.1 && Math.abs(lb[3] + 20) < 0.1 && la[1] >= 9.9 && lb[1] > la[1] + 2 && lb[1] <= 18.1,
      `at Play it rides its own track from where it was put (x ${la?.[1]} → ${lb?.[1]}, z ${la?.[3]} and ${lb?.[3]}), not back to the old one`, { code: liftPlay.code, la, lb, out: liftPlay.out.slice(-300) });
  }
  // A car's Angle (car:turn_to) is one of its own lines, read back as the car's (so its Inspector shows it).
  const carSrc = 'mention tgame\n\ngame = tgame.world("My World", 960, 600)\ngame:sky "day"\ngame:island(80)\ncar = game:car(0, 1, -6, "red")\ncar:drive()\n';
  const carTurned = await edit(carSrc, `(P, E) => E.setProp(P, P.byVar.car, 'turn_to', [90])`);
  const carAngle = await ev(`window.TuffEngine.parse(${JSON.stringify(carTurned)}).byVar.car.props.turn_to?.args[0] ?? null`);
  check(carTurned === `${carSrc}car:turn_to 90\n` && carAngle === 90, "a car's Angle 90 writes car:turn_to 90 after its lines, and Tuff Engine reads it back as the car's", { carTurned, carAngle });

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
  const undoSeq = (await dbg()).loadSeq;
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(slowBefore)}`, 4000);
  check(await code() === slowBefore, 'and one Ctrl+Z takes the whole 250 back to 120', firstDiff(await code(), slowBefore));
  await settleSince(undoSeq);
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
  const undoSeq2 = (await dbg()).loadSeq;
  await ev(`document.querySelector('#en-stage').focus()`);
  await t.key('z', CTRL);
  await waitFor(`window.__code() === ${JSON.stringify(slowBefore)}`, 4000);
  check(await code() === slowBefore, 'one Ctrl+Z puts 800 back', firstDiff(await code(), slowBefore));
  await settleSince(undoSeq2);
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
