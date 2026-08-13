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
