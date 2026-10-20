// MANUAL: Tuff AI in the real IDE, with the real model. It needs the 1.3 GB model file, so it never runs on CI.
// It checks:
//   - the Tuff AI tab and a real answer whose code went through the checker;
//   - a fast follow-up;
//   - Explain on a Run error;
//   - Apply with one-step undo;
//   - the download card, which starts a download and stops it straight away.
// Stand-in agents and a scratch home are used, as in the mock suites.
// Usage: node test/e2e/manual/tuff-ai.mjs --model <Qwen3.5-2B-Q4_K_M.gguf> [--app <TuffCode binary>]
// A source checkout without node-llama-cpp installed can point TUFFCODE_LLAMA_RUNTIME at a separate install.
import fs from 'node:fs';
import path from 'node:path';
import { launch, context } from '../launch.mjs';
import { connect } from '../cdp.mjs';

const arg = (k) => (process.argv.indexOf(k) > 0 ? process.argv[process.argv.indexOf(k) + 1] : null);
const modelArg = arg('--model');
if (process.env.CI || !modelArg || !fs.existsSync(modelArg)) {
  console.error('Usage: node test/e2e/manual/tuff-ai.mjs --model <path to Qwen3.5-2B-Q4_K_M.gguf> [--app <TuffCode binary>]\n(Manual only: it needs the real model.)');
  process.exit(2);
}

