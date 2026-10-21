// Links and other Markdown in agents' replies: file:/// links (as Antigravity writes them) and main.tuf:2
// open in the editor, web links ask first, javascript: stays text, and tables and numbered lists draw.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'links and Markdown in agent replies' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const idle = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`);
  const active = () => ev(`window.TuffIDE.activeFile()`);

  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 10000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  // The Claude stand-in sends the reply: every agent's reply goes through the same renderer, and on Windows
  // the Antigravity stand-in (a .cmd) can't take a prompt (it comes on the command line, with newlines).
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"]')`);
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);
  await t.sleep(300);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'notes.tuf'))}); return 1; })()`);
  // The empty panel's "Set up and check agent tools" button keeps its own look: links in replies don't restyle it.
  const setup = await ev(`(() => { const b = document.querySelector('.ta-empty [data-setup]'); if (!b) return null; const s = getComputedStyle(b); return { border: s.borderBottomWidth, display: s.display }; })()`);
  check('The setup button is not styled like a link in a reply', setup && setup.border === '0px' && setup.display === 'inline-flex', setup);

  await send('LINKS please');
  await idle();
  const reply = `[...document.querySelectorAll('.ta-msg.agent')].pop()`;
  const got = await ev(`(() => { const r = ${reply}; return {
    files: [...r.querySelectorAll('.ta-a.file')].map(a => ({ text: a.textContent, file: a.dataset.file, line: a.dataset.line || '' })),
    web: [...r.querySelectorAll('.ta-a.web')].map(a => a.dataset.url),
    raw: /\\]\\((file|main|javascript)/.test(r.textContent),
    js: [...r.querySelectorAll('a')].some(a => /javascript/i.test(a.outerHTML)),
    table: [...r.querySelectorAll('table th')].map(x => x.textContent).join(','),
    bold: r.querySelector('table td b')?.textContent || '',
    ols: [...r.querySelectorAll('ol')].map(o => o.getAttribute('start') || '1').join(','),
    look: (() => { const a = r.querySelector('.ta-a.web'), s = getComputedStyle(a); return { display: s.display, pad: s.paddingTop, margin: s.marginTop, size: s.fontSize, text: getComputedStyle(a.parentElement).fontSize }; })(),
  }; })()`);
  const main = path.join(ctx.root, 'main.tuf');
  // On a Mac the temp project is /var/… for the IDE and /private/var/… for the agent: the same folder.
  const same = (a, b) => { try { return fs.realpathSync.native(a).toLowerCase() === fs.realpathSync.native(b).toLowerCase(); } catch { return false; } };
  check('The file:/// link and main.tuf:2 are links to the project\'s main.tuf, with no raw [..](..) left', got.files.length === 2 && got.files.every((f) => same(f.file, main)) && got.files[1].line === '2' && !got.raw, got);
  check('A web address is a link, and javascript: stays plain text', got.web.join() === 'https://example.com/tuff' && !got.js, got);
  check('A link in a reply sits in the line like its words (not a padded button)', got.look.display === 'inline' && got.look.pad === '0px' && got.look.margin === '0px' && got.look.size === got.look.text, got.look);
  check('The table draws (with bold in a cell), and numbered items split by blank lines read 1, 2', got.table === 'Who,Messages' && got.bold === '3' && got.ols === '1,2', got);

  await ev(`${reply}.querySelector('.ta-a.file').click()`);
  await waitFor(`String(window.TuffIDE.activeFile() || '').toLowerCase().endsWith('main.tuf')`, 5000);
  check('Clicking the file link opens main.tuf in the editor', same(String(await active()), main), await active());

  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'notes.tuf'))}); return 1; })()`);
  await ev(`${reply}.querySelectorAll('.ta-a.file')[1].click()`);
  await waitFor(`String(window.TuffIDE.activeFile() || '').toLowerCase().endsWith('main.tuf')`, 5000);
  await t.sleep(200);
  const pos = await ev(`window.TuffIDE.editor().getPosition()?.lineNumber`);
  check('main.tuf:2 opens main.tuf with the cursor on line 2', String(await active()).toLowerCase().endsWith('main.tuf') && pos === 2, { file: await active(), pos });

  await ev(`${reply}.querySelector('.ta-a.web').click()`);
  const asked = await waitFor(`!document.querySelector('#modal').classList.contains('hidden') && /example\\.com\\/tuff/.test(document.querySelector('#modal-title').textContent)`, 5000);
  const title = await ev(`document.querySelector('#modal-title').textContent`);
  await ev(`document.querySelector('#modal-cancel').click()`); // never really open a browser in a test
  check('A web link asks before opening the browser, and shows the address', asked && /in your web browser\?/.test(title), title);
};
