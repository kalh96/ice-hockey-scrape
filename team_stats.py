"""Parse the league table / team stats page."""

import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def _slug_from_href(href: str, path_segment: str) -> str | None:
    parts = [p for p in urlparse(href).path.strip("/").split("/") if p]
    for i, p in enumerate(parts):
        if p == path_segment and i + 1 < len(parts):
            return parts[i + 1]
    return None


def _int(val: str | None) -> int | None:
    if val is None:
        return None
    val = val.strip()
    if val in ("", "-", "\xa0"):
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _float(val: str | None) -> float | None:
    if val is None:
        return None
    val = val.strip()
    if val in ("", "-", "\xa0"):
        return None
    # strip trailing % if present
    val = val.rstrip("%")
    try:
        return float(val)
    except ValueError:
        return None


def _cell(row: Tag, cls: str) -> str | None:
    td = row.find("td", class_=cls)
    if td is None:
        return None
    return td.get_text(strip=True) or None


def parse_team_stats(soup: BeautifulSoup) -> list[dict]:
    """
    Returns list of dicts with team season stats.
    Handles both the league table (sp-league-table) and a stats table
    (sp-data-table) since SIHA uses different table classes on different pages.
    """
    # Try the dedicated team stats table first, then fall back to the league table
    table = (
        soup.find("table", class_="sp-standings-table") or
        soup.find("table", class_="sp-league-table") or
        soup.find("table", class_="sp-data-table")
    )
    if table is None:
        logger.warning("No team stats table found")
        return []

    results = []
    for row in table.select("tbody tr"):
        name_td = row.find("td", class_="data-name")
        if name_td is None:
            continue

        team_link = name_td.find("a")
        if team_link:
            team_name = team_link.get_text(strip=True)
            team_slug = _slug_from_href(team_link.get("href", ""), "team") or ""
        else:
            team_name = name_td.get_text(strip=True)
            team_slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")

        if not team_slug:
            continue

        # pp_pct and pk_pct may be stored as percentage (e.g. "18.2") or decimal
        pp_pct = _float(_cell(row, "data-pp_pct") or _cell(row, "data-ppp"))
        pk_pct = _float(_cell(row, "data-pk_pct") or _cell(row, "data-pkp"))

        results.append({
            "team_slug": team_slug,
            "team_name": team_name,
            "pos":       _int(_cell(row, "data-pos") or _cell(row, "data-rank")),
            "gp":        _int(_cell(row, "data-gp")),
            "wins":      _int(_cell(row, "data-w")),
            "losses":    _int(_cell(row, "data-l")),
            "otl":       _int(_cell(row, "data-otl")),
            "gf":        _int(_cell(row, "data-gf")),
            "ga":        _int(_cell(row, "data-ga")),
            "goal_diff": _int(_cell(row, "data-diff") or _cell(row, "data-gd")),
            "pts":       _int(_cell(row, "data-pts")),
            "ppo":       _int(_cell(row, "data-ppo")),
            "ppg":       _int(_cell(row, "data-ppg")),
            "pp_pct":    pp_pct,
            "ppga":      _int(_cell(row, "data-ppga")),
            "ppoa":      _int(_cell(row, "data-ppoa")),
            "pk_pct":    pk_pct,
            "shg":       _int(_cell(row, "data-shg")),
            "shga":      _int(_cell(row, "data-shga")),
        })

    logger.info("Parsed %d team stats rows", len(results))
    return results
