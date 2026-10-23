// Real physics for tgame: Rapier 0.21 (tuff_view_web/rapier/, Apache-2.0). engine.js imports this file, and this file
// imports Rapier, only once a game turns physics on, so a game without physics never loads either.
//
// The page owns what physics moves. It steps the world at a fixed 60 Hz (catching up a few steps after a slow frame,
// never more), draws each body where it is (smoothed between steps, for screens faster than 60 Hz), and once a frame
// tells Python where its physics things went and what hit what, in one 'phys' event. Python keeps those values and
// never sends them back. When the program moves a physics thing itself, the move arrives as a change to the thing's
// object (x, y, z, rx...) and its body goes there (a teleport) and carries on, keeping its speed. Each report says
// the last of Python's batches the page had applied (seq), so Python knows a report from before its move is old.
// A shake only tilts how a body is drawn (its object's `wobble`, a quaternion), not the body.
//
// What each object is comes from Python as its `phys` property: { kind: 'dynamic' (falls, tumbles, gets pushed),
// 'static' (never moves) or 'kinematic' (moved by the program), shape, size, cy (how far its middle is above the
// object's position), mass, bounce, friction, hits (report what hits it) }. Shapes: 'box' [hx, hy, hz], 'ball' r,
// 'cylinder' / 'cone' / 'capsule' [half height, r], 'land' (the terrain's heights), 'car' and 'ragdoll'. In 2D:
// 'box' [hx, hy], 'ball' r, 'capsule' [half length, r, x, y, angle] (a line), in the game's own pixels.
//
// Heights Python reads for a body that tumbles (3D): x and z are its middle, y its lowest point. A car and a ragdoll
// report their own way (see report3d).

const STEP = 1 / 60;
const MAX_STEPS = 4;        // after a slow frame, catch up at most this many steps; the rest of the time is dropped
const DEG = Math.PI / 180;
const LOST = -300;          // a body that falls this far (off the island, through the world) stops being simulated,
                            // until the program puts it somewhere (revive)
const PLAYER = { r: 0.32, half: 0.555, feet: 0.875 };  // tgame's player: a capsule 1.75 tall, its feet at y

let R = null;               // Rapier (rapier3d.mjs or rapier2d.mjs)
let D3 = true;              // a 3D world (tgame.world) or a 2D game (tgame.window)
let world = null;
let queue = null;           // the world's EventQueue
let host = null;            // what engine.js lends: emit, report, node, applied
let paused = false;
let last = 0;               // the last frame's time (ms)
let acc = 0;                // seconds of the world not stepped yet
let steps = 0;
let dirty = false;          // something changed since the last report (a teleport): tell Python
const recs = new Map();     // object node -> its record
const byId = new Map();     // object id -> its record
const owners = new Map();   // collider handle -> { id (the object's id; 0: the player; -1: a wall), rec }
const pending = new Map();  // hits that started, collecting how hard they were for two steps: key -> { a, b, s, age }
let walls = [];             // 2D: the bodies of game:walls
let player = null;          // 3D: the player's capsule, moved by its character controller
let chase = null;           // 3D: the car the camera follows, and where the camera is

// ---------------------------------------------------------------- starting

export async function load(helpers, opts) {
  host = helpers;
  D3 = (opts && opts.dim) !== 2;
  R = await import(D3 ? './rapier/rapier3d.mjs' : './rapier/rapier2d.mjs');
  await R.init();
  const g = opts && typeof opts.gravity === 'number' ? opts.gravity : (D3 ? -9.8 : 900);
  world = new R.World(D3 ? { x: 0, y: g, z: 0 } : { x: 0, y: g });
  world.timestep = STEP;
  if (!D3) world.lengthUnit = 50;  // pixels: about 50 to a metre, so Rapier's tolerances fit the game's sizes
  queue = new R.EventQueue(true);
  return api;
}

const api = { attach, moved, detach, call, step, landChanged, info };

function info() {
  let awake = 0;
  for (const r of recs.values()) if (r.kind === 'dynamic' && r.moving) awake++;
  return { dim: D3 ? 3 : 2, bodies: recs.size, awake, steps, paused };
}

// ---------------------------------------------------------------- objects with a body

// The object's `phys` changed (or it got one): make its body, or change it. null takes its body away.
function attach(n) {
  const spec = n.phys;
  const old = recs.get(n);
  if (n.dead || !spec) { if (old) drop(old); return; }
  if (old && old.spec.shape === spec.shape && ['car', 'ragdoll', 'land'].includes(spec.shape)) {
    // The same car, ragdoll or land with a new mass, bounce, friction or hits: changed where it is.
    old.spec = spec;
    old.colliders.forEach((c, i) => {
      tune(c, spec);
      if (old.parts) c.setMass(+spec.parts[i][4]);
      else if (old.vehicle) carMass(c, spec);
    });
    return;
  }
  if (old && old.spec.shape === spec.shape) {
    // The same shape: a new kind, size, mass, bounce... on the same body, so it keeps going as it was.
    if (old.spec.kind !== spec.kind) old.body.setBodyType(bodyType(spec.kind), true);
    for (const c of old.colliders) { owners.delete(c.handle); world.removeCollider(c, false); }
    old.spec = spec;
    old.kind = spec.kind;
    old.cy = +spec.cy || 0;
    old.colliders = [collider(spec, old.body, old)];
    if (spec.kind === 'dynamic') { old.body.enableCcd(true); old.body.wakeUp(); }
    return;
  }
  if (old) drop(old);
  const rec = { n, id: n.id, spec, kind: spec.kind, cy: +spec.cy || 0, colliders: [], prev: null, cur: null, asleep: false, born: steps };
  recs.set(n, rec);
  byId.set(n.id, rec);
  if (spec.shape === 'land') makeLand(rec);
  else if (spec.shape === 'car') makeCar(rec);
  else if (spec.shape === 'ragdoll') makeRagdoll(rec);
  else makeBody(rec);
  dirty = true;
}

function detach(n) {
  const r = recs.get(n);
  if (r) drop(r);
}

function drop(r) {
  recs.delete(r.n);
  if (byId.get(r.id) === r) byId.delete(r.id);
  for (const c of r.colliders) owners.delete(c.handle);
  if (r.vehicle) world.removeVehicleController(r.vehicle);
  if (chase && chase.rec === r) chase = null;
  for (const b of r.parts ? r.parts.map((p) => p.body) : [r.body]) if (b) world.removeRigidBody(b);
}

function bodyType(kind) {
  return kind === 'dynamic' ? R.RigidBodyType.Dynamic : kind === 'kinematic' ? R.RigidBodyType.KinematicPositionBased : R.RigidBodyType.Fixed;
}

function bodyDesc(kind) {
  if (kind === 'dynamic') return R.RigidBodyDesc.dynamic().setCcdEnabled(true);
  return kind === 'kinematic' ? R.RigidBodyDesc.kinematicPositionBased() : R.RigidBodyDesc.fixed();
}

function shapeDesc(shape, size) {
  const s = (v) => Math.max(D3 ? 0.005 : 0.25, +v || 0);
  if (D3) {
    switch (shape) {
      case 'ball': return R.ColliderDesc.ball(s(size));
      case 'cylinder': return R.ColliderDesc.cylinder(s(size[0]), s(size[1]));
      case 'cone': return R.ColliderDesc.cone(s(size[0]), s(size[1]));
      case 'capsule': return R.ColliderDesc.capsule(s(size[0]), s(size[1]));
      default: return R.ColliderDesc.cuboid(s(size[0]), s(size[1]), s(size[2]));
    }
  }
  switch (shape) {
    case 'ball': return R.ColliderDesc.ball(s(size));
    case 'capsule': {
      const d = R.ColliderDesc.capsule(s(size[0]), s(size[1]));
      d.setTranslation(+size[2] || 0, +size[3] || 0);
      d.setRotation((+size[4] || 0) * DEG);
      return d;
    }
    default: return R.ColliderDesc.cuboid(s(size[0]), s(size[1]));
  }
}

// A collider for a body, with the spec's mass (or one from its size; false: the one desc has), bounce and friction.
// Bounce takes the bouncier of the two things that meet, so a bouncy ball bounces on any floor.
function collider(spec, body, rec, desc = shapeDesc(spec.shape, spec.size), mass = spec.mass) {
  if (mass > 0) desc.setMass(+mass);
  else if (mass !== false) desc.setDensity(D3 ? 1 : 1 / 2500);  // 3D: a 1 m crate weighs 1 kg; 2D: 50 x 50 pixels weigh 1 kg
  const c = world.createCollider(desc, body);
  tune(c, spec);
  owners.set(c.handle, { id: rec.id, rec });
  return c;
}

// Its bounce, friction, and whether what hits it is reported.
function tune(c, spec) {
  c.setFriction(spec.friction == null ? 0.5 : Math.max(0, +spec.friction));
  c.setRestitution(spec.bounce == null ? 0.1 : Math.min(1, Math.max(0, +spec.bounce)));
  c.setRestitutionCombineRule(R.CoefficientCombineRule.Max);
  c.setActiveEvents(spec.hits ? R.ActiveEvents.COLLISION_EVENTS | R.ActiveEvents.CONTACT_FORCE_EVENTS : R.ActiveEvents.NONE);
  c.setContactForceEventThreshold(0);
}

// A body where the object is now: its middle is cy above the object's position (turned with it).
function makeBody(rec) {
  const { n, spec } = rec;
  const desc = bodyDesc(spec.kind);
  if (D3) {
    const o = n.obj;
    const q = quat(o.quaternion);
    const c = add(vec(o.position), qrot(q, [0, rec.cy, 0]));
    desc.setTranslation(c[0], c[1], c[2]).setRotation({ x: q[0], y: q[1], z: q[2], w: q[3] });
  } else {
    desc.setTranslation(+n.p.x || 0, +n.p.y || 0).setRotation((+n.p.rot || 0) * DEG);
  }
  rec.body = world.createRigidBody(desc);
  rec.colliders = [collider(spec, rec.body, rec)];
  if (D3 && n.obj.visible === false) rec.body.setEnabled(false);
  if (!D3 && n.p.visible === false) rec.body.setEnabled(false);
  rec.cur = rec.prev = state(rec.body);
}

// The land: a heightfield of the terrain's own heights (the same triangles three.js draws). It's made again when
// the heights change (at the next step, once however many changes came).
function makeLand(rec) {
  const n = rec.n;
  const grid = n.grid;
  if (!grid) return;
  const N = grid.N;
  const pos = n.obj.geometry.attributes.position.array;
  const h = new Float32Array(N * N);
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) h[i * N + j] = pos[(j * N + i) * 3 + 1];  // Rapier's are by column
  const o = n.obj.position;
  if (!rec.body) rec.body = world.createRigidBody(R.RigidBodyDesc.fixed().setTranslation(o.x, o.y, o.z));
  for (const c of rec.colliders) { owners.delete(c.handle); world.removeCollider(c, false); }
  const desc = R.ColliderDesc.heightfield(N - 1, N - 1, h, { x: grid.size, y: 1, z: grid.size });
  rec.colliders = [collider({ ...rec.spec, shape: 'land' }, rec.body, rec, desc, false)];
  rec.landDirty = false;
}

