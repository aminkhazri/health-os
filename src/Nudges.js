/**
 * Health OS — smart nudges: an alert only when you're behind pace.
 *
 * A time-driven trigger runs checkNudges() every 15 minutes. When a checkpoint time has just passed, it reads
 * today's water (Food Log) and calm minutes (Daily Log). If you're behind the pace for that time, it creates a
 * 5-minute event starting 2 minutes from now on the Health & Fitness calendar, with a popup at start. The Google
 * Calendar app turns that into a phone notification. If you're on pace, nothing is sent.
 *
 * Each checkpoint fires at most once a day (remembered in Script Properties), and yesterday's nudge events are
 * cleaned up automatically so the calendar doesn't fill up.
 */

const NUDGE_TAG = '[health-os-nudge]';

// ISO weekday (Mon=1 … Sun=7) -> checkpoints. at = minutes after midnight; water = oz you should have by then.
// calm = minutes of breathing you should have by then (0 = don't check calm at this checkpoint).
const NUDGE_PLAN = (() => {
  const work = [{ at: 6 * 60 + 45, water: 24, calm: 0 }, { at: 10 * 60, water: 50, calm: 0 },
                { at: 12 * 60 + 45, water: 75, calm: 0 }, { at: 15 * 60 + 30, water: 100, calm: 3 }];
  const off  = [{ at: 10 * 60 + 15, water: 40, calm: 0 }, { at: 16 * 60, water: 90, calm: 3 }];
  const shift = { at: 20 * 60, water: 110, calm: 0 };   // UPS nights (Mon–Fri): one check mid-shift, water only
  return { 7: work, 1: work.concat(shift), 2: work.concat(shift), 3: work.concat(shift), 4: off.concat(shift), 5: off.concat(shift), 6: off };
})();

/** Pure: the checkpoint that just passed (within the last `windowMin` minutes) and hasn't fired today. */
function dueCheckpoint_(plan, isoDow, minutesNow, firedToday, windowMin) {
  return (plan[isoDow] || []).find(c => minutesNow >= c.at && minutesNow < c.at + windowMin && !firedToday.includes(c.at)) || null;
}

/** Pure: what to say, or null if you're on pace. */
function nudgeFor_(cp, waterOz, calmMin) {
  const dry = waterOz < cp.water, tense = cp.calm > 0 && calmMin < cp.calm;
  if (!dry && !tense) return null;
  const gap = Math.round(cp.water - waterOz);
  const sip = gap >= 20 ? 'about a full 24 oz bottle' : gap >= 12 ? 'about half a bottle' : 'a few big sips';
  const parts = [];
  if (dry) parts.push(`💧 Behind on water: ${Math.round(waterOz)} of ${cp.water} oz by now. Drink ${sip}, then tap +24 oz (or +8 oz) in Health OS.`);
  if (tense) parts.push(`🧘 Only ${calmMin} of ${cp.calm} calm minutes so far. Tap "Breathe 1 min" when you get a gap.`);
  const title = dry && tense ? `💧🧘 Catch up: water ${Math.round(waterOz)}/${cp.water} oz + 1 min breathing`
    : dry ? `💧 Catch up on water: ${Math.round(waterOz)}/${cp.water} oz` : '🧘 1 min of breathing';
  return { title, desc: parts.join('<br><br>') };
}

/** Trigger target. Safe to run any time: does nothing unless a checkpoint just passed. */
function checkNudges() {
  const tz = CONFIG.TZ, now = new Date();
  const today = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  const dow = Number(Utilities.formatDate(now, tz, 'u'));
  const mins = Number(Utilities.formatDate(now, tz, 'H')) * 60 + Number(Utilities.formatDate(now, tz, 'm'));
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('NUDGE_CLEANED') !== today) { cleanOldNudges_(); props.setProperty('NUDGE_CLEANED', today); }

  const fired = JSON.parse(props.getProperty('NUDGE_FIRED_' + today) || '[]');
  const cp = dueCheckpoint_(NUDGE_PLAN, dow, mins, fired, 30);   // 30-min window: a 15-min trigger can't miss it
  if (!cp) return 'no checkpoint due';
  fired.push(cp.at);
  props.setProperty('NUDGE_FIRED_' + today, JSON.stringify(fired));
  props.deleteProperty('NUDGE_FIRED_' + Utilities.formatDate(new Date(now.getTime() - 86400000), tz, 'yyyy-MM-dd'));

  const t = todayTotals_(today);
  const n = nudgeFor_(cp, t.water, t.calm);
  if (!n) return 'on pace, no nudge';
  sendNudge_(n.title, n.desc);
  return 'sent: ' + n.title;
}

/** Today's water oz (sum of Food Log column J) and calm minutes (Daily Log column R). */
function todayTotals_(today) {
  const ss = ss_(), tz = ss.getSpreadsheetTimeZone();
  let water = 0, calm = 0;
  const log = ss.getSheetByName('Food Log');
  if (log && log.getLastRow() > 1) log.getRange(2, 1, log.getLastRow() - 1, 10).getValues()
    .forEach(r => { if (r[0] instanceof Date && key_(r[0], tz) === today) water += Number(r[9]) || 0; });
  const dl = ss.getSheetByName('Daily Log');
  const row = dl.getRange(2, 1, dl.getLastRow() - 1, 18).getValues().find(r => r[0] instanceof Date && key_(r[0], tz) === today);
  if (row) calm = Number(row[17]) || 0;
  return { water, calm };
}

function sendNudge_(title, desc) {
  const cal = CalendarApp.getCalendarsByName(CONFIG.CALENDAR_NAME)[0];
  const start = new Date(Date.now() + 2 * 60000), end = new Date(start.getTime() + 5 * 60000);
  const ev = cal.createEvent(title, start, end, { description: desc + '<br><br>' +
    (CONFIG.APP_URL ? `👉 <a href="${CONFIG.APP_URL}">Open Health OS</a><br><br>` : '') + NUDGE_TAG });
  ev.removeAllReminders(); ev.addPopupReminder(0); ev.setTransparency(CalendarApp.EventTransparency.TRANSPARENT);
  return ev.getId();
}

/** Deletes past one-off nudge events (only ones carrying the tag, never your other events). */
function cleanOldNudges_() {
  const cal = CalendarApp.getCalendarsByName(CONFIG.CALENDAR_NAME)[0];
  const startToday = new Date(); startToday.setHours(0, 0, 0, 0);
  cal.getEvents(new Date(startToday.getTime() - 14 * 86400000), startToday)
    .filter(e => !e.isRecurringEvent() && String(e.getDescription()).includes(NUDGE_TAG))
    .forEach(e => e.deleteEvent());
}

/** One-time: install the 15-minute trigger (safe to re-run; never duplicates). */
function installNudges() {
  const has = ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === 'checkNudges');
  if (!has) ScriptApp.newTrigger('checkNudges').timeBased().everyMinutes(15).create();
  return has ? 'already installed' : 'installed';
}

/** Manual check from the editor: sends one clearly-labelled test nudge so you can see it arrive on the phone. */
function testNudge() {
  const t = todayTotals_(Utilities.formatDate(new Date(), CONFIG.TZ, 'yyyy-MM-dd'));
  sendNudge_('✅ Test: smart nudges are working', `Right now: ${Math.round(t.water)} oz water, ${t.calm} calm minutes. This is a one-time test.`);
  return t;
}

if (typeof module !== 'undefined') module.exports = { dueCheckpoint_, nudgeFor_, NUDGE_PLAN }; // Node tests only
