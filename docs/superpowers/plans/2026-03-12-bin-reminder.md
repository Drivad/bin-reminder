# Bin Collection Email Reminder Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub Actions workflow that scrapes Waverley Council's bin collection website nightly and sends a Gmail reminder the evening before any scheduled collection.

**Architecture:** A single Python script (`scraper.py`) performs three HTTP requests to extract the bin schedule for a given address, checks if any collection is tomorrow, and sends email via Gmail SMTP. A GitHub Actions workflow runs the script on a daily cron schedule with secrets injected as environment variables.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4` (html.parser), `smtplib` + `email.mime.text` (stdlib), GitHub Actions

---

## File Structure

```
bin-reminder/
├── .github/
│   └── workflows/
│       └── bin-reminder.yml       # GH Actions: cron trigger, secrets, run scraper
├── scraper.py                     # All scraping + email logic
├── tests/
│   └── test_scraper.py            # Unit tests with mocked HTTP
└── requirements.txt               # requests, beautifulsoup4
```

---

## Chunk 1: Scraper core

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_scraper.py` (empty for now)
- Create: `scraper.py` (empty for now)

- [ ] **Step 1: Create requirements.txt**

```
requests
beautifulsoup4
pytest
```

- [ ] **Step 2: Create empty placeholder files**

```bash
mkdir -p tests
touch tests/__init__.py tests/test_scraper.py scraper.py
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/ scraper.py
git commit -m "chore: scaffold project structure"
```

---

### Task 2: Track token extraction

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `scraper.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scraper.py`:

```python
from scraper import extract_track_token


FAKE_SEQ1_HTML = """
<html><body>
<form data-form-title="Property Lookup Form"
      action="https://wav-wrp.whitespacews.com/mop.php?serviceID=A&amp;Track=2026/03/12/QDFR1EH53W&amp;seq=2"
      method="post">
</form>
</body></html>
"""


def test_extract_track_token_returns_token():
    token = extract_track_token(FAKE_SEQ1_HTML)
    assert token == "2026/03/12/QDFR1EH53W"


def test_extract_track_token_raises_on_missing():
    with pytest.raises(ValueError, match="Track token not found"):
        extract_track_token("<html><body>no form here</body></html>")
```

Also add `import pytest` at the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scraper.py -v
```

Expected: `ImportError` or `FAILED` — `extract_track_token` not yet defined.

- [ ] **Step 3: Implement `extract_track_token` in scraper.py**

```python
import re
from bs4 import BeautifulSoup


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py requirements.txt
git commit -m "feat: extract Track token from seq=1 HTML"
```

---

### Task 3: Address lookup (find pIndex)

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
from scraper import find_pindex


FAKE_SEQ2_HTML = """
<html><body>
<ul>
  <li><a href="mop.php?Track=2026/03/12/QDFR1EH53W&serviceID=A&seq=3&pIndex=1"
         aria-label="7, GREEN LANE, FARNCOMBE, GODALMING, SURREY, ..">
    7, GREEN LANE, FARNCOMBE, GODALMING, SURREY
  </a></li>
  <li><a href="mop.php?Track=2026/03/12/QDFR1EH53W&serviceID=A&seq=3&pIndex=2"
         aria-label="17, GREEN LANE, FARNCOMBE, GODALMING, SURREY, ..">
    17, GREEN LANE, FARNCOMBE, GODALMING, SURREY
  </a></li>
  <li><a href="mop.php?Track=2026/03/12/QDFR1EH53W&serviceID=A&seq=3&pIndex=3"
         aria-label="70, GREEN LANE, FARNCOMBE, GODALMING, SURREY, ..">
    70, GREEN LANE, FARNCOMBE, GODALMING, SURREY
  </a></li>
</ul>
</body></html>
"""


def test_find_pindex_exact_match():
    assert find_pindex(FAKE_SEQ2_HTML, "7") == "1"


def test_find_pindex_does_not_match_partial():
    # "7" should NOT match "17" or "70"
    assert find_pindex(FAKE_SEQ2_HTML, "7") == "1"
    assert find_pindex(FAKE_SEQ2_HTML, "17") == "2"
    assert find_pindex(FAKE_SEQ2_HTML, "70") == "3"


def test_find_pindex_raises_on_no_match():
    with pytest.raises(ValueError, match="Address not found"):
        find_pindex(FAKE_SEQ2_HTML, "99")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_find_pindex_exact_match -v
```

Expected: `ImportError` — `find_pindex` not defined.

