window.TUFF_KEYWORDS = [
  'say', 'input', 'func', 'return', 'if', 'elif', 'else', 'then', 'while', 'for', 'in',
  'break', 'continue', 'and', 'or', 'not', 'is', 'true', 'false', 'nil', 'flush', 'import', 'mention',
];

window.TUFF_METHOD_DOCS = {
  clock: ['app:clock("analog", size)', 'A ticking clock. Use "digital" for numbers. Change the time with :set(10, 30).'],
  spinner: ['app:spinner("Loading...")', 'A spinning loading ring.'],
  checkbox: ['app:checkbox("Label", false)', 'A tick box. Read it with :value.'],
  dropdown: ['app:dropdown(["A", "B"], "A")', 'Pick one choice from a list.'],
  speed: ['thing:speed 2', 'Animation speed: 1 is normal, 2 is twice as fast, 0.5 is half speed.'],
  gradient: ['app:gradient("#00c6ff", "#7b2ff7")', 'mtgui: sets the two accent gradient colors.'],
  now: ['clock:now', 'Sets a clock back to the real time.'],
  pause: ['clock:pause', 'Stops a clock.'],
  resume: ['clock:resume', 'Starts a paused clock again.'],
  flip: ['switch:flip', 'Turns a switch or checkbox the other way.'],
  options: ['dropdown:options(["A", "B"])', 'Replaces the choices in a dropdown.'],
  start: ['spinner:start', 'Starts a spinner spinning.'],
  stop: ['spinner:stop', 'Stops a spinner.'],
  heading: ['app:heading "Text"', 'Big bold title text.'],
  text: ['app:text "Text"', 'Normal text. Change it later with :set. On a tap response, res:text gives back what the server sent, as text.'],
  small: ['app:small "Text"', 'Small grey text for hints and captions.'],
  button: ['app:button("Text", clicked, "primary")', 'A button. clicked is the function to run. Styles: primary, secondary, outline, ghost, success, danger.'],
  input: ['app:input "Hint"', 'A text box. Read it with :value.'],
  toggle: ['app:toggle("Label", true)', 'An on/off switch.'],
  slider: ['app:slider(min, max, start)', 'Drag to pick a number.'],
  progress: ['app:progress(percent)', 'A progress bar from 0 to 100.'],
  image: ['app:image("pic.png", width)', 'Shows a .png or .gif from your project folder.'],
  divider: ['app:divider', 'A thin line between sections.'],
  space: ['app:space 20', 'Empty space.'],
  row: ['row = app:row', 'Puts the things you add to it side by side.'],
  card: ['card = app:card', 'A rounded panel to group things.'],
  page: ['home = app:page "Home"', 'A page of your app. Add things to it like a card. Only one page shows at a time, starting with the first one you make.'],
  open: ['home:open', 'Shows this page and hides the other pages.'],
  opened: ['home:opened shown', 'Runs shown each time this page opens.'],
  showing: ['home:showing', 'Gives back true if this page is the one on screen.'],
  title: ['app:title "Title"', 'Changes the window title, even while running.'],
  icon: ['app:icon "icon.png"', 'Changes the window icon (.png, .gif or .ico in your project folder).'],
  size: ['app:size(width, height)', 'Resizes the window. On a tap data object, data:size gives how many names it has.'],
  theme: ['app:theme "light"', 'Switches between "dark" and "light".'],
  accent: ['app:accent "purple"', 'Changes the highlight color: blue, purple, pink, red, orange, yellow, green, teal or a hex code.'],
  every: ['app:every(seconds, tick)', 'Runs a function again and again, like a clock. To pause it, check a variable at the top of the function: if not running: return'],
  after: ['app:after(seconds, done)', 'Runs a function once after a delay.'],
  alert: ['app:alert "Message"', 'Pops up a message with an OK button.'],
  confirm: ['app:confirm "Are you sure?"', 'Pops up Yes/No and gives back true or false.'],
  ask: ['app:ask "Question?"', 'Pops up a text box and gives back what was typed.'],
  close: ['app:close', 'Closes the window.'],
  set: ['thing:set value', 'Changes the text or value: of a label, button, text box, slider, progress bar, switch or dropdown. It doesn\'t run :change (for a switch or checkbox, switch:set(true, true) does). A clock takes :set(hours, minutes, seconds); an image takes a new picture file. On a tap data object, data:set("name", value) adds or changes a value.'],
  value: ['thing:value', 'Gives back the current value: the text of a label, button or text box; the chosen option of a dropdown; true or false for a switch or checkbox; a number for a slider or progress bar; "14:05:09" for a clock.'],
  change: ['thing:change fn', 'Runs fn when the value changes: on every key typed in a text box, or when a dropdown, switch, checkbox or slider changes. If fn has an input, it gets the new value, like func moved(v):'],
  enter: ['box:enter fn', 'Runs fn when Enter is pressed in a text box. If fn has an input, it gets the text.'],
  focus: ['box:focus', 'Puts the cursor in a text box, ready for typing.'],
  click: ['button:click fn', 'Changes which function the button runs.'],
  style: ['button:style "danger"', 'Changes a button\'s style (primary, secondary, outline, ghost, success, danger), or a clock\'s style ("analog" or "digital").'],
  color: ['label:color "red"', 'Changes the text color: blue, purple, pink, red, orange, yellow, green, teal, white, black, gray or "#rrggbb". "text" puts it back to normal.'],
  disable: ['button:disable', 'Greys out a button so it can\'t be clicked.'],
  enable: ['button:enable', 'Makes a disabled button clickable again.'],
  hide: ['thing:hide', 'Hides it.'],
  show: ['thing:show', 'Shows it again after :hide.'],
  remove: ['thing:remove', 'Removes a widget for good. On a list, items:remove value takes that value out (by value, not by position).'],
  clear: ['thing:clear', 'Empties a text box, or a line you already said. On a row, card or page, removes everything inside it.'],
  rewrite: ['line:rewrite value', 'Replaces the text of a line you already said.'],
  append: ['line:append value', 'Adds text to the end of a line you already said.'],
  add: ['items:add value', 'Lists: adds value to the end of the list.'],
  pop: ['items:pop', 'Lists: takes the last item off the list and gives it back.'],
  has: ['thing:has value', 'Lists: true if the list holds value. Text: true if the text contains it, like name:has "a". Data objects (tap): true if it has that name, like user:has "email".'],
  upper: ['text:upper', 'Text: gives back the text in CAPITAL letters.'],
  lower: ['text:lower', 'Text: gives back the text in small letters.'],
  trim: ['text:trim', 'Text: gives back the text without spaces at the start and end.'],
  status: ['res:status', 'tap responses: the status code, like 200 (it worked) or 404 (not found).'],
  ok: ['res:ok', 'tap responses: true if the request worked (a status from 200 to 299). Errors like 404 don\'t stop the program, so check this.'],
  json: ['res:json', 'tap responses: reads what the server sent as JSON. An object {...} gives a data object (read it with :get), an array [...] gives a list.'],
  header: ['res:header("Content-Type")', 'tap responses: one header the server sent, or nil if it didn\'t send it.'],
  get: ['data:get("name")', 'tap data objects: the value with that name, or nil if there isn\'t one. Objects inside are data objects too, and arrays are lists.'],
  keys: ['data:keys', 'tap data objects: a list of all its names. Loop over it with: for name in data:keys():'],
};

