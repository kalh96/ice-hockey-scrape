"""
SQLite persistence layer for the simulation game.

Uses sim.db in the project root (separate from siha.db).
All tables are prefixed sim_ to avoid any future collision.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sim.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all sim tables if they do not exist. Safe to re-run."""
    conn.executescript("""
        -- One row per simulated league/season
        CREATE TABLE IF NOT EXISTS sim_leagues (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            season     TEXT NOT NULL,
            n_teams    INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        -- One row per team in a league
        CREATE TABLE IF NOT EXISTS sim_teams (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id    INTEGER NOT NULL REFERENCES sim_leagues(id),
            name         TEXT NOT NULL,
            quality_bias INTEGER NOT NULL DEFAULT 0
        );

        -- One row per player; all attributes in one table (NULLs for non-applicable attrs)
        CREATE TABLE IF NOT EXISTS sim_players (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id         INTEGER NOT NULL REFERENCES sim_teams(id),
            name            TEXT NOT NULL,
            position        TEXT NOT NULL,
            age             INTEGER,
            potential       INTEGER,
            morale          INTEGER,
            overall         REAL,
            -- Skater attributes
            skating         INTEGER,
            shooting        INTEGER,
            passing         INTEGER,
            physicality     INTEGER,
            defence         INTEGER,
            stamina         INTEGER,
            -- Goalie attributes
            positioning     INTEGER,
            reflexes        INTEGER,
            rebound_control INTEGER,
            -- Line assignment (set at squad creation)
            line_number     INTEGER,   -- 1-4 for forwards/defence; 1=starter for goalies
            slot            TEXT       -- 'lw','c','rw','ld','rd','g'
        );

        -- Scheduled and played fixtures
        CREATE TABLE IF NOT EXISTS sim_fixtures (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id    INTEGER NOT NULL REFERENCES sim_leagues(id),
            round_num    INTEGER,
            phase        TEXT NOT NULL DEFAULT 'regular',  -- 'regular','playoff_sf','playoff_final'
            home_team_id INTEGER NOT NULL REFERENCES sim_teams(id),
            away_team_id INTEGER NOT NULL REFERENCES sim_teams(id),
            home_score   INTEGER,
            away_score   INTEGER,
            result_type  TEXT,    -- 'REG','OT','SO'
            played       INTEGER NOT NULL DEFAULT 0
        );

        -- Goal and penalty events per fixture
        CREATE TABLE IF NOT EXISTS sim_game_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id   INTEGER NOT NULL REFERENCES sim_fixtures(id),
            period       TEXT,
            time         TEXT,
            event_type   TEXT NOT NULL,   -- 'goal','penalty','shootout'
            team_name    TEXT,
            scorer_name  TEXT,
            assist1_name TEXT,
            assist2_name TEXT,
            goal_type    TEXT,            -- 'PPG','OTG','SO', NULL = even strength
            penalty_player TEXT,
            infraction   TEXT,
            minutes      INTEGER
        );

        -- Aggregated season stats per player (updated after each game)
        CREATE TABLE IF NOT EXISTS sim_player_stats (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL REFERENCES sim_leagues(id),
            player_id INTEGER NOT NULL REFERENCES sim_players(id),
            phase     TEXT NOT NULL DEFAULT 'regular',
            gp        INTEGER NOT NULL DEFAULT 0,
            g         INTEGER NOT NULL DEFAULT 0,
            a         INTEGER NOT NULL DEFAULT 0,
            pts       INTEGER NOT NULL DEFAULT 0,
            UNIQUE (league_id, player_id, phase)
        );

        -- Standings snapshot (updated after each game)
        CREATE TABLE IF NOT EXISTS sim_standings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL REFERENCES sim_leagues(id),
            team_id   INTEGER NOT NULL REFERENCES sim_teams(id),
            phase     TEXT NOT NULL DEFAULT 'regular',
            gp        INTEGER NOT NULL DEFAULT 0,
            w         INTEGER NOT NULL DEFAULT 0,
            otw       INTEGER NOT NULL DEFAULT 0,
            l         INTEGER NOT NULL DEFAULT 0,
            otl       INTEGER NOT NULL DEFAULT 0,
            gf        INTEGER NOT NULL DEFAULT 0,
            ga        INTEGER NOT NULL DEFAULT 0,
            pts       INTEGER NOT NULL DEFAULT 0,
            UNIQUE (league_id, team_id, phase)
        );

        -- Player-controlled season state
        CREATE TABLE IF NOT EXISTS sim_managed_seasons (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id        INTEGER NOT NULL REFERENCES sim_leagues(id),
            user_team_id     INTEGER NOT NULL REFERENCES sim_teams(id),
            current_matchday INTEGER NOT NULL DEFAULT 1,
            total_matchdays  INTEGER NOT NULL,
            n_playoff_teams  INTEGER NOT NULL DEFAULT 4,
            status           TEXT NOT NULL DEFAULT 'active',
            playoff_round    TEXT,
            created_at       TEXT NOT NULL
        );
    """)
    conn.commit()
    # Migration: add playoff_round to existing DBs that pre-date this column
    try:
        conn.execute("ALTER TABLE sim_managed_seasons ADD COLUMN playoff_round TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

def insert_league(conn: sqlite3.Connection, name: str, season: str, n_teams: int) -> int:
    cur = conn.execute(
        "INSERT INTO sim_leagues (name, season, n_teams, created_at) VALUES (?,?,?,?)",
        (name, season, n_teams, now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def insert_team(conn: sqlite3.Connection, league_id: int, name: str, quality_bias: int) -> int:
    cur = conn.execute(
        "INSERT INTO sim_teams (league_id, name, quality_bias) VALUES (?,?,?)",
        (league_id, name, quality_bias),
    )
    conn.commit()
    return cur.lastrowid


def insert_player(conn: sqlite3.Connection, team_id: int, player: dict,
                  line_number: int | None = None, slot: str | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO sim_players
               (team_id, name, position, age, potential, morale, overall,
                skating, shooting, passing, physicality, defence, stamina,
                positioning, reflexes, rebound_control, line_number, slot)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            team_id,
            player["name"], player["position"], player["age"],
            player.get("potential"), player.get("morale"), player.get("overall"),
            player.get("skating"), player.get("shooting"), player.get("passing"),
            player.get("physicality"), player.get("defence"), player.get("stamina"),
            player.get("positioning"), player.get("reflexes"), player.get("rebound_control"),
            line_number, slot,
        ),
    )
    conn.commit()
    return cur.lastrowid


def insert_fixture(conn: sqlite3.Connection, league_id: int, round_num: int, phase: str,
                   home_team_id: int, away_team_id: int) -> int:
    cur = conn.execute(
        """INSERT INTO sim_fixtures (league_id, round_num, phase, home_team_id, away_team_id)
           VALUES (?,?,?,?,?)""",
        (league_id, round_num, phase, home_team_id, away_team_id),
    )
    conn.commit()
    return cur.lastrowid


def record_fixture_result(conn: sqlite3.Connection, fixture_id: int, result: dict) -> None:
    conn.execute(
        """UPDATE sim_fixtures
           SET home_score=?, away_score=?, result_type=?, played=1
           WHERE id=?""",
        (result["home_score"], result["away_score"], result["result_type"], fixture_id),
    )
    for ev in result["events"]:
        conn.execute(
            """INSERT INTO sim_game_events
                   (fixture_id, period, time, event_type, team_name,
                    scorer_name, assist1_name, assist2_name, goal_type,
                    penalty_player, infraction, minutes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fixture_id, str(ev.get("period", "")), ev.get("time", ""),
                ev["type"], ev.get("team"),
                ev.get("scorer"), ev.get("assist1"), ev.get("assist2"),
                ev.get("goal_type"),
                ev.get("player"), ev.get("infraction"), ev.get("minutes"),
            ),
        )
    conn.commit()


def upsert_standing(conn: sqlite3.Connection, league_id: int, team_id: int,
                    phase: str, row: dict) -> None:
    conn.execute(
        """INSERT INTO sim_standings (league_id, team_id, phase, gp, w, otw, l, otl, gf, ga, pts)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT (league_id, team_id, phase) DO UPDATE SET
               gp=excluded.gp, w=excluded.w, otw=excluded.otw,
               l=excluded.l, otl=excluded.otl,
               gf=excluded.gf, ga=excluded.ga, pts=excluded.pts""",
        (league_id, team_id, phase,
         row["gp"], row["w"], row["otw"], row["l"], row["otl"],
         row["gf"], row["ga"], row["pts"]),
    )
    conn.commit()


def create_managed_season(
    conn: sqlite3.Connection,
    league_id: int,
    user_team_id: int,
    total_matchdays: int,
    n_playoff_teams: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO sim_managed_seasons
               (league_id, user_team_id, current_matchday, total_matchdays,
                n_playoff_teams, status, created_at)
           VALUES (?,?,1,?,?,'active',?)""",
        (league_id, user_team_id, total_matchdays, n_playoff_teams, now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def advance_managed_season(
    conn: sqlite3.Connection,
    game_id: int,
    new_matchday: int | None = None,
    status: str | None = None,
    playoff_round: str | None = None,
) -> None:
    sets, vals = [], []
    if new_matchday is not None:
        sets.append("current_matchday=?"); vals.append(new_matchday)
    if status is not None:
        sets.append("status=?"); vals.append(status)
    if playoff_round is not None:
        sets.append("playoff_round=?"); vals.append(playoff_round)
    if sets:
        vals.append(game_id)
        conn.execute(f"UPDATE sim_managed_seasons SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()


def upsert_player_stat(conn: sqlite3.Connection, league_id: int, player_id: int,
                       phase: str, gp: int, g: int, a: int) -> None:
    conn.execute(
        """INSERT INTO sim_player_stats (league_id, player_id, phase, gp, g, a, pts)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT (league_id, player_id, phase) DO UPDATE SET
               gp=excluded.gp, g=excluded.g, a=excluded.a, pts=excluded.pts""",
        (league_id, player_id, phase, gp, g, a, g + a),
    )
    conn.commit()
