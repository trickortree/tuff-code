// The message box: Ask / Plan / Edit, "/" commands, /compact, and the follow-up buttons
// ("Edit it for me" after an Ask answer that offers a change, "Go ahead" after a plan), and Explain on a
// Run error.
export const meta = { title: 'modes, / commands and /compact' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const idle = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`);
  const runs = (who) => ctx.readLog(who).filter((l) => l.prompt);
  const last = (who) => runs(who).pop() || {};
  const lastNote = () => ev(`[...document.querySelectorAll('.ta-msg.note .ta-notebox')].pop()?.textContent || ''`);

  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"] .dot.ready')`);
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);

  // One row: mode, model, thinking, send.
  const row = await ev(`(() => { const r = document.querySelector('.ta-row'); const ys = ['.ta-mode', '.ta-dd[data-o="model"]', '.ta-send'].map(s => Math.round(r.querySelector(s).getBoundingClientRect().top)); return { modes: [...r.querySelectorAll('.ta-mode button')].map(b => b.dataset.m), ys }; })()`);
  check('Plan, Ask and Edit sit in one row with the model chip and Send', row.modes.join() === 'plan,ask,edit' && Math.max(...row.ys) - Math.min(...row.ys) < 12, row);
  // In a narrow panel the chips shrink instead of running under Send, and Send/Stop is no taller than them.
  const fit = async () => ev(`(() => { const r = document.querySelector('.ta-row'), s = r.querySelector('.ta-send').getBoundingClientRect(); const chips = [...r.querySelectorAll('.ta-dd-btn, .ta-mode')].map(e => e.getBoundingClientRect()); return { clear: chips.every(c => c.right <= s.left + 0.5), sendH: Math.round(s.height), tallest: Math.round(Math.max(...chips.map(c => c.height))), inside: s.right <= r.getBoundingClientRect().right + 0.5 }; })()`);
  await ev(`document.documentElement.style.setProperty('--rightbar-w', '360px'); 1`);
  await t.sleep(300);
  const narrow = await fit();
  await ev(`document.querySelector('.ta-send').classList.add('stop'); 1`);
  const narrowStop = await fit();
  await ev(`document.querySelector('.ta-send').classList.remove('stop'); document.documentElement.style.removeProperty('--rightbar-w'); 1`);
  await t.sleep(300);
  check('In a 360 px panel the chips stay clear of Send/Stop, which is no taller than they are', narrow.clear && narrowStop.clear && narrow.inside && narrow.sendH <= narrow.tallest && narrowStop.sendH <= narrowStop.tallest, { narrow, narrowStop });

  // Typing "/" lists commands; /help writes them into the chat.
  await ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.focus(); ta.value = '/c'; ta.dispatchEvent(new Event('input', { bubbles: true })); return 1; })()`);
  const listed = await ev(`[...document.querySelectorAll('.ta-slash:not(.hidden) .ta-slash-opt b')].map(b => b.textContent)`);
  check('Typing "/c" lists the matching commands', listed.includes('/compact') && listed.includes('/claude') && listed.includes('/codex') && !listed.includes('/help'), listed);
  await send('/help');
  check('/help lists the commands in the chat', /\/compact/.test(await lastNote()) && /\/plan/.test(await lastNote()), await lastNote());
  await send('/nope');
  check('An unknown command says so', /There's no \/nope command/.test(await lastNote()), await lastNote());

  // Ask: the agent is told to ask before changing anything, and an answer with code gets "Edit it for me".
  await send('Make my greeting friendlier');
  await idle();
  const ask = last('claude');
  check('Ask tells the agent to offer the change, not paste a whole program', /ask if they'd like you to make the change/.test(ask.prompt || '') && (ask.args || [])[ask.args.indexOf('--permission-mode') + 1] === 'default', (ask.prompt || '').slice(0, 400));
  check('An Ask answer with code gets "Edit it for me"', await ev(`!!document.querySelector('.ta-msg.agent:last-child [data-act="do-edit"]')`), await ev(`document.querySelector('.ta-msg.agent:last-of-type')?.textContent?.slice(-200)`));
  await ev(`document.querySelector('[data-act="do-edit"]').click()`);
  await idle();
  const did = last('claude');
  check('"Edit it for me" sends one message in Edit mode, and the mode stays Ask', /make that change/.test(did.prompt || '') && (did.args || [])[did.args.indexOf('--permission-mode') + 1] === 'acceptEdits' && await ev(`document.querySelector('.ta-mode button.on')?.dataset.m === 'ask'`), did.args);

  // Tab or Enter on a half-typed command fills it in and never runs it, so "/n" + Tab can't clear the chat.
  const msgCount = () => ev(`document.querySelectorAll('.ta-msg').length`);
  const keyIn = (text, key) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.focus(); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new Event('input', { bubbles: true })); ta.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(key)}, bubbles: true })); return ta.value; })()`);
  const [msgsBefore, runsBefore] = [await msgCount(), runs('claude').length];
  const tabbed = await keyIn('/n', 'Tab');
  const entered = await keyIn('/c', 'Enter');
  await t.sleep(300);
  check('Tab or Enter on a half-typed command fills it in and runs nothing (#35)', tabbed === '/new' && entered === '/compact' && await msgCount() === msgsBefore && runs('claude').length === runsBefore, { tabbed, entered, msgs: [msgsBefore, await msgCount()] });
  await keyIn('', 'Escape');

  // /plan switches to Plan; the plan gets "Go ahead".
  await send('/plan add a score counter');
  await idle();
  const plan = last('claude');
  check('/plan switches to Plan and sends the rest', await ev(`document.querySelector('.ta-mode button.on')?.dataset.m === 'plan'`) && /add a score counter/.test(plan.prompt || '') && (plan.args || [])[plan.args.indexOf('--permission-mode') + 1] === 'plan' && /numbered plan/.test(plan.prompt || ''), plan.args);
  check('A plan gets "Go ahead"', await ev(`!!document.querySelector('[data-act="go"]')`), null);
  // It goes to the selected agent, so it hides while another agent's tab is selected.
  await ev(`document.querySelector('.ta-agents button[data-id="codex"]').click()`);
  const goOnCodex = await ev(`!!document.querySelector('[data-act="go"]')`);
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);
  check('"Go ahead" hides on another agent\'s tab and comes back on Claude\'s (#37)', !goOnCodex && await ev(`!!document.querySelector('[data-act="go"]')`), { goOnCodex });
  await ev(`document.querySelector('[data-act="go"]').click()`);
  await idle();
  const go = last('claude');
  check('"Go ahead" sends the go-ahead in Edit mode', /Go ahead with the plan/.test(go.prompt || '') && (go.args || [])[go.args.indexOf('--permission-mode') + 1] === 'acceptEdits', go.args);
  await send('/ask');

  // /codex switches agent; /model picks by name.
  await send('/codex');
  check('/codex switches to Codex', await ev(`document.querySelector('.ta-agents button.on')?.dataset.id === 'codex'`), null);
  await send('/claude');
  await waitFor(`!(document.querySelector('.ta-dd[data-o="model"] .ta-dd-v')?.textContent || '').includes('Loading')`, 8000);
  await send('/model sonnet');
  check('/model sonnet picks Sonnet', /Sonnet/.test(await ev(`document.querySelector('.ta-dd[data-o="model"] .ta-dd-v').textContent`)) && /will use Sonnet/.test(await lastNote()), await lastNote());
  await send('/model');

  // /compact: the reply becomes the summary; later prompts get it instead of the chat before it.
  const before = runs('claude').length;
  await send('/compact');
  await waitFor(`runs => true`, 100);
  await idle();
  const sum = last('claude');
  check('/compact asks the agent for a summary of the whole chat, in a fresh session', runs('claude').length === before + 1 && /Summarize this whole chat/.test(sum.prompt || '') && /add a score counter/.test(sum.prompt || '') && !(sum.args || []).includes('--resume'), (sum.prompt || '').slice(-400));
  check('The summary shows as "Chat summary", and older messages fade', await ev(`!!document.querySelector('.ta-msg.agent.summary') && document.querySelectorAll('.ta-old').length > 3`), await ev(`document.querySelectorAll('.ta-old').length`));
  await send('what did we do so far?');
  await idle();
  const after = last('claude');
  check('After /compact, an agent gets the summary instead of the old messages', /Summary of the chat before this point/.test(after.prompt || '') && !/Make my greeting friendlier/.test(after.prompt || '') && !(after.args || []).includes('--resume'), { sum: (after.prompt || '').indexOf('Summary of the chat'), earlier: (after.prompt || '').indexOf('Earlier in this chat'), old: (after.prompt || '').indexOf('Make my greeting'), msg: (after.prompt || '').indexOf('what did we do'), len: (after.prompt || '').length, resume: (after.args || []).includes('--resume'), tail: (after.prompt || '').slice(-300) });

  // Tuff AI only answers: Plan and Edit are off on its tab.
  await ev(`document.querySelector('.ta-agents button[data-id="tuffai"]').click()`);
  check('On the Tuff AI tab, Plan and Edit are switched off', await ev(`(() => { const b = [...document.querySelectorAll('.ta-mode button')]; return b.find(x => x.dataset.m === 'plan').disabled && b.find(x => x.dataset.m === 'edit').disabled && b.find(x => x.dataset.m === 'ask').classList.contains('on'); })()`), null);
  // Without its model: the download card names Pumice 1 (with the credit to Qwen3.5-2B), and the Model and
  // Thinking chips wait until it's downloaded.
  await waitFor(`!!document.querySelector('.ta-status .ta-card, .ta-status .ta-note:not(:empty)') && !/Checking Tuff AI/.test(document.querySelector('.ta-status').textContent)`, 10000);
  const card = await ev(`({ text: document.querySelector('.ta-status')?.textContent || '', get: document.querySelector('.ta-status [data-a="ai-get"]')?.textContent || '', chips: document.querySelector('.ta-opts').classList.contains('hidden') })`);
  if (card.get) {
    check('The Tuff AI card offers to download Pumice 1, credits Qwen3.5-2B, and hides the chips until then', /^Download Pumice 1 \(1\.3 GB\)$/.test(card.get) && /Its model is Pumice 1/.test(card.text) && /Pumice 1 · based on Qwen3\.5-2B \(Apache 2\.0\)/.test(card.text) && card.chips, card);
  } else t.skip('The Tuff AI download card', `this copy has no node-llama-cpp: ${card.text.slice(0, 80)}`);
  // Tuff AI only reads the last few messages, so it can't sum up the chat for everyone.
  const summaries = () => ev(`document.querySelectorAll('.ta-msg.agent.summary').length`);
  const sumBefore = await summaries();
  await send('/compact');
  check('/compact on Tuff AI says to switch agents, and leaves the chat as it is (#12)', /can't sum up the chat/.test(await lastNote()) && await summaries() === sumBefore, await lastNote());

  // Explain on a Run error (the Explain / Fix commands work the same way).
  const toasts = () => ev(`window.__toasts`);
  const watchToasts = () => ev(`(() => { window.__toasts = []; new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => n.classList?.contains('toast') && window.__toasts.push(n.textContent)))).observe(document.querySelector('#toasts'), { childList: true }); return 1; })()`);
  const asked = () => ev(`document.querySelectorAll('.ta-msg.user').length`);
  await watchToasts();
  await ev(`document.querySelector('.ta-agents button[data-id="claude"]').click()`);
  await ev(`document.querySelector('.ta [data-a="setup"]').click()`);
  await waitFor(`!document.querySelector('.ta-setup').classList.contains('hidden')`, 5000);
  let n = await asked();
  await ev(`window.tuffExplainError('Tuff error on line 2: expected ":"'); 1`);
  await waitFor(`document.querySelectorAll('.ta-msg.user').length > ${n}`, 8000);
  await idle();
  check('Explain from the Agent tools page goes back to the chat, where the answer shows (#38)', await asked() > n && await ev(`!document.querySelector('.ta-msgs').classList.contains('hidden') && document.querySelector('.ta-setup').classList.contains('hidden')`), await ev(`document.querySelector('.ta-msgs').className`));

  await send('SLOW question');
  await waitFor(`!!document.querySelector('.ta-msg.agent.live')`, 8000);
  n = await asked();
  await ev(`window.tuffExplainError('Tuff error on line 3: oops'); 1`);
  await t.sleep(400);
  check('Explain while an agent is answering says to wait, and sends nothing (#38)', (await toasts()).some((x) => /Wait for the reply to finish/.test(x)) && await asked() === n, await toasts());
  await ev(`document.querySelector('.ta-send').click()`);
  await idle();

  // The panel looks for agents when it opens (and on "Look for agents again"). Explain waits for that
  // instead of saying the agent isn't installed.
  n = await asked();
  let runsAt = runs('claude').length;
  await ev(`(() => { document.querySelector('.ta-top [data-a="menu"]').click(); [...document.querySelectorAll('.ta-menu button')].find(b => /look for agents again/i.test(b.textContent)).click(); window.tuffExplainError('Tuff error on line 4: while looking'); return 1; })()`);
  await waitFor(`document.querySelectorAll('.ta-msg.user').length > ${n}`, 15000);
  await idle();
  check('Explain while the panel looks for agents waits, then sends (#9)', await asked() > n && runs('claude').length > runsAt && !(await toasts()).some((x) => /isn't installed/.test(x)), { toasts: await toasts(), runs: [runsAt, runs('claude').length] });

  // The first time the panel opens after a restart (it was closed when TuffCode last quit).
  await ev(`document.querySelector('#toolstrip-right .ts-btn.active').click(); 1`);
  await t.reload();
  await waitFor(`typeof window.tuffExplainError === 'function' && !document.querySelector('.ta')`, 10000);
  await watchToasts();
  runsAt = runs('claude').length;
  await ev(`window.tuffExplainError('Tuff error on line 5: after a restart'); 1`);
  await waitFor(`document.querySelectorAll('.ta-msg.user').length > 0`, 15000);
  await idle();
  check('After a restart, Explain opens the panel and sends to the agent (#9)', await asked() === 1 && /after a restart/.test(last('claude').prompt || '') && runs('claude').length > runsAt && !(await toasts()).some((x) => /isn't installed/.test(x)), { toasts: await toasts(), asked: await asked(), runs: [runsAt, runs('claude').length] });
};
