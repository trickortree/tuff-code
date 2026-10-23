// Starter apps for the Design Studio's template gallery. Also shared with AI agents through
// the TuffCode MCP server (mcp/tuff-mcp.js) as examples of good Tuff code, so keep them runnable.
window.TUFF_TEMPLATES = [
    { id: 'counter', name: 'Counter', desc: 'Two buttons that count up and down.', code: `mention mtgui

app = mtgui.window("Counter", 360, 400)
app:accent "purple"
app:heading "Counter"
app:small "Press the buttons to count up and down."
count = app:heading "0"
row = app:row
row:button("-", down, "secondary")
row:button("+", up, "primary")
app:button("Reset", reset, "ghost")

n = 0

func up():
    n += 1
    count:set text(n)

func down():
    n -= 1
    count:set text(n)

func reset():
    n = 0
    count:set "0"
` },
    { id: 'login', name: 'Sign in', desc: 'A username box, a password box and a sign-in button.', code: `mention mtgui

app = mtgui.window("Sign in", 380, 470)
app:accent "blue"
app:heading "Welcome back"
app:small "Sign in to continue."
user = app:input "Username"
password = app:input "Password"
remember = app:checkbox("Remember me", true)
app:button("Sign in", sign_in, "primary")
status = app:small ""
password:enter sign_in

func sign_in():
    if user:value is "":
        status:set "Type your username first."
    else:
        status:set "Hi " + user:value + "! You're signed in."
` },
    { id: 'todo', name: 'To-do list', desc: 'Type tasks and tick them off.', code: `mention mtgui

app = mtgui.window("To-do list", 420, 560)
app:accent "green"
app:heading "To-do list"
app:small "Type a task, then press Enter or Add."
row = app:row
task = row:input "New task"
row:button("Add", add_task, "primary")
tasks = app:card
summary = app:small "No tasks yet"
task:enter add_task

count = 0

func add_task():
    if task:value is "":
        return
    tasks:checkbox(task:value, false)
    task:clear
    count += 1
    if count is 1:
        summary:set "1 task"
    else:
        summary:set text(count) + " tasks"
` },
    { id: 'pizza', name: 'Pizza order', desc: 'A form with a dropdown, checkboxes and a slider.', code: `mention mtgui

app = mtgui.window("Pizza order", 400, 600)
app:accent "orange"
app:heading "Build your pizza"
app:small "Pick a size and toppings, then order."
name = app:input "Your name"
size = app:dropdown(["Small", "Medium", "Large"], "Medium")
toppings = app:card
cheese = toppings:checkbox("Extra cheese", true)
pepperoni = toppings:checkbox("Pepperoni", false)
app:small "How spicy?"
spice = app:slider(0, 10, 3)
row = app:row
row:button("Order", order, "primary")
row:button("Clear", clear, "ghost")
status = app:text ""

func order():
    status:set "Thanks " + name:value + "! Your " + size:value + " pizza is on its way."

func clear():
    name:clear
    status:set ""
` },
    { id: 'clock', name: 'Clock', desc: 'An analog and a digital clock you can pause and speed up.', code: `mention mtgui

app = mtgui.window("Clock", 380, 560)
app:accent "teal"
app:heading "Clock"
big = app:clock("analog", 200)
small = app:clock("digital")
row = app:row
row:button("Pause", pause, "secondary")
row:button("Resume", resume, "primary")
fast = app:toggle("Super speed", false)
fast:change speed_up

func pause():
    big:pause
    small:pause

func resume():
    big:resume
    small:resume

func speed_up():
    if fast:value:
        big:speed 60
        small:speed 60
    else:
        big:speed 1
        small:speed 1
` },
    { id: 'settings', name: 'Settings page', desc: 'Switches, a volume slider and a language picker.', code: `mention mtgui

app = mtgui.window("Settings", 420, 620)
app:heading "Settings"
card = app:card
dark = card:toggle("Dark mode", true)
sounds = card:toggle("Sound effects", true)
card:divider
card:small "Volume"
volume = card:slider(0, 100, 70)
level = card:progress(70)
language = app:dropdown(["English", "Espanol", "Francais"], "English")
app:button("Save", save, "primary")
saved = app:small ""
dark:change switch_theme
volume:change show_volume

func switch_theme():
    if dark:value:
        app:theme "dark"
    else:
        app:theme "light"

func show_volume():
    level:set volume:value

func save():
    saved:set "Saved! Language: " + language:value
` },
    { id: 'quiz', name: 'Quiz', desc: 'A question with answer buttons and a score bar.', code: `mention mtgui

app = mtgui.window("Quick quiz", 420, 480)
app:accent "pink"
app:heading "Quick quiz"
question = app:text "What is 7 x 8?"
row = app:row
row:button("54", wrong, "outline")
row:button("56", right, "outline")
row:button("63", wrong, "outline")
result = app:text ""
bar = app:progress(0)

func right():
    result:set "Correct!"
    bar:set 100

func wrong():
    result:set "Not quite, try again."
    bar:set 30
` },
    { id: 'shop', name: 'Pizza shop (pages)', desc: 'Three pages: Home, Menu and Cart. Buttons switch between them.', code: `mention mtgui

app = mtgui.window("Pizza shop", 400, 560)
app:accent "orange"
app:heading "Tony's Pizza"
home = app:page "Home"
home:text "Hot pizza, made to order."
home:button("See the menu", go_menu, "primary")
home:button("Your cart", go_cart, "ghost")
menu = app:page "Menu"
menu:small "Pick a pizza to put it in your cart."
menu:button("Margherita  $8", add_margherita, "outline")
menu:button("Pepperoni  $10", add_pepperoni, "outline")
menu:button("Back", go_home, "ghost")
cart = app:page "Cart"
summary = cart:text "Your cart is empty."
cart:button("Order now", order, "primary")
cart:button("Keep shopping", go_menu, "ghost")
cart:opened show_cart

items = 0
total = 0

func go_home():
    home:open

func go_menu():
    menu:open

func go_cart():
    cart:open

func add_margherita():
    items += 1
    total += 8
    go_cart()

func add_pepperoni():
    items += 1
    total += 10
    go_cart()

func show_cart():
    if items is 0:
        summary:set "Your cart is empty."
    elif items is 1:
        summary:set "1 pizza, $" + text(total)
    else:
        summary:set text(items) + " pizzas, $" + text(total)

func order():
    if items is 0:
        app:alert "Add a pizza first!"
    else:
        app:alert "Thanks! Your order is on its way."
        items = 0
        total = 0
        home:open
` },
];

