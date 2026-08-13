import re
import datetime
import os
import sys

from scraper import (
    fetch_html,
    extract_track_token,
    find_pindex,
    parse_collections,
    short_name,  # re-exported: strips the "Collection Service" suffix
)


def _week_range(today: datetime.date, offset_weeks: int = 0):
    """Return (monday, sunday) for the week containing today, offset by N weeks."""
    monday = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(weeks=offset_weeks)
    sunday = monday + datetime.timedelta(days=6)
    return monday, sunday


# Each tuple: (keyword_to_match_in_query, display_name_to_match_in_service_string)
# display_name is used (not keyword) so synonyms like "rubbish"→"Domestic Waste" work correctly
_SERVICE_KEYWORDS = [
    ("garden", "Garden Waste"),
    ("recycling", "Recycling"),
    ("food", "Food Waste"),
    ("domestic", "Domestic Waste"),
    ("rubbish", "Domestic Waste"),
    ("general", "Domestic Waste"),
]


def resolve_intent(
    q: str,
    collections: list[tuple[datetime.date, str]],
    today: datetime.date = None,
) -> str:
    """Keyword-match q against bin schedule and return a spoken response."""
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()

    q_lower = q.lower()

    # Priority 1: this week
    if "this week" in q_lower:
        monday, sunday = _week_range(today, 0)
        entries = [(d, s) for d, s in collections if monday <= d <= sunday]
        if not entries:
            return "There are no collections this week."
        parts = [f"{short_name(s)} on {d.strftime('%A %-d %B')}" for d, s in entries]
        return f"This week's collections: {', '.join(parts)}."

    # Priority 2: next week
    if "next week" in q_lower:
        monday, sunday = _week_range(today, 1)
        entries = [(d, s) for d, s in collections if monday <= d <= sunday]
        if not entries:
            return "There are no collections next week."
        parts = [f"{short_name(s)} on {d.strftime('%A %-d %B')}" for d, s in entries]
        return f"Next week's collections: {', '.join(parts)}."

    # Priorities 3-6: service-specific keywords
    for keyword, display_name in _SERVICE_KEYWORDS:
        if keyword in q_lower:
            matches = [(d, s) for d, s in collections if display_name.lower() in s.lower()]
            if not matches:
                return f"There are no upcoming {display_name} collections in the schedule."
            d, s = matches[0]
            return f"Your next {short_name(s)} collection is {d.strftime('%A %-d %B')}."

    # Priority 7: default — next upcoming collection(s)
    if not collections:
        return "There are no upcoming collections in the schedule."
    next_date = min(d for d, s in collections)
    services = [s for d, s in collections if d == next_date]
    names = [short_name(s) for s in services]
    date_str = next_date.strftime("%A %-d %B")
    if len(names) == 1:
        return f"Your next collection is {names[0]} on {date_str}."
    return f"Your next collections are {' and '.join(names)} on {date_str}."


from flask import Flask, request as flask_request

app = Flask(__name__)


def scrape_schedule() -> list:
    """Run 3-step scrape and return list of (date, service_name) tuples. Raises on failure."""
    postcode = os.environ["POSTCODE"]
    house_number = os.environ["HOUSE_NUMBER"]
    seq1_html = fetch_html("https://wav-wrp.whitespacews.com/mop.php?serviceID=A&seq=1")
    token = extract_track_token(seq1_html)
    seq2_url = f"https://wav-wrp.whitespacews.com/mop.php?serviceID=A&Track={token}&seq=2"
    seq2_html = fetch_html(seq2_url, method="post", data={
        "address_postcode": postcode,
        "address_name_number": house_number,
    })
    pindex = find_pindex(seq2_html, house_number)
    seq3_url = f"https://wav-wrp.whitespacews.com/mop.php?Track={token}&serviceID=A&seq=3&pIndex={pindex}"
    seq3_html = fetch_html(seq3_url)
    return parse_collections(seq3_html)


@app.route("/ask")
def ask():
    q = flask_request.args.get("q", "")
    try:
        collections = scrape_schedule()
    except Exception as e:
        print(f"Scrape error: {e}", file=sys.stderr)
        return (
            "Sorry, I couldn't fetch the bin schedule right now. Please try again later.",
            200,
            {"Content-Type": "text/plain"},
        )
    response = resolve_intent(q, collections)
    return response, 200, {"Content-Type": "text/plain"}
