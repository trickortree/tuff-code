// Sums up bake-off results into a Markdown report.
//   node tuff-ai/bakeoff/report.mjs [results dir] > tuff-ai/bakeoff/RESULTS.md
//   node tuff-ai/bakeoff/report.mjs --think [results/think]   the thinking levels' tables (run.mjs --app)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pct = (a, b) => (b ? `${Math.round((100 * a) / b)}%` : '–');
const avg = (xs) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : 0);
const readRows = (file) => fs.readFileSync(file, 'utf8').split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));

if (process.argv[2] === '--think') {
  thinkReport(process.argv[3] || path.join(path.dirname(fileURLToPath(import.meta.url)), 'results', 'think'));
  process.exit(0);
}

// One row per run of run.mjs --app: a level, with or without the improver, on the GPU or the CPU.
function thinkReport(dir) {
  const q = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)] : 0; };
  const sec = (ms) => `${(ms / 1000).toFixed(1)}`;
  const ORDER = ['off', 'low', 'medium', 'high'];
  const runs = fs.readdirSync(dir).filter((f) => f.endsWith('.jsonl')).map((f) => {
    const rows = readRows(path.join(dir, f));
    const r = rows[0] || {};
    return { file: f, rows, level: r.think, budget: r.budget, temp: r.temp, improve: r.improve, dev: r.dev, threads: r.threads };
  }).filter((r) => r.rows.length).sort((a, b) => (a.dev === 'cpu') - (b.dev === 'cpu') || ORDER.indexOf(a.level) - ORDER.indexOf(b.level) || a.budget - b.budget || a.improve - b.improve);
  const name = (r) => `${r.level[0].toUpperCase()}${r.level.slice(1)}${r.budget ? ` (${r.budget})` : ''}${r.temp != null && r.temp !== 0.2 ? `, temperature ${r.temp}` : ''}`;
  const n = (xs, k) => xs.filter((x) => x[k]).length;
  const out = [];
  const table = (list) => {
    out.push('| Level (thought budget) | Improver | Tasks | **Pass, after 1 retry** | First try | Write | Apps | Fix | Fix: explained | Median s | 90th pct s | Thought tokens (mean) | Cut by the budget | Looping when cut |');
    out.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |');
    for (const r of list) {
      const by = (t) => r.rows.filter((x) => x.type === t);
      const w = by('write'), g = by('gui'), f = by('fix');
      const ms = r.rows.map((x) => x.ms || 0);
      const cut = r.rows.filter((x) => x.cut > 0);
      out.push(`| ${name(r)} | ${r.improve ? 'on' : 'off'} | ${r.rows.length} | **${pct(n(r.rows, 'pass'), r.rows.length)}** | ${pct(n(r.rows, 'pass1'), r.rows.length)} | ${pct(n(w, 'pass'), w.length)} | ${pct(n(g, 'pass'), g.length)} | ${pct(n(f, 'pass'), f.length)} | ${pct(n(f, 'explained'), f.length)} | ${sec(q(ms, 0.5))} | ${sec(q(ms, 0.9))} | ${Math.round(avg(r.rows.map((x) => x.thinkTokens || 0)))} | ${r.budget ? `${cut.length} of ${r.rows.length}` : '–'} | ${r.budget ? cut.filter((x) => x.loop).length : '–'} |`);
    }
  };
  const gpu = runs.filter((r) => r.dev !== 'cpu');
  const cpu = runs.filter((r) => r.dev === 'cpu');
  if (gpu.length) { out.push(`**On the GPU** (${gpu[0].dev}):`, ''); table(gpu); out.push(''); }
  if (cpu.length) {
    out.push(`**On the CPU** (${cpu[0].threads || 'auto'} threads):`, '');
    table(cpu);
    const off = cpu.find((r) => r.level === 'off' && r.improve);
    if (off) {
      out.push('');
      for (const r of cpu.filter((x) => x !== off)) {
        const ids = new Set(off.rows.map((x) => x.id));
        const both = r.rows.filter((x) => ids.has(x.id));
        const extra = both.map((x) => x.ms - off.rows.find((o) => o.id === x.id).ms);
        out.push(`- ${name(r)} with the improver adds a median of **${sec(q(extra, 0.5))} s** per answer on the CPU over Off (90th percentile ${sec(q(extra, 0.9))} s, over the same ${both.length} tasks).`);
      }
    }
    out.push('');
  }
  // What the improver changed, level by level.
  const pairs = gpu.filter((r) => !r.improve).map((a) => [a, gpu.find((b) => b.improve && b.level === a.level && b.budget === a.budget && b.temp === a.temp)]).filter(([, b]) => b);
  if (pairs.length) {
    out.push('**The improver, task by task** (the same tasks with and without it):', '');
    for (const [a, b] of pairs) {
      const ids = new Set(a.rows.map((x) => x.id));
      const both = b.rows.filter((x) => ids.has(x.id));
      const won = both.filter((x) => x.pass && !a.rows.find((y) => y.id === x.id).pass).length;
      const lost = both.filter((x) => !x.pass && a.rows.find((y) => y.id === x.id).pass).length;
      out.push(`- ${name(b)}: the improver turned ${won} failures into passes and ${lost} passes into failures.`);
    }
    out.push('');
  }
  console.log(out.join('\n'));
}

