/**
 * Health OS Inbox — the only public piece of Health OS.
 *
 * Deployed as a web app: Execute as "Me", Who has access "Anyone". An iPhone Shortcut POSTs JSON:
 *   { "key": "<sync key>", "steps": 8432, "active_kcal": 512, "date": "2026-11-15" }   (date optional = today)
 * The inbox checks the key against the SHA-256 fingerprint in the tracker's hidden _Sync tab, then
 * upserts one row per day in the Activity tab. It can't read anything back out, by design.
 *
 * Script Properties (Project Settings → Script properties): SHEET_ID = the tracker Sheet's ID.
 * Nothing secret lives in this file or in the repo.
 */

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('SHEET_ID'));
    const sync = ss.getSheetByName('_Sync');
    const stored = sync ? String(sync.getRange('B1').getValue()) : '';
    if (!stored || typeof body.key !== 'string' || !sameText_(sha256Hex_(body.key.trim()), stored)) return reply_({ ok: false, error: 'Key not accepted' });

    const tz = ss.getSpreadsheetTimeZone();
    const day = cleanDay_(normalizeFields_(body), Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd'));
    if (!day) return reply_({ ok: false, error: 'Expected steps and/or active_kcal as numbers',
      received: Object.keys(body).filter(k => k !== 'key').map(k => k + '=' + JSON.stringify(body[k]).slice(0, 40)) });

    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try { upsert_(ss.getSheetByName('Activity'), day, tz); } finally { lock.releaseLock(); }
    return reply_({ ok: true, date: day.date, steps: day.steps, active_kcal: day.kcal });
  } catch (err) {
    console.error(err);                       // details stay in the private execution log
    return reply_({ ok: false, error: 'Could not save' });
  }
}

/** Opening the URL in a browser just confirms it's alive; no data is ever returned. */
function doGet() { return reply_({ ok: true, service: 'Health OS inbox' }); }

/** Pure: forgiving field names from the Shortcut ("Steps", "active kcal", "Active Energy" ...). */
function normalizeFields_(b) {
  const out = {};
  Object.keys(b || {}).forEach(k => {
    const n = String(k).toLowerCase().replace(/[^a-z]/g, '');
    if (n === 'steps' || n === 'step' || n === 'stepcount') out.steps = b[k];
    else if (n === 'activekcal' || n === 'activecalories' || n === 'activeenergy' || n === 'kcal') out.active_kcal = b[k];
    else if (n === 'date') out.date = b[k];
  });
  return out;
}

/** Pure: validates and normalizes one day. Accepts "8,432", "8432 steps", 512.7, etc. Returns null if nothing usable. */
function cleanDay_(b, todayKey) {
  const num = (v, max) => {
    if (v === undefined || v === null || v === '') return null;
    const t = String(v).replace(/[^0-9.]/g, '');
    if (t === '') return null;
    const n = Number(t);
    return isFinite(n) && n >= 0 && n <= max ? Math.round(n) : null;
  };
  // Steps are always whole numbers, so any dot or comma is a thousands separator ("1.708" or "1,708" = 1708 steps).
  const steps = (b.steps === undefined || b.steps === null || b.steps === '') ? null : num(String(b.steps).replace(/[^0-9]/g, ''), 150000);
  const kcal = num(b.active_kcal, 10000);
  if (steps === null && kcal === null) return null;
  const date = /^\d{4}-\d{2}-\d{2}$/.test(String(b.date || '')) ? String(b.date) : todayKey;
  if (date > todayKey) return null;
  return { date, steps, kcal };
}

/** Pure: compare two strings in constant time for equal lengths. */
function sameText_(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

function upsert_(sh, day, tz) {
  const last = sh.getLastRow();
  const keys = last > 1 ? sh.getRange(2, 1, last - 1, 1).getValues().map(r => r[0] instanceof Date ? Utilities.formatDate(r[0], tz, 'yyyy-MM-dd') : '') : [];
  const i = keys.indexOf(day.date);
  const row = i >= 0 ? i + 2 : last + 1;
  const prev = i >= 0 ? sh.getRange(row, 2, 1, 2).getValues()[0] : ['', ''];
  sh.getRange(row, 1, 1, 5).setValues([[
    Utilities.parseDate(day.date, tz, 'yyyy-MM-dd'),
    day.steps === null ? prev[0] : day.steps,
    day.kcal === null ? prev[1] : day.kcal,
    new Date(), 'iPhone Shortcut']]);
}

function sha256Hex_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)
    .map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
}

function reply_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

if (typeof module !== 'undefined') module.exports = { cleanDay_, sameText_, normalizeFields_ }; // Node tests only
