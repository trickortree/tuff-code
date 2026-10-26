// Tests the tap library (HTTP for Tuff) against a local web server, through real .tuf programs.
// Exits 1 if any check fails. The last check gets a real https:// page and is only reported.
// Usage: node test/tap-test.mjs [how to run Tuff, e.g. py -3 ../tuff.py, or ../build/runtime/tuff-runtime/tuff-runtime.exe]
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const TUFF = process.argv.length > 2 ? process.argv.slice(2)
  : process.platform === 'win32' ? ['py', '-3', path.join(here, '..', '..', 'tuff.py')] : ['python3', path.join(here, '..', '..', 'tuff.py')];
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tap-test-'));

// ---------------------------------------------------------------- the local web server
const slow = new Set();
const server = http.createServer((req, res) => {
  let body = '';
  req.on('data', (d) => { body += d; });
  req.on('end', () => {
    const send = (status, type, text, extra = {}) => {
      res.writeHead(status, { ...(type ? { 'Content-Type': type } : {}), ...extra });
      res.end(text);
    };
    const url = req.url;
    if (url === '/text') return send(200, 'text/plain; charset=utf-8', 'hello tap', { 'X-Two': ['a', 'b'] });
    if (url === '/json') return send(200, 'application/json', JSON.stringify({ name: 'Ada', age: 36, langs: ['tuff', 'python'], address: { city: 'London' }, admin: false, boss: null }));
    if (url === '/array') return send(200, 'application/json', '[1, "two", {"three": 3}]');
    if (url === '/number') return send(200, 'application/json', '42');
    if (url === '/utf8') return send(200, 'text/plain; charset=utf-8', 'héllo ✓');
    if (url === '/headers') return send(200, 'application/json', JSON.stringify(req.headers));
    if (url === '/users/octocat') return send(200, 'application/json', JSON.stringify({ login: 'octocat', name: 'The Octocat', public_repos: 8 }));
    if (url === '/echo' || url === '/post') return send(200, 'application/json', JSON.stringify({ method: req.method, type: req.headers['content-type'] || null, body }));
    if (url.startsWith('/status/')) return send(Number(url.slice(8)), 'text/plain', `status ${url.slice(8)}`);
    if (url === '/empty') return send(204, null, '');
    if (url === '/redirect') return send(302, null, '', { Location: '/json' });
    if (url === '/redirect-headers') return send(302, null, '', { Location: '/headers' });
    if (url === '/redirect-away') return send(302, null, '', { Location: `${OTHER}/headers` });
    if (url === '/bom') return send(200, 'application/json; charset=utf-8', Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from('{"temp":12.5}')]));
    if (url === '/badjson') return send(200, 'application/json', '{not json');
    if (url === '/slow') { slow.add({ res, timer: setTimeout(() => send(200, 'text/plain', 'too late'), 25000) }); return; }
    send(404, 'text/plain', 'no such page');
  });
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;
// Another site (another port), for redirects that leave the first one. It shows the headers it got.
const other = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(req.headers));
});
await new Promise((r) => other.listen(0, '127.0.0.1', r));
const OTHER = `http://127.0.0.1:${other.address().port}`;
// A port nobody is listening on, for "refused the connection".
const closed = http.createServer();
await new Promise((r) => closed.listen(0, '127.0.0.1', r));
const CLOSED = `http://127.0.0.1:${closed.address().port}`;
await new Promise((r) => closed.close(r));

// ---------------------------------------------------------------- running Tuff
let n = 0;
function tuff(code, check = false) {
  const file = path.join(dir, `p${++n}.tuf`);
  fs.writeFileSync(file, `mention tap\n\n${code.replaceAll('BASE', BASE).replaceAll('CLOSED', CLOSED)}`);
  return new Promise((resolve) => {
    const [cmd, ...args] = TUFF;
    const started = Date.now();
    const proc = spawn(cmd, [...args, ...(check ? ['--check'] : []), file], { env: { ...process.env, PYTHONIOENCODING: 'utf-8' }, windowsHide: true });
    let out = '';
    proc.stdout.on('data', (d) => { out += d; });
    proc.stderr.on('data', (d) => { out += d; });
    proc.stdin.end();
    // The built runtime asks "Press Enter to close..." at the end; that isn't the program's output.
    proc.on('close', (code) => resolve({ code, out: out.replace(/\r\n/g, '\n').replace(/\s*Press Enter to close\.\.\.\s*$/, '').trim(), seconds: (Date.now() - started) / 1000 }));
  });
}