- [ ] **Step 3: Implement `find_pindex` in scraper.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: find pIndex by house number from address list"
```

---

### Task 4: Parse collection schedule

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
import datetime
from scraper import parse_collections


FAKE_SEQ3_HTML = """
<html><body>
<ul class="displayinlineblock">
  <li tabIndex="0"><p class="colordarkblue">Thursday</p></li>
  <li tabIndex="0"><p class="colordarkblue">12/03/2026</p></li>
  <li tabIndex="0"><p class="colordarkblue">Garden Waste Collection Service</p></li>
</ul>
<hr>
<ul class="displayinlineblock">
  <li tabIndex="0"><p class="colordarkblue">Tuesday</p></li>
  <li tabIndex="0"><p class="colordarkblue">17/03/2026</p></li>
  <li tabIndex="0"><p class="colordarkblue">Food Waste Collection Service</p></li>
</ul>
<hr>
<ul class="displayinlineblock">
  <li tabIndex="0"><p class="colordarkblue">Tuesday</p></li>
  <li tabIndex="0"><p class="colordarkblue">17/03/2026</p></li>
  <li tabIndex="0"><p class="colordarkblue">Recycling Collection Service</p></li>
</ul>
</body></html>
"""


def test_parse_collections_returns_all_entries():
    entries = parse_collections(FAKE_SEQ3_HTML)
    assert len(entries) == 3


def test_parse_collections_entry_structure():
    entries = parse_collections(FAKE_SEQ3_HTML)
    assert entries[0] == (datetime.date(2026, 3, 12), "Garden Waste Collection Service")
    assert entries[1] == (datetime.date(2026, 3, 17), "Food Waste Collection Service")


def test_parse_collections_empty_page():
    assert parse_collections("<html><body></body></html>") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_parse_collections_returns_all_entries -v
```

Expected: `ImportError` — `parse_collections` not defined.

- [ ] **Step 3: Implement `parse_collections` in scraper.py**

```python
def parse_collections(html: str) -> list[tuple[datetime.date, str]]:
    """Parse collection entries from seq=3 HTML. Returns list of (date, service_name)."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    date_pattern = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    # Each collection is a <ul> block with tabIndex="0" <li> items
    for ul in soup.find_all("ul"):
        texts = [
            li.get_text(strip=True)
            for li in ul.find_all("li", {"tabIndex": "0"})
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
```

Also add `import datetime` at the top of `scraper.py`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: parse collection schedule from seq=3 HTML"
```

---

### Task 5: Tomorrow filter

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
from scraper import collections_tomorrow


def test_collections_tomorrow_finds_match():
    today = datetime.date(2026, 3, 16)  # Monday
    entries = [
        (datetime.date(2026, 3, 17), "Food Waste Collection Service"),
        (datetime.date(2026, 3, 17), "Recycling Collection Service"),
        (datetime.date(2026, 3, 24), "Domestic Waste Collection Service"),
    ]
    result = collections_tomorrow(entries, today)
    assert result == [
        "Food Waste Collection Service",
        "Recycling Collection Service",
    ]


def test_collections_tomorrow_no_match():
    today = datetime.date(2026, 3, 16)
    entries = [(datetime.date(2026, 3, 24), "Domestic Waste Collection Service")]
    assert collections_tomorrow(entries, today) == []


def test_collections_tomorrow_empty_input():
    assert collections_tomorrow([], datetime.date(2026, 3, 16)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_collections_tomorrow_finds_match -v
```

Expected: `ImportError` — `collections_tomorrow` not defined.

- [ ] **Step 3: Implement `collections_tomorrow` in scraper.py**

```python
def collections_tomorrow(
    entries: list[tuple[datetime.date, str]],
    today: datetime.date,
) -> list[str]:
    """Return service names for collections scheduled for tomorrow."""
    tomorrow = today + datetime.timedelta(days=1)
    return [service for date, service in entries if date == tomorrow]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: filter collections due tomorrow"
```

---

## Chunk 2: Email, main orchestration, and GitHub Actions

### Task 6: Email composition

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
import email as email_module
from scraper import compose_email


def test_compose_email_subject():
    msg = compose_email(
        services=["Recycling Collection Service", "Food Waste Collection Service"],
        tomorrow=datetime.date(2026, 3, 17),
        sender="bot@gmail.com",
        recipient="me@gmail.com",
    )
    assert msg["Subject"] == "Bin reminder: put out your bins tonight"


def test_compose_email_recipient():
    msg = compose_email(
        services=["Garden Waste Collection Service"],
        tomorrow=datetime.date(2026, 3, 26),
        sender="bot@gmail.com",
        recipient="me@gmail.com",
    )
    assert msg["To"] == "me@gmail.com"
    assert msg["From"] == "bot@gmail.com"


def test_compose_email_body_contains_services():
    msg = compose_email(
        services=["Recycling Collection Service"],
        tomorrow=datetime.date(2026, 3, 17),
        sender="bot@gmail.com",
        recipient="me@gmail.com",
    )
    body = msg.get_payload()
    assert "Recycling Collection Service" in body
    assert "Tuesday 17 March" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scraper.py::test_compose_email_subject -v
