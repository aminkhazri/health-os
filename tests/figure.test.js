// Unit tests for the animated demo figure (src/Figure.html): the pose blending and the joint math.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ctx = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'src', 'Figure.html'), 'utf8').replace(/<\/?script>/g, ''), ctx);
const { FIGS, figPoseAt, figJoints } = ctx.globalThis;
const { WORKOUTS, PROJECTS } = require('../src/WebApp.js');
const { STRETCHES } = require('../src/Stretch.js');
const near = (a, b, tol) => Math.abs(a - b) <= (tol || 0.01);

test('a pose at a keyframe time equals that keyframe, and the loop wraps', () => {
  const f = FIGS['Goblet squat'];
  assert.ok(near(figPoseAt(f, 0).legU, 0));
  assert.ok(near(figPoseAt(f, 2.2).legU, 75));
  assert.ok(near(figPoseAt(f, 5 + 2.2).legU, 75));       // one full loop later
  const mid = figPoseAt(f, 1.1).legU;
  assert.ok(mid > 30 && mid < 45, 'halfway through the descent is about half the angle');
});

test('far-side limbs copy the near side unless given', () => {
  const p = figPoseAt(FIGS['Goblet squat'], 2.2);
  assert.equal(p.legU2, p.legU);
  assert.equal(p.armL2, p.armL);
});

test('anchored feet never slide: the ankle stays on its anchor through the whole move', () => {
  ['Goblet squat', 'Push-up bottom hold'].forEach(name => {
    const f = FIGS[name], dur = f.keys[f.keys.length - 1].at;
    for (let t = 0; t <= dur; t += 0.25) {
      const j = figJoints(f, figPoseAt(f, t));
      assert.ok(near(j.near.ank[0], f.anchor[0]) && near(j.near.ank[1], f.anchor[1]), name + ' at ' + t);
    }
  });
});

test('the figure stays inside the drawing area and above the floor', () => {
  Object.entries(FIGS).forEach(([name, f]) => {
    const dur = f.keys[f.keys.length - 1].at;
    for (let t = 0; t <= dur; t += 0.2) {
      const j = figJoints(f, figPoseAt(f, t));
      [j.hip, j.sh, j.head, j.near.knee, j.near.ank, j.near.toe, j.near.el, j.near.hand].forEach(p => {
        assert.ok(p[0] >= 8 && p[0] <= 232 && p[1] >= 10 && p[1] <= 199, `${name} at ${t.toFixed(1)}: ${p.map(Math.round)}`);
      });
    }
  });
});

test('push-up: hands stay on the floor under the shoulders', () => {
  const f = FIGS['Push-up bottom hold'];
  for (let t = 0; t <= 10; t += 0.5) {
    const j = figJoints(f, figPoseAt(f, t));
    assert.ok(near(j.near.hand[0], 170) && near(j.near.hand[1], 195), 'hands pinned at ' + t);
    assert.ok(near(Math.hypot(j.near.el[0] - j.sh[0], j.near.el[1] - j.sh[1]), 30, 0.6), 'upper arm keeps its length at ' + t);
    assert.ok(j.near.el[0] <= j.sh[0] + 1, 'elbow bends back, not forward, at ' + t);
  }
});

test('every figure belongs to a real exercise or stretch, and keyframe times increase', () => {
  const names = new Set([].concat(...Object.values(WORKOUTS), ...Object.values(PROJECTS).map(p => p.ex), Object.keys(STRETCHES)));
  Object.entries(FIGS).forEach(([name, f]) => {
    assert.ok(names.has(name), name);
    f.keys.forEach((k, i) => { if (i) assert.ok(k.at > f.keys[i - 1].at, name); });
  });
});
