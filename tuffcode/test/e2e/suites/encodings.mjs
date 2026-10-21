// .tuf files that aren't plain UTF-8: UTF-16 with a byte order mark (Notepad's "Unicode", what Windows
// PowerShell's > and Out-File write), UTF-8 with a BOM, and Windows-1252 ("ANSI", older Notepad). They open
// with the right text, opening one never rewrites it, a change saves as plain UTF-8 (which the Tuff runtime
// reads), and a save that leaves the text as it was leaves the file alone.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: '.tuf files saved as UTF-16, UTF-8 with a BOM or Windows-1252' };

const TEXT = 'say "Héllo, naïve café 🙂"\r\nsay "two"\r\n';
const ANSI_TEXT = 'say "café – naïve €5"\r\nsay "two"\r\n'; // every character is in Windows-1252
const utf16le = (s) => Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(s, 'utf16le')]);
const utf16be = (s) => Buffer.concat([Buffer.from([0xfe, 0xff]), Buffer.from(s, 'utf16le').swap16()]);
const utf8bom = (s) => Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from(s, 'utf8')]);
const CP1252 = { '–': 0x96, '€': 0x80 };
const cp1252 = (s) => Buffer.from([...s].map((ch) => CP1252[ch] ?? ch.charCodeAt(0)));

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const lf = (s) => s.replace(/\r\n/g, '\n');
  const file = (name) => path.join(ctx.root, name);
  const bytes = (f) => fs.readFileSync(f);
  const open = async (f) => {
    await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(f)}); return 1; })()`);
    await t.sleep(300);
    return lf(await t.code());
  };
  const tab = (f) => `[...document.querySelectorAll('#tabs .tab')].find(x => x.title === ${JSON.stringify(f)})`;
  const typeAtEnd = async (text) => { await t.cursorEnd(); await t.type(text, 40); };
  const waitSaved = (f) => t.waitFor(`!${tab(f)}?.classList.contains('dirty')`, 6000, 100);

  const files = {
    le: [file('utf16le.tuf'), utf16le(TEXT), TEXT],
    be: [file('utf16be.tuf'), utf16be(TEXT), TEXT],
    bom: [file('utf8bom.tuf'), utf8bom(TEXT), TEXT],
    ansi: [file('ansi.tuf'), cp1252(ANSI_TEXT), ANSI_TEXT],
    // UTF-8 with one Windows-1252 line added to it (Add-Content in Windows PowerShell does this)
    mixed: [file('mixed.tuf'), Buffer.concat([Buffer.from('say "🙂 é"\n', 'utf8'), cp1252('say "é"\n')]), 'say "🙂 é"\nsay "é"\n'],
  };
  for (const [f, data] of Object.values(files)) fs.writeFileSync(f, data);
  const ansiBefore = ctx.tuffCheck(files.ansi[0]); // the runtime asks for UTF-8

  // 1) they open with the right text
  for (const [key, label] of [['le', 'UTF-16 LE (with its BOM)'], ['be', 'UTF-16 BE (with its BOM)'], ['bom', 'UTF-8 with a BOM'], ['ansi', 'Windows-1252 ("ANSI")'], ['mixed', 'UTF-8 with a Windows-1252 line in it']]) {
    const [f, , text] = files[key];
    const shown = await open(f);
    check(`A ${label} file opens with the right text`, shown === lf(text), { shown, want: lf(text) });
  }

  // 2) opening them, switching tabs and losing focus (which saves) changed nothing on disk
  await ev(`window.dispatchEvent(new Event('blur')); 1`);
  await t.sleep(2200); // past the autosave
  const untouched = Object.entries(files).filter(([, [f, data]]) => !bytes(f).equals(data)).map(([k]) => k);
  check('Opening them changes nothing on disk (no file is rewritten)', !untouched.length, untouched);

  // 3) a save that leaves the text as it was leaves the file alone: type a letter and take it out again
  const [be] = files.be;
  await open(be);
  await typeAtEnd('x');
  await t.key('Backspace');
  check('...the tab shows the unsaved dot after typing and deleting a letter', await ev(`!!${tab(be)}?.classList.contains('dirty')`), null);
  const autosaved = await waitSaved(be);
  check('...and saving it leaves the UTF-16 file exactly as it was', autosaved && bytes(be).equals(files.be[1]), { autosaved, head: [...bytes(be).subarray(0, 6)] });

  // 4) a change saves as plain UTF-8, no BOM
  for (const [key, label] of [['le', 'UTF-16'], ['bom', 'UTF-8 with a BOM'], ['ansi', 'Windows-1252'], ['mixed', 'mixed']]) {
    const [f, , text] = files[key];
    await open(f);
    await typeAtEnd('say "added"');
    await t.key('s', ctx.platform === 'darwin' ? 4 : 2);
    const saved = await waitSaved(f);
    const b = bytes(f);
    const want = lf(text) + 'say "added"';
    const asUtf8 = b.toString('utf8');
    const ok = saved && b[0] !== 0xef && b[0] !== 0xff && b[0] !== 0xfe && lf(asUtf8) === lf(want) && !asUtf8.includes('�');
    check(`An edited ${label} file saves as UTF-8 with every character kept`, ok, { saved, head: [...b.subarray(0, 4)], text: asUtf8, want });
  }
  const checked = ctx.tuffCheck(files.ansi[0]).trim();
  if (/No Python found/.test(checked)) t.skip('The saved Windows-1252 file passes tuff --check', checked);
  else check('...and the Tuff runtime reads the saved Windows-1252 file now (tuff --check: OK)', ansiBefore.includes("isn't saved as UTF-8") && checked === 'OK', { before: ansiBefore, after: checked });

  // 5) an agent (or PowerShell) rewrites an open, unedited file as UTF-16: the tab shows the new text
  const [le] = files.le;
  await open(le);
  await t.waitFor(`!${tab(le)}?.classList.contains('dirty')`, 4000);
  const NEW = 'say "rewritten by an agent: ÄÖÜ 🙂"\r\n';
  fs.writeFileSync(le, utf16le(NEW));
  const reloaded = await t.waitFor(`monaco.editor.getEditors()[0].getModel().getValue().includes('rewritten by an agent: ÄÖÜ 🙂')`, 8000, 150);
  check('A UTF-16 file changed on disk while open reloads with the right text', reloaded, lf(await t.code()));
  await t.sleep(2000);
  check('...and isn\'t rewritten by TuffCode after the reload', bytes(le).equals(utf16le(NEW)), [...bytes(le).subarray(0, 6)]);
};
