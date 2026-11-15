/**
 * Health OS — automation engine (Google Apps Script)
 *
 * Runs on Google's servers (no laptop needed). Three jobs:
 *   1. setup()           — ONE TIME: creates the calendar with recurring reminders,
 *                           the daily task list, and installs the scheduled triggers.
 *   2. resetDailyTasks() — DAILY ~3 AM: clears yesterday's checklist and adds today's
 *                           tasks. Needed because the Tasks API has no "repeat" option.
 *   3. weeklyReview()    — SUNDAY ~6 PM: emails last week's numbers from the tracker
 *                           Sheet, plus the 2-week calorie check.
 *
 * Personal settings (Sheet ID, schedule, dates) live in config.js — see config.example.js.
 * No passwords or tokens are stored in code: Google handles auth via the OAuth consent screen.
 */

/** ONE-TIME SETUP. Idempotent: safe to re-run, skips anything that already exists. */
function setup() {
  const cal = getOrCreateCalendar_();
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('EVENTS_CREATED')) {
    EVENTS.forEach(([title, days, hh, mm, dur, popup, desc]) => {
      const start = firstMatchingDay_(CONFIG.SERIES_START, days);
      start.setHours(hh, mm, 0, 0);
      const end = new Date(start.getTime() + dur * 60000);
      const rec = CalendarApp.newRecurrence().addWeeklyRule().onlyOnWeekdays(days);
      const series = cal.createEventSeries(title, start, end, rec, { description: desc });
      series.removeAllReminders();
      if (popup !== null) series.addPopupReminder(popup);
    });
    const t = CONFIG.TRANSITION_EVENT;
    if (t) {
      const ev = cal.createEvent(t.title, t.date, new Date(t.date.getTime() + 30 * 60000), { description: t.description });
      ev.removeAllReminders(); ev.addPopupReminder(0);
    }
    props.setProperty('EVENTS_CREATED', 'yes');
  }
  getOrCreateTaskList_();
  installTriggers_();
  resetDailyTasks();
  verify();
}

/** Prints a status report so the setup can be checked from the execution log. */
function verify() {
  const cal = CalendarApp.getCalendarsByName(CONFIG.CALENDAR_NAME)[0];
  const now = new Date();
  const week = new Date(now.getTime() + 7 * 86400000);
  const listId = getOrCreateTaskList_();
  const tasks = Tasks.Tasks.list(listId, { showCompleted: true, showHidden: true }).items || [];
  const triggers = ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction());
  console.log('Calendar: ' + (cal ? 'OK' : 'MISSING') + ' | events next 7 days: ' + (cal ? cal.getEvents(now, week).length : 0));
  console.log('Task list: OK | tasks today: ' + tasks.length);
  console.log('Triggers: ' + triggers.join(', '));
}

/** DAILY: rebuild today's checklist. */
function resetDailyTasks() {
  const listId = getOrCreateTaskList_();
  const old = Tasks.Tasks.list(listId, { showCompleted: true, showHidden: true, maxResults: 100 }).items || [];
  old.forEach(t => Tasks.Tasks.remove(listId, t.id));

  const dow = Number(Utilities.formatDate(new Date(), CONFIG.TZ, 'u')); // ISO: 1=Mon … 7=Sun
  // Phase switch: when 'Current phase' on the tracker's Start Here tab contains "Phase 2", shift tasks stop.
  const phase = String(SpreadsheetApp.openById(CONFIG.SHEET_ID).getSheetByName('Start Here').getRange('B14').getValue());
  const items = buildTaskItems_(dow, !phase.includes('Phase 2'));

  const due = Utilities.formatDate(new Date(), CONFIG.TZ, "yyyy-MM-dd'T'00:00:00.000'Z'");
  // Insert in reverse: each new task goes to the top of the list.
  items.slice().reverse().forEach(([title, notes]) => Tasks.Tasks.insert({ title, notes, due }, listId));
}

/**
 * Pure function (no Google services) so it can be unit-tested in Node.
 * @param {number} dow ISO weekday, 1=Mon … 7=Sun
 * @param {boolean} shiftPhaseActive true while the second (physical) job is still part of the routine
 * @return {Array<[string, string]>} [title, notes] in display order
 */
