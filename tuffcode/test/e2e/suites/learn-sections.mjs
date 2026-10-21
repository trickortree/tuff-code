// Learn Tuff's sections: Basics, 2 Build apps, 2.1 Modern apps, then the new 2.2 Advanced apps (atgui), 3 The
// internet (tap) and 4 Games (tgame). Starts from a 1.0.4 profile's progress (Modern apps lessons done when it was
// still "Section 2.2"), so finished lessons must stay finished. Opens a lesson in each new section with real clicks,
// runs the first Games lesson from the lesson's Run button (the starter, then the solution; tgame's autopilot closes
// the game), and checks every new lesson: its check accepts its solution and rejects its starter, and its example,
// starter and solution pass tuff --check. The first internet lesson also runs for real when the internet is there.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { OUT, REPO, python } from '../launch.mjs';

// The games started from the IDE close themselves: tgame's autopilot (tuffcode/test/tgame/README.md) reads this plan.
const PLAN = path.join(OUT, 'learn-sections', 'autopilot.json');
export const meta = { title: 'Learn Tuff: the sections, old progress, and the new lessons\' checks', timeout: 360000, env: { TUFF_TGAME_AUTOPILOT: PLAN } };

const NL = '\n';
const TITLES = ['Basics', 'Section 2 · Build apps', 'Section 2.1 · Modern apps', 'Section 2.2 · Advanced apps', 'Section 3 · The internet', 'Section 4 · Games'];
const NEW = ['atgui', 'tap', 'tgame'];
// What a 1.0.4 profile saved: two Basics lessons, one Build apps lesson and two Modern apps lessons done.
const OLD_DONE = ['say-hello', 'variables', 'tgui-window', 'mtgui-window', 'mtgui-studio'];
// Console tap lessons: what to type, and what to use when the internet isn't there.
const TAP_RUN = {
  'tap-get': { stand_in: '200\n{"setup": "Why?", "punchline": "Because."}' },
  'tap-json': { stand_in: 'Why?\nBecause.' },
  'tap-ok': { input: 'octocat\n', stand_in: 'GitHub username? octocat has 8 public repos' },
  'tap-lists': { stand_in: '1. Cats nap.\n2. Cats purr.\n3. Cats climb.\n4. Cats hunt.\n5. Cats sleep.' },
  'tap-weather': { stand_in: 'Right now it is 10.5°C\nThat is 51°F' },
  'tap-post': { stand_in: 'Saved as post number 101' },
};

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 8000) => t.waitFor(js, ms, 120);
  const LESSONS = path.join(ctx.root, 'lessons');
  const norm = (s) => String(s ?? '').replace(/\r\n/g, NL);
  const settings = () => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'));
  // A real click in the middle of an element (scrolled into view first).
  const clickEl = async (js) => {
    const r = await ev(`(() => { const el = (${js}); if (!el) return null; el.scrollIntoView({ block: 'center' }); const b = el.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2, w: b.width }; })()`);
    if (!r || !r.w) return false;
    await t.click(r.x, r.y);
    return true;
  };
  const sectionHead = (title) => `[...document.querySelectorAll('#learn-body .learn-section')].find((h) => h.querySelector('.ls-title').textContent === ${JSON.stringify(title)})`;
  const lessonEl = (title) => `[...document.querySelectorAll('#learn-body .lesson')].find((l) => l.querySelector('.lesson-title').textContent === ${JSON.stringify(title)})`;
  const openLesson = `document.querySelector('#learn-body .lesson.open')`;
  const activeTab = () => ev(`(document.querySelector('#tabs .tab.active') || {}).title || null`);

  // ---------------------------------------------------------------- a 1.0.4 profile's progress
  fs.writeFileSync(ctx.settingsFile, JSON.stringify({ ...settings(), learnDone: OLD_DONE, learnCurrent: 'mtgui-studio', learnOpen: ['basics', 'mtgui'] }, null, 2));
  await t.reload();
  await ev(`window.TuffPluginHost?.closePanel?.(); window.TuffIDE.showSideView('learn', true); 1`);
  await waitFor(`!!document.querySelector('#learn-body .learn-section')`);
  await t.sleep(400);

  const secs = await ev(`window.TuffLearn.sections()`);
  const titles = await ev(`[...document.querySelectorAll('#learn-body .learn-section .ls-title')].map((e) => e.textContent)`);
  check(`The sections are, in order: ${TITLES.join(', ')}`, JSON.stringify(titles) === JSON.stringify(TITLES) && JSON.stringify(secs.map((s) => s.title)) === JSON.stringify(TITLES), titles);
  const tags = await ev(`[...document.querySelectorAll('#learn-body .learn-section')].map((h) => !!h.querySelector('.ls-tag'))`);
  check('Every section but Basics is marked Optional', JSON.stringify(tags) === JSON.stringify([false, true, true, true, true, true]), tags);
  const fresh = secs.filter((s) => NEW.includes(s.id));
  check('Advanced apps, The internet and Games each have 5 to 9 lessons', fresh.length === 3 && fresh.every((s) => s.lessons.length >= 5 && s.lessons.length <= 9), fresh.map((s) => [s.id, s.lessons.length]));
  const games = fresh.find((s) => s.id === 'tgame');
  check('The last Games lesson is "Make your own game"', games && games.lessons.at(-1).title === 'Make your own game', games && games.lessons.map((l) => l.title));
  const files = secs.flatMap((s) => s.lessons.map((l) => l.file));
  const badNames = fresh.flatMap((s) => s.lessons.filter((l, i) => l.file !== `${s.id}-${String(i + 1).padStart(2, '0')}-${l.id.slice(s.id.length + 1)}.tuf`).map((l) => l.file));
  check('New lesson files are named <section>-<number>-<name>.tuf (atgui-01-window.tuf, tap-01-get.tuf, tgame-01-window.tuf...)',
    badNames.length === 0 && ['atgui-01-window.tuf', 'tap-01-get.tuf', 'tgame-01-window.tuf'].every((f) => files.includes(f)), { badNames, sample: files.filter((f) => /^(atgui|tap|tgame)-01/.test(f)) });
  check('Old lesson files keep their names (06-loops.tuf, tgui-08-build.tuf, mtgui-04-studio.tuf)', ['06-loops.tuf', 'tgui-08-build.tuf', 'mtgui-01-window.tuf', 'mtgui-04-studio.tuf'].every((f) => files.includes(f)), files.filter((f) => /^(\d|tgui|mtgui)/.test(f)));

  const total = secs.reduce((n, s) => n + s.lessons.length, 0);
  const progress = await ev(`document.querySelector('#lp-text').textContent`);
  check(`The old progress carries on: ${OLD_DONE.length} / ${total} lessons done`, progress === `${OLD_DONE.length} / ${total}`, progress);
  const modern = await ev(`(() => { const h = ${sectionHead('Section 2.1 · Modern apps')}; return { count: h.querySelector('.ls-count').textContent, open: h.classList.contains('open') }; })()`);
  const rows = await ev(`['Going modern', 'Gradients and themes', 'Design Studio'].map((t) => { const l = ${`[...document.querySelectorAll('#learn-body .lesson')]`}.find((x) => x.querySelector('.lesson-title').textContent === t); return l ? l.classList.contains('done') : null; })`);
  check('Modern apps (now Section 2.1) shows 2 / 4, with Going modern and Design Studio still done', modern.count === '2 / 4' && modern.open && JSON.stringify(rows) === '[true,false,true]', { modern, rows });
  const basics = await ev(`${sectionHead('Basics')}.querySelector('.ls-count').textContent`);
  check('Basics still shows its 2 finished lessons', basics === '2 / 10', basics);
  await t.shot('learn_sections.png');

  // ---------------------------------------------------------------- Section 2.2, from "Try Section 2.2"
  const tryBtn = await ev(`(() => { const b = ${openLesson}?.querySelector('[data-act="nextsection"]'); return b ? b.textContent.trim() : null; })()`);
  check('The finished last Modern apps lesson offers "Try Section 2.2"', tryBtn === 'Try Section 2.2', tryBtn);
  const atgui = fresh.find((s) => s.id === 'atgui');
  const atguiFile = path.join(LESSONS, atgui.lessons[0].file);
  await clickEl(`${openLesson}.querySelector('[data-act="nextsection"]')`);
  const madeA = await waitFor(`(document.querySelector('#tabs .tab.active') || {}).title === ${JSON.stringify(atguiFile)}`, 8000);
  const openA = await ev(`({ lesson: ${openLesson}?.querySelector('.lesson-title').textContent, section: ${sectionHead('Section 2.2 · Advanced apps')}.classList.contains('open') })`);
  check('Clicking it opens Section 2.2 at "Going advanced" and its file lessons/atgui-01-window.tuf, with the starter in it',
    madeA && openA.section && openA.lesson === 'Going advanced' && fs.existsSync(atguiFile) && norm(fs.readFileSync(atguiFile, 'utf8')) === norm(atgui.lessons[0].starter),
    { madeA, openA, active: await activeTab(), exists: fs.existsSync(atguiFile) });

  // ---------------------------------------------------------------- Sections 3 and 4, by clicking
  for (const [id, title] of [['tap', 'Section 3 · The internet'], ['tgame', 'Section 4 · Games']]) {
    const sec = fresh.find((s) => s.id === id);
    const first = sec.lessons[0];
    const file = path.join(LESSONS, first.file);
    await clickEl(sectionHead(title));
    await waitFor(`${sectionHead(title)}.classList.contains('open')`, 3000);
    const count = await ev(`${sectionHead(title)}.querySelector('.ls-count').textContent`);
    const shown = await ev(`(() => { const out = []; let el = ${sectionHead(title)}.nextElementSibling; while (el && el.classList.contains('lesson')) { out.push(el.querySelector('.lesson-title').textContent); el = el.nextElementSibling; } return out; })()`);
    check(`Clicking "${title}" opens it: ${sec.lessons.length} lessons, 0 / ${sec.lessons.length} done`, count === `0 / ${sec.lessons.length}` && JSON.stringify(shown) === JSON.stringify(sec.lessons.map((l) => l.title)), { count, shown });
    await clickEl(`${lessonEl(first.title)}.querySelector('.lesson-head')`);
    await waitFor(`${lessonEl(first.title)}.classList.contains('open')`, 3000);
    const content = await ev(`(() => { const l = ${lessonEl(first.title)}; return { task: l.querySelector('.lx-task')?.textContent || '', code: l.querySelector('.lx-code')?.textContent || '', start: l.querySelector('[data-act="open"]')?.textContent.trim() }; })()`);
    await clickEl(`${lessonEl(first.title)}.querySelector('[data-act="open"]')`);
    const made = await waitFor(`(document.querySelector('#tabs .tab.active') || {}).title === ${JSON.stringify(file)}`, 8000);
    check(`"${first.title}" shows its example and task, and Start lesson makes lessons/${first.file} with the starter`,
      made && content.start === 'Start lesson' && /YOUR TASK/.test(content.task) && content.code.includes(id === 'tap' ? 'tap.get' : 'tgame.window') && norm(fs.readFileSync(file, 'utf8')) === norm(first.starter),
      { made, content, active: await activeTab() });
  }
  await t.shot('learn_games_open.png');

  // ---------------------------------------------------------------- every new lesson's check
  const py = python();
  const outputs = {};
  let online = 0;
  for (const s of fresh) {
    for (const l of s.lessons) {
      outputs[l.id] = '';
      if (!TAP_RUN[l.id]) continue;
      // The console tap lessons' solutions, run for real when there's Python and the internet.
      const f = path.join(ctx.tmp, `${l.id}.tuf`);
      fs.writeFileSync(f, l.solution);
      const r = py ? spawnSync(py[0], [...py.slice(1), path.join(REPO, 'tuff.py'), f], { input: TAP_RUN[l.id].input || '', encoding: 'utf8', timeout: 30000, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }) : null;
      if (r && r.status === 0 && r.stdout.trim()) { outputs[l.id] = r.stdout; online++; } else outputs[l.id] = TAP_RUN[l.id].stand_in;
    }
  }
  t.info(`${online} of ${Object.keys(TAP_RUN).length} internet lessons ran for real; the rest use a stand-in output`);
  const verdicts = await ev(`(() => { const out = ${JSON.stringify(outputs)}; return window.TuffLearn.sections().filter((s) => ${JSON.stringify(NEW)}.includes(s.id)).flatMap((s) => s.lessons.map((l) => {
    const run = (src) => { try { return window.TuffLearn.check(l.id, src, out[l.id]); } catch (e) { return 'THREW ' + e.message; } };
    return { id: l.id, solution: run(l.solution), starter: run(l.starter), empty: run('') };
  })); })()`);
  for (const s of fresh) {
    const mine = verdicts.filter((v) => s.lessons.some((l) => l.id === v.id));
    const accepted = mine.filter((v) => v.solution === true).length;
    check(`${s.title}: every lesson's check accepts its solution (${accepted} / ${mine.length})`, accepted === mine.length, mine.filter((v) => v.solution !== true));
    const rejected = mine.filter((v) => typeof v.starter === 'string' && v.starter && !/^THREW/.test(v.starter) && typeof v.empty === 'string' && !/^THREW/.test(v.empty));
    check(`${s.title}: every lesson's check rejects its starter (and empty code) with a hint`, rejected.length === mine.length, mine.filter((v) => !rejected.includes(v)));
  }
  // A starter with the lesson's answers written in its # comments still isn't accepted.
  const commented = await ev(`window.TuffLearn.check('tgame-own', '# game:held("left") star:touches(basket) score += 1 game:game_over("x", start)\\nmention tgame\\ngame = tgame.window("G")\\n')`);
  check('Checks ignore # comments: code that only mentions the answers in comments gets a hint', commented !== true && /control/.test(commented), commented);
  // The Tuff Engine lesson: a coin or an enemy that's there without its behaviour (taken off in the Inspector) gets
  // a hint to give it back, not one to add a coin or an enemy, which would only make a second one.
  const engineGame = secs.flatMap((s) => s.lessons).find((l) => l.id === 'tgame-engine').solution;
  const withoutFn = (code, fn) => code.replace(new RegExp(`\\ngame:every_frame ${fn}\\n`), '\n').replace(new RegExp(`\\n# Tuff Engine: [^\\n]*\\nfunc ${fn}\\(dt\\):\\n(?:    [^\\n]*\\n)+`), '\n');
  const noCollect = withoutFn(engineGame, 'coin_collect');
  const noHurts = withoutFn(withoutFn(engineGame, 'enemy_hurts'), 'enemy_chase');
  const hints = await ev(`[${JSON.stringify(noCollect)}, ${JSON.stringify(noHurts.replace(/^enemy = .*\n/m, ''))}, ${JSON.stringify(noHurts)}].map((src) => window.TuffLearn.check('tgame-engine', src))`);
  check('Tuff Engine lesson: a coin without Collect it gets "Select your coin … Add behaviour", an enemy without Game over the same, and no enemy at all "Add an Enemy"',
    /^Select your coin in Tuff Engine/.test(hints[0]) && /^Add an Enemy too/.test(hints[1]) && /^Select your enemy in Tuff Engine/.test(hints[2]) && !/coin_collect/.test(noCollect) && !/enemy_hurts/.test(noHurts), hints);
  // PokéAPI lists come a page at a time: an address with no name gets the first 20, not every Pokémon.
  const tapOk = secs.flatMap((s) => s.lessons).find((l) => l.id === 'tap-ok');
  check('"When it goes wrong" says an address with no name gets a list of the first 20 Pokémon (not every one)', /a list of Pokémon instead \(just the first 20\)/.test(tapOk.body) && !/every Pokémon/.test(tapOk.body), tapOk.body);

  // ---------------------------------------------------------------- tuff --check on every lesson's code
  const failed = [];
  let checked = 0;
  for (const s of secs) {
    for (const l of s.lessons) {
      for (const [kind, code] of [['example', l.example], ['starter', l.starter], ['solution', l.solution]]) {
        if (!code) continue; // the Build an .exe lesson has no starter
        const f = path.join(ctx.tmp, `check_${l.id}_${kind}.tuf`);
        fs.writeFileSync(f, code);
        const out = ctx.tuffCheck(f);
        checked++;
        if (!/^OK\b/.test(out.trim())) failed.push({ lesson: l.id, kind, out: out.trim().slice(0, 300) });
      }
    }
  }
  check(`Every lesson's example, starter and solution passes tuff --check (${checked} programs)`, checked > 100 && failed.length === 0, failed.slice(0, 6));

  // ---------------------------------------------------------------- the first Games lesson, run from its Run button
  const hasWebview = ctx.packaged || (py && spawnSync(py[0], [...py.slice(1), '-c', 'import webview'], { windowsHide: true }).status === 0);
  const g1 = games.lessons[0];
  const g1File = path.join(LESSONS, g1.file);
  const runFromLesson = async (title) => {
    await ev(`window.__learnRuns = (window.__learnRuns || 0); if (!window.__learnRunHook) { window.__learnRunHook = true; window.addEventListener('tuff:run-finished', () => { window.__learnRuns++; }); } 1`);
    const before = await ev(`window.__learnRuns`);
    await clickEl(`${lessonEl(title)}.querySelector('[data-act="run"]')`);
    const ended = await waitFor(`window.__learnRuns > ${before}`, 60000);
    await t.sleep(400);
    return ended;
  };
  const statusOf = (title) => ev(`(() => { const l = ${lessonEl(title)}; const s = l?.querySelector('.lx-status'); return { done: l?.classList.contains('done'), cls: s?.className || null, text: s?.textContent.trim() || null }; })()`);
  if (!hasWebview) {
    t.skip('running "Your first game" from the lesson', 'the Python that runs tuff.py has no pywebview (py -m pip install pywebview)');
  } else {
    fs.mkdirSync(path.dirname(PLAN), { recursive: true });
    fs.writeFileSync(PLAN, JSON.stringify({ on_top: true, timeout: 20, steps: [{ at: 1.0, shot: 'learn_tgame_window.png' }, { at: 1.4, close: true }] }));
    await clickEl(`${lessonEl(g1.title)}.querySelector('.lesson-head')`);
    if (!(await ev(`${lessonEl(g1.title)}.classList.contains('open')`))) await clickEl(`${lessonEl(g1.title)}.querySelector('.lesson-head')`);
    // The starter: it runs, but the lesson isn't finished, and the hint says what's missing.
    const ran1 = await runFromLesson(g1.title);
    const s1 = await statusOf(g1.title);
    check('Running the starter of "Your first game" shows a hint and leaves the lesson unfinished',
      ran1 && !s1.done && /fail/.test(s1.cls || '') && /tgame\.window/.test(s1.text || ''), s1);
    // The solution, typed into the lesson's tab: the game opens, the autopilot closes it, the lesson is done.
    if ((await activeTab()) !== g1File) await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(g1File)}); return 1; })()`);
    await t.setCode(g1.solution);
    const t0 = Date.now();
    const ran2 = await runFromLesson(g1.title);
    await waitFor(`${lessonEl(g1.title)}?.classList.contains('done')`, 4000);
    const s2 = await statusOf(g1.title);
    const out = await ev(`document.querySelector('#run-output').innerText`);
    const toasts = await ev(`[...document.querySelectorAll('.toast')].map((x) => x.textContent.trim())`);
    check(`Running the solution opens the game, which closes itself, and the lesson is done (${((Date.now() - t0) / 1000).toFixed(1)} s)`,
      ran2 && s2.done && /pass/.test(s2.cls || '') && /exit code 0/.test(out) && norm(fs.readFileSync(g1File, 'utf8')) === norm(g1.solution), { s2, out: out.slice(-300) });
    check('The toast names the section: "Section 4 · Lesson 1 complete: Your first game"', toasts.some((x) => x.includes('Section 4 · Lesson 1 complete: Your first game')), toasts);
    const saved = settings().learnDone || [];
    check('Saved progress keeps every old lesson and adds tgame-window', [...OLD_DONE, 'tgame-window'].every((id) => saved.includes(id)), saved);
    const games4 = await ev(`${sectionHead('Section 4 · Games')}.querySelector('.ls-count').textContent`);
    check(`Section 4 shows 1 / ${games.lessons.length}`, games4 === `1 / ${games.lessons.length}`, games4);
    await t.shot('learn_tgame_done.png');
  }

  // ---------------------------------------------------------------- the first internet lesson, for real when online
  if (!online) {
    t.skip('running "Your first request" from the lesson', 'no internet (or no Python) here');
  } else {
    const tap = fresh.find((s) => s.id === 'tap').lessons[0];
    const tapFile = path.join(LESSONS, tap.file);
    await clickEl(`${lessonEl(tap.title)}.querySelector('.lesson-head')`);
    if (!(await ev(`${lessonEl(tap.title)}.classList.contains('open')`))) await clickEl(`${lessonEl(tap.title)}.querySelector('.lesson-head')`);
    await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(tapFile)}); return 1; })()`);
    await t.setCode(tap.solution);
    const ran = await runFromLesson(tap.title);
    await waitFor(`${lessonEl(tap.title)}?.classList.contains('done')`, 4000);
    const st = await statusOf(tap.title);
    const out = await ev(`document.querySelector('#run-output').innerText`);
    if (ran && !st.done && /hit an error/.test(st.text || '')) t.skip('"Your first request" from the lesson', `the request failed here: ${out.slice(-200)}`);
    else check('Running "Your first request" for real finishes the lesson', ran && st.done && /pass/.test(st.cls || ''), { st, out: out.slice(-300) });
  }
  const after = settings();
  check('The Modern apps lessons are still done at the end', ['mtgui-window', 'mtgui-studio'].every((id) => (after.learnDone || []).includes(id)), after.learnDone);
};
