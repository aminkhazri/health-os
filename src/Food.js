/**
 * Health OS — food & drink logging with automatic calorie / protein / water totals.
 *
 * Sheet tabs (created by setupFood):
 *   Foods      — your library: Food | Portion | Category | kcal | Protein g | Carbs g | Fat g | Water oz
 *   Food Log   — one row per thing eaten: Date | Time | Meal | Food | Qty | kcal | Protein g | Carbs g | Fat g | Water oz
 * Daily Log gets M/N/O = calories / protein / water totals per day (SUMIFS on Food Log),
 * Weekly Summary gets L = average calories on days with food logged.
 *
 * Values are typical USDA-style estimates for the stated portion — edit any row in the Foods tab.
 */

const FOOD_HEADERS = ['Food', 'Portion', 'Category', 'kcal', 'Protein g', 'Carbs g', 'Fat g', 'Water oz'];
const LOG_HEADERS = ['Date', 'Time', 'Meal', 'Food', 'Qty', 'kcal', 'Protein g', 'Carbs g', 'Fat g', 'Water oz'];
const MEAL_CODES = { Breakfast: 'B', Lunch: 'L', Snack: 'S', Dinner: 'D' };

// [Food, Portion, Category, kcal, protein, carbs, fat, water oz]
const FOOD_SEED = [
  ['Salmon, egg, spinach & cheese wrap', '1 wrap', 'Meals', 380, 26, 23, 20, 0],
  ['Smoothie (milk, banana, PB, oats, yogurt)', '1 full blender', 'Meals', 830, 40, 85, 39, 12],
  ['Eggs + tortilla + cheese', '3 eggs, 1 tortilla, 1 oz cheese', 'Meals', 460, 30, 23, 27, 0],
  ['Oatmeal with milk & banana', '1 bowl', 'Meals', 405, 14, 66, 11, 8],
  ['Home plate: chicken, rice & veg', '1 plate', 'Meals', 760, 58, 77, 20, 0],
  ['Home plate: salmon, potatoes & veg', '1 plate', 'Meals', 700, 45, 62, 28, 0],
  ['Home plate: lentils / Mediterranean', '1 plate', 'Meals', 720, 33, 110, 16, 0],
  ['Small meal (estimate)', '1', 'Meals', 400, 20, 40, 15, 0],
  ['Medium meal (estimate)', '1', 'Meals', 600, 30, 60, 22, 0],
  ['Large meal (estimate)', '1', 'Meals', 900, 45, 90, 35, 0],
  ['Egg, large', '1 egg', 'Protein', 72, 6, 0, 5, 0],
  ['Greek yogurt, plain whole-milk', '3/4 cup', 'Protein', 160, 16, 6, 8, 0],
  ['Chicken breast, cooked', '4 oz (1 palm)', 'Protein', 185, 35, 0, 4, 0],
  ['Salmon, cooked', '4 oz (1 palm)', 'Protein', 235, 25, 0, 14, 0],
  ['Cheddar cheese', '1 oz slice', 'Protein', 115, 7, 0, 9, 0],
  ['Lentils, cooked', '1 cup', 'Protein', 230, 18, 40, 1, 0],
  ['Tuna or salmon pouch', '1 pouch', 'Protein', 80, 16, 0, 1, 0],
  ['String cheese', '1 stick', 'Protein', 80, 7, 1, 6, 0],
  ['Rice, cooked', '1 cup (1 fist)', 'Carbs', 205, 4, 45, 0, 0],
  ['Potato, baked', '1 medium', 'Carbs', 160, 4, 37, 0, 0],
  ['Whole-wheat tortilla', '1 large', 'Carbs', 130, 4, 22, 4, 0],
  ['Oats, dry', '1/2 cup', 'Carbs', 150, 5, 27, 3, 0],
  ['Whole-wheat bread', '1 slice', 'Carbs', 80, 4, 14, 1, 0],
  ['Banana', '1 medium', 'Carbs', 105, 1, 27, 0, 0],
  ['Apple', '1 medium', 'Carbs', 95, 0, 25, 0, 0],
  ['Mixed vegetables', '1 cup', 'Carbs', 60, 3, 12, 0, 0],
  ['Spinach, raw', '1 cup', 'Carbs', 7, 1, 1, 0, 0],
  ['Mixed nuts', '1 oz handful', 'Snacks', 170, 5, 6, 15, 0],
  ['Peanut butter', '2 tbsp', 'Snacks', 190, 7, 7, 16, 0],
  ['PB + banana tortilla roll-up', '1 roll-up', 'Snacks', 425, 12, 56, 20, 0],
  ['Trail mix', '1/4 cup', 'Snacks', 175, 5, 16, 11, 0],
  ['Olive oil (cooking)', '1 tbsp', 'Snacks', 120, 0, 0, 14, 0],
  ['Water', '8 oz glass', 'Drinks', 0, 0, 0, 0, 8],
  ['Water bottle', '24 oz', 'Drinks', 0, 0, 0, 0, 24],
  ['Whole milk', '1 cup', 'Drinks', 150, 8, 12, 8, 8],
  ['Coffee, black', '1 cup', 'Drinks', 2, 0, 0, 0, 8],
  ['Coffee with milk & sugar', '1 cup', 'Drinks', 60, 1, 9, 2, 8],
  ['Orange juice', '1 cup', 'Drinks', 110, 2, 26, 0, 8],
  ['Soda', '12 oz can', 'Drinks', 140, 0, 39, 0, 12],
];