function landChanged(n) {
  const r = recs.get(n);
  if (r && r.spec.shape === 'land') r.landDirty = true;
}

// ---- a car: Rapier's ray-cast vehicle. A box for the body on four wheels that are rays with springs. Python's spec:
// size (the body's half sizes), cy (its middle above the car's position), wheel_r, rest (the springs' length), mass,
// and wheels: [id, x, y, z] (each wheel's object and where its spring is fixed, in the car's own space).
const CAR = { stiffness: 30, compression: 4.4, relaxation: 2.3, slip: 2.2, travel: 0.3, force: 1100, top: 22, brake: 8 };

function makeCar(rec) {
  const { n, spec } = rec;
  const o = n.obj;
  const q = quat(o.quaternion);
  const c = add(vec(o.position), qrot(q, [0, rec.cy, 0]));
  rec.body = world.createRigidBody(R.RigidBodyDesc.dynamic().setTranslation(c[0], c[1], c[2])
    .setRotation({ x: q[0], y: q[1], z: q[2], w: q[3] }).setCanSleep(false).setLinearDamping(0.05).setAngularDamping(0.6));
  const [hx, hy, hz] = spec.size;
  rec.colliders = [collider(spec, rec.body, rec, R.ColliderDesc.cuboid(hx, hy, hz), false)];
  carMass(rec.colliders[0], spec);
  const v = rec.vehicle = world.createVehicleController(rec.body);
  v.setIndexForwardAxis = 2;
  rec.wheels = [];
  for (const [id, x, y, z] of spec.wheels) {
    const cs = { x, y: y - rec.cy, z };
    const i = rec.wheels.length;
    v.addWheel(cs, { x: 0, y: -1, z: 0 }, { x: -1, y: 0, z: 0 }, spec.rest || 0.35, spec.wheel_r || 0.36);
    v.setWheelSuspensionStiffness(i, CAR.stiffness);
    v.setWheelSuspensionCompression(i, CAR.compression);
    v.setWheelSuspensionRelaxation(i, CAR.relaxation);
    v.setWheelFrictionSlip(i, CAR.slip);
    v.setWheelMaxSuspensionTravel(i, CAR.travel);
    v.setWheelMaxSuspensionForce(i, 1e5);
    rec.wheels.push({ n: host.node(id), cs, front: z < 0 });
  }
  rec.controls = { throttle: 0, steer: 0, brake: 0 };
  rec.power = 1;
  rec.steer = 0;
  rec.kmh = 0;
  rec.cur = rec.prev = state(rec.body);
}

// A car's weight, low down under its floor, so it leans in a corner instead of rolling over.
function carMass(c, spec) {
  const [hx, hy, hz] = spec.size;
  const m = spec.mass > 0 ? +spec.mass : 150;
  c.setMassProperties(m, { x: 0, y: -hy * 1.4, z: 0 },
    { x: m * (hy * hy + hz * hz) / 3, y: m * (hx * hx + hz * hz) / 3, z: m * (hx * hx + hy * hy) / 3 }, { x: 0, y: 0, z: 0, w: 1 });
}

function driveCar(r) {
  const v = r.vehicle;
  const speed = -v.currentVehicleSpeed();  // forward (to -z) is positive
  const { throttle, steer, brake } = r.controls;
  const turn = 0.55 - 0.4 * Math.min(1, Math.abs(speed) / CAR.top);  // less steering the faster it goes
  r.steer += Math.max(-3 * STEP, Math.min(3 * STEP, steer * turn - r.steer));
  const force = CAR.force * Math.max(0, r.power);
  let engine = 0;
  let stop = brake ? CAR.brake : 0;
  if (throttle > 0) {
    if (speed < -1) stop = CAR.brake;  // going backwards: W brakes first
    else engine = force * Math.max(0, 1 - speed / (CAR.top * Math.max(0.3, Math.sqrt(r.power))));
  } else if (throttle < 0) {
    if (speed > 1) stop = CAR.brake;   // going forwards: S brakes first, then reverses
    else engine = -force * 0.6 * Math.max(0, 1 + speed / (CAR.top * 0.4));
  } else if (!brake) stop = 0.4;       // rolling to a stop
  for (let i = 0; i < r.wheels.length; i++) {
    const w = r.wheels[i];
    v.setWheelEngineForce(i, w.front ? 0 : -engine / 2);
    v.setWheelSteering(i, w.front ? r.steer : 0);
    v.setWheelBrake(i, stop);
  }
  v.updateVehicle(STEP);
  r.kmh = speed * 3.6;
}

