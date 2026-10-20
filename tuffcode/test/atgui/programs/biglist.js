// Scrolls biglist.tuf's 1,000-item list for 3 seconds, a step every animation frame, and times the frames
// (each step makes the page lay out and paint, which is harder than a wheel scroll). Then picks item 900.
const box = T.q('.at-scroll');
const items = T.qa('.at-item');
const total = box.scrollHeight - box.clientHeight;
const gaps = [];
await new Promise((resolve) => {
  let last = 0;
  const t0 = performance.now();
  function step(now) {
    if (last) gaps.push(now - last);
    last = now;
    box.scrollTop = ((now - t0) * 2.2) % total; // about 2,200 px a second, down and around again
    if (now - t0 < 3000) requestAnimationFrame(step); else resolve();
  }
  requestAnimationFrame(step);
});
// The display's own frame time, from an idle second, to compare against.
const idle = [];
await new Promise((resolve) => { let last = 0; const t0 = performance.now(); function f(now) { if (last) idle.push(now - last); last = now; if (now - t0 < 1000) requestAnimationFrame(f); else resolve(); } requestAnimationFrame(f); });
const target = T.find('.at-item', 'Item 900');
target.scrollIntoView({ block: 'center' });
await T.frame();
const picked = T.q('.at-heading');
const pickMs = await T.watch(picked, () => T.click(target));
const scrolled = T.spread(gaps);
const display = T.spread(idle);
T.done({
  items: items.length, second_lines: T.qa('.at-item-sub').length, scroll_height: box.scrollHeight,
  frames: gaps.length, scroll_fps: +(1000 / (gaps.reduce((a, b) => a + b, 0) / gaps.length)).toFixed(1),
  gap_ms: scrolled, display_gap_ms: display, long_frames: gaps.filter((g) => g > display.median * 1.5 + 4).length,
  pick_ms: +pickMs.toFixed(2), picked: picked.textContent, selected: target.classList.contains('at-selected'),
});
