// Checks the title bar, maximizes and restores the real window (its button, then a double-click),
// resizes it from Python, and closes it with the title bar's close button.
const checks = {};
const bar = T.q('.at-titlebar');
checks.dragRegions = bar.classList.contains('pywebview-drag-region') && T.q('.at-tb-slot').classList.contains('pywebview-drag-region');
checks.buttons = T.qa('.at-wb').length === 3;
checks.grips = T.qa('.at-grip').length === 3;
checks.title = T.q('.at-tb-title').textContent === 'My frameless app';
checks.search = !!T.q('.at-tb-slot .at-input');
await T.shot('frameless');
const w0 = innerWidth;
T.click(T.qa('.at-wb')[1]);
checks.maximized = !!(await T.until(() => innerWidth > w0 + 100, 4000));
T.click(T.qa('.at-wb')[1]);
checks.restored = !!(await T.until(() => Math.abs(innerWidth - w0) < 4, 4000));
T.dblclick(bar);
checks.dblMaximized = !!(await T.until(() => innerWidth > w0 + 100, 4000));
T.dblclick(bar);
checks.dblRestored = !!(await T.until(() => Math.abs(innerWidth - w0) < 4, 4000));
tv.emit('at-resize', { w: 760, h: 500 });
checks.resized = !!(await T.until(() => Math.abs(innerWidth - 760) < 4 && Math.abs(innerHeight - 500) < 4, 4000));
T.log('checks ' + JSON.stringify(checks));
T.click(T.qa('.at-wb')[2]);
