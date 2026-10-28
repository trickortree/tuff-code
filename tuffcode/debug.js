// The Tuff Debugger's line to a program (1.5.0). Debug runs the program with TUFF_DEBUG=<port>, and the program
// connects back to this server on 127.0.0.1. They talk in JSON, one message to a line (tuff.py's "the debugger"
// section lists them all): the renderer's commands go to the program as they are, and what the program says comes
// back to the renderer, so its say and input stay the Run window's as in any run. One program at a time.
const net = require('net');

let session = null;

// Listens for the next program: resolves to the port to give it. first: the messages it's sent as soon as it
// connects (its breakpoints, then how it starts), and events(msg): each message it sends.
function open(first, events) {
  close();
  const s = { server: net.createServer(), socket: null, queue: [...first], events };
  session = s;
  s.server.on('connection', (sock) => {
    if (session !== s || s.socket) { sock.destroy(); return; }
    s.socket = sock;
    s.server.close(); // one program, one connection
    sock.setNoDelay(true);
    sock.setEncoding('utf8');
    let buf = '';
    sock.on('data', (data) => {
      buf += data;
      for (let i = buf.indexOf('\n'); i >= 0; i = buf.indexOf('\n')) {
        const line = buf.slice(0, i);
        buf = buf.slice(i + 1);
        let msg = null;
        try { msg = JSON.parse(line); } catch {}
        if (msg && typeof msg === 'object' && session === s) s.events(msg);
      }
    });
    sock.on('error', () => {});
    sock.on('close', () => { if (session === s) session = null; });
    for (const msg of s.queue) sock.write(JSON.stringify(msg) + '\n');
    s.queue = [];
  });
  return new Promise((resolve, reject) => {
    s.server.once('error', reject);
    s.server.listen(0, '127.0.0.1', () => resolve(s.server.address().port));
  });
}

// A command for the program (it waits for the connection): false when there's no program to send it to.
function send(msg) {
  const s = session;
  if (!s || !msg || typeof msg !== 'object') return false;
  if (s.socket) s.socket.write(JSON.stringify(msg) + '\n');
  else s.queue.push(msg);
  return true;
}

// The program has ended, or another run starts: the line closes.
function close() {
  const s = session;
  session = null;
  if (!s) return;
  try { s.server.close(); } catch {}
  s.socket?.destroy();
}

module.exports = { open, send, close };
