// Unit tests for the rest-day recovery score (src/Recovery.html).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ctx = { globalThis: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'src', 'Recovery.html'), 'utf8').replace(/<\/?script>/g, ''), ctx);
const { recoveryScore, hrBaseline } = ctx.globalThis;

const goals = { sleepGoal: 7, kcalGoal: 2600, proteinGoal: 150, waterGoal: 125, calmGoal: 10, flexGoal: 5 };
const full = { ...goals, sleep: 7, kcal: 2600, protein: 150, water: 125, calm: 10, flex: 5 };

test('everything on target scores 100 with no weakest factor', () => {
  const r = recoveryScore({ ...full, hr: 60, hrBaseline: 62 });
  assert.equal(r.score, 100);
  assert.equal(r.weakest, null);
  assert.equal(r.usedHr, true);
});

test('nothing logged scores 0 and sleep is named first', () => {
  const r = recoveryScore({ ...goals });
  assert.equal(r.score, 0);
  assert.equal(r.weakest.name, 'Sleep');
});

test('short sleep pulls the score down by its weight', () => {
  // Sleep 5/7 h = 71.4% at weight 35 of 90 (no HR) -> everything else 100
  const r = recoveryScore({ ...full, sleep: 5 });
  assert.equal(r.score, Math.round((71.43 * 35 + 100 * 55) / 90));
  assert.equal(r.weakest.name, 'Sleep');
});

test('resting HR above your average costs 20 points per bpm, capped at 0', () => {
  assert.equal(recoveryScore({ ...full, hr: 63, hrBaseline: 60 }).parts.find(p => p.name === 'Resting HR').v, 40);
  assert.equal(recoveryScore({ ...full, hr: 70, hrBaseline: 60 }).parts.find(p => p.name === 'Resting HR').v, 0);
  assert.equal(recoveryScore({ ...full, hr: 70, hrBaseline: 60 }).score, 90);
});

test('missing heart rate or baseline leaves that factor out instead of counting 0', () => {
  assert.equal(recoveryScore({ ...full }).usedHr, false);
  assert.equal(recoveryScore({ ...full, hr: 60 }).score, 100);
});

test('baseline needs at least 3 readings', () => {
  assert.equal(hrBaseline([60, 62]), null);
  assert.equal(hrBaseline([60, 62, 64, null]), 62);
});
