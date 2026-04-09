"""Parse EIHL individual game pages.

Three sub-pages are fetched per game:
  /game/{id}-{home}-{away}          → venue, attendance, period scores
  /game/{id}-{home}-{away}/events   → goals and penalties by period
  /game/{id}-{home}-{away}/stats    → per-player per-game stats
"""

import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_PLAYER_RE = re.compile(r"/player/(\d+)-")


def _int(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.strip().replace(",", "")
    return int(s) if s.isdigit() else None


def _float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.strip().replace("%", ""))
    except (ValueError, AttributeError):
        return None


def _player_id_from_href(href: str | None) -> str | None:
    if not href:
        return None
    m = _PLAYER_RE.search(href)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Main game page  →  venue, attendance, period scores
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})"
    r"(?:,\s*(\d{2}:\d{2}))?",
    re.IGNORECASE,
)
_MONTH_NUM_GD = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _parse_game_date(soup: BeautifulSoup) -> str | None:
    """Extract game date from the detail page header, e.g. '18 Mar 2026, 19:30'."""
    # Primary: the dedicated date badge div
    badge = soup.find("div", class_=lambda c: c and "text-gray" in c and "font-size-small" in c)
    candidates = [badge.get_text(" ", strip=True)] if badge else []
    # Fallback: scan full text
    candidates.append(soup.get_text(" ", strip=True)[:2000])
    for text in candidates:
        m = _DATE_RE.search(text)
        if m:
            day, mon, year, time = m.groups()
            month_num = _MONTH_NUM_GD.get(mon.lower(), "01")
            return f"{year}-{month_num}-{int(day):02d} {time or '00:00'}"
    return None


def parse_main_page(soup: BeautifulSoup) -> dict:
    result = {
        "date": _parse_game_date(soup),
        "venue": None, "attendance": None,
        "home_p1": None, "away_p1": None,
        "home_p2": None, "away_p2": None,
        "home_p3": None, "away_p3": None,
        "home_ot": None, "away_ot": None,
    }

    full_text = soup.get_text(" ", strip=True)

    # --- Attendance: look for a number near "attendance" ---
    att_m = re.search(r"attendance[:\s]+([0-9,]+)", full_text, re.IGNORECASE)
    if att_m:
        result["attendance"] = _int(att_m.group(1))

    # --- Venue: text near "arena" or "ice" ---
    venue_m = re.search(r"([A-Z][A-Za-z\s]+(?:Arena|Rink|Ice|Centre|Center))", full_text)
    if venue_m:
        result["venue"] = venue_m.group(1).strip()

    # --- Period scores: look for "N N | N N | N N" pattern ---
    # Format is pairs of numbers separated by whitespace/pipes representing
    # period-by-period scores (home away | home away | home away [| home away for OT])
    period_m = re.search(
        r"(\d+)\s+(\d+)\s*\|\s*(\d+)\s+(\d+)\s*\|\s*(\d+)\s+(\d+)"
        r"(?:\s*\|\s*(\d+)\s+(\d+))?",
        full_text,
    )
    if period_m:
        result.update({
            "home_p1": int(period_m.group(1)), "away_p1": int(period_m.group(2)),
            "home_p2": int(period_m.group(3)), "away_p2": int(period_m.group(4)),
            "home_p3": int(period_m.group(5)), "away_p3": int(period_m.group(6)),
            "home_ot": _int(period_m.group(7)), "away_ot": _int(period_m.group(8)),
        })
    else:
        logger.debug("No period score pattern found on main game page")

    return result


# ---------------------------------------------------------------------------
# Events page  →  goals and penalties
# ---------------------------------------------------------------------------

def _current_period(heading_text: str) -> int | None:
    t = heading_text.lower()
    if "1st" in t or "first" in t or "period 1" in t:
        return 1
    if "2nd" in t or "second" in t or "period 2" in t:
        return 2
    if "3rd" in t or "third" in t or "period 3" in t:
        return 3
    if "overtime" in t or "ot" in t or "period 4" in t:
        return None  # OT stored as NULL period
    return None


def _goal_type_from_text(text: str) -> str | None:
    t = text.lower()
    if "power-play" in t or "powerplay" in t or "ppg" in t:
        return "PPG"
    if "short" in t or "shorthanded" in t or "shg" in t:
        return "SHG"
    if "empty" in t or "en" in t:
        return "EN"
    return None


