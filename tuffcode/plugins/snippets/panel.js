// Snippet Library: ready-made Tuff you can insert, plus your own saved snippets.
// Snippets use editor placeholders: ${1:name} is a spot you can Tab through after inserting.
TuffPlugins.register('snippets', (t) => {
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const plain = (s) => s.replace(/\$\{\d+:([^}]*)\}/g, '$1').replace(/\$\{?\d+\}?/g, '');

  const LIBRARY = [
    ['Basics', [
      ['Say hello', 'say "Hello, ${1:world}!"'],
      ['Ask a question', '${1:name} = input "${2:What is your name?} "\nsay "Nice to meet you, " + ${1:name} + "!"'],
      ['If / else', '${1:score} = ${2:12}\nif ${1:score} > ${3:10}:\n    say "${4:Big!}"\nelse:\n    say "${5:Small}"'],
      ['Count with for', 'for ${1:i} in range(1, ${2:10}):\n    say ${1:i}'],
      ['Repeat with while', '${1:n} = ${2:3}\nwhile ${1:n} > 0:\n    say ${1:n}\n    ${1:n} -= 1'],
      ['Function', 'func ${1:double}(${2:n}):\n    ${3:n * 2}'],
      ['Random dice roll', 'roll = random(1, 6)\nsay "You rolled " + text(roll)'],
    ]],
    ['Text and lists', [
      ['Go through a list', '${1:fruits} = [${2:"apple", "banana", "cherry"}]\nfor ${3:item} in ${1:fruits}:\n    say ${3:item}'],
      ['Number from input', '${1:age} = number(input "${2:How old are you?} ")\nsay "Next year you will be " + text(${1:age} + 1)'],
      ['Guessing game', 'secret = random(1, 10)\nguess = number(input "Guess 1 to 10: ")\nwhile guess is not secret:\n    if guess < secret:\n        say "Higher!"\n    else:\n        say "Lower!"\n    guess = number(input "Guess again: ")\nsay "You got it!"'],
    ]],
    ['Live lines', [
      ['Loading then done', 'line = say "${1:Loading}..."\nwait(${2:1})\nline:rewrite "${3:Done!}"'],
      ['Countdown', 'line = say "3"\nfor n in [2, 1]:\n    wait(1)\n    line:rewrite text(n)\nwait(1)\nline:rewrite "${1:Go!}"'],
      ['Spinner animation', 'import anims\nanims.loading("${1:Thinking}", ${2:2})'],
    ]],
    ['App windows', [
      ['App window', 'mention mtgui\n\napp = mtgui.window("${1:My App}", ${2:400}, ${3:500})\napp:accent "${4:purple}"\napp:heading "${5:Hello!}"\n$0'],
      ['Button with a function', 'app:button("${1:Click me}", ${2:clicked}, "primary")\n\nfunc ${2:clicked}():\n    ${3:app:alert "Clicked!"}'],
      ['Text box + Enter', '${1:name} = app:input "${2:Type your name}"\n${3:greeting} = app:text ""\n${1:name}:enter ${4:greet}\n\nfunc ${4:greet}():\n    ${3:greeting}:set "Hi " + ${1:name}:value + "!"'],
      ['Switch that does something', '${1:dark} = app:toggle("${2:Dark mode}", true)\n${1:dark}:change ${3:switched}\n\nfunc ${3:switched}():\n    if ${1:dark}:value:\n        app:theme "dark"\n    else:\n        app:theme "light"'],
      ['Slider moves a bar', '${1:volume} = app:slider(0, 100, 50)\n${2:bar} = app:progress(50)\n${1:volume}:change ${3:moved}\n\nfunc ${3:moved}():\n    ${2:bar}:set ${1:volume}:value'],
      ['Row of buttons', '${1:row} = app:row\n${1:row}:button("${2:Yes}", ${3:yes}, "primary")\n${1:row}:button("${4:No}", ${5:no}, "ghost")\n\nfunc ${3:yes}():\n    app:alert "You picked ${2:Yes}"\n\nfunc ${5:no}():\n    app:alert "You picked ${4:No}"'],
      ['Timer that ticks', '${1:ticks} = 0\n${2:label} = app:text "0"\napp:every(${3:1}, ${4:tick})\n\nfunc ${4:tick}():\n    ${1:ticks} += 1\n    ${2:label}:set text(${1:ticks})'],
      ['Pages and a button to switch', '${1:home} = app:page "${2:Home}"\n${1:home}:heading "${3:Welcome}"\n${4:about} = app:page "${5:About}"\n${4:about}:text "${6:Made with Tuff}"\n${1:home}:button("${7:About}", go_${4:about}, "primary")\n${4:about}:button("Back", go_${1:home}, "ghost")\n\nfunc go_${4:about}():\n    ${4:about}:open\n\nfunc go_${1:home}():\n    ${1:home}:open'],
      ['Card with a list', '${1:card} = app:card\n${1:card}:heading "${2:Today}"\n${1:card}:checkbox("${3:Homework}", false)\n${1:card}:checkbox("${4:Walk the dog}", false)'],
    ]],
  ];

  let root = null;
  let query = '';

  const panel = t.panel('library', {
    title: 'Snippets',
    mount(el) {
      root = el;
      el.innerHTML = `<div class="sn">
        <label class="sn-search"><input placeholder="Search snippets" spellcheck="false"></label>
        <div class="sn-list"></div>
        <div class="sn-foot"><button class="btn sm" data-a="save">Save selection as snippet</button></div>
      </div>`;
      el.querySelector('input').oninput = (e) => { query = e.target.value.trim().toLowerCase(); render(); };
      el.querySelector('input').onkeydown = (e) => e.stopPropagation();
      el.querySelector('[data-a="save"]').onclick = saveSelection;
      el.querySelector('.sn-list').onclick = onClick;
      render();
      return {};
    },
  });
  t.command('open', 'Snippets: Open', () => panel.toggle());

  const mine = () => t.storage.get('mine', []);

  function groups() {
    const own = mine().map((s) => [s.name, s.body, true]);
    return [...(own.length ? [['My snippets', own]] : []), ...LIBRARY];
  }

  function render() {
    const list = root.querySelector('.sn-list');
    let html = '';
    groups().forEach(([cat, items], gi) => {
      const shown = items.map((it, i) => [it, i]).filter(([[name, body]]) => !query || `${cat} ${name} ${body}`.toLowerCase().includes(query));
      if (!shown.length) return;
      html += `<div class="sn-cat">${esc(cat)}</div>`;
      for (const [[name, body, own], i] of shown) {
        html += `<div class="sn-item" data-g="${gi}" data-i="${i}">
          <div class="sn-h"><b>${esc(name)}</b>
            ${own ? '<button data-a="del" title="Delete this snippet">Delete</button>' : ''}
            <button data-a="copy">Copy</button><button data-a="insert" class="primary">Insert</button></div>
          <pre>${esc(plain(body))}</pre></div>`;
      }
    });
    list.innerHTML = html || '<div class="sn-empty">No snippets match.</div>';
  }

  function onClick(e) {
    const b = e.target.closest('button');
    const item = e.target.closest('.sn-item');
    if (!b || !item) return;
    const [, items] = groups()[+item.dataset.g];
    const [name, body] = items[+item.dataset.i];
    if (b.dataset.a === 'insert') t.editor.insertSnippet(body);
    if (b.dataset.a === 'copy') { navigator.clipboard.writeText(plain(body)); t.toast('Copied.', 'ok', 1500); }
    if (b.dataset.a === 'del') {
      t.storage.set('mine', mine().filter((s) => s.name !== name));
      render();
    }
  }

  async function saveSelection() {
    const body = t.editor.selection();
    if (!body.trim()) { t.toast('Select some code in the editor first.'); return; }
    const name = await t.ask({ title: 'Name this snippet', value: body.trim().split('\n')[0].slice(0, 40) });
    if (!name) return;
    t.storage.set('mine', [...mine().filter((s) => s.name !== name), { name, body: body.replace(/\$/g, '\\$') }]);
    t.toast(`Saved "${name}".`, 'ok');
    render();
  }
});
