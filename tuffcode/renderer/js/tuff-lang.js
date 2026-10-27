window.TUFF_KEYWORDS = [
  'say', 'input', 'func', 'return', 'if', 'elif', 'else', 'then', 'while', 'for', 'in',
  'break', 'continue', 'and', 'or', 'not', 'is', 'true', 'false', 'nil', 'flush', 'import', 'mention',
  'try', 'catch', // 1.4.0 (only at the start of a line with a ':' after them, so they still work as names)
];

window.TUFF_METHOD_DOCS = {
  clock: ['app:clock("analog", size)', 'A ticking clock. Use "digital" for numbers. Change the time with :set(10, 30).'],
  spinner: ['app:spinner("Loading...")', 'A spinning loading ring.'],
  checkbox: ['app:checkbox("Label", false)', 'A tick box. Read it with :value.'],
  dropdown: ['app:dropdown(["A", "B"], "A")', 'Pick one choice from a list.'],
  speed: ['thing:speed 2', 'Animation speed: 1 is normal, 2 is twice as fast, 0.5 is half speed. In tgame, sprite:speed(vx, vy) keeps a sprite moving by itself, that many pixels a second (objects take vx, vy, vz), and car:speed() gives how fast a car goes, in km/h.'],
  gradient: ['app:gradient("#00c6ff", "#7b2ff7")', 'mtgui: sets the two accent gradient colors.'],
  now: ['clock:now', 'Sets a clock back to the real time.'],
  pause: ['clock:pause', 'Stops a clock. In tgame, game:pause("Paused") stops the game and shows the message; game:resume() goes on.'],
  resume: ['clock:resume', 'Starts a paused clock again. In tgame, game:resume() carries on after :pause or :game_over.'],
  flip: ['switch:flip', 'Turns a switch or checkbox the other way.'],
  options: ['dropdown:options(["A", "B"])', 'Replaces the choices in a dropdown.'],
  start: ['spinner:start', 'Starts a spinner spinning.'],
  stop: ['spinner:stop', 'Stops a spinner. In tgame, clock:stop() stops a countdown.'],
  heading: ['app:heading "Text"', 'Big bold title text.'],
  text: ['app:text "Text"', 'Normal text. Change it later with :set. On a tap response, res:text gives back what the server sent, as text. In tgame, game:text(words, x, y, size, color) puts words on the screen; change them with :set.'],
  small: ['app:small "Text"', 'Small grey text for hints and captions.'],
  button: ['app:button("Text", clicked, "primary")', 'A button. clicked is the function to run. Styles: primary, secondary, outline, ghost, success, danger.'],
  input: ['app:input "Hint"', 'A text box. Read it with :value.'],
  toggle: ['app:toggle("Label", true)', 'An on/off switch.'],
  slider: ['app:slider(min, max, start)', 'Drag to pick a number.'],
  progress: ['app:progress(percent)', 'A progress bar from 0 to 100.'],
  image: ['app:image("pic.png", width)', 'Shows a .png or .gif from your project folder. In tgame, game:image("ship.png", x, y, width) is a sprite (.png, .jpg, .gif or .webp).'],
  divider: ['app:divider', 'A thin line between sections.'],
  space: ['app:space 20', 'Empty space.'],
  row: ['row = app:row', 'Puts the things you add to it side by side.'],
  card: ['card = app:card', 'A rounded panel to group things.'],
  page: ['home = app:page "Home"', 'A page of your app. Add things to it like a card. Only one page shows at a time, starting with the first one you make.'],
  open: ['home:open', 'Shows this page and hides the other pages. In tgame, game:open() is true until the game window is closed: while game:open():, and door:open() swings a door open.'],
  opened: ['home:opened shown', 'Runs shown each time this page opens.'],
  showing: ['home:showing', 'Gives back true if this page is the one on screen.'],
  title: ['app:title "Title"', 'Changes the window title, even while running. Works on a tgame window too.'],
  icon: ['app:icon "icon.png"', 'Changes the window icon (.png, .gif or .ico in your project folder).'],
  size: ['app:size(width, height)', 'Resizes the window. On a tap data object, data:size gives how many names it has. A tgame sprite:size(width, height) resizes a box or picture (a circle takes its radius, text its letter size); an object takes size(width, height, depth).'],
  theme: ['app:theme "light"', 'Switches between "dark" and "light".'],
  accent: ['app:accent "purple"', 'Changes the highlight color: blue, purple, pink, red, orange, yellow, green, teal or a hex code.'],
  every: ['app:every(seconds, tick)', 'Runs a function again and again, like a clock. To pause it, check a variable at the top of the function: if not running: return Works the same on a tgame window (it pauses with the game).'],
  after: ['app:after(seconds, done)', 'Runs a function once after a delay. Works the same on a tgame window.'],
  alert: ['app:alert "Message"', 'Pops up a message with an OK button.'],
  confirm: ['app:confirm "Are you sure?"', 'Pops up Yes/No and gives back true or false.'],
  ask: ['app:ask "Question?"', 'Pops up a text box and gives back what was typed.'],
  close: ['app:close', 'Closes the window. Closes a tgame window too, and door:close() shuts a tgame door.'],
  set: ['thing:set value', 'Changes the text or value: of a label, button, text box, slider, progress bar, switch or dropdown. It doesn\'t run :change (for a switch or checkbox, switch:set(true, true) does). A clock takes :set(hours, minutes, seconds); an image takes a new picture file. On a tap data object, data:set("name", value) adds or changes a value. A tgame text sprite takes new words (score:set "Score: 5"), a picture a new file, and any sprite or object keeps named values: tree:set("hp", 3).'],
  value: ['thing:value', 'Gives back the current value: the text of a label, button or text box; the chosen option of a dropdown; true or false for a switch or checkbox; a number for a slider or progress bar; "14:05:09" for a clock. A tgame text sprite gives its words.'],
  change: ['thing:change fn', 'Runs fn when the value changes: on every key typed in a text box, or when a dropdown, switch, checkbox or slider changes. If fn has an input, it gets the new value, like func moved(v):'],
  enter: ['box:enter fn', 'Runs fn when Enter is pressed in a text box. If fn has an input, it gets the text.'],
  focus: ['box:focus', 'Puts the cursor in a text box, ready for typing.'],
  click: ['button:click fn', 'Changes which function the button runs.'],
  style: ['button:style "danger"', 'Changes a button\'s style (primary, secondary, outline, ghost, success, danger), or a clock\'s style ("analog" or "digital"). In tgame, land:style "snow" changes how the land looks: grass, desert, snow, rocky or autumn.'],
  color: ['label:color "red"', 'Changes the text color: blue, purple, pink, red, orange, yellow, green, teal, white, black, gray or "#rrggbb". "text" puts it back to normal. A tgame sprite, object or group takes any of those colors, plus brown, gold, lime, cyan, navy, sky, sand, grass, leaf, wood, stone, water, snow, silver.'],
  disable: ['button:disable', 'Greys out a button so it can\'t be clicked.'],
  enable: ['button:enable', 'Makes a disabled button clickable again.'],
  hide: ['thing:hide', 'Hides it. Works on tgame sprites, objects, groups, panels, screens and the arrow from world:arrow_to too.'],
  show: ['thing:show', 'Shows it again after :hide. Works on tgame sprites, objects, groups, panels, screens and arrows too (a screen that pauses pauses the game again).'],
  remove: ['thing:remove', 'Removes a widget for good. On a list, items:remove value takes that value out (by value, not by position). In tgame, it takes a sprite or object out of the game; on a group, group:remove(thing) only takes it out of the group.'],
  clear: ['thing:clear', 'Empties a text box, or a line you already said. On a row, card or page, removes everything inside it. In tgame, game:clear() removes everything the program made, group:clear() everything in a group, and panel:clear() the widgets on a panel or screen.'],
  rewrite: ['line:rewrite value', 'Replaces the text of a line you already said.'],
  append: ['line:append value', 'Adds text to the end of a line you already said.'],
  add: ['items:add value', 'Lists: adds value to the end of the list. A tgame group adds a sprite or object, and a tgame countdown adds seconds: clock:add(5).'],
  pop: ['items:pop', 'Lists: takes the last item off the list and gives it back.'],
  has: ['thing:has value', 'Lists: true if the list holds value. Text: true if the text contains it, like name:has "a". Data objects (tap): true if it has that name, like user:has "email". A tgame group: true if the thing is in it.'],
  upper: ['text:upper', 'Text: gives back the text in CAPITAL letters.'],
  lower: ['text:lower', 'Text: gives back the text in small letters. In tgame, land:lower(x, z, size, amount) is a brush that digs the land down.'],
  trim: ['text:trim', 'Text: gives back the text without spaces at the start and end.'],
  status: ['res:status', 'tap responses: the status code, like 200 (it worked) or 404 (not found).'],
  ok: ['res:ok', 'tap responses: true if the request worked (a status from 200 to 299). Errors like 404 don\'t stop the program, so check this.'],
  json: ['res:json', 'tap responses: reads what the server sent as JSON. An object {...} gives a dictionary (read it with data["name"] or data:get("name")), an array [...] gives a list.'],
  header: ['res:header("Content-Type")', 'tap responses: one header the server sent, or nil if it didn\'t send it.'],
  get: ['data:get("name")', 'tap: res:json gives a dictionary, so data:get("name") is the value with that name, or nil if there isn\'t one (data["name"] works too). Objects inside are dictionaries too, and arrays are lists. tgame sprites and objects keep values too: tree:get("hp").'],
  keys: ['data:keys', 'tap: res:json gives a dictionary, so data:keys() is a list of all its names. Loop over them with: for name in data:'],
  // tgame (games). Names tgui or tap also use (text, set, open...) have one entry above, which mentions tgame too.
  frame: ['game:frame()', 'tgame: draws the next frame, handles keys and clicks, and gives back the seconds since the last one (dt). Use it in a loop: while game:open(): dt = game:frame()'],
  every_frame: ['game:every_frame(step)', 'tgame: runs step(dt) every frame, with the seconds since the last one. The callback style: no loop needed.'],
  on_key: ['game:on_key("space", jump)', 'tgame: runs jump when the key is pressed. "any" runs it for every key, and the function can take the key\'s name: func pressed(key):'],
  clicked: ['thing:clicked fn', 'tgame: runs fn when it\'s clicked. A sprite or object gives fn itself (func chop(tree):); the game gives x and y (a world gives x, y and z).'],
  held: ['game:held("left")', 'tgame: true while the key is held down. Keys: a letter, a number, space, enter, shift, up, down, left, right, "mouse".'],
  pressed: ['game:pressed("space")', 'tgame: true only in the frame the key went down (for a pygame-style loop).'],
  mouse_x: ['game:mouse_x()', 'tgame: where the mouse is, across.'],
  mouse_y: ['game:mouse_y()', 'tgame: where the mouse is, down.'],
  time: ['game:time()', 'tgame: seconds since the game started, not counting pauses.'],
  fps: ['game:fps()', 'tgame: frames per second right now.'],
  paused: ['game:paused()', 'tgame: true while the game is paused or over.'],
  game_over: ['game:game_over("Score: 5", restart)', 'tgame: stops the game and shows "Game over" with the message. Space (or a click) then runs restart, which should set everything back. Leave restart out to just stop.'],
  sound: ['game:sound "coin"', 'tgame: plays a sound: beep, coin, jump, hit, boom, chop, laser, pop, click, step, powerup, win, lose, or a .wav, .mp3 or .ogg file from your project folder.'],
  beep: ['game:beep(pitch, seconds)', 'tgame: a beep. pitch is in hertz (440 by default).'],
  music: ['game:music "song.mp3"', 'tgame: plays a sound file over and over. game:stop_music() stops it.'],
  stop_music: ['game:stop_music()', 'tgame: stops the music.'],
  volume: ['game:volume 50', 'tgame: how loud everything is, from 0 to 100.'],
  width: ['game:width()', 'tgame: how wide the game is.'],
  height: ['game:height()', 'tgame: how tall the game is.'],
  background: ['game:background "black"', 'tgame: the color behind everything (in 3D, a plain sky).'],
  random_spot: ['game:random_spot()', 'tgame: a random spot on the screen, [x, y] (or [x, 0, z] on the ground in 3D). random_spot(20) keeps to a grid of 20. Use it anywhere x and y go: food:move_to(game:random_spot())'],
  group: ['things = game:group()', 'tgame: a group of sprites or objects: :add, :remove, :has, :items, :count, and :move, :hide, :show, :color, :clear for all of them at once.'],
  hud: ['hud = game:hud()', 'tgame: a layer on top of the game that the camera doesn\'t move, for scores and messages: hud:text("Score: 0", 80, 30).'],
  panel: ['bar = game:panel("top left")', 'tgame: real buttons, text boxes and every other atgui widget, pinned to a place on the game: "top left", "top", "top right", "left", "center", "right", "bottom left", "bottom" or "bottom right". bar:button("Shop", open_shop), bar:heading "Coins: 0", bar:progress(100)... Clicks on its widgets go to them; clicks anywhere else reach the game. bar:hide, bar:show, bar:clear.'],
  screen: ['shop = game:screen("Shop")', 'tgame: a layer over the whole game for a menu, a shop, a pause menu or game over, with the title on top. Add any atgui widget to it (shop:button, shop:input, shop:slider...). It pauses the game while it shows (game:screen("Map", false) doesn\'t). shop:show, shop:hide, shop:shown().'],
  start_screen: ['start = game:start_screen("My Game", "Click to play")', 'tgame: a title screen over the game, which waits until it\'s clicked (or Enter or Space). In a 3D world with a player, that click also locks the mouse for looking around. Add more to it like a screen (start:text "..."), and start:show() brings it back, like after game over.'],
  shown: ['shop:shown()', 'tgame: true while a screen (game:screen, game:start_screen or game:main_menu) is showing.'],
  splash: ['game:splash("logo.png", 3)', 'tgame: a splash screen when the game starts, before the main menu or start screen: a picture from your project folder (.png, .jpg or .gif, fitted on black) or some text, for that many seconds (2 by default). Several play in order, each fading in and out, and a click or any key skips to the next. game:splash() shows "Made with Tuff". The game is paused and the mouse free while they play.'],
  main_menu: ['menu = game:main_menu("My Game")', 'tgame: a main menu: a big title over the paused game, with wide buttons under it (menu:button("Play", play), menu:text, menu:image...). It shows when the game starts, after any splash screens, and the mouse stays free: its clicks never reach the game. menu:hide() starts the game (in 3D with a player, that click also locks the mouse for looking around), and menu:show() brings it back, like from a pause menu.'],
  lock_mouse: ['world:lock_mouse()', 'tgame (3D): locks the mouse for looking around: now, while the game\'s window is in front, or else on the next click on the game. While a screen shows, it locks once the screen hides.'],
  unlock_mouse: ['world:unlock_mouse()', 'tgame (3D): frees the mouse (the pointer shows again), and keeps it free until world:lock_mouse() or a click on the game. Screens, the main menu and splash screens free it by themselves while they show.'],
  mouse_locked: ['world:mouse_locked()', 'tgame (3D): true while the mouse is locked for looking around, false while it\'s free.'],
  auto_lock: ['world:auto_lock(false)', 'tgame (3D): with false, clicks on the game no longer lock the mouse, so your code decides with world:lock_mouse() and world:unlock_mouse(). true turns it back on (the default once there\'s a player).'],
  box: ['game:box(x, y, width, height, color)', 'tgame: a rectangle. x and y are its middle. In 3D: world:box(x, y, z, size, color), with its bottom at y (0 is the ground); size is a number or [width, height, depth].'],
  circle: ['game:circle(x, y, radius, color)', 'tgame: a circle.'],
  line: ['game:line(x1, y1, x2, y2, color)', 'tgame: a line. :size changes how thick it is.'],
  camera: ['game:camera(x, y)', 'tgame (2D): the point in the middle of the screen, for games bigger than the window. The HUD stays put.'],
  sky: ['world:sky "sunset"', 'tgame (3D): day, sunset, dawn, night, cloudy or space. It sets the sky, the sun, the light and the fog.'],
  fog: ['world:fog 60', 'tgame (3D): things fade into the sky this far away. 0 turns the fog off.'],
  sun: ['world:sun 1.5', 'tgame (3D): how bright the sun is (1 is normal, 0 is off).'],
  light: ['world:light(x, y, z, color)', 'tgame (3D): a lamp that lights up what\'s around it.'],
  ground: ['world:ground "grass"', 'tgame (3D): a big flat floor at height 0. world:ground(color, size).'],
  island: ['world:island(80)', 'tgame (3D): a round grassy island this wide, with a beach and the sea around it. The player can\'t walk off it.'],
  sphere: ['world:sphere(x, y, z, size, color)', 'tgame (3D): a ball, size across, sitting at height y.'],
  cylinder: ['world:cylinder(x, y, z, size, color)', 'tgame (3D): a cylinder. size is a number or [width, height].'],
  cone: ['world:cone(x, y, z, size, color)', 'tgame (3D): a cone. size is a number or [width, height].'],
  plane: ['world:plane(x, y, z, size, color)', 'tgame (3D): a flat square lying down (a mat, a path, water). size is a number or [width, depth].'],
  spawn: ['world:spawn("tree", x, y, z)', 'tgame (3D): a ready-made model: tree, pine, rock, bush, flower, house, hut, sign, crate, fence or coin (or a .glb file). Leave out the spot for a random one.'],
  player: ['player = world:player "first person"', 'tgame (3D): you, walking with WASD or the arrows, jumping with Space and looking with the mouse once the game is clicked. "first person" or "third person".'],
  camera_at: ['world:camera_at(x, y, z)', 'tgame (3D): puts the camera there. Point it with world:look_at.'],
  look_at: ['thing:look_at(x, y, z)', 'tgame (3D): turns the camera (world:look_at) or an object to face a spot or another object.'],
  follow: ['world:follow(thing, distance, height)', 'tgame (3D): the camera follows behind an object (7 back and 3 up by default).'],
  orbit: ['world:orbit(thing)', 'tgame (3D): the camera circles an object or a spot: drag with the mouse to turn, scroll to zoom.'],
  looking_at: ['world:looking_at()', 'tgame (3D): the object in the middle of the view (under the crosshair), or nil. looking_at(4) only finds things within 4.'],
  lighting: ['world:lighting "modern"', 'tgame (3D): "modern" gives soft light from the sky, richer colours and shadows that follow the camera; "simple" (the default) is the classic look.'],
  terrain: ['land = world:terrain(200)', 'tgame (3D): land you can shape, this wide, centred on 0, 0: land:hill, :mountain, :lake, :valley, :raise... A style can go second: world:terrain(200, "snow"). In a world with land, every y is the height above the land.'],
  hill: ['land:hill(x, z, size, height)', 'tgame (3D): a round hill on the land, size wide. A negative height makes a hollow.'],
  mountain: ['land:mountain(x, z, size, height)', 'tgame (3D): a tall, rough mountain, rocky with a snowy top.'],
  dip: ['land:dip(x, z, size, depth)', 'tgame (3D): a hollow in the land.'],
  lake: ['land:lake(x, z, size, depth)', 'tgame (3D): a hollow with water in it. The player can\'t walk into it.'],
  valley: ['land:valley(x1, z1, x2, z2, width, depth)', 'tgame (3D): a long trench in the land, from x1, z1 to x2, z2.'],
  raise: ['land:raise(x, z, size, amount)', 'tgame (3D): a brush that lifts the land there. Give it a list of spots for a stroke: land:raise([[1, 2], [3, 2]], 8, 1.5)'],
  smooth: ['land:smooth(x, z, size)', 'tgame (3D): a brush that evens out bumps in the land (or a list of spots, then the size).'],
  flatten: ['land:flatten(x, z, size, height)', 'tgame (3D): a brush that moves the land toward that height, to make a flat place.'],
  water: ['land:water(level)', 'tgame (3D): a sea over every part of the land lower than that height.'],
  height_at: ['land:height_at(x, z)', 'tgame (3D): how high the land is there, as a number.'],
  x: ['thing:x()', 'tgame: where a sprite or object is, across.'],
  y: ['thing:y()', 'tgame: where a sprite is, down (in 3D: how high an object\'s bottom is, above the land if there is a terrain).'],
  z: ['thing:z()', 'tgame (3D): where an object is, front to back.'],
  spot: ['thing:spot()', 'tgame: where it is, as a list: [x, y] (or [x, y, z] in 3D). Use it anywhere a spot goes: tail:move_to(head:spot())'],
  move: ['thing:move(dx, dy)', 'tgame: moves it by that much (in 3D: dx, dy, dz). A group moves everything in it.'],
  move_to: ['thing:move_to(x, y)', 'tgame: puts it at x, y (in 3D: x, y, z), or at a spot: food:move_to(game:random_spot())'],
  glide: ['thing:glide(x, y, seconds)', 'tgame: moves it smoothly to x, y over some seconds (in 3D: x, y, z, seconds).'],
  forward: ['thing:forward(distance)', 'tgame: moves it the way it\'s facing (2D: angle 0 is to the right; 3D: an object starts facing away from the camera).'],
  turn: ['thing:turn(degrees)', 'tgame: turns it by that many degrees. More than 0 turns right (clockwise). A boost pad shoots the player the way it faces, so boost:turn(90) aims it.'],
  turn_to: ['thing:turn_to(degrees)', 'tgame: sets which way it faces, in degrees.'],
  angle: ['thing:angle()', 'tgame: which way it faces, in degrees.'],
  spin: ['thing:spin(degrees_per_second)', 'tgame: keeps it turning by itself. spin(0) stops. A 3D physics thing also takes spin(x, y, z): a twist that sets it spinning.'],
  point_at: ['sprite:point_at(x, y)', 'tgame (2D): turns a sprite to face a spot or another sprite.'],
  on_edge: ['sprite:on_edge "bounce"', 'tgame (2D): what a sprite does at the edge of the screen: "bounce", "wrap" (comes back on the other side), "stop" (stays on screen) or "none".'],
  on_screen: ['sprite:on_screen()', 'tgame (2D): true if any of it can be seen.'],
  touches: ['thing:touches(other)', 'tgame: true if it touches another sprite or object. Give it a list or a group and it gives back the one it touches, or nil: hit = ball:touches(bricks)'],
  distance: ['thing:distance(other)', 'tgame: how far it is from another sprite, object, the player, or a spot.'],
  scale: ['thing:scale 2', 'tgame: how big it is drawn: 1 is normal, 2 is twice as big.'],
  layer: ['sprite:layer 2', 'tgame (2D): which sprites are drawn on top. Higher layers are on top; 0 by default.'],
  flip: ['sprite:flip()', 'tgame: mirrors a 2D sprite left to right (again to flip back). car:flip() puts a car back on its wheels.'],
  align: ['label:align "left"', 'tgame (2D): makes x the left edge of the text ("left"), its middle ("center") or its right edge ("right").'],
  shake: ['thing:shake()', 'tgame: shakes it for a moment, like a tree being chopped. game:shake(0.5) shakes the camera (0 to 2) for a moment, and world:shake(1, 1.5) for 1.5 seconds.'],
  fall: ['tree:fall()', 'tgame (3D): it topples over, away from the player. It stops being solid.'],
  fallen: ['tree:fallen()', 'tgame (3D): true from :fall until it stands up again.'],
  grow: ['thing:grow()', 'tgame (3D): grows from tiny to its full size.'],
  regrow: ['tree:regrow(5)', 'tgame (3D): after it falls, it stands up again and grows back this many seconds later.'],
  swing: ['axe:swing()', 'tgame (3D): swings it forward and back, like an axe chopping.'],
  glow: ['thing:glow "gold"', 'tgame (3D): makes it shine in that color. "none" stops.'],
  solid: ['thing:solid false', 'tgame (3D): whether the player bumps into it (true for most things you make).'],
  label: ['thing:label "Oak"', 'tgame (3D): text floating above an object. label "" removes it. A sign gets the words written on its board: sign:label("Shop").'],
  walk_speed: ['player:walk_speed 6', 'tgame (3D): how fast the player walks (5 by default). Shift runs.'],
  jump_height: ['player:jump_height 2', 'tgame (3D): how high the player jumps (1.2 by default).'],
  jump: ['player:jump()', 'tgame (3D): makes the player jump (Space does it too).'],
  hold: ['axe = player:hold "axe"', 'tgame (3D): the player holds an axe, pickaxe, sword, torch or hammer. It gives back the held thing, so axe:swing() works.'],
  items: ['group:items()', 'tgame: a list of everything in a group.'],
  count: ['group:count()', 'tgame: how many things are in a group.'],
  terrain: ['land = world:terrain(200)', 'tgame (3D): a square of flat land this wide around 0, 0, to shape with :hill, :mountain, :lake, :valley and the brushes. A style can go second: world:terrain(200, "snow"). A world has one. With it, every y is the height above the land.'],
  lighting: ['world:lighting "modern"', 'tgame (3D): "modern" lights everything softly from the sky, with tone mapping and sharper shadows. "simple" (the default) is the classic look.'],
  hill: ['land:hill(x, z, size, height)', 'tgame (3D): a smooth hill on the land, size wide.'],
  mountain: ['land:mountain(x, z, size, height)', 'tgame (3D): a tall, rough, rocky mountain with a snowy top. The same code always makes the same mountain.'],
  dip: ['land:dip(x, z, size, depth)', 'tgame (3D): a hollow in the land.'],
  lake: ['land:lake(x, z, size, depth)', 'tgame (3D): a hollow with water in it, up to where the ground was. The player can\'t walk into it.'],
  valley: ['land:valley(x1, z1, x2, z2, width, depth)', 'tgame (3D): a trench in the land from one spot to the other.'],
  raise: ['land:raise(x, z, size, amount)', 'tgame (3D): a brush that pushes the land up. A list of [x, z] spots in place of x and z is a stroke: land:raise([[0, 0], [4, 2]], 8, 1.5)'],
  smooth: ['land:smooth(x, z, size)', 'tgame (3D): a brush that evens out bumps in the land.'],
  flatten: ['land:flatten(x, z, size, height)', 'tgame (3D): a brush that moves the land toward that height, for a flat spot.'],
  water: ['land:water(-1)', 'tgame (3D): a sea everywhere the land is lower than that height.'],
  height_at: ['land:height_at(x, z)', 'tgame (3D): how high the land is there, as a number.'],
  // tgame's physics: things that fall, bounce, tumble and get pushed.
  physics: ['crate:physics()', 'tgame: makes it a physics thing: it falls, bounces, tumbles, knocks into things and gets pushed. physics("static") stays put but is solid (a floor, a wall), "kinematic" is moved only by your code, "off" turns it off ("on", "fixed" and "none" work too). It gives back the thing: ball = world:sphere(0, 5, 0, 1, "red"):physics()'],
  weight: ['crate:weight(50)', 'tgame: how heavy a physics thing is, in kg. Things weigh what they are by default (a crate 25, a 1 m box 50, a car 1200, a ragdoll and the player 70), so heavy things are hard to push and the player can\'t budge them. crate:weight() gives it back. player:weight(90) makes the player shove harder.'],
  mass: ['crate:mass(2)', 'tgame: the same as :weight: how heavy a physics thing is, in kg. crate:mass() gives it back.'],
  bounce: ['ball:bounce(0.6)', 'tgame: how bouncy a physics thing is, from 0 (no bounce) to 1 (it bounces right back up).'],
  friction: ['crate:friction(0.4)', 'tgame: how grippy a physics thing is: 0 slides like ice, 1 and more grips.'],
  push: ['crate:push(0, 5, -3)', 'tgame: kicks a physics thing: x, y and z, or x and y in 2D. In 3D the numbers are the speed it gives a 50 kg thing (a 1 m box): heavier things move less, lighter ones fly off faster.'],
  velocity: ['crate:velocity(0, 0, -4)', 'tgame: sets how fast a physics thing moves each way (x, y, z, or x, y in 2D). crate:velocity() gives it back as a list.'],
  on_hit: ['crate:on_hit(bumped)', 'tgame: runs bumped(other, strength) when something hits it: other is what hit it, and strength how hard (under 1 is a gentle touch; heavy things hit harder). Works on physics things and the player.'],
  sleep: ['crate:sleep()', 'tgame: a physics thing stops moving until something hits it or :wake wakes it.'],
  wake: ['crate:wake()', 'tgame: wakes a sleeping physics thing up, so it falls and moves again.'],
  gravity: ['world:gravity(-9.8)', 'tgame: how strong gravity is for physics things: -9.8 is like on Earth (the default), 0 floats like in space. In 2D, game:gravity(900) is pixels a second each second, down the screen.'],
  explode: ['world:explode(x, y, z, strength, radius)', 'tgame: pushes every physics thing within radius away from the spot, less the further away it is (2D: game:explode(x, y, strength, radius)).'],
  walls: ['game:walls(true)', 'tgame (2D): makes the edges of the screen walls that physics things bounce off.'],
  car: ['car = world:car(x, y, z, "red")', 'tgame (3D): a car with four wheels, springy suspension and steering (it weighs 1200 kg). The player walks up to it and presses F to get in ("F: Get in" shows), drives with the arrow keys or WASD, and presses F again to get out. car:drive() starts the game in it, :engine(2) gives it more power, :speed() is how fast it goes in km/h, and :flip() puts it back on its wheels.'],
  ragdoll: ['dummy = world:ragdoll(x, y, z, "blue")', 'tgame (3D): a person made of jointed parts (a head, a body, arms and legs) that flops over when it\'s hit or pushed: dummy:push(0, 4, -6). It weighs 70 kg, and dresses like a person: dummy:shirt("red"), dummy:hair("curly").'],
  drive: ['car:drive()', 'tgame (3D): the player starts in the car (F gets out): the arrow keys or WASD drive it, and the camera follows it. Without a player, the keys drive it. car:drive(false) gets out.'],
  on_enter: ['car:on_enter(got_in)', 'tgame (3D): runs got_in() when the player gets into the car (F next to it, or car:drive()). A game that uses F itself (world:on_key("f", ...)) gets in with car:drive() instead.'],
  on_exit: ['car:on_exit(got_out)', 'tgame (3D): runs got_out() when the player gets out of the car (F again, or car:drive(false)).'],
  driven: ['car:driven()', 'tgame (3D): true while the player is in the car.'],
  in_car: ['player:in_car()', 'tgame (3D): true while the player is in a car (it got in with F).'],
  shirt: ['npc:shirt("red")', 'tgame (3D): the colour of a person\'s shirt (a person, a ragdoll, or the player in third person).'],
  pants: ['npc:pants("black")', 'tgame (3D): the colour of a person\'s trousers.'],
  skin: ['npc:skin("tan")', 'tgame (3D): a person\'s skin colour: pale, light, tan, medium, brown, dark, or a hex code.'],
  hair: ['npc:hair("curly", "blonde")', 'tgame (3D): a person\'s hair style (short, swoop, bob, ponytail, buns, curly, spiky) and its colour (black, brown, blonde, ginger, grey, or any colour), one or both.'],
  shoes: ['npc:shoes("white")', 'tgame (3D): the colour of a person\'s shoes.'],
  sleeves: ['npc:sleeves("short")', 'tgame (3D): a person\'s sleeves: "long", or "short" (rolled up to the elbow).'],
  engine: ['car:engine(1.5)', 'tgame (3D): how strong a car\'s engine is: 1 is normal, 2 is twice as strong.'],
  animate: ['hero:animate("walk")', 'tgame (3D): what a character model does: "walk", "idle" (a gentle breathe), "wave" or "none". By default it walks when it moves and breathes when it stands still.'],
  // tgame's game kit: effects, the HUD, interaction and level pieces.
  slow_mo: ['world:slow_mo(0.3, 2)', 'tgame: slow motion. Everything (the game clock, things that move, physics, animation) runs at 30% for 2 seconds, then eases back (the speed is from 0.05 to 1). world:slow_mo(1) ends it. game:slow_mo works in 2D too.'],
  pop_text: ['world:pop_text("+10", x, y, z)', 'tgame: text that floats up from a spot and fades, like "+10" over a coin. Then a color and a size in pixels (how tall it is on screen, 34 if you leave it out): world:pop_text("+10", 0, 2, 0, "gold", 40). In 2D: game:pop_text("+10", x, y).'],
  weather: ['world:weather("rain")', 'tgame (3D): "rain" (falling streaks, a darker sky, thicker fog, wet ground), "snow" (drifting flakes, a paler sky) or "none". Then how strong it is, from 0 to 2: world:weather("snow", 1.5).'],
  day_cycle: ['world:day_cycle(120)', 'tgame (3D): morning, noon, sunset, night (with stars) and dawn, round and round, over 120 seconds (2 or more); the sky, the sun, the light and the fog follow. world:day_cycle(0) stops it where it is.'],
  time_of_day: ['world:time_of_day(18)', 'tgame (3D): jumps to that hour, from 0 to 24 (18 is 6 pm, a sunset).'],
  health_bar: ['enemy:health_bar(100)', 'tgame: a health bar over it (in 3D it faces the camera), full at 100 (a door has no health). enemy:hurt(10) takes some off, enemy:heal(5) gives some back, enemy:health() is how much it has.'],
  hurt: ['enemy:hurt(10)', 'tgame: takes 10 off its health: its bar shrinks and flashes. At 0, its :on_death function runs.'],
  heal: ['enemy:heal(5)', 'tgame: gives it 5 health back (never more than its health bar\'s most).'],
  health: ['enemy:health()', 'tgame: how much health it has, as a number.'],
  on_death: ['enemy:on_death(gone)', 'tgame: runs gone() once, when its health reaches 0.'],
  countdown: ['clock = game:countdown(60, times_up)', 'tgame: a timer in the top right that ticks down from 60 seconds, turns red under 10 and runs times_up() at 0. clock:add(5) adds seconds, clock:stop() stops it, clock:left() is how many seconds are left.'],
  left: ['clock:left()', 'tgame: how many seconds a countdown has left, as a number.'],
  arrow_to: ['arrow = world:arrow_to(chest)', 'tgame (3D): an arrow at the edge of the screen that points at a thing, with how far it is ("24 m"). arrow:hide(), arrow:show(), and world:arrow_to(other) points it at something else.'],
  minimap: ['map = world:minimap()', 'tgame (3D): a round map in the top right: the land, its water, and the player as an arrow. Its size in pixels (180, from 60 to 600) and a corner are optional: world:minimap(200, "top left"). map:mark(coin, "gold") adds a dot.'],
  mark: ['map:mark(coin, "gold")', 'tgame (3D): a dot on the minimap that follows a thing, in a color.'],
  unmark: ['map:unmark(coin)', 'tgame (3D): takes a thing\'s dot off the minimap.'],
  zoom: ['map:zoom(2)', 'tgame (3D): how close the minimap shows: 2 is twice as close, 0.5 shows more.'],
  can_grab: ['player:can_grab()', 'tgame (3D): E picks up the physics thing the player looks at (within 3 m) and it floats in front of them; a click throws it, E again drops it. player:can_grab(false) turns it off.'],
  holding: ['player:holding()', 'tgame (3D): the thing the player is holding with :can_grab, or nil.'],
  say: ['npc:say("Hi! Find my lost cat.")', 'tgame (3D): a speech bubble over it for 4 seconds. A second input is how many seconds (0 keeps it): npc:say("Bye", 2).'],
  on_talk: ['npc:on_talk(talk)', 'tgame (3D): when the player is within 3 m and presses E ("E: Talk" shows), talk() runs.'],
  door: ['door = world:door(x, y, z)', 'tgame (3D): a door in a frame that swings open when the player walks into it or presses E, and closes after a while. A color is optional ("wood"). door:open(), door:close(), door:turn(90), door:needs(key).'],
  needs: ['door:needs(key)', 'tgame (3D): the door is locked until the player picks up the key (they walk into it and it goes). A locked door says "Locked!" and the key\'s name.'],
  lock: ['door:lock()', 'tgame (3D): locks a door, so it doesn\'t open.'],
  unlock: ['door:unlock()', 'tgame (3D): unlocks a door.'],
  jump_pad: ['pad = world:jump_pad(x, y, z, 15)', 'tgame (3D): a glowing pad that launches the player (and physics things) up, 15 metres a second, with a whoosh.'],
  boost_pad: ['boost = world:boost_pad(x, y, z, 20)', 'tgame (3D): a pad that shoots the player forward the way it faces, with streaks. boost:turn(90) aims it.'],
  path: ['lift:path([[0, 2, 0], [10, 2, 0]], 3)', 'tgame (3D): moves it along the spots at 3 metres a second, and back (a moving platform). "loop" as a third input goes round instead. The player and physics things ride on it. lift:path() stops it. Not for a car or a ragdoll: they always use physics.'],
};

