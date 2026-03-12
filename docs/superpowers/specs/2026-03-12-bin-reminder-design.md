# Bin Collection Email Reminder — Design Spec

**Date:** 2026-03-12
**Status:** Approved

---

## Overview

A GitHub Actions workflow that runs nightly, scrapes the Waverley Borough Council bin collection website for the user's address, and sends a Gmail reminder the evening before any scheduled collection.

---

## Architecture

### Scraper flow (three HTTP steps, no browser)

1. `GET https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1`
   Extract the `Track` session token from the form action URL (e.g. `2026/03/12/QDFR1EH53W`). This token is generated fresh by the server on every page load — it must not be hardcoded.

2. `POST https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track=<TOKEN>&seq=2`
   Body: `address_postcode=<POSTCODE>&address_name_number=<HOUSE_NUMBER>`
   Response: HTML list of matching addresses. Find the `pIndex` whose label contains the house number.

3. `GET https://wav-wrp.whitespacews.com/mop.php?Track=<TOKEN>&serviceID=A&seq=3&pIndex=<N>`
   Parse HTML for upcoming collection entries. Each entry contains a date (`DD/MM/YYYY`) and a service name (e.g. "Recycling Collection Service").

### Decision logic

- Convert each collection date to a `datetime.date` object.
- If any collection date equals `today + 1 day`, collect all services due that day.
- If no collection is due tomorrow, exit silently (no email sent).

### Email

- **Transport:** Gmail SMTP (`smtp.gmail.com:587`, STARTTLS)
- **Auth:** Gmail address + Google app password
- **Subject:** `Bin reminder: put out your bins tonight`
- **Body:** Plain text listing tomorrow's date and each service due, e.g.:
  ```
  Tomorrow's collections (Tuesday 17 March):
  - Food Waste Collection Service
  - Recycling Collection Service

  — Waverley bin bot
  ```

---

## Repository structure

```
bin-reminder/
├── .github/
│   └── workflows/
│       └── bin-reminder.yml
└── scraper.py
```

### `bin-reminder.yml`

- Trigger: `schedule: cron: '0 19 * * *'` (7pm UTC daily)
- Runner: `ubuntu-latest`
- Steps: checkout → `pip install requests beautifulsoup4` → `python scraper.py`
- All secrets passed as environment variables

### `scraper.py`

Single script, no classes needed:
1. Read env vars: `POSTCODE`, `HOUSE_NUMBER`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`
2. Fetch Track token
3. POST postcode to get address list, find matching `pIndex`
4. Fetch collection schedule
5. Check for tomorrow's collections
6. Send email if any found, else exit 0

---

## GitHub Actions secrets

| Secret | Description |
|---|---|
| `POSTCODE` | e.g. `GU7 3SN` |
| `HOUSE_NUMBER` | e.g. `7` |
| `GMAIL_ADDRESS` | Sending Gmail address |
| `GMAIL_APP_PASSWORD` | Google app password (not main password) |
| `RECIPIENT_EMAIL` | Where to send reminders |

---

## Stretch goal: Alexa skill

A separate AWS Lambda function that calls the same three-step scrape on demand and returns the next collection date as a spoken response. No changes required to this repo — the Lambda embeds the same scraping logic independently.

---

## Out of scope

- ICS calendar generation
- SMS/push notifications
- Multiple addresses
- Historical data
