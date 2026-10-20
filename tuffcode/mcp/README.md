# TuffCode MCP server: teaching AI agents Tuff

AI coding agents like Claude Code, Codex and Antigravity don't know Tuff. TuffCode's MCP server teaches them. MCP is the standard way AI agents plug into tools, and this server gives an agent four:

| Tool | What it does |
| --- | --- |
| `tuff_reference` | The Tuff guide ([tuff-guide.md](tuff-guide.md)), plus every keyword, built-in function, library function and method. The guide covers how Tuff differs from Python, text, lists, events, pages, patterns and what Tuff can't do. |
| `tuff_examples` | 8 complete, working Tuff apps. |
| `tuff_check` | Checks code without running it. It catches syntax mistakes, names that are never set, wrong input counts, event functions that would crash, and methods that don't exist. |
| `tuff_run` | Runs a console program with typed answers and returns what it printed. |

## The easy way: inside TuffCode
1. Open **Tuff Agents** with `Ctrl+Shift+A`. If it isn't there, install it from the plugin marketplace (`Alt+3`).
2. Click the **plug button** at the top of the panel. That opens **Agent tools**.
3. **Check the tools work** runs by itself. It starts the tools exactly the way your agents do and tries every one, with a ✓ or ✗ for each step.
4. Under **Connect your agents**:
   - For Codex or Antigravity, click **Connect**. Codex's tools also show up in the **Codex app**, which shares its settings (restart the app to see "tuffcode").
   - Claude Code gets the tools automatically in the panel. **Add to the Claude app** also gives them to the Claude desktop app (its chat and its Code tab) and to `claude` in a terminal. Restart the Claude app to see "tuffcode".
5. Click **Test it**. The agent is asked to use the tools, and the panel shows which ones it really used.

The agents also work when they only came with their desktop app: TuffCode finds the copy of Claude Code inside the Claude app and the copy of Codex inside the Codex app. If one isn't signed in, the panel shows a **Sign in** button that opens its sign-in window.

## By hand
**Agent tools** shows these commands with the exact paths for your computer, plus Copy buttons, so that's the easiest place to get them. For an installed copy of TuffCode they usually look like this:

```bash
claude mcp add --scope user tuffcode -e ELECTRON_RUN_AS_NODE=1 -- "C:\Users\YOU\AppData\Local\Programs\TuffCode\TuffCode.exe" "C:\Users\YOU\AppData\Local\Programs\TuffCode\resources\app.asar.unpacked\mcp\tuff-mcp.js"
```
```bash
codex mcp add tuffcode --env ELECTRON_RUN_AS_NODE=1 -- "C:\Users\YOU\AppData\Local\Programs\TuffCode\TuffCode.exe" "C:\Users\YOU\AppData\Local\Programs\TuffCode\resources\app.asar.unpacked\mcp\tuff-mcp.js"
```
```bash
agy mcp add --env ELECTRON_RUN_AS_NODE=1 tuffcode "C:\Users\YOU\AppData\Local\Programs\TuffCode\TuffCode.exe" "C:\Users\YOU\AppData\Local\Programs\TuffCode\resources\app.asar.unpacked\mcp\tuff-mcp.js"
```

Antigravity also has to be allowed to use the tools, because it can't ask for permission when TuffCode runs it. **Connect** does this for you. By hand, add these rules to `%USERPROFILE%\.gemini\antigravity-cli\settings.json`:

```json
{ "permissions": { "allow": ["mcp(tuffcode/tuff_reference)", "mcp(tuffcode/tuff_examples)", "mcp(tuffcode/tuff_check)", "mcp(tuffcode/tuff_run)"] } }
```

**Other apps** (the Claude desktop app, Cursor, Windsurf and others): add this to the app's MCP settings file, then restart the app. Examples of that file are `%APPDATA%\Claude\claude_desktop_config.json` and `.cursor/mcp.json`. In VS Code's `mcp.json`, write `"servers"` instead of `"mcpServers"`.

```json
{
  "mcpServers": {
    "tuffcode": {
      "command": "C:\\Users\\YOU\\AppData\\Local\\Programs\\TuffCode\\TuffCode.exe",
      "args": ["C:\\Users\\YOU\\AppData\\Local\\Programs\\TuffCode\\resources\\app.asar.unpacked\\mcp\\tuff-mcp.js"],
      "env": { "ELECTRON_RUN_AS_NODE": "1" }
    }
  }
}
```

`ELECTRON_RUN_AS_NODE=1` makes TuffCode's own program run the server, so you don't need Node.js. An installed TuffCode checks and runs Tuff with its bundled runtime, so you don't need Python either.

**Running TuffCode from source?** Then:
- the command is `node` (or `tuffcode/node_modules/electron/dist/electron.exe` with `ELECTRON_RUN_AS_NODE=1`);
- the path is `tuffcode/mcp/tuff-mcp.js` in your checkout;
- Python 3 must be installed.

## Checking it works
1. See that the agent has the tools:
   - Claude Code: `claude mcp get tuffcode`
   - Codex: `codex mcp get tuffcode`
   - Antigravity: `agy mcp list`
2. Ask the agent: *"Use the tuff_reference tool, then make me a small Tuff app."* If it reads the Tuff guide first, it's working.
3. Or, in TuffCode, use **Agent tools → Run the check** and **Test it**.

If the tools don't start, run the check in Agent tools: the red step says what went wrong. The paths point at one copy of TuffCode. If you move or reinstall it, connect again, or copy the new commands.

## For developers
- [tuff-mcp.js](tuff-mcp.js) is a small stdio server: one JSON-RPC message per line, with no dependencies.
- [tuff-guide.md](tuff-guide.md) is the guide agents read first. Every example in it is checked with `tuff.py --check`.
- It reads the editor's own docs and templates from `../renderer/js/`, so agents see the same help as the editor.
- To find Tuff it uses, in order:
  1. `TUFF_CMD`, a JSON array like `["py", "-3", "-u", "C:/path/tuff.py"]`;
  2. the bundled `tuff-runtime.exe`;
  3. `py -3 ../../tuff.py`.
