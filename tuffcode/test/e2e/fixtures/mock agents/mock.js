// Stand-in for the Claude Code, Codex and Antigravity CLIs: answers like them and logs what it was given.
// Started through the claude/codex/agy shims next to it (.cmd on Windows, shell scripts elsewhere).
// Logs and .connected markers go to MOCK_AGENT_OUT (the launcher points it at test/e2e/out/<suite>/agents).
// It never touches a real agent's settings. The folder has a space in its name on purpose, to test path quoting.
// Model IDs a real Claude Code carries (TuffCode reads them to name the aliases): claude-opus-5-5 claude-opus-5 claude-fable-5-1 claude-sonnet-5-5 claude-haiku-5-5 claude-sonnet-4-20250514
const fs = require('fs');
const path = require('path');
const [who, ...args] = process.argv.slice(2);
const dir = process.env.MOCK_AGENT_OUT || path.join(__dirname, '..', '..', 'out', 'agents');
fs.mkdirSync(dir, { recursive: true });
const marker = path.join(dir, `${who}.connected`);
const log = (o) => fs.appendFileSync(path.join(dir, `${who}.log`), JSON.stringify(o) + '\n');
const out = (o) => process.stdout.write(JSON.stringify(o) + '\n');
if (args[0] === '--version') { console.log({ claude: '2.1.400 (Claude Code)', codex: 'codex-cli 0.99.0', agy: '1.99.0' }[who]); process.exit(0); }
if (args[0] === '--help' && who === 'claude') {
  console.log(`Usage: claude [options] [command] [prompt]
  --effort <level>                      Effort level for the current session
                                        (low, medium, high, xhigh, max)
  --model <model>                       Model for the current session. Provide
                                        an alias for the latest model (e.g.
                                        'fable', 'opus', or 'sonnet') or a
                                        model's full name.`);
  process.exit(0);
}
if (args[0] === 'debug' && args[1] === 'models') {
  console.log(JSON.stringify({ models: [
    { slug: 'gpt-mock-sol', display_name: 'GPT-Mock-Sol', visibility: 'list', default_reasoning_level: 'medium', supported_reasoning_levels: [{ effort: 'low' }, { effort: 'medium' }, { effort: 'high' }, { effort: 'ultra' }] },
    { slug: 'gpt-mock-luna', display_name: 'GPT-Mock-Luna', visibility: 'list', default_reasoning_level: 'low', supported_reasoning_levels: [{ effort: 'low' }, { effort: 'medium' }] },
    { slug: 'gpt-hidden', display_name: 'Hidden', visibility: 'hide', supported_reasoning_levels: [] },
  ] }));
  process.exit(0);
}
// Antigravity lists one line per model and thinking level.
if (who === 'agy' && args[0] === 'models') {
  console.log(['Fetching models...', 'gemini-mock-flash-low  Gemini Mock Flash (Low)', 'gemini-mock-flash-high  Gemini Mock Flash (High)', 'gemini-mock-pro  Gemini Mock Pro'].join('\n'));
  process.exit(0);
}
if (args[0] === 'login') {
  if (args[1] !== 'status') { log({ login: args }); process.exit(0); }
  console.log(process.env.MOCK_SIGNED_OUT ? 'Not logged in' : 'Logged in using ChatGPT');
  process.exit(process.env.MOCK_SIGNED_OUT ? 1 : 0);
}
if (args[0] === 'auth') { console.log(JSON.stringify({ loggedIn: !process.env.MOCK_SIGNED_OUT })); process.exit(0); }
if (args[0] === 'mcp') {
  log({ mcp: args.slice(1) });
  if (args[1] === 'get') process.exit(fs.existsSync(marker) ? 0 : 1);
  if (args[1] === 'list') { console.log(fs.existsSync(marker) ? 'tuffcode: connected' : 'No MCP servers configured.'); process.exit(0); }
  if (args[1] === 'add') { fs.writeFileSync(marker, JSON.stringify(args)); console.log('added'); process.exit(0); }
  if (args[1] === 'remove') { fs.rmSync(marker, { force: true }); process.exit(0); }
  process.exit(0);
}
let stdin = '';
process.stdin.on('data', (d) => (stdin += d));
process.stdin.on('end', async () => {
  // Antigravity takes the prompt on the command line (--print=...), the others on stdin.
  const printArg = args.find((a) => a.startsWith('--print='));
  const prompt = printArg ? printArg.slice('--print='.length) : stdin;
  log({ args, cwd: process.cwd(), prompt });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  if (who === 'claude') {
    let mcpCfg = null;
    const i = args.indexOf('--mcp-config');
    if (i >= 0) mcpCfg = JSON.parse(fs.readFileSync(args[i + 1], 'utf8'));
    out({ type: 'system', subtype: 'init', session_id: 'sess-123', model: args.includes('--model') ? { fable: 'claude-fable-5-1', opus: 'claude-opus-5-5', sonnet: 'claude-sonnet-5-5', haiku: 'claude-haiku-5-5' }[args[args.indexOf('--model') + 1]] : 'claude-opus-5-5', mcp_servers: [{ name: 'tuffcode', status: mcpCfg?.mcpServers?.tuffcode ? 'connected' : 'failed' }] });
    out({ type: 'assistant', message: { content: [{ type: 'tool_use', id: 't1', name: 'mcp__tuffcode__tuff_reference', input: {} }] } });
    out({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 't1', content: 'ok' }] } });
    out({ type: 'assistant', message: { content: [{ type: 'tool_use', id: 't2', name: 'Read', input: { file_path: path.join(process.cwd(), 'main.tuf') } }] } });
    out({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 't2', content: 'ok' }] } });
    const text = "Here's a **friendlier** greeting:\n\n```tuff\nsay \"Hi there!\"\n```\n\n- It uses `say`\n- It's short";
    for (const chunk of text.match(/[\s\S]{1,9}/g)) { out({ type: 'stream_event', event: { type: 'content_block_delta', delta: { type: 'text_delta', text: chunk } } }); await sleep(15); }
    out({ type: 'stream_event', event: { type: 'content_block_stop' } });
    if (args.includes('acceptEdits')) {
      out({ type: 'assistant', message: { content: [{ type: 'tool_use', id: 't3', name: 'Edit', input: { file_path: path.join(process.cwd(), 'main.tuf') } }] } });
      fs.appendFileSync(path.join(process.cwd(), 'main.tuf'), '\nsay "added by the agent"\n');
      out({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 't3', content: 'ok' }] } });
    }
    if (stdin.includes('SLOW')) await sleep(20000);
    out({ type: 'result', subtype: 'success', is_error: false, result: text, session_id: 'sess-123', total_cost_usd: 0.01 });
  } else if (who === 'agy') {
    out({ event: 'init', conversation_id: 'conv-1' });
    out({ event: 'step_update', step_update: { step_index: 0, step_type: 'agent_response', text_delta: 'Antigravity says: hello from the stand-in.' } });
    out({ event: 'result', result: { status: 'success', response: 'Antigravity says: hello from the stand-in.', conversation_id: 'conv-1' } });
  } else {
    out({ type: 'thread.started', thread_id: 'th-1' });
    out({ type: 'turn.started' });
    out({ type: 'item.started', item: { id: 'i1', type: 'mcp_tool_call', server: 'tuffcode', tool: 'tuff_check', arguments: { file: 'main.tuf' }, status: 'in_progress' } });
    out({ type: 'item.completed', item: { id: 'i1', type: 'mcp_tool_call', server: 'tuffcode', tool: 'tuff_check', status: 'completed' } });
    out({ type: 'item.started', item: { id: 'i2', type: 'command_execution', command: 'py tuff.py main.tuf', status: 'in_progress' } });
    out({ type: 'item.completed', item: { id: 'i2', type: 'command_execution', command: 'py tuff.py main.tuf', exit_code: 1, status: 'failed' } });
    out({ type: 'item.completed', item: { id: 'i3', type: 'agent_message', text: 'Codex says: your code looks fine.' } });
    out({ type: 'turn.completed', usage: {} });
  }
});
