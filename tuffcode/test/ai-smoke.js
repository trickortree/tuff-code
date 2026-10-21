// Runs Tuff AI's backend inside Electron, the way the app does, and prints what the panel would get.
// Then checks who Pumice 1 says it is, the thinking levels, Stop while it thinks, Stop while the model
// starts, and a model file that won't load.
//   npx electron test/ai-smoke.js <model folder with the .gguf> ["question"]
// Needs node-llama-cpp: the app's own, or TUFFCODE_LLAMA_RUNTIME pointing at a separate install.
const { app } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

const [modelDir, question] = process.argv.slice(2).filter((a) => !a.startsWith('--') && !a.endsWith('ai-smoke.js'));
const data = fs.mkdtempSync(path.join(os.tmpdir(), 'tuff-ai-smoke-'));
app.setPath('userData', data);

app.whenReady().then(async () => {
  const ai = require('../ai');
  const m = ai.MODELS[0];
  fs.mkdirSync(path.join(data, 'models'), { recursive: true });
  fs.linkSync(path.join(modelDir, m.file), path.join(data, 'models', m.file));
  ai.setup({
    // Like main.js: tuff.py checks a file (it doesn't read the code from stdin).
    checkSource: async (code) => {
      const file = path.join(data, `check-${Date.now()}.tuf`);
      fs.writeFileSync(file, code);
      const r = require('child_process').spawnSync('python', [path.join(__dirname, '..', '..', 'tuff.py'), '--check', file], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
      return { ok: r.status === 0, message: (r.stdout + r.stderr).split(/\r?\n/)[0] };
    },
  });
  console.log('status', JSON.stringify(await ai.status()));
  const t0 = Date.now();
  let first = 0;
  const ask = (q, id) => new Promise((done) => ai.run({ runId: id, prompt: q, model: m.id }, (e) => {
    if (e.kind === 'delta') { if (!first) first = Date.now(); process.stdout.write(e.text); return; }
    console.log(`\n[${e.kind}]`, JSON.stringify({ ...e, runId: undefined, input: undefined }));
    if (e.kind === 'done') done(e);
  }));
  const r1 = await ask(question || 'Make a program that says the numbers 1 to 5.', 'r1');
  const r1ms = Date.now() - t0;
  console.log(`\nfirst answer: ${r1ms} ms (first token after ${first - t0} ms)`);
  const t1 = Date.now();
  const r2 = await ask('What does round(2.5) give in Tuff?', 'r2');
  console.log(`\nsecond answer: ${Date.now() - t1} ms`);

  const fails = [];
  const check = (name, ok, got) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}`); if (!ok) { console.log('      got', JSON.stringify(got).slice(0, 500)); fails.push(name); } };
  // Every event of one question. onEvent can act on them as they come.
  const events = (q, id, onEvent = () => {}, extra = {}) => new Promise((done) => {
    const got = [];
    ai.run({ runId: id, prompt: q, model: m.id, ...extra }, (e) => { got.push(e); onEvent(e); if (e.kind === 'done') done(got); });
  });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Who it says it is: Pumice 1, based on Qwen3.5-2B, never ChatGPT, Qwen's own assistant or "Tuff AI".
  const answer = async (q, effort, id) => {
    const got = await events(q, id, () => {}, { effort, ai: { question: q } });
    return { text: got.filter((e) => e.kind === 'delta').map((e) => e.text).join('').trim(), got };
  };
  const falseClaim = /\bI(?:'m| am) (?:an? )?(?:ChatGPT|Claude|Gemini|Qwen\b(?!3)|Tuff AI\b)|\b(?:made|created|developed|built|trained) by (?:OpenAI|Anthropic|Google|Alibaba)/i;
  for (const [q, lv] of [['Who are you?', 'off'], ['What model are you?', 'low'], ['Are you ChatGPT?', 'off'], ['Are you Qwen?', 'off'], ['Are you Tuff AI?', 'low']]) {
    const a = await answer(q, lv, `who-${q}`);
    console.log(`[${lv}] ${q}\n      ${a.text.replace(/\s+/g, ' ').slice(0, 300)}`);
    check(`"${q}" (${lv}): it says it's Pumice 1, and claims to be nothing else`, /Pumice 1/.test(a.text) && !falseClaim.test(a.text), a.text);
  }
  // ... and only when it's asked. With the sentence to say in the system prompt, it began 58 of 60 Tuff Bench
  // answers with it. These are at the default level, with a file open for the first one, like the panel.
  for (const [q, parts] of [['What does say do?', { file: 'main.tuf', code: 'say "Hello"\n' }], ['Make a program that counts from 1 to 10.', {}], ['How do I make a list in Tuff?', {}]]) {
    const got = await events(q, `plain-${q}`, () => {}, { ai: { question: q, ...parts } });
    const done = got[got.length - 1];
    const said = (done.stats?.answers || []).join('\n\n');
    console.log(`[default] ${q}\n      ${said.replace(/\s+/g, ' ').slice(0, 200)}`);
    check(`"${q}": the answer doesn't say who it is`, done.ok && said.trim() && !/Pumice|TuffCode's own AI|I(?:'m| am) based on/i.test(said), said);
  }
  const firstTwo = [r1, r2].map((r) => (r.stats?.answers || []).join('\n\n'));
  check('... nor do the first two answers', firstTwo.every((t) => t.trim() && !/Pumice|TuffCode's own AI/i.test(t)), firstTwo);

  // The thinking levels with the real model.
  const run = async (q, effort, id, onEvent) => {
    const t = Date.now();
    const got = await events(q, id, onEvent, { effort, ai: { question: q } });
    return { got, ms: Date.now() - t, kinds: got.map((e) => e.kind), thought: got.find((e) => e.kind === 'thought'), stages: got.filter((e) => e.kind === 'stage').map((e) => e.text) };
  };
  const off = await run('Make a program that says the numbers 1 to 3.', 'off', 'lv-off');
  check(`Off: no thinking, and an answer (${off.ms} ms)`, !off.kinds.includes('thinking') && off.kinds.includes('delta') && off.got[off.got.length - 1].ok, off.stages);
  const low = ai.LEVELS.find((l) => l.id === 'low');
  const lo = await run('Make a program that says the numbers 1 to 3.', 'low', 'lv-low');
  check(`Low: it thinks (${lo.thought?.tokens} tokens, budget ${low.budget}), then answers (${lo.ms} ms)`, lo.kinds.includes('thinking') && lo.thought && lo.thought.tokens <= low.budget + 8 && lo.kinds.includes('delta') && lo.stages.includes('Thinking') && lo.stages.includes('Writing'), { thought: lo.thought, stages: lo.stages });
  const med = await run('Make a program that asks for a name and says Hi to it.', 'medium', 'lv-med');
  const plan = med.got.filter((e) => e.kind === 'plan').map((e) => e.text).join('');
  check(`Medium: it rewrites the request, thinks, then answers (${med.ms} ms)`, plan.trim().length > 10 && !/```/.test(plan) && med.kinds.includes('thinking') && med.kinds.includes('delta') && med.stages.slice(0, 3).join() === 'Reading your question,Planning,Thinking', { plan, stages: med.stages });
  console.log(`      plan: ${plan.replace(/\s+/g, ' ').slice(0, 300)}`);

  // Stop while it thinks: it stops straight away, and the next question isn't kept waiting.
  let stoppedAt = 0;
  const late2 = [];
  const st = await run('Make a guessing game where I guess a number from 1 to 10.', 'high', 'lv-stop', (e) => {
    if (stoppedAt && e.kind !== 'done') late2.push(e.kind);
    if (e.kind === 'thinking' && !stoppedAt) { stoppedAt = Date.now(); ai.stop('lv-stop'); }
  });
  const stopMs = Date.now() - stoppedAt;
  check(`Stop while it thinks: done in ${stopMs} ms, with no answer after it`, st.got[st.got.length - 1].ok && !late2.includes('delta') && stopMs < 3000, { late2, stopMs });
  const after = await run('Say hello in Tuff.', 'off', 'lv-after');
  check(`... and the next question gets its answer (${after.ms} ms)`, after.kinds.includes('delta') && after.got[after.got.length - 1].ok, after.kinds);

  // Stop while the model is starting: that question gets no answer, and the next one isn't kept waiting.
  ai.quit();
  const late = []; // anything for r3 after its done
  let r3done = false;
  const r3 = await events('Make a program that counts to 10.', 'r3', (e) => { if (r3done) late.push(e); if (e.kind === 'note') ai.stop('r3'); if (e.kind === 'done') r3done = true; });
  const t4 = Date.now();
  const r4 = await events('Say hello in Tuff.', 'r4');
  const ms4 = Date.now() - t4;
  await sleep(1000);
  check('Stop while Tuff AI starts: no answer comes for that question', r3.some((e) => e.kind === 'note') && !r3.some((e) => e.kind === 'delta') && r3[r3.length - 1].ok && !late.length, { r3: r3.map((e) => e.kind), late: late.map((e) => e.kind) });
  check(`... and the next question isn't kept waiting behind it (${ms4} ms)`, r4[r4.length - 1].ok && r4.some((e) => e.kind === 'delta') && ms4 < r1ms + 30000, r4.map((e) => e.kind));

  // A model file that doesn't load: each question starts Tuff AI again rather than repeating the old failure.
  ai.quit();
  const real = { file: m.file, size: m.size };
  fs.writeFileSync(path.join(data, 'models', 'broken.gguf'), Buffer.alloc(4096, 7));
  Object.assign(m, { file: 'broken.gguf', size: 4096 });
  const r5 = await events('Say hi.', 'r5');
  const r6 = await events('Say hi.', 'r6');
  Object.assign(m, real);
  check('A model that fails to load: the next question starts Tuff AI again', !r5[r5.length - 1].ok && r6.some((e) => e.kind === 'note' && /Starting/.test(e.text)) && !r6[r6.length - 1].ok, { r5, r6 });

  ai.quit();
  // Electron keeps files open in its own userData folder, so on Windows it can't all go yet.
  try { fs.rmSync(data, { recursive: true, force: true }); } catch {}
  app.exit(r1.ok && r2.ok && !fails.length ? 0 : 1);
});
