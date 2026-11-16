/**
 * Health OS — mobile web app (served by this same Apps Script project).
 * Deployed as a web app: "Execute as: Me", "Who has access: Only myself".
 * The page calls these functions with google.script.run; all data lives in the tracker Sheet.
 */

// Phase 1 "Build" (8 weeks): home workouts with dumbbells, bands and a mat. 3 sets, stop 1-2 reps short of failure.
// Each workout ends with two isometric holds (no movement, ~8/10 effort): mostly at long muscle lengths, plus
// the Copenhagen plank, which protects the groin in soccer.
const WORKOUTS = {
  A: ['Goblet squat', 'Dumbbell floor press', 'One-arm dumbbell row', 'Dumbbell Romanian deadlift', 'Dumbbell shoulder press', 'Band pull-apart',
      'Copenhagen plank', 'Side plank'],
  B: ['Bulgarian split squat', 'Single-leg Romanian deadlift', 'Dumbbell hip thrust', 'Heel-raised goblet squat', 'Standing calf raise', 'Dead bug',
      'Split squat bottom hold', 'Single-leg glute bridge hold'],
  C: ['Push-up', 'Band row', 'Incline dumbbell press', 'Dumbbell lateral raise', 'Dumbbell curl', 'Overhead triceps extension',
      'Push-up bottom hold', "Dumbbell farmer's hold"],
};
const WORKOUT_INFO = {
  names: { A: 'Full body', B: 'Legs + core', C: 'Upper body' },
  day: { 4: 'A', 6: 'B', 7: 'C' },                 // ISO weekday -> planned workout (Thu, Sat, Sun)
  targets: {
    'Goblet squat': '3 × 8–12', 'Dumbbell floor press': '3 × 8–12', 'One-arm dumbbell row': '3 × 10–12 each arm',
    'Dumbbell Romanian deadlift': '3 × 10–12', 'Dumbbell shoulder press': '3 × 8–12', 'Band pull-apart': '2 × 15–20',
    'Bulgarian split squat': '3 × 8–10 each leg', 'Single-leg Romanian deadlift': '3 × 8–10 each leg', 'Dumbbell hip thrust': '3 × 10–15',
    'Heel-raised goblet squat': '2 × 12–15', 'Standing calf raise': '3 × 12–20', 'Dead bug': '2 × 8 each side, slow',
    'Push-up': '3 × as many as you can, minus 2', 'Band row': '3 × 12–15', 'Incline dumbbell press': '3 × 8–12',
    'Dumbbell lateral raise': '3 × 12–15', 'Dumbbell curl': '3 × 10–12', 'Overhead triceps extension': '3 × 10–12',
    // Isometric finishers (hold times in seconds)
    'Copenhagen plank': '3 × 15–20 s each side, knee on a couch or chair', 'Side plank': '2 × 30–45 s each side',
    'Split squat bottom hold': '3 × 30 s each leg, back knee just off the floor', 'Single-leg glute bridge hold': '2 × 30 s each leg',
    'Push-up bottom hold': '3 × 20–30 s, chest 2 inches off the floor', "Dumbbell farmer's hold": '3 × 30–45 s, heaviest pair you can grip',
  },
};

// Projects: short add-on sessions for specific goals. They log to the Workout Log like any session but don't count
// toward the 3 main workouts a week, don't change which main workout is next, and don't affect Workout/Recovery on the chart.
const PROJECTS = {
  Neck: {
    icon: '🛡️', name: 'Neck strength', order: 1,
    why: 'A strong neck supports the spine and helps absorb contact and headers in soccer.',
    how: '3 times a week, about 8 minutes: right after Workouts A, B and C. Slow and controlled: never jerk your head. Start with no extra weight. Stop if you feel sharp pain, numbness, tingling or a headache.',
    ex: ['Supine chin tuck', 'Neck isometric hold', 'Prone neck extension', 'Side-lying neck raise', 'Dumbbell shrug'],
    targets: { 'Supine chin tuck': '2 × 10, hold 3 s', 'Neck isometric hold': '2 rounds × 10 s each way (front, back, left, right)',
      'Prone neck extension': '2 × 12, slow', 'Side-lying neck raise': '2 × 12 each side', 'Dumbbell shrug': '3 × 12–15, 1 s squeeze' },
  },
  Calves: {
    icon: '🦵', name: 'Calf size', order: 2,
    why: 'Strong calves that need more size: more weekly sets, a full stretch at the bottom and steady added weight.',
    how: '3 times a week on rest days (Mon, Wed, Fri), about 10 minutes. Every rep: 3 s down, 2 s paused in the deepest stretch, then up and squeeze 1 s. When every set hits the top of the range, add weight. Size also needs the calorie surplus you are already eating.',
    ex: ['Single-leg deficit calf raise', 'Seated dumbbell calf raise', 'Tibialis raise', 'Single-leg calf raise hold'],
    targets: { 'Single-leg deficit calf raise': '3 × 10–15 each leg', 'Seated dumbbell calf raise': '3 × 15–20', 'Tibialis raise': '2 × 15–20',
      'Single-leg calf raise hold': '2 × 30 s each leg, halfway up, holding a dumbbell' },
  },
};

