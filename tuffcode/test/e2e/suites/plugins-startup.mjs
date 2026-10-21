// Plugins don't wait for GitHub: the marketplace shows the list TuffCode comes with, and installed plugins
// (Tuff Agents) start, straight away, even when the online registry.json is slow or can't be reached. The
// online entries are added to the marketplace when they come. The online list comes from a web server
// started here (TUFFCODE_REGISTRY_URL), so nothing goes to GitHub.
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { launch, FIXTURES } from '../launch.mjs';
import { connect } from '../cdp.mjs';

const SLOW_MS = 5000; // the slow list comes after 5 s (TuffCode gives up after 6)
const ONLINE = { version: 1, plugins: [], newer: [{ id: 'e2e-online', name: 'Online Only', version: '1.0.0', author: 'e2e', description: 'Only in the online list.', source: 'https://raw.githubusercontent.com/trickortree/tuff-code/main/e2e-none/', files: ['plugin.json'] }] };
const asked = []; // every request the server got: its path
const server = http.createServer((req, res) => {
  asked.push(req.url);
  if (req.url.startsWith('/never/')) return; // never answers: like a network that hangs
  setTimeout(() => { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(ONLINE)); }, req.url.startsWith('/slow/') ? SLOW_MS : 0);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
server.unref();
const BASE = `http://127.0.0.1:${server.address().port}`;
// A port nobody listens on: like being offline.
const OFFLINE = await new Promise((r) => { const s = http.createServer(); s.listen(0, '127.0.0.1', () => { const { port } = s.address(); s.close(() => r(`http://127.0.0.1:${port}/registry.json`)); }); });

export const meta = { title: 'plugins start without waiting for the online marketplace', env: { TUFFCODE_REGISTRY_URL: `${BASE}/slow/registry.json` }, timeout: 240000 };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  try {
    // 1) The marketplace shows the list TuffCode comes with at once; the slow online one is still on its way
    await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
    const shown = await t.waitFor(`!!document.querySelector('.pl-card[data-id="snippets"]')`, 1000, 50);
    const ids = await ev(`[...document.querySelectorAll('.pl-card')].map(c => c.dataset.id)`);
    check('The marketplace shows the plugins TuffCode comes with straight away, while the online list is slow', shown && ['tuff-agents', 'snippets', 'api-explorer', 'sprite-studio', 'sound-lab'].every((id) => ids.includes(id)) && !ids.includes('e2e-online'), ids);
    // 2) ...and the online entries are added when they come, while the view is open
    const added = await t.waitFor(`!!document.querySelector('.pl-card[data-id="e2e-online"] [data-a="install"]')`, SLOW_MS + 4000, 100);
    check('The online entries show up in the open marketplace when they come', added, await ev(`[...document.querySelectorAll('.pl-card')].map(c => c.dataset.id)`));
    check('...from one request to the online list', asked.filter((u) => u.startsWith('/slow/')).length === 1, asked);

    // 3) Tuff Agents installed, the online list hangs or can't be reached: it is ready within 1 s of the IDE
    for (const [label, url] of [['slow (it never answers)', `${BASE}/never/registry.json`], ['offline', OFFLINE]]) {
      const scratch = fs.realpathSync.native(fs.mkdtempSync(path.join(os.tmpdir(), 'tuffcode-e2e-plstart-')));
      const root = path.join(scratch, 'project');
      fs.cpSync(path.join(FIXTURES, 'project'), root, { recursive: true });
      const userData = path.join(scratch, 'user-data');
      fs.mkdirSync(userData);
      fs.writeFileSync(path.join(userData, 'settings.json'), JSON.stringify({ introSeen: true, autoCheckUpdates: false, autoUpdate: false, lastFolder: root, plugins: { 'tuff-agents': { enabled: true, version: '1.0.0' } }, rightPanel: 'tuff-agents:chat' }, null, 2));
      // A second TuffCode with these settings: the last --user-data-dir wins over the one launch() makes.
      const app = await launch({ name: 'plugins-startup-2', env: { TUFFCODE_REGISTRY_URL: url }, args: [`--user-data-dir=${userData}`] });
      let t2;
      try {
        t2 = await connect(app);
        await t2.ready();
        const t0 = Date.now();
        const ready = await t2.waitFor(`window.TuffPluginHost.state().active.includes('tuff-agents') && !!document.querySelector('.ta textarea')`, 1000, 50);
        check(`With the online list ${label}, Tuff Agents is ready within 1 s of the IDE loading`, ready, await t2.eval(`window.TuffPluginHost.state()`));
        if (ready) t.info(`Tuff Agents was ready ${Date.now() - t0} ms after the IDE had loaded`);
        const cards = await t2.waitFor(`(() => { document.querySelector('.ts-btn[data-tool="plugins"]:not(.active)')?.click(); return !!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="toggle"]'); })()`, 1000, 50);
        check(`...and the marketplace shows it as installed straight away`, cards, await t2.eval(`[...document.querySelectorAll('.pl-card')].map(c => c.dataset.id)`));
        if (t2.events.length) t.info(`page errors in the second TuffCode: ${[...new Set(t2.events)].slice(0, 5).join(' | ')}`);
      } finally {
        t2?.close();
        await app.stop();
        try { fs.rmSync(scratch, { recursive: true, force: true, maxRetries: 20, retryDelay: 300 }); } catch {} // Windows can hold on to files for a moment
      }
    }
  } finally {
    server.closeAllConnections();
    server.close();
  }
};
