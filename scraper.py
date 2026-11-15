import argparse
import datetime
import json
import os
import pathlib
import re
import smtplib
import sys

import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

def extract_track_token(html: str) -> str:
    """Extract the Track session token from the seq=1 page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", {"data-form-title": "Property Lookup Form"})
    if not form:
        raise ValueError("Track token not found: Property Lookup Form not in page")
    action = form.get("action", "")
    match = re.search(r"Track=([^&]+)", action)
    if not match:
        raise ValueError("Track token not found: no Track param in form action")
    return match.group(1)

def find_pindex(html: str, house_number: str) -> str:
    """Find the pIndex for a given house number in the seq=2 address list HTML."""
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(rf"^{re.escape(house_number)},")
    for link in soup.find_all("a", {"aria-label": True}):
        if pattern.match(link["aria-label"].strip()):
            href = link.get("href", "")
            match = re.search(r"pIndex=(\d+)", href)
            if match:
                return match.group(1)
    raise ValueError(f"Address not found for house number '{house_number}'")

def parse_collections(html: str) -> list[tuple[datetime.date, str]]:
    """Parse collection entries from seq=3 HTML. Returns list of (date, service_name)."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    date_pattern = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    # Each collection is a <ul> block with tabindex="0" <li> items
    for u1 in soup.find_all("ul"):
        texts = [
            li.get_text(strip=True)
            for li in u1.find_all("li", {"tabindex": "0"}, recursive=False)
        ]
        # Find a date-shaped string and the service name (last text item)
        date_str = next((t for t in texts if date_pattern.match(t)), None)
        service = texts[-1] if texts else None
        if date_str and service and not date_pattern.match(service):
            try:
                date = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
                results.append((date, service))
            except ValueError:
                continue
    return results

def collections_tomorrow(
    entries: list[tuple[datetime.date, str]],
    today: datetime.date,
) -> list[str]:
    """Return service names for collections scheduled for tomorrow."""
    tomorrow = today + datetime.timedelta(days=1)
    return [service for date, service in entries if date == tomorrow]

def compose_email(
    services: list[str],
    tomorrow: datetime.date,
    sender: str,
    recipient: str,
    note: str = None,
) -> MIMEText:
    """Compose a plain-text reminder email."""
    date_str = tomorrow.strftime("%A %-d %B")  # e.g. "Tuesday 17 March"
    service_lines = "\n".join(f"- {s}" for s in services)
    footer = f"{note}\n\n— Waverley bin bot" if note else "— Waverley bin bot"
    body = (
        f"Tomorrow's collections ({date_str}):\n"
        f"{service_lines}\n\n"
        f"{footer}"
    )
    # Specify UTF-8 charset directly in MIMEText
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "Bin reminder: put out your bins tonight"
    msg["From"] = sender
    msg["To"] = recipient
    return msg

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def fetch_html(url: str, method: str = "get", data: dict = None, timeout: int = 15) -> str:
    """Fetch URL, raise on HTTP error, return HTML text."""
    if method == "post":
        resp = requests.post(url, data=data, headers=_HEADERS, timeout=timeout)
    else:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def send_email(msg: MIMEText, sender: str, app_password: str) -> None:
    """Send email via Gmail SMTP."""
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.send_message(msg)

# The portal hands back several weeks of collections at once, so it only needs
# visiting occasionally from a residential connection. Everything in between
# reads this saved copy, which works anywhere - CI included.
SCHEDULE_FILE = pathlib.Path(__file__).with_name("schedule.json")

# Warn this many days before the saved schedule runs out, so there is time to
# refresh before it silently degrades to the fortnightly estimate.
CACHE_WARN_DAYS = 14


