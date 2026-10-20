// API Explorer, driven like a person would: installs it from the marketplace, types web addresses, clicks
// Send, opens the JSON tree and clicks values, then copies, inserts and saves the Tuff code it writes. Every
// program it writes passes `tuff.py --check`, and runs with tap against a local web server started here, which
// also checks what tap really sent. Also: headers and a JSON body, the answer's colours and tabs, plain-words
// errors (bad address, nothing listening, a 15 s timeout), history (20 kept, survives a restart, clearing),
// the panel at 300 and 400 px wide, and (when online) every example.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { python, REPO, APP_DIR } from '../launch.mjs';

export const meta = { title: 'API Explorer: web requests, the JSON tree and Tuff code for tap', timeout: 420000 };

const WEATHER = { latitude: 51.5, longitude: -0.12, current_units: { time: 'iso8601', temperature_2m: '°C' }, current: { time: '2026-10-20T13:45', temperature_2m: 12.3 } };
const FACTS = { current_page: 1, data: [{ fact: 'Cats sleep a lot.', length: 17 }, { fact: 'Cats have five toes on their front paws.', length: 40 }, { fact: 'A group of cats is a clowder.', length: 29 }], total: 3 };
const PEOPLE = [{ name: 'Ada', langs: ['tuff', 'python'] }, { name: 'Alan', langs: ['tuff'] }];
const ODD = {
  'post code': '90210', '2fast': true, if: 1, text: 'x', 'say "hi"': 'quoted', price: -4.5, gone: null, empty: {},
  nested: { deep: [[1, { x: null }], 'C:\\path\\new', 'tab\there'] },
  big: Array.from({ length: 250 }, (_, i) => i * 2),
};
const TEXT = 'hello from the test server\nsecond line';
// A name with a line separator in it (U+2028): Tuff ends a line there, and has no way to write one.
const LS = String.fromCharCode(0x2028);
const HIDDEN = { [`a${LS}b`]: 1, plain: 2 };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const q = (sel) => `document.querySelector(${JSON.stringify(sel)})`;
  const waitFor = (js, ms = 10000) => t.waitFor(js, ms);
  const sleep = t.sleep;

  // ---------------------------------------------------------------- the local web server
  const seen = []; // every request: { method, url, headers, body }
  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (d) => { body += d; });
    req.on('end', () => {
      seen.push({ method: req.method, url: req.url, headers: req.headers, body });
      const send = (status, type, text) => { res.writeHead(status, type ? { 'Content-Type': type } : {}); res.end(text); };
      const json = (v, status = 200) => send(status, 'application/json; charset=utf-8', JSON.stringify(v));
      const u = req.url.split('?')[0];
      if (u === '/weather') return json(WEATHER);
      if (u === '/facts') return json(FACTS);
      if (u === '/people') return json(PEOPLE);
      if (u === '/odd') return json(ODD);
      if (u === '/hidden') return json(HIDDEN);
      if (u === '/text') return send(200, 'text/plain; charset=utf-8', TEXT);
      if (u === '/echo') {
        let parsed = body;
        try { parsed = JSON.parse(body); } catch {}
        return json({ method: req.method, type: req.headers['content-type'] || null, test: req.headers['x-test'] || null, body: parsed });
      }
      if (u === '/status/404') return json({ message: 'Not Found' }, 404);
      if (u === '/status/500') return send(500, 'text/plain', 'oops');
      if (u === '/slow') return; // never answers
      send(404, 'text/plain', 'no such page');
    });
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const BASE = `http://127.0.0.1:${server.address().port}`;
  const closed = http.createServer();
  await new Promise((r) => closed.listen(0, '127.0.0.1', r));
  const CLOSED = `http://127.0.0.1:${closed.address().port}`;
  await new Promise((r) => closed.close(r));

  // ---------------------------------------------------------------- running Tuff
  const py = python();
  // A packaged app's own runtime (on a Mac it's in TuffCode.app/Contents/Resources), never Python instead.
  const resources = process.platform === 'darwin' ? path.join(path.dirname(ctx.exe), '..', 'Resources') : path.join(path.dirname(ctx.exe), 'resources');
  const runtime = path.join(resources, 'runtime', ctx.win ? 'tuff-runtime.exe' : 'tuff-runtime');
  const tuffCmd = ctx.packaged ? (fs.existsSync(runtime) ? [runtime] : null) : py ? [...py, path.join(REPO, 'tuff.py')] : null;
  const runTuff = (file) => new Promise((resolve) => {
    if (!tuffCmd) { resolve({ code: -1, out: ctx.packaged ? `The packaged app has no Tuff runtime at ${runtime}` : 'No Python found to run tuff.py' }); return; }
    const proc = spawn(tuffCmd[0], [...tuffCmd.slice(1), file], { env: { ...process.env, PYTHONIOENCODING: 'utf-8', NO_PROXY: '127.0.0.1,localhost' }, windowsHide: true });
    let out = '';
    proc.stdout.on('data', (d) => { out += d; });
    proc.stderr.on('data', (d) => { out += d; });
    proc.stdin.end();
    proc.on('close', (code) => resolve({ code, out: out.replace(/\r\n/g, '\n').replace(/\s*Press Enter to close\.\.\.\s*$/, '').trim() }));
  });
  const checkOk = (file) => ctx.tuffCheck(file).trim();
  const proj = (name) => path.join(ctx.root, name);

  // ---------------------------------------------------------------- driving the panel
  // A real mouse click in the middle of what `expr` finds, after making sure nothing covers it.
  async function click(expr, what = expr) {
    const r = await ev(`(() => { const e = ${expr}; if (!e) return null; e.scrollIntoView({ block: 'nearest', inline: 'nearest' }); const b = e.getBoundingClientRect(); const x = b.x + Math.min(b.width / 2, 40), y = b.y + b.height / 2; const h = document.elementFromPoint(x, y); return { x, y, w: b.width, hit: !!h && (h === e || e.contains(h)) }; })()`);
    if (!r || !r.w) throw new Error(`Nothing to click: ${what}`);
    if (!r.hit) throw new Error(`Something covers ${what}`);
    await t.click(r.x, r.y);
  }
  // Click a text box, select what's in it and type over it.
  async function fill(expr, text, delay = 12) {
    await click(expr);
    await t.key('A', 2);
    await t.key('Backspace');
    await t.type(text, delay);
  }
  const button = (scope, text) => `[...document.querySelectorAll(${JSON.stringify(scope)})].find((b) => b.textContent.trim() === ${JSON.stringify(text)})`;
  const answered = () => waitFor(`!!document.querySelector('.ax-main .ax-status, .ax-main .ax-err')`, 20000);
  async function sendTo(url) {
    await fill(q('.ax-url'), url);
    await click(q('.ax-send'), 'Send');
    return answered();
  }
  // The tree row for a path of keys (strings) and positions (numbers), opening rows on the way.
  const rowExpr = (keys) => `(() => { let scope = document.querySelector('.ax-tree > .ax-node > .ax-kids'); let row = null;
    for (const k of ${JSON.stringify(keys)}) {
      if (!scope) return null;
      row = [...scope.children].map((n) => n.querySelector(':scope > .ax-row')).find((r) => r && r.querySelector('.ax-k')?.textContent === String(k));
      if (!row) return null;
      scope = row.nextElementSibling;
    }
    return row; })()`;
  async function openRow(keys) {
    if (await ev(`${rowExpr(keys)}?.classList.contains('open')`)) return;
    await click(`${rowExpr(keys)}.querySelector('.ax-tog')`, `the arrow of ${keys.join(' › ')}`);
  }
  async function pick(keys) {
    for (let i = 1; i < keys.length; i++) await openRow(keys.slice(0, i));
    await click(`${rowExpr(keys)}.querySelector('.ax-v')`, `the value of ${keys.join(' › ')}`);
    await waitFor(`!document.querySelector('.ax-drawer').classList.contains('hidden')`, 3000);
  }
  // The code on screen: one block per line.
  const shownCode = () => ev(`(() => { const lines = [...document.querySelectorAll('.ax-drawer .ax-pre .ln')].map((l) => l.textContent); return lines.length ? lines.join('\\n') + '\\n' : ''; })()`);
  const setMode = async (whole) => { await click(button('.ax-mode button', whole ? 'Whole program' : 'Short')); await sleep(100); };
  const status = () => ev(`(() => { const c = document.querySelector('.ax-code'); return c && { text: c.textContent.trim(), cls: c.className, color: getComputedStyle(c).color, meta: [...document.querySelectorAll('.ax-meta')].map((m) => m.textContent), why: document.querySelector('.ax-why')?.textContent || '' }; })()`);
  const errorShown = () => ev(`(() => { const e = document.querySelector('.ax-err'); return e && { kind: e.dataset.kind, title: e.querySelector('b').textContent, text: e.querySelector('p').textContent, retry: !!e.querySelector('[data-a="retry"]') }; })()`);
  const token = (name) => ev(`(() => { const s = document.createElement('span'); s.style.color = 'var(${name})'; document.body.append(s); const c = getComputedStyle(s).color; s.remove(); return c; })()`);
  const rightbar = () => ev(`(() => { const r = document.querySelector('#rightbar').getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; })()`);
  const shots = [];
  const shoot = async (name) => { await ev(`document.querySelectorAll('.toast').forEach((x) => x.remove()); 1`); await sleep(250); shots.push(await t.shot(name, await rightbar())); };
  const setWidth = async (px) => { await ev(`document.documentElement.style.setProperty('--rightbar-w', '${px}px'); 1`); await sleep(250); };
  // Save the shown code into the scratch project, --check it and run it.
  let nSaved = 0;
  async function saveAndRun(code) {
    const file = proj(`gen_${++nSaved}.tuf`);
    fs.writeFileSync(file, code);
    return { file, check: checkOk(file), run: await runTuff(file) };
  }
  const tapSaw = (pred) => seen.filter((r) => /TuffCode-tap/.test(r.headers['user-agent'] || '') && pred(r));
  // Waits up to 6 s for something on disk.
  const until = async (fn) => { for (let i = 0; i < 40; i++) { if (fn()) return true; await sleep(150); } return false; };
  const setMethod = async (m, key) => {
    await ev(`document.querySelector('.ax-method').focus()`);
    for (let i = 0; i < 4 && (await ev(`document.querySelector('.ax-method').value`)) !== m; i++) await t.key(key);
    if ((await ev(`document.querySelector('.ax-method').value`)) !== m) {
      t.info(`The arrow keys didn't pick ${m} in the closed dropdown here; picking it through its value`);
      await ev(`(() => { const s = document.querySelector('.ax-method'); s.value = ${JSON.stringify(m)}; s.dispatchEvent(new Event('change', { bubbles: true })); return 1; })()`);
    }
  };

  try {
    // ---------------------------------------------------------------- 1. install from the marketplace
    fs.writeFileSync(proj('main.tuf'), '# my program\n');
    await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(proj('main.tuf'))}); return 1; })()`);
    await ev(`(() => { window.TuffIDE.showSideView('plugins', true); return 1; })()`);
    await waitFor(`!!document.querySelector('.pl-card[data-id="api-explorer"]')`);
    const card = await ev(`(() => { const c = document.querySelector('.pl-card[data-id="api-explorer"]'); return c && { name: c.querySelector('.pl-name b').textContent, by: c.querySelector('.pl-by').textContent, tags: [...c.querySelectorAll('.pl-tags span')].map((s) => s.textContent) }; })()`);
    check('The marketplace lists API Explorer as coming with TuffCode', card && card.name === 'API Explorer' && /comes with TuffCode/.test(card.by), card);
    await click(`document.querySelector('.pl-card[data-id="api-explorer"] [data-a="install"]')`, 'Install');
    const opened = await waitFor(`!document.querySelector('#rightbar').classList.contains('hidden') && !!document.querySelector('.ax .ax-item')`, 15000);
    const first = await ev(`({ title: document.querySelector('#rb-title').textContent, examples: document.querySelectorAll('.ax-item[data-ex]').length, tab: document.querySelector('.ax-tabs .on')?.textContent.trim(), strip: [...document.querySelectorAll('#toolstrip-right .ts-btn')].map((b) => b.title), method: document.querySelector('.ax-method').value, body: !document.querySelector('[data-a="body"]').classList.contains('hidden') })`);
    check('Installing opens the API Explorer panel on the right, on its Examples', opened && first.title === 'API Explorer' && first.tab === 'Examples' && first.examples >= 6 && first.strip.includes('API Explorer'), first);
    check('It starts on GET, with no Body for a GET', first.method === 'GET' && !first.body, first);
    await shoot('api-explorer-1-examples-400.png');

    // Shortcut keys pressed while typing in the address box stay with the box: the IDE's Ctrl+D (copy a line),
    // Ctrl+Y (delete a line) and Ctrl+Shift+Z (redo) would change the open code file and move the cursor there.
    const keysBefore = await t.code();
    await fill(q('.ax-url'), `${BASE}/weather`);
    await t.key('D', 2);
    await t.key('Y', 2);
    await t.key('Z', 10);
    await sleep(200);
    const keysAfter = { code: await t.code(), focus: await ev(`document.activeElement === document.querySelector('.ax-url')`), url: await ev(`document.querySelector('.ax-url').value`) };
    check('Ctrl+D, Ctrl+Y and Ctrl+Shift+Z in the address box leave the code file alone, and the box keeps the focus', keysAfter.code === keysBefore && keysAfter.focus && keysAfter.url === `${BASE}/weather`, { keysBefore, keysAfter });

    // ---------------------------------------------------------------- 2. a GET with JSON: status, time, size, the tree
    await sendTo(`${BASE}/weather`);
    const st = await status();
    const green = await token('--green');
    check('GET /weather: "200 OK" in green, with the time and the size', st && st.text === '200 OK' && /\bok\b/.test(st.cls) && st.color === green && /\d+ ms/.test(st.meta[0]) && st.meta[1] === `${Buffer.byteLength(JSON.stringify(WEATHER))} B`, { st, green });
    const tree = await ev(`({ tab: document.querySelector('.ax-tabs .on')?.textContent.trim(), subs: [...document.querySelectorAll('.ax-sub button')].map((b) => b.textContent.trim()), rows: [...document.querySelectorAll('.ax-tree .ax-row')].map((r) => r.textContent) })`);
    check('The answer shows as a tree, with Tree, Raw and Headers tabs', tree.tab === 'Answer' && tree.subs[0] === 'Tree' && tree.subs[1] === 'Raw' && /^Headers\s*\d+$/.test(tree.subs[2]) && tree.rows.includes('temperature_2m:12.3') && tree.rows.includes('current:{ 2 values }'), tree);
    const colors = await ev(`(() => { const c = (sel) => { const e = document.querySelector(sel); return e && getComputedStyle(e).color; }; return { str: c('.ax-v.str'), num: c('.ax-v.num'), sum: c('.ax-v.sum') }; })()`);
    const yellow = await token('--yellow');
    check('Values are coloured by type (text green, numbers yellow, groups grey)', colors.str === green && colors.num === yellow && colors.sum !== green && colors.sum !== yellow, { colors, green, yellow });

    // ---------------------------------------------------------------- 3. click a value: the Tuff code
    await pick(['current', 'temperature_2m']);
    const want1 = `mention tap\nres = tap.get("${BASE}/weather")\ndata = res:json\ntemperature_2m = data:get("current"):get("temperature_2m")\n`;
    const d1 = await ev(`({ path: document.querySelector('.ax-path').textContent, sel: document.querySelector('.ax-row.sel')?.textContent })`);
    check('Clicking temperature_2m shows the tap code that reaches it', (await shownCode()) === want1 && d1.path === 'current › temperature_2m' && d1.sel === 'temperature_2m:12.3', { code: await shownCode(), d1 });

    // Copy
    await t.focus();
    await click(button('.ax-dbtns button', 'Copy'), 'Copy');
    await sleep(300);
    let clip = null;
    try { clip = await ev(`navigator.clipboard.readText()`); } catch (err) { clip = `(couldn't read: ${err.message})`; }
    check('Copy puts the code on the clipboard', String(clip).replace(/\r\n/g, '\n') === want1, clip);

    // Insert into main.tuf, save with Ctrl+S, --check and run it
    await t.cursorEnd();
    await click(button('.ax-dbtns button', 'Insert'), 'Insert');
    await sleep(300);
    check('Insert puts the code into the open file at the cursor', (await t.code()) === `# my program\n${want1}`, await t.code());
    await ev(`monaco.editor.getEditors()[0].focus()`);
    await t.key('S', 2);
    const savedMain = await until(() => fs.readFileSync(proj('main.tuf'), 'utf8').includes('temperature_2m'));
    const mainCheck = checkOk(proj('main.tuf'));
    const before = tapSaw((r) => r.url === '/weather').length;
    const mainRun = await runTuff(proj('main.tuf'));
    check('main.tuf with the inserted code is saved, passes --check and runs (tap GETs /weather)', savedMain && mainCheck === 'OK' && mainRun.code === 0 && tapSaw((r) => r.url === '/weather' && r.method === 'GET').length === before + 1, { savedMain, mainCheck, mainRun });

    // Whole program, saved as a new file (the "files" permission) and run
    await setMode(true);
    const whole1 = await shownCode();
    check('"Whole program" checks res:ok and says the value', whole1 === `mention tap\n\nres = tap.get("${BASE}/weather")\nif res:ok:\n    data = res:json\n    temperature_2m = data:get("current"):get("temperature_2m")\n    say "temperature_2m: " + temperature_2m\nelse:\n    say "Something went wrong. The server answered " + res:status\n`, whole1);
    await click(button('.ax-dbtns button', 'Save as new file'), 'Save as new file');
    const savedNew = await until(() => fs.existsSync(proj('temperature_2m.tuf')));
    await waitFor(`(window.TuffIDE.activeFile() || '').endsWith('temperature_2m.tuf')`, 5000);
    const newFile = savedNew ? fs.readFileSync(proj('temperature_2m.tuf'), 'utf8') : '';
    const run1 = savedNew ? await runTuff(proj('temperature_2m.tuf')) : {};
    check('"Save as new file" writes temperature_2m.tuf into the project and opens it', savedNew && newFile === whole1 && (await ev(`window.TuffIDE.activeFile()`)).endsWith('temperature_2m.tuf'), { savedNew, active: await ev(`window.TuffIDE.activeFile()`) });
    check('temperature_2m.tuf passes --check and says "temperature_2m: 12.3" when run', checkOk(proj('temperature_2m.tuf')) === 'OK' && run1.code === 0 && run1.out === 'temperature_2m: 12.3', { check: checkOk(proj('temperature_2m.tuf')), run1 });
    const codeBox = await ev(`(() => { const p = document.querySelector('.ax-pre'); const lines = [...p.querySelectorAll('.ln')]; return { sideways: p.scrollWidth > p.clientWidth + 1, wrapped: lines.filter((l) => l.getClientRects().length > 1 || l.offsetHeight > 24).length }; })()`);
    check('At 400 px the code box wraps long lines instead of scrolling sideways', !codeBox.sideways && codeBox.wrapped >= 1, codeBox);
    await shoot('api-explorer-2-code-400.png');
    // A second save doesn't overwrite the first
    await click(button('.ax-dbtns button', 'Save as new file'), 'Save as new file');
    const second = await until(() => fs.existsSync(proj('temperature_2m_2.tuf')));
    check('Saving again makes temperature_2m_2.tuf instead of overwriting', second && fs.readFileSync(proj('temperature_2m.tuf'), 'utf8') === whole1, second);
    await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(proj('main.tuf'))}); return 1; })()`);

    // ---------------------------------------------------------------- 4. lists: Tuff positions start at 0
    await sendTo(`${BASE}/facts`);
    const list = await ev(`[...document.querySelectorAll('.ax-tree .ax-row')].map((r) => r.textContent)`);
    check('A list is labelled with its item count, and its items by position from 0', list.includes('data:[ 3 items ]') && list.includes('0:{ 2 values }') && list.includes('2:{ 2 values }'), list);
    await pick(['data', 1, 'fact']);
    check('The drawer keeps showing the kind of code picked last (Whole program)', (await ev(`document.querySelector('.ax-mode .on').textContent`)) === 'Whole program', null);
    await setMode(false);
    const code2 = await shownCode();
    const tip = await ev(`document.querySelector('.ax-tip')?.textContent || ''`);
    check('The second fact is data:get("data")[1]:get("fact"), with a note that lists start at 0', code2.endsWith(`fact = data:get("data")[1]:get("fact")\n`) && /start at 0/.test(tip), { code2, tip });
    // Short code inserted into a file that already mentions tap: no second "mention tap"
    await t.cursorEnd();
    await click(button('.ax-dbtns button', 'Insert'), 'Insert');
    await sleep(300);
    const twice = await t.code();
    check('Inserting into a file that already mentions tap leaves out "mention tap"', (twice.match(/mention tap/g) || []).length === 1 && twice.includes(`res = tap.get("${BASE}/facts")`), twice);
    await setMode(true);
    const g2 = await saveAndRun(await shownCode());
    check('Whole program for data[1].fact passes --check and says the SECOND fact', g2.check === 'OK' && g2.run.code === 0 && g2.run.out === `fact: ${FACTS.data[1].fact}`, g2);

    // A list at the top, and a list inside an item
    await sendTo(`${BASE}/people`);
    await pick([0, 'langs', 1]);
    const code3 = await shownCode();
    const g3 = await saveAndRun(code3);
    check('people[0].langs[1] is data[0]:get("langs")[1], passes --check and says python', code3.includes('lang = data[0]:get("langs")[1]') && g3.check === 'OK' && g3.run.out === 'langs[1]: python', { code3, g3 });
    await pick([1]);
    const g4 = await saveAndRun(await shownCode());
    check('A whole item (a data object) is said on its own line, as JSON', g4.check === 'OK' && g4.run.code === 0 && g4.run.out.startsWith('data[1]:\n') && JSON.parse(g4.run.out.slice(8)).name === 'Alan', g4);

    // ---------------------------------------------------------------- 5. awkward names, long lists
    await sendTo(`${BASE}/odd`);
    const oddCases = [
      [['post code'], 'post_code = data:get("post code")', 'post code: 90210'],
      [['2fast'], 'value_2fast = data:get("2fast")', '2fast: true'],
      [['if'], 'if_value = data:get("if")', 'if: 1'],
      [['text'], 'text_value = data:get("text")', 'text: x'],
      [['say "hi"'], 'say_hi = data:get("say \\"hi\\"")', 'say "hi": quoted'],
      [['price'], 'price = data:get("price")', 'price: -4.5'],
      [['gone'], 'gone = data:get("gone")', 'gone: nil'],
      [['nested', 'deep', 0, 1, 'x'], 'x = data:get("nested"):get("deep")[0][1]:get("x")', 'x: nil'],
      [['nested', 'deep', 1], 'deep_item = data:get("nested"):get("deep")[1]', 'deep[1]: C:\\path\\new'],
      [['nested', 'deep', 2], 'deep_item = data:get("nested"):get("deep")[2]', 'deep[2]: tab\there'],
    ];
    const oddResults = [];
    for (const [keys, line, out] of oddCases) {
      await pick(keys);
      const code = await shownCode();
      const g = await saveAndRun(code);
      oddResults.push({ keys, ok: code.includes(`    ${line}\n`) && g.check === 'OK' && g.run.code === 0 && g.run.out === out, line, code, g });
    }
    const oddBad = oddResults.filter((r) => !r.ok);
    check(`Awkward JSON names make good Tuff names and texts (${oddCases.length} values: spaces, digits, keywords, built-ins, quotes, backslashes, tabs, nil): each passes --check and says the value`, oddBad.length === 0, oddBad.slice(0, 2));
    await openRow(['big']);
    const bigRows = () => ev(`${rowExpr(['big'])}.nextElementSibling.querySelectorAll(':scope > .ax-node').length`);
    const n1 = await bigRows();
    const moreText = await ev(`${rowExpr(['big'])}.nextElementSibling.querySelector('.ax-more')?.textContent`);
    await click(`${rowExpr(['big'])}.nextElementSibling.querySelector('.ax-more')`, 'Show more');
    const n2 = await bigRows();
    check('A 250-item list shows 100 rows, then "Show 100 more"', n1 === 100 && moreText === 'Show 100 more (250 in all)' && n2 === 200, { n1, n2, moreText });
    await click(`${rowExpr(['big'])}.querySelector('.ax-tog')`, 'close big');
    check('The arrow closes a list again', !(await ev(`${rowExpr(['big'])}.classList.contains('open')`)) && (await ev(`${rowExpr(['big'])}.nextElementSibling.children.length`)) === 0, null);
    // Keyboard: Down from the first row, Enter picks it
    await click(`document.querySelector('.ax-tree .ax-row')`, 'the first row');
    await t.key('ArrowDown');
    await t.key('Enter');
    check('Arrow keys move through the tree and Enter picks a row', (await ev(`document.querySelector('.ax-path').textContent`)) === 'post code', await ev(`document.querySelector('.ax-path').textContent`));

    // A name with a hidden line separator: Tuff can't write it, so the code changes it (and still passes
    // --check), and the drawer says so. A plain name next to it gets no such note.
    await sendTo(`${BASE}/hidden`);
    await pick([`a${LS}b`]);
    const hid = { code: await shownCode(), note: await ev(`document.querySelector('.ax-inexact')?.textContent || ''`) };
    const gh = await saveAndRun(hid.code);
    await pick(['plain']);
    const plainNote = await ev(`!!document.querySelector('.ax-inexact')`);
    check('A name with a hidden character: the code passes --check and the drawer says Tuff had to change it', gh.check === 'OK' && !hid.code.includes(LS) && /hidden character/.test(hid.note) && !plainNote, { hid, check: gh.check, plainNote });

    // ---------------------------------------------------------------- 6. a text answer; Raw and Headers
    await sendTo(`${BASE}/text`);
    const txt = await ev(`({ subs: [...document.querySelectorAll('.ax-sub button')].map((b) => b.textContent.trim()), pre: document.querySelector('.ax-raw')?.textContent })`);
    check('Plain text shows as text (Text and Headers tabs)', txt.subs[0] === 'Text' && txt.subs.length === 2 && txt.pre === TEXT, txt);
    await click(`document.querySelector('[data-a="code-all"]')`, 'Tuff code');
    await setMode(true);
    const g5 = await saveAndRun(await shownCode());
    check('"Tuff code" for a text answer uses res:text; the program says the text', (await shownCode()).includes('    say res:text\n') && g5.check === 'OK' && g5.run.out === TEXT, g5);
    await click(`[...document.querySelectorAll('.ax-sub button')].find((b) => b.dataset.sub === 'headers')`, 'Headers tab');
    const heads = await ev(`[...document.querySelectorAll('.ax-heads > div')].map((d) => d.querySelector('b').textContent + '=' + d.querySelector('span').textContent)`);
    check('The Headers tab lists what the server sent back', heads.includes('content-type=text/plain; charset=utf-8'), heads);
    await sendTo(`${BASE}/weather`);
    await click(`[...document.querySelectorAll('.ax-sub button')].find((b) => b.dataset.sub === 'raw')`, 'Raw tab');
    check('The Raw tab shows exactly what came back', (await ev(`document.querySelector('.ax-raw').textContent`)) === JSON.stringify(WEATHER), null);

    // ---------------------------------------------------------------- 7. 4xx and 5xx in red, in plain words
    await sendTo(`${BASE}/status/404`);
    const s404 = await status();
    const red = await token('--red');
    check('404 shows "404 Not found" in red, and says what it means', s404.text === '404 Not found' && /\bbad\b/.test(s404.cls) && s404.color === red && /nothing at this address/.test(s404.why), { s404, red });
    await sendTo(`${BASE}/status/500`);
    const s500 = await status();
    check('500 shows in red too, and says it isn\'t your fault', s500.text === '500 Server error' && s500.color === red && /on the server/.test(s500.why), s500);

    // ---------------------------------------------------------------- 8. POST with a header and a JSON body; PUT; DELETE
    // The method dropdown, with the keyboard (a click would open the system's own list, outside the page)
    await fill(q('.ax-url'), `${BASE}/echo`);
    await setMethod('POST', 'ArrowDown');
    const post = await ev(`({ method: document.querySelector('.ax-method').value, body: !document.querySelector('.ax-bodyed').classList.contains('hidden') })`);
    check('Picking POST opens the Body box', post.method === 'POST' && post.body, post);
    await click(`document.querySelector('[data-a="headers"]')`, 'Headers');
    await fill(`document.querySelector('.ax-hrow input[data-f="name"]')`, 'X-Test');
    await fill(`document.querySelector('.ax-hrow input[data-f="value"]')`, 'hello');
    const bodyJson = '{"title": "Hi", "tags": ["a", "b"], "n": 5, "author": {"name": "Ada"}}';
    // An unfinished body is caught before anything is sent
    const nBefore = seen.length;
    await fill(`document.querySelector('.ax-body')`, '{title: Hi}');
    await click(q('.ax-send'), 'Send');
    await sleep(300);
    const bodyErr = await ev(`(() => { const e = document.querySelector('.ax-bodyerr'); return e.classList.contains('hidden') ? null : e.textContent; })()`);
    check("A body that isn't JSON yet is caught, in plain words, and nothing is sent", !!bodyErr && /isn't JSON yet/.test(bodyErr) && /double quotes/.test(bodyErr) && seen.length === nBefore, { bodyErr, sent: seen.length - nBefore });
    await fill(`document.querySelector('.ax-body')`, bodyJson, 6);
    const bodyKeysBefore = await t.code();
    await t.key('D', 2);
    await t.key('Y', 2);
    await sleep(200);
    check('Ctrl+D and Ctrl+Y in the Body box leave the code file alone', (await t.code()) === bodyKeysBefore && (await ev(`document.activeElement === document.querySelector('.ax-body') && document.querySelector('.ax-body').value`)) === bodyJson, await t.code());
    await setWidth(300);
    await click(q('.ax-send'), 'Send');
    await answered();
    const echo = seen[seen.length - 1];
    check('POST sends the header and the JSON body with Content-Type: application/json', echo.method === 'POST' && echo.url === '/echo' && echo.headers['x-test'] === 'hello' && echo.headers['content-type'] === 'application/json' && JSON.stringify(JSON.parse(echo.body)) === JSON.stringify(JSON.parse(bodyJson)), echo);
    await pick(['body', 'title']);
    await setMode(true);
    const postCode = await shownCode();
    const nTap = tapSaw(() => true).length;
    const g6 = await saveAndRun(postCode);
    const tapPost = tapSaw(() => true).slice(nTap)[0] || {};
    check('The POST program builds the body with tap.data() and :set, and sends the header', postCode.includes('headers:set("X-Test", "hello")') && postCode.includes('author = tap.data()') && postCode.includes('body:set("tags", ["a", "b"])') && postCode.includes(`res = tap.post("${BASE}/echo", body, headers)`), postCode);
    check('...passes --check, says "title: Hi", and tap sends the same JSON, header and type', g6.check === 'OK' && g6.run.out === 'title: Hi' && tapPost.method === 'POST' && tapPost.headers?.['x-test'] === 'hello' && tapPost.headers?.['content-type'] === 'application/json' && JSON.stringify(JSON.parse(tapPost.body || 'null')) === JSON.stringify(JSON.parse(bodyJson)), { g6, tapPost });
    // Layout at 300 px: nothing sticks out, every button can be clicked
    const layout = () => ev(`(() => { const p = document.querySelector('#rightbar').getBoundingClientRect(); const out = []; for (const e of document.querySelectorAll('.ax-bar > *, .ax-opts button:not(.hidden), .ax-hrow > *, .ax-tabs button, .ax-dbtns button, .ax-mode button, .ax-status > *')) { const r = e.getBoundingClientRect(); if (r.width && (r.left < p.left - 0.5 || r.right > p.right + 0.5 || r.bottom > p.bottom + 0.5)) out.push(e.className + ' ' + e.textContent.trim()); } return { w: Math.round(p.width), out, main: Math.round(document.querySelector('.ax-main').getBoundingClientRect().height), wide: [...document.querySelectorAll('.ax, .ax-main, .ax-drawer, .ax-bar, .ax-tabs, .ax-pre')].filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.className) }; })()`);
    const lay = await layout();
    check('At 300 px wide, with the headers, the body and the code all open, nothing sticks out and nothing scrolls sideways', lay.w === 300 && lay.out.length === 0 && lay.wide.length === 0 && lay.main >= 60, lay);
    await shoot('api-explorer-3-post-300.png');
    await setWidth(400);
    // Text body
    await click(button('.ax-btype button', 'Text'), 'Text');
    await fill(`document.querySelector('.ax-body')`, 'just words');
    await click(q('.ax-send'), 'Send');
    await answered();
    const textEcho = seen[seen.length - 1];
    check('A Text body goes as text/plain', textEcho.body === 'just words' && /^text\/plain/.test(textEcho.headers['content-type']), textEcho);
    // PUT, then DELETE (no Body button for DELETE)
    await setMethod('PUT', 'ArrowDown');
    await click(q('.ax-send'), 'Send');
    await answered();
    check('PUT sends too', seen[seen.length - 1].method === 'PUT' && seen[seen.length - 1].body === 'just words', seen[seen.length - 1].method);
    await setMethod('DELETE', 'ArrowDown');
    const delUi = await ev(`({ bodyBtn: document.querySelector('[data-a="body"]').classList.contains('hidden'), bodyBox: document.querySelector('.ax-bodyed').classList.contains('hidden') })`);
    await click(q('.ax-send'), 'Send');
    await answered();
    const del = seen[seen.length - 1];
    await pick(['method']);
    await setMode(true);
    const delCode = await shownCode();
    const g7 = await saveAndRun(delCode);
    check('DELETE hides the Body, sends no body, and its program uses tap.delete', delUi.bodyBtn && delUi.bodyBox && del.method === 'DELETE' && del.body === '' && delCode.includes(`res = tap.delete("${BASE}/echo", headers)`) && g7.check === 'OK' && g7.run.out === 'method: DELETE', { delUi, del: del.method, delCode, g7 });
    // Back to a plain GET
    await click(`document.querySelector('.ax-hrow [data-a="del-header"]')`, 'remove the header');
    await setMethod('GET', 'ArrowUp');

    // ---------------------------------------------------------------- 9. errors in plain words
    await sendTo('http://nope.invalid/');
    const e1 = await errorShown();
    check('A website that doesn\'t exist: "Couldn\'t find that website" (or "No internet" when offline)', e1 && ((e1.kind === 'address' && /no website called nope\.invalid/.test(e1.text)) || e1.kind === 'offline') && e1.retry, e1);
    await sendTo(`${CLOSED}/x`);
    const e2 = await errorShown();
    check('Nothing listening: "Nothing answered", with Try again', e2 && e2.kind === 'refused' && e2.title === 'Nothing answered' && e2.retry, e2);
    const nFtp = seen.length;
    await sendTo('ftp://example.com/file');
    const e3 = await errorShown();
    check('Not a web address: says what one looks like, and sends nothing', e3 && e3.title === "That isn't a web address" && /https:\/\//.test(e3.text) && !e3.retry && seen.length === nFtp, e3);
    await sendTo(`${BASE}/two words`);
    const e5 = await errorShown();
    await fill(q('.ax-url'), ' ');
    await click(q('.ax-send'), 'Send');
    await sleep(200);
    const e6 = await errorShown();
    check('A space in the address, or no address at all, is explained and nothing is sent', e5?.text === "A web address can't have spaces in it. Write a space as %20." && e6?.title === 'Type a web address first' && seen.length === nFtp, { e5, e6 });
    await sendTo(`${BASE.replace('http://', '')}/text`);
    check('An address without http:// gets it added, and works', (await ev(`document.querySelector('.ax-url').value`)) === `${BASE}/text` && (await status())?.text === '200 OK', await ev(`document.querySelector('.ax-url').value`));
    await fill(q('.ax-url'), `${BASE}/slow`);
    const tSlow = Date.now();
    await click(q('.ax-send'), 'Send');
    await sleep(1500);
    const waiting = await ev(`({ wait: document.querySelector('.ax-wait')?.textContent || '', send: document.querySelector('.ax-send').textContent, disabled: document.querySelector('.ax-send').disabled })`);
    check('While it waits: "Waiting for an answer" with the seconds, and Send says Sending…', /Waiting for an answer from 127\.0\.0\.1/.test(waiting.wait) && /\d s$/.test(waiting.wait) && waiting.send === 'Sending…' && waiting.disabled, waiting);
    await waitFor(`!!document.querySelector('.ax-err')`, 25000);
    const e4 = await errorShown();
    check(`No answer within 15 s: "No answer in time" (after ${((Date.now() - tSlow) / 1000).toFixed(1)} s)`, e4 && e4.kind === 'timeout' && e4.title === 'No answer in time' && /15 seconds/.test(e4.text), e4);
    // "No internet" can't be made for real here, so check the words for Chromium's offline error.
    const G = createRequire(import.meta.url)(path.join(APP_DIR, 'plugins', 'api-explorer', 'panel.js'));
    const off = G.explain(new Error("Error invoking remote method 'plugins:request': Error: net::ERR_INTERNET_DISCONNECTED"), 'https://catfact.ninja/fact');
    check('Offline (net::ERR_INTERNET_DISCONNECTED) reads "No internet"', off.kind === 'offline' && off.title === 'No internet' && /Wi-Fi/.test(off.text), off);
    await shoot('api-explorer-4-error-400.png');

    // ---------------------------------------------------------------- 10. history: the last 20, kept, cleared
    await click(`document.querySelector('.ax-tabs [data-v="history"]')`, 'History');
    const hist = await ev(`[...document.querySelectorAll('.ax-hitem')].map((h) => [...h.querySelectorAll('span')].filter((s) => !s.children.length).map((s) => s.textContent.trim()).join(' | '))`);
    check('History lists the requests, newest first, with their status or error', hist.length >= 10 && /^GET \| 127\.0\.0\.1:\d+\/slow \| No answer in time/.test(hist[0]) && hist.some((h) => /^POST \| 127\.0\.0\.1:\d+\/echo \| 200/.test(h)) && hist.some((h) => /\/status\/404 \| 404/.test(h)), hist.slice(0, 6));
    const histColor = await ev(`getComputedStyle(document.querySelector('.ax-hs.bad')).color`);
    check('Failed requests are red in the history', histColor === red, histColor);
    // Click a GET in the history: it's sent again
    const nWeather = seen.filter((r) => r.url === '/weather').length;
    await click(`[...document.querySelectorAll('.ax-hitem')].find((h) => /\\/weather/.test(h.textContent))`, 'the /weather row');
    await answered();
    check('Clicking a GET in the history sends it again', seen.filter((r) => r.url === '/weather').length === nWeather + 1 && (await status())?.text === '200 OK', null);
    // A password in a header is sent, but not kept in the history (which lives in the settings file)
    const stored = () => { try { return JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8')).pluginData?.['api-explorer']?.history || null; } catch { return null; } };
    if (await ev(`document.querySelector('.ax-hdrs').classList.contains('hidden')`)) await click(`document.querySelector('[data-a="headers"]')`, 'Headers');
    if (!(await ev(`!!document.querySelector('.ax-hrow')`))) await click(`document.querySelector('[data-a="add-header"]')`, 'Add a header');
    await fill(`document.querySelector('.ax-hrow input[data-f="name"]')`, 'Authorization');
    await fill(`document.querySelector('.ax-hrow input[data-f="value"]')`, 'Bearer s3cret');
    await sendTo(`${BASE}/text?auth=1`);
    await sleep(400);
    const authSent = seen[seen.length - 1];
    const authKept = (stored() || []).find((h) => /auth=1/.test(h.url));
    check('A header like Authorization is sent, but its value is not kept in the history', authSent.headers.authorization === 'Bearer s3cret' && authKept && JSON.stringify(authKept.headers) === '[["Authorization",""]]' && !fs.readFileSync(ctx.settingsFile, 'utf8').includes('s3cret'), { sent: authSent.headers.authorization, authKept });
    await click(`document.querySelector('.ax-hrow [data-a="del-header"]')`, 'remove the header');
    await click(`document.querySelector('.ax-tabs [data-v="history"]')`, 'History');
    const nAuth = seen.length;
    await click(`[...document.querySelectorAll('.ax-hitem')].find((h) => /auth=1/.test(h.textContent))`, 'the auth=1 row');
    await sleep(600);
    const authBack = await ev(`({ name: document.querySelector('.ax-hrow input[data-f="name"]')?.value, value: document.querySelector('.ax-hrow input[data-f="value"]')?.value })`);
    check('Clicking it in the history waits for the password to be typed again instead of sending', seen.length === nAuth && authBack.name === 'Authorization' && authBack.value === '', { authBack, sent: seen.length - nAuth });
    await click(`document.querySelector('.ax-hrow [data-a="del-header"]')`, 'remove the header');

    // Fill it past 20 (the address is set directly to save typing time; Send is a real click)
    for (let i = 1; i <= 22; i++) {
      await ev(`(() => { const u = document.querySelector('.ax-url'); u.value = ${JSON.stringify(`${BASE}/text?n=`)} + ${i}; u.dispatchEvent(new Event('input', { bubbles: true })); return 1; })()`);
      await click(q('.ax-send'), 'Send');
      await answered();
      await waitFor(`!document.querySelector('.ax-send').disabled`, 5000);
    }
    await sleep(600);
    const h20 = stored();
    check('Only the last 20 requests are kept (saved through t.storage)', h20 && h20.length === 20 && h20[0].url === `${BASE}/text?n=22` && h20[19].url === `${BASE}/text?n=3`, h20 && h20.map((h) => h.url.slice(-6)));
    await t.reload();
    const back = await waitFor(`!!document.querySelector('.ax')`, 15000);
    if (!(await ev(`!!document.querySelector('.ax') && !document.querySelector('#rightbar').classList.contains('hidden')`))) await ev(`(() => { const b = [...document.querySelectorAll('#toolstrip-right .ts-btn')].find((b) => b.title === 'API Explorer'); b?.click(); return 1; })()`);
    await waitFor(`!!document.querySelector('.ax-tabs')`, 5000);
    await click(`document.querySelector('.ax-tabs [data-v="history"]')`, 'History');
    const after = await ev(`({ n: document.querySelectorAll('.ax-hitem').length, label: document.querySelector('.ax-tabs [data-v="history"]').textContent.trim() })`);
    check('History is still there after a restart', back && after.n === 20 && after.label === 'History 20', after);
    await click(button('.ax-main button', 'Clear history'), 'Clear history');
    await sleep(500);
    const cleared = await ev(`({ n: document.querySelectorAll('.ax-hitem').length, empty: document.querySelector('.ax-empty')?.textContent || '', label: document.querySelector('.ax-tabs [data-v="history"]').textContent.trim() })`);
    check('Clear history empties it, on screen and in the settings', cleared.n === 0 && /Nothing here yet/.test(cleared.empty) && cleared.label === 'History' && (stored() || []).length === 0, { cleared, stored: stored() });

    // ---------------------------------------------------------------- 11. the examples, for real (online only)
    let online = false;
    try { online = (await fetch('https://catfact.ninja/fact', { signal: AbortSignal.timeout(6000) })).ok; } catch {}
    if (!online) t.skip('every example answers with JSON, and its Tuff runs', 'no internet here');
    else {
      await click(`document.querySelector('.ax-tabs [data-v="examples"]')`, 'Examples');
      const n = await ev(`document.querySelectorAll('.ax-item[data-ex]').length`);
      const results = [];
      for (let i = 0; i < n; i++) {
        await click(`document.querySelector('.ax-tabs [data-v="examples"]')`, 'Examples');
        const name = await ev(`document.querySelectorAll('.ax-item[data-ex]')[${i}].querySelector('b').textContent`);
        await click(`document.querySelectorAll('.ax-item[data-ex]')[${i}]`, name);
        await answered();
        const s = await status();
        const rows = await ev(`document.querySelectorAll('.ax-tree .ax-row').length`);
        results.push({ name, status: s?.text, rows, error: (await errorShown())?.title });
      }
      const bad = results.filter((r) => !/^2\d\d /.test(r.status || '') || r.rows < 2);
      check(`Every example (${results.length}) answers 2xx with JSON`, results.length >= 6 && bad.length === 0, results);
      // Two of them as whole programs, run with tap over the internet
      const runs = [];
      for (const [name, keys, want] of [['A cat fact', ['fact'], /^fact: .{10,}/], ['Weather in London', ['current', 'temperature_2m'], /^temperature_2m: -?\d+(\.\d+)?$/]]) {
        await click(`document.querySelector('.ax-tabs [data-v="examples"]')`, 'Examples');
        await click(`[...document.querySelectorAll('.ax-item[data-ex]')].find((e) => e.querySelector('b').textContent === ${JSON.stringify(name)})`, name);
        await answered();
        await pick(keys);
        await setMode(true);
        const g = await saveAndRun(await shownCode());
        runs.push({ name, ok: g.check === 'OK' && g.run.code === 0 && want.test(g.run.out), out: g.run.out, check: g.check });
      }
      check('"A cat fact" and "Weather in London" programs run with tap over the internet', runs.every((r) => r.ok), runs);
    }

    // ---------------------------------------------------------------- 12. every value of every answer, through the code writer
    // The panel's own code writer (the same file, loaded in Node) for every value in these answers:
    // each whole program passes --check, and running it says that value.
    const answers = [['/weather', WEATHER], ['/facts', FACTS], ['/people', PEOPLE], ['/odd', { ...ODD, big: ODD.big.slice(0, 3) }]];
    const shown = (v) => (v === null ? 'nil' : String(v));
    const jobs = [];
    const walk = (v, p, url) => {
      if (v !== null && typeof v === 'object') {
        if (Array.isArray(v)) v.forEach((x, i) => walk(x, [...p, { i }], url));
        else Object.entries(v).forEach(([k, x]) => walk(x, [...p, { k }], url));
      } else jobs.push({ url, path: p, value: v });
    };
    for (const [u, v] of answers) walk(v, [], u);
    const sweep = [];
    const one = async (j, n) => {
      const req = { method: 'GET', url: `${BASE}${j.url}`, headers: [] };
      const code = G.code({ req, kind: 'json', path: j.path, value: j.value, whole: true });
      const file = proj(`sweep_${n}.tuf`);
      fs.writeFileSync(file, code);
      const run = await runTuff(file);
      const line = run.out.split('\n').pop();
      sweep.push({ path: G.crumbs(j.path), ok: checkOk(file) === 'OK' && run.code === 0 && line.endsWith(`: ${shown(j.value)}`), out: run.out, code });
    };
    for (let i = 0; i < jobs.length; i += 6) await Promise.all(jobs.slice(i, i + 6).map((j, k) => one(j, i + k)));
    const sweepBad = sweep.filter((s) => !s.ok);
    check(`Whole programs for all ${sweep.length} values in four answers pass --check and say the right value`, sweep.length > 30 && sweepBad.length === 0, sweepBad.slice(0, 2));

    // Characters Tuff can't write, in a name, a JSON body, a text body or a header: every program still
    // passes --check (Tuff ends a line at U+0085, U+2028 and U+2029), and exact() says the code had to change them.
    const ch = (n) => String.fromCharCode(n);
    const get = { method: 'GET', url: `${BASE}/odd`, headers: [] };
    const odd2 = [
      { req: get, path: [{ k: `a${ch(0x2028)}b` }] },
      { req: get, path: [{ k: `a${ch(0x2029)}b` }] },
      { req: get, path: [{ k: `a${ch(0x85)}b` }] },
      { req: get, path: [{ k: `a${ch(1)}b` }] },
      { req: { method: 'POST', url: `${BASE}/echo`, headers: [], body: '{"v": "a\\u2028b"}', bodyType: 'json' }, path: [{ k: 'v' }] },
      { req: { method: 'POST', url: `${BASE}/echo`, headers: [['X-Test', `h${ch(0x2028)}v`]], body: `a${ch(0x85)}b`, bodyType: 'text' }, path: [{ k: 'body' }] },
    ].map((o, i) => {
      const opts = { ...o, kind: 'json', value: 1, whole: true };
      const file = proj(`hidden_${i}.tuf`);
      fs.writeFileSync(file, G.code(opts));
      return { i, check: checkOk(file), exact: G.exact(opts) };
    });
    const plainExact = G.exact({ req: get, kind: 'json', path: [{ k: 'post code' }], value: 1, whole: true });
    check('Hidden characters Tuff can\'t write: the code still passes --check, and exact() says it was changed', odd2.every((r) => r.check === 'OK' && !r.exact) && plainExact, { odd2, plainExact });
    const hiddenUrls = [ch(0x85), ch(1)].map((c) => G.fixUrl(`${BASE}/a${c}b`).error?.text || 'sent');
    check('An address with a hidden character in it isn\'t sent, and says why', hiddenUrls.every((x) => /hidden character/.test(x)) && G.fixUrl(`${BASE}/ab`).url === `${BASE}/ab`, hiddenUrls);
  } finally {
    t.info(`screenshots: ${shots.join(', ')}`);
    server.closeAllConnections?.();
    await new Promise((r) => server.close(r));
  }
};
