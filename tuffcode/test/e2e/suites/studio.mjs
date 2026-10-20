// Design Studio: drag tiles and widgets, edit in place, duplicate and delete, events, wrap in a card,
// rename, undo, reorder layers, and make a new file from a template. The result must still be valid Tuff.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'Design Studio' };

export default async (t, ctx) => {
  const check = t.check;
  const P = (f) => path.join(ctx.root, f);
  const DEMO = fs.readFileSync(path.join(ctx.fixtures, 'project', 'demo.tuf'), 'utf8');
  const code = async () => (await t.eval(`window.__demo.getValue()`)).replace(/\r\n/g, '\n');
  const lines = async () => (await code()).split('\n');
  const center = (js) => t.eval(`(() => { const el = (${js}); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, top: r.top, bottom: r.bottom, left: r.left, right: r.right }; })()`);
  const drag = async (a, b) => {
    await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: a.x, y: a.y });
    await t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: a.x, y: a.y, button: 'left', buttons: 1, clickCount: 1 });
    const steps = 12;
    for (let i = 1; i <= steps; i++) {
      await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: a.x + (b.x - a.x) * i / steps, y: a.y + (b.y - a.y) * i / steps, button: 'left', buttons: 1 });
      await t.sleep(25);
    }
    await t.sleep(120);
    await t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: b.x, y: b.y, button: 'left', buttons: 0, clickCount: 1 });
    await t.sleep(500);
  };
  const node = (pred) => `[...document.querySelectorAll('#sd-stage .pv-node')].find(n => ${pred})`;
  const tile = (kind) => `document.querySelector('.sd-tile[data-kind="${kind}"]')`;
  const select = async (pred) => { const c = await center(node(pred)); await t.click(c.x, c.y); await t.sleep(400); };

  // a fresh copy of the demo file in the editor model
  const demo = JSON.stringify(P('demo.tuf'));
  await t.eval(`(async () => { await window.TuffIDE.openFile(${demo}); return 1; })()`);
  await t.eval(`(async () => { window.__demo = await window.TuffIDE.getModel(${demo}); window.__demo.setValue(${JSON.stringify(DEMO)}); return 1; })()`);
  await t.eval(`(async () => { await window.TuffIDE.openStudio(${demo}); return 1; })()`);
  await t.sleep(1200);
  await t.eval(`document.querySelector('.sd-tabs [data-tab="add"]').click()`);
  await t.sleep(200);

  // 1. drag a Button tile in between the name box and the dropdown
  {
    const from = await center(tile('button'));
    const dd = await center(node(`n.classList.contains('k-dropdown')`));
    await drag(from, { x: dd.x, y: dd.top + 4 });
    const l = await lines();
    const i = l.findIndex((x) => x.startsWith('name = app:input'));
    check('drag Button tile in between name box and dropdown', /^button\d* = app:button "Click me"$/.test(l[i + 1]) && l[i + 2].startsWith('size = app:dropdown'), l.slice(i, i + 3));
    check('new button is selected', (await t.eval(`document.querySelector('.in-id b').textContent`)) === 'Button', null);
  }

  // 2. drag the Clear button out of the row to below the status text
  {
    const from = await center(node(`n.classList.contains('k-button') && n.textContent === 'Clear'`));
    const st = await center(node(`n.classList.contains('k-text')`));
    await drag(from, { x: st.x, y: st.bottom + 6 });
    const l = await lines();
    check('drag Clear out of the row to the end of the window', l.includes('app:button("Clear", clear, "ghost")') && !l.includes('row:button("Clear", clear, "ghost")') && l.indexOf('app:button("Clear", clear, "ghost")') > l.indexOf('status = app:text ""'), l.slice(10, 20));
  }

  // 3. double-click the heading and type a new title
  {
    const h = await center(`document.querySelector('#sd-stage .pv-h')`);
    await t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: h.x, y: h.y, button: 'left', clickCount: 1 });
    await t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: h.x, y: h.y, button: 'left', clickCount: 1 });
    await t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: h.x, y: h.y, button: 'left', clickCount: 2 });
    await t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: h.x, y: h.y, button: 'left', clickCount: 2 });
    await t.sleep(300);
    const editing = await t.eval(`!!document.querySelector('#sd-stage .editing')`);
    await t.send('Input.insertText', { text: 'Pizza time' });
    await t.key('Enter');
    await t.sleep(500);
    check('double-click heading to edit it in place', editing && (await lines()).includes('app:heading "Pizza time"'), { editing, l: (await lines()).slice(3, 5) });
  }

  // 4. Ctrl+D duplicates the selected Order button, Delete removes the copy
  {
    await select(`n.classList.contains('k-button') && n.textContent === 'Order'`);
    await t.key('D', 2);
    await t.sleep(500);
    let c = await code();
    check('Ctrl+D duplicates the selected widget', (c.match(/:button\("Order", order, "primary"\)/g) || []).length === 2, c);
    await t.key('Delete');
    await t.sleep(500);
    c = await code();
    check('Delete removes the selected widget', (c.match(/:button\("Order", order, "primary"\)/g) || []).length === 1, c);
  }

  // 5. events: give the name box a "when the text changes" function
  {
    await select(`n.classList.contains('k-input')`);
    const ok = await t.eval(`(() => { const s = [...document.querySelectorAll('#sd-props .pf')].find(f => /text changes/.test(f.textContent))?.querySelector('select'); if (!s) return false; s.value = '+new'; s.dispatchEvent(new Event('change')); return true; })()`);
    await t.sleep(600);
    const c = await code();
    check('Events: "+ New function" wires name:change and writes the function', ok && /\nname:change name_changed\n/.test(c) && /func name_changed\(\):\n    say name:value/.test(c), c.slice(-300));
  }

  // 6. wrap the slider in a card
  {
    await select(`n.classList.contains('k-slider')`);
    await t.eval(`[...document.querySelectorAll('#sd-actions button')].find(b => b.textContent.includes('Wrap in card')).click()`);
    await t.sleep(500);
    const l = await lines();
    const i = l.findIndex((x) => /^card\d+ = app:card$/.test(x));
    check('Wrap in card puts the slider inside a new card', i > 0 && /^spice = card\d+:slider\(0, 10, 3\)$/.test(l[i + 1]), l.slice(i - 1, i + 3));
  }

  // 7. rename the slider from the inspector
  {
    await select(`n.classList.contains('k-slider')`);
    await t.eval(`(() => { const i = document.querySelector('#in-name'); i.focus(); i.value = 'heat'; i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); })()`);
    await t.sleep(500);
    const c = await code();
    check('renaming spice -> heat updates the code', /\nheat = card\d+:slider/.test(c) && !/\bspice\b/.test(c), c);
  }

  // 8. undo brings the old name back
  {
    await t.eval(`document.querySelector('#sd-canvas').focus()`);
    await t.key('Z', 2);
    await t.sleep(500);
    check('Ctrl+Z undoes the rename', /\bspice = card\d+:slider/.test(await code()), (await code()).slice(0, 600));
    await t.key('Y', 2);
    await t.sleep(400);
  }

  // 9. layers panel: drag the dropdown layer above the name box layer
  {
    await t.eval(`document.querySelector('.sd-tabs [data-tab="layers"]').click()`);
    await t.sleep(300);
    const from = await center(`[...document.querySelectorAll('.sd-layer')].find(r => r.querySelector('.lb').textContent === 'Dropdown')`);
    const to = await center(`[...document.querySelectorAll('.sd-layer')].find(r => r.querySelector('.lb').textContent === 'Text box')`);
    await drag(from, { x: to.x, y: to.top + 3 });
    const l = await lines();
    check('drag a layer to reorder', l.findIndex((x) => x.startsWith('size = app:dropdown')) < l.findIndex((x) => x.startsWith('name = app:input')), l.slice(0, 12));
    await t.shot('studio_layers.png');
    await t.eval(`document.querySelector('.sd-tabs [data-tab="add"]').click()`);
  }

  // 10. the result is still valid Tuff
  {
    fs.writeFileSync(P('demo_after.tuf'), await code());
    const out = ctx.tuffCheck(P('demo_after.tuf'));
    check('edited file passes tuff --check', /OK/.test(out), out);
  }
  await t.shot('studio_final.png');

  // 11. templates: open the gallery and make a new file from one (1.0.3 has 8; later versions may add more)
  {
    await t.eval(`document.querySelector('#sd-templates').click()`);
    await t.sleep(700);
    const n = await t.eval(`document.querySelectorAll('.sd-tcard').length`);
    await t.shot('studio_templates.png');
    fs.rmSync(P('counter.tuf'), { force: true });
    await t.eval(`[...document.querySelectorAll('.sd-tcard')].find(c => c.querySelector('b').textContent === 'Counter').querySelector('[data-a="new"]').click()`);
    await t.sleep(1500);
    const made = fs.existsSync(P('counter.tuf'));
    const shown = await t.eval(`document.querySelector('#sd-file').value`);
    check('Templates: at least 8 cards, "New file" makes counter.tuf and opens it', n >= 8 && made && /counter\.tuf$/.test(shown), { n, made, shown });
    await t.shot('studio_counter.png');
  }
};
