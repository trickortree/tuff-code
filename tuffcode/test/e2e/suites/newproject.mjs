// New Project (1.5.0): File > New Project… (and the project menu, Search Everywhere and the empty editor's button)
// opens the starters gallery. Searching, the arrow keys (after a click on the dialog's title too), a name that's taken
// becoming "Snake 2", Create opening the new folder as the project with its main.tuf, Esc, and the offer of a free
// name for the longest name there is. New projects go in a scratch folder, never your Documents:
// the suite sets settings.newProjectFolder first (the gallery remembers the folder it last used).
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'New Project: the starters gallery' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const projects = path.join(path.dirname(ctx.root), 'projects');
  fs.mkdirSync(path.join(projects, 'Snake'), { recursive: true }); // so the gallery offers "Snake 2"
  await ev(`window.TuffIDE.saveSettings({ newProjectFolder: ${JSON.stringify(projects)} }); 1`);
  const state = () => ev(`(() => {
    const b = document.querySelector('#new-project');
    if (!b) return null;
    const cards = [...b.querySelectorAll('.np-card')];
    const top = cards[0]?.offsetTop;
    const a = document.activeElement;
    return { cards: cards.map((c) => c.dataset.id), across: cards.filter((c) => c.offsetTop === top).length, sel: b.querySelector('.np-card.sel')?.dataset.id || null,
      name: b.querySelector('#np-name').value, folder: b.querySelector('#np-folder').textContent, status: b.querySelector('#np-status').textContent,
      create: !b.querySelector('#np-create').disabled, focus: a?.id || a?.dataset?.id || a?.tagName };
  })()`);
  const isOpen = () => ev(`!!document.querySelector('#new-project')`);
  // ArrowLeft and ArrowRight aren't in cdp.mjs's keys
  const arrow = async (key, keyCode) => {
    await t.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key, code: key, windowsVirtualKeyCode: keyCode });
    await t.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: keyCode });
    await t.sleep(150);
  };

  // File > New Project… is the menu's first item
  await ev(`document.querySelector('#menubar .menu-root > button').click(); 1`);
  await t.sleep(200);
  const items = await ev(`[...document.querySelectorAll('#menubar .dropdown .mi > span:first-child')].map((s) => s.textContent)`);
  check('File > New Project… is the first item of the File menu', items[0] === 'New Project…', items);
  await ev(`document.querySelector('#menubar .dropdown .mi').click(); 1`);
  await t.waitFor(`document.querySelector('#np-name')?.value === 'My Project'`, 5000);
  let s = await state();
  const listed = s?.cards.length === 10 ? null : await ev(`window.tuff.starters.list().then((r) => ({ starters: r.starters.map((x) => x.id), folder: r.folder }), (e) => String(e))`);
  check('it opens the gallery: 10 starters, Blank chosen, named "My Project"', s && s.cards.length === 10 && s.sel === 'blank' && s.name === 'My Project', { s, listed });
  check('the projects go in the folder used last (here the scratch folder)', s && s.folder === projects && s.status.includes(path.join(projects, 'My Project')), s);
  check('the search box has the focus', s?.focus === 'np-q', s);
  await t.shot('newproject.png');

  // Searching, and the name for a starter whose folder is there already
  await t.type('snake', 40);
  await t.waitFor(`document.querySelector('#np-name')?.value === 'Snake 2'`, 5000);
  s = await state();
  check('typing "snake" leaves Snake, and the name is "Snake 2" (there\'s a Snake folder)', s.cards.join() === 'snake' && s.sel === 'snake' && s.name === 'Snake 2', s);
  await t.key('a', 2); // Ctrl+A
  await t.key('Backspace');
  await t.waitFor(`document.querySelectorAll('.np-card').length === 10`, 3000);

  // Arrow keys: Down in the search box goes a row down from the chosen card (Snake: a card the search showed stays
  // chosen when the search is cleared); on the cards Home goes to the first and Right goes across
  s = await state();
  const was = s.cards.indexOf(s.sel);
  check('clearing the search keeps the chosen card (Snake)', s.sel === 'snake' && s.cards.length === 10, s);
  await t.key('ArrowDown');
  await t.sleep(200);
  s = await state();
  check('Down in the search box chooses the card a row below', s.sel === s.cards[was + s.across] && s.focus === 'np-q', s);
  await ev(`document.querySelector('.np-card.sel').focus(); 1`);
  await arrow('Home', 36);
  s = await state();
  check('Home on a card chooses the first one', s.sel === 'blank', s);
  await arrow('ArrowRight', 39);
  s = await state();
  check('Right on a card chooses the next one, and the focus goes with it', s.sel === s.cards[1] && s.focus === s.sel, s);
  await arrow('Home', 36);
  s = await state();
  check('Home goes back to the first card', s.sel === 'blank', s);
  // A click on the dialog's text (its title here) gives the box itself the focus, and the keys still work there
  const title = await ev(`(() => { const r = document.querySelector('#np-title').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
  await t.click(title.x, title.y);
  check('a click on the title gives the box the focus', await ev(`!!document.activeElement?.classList.contains('np-box')`), await state());
  await arrow('ArrowRight', 39);
  s = await state();
  check('...and Right still chooses the next card', s.sel === s.cards[1] && s.focus === s.sel, s);
  await t.click(title.x, title.y);
  await t.key('Escape');
  await t.sleep(200);
  check('Esc closes it, after a click on the title too', !(await isOpen()), null);
  check('...and nothing was made', fs.readdirSync(projects).join() === 'Snake', fs.readdirSync(projects));

  // Search Everywhere finds the command; Enter creates the chosen starter
  await t.key('Shift');
  await t.key('Shift');
  await t.sleep(300);
  await t.type('New Project', 30);
  await t.sleep(300);
  await t.key('Enter');
  await t.waitFor(`document.querySelector('#np-name')?.value === 'My Project'`, 5000);
  check('Search Everywhere finds New Project… and opens the gallery', await isOpen(), null);
  await t.type('snake', 40);
  await t.waitFor(`document.querySelector('#np-name')?.value === 'Snake 2'`, 5000);
  await t.key('Enter');
  const made = path.join(projects, 'Snake 2');
  const opened = await t.waitFor(`window.TuffIDE.root() === ${JSON.stringify(made)} && (window.TuffIDE.activeFile() || '').endsWith('main.tuf')`, 10000);
  check('Enter makes "Snake 2", opens it as the project, and opens its main.tuf', opened && !(await isOpen()),
    await ev(`({ root: window.TuffIDE.root(), file: window.TuffIDE.activeFile() })`));
  check('Snake 2 has the starter\'s files', fs.existsSync(path.join(made, 'main.tuf'))
    && fs.readFileSync(path.join(made, 'main.tuf'), 'utf8') === fs.readFileSync(path.join(ctx.appDir, 'starters', 'snake', 'main.tuf'), 'utf8'), fs.existsSync(made) && fs.readdirSync(made));
  check('the Snake folder that was there is untouched', fs.readdirSync(path.join(projects, 'Snake')).length === 0, null);
  const toast = await ev(`[...document.querySelectorAll('.toast')].map((x) => x.textContent).join(' | ')`);
  check('a toast says what was made', /Made Snake 2 from the Snake starter/.test(toast), toast);
  check('the new main.tuf passes the checker', /^OK/.test(ctx.tuffCheck(path.join(made, 'main.tuf')).trim()), ctx.tuffCheck(path.join(made, 'main.tuf')));
  await t.shot('newproject_made.png');

  // The project menu in the title bar, then the empty editor's button
  await ev(`document.querySelector('#project-widget').click(); 1`);
  await t.sleep(200);
  const menu = await ev(`[...document.querySelectorAll('#context-menu .mi > span:first-child')].map((s) => s.textContent)`);
  check('the project menu has New Project… first', menu[0] === 'New Project…', menu);
  await t.key('Escape');
  await ev(`document.querySelector('#context-menu').classList.add('hidden'); 1`);
  await ev(`(() => { for (let i = 0; i < 20 && document.querySelector('#tabs .tab .x'); i++) document.querySelector('#tabs .tab .x').click(); return 1; })()`);
  await t.waitFor(`!document.querySelector('#empty-state').classList.contains('hidden')`, 3000);
  const button = await ev(`(() => { const b = document.querySelector('#es-new-project'); const r = b.getBoundingClientRect(); return { text: b.textContent, shown: r.width > 0 && r.height > 0 }; })()`);
  check('the empty editor has a New Project… button', button.text === 'New Project…' && button.shown, button);
  await t.shot('newproject_empty.png');
  await ev(`document.querySelector('#es-new-project').click(); 1`);
  await t.waitFor(`!!document.querySelector('#new-project .np-card')`, 5000);
  check('...which opens the gallery', await isOpen(), null);
  // A click on the dim backdrop closes it
  await ev(`(() => { const b = document.querySelector('#new-project'); b.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); return 1; })()`);
  await t.sleep(200);
  check('a click outside the box closes it', !(await isOpen()), null);

  // The longest name, taken: the offer of a free one still shows whole in the status line, and a click takes it
  const long = 'L'.repeat(80);
  fs.mkdirSync(path.join(projects, long));
  await ev(`window.TuffNewProject.open(); 1`);
  await t.waitFor(`/^Makes /.test(document.querySelector('#np-status')?.textContent || '')`, 5000);
  await ev(`(() => { const b = document.querySelector('#np-name'); b.focus(); b.value = ${JSON.stringify(long)}; b.dispatchEvent(new Event('input', { bubbles: true })); return 1; })()`);
  await t.waitFor(`!!document.querySelector('#np-status')?.classList.contains('taken')`, 5000);
  const offer = await ev(`(() => {
    const s = document.querySelector('#np-status').getBoundingClientRect();
    const b = document.querySelector('#np-status [data-a="free"]')?.getBoundingClientRect();
    return b ? { shown: b.width > 40 && b.left >= s.left - 1 && b.right <= s.right + 1, x: b.left + b.width / 2, y: b.top + b.height / 2 } : null;
  })()`);
  check('a long taken name: the offer of a free name shows in the status line', offer?.shown, offer);
  await t.shot('newproject_long_name.png');
  if (offer) await t.click(offer.x, offer.y);
  await t.waitFor(`/^Makes /.test(document.querySelector('#np-status')?.textContent || '')`, 5000);
  s = await state();
  check('...and a click on it puts in a free name that fits (78 letters and " 2")', s?.name === `${'L'.repeat(78)} 2` && s.create, s);
  await t.key('Escape');
  await t.sleep(200);
  check('...then Esc closes it, and nothing more was made', !(await isOpen()) && fs.readdirSync(projects).sort().join() === [long, 'Snake', 'Snake 2'].sort().join(),
    fs.readdirSync(projects));
};
