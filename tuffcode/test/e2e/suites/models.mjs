// Model and Thinking dropdowns: filled from each agent's own list with real model names, passed to
// the run, remembered, usable from the keyboard, and locked (with the agent tabs) during a reply.
// Tuff AI's chips too (Pumice 1, Off / Low / Medium / High), on a stand-in model: a file the model's size
// and a stand-in for node-llama-cpp, so the real ai.js and ai-worker.mjs run without the 1.3 GB download.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const FAKE = fs.mkdtempSync(path.join(os.tmpdir(), 'tuffcode-e2e-llama-'));
const FAKE_LOG = path.join(FAKE, 'llama.log');
const fakeLib = path.join(FAKE, 'node_modules', 'node-llama-cpp', 'dist');
fs.mkdirSync(fakeLib, { recursive: true });
// It thinks only when the chat lets it (thoughts "auto" and a budget), a few tokens, or many and slowly
// when the question says SLOW. It answers with a tiny Tuff program, and logs every prompt.
fs.writeFileSync(path.join(fakeLib, 'index.js'), `
import fs from 'node:fs';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (o) => fs.appendFileSync(process.env.FAKE_LLAMA_LOG, JSON.stringify(o) + '\\n');
const sequence = { nextTokenIndex: 0, needsCheckpoints: false, tokenMeter: { usedInputTokens: 0, usedOutputTokens: 0 }, async eraseContextTokenRanges() {}, async evaluateWithoutGeneratingNewTokens() {}, async takeCheckpoint() {} };
export async function getLlama() {
  return { gpu: false, async getGpuDeviceNames() { return []; }, async dispose() {}, async loadModel() { return { tokenizer: {}, async createContext() { return { getSequence: () => sequence }; } }; } };
}
export class QwenChatWrapper { constructor(o = {}) { this.thoughts = o.thoughts || 'auto'; } }
export class LlamaChatSession {
  constructor({ chatWrapper }) { this.chatWrapper = chatWrapper || new QwenChatWrapper(); }
  dispose() {}
  resetChatHistory() {}
  async prompt(text, { signal, onResponseChunk, budgets, maxTokens, customStopTriggers }) {
    const plan = /Don't answer yet/.test(text);
    const slow = /SLOW/.test(text);
    const budget = budgets?.thoughtTokens ?? 0;
    log({ plan, thoughts: this.chatWrapper.thoughts, budget, maxTokens, improved: /What TuffCode worked out/.test(text) });
    if (this.chatWrapper.thoughts === 'auto' && budget > 0) {
      for (let n = 0; n < Math.min(budget, slow ? 400 : 6); n++) {
        if (signal?.aborted) return '';
        await sleep(slow ? 50 : 5);
        onResponseChunk?.({ type: 'segment', segmentType: 'thought', text: 'Thinking it over. ', tokens: [1] });
      }
    }
    let reply = plan ? 'Task: show Hi on the screen.' : 'Here you go:\\n\\u0060\\u0060\\u0060tuff\\nsay "Hi"\\n\\u0060\\u0060\\u0060';
    let out = '';
    for (const piece of reply.match(/[\\s\\S]{1,6}/g)) {
      if (signal?.aborted) return out;
      await sleep(5);
      out += piece;
      onResponseChunk?.({ type: undefined, text: piece, tokens: [1] });
    }
    return out;
  }
}
`);
process.on('exit', () => { try { fs.rmSync(FAKE, { recursive: true, force: true }); } catch {} });

