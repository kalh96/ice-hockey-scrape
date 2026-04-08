"""Parse EIHL standings pages.

URLs:
  League: https://www.eliteleague.co.uk/standings/2025/43-elite-ice-hockey-league
  Cup:    https://www.eliteleague.co.uk/standings/2025/44-challenge-cup

League standings: single table, all 10 teams.
Cup standings: two group tables (Group A, Group B).
"""

import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _int(s: str | None) -> int | None:
    if not s:
        return None
    s = s.strip()
    return int(s) if re.match(r"^-?\d+$", s) else None


def _float(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.strip().replace("%", ""))
    except ValueError:
        return None


def _parse_standings_table(table, competition: str, season: str,
                            group_name: str | None) -> list[dict]:
    """Parse one <table> element into a list of standing row dicts."""
    headers = []
    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True).upper() for th in thead.find_all(["th", "td"])]

    def _col(name: str, cells: list[str]) -> str | None:
        try:
            return cells[headers.index(name)]
        except (ValueError, IndexError):
            return None

    rows = []
    pos  = 0
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or len(cells) < 4:
            continue

        # Team name: find the longest non-numeric cell (usually the team column)
        team_name = None
        for cell in cells:
            if cell and not re.match(r"^[\d.\-%]+$", cell) and len(cell) > 2:
                team_name = cell.strip()
                break
        if not team_name:
            continue

        pos += 1
        rows.append({
            "season":      season,
            "competition": competition,
            "group_name":  group_name,
            "team":        team_name,
            "pos":         _int(_col("POS", cells)) or pos,
            "gp":          _int(_col("GP", cells)),
            "pts":         _int(_col("PTS", cells)),
            "w":           _int(_col("W", cells)),
            "otw":         _int(_col("OTW", cells)),
            "l":           _int(_col("L", cells)),
            "otl":         _int(_col("OTL/SOL", cells)) or _int(_col("OTL", cells)),
            "gf":          _int(_col("GF", cells)),
            "ga":          _int(_col("GA", cells)),
        })

    return rows


def parse_standings_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Return list of standing dicts for all teams/groups on the page."""
    all_rows   = []
    tables     = soup.find_all("table")
    group_name = None   # None for League; set to 'A'/'B' for Cup

    if competition == "Cup":
        # Cup page has two group tables; detect group labels from headings
        headings = soup.find_all(["h2", "h3", "h4"])
        groups   = []
        for h in headings:
            txt = h.get_text(strip=True)
            m   = re.search(r"group\s+([A-Z])", txt, re.IGNORECASE)
            if m:
                groups.append(m.group(1).upper())

        for i, table in enumerate(tables):
            gname = groups[i] if i < len(groups) else str(i + 1)
            rows  = _parse_standings_table(table, competition, season, gname)
            all_rows.extend(rows)
    else:
        # League: single table, no group
        for table in tables:
            rows = _parse_standings_table(table, competition, season, None)
            if rows:
                all_rows.extend(rows)
                break  # only need the first real standings table

    if not all_rows:
        logger.warning("No standings rows parsed for %s — check page structure", competition)
    else:
        logger.info("[%s] Parsed %d standings rows", competition, len(all_rows))

    return all_rows