// tgame games, only for AI agents (the MCP server's tuff_examples puts them after the apps above). The Design
// Studio shows the apps; games start from Tuff Engine's own templates. Keep them runnable too.
window.TUFF_GAME_EXAMPLES = [
    { id: 'hills_and_lake', name: 'Hills and lake (3D)', desc: 'A tgame 3D world with modern lighting and land made in code (world:terrain): a hill, a mountain, a lake, a valley and a brush stroke, trees standing on the land, and a player who chops them.', code: `mention tgame

game = tgame.world("Hills and Lake")
game:sky "day"
game:lighting "modern"                     # soft light from the sky and sharper shadows
land = game:terrain(200)                   # flat land 200 wide, around 0, 0
land:style "grass"                         # grass, desert, snow, rocky or autumn
land:hill(30, -20, 40, 10)                 # x, z, size (how wide), height
land:mountain(-55, -55, 70, 40)            # rocky, with a snowy top
land:lake(-30, 35, 40, 4)                  # x, z, size, depth: a hollow with water in it
land:valley(20, 30, 90, 70, 18, 6)         # from x1, z1 to x2, z2, then width and depth
land:raise([[60, -60], [70, -55], [80, -45]], 10, 2)   # a brush stroke: a ridge

player = game:player("third person")       # walks over the hills, but not into the lake
game:spawn("hut", 6, 0, -6)                # y 0 is on the land
game:spawn("tree", 30, 0, -20)             # on the hilltop
for i in range(1, 25):
    tree = game:spawn("pine")              # somewhere random on dry land
    tree:clicked chop

logs = 0
logs_label = game:hud():text("Logs: 0", 90, 30)

func chop(tree):
    if tree:distance(player) < 4 and not tree:fallen():
        tree:shake()
        tree:fall()
        tree:regrow(8)
        logs += 1
        logs_label:set "Logs: " + logs

while game:open():
    game:frame()
` },
    { id: 'apple_shop', name: 'Apple shop (menus and screens)', desc: 'A tgame 2D game with real UI: a click-to-play start screen, a panel pinned to the top left with the coins and a Shop button, a shop screen that pauses the game while it shows, and a game over screen with Play again. Every atgui widget works on a panel or a screen.', code: `mention tgame

game = tgame.window("Apple Shop", 640, 480)
game:background "sky"
basket_width = 80
basket = game:box(320, 450, basket_width, 20, "wood")
basket:on_edge "stop"
apple = game:circle(320, 0, 12, "red")
coins = 0
speed = 300                                # how fast the basket moves
misses = 0

# Click to play: a title screen over the game. The game waits behind it until it's clicked.
start = game:start_screen("Apple Shop", "Click to play")
start:text "Catch apples with the arrow keys. Miss 3 and it's game over."

# A panel: real widgets pinned to the top left. Clicks on them go to them; clicks anywhere else reach the game.
bar = game:panel("top left")
coins_label = bar:heading "Coins: 0"
lives = bar:progress(100)
bar:button("Shop", open_shop):icon "cart"

# The shop: a screen over the whole game. It pauses the game while it shows.
shop = game:screen("Shop")
shop:text "Spend your coins on a better basket."
row = shop:row()
row:button("Wider basket (5)", buy_wider)
row:button("Faster basket (8)", buy_faster, "gradient")
shop:button("Back to the game", close_shop, "secondary")
shop:hide()                                # screens start shown

# Game over is a screen too.
over = game:screen("Game over")
caught_text = over:text ""
over:button("Play again", play_again)
over:hide()

func open_shop():
    shop:show()

func close_shop():
    shop:hide()

func add_coins(n):
    coins += n
    coins_label:set "Coins: " + coins

func buy_wider():
    if coins < 5:
        game:sound "lose"
    else:
        add_coins(-5)
        basket_width += 30
        basket:size(basket_width, 20)
        game:sound "powerup"

func buy_faster():
    if coins < 8:
        game:sound "lose"
    else:
        add_coins(-8)
        speed += 150
        game:sound "powerup"

func play_again():
    misses = 0
    lives:set 100
    add_coins(-coins)
    over:hide()
    start:show()                           # back to the title screen

func step(dt):                             # dt is 0 while a screen pauses the game
    if game:held("left"):
        basket:move(-speed * dt, 0)
    if game:held("right"):
        basket:move(speed * dt, 0)
    apple:move(0, 220 * dt)
    if apple:touches(basket):
        add_coins(1)
        game:sound "coin"
        apple:move_to(random(20, 620), 0)
    elif apple:y() > 480:
        misses += 1
        lives:set 100 - misses * 33
        apple:move_to(random(20, 620), 0)
        if misses >= 3:
            caught_text:set "You have " + coins + " coins."
            over:show()

game:every_frame step
` },
    { id: 'car_smash', name: 'Car smash (physics, 3D)', desc: 'A tgame 3D world with real physics: a car you drive with the arrow keys into towers of crates that fall and tumble (thing:physics(), :mass, :friction, :bounce), a bouncy ball, a ragdoll that flops over, crate:on_hit counting the crates knocked over, an explosion on B (world:explode) and car:flip on F.', code: `mention tgame

game = tgame.world("Car Smash", 960, 600)
game:sky "day"
game:lighting "modern"
land = game:terrain(160)                   # with physics on, the land is solid
land:hill(45, 10, 40, 6)                   # a hill to drive up
game:gravity(-9.8)                         # how strong gravity is (this is the default)

# Towers of crates: physics things fall, tumble and get knocked over.
towers = [[0, -20], [-12, -30], [12, -34]]
for spot in towers:
    for i in range(0, 5):
        crate = game:box(spot[0], i * 1.05, spot[1], 1, "wood")
        crate:physics()                    # it falls and can be pushed
        crate:mass(1.5)                    # kg
        crate:friction(0.6)
        crate:on_hit(crate_hit)

ball = game:sphere(-6, 0, -10, 1.2, "red"):physics()   # physics() gives back the thing
ball:bounce(0.7)                           # 0 doesn't bounce, 1 bounces right back up
dummy = game:ragdoll(6, 0, -16, "blue")    # a person made of parts that flops when it's hit

car = game:car(0, 1, 6, "orange")
car:drive()                                # the arrow keys or WASD drive it, and the camera follows
car:engine(1.5)                            # a bit more power than normal
car:on_hit(car_hit)

hud = game:hud()
score_label = hud:text("Knocked: 0", 100, 30)
speed_label = hud:text("Speed: 0 km/h", 100, 64)
hud:text("Arrows drive, F flips the car, B goes boom", 480, 580, 18)
score = 0

func crate_hit(other, strength):           # what hit it, and how hard
    if strength > 3:
        score += 1
        score_label:set "Knocked: " + score

func car_hit(other, strength):
    if strength > 20:
        game:sound "hit"

func flip(key):
    car:flip()                             # back on its wheels

func boom(key):
    game:explode(car:x(), 0, car:z() - 6, 25, 10)   # pushes everything near it away
    game:sound "boom"

func step(dt):
    speed_label:set "Speed: " + round(car:speed()) + " km/h"

game:on_key("f", flip)
game:on_key("b", boom)
game:every_frame step
` },
    { id: 'snow_course', name: 'Snowy obstacle course (game kit, 3D)', desc: 'A tgame 3D world built from the game kit: snow at sunset (world:weather, :time_of_day), a person who talks when you press E (:say, :on_talk), a jump pad, a boost pad and a moving platform (:path), a key that opens a locked door (:needs), a countdown, a minimap and an arrow to what to find next, a snowman with a health bar, and pop_text, slow_mo and shake when you win.', code: `mention tgame

game = tgame.world("Snowy Course", 960, 600)
game:sky "sunset"
land = game:terrain(140, "snow")
game:weather("snow", 1.2)                  # "rain", "snow" or "none", then how strong (0 to 2)
game:time_of_day(17)                       # 5 pm: a low sun
player = game:player("third person")
map = game:minimap(160, "top left")        # the land and the player, in a corner

coach = game:spawn("person", 0, 0, 4)
coach:say("Press E to talk to me!", 0)     # 0 keeps the bubble up
coach:on_talk(coach_talk)

pad = game:jump_pad(0, 0, -6, 12)          # launches you up onto the ledge
ledge = game:box(0, 0, -14, [8, 3, 6], "stone")
boost = game:boost_pad(0, 3, -12, 22)      # shoots you along the ledge
boost:turn(180)
lift = game:box(0, 3, -22, [4, 0.4, 4], "wood")
lift:path([[0, 3, -22], [12, 6, -22], [12, 6, -34]], 3, "loop")   # round and round, and you ride it
key = game:spawn("key", 12, 6, -34)        # walk into it to pick it up
map:mark(key, "gold")
door = game:door(0, 0, -44, "wood")
door:needs(key)                            # "Locked!" until you have the key
goal = game:spawn("chest", 0, 0, -50)
arrow = game:arrow_to(key)                 # an arrow at the screen's edge, with how far it is

snowman = game:sphere(-6, 0, -2, 1.2, "snow")
snowman:health_bar(3)                      # click it three times
snowman:clicked melt
snowman:on_death(melted)

clock = game:countdown(120, times_up)      # top right; red under 10 seconds
has_key = false
done = false

func coach_talk():
    coach:say("Jump pad, boost pad, ride the lift, grab the key, open the door!", 6)

func melt(thing):
    snowman:hurt(1)
    game:pop_text("-1", snowman:spot(), "red")

func melted():
    snowman:hide()
    clock:add(10)
    game:pop_text("+10 s", -6, 1, -2, "gold")

func times_up():
    game:pause("Out of time!")

func step(dt):
    if not has_key and player:distance(key) < 1.5:
        has_key = true
        game:pop_text("Got the key!", player:spot(), "gold")
        map:unmark(key)
        game:arrow_to(goal)                # the arrow points at the chest now
    if not done and player:touches(goal):
        done = true
        clock:stop()
        arrow:hide()
        game:slow_mo(0.3, 2)               # everything at 30% for 2 seconds
        game:shake(0.5)
        game:pop_text("You made it!", goal:spot(), "gold", 2)

game:every_frame step
` },
];