const DIR = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), 'results');
const runs = fs.readdirSync(DIR).filter((f) => f.endsWith('.jsonl')).sort().map((f) => {
  const rows = fs.readFileSync(path.join(DIR, f), 'utf8').split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));
  const log = path.join(DIR, f.replace(/\.jsonl$/, '.log'));
  const events = fs.existsSync(log) ? fs.readFileSync(log, 'utf8').split(/\r?\n/).filter((l) => l.startsWith('{')).flatMap((l) => { try { return [JSON.parse(l)]; } catch { return []; } }) : [];
  return { name: f.replace(/\.jsonl$/, ''), rows, start: events.find((e) => e.event === 'start'), end: events.find((e) => e.event === 'end') };
});

const out = [];
out.push('# Bake-off results', '', `Made by \`report.mjs\` from \`${path.basename(DIR)}/\`. Every score comes from running the model's code with \`tuff.py\`.`, '');
out.push('| Run | Tasks | **All, after 1 retry** | First try | Write | Apps | Fix: fixed | Fix: explained | Passes the checker (first try) |');
out.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- |');
for (const r of runs) {
  const by = (t) => r.rows.filter((x) => x.type === t);
  const w = by('write'), g = by('gui'), f = by('fix');
  const n = (xs, k) => xs.filter((x) => x[k]).length;
  out.push(`| ${r.name} | ${r.rows.length} | **${pct(n(r.rows, 'pass'), r.rows.length)}** | ${pct(n(r.rows, 'pass1'), r.rows.length)} | ${pct(n(w, 'pass'), w.length)} | ${pct(n(g, 'pass'), g.length)} | ${pct(n(f, 'pass'), f.length)} | ${pct(n(f, 'explained'), f.length)} | ${pct(n(r.rows, 'check1'), r.rows.length)} |`);
}
out.push('', '"After 1 retry" is what Tuff AI would show in the app: if the first answer fails `tuff.py --check`, the model gets one more try with the checker\'s error. "Apps" are only checked, never run. "Explained" means the explanation names the mistake (a rough keyword check). Speed and memory aren\'t in this table: part of each run used the GPU to save time, and scores don\'t depend on it. The CPU speed and memory numbers come from `probe.mjs`.', '');

out.push('## By category (after 1 retry)', '');
const cats = [...new Set(runs.flatMap((r) => r.rows.map((x) => (x.type === 'fix' ? `fix: ${x.kind}` : x.cat))))].sort();
out.push(`| Category | ${runs.map((r) => r.name).join(' | ')} |`, `| --- | ${runs.map(() => '---').join(' | ')} |`);
for (const c of cats) {
  out.push(`| ${c} | ${runs.map((r) => { const xs = r.rows.filter((x) => (x.type === 'fix' ? `fix: ${x.kind}` : x.cat) === c); return `${pct(xs.filter((x) => x.pass).length, xs.length)} (${xs.length})`; }).join(' | ')} |`);
}
out.push('', '## By level (after 1 retry)', '');
out.push(`| Level | ${runs.map((r) => r.name).join(' | ')} |`, `| --- | ${runs.map(() => '---').join(' | ')} |`);
for (const l of ['easy', 'medium', 'hard']) {
  out.push(`| ${l} | ${runs.map((r) => { const xs = r.rows.filter((x) => x.level === l); return pct(xs.filter((x) => x.pass).length, xs.length); }).join(' | ')} |`);
}
out.push('', '## Why first tries failed', '');
for (const r of runs) {
  const fails = r.rows.filter((x) => !x.pass1);
  const kinds = {};
  for (const x of fails) {
    const w = x.why1 || '';
    const k = /no code block/.test(w) ? 'no code block' : /^missing/.test(w) ? 'app is missing a needed part' : /output:/.test(w) ? 'runs, wrong output' : /exits/.test(w) ? 'stops with an error when run' : 'fails the checker';
    kinds[k] = (kinds[k] || 0) + 1;
  }
  out.push(`- **${r.name}:** ${Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}`);
}
console.log(out.join('\n'));
