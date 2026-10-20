// The editor's tables (renderer/js/tuff-lang.js) know atgui: it loads the way the MCP server loads it, every
// atgui method has hover/completion docs, the shared docs kept their old text, and the "atgui app" snippet
// passes tuff.py --check.   Usage: node tuffcode/test/atgui/docs_test.mjs
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.join(here, '..', '..', '..');
const PY = process.platform === 'win32' ? ['py', '-3'] : ['python3'];
const results = [];
const check = (ok, what, got) => { results.push(ok); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}${ok || got === undefined ? '' : `\n        got: ${JSON.stringify(got).slice(0, 500)}`}`); };

const window = {};
const src = fs.readFileSync(path.join(repo, 'tuffcode', 'renderer', 'js', 'tuff-lang.js'), 'utf8');
vm.runInNewContext(src, { window }, { filename: 'tuff-lang.js' });
check(!!window.TUFF_LIBS?.atgui?.window, 'TUFF_LIBS has atgui.window');
check(!!window.TUFF_DOCS?.atgui, 'TUFF_DOCS has atgui');
for (const lib of ['tgui', 'mtgui', 'anims', 'tap']) check(!!window.TUFF_LIBS[lib], `TUFF_LIBS still has ${lib}`);

// Every method name of every atgui kind, from the library itself.
const names = JSON.parse(execFileSync(PY[0], [...PY.slice(1), '-c',
  'import json, sys; sys.path.insert(0, sys.argv[1]); import tuff_atgui as a; t = a.tables(); print(json.dumps(sorted({m for k in t["kinds"].values() for m in k})))', repo], { encoding: 'utf8' }));
const simple = new Set(['clear', 'upper', 'lower', 'trim', 'has', 'add', 'pop']);
const missing = names.filter((n) => !window.TUFF_METHOD_DOCS[n] && !simple.has(n) && !window.TUFF_DOCS[n]);
check(missing.length === 0, `every atgui method has a doc (${names.length} names)`, missing);
const docs = window.TUFF_METHOD_DOCS;
check(docs.set[1].startsWith('Changes the text or value') && docs.set[1].includes('atgui:'), 'a shared name (set) kept its doc and gained atgui\'s', docs.set);
check(docs.text[1].includes('tap response'), 'text still mentions tap', docs.text);
check(docs.size[1].includes('data:size'), 'size still mentions tap', docs.size);

// The snippet, with its placeholders filled in, passes --check.
const m = src.match(/label: 'atgui app'[^\n]*insertText: '((?:[^'\\]|\\.)*)'/);
check(!!m, 'there is an "atgui app" snippet');
if (m) {
  const code = JSON.parse(`"${m[1].replace(/\\'/g, "'").replace(/"/g, '\\"')}"`).replace(/\$\{\d+:([^}]*)\}/g, '$1').replace(/\$\d+/g, 'say name');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'atgui-snippet-'));
  const file = path.join(dir, 'snippet.tuf');
  fs.writeFileSync(file, code);
  const r = spawnSync(PY[0], [...PY.slice(1), path.join(repo, 'tuff.py'), '--check', file], { encoding: 'utf8' });
  check(r.status === 0 && r.stdout.trim() === 'OK', 'the snippet passes --check', r.stdout + r.stderr);
  fs.rmSync(dir, { recursive: true, force: true });
}
const failed = results.filter((x) => !x).length;
console.log(`docs: ${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