window.TUFF_LIBS = {
  tgui: {
    window: ['tgui.window("Title", width, height)', 'Opens a new app window. Width and height are optional.'],
  },
  mtgui: {
    window: ['mtgui.window("Title", width, height)', 'Opens a modern app window with gradients, gloss and shine.'],
  },
  anims: {
    loading: ['anims.loading(text, seconds)', 'A spinning / - \\ | loader with animated dots. Both inputs are optional.'],
    bar: ['anims.bar(text, seconds, width)', 'A progress bar that fills from 0% to 100%. width is how many blocks wide it is (20 by default).'],
    type: ['anims.type(text, speed)', 'Types text out one letter at a time. speed is seconds per letter (0.04 by default), so a bigger number is slower.'],
    countdown: ['anims.countdown(start, then)', 'Counts down on one line, then shows the `then` text.'],
  },
  tap: {
    get: ['tap.get(url, headers)', 'Gets a web page or API and gives back a response: res:status, res:ok, res:text, res:json, res:header(name). headers is optional: a data object.'],
    post: ['tap.post(url, body, headers)', 'Sends body to url and gives back a response. Text goes as plain text; a data object or a list goes as JSON. headers is optional.'],
    put: ['tap.put(url, body, headers)', 'Like tap.post, but for replacing what is at url. headers is optional.'],
    delete: ['tap.delete(url, headers)', 'Asks the server to delete what is at url, and gives back a response. headers is optional.'],
    data: ['tap.data()', 'Makes an empty data object, for a JSON body or headers. Fill it with :set("name", value).'],
  },
};

window.TUFF_DOCS = {
  say: ['say value', 'Shows a line in the Run window. `line = say "hi"` keeps the line so you can :rewrite it later.'],
  input: ['input "question"', 'Asks the person running the program to type something and gives back their answer as text.'],
  func: ['func name(inputs):', 'Makes a function. It gives back its last value automatically, or whatever you `return`.'],
  return: ['return value', 'Leaves the function and gives back a value.'],
  if: ['if condition:', 'Runs the indented block only when the condition is true. `then` works instead of `:`.'],
  elif: ['elif condition:', 'Checked when the `if` above it was false.'],
  else: ['else:', 'Runs when nothing above it matched.'],
  then: ['then', 'Starts a block, same as `:`. Writing both (`then:`) works too.'],
  while: ['while condition:', 'Repeats the block as long as the condition stays true.'],
  for: ['for item in list:', 'Runs the block once for every item in a list, text or range().'],
  is: ['a is b', 'True when both sides are equal. Use `is not` for the opposite.'],
  print: ['print(a, b, ...)', 'Like `say`, but takes several values separated by commas.'],
  number: ['number(text)', 'Turns text like "42" into the number 42. Text that is not a number gives err instead of stopping: check with `if number(t) is err:`.'],
  num: ['num(text)', 'Short for number(): num("42") is 42, and text that is not a number gives err.'],
  int: ['int(value)', 'A whole number, dropping any decimals: int("42") is 42, int(3.7) is 3. Text that is not a number gives err.'],
  text: ['text(value)', 'Turns any value into text.'],
  str: ['str(value)', 'Same as text(): turns any value into text, like str(5) + " apples".'],
  err: ['err', 'What number(), num() and int() give back for text that is not a number. Check with `if num(answer) is err:`. Using an err in maths stops the program and says why.'],
  len: ['len(value)', 'How many characters are in some text, or items in a list.'],
  round: ['round(number, digits)', 'Rounds a number. digits is optional.'],
  random: ['random(low, high)', 'A random whole number from low to high, both included.'],
  wait: ['wait(seconds)', 'Pauses the program. Great with :rewrite for animations.'],
  range: ['range(start, end)', 'A list of numbers from start to end, both included. range(5) is 1 to 5.'],
  flush: ['flush', 'Wipes everything in the Run window. Same as clear(all).'],
  clear: ['clear(lines)', 'Removes the last few lines from the Run window, like clear(2). clear(all) removes everything. (line:clear empties one line you already said.)'],
  all: ['all', 'Means every line, as in clear(all).'],
  import: ['import library', 'Loads a library of extra functions, like: import anims'],
  anims: ['import anims', 'Ready-made animations: loading, bar, type, countdown.'],
  tgui: ['import tgui', 'Tuff GUI: make real app windows with buttons, text boxes, toggles and more.'],
  mtgui: ['mention mtgui', 'Modern Tuff GUI: like tgui with gradients, gloss, shine and glow.'],
  tap: ['mention tap', 'Get and send things on the web (HTTP), like Python\'s requests: tap.get, post, put, delete. JSON comes back as data objects.'],
  mention: ['mention library', 'Loads a library. Works exactly like import.'],
  sqrt: ['sqrt(number)', 'Square root: sqrt(81) is 9.'],
  abs: ['abs(number)', 'Removes the minus sign: abs(-5) is 5.'],
  floor: ['floor(number)', 'Rounds down: floor(3.7) is 3.'],
  ceil: ['ceil(number)', 'Rounds up: ceil(3.2) is 4.'],
  min: ['min(a, b, ...)', 'The smallest number. Also works on a list.'],
  max: ['max(a, b, ...)', 'The biggest number. Also works on a list.'],
  sum: ['sum(a, b, ...)', 'Adds numbers together. Also works on a list.'],
  average: ['average(a, b, ...)', 'The average of some numbers or a list.'],
  pi: ['pi', '3.14159...'],
  rewrite: ['line:rewrite value', 'Replaces the text of a line you already said.'],
  append: ['line:append value', 'Adds text to the end of a line you already said.'],
};

