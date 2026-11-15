// Validates a config file's shape (defaults to config.example.js; set CONFIG_FILE to check your own).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const file = process.env.CONFIG_FILE || path.join(__dirname, '..', 'config.example.js');
const names = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];
const sandbox = { CalendarApp: { Weekday: Object.fromEntries(names.map(n => [n, n])) } };
vm.runInNewContext(fs.readFileSync(file, 'utf8') + '\n;this.CONFIG = CONFIG; this.EVENTS = EVENTS;', sandbox);
const { CONFIG, EVENTS } = sandbox;

test('CONFIG has the required keys', () => {
  for (const k of ['TZ', 'CALENDAR_NAME', 'TASKLIST_NAME', 'SHEET_ID', 'SERIES_START', 'DAYS', 'WATER_GOAL', 'WINDDOWN', 'WEEKLY_WORKOUT_TARGET']) {
    assert.ok(k in CONFIG, `missing ${k}`);
  }
  assert.ok(CONFIG.SERIES_START instanceof Date || Object.prototype.toString.call(CONFIG.SERIES_START) === '[object Date]');
});

test('DAYS use ISO weekdays 1–7', () => {
  for (const [k, list] of Object.entries(CONFIG.DAYS)) {
    assert.ok(Array.isArray(list), k);
    list.forEach(d => assert.ok(Number.isInteger(d) && d >= 1 && d <= 7, `${k}: ${d}`));
  }
});

test('every EVENTS row is well-formed', () => {
  assert.ok(EVENTS.length > 0);
  EVENTS.forEach(([title, days, hh, mm, dur, popup, desc], i) => {
    assert.equal(typeof title, 'string', `row ${i} title`);
    assert.ok(days.length && days.every(d => names.includes(d)), `row ${i} days`);
    assert.ok(hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59, `row ${i} time`);
    assert.ok(dur > 0, `row ${i} duration`);
    assert.ok(popup === null || popup >= 0, `row ${i} popup`);
    assert.equal(typeof desc, 'string', `row ${i} description`);
  });
});
