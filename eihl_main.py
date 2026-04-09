"""Entry point for the EIHL scraper.

Run with:
  python eihl_main.py [--db PATH] [--fixtures-only] [--stats-only] [-v]

What it does:
  1. Creates all eihl_* tables in siha.db (safe if already exist)
  2. Scrapes League and Cup schedule pages → eihl_fixtures
  3. Scrapes game detail pages (events + player stats) for new completed games
  4. Scrapes League and Cup standings → eihl_standings
  5. Scrapes League and Cup skater/goalie season stats → eihl_skater_stats / eihl_goalie_stats

SNL tables are never touched.
"""

import argparse
import logging
import sqlite3
import sys

import eihl_db
import eihl_fixtures  as fixtures_mod
import eihl_game_detail as detail_mod
import eihl_standings as standings_mod
import eihl_stats     as stats_mod
from eihl_config import (
    BASE_URL, CURRENT_SEASON, DB_PATH,
    EIHL_LEAGUE_SEASON_ID, EIHL_CUP_SEASON_ID,
    EIHL_LEAGUE_STAGE_ID,  EIHL_CUP_STAGE_ID,
    EIHL_LEAGUE_PLAYOFF_START, EIHL_CUP_KNOCKOUT_GAME_IDS,
)
from eihl_scraper import get_soup

logger = logging.getLogger(__name__)

SCHEDULE_URL_LEAGUE = f"{BASE_URL}/schedule?id_season={EIHL_LEAGUE_SEASON_ID}"
SCHEDULE_URL_CUP    = f"{BASE_URL}/schedule?id_season={EIHL_CUP_SEASON_ID}"

STANDINGS_URL_LEAGUE = f"{BASE_URL}/standings/2025/{EIHL_LEAGUE_SEASON_ID}-elite-ice-hockey-league"
STANDINGS_URL_CUP    = f"{BASE_URL}/standings/2025/{EIHL_CUP_SEASON_ID}-challenge-cup"

SKATER_URL_LEAGUE  = f"{BASE_URL}/stats/players?id_season={EIHL_LEAGUE_SEASON_ID}&id_stage={EIHL_LEAGUE_STAGE_ID}"
GOALIE_URL_LEAGUE  = f"{BASE_URL}/stats/goalies?id_season={EIHL_LEAGUE_SEASON_ID}&id_stage={EIHL_LEAGUE_STAGE_ID}"
SKATER_URL_CUP     = f"{BASE_URL}/stats/players?id_season={EIHL_CUP_SEASON_ID}&id_stage={EIHL_LEAGUE_STAGE_ID}"
GOALIE_URL_CUP     = f"{BASE_URL}/stats/goalies?id_season={EIHL_CUP_SEASON_ID}&id_stage={EIHL_LEAGUE_STAGE_ID}"


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("eihl_scraper.log", encoding="utf-8"),
        ],
    )


# ---------------------------------------------------------------------------
# Passes
# ---------------------------------------------------------------------------

def run_fixtures_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== FIXTURES PASS ===")

    for competition, url in [("League", SCHEDULE_URL_LEAGUE), ("Cup", SCHEDULE_URL_CUP)]:
        fixtures = fixtures_mod.scrape_all_months(get_soup, url, competition, CURRENT_SEASON)
        for f in fixtures:
            # Determine phase for phase-aware display
            if competition == "League":
                d = f.get("date") or ""
                f["phase"] = "playoff" if d >= EIHL_LEAGUE_PLAYOFF_START else "regular"
            else:  # Cup
                f["phase"] = "knockout" if f["game_id"] in EIHL_CUP_KNOCKOUT_GAME_IDS else "group"
            eihl_db.upsert_fixture(conn, **f)
        conn.commit()
        logger.info("[%s] Upserted %d fixtures", competition, len(fixtures))


