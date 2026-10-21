// The run button in the title bar: play when idle, Stop while a program runs, and back again when it's
// stopped. Runs slow.tuf (it waits 2 s) with the Tuff runtime (packaged) or Python + tuff.py (checkout).
import path from 'node:path';

export const meta = { title: 'the run button' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const btn = () => ev(`({ running: document.querySelector('#btn-run').classList.contains('running'), title: document.querySelector('#btn-run').title, play: getComputedStyle(document.querySelector('#btn-run .i-play')).display, stop: getComputedStyle(document.querySelector('#btn-run .i-stop')).display })`);
  const output = () => ev(`document.querySelector('#run-output').innerText.slice(-300)`);
  t.info('title bar buttons: ' + await ev(`[...document.querySelectorAll('#titlebar .tb-right button')].map(b => b.id || b.className).join(', ')`));
  t.info('toolstrip: ' + await ev(`[...document.querySelectorAll('.ts-btn')].map(b => b.dataset.tool).join(', ')`));

  const idle = await btn();
  check('Idle: the run button shows play, not Stop', !idle.running && idle.play !== 'none' && idle.stop === 'none', idle);
  await t.shot('titlebar.png', { x: 0, y: 0, width: 1400, height: 40 });
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'slow.tuf'))}); return 1; })()`);
  await t.sleep(500);
  await ev(`document.querySelector('#btn-run').click()`);
  const started = await t.waitFor(`document.querySelector('#btn-run').classList.contains('running') && /starting/.test(document.querySelector('#run-output').innerText)`, 15000);
  const running = await btn();
  check('Running slow.tuf: the button turns into Stop', running.running && running.stop !== 'none' && running.play === 'none', running);
  check('The program started (its first line is in the Run output)', started, await output());
  await t.shot('titlebar_running.png', { x: 900, y: 0, width: 500, height: 40 });
  await ev(`document.querySelector('#btn-run').click()`);
  await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running')`, 5000);
  const stopped = await btn();
  check('Clicking it again stops the program before it finishes', !stopped.running && stopped.play !== 'none' && !/done/.test(await output()), { stopped, output: await output() });
  await ev(`document.querySelector('#runconfig-widget').click()`);
  await t.sleep(300);
  const menu = await ev(`[...document.querySelectorAll('#context-menu button, #context-menu .mi')].map(b => b.innerText.replace(/\\n/g, ' '))`);
  check('The run configuration menu opens', menu.length > 0, menu);
  t.info('menu: ' + menu.join(' | '));
  await t.shot('runmenu.png', { x: 800, y: 0, width: 600, height: 260 });
  await t.key('Escape');
};
