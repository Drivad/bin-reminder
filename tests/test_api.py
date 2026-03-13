import pytest
import datetime
from api import short_name


def test_short_name_strips_collection_service():
    assert short_name("Garden Waste Collection Service") == "Garden Waste"


def test_short_name_strips_case_insensitive():
    assert short_name("recycling collection service") == "recycling"


def test_short_name_leaves_unmatched_strings_unchanged():
    assert short_name("Garden Waste") == "Garden Waste"


def test_short_name_strips_extra_whitespace():
    assert short_name("Food Waste Collection Service  ") == "Food Waste"


from api import resolve_intent

# Fixed test fixture — today = 2026-03-16 (Monday)
TODAY = datetime.date(2026, 3, 16)

FAKE_COLLECTIONS = [
    (datetime.date(2026, 3, 17), "Food Waste Collection Service"),
    (datetime.date(2026, 3, 17), "Recycling Collection Service"),
    (datetime.date(2026, 3, 24), "Domestic Waste Collection Service"),
    (datetime.date(2026, 3, 24), "Food Waste Collection Service"),
    (datetime.date(2026, 3, 26), "Garden Waste Collection Service"),
]


def test_resolve_intent_garden():
    result = resolve_intent("when does the garden waste go out", FAKE_COLLECTIONS, TODAY)
    assert result == "Your next Garden Waste collection is Thursday 26 March."


def test_resolve_intent_recycling():
    result = resolve_intent("when is recycling", FAKE_COLLECTIONS, TODAY)
    assert result == "Your next Recycling collection is Tuesday 17 March."


def test_resolve_intent_food():
    result = resolve_intent("food waste", FAKE_COLLECTIONS, TODAY)
    assert result == "Your next Food Waste collection is Tuesday 17 March."


def test_resolve_intent_domestic():
    result = resolve_intent("domestic", FAKE_COLLECTIONS, TODAY)
    assert result == "Your next Domestic Waste collection is Tuesday 24 March."


def test_resolve_intent_rubbish():
    result = resolve_intent("when does rubbish go out", FAKE_COLLECTIONS, TODAY)
    assert result == "Your next Domestic Waste collection is Tuesday 24 March."


def test_resolve_intent_general():
    result = resolve_intent("general waste", FAKE_COLLECTIONS, TODAY)
    assert result == "Your next Domestic Waste collection is Tuesday 24 March."


def test_resolve_intent_service_not_found():
    result = resolve_intent("garden", [], TODAY)
    assert result == "There are no upcoming Garden Waste collections in the schedule."
