"""Parse the EIHL schedule page for fixtures and results.

URL format:
  https://www.eliteleague.co.uk/schedule?id_season=43   → League
  https://www.eliteleague.co.uk/schedule?id_season=44   → Cup (verify on first run)

Each game is an <a href="/game/{id}-{home_abbrev}-{away_abbrev}"> block containing
team logos, abbreviations, score or date/time, and status text.
"""

import logging
import re

from bs4 import BeautifulSoup

from eihl_config import BASE_URL, TEAM_ABBREV

logger = logging.getLogger(__name__)

_MONTH_NUM = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}
_MONTHS = set(_MONTH_NUM)
_GAME_RE = re.compile(r"^/game/(\d+)-([a-z]+)-([a-z]+)$")


def _normalize_date(raw: str, season: str) -> str | None:
    """Convert '11 apr 18:00' (lowercased) → '2026-04-11 18:00'."""
    m = re.match(r"(\d{1,2})\s+([a-z]{3})(?:\s+(\d{2}:\d{2}))?", raw.strip())
    if not m:
        return None
    day, mon, time_part = m.group(1), m.group(2), m.group(3) or "00:00"
    month_num = _MONTH_NUM.get(mon)
    if not month_num:
        return None
    season_start = int(season[:4])   # 2025 from "2025-26"
    year = season_start if int(month_num) >= 9 else season_start + 1
    return f"{year}-{month_num}-{int(day):02d} {time_part}"


def _parse_game_link(a_tag, competition: str, season: str) -> dict | None:
    href = a_tag.get("href", "").split("?")[0]  # strip any query string
    m = _GAME_RE.match(href)
    if not m:
        return None

    game_id      = m.group(1)
    home_abbrev  = m.group(2)
    away_abbrev  = m.group(3)
    home_team    = TEAM_ABBREV.get(home_abbrev, home_abbrev.upper())
    away_team    = TEAM_ABBREV.get(away_abbrev, away_abbrev.upper())

    # Flatten all text tokens (lowercase)
    raw_text = a_tag.get_text(" ", strip=True)
    tokens   = raw_text.lower().split()

    # --- Status ---
    if "final ot" in raw_text.lower() or "final-ot" in raw_text.lower():
        status = "final OT"
    elif "final so" in raw_text.lower() or "final-so" in raw_text.lower():
        status = "final SO"
    elif "final" in raw_text.lower():
        status = "final"
    else:
        status = "scheduled"

    # --- Score (two adjacent integers) ---
    home_score = away_score = None
    if status != "scheduled":
        for i, tok in enumerate(tokens[:-1]):
            if tok.isdigit() and tokens[i + 1].isdigit():
                home_score = int(tok)
                away_score = int(tokens[i + 1])
                break

    # --- Date (day + month [+ HH:MM]) ---
    raw_date = None
    for i, tok in enumerate(tokens):
        if tok in _MONTHS and i > 0 and tokens[i - 1].isdigit():
            day_tok  = tokens[i - 1]
            time_tok = tokens[i + 1] if (i + 1 < len(tokens)
                                          and re.match(r"\d{2}:\d{2}", tokens[i + 1])) else ""
            raw_date = f"{day_tok} {tok} {time_tok}".strip()
            break

    return {
        "game_id":    game_id,
        "competition": competition,
        "season":     season,
        "home_team":  home_team,
        "away_team":  away_team,
        "home_score": home_score,
        "away_score": away_score,
        "status":     status,
        "date":       _normalize_date(raw_date, season) if raw_date else None,
        "game_url":   f"{BASE_URL}/game/{game_id}-{home_abbrev}-{away_abbrev}",
    }


def parse_schedule_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Return list of fixture dicts parsed from a schedule page."""
    fixtures = []
    seen = set()

    for a in soup.find_all("a", href=_GAME_RE):
        fixture = _parse_game_link(a, competition, season)
        if fixture and fixture["game_id"] not in seen:
            seen.add(fixture["game_id"])
            fixtures.append(fixture)

    if not fixtures:
        logger.warning(
            "No game links found on schedule page for %s. "
            "Check if the page uses JavaScript rendering or the URL parameters changed.",
            competition,
        )

    logger.info("[%s] Parsed %d fixtures from schedule", competition, len(fixtures))
    return fixtures
