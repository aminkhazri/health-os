/**
 * Health OS — food & drink logging with automatic calorie / protein / water / caffeine totals.
 *
 * Sheet tabs (created / upgraded by setupFood — idempotent, safe to re-run):
 *   Foods     — library: Food | Portion | Category | kcal | Protein g | Carbs g | Fat g | Water oz | Caffeine mg | Keywords
 *   Food Log  — one row per item: Date | Time | Meal | Food | Qty | kcal | Protein g | Carbs g | Fat g | Water oz | Caffeine mg
 * Daily Log gets M/N/O/P = calories / protein / water / caffeine per day (SUMIFS on Food Log);
 * Weekly Summary gets L = average calories on days with food logged.
 *
 * The app's quick-add box matches what you type against the Keywords column (comma-separated phrases).
 * Values are typical estimates for the stated portion — edit any row in the Foods tab.
 */

const FOOD_HEADERS = ['Food', 'Portion', 'Category', 'kcal', 'Protein g', 'Carbs g', 'Fat g', 'Water oz', 'Caffeine mg', 'Keywords'];
const LOG_HEADERS = ['Date', 'Time', 'Meal', 'Food', 'Qty', 'kcal', 'Protein g', 'Carbs g', 'Fat g', 'Water oz', 'Caffeine mg'];
const MEAL_CODES = { Breakfast: 'B', Lunch: 'L', Snack: 'S', Dinner: 'D' }; // 'Drink' entries don't tick a meal

