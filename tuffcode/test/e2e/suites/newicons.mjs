// The plugin icons (Tuff Agents: chat bubble, Snippet Library: scissors) are what the app actually draws:
// in the right toolstrip, on the marketplace cards and in the empty Tuff Agents chat.
export const meta = { title: 'plugin icons' };

const CHAT = 'M3 7.5A3.5 3.5 0 0 1 6.5 4h11'; // start of the chat bubble path
const SCISSORS = 'M8.6 15.6L21 5.5'; // a scissors blade
const OLD = ['M11 3.5l1.9 4.8', 'M8 7l-5 5 5 5M16 7']; // the old sparkles and </>

export default async (t) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const rect = (sel) => ev(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);
  // The SVG inside a mask url, decoded, for every element matching sel
  const masksOf = (sel) => ev(`[...document.querySelectorAll(${JSON.stringify(sel)})].map(el => decodeURIComponent(getComputedStyle(el).webkitMaskImage || ''))`);

  // Marketplace: install both plugins (a fresh profile has none)
  await ev(`(() => { window.TuffIDE.showSideView('plugins', true); return 1; })()`);
  await t.waitFor(`document.querySelectorAll('.pl-card').length >= 2`);
  for (const id of ['tuff-agents', 'snippets']) {
    await ev(`document.querySelector('.pl-card[data-id="${id}"] [data-a="install"]')?.click(); 1`);
    await t.sleep(1500);
  }
  check('Both plugins have a button in the right toolstrip', await t.waitFor(`['Tuff Agents', 'Snippets'].every(n => [...document.querySelectorAll('#toolstrip-right .ts-btn')].some(b => b.title === n))`),
    await ev(`[...document.querySelectorAll('#toolstrip-right .ts-btn')].map(b => b.title)`));

  const strip = await ev(`[...document.querySelectorAll('#toolstrip-right .ts-btn')].map(b => ({ title: b.title, svg: decodeURIComponent(getComputedStyle(b.querySelector('.pi')).webkitMaskImage) }))`);
  const agentsBtn = strip.find((b) => b.title === 'Tuff Agents');
  const snipBtn = strip.find((b) => b.title === 'Snippets');
  check('Toolstrip: Tuff Agents draws the chat bubble', !!agentsBtn && agentsBtn.svg.includes(CHAT), agentsBtn);
  check('Toolstrip: Snippets draws the scissors', !!snipBtn && snipBtn.svg.includes(SCISSORS), snipBtn);

  const cards = await masksOf('.pl-card .pl-ic .pi');
  check('Marketplace: one card shows the chat bubble', cards.filter((s) => s.includes(CHAT)).length === 1, cards.map((s) => s.slice(60, 140)));
  check('Marketplace: one card shows the scissors', cards.filter((s) => s.includes(SCISSORS)).length === 1, cards.map((s) => s.slice(60, 140)));
  check('No old icon is drawn anywhere', ![...strip.map((b) => b.svg), ...cards].some((s) => OLD.some((o) => s.includes(o))), 'an old icon is still drawn');
  await t.shot('ni_marketplace.png', await rect('#sidebar'));

  // Open Tuff Agents: its empty chat has the big icon (gradient through the same shape)
  await ev(`(() => { const b = [...document.querySelectorAll('#toolstrip-right .ts-btn')].find(b => b.title === 'Tuff Agents'); if (!b.classList.contains('active')) b.click(); return 1; })()`);
  await t.sleep(900);
  const rule = await ev(`(() => { for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch { continue; } for (const r of rules) if (r.selectorText === '.ta-empty-ic') return decodeURIComponent(r.style.webkitMaskImage || r.style.maskImage || ''); } return null; })()`);
  check('Empty Tuff Agents chat uses the chat bubble too', !!rule && rule.includes(CHAT) && !rule.includes(OLD[0]), rule && rule.slice(0, 200));
  const empty = await ev(`!!document.querySelector('.ta-empty-ic') && getComputedStyle(document.querySelector('.ta-empty-ic')).display !== 'none'`);
  t.info(`empty-chat icon on screen right now: ${empty}`);
  check('The open Tuff Agents button is highlighted', await ev(`[...document.querySelectorAll('#toolstrip-right .ts-btn')].find(b => b.title === 'Tuff Agents').classList.contains('active')`), false);
  await t.shot('ni_rightbar.png', await rect('#rightbar'));
  const ts = await rect('#toolstrip-right');
  if (ts) await t.shot('ni_toolstrip.png', { x: ts.x - 4, y: ts.y - 4, width: ts.width + 8, height: Math.min(ts.height + 8, 120) });
};
