// Sprite Studio: install it from the marketplace, draw with real mouse drags on its canvas, save PNGs into the
// scratch project and decode them here (zlib + PNG row filters, no packages), undo/redo with Ctrl+Z / Ctrl+Y,
// frames, the live preview, scale up, opening PNGs again, and the "Use in code" Tuff passing tuff --check.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

export const meta = { title: 'Sprite Studio plugin (pixel art editor)', timeout: 360000 };

const MAIN = `mention tgame

game = tgame.window("Test", 640, 480)
`;

// ---- PNG files, read and written here without any packages
export function decodePng(file) {
  const buf = fs.readFileSync(file);
  if (buf.readUInt32BE(0) !== 0x89504e47 || buf.readUInt32BE(4) !== 0x0d0a1a0a) throw new Error(`${file} isn't a PNG`);
  let o = 8, w = 0, h = 0, depth = 0, type = 0, interlace = 0;
  const idat = [], texts = [];
  while (o < buf.length) {
    const len = buf.readUInt32BE(o), kind = buf.toString('latin1', o + 4, o + 8), body = buf.subarray(o + 8, o + 8 + len);
    if (zlib.crc32(buf.subarray(o + 4, o + 8 + len)) !== buf.readUInt32BE(o + 8 + len)) throw new Error(`bad CRC in the ${kind} chunk`);
    if (kind === 'IHDR') { w = body.readUInt32BE(0); h = body.readUInt32BE(4); depth = body[8]; type = body[9]; interlace = body[12]; }
    else if (kind === 'IDAT') idat.push(body);
    else if (kind === 'tEXt') texts.push(body.toString('latin1'));
    else if (kind === 'IEND') break;
    o += 12 + len;
  }
  if (depth !== 8 || ![2, 6].includes(type) || interlace) throw new Error(`unexpected PNG format: depth ${depth}, type ${type}, interlace ${interlace}`);
  const bpp = type === 6 ? 4 : 3, stride = w * bpp;
  const raw = zlib.inflateSync(Buffer.concat(idat));
  if (raw.length !== (stride + 1) * h) throw new Error(`pixel data is ${raw.length} bytes, expected ${(stride + 1) * h}`);
  const out = Buffer.alloc(w * h * 4);
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)];
    const line = Buffer.from(raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)));
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? line[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
      let add = 0;
      if (f === 1) add = a;
      else if (f === 2) add = b;
      else if (f === 3) add = (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); add = pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      else if (f !== 0) throw new Error(`unknown PNG filter ${f} on row ${y}`);
      line[i] = (line[i] + add) & 255;
    }
    for (let x = 0; x < w; x++) {
      out[(y * w + x) * 4] = line[x * bpp]; out[(y * w + x) * 4 + 1] = line[x * bpp + 1]; out[(y * w + x) * 4 + 2] = line[x * bpp + 2];
      out[(y * w + x) * 4 + 3] = bpp === 4 ? line[x * 4 + 3] : 255;
    }
    prev = line;
  }
  // a pixel as "#rrggbb", or "clear" when it's see-through
  const at = (x, y) => { const i = (y * w + x) * 4; return out[i + 3] === 0 ? 'clear' : '#' + [out[i], out[i + 1], out[i + 2]].map((v) => v.toString(16).padStart(2, '0')).join('') + (out[i + 3] === 255 ? '' : `@${out[i + 3]}`); };
  return { w, h, texts, at, data: out };
}

