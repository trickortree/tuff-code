// "Run a second player" beside Run: a second copy of a multiplayer tgame game, so one copy hosts and the other
// joins on this one computer. The button only shows for a file that uses :host( or :join(. Both copies really
// run (two processes with the game's path), the joining copy says it joined, and the Run panel marks each line
// P1 or P2. The second player's button stops only it, Stop ends both, and closing TuffCode ends both too.
// Rooms stay on 127.0.0.1 (TUFF_NET_LOCAL=1) on ports of this test's own. A checkout needs pywebview in its Python.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { python } from '../launch.mjs';

export const meta = {
  title: 'Run a second player: two copies of a multiplayer game',
  timeout: 300000,
  env: { TUFF_NET_LOCAL: '1', TUFF_NET_PORT: '47990' },
};

// Each copy looks for the room for 3 seconds and hosts it if nobody's there: the first copy hosts, the second joins.
const GAME = `mention tgame

game = tgame.window("Second Player", 420, 300)
game:background "navy"
game:join("Second Room")

func joined(name):
    say "joined " + name

func alone():
    if not game:connected():
        game:leave()
        game:host("Second Room")
        say "hosting " + text(game:hosting())

game:on_join(joined)
game:after(3, alone)
`;

// The copies of a program running now: processes with its path in their command line, less their own children
// (on Windows py.exe starts python.exe).
function copiesRunning(file) {
  let rows;
  if (process.platform === 'win32') {
    const ps = `Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine.ToLower().Contains('${file.toLowerCase().replace(/'/g, "''")}') } | ForEach-Object { "$($_.ProcessId) $($_.ParentProcessId)" }`;
    const r = spawnSync('powershell', ['-NoProfile', '-Command', ps], { encoding: 'utf8', windowsHide: true });
    rows = (r.stdout || '').split(/\r?\n/).filter((l) => l.trim()).map((l) => l.trim().split(/\s+/).map(Number));
  } else {
    const r = spawnSync('ps', ['-A', '-o', 'pid=,ppid=,command='], { encoding: 'utf8' });
    rows = (r.stdout || '').split('\n').filter((l) => l.includes(file)).map((l) => l.trim().split(/\s+/).slice(0, 2).map(Number));
  }
  const pids = new Set(rows.map(([pid]) => pid));
  return rows.filter(([, ppid]) => !pids.has(ppid)).length;
}

