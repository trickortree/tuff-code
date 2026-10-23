// Speech bubbles for tgame (npc:say): a white bubble with a tail, its words wrapped onto lines, over whoever's
// talking. tuff_tgame.py's Interaction makes a group in the 3D scene for each bubble, keeps it over the one talking
// (hiding it with them), takes it away when its time is up, and sends its words with view.js(...), in order with
// its other changes: window.tgInteract.say(tv, id, text) draws the bubble in that group (the group's position is the
// tip of the tail). Everything else E does (talking, doors, grabbing and throwing) is tgame's, in Python and physics.
//
// engine.js imports this file (one line). It only uses what custom JS gets as `tv` (window.tuffView): the objects and
// three.js.

const FONT = 'Segoe UI, system-ui, sans-serif';
const SIZE = 40;      // the words, in canvas pixels
const LINE = 50;
const WIDEST = 560;   // a line wraps after this many pixels
const PAD = 26;
const TAIL = 30;      // how far the tail reaches down
const METRE = 0.0034; // canvas pixels to metres: one line of words is about 17 cm tall

// The words on lines no wider than WIDEST (a word too long for a line gets a line of its own).
function wrap(g, text) {
  const lines = [];
  for (const para of String(text).split('\n')) {
    let line = '';
    for (const word of para.split(/\s+/).filter(Boolean)) {
      const next = line ? `${line} ${word}` : word;
      if (line && g.measureText(next).width > WIDEST) { lines.push(line); line = word; } else line = next;
    }
    lines.push(line);
  }
  return lines.slice(0, 8);
}

// The bubble, drawn on a canvas: its box, its tail at the bottom middle, and the words.
function draw(text) {
  const c = document.createElement('canvas');
  const g = c.getContext('2d');
  g.font = `600 ${SIZE}px ${FONT}`;
  const lines = wrap(g, text);
  const wide = Math.max(80, ...lines.map((l) => g.measureText(l).width));
  const w = Math.ceil(wide + PAD * 2);
  const h = Math.ceil(lines.length * LINE + PAD * 1.6);
  c.width = w + 8;
  c.height = h + TAIL + 8;
  g.font = `600 ${SIZE}px ${FONT}`;
  const x = 4;
  const y = 4;
  const mid = c.width / 2;
  g.beginPath();
  g.roundRect(x, y, w, h, Math.min(34, h / 2));
  g.moveTo(mid - 20, y + h - 1);
  g.lineTo(mid - 4, y + h + TAIL);
  g.lineTo(mid + 14, y + h - 1);
  g.closePath();
  g.shadowColor = 'rgba(0, 0, 0, 0.28)';
  g.shadowBlur = 6;
  g.shadowOffsetY = 2;
  g.fillStyle = '#ffffff';
  g.fill();
  g.shadowColor = 'transparent';
  g.lineWidth = 3;
  g.strokeStyle = 'rgba(20, 24, 32, 0.22)';
  g.stroke();
  g.fillStyle = '#1d2026';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  lines.forEach((l, i) => g.fillText(l, mid, y + PAD * 0.8 + LINE * (i + 0.5) + 2));
  return c;
}

// Draws the bubble with these words in group `id` (made by tgame), in place of the one it had.
function say(tv, id, text) {
  const n = tv.objs.get(id);
  const THREE = tv.three();
  if (!n || !n.obj || !THREE || THREE.failed) return;
  if (n.bubble) n.obj.dispose();
  const canvas = draw(text);
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  // Drawn over everything, so what's said stays readable when a wall or a tree is in the way.
  const material = new THREE.SpriteMaterial({ map, transparent: true, depthWrite: false, depthTest: false });
  const s = new THREE.Sprite(material);
  s.center.set(0.5, 0);
  s.renderOrder = 1000;
  s.scale.set(canvas.width * METRE, canvas.height * METRE, 1);
  s.raycast = () => {};  // not something to click or look at: what's behind it is
  n.obj.add(s);
  n.bubble = s;
  // engine.js lets go of a group by calling its dispose(): the bubble's picture goes with it.
  n.obj.dispose = () => {
    s.removeFromParent();
    map.dispose();
    material.dispose();
    n.bubble = null;
  };
  if (n.host) n.host.dirty = true;
}

window.tgInteract = { say };
