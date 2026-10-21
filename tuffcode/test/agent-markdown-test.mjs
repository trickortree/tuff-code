// Runs the Tuff Agents panel's Markdown renderer (md, inline, link, linkTarget, prose) outside the IDE, on
// the kinds of replies real agents write: file:/// links, file:line links, tables, numbered lists split by
// blank lines, quotes, code spans, and links that must stay plain text. Exits 1 if any check fails.
// Usage: node test/agent-markdown-test.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = fs.readFileSync(path.join(here, '..', 'plugins', 'tuff-agents', 'panel.js'), 'utf8');
const start = src.indexOf('  function md(src)');
const end = src.indexOf('  // ---------------------------------------------------------------- running');
const body = src.slice(start, end);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const short = (p) => String(p || '').split(/[\\/]/).pop();
const icon = () => '';
const lit = new Map();
const t = { project: { root: () => 'C:\\Users\\jacks\\OneDrive\\Documents\\TuffProjects\\HelloTuff' }, editor: { replaceAll: () => {} } };
const api = new Function('esc', 'short', 'icon', 'lit', 't', `${body}\nreturn { md, inline, linkTarget };`)(esc, short, icon, lit, t);

let fails = 0;
const check = (name, ok, got) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '\n      got: ' + got}`); if (!ok) fails++; };
const { md, linkTarget } = api;

const user = `Here's who answered each of your earlier messages:

1. Claude Code (Opus 5.5) answered your first three messages—explaining \`tgame\`, creating [GameDude.tuf](file:///C:/Users/jacks/OneDrive/Documents/TuffProjects/HelloTuff/GameDude.tuf), and creating [CoinHunt3D.tuf](file:///C:/Users/jacks/OneDrive/Documents/TuffProjects/HelloTuff/CoinHunt3D.tuf).
2. Tuff AI (Qwen3.5-2B) answered the next two ("Hi" and "What ai are you?").
3. Antigravity (me!) answered your last message ("yo anti wsg").`;
let h = md(user);
check('the user\'s message: two file links, no raw [..](..)', (h.match(/class="ta-a file"/g) || []).length === 2 && !/\]\(file:/.test(h), h);
check('file:/// link → a Windows path', h.includes('data-file="C:\\Users\\jacks\\OneDrive\\Documents\\TuffProjects\\HelloTuff\\GameDude.tuf"'), h);
check('the numbered list stays a list of 3 with `tgame` as code', /<ol><li>/.test(h) && (h.match(/<li>/g) || []).length === 3 && h.includes('<code>tgame</code>'), h);

h = md('1. one\n\n2. two\n\n3. three');
check('numbers split by blank lines keep counting (start="2", start="3")', h.includes('<ol start="2">') && h.includes('<ol start="3">'), h);
h = md('| Name | Score |\n| --- | ---: |\n| Sam | **10** |\n| Zoë | `5` |');
check('a table', h.includes('<table>') && h.includes('<th>Name</th>') && h.includes('<td><b>10</b></td>') && h.includes('<td><code>5</code></td>'), h);
h = md('Use `a*b*c` and `**not bold**` here, and *real italics*.');
check('code spans are not styled inside', h.includes('<code>a*b*c</code>') && h.includes('<code>**not bold**</code>') && h.includes('<i>real italics</i>'), h);
h = md('See https://example.com/page?x=1&y=2. And <https://tuff.dev>.');
check('bare web addresses become links, without the full stop', h.includes('data-url="https://example.com/page?x=1&amp;y=2"') && h.includes('data-url="https://tuff.dev"'), h);
h = md('[bad](javascript:alert(1)) and [data](data:text/html,hi) and [mail](mailto:a@b.c)');
check('javascript:, data: and mailto: are plain text, never links', !h.includes('<a ') && h.includes('bad') && !h.includes('javascript'), h);
check('main.tuf:12 → the file and line 12', JSON.stringify(linkTarget('main.tuf:12')) === JSON.stringify({ file: 'C:\\Users\\jacks\\OneDrive\\Documents\\TuffProjects\\HelloTuff\\main.tuf', line: 12 }), JSON.stringify(linkTarget('main.tuf:12')));
check('file:///…#L7 → line 7', linkTarget('file:///C:/a/b.tuf#L7').line === 7 && linkTarget('file:///C:/a/b.tuf#L7').file === 'C:\\a\\b.tuf', JSON.stringify(linkTarget('file:///C:/a/b.tuf#L7')));
check('%20 in a file link is a space', linkTarget('file:///C:/My%20Docs/a.tuf').file === 'C:\\My Docs\\a.tuf', JSON.stringify(linkTarget('file:///C:/My%20Docs/a.tuf')));
h = md('[x](<C:/My Docs/x.tuf>)');
check('<path with spaces> in a link', h.includes('data-file="C:\\My Docs\\x.tuf"'), h);
h = md('> a quote\n> second line\n\n---\n\n~~old~~ new');
check('quotes, a --- line and ~~strikethrough~~', h.includes('<blockquote>a quote<br>second line</blockquote>') && h.includes('<hr>') && h.includes('<s>old</s>'), h);
h = md('- top\n  - under it\n  more about it\n- next');
check('an indented item is a list inside the one above, and an indented line joins its item', h === '<ul><li>top<ul><li>under it<br>more about it</li></ul></li><li>next</li></ul>', h);
h = md('1. Step one\n   - detail a\n   - detail b\n2. Step two\n   1. sub one\n   2. sub two\n3. Step three');
check('bullets under numbered steps don\'t use up numbers: 3 steps in one <ol>, the sub-steps numbered in their own', h === '<ol><li>Step one<ul><li>detail a</li><li>detail b</li></ul></li><li>Step two<ol><li>sub one</li><li>sub two</li></ol></li><li>Step three</li></ol>', h);
h = md('- a\n  - b\n    - c\n  - d\n- e');
check('three levels deep, and back out again', h === '<ul><li>a<ul><li>b<ul><li>c</li></ul></li><li>d</li></ul></li><li>e</li></ul>', h);
h = md('1. a\n   - x\n   1. y\n2. b');
check('bullets then numbers inside one item: two lists side by side', h === '<ol><li>a<ul><li>x</li></ul><ol><li>y</li></ol></li><li>b</li></ol>', h);
h = md('##### Small heading\nmy_file_name and snake_case stay, but _this_ is italic. \\*not italic\\*');
check('#####, snake_case kept, _italic_, \\*escapes\\*', h.includes('<h4>Small heading</h4>') && h.includes('my_file_name') && h.includes('snake_case') && h.includes('<i>this</i>') && h.includes('*not italic*'), h);
h = md('<script>alert(1)</script> and [<b>x</b>](https://a.b)');
check('HTML is escaped, in text and link labels', !h.includes('<script>') && h.includes('&lt;script&gt;') && h.includes('&lt;b&gt;x&lt;/b&gt;'), h);
h = md('```tuff\nsay "[x](file:///C:/a.tuf)"\n```');
check('links inside a code block stay code', !h.includes('<a '), h);
h = md('[a "quote"](https://x.y/"onmouseover=alert(1))');
check('quotes in a URL can\'t break out of the attribute', !/data-url="[^"]*"onmouseover/.test(h), h);
console.log(fails ? `${fails} failed` : 'all passed');
process.exit(fails ? 1 : 0);
