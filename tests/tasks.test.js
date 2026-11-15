// Unit tests for the pure scheduling logic in src/Code.js.
// Run: npm test   (uses Node's built-in test runner — no dependencies)
const test = require('node:test');
const assert = require('node:assert/strict');

// Code.js reads CONFIG at call time; provide a test schedule as a global.
global.CONFIG = {
  DAYS: { work: [7, 1, 2, 3], shift: [1, 2, 3, 4, 5], workout: [4, 6], prep: [6, 7, 1, 2] },
  WORKDAY_LUNCH: 'Packed lunch.',
  WATER_GOAL: 'Water ~3 L',
  WINDDOWN: 'Wind-down',
};
const { buildTaskItems_, firstMatchingDay_ } = require('../src/Code.js');
const titles = (dow, active = true) => buildTaskItems_(dow, active).map(([t]) => t);

test('every day has the core checklist, in order, ending with wind-down', () => {
  for (let dow = 1; dow <= 7; dow++) {
    const t = titles(dow);
    assert.equal(t[0], 'Weigh in + log tracker row (1 min)');
    assert.ok(t.includes('Breakfast') && t.includes('Lunch') && t.includes('Dinner'));
    assert.equal(t[t.length - 1], 'Wind-down');
  }
});

test('workout task only on configured training days (Thu=4, Sat=6)', () => {
  for (let dow = 1; dow <= 7; dow++) {
    assert.equal(titles(dow).includes('Workout (A/B) + log sets'), [4, 6].includes(dow), `dow ${dow}`);
  }
});

test('shift tasks appear on shift days only while the phase is active', () => {
  assert.ok(titles(1, true).includes('Pack shift snack + water'));      // Monday, Phase 1
  assert.ok(!titles(1, false).includes('Pack shift snack + water'));    // Monday, Phase 2
  assert.ok(!titles(7, true).includes('Pack shift snack + water'));     // Sunday: no shift
  const water = buildTaskItems_(1, true).find(([t]) => t === 'Water ~3 L');
  assert.equal(water[1], 'Extra bottle for the shift.');
});

test('lunch note differs on workdays vs days off', () => {
  const lunch = dow => buildTaskItems_(dow, true).find(([t]) => t === 'Lunch')[1];
  assert.equal(lunch(7), 'Packed lunch.');   // Sunday is a workday
  assert.equal(lunch(5), 'Plate template.'); // Friday is a day off
});

test('firstMatchingDay_ skips to the first configured weekday', () => {
  const mon = new Date(2026, 10, 16); // Monday
  assert.equal(firstMatchingDay_(mon, ['THURSDAY', 'SATURDAY']).getDate(), 19);
  assert.equal(firstMatchingDay_(mon, ['MONDAY']).getDate(), 16);
  assert.equal(firstMatchingDay_(mon, ['SUNDAY']).getDate(), 22);
});