// atgui: its library entry and its methods. TUFF_METHOD_DOCS is one namespace for every library, so a name
// atgui shares with tgui or tap keeps its doc, with atgui's use added at the end.
(() => {
  window.TUFF_LIBS.atgui = {
    window: ['atgui.window("Title", width, height)', 'Opens a modern app window made of real HTML and CSS: sidebars, lists, chat bubbles, dashboards, menus and pop-ups, all styled from Tuff. Width and height are optional.'],
  };
  window.TUFF_DOCS.atgui = ['mention atgui', 'Advanced Tuff GUI: apps that look like the Claude or Codex desktop apps. Sidebars, lists, tables, tabs, markdown, menus, toasts, animations and styling, with no HTML to write.'];
  const docs = window.TUFF_METHOD_DOCS;
  const also = {
    set: 'atgui: also lists (picks an item), tables, markdown, code, charts, badges, icons, avatars, modals and the title bar.',
    value: 'atgui: a list gives the picked item\'s text (nil if none), a table the picked row as a list, tabs the open tab\'s name.',
    change: 'atgui: a list\'s :change gets the picked item\'s text, a table\'s the row (a list), tabs\' the tab\'s name.',
    enter: 'atgui: in a textarea, Enter runs fn and Shift+Enter starts a new line.',
    focus: 'atgui: box:focus fn runs fn(true) when the cursor goes in and fn(false) when it leaves.',
    add: 'atgui: list:add("Inbox") adds an item and gives it back; table:add(["Ada", "Admin"]) adds a row; markdown, code and charts add to the end.',
    remove: 'atgui: list:remove "Inbox" takes an item out of a list or table (with no input, the whole widget goes).',
    clear: 'atgui: empties a list, table, markdown or code block too.',
    open: 'atgui: tabs:open "Home", dlg:open shows a modal, menu:open shows a menu under what was just clicked.',
    opened: 'atgui: also for a tab.',
    close: 'atgui: dlg:close closes a modal; menu:close closes a menu.',
    style: 'atgui: w:style(name, value) with friendly names: background, color, radius, padding, margin, border, shadow, size, bold, opacity, glass, blur, gradient, width, height, scale... Start the name with hover, pressed or focus for that moment, like btn:style("hover scale", 1.05). Buttons, badges and spinners also take one style name.',
    color: 'atgui: also icons.',
    icon: 'atgui: btn:icon "send" puts a built-in icon on a button (or a list item, badge or menu item); row:icon("search", 20) shows one; app:icon "logo.png" sets the window\'s icon.',
    image: 'atgui: also .jpg, .webp and .svg, or a web address.',
    theme: 'atgui: also "system", which follows the computer.',
    accent: 'atgui: also indigo and gray.',
    start: 'atgui: timer:start runs a timer from app:every again.',
    stop: 'atgui: timer:stop pauses a timer from app:every or app:after.',
    small: 'atgui: item:small "text" gives a list item a second line.',
    spinner: 'atgui: spinner:style "dots" makes three bouncing dots, like "someone is typing".',
    every: 'atgui: gives back a timer with :stop and :start.',
    after: 'atgui: gives back a timer with :stop.',
    title: 'atgui: also changes the title bar\'s text.',
    button: 'atgui: also the gradient style, and the function gets the button\'s text (or leave the input out).',
    page: 'atgui: works the same, as screens in the window\'s main area (tabs show a tab bar instead).',
    gradient: 'atgui: the accent and its partner color (gradient buttons, progress bars).',
  };
  for (const [name, text] of Object.entries(also)) if (docs[name] && text) docs[name] = [docs[name][0], `${docs[name][1]} ${text}`];
  Object.assign(docs, {
    textarea: ['app:textarea "Message"', 'atgui: a text box for several lines that grows as you type. With :enter, Enter runs the function and Shift+Enter starts a new line.'],
    switch: ['app:switch("Dark mode", true)', 'atgui: an on/off switch (tgui calls it toggle). Read it with :value.'],
    list: ['items = app:list(["Inbox", "Sent"])', 'atgui: a list to pick from. items:add("x") gives back the item (:icon, :small, :badge); items:change fn gets the picked item\'s text.'],
    table: ['t = app:table(["Name", "Role"])', 'atgui: a table. t:add(["Ada", "Admin"]) adds a row; t:change fn gets the picked row as a list.'],
    tabs: ['tabs = app:tabs()', 'atgui: tabs. home = tabs:tab "Home" makes one to add widgets to; tabs:open "Home", tabs:value, tabs:change fn.'],
    tab: ['home = tabs:tab "Home"', 'atgui: a tab of a tabs widget. Add widgets to it like a card.'],
    column: ['col = row:column', 'atgui: stacks things down, like the window does. Useful inside a row.'],
    grid: ['g = app:grid(3)', 'atgui: things in equal columns (with no number, as many as fit). card:style("span", 2) makes a card two columns wide.'],
    scroll: ['msgs = app:scroll()', 'atgui: a part that scrolls on its own and takes the space left, like a chat\'s messages. msgs:to_bottom scrolls to the end.'],
    split: ['panes = app:split(260)', 'atgui: two panes side by side; the first is 260 wide, with a handle to drag between them.'],
    sidebar: ['side = app:sidebar(240)', 'atgui: a column down the left side of the window, or app:sidebar(240, "right").'],
    avatar: ['app:avatar("Ada Lovelace")', 'atgui: a round badge with someone\'s initials, or a picture file. A color is optional: app:avatar("Ada", "pink").'],
    badge: ['app:badge("New", "success")', 'atgui: a small pill of text. Styles: accent, gray, success, warning, danger, info, outline. item:badge "3" shows a count on a list item.'],
    markdown: ['app:markdown "**bold**"', 'atgui: formatted text from Markdown: headings, **bold**, *italic*, `code`, lists, links, tables and code blocks. :add adds more at the end, for replies that arrive bit by bit.'],
    code: ['app:code(text, "tuff")', 'atgui: a code block with colors and a Copy button.'],
    html: ['app:html("<b>Hi</b>")', 'atgui, for experts: your own HTML.'],
    chart: ['app:chart([3, 8, 5], "line")', 'atgui: a small line or bar chart. chart:add 9 adds a point; chart:set([...]) replaces them all.'],
    gap: ['box:gap 12', 'atgui: the space between the things in a row, column, card, grid or the window.'],
    padding: ['box:padding 20', 'atgui: the space inside the edges of a row, column, card or the window.'],
    align: ['box:align "center"', 'atgui: lines things up across a row or column: start, center, end or stretch.'],
    justify: ['row:justify "between"', 'atgui: spreads things along a row or column: start, center, end, between, around or evenly.'],
    grow: ['w:grow', 'atgui: makes it take the space left over in its row or column.'],
    fill: ['w:fill', 'atgui: stretches it across its row or column.'],
    width: ['w:width 200', 'atgui: sets the width (pixels, or text like "50%").'],
    height: ['w:height 120', 'atgui: sets the height (pixels, or text like "50%").'],
    drag: ['bar:drag', 'atgui: dragging it moves a window that has no frame.'],
    tooltip: ['w:tooltip "Hint"', 'atgui: a little label that shows when the mouse rests on it.'],
    hover: ['w:hover fn', 'atgui: runs fn(true) when the mouse goes over it and fn(false) when it leaves.'],
    clicked: ['w:clicked fn', 'atgui: runs fn when it\'s clicked. Works on any widget; fn gets its text (or leave the input out).'],
    animate: ['w:animate "slide-up"', 'atgui: fade-in, fade-out, slide-up, slide-down, slide-left, slide-right, pop, zoom-in, zoom-out, bounce, shake, pulse, spin, wiggle, float, blink. w:animate("pulse", 1, "forever") repeats; "none" stops.'],
    css: ['w:css("letter-spacing: 2px")', 'atgui, for experts: adds CSS to it. app:css(".at-card { ... }") adds CSS rules to the whole window.'],
    font: ['app:font "rounded"', 'atgui: the window\'s font: system, rounded, serif, mono, or a font\'s name.'],
    frameless: ['app:frameless', 'atgui: a window without the system\'s frame or title bar. Use it at the top of the program.'],
    titlebar: ['bar = app:titlebar("My App")', 'atgui: a frameless window with its own title bar (drag it to move; minimize, maximize and close). Add things to it like a row.'],
    modal: ['dlg = app:modal("Rename")', 'atgui: a dialog over the window. Add widgets to it, then dlg:open and dlg:close; Escape or a click outside closes it. dlg:closed fn.'],
    menu: ['m = app:menu()', 'atgui: a pop-up menu: m:item("Copy", copy), m:divider. w:menu m opens it on a right-click; m:open opens it under what was just clicked.'],
    item: ['m:item("Delete", delete_it, "danger")', 'atgui: adds an item to a menu. Its function gets the text of the list item that was right-clicked (or nil).'],
    toast: ['app:toast("Saved", "success")', 'atgui: a message that pops up in the corner for a few seconds: info, success, warning or error.'],
    key: ['app:key("ctrl+s", save)', 'atgui: runs a function when a key is pressed: "ctrl+s", "escape", "f5", "ctrl+shift+n"...'],
    closed: ['app:closed fn', 'atgui: runs fn when the window closes (or a modal: dlg:closed fn).'],
    minimize: ['app:minimize', 'atgui: minimizes the window.'],
    maximize: ['app:maximize', 'atgui: maximizes the window, or puts it back.'],
    password: ['box:password', 'atgui: hides what\'s typed in a text box, with dots.'],
    items: ['items:items()', 'atgui: the texts of every item in a list, as a list.'],
    to_bottom: ['msgs:to_bottom', 'atgui: scrolls a scroll() to the end.'],
    to_top: ['msgs:to_top', 'atgui: scrolls a scroll() to the start.'],
    select: ['item:select', 'atgui: picks this list item (or table row), without running :change.'],
  });
})();

