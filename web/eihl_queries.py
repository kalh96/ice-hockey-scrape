"""Read-only database queries for the EIHL web layer."""

import sqlite3
from config import DB_PATH, CURRENT_SEASON

EIHL_CURRENT_SEASON = CURRENT_SEASON   # shared; update in web/config.py each August


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def get_eihl_recent_results(competition="League", season=EIHL_CURRENT_SEASON,
                            limit=10, phase=None):
    conn = _conn()
    try:
        phase_clause = "AND phase = ?" if phase else ""
        params = [season, competition, competition]
        if phase:
            params.append(phase)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT game_id, date, home_team, away_team, home_score, away_score,
                   status, competition, phase
            FROM eihl_fixtures
            WHERE status != 'scheduled'
              AND season = ?
              AND (? = 'all' OR competition = ?)
              {phase_clause}
            ORDER BY COALESCE(date, '0') DESC, CAST(game_id AS INTEGER) DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_upcoming_fixtures(competition="League", season=EIHL_CURRENT_SEASON,
                               limit=10, phase=None):
    conn = _conn()
    try:
        phase_clause = "AND phase = ?" if phase else ""
        params = [season, competition, competition]
        if phase:
            params.append(phase)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT game_id, date, home_team, away_team, competition, phase
            FROM eihl_fixtures
            WHERE status = 'scheduled'
              AND season = ?
              AND (? = 'all' OR competition = ?)
              {phase_clause}
            ORDER BY COALESCE(date, 'z') ASC, CAST(game_id AS INTEGER) ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_all_fixtures(competition="all", season=EIHL_CURRENT_SEASON):
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT game_id, date, home_team, away_team, home_score, away_score,
                   status, competition, phase
            FROM eihl_fixtures
            WHERE season = ?
              AND (? = 'all' OR competition = ?)
            ORDER BY status ASC,
                     COALESCE(date, '0') DESC,
                     CAST(game_id AS INTEGER) DESC
            """,
            (season, competition, competition),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_fixtures_by_ids(game_ids: list[str]) -> dict:
    """Return {game_id: fixture dict} for the given list of EIHL game IDs."""
    if not game_ids:
        return {}
    conn = _conn()
    try:
        placeholders = ",".join("?" * len(game_ids))
        rows = conn.execute(
            f"""
            SELECT game_id, date, status, home_team, away_team, home_score, away_score
            FROM eihl_fixtures
            WHERE game_id IN ({placeholders})
            """,
            game_ids,
        ).fetchall()
        result = {}
        for r in rows:
            d = dict(r)
            d["event_id"] = d["game_id"]  # alias for bracket builder compatibility
            result[d["game_id"]] = d
        return result
    finally:
        conn.close()


def get_eihl_standings(competition="League", season=EIHL_CURRENT_SEASON):
    """Return standings rows.  League → flat list; Cup → list with group_name."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT team, group_name, qualifier, pos, gp, pts, w, otw, l, otl, gf, ga
            FROM eihl_standings
            WHERE competition = ? AND season = ?
            ORDER BY group_name, pos
            """,
            (competition, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_skater_stats(competition="League", season=EIHL_CURRENT_SEASON):
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT player_name, team, position, gp, g, a, pts, pim,
                   ppg, shg, plus_minus, sog, s_pct, fow, fol
            FROM eihl_skater_stats
            WHERE competition = ? AND season = ?
            ORDER BY pts DESC, g DESC, a DESC
            """,
            (competition, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_goalie_stats(competition="League", season=EIHL_CURRENT_SEASON):
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT player_name, team, gp, w, l, so, sa, ga, min_played, gaa, svs_pct, pim
            FROM eihl_goalie_stats
            WHERE competition = ? AND season = ?
            ORDER BY svs_pct DESC
            """,
            (competition, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_game_detail(game_id: str):
    """Return full game detail dict or None."""
    conn = _conn()
    try:
        fixture = conn.execute(
            """
            SELECT game_id, date, home_team, away_team, home_score, away_score,
                   status, competition, venue, attendance,
                   home_p1, away_p1, home_p2, away_p2, home_p3, away_p3,
                   home_ot, away_ot
            FROM eihl_fixtures WHERE game_id = ?
            """,
            (game_id,),
        ).fetchone()
        if fixture is None:
            return None

        events = conn.execute(
            """
            SELECT period, time_in_period, event_type, team, player_name,
                   assist1_name, assist2_name, goal_type, penalty_type, penalty_minutes
            FROM eihl_game_events
            WHERE game_id = ?
            ORDER BY period NULLS LAST, time_in_period
            """,
            (game_id,),
        ).fetchall()

        player_stats = conn.execute(
            """
            SELECT team, player_name, jersey, position,
                   goals, assists, pim, ppg, shg, plus_minus, sog, toi, bs, fow, fol,
                   shots_against, saves, goals_against, svs_pct, min_played
            FROM eihl_game_player_stats
            WHERE game_id = ?
            ORDER BY team, position, CAST(jersey AS INTEGER)
            """,
            (game_id,),
        ).fetchall()

        return {
            "fixture":      dict(fixture),
            "events":       [dict(r) for r in events],
            "player_stats": [dict(r) for r in player_stats],
        }
    finally:
        conn.close()


def get_eihl_team_fixtures(team_name: str, season=EIHL_CURRENT_SEASON):
    """Return all fixtures (results + scheduled) for a specific team."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT game_id, date, home_team, away_team, home_score, away_score,
                   status, competition
            FROM eihl_fixtures
            WHERE (home_team = ? OR away_team = ?) AND season = ?
            ORDER BY COALESCE(date, 'z') ASC, game_id ASC
            """,
            (team_name, team_name, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eihl_team_standing(team_name: str, season=EIHL_CURRENT_SEASON):
    """Return the League standing row for a team, or None."""
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT team, qualifier, pos, gp, pts, w, otw, l, otl, gf, ga
            FROM eihl_standings
            WHERE team = ? AND competition = 'League' AND season = ?
            """,
            (team_name, season),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_eihl_team_skaters(team_name: str, competition="League", season=EIHL_CURRENT_SEASON):
    """Return skater stats for a specific team."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT player_name, position, gp, g, a, pts, pim, plus_minus, sog
            FROM eihl_skater_stats
            WHERE team = ? AND competition = ? AND season = ?
            ORDER BY pts DESC, g DESC
            """,
            (team_name, competition, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def eihl_tables_exist() -> bool:
    """Return True if eihl_fixtures table exists (data has been scraped at least once)."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='eihl_fixtures'"
        ).fetchone()
        return row is not None
    finally:
        conn.close()
