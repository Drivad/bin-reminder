# Datacenter-reachable bin-collection sources for Waverley Borough Council

Investigated 2026-11-15 from a GitHub-Actions-like cloud container (datacenter IP,
outbound HTTPS via proxy). Goal: find a source that could drive a fully-remote
reminder — garden waste and bank-holiday changes included — with no device at home.

## Verdict up front

**There is a viable fully-remote option, but it is a partial one.**

The council's own website (`www.waverley.gov.uk`) is **completely reachable from a
datacenter IP** — it is different infrastructure from the booking portal, and it
serves both the calendar PDFs and, on the HTML page, the full Christmas/New Year
revised-day table. The blocked portal remains blocked.

What this gets you and what it does not:

| Need | Available remotely? |
|---|---|
| Fortnightly recycling vs general-waste pattern | **Yes** — calendar PDFs, 2026 and 2027 |
| Garden waste dates | **Yes** — dedicated garden waste PDFs, 2026 and 2027 |
| Garden waste winter suspension | **Yes** — printed on the garden PDFs |
| Bank-holiday / Christmas day shifts | **Yes** — HTML table on the bins page |
| **Which weekday your property is collected** | **No** — not published anywhere |
| **Which zone you are (week 1 or week 2)** | **No** — not published anywhere |
| Food waste dates | **No** — absent from every calendar |

The two missing items are **fixed per property and never change**, so they can be
configured once by hand (and are already known — see `schedule.json`). That is the
crux: the *static* facts are the ones that are unavailable remotely, and the
*changing* facts are the ones that are available. So a remote job is feasible.

---

## 1. The council's own website — WORKS

### 1.1 The bins page

The URL in the brief still works but **301-redirects to a new path**; the site has
been restructured, so the old path should not be hardcoded.

| URL | Status | `server` header |
|---|---|---|
| `https://www.waverley.gov.uk/services/bins-and-recycling/rubbish-and-recycling-collections/check-bin-collection-day` | `301` → then `200` | *(none sent)* |
| `https://www.waverley.gov.uk/bins-garden-waste-and-recycling/check-your-bin-collection-day` | `200` | *(none sent)* |

The 301 `location` is `/bins-garden-waste-and-recycling/check-your-bin-collection-day`.
Response is 162,735 bytes of HTML. The stack is DotNetNuke (DNN) — `dnn_IsMobile`
and `.ASPXANONYMOUS` cookies, `x-ua-compatible: IE=edge`. The `server` header is
stripped on dynamic pages but static assets reveal `Microsoft-IIS/10.0`.

**Usable from a datacenter: yes.** No block, no CAPTCHA, no JS challenge. Five
sequential fetches all returned `200` with no rate limiting or throttling.

### 1.2 The calendar PDFs — real URLs found

The brief's example URL works, but the **current links on the page carry different
capitalisation and a `?ver=` cache-buster**. The `?ver=` parameter is **not
required** — all eight PDFs return `200` without it. Base path:

```
https://www.waverley.gov.uk/Portals/0/Documents/services/bins-and-recycling/check-bin-collection-day/
```

| Filename (appended to base path) | Status | Bytes |
|---|---|---|
| `refuse-and-recycling-calendar-2026-week-1.pdf` | `200` | 132,664 |
| `refuse-and-recycling-calendar-2026-week-2.pdf` | `200` | 132,925 |
| `garden-waste-2026-week-1-Calendar.pdf` | `200` | 137,595 |
| `garden-waste-2026-week-2-Calendar.pdf` | `200` | 136,608 |
| `Refuse-and-Recycling-Calendar-2027-week-1.pdf` | `200` | 132,336 |
| `Refuse-and-Recycling-Calendar-2027-week-2.pdf` | `200` | 132,751 |
| `Garden-Waste-2027-Week-1-Calendar.pdf` | `200` | 138,705 |
| `Garden-Waste-2027-Week-2-Calendar.pdf` | `200` | 137,827 |

All are `application/pdf`, PDF 1.7, one page, `server: Microsoft-IIS/10.0`.
The exact lowercase URL from the brief also returns `200` (132,664 bytes — byte-identical
to the discovered 2026 week 1 link, so the path is case-insensitive).

**2027 calendars are already published**, so the data runs ~13 months ahead.

### 1.3 What the PDFs actually contain

Text extracts cleanly with `pdftotext -layout` (no OCR needed).

**Week 1 vs week 2: yes, clearly distinguished.** They are exact inverses of each
other — every row that says `Recycling` in week 1 says `General Waste` in week 2.
Diff of the two 2026 refuse calendars, January–March:

```
< General Waste & Recycling Calendar Week 1 - 2026
> General Waste & Recycling Calendar Week 2 - 2026

< Recycling                      1   2    General Waste    2  3  4  5  6
< General Waste      5   6   7    8   9    Recycling        9 10 11 12 13
< Recycling         12  13  14   15  16    General Waste   16 17 18 19 20
---
> General Waste                   1   2    Recycling        2  3  4  5  6
> Recycling          5   6   7    8   9    General Waste    9 10 11 12 13
> General Waste     12  13  14   15  16    Recycling       16 17 18 19 20
```

**Representative extract — `refuse-and-recycling-calendar-2026-week-1.pdf`:**

```
General Waste & Recycling Calendar Week 1 - 2026

   January           Mo    Tu    We   Th  Fr     February      Mo  Tu  We  Th  Fr
Recycling                            1   2    General Waste    2   3   4   5   6
General Waste        5     6     7   8   9    Recycling        9  10  11  12  13
Recycling           12    13    14  15  16    General Waste   16  17  18  19  20
General Waste       19    20    21  22  23    Recycling       23  24  25  26  27
Recycling           26    27    28  29  30

   October           Mo    Tu    We   Th  Fr     December      Mo  Tu  We  Th  Fr
General Waste                        1   2    Recycling            1   2   3   4
Recycling            5     6     7   8   9    General Waste    7   8   9  10  11
General Waste       12    13    14  15  16    Recycling       14  15  16  17  18
Recycling           19    20    21  22  23    General Waste   21  22  23  24  25
General Waste       26    27    28  29  30    Recycling       28  29  30  31

KEY
Recycling
General Waste
Please check your bin collection dates on the
Waverley website as they are subject to change
```

Note the structure: **each row is a whole week (Mon–Fri), not a single day.** The
row labelled `Recycling  12 13 14 15 16` means "the week of 12 Jan is a recycling
week" — it does not say which of those five days is *your* day. The PDF is designed
for a resident who already knows their weekday.

**Representative extract — `garden-waste-2026-week-1-Calendar.pdf`:**

```
Week 1 - Garden Waste Collections 2026
Collection day:

                  January                       February                     March
 Mo    Tu    We    Th   Fr   Mo   Tu   We   Th   Fr   Mo    Tu    We    Th    Fr
  5     6     7     8   9     2    3    4    5   6     2     3     4     5     6
 19    20    21    22   23   16   17   18   19  20    16    17    18    19    20
                                                      30    31

                  October                     November                     December
 Mo    Tu    We    Th   Fr   Mo   Tu   We   Th   Fr   Mo    Tu    We    Th    Fr
                    1   2     9   10   11   12  13     7     8     9    10    11
 12    13    14    15  16    23   24   25   26  27      No collections 21 Dec-01 Jan
 26    27    28    29  30
```

Note `Collection day:` — a **blank field for the resident to write in by hand**.
This confirms the weekday is not published data.

**Garden waste coverage: yes**, as separate week 1 / week 2 PDFs, fortnightly
year-round, and the **winter suspension is marked**: `No collections 21 Dec-01 Jan`
for 2026, and `No collections 20 Dec 2027 - 02 Jan 2028` on the 2027 calendars.

**Bank-holiday changes in the PDFs: NO — and this is the important negative.**
`grep -iE "bank|holiday|christmas|new year|chang"` across all eight extracts returns
only the garden-waste winter-suspension line and the refuse footer disclaimer. The
refuse calendars show collections proceeding **as if bank holidays did not exist**:

- 2026 week 1 December shows `General Waste 21 22 23 24 25` — including Friday
  25 December, Christmas Day. No collection happens that day.
- It then shows `Recycling 28 29 30 31` as a normal week, although Monday
  28 December 2026 is the substitute Boxing Day bank holiday.
- 2027 week 1 December likewise shows `Recycling 27 28 29 30 31`, although Mon 27
  and Tue 28 December 2027 are both substitute bank holidays.

The PDFs carry only the disclaimer `Please check your bin collection dates on the
Waverley website as they are subject to change`. **Driving reminders from the PDFs
alone would send wrong dates across every bank holiday period.**

One further caution: the grid layout extracts imperfectly in places. In
`Garden-Waste-2027-Week-1-Calendar.pdf` the September block comes out as
`1  2  1  2  3` and October has a stray duplicate `29` on its own line — layout
artifacts of the two-row-per-month grid. Any parser needs to validate that
extracted dates actually form a 14-day series rather than trusting the text.

### 1.4 The Christmas / bank-holiday table — the gap-filler, and it is on the HTML page

There is **no separate Christmas page** (confirmed against `sitemap.xml`, which
lists 11 bins pages — none festive). The data is embedded in the bins page itself,
as a clean HTML `<table>`, and the bins page returns `200` from here.

Parsed straight out of the markup — `Christmas and New Year period 2026 to 2027`:

