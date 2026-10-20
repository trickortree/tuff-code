// Answers popups.tuf's popups: types a name and presses Enter, presses Space on the focused Yes (a real key
// press: an app's Space presses its buttons), presses Escape (= No), clicks OK.
const shown = () => { const all = T.qa('.at-overlay.at-shown'); return all[all.length - 1]; };
const field = await T.until(() => shown() && shown().querySelector('.at-input'));
const prompt = shown().querySelector('.at-text').textContent;
let o = null;
await T.shot('popup-ask');
await T.wait(250);
T.type(field, 'Ada');
T.key('Enter', {}, field);
o = await T.until(() => shown() && shown().textContent.includes('Are you sure?'));
await T.wait(150);
await T.until(() => document.activeElement && document.activeElement.textContent.trim() === 'Yes');
await T.press(' ');
o = await T.until(() => shown() && shown().textContent.includes('Really sure?'));
T.key('Escape');
o = await T.until(() => shown() && shown().textContent.includes('All done'));
T.click(T.find('.at-overlay.at-shown .at-btn', 'OK'));
T.log('answered all four, prompt was: ' + prompt);
// The program closes its own window after the last popup, so there's nothing more to do here.
