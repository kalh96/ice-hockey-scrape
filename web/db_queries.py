"""Read-only database queries for the web layer."""

import sqlite3
from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_standings(comp_name="SNL"):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT t.name, t.slug,
                   s.pos, s.gp, s.wins, s.losses, s.otl,
                   s.gf, s.ga, s.goal_diff, s.pts
            FROM team_season_stats s
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE c.name = ?
            ORDER BY s.pos
            """,
            (comp_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_results(comp_name="SNL", limit=5):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT f.event_id, f.date, f.home_score, f.away_score,
                   ht.name AS home_team, at.name AS away_team,
                   c.name AS competition
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE f.status = 'final'
              AND (? = 'all' OR c.name = ?)
            ORDER BY COALESCE(f.date, '0') DESC, f.event_id DESC
            LIMIT ?
            """,
            (comp_name, comp_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_upcoming_fixtures(comp_name="SNL", limit=5):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT f.event_id, f.date,
                   ht.name AS home_team, at.name AS away_team,
                   c.name AS competition
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE f.status = 'scheduled'
              AND (? = 'all' OR c.name = ?)
            ORDER BY COALESCE(f.date, 'z') ASC, f.event_id ASC
            LIMIT ?
            """,
            (comp_name, comp_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_fixtures(comp_name="all"):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT f.event_id, f.date, f.home_score, f.away_score, f.status,
                   ht.name AS home_team, at.name AS away_team,
                   c.name AS competition
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE (? = 'all' OR c.name = ?)
            ORDER BY f.status ASC,
                     COALESCE(f.date, 'z') DESC,
                     f.event_id DESC
            """,
            (comp_name, comp_name),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_skater_stats(comp_name="SNL"):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.name AS player_name, t.name AS team_name,
                   s.position, s.gp, s.goals, s.assists, s.total_points, s.pim
            FROM season_skater_stats s
            JOIN players p ON p.id = s.player_id
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE c.name = ?
            ORDER BY s.total_points DESC, s.goals DESC, s.assists DESC
            """,
            (comp_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_netminder_stats(comp_name="SNL"):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.name AS player_name, t.name AS team_name,
                   s.gp, s.shots_against, s.saves, s.goals_against,
                   s.save_pct, s.gaa, s.toi
            FROM season_netminder_stats s
            JOIN players p ON p.id = s.player_id
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE c.name = ?
            ORDER BY s.save_pct DESC
            """,
            (comp_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_event_detail(event_id):
    conn = get_connection()
    try:
        fixture = conn.execute(
            """
            SELECT f.event_id, f.date, f.home_score, f.away_score, f.status,
                   ht.name AS home_team, at.name AS away_team,
                   c.name AS competition
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE f.event_id = ?
            """,
            (event_id,),
        ).fetchone()

        if fixture is None:
            return None

        period_scores = conn.execute(
            """
            SELECT t.name AS team_name, eps.period_1, eps.period_2,
                   eps.period_3, eps.ppg, eps.ppo, eps.outcome
            FROM event_period_scores eps
            JOIN teams t ON t.id = eps.team_id
            WHERE eps.event_id = ?
            ORDER BY eps.outcome DESC
            """,
            (event_id,),
        ).fetchall()

        player_stats = conn.execute(
            """
            SELECT p.name AS player_name, t.name AS team_name,
                   eps.jersey_number, eps.position,
                   eps.goals, eps.assists, eps.pim,
                   eps.shots_against, eps.saves, eps.goals_against, eps.toi
            FROM event_player_stats eps
            JOIN players p ON p.id = eps.player_id
            JOIN teams t ON t.id = eps.team_id
            WHERE eps.event_id = ?
            ORDER BY t.id, eps.position, CAST(eps.jersey_number AS INTEGER)
            """,
            (event_id,),
        ).fetchall()

        return {
            "fixture": dict(fixture),
            "period_scores": [dict(r) for r in period_scores],
            "player_stats": [dict(r) for r in player_stats],
        }
    finally:
        conn.close()