const TUFF_BUILTINS = ['print', 'number', 'num', 'int', 'text', 'str', 'len', 'round', 'random', 'wait', 'range', 'clear', 'sqrt', 'abs', 'floor', 'ceil', 'min', 'max', 'sum', 'average'];

// A line that opens an indented block: if/elif/else/while/for/func ending in ':' or 'then'.
const BLOCK_OPENER = /^\s*(if|elif|else|while|for|func)\b.*(:|\bthen)\s*(#.*)?$/;
const BLOCK_START = /^\s*(if|elif|else|while|for|func)\b/;

// True when the end of `text` is inside a "string", a 'string' or a # comment.
function insideStringOrComment(text) {
  let quote = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === '\\') i++;
      else if (c === quote) quote = null;
    } else if (c === '"' || c === "'") quote = c;
    else if (c === '#') return true;
  }
  return quote !== null;
}

// Should typing ':' or '.' just before `position` open the suggestion list?
// Yes for a method call (app:) or a library (tgui.); no for the colon that opens a block
// (func greet():, if x is 1:, else:), numbers (3.) and anything inside a string or comment.
window.tuffWantsSuggest = function tuffWantsSuggest(model, position) {
  const line = model.getLineContent(position.lineNumber);
  const before = line.slice(0, position.column - 1);
  if (insideStringOrComment(before)) return false;
  if (before.endsWith('.')) {
    const lib = before.match(/([A-Za-z_]\w*)\.$/);
    return !!(lib && window.TUFF_LIBS[lib[1]]);
  }
  if (!/[A-Za-z_]\w*:$/.test(before)) return false;
  const atEnd = !line.slice(position.column - 1).trim();
  return !(atEnd && BLOCK_START.test(line));
};

