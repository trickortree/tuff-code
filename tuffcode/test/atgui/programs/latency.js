// 100 clicks and 100 keystrokes, each timed from the DOM event to seeing the Tuff function's change.
const count = T.q('.at-heading');
const mirror = T.q('.at-text');
const button = T.find('.at-btn', 'Click');
const box = T.q('.at-input');
await T.wait(300);
const clicks = [];
for (let i = 0; i < 100; i++) { clicks.push(await T.watch(count, () => T.click(button))); await T.wait(4); }
const keys = [];
const word = 'the quick brown fox jumps over the lazy dog ';
let typed = '';
for (let i = 0; i < 100; i++) {
  typed += word[i % word.length];
  keys.push(await T.watch(mirror, () => T.type(box, typed)));
  await T.wait(4);
}
T.done({ click_ms: T.spread(clicks), key_ms: T.spread(keys), count: count.textContent, mirror_ok: mirror.textContent === typed });