export const meta = { title: 'Model and Thinking dropdowns', env: { TUFFCODE_LLAMA_RUNTIME: FAKE, FAKE_LLAMA_LOG: FAKE_LOG } };

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
  // On a slow machine the list fills in later, and the panel can redraw (closing the menu) as it does: open the
  // menu again if it's shut, and pick the option once it's there, in one step each time.
  const choose = async (o, v) => {
    for (let i = 0; i < 60; i++) {
      const done = await ev(`(() => { const d = ${dd(o)}; if (!d) return false; const opt = d.querySelector('.ta-dd-opt[data-v="${v}"]'); if (opt) { opt.click(); return true; } const b = d.querySelector('.ta-dd-btn'); if (b && !b.disabled && b.getAttribute('aria-expanded') !== 'true') b.click(); return false; })()`);
      if (done) return;
      await t.sleep(250);
    }
    throw new Error(`The ${o} menu never showed "${v}"`);
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
  const labelRunning = await ev(`document.querySelector('.ta-send').getAttribute('aria-label')`);
  await ev(`document.querySelector('.ta-send').click()`);
  await waitFor(`!document.querySelector('.ta-send').classList.contains('stop')`, 5000);
  check('After Stop everything unlocks', await ev(`!${dd('model')}.querySelector('.ta-dd-btn').disabled && !document.querySelector('.ta-agents button[data-id="codex"]').disabled`), null);
  const labelIdle = await ev(`document.querySelector('.ta-send').getAttribute('aria-label')`);
  check('A screen reader hears "Stop" while it answers and "Send" after', labelRunning === 'Stop' && labelIdle === 'Send', { labelRunning, labelIdle });

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

  // ---------------------------------------------------------------- Tuff AI: Pumice 1 and its thinking levels
  const prompts = () => { try { return fs.readFileSync(FAKE_LOG, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)); } catch { return []; } };
  const lastAnswer = () => prompts().filter((p) => !p.plan).pop() || {};
  // The model "downloaded": a file of exactly its size (ai.js only checks the size).
  const models = path.join(path.dirname(ctx.settingsFile), 'models');
  fs.mkdirSync(models, { recursive: true });
  const fd = fs.openSync(path.join(models, 'Qwen3.5-2B-Q4_K_M.gguf'), 'w');
  fs.ftruncateSync(fd, 1280835840);
  fs.closeSync(fd);
  await ev(`(() => { document.querySelector('.ta-top [data-a="menu"]').click(); [...document.querySelectorAll('.ta-menu button')].find(b => /look for agents again/i.test(b.textContent)).click(); return 1; })()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="tuffai"] .dot.ready')`, 20000);
  await tab('tuffai');
  await waitFor(`!${dd('model')}.querySelector('.ta-dd-btn').disabled && ${dd('model')}.querySelector('.ta-dd-v').textContent !== 'Loading…'`, 10000);
  check('Tuff AI: with its model there, the Model and Thinking chips show, and no download card', await ev(`!document.querySelector('.ta-opts').classList.contains('hidden') && !document.querySelector('.ta-status [data-a="ai-get"]')`), await ev(`document.querySelector('.ta-status')?.textContent`));
  const am = await opts('model');
  check('Tuff AI: the model chip lists Pumice 1, and only it (no "Default")', JSON.stringify(am) === JSON.stringify(['qwen3.5-2b=Pumice 1']), am);
  const credit = await ev(`(() => { ${dd('model')}.querySelector('.ta-dd-btn').click(); const s = ${dd('model')}.querySelector('.ta-dd-opt small')?.textContent; document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); return s; })()`);
  check('... with a line of small text that never names the base model', /TuffCode's own AI/.test(credit || '') && !/qwen|apache/i.test(credit || ''), credit);
  const panelWords = await ev(`(() => { const p = document.querySelector('.ta'); return [p.innerText, ...[...p.querySelectorAll('[title], [aria-label]')].map((e) => (e.title || '') + ' ' + (e.getAttribute('aria-label') || ''))].join(' | '); })()`);
  check('Nothing in the Tuff AI panel says Qwen, in its text or its tooltips', !/qwen/i.test(panelWords), panelWords.match(/.{0,60}qwen.{0,60}/i)?.[0]);
  const ae = await opts('effort');
  check('Tuff AI: thinking levels Off, Low, Medium and High, with the default marked', JSON.stringify(ae) === JSON.stringify(['off=Off', 'low=Low (default)', 'medium=Medium', 'high=High']), ae);
  check('Tuff AI: the chips show Pumice 1 and the default level', (await shown('model')) === 'Pumice 1' && (await shown('effort')) === 'Low', [await shown('model'), await shown('effort')]);

  await choose('effort', 'high');
  await send('Make a program that says Hi');
  await idle();
  const high = lastAnswer();
  check('High: the model thinks with its 512-token budget, after the improver and a plan', high.thoughts === 'auto' && high.budget === 512 && prompts().some((p) => p.plan) && prompts().some((p) => p.improved), prompts());
  check('High: the reply says Tuff AI · Pumice 1 · High', /Tuff AI · Pumice 1 · High/.test(await who()), await who());
  const folds = await ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return [...m.querySelectorAll('details.ta-fold')].map(d => ({ cls: d.className, open: d.open, summary: d.querySelector('summary').textContent.trim(), body: d.querySelector('.ta-fold-b').textContent })); })()`);
  check('The reply has the improved request, folded, with its plan', folds[0]?.cls.includes('ta-improved') && !folds[0].open && folds[0].summary === 'Made your request clearer' && /They want: a Tuff program/.test(folds[0].body) && /rewrote it as/.test(folds[0].body) && /Task: show Hi/.test(folds[0].body), folds[0]);
  check('... and the thinking, folded, as "Thought for N s"', folds[1]?.cls.includes('ta-thought') && !folds[1].open && /^Thought for \d+ s$/.test(folds[1].summary) && /Thinking it over/.test(folds[1].body), folds[1]);
  await ev(`[...document.querySelectorAll('.ta-msg.agent')].pop().querySelector('details.ta-thought summary').click()`);
  check('Clicking "Thought for N s" opens the thinking', await ev(`[...document.querySelectorAll('.ta-msg.agent')].pop().querySelector('details.ta-thought').open`), null);
  await ev(`[...document.querySelectorAll('.ta-msg.agent')].pop().querySelector('details.ta-improved summary').click()`);
  await t.sleep(200);
  await t.shot('tuffai_folds.png');
  check('Its code went through the checker', await ev(`[...[...document.querySelectorAll('.ta-msg.agent')].pop().querySelectorAll('.ta-tool')].some(x => /Checked/.test(x.textContent))`), null);

  await choose('effort', 'off');
  await send('Make a program that says Hi again');
  await idle();
  const offRun = lastAnswer();
  check('Off: no thinking at all (thoughts "discourage", budget 0, 700 tokens), as in 1.0.4', offRun.thoughts === 'discourage' && offRun.budget === 0 && offRun.maxTokens === 700, offRun);
  check('Off: the reply says just Tuff AI · Pumice 1, and has no thinking fold', /Tuff AI · Pumice 1$/.test((await who()) || '') && await ev(`![...document.querySelectorAll('.ta-msg.agent')].pop().querySelector('.ta-thought')`), await who());

  // While it thinks, the shimmering "Thinking…" label shows; Stop stops it and unlocks the chips.
  await choose('effort', 'low');
  await send('SLOW: think about this one');
  const live = await waitFor(`!!document.querySelector('.ta-msg.agent.live details.ta-thought .ta-typing')`, 15000);
  const label = await ev(`document.querySelector('.ta-msg.agent.live details.ta-thought .ta-typing span')?.textContent`);
  const lockedAi = await ev(`({ model: ${dd('model')}.querySelector('.ta-dd-btn').disabled, effort: ${dd('effort')}.querySelector('.ta-dd-btn').disabled })`);
  await t.shot('tuffai_thinking.png');
  check('While Pumice 1 thinks, its fold says "Thinking…" with the shimmer, and the chips are locked', live && label === 'Thinking…' && lockedAi.model && lockedAi.effort, { live, label, lockedAi });
  await ev(`document.querySelector('.ta-send').click()`);
  await waitFor(`!document.querySelector('.ta-send').classList.contains('stop') && /Stopped\\./.test([...document.querySelectorAll('.ta-msg.agent')].pop().textContent)`, 5000);
  const stopped = await ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return { text: m.textContent, summary: m.querySelector('details.ta-thought summary')?.textContent.trim(), typing: !!m.querySelector('.ta-typing') }; })()`);
  check('Stop while it thinks: Stopped, the fold says how long it thought, and the chips unlock', /Stopped\./.test(stopped.text) && /^Thought for \d+ s$/.test(stopped.summary || '') && !stopped.typing && await ev(`!${dd('effort')}.querySelector('.ta-dd-btn').disabled`), stopped);

  // Plan, Ask and Edit all work with Tuff AI. In Edit its checked program goes into the open file (one Ctrl+Z
  // puts it back), but not when it comes out much shorter than the file (a small model can stop halfway).
  check('On the Tuff AI tab, Plan, Ask and Edit can all be picked', await ev(`[...document.querySelectorAll('.ta-mode button')].every((b) => !b.disabled)`), null);
  const lastMsg = (js) => ev(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return ${js}; })()`);
  const editFile = path.join(ctx.root, 'edit_me.tuf');
  fs.writeFileSync(editFile, 'say "Bye"\n');
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(editFile)}); return 1; })()`);
  await waitFor(`monaco.editor.getEditors()[0].getModel()?.getValue().includes('Bye')`, 6000);
  await ev(`document.querySelector('.ta-mode button[data-m="edit"]').click()`);
  await send('make it say hi');
  await idle();
  const edited = await t.code();
  const editCard = await lastMsg(`m.querySelector('details.ta-improved .ta-fold-b')?.textContent || ''`);
  const editText = await lastMsg('m.textContent');
  check('Edit: Pumice 1 is asked to change the open program, puts its checked program into the file, and says so', /say "Hi"/.test(edited) && !/Bye/.test(edited) && /their open program changed/.test(editCard) && /Changed .+Ctrl\+Z undoes it/.test(editText), { edited, editCard, end: editText.slice(-160) });
  await ev(`monaco.editor.getEditors()[0].trigger('test', 'undo')`);
  check('... and one Ctrl+Z puts the file back', /say "Bye"/.test(await t.code()), await t.code());
  const long = Array.from({ length: 30 }, (_, i) => `say "Line ${i + 1}"`).join('\n') + '\n';
  await t.setCode(long);
  await send('change line 3');
  await idle();
  check('Edit: a program much shorter than the file (cut off halfway) is not put in, and it says why', (await t.code()) === long && /much shorter than .+ so your file wasn't changed/.test(await lastMsg('m.textContent')), (await lastMsg('m.textContent')).slice(-200));
  await ev(`document.querySelector('.ta-mode button[data-m="ask"]').click()`);
  // A word or two with a file open is a question about that program: explain it.
  await send('what');
  await idle();
  const vague = await lastMsg(`m.querySelector('details.ta-improved .ta-fold-b')?.textContent || ''`);
  check('"what" with a file open becomes: explain what this program does', /an explanation of their code/.test(vague) && /say what .+ does as a whole/.test(vague), vague);

  await choose('effort', 'medium');
  await t.reload();
  await ensurePanel();
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="tuffai"] .dot.ready')`, 20000);
  await tab('tuffai');
  await waitFor(`${dd('effort')}.querySelector('.ta-dd-v').textContent !== 'Loading…'`, 10000);
  check("Tuff AI's level is remembered after a restart", (await shown('effort')) === 'Medium', await shown('effort'));
  await tab('claude');
};
