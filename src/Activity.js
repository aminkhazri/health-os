/**
 * Health OS — steps and active calories from the iPhone (Apple Health).
 *
 * How the data gets here:
 *   iPhone Shortcut  --POST {key, steps, active_kcal}-->  "Health OS Inbox" (a separate, tiny Apps Script
 *   project deployed for "Anyone")  -->  writes one row per day into the "Activity" tab of the tracker Sheet.
 *
 * Why a separate project: this dashboard is deployed "Only myself", so a Shortcut can't reach it (it can't
 * sign in to Google). The inbox has to be public, so it does exactly one thing: check the key, write steps.
 *
 * The key: the dashboard creates a random key, shows it to you once, and stores only its SHA-256
 * fingerprint in the hidden "_Sync" tab. The inbox hashes whatever key it receives and compares.
 * A copy of the Sheet therefore never contains a usable key. Lost it? Create a new one (the old one stops working).
 */

const ACTIVITY_SHEET = 'Activity';
const SYNC_SHEET = '_Sync';
const ACTIVITY_HEADERS = ['Date', 'Steps', 'Active kcal', 'Synced at', 'Source'];

/** One-time, safe to re-run: creates the Activity and _Sync tabs and the Weekly Summary "Avg steps" column. */
function setupActivity() {
  const ss = ss_();
  let a = ss.getSheetByName(ACTIVITY_SHEET);
  if (!a) {
    a = ss.insertSheet(ACTIVITY_SHEET);
    a.getRange(1, 1, 1, ACTIVITY_HEADERS.length).setValues([ACTIVITY_HEADERS]).setFontWeight('bold');
    a.setFrozenRows(1);
    a.getRange('A:A').setNumberFormat('ddd mmm d, yyyy');
    a.getRange('B:C').setNumberFormat('#,##0');
    a.getRange('D:D').setNumberFormat('mmm d h:mm am/pm');
    a.setColumnWidths(1, 5, 130);
  }
  let s = ss.getSheetByName(SYNC_SHEET);
  if (!s) {
    s = ss.insertSheet(SYNC_SHEET);
    s.getRange('A1:A2').setValues([['key_sha256'], ['created']]);
    s.getRange('A4').setValue('Only a fingerprint of the iPhone sync key is stored here. Create or replace the key from the Health OS app (Progress tab).');
    s.hideSheet();
  }
  const wk = ss.getSheetByName('Weekly Summary');
  wk.getRange(1, 13).setValue('Avg steps').setFontWeight('bold');
  const n = wk.getLastRow() - 1, f = [];
  for (let r = 2; r <= n + 1; r++) f.push([`=IFERROR(AVERAGEIFS(Activity!B:B,Activity!A:A,">="&A${r},Activity!A:A,"<"&A${r}+7),"")`]);
  wk.getRange(2, 13, n, 1).setFormulas(f).setNumberFormat('#,##0');
  // Weekly average resting heart rate from the Daily Log (column Q, typed in each morning).
  wk.getRange(1, 14).setValue('Avg resting HR').setFontWeight('bold');
  const h = [];
  for (let r = 2; r <= n + 1; r++) h.push([`=IFERROR(AVERAGEIFS('Daily Log'!Q:Q,'Daily Log'!A:A,">="&A${r},'Daily Log'!A:A,"<"&A${r}+7),"")`]);
  wk.getRange(2, 14, n, 1).setFormulas(h).setNumberFormat('0');
  const dl = ss.getSheetByName('Daily Log');
  if (dl.getRange(1, 17).getValue() === '') dl.getRange(1, 17).setValue('Resting HR').setFontWeight('bold');
  return 'Activity ready';
}

/** Steps + active kcal for the page: the chosen day, a 120-day series, and sync status. */
function getActivityData_(ss, dateKey, tz) {
  const a = ss.getSheetByName(ACTIVITY_SHEET), s = ss.getSheetByName(SYNC_SHEET);
  const out = { day: null, series: [], lastSync: null, keySet: !!(s && s.getRange('B1').getValue()),
    stepGoal: CONFIG.STEP_GOAL || 8000, inboxUrl: CONFIG.INBOX_URL || '' };
  if (!a || a.getLastRow() < 2) return out;
  const today = key_(new Date(), tz);
  let last = null;
  a.getRange(2, 1, a.getLastRow() - 1, 4).getValues().forEach(r => {
    if (!(r[0] instanceof Date)) return;
    const k = key_(r[0], tz), row = { d: k, st: num_(r[1]), ak: num_(r[2]) };
    if (k === dateKey) out.day = Object.assign({ synced: r[3] instanceof Date ? r[3].toISOString() : null }, row);
    if (k <= today) out.series.push(row);
    if (r[3] instanceof Date && (!last || r[3] > last)) last = r[3];
  });
  out.series.sort((x, y) => x.d < y.d ? -1 : 1);
  out.series = out.series.slice(-120);
  out.lastSync = last ? last.toISOString() : null;
  return out;
}

/** Creates a new sync key, stores only its fingerprint, and returns the key ONCE so you can copy it. */
function newSyncKey() {
  const ss = ss_();
  if (!ss.getSheetByName(SYNC_SHEET)) setupActivity();
  const key = (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');   // 64 hex chars, ~244 random bits
  ss.getSheetByName(SYNC_SHEET).getRange('B1:B2').setValues([[sha256Hex_(key)], [new Date()]]);
  return { key, url: CONFIG.INBOX_URL || '' };
}

function sha256Hex_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)
    .map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
}
