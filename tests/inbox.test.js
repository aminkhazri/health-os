const test = require('node:test');
const assert = require('node:assert');
const { cleanDay_, sameText_, normalizeFields_ } = require('../inbox/Inbox.js');

const T = '2026-11-15';
test('accepts plain numbers and rounds', () => {
  assert.deepStrictEqual({ ...cleanDay_({ steps: 8432, active_kcal: 512.7 }, T) }, { date: T, steps: 8432, kcal: 513 });
});
test('accepts Shortcut-style text like "8,432 steps"', () => {
  assert.deepStrictEqual({ ...cleanDay_({ steps: '8,432 steps', active_kcal: '' }, T) }, { date: T, steps: 8432, kcal: null });
});
test('rejects empty, negative-looking junk and absurd values', () => {
  assert.strictEqual(cleanDay_({}, T), null);
  assert.strictEqual(cleanDay_({ steps: 'abc' }, T), null);
  assert.strictEqual(cleanDay_({ steps: 999999 }, T), null);
});
test('uses a valid past date, defaults to today, refuses the future', () => {
  assert.strictEqual(cleanDay_({ steps: 1, date: '2026-11-14' }, T).date, '2026-11-14');
  assert.strictEqual(cleanDay_({ steps: 1, date: 'yesterday' }, T).date, T);
  assert.strictEqual(cleanDay_({ steps: 1, date: '2026-11-16' }, T), null);
});
test('sameText_ compares exactly', () => {
  assert.ok(sameText_('abc', 'abc'));
  assert.ok(!sameText_('abc', 'abd'));
  assert.ok(!sameText_('abc', 'abcd'));
});
test('normalizeFields_ accepts spaced / capitalized names', () => {
  assert.deepStrictEqual({ ...normalizeFields_({ 'Steps ': 5, 'active kcal': 7, key: 'x' }) }, { steps: 5, active_kcal: 7 });
  assert.deepStrictEqual({ ...normalizeFields_({ 'Active Energy': 9 }) }, { active_kcal: 9 });
});
