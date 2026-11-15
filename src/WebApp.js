/**
 * Health OS — mobile web app (served by this same Apps Script project).
 * Deployed as a web app: "Execute as: Me", "Who has access: Only myself".
 * The page calls these functions with google.script.run; all data lives in the tracker Sheet.
 */

const WORKOUTS = {
  A: ['Goblet squat (DB)', 'Dumbbell bench press', 'Lat pulldown (Hoist)', 'Dumbbell Romanian deadlift', 'Seated row (Hoist)', 'Plank (sec)'],
  B: ['DB reverse lunge / split squat', 'Hoist chest press / incline DB press', 'One-arm DB row', 'Leg curl (Hoist)', 'Seated DB shoulder press', 'DB curl + triceps pushdown'],
};

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Health OS')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

function ss_() { return SpreadsheetApp.openById(CONFIG.SHEET_ID); }
function key_(d, tz) { return Utilities.formatDate(d, tz, 'yyyy-MM-dd'); }
function num_(v) { return (v === '' || v === null || isNaN(v)) ? null : Number(v); }

/** Everything the page needs in one round trip. dateKey = 'yyyy-MM-dd' (defaults to today). */
function getAppData(dateKey) {
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone();
  const today = key_(new Date(), tz);
  dateKey = dateKey || today;

  const daily = ss.getSheetByName('Daily Log');
  const dv = daily.getRange(2, 1, daily.getLastRow() - 1, 15).getValues();
  let entry = null;
  const series = [];
  dv.forEach(r => {
    if (!(r[0] instanceof Date)) return;
    const k = key_(r[0], tz);
    if (k === dateKey) entry = { date: k, weight: num_(r[1]), sleep: num_(r[2]), energy: num_(r[3]),
      protein: r[4], meals: num_(r[5]), water: r[6], notes: r[7], mealsDetail: String(r[11] || '') };
    if (k <= today && (r[1] !== '' || r[2] !== '' || num_(r[12]) > 0)) series.push({ d: k, w: num_(r[1]), s: num_(r[2]), wa: num_(r[8]), k: num_(r[12]) || null });
  });

  const weekly = ss.getSheetByName('Weekly Summary').getRange(2, 1, 52, 12).getValues()
    .filter(r => r[0] instanceof Date && key_(r[0], tz) <= today)
    .map(r => ({ wk: key_(r[0], tz), avg: num_(r[1]), chg: num_(r[2]), toGoal: num_(r[3]), workouts: num_(r[4]) || 0,
      sleep: num_(r[5]), protein: num_(r[6]) || 0, trend: String(r[7] || ''), rate2: num_(r[8]), cal: String(r[9] || ''), kcal: num_(r[11]) }));

  const sh = ss.getSheetByName('Start Here');
  const targets = { start: num_(sh.getRange('B5').getValue()), goal: num_(sh.getRange('B6').getValue()),
    calories: num_(sh.getRange('B7').getValue()), low: num_(sh.getRange('B12').getValue()),
    high: num_(sh.getRange('B13').getValue()), phase: String(sh.getRange('B14').getValue()) };

  const wl = ss.getSheetByName('Workout Log');
  const wv = wl.getRange(2, 1, Math.max(wl.getLastRow() - 1, 1), 7).getValues().filter(r => r[0] instanceof Date && r[2] !== '');
  const last = {};
  let lastLetter = null, lastDate = null;
  wv.forEach(r => {
    last[r[2]] = { date: key_(r[0], tz), sets: num_(r[3]), reps: String(r[4]), weight: num_(r[5]) };
    if (r[1]) { lastLetter = String(r[1]); lastDate = key_(r[0], tz); }
  });

  const cal = weekly.filter(w => w.cal).pop() || null;
  const food = getFoodData_(ss, dateKey, tz);
  return { today, dateKey, entry, series: series.slice(-120), weekly, targets, last,
    next: lastLetter === 'A' ? 'B' : 'A', lastLetter, lastWorkoutDate: lastDate, workouts: WORKOUTS, calCheck: cal, food, name: CONFIG.NAME || '' };
}

