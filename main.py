"""Entry point: orchestrates all scraping passes."""

import argparse
import logging
import sys

import db
import events as events_mod
import fixtures as fixtures_mod
import scraper as scraper_mod
import season_stats as season_stats_mod
import team_stats as team_stats_mod
from config import DB_PATH, EVENT_URL, STATS_URLS


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("scraper.log", encoding="utf-8"),
        ],
    )


logger = logging.getLogger(__name__)


def run_fixtures_pass(conn, fixtures_only: bool = False) -> None:
    from config import FIXTURES_URL
    logger.info("=== FIXTURES PASS ===")
    soup = scraper_mod.get_soup(FIXTURES_URL)
    if soup is None:
        logger.error("Failed to fetch fixtures page — aborting fixtures pass")
        return

    fixtures = fixtures_mod.parse_fixtures_page(soup)
    if not fixtures:
        logger.warning("No fixtures parsed from page")
        return

    for f in fixtures:
        comp_id = db.get_competition_id(conn, f["competition"])
        home_id = db.upsert_team(conn, f["home_team_slug"], f["home_team_name"])
        away_id = db.upsert_team(conn, f["away_team_slug"], f["away_team_name"])
        db.upsert_fixture(
            conn,
            event_id=f["event_id"],
            competition_id=comp_id,
            date=f["date"],
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=f["home_score"],
            away_score=f["away_score"],
            status=f["status"],
        )
    conn.commit()

    final = sum(1 for f in fixtures if f["status"] == "final")
    scheduled = len(fixtures) - final
    logger.info("Upserted %d fixtures (%d final, %d scheduled)", len(fixtures), final, scheduled)


def run_event_detail_pass(conn, force_event_id: int | None = None) -> None:
    logger.info("=== EVENT DETAIL PASS ===")

    if force_event_id is not None:
        todo = [force_event_id]
        logger.info("Force-fetching event %d", force_event_id)
    else:
        todo = db.get_unscraped_event_ids(conn)
        logger.info("%d new completed event(s) to scrape", len(todo))

    scraped = skipped = 0
    for event_id in todo:
        url = EVENT_URL.format(event_id)
        soup = scraper_mod.get_soup(url)
        if soup is None:
            logger.warning("Skipping event %d (no response)", event_id)
            skipped += 1
            continue

        data = events_mod.parse_event_page(event_id, soup)

        try:
            # Write all event data in a single transaction
            conn.execute("BEGIN")

            if data.get("date"):
                db.update_fixture_date(conn, event_id, data["date"])

            for ps in data["period_scores"]:
                team_id = db.upsert_team(conn, ps["team_slug"], ps["team_name"])
                db.upsert_period_scores(
                    conn, event_id, team_id,
                    ps["period_1"], ps["period_2"], ps["period_3"],
                    ps["ppg"], ps["ppo"], ps["outcome"],
                )

            for p in data["player_stats"]:
                team_id = db.upsert_team(conn, p["team_slug"], p["team_name"])
                player_id = db.upsert_player(conn, p["player_slug"], p["player_name"])
                db.upsert_event_player_stat(
                    conn, event_id, team_id, player_id,
                    p["jersey_number"], p["position"],
                    p["goals"], p["assists"], p["pim"],
                    p["shots_against"], p["saves"], p["goals_against"],
                    p["toi"],
                )

            conn.commit()
            scraped += 1
            logger.info(
                "Event %d: %d period rows, %d player rows",
                event_id, len(data["period_scores"]), len(data["player_stats"]),
            )
        except Exception as exc:
            conn.rollback()
            logger.error("Event %d: write failed — %s", event_id, exc, exc_info=True)
            skipped += 1

    logger.info("Event detail pass complete: %d scraped, %d skipped", scraped, skipped)


