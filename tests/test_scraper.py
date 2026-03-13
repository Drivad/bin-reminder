import pytest

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


def test_extract_track_token_raises_on_missing_form():
    with pytest.raises(ValueError, match="Property Lookup Form not in page"):
        extract_track_token("<html><body>no form here</body></html>")


def test_extract_track_token_raises_on_missing_param():
    with pytest.raises(ValueError, match="no Track param in form action"):
        extract_track_token(
            '<html><body><form data-form-title="Property Lookup Form" action="/foo"></form></body></html>'
        )


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


import datetime
from scraper import parse_collections


FAKE_SEQ3_HTML = """
<html><body>
<u1 class="displayinlineblock">
  <li><img alt="Collection Item"></li>
  <li tabindex="0"><p class="colordarkblue">12/03/2026</p></li>
  <li tabindex="0"><p class="colordarkblue">Garden Waste Collection Service</p></li>
</u1>
<u1 class="displayinlineblock">
  <li><img alt="Collection Item"></li>
  <li tabindex="0"><p class="colordarkblue">17/03/2026</p></li>
  <li tabindex="0"><p class="colordarkblue">Food Waste Collection Service</p></li>
</u1>
<u1 class="displayinlineblock">
  <li><img alt="Collection Item"></li>
  <li tabindex="0"><p class="colordarkblue">17/03/2026</p></li>
  <li tabindex="0"><p class="colordarkblue">Recycling Collection Service</p></li>
</u1>
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
