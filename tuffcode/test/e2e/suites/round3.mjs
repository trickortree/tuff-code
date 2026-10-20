// Round 3: tab flash fix, centred icon buttons, logo, file icons, the 8th template and pages, Studio name tags.
// The window has to be drawing: CSS animations (and their events) don't run in a hidden window.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

export const meta = { title: 'round 3: tabs, icons, logo, templates and pages', platforms: ['win32'], why: 'Ctrl shortcuts in the editor, Cmd on a Mac' };

const NL = '\n';

export default async (t, ctx) => {
  const check = t.check;
  const info = t.info;
  const ev = (js) => t.eval(js);
  const P = (f) => path.join(ctx.root, f);
  const APP = (f) => path.join(ctx.appDir, f);
  const waitFor = (js, ms = 6000) => t.waitFor(js, ms, 120);
  const open = (p) => ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(p)}); return 1; })()`);
  const typeHuman = async (s) => { for (const ch of s) await t.type(ch, 70 + Math.floor(Math.random() * 41)); };
  const rect = (js) => ev(`(() => { const el = (${js}); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, left: r.left, top: r.top, width: r.width, height: r.height }; })()`);
  const clickEl = async (js) => { const r = await rect(js); if (!r || !r.width) return false; await t.click(r.x, r.y); return true; };
  const zoomShot = (file, c, scale) => t.shot(file, { x: c.x, y: c.y, width: c.width, height: c.height, scale });
  const val = async () => (await ev(`monaco.editor.getEditors()[0].getModel().getValue()`)).replace(/\r\n/g, NL);
  const modelOf = (p) => ev(`monaco.editor.getModel(monaco.Uri.file(${JSON.stringify(p)})).getValue()`);
  const tabOf = (p) => `[...document.querySelectorAll('#tabs .tab')].find(x => x.title === ${JSON.stringify(p)})`;
  const RUN = Date.now().toString(36);
  const TD = P('r3tabs');
  const meas = { x: new Map(), pa: new Map(), ff: new Map() };
  const measure = async () => {
    for (const [k, sel, text] of [['x', '.tab .x', false], ['pa', '.panel-actions button', false], ['ff', '.ff-opt', true]]) {
      for (const m of await ev(`window.__ctr(${JSON.stringify(sel)}, ${text})`)) if (!m.skip) meas[k].set(m.id, m);
    }
  };

  const vis = await ev(`document.visibilityState`);
  check('Precondition: the test window is visible (so CSS fades run)', vis === 'visible', vis);
  await ev(`window.TuffPluginHost && window.TuffPluginHost.closePanel && window.TuffPluginHost.closePanel(); 1`);
  // Centre-of-button vs centre-of-icon (svg) or centre-of-text (a Range over the button's text).
  await ev(`window.__ctr = (sel, text) => [...document.querySelectorAll(sel)].map((b) => {
    const tab = b.closest('.tab');
    const id = tab ? 'tab x: ' + tab.textContent.trim() : (b.id || b.title || b.className);
    const r = b.getBoundingClientRect();
    if (!r.width || !r.height) return { id: id, skip: true };
    let c = null;
    if (text) { const rg = document.createRange(); rg.selectNodeContents(b); c = rg.getBoundingClientRect(); }
    else { const s = b.querySelector('svg'); c = s ? s.getBoundingClientRect() : null; }
    if (!c || !c.width) return { id: id, skip: true };
    const q = (v) => Math.round(v * 1000) / 1000;
    return { id: id, dx: q(c.left + c.width / 2 - (r.left + r.width / 2)), dy: q(c.top + c.height / 2 - (r.top + r.height / 2)), btn: q(r.width) + 'x' + q(r.height), inner: q(c.width) + 'x' + q(c.height) };
  }); 1`);

  // ---------------------------------------------------------------- 1. file icons
  const ICONFILES = ['.env', '.env.local', 'config.ini', 'data.yml', 'notes.txt', 'pic.png', 'Makefile', '.gitignore', 'run.bat', 'tool.ps1', 'page.html', 'style.css', 'mystery.xyz', 'script.py', 'app.js', 'data.json', 'guide.md'];
  for (const f of ICONFILES) {
    if (fs.existsSync(P(f))) continue;
    if (f === 'pic.png') fs.copyFileSync(APP('renderer/assets/icon.png'), P(f));
    else fs.writeFileSync(P(f), '');
  }
  await ev(`window.TuffIDE.showSideView('project', true); 1`);
  await t.sleep(250);
  const refreshed = await clickEl(`document.querySelector('#tree-refresh')`);
  await t.sleep(800);
  const icons = await ev(`Object.fromEntries([...document.querySelectorAll('#tree .tree-row:not(.root)')].map(r => [r.querySelector('.name').textContent, r.querySelector('.fi') ? r.querySelector('.fi').outerHTML : null]))`);
  const I = (f) => icons[f] || '';
  const missing = [...ICONFILES, 'main.tuf'].filter((f) => !icons[f]);
  check('Refresh button shows every new file in the tree', refreshed && missing.length === 0, { refreshed, missing });
  const gear = I('.env');
  check('.env, .env.local, config.ini and data.yml share one icon (the gear)', !!gear && ['.env.local', 'config.ini', 'data.yml'].every((f) => I(f) === gear), { env: gear.slice(0, 160), envLocal: I('.env.local') === gear, ini: I('config.ini') === gear, yml: I('data.yml') === gear });
  const cats = { gear: '.env', picture: 'pic.png', M: 'Makefile', branch: '.gitignore', 'terminal bat': 'run.bat', 'terminal ps1': 'tool.ps1', '</>': 'page.html', '#': 'style.css', 'plain page': 'mystery.xyz' };
  const dup = [];
  const ks = Object.keys(cats);
  for (let i = 0; i < ks.length; i++) for (let j = i + 1; j < ks.length; j++) if (I(cats[ks[i]]) === I(cats[ks[j]])) dup.push(ks[i] + ' = ' + ks[j]);
  check('Gear, picture, M, branch, terminal (bat), terminal (ps1), </>, # and the plain page are 9 different icons', dup.length === 0 && ks.every((k) => I(cats[k])), dup);
  const hexes = (s) => [...s.matchAll(/#([0-9a-f]{6})/gi)].map((m) => [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)));
  const bat = hexes(I('run.bat')), ps1 = hexes(I('tool.ps1'));
  check('run.bat terminal is green, tool.ps1 terminal is blue', bat.length > 0 && bat.every(([r, g, b]) => g > r && g > b) && ps1.some(([r, g, b]) => b > r && b > g), { bat, ps1 });
  check('.tuf keeps its T icon', /var\(--accent\)/.test(I('main.tuf')) && /M5 5\.2h6M8 5\.2v6\.3/.test(I('main.tuf')), I('main.tuf'));
  const old = ['main.tuf', 'script.py', 'app.js', 'data.json', 'guide.md'].map(I);
  check('.tuf, .py, .js, .json and .md keep their own icons (all different, none is the plain page)', new Set(old).size === 5 && old.every((v) => v && v !== I('mystery.xyz')), old.map((v) => v.slice(0, 90)));
  info(`notes.txt icon is ${I('notes.txt') === I('mystery.xyz') ? 'the same plain page as unknown types' : 'a lined page, different from the plain page for unknown types'}`);
  const sbr = await rect(`document.querySelector('#sidebar')`);
  await zoomShot('r3_tree.png', { x: sbr.left, y: sbr.top, width: sbr.width, height: Math.min(sbr.height, 760) }, 2);

  // ---------------------------------------------------------------- 2. logo
  const logo = await ev(`(() => { const f = (i) => i && { src: i.src, attr: i.getAttribute('src'), complete: i.complete, nw: i.naturalWidth, nh: i.naturalHeight, shown: i.getBoundingClientRect().width + 'x' + i.getBoundingClientRect().height }; return { title: f(document.querySelector('#titlebar .app-logo')), empty: f(document.querySelector('#empty-state .es-logo')) }; })()`);
  check('Title bar logo (#titlebar .app-logo) is assets/icon.png, naturalWidth >= 256', !!logo.title && /\/assets\/icon\.png$/.test(logo.title.src) && logo.title.nw >= 256, logo.title);
  check('Empty-state logo (#empty-state .es-logo) is assets/icon.png, naturalWidth >= 256', !!logo.empty && /\/assets\/icon\.png$/.test(logo.empty.src) && logo.empty.nw >= 256, logo.empty);
  const tbr = await rect(`document.querySelector('#titlebar')`);
  await zoomShot('r3_titlebar.png', { x: 0, y: tbr.top, width: 420, height: tbr.height }, 3);
  const svg = await ev(`(async () => { const img = new Image(); img.src = 'assets/icon.svg'; try { await img.decode(); } catch (e) { return { err: String(e), nw: img.naturalWidth }; } return { nw: img.naturalWidth, nh: img.naturalHeight }; })()`);
  const dots = (fs.readFileSync(APP('renderer/assets/icon.svg'), 'utf8').match(/<circle\b/g) || []).length;
  check('assets/icon.svg decodes in an <img> (naturalWidth > 0); the file has 48 dots', svg.nw > 0 && !svg.err && dots === 48, { svg, dots });
  await ev(`(async () => { const img = new Image(); img.id = '__svgprev'; img.src = 'assets/icon.svg'; img.style.cssText = 'position:fixed;left:20px;top:60px;width:256px;height:256px;z-index:99999'; document.body.appendChild(img); await img.decode(); return 1; })()`);
  await t.sleep(150);
  await zoomShot('r3_icon_svg.png', { x: 20, y: 60, width: 256, height: 256 }, 1);
  await ev(`document.getElementById('__svgprev').remove(); 1`);

  // ---------------------------------------------------------------- 3. tab flash
  fs.mkdirSync(TD, { recursive: true });
  const TOKEN = `zap_${RUN}`, NEWTOK = `zop_${RUN}`;
  const tabFiles = [1, 2, 3, 4, 5, 6].map((i) => path.join(TD, `r3_${RUN}_${i}.tuf`));
  tabFiles.forEach((f, i) => fs.writeFileSync(f, `say "file ${i + 1}${i === 2 ? ' ' + TOKEN : ''}"` + NL));
  const closedTxt = path.join(TD, `r3_${RUN}_closed.txt`);
  fs.writeFileSync(closedTxt, `${TOKEN} in a closed file` + NL);
  for (const f of tabFiles.slice(0, 5)) { await open(f); await t.sleep(300); }
  await t.sleep(900);
  const setup = await ev(`(() => {
    window.__tabin = [];
    if (!window.__r3listen) {
      window.__r3listen = true;
      document.addEventListener('animationstart', (e) => {
        if (e.animationName !== 'tabin') return;
        const tab = e.target.closest ? e.target.closest('.tab') : null;
        window.__tabin.push(tab ? (tab.title || tab.textContent.trim()) : String(e.target.id || e.target.className));
      }, true);
    }
    window.__allTabs = [...document.querySelectorAll('#tabs .tab')];
    window.__tabEl = document.querySelector('#tabs .tab.active');
    return { n: window.__allTabs.length, active: window.__tabEl && window.__tabEl.title, enter: window.__allTabs.filter(x => x.classList.contains('enter')).length };
  })()`);
  check('5 fresh files are open as tabs (last one active, all fades finished)', setup.n >= 5 && setup.active === tabFiles[4] && setup.enter === 0, setup);
  const tabState = () => ev(`(() => { const now = [...document.querySelectorAll('#tabs .tab')]; const was = window.__allTabs; return { fades: window.__tabin.slice(), same: now.length === was.length && now.every((el, i) => el === was[i]), active: document.querySelector('#tabs .tab.active') === window.__tabEl && window.__tabEl.isConnected, dirty: window.__tabEl.classList.contains('dirty') }; })()`);

  await ev(`(() => { const e = monaco.editor.getEditors()[0]; const m = e.getModel(); const l = m.getLineCount(); e.setPosition({ lineNumber: l, column: m.getLineMaxColumn(l) }); e.focus(); })()`);
  await typeHuman('# abcdefgh');
  const s1 = await tabState();
  const v1 = await val();
  check('Typing 10 characters fires 0 tabin fades', s1.fades.length === 0, s1.fades);
  check('Typing keeps the same DOM element for the tab (and every other tab)', s1.active && s1.same, s1);
  check('Typing marks the tab dirty', s1.dirty && v1 === 'say "file 5"' + NL + '# abcdefgh', { s1, v1 });

  await t.key('S', 2);
  await t.sleep(500);
  const s2 = await tabState();
  const disk2 = fs.readFileSync(tabFiles[4], 'utf8').replace(/\r\n/g, NL);
  check('Ctrl+S clears dirty; still 0 fades and the same tab elements', !s2.dirty && s2.fades.length === 0 && s2.same && s2.active && disk2 === v1, { s2, disk2 });

  // undo back to the saved text (a cursor move first, so the new typing is its own undo step)
  await t.key('ArrowUp'); await t.key('ArrowDown'); await t.key('End');
  await typeHuman('klm');
  const s3a = await tabState();
  await t.key('Z', 2);
  await t.sleep(200);
  const s3 = await tabState();
  const v3 = await val();
  check('Type more, then Ctrl+Z back to the saved text: dirty goes away (0 fades, same elements)', s3a.dirty && v3 === v1 && !s3.dirty && s3.fades.length === 0 && s3.same, { s3a, s3, v3 });
  await t.key('Z', 2);
  await t.sleep(200);
  const s4a = await tabState(); const v4a = await val();
  await t.key('Z', 10);
  await t.sleep(200);
  const s4 = await tabState(); const v4 = await val();
  check('Undo past the save is dirty; redo (Ctrl+Shift+Z) back to the saved text is clean again', s4a.dirty && v4a !== v1 && !s4.dirty && v4 === v1 && s4.fades.length === 0 && s4.same, { s4a, v4a, s4, v4 });

  // observation: keep typing straight after a save, then Ctrl+Z
  await typeHuman('nop');
  await t.key('S', 2);
  await t.sleep(400);
  const savedNop = await val();
  await typeHuman('qrs');
  await t.key('Z', 2);
  await t.sleep(200);
  const v5 = await val(); const s5 = await tabState();
  info(`Save, keep typing on the same spot, Ctrl+Z: lands ${v5 === savedNop ? 'on the saved text' : 'PAST the saved text (' + JSON.stringify(v5.split(NL).pop()) + ' instead of ' + JSON.stringify(savedNop.split(NL).pop()) + ')'}; dirty=${s5.dirty}`);
  await t.key('S', 2);
  await t.sleep(400);

  // autosave
  await typeHuman('!');
  const s6a = await tabState();
  await t.sleep(2300);
  const s6 = await tabState();
  const disk6 = fs.readFileSync(tabFiles[4], 'utf8').replace(/\r\n/g, NL);
  check('Autosave (1.5 s after typing) clears dirty with 0 fades and the same tab elements', s6a.dirty && !s6.dirty && s6.fades.length === 0 && s6.same && disk6.endsWith('!'), { s6a, s6, tail: disk6.slice(-24) });

  // Find in Files: measure .ff-opt, then Replace all across an open tab and a closed file
  await t.key('F', 10);
  await t.sleep(500);
  const ffShown = await ev(`!document.querySelector('#view-find').classList.contains('hidden')`);
  await measure();
  await ev(`(() => { const i = document.querySelector('#ff-q'); i.value = ${JSON.stringify(TOKEN)}; i.dispatchEvent(new Event('input')); })()`);
  const found = await waitFor(`/^2 matches in 2 files/.test(document.querySelector('#ff-sum').textContent)`, 6000);
  await ev(`(() => { const i = document.querySelector('#ff-r'); i.value = ${JSON.stringify(NEWTOK)}; i.dispatchEvent(new Event('input')); })()`);
  await clickEl(`document.querySelector('#ff-replace')`);
  const modal = await waitFor(`!document.querySelector('#modal').classList.contains('hidden')`, 3000);
  await clickEl(`document.querySelector('#modal-ok')`);
  await t.sleep(1200);
  const s7 = await tabState();
  const m3 = await modelOf(tabFiles[2]);
  const d3 = fs.readFileSync(tabFiles[2], 'utf8'), dc = fs.readFileSync(closedTxt, 'utf8');
  const tab3dirty = await ev(`${tabOf(tabFiles[2])}.classList.contains('dirty')`);
  check('Replace all (one open tab + one closed file): 0 fades, every tab element kept, open tab saved', ffShown && found && modal && m3.includes(NEWTOK) && d3.includes(NEWTOK) && dc.includes(NEWTOK) && !tab3dirty && s7.fades.length === 0 && s7.same, { ffShown, found, modal, m3, d3, dc, tab3dirty, s7 });

  // agent reload: a file changes on disk, then the IDE reloads it the way Tuff Agents asks it to
  fs.writeFileSync(tabFiles[1], 'say "changed by an agent"' + NL);
  await ev(`(async () => { await window.TuffIDE.reloadChanged(); return 1; })()`);
  await t.sleep(500);
  const s8 = await tabState();
  const m2 = await modelOf(tabFiles[1]);
  const tab2dirty = await ev(`${tabOf(tabFiles[1])}.classList.contains('dirty')`);
  check('Agent reload (TuffIDE.reloadChanged) updates the open tab with 0 fades and the same elements', m2.includes('changed by an agent') && !tab2dirty && s8.fades.length === 0 && s8.same, { s8, m2, tab2dirty });

  // switching tabs rebuilds the bar but must not fade the existing tabs
  await ev(`window.__tabin = []; ${tabOf(tabFiles[3])}.scrollIntoView({ inline: 'nearest', block: 'nearest' }); 1`);
  await t.sleep(150);
  await clickEl(`${tabOf(tabFiles[3])}.querySelector('span')`);
  await t.sleep(600);
  const swi = await ev(`({ fades: window.__tabin.slice(), active: (document.querySelector('#tabs .tab.active') || {}).title })`);
  check('Clicking another tab switches to it with 0 fades', swi.active === tabFiles[3] && swi.fades.length === 0, swi);

  // a NEW file: exactly one fade, on that tab
  await ev(`window.__tabin = []; 1`);
  await open(tabFiles[5]);
  await t.sleep(800);
  const nf = await ev(`({ fades: window.__tabin.slice(), enter: [...document.querySelectorAll('#tabs .tab.enter')].map(x => x.title), n: document.querySelectorAll('#tabs .tab').length })`);
  check('Opening one NEW file fires exactly one tabin fade, for that tab only', nf.fades.length === 1 && nf.fades[0] === tabFiles[5], nf);
  check("The new tab drops its 'enter' class once the fade ends", nf.enter.length === 0, nf.enter);

  // ---------------------------------------------------------------- 4. centring + hover shot
  await ev(`window.TuffIDE.showSideView('project', true); 1`);
  await t.sleep(300);
  await measure();
  const xr = await rect(`document.querySelector('#tabs .tab.active .x')`);
  await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: xr.x, y: xr.y });
  await t.sleep(300);
  const hov = await ev(`document.querySelector('#tabs .tab.active .x').matches(':hover')`);
  const tr = await rect(`document.querySelector('#tabs .tab.active')`);
  await zoomShot('r3_tab_x_hover.png', { x: tr.left, y: tr.top, width: tr.width, height: tr.height }, 5);
  check('Mouse over the active tab X puts it in :hover (zoomed shot r3_tab_x_hover.png)', hov, hov);
  await t.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 700, y: 500 });
  // other panels: Learn, Plugins, bottom Run/Build, right-hand plugin panel
  for (const tool of ['learn', 'plugins']) {
    await clickEl(`document.querySelector('.ts-btn[data-tool="${tool}"]')`);
    await t.sleep(600);
    await measure();
  }
  // A fresh profile has no plugins: install Snippets, so a right-hand panel (and its hide button) is measured too.
  if (!(await ev(`!!document.querySelector('#toolstrip-right:not(.hidden) .ts-btn')`))) {
    await ev(`document.querySelector('.pl-card[data-id="snippets"] [data-a="install"]')?.click(); 1`);
    await waitFor(`!!document.querySelector('#toolstrip-right:not(.hidden) .ts-btn')`, 8000);
    await t.sleep(500);
    await ev(`window.TuffPluginHost.closePanel(); 1`);
    await t.sleep(300);
  }
  await ev(`window.TuffIDE.showSideView('project', true); 1`);
  const bottomShown = () => ev(`getComputedStyle(document.querySelector('#bottom-panel')).display !== 'none' && document.querySelector('#bottom-panel').getBoundingClientRect().height > 30`);
  if (!(await bottomShown())) await clickEl(`document.querySelector('.ts-btn[data-tool="run"]')`);
  await t.sleep(500);
  await measure();
  await clickEl(`document.querySelector('.bp-tab[data-tab="build"]')`);
  await t.sleep(300);
  await measure();
  await clickEl(`document.querySelector('.bp-tab[data-tab="run"]')`);
  await t.sleep(200);
  if (await bottomShown()) await clickEl(`document.querySelector('.ts-btn[data-tool="run"]')`);
  const rbBtn = await ev(`!!document.querySelector('#toolstrip-right:not(.hidden) .ts-btn')`);
  if (rbBtn) {
    await clickEl(`document.querySelector('#toolstrip-right .ts-btn')`);
    await waitFor(`!document.querySelector('#rightbar').classList.contains('hidden')`, 3000);
    await t.sleep(400);
    await measure();
    await clickEl(`document.querySelector('#rb-hide')`);
    await t.sleep(300);
  }
  const bad = (map) => [...map.values()].filter((m) => Math.abs(m.dx) > 0.5 || Math.abs(m.dy) > 0.5);
  const worst = (map) => [...map.values()].reduce((a, m) => Math.max(a, Math.abs(m.dx), Math.abs(m.dy)), 0);
  const PA = ['tree-new-file', 'tree-refresh', 'tree-collapse', 'sidebar-hide', 'ff-hide', 'learn-hide', 'pl-refresh', 'pl-hide', 'run-rerun', 'run-stop2', 'run-clear', 'build-again', 'build-cancel', 'bottom-hide', 'rb-hide'];
  const paMissing = PA.filter((id) => !meas.pa.has(id));
  check(`Every tab X (${meas.x.size} measured) is centred on its icon within 0.5px (worst ${worst(meas.x)}px)`, meas.x.size >= 6 && bad(meas.x).length === 0, { bad: bad(meas.x), sample: [...meas.x.values()].slice(0, 2) });
  check(`Every .panel-actions button (${meas.pa.size} measured) is centred on its icon within 0.5px (worst ${worst(meas.pa)}px)`, paMissing.length === 0 && bad(meas.pa).length === 0, { paMissing, bad: bad(meas.pa) });
  check(`Find in Files options (Aa, ab, .*) have their text centred within 0.5px (worst ${worst(meas.ff)}px)`, meas.ff.size === 3 && bad(meas.ff).length === 0, [...meas.ff.values()]);

  // ---------------------------------------------------------------- 5. Studio: templates, pages, name tags, full size
  await ev(`(async () => { await window.TuffIDE.openStudio(${JSON.stringify(P('main.tuf'))}); return 1; })()`);
  await t.sleep(1500);
  await clickEl(`document.querySelector('#sd-templates')`);
  await t.sleep(900);
  const cards = await ev(`[...document.querySelectorAll('.sd-tcard')].map(c => c.querySelector('b').textContent)`);
  check('Templates shows at least 8 cards, including "Pizza shop (pages)"', cards.length >= 8 && cards.includes('Pizza shop (pages)'), cards);
  const card = `[...document.querySelectorAll('.sd-tcard')].find(c => c.querySelector('b').textContent === 'Pizza shop (pages)')`;
  await ev(`${card}.scrollIntoView({ block: 'center' }); 1`);
  await t.sleep(300);
  await t.shot('r3_templates.png');
  const clickedNew = await clickEl(`${card}.querySelector('[data-a="new"]')`);
  let made = false;
  for (let i = 0; i < 50 && !made; i++) { made = fs.existsSync(P('shop.tuf')); if (!made) await t.sleep(100); }
  await t.sleep(1600);
  const tpl = { window: {} };
  vm.runInNewContext(fs.readFileSync(APP('renderer/js/tuff-templates.js'), 'utf8'), tpl);
  const want = tpl.window.TUFF_TEMPLATES.find((x) => x.id === 'shop').code;
  const disk = made ? fs.readFileSync(P('shop.tuf'), 'utf8') : '';
  const shopModel = made ? ((await ev(`(() => { const m = monaco.editor.getModel(monaco.Uri.file(${JSON.stringify(P('shop.tuf'))})); return m ? m.getValue() : null; })()`)) || '').replace(/\r\n/g, NL) : '';
  const pg = await ev(`({ file: (document.querySelector('#sd-file') || {}).value, pages: [...document.querySelectorAll('.sd-pg:not(.add)')].map(b => (b.classList.contains('on') ? '*' : '') + b.textContent.trim()), add: [...document.querySelectorAll('.sd-pg.add')].map(b => b.textContent.trim()) })`);
  check('"New file" makes shop.tuf (the template code, also in the Studio\'s model) and the Studio shows page tabs Home, Menu, Cart', clickedNew && made && disk === want && shopModel === want && /shop\.tuf$/.test(pg.file || '') && JSON.stringify(pg.pages.map((p) => p.replace('*', ''))) === '["Home","Menu","Cart"]', { clickedNew, made, diskIsTemplate: disk === want, modelIsTemplate: shopModel === want, pg });
  info(`page strip: ${JSON.stringify(pg.pages)} + ${JSON.stringify(pg.add)}`);
  await t.shot('r3_studio_pages.png');
  await clickEl(`[...document.querySelectorAll('.sd-pg')].find(b => b.textContent.trim() === 'Menu')`);
  await t.sleep(600);
  const menuShown = await ev(`({ on: (document.querySelector('.sd-pg.on') || {}).textContent, btns: [...document.querySelectorAll('#sd-stage .pv-btn')].map(b => b.textContent) })`);
  check('Clicking the Menu page tab shows the Menu page (Margherita / Pepperoni buttons)', /Menu/.test(menuShown.on || '') && menuShown.btns.some((b) => /Margherita/.test(b)) && menuShown.btns.some((b) => /Pepperoni/.test(b)), menuShown);
  await t.shot('r3_studio_menu.png');
  const tag = await ev(`(() => { const n = document.querySelector('#sd-stage .pv-node'); if (!n) return null; const cs = getComputedStyle(n, '::before'); return { fontSize: cs.fontSize, fontWeight: cs.fontWeight, content: cs.content, nodes: document.querySelectorAll('#sd-stage .pv-node').length }; })()`);
  check('Studio name tags (.pv-node::before) have font-size 11px', !!tag && tag.fontSize === '11px', tag);
  const tz = await ev(`(() => { const n = document.querySelector('#sd-stage .pv-node'); return { stageZoom: document.querySelector('#sd-stage').style.zoom, cssZoom: n ? n.currentCSSZoom : null }; })()`);
  info(`name tags sit inside the zoomed stage: Studio zoom ${tz.stageZoom}, so on screen they are about ${(11 * (tz.cssZoom || Number(tz.stageZoom) || 1)).toFixed(1)}px`);
  const pvlogo = await ev(`(() => { const i = document.querySelector('#sd-stage .pv-titlebar img'); return i && { src: i.src, nw: i.naturalWidth, complete: i.complete }; })()`);
  check('Studio preview title bar shows assets/icon.png', !!pvlogo && /\/assets\/icon\.png$/.test(pvlogo.src) && pvlogo.nw >= 256, pvlogo);
  await measure();
  const stx = [...meas.x.values()].find((m) => /Design Studio/.test(m.id));
  check('The Design Studio tab X is centred too', !!stx && Math.abs(stx.dx) <= 0.5 && Math.abs(stx.dy) <= 0.5, stx);
  const f11 = async () => {
    await t.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'F11', code: 'F11', windowsVirtualKeyCode: 122 });
    await t.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'F11', code: 'F11', windowsVirtualKeyCode: 122 });
    await t.sleep(600);
  };
  await ev(`document.querySelector('#sd-canvas').focus(); 1`);
  await f11();
  const full = await ev(`({ on: document.querySelector('#app').classList.contains('studio-full'), btn: document.querySelector('#sd-full').classList.contains('on'), side: getComputedStyle(document.querySelector('#sidebar')).display, tabs: getComputedStyle(document.querySelector('#tabs')).display, title: getComputedStyle(document.querySelector('#titlebar')).display })`);
  await t.shot('r3_full.png');
  await f11();
  const back = await ev(`!document.querySelector('#app').classList.contains('studio-full') && getComputedStyle(document.querySelector('#sidebar')).display !== 'none'`);
  check('F11 in the Studio turns Full size on (sidebar + tabs hidden, title bar kept) and off again', full.on && full.btn && full.side === 'none' && full.tabs === 'none' && full.title !== 'none' && back, { full, back });
};