// [Food, Portion, Category, kcal, protein, carbs, fat, water oz, caffeine mg, keywords]
const FOOD_SEED = [
  ['Salmon, egg, spinach & cheese wrap', '1 wrap', 'Meals', 380, 26, 23, 20, 0, 0, 'salmon wrap, wrap, lunch wrap'],
  ['Smoothie (milk, banana, PB, oats, yogurt)', '1 full blender', 'Meals', 830, 40, 85, 39, 12, 0, 'smoothie, shake'],
  ['Eggs + tortilla + cheese', '3 eggs, 1 tortilla, 1 oz cheese', 'Meals', 460, 30, 23, 27, 0, 0, 'egg tortilla, breakfast taco, egg wrap'],
  ['Oatmeal with milk & banana', '1 bowl', 'Meals', 405, 14, 66, 11, 8, 0, 'oatmeal, porridge'],
  ['Home plate: chicken, rice & veg', '1 plate', 'Meals', 760, 58, 77, 20, 0, 0, 'chicken and rice, chicken rice, chicken dinner'],
  ['Home plate: salmon, potatoes & veg', '1 plate', 'Meals', 700, 45, 62, 28, 0, 0, 'salmon and potatoes, salmon dinner'],
  ['Home plate: lentils / Mediterranean', '1 plate', 'Meals', 720, 33, 110, 16, 0, 0, 'lentil plate, lentil dinner, mediterranean'],
  ['Small meal (estimate)', '1', 'Meals', 400, 20, 40, 15, 0, 0, 'small meal, light meal'],
  ['Medium meal (estimate)', '1', 'Meals', 600, 30, 60, 22, 0, 0, 'medium meal, meal'],
  ['Large meal (estimate)', '1', 'Meals', 900, 45, 90, 35, 0, 0, 'large meal, big meal, big plate'],
  ['Egg, large', '1 egg', 'Protein', 72, 6, 0, 5, 0, 0, 'egg, eggs, boiled egg, fried egg, scrambled eggs'],
  ['Greek yogurt, plain whole-milk', '3/4 cup', 'Protein', 160, 16, 6, 8, 0, 0, 'greek yogurt, yogurt'],
  ['Chicken breast, cooked', '4 oz (1 palm)', 'Protein', 185, 35, 0, 4, 0, 0, 'chicken, chicken breast'],
  ['Salmon, cooked', '4 oz (1 palm)', 'Protein', 235, 25, 0, 14, 0, 0, 'salmon'],
  ['Cheddar cheese', '1 oz slice', 'Protein', 115, 7, 0, 9, 0, 0, 'cheese, cheddar'],
  ['Lentils, cooked', '1 cup', 'Protein', 230, 18, 40, 1, 0, 0, 'lentils'],
  ['Tuna or salmon pouch', '1 pouch', 'Protein', 80, 16, 0, 1, 0, 0, 'tuna, tuna pouch, salmon pouch'],
  ['String cheese', '1 stick', 'Protein', 80, 7, 1, 6, 0, 0, 'string cheese'],
  ['Rice, cooked', '1 cup (1 fist)', 'Carbs', 205, 4, 45, 0, 0, 0, 'rice'],
  ['Potato, baked', '1 medium', 'Carbs', 160, 4, 37, 0, 0, 0, 'potato, potatoes'],
  ['Whole-wheat tortilla', '1 large', 'Carbs', 130, 4, 22, 4, 0, 0, 'tortilla'],
  ['Oats, dry', '1/2 cup', 'Carbs', 150, 5, 27, 3, 0, 0, 'oats'],
  ['Whole-wheat bread', '1 slice', 'Carbs', 80, 4, 14, 1, 0, 0, 'bread, toast'],
  ['Banana', '1 medium', 'Carbs', 105, 1, 27, 0, 0, 0, 'banana'],
  ['Apple', '1 medium', 'Carbs', 95, 0, 25, 0, 0, 0, 'apple'],
  ['Mixed vegetables', '1 cup', 'Carbs', 60, 3, 12, 0, 0, 0, 'vegetables, veggies, veg, salad'],
  ['Spinach, raw', '1 cup', 'Carbs', 7, 1, 1, 0, 0, 0, 'spinach'],
  ['Mixed nuts', '1 oz handful', 'Snacks', 170, 5, 6, 15, 0, 0, 'nuts, mixed nuts, almonds, cashews'],
  ['Peanut butter', '2 tbsp', 'Snacks', 190, 7, 7, 16, 0, 0, 'peanut butter, pb'],
  ['PB + banana tortilla roll-up', '1 roll-up', 'Snacks', 425, 12, 56, 20, 0, 0, 'roll up, roll-up, pb banana wrap'],
  ['Trail mix', '1/4 cup', 'Snacks', 175, 5, 16, 11, 0, 0, 'trail mix'],
  ['Olive oil (cooking)', '1 tbsp', 'Snacks', 120, 0, 0, 14, 0, 0, 'olive oil'],
  ['Water', '8 oz glass', 'Drinks', 0, 0, 0, 0, 8, 0, 'water, glass of water'],
  ['Water bottle', '24 oz', 'Drinks', 0, 0, 0, 0, 24, 0, 'water bottle, bottle of water'],
  ['Whole milk', '1 cup', 'Drinks', 150, 8, 12, 8, 8, 0, 'milk, glass of milk, whole milk'],
  ['Coffee, black', '1 cup (8 oz)', 'Drinks', 2, 0, 0, 0, 8, 95, 'coffee, black coffee'],
  ['Coffee with milk & sugar', '1 cup (8 oz)', 'Drinks', 60, 1, 9, 2, 8, 95, 'coffee with milk, coffee with cream, latte'],
  ['Orange juice', '1 cup', 'Drinks', 110, 2, 26, 0, 8, 0, 'orange juice, juice, oj'],
  ['Soda', '12 oz can', 'Drinks', 140, 0, 39, 0, 12, 34, 'soda, coke, pepsi, pop'],
  ['Celsius energy drink', '12 oz can', 'Drinks', 10, 0, 2, 0, 12, 250, 'celsius'],
  ['Energy drink', '16 oz can', 'Drinks', 210, 0, 54, 0, 16, 160, 'energy drink, monster, red bull'],
  ['Espresso', '1 shot', 'Drinks', 3, 0, 0, 0, 1, 63, 'espresso, shot of espresso'],
  ['Tea', '1 cup (8 oz)', 'Drinks', 2, 0, 0, 0, 8, 47, 'tea, black tea, green tea'],
];