// tgame's saved game data: game:save, :load, :saved and :forget, the same on a 2D game and a 3D world.
Object.assign(window.TUFF_METHOD_DOCS, {
  save: ['game:save("best", score)', 'tgame: saves a value under a name, right away, so it\'s still there the next time the game runs: a high score, the level, settings. It keeps numbers, text, true/false, nil, lists and dictionaries (and tap data objects). Saves belong to the game\'s title, so give each game its own.'],
  load: ['best = game:load("best", 0)', 'tgame: gives back what was saved under that name, even by an earlier run of the game, or the second input when nothing was saved yet (nil if you leave it out). Lists come back as lists, and dictionaries (and tap data objects) as dictionaries.'],
  saved: ['game:saved("best")', 'tgame: true if something is saved under that name.'],
  forget: ['game:forget("best")', 'tgame: forgets one save. game:forget() forgets every save this game has.'],
});

// tgame's multiplayer: games on the same network play together, the same on a 2D game and a 3D world
// (world:others is a 3D world's).
Object.assign(window.TUFF_METHOD_DOCS, {
  host: ['game:host("Tag")', 'tgame: hosts a room that games on the same network (the same Wi-Fi) can join. game:host() names it after the game. game:hosting() is true from the next line.'],
  join: ['game:join()', 'tgame: finds a room on the network and goes in. game:join("Tag") goes in the room called Tag, and game:join("192.168.1.20") straight to that computer. The game keeps running while it looks; game:connected() is true once it\'s in.'],
  leave: ['game:leave()', 'tgame: leaves the room. A host leaving closes the room for everyone.'],
  connected: ['game:connected()', 'tgame: true while the game is in a room (hosting one, or joined).'],
  hosting: ['game:hosting()', 'tgame: true while this game hosts the room. Handy for things only one game should do, like starting a timer.'],
  players: ['names = game:players()', 'tgame: a list of everyone\'s names in the room, yours too, the host\'s first.'],
  my_name: ['game:my_name("Sam")', 'tgame: the name other players see (over your head in 3D, and as the sender of your messages). game:my_name() gives it back: "Player 1" for the host, "Player 2"... unless you chose one.'],
  send: ['game:send("score", 10)', 'tgame: sends a message to every other player, with a value if you like (numbers, text, true/false, lists, tables). Their on_message function gets it.'],
  on_message: ['game:on_message(got)', 'tgame: runs got(message, value, sender) for each message another player sends: the message, its value (nil if none) and their name.'],
  on_join: ['game:on_join(hello)', 'tgame: runs hello(name) when another player comes in (and, when you join, for each player already there).'],
  on_leave: ['game:on_leave(bye)', 'tgame: runs bye(name) when another player leaves, or for everyone when the host leaves.'],
  share: ['game:share("coins", 5)', 'tgame: sets a value every player in the room sees. The host keeps it, so players who join later get it too.'],
  shared: ['coins = game:shared("coins", 0)', 'tgame: a value shared with game:share, or the second input until someone shares it.'],
  others: ['for p in world:others():', 'tgame (3D): the other players, as people in your world that walk where they walk, with their names over their heads. p:get("name") is their name; me:distance(p) and me:touches(p) work.'],
});

