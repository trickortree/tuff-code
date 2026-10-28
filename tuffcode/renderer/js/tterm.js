// tterm (1.5.0): a terminal game's screen in the Run panel. tuff.py says it as a line whose look has screen: 1 (w and
// h are its size, live: 1 while screen:every_frame runs and wants keys), and rewrites it as it changes; ide.js's
// richLine colours it and hands it here. Click it to play: it takes the keys, and each one goes to the program over
// stdin as a line, \x1b]tuff;key;down;<name>\x07 (up when it's let go, none for all of them at once). Esc lets go,
// and the program gets it too: it ends screen:every_frame, as in a terminal. Clicking anywhere else lets go and the
// game carries on. The hint ("Click to play", "Esc to let go") is drawn by CSS, so runOutputText() never sees it.
(() => {
  const NAMED = {
    ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Left: 'left', Right: 'right', Up: 'up', Down: 'down',
    ' ': 'space', Spacebar: 'space', Enter: 'enter', Escape: 'escape', Esc: 'escape', Tab: 'tab', Backspace: 'backspace', Delete: 'delete',
  };

  // tterm's name for a key, as tuff_tterm.py's key_name has it: what it types (a letter in lower case), or the
  // name of an arrow, space, Enter and the rest. null for keys a terminal never sees on their own (Shift, F5...).
  function keyName(e) {
    if (NAMED[e.key]) return NAMED[e.key];
    if (typeof e.key === 'string' && [...e.key].length === 1 && e.key.trim()) return e.key.toLowerCase();
    return null;
  }

  function keyLine(kind, name) {
    return `\x1b]tuff;key;${kind}${name ? `;${name}` : ''}\x07\n`;
  }

  function hint(span) {
    const t = span.tterm;
    const playing = t.live && document.activeElement === span;
    span.classList.toggle('playing', playing);
    if (t.live) span.dataset.hint = playing ? 'Esc to let go' : 'Click to play';
    else delete span.dataset.hint;
  }

  function letGo(span) {
    const t = span.tterm;
    if (t.down.size) {
      t.down.clear();
      t.send?.(keyLine('none'));
    }
  }

  // Makes a say line a screen (the first time) and keeps up with its look: live or not, and who its keys go to
  // (send(line), or null for the second player's copy, which reads no keys).
  function screen(span, look, send) {
    span.classList.add('tscreen');
    if (!span.tterm) {
      const t = { live: false, send: null, down: new Map(), started: false };
      span.tterm = t;
      span.tabIndex = -1;
      span.addEventListener('keydown', (e) => {
        if (!t.live || e.ctrlKey || e.altKey || e.metaKey) return; // the IDE's own shortcuts still work
        const name = keyName(e);
        if (!name) return;
        e.preventDefault();
        e.stopPropagation();
        t.down.set(e.code || name, name);
        t.send?.(keyLine('down', name)); // (and again as it repeats, as in a terminal)
        if (name === 'escape') span.blur();
      });
      span.addEventListener('keyup', (e) => {
        const name = t.down.get(e.code || keyName(e));
        if (!name) return;
        t.down.delete(e.code || name);
        e.preventDefault();
        t.send?.(keyLine('up', name));
      });
      span.addEventListener('focus', () => hint(span));
      span.addEventListener('blur', () => { letGo(span); hint(span); });
      span.addEventListener('mousedown', (e) => {
        if (!t.live) return;
        e.preventDefault(); // (no text selection starting in the game)
        span.focus({ preventScroll: true });
      });
    }
    const t = span.tterm;
    t.send = send || null;
    t.live = !!(look && look.live && send);
    span.classList.toggle('live', t.live);
    span.tabIndex = t.live ? 0 : -1;
    if (!t.live && document.activeElement === span) span.blur();
    if (t.live && !t.started) {
      t.started = true; // the game has just started: it gets the keys at once, as a question's box gets the typing
      span.focus({ preventScroll: true });
    }
    hint(span);
  }

  // The program ended: no screen takes keys any more.
  function ended(root) {
    for (const span of (root || document).querySelectorAll('.tscreen.live')) screen(span, null, null);
  }

  window.TuffTerm = { keyName, keyLine, screen, ended };
})();
