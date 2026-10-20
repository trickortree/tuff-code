// Sound Lab: sound effects for tgame games, made right here.
// A small synth turns a handful of settings (wave, pitch, slide, loudness over time...) into samples, Web Audio
// plays them, and the .wav file (16-bit PCM, mono, 44.1 kHz) is written byte by byte, header and all. The
// settings also go inside the .wav, in a LIST/INFO comment, so a saved sound can be opened and changed again.
TuffPlugins.register('sound-lab', (t) => {
  const RATE = 44100;
  const MAX_SECONDS = 4;
  const MARK = 'TuffCode Sound Lab settings: ';
  const SOUND_FILE = /\.(wav|mp3|ogg|m4a)$/i;
  const TGAME = /^\s*(mention|import)\s+tgame\b/m;
  const GAME_VAR = /^\s*([A-Za-z_]\w*)\s*=\s*tgame\.(window|world)\s*\(/m;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const slash = (p) => String(p || '').replace(/\\/g, '/');

  // ---------------------------------------------------------------- the settings
  // Every slider runs 0..1, or -1..1 for the ones that go both ways. physical() turns them into real units.
  const WAVES = [['square', 'Square'], ['saw', 'Saw'], ['sine', 'Sine'], ['noise', 'Noise']];
  const pct = (v) => `${Math.round(Math.abs(v) * 100)}%`;
  const offOr = (f) => (v, ph) => (Math.abs(v) < 0.005 ? 'off' : f(v, ph));
  const upDown = (up, down) => (v) => (Math.abs(v) < 0.005 ? 'none' : `${v > 0 ? up : down} ${pct(v)}`);
  const secs = (s) => `${s < 0.995 ? s.toFixed(2) : s.toFixed(1)} s`;
  const notes = (n) => (n ? `${n > 0 ? 'up' : 'down'} ${Math.abs(n)} note${Math.abs(n) === 1 ? '' : 's'}` : 'off');

  const SIMPLE = [
    ['Pitch', [
      { k: 'pitch', label: 'Start pitch', hint: 'How high or low the sound starts.', fmt: (v, f) => `${Math.round(f.freq)} Hz` },
      { k: 'slide', label: 'Pitch slide', min: -1, hint: 'Left makes the pitch fall while it plays, right makes it rise.', fmt: upDown('up', 'down') },
      { k: 'vibrato', label: 'Vibrato', hint: 'Makes the pitch wobble up and down.', fmt: offOr(pct) },
    ]],
    ['Loudness over time', [
      { k: 'attack', label: 'Attack', hint: 'How long it takes to get loud. Short is a sharp start, long is a slow fade in.', fmt: (v, f) => secs(f.attack) },
      { k: 'sustain', label: 'Sustain', hint: 'How long it stays loud.', fmt: (v, f) => secs(f.sustain) },
      { k: 'decay', label: 'Decay', hint: 'How long it takes to fade away at the end.', fmt: (v, f) => secs(f.decay) },
    ]],
    ['Extras', [
      { k: 'volume', label: 'Volume', hint: 'How loud the whole sound is.', fmt: pct },
      { k: 'repeat', label: 'Repeat', hint: 'Starts the pitch over and over while it plays. Further right repeats faster.', fmt: offOr((v, f) => secs(f.repeat)) },
      { k: 'arp', label: 'Arpeggio jump', min: -1, hint: 'Jumps to a higher (right) or lower (left) note partway through, like a coin pickup.', fmt: (v, f) => notes(f.arpSemis) },
    ]],
  ];
  const ADVANCED = [
    { k: 'duty', label: 'Square shape', hint: 'Makes the square wave thinner, for a buzzier sound. Only changes the square wave.', fmt: (v, f) => `${Math.round(f.width * 100)}%` },
    { k: 'dutySlide', label: 'Shape slide', min: -1, hint: 'Changes the square shape while it plays.', fmt: upDown('wider', 'thinner') },
    { k: 'slideBend', label: 'Slide bend', min: -1, hint: 'Bends the pitch slide: right curves it up more and more, left curves it down.', fmt: upDown('up', 'down') },
    { k: 'vibSpeed', label: 'Vibrato speed', hint: 'How fast the vibrato wobbles.', fmt: (v, f) => `${f.vibRate.toFixed(1)} Hz` },
    { k: 'arpTime', label: 'Jump time', hint: 'When the arpeggio jump happens.', fmt: (v, f) => secs(f.arpTime) },
    { k: 'punch', label: 'Punch', hint: 'Makes the start louder, so it hits harder.', fmt: offOr(pct) },
    { k: 'lowpass', label: 'Muffle', hint: 'Takes away the high, bright part, like hearing it through a wall.', fmt: offOr(pct) },
    { k: 'highpass', label: 'Thin out', hint: 'Takes away the low, deep part, like a tiny speaker.', fmt: offOr(pct) },
    { k: 'flanger', label: 'Flanger', hint: 'Adds a very short echo that sounds like a jet or a robot.', fmt: offOr(pct) },
    { k: 'flangerSweep', label: 'Flanger sweep', min: -1, hint: 'Makes the flanger echo move while it plays.', fmt: upDown('up', 'down') },
    { k: 'crush', label: 'Crunch', hint: 'Makes it rougher, like an old game console.', fmt: offOr(pct) },
  ];
  const SLIDERS = new Map([...SIMPLE.flatMap(([, rows]) => rows), ...ADVANCED].map((s) => [s.k, { min: 0, max: 1, ...s }]));

  const DEFAULTS = {
    wave: 'square', pitch: 0.5, slide: 0, vibrato: 0, attack: 0, sustain: 0.3, decay: 0.4, volume: 0.5, repeat: 0, arp: 0,
    duty: 0, dutySlide: 0, slideBend: 0, vibSpeed: 0.4, arpTime: 0.3, punch: 0, lowpass: 0, highpass: 0, flanger: 0, flangerSweep: 0, crush: 0, seed: 1,
  };
  // The first sound anyone hears: a clean coin.
  const FIRST = { wave: 'square', pitch: 0.7, sustain: 0.22, decay: 0.45, punch: 0.45, arp: 0.42, arpTime: 0.3, duty: 0.2, seed: 7 };

  // Settings from anywhere (a preset, storage, a saved .wav) made safe: known keys only, in range, on the slider's steps.
  function fix(p) {
    const out = { ...DEFAULTS };
    for (const k of Object.keys(DEFAULTS)) {
      const v = p?.[k];
      if (k === 'wave') out.wave = WAVES.some(([w]) => w === v) ? v : DEFAULTS.wave;
      else if (k === 'seed') out.seed = Number.isFinite(+v) && +v >= 1 ? Math.floor(+v) % 2147483647 || 1 : 1;
      else if (Number.isFinite(+v) && v !== null && v !== '') {
        const s = SLIDERS.get(k);
        out[k] = Math.round(clamp(+v, s.min, s.max) * 100) / 100;
      }
    }
    return out;
  }

  // The sliders in real units: hertz, octaves, seconds.
  function physical(p) {
    const sq = (x) => x * x;
    const ssq = (x) => Math.sign(x) * x * x;
    return {
      freq: 55 * 2 ** (p.pitch * 5.5), // 55 Hz to about 2500 Hz
      slide: ssq(p.slide) * 8, // octaves per second
      bend: ssq(p.slideBend) * 24, // octaves per second, per second
      vibDepth: (sq(p.vibrato) * 6) / 12, // octaves
      vibRate: 1 + sq(p.vibSpeed) * 29, // Hz
      attack: sq(p.attack) * 1.2,
      sustain: sq(p.sustain) * 1.6,
      decay: sq(p.decay) * 1.8,
      gain: p.volume,
      repeat: p.repeat > 0.005 ? 0.03 + sq(1 - p.repeat) * 0.6 : 0, // seconds between restarts
      arpSemis: Math.round(p.arp * 12),
      arpTime: 0.01 + sq(p.arpTime) * 0.5,
      width: 0.5 - p.duty * 0.45, // how much of each square wave is "up"
      widthSlide: ssq(p.dutySlide) * 1.5, // per second
      punch: p.punch * 1.5,
      lowpass: p.lowpass > 0.005 ? 22000 * 2 ** (-p.lowpass * 7) : 0, // Hz, 0 = off
      highpass: p.highpass > 0.005 ? 20 * 2 ** (p.highpass * 7) : 0,
      flangeMs: p.flanger > 0.005 ? 0.4 + sq(p.flanger) * 10 : 0,
      flangeSweep: p.flangerSweep * 12, // ms per second
      crush: 1 + Math.floor(sq(p.crush) * 15), // hold each sample this many times
    };
  }

  // ---------------------------------------------------------------- the synth
  // A soft corner for the square and saw waves' jumps, so high notes don't fizz (a "polyBLEP").
  function blep(ph, dt) {
    if (ph < dt) { const x = ph / dt; return x + x - x * x - 1; }
    if (ph > 1 - dt) { const x = (ph - 1) / dt; return x * x + x + x + 1; }
    return 0;
  }

  // The same settings always give the same samples: the noise comes from this little generator, seeded.
  function noiseFrom(seed) {
    let s = seed >>> 0 || 1;
    return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
  }

  function render(p) {
    const f = physical(p);
    let { attack, sustain, decay } = f;
    if (attack + sustain + decay < 0.02) sustain = 0.02 - attack - decay;
    const n = Math.ceil(Math.min(MAX_SECONDS, attack + sustain + decay) * RATE);
    const out = new Float32Array(n);
    const rand = noiseFrom(p.seed);
    const level = { square: 0.5, saw: 0.55, sine: 0.85, noise: 0.6 }[p.wave] * f.gain * 1.6;
    const lpA = f.lowpass ? 1 - Math.exp((-2 * Math.PI * f.lowpass) / RATE) : 1;
    const hpA = f.highpass ? 1 - Math.exp((-2 * Math.PI * f.highpass) / RATE) : 0;
    const echo = new Float32Array(2048);
    const fade = Math.min(n, Math.round(0.003 * RATE));
    let phase = 0, noisePhase = 0, noise = rand() * 2 - 1;
    let lp1 = 0, lp2 = 0, hp = 0, held = 0, hold = 0;
    for (let i = 0; i < n; i++) {
      const time = i / RATE;
      const local = f.repeat ? time % f.repeat : time; // repeat starts the pitch part over
      let oct = f.slide * local + 0.5 * f.bend * local * local;
      if (f.arpSemis && local >= f.arpTime) oct += f.arpSemis / 12;
      if (f.vibDepth) oct += f.vibDepth * Math.sin(2 * Math.PI * f.vibRate * time);
      const dt = clamp(f.freq * 2 ** oct, 20, 12000) / RATE;
      phase += dt;
      if (phase >= 1) phase -= 1;

      let x;
      if (p.wave === 'sine') x = Math.sin(2 * Math.PI * phase);
      else if (p.wave === 'saw') x = 2 * phase - 1 - blep(phase, dt);
      else if (p.wave === 'noise') {
        noisePhase += dt * 16; // a new random level 16 times a cycle: low pitches rumble, high ones hiss
        while (noisePhase >= 1) { noisePhase -= 1; noise = rand() * 2 - 1; }
        x = noise;
      } else {
        const w = clamp(f.width + f.widthSlide * local, 0.03, 0.5);
        x = (phase < w ? 1 : -1) + blep(phase, dt) - blep((phase - w + 1) % 1, dt);
      }

      let env;
      if (time < attack) env = time / attack;
      else if (time < attack + sustain) env = 1 + f.punch * (1 - (time - attack) / sustain);
      else env = decay ? Math.max(0, 1 - (time - attack - sustain) / decay) : 0;
      x *= env;

      if (f.lowpass) { lp1 += lpA * (x - lp1); lp2 += lpA * (lp1 - lp2); x = lp2; }
      if (f.highpass) { hp += hpA * (x - hp); x -= hp; }
      if (f.flangeMs) {
        echo[i & 2047] = x;
        const back = i - (clamp(f.flangeMs + f.flangeSweep * time, 0.1, 40) * RATE) / 1000;
        const j = Math.floor(back);
        const a = j >= 0 ? echo[j & 2047] : 0;
        const b = j + 1 >= 0 ? echo[(j + 1) & 2047] : 0;
        x += 0.6 * (a + (b - a) * (back - j));
      }
      if (f.crush > 1) { if (hold <= 0) { held = x; hold = f.crush; } hold--; x = held; }

      x *= level;
      const ax = Math.abs(x);
      if (ax > 0.8) x = Math.sign(x) * (0.8 + 0.2 * Math.tanh((ax - 0.8) / 0.2)); // a soft ceiling: never clips
      if (i >= n - fade) x *= (n - i) / fade; // no click at the end
      out[i] = x;
    }
    return out;
  }

  // ---------------------------------------------------------------- presets
  const PRESETS = [['coin', 'Coin'], ['jump', 'Jump'], ['laser', 'Laser'], ['explosion', 'Explosion'], ['powerup', 'Power-up'], ['hit', 'Hit'], ['blip', 'Blip'], ['random', 'Random']];
  const FILE_NAMES = { coin: 'coin', jump: 'jump', laser: 'laser', explosion: 'explosion', powerup: 'powerup', hit: 'hit', blip: 'blip', random: 'sound' };

  function generate(kind) {
    const r = (a, b) => a + Math.random() * (b - a);
    const pick = (...xs) => xs[Math.floor(Math.random() * xs.length)];
    const maybe = (chance, v) => (Math.random() < chance ? v : 0);
    let p;
    switch (kind) {
      case 'coin':
        p = { wave: pick('square', 'square', 'saw', 'sine'), pitch: r(0.6, 0.78), sustain: r(0.15, 0.3), decay: r(0.35, 0.55), punch: r(0.3, 0.6),
          arp: maybe(0.75, r(0.3, 0.6)), arpTime: r(0.25, 0.4), duty: r(0, 0.5) };
        break;
      case 'jump':
        p = { wave: pick('square', 'square', 'sine'), pitch: r(0.3, 0.45), slide: r(0.55, 0.8), sustain: r(0.2, 0.35), decay: r(0.3, 0.5),
          duty: r(0, 0.6), highpass: maybe(0.5, r(0.05, 0.3)), lowpass: maybe(0.4, r(0.05, 0.3)) };
        break;
      case 'laser':
        p = { wave: pick('square', 'saw', 'saw', 'sine'), pitch: r(0.7, 0.95), slide: -r(0.6, 0.9), slideBend: maybe(0.3, r(-0.3, 0.3)), sustain: r(0.15, 0.3),
          decay: r(0.2, 0.45), duty: r(0, 0.8), dutySlide: maybe(0.5, r(-0.5, 0.5)), flanger: maybe(0.25, r(0.1, 0.4)), highpass: maybe(0.4, r(0.05, 0.3)),
          vibrato: maybe(0.2, r(0.1, 0.3)) };
        break;
      case 'explosion':
        p = { wave: 'noise', pitch: r(0.2, 0.45), slide: Math.random() < 0.5 ? -r(0.1, 0.4) : r(-0.1, 0.15), sustain: r(0.3, 0.5), decay: r(0.55, 0.8),
          punch: r(0.3, 0.8), flanger: maybe(0.3, r(0.2, 0.5)), flangerSweep: r(-0.3, 0.3), repeat: maybe(0.25, r(0.4, 0.7)), lowpass: maybe(0.5, r(0.1, 0.4)),
          crush: maybe(0.3, r(0.1, 0.5)), volume: 0.6 };
        break;
      case 'powerup':
        p = { wave: pick('square', 'saw', 'square'), pitch: r(0.35, 0.5), slide: r(0.3, 0.55), sustain: r(0.45, 0.6), decay: r(0.4, 0.6), duty: r(0, 0.6),
          ...(Math.random() < 0.5 ? { repeat: r(0.45, 0.75) } : { vibrato: r(0.2, 0.45), vibSpeed: r(0.5, 0.75) }) };
        break;
      case 'hit':
        p = { wave: pick('square', 'saw', 'noise', 'noise'), pitch: r(0.35, 0.6), slide: -r(0.4, 0.75), sustain: r(0.05, 0.2), decay: r(0.25, 0.4),
          highpass: maybe(0.5, r(0.05, 0.3)), duty: r(0, 0.7), punch: r(0, 0.4) };
        break;
      case 'blip':
        p = { wave: pick('square', 'square', 'sine', 'saw'), pitch: r(0.55, 0.8), sustain: r(0.12, 0.22), decay: r(0.08, 0.2), duty: r(0, 0.7), highpass: r(0, 0.2) };
        break;
      default: {
        const s = r(-1, 1);
        p = { wave: pick('square', 'saw', 'sine', 'noise'), pitch: r(0.1, 0.95), slide: s * s * s, vibrato: maybe(0.3, r(0.05, 0.6)), vibSpeed: r(0, 1),
          attack: maybe(0.3, r(0, 0.5)), sustain: r(0.1, 0.6), decay: r(0.15, 0.7), repeat: maybe(0.25, r(0.2, 0.9)), arp: maybe(0.3, r(-1, 1)), arpTime: r(0, 1),
          duty: r(0, 1), dutySlide: maybe(0.3, r(-1, 1)), slideBend: maybe(0.2, r(-0.5, 0.5)), punch: r(0, 0.6), lowpass: maybe(0.3, r(0, 0.6)),
          highpass: maybe(0.3, r(0, 0.4)), flanger: maybe(0.2, r(0, 0.6)), flangerSweep: r(-1, 1), crush: maybe(0.15, r(0, 0.7)) };
      }
    }
    return fix({ ...p, seed: 1 + Math.floor(Math.random() * 2147483645) });
  }

  // "Change a little": every setting that's on moves a tiny bit, and now and then one that's off comes on.
  function nudge(p) {
    const q = { ...p };
    for (const s of SLIDERS.values()) {
      if (s.k === 'volume' || (Math.abs(q[s.k]) < 0.005 && Math.random() < 0.8)) continue;
      q[s.k] += (Math.random() * 2 - 1) * 0.06;
    }
    return fix(q);
  }

  // ---------------------------------------------------------------- the .wav file
  // RIFF/WAVE: a "fmt " chunk (PCM, 1 channel, 44100 a second, 16 bits), the "data" chunk, then a LIST/INFO
  // chunk naming the software and keeping the settings as a comment. Players skip chunks they don't know.
  function encodeWav(samples, comment) {
    const ascii = (s) => Uint8Array.from(s, (c) => c.charCodeAt(0) & 0x7f);
    const sub = (id, text) => { const body = ascii(text + '\0'); return { id, body, size: body.length + (body.length & 1) }; };
    const info = comment ? [sub('ISFT', 'TuffCode Sound Lab'), sub('ICMT', comment)] : [];
    const listSize = info.length ? 4 + info.reduce((a, c) => a + 8 + c.size, 0) : 0;
    const dataSize = samples.length * 2;
    const bytes = new Uint8Array(44 + dataSize + (listSize ? 8 + listSize : 0));
    const v = new DataView(bytes.buffer);
    const tag = (at, s) => { for (let i = 0; i < 4; i++) bytes[at + i] = s.charCodeAt(i); };
    tag(0, 'RIFF'); v.setUint32(4, bytes.length - 8, true); tag(8, 'WAVE');
    tag(12, 'fmt '); v.setUint32(16, 16, true);
    v.setUint16(20, 1, true); // PCM
    v.setUint16(22, 1, true); // mono
    v.setUint32(24, RATE, true);
    v.setUint32(28, RATE * 2, true); // bytes a second
    v.setUint16(32, 2, true); // bytes a sample
    v.setUint16(34, 16, true); // bits a sample
    tag(36, 'data'); v.setUint32(40, dataSize, true);
    for (let i = 0; i < samples.length; i++) v.setInt16(44 + i * 2, Math.round(clamp(samples[i], -1, 1) * 32767), true);
    if (listSize) {
      let at = 44 + dataSize;
      tag(at, 'LIST'); v.setUint32(at + 4, listSize, true); tag(at + 8, 'INFO');
      at += 12;
      for (const c of info) { tag(at, c.id); v.setUint32(at + 4, c.body.length, true); bytes.set(c.body, at + 8); at += 8 + c.size; }
    }
    return bytes;
  }

  function toBase64(bytes) {
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }

  // The settings back out of a Sound Lab .wav. The file comes in as text, but the comment is plain ASCII, so it survives.
  function settingsIn(text) {
    const at = String(text || '').lastIndexOf(MARK);
    if (at < 0) return null;
    const end = text.indexOf('\0', at);
    try { return fix(JSON.parse(text.slice(at + MARK.length, end < 0 ? undefined : end))); } catch { return null; }
  }

  // ---------------------------------------------------------------- icons (simple line icons, 16 x 16)
  const ic = (d, cls = 'sl-ic') => `<svg class="${cls}" viewBox="0 0 16 16" aria-hidden="true"><path d="${d}"/></svg>`;
  const ICON = {
    play: ic('M5 3.2v9.6L12.6 8z'),
    again: ic('M13 8a5 5 0 1 1-1.46-3.54M13 2.6v3h-3'),
    nudge: ic('M1.5 9.5c1.6 0 1.6-3 3.25-3s1.6 3 3.25 3 1.6-3 3.25-3 1.6 3 3.25 3'),
    save: ic('M8 2.5v7.6M4.8 7.1 8 10.2l3.2-3.1M3 13.2h10'),
    chevron: ic('M6 4l4 4-4 4', 'sl-ic sl-chev'),
    code: ic('M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5'),
    copy: ic('M5.5 5.5h7v7h-7zM3.5 10.5v-7h7'),
    game: ic('M4.5 5.5h7a3 3 0 0 1 0 6h-7a3 3 0 0 1 0-6zM5.5 7.4v2.2M4.4 8.5h2.2M10.4 8.2v.1M11.8 9v.1'),
    edit: ic('M10.6 3.2l2.2 2.2-6.9 6.9H3.7v-2.2z'),
    refresh: ic('M13 8a5 5 0 1 1-1.46-3.54M13 2.6v3h-3'),
  };
  const WAVE_ICON = {
    square: ic('M1 11.5V4.5h3.5v7H8v-7h3.5v7H15'),
    saw: ic('M1 11.5l4.6-7v7l4.6-7v7l4.6-7'),
    sine: ic('M.5 8q2.5-7 5 0t5 0t5 0'),
    noise: ic('M1 9l1.4-3.5 1.4 6 1.4-8 1.4 7 1.4-4.5 1.4 5.5 1.4-7 1.4 5 1.4-2'),
  };

  // ---------------------------------------------------------------- state
  const last = t.storage.get('last', null);
  let params = fix(last?.params || FIRST);
  let preset = last ? last.preset ?? null : 'coin';
  let fileName = cleanName(last?.name) || 'coin';
  let autoName = last?.autoName !== false;
  let autoPlay = last?.autoPlay !== false;
  let samples = render(params);
  let root = null;
  let audio = null; // the AudioContext, made on the first Play (browsers want a click first)
  let voice = null; // what's playing now: { src, start, length, main }
  let fileVoice = null;
  let frame = 0;
  let sounds = []; // sound files in the project: { path, rel, name, dir }
  const labSettings = new Map(); // rel (lower case) -> settings, or null for a sound Sound Lab didn't make
  let labRoot = null; // the project labSettings is about
  let listedAt = 0;
  let useRel = null;
  let resize = null;
  let rememberTimer = 0;

  function cleanName(s) {
    return String(s || '').trim().replace(/\.(wav|mp3|ogg|m4a)$/i, '').replace(/\s+/g, '_').replace(/[^\w-]/g, '').replace(/^[-_]+/, '').slice(0, 40);
  }

  function remember(now) {
    clearTimeout(rememberTimer);
    const write = () => t.storage.set('last', { params, preset, name: fileName, autoName, autoPlay });
    if (now) write();
    else rememberTimer = setTimeout(write, 400);
  }

  const $ = (s) => root.querySelector(s);
  const $$ = (s) => [...root.querySelectorAll(s)];

  // ---------------------------------------------------------------- the panel
  const rowHtml = (s) => {
    const d = SLIDERS.get(s.k);
    return `<div class="sl-row" data-row="${s.k}" title="${esc(s.hint)} Double-click the name to set it back.">
      <span class="sl-lbl">${esc(s.label)}</span>
      <input type="range" min="${d.min}" max="${d.max}" step="0.01" data-k="${s.k}" aria-label="${esc(s.label)}">
      <output class="sl-val"></output>
    </div>`;
  };

  const panel = t.panel('lab', {
    title: 'Sound Lab',
    mount(el) {
      root = el;
      el.innerHTML = `<div class="sl">
        <div class="sl-h">Start with a preset</div>
        <div class="sl-presets">${PRESETS.map(([k, label]) => `<button data-preset="${k}">${label}</button>`).join('')}</div>
        <div class="sl-tools">
          <button class="sl-link" data-a="another" title="A new sound of the same kind">${ICON.again}Make another</button>
          <button class="sl-link" data-a="nudge" title="Move every setting a tiny bit">${ICON.nudge}Change a little</button>
        </div>
        <div class="sl-player">
          <div class="sl-wavebox"><canvas class="sl-canvas"></canvas><span class="sl-len"></span></div>
          <div class="sl-prow">
            <button class="btn sm primary sl-play" data-a="play">${ICON.play}Play</button>
            <label class="sl-check"><input type="checkbox" class="sl-auto"> Play after each change</label>
          </div>
        </div>
        <div class="sl-h">Wave</div>
        <div class="sl-seg" role="radiogroup" aria-label="Wave">${WAVES.map(([w, label]) => `<button role="radio" data-wave="${w}" title="${label} wave">${WAVE_ICON[w]}<span>${label}</span></button>`).join('')}</div>
        ${SIMPLE.map(([title, rows]) => `<div class="sl-h">${esc(title)}</div>${rows.map(rowHtml).join('')}`).join('')}
        <details class="sl-adv"><summary>${ICON.chevron}Advanced</summary><div class="sl-adv-body">${ADVANCED.map(rowHtml).join('')}</div></details>
        <div class="sl-h">Save</div>
        <div class="sl-save">
          <label class="sl-namebox" title="The file's name. Letters, numbers, - and _ work."><span>sounds/</span><input class="sl-name" spellcheck="false" maxlength="40" aria-label="Sound name"><span>.wav</span></label>
          <button class="btn sm primary" data-a="save">${ICON.save}Save as .wav</button>
        </div>
        <div class="sl-h">Use in code</div>
        <div class="sl-use"></div>
        <div class="sl-h sl-h-row"><span>Sounds in this project</span><button class="sl-ib" data-a="refresh" title="Look for sounds again">${ICON.refresh}</button></div>
        <div class="sl-list"></div>
      </div>`;
      const box = $('.sl');
      box.addEventListener('click', onClick);
      box.addEventListener('input', onInput);
      box.addEventListener('change', onChange);
      box.addEventListener('dblclick', (e) => {
        const row = e.target.closest('.sl-lbl') && e.target.closest('.sl-row');
        if (!row) return;
        params[row.dataset.row] = DEFAULTS[row.dataset.row];
        showSettings();
        if (autoPlay) play();
      });
      // Coming back to the panel: the open file (so the code line) may have changed, and maybe the sounds too.
      box.addEventListener('pointerenter', () => { if (Date.now() - listedAt > 5000) listSounds(); else renderUse(); });
      const name = $('.sl-name');
      name.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') save(); });
      const adv = $('.sl-adv');
      adv.open = !!t.storage.get('advanced', false);
      adv.addEventListener('toggle', () => t.storage.set('advanced', adv.open));
      $('.sl-auto').checked = autoPlay;
      resize = new ResizeObserver(() => draw());
      resize.observe($('.sl-wavebox'));
      showSettings();
      return { onShow() { draw(); listSounds(); } };
    },
  });
  t.command('open', 'Sound Lab: Open', () => panel.toggle());

  function onClick(e) {
    const p = e.target.closest('button[data-preset]');
    if (p) { usePreset(p.dataset.preset); return; }
    const w = e.target.closest('button[data-wave]');
    if (w) {
      params.wave = w.dataset.wave;
      showSettings();
      if (autoPlay) play();
      return;
    }
    const a = e.target.closest('button[data-a]')?.dataset.a;
    const item = e.target.closest('.sl-item');
    const s = item ? sounds[+item.dataset.i] : null;
    if (a === 'play') play();
    else if (a === 'another') usePreset(preset || 'random');
    else if (a === 'nudge') { params = nudge(params); showSettings(); play(); }
    else if (a === 'save') save();
    else if (a === 'refresh') { labSettings.clear(); listSounds(); }
    else if (a === 'playfile' && s) playSaved(s);
    else if (a === 'edit' && s) edit(s);
    else if (a === 'use' && s) { useRel = s.rel; renderList(); renderUse(); $('.sl-use').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    else if (a === 'insert') insertCode();
    else if (a === 'copy') copyCode();
    else if (a === 'testgame') testGame();
    else if (a === 'copyhere') copyNextToGame();
  }

  function onInput(e) {
    const el = e.target;
    if (el.matches('input[type="range"]')) {
      params[el.dataset.k] = Math.round(+el.value * 100) / 100;
      paintSlider(el);
      refreshSound();
    } else if (el.matches('.sl-name')) {
      fileName = cleanName(el.value);
      autoName = false;
      remember();
    }
  }

  function onChange(e) {
    const el = e.target;
    if (el.matches('input[type="range"]') && autoPlay) play();
    else if (el.matches('.sl-auto')) { autoPlay = el.checked; remember(); }
    else if (el.matches('.sl-name')) { el.value = fileName; }
  }

  function usePreset(kind) {
    preset = kind;
    params = generate(kind);
    if (autoName) fileName = freeName(FILE_NAMES[kind] || 'sound');
    showSettings();
    play();
  }

  // The first name like coin, coin_2, coin_3... that isn't in the sounds folder yet.
  function freeName(base) {
    const taken = new Set(sounds.map((s) => s.rel.toLowerCase()));
    let n = base;
    for (let i = 2; taken.has(`sounds/${n}.wav`); i++) n = `${base}_${i}`;
    return n;
  }

  // Puts the settings into every slider, button and box, then makes the sound again.
  function showSettings() {
    for (const el of $$('input[type="range"]')) { el.value = params[el.dataset.k]; paintSlider(el); }
    for (const b of $$('[data-wave]')) { const on = b.dataset.wave === params.wave; b.classList.toggle('on', on); b.setAttribute('aria-checked', on); }
    for (const b of $$('[data-preset]')) b.classList.toggle('on', b.dataset.preset === preset);
    const name = $('.sl-name');
    if (document.activeElement !== name) name.value = fileName;
    refreshSound();
  }

  function refreshSound() {
    samples = render(params);
    const f = physical(params);
    for (const row of $$('.sl-row')) row.querySelector('output').textContent = SLIDERS.get(row.dataset.row).fmt(params[row.dataset.row], f);
    $('.sl-len').textContent = secs(samples.length / RATE);
    root.dataset.samples = samples.length;
    root.dataset.soundWave = params.wave; // for tests and tools: what the panel shows now
    draw();
    remember();
  }

  // The slider's filled part: from the left end, or from the middle for the ones that go both ways.
  function paintSlider(el) {
    const min = +el.min, max = +el.max;
    const at = ((+el.value - min) / (max - min)) * 100;
    const zero = ((clamp(0, min, max) - min) / (max - min)) * 100;
    el.style.setProperty('--a', `${Math.min(at, zero)}%`);
    el.style.setProperty('--b', `${Math.max(at, zero)}%`);
  }

  // ---------------------------------------------------------------- the waveform
  let cols = null; // [samples, width, Float32Array of min/max pairs]
  function draw(progress = -1) {
    if (!root) return;
    const c = $('.sl-canvas');
    const box = c.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(box.clientWidth * dpr), h = Math.round(box.clientHeight * dpr);
    if (!w || !h) return;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    if (!cols || cols[0] !== samples || cols[1] !== w) {
      const mm = new Float32Array(w * 2);
      const per = samples.length / w;
      for (let x = 0; x < w; x++) {
        let lo = 0, hi = 0;
        const end = Math.min(samples.length, Math.max(Math.floor(x * per) + 1, Math.floor((x + 1) * per)));
        for (let i = Math.floor(x * per); i < end; i++) { const s = samples[i]; if (s < lo) lo = s; if (s > hi) hi = s; }
        mm[x * 2] = lo;
        mm[x * 2 + 1] = hi;
      }
      cols = [samples, w, mm];
    }
    const g = c.getContext('2d');
    const css = getComputedStyle(root);
    const color = (name) => css.getPropertyValue(name).trim();
    const mid = h / 2, amp = h / 2 - 4 * dpr, line = Math.max(1, Math.round(dpr));
    g.clearRect(0, 0, w, h);
    g.fillStyle = color('--border-soft');
    g.fillRect(0, Math.round(mid), w, line);
    g.fillStyle = color('--accent');
    const mm = cols[2];
    for (let x = 0; x < w; x++) {
      const top = mid - mm[x * 2 + 1] * amp, bottom = mid - mm[x * 2] * amp;
      if (bottom - top >= 0.5) g.fillRect(x, top, 1, Math.max(line, bottom - top));
    }
    if (progress >= 0) {
      g.fillStyle = color('--text');
      g.fillRect(Math.min(w - line, Math.round(progress * w)), 0, line, h);
    }
  }

  // ---------------------------------------------------------------- playing
  function stopAll() {
    if (voice) { try { voice.src.stop(); } catch {} voice = null; }
    if (fileVoice) { try { fileVoice.pause(); } catch {} fileVoice = null; }
    cancelAnimationFrame(frame);
  }

  async function play(data = samples, main = true) {
    try {
      audio = audio || new AudioContext();
      if (audio.state === 'suspended') await audio.resume();
      stopAll();
      const buf = audio.createBuffer(1, data.length, RATE);
      buf.copyToChannel(data, 0);
      const src = audio.createBufferSource();
      src.buffer = buf;
      src.connect(audio.destination);
      const me = { src, start: audio.currentTime, length: data.length / RATE, main };
      src.onended = () => { if (voice === me) { voice = null; draw(); } };
      src.start();
      voice = me;
      root.dataset.plays = (+root.dataset.plays || 0) + 1;
      root.dataset.audio = audio.state;
      if (main) tick();
    } catch (err) {
      root.dataset.playError = String(err?.message || err);
      t.toast(`Couldn't play the sound: ${err?.message || err}`, 'error');
    }
  }

  function tick() {
    cancelAnimationFrame(frame);
    const step = () => {
      if (!voice?.main || !root) { draw(); return; }
      const p = (audio.currentTime - voice.start) / voice.length;
      if (p >= 1) { draw(); return; }
      draw(p);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
  }

  async function playSaved(s) {
    const lab = await settingsOf(s);
    if (lab) { play(render(lab), false); return; }
    // A sound Sound Lab didn't make: let the browser play the file itself.
    try {
      stopAll();
      fileVoice = new Audio(fileUrl(s.path));
      await fileVoice.play();
      root.dataset.plays = (+root.dataset.plays || 0) + 1;
    } catch (err) {
      t.toast(`Couldn't play ${s.name} here, but it can still work in your game.`, 'error');
    }
  }

  const fileUrl = (p) => (/^[A-Za-z]:/.test(p) ? 'file:///' : 'file://') + encodeURI(slash(p)).replace(/[?#]/g, encodeURIComponent);

  // ---------------------------------------------------------------- saving
  async function save() {
    if (!t.project.write) { t.toast('Sound Lab needs the "files" permission to save.', 'error'); return; }
    const name = cleanName($('.sl-name').value);
    if (!name) { t.toast('Give your sound a name first.'); $('.sl-name').focus(); return; }
    fileName = name;
    $('.sl-name').value = name;
    const rel = `sounds/${name}.wav`;
    await listSounds(false);
    if (sounds.some((s) => s.rel.toLowerCase() === rel.toLowerCase())
      && !(await t.ask({ title: `Replace ${rel}?`, confirm: true, okLabel: 'Replace' }))) return;
    try {
      await writeSound(rel, params);
    } catch (err) {
      t.toast(`Couldn't save ${rel}: ${err?.message || err}`, 'error', 6000);
      return;
    }
    useRel = rel;
    root.dataset.saves = (+root.dataset.saves || 0) + 1;
    root.dataset.saved = rel;
    autoName = true; // the next preset gets a new name, so it doesn't replace this one
    t.toast(`Saved ${rel}.`, 'ok');
    remember(true);
    await listSounds();
  }

  async function writeSound(rel, settings) {
    const bytes = encodeWav(render(settings), MARK + JSON.stringify(settings));
    await t.project.write(rel, toBase64(bytes), { encoding: 'base64' });
    labSettings.set(rel.toLowerCase(), { ...settings });
  }

  // ---------------------------------------------------------------- sounds in this project
  async function listSounds(show = true) {
    let files = [];
    try { files = await t.project.files(); } catch {}
    listedAt = Date.now();
    if (t.project.root() !== labRoot) { labRoot = t.project.root(); labSettings.clear(); }
    sounds = files.filter((f) => SOUND_FILE.test(f.name))
      .map((f) => { const rel = slash(f.rel); return { path: f.path, rel, name: f.name, dir: rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '' }; })
      .sort((a, b) => (a.dir === 'sounds' ? 0 : 1) - (b.dir === 'sounds' ? 0 : 1) || a.rel.localeCompare(b.rel));
    if (!show || !root) return;
    if (!sounds.some((s) => s.rel === useRel)) useRel = sounds.find((s) => s.dir === 'sounds')?.rel || sounds[0]?.rel || null;
    renderList();
    renderUse();
    // Find out which ones Sound Lab made (they can be changed again), one file at a time.
    for (const s of sounds) {
      if (!/\.wav$/i.test(s.name) || labSettings.has(s.rel.toLowerCase())) continue;
      await settingsOf(s);
      renderList();
    }
  }

  async function settingsOf(s) {
    const key = s.rel.toLowerCase();
    if (!labSettings.has(key)) {
      let found = null;
      if (/\.wav$/i.test(s.name)) { try { found = settingsIn(await t.project.read(s.path)); } catch {} }
      labSettings.set(key, found);
    }
    return labSettings.get(key);
  }

  // Sets a box's HTML only when it changed, so buttons aren't swapped out from under a click.
  const shown = new WeakMap();
  const fill = (box, html) => { if (shown.get(box) !== html) { box.innerHTML = html; shown.set(box, html); } };

  function renderList() {
    if (!root) return;
    fill($('.sl-list'), !sounds.length ? '<div class="sl-empty">No sounds yet. Make one above and save it, and it shows up here.</div>'
      : sounds.map((s, i) => `<div class="sl-item${s.rel === useRel ? ' on' : ''}" data-i="${i}" data-rel="${esc(s.rel)}">
      <button class="sl-ib" data-a="playfile" title="Play ${esc(s.name)}">${ICON.play}</button>
      <div class="sl-file"><span>${esc(s.name)}</span>${s.dir === 'sounds' ? '' : `<small>${esc(s.dir || 'top folder')}</small>`}</div>
      ${labSettings.get(s.rel.toLowerCase()) ? `<button class="sl-tb" data-a="edit" title="Open it in Sound Lab to change it">${ICON.edit}Edit</button>` : ''}
      <button class="sl-tb" data-a="use" title="Show the code that plays it">${ICON.code}Use</button>
    </div>`).join(''));
  }

  async function edit(s) {
    const lab = await settingsOf(s);
    if (!lab) return;
    params = { ...lab };
    preset = null;
    fileName = cleanName(s.name);
    autoName = false;
    useRel = s.rel;
    showSettings();
    renderList();
    renderUse();
    $('.sl').scrollTo({ top: 0, behavior: 'smooth' });
    play();
  }

  // ---------------------------------------------------------------- use in code
  // tgame finds files next to the game's .tuf file, so the path starts from the game's own folder.
  function codeFor(s) {
    const file = t.editor.file();
    const isTuf = !!file && /\.tuf$/i.test(file);
    const code = isTuf ? t.editor.code() : '';
    const game = (code.match(GAME_VAR) || [])[1] || 'game';
    const out = { path: s.rel, warn: '', note: '', dir: '' };
    if (isTuf) {
      const rel = slash(t.project.rel(file));
      const dir = rel.includes('/') && rel !== slash(file) ? rel.slice(0, rel.lastIndexOf('/')) : '';
      const base = rel.slice(rel.lastIndexOf('/') + 1);
      if (dir && s.rel.toLowerCase().startsWith(dir.toLowerCase() + '/')) out.path = s.rel.slice(dir.length + 1);
      else if (dir) {
        out.dir = dir;
        out.warn = `tgame looks for sounds in your game's own folder. ${base} is in "${dir}", so this sound has to be in there too.`;
      }
      if (!TGAME.test(code)) out.note = `${base} isn't a tgame game yet (it needs "mention tgame" at the top). "Make a test game" makes one that plays this sound.`;
    } else {
      out.note = 'Open your game\'s .tuf file, click an empty line where the sound should play, then Insert.';
    }
    out.line = `${game}:sound "${out.path}"`;
    return out;
  }

  function renderUse() {
    if (!root) return;
    const box = $('.sl-use');
    const s = sounds.find((x) => x.rel === useRel);
    if (!s) {
      fill(box, '<p class="sl-note">Save a sound first. Then the line of code that plays it shows up here.</p>');
      return;
    }
    const u = codeFor(s);
    const canCopy = u.dir && labSettings.get(s.rel.toLowerCase());
    fill(box, `<div class="sl-code"><code>${esc(u.line)}</code></div>
      <div class="sl-btns">
        <button class="btn sm primary" data-a="insert">${ICON.code}Insert into code</button>
        <button class="btn sm" data-a="copy">${ICON.copy}Copy</button>
        <button class="btn sm" data-a="testgame" title="A small game that plays this sound when you press space">${ICON.game}Make a test game</button>
      </div>
      ${u.warn ? `<p class="sl-warn">${esc(u.warn)}${canCopy ? ` <button class="sl-link inline" data-a="copyhere">Save a copy in "${esc(u.dir)}/sounds"</button>` : ''}</p>` : ''}
      <p class="sl-note">${esc(u.note || 'Put it where something happens in your game, like when the player grabs a coin. Click an empty line in your code first.')}</p>`);
  }

  async function insertCode() {
    const s = sounds.find((x) => x.rel === useRel);
    if (!s) return;
    const u = codeFor(s);
    renderUse();
    if (!t.editor.file()) { t.toast('Open your game file first, then click Insert.'); return; }
    if (await t.editor.insert(u.line)) t.toast('Added the line to your code.', 'ok', 1800);
  }

  async function copyCode() {
    const s = sounds.find((x) => x.rel === useRel);
    if (!s) return;
    try { await navigator.clipboard.writeText(codeFor(s).line); t.toast('Copied.', 'ok', 1500); } catch { t.toast("Couldn't copy."); }
  }

  async function copyNextToGame() {
    const s = sounds.find((x) => x.rel === useRel);
    const lab = s && labSettings.get(s.rel.toLowerCase());
    const u = s && codeFor(s);
    if (!lab || !u?.dir) return;
    const rel = `${u.dir}/sounds/${s.name.replace(/\.\w+$/, '')}.wav`;
    try { await writeSound(rel, lab); } catch (err) { t.toast(`Couldn't save ${rel}: ${err?.message || err}`, 'error'); return; }
    useRel = rel;
    t.toast(`Saved ${rel}.`, 'ok');
    await listSounds();
  }

  const testGameCode = (rel, name) => `mention tgame

game = tgame.window("Sound test", 500, 300)
game:background "navy"
game:text("Press space or click to play ${name}", 250, 135, 22, "white")
game:text("Made with Sound Lab", 250, 175, 14, "gray")

func play_it(key):
    game:sound "${rel}"

func on_click(x, y):
    game:sound "${rel}"

game:on_key("space", play_it)
game:clicked on_click
`;

  // A new .tuf file in the top folder that plays the sound: press Run and then space.
  async function testGame() {
    const s = sounds.find((x) => x.rel === useRel);
    if (!s || !t.project.write) return;
    let files = [];
    try { files = await t.project.files(); } catch {}
    const taken = new Set(files.map((f) => slash(f.rel).toLowerCase()));
    let file = 'sound_test.tuf';
    for (let i = 2; taken.has(file); i++) file = `sound_test_${i}.tuf`;
    try {
      await t.project.write(file, testGameCode(s.rel, s.name));
    } catch (err) {
      t.toast(`Couldn't make ${file}: ${err?.message || err}`, 'error');
      return;
    }
    const top = t.project.root();
    await t.openFile(top + (top.includes('\\') ? '\\' : '/') + file);
    root.dataset.testGame = file;
    t.toast(`Made ${file}. Press Run, then space, to hear it.`, 'ok', 4000);
  }

  return () => {
    remember(true);
    clearTimeout(rememberTimer);
    stopAll();
    resize?.disconnect();
    try { audio?.close(); } catch {}
    root = null;
  };
});
