// The tab bar (1.5.0), with the real mouse: dragging a tab along the bar moves it, Escape mid-drag puts it back,
// the right-click menu has the new items, and Ctrl+Shift+PgUp/PgDn move the tab on screen.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'dragging tabs and their menu', platforms: ['win32', 'linux'], why: 'Ctrl+Shift+PgUp/PgDn (Cmd on a Mac)' };

const CTRL = 2, SHIFT = 8;

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const stamp = Date.now().toString(36);
  const files = ['one', 'two', 'three'].map((n) => path.join(ctx.root, `tabs_${n}_${stamp}.tuf`));
  for (const f of files) fs.writeFileSync(f, 'say "hi"\n');
  for (const f of files) await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(f)}); return 1; })()`);
  const order = async () => JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#tabs .tab')].map((x) => x.title))`)).filter((p) => files.includes(p));
  const press = async (key, keyCode, mods) => {
    await t.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', modifiers: mods, windowsVirtualKeyCode: keyCode, key, code: key });
    await t.send('Input.dispatchKeyEvent', { type: 'keyUp', modifiers: mods, windowsVirtualKeyCode: keyCode, key, code: key });
    await t.sleep(150);
  };
  const box = async (f) => JSON.parse(await ev(`JSON.stringify((() => { const r = [...document.querySelectorAll('#tabs .tab')].find((x) => x.title === ${JSON.stringify(f)}).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width }; })())`));
  const mouse = (type, x, y, buttons) => t.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons, clickCount: 1 });
  const drag = async (from, toX, { escape = false } = {}) => {
    const a = await box(from);
    await mouse('mouseMoved', a.x, a.y, 0);
    await mouse('mousePressed', a.x, a.y, 1);
    for (let i = 1; i <= 10; i++) { await mouse('mouseMoved', a.x + ((toX - a.x) * i) / 10, a.y, 1); await t.sleep(30); }
    if (escape) await t.key('Escape');
    await mouse('mouseReleased', toX, a.y, 0);
    await t.sleep(200);
  };
  check('Three test files are open in tabs, in order', JSON.stringify(await order()) === JSON.stringify(files), await order());

  const last = await box(files[2]);
  await drag(files[0], last.x + last.w / 2 - 4);
  check('Dragging the first tab past the last moves it to the end', JSON.stringify(await order()) === JSON.stringify([files[1], files[2], files[0]]), await order());

  const first = await box(files[1]);
  await drag(files[0], first.x - first.w / 2 + 4, { escape: true });
  check('Escape while dragging puts the tab back where it was', JSON.stringify(await order()) === JSON.stringify([files[1], files[2], files[0]]), await order());

  const b = await box(files[2]);
  await t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: b.x, y: b.y, button: 'right', clickCount: 1 });
  await t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: b.x, y: b.y, button: 'right', clickCount: 1 });
  await t.sleep(200);
  const items = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#context-menu:not(.hidden) .mi')].map((m) => (m.disabled ? '(' : '') + m.textContent))`));
  check('Right-clicking a tab shows its menu with Run, the closes, Move, the paths, Show in Project and Rename',
    ['Close Tabs to the Left', 'Close Tabs to the Right', 'Move Tab Left', 'Move Tab Right', 'Copy Relative Path', 'Show in Project', 'Rename File…']
      .every((w) => items.some((x) => x.includes(w))) && items.some((x) => x.startsWith('Run ')), items);
  await t.key('Escape');

  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(files[0])}); return 1; })()`);
  await press('PageUp', 33, CTRL | SHIFT);
  check('Ctrl+Shift+PgUp moves the tab on screen one place left', JSON.stringify(await order()) === JSON.stringify([files[1], files[0], files[2]]), await order());
  await press('PageDown', 34, CTRL | SHIFT);
  check('...and Ctrl+Shift+PgDn moves it back', JSON.stringify(await order()) === JSON.stringify([files[1], files[2], files[0]]), await order());
  await t.shot('tabs.png');
  for (const f of files) { try { fs.unlinkSync(f); } catch {} }
};
