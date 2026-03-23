"""Database layer: schema, upsert helpers, incremental queries."""

import sqlite3
from datetime import datetime, timezone


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS competitions (
            id   INTEGER PRIMARY KEY,
            name TEXT    NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS teams (
            id   INTEGER PRIMARY KEY,
            slug TEXT    NOT NULL UNIQUE,
            name TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS players (
            id   INTEGER PRIMARY KEY,
            slug TEXT    NOT NULL UNIQUE,
            name TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fixtures (
            event_id       INTEGER PRIMARY KEY,
            competition_id INTEGER NOT NULL REFERENCES competitions(id),
            date           TEXT,
            home_team_id   INTEGER REFERENCES teams(id),
            away_team_id   INTEGER REFERENCES teams(id),
            home_score     INTEGER,
            away_score     INTEGER,
            status         TEXT    NOT NULL DEFAULT 'scheduled',
            scraped_at     TEXT    NOT NULL,
            event_url      TEXT
        );
        -- Add event_url column if upgrading an existing database
        CREATE TABLE IF NOT EXISTS _migrations (id INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO _migrations VALUES (1);

        CREATE TABLE IF NOT EXISTS event_period_scores (
            id         INTEGER PRIMARY KEY,
            event_id   INTEGER NOT NULL REFERENCES fixtures(event_id),
            team_id    INTEGER NOT NULL REFERENCES teams(id),
            period_1   INTEGER,
            period_2   INTEGER,
            period_3   INTEGER,
            ppg        INTEGER,
            ppo        INTEGER,
            outcome    TEXT,
            UNIQUE (event_id, team_id)
        );

        CREATE TABLE IF NOT EXISTS event_player_stats (
            id             INTEGER PRIMARY KEY,
            event_id       INTEGER NOT NULL REFERENCES fixtures(event_id),
            team_id        INTEGER NOT NULL REFERENCES teams(id),
            player_id      INTEGER NOT NULL REFERENCES players(id),
            jersey_number  TEXT,
            position       TEXT,
            goals          INTEGER DEFAULT 0,
            assists        INTEGER DEFAULT 0,
            pim            INTEGER DEFAULT 0,
            shots_against  INTEGER,
            saves          INTEGER,
            goals_against  INTEGER,
            toi            TEXT,
            UNIQUE (event_id, team_id, player_id)
        );

        CREATE TABLE IF NOT EXISTS season_skater_stats (
            id             INTEGER PRIMARY KEY,
            competition_id INTEGER NOT NULL REFERENCES competitions(id),
            player_id      INTEGER NOT NULL REFERENCES players(id),
            team_id        INTEGER NOT NULL REFERENCES teams(id),
            position       TEXT,
            gp             INTEGER,
            goals          INTEGER,
            assists        INTEGER,
            total_points   INTEGER,
            pim            INTEGER,
            scraped_at     TEXT    NOT NULL,
            UNIQUE (competition_id, player_id)
        );

        CREATE TABLE IF NOT EXISTS season_netminder_stats (
            id             INTEGER PRIMARY KEY,
            competition_id INTEGER NOT NULL REFERENCES competitions(id),
            player_id      INTEGER NOT NULL REFERENCES players(id),
            team_id        INTEGER NOT NULL REFERENCES teams(id),
            gp             INTEGER,
            shots_against  INTEGER,
            saves          INTEGER,
            goals_against  INTEGER,
            save_pct       REAL,
            gaa            REAL,
            toi            TEXT,
            scraped_at     TEXT    NOT NULL,
            UNIQUE (competition_id, player_id)
        );

        CREATE TABLE IF NOT EXISTS team_season_stats (
            id             INTEGER PRIMARY KEY,
            competition_id INTEGER NOT NULL REFERENCES competitions(id),
            team_id        INTEGER NOT NULL REFERENCES teams(id),
            pos            INTEGER,
            gp             INTEGER,
            wins           INTEGER,
            losses         INTEGER,
            otl            INTEGER,
            gf             INTEGER,
            ga             INTEGER,
            goal_diff      INTEGER,
            pts            INTEGER,
            ppo            INTEGER,
            ppg            INTEGER,
            pp_pct         REAL,
            ppga           INTEGER,
            ppoa           INTEGER,
            pk_pct         REAL,
            shg            INTEGER,
            shga           INTEGER,
            scraped_at     TEXT    NOT NULL,
            UNIQUE (competition_id, team_id)
        );
    """)

    # Seed competition rows
    for name in ("SNL", "Scottish Cup"):
        conn.execute(
            "INSERT OR IGNORE INTO competitions (name) VALUES (?)", (name,)
        )
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_competition_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM competitions WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown competition: {name!r}")
    return row["id"]


def upsert_team(conn: sqlite3.Connection, slug: str, name: str) -> int:
    conn.execute(
        "INSERT INTO teams (slug, name) VALUES (?, ?)"
        " ON CONFLICT(slug) DO UPDATE SET name=excluded.name",
        (slug, name),
    )
    return conn.execute(
        "SELECT id FROM teams WHERE slug = ?", (slug,)
    ).fetchone()["id"]


def upsert_player(conn: sqlite3.Connection, slug: str, name: str) -> int:
    conn.execute(
        "INSERT INTO players (slug, name) VALUES (?, ?)"
        " ON CONFLICT(slug) DO UPDATE SET name=excluded.name",
        (slug, name),
    )
    return conn.execute(
        "SELECT id FROM players WHERE slug = ?", (slug,)
    ).fetchone()["id"]


def upsert_fixture(
    conn: sqlite3.Connection,
    event_id: int,
    competition_id: int,
    date: str | None,
    home_team_id: int,
    away_team_id: int,
    home_score: int | None,
    away_score: int | None,
    status: str,
    event_url: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO fixtures
            (event_id, competition_id, date, home_team_id, away_team_id,
             home_score, away_score, status, scraped_at, event_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            competition_id = excluded.competition_id,
            date           = COALESCE(excluded.date, fixtures.date),
            home_team_id   = excluded.home_team_id,
            away_team_id   = excluded.away_team_id,
            home_score     = excluded.home_score,
            away_score     = excluded.away_score,
            status         = excluded.status,
            scraped_at     = excluded.scraped_at,
            event_url      = COALESCE(excluded.event_url, fixtures.event_url)
        """,
        (
            event_id, competition_id, date, home_team_id, away_team_id,
            home_score, away_score, status, now_iso(), event_url,
        ),
    )


def upsert_period_scores(
    conn: sqlite3.Connection,
    event_id: int,
    team_id: int,
    period_1: int | None,
    period_2: int | None,
    period_3: int | None,
    ppg: int | None,
    ppo: int | None,
    outcome: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO event_period_scores
            (event_id, team_id, period_1, period_2, period_3, ppg, ppo, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id, team_id) DO UPDATE SET
            period_1 = excluded.period_1,
            period_2 = excluded.period_2,
            period_3 = excluded.period_3,
            ppg      = excluded.ppg,
            ppo      = excluded.ppo,
            outcome  = excluded.outcome
        """,
        (event_id, team_id, period_1, period_2, period_3, ppg, ppo, outcome),
    )


def upsert_event_player_stat(
    conn: sqlite3.Connection,
    event_id: int,
    team_id: int,
    player_id: int,
    jersey_number: str | None,
    position: str | None,
    goals: int,
    assists: int,
    pim: int,
    shots_against: int | None,
    saves: int | None,
    goals_against: int | None,
    toi: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO event_player_stats
            (event_id, team_id, player_id, jersey_number, position,
             goals, assists, pim, shots_against, saves, goals_against, toi)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id, team_id, player_id) DO UPDATE SET
            jersey_number = excluded.jersey_number,
            position      = excluded.position,
            goals         = excluded.goals,
            assists       = excluded.assists,
            pim           = excluded.pim,
            shots_against = excluded.shots_against,
            saves         = excluded.saves,
            goals_against = excluded.goals_against,
            toi           = excluded.toi
        """,
        (
            event_id, team_id, player_id, jersey_number, position,
            goals, assists, pim, shots_against, saves, goals_against, toi,
        ),
    )


def upsert_season_skater(
    conn: sqlite3.Connection,
    competition_id: int,
    player_id: int,
    team_id: int,
    position: str | None,
    gp: int | None,
    goals: int | None,
    assists: int | None,
    total_points: int | None,
    pim: int | None,
) -> None:
    conn.execute(
        """
        INSERT INTO season_skater_stats
            (competition_id, player_id, team_id, position,
             gp, goals, assists, total_points, pim, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(competition_id, player_id) DO UPDATE SET
            team_id      = excluded.team_id,
            position     = excluded.position,
            gp           = excluded.gp,
            goals        = excluded.goals,
            assists      = excluded.assists,
            total_points = excluded.total_points,
            pim          = excluded.pim,
            scraped_at   = excluded.scraped_at
        """,
        (
            competition_id, player_id, team_id, position,
            gp, goals, assists, total_points, pim, now_iso(),
        ),
    )


def upsert_season_netminder(
    conn: sqlite3.Connection,
    competition_id: int,
    player_id: int,
    team_id: int,
    gp: int | None,
    shots_against: int | None,
    saves: int | None,
    goals_against: int | None,
    save_pct: float | None,
    gaa: float | None,
    toi: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO season_netminder_stats
            (competition_id, player_id, team_id,
             gp, shots_against, saves, goals_against, save_pct, gaa, toi,
             scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(competition_id, player_id) DO UPDATE SET
            team_id       = excluded.team_id,
            gp            = excluded.gp,
            shots_against = excluded.shots_against,
            saves         = excluded.saves,
            goals_against = excluded.goals_against,
            save_pct      = excluded.save_pct,
            gaa           = excluded.gaa,
            toi           = excluded.toi,
            scraped_at    = excluded.scraped_at
        """,
        (
            competition_id, player_id, team_id,
            gp, shots_against, saves, goals_against, save_pct, gaa, toi,
            now_iso(),
        ),
    )


def upsert_team_season_stat(
    conn: sqlite3.Connection,
    competition_id: int,
    team_id: int,
    **kwargs,
) -> None:
    fields = [
        "pos", "gp", "wins", "losses", "otl", "gf", "ga", "goal_diff",
        "pts", "ppo", "ppg", "pp_pct", "ppga", "ppoa", "pk_pct", "shg", "shga",
    ]
    cols = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{f} = excluded.{f}" for f in fields)
    values = [kwargs.get(f) for f in fields]

    conn.execute(
        f"""
        INSERT INTO team_season_stats
            (competition_id, team_id, {cols}, scraped_at)
        VALUES (?, ?, {placeholders}, ?)
        ON CONFLICT(competition_id, team_id) DO UPDATE SET
            {updates},
            scraped_at = excluded.scraped_at
        """,
        [competition_id, team_id] + values + [now_iso()],
    )


def upsert_standings(
    conn: sqlite3.Connection,
    competition_id: int,
    team_id: int,
    pos: int | None,
    gp: int | None,
    wins: int | None,
    losses: int | None,
    otl: int | None,
    gf: int | None,
    ga: int | None,
    goal_diff: int | None,
    pts: int | None,
) -> None:
    """Update only the standings columns; leave special-teams stats untouched."""
    conn.execute(
        """
        INSERT INTO team_season_stats
            (competition_id, team_id, pos, gp, wins, losses, otl, gf, ga, goal_diff, pts, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(competition_id, team_id) DO UPDATE SET
            pos       = excluded.pos,
            gp        = excluded.gp,
            wins      = excluded.wins,
            losses    = excluded.losses,
            otl       = excluded.otl,
            gf        = excluded.gf,
            ga        = excluded.ga,
            goal_diff = excluded.goal_diff,
            pts       = excluded.pts,
            scraped_at = excluded.scraped_at
        """,
        (competition_id, team_id, pos, gp, wins, losses, otl, gf, ga, goal_diff, pts, now_iso()),
    )


def update_fixture_date(conn: sqlite3.Connection, event_id: int, date: str) -> None:
    conn.execute(
        "UPDATE fixtures SET date = ? WHERE event_id = ?", (date, event_id)
    )


def get_undated_event_ids(conn: sqlite3.Connection) -> list[int]:
    """Return event_ids for final fixtures that have no date recorded."""
    rows = conn.execute(
        "SELECT event_id FROM fixtures WHERE status = 'final' AND date IS NULL ORDER BY event_id"
    ).fetchall()
    return [r["event_id"] for r in rows]


def get_unscraped_events(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Return (event_id, url) for final fixtures with no player stats and no period scores yet.

    Events that have period scores but no player stats have already been fetched
    (the match report exists but the player table was not published); skip them.
    """
    rows = conn.execute(
        """
        SELECT f.event_id,
               COALESCE(f.event_url, '/event/' || f.event_id || '/') AS url
        FROM fixtures f
        WHERE f.status = 'final'
          AND f.event_id NOT IN (
              SELECT DISTINCT event_id FROM event_player_stats
          )
          AND f.event_id NOT IN (
              SELECT DISTINCT event_id FROM event_period_scores
          )
        ORDER BY f.event_id
        """
    ).fetchall()
    return [(r["event_id"], r["url"]) for r in rows]


def get_undated_events(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Return (event_id, url) for final fixtures with no date recorded."""
    rows = conn.execute(
        """
        SELECT f.event_id,
               COALESCE(f.event_url, '/event/' || f.event_id || '/') AS url
        FROM fixtures f
        WHERE f.status = 'final' AND f.date IS NULL
        ORDER BY f.event_id
        """
    ).fetchall()
    return [(r["event_id"], r["url"]) for r in rows]
