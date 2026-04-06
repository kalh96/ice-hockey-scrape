"""Read-only database queries for the web layer."""

import sqlite3
from config import DB_PATH, CURRENT_SEASON


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_standings(comp_name="SNL", season=CURRENT_SEASON):
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
            WHERE c.name = ? AND s.season = ?
            ORDER BY s.pos
            """,
            (comp_name, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_results(comp_name="SNL", season=CURRENT_SEASON, limit=5):
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
              AND f.season = ?
              AND (? = 'all' OR c.name = ?)
            ORDER BY COALESCE(f.date, '0') DESC, f.event_id DESC
            LIMIT ?
            """,
            (season, comp_name, comp_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_upcoming_fixtures(comp_name="SNL", season=CURRENT_SEASON, limit=5):
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
              AND f.season = ?
              AND (? = 'all' OR c.name = ?)
            ORDER BY COALESCE(f.date, 'z') ASC, f.event_id ASC
            LIMIT ?
            """,
            (season, comp_name, comp_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_fixtures(comp_name="all", season=CURRENT_SEASON):
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
            WHERE f.season = ?
              AND (? = 'all' OR c.name = ?)
            ORDER BY f.status ASC,
                     COALESCE(f.date, 'z') DESC,
                     f.event_id DESC
            """,
            (season, comp_name, comp_name),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _skater_stats_from_events(conn, comp_name, season):
    """Aggregate skater stats from event_player_stats (used for competitions
    with no dedicated SIHA stats page, e.g. SNL Play-offs)."""
    rows = conn.execute(
        """
        SELECT p.name AS player_name, t.name AS team_name,
               eps.position,
               COUNT(DISTINCT eps.event_id) AS gp,
               SUM(eps.goals)                AS goals,
               SUM(eps.assists)              AS assists,
               SUM(eps.goals + eps.assists)  AS total_points,
               SUM(eps.pim)                  AS pim
        FROM event_player_stats eps
        JOIN players p      ON p.id = eps.player_id
        JOIN teams t        ON t.id = eps.team_id
        JOIN fixtures f     ON f.event_id = eps.event_id
        JOIN competitions c ON c.id = f.competition_id
        WHERE c.name = ? AND f.season = ? AND eps.position != 'GK'
        GROUP BY eps.player_id, eps.team_id
        ORDER BY total_points DESC, goals DESC, assists DESC
        """,
        (comp_name, season),
    ).fetchall()
    return [dict(r) for r in rows]


def _netminder_stats_from_events(conn, comp_name, season):
    """Aggregate netminder stats from event_player_stats."""
    rows = conn.execute(
        """
        SELECT p.name AS player_name, t.name AS team_name,
               COUNT(DISTINCT eps.event_id) AS gp,
               SUM(eps.shots_against)       AS shots_against,
               SUM(eps.saves)               AS saves,
               SUM(eps.goals_against)       AS goals_against,
               CASE WHEN SUM(eps.shots_against) > 0
                    THEN CAST(SUM(eps.saves) AS REAL) / SUM(eps.shots_against)
                    ELSE NULL END            AS save_pct,
               NULL                         AS gaa,
               NULL                         AS toi
        FROM event_player_stats eps
        JOIN players p      ON p.id = eps.player_id
        JOIN teams t        ON t.id = eps.team_id
        JOIN fixtures f     ON f.event_id = eps.event_id
        JOIN competitions c ON c.id = f.competition_id
        WHERE c.name = ? AND f.season = ? AND eps.position = 'GK'
        GROUP BY eps.player_id, eps.team_id
        ORDER BY save_pct DESC
        """,
        (comp_name, season),
    ).fetchall()
    return [dict(r) for r in rows]


def get_skater_stats(comp_name="SNL", season=CURRENT_SEASON):
    conn = get_connection()
    try:
        # Competitions without a dedicated SIHA stats page are aggregated
        # directly from individual game events.
        if comp_name == "SNL Play-offs":
            return _skater_stats_from_events(conn, comp_name, season)
        rows = conn.execute(
            """
            SELECT p.name AS player_name, t.name AS team_name,
                   s.position, s.gp, s.goals, s.assists, s.total_points, s.pim
            FROM season_skater_stats s
            JOIN players p ON p.id = s.player_id
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE c.name = ? AND s.season = ?
            ORDER BY s.total_points DESC, s.goals DESC, s.assists DESC
            """,
            (comp_name, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_netminder_stats(comp_name="SNL", season=CURRENT_SEASON):
    conn = get_connection()
    try:
        if comp_name == "SNL Play-offs":
            return _netminder_stats_from_events(conn, comp_name, season)
        rows = conn.execute(
            """
            SELECT p.name AS player_name, t.name AS team_name,
                   s.gp, s.shots_against, s.saves, s.goals_against,
                   s.save_pct, s.gaa, s.toi
            FROM season_netminder_stats s
            JOIN players p ON p.id = s.player_id
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE c.name = ? AND s.season = ?
            ORDER BY s.save_pct DESC
            """,
            (comp_name, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_team_recent_results(db_name, season=CURRENT_SEASON, limit=5):
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
              AND f.season = ?
              AND (ht.name = ? OR at.name = ?)
            ORDER BY COALESCE(f.date, '0') DESC, f.event_id DESC
            LIMIT ?
            """,
            (season, db_name, db_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_team_upcoming_fixtures(db_name, season=CURRENT_SEASON, limit=5):
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
              AND f.season = ?
              AND (ht.name = ? OR at.name = ?)
            ORDER BY COALESCE(f.date, 'z') ASC, f.event_id ASC
            LIMIT ?
            """,
            (season, db_name, db_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_team_standings_row(db_name, comp_name="SNL", season=CURRENT_SEASON):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT t.name, s.pos, s.gp, s.wins, s.losses, s.otl,
                   s.gf, s.ga, s.goal_diff, s.pts
            FROM team_season_stats s
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE t.name = ? AND c.name = ? AND s.season = ?
            LIMIT 1
            """,
            (db_name, comp_name, season),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_team_skater_stats(db_name, season=CURRENT_SEASON):
    conn = get_connection()
    try:
        # Stats from dedicated season stats pages (SNL, Scottish Cup)
        rows = conn.execute(
            """
            SELECT p.name AS player_name,
                   s.position, s.gp, s.goals, s.assists, s.total_points, s.pim,
                   c.name AS competition
            FROM season_skater_stats s
            JOIN players p ON p.id = s.player_id
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE t.name = ? AND s.season = ?
            ORDER BY c.name, s.total_points DESC, s.goals DESC
            """,
            (db_name, season),
        ).fetchall()
        results = [dict(r) for r in rows]

        # Stats aggregated from game events for SNL Play-offs
        playoff_rows = conn.execute(
            """
            SELECT p.name AS player_name, eps.position,
                   COUNT(DISTINCT eps.event_id) AS gp,
                   SUM(eps.goals)               AS goals,
                   SUM(eps.assists)             AS assists,
                   SUM(eps.goals + eps.assists) AS total_points,
                   SUM(eps.pim)                 AS pim,
                   'SNL Play-offs'              AS competition
            FROM event_player_stats eps
            JOIN players p      ON p.id = eps.player_id
            JOIN teams t        ON t.id = eps.team_id
            JOIN fixtures f     ON f.event_id = eps.event_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE t.name = ? AND f.season = ?
              AND c.name = 'SNL Play-offs' AND eps.position != 'GK'
            GROUP BY eps.player_id
            ORDER BY total_points DESC, goals DESC
            """,
            (db_name, season),
        ).fetchall()
        results += [dict(r) for r in playoff_rows]
        return results
    finally:
        conn.close()


def get_team_netminder_stats(db_name, season=CURRENT_SEASON):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.name AS player_name,
                   s.gp, s.shots_against, s.saves, s.goals_against,
                   s.save_pct, s.gaa, s.toi,
                   c.name AS competition
            FROM season_netminder_stats s
            JOIN players p ON p.id = s.player_id
            JOIN teams t ON t.id = s.team_id
            JOIN competitions c ON c.id = s.competition_id
            WHERE t.name = ? AND s.season = ?
            ORDER BY s.save_pct DESC
            """,
            (db_name, season),
        ).fetchall()
        results = [dict(r) for r in rows]

        # Netminder stats from game events for SNL Play-offs
        playoff_rows = conn.execute(
            """
            SELECT p.name AS player_name,
                   COUNT(DISTINCT eps.event_id) AS gp,
                   SUM(eps.shots_against)       AS shots_against,
                   SUM(eps.saves)               AS saves,
                   SUM(eps.goals_against)       AS goals_against,
                   CASE WHEN SUM(eps.shots_against) > 0
                        THEN CAST(SUM(eps.saves) AS REAL) / SUM(eps.shots_against)
                        ELSE NULL END            AS save_pct,
                   NULL                         AS gaa,
                   NULL                         AS toi,
                   'SNL Play-offs'              AS competition
            FROM event_player_stats eps
            JOIN players p      ON p.id = eps.player_id
            JOIN teams t        ON t.id = eps.team_id
            JOIN fixtures f     ON f.event_id = eps.event_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE t.name = ? AND f.season = ?
              AND c.name = 'SNL Play-offs' AND eps.position = 'GK'
            GROUP BY eps.player_id
            ORDER BY save_pct DESC
            """,
            (db_name, season),
        ).fetchall()
        results += [dict(r) for r in playoff_rows]
        return results
    finally:
        conn.close()


def get_fixtures_by_ids(event_ids):
    """Return {event_id: fixture dict} for a list of event IDs."""
    if not event_ids:
        return {}
    conn = get_connection()
    try:
        placeholders = ','.join('?' * len(event_ids))
        rows = conn.execute(
            f"""
            SELECT f.event_id, f.date, f.status, f.home_score, f.away_score,
                   ht.name AS home_team, at.name AS away_team
            FROM fixtures f
            JOIN teams ht ON ht.id = f.home_team_id
            JOIN teams at ON at.id = f.away_team_id
            WHERE f.event_id IN ({placeholders})
            """,
            event_ids,
        ).fetchall()
        return {r['event_id']: dict(r) for r in rows}
    finally:
        conn.close()


def get_team_form(db_name, season, n=5):
    """Last n completed games for a team across all competitions, newest first.
    Each row gains: result ('W'/'L'), gf, ga, opponent, home_game."""
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
              AND f.season = ?
              AND (ht.name = ? OR at.name = ?)
            ORDER BY COALESCE(f.date, '0') DESC, f.event_id DESC
            LIMIT ?
            """,
            (season, db_name, db_name, n),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            is_home = d['home_team'] == db_name
            d['result'] = 'W' if (
                (is_home and (d['home_score'] or 0) > (d['away_score'] or 0)) or
                (not is_home and (d['away_score'] or 0) > (d['home_score'] or 0))
            ) else 'L'
            d['gf'] = d['home_score'] if is_home else d['away_score']
            d['ga'] = d['away_score'] if is_home else d['home_score']
            d['opponent'] = d['away_team'] if is_home else d['home_team']
            d['home_game'] = is_home
            results.append(d)
        return results
    finally:
        conn.close()


def get_head_to_head(team1_db, team2_db, season):
    """All completed games between two teams this season, newest first."""
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
              AND f.season = ?
              AND (
                (ht.name = ? AND at.name = ?)
                OR  (ht.name = ? AND at.name = ?)
              )
            ORDER BY COALESCE(f.date, '0') DESC, f.event_id DESC
            """,
            (season, team1_db, team2_db, team2_db, team1_db),
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