def _extract_player_from_link(a_tag) -> tuple[str | None, str | None]:
    """Return (player_name, player_id) from a /player/ link."""
    if a_tag is None:
        return None, None
    href   = a_tag.get("href", "")
    pid    = _player_id_from_href(href)
    name   = a_tag.get_text(strip=True)
    # Strip jersey number prefix like "#19 Kristoff Kontos" → "Kristoff Kontos"
    name   = re.sub(r"^#\d+\s*", "", name).strip()
    return (name or None), pid


def parse_events_page(soup: BeautifulSoup, home_team: str, away_team: str) -> list[dict]:
    """Return list of event dicts (goals and penalties)."""
    events    = []
    period    = None

    # Walk every element looking for period headers and event blocks
    for tag in soup.find_all(True):
        tag_text = tag.get_text(strip=True)

        # Period heading detection (h2/h3/h4 or divs containing "period" text)
        if tag.name in ("h2", "h3", "h4") or (
            tag.name in ("div", "span", "p")
            and re.search(r"\b(1st|2nd|3rd|first|second|third|overtime)\b.*period"
                          r"|\bperiod\b.*\b(1st|2nd|3rd|first|second|third|overtime)\b",
                          tag_text, re.IGNORECASE)
            and len(tag_text) < 40
        ):
            p = _current_period(tag_text)
            if p is not None or "overtime" in tag_text.lower() or "ot" in tag_text.lower():
                period = p
                continue

        # Goal events: look for blocks containing a player link + time + assists
        player_links = tag.find_all("a", href=_PLAYER_RE)
        if len(player_links) >= 1 and tag.name in ("div", "li", "tr", "section", "article"):
            block_text = tag.get_text(" ", strip=True)

            # Time pattern like 41:30
            time_m = re.search(r"\b(\d{1,2}:\d{2})\b", block_text)
            time_str = time_m.group(1) if time_m else None

            # Skip if this is a penalty block (contains penalty keywords but not a time)
            is_penalty = any(
                kw in block_text.lower()
                for kw in ("hooking", "tripping", "roughing", "fighting",
                           "interference", "boarding", "charging", "slashing",
                           "elbowing", "high-sticking", "delay", "unsportsmanlike",
                           "misconduct", "cross-checking", "holding")
            )
            is_goal = time_str and not is_penalty

            if is_goal:
                scorer_link = player_links[0]
                scorer_name, scorer_id = _extract_player_from_link(scorer_link)

                # Determine team: look for team name in block text
                team = None
                for tname in (home_team, away_team):
                    if tname.lower() in block_text.lower():
                        team = tname
                        break

                # Assists: remaining player links after the scorer
                assist1_name = assist1_id = assist2_name = assist2_id = None
                if len(player_links) > 1:
                    assist1_name, assist1_id = _extract_player_from_link(player_links[1])
                if len(player_links) > 2:
                    assist2_name, assist2_id = _extract_player_from_link(player_links[2])

                goal_type = _goal_type_from_text(block_text)

                events.append({
                    "period":         period,
                    "time_in_period": time_str,
                    "event_type":     "goal",
                    "team":           team,
                    "player_name":    scorer_name,
                    "player_id":      scorer_id,
                    "assist1_name":   assist1_name,
                    "assist1_id":     assist1_id,
                    "assist2_name":   assist2_name,
                    "assist2_id":     assist2_id,
                    "goal_type":      goal_type,
                    "penalty_type":   None,
                    "penalty_minutes": None,
                })

            elif is_penalty and player_links:
                pname, pid = _extract_player_from_link(player_links[0])
                # Extract penalty minutes from "2-minute" or "5 minute" pattern
                mins_m = re.search(r"\b(\d+)[-\s]?min", block_text, re.IGNORECASE)
                mins = int(mins_m.group(1)) if mins_m else None

                # Extract penalty type (first known keyword found)
                pen_type = None
                for kw in ("Hooking", "Tripping", "Roughing", "Fighting",
                           "Interference", "Boarding", "Charging", "Slashing",
                           "Elbowing", "High-Sticking", "Delay of Game",
                           "Unsportsmanlike", "Misconduct", "Cross-Checking", "Holding"):
                    if kw.lower() in block_text.lower():
                        pen_type = kw
                        break

                team = None
                for tname in (home_team, away_team):
                    if tname.lower() in block_text.lower():
                        team = tname
                        break

                events.append({
                    "period":          period,
                    "time_in_period":  time_str,
                    "event_type":      "penalty",
                    "team":            team,
                    "player_name":     pname,
                    "player_id":       pid,
                    "assist1_name":    None, "assist1_id":    None,
                    "assist2_name":    None, "assist2_id":    None,
                    "goal_type":       None,
                    "penalty_type":    pen_type,
                    "penalty_minutes": mins,
                })

    # Deduplicate: the parser may encounter the same event in both a parent
    # container (period/team=None) and the actual event div (period/team set).
    # Group by (type, player, time) and keep the most-informative version.
    from collections import defaultdict
    grouped: dict[tuple, list] = defaultdict(list)
    for ev in events:
        base_key = (
            ev["event_type"],
            ev["player_id"] or ev["player_name"],
            ev["time_in_period"],
        )
        grouped[base_key].append(ev)

    deduped = []
    for evs in grouped.values():
        best = max(evs, key=lambda e: (
            e["period"] is not None,
            e["team"] is not None,
            e["assist1_name"] is not None,
        ))
        deduped.append(best)

    logger.debug("Parsed %d events (%d after dedup)", len(events), len(deduped))
    return deduped


