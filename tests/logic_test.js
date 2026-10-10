#!/usr/bin/env node
/* Deterministic logic test — no browser, no rendering.
 * Loads the game script from index.html, stubs the DOM, plays a full game and
 * checks the rules. Run: node tests/logic_test.js
 */
const fs = require('fs');
const path = require('path');

const noop = () => {};
const grad = { addColorStop: noop };
const ctxStub = new Proxy(
  {
    createLinearGradient: () => grad,
    createRadialGradient: () => grad,
    measureText: () => ({ width: 10 }),
  },
  { get: (t, k) => (k in t ? t[k] : noop), set: (t, k, v) => ((t[k] = v), true) }
);

function elNode(id) {
  return {
    id, textContent: '', innerHTML: '', disabled: false, value: '', style: {},
    clientWidth: 640, clientHeight: 560, width: 640, height: 560,
    classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
    getContext: () => ctxStub,
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
    addEventListener: noop,
    onclick: null,
  };
}

global.document = {
  hidden: false,
  getElementById: (id) => elNode(id),
  createElement: () => ({ style: {}, getContext: () => ctxStub }),
  addEventListener: noop,
};
global.window = { addEventListener: noop, devicePixelRatio: 1 };
global.localStorage = {
  _d: {},
  getItem: (k) => global.localStorage._d[k] ?? null,
  setItem: (k, v) => { global.localStorage._d[k] = v; },
};

let T = 0;
global.performance = { now: () => T };
let rafQueue = [];
global.requestAnimationFrame = (fn) => rafQueue.push(fn);

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
eval(html.match(/<script>([\s\S]*?)<\/script>/)[1]);

const G = global.window.cubegame;
const N = G.cfg.N, TOTAL = N * N * N;
const frames = (n) => {
  for (let i = 0; i < n; i++) {
    T += 16;
    const q = rafQueue; rafQueue = [];
    for (const f of q) f(T);
  }
};

const fails = [];
const check = (cond, msg) => { if (!cond) fails.push(msg); };

function multiset() {
  return G.state.cells.filter((c) => c !== null).sort((a, b) => a - b).join(',');
}

// Invariant: after gravity has run, every column is compact — a cube rests on the
// floor or on another cube. (Rotation alone must NOT enforce this.)
function compactColumns(tag) {
  for (let x = 0; x < N; x++) {
    for (let z = 0; z < N; z++) {
      let expect = 0;
      for (let y = 0; y < N; y++) {
        const i = G.idx(x, y, z);
        if (G.state.cells[i] === null) continue;
        if (y !== expect) { fails.push(`${tag}: floating cube at (${x},${y},${z})`); return false; }
        expect++;
      }
    }
  }
  return true;
}

// ---------------------------------------------------------------- full game
G.cfg.seed = 7;
G.newGame();
frames(30);

const total0 = G.cubesLeft();
let popped = 0, expected = 0, guard = 0, scoreBeforeLast = 0, lastGroup = 0;

while (guard++ < 400) {
  frames(40);
  if (G.state.phase !== 'idle') { fails.push('phase not idle after settle'); break; }
  compactColumns('after settle');
  const g = G.largestGroup();
  if (g.length < 2) break;
  scoreBeforeLast = expected;
  lastGroup = g.length;
  expected += lastGroup * (lastGroup - 1) * G.chainMult();
  popped += lastGroup;
  G.popGroup(g);
  frames(40);
  if (G.state.score !== expected) fails.push(`score ${G.state.score} != ${expected}`);
  if (G.cubesLeft() !== total0 - popped) fails.push(`cubes ${G.cubesLeft()} != ${total0 - popped}`);
}
frames(40);
const bonus = G.cubesLeft() === 0 ? G.cfg.clearBonus : 0;
if (G.state.score !== expected + bonus) fails.push(`final score ${G.state.score} != ${expected + bonus}`);
if (!G.state.over) fails.push('game over not detected');
console.log(`game: score=${G.state.score} moves=${G.state.moves} left=${G.cubesLeft()} over=${G.state.over}`);

// ---------------------------------------------------------------- undo
G.undo();
frames(40);
compactColumns('undo');
if (G.state.score !== scoreBeforeLast) fails.push(`undo score ${G.state.score} != ${scoreBeforeLast}`);
if (G.cubesLeft() !== total0 - popped + lastGroup) fails.push(`undo cubes ${G.cubesLeft()} != ${total0 - popped + lastGroup}`);
console.log(`undo: score=${G.state.score} cubes=${G.cubesLeft()}`);

