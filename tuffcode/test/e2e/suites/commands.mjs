// The message box: Ask / Plan / Edit, "/" commands, /compact, and the follow-up buttons
// ("Edit it for me" after an Ask answer that offers a change, "Go ahead" after a plan).
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
  check('Ask, Plan and Edit sit in one row with the model chip and Send', row.modes.join() === 'ask,plan,edit' && Math.max(...row.ys) - Math.min(...row.ys) < 12, row);

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

  // /plan switches to Plan; the plan gets "Go ahead".
  await send('/plan add a score counter');
  await idle();
  const plan = last('claude');
  check('/plan switches to Plan and sends the rest', await ev(`document.querySelector('.ta-mode button.on')?.dataset.m === 'plan'`) && /add a score counter/.test(plan.prompt || '') && (plan.args || [])[plan.args.indexOf('--permission-mode') + 1] === 'plan' && /numbered plan/.test(plan.prompt || ''), plan.args);
  check('A plan gets "Go ahead"', await ev(`!!document.querySelector('[data-act="go"]')`), null);
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
};
