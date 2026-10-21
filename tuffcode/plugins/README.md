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
  "panels": [{ "id": "main", "title": "My Plugin" }],
  "permissions": ["files"]
}
```

The icon is an SVG. Only its shape is used: TuffCode colors it to match the theme.

`permissions` (optional) asks for the parts of `t` that only some plugins need: `"files"` (`t.project.write`), `"net"` (`t.net`) and `"agents"` (`t.agents`). They decide what `t` has, and nothing more: they are not a sandbox. A plugin runs in TuffCode's own page, with everything the page can reach, so whatever it asks for, its code can do anything TuffCode can. That's why the marketplace only lists plugins someone has read, and why you should only install ones you trust.

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
| `t.editor` | `code()`, `selection()`, `selectionLines()`, `file()`, `insert(text)`, `insertSnippet(text)` (supports `${1:placeholder}`), `replaceAll(text)` (one step Ctrl+Z undoes). |
| `t.project` | `root()`, `files()`, `read(path)` (the file's text: UTF-8, UTF-16 with a BOM and Windows-1252 files all come back as the right text; it's for text, so a picture's bytes don't survive it), `rel(path)`. |
| `t.project.write(path, data, { encoding })` | Only for plugins with `"permissions": ["files"]`. Saves text (`encoding: "utf8"`, the default, saved as UTF-8) or base64 data such as a PNG or WAV (`encoding: "base64"`) inside the open project: `path` is relative to the project folder (or a full path inside it), and any folders on the way are made. Anywhere outside the open project is refused (the promise rejects). Gives back the full path it saved, and reloads open tabs and the project tree. |
| `t.openFile(path, line)`, `t.run(path)` | Open a file in a tab (with `line`, the cursor goes to that line, like a `main.tuf:12` link), or run a Tuff file. |
| `t.openWeb(url)` | Open an `http://` or `https://` page in the web browser. It leaves TuffCode, so only do it when the user clicked a link, and ask first. Gives back `false` for anything else. |
| `t.toast(message, kind)`, `t.ask({ title, value, confirm })` | Little messages and questions. |
| `t.reloadChanged()` | Reload open files that changed on disk. |
| `t.storage.get(key, fallback)`, `t.storage.set(key, value)` | Remember things between sessions. |
| `t.tuff` | The language tables: `keywords`, `docs`, `methods`, `libs`, `templates`. |
| `t.net` | Only for plugins with `"permissions": ["net"]`: `request({ url, method, headers, body })` gives back `{ ok, status, statusText, headers, text, ms }`. Only http and https, and 15 seconds at most. |
| `t.agents` | Only for plugins with `"permissions": ["agents"]`: run Claude Code, Codex or Antigravity (see `tuff-agents`). |

## Getting it into the marketplace

The marketplace list is [`registry.json`](registry.json) in this folder. TuffCode shows the copy it comes with straight away, and starts the plugins you installed, without waiting for the network. It also asks for the newest copy from the `main` branch on GitHub, and adds what's new there to the marketplace when it comes (the refresh button in the Plugins view asks again).

`registry.json` has two lists:

- `plugins`: plugins that work in every TuffCode.
- `newer`: plugins that need a newer TuffCode, each with `"needs"`: the first version that has everything it uses, like `"needs": "1.0.4"`. TuffCode 1.0.3 and older read only `plugins`, also from the `main` branch, and offer to download any entry there they didn't come with, so a plugin that uses something new must go in `newer`, never in `plugins`. TuffCode 1.0.4 and newer read both lists and leave out the entries that need a newer version than themselves.

To list a plugin that lives in its own GitHub repo, add an entry like this:

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
