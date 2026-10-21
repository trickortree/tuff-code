// Sums up bake-off results into a Markdown report.
//   node tuff-ai/bakeoff/report.mjs [results dir] > tuff-ai/bakeoff/RESULTS.md
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), 'results');
const pct = (a, b) => (b ? `${Math.round((100 * a) / b)}%` : '–');
const avg = (xs) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : 0);
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
