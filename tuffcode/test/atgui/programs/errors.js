// Clicks the broken button 3 times, types 3 times, lets the broken timer run for half a second, and checks
// that the good button still works in between. run_all.py counts the reports in stderr.
const broken = T.find('.at-btn', 'Broken');
const good = T.find('.at-btn', 'Good');
const box = T.q('.at-input');
for (let i = 0; i < 3; i++) {
  T.click(broken); await T.wait(60);
  T.type(box, 'abc'.slice(0, i + 1)); await T.wait(60);
  T.click(good); await T.wait(60);
}
await T.wait(500);
T.done({ clicked: true });
