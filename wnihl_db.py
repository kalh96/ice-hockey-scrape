"""WNIHL database schema and upsert helpers.

All tables are prefixed with wnihl_ and live in the shared siha.db.
No existing SNL or EIHL tables are touched.
"""

import sqlite3
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_wnihl_schema(conn: sqlite3.Connection) -> None:
    """Create all WNIHL tables if they do not exist. Safe to re-run."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wnihl_fixtures (
            fixture_id  TEXT PRIMARY KEY,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,   -- 'Elite', '1 North', '1 South'
            date        TEXT,            -- ISO YYYY-MM-DD HH:MM
            home_team   TEXT NOT NULL,
            away_team   TEXT NOT NULL,
            home_score  INTEGER,
            away_score  INTEGER,
            status      TEXT NOT NULL DEFAULT 'scheduled',
            venue       TEXT,
            round       TEXT,
            game_url    TEXT,
            scraped_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wnihl_standings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,
            team        TEXT NOT NULL,
            pos         INTEGER,
            gp          INTEGER,
            w           INTEGER,
            l           INTEGER,
            d           INTEGER,
            gf          INTEGER,
            ga          INTEGER,
            pts         INTEGER,
            scraped_at  TEXT NOT NULL,
            UNIQUE (season, competition, team)
        );

        CREATE TABLE IF NOT EXISTS wnihl_player_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team        TEXT NOT NULL,
            games       INTEGER,
            goals       INTEGER,
            assists     INTEGER,
            points      INTEGER,
            scraped_at  TEXT NOT NULL,
            UNIQUE (season, competition, player_name, team)
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_fixture(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO wnihl_fixtures
            (fixture_id, season, competition, date, home_team, away_team,
             home_score, away_score, status, venue, round, game_url, scraped_at)
        VALUES
            (:fixture_id, :season, :competition, :date, :home_team, :away_team,
             :home_score, :away_score, :status, :venue, :round, :game_url, :scraped_at)
        ON CONFLICT(fixture_id) DO UPDATE SET
            date       = COALESCE(excluded.date, wnihl_fixtures.date),
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            status     = excluded.status,
            venue      = COALESCE(excluded.venue, wnihl_fixtures.venue),
            scraped_at = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def upsert_standing(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO wnihl_standings
            (season, competition, team, pos, gp, w, l, d, gf, ga, pts, scraped_at)
        VALUES
            (:season, :competition, :team, :pos, :gp, :w, :l, :d, :gf, :ga, :pts, :scraped_at)
        ON CONFLICT(season, competition, team) DO UPDATE SET
            pos        = excluded.pos,
            gp         = excluded.gp,
            w          = excluded.w,
            l          = excluded.l,
            d          = excluded.d,
            gf         = excluded.gf,
            ga         = excluded.ga,
            pts        = excluded.pts,
            scraped_at = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def upsert_player_stat(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO wnihl_player_stats
            (season, competition, player_name, team, games, goals, assists, points, scraped_at)
        VALUES
            (:season, :competition, :player_name, :team, :games, :goals, :assists, :points, :scraped_at)
        ON CONFLICT(season, competition, player_name, team) DO UPDATE SET
            games      = excluded.games,
            goals      = excluded.goals,
            assists    = excluded.assists,
            points     = excluded.points,
            scraped_at = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )
