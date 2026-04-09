"""Parse the EIHL schedule page for fixtures and results.

The schedule page only returns the most recent fixture window regardless of URL
parameters (the month filter is JavaScript-driven).  To get the full season we
fetch each calendar month individually and merge by game_id.

Season months: September (9) – December (12) in year N, January (1) – April (4) in year N+1.

Score formats observed:
  Space-separated (League):  "1 4 final", "3 2 final OT"
  Colon-separated (Cup):     "3:6", "2:3 OT"
"""

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from eihl_config import BASE_URL, TEAM_ABBREV

logger = logging.getLogger(__name__)

_MONTH_NUM = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}
_MONTHS   = set(_MONTH_NUM)
_GAME_RE  = re.compile(r"^/game/(\d+)-([a-z]+)-([a-z]+)$")
_TODAY    = date.today().isoformat()   # refreshed at import time


def _normalize_date(raw: str, season: str) -> str | None:
    """'11 apr 18:00' → '2026-04-11 18:00'.  Handles both name and dot formats."""
    raw = raw.strip().lower()

    # DD.MM.YYYY  or  DD.MM.YYYY HH:MM
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{2}:\d{2}))?", raw)
    if m:
        d, mo, yr, t = m.groups()
        return f"{yr}-{mo.zfill(2)}-{d.zfill(2)} {t or '00:00'}"

    # D+ month_abbrev [HH:MM]
    m = re.match(r"(\d{1,2})\s+([a-z]{3})(?:\s+(\d{2}:\d{2}))?", raw)
    if m:
        d, mon, t = m.groups()
        month_num = _MONTH_NUM.get(mon)
        if not month_num:
            return None
        season_start = int(season[:4])
        year = season_start if int(month_num) >= 9 else season_start + 1
        return f"{year}-{month_num}-{int(d):02d} {t or '00:00'}"

    return None


def _parse_game_link(a_tag, competition: str, season: str) -> dict | None:
    href = a_tag.get("href", "").split("?")[0]
    m = _GAME_RE.match(href)
    if not m:
        return None

    game_id     = m.group(1)
    home_abbrev = m.group(2)
    away_abbrev = m.group(3)
    home_team   = TEAM_ABBREV.get(home_abbrev, home_abbrev.upper())
    away_team   = TEAM_ABBREV.get(away_abbrev, away_abbrev.upper())

    raw_text  = a_tag.get_text(" ", strip=True)
    raw_lower = raw_text.lower()
    tokens    = raw_lower.split()

    # --- Status ---
    if "final ot" in raw_lower or "final-ot" in raw_lower:
        status = "final OT"
    elif "final so" in raw_lower or "final-so" in raw_lower:
        status = "final SO"
    elif "final" in raw_lower:
        status = "final"
    else:
        status = "scheduled"

    # --- Score ---
    home_score = away_score = None
    if status != "scheduled":
        # Try space-separated: "1 4 final"
        for i, tok in enumerate(tokens[:-1]):
            if tok.isdigit() and tokens[i + 1].isdigit():
                home_score = int(tok)
                away_score = int(tokens[i + 1])
                break
        # Fallback: colon-separated "3:6" (Cup format)
        if home_score is None:
            cm = re.search(r"\b(\d{1,2}):(\d{1,2})\b", raw_text)
            if cm:
                home_score = int(cm.group(1))
                away_score = int(cm.group(2))

    # --- Date ---
    raw_date = None

    # Try DD.MM.YYYY in text
    dm = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", raw_text)
    if dm:
        raw_date = f"{dm.group(1)}.{dm.group(2)}.{dm.group(3)}"

    # Try month-name format: "11 apr 18:00"
    if raw_date is None:
        for i, tok in enumerate(tokens):
            if tok in _MONTHS and i > 0 and tokens[i - 1].isdigit():
                day_tok  = tokens[i - 1]
                time_tok = (tokens[i + 1]
                            if i + 1 < len(tokens) and re.match(r"\d{2}:\d{2}", tokens[i + 1])
                            else "")
                raw_date = f"{day_tok} {tok} {time_tok}".strip()
                break

    iso_date = _normalize_date(raw_date, season) if raw_date else None

    # If game has a score but was parsed as "scheduled" because "final" wasn't in
    # the block text, treat it as completed.
    # Historical games on the "all months" page show ONLY the score (e.g. "3:2 OT")
    # with no date and no "final" keyword.
    if status == "scheduled" and home_score is None:
        # Try colon score even without "final" keyword
        cm = re.search(r"\b(\d{1,2}):(\d{1,2})\b", raw_text)
        if cm:
            cand_home = int(cm.group(1))
            cand_away = int(cm.group(2))
            # Only treat as score if both values are plausible goal totals (< 25)
            if cand_home < 25 and cand_away < 25:
                # Mark as final if:
                #   (a) we have a date and it's in the past, OR
                #   (b) there is no date AND no time pattern (e.g. "HH:MM") in the text
                #       meaning the schedule page didn't show an upcoming time, so it's
                #       a completed historical game
                date_in_past = iso_date and iso_date[:10] < _TODAY
                no_upcoming_time = not re.search(r"\b\d{2}:\d{2}\b", raw_text) and not iso_date
                if date_in_past or no_upcoming_time:
                    home_score = cand_home
                    away_score = cand_away
                    # Detect OT/SO from suffix
                    if "so" in raw_lower:
                        status = "final SO"
                    elif "ot" in raw_lower:
                        status = "final OT"
                    else:
                        status = "final"

    return {
        "game_id":     game_id,
        "competition": competition,
        "season":      season,
        "home_team":   home_team,
        "away_team":   away_team,
        "home_score":  home_score,
        "away_score":  away_score,
        "status":      status,
        "date":        iso_date,
        "game_url":    f"{BASE_URL}/game/{game_id}-{home_abbrev}-{away_abbrev}",
    }


