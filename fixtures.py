"""Parse the fixtures/results page to discover all event IDs."""

import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _extract_event_id(href: str) -> int | None:
    m = re.search(r"/event/(\d+)/", href)
    if m:
        return int(m.group(1))
    return None


def _extract_team_slug(href: str) -> str:
    parts = [p for p in urlparse(href).path.strip("/").split("/") if p]
    # href pattern: /team/{slug}/
    if len(parts) >= 2 and parts[0] == "team":
        return parts[1]
    return parts[-1] if parts else ""


def parse_fixtures_page(soup: BeautifulSoup) -> list[dict]:
    """
    Return a list of fixture dicts:
      event_id, competition, date, home_team_slug, home_team_name,
      away_team_slug, away_team_name, home_score, away_score, status
    """
    fixtures = []

    for event_link in soup.select("a.sp-scoreboard-event"):
        href = event_link.get("href", "")
        event_id = _extract_event_id(href)
        if event_id is None:
            continue

        competition = (
            event_link.select_one(".sp-scoreboard-league") or
            event_link.select_one(".sp-event-league")
        )
        competition_name = competition.get_text(strip=True) if competition else "SNL"

        date_el = event_link.select_one(".sp-scoreboard-date")
        date_str = date_el.get_text(strip=True) if date_el else None

        team_els = event_link.select(".sp-scoreboard-team")
        if len(team_els) < 2:
            logger.warning("Event %d: fewer than 2 team elements, skipping", event_id)
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

        fixtures.append({
            "event_id":       event_id,
            "competition":    _normalise_competition(competition_name),
            "date":           date_str,
            "home_team_slug": home_slug,
            "home_team_name": home_name,
            "away_team_slug": away_slug,
            "away_team_name": away_name,
            "home_score":     home_score,
            "away_score":     away_score,
            "status":         status,
        })

    logger.info("Parsed %d fixtures from scoreboard", len(fixtures))
    return fixtures


def _normalise_competition(raw: str) -> str:
    raw = raw.strip()
    if "cup" in raw.lower():
        return "Scottish Cup"
    return "SNL"


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
