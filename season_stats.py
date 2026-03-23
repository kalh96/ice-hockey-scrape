"""Parse season aggregate skater and netminder list pages."""

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


def parse_skater_list(soup: BeautifulSoup) -> list[dict]:
    """
    Returns list of dicts:
      player_slug, player_name, team_slug, team_name, position,
      gp, goals, assists, total_points, pim
    """
    table = soup.find("table", class_="sp-player-list")
    if table is None:
        logger.warning("No sp-player-list table found on skater page")
        return []

    results = []
    for row in table.select("tbody tr"):
        name_td = row.find("td", class_="data-name")
        if name_td is None:
            continue

        player_link = name_td.find("a")
        if not player_link:
            continue
        player_name = player_link.get_text(strip=True)
        player_slug = _slug_from_href(player_link.get("href", ""), "player") or ""
        if not player_slug:
            continue

        team_td = row.find("td", class_="data-team")
        if team_td:
            team_link = team_td.find("a")
            if team_link:
                team_name = team_link.get_text(strip=True)
                team_slug = _slug_from_href(team_link.get("href", ""), "team") or ""
            else:
                team_name = team_td.get_text(strip=True)
                team_slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")
        else:
            team_name = team_slug = ""

        results.append({
            "player_slug":   player_slug,
            "player_name":   player_name,
            "team_slug":     team_slug,
            "team_name":     team_name,
            "position":      _cell(row, "data-position"),
            "gp":            _int(_cell(row, "data-gp")),
            "goals":         _int(_cell(row, "data-g")),
            "assists":       _int(_cell(row, "data-a")),
            "total_points":  _int(_cell(row, "data-p")),
            "pim":           _int(_cell(row, "data-pim")),
        })

    logger.info("Parsed %d skaters", len(results))
    return results


def parse_netminder_list(soup: BeautifulSoup) -> list[dict]:
    """
    Returns list of dicts:
      player_slug, player_name, team_slug, team_name,
      gp, shots_against, saves, goals_against, save_pct, gaa, toi
    """
    table = soup.find("table", class_="sp-player-list")
    if table is None:
        logger.warning("No sp-player-list table found on netminder page")
        return []

    results = []
    for row in table.select("tbody tr"):
        name_td = row.find("td", class_="data-name")
        if name_td is None:
            continue

        player_link = name_td.find("a")
        if not player_link:
            continue
        player_name = player_link.get_text(strip=True)
        player_slug = _slug_from_href(player_link.get("href", ""), "player") or ""
        if not player_slug:
            continue

        team_td = row.find("td", class_="data-team")
        if team_td:
            team_link = team_td.find("a")
            if team_link:
                team_name = team_link.get_text(strip=True)
                team_slug = _slug_from_href(team_link.get("href", ""), "team") or ""
            else:
                team_name = team_td.get_text(strip=True)
                team_slug = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")
        else:
            team_name = team_slug = ""

        # SV% may be in data-svpercent or data-sv_pct
        sv_pct_td = (
            row.find("td", class_="data-svpercent") or
            row.find("td", class_="data-sv_pct") or
            row.find("td", class_="data-svp")
        )
        sv_pct_str = sv_pct_td.get_text(strip=True) if sv_pct_td else None

        results.append({
            "player_slug":   player_slug,
            "player_name":   player_name,
            "team_slug":     team_slug,
            "team_name":     team_name,
            "gp":            _int(_cell(row, "data-gp")),
            "shots_against": _int(_cell(row, "data-sa")),
            "saves":         _int(_cell(row, "data-sv")),
            "goals_against": _int(_cell(row, "data-ga")),
            "save_pct":      _float(sv_pct_str),
            "gaa":           _float(_cell(row, "data-gaa")),
            "toi":           _cell(row, "data-toi"),
        })

    logger.info("Parsed %d netminders", len(results))
    return results
