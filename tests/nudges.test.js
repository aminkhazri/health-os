const test = require('node:test');
const assert = require('node:assert');
const { dueCheckpoint_, nudgeFor_, NUDGE_PLAN } = require('../src/Nudges.js');

test('a checkpoint is due only in its window and only once a day', () => {
  // Monday (1) 10:07 -> the 10:00 workday checkpoint
  assert.equal(dueCheckpoint_(NUDGE_PLAN, 1, 607, [], 30).at, 600);
  assert.equal(dueCheckpoint_(NUDGE_PLAN, 1, 607, [600], 30), null);      // already fired today
  assert.equal(dueCheckpoint_(NUDGE_PLAN, 1, 645, [], 30), null);         // window closed
  assert.equal(dueCheckpoint_(NUDGE_PLAN, 1, 595, [], 30), null);         // not yet
  assert.equal(dueCheckpoint_(NUDGE_PLAN, 4, 607, [], 30), null);         // Thursday has no 10:00 checkpoint
  assert.equal(dueCheckpoint_(NUDGE_PLAN, 4, 620, [], 30).at, 615);       // Thursday 10:15
});
test('no nudge when on pace', () => {
  assert.equal(nudgeFor_({ at: 600, water: 50, calm: 0 }, 50, 0), null);
  assert.equal(nudgeFor_({ at: 930, water: 100, calm: 3 }, 110, 5), null);
});
test('water, calm, or both', () => {
  assert.match(nudgeFor_({ at: 600, water: 50, calm: 0 }, 20, 0).title, /^💧 Catch up on water: 20\/50/);
  assert.match(nudgeFor_({ at: 930, water: 100, calm: 3 }, 120, 1).title, /^🧘/);
  assert.match(nudgeFor_({ at: 930, water: 100, calm: 3 }, 60, 0).title, /^💧🧘/);
  assert.match(nudgeFor_({ at: 600, water: 50, calm: 0 }, 20, 0).desc, /full 24 oz bottle/);
  assert.match(nudgeFor_({ at: 600, water: 50, calm: 0 }, 45, 0).desc, /few big sips/);
});

test('UPS nights get one 8 PM water check; Saturday and Sunday do not', () => {
  [1, 2, 3, 4, 5].forEach(d => assert.deepEqual(dueCheckpoint_(NUDGE_PLAN, d, 1205, [], 30), { at: 1200, water: 110, calm: 0 }));
  [6, 7].forEach(d => assert.equal(dueCheckpoint_(NUDGE_PLAN, d, 1205, [], 30), null));
  assert.equal(nudgeFor_({ at: 1200, water: 110, calm: 0 }, 112, 0), null);
  assert.match(nudgeFor_({ at: 1200, water: 110, calm: 0 }, 96, 0).title, /96\/110/);
});
