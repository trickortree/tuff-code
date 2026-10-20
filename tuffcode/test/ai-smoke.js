// Runs Tuff AI's backend inside Electron, the way the app does, and prints what the panel would get.
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
    checkSource: async (code) => {
      const r = require('child_process').spawnSync('python', [path.join(__dirname, '..', '..', 'tuff.py'), '--check', '-'], { input: code, encoding: 'utf8' });
      return { ok: r.status === 0, message: (r.stdout + r.stderr).split('\n')[0] };
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
  console.log(`\nfirst answer: ${Date.now() - t0} ms (first token after ${first - t0} ms)`);
  const t1 = Date.now();
  const r2 = await ask('What does round(2.5) give in Tuff?', 'r2');
  console.log(`\nsecond answer: ${Date.now() - t1} ms`);
  ai.quit();
  fs.rmSync(data, { recursive: true, force: true });
  app.exit(r1.ok && r2.ok ? 0 : 1);
});
