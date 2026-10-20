// Tuff Agents > Agent tools: the MCP check, connecting agents, the by-hand commands and "Test it".
// Uses only the stand-in agents; Antigravity is only looked at, never connected.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'Agent tools: the MCP check, connecting and Test it' };

const NL = '\n';

export default async (t, ctx) => {
  const check = t.check;
  const info = t.info;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 15000) => t.waitFor(js, ms);
  const click = (sel) => ev(`(() => { const b = document.querySelector(${JSON.stringify(sel)}); if (!b) return false; b.click(); return true; })()`);
  const text = (sel) => ev(`document.querySelector(${JSON.stringify(sel)})?.textContent.trim() ?? null`);
  const visible = (sel) => ev(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); return !!el && el.offsetParent !== null; })()`);
  const toastHas = (s) => waitFor(`[...document.querySelectorAll('.toast')].some(x => x.textContent.includes(${JSON.stringify(s)}))`, 20000);
  const state = (id) => text(`.tas-agent[data-id="${id}"] .tas-state`);
  const rect = (sel) => ev(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);

  fs.writeFileSync(path.join(ctx.root, 'main.tuf'), 'say "Hi"' + NL);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(path.join(ctx.root, 'main.tuf'))}); return 1; })()`);
  await ev(`(() => { window.TuffIDE.showSideView('plugins', true); return 1; })()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`);
  await click('.pl-card[data-id="tuff-agents"] [data-a="install"]');
  check('Tuff Agents installs and opens', await waitFor(`!!document.querySelector('.ta')`), null);
  await waitFor(`['claude', 'codex', 'antigravity'].every(id => document.querySelector('.ta-agents button[data-id="' + id + '"] .dot.ready'))`, 25000);

  // 1. ways in: the plug button, the Teach card, the menu, the empty chat
  check('The header has a plug button for Agent tools', await visible('.ta-top [data-a="setup"]'), null);
  await click('.ta-agents button[data-id="codex"]');
  check('Codex not connected: the Teach card has "How it works"', await waitFor(`/How it works/.test(document.querySelector('.ta-status')?.textContent || '')`, 10000), await text('.ta-status'));
  await click('.ta-status [data-a="setup"]');
  check('"How it works" opens Agent tools and hides the chat', (await visible('.ta-setup')) && !(await visible('.ta-compose')) && !(await visible('.ta-msgs')), null);

  // 2. the check runs by itself the first time
  const done = await waitFor(`document.querySelectorAll('.tas-steps li.ok, .tas-steps li.bad').length >= 6 || !!document.querySelector('.tas-steps li.bad')`, 60000);
  const steps = await ev(`[...document.querySelectorAll('.tas-steps li')].map(li => ({ ok: li.classList.contains('ok'), name: li.querySelector('b').textContent, detail: li.querySelector('span').textContent }))`);
  check('The check runs by itself and all its steps (at least 6) pass', done && steps.length >= 6 && steps.every((s) => s.ok), steps);
  const d = (re) => steps.find((s) => re.test(s.name))?.detail || '';
  check('Step details: the version, the 4 tools, the guide size and at least 8 examples',
    /TuffCode tools \d+\.\d+\.\d+/.test(d(/tools start up/)) && ['tuff_reference', 'tuff_examples', 'tuff_check', 'tuff_run'].every((n) => d(/Agents can see/).includes(n)) && /characters, \d+ sections/.test(d(/guide loads/)) && Number((/^(\d+) example apps/.exec(d(/example apps load/)) || [])[1]) >= 8, steps);
  check('Step details: the checker found the planted mistake, the runner printed Hi Sam!', /line 1/i.test(d(/checker spots/)) && /Hi Sam!/.test(d(/program runs/)), steps);
  check('It says everything works', /All good/.test(await text('.ta-setup .tas-ok') || ''), await text('.ta-setup section'));
  info('steps: ' + steps.map((s) => `${s.name}: ${s.detail}`).join(' | '));
  await t.shot('ms_check.png', await rect('#rightbar'));

  // 3. agents
  check('Claude: ready in this panel, with Test it and Add to terminal', /Ready in this panel/.test(await state('claude') || '') && !!(await text('.tas-agent[data-id="claude"] [data-s="test"]')) && !!(await text('.tas-agent[data-id="claude"] [data-s="on"]')), await state('claude'));
  check('Codex: not connected, with Connect', /Not connected/.test(await state('codex') || '') && !!(await text('.tas-agent[data-id="codex"] [data-s="on"]')), await state('codex'));
  info('Antigravity (stand-in, only looked at): ' + await state('antigravity'));

  // 4. by hand: open Codex's section, then connect Codex. The section must stay open.
  await ev(`(() => { const d = document.querySelector('details.tas-man[data-m="codex"]'); d.open = true; return 1; })()`);
  await t.sleep(200);
  await click('.tas-agent[data-id="codex"] [data-s="on"]');
  check('Connect: Codex shows Connected, with Test it and Remove', await waitFor(`/^Connected/.test(document.querySelector('.tas-agent[data-id="codex"] .tas-state')?.textContent || '') && !!document.querySelector('.tas-agent[data-id="codex"] [data-s="test"]')`, 20000), await state('codex'));
  check('The open Codex section stayed open after the screen updated', await ev(`document.querySelector('details.tas-man[data-m="codex"]').open`), null);
  const add = ctx.readLog('codex').find((l) => l.mcp && l.mcp[0] === 'add');
  const shown = await ev(`[...document.querySelectorAll('details.tas-man[data-m="codex"] .ta-cmd code')].map(c => c.textContent)`);
  info('Codex add command shown: ' + shown[0]);
  const strip = (s) => s.replace(/"/g, '');
  check('The by-hand Codex command is exactly what Connect ran', !!add && strip(shown[0] || '') === `codex mcp ${add.mcp.join(' ')}`, { shown: shown[0], ran: add?.mcp });
  check('...and "check they\'re there" is codex mcp get tuffcode', shown[1] === 'codex mcp get tuffcode', shown[1]);
  const json = await ev(`document.querySelector('details.tas-man[data-m="other"] .ta-cmd code').textContent`);
  let cfg = null;
  try { cfg = JSON.parse(json); } catch {}
  const srv = cfg?.mcpServers?.tuffcode;
  check('Other apps: valid JSON with TuffCode itself as the command, the server path and ELECTRON_RUN_AS_NODE', !!srv && ctx.samePath(srv.command, ctx.exe) && /tuff-mcp\.js$/.test(srv.args?.[0] || '') && srv.env?.ELECTRON_RUN_AS_NODE === '1' && fs.existsSync(srv.command) && fs.existsSync(srv.args[0]), { json, exe: ctx.exe });
  const claudeCmd = await ev(`document.querySelector('details.tas-man[data-m="claude"] .ta-cmd code').textContent`);
  check('Claude by hand: claude mcp add --scope user tuffcode -e ELECTRON_RUN_AS_NODE=1 -- <TuffCode> <tuff-mcp.js>', !!srv && strip(claudeCmd) === `claude mcp add --scope user tuffcode -e ELECTRON_RUN_AS_NODE=1 -- ${srv.command} ${srv.args[0]}`, claudeCmd);
  await click('details.tas-man[data-m="codex"] .ta-cmd button');
  check('Copy shows "Copied"', await toastHas('Copied. Paste it in a terminal.'), null);
  await t.shot('ms_agents.png', await rect('#rightbar'));

  // 5. Test it with Claude: keeps your draft, asks only (no edits, no file), reports the tools it used
  await click('.ta-setup [data-s="back"]');
  await ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = 'my draft'; return 1; })()`);
  await click('.ta-top [data-a="setup"]');
  await waitFor(`!!document.querySelector('.tas-agent[data-id="claude"] [data-s="test"]')`);
  const before = ctx.readLog('claude').length;
  await click('.tas-agent[data-id="claude"] [data-s="test"]');
  check('Test it goes back to the chat', await waitFor(`!document.querySelector('.ta-msgs').classList.contains('hidden')`, 5000), null);
  check('The chat shows "Test Claude Code\'s TuffCode tools"', await waitFor(`[...document.querySelectorAll('.ta-msg.user .ta-bubble')].some(b => b.textContent === "Test Claude Code's TuffCode tools")`, 5000), null);
  check('Test passed: Claude Code used tuff_reference', await toastHas('Test passed: Claude Code used tuff_reference.'), await ev(`[...document.querySelectorAll('.toast')].map(x => x.textContent)`));
  const run = ctx.readLog('claude').slice(before).find((l) => l.prompt);
  check('The test prompt asks only: no file, Ask permissions', !!run && run.prompt.includes('quick test of your TuffCode tools') && run.prompt.includes("Don't change any files") && !run.prompt.includes('Open file:') && run.args.includes('default') && !run.args.includes('acceptEdits'), run && { args: run.args, prompt: run.prompt.slice(0, 300) });
  check('Your draft in the message box is kept', (await ev(`document.querySelector('.ta textarea').value`)) === 'my draft', await ev(`document.querySelector('.ta textarea').value`));
  await click('.ta-top [data-a="setup"]');
  check('Agent tools shows the result under Claude', /Test passed: Claude Code used tuff_reference/.test(await text('.tas-agent[data-id="claude"] .tas-test') || ''), await text('.tas-agent[data-id="claude"]'));

  // 6. Test it with Codex (connected above)
  await click('.tas-agent[data-id="codex"] [data-s="test"]');
  check('Test passed: Codex used tuff_check', await toastHas('Test passed: Codex used tuff_check.'), await ev(`[...document.querySelectorAll('.toast')].map(x => x.textContent)`));

  // 7. menu entry, empty-chat link and Remove
  await ev(`(() => { document.querySelector('.ta [data-a="menu"]').click(); return 1; })()`);
  check('The ⋯ menu has "Agent tools: set up and check"', await waitFor(`[...document.querySelectorAll('.ta-menu button')].some(b => b.textContent === 'Agent tools: set up and check')`, 3000), await ev(`[...document.querySelectorAll('.ta-menu button')].map(b => b.textContent)`));
  await ev(`(() => { [...document.querySelectorAll('.ta-menu button')].find(b => b.dataset.m === 'new').click(); return 1; })()`);
  check('The empty chat links to Agent tools', await waitFor(`!!document.querySelector('.ta-empty [data-setup]')`, 3000), null);
  await click('.ta-empty [data-setup]');
  await waitFor(`!!document.querySelector('.tas-agent[data-id="codex"] [data-s="off"]')`);
  await click('.tas-agent[data-id="codex"] [data-s="off"]');
  check('Remove: Codex is Not connected again', await waitFor(`/Not connected/.test(document.querySelector('.tas-agent[data-id="codex"] .tas-state')?.textContent || '')`, 20000) && !fs.existsSync(path.join(ctx.agents, 'codex.connected')), await state('codex'));
  await click('.ta-setup [data-s="back"]');
  check('Back returns to the chat', (await visible('.ta-compose')) && !(await visible('.ta-setup')), null);
};
