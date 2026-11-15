import datetime

import pytest

from holidays import (
    StaleTableError,
    adjust,
    in_festive_window,
    parse_holiday_changes,
    season_start_year,
)

# The real 2026/27 table as published on the council's bins page.
REAL_TABLE = """
<html><body>
<h3>Christmas and New Year period 2026 to 2027</h3>
<table>
  <tr><th>Usual collection day</th><th>Revised collection day</th></tr>
  <tr><td>Monday 21 December</td><td>No change</td></tr>
  <tr><td>Thursday 24 December (Christmas Eve)</td><td>No change</td></tr>
  <tr><td>Friday 25 December (Christmas Day)</td><td>Monday 28 December</td></tr>
  <tr><td>Monday 28 December (Boxing Day)</td><td>Tuesday 29 December</td></tr>
  <tr><td>Tuesday 29 December</td><td>Wednesday 30 December</td></tr>
  <tr><td>Thursday 31 December</td><td>Saturday 2 January</td></tr>
  <tr><td>Friday 1 January (New Year's Day)</td><td>Monday 4 January</td></tr>
  <tr><td>Tuesday 5 January</td><td>Wednesday 6 January</td></tr>
</table>
</body></html>
"""

# The council was observed serving a stale clinical-waste table beside the live
# one: these weekdays are 2025's, not 2026's.
STALE_TABLE = """
<html><body>
<table>
  <tr><th>Usual collection day</th><th>Revised collection day</th></tr>
  <tr><td>Thursday 25 December</td><td>Monday 29 December</td></tr>
  <tr><td>Friday 26 December (Boxing Day)</td><td>Tuesday 30 December</td></tr>
</table>
</body></html>
"""

TODAY = datetime.date(2026, 11, 15)


def test_parses_the_real_table():
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    assert changes[datetime.date(2026, 12, 25)] == datetime.date(2026, 12, 28)
    assert changes[datetime.date(2026, 12, 29)] == datetime.date(2026, 12, 30)


def test_january_rows_roll_into_the_next_year():
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    # New Year's Day 2027 moves to Monday 4 January 2027.
    assert changes[datetime.date(2027, 1, 1)] == datetime.date(2027, 1, 4)
    assert changes[datetime.date(2027, 1, 5)] == datetime.date(2027, 1, 6)


def test_no_change_rows_are_not_treated_as_moves():
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    assert datetime.date(2026, 12, 21) not in changes
    assert datetime.date(2026, 12, 24) not in changes


def test_stale_table_is_rejected_entirely():
    # 25 Dec 2026 is a Friday, not a Thursday. Trusting this would shift
    # collections by a day across the whole festive period.
    assert parse_holiday_changes(STALE_TABLE, TODAY) == {}


def test_stale_and_live_tables_on_one_page_keeps_only_the_live_one():
    both = REAL_TABLE.replace("</body>", STALE_TABLE + "</body>")
    changes = parse_holiday_changes(both, TODAY)
    assert changes[datetime.date(2026, 12, 25)] == datetime.date(2026, 12, 28)
    assert datetime.date(2026, 12, 26) not in changes


def test_page_with_no_table_yields_nothing():
    assert parse_holiday_changes("<html><body><p>Nothing here</p></body></html>", TODAY) == {}


def test_season_start_year_rolls_over_mid_year():
    assert season_start_year(datetime.date(2026, 11, 15)) == 2026
    assert season_start_year(datetime.date(2027, 1, 4)) == 2026  # still the 26/27 season
    assert season_start_year(datetime.date(2027, 7, 1)) == 2027


def test_festive_window_covers_the_turn_of_the_year():
    assert in_festive_window(datetime.date(2026, 12, 25)) is True
    assert in_festive_window(datetime.date(2027, 1, 2)) is True
    assert in_festive_window(datetime.date(2026, 8, 4)) is False


# --- applying the changes -------------------------------------------------

BASE = {
    datetime.date(2026, 12, 25): ["Food Waste Collection Service"],
    datetime.date(2026, 12, 21): ["Recycling Collection Service"],
}


def _base(date):
    return BASE.get(date, [])


def test_collection_moves_onto_its_revised_day():
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    # Christmas Day's collection happens on Monday 28 December instead.
    assert adjust(datetime.date(2026, 12, 28), changes, _base) == [
        "Food Waste Collection Service"
    ]


def test_nothing_is_collected_on_the_day_it_moved_off():
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    assert adjust(datetime.date(2026, 12, 25), changes, _base) == []


def test_a_no_change_day_is_left_alone():
    # 21 December is listed but explicitly unchanged, so it must behave normally.
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    assert adjust(datetime.date(2026, 12, 21), changes, _base) == [
        "Recycling Collection Service"
    ]


def test_a_day_moved_off_reports_nothing_even_though_it_is_a_normal_day():
    # 29 Dec normally has a collection, but the table moves it to the 30th.
    changes = parse_holiday_changes(REAL_TABLE, TODAY)
    base = {datetime.date(2026, 12, 29): ["Domestic Waste Collection Service"]}
    assert adjust(datetime.date(2026, 12, 29), changes, lambda d: base.get(d, [])) == []
    assert adjust(datetime.date(2026, 12, 30), changes, lambda d: base.get(d, [])) == [
        "Domestic Waste Collection Service"
    ]


def test_stale_row_raises_rather_than_silently_resolving():
    with pytest.raises(StaleTableError):
        from holidays import _resolve

        _resolve("Thursday 25 December", 2026)