// ---- a ragdoll: a body for each part (head, chest, hips, arms, legs) held together by joints. Python's spec: parts
// [id, shape, size, [x, y, z] (its middle, standing, in the ragdoll's own space), mass], joints [part a, part b,
// [x, y, z] (where they meet), 'ball' or 'hinge' (turns about x), [lowest, highest] angle or null], main (the chest).
// The ragdoll's own object stays where the world's middle is; each part's object goes where its body is.
function makeRagdoll(rec) {
  const { n, spec } = rec;
  const o = n.obj;
  const q = quat(o.quaternion);
  const base = vec(o.position);
  const k = o.scale.x || 1;
  // Standing on the ground, it starts asleep: it stands until something hits it or it's pushed (that wakes it).
  rec.parts = spec.parts.map(([id, shape, size, at, mass]) => {
    const c = add(base, qrot(q, at.map((v) => v * k)));
    const body = world.createRigidBody(R.RigidBodyDesc.dynamic().setTranslation(c[0], c[1], c[2])
      .setRotation({ x: q[0], y: q[1], z: q[2], w: q[3] }).setAngularDamping(1.5).setLinearDamping(0.1).setCcdEnabled(true)
      .setSleeping(!!spec.stand));
    const size2 = Array.isArray(size) ? size.map((v) => v * k) : size * k;
    const part = { n: host.node(id), body, shape, size: size2, mass };
    rec.colliders.push(collider({ ...spec, shape, size: size2 }, body, rec, undefined, mass));
    part.cur = part.prev = state(body);
    return part;
  });
  for (const [a, b, at, kind, limits] of spec.joints) {
    const A = rec.parts[a].body;
    const B = rec.parts[b].body;
    const w = add(base, qrot(q, at.map((v) => v * k)));
    const local = (body) => {
      const t = body.translation();
      return vecObj(qrot(conj(q), [w[0] - t.x, w[1] - t.y, w[2] - t.z]));
    };
    const data = kind === 'hinge' ? R.JointData.revolute(local(A), local(B), { x: 1, y: 0, z: 0 }) : R.JointData.spherical(local(A), local(B));
    const j = world.createImpulseJoint(data, A, B, !spec.stand);
    j.setContactsEnabled(false);
    if (kind === 'hinge' && limits) j.setLimits(limits[0], limits[1]);
  }
  rec.main = rec.parts[spec.main || 0];
  rec.body = rec.main.body;
  rec.still = spec.stand ? 2 : 0;  // its joints wake it in its first step: back to sleep for its first two
  holdStill(n);
  rec.cur = rec.prev = state(rec.body);
}

// The ragdoll's own object stays put, so its parts' objects can take their bodies' places as they are.
function holdStill(n) {
  n.obj.position.set(0, 0, 0);
  n.obj.quaternion.set(0, 0, 0, 1);
  n.obj.scale.set(1, 1, 1);
}

// ---------------------------------------------------------------- the program moved a thing

// Changes Python made to an object with a body (engine.js's setObj or setShape, after it applied them): a move
// teleports the body (a dynamic one keeps its speed), and hiding it switches its body off.
function moved(n, props) {
  const r = recs.get(n);
  if (!r) return;
  if ('visible' in props) for (const b of r.parts ? r.parts.map((p) => p.body) : [r.body]) if (b) b.setEnabled(!!props.visible);
  if (r.parts) {  // a ragdoll's object stays at the world's middle: only where the program put it counts
    if ('x' in props || 'y' in props || 'z' in props) moveRagdoll(r);
    else holdStill(n);
    return;
  }
  if ('wobble' in props && D3 && r.kind === 'dynamic' && r.cur) draw(r, 1);  // a shake: drawn tilted, the body as it is
  if (D3 ? !('x' in props || 'y' in props || 'z' in props || 'rx' in props || 'ry' in props || 'rz' in props)
    : !('x' in props || 'y' in props || 'rot' in props)) return;
  if (!r.body) return;
  if (!D3) {
    const p = n.p;
    if (r.kind === 'kinematic') {
      r.body.setNextKinematicTranslation({ x: +p.x, y: +p.y });
      r.body.setNextKinematicRotation((+p.rot || 0) * DEG);
      return;
    }
    r.body.setTranslation({ x: +p.x, y: +p.y }, true);
    r.body.setRotation((+p.rot || 0) * DEG, true);
  } else {
    const o = n.obj;
    const q = quat(o.quaternion);
    if (r.kind === 'dynamic') {
      // Python's x, y, z for a dynamic body: its middle across, its lowest point up (a car: its own position). Only
      // turned, it turns about its middle.
      const put = 'x' in props || 'y' in props || 'z' in props;
      const c = !put ? vec(r.body.translation())
        : r.vehicle ? add(vec(o.position), qrot(q, [0, r.cy, 0])) : [o.position.x, o.position.y + extentY(r.spec, q), o.position.z];
      if (put) revive(r);
      r.body.setTranslation({ x: c[0], y: c[1], z: c[2] }, true);
      r.body.setRotation({ x: q[0], y: q[1], z: q[2], w: q[3] }, true);
    } else {
      const c = add(vec(o.position), qrot(q, [0, r.cy, 0]));
      if (r.kind === 'kinematic' && Array.isArray(props.vel)) { r.glide = { at: c, v: props.vel.map(Number) }; return; }  // on a path: glide()
      if (r.kind === 'kinematic') {
        r.body.setNextKinematicTranslation({ x: c[0], y: c[1], z: c[2] });
        r.body.setNextKinematicRotation({ x: q[0], y: q[1], z: q[2], w: q[3] });
        return;
      }
      r.body.setTranslation({ x: c[0], y: c[1], z: c[2] }, true);
      r.body.setRotation({ x: q[0], y: q[1], z: q[2], w: q[3] }, true);
    }
  }
  world.propagateModifiedBodyPositionsToColliders();
  r.cur = r.prev = state(r.body);
  if (r.kind === 'dynamic') { draw(r, 1); r.moved = true; dirty = true; }
}

