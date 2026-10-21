// MANUAL: screenshots of the Tuff Agents panel in its main states, for design review. Uses the stand-in
// agents, so nothing real is called. Saves PNGs to test/e2e/out/panel-shots/.
// Usage: node test/e2e/manual/panel-shots.mjs [--app <TuffCode binary>] [--theme light]
import fs from 'node:fs';
import path from 'node:path';
import { launch } from '../launch.mjs';
import { connect } from '../cdp.mjs';

const arg = (k) => (process.argv.indexOf(k) > 0 ? process.argv[process.argv.indexOf(k) + 1] : null);
const app = await launch({ name: 'panel-shots', project: 'project', app: arg('--app') });
const outDir = path.join(app.out, 'shots');
fs.mkdirSync(outDir, { recursive: true });
let t;
try {
  t = await connect(app);
  await t.ready();
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  if (arg('--theme')) await ev(`(() => { window.TuffIDE.setTheme?.(${JSON.stringify(arg('--theme'))}); return 1; })()`);
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')?.click()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"] .dot.ready')`, 20000);
  const files = await ev(`window.TuffIDE.listFiles().then(f => f.map(x => x.path))`);
  const tuf = files.find((f) => /\.tuf$/.test(f));
  if (tuf) await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(tuf)}); return 1; })()`);
  const shot = async (name) => {
    await t.sleep(400);
    await ev(`document.querySelectorAll(".toast").forEach((x) => x.remove()); 1`);
    const r = await ev(`(() => { const p = document.querySelector('.ta').closest('.rb-panel, .right-panel, #rightbar, aside') || document.querySelector('.ta'); const b = p.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; })()`);
    const res = await t.send('Page.captureScreenshot', { format: 'png', clip: { x: r.x, y: r.y, width: r.w, height: r.h, scale: 1 } });
    fs.writeFileSync(path.join(outDir, `${name}.png`), Buffer.from(res.data, 'base64'));
    console.log('saved', name);
  };
  const tab = (id) => ev(`document.querySelector('.ta-agents button[data-id="${id}"]').click()`);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const idle = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`, 30000);

  await tab('claude');
  await shot('1-empty');
  await send('Make my app look nicer');
  await t.sleep(300);
  await shot('2-thinking');
  await idle();
  await tab('codex');
  await send('what did claude change? show me the code');
  await idle();
  await shot('3-chat');
  await ev(`document.querySelector('.ta-msgs').scrollTop = 1e6`);
  await shot('4-chat-bottom');
  await tab('tuffai');
  await shot('5-tuffai-card');
  await ev(`document.querySelector('.ta-top [data-a="setup"]').click()`);
  await t.sleep(800);
  await shot('6-setup');
  console.log(outDir);
  console.log('page errors:', JSON.stringify((t.events || []).slice(0, 8), null, 1));
} finally {
  t?.close?.();
  await app.stop();
}
