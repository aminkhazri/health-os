// Unit tests for the quick-add text parser (src/Parser.html), run against the real seed library in src/Food.js.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = f => fs.readFileSync(path.join(__dirname, '..', 'src', f), 'utf8');
const ctx = { globalThis: {} };
vm.runInNewContext(read('Parser.html').replace(/<\/?script>/g, ''), ctx);
const parseQuick = ctx.globalThis.parseQuick;
vm.runInNewContext(read('Food.js') + '\n;globalThis.SEED = FOOD_SEED;', ctx);
const library = ctx.globalThis.SEED.map(r => ({ name: r[0], portion: r[1], cat: r[2], kcal: r[3], w: r[7], caf: r[8], kw: r[9] }));

// Results come from a vm sandbox (different realm), so copy into plain arrays before deepEqual.
const plain = v => JSON.parse(JSON.stringify(v));
const names = text => plain(parseQuick(text, library).items.map(x => `${x.qty}x ${library[x.i].name}`));

test('single items and quantities', () => {
  assert.deepEqual(names('2 eggs'), ['2x Egg, large']);
  assert.deepEqual(names('a banana'), ['1x Banana']);
  assert.deepEqual(names('celsius'), ['1x Celsius energy drink']);
  assert.deepEqual(names('half a smoothie'), ['0.5x Smoothie (milk, banana, PB, oats, yogurt)']);
});

test('several items in one line', () => {
  assert.deepEqual(names('2 eggs and toast, coffee'), ['2x Egg, large', '1x Whole-wheat bread', '1x Coffee, black']);
  assert.deepEqual(names('2 salmon wraps and a greek yogurt'), ['2x Salmon, egg, spinach & cheese wrap', '1x Greek yogurt, plain whole-milk']);
});

test('longest phrase wins over its parts', () => {
  assert.deepEqual(names('chicken and rice'), ['1x Home plate: chicken, rice & veg']);
  assert.deepEqual(names('coffee with milk'), ['1x Coffee with milk & sugar']);
  assert.deepEqual(names('water bottle'), ['1x Water bottle']);
});

test('ounces convert to portions', () => {
  assert.deepEqual(names('16 oz water'), ['2x Water']);
  assert.deepEqual(names('16oz coffee'), ['2x Coffee, black']);
  assert.deepEqual(names('8 oz chicken'), ['2x Chicken breast, cooked']);
});

test('unrecognised food is returned for a one-time calorie prompt', () => {
  const r = plain(parseQuick('turkey sandwich', library));
  assert.equal(r.items.length, 0);
  assert.deepEqual(r.unknown, ['turkey sandwich']);
  const mixed = plain(parseQuick('2 eggs and a bagel', library));
  assert.deepEqual(mixed.items.map(x => library[x.i].name), ['Egg, large']);
  assert.deepEqual(mixed.unknown, ['bagel']);
});