// A thing moving along a path (tgame's thing:path): Python sends where it is and how fast it's going (vel) every
// frame, but its frames and the steps here don't line up, so a step would get two moves or none, and what rides on it
// would be kicked up or left behind. Instead it goes on at that speed every step, pulled gently toward where Python
// has it (that spot goes on at the same speed until the next frame says where it is).
function glide(r) {
  const g = r.glide;
  if (r.kind !== 'kinematic' || !r.body) { r.glide = null; return; }
  const now = vec(r.body.translation());
  const next = now.map((v, i) => v + g.v[i] * STEP + (g.at[i] - v) * 0.15);
  g.at = g.at.map((v, i) => v + g.v[i] * STEP);
  r.body.setNextKinematicTranslation(vecObj(next));
}

// A body that fell out of the world was switched off (see fixedStep). Put somewhere by the program (or flipped back
// onto its wheels), it's switched on again, unless it's hidden (that switches it off too).
function revive(r) {
  if (!D3 || r.n.obj.visible === false) return;
  for (const b of bodies(r)) if (!b.isEnabled()) b.setEnabled(true);
}

// A ragdoll moved by the program: every part moves by as much as its reported spot did (and it's drawn there).
function moveRagdoll(r) {
  revive(r);
  const o = r.n.obj;
  const want = vec(o.position);
  const now = report3d(r);
  const d = [want[0] - now[1], want[1] - now[2], want[2] - now[3]];
  for (const p of r.parts) {
    const t = p.body.translation();
    p.body.setTranslation({ x: t.x + d[0], y: t.y + d[1], z: t.z + d[2] }, true);
    p.cur = p.prev = state(p.body);
  }
  holdStill(r.n);
  world.propagateModifiedBodyPositionsToColliders();
  r.cur = r.prev = state(r.body);
  draw(r, 1);
  r.moved = true;
  dirty = true;
}

// ---------------------------------------------------------------- what Python asks for

function call(op, args) {
  const fn = OPS[op];
  if (!fn) throw new Error(`physics has no '${op}'`);
  return fn(...args);
}

function rec(id) {
  return byId.get(id) || null;
}

function bodies(r) {
  return r ? (r.parts ? r.parts.map((p) => p.body) : r.body ? [r.body] : []) : [];
}

// The program set something going: a standing ragdoll stops being put back to sleep. Gives its (main) body.
function moving(id) {
  const r = rec(id);
  if (!r) return null;
  r.pushed = true;
  return r.body;
}

const OPS = {
  gravity(g) { world.gravity = D3 ? { x: 0, y: +g, z: 0 } : { x: 0, y: +g }; for (const r of recs.values()) for (const b of bodies(r)) if (b.isDynamic()) b.wakeUp(); },
  pause(on) { paused = !!on; },
  // An impulse (a kick: mass times the change in speed). A ragdoll gets it in its chest, so it flops.
  push(id, x, y, z) {
    const b = moving(id);
    if (b && b.isDynamic()) b.applyImpulse(D3 ? { x: +x, y: +y, z: +z } : { x: +x, y: +y }, true);
  },
  spin(id, x, y, z) {
    const b = moving(id);
    if (b && b.isDynamic()) b.applyTorqueImpulse(D3 ? { x: +x, y: +y, z: +z } : +x, true);
  },
  velocity(id, x, y, z) {
    moving(id);
    for (const b of bodies(rec(id))) if (b.isDynamic()) b.setLinvel(D3 ? { x: +x, y: +y, z: +z } : { x: +x, y: +y }, true);
  },
  sleep(id) { for (const b of bodies(rec(id))) b.sleep(); },
  wake(id) { moving(id); for (const b of bodies(rec(id))) b.wakeUp(); },
  // Things near the middle fly away from it: `strength` is how fast (metres or pixels a second) right at the middle,
  // less further off, none at `radius`. In 3D they go up a little too.
  explode(...a) {
    const [x, y, z, strength, radius] = D3 ? a : [a[0], a[1], 0, a[2], a[3]];
    const rr = Math.max(0.01, +radius);
    for (const r of recs.values()) {
      for (const b of bodies(r)) {
        if (!b.isDynamic() || !b.isEnabled()) continue;
        const t = b.translation();
        let dx = t.x - x;
        let dy = t.y - y;
        let dz = D3 ? t.z - z : 0;
        const d = Math.hypot(dx, dy, dz);
        if (d >= rr) continue;
        if (d < 1e-6) { dx = 0; dy = D3 ? 1 : -1; dz = 0; } else { dx /= d; dy /= d; dz /= d; }
        if (D3) dy = Math.max(dy, 0) + 0.35;
        r.pushed = true;
        const k = +strength * (1 - d / rr) * b.mass();
        b.applyImpulse(D3 ? { x: dx * k, y: dy * k, z: dz * k } : { x: dx * k, y: dy * k }, true);
      }
    }
  },
  // 2D: the screen's edges as walls (or not), around a game w x h pixels.
  walls(on, w, h) {
    for (const b of walls) world.removeRigidBody(b);
    walls = [];
    if (!on) return;
    const T = 200;
    for (const [x, y, hx, hy] of [[w / 2, -T, w / 2 + T * 2, T], [w / 2, h + T, w / 2 + T * 2, T], [-T, h / 2, T, h / 2 + T * 2], [w + T, h / 2, T, h / 2 + T * 2]]) {
      const b = world.createRigidBody(R.RigidBodyDesc.fixed().setTranslation(x, y));
      const c = world.createCollider(R.ColliderDesc.cuboid(hx, hy).setFriction(0.5), b);
      owners.set(c.handle, { id: -1, rec: null });
      walls.push(b);
    }
  },
  // The player (3D): seq numbers each move. 'player' walks it by dx, dy, dz (where Python put it after its own
  // collisions with the land and fixed things); its controller stops it at physics things and pushes them.
  player(seq, dx, dy, dz, x, y, z) {
    if (!player) makePlayer(x, y, z);
    player.want[0] += +dx;
    player.want[1] += +dy;
    player.want[2] += +dz;
    player.seq = seq;
  },
  player_to(seq, x, y, z) {
    if (!player) makePlayer(x, y, z);
    player.body.setEnabled(true);
    player.at = [+x, +y + PLAYER.feet, +z];
    player.body.setTranslation(vecObj(player.at), true);
    world.propagateModifiedBodyPositionsToColliders();
    player.want = [0, 0, 0];
    player.seq = player.done = seq;
    dirty = true;
  },
  // The player got into a car: its capsule isn't left standing where it got in (player_to brings it back).
  player_off() {
    if (!player) return;
    player.body.setEnabled(false);
    player.touching.clear();
  },
  // A car's controls: throttle (1 forward, -1 back), steer (1 left, -1 right), brake (0 or 1).
  drive(id, throttle, steer, brake) {
    const r = rec(id);
    if (r && r.controls) r.controls = { throttle: +throttle, steer: +steer, brake: +brake };
  },
  engine(id, power) { const r = rec(id); if (r) r.power = +power; },
  // Back on its wheels, a little above where it is, facing the way it faced.
  flip(id) {
    const r = rec(id);
    if (!r || !r.body) return;
    const t = r.body.translation();
    const q = quat(r.body.rotation());
    const yaw = Math.atan2(2 * (q[3] * q[1] + q[0] * q[2]), 1 - 2 * (q[1] * q[1] + q[2] * q[2]));
    revive(r);
    r.body.setTranslation({ x: t.x, y: t.y + 1.2, z: t.z }, true);
    r.body.setRotation({ x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) }, true);
    r.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
    r.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
  },
  // The camera follows this car (or stops: id null): behind it and a little above, smoothly.
  chase(id) {
    const r = id == null ? null : rec(id);
    chase = r ? { rec: r, at: null } : null;
  },
};