function encodePng(w, h, rgba) {
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'latin1'), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 6;
  // "Sub" filtered rows, so the IDE reads a PNG that isn't laid out like its own
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 4 + 1)] = 1;
    for (let i = 0; i < w * 4; i++) raw[y * (w * 4 + 1) + 1 + i] = (rgba[y * w * 4 + i] - (i >= 4 ? rgba[y * w * 4 + i - 4] : 0)) & 255;
  }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 10000) => t.waitFor(js, ms);
  const P = (...p) => path.join(ctx.root, ...p);
  const SS = `document.querySelector('.ss')`;
  const q = (sel) => `${SS}.querySelector(${JSON.stringify(sel)})`;

  // Real clicks: scroll the thing into view, then press and release the mouse on its middle.
  // A toast sitting on top of it is moved out of the way first, as a person would wait for it to go.
  async function clickEl(sel) {
    const where = `(() => { const el = ${q(sel)}; if (!el) return null; el.scrollIntoView({ block: 'center', inline: 'nearest' }); const b = el.getBoundingClientRect(); const x = b.left + b.width / 2, y = b.top + b.height / 2; const hit = document.elementFromPoint(x, y); return { x, y, covered: !hit || !(el === hit || el.contains(hit) || hit.contains(el) || el.closest('label')?.contains(hit)) }; })()`;
    let r = await ev(where);
    if (!r) throw new Error(`Sprite Studio has no ${sel}`);
    if (r.covered) { await ev(`document.querySelectorAll('.toast').forEach((x) => x.remove()); 1`); r = await ev(where); }
    await t.sleep(60);
    await t.click(r.x, r.y);
  }
  const openFromList = async (rel) => {
    const i = await ev(`[...${SS}.querySelectorAll('.ss-menu [data-open]')].find((b) => b.textContent === ${JSON.stringify(rel)})?.dataset.open`);
    if (i == null) throw new Error(`The Open list has no ${rel}`);
    await clickEl(`.ss-menu [data-open="${i}"]`);
  };
  // Where a sprite pixel is on the screen. The canvas says its size in data-w and data-h.
  const showCanvas = async () => { await ev(`${q('.ss-canvas')}.scrollIntoView({ block: 'center' }); 1`); await t.sleep(80); };
  const cell = (x, y) => ev(`(() => { const c = ${q('.ss-canvas')}; const r = c.getBoundingClientRect(); return { x: r.left + (${x} + 0.5) * r.width / +c.dataset.w, y: r.top + (${y} + 0.5) * r.height / +c.dataset.h }; })()`);
  async function drag(points, button = 'left') {
    await showCanvas();
    const btn = button === 'left' ? 1 : 2;
    const a = await cell(...points[0]);
    await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: a.x, y: a.y });
    await t.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: a.x, y: a.y, button, buttons: btn, clickCount: 1 });
    for (const p of points.slice(1)) {
      const b = await cell(...p);
      await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: b.x, y: b.y, button, buttons: btn });
      await t.sleep(15);
    }
    const z = await cell(...points[points.length - 1]);
    await t.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: z.x, y: z.y, button, buttons: 0, clickCount: 1 });
    await t.sleep(120);
  }
  const tap = (x, y) => drag([[x, y]]);
  async function typeInto(sel, text, enter = false) {
    await clickEl(sel);
    await t.key('a', 2); // Ctrl+A: select what's there
    await t.type(text, 20);
    if (enter) await t.key('Enter');
  }
  // Focus the panel itself (a click on its hint line), like a person clicking in the panel before a shortcut.
  const focusPanel = () => clickEl('.ss-hint');
  const ctrl = (k, shift = false) => t.key(k, shift ? 10 : 2);
  const save = async () => { await clickEl('[data-a="save"]'); await t.sleep(700); };
  const png = (rel) => decodePng(P(...rel.split('/')));
  const exists = (rel) => fs.existsSync(P(...rel.split('/')));
  const pre = () => ev(`${q('.ss-pre')}?.textContent || ''`);
  const tuffOk = (name, code) => { fs.writeFileSync(P(name), code); return ctx.tuffCheck(P(name)); };
  const frames = () => ev(`[...${SS}.querySelectorAll('.ss-frame')].map((f) => f.classList.contains('on'))`);
  const editorLines = () => ev(`monaco.editor.getEditors()[0].getModel().getLineCount()`);
  const RED = '#d8403c', BLUE = '#3460c8', YELLOW = '#f7d046', GREEN = '#2f9a54', TEAL = '#22aa88';

  fs.writeFileSync(P('main.tuf'), MAIN);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(P('main.tuf'))}); return 1; })()`);
  await t.sleep(400);

  // 1. install it from the marketplace
  await ev(`(() => { window.TuffIDE.showSideView('plugins', true); return 1; })()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="sprite-studio"] [data-a="install"]')`);
  const cardText = await ev(`document.querySelector('.pl-card[data-id="sprite-studio"]').textContent`);
  check('The marketplace lists Sprite Studio as a built-in plugin', /Sprite Studio/.test(cardText) && /comes with TuffCode/.test(cardText), cardText);
  const inst = await ev(`(() => { const b = document.querySelector('.pl-card[data-id="sprite-studio"] [data-a="install"]'); b.scrollIntoView({ block: 'center' }); const r = b.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
  await t.click(inst.x, inst.y);
  const opened = await waitFor(`!!document.querySelector('.ss .ss-canvas') && !document.querySelector('#rightbar').classList.contains('hidden')`);
  check('Installing it opens the Sprite Studio panel on the right', opened && (await ev(`document.querySelector('#rb-title').textContent`)) === 'Sprite Studio' &&
    (await ev(`[...document.querySelectorAll('#toolstrip-right .ts-btn')].some((b) => b.title === 'Sprite Studio')`)), await ev(`window.TuffPluginHost.state()`));
  const mask = await ev(`(() => { const b = [...document.querySelectorAll('#toolstrip-right .ts-btn')].find((x) => x.title === 'Sprite Studio'); return decodeURIComponent(getComputedStyle(b.querySelector('.pi')).webkitMaskImage || ''); })()`);
  check('Its toolstrip button draws the pencil-and-pixels icon', mask.includes('M15.6 4.4a2 2 0 0 1 2.8 0') && mask.includes('M2.5 19.5h3v3h-3z'), mask.slice(0, 200));
  await ev(`document.documentElement.style.setProperty('--rightbar-w', '400px'); 1`);
  await t.sleep(400);

  // 2. a 16 x 16 canvas, zoomed to fit and crisp
  const canvas = await ev(`(() => { const c = ${q('.ss-canvas')}; const r = c.getBoundingClientRect(); const p = ${SS}.getBoundingClientRect(); return { w: +c.dataset.w, h: +c.dataset.h, bw: c.width, bh: c.height, cssW: r.width, panelW: p.width, render: getComputedStyle(c).imageRendering, size: ${q('[data-size].on')}.dataset.size, tool: ${q('[data-tool].on')}.dataset.tool }; })()`);
  check('It starts with a 16 x 16 canvas and the pencil', canvas.w === 16 && canvas.h === 16 && canvas.size === '16' && canvas.tool === 'pencil', canvas);
  check('The canvas fills the panel at a whole zoom, drawn pixelated', canvas.bw % 16 === 0 && canvas.bw === canvas.bh && canvas.cssW > canvas.panelW * 0.75 && canvas.cssW <= canvas.panelW && canvas.render === 'pixelated', canvas);
  check('"Use in code" waits for a save', /Save your sprite/.test(await ev(`${q('.ss-code')}.textContent`)), await ev(`${q('.ss-code')}.textContent`));

  // 3. draw: a red pencil line and a blue rectangle outline, then save as hero
  await typeInto('[data-f="name"]', 'hero');
  // Shortcut keys while typing the name stay with the box: the IDE would copy a line of main.tuf (Ctrl+D),
  // open its Replace box (Ctrl+R) or delete a line (Ctrl+Y), and move the typing into the code.
  const nameKeysBefore = await t.code();
  await ctrl('d');
  await ctrl('r');
  await ctrl('y');
  await t.sleep(200);
  const nameKeys = await ev(`({ focus: document.activeElement === ${q('[data-f="name"]')}, name: ${q('[data-f="name"]')}.value, replace: !!document.querySelector('.monaco-editor .find-widget.visible') })`);
  check('Ctrl+D, Ctrl+R and Ctrl+Y in the Name box leave the code file alone, and the box keeps the focus', (await t.code()) === nameKeysBefore && nameKeys.focus && nameKeys.name === 'hero' && !nameKeys.replace, { nameKeys, code: await t.code() });
  await clickEl(`[data-color="${RED}"]`);
  await drag([[2, 3], [4, 3], [7, 3], [9, 3]]);
  await clickEl(`[data-color="${BLUE}"]`);
  await clickEl('[data-tool="rect"]');
  await drag([[1, 6], [3, 8], [5, 10]]);
  check('The save line says where it goes', (await ev(`${q('.ss-where')}.textContent`)) === 'Saves sprites/hero.png (16 x 16 pixels).', await ev(`${q('.ss-where')}.textContent`));
  await save();
  let hero = exists('sprites/hero.png') && png('sprites/hero.png');
  check('Save writes sprites/hero.png into the project', !!hero && hero.w === 16 && hero.h === 16, hero && { w: hero.w, h: hero.h });
  check('The PNG has the pencil line in red', hero && [2, 3, 4, 5, 6, 7, 8, 9].every((x) => hero.at(x, 3) === RED) && hero.at(1, 3) === 'clear' && hero.at(10, 3) === 'clear', hero && [1, 2, 9, 10].map((x) => hero.at(x, 3)));
  check('...the rectangle outline in blue, hollow inside, and see-through elsewhere',
    hero && [[1, 6], [5, 6], [1, 10], [5, 10], [3, 6], [1, 8], [5, 8], [3, 10]].every(([x, y]) => hero.at(x, y) === BLUE) && hero.at(3, 8) === 'clear' && hero.at(0, 0) === 'clear' && hero.at(15, 15) === 'clear',
    hero && { corner: hero.at(1, 6), inside: hero.at(3, 8), origin: hero.at(0, 0) });
  check('The PNG remembers its scale in a text note', hero && hero.texts.includes('Sprite Studio\0scale=1'), hero && hero.texts);

  // 4. "Use in code": tgame picked from the open file, its window name and middle; all three pass tuff --check
  await waitFor(`!!${q('.ss-pre')}`);
  const tg = await pre();
  check('"Use in code" shows the tgame line for the open game (its window and middle)', tg === 'hero = game:image("sprites/hero.png", 320, 240, 16)' && (await ev(`${q('[data-lib].on')}.dataset.lib`)) === 'tgame', tg);
  let out = tuffOk('use_tgame.tuf', `${MAIN}${tg}\n\nwhile game:open():\n    game:frame()\n`);
  check('The tgame code passes tuff --check in a small game', /OK/.test(out), out);
  await clickEl('[data-lib="mtgui"]');
  const mt = await pre();
  out = tuffOk('use_mtgui.tuf', `mention mtgui\n\napp = mtgui.window("Test")\n${mt}\n`);
  check('mtgui: app:image "sprites/hero.png", and it passes tuff --check', mt === 'hero = app:image "sprites/hero.png"' && /OK/.test(out), { mt, out });
  await clickEl('[data-lib="atgui"]');
  const at = await pre();
  out = tuffOk('use_atgui.tuf', `mention atgui\n\napp = atgui.window("Test")\n${at}\n`);
  check('atgui: a bigger, still sharp picture, and it passes tuff --check', at === 'hero = app:image("sprites/hero.png", 64)\nhero:css "image-rendering: pixelated; border-radius: 0"' && /OK/.test(out), { at, out });
  await clickEl('[data-lib="tgame"]');

  // 5. Insert puts it in the open file
  await t.cursorEnd();
  await clickEl('[data-a="insert"]');
  await t.sleep(300);
  const code = await t.code();
  check('Insert puts the line where the cursor is in main.tuf', code === `${MAIN}hero = game:image("sprites/hero.png", 320, 240, 16)\n`, code);
  out = tuffOk('inserted.tuf', `${code}\nwhile game:open():\n    game:frame()\n`);
  check('main.tuf with the inserted line passes tuff --check', /OK/.test(out), out);

  // 6. fill, then undo and redo with the keyboard (only while the panel has focus)
  await clickEl(`[data-color="${YELLOW}"]`);
  await clickEl('[data-tool="fill"]');
  await tap(12, 12);
  await save();
  hero = png('sprites/hero.png');
  check('Fill paints the see-through area around the shapes, not the inside of the rectangle', hero.at(12, 12) === YELLOW && hero.at(0, 0) === YELLOW && hero.at(15, 4) === YELLOW && hero.at(3, 8) === 'clear' && hero.at(3, 3) === RED, [hero.at(12, 12), hero.at(0, 0), hero.at(3, 8), hero.at(3, 3)]);
  // Ctrl+Z in the code editor is the editor's: it takes the inserted line back out and leaves the sprite alone
  await ev(`monaco.editor.getEditors()[0].focus(); 1`);
  await ctrl('z');
  await t.sleep(200);
  const afterEditorUndo = await t.code();
  await save();
  check('Ctrl+Z in the code editor undoes code, not the sprite', png('sprites/hero.png').at(12, 12) === YELLOW && !afterEditorUndo.includes('game:image'), afterEditorUndo);
  await focusPanel();
  await ctrl('z');
  await save();
  check('Ctrl+Z in the panel undoes the fill', png('sprites/hero.png').at(12, 12) === 'clear' && png('sprites/hero.png').at(2, 3) === RED, png('sprites/hero.png').at(12, 12));
  const lines = await editorLines();
  await focusPanel();
  await ctrl('y');
  await save();
  check('Ctrl+Y redoes it, and doesn\'t delete a line in the code editor', png('sprites/hero.png').at(12, 12) === YELLOW && (await editorLines()) === lines, { px: png('sprites/hero.png').at(12, 12), lines, now: await editorLines() });
  await focusPanel();
  await ctrl('z', true); // Ctrl+Shift+Z is redo too: nothing left to redo, so nothing changes
  await ctrl('z');
  await clickEl('[data-a="redo"]');
  await clickEl('[data-a="undo"]');
  await save();
  check('The Undo and Redo buttons work too', png('sprites/hero.png').at(12, 12) === 'clear', png('sprites/hero.png').at(12, 12));

  // 7. eraser, mirror, eyedropper, line, a typed colour code
  await clickEl('[data-tool="eraser"]');
  await drag([[2, 3], [3, 3]]);
  await clickEl(`[data-color="${GREEN}"]`);
  check('Picking a colour while rubbing out goes back to the last drawing tool (fill)', (await ev(`${q('[data-tool].on')}.dataset.tool`)) === 'fill', await ev(`${q('[data-tool].on')}.dataset.tool`));
  await clickEl('[data-tool="pencil"]');
  await clickEl('[data-a="mirror"]');
  await tap(1, 1);
  await clickEl('[data-a="mirror"]');
  await clickEl('[data-tool="picker"]');
  await tap(5, 3);
  const picked = await ev(`({ hex: ${q('[data-f="hex"]')}.value, tool: ${q('[data-tool].on')}.dataset.tool })`);
  check('The eyedropper picks up red and goes back to drawing', picked.hex === RED && picked.tool === 'pencil', picked);
  await clickEl('[data-tool="line"]');
  await drag([[0, 15], [8, 15], [15, 15]]);
  await typeInto('[data-f="hex"]', TEAL, true);
  await clickEl('[data-tool="pencil"]');
  await tap(8, 13);
  await save();
  hero = png('sprites/hero.png');
  check('Eraser rubs out, mirror draws both sides, line goes edge to edge, the typed colour draws',
    hero.at(2, 3) === 'clear' && hero.at(3, 3) === 'clear' && hero.at(4, 3) === RED && hero.at(1, 1) === GREEN && hero.at(14, 1) === GREEN &&
    [0, 5, 10, 15].every((x) => hero.at(x, 15) === RED) && hero.at(8, 13) === TEAL,
    { erased: hero.at(2, 3), mirror: [hero.at(1, 1), hero.at(14, 1)], line: [hero.at(0, 15), hero.at(15, 15)], teal: hero.at(8, 13) });
  check('Recent colours start with the last one used', (await ev(`[...${SS}.querySelectorAll('.ss-recent [data-color]')].map((b) => b.dataset.color)`))[0] === TEAL, await ev(`[...${SS}.querySelectorAll('.ss-recent [data-color]')].map((b) => b.dataset.color)`));

  // 8. frames: duplicate, draw on the copy, add, delete, move it to the front, 12 frames a second, a sprite sheet
  await clickEl('[data-a="dup"]');
  check('Duplicate adds a second frame and selects it', JSON.stringify(await frames()) === '[false,true]', await frames());
  await tap(12, 5);
  await clickEl('[data-a="add"]');
  check('Add puts an empty third frame after it', JSON.stringify(await frames()) === '[false,false,true]', await frames());
  await clickEl('[data-a="del"]');
  await clickEl('[data-frame="1"]');
  await clickEl('[data-a="left"]');
  check('Delete takes it away, and the arrow moves frame 2 to the front', JSON.stringify(await frames()) === '[true,false]', await frames());
  await typeInto('[data-f="fps"]', '12');
  await t.key('Tab');
  await clickEl('[data-f="sheet"]');
  check('The save line lists the numbered frames and the sheet', /^Saves sprites\/hero_1\.png to hero_2\.png \(16 x 16 pixels each\), and the sheet hero_sheet\.png\.$/.test(await ev(`${q('.ss-where')}.textContent`)), await ev(`${q('.ss-where')}.textContent`));
  await save();
  const f1 = png('sprites/hero_1.png'), f2 = png('sprites/hero_2.png'), sh = exists('sprites/hero_sheet.png') && png('sprites/hero_sheet.png');
  check('Frames save as hero_1.png and hero_2.png, in their new order', f1.at(12, 5) === TEAL && f2.at(12, 5) === 'clear' && f1.at(8, 13) === TEAL && f2.at(8, 13) === TEAL, [f1.at(12, 5), f2.at(12, 5)]);
  check('The sprite sheet has both frames side by side (32 x 16)', sh && sh.w === 32 && sh.h === 16 && sh.at(12, 5) === TEAL && sh.at(28, 5) === 'clear' && sh.at(4, 3) === RED && sh.at(20, 3) === RED, sh && { w: sh.w, h: sh.h, a: sh.at(12, 5), b: sh.at(28, 5) });

  // 9. onion skin shows the frame before, faintly; the preview plays the frames
  await clickEl('[data-frame="1"]');
  const shown = () => ev(`(() => { const c = ${q('.ss-canvas')}; const k = c.width / +c.dataset.w; return [...c.getContext('2d').getImageData(Math.floor((12 + 0.5) * k), Math.floor((5 + 0.5) * k), 1, 1).data]; })()`);
  const before = await shown();
  await clickEl('[data-f="onion"]');
  const withOnion = await shown();
  await clickEl('[data-f="onion"]');
  const teal = [0x22, 0xaa, 0x88];
  check('Onion skin shows frame 1 faintly under frame 2', JSON.stringify(before) !== JSON.stringify(withOnion) && withOnion.slice(0, 3).some((v, i) => Math.abs(v - teal[i]) > 20) && JSON.stringify(await shown()) === JSON.stringify(before), { before, withOnion });
  const seen = new Set();
  for (let i = 0; i < 30; i++) {
    seen.add(await ev(`${q('.ss-preview canvas')}.getContext('2d').getImageData(12, 5, 1, 1).data[3]`));
    await t.sleep(40);
  }
  check('The preview plays the animation (the pixel comes and goes)', seen.has(0) && seen.has(255), [...seen]);

  // 10. the animation's code: a list of pictures and a timer, 12 a second; "Try in a new file"
  await waitFor(`/hero_pics/.test(${q('.ss-pre')}.textContent)`);
  const anim = await pre();
  check('Animated tgame code steps through hero_1.png and hero_2.png 12 times a second',
    anim.includes('hero_pics = ["sprites/hero_1.png", "sprites/hero_2.png"]') && anim.includes('hero = game:image("sprites/hero_1.png", 320, 240, 16)') && anim.includes('game:every(1 / 12, next_hero_pic)') && anim.includes('    hero:set hero_pics[hero_at]'), anim);
  out = tuffOk('use_anim.tuf', `${MAIN}${anim}\n\nwhile game:open():\n    game:frame()\n`);
  check('The animation code passes tuff --check in a small game', /OK/.test(out), out);
  for (const lib of ['mtgui', 'atgui']) {
    await clickEl(`[data-lib="${lib}"]`);
    out = tuffOk(`use_anim_${lib}.tuf`, `mention ${lib}\n\napp = ${lib}.window("Test")\n${await pre()}\n`);
    check(`The ${lib} animation code passes tuff --check`, /OK/.test(out) && (await pre()).includes('app:every(1 / 12, next_hero_pic)'), { code: await pre(), out });
  }
  await clickEl('[data-lib="tgame"]');
  await clickEl('[data-a="try"]');
  await waitFor(`/hero_game\\.tuf$/.test(window.TuffIDE.activeFile() || '')`);
  out = exists('hero_game.tuf') ? ctx.tuffCheck(P('hero_game.tuf')) : 'no file';
  check('"Try in a new file" makes hero_game.tuf, opens it, and it passes tuff --check', /OK/.test(out) && /hero_game\.tuf$/.test(await ev(`window.TuffIDE.activeFile()`)) && (await t.code()).startsWith('mention tgame'), out);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(P('main.tuf'))}); return 1; })()`);

  // 11. scale up: 4x saves 64 x 64 with every pixel a sharp 4 x 4 block
  await clickEl('[data-scale="4"]');
  await save();
  const big = png('sprites/hero_1.png');
  const block = [48, 49, 50, 51].every((x) => [20, 21, 22, 23].every((y) => big.at(x, y) === TEAL));
  check('Scale up 4x saves 64 x 64, each pixel a 4 x 4 block', big.w === 64 && big.h === 64 && block && big.at(47, 20) === 'clear' && big.at(52, 20) === 'clear' && big.texts.includes('Sprite Studio\0scale=4'), { w: big.w, h: big.h, block, edge: big.at(47, 20) });
  out = await pre();
  check('The code uses the saved size (64 wide)', out.includes('game:image("sprites/hero_1.png", 320, 240, 64)'), out);

  // 12. New, then open the 4x frames again: back to the real 16 x 16 pixels, both frames
  await clickEl('[data-a="new"]');
  check('New starts a blank sprite called "sprite"', (await ev(`${q('[data-f="name"]')}.value`)) === 'sprite' && JSON.stringify(await frames()) === '[true]', await ev(`${q('[data-f="name"]')}.value`));
  await clickEl('[data-a="open"]');
  await waitFor(`!${q('.ss-menu')}.classList.contains('hidden')`);
  const listed = await ev(`[...${SS}.querySelectorAll('.ss-menu [data-open]')].map((b) => b.textContent)`);
  check('Open lists the project\'s PNG pictures', ['sprites/hero.png', 'sprites/hero_1.png', 'sprites/hero_2.png', 'sprites/hero_sheet.png'].every((f) => listed.includes(f)), listed);
  await openFromList('sprites/hero_2.png');
  await waitFor(`${q('.ss-canvas')}.dataset.w === '16' && ${SS}.querySelectorAll('.ss-frame').length === 2`);
  const reopened = await ev(`({ w: ${q('.ss-canvas')}.dataset.w, frames: ${SS}.querySelectorAll('.ss-frame').length, on: [...${SS}.querySelectorAll('.ss-frame')].findIndex((f) => f.classList.contains('on')), name: ${q('[data-f="name"]')}.value, folder: ${q('[data-f="folder"]')}.value, scale: ${q('[data-scale].on')}.dataset.scale })`);
  check('Opening hero_2.png brings back both frames at 16 x 16, on frame 2, saved at 4x', reopened.w === '16' && reopened.frames === 2 && reopened.on === 1 && reopened.name === 'hero' && reopened.folder === 'sprites' && reopened.scale === '4', reopened);
  const old = ['hero_1', 'hero_2', 'hero_sheet'].map((n) => png(`sprites/${n}.png`).data);
  await save();
  const again = ['hero_1', 'hero_2', 'hero_sheet'].map((n) => png(`sprites/${n}.png`).data);
  check('Saving it again writes the same pictures, without asking (they are its own files)', old.every((d, i) => d.equals(again[i])) && (await ev(`document.querySelector('#modal').classList.contains('hidden')`)), null);

  // 13. a PNG made somewhere else (12 x 10, no note): opens as a custom size; Custom resizes it to 20 x 12
  const coin = Buffer.alloc(12 * 10 * 4);
  for (let y = 0; y < 10; y++) for (let x = 0; x < 12; x++) coin.set((x + y) % 3 ? [255, 200, 0, 255] : [0, 0, 0, 0], (y * 12 + x) * 4);
  fs.writeFileSync(P('sprites', 'coin.png'), encodePng(12, 10, coin));
  await clickEl('[data-a="open"]');
  await waitFor(`!${q('.ss-menu')}.classList.contains('hidden')`);
  const ed = await ev(`(() => { const r = document.querySelector('.monaco-editor .view-lines').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + 40 }; })()`);
  await t.click(ed.x, ed.y);
  check('A click in the code editor closes the Open list', await waitFor(`${q('.ss-menu')}.classList.contains('hidden')`, 2000), null);
  await clickEl('[data-a="open"]');
  await waitFor(`[...${SS}.querySelectorAll('.ss-menu [data-open]')].some((b) => b.textContent === 'sprites/coin.png')`);
  await openFromList('sprites/coin.png');
  await waitFor(`${q('.ss-canvas')}.dataset.w === '12'`);
  const c1 = await ev(`({ w: ${q('.ss-canvas')}.dataset.w, h: ${q('.ss-canvas')}.dataset.h, size: ${q('[data-size].on')}.dataset.size, frames: ${SS}.querySelectorAll('.ss-frame').length, scale: ${q('[data-scale].on')}.dataset.scale, name: ${q('[data-f="name"]')}.value })`);
  check('A 12 x 10 PNG opens as a custom size, one frame, at 1x', c1.w === '12' && c1.h === '10' && c1.size === 'custom' && c1.frames === 1 && c1.scale === '1' && c1.name === 'coin', c1);
  await clickEl('[data-size="custom"]');
  await typeInto('[data-f="cw"]', '20');
  await typeInto('[data-f="ch"]', '12');
  await clickEl('[data-a="resize"]');
  await save();
  const c2 = png('sprites/coin.png');
  check('Custom 20 x 12 keeps the drawing in the middle', c2.w === 20 && c2.h === 12 && c2.at(0, 0) === 'clear' && c2.at(4, 1) === 'clear' && c2.at(5, 1) === '#ffc800' && c2.at(15, 10) === '#ffc800' && c2.at(16, 1) === 'clear', { w: c2.w, h: c2.h, a: c2.at(4, 1), b: c2.at(5, 1) });
  await clickEl('[data-size="32"]');
  check('A preset size resizes too (32 x 32)', (await ev(`${q('.ss-canvas')}.dataset.w + 'x' + ${q('.ss-canvas')}.dataset.h`)) === '32x32', await ev(`${q('.ss-canvas')}.dataset.w`));

  // 14. saving over a picture that isn't this sprite's asks first
  await clickEl('[data-a="new"]');
  await typeInto('[data-f="name"]', 'coin');
  await clickEl('[data-a="save"]');
  const asked = await waitFor(`!document.querySelector('#modal').classList.contains('hidden')`, 4000);
  const title = await ev(`document.querySelector('#modal-title').textContent`);
  const cancel = await ev(`(() => { const r = document.querySelector('#modal-cancel').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
  await t.click(cancel.x, cancel.y);
  await t.sleep(300);
  check('Saving over another picture asks first, and Cancel leaves it alone', asked && title === 'Replace sprites/coin.png?' && png('sprites/coin.png').w === 20, title);

  // 15. a little blinking smiley for the screenshots, at 400 px and then 300 px wide (where everything still fits)
  await clickEl('[data-a="new"]');
  await clickEl('[data-size="16"]');
  await typeInto('[data-f="name"]', 'smiley');
  await clickEl(`[data-color="${YELLOW}"]`);
  await clickEl('[data-tool="fillrect"]');
  await drag([[3, 3], [12, 12]]);
  await clickEl('[data-color="#1b1b24"]');
  await clickEl('[data-tool="pencil"]');
  await clickEl('[data-a="mirror"]');
  await drag([[5, 6], [5, 7]]);
  await drag([[5, 10], [6, 11], [7, 11]]);
  await clickEl('[data-a="mirror"]');
  await clickEl('[data-a="dup"]');
  await clickEl(`[data-color="${YELLOW}"]`);
  await clickEl('[data-a="mirror"]');
  await tap(5, 6);
  await clickEl('[data-a="mirror"]');
  await clickEl('[data-frame="0"]');
  await clickEl('[data-scale="4"]');
  await save();
  const smile = exists('sprites/smiley_1.png') && png('sprites/smiley_1.png'), blink = exists('sprites/smiley_2.png') && png('sprites/smiley_2.png');
  check('The smiley saves as two 64 x 64 frames: eyes open, then shut', smile && blink && smile.w === 64 && smile.at(20, 24) === '#1b1b24' && smile.at(40, 24) === '#1b1b24' && blink.at(20, 24) === YELLOW && blink.at(20, 28) === '#1b1b24', smile && blink && [smile.at(20, 24), blink.at(20, 24), blink.at(20, 28)]);
  await waitFor(`/smiley_pics/.test(${q('.ss-pre')}.textContent)`);
  const smileCode = await pre();
  out = tuffOk('use_smiley.tuf', `${MAIN}${smileCode}\n\nwhile game:open():\n    game:frame()\n`);
  check('A longer list of pictures goes one per line, and still passes tuff --check', smileCode.startsWith('smiley_pics = [\n    "sprites/smiley_1.png",\n    "sprites/smiley_2.png"\n]\n') && /OK/.test(out), { smileCode, out });
  const rightbar = () => ev(`(() => { const r = document.querySelector('#rightbar').getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);
  const clean = async () => { await ev(`document.querySelectorAll('.toast').forEach((x) => x.remove()); 1`); await t.sleep(150); };
  await ev(`${SS}.scrollTop = 0; 1`);
  const eye = await cell(8, 8);
  await t.move(eye.x, eye.y);
  await clean();
  const s1 = await t.shot('ss_400.png', await rightbar());
  await ev(`${SS}.scrollTop = ${SS}.scrollHeight; 1`);
  await clean();
  const s2 = await t.shot('ss_400_bottom.png', await rightbar());
  // 280 px is the narrowest the sidebar can be dragged to
  for (const w of [280, 300]) {
    await ev(`document.documentElement.style.setProperty('--rightbar-w', '${w}px'); 1`);
    await t.sleep(500);
    const narrow = await ev(`(() => { const s = ${SS}; const c = s.querySelector('.ss-canvas').getBoundingClientRect(); const p = s.getBoundingClientRect(); const over = [...s.querySelectorAll('button, input, .ss-pre, canvas')].filter((el) => { const r = el.getBoundingClientRect(); return r.width && (r.right > p.right + 0.5 || r.left < p.left - 0.5); }).map((el) => el.className || el.tagName); return { scroll: s.scrollWidth, client: s.clientWidth, canvas: c.width, canvasRight: c.right, panelRight: p.right, over }; })()`);
    check(`At ${w} px wide nothing spills out of the panel, and the canvas still fills it`, narrow.scroll <= narrow.client && narrow.canvasRight <= narrow.panelRight && narrow.canvas > w * 0.75 && !narrow.over.length, narrow);
  }
  await ev(`${SS}.scrollTop = 0; document.querySelectorAll('.toast').forEach((x) => x.remove()); 1`);
  await t.sleep(200);
  const s3 = await t.shot('ss_300.png', await rightbar());
  t.info(`screenshots: ${[s1, s2, s3].join(', ')}`);

  const ours = t.events.filter((e) => /sprite-studio|panel\.js/.test(e));
  check('No errors from the plugin on the page', !ours.length, ours);
};
