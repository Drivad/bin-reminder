# Waverley bin reminder

Emails you the evening before a bin collection.

## How it runs

The council's portal sits behind an AWS load balancer that rejects datacenter
IPs, so GitHub-hosted runners get a blanket `403` and cannot read the schedule.

The portal returns several weeks of collections in one go, though, so it does
not need visiting daily. Fetch it occasionally from home, save the result, and
the nightly job just reads the saved copy - which works anywhere, CI included.

`scraper.py` picks the best source available, in order:

| Source | Covers | Needs |
|---|---|---|
| `schedule.json` - the saved fetch | everything, garden waste included | a refresh every few weeks |
| live portal scrape | everything | a residential connection |
| fortnightly estimate | food / recycling / domestic only | nothing |

Whichever is used, **bank-holiday changes are applied on top**, read from the
council's own website. That part needs no home connection: `waverley.gov.uk` is
ordinary on-premise hosting and answers datacenter IPs fine - it is only the
third-party booking portal at `whitespacews.com` that blocks them. See
[docs/FINDINGS.md](docs/FINDINGS.md) for the full survey of what is and is not
reachable remotely.

If the saved schedule runs out, emails say so explicitly and fall back to the
estimate, rather than quietly dropping garden waste.

## Garden waste

Garden waste runs on a **different day from the other bins**: Thursday,
fortnightly, against Tuesday for everything else. That is observed, not
assumed - the fixtures in `tests/` were captured from the live portal for this
property (their session token is dated `2026/03/12`) and show Garden Waste on
Thursday 12 and Thursday 26 March 2026, with Food and Recycling on the
Tuesdays between.

It also pins the zone twice over. The council's Week 1 calendar puts recycling
on the weeks of 12 and 26 January 2026, making the week of 3 August a
general-waste week in that zone - and this property had recycling on Tuesday
4 August, so it is **Week 2**. Week 2's garden fortnights begin the weeks of
9 and 23 March, whose Thursdays are exactly the two fixture dates.

The published winter suspensions (21 Dec 2026 - 1 Jan 2027, and 20 Dec 2027 -
2 Jan 2028) are encoded. A suspended collection is dropped rather than
deferred: the fortnightly parity carries straight on afterwards.

A `schedule.json` fetched from the portal overrides all of this, so real data
always wins where it is available.

## Bank holidays and Christmas

Over Christmas the council publishes a "usual day → revised day" table on its
bins page. `holidays.py` reads it and shifts collections accordingly:

```sh
python scraper.py --holidays
```

```
11 change(s) published:
  Fri 25 Dec 2026  ->  Mon 28 Dec 2026
  Tue 29 Dec 2026  ->  Wed 30 Dec 2026
  ...
```

Two things it deliberately refuses to do quietly:

- **Stale tables are rejected.** The council has been observed serving last
  year's table beside this year's, so every row's weekday is checked against
  the year it claims to cover. A row that does not match is dropped.
- **Parsing nothing in December or January is an alarm**, not a quiet "no
  changes" - the email says the dates may be wrong rather than being
  confidently a day out over Christmas.

The `Check Holiday Changes` workflow runs this weekly against the live page, so
a breakage surfaces before it matters.

## Optional: a real fetch from the portal

Everything above runs without this. But if you ever happen to be on home
broadband, a real fetch from the portal will override the derived dates, and
real data always wins:

```sh
python scraper.py --list --postcode "GU8 5QQ" --house-number 7
git add schedule.json && git commit -m "Refresh schedule" && git push
```

```
Upcoming collections (12 found):

  Tue 17 Nov  Food Waste       (tomorrow)
  Tue 17 Nov  Domestic Waste   (tomorrow)
  Thu 19 Nov  Garden Waste     (in 3 days)

Your pIndex is 1 (needed for the iPhone Shortcut).
Saved 12 collections to schedule.json, through Tue 08 Dec.
```

It is also the only way to confirm your garden-waste subscription is still
active - nothing reachable from a server can see that.

This fails with a `403` on a work VPN or any cloud machine; the council blocks
those. It needs a residential connection.

## iPhone Shortcut ("Hey Siri, when are the bins?")

iOS cannot run `scraper.py` - there is no cron and background scripts get
killed. But Shortcuts can make the requests itself, and because it runs on the
phone it uses your home wifi, which the council portal accepts. No hardware,
no server, no Gmail.

The portal is a three-step session flow and the Shortcut has to walk all three:
get a `Track` token, **bind that token to your address**, then read the schedule.
Step 4 below is easy to skip and skipping it is silent - see the warning after
the table.

First get your `pIndex`, which is fixed for your property. Run `--list` from a
laptop at home and it prints it at the bottom. Then build this in Shortcuts,
replacing `YOUR_PINDEX`, `YOUR_POSTCODE` and `YOUR_HOUSE_NUMBER`:

| # | Action | Settings |
|---|---|---|
| 1 | **Get Contents of URL** | `https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1` |
| 2 | **Match Text** | Pattern: `Track=([^&"]+)` |
| 3 | **Get Group from Matched Text** | Group `1`. Wrap in *Get First Item from List* if it returns several. |
| 4 | **Get Contents of URL** | `https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track=[group from step 3]&seq=2` |
| | ↳ Method | `POST` |
| | ↳ Request Body | **Form** - `address_postcode` = `YOUR_POSTCODE`, `address_name_number` = `YOUR_HOUSE_NUMBER` |
| 5 | **Get Contents of URL** | `https://wav-wrp.whitespacews.com/mop.php?Track=[group from step 3]&serviceID=A&seq=3&pIndex=YOUR_PINDEX` |
| 6 | **Match Text** | Pattern: `(\d{2}/\d{2}/\d{4})[\s\S]{0,300}?([A-Z][A-Za-z ]*?Collection Service)` |
| 7 | **Repeat with Each** | over the matches from step 6 |
| 8 | ↳ **Get Group from Matched Text** | Group `1` - the date |
| 9 | ↳ **Get Group from Matched Text** | Group `2` - the service |
| 10 | ↳ **Add to Variable** | e.g. `results`, combining the two |
| 11 | **Show Result** / **Speak Text** | the `results` variable |

Name it "When are the bins" and Siri will answer to that phrase.

### If it says there are no collections

You almost certainly skipped step 4, the `seq=2` POST. **`pIndex` on its own does
not identify your property** - it only picks between addresses already resolved
for that token, so the token must be bound to an address first.

Skipping it fails silently rather than erroring. `seq=3` still returns HTTP `200`
and a perfectly valid page reading *"Sorry - there are no scheduled services at
this address"*, which is easy to misread as your address genuinely having no
schedule. Measured against the real portal: without step 4 the page is ~11 KB with
one `<ul>` and zero collections; with it, ~21 KB, eleven `<ul>`s and ten
collections.

Step 4's own output is not used - it exists only for its side effect on the
session. The binding is held server-side against the `Track` token and does *not*
depend on cookies (a `seq=3` request from a cookieless session with the same token
still returns the full schedule), so it does not matter that Shortcuts will not
reliably carry cookies between *Get Contents of URL* actions.

Both regexes above were checked against real portal HTML - not just the test
fixture - and produce output identical to `parse_collections()`. Note that the
regexes being right is not enough on its own: the original version of this recipe
had correct regexes but omitted step 4, and so always returned nothing.

You *can* put this on a daily time automation, but Shortcuts automations
silently skip often enough that it is worth pairing with a real scheduled job
rather than relying on it alone.

## Scheduling

`.github/workflows/bin-reminder.yml` runs daily at 06:37 UTC and is the whole
deployment - there is nothing to install and nothing of yours to keep running.

The time is deliberately early and on an odd minute. GitHub's scheduler was
observed firing this job between 4h32m and 9h11m late every day for a week,
which was landing reminders between 18:32 and 23:11. Firing early means even
the worst drift seen still arrives in the afternoon.

`check-holidays.yml` runs weekly and prints what the council's festive table
currently says, so a parser breakage surfaces before it matters.

## Development

```sh
pip install -r requirements.txt
pytest tests/ -q
```

`api.py` is a small Flask endpoint (`/ask?q=...`) answering questions like
"when is the recycling", for a Siri shortcut. **It is currently non-functional
when hosted**: it scrapes the portal directly, so from any server it gets the
same `403` as everything else. It would work if pointed at
`scraper.resolve_due()` like the reminder is.
