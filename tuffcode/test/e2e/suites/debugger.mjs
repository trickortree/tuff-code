// The Tuff Debugger (1.5.0), driven like a person would: a breakpoint from a click in the gutter, the Debug button,
// the paused line, the Variables panel and the call stack, F10, F11, Shift+F11 and F5, a value opened, another frame,
// stepping into the file it imports, pause on error, input() while debugging, Watch it run with Pause and Continue,
// the Run menu, and a plain Run closing the debug pane. The program runs with the Tuff runtime (packaged) or Python
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
  const ended = () => t.waitFor(`window.TuffDebug.state().state === 'ended'`, 20000);

  // ---- a breakpoint from the gutter, then Debug
  await open('debug.tuf');
  await clickGlyph(10);
  check('A click in the glyph margin puts a breakpoint (a red dot) on line 10', JSON.stringify(await ev('window.TuffDebug.breakpoints()')).includes('"lines":[10]')
    && await ev(`!!document.querySelector('.monaco-editor .dbg-bp:not(.hint)')`), await ev('window.TuffDebug.breakpoints()'));
  await t.shot('breakpoint.png');
  await clickSel('#btn-debug');
  check('Debug runs it and it stops at the breakpoint, inside add()', await pausedAt(10), await state());
  check('...the paused line is lit and the debug pane is open beside the Run output', await lit('paused') === 1
    && await ev(`!document.querySelector('#debug-pane').classList.contains('hidden')`), await lit('paused'));
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
    && await ev(`window.TuffIDE.activeFile().endsWith('money.tuf')`) && await lit('paused') === 1, await state());
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
    && await lit('error') === 1, await state());
  vars = await text('#debug-pane .dbg-sec.vars .dbg-list');
  check("...with the error in the pane, and half's names as they were", /Stopped by an error on line 3/.test(await text('#debug-pane .dbg-status')) && /x\s+4/.test(vars) && /y\s+8/.test(vars), vars);
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
  check('...and the Variables panel shows the answer as text', /name\s+"Sam"\s+text/.test(await text('#debug-pane .dbg-sec.vars .dbg-list')), await text('#debug-pane .dbg-sec.vars .dbg-list'));
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
};
