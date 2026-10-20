// Autocomplete and indenting: no popup after a block colon or inside strings and comments, Enter indents
// after func/if/else/for, return outdents, and the method popup still opens after app: and tgui.
import path from 'node:path';

export const meta = { title: 'autocomplete and indenting' };

export default async (t, ctx) => {
  const check = t.check;
  await t.eval(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'main.tuf'))}); return 1; })()`);
  await t.sleep(400);
  const fresh = async (code = '') => { await t.setCode(code); await t.cursorEnd(); };
  const norm = async () => (await t.code()).replace(/\r\n/g, '\n');

  await fresh();
  await t.type('func greet():');
  await t.sleep(350);
  check('no popup after func greet():', !(await t.suggestOpen()), await t.suggestions());
  await t.key('Enter');
  check('Enter after func line indents', (await norm()) === 'func greet():\n    ', await norm());
  await t.type('say "hi"');
  await t.key('Escape');
  await t.key('Enter');
  check('next line keeps indent', (await norm()) === 'func greet():\n    say "hi"\n    ', await norm());
  await t.type('return 1');
  await t.key('Escape');
  await t.key('Enter');
  check('return outdents next line', (await norm()) === 'func greet():\n    say "hi"\n    return 1\n', await norm());

  await fresh();
  await t.type('say "Time:');
  await t.sleep(350);
  check('no popup for : inside a string', !(await t.suggestOpen()), await t.suggestions());

  await fresh();
  await t.type('# note:');
  await t.sleep(350);
  check('no popup for : inside a comment', !(await t.suggestOpen()), await t.suggestions());

  await fresh();
  await t.type('if name:');
  await t.sleep(350);
  check('no popup for block colon after a name (if name:)', !(await t.suggestOpen()), await t.suggestions());
  await t.key('Enter');
  check('if name: + Enter indents', (await norm()) === 'if name:\n    ', await norm());

  await fresh('if x is 1:\n    say 1\n    ');
  await t.type('else:');
  await t.sleep(300);
  check('typing else: dedents it', (await norm()) === 'if x is 1:\n    say 1\nelse:', await norm());
  await t.key('Enter');
  check('else: + Enter indents', (await norm()) === 'if x is 1:\n    say 1\nelse:\n    ', await norm());

  await fresh('app = tgui.window("x")\n');
  await t.type('app:');
  await t.sleep(400);
  const items = await t.suggestions();
  check('app: still shows methods', (await t.suggestOpen()) && items.some((i) => /button/.test(i)), items);
  await t.key('Backspace');
  await t.sleep(350);
  check('Backspace over : closes the list', !(await t.suggestOpen()) && (await norm()).endsWith('\napp'), { open: await t.suggestOpen(), code: await norm() });

  await fresh('import tgui\n');
  await t.type('tgui.');
  await t.sleep(400);
  check('tgui. shows library functions', await t.suggestOpen(), await t.suggestions());
  await t.key('Escape');

  await fresh();
  await t.type('x = 3.');
  await t.sleep(350);
  check('no popup after a number dot', !(await t.suggestOpen()), await t.suggestions());

  await fresh();
  await t.type('for i in range(1, 3):');
  await t.sleep(300);
  check('no popup after for ... :', !(await t.suggestOpen()), await t.suggestions());
  await t.key('Enter');
  check('for + Enter indents', (await norm()) === 'for i in range(1, 3):\n    ', await norm());
};
