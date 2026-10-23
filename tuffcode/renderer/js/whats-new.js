// What's New: after an update, the first time TuffCode opens it shows "Here's what's changed!" with that version's
// notes, once. Help > What's New shows it again. Each version's notes live here (not fetched, so it works offline);
// its pictures go in renderer/whats-new/<version>/ and show at the top, with rounded corners.
(() => {
  const NOTES = {
    '1.2.0': {
      images: ['1.png'],
      notes: `### Real physics in games
- **Things fall, bounce, tumble and get pushed.** \`crate:physics()\` turns it on, with Rapier, a real physics engine. Tune it with \`crate:mass(2)\`, \`crate:bounce(0.6)\` and \`crate:friction(0.4)\`.
- **Kick things around:** \`push\`, \`spin\` and \`velocity\`, or \`world:explode(x, y, z, strength, radius)\` to blast things apart.
- **Know when things hit:** \`crate:on_hit(bumped)\` runs \`bumped(other, strength)\`.
- **Drive a car:** \`car = world:car(0, 1, 10, "red")\`, then \`car:drive()\`: WASD or the arrow keys, with a chase camera.
- **Ragdolls:** \`world:ragdoll(5, 0, 0, "blue")\` is a person that flops when it's pushed or hit.
- **The player pushes crates and can stand on them.** 2D games get physics too: \`game:gravity(900)\` and \`game:walls(true)\`.

### Better models and animation
- The 3D kit has more detail, softer shapes and nicer materials, plus new \`"person"\` and \`"chest"\` models.
- Characters walk with swinging arms and legs and breathe while standing. Trees sway, water ripples, coins spin.

### Juice
- **Slow motion:** \`world:slow_mo(0.3, 2)\` runs everything at 30% for 2 seconds, then eases back. Perfect for a big win.
- **Screen shake:** \`world:shake(0.5)\` shakes the camera for a moment. Try it when something explodes.
- **Floating text:** \`world:pop_text("+10", x, y, z)\` floats up and fades, like points over a coin. 2D games get all three too.
- **Rain and snow:** \`world:weather("rain")\` brings falling streaks, a darker sky and wet ground; \`"snow"\` brings drifting flakes.
- **Day and night:** \`world:day_cycle(120)\` goes from morning to sunset to a starry night and back. \`world:time_of_day(18)\` jumps to 6 pm.

### Game screens
- **Health bars:** \`enemy:health_bar(100)\`, then \`enemy:hurt(10)\` and \`enemy:heal(5)\`. \`enemy:on_death(gone)\` runs when it reaches 0.
- **A countdown:** \`game:countdown(60, times_up)\` ticks down in the corner and turns red at the end.
- **An arrow to anything:** \`world:arrow_to(chest)\` points the way at the edge of the screen and says how far it is.
- **A minimap:** \`world:minimap()\` shows the land and where you are. \`map:mark(coin, "gold")\` adds a dot.

### Interaction
- **Pick things up:** \`player:can_grab()\` lets E pick up the thing you look at. Click to throw it!
- **People who talk:** \`npc:say("Hi!")\` shows a speech bubble, and \`npc:on_talk(talk)\` runs when you walk up and press E.
- **Doors and keys:** \`world:door(0, 0, -5)\` swings open when you walk into it. \`door:needs(key)\` locks it until you find the new \`"key"\`.

### Level pieces
- **Jump pads and boost pads:** \`world:jump_pad(0, 0, 5, 15)\` launches you up, and \`world:boost_pad(0, 0, 10, 20)\` shoots you forward.
- **Moving platforms:** \`lift:path([[0, 2, 0], [10, 2, 0]], 3)\` moves anything along the spots, and you ride it.

### Tuff Engine and AIs
- A **Physics** section in the Inspector (Off, Falls or Fixed, with Mass, Bounce and Friction), and **Car** and **Ragdoll** tiles in Add.
- **Level pieces** in Add: Door, Key, Jump pad, Boost pad, Moving platform and Talking person.
- Claude, Codex, Antigravity and Pumice 1 know all of it, and the checker catches mistakes.`,
    },
  };

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  // The little Markdown the notes use: ### headings, - bullets, **bold**, `code` and [links](https://...).
  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" data-web="$2">$1</a>');
  }
  function render(md) {
    const out = [];
    let list = false;
    for (const line of md.split('\n')) {
      const t = line.trim();
      const bullet = /^- (.*)$/.exec(t);
      if (!bullet && list) { out.push('</ul>'); list = false; }
      if (/^### /.test(t)) out.push(`<h3>${inline(t.slice(4))}</h3>`);
      else if (bullet) { if (!list) { out.push('<ul>'); list = true; } out.push(`<li>${inline(bullet[1])}</li>`); }
      else if (t) out.push(`<p>${inline(t)}</p>`);
    }
    if (list) out.push('</ul>');
    return out.join('');
  }

  let ide = null;
  const has = (version) => !!NOTES[version];

  // The pictures scroll sideways one at a time (dots under them when there's more than one).
  function hero(version, images) {
    if (!images.length) return '';
    const pics = images.map((src, i) => `<img src="whats-new/${esc(version)}/${esc(src)}" alt="" draggable="false" data-i="${i}">`).join('');
    const dots = images.length > 1 ? `<div class="wn-dots">${images.map((_, i) => `<button data-dot="${i}" aria-label="Picture ${i + 1}"${i ? '' : ' class="on"'}></button>`).join('')}</div>` : '';
    return `<div class="wn-hero"><div class="wn-strip">${pics}</div>${dots}</div>`;
  }

  function show(version) {
    const entry = NOTES[version];
    if (!entry) return false;
    close();
    const box = document.createElement('div');
    box.id = 'whatsnew';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-labelledby', 'wn-title');
    // Everything scrolls together (so the scrollbar runs the whole height); the bar with "Let's go" stays put. Until
    // the end is reached, a fade and "Scroll for more" say there's more below.
    box.innerHTML = `<div class="wn-card">
      <div class="wn-scroll">
        ${hero(version, entry.images)}
        <div class="wn-head"><h2 id="wn-title">Here's what's changed!</h2><span class="wn-ver">TuffCode ${esc(version)}</span></div>
        <div class="wn-body">${render(entry.notes)}</div>
        <div class="wn-end">
          <span class="wn-end-mark" aria-hidden="true"></span>
          <b>That's everything new in TuffCode ${esc(version)}.</b>
          <span>Have fun making things! Every update's notes are on <a href="https://github.com/trickortree/tuff-code/releases" data-web="https://github.com/trickortree/tuff-code/releases">GitHub</a>, and Help &gt; What's New brings this back.</span>
        </div>
        <div class="wn-fade" aria-hidden="true"></div>
      </div>
      <div class="wn-foot">
        <span class="wn-more" aria-hidden="true">Scroll for more<svg viewBox="0 0 16 16"><path d="M4 6l4 4 4-4"/></svg></span>
        <button class="btn primary" data-a="close">Let's go</button>
      </div>
    </div>`;
    document.body.appendChild(box);
    const card = box.querySelector('.wn-card');
    const scroller = box.querySelector('.wn-scroll');
    const atEnd = () => card.classList.toggle('at-end', scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 4);
    scroller.addEventListener('scroll', atEnd, { passive: true });
    new ResizeObserver(atEnd).observe(scroller);
    box.querySelectorAll('img').forEach((img) => img.addEventListener('load', atEnd));
    atEnd();
    const strip = box.querySelector('.wn-strip');
    const dots = [...box.querySelectorAll('[data-dot]')];
    strip?.addEventListener('scroll', () => {
      const i = Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth));
      dots.forEach((d, k) => d.classList.toggle('on', k === i));
    });
    dots.forEach((d) => (d.onclick = () => strip.scrollTo({ left: +d.dataset.dot * strip.clientWidth, behavior: 'smooth' })));
    box.addEventListener('mousedown', (e) => { if (e.target === box) close(); });
    box.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-web]');
      if (a) { e.preventDefault(); ide?.openWeb?.(a.dataset.web); }
      if (e.target.closest('[data-a="close"]')) close();
    });
    document.addEventListener('keydown', onKey, true);
    requestAnimationFrame(() => { box.classList.add('in'); box.querySelector('[data-a="close"]').focus(); });
    return true;
  }

  function onKey(e) {
    if (e.key === 'Escape' && document.getElementById('whatsnew')) { e.preventDefault(); e.stopPropagation(); close(); }
  }

  function close() {
    document.removeEventListener('keydown', onKey, true);
    document.getElementById('whatsnew')?.remove();
  }

  window.TuffWhatsNew = {
    init(api) { ide = api; },
    has,
    show,
    close,
    // After an update (not a first install): once per version, when it has notes.
    async maybeShow(version, settings, save) {
      if (!has(version) || settings.whatsNewSeen === version) return false;
      await save({ whatsNewSeen: version });
      return show(version);
    },
  };
})();
