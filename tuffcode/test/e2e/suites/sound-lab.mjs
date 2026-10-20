// Sound Lab: installs it from the marketplace and uses it like a person would, with real clicks and typing.
// Makes every preset and saves it into the scratch project's sounds folder, then reads each .wav back here
// (RIFF header, PCM 16-bit mono 44.1 kHz, length, not silent, in range, the settings chunk) and with Python's
// wave module. Checks that sliders and the wave buttons change the bytes (and the same settings give the same
// bytes), that Play works after a real click, the list of saved sounds, "Use in code" (the line goes into the
// editor and passes tuff --check in a small tgame program, with a negative control), the subfolder copy, the
// test game, and that the settings come back after a restart. Screenshots of the sidebar at 400 and 300 px.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { python } from '../launch.mjs';

export const meta = { title: 'Sound Lab: game sound effects saved as .wav files', timeout: 300000 };

const PRESETS = ['coin', 'jump', 'laser', 'explosion', 'powerup', 'hit', 'blip', 'random'];
const MARK = 'TuffCode Sound Lab settings: ';

const MAIN = `mention tgame

arcade = tgame.window("Coin catcher", 600, 400)
arcade:background "navy"
player = arcade:box(300, 370, 60, 20, "gold")
coin = arcade:circle(300, 0, 12, "yellow")
score = 0

func step(dt):
    if arcade:held("left"):
        player:move(-300 * dt, 0)
    if arcade:held("right"):
        player:move(300 * dt, 0)
    coin:move(0, 180 * dt)
    if coin:touches(player):
        score += 1
        coin:move_to(random(20, 580), 0)
    elif coin:y() > 400:
        coin:move_to(random(20, 580), 0)

arcade:every_frame step
`;
const AFTER_LINE = 16; // "score += 1": the test presses Enter at its end, and the sound goes on the new line

const LEVEL = `mention tgame

game = tgame.window("Level 1", 400, 300)
game:background "teal"
`;

