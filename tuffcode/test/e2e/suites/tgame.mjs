// A tgame program run with the Run button: its first output line is the yellow Tuff Engine notice, before anything
// the program prints, and the game window closes itself (a timer in the program calls game:close), which ends the run.
// Runs with the Tuff runtime (packaged) or Python + tuff.py (checkout); a checkout needs pywebview in that Python.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { python } from '../launch.mjs';

export const meta = { title: 'tgame: the Tuff Engine notice, from the Run button', timeout: 120000 };

const NOTICE = 'Tuff Engine is coming soon: a visual way to make games with TuffCode.';
const GAME = `mention tgame

game = tgame.window("E2E game", 420, 300)
game:background "navy"
ball = game:circle(210, 150, 20, "gold")
ball:speed(120, 80)
ball:on_edge "bounce"
say "the game started"

func done():
    say "closing the game"
    game:close()

game:after(2.5, done)
`;

export default async (t, ctx) => {
  const check = (ok, label, got) => t.check(label, ok, got); // ok first, like the tgame Python tests
  const ev = (js) => t.eval(js);
  if (!ctx.packaged) {
    const py = python();
    if (!py || spawnSync(py[0], [...py.slice(1), '-c', 'import webview'], { windowsHide: true }).status !== 0) {
      t.skip('the tgame run', 'the Python that runs tuff.py has no pywebview (py -m pip install pywebview)');
      return;
    }
  }
  const file = path.join(ctx.root, 'e2e_game.tuf');
  fs.writeFileSync(file, GAME);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(file)}); return 1; })()`);
  await t.sleep(500);
  const t0 = Date.now();
  await ev(`document.querySelector('#btn-run').click()`);
  const started = await t.waitFor(`/the game started/.test(document.querySelector('#run-output').innerText)`, 45000);
  check(started, `the game started from the Run button (${((Date.now() - t0) / 1000).toFixed(1)} s)`, await ev(`document.querySelector('#run-output').innerText.slice(-400)`));

  // The Run output: the command line (.cmd), then what the program said, one span per line.
  const lines = await ev(`[...document.querySelectorAll('#run-output > span')]
    .filter((s) => !s.classList.contains('cmd') && s.textContent.trim())
    .map((s) => ({ text: s.textContent.trim(), cls: s.className, color: getComputedStyle(s).color }))`);
  const first = lines[0] || {};
  check(first.text === NOTICE, 'the first output line is the Tuff Engine notice', lines.slice(0, 3));
  check(/\bnotice\b/.test(first.cls) && /\btline\b/.test(first.cls), 'it is a say line with the notice class', first.cls);
  const yellow = await ev(`(() => { const s = document.createElement('span'); s.style.color = 'var(--yellow)'; document.body.append(s); const c = getComputedStyle(s).color; s.remove(); return c; })()`);
  check(first.color === yellow && yellow === 'rgb(229, 192, 123)', `and it shows in the theme's yellow (${first.color})`, { color: first.color, yellow });
  check(lines[1] && lines[1].text === 'the game started' && !/notice/.test(lines[1].cls) && lines[1].color !== yellow,
    "the program's own first line comes right after it, in the normal color", lines.slice(1, 3));
  await t.shot('tgame_running.png');

  const finished = await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running')`, 45000);
  const out = await ev(`document.querySelector('#run-output').innerText`);
  check(finished && /closing the game/.test(out) && /exit code 0/.test(out),
    `the game closed itself and the run ended with exit code 0 (${((Date.now() - t0) / 1000).toFixed(1)} s after Run)`, out.slice(-400));
  const notices = await ev(`document.querySelectorAll('#run-output .notice').length`);
  check(notices === 1, 'the notice was shown once', notices);
  await t.shot('tgame_finished.png');
};
