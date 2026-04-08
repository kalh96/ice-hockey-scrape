"""Entry point for the WNIHL scraper.

Run with:
  python wnihl_main.py [--db PATH] [--fixtures-only] [-v]

What it does:
  1. Creates all wnihl_* tables in siha.db (safe if already exist)
  2. Scrapes fixture/results pages → wnihl_fixtures
  3. Scrapes standings pages → wnihl_standings
  4. Scrapes player stats pages → wnihl_player_stats

EIHL and SNL tables are never touched.
"""

import argparse
import logging
import sqlite3
import sys

import wnihl_db
import wnihl_fixtures as fixtures_mod
import wnihl_standings as standings_mod
import wnihl_stats as stats_mod
from wnihl_config import BASE_URL, ASSOC_CLIENT, COMPETITIONS, CURRENT_SEASON
from wnihl_scraper import get_soup

logger = logging.getLogger(__name__)


def _comp_url(comp_id: str, action: str) -> str:
    return f"{BASE_URL}/comp_info.cgi?a={action}&compID={comp_id}&c={ASSOC_CLIENT}"


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("wnihl_scraper.log", encoding="utf-8"),
        ],
    )


def run_fixtures_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== WNIHL FIXTURES PASS ===")
    for comp_key, comp_info in COMPETITIONS.items():
        comp_id = comp_info["comp_id"]
        url = _comp_url(comp_id, "FIXTURE")
        soup = get_soup(url)
        if soup is None:
            logger.error("[%s] Failed to fetch fixtures page", comp_key)
            continue
        fixtures = fixtures_mod.parse_fixtures_page(soup, comp_key, CURRENT_SEASON)
        for f in fixtures:
            wnihl_db.upsert_fixture(conn, **f)
        conn.commit()
        logger.info("[%s] Upserted %d fixtures", comp_key, len(fixtures))


def run_standings_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== WNIHL STANDINGS PASS ===")
    for comp_key, comp_info in COMPETITIONS.items():
        comp_id = comp_info["comp_id"]
        url = _comp_url(comp_id, "LADDER")
        soup = get_soup(url)
        if soup is None:
            logger.error("[%s] Failed to fetch standings page", comp_key)
            continue
        rows = standings_mod.parse_standings_page(soup, comp_key, CURRENT_SEASON)
        for row in rows:
            wnihl_db.upsert_standing(conn, **row)
        conn.commit()
        logger.info("[%s] Upserted %d standing rows", comp_key, len(rows))


def run_stats_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== WNIHL STATS PASS ===")
    for comp_key, comp_info in COMPETITIONS.items():
        comp_id = comp_info["comp_id"]
        url = _comp_url(comp_id, "STATS")
        soup = get_soup(url)
        if soup is None:
            logger.error("[%s] Failed to fetch stats page", comp_key)
            continue
        rows = stats_mod.parse_stats_page(soup, comp_key, CURRENT_SEASON)
        for row in rows:
            wnihl_db.upsert_player_stat(conn, **row)
        conn.commit()
        logger.info("[%s] Upserted %d player stat rows", comp_key, len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape WNIHL data into siha.db")
    parser.add_argument("--db",            default="siha.db",  help="SQLite DB path")
    parser.add_argument("--fixtures-only", action="store_true", help="Only run fixtures pass")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger.info("Starting WNIHL scraper -- db: %s", args.db)

    import db as snl_db
    conn = snl_db.get_connection(args.db)
    wnihl_db.init_wnihl_schema(conn)

    try:
        run_fixtures_pass(conn)
        if not args.fixtures_only:
            run_standings_pass(conn)
            run_stats_pass(conn)
    finally:
        conn.close()

    logger.info("WNIHL scraper done.")


if __name__ == "__main__":
    main()
