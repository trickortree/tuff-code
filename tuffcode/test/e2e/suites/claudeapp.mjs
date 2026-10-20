// "Add to the Claude app" adds TuffCode's tools to Claude Code AND the Claude app's own settings
// file (a scratch copy here), keeping everything else in it; Remove takes them out again.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'Add to the Claude app' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const cfgFile = path.join(ctx.agents, 'claude_desktop_config.json');
  const readCfg = () => { try { return JSON.parse(fs.readFileSync(cfgFile, 'utf8')); } catch { return null; } };
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  const state = () => ev(`document.querySelector('.tas-agent[data-id="claude"] .tas-state')?.textContent`);
  fs.writeFileSync(cfgFile, JSON.stringify({ preferences: { keepMe: true }, mcpServers: { other: { command: 'x' } } }));

  // Tuff Agents isn't installed in a fresh profile: install it, then open Agent tools.
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  await waitFor(`!!document.querySelector('.ta-top [data-a="setup"]')`);
  await ev(`document.querySelector('.ta-top [data-a="setup"]').click()`);
  check('Claude starts as "Ready in this panel" with "Add to the Claude app"', await waitFor(`/Ready in this panel/.test(document.querySelector('.tas-agent[data-id="claude"] .tas-state')?.textContent || '') && /Add to the Claude app/.test(document.querySelector('.tas-agent[data-id="claude"] [data-s="on"]')?.textContent || '')`), await state());
  await ev(`document.querySelector('.tas-agent[data-id="claude"] [data-s="on"]').click()`);
  const added = await waitFor(`/in the Claude app/.test(document.querySelector('.tas-agent[data-id="claude"] .tas-state')?.textContent || '')`);
  const cfg = readCfg();
  const s = cfg?.mcpServers?.tuffcode;
  check('Adding shows "Ready here, in the Claude app and the terminal"', added, await state());
  check('Claude app settings get a tuffcode server (TuffCode itself + tuff-mcp.js, Node mode)', !!s && ctx.samePath(s.command, ctx.exe) && /tuff-mcp\.js$/.test(s.args?.[0] || '') && s.env?.ELECTRON_RUN_AS_NODE === '1', { s, exe: ctx.exe });
  check('Everything else in the Claude app settings is kept', cfg?.preferences?.keepMe === true && cfg?.mcpServers?.other?.command === 'x', cfg);
  check('A backup of the old settings is saved once', fs.existsSync(`${cfgFile}.before-tuffcode`), null);
  await ev(`document.querySelector('.tas-agent[data-id="claude"] [data-s="off"]').click()`);
  const removed = await waitFor(`/Ready in this panel/.test(document.querySelector('.tas-agent[data-id="claude"] .tas-state')?.textContent || '')`);
  const after = readCfg();
  check('Remove takes tuffcode out and keeps the rest', removed && !after?.mcpServers?.tuffcode && after?.preferences?.keepMe === true && after?.mcpServers?.other?.command === 'x', after);
};
