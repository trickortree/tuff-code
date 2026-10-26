// The plugin icons (Tuff Agents: a chat bubble with a sparkle, Snippet Library: scissors) are what the app actually
// draws: in the right toolstrip, on the marketplace cards and in the empty Tuff Agents chat. Since 1.3.0 they're
// MingCute's chat-3-ai-line and scissors-line, like the rest of TuffCode's icons (renderer/js/icons.js).
export const meta = { title: 'plugin icons' };

const CHAT = 'm10 18.814l.186-.982'; // in MingCute's chat-3-ai-line
const SCISSORS = 'M16.984 2.283a2 2 0 0 1 .492'; // the start of MingCute's scissors-line
// The old ones: sparkles, </>, the hand-drawn chat bubble and scissors blade.
const OLD = ['M11 3.5l1.9 4.8', 'M8 7l-5 5 5 5M16 7', 'M3 7.5A3.5 3.5 0 0 1 6.5 4h11', 'M8.6 15.6L21 5.5'];

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

  // Settings is a drawn cog wheel (MingCute's settings-5-line: a hole, then the wheel) on every system, not a font
  // glyph, and the Gear Customizer's gear in the editor margin is the same cog.
  const cog = await ev(`(() => { const b = document.querySelector('#btn-settings'); const s = b?.querySelector('svg.i-cog'); const r = s?.getBoundingClientRect(); const ps = s ? [...s.querySelectorAll('path')] : []; return s && { icon: s.dataset.icon, paths: ps.length, d: ps[0]?.getAttribute('d') || '', stroke: ps[1] ? getComputedStyle(ps[1]).stroke : '', w: r.width, h: r.height, glyph: !!b.querySelector('.fl') }; })()`);
  check('Settings: the button draws a cog wheel around a hole, in the icon colour', !!cog && cog.icon === 'settings-5-line' && cog.paths === 2 && /^M15 12a3 3 0 1 1-6 0/.test(cog.d) && cog.stroke !== 'none' && cog.w === 16 && cog.h === 16 && !cog.glyph, cog && { ...cog, d: cog.d.slice(0, 60) });
  const marginGear = await ev(`(() => { for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch { continue; } for (const r of rules) if (r.selectorText === '.tuff-gear') return decodeURIComponent(r.style.backgroundImage || ''); } return ''; })()`);
  check('The Gear Customizer draws the same cog', !!cog && marginGear.includes(cog.d.slice(0, 120)), marginGear.slice(0, 160));
  const sb = await rect('#btn-settings');
  const idle = await ev(`getComputedStyle(document.querySelector('#btn-settings svg')).color`);
  await t.move(sb.x + sb.width / 2, sb.y + sb.height / 2);
  const hot = await ev(`getComputedStyle(document.querySelector('#btn-settings svg')).color`);
  check('Settings: the cog brightens on hover like the other buttons', hot !== idle, { idle, hot });
  await t.shot('ni_settings.png', { x: sb.x - 50, y: sb.y - 5, width: sb.width + 60, height: sb.height + 10 });
  await ev(`document.querySelector('#btn-settings').click(); 1`);
  check('Settings: clicking the cog opens Settings', await t.waitFor(`!document.querySelector('#settings').classList.contains('hidden')`, 5000));
};
