const test = require('node:test');
const assert = require('node:assert');
const { STRETCHES, STRETCH_ROUTINES, VIDEOS, routineSeconds_ } = require('../src/Stretch.js');
const { WORKOUTS, PROJECTS } = require('../src/WebApp.js');

test('routine length counts each-side steps twice', () => {
  assert.equal(routineSeconds_({ steps: [['a', 30, true], ['b', 45, false]] }), 105);
});

test('every routine is a whole number of minutes between 4 and 8', () => {
  STRETCH_ROUTINES.forEach(r => {
    const s = routineSeconds_(r);
    assert.equal(s % 60, 0, r.name + ' is ' + s + ' s');
    assert.ok(s >= 240 && s <= 480, r.name);
  });
});

test('every routine step is a known stretch with a cue', () => {
  STRETCH_ROUTINES.forEach(r => r.steps.forEach(([name]) => assert.ok(STRETCHES[name], name)));
});

test('every exercise and every stretch has a well-formed video ID', () => {
  const names = [].concat(...Object.values(WORKOUTS), ...Object.values(PROJECTS).map(p => p.ex), Object.keys(STRETCHES));
  names.forEach(n => assert.match(VIDEOS[n] || '', /^[A-Za-z0-9_-]{11}$/, n));
});

test('every project exercise has a target, and projects never share a letter with a main workout', () => {
  Object.entries(PROJECTS).forEach(([k, p]) => {
    assert.ok(!WORKOUTS[k], k);
    p.ex.forEach(ex => assert.ok(p.targets[ex], ex));
  });
});