# ---------------------------------------------------------------------------
# Stats page  →  per-player game stats
# ---------------------------------------------------------------------------

def _parse_stat_table(table, team_name: str, position_type: str) -> list[dict]:
    """Parse one HTML table (skaters or goalies) for a given team."""
    rows = []
    headers = []

    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True).upper() for th in thead.find_all(["th", "td"])]

    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or len(cells) < 3:
            continue

        # Extract player link for ID and name
        player_a = tr.find("a", href=_PLAYER_RE)
        pname, pid = _extract_player_from_link(player_a)
        if not pname:
            pname = cells[1] if len(cells) > 1 else None

        def _col(name: str) -> str | None:
            """Get cell value by header name."""
            try:
                idx = headers.index(name)
                return cells[idx] if idx < len(cells) else None
            except ValueError:
                return None

        jersey   = _col("JERSEY") or _col("#") or cells[0]
        position = _col("POSITION") or _col("POS") or position_type

        if position_type == "GK":
            rows.append({
                "team":         team_name,
                "player_name":  pname,
                "player_id":    pid,
                "jersey":       jersey,
                "position":     "GK",
                "goals":        None, "assists": None, "pim": _int(_col("PIM")),
                "ppg":          None, "shg":     None, "plus_minus": None,
                "sog":          None, "fow":     None, "fol":        None,
                "bs":           None, "toi":     None,
                "shots_against": _int(_col("SA")),
                "saves":         _int(_col("SVS")) or _int(_col("SV")),
                "goals_against": _int(_col("GA")),
                "svs_pct":       _float(_col("SVS%")),
                "min_played":    _col("MIN"),
            })
        else:
            rows.append({
                "team":          team_name,
                "player_name":   pname,
                "player_id":     pid,
                "jersey":        jersey,
                "position":      position,
                "goals":         _int(_col("G")),
                "assists":       _int(_col("A")),
                "pim":           _int(_col("PIM")),
                "ppg":           _int(_col("PPG")),
                "shg":           _int(_col("SHG")),
                "plus_minus":    _int(_col("+/-")),
                "sog":           _int(_col("SOG")),
                "fow":           _int(_col("FOW")),
                "fol":           _int(_col("FOL")),
                "bs":            _int(_col("BS")),
                "toi":           _col("TOI"),
                "shots_against": None,
                "saves":         None,
                "goals_against": None,
                "svs_pct":       None,
                "min_played":    None,
            })
    return rows


def parse_stats_page(soup: BeautifulSoup, home_team: str, away_team: str) -> list[dict]:
    """Return flat list of per-player stat dicts for both teams."""
    stats = []

    # The page has section headings with team names above each table group.
    # Walk sections; each table belongs to the last-seen team heading.
    current_team = None

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "table", "div"]):
        tag_text = tag.get_text(strip=True)

        # Team name detection from headings
        if tag.name in ("h1", "h2", "h3", "h4"):
            for tname in (home_team, away_team):
                if tname.lower() in tag_text.lower():
                    current_team = tname
                    break

        if tag.name == "table" and current_team:
            # Determine if this is a goalie table by header content
            headers_text = tag.find("thead").get_text(" ") if tag.find("thead") else ""
            is_goalie = any(h in headers_text.upper() for h in ("SVS%", "GAA", "MIN", "SA"))
            pos_type  = "GK" if is_goalie else "F"
            rows      = _parse_stat_table(tag, current_team, pos_type)
            stats.extend(rows)

    logger.debug("Parsed %d player stat rows from stats page", len(stats))
    return stats