```

Expected: `ImportError` — `compose_email` not defined.

- [ ] **Step 3: Implement `compose_email` in scraper.py**

```python
from email.mime.text import MIMEText


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
    msg = MIMEText(body)
    msg["Subject"] = "Bin reminder: put out your bins tonight"
    msg["From"] = sender
    msg["To"] = recipient
    return msg
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: compose reminder email"
```

---

### Task 7: Main orchestration

**Files:**
- Modify: `scraper.py`

This task wires everything together in a `main()` function. No new unit tests (HTTP calls are integration concerns — tested manually via `workflow_dispatch`).

- [ ] **Step 1: Add `main()` to scraper.py**

Append to `scraper.py`:

```python
import os
import smtplib
import sys
import requests


def fetch_html(url: str, method: str = "get", data: dict = None, timeout: int = 15) -> str:
    """Fetch URL, raise on HTTP error, return HTML text."""
    if method == "post":
        resp = requests.post(url, data=data, timeout=timeout)
    else:
        resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def send_email(msg: MIMEText, sender: str, app_password: str) -> None:
    """Send email via Gmail SMTP."""
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.send_message(msg)


def main() -> None:
    postcode = os.environ["POSTCODE"]
    house_number = os.environ["HOUSE_NUMBER"]
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    # Step 1: get Track token
    seq1_html = fetch_html("https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1")
    token = extract_track_token(seq1_html)

    # Step 2: POST postcode, find pIndex
    seq2_url = f"https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track={token}&seq=2"
    seq2_html = fetch_html(seq2_url, method="post", data={
        "address_postcode": postcode,
        "address_name_number": house_number,
    })
    pindex = find_pindex(seq2_html, house_number)

    # Step 3: fetch collection schedule
    seq3_url = (
        f"https://wav-wrp.whitespacews.com/mop.php"
        f"?Track={token}&serviceID=A&seq=3&pIndex={pindex}"
    )
    seq3_html = fetch_html(seq3_url)
    entries = parse_collections(seq3_html)

    # Check for tomorrow
    today = datetime.datetime.utcnow().date()
    due_tomorrow = collections_tomorrow(entries, today)

    if not due_tomorrow:
        print("No collections due tomorrow. Nothing to do.")
        sys.exit(0)

    # Send reminder
    tomorrow = today + datetime.timedelta(days=1)
    msg = compose_email(due_tomorrow, tomorrow, gmail_address, recipient)
    send_email(msg, gmail_address, gmail_app_password)
    print(f"Reminder sent for: {', '.join(due_tomorrow)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run existing tests to confirm nothing broken**

```bash
pytest tests/test_scraper.py -v
```

Expected: all PASSED.

- [ ] **Step 3: Commit**

```bash
git add scraper.py
git commit -m "feat: main orchestration — wire scraper, email, env vars"
```

---

### Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/bin-reminder.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Bin Collection Reminder

on:
  schedule:
    - cron: '0 19 * * *'  # 7pm UTC daily (may run up to ~60 min late)
  workflow_dispatch:        # allows manual trigger for testing

jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run bin reminder
        run: python scraper.py
        env:
          POSTCODE: ${{ secrets.POSTCODE }}
          HOUSE_NUMBER: ${{ secrets.HOUSE_NUMBER }}
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/
git commit -m "feat: add GitHub Actions cron workflow"
```

---

### Task 9: Create GitHub repo and push

- [ ] **Step 1: Create the repo on GitHub**

```bash
gh repo create Drivad/bin-reminder --public --description "Waverley bin collection email reminder" --source=. --remote=origin --push
```

Expected output: repo created at `https://github.com/Drivad/bin-reminder`, all commits pushed.

- [ ] **Step 2: Add GitHub Actions secrets**

Run each of these (you'll be prompted for the value):

```bash
gh secret set POSTCODE --repo Drivad/bin-reminder
gh secret set HOUSE_NUMBER --repo Drivad/bin-reminder
gh secret set GMAIL_ADDRESS --repo Drivad/bin-reminder
gh secret set GMAIL_APP_PASSWORD --repo Drivad/bin-reminder
gh secret set RECIPIENT_EMAIL --repo Drivad/bin-reminder
```

Values to enter:
- `POSTCODE`: your full postcode (e.g. `GU7 3SN`)
- `HOUSE_NUMBER`: your house number (e.g. `7`)
- `GMAIL_ADDRESS`: your Gmail address
- `GMAIL_APP_PASSWORD`: a Google app password — generate one at https://myaccount.google.com/apppasswords (requires 2FA enabled)
- `RECIPIENT_EMAIL`: email address to receive reminders (can be same as Gmail)

- [ ] **Step 3: Trigger a test run**

```bash
gh workflow run bin-reminder.yml --repo Drivad/bin-reminder
```

- [ ] **Step 4: Watch the run**

```bash
gh run watch --repo Drivad/bin-reminder
```

Expected: job completes green. Check your inbox — if today+1 has a collection, you'll get an email. If not, the log will say "No collections due tomorrow."

- [ ] **Step 5: Verify secrets are set**

```bash
gh secret list --repo Drivad/bin-reminder
```

Expected: 5 secrets listed.
