// The Tuff Debugger (1.5.0), driven like a person would: a breakpoint from a click in the gutter, the Debug button,
// the paused line, the Variables panel and the call stack, F10, F11, Shift+F11 and F5, a value opened, another frame,
// stepping into the file it imports, pause on error, input() while debugging, Watch it run with Pause and Continue
// (and the eye again once it has ended), the Run menu, and a plain Run closing the debug pane. Then a pause while
// Search Everywhere is open (the keyboard stays in it), F9 while Design Studio shows, Auto Code Sort keeping the
// breakpoints on their lines, and New Project while a program is paused. The program runs with the Tuff runtime (packaged) or Python
// + tuff.py (checkout); it's a console program, so no window opens.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'the debugger: breakpoints, stepping, Variables and Watch it run', timeout: 300000 };

const SHIFT = 8;
const MAIN = `import money.tuf
kind Pet:
    name = "?"
    hunger = 5
    func feed(amount):
        my.hunger -= amount
total = 0
rex = Pet("Rex")
func add(n):
    total += n
    return total
for i in range(1, 3):
    add(i)
rex:feed(2)
say money.with_tax(10)
say total
`;
const MONEY = 'rate = 0.2\n\nfunc with_tax(price):\n    extra = price * rate\n    return price + extra\n';
const ERROR = 'func half(x):\n    y = x * 2\n    return y + nope\nsay half(4)\n';
const ASK = 'name = input "Name? "\nsay "Hi " + name\nsize = len(name)\nsay size\n';
const COUNT = 'count = 3\nwhile count > 0:\n    say count\n    wait(0.2)\n    count -= 1\nsay "Liftoff!"\n';

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const file = (name) => path.join(ctx.root, name);
  for (const [name, code] of [['debug.tuf', MAIN], ['money.tuf', MONEY], ['oops.tuf', ERROR], ['ask.tuf', ASK], ['count.tuf', COUNT]]) fs.writeFileSync(file(name), code);
  const open = async (name) => {
    await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(file(name))}); return 1; })()`);
    await t.waitFor(`window.TuffIDE.activeFile()?.endsWith(${JSON.stringify(name)})`, 6000);
    await t.sleep(300);
  };
  const state = () => ev('window.TuffDebug.state()');
  const pausedAt = (line, ms = 20000) => t.waitFor(`(() => { const s = window.TuffDebug.state(); return s.state === 'paused' && s.line === ${line}; })()`, ms);
  const text = (sel) => ev(`document.querySelector(${JSON.stringify(sel)})?.innerText || ''`);
  const fkey = async (key, keyCode, mods = 0) => {
    await t.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', modifiers: mods, windowsVirtualKeyCode: keyCode, key, code: key });
    await t.send('Input.dispatchKeyEvent', { type: 'keyUp', modifiers: mods, windowsVirtualKeyCode: keyCode, key, code: key });
    await t.sleep(120);
  };
  const rect = (sel) => ev(`(() => { const r = document.querySelector(${JSON.stringify(sel)})?.getBoundingClientRect(); return r && r.width ? [r.left + r.width / 2, r.top + r.height / 2] : null; })()`);
  const clickSel = async (sel) => {
    const at = await rect(sel);
    if (!at) throw new Error(`Nothing to click: ${sel}`);
    await t.click(at[0], at[1]);
  };
  // The middle of a line's glyph margin (left of the line numbers), where a click adds or takes away a breakpoint.
  const glyph = (line) => ev(`(() => { const e = window.TuffIDE.editor(); e.revealLineInCenter(${line}); const p = e.getScrolledVisiblePosition({ lineNumber: ${line}, column: 1 });
    const r = e.getDomNode().getBoundingClientRect(); const l = e.getLayoutInfo(); return [r.left + l.glyphMarginLeft + l.glyphMarginWidth / 2, r.top + p.top + p.height / 2]; })()`);
  const clickGlyph = async (line) => {
    const [x, y] = await glyph(line);
    await t.move(x, y);
    await t.click(x, y);
    await t.sleep(200);
  };
  const lit = (kind) => ev(`document.querySelectorAll('.monaco-editor .dbg-line.${kind}').length`);
  // A line lit by a pause: the debugger marks it as the state changes, and the editor paints it on its next frame, so
  // on a slow machine (a CI Mac) a check can come in between. It gets a moment.
  const litSoon = (kind) => t.waitFor(`document.querySelectorAll('.monaco-editor .dbg-line.${kind}').length === 1`, 3000);
  const ended = () => t.waitFor(`window.TuffDebug.state().state === 'ended'`, 20000);

  // ---- a breakpoint from the gutter, then Debug
  await open('debug.tuf');
  await clickGlyph(10);
  check('A click in the glyph margin puts a breakpoint (a red dot) on line 10', JSON.stringify(await ev('window.TuffDebug.breakpoints()')).includes('"lines":[10]')
    && await ev(`!!document.querySelector('.monaco-editor .dbg-bp:not(.hint)')`), await ev('window.TuffDebug.breakpoints()'));
  await t.shot('breakpoint.png');
  await clickSel('#btn-debug');
  check('Debug runs it and it stops at the breakpoint, inside add()', await pausedAt(10), await state());
  // (once on the Windows CI machine the pane was still hidden here, with the line lit: it gets a moment, and says
  // how it was if it stays hidden)
  const paneOpen = await t.waitFor(`[...document.querySelectorAll('#debug-pane')].some((p) => !p.classList.contains('hidden'))`, 3000);
  check('...the paused line is lit and the debug pane is open beside the Run output', await litSoon('paused') && paneOpen,
    { lit: await lit('paused'), panes: await ev(`[...document.querySelectorAll('#debug-pane')].map((p) => p.className)`), state: await state() });
  const status = await text('#debug-pane .dbg-status');
  check('...it says where and why', /Stopped at a breakpoint on line 10 of debug\.tuf/.test(status), status);
  let vars = await text('#debug-pane .dbg-sec.vars .dbg-list');
  check("The Variables panel: add's own n, then debug.tuf's top level (total, rex), as say shows them", /In add\(\)/.test(vars) && /n\s+1\s+number/.test(vars)
    && /debug\.tuf's top level/.test(vars) && /total\s+0/.test(vars) && /rex\s+Pet\(name: "Rex", hunger: 5\)/.test(vars), vars);
  const stack = await text('#debug-pane .dbg-sec.stack .dbg-list');
  check('The call stack: add() on line 10, called from the top level on line 13', /add\(\)\s+debug\.tuf:10/.test(stack) && /top level\s+debug\.tuf:13/.test(stack), stack);
  await t.shot('paused.png');

  // ---- stepping with the keys
  await fkey('F10', 121);
  check('F10 (Step Over) goes to the next line', await pausedAt(11), await state());
  await fkey('F11', 122, SHIFT);
  check("Shift+F11 (Step Out) finishes add() and stops on the for line as the loop goes round", await pausedAt(12), await state());
  vars = await text('#debug-pane .dbg-sec.vars .dbg-list');
  check('...where total is 1 and i is 2', /total\s+1/.test(vars) && /i\s+2/.test(vars), vars);
  await ev(`[...document.querySelectorAll('#debug-pane .dbg-var')].find((r) => r.querySelector('.nm')?.textContent === 'rex')?.click()`);
  check('Clicking rex opens it: its fields', await t.waitFor(`/hunger\\s+5/.test(document.querySelector('#debug-pane .dbg-sec.vars .dbg-list').innerText)
    && !!document.querySelector('#debug-pane .dbg-var[style*="--d:1"]')`, 6000), await text('#debug-pane .dbg-sec.vars .dbg-list'));
  await fkey('F11', 122);
  check('F11 (Step Into) goes on to the line that calls add()', await pausedAt(13), await state());
  await fkey('F11', 122);
  check('...and F11 again goes into it', await pausedAt(10), await state());
  await ev(`[...document.querySelectorAll('#debug-pane .dbg-frame')].find((f) => /top level/.test(f.innerText))?.click()`);
  check('Clicking the top level in the call stack lights its line (13) and shows its names', await t.waitFor(`document.querySelectorAll('.monaco-editor .dbg-line.frame').length === 1
    && !/In add\\(\\)/.test(document.querySelector('#debug-pane .dbg-sec.vars .dbg-list').innerText)`, 6000), await text('#debug-pane .dbg-sec.vars .dbg-list'));
  await t.shot('frame.png');
  await clickGlyph(10);
  check('A click on the dot takes the breakpoint away', JSON.stringify(await ev('window.TuffDebug.breakpoints()')) === '[]', await ev('window.TuffDebug.breakpoints()'));
  await fkey('F5', 116);
  check('F5 (Continue) runs it to the end', await ended(), await state());
  check('...with its output in the Run window as usual, and the pane says it has finished', /12\s+6/.test(await text('#run-output'))
    && /has finished/.test(await text('#debug-pane .dbg-status')), [await text('#run-output'), await text('#debug-pane .dbg-status')]);

  // ---- into the file it imports
  await open('debug.tuf');
  await ev(`(() => { const e = window.TuffIDE.editor(); e.setPosition({ lineNumber: 15, column: 1 }); e.focus(); })()`);
  await fkey('F9', 120);
  check('F9 puts a breakpoint on the cursor\'s line', JSON.stringify(await ev('window.TuffDebug.breakpoints()')).includes('"lines":[15]'), await ev('window.TuffDebug.breakpoints()'));
  await clickSel('#btn-debug');
  check('It stops on line 15', await pausedAt(15), await state());
  await fkey('F11', 122);
  check('F11 goes into money.with_tax: money.tuf opens with its line lit', await t.waitFor(`(() => { const s = window.TuffDebug.state(); return s.state === 'paused' && /money\\.tuf$/.test(s.file) && s.line === 4; })()`, 10000)
    && await ev(`window.TuffIDE.activeFile().endsWith('money.tuf')`) && await litSoon('paused'), { state: await state(), lit: await lit('paused') });
  vars = await text('#debug-pane .dbg-sec.vars .dbg-list');
  check("...and the names are with_tax's, then money.tuf's own top level", /In with_tax\(\)/.test(vars) && /price\s+10/.test(vars) && /money\.tuf's top level/.test(vars)
    && /rate\s+0\.2/.test(vars) && !/total/.test(vars), vars);
  await t.shot('money.png');
  await fkey('F11', 122, SHIFT);
  check('Shift+F11 comes back out to debug.tuf, on the next line', await t.waitFor(`(() => { const s = window.TuffDebug.state(); return s.state === 'paused' && /debug\\.tuf$/.test(s.file) && s.line === 16; })()`, 10000), await state());
  await open('debug.tuf');
  await ev(`(() => { const e = window.TuffIDE.editor(); e.setPosition({ lineNumber: 15, column: 1 }); e.focus(); })()`);
  await fkey('F9', 120);
  await fkey('F5', 116);
  await ended();

  // ---- pause on error
  await open('oops.tuf');
  await clickSel('#btn-debug');
  check('An error pauses on its line before the program ends', await t.waitFor(`(() => { const s = window.TuffDebug.state(); return s.state === 'paused' && s.reason === 'error' && s.line === 3; })()`, 20000)
    && await litSoon('error'), { state: await state(), lit: await lit('error') });
  vars = await text('#debug-pane .dbg-sec.vars .dbg-list');
  check("...with the error in the pane, and half's names as they were", /Stopped by an error on line 3/.test(await text('#debug-pane .dbg-status')) && /x\s+4/.test(vars) && /y\s+8/.test(vars), vars);
  check('...and it says Continue ends the program', /Continue ends the program/.test(await text('#debug-pane .dbg-status')), await text('#debug-pane .dbg-status'));
  await t.shot('error.png');
  await fkey('F5', 116);
  check('Continue ends it with the error', await ended() && /Tuff error on line 3/.test(await text('#run-output')), await text('#run-output'));

  // ---- input() while debugging
  await open('ask.tuf');
  await ev(`(() => { const e = window.TuffIDE.editor(); e.setPosition({ lineNumber: 3, column: 1 }); e.focus(); })()`);
  await fkey('F9', 120);
  await clickSel('#btn-debug');
  await t.waitFor(`!!document.querySelector('#run-input') && /Name\\?/.test(document.querySelector('#run-output').innerText)`, 15000);
  await clickSel('#run-input');
  await t.type('Sam\n', 40);
  check('input() is answered in the Run window as usual, then it stops at the breakpoint', await pausedAt(3), await state());
  check('...and the Variables panel shows the answer as text, as say shows it', /name\s+Sam\s+text/.test(await text('#debug-pane .dbg-sec.vars .dbg-list')), await text('#debug-pane .dbg-sec.vars .dbg-list'));
  await fkey('F9', 120); // (the cursor is on line 3 again: the breakpoint goes)
  await fkey('F5', 116);
  check('...then it goes on', await ended() && /Hi Sam/.test(await text('#run-output')), await text('#run-output'));

  // ---- Watch it run
  await open('count.tuf');
  await ev(`window.TuffIDE.runCommand('watchRun')`);
  check('Watch It Run shows each line as it runs', await t.waitFor(`document.querySelectorAll('.monaco-editor .dbg-line.watch').length === 1`, 20000)
    && /Watching it run/.test(await text('#debug-pane .dbg-status')), await text('#debug-pane .dbg-status'));
  await t.shot('watch.png');
  const seen = new Set();
  for (let i = 0; i < 20; i++) {
    const s = await state();
    if (s.line) seen.add(s.line);
    await t.sleep(150);
  }
  check('...line after line, the while line too', seen.size >= 3 && seen.has(2), [...seen]);
  await clickSel('#debug-pane .dbg-b[data-act="pause"]');
  check('Pause stops it where it is', await t.waitFor(`window.TuffDebug.state().state === 'paused' && window.TuffDebug.state().reason === 'pause'`, 10000), await state());
  await ev(`(() => { const s = document.querySelector('#debug-pane .dbg-speed input'); s.value = '10'; s.dispatchEvent(new Event('input')); })()`);
  await clickSel('#debug-pane .dbg-b[data-act="continue"]');
  check('Continue goes on watching (at the new speed) to the end', await ended() && /Liftoff!/.test(await text('#run-output')), await text('#run-output'));
  const eye = '#debug-pane .dbg-b[data-act="watch"]';
  check('...then the eye goes out', await ev(`!document.querySelector(${JSON.stringify(eye)}).classList.contains('on')`), await state());
  await clickSel(eye);
  check('...and the eye watches it run again', await t.waitFor(`window.TuffDebug.state().watching && document.querySelectorAll('.monaco-editor .dbg-line.watch').length === 1`, 20000), await state());
  await clickSel('#debug-pane .dbg-b[data-act="stop"]');
  await ended();

  // ---- the Run menu, and a plain run
  await ev(`[...document.querySelectorAll('#menubar .menu-root > button')].find((b) => b.textContent === 'Run').click()`);
  await t.sleep(300);
  const menu = await ev(`[...document.querySelectorAll('.menu-root.open .dropdown .mi')].map((m) => m.innerText.replace(/\\s+/g, ' ').trim())`);
  check('The Run menu has Debug, Watch It Run, the steps, Pause and Toggle Breakpoint', ['Debug Current File Shift+F9', 'Watch It Run', 'Continue F5', 'Step Over F10',
    'Step Into F11', 'Step Out Shift+F11', 'Pause the Program', 'Toggle Breakpoint F9'].every((m) => menu.includes(m)), menu);
  await t.shot('runmenu.png', { x: 0, y: 0, width: 700, height: 520 });
  await t.key('Escape');
  await clickSel('#btn-run');
  check('A plain Run closes the debug pane', await t.waitFor(`document.querySelector('#debug-pane').classList.contains('hidden')`, 5000), null);
  await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running')`, 20000);

  // ---- a pause while a dialog is open (Search Everywhere): the line is lit, and the keyboard stays in the dialog
  const SLOW = 'say "a"\nwait(2)\nsay "b"\nsay "c"\n';
  fs.writeFileSync(file('slow.tuf'), SLOW);
  const dot = (name, line) => ev(`window.TuffDebug.toggle(${JSON.stringify(file(name))}, ${line})`);
  await open('slow.tuf');
  await dot('slow.tuf', 3);
  await clickSel('#btn-debug');
  await t.waitFor(`window.TuffDebug.state().state === 'running'`, 15000);
  await ev(`window.TuffIDE.runCommand('searchEverywhere')`);
  await t.waitFor(`document.activeElement?.id === 'se-input'`, 3000);
  await t.type('ab', 40);
  check('A breakpoint reached while Search Everywhere is open lights its line, and the keyboard stays in the search box', await pausedAt(3) && await litSoon('paused')
    && await ev(`document.activeElement?.id === 'se-input'`), { state: await state(), lit: await lit('paused') });
  await t.type('xy', 40);
  const searched = await ev(`document.querySelector('#se-input').value`);
  check('...what is typed then goes into the box, not the code', searched === 'abxy' && (await t.code()).replace(/\r\n/g, '\n') === SLOW, [searched, await t.code()]);
  await t.key('Escape');
  await fkey('F10', 121);
  check('...Esc closes it, and F10 steps on in the code', await ev(`document.querySelector('#search-everywhere').classList.contains('hidden')`) && await pausedAt(4), await state());
  await dot('slow.tuf', 3);
  await fkey('F5', 116);
  await ended();

  // ---- F9 while Design Studio shows (the code editor is hidden): only a toast
  fs.writeFileSync(file('shop.tuf'), 'import tgui\n\nwin = tgui.window("Shop", 420, 360)\ntitle = win:heading("Hello")\nwin:show()\n');
  await open('shop.tuf');
  await ev(`window.TuffIDE.editor().setPosition({ lineNumber: 4, column: 1 })`);
  await ev(`window.TuffIDE.runCommand('studio')`);
  await t.waitFor(`window.TuffIDE.studioVisible()`, 6000);
  const dots = JSON.stringify(await ev('window.TuffDebug.breakpoints()'));
  await fkey('F9', 120);
  check('F9 while Design Studio shows puts no breakpoint in the hidden code, and says to show the code', JSON.stringify(await ev('window.TuffDebug.breakpoints()')) === dots
    && await t.waitFor(`[...document.querySelectorAll('#toasts .toast')].some((x) => /Show the code/.test(x.textContent))`, 3000), await ev('window.TuffDebug.breakpoints()'));

  // ---- Auto Code Sort puts each breakpoint back on its own line, and one Ctrl+Z takes the sort back
  const MESSY = 'func greet(who):\n  say "hi " + who\nx=1\ngreet("Sam")\nsay x\n';
  fs.writeFileSync(file('messy.tuf'), MESSY);
  await open('messy.tuf');
  for (const n of [2, 3, 5]) await dot('messy.tuf', n);
  await ev(`(() => { const e = window.TuffIDE.editor(); e.setPosition({ lineNumber: 5, column: 1 }); e.focus(); })()`);
  await ev(`window.TuffIDE.runCommand('autoSort')`);
  await t.waitFor(`window.TuffIDE.editor().getModel().getValue().includes('# ── Functions')`, 6000);
  const sorted = await ev(`(() => { const m = window.TuffIDE.editor().getModel();
    return window.TuffDebug.breakpoints().filter((b) => /messy\\.tuf$/i.test(b.path)).flatMap((b) => b.lines).map((n) => m.getLineContent(n).trim()); })()`);
  check('Auto Code Sort moving a function down (and x=1 to x = 1): each breakpoint goes with its line', JSON.stringify(sorted) === JSON.stringify(['x = 1', 'say x', 'say "hi " + who']), sorted);
  await t.key('z', ctx.platform === 'darwin' ? 4 : 2);
  await t.sleep(300);
  const back = await ev(`window.TuffDebug.breakpoints().filter((b) => /messy\\.tuf$/i.test(b.path)).flatMap((b) => b.lines)`);
  check('...and one Ctrl+Z takes the sort back, with the breakpoints on their lines again', (await t.code()).replace(/\r\n/g, '\n') === MESSY
    && JSON.stringify(back) === '[2,3,5]', [await t.code(), back]);
  for (const b of await ev('window.TuffDebug.breakpoints()')) for (const n of b.lines) await ev(`window.TuffDebug.toggle(${JSON.stringify(b.path)}, ${n})`);

  // ---- New Project while a program is paused: it stops, the old project's Design Studio tab goes, and Rerun runs the
  // new project's main.tuf (the gallery makes it in a scratch folder, as newproject.mjs does)
  await open('slow.tuf');
  await dot('slow.tuf', 3);
  await clickSel('#btn-debug');
  check('(slow.tuf stops at its breakpoint, with the Design Studio tab still open)', await pausedAt(3) && await ev(`!!document.querySelector('#tabs .studio-tab')`), await state());
  const projects = path.join(path.dirname(ctx.root), 'projects');
  fs.mkdirSync(projects, { recursive: true });
  await ev(`window.TuffIDE.saveSettings({ newProjectFolder: ${JSON.stringify(projects)} }); 1`);
  await ev(`window.TuffNewProject.open(); 1`);
  await t.waitFor(`!!document.querySelector('#new-project .np-card.sel') && !document.querySelector('#np-create').disabled`, 10000);
  await t.key('Enter');
  const made = await t.waitFor(`!document.querySelector('#new-project') && window.TuffIDE.root().startsWith(${JSON.stringify(projects)})`, 15000);
  check('New Project while it is paused: the program stops, and the pane says so', made && (await state()).state === 'ended'
    && /The program was stopped/.test(await text('#debug-pane .dbg-status')), [await state(), await text('#debug-pane .dbg-status')]);
  const tabs = await ev(`[...document.querySelectorAll('#tabs .tab')].map((x) => x.title)`);
  check("...the old project's Design Studio tab goes, and only the new project's main.tuf is open", tabs.length === 1 && tabs[0].startsWith(projects) && /main\.tuf$/.test(tabs[0]), tabs);
  await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running')`, 10000);
  await fkey('F5', 116, 2); // Ctrl+F5: Rerun
  check("...and Rerun (Ctrl+F5) runs the new project's main.tuf, not slow.tuf", await t.waitFor(`document.querySelector('#run-tab-name').textContent === 'main.tuf'`, 6000),
    await text('#run-tab-name'));
  await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running')`, 20000);
};