// A plain .wav that Sound Lab didn't make (no settings chunk): 0.2 s of a 440 Hz tone.
function plainWav() {
  const n = 8820;
  const b = Buffer.alloc(44 + n * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVE', 8);
  b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(44100, 24); b.writeUInt32LE(88200, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34);
  b.write('data', 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(Math.sin((2 * Math.PI * 440 * i) / 44100) * 8000 * (1 - i / n)), 44 + i * 2);
  return b;
}

// Reads a .wav the long way: every chunk, the format, the samples and a few numbers about them.
function parseWav(buf) {
  const id = (o) => buf.toString('ascii', o, o + 4);
  const out = { riff: id(0), wave: id(8), riffSize: buf.readUInt32LE(4), fileSize: buf.length, chunks: [] };
  let at = 12;
  while (at + 8 <= buf.length) {
    const name = id(at), size = buf.readUInt32LE(at + 4), body = at + 8;
    out.chunks.push(name);
    if (name === 'fmt ') {
      out.fmt = { format: buf.readUInt16LE(body), channels: buf.readUInt16LE(body + 2), rate: buf.readUInt32LE(body + 4), byteRate: buf.readUInt32LE(body + 8), align: buf.readUInt16LE(body + 12), bits: buf.readUInt16LE(body + 14) };
    } else if (name === 'data') {
      out.dataSize = size;
      out.data = buf.subarray(body, body + size);
    } else if (name === 'LIST') out.list = buf.toString('latin1', body, body + size);
    at = body + size + (size & 1);
  }
  out.endsAt = at;
  if (out.data) {
    const n = out.data.length >> 1;
    let peak = 0, sum = 0, top = 0;
    for (let i = 0; i < n; i++) {
      const s = out.data.readInt16LE(i * 2);
      const a = Math.abs(s);
      if (a > peak) peak = a;
      if (a >= 32767) top++;
      sum += s * s;
    }
    Object.assign(out, { samples: n, peak, rms: Math.sqrt(sum / Math.max(1, n)) / 32768, top });
  }
  if (out.list) {
    const i = out.list.indexOf(MARK);
    if (i >= 0) { try { out.settings = JSON.parse(out.list.slice(i + MARK.length, out.list.indexOf('\0', i))); } catch {} }
    out.software = /ISFT[\s\S]{4}TuffCode Sound Lab\0/.test(out.list);
  }
  return out;
}

export default async (t, ctx) => {
  const check = t.check;
  const ev = (js) => t.eval(js);
  const waitFor = (js, ms = 10000) => t.waitFor(js, ms);
  const P = `document.querySelector('.rb-panel[data-panel="sound-lab:lab"]')`;
  const sl = `${P}?.querySelector('.sl')`;
  const SL = `${P}.querySelector('.sl')`; // for assignments
  const data = (k) => ev(`${P}?.dataset[${JSON.stringify(k)}] ?? null`);
  const sounds = path.join(ctx.root, 'sounds');
  const file = (rel) => path.join(ctx.root, ...rel.split('/'));

  // Where an element is on screen (scrolled into the middle of its panel), and whether a click there reaches it.
  const spot = (sel, frac = 0.5) => ev(`(() => {
    const el = document.querySelector(${JSON.stringify(sel)});
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    document.querySelectorAll('.toast').forEach((x) => x.remove());
    const r = el.getBoundingClientRect();
    const x = r.left + r.width * ${frac}, y = r.top + r.height / 2;
    const hit = document.elementFromPoint(x, y);
    return { x, y, ok: !!hit && (hit === el || el.contains(hit)) };
  })()`);
  // A real mouse click (CDP Input events) on the element.
  const click = async (sel, frac) => {
    const p = await spot(sel, frac);
    if (!p) throw new Error(`Nothing on the page matches ${sel}`);
    if (!p.ok) t.info(`${sel} looks covered at ${Math.round(p.x)}, ${Math.round(p.y)}`);
    await t.click(p.x, p.y);
    return p;
  };
  const inPanel = (s) => `.rb-panel[data-panel="sound-lab:lab"] ${s}`;
  const row = (rel, a) => inPanel(`.sl-item[data-rel="${rel}"] [data-a="${a}"]`);
  const plays = async () => +(await data('plays')) || 0;
  const sliderValue = (k) => ev(`+${P}.querySelector('input[data-k="${k}"]').value`);

  // Types a name into the name box (click it, select what's there, type) and clicks "Save as .wav".
  async function saveAs(name) {
    await click(inPanel('.sl-name'));
    await ev(`${P}.querySelector('.sl-name').select()`);
    await t.type(name, 15);
    const before = +(await data('saves')) || 0;
    await click(inPanel('[data-a="save"]'));
    const rel = `sounds/${name}.wav`;
    const ok = await waitFor(`(+${P}.dataset.saves || 0) > ${before} && ${P}.dataset.saved === ${JSON.stringify(rel)}`, 10000);
    return ok && fs.existsSync(file(rel)) ? fs.readFileSync(file(rel)) : null;
  }

  // tuff --check outside the temp folder (it skips the "is the file there" check for files in temp).
  const checkDir = (name) => { const d = path.join(ctx.out, name); fs.rmSync(d, { recursive: true, force: true }); fs.mkdirSync(path.join(d, 'sounds'), { recursive: true }); return d; };

  // ---------------------------------------------------------------- 1. install from the marketplace
  const mainPath = path.join(ctx.root, 'main.tuf');
  fs.writeFileSync(mainPath, MAIN);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(mainPath)}); return 1; })()`);
  await t.sleep(400);
  await click('.ts-btn[data-tool="plugins"]');
  await waitFor(`!!document.querySelector('.pl-card[data-id="sound-lab"]')`, 8000);
  const cardText = await ev(`document.querySelector('.pl-card[data-id="sound-lab"]')?.textContent || ''`);
  check('The marketplace lists Sound Lab as a built-in plugin', /Sound Lab/.test(cardText) && /comes with TuffCode/.test(cardText) && /\.wav/.test(cardText), cardText.slice(0, 300));
  await click('.pl-card[data-id="sound-lab"] [data-a="install"]');
  const opened = await waitFor(`!document.querySelector('#rightbar').classList.contains('hidden') && !!${sl} && document.querySelector('#rb-title').textContent === 'Sound Lab'`, 15000);
  const shape = await ev(`(() => { const p = ${P}; return { presets: p.querySelectorAll('[data-preset]').length, waves: [...p.querySelectorAll('[data-wave]')].map(b => b.textContent.trim()), simple: p.querySelectorAll('.sl > .sl-row').length, advanced: p.querySelectorAll('.sl-adv .sl-row').length, labels: [...p.querySelectorAll('.sl > .sl-row .sl-lbl')].map(x => x.textContent), samples: +p.dataset.samples, width: Math.round(document.querySelector('#rightbar').getBoundingClientRect().width) }; })()`);
  check('Installing it opens the Sound Lab panel on the right', opened, await ev(`window.TuffPluginHost.state()`));
  check('It has 8 presets, the 4 waves and the 9 simple sliders with friendly names, plus 11 advanced ones',
    shape.presets === 8 && shape.waves.join() === 'Square,Saw,Sine,Noise' && shape.simple === 9 && shape.advanced === 11
    && ['Start pitch', 'Pitch slide', 'Vibrato', 'Attack', 'Sustain', 'Decay', 'Volume', 'Repeat', 'Arpeggio jump'].every((l) => shape.labels.includes(l)) && shape.samples > 0, shape);
  const drawn = await ev(`(() => { const c = ${P}.querySelector('.sl-canvas'); const g = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < g.length; i += 4) if (g[i]) n++; return { w: c.width, h: c.height, painted: n }; })()`);
  check('A drawing of the waveform shows before anything is played', drawn.w > 100 && drawn.painted > drawn.w, drawn);

  // ---------------------------------------------------------------- 2. every preset, saved and read back
  const files = {};
  let autoPlays = true;
  for (const kind of PRESETS) {
    const before = await plays();
    await click(inPanel(`[data-preset="${kind}"]`));
    if (!(await waitFor(`(+${P}.dataset.plays || 0) > ${before}`, 5000))) autoPlays = false;
    const expect = { samples: +(await data('samples')), wave: await data('soundWave') };
    const buf = await saveAs(`e2e_${kind}`);
    files[kind] = { buf, expect, wav: buf ? parseWav(buf) : null };
  }
  const all = Object.entries(files);
  check('Clicking a preset plays it (Web Audio after a real click), with no errors', autoPlays && !(await data('playError')) && (await data('audio')) === 'running', { plays: await plays(), audio: await data('audio'), err: await data('playError') });
  check('Every preset saves a .wav into the project\'s sounds folder', all.every(([, f]) => f.buf), all.map(([k, f]) => `${k}:${!!f.buf}`));
  const headerBad = all.filter(([, { wav: w }]) => !w || w.riff !== 'RIFF' || w.wave !== 'WAVE' || w.riffSize !== w.fileSize - 8 || w.endsAt !== w.fileSize
    || w.chunks.join() !== 'fmt ,data,LIST' || !w.fmt || w.fmt.format !== 1 || w.fmt.channels !== 1 || w.fmt.rate !== 44100 || w.fmt.bits !== 16 || w.fmt.byteRate !== 88200 || w.fmt.align !== 2);
  check('RIFF/WAVE header: PCM, mono, 44100 Hz, 16-bit, byte rate 88200, block align 2, RIFF size = file size - 8', !headerBad.length, headerBad.map(([k, f]) => [k, f.wav && { ...f.wav, data: undefined, list: undefined }]));
  const lengths = all.map(([k, f]) => [k, f.wav?.samples, f.expect.samples, +((f.wav?.samples || 0) / 44100).toFixed(3)]);
  check('Each file is as long as the sound in the panel, between 0.02 and 4 seconds', lengths.every(([, got, want, s]) => got === want && s >= 0.02 && s <= 4) && all.every(([, f]) => f.wav.dataSize === f.wav.samples * 2), lengths);
  const levels = all.map(([k, f]) => [k, f.wav?.peak, +(f.wav?.rms || 0).toFixed(4), f.wav?.top, f.wav?.samples]);
  check('None is silent: the loudest sample is over 10% and the average level over 1%', levels.every(([, peak, rms]) => peak > 3277 && rms > 0.01), levels);
  check('All stay in range: hardly any samples (under 0.1%) reach the 16-bit limit (the synth has a soft ceiling)', levels.every(([, peak, , top, count]) => peak <= 32767 && top / Math.max(1, count) < 0.001), levels);
  check('Each file keeps its settings in a LIST/INFO chunk (to open it again), with the right wave',
    all.every(([, f]) => f.wav.software && f.wav.settings && f.wav.settings.wave === f.expect.wave && typeof f.wav.settings.pitch === 'number'), all.map(([k, f]) => [k, f.wav.settings?.wave, f.expect.wave, f.wav.software]));
  check('The 8 presets make 8 different sounds', new Set(all.map(([, f]) => f.wav.data.toString('base64'))).size === 8, null);
  const py = python();
  if (py) {
    const code = 'import sys, wave\nfor f in sys.argv[1:]:\n    w = wave.open(f)\n    print(w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())';
    const r = spawnSync(py[0], [...py.slice(1), '-I', '-c', code, ...PRESETS.map((k) => file(`sounds/e2e_${k}.wav`))], { encoding: 'utf8', windowsHide: true });
    const want = PRESETS.map((k) => `1 2 44100 ${files[k].wav.samples}`).join('\n');
    check("Python's wave module reads every file the same way", r.status === 0 && r.stdout.trim().replace(/\r/g, '') === want, { out: r.stdout, err: r.stderr, want });
  } else t.skip("Python's wave module reads the files", 'no Python found');

  // ---------------------------------------------------------------- 3. the sliders and waves change the sound
  await click(inPanel('[data-preset="coin"]'));
  await t.sleep(200);
  const base = parseWav(await saveAs('e2e_base'));
  const canvasBefore = await ev(`${P}.querySelector('.sl-canvas').toDataURL()`);
  const pitch0 = { v: await sliderValue('pitch'), label: await ev(`${P}.querySelector('[data-row="pitch"] output').textContent`) };
  await click(inPanel('input[data-k="pitch"]'), pitch0.v > 0.5 ? 0.15 : 0.9);
  await t.sleep(200);
  const pitch1 = { v: await sliderValue('pitch'), label: await ev(`${P}.querySelector('[data-row="pitch"] output').textContent`) };
  const higher = parseWav(await saveAs('e2e_pitch'));
  const canvasAfter = await ev(`${P}.querySelector('.sl-canvas').toDataURL()`);
  check('Moving "Start pitch" with the mouse changes its value, its label and the waveform drawing', pitch1.v !== pitch0.v && pitch1.label !== pitch0.label && /Hz$/.test(pitch1.label) && canvasBefore !== canvasAfter, { pitch0, pitch1 });
  check('... and the saved file has different bytes', base.data && higher.data && !base.data.equals(higher.data), { base: base.samples, higher: higher.samples });

  const wave0 = await data('soundWave');
  const other = wave0 === 'sine' ? 'saw' : 'sine';
  await click(inPanel(`[data-wave="${other}"]`));
  await t.sleep(200);
  const waved = parseWav(await saveAs('e2e_wave'));
  const waveOn = await ev(`${P}.querySelector('[data-wave="${other}"]').classList.contains('on') && ${P}.querySelector('[data-wave="${other}"]').getAttribute('aria-checked') === 'true'`);
  check(`Clicking the ${other} wave picks it and changes the bytes again`, waveOn && waved.settings?.wave === other && !waved.data.equals(higher.data), { waveOn, wave: waved.settings?.wave });

  const slide0 = await sliderValue('decay');
  await click(inPanel('input[data-k="decay"]'), slide0 > 0.5 ? 0.2 : 0.85);
  await t.sleep(200);
  const decayed = parseWav(await saveAs('e2e_decay'));
  check('"Decay" changes how long the sound is', decayed.samples !== waved.samples && (await sliderValue('decay')) !== slide0, { before: waved.samples, after: decayed.samples });

  await click(inPanel('.sl-adv summary'));
  await t.sleep(200);
  const advOpen = await ev(`${P}.querySelector('.sl-adv').open`);
  await click(inPanel('input[data-k="lowpass"]'), 0.8);
  await t.sleep(200);
  const muffled = parseWav(await saveAs('e2e_muffle'));
  check('The Advanced section opens, and its "Muffle" slider changes the bytes too', advOpen && (await sliderValue('lowpass')) > 0.5 && !muffled.data.equals(decayed.data) && muffled.settings?.lowpass > 0.5, { advOpen, lowpass: await sliderValue('lowpass') });
  const again = parseWav(await saveAs('e2e_muffle_again'));
  check('The same settings always make exactly the same bytes', again.data.equals(muffled.data), null);
  await click(inPanel('.sl-adv summary'));

  // "Make another" and "Change a little"
  const s0 = await ev(`JSON.stringify([...${P}.querySelectorAll('input[type=range]')].map(i => i.value))`);
  await click(inPanel('[data-a="another"]'));
  await t.sleep(200);
  const s1 = await ev(`JSON.stringify([...${P}.querySelectorAll('input[type=range]')].map(i => i.value))`);
  await click(inPanel('[data-a="nudge"]'));
  await t.sleep(200);
  const s2 = await ev(`JSON.stringify([...${P}.querySelectorAll('input[type=range]')].map(i => i.value))`);
  check('"Make another" and "Change a little" both give new settings', s0 !== s1 && s1 !== s2 && (await ev(`${P}.querySelector('[data-preset="coin"]').classList.contains('on')`)), { s0, s1, s2 });

  // ---------------------------------------------------------------- 4. Play
  const p0 = await plays();
  const eventsBefore = t.events.length;
  await click(inPanel('[data-a="play"]'));
  const played = await waitFor(`(+${P}.dataset.plays || 0) > ${p0}`, 5000);
  await t.sleep(60);
  await click(inPanel('[data-a="play"]')); // again while it's still playing: starts over
  await waitFor(`(+${P}.dataset.plays || 0) > ${p0 + 1}`, 5000);
  const exceptions = t.events.slice(eventsBefore).filter((e) => /^\[exception\]/.test(e));
  check('Play (a real click) plays the sound with Web Audio, twice in a row, and nothing throws',
    played && (await plays()) === p0 + 2 && (await data('audio')) === 'running' && !(await data('playError')) && !exceptions.length, { plays: await plays(), audio: await data('audio'), err: await data('playError'), exceptions });

  // ---------------------------------------------------------------- 5. the list of saved sounds
  fs.writeFileSync(path.join(sounds, 'plain_beep.wav'), plainWav());
  await click(inPanel('[data-a="refresh"]'));
  await waitFor(`!!${P}.querySelector('.sl-item[data-rel="sounds/plain_beep.wav"]') && !!${P}.querySelector('.sl-item[data-rel="sounds/e2e_coin.wav"] [data-a="edit"]')`, 8000);
  const listed = await ev(`[...${P}.querySelectorAll('.sl-item')].map(x => ({ rel: x.dataset.rel, edit: !!x.querySelector('[data-a="edit"]'), play: !!x.querySelector('[data-a="playfile"]'), use: !!x.querySelector('[data-a="use"]') }))`);
  const wanted = [...PRESETS.map((k) => `sounds/e2e_${k}.wav`), 'sounds/e2e_base.wav', 'sounds/e2e_pitch.wav', 'sounds/plain_beep.wav'];
  check('"Sounds in this project" lists every saved sound with Play and Use buttons', wanted.every((r) => listed.some((x) => x.rel === r && x.play && x.use)), listed);
  check('Sound Lab\'s own sounds get an Edit button, a .wav from elsewhere doesn\'t', listed.filter((x) => x.rel.startsWith('sounds/e2e_')).every((x) => x.edit) && listed.find((x) => x.rel === 'sounds/plain_beep.wav')?.edit === false, listed);
  let n = await plays();
  await click(row('sounds/e2e_explosion.wav', 'playfile'));
  const playedSaved = await waitFor(`(+${P}.dataset.plays || 0) > ${n}`, 5000);
  n = await plays();
  await click(row('sounds/plain_beep.wav', 'playfile'));
  const playedPlain = await waitFor(`(+${P}.dataset.plays || 0) > ${n}`, 5000);
  check('The list\'s Play buttons play a saved Sound Lab sound and a plain .wav file', playedSaved && playedPlain && !(await data('playError')), { playedSaved, playedPlain, err: await data('playError'), toasts: await ev(`[...document.querySelectorAll('.toast')].map(x => x.textContent)`) });

  // ---------------------------------------------------------------- 6. Use in code
  await click(row('sounds/e2e_coin.wav', 'use'));
  await t.sleep(200);
  const codeLine = await ev(`${P}.querySelector('.sl-code code')?.textContent`);
  check('"Use" shows the tgame line, with the game\'s own name for its window (arcade)', codeLine === 'arcade:sound "sounds/e2e_coin.wav"'
    && (await ev(`${P}.querySelector('.sl-item[data-rel="sounds/e2e_coin.wav"]').classList.contains('on')`)), codeLine);
  // Like a person: click at the end of "score += 1", press Enter (the editor indents the new line), then Insert.
  await ev(`(() => { const e = monaco.editor.getEditors()[0]; e.setPosition({ lineNumber: ${AFTER_LINE}, column: e.getModel().getLineMaxColumn(${AFTER_LINE}) }); e.focus(); return 1; })()`);
  await t.key('Enter');
  await click(inPanel('[data-a="insert"]'));
  await t.sleep(300);
  const edited = await t.code();
  const inserted = edited.split('\n')[AFTER_LINE];
  check('"Insert into code" puts the line at the cursor in the game', inserted === '        arcade:sound "sounds/e2e_coin.wav"', { line: inserted });
  const okDir = checkDir('check-main');
  fs.writeFileSync(path.join(okDir, 'main.tuf'), edited);
  fs.copyFileSync(file('sounds/e2e_coin.wav'), path.join(okDir, 'sounds', 'e2e_coin.wav'));
  const okCheck = ctx.tuffCheck(path.join(okDir, 'main.tuf')).trim();
  check('The game with the inserted line passes tuff --check (the sound file is next to it)', okCheck === 'OK', okCheck);
  const missDir = checkDir('check-missing');
  fs.writeFileSync(path.join(missDir, 'main.tuf'), edited);
  const missCheck = ctx.tuffCheck(path.join(missDir, 'main.tuf'));
  check('... and --check does look for the file: without the .wav it fails', /Couldn't find the sound 'sounds\/e2e_coin\.wav'/.test(missCheck), missCheck);
  await ev(`monaco.editor.getEditors()[0].trigger('t', 'undo')`);

  // A test game: a new .tuf in the top folder that plays the sound.
  await click(inPanel('[data-a="testgame"]'));
  await waitFor(`!!${P}.dataset.testGame`, 8000);
  const testName = await data('testGame');
  const testPath = path.join(ctx.root, testName || 'none');
  const testCode = fs.existsSync(testPath) ? fs.readFileSync(testPath, 'utf8') : '';
  const opened2 = await waitFor(`(window.TuffIDE.activeFile() || '').endsWith(${JSON.stringify(testName)})`, 5000);
  const tgDir = checkDir('check-testgame');
  fs.writeFileSync(path.join(tgDir, testName || 'x.tuf'), testCode);
  fs.copyFileSync(file('sounds/e2e_coin.wav'), path.join(tgDir, 'sounds', 'e2e_coin.wav'));
  const tgCheck = ctx.tuffCheck(path.join(tgDir, testName || 'x.tuf')).trim();
  check('"Make a test game" makes sound_test.tuf, opens it, and it passes tuff --check', testName === 'sound_test.tuf' && opened2 && /^mention tgame/.test(testCode)
    && (testCode.match(/game:sound "sounds\/e2e_coin\.wav"/g) || []).length === 2 && tgCheck === 'OK', { testName, opened2, tgCheck, testCode });

  // A game in a subfolder: tgame only finds files in the game's own folder.
  const levelPath = path.join(ctx.root, 'levels', 'level1.tuf');
  fs.mkdirSync(path.dirname(levelPath), { recursive: true });
  fs.writeFileSync(levelPath, LEVEL);
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(levelPath)}); return 1; })()`);
  await t.sleep(300);
  await click(row('sounds/e2e_coin.wav', 'use'));
  await t.sleep(200);
  const warn = await ev(`${P}.querySelector('.sl-warn')?.textContent || ''`);
  check('For a game in a folder, it says the sound has to be in that folder too', /levels/.test(warn) && !!(await ev(`!!${P}.querySelector('[data-a="copyhere"]')`)), warn);
  await click(inPanel('[data-a="copyhere"]'));
  await waitFor(`!!${P}.querySelector('.sl-item[data-rel="levels/sounds/e2e_coin.wav"]')`, 8000);
  const lvLine = await ev(`${P}.querySelector('.sl-code code')?.textContent`);
  const lvDir = checkDir('check-level');
  fs.writeFileSync(path.join(lvDir, 'level1.tuf'), LEVEL + lvLine.replace(/^\w+/, 'game') + '\n');
  if (fs.existsSync(file('levels/sounds/e2e_coin.wav'))) fs.copyFileSync(file('levels/sounds/e2e_coin.wav'), path.join(lvDir, 'sounds', 'e2e_coin.wav'));
  const lvCheck = ctx.tuffCheck(path.join(lvDir, 'level1.tuf')).trim();
  const copied = fs.existsSync(file('levels/sounds/e2e_coin.wav')) ? parseWav(fs.readFileSync(file('levels/sounds/e2e_coin.wav'))) : null;
  check('"Save a copy" puts it in levels/sounds, the line becomes game:sound "sounds/e2e_coin.wav", and it passes --check',
    copied && copied.data.equals(files.coin.wav.data) && lvLine === 'game:sound "sounds/e2e_coin.wav"' && !(await ev(`!!${P}.querySelector('.sl-warn')`)) && lvCheck === 'OK', { lvLine, lvCheck, copied: !!copied });

  // Edit: a saved sound comes back into the sliders.
  await ev(`(async () => { await window.TuffIDE.openFile(${JSON.stringify(mainPath)}); return 1; })()`);
  await click(row('sounds/e2e_jump.wav', 'edit'));
  await t.sleep(400);
  const editState = { name: await ev(`${P}.querySelector('.sl-name').value`), samples: +(await data('samples')), wave: await data('soundWave'), pitch: await sliderValue('pitch') };
  check('"Edit" opens a saved sound again: same name, length, wave and sliders', editState.name === 'e2e_jump' && editState.samples === files.jump.wav.samples
    && editState.wave === files.jump.wav.settings.wave && Math.abs(editState.pitch - files.jump.wav.settings.pitch) < 1e-9, { editState, saved: files.jump.wav.settings });

  // ---------------------------------------------------------------- 7. it remembers the last settings
  const vol = await sliderValue('volume');
  await click(inPanel('input[data-k="volume"]'), vol > 0.5 ? 0.25 : 0.75);
  await t.sleep(900);
  const remembered = { volume: await sliderValue('volume'), pitch: await sliderValue('pitch'), name: await ev(`${P}.querySelector('.sl-name').value`) };
  let stored = null;
  try { stored = JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8')).pluginData?.['sound-lab']?.last; } catch {}
  check('The settings are saved in TuffCode\'s settings (t.storage) as you go', stored && stored.params?.volume === remembered.volume && stored.name === remembered.name, { stored, remembered });
  await t.reload();
  const back = await waitFor(`!!${sl}`, 15000);
  await t.sleep(300);
  const after = back ? { volume: await sliderValue('volume'), pitch: await sliderValue('pitch'), name: await ev(`${P}.querySelector('.sl-name').value`) } : null;
  check('After a restart the panel comes back with the same settings and name', back && JSON.stringify(after) === JSON.stringify(remembered), { remembered, after });

  // ---------------------------------------------------------------- 8. how it looks: 400 px, then 300 px
  await waitFor(`${P}.querySelectorAll('.sl-item').length > 5`, 8000);
  await click(row('sounds/e2e_coin.wav', 'use'));
  const rect = () => ev(`(() => { const r = document.querySelector('#rightbar').getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; })()`);
  const scrollTo = async (where) => {
    await t.move(600, 300); // the mouse over the editor, so nothing in the panel shows a hover
    await ev(`(() => {
      document.querySelectorAll('.toast').forEach((x) => x.remove());
      const box = ${SL};
      if (${JSON.stringify(where)} === 'top') { box.scrollTop = 0; return 1; }
      // the "Save" heading just under the part that stays at the top
      const h = [...box.querySelectorAll('.sl-h')].find((x) => x.textContent.trim() === 'Save');
      box.scrollTop += h.getBoundingClientRect().top - box.getBoundingClientRect().top - box.querySelector('.sl-player').offsetHeight + 4;
      return 1;
    })()`);
    await t.sleep(400);
  };
  await scrollTo('top');
  const shot1 = await t.shot('sound-lab-1-presets.png', await rect());
  await scrollTo('save');
  const shot2 = await t.shot('sound-lab-2-save-and-use.png', await rect());
  await ev(`document.documentElement.style.setProperty('--rightbar-w', '300px'); 1`);
  await scrollTo('top');
  const narrow = await ev(`(() => {
    const box = ${SL};
    const right = box.getBoundingClientRect().right;
    const over = [...box.querySelectorAll('button, input, output, .sl-lbl, .sl-code, canvas')].filter((el) => el.getClientRects().length && !el.closest('.sl-code') && el.getBoundingClientRect().right > right + 0.5).map((el) => el.className || el.tagName);
    return { width: Math.round(document.querySelector('#rightbar').getBoundingClientRect().width), scroll: box.scrollWidth, client: box.clientWidth, over };
  })()`);
  check('At 300 px wide nothing sticks out sideways (no sideways scrolling)', narrow.width === 300 && narrow.scroll <= narrow.client && !narrow.over.length, narrow);
  const shot3 = await t.shot('sound-lab-3-narrow-300px.png', await rect());
  await ev(`document.documentElement.style.setProperty('--rightbar-w', '400px'); 1`);
  t.info(`screenshots: ${shot1}, ${shot2}, ${shot3}`);

  const wrote = fs.readdirSync(ctx.root, { recursive: true }).map((f) => f.replace(/\\/g, '/')).filter((f) => /\.wav$/.test(f));
  check('Sound Lab only wrote .wav files inside the project\'s sounds folders', wrote.every((f) => /^(levels\/)?sounds\/[\w-]+\.wav$/.test(f)), wrote);
  // (Monaco's own "Canceled" from the restart above isn't Sound Lab's.)
  const errors = t.events.filter((e) => /sound-lab|Sound Lab/i.test(e));
  check('No page errors from Sound Lab', !errors.length, errors);
};