let pass = 0, fail = 0;
const check = (name, ok, got) => { ok ? pass++ : fail++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '\n        got: ' + JSON.stringify(got)?.slice(0, 700)}`); };

const app = await launch({ name: 'tuff-ai', project: 'project', app: arg('--app'), env: process.env.TUFFCODE_LLAMA_RUNTIME ? { TUFFCODE_LLAMA_RUNTIME: process.env.TUFFCODE_LLAMA_RUNTIME } : {} });
process.on('SIGINT', async () => { await app.stop(); process.exit(130); });
const models = path.join(app.userData, 'models');
const model = path.join(models, path.basename(modelArg));
fs.mkdirSync(models, { recursive: true });
try { fs.linkSync(modelArg, model); } catch { fs.copyFileSync(modelArg, model); }
const broken = path.join(app.root, 'count.tuf');
fs.writeFileSync(broken, 'say "Counting to 3"\nfor n in range(1, 3)\n    say n\n');

let t;
try {
  t = await connect(app);
  await t.ready();
  const ctx = context(app);
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 250);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const idle = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`, 180000);
  const last = () => ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m ? { who: m.querySelector('.ta-who')?.textContent, text: m.querySelector('.ta-md')?.textContent, tools: [...m.querySelectorAll('.ta-tool')].map(x => x.className + ' ' + x.textContent), err: m.querySelector('.ta-err')?.textContent || '', apply: !!m.querySelector('[data-code="apply"]') } : null; })()`);
  const fileText = () => ev(`window.monaco?.editor.getModels().find(m => /count\\.tuf$/.test(m.uri.path))?.getValue()`);

  // Install Tuff Agents from the marketplace and open it on the Tuff AI tab, with count.tuf open.
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')?.click()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="tuffai"]')`, 20000);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(broken)}); return 1; })()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="tuffai"] .dot.ready, .ta-agents button[data-id="tuffai"] .dot.missing')`, 20000);
  await ev(`document.querySelector('.ta-agents button[data-id="tuffai"]').click()`);
  await t.sleep(500);
  check('Tuff AI has a tab, and with the model there, no download card', await ev(`!document.querySelector('.ta-status [data-a="ai-get"]')`), await ev(`document.querySelector('.ta-status')?.textContent`));

  const t0 = Date.now();
  await send('How do I show the text Hello on the screen in Tuff? Give a tiny program.');
  await idle();
  const a1 = await last();
  console.log(`      first answer: ${Date.now() - t0} ms`);
  check('Tuff AI answers, marked with its model', /Tuff AI · Qwen3\.5-2B/.test(a1?.who || '') && (a1?.text || '').length > 5 && !a1?.err, a1);
  check('Its code went through the checker, and has Apply', !/```/.test(a1?.text || '') || (a1?.tools.some((x) => /check/i.test(x)) && a1?.apply), a1);

  const t1 = Date.now();
  await send('What does round(2.5) give?');
  await idle();
  const ms = Date.now() - t1;
  check(`A follow-up is fast (${ms} ms)`, ms < 20000 && ((await last())?.text || '').length > 3, await last());

  await ev(`document.querySelector('#btn-run').click()`);
  const hasBtn = await waitFor(`!!document.querySelector('#run-output .explain-err')`, 30000);
  check('A Tuff error in the Run output has Explain', hasBtn, await ev(`document.querySelector('#run-output')?.textContent?.slice(0, 300)`));
  if (hasBtn) {
    const n = await ev(`document.querySelectorAll('.ta-msg.user').length`);
    await ev(`document.querySelector('#run-output .explain-err').click()`);
    await waitFor(`document.querySelectorAll('.ta-msg.user').length > ${n}`, 10000);
    await idle();
    const asked = await ev(`[...document.querySelectorAll('.ta-msg.user')].pop()?.textContent || ''`);
    check('Explain sends the error, and Tuff AI answers', /got this error/.test(asked) && /line 2/.test(asked) && ((await last())?.text || '').length > 10, { asked, a: await last() });
  }

  const before = await fileText();
  if (await ev(`(() => { const b = [...document.querySelectorAll('[data-code="apply"]')].pop(); b?.click(); return !!b; })()`)) {
    await waitFor(`!document.querySelector('#modal')?.classList.contains('hidden')`, 5000);
    await ev(`document.querySelector('#modal-ok').click()`);
    await t.sleep(600);
    const after = await fileText();
    await ev(`(() => { const e = window.monaco.editor.getEditors()[0]; e.focus(); e.trigger('test', 'undo'); return 1; })()`);
    await t.sleep(300);
    check('Apply replaces the file, and one undo brings it back', after !== before && (await fileText()) === before, { before, after });
  } else check('There was an Apply button', false, null);

  fs.renameSync(model, model + '.away');
  try {
    await ev(`(() => { document.querySelector('.ta-top [data-a="menu"]').click(); [...document.querySelectorAll('.ta-menu button')].find(b => /look for agents again/i.test(b.textContent))?.click(); return 1; })()`);
    const card = await waitFor(`!!document.querySelector('.ta-status [data-a="ai-get"]')`, 20000);
    const text = await ev(`document.querySelector('.ta-status')?.textContent || ''`);
    check('Without the model: a preview card with the download size and free memory', card && /1\.3 GB/.test(text) && /preview/i.test(text) && /free memory/.test(text), text);
    await ev(`document.querySelector('.ta-status [data-a="ai-get"]').click()`);
    check('The download shows progress', await waitFor(`/Downloading Tuff AI/.test(document.querySelector('.ta-status')?.textContent || '')`, 15000), await ev(`document.querySelector('.ta-status')?.textContent`));
    await t.sleep(1500);
    await ev(`document.querySelector('.ta-status [data-a="ai-cancel"]')?.click()`);
    check('Stop ends it and the card comes back', await waitFor(`!!document.querySelector('.ta-status [data-a="ai-get"]')`, 15000), await ev(`document.querySelector('.ta-status')?.textContent`));
  } finally {
    fs.renameSync(model + '.away', model);
  }
  const errs = (t.events || []).filter((e) => /exception|console.error/.test(e));
  check('No page errors', !errs.length, errs);
  void ctx;
} catch (err) {
  fail++;
  console.log(`FAIL  ${err.message}`);
} finally {
  t?.close?.();
  await app.stop();
}
console.log(`--- tuff-ai: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
