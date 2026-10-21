// Shortcut keys typed in a box that isn't the code editor (Tuff Agents' message box here) stay with the box:
// Ctrl+Y used to delete a line of the open code file and move you into the editor, so the Ctrl+Z after it
// undid code as well. Ctrl+Shift+Z, Ctrl+D, Ctrl+R and Ctrl+Alt+L did the same. The shortcuts for the whole
// app (Ctrl+S, Alt+4 ...) still work from the box, and in the editor Ctrl+Y and Ctrl+Z still change the code.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'shortcut keys in a text box leave the code alone' };

const CTRL = 2, ALT = 1, SHIFT = 8;
const CODE = 'say "one"\nsay "two"\nsay "three"\n';

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const mac = ctx.platform === 'darwin';
  const CMD = mac ? 4 : CTRL; // the editor's own undo is Cmd+Z on a Mac
  const file = path.join(ctx.root, 'keys.tuf');
  const val = async () => (await t.code()).replace(/\r\n/g, '\n');
  const box = `document.querySelector('.ta textarea')`;
  const inBox = () => ev(`document.activeElement === ${box}`);
  const disk = () => fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');

  fs.writeFileSync(file, CODE);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(file)}); return 1; })()`);
  await t.waitFor(`monaco.editor.getEditors()[0].getModel()?.getValue().includes('three')`, 6000);

  // Tuff Agents from the marketplace: its panel opens on the right with the message box
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await t.waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 10000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  check('Tuff Agents is installed and shows its message box', await t.waitFor(`!!${box}`, 10000), await ev(`window.TuffPluginHost.state()`));
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`); // close the Plugins view again

  // the cursor at the end of the code, then into the message box and type there
  await t.cursorEnd();
  const code0 = await val();
  const [bx, by] = await ev(`(() => { const r = ${box}.getBoundingClientRect(); return [r.x + 30, r.y + 12]; })()`);
  const intoBox = async () => { await t.click(bx, by); await t.sleep(150); };
  await intoBox();
  await t.type('hello', 40);
  check('Typing in the message box goes into the box, not the code', (await ev(`${box}.value`)) === 'hello' && (await val()) === code0 && (await inBox()), { box: await ev(`${box}.value`), code: await val() });

  await t.key('y', CTRL);
  await t.sleep(250);
  check('Ctrl+Y in the message box leaves the code alone, and the box keeps the focus and its text', (await val()) === code0 && (await inBox()) && (await ev(`${box}.value`)) === 'hello', { code: await val(), focus: await ev(`document.activeElement.className || document.activeElement.tagName`), box: await ev(`${box}.value`) });

  await t.key('z', CTRL);
  await t.sleep(250);
  check('Ctrl+Z in the message box leaves the code alone, and the box keeps the focus', (await val()) === code0 && (await inBox()), { code: await val(), focus: await ev(`document.activeElement.className || document.activeElement.tagName`) });
  // A made-up key press doesn't reach a Mac text box's own editing (see cdp.mjs), so only here.
  // (How much one Ctrl+Z takes back is the browser's call: all of "hello", or "ello" when it made "h" its own step.)
  const left = await ev(`${box}.value`);
  if (!mac) check('...and it undoes the typing in the box instead', left !== 'hello' && 'hello'.startsWith(left), left);
  else t.skip('Ctrl+Z undoes the typing in the box', 'a made-up key press never reaches the Mac text box');

  for (const [k, mods, name] of [['z', CTRL | SHIFT, 'Ctrl+Shift+Z'], ['d', CTRL, 'Ctrl+D'], ['r', CTRL, 'Ctrl+R'], ['l', CTRL | ALT, 'Ctrl+Alt+L']]) {
    await intoBox();
    await t.key(k, mods);
    await t.sleep(300);
    check(`${name} in the message box leaves the code alone and the focus in the box`, (await val()) === code0 && (await inBox()), { code: await val(), focus: await ev(`document.activeElement.className || document.activeElement.tagName`) });
  }

  // The app's own shortcuts still work from the box: Ctrl+S saves, Alt+4 shows and hides the Run window
  await ev(`(() => { const m = monaco.editor.getEditors()[0].getModel(); m.pushEditOperations([], [{ range: m.getFullModelRange(), text: ${JSON.stringify(CODE + 'say "four"\n')} }], () => null); return 1; })()`);
  await intoBox();
  await t.key('s', CTRL);
  const saved = await t.waitFor(`[...document.querySelectorAll('#toasts .toast')].some(x => /All files saved/.test(x.textContent))`, 1200, 50);
  check('Ctrl+S in the message box still saves (straight away, not by the autosave)', saved && disk().includes('say "four"') && (await inBox()), { saved, disk: disk() });
  const runShown = () => ev(`!document.querySelector('#bottom-panel').classList.contains('hidden')`);
  const before = await runShown();
  await intoBox();
  await t.key('4', ALT);
  await t.sleep(300);
  const after = await runShown();
  await t.key('4', ALT);
  await t.sleep(300);
  check('Alt+4 in the message box still shows or hides the Run window', before !== after && (await runShown()) === before, { before, after });

  // In the code editor the same keys still work on the code
  await ev(`(() => { const e = monaco.editor.getEditors()[0]; e.setPosition({ lineNumber: 2, column: 1 }); e.focus(); return 1; })()`);
  await t.sleep(150);
  const code1 = await val();
  await t.key('y', CTRL);
  await t.sleep(250);
  check('Ctrl+Y in the editor still deletes the line', (await val()) === code1.replace('say "two"\n', ''), await val());
  await t.key('z', CMD);
  await t.sleep(250);
  check(`${mac ? 'Cmd' : 'Ctrl'}+Z in the editor still undoes it`, (await val()) === code1, await val());
  await t.key('d', CTRL);
  await t.sleep(250);
  check('Ctrl+D in the editor still copies the line', (await val()) === code1.replace('say "two"\n', 'say "two"\nsay "two"\n'), await val());
  await t.key('z', CMD);
  await t.sleep(250);
  check('...and undo takes the copy back out', (await val()) === code1, await val());

  // A plugin's own shortcut works from the box too: Ctrl+Shift+A (Cmd+Shift+A on a Mac) hides Tuff Agents
  await intoBox();
  await t.key('a', CMD | SHIFT);
  check("A plugin's shortcut (Ctrl+Shift+A) still works from the box: it hides the Tuff Agents panel", await t.waitFor(`document.querySelector('#rightbar').classList.contains('hidden')`, 1500, 50), await ev(`window.TuffPluginHost.state()`));
};
