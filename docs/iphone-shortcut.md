# iPhone steps sync (Apple Health → Health OS)

```
iPhone Shortcut ──POST {key, steps, active_kcal}──▶ Health OS Inbox (Apps Script, "Anyone")
                                                     │  checks SHA-256(key) against _Sync!B1
                                                     ▼
                                          Tracker Sheet › Activity tab (one row per day)
                                                     │
                                          Health OS app (private) reads it: 👟 gauge, charts
```

## One-time setup
1. In Health OS on the iPhone: **Progress → iPhone sync → Create (or Replace) sync key → Copy key**. The key is shown once; only its fingerprint is stored.
2. **Shortcuts → +**, name it `Health OS Sync`, then add:
   1. **Find Health Samples** — Type *Steps*, filter *Start Date is today*, **Group by Day**.
   2. **Calculate Statistics** — *Sum* of Health Samples.
   3. **Find Health Samples** — Type *Active Energy*, *Start Date is today*, **Group by Day**.
   4. **Calculate Statistics** — *Sum*.
   5. **Get Contents of URL** — the inbox URL; Method **POST**; Request Body **JSON**:
      `key` (Text) = pasted key · `steps` (Number) = first Statistics · `active_kcal` (Number) = second Statistics.
   6. *(optional while testing)* **Show Notification** — Contents of URL.
3. Run it once and allow Health access. You should see `{"ok":true,...}`.
4. **Automation → + → Charger → Is Connected → Run Immediately → Health OS Sync**, plus a **Time of Day** automation (e.g. 4:45 PM).

## Notes
- Each run overwrites today's row, so running it often is safe.
- Health data is locked while the iPhone is locked; the charger trigger usually fires as you plug in.
- Lost or leaked key: tap **Replace sync key** and paste the new one into the Shortcut.
