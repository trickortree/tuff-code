// Links and other Markdown in agents' replies: file:/// links (as Antigravity writes them) and main.tuf:2
// open in the editor, web links ask first (showing the whole site), files on another computer or outside
// the project ask first, javascript: stays text, and tables, numbered lists (with bullets inside a step),
// `code` in a link and a **bold** address draw.
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
  const setup = await ev(`(() => { const b = document.querySelector('.ta-empty [data-setup]'); if (!b) return null; const s = getComputedStyle(b); return { border: s.borderBottomWidth, pad: s.paddingTop }; })()`);
  check('The setup button is not styled like a link in a reply', setup && setup.border === '0px' && setup.pad === '4px', setup);

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
    ols: [...r.querySelectorAll('.ta-md > ol')].map(o => o.getAttribute('start') || '1').join(','),
    look: (() => { const a = r.querySelector('.ta-a.web'), s = getComputedStyle(a); return { display: s.display, pad: s.paddingTop, margin: s.marginTop, size: s.fontSize, text: getComputedStyle(a.parentElement).fontSize }; })(),
    // The steps: 3 numbered items in one list, the bullets inside the first, numbered 1, 2, 3 on screen.
    steps: (() => { const o = [...r.querySelectorAll('.ta-md > ol')].pop(); return { items: o.children.length, inner: [...o.children[0].querySelectorAll(':scope > ul > li')].map(li => li.textContent).join(','), last: o.children[2]?.textContent, lastY: o.children[2]?.getBoundingClientRect().top, innerY: o.children[0].querySelector('ul li')?.getBoundingClientRect().top }; })(),
    codeLink: (() => { const a = [...r.querySelectorAll('.ta-a.file')].find(a => a.querySelector('code')); return a ? { text: a.textContent, file: a.dataset.file } : null; })(),
    boldUrl: (() => { const a = [...r.querySelectorAll('b .ta-a.web')][0]; return a ? { text: a.textContent, url: a.dataset.url } : null; })(),
    stars: /\\*\\*/.test(r.textContent),
  }; })()`);
  const main = path.join(ctx.root, 'main.tuf');
  // On a Mac the temp project is /var/… for the IDE and /private/var/… for the agent: the same folder.
  const same = (a, b) => { try { return fs.realpathSync.native(a).toLowerCase() === fs.realpathSync.native(b).toLowerCase(); } catch { return false; } };
  check('The file:/// link and main.tuf:2 are links to the project\'s main.tuf, with no raw [..](..) left', got.files.slice(0, 2).every((f) => same(f.file, main)) && got.files[1].line === '2' && !got.raw, got);
  check('A web address is a link, and javascript: stays plain text', got.web[0] === 'https://example.com/tuff' && !got.js, got);
  check('A link in a reply sits in the line like its words (not a padded button)', got.look.display === 'inline' && got.look.pad === '0px' && got.look.margin === '0px' && got.look.size === got.look.text, got.look);
  check('The table draws (with bold in a cell), and numbered items split by blank lines read 1, 2', got.table === 'Who,Messages' && got.bold === '3' && got.ols === '1,2,1', got);
  check('Bullets under step 1 sit inside it, so the steps are one list of 3 (1, 2, 3, not 1, 4, 5)', got.steps.items === 3 && got.steps.inner === 'press Run,watch it' && got.steps.last === 'Done' && got.steps.innerY < got.steps.lastY, got.steps);
  check('`notes.tuf` inside a link\'s text shows as code, not "0"', got.codeLink && got.codeLink.text === 'notes.tuf' && same(got.codeLink.file, path.join(ctx.root, 'notes.tuf')), got.codeLink);
  check('**http://localhost:8000** is a bold link to http://localhost:8000, with no ** left', got.boldUrl && got.boldUrl.url === 'http://localhost:8000' && got.boldUrl.text === 'http://localhost:8000' && !got.stars, got);

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

  // A name before the site is dropped: the question (and the browser) get example.com, all of it.
  await waitFor(`document.querySelector('#modal').classList.contains('hidden')`, 3000);
  await ev(`[...${reply}.querySelectorAll('.ta-a.web')].find(a => a.textContent === 'docs').click()`);
  await waitFor(`!document.querySelector('#modal').classList.contains('hidden')`, 5000);
  const docs = await ev(`({ title: document.querySelector('#modal-title').textContent, url: [...${reply}.querySelectorAll('.ta-a.web')].find(a => a.textContent === 'docs').dataset.url })`);
  await ev(`document.querySelector('#modal-cancel').click()`);
  check('https://tuffcode.dev@example.com/docs asks "Open https://example.com/docs in your web browser?"', docs.title === 'Open https://example.com/docs in your web browser?' && docs.url === 'https://example.com/docs', docs);

  // A file on another computer asks, naming it, and Cancel leaves the editor alone.
  const before = await active();
  await waitFor(`document.querySelector('#modal').classList.contains('hidden')`, 3000);
  await ev(`[...${reply}.querySelectorAll('.ta-a.file')].find(a => a.textContent === 'level').click()`);
  const unc = await waitFor(`!document.querySelector('#modal').classList.contains('hidden')`, 5000);
  const uncTitle = await ev(`document.querySelector('#modal-title').textContent`);
  await ev(`document.querySelector('#modal-cancel').click()`);
  await t.sleep(300);
  const share = process.platform === 'win32' ? '\\\\127.0.0.1\\no-such-share\\level.tuf' : '//127.0.0.1/no-such-share/level.tuf';
  check('A link to //127.0.0.1/no-such-share asks first and opens nothing on Cancel', unc && uncTitle === `Open ${share} from another computer?` && (await active()) === before, { uncTitle, active: await active(), before });

  // A file outside the project asks, showing where it is, and opens on Open.
  const outside = path.join(path.dirname(ctx.root), 'outside.tuf');
  fs.writeFileSync(outside, 'say "outside the project"\n');
  await waitFor(`document.querySelector('#modal').classList.contains('hidden')`, 3000);
  await ev(`[...${reply}.querySelectorAll('.ta-a.file')].find(a => a.textContent === 'outside').click()`);
  const out = await waitFor(`!document.querySelector('#modal').classList.contains('hidden') && /from outside your project\\?$/.test(document.querySelector('#modal-title').textContent)`, 5000);
  const outTitle = await ev(`document.querySelector('#modal-title').textContent`);
  const tip = await ev(`[...${reply}.querySelectorAll('.ta-a.file')].find(a => a.textContent === 'outside').title`);
  const openedEarly = String(await active()).toLowerCase().endsWith('outside.tuf');
  await ev(`document.querySelector('#modal-ok').click()`);
  await waitFor(`String(window.TuffIDE.activeFile() || '').toLowerCase().endsWith('outside.tuf')`, 5000);
  check('../outside.tuf asks "Open <its path> from outside your project?" and opens on Open', out && !openedEarly && /^Open .*outside\.tuf from outside your project\?$/.test(outTitle) && same(tip.replace(/^Open /, ''), outside) && same(String(await active()), outside), { outTitle, tip, active: await active() });
};