window.TUFF_LIBS = {
  tgui: {
    window: ['tgui.window("Title", width, height)', 'Opens a new app window. Width and height are optional.'],
  },
  mtgui: {
    window: ['mtgui.window("Title", width, height)', 'Opens a modern app window with gradients, gloss and shine.'],
  },
  anims: {
    loading: ['anims.loading(text, seconds)', 'A spinning / - \\ | loader with animated dots. Both inputs are optional. After its inputs, look words like say:color\'s (1.4.1): colours, rainbow, bold/dim/italic/underline. anims.loading("Pulling info...", "green")'],
    bar: ['anims.bar(text, seconds, width)', 'A progress bar that fills from 0% to 100%. width is how many blocks wide it is (20 by default). After its inputs, look words like say:color\'s (1.4.1): colours, rainbow, bold/dim/italic/underline.'],
    type: ['anims.type(text, speed)', 'Types text out one letter at a time. speed is seconds per letter (0.04 by default), so a bigger number is slower. After its inputs, look words like say:color\'s (1.4.1): colours, rainbow, bold/dim/italic/underline.'],
    countdown: ['anims.countdown(start, then)', 'Counts down on one line, then shows the `then` text. After its inputs, look words like say:color\'s (1.4.1): colours, rainbow, bold/dim/italic/underline. anims.countdown(3, "Go!", "lime")'],
  },
  tap: {
    get: ['tap.get(url, headers)', 'Gets a web page or API and gives back a response: res:status, res:ok, res:text, res:json, res:header(name). headers is optional: a dictionary, like {"Accept": "text/csv"}.'],
    post: ['tap.post(url, body, headers)', 'Sends body to url and gives back a response. Text goes as plain text; a dictionary or a list goes as JSON. headers is optional.'],
    put: ['tap.put(url, body, headers)', 'Like tap.post, but for replacing what is at url. headers is optional.'],
    delete: ['tap.delete(url, headers)', 'Asks the server to delete what is at url, and gives back a response. headers is optional.'],
    data: ['tap.data()', 'An empty dictionary, the same as {}: for a JSON body or headers. Fill it with :set("name", value) or data["name"] = value.'],
  },
  tgame: {
    window: ['tgame.window("Title", width, height)', 'Opens a 2D game window (800 by 600 by default). Make boxes, circles, text and pictures on it, then loop: while game:open(): dt = game:frame()'],
    world: ['tgame.world("Title", width, height)', 'Opens a 3D game world: a sky, the ground, an island or land with hills and lakes (:terrain), shapes, ready-made trees and houses (:spawn), and a player who walks around (:player).'],
  },
};

