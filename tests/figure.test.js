// Unit tests for the animated demo figure (src/Figure.html): pose blending, joint math, and that every move has a sane figure.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ctx = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'src', 'Figure.html'), 'utf8').replace(/<\/?script>/g, ''), ctx);
const { FIGS, figPoseAt, figJoints, figFrame, figDuration } = ctx.globalThis;
const { WORKOUTS, PROJECTS } = require('../src/WebApp.js');
const { STRETCHES } = require('../src/Stretch.js');
const near = (a, b, tol) => Math.abs(a - b) <= (tol || 0.01);
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const eachTime = (name, step, fn) => { for (let t = 0; t <= figDuration(name); t += step) fn(t, figJoints(FIGS[name], figPoseAt(FIGS[name], t))); };

test('every exercise and every stretch has an animated figure, and nothing extra', () => {
  const names = [].concat(...Object.values(WORKOUTS), ...Object.values(PROJECTS).map(p => p.ex), Object.keys(STRETCHES));
  names.forEach(n => assert.ok(FIGS[n], 'no figure for ' + n));
  Object.keys(FIGS).forEach(n => assert.ok(names.includes(n), 'figure for unknown move ' + n));
});

test('a pose at a keyframe equals that keyframe, the loop wraps, and keyframe times increase', () => {
  const f = FIGS['Goblet squat'];
  assert.ok(near(figPoseAt(f, 0).legU, 0));
  assert.ok(near(figPoseAt(f, 2.2).legU, 75));
  assert.ok(near(figPoseAt(f, figDuration('Goblet squat') + 2.2).legU, 75));
  const mid = figPoseAt(f, 1.1).legU;
  assert.ok(mid > 30 && mid < 45, 'halfway through the descent is about half the angle');
  Object.entries(FIGS).forEach(([n, g]) => g.keys.forEach((k, i) => { if (i) assert.ok(k.at > g.keys[i - 1].at, n); }));
});

test('far-side limbs copy the near side in the side view and mirror it in the front view', () => {
  const s = figPoseAt(FIGS['Goblet squat'], 2.2), f = figPoseAt(FIGS['Dumbbell lateral raise'], 1.3);
  assert.equal(s.legU2, s.legU);
  assert.equal(f.armU2, -f.armU);
});

test('planted feet never slide', () => {
  Object.entries(FIGS).filter(([, f]) => f.anchor && !f.ik).forEach(([name, f]) => eachTime(name, 0.25, (t, j) =>
    assert.ok(dist(j.near.ank, f.anchor) < 0.01, name + ' at ' + t)));
  Object.entries(FIGS).filter(([, f]) => f.ankle2).forEach(([name, f]) => eachTime(name, 0.25, (t, j) =>
    assert.ok(dist(j.far.ank, f.ankle2) < 2.5, name + ' far foot at ' + t + ': ' + dist(j.far.ank, f.ankle2).toFixed(1))));
});

test('pinned hands stay put and bones keep their length', () => {
  eachTime('Push-up', 0.5, (t, j) => {
    assert.ok(dist(j.near.hand, [170, 195]) < 0.6, 'hands pinned at ' + t);
    assert.ok(near(dist(j.sh, j.near.el), 30, 0.6), 'upper arm length at ' + t);
    assert.ok(j.near.el[0] <= j.sh[0] + 1, 'elbow bends back at ' + t);
  });
  Object.keys(FIGS).forEach(name => eachTime(name, 0.5, (t, j) => {
    const hip = j.front ? j.near.hipJ : j.hip;
    assert.ok(near(dist(hip, j.near.knee), 44, 0.6) && near(dist(j.near.knee, j.near.ank), 42, 0.6), name + ' leg bones at ' + t);
  }));
});

test('every figure stays inside its drawing area and above the floor', () => {
  Object.entries(FIGS).forEach(([name, f]) => {
    const [vx, vy, vw, vh] = (f.view || '0 0 240 212').split(' ').map(Number);
    eachTime(name, 0.2, (t, j) => {
      const pts = [j.head, j.near.knee, j.near.ank, j.near.toe, j.near.el, j.near.hand, j.far.knee, j.far.ank, j.far.toe, j.far.el, j.far.hand];
      pts.forEach((p, i) => {
        const where = `${name} at ${t.toFixed(1)}, point ${i}: ${p.map(Math.round)}`;
        assert.ok(p[0] >= vx + 4 && p[0] <= vx + vw - 4, 'x out of view: ' + where);
        assert.ok(p[1] >= vy + 4, 'above the view: ' + where);
        assert.ok(p[1] <= (f.noGround ? vy + vh - 4 : 199.5), 'below the floor: ' + where);
      });
      assert.ok(j.head[1] - 11 >= vy - 0.5, name + ' head is cut off at ' + t.toFixed(1));
    });
  });
});

test('a frame is drawable markup with a cue', () => {
  Object.keys(FIGS).forEach(name => {
    const f = figFrame(name, 0.1);
    assert.match(f.svg, /<circle class="fg-head/);
    assert.ok(!/NaN/.test(f.svg), name + ' has NaN in its drawing');
    assert.ok(f.say && f.say.length > 5, name + ' needs a cue');
  });
});

test('a target line becomes a plan the guided set can follow', () => {
  const { figPlan } = ctx.globalThis, plain = o => JSON.parse(JSON.stringify(o));
  assert.deepEqual(plain(figPlan('3 × 8–12')), { sets: 3, sides: 1, lo: 8, hi: 12, rest: 75 });
  assert.deepEqual(plain(figPlan('3 × 8–10 each leg')), { sets: 3, sides: 2, lo: 8, hi: 10, rest: 75 });
  assert.deepEqual(plain(figPlan('2 × 30–45 s each side')), { sets: 2, sides: 2, hold: 30, rest: 45 });
  assert.deepEqual(plain(figPlan('2 rounds × 10 s each way (front, back, left, right)')), { sets: 2, sides: 4, hold: 10, rest: 45 });
  assert.deepEqual(plain(figPlan('2 × 10, hold 3 s')), { sets: 2, sides: 1, lo: 10, hi: 10, rest: 75 });
  assert.deepEqual(plain(figPlan('3 × as many as you can, minus 2')), { sets: 3, sides: 1, lo: 0, hi: 0, rest: 75 });
  assert.deepEqual(plain(figPlan('', 40)), { sets: 1, sides: 1, hold: 40, rest: 0 });
  const all = Object.assign({}, require('../src/WebApp.js').WORKOUT_INFO.targets, ...Object.values(PROJECTS).map(p => p.targets));
  Object.entries(all).forEach(([n, t]) => { const p = figPlan(t); assert.ok(p.sets >= 2 && (p.hold || p.hi || /as many/.test(t)), n + ': ' + t); });
});

