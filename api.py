import re
import datetime
import os
import sys

from scraper import fetch_html, extract_track_token, find_pindex, parse_collections


def short_name(service: str) -> str:
    """Strip 'Collection Service' suffix for spoken output."""
    return re.sub(r"\s*collection service\s*$", "", service, flags=re.IGNORECASE).strip()
