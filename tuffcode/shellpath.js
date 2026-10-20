// Apps opened from the Mac Dock or Finder get a bare PATH (/usr/bin:/bin:/usr/sbin:/sbin), so Python,
// Homebrew and the AI agents (claude, codex, agy) wouldn't be found. This reads PATH from the login
// shell in the background, so the window opens straight away; code that runs those tools awaits
// ready() first. A shell that hangs is killed (with everything it started) after 10 seconds.
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

let ready = Promise.resolve();

function withExtras(p) {
  const have = String(p || '').split(':').filter(Boolean);
  for (const d of ['/opt/homebrew/bin', '/usr/local/bin', path.join(os.homedir(), '.local', 'bin')]) if (!have.includes(d)) have.push(d);
  return have.join(':');
}

function start() {
  if (process.platform === 'win32') return ready;
  process.env.PATH = withExtras(process.env.PATH); // good enough until the shell answers
  const shell = process.env.SHELL || '/bin/zsh';
  // nushell, xonsh and elvish don't expand "$PATH" the POSIX way; ask zsh instead.
  const sh = /\/(nu|xonsh|elvish)$/.test(shell) ? '/bin/zsh' : shell;
  const args = /\/t?csh$/.test(sh) ? ['-c', 'printf "@@%s@@" "$PATH"'] : ['-ilc', 'printf "@@%s@@" "$PATH"'];
  ready = new Promise((resolve) => {
    let child;
    try {
      child = spawn(sh, args, { detached: true, stdio: ['ignore', 'pipe', 'ignore'], env: { ...process.env, DISABLE_AUTO_UPDATE: 'true' } });
    } catch {
      resolve();
      return;
    }
    let out = '';
    let finished = false;
    const kill = () => { try { process.kill(-child.pid, 'SIGKILL'); } catch {} };
    const finish = () => { if (finished) return; finished = true; clearTimeout(timer); resolve(); };
    const timer = setTimeout(() => { kill(); finish(); }, 10000);
    child.stdout.on('data', (d) => {
      out += d;
      const m = /@@(.*?)@@/.exec(out);
      if (!m) return;
      // Only trust an answer that looks like a real PATH.
      if (m[1].split(':').includes('/usr/bin')) process.env.PATH = withExtras(m[1]);
      kill();
      finish();
    });
    child.on('error', finish);
    child.on('close', finish);
  });
  return ready;
}

module.exports = { start, ready: () => ready };
