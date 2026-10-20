// Undo after saving: one Ctrl+Z should land on exactly what was saved, by Ctrl+S or by autosave.
// No spaces in the typed text: Monaco already starts a new undo step when you type a space after a letter,
// so the bug only shows when you keep typing letters (abc, save, def).
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'undo after saving', platforms: ['win32'], why: 'Ctrl+Z in the editor, Cmd+Z on a Mac' };

const NL = '\n';
const CTRL = 2, SHIFT = 8;

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const file = path.join(ctx.root, `undo_${Date.now().toString(36)}.tuf`);
  const val = async () => (await t.code()).replace(/\r\n/g, NL);
  const disk = () => { try { return fs.readFileSync(file, 'utf8').replace(/\r\n/g, NL); } catch { return null; } };
  const waitDisk = async (want, ms = 5000) => { const end = Date.now() + ms; while (Date.now() < end) { if (disk() === want) return true; await t.sleep(100); } return false; };
  const tab = `[...document.querySelectorAll('#tabs .tab')].find(x => x.title === ${JSON.stringify(file)})`;
  const dirty = () => ev(`${tab}?.classList.contains('dirty')`);
  const toEnd = () => ev(`(() => { const e = monaco.editor.getEditors()[0]; e.setPosition({ lineNumber: 1, column: e.getModel().getLineMaxColumn(1) }); e.focus(); return 1; })()`);
  const undo = async () => { await t.key('z', CTRL); await t.sleep(200); };

  fs.writeFileSync(file, 'say "hi"' + NL);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(file)}); return 1; })()`);
  check('Opened a fresh test file', await t.waitFor(`monaco.editor.getEditors()[0].getModel()?.getValue().startsWith('say "hi"')`, 6000, 100), await val());
  await toEnd();

  // 1) Ctrl+S, keep typing in the same spot, then Ctrl+Z
  await t.type('abc', 60);
  await t.key('s', CTRL);
  const saved1 = 'say "hi"abc' + NL;
  check('Ctrl+S saved the file', await waitDisk(saved1), disk());
  await t.type('def', 60);
  check('Kept typing straight after saving', (await val()) === 'say "hi"abcdef' + NL, await val());
  await undo();
  check('One Ctrl+Z goes back to exactly what was saved', (await val()) === saved1, await val());
  check('...and the tab shows no unsaved dot', (await dirty()) === false, await dirty());
  await undo();
  check('A second Ctrl+Z goes back to before the save', (await val()) === 'say "hi"' + NL, await val());
  check('...and now the tab shows the unsaved dot', (await dirty()) === true, await dirty());
  await t.key('z', CTRL | SHIFT);
  await t.sleep(200);
  check('Redo (Ctrl+Shift+Z) brings the saved text back, with no unsaved dot', (await val()) === saved1 && (await dirty()) === false, [await val(), await dirty()]);

  // 2) Autosave: type, pause until autosave runs (1.5 s), type more, then Ctrl+Z
  await toEnd();
  await t.type('xyz', 60);
  const saved2 = 'say "hi"abcxyz' + NL;
  check('Autosave saved the file after a pause', await waitDisk(saved2, 6000), disk());
  await t.sleep(300);
  await t.type('123', 60);
  await undo();
  check('One Ctrl+Z after an autosave goes back to the autosaved text', (await val()) === saved2, await val());
  check('...and the tab shows no unsaved dot', (await dirty()) === false, await dirty());
};
