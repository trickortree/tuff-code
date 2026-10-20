// Model and Thinking dropdowns: filled from each agent's own list with real model names, passed to
// the run, remembered, usable from the keyboard, and locked (with the agent tabs) during a reply.
export const meta = { title: 'Model and Thinking dropdowns' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  const dd = (o) => `document.querySelector('.ta-dd[data-o="${o}"]')`;
  const opts = async (o) => {
    await ev(`${dd(o)}.querySelector('.ta-dd-btn').click()`);
    const list = await ev(`[...${dd(o)}.querySelectorAll('.ta-dd-opt')].map(x => x.dataset.v + '=' + x.querySelector('b').textContent)`);
    await ev(`document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))`);
    return list;
  };
  const choose = async (o, v) => {
    await ev(`${dd(o)}.querySelector('.ta-dd-btn').click()`);
    await ev(`${dd(o)}.querySelector('.ta-dd-opt[data-v="${v}"]').click()`);
  };
  const shown = (o) => ev(`${dd(o)}.querySelector('.ta-dd-v').textContent`);
  const tab = (id) => ev(`document.querySelector('.ta-agents button[data-id="${id}"]').click()`);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const idle = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`);
  const who = () => ev(`[...document.querySelectorAll('.ta-msg.agent .ta-who')].pop()?.textContent`);
  const ensurePanel = async () => {
    if (!(await ev(`!![...document.querySelectorAll('#toolstrip-right .ts-btn')].find(b => b.title === 'Tuff Agents')`))) {
      await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
      await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
      await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')?.click()`);
      await waitFor(`!!document.querySelector('.ta')`, 10000);
    }
    await ev(`(() => { const b = [...document.querySelectorAll('#toolstrip-right .ts-btn')].find(b => b.title === 'Tuff Agents'); if (b && !b.classList.contains('active')) b.click(); return 1; })()`);
  };

  await ensurePanel();
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"]')`);
  await tab('claude');
  await waitFor(`!${dd('model')}.querySelector('.ta-dd-btn').disabled`);
  await choose('model', ''); await choose('effort', '');
  const cm = await opts('model');
  check('Claude: real model names from Claude Code (Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5)', JSON.stringify(cm) === JSON.stringify(['=Default', 'fable=Fable 5.1', 'opus=Opus 5.5', 'sonnet=Sonnet 5.5', 'haiku=Haiku 5.5']), cm);
  check('Each model has a short description', await ev(`(() => { ${dd('model')}.querySelector('.ta-dd-btn').click(); const subs = [...${dd('model')}.querySelectorAll('.ta-dd-opt small')].map(x => x.textContent); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); return subs.length === 5 && subs.every(Boolean); })()`), null);
  const ce = await opts('effort');
  check('Claude: thinking levels from Claude Code', JSON.stringify(ce) === JSON.stringify(['=Default', 'low=Low', 'medium=Medium', 'high=High', 'xhigh=Extra high', 'max=Max']), ce);

  await send('hello on default');
  await idle();
  check('After a Default reply, the button names the model that answered (Default · Opus 5.5)', /Default · Opus 5\.5/.test(await shown('model')), await shown('model'));
  check('…and so does the reply header', /Opus 5\.5/.test(await who()), await who());

  await ev(`${dd('model')}.querySelector('.ta-dd-btn').focus()`);
  const key = (k) => ev(`${dd('model')}.querySelector('.ta-dd-btn').dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(k)}, bubbles: true }))`);
  await key('ArrowDown');
  check('Keyboard: Arrow Down opens the menu', await ev(`!${dd('model')}.querySelector('.ta-dd-menu').classList.contains('hidden')`), null);
  await key('ArrowDown'); await key('ArrowDown'); await key('Enter');
  check('Keyboard: arrows and Enter pick Opus 5.5', (await shown('model')) === 'Opus 5.5', await shown('model'));
  await key('ArrowDown'); await key('Escape');
  check('Keyboard: Esc closes the menu', await ev(`${dd('model')}.querySelector('.ta-dd-menu').classList.contains('hidden')`), null);

  await choose('effort', 'high');
  await send('hello with opus');
  await idle();
  const ca = ctx.readLog('claude').filter((l) => l.prompt).pop()?.args || [];
  check('Claude run gets --model opus --effort high', ca[ca.indexOf('--model') + 1] === 'opus' && ca[ca.indexOf('--effort') + 1] === 'high', ca);
  check('The reply says which model and level answered', /Opus 5\.5 · High/.test(await who()), await who());

  await send('SLOW please');
  await waitFor(`document.querySelector('.ta-send').classList.contains('stop')`, 5000);
  await t.sleep(400);
  const locked = await ev(`({ codex: document.querySelector('.ta-agents button[data-id="codex"]').disabled, claude: document.querySelector('.ta-agents button[data-id="claude"]').disabled, model: ${dd('model')}.querySelector('.ta-dd-btn').disabled, effort: ${dd('effort')}.querySelector('.ta-dd-btn').disabled })`);
  check('While it is answering, the other agents and both dropdowns are locked', locked.codex && !locked.claude && locked.model && locked.effort, locked);
  await ev(`${dd('model')}.querySelector('.ta-dd-btn').click()`);
  check('A locked dropdown does not open', await ev(`${dd('model')}.querySelector('.ta-dd-menu').classList.contains('hidden')`), null);
  await ev(`document.querySelector('.ta-send').click()`);
  await waitFor(`!document.querySelector('.ta-send').classList.contains('stop')`, 5000);
  check('After Stop everything unlocks', await ev(`!${dd('model')}.querySelector('.ta-dd-btn').disabled && !document.querySelector('.ta-agents button[data-id="codex"]').disabled`), null);

  await tab('codex');
  await waitFor(`${dd('model')}.querySelector('.ta-dd-v').textContent !== 'Loading…'`);
  const xm = await opts('model');
  check('Codex: models from its own catalog, hidden ones left out', JSON.stringify(xm) === JSON.stringify(['=Default', 'gpt-mock-sol=GPT-Mock-Sol', 'gpt-mock-luna=GPT-Mock-Luna']), xm);
  await choose('model', 'gpt-mock-sol');
  const xe = await opts('effort');
  check("Codex: thinking levels are that model's, and Default names its default", JSON.stringify(xe) === JSON.stringify(['=Default (Medium)', 'low=Low', 'medium=Medium', 'high=High', 'ultra=Ultra']), xe);
  await choose('effort', 'ultra');
  await choose('model', 'gpt-mock-luna');
  check('Switching to a model without that level falls back to its Default', /^Default/.test(await shown('effort')), await shown('effort'));
  await choose('effort', 'medium');
  await send('hello codex');
  await idle();
  const xa = ctx.readLog('codex').filter((l) => l.prompt !== undefined && l.args?.[0] === 'exec').pop()?.args || [];
  check('Codex run gets -m gpt-mock-luna -c model_reasoning_effort=medium', xa[xa.indexOf('-m') + 1] === 'gpt-mock-luna' && xa[xa.indexOf('-c') + 1] === 'model_reasoning_effort=medium', xa);

  await tab('antigravity');
  check('Antigravity: agy lists its models (Gemini…)', await waitFor(`(() => { ${dd('model')}.querySelector('.ta-dd-btn').click(); const ok = [...${dd('model')}.querySelectorAll('.ta-dd-opt b')].some(o => /Gemini/.test(o.textContent)); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); return ok; })()`, 30000), null);

  await t.reload();
  await ensurePanel();
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"]')`);
  await tab('claude');
  await waitFor(`${dd('model')}.querySelector('.ta-dd-v').textContent !== 'Loading…'`);
  const kept = [await shown('model'), await shown('effort')];
  check('Choices are remembered per agent after a restart', kept[0] === 'Opus 5.5' && kept[1] === 'High', kept);
  await ev(`${dd('model')}.querySelector('.ta-dd-btn').click()`);
  await t.sleep(250);
  await t.shot('dd_model.png');
  await ev(`document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))`);
  await ev(`${dd('effort')}.querySelector('.ta-dd-btn').click()`);
  await t.sleep(250);
  await t.shot('dd_effort.png');
  await ev(`document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))`);
};
