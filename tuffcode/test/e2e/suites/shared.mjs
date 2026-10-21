// One chat, several agents: each agent is told who it is, that the chat is shared, and which
// earlier replies were whose; agents that resume their own session get what happened since.
export const meta = { title: 'one chat shared by several agents' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 20000) => t.waitFor(js, ms, 200);
  const tab = (id) => ev(`document.querySelector('.ta-agents button[data-id="${id}"]').click()`);
  const send = (text) => ev(`(() => { const ta = document.querySelector('.ta textarea'); ta.value = ${JSON.stringify(text)}; ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return 1; })()`);
  const idle = () => waitFor(`(() => { const m = [...document.querySelectorAll('.ta-msg.agent')].pop(); return m && !m.querySelector('.ta-typing'); })()`);
  const last = (who) => ctx.readLog(who).filter((l) => l.prompt).pop() || {};

  // Tuff Agents isn't installed in a fresh profile
  await ev(`document.querySelector('.ts-btn[data-tool="plugins"]').click()`);
  await waitFor(`!!document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]')`, 8000);
  await ev(`document.querySelector('.pl-card[data-id="tuff-agents"] [data-a="install"]').click()`);
  await waitFor(`!!document.querySelector('.ta-agents button[data-id="claude"]')`);
  // fresh chat, Default models
  await ev(`(() => { const m = document.querySelector('.ta-top [data-a="menu"]'); m.click(); const n = [...document.querySelectorAll('.ta-menu [data-a], .ta-menu button')].find(b => /new chat/i.test(b.textContent)); n?.click(); return !!n; })()`);
  await tab('claude');
  await t.sleep(300);

  await send('what model are you?');
  await idle();
  const p1 = last('claude').prompt || '';
  check('Claude is told who it is', /You are Claude Code/.test(p1), p1.slice(0, 600));

  await tab('codex');
  await t.sleep(300);
  await send('what context do you have and what model are you');
  await idle();
  const p2 = last('codex').prompt || '';
  check('Codex is told it is Codex, in a shared chat', /You are Codex/.test(p2) && /shared memory/.test(p2) && /I'm Opus 5.5/.test(p2), p2.slice(0, 800));
  check("Claude's earlier reply is labelled as Claude's (with its model), not as Codex's own", /Claude Code \(Opus 5\.5\): Here's a \*\*friendlier\*\*/.test(p2) && !/\nYou: /.test(p2), p2.slice(p2.indexOf('Earlier in this chat')).slice(0, 600));

  // "Test it" for Claude in between must not make Claude lose what Codex did (review finding).
  await tab('claude');
  await ev(`document.querySelector('.ta-top [data-a="setup"]').click()`);
  await waitFor(`!!document.querySelector('.tas-agent[data-id="claude"] [data-s="test"]')`);
  await ev(`document.querySelector('.tas-agent[data-id="claude"] [data-s="test"]').click()`);
  await waitFor(`[...document.querySelectorAll('.toast')].some(x => /Test passed|didn't use|reached the tools/.test(x.textContent))`, 20000);
  const testRun = last('claude');
  check('"Test it" runs without resuming the chat session', !(testRun.args || []).includes('--resume'), testRun.args);
  await ev(`document.querySelector('.ta-top [data-a="setup"]').click()`);
  await t.sleep(300);
  await send('and what did codex say?');
  await idle();
  const l3 = last('claude');
  const p3 = l3.prompt || '';
  check('Claude resumes its own session (--resume)', (l3.args || []).includes('--resume'), l3.args);
  check('…and is caught up on what happened while Codex answered', /Since you last answered, this happened in the chat \(for context only[^)]*\):\n<chat>/.test(p3) && /<message>\nand what did codex say\?\n<\/message>/.test(p3) && /Codex( \([^)]*\))?: Codex says: your code looks fine\./.test(p3), p3.slice(p3.indexOf('Since you last')).slice(0, 600));
  check('…without repeating its own earlier turns', !/what model are you\?/.test(p3.slice(p3.indexOf('Since you last'))), p3.slice(p3.indexOf('Since you last')).slice(0, 600));

  // Tuff Engine's "Ask an agent" (window.tuffAskAgent) says whether the question went: true when it's on its
  // way, false while another reply is still coming (so the Engine keeps its box and the kid's text).
  const asked = await ev(`window.tuffAskAgent('make the coin bigger SLOW')`);
  await waitFor(`!!document.querySelector('.ta-send.stop')`, 5000);
  const busy = await ev(`window.tuffAskAgent('and add a second coin')`);
  const toast = await ev(`[...document.querySelectorAll('.toast')].map(x => x.textContent).join(' | ')`);
  check('tuffAskAgent gives true when the question goes, and false (with "Wait for the reply") while one is running', asked === true && busy === false && /Wait for the reply to finish/.test(toast), { asked, busy, toast });
  await ev(`document.querySelector('.ta-send.stop')?.click()`);
  await idle();
};
