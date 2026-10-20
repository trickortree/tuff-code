// The New File dialog (Ctrl+Alt+N): type chips, names without an extension, and Escape.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'the New File dialog' };

export default async (t, ctx) => {
  const check = t.check;
  const P = (f) => path.join(ctx.root, f);
  for (const f of ['.env', 'Makefile', 'notes.tuf', 'readme.md']) fs.rmSync(P(f), { force: true });
  const ls = () => fs.readdirSync(ctx.root);
  const open = async () => {
    await t.eval(`document.querySelector('#tree').focus()`);
    await t.key('N', 3); // Ctrl+Alt+N
    await t.sleep(250);
  };
  const state = () => t.eval(`({ open: !document.querySelector('#modal').classList.contains('hidden'), title: document.querySelector('#modal-title').textContent, value: document.querySelector('#modal-input').value, chips: [...document.querySelectorAll('#modal-choices button')].map(b => (b.classList.contains('sel') ? '*' : '') + b.textContent) })`);
  const clickChip = (label) => t.eval(`[...document.querySelectorAll('#modal-choices button')].find(b => b.textContent === ${JSON.stringify(label)}).click()`);
  const setName = (v) => t.eval(`(() => { const i = document.querySelector('#modal-input'); i.value = ${JSON.stringify(v)}; i.dispatchEvent(new Event('input')); i.focus(); })()`);
  const lang = () => t.eval(`monaco.editor.getEditors()[0].getModel().getLanguageId()`);

  await open();
  let s = await state();
  check('Ctrl+Alt+N opens "New File" with type chips', s.open && s.title === 'New File' && s.chips.includes('*Tuff') && s.chips.includes('.env'), s);
  await t.shot('newfile.png');
  await clickChip('.env');
  s = await state();
  check('.env chip makes the name ".env"', s.value === '.env' && s.chips.includes('*.env'), s);
  await t.key('Enter');
  await t.sleep(600);
  check('.env file is created', fs.existsSync(P('.env')), ls());
  check('.env opens with settings highlighting', (await lang()) === 'ini', await lang());

  await open();
  await setName('Makefile');
  s = await state();
  check('typing a name with no extension highlights Other', s.chips.includes('*Other'), s);
  await t.key('Enter');
  await t.sleep(600);
  check('Makefile is created with no extension added', fs.existsSync(P('Makefile')) && !fs.existsSync(P('Makefile.tuf')), ls());

  await open();
  await setName('notes.tuf');
  await t.key('Enter');
  await t.sleep(600);
  check('notes.tuf still works', fs.existsSync(P('notes.tuf')), ls());

  await open();
  await setName('readme');
  await clickChip('Markdown');
  s = await state();
  check('Markdown chip turns readme into readme.md', s.value === 'readme.md', s);
  await t.key('Escape');
  await t.sleep(200);
  check('Escape cancels without creating', !fs.existsSync(P('readme.md')) && !(await state()).open, ls());
};
