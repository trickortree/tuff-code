// The Creativity Update (1.3.2): say:color, say:ascii and print:pen in the Run panel. Colours and the bar behind a
// line, rainbow letters, big ASCII-art letters in each font, a big-letter score that changes, and every animation.
// With TUFF_SHOWCASE=<folder> it also films each animation there (frames of the Run panel, for the showcase GIFs).
import fs from 'node:fs';
import path from 'node:path';

export const meta = { title: 'The Creativity Update: colours, ASCII art and animations' };

const EFFECTS = { fade: 'FADE IN', build: 'BUILD IT', explode: 'GAME OVER', assemble: 'YOU WIN', type: 'HELLO', glitch: 'HACKED', drop: 'TUFF', wave: 'CREATIVE' };

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const film = process.env.TUFF_SHOWCASE;
  const rect = (sel) => ev(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);
  const lines = () => ev(`[...document.querySelectorAll('#run-output .tline')].map(s => ({ text: s.textContent, cls: s.className, color: s.style.color, bg: s.style.backgroundColor, weight: s.style.fontWeight, kids: [...s.querySelectorAll('span')].map(k => k.style.color), white: getComputedStyle(s).whiteSpace, display: getComputedStyle(s).display, width: s.getBoundingClientRect().width }))`);

  async function run(name, code, waitDone = true) {
    const file = path.join(ctx.root, name);
    fs.writeFileSync(file, code);
    await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(file)}); return 1; })()`);
    await t.sleep(300);
    await ev(`document.querySelector('#run-output').replaceChildren(); document.querySelector('#btn-run').click(); 1`);
    if (waitDone) await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running') && !!document.querySelector('#run-output .done')`, 20000);
  }

  // Filming: a taller Run panel, and pictures from a program's first line down (not the command above it)
  if (film) await ev(`document.documentElement.style.setProperty('--bottom-h', '560px'); 1`);
  const below = async (first) => {
    const area = await rect('#run-output');
    const top = await ev(`(() => { const s = [...document.querySelectorAll('#run-output .tline')].find(x => x.textContent === ${JSON.stringify(first)}); return s ? s.getBoundingClientRect().top - 6 : null; })()`);
    return top == null ? area : { x: area.x, y: top, width: area.width, height: area.y + area.height - top };
  };

  // Colours, the bar, styles, rainbow and print:pen
  await run('looks.tuf', [
    'say:color("Game over!", "red")',
    'say:color("LEVEL UP", "white", "green", "bold")',
    'say:color("WINNER", "rainbow")',
    'print:pen("cyan")',
    'say "this is cyan"',
    'print:pen()',
    'say "back to normal"',
  ].join('\n') + '\n');
  const looks = await lines();
  const by = (text) => looks.find((l) => l.text === text) || {};
  check('say:color("Game over!", "red"): the line is red', by('Game over!').color === 'rgb(229, 72, 77)', by('Game over!'));
  check('A second colour is a bar behind the whole line, and bold is bold', by('LEVEL UP').bg === 'rgb(34, 163, 90)' && by('LEVEL UP').color === 'rgb(255, 255, 255)' && by('LEVEL UP').weight === '700' && by('LEVEL UP').display === 'inline-block', by('LEVEL UP'));
  check('rainbow gives each letter its own colour', by('WINNER').kids.length === 6 && new Set(by('WINNER').kids).size === 6, by('WINNER'));
  const hue = () => ev(`getComputedStyle([...document.querySelectorAll('#run-output .tline.rainbow > span')][0]).filter`);
  const h1 = await hue();
  await t.sleep(400);
  const h2 = await hue();
  check('...and the rainbow keeps moving after the program ends (its hue turns)', /hue-rotate/.test(h1) && h1 !== h2, { h1, h2 });
  // A PC with Windows' Animation effects off says "reduce motion": the rainbow still flows there, slower
  await t.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  const r1 = await hue();
  await t.sleep(400);
  const r2 = await hue();
  const slow = await ev(`getComputedStyle([...document.querySelectorAll('#run-output .tline.rainbow > span')][0]).animationDuration`);
  check('With "reduce motion" on, the rainbow still flows, slowly', /hue-rotate/.test(r1) && r1 !== r2 && slow === '9s', { r1, r2, slow });
  await t.send('Emulation.setEmulatedMedia', { features: [] });
  check('print:pen("cyan") colours the lines after it, and print:pen() stops it', by('this is cyan').color === 'rgb(34, 211, 238)' && by('back to normal').color === '', [by('this is cyan'), by('back to normal')]);
  await t.shot('looks.png', await below('Game over!'));

  // 1.3.6: rainbows share one clock (a rewrite carries on at the same colours), and :play / :rewrite animate a line
  // where it is instead of saying a new one
  await run('play.tuf', [
    'one = say:color("ONE", "rainbow")',
    'wait(1)',
    'two = say:color("TWO", "rainbow")',
    'title = say:ascii("BOOM", "sky")',
    'title:play("explode")',
    'title:rewrite("BACK", "assemble", "gold")',
  ].join('\n') + '\n');
  const phases = await ev(`[...document.querySelectorAll('#run-output .tline.rainbow')].map((s) => getComputedStyle(s.firstElementChild).filter)`);
  const deg = (f) => Number((/hue-rotate\((-?[\d.]+)deg\)/.exec(f) || [])[1]);
  const apart = Math.abs(deg(phases[0]) - deg(phases[1])) % 360;
  check('Two rainbows said a second apart flow in step (one clock for every rainbow)', phases.length === 2 && Math.min(apart, 360 - apart) < 20, phases);
  const played = await lines();
  const bigs = played.filter((l) => l.cls.includes("art"));
  check(':play and :rewrite animate the big line where it is: no new line, and it ends as BACK in gold', bigs.length === 1 && bigs[0].text.includes("█") && bigs[0].color === "rgb(242, 194, 48)", played.map((l) => l.text.slice(0, 20)));

  // Big letters in every font, and a score that changes
  await run('fonts.tuf', [
    'for font in ["block", "wide", "small", "shadow", "led", "hash"]:',
    '    say:ascii("TUFF " + font, font, "sky")',
    'score = say:ascii("0", "small", "gold")',
    'score:rewrite(42)',
  ].join('\n') + '\n');
  const fonts = await lines();
  const art = fonts.filter((l) => l.cls.includes('art'));
  check('say:ascii draws big letters in each font (6 fonts and the score)', art.length === 7 && art[0].text.includes('█') && art[4].text.includes('●') && art[5].text.includes('#'), art.map((a) => a.text.split('\n')[0].slice(0, 30)));
  check('Big letters keep their rows: they don\'t wrap', art.every((a) => a.white === 'pre'), art.map((a) => a.white));
  check('score:rewrite(42) redraws the big score as 42, still gold', art[6] && art[6].color === 'rgb(242, 194, 48)' && art[6].text.split('\n').length === 3 && art[6].text.length > 20, art[6]);
  await t.shot('fonts.png', await below(art[0] && art[0].text));

  // Every animation: it plays, then shows how it ends (explode leaves nothing)
  for (const [effect, text] of Object.entries(EFFECTS)) {
    const color = effect === 'explode' ? ', "red"' : effect === 'wave' ? '' : ', "sky"';
    await run(`anim_${effect}.tuf`, `say "${effect}:"\nsay:ascii("${text}", "${effect}"${color})\nsay "done"\n`, false);
    const frames = [];
    const started = Date.now();
    await t.waitFor(`[...document.querySelectorAll('#run-output .tline')].length >= 2`, 15000, 20);
    const area = await below(`${effect}:`);
    const dir = film && path.join(film, effect);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    const snap = async () => frames.push({ at: Date.now() - started, data: (await t.send('Page.captureScreenshot', { format: 'png', clip: { ...area, scale: 1 } })).data });
    while (Date.now() - started < 9000) {
      if (film) await snap();
      if (await ev(`[...document.querySelectorAll('#run-output .tline')].some(s => s.textContent === 'done')`)) break;
      if (!film) await t.sleep(50);
    }
    if (film) {
      await t.sleep(900); // how it ends, held
      await snap();
      frames.forEach((f, i) => fs.writeFileSync(path.join(dir, String(i).padStart(3, '0') + '.png'), Buffer.from(f.data, 'base64')));
      fs.writeFileSync(path.join(dir, 'times.json'), JSON.stringify(frames.map((f) => f.at)));
      t.info(`${effect}: ${frames.length} frames in ${((Date.now() - started) / 1000).toFixed(1)} s`);
    }
    await t.waitFor(`!document.querySelector('#btn-run').classList.contains('running')`, 15000);
    const end = (await lines()).find((l) => l.cls.includes('art'));
    const shows = effect === 'explode' ? end && end.text.trim() === '' : end && end.text.includes('█');
    check(`${effect}: it plays and ends ${effect === 'explode' ? 'with the letters gone' : 'as the big letters'}`, !!shows, end && end.text.slice(0, 80));
    await t.shot(`anim_${effect}.png`, await rect('#run-output'));
  }
};
