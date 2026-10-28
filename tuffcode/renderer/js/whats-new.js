// What's New: after an update, the first time TuffCode opens it shows "Here's what's changed!" with that version's
// notes, once. Help > What's New shows it again. Each version's notes live here (not fetched, so it works offline);
// its pictures go in renderer/whats-new/<version>/ and show at the top, with rounded corners.
(() => {
  const NOTES = {
    '1.3.0': {
      images: ['1.png'],
      notes: `### Play together
- **Games can be multiplayer now!** Everyone on the same Wi-Fi can play in one game together: one computer hosts a room, and the others join it.
- **Host a room:** \`world:host("Tag")\` makes a room called Tag. The top of the window says it's hosting, and the computer's address.
- **Join a room:** \`world:join()\` finds a room on your network and goes in by itself. \`world:join("Tag")\` looks for that room, and \`world:join("192.168.1.20")\` goes straight to a friend's computer.
- **Leave:** \`world:leave()\` leaves the room. When the host leaves, the room closes for everyone.

### See each other
- **Other players show up in your world** as people with their names over their heads. They walk where they walk, jump when they jump, and each has their own shirt color.
- **Find them in your code:** \`world:others()\` is a list of the other players. Use \`me:distance(p)\` or \`me:touches(p)\` for a game of tag, and \`p:get("name")\` for their name.
- **Names:** \`world:my_name("Sam")\` picks the name everyone sees. Without one, you're "Player 1", "Player 2" and so on.
- **Who's playing:** \`world:players()\` lists everyone's names. \`world:on_join(hello)\` runs when someone comes in, and \`world:on_leave(bye)\` when they go.

### Send messages
- **Tell everyone something:** \`world:send("score", 10)\` sends a message, with a number, some text, a list or a table.
- **Hear it:** \`world:on_message(got)\` runs \`got(message, value, sender)\` each time a message arrives, so you know what it says and who sent it.
- **2D games too:** send where your sprite is, \`game:send("at", [me:x(), me:y()])\`, and move a sprite for your friend when it arrives.

### Share values
- **One value everyone sees:** \`world:share("coins", 5)\` sets it, and \`world:shared("coins", 0)\` reads it on every computer. The host keeps it, so players who join late see it too.
- **Only one host:** \`world:hosting()\` is true on the computer that hosts, for things only one game should do, like starting the timer or placing the coins.

### Try it on your own
- **A second player on one computer:** in a game that hosts or joins, a two-people button shows next to Run. It runs a second player, another copy of your game, so you can host in one window and join in the other. The Run panel marks each line P1 or P2.

### Get in the car
- **Press F to get in:** walk up to a car and "F: Get in" shows. F gets in and you drive with WASD or the arrow keys, and F again gets out beside the door. Nothing drives off by itself when the game starts.
- **Start in it:** \`car:drive()\` starts the game with the player in the car. \`car:on_enter(got_in)\` and \`car:on_exit(got_out)\` run when you get in and out.

### Things have weight
- **Everything weighs what it is:** a crate 25 kg, a person 70, a rock 300, a car 1200. Walk into a crate and it slides away; walk into a big rock and it doesn't budge.
- **Change it:** \`crate:weight(80)\`, and \`crate:weight()\` tells you. A heavy thing moves less when it's pushed and hits harder.
- **Physics on anything:** cones, planes, people, signs, every model, and in 2D boxes, circles, lines, text and pictures. Tuff Engine has a Physics section for all of them.

### Signs and people
- **Real words on signs:** \`sign:label("Shop")\` writes on the sign's board, on both sides, instead of floating over it.
- **Dress people up:** \`npc:shirt("red")\`, \`npc:hair("curly", "blonde")\`, \`npc:pants\`, \`npc:skin\`, \`npc:shoes\` and \`npc:sleeves("short")\`. Ragdolls and the player in third person too.

### Tuff Engine
- **A bigger Add panel** where every name fits (drag its edge to make it wider), and **real pictures** of everything you can add, drawn by the game engine.
- **Clothes and hair** for people and ragdolls, **Weight** for physics things, and **Sign text** for signs, right in the Inspector.

### Good to know
- The first time a computer hosts, Windows may ask if TuffCode can use the network. Click **Allow**.
- **Weights changed:** a 1 m box weighed 1 kg in 1.2.0 and weighs 50 kg now. Boxes and balls move just as before, but if your game sets \`:mass\`, use about 50 times the number.
- A game that uses F for itself (\`world:on_key("f", ...)\`) keeps it, and gets in cars with \`car:drive()\`.
- Games you build with Build exe can host and join too, so you can share your game and play it together.
- Claude, Codex, Antigravity and Pumice 1 know all of it, and the checker catches mistakes like a message that isn't text.`,
    },
    '1.2.0': {
      images: ['1.png'],
      notes: `### Real physics in games
- **Things fall, bounce, tumble and get pushed.** \`crate:physics()\` turns it on, with Rapier, a real physics engine. Tune it with \`crate:mass(2)\`, \`crate:bounce(0.6)\` and \`crate:friction(0.4)\`.
- **Kick things around:** \`push\`, \`spin\` and \`velocity\`, or \`world:explode(x, y, z, strength, radius)\` to blast things apart.
- **Know when things hit:** \`crate:on_hit(bumped)\` runs \`bumped(other, strength)\`.
- **Drive a car:** \`car = world:car(0, 1, 10, "red")\`, then \`car:drive()\`: WASD or the arrow keys, with a chase camera.
- **Ragdolls:** \`world:ragdoll(5, 0, 0, "blue")\` is a person that flops when it's pushed or hit.
- **The player pushes crates and can stand on them.** 2D games get physics too: \`game:gravity(900)\` and \`game:walls(true)\`.

### Better models and animation
- The 3D kit has more detail, softer shapes and nicer materials, plus new \`"person"\` and \`"chest"\` models.
- Characters walk with swinging arms and legs and breathe while standing. Trees sway, water ripples, coins spin.

### Juice
- **Slow motion:** \`world:slow_mo(0.3, 2)\` runs everything at 30% for 2 seconds, then eases back. Perfect for a big win.
- **Screen shake:** \`world:shake(0.5)\` shakes the camera for a moment. Try it when something explodes.
- **Floating text:** \`world:pop_text("+10", x, y, z)\` floats up and fades, like points over a coin. 2D games get all three too.
- **Rain and snow:** \`world:weather("rain")\` brings falling streaks, a darker sky and wet ground; \`"snow"\` brings drifting flakes.
- **Day and night:** \`world:day_cycle(120)\` goes from morning to sunset to a starry night and back. \`world:time_of_day(18)\` jumps to 6 pm.

### Splash screens, menus and the mouse
- **Splash screens:** \`game:splash("logo.png", 3)\` shows your logo or some text as the game starts. \`game:splash()\` shows "Made with Tuff".
- **Main menus:** \`menu = game:main_menu("My Game")\` waits for Play, and the mouse stays free to click its buttons.
- **Mouse controls:** \`world:unlock_mouse()\` frees the mouse in a first-person game (to read a note or use a shop), and \`world:lock_mouse()\` locks it again. \`world:mouse_locked()\` tells you which it is.
- **No more "press Esc to show your cursor" banner** over your game. Games hold the mouse themselves now.

### Saving
- **Saved games:** \`game:save("best", score)\` keeps a high score, progress or settings for next time, even after the game closes. \`game:load("best", 0)\` gets it back, and \`game:forget("best")\` forgets it.

### On the screen
- **Health bars:** \`enemy:health_bar(100)\`, then \`enemy:hurt(10)\` and \`enemy:heal(5)\`. \`enemy:on_death(gone)\` runs when it reaches 0.
- **A countdown:** \`game:countdown(60, times_up)\` ticks down in the corner and turns red at the end.
- **An arrow to anything:** \`world:arrow_to(chest)\` points the way at the edge of the screen and says how far it is.
- **A minimap:** \`world:minimap()\` shows the land and where you are. \`map:mark(coin, "gold")\` adds a dot.

### Interaction
- **Pick things up:** \`player:can_grab()\` lets E pick up the thing you look at. Click to throw it!
- **People who talk:** \`npc:say("Hi!")\` shows a speech bubble, and \`npc:on_talk(talk)\` runs when you walk up and press E.
- **Doors and keys:** \`world:door(0, 0, -5)\` swings open when you walk into it. \`door:needs(key)\` locks it until you find the new \`"key"\`.

### Level pieces
- **Jump pads and boost pads:** \`world:jump_pad(0, 0, 5, 15)\` launches you up, and \`world:boost_pad(0, 0, 10, 20)\` shoots you forward.
- **Moving platforms:** \`lift:path([[0, 2, 0], [10, 2, 0]], 3)\` moves anything along the spots, and you ride it.

### Tuff Engine and AIs
- A **Physics** section in the Inspector (Off, Falls or Fixed, with Mass, Bounce and Friction), and **Car** and **Ragdoll** tiles in Add.
- **Level pieces** in Add: Door, Key, Jump pad, Boost pad, Moving platform and Talking person.
- Claude, Codex, Antigravity and Pumice 1 know all of it, and the checker catches mistakes.`,
    },
  };
  // 1.3.1 is 1.3.0 with new icons. Most copies go straight from 1.2.0 to 1.3.1 and only see 1.3.1's notes, so they're
  // the new look and then all of 1.3.0's.
  NOTES['1.3.1'] = {
    images: ['1.png'],
    notes: `### A new look
- **New icons everywhere:** buttons, tabs, files, menus, Tuff Engine and every plugin have fresh, friendly icons. They're MingCute, a free icon set by the MingCute Design team.

If you already had 1.3.0, the icons are what's new. Everything else here came in 1.3.0, the Multiplayer Update.

${NOTES['1.3.0'].notes}`,
  };
  NOTES['1.3.5'] = {
    images: ['1.png'],
    notes: `### Colours in the Run window
- **Coloured lines:** \`say:color("Game over!", "red")\`. Any colour name, or a code like \`"#ff8800"\`.
- **A bar behind the line:** a second colour, like \`say:color("LEVEL UP!", "black", "lime")\`. \`bold\`, \`dim\`, \`italic\` and \`underline\` work too.
- **Rainbow:** \`say:color("WINNER", "rainbow")\` gives every letter its own colour, and the colours keep flowing.
- **A pen for everything:** \`print:pen("cyan")\` styles every line after it, until \`print:pen()\`.

### Big letters
- \`say:ascii("GAME OVER")\` writes in big block letters, with six fonts: \`block\`, \`wide\`, \`small\`, \`shadow\`, \`led\` and \`hash\`.
- Colours, bars and rainbow work on them too, and \`score = say:ascii(0, "gold")\` then \`score:rewrite(42)\` makes a big live scoreboard.

### Animations
- Add one to a line and it plays when it's said: \`fade\`, \`build\`, \`explode\`, \`assemble\`, \`type\`, \`glitch\`, \`drop\` and \`wave\`, like \`say:ascii("BOOM", "explode", "red")\`.
- They work in a real terminal and in Build exe console apps too.

### Drawing: tdraw
- **A new library for drawing with a pen.** \`mention tdraw\`, then \`pen = tdraw.pen()\`, \`pen:forward(100)\`, \`pen:right(90)\`.
- Shapes and fills (\`pen:circle(50, "gold")\`, \`pen:star(100)\`, \`pen:polygon(6, 40)\`), text, rainbow pens, a background colour, and \`tdraw.on_click\` for drawing with the mouse.

### Learn
- **Two new sections:** "Make it look good" (colours, big letters, animations, a scoreboard project) and "Drawing" (five lessons with tdraw).

### Good to know
- The editor checks the new words as you type: \`say:color("hi", "redd")\` asks if you meant "red".
- Claude, Codex, Antigravity and Pumice 1 know all of it.`,
  };
  // 1.4.0, the Toolbox Update (a beta for now: its picture comes later).
  // 1.5.0, The Workshop Update (being built: these notes grow with each beta).
  NOTES['1.5.0'] = {
    images: ['1.png'],
    notes: `### Text templates
- \`f"{name} has {score + 1} points"\`: any code inside { }, shown the way say shows it.
- Formats by example: \`{price:money}\` gives $12.50, \`{x:0.00}\` two decimals (rounded half up), \`{n:000}\` 007, \`{name:12}\` a width.

### Animated sprites
- \`hero:frames(4)\` cuts a sprite sheet into frames, \`hero:animation("walk", [1, 2, 3, 4], 10)\` names some, and \`hero:play("walk")\` plays them. They pause with the game, and Sprite Studio's "Use in code" writes them for you.

### Your own files
- \`import money.tuf\` loads money.tuf from the same folder (or a libs folder there). A file can have a library's name too: \`import tmusic.tuf\` is yours, \`import tmusic\` is Tuff's. Its functions and values go after a dot: \`money.as_money(6.375)\`, \`money.rate\`.
- Each file runs once, however many files import it. Mistakes name the file and line they're in.

### Kinds: your own objects
- \`kind Pet:\` with fields (\`name = "?"\`, \`hunger = 5\`) and actions (\`func feed(amount):\`). Inside an action, \`my.hunger\` is the pet's own.
- \`rex = Pet("Rex")\` fills the fields in order. Then \`rex.hunger\`, \`rex:feed(2)\`, and \`file.save\` keeps pets for next time.

### tterm: terminal games
- \`screen = tterm.screen(40, 20)\` gives a grid of letters in colours. Draw with \`screen:put(x, y, "@", "lime")\`, \`:text\` and \`:box\`, and read keys with \`screen:pressed("space")\` and \`screen:held("left")\`.
- \`screen:every_frame(step)\` runs a game about 20 times a second, in the Run panel (click it to play), a terminal or a Build exe.

### tmusic: music from notes
- \`tmusic.play("C4 E4 G4 C5*2", "piano")\` plays a tune.
- \`song = tmusic.song(120)\`, then \`song:track("chip", "C4 E4 G4 E4")\` for each instrument (piano, chip, bass, pluck, bell, organ, flute and drums). \`song:play()\`, \`song:loop()\`, \`song:save("theme.wav")\`, or a game's \`game:music(song)\`.

### Faster
- Tuff programs run several times faster: a million-step loop takes a fraction of a second. Library calls are about 5 times quicker too.
- A sum too big for a decimal (\`10 ^ 400 / 3\`) says so in plain words instead of crashing.

### The debugger
- Click beside a line number (or press F9) for a red dot, a breakpoint. Press Debug, next to Run (Shift+F9), and the program stops on that line.
- While it's stopped, Variables shows each name's value (lists, dictionaries and kinds open up) and the call stack shows which function called which. Step Over (F10), Step Into (F11), Step Out (Shift+F11) and Continue (F5) move it on.
- An error stops it on the line that went wrong, with the names as they were.
- Watch it run lights up each line as it runs, slow enough to follow, with a speed slider.
- Breakpoints stay with their lines when the whole file changes at once: Auto Code Sort (and its Undo), Replace in Files, or another program changing the file.

### New Project
- File > New Project… starts a project from a starter: Hello, Quiz, Habit Tracker, Corner Shop, Snake, Coin Collector, Music Box, Drawing, Weather or a blank one. Give it a name and it opens, ready to run.

### Learn
- A new section, 1.7 · Workshop: a lesson each for text templates, kinds, actions, your own files, music, a terminal game and animated pictures.

### Tabs
- **Drag a tab** along the top to move it. Escape while dragging puts it back. Ctrl+Shift+PgUp and Ctrl+Shift+PgDn move the tab you're on, and TuffCode reopens your tabs in that order.
- **Right-click a tab** to Run it, close the tabs to its left or right, move it, copy its path (or the part inside your project), show it in the Project view or rename it.

### Drawing
- **Change the pen's look:** \`pen:shape("arrow")\`. It takes "turtle", "arrow", "big arrow", "circle", "square" or "triangle", and a size makes it bigger: \`pen:shape("turtle", 2)\`. \`pen:hide()\` still hides it.
- After \`pen:\` the editor suggests only what a pen can do. It used to suggest everything, \`app:icon\` too. \`song:\` suggests a song's methods the same way.

### Fixes
- **Built apps keep what they save:** files from \`file.save\`, \`file.write\`, \`file.add\` and \`song:save\` go in a folder beside the app, named after it (Corner Shop files for Corner Shop), so they're still there next time. If it can't save there (in Program Files, say), it saves in a TuffApps folder in your app data. They used to vanish when the app closed.
- Build Exe works for a project whose folder has a ; in its name, and a new project's name can't have one.
- After you open another folder, Run, Rerun (Ctrl+F5), Design Studio and Build use that folder's files, not the last project's.
- On Windows and Linux, Ctrl+W and Ctrl+R in a box (New Project, Search Everywhere) no longer close or reload TuffCode.
- Learn: stopping a lesson's program (Stop, or Ctrl+F2) no longer says it hit an error.`,
  };
  // 1.4.1 fixes 1.4.0 and adds looks to input and anims.
  NOTES['1.4.1'] = {
    images: ['../1.4.0/1.png'],
    notes: `### Colour on more things
- **Questions in colour:** \`name = input:color("Name? ", "green")\` asks with the question in a look: colours, rainbow, bold and the rest.
- **Anims in colour:** look words go after an anim's usual inputs, like \`anims.loading("Pulling info...", "green")\` or \`anims.countdown(3, "Go!", "lime")\`.
- \`print:pen\` now colours input's questions and anims too.

### Fixes
- **Deep functions:** a function can call itself over 10,000 times now (it used to stop at about 100).
- atgui: \`app:closed\` always runs when the window is closed with its X, so an app can save on the way out.
- \`:play\` on a rainbow line keeps the rainbow flowing instead of jumping back to its first colours.
- tap's JSON comes back as dictionaries, so \`data["name"]\` and \`for key in data:\` work.
- Build Exe packs pictures from a parent folder (\`"../"\`), and problems inside a built app show in its error box.
- Find and Replace in Files read files saved as UTF-16.
- Learn: Basics lesson 10's check wants the number first.
- \`--check\` catches more: pictures outside a game's or app's folder (\`"../"\`), which its window can't show, and a few slips with parts and dictionary keys.

Everything from 1.4.0, the Toolbox Update, is here too: dictionaries, parts, text tools, sorting, files, try/catch and more.`,
  };
  NOTES['1.4.0'] = {
    images: ['1.png'],
    notes: `### Dictionaries
- **Keep things by name:** \`ages = {"sam": 14, "ann": 12}\`, then \`ages["sam"]\`, and \`ages["bob"] = 15\` to add one.
- \`ages:has("sam")\`, \`ages:get("zed", 0)\`, \`ages:remove("ann")\`, \`ages:keys()\` and \`ages:values()\`. \`for name in ages:\` goes through the keys.

### Text tools
- **Parts:** \`s[0:4]\`, \`s[2:]\` and \`s[-3:]\`, on text and lists. Both ends are included, like \`range\`.
- \`:split(",")\`, \`:replace("a", "b")\`, \`:starts\`, \`:ends\`, \`:find\`, \`:count\`, \`:pad_left(3, "0")\` and \`:pad_right\`. \`items:join(", ")\` puts a list back together. \`text(3.14159, 2)\` gives "3.14".

### Sorting
- \`items:sort()\`, \`items:sort(by_score)\` and \`items:reverse()\`.

### Files
- \`file.read\`, \`file.write\`, \`file.add\`, \`file.lines\`, \`file.exists\` and \`file.delete\`, in your project folder.
- \`file.save("save.json", data)\` and \`file.load("save.json", {})\` keep lists and dictionaries for next time. There's nothing to mention.

### When things go wrong
- \`try:\` then \`catch problem:\`. Something that would stop the program (a missing file, a bad web request) runs \`catch\` instead.

### Date, time and maths
- \`now()\`, \`today()\`, \`date()\` (year, month, day, weekday...) and \`time()\` for timers.
- \`sin\`, \`cos\` and \`tan\` (in degrees), \`log\`, and random decimals with \`random()\`.

### Learn
- **A new section, Toolbox:** dictionaries, text tools, sorting, files, and what to do when things go wrong.

### Also from 1.3.5 and 1.3.6
- Coloured lines and big letters (\`say:color\`, \`say:ascii\`), 8 animations, \`line:play\`, and **tdraw** for drawing with a pen.`,
  };
  // 1.3.6 adds a few things to 1.3.5. Copies coming from before 1.3.5 only see 1.3.6's notes, so they carry 1.3.5's too.
  NOTES['1.3.6'] = {
    images: ['1.png'],
    notes: `### Animate a line that's already there
- **\`line:play("explode")\`** plays an animation on a line where it is, any time after it was said. Put \`wait(3)\` before it and it plays 3 seconds later.
- **\`line:rewrite("GO!", "glitch", "lime")\`** changes the text with an animation, and can change its colour, style or font too.
- \`say\` always makes a new line, so \`title:rewrite say:ascii(...)\` used to leave two lines. Now the editor points that out and says how to animate the line that's there.

### Smoother rainbows
- Every rainbow runs on one clock, so a rewritten rainbow line carries on at the same colours, and rainbow lines flow in step.

If you already have 1.3.5, that's what's new. Everything else here came in 1.3.5, the Creativity Update.

${NOTES['1.3.5'].notes}`,
  };

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  // The little Markdown the notes use: ### headings, - bullets, **bold**, `code` and [links](https://...).
  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" data-web="$2">$1</a>');
  }
  function render(md) {
    const out = [];
    let list = false;
    for (const line of md.split('\n')) {
      const t = line.trim();
      const bullet = /^- (.*)$/.exec(t);
      if (!bullet && list) { out.push('</ul>'); list = false; }
      if (/^### /.test(t)) out.push(`<h3>${inline(t.slice(4))}</h3>`);
      else if (bullet) { if (!list) { out.push('<ul>'); list = true; } out.push(`<li>${inline(bullet[1])}</li>`); }
      else if (t) out.push(`<p>${inline(t)}</p>`);
    }
    if (list) out.push('</ul>');
    return out.join('');
  }

  let ide = null;
  let back = null; // what had the focus before it opened (it gets it back when it closes)
  const has = (version) => !!NOTES[version];

  // The pictures scroll sideways one at a time (dots under them when there's more than one).
  function hero(version, images) {
    if (!images.length) return '';
    const pics = images.map((src, i) => `<img src="whats-new/${esc(version)}/${esc(src)}" alt="" draggable="false" data-i="${i}">`).join('');
    const dots = images.length > 1 ? `<div class="wn-dots">${images.map((_, i) => `<button data-dot="${i}" aria-label="Picture ${i + 1}"${i ? '' : ' class="on"'}></button>`).join('')}</div>` : '';
    return `<div class="wn-hero"><div class="wn-strip">${pics}</div>${dots}</div>`;
  }

  function show(version) {
    const entry = NOTES[version];
    if (!entry) return false;
    if (!document.getElementById('whatsnew')) back = document.activeElement;
    close(false);
    const box = document.createElement('div');
    box.id = 'whatsnew';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-labelledby', 'wn-title');
    // Everything scrolls together (so the scrollbar runs the whole height); the bar with "Let's go" stays put. Until
    // the end is reached, a fade and "Scroll for more" say there's more below.
    box.innerHTML = `<div class="wn-card">
      <div class="wn-scroll">
        ${hero(version, entry.images)}
        <div class="wn-head"><h2 id="wn-title">Here's what's changed!</h2><span class="wn-ver">TuffCode ${esc(version)}</span></div>
        <div class="wn-body">${render(entry.notes)}</div>
        <div class="wn-end">
          <span class="wn-end-mark" aria-hidden="true"></span>
          <b>That's everything new in TuffCode ${esc(version)}.</b>
          <span>Have fun making things! Every update's notes are on <a href="https://github.com/trickortree/tuff-code/releases" data-web="https://github.com/trickortree/tuff-code/releases">GitHub</a>, and Help &gt; What's New brings this back.</span>
        </div>
        <div class="wn-fade" aria-hidden="true"></div>
      </div>
      <div class="wn-foot">
        <span class="wn-more" aria-hidden="true">Scroll for more${TuffIcon('down-line')}</span>
        <button class="btn primary" data-a="close">Let's go</button>
      </div>
    </div>`;
    document.body.appendChild(box);
    const card = box.querySelector('.wn-card');
    const scroller = box.querySelector('.wn-scroll');
    const atEnd = () => card.classList.toggle('at-end', scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 4);
    scroller.addEventListener('scroll', atEnd, { passive: true });
    new ResizeObserver(atEnd).observe(scroller);
    box.querySelectorAll('img').forEach((img) => img.addEventListener('load', atEnd));
    atEnd();
    const strip = box.querySelector('.wn-strip');
    const dots = [...box.querySelectorAll('[data-dot]')];
    strip?.addEventListener('scroll', () => {
      const i = Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth));
      dots.forEach((d, k) => d.classList.toggle('on', k === i));
    });
    dots.forEach((d) => (d.onclick = () => strip.scrollTo({ left: +d.dataset.dot * strip.clientWidth, behavior: 'smooth' })));
    // A click on the backdrop closes it. preventDefault: the mousedown would move the focus to the page right after
    // close() gave it back.
    box.addEventListener('mousedown', (e) => { if (e.target === box) { e.preventDefault(); close(); } });
    box.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-web]');
      if (a) { e.preventDefault(); ide?.openWeb?.(a.dataset.web); }
      if (e.target.closest('[data-a="close"]')) close();
    });
    document.addEventListener('keydown', onKey, true);
    requestAnimationFrame(() => { box.classList.add('in'); box.querySelector('[data-a="close"]').focus(); });
    return true;
  }

  function onKey(e) {
    const box = document.getElementById('whatsnew');
    if (!box) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
    // It's modal: Tab goes round its links and buttons, never to the IDE behind it.
    if (e.key === 'Tab') {
      const stops = [...box.querySelectorAll('a[href], button')].filter((el) => el.offsetParent);
      const i = stops.indexOf(document.activeElement);
      const next = e.shiftKey ? (i <= 0 ? stops.length - 1 : i - 1) : (i + 1) % stops.length;
      e.preventDefault();
      stops[next]?.focus();
    }
  }

  // refocus: give the focus back to what had it (or the code editor, when that's gone or it was nothing).
  function close(refocus = true) {
    document.removeEventListener('keydown', onKey, true);
    const box = document.getElementById('whatsnew');
    if (!box) return;
    box.remove();
    if (!refocus) return;
    const to = back;
    back = null;
    if (to && to !== document.body && to.isConnected) to.focus();
    if (!document.activeElement || document.activeElement === document.body) ide?.focusEditor?.();
  }

  window.TuffWhatsNew = {
    init(api) { ide = api; },
    has,
    show,
    close,
    // After an update (not a first install): once per version, when it has notes.
    async maybeShow(version, settings, save) {
      if (!has(version) || settings.whatsNewSeen === version) return false;
      await save({ whatsNewSeen: version });
      return show(version);
    },
  };
})();
