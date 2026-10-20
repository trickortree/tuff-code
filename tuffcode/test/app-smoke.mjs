// Starts a packaged TuffCode, drives its window over the DevTools protocol and checks that the
// IDE really comes up on this system: editor loaded, title bar right for the platform, icons
// drawn, agent detection working. Saves a screenshot. Exits 1 if any check fails.
// Usage: node test/app-smoke.mjs <TuffCode binary> <screenshot.png> [extra args for the app...]
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const [bin, shot = 'tuffcode-smoke.png', ...extra] = process.argv.slice(2);
const PORT = 9555;
const app = spawn(bin, [...extra, `--remote-debugging-port=${PORT}`], { stdio: ['ignore', 'pipe', 'pipe'] });
app.stdout.on('data', (d) => process.stdout.write(`[app] ${d}`));
app.stderr.on('data', (d) => process.stdout.write(`[app] ${d}`));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const check = (name, ok, got) => { results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `\n      got: ${JSON.stringify(got).slice(0, 400)}`}`); };

let page = null;
for (let i = 0; i < 90 && !page; i++) {
  await sleep(1000);
  try { page = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === 'page'); } catch {}
}
if (!page) { console.log('FAIL  the window never opened'); app.kill(); process.exit(1); }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0;
const waiting = new Map();
ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); waiting.get(m.id)?.(m); waiting.delete(m.id); });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const waitFor = async (expr, ms = 30000) => { const end = Date.now() + ms; while (Date.now() < end) { if (await ev(expr)) return true; await sleep(300); } return false; };

check('The IDE page loads', await waitFor(`document.readyState === 'complete' && !!document.querySelector('#titlebar')`, 60000), await ev('document.title'));
for (let i = 0; i < 20 && (await ev(`!!document.querySelector('.intro-cta')`)); i++) { await ev(`document.querySelector('.intro-cta')?.click()`); await sleep(700); }
await sleep(1500);
const platform = await ev('window.tuff.platform');
console.log(`platform: ${platform}, version: ${await ev('window.tuff.version?.()')}`);
check('The code editor loads', await waitFor(`!!document.querySelector('.monaco-editor')`, 30000), null);
if (platform === 'darwin') {
  check('Mac: the title bar makes room for the traffic lights and hides the Windows buttons', await ev(`document.documentElement.classList.contains('mac') && getComputedStyle(document.querySelector('.win-controls')).display === 'none'`), null);
}
if (platform !== 'win32') {
  const raw = await ev(`[...document.querySelectorAll('.fl')].filter((e) => /[\\uE000-\\uF8FF]/.test(e.textContent)).map((e) => e.parentElement?.id || e.className)`);
  check('Every Windows-font icon is replaced by a drawn one', Array.isArray(raw) && raw.length === 0, raw);
  check('No ".exe" wording on this system', await ev(`!document.body.innerText.includes('.exe')`), null);
}
const agents = await ev('window.tuff.agents.detect().then((a) => a.map((x) => x.id + ":" + x.installed))');
// At least these three: later versions may add more agents.
check('Agent detection runs (Claude Code, Codex, Antigravity and any others)', Array.isArray(agents) && agents.length >= 3 && ['claude', 'codex', 'antigravity'].every((id) => agents.some((a) => a.startsWith(`${id}:`))), agents);
const shotData = (await send('Page.captureScreenshot', { format: 'png' })).result?.data;
if (shotData) fs.writeFileSync(shot, Buffer.from(shotData, 'base64'));
check('Screenshot saved', !!shotData, null);

console.log(results.join('\n'));
ws.close();
app.kill();
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0);
