"""Parse the fixtures/results page to discover all event IDs."""

import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


import zlib


def _extract_event_id(href: str) -> int | None:
    """Extract numeric event ID, or derive a stable integer from a slug URL."""
    m = re.search(r"/event/(\d+)/", href)
    if m:
        return int(m.group(1))
    # Slug-based URL e.g. /event/thunder-vs-caps-2/
    m = re.search(r"/event/([a-z0-9][a-z0-9\-]+[a-z0-9])/", href)
    if m:
        slug = m.group(1)
        # Use CRC32 + offset to produce a stable ID outside the normal 5-digit range
        return zlib.crc32(slug.encode()) & 0x7FFFFFFF | 0x40000000
    return None


def _event_url(href: str) -> str | None:
    """Return the path portion of an event href, or None if not an event link."""
    m = re.search(r"(/event/[^/\"' ]+/)", href)
    return m.group(1) if m else None


def _extract_team_slug(href: str) -> str:
    parts = [p for p in urlparse(href).path.strip("/").split("/") if p]
    if len(parts) >= 2 and parts[0] == "team":
        return parts[1]
    return parts[-1] if parts else ""


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _normalise_competition(raw: str) -> str | None:
    """Return competition name, or None if the heading is not a recognised competition."""
    raw = raw.strip().lower()
    if "cup" in raw:
        return "Scottish Cup"
    if "snl" in raw or "scottish national league" in raw:
        return "SNL"
    return None


def parse_fixtures_page(soup: BeautifulSoup) -> list[dict]:
    """
    Return a list of fixture dicts:
      event_id, competition, date, home_team_slug, home_team_name,
      away_team_slug, away_team_name, home_score, away_score, status

    Parses both:
    - The scoreboard widget (upcoming/recent games, includes date info)
    - The full fixture matrix (all completed and scheduled games)
    """
    fixtures: dict[int, dict] = {}

    # --- Pass 1: scoreboard widget (provides dates and upcoming fixtures) ---
    for event_link in soup.select("a.sp-scoreboard-event"):
        href = event_link.get("href", "")
        event_id = _extract_event_id(href)
        if event_id is None:
            continue

        competition_el = (
            event_link.select_one(".sp-scoreboard-league") or
            event_link.select_one(".sp-event-league")
        )
        competition_name = (competition_el.get_text(strip=True) if competition_el else None) or "SNL"
        competition = _normalise_competition(competition_name)
        if competition is None:
            logger.debug("Skipping scoreboard event %s — unknown competition %r", href, competition_name)
            continue

        date_el = event_link.select_one(".sp-scoreboard-date")
        date_str = date_el.get_text(strip=True) if date_el else None

        team_els = event_link.select(".sp-scoreboard-team")
        if len(team_els) < 2:
            continue

        def _team_info(el):
            name_el = el.select_one(".sp-scoreboard-team-name")
            name = name_el.get_text(strip=True) if name_el else ""
            link_el = el.select_one("a")
            slug = _extract_team_slug(link_el["href"]) if link_el else _slugify(name)
            score_el = el.select_one(".sp-scoreboard-result")
            score = score_el.get_text(strip=True) if score_el else None
            return name, slug, score

        home_name, home_slug, home_score_str = _team_info(team_els[0])
        away_name, away_slug, away_score_str = _team_info(team_els[1])

        # Skip placeholder fixtures where teams are not yet announced
        if not home_slug and not away_slug:
            logger.debug("Skipping blank fixture %s — teams not yet announced", href)
            continue

        if home_score_str is not None and away_score_str is not None:
            try:
                home_score = int(home_score_str)
                away_score = int(away_score_str)
                status = "final"
            except ValueError:
                home_score = away_score = None
                status = "scheduled"
        else:
            home_score = away_score = None
            status = "scheduled"

        fixtures[event_id] = {
            "event_id":       event_id,
            "competition":    competition,
            "date":           date_str,
            "home_team_slug": home_slug,
            "home_team_name": home_name,
            "away_team_slug": away_slug,
            "away_team_name": away_name,
            "home_score":     home_score,
            "away_score":     away_score,
            "status":         status,
            "event_url":      _event_url(href),
        }

    logger.info("Parsed %d fixtures from scoreboard", len(fixtures))

    # --- Pass 2: fixture matrix tables (full season schedule) ---
    for matrix in soup.find_all("table", class_="sp-event-matrix"):
        # Determine competition from the nearest preceding heading
        heading = matrix.find_previous(["h2", "h3", "h4", "h5"])
        heading_text = heading.get_text(strip=True) if heading else ""
        competition = _normalise_competition(heading_text)
        if competition is None:
            logger.debug("Skipping matrix — unknown competition %r", heading_text)
            continue

        # Build column index → (away_slug, away_name) from thead
        thead = matrix.find("thead")
        col_teams: list[tuple[str, str]] = []  # index 0 = col 1 (skip row-header col)
        if thead:
            for th in thead.find_all("th"):
                link = th.find("a")
                if link:
                    away_name = link.get("title", "") or link.get_text(strip=True)
                    away_slug = _extract_team_slug(link.get("href", ""))
                    col_teams.append((away_slug, away_name))
                else:
                    col_teams.append(("", ""))  # row-header placeholder

        tbody = matrix.find("tbody")
        if tbody is None:
            continue

        for row in tbody.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            # First cell is the home team
            home_cell = cells[0]
            home_link = home_cell.find("a")
            if home_link:
                home_name = home_link.get("title", "") or home_link.get_text(strip=True)
                home_slug = _extract_team_slug(home_link.get("href", ""))
            else:
                home_name = home_cell.get_text(strip=True)
                home_slug = _slugify(home_name)

            if not home_slug:
                continue

            # Remaining cells are away-team columns
            for col_idx, cell in enumerate(cells[1:], start=1):
                # col_idx maps to col_teams[col_idx] (col_teams[0] is the placeholder)
                if col_idx < len(col_teams):
                    away_slug, away_name = col_teams[col_idx]
                else:
                    away_slug = away_name = ""

                # Each cell may contain one or more event links
                for link in cell.find_all("a", href=re.compile(r"/event/[^/\"' ]+/")):
                    event_id = _extract_event_id(link["href"])
                    if event_id is None:
                        continue

                    # Score is the link text, e.g. "3-2" (home-away)
                    score_text = link.get_text(strip=True)
                    score_match = re.match(r"^(\d+)-(\d+)$", score_text)
                    if score_match:
                        home_score = int(score_match.group(1))
                        away_score = int(score_match.group(2))
                        status = "final"
                    else:
                        home_score = away_score = None
                        status = "scheduled"

                    # Always update with matrix team info (canonical slugs from hrefs).
                    # Preserve date and score from scoreboard if already captured.
                    if event_id not in fixtures:
                        fixtures[event_id] = {
                            "event_id":       event_id,
                            "competition":    competition,
                            "date":           None,
                            "home_team_slug": home_slug,
                            "home_team_name": home_name,
                            "away_team_slug": away_slug,
                            "away_team_name": away_name,
                            "home_score":     home_score,
                            "away_score":     away_score,
                            "status":         status,
                            "event_url":      _event_url(link["href"]),
                        }
                    else:
                        # Update team info from matrix (more canonical than scoreboard)
                        fixtures[event_id]["home_team_slug"] = home_slug
                        fixtures[event_id]["home_team_name"] = home_name
                        fixtures[event_id]["away_team_slug"] = away_slug
                        fixtures[event_id]["away_team_name"] = away_name

    matrix_total = len(fixtures)
    logger.info("Parsed %d total fixtures (scoreboard + matrix)", matrix_total)
    return list(fixtures.values())
