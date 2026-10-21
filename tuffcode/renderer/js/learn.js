(() => {
  const api = window.tuff;
  const $ = (s) => document.querySelector(s);
  const lines = (out) => out.split('\n').map((l) => l.trim()).filter(Boolean);
  // The code without its # comments (a # inside quotes stays), so a starter's instructions never pass a check.
  const withoutComments = (src) => src.split('\n').map((line) => {
    let quote = null;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (quote) {
        if (ch === '\\') i++;
        else if (ch === quote) quote = null;
      } else if (ch === '"' || ch === "'") quote = ch;
      else if (ch === '#') return line.slice(0, i).trimEnd();
    }
    return line;
  }).join('\n');

  const BASICS = [
    {
      id: 'say-hello',
      title: 'Say hello',
      body: `<p>A Tuff program is a list of instructions that run from top to bottom.</p>
             <p><code>say</code> shows a line in the Run window. Text goes inside quotes.</p>`,
      example: 'say "Hello, world!"\nsay "Tuff is running"',
      task: 'Change the text so Tuff says hello to <b>you</b>, like <code>say "Hello, Sam!"</code>. Then press <kbd>Shift+F10</kbd>.',
      starter: '# Lesson 1: Say hello\n# Change the text so Tuff says hello to YOU, then press Shift+F10.\n\nsay "Hello, world!"\n',
      check: (src, out) => {
        const hello = lines(out).find((l) => /^h(ello|i|ey)\b/i.test(l) && !/^hello,? world!?$/i.test(l));
        return hello ? true : 'Make a line that starts with "Hello" and has your name in it.';
      },
    },
    {
      id: 'variables',
      title: 'Variables',
      body: `<p>A <b>variable</b> is a name that holds a value. Make one with <code>=</code>.</p>
             <p>Join things together with <code>+</code>. Numbers join into text automatically.</p>`,
      example: 'name = "Sam"\nage = 14\nsay name + " is " + age + " years old"',
      task: 'Make a variable called <code>food</code> holding your favorite food, then say it in a sentence.',
      starter: '# Lesson 2: Variables\n# Make a variable called food with your favorite food,\n# then say it in a sentence.\n\nname = "Sam"\nsay "My name is " + name\n\n',
      check: (src, out) => {
        if (!/^\s*food\s*=/m.test(src)) return 'Create the variable first, like: food = "pizza"';
        if (!/(say|print)\b.*\bfood\b/.test(src)) return 'Now use food in a say line, like: say "I love " + food';
        return lines(out).length ? true : 'Your program ran but didn\'t say anything.';
      },
    },
    {
      id: 'math',
      title: 'Numbers and math',
      body: `<p><code>+ - * /</code> work like a calculator. <code>^</code> is power (<code>2 ^ 3</code> is 8) and <code>%</code> gives the remainder.</p>
             <p>Handy helpers: <code>sqrt(81)</code>, <code>abs(-5)</code>, <code>round(3.14159, 2)</code>, <code>min</code>, <code>max</code>, <code>sum</code>, <code>average</code> and <code>pi</code>.</p>
             <p><code>+=</code> adds to a variable that already exists.</p>`,
      example: 'coins = 10\ncoins += 5\nsay "Coins: " + coins\nsay 7 * 6\nsay 2 ^ 10\nsay sqrt(144)\nsay average(80, 90, 100)',
      task: 'Work out how many seconds are in one day (24 hours × 60 minutes × 60 seconds) and say the answer.',
      starter: '# Lesson 3: Numbers and math\n# How many seconds are in one day? Use * to work it out, then say it.\n\n',
      check: (src, out) => (/\b86400\b/.test(out) ? true : 'Not quite. Try: say 24 * 60 * 60'),
    },
    {
      id: 'input',
      title: 'Asking questions',
      body: `<p><code>input</code> asks a question. When it runs, click the Run window, type your answer and press <kbd>Enter</kbd>.</p>
             <p>Answers are always text. Use <code>number(...)</code> to turn an answer into a number. (If someone types a word instead, you get <code>err</code>. Lesson 10 shows how to check for it.)</p>`,
      example: 'name = input "What\'s your name? "\nsay "Nice to meet you, " + name + "!"\n\nage = number(input "How old are you? ")\nsay "Next year you\'ll be " + (age + 1)',
      task: 'Ask for someone\'s favorite food, then say something about their answer.',
      starter: '# Lesson 4: Asking questions\n# Ask for a favorite food with input, then say something about it.\n\n',
      check: (src, out) => {
        if (!/\binput\b/.test(src)) return 'Use input to ask the question, like: food = input "Favorite food? "';
        return /(say|print)\b/.test(src) ? true : 'Now say something using their answer.';
      },
    },
    {
      id: 'decisions',
      title: 'Making decisions',
      body: `<p><code>if</code> runs a block only when something is true. The lines inside are indented 4 spaces.</p>
             <p>Compare with <code>is</code>, <code>is not</code>, <code>&gt;</code> and <code>&lt;</code>. Start a block with <code>:</code> or <code>then</code>; both work.</p>`,
      example: 'answer = input "Do you like pizza? "\nif answer is "yes":\n    say "Same!"\nelif answer is "no" then\n    say "More for me."\nelse:\n    say "Hmm, okay."',
      task: 'Ask for a password. If it\'s <code>tuff123</code>, say "Access granted". Otherwise say "Access denied".',
      starter: '# Lesson 5: Making decisions\n# Ask for a password. If it is "tuff123" say "Access granted",\n# otherwise say "Access denied".\n\n',
      check: (src, out) => {
        if (!/\bif\b/.test(src) || !/\belse\b/.test(src)) return 'You\'ll need both an if and an else.';
        return /access (granted|denied)/i.test(out) ? true : 'Say exactly "Access granted" or "Access denied".';
      },
    },
    {
      id: 'loops',
      title: 'Loops',
      body: `<p><code>for</code> repeats a block once for each item. <code>range(1, 5)</code> counts from 1 to 5, both ends included.</p>
             <p><code>while</code> keeps repeating as long as something stays true.</p>`,
      example: 'for lap in range(1, 3):\n    say "Lap " + lap\n\nfuel = 3\nwhile fuel > 0:\n    say "Fuel left: " + fuel\n    fuel -= 1',
      task: 'Count from 1 to 10, saying each number on its own line.',
      starter: '# Lesson 6: Loops\n# Count from 1 to 10 using a loop.\n\n',
      check: (src, out) => {
        if (!/\b(for|while)\b/.test(src)) return 'Use a loop instead of writing 10 say lines.';
        const missing = [...Array(10)].map((_, i) => i + 1).filter((n) => !new RegExp(`\\b${n}\\b`).test(out));
        return missing.length ? `Missing: ${missing.join(', ')}` : true;
      },
    },
    {
      id: 'functions',
      title: 'Functions',
      body: `<p>A <b>function</b> is a reusable block with a name. Inputs go inside <code>( )</code>.</p>
             <p>A function gives back its last value automatically, or whatever you <code>return</code>.</p>`,
      example: 'func greet(name):\n    say "Hey " + name + "!"\n\ngreet("Sam")\n\nfunc double(n):\n    n * 2\n\nsay double(21)',
      task: 'Write a function <code>square(n)</code> that gives back <code>n * n</code>, then say <code>square(12)</code>.',
      starter: '# Lesson 7: Functions\n# Write func square(n) that gives back n * n,\n# then say square(12).\n\n',
      check: (src, out) => {
        if (!/func\s+square\s*\(/.test(src)) return 'Start with: func square(n):';
        return /\b144\b/.test(out) ? true : 'square(12) should come out as 144.';
      },
    },
    {
      id: 'live-lines',
      title: 'Live lines',
      body: `<p>Write <code>line = say ...</code> and Tuff remembers that line. Later, <code>line:rewrite</code> changes it in place.</p>
             <p>Pair it with <code>wait(seconds)</code> for countdowns, loading bars and animations.</p>`,
      example: 'bar = say "Loading"\nfor i in range(1, 5):\n    wait(0.4)\n    bar:rewrite "Loading" + "." * i\nbar:rewrite say "Done!"',
      task: 'Make a countdown from 3 to 1 on <b>one</b> line (wait a second between numbers), then rewrite it to say "Liftoff!".',
      starter: '# Lesson 8: Live lines\n# Count down 3, 2, 1 on ONE line using :rewrite and wait(1),\n# then rewrite it to "Liftoff!".\n\n',
      check: (src, out) => {
        if (!/:rewrite\b/.test(src)) return 'Use line:rewrite so the countdown stays on one line.';
        return /liftoff/i.test(out) ? true : 'End by rewriting the line to "Liftoff!".';
      },
    },
    {
      id: 'anims-and-clear',
      title: 'Animations and clearing',
      body: `<p>A <b>library</b> adds extra powers. Load one with <code>import</code> at the top of your file.</p>
             <p>The <code>anims</code> library has ready-made animations: <code>anims.loading()</code>, <code>anims.bar()</code>, <code>anims.type()</code> and <code>anims.countdown()</code>.</p>
             <p><code>flush</code> or <code>clear(all)</code> wipes the Run window. <code>clear(2)</code> removes just the last 2 lines.</p>`,
      example: 'import anims\n\nanims.loading("Downloading", 2)\nanims.bar("Installing", 2)\nanims.type("Welcome to Tuff!")\nwait(1)\n\nflush\nsay "Fresh start!"',
      task: 'Import <code>anims</code>, show a loading animation, then <code>flush</code> the screen and say something new.',
      starter: '# Lesson 9: Animations and clearing\n# Import anims, show anims.loading(), then flush and say something new.\n\n',
      check: (src, out) => {
        if (!/^\s*import\s+anims\b/m.test(src)) return 'Start with: import anims';
        if (!/anims\.loading\s*\(/.test(src)) return 'Show a loader with anims.loading()';
        if (!/^\s*(flush|clear\s*\()/m.test(src)) return 'Wipe the screen with flush (or clear(all)).';
        return lines(out).length ? true : 'Say something after you flush.';
      },
    },
    {
      id: 'checking-answers',
      title: 'Checking answers',
      body: `<p>People type all sorts of things. When an answer isn't a number, <code>number(...)</code> (or the short <code>num(...)</code>) gives back <code>err</code> instead of a number, so you can check first:</p>
             <p><code>if num(answer) is err:</code> means "if that wasn't a number". If you use an <code>err</code> in maths anyway, the program stops and tells you why.</p>
             <p><code>int(...)</code> gives a whole number (<code>int("3.7")</code> is 3), and <code>str(...)</code> turns anything into text, just like <code>text(...)</code>.</p>`,
      example: 'bet = input "How many coins do you bet? "\nif num(bet) is err:\n    say "That isn\'t a number!"\nelse:\n    coins = int(bet)\n    say "You bet " + str(coins) + " coins"',
      task: 'Ask for a number. If it isn\'t one, say so. If it is, say double it.',
      starter: '# Lesson 10: Checking answers\n# Ask for a number, check it with "is err", then say double it.\n\n',
      check: (src, out) => {
        if (!/\binput\b/.test(src)) return 'Ask with input first, like: n = input "A number? "';
        if (!/\bis\s+(not\s+)?err\b/.test(src)) return 'Check the answer with: if num(n) is err:';
        // input gives text, and text is never err: what's checked has to go through num(), number() or int() first,
        // right there (num(n) is err) or in a variable made with one (n = num(input "?") ... n is err).
        const madeWith = (name) => new RegExp(`^\\s*${name}\\s*=\\s*(num|number|int)\\s*\\(`, 'm').test(src);
        const converted = [...src.matchAll(/(\b(?:num|number|int)\s*\([^\n]*\)|\b\w+)\s+is\s+(?:not\s+)?err\b/g)]
          .some(([, what]) => /^(num|number|int)\s*\(/.test(what) || madeWith(what));
        if (!converted) return 'input gives text, and text is never err. Turn it into a number as you check: if num(n) is err:';
        return lines(out).length ? true : 'Say something with the answer.';
      },
    },
  ];

  const TGUI = [
    {
      id: 'tgui-window',
      title: 'Your first window',
      body: `<p><code>tgui</code> (Tuff GUI) makes real desktop apps with windows and buttons.</p>
             <p>Make a window with <code>tgui.window("Title")</code>, then add things to it. They stack from top to bottom. The app keeps running until you close its window.</p>`,
      example: 'import tgui\n\napp = tgui.window("My First App")\napp:heading "Hello!"\napp:text "This is a real app made with Tuff."\napp:small "Close the window to finish."',
      task: 'Make a window with your name in the title, a heading and some text. Run it, then close the window.',
      starter: '# Section 2, Lesson 1: Your first window\n# Make a window with a heading and some text, run it, then close the window.\n\nimport tgui\n\n',
      check: (src) => {
        if (!/^\s*(import|mention)\s+tgui\b/m.test(src)) return 'Start with: import tgui';
        if (!/tgui\.window\s*\(/.test(src)) return 'Make a window with: app = tgui.window("My App")';
        return /:heading\b/.test(src) ? true : 'Add a heading, like: app:heading "Hello!"';
      },
    },
    {
      id: 'tgui-buttons',
      title: 'Buttons',
      body: `<p><code>app:button("Text", clicked)</code> adds a button. When it's clicked, Tuff runs the function you named. Write the name with no brackets.</p>
             <p>Button styles: <code>"primary"</code>, <code>"secondary"</code>, <code>"outline"</code>, <code>"ghost"</code>, <code>"success"</code> and <code>"danger"</code>. Change any text later with <code>:set</code>.</p>`,
      example: 'import tgui\n\napp = tgui.window("Clicker")\ncount = 0\nlabel = app:heading "Clicks: 0"\n\nfunc clicked():\n    count += 1\n    label:set "Clicks: " + count\n\nfunc reset():\n    count = 0\n    label:set "Clicks: 0"\n\nbuttons = app:row\nbuttons:button("Click me", clicked)\nbuttons:button("Reset", reset, "outline")',
      task: 'Make a button that changes some text when you click it.',
      starter: '# Section 2, Lesson 2: Buttons\n# Make a button that changes some text when you click it.\n\nimport tgui\n\napp = tgui.window("Buttons")\n\n',
      check: (src) => {
        if (!/:button\s*\(/.test(src)) return 'Add a button, like: app:button("Click me", clicked)';
        if (!/^\s*func\s+\w+/m.test(src)) return 'Write the function the button runs, like: func clicked():';
        return /:set\b/.test(src) ? true : 'Inside your function, change some text with :set';
      },
    },
    {
      id: 'tgui-inputs',
      title: 'Text boxes',
      body: `<p><code>app:input "Hint text"</code> adds a box people can type in. Read what they typed with <code>:value</code>.</p>
             <p><code>box:enter greet</code> runs a function when they press <kbd>Enter</kbd>. <code>box:change</code> runs one on every key.</p>`,
      example: 'import tgui\n\napp = tgui.window("Greeter")\nname = app:input "Your name"\nhello = app:text ""\n\nfunc greet():\n    hello:set "Hey " + name:value + "!"\n\napp:button("Say hi", greet)\nname:enter greet',
      task: 'Ask for a name with <code>app:input</code> and greet the person when they click a button.',
      starter: '# Section 2, Lesson 3: Text boxes\n# Ask for a name with app:input and greet them when a button is clicked.\n\nimport tgui\n\napp = tgui.window("Greeter")\n\n',
      check: (src) => {
        if (!/:input\b/.test(src)) return 'Add a text box with app:input "Your name"';
        return /:value\b/.test(src) ? true : 'Read what was typed with :value';
      },
    },
    {
      id: 'tgui-layout',
      title: 'Rows, cards and spacing',
      body: `<p>Things stack top to bottom. Put them side by side with <code>row = app:row</code>, then add to the row.</p>
             <p>Group things in a rounded panel with <code>app:card</code>. Add a line with <code>app:divider</code> and a gap with <code>app:space 20</code>. Pop up a message with <code>app:alert</code>.</p>`,
      example: 'import tgui\n\napp = tgui.window("Profile")\n\ncard = app:card\ncard:heading "Sam"\ncard:small "Tuff developer · 3 apps"\n\nfunc follow():\n    app:alert "You followed Sam!"\n\napp:divider\nrow = app:row\nrow:button("Follow", follow)\nrow:button("Message", follow, "outline")',
      task: 'Put something inside a card, and two buttons side by side in a row.',
      starter: '# Section 2, Lesson 4: Rows, cards and spacing\n# Put something in a card, and two buttons side by side in a row.\n\nimport tgui\n\napp = tgui.window("Layout")\n\n',
      check: (src) => {
        if (!/:card\b/.test(src)) return 'Make a card with: card = app:card';
        return /:row\b/.test(src) ? true : 'Make a row with: row = app:row';
      },
    },
    {
      id: 'tgui-controls',
      title: 'Toggles, sliders and progress',
      body: `<p><code>app:toggle("Label", true)</code> is an on/off switch. <code>app:slider(0, 100, 30)</code> picks a number. <code>app:progress(30)</code> shows a bar.</p>
             <p>Use <code>:change</code> to run a function whenever one changes. It gets the new value.</p>`,
      example: 'import tgui\n\napp = tgui.window("Controls")\ndark = app:toggle("Dark mode", true)\nvolume = app:slider(0, 100, 30)\nbar = app:progress(30)\n\nfunc moved(value):\n    bar:set value\n\nfunc flip(on):\n    if on:\n        app:theme "dark"\n    else:\n        app:theme "light"\n\nvolume:change moved\ndark:change flip',
      task: 'Make a slider that moves a progress bar.',
      starter: '# Section 2, Lesson 5: Toggles, sliders and progress\n# Make a slider that moves a progress bar.\n\nimport tgui\n\napp = tgui.window("Controls")\n\n',
      check: (src) => {
        if (!/:slider\b/.test(src) || !/:progress\b/.test(src)) return 'You need both app:slider and app:progress';
        return /:change\b/.test(src) ? true : 'Connect them with slider:change';
      },
    },
    {
      id: 'tgui-window-style',
      title: 'Title, icon and theme',
      body: `<p>Change how your app looks any time, even while it's running:</p>
             <p><code>app:title "New title"</code> · <code>app:icon "logo.png"</code> (a .png in your project folder) · <code>app:theme "light"</code> · <code>app:accent "purple"</code> · <code>app:size(500, 400)</code></p>
             <p><code>app:every(1, tick)</code> runs a function every second. It's great for clocks, timers and animations.</p>`,
      example: 'import tgui\n\napp = tgui.window("Timer")\napp:accent "purple"\nseconds = 0\nlabel = app:heading "0s"\n\nfunc tick():\n    seconds += 1\n    label:set seconds + "s"\n    app:title "Timer · " + seconds + "s"\n\nfunc grow():\n    app:size(520, 420)\n\napp:every(1, tick)\napp:button("Make bigger", grow, "outline")',
      task: 'Make the window title change while the app is running, with <code>app:every</code> or a button.',
      starter: '# Section 2, Lesson 6: Title, icon and theme\n# Make the window title change while the app is running.\n\nimport tgui\n\napp = tgui.window("Live title")\n\n',
      check: (src) => {
        if (!/:title\b/.test(src)) return 'Change the title with app:title "..."';
        return /:every\b|:button\b|:after\b/.test(src) ? true : 'Change it from app:every or a button so it happens while running.';
      },
    },
    {
      id: 'tgui-motion',
      title: 'Clocks and animation',
      body: `<p><code>app:clock</code> adds a ticking clock. Make it digital with <code>app:clock "digital"</code>. Set its time with <code>clock:set(10, 30)</code>.</p>
             <p>Anything that moves has <code>:speed</code>: <code>2</code> is twice as fast, <code>0.5</code> is half speed. Try it on clocks, switches, spinners and progress bars.</p>
             <p>Tip: hover a UI line in your code and click the gear in the margin to change things without typing.</p>`,
      example: 'import tgui\n\napp = tgui.window("Clocks")\nclock = app:clock\nclock:set(10, 30)\nclock:speed 60\n\nswitch = app:toggle("Slow switch", false)\nswitch:speed 0.3\n\napp:spinner("Thinking...")\nsize = app:dropdown(["Small", "Medium", "Large"])\napp:checkbox("Remember me", true)',
      task: 'Make a clock that starts at a time you choose and runs at a different speed.',
      starter: '# Section 2, Lesson 7: Clocks and animation\n# Make a clock that starts at a time you choose and runs at a different speed.\n\nimport tgui\n\napp = tgui.window("Clock")\n\n',
      check: (src) => {
        if (!/:clock\b/.test(src)) return 'Add a clock with: clock = app:clock';
        if (!/:set\s*\(/.test(src)) return 'Set its time with clock:set(10, 30)';
        return /:speed\b/.test(src) ? true : 'Change how fast it runs with clock:speed 2';
      },
    },
    {
      id: 'tgui-build',
      title: 'Build an .exe',
      build: true,
      body: `<p>Turn any Tuff program into a real Windows app you can share. No Python needed on the other computer.</p>
             <p>Click the hammer at the top or press <kbd>Ctrl+F9</kbd>. Pick a name and an icon, then press <b>Build .exe</b>. The Build tab explains each step, and your app ends up in the <code>dist</code> folder.</p>`,
      example: '# 1. Open one of your tgui apps\n# 2. Click the hammer (or press Ctrl+F9)\n# 3. Choose a name and icon, then press Build .exe\n# 4. Click "Open app" when it finishes',
      task: 'Build one of your programs into an .exe.',
      starter: '',
      check: () => true,
    },
  ];

  const MTGUI = [
    {
      id: 'mtgui-window',
      title: 'Going modern',
      body: `<p><code>mtgui</code> (Modern Tuff GUI) works exactly like tgui, with a fancier look: gradients, glossy buttons, a shine when you hover, glowing text boxes and smooth animations.</p>
             <p>You can write <code>mention mtgui</code> or <code>import mtgui</code>. They do the same thing.</p>`,
      example: 'mention mtgui\n\napp = mtgui.window("Modern App")\napp:heading "So shiny"\napp:small "Hover the button to see the shine"\n\nfunc hi():\n    app:alert "Hey!"\n\napp:button("Say hi", hi)\napp:button("Secondary", hi, "outline")',
      task: 'Make an mtgui window with a heading and a button. Hover the button to see it shine.',
      starter: '# Section 2.1, Lesson 1: Going modern\n# Make an mtgui window with a heading and a button.\n\nmention mtgui\n\n',
      check: (src) => {
        if (!/^\s*(import|mention)\s+mtgui\b/m.test(src)) return 'Start with: mention mtgui';
        if (!/mtgui\.window\s*\(/.test(src)) return 'Make a window with: app = mtgui.window("My App")';
        return /:button\b/.test(src) ? true : 'Add a button with app:button("Text", fn)';
      },
    },
    {
      id: 'mtgui-gradients',
      title: 'Gradients and themes',
      body: `<p>Every accent in mtgui is a two-color gradient. Pick one with <code>app:accent "purple"</code>. Try blue, purple, pink, red, orange, yellow, green or teal.</p>
             <p>Make your own with <code>app:gradient("#00c6ff", "#7b2ff7")</code>. <code>app:theme "light"</code> switches to the light look.</p>`,
      example: 'mention mtgui\n\napp = mtgui.window("Gradients")\napp:heading "Pick a vibe"\nbar = app:progress(70)\n\nfunc sunset():\n    app:accent "orange"\n\nfunc ocean():\n    app:gradient("#00c6ff", "#7b2ff7")\n\nrow = app:row\nrow:button("Sunset", sunset)\nrow:button("Ocean", ocean)',
      task: 'Make buttons that change the accent gradient while the app is running.',
      starter: '# Section 2.1, Lesson 2: Gradients and themes\n# Make buttons that change the accent gradient while the app is running.\n\nmention mtgui\n\napp = mtgui.window("Gradients")\n\n',
      check: (src) => (/:(accent|gradient)\b/.test(src) && /:button\b/.test(src) ? true : 'Use app:accent or app:gradient inside a function a button runs.'),
    },
    {
      id: 'mtgui-motion',
      title: 'Motion and speed',
      body: `<p>Animated widgets look extra smooth in mtgui: the clock gets a gradient ring, the spinner a gradient tail, and progress bars shimmer.</p>
             <p>Change any animation with <code>:speed</code>. Buttons have it too: it controls how fast the shine sweeps across.</p>`,
      example: 'mention mtgui\n\napp = mtgui.window("Motion", 460, 560)\nclock = app:clock("analog", 140)\nclock:speed 30\n\nspin = app:spinner("Syncing...")\nspin:speed 2\n\nbar = app:progress(40)\nbar:speed 0.5\n\nfunc fill():\n    bar:set 100\n\napp:button("Fill it", fill)',
      task: 'Use <code>:speed</code> on at least two different animated widgets.',
      starter: '# Section 2.1, Lesson 3: Motion and speed\n# Use :speed on at least two different animated widgets.\n\nmention mtgui\n\napp = mtgui.window("Motion")\n\n',
      check: (src) => ((src.match(/:speed\b/g) || []).length >= 2 ? true : 'Use :speed on two things, like clock:speed 10 and spin:speed 2'),
    },
    {
      id: 'mtgui-studio',
      title: 'Design Studio',
      studio: true,
      body: `<p>Design Studio lets you build your window by clicking instead of typing. Open it with the palette button at the top or <kbd>Ctrl+Shift+D</kbd>.</p>
             <p>Add things from the left, click anything in the preview to change it on the right, and move or delete it. Every change is written into your code, so you can switch back any time. <kbd>Ctrl+Z</kbd> undoes it.</p>`,
      example: '# 1. Start the lesson, then click "Open Design Studio"\n# 2. Add a Card, then (with the card selected) a Heading and a Button\n# 3. Pick a gradient in the Window settings\n# 4. Click Run app',
      task: 'Use Design Studio to add a card with a heading and a button inside it, then run your app.',
      starter: '# Section 2.1, Lesson 4: Design Studio\n# Use Design Studio to add a card with a heading and a button, then run it.\n\nmention mtgui\n\napp = mtgui.window("Studio App")\n',
      check: (src) => {
        if (!/:card\b/.test(src)) return 'Add a card in Design Studio.';
        return /\w+:heading\b/.test(src) && /\w+:button\b/.test(src) ? true : 'Put a heading and a button in your card.';
      },
    },
  ];

  // The new sections' lessons also have a solution: a program their check accepts (the e2e tests run it).
  const ATGUI = [
    {
      id: 'atgui-window',
      title: 'Going advanced',
      body: `<p><code>atgui</code> (Advanced Tuff GUI) makes apps that look like the ones on your computer, with sidebars, lists, chat bubbles, dashboards and pop-ups. Most of mtgui works the same way.</p>
             <p><code>app:toast("Saved!", "success")</code> pops up a small message that goes away by itself. Try <code>"info"</code>, <code>"success"</code>, <code>"warning"</code> and <code>"error"</code>.</p>`,
      example: 'mention atgui\n\napp = atgui.window("My App", 600, 400)\napp:accent "indigo"\napp:heading "Hello, atgui!"\napp:text "Buttons, lists and pop-ups, all from Tuff."\n\nfunc saved():\n    app:toast("Saved!", "success")\n\napp:button("Save", saved)',
      task: 'Make an atgui window with a heading and a button that pops up a toast. Run it, click the button, then close the window.',
      starter: '# Section 2.2, Lesson 1: Going advanced\n# Make an atgui window with a heading and a button that pops up a toast.\n\nmention atgui\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Toasts", 500, 320)\napp:heading "Toast maker"\n\nfunc hello():\n    app:toast("Hello there!", "info")\n\napp:button("Make a toast", hello)\n',
      check: (src) => {
        if (!/^\s*(import|mention)\s+atgui\b/m.test(src)) return 'Start with: mention atgui';
        if (!/atgui\.window\s*\(/.test(src)) return 'Make a window with: app = atgui.window("My App")';
        if (!/:heading\b/.test(src)) return 'Add a heading, like: app:heading "Hello!"';
        if (!/:button\b/.test(src)) return 'Add a button, like: app:button("Save", saved)';
        return /:toast\b/.test(src) ? true : 'In the button\'s function, pop up a toast: app:toast("Hi!", "info")';
      },
    },
    {
      id: 'atgui-icons',
      title: 'Icons and badges',
      body: `<p>atgui has more than 80 icons built in. Put one on a button with <code>:icon</code>, like <code>app:button("Send", send):icon "send"</code>. With <code>""</code> as the button's text, only the icon shows.</p>
             <p>A <b>badge</b> is a small colored label: <code>app:badge("New", "success")</code>. <code>app:avatar("Ada Lovelace")</code> shows someone's initials in a circle.</p>`,
      example: 'mention atgui\n\napp = atgui.window("Inbox", 520, 360)\ntop = app:row\ntop:avatar("Ada Lovelace")\ntop:heading "Ada"\ntop:badge("3 new", "success")\n\nfunc liked():\n    app:toast("Liked!", "success")\n\nrow = app:row\nrow:button("Like", liked):icon "heart"\nrow:button("", liked, "ghost"):icon "star"',
      task: 'Give a button an icon, and add a badge next to something.',
      starter: '# Section 2.2, Lesson 2: Icons and badges\n# Give a button an icon, and add a badge next to something.\n\nmention atgui\n\napp = atgui.window("Icons", 520, 360)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Icons", 520, 360)\nrow = app:row\nrow:heading "Messages"\nrow:badge("2 new", "info")\n\nfunc sent():\n    app:toast("Sent!", "success")\n\napp:button("Send", sent):icon "send"\n',
      check: (src) => {
        if (!/\)\s*:icon\b/.test(src) && !/\b(\w+)\s*=\s*\w+:button\b[\s\S]*\b\1:icon\b/.test(src)) return 'Put an icon on a button: app:button("Send", sent):icon "send"';
        return /:badge\b/.test(src) ? true : 'Add a badge, like: app:badge("New", "success")';
      },
    },
    {
      id: 'atgui-sidebar',
      title: 'Sidebars and lists',
      body: `<p><code>side = app:sidebar(220)</code> makes a column down the left side, 220 pixels wide. Add things to it just like the window.</p>
             <p><code>side:list(["Ideas", "Shopping"])</code> makes a list you can click. <code>notes:change opened</code> runs a function when an item is picked, and the function gets the item's text.</p>`,
      example: 'mention atgui\n\napp = atgui.window("Notes", 700, 420)\nside = app:sidebar(200)\nside:heading "Notes"\nnotes = side:list(["Ideas", "Shopping", "Homework"])\ntitle = app:heading "Pick a note"\n\nfunc opened(name):\n    title:set name\n\nnotes:change opened',
      task: 'Make a sidebar with a list in it. When an item is picked, show its name in a heading.',
      starter: '# Section 2.2, Lesson 3: Sidebars and lists\n# Make a sidebar with a list. When an item is picked, show its name in a heading.\n\nmention atgui\n\napp = atgui.window("Sidebar", 700, 420)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Sidebar", 700, 420)\nside = app:sidebar(220)\nside:heading "Pets"\npets = side:list(["Cat", "Dog", "Fish"])\nshown = app:heading "Pick a pet"\n\nfunc picked(pet):\n    shown:set "You picked " + pet\n\npets:change picked\n',
      check: (src) => {
        if (!/:sidebar\b/.test(src)) return 'Make a sidebar with: side = app:sidebar(220)';
        if (!/:list\b/.test(src)) return 'Put a list in it: items = side:list(["Ideas", "Shopping"])';
        return /:change\b/.test(src) ? true : 'Run a function when an item is picked: items:change picked';
      },
    },
    {
      id: 'atgui-style',
      title: 'Styles and animation',
      body: `<p>Change how anything looks with <code>:style(name, value)</code>. <code>card:style("radius", 20)</code> rounds its corners and <code>label:style("size", 40)</code> makes text bigger. Start the name with <code>hover</code> to change it only while the mouse is over it: <code>btn:style("hover scale", 1.1)</code>.</p>
             <p><code>:animate "pop"</code> plays an animation. Try <code>bounce</code>, <code>shake</code>, <code>spin</code>, <code>wiggle</code> and <code>slide-up</code>.</p>`,
      example: 'mention atgui\n\napp = atgui.window("Styles", 480, 360)\ncard = app:card\ncard:style("radius", 24)\ncard:style("hover shadow", "glow")\nstar = card:heading "Star"\nstar:style("size", 40)\n\nfunc wiggle():\n    star:animate "wiggle"\n\ngo = card:button("Wiggle", wiggle, "gradient")\ngo:style("hover scale", 1.1)',
      task: 'Style a card, and make something in it animate when a button is clicked.',
      starter: '# Section 2.2, Lesson 4: Styles and animation\n# Style a card, and make something animate when a button is clicked.\n\nmention atgui\n\napp = atgui.window("Styles", 480, 360)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Party", 480, 360)\ncard = app:card\ncard:style("radius", 20)\ncard:style("background", "pink")\nbig = card:heading "Party time"\n\nfunc party():\n    big:animate "bounce"\n\ncard:button("Bounce", party)\n',
      check: (src) => {
        if (!/:card\b/.test(src)) return 'Make a card with: card = app:card';
        if (!/:style\b/.test(src)) return 'Style it, like: card:style("radius", 20)';
        if (!/:button\b/.test(src)) return 'Add a button that runs a function: card:button("Go", go)';
        return /:animate\b/.test(src) ? true : 'In the button\'s function, animate something: label:animate "bounce"';
      },
    },
    {
      id: 'atgui-popups',
      title: 'Pop-ups',
      body: `<p>A <b>modal</b> is a pop-up box with things inside. Make one with <code>dlg = app:modal("Rename")</code>, add widgets to it like a card, then show it with <code>dlg:open</code>. <code>dlg:close</code> hides it again, and so do <kbd>Esc</kbd> and a click outside it.</p>
             <p><code>app:confirm "Clear it?"</code> asks yes or no and gives back true or false.</p>`,
      example: 'mention atgui\n\napp = atgui.window("Pop-ups", 520, 360)\nname = app:heading "Untitled"\ndlg = app:modal("Rename")\nbox = dlg:input "New name"\n\nfunc save_name():\n    name:set box:value()\n    dlg:close\n\nfunc rename():\n    dlg:open\n\nfunc clear_name():\n    if app:confirm "Clear the name?":\n        name:set "Untitled"\n\ndlg:button("Save", save_name)\nrow = app:row\nrow:button("Rename", rename)\nrow:button("Clear", clear_name, "danger")',
      task: 'Make a button that opens a modal with a text box inside it. Use what was typed when the modal\'s own button is clicked.',
      starter: '# Section 2.2, Lesson 5: Pop-ups\n# Make a button that opens a modal with a text box inside it.\n\nmention atgui\n\napp = atgui.window("Pop-ups", 520, 360)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Hello", 520, 360)\nhello = app:heading "Hello!"\ndlg = app:modal("Your name")\nbox = dlg:input "Type your name"\n\nfunc done():\n    hello:set "Hello, " + box:value() + "!"\n    dlg:close\n\nfunc ask_name():\n    dlg:open\n\ndlg:button("Done", done)\napp:button("Change name", ask_name)\n',
      check: (src) => {
        if (!/:modal\b/.test(src)) return 'Make a pop-up with: dlg = app:modal("Rename")';
        if (!/:input\b/.test(src)) return 'Put a text box in it: box = dlg:input "New name"';
        if (!/:open\b/.test(src)) return 'Show it from a button\'s function with: dlg:open';
        return /:value\b/.test(src) ? true : 'Read what was typed with: box:value()';
      },
    },
    {
      id: 'atgui-keys',
      title: 'Keyboard shortcuts',
      body: `<p><code>app:key("ctrl+s", save)</code> runs a function when keys are pressed. Try <code>"escape"</code>, <code>"f5"</code>, <code>"space"</code> or <code>"ctrl+shift+n"</code>.</p>
             <p>Keys with Ctrl or Alt, the F keys and Escape work anywhere in the window, even while someone is typing in a text box. Other keys, like <code>"space"</code>, don't run while someone is typing, so a space typed in a box stays a space.</p>
             <p>Tell people about the shortcut with a tooltip: <code>btn:tooltip "Ctrl+S"</code> shows when the mouse rests on the button.</p>`,
      example: 'mention atgui\n\napp = atgui.window("Shortcuts", 520, 360)\napp:heading "Press Ctrl+S"\nnotes = app:textarea "Write something"\n\nfunc save():\n    app:toast("Saved!", "success")\n\nbtn = app:button("Save", save)\nbtn:tooltip "Ctrl+S"\napp:key("ctrl+s", save)',
      task: 'Make a key (like <kbd>Space</kbd> or <kbd>Ctrl+S</kbd>) run a function that pops up a toast.',
      starter: '# Section 2.2, Lesson 6: Keyboard shortcuts\n# Make a key run a function that pops up a toast.\n\nmention atgui\n\napp = atgui.window("Shortcuts", 420, 300)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Space counter", 420, 300)\ncount = 0\nshown = app:heading "Press space"\n\nfunc add():\n    count += 1\n    shown:set "Pressed " + count + " times"\n    app:toast("Nice!", "info")\n\napp:key("space", add)\n',
      check: (src) => {
        if (!/:key\b/.test(src)) return 'Connect a key to a function: app:key("space", jump)';
        return /:toast\b/.test(src) ? true : 'In that function, pop up a toast: app:toast("Nice!", "info")';
      },
    },
    {
      id: 'atgui-dashboard',
      title: 'Dashboards',
      body: `<p><code>grid = app:grid(3)</code> puts things in 3 columns. Add a card for each one.</p>
             <p><code>card:chart([3, 8, 5, 9], "line")</code> draws a chart from a list of numbers. <code>"bar"</code> works too. <code>chart:add(7)</code> adds a number to the end, so a chart can grow while the app runs.</p>`,
      example: 'mention atgui\n\napp = atgui.window("My week", 760, 420)\napp:heading "My week"\ngrid = app:grid(3)\n\nsteps = grid:card\nsteps:small "Steps"\nsteps:heading "8,214"\nsteps:chart([5, 7, 6, 9, 8], "line")\n\nrest = grid:card\nrest:small "Sleep"\nrest:heading "7.5 h"\nrest:chart([7, 8, 6, 7, 8], "bar")\n\nwater = grid:card\nwater:small "Water"\nwater:heading "6 cups"\nlive = water:chart([2, 4, 6], "line")\n\nfunc drink():\n    live:add(random(1, 8))\n\napp:every(2, drink)',
      task: 'Make a grid of cards with at least one chart in it.',
      starter: '# Section 2.2, Lesson 7: Dashboards\n# Make a grid of cards with at least one chart in it.\n\nmention atgui\n\napp = atgui.window("Dashboard", 760, 420)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Game stats", 760, 420)\napp:heading "Game stats"\ngrid = app:grid(2)\nwins = grid:card\nwins:small "Wins"\nwins:heading "12"\nwins:chart([1, 3, 2, 4, 2], "bar")\nbest = grid:card\nbest:small "Best score"\nbest:heading "980"\nbest:chart([400, 650, 720, 980], "line")\n',
      check: (src) => {
        if (!/:grid\b/.test(src)) return 'Make a grid with: grid = app:grid(3)';
        if (!/:card\b/.test(src)) return 'Put cards in it: box = grid:card';
        return /:chart\b/.test(src) ? true : 'Draw a chart in a card: box:chart([3, 8, 5], "line")';
      },
    },
    {
      id: 'atgui-chat',
      title: 'Build a chat app',
      body: `<p><code>msgs = app:scroll()</code> makes an area that scrolls by itself, like a chat's messages. <code>msgs:to_bottom</code> scrolls to the newest one.</p>
             <p>In a <code>textarea</code>, <code>box:enter send</code> runs when <kbd>Enter</kbd> is pressed. <kbd>Shift+Enter</kbd> starts a new line. Use <code>app:after</code> to make a friend reply a moment later.</p>`,
      example: 'mention atgui\n\napp = atgui.window("Chat", 520, 560)\napp:heading "Chat with Robo"\nmsgs = app:scroll()\nbar = app:row\nbox = bar:textarea "Write a message"\nbox:grow\n\nfunc reply():\n    msgs:text "Robo: Cool!"\n    msgs:to_bottom\n\nfunc send():\n    words = box:value():trim()\n    if words is not "":\n        msgs:text "You: " + words\n        box:clear\n        msgs:to_bottom\n        app:after(1, reply)\n\nbox:enter send\nbar:button("", send, "primary"):icon "send"',
      task: 'Make a chat: pressing <kbd>Enter</kbd> adds your message to a scroll area, and a friend replies a second later.',
      starter: '# Section 2.2, Lesson 8: Build a chat app\n# Pressing Enter adds your message to a scroll area,\n# and a friend replies a second later.\n\nmention atgui\n\napp = atgui.window("Chat", 520, 560)\n\n',
      solution: 'mention atgui\n\napp = atgui.window("Chat", 520, 560)\nmsgs = app:scroll()\nbox = app:textarea "Say something"\n\nfunc answer():\n    msgs:text "Friend: Haha, nice!"\n    msgs:to_bottom\n\nfunc send():\n    said = box:value():trim()\n    if said is not "":\n        bubble = msgs:text "Me: " + said\n        bubble:animate "slide-up"\n        box:clear\n        msgs:to_bottom\n        app:after(1, answer)\n\nbox:enter send\n',
      check: (src) => {
        if (!/:scroll\b/.test(src)) return 'Make the messages area with: msgs = app:scroll()';
        if (!/:enter\b/.test(src)) return 'Send when Enter is pressed: box:enter send';
        return /:after\b/.test(src) ? true : 'Make the friend reply a second later: app:after(1, reply)';
      },
    },
  ];

  const TAP = [
    {
      id: 'tap-get',
      title: 'Your first request',
      body: `<p>The <code>tap</code> library lets your program talk to websites. Lots of sites have an <b>API</b>: a web address made for programs instead of people.</p>
             <p><code>res = tap.get("https://...")</code> asks for that address and waits for the answer. <code>res:text</code> is what came back, and <code>res:status</code> says how it went (200 means OK).</p>
             <p>You need the internet for this section.</p>`,
      example: 'mention tap\n\nres = tap.get("https://catfact.ninja/fact")\nsay "Status: " + res:status\nsay res:text',
      task: 'Get <code>https://official-joke-api.appspot.com/random_joke</code> and say what comes back.',
      starter: '# Section 3, Lesson 1: Your first request\n# Get https://official-joke-api.appspot.com/random_joke and say what comes back.\n# You need the internet for this section.\n\nmention tap\n\n',
      solution: 'mention tap\n\nres = tap.get("https://official-joke-api.appspot.com/random_joke")\nsay res:status\nsay res:text\n',
      check: (src, out) => {
        if (!/^\s*(import|mention)\s+tap\b/m.test(src)) return 'Start with: mention tap';
        if (!/tap\.get\s*\(/.test(src)) return 'Ask for the address with: res = tap.get("https://...")';
        if (!/:text\b/.test(src)) return 'Say what came back with: say res:text';
        return lines(out).length ? true : 'Your program ran but didn\'t say anything.';
      },
    },
    {
      id: 'tap-json',
      title: 'Reading JSON',
      body: `<p>Most APIs answer in <b>JSON</b>, a way of writing data as names and values, like <code>{"fact": "Cats nap a lot", "length": 14}</code>.</p>
             <p><code>data = res:json</code> turns it into a <b>data object</b>. Get a value out of it with <code>data:get("fact")</code>. <code>data:keys()</code> lists every name it has.</p>`,
      example: 'mention tap\n\nres = tap.get("https://catfact.ninja/fact")\ndata = res:json\nsay data:keys()\nsay data:get("fact")\nsay "That fact is " + data:get("length") + " characters long."',
      task: 'Get a random joke, then say its <code>"setup"</code> and its <code>"punchline"</code>.',
      starter: '# Section 3, Lesson 2: Reading JSON\n# Get a random joke, then say its "setup" and its "punchline".\n\nmention tap\n\nres = tap.get("https://official-joke-api.appspot.com/random_joke")\n',
      solution: 'mention tap\n\nres = tap.get("https://official-joke-api.appspot.com/random_joke")\njoke = res:json\nsay joke:get("setup")\nsay joke:get("punchline")\n',
      check: (src, out) => {
        if (!/:json\b/.test(src)) return 'Turn the answer into data with: joke = res:json';
        if (!/:get\s*\(?\s*["']setup["']/.test(src)) return 'Say the setup with: say joke:get("setup")';
        if (!/:get\s*\(?\s*["']punchline["']/.test(src)) return 'Now the punchline: say joke:get("punchline")';
        return lines(out).length ? true : 'Your program ran but didn\'t say anything.';
      },
    },
    {
      id: 'tap-ok',
      title: 'When it goes wrong',
      body: `<p>Sometimes a site can't find what you asked for. Then <code>res:status</code> is 404 (not found) instead of 200, and your program keeps going.</p>
             <p><code>res:ok</code> is true when it worked. Check it before you use the answer, and say something friendly when it didn't.</p>
             <p>Check for an empty name first, in case someone just presses <kbd>Enter</kbd>. With no name, the address gets a list of Pokémon instead (just the first 20). That works, so <code>res:ok</code> would be true, but the list has no weight in it.</p>`,
      example: 'mention tap\n\nname = input "Which Pokémon? "\nname = name:trim():lower()\nif name is "":\n    say "Type a name first!"\nelse:\n    res = tap.get("https://pokeapi.co/api/v2/pokemon/" + name)\n    if res:ok:\n        mon = res:json\n        say name + " weighs " + (mon:get("weight") / 10) + " kg"\n    else:\n        say "There is no Pokémon called " + name + " (error " + res:status + ")"',
      task: 'Ask for a GitHub username (try <code>octocat</code>). If <code>res:ok</code>, say how many <code>"public_repos"</code> they have. If not, say a friendly message.',
      starter: '# Section 3, Lesson 3: When it goes wrong\n# Ask for a GitHub username. If res:ok, say how many "public_repos" they have.\n# If not, say a friendly message.\n\nmention tap\n\n',
      solution: 'mention tap\n\nwho = input "GitHub username? "\nwho = who:trim()\nif who is "":\n    say "Type a name first!"\nelse:\n    res = tap.get("https://api.github.com/users/" + who)\n    if res:ok:\n        user = res:json\n        say who + " has " + user:get("public_repos") + " public repos"\n    else:\n        say "Couldn\'t find " + who + " (error " + res:status + ")"\n',
      check: (src, out) => {
        if (!/\binput\b/.test(src)) return 'Ask for the name with: who = input "GitHub username? "';
        if (!/:ok\b/.test(src)) return 'Check the answer first: if res:ok:';
        if (!/\belse\b/.test(src)) return 'Add an else: with a friendly message for when it didn\'t work.';
        return lines(out).length ? true : 'Your program ran but didn\'t say anything.';
      },
    },
    {
      id: 'tap-lists',
      title: 'Lists in answers',
      body: `<p>Some answers hold a <b>list</b>. <code>https://catfact.ninja/facts?limit=3</code> sends back three facts at once, in a list called <code>"data"</code>.</p>
             <p>Get the list with <code>page:get("data")</code>, then go through it with <code>for</code>. Each item is a data object of its own.</p>`,
      example: 'mention tap\n\nres = tap.get("https://catfact.ninja/facts?limit=3")\npage = res:json\nfacts = page:get("data")\nsay "I got " + len(facts) + " facts:"\nfor fact in facts:\n    say "- " + fact:get("fact")',
      task: 'Get 5 cat facts (<code>?limit=5</code>) and say each one with its number in front, like <code>1. Cats ...</code>',
      starter: '# Section 3, Lesson 4: Lists in answers\n# Get 5 cat facts and say each one with its number in front, like "1. Cats ..."\n\nmention tap\n\n',
      solution: 'mention tap\n\nres = tap.get("https://catfact.ninja/facts?limit=5")\npage = res:json\nfacts = page:get("data")\ncount = 0\nfor fact in facts:\n    count += 1\n    say text(count) + ". " + fact:get("fact")\n',
      check: (src, out) => {
        if (!/limit=5\b/.test(src)) return 'Ask for 5 facts: put ?limit=5 at the end of the address.';
        if (!/\bfor\b/.test(src)) return 'Go through the list with: for fact in facts:';
        return lines(out).some((l) => /^1\.\s/.test(l)) ? true : 'Put the number in front, like: say text(count) + ". " + fact:get("fact")';
      },
    },
    {
      id: 'tap-weather',
      title: 'Weather in numbers',
      body: `<p>Numbers in JSON come out as real Tuff numbers, so you can do maths with them.</p>
             <p>Open-Meteo gives the weather anywhere: put a place's <code>latitude</code> and <code>longitude</code> in the address. The temperature is inside <code>"current"</code>, a data object inside the answer, so get it in two steps: <code>data:get("current"):get("temperature_2m")</code>.</p>`,
      example: 'mention tap\n\nres = tap.get("https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current=temperature_2m")\ndata = res:json\nnow = data:get("current")\ntemp = now:get("temperature_2m")\nsay "Right now it is " + temp + "°C in London"\nif temp < 10:\n    say "Wear a coat!"',
      task: 'Say the temperature in °F too: multiply it by 9, divide by 5, add 32, then <code>round</code> it.',
      starter: '# Section 3, Lesson 5: Weather in numbers\n# Say the temperature in °F too: multiply by 9, divide by 5, add 32, then round it.\n\nmention tap\n\nres = tap.get("https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current=temperature_2m")\ndata = res:json\n',
      solution: 'mention tap\n\nres = tap.get("https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&current=temperature_2m")\ndata = res:json\ntemp = data:get("current"):get("temperature_2m")\nsay "Right now it is " + temp + "°C"\nsay "That is " + round(temp * 9 / 5 + 32) + "°F"\n',
      check: (src, out) => {
        if (!/:get\s*\(?\s*["']temperature_2m["']/.test(src)) return 'Get the temperature with: data:get("current"):get("temperature_2m")';
        if (!/\*\s*9\s*\/\s*5|\*\s*1\.8\b/.test(src)) return 'For °F, multiply by 9 / 5 and add 32: temp * 9 / 5 + 32';
        if (!/\bround\s*\(/.test(src)) return 'Round it with round(...)';
        return lines(out).length ? true : 'Your program ran but didn\'t say anything.';
      },
    },
    {
      id: 'tap-post',
      title: 'Sending data',
      body: `<p><code>tap.get</code> asks for something. <code>tap.post</code> <b>sends</b> something, like a new post or a high score.</p>
             <p>Build what you send with <code>post = tap.data()</code> and <code>post:set("title", "Hello")</code>, then send it with <code>tap.post(address, post)</code>. JSONPlaceholder is a site for testing: it pretends to save your post and sends it back with an <code>"id"</code>.</p>`,
      example: 'mention tap\n\npost = tap.data()\npost:set("title", "Hello from Tuff")\npost:set("body", "My first post")\npost:set("userId", 1)\nsent = tap.post("https://jsonplaceholder.typicode.com/posts", post)\nsay "Status: " + sent:status\nsay sent:json',
      task: 'Send a post about your favorite game, then say the <code>"id"</code> the server gives back.',
      starter: '# Section 3, Lesson 6: Sending data\n# Send a post about your favorite game, then say the "id" the server gives back.\n\nmention tap\n\n',
      solution: 'mention tap\n\npost = tap.data()\npost:set("title", "My favorite game")\npost:set("body", "Hide and seek, because anyone can play")\npost:set("userId", 7)\nsent = tap.post("https://jsonplaceholder.typicode.com/posts", post)\nif sent:ok:\n    saved = sent:json\n    say "Saved as post number " + saved:get("id")\nelse:\n    say "That did not work: error " + sent:status\n',
      check: (src, out) => {
        if (!/tap\.data\s*\(/.test(src)) return 'Make what you send with: post = tap.data()';
        if (!/:set\b/.test(src)) return 'Fill it in: post:set("title", "My favorite game")';
        if (!/tap\.post\s*\(/.test(src)) return 'Send it with: sent = tap.post("https://jsonplaceholder.typicode.com/posts", post)';
        if (!/:get\s*\(?\s*["']id["']/.test(src)) return 'Say the id that comes back: answer = sent:json, then say answer:get("id")';
        return lines(out).length ? true : 'Your program ran but didn\'t say anything.';
      },
    },
    {
      id: 'tap-app',
      title: 'The internet in an app',
      body: `<p>tap works in window apps too. Get the data in a button's function, then show it with <code>:set</code>.</p>
             <p>The window waits while the answer comes in, so make one request per click.</p>`,
      example: 'mention mtgui\nmention tap\n\napp = mtgui.window("Cat facts", 420, 320)\napp:heading "Cat facts"\nfact = app:text "Click the button for a fact."\n\nfunc new_fact():\n    res = tap.get("https://catfact.ninja/fact")\n    if res:ok:\n        data = res:json\n        fact:set data:get("fact")\n    else:\n        fact:set "No fact right now. Try again!"\n\napp:button("New fact", new_fact)',
      task: 'Make a joke app: a button that gets a new joke and shows its setup and punchline in two labels.',
      starter: '# Section 3, Lesson 7: The internet in an app\n# Make a button that gets a new joke and shows its setup and punchline.\n\nmention mtgui\nmention tap\n\napp = mtgui.window("Jokes", 440, 340)\n\n',
      solution: 'mention mtgui\nmention tap\n\napp = mtgui.window("Jokes", 440, 340)\napp:heading "Joke machine"\nsetup = app:text "Click for a joke."\npunchline = app:small ""\n\nfunc joke():\n    res = tap.get("https://official-joke-api.appspot.com/random_joke")\n    if res:ok:\n        data = res:json\n        setup:set data:get("setup")\n        punchline:set data:get("punchline")\n    else:\n        setup:set "The joke server is resting. Try again!"\n\napp:button("Tell me a joke", joke)\n',
      check: (src) => {
        if (!/^\s*(import|mention)\s+tap\b/m.test(src)) return 'Add: mention tap';
        if (!/\b(tgui|mtgui|atgui)\.window\s*\(/.test(src)) return 'Make a window with: app = mtgui.window("Jokes")';
        if (!/:button\b/.test(src)) return 'Add a button: app:button("Tell me a joke", joke)';
        if (!/tap\.get\s*\(/.test(src)) return 'In the button\'s function, get a joke with tap.get(...)';
        return /:set\b/.test(src) ? true : 'Show the joke with: setup:set data:get("setup")';
      },
    },
  ];

  const TGAME = [
    {
      id: 'tgame-window',
      title: 'Your first game',
      body: `<p><code>tgame</code> makes games you can play: shapes that move, keys to steer them, scores and sounds. <code>game = tgame.window("Title", 600, 400)</code> opens a game window 600 wide and 400 tall.</p>
             <p>Shapes are called <b>sprites</b>: <code>game:box(x, y, width, height, color)</code> and <code>game:circle(x, y, radius, color)</code>. x and y are the middle of the sprite. (0, 0) is the top-left corner, and y goes <b>down</b>.</p>
             <p>A game runs in a loop. <code>while game:open():</code> keeps going until the window closes, and <code>game:frame()</code> draws each frame.</p>`,
      example: 'mention tgame\n\ngame = tgame.window("My Game", 600, 400)\ngame:background "navy"\nsun = game:circle(500, 80, 40, "gold")\nground = game:box(300, 380, 600, 40, "grass")\ngame:text("Hello, game!", 300, 200, 32, "white")\n\nwhile game:open():\n    game:frame()',
      task: 'Make a game window with a background color, a circle and a box. Run it, then close the window.',
      starter: '# Section 4, Lesson 1: Your first game\n# Make a game window with a background color, a circle and a box.\n\nmention tgame\n\n',
      solution: 'mention tgame\n\ngame = tgame.window("Space", 600, 400)\ngame:background "black"\nplanet = game:circle(300, 200, 60, "teal")\nship = game:box(100, 320, 40, 20, "silver")\n\nwhile game:open():\n    game:frame()\n',
      check: (src) => {
        if (!/^\s*(import|mention)\s+tgame\b/m.test(src)) return 'Start with: mention tgame';
        if (!/tgame\.window\s*\(/.test(src)) return 'Make a game window with: game = tgame.window("My Game", 600, 400)';
        if (!/:background\b/.test(src)) return 'Pick a background color: game:background "navy"';
        if (!/:circle\b/.test(src) || !/:box\b/.test(src)) return 'Add a circle and a box, like: game:circle(300, 200, 40, "gold")';
        return /while\s+\w+:open\b/.test(src) ? true : 'Keep the game running: while game:open(): with game:frame() inside it';
      },
    },
    {
      id: 'tgame-keys',
      title: 'Moving with keys',
      body: `<p><code>game:held("left")</code> is true while the left arrow is held down. Check it in the loop to move things.</p>
             <p><code>dt = game:frame()</code> gives the seconds since the last frame (about 0.016). Moving by <code>300 * dt</code> each frame moves 300 pixels a second, on any computer. <code>player:on_edge "stop"</code> keeps it on the screen.</p>`,
      example: 'mention tgame\n\ngame = tgame.window("Move", 600, 400)\nplayer = game:box(300, 200, 40, 40, "lime")\nplayer:on_edge "stop"\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n    if game:held("right"):\n        player:move(300 * dt, 0)',
      task: 'Make the player move up and down too, with the up and down arrows. Remember, y goes down.',
      starter: '# Section 4, Lesson 2: Moving with keys\n# Make the player move up and down too, with the up and down arrows.\n\nmention tgame\n\ngame = tgame.window("Move", 600, 400)\nplayer = game:box(300, 200, 40, 40, "lime")\nplayer:on_edge "stop"\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n    if game:held("right"):\n        player:move(300 * dt, 0)\n',
      solution: 'mention tgame\n\ngame = tgame.window("Move", 600, 400)\nplayer = game:box(300, 200, 40, 40, "lime")\nplayer:on_edge "stop"\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n    if game:held("right"):\n        player:move(300 * dt, 0)\n    if game:held("up"):\n        player:move(0, -300 * dt)\n    if game:held("down"):\n        player:move(0, 300 * dt)\n',
      check: (src) => {
        if (!/:held\s*\(?\s*["']up["']/.test(src)) return 'Check the up arrow with: if game:held("up"):';
        if (!/:held\s*\(?\s*["']down["']/.test(src)) return 'Now the down arrow: if game:held("down"):';
        return /:move\s*\(\s*0\s*,/.test(src) ? true : 'Move up and down by changing y: player:move(0, -300 * dt)';
      },
    },
    {
      id: 'tgame-bounce',
      title: 'Speed and bouncing',
      body: `<p><code>ball:speed(200, 150)</code> keeps a sprite moving by itself: 200 pixels a second across and 150 down. You don't have to move it in the loop.</p>
             <p><code>ball:on_edge "bounce"</code> makes it bounce off the edges. <code>"wrap"</code> brings it back on the other side, and <code>"stop"</code> stops it.</p>`,
      example: 'mention tgame\n\ngame = tgame.window("Bounce", 600, 400)\nball = game:circle(300, 200, 20, "gold")\nball:speed(200, 150)\nball:on_edge "bounce"\nghost = game:circle(100, 100, 15, "white")\nghost:speed(120, 0)\nghost:on_edge "wrap"\n\nwhile game:open():\n    game:frame()',
      task: 'Make three balls in different colors that bounce around the screen by themselves.',
      starter: '# Section 4, Lesson 3: Speed and bouncing\n# Make three balls in different colors that bounce around by themselves.\n\nmention tgame\n\ngame = tgame.window("Bounce", 600, 400)\n\n# make your balls here\n\nwhile game:open():\n    game:frame()\n',
      solution: 'mention tgame\n\ngame = tgame.window("Three balls", 600, 400)\nfor color in ["red", "gold", "teal"]:\n    ball = game:circle(random(50, 550), random(50, 350), 20, color)\n    ball:speed(random(100, 250), random(100, 250))\n    ball:on_edge "bounce"\n\nwhile game:open():\n    game:frame()\n',
      check: (src) => {
        if (!/:circle\b/.test(src)) return 'Make a ball with: ball = game:circle(300, 200, 20, "gold")';
        if (!/:speed\b/.test(src)) return 'Keep a ball moving with: ball:speed(200, 150)';
        if (!/:on_edge\s*\(?\s*["']bounce["']/.test(src)) return 'Make it bounce with: ball:on_edge "bounce"';
        return (src.match(/:circle\b/g) || []).length >= 3 || /\bfor\b/.test(src) ? true : 'Make three balls. A for loop can make them for you.';
      },
    },
    {
      id: 'tgame-catch',
      title: 'Catch and score',
      body: `<p><code>player:touches(coin)</code> is true when two sprites touch. That's how a game knows you caught something, or got hit.</p>
             <p>Keep the score in a variable, show it with <code>label = game:text("Score: 0", 300, 24)</code> and change it with <code>label:set</code>. <code>game:sound "coin"</code> plays a sound. Try beep, jump, hit, boom, pop, powerup and win.</p>
             <p><code>coin:move_to(game:random_spot())</code> sends the coin somewhere random. If it lands on the player, the <code>while</code> picks a new spot, so one coin can't be caught twice.</p>`,
      example: 'mention tgame\n\ngame = tgame.window("Coins", 600, 400)\nplayer = game:box(100, 200, 30, 30, "lime")\nplayer:on_edge "stop"\ncoin = game:circle(400, 200, 12, "gold")\ncoins = 0\nlabel = game:text("Coins: 0", 300, 24)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n    if game:held("right"):\n        player:move(300 * dt, 0)\n    if game:held("up"):\n        player:move(0, -300 * dt)\n    if game:held("down"):\n        player:move(0, 300 * dt)\n    if player:touches(coin):\n        coins += 1\n        label:set "Coins: " + coins\n        game:sound "coin"\n        coin:move_to(game:random_spot())\n        while coin:touches(player):\n            coin:move_to(game:random_spot())',
      task: 'Catch the falling star: when it touches the basket, add 1 to the score, show it, and send the star back to the top.',
      starter: '# Section 4, Lesson 4: Catch and score\n# When the star touches the basket, add 1 to the score, show it,\n# and send the star back to the top.\n\nmention tgame\n\ngame = tgame.window("Catch", 600, 400)\nbasket = game:box(300, 370, 80, 20, "gold")\nbasket:on_edge "stop"\nstar = game:circle(300, 0, 12, "yellow")\nscore = 0\nlabel = game:text("Score: 0", 300, 24)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        basket:move(-400 * dt, 0)\n    if game:held("right"):\n        basket:move(400 * dt, 0)\n    star:move(0, 200 * dt)\n    if star:y() > 400:\n        star:move_to(random(20, 580), 0)\n',
      solution: 'mention tgame\n\ngame = tgame.window("Catch", 600, 400)\nbasket = game:box(300, 370, 80, 20, "gold")\nbasket:on_edge "stop"\nstar = game:circle(300, 0, 12, "yellow")\nscore = 0\nlabel = game:text("Score: 0", 300, 24)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        basket:move(-400 * dt, 0)\n    if game:held("right"):\n        basket:move(400 * dt, 0)\n    star:move(0, 200 * dt)\n    if star:touches(basket):\n        score += 1\n        label:set "Score: " + score\n        game:sound "coin"\n        star:move_to(random(20, 580), 0)\n    elif star:y() > 400:\n        star:move_to(random(20, 580), 0)\n',
      check: (src) => {
        if (!/:touches\b/.test(src)) return 'Check for a catch with: if star:touches(basket):';
        if (!/\bscore\s*(\+=|=\s*score\s*\+)/.test(src)) return 'Add to the score with: score += 1';
        return /:set\b/.test(src) ? true : 'Show the new score with: label:set "Score: " + score';
      },
    },
    {
      id: 'tgame-dodge',
      title: 'Dodge and game over',
      body: `<p><code>game:every(1, drop)</code> runs a function every second. Here it makes a new rock each time and puts it in a <b>group</b>: <code>rocks = game:group()</code>, then <code>rocks:add(rock)</code>. <code>player:touches(rocks)</code> checks every rock at once.</p>
             <p><code>game:game_over("Hit!", start)</code> stops the game and shows a message. Pressing <kbd>Space</kbd> then runs <code>start</code>, which should put everything back.</p>`,
      example: 'mention tgame\n\ngame = tgame.window("Dodge", 400, 300)\nplayer = game:box(200, 270, 30, 30, "lime")\nplayer:on_edge "stop"\nrocks = game:group()\n\nfunc drop():\n    rock = game:circle(random(10, 390), 0, 10, "gray")\n    rock:speed(0, 150)\n    rocks:add(rock)\n\nfunc start():\n    rocks:clear()\n\ngame:every(1, drop)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-250 * dt, 0)\n    if game:held("right"):\n        player:move(250 * dt, 0)\n    if player:touches(rocks):\n        game:game_over("Hit by a rock!", start)',
      task: 'Add a score that goes up by 1 every second you stay alive. Show it in the game-over message, and set it back to 0 in <code>start</code>.',
      starter: '# Section 4, Lesson 5: Dodge and game over\n# Add a score that goes up by 1 every second you stay alive.\n# Show it in the game-over message, and set it back to 0 in start.\n\nmention tgame\n\ngame = tgame.window("Dodge", 400, 300)\nplayer = game:box(200, 270, 30, 30, "lime")\nplayer:on_edge "stop"\nrocks = game:group()\n\nfunc drop():\n    rock = game:circle(random(10, 390), 0, 10, "gray")\n    rock:speed(0, 150)\n    rocks:add(rock)\n\nfunc start():\n    rocks:clear()\n\ngame:every(1, drop)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-250 * dt, 0)\n    if game:held("right"):\n        player:move(250 * dt, 0)\n    if player:touches(rocks):\n        game:game_over("Hit by a rock!", start)\n',
      solution: 'mention tgame\n\ngame = tgame.window("Dodge", 400, 300)\nplayer = game:box(200, 270, 30, 30, "lime")\nplayer:on_edge "stop"\nrocks = game:group()\nscore = 0\nlabel = game:text("Score: 0", 200, 20)\n\nfunc drop():\n    rock = game:circle(random(10, 390), 0, 10, "gray")\n    rock:speed(0, 150)\n    rocks:add(rock)\n\nfunc tick():\n    score += 1\n    label:set "Score: " + score\n\nfunc start():\n    rocks:clear()\n    score = 0\n    label:set "Score: 0"\n\ngame:every(1, drop)\ngame:every(1, tick)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-250 * dt, 0)\n    if game:held("right"):\n        player:move(250 * dt, 0)\n    if player:touches(rocks):\n        game:game_over("Score: " + score, start)\n',
      check: (src) => {
        if (!/:every\b/.test(src)) return 'Drop rocks with a timer: game:every(1, drop)';
        if (!/:game_over\b/.test(src)) return 'End the game with: game:game_over("Hit!", start)';
        if (!/\bscore\s*(\+=|=\s*score\s*\+)/.test(src)) return 'Count the seconds: write func tick() that does score += 1, and run it with game:every(1, tick)';
        return /:game_over\b[^)\n]*\bscore\b/.test(src) ? true : 'Put the score in the message: game:game_over("Score: " + score, start)';
      },
    },
    {
      id: 'tgame-3d',
      title: 'A 3D world',
      body: `<p><code>tgame.world("Title")</code> makes a 3D world instead of a flat window. <code>game:sky "sunset"</code> picks the sky, and <code>game:island(60)</code> makes ground to stand on.</p>
             <p><code>game:player("first person")</code> lets you walk around: <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> walk, <kbd>Space</kbd> jumps, and clicking the game lets you look around with the mouse. <code>game:spawn("tree")</code> puts a ready-made tree somewhere random. There are also pine, rock, bush, flower, house, hut, sign, crate, fence and coin.</p>
             <p>In 3D, y is how high something is. x and z go along the ground.</p>`,
      example: 'mention tgame\n\ngame = tgame.world("My World")\ngame:sky "sunset"\ngame:island(60)\nplayer = game:player("first person")\nfor i in range(1, 10):\n    game:spawn("pine")\ngame:spawn("house", 0, 0, -12)\n\nwhile game:open():\n    game:frame()',
      task: 'Make your own world: pick a sky, add an island and a player, and spawn at least two kinds of things, like trees and rocks.',
      starter: '# Section 4, Lesson 6: A 3D world\n# Pick a sky, add an island and a player,\n# and spawn at least two kinds of things.\n\nmention tgame\n\n',
      solution: 'mention tgame\n\ngame = tgame.world("Forest")\ngame:sky "day"\ngame:island(80)\nplayer = game:player("third person")\nfor i in range(1, 12):\n    game:spawn("tree")\nfor i in range(1, 6):\n    game:spawn("rock")\ngame:spawn("hut", 5, 0, -8)\n\nwhile game:open():\n    game:frame()\n',
      check: (src) => {
        if (!/tgame\.world\s*\(/.test(src)) return 'Make a 3D world with: game = tgame.world("My World")';
        if (!/:sky\b/.test(src)) return 'Pick a sky, like: game:sky "sunset"';
        if (!/:(island|ground)\b/.test(src)) return 'Give it ground to stand on: game:island(60)';
        if (!/:player\b/.test(src)) return 'Add a player: player = game:player("first person")';
        const kinds = new Set([...src.matchAll(/:spawn\s*\(?\s*["'](\w+)["']/g)].map((m) => m[1]));
        return kinds.size >= 2 ? true : 'Spawn at least two kinds of things, like game:spawn("tree") and game:spawn("rock")';
      },
    },
    {
      id: 'tgame-coins',
      title: 'Collect the coins',
      body: `<p>Things in a 3D world can be clicked. <code>coin:clicked grab</code> runs <code>grab</code>, and it gets the thing that was clicked. Once you've clicked the game to look around, the mouse pointer is hidden, so a click picks whatever is under the dot in the middle of the view.</p>
             <p><code>coin:distance(player)</code> says how far away something is, so people have to walk up to it first. <code>game:hud()</code> is a flat layer on top of the world, for things like the score.</p>`,
      example: 'mention tgame\n\ngame = tgame.world("Lumberjack")\ngame:island(60)\nplayer = game:player("first person")\naxe = player:hold("axe")\nlogs = 0\nlabel = game:hud():text("Logs: 0", 90, 30)\n\nfunc chop(tree):\n    axe:swing()\n    if tree:distance(player) < 4 and not tree:fallen():\n        tree:fall()\n        tree:regrow(5)\n        logs += 1\n        label:set "Logs: " + logs\n\nfor i in range(1, 15):\n    tree = game:spawn("tree")\n    tree:clicked chop\n\nwhile game:open():\n    game:frame()',
      task: 'Spawn 10 coins. Clicking a coin that\'s close removes it, adds 1 to a coin counter on the HUD and plays the coin sound.',
      starter: '# Section 4, Lesson 7: Collect the coins\n# Spawn 10 coins. Clicking a coin that is close removes it,\n# adds 1 to a counter on the HUD and plays the coin sound.\n\nmention tgame\n\ngame = tgame.world("Coin hunt")\ngame:island(60)\nplayer = game:player("first person")\n\nwhile game:open():\n    game:frame()\n',
      solution: 'mention tgame\n\ngame = tgame.world("Coin hunt")\ngame:sky "day"\ngame:island(60)\nplayer = game:player("first person")\ncoins = 0\nlabel = game:hud():text("Coins: 0", 90, 30)\n\nfunc grab(coin):\n    if coin:distance(player) < 5:\n        coin:remove()\n        coins += 1\n        label:set "Coins: " + coins\n        game:sound "coin"\n\nfor i in range(1, 10):\n    coin = game:spawn("coin")\n    coin:clicked grab\n\nwhile game:open():\n    game:frame()\n',
      check: (src) => {
        if (!/:spawn\s*\(?\s*["']coin["']/.test(src)) return 'Make coins with: coin = game:spawn("coin")';
        if (!/:clicked\b/.test(src)) return 'Run a function when a coin is clicked: coin:clicked grab';
        if (!/:remove\b|:hide\b/.test(src)) return 'Take the coin away with: coin:remove()';
        if (!/:hud\b/.test(src)) return 'Show the count on the HUD: label = game:hud():text("Coins: 0", 90, 30)';
        return /\+=|\b(\w+)\s*=\s*\1\s*\+/.test(src) ? true : 'Count the coins with: coins += 1';
      },
    },
    {
      id: 'tgame-engine',
      title: 'Tuff Engine',
      engine: true,
      body: `<p><b>Tuff Engine</b> is a tab where you build a game by clicking and dragging. Everything you do there is written into your file as normal Tuff code, and code you type shows up in Tuff Engine too.</p>
             <p>Open it with the gamepad button on the left or <kbd>Ctrl+Shift+G</kbd>. Click something in <b>Add</b> to put it in your game, drag it where you want it, and change it on the right. <kbd>Ctrl+Z</kbd> undoes. <b>Play</b> runs the real game.</p>`,
      example: '# 1. Start the lesson, then click "Open Tuff Engine"\n# 2. In Add, click Player, then Coin, then Enemy\n# 3. Drag the coin somewhere new\n# 4. Click Play, collect the coin, then close the game window',
      task: 'In Tuff Engine, add a <b>Player</b>, a <b>Coin</b> and an <b>Enemy</b>, then press <b>Play</b>. Collect the coin, then close the game window.',
      starter: '# Section 4, Lesson 8: Tuff Engine\n# Open Tuff Engine, add a Player, a Coin and an Enemy, then press Play.\n\nmention tgame\n\ngame = tgame.window("Coin Dash", 800, 600)\ngame:background "navy"\n',
      solution: "mention tgame\n\ngame = tgame.window(\"Coin Dash\", 800, 600)\ngame:background \"navy\"\nscore = 0\nscore_label = game:text(\"Score: 0\", 400, 30, 24, \"white\")\nplayer = game:box(400, 520, 50, 50, \"lime\")\nplayer:on_edge \"stop\"\ncoin = game:circle(200, 200, 14, \"gold\")\nenemy = game:box(100, 80, 40, 40, \"red\")\nball = game:circle(600, 300, 12, \"white\")\nball:speed(200, 150)\nball:on_edge \"bounce\"\n\ngame:every_frame player_arrows\ngame:every_frame coin_collect\ngame:every_frame enemy_chase\ngame:every_frame enemy_hurts\n\n# Tuff Engine: player moves with the arrow keys\nfunc player_arrows(dt):\n    if game:held(\"left\"):\n        player:move(-300 * dt, 0)\n    if game:held(\"right\"):\n        player:move(300 * dt, 0)\n    if game:held(\"up\"):\n        player:move(0, -300 * dt)\n    if game:held(\"down\"):\n        player:move(0, 300 * dt)\n\n# Tuff Engine: player collects coin\nfunc coin_collect(dt):\n    if coin:touches(player):\n        score += 1\n        score_label:set \"Score: \" + score\n        game:sound \"coin\"\n        coin:move_to(game:random_spot())\n\n# Tuff Engine: enemy chases player\nfunc enemy_chase(dt):\n    enemy:point_at(player)\n    enemy:forward(120 * dt)\n\n# Tuff Engine: game over when enemy touches player\nfunc enemy_hurts(dt):\n    if enemy:touches(player) and not game:paused():\n        game:sound \"lose\"\n        game:game_over(\"Score: \" + score, play_again)\n\n# Tuff Engine: play again after a game over\nfunc play_again():\n    score = 0\n    score_label:set \"Score: 0\"\n    player:move_to(400, 520)\n    coin:move_to(200, 200)\n    enemy:move_to(100, 80)\n",
      check: (src) => {
        if (!/:held\b/.test(src)) return 'Add a Player from the Add list in Tuff Engine: it moves with the arrow keys.';
        // Collect it is what adds to the score (an enemy's Game over has :touches too). A coin or an enemy that's there
        // without its behaviour (taken off in the Inspector) gets told how to give it back, not to add another one.
        if (!/\bscore\s*\+=/.test(src)) return /^coin\w*\s*=\s*\w+:circle\b/m.test(src) ? 'Select your coin in Tuff Engine and pick "+ Add behaviour…", then "Collect it".' : 'Add a Coin: it comes with "Collect it".';
        if (!/:game_over\b/.test(src)) return /^enemy\w*\s*=\s*\w+:box\b/m.test(src) ? 'Select your enemy in Tuff Engine and pick "+ Add behaviour…", then "Game over when it touches…".' : 'Add an Enemy too: it chases the player.';
        return /\bwait\s*\(/.test(src) ? 'Take out wait(): it freezes a game.' : true;
      },
    },
    {
      id: 'tgame-own',
      title: 'Make your own game',
      body: `<p>You know enough to make a real game! Pick an idea: catch things, dodge things, collect coins, a race or a 3D treasure hunt.</p>
             <p>Build it one step at a time, and run it after each one. First something you can move, then something to catch or dodge, then a score, and last a <code>game_over</code> so people can play again. Here's a whole game made that way.</p>`,
      example: 'mention tgame\n\ngame = tgame.window("Star catcher", 600, 400)\ngame:background "#14213d"\nbasket = game:box(300, 370, 90, 20, "gold")\nbasket:on_edge "stop"\nstar = game:circle(300, 0, 12, "yellow")\nscore = 0\nlives = 3\nlabel = game:text("Score: 0   Lives: 3", 300, 24, 22, "white")\n\nfunc show():\n    label:set "Score: " + score + "   Lives: " + lives\n\nfunc start():\n    score = 0\n    lives = 3\n    star:move_to(300, 0)\n    show()\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        basket:move(-450 * dt, 0)\n    if game:held("right"):\n        basket:move(450 * dt, 0)\n    star:move(0, (200 + score * 20) * dt)\n    if star:touches(basket):\n        score += 1\n        game:sound "coin"\n        star:move_to(random(20, 580), 0)\n        show()\n    elif star:y() > 400:\n        lives -= 1\n        game:sound "hit"\n        star:move_to(random(20, 580), 0)\n        show()\n        if lives is 0:\n            game:game_over("Stars caught: " + score, start)',
      task: 'Make your own game. It needs something the player controls, something to catch or dodge, a score, and a game over that lets you play again.',
      starter: '# Section 4, Lesson 9: Make your own game\n# Your game needs:\n#   1. something the player controls (game:held or :clicked)\n#   2. something to catch or dodge (:touches)\n#   3. a score (score += 1)\n#   4. a game over that lets you play again (game:game_over)\n\nmention tgame\n\ngame = tgame.window("My Game", 600, 400)\n\nwhile game:open():\n    dt = game:frame()\n',
      solution: 'mention tgame\n\ngame = tgame.window("Coin dash", 600, 400)\ngame:background "#1b1b2f"\nplayer = game:box(300, 200, 30, 30, "lime")\nplayer:on_edge "stop"\ncoin = game:circle(100, 100, 12, "gold")\nbomb = game:circle(500, 300, 18, "red")\nbomb:speed(180, 140)\nbomb:on_edge "bounce"\nscore = 0\nlabel = game:text("Coins: 0", 300, 24, 22, "white")\n\nfunc start():\n    score = 0\n    label:set "Coins: 0"\n    player:move_to(300, 200)\n    bomb:move_to(500, 300)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n    if game:held("right"):\n        player:move(300 * dt, 0)\n    if game:held("up"):\n        player:move(0, -300 * dt)\n    if game:held("down"):\n        player:move(0, 300 * dt)\n    if player:touches(coin):\n        score += 1\n        label:set "Coins: " + score\n        game:sound "coin"\n        coin:move_to(game:random_spot())\n        while coin:touches(player):\n            coin:move_to(game:random_spot())\n    if player:touches(bomb) and not game:paused():\n        game:sound "boom"\n        game:game_over("Coins collected: " + score, start)\n',
      check: (src) => {
        if (!/tgame\.(window|world)\s*\(/.test(src)) return 'Start with a window: game = tgame.window("My Game", 600, 400)';
        if (!/:(held|pressed|on_key|clicked|player)\b/.test(src)) return 'Give the player something to control, like: if game:held("left"):';
        if (!/:(touches|clicked)\b/.test(src)) return 'Add something to catch or dodge, and check for it with :touches';
        if (!/\+=|\b(\w+)\s*=\s*\1\s*\+/.test(src)) return 'Keep a score: score += 1';
        return /:game_over\b/.test(src) ? true : 'End with game:game_over("Score: " + score, start), so people can play again.';
      },
    },
  ];

  BASICS.forEach((l) => { l.section = 'basics'; });
  TGUI.forEach((l) => { l.section = 'tgui'; });
  MTGUI.forEach((l) => { l.section = 'mtgui'; });
  ATGUI.forEach((l) => { l.section = 'atgui'; });
  TAP.forEach((l) => { l.section = 'tap'; });
  TGAME.forEach((l) => { l.section = 'tgame'; });
  const SECTIONS = [
    { id: 'basics', title: 'Basics', lessons: BASICS, prefix: '' },
    { id: 'tgui', title: 'Section 2 · Build apps', optional: true, lessons: TGUI, prefix: 'tgui-' },
    { id: 'mtgui', title: 'Section 2.1 · Modern apps', optional: true, lessons: MTGUI, prefix: 'mtgui-' },
    { id: 'atgui', title: 'Section 2.2 · Advanced apps', optional: true, lessons: ATGUI, prefix: 'atgui-' },
    { id: 'tap', title: 'Section 3 · The internet', optional: true, lessons: TAP, prefix: 'tap-' },
    { id: 'tgame', title: 'Section 4 · Games', optional: true, lessons: TGAME, prefix: 'tgame-' },
  ];
  const LESSONS = SECTIONS.flatMap((s) => s.lessons);

  let ide = null;
  let done = new Set();
  let current = BASICS[0].id;
  let openSections = new Set(['basics']);
  const status = {};

  const sectionOf = (l) => SECTIONS.find((s) => s.id === l.section);
  const numberOf = (l) => sectionOf(l).lessons.indexOf(l) + 1;
  const lessonDir = () => ide.join(ide.root(), 'lessons');
  // lessons/<prefix><number>-<id without the prefix>.tuf: "06-loops.tuf", "mtgui-01-window.tuf", "tgame-02-keys.tuf".
  const fileName = (l) => {
    const { prefix } = sectionOf(l);
    return `${prefix}${String(numberOf(l)).padStart(2, '0')}-${prefix && l.id.startsWith(prefix) ? l.id.slice(prefix.length) : l.id}.tuf`;
  };
  const lessonPath = (l) => ide.join(lessonDir(), fileName(l));
  // "the basics", "Section 2.1"
  const sectionName = (sec) => (sec.id === 'basics' ? 'the basics' : sec.title.split(' · ')[0]);
  const byId = (id) => LESSONS.find((l) => l.id === id);
  const CHECK_SVG = '<svg viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7"/></svg>';

  function save() {
    ide.saveSettings({ learnDone: [...done], learnCurrent: current, learnOpen: [...openSections] });
  }

  async function complete(l) {
    const first = !done.has(l.id);
    done.add(l.id);
    const sec = sectionOf(l);
    const last = numberOf(l) === sec.lessons.length;
    status[l.id] = { pass: true, msg: last ? `Nice! That was the last lesson in ${sectionName(sec)}.` : 'Nice! Lesson complete.' };
    current = l.id;
    openSections.add(l.section);
    save();
    render();
    if (first) {
      celebrate();
      ide.toast(`${sec.id === 'basics' ? '' : `${sectionName(sec)} · `}Lesson ${numberOf(l)} complete: ${l.title}`, 'ok');
    }
  }

  async function ensureLessonFile(l) {
    if (!(await api.fs.exists(lessonDir()))) await api.fs.createDir(lessonDir());
    const p = lessonPath(l);
    if (!(await api.fs.exists(p))) {
      await api.fs.writeFile(p, l.starter);
      await ide.refreshTree();
    }
    return p;
  }

  async function openLesson(l) {
    await ide.openFile(await ensureLessonFile(l));
  }

  async function runLesson(l) {
    const p = await ensureLessonFile(l);
    await ide.openFile(p);
    ide.runFile(p);
  }

  function banner(html) {
    const el = document.createElement('div');
    el.className = 'learn-finished';
    el.innerHTML = html;
    return el;
  }

  function goTo(l) {
    current = l.id;
    openSections.add(l.section);
    save();
    render();
    if (!l.build) openLesson(l);
  }

  async function openBuildForLesson() {
    let target = null;
    for (const l of [...TGUI].reverse()) {
      if (!l.build && (await api.fs.exists(lessonPath(l)))) { target = lessonPath(l); break; }
    }
    ide.openBuild(target || undefined);
  }

  function renderLesson(l, body) {
    const open = l.id === current;
    const sec = sectionOf(l);
    const n = numberOf(l);
    const wrap = document.createElement('div');
    wrap.className = 'lesson' + (open ? ' open' : '') + (done.has(l.id) ? ' done' : '');
    wrap.innerHTML = `<button class="lesson-head"><span class="lnum">${done.has(l.id) ? CHECK_SVG : n}</span><span class="lesson-title">${l.title}</span></button>`;
    wrap.querySelector('.lesson-head').onclick = () => {
      current = open ? null : l.id;
      save();
      render();
    };
    if (open) {
      const st = status[l.id];
      const nextLesson = sec.lessons[n];
      const c = document.createElement('div');
      c.className = 'lesson-content';
      const actions = l.build
        ? '<button class="btn sm primary" data-act="build">Open the Build window</button>'
        : `<button class="btn sm primary" data-act="open">${done.has(l.id) ? 'Open lesson file' : 'Start lesson'}</button>
           ${l.studio ? '<button class="btn sm" data-act="studio">Open Design Studio</button>' : ''}
           ${l.engine ? '<button class="btn sm" data-act="engine">Open Tuff Engine</button>' : ''}
           <button class="btn sm run" data-act="run"><svg viewBox="0 0 16 16"><path d="M5 3.6c0-.8.9-1.3 1.6-.85l6.2 4.1c.6.4.6 1.3 0 1.7l-6.2 4.1C5.9 13.1 5 12.6 5 11.8z"/></svg>Run</button>`;
      const nextSection = SECTIONS[SECTIONS.indexOf(sec) + 1];
      const next = done.has(l.id) && nextLesson ? '<button class="btn sm" data-act="next">Next lesson</button>'
        : done.has(l.id) && nextSection ? `<button class="btn sm" data-act="nextsection">Try ${nextSection.title.split(' · ')[0]}</button>` : '';
      c.innerHTML = `
        ${l.body}
        <pre class="lx-code"></pre>
        <div class="lx-task"><div class="lbl">YOUR TASK</div>${l.task}</div>
        <div class="lx-actions">${actions}${next}</div>
        ${st ? `<div class="lx-status ${st.pass ? 'pass' : 'fail'}">${st.pass ? CHECK_SVG : '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/><path d="M8 5v3.5M8 11h.01"/></svg>'}<span></span></div>` : ''}`;
      c.querySelector('.lx-code').textContent = l.example;
      if (st) c.querySelector('.lx-status span').textContent = st.msg;
      c.querySelector('[data-act="open"]')?.addEventListener('click', () => openLesson(l));
      c.querySelector('[data-act="run"]')?.addEventListener('click', () => runLesson(l));
      c.querySelector('[data-act="build"]')?.addEventListener('click', openBuildForLesson);
      c.querySelector('[data-act="next"]')?.addEventListener('click', () => goTo(nextLesson));
      c.querySelector('[data-act="nextsection"]')?.addEventListener('click', () => goTo(nextSection.lessons[0]));
      c.querySelector('[data-act="studio"]')?.addEventListener('click', async () => ide.openStudio(await ensureLessonFile(l)));
      c.querySelector('[data-act="engine"]')?.addEventListener('click', async () => ide.openEngine(await ensureLessonFile(l)));
      wrap.appendChild(c);
      colorize(c.querySelector('.lx-code'), l.example);
    }
    body.appendChild(wrap);
  }

  function render() {
    const total = LESSONS.length;
    $('#lp-fill').style.width = `${(done.size / total) * 100}%`;
    $('#lp-text').textContent = `${done.size} / ${total}`;
    const body = $('#learn-body');
    body.innerHTML = '';
    const basicsDone = BASICS.every((l) => done.has(l.id));
    if (done.size === total) {
      body.appendChild(banner('<b>You finished Learn Tuff.</b><span>You can build programs, apps, games and .exe files, and use the internet. Go make something of your own.</span>'));
    } else if (basicsDone) {
      body.appendChild(banner('<b>You finished the basics.</b><span>The other sections are optional. They show you how to build real apps, use the internet and make games.</span>'));
    }
    for (const sec of SECTIONS) {
      const count = sec.lessons.filter((l) => done.has(l.id)).length;
      const isOpen = openSections.has(sec.id);
      const head = document.createElement('button');
      head.className = 'learn-section' + (isOpen ? ' open' : '');
      head.innerHTML = `<svg class="ls-chev" viewBox="0 0 16 16"><path d="M6 4l4 4-4 4"/></svg><span class="ls-title">${sec.title}</span>${sec.optional ? '<span class="ls-tag">Optional</span>' : ''}<span class="ls-count">${count} / ${sec.lessons.length}</span>`;
      head.onclick = () => {
        if (isOpen) openSections.delete(sec.id);
        else openSections.add(sec.id);
        save();
        render();
      };
      body.appendChild(head);
      if (isOpen) for (const l of sec.lessons) renderLesson(l, body);
    }
  }

  async function colorize(el, code) {
    const monaco = await ide.monacoReady();
    el.innerHTML = await monaco.editor.colorize(code, 'tuff', { tabSize: 4 });
  }

  function celebrate() {
    const host = document.querySelector('.lesson.open .lnum');
    if (!host) return;
    const r = host.getBoundingClientRect();
    const colors = ['var(--accent)', 'var(--accent-2)', '#5fb865', '#e5c07b', '#fff'];
    for (let i = 0; i < 26; i++) {
      const s = document.createElement('span');
      s.className = 'confetti';
      const ang = Math.random() * Math.PI * 2;
      const dist = 40 + Math.random() * 70;
      s.style.left = `${r.left + r.width / 2}px`;
      s.style.top = `${r.top + r.height / 2}px`;
      s.style.background = colors[i % colors.length];
      s.style.setProperty('--dx', `${Math.cos(ang) * dist}px`);
      s.style.setProperty('--dy', `${Math.sin(ang) * dist - 30}px`);
      s.style.setProperty('--rot', `${Math.random() * 720 - 360}deg`);
      document.body.appendChild(s);
      setTimeout(() => s.remove(), 1000);
    }
  }

  window.addEventListener('tuff:run-finished', async (e) => {
    if (!ide) return;
    const { file, code, output } = e.detail;
    const l = LESSONS.find((x) => !x.build && file && file.toLowerCase() === lessonPath(x).toLowerCase());
    if (!l) return;
    if (code !== 0) {
      status[l.id] = { pass: false, msg: 'Your program hit an error. Click the red message in the Run window to jump to it.' };
    } else {
      const result = l.check(withoutComments(await api.fs.readFile(file)), output);
      if (result === true) return complete(l);
      status[l.id] = { pass: false, msg: result };
    }
    current = l.id;
    openSections.add(l.section);
    render();
  });

  window.addEventListener('tuff:build-finished', (e) => {
    if (ide && e.detail.ok) complete(TGUI.find((l) => l.build));
  });

  window.TuffLearn = {
    init(ideApi) {
      ide = ideApi;
      const s = ide.settings();
      done = new Set((s.learnDone || []).filter(byId));
      current = s.learnCurrent === null ? null : byId(s.learnCurrent) ? s.learnCurrent : BASICS[0].id;
      openSections = new Set(s.learnOpen || ['basics']);
      if (current) openSections.add(byId(current).section);
      render();
    },
    // For the tests (test/e2e/suites/learn-sections.mjs): the sections in order with their lessons, and a
    // lesson's own check (true, or the hint it would show).
    sections: () => SECTIONS.map((s) => ({
      id: s.id, title: s.title, optional: !!s.optional,
      lessons: s.lessons.map((l) => ({ id: l.id, title: l.title, file: fileName(l), body: l.body, example: l.example, starter: l.starter, solution: l.solution ?? null })),
    })),
    check: (id, src, out = '') => byId(id).check(withoutComments(src), out),
  };
})();
