# Siri Bin Query API — Design Spec

**Date:** 2026-03-13
**Status:** Under review

---

## Overview

A Flask API endpoint added to the existing `bin-reminder` repo, deployed to Railway. A Siri Shortcut calls it with a spoken question and reads the plain-text response aloud.

---

## Architecture

### Endpoint

```
GET /ask?q=<url-encoded question>
```

Returns plain text, suitable for Siri to speak aloud. On any error, returns a plain-text error message (never crashes silently).

### Scraping

On each request, the API runs the same 3-step HTTP flow already in `scraper.py`:
1. GET seq=1 → extract Track token
2. POST postcode → find pIndex
3. GET seq=3 → parse collection schedule

`POSTCODE` and `HOUSE_NUMBER` are read from Railway environment variables.

Reuses existing functions imported directly from `scraper.py`:
- `fetch_html`
- `extract_track_token`
- `find_pindex`
- `parse_collections`

### Keyword matching

The `q` parameter is lowercased and checked for keywords in priority order:

| Keyword(s) | Intent | Response shape |
|---|---|---|
| "this week" | Collections Mon–Sun this week | List all matching, or "no collections this week" |
| "next week" | Collections Mon–Sun next week | List all matching, or "no collections next week" |
| "garden" | Next garden waste date | Single service + date |
| "recycling" | Next recycling date | Single service + date |
| "food" | Next food waste date | Single service + date |
| "domestic" / "rubbish" / "general" | Next domestic waste date | Single service + date |
| *(anything else)* | Next upcoming collection(s) | All services due on the nearest date |

"This week" = Monday through Sunday of the current week (using UTC date).

### Response format

Plain text, written to be spoken. Examples:

- `"Your next recycling collection is Tuesday 17 March."`
- `"This week's collections: Food Waste on Tuesday 17 March, Recycling on Tuesday 17 March."`
- `"No garden waste collections found in the schedule."`
- `"Your next collections are Food Waste and Recycling on Tuesday 17 March."`

### Error handling

- Scrape failure (site down, token not found, address not found): return `"Sorry, I couldn't fetch the bin schedule right now. Please try again later."`
- Missing `q` parameter: return `"Your next collections are ..."` (fall through to default intent)
- All exceptions caught at the route level, logged to stderr, safe message returned to Siri

---

## File structure

```
bin-reminder/
├── .github/workflows/bin-reminder.yml  (unchanged)
├── scraper.py                          (unchanged)
├── api.py                              (new)
├── Procfile                            (new)
├── requirements.txt                    (add flask, gunicorn)
└── tests/
    ├── test_scraper.py                 (unchanged)
    └── test_api.py                     (new)
```

### `api.py`

- Flask app with single route `GET /ask`
- `resolve_intent(q: str, collections: list) -> str` — keyword matching + response formatting (pure function, fully testable)
- `scrape_schedule() -> list` — calls fetch_html / extract_track_token / find_pindex / parse_collections
- Route handler calls `scrape_schedule()`, passes result to `resolve_intent()`, returns plain text

### `Procfile`

```
web: gunicorn api:app
```

### `requirements.txt` additions

```
flask
gunicorn
```

### `tests/test_api.py`

Unit tests for `resolve_intent()` only — keyword matching and response text. No HTTP mocking needed (scraping is tested in `test_scraper.py`). Uses a fixed list of fake collection entries covering multiple service types and dates.

---

## Railway deployment

- Deploy from existing `Drivad/bin-reminder` GitHub repo
- Set environment variables: `POSTCODE=GU7 3SN`, `HOUSE_NUMBER=7`
- Railway auto-deploys on push to `main`
- Free tier: no credit card, no sleep/cold-start issues

---

## Siri Shortcut

Manual setup by user after deployment (not automated):

1. Create a new Shortcut in the iOS Shortcuts app
2. Add action: **Ask for Input** — prompt: "What would you like to know?"
3. Add action: **Get Contents of URL** — `https://<railway-url>/ask?q=<Provided Input>`
4. Add action: **Speak Text** — speak the result
5. Name the shortcut "Bin Check" — triggered by "Hey Siri, Bin Check"

---

## Out of scope

- Authentication / rate limiting
- Multi-address support
- Caching (scrape is fast enough at ~2s)
- Natural language understanding beyond keyword matching
