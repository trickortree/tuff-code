// Plugins and Tuff Agents with the stand-in agents: the marketplace, installing, connecting Codex, Ask and
// Edit mode with Claude, resuming, Stop, a Codex run, the Snippets plugin, turning off/on and uninstalling.
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'Plugins and Tuff Agents (stand-in agents)' };

const MAIN = `mention mtgui

app = mtgui.window("Hello")
app:heading "Hi there!"
`;

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const main = JSON.stringify(path.join(ctx.root, 'main.tuf'));
  const waitFor = (js, ms = 15000) => t.waitFor(js, ms);
  const clickText = (sel, text) => ev(`(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find(x => x.textContent.trim() === ${JSON.stringify(text)}); if (!b) return false; b.click(); return true; })()`);
  const card = (id) => `document.querySelector('.pl-card[data-id="${id}"]')`;
  const send = async (text) => {
    await ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); })()`);
  };
  const lastAgentDone = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`, 20000);
  const lastRun = (who) => ctx.readLog(who).filter((l) => l.prompt).pop() || {};

  fs.writeFileSync(path.join(ctx.root, 'main.tuf'), MAIN);
  await ev(`(async () => { await window.TuffIDE.openFile(${main}); return 1; })()`);
  await t.sleep(400);

  // 1. marketplace
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await t.sleep(600);
  const ids = await ev(`[...document.querySelectorAll('.pl-card')].map(c => c.dataset.id)`);
  check('Plugins view shows the marketplace with Tuff Agents and Snippets', ids.includes('tuff-agents') && ids.includes('snippets') && (await ev(`!document.querySelector('#view-plugins').classList.contains('hidden')`)), ids);
  await t.shot('p_market.png');

  // 2. install Tuff Agents -> right panel opens
  await ev(`${card('tuff-agents')}.querySelector('[data-a="install"]').click()`);
  const opened = await waitFor(`!document.querySelector('#rightbar').classList.contains('hidden') && !!document.querySelector('.ta')`);
  check('Installing Tuff Agents opens its panel on the right', opened && (await ev(`document.querySelectorAll('#toolstrip-right .ts-btn').length`)) === 1, await ev(`window.TuffPluginHost.state()`));

  // 3. the three stand-in agents are found
  const found = await waitFor(`['claude', 'codex', 'antigravity'].every(id => document.querySelector('.ta-agents button[data-id="' + id + '"] .dot.ready'))`, 25000);
  check('Claude Code, Codex and Antigravity show as installed (green dots)', found, await ev(`[...document.querySelectorAll('.ta-agents button')].map(b => b.textContent + ':' + b.querySelector('.dot').className)`));
  await t.shot('p_agents.png');

  // 4. Codex not connected -> Connect card -> connect
  await clickText('.ta-agents button', 'Codex');
  const cardShown = await waitFor(`/Teach Codex about Tuff/.test(document.querySelector('.ta-status').textContent)`, 8000);
  await ev(`document.querySelector('.ta-status [data-a="connect"]').click()`);
  const connected = await waitFor(`!/Teach Codex/.test(document.querySelector('.ta-status').textContent)`, 15000);
  const add = ctx.readLog('codex').find((l) => l.mcp && l.mcp[0] === 'add');
  check('Codex: "Connect" adds the tuffcode MCP server (codex mcp add)', cardShown && connected && add && add.mcp.includes('tuffcode') && add.mcp.includes('ELECTRON_RUN_AS_NODE=1') && add.mcp.some((a) => /tuff-mcp\.js$/.test(a)), add);

  // 5. Claude, Ask mode
  await clickText('.ta-agents button', 'Claude');
  await t.sleep(300);
  await send('Make my greeting friendlier');
  await lastAgentDone();
  const claude1 = lastRun('claude');
  const a = claude1.args || [];
  check('Claude runs headless with stream-json, the TuffCode MCP config and Ask permissions',
    a.includes('-p') && a.includes('stream-json') && a.includes('--verbose') && a.includes('--mcp-config') && a[a.indexOf('--allowedTools') + 1] === 'mcp__tuffcode' && a[a.indexOf('--permission-mode') + 1] === 'default', a);
  check('The prompt carries the open file and the question (sent through stdin)', /Open file: main\.tuf/.test(claude1.prompt) && /app:heading "Hi there!"/.test(claude1.prompt) && /Make my greeting friendlier/.test(claude1.prompt) && /Don't change any files/.test(claude1.prompt), (claude1.prompt || '').slice(0, 500));
  check('The agent runs in the project folder', ctx.samePath(claude1.cwd, ctx.root), { cwd: claude1.cwd, root: ctx.root });
  const msg = await ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return { html: m.innerHTML.slice(0, 900), tools: [...m.querySelectorAll('.ta-tool')].map(x => x.className + '|' + x.textContent), code: m.querySelector('.ta-code code')?.textContent, bold: m.querySelector('.ta-md b')?.textContent, li: m.querySelectorAll('.ta-md li').length }; })()`);
  check('Reply streams in with tool steps, a code block, bold and a list', msg.tools.length === 2 && /ok\|Read the Tuff guide/.test(msg.tools[0]) && /ok\|Read main\.tuf/.test(msg.tools[1]) && msg.code === 'say "Hi there!"' && msg.bold === 'friendlier' && msg.li === 2, msg);
  await t.shot('p_chat.png');

  // 6. Insert the code block into the editor
  await ev(`(() => { const e = monaco.editor.getEditors()[0]; const m = e.getModel(); e.setPosition({ lineNumber: m.getLineCount(), column: m.getLineMaxColumn(m.getLineCount()) }); })()`);
  await ev(`[...document.querySelectorAll('.ta-msg.agent')].pop().querySelector('[data-code="insert"]').click()`);
  await t.sleep(300);
  check('"Insert" puts the agent\'s code into the editor', (await ev(`monaco.editor.getEditors()[0].getModel().getValue()`)).includes('say "Hi there!"'), null);
  await ev(`monaco.editor.getEditors()[0].trigger('t', 'undo')`);
  await ev(`(async () => { await window.TuffIDE.openFile(${main}); return 1; })()`);

  // 7. second message resumes the Claude session
  await send('Thanks!');
  await lastAgentDone();
  check('A follow-up resumes the same Claude session (--resume)', (lastRun('claude').args || []).join(' ').includes('--resume sess-123'), lastRun('claude').args);

  // 8. Edit mode: the agent changes main.tuf, the open tab reloads
  await clickText('.ta-mode button', 'Edit');
  await send('Add a goodbye line');
  await lastAgentDone();
  const claude3 = lastRun('claude');
  await t.sleep(800);
  const editorCode = await ev(`(async () => (await window.TuffIDE.getModel(${main})).getValue())()`);
  check('Edit mode uses acceptEdits, and the changed file reloads in the editor', (claude3.args || []).includes('acceptEdits') && /added by the agent/.test(editorCode) && /You may change files/.test(claude3.prompt), { args: claude3.args, editorCode });
  await clickText('.ta-mode button', 'Ask');

  // 9. Stop a slow run
  await send('SLOW please');
  await t.sleep(1500);
  await ev(`document.querySelector('.ta-send').click()`);
  await t.sleep(800);
  const stopped = await ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return /Stopped/.test(m.textContent) && document.querySelector('.ta-send').textContent === 'Send'; })()`);
  check('Stop ends a running agent', stopped, await ev(`[...document.querySelectorAll('.ta-msg.agent')].pop().textContent.slice(-200)`));

  // 10. Codex run
  await clickText('.ta-agents button', 'Codex');
  await send('Is my code ok?');
  await lastAgentDone();
  const codex = lastRun('codex');
  const cm = await ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return { text: m.querySelector('.ta-md').textContent, tools: [...m.querySelectorAll('.ta-tool')].map(x => x.className + '|' + x.textContent) }; })()`);
  check('Codex runs "exec --json" read-only with the prompt on stdin', ['exec', '--json', '--skip-git-repo-check', '--sandbox', 'read-only', '-'].every((x) => (codex.args || []).includes(x)) && /Is my code ok\?/.test(codex.prompt || ''), codex.args);
  check('Codex reply and steps show (check passed, failed command marked)', /Codex says: your code looks fine\./.test(cm.text) && /ok\|Checked main\.tuf for mistakes/.test(cm.tools[0] || '') && /bad\|Ran py tuff\.py main\.tuf/.test(cm.tools[1] || ''), cm);
  await t.shot('p_codex.png');

  // 11. Snippets plugin
  await ev(`${card('snippets')}.querySelector('[data-a="install"]').click()`);
  const snip = await waitFor(`!!document.querySelector('.sn-item')`);
  await ev(`(() => { const e = monaco.editor.getEditors()[0]; const m = e.getModel(); e.setPosition({ lineNumber: m.getLineCount(), column: m.getLineMaxColumn(m.getLineCount()) }); })()`);
  await ev(`[...document.querySelectorAll('.sn-item')].find(i => i.querySelector('b').textContent === 'Say hello').querySelector('[data-a="insert"]').click()`);
  await t.sleep(300);
  check('Snippets: Insert puts "Say hello" in the editor', snip && (await ev(`monaco.editor.getEditors()[0].getModel().getValue()`)).includes('say "Hello, world!"'), null);
  await t.shot('p_snippets.png');
  await ev(`monaco.editor.getEditors()[0].trigger('t', 'undo')`);

  // 12. turn off / on / uninstall
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').classList.contains('active') || document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await t.sleep(300);
  await ev(`${card('snippets')}.querySelector('[data-a="toggle"]').click()`);
  await t.sleep(700);
  const offCount = await ev(`document.querySelectorAll('#toolstrip-right .ts-btn').length`);
  await ev(`${card('snippets')}.querySelector('[data-a="toggle"]').click()`);
  await t.sleep(700);
  const onCount = await ev(`document.querySelectorAll('#toolstrip-right .ts-btn').length`);
  check('Turning a plugin off removes its panel, on brings it back', offCount === 1 && onCount === 2, { offCount, onCount });

  // 13. survives a reload
  await t.reload();
  const st = await ev(`window.TuffPluginHost.state()`);
  check('Installed plugins come back after restarting', st.active.includes('tuff-agents') && st.active.includes('snippets') && st.panels.length === 2, st);

  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await t.sleep(400);
  await ev(`${card('snippets')}.querySelector('[data-a="uninstall"]').click()`);
  await t.sleep(400);
  await ev(`document.querySelector('#modal-ok').click()`);
  await t.sleep(800);
  check('Uninstall removes the plugin', !(await ev(`window.TuffPluginHost.state()`)).active.includes('snippets') && (await ev(`!!${card('snippets')}.querySelector('[data-a="install"]')`)), await ev(`window.TuffPluginHost.state()`));
};
