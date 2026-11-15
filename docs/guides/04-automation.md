# Automation Documentation

Everything runs on **Google's servers**: your laptop can be off. Cost: $0 (free Google services, plus the free Shortcuts app on your iPhone). Source code: **github.com/aminkhazri/health-os** (public; private settings and the sync key are never in it).

## Architecture

```
 iPhone (Apple Health) --Shortcut, POST + key--> Health OS Inbox (public, write-only)
                                                        |
 Health OS app (private web app) <--reads/writes--> Tracker Sheet <-- formulas: averages, trends, calorie check
        ^                                               |
   you log here                         weeklyReview() Sundays ~6 PM --> Gmail
 Google Calendar  <-- recurring events + alerts (created once by setup())
 Google Tasks     <-- resetDailyTasks(), daily ~3 AM
```

## Components

| Piece | Technology | Notes |
|---|---|---|
| Health OS app | Apps Script **web app** (HtmlService), project "Health OS Automation" | Deployed "Execute as me / Only myself": only your Google account can open it. The page talks to the server with google.script.run |
| Food logging | Parser in the page + a Foods library tab | Free-text quick add; longest keyword match; quantities like "2", "half", "24 oz"; unknown foods are learned once |
| Reminders | Calendar recurring event series | Alerts set per series; dinner is silent |
| Checklist | Apps Script + Tasks API (advanced service) | The Tasks API has no recurrence, so a daily job deletes yesterday's tasks and adds today's |
| Steps sync | iPhone Shortcut → separate project "Health OS Inbox" | See "Steps sync and the sync key" below |
| Calculations | Sheets formulas (AVERAGEIFS, SUMIFS, COUNTIFS) | Recalculate as data arrives |
| Weekly email | Apps Script MailApp + time-driven trigger | Reads the Weekly Summary tab |
| Smart nudges | Apps Script trigger every 15 min (checkNudges in Nudges.js) | At set checkpoints, reads today's water and calm minutes; if behind pace, creates a 5-minute calendar event 2 minutes ahead with a popup, which the Google Calendar app turns into a notification. Each checkpoint fires once a day; old nudge events are cleaned up |

## Stretching and demo videos

- `src/Stretch.js` holds three things as plain data: the stretches (name and cue), the three routines (stretch, seconds, each side or not) and the video list (exercise or stretch name → YouTube video ID).
- The guided timer runs in the phone's browser. When a routine ends, the app calls `addStretch`, which adds the minutes to the Daily Log (column S, "Stretch min") under a lock so two saves can't overwrite each other.
- Videos are not stored in the app. Tapping Demo creates a YouTube player for that one video; nothing loads until then.
- To swap a video: change its ID in `src/Stretch.js`, then publish a new version of the web app.
- Lesson learned: Apps Script's HTML templates treat `//` inside a backtick string as a comment and cut the line, which broke the page once. URLs in the page script are built with normal quotes.

## Tracker Sheet tabs

| Tab | Holds |
|---|---|
| Start Here | Targets: start/goal weight, daily calories, gain band, current phase, UPS exit date |
| Daily Log | One row per day: weight, sleep, energy, checklist, meals detail, food totals (kcal, protein, water, caffeine), resting HR, mindful minutes, stretch minutes (column S) |
| Food Log | Every food/drink entry with calories and macros |
| Foods | The food library the app matches against (editable) |
| Workout Log | One row per exercise per session |
| Activity | Steps and active calories per day from the iPhone |
| Weekly Summary | Weekly averages: weight, change, workouts, sleep, protein days, calories, steps, resting HR, calorie check |
| _Sync (hidden) | Only the fingerprint of the sync key |

## Steps sync and the sync key

- The app is private, and a Shortcut can't sign in to Google, so a second, tiny project — **Health OS Inbox** — is deployed for "Anyone". It does one thing: accept steps and active calories for a day and write them to the Activity tab. It can't read anything back.
- **The key:** the app's Progress tab creates a random 64-character key and shows it once. The Sheet stores only its **SHA-256 fingerprint**. The inbox hashes the key it receives and compares fingerprints, so even a copy of the Sheet contains no usable key.
- **Lost or leaked key:** Progress → iPhone sync → Replace sync key (tap twice), then paste the new key into the Shortcut. The old key stops working immediately.
- The inbox accepts flexible field names ("steps", "active kcal", "active_kcal") and reads "1.708" or "1,708" steps as 1,708.
- Each sync overwrites that day's row, so running it often is harmless.
- iPhones block Health data while locked, so a run that fires while the phone is locked may be skipped. The charger trigger usually fires while it's unlocked.

## Concepts (for learning / portfolio)

- **Web app deployments:** a deployment freezes a *version* of the code. Saving code changes nothing for users until you publish a new version: Deploy → Manage deployments → Edit → Version: New version → Deploy. The URL stays the same.
- **Least privilege:** the public piece (the inbox) is a separate project with only the spreadsheets permission and a single job, so the private app never has to be public.
- **Hashing secrets:** store a fingerprint, never the secret. Compare in constant time.
- **Time-driven triggers:** Apps Script's built-in cron (daily ~3 AM, Sundays ~6 PM).
- **Advanced services:** wrappers over Google REST APIs (here Tasks v1), declared in appsscript.json.
- **OAuth consent:** you granted each project its permissions once. Google keeps the token on its side; no password or token is in the code. The "unverified app" warning is normal for your own scripts.
- **Idempotency:** setup functions check what exists before creating anything, so re-running them doesn't duplicate.
- **Time zones:** the script and the Sheet are both on America/New_York, so a 9 PM entry never lands on the next day.
- **Tests:** 20 automated tests (Node's built-in test runner) cover the checklist builder, food parser and inbox validation: `npm test`.

## Maintenance

- **Normally: nothing.** Triggers and deployments keep running.
- **If something fails:** Google emails you a "Summary of failures for Google Apps Script". Open the project → Executions to see the error.
- **Code changes:** edit in GitHub or locally, push the files to the project with clasp (or paste in the editor), save, then publish a new version (above).
- **Changing reminder times:** edit the events in Google Calendar ("All events"). No code needed.
- **Changing targets:** calories in the Sheet's Start Here tab; water, protein, caffeine and step goals in the private config file.
- **Quotas (free account):** ~100 emails/day and 90 minutes of trigger time/day. This system uses 1 email/week and seconds per day.

## Revoke / uninstall

1. script.google.com → each project → Triggers → delete triggers; Deploy → Manage deployments → Archive.
2. myaccount.google.com/permissions → remove "Health OS Automation" and "Health OS Inbox".
3. Delete the "Health OS Sync" Shortcut and its automations on the iPhone.
4. Optionally delete the Health & Fitness calendar and the task list.

## Limitations

- Google Tasks can't have reminder times through the API (dates only). Timed nudges come from the Calendar.
- Your TicWatch's heart rate stays in Google's systems and isn't readable on iPhone, so resting HR is typed in each morning.
- Notifications depend on the Google Calendar app's iPhone notification settings.
