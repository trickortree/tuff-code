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
  ];
