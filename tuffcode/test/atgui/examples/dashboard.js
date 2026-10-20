// Drives examples/dashboard.tuf: waits for the live number to change (app:every), clicks a table row.
const live = T.qa('.at-card .at-heading')[3];
const before = live.textContent;
const changed = await T.until(() => live.textContent !== before, 5000);
const row = T.qa('.at-table tbody tr')[1];
T.click(row);
const toast = await T.until(() => T.find('.at-toast', 'Order #1041 for Alan Turing'));
const selected = row.classList.contains('at-selected');
await T.wait(500);
await T.shot('dashboard');
T.done({ changed: !!changed, toast: !!toast, selected, cards: T.qa('.at-card').length, charts: T.qa('.at-chart').length });
