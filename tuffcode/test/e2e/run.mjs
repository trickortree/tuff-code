// Runs the IDE end-to-end suites (test/e2e/suites/*.mjs). Each suite gets a fresh TuffCode from launch.mjs:
// its own settings, a scratch copy of a fixture project and the stand-in agents, never your real ones.
// Suites run one at a time, because a covered or hidden window stops drawing and the suites wait on it.
// Usage: node test/e2e/run.mjs [suite...] [--app <TuffCode binary>] [--keep]
//   suite   names from test/e2e/suites (default: every suite that runs on this system)
//   --app   test a packaged TuffCode instead of the source checkout (`electron .` in tuffcode/)
//   --keep  keep each suite's scratch folder (project, settings) to look at afterwards
// Prints PASS/FAIL for every check and a total, and exits 1 if anything failed. Logs, screenshots and the
// stand-in agents' logs go to test/e2e/out/<suite>/. Real-agent tests are in test/e2e/manual and never run here.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { E2E, launch, context } from './launch.mjs';
import { connect } from './cdp.mjs';

const SUITES = path.join(E2E, 'suites');
const all = fs.readdirSync(SUITES).filter((f) => f.endsWith('.mjs')).map((f) => f.slice(0, -4)).sort();
const argv = process.argv.slice(2);
let appBin = null;
let keep = false;
const wanted = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--app') appBin = argv[++i];
  else if (argv[i] === '--keep') keep = true;
  else wanted.push(path.basename(argv[i]).replace(/\.mjs$/, ''));
}
const unknown = wanted.filter((n) => !all.includes(n));
if (unknown.length) { console.error(`No such suite: ${unknown.join(', ')}. Suites: ${all.join(', ')}`); process.exit(2); }
if (appBin && !fs.existsSync(appBin)) { console.error(`No TuffCode at ${appBin}`); process.exit(2); }

let current = null;
process.on('SIGINT', async () => { await current?.stop(); process.exit(130); });

const within = (promise, ms) => {
  promise.catch(() => {}); // it can still fail after a timeout, once the app is gone
  let timer;
  return Promise.race([promise, new Promise((_, j) => { timer = setTimeout(() => j(new Error(`timed out after ${ms / 1000} s`)), ms); })]).finally(() => clearTimeout(timer));
};

const summary = [];
for (const name of wanted.length ? wanted : all) {
  const mod = await import(pathToFileURL(path.join(SUITES, `${name}.mjs`)).href);
  const meta = mod.meta || {};
  if (meta.platforms && !meta.platforms.includes(process.platform)) {
    console.log(`\n=== ${name}: skipped, it only runs on ${meta.platforms.join(', ')}${meta.why ? ` (${meta.why})` : ''}`);
    summary.push({ name, skipped: true });
    continue;
  }
  console.log(`\n=== ${name}: ${meta.title || ''}`);
  const res = { name, pass: 0, fail: 0, skip: 0 };
  summary.push(res);
  const app = await launch({ name, project: meta.project, app: appBin, env: meta.env, keep });
  current = app;
  let t;
  try {
    t = await connect(app);
    await t.ready();
    t.check = (label, ok, got) => {
      ok ? res.pass++ : res.fail++;
      console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${ok ? '' : `\n        got: ${JSON.stringify(got)?.slice(0, 700)}`}`);
      return !!ok;
    };
    t.info = (s) => console.log(`INFO  ${s}`);
    t.skip = (label, why) => { res.skip++; console.log(`SKIP  ${label} (${why})`); };
    await within(mod.default(t, context(app)), meta.timeout || 300000);
    if (!res.pass && !res.fail && !res.skip) { res.fail++; console.log('FAIL  the suite ran no checks'); }
  } catch (err) {
    res.fail++;
    console.log(`FAIL  ${name} stopped: ${String(err.stack || err.message).split('\n').slice(0, 4).join('\n        ')}`);
    if (!app.alive()) console.log(`        the app exited (code ${app.proc.exitCode}); see ${path.join(app.out, 'app.log')}`);
  } finally {
    if (t) {
      try { await t.shot('end.png'); } catch {}
      if (t.events.length) console.log('--- page errors ---\n' + [...new Set(t.events)].slice(0, 15).join('\n'));
      t.close();
    }
    await app.stop();
    current = null;
  }
  console.log(`--- ${name}: ${res.pass} passed, ${res.fail} failed${res.skip ? `, ${res.skip} skipped` : ''}`);
}

const ran = summary.filter((s) => !s.skipped);
const total = ran.reduce((a, s) => ({ pass: a.pass + s.pass, fail: a.fail + s.fail, skip: a.skip + s.skip }), { pass: 0, fail: 0, skip: 0 });
console.log('\n=== Summary');
for (const s of summary) console.log(`${s.skipped ? 'skip' : s.fail ? 'FAIL' : 'ok  '}  ${s.name.padEnd(12)} ${s.skipped ? 'not on this system' : `${s.pass}/${s.pass + s.fail}${s.skip ? ` (${s.skip} skipped)` : ''}`}`);
console.log(`TOTAL: ${total.pass} passed, ${total.fail} failed${total.skip ? `, ${total.skip} checks skipped` : ''}, in ${ran.length} suites${summary.length > ran.length ? ` (${summary.length - ran.length} not for this system)` : ''}`);
process.exit(total.fail || !ran.length ? 1 : 0);