function buildTaskItems_(dow, shiftPhaseActive) {
  const d = CONFIG.DAYS;
  const isWork = d.work.includes(dow);
  const shiftDay = shiftPhaseActive && d.shift.includes(dow);
  const items = [
    ['Weigh in + log tracker row (1 min)', 'Morning, before food.'],
    ['Breakfast', isWork ? 'Before your shift starts.' : ''],
    ['Lunch', isWork ? CONFIG.WORKDAY_LUNCH : 'Plate template.'],
    ['2 protein snacks', 'Greek yogurt, eggs, cheese + tortilla, nuts, PB, milk.'],
    [CONFIG.WATER_GOAL, shiftDay ? 'Extra bottle for the shift.' : ''],
    ['Dinner', ''],
    ['5-min mobility', 'Hips, shoulders, upper back.'],
  ];
  if (d.workout.includes(dow)) items.push(['Workout (A/B) + log sets', '40–50 min. See Workout Plan.']);
  if (shiftDay) items.push(['Pack shift snack + water', '']);
  if (d.prep.includes(dow)) items.push(["Prep tomorrow's lunch", '']);
  items.push([CONFIG.WINDDOWN, '']);
  return items;
}

/** WEEKLY (Sunday evening): email last week's summary from the tracker. */
function weeklyReview() {
  const sh = SpreadsheetApp.openById(CONFIG.SHEET_ID).getSheetByName('Weekly Summary');
  const rows = sh.getRange(2, 1, sh.getLastRow() - 1, 12).getValues();
  const lastWeek = new Date(); lastWeek.setHours(0, 0, 0, 0);
  lastWeek.setDate(lastWeek.getDate() - lastWeek.getDay() - 7); // previous Sunday
  const r = rows.find(x => x[0] instanceof Date && x[0].toDateString() === lastWeek.toDateString());
  if (!r) return;
  const [wk, avg, chg, toGoal, workouts, sleep, protein, trend, rate2, calCheck, goal, kcal] = r;
  const fmt = v => (v === '' || v === null) ? '—' : (typeof v === 'number' ? v.toFixed(1) : v);
  const lines = [
    'Week of ' + Utilities.formatDate(wk, CONFIG.TZ, 'MMM d'),
    '',
    'Average weight: ' + fmt(avg) + ' lb  (change: ' + fmt(chg) + ', trend: ' + fmt(trend) + ')',
    'To goal (' + goal + '): ' + fmt(toGoal) + ' lb',
    'Workouts: ' + workouts + ' of ' + CONFIG.WEEKLY_WORKOUT_TARGET,
    'Average sleep: ' + fmt(sleep) + ' h',
    'Protein days: ' + protein + ' of 7',
    'Avg calories (days with food logged): ' + (kcal === '' ? '—' : Math.round(kcal)),
    '',
    calCheck ? '2-WEEK CALORIE CHECK: ' + calCheck + ' (avg ' + fmt(rate2) + ' lb/wk). If you change it, log it on the Start Here tab.'
             : 'Calorie check: next week.',
    avg === '' ? "\nNo weigh-ins logged last week — that's fine, just start again tomorrow morning." : '',
    '',
    'Tracker: https://docs.google.com/spreadsheets/d/' + CONFIG.SHEET_ID,
  ];
  MailApp.sendEmail(Session.getEffectiveUser().getEmail(), '📊 Weekly health review', lines.join('\n'));
}

// ---------- helpers ----------
function getOrCreateCalendar_() {
  const found = CalendarApp.getCalendarsByName(CONFIG.CALENDAR_NAME);
  if (found.length) return found[0];
  return CalendarApp.createCalendar(CONFIG.CALENDAR_NAME, { timeZone: CONFIG.TZ, color: CalendarApp.Color.GREEN });
}

function getOrCreateTaskList_() {
  const lists = Tasks.Tasklists.list().items || [];
  const hit = lists.find(l => l.title === CONFIG.TASKLIST_NAME);
  return hit ? hit.id : Tasks.Tasklists.insert({ title: CONFIG.TASKLIST_NAME }).id;
}

function installTriggers_() {
  ScriptApp.getProjectTriggers()
    .filter(t => ['resetDailyTasks', 'weeklyReview'].includes(t.getHandlerFunction()))
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('resetDailyTasks').timeBased().everyDays(1).atHour(3).inTimezone(CONFIG.TZ).create();
  ScriptApp.newTrigger('weeklyReview').timeBased().onWeekDay(ScriptApp.WeekDay.SUNDAY).atHour(18).inTimezone(CONFIG.TZ).create();
}

/** First date on/after `from` whose weekday is in `days` (avoids a stray first event in a series). */
function firstMatchingDay_(from, days) {
  const names = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];
  const wanted = days.map(d => names.indexOf(String(d)));
  const d = new Date(from);
  while (!wanted.includes(d.getDay())) d.setDate(d.getDate() + 1);
  return d;
}

if (typeof module !== 'undefined') module.exports = { buildTaskItems_, firstMatchingDay_ }; // Node tests only