window.TUFF_DOCS = {
  say: ['say value', 'Shows a line in the Run window. `line = say "hi"` keeps the line so you can :rewrite it later.'],
  input: ['input "question"', 'Asks the person running the program to type something and gives back their answer as text. input:color("Name? ", "green") asks with the question in a look (colours, rainbow, styles), like say:color.'],
  func: ['func name(inputs):', 'Makes a function. It gives back its last value automatically, or whatever you `return`.'],
  return: ['return value', 'Leaves the function and gives back a value.'],
  if: ['if condition:', 'Runs the indented block only when the condition is true. `then` works instead of `:`.'],
  elif: ['elif condition:', 'Checked when the `if` above it was false.'],
  else: ['else:', 'Runs when nothing above it matched.'],
  then: ['then', 'Starts a block, same as `:`. Writing both (`then:`) works too.'],
  while: ['while condition:', 'Repeats the block as long as the condition stays true. Loops are quick (1.5.0): a million steps take about a second or less.'],
  for: ['for item in list:', 'Runs the block once for every item in a list, text or range(). Loops are quick (1.5.0): a million steps take about a second or less.'],
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
  tap: ['mention tap', 'Get and send things on the web (HTTP), like Python\'s requests: tap.get, post, put, delete. JSON comes back as dictionaries and lists.'],
  tgame: ['mention tgame', 'Make games, like pygame: tgame.window for 2D (sprites, keys, the mouse, collisions, sounds) and tgame.world for 3D (a sky, trees, a first-person player).'],
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
  const own = {
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
  };
  // A name tgame has too (align, clicked, grow, width...) keeps both meanings. Its doc then starts with
  // neither library's name, so completions offer it in atgui and tgame files alike.
  for (const [name, [sig, text]] of Object.entries(own)) {
    docs[name] = docs[name] && /^tgame\b/.test(docs[name][1])
      ? [docs[name][0], `In tgame: ${docs[name][1].replace(/^tgame( \([^)]*\))?:\s*/, '')} In atgui: ${text.replace(/^atgui:\s*/, '')}`]
      : [sig, text];
  }
})();

