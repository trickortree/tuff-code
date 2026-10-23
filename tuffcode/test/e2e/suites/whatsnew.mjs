// What's New: after an update TuffCode shows "Here's what's changed!" once, with that version's notes and pictures
// (rounded corners), and Help > What's New shows it again.
import fs from 'node:fs';

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

  // As if it had just updated from 1.1.0: the intro plays, then What's New opens.
  fs.writeFileSync(ctx.settingsFile, JSON.stringify({ ...settings(), introSeen: true, introVersion: '1.1.0', whatsNewSeen: undefined }, null, 2));
  await t.reload();
  const opened = await waitFor(`!!document.querySelector('#whatsnew.in')`, 30000);
  const b = await box();
  check(`After updating to ${version}, "Here's what's changed!" opens with the version and its notes`, opened && b?.title === "Here's what's changed!" && b.ver === `TuffCode ${version}` && b.body.length > 100, b);
  check('Its pictures (when it has any) load and have rounded corners', !!b && b.imgs.every((i) => parseFloat(i.radius) >= 8 && i.w > 0 && i.shown > 0), b?.imgs);
  await t.sleep(400);
  await t.shot('whatsnew.png');
  await ev(`document.querySelector('#whatsnew [data-a="close"]').click()`);
  await t.sleep(300);
  check('"Let\'s go" closes it, and it is remembered as seen', !(await box()) && settings().whatsNewSeen === version, settings().whatsNewSeen);

  await t.reload();
  await t.sleep(2500);
  check('Next time TuffCode opens, it doesn\'t show again', !(await box()), await box());

  // Help > What's New shows it any time; Escape closes it.
  await ev(`(() => { const h = [...document.querySelectorAll('.menu-root > button')].find((x) => x.textContent === 'Help'); h.click(); const item = [...document.querySelectorAll('.menu-root.open .mi')].find((m) => /What's New/.test(m.textContent)); item?.click(); return !!item; })()`);
  check("Help > What's New opens it again", await waitFor(`!!document.querySelector('#whatsnew.in')`, 3000), null);
  await t.key('Escape');
  await t.sleep(300);
  check('Escape closes it', !(await box()), null);
};