/** Pure: which workout is next. A planned day (Thu/Sat/Sun) wins; otherwise rotate A -> B -> C after the last one logged. */
function nextWorkout_(isoDow, lastLetter) {
  if (WORKOUT_INFO.day[isoDow]) return WORKOUT_INFO.day[isoDow];
  const order = Object.keys(WORKOUTS), i = order.indexOf(lastLetter);
  return order[(i + 1) % order.length];
}


function doGet() {
  return HtmlService.createTemplateFromFile('Index').evaluate()
    .setTitle('Health OS')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

/** Lets Index.html pull in other HTML files: <?!= include('Parser'); ?> */
function include(name) { return HtmlService.createHtmlOutputFromFile(name).getContent(); }

function ss_() { return SpreadsheetApp.openById(CONFIG.SHEET_ID); }
function key_(d, tz) { return Utilities.formatDate(d, tz, 'yyyy-MM-dd'); }
function num_(v) { return (v === '' || v === null || isNaN(v)) ? null : Number(v); }

/** Everything the page needs in one round trip. dateKey = 'yyyy-MM-dd' (defaults to today). */
function getAppData(dateKey) {
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone();
  const today = key_(new Date(), tz);
  dateKey = dateKey || today;

  const daily = ss.getSheetByName('Daily Log');
  const dv = daily.getRange(2, 1, daily.getLastRow() - 1, Math.min(19, daily.getMaxColumns())).getValues();
  let entry = null;
  const series = [];
  dv.forEach(r => {
    if (!(r[0] instanceof Date)) return;
    const k = key_(r[0], tz);
    if (k === dateKey) entry = { date: k, weight: num_(r[1]), sleep: num_(r[2]), energy: num_(r[3]),
      protein: r[4], meals: num_(r[5]), water: r[6], notes: r[7], mealsDetail: String(r[11] || ''), hr: num_(r[16]), mind: num_(r[17]) || 0, stretch: num_(r[18]) || 0 };
    if (k <= today && (r[1] !== '' || r[2] !== '' || num_(r[12]) > 0 || r[16] !== '' || num_(r[17]) > 0 || num_(r[18]) > 0)) series.push({ m: num_(r[17]) || null, f: num_(r[18]) || null, p: num_(r[13]) || null, wo: num_(r[14]) || null, d: k, w: num_(r[1]), s: num_(r[2]), wa: num_(r[8]), k: num_(r[12]) || null, hr: num_(r[16]) });
  });

  const weekly = ss.getSheetByName('Weekly Summary').getRange(2, 1, 52, 12).getValues()
    .filter(r => r[0] instanceof Date && key_(r[0], tz) <= today)
    .map(r => ({ wk: key_(r[0], tz), avg: num_(r[1]), chg: num_(r[2]), toGoal: num_(r[3]), workouts: num_(r[4]) || 0,
      sleep: num_(r[5]), protein: num_(r[6]) || 0, trend: String(r[7] || ''), rate2: num_(r[8]), cal: String(r[9] || ''), kcal: num_(r[11]) }));

  const sh = ss.getSheetByName('Start Here');
  const targets = { start: num_(sh.getRange('B5').getValue()), goal: num_(sh.getRange('B6').getValue()),
    calories: num_(sh.getRange('B7').getValue()), workouts: CONFIG.WEEKLY_WORKOUT_TARGET || 3, mindful: CONFIG.MINDFUL_GOAL_MIN || 10, stretch: CONFIG.STRETCH_GOAL_MIN || 5, low: num_(sh.getRange('B12').getValue()),
    high: num_(sh.getRange('B13').getValue()), phase: String(sh.getRange('B14').getValue()) };

  const wl = ss.getSheetByName('Workout Log');
  const wv = wl.getRange(2, 1, Math.max(wl.getLastRow() - 1, 1), 7).getValues().filter(r => r[0] instanceof Date && r[2] !== '');
  const last = {}, lastSession = {};
  let lastLetter = null, lastDate = null;
  wv.forEach(r => {
    last[r[2]] = { date: key_(r[0], tz), sets: num_(r[3]), reps: String(r[4]), weight: num_(r[5]) };
    const l = String(r[1] || '');
    if (l) lastSession[l] = key_(r[0], tz);
    if (WORKOUTS[l]) { lastLetter = l; lastDate = key_(r[0], tz); }   // projects don't move the main rotation
  });

  const cal = weekly.filter(w => w.cal).pop() || null;
  const food = getFoodData_(ss, dateKey, tz);
  const activity = getActivityData_(ss, dateKey, tz);
  return { today, dateKey, entry, series: series.slice(-120), weekly, targets, last,
    next: nextWorkout_(Number(Utilities.formatDate(new Date(), tz, 'u')), lastLetter), workoutInfo: WORKOUT_INFO, lastLetter, lastWorkoutDate: lastDate, lastSession, workouts: WORKOUTS, projects: PROJECTS, calCheck: cal, food, activity, stretches: STRETCHES, routines: STRETCH_ROUTINES, videos: VIDEOS, tallVideos: TALL_VIDEOS, name: CONFIG.NAME || '' };
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
  // Resting heart rate (bpm), entered by hand from the watch. Ignore anything outside a human range.
  if (sh.getRange(1, 17).getValue() === '') sh.getRange(1, 17).setValue('Resting HR').setFontWeight('bold');
  const hr = num_(o.hr);
  sh.getRange(row, 17).setValue(hr !== null && hr >= 30 && hr <= 220 ? Math.round(hr) : '');
  SpreadsheetApp.flush();
  return getAppData(o.date);
}

/** Add (or with a negative number, remove) mindful minutes for a day. Stored in Daily Log column R. */
function addMindful(dateKey, minutes) { return addMinutes_(dateKey, minutes, 18, 'Mindful min'); }

/** Add (or remove) stretching minutes for a day. Stored in Daily Log column S. */
function addStretch(dateKey, minutes) { return addMinutes_(dateKey, minutes, 19, 'Stretch min'); }

/** Shared by Calm and Flexibility: add minutes to one Daily Log cell. The lock stops two quick taps from overwriting each other. */
function addMinutes_(dateKey, minutes, colNo, header) {
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone(), sh = ss.getSheetByName('Daily Log');
  const col = sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues();
  const i = col.findIndex(r => r[0] instanceof Date && key_(r[0], tz) === dateKey);
  if (i < 0) throw new Error('That date is not in the Daily Log: ' + dateKey);
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    if (sh.getMaxColumns() < colNo) sh.insertColumnsAfter(sh.getMaxColumns(), colNo - sh.getMaxColumns());
    if (sh.getRange(1, colNo).getValue() === '') sh.getRange(1, colNo).setValue(header).setFontWeight('bold');
    const cell = sh.getRange(i + 2, colNo);
    const total = Math.max(0, Math.min(240, (num_(cell.getValue()) || 0) + (num_(minutes) || 0)));
    cell.setValue(total || '');
    SpreadsheetApp.flush();
  } finally { lock.releaseLock(); }
  return getAppData(dateKey);
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
  // Column H counts sessions for the weekly total: 1 on the first row of a main session, 0 for project rows.
  // Comparing the letter too means a main workout logged after a project on the same day still counts.
  if (PROJECTS[o.letter]) sh.getRange(r, 8, o.items.length, 1).setValue(0);
  else sh.getRange(r, 8, o.items.length, 1).setFormulaR1C1('=IF(R[0]C1="","",IF(OR(R[0]C1<>R[-1]C1,R[0]C2<>R[-1]C2),1,0))');
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

if (typeof module !== 'undefined') module.exports = { nextWorkout_, WORKOUTS, WORKOUT_INFO, PROJECTS }; // Node tests only
