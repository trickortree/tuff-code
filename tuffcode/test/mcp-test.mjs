// Drives the TuffCode MCP server over stdio like an agent would. Exits 1 if any check fails.
// Usage: node test/mcp-test.mjs <TuffCode binary (or node)> <path to tuff-mcp.js>
import { spawn } from 'node:child_process';
const [cmd, ...args] = process.argv.slice(2);
const proc = spawn(cmd, args, { env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' }, stdio: ['pipe', 'pipe', 'inherit'] });
let buf = '';
const waiting = new Map();
proc.stdout.on('data', (d) => {
  buf += d;
  let nl;
  while ((nl = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
    const msg = JSON.parse(line);
    waiting.get(msg.id)?.(msg); waiting.delete(msg.id);
  }
});
let id = 0;
const call = (method, params) => new Promise((r) => { const i = ++id; waiting.set(i, r); proc.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: i, method, params }) + '\n'); });
const tool = async (name, a = {}) => (await call('tools/call', { name, arguments: a })).result;
const results = [];
const check = (name, ok, got) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '\n      got: ' + JSON.stringify(got).slice(0, 400)}`);

const init = await call('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'test', version: '1' } });
check('initialize returns server info + tools capability', init.result?.serverInfo?.name === 'tuffcode' && init.result.capabilities.tools && init.result.protocolVersion === '2025-06-18', init);
proc.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
const list = await call('tools/list', {});
// "At least" checks for tools, libraries and templates: later versions add more of each.
const names = list.result.tools.map((t) => t.name);
check('tools/list has (at least) the 4 tools', ['tuff_reference', 'tuff_examples', 'tuff_check', 'tuff_run'].every((n) => names.includes(n)), names);
const ref = await tool('tuff_reference');
const refText = ref.content[0].text;
check('tuff_reference includes guide, keywords, builtins, libraries (at least tgui, mtgui, anims), widget methods', /Tuff language guide/.test(refText) && /## Keywords\nsay, input/.test(refText) && /`range\(start, end\)`/.test(refText) && ['tgui', 'mtgui', 'anims'].every((lib) => refText.includes(`### ${lib}\n`)) && /`app:button\(/.test(refText), refText.slice(0, 300));
check('tuff_reference topic=widgets is just the methods part', /^## Methods \(windows, widgets, lists, text and lines\)/.test((await tool('tuff_reference', { topic: 'widgets' })).content[0].text), null);
const guide = (await tool('tuff_reference', { topic: 'guide' })).content[0].text;
check('the guide has the Python table, events, patterns and limits', ['## Tuff is not Python', '### Events: what the function gets', '## Patterns', "## What Tuff can't do", 'func is_number(t):'].every((s) => guide.includes(s)), guide.slice(0, 200));
const methodDocs = (await tool('tuff_reference', { topic: 'widgets' })).content[0].text;
check('the methods list has list and text methods', ['items:add value', 'thing:has value', 'text:trim'].every((s) => methodDocs.includes(s)), null);
const ex = (await tool('tuff_examples')).content[0].text;
check('tuff_examples has the templates (at least 8)', (ex.match(/^## /gm) || []).length >= 8 && /func add_task\(\):/.test(ex), ex.slice(0, 200));
const land = /## Hills and lake \(3D\)[^\n]*\n[^\n]*\n\n```tuff\n([\s\S]*?)```/.exec(ex);
check('... and a tgame world with land (terrain) and modern lighting, which tuff_check accepts', land && /:terrain\(/.test(land[1]) && /:lighting "modern"/.test(land[1]) && /^OK/.test((await tool('tuff_check', { code: land[1] })).content[0].text), land ? land[1].slice(0, 200) : ex.slice(-300));
check('the guide has the land and lighting section, with "y is the height above the land"', guide.includes('#### Land and lighting (3D)') && guide.includes('**y is the height above the land.**'), null);
const shopGame = /## Apple shop \(menus and screens\)[^\n]*\n[^\n]*\n\n```tuff\n([\s\S]*?)```/.exec(ex);
check('... and a tgame game with a start screen, a panel with a button and a pausing shop screen, which tuff_check accepts', shopGame && /:start_screen\(/.test(shopGame[1]) && /bar = game:panel\("top left"\)/.test(shopGame[1]) && /bar:button\(/.test(shopGame[1]) && /shop = game:screen\("Shop"\)/.test(shopGame[1]) && /^OK/.test((await tool('tuff_check', { code: shopGame[1] })).content[0].text), shopGame ? shopGame[1].slice(0, 200) : ex.slice(-300));
check('the guide has the menus, buttons and screens section: start screens, panel places, pausing screens, every atgui widget', guide.includes('#### Menus, buttons and screens in games') && ['game:start_screen(', '"bottom right"', 'the game is paused', '**Every atgui widget works on a panel or a screen:**'].every((s) => guide.includes(s)), null);
const smash = /## Car smash \(physics, 3D\)[^\n]*\n[^\n]*\n\n```tuff\n([\s\S]*?)```/.exec(ex);
check('... and a tgame world with physics (crates, a ball, a ragdoll, a car it drives, on_hit and explode), which tuff_check accepts', smash && ['crate:physics()', ':ragdoll(', 'car = game:car(', 'car:drive()', ':on_hit(', 'game:explode('].every((s) => smash[1].includes(s)) && /^OK/.test((await tool('tuff_check', { code: smash[1] })).content[0].text), smash ? smash[1].slice(0, 200) : ex.slice(-300));
check('the guide has the physics section: kinds of physics, push and velocity, on_hit, the car, the ragdoll, explode, 2D, tips and animate', guide.includes('#### Physics') && ['thing:physics("static")', ':push(x, y, z)', ':velocity()', 'func bumped(other, strength):', 'car:drive()', 'world:ragdoll(', 'world:explode(x, y, z, strength, radius)', 'game:walls(true)', "don't move a physics thing every frame", 'thing:animate('].every((s) => guide.includes(s)), null);
const badPhysics = await tool('tuff_check', { code: 'mention tgame\nworld = tgame.world("x")\ncrate = world:box(0, 6, 0, 1, "wood")\ncrate:physics("fixed")\ncrate:mass(0)\n' });
check('tuff_check knows the kinds of physics, with "did you mean", and that a mass is above 0', badPhysics.isError && /not "fixed"\. Did you mean "static"\?/.test(badPhysics.content[0].text) && /crate:mass needs a number above 0, like crate:mass\(2\)\./.test(badPhysics.content[0].text), badPhysics.content[0].text);
const course = /## Snowy obstacle course \(game kit, 3D\)[^\n]*\n[^\n]*\n\n```tuff\n([\s\S]*?)```/.exec(ex);
check('... and a tgame world built from the game kit (weather, a talking person, pads, a path, a key and a door, a countdown, a minimap), which tuff_check accepts', course && ['game:weather(', ':on_talk(', ':jump_pad(', ':boost_pad(', 'lift:path(', 'door:needs(key)', 'game:countdown(', 'game:minimap(', ':health_bar(', 'game:slow_mo('].every((s) => course[1].includes(s)) && /^OK/.test((await tool('tuff_check', { code: course[1] })).content[0].text), course ? course[1].slice(0, 200) : ex.slice(-300));
check('the guide has the game kit section: effects, the HUD, interaction and level pieces', guide.includes('#### Game kit') && ['world:slow_mo(0.3, 2)', 'world:shake(0.5)', 'world:pop_text("+10", x, y, z)', 'world:weather("rain")', 'world:day_cycle(120)', 'world:time_of_day(18)', 'enemy:health_bar(100)', 'clock = game:countdown(60, times_up)', 'world:arrow_to(chest)', 'map:mark(coin, "gold")', 'player:can_grab()', 'npc:on_talk(talk)', 'door:needs(key)', 'world:jump_pad(', 'world:boost_pad(', 'lift:path('].every((s) => guide.includes(s)), null);
const badKit = await tool('tuff_check', { code: 'mention tgame\nworld = tgame.world("x")\nworld:weather("rainy")\nmap = world:minimap(180, "upper left")\n' });
check('tuff_check knows the weathers and the minimap\'s corners, with "did you mean"', badKit.isError && /not "rainy"\. Did you mean "rain"\?/.test(badKit.content[0].text) && /not "upper left"\. Did you mean "top left"\?/.test(badKit.content[0].text), badKit.content[0].text);
const badUi = await tool('tuff_check', { code: 'mention tgame\ngame = tgame.window("x")\nbar = game:panel("middel")\n' });
check('tuff_check knows where a panel can go, with "did you mean"', badUi.isError && /not "middel"\. Did you mean "center"\?/.test(badUi.content[0].text), badUi.content[0].text);
const good = await tool('tuff_check', { code: 'say "hi"\nfunc f(x):\n    x * 2\n' });
check('tuff_check OK on good code', !good.isError && /OK/.test(good.content[0].text), good);
const bad = await tool('tuff_check', { code: 'if x is 1\n    say 1\n' });
check('tuff_check explains a mistake with its line', bad.isError && /line 1/i.test(bad.content[0].text) && /':' or 'then'/.test(bad.content[0].text), bad);
const run = await tool('tuff_run', { code: 'name = input "Name? "\nsay "Hi " + name\nfor i in range(1, 3):\n    say i\n', input: 'Sam' });
check('tuff_run runs with input and returns output', /Hi Sam/.test(run.content[0].text) && /1\n2\n3/.test(run.content[0].text) && /Exit code 0/.test(run.content[0].text), run);
// The built runtime ignores PYTHONIOENCODING, so this fails there if Tuff leaves a pipe on Windows' old code page.
const uni = (await tool('tuff_run', { code: 'say "21.5 °C … \u{1F600}"\nname = input "Name? "\nsay "Hi " + name\n', input: 'Zoë' })).content[0].text;
check('tuff_run keeps text like °, …, emoji and a typed Zoë', uni.includes('21.5 °C … \u{1F600}') && uni.includes('Hi Zoë') && !uni.includes('�'), uni);
const scr = (await tool('tuff_run', { code: 'line = say "Loading"\nline:rewrite("Done!")\nsay "next"\nsay "gone"\nclear(1)\nname = input "Name? "\nsay "Hi " + name\n', input: 'Sam' })).content[0].text;
check('tuff_run shows the final screen: rewritten and cleared lines, answers after questions', scr.startsWith('Done!\nnext\nName? Sam\nHi Sam\n'), scr);
const short = (await tool('tuff_run', { code: 'a = input "A? "\nb = input "B? "\n', input: 'x' })).content[0].text;
check('tuff_run says when the program runs out of answers', /no more input to read/.test(short) && /Exit code 1/.test(short), short);
const deep = (await tool('tuff_check', { code: 'mention mtgui\napp = mtgui.window("T")\napp:hedding "Hi"\nb = app:button("Go", go(), "big")\nfunc go():\n    say 1\n' })).content[0].text;
check('tuff_check lists every problem: method typo, handler with brackets, unknown style', /hedding/.test(deep) && /without brackets/.test(deep) && /'big' isn't a button style/.test(deep), deep);
const slow = await tool('tuff_run', { code: 'while true:\n    wait(1)\n', timeout_seconds: 1 });
check('tuff_run stops a program that runs too long', /Stopped after 1 seconds/.test(slow.content[0].text), slow);
const nofile = await tool('tuff_check', { file: 'does/not/exist.tuf' });
check('missing file is a clear error', nofile.isError && /No file at/.test(nofile.content[0].text), nofile);
const unknown = await call('tools/call', { name: 'nope', arguments: {} });
check('unknown tool is a JSON-RPC error', unknown.error?.code === -32602, unknown);
console.log(results.join('\n'));
proc.stdin.end();
process.exitCode = results.some((r) => r.startsWith('FAIL')) ? 1 : 0;
