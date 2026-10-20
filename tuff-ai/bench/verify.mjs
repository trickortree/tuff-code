// Checks Tuff Bench files against the real interpreter, and fills in expected output.
//   node tuff-ai/bench/verify.mjs <file.jsonl> [--fill]
// write tasks: the solution must pass --check, and each test's stdout must match a real run.
// gui tasks:   the solution must pass --check and contain every "needs" string (never run: it opens windows).
// fix tasks:   "broken" must fail the way "kind" says, and "fixed" must pass like a write task.
// --fill writes the real outputs into the file (stdout, error, got) instead of comparing.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const TUFF = path.join(ROOT, 'tuff.py');
const PY = process.env.TUFF_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'tuff-bench-'));
let n = 0;

export const norm = (s) => String(s ?? '').replace(/\r\n/g, '\n').split('\n').map((l) => l.replace(/\s+$/, '')).join('\n').replace(/\n+$/, '');

export function tuff(code, { stdin = '', check = false, timeout = 10 } = {}) {
  const file = path.join(TMP, `t${n++}.tuf`);
  fs.writeFileSync(file, code, 'utf8');
  return new Promise((resolve) => {
    const p = spawn(PY, [TUFF, ...(check ? ['--check'] : []), file], {
      windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', TUFF_IDE: '', TUFF_ECHO_INPUT: '' },
    });
    let out = '', err = '', timedOut = false;
    p.stdout.on('data', (d) => { if (out.length < 100000) out += d; });
    p.stderr.on('data', (d) => { if (err.length < 100000) err += d; });
    const t = setTimeout(() => { timedOut = true; p.kill(); }, timeout * 1000);
    p.on('close', (code) => {
      clearTimeout(t);
      fs.rmSync(file, { force: true });
      resolve({ code: timedOut ? -1 : code, out: norm(out), err: norm(err), timedOut });
    });
    p.stdin.on('error', () => {});
    p.stdin.end(stdin ? (stdin.endsWith('\n') ? stdin : stdin + '\n') : '');
  });
}

// Does the code contain a "needs" entry? A list means any one of them. The library line counts in any form,
// because `import` and `mention` mean the same thing and tgui and mtgui have the same widgets.
export function hasNeed(code, need) {
  if (Array.isArray(need)) return need.some((n) => hasNeed(code, n));
  if (/^(mention|import)\s+m?tgui$/.test(String(need).trim())) return /^\s*(mention|import)\s+m?tgui\b/m.test(code);
  return code.includes(need);
}

// The error text a beginner would see: whatever the run printed after it failed.
const errorText = (r) => norm([r.out, r.err].filter(Boolean).join('\n')).split('\n').filter((l) => !/^Traceback|^\s+File "/.test(l)).join('\n');

async function checkSolution(code, tests, fill, where, problems) {
  const c = await tuff(code, { check: true });
  if (c.code !== 0) { problems.push(`${where}: fails --check: ${errorText(c).split('\n')[0]}`); return; }
  for (const [i, t] of (tests || []).entries()) {
    const r = await tuff(code, { stdin: t.stdin || '' });
    if (r.code !== 0) { problems.push(`${where} test ${i}: exits ${r.code}${r.timedOut ? ' (timed out)' : ''}: ${errorText(r).split('\n').slice(-3).join(' | ')}`); continue; }
    if (fill) t.stdout = r.out;
    else if (norm(t.stdout) !== r.out) problems.push(`${where} test ${i}: output differs.\n  want: ${JSON.stringify(norm(t.stdout))}\n  got:  ${JSON.stringify(r.out)}`);
  }
}

export async function verifyTask(x, fill = false) {
  const problems = [];
  const where = x.id || '(no id)';
  if (x.type === 'gui') {
    const c = await tuff(x.solution, { check: true });
    if (c.code !== 0) problems.push(`${where}: fails --check: ${errorText(c).split('\n')[0]}`);
    for (const s of x.needs || []) if (!hasNeed(x.solution, s)) problems.push(`${where}: solution lacks ${JSON.stringify(s)}`);
  } else if (x.type === 'fix') {
    const stdin = x.tests?.[0]?.stdin || '';
    const b = await tuff(x.broken, { stdin });
    await checkSolution(x.fixed, x.tests, fill, `${where} (fixed)`, problems);
    if (x.kind === 'error') {
      if (b.code === 0) problems.push(`${where}: "broken" runs without an error`);
      else if (fill) x.error = errorText(b);
      else if (norm(x.error) !== errorText(b)) problems.push(`${where}: error text differs.\n  want: ${JSON.stringify(norm(x.error))}\n  got:  ${JSON.stringify(errorText(b))}`);
    } else if (x.kind === 'wrong-output') {
      if (b.code !== 0) problems.push(`${where}: "broken" should run but exits ${b.code}: ${errorText(b).split('\n')[0]}`);
      else if (b.out === norm(x.tests?.[0]?.stdout)) problems.push(`${where}: "broken" already gives the right output`);
      else if (fill) x.got = b.out;
    } else problems.push(`${where}: kind must be "error" or "wrong-output"`);
  } else {
    if (!x.tests?.length) problems.push(`${where}: no tests`);
    await checkSolution(x.solution, x.tests, fill, where, problems);
  }
  return problems;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [file, flag] = process.argv.slice(2);
  if (!file) { console.error('usage: node verify.mjs <file.jsonl> [--fill]'); process.exit(2); }
  const fill = flag === '--fill';
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter((l) => l.trim());
  const tasks = [];
  const problems = [];
  const ids = new Set();
  for (const [i, l] of lines.entries()) {
    try { tasks.push(JSON.parse(l)); } catch (e) { problems.push(`line ${i + 1}: bad JSON: ${e.message}`); }
  }
  for (const x of tasks) {
    if (ids.has(x.id)) problems.push(`${x.id}: duplicate id`);
    ids.add(x.id);
    problems.push(...(await verifyTask(x, fill)));
  }
  if (fill) fs.writeFileSync(file, tasks.map((x) => JSON.stringify(x)).join('\n') + '\n', 'utf8');
  fs.rmSync(TMP, { recursive: true, force: true });
  console.log(`${tasks.length} tasks, ${problems.length} problems${fill ? ' (outputs filled in)' : ''}`);
  for (const p of problems) console.log('- ' + p);
  process.exit(problems.length ? 1 : 0);
}
