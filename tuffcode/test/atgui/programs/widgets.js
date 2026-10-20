// Drives programs/widgets.tuf with real DOM events. Each step waits for Python's answer (a change in the
// page, or a short pause for steps that only `say` something), so what the program says stays in order.
const checks = {};
const said = () => T.wait(120);
const btn = (text) => T.find('.at-btn', text);
const counter = T.find('.at-text', '0');

T.click(btn('Add one'));
await T.until(() => counter.textContent === '1');
T.click(btn('Add one'));
checks.counter = !!(await T.until(() => counter.textContent === '2'));
T.click(btn('Named')); await said();

const box = T.q('.at-input');
T.type(box, 'hi'); await said();
T.key('Enter', {}, box); await said();
const area = T.q('.at-textarea');
T.type(area, 'hello');
T.key('Enter', {}, area);
checks.textareaCleared = !!(await T.until(() => area.value === ''));

T.click(T.find('.at-check', 'Tick me')); await said();
T.click(T.find('.at-check', 'Switch me')); await said();
const slider = T.q('.at-slider');
slider.value = 7; slider.dispatchEvent(new Event('input', { bubbles: true })); await said();
checks.sliderFill = slider.style.getPropertyValue('--p') === '70%';

const dd = T.q('.at-dropdown');
T.click(dd);
const blue = await T.until(() => T.find('.at-menu.at-open .at-mi', 'Blue'));
checks.dropdownMenu = !!blue;
T.click(blue);
checks.dropdownLabel = !!(await T.until(() => dd.textContent.trim() === 'Blue'));

const banana = T.find('.at-item', 'Banana');
T.click(banana);
checks.itemSelected = !!(await T.until(() => banana.classList.contains('at-selected')));
const alan = T.qa('.at-table tbody tr')[1];
T.click(alan); await said();
checks.rowSelected = alan.classList.contains('at-selected');

T.click(T.find('.at-tab', 'Two'));
checks.tabShown = !!(await T.until(() => T.find('.at-tabpage', 'Second page').style.display !== 'none' && T.find('.at-tabpage', 'First page').style.display === 'none'));

const card = T.find('.at-card', 'Hover or click me');
T.hover(card, true); await said();
T.hover(card, false); await said();
T.click(card); await said();
checks.cardRadius = getComputedStyle(card).borderTopLeftRadius === '12px';
checks.cardCss = getComputedStyle(card).outlineColor === 'rgb(0, 128, 0)';
checks.hoverRule = [...document.adoptedStyleSheets].some((s) => [...s.cssRules].some((r) => r.selectorText && r.selectorText.includes(`[data-at="${card._tv}"]:hover`) && r.style.getPropertyValue('background') === 'rgb(255, 0, 0)'));
T.hover(card, true);
checks.tooltip = !!(await T.until(() => { const tip = T.q('.at-tip.at-shown'); return tip && tip.textContent === 'A tip'; }, 2000));
T.hover(card, false); await said();

const cherry = T.find('.at-item', 'Cherry');
T.right(cherry);
const rename = await T.until(() => T.find('.at-menu.at-open .at-mi', 'Rename'));
checks.contextMenu = !!rename;
T.click(rename); await said();
checks.menuClosed = !!(await T.until(() => !T.q('.at-menu.at-open')));

// Chromium only fires real focus events while the window is the foreground one, which a test window may or
// may not be, so these are sent by hand (atgui's listener and the bridge still do the rest).
const focusBox = T.qa('.at-input')[1];
focusBox.dispatchEvent(new FocusEvent('focusin', { bubbles: true, relatedTarget: box })); await said();
focusBox.dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: box })); await said();
T.key('k', { ctrlKey: true }); await said();

T.click(btn('Open modal'));
const overlay = await T.until(() => T.q('.at-overlay.at-shown'));
checks.modalOpened = !!overlay;
T.key('Escape');
checks.modalClosed = !!(await T.until(() => !T.q('.at-overlay.at-shown')));
await said();

T.click(btn('Probe'));
await T.until(() => T.qa('.at-table tbody tr').length === 3);
await said();
checks.listItems = JSON.stringify(T.qa('.at-item').map((e) => e.textContent)) === '["Banana","Cherry","Date"]';
checks.markdownAdd = T.q('.at-md').innerHTML.includes('<strong>world</strong> and <em>more</em>');
checks.codeSet = T.q('.at-codeblock pre').textContent === 'say 2';
const badge = T.q('.at-badge');
checks.badge = badge.textContent === 'Gamma' && badge.classList.contains('at-danger') && !badge.classList.contains('at-info');
checks.progress = T.q('.at-bar').style.width === '75%';
checks.counterHidden = counter.style.display === 'none';
checks.switchOff = !T.find('.at-check', 'Switch me').querySelector('input').checked;
checks.sliderSet = slider.value === '9' && slider.style.getPropertyValue('--p') === '90%';
checks.highlighted = T.q('.at-codeblock .at-k') !== null;
// Layout, pictures, styling, animation and the escape hatches.
const app = T.q('.at-app');
checks.font = /Charter|Georgia/.test(getComputedStyle(app).fontFamily);
checks.appCss = getComputedStyle(T.q('.probe-rule')).letterSpacing === '3px';
checks.htmlWidget = T.q('.at-html .probe-rule').textContent === 'Raw HTML';
const pic = T.q('img.at-image');
checks.picture = !!(await T.until(() => pic.complete && pic.naturalWidth === 64)) && pic.getBoundingClientRect().width === 48;
const split = T.q('.at-split');
checks.split = split.children.length === 3 && split.children[1].classList.contains('at-handle') && split.children[0].getBoundingClientRect().width === 180 && split.children[2].classList.contains('at-grow');
const spaced = T.find('.at-row', 'Grows');
checks.gapAlign = getComputedStyle(spaced).columnGap === '20px' && getComputedStyle(spaced).alignItems === 'flex-start';
const grows = T.find('.at-text', 'Grows');
checks.grow = grows.classList.contains('at-grow') && getComputedStyle(grows).flexGrow === '1';
checks.icon = T.q('.at-icon use').getAttribute('href') === '#at-i-star' && !!document.getElementById('at-i-star');
checks.avatar = T.q('.at-avatar').textContent === 'AL';
const fancy = T.find('.at-card', 'Fancy');
const fs = getComputedStyle(fancy);
checks.gradient = fs.backgroundImage.includes('linear-gradient');
checks.glass = fs.backdropFilter.includes('blur');
checks.shadow = fs.boxShadow !== 'none';
checks.animation = fancy.getAnimations().some((a) => a.playState === 'running');
checks.pressedRule = [...document.adoptedStyleSheets].some((sh) => [...sh.cssRules].some((r) => r.selectorText && r.selectorText.includes(`[data-at="${fancy._tv}"]:active`)));
checks.chart = T.qa('.at-chart rect').length === 4;
checks.shownAgain = T.find('.at-small', 'Shown later').style.display !== 'none';
await T.shot('widgets');
T.done({ checks });
