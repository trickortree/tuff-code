# TuffCode plugins

Plugins add panels and commands to TuffCode. The Plugins view (puzzle piece on the left, or Alt+3) lists everything in the marketplace. Install a plugin there and its panel shows up as an icon on the right edge of the window.

## What a plugin looks like

A plugin is a folder with three files:

```
my-plugin/
  plugin.json   about the plugin
  panel.js      its code
  panel.css     its styles (optional)
```

`plugin.json`:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "you",
  "description": "One or two sentences about what it does.",
  "icon": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"#000\" stroke-width=\"2\"><circle cx=\"12\" cy=\"12\" r=\"8\"/></svg>",
  "main": "panel.js",
  "style": "panel.css",
  "panels": [{ "id": "main", "title": "My Plugin" }]
}
```

The icon is an SVG. Only its shape is used: TuffCode colors it to match the theme.

`panel.js`:

```js
TuffPlugins.register('my-plugin', (t) => {
  const panel = t.panel('main', {
    title: 'My Plugin',
    mount(el) {
      el.innerHTML = '<button>Say hi</button>';
      el.querySelector('button').onclick = () => t.editor.insert('say "hi"\n');
      return { onShow() {}, onHide() {} };
    },
  });
  t.command('open', 'My Plugin: Open', () => panel.toggle(), 'Ctrl+Alt+M');
  return () => { /* clean up when the plugin is turned off */ };
});
```

## The `t` object

| | |
| --- | --- |
| `t.panel(id, { title, icon, mount })` | A panel in the right sidebar. `mount(el)` runs the first time it opens. Returns `{ open, close, toggle, isOpen, element }`. |
| `t.command(id, label, run, shortcut)` | A command for Search Everywhere (type `/`) with an optional shortcut. |
| `t.editor` | `code()`, `selection()`, `selectionLines()`, `file()`, `insert(text)`, `insertSnippet(text)` (supports `${1:placeholder}`). |
| `t.project` | `root()`, `files()`, `read(path)`, `rel(path)`. With `"permissions": ["files"]`, also `write(path, data, { encoding })`: saves text, or base64 data such as a PNG or WAV (`encoding: "base64"`), at a path inside the open project, and refreshes the project tree. |
| `t.openFile(path)`, `t.run(path)` | Open a file in a tab, or run a Tuff file. |
| `t.toast(message, kind)`, `t.ask({ title, value, confirm })` | Little messages and questions. |
| `t.reloadChanged()` | Reload open files that changed on disk. |
| `t.storage.get(key, fallback)`, `t.storage.set(key, value)` | Remember things between sessions. |
| `t.tuff` | The language tables: `keywords`, `docs`, `methods`, `libs`, `templates`. |
| `t.net` | Only for plugins with `"permissions": ["net"]`: `request({ url, method, headers, body })` gives back `{ ok, status, statusText, headers, text, ms }`. Only http and https, and 15 seconds at most. |
| `t.agents` | Only for plugins with `"permissions": ["agents"]`: run Claude Code, Codex or Antigravity (see `tuff-agents`). |

## Getting it into the marketplace

The marketplace list is [`registry.json`](registry.json) in this folder. TuffCode downloads the newest copy from the `main` branch on GitHub. To list a plugin that lives in its own GitHub repo, add an entry like this:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "you",
  "description": "…",
  "icon": "<svg …></svg>",
  "source": "https://raw.githubusercontent.com/you/my-plugin/v1.0.0/",
  "files": ["plugin.json", "panel.js", "panel.css"]
}
```

TuffCode only downloads plugins from `raw.githubusercontent.com` or `github.com`, and only the files listed. Plugins run inside TuffCode with access to the user's project, so only list plugins you've read.

## The TuffCode MCP server

`../mcp/tuff-mcp.js` is an MCP server that teaches AI agents the Tuff language. It has four tools: `tuff_reference`, `tuff_examples`, `tuff_check` and `tuff_run`. Tuff Agents connects it to Claude Code, Codex and Antigravity for you. To add it to any other MCP client, run it over stdio with TuffCode's own executable:

```json
{ "command": "C:/Path/To/TuffCode.exe", "args": ["C:/Path/To/resources/app.asar.unpacked/mcp/tuff-mcp.js"], "env": { "ELECTRON_RUN_AS_NODE": "1" } }
```
