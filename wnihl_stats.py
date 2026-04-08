"""Parse WNIHL player stats from the STATS page on mygameday.app.

The stats are in a plain HTML <table>.
Columns: Player Name  Team Name  M  Last  G  A  P
  M    = matches played
  Last = date of last game
  G    = goals
  A    = assists
  P    = points (G+A)
"""

import logging
import re

from bs4 import BeautifulSoup

from wnihl_config import clean_team_name

logger = logging.getLogger(__name__)


def _int(val: str | None) -> int | None:
    if not val:
        return None
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return None


def parse_stats_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Return list of player stat dicts from the STATS page."""
    table = soup.find("table")
    if not table:
        logger.warning("[%s] No stats table found", competition)
        return []

    # Build column index from header
    thead = table.find("thead")
    headers = []
    if thead:
        headers = [th.get_text(strip=True).upper() for th in thead.find_all(["th", "td"])]
    else:
        first_row = table.find("tr")
        if first_row:
            headers = [td.get_text(strip=True).upper() for td in first_row.find_all(["th", "td"])]

    def _col(name: str, cells: list[str]) -> str | None:
        try:
            return cells[headers.index(name)]
        except (ValueError, IndexError):
            return None

    rows = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or len(cells) < 3:
            continue
        # Skip header row
        if cells[0].upper() in ("PLAYER NAME", "PLAYER", "NAME"):
            continue

        player_name = _col("PLAYER NAME", cells) or _col("PLAYER", cells)
        if not player_name:
            continue

        team_raw = _col("TEAM NAME", cells) or _col("TEAM", cells) or ""
        team_name = clean_team_name(team_raw) if team_raw else ""

        rows.append({
            "season":      season,
            "competition": competition,
            "player_name": player_name.strip(),
            "team":        team_name,
            "games":       _int(_col("M", cells)),
            "goals":       _int(_col("G", cells)),
            "assists":     _int(_col("A", cells)),
            "points":      _int(_col("P", cells)),
        })

    if not rows:
        logger.warning("[%s] No stat rows parsed — check page structure", competition)
    else:
        logger.info("[%s] Parsed %d player stat rows", competition, len(rows))

    return rows