def run_date_backfill_pass(conn) -> None:
    """Fetch event pages for completed fixtures that have no date recorded."""
    todo = db.get_undated_event_ids(conn)
    if not todo:
        return
    logger.info("=== DATE BACKFILL PASS (%d events) ===", len(todo))
    updated = 0
    for event_id in todo:
        url = EVENT_URL.format(event_id)
        soup = scraper_mod.get_soup(url)
        if soup is None:
            continue
        data = events_mod.parse_event_page(event_id, soup)
        if data.get("date"):
            db.update_fixture_date(conn, event_id, data["date"])
            updated += 1
    conn.commit()
    logger.info("Date backfill complete: %d dates updated", updated)


def run_season_stats_pass(conn) -> None:
    logger.info("=== SEASON STATS PASS ===")

    for comp_name, urls in STATS_URLS.items():
        comp_id = db.get_competition_id(conn, comp_name)

        # Skaters
        soup = scraper_mod.get_soup(urls["skaters"])
        if soup:
            rows = season_stats_mod.parse_skater_list(soup)
            for r in rows:
                team_id = db.upsert_team(conn, r["team_slug"], r["team_name"])
                player_id = db.upsert_player(conn, r["player_slug"], r["player_name"])
                db.upsert_season_skater(
                    conn, comp_id, player_id, team_id,
                    r["position"], r["gp"], r["goals"], r["assists"],
                    r["total_points"], r["pim"],
                )
            conn.commit()
            logger.info("[%s] Upserted %d skater season stats", comp_name, len(rows))
        else:
            logger.warning("[%s] Failed to fetch skater stats page", comp_name)

        # Netminders
        soup = scraper_mod.get_soup(urls["netminders"])
        if soup:
            rows = season_stats_mod.parse_netminder_list(soup)
            for r in rows:
                team_id = db.upsert_team(conn, r["team_slug"], r["team_name"])
                player_id = db.upsert_player(conn, r["player_slug"], r["player_name"])
                db.upsert_season_netminder(
                    conn, comp_id, player_id, team_id,
                    r["gp"], r["shots_against"], r["saves"], r["goals_against"],
                    r["save_pct"], r["gaa"], r["toi"],
                )
            conn.commit()
            logger.info("[%s] Upserted %d netminder season stats", comp_name, len(rows))
        else:
            logger.warning("[%s] Failed to fetch netminder stats page", comp_name)

        # Team stats (SNL only for now)
        if "teams" in urls:
            soup = scraper_mod.get_soup(urls["teams"])
            if soup:
                rows = team_stats_mod.parse_team_stats(soup)
                for r in rows:
                    team_id = db.upsert_team(conn, r["team_slug"], r["team_name"])
                    db.upsert_team_season_stat(conn, comp_id, team_id, **{
                        k: v for k, v in r.items()
                        if k not in ("team_slug", "team_name")
                    })
                conn.commit()
                logger.info("[%s] Upserted %d team stats rows", comp_name, len(rows))
            else:
                logger.warning("[%s] Failed to fetch team stats page", comp_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape SIHA SNL 2025-26 ice hockey stats into a SQLite database."
    )
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database file")
    parser.add_argument(
        "--fixtures-only", action="store_true",
        help="Only run the fixtures pass (skip event detail and season stats)"
    )
    parser.add_argument(
        "--stats-only", action="store_true",
        help="Only run fixtures + season stats passes (skip event detail scraping)"
    )
    parser.add_argument(
        "--event", type=int, metavar="ID",
        help="Force-fetch a single event by ID (for debugging)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable DEBUG logging"
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger.info("Starting SIHA scraper — db: %s", args.db)

    conn = db.get_connection(args.db)
    db.init_schema(conn)

    try:
        run_fixtures_pass(conn)

        if not args.fixtures_only:
            if not args.stats_only:
                run_event_detail_pass(conn, force_event_id=args.event)
            run_date_backfill_pass(conn)
            run_season_stats_pass(conn)

    finally:
        conn.close()

    logger.info("Done.")


if __name__ == "__main__":
    main()
