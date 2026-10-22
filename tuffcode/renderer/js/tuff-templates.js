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
];
