import re
import datetime
import os
import sys

from scraper import fetch_html, extract_track_token, find_pindex, parse_collections


def short_name(service: str) -> str:
    """Strip 'Collection Service' suffix for spoken output."""
    return re.sub(r"\s*collection service\s*$", "", service, flags=re.IGNORECASE).strip()


def _week_range(today: datetime.date, offset_weeks: int = 0):
    """Return (monday, sunday) for the week containing today, offset by N weeks."""
    monday = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(weeks=offset_weeks)
    sunday = monday + datetime.timedelta(days=6)
    return monday, sunday


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
