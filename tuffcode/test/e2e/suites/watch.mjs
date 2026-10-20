// Files made, changed or deleted outside TuffCode show up in the project tree straight away,
// and an open tab follows changes on disk unless it has unsaved edits.
// On Windows TuffCode only watches the folder while its window has focus, so this brings it to the front first.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'the project tree follows changes on disk' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const P = (f) => path.join(ctx.root, f);
  const waitFor = async (js, ms = 4000) => { const end = Date.now() + ms; while (Date.now() < end) { if (await ev(js)) return Date.now(); await t.sleep(50); } return 0; };
  const row = (name) => `[...document.querySelectorAll('#tree .tree-row')].find(r => r.querySelector('.name')?.textContent === ${JSON.stringify(name)})`;

  const focused = await t.focus();
  if (ctx.win) {
    // Is the folder being watched? A file made now shows up by itself only if the window has focus.
    fs.writeFileSync(P('watch_probe.tuf'), '');
    const watching = await waitFor(`!!${row('watch_probe.tuf')}`);
    fs.rmSync(P('watch_probe.tuf'));
    await waitFor(`!${row('watch_probe.tuf')}`);
    if (!watching) {
      const why = `the window didn't get focus (document.hasFocus: ${focused}), and on Windows TuffCode only watches the folder while it has focus`;
      if (!ctx.ci) { t.skip('the 5 watch checks', `${why}. Run it again without using the PC meanwhile`); return; }
      t.info(`${why}; on CI it should have focus, so the checks below run anyway`);
    }
  }

  fs.writeFileSync(P('watch_tab.tuf'), 'say "one"\n');
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(P('watch_tab.tuf'))}); return 1; })()`);
  await t.sleep(800);

  let t0 = Date.now();
  fs.writeFileSync(P('watch_new.tuf'), 'say "made outside"\n');
  let at = await waitFor(`!!${row('watch_new.tuf')}`);
  check(`A new file appears in the tree by itself${at ? ` (${at - t0} ms)` : ''}`, !!at, null);
  check('It glows for a moment so you can see it', at && (await ev(`${row('watch_new.tuf')}?.classList.contains('fresh')`)), await ev(`${row('watch_new.tuf')}?.className`));

  t0 = Date.now();
  fs.writeFileSync(P('watch_tab.tuf'), 'say "two"\n');
  at = await waitFor(`window.TuffIDE?.code?.() ? /two/.test(window.TuffIDE.code()) : /two/.test(document.querySelector('.monaco-editor .view-lines')?.textContent || '')`);
  check(`An open tab shows the new text when the file changes on disk${at ? ` (${at - t0} ms)` : ''}`, !!at, await ev(`document.querySelector('.monaco-editor .view-lines')?.textContent`));

  fs.mkdirSync(P('watch_dir'));
  at = await waitFor(`!!${row('watch_dir')}`);
  check('A new folder appears too', !!at, null);

  fs.rmSync(P('watch_new.tuf'));
  at = await waitFor(`!${row('watch_new.tuf')}`);
  check('A deleted file disappears', !!at, null);
};