/** ONE-TIME (safe to re-run): create the Foods + Food Log tabs and the total columns. */
function setupFood() {
  const ss = ss_();
  let foods = ss.getSheetByName('Foods');
  if (!foods) {
    foods = ss.insertSheet('Foods');
    foods.getRange(1, 1, 1, FOOD_HEADERS.length).setValues([FOOD_HEADERS]).setFontWeight('bold');
    foods.getRange(2, 1, FOOD_SEED.length, FOOD_HEADERS.length).setValues(FOOD_SEED);
    foods.setFrozenRows(1); foods.setColumnWidth(1, 300); foods.setColumnWidth(2, 200);
  }
  let log = ss.getSheetByName('Food Log');
  if (!log) {
    log = ss.insertSheet('Food Log');
    log.getRange(1, 1, 1, LOG_HEADERS.length).setValues([LOG_HEADERS]).setFontWeight('bold');
    log.setFrozenRows(1); log.setColumnWidth(4, 300);
    log.getRange('A2:A').setNumberFormat('ddd mmm d');
  }
  const daily = ss.getSheetByName('Daily Log');
  const n = daily.getLastRow() - 1;
  daily.getRange(1, 13, 1, 3).setValues([['Calories (logged)', 'Protein g (logged)', 'Water oz (logged)']]).setFontWeight('bold');
  const f = [];
  for (let r = 2; r <= n + 1; r++) {
    f.push([`=SUMIFS('Food Log'!F:F,'Food Log'!A:A,A${r})`, `=SUMIFS('Food Log'!G:G,'Food Log'!A:A,A${r})`, `=SUMIFS('Food Log'!J:J,'Food Log'!A:A,A${r})`]);
  }
  daily.getRange(2, 13, n, 3).setFormulas(f).setNumberFormat('0');
  const wk = ss.getSheetByName('Weekly Summary');
  const wn = wk.getLastRow() - 1;
  wk.getRange(1, 12).setValue('Avg kcal (logged days)').setFontWeight('bold');
  const wf = [];
  for (let r = 2; r <= wn + 1; r++) wf.push([`=IFERROR(AVERAGEIFS('Daily Log'!M:M,'Daily Log'!K:K,A${r},'Daily Log'!M:M,">0"),"")`]);
  wk.getRange(2, 12, wn, 1).setFormulas(wf).setNumberFormat('0');
  console.log('Foods: ' + (foods.getLastRow() - 1) + ' items | Food Log ready | totals added');
}