window.registerTuff = function registerTuff(monaco, accent) {
  monaco.languages.register({ id: 'tuff', extensions: ['.tuf'], aliases: ['Tuff', 'tuff'] });

  monaco.languages.setMonarchTokensProvider('tuff', {
    keywords: window.TUFF_KEYWORDS.filter((k) => !['true', 'false', 'nil'].includes(k)),
    constants: ['true', 'false', 'nil', 'err', 'all', 'pi'],
    builtins: TUFF_BUILTINS,
    libs: Object.keys(window.TUFF_LIBS),
    operators: ['=', '==', '!=', '<', '>', '<=', '>=', '+', '-', '*', '/', '%', '^', '+=', '-=', '*=', '/='],
    symbols: /[=><!+\-*\/%^]+/,
    tokenizer: {
      root: [
        [/#.*$/, 'comment'],
        [/(func)(\s+)([a-zA-Z_]\w*)/, ['keyword', '', 'function.decl']],
        [/(:)([a-zA-Z_]\w*)/, ['delimiter', 'method']],
        [/([a-zA-Z_]\w*)(\.)([a-zA-Z_]\w*)/, [{ cases: { '@libs': 'library', '@default': 'identifier' } }, 'delimiter', 'function']],
        [/[a-zA-Z_]\w*(?=\s*\()/, { cases: { '@keywords': 'keyword', '@builtins': 'predefined', '@default': 'function' } }],
        [/[a-zA-Z_]\w*/, { cases: { '@keywords': 'keyword', '@constants': 'constant', '@builtins': 'predefined', '@libs': 'library', '@default': 'identifier' } }],
        [/\d+(\.\d+)?/, 'number'],
        [/"/, 'string', '@dq'],
        [/'/, 'string', '@sq'],
        [/[()\[\]]/, '@brackets'],
        [/@symbols/, { cases: { '@operators': 'operator', '@default': '' } }],
      ],
      dq: [[/\\./, 'string.escape'], [/"/, 'string', '@pop'], [/[^"\\]+/, 'string']],
      sq: [[/\\./, 'string.escape'], [/'/, 'string', '@pop'], [/[^'\\]+/, 'string']],
    },
  });

  monaco.languages.setLanguageConfiguration('tuff', {
    comments: { lineComment: '#' },
    brackets: [['[', ']'], ['(', ')']],
    autoClosingPairs: [
      { open: '[', close: ']' }, { open: '(', close: ')' },
      { open: '"', close: '"', notIn: ['string'] }, { open: "'", close: "'", notIn: ['string'] },
    ],
    surroundingPairs: [{ open: '"', close: '"' }, { open: '(', close: ')' }, { open: '[', close: ']' }],
    indentationRules: {
      increaseIndentPattern: BLOCK_OPENER,
      decreaseIndentPattern: /^\s*(elif|else)\b/,
    },
    onEnterRules: [
      { beforeText: BLOCK_OPENER, action: { indentAction: monaco.languages.IndentAction.Indent } },
      { beforeText: /^\s+(return|break|continue)\b.*$/, action: { indentAction: monaco.languages.IndentAction.Outdent } },
    ],
    folding: { offSide: true },
  });

  monaco.languages.registerHoverProvider('tuff', {
    provideHover(model, position) {
      const word = model.getWordAtPosition(position);
      if (!word) return null;
      const before = model.getLineContent(position.lineNumber).slice(0, word.startColumn - 1);
      const lib = before.match(/(\w+)\.$/);
      const doc = (lib && window.TUFF_LIBS[lib[1]]?.[word.word])
        || (/\w:$/.test(before) && window.TUFF_METHOD_DOCS[word.word])
        || window.TUFF_DOCS[word.word];
      if (!doc) return null;
      return {
        range: new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn),
        contents: [{ value: '```tuff\n' + doc[0] + '\n```' }, { value: doc[1] }],
      };
    },
  });

  // No trigger characters here: the IDE opens the list itself after ':' or '.'
  // (see tuffWantsSuggest), which is reliable and never fires for block colons.
  monaco.languages.registerCompletionItemProvider('tuff', {
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position);
      const range = { startLineNumber: position.lineNumber, endLineNumber: position.lineNumber, startColumn: word.startColumn, endColumn: word.endColumn };
      const K = monaco.languages.CompletionItemKind;
      const R = monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet;
      const line = model.getLineContent(position.lineNumber);
      const before = line.slice(0, word.startColumn - 1);
      if (insideStringOrComment(line.slice(0, position.column - 1))) return { suggestions: [] };
      const libMatch = before.match(/(\w+)\.$/);
      if (libMatch) {
        const lib = window.TUFF_LIBS[libMatch[1]];
        if (!lib) return { suggestions: [] };
        return {
          suggestions: Object.entries(lib).map(([name, [sig, docText]]) => ({
            label: name, kind: K.Function, insertText: `${name}($0)`, insertTextRules: R, range, detail: sig, documentation: docText,
          })),
        };
      }
      if (/^\s*(import|mention)\s+$/.test(before)) {
        return { suggestions: Object.keys(window.TUFF_LIBS).map((l) => ({ label: l, kind: K.Module, insertText: l, range, documentation: window.TUFF_DOCS[l]?.[1] })) };
      }
      if (/\w:$/.test(before)) {
        const methods = new Set([...Object.keys(window.TUFF_METHOD_DOCS), 'clear', 'upper', 'lower', 'trim', 'has', 'add', 'pop']);
        return {
          suggestions: [...methods].map((m) => ({
            label: m, kind: K.Method, insertText: m, range,
            detail: window.TUFF_METHOD_DOCS[m]?.[0], documentation: window.TUFF_METHOD_DOCS[m]?.[1] || window.TUFF_DOCS[m]?.[1],
          })),
        };
      }
      const snippets = [
        { label: 'say', kind: K.Snippet, insertText: 'say "${1:text}"', insertTextRules: R, detail: 'Show a line', range },
        { label: 'input', kind: K.Snippet, insertText: '${1:answer} = input "${2:question} "', insertTextRules: R, detail: 'Ask a question', range },
        { label: 'func', kind: K.Snippet, insertText: 'func ${1:name}(${2}):\n    $0', insertTextRules: R, detail: 'Function', range },
        { label: 'if', kind: K.Snippet, insertText: 'if ${1:condition}:\n    $0', insertTextRules: R, detail: 'If block', range },
        { label: 'ifelse', kind: K.Snippet, insertText: 'if ${1:condition}:\n    $2\nelse:\n    $0', insertTextRules: R, detail: 'If / else', range },
        { label: 'while', kind: K.Snippet, insertText: 'while ${1:condition}:\n    $0', insertTextRules: R, detail: 'While loop', range },
        { label: 'for', kind: K.Snippet, insertText: 'for ${1:i} in range(${2:1}, ${3:10}):\n    $0', insertTextRules: R, detail: 'Count loop', range },
        { label: 'line', kind: K.Snippet, insertText: '${1:line} = say "${2:text}"\n${1:line}:rewrite "${3:new text}"', insertTextRules: R, detail: 'Say, then rewrite', range },
        { label: 'ask number', kind: K.Snippet, insertText: '${1:n} = num(input "${2:A number?} ")\nwhile ${1:n} is err:\n    say "Please type a number."\n    ${1:n} = num(input "${2:A number?} ")\n$0', insertTextRules: R, detail: 'Ask until they type a number (err)', range },
        { label: 'import anims', kind: K.Snippet, insertText: 'import anims\n', range, detail: 'Load the animations library' },
        { label: 'tap', kind: K.Snippet, insertText: 'mention tap\n\nres = tap.get("${1:https://api.github.com/users/octocat}")\nif res:ok:\n    info = res:json\n    say info:get("${2:name}")\nelse:\n    say "Error " + res:status\n', insertTextRules: R, range, detail: 'Get JSON from the web' },
        { label: 'tgui app', kind: K.Snippet, insertText: 'import tgui\n\napp = tgui.window("${1:My App}")\napp:heading "${2:Hello!}"\n\nfunc ${3:clicked}():\n    $0\n\napp:button("${4:Click me}", ${3:clicked})\n', insertTextRules: R, range, detail: 'A starter app window' },
        { label: 'atgui app', kind: K.Snippet, insertText: 'mention atgui\n\napp = atgui.window("${1:My App}", 900, 600)\napp:accent "${2:indigo}"\nside = app:sidebar(220)\nside:heading "${3:My App}"\npages = side:list(["Home", "Settings"])\npages:change opened\ntitle = app:heading "Home"\ncard = app:card\ncard:text "${4:Hello!}"\n\nfunc opened(name):\n    title:set name\n    $0\n', insertTextRules: R, range, detail: 'A modern app with a sidebar' },
      ];
      const kws = window.TUFF_KEYWORDS.map((k) => ({ label: k, kind: K.Keyword, insertText: k, range, documentation: window.TUFF_DOCS[k]?.[1] }));
      const fns = TUFF_BUILTINS.map((b) => ({ label: b, kind: K.Function, insertText: `${b}($0)`, insertTextRules: R, range, detail: window.TUFF_DOCS[b]?.[0], documentation: window.TUFF_DOCS[b]?.[1] }));
      const seen = new Set([...window.TUFF_KEYWORDS, ...TUFF_BUILTINS]);
      const ids = [];
      for (const f of userFuncs(model)) {
        seen.add(f.name);
        ids.push({ label: f.name, kind: K.Function, insertText: `${f.name}($0)`, insertTextRules: R, range, detail: `func ${f.name}(${f.params.join(', ')})` });
      }
      for (const m of model.getValue().matchAll(/[A-Za-z_]\w{1,}/g)) {
        if (!seen.has(m[0]) && m[0] !== word.word) {
          seen.add(m[0]);
          ids.push({ label: m[0], kind: K.Variable, insertText: m[0], range });
        }
      }
      return { suggestions: [...snippets, ...kws, ...fns, ...ids] };
    },
  });

  registerTuffNavigation(monaco);
  window.defineTuffTheme(monaco, accent);
};

