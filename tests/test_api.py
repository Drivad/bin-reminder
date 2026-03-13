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