/** ONE-TIME / UPGRADE (idempotent): create or upgrade the Foods + Food Log tabs and the total columns. */
function setupFood() {
  const ss = ss_();
  let foods = ss.getSheetByName('Foods');
  if (!foods) {
    foods = ss.insertSheet('Foods');
    foods.getRange(1, 1, 1, FOOD_HEADERS.length).setValues([FOOD_HEADERS]).setFontWeight('bold');
    foods.getRange(2, 1, FOOD_SEED.length, FOOD_HEADERS.length).setValues(FOOD_SEED);
    foods.setFrozenRows(1); foods.setColumnWidth(1, 300); foods.setColumnWidth(2, 200);
  } else {
    foods.getRange(1, 1, 1, FOOD_HEADERS.length).setValues([FOOD_HEADERS]).setFontWeight('bold');
    const n = Math.max(foods.getLastRow() - 1, 0);
    const rows = n ? foods.getRange(2, 1, n, FOOD_HEADERS.length).getValues() : [];
    const seedByName = Object.fromEntries(FOOD_SEED.map(r => [r[0], r]));
    rows.forEach((r, i) => {          // fill caffeine / keywords on older rows without touching edited numbers
      const s = seedByName[r[0]];
      if (s && r[8] === '') foods.getRange(i + 2, 9).setValue(s[8]);
      if (s && r[9] === '') foods.getRange(i + 2, 10).setValue(s[9]);
    });
    const have = new Set(rows.map(r => r[0]));
    const missing = FOOD_SEED.filter(r => !have.has(r[0]));
    if (missing.length) foods.getRange(foods.getLastRow() + 1, 1, missing.length, FOOD_HEADERS.length).setValues(missing);
  }
  foods.setColumnWidth(10, 320);

  let log = ss.getSheetByName('Food Log');
  if (!log) {
    log = ss.insertSheet('Food Log');
    log.setFrozenRows(1); log.setColumnWidth(4, 300);
    log.getRange('A2:A').setNumberFormat('ddd mmm d');
  }
  log.getRange(1, 1, 1, LOG_HEADERS.length).setValues([LOG_HEADERS]).setFontWeight('bold');

  const daily = ss.getSheetByName('Daily Log');
  const n = daily.getLastRow() - 1;
  daily.getRange(1, 13, 1, 4).setValues([['Calories (logged)', 'Protein g (logged)', 'Water oz (logged)', 'Caffeine mg (logged)']]).setFontWeight('bold');
  const f = [];
  for (let r = 2; r <= n + 1; r++) f.push(['F', 'G', 'J', 'K'].map(c => `=SUMIFS('Food Log'!${c}:${c},'Food Log'!A:A,A${r})`));
  daily.getRange(2, 13, n, 4).setFormulas(f).setNumberFormat('0');

  const wk = ss.getSheetByName('Weekly Summary');
  const wn = wk.getLastRow() - 1;
  wk.getRange(1, 12).setValue('Avg kcal (logged days)').setFontWeight('bold');
  const wf = [];
  for (let r = 2; r <= wn + 1; r++) wf.push([`=IFERROR(AVERAGEIFS('Daily Log'!M:M,'Daily Log'!K:K,A${r},'Daily Log'!M:M,">0"),"")`]);
  wk.getRange(2, 12, wn, 1).setFormulas(wf).setNumberFormat('0');
  const moved = refileDrinks_(ss);
  console.log('Foods: ' + (foods.getLastRow() - 1) + ' items | Food Log ready | daily totals incl. caffeine | drinks re-filed: ' + moved);
}