// ---------------------------------------------------------------- understanding a file
// Every name used in code (not in strings or comments, and not a .member or :method),
// with its position. Used for go to definition, find uses and rename.
function tuffIdents(model) {
  const out = [];
  const lines = model.getLinesContent();
  lines.forEach((text, i) => {
    let quote = null;
    for (let c = 0; c < text.length;) {
      const ch = text[c];
      if (quote) {
        if (ch === '\\') c += 2;
        else { if (ch === quote) quote = null; c++; }
        continue;
      }
      if (ch === '"' || ch === "'") { quote = ch; c++; continue; }
      if (ch === '#') break;
      const m = /^[A-Za-z_]\w*/.exec(text.slice(c));
      if (m && !/\w/.test(text[c - 1] || '')) {
        const prev = text[c - 1];
        if (prev !== '.' && prev !== ':' && !window.TUFF_KEYWORDS.includes(m[0])) {
          out.push({ name: m[0], line: i + 1, start: c + 1, end: c + 1 + m[0].length });
        }
        c += m[0].length;
        continue;
      }
      c++;
    }
  });
  return out;
}

function userFuncs(model) {
  const out = [];
  model.getLinesContent().forEach((text, i) => {
    const m = text.match(/^(\s*)func\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?/);
    if (m) out.push({ name: m[2], line: i + 1, col: m[1].length + text.slice(m[1].length).indexOf(m[2]) + 1, indent: m[1].length, params: (m[3] || '').split(',').map((s) => s.trim()).filter(Boolean) });
  });
  return out;
}