| Usual collection day | Revised collection day |
|---|---|
| Monday 21 December | No change |
| Tuesday 22 December | No change |
| Wednesday 23 December | No change |
| Thursday 24 December (Christmas Eve) | No change |
| Friday 25 December (Christmas Day) | Monday 28 December |
| Monday 28 December (Boxing Day) | Tuesday 29 December |
| Tuesday 29 December | Wednesday 30 December |
| Wednesday 30 December | Thursday 31 December |
| Thursday 31 December | Saturday 2 January |
| Friday 1 January (New Year's Day) | Monday 4 January |
| Monday 4 January | Tuesday 5 January |
| Tuesday 5 January | Wednesday 6 January |
| Wednesday 6 January | Thursday 7 January |
| Thursday 7 January | Friday 8 January |
| Friday 8 January | Saturday 9 January |

Accompanying text: *"Please present your bins at 6am on your revised collection
day. Normal collections resume from Monday 11 January 2027."* And for garden waste:
*"There will be no garden waste collections from 21 December 2026 to 1 January 2027."*

This is exactly the missing bank-holiday layer, it is machine-readable, and it was
already published on 15 November — about six weeks ahead of the period it covers.

**But a serious data-quality warning.** The same page carries a *second* table, for
clinical waste, which is **stale — it is last year's**. Its weekdays do not match
2026: it says `Thursday 25 December` and `Friday 26 December (Boxing Day)`, but in
2026 those dates are Friday and Saturday. They were Thursday and Friday in **2025**.
The page even admits it in the surrounding prose — *"Christmas and New Year
collection dates will be announced shortly"* — directly above a fully populated
table, and there is a stray `-->` in the rendered text where an HTML comment was
left unbalanced.

The rubbish/recycling table is correct for 2026 (25 Dec 2026 *is* a Friday; the
substitute Boxing Day bank holiday *is* Mon 28 Dec). But the page demonstrably ships
stale tables next to current ones, so **any parser must date-check what it reads** —
verify the named weekdays match the target year before trusting a row.

### 1.5 robots.txt — a caveat on the PDFs

`https://www.waverley.gov.uk/robots.txt` → `200`, 172 lines.

- The **HTML bins page is permitted** — `User-agent: *` with an empty `Disallow:`,
  and nothing matching `/bins-garden-waste-and-recycling/`.
- The **PDFs are disallowed**: `Disallow: /Portals/` appears for `User-agent: *`,
  and the calendars live at `/Portals/0/Documents/...`.

This is boilerplate DNN crawler hygiene — it exists to keep the CMS asset tree out
of search indexes, not to stop residents downloading calendars the council links
from its own page. But a well-behaved automated job should not fetch `/Portals/`
repeatedly on a schedule. Mitigations: fetch each PDF **once** by hand and commit
the parsed result (they change annually, not weekly), or skip the PDFs entirely and
derive the fortnightly pattern arithmetically from a single known anchor date, which
needs no PDF at all. The HTML page — the part that genuinely needs re-fetching,
because that is where bank-holiday changes appear — is not disallowed.

---

## 2. The whitespacews portal — BLOCKED, as expected

```
$ curl -s -o /dev/null -w "%{http_code}\n" \
    "https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1" --max-time 25
403
```

| URL | Status | `server` header |
|---|---|---|
| `https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1` | `403` | `awselb/2.0` |

Not retried with different headers, per the brief. The `403` comes straight from an
AWS Elastic Load Balancer before reaching the application — consistent with the
blanket datacenter-IP block already documented in `README.md`.

This confirms the two sources are genuinely separate infrastructure: council site on
on-premise `Microsoft-IIS/10.0`, portal behind `awselb/2.0`. Only the latter blocks us.

**Usable from a datacenter: no.** This is the only source with per-property,
address-level data (weekday, zone, garden-waste subscription status), which is why
the remote options cannot fully replace it.

---

## 3. Third-party republishers

### robbrad/UKBinCollectionData — supports Waverley, but via the blocked portal

The project does support Waverley. From `uk_bin_collection/tests/input.json`
(fetched `200` from `raw.githubusercontent.com`, 351 councils total):

```json
"WaverleyBoroughCouncil": {
  "LAD24CD": "E07000216",
  "house_number": "23",
  "postcode": "GU9 9QG",
  "skip_get_url": true,
  "url": "https://wav-wrp.whitespacews.com/",
  "wiki_name": "Waverley",
  "wiki_note": "Follow the instructions [here](https://wav-wrp.whitespacews.com/#!) until you get the page that shows your next scheduled collections. Then take the number from `pIndex=NUMBER` in the URL and pass it as the `-n` parameter along with your postcode in `-p`."
}
```

Its scraper (`councils/WaverleyBoroughCouncil.py`, `200`) hits exactly the endpoints
this repo's `scraper.py` already uses:

```
https://wav-wrp.whitespacews.com/
https://wav-wrp.whitespacews.com/mop.php?serviceID=A&...&seq=2
```

It is the same portal, the same `mop.php` sequence, and the same `pIndex` requirement.
**It does not republish the data — it scrapes it live**, so from a datacenter it hits
the identical `403`. No help here, and nothing to be gained by adopting it.

### Nothing else found

The council site links no API, feed or iCal — the postcode checker is a plain
hyperlink to `https://wav-wrp.whitespacews.com/#!`, i.e. it hands the user off to the
blocked portal and holds no lookup of its own. The only other machine-readable
outbound reference on the bins page is `api.cludo.com` (site search). No open-data
endpoint for Waverley collections was found.

---

## 4. Could this drive a fully-remote reminder?

**Yes, with one real caveat and one acceptable one.**

The workable design: hardcode the two static per-property facts (weekday and
week-1/week-2 zone — both already known and in `schedule.json`), derive the
fortnightly recycling/general-waste and garden-waste pattern from the calendars, and
**re-fetch the bins HTML page on each run to pick up bank-holiday changes**, applying
any `usual → revised` row that matches the configured weekday. No home device, no
`403`, nothing to refresh by hand every few weeks.

That is a genuine improvement on the current arrangement: it removes the recurring
manual refresh and the two-week expiry warning, and it keeps garden waste.

### Weaknesses, stated plainly

1. **Food waste is not covered at all.** No calendar includes it. It is weekly, so a
   fixed weekly rule would work — but that is an assumption, not published data, and
   it would silently break if the council changed the service.
2. **Garden waste subscription status is invisible.** The checker shows garden waste
   "for subscribed properties only"; the PDFs show the schedule for subscribers
   generally. A remote job cannot tell whether the subscription has lapsed, so it
   would keep announcing garden waste after a missed renewal (£87.60/year, renewed
   annually).
3. **The Christmas table is free prose in a CMS, and it ships stale.** The clinical
   waste table on that very page is a year out of date. The table is not a contract:
   its wording, structure and position can change between years, and a parser that
   works this December may silently match nothing next December. Matching nothing
   would fail *unsafely* — reminders would fall back to the unadjusted pattern and be
   confidently wrong over Christmas, the period people most rely on them. Any
   implementation needs to date-check rows and treat "table present but no rows
   parsed" as an alarm, not as "no changes".
4. **Non-Christmas bank holidays are unverified.** The page carries a Christmas/New
   Year table because that period shifts every day of the fortnight. Whether Waverley
   publishes the same for Easter, early May, spring and August bank holidays is not
   established — I only observed the festive table. If those shifts are announced
   somewhere else, or only in a news item, a remote job would miss them.
5. **Both PDFs and HTML are scraped artifacts.** The refuse PDFs carry an explicit
   disclaimer that dates are subject to change and should be checked on the website.
   The authoritative per-property answer lives only behind the `403`.
6. **The 301 and the `?ver=` churn show the paths move.** The brief's URLs were
   already stale by one site restructure. Filename capitalisation differs between the
   2026 and 2027 PDFs, so next year's links should be discovered by scraping the page
   for `.pdf` hrefs rather than constructed by pattern.
7. **`/Portals/` is robots-disallowed** (§1.5) — fetch the PDFs once, not nightly.

### Recommendation

Treat the council site as a **supplement, not a replacement**. The highest-value,
lowest-risk change is to use the bins HTML page's Christmas table to correct the
dates that `schedule.json` already provides, and to extend coverage when the saved
schedule runs out instead of dropping to the current estimate — which today has no
garden waste and no bank-holiday awareness. A fully-remote build is achievable, but
it trades an occasional manual refresh for a parser that can go quietly wrong over
Christmas, so it should fail loudly rather than fall back silently.

---

## Appendix: reproducing these checks

```sh
# Council bins page (follows the 301 to the current path)
curl -sSL -o bins.html -D - \
  "https://www.waverley.gov.uk/services/bins-and-recycling/rubbish-and-recycling-collections/check-bin-collection-day"

# Discover the current calendar PDF links rather than hardcoding them
grep -oiE 'href="[^"]*(calendar|garden)[^"]*\.pdf[^"]*"' bins.html | sort -u

# A calendar PDF, no ?ver= needed
B="https://www.waverley.gov.uk/Portals/0/Documents/services/bins-and-recycling/check-bin-collection-day"
curl -sSL -o gw.pdf "$B/garden-waste-2026-week-1-Calendar.pdf"
pdftotext -layout gw.pdf -          # pdftotext is preinstalled; no OCR required

# The portal, for contrast
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1" --max-time 25   # 403
```

All checks run 2026-11-15 from a cloud container on a datacenter IP.
