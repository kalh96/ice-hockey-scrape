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
    if len(parts) >= 2 and parts[0] == "team":
        return parts[1]
    return parts[-1] if parts else ""


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _normalise_competition(raw: str) -> str:
    raw = raw.strip()
    if "cup" in raw.lower():
        return "Scottish Cup"
    return "SNL"


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
        competition_name = competition_el.get_text(strip=True) if competition_el else "SNL"

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
            "competition":    _normalise_competition(competition_name),
            "date":           date_str,
            "home_team_slug": home_slug,
            "home_team_name": home_name,
            "away_team_slug": away_slug,
            "away_team_name": away_name,
            "home_score":     home_score,
            "away_score":     away_score,
            "status":         status,
        }

    logger.info("Parsed %d fixtures from scoreboard", len(fixtures))

    # --- Pass 2: fixture matrix tables (full season schedule) ---
    for matrix in soup.find_all("table", class_="sp-event-matrix"):
        # Determine competition from the nearest preceding heading
        heading = matrix.find_previous(["h2", "h3", "h4", "h5"])
        competition = _normalise_competition(
            heading.get_text(strip=True) if heading else "SNL"
        )

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
                for link in cell.find_all("a", href=re.compile(r"/event/\d+/")):
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

                    # Only add if not already captured by the scoreboard (which has date info)
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
                        }

    matrix_total = len(fixtures)
    logger.info("Parsed %d total fixtures (scoreboard + matrix)", matrix_total)
    return list(fixtures.values())