// Last line of the indented block that starts on `line`.
function blockEnd(model, line) {
  const lines = model.getLinesContent();
  const indent = (s) => s.length - s.trimStart().length;
  const base = indent(lines[line - 1]);
  let end = line;
  for (let i = line; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    if (indent(lines[i]) <= base) break;
    end = i + 1;
  }
  return end;
}

function definitionOf(model, name, atLine) {
  const funcs = userFuncs(model);
  const fn = funcs.find((f) => f.name === name);
  if (fn) return { line: fn.line, start: fn.col, end: fn.col + name.length };
  // An input of the function we're inside.
  const inside = funcs.filter((f) => f.line <= atLine && blockEnd(model, f.line) >= atLine).pop();
  if (inside && inside.params.includes(name)) {
    const text = model.getLineContent(inside.line);
    const col = text.indexOf('(') + 1 + text.slice(text.indexOf('(')).search(new RegExp(`\\b${name}\\b`));
    return { line: inside.line, start: col, end: col + name.length };
  }
  const lines = model.getLinesContent();
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(new RegExp(`^(\\s*)(?:for\\s+)?(${name})\\s*(?:=(?!=)|[+\\-*/]=|\\s+in\\b)`));
    if (m) return { line: i + 1, start: m[0].indexOf(name) + 1, end: m[0].indexOf(name) + 1 + name.length };
  }
  return null;
}

// The call the cursor is inside: name, how it's called and which input it's on.
function callAt(textBefore) {
  let depth = 0;
  let commas = 0;
  let quote = null;
  for (let i = textBefore.length - 1; i >= 0; i--) {
    const c = textBefore[i];
    if (quote) { if (c === quote) quote = null; continue; }
    if (c === '"' || c === "'") { quote = c; continue; }
    if (c === ')' || c === ']') depth++;
    else if (c === '[') depth--;
    else if (c === '(') {
      if (depth === 0) {
        const m = textBefore.slice(0, i).match(/(?:([A-Za-z_]\w*)\.|:)?([A-Za-z_]\w*)\s*$/);
        if (!m) return null;
        const how = m[1] ? 'lib' : /:[A-Za-z_]\w*\s*$/.test(textBefore.slice(0, i)) ? 'method' : 'call';
        return { name: m[2], lib: m[1], how, active: commas };
      }
      depth--;
    } else if (c === ',' && depth === 0) commas++;
  }
  return null;
}

