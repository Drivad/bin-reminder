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

Returns plain text, suitable for Siri to speak aloud. On any error, returns a plain-text error message (never crashes silently). Missing or empty `q` falls through to the default intent (next upcoming collections) — no special-case branch needed.

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

`scrape_schedule()` raises an exception on any failure (site down, token not found, address not found). It returns an empty list if the schedule page is valid but contains no future entries. The route handler catches exceptions and returns the user-friendly error string; an empty list is passed to `resolve_intent` normally.

### Service name display

Service names from `parse_collections` are long (e.g. `"Garden Waste Collection Service"`). For spoken output, strip the suffix `" Collection Service"` (case-insensitive) to produce short display names: `"Garden Waste"`, `"Recycling"`, `"Food Waste"`, `"Domestic Waste"`.

Helper: `short_name(service: str) -> str`
```python
import re
return re.sub(r"\s*collection service\s*$", "", service, flags=re.IGNORECASE).strip()
```

### Keyword matching

`q` is lowercased. Keywords are checked in the order shown below — first match wins. This means a query like "recycling this week" matches "this week" (the first rule), not "recycling". This is intentional: week queries return all collections for that period.

| Priority | Keyword(s) in `q.lower()` | Intent | Response |
|---|---|---|---|
| 1 | "this week" | Collections Mon–Sun this week | See response format below |
| 2 | "next week" | Collections Mon–Sun next week | See response format below |
| 3 | "garden" | Next garden waste | Single service + date |
| 4 | "recycling" | Next recycling | Single service + date |
| 5 | "food" | Next food waste | Single service + date |
| 6 | "domestic" or "rubbish" or "general" | Next domestic waste | Single service + date |
| 7 | *(anything else, including empty)* | Next upcoming collection(s) | All services on the nearest date |

Service keyword matching: `keyword in service.lower()` on each `(date, service)` tuple from the schedule. E.g. `"garden" in "garden waste collection service"` → True.

"This week" = Monday through Sunday of the current UTC week. "Next week" = Monday through Sunday of the following UTC week.

### Response format

Plain text, written to be spoken. Uses short display names (see above).

**Default intent (next upcoming):**
- With results: `"Your next collections are Garden Waste and Recycling on Tuesday 17 March."`
- Single service: `"Your next collection is Food Waste on Tuesday 17 March."`
- No results: `"There are no upcoming collections in the schedule."`

**This week:**
- With results: `"This week's collections: Food Waste on Tuesday 17 March, Recycling on Tuesday 17 March."`
- No results: `"There are no collections this week."`

**Next week:**
- With results: `"Next week's collections: Domestic Waste on Tuesday 24 March, Food Waste on Tuesday 24 March."`
- No results: `"There are no collections next week."`

**Service-specific (e.g. garden):**
- With result: `"Your next Garden Waste collection is Thursday 26 March."`
- No result: `"There are no upcoming Garden Waste collections in the schedule."`

**Scrape error:**
`"Sorry, I couldn't fetch the bin schedule right now. Please try again later."`

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
- `short_name(service: str) -> str` — strips "Collection Service" suffix for spoken output
- `resolve_intent(q: str, collections: list[tuple[datetime.date, str]]) -> str` — keyword matching + response formatting (pure function, fully testable, no I/O)
- `scrape_schedule() -> list` — calls fetch_html / extract_track_token / find_pindex / parse_collections; raises on failure, returns empty list if no entries
- Route handler: calls `scrape_schedule()` in a try/except, passes result to `resolve_intent(q, collections)`, returns plain text with `Content-Type: text/plain`

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

Unit tests for `short_name()` and `resolve_intent()` only. Uses a fixed list of fake `(date, service_name)` tuples covering all four service types across multiple dates. No HTTP calls. Tests cover:
- Each keyword intent (this week, next week, each service type, default)
- No-results cases for each intent
- Empty collections list
- Missing/empty `q`

---

## Railway deployment

- Deploy from existing `Drivad/bin-reminder` GitHub repo
- Railway's free "Trial" plan provides a $5 one-time credit; a credit card is required to continue beyond that. Paid "Hobby" plan is ~$5/month and covers a small always-on web service comfortably.
- Set environment variables in Railway dashboard: `POSTCODE=GU7 3SN`, `HOUSE_NUMBER=7`
- Railway auto-deploys on push to `main`

---

## Siri Shortcut

Manual setup by user after deployment (not automated):

1. Create a new Shortcut in the iOS Shortcuts app
2. Add action: **Ask for Input** (Text) — prompt: "What would you like to know?"
3. Add action: **URL** — set the base URL to `https://<railway-url>/ask` and add a query parameter `q` with value set to the **Provided Input** from step 2. (Using the URL action with a named query parameter field ensures the input is correctly URL-encoded automatically — do **not** concatenate the input directly into a URL string.)
4. Add action: **Get Contents of URL** — using the URL from step 3
5. Add action: **Speak Text** — speak the result
6. Name the shortcut "Bin Check" — triggered by "Hey Siri, Bin Check"

---

## Out of scope

- Authentication / rate limiting
- Multi-address support
- Caching
- Natural language understanding beyond keyword matching