// 1.3.5: say:color, say:ascii and print:pen, and tdraw (drawing with a pen). A name another library has too keeps its
// doc, with this use added at the end.
(() => {
  window.TUFF_LIBS.tdraw = {
    pen: ['pen = tdraw.pen()', 'Opens the drawing window and gives a pen in the middle (0, 0), facing right. x goes right, y goes up. Move it with :forward, :left, :right, :go and :jump.'],
    background: ['tdraw.background("navy")', 'The drawing window\'s background colour.'],
    clear: ['tdraw.clear()', 'Wipes everything every pen has drawn.'],
    title: ['tdraw.title("My art")', 'The drawing window\'s title.'],
    size: ['tdraw.size(800, 600)', 'The drawing window\'s size.'],
    on_click: ['tdraw.on_click(clicked)', 'Runs clicked(x, y) when the drawing is clicked.'],
  };
  window.TUFF_DOCS.tdraw = ['mention tdraw', 'Drawing with a pen (a turtle): lines, shapes, fills, text and rainbow pens, in a window that stays open. pen = tdraw.pen(), then pen:forward(100), pen:right(90).'];
  window.TUFF_DOCS.print = ['print(a, b, ...)', 'Like `say`, but takes several values separated by commas. print:color, print:ascii and print:pen (also say:color, say:ascii, say:pen) style what it shows.'];
  const docs = window.TUFF_METHOD_DOCS;
  window.TUFF_DOCS.rewrite = ['line:rewrite("new text", "glitch")', 'Replaces the text of a line you already said. After the text, look words (colours, rainbow, styles, a font) change its look and an animation plays on it in place.'];
  const own = {
    play: ['line:play("explode")', 'Plays an animation on a line you already said, where it is: fade, build, explode, assemble, type, glitch, drop or wave. With wait(3) before it, it plays 3 seconds later.'],
    ascii: ['say:ascii("GAME OVER", "red", "explode")', 'Big ASCII-art letters. After the text, in any order: a font (block, wide, small, shadow, led, hash), colours (the letters\', then a bar behind them), rainbow, bold/dim/italic/underline and an animation (fade, build, explode, assemble, type, glitch, drop, wave). It gives back the line: :rewrite keeps it big.'],
    pen: ['print:pen("lime", "bold")', 'Every line said after it gets this look (colours, rainbow, styles) until print:pen(): say, print, input\'s questions and anims too.'],
    color: ['say:color("Game over!", "red")', 'A coloured line. After the text, in any order: colours (the first is the letters\', a second is a bar behind the whole line), "rainbow", bold/dim/italic/underline and an animation (fade, type, glitch...). tdraw: pen:color("red") sets the pen\'s colour ("rainbow" changes as it moves), pen:color("red", "gold") the line and the fill. On a widget, label:color "red" changes its text color, and in tgame hero:color("gold") colours a sprite, object or group.'],
    forward: ['pen:forward(100)', 'tdraw: moves the pen forward, drawing a line (unless it\'s :up).'],
    back: ['pen:back(50)', 'tdraw: moves the pen backward, drawing as it goes.'],
    left: ['pen:left(90)', 'tdraw: turns the pen left by that many degrees (90 if you leave it out).'],
    right: ['pen:right(90)', 'tdraw: turns the pen right by that many degrees (90 if you leave it out).'],
    go: ['pen:go(x, y)', 'tdraw: moves the pen straight to x, y, drawing a line.'],
    jump: ['pen:jump(x, y)', 'tdraw: moves the pen to x, y without drawing.'],
    home: ['pen:home()', 'tdraw: back to the middle, facing right, without drawing.'],
    face: ['pen:face(90)', 'tdraw: points the pen: 0 is right, 90 up, 180 left, 270 down.'],
    up: ['pen:up()', 'tdraw: lifts the pen, so moving doesn\'t draw.'],
    down: ['pen:down()', 'tdraw: puts the pen down again, so moving draws.'],
    width: ['pen:width(5)', 'tdraw: how thick the pen\'s lines are.'],
    speed: ['pen:speed "fast"', 'tdraw: "slow", "normal", "fast" (the start) or "instant" (no animation, for big drawings), or 1 to 10.'],
    circle: ['pen:circle(50, "gold")', 'tdraw: a circle of that radius, starting where the pen is. A colour after it fills it.'],
    square: ['pen:square(80, "sky")', 'tdraw: a square with that side. A colour after it fills it.'],
    triangle: ['pen:triangle(80)', 'tdraw: a triangle with that side. A colour after it fills it.'],
    polygon: ['pen:polygon(6, 40)', 'tdraw: a shape with that many sides, each that long (6 makes a hexagon). A colour after it fills it.'],
    star: ['pen:star(100, "gold")', 'tdraw: a five-pointed star. A colour after it fills it.'],
    dot: ['pen:dot(20, "red")', 'tdraw: a filled dot where the pen is. The colour is optional.'],
    write: ['pen:write("Hello", 24)', 'tdraw: writes text where the pen is. The size is optional.'],
    hide: ['pen:hide()', 'tdraw: hides the turtle (the drawing stays).'],
    show: ['pen:show()', 'tdraw: shows the turtle again.'],
    x: ['pen:x()', 'tdraw: where the pen is, across.'],
    y: ['pen:y()', 'tdraw: where the pen is, up and down.'],
  };
  for (const [name, [sig, text]] of Object.entries(own)) {
    docs[name] = docs[name] && name !== 'color' ? [docs[name][0], `${docs[name][1]} ${text}`] : [sig, text];
  }
})();

