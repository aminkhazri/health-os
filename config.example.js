/**
 * Health OS — personal configuration TEMPLATE.
 *
 * Copy this file to src/config.js and fill in your own values.
 * src/config.js is git-ignored (it holds your Sheet ID and schedule) but IS pushed
 * to Apps Script by clasp, so the live project gets it.
 */
const CONFIG = {
  NAME: 'Alex',               // used in the app greeting
  TZ: 'America/New_York',
  APP_URL: '',   // web app link, shown in the daily checklist
  CALENDAR_NAME: 'Health & Fitness',
  TASKLIST_NAME: 'Daily Health Checklist',
  SHEET_ID: 'YOUR_TRACKER_SHEET_ID',            // from the Sheet URL: /spreadsheets/d/<ID>/edit
  SERIES_START: new Date(2026, 0, 5),          // first day the recurring reminders begin (month is 0-based)
  WEEKLY_WORKOUT_TARGET: 3,
  PROTEIN_TARGET: 150,       // g/day — daily bar + auto-tick at 95%
  WATER_OZ_TARGET: 125,      // oz/day (~3.7 L) from drinks — active adult male; daily gauge + auto-tick
  CAFFEINE_LIMIT_MG: 400,
  STEP_GOAL: 8000,           // steps/day for the 👟 gauge (from the iPhone via Apple Health)
  INBOX_URL: '',             // public URL of the separate "Health OS Inbox" project (see inbox/)    // mg/day — commonly cited limit for healthy adults; gauge turns red past it

  // ISO weekdays: 1=Mon … 7=Sun — drive the daily checklist
  DAYS: {
    work: [1, 2, 3, 4, 5],     // main job days
    shift: [],                 // second-job days (shift tasks stop once the tracker phase says "Phase 2")
    workout: [2, 6],           // training days
    prep: [7, 1, 2, 3, 4],     // evenings to prep the next day's lunch
  },
  WORKDAY_LUNCH: 'Packed lunch.',
  WATER_GOAL: 'Water ~125 oz (3.7 L)',
  WINDDOWN: 'Wind-down → lights out',

  // Optional one-off calendar reminder (set to null to skip)
  TRANSITION_EVENT: {
    title: '🔁 Routine transition check',
    date: new Date(2026, 2, 1, 9, 0),
    description: 'Follow the transition procedure doc. Move this event if your date changes.',
  },
};

const D = CalendarApp.Weekday;
const WEEKDAYS = [D.MONDAY, D.TUESDAY, D.WEDNESDAY, D.THURSDAY, D.FRIDAY];
const WEEKEND = [D.SATURDAY, D.SUNDAY];
const ALLDAYS = WEEKDAYS.concat(WEEKEND);

// Recurring reminders: [title, days, hour, minute, durationMin, popupMinutesBefore (null = silent), description]
const EVENTS = [
  ['💧 Water + breakfast (weigh in first)', ALLDAYS, 7, 0, 15, 0, 'Weigh in, log the tracker, then breakfast.'],
  ['🥜 Snack + water + stretch', WEEKDAYS, 10, 30, 15, 0, 'Protein snack, refill water, 2 min of movement.'],
  ['🌯 Lunch', ALLDAYS, 12, 30, 30, 0, 'Plate template: palm of protein, fist of carbs, fist of veg, thumb of fat.'],
  ['🥜 Snack + water + stretch', WEEKDAYS, 15, 0, 15, 0, 'Protein snack + water.'],
  ['🍽 Dinner', ALLDAYS, 18, 0, 30, null, 'Generous protein portion.'],
  ['🏋️ Workout (alternate A / B)', [D.TUESDAY, D.SATURDAY], 17, 30, 50, 15, 'Log sets in the app.'],
  ['🌙 Wind-down', ALLDAYS, 22, 0, 30, 0, 'Screens down.'],
  ['📊 Weekly review (10 min)', [D.SUNDAY], 18, 30, 10, 0, 'Open the weekly email / Progress tab.'],
];