function registerTuffNavigation(monaco) {
  const L = monaco.languages;
  const wordAt = (model, position) => {
    const w = model.getWordAtPosition(position);
    if (!w) return null;
    const hit = tuffIdents(model).find((x) => x.line === position.lineNumber && x.start === w.startColumn);
    return hit ? w : null;
  };
  const range = (line, start, end) => new monaco.Range(line, start, line, end);

  L.registerDefinitionProvider('tuff', {
    provideDefinition(model, position) {
      const w = wordAt(model, position);
      const d = w && definitionOf(model, w.word, position.lineNumber);
      return d ? { uri: model.uri, range: range(d.line, d.start, d.end) } : null;
    },
  });

  L.registerReferenceProvider('tuff', {
    provideReferences(model, position) {
      const w = wordAt(model, position);
      if (!w) return [];
      return tuffIdents(model).filter((x) => x.name === w.word).map((x) => ({ uri: model.uri, range: range(x.line, x.start, x.end) }));
    },
  });

  L.registerRenameProvider('tuff', {
    resolveRenameLocation(model, position) {
      const w = wordAt(model, position);
      if (!w) return { rejectReason: 'Put the cursor on a name you made (a variable or a function) to rename it.', range: undefined, text: '' };
      if (TUFF_BUILTINS.includes(w.word) || window.TUFF_LIBS[w.word]) return { rejectReason: `'${w.word}' is part of Tuff, so it can't be renamed.`, range: undefined, text: '' };
      return { range: range(position.lineNumber, w.startColumn, w.endColumn), text: w.word };
    },
    provideRenameEdits(model, position, newName) {
      const w = wordAt(model, position);
      if (!w) return null;
      if (!/^[A-Za-z_]\w*$/.test(newName) || window.TUFF_KEYWORDS.includes(newName)) return { edits: [], rejectReason: `'${newName}' can't be a name. Use letters, numbers and _, and not a Tuff word.` };
      const edits = tuffIdents(model).filter((x) => x.name === w.word).map((x) => ({ resource: model.uri, versionId: model.getVersionId(), textEdit: { range: range(x.line, x.start, x.end), text: newName } }));
      return { edits };
    },
  });

  L.registerDocumentSymbolProvider('tuff', {
    displayName: 'Tuff',
    provideDocumentSymbols(model) {
      const K = L.SymbolKind;
      const symbols = [];
      const seen = new Set();
      model.getLinesContent().forEach((text, i) => {
        const line = i + 1;
        let m;
        if ((m = text.match(/^\s*func\s+([A-Za-z_]\w*)\s*(\([^)]*\))?/))) {
          const end = blockEnd(model, line);
          symbols.push({ name: m[1], detail: m[2] || '()', kind: K.Function, range: new monaco.Range(line, 1, end, model.getLineMaxColumn(end)), selectionRange: range(line, 1, model.getLineMaxColumn(line)), tags: [] });
        } else if ((m = text.match(/^([A-Za-z_]\w*)\s*=\s*(m?tgui|atgui)\.window/))) {
          symbols.push({ name: m[1], detail: `${m[2]} window`, kind: K.Class, range: range(line, 1, model.getLineMaxColumn(line)), selectionRange: range(line, 1, m[1].length + 1), tags: [] });
          seen.add(m[1]);
        } else if ((m = text.match(/^([A-Za-z_]\w*)\s*=\s*[A-Za-z_]\w*:([a-z]+)/))) {
          if (seen.has(m[1])) return;
          seen.add(m[1]);
          symbols.push({ name: m[1], detail: m[2], kind: K.Field, range: range(line, 1, model.getLineMaxColumn(line)), selectionRange: range(line, 1, m[1].length + 1), tags: [] });
        } else if ((m = text.match(/^([A-Za-z_]\w*)\s*=(?!=)/))) {
          if (seen.has(m[1])) return;
          seen.add(m[1]);
          symbols.push({ name: m[1], detail: 'variable', kind: K.Variable, range: range(line, 1, model.getLineMaxColumn(line)), selectionRange: range(line, 1, m[1].length + 1), tags: [] });
        }
      });
      return symbols;
    },
  });

  L.registerSignatureHelpProvider('tuff', {
    signatureHelpTriggerCharacters: ['(', ','],
    signatureHelpRetriggerCharacters: [','],
    provideSignatureHelp(model, position) {
      const before = model.getLineContent(position.lineNumber).slice(0, position.column - 1);
      if (insideStringOrComment(before)) return null;
      const call = callAt(before);
      if (!call) return null;
      let sig = null;
      let doc = '';
      if (call.how === 'lib') [sig, doc] = window.TUFF_LIBS[call.lib]?.[call.name] || [];
      else if (call.how === 'method') [sig, doc] = window.TUFF_METHOD_DOCS[call.name] || [];
      else {
        const f = userFuncs(model).find((x) => x.name === call.name);
        if (f) { sig = `${f.name}(${f.params.join(', ')})`; doc = 'A function in this file.'; }
        else [sig, doc] = window.TUFF_DOCS[call.name] || [];
      }
      const inner = sig && sig.match(/\(([^)]*)\)/);
      if (!inner) return null;
      const params = inner[1].split(',').map((s) => s.trim()).filter(Boolean);
      return {
        value: { signatures: [{ label: sig, documentation: doc, parameters: params.map((p) => ({ label: p })) }], activeSignature: 0, activeParameter: Math.min(call.active, Math.max(0, params.length - 1)) },
        dispose() {},
      };
    },
  });

  // Colour swatches (with a picker) on "#rrggbb" text, e.g. app:accent "#ff8800".
  L.registerColorProvider('tuff', {
    provideDocumentColors(model) {
      const out = [];
      model.getLinesContent().forEach((text, i) => {
        for (const m of text.matchAll(/(["'])#([0-9a-fA-F]{6})\1/g)) {
          const hex = m[2];
          out.push({
            color: { red: parseInt(hex.slice(0, 2), 16) / 255, green: parseInt(hex.slice(2, 4), 16) / 255, blue: parseInt(hex.slice(4, 6), 16) / 255, alpha: 1 },
            range: range(i + 1, m.index + 2, m.index + 9),
          });
        }
      });
      return out;
    },
    provideColorPresentations(model, info) {
      const h = (v) => Math.round(v * 255).toString(16).padStart(2, '0');
      return [{ label: `#${h(info.color.red)}${h(info.color.green)}${h(info.color.blue)}` }];
    },
  });

  // Hovering one of your own functions shows how to call it and the note Auto Code Sort wrote.
  L.registerHoverProvider('tuff', {
    provideHover(model, position) {
      const w = wordAt(model, position);
      if (!w) return null;
      const f = userFuncs(model).find((x) => x.name === w.word);
      if (!f) return null;
      const above = f.line > 1 ? model.getLineContent(f.line - 1).match(/^\s*#\s*↳\s*(.*)$/) : null;
      return {
        range: range(position.lineNumber, w.startColumn, w.endColumn),
        contents: [{ value: '```tuff\nfunc ' + f.name + '(' + f.params.join(', ') + ')\n```' }, { value: above ? above[1] : `Defined on line ${f.line}. Ctrl+click or F12 jumps there.` }],
      };
    },
  });
}

window.defineTuffTheme = function defineTuffTheme(monaco, accent) {
  const a = accent.replace('#', '');
  monaco.editor.defineTheme('tuff-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '7a7e85', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'cf8e6d' },
      { token: 'constant', foreground: 'cf8e6d' },
      { token: 'string', foreground: '6aab73' },
      { token: 'string.escape', foreground: 'cf8e6d' },
      { token: 'number', foreground: '2aacb8' },
      { token: 'function', foreground: '56a8f5' },
      { token: 'function.decl', foreground: '56a8f5' },
      { token: 'method', foreground: '56a8f5', fontStyle: 'italic' },
      { token: 'predefined', foreground: '8888c6' },
      { token: 'library', foreground: 'c77dbb' },
      { token: 'identifier', foreground: 'bcbec4' },
      { token: 'operator', foreground: 'bcbec4' },
      { token: 'delimiter', foreground: 'bcbec4' },
    ],
    colors: {
      'editor.background': '#1e1f22',
      'editor.foreground': '#bcbec4',
      'editor.lineHighlightBackground': '#26282e',
      'editor.lineHighlightBorder': '#00000000',
      'editorLineNumber.foreground': '#4b5059',
      'editorLineNumber.activeForeground': '#a1a3ab',
      'editor.selectionBackground': '#214283',
      'editor.inactiveSelectionBackground': '#2a3a5c',
      'editorCursor.foreground': '#ced0d6',
      'editorIndentGuide.background1': '#2f3136',
      'editorIndentGuide.activeBackground1': '#4b5059',
      'editorGutter.background': '#1e1f22',
      'editorWidget.background': '#2b2d30',
      'editorWidget.border': '#43454a',
      'editorHoverWidget.background': '#2b2d30',
      'editorHoverWidget.border': '#43454a',
      'editorSuggestWidget.background': '#2b2d30',
      'editorSuggestWidget.border': '#43454a',
      'editorSuggestWidget.selectedBackground': '#' + a + '66',
      'editorBracketMatch.background': '#3b514d',
      'editorBracketMatch.border': '#00000000',
      'editorError.foreground': '#f75464',
      'scrollbarSlider.background': '#ffffff1a',
      'scrollbarSlider.hoverBackground': '#ffffff2e',
      'focusBorder': '#' + a,
    },
  });
};
