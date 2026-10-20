// !!! MANUAL ONLY: REAL AGENTS, NO STAND-INS !!!
// Drives Tuff Agents with the real Claude Code, Codex and Antigravity on this PC, the way a person sees them.
// It sends real prompts on your real accounts (using your quota), and lets Antigravity make a file. It reads
// your real agents' sign-in, so unlike the mock suites it keeps your real home folder. It only ever opens a
// scratch copy of fixtures/project2, and stops if the IDE shows any other project.
// It is never run by run.mjs or CI, and refuses to start on CI or without the flag below.
// Usage: node test/e2e/manual/real-agents.mjs --yes-use-my-real-agents [--app <TuffCode binary>]
import fs from 'node:fs';
import path from 'node:path';
import { launch, context } from '../launch.mjs';
import { connect } from '../cdp.mjs';

if (process.env.CI || process.env.GITHUB_ACTIONS) {
  console.error('REFUSING TO RUN: real-agent tests are manual only and never run on CI.');
  process.exit(2);
}
if (!process.argv.includes('--yes-use-my-real-agents')) {
  console.error([
    '',
    '  !!! This test uses your REAL Claude Code, Codex and Antigravity. !!!',
    '  It sends real prompts on your accounts and lets Antigravity write a file in a scratch project.',
    '  To run it anyway: node test/e2e/manual/real-agents.mjs --yes-use-my-real-agents [--app <TuffCode binary>]',
    '  The mock suites (node test/e2e/run.mjs) test the same panel with stand-ins instead.',
    '',
  ].join('\n'));
  process.exit(2);
}
const appArg = process.argv.indexOf('--app') > 0 ? process.argv[process.argv.indexOf('--app') + 1] : null;