function makePlayer(x, y, z) {
  const at = [+x, +y + PLAYER.feet, +z];
  const body = world.createRigidBody(R.RigidBodyDesc.kinematicPositionBased().setTranslation(at[0], at[1], at[2]));
  const c = world.createCollider(R.ColliderDesc.capsule(PLAYER.half, PLAYER.r)
    .setActiveEvents(R.ActiveEvents.COLLISION_EVENTS | R.ActiveEvents.CONTACT_FORCE_EVENTS).setContactForceEventThreshold(0), body);
  owners.set(c.handle, { id: 0, rec: null });
  const kcc = world.createCharacterController(0.02);
  kcc.setApplyImpulsesToDynamicBodies(true);
  kcc.setCharacterMass(60);
  kcc.setSlideEnabled(true);
  kcc.disableAutostep();
  kcc.disableSnapToGround();
  // seq: the last move that came; done: the last one the controller has made (what the report to Python is up to)
  player = { body, collider: c, kcc, at, want: [0, 0, 0], seq: 0, done: 0, grounded: false, touching: new Set(), v: [0, 0, 0] };
}

// The player's move this step: as far as its controller lets it go toward where Python walked it. The land, fixed
// things and kinematic ones (the program moves those, so Python knows where they are) are left to Python: it walks
// on them as it always has, and a lift carries it. This is for the things physics moves.
function movePlayer() {
  const p = player;
  const want = p.want;
  p.want = [0, 0, 0];
  p.done = p.seq;
  p.kcc.computeColliderMovement(p.collider, vecObj(want),
    R.QueryFilterFlags.EXCLUDE_FIXED | R.QueryFilterFlags.EXCLUDE_KINEMATIC | R.QueryFilterFlags.EXCLUDE_SENSORS);
  const m = p.kcc.computedMovement();
  p.v = [m.x / STEP, m.y / STEP, m.z / STEP];
  p.at = [p.at[0] + m.x, p.at[1] + m.y, p.at[2] + m.z];
  p.body.setNextKinematicTranslation(vecObj(p.at));
  p.grounded = p.kcc.computedGrounded();
  // Walking into something counts as a hit when it starts (not every step it's pushed).
  const now = new Set();
  for (let i = 0; i < p.kcc.numComputedCollisions(); i++) {
    const hit = p.kcc.computedCollision(i);
    const c = hit && hit.collider;
    if (!c) continue;
    now.add(c.handle);
    if (!p.touching.has(c.handle)) {
      const b = c.parent();
      const v = b ? b.linvel() : { x: 0, y: 0, z: 0 };
      const s = Math.hypot(p.v[0] - v.x, p.v[1] - v.y, p.v[2] - v.z) * Math.min(60, b && b.isDynamic() ? b.mass() : 60);
      started(p.collider.handle, c.handle, s);
    }
  }
  p.touching = now;
}

// ---------------------------------------------------------------- every frame