// 1.4.0, the Toolbox Update: dictionaries, text tools, sorting, files, try/catch, date and time, more maths.
(() => {
  window.TUFF_LIBS.file = {
    read: ['file.read("notes.txt")', 'The text in a file, from your project folder.'],
    write: ['file.write("notes.txt", text)', 'Makes the file (or replaces what is in it) with the text.'],
    add: ['file.add("log.txt", line)', 'Adds a line to the end of a file (making it if it isn\'t there).'],
    lines: ['file.lines("names.txt")', 'A file\'s lines, as a list.'],
    exists: ['file.exists("save.json")', 'True if the file is there.'],
    delete: ['file.delete("old.txt")', 'Deletes a file.'],
    save: ['file.save("save.json", data)', 'Saves text, numbers, lists and dictionaries as JSON, to load back later.'],
    load: ['data = file.load("save.json", {})', 'Loads what file.save saved. The second input is what you get if the file isn\'t there yet. JSON keeps every key as text, so a dictionary\'s number keys come back as text: d["1"], not d[1].'],
  };
  Object.assign(window.TUFF_DOCS, {
    file: ['file.read("notes.txt")', 'Text files and saved data, in your project folder: file.read, write, add, lines, exists, delete, save and load. Nothing to mention.'],
    try: ['try:', 'Runs the block, and if something goes wrong in it, runs the catch: block below instead of stopping the program.'],
    catch: ['catch problem:', 'Runs when something in the try: block above went wrong. problem is what went wrong, as text. Any name works except Tuff\'s own, like err, text, len or time, and catch: on its own works too.'],
    now: ['now()', 'The time now, as text like "14:05:09".'],
    today: ['today()', 'Today\'s date, as text like "2026-10-26".'],
    time: ['time()', 'Seconds since the program started (with decimals). Save it, then subtract later for a timer.'],
    date: ['d = date()', 'Today and now as a dictionary: d["year"], d["month"], d["day"], d["weekday"], d["hour"], d["minute"], d["second"].'],
    sin: ['sin(degrees)', 'Sine of an angle in degrees: sin(90) is 1.'],
    cos: ['cos(degrees)', 'Cosine of an angle in degrees: cos(180) is -1.'],
    tan: ['tan(degrees)', 'Tangent of an angle in degrees: tan(45) is 1. tan(90) has no answer, so it gives an error.'],
    log: ['log(number, base)', 'The logarithm: log(100, 10) is 2 and log(1000, 10) is 3. Without a base, the natural log.'],
    random: ['random(low, high)', 'A random whole number from low to high, both included, like random(1, 6). If either end has digits after the point, like random(0.5, 2), it gives a decimal in that range (12 / 2 and 1.0 count as whole). random(6) is a whole number from 1 to 6, random(0.5) a decimal from 0 to 0.5, and random() a decimal from 0 to 1.'],
    text: ['text(value, decimals)', 'Turns any value into text. text(3.14159, 2) is "3.14".'],
    len: ['len(value)', 'How many characters are in some text, items in a list, or keys in a dictionary.'],
  });
  const docs = window.TUFF_METHOD_DOCS;
  const own = {
    split: ['t:split(",")', 'Text split into a list at each ",". With nothing, it splits at spaces.'],
    replace: ['t:replace("old", "new")', 'The text with every "old" replaced by "new".'],
    starts: ['t:starts("Mr")', 'True if the text starts with it.'],
    ends: ['t:ends(".txt")', 'True if the text ends with it.'],
    find: ['t:find("x")', 'Where it first is in the text (or a list), from 0, or -1 if it isn\'t there.'],
    count: ['t:count("a")', 'How many times it is in the text.'],
    pad_left: ['t:pad_left(3, "0")', 'The text filled on the left to that width: "7" becomes "007".'],
    pad_right: ['t:pad_right(10)', 'The text filled on the right with spaces to that width, to line up columns.'],
    sort: ['items:sort()', 'Sorts the list in place, numbers small to big, text A to Z. items:sort(by_score) sorts by what by_score(item) gives back.'],
    reverse: ['items:reverse()', 'Turns the list around, in place.'],
    join: ['items:join(", ")', 'The items as one text, with ", " between them.'],
    keys: ['ages:keys()', 'A dictionary\'s keys, as a list.'],
    values: ['ages:values()', 'A dictionary\'s values, as a list.'],
    get: ['ages:get("sam", 0)', 'A dictionary\'s value for a key, or the second input (nil if left out) when the key isn\'t there.'],
    set: ['ages:set("sam", 15)', 'Sets a key in a dictionary (same as ages["sam"] = 15). A key is text or a number.'],
    has: ['ages:has("sam")', 'Dictionaries: true if it has that key, like ages:has "sam".'],
    remove: ['ages:remove("sam")', 'On a dictionary, ages:remove "sam" takes that key out.'],
    size: ['ages:size()', 'On a dictionary, ages:size() is how many keys it has, the same as len(ages).'],
  };
  // A name a library has too (split in atgui, join and count in tgame, keys and get in tap) puts this use first and
  // the library's after it, so the doc starts with no library's name and ':' offers it in every program. A name whose
  // doc isn't one library's (set, has, size...) keeps it first, with this use added at the end.
  for (const [name, [sig, text]] of Object.entries(own)) {
    const old = docs[name];
    const lib = old && old[1].match(/^(atgui|tgame|tdraw|tap)\b[^:.]*:\s*/);
    if (!old) docs[name] = [sig, text];
    else if (lib) docs[name] = [sig, `${text} In ${lib[1]}, ${old[0]}: ${old[1].slice(lib[0].length)}`];
    else if (/^In tgame:/.test(old[1])) docs[name] = [sig, `${text} ${old[1]}`];
    else docs[name] = [old[0], `${old[1]} ${text}`];
  }
})();

const TUFF_BUILTINS = ['print', 'number', 'num', 'int', 'text', 'str', 'len', 'round', 'random', 'wait', 'range', 'clear', 'sqrt', 'abs', 'floor', 'ceil', 'min', 'max', 'sum', 'average',
  'now', 'today', 'time', 'date', 'sin', 'cos', 'tan', 'log'];