def parse_schedule_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Return list of fixture dicts parsed from one schedule page."""
    fixtures = []
    seen = set()
    for a in soup.find_all("a", href=_GAME_RE):
        fixture = _parse_game_link(a, competition, season)
        if fixture and fixture["game_id"] not in seen:
            seen.add(fixture["game_id"])
            fixtures.append(fixture)
    if not fixtures:
        logger.warning(
            "No game links found for %s. The page may use JavaScript rendering "
            "or the URL parameters changed.",
            competition,
        )
    return fixtures


def scrape_all_months(scraper_get_soup, base_schedule_url: str,
                      competition: str, season: str) -> list[dict]:
    """Fetch the full season schedule.

    Step 1: fetch id_month=999 (all months) to get the complete game list quickly.
    Step 2: fetch each calendar month individually to supplement dates — the
            all-months view omits dates for completed games.
    """
    # Step 1: all-months for complete coverage
    all_months_url = f"{base_schedule_url}&id_team=0&id_month=999"
    soup = scraper_get_soup(all_months_url)
    all_fixtures: dict[str, dict] = {}
    if soup is not None:
        for f in parse_schedule_page(soup, competition, season):
            all_fixtures[f["game_id"]] = f
        logger.info("[%s] all-months: %d fixtures", competition, len(all_fixtures))
    else:
        logger.warning("[%s] all-months fetch failed", competition)

    # Step 2: per-month sweep to pick up dates (all-months view omits them)
    _season_months = [9, 10, 11, 12, 1, 2, 3, 4]
    for month in _season_months:
        url  = f"{base_schedule_url}&id_team=0&id_month={month}"
        soup = scraper_get_soup(url)
        if soup is None:
            logger.warning("[%s] month=%d: fetch failed", competition, month)
            continue
        for f in parse_schedule_page(soup, competition, season):
            gid = f["game_id"]
            if gid not in all_fixtures:
                all_fixtures[gid] = f
            else:
                existing = all_fixtures[gid]
                if f.get("date") and not existing.get("date"):
                    existing["date"] = f["date"]
                if f.get("home_score") is not None and existing.get("home_score") is None:
                    existing["home_score"] = f["home_score"]
                    existing["away_score"] = f["away_score"]
                if f["status"] != "scheduled" and existing["status"] == "scheduled":
                    existing["status"] = f["status"]
        logger.info("[%s] month=%d: supplement done (total %d)",
                    competition, month, len(all_fixtures))

    if not all_fixtures:
        logger.warning("[%s] no fixtures found", competition)
    return list(all_fixtures.values())