const results = [];
const check = (name, ok, got) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '\n      got: ' + JSON.stringify(got).slice(0, 600)}`);
// Runs code, wants exactly these output lines and exit code 0, and wants --check to say OK.
async function works(name, code, want) {
  const [run, chk] = await Promise.all([tuff(code), tuff(code, true)]);
  check(name, run.code === 0 && run.out === want.join('\n'), run);
  check(`${name}: --check says OK`, chk.code === 0 && chk.out === 'OK', chk);
}
// Runs code, wants it to stop with this message (on this line, when given), and --check to say OK.
async function stops(name, code, message, line) {
  const [run, chk] = await Promise.all([tuff(code), tuff(code, true)]);
  check(name, run.code === 1 && run.out.includes(message) && (!line || run.out.includes(`Tuff error on line ${line}:`)), run);
  check(`${name}: --check says OK`, chk.code === 0 && chk.out === 'OK', chk);
  return run;
}
// --check must catch this mistake.
async function caught(name, code, message) {
  const chk = await tuff(code, true);
  check(`--check catches ${name}`, chk.code === 1 && chk.out.includes(message), chk);
}
// The run stops with this message on this line, and --check catches it first, saying checkMessage.
async function stopsAndCaught(name, code, message, line, checkMessage = message) {
  const [run, chk] = await Promise.all([tuff(code), tuff(code, true)]);
  check(name, run.code === 1 && run.out.includes(message) && run.out.includes(`Tuff error on line ${line}:`), run);
  check(`${name}: --check says so first`, chk.code === 1 && chk.out.includes(checkMessage) && chk.out.includes(`Tuff error on line ${line}:`), chk);
}

// The timeout takes 15 seconds, so it runs while the other checks do.
const timeout = tuff('res = tap.get("BASE/slow")\nsay "not reached"\n');

await works('GET text: status, ok, text, headers, how a response shows', `res = tap.get("BASE/text")
say res:status
say res:ok
say res:text
say res:header("content-type")
say res:header("X-Two")
say res:header("X-Missing")
say res
`, ['200', 'true', 'hello tap', 'text/plain; charset=utf-8', 'a, b', 'nil', '<response 200>']);

await works('GET JSON: data objects, nested objects, lists, true/false/nil', `user = tap.get("BASE/json"):json
say user:get("name")
say user:get("age") + 1
say user:get("langs")[0]
say user:get("address"):get("city")
say user:get("admin")
say user:get("boss")
say user:get("nope")
say user:has("age")
say user:has("nope")
say user:keys()
say user:size()
for lang in user:get("langs"):
    say lang
