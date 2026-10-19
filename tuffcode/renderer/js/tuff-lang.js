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
  text: ['app:text "Text"', 'Normal text. Change it later with :set.'],
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
  title: ['app:title "Title"', 'Changes the window title, even while running.'],
  icon: ['app:icon "icon.png"', 'Changes the window icon (.png, .gif or .ico in your project folder).'],
  size: ['app:size(width, height)', 'Resizes the window.'],
  theme: ['app:theme "light"', 'Switches between "dark" and "light".'],
  accent: ['app:accent "purple"', 'Changes the highlight color: blue, purple, pink, red, orange, yellow, green, teal or a hex code.'],
  every: ['app:every(seconds, tick)', 'Runs a function again and again, like a clock.'],
  after: ['app:after(seconds, done)', 'Runs a function once after a delay.'],
  alert: ['app:alert "Message"', 'Pops up a message with an OK button.'],
  confirm: ['app:confirm "Are you sure?"', 'Pops up Yes/No and gives back true or false.'],
  ask: ['app:ask "Question?"', 'Pops up a text box and gives back what was typed.'],
  close: ['app:close', 'Closes the window.'],
  set: ['thing:set value', 'Changes the text or value.'],
  value: ['thing:value', 'Gives back the current text or value.'],
  change: ['thing:change fn', 'Runs fn when the value changes. fn gets the new value.'],
  enter: ['box:enter fn', 'Runs fn when Enter is pressed in a text box.'],
  click: ['button:click fn', 'Changes which function the button runs.'],
  style: ['button:style "danger"', 'Changes the button style.'],
  color: ['label:color "red"', 'Changes the text color.'],
  disable: ['button:disable', 'Greys out a button so it can\'t be clicked.'],
  enable: ['button:enable', 'Makes a disabled button clickable again.'],
  hide: ['thing:hide', 'Hides it.'],
  show: ['thing:show', 'Shows it again after :hide.'],
  remove: ['thing:remove', 'Removes it for good.'],
  rewrite: ['line:rewrite value', 'Replaces the text of a line you already said.'],
  append: ['line:append value', 'Adds text to the end of a line you already said.'],
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
    bar: ['anims.bar(text, seconds)', 'A progress bar that fills from 0% to 100%.'],
    type: ['anims.type(text, speed)', 'Types text out one letter at a time.'],
    countdown: ['anims.countdown(start, then)', 'Counts down on one line, then shows the `then` text.'],
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
  then: ['then', 'Starts a block, same as `:`.'],
  while: ['while condition:', 'Repeats the block as long as the condition stays true.'],
  for: ['for item in list:', 'Runs the block once for every item in a list, text or range().'],
  is: ['a is b', 'True when both sides are equal. Use `is not` for the opposite.'],
  print: ['print(a, b, ...)', 'Like `say`, but takes several values separated by commas.'],
  number: ['number(text)', 'Turns text like "42" into the number 42.'],
  text: ['text(value)', 'Turns any value into text.'],
  len: ['len(value)', 'How many characters are in some text, or items in a list.'],
  round: ['round(number, digits)', 'Rounds a number. digits is optional.'],
  random: ['random(low, high)', 'A random whole number from low to high, both included.'],
  wait: ['wait(seconds)', 'Pauses the program. Great with :rewrite for animations.'],
  range: ['range(start, end)', 'A list of numbers from start to end, both included. range(5) is 1 to 5.'],
  flush: ['flush', 'Wipes everything in the Run window. Same as clear(all).'],
  clear: ['clear(lines)', 'Removes the last few lines from the Run window, like clear(2). clear(all) removes everything.'],
  all: ['all', 'Means every line, as in clear(all).'],
  import: ['import library', 'Loads a library of extra functions, like: import anims'],
  anims: ['import anims', 'Ready-made animations: loading, bar, type, countdown.'],
  tgui: ['import tgui', 'Tuff GUI: make real app windows with buttons, text boxes, toggles and more.'],
  mtgui: ['mention mtgui', 'Modern Tuff GUI: like tgui with gradients, gloss, shine and glow.'],
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
  clear: ['line:clear', 'Empties a line you already said.'],
};

const TUFF_BUILTINS = ['print', 'number', 'text', 'len', 'round', 'random', 'wait', 'range', 'clear', 'sqrt', 'abs', 'floor', 'ceil', 'min', 'max', 'sum', 'average'];

window.registerTuff = function registerTuff(monaco, accent) {
  monaco.languages.register({ id: 'tuff', extensions: ['.tuf'], aliases: ['Tuff', 'tuff'] });

  monaco.languages.setMonarchTokensProvider('tuff', {
    keywords: window.TUFF_KEYWORDS.filter((k) => !['true', 'false', 'nil'].includes(k)),
    constants: ['true', 'false', 'nil', 'all', 'pi'],
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
      increaseIndentPattern: /^\s*(if|elif|else|while|for|func)\b.*(:|\bthen)\s*(#.*)?$/,
      decreaseIndentPattern: /^\s*(elif|else)\b/,
    },
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

  monaco.languages.registerCompletionItemProvider('tuff', {
    triggerCharacters: [':', '.'],
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position);
      const range = { startLineNumber: position.lineNumber, endLineNumber: position.lineNumber, startColumn: word.startColumn, endColumn: word.endColumn };
      const K = monaco.languages.CompletionItemKind;
      const R = monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet;
      const before = model.getLineContent(position.lineNumber).slice(0, word.startColumn - 1);
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
        { label: 'import anims', kind: K.Snippet, insertText: 'import anims\n', range, detail: 'Load the animations library' },
        { label: 'tgui app', kind: K.Snippet, insertText: 'import tgui\n\napp = tgui.window("${1:My App}")\napp:heading "${2:Hello!}"\n\nfunc ${3:clicked}():\n    $0\n\napp:button("${4:Click me}", ${3:clicked})\n', insertTextRules: R, range, detail: 'A starter app window' },
      ];
      const kws = window.TUFF_KEYWORDS.map((k) => ({ label: k, kind: K.Keyword, insertText: k, range, documentation: window.TUFF_DOCS[k]?.[1] }));
      const fns = TUFF_BUILTINS.map((b) => ({ label: b, kind: K.Function, insertText: `${b}($0)`, insertTextRules: R, range, detail: window.TUFF_DOCS[b]?.[0], documentation: window.TUFF_DOCS[b]?.[1] }));
      const seen = new Set([...window.TUFF_KEYWORDS, ...TUFF_BUILTINS]);
      const ids = [];
      for (const m of model.getValue().matchAll(/[A-Za-z_]\w{1,}/g)) {
        if (!seen.has(m[0]) && m[0] !== word.word) {
          seen.add(m[0]);
          ids.push({ label: m[0], kind: K.Variable, insertText: m[0], range });
        }
      }
      return { suggestions: [...snippets, ...kws, ...fns, ...ids] };
    },
  });

  window.defineTuffTheme(monaco, accent);
};

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