def run_game_detail_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== GAME DETAIL PASS ===")

    pending = eihl_db.get_games_needing_detail(conn)
    logger.info("%d game(s) need detail scraping", len(pending))

    scraped = skipped = 0
    for game in pending:
        gid  = game["game_id"]
        gurl = game["game_url"]
        home = game["home_team"]
        away = game["away_team"]

        logger.info("Scraping game %s: %s vs %s", gid, home, away)

        # Main page
        soup_main = get_soup(gurl)
        if soup_main:
            detail = detail_mod.parse_main_page(soup_main)
            eihl_db.update_fixture_detail(conn, gid, **detail)
            conn.commit()

        # Events page
        soup_ev = get_soup(gurl + "/events")
        if soup_ev:
            events = detail_mod.parse_events_page(soup_ev, home, away)
            eihl_db.replace_game_events(conn, gid, events)
            conn.commit()
            logger.info("  Events: %d rows", len(events))
        else:
            logger.warning("  Could not fetch events page for game %s", gid)

        # Stats page
        soup_st = get_soup(gurl + "/stats")
        if soup_st:
            player_stats = detail_mod.parse_stats_page(soup_st, home, away)
            for ps in player_stats:
                if ps.get("player_id"):
                    eihl_db.upsert_game_player_stat(conn, game_id=gid, **ps)
            conn.commit()
            logger.info("  Player stats: %d rows", len(player_stats))
        else:
            logger.warning("  Could not fetch stats page for game %s", gid)

        scraped += 1

    logger.info("Game detail pass: %d scraped, %d skipped", scraped, skipped)


def run_standings_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== STANDINGS PASS ===")

    for competition, url in [("League", STANDINGS_URL_LEAGUE), ("Cup", STANDINGS_URL_CUP)]:
        soup = get_soup(url)
        if soup is None:
            logger.error("[%s] Failed to fetch standings page", competition)
            continue

        rows = standings_mod.parse_standings_page(soup, competition, CURRENT_SEASON)
        for row in rows:
            eihl_db.upsert_standing(conn, **row)
        conn.commit()
        logger.info("[%s] Upserted %d standing rows", competition, len(rows))


def run_stats_pass(conn: sqlite3.Connection) -> None:
    logger.info("=== SEASON STATS PASS ===")

    for competition, skater_url, goalie_url in [
        ("League", SKATER_URL_LEAGUE, GOALIE_URL_LEAGUE),
        ("Cup",    SKATER_URL_CUP,    GOALIE_URL_CUP),
    ]:
        # Skaters
        skaters = stats_mod.scrape_all_pages(
            get_soup, skater_url, stats_mod.parse_skater_stats_page,
            competition, CURRENT_SEASON,
        )
        for s in skaters:
            if s.get("player_id"):
                eihl_db.upsert_skater_stat(conn, **s)
        conn.commit()
        logger.info("[%s] Upserted %d skater rows", competition, len(skaters))

        # Goalies
        goalies = stats_mod.scrape_all_pages(
            get_soup, goalie_url, stats_mod.parse_goalie_stats_page,
            competition, CURRENT_SEASON,
        )
        for g in goalies:
            if g.get("player_id"):
                eihl_db.upsert_goalie_stat(conn, **g)
        conn.commit()
        logger.info("[%s] Upserted %d goalie rows", competition, len(goalies))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape EIHL stats into siha.db")
    parser.add_argument("--db",            default=DB_PATH,    help="SQLite DB path")
    parser.add_argument("--fixtures-only", action="store_true", help="Only run fixtures pass")
    parser.add_argument("--stats-only",    action="store_true", help="Skip game detail scraping")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger.info("Starting EIHL scraper — db: %s", args.db)

    import db as snl_db
    conn = snl_db.get_connection(args.db)
    eihl_db.init_eihl_schema(conn)

    try:
        run_fixtures_pass(conn)

        if not args.fixtures_only:
            if not args.stats_only:
                run_game_detail_pass(conn)
            run_standings_pass(conn)
            run_stats_pass(conn)

    finally:
        conn.close()

    logger.info("EIHL scraper done.")


if __name__ == "__main__":
    main()