let pass = 0, fail = 0;
const check = (name, ok, got) => { ok ? pass++ : fail++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '\n        got: ' + JSON.stringify(got)?.slice(0, 700)}`); };

const app = await launch({ name: 'real-agents', project: 'project2', app: appArg, mocks: false });
process.on('SIGINT', async () => { await app.stop(); process.exit(130); });
let t;
try {
  t = await connect(app);
  await t.ready();
  const ctx = context(app);
  const proj = ctx.root;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 300);
  const choose = async (o, v) => {
    await ev(`document.querySelector('.ta-dd[data-o="${o}"] .ta-dd-btn').click()`);
    await ev(`document.querySelector('.ta-dd[data-o="${o}"] .ta-dd-opt[data-v="${v}"]').click()`);
  };
  const optNames = (o) => ev(`(() => { const b = document.querySelector('.ta-dd[data-o="${o}"] .ta-dd-btn'); b.click(); const n = [...document.querySelectorAll('.ta-dd[data-o="${o}"] .ta-dd-opt')].map(x => x.dataset.v + '=' + x.querySelector('b').textContent); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); return n; })()`);
  const tab = (id) => ev(`document.querySelector('.ta-agents button[data-id="${id}"]').click()`);
  const mode = (m) => ev(`document.querySelector('.ta-mode button[data-m="${m}"]').click()`);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const last = () => ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m ? { who: m.querySelector('.ta-who')?.textContent, text: m.querySelector('.ta-md')?.textContent, tools: [...m.querySelectorAll('.ta-tool')].map(x => x.className.replace('ta-tool', '').trim() + '|' + x.textContent.trim()), err: m.querySelector('.ta-err, .ta-error')?.textContent, typing: !!m.querySelector('.ta-typing') } : null; })()`);
  const reply = async (text, ms = 150000) => { await send(text); await t.sleep(800); await waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`, ms); return last(); };

  // The guard: only ever the scratch project.
  const openProj = await ev(`document.querySelector('#project-widget')?.textContent || ''`);
  const root = await ev('window.TuffIDE.root()');
  if (!/project2/.test(openProj) || !ctx.samePath(root, proj)) throw new Error(`ABORT: the open project is not the scratch project2 (${openProj.trim()} at ${root})`);

  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')?.click()`);
  await waitFor(`!!document.querySelector('.ta')`, 10000);
  await waitFor(`['claude', 'codex', 'antigravity'].every(id => document.querySelector('.ta-agents button[data-id="' + id + '"] .dot.ready'))`, 40000);
  const titles = await ev(`[...document.querySelectorAll('.ta-agents button')].map(b => b.dataset.title)`);
  check('Claude Code, Codex and Antigravity are all found', titles.length >= 3 && titles.every((x) => !/isn't installed/.test(x)), titles);

  await tab('claude');
  // Claude Code from the Claude app: either it asks you to sign in, or (once you have) it's ready.
  await t.sleep(4000);
  const claudeSignedIn = !/Sign in to Claude Code/.test(await ev(`document.querySelector('.ta-status')?.textContent || ''`));
  console.log(`(Claude Code is ${claudeSignedIn ? 'signed in' : 'not signed in'} on this PC)`);
  if (!claudeSignedIn) check('Claude (not signed in) shows "Sign in to Claude Code"', true, null);

  let cnames = [];
  for (let i = 0; i < 40 && !cnames.some((x) => x.startsWith('opus=')); i++) { cnames = await optNames('model'); await t.sleep(500); }
  check('Claude dropdown shows real names from your Claude Code (Opus 5.5…)', cnames.some((x) => /^opus=Opus \d/.test(x)) && cnames.some((x) => /^fable=Fable \d/.test(x)), cnames);

  // Codex
  await tab('codex');
  let cm = [];
  for (let i = 0; i < 60 && !cm.some((x) => x.startsWith('gpt-5.6-luna=')); i++) { cm = await optNames('model'); await t.sleep(500); }
  check("Codex's real model list shows", cm.length > 3, cm);
  await mode('ask');
  await choose('model', 'gpt-5.6-luna');
  await choose('effort', 'low');
  const c1 = await reply('Reply with the single word OK. Do not use any tools.');
  check('Codex answers through the panel (GPT-5.6-Luna, Low)', /\bOK\b/.test(c1?.text || '') && !c1?.err && /Luna · Low/.test(c1?.who || ''), c1);

  // Antigravity, Ask
  await tab('antigravity');
  for (let i = 0, got = []; i < 80 && !got.some((x) => /Flash/.test(x)); i++) { got = await optNames('model'); await t.sleep(500); }
  await choose('model', 'gemini-3.8-flash');
  await choose('effort', 'low');
  const a1 = await reply('Reply with the single word OK. Do not use any tools.');
  check('Antigravity answers through the panel', /\bOK\b/.test(a1?.text || '') && !a1?.err, a1);

  // Antigravity, Edit: the user's own kind of request
  await mode('edit');
  const a2 = await reply('Make a file called guiTest.tuf in this project containing exactly one line: say "hi"');
  const made = fs.existsSync(path.join(proj, 'guiTest.tuf')) ? fs.readFileSync(path.join(proj, 'guiTest.tuf'), 'utf8') : null;
  check('Antigravity in Edit mode makes guiTest.tuf', !!made && /say "hi"/.test(made) && !a2?.err, { a2, made });
  check('Its file step shows in the panel', (a2?.tools || []).some((x) => /guiTest\.tuf/.test(x)), a2?.tools);

  // Follow-up keeps the conversation
  await mode('ask');
  const a3 = await reply('What is the name of the file you just made? Answer with only the file name.');
  check('A follow-up continues the same Antigravity conversation', /guiTest\.tuf/i.test(a3?.text || ''), a3);
  const a4 = await reply('Call your call_mcp_tool tool with the MCP server "tuffcode" and its tool "tuff_check", passing file = guiTest.tuf. Do not run shell commands. Then tell me exactly what it returned.');
  check("Antigravity uses TuffCode's check tool from the panel (allowed, green step)", (a4?.tools || []).some((x) => /^ok|Checked .*for mistakes/.test(x)) && !(a4?.tools || []).some((x) => /tuff_check.json/.test(x)), a4);
  // Shared chat: Codex must not take Antigravity's replies for its own.
  await tab('codex');
  await choose('model', 'gpt-5.6-luna');
  await choose('effort', 'low');
  const c2 = await reply('Which AI agent wrote the reply just before this message of mine? Answer with just its name.');
  check("Codex knows the previous reply was Antigravity's, not its own", /antigravity/i.test(c2?.text || '') && !c2?.err, c2);

  // Real Claude Code, once it's signed in: answers, names the model it ran on, and knows who
  // wrote the previous reply (Codex) even though it resumes its own session.
  if (claudeSignedIn) {
    await tab('claude');
    await mode('ask');
    await choose('model', 'haiku');
    await choose('effort', 'low');
    const k1 = await reply('Reply with the single word OK. Do not use any tools.');
    check('Real Claude Code answers through the panel (Haiku, Low)', /\bOK\b/.test(k1?.text || '') && !k1?.err, k1);
    check('Its reply header names the model Claude Code really used', /Haiku \d/.test(k1?.who || ''), k1?.who);
    await tab('codex');
    const c3 = await reply('Reply with the single word PELICAN. Do not use any tools.');
    check('Codex answers again (PELICAN)', /PELICAN/i.test(c3?.text || ''), c3);
    await tab('claude');
    const k2 = await reply('What single word did Codex just reply with? Answer with just that word.');
    check('Claude Code, resuming its session, is caught up on what Codex said meanwhile', /PELICAN/i.test(k2?.text || '') && !k2?.err, k2);
  }
} catch (err) {
  fail++;
  console.log(`FAIL  stopped: ${err.message}`);
} finally {
  try { await t?.shot('end.png'); } catch {}
  t?.close();
  await app.stop();
}
console.log(`\nTOTAL: ${pass} passed, ${fail} failed (real agents)`);
process.exit(fail ? 1 : 0);
