// Makes renderer/js/icons.js: the icons TuffCode's interface uses, from MingCute (https://www.mingcute.com,
// Apache-2.0, by the MingCute Design team), in the @iconify-json/mingcute package. Only the icons TuffCode uses go in.
// After using a new one (TuffIcon('name') in a script, or data-icon="name" in index.html):
//   npm pack @iconify-json/mingcute         (into an empty folder, then unpack it there)
//   node scripts/make-icons.cjs <that folder>/package/icons.json
// A name MingCute doesn't have stops it, with the names it does have that are close.
const fs = require('fs');
const path = require('path');

const src = process.argv[2];
if (!src) { console.error('Usage: node scripts/make-icons.cjs <@iconify-json/mingcute>/icons.json'); process.exit(2); }
const set = JSON.parse(fs.readFileSync(src, 'utf8'));
const root = path.join(__dirname, '..');
const scan = [path.join(root, 'renderer'), path.join(root, 'plugins')];

const used = new Map();  // name -> the files it's in
function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== 'node_modules' && e.name !== 'whats-new') walk(p); continue; }
    if (!/\.(js|html|mjs)$/.test(e.name) || p.endsWith(path.join('js', 'icons.js'))) continue;
    const text = fs.readFileSync(p, 'utf8');
    for (const m of text.matchAll(/TuffIcon\(\s*['"]([a-z0-9-]+)['"]|data-icon="([a-z0-9-]+)"/g)) {
      const name = m[1] || m[2];
      if (!used.has(name)) used.set(name, new Set());
      used.get(name).add(path.relative(root, p));
    }
  }
}
for (const d of scan) walk(d);

const missing = [...used.keys()].filter((n) => !set.icons[n]);
if (missing.length) {
  for (const n of missing) {
    const stem = n.replace(/-(line|fill)$/, '').split('-')[0];
    const near = Object.keys(set.icons).filter((k) => k.includes(stem)).slice(0, 8);
    console.error(`MingCute has no "${n}" (in ${[...used.get(n)].join(', ')}). Close: ${near.join(', ') || 'none'}`);
  }
  process.exit(1);
}

const names = [...used.keys()].sort();
const body = names.map((n) => `    ${JSON.stringify(n)}: ${JSON.stringify(set.icons[n].body)},`).join('\n');
const out = `// TuffCode's interface icons: MingCute (https://www.mingcute.com, Apache-2.0, by the MingCute Design team; the license
// is in renderer/licenses/MingCute-LICENSE.txt). Made by scripts/make-icons.cjs from the @iconify-json/mingcute package:
// only the ${names.length} icons TuffCode uses. Don't edit it by hand: use an icon (TuffIcon('name') or data-icon="name"),
// then run the script.
//   TuffIcon('search-line')            an <svg> (24 x 24, drawn in currentColor; the CSS sizes it)
//   TuffIcon('search-line', 'my-class') with a class
//   <svg data-icon="search-line"></svg> in index.html: filled in when this file loads (its other attributes stay)
(() => {
  const ICONS = {
${body}
  };
  const svg = (name, cls = '') => {
    const b = ICONS[name];
    if (!b) console.warn(\`TuffIcon: no icon called "\${name}" (run scripts/make-icons.cjs)\`);
    return \`<svg\${cls ? \` class="\${cls}"\` : ''} viewBox="0 0 24 24" aria-hidden="true">\${b || ''}</svg>\`;
  };
  // index.html's icons: <svg data-icon="name">. Its own fill and stroke settings go (MingCute's shapes have theirs).
  const fill = (el) => {
    el.setAttribute('viewBox', '0 0 24 24');
    for (const a of ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin']) el.removeAttribute(a);
    if (!el.hasAttribute('aria-hidden') && !el.hasAttribute('aria-label')) el.setAttribute('aria-hidden', 'true');
    el.innerHTML = ICONS[el.dataset.icon] || '';
  };
  window.TuffIcon = svg;
  window.TuffIcon.fill = (root = document) => root.querySelectorAll('svg[data-icon]').forEach(fill);
  window.TuffIcon.names = () => Object.keys(ICONS);
  // (Loaded at the end of the page: what's above it is there now, before ide.js and the others run.)
  window.TuffIcon.fill();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => window.TuffIcon.fill());
})();
`;
fs.writeFileSync(path.join(root, 'renderer', 'js', 'icons.js'), out);
console.log(`renderer/js/icons.js: ${names.length} icons`);
