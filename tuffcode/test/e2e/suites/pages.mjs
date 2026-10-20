// Design Studio pages and Full size: Add pages, switch pages, "open page" buttons, + Page, page events.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'Design Studio pages and Full size', project: 'project2' };

const NL = '\n';
const SHOP = ['mention mtgui', '', 'app = mtgui.window("Shop", 400, 520)', 'app:heading "My Shop"', 'app:small "Fresh pizza, every day."', 'name = app:input "Your name"', 'app:button("Order", order, "primary")', 'status = app:text ""', '', 'func order():', '    status:set "Thanks " + name:value', ''].join(NL);

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const P = (f) => path.join(ctx.root, f);
  const shop = JSON.stringify(P('shop.tuf'));
  const code = async () => (await ev(`window.__m.getValue()`)).replace(/\r\n/g, NL);
  const lines = async () => (await code()).split(NL);
  const clickPage = (label) => ev(`(() => { const b = [...document.querySelectorAll('.sd-pg')].find(x => x.textContent.trim() === ${JSON.stringify(label)}); if (!b) return false; b.click(); return true; })()`);
  const pageTabs = () => ev(`[...document.querySelectorAll('.sd-pg')].map(b => (b.classList.contains('on') ? '*' : '') + b.textContent.trim())`);

  fs.writeFileSync(P('shop.tuf'), SHOP);
  await ev(`(async () => { window.__m = await window.TuffIDE.getModel(${shop}); window.__m.setValue(${JSON.stringify(SHOP)}); await window.TuffIDE.openStudio(${shop}); return 1; })()`);
  await t.sleep(1200);

  check('A one-page app shows an "Add pages" button over the canvas', JSON.stringify(await pageTabs()) === JSON.stringify(['Add pages']), await pageTabs());

  // 1. Add pages: everything moves onto Home, and Page 2 is added
  await clickPage('Add pages');
  await t.sleep(700);
  let l = await lines();
  const hi = l.indexOf('home = app:page "Home"');
  check('"Add pages" puts the current widgets on a Home page and adds Page 2', hi === 3 && l[4] === 'home:heading "My Shop"' && l.includes('name = home:input "Your name"') && l.includes('home:button("Order", order, "primary")') && l.includes('page_2 = app:page "Page 2"'), l.slice(0, 12));
  check('Page tabs show Home and Page 2, with Page 2 open', JSON.stringify(await pageTabs()) === JSON.stringify(['Home', '*Page 2', 'Page']), await pageTabs());
  await t.shot('pg_added.png');

  // 2. switch pages
  await clickPage('Home');
  await t.sleep(500);
  const homeShown = await ev(`!!document.querySelector('#sd-stage .pv-page') && [...document.querySelectorAll('#sd-stage .pv-btn')].some(b => b.textContent === 'Order')`);
  check('Clicking the Home tab shows the Home page', homeShown && (await pageTabs())[0] === '*Home', await pageTabs());

  // 3. button -> open page
  await ev(`(() => { const n = [...document.querySelectorAll('#sd-stage .pv-node.k-button')].find(x => x.textContent === 'Order'); n.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, button: 0 })); window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); })()`);
  await t.sleep(500);
  const opt = await ev(`(() => { const s = [...document.querySelectorAll('#sd-props .pf')].find(f => /When clicked/.test(f.textContent))?.querySelector('select'); return s ? [...s.options].map(o => o.textContent) : null; })()`);
  await ev(`(() => { const s = [...document.querySelectorAll('#sd-props .pf')].find(f => /When clicked/.test(f.textContent)).querySelector('select'); s.value = '+page:page_2'; s.dispatchEvent(new Event('change')); })()`);
  await t.sleep(700);
  let c = await code();
  check('A button\'s "When clicked" offers "→ Open page" and writes go_page_2()', !!opt && opt.includes('→ Open page "Page 2"') && /home:button\("Order", go_page_2(, "primary")?\)/.test(c) && new RegExp('func go_page_2\\(\\):' + NL + '    page_2:open').test(c), { opt, tail: c.slice(-160) });
  const opt2 = await ev(`(() => { const s = [...document.querySelectorAll('#sd-props .pf')].find(f => /When clicked/.test(f.textContent))?.querySelector('select'); return s ? s.options[s.selectedIndex].textContent : null; })()`);
  check('The event then reads go_page_2() → opens page "Page 2"', opt2 === 'go_page_2() → opens page "Page 2"', opt2);

  // 4. "+ Page" adds Page 3; dropping a tile lands on the open page
  await clickPage('Page');
  await t.sleep(600);
  check('"+ Page" adds Page 3 and opens it', (await code()).includes('page_3 = app:page "Page 3"') && (await pageTabs()).includes('*Page 3'), await pageTabs());
  await ev(`document.querySelector('.sd-tile[data-kind="text"]').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, button: 0, clientX: 5, clientY: 5 }))`);
  await ev(`window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }))`);
  await t.sleep(600);
  check('Clicking the Text tile adds it to the open page', /\n\w+ = page_3:text "Some text"/.test(await code()), (await lines()).slice(-14));

  // 5. page opened event
  await clickPage('Page 2');
  await t.sleep(400);
  await ev(`(() => { const s = [...document.querySelectorAll('#sd-props .pf')].find(f => /When this page opens/.test(f.textContent)).querySelector('select'); s.value = '+new'; s.dispatchEvent(new Event('change')); })()`);
  await t.sleep(700);
  c = await code();
  check('A page\'s "When this page opens" writes page_2:opened page_2_opened', /\npage_2:opened page_2_opened\n/.test(c) && /func page_2_opened\(\):\n    say "Page 2 opened"/.test(c), c.slice(-300));

  // 6. still valid Tuff
  fs.writeFileSync(P('shop_after.tuf'), c);
  const out = ctx.tuffCheck(P('shop_after.tuf'));
  check('The multi-page app passes tuff --check', /OK/.test(out), out);
  await t.shot('pg_final.png');

  // 7. full size
  await ev(`document.querySelector('#sd-full').click()`);
  await t.sleep(500);
  const full = await ev(`({ cls: document.querySelector('#app').classList.contains('studio-full'), side: getComputedStyle(document.querySelector('#sidebar')).display, tabs: getComputedStyle(document.querySelector('#tabs')).display, title: getComputedStyle(document.querySelector('#titlebar')).display })`);
  await t.shot('pg_full.png');
  await ev(`document.querySelector('#sd-full').click()`);
  await t.sleep(400);
  const back = await ev(`!document.querySelector('#app').classList.contains('studio-full') && getComputedStyle(document.querySelector('#sidebar')).display !== 'none'`);
  check('Full size hides the sidebar and tabs (title bar stays) and toggles back', full.cls && full.side === 'none' && full.tabs === 'none' && full.title !== 'none' && back, { full, back });
  await ev(`(async () => { await window.TuffIDE.openFile(${shop}); return 1; })()`);
  await t.sleep(300);
  const leftStudio = await ev(`!document.querySelector('#app').classList.contains('studio-on')`);
  check('Leaving the Studio drops full-size layout (code view normal)', leftStudio, null);
};
