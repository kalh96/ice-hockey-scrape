"""Parse individual /event/{id}/ pages for period scores and player stats."""

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
    try:
        return float(val)
    except ValueError:
        return None


def _cell(row: Tag, cls: str) -> str | None:
    td = row.find("td", class_=cls)
    if td is None:
        return None
    return td.get_text(strip=True) or None


def parse_event_page(event_id: int, soup: BeautifulSoup) -> dict:
    """
    Returns:
    {
        "period_scores": [
            {"team_slug": str, "team_name": str,
             "period_1": int|None, ..., "ppg": int|None, "ppo": int|None, "outcome": str|None}
        ],
        "player_stats": [
            {"team_slug": str, "team_name": str,
             "player_slug": str, "player_name": str,
             "jersey_number": str|None, "position": str|None,
             "goals": int, "assists": int, "pim": int,
             "shots_against": int|None, "saves": int|None,
             "goals_against": int|None, "toi": str|None}
        ]
    }
    """
    period_scores = _parse_period_scores(event_id, soup)
    player_stats = _parse_player_stats(event_id, soup)
    return {"period_scores": period_scores, "player_stats": player_stats}


def _parse_period_scores(event_id: int, soup: BeautifulSoup) -> list[dict]:
    table = soup.find("table", class_="sp-event-results")
    if table is None:
        logger.warning("Event %d: no sp-event-results table found", event_id)
        return []

    results = []
    for row in table.select("tbody tr"):
        if "sp-total-row" in row.get("class", []):
            continue

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

        results.append({
            "team_slug": team_slug,
            "team_name": team_name,
            "period_1":  _int(_cell(row, "data-first")),
            "period_2":  _int(_cell(row, "data-second")),
            "period_3":  _int(_cell(row, "data-third")),
            "ppg":       _int(_cell(row, "data-ppg")),
            "ppo":       _int(_cell(row, "data-ppo")),
            "outcome":   _cell(row, "data-outcome"),
        })

    return results


def _parse_player_stats(event_id: int, soup: BeautifulSoup) -> list[dict]:
    stats = []

    # Each team's stats live inside a div.sp-template-event-performance-values
    # which contains both the h4.sp-table-caption (team name) and the
    # table.sp-event-performance. We search within each wrapper div.
    wrappers = soup.find_all("div", class_="sp-template-event-performance-values")
    if not wrappers:
        # Fallback: try finding performance tables directly and look for preceding h4
        wrappers = [t.parent for t in soup.find_all("table", class_="sp-event-performance")]

    for wrapper in wrappers:
        heading = wrapper.find("h4", class_="sp-table-caption")
        if heading is None:
            continue

        team_link = heading.find("a")
        if team_link:
            team_name = team_link.get_text(strip=True)
            team_slug = _slug_from_href(team_link.get("href", ""), "team") or ""
        else:
            team_name = heading.get_text(strip=True)
            team_slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")

        table = wrapper.find("table", class_="sp-event-performance")
        if table is None:
            logger.debug("Event %d: no performance table in wrapper for %r", event_id, team_name)
            continue

        for row in table.select("tbody tr"):
            if "sp-total-row" in row.get("class", []):
                continue

            name_td = row.find("td", class_="data-name")
            if name_td is None:
                continue

            player_link = name_td.find("a")
            if player_link:
                player_name = player_link.get_text(strip=True)
                player_slug = _slug_from_href(player_link.get("href", ""), "player") or ""
            else:
                player_name = name_td.get_text(strip=True)
                player_slug = re.sub(r"[^a-z0-9]+", "-", player_name.lower()).strip("-")

            if not player_slug or not player_name:
                continue

            stats.append({
                "team_slug":     team_slug,
                "team_name":     team_name,
                "player_slug":   player_slug,
                "player_name":   player_name,
                "jersey_number": _cell(row, "data-number"),
                "position":      _cell(row, "data-position"),
                "goals":         _int(_cell(row, "data-g")) or 0,
                "assists":       _int(_cell(row, "data-a")) or 0,
                "pim":           _int(_cell(row, "data-pim")) or 0,
                "shots_against": _int(_cell(row, "data-sa")),
                "saves":         _int(_cell(row, "data-sv")),
                "goals_against": _int(_cell(row, "data-ga")),
                "toi":           _cell(row, "data-toi"),
            })

    return stats
