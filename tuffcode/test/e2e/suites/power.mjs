// Editor power tools: live checking, go to definition, find all uses, rename, go to symbol, parameter hints,
// colour swatches, Find in Files with Replace all, reopen closed tab, zen mode and the Go menu.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'editor power tools', platforms: ['win32'], why: 'Ctrl and F-key shortcuts, Cmd on a Mac' };

const NL = '\n';

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const P = (f) => path.join(ctx.root, f);
  const waitFor = (js, ms = 8000) => t.waitFor(js, ms, 120);
  const open = (f) => ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(P(f))}); return 1; })()`);
  const setCode = (code) => ev(`monaco.editor.getEditors()[0].getModel().setValue(${JSON.stringify(code)})`);
  const code = async () => (await ev(`monaco.editor.getEditors()[0].getModel().getValue()`)).replace(/\r\n/g, NL);
  const cursor = (line, col) => ev(`(() => { const e = monaco.editor.getEditors()[0]; e.setPosition({ lineNumber: ${line}, column: ${col} }); e.focus(); })()`);
  const pos = () => ev(`(() => { const p = monaco.editor.getEditors()[0].getPosition(); return [p.lineNumber, p.column]; })()`);
  const trigger = (id) => ev(`monaco.editor.getEditors()[0].trigger('test', '${id}', null)`);

  await ev(`window.TuffPluginHost?.closePanel()`);
  // Keep the source in a constant: reading power.tuf back later races the IDE's 1.5 s autosave of the step-1 text.
  const POWER = ['say greet("Sam")', 'score = 1', 'say "score is " + text(score)', 'score += 2', '', 'func greet(name):', '    "Hi " + name', ''].join(NL);
  fs.writeFileSync(P('power.tuf'), POWER);
  await open('power.tuf');
  await t.sleep(300);

  // 1. live checking
  const ok1 = await waitFor(`document.querySelector('#sb-problems').className === 'ok'`);
  check('Live check: a good file shows "No mistakes"', ok1, await ev(`document.querySelector('#sb-problems').outerHTML`));
  await setCode(['say "a"', 'if x is 1', '    say 2', ''].join(NL));
  const bad = await waitFor(`monaco.editor.getModelMarkers({ owner: 'tuff-live' }).length === 1`, 6000);
  const mk = await ev(`monaco.editor.getModelMarkers({ owner: 'tuff-live' }).map(m => [m.startLineNumber, m.message])`);
  const sb = await ev(`document.querySelector('#sb-problems').textContent`);
  check('Live check: a mistake gets a red squiggle and shows in the status bar (no running needed)', bad && mk[0][0] === 2 && /':' or 'then'/.test(mk[0][1]) && /^Line 2:/.test(sb), { mk, sb });
  await t.shot('w_live.png');
  // x has to be set: since round 3 the live check also flags names that are never set.
  await setCode(['x = 1', 'if x is 1:', '    say 2', ''].join(NL));
  const fixed = await waitFor(`monaco.editor.getModelMarkers({ owner: 'tuff-live' }).length === 0 && document.querySelector('#sb-problems').className === 'ok'`, 6000);
  check('Live check: fixing it clears the mistake', fixed, await ev(`monaco.editor.getModelMarkers({ owner: 'tuff-live' }).length`));

  // 2. go to definition (F12)
  await setCode(POWER);
  await t.sleep(200);
  await cursor(1, 7);
  await t.key('F12');
  await t.sleep(500);
  const p2 = await pos();
  check('F12 on greet jumps to func greet', p2[0] === 6, p2);

  // 3. find all uses (Shift+F12 peek)
  await cursor(2, 2);
  await trigger('editor.action.goToReferences');
  const peek = await waitFor(`!!document.querySelector('.peekview-widget')`, 4000);
  const refs = await ev(`document.querySelectorAll('.peekview-widget .monaco-list-row').length`);
  check('Find all uses shows a peek list (score is used 3 times)', peek && refs >= 3, { peek, refs });
  await t.key('Escape');
  await t.sleep(200);

  // 4. rename everywhere (F2) leaves strings alone
  await cursor(2, 2);
  await trigger('editor.action.rename');
  const box = await waitFor(`!!document.querySelector('.rename-box input, .rename-input')`, 4000);
  await ev(`(() => { const i = document.querySelector('.rename-box input, .rename-input'); i.value = 'points'; i.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  await t.key('Enter');
  await t.sleep(700);
  const c4 = await code();
  check('Rename: score -> points everywhere, but not inside "score is "', box && /points = 1/.test(c4) && /text\(points\)/.test(c4) && /points \+= 2/.test(c4) && /"score is "/.test(c4) && !/\bscore\b(?!")/.test(c4.replace(/"score is "/, '')), c4);

  // 5. go to symbol
  await cursor(1, 1);
  await trigger('editor.action.quickOutline');
  await waitFor(`!!document.querySelector('.quick-input-widget .monaco-list-row')`, 4000);
  const syms = await ev(`[...document.querySelectorAll('.quick-input-widget .monaco-list-row')].map(r => r.getAttribute('aria-label') || r.textContent)`);
  check('Go to Symbol lists functions and variables', syms.some((s) => /greet/.test(s)) && syms.some((s) => /points/.test(s)), syms);
  await t.key('Escape');

  // 6. parameter hints
  await setCode(NL);
  await cursor(1, 1);
  await t.type('round(', 70);
  const hint = await waitFor(`!!document.querySelector('.parameter-hints-widget.visible')`, 4000);
  const label1 = await ev(`document.querySelector('.parameter-hints-widget .signature')?.textContent`);
  await t.type('3, ', 70);
  await t.sleep(400);
  const active = await ev(`document.querySelector('.parameter-hints-widget .parameter.active')?.textContent`);
  check('Parameter hints: round( shows round(number, digits) and moves to digits after a comma', hint && /round\(number, digits\)/.test(label1 || '') && active === 'digits', { hint, label1, active });
  await t.key('Escape');

  // 7. colour swatches
  await setCode(['mention mtgui', 'app = mtgui.window("x")', 'app:accent "#ff8800"', ''].join(NL));
  const sw = await waitFor(`!!document.querySelector('.colorpicker-color-decoration')`, 5000);
  check('Hex colors get a color swatch', sw, null);
  await t.shot('w_color.png', { x: 300, y: 80, width: 700, height: 160 });

  // 8. find in files + replace all
  const RUN = Date.now().toString(36);
  const f1 = `ff1_${RUN}.tuf`, f2 = `ff2_${RUN}.txt`;
  fs.writeFileSync(P(f1), ['say "XYZ one"', 'say "xyz two"', ''].join(NL));
  fs.writeFileSync(P(f2), ['XYZ in text', ''].join(NL));
  await open(f1);
  await t.key('F', 10);
  await t.sleep(300);
  const shown = await ev(`!document.querySelector('#view-find').classList.contains('hidden') && document.activeElement === document.querySelector('#ff-q')`);
  await ev(`(() => { const i = document.querySelector('#ff-q'); i.value = 'XYZ'; i.dispatchEvent(new Event('input')); })()`);
  await waitFor(`/match/.test(document.querySelector('#ff-sum').textContent)`, 6000);
  const counts = () => ev(`Object.fromEntries([...document.querySelectorAll('#ff-results .ff-file')].map(f => [f.querySelector('.nm').textContent, +f.querySelector('.n').textContent]))`);
  const sum1 = await counts();
  await ev(`document.querySelector('#ff-case').click()`);
  await waitFor(`[...document.querySelectorAll('#ff-results .ff-file')].some(f => f.querySelector('.nm').textContent === ${JSON.stringify(f1)} && f.querySelector('.n').textContent === '1')`, 6000);
  const sum2 = await counts();
  check('Find in Files (Ctrl+Shift+F) finds matches across files; Aa makes it case-sensitive', shown && sum1[f1] === 2 && sum1[f2] === 1 && sum2[f1] === 1 && sum2[f2] === 1, { shown, sum1, sum2 });
  await ev(`document.querySelector('.ff-hit').click()`);
  await ev(`(() => { const i = document.querySelector('#ff-r'); i.value = 'ABC'; })()`);
  await ev(`document.querySelector('#ff-replace').click()`);
  await t.sleep(300);
  await ev(`document.querySelector('#modal-ok').click()`);
  await t.sleep(900);
  const d1 = fs.readFileSync(P(f1), 'utf8');
  const d2 = fs.readFileSync(P(f2), 'utf8');
  check('Replace all changes open and closed files (case-sensitive kept "xyz two")', /ABC one/.test(d1) && /xyz two/.test(d1) && /ABC in text/.test(d2), { d1, d2 });
  await t.shot('w_find.png');
  await ev(`document.querySelector('#ff-case').click()`);

  // 9. reopen closed tab
  await open('notes.tuf');
  await t.sleep(200);
  await t.key('F4', 2);
  await t.sleep(300);
  const gone = await ev(`![...document.querySelectorAll('.tab')].some(x => /notes\\.tuf/.test(x.textContent))`);
  await t.key('T', 10);
  await t.sleep(500);
  const back = await ev(`[...document.querySelectorAll('.tab')].some(x => /notes\\.tuf/.test(x.textContent))`);
  check('Ctrl+Shift+T reopens the tab you just closed', gone && back, { gone, back });

  // 10. zen mode
  await t.key('Z', 3);
  await t.sleep(300);
  const zenOn = await ev(`getComputedStyle(document.querySelector('#toolstrip')).display === 'none' && getComputedStyle(document.querySelector('#statusbar')).display === 'none'`);
  await t.shot('w_zen.png');
  await t.key('Z', 3);
  await t.sleep(300);
  const zenOff = await ev(`getComputedStyle(document.querySelector('#toolstrip')).display !== 'none'`);
  check('Zen mode (Ctrl+Alt+Z) hides the side bars and comes back', zenOn && zenOff, { zenOn, zenOff });

  // 11. menus have the new commands
  const goMenu = await ev(`(() => { const b = [...document.querySelectorAll('.menu-root > button')].find(x => x.textContent === 'Go'); b.click(); const items = [...document.querySelectorAll('.menu-root.open .mi')].map(m => m.innerText.split(String.fromCharCode(10))[0]); b.click(); return items; })()`);
  check('A new Go menu lists the navigation commands', ['Go to Function or Widget…', 'Go to Definition', 'Find All Uses', 'Reopen Closed Tab'].every((x) => goMenu.includes(x)), goMenu);

  // 12. Checks that start together (several tabs at startup, Auto code sort's before/after) each check their own
  // code. They used to share a temp file named by the millisecond, so one could get another's mistakes.
  const together = await ev(`(async () => {
    const good = 'name = "Sam"\\nsay "Hi " + name\\n', bad = 'say "Hi\\n';
    const rs = await Promise.all([good, bad, good, bad, good, bad].map((c) => window.tuff.checkSource(c)));
    return rs.map((r) => r.ok);
  })()`);
  check('Checks started at the same moment each get their own answer (good, bad, good, bad, …)', JSON.stringify(together) === JSON.stringify([true, false, true, false, true, false]), together);
};
