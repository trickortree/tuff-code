// Deleting a watched folder must not make the main process spin (review finding), and the
// watcher has to come back for the real project afterwards.
// On Windows TuffCode only watches the folder while its window has focus, so this brings it to the front first.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'a deleted watched folder' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const inTree = (name) => `!![...document.querySelectorAll('#tree .tree-row .name')].find(n => n.textContent === ${JSON.stringify(name)})`;

  const focused = await t.focus();
  if (ctx.win) {
    fs.writeFileSync(path.join(ctx.root, 'watch_probe.tuf'), '');
    const watching = await t.waitFor(inTree('watch_probe.tuf'), 4000, 100);
    fs.rmSync(path.join(ctx.root, 'watch_probe.tuf'));
    await t.waitFor(`!${inTree('watch_probe.tuf')}`, 4000, 100);
    if (!watching) {
      const why = `the window didn't get focus (document.hasFocus: ${focused}), and on Windows TuffCode only watches the folder while it has focus`;
      if (!ctx.ci) { t.skip('the 4 checks for a deleted watched folder', `${why}. Run it again without using the PC meanwhile`); return; }
      t.info(`${why}; on CI it should have focus, so the checks below run anyway`);
    }
  }

  const tmp = fs.mkdtempSync(path.join(ctx.tmp, 'tc-watch-'));
  fs.writeFileSync(path.join(tmp, 'a.tuf'), 'say 1\n');
  const root = await ev('window.TuffIDE.root()');
  const ok = await ev(`window.tuff.fs.watch(${JSON.stringify(tmp)})`);
  check('Watching a scratch folder starts', ok === true, ok);
  await t.sleep(500);
  fs.rmSync(tmp, { recursive: true, force: true });
  await t.sleep(1500);
  const before = ctx.cpuMs();
  await t.sleep(4000);
  const used = ctx.cpuMs() - before;
  check(`The main process stays idle after the folder is deleted (${Math.round(used)} ms CPU in 4 s)`, used < 800, used);
  const back = await ev(`window.tuff.fs.watch(${JSON.stringify(root)})`);
  check('Watching the real project again works', back === true, back);
  fs.writeFileSync(path.join(root, 'watch_back.tuf'), 'say 2\n');
  check('…and new files show up again', await t.waitFor(inTree('watch_back.tuf'), 4000, 100), null);
};
