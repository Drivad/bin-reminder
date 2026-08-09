import datetime
import os
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
) -> MIMEText:
    """Compose a plain-text reminder email."""
    date_str = tomorrow.strftime("%A %-d %B")  # e.g. "Tuesday 17 March"
    service_lines = "\n".join(f"- {s}" for s in services)
    body = (
        f"Tomorrow's collections ({date_str}):\n"
        f"{service_lines}\n\n"
        f"— Waverley bin bot"
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


def main() -> None:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    today = datetime.datetime.now(datetime.timezone.utc).date()
    tomorrow = today + datetime.timedelta(days=1)
    due_tomorrow = scheduled_collections(tomorrow)

    if not due_tomorrow:
        print("No collections due tomorrow. Nothing to do.")
        sys.exit(0)

    msg = compose_email(due_tomorrow, tomorrow, gmail_address, recipient)
    send_email(msg, gmail_address, gmail_app_password)
    print(f"Reminder sent for: {', '.join(due_tomorrow)}")

if __name__ == "__main__":
    main()