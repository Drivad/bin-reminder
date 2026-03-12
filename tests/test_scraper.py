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