// Steps the world (fixed 60 Hz steps for the time since the last frame), draws the bodies, and reports to Python.
function step(now) {
  if (!world) return;
  const dt = last ? Math.min(0.25, (now - last) / 1000) : 0;
  last = now;
  if (paused) { acc = 0; return; }
  acc += dt;
  let n = 0;
  while (acc >= STEP && n < MAX_STEPS) {
    fixedStep();
    acc -= STEP;
    n++;
  }
  if (acc >= STEP) acc = 0;  // still behind: let the time go rather than fall further behind
  const alpha = Math.min(1, acc / STEP);
  // The bodies that are moving, or that stepped this frame and moved (one that just fell asleep goes where it
  // stopped). A body asleep isn't drawn again, so a world where everything has settled isn't drawn at all.
  for (const r of recs.values()) if (r.kind === 'dynamic' && (r.moving || (n && r.moved))) draw(r, alpha);
  if (chase) follow(dt);
  if (n || dirty) send();
}

function fixedStep() {
  for (const r of recs.values()) {
    if (r.landDirty) makeLand(r);
    if (r.vehicle) driveCar(r);
    if (r.glide) glide(r);
  }
  if (player && player.body.isEnabled()) movePlayer();
  world.step(queue);
  steps++;
  queue.drainCollisionEvents((h1, h2, start) => { if (start) started(h1, h2, 0); });
  queue.drainContactForceEvents((e) => {
    const p = pending.get(pairKey(e.collider1(), e.collider2()));
    if (p) p.s += e.totalForceMagnitude() * STEP;
  });
  for (const r of recs.values()) {
    if (r.kind !== 'dynamic' || !r.body) continue;
    if (r.still && r.still-- && !r.pushed) for (const p of r.parts) p.body.sleep();
    const asleep = r.body.isSleeping();
    if (!asleep || !r.asleep) r.moved = true;  // awake, or it just fell asleep: report where it stopped
    r.asleep = asleep;
    r.moving = !asleep;
    r.prev = r.cur;
    r.cur = state(r.body);
    if (r.parts) for (const p of r.parts) { p.prev = p.cur; p.cur = state(p.body); }
    if (r.cur[1] < LOST && D3) for (const b of bodies(r)) b.setEnabled(false);
  }
}

function pairKey(a, b) {
  return a < b ? `${a} ${b}` : `${b} ${a}`;
}

// A hit started between two colliders: it's reported after two more steps, with how hard it was (the impulses that
// pushed them apart, in N·s, or for a player walking into something, about its speed times its mass).
function started(h1, h2, s) {
  const a = owners.get(h1);
  const b = owners.get(h2);
  if (!a || !b) return;
  if ((a.rec && steps - a.rec.born < 3) || (b.rec && steps - b.rec.born < 3)) return;  // made touching: that's no hit
  const key = pairKey(h1, h2);
  if (!pending.has(key)) pending.set(key, { a: a.id, b: b.id, s, age: 0 });
}

// Where a body is now: 3D [x, y, z, qx, qy, qz, qw] (its middle), 2D [x, y, angle].
function state(b) {
  const t = b.translation();
  if (!D3) return [t.x, t.y, b.rotation()];
  const q = b.rotation();
  return [t.x, t.y, t.z, q.x, q.y, q.z, q.w];
}

// Puts a body's object where its body is, between its last two steps (alpha 0..1).
function draw(r, alpha) {
  const n = r.n;
  if (!D3) {
    const a = r.prev;
    const b = r.cur;
    n.p.x = a[0] + (b[0] - a[0]) * alpha;
    n.p.y = a[1] + (b[1] - a[1]) * alpha;
    n.p.rot = (a[2] + (b[2] - a[2]) * alpha) / DEG;
    n.host.dirty = true;
    return;
  }
  if (r.parts) {
    for (const p of r.parts) {
      if (!p.n) continue;
      const [t, q] = blend(p.prev, p.cur, alpha);
      p.n.obj.position.set(t[0], t[1], t[2]);
      p.n.obj.quaternion.set(q[0], q[1], q[2], q[3]);
    }
    n.host.dirty = true;
    return;
  }
  const [t, q] = blend(r.prev, r.cur, alpha);
  const at = sub(t, qrot(q, [0, r.cy, 0]));
  n.obj.position.set(at[0], at[1], at[2]);
  const w = n.wobble ? qmul(n.wobble, q) : q;  // a shake tilts how it's drawn, not its body
  n.obj.quaternion.set(w[0], w[1], w[2], w[3]);
  if (r.vehicle) drawWheels(r);
  n.host.dirty = true;
}

function blend(a, b, alpha) {
  const t = [a[0] + (b[0] - a[0]) * alpha, a[1] + (b[1] - a[1]) * alpha, a[2] + (b[2] - a[2]) * alpha];
  let d = a[3] * b[3] + a[4] * b[4] + a[5] * b[5] + a[6] * b[6];
  const s = d < 0 ? -1 : 1;
  const q = [0, 1, 2, 3].map((i) => a[3 + i] + (s * b[3 + i] - a[3 + i]) * alpha);
  d = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
  return [t, q.map((v) => v / d)];
}

// A car's wheels: each where its spring holds it, turned by the steering and rolling as it goes.
function drawWheels(r) {
  const v = r.vehicle;
  for (let i = 0; i < r.wheels.length; i++) {
    const w = r.wheels[i];
    if (!w.n) continue;
    const len = v.wheelSuspensionLength(i);
    w.n.obj.position.set(w.cs.x, w.cs.y + r.cy - (len == null ? 0.3 : len), w.cs.z);
    const steer = v.wheelSteering(i) || 0;
    const roll = v.wheelRotation(i) || 0;
    const qs = [0, Math.sin(steer / 2), 0, Math.cos(steer / 2)];
    const qr = [Math.sin(roll / 2), 0, 0, Math.cos(roll / 2)];
    const q = qmul(qs, qr);
    w.n.obj.quaternion.set(q[0], q[1], q[2], q[3]);
  }
}