/** Upgrade helper: older app versions logged drinks under a meal. Move them to 'Drink' and fix the meal ticks. */
function refileDrinks_(ss) {
  const tz = ss.getSpreadsheetTimeZone(), log = ss.getSheetByName('Food Log');
  if (log.getLastRow() < 2) return 0;
  const drinkNames = new Set(ss.getSheetByName('Foods').getRange(2, 1, ss.getSheetByName('Foods').getLastRow() - 1, 3).getValues()
    .filter(r => r[2] === 'Drinks').map(r => r[0]));
  const days = {};
  let moved = 0;
  const full = log.getRange(2, 1, log.getLastRow() - 1, 4).getValues();
  full.forEach((r, i) => {
    if (r[0] instanceof Date && drinkNames.has(r[3]) && r[2] !== 'Drink') {
      log.getRange(i + 2, 3).setValue('Drink'); moved++;
      days[key_(r[0], tz)] = r[2];
    }
  });
  SpreadsheetApp.flush();
  Object.entries(days).forEach(([k, meal]) => untickMealIfEmpty_(ss, k, tz, meal));
  return moved;
}

/** Food data for one day: library, entries (with sheet row for deletion), totals, targets, frequent items. */
function getFoodData_(ss, dateKey, tz) {
  const foods = ss.getSheetByName('Foods'), log = ss.getSheetByName('Food Log');
  if (!foods || !log) return null;
  const library = foods.getLastRow() < 2 ? [] : foods.getRange(2, 1, foods.getLastRow() - 1, 10).getValues()
    .filter(r => r[0] !== '')
    .map(r => ({ name: String(r[0]), portion: String(r[1]), cat: String(r[2]), kcal: num_(r[3]) || 0, p: num_(r[4]) || 0, c: num_(r[5]) || 0,
      f: num_(r[6]) || 0, w: num_(r[7]) || 0, caf: num_(r[8]) || 0, kw: String(r[9] || '') }));
  const entries = [], counts = {};
  if (log.getLastRow() >= 2) {
    const all = log.getRange(2, 1, log.getLastRow() - 1, 11).getValues();
    all.forEach((r, i) => {
      if (!(r[0] instanceof Date)) return;
      if (i >= all.length - 300) counts[r[3]] = (counts[r[3]] || 0) + 1;
      if (key_(r[0], tz) === dateKey) {
        entries.push({ row: i + 2, time: String(r[1]), meal: String(r[2]), name: String(r[3]), qty: num_(r[4]) || 1,
          kcal: num_(r[5]) || 0, p: num_(r[6]) || 0, c: num_(r[7]) || 0, f: num_(r[8]) || 0, w: num_(r[9]) || 0, caf: num_(r[10]) || 0 });
      }
    });
  }
  const frequent = Object.entries(counts).filter(([n]) => !/^Water/.test(n)).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([n]) => n);
  const sum = k => Math.round(entries.reduce((a, e) => a + e[k], 0));
  return { library, entries, frequent,
    totals: { kcal: sum('kcal'), p: sum('p'), c: sum('c'), f: sum('f'), w: sum('w'), caf: sum('caf') },
    targets: { protein: CONFIG.PROTEIN_TARGET || 150, water: CONFIG.WATER_OZ_TARGET || 100, caffeine: CONFIG.CAFFEINE_LIMIT_MG || 400 } };
}

/**
 * Log one or more items in a single call.
 * items: [{ meal, name, qty, kcal, p, c, f, w, caf, saveToLibrary?, keyword?, cat?, portion? }]
 * kcal/p/c/f/w/caf are PER PORTION; qty multiplies them.
 */
