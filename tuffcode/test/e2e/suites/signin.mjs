// Claude Code and Codex found but not signed in (the stand-ins run with MOCK_SIGNED_OUT=1): the panel asks
// to sign in instead of failing, chatting waits for it, and Agent tools shows it too. Sign in opens a real
// console window running the agent's own sign-in; the test closes it again (found by its scratch script path).
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'agents that are not signed in', env: { MOCK_SIGNED_OUT: '1' }, platforms: ['win32'], why: 'checks the Windows console window; a Mac opens Terminal instead' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  // The app's temp folder is a scratch one, so these scripts (and the windows running them) are only this run's.
  const script = (id) => path.join(ctx.tmp, `tuffcode-signin-${id}.cmd`);
  const readScript = (id) => { try { return fs.readFileSync(script(id), 'utf8'); } catch { return ''; } };
  const consoles = (id, then = '"$($_.ProcessId) $($_.CommandLine)"') => spawnSync('powershell', ['-NoProfile', '-Command',
    `Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains('${script(id).toLowerCase().replace(/'/g, "''")}') } | ForEach-Object { ${then} }`],
  { encoding: 'utf8', windowsHide: true }).stdout?.trim() || '';
  const closeConsoles = (id) => consoles(id, 'Stop-Process -Id $_.ProcessId -Force');
  const send = () => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = 'hello'; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);

  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"]')`);
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);
  check('Claude tab shows "Sign in to Claude Code"', await waitFor(`/Sign in to Claude Code/.test(document.querySelector('.ta-status')?.textContent || '')`), await ev(`document.querySelector('.ta-status')?.textContent`));
  await send();
  check('Sending waits for sign-in instead of failing', await waitFor(`[...document.querySelectorAll('.toast')].some(x => /Sign in to Claude Code first/.test(x.textContent))`, 5000), null);
  await ev(`document.querySelector('.ta-status [data-a="signin"]').click()`);
  check('Sign in opens Claude\'s own sign-in', await waitFor(`[...document.querySelectorAll('.toast')].some(x => /sign-in window opened/.test(x.textContent))`, 8000), null);
  await t.sleep(1500);
  const win = consoles('claude');
  check('A real console window runs "claude auth login"', /tuffcode-signin-claude\.cmd/.test(win) && /call ".*claude\.cmd" auth login/.test(readScript('claude')), win || readScript('claude'));
  closeConsoles('claude');
  await ev(`document.querySelector('.ta-top [data-a="setup"]').click()`);
  check('Agent tools shows Claude Code as Not signed in, with Sign in', await waitFor(`/Not signed in/.test(document.querySelector('.tas-agent[data-id="claude"] .tas-state')?.textContent || '') && !!document.querySelector('.tas-agent[data-id="claude"] [data-s="signin"]')`), await ev(`document.querySelector('.tas-agent[data-id="claude"]')?.textContent`));
  check('Agent tools shows Codex as Not signed in, with Sign in', await waitFor(`/Not signed in/.test(document.querySelector('.tas-agent[data-id="codex"] .tas-state')?.textContent || '') && !!document.querySelector('.tas-agent[data-id="codex"] [data-s="signin"]')`), await ev(`document.querySelector('.tas-agent[data-id="codex"]')?.textContent`));
  await ev(`document.querySelector('.tas-agent[data-id="codex"] [data-s="signin"]').click()`);
  await t.sleep(2000);
  const cwin = consoles('codex');
  check('Codex Sign in opens a console window running "codex login"', /tuffcode-signin-codex\.cmd/.test(cwin) && /call ".*codex\.cmd" login/.test(readScript('codex')), cwin || readScript('codex'));
  closeConsoles('codex');
  await ev(`document.querySelector('.tas [data-s="back"]')?.click()`);
  await ev(`document.querySelector('.ta-agents button[data-id="codex"]').click()`);
  check('Codex tab shows "Sign in to Codex"', await waitFor(`/Sign in to Codex/.test(document.querySelector('.ta-status')?.textContent || '')`), await ev(`document.querySelector('.ta-status')?.textContent`));
  await send();
  check('Sending to Codex waits for sign-in', await waitFor(`[...document.querySelectorAll('.toast')].some(x => /Sign in to Codex first/.test(x.textContent))`, 5000), null);
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);
};
