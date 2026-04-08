"""Parse EIHL season skater and goalie stats pages.

Pages are paginated (50 rows per page).  The scraper follows "Next" links until
no more are found.

URLs (League):
  /stats/players?id_season=43&id_stage=1
  /stats/goalies?id_season=43&id_stage=1

URLs (Cup) — stage ID to be verified on first run:
  /stats/players?id_season=43&id_stage=2
  /stats/goalies?id_season=43&id_stage=2
"""

import logging
import re

from bs4 import BeautifulSoup

from eihl_config import BASE_URL

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


_PLAYER_RE = re.compile(r"/player/(\d+)-")


def _player_id_from_href(href: str | None) -> str | None:
    if not href:
        return None
    m = _PLAYER_RE.search(href)
    return m.group(1) if m else None


def _next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    """Return the URL of the next pagination page, or None if on last page."""
    # Look for a link whose text is "Next" or "›" or "»"
    for a in soup.find_all("a"):
        txt = a.get_text(strip=True).lower()
        if txt in ("next", "›", "»", ">", "next »"):
            href = a.get("href", "")
            if href.startswith("http"):
                return href
            if href.startswith("/"):
                return BASE_URL + href
    return None


def parse_skater_stats_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Parse one page of skater stats. Returns list of stat dicts."""
    rows    = []
    table   = soup.find("table")
    if not table:
        logger.warning("No table found on skater stats page")
        return rows

    headers = [th.get_text(strip=True).upper()
               for th in (table.find("thead") or table).find_all(["th", "td"])]

    def _col(name: str, cells: list) -> str | None:
        try:
            return cells[headers.index(name)]
        except (ValueError, IndexError):
            return None

    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 5:
            continue

        player_a = tr.find("a", href=_PLAYER_RE)
        player_id = _player_id_from_href(player_a["href"] if player_a else None)
        player_name = player_a.get_text(" ", strip=True) if player_a else _col("PLAYER", cells)
        if not player_name:
            continue

        rows.append({
            "season":      season,
            "competition": competition,
            "player_name": re.sub(r"^#\d+\s*", "", player_name).strip(),
            "player_id":   player_id,
            "team":        _col("TEAM", cells) or "",
            "position":    _col("POSITION", cells) or _col("POS", cells),
            "gp":          _int(_col("GP", cells)),
            "g":           _int(_col("G", cells)),
            "a":           _int(_col("A", cells)),
            "pts":         _int(_col("PTS", cells)),
            "pim":         _int(_col("PIM", cells)),
            "ppg":         _int(_col("PPG", cells)),
            "shg":         _int(_col("SHG", cells)),
            "plus_minus":  _int(_col("+/-", cells)),
            "sog":         _int(_col("SOG", cells)),
            "s_pct":       _float(_col("S", cells)) or _float(_col("S%", cells)),
            "fow":         _int(_col("FOW", cells)),
            "fol":         _int(_col("FOL", cells)),
        })

    return rows


def parse_goalie_stats_page(soup: BeautifulSoup, competition: str, season: str) -> list[dict]:
    """Parse one page of goalie stats. Returns list of stat dicts."""
    rows  = []
    table = soup.find("table")
    if not table:
        logger.warning("No table found on goalie stats page")
        return rows

    headers = [th.get_text(strip=True).upper()
               for th in (table.find("thead") or table).find_all(["th", "td"])]

    def _col(name: str, cells: list) -> str | None:
        try:
            return cells[headers.index(name)]
        except (ValueError, IndexError):
            return None

    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 5:
            continue

        player_a    = tr.find("a", href=_PLAYER_RE)
        player_id   = _player_id_from_href(player_a["href"] if player_a else None)
        player_name = player_a.get_text(" ", strip=True) if player_a else _col("PLAYER", cells)
        if not player_name:
            continue

        rows.append({
            "season":      season,
            "competition": competition,
            "player_name": re.sub(r"^#\d+\s*", "", player_name).strip(),
            "player_id":   player_id,
            "team":        _col("TEAM", cells) or "",
            "gp":          _int(_col("GP", cells)),
            "w":           _int(_col("W", cells)),
            "l":           _int(_col("L", cells)),
            "so":          _int(_col("SO", cells)),
            "sa":          _int(_col("SA", cells)),
            "ga":          _int(_col("GA", cells)),
            "min_played":  _col("MIN", cells),
            "gaa":         _float(_col("GAA", cells)),
            "svs_pct":     _float(_col("SVS%", cells)),
            "pim":         _int(_col("PIM", cells)),
        })

    return rows


def scrape_all_pages(scraper_get_soup, start_url: str, parse_fn,
                     competition: str, season: str) -> list[dict]:
    """Fetch all pages for a paginated stats URL and return combined rows."""
    all_rows   = []
    url        = start_url
    page_count = 0

    while url:
        soup = scraper_get_soup(url)
        if soup is None:
            logger.warning("Failed to fetch stats page: %s", url)
            break
        rows = parse_fn(soup, competition, season)
        all_rows.extend(rows)
        page_count += 1
        logger.debug("Page %d: %d rows (total so far: %d)", page_count, len(rows), len(all_rows))
        url = _next_page_url(soup, url)

    logger.info("Scraped %d stat rows across %d page(s)", len(all_rows), page_count)
    return all_rows