/** Food data for one day: library, entries (with sheet row for deletion) and totals. */
function getFoodData_(ss, dateKey, tz) {
  const foods = ss.getSheetByName('Foods'), log = ss.getSheetByName('Food Log');
  if (!foods || !log) return null;
  const library = foods.getLastRow() < 2 ? [] : foods.getRange(2, 1, foods.getLastRow() - 1, 8).getValues()
    .filter(r => r[0] !== '')
    .map(r => ({ name: String(r[0]), portion: String(r[1]), cat: String(r[2]), kcal: num_(r[3]) || 0, p: num_(r[4]) || 0, c: num_(r[5]) || 0, f: num_(r[6]) || 0, w: num_(r[7]) || 0 }));
  const entries = [];
  if (log.getLastRow() >= 2) {
    log.getRange(2, 1, log.getLastRow() - 1, 10).getValues().forEach((r, i) => {
      if (r[0] instanceof Date && key_(r[0], tz) === dateKey) {
        entries.push({ row: i + 2, time: String(r[1]), meal: String(r[2]), name: String(r[3]), qty: num_(r[4]) || 1,
          kcal: num_(r[5]) || 0, p: num_(r[6]) || 0, c: num_(r[7]) || 0, f: num_(r[8]) || 0, w: num_(r[9]) || 0 });
      }
    });
  }
  const sum = k => Math.round(entries.reduce((a, e) => a + e[k], 0));
  return { library, entries, totals: { kcal: sum('kcal'), p: sum('p'), c: sum('c'), f: sum('f'), w: sum('w') },
    targets: { protein: CONFIG.PROTEIN_TARGET || 150, water: CONFIG.WATER_OZ_TARGET || 100 } };
}

/**
 * Log one food/drink. o = { date, meal, name, qty, kcal, p, c, f, w, portion?, cat?, saveToLibrary? }
 * kcal/p/c/f/w are PER PORTION; qty multiplies them.
 */
function addFood(o) {
  if (!o || !o.name) throw new Error('Pick a food or type a name.');
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone();
  const qty = Number(o.qty) || 1;
  const n = k => Math.round((Number(o[k]) || 0) * qty * 10) / 10;
  const date = Utilities.parseDate(o.date, tz, 'yyyy-MM-dd');
  const time = Utilities.formatDate(new Date(), tz, 'h:mm a');
  ss.getSheetByName('Food Log').appendRow([date, time, o.meal || 'Snack', o.name, qty, n('kcal'), n('p'), n('c'), n('f'), n('w')]);
  if (o.saveToLibrary) {
    ss.getSheetByName('Foods').appendRow([o.name, o.portion || '1 serving', o.cat || 'Meals',
      Number(o.kcal) || 0, Number(o.p) || 0, Number(o.c) || 0, Number(o.f) || 0, Number(o.w) || 0]);
  }
  SpreadsheetApp.flush();
  autoMarkDay_(ss, o.date, tz);
  return getAppData(o.date);
}

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

/** After logging food: tick protein / water / meals on the Daily Log when targets are reached (never un-ticks). */
function autoMarkDay_(ss, dateKey, tz) {
  const fd = getFoodData_(ss, dateKey, tz);
  const daily = ss.getSheetByName('Daily Log');
  const col = daily.getRange(2, 1, daily.getLastRow() - 1, 1).getValues();
  const i = col.findIndex(r => r[0] instanceof Date && key_(r[0], tz) === dateKey);
  if (i < 0) return;
  const row = i + 2;
  if (fd.totals.p >= fd.targets.protein * 0.95) daily.getRange(row, 5).setValue('Y');
  if (fd.totals.w >= fd.targets.water) daily.getRange(row, 7).setValue('Y');
  const have = new Set(String(daily.getRange(row, 12).getValue() || '').split(''));
  fd.entries.forEach(e => { const c = MEAL_CODES[e.meal]; if (c && !(e.kcal === 0 && e.meal === 'Snack')) have.add(c); });
  const codes = ['B', 'L', 'S', 'D'].filter(c => have.has(c)).join('');
  daily.getRange(row, 12).setValue(codes);
  daily.getRange(row, 6).setValue(codes.length);
}

/** After a delete: if no food is left for that meal, un-tick it on the Daily Log checklist. */
function untickMealIfEmpty_(ss, dateKey, tz, meal) {
  const code = MEAL_CODES[meal];
  if (!code) return;
  const fd = getFoodData_(ss, dateKey, tz);
  if (fd.entries.some(e => e.meal === meal && !(e.kcal === 0 && e.meal === 'Snack'))) return;
  const daily = ss.getSheetByName('Daily Log');
  const col = daily.getRange(2, 1, daily.getLastRow() - 1, 1).getValues();
  const i = col.findIndex(r => r[0] instanceof Date && key_(r[0], tz) === dateKey);
  if (i < 0) return;
  const row = i + 2;
  const codes = String(daily.getRange(row, 12).getValue() || '').replace(code, '');
  daily.getRange(row, 12).setValue(codes);
  daily.getRange(row, 6).setValue(codes.length || '');
}
