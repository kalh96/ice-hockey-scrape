"""Parse WNIHL standings from the LADDER page on mygameday.app.

The standings are in a plain HTML <table> (not a JavaScript variable).
Columns: POS  TEAM  P  W  L  D  For  Agst  PTS  GD  [L5]

Note: WNIHL uses D (draws) rather than EIHL's OTW/OTL split.
"""

import logging
import re

from bs4 import BeautifulSoup

from wnihl_config import clean_team_name

logger = logging.getLogger(__name__)


def _int(val: str | None) -> int | None:
    if val is None:
        return None
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return None


def parse_standings_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Return list of standing row dicts from the LADDER page."""
    table = soup.find("table")
    if not table:
        logger.warning("[%s] No standings table found", competition)
        return []

    # Build column index from header row
    thead = table.find("thead")
    headers = []
    if thead:
        headers = [th.get_text(strip=True).upper() for th in thead.find_all(["th", "td"])]
    else:
        # First row may be headers
        first_row = table.find("tr")
        if first_row:
            headers = [td.get_text(strip=True).upper() for td in first_row.find_all(["th", "td"])]

    def _col(name: str, cells: list[str]) -> str | None:
        try:
            return cells[headers.index(name)]
        except (ValueError, IndexError):
            return None

    rows = []
    pos = 0
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or len(cells) < 4:
            continue
        # Skip header rows
        if cells[0].upper() in ("POS", "#", ""):
            continue

        team_raw = _col("TEAM", cells)
        if not team_raw or re.match(r"^[\d.\-%]+$", team_raw):
            # Fallback: find longest non-numeric cell
            for c in cells:
                if c and not re.match(r"^[\d.\-% ]+$", c) and len(c) > 1:
                    team_raw = c
                    break

        if not team_raw:
            continue

        team_name = clean_team_name(team_raw)
        pos += 1

        rows.append({
            "season":      season,
            "competition": competition,
            "team":        team_name,
            "pos":         _int(_col("POS", cells)) or pos,
            "gp":          _int(_col("P", cells)),
            "w":           _int(_col("W", cells)),
            "l":           _int(_col("L", cells)),
            "d":           _int(_col("D", cells)),
            "gf":          _int(_col("FOR", cells)),
            "ga":          _int(_col("AGST", cells)),
            "pts":         _int(_col("PTS", cells)),
        })

    if not rows:
        logger.warning("[%s] No standing rows parsed — check page structure", competition)
    else:
        logger.info("[%s] Parsed %d standing rows", competition, len(rows))

    return rows
