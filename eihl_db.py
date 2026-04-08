"""EIHL database schema and upsert helpers.

All tables are prefixed with eihl_ and live in the shared siha.db.
No existing SNL tables are touched.
"""

import sqlite3
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_eihl_schema(conn: sqlite3.Connection) -> None:
    """Create all EIHL tables if they do not exist. Safe to re-run."""
    conn.executescript("""
        -- Fixtures / results
        CREATE TABLE IF NOT EXISTS eihl_fixtures (
            game_id     TEXT PRIMARY KEY,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,          -- 'League' or 'Cup'
            date        TEXT,                   -- ISO YYYY-MM-DD HH:MM
            home_team   TEXT NOT NULL,
            away_team   TEXT NOT NULL,
            home_score  INTEGER,
            away_score  INTEGER,
            home_p1     INTEGER, away_p1 INTEGER,
            home_p2     INTEGER, away_p2 INTEGER,
            home_p3     INTEGER, away_p3 INTEGER,
            home_ot     INTEGER, away_ot INTEGER,
            status      TEXT NOT NULL DEFAULT 'scheduled',
            venue       TEXT,
            attendance  INTEGER,
            game_url    TEXT,
            scraped_at  TEXT NOT NULL
        );

        -- Goal and penalty events per game (deleted and re-inserted on re-scrape)
        CREATE TABLE IF NOT EXISTS eihl_game_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         TEXT NOT NULL REFERENCES eihl_fixtures(game_id),
            period          INTEGER,            -- 1, 2, 3; NULL = OT
            time_in_period  TEXT,               -- e.g. '41:30'
            event_type      TEXT NOT NULL,      -- 'goal' or 'penalty'
            team            TEXT,
            player_name     TEXT,
            player_id       TEXT,               -- numeric ID from /player/{id}-name
            assist1_name    TEXT,
            assist1_id      TEXT,
            assist2_name    TEXT,
            assist2_id      TEXT,
            goal_type       TEXT,               -- 'PPG', 'SHG', 'EN', or NULL (even strength)
            penalty_type    TEXT,               -- e.g. 'Hooking', 'Tripping'
            penalty_minutes INTEGER,
            scraped_at      TEXT NOT NULL
        );

        -- Per-game player stats (skaters and goalies in one table)
        CREATE TABLE IF NOT EXISTS eihl_game_player_stats (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id       TEXT NOT NULL REFERENCES eihl_fixtures(game_id),
            team          TEXT NOT NULL,
            player_name   TEXT NOT NULL,
            player_id     TEXT,
            jersey        TEXT,
            position      TEXT,           -- 'F', 'D', 'GK'
            -- Skater columns
            goals         INTEGER,
            assists       INTEGER,
            pim           INTEGER,
            ppg           INTEGER,
            shg           INTEGER,
            plus_minus    INTEGER,
            sog           INTEGER,
            fow           INTEGER,
            fol           INTEGER,
            bs            INTEGER,        -- blocked shots
            toi           TEXT,           -- time on ice
            -- Goalie columns
            shots_against INTEGER,
            saves         INTEGER,
            goals_against INTEGER,
            svs_pct       REAL,
            min_played    TEXT,
            scraped_at    TEXT NOT NULL,
            UNIQUE (game_id, team, player_id)
        );

        -- Season standings (League = one group, Cup = group A or B)
        CREATE TABLE IF NOT EXISTS eihl_standings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,      -- 'League' or 'Cup'
            group_name  TEXT,              -- NULL for League; 'A' or 'B' for Cup
            team        TEXT NOT NULL,
            qualifier   TEXT,              -- 'c' = champion, 'x' = playoff-qualified, NULL = neither
            pos         INTEGER,
            gp          INTEGER,
            pts         INTEGER,
            w           INTEGER,
            otw         INTEGER,
            l           INTEGER,
            otl         INTEGER,
            gf          INTEGER,
            ga          INTEGER,
            scraped_at  TEXT NOT NULL,
            UNIQUE (season, competition, group_name, team)
        );

        -- Season skater stats
        CREATE TABLE IF NOT EXISTS eihl_skater_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,
            player_name TEXT NOT NULL,
            player_id   TEXT,
            team        TEXT NOT NULL,
            position    TEXT,
            gp          INTEGER,
            g           INTEGER,
            a           INTEGER,
            pts         INTEGER,
            pim         INTEGER,
            ppg         INTEGER,
            shg         INTEGER,
            plus_minus  INTEGER,
            sog         INTEGER,
            s_pct       REAL,
            fow         INTEGER,
            fol         INTEGER,
            scraped_at  TEXT NOT NULL,
            UNIQUE (season, competition, player_id)
        );

        -- Season goalie stats
        CREATE TABLE IF NOT EXISTS eihl_goalie_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            season      TEXT NOT NULL DEFAULT '2025-26',
            competition TEXT NOT NULL,
            player_name TEXT NOT NULL,
            player_id   TEXT,
            team        TEXT NOT NULL,
            gp          INTEGER,
            w           INTEGER,
            l           INTEGER,
            so          INTEGER,
            sa          INTEGER,
            ga          INTEGER,
            min_played  TEXT,
            gaa         REAL,
            svs_pct     REAL,
            pim         INTEGER,
            scraped_at  TEXT NOT NULL,
            UNIQUE (season, competition, player_id)
        );
    """)
    conn.commit()

    # Migrations: add columns that didn't exist in the initial schema
    _add_column_if_missing(conn, "eihl_standings", "qualifier", "TEXT")

    # Migration: fix NULL group_name rows (SQLite NULL != NULL breaks UNIQUE upsert)
    # Step 1: remove old-format rows where qualifier wasn't stripped (team starts with digit)
    conn.execute("DELETE FROM eihl_standings WHERE team GLOB '[0-9]*'")
    # Step 2: delete NULL group_name duplicates, keep only latest per team
    conn.execute("""
        DELETE FROM eihl_standings
        WHERE group_name IS NULL
          AND id NOT IN (
            SELECT MAX(id) FROM eihl_standings
            WHERE group_name IS NULL
            GROUP BY season, competition, team
          )
    """)
    # Step 3: rename NULL → '' so UNIQUE constraint works
    conn.execute("UPDATE eihl_standings SET group_name = '' WHERE group_name IS NULL")
    conn.commit()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_fixture(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO eihl_fixtures
            (game_id, season, competition, date, home_team, away_team,
             home_score, away_score, status, game_url, scraped_at)
        VALUES (:game_id, :season, :competition, :date, :home_team, :away_team,
                :home_score, :away_score, :status, :game_url, :scraped_at)
        ON CONFLICT(game_id) DO UPDATE SET
            date       = COALESCE(excluded.date, eihl_fixtures.date),
            home_score = excluded.home_score,
            away_score = excluded.away_score,
            status     = excluded.status,
            scraped_at = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def update_fixture_detail(conn: sqlite3.Connection, game_id: str,
                          venue: str | None, attendance: int | None,
                          home_p1, away_p1, home_p2, away_p2,
                          home_p3, away_p3, home_ot, away_ot) -> None:
    conn.execute(
        """
        UPDATE eihl_fixtures SET
            venue      = :venue,
            attendance = :attendance,
            home_p1 = :hp1, away_p1 = :ap1,
            home_p2 = :hp2, away_p2 = :ap2,
            home_p3 = :hp3, away_p3 = :ap3,
            home_ot = :hot, away_ot = :aot,
            scraped_at = :ts
        WHERE game_id = :game_id
        """,
        dict(game_id=game_id, venue=venue, attendance=attendance,
             hp1=home_p1, ap1=away_p1, hp2=home_p2, ap2=away_p2,
             hp3=home_p3, ap3=away_p3, hot=home_ot, aot=away_ot,
             ts=now_iso()),
    )


def replace_game_events(conn: sqlite3.Connection,
                        game_id: str, events: list[dict]) -> None:
    """Delete old events for game_id then insert the new set atomically."""
    conn.execute("DELETE FROM eihl_game_events WHERE game_id = ?", (game_id,))
    for ev in events:
        conn.execute(
            """
            INSERT INTO eihl_game_events
                (game_id, period, time_in_period, event_type, team, player_name,
                 player_id, assist1_name, assist1_id, assist2_name, assist2_id,
                 goal_type, penalty_type, penalty_minutes, scraped_at)
            VALUES
                (:game_id, :period, :time_in_period, :event_type, :team, :player_name,
                 :player_id, :assist1_name, :assist1_id, :assist2_name, :assist2_id,
                 :goal_type, :penalty_type, :penalty_minutes, :scraped_at)
            """,
            {**ev, "game_id": game_id, "scraped_at": now_iso()},
        )


def upsert_game_player_stat(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO eihl_game_player_stats
            (game_id, team, player_name, player_id, jersey, position,
             goals, assists, pim, ppg, shg, plus_minus, sog, fow, fol, bs, toi,
             shots_against, saves, goals_against, svs_pct, min_played, scraped_at)
        VALUES
            (:game_id, :team, :player_name, :player_id, :jersey, :position,
             :goals, :assists, :pim, :ppg, :shg, :plus_minus, :sog, :fow, :fol, :bs, :toi,
             :shots_against, :saves, :goals_against, :svs_pct, :min_played, :scraped_at)
        ON CONFLICT(game_id, team, player_id) DO UPDATE SET
            goals         = excluded.goals,
            assists       = excluded.assists,
            pim           = excluded.pim,
            ppg           = excluded.ppg,
            shg           = excluded.shg,
            plus_minus    = excluded.plus_minus,
            sog           = excluded.sog,
            fow           = excluded.fow,
            fol           = excluded.fol,
            bs            = excluded.bs,
            toi           = excluded.toi,
            shots_against = excluded.shots_against,
            saves         = excluded.saves,
            goals_against = excluded.goals_against,
            svs_pct       = excluded.svs_pct,
            min_played    = excluded.min_played,
            scraped_at    = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def upsert_standing(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO eihl_standings
            (season, competition, group_name, team, qualifier, pos, gp, pts, w, otw, l, otl, gf, ga, scraped_at)
        VALUES
            (:season, :competition, :group_name, :team, :qualifier, :pos, :gp, :pts, :w, :otw, :l, :otl, :gf, :ga, :scraped_at)
        ON CONFLICT(season, competition, group_name, team) DO UPDATE SET
            qualifier  = excluded.qualifier,
            pos        = excluded.pos,
            gp         = excluded.gp,
            pts        = excluded.pts,
            w          = excluded.w,
            otw        = excluded.otw,
            l          = excluded.l,
            otl        = excluded.otl,
            gf         = excluded.gf,
            ga         = excluded.ga,
            scraped_at = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def upsert_skater_stat(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO eihl_skater_stats
            (season, competition, player_name, player_id, team, position,
             gp, g, a, pts, pim, ppg, shg, plus_minus, sog, s_pct, fow, fol, scraped_at)
        VALUES
            (:season, :competition, :player_name, :player_id, :team, :position,
             :gp, :g, :a, :pts, :pim, :ppg, :shg, :plus_minus, :sog, :s_pct, :fow, :fol, :scraped_at)
        ON CONFLICT(season, competition, player_id) DO UPDATE SET
            team        = excluded.team,
            position    = excluded.position,
            gp          = excluded.gp,
            g           = excluded.g,
            a           = excluded.a,
            pts         = excluded.pts,
            pim         = excluded.pim,
            ppg         = excluded.ppg,
            shg         = excluded.shg,
            plus_minus  = excluded.plus_minus,
            sog         = excluded.sog,
            s_pct       = excluded.s_pct,
            fow         = excluded.fow,
            fol         = excluded.fol,
            scraped_at  = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def upsert_goalie_stat(conn: sqlite3.Connection, **kw) -> None:
    conn.execute(
        """
        INSERT INTO eihl_goalie_stats
            (season, competition, player_name, player_id, team,
             gp, w, l, so, sa, ga, min_played, gaa, svs_pct, pim, scraped_at)
        VALUES
            (:season, :competition, :player_name, :player_id, :team,
             :gp, :w, :l, :so, :sa, :ga, :min_played, :gaa, :svs_pct, :pim, :scraped_at)
        ON CONFLICT(season, competition, player_id) DO UPDATE SET
            team       = excluded.team,
            gp         = excluded.gp,
            w          = excluded.w,
            l          = excluded.l,
            so         = excluded.so,
            sa         = excluded.sa,
            ga         = excluded.ga,
            min_played = excluded.min_played,
            gaa        = excluded.gaa,
            svs_pct    = excluded.svs_pct,
            pim        = excluded.pim,
            scraped_at = excluded.scraped_at
        """,
        {**kw, "scraped_at": now_iso()},
    )


def get_games_needing_detail(conn: sqlite3.Connection) -> list[dict]:
    """Return completed games that have no event data or player stats yet."""
    rows = conn.execute(
        """
        SELECT game_id, game_url, home_team, away_team
        FROM eihl_fixtures
        WHERE status != 'scheduled'
          AND game_id NOT IN (SELECT DISTINCT game_id FROM eihl_game_events)
          AND game_id NOT IN (SELECT DISTINCT game_id FROM eihl_game_player_stats)
        ORDER BY date
        """
    ).fetchall()
    return [dict(r) for r in rows]
