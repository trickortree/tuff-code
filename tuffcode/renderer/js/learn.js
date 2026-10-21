(() => {
  const api = window.tuff;
  const $ = (s) => document.querySelector(s);
  const lines = (out) => out.split('\n').map((l) => l.trim()).filter(Boolean);

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

  BASICS.forEach((l) => { l.section = 'basics'; });
  TGUI.forEach((l) => { l.section = 'tgui'; });
  MTGUI.forEach((l) => { l.section = 'mtgui'; });
  const SECTIONS = [
    { id: 'basics', title: 'Basics', lessons: BASICS, prefix: '' },
    { id: 'tgui', title: 'Section 2 · Build apps', optional: true, lessons: TGUI, prefix: 'tgui-' },
    { id: 'mtgui', title: 'Section 2.1 · Modern apps', optional: true, lessons: MTGUI, prefix: 'mtgui-' },
  ];
  const LESSONS = [...BASICS, ...TGUI, ...MTGUI];

  let ide = null;
  let done = new Set();
  let current = BASICS[0].id;
  let openSections = new Set(['basics']);
  const status = {};

  const sectionOf = (l) => SECTIONS.find((s) => s.id === l.section);
  const numberOf = (l) => sectionOf(l).lessons.indexOf(l) + 1;
  const lessonDir = () => ide.join(ide.root(), 'lessons');
  const lessonPath = (l) => ide.join(lessonDir(), `${sectionOf(l).prefix}${String(numberOf(l)).padStart(2, '0')}-${l.id.replace(/^m?tgui-/, '')}.tuf`);
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
    status[l.id] = { pass: true, msg: last ? `Nice! That was the last lesson in ${sec.id === 'basics' ? 'the basics' : 'Section 2'}.` : 'Nice! Lesson complete.' };
    current = l.id;
    openSections.add(l.section);
    save();
    render();
    if (first) {
      celebrate();
      ide.toast(`${sec.id === 'tgui' ? 'Section 2 · ' : ''}Lesson ${numberOf(l)} complete: ${l.title}`, 'ok');
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
      body.appendChild(banner('<b>You finished Learn Tuff.</b><span>You can build programs, apps and .exe files. Go make something of your own.</span>'));
    } else if (basicsDone) {
      body.appendChild(banner('<b>You finished the basics.</b><span>Section 2 is optional. It shows you how to build real apps with windows and buttons.</span>'));
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
      const result = l.check(await api.fs.readFile(file), output);
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
  };
})();
