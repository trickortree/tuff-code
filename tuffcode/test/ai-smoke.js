// Runs Tuff AI's backend inside Electron, the way the app does, and prints what the panel would get.
// Then checks Stop while the model starts, and a model file that won't load.
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
  const events = (q, id, onEvent = () => {}) => new Promise((done) => {
    const got = [];
    ai.run({ runId: id, prompt: q, model: m.id }, (e) => { got.push(e); onEvent(e); if (e.kind === 'done') done(got); });
  });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