// The chase camera: behind the car and above it, looking at it, catching up smoothly.
function follow(dt) {
  const r = chase.rec;
  const scene = r.n.host;
  if (!scene || !scene.camera) return;
  const o = r.n.obj;
  const q = quat(o.quaternion);
  const f = qrot(q, [0, 0, -1]);
  const flat = Math.hypot(f[0], f[2]) || 1;
  const mid = [o.position.x, o.position.y + 1, o.position.z];
  const want = [mid[0] - (f[0] / flat) * 7.5, mid[1] + 2.2, mid[2] - (f[2] / flat) * 7.5];
  const k = chase.at ? 1 - Math.exp(-5 * dt) : 1;
  chase.at = chase.at ? chase.at.map((v, i) => v + (want[i] - v) * k) : want;
  const cam = scene.camera;
  cam.position.set(chase.at[0], chase.at[1], chase.at[2]);
  cam.lookAt(mid[0], mid[1] + 0.3, mid[2]);
  scene.yaw = cam.rotation.y / DEG;
  scene.pitch = cam.rotation.x / DEG;
  scene.roll = cam.rotation.z / DEG;
  scene.dirty = true;
}

// ---------------------------------------------------------------- telling Python

const r4 = (v) => Math.round(v * 1e4) / 1e4;

function send() {
  dirty = false;
  const out = {};
  const b = [];
  for (const r of recs.values()) {
    if (!r.moved || r.kind !== 'dynamic') continue;
    r.moved = false;
    b.push(D3 ? report3d(r) : report2d(r));
  }
  if (b.length) out.b = b;
  const hits = [];
  for (const [key, p] of pending) {
    if (++p.age < 3) continue;
    pending.delete(key);
    hits.push([p.a, p.b, r4(p.s)]);
  }
  if (hits.length) out.h = hits;
  if (player) out.p = [player.done,r4(player.at[0]), r4(player.at[1] - PLAYER.feet), r4(player.at[2]), player.grounded ? 1 : 0];
  if (chase && chase.at) {
    const cam = chase.rec.n.host.camera;
    out.c = [r4(cam.position.x), r4(cam.position.y), r4(cam.position.z), r4(-cam.rotation.y / DEG), r4(cam.rotation.x / DEG)];
  }
  if (!(out.b || out.h || out.p || out.c)) return;
  out.seq = host.applied();  // the last of Python's batches applied: Python's moves after it aren't in this report
  host.emit('phys', out);
}

// 3D: [id, x, y, z, qx, qy, qz, qw, vx, vy, vz] (a car adds its speed in km/h). x and z are the middle and y the
// lowest point; a car's spot is its own position (under its middle), a ragdoll's its chest's x and z and its lowest
// part, turned like its chest.
function report3d(r) {
  const c = r.cur;
  const q = [c[3], c[4], c[5], c[6]];
  let at;
  if (r.vehicle) at = sub(c, qrot(q, [0, r.cy, 0]));
  else if (r.parts) {
    let low = Infinity;
    for (const p of r.parts) low = Math.min(low, p.cur[1] - extentY({ shape: p.shape, size: p.size }, [p.cur[3], p.cur[4], p.cur[5], p.cur[6]]));
    at = [c[0], low, c[2]];
  } else at = [c[0], c[1] - extentY(r.spec, q), c[2]];
  const v = r.body.linvel();
  const out = [r.id, r4(at[0]), r4(at[1]), r4(at[2]), r4(q[0]), r4(q[1]), r4(q[2]), r4(q[3]), r4(v.x), r4(v.y), r4(v.z)];
  if (r.vehicle) out.push(r4(r.kmh));
  return out;
}

// 2D: [id, x, y, angle (degrees), vx, vy, spin (degrees a second)]
function report2d(r) {
  const c = r.cur;
  const v = r.body.linvel();
  return [r.id, r4(c[0]), r4(c[1]), r4(c[2] / DEG), r4(v.x), r4(v.y), r4(r.body.angvel() / DEG)];
}

// ---------------------------------------------------------------- 3D maths ([x, y, z] and quaternions [x, y, z, w])

function vec(v) { return [v.x, v.y, v.z]; }
function vecObj(a) { return { x: a[0], y: a[1], z: a[2] }; }
function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function quat(q) { return [q.x, q.y, q.z, q.w]; }
function conj(q) { return [-q[0], -q[1], -q[2], q[3]]; }

function qmul(a, b) {
  return [a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
    a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
    a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
    a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2]];
}

function qrot(q, v) {
  const [x, y, z, w] = q;
  const tx = 2 * (y * v[2] - z * v[1]);
  const ty = 2 * (z * v[0] - x * v[2]);
  const tz = 2 * (x * v[1] - y * v[0]);
  return [v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx)];
}

// How far a shape reaches down from its middle, turned by q.
function extentY(spec, q) {
  const [x, y, z, w] = q;
  const a = Math.abs(2 * (x * y + w * z));
  const b = Math.abs(1 - 2 * (x * x + z * z));
  const c = Math.abs(2 * (y * z - w * x));
  const s = spec.size;
  switch (spec.shape) {
    case 'ball': return +s;
    case 'capsule': return b * s[0] + s[1];
    case 'cylinder': case 'cone': return b * s[0] + Math.sqrt(Math.max(0, 1 - b * b)) * s[1];
    case 'box': return a * s[0] + b * s[1] + c * s[2];
    default: return 0;
  }
}
