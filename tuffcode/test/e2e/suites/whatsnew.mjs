// What's New: after an update TuffCode shows "Here's what's changed!" once, with that version's notes and pictures
// (rounded corners), and Help > What's New shows it again. It's modal (Tab stays in it), and closing it gives the
// focus back, so typing goes into the code again.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: "What's New after an update" };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  const settings = () => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'));
  const version = await ev('window.tuff.version()');
  const box = () => ev(`(() => { const b = document.querySelector('#whatsnew'); if (!b) return null; const imgs = [...b.querySelectorAll('.wn-hero img')];
    return { title: b.querySelector('#wn-title')?.textContent, ver: b.querySelector('.wn-ver')?.textContent, body: b.querySelector('.wn-body')?.textContent || '',
      imgs: imgs.map((i) => ({ radius: getComputedStyle(i).borderRadius, w: i.naturalWidth, shown: i.getBoundingClientRect().width })) }; })()`);

  await t.sleep(1500);
  check('A copy that was never updated (no earlier version on record) shows no What\'s New', !(await box()), await box());

  // As if it had just updated from 1.1.0, with main.tuf open: the intro plays, then What's New opens.
  await ev(`window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'main.tuf'))}).then(() => 1)`);
  for (let i = 0; i < 30 && !(settings().openTabs || []).length; i++) await t.sleep(100);
  fs.writeFileSync(ctx.settingsFile, JSON.stringify({ ...settings(), introSeen: true, introVersion: '1.1.0', whatsNewSeen: undefined }, null, 2));
  await t.reload();
  const opened = await waitFor(`!!document.querySelector('#whatsnew.in')`, 30000);
  const b = await box();
  check(`After updating to ${version}, "Here's what's changed!" opens with the version and its notes`, opened && b?.title === "Here's what's changed!" && b.ver === `TuffCode ${version}` && b.body.length > 100, b);
  check('Its pictures (when it has any) load and have rounded corners', !!b && b.imgs.every((i) => parseFloat(i.radius) >= 8 && i.w > 0 && i.shown > 0), b?.imgs);
  await t.sleep(400);
  await t.shot('whatsnew.png');

  // One scroll area from the picture down (the scrollbar runs the whole height). Until the end, a fade and "Scroll for
  // more" show; at the end they go, and the end note is there. A picture of every scroll.
  const look = () => ev(`(() => { const c = document.querySelector('#whatsnew .wn-card'), s = c.querySelector('.wn-scroll');
    return { top: s.scrollTop, max: s.scrollHeight - s.clientHeight, end: c.classList.contains('at-end'), hint: getComputedStyle(c.querySelector('.wn-more')).opacity,
      fade: getComputedStyle(c.querySelector('.wn-fade')).opacity, heroInScroll: !!s.querySelector('.wn-hero') || !c.querySelector('.wn-hero'),
      note: c.querySelector('.wn-end')?.textContent.trim() || '' }; })()`);
  const card = await ev(`(() => { const r = document.querySelector('#whatsnew .wn-card').getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);
  const first = await look();
  check('The picture, title and notes scroll together, and it starts at the top', first.heroInScroll && first.top === 0, first);
  check('With more below, "Scroll for more" and the fade show', first.max > 0 && !first.end && first.hint === '1' && first.fade === '1', first);
  let n = 0;
  await ev(`document.querySelector('#whatsnew .wn-scroll').style.scrollBehavior = 'auto'; 1`);
  for (;;) {
    n++;
    await t.shot(`whatsnew_scroll_${n}.png`, card);
    const now = await look();
    if (now.end || n > 12) break;
    await ev(`(() => { const s = document.querySelector('#whatsnew .wn-scroll'); s.scrollTop += Math.round(s.clientHeight * 0.8); return 1; })()`);
    await t.sleep(450);
  }
  const last = await look();
  t.info(`${n} scroll pictures`);
  check('At the end, "Scroll for more" and the fade are gone, and the end note says that\'s everything', last.end && last.hint === '0' && last.fade === '0' && /That's everything new in TuffCode/.test(last.note), last);
  // It's modal: Tab and Shift+Tab go round its links and "Let's go", never to the IDE behind it.
  const focusIn = () => ev(`!!document.activeElement?.closest('#whatsnew')`);
  const tabs = [];
  for (let i = 0; i < 4; i++) { await t.key('Tab'); tabs.push(await focusIn()); }
  for (let i = 0; i < 4; i++) { await t.key('Tab', 8); tabs.push(await focusIn()); }
  check('Tab and Shift+Tab keep the focus inside What\'s New', tabs.every(Boolean), tabs);
  const editorFocus = () => ev(`(() => { const e = window.TuffIDE.editor(); return !!e && e.hasTextFocus(); })()`);
  const focusName = () => ev(`document.activeElement?.className || document.activeElement?.tagName`);
  await ev(`document.querySelector('#whatsnew [data-a="close"]').click()`);
  await t.sleep(300);
  check('"Let\'s go" closes it, and it is remembered as seen', !(await box()) && settings().whatsNewSeen === version, settings().whatsNewSeen);
  check('and the code editor has the focus again (the intro gave it the focus before What\'s New opened)', await editorFocus(), await focusName());

  await t.reload();
  await t.sleep(2500);
  check('Next time TuffCode opens, it doesn\'t show again', !(await box()), await box());

  // Help > What's New shows it any time; Escape closes it. (A click on the menu leaves the focus nowhere, on the page
  // itself: closing gives it to the code editor then.)
  await ev(`document.activeElement?.blur(); 1`);
  await ev(`(() => { const h = [...document.querySelectorAll('.menu-root > button')].find((x) => x.textContent === 'Help'); h.click(); const item = [...document.querySelectorAll('.menu-root.open .mi')].find((m) => /What's New/.test(m.textContent)); item?.click(); return !!item; })()`);
  check("Help > What's New opens it again", await waitFor(`!!document.querySelector('#whatsnew.in')`, 3000), null);
  await t.key('Escape');
  await t.sleep(300);
  check('Escape closes it', !(await box()), null);
  const codeBefore = await ev(`window.TuffIDE.editor().getValue()`);
  await t.type('#', 0);
  await t.sleep(200);
  const codeAfter = await ev(`window.TuffIDE.editor().getValue()`);
  check('and typing goes into the code editor again', await editorFocus() && codeAfter.length === codeBefore.length + 1 && codeAfter.includes('#'), { focus: await focusName(), typed: codeAfter.length - codeBefore.length });
  await ev(`window.TuffIDE.editor().trigger('test', 'undo', null); 1`);
};
