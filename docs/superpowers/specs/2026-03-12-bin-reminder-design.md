# Bin Collection Email Reminder — Design Spec

**Date:** 2026-03-12
**Status:** Under review

---

## Overview

A GitHub Actions workflow that runs nightly, scrapes the Waverley Borough Council bin collection website for the user's address, and sends a Gmail reminder the evening before any scheduled collection.

---

## Architecture

### Scraper flow (three HTTP steps, no browser)

**Step 1 — Fetch Track token**

```
GET https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1
```

Parse the response HTML. Find the `<form>` with `data-form-title="Property Lookup Form"`. Its `action` attribute contains the Track token inline, e.g.:

```
https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track=2026/03/12/QDFR1EH53W&seq=2
```

Extract the `Track` value using a regex: `Track=([^&]+)`. This token is generated fresh by the server on every page load and must never be hardcoded. If the token cannot be extracted, log an error and exit non-zero.

**Step 2 — POST postcode, get address list**

```
POST https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track=<TOKEN>&seq=2
Body (form-encoded): address_postcode=<POSTCODE>&address_name_number=<HOUSE_NUMBER>
```

Confirmed field names from live HTML: `address_postcode` and `address_name_number`.

Response: HTML list of address hyperlinks. Each link contains a `pIndex` query parameter. Find the link whose `aria-label` starts with `<HOUSE_NUMBER>,` (comma immediately after the number, to avoid matching e.g. `17` when looking for `7`). Extract its `pIndex`. If no match is found, log an error and exit non-zero.

**Step 3 — Fetch collection schedule**

```
GET https://wav-wrp.whitespacews.com/mop.php?Track=<TOKEN>&serviceID=A&seq=3&pIndex=<N>
```

Parse HTML for collection entries. Each entry is a `<ul>` block containing `<li>` elements with `tabIndex="0"`. Within each block, extract the date (format `DD/MM/YYYY`) and service name. If no entries are found, treat as empty schedule (no email).

### Decision logic

- Convert each collection date to a `datetime.date` object using `datetime.strptime(date_str, "%d/%m/%Y").date()`.
- Compare against `datetime.date.today() + datetime.timedelta(days=1)` using UTC (`datetime.utcnow().date()`). The 7pm UTC trigger time means this equals the same evening in both UTC and BST, so UTC is acceptable for this use case.
- If any collection date equals tomorrow, collect all service names due that day.
- If no collection is due tomorrow, print a log message and call `sys.exit(0)` (clean success — GitHub Actions shows green).

### Email

- **Transport:** Gmail SMTP (`smtp.gmail.com`, port 587, STARTTLS)
- **Auth:** Gmail address + Google app password
- **Format:** Use `email.mime.text.MIMEText` (stdlib) for proper header formatting
- **Subject:** `Bin reminder: put out your bins tonight`
- **Body:** Plain text, e.g.:
  ```
  Tomorrow's collections (Tuesday 17 March):
  - Food Waste Collection Service
  - Recycling Collection Service

  — Waverley bin bot
  ```

### Error handling

All HTTP requests use a 15-second timeout. On any HTTP error (`raise_for_status()`), scrape failure, or unhandled exception: log the error to stdout and exit non-zero so GitHub Actions marks the job as failed (visible in the Actions tab).

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

```yaml
on:
  schedule:
    - cron: '0 19 * * *'   # 7pm UTC daily (note: GH Actions may run up to ~60 min late)
  workflow_dispatch:         # allow manual trigger for testing

jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install requests beautifulsoup4
      - run: python scraper.py
        env:
          POSTCODE: ${{ secrets.POSTCODE }}
          HOUSE_NUMBER: ${{ secrets.HOUSE_NUMBER }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
```

### `scraper.py`

Single script, procedural:
1. Read env vars: `POSTCODE`, `HOUSE_NUMBER`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`
2. GET seq=1, extract Track token (exit non-zero if not found)
3. POST postcode to get address list, find matching `pIndex` by `^<HOUSE_NUMBER>,` match on `aria-label` (exit non-zero if not found)
4. GET seq=3, parse collection entries
5. Check for tomorrow's collections
6. If found: send email via Gmail SMTP using `MIMEText`, exit 0
7. If not found: log "No collections tomorrow", exit 0

Use `html.parser` as the BeautifulSoup parser (stdlib, no extra install needed).

---

## GitHub Actions secrets

| Secret | Example value | Notes |
|---|---|---|
| `POSTCODE` | `GU0 0XX` | Your full postcode |
| `HOUSE_NUMBER` | `42` | House number used to match your address |
| `GMAIL_ADDRESS` | `you@gmail.com` | Sending address (can equal `RECIPIENT_EMAIL`) |
| `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` | Google app password, not your main password |
| `RECIPIENT_EMAIL` | `you@gmail.com` | Where reminders are delivered |

---

## Known limitations

- GitHub Actions scheduled workflows can run up to ~60 minutes late under heavy load. The 7pm UTC reminder may occasionally arrive at 7:30–8pm.
- The scraper depends on the Waverley Council website HTML structure. If the site is redesigned, the scraper will need updating.

---

## Stretch goal: Alexa skill

A separate AWS Lambda function that calls the same three-step scrape on demand and returns the next collection date as a spoken response ("Your next bin collection is recycling on Tuesday"). No changes required to this repo.

---

## Out of scope

- ICS calendar generation
- SMS/push notifications
- Multiple addresses
- Historical data
