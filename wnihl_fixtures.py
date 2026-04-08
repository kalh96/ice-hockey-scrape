"""Parse WNIHL fixtures and results from mygameday.app.

All fixture data is embedded in the page HTML as:
    var matches = [{...}, {...}, ...];

A single fetch of the FIXTURE page returns the full season (past + future games).
"""

import json
import logging
import re

from bs4 import BeautifulSoup

from wnihl_config import BASE_URL, ASSOC_CLIENT, clean_team_name

logger = logging.getLogger(__name__)

_MATCHES_RE = re.compile(r"var matches\s*=\s*(\[.*?\]);", re.DOTALL)


def _parse_status(match: dict) -> str:
    if match.get("FutureGame"):
        return "scheduled"
    fin = match.get("FinalisationString", "").upper()
    if fin in ("FINAL", "FINALS", "RESULT"):
        return "final"
    if match.get("PastGame") and match.get("HomeScore") is not None:
        return "final"
    return "scheduled"


def parse_fixtures_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Extract all fixtures from a mygameday FIXTURE page."""
    html = str(soup)
    m = _MATCHES_RE.search(html)
    if not m:
        logger.warning("[%s] No 'var matches' found in page", competition)
        return []

    try:
        raw_matches = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        logger.error("[%s] JSON parse error: %s", competition, exc)
        return []

    fixtures = []
    seen = set()
    for match in raw_matches:
        if match.get("isBye"):
            continue

        fixture_id = str(match.get("FixtureID", ""))
        if not fixture_id or fixture_id in seen:
            continue
        seen.add(fixture_id)

        home_raw = match.get("HomeName", "")
        away_raw = match.get("AwayName", "")
        home_team = clean_team_name(home_raw)
        away_team = clean_team_name(away_raw)

        status = _parse_status(match)

        home_score = away_score = None
        if status == "final":
            try:
                home_score = int(match["HomeScore"])
                away_score = int(match["AwayScore"])
            except (KeyError, ValueError, TypeError):
                pass

        # Date: TimeDateRaw is "YYYY-MM-DD HH:MM:SS"
        raw_dt = match.get("TimeDateRaw", "")
        iso_date = raw_dt[:16] if raw_dt else None   # "YYYY-MM-DD HH:MM"

        game_url = match.get("DetailedResultsURL", "")
        # DetailedResultsURL may contain HTML entities — decode &amp; → &
        game_url = game_url.replace("&amp;", "&")

        fixtures.append({
            "fixture_id":  fixture_id,
            "competition": competition,
            "season":      season,
            "home_team":   home_team,
            "away_team":   away_team,
            "home_score":  home_score,
            "away_score":  away_score,
            "status":      status,
            "date":        iso_date,
            "venue":       match.get("VenueName") or None,
            "round":       match.get("Round") or None,
            "game_url":    game_url or None,
        })

    logger.info("[%s] Parsed %d fixtures (%d skipped byes/dupes)",
                competition, len(fixtures), len(raw_matches) - len(fixtures))
    return fixtures
