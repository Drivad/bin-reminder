"""Bank-holiday collection changes, read from the council's own website.

The booking portal blocks datacenter IPs, but www.waverley.gov.uk does not - it
is separate, on-premise infrastructure. Over Christmas and New Year the council
publishes a "usual day -> revised day" table on its bins page, which is the one
piece of bank-holiday information the fortnightly arithmetic cannot know.

Everything here fails loudly rather than quietly: a festive period with no rows
parsed is treated as an alarm, not as "no changes". Reminders that are silently
wrong over Christmas are worse than reminders that admit they are unsure.
"""

import datetime
import re

from bs4 import BeautifulSoup

BINS_PAGE = (
    "https://www.waverley.gov.uk/services/bins-and-recycling"
    "/rubbish-and-recycling-collections/check-bin-collection-day"
)

# Weeks either side of the new year when a festive table should exist. Used to
# decide whether finding nothing is suspicious.
FESTIVE_START = (12, 10)  # 10 December
FESTIVE_END = (1, 15)  # 15 January

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_MONTHS = {"december": 12, "january": 1}

# e.g. "Friday 25 December (Christmas Day)" / "Monday 4 January"
_DATE_RE = re.compile(
    r"\b(" + "|".join(_WEEKDAYS) + r")\s+(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\b",
    re.IGNORECASE,
)


class StaleTableError(Exception):
    """The published table's weekdays do not match the year it claims to cover."""


def in_festive_window(date: datetime.date) -> bool:
    """True if `date` falls in the period where a festive table should be published."""
    return (date.month, date.day) >= FESTIVE_START or (date.month, date.day) <= FESTIVE_END


def _resolve(text: str, season_start_year: int) -> datetime.date:
    """Turn 'Friday 25 December' into a real date, or raise if the weekday is wrong.

    December belongs to the season's first year, January to the second. The
    weekday check is the guard against stale tables: the council has been
    observed serving last year's table next to this year's.
    """
    match = _DATE_RE.search(text)
    if not match:
        raise ValueError(f"no date found in {text!r}")
    day_name, day, month_name = match.group(1).lower(), int(match.group(2)), match.group(3).lower()

    month = _MONTHS[month_name]
    year = season_start_year if month == 12 else season_start_year + 1
    date = datetime.date(year, month, day)

    if date.weekday() != _WEEKDAYS[day_name]:
        raise StaleTableError(
            f"{text.strip()!r} is not a {day_name.title()} in {year} "
            f"({date:%A %d %B %Y}) - the published table is for a different year"
        )
    return date


def season_start_year(today: datetime.date) -> int:
    """The year the current (or upcoming) festive season begins in."""
    return today.year if today.month >= 6 else today.year - 1


def parse_holiday_changes(html: str, today: datetime.date) -> dict:
    """Extract {usual_date: revised_date} from the bins page.

    Rows reading "No change" are skipped. Rows whose weekday does not match the
    season being parsed are skipped too - that is how a stale table is rejected
    without discarding a valid one on the same page.
    """
    soup = BeautifulSoup(html, "html.parser")
    year = season_start_year(today)
    changes = {}

    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        usual_text, revised_text = cells[0], cells[1]

        try:
            usual = _resolve(usual_text, year)
        except (ValueError, StaleTableError):
            continue  # header row, prose, or a table for another year

        if "no change" in revised_text.lower():
            continue
        try:
            revised = _resolve(revised_text, year)
        except (ValueError, StaleTableError):
            continue

        changes[usual] = revised

    return changes


def adjust(
    date: datetime.date,
    changes: dict,
    base_collections,
) -> list:
    """What is actually collected on `date`, once holiday moves are applied.

    `base_collections` maps a date to the services normally due on it.

    Three cases: something moved *onto* this date, something moved *off* it, or
    neither. A date can only be moved off once, so the first match wins.
    """
    moved_onto = [usual for usual, revised in changes.items() if revised == date]
    if moved_onto:
        return base_collections(moved_onto[0])

    if date in changes:
        return []  # this day's collection happens on another date

    return base_collections(date)