say user:get("address")
say [user:get("address")]
`, ['Ada', '37', 'tuff', 'London', 'false', 'nil', 'nil', 'true', 'false', '["name", "age", "langs", "address", "admin", "boss"]', '6', 'tuff', 'python',
  '{', '  "city": "London"', '}', '[{"city": "London"}]']);

await works(':json of an array and of a number', `items = tap.get("BASE/array"):json
say len(items)
say items[1]
say items[2]:get("three")
say tap.get("BASE/number"):json + 1
t = tap.get("BASE/utf8"):text
say len(t)
say t[1] is "é" and t[-1] is "✓"
`, ['3', 'two', '3', '43', '7', 'true']);

await works('POST a data object as JSON', `body = tap.data()
body:set("title", "Hi")
body:set("tags", ["a", "b"])
inner = tap.data()
inner:set("ok", true)
body:set("inner", inner)
body:set("n", 2)
echo = tap.post("BASE/echo", body):json
say echo:get("method")
say echo:get("type")
say echo:get("body")
`, ['POST', 'application/json', '{"title": "Hi", "tags": ["a", "b"], "inner": {"ok": true}, "n": 2}']);

await works('POST text, PUT a list, DELETE', `a = tap.post("BASE/echo", "plain words"):json
say a:get("type")
say a:get("body")
b = tap.put("BASE/echo", [1, "two", nil]):json
say b:get("method")
say b:get("type")
say b:get("body")
c = tap.delete("BASE/echo"):json
say c:get("method")
say c:get("body") is ""
`, ['text/plain; charset=utf-8', 'plain words', 'PUT', 'application/json', '[1, "two", null]', 'DELETE', 'true']);

await works('headers go with GET and POST, and yours win', `h = tap.data()
h:set("X-Token", "abc123")
h:set("Accept", "application/json")
seen = tap.get("BASE/headers", h):json
say seen:get("x-token")
say seen:get("accept")
say seen:get("user-agent")
csv = tap.data()
csv:set("Content-Type", "text/csv")
say tap.post("BASE/echo", "a,b", csv):json:get("type")
`, ['abc123', 'application/json', 'TuffCode-tap/1.0', 'text/csv']);

await works('HTTP error statuses don\'t stop the program; redirects are followed', `r = tap.get("BASE/status/404")
say r:status
say r:ok
say r:text
r = tap.get("BASE/status/500")
say r:status
say r:ok
r = tap.post("BASE/status/201", "x")
say r:status
say r:ok
r = tap.get("BASE/empty")
say r:status
say "[" + r:text + "]"
r = tap.get("BASE/redirect")
say r:status
say r:json:get("name")
say "still running"
`, ['404', 'false', 'status 404', '500', 'false', '201', 'true', '204', '[]', '200', 'Ada', 'still running']);

await works('a redirect to another site keeps your keys there; the same site gets them', `h = tap.data()
h:set("Authorization", "Bearer MY-SECRET-KEY")
h:set("X-Api-Key", "KEY2")
h:set("Accept", "application/json")
same = tap.get("BASE/redirect-headers", h):json
say same:get("authorization")
say same:get("x-api-key")
away = tap.get("BASE/redirect-away", h):json
say away:get("authorization")
say away:get("x-api-key")
say away:get("accept")
say away:get("user-agent")
`, ['Bearer MY-SECRET-KEY', 'KEY2', 'nil', 'nil', 'application/json', 'TuffCode-tap/1.0']);

await works('JSON that starts with a byte order mark', `res = tap.get("BASE/bom")
say res:json:get("temp")
say len(res:text)
`, ['12.5', '13']);

await stops('an err given to tap stops with its reason', 'res = tap.get(num("abc"))\n', "The input to tap.get() is err: num() couldn't turn 'abc' into a number.", 3);

// The guide's example, with its two web addresses pointed at the local server.
const guide = fs.readFileSync(path.join(here, '..', 'mcp', 'tuff-guide.md'), 'utf8').replace(/\r\n/g, '\n').match(/### tap\n```tuff\n([\s\S]*?)```/);
check('the guide has a tap example', !!guide, null);
if (guide) {
  const example = guide[1].replace(/^mention tap\n\n/, '').replaceAll('https://api.github.com', 'BASE').replaceAll('https://httpbin.org', 'BASE');
  await works("the guide's tap example", example, ['The Octocat has 8 public repos', '200']);
}

await stops('bad JSON is a friendly error on its line', 'res = tap.get("BASE/badjson")\nsay res:status\nuser = res:json\n', "The response isn't JSON (Expecting property name enclosed in double quotes, line 1, column 2). Use :text to see what came back.", 5);
await stops('an empty response has no JSON', 'say tap.get("BASE/empty"):json\n', 'The response is empty, so there\'s no JSON in it (its status is 204).', 3);
await stops('a bad host is a friendly error', 'res = tap.get("http://no-such-host.invalid/x")\n', "Couldn't find no-such-host.invalid. Check the web address and your internet connection.", 3);
await stops('a refused connection is a friendly error', 'res = tap.get("CLOSED/x")\n', 'refused the connection', 3);
await stops('a web address without http(s):// is a friendly error', 'res = tap.get("example.com")\n', 'tap.get needs a web address that starts with http:// or https://, not "example.com". Try "https://example.com".', 3);
await stops('ftp:// is refused', 'res = tap.get("ftp://example.com/file")\n', 'needs a web address that starts with http:// or https://', 3);
await stops('a number body is refused', 'res = tap.post("BASE/echo", 5)\n', 'tap.post sends text, a dictionary, a list or a data object, not a number.', 3);
await stops('headers must be a data object', 'res = tap.get("BASE/text", "X-Token: 1")\n', "tap.get's headers have to be a data object or a dictionary, like {\"Accept\": \"application/json\"}, not text.", 3);
await stops('a data object can\'t hold a function', 'func f():\n    return 1\nd = tap.data()\nd:set("f", f)\n', 'A data object can only hold text, numbers, true/false, nil, lists, dictionaries and data objects, not a function.', 6);
await stops('data object names are text', 'd = tap.data()\nd:set(1, "x")\n', 'data:set needs a name as text', 4);
// [ ] on a data object: the run says to use :get (or :set), and so does --check, not "List positions must be whole numbers".
await stopsAndCaught('user["name"] on a :json data object says to use :get', 'user = tap.get("BASE/json"):json\nsay user["name"]\n',
  'Can\'t use [ ] on a data object. Use :get instead, like user:get("name").', 4,
  'List positions must be whole numbers, not text. If user is a data object (from :json), use :get instead, like user:get("name").');
await stopsAndCaught('d["name"] on tap.data() says to use :get', 'd = tap.data()\nd:set("name", "Ada")\nsay d["name"]\n',
  'Can\'t use [ ] on a data object. Use :get instead, like d:get("name").', 5);
await stopsAndCaught('a nested object\'s ["city"] says which :get', 'user = tap.get("BASE/json"):json\nsay user:get("address")["city"]\n',
  'Use :get instead, like user:get("address"):get("city").', 4, 'use :get instead, like user:get("address"):get("city").');
await stopsAndCaught('d["name"] = ... on a data object says to use :set', 'd = tap.data()\nd["name"] = "Ada"\n',
  'You can only set items in a list, not in a data object. Use :set instead, like d:set("name", value).', 4);

await caught('a response method typo', 'res = tap.get("BASE/text")\nsay res:stauts\n', "A response doesn't have :stauts. Did you mean :status?");
await caught('a data object method typo', 'd = tap.data()\nsay d:gett("x")\n', "A data object doesn't have :gett. Did you mean :get?");
await caught('a missing tap function', 'tap.fetch("BASE/text")\n', "tap doesn't have 'fetch'. It has: get, post, put, delete, data.");
await caught('tap.get with no address', 'res = tap.get()\n', 'tap.get() got the wrong number of inputs (0).');
await caught('tap.post with no body', 'res = tap.post("BASE/echo")\n', 'tap.post() got the wrong number of inputs (1).');
await caught(':header with no name', 'res = tap.get("BASE/text")\nsay res:header()\n', 'response:header got the wrong number of inputs (0).');
await caught(':set with one input', 'd = tap.data()\nd:set("a")\n', 'data object:set got the wrong number of inputs (1).');
await caught('a method input that swallowed the maths', 'res = tap.get("BASE/text")\nsay res:status - 1\n', "res:status doesn't take an input");
await caught('looping over a data object', 'd = tap.data()\nfor k in d:\n    say k\n', "Can't loop over a data object. Loop over its names instead: for k in d:keys():");
await caught(':text used as a number','res = tap.get("BASE/text")\nsay res:text() - 1\n', "Can't subtract text and a number.");

// ---- 1.4.0 dictionaries go anywhere a data object does (fix140)
await works('POST and PUT a dictionary as JSON, and dictionary headers', `body = {"title": "Hi", "tags": ["a", "b"], "inner": {"ok": true}, "n": 2}
echo = tap.post("BASE/echo", body):json
say echo:get("type")
say echo:get("body")
say tap.put("BASE/echo", {1: "one", "two": nil}):json:get("body")
h = {"X-Token": "abc123", "Accept": "application/json"}
seen = tap.get("BASE/headers", h):json
say seen:get("x-token")
say seen:get("accept")
`, ['application/json', '{"title": "Hi", "tags": ["a", "b"], "inner": {"ok": true}, "n": 2}', '{"1": "one", "two": null}', 'abc123', 'application/json']);

await works('a data object holds a dictionary, and a dictionary holds a data object', `d = tap.data()
d:set("info", {"a": 1, "b": [true, nil]})
say d:get("info"):get("a")
say [d]
user = tap.get("BASE/json"):json
mixed = {"who": user:get("address"), "n": 1}
say tap.post("BASE/echo", mixed):json:get("body")
`, ['1', '[{"info": {"a": 1, "b": [true, null]}}]', '{"who": {"city": "London"}, "n": 1}']);

await stops('a dictionary inside a data object can\'t hold a function', 'func f():\n    return 1\nd = tap.data()\nd:set("info", {"f": f})\n',
  'A data object can only hold text, numbers, true/false, nil, lists, dictionaries and data objects, not a function.', 6);
await stops('a dictionary that holds itself can\'t be sent', 'd = {"a": 1}\nd["me"] = d\nres = tap.post("BASE/echo", d)\n',
  'What you send can\'t hold itself.', 5);

const t = await timeout;
check(`a server that doesn't answer stops after 15 seconds (took ${t.seconds.toFixed(1)} s)`, t.code === 1 && t.out.includes("127.0.0.1 didn't answer within 15 seconds.") && t.seconds >= 14 && t.seconds < 30, t);

// A real https:// page: shows that certificates work here. Reported, but not required.
const online = await tuff('res = tap.get("https://api.github.com/zen")\nsay res:status\nsay res:text\n');
const info = `INFO  real HTTPS GET https://api.github.com/zen: ${online.code === 0 ? 'worked' : 'did NOT work'} (${online.seconds.toFixed(1)} s)\n      ${online.out.replace(/\n/g, '\n      ')}`;

for (const { res, timer } of slow) { clearTimeout(timer); res.destroy(); }
server.closeAllConnections?.();
server.close();
other.closeAllConnections?.();
other.close();
fs.rmSync(dir, { recursive: true, force: true });
console.log(results.join('\n'));
console.log(info);
const failed = results.filter((r) => r.startsWith('FAIL')).length;
console.log(`--- ${results.length - failed}/${results.length} passed`);
process.exitCode = failed ? 1 : 0;