export default async (t, ctx) => {
  const check = (ok, label, got) => t.check(label, ok, got);
  const ev = (js) => t.eval(js);
  if (!ctx.packaged) {
    const py = python();
    if (!py || spawnSync(py[0], [...py.slice(1), '-c', 'import webview'], { windowsHide: true }).status !== 0) {
      t.skip('the second player', 'the Python that runs tuff.py has no pywebview (py -m pip install pywebview)');
      return;
    }
  }
  const game = path.join(ctx.root, 'second_player.tuf');
  const plain = path.join(ctx.root, 'no_rooms.tuf');
  fs.writeFileSync(game, GAME);
  fs.writeFileSync(plain, 'say "no multiplayer here"\n');
  const open = (f) => ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(f)}); return 1; })()`);
  const shown = () => ev(`!document.querySelector('#btn-run2').classList.contains('hidden')`);
  const out = () => ev(`document.querySelector('#run-output').innerText`);
  // JS for the page: how many of a copy's lines match, and whether one does.
  const count = (re, who) => `[...document.querySelectorAll('#run-output > span')].filter((s) => s.classList.contains('p2') === ${who === 2} && ${re}.test(s.textContent)).length`;
  const said = (re, who, n = 1) => `${count(re, who)} >= ${n}`;
  const waitCopies = async (n, ms) => {
    const end = Date.now() + ms;
    let got = copiesRunning(game);
    while (got !== n && Date.now() < end) { await t.sleep(400); got = copiesRunning(game); }
    return got;
  };

  // Only for a file that hosts or joins.
  await open(plain);
  await t.sleep(500);
  check(!(await shown()), 'a file with no game:host or game:join: no "Run a second player" button', await shown());
  await ev(`(() => { const m = window.TuffIDE.editor().getModel(); m.setValue(m.getValue() + 'game:join()\\n'); return 1; })()`);
  const typed = await t.waitFor(`!document.querySelector('#btn-run2').classList.contains('hidden')`, 3000);
  check(typed, 'typing game:join() in it shows the button', await shown());
  await ev(`(() => { const m = window.TuffIDE.editor().getModel(); m.setValue('say "no multiplayer here"\\n'); return 1; })()`);
  const gone = await t.waitFor(`document.querySelector('#btn-run2').classList.contains('hidden')`, 3000);
  check(gone, 'and taking it out hides it again', await shown());

  await open(game);
  await t.sleep(500);
  const btn = await ev(`(() => { const b = document.querySelector('#btn-run2'); const r = b.getBoundingClientRect(), run = document.querySelector('#btn-run').getBoundingClientRect();
    return { shown: !b.classList.contains('hidden'), title: b.title, inWidget: !!b.closest('.run-widget'), nextToRun: Math.abs(r.left - run.right) < 4 && Math.abs(r.top - run.top) < 2, w: r.width, runW: run.width, fill: (p => p ? getComputedStyle(p).fill : 'no shape')(b.querySelector('.i-players path')) }; })()`);
  check(btn.shown && /second player/i.test(btn.title), 'a game that hosts and joins: the button shows, titled "Run a second player..."', btn);
  check(btn.inWidget && btn.nextToRun && btn.w === btn.runW, 'it sits right after Run in the run widget, the same size', btn);
  check(btn.fill === 'rgb(95, 184, 101)', `its two people are the Run button's green (${btn.fill})`, btn.fill);
  await ev(`document.querySelector('#runconfig-widget').click()`);
  await t.sleep(300);
  const menu = await ev(`[...document.querySelectorAll('#context-menu button, #context-menu .mi')].map(b => b.innerText.replace(/\\n/g, ' '))`);
  check(menu.some((m) => /Run a Second Player/.test(m)), 'the run options menu has "Run a Second Player" too', menu);
  await t.key('Escape');
  await t.shot('second_button.png', { x: 900, y: 0, width: 500, height: 40 });

  // The first copy: it finds no room, so it hosts.
  t.info('starting the first copy (it looks for a room for 3 s, then hosts)...');
  const t0 = Date.now();
  await ev(`document.querySelector('#btn-run').click()`);
  const hosting = await t.waitFor(`/hosting true/.test(document.querySelector('#run-output').innerText)`, 60000);
  check(hosting, `the first copy hosts the room (${((Date.now() - t0) / 1000).toFixed(1)} s)`, (await out()).slice(-400));
  check(!(await ev(`document.querySelector('#run-output').classList.contains('two')`)), 'with one copy, the Run panel has no P1 or P2 chips', null);

  // The second copy joins it.
  t.info('starting the second player...');
  const t1 = Date.now();
  await ev(`document.querySelector('#btn-run2').click()`);
  const running2 = await t.waitFor(`document.querySelector('#btn-run2').classList.contains('running')`, 5000);
  const state = await ev(`({ run: document.querySelector('#btn-run').classList.contains('running'), title: document.querySelector('#btn-run2').title,
    stop: getComputedStyle(document.querySelector('#btn-run2 .i-stop')).display, two: document.querySelector('#run-output').classList.contains('two') })`);
  check(running2 && state.run && state.stop !== 'none' && /Stop the second player/.test(state.title), 'while it runs, its button is a stop for the second player, and Run still shows Stop', state);
  const joined = await t.waitFor(said('/^joined Player 1/', 2), 40000);
  check(joined, `the second player joins the first copy's room and says "joined Player 1" (${((Date.now() - t1) / 1000).toFixed(1)} s)`, (await out()).slice(-500));
  const hostSaw = await t.waitFor(said('/^joined Player 2/', 1), 10000);
  check(hostSaw, 'and the first copy says "joined Player 2"', (await out()).slice(-500));
  const both = await waitCopies(2, 5000);
  check(both === 2, `both copies are running (${both} processes with the game's path)`, both);

  // Labelled: a P1 or P2 chip on each line, drawn by CSS (not in the text).
  const chips = await ev(`(() => {
    const spans = [...document.querySelectorAll('#run-output > span[data-who]')];
    const chip = (s) => getComputedStyle(s, '::before').content;
    const of = (re) => { const s = spans.find((x) => re.test(x.textContent)); return s ? { who: s.dataset.who, p2: s.classList.contains('p2'), chip: chip(s), bg: getComputedStyle(s, '::before').backgroundColor } : null; };
    return { hosting: of(/^hosting true/), joined1: of(/^joined Player 1/), joined2: of(/^joined Player 2/), notices: document.querySelectorAll('#run-output .notice').length, cmds: document.querySelectorAll('#run-output .cmd').length };
  })()`);
  check(chips.joined1?.chip === '"P2"' && chips.joined1.p2, 'the second player\'s lines start with a P2 chip', chips);
  check(chips.hosting?.chip === '"P1"' && chips.joined2?.chip === '"P1"' && !chips.hosting.p2, "the first copy's lines start with a P1 chip (the ones from before the second player too)", chips);
  check(chips.joined1 && chips.hosting && chips.joined1.bg !== chips.hosting.bg, 'P1 and P2 are different colors', chips);
  check(chips.notices === 1 && chips.cmds === 2, 'the Tuff Engine notice shows once, and each copy\'s command line shows', chips);
  const text = await out();
  check(!/P[12]/.test(text), "the chips aren't in the panel's text (copying it gives what the programs said)", text.slice(-300));
  await t.shot('second_running.png');

  // Its own button stops only the second player.
  await ev(`document.querySelector('#btn-run2').click()`);
  const stopped2 = await t.waitFor(`!document.querySelector('#btn-run2').classList.contains('running') && /The second player finished/.test(document.querySelector('#run-output').innerText)`, 10000);
  const left = await waitCopies(1, 8000);
  const runStill = await ev(`document.querySelector('#btn-run').classList.contains('running')`);
  check(stopped2 && left === 1 && runStill, 'its button stops the second player; the first copy keeps running', { stopped2, left, runStill });

  // Stop ends both.
  await ev(`document.querySelector('#btn-run2').click()`);
  const again = await t.waitFor(said('/^joined Player 1/', 2, 2), 40000); // its second "joined"
  check(again && await waitCopies(2, 5000) === 2, 'a second player can start again while the first copy runs', (await out()).slice(-300));
  await ev(`document.querySelector('#btn-run').click()`);
  const allStopped = await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running') && !document.querySelector('#btn-run2').classList.contains('running')`, 10000);
  const none = await waitCopies(0, 8000);
  check(allStopped && none === 0, 'Stop ends both copies', { allStopped, none, out: (await out()).slice(-300) });

  // Run starts over with one copy.
  await ev(`document.querySelector('#btn-run').click()`);
  await t.waitFor(`/hosting true/.test(document.querySelector('#run-output').innerText)`, 60000);
  await ev(`document.querySelector('#btn-run2').click()`);
  await t.waitFor(said('/^joined Player 1/', 2), 40000);
  check(await waitCopies(2, 5000) === 2, 'Run, then Run a second player, once more: two copies', copiesRunning(game));
  await ev(`window.TuffIDE.runFile(${JSON.stringify(game)})`);
  await t.waitFor(`document.querySelector('#btn-run').classList.contains('running') && !document.querySelector('#btn-run2').classList.contains('running')`, 10000);
  const fresh = await ev(`({ two: document.querySelector('#run-output').classList.contains('two'), p2: document.querySelectorAll('#run-output .p2').length })`);
  const one = await waitCopies(1, 8000);
  check(one === 1 && !fresh.two && fresh.p2 === 0, 'running the program again starts over with one copy (the second player ends)', { one, fresh });

  // Closing TuffCode ends both.
  await t.waitFor(`/hosting true/.test(document.querySelector('#run-output').innerText)`, 60000);
  await ev(`document.querySelector('#btn-run2').click()`);
  await t.waitFor(said('/^joined Player 1/', 2), 40000);
  const before = await waitCopies(2, 5000);
  t.info(`closing TuffCode with ${before} copies running...`);
  try { await ev(`window.TuffIDE.runCommand('exit')`); } catch {} // the window goes, and the eval with it
  const after = await waitCopies(0, 15000);
  check(before === 2 && after === 0, 'closing TuffCode ends both copies', { before, after });
};