// Libraries that are always there, with nothing to mention (1.4.0's file.read...). They aren't functions, and
// import/mention doesn't offer them.
const TUFF_READY_LIBS = ['file'];
// The hover on a text template's f (1.5.0). It isn't in TUFF_DOCS, so a variable called f keeps no doc.
const TUFF_TEMPLATE_DOC = ['f"{name} has {score + 1} points"', 'A text template: the code in each { } is worked out and shown the way say shows it. '
  + 'A format can go after a \':\': {x:0.00} (2 decimals, rounded half up), {n:000} (at least 3 digits), {price:money} ($1,234.50), '
  + 'or a width, {name:12} (text on the left, numbers on the right; >12 and <12 choose). {{ and }} show a brace.'];

// try: and catch: (or catch problem:) at the start of a line, with nothing glued after the ':' (1.4.0). These always
// start a block. try:say "hi", with the ':' glued to a word, does too unless the program gives try a value (see
// tryCatchWord); anywhere else try and catch are a program's own names, like catch = [] or catch:add(1).
const TRY_CATCH = /^\s*(try|catch(\s+[A-Za-z_]\w*)?)\s*:(?=\s|#|$)/;
// A line that opens an indented block: if/elif/else/while/for/func ending in ':' or 'then', or try:/catch problem:.
const BLOCK_OPENER = /^\s*((if|elif|else|while|for|func)\b.*(:|\bthen)|(try|catch(\s+[A-Za-z_]\w*)?)\s*:)\s*(#.*)?$/;
const BLOCK_START = new RegExp(String.raw`^\s*(if|elif|else|while|for|func)\b|` + TRY_CATCH.source);

// Does the program give try and catch values of its own (try = ..., for catch in, a function input called catch)?
function ownTryCatch(model) {
  return { try: givesValue(model, 'try'), catch: givesValue(model, 'catch') };
}

// The try or catch that starts this line's block, or null, as tuff.py decides it: try: and catch: with nothing glued
// to the ':' and catch problem: always do, and try:say "hi" (the ':' glued to a word) does too, unless the program
// gives that word a value (own, from ownTryCatch). Then it's a method call, so a 1.3.6 program's catch:add(fish) works.
function tryCatchWord(text, own) {
  const m = /^\s*(try|catch)(\s+[A-Za-z_]\w*)?\s*:/.exec(text);
  if (!m) return null;
  if (m[2]) return m[1] === 'catch' ? 'catch' : null;
  return /^\s*(try|catch):[A-Za-z_]/.test(text) && own[m[1]] ? null : m[1];
}

// How each character of a line reads: 'c' code, 's' text (in quotes) and '#' a comment, as tuff.py reads it. In a
// text template (1.5.0) the code in each { } is code, like f"{name} has {score + 1} points"; the f, the quotes, the
// text, {{ and }}, and the { and } around the code are text. ends: 'text' or 'comment' when the line ends inside one.
function tuffScan(text) {
  const kinds = [];
  const open = []; // the templates the scan is inside: { quote, depth }, depth -1 in its text, else the brackets open in its { }
  let quote = null; // a plain "string" being read
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    const t = open[open.length - 1];
    if (quote) {
      kinds[i] = 's';
      if (c === '\\') kinds[++i] = 's';
      else if (c === quote) quote = null;
    } else if (t && t.depth < 0) {
      kinds[i] = 's';
      if (c === '\\' && 'nt\\"\''.includes(text[i + 1] || '#')) kinds[++i] = 's';
      else if (c === t.quote) open.pop();
      else if ((c === '{' || c === '}') && text[i + 1] === c) kinds[++i] = 's'; // {{ and }} show a brace
      else if (c === '{') t.depth = 0;
    } else if (c === '#') {
      for (; i < text.length; i++) kinds[i] = '#';
      return { kinds, ends: 'comment' };
    } else if (c === '"' || c === "'") {
      kinds[i] = 's';
      if (text[i - 1] === 'f' && !/\w/.test(text[i - 2] || '')) {
        kinds[i - 1] = 's';
        open.push({ quote: c, depth: -1 });
      } else quote = c;
    } else {
      kinds[i] = 'c';
      if (t && '([{'.includes(c)) t.depth++;
      else if (t && (c === ')' || c === ']')) t.depth = Math.max(0, t.depth - 1);
      else if (t && c === '}') {
        if (t.depth) t.depth--;
        else { kinds[i] = 's'; t.depth = -1; } // the } that ends the code
      }
    }
  }
  return { kinds, ends: quote || (open.length && open[open.length - 1].depth < 0) ? 'text' : null };
}

// True when the end of `text` is inside a "string", a 'string' or a # comment (and not in the code of an f"{...}").
function insideStringOrComment(text) {
  return tuffScan(text).ends !== null;
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
  // catch: in a program with its own catch (catch = []) is on its way to catch:add(...).
  const own = /^\s*(try|catch):$/.exec(before);
  return !(atEnd && BLOCK_START.test(line)) || !!(own && givesValue(model, own[1]));
};

// Typing the ':' of catch: or catch problem: moves the line out to its try:'s indent, like else (ide.js calls this).
// It isn't in decreaseIndentPattern: Monaco outdents a line the moment it matches and never puts it back, and in a
// program that gives catch a value (catch = [], for catch in, a function input) catch:add(fish) is a method call that
// keeps its place. Gives back the edit, or null.
window.tuffCatchOutdent = function tuffCatchOutdent(model, position) {
  const n = position.lineNumber;
  const line = model.getLineContent(n);
  if (!/^\s*catch(\s+[A-Za-z_]\w*)?\s*:\s*(#.*)?$/.test(line)) return null;
  const own = ownTryCatch(model);
  if (own.catch) return null;
  const indent = (s) => s.length - s.trimStart().length;
  const at = indent(line);
  let limit = at + 1; // the try has to be further out than every line between them
  for (let i = n - 1; i >= 1; i--) {
    const text = model.getLineContent(i);
    if (!text.trim() || /^\s*#/.test(text) || indent(text) >= limit) continue;
    if (tryCatchWord(text, own) === 'try') {
      if (indent(text) >= at) return null; // already there
      return { range: { startLineNumber: n, startColumn: 1, endLineNumber: n, endColumn: at + 1 }, text: text.slice(0, indent(text)) };
    }
    limit = indent(text);
    if (!limit) return null;
  }
  return null;
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
        [/f"/, 'string', '@fdq'], // a text template (1.5.0): f"{name} has {score + 1} points"
        [/f'/, 'string', '@fsq'],
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
      // A template's text: {{ and }} show a brace, and { starts code, coloured as code until its }.
      fdq: [[/\{\{|\}\}|\\[nt\\"']/, 'string.escape'], [/\{/, 'delimiter.curly', '@fcode'], [/"/, 'string', '@pop'], [/[^"\\{}]+/, 'string'], [/./, 'string']],
      fsq: [[/\{\{|\}\}|\\[nt\\"']/, 'string.escape'], [/\{/, 'delimiter.curly', '@fcode'], [/'/, 'string', '@pop'], [/[^'\\{}]+/, 'string'], [/./, 'string']],
      fcode: [
        [/:\s*(?:0+(?:\.0+)?|money|[<>]?[1-9]\d*)\s*(?=\})/, 'string.escape'], // its format: {x:0.00}, {price:money}, {name:12}
        [/\}/, 'delimiter.curly', '@pop'],
        [/\{/, 'delimiter.curly', '@fdict'], // a dictionary in it: f"{ {"a": 1}["a"] }"
        { include: '@root' },
      ],
      fdict: [[/\}/, 'delimiter.curly', '@pop'], [/\{/, 'delimiter.curly', '@fdict'], { include: '@root' }],
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
      // catch outdents when its ':' is typed, but only in a program without its own catch: see tuffCatchOutdent.
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
      const line = model.getLineContent(position.lineNumber);
      const before = line.slice(0, word.startColumn - 1);
      if (word.word === 'f' && /^["']/.test(line.slice(word.endColumn - 1))) { // the f of a text template
        return {
          range: new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn),
          contents: [{ value: '```tuff\n' + TUFF_TEMPLATE_DOC[0] + '\n```' }, { value: TUFF_TEMPLATE_DOC[1] }],
        };
      }
      const lib = before.match(/(\w+)\.$/);
      // A built-in's name the program gives a value (a 1.3.6 program's log = []) is the program's own variable.
      const own = TUFF_BUILTINS.includes(word.word) && givesValue(model, word.word);
      const doc = (lib && window.TUFF_LIBS[lib[1]]?.[word.word])
        || (/\w:$/.test(before) && window.TUFF_METHOD_DOCS[word.word])
        || (!own && window.TUFF_DOCS[word.word]);
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
        return { suggestions: Object.keys(window.TUFF_LIBS).filter((l) => !TUFF_READY_LIBS.includes(l)).map((l) => ({ label: l, kind: K.Module, insertText: l, range, documentation: window.TUFF_DOCS[l]?.[1] })) };
      }
      if (/\b(say|print):$/.test(before)) { // say:ascii, say:color, say:pen (1.3.5)
        return {
          suggestions: ['ascii', 'color', 'pen'].map((m) => ({
            label: m, kind: K.Method, insertText: m, range, detail: window.TUFF_METHOD_DOCS[m]?.[0], documentation: window.TUFF_METHOD_DOCS[m]?.[1],
          })),
        };
      }
      if (/\binput:$/.test(before)) { // input:color (1.4.1): the question in a look
        return { suggestions: [{ label: 'color', kind: K.Method, insertText: 'color', range, detail: 'input:color("Name? ", "green")',
          documentation: 'Asks like input, with the question in a look: colours (the letters\', then a bar behind them), "rainbow" and bold/dim/italic/underline. It gives back what was typed.' }] };
      }
      if (/\w:$/.test(before)) {
        // atgui's, tgame's and tdraw's own methods (their docs start with "atgui", "tgame" or "tdraw") only crowd the
        // list in files that use that library. A game with a panel or a screen uses atgui's widgets too. print's
        // :ascii and :pen come only after say: or print: (above).
        const src = model.getValue();
        const games = /^\s*(import|mention)\s+tgame\b/m.test(src);
        const modern = /^\s*(import|mention)\s+atgui\b/m.test(src) || (games && /:\s*(panel|screen|start_screen|main_menu)\b/.test(src));
        const drawing = /^\s*(import|mention)\s+tdraw\b/m.test(src);
        const names = Object.keys(window.TUFF_METHOD_DOCS).filter((m) => {
          const doc = window.TUFF_METHOD_DOCS[m][1] || '';
          if (m === 'ascii' || m === 'pen') return false;
          if (/^tdraw\b/.test(doc)) return drawing;
          if (/^In tgame:/.test(doc)) return games || modern;  // a name both have (align, animate...): in either's files
          return (games || !/^tgame\b/.test(doc)) && (modern || !/^atgui\b/.test(doc));
        });
        const methods = new Set([...names, 'clear', 'upper', 'lower', 'trim', 'has', 'add', 'pop']);
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
        { label: 'f"..."', kind: K.Snippet, insertText: 'f"${1:Hello} {${2:name}\\}$0"', insertTextRules: R, detail: 'Text template: values in { }', documentation: TUFF_TEMPLATE_DOC[1], range },
        { label: 'ask number', kind: K.Snippet, insertText: '${1:n} = num(input "${2:A number?} ")\nwhile ${1:n} is err:\n    say "Please type a number."\n    ${1:n} = num(input "${2:A number?} ")\n$0', insertTextRules: R, detail: 'Ask until they type a number (err)', range },
        { label: 'import anims', kind: K.Snippet, insertText: 'import anims\n', range, detail: 'Load the animations library' },
        { label: 'tap', kind: K.Snippet, insertText: 'mention tap\n\nres = tap.get("${1:https://api.github.com/users/octocat}")\nif res:ok:\n    info = res:json\n    say info:get("${2:name}")\nelse:\n    say "Error " + res:status\n', insertTextRules: R, range, detail: 'Get JSON from the web' },
        { label: 'tgame 2D', kind: K.Snippet, insertText: 'mention tgame\n\ngame = tgame.window("${1:My Game}", 600, 400)\nplayer = game:box(300, 200, 40, 40, "${2:teal}")\nscore = game:text("Score: 0", 300, 30)\n\nwhile game:open():\n    dt = game:frame()\n    if game:held("left"):\n        player:move(-300 * dt, 0)\n    if game:held("right"):\n        player:move(300 * dt, 0)\n    $0\n', insertTextRules: R, range, detail: 'A starter 2D game' },
        { label: 'tgame 3D', kind: K.Snippet, insertText: 'mention tgame\n\ngame = tgame.world("${1:My World}")\ngame:sky "${2:day}"\ngame:island(80)\nplayer = game:player("first person")\nfor i in range(1, 20):\n    tree = game:spawn("tree")\n    tree:clicked ${3:chop}\n\nfunc ${3:chop}(tree):\n    tree:shake()\n    $0\n\nwhile game:open():\n    game:frame()\n', insertTextRules: R, range, detail: 'A starter 3D world' },
        { label: 'tgui app', kind: K.Snippet, insertText: 'import tgui\n\napp = tgui.window("${1:My App}")\napp:heading "${2:Hello!}"\n\nfunc ${3:clicked}():\n    $0\n\napp:button("${4:Click me}", ${3:clicked})\n', insertTextRules: R, range, detail: 'A starter app window' },
        { label: 'atgui app', kind: K.Snippet, insertText: 'mention atgui\n\napp = atgui.window("${1:My App}", 900, 600)\napp:accent "${2:indigo}"\nside = app:sidebar(220)\nside:heading "${3:My App}"\npages = side:list(["Home", "Settings"])\npages:change opened\ntitle = app:heading "Home"\ncard = app:card\ncard:text "${4:Hello!}"\n\nfunc opened(name):\n    title:set name\n    $0\n', insertTextRules: R, range, detail: 'A modern app with a sidebar' },
      ];
      const kws = window.TUFF_KEYWORDS.map((k) => ({ label: k, kind: K.Keyword, insertText: k, range, documentation: window.TUFF_DOCS[k]?.[1] }));
      // A built-in's name the program gives a value (a 1.3.6 program's log = []) comes in below as its own name.
      const src = model.getValue();
      const builtins = TUFF_BUILTINS.filter((b) => !(src.includes(b) && givesValue(model, b)));
      const fns = builtins.map((b) => ({ label: b, kind: K.Function, insertText: `${b}($0)`, insertTextRules: R, range, detail: window.TUFF_DOCS[b]?.[0], documentation: window.TUFF_DOCS[b]?.[1] }));
      // file goes in as file: the '.' after it opens its list.
      const libs = TUFF_READY_LIBS.map((l) => ({ label: l, kind: K.Module, insertText: l, range, detail: window.TUFF_DOCS[l]?.[0], documentation: window.TUFF_DOCS[l]?.[1] }));
      const seen = new Set([...window.TUFF_KEYWORDS, ...builtins, ...TUFF_READY_LIBS]);
      const ids = [];
      for (const f of userFuncs(model)) {
        seen.add(f.name);
        ids.push({ label: f.name, kind: K.Function, insertText: `${f.name}($0)`, insertTextRules: R, range, detail: `func ${f.name}(${f.params.join(', ')})` });
      }
      for (const m of src.matchAll(/[A-Za-z_]\w{1,}/g)) {
        if (!seen.has(m[0]) && m[0] !== word.word) {
          seen.add(m[0]);
          ids.push({ label: m[0], kind: K.Variable, insertText: m[0], range });
        }
      }
      return { suggestions: [...snippets, ...kws, ...fns, ...libs, ...ids] };
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
  const own = ownTryCatch(model);
  lines.forEach((text, i) => {
    const block = tryCatchWord(text, own) ? text.search(/\S/) : -1; // where this line's try: or catch: word is
    const { kinds } = tuffScan(text); // names in a template's { } count too: f"{score}"
    for (let c = 0; c < text.length;) {
      if (kinds[c] !== 'c') { c++; continue; }
      const m = /^[A-Za-z_]\w*/.exec(text.slice(c));
      if (m && !/\w/.test(text[c - 1] || '')) {
        const prev = text[c - 1];
        const word = window.TUFF_KEYWORDS.includes(m[0]) && (!['try', 'catch'].includes(m[0]) || c === block);
        if (prev !== '.' && prev !== ':' && !word) {
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
  return valueLine(model, name);
}

// The first line that gives `name` a value: name = ..., name += ..., for name in ... or catch name:.
function valueLine(model, name) {
  const given = new RegExp(`^(\\s*(?:for\\s+)?)${name}\\s*(?:=(?!=)|[+\\-*/]=|\\s+in\\b)`);
  const caught = new RegExp(`^(\\s*catch\\s+)${name}\\s*:`);
  const lines = model.getLinesContent();
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(given) || lines[i].match(caught);
    if (m) return { line: i + 1, start: m[1].length + 1, end: m[1].length + 1 + name.length };
  }
  return null;
}

// Does the program give `name` a value of its own (a variable, a loop or catch name, a function or an input)?
// Then it's the program's name, even when Tuff has one like it: a 1.3.6 program's log = [] still renames.
function givesValue(model, name) {
  return userFuncs(model).some((f) => f.name === name || f.params.includes(name)) || !!valueLine(model, name);
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
    if (c === ')' || c === ']' || c === '}') depth++;
    else if (c === '[' || c === '{') {
      // Inside a list or a dictionary that isn't closed yet, show({"a": 1, "b": 2 is still on show's first input.
      if (depth) depth--;
      else commas = 0;
    } else if (c === '(') {
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
      const builtIn = TUFF_BUILTINS.includes(w.word) || Object.hasOwn(window.TUFF_LIBS, w.word);
      if (builtIn && !givesValue(model, w.word)) return { rejectReason: `'${w.word}' is part of Tuff, so it can't be renamed.`, range: undefined, text: '' };
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
        } else if ((m = text.match(/^([A-Za-z_]\w*)\s*=\s*(m?tgui|atgui|tgame)\.(window|world)/))) {
          symbols.push({ name: m[1], detail: `${m[2]} ${m[3]}`, kind: K.Class, range: range(line, 1, model.getLineMaxColumn(line)), selectionRange: range(line, 1, m[1].length + 1), tags: [] });
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
      const params = (inner[1].match(/("[^"]*"|[^,"])+/g) || []).map((s) => s.trim()).filter(Boolean); // t:split(",") has one input
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
      'scrollbarSlider.background': '#ffffff21',
      'scrollbarSlider.hoverBackground': '#ffffff42',
      'scrollbarSlider.activeBackground': '#' + a + 'b3',
      'scrollbar.shadow': '#00000000',
      'focusBorder': '#' + a,
    },
  });
};