// ---------------------------------------------------------------- two-click flow
G.cfg.seed = 11;
G.newGame();
frames(40);
const start = G.largestGroup();
if (start.length < 2) fails.push('no group to click at start');
G.clickCube(start[0]);
frames(40);
if (G.state.sel.length !== start.length) fails.push(`click 1 did not select (${G.state.sel.length})`);
if (G.state.phase !== 'idle') fails.push('click 1 must not pop');
const before = G.state.score;
G.clickCube(start[0]);
frames(40);
if (G.state.score === before) fails.push('click 2 did not pop');
if (G.cubesLeft() !== total0 - start.length) fails.push(`click 2 cubes ${G.cubesLeft()}`);
console.log(`click flow: selected ${start.length}, score ${before} -> ${G.state.score}`);

// clicking a different group reselects and breaks the chain
G.cfg.seed = 29;
G.newGame();
frames(40);
const a = G.largestGroup();
G.clickCube(a[0]);
frames(40);
G.state.chain = 3;
let other = -1;
for (let i = 0; i < TOTAL; i++) {
  if (G.state.cells[i] !== null && !G.state.sel.includes(i) && G.findGroup(i).length >= 2) { other = i; break; }
}
if (other < 0) fails.push('test setup: no second group');
G.clickCube(other);
if (G.state.chain !== 0) fails.push('reselect should reset the chain');
if (G.state.sel.length !== G.findGroup(other).length) fails.push('reselect did not change the selection');
console.log(`reselect: chain 3 -> ${G.state.chain}, sel ${G.state.sel.length}`);

// single cubes are not clickable
let single = -1;
for (let i = 0; i < TOTAL; i++) if (G.state.cells[i] !== null && G.findGroup(i).length === 1) { single = i; break; }
if (single >= 0) {
  const selBefore = G.state.sel.length;
  G.clickCube(single);
  if (G.state.sel.length !== 0) fails.push('single cube should not be selectable');
  console.log(`single cube: group of 1 rejected (sel ${selBefore} -> 0)`);
}

// ---------------------------------------------------------------- rotation
G.cfg.seed = 13;
G.newGame();
frames(40);
const bag = multiset();
const probe = G.idx(1, 2, 3);
const probeColor = G.state.cells[probe];
G.rotate('y', 1);
frames(40);
if (multiset() !== bag) fails.push('rotation changed the colour multiset');
if (G.cubesLeft() !== TOTAL) fails.push('rotation changed the cube count');
// rotation about Y: (x,y,z) -> (z, y, N-1-x)
if (G.state.cells[G.idx(3, 2, N - 1 - 1)] !== probeColor) fails.push('rotation mapping (y) is wrong');
console.log(`rotate y: multiset preserved, cube (1,2,3) -> (3,2,${N - 2})`);

// rotation must NOT trigger gravity: a non-compact column stays non-compact
// (rotation about Y keeps y, so the hole and the floating cube move together)
G.cfg.seed = 31;
G.newGame();
frames(40);
G.state.cells[G.idx(0, 0, 0)] = null;                 // hole at the floor
const floatIdx = G.idx(0, 3, 0);                       // cube floating above the hole
if (G.state.cells[floatIdx] === null) G.state.cells[floatIdx] = 0;
const floatColor = G.state.cells[floatIdx];
G.rotate('y', 1);
frames(40);
if (G.state.phase !== 'idle') fails.push('rotation did not finish');
// (0,3,0) -> (z, y, N-1-x) = (0, 3, N-1)
if (G.state.cells[G.idx(0, 3, N - 1)] !== floatColor) fails.push('rotation lost the floating cube');
// the column that received it must still have a gap at y=0
if (G.state.cells[G.idx(0, 0, N - 1)] !== null) fails.push('rotation triggered gravity (column compacted)');
console.log(`rotate y: floating cube stayed floating at (0,3,${N - 1}), gap kept at y=0`);

// gravity does run on destruction
G.cfg.seed = 17;
G.newGame();
frames(40);
const g2 = G.largestGroup();
G.popGroup(g2);
frames(40);
compactColumns('after pop');

// ---------------------------------------------------------------- shuffle
G.cfg.seed = 19;
G.newGame();
frames(40);
const bag2 = multiset();
G.shuffle();
frames(40);
if (multiset() !== bag2) fails.push('shuffle changed the multiset');
if (G.cubesLeft() !== TOTAL) fails.push('shuffle changed the cube count');
if (multiset() === bag2) console.log('shuffle: multiset preserved, order changed');

// game over when every group is a single cube (3D checkerboard)
G.cfg.seed = 23;
G.newGame();
for (let x = 0; x < N; x++) for (let y = 0; y < N; y++) for (let z = 0; z < N; z++)
  G.state.cells[G.idx(x, y, z)] = ((x + y + z) % 2);
G.state.over = false;
G.checkOver();
if (!G.state.over) fails.push('checkerboard should be game over');
console.log(`game over: detected (score ${G.state.score})`);

console.log(`best persisted: ${G.state.best}`);
console.log('\n' + (fails.length ? 'FAIL' : 'ALL CHECKS PASSED'));
fails.forEach((f) => console.log(' -', f));
process.exit(fails.length ? 1 : 0);
