# Waverley bin reminder

Emails you the evening before a bin collection.

## How it runs

The council's portal sits behind an AWS load balancer that rejects datacenter
IPs, so GitHub-hosted runners get a blanket `403` and cannot read the schedule.
The reminder therefore runs best from a machine on a home connection.

`scraper.py` tries the live portal first and falls back to a hardcoded
fortnightly cycle if it cannot reach it:

| | Live portal | Fallback |
|---|---|---|
| Food waste, recycling, domestic | yes | yes |
| Garden waste (seasonal, separate day) | yes | **no** |
| Handles bank-holiday shifts | yes | no |

Fallback emails are marked as estimates. Garden waste only works on the live
path, which is the main reason to run it from home.

## Checking it by hand

You do not need any of the hardware below to just look up your collections.
From any machine on home broadband:

```sh
pip install -r requirements.txt
python scraper.py --list --postcode "GU8 5QQ" --house-number 7
```

```
Upcoming collections (12 found):

  Tue 18 Aug  Food Waste       (tomorrow)
  Tue 18 Aug  Recycling        (tomorrow)
  Thu 20 Aug  Garden Waste     (in 3 days)
```

No email is sent and no Gmail setup is needed. `--postcode` and
`--house-number` fall back to the environment variables if omitted.

This will fail with a `403` on a work VPN or a cloud machine - the council
blocks those. Run it from home.

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

## Recommended setup: Raspberry Pi

A Pi Zero 2 W (~£15) is enough — it draws under a watt and runs silently.

1. Flash **Raspberry Pi OS Lite (64-bit)**. The 32-bit build is fine here,
   but 64-bit keeps the option of a GitHub runner open later.
   Enable SSH and your wifi in the Imager's advanced settings.

2. On the Pi:

   ```sh
   git clone https://github.com/Drivad/bin-reminder.git
   cd bin-reminder
   sudo ./deploy/install.sh
   ```

3. Fill in your address and Gmail credentials:

   ```sh
   sudo nano /etc/bin-reminder.env
   ```

   `GMAIL_APP_PASSWORD` must be a Google [app password](https://myaccount.google.com/apppasswords),
   not your account password.

4. Test it, without waiting for the timer:

   ```sh
   sudo systemctl start bin-reminder.service
   journalctl -u bin-reminder.service -n 30 --no-pager
   ```

The timer fires at 18:00 **local** time, so BST and GMT are handled
automatically. If the Pi is off at 18:00 it runs as soon as it is back up.

Change the time by editing `OnCalendar` in
`/etc/systemd/system/bin-reminder.timer`, then `sudo systemctl daemon-reload`.

To update later: `git pull && sudo ./deploy/install.sh`.

## GitHub Actions (backup)

`.github/workflows/bin-reminder.yml` still runs daily as a safety net, but from
GitHub's runners it can only ever send the estimated fallback, and its schedule
can drift by hours. Disable it in the Actions tab once the Pi is working.

## Development

```sh
pip install -r requirements.txt
pytest tests/ -q
```

`api.py` is a small Flask endpoint (`/ask?q=...`) that answers questions like
"when is the recycling" for use from a Siri shortcut.