/** Write one Daily Log row (finds the row by date). */
function saveDaily(o) {
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone(), sh = ss.getSheetByName('Daily Log');
  const col = sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues();
  const i = col.findIndex(r => r[0] instanceof Date && key_(r[0], tz) === o.date);
  if (i < 0) throw new Error('That date is not in the Daily Log: ' + o.date);
  const row = i + 2;
  const v = x => (x === null || x === undefined) ? '' : x;
  sh.getRange(row, 2, 1, 7).setValues([[v(o.weight), v(o.sleep), v(o.energy), v(o.protein), v(o.meals), v(o.water), v(o.notes)]]);
  if (sh.getRange(1, 12).getValue() === '') sh.getRange(1, 12).setValue('Meals detail (app)');
  sh.getRange(row, 12).setValue(o.mealsDetail || '');
  SpreadsheetApp.flush();
  return getAppData(o.date);
}

/** Append one workout session (one row per exercise) to the Workout Log. */
function saveWorkout(o) {
  if (!o.items || !o.items.length) throw new Error('No exercises marked done.');
  const ss = ss_(), sh = ss.getSheetByName('Workout Log');
  const a = sh.getRange(2, 1, sh.getMaxRows() - 1, 1).getValues();
  let r = a.findIndex(x => x[0] === '') + 2;
  if (r < 2) r = sh.getMaxRows() + 1;
  const needEnd = r + o.items.length - 1;
  if (needEnd > sh.getMaxRows()) sh.insertRowsAfter(sh.getMaxRows(), needEnd - sh.getMaxRows() + 50);
  // Build the date in the Sheet's own time zone so it never shifts to the previous day.
  const date = Utilities.parseDate(o.date, ss.getSpreadsheetTimeZone(), 'yyyy-MM-dd');
  sh.getRange(r, 1, o.items.length, 7).setValues(o.items.map(it =>
    [date, o.letter, it.ex, num_(it.sets), String(it.reps || ''), num_(it.weight), it.notes || '']));
  sh.getRange(r, 1, o.items.length, 1).setNumberFormat('ddd mmm d');
  sh.getRange(r, 8, o.items.length, 1).setFormulaR1C1('=IF(R[0]C1="","",IF(R[0]C1<>R[-1]C1,1,0))');
  SpreadsheetApp.flush();
  return getAppData(o.date);
}

/** One-time: make Weekly Summary workout counts use whole columns so the log can grow past row 401. */
function widenWorkoutRanges() {
  const sh = ss_().getSheetByName('Weekly Summary');
  const f = [];
  for (let r = 2; r <= 53; r++) f.push([`=SUMIFS('Workout Log'!H:H,'Workout Log'!A:A,">="&A${r},'Workout Log'!A:A,"<"&A${r}+7)`]);
  sh.getRange(2, 5, f.length, 1).setFormulas(f);
}

/** One-time maintenance: align the Sheet's time zone with CONFIG.TZ and remove rows whose note is TEST. */
function maintenance() {
  const ss = ss_();
  ss.setSpreadsheetTimeZone(CONFIG.TZ);
  const dl = ss.getSheetByName('Daily Log');
  const dv = dl.getRange(2, 8, dl.getLastRow() - 1, 1).getValues();
  dv.forEach((r, i) => { if (r[0] === 'TEST') { dl.getRange(i + 2, 2, 1, 7).clearContent(); dl.getRange(i + 2, 12).clearContent(); } });
  const wl = ss.getSheetByName('Workout Log');
  const wv = wl.getRange(2, 7, wl.getLastRow() - 1, 1).getValues();
  wv.forEach((r, i) => { if (r[0] === 'TEST') wl.getRange(i + 2, 1, 1, 7).clearContent(); });
  console.log('Sheet time zone: ' + ss.getSpreadsheetTimeZone());
}
