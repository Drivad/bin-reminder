# Handoff: verify the bin reminder against a real address

Paste this to a Claude instance running on a machine at home, or point it at
this file in the repo. It is self-contained - no prior conversation needed.

## What this project is

A bin collection reminder for Waverley Borough Council (Surrey, UK). It scrapes
the council's WhiteSpace WRP portal for a single address and emails the user the
evening before a collection.

Repo: https://github.com/Drivad/bin-reminder

## The one constraint that matters

**The council portal blocks datacenter IPs.** `wav-wrp.whitespacews.com` sits
behind an AWS load balancer that returns a bare `403 Forbidden` to anything
that is not a residential connection.

This was diagnosed properly, not guessed. A probe tried five strategies from
GitHub Actions - bare request, `User-Agent` only, full browser header set, the
site root, and a cookie-bearing session with `Referer` - and all five returned
**byte-identical** 403s with `server: awselb/2.0`, no cookies set and no
challenge page. The block is on source IP, applied before the application sees
the request. No header, session or user-agent change can get through it.

**So:** run this from home broadband. It will fail on a corporate VPN, a cloud
box, or a datacenter connection. If the work laptop is tunnelling all traffic
through a company VPN, drop off the VPN first.

## The task

Nobody has ever successfully run this against the real address. Every fix so far
was inferred from error logs, never from a successful fetch. Confirm it works:

```sh
git clone https://github.com/Drivad/bin-reminder.git
cd bin-reminder
pip install -r requirements.txt
python scraper.py --list --postcode "<POSTCODE>" --house-number "<NUMBER>"
```

Ask the user for their postcode and house number. `--house-number` is just the
number, e.g. `7`.

No email is sent by `--list` and no Gmail credentials are needed.

## What success looks like

```
Upcoming collections (12 found):

  Tue 22 Sep  Food Waste       (in 5 days)
  Tue 22 Sep  Recycling        (in 5 days)
  Thu 24 Sep  Garden Waste     (in 7 days)

Your pIndex is 1 (needed for the iPhone Shortcut).
```

Report back to the user: the full output, and in particular **whether Garden
Waste appears**. Garden waste runs on a separate seasonal schedule and is the
main thing the offline fallback cannot cover, so its presence is the real test.
Also note the `pIndex` - it is fixed for the property and is needed to build an
iOS Shortcut.

## If it fails

**`403 Client Error`** - you are on a blocked connection. Check for a corporate
VPN and retry from plain home wifi. This is not a code bug.

**`The portal returned no collections`** - the scrape succeeded but parsing
found nothing. This exact bug existed for months: `parse_collections()` in
`scraper.py` searched for `<u1>` tags (letter u, digit one) when the portal
emits standard `<ul>`. It is fixed, but the portal template may have moved
again. Dump the HTML and inspect:

```python
from scraper import lookup_property, fetch_html
token, pindex = lookup_property("<POSTCODE>", "<NUMBER>")
url = f"https://wav-wrp.whitespacews.com/mop.php?Track={token}&serviceID=A&seq=3&pIndex={pindex}"
html = fetch_html(url)
open("seq3.html", "w").write(html)
```

Then compare against the fixture in `tests/test_scraper.py` (`FAKE_SEQ3_HTML`),
which documents the structure the parser expects: a `<ul>` per collection
containing `<li tabindex="0">` items, one holding a `DD/MM/YYYY` date and one
the service name.

**`Address not found for house number`** - step 2 matched no address. The
matcher anchors on `^<number>,` against each link's `aria-label`, so flats or
named houses may need a different form. Dump the seq=2 HTML and look at the
actual `aria-label` values.

**`Track token not found`** - the portal changed its lookup form. Check
`extract_track_token()`, which expects a `<form data-form-title="Property
Lookup Form">` whose `action` carries a `Track=` parameter.

## How the code is laid out

| Function | Does |
|---|---|
| `lookup_property()` | Steps 1-2: get session token, resolve address to `pIndex` |
| `fetch_collections()` | Step 3: fetch and parse the schedule |
| `scrape_schedule()` | All three, the normal entry point |
| `scheduled_collections()` | Offline fallback: fortnightly maths, no network |
| `main()` | Tries live, falls back to maths, emails if due tomorrow |

The fallback is anchored to a known real collection: **Tue 4 Aug 2026 was Food
Waste + Recycling**. Food waste is weekly; recycling and domestic waste
alternate fortnightly. It cannot model garden waste or bank-holiday shifts, and
emails sent from it are marked as estimates.

## Working on the repo

```sh
python -m pytest tests/ -q     # 40 tests, all should pass
```

Develop on a branch, not `main`. If you change parsing, add a fixture to
`tests/test_scraper.py` reflecting the real HTML you captured - that is how the
`<u1>`/`<ul>` bug went unnoticed, because the fixture had the same typo as the
code and the tests passed happily against it.

## Useful follow-ups once it works

- Feed the confirmed schedule back so the fallback anchor can be re-verified.
- Build the iOS Shortcut - recipe is in the README, needs the `pIndex`.
- Set up the nightly job: `sudo ./deploy/install.sh` on any always-on Linux box
  at home (systemd timer, fires 18:00 local).