def save_schedule(
    entries: list[tuple[datetime.date, str]],
    path: pathlib.Path = SCHEDULE_FILE,
    today: datetime.date = None,
) -> None:
    """Write collections to disk so later runs need no network."""
    today = today or datetime.date.today()
    payload = {
        "refreshed": today.isoformat(),
        "collections": [
            {"date": d.isoformat(), "service": s} for d, s in sorted(entries)
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def load_schedule(
    path: pathlib.Path = SCHEDULE_FILE,
) -> tuple[list[tuple[datetime.date, str]], datetime.date]:
    """Read the saved schedule. Returns ([], None) if missing or unreadable.

    Never raises: a corrupt cache must degrade to the estimate, not crash the
    nightly job.
    """
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return [], None

    entries = []
    for row in payload.get("collections", []):
        try:
            entries.append((datetime.date.fromisoformat(row["date"]), row["service"]))
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed rows rather than losing the whole cache

    try:
        refreshed = datetime.date.fromisoformat(payload["refreshed"])
    except (KeyError, TypeError, ValueError):
        refreshed = None

    return sorted(entries), refreshed


def schedule_covers(entries: list[tuple[datetime.date, str]], date: datetime.date) -> bool:
    """True if the saved schedule extends far enough to be trusted for `date`.

    A cache whose last entry is before `date` cannot distinguish "no collection
    that day" from "ran out of data", so it must not be used.
    """
    return bool(entries) and max(d for d, _ in entries) >= date


# Anchor: a known Recycling Tuesday. The fortnightly cycle is:
#   anchor + 0, 14, 28, ... days → Food Waste + Recycling
#   anchor + 7, 21, 35, ... days → Food Waste + Domestic Waste
_RECYCLING_ANCHOR = datetime.date(2026, 8, 4)


def scheduled_collections(date: datetime.date) -> list[str]:
    """Return collection service names for a given date using hardcoded fortnightly schedule."""
    if date.weekday() != 1:  # 1 = Tuesday
        return []
    services = ["Food Waste Collection Service"]
    if (date - _RECYCLING_ANCHOR).days % 14 == 0:
        services.append("Recycling Collection Service")
    else:
        services.append("Domestic Waste Collection Service")
    return services


def lookup_property(postcode: str, house_number: str) -> tuple[str, str]:
    """Return (track_token, pindex) for an address. Steps 1 and 2 of the scrape.

    The pindex is stable for a property; only the token changes per session.
    """
    seq1_html = fetch_html("https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1")
    token = extract_track_token(seq1_html)

    seq2_url = f"https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track={token}&seq=2"
    seq2_html = fetch_html(seq2_url, method="post", data={
        "address_postcode": postcode,
        "address_name_number": house_number,
    })
    return token, find_pindex(seq2_html, house_number)


def fetch_collections(token: str, pindex: str) -> list[tuple[datetime.date, str]]:
    """Step 3 of the scrape: read the schedule for an already-resolved property."""
    seq3_url = (
        f"https://wav-wrp.whitespacews.com/mop.php"
        f"?Track={token}&serviceID=A&seq=3&pIndex={pindex}"
    )
    return parse_collections(fetch_html(seq3_url))


def scrape_schedule(
    postcode: str = None,
    house_number: str = None,
) -> list[tuple[datetime.date, str]]:
    """Run the full 3-step portal scrape. Raises if the portal is unreachable."""
    postcode = postcode or os.environ["POSTCODE"]
    house_number = house_number or os.environ["HOUSE_NUMBER"]
    token, pindex = lookup_property(postcode, house_number)
    return fetch_collections(token, pindex)


def list_collections(postcode: str = None, house_number: str = None) -> int:
    """Print upcoming collections. Returns a process exit code."""
    try:
        postcode = postcode or os.environ["POSTCODE"]
        house_number = house_number or os.environ["HOUSE_NUMBER"]
        token, pindex = lookup_property(postcode, house_number)
        entries = fetch_collections(token, pindex)
    except Exception as e:  # noqa: BLE001 - surface the cause to the user
        print(f"Could not reach the council portal: {type(e).__name__}: {e}", file=sys.stderr)
        print(
            "\nIf this says 403, you are on a connection the council blocks "
            "(most likely a datacenter or VPN). Try again from home broadband.",
            file=sys.stderr,
        )
        return 1

    if not entries:
        print("The portal returned no collections for that address.")
        print("Double-check the postcode and house number.")
        return 1

    today = datetime.date.today()
    print(f"Upcoming collections ({len(entries)} found):\n")
    for date, service in sorted(entries):
        days = (date - today).days
        if days == 0:
            when = "today"
        elif days == 1:
            when = "tomorrow"
        elif days < 0:
            continue  # already been and gone
        else:
            when = f"in {days} days"
        print(f"  {date.strftime('%a %d %b')}  {short_name(service):<16} ({when})")

    # The pindex is fixed for a property, so it can be hardcoded into an iOS
    # Shortcut to skip the address lookup entirely. See README.
    print(f"\nYour pIndex is {pindex} (needed for the iPhone Shortcut).")

    # Always save what we fetched: this is the whole point of running from home.
    save_schedule(entries)
    last = max(d for d, _ in entries)
    print(f"Saved {len(entries)} collections to {SCHEDULE_FILE.name}, through {last:%a %d %b}.")
    print("Commit and push it so the nightly reminder uses it:")
    print(f"    git add {SCHEDULE_FILE.name} && git commit -m 'Refresh schedule' && git push")
    return 0


def short_name(service: str) -> str:
    """Strip the 'Collection Service' suffix for readable output."""
    return re.sub(r"\s*collection service\s*$", "", service, flags=re.IGNORECASE).strip()


def resolve_due(
    today: datetime.date,
) -> tuple[list[str], str]:
    """Work out tomorrow's collections. Returns (services, note_for_email).

    Three sources, best first:
      1. the saved schedule, if it reaches far enough ahead - real data,
         garden waste included, and needs no network
      2. a live scrape, which only works from a residential connection; the
         result is saved so later runs get source 1
      3. the fortnightly estimate, which cannot model garden waste
    """
    tomorrow = today + datetime.timedelta(days=1)

    cached, refreshed = load_schedule()
    if schedule_covers(cached, tomorrow):
        due = collections_tomorrow(cached, today)
        runs_out = max(d for d, _ in cached)
        days_left = (runs_out - today).days
        print(
            f"Using saved schedule ({len(cached)} collections, "
            f"refreshed {refreshed or 'unknown'}, good through {runs_out})."
        )
        note = None
        if days_left <= CACHE_WARN_DAYS:
            note = (
                f"Heads up: the saved schedule runs out in {days_left} days "
                f"({runs_out:%a %d %b}). Run 'python scraper.py --list' from home "
                "and push the result, or garden waste will drop off."
            )
            print(f"WARNING: schedule runs out in {days_left} days.", file=sys.stderr)
        return due, note

    if cached:
        print(
            f"Saved schedule ran out on {max(d for d, _ in cached)}; it cannot "
            "cover tomorrow.",
            file=sys.stderr,
        )
    else:
        print("No saved schedule found.", file=sys.stderr)

    # Nothing cached for tomorrow - try live, in case we happen to be on a
    # connection the portal accepts. Saves the result if it works.
    try:
        entries = scrape_schedule()
        if not entries:
            raise ValueError("portal returned no collections")
        save_schedule(entries, today=today)
        print(f"Fetched and saved {len(entries)} collections from the portal.")
        return collections_tomorrow(entries, today), None
    except Exception as e:  # noqa: BLE001 - any failure falls back to maths
        print(f"Live lookup unavailable ({type(e).__name__}: {e}).", file=sys.stderr)

    print("Falling back to the fortnightly estimate.", file=sys.stderr)
    return scheduled_collections(tomorrow), (
        "(Estimated from the fortnightly cycle - garden waste and bank-holiday "
        "changes are NOT included. Run 'python scraper.py --list' from home and "
        "push the result to fix this.)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Waverley bin collection reminder.",
        epilog="With no arguments, emails a reminder if a collection is due tomorrow.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="fetch from the portal, print upcoming collections and save them "
        "to schedule.json; sends no email. Run this from home broadband.",
    )
    parser.add_argument("--postcode", help="overrides the POSTCODE environment variable")
    parser.add_argument(
        "--house-number", help="overrides the HOUSE_NUMBER environment variable"
    )
    args = parser.parse_args()

    if args.list:
        sys.exit(list_collections(args.postcode, args.house_number))

    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    today = datetime.datetime.now(datetime.timezone.utc).date()
    tomorrow = today + datetime.timedelta(days=1)
    due_tomorrow, note = resolve_due(today)

    if not due_tomorrow:
        print("No collections due tomorrow. Nothing to do.")
        sys.exit(0)

    msg = compose_email(due_tomorrow, tomorrow, gmail_address, recipient, note=note)
    send_email(msg, gmail_address, gmail_app_password)
    print(f"Reminder sent for: {', '.join(due_tomorrow)}")

if __name__ == "__main__":
    main()