function addFoods(dateKey, items) {
  if (!items || !items.length) throw new Error('Nothing to add.');
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone();
  const date = Utilities.parseDate(dateKey, tz, 'yyyy-MM-dd');
  const time = Utilities.formatDate(new Date(), tz, 'h:mm a');
  const rows = items.map(o => {
    const qty = Number(o.qty) || 1;
    const n = k => Math.round((Number(o[k]) || 0) * qty * 10) / 10;
    return [date, time, o.meal || 'Snack', o.name, qty, n('kcal'), n('p'), n('c'), n('f'), n('w'), n('caf')];
  });
  const log = ss.getSheetByName('Food Log');
  log.getRange(log.getLastRow() + 1, 1, rows.length, LOG_HEADERS.length).setValues(rows);
  const newLib = items.filter(o => o.saveToLibrary).map(o => [o.name, o.portion || '1 serving', o.cat || 'Meals',
    Number(o.kcal) || 0, Number(o.p) || 0, Number(o.c) || 0, Number(o.f) || 0, Number(o.w) || 0, Number(o.caf) || 0,
    String(o.keyword || o.name).toLowerCase()]);
  if (newLib.length) {
    const foods = ss.getSheetByName('Foods');
    foods.getRange(foods.getLastRow() + 1, 1, newLib.length, FOOD_HEADERS.length).setValues(newLib);
  }
  SpreadsheetApp.flush();
  autoMarkDay_(ss, dateKey, tz);
  return getAppData(dateKey);
}

/** Back-compat single add (used by older app versions). */
function addFood(o) { return addFoods(o.date, [o]); }

/** Remove one Food Log row (checks the date so a stale screen can't delete the wrong row). */
function deleteFood(row, dateKey) {
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone(), log = ss.getSheetByName('Food Log');
  const [d, , meal] = log.getRange(row, 1, 1, 3).getValues()[0];
  if (!(d instanceof Date) || key_(d, tz) !== dateKey) throw new Error('That entry changed — refresh and try again.');
  log.deleteRow(row);
  SpreadsheetApp.flush();
  untickMealIfEmpty_(ss, dateKey, tz, String(meal));
  return getAppData(dateKey);
}

function dailyRow_(ss, dateKey, tz) {
  const daily = ss.getSheetByName('Daily Log');
  const col = daily.getRange(2, 1, daily.getLastRow() - 1, 1).getValues();
  const i = col.findIndex(r => r[0] instanceof Date && key_(r[0], tz) === dateKey);
  return i < 0 ? null : { daily, row: i + 2 };
}

/** After logging: tick protein / water / meals on the Daily Log when targets are reached (never un-ticks). */
function autoMarkDay_(ss, dateKey, tz) {
  const fd = getFoodData_(ss, dateKey, tz);
  const d = dailyRow_(ss, dateKey, tz);
  if (!d) return;
  if (fd.totals.p >= fd.targets.protein * 0.95) d.daily.getRange(d.row, 5).setValue('Y');
  if (fd.totals.w >= fd.targets.water) d.daily.getRange(d.row, 7).setValue('Y');
  const have = new Set(String(d.daily.getRange(d.row, 12).getValue() || '').split(''));
  fd.entries.forEach(e => { if (MEAL_CODES[e.meal]) have.add(MEAL_CODES[e.meal]); });
  const codes = ['B', 'L', 'S', 'D'].filter(c => have.has(c)).join('');
  d.daily.getRange(d.row, 12).setValue(codes);
  d.daily.getRange(d.row, 6).setValue(codes.length || '');
}

/** After a delete: if no food is left for that meal, un-tick it on the Daily Log checklist. */
function untickMealIfEmpty_(ss, dateKey, tz, meal) {
  const code = MEAL_CODES[meal];
  if (!code) return;
  const fd = getFoodData_(ss, dateKey, tz);
  if (fd.entries.some(e => e.meal === meal)) return;
  const d = dailyRow_(ss, dateKey, tz);
  if (!d) return;
  const codes = String(d.daily.getRange(d.row, 12).getValue() || '').replace(code, '');
  d.daily.getRange(d.row, 12).setValue(codes);
  d.daily.getRange(d.row, 6).setValue(codes.length || '');
}
