"""Read-only DB query helpers for the simulation web UI."""

from sim.db import get_conn


def get_all_leagues():
    """Return all leagues, newest first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, season, n_teams, created_at FROM sim_leagues ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_league(league_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM sim_leagues WHERE id=?", (league_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_standings(league_id: int):
    """Return final regular-season standings with team names and pos column."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.gp, s.w, s.otw, s.l, s.otl, s.gf, s.ga, s.pts,
               t.name AS team, t.id AS team_id
        FROM sim_standings s
        JOIN sim_teams t ON s.team_id = t.id
        WHERE s.league_id=? AND s.phase='regular'
        ORDER BY s.pts DESC, (s.gf - s.ga) DESC, s.gf DESC
    """, (league_id,)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    for i, r in enumerate(result):
        r["pos"] = i + 1
        r["gd"]  = r["gf"] - r["ga"]
    return result


def get_top_scorers(league_id: int, n: int = 20):
    conn = get_conn()
    rows = conn.execute("""
        SELECT ps.gp, ps.g, ps.a, ps.pts,
               p.name AS player, p.position,
               t.name AS team, t.id AS team_id
        FROM sim_player_stats ps
        JOIN sim_players p ON ps.player_id = p.id
        JOIN sim_teams t ON p.team_id = t.id
        WHERE ps.league_id=? AND ps.phase='regular' AND p.position != 'G'
        ORDER BY ps.pts DESC, ps.g DESC
        LIMIT ?
    """, (league_id, n)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_results(league_id: int, phase: str = "regular", limit: int | None = None):
    conn = get_conn()
    q = """
        SELECT f.id, f.phase, f.home_score, f.away_score, f.result_type,
               ht.name AS home_team, ht.id AS home_team_id,
               at.name AS away_team, at.id AS away_team_id
        FROM sim_fixtures f
        JOIN sim_teams ht ON f.home_team_id = ht.id
        JOIN sim_teams at ON f.away_team_id = at.id
        WHERE f.league_id=? AND f.phase=? AND f.played=1
        ORDER BY f.id DESC
    """
    params: list = [league_id, phase]
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_playoff_results(league_id: int):
    """Return all playoff fixtures in chronological order."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.id, f.phase, f.home_score, f.away_score, f.result_type,
               ht.name AS home_team, ht.id AS home_team_id,
               at.name AS away_team, at.id AS away_team_id
        FROM sim_fixtures f
        JOIN sim_teams ht ON f.home_team_id = ht.id
        JOIN sim_teams at ON f.away_team_id = at.id
        WHERE f.league_id=? AND f.phase != 'regular'
        ORDER BY f.id ASC
    """, (league_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fixture(fixture_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT f.*,
               ht.name AS home_team, ht.id AS home_team_id,
               at.name AS away_team, at.id AS away_team_id,
               l.name AS league_name, l.season, l.id AS league_id
        FROM sim_fixtures f
        JOIN sim_teams ht ON f.home_team_id = ht.id
        JOIN sim_teams at ON f.away_team_id = at.id
        JOIN sim_leagues l ON f.league_id = l.id
        WHERE f.id=?
    """, (fixture_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_fixture_events(fixture_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sim_game_events WHERE fixture_id=? ORDER BY id ASC",
        (fixture_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_team(team_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT t.*, l.name AS league_name, l.season, l.id AS league_id
        FROM sim_teams t
        JOIN sim_leagues l ON t.league_id = l.id
        WHERE t.id=?
    """, (team_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_team_players(team_id: int, league_id: int):
    """Return all players with their season stats, ordered by line slot."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*,
               COALESCE(ps.gp, 0) AS stat_gp,
               COALESCE(ps.g,  0) AS stat_g,
               COALESCE(ps.a,  0) AS stat_a,
               COALESCE(ps.pts,0) AS stat_pts
        FROM sim_players p
        LEFT JOIN sim_player_stats ps
            ON ps.player_id=p.id AND ps.league_id=? AND ps.phase='regular'
        WHERE p.team_id=?
        ORDER BY
            CASE p.position
                WHEN 'LW' THEN 1 WHEN 'C' THEN 2 WHEN 'RW' THEN 3
                WHEN 'LD' THEN 4 WHEN 'RD' THEN 5 WHEN 'G'  THEN 6
                ELSE 7
            END,
            p.line_number, p.overall DESC
    """, (league_id, team_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_team_fixtures(team_id: int, league_id: int):
    """Return all played fixtures for a team."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.id, f.phase, f.home_score, f.away_score, f.result_type,
               ht.name AS home_team, ht.id AS home_team_id,
               at.name AS away_team, at.id AS away_team_id
        FROM sim_fixtures f
        JOIN sim_teams ht ON f.home_team_id = ht.id
        JOIN sim_teams at ON f.away_team_id = at.id
        WHERE f.league_id=?
          AND (f.home_team_id=? OR f.away_team_id=?)
          AND f.played=1
        ORDER BY f.id ASC
    """, (league_id, team_id, team_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_team_standing(team_id: int, league_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT * FROM sim_standings
        WHERE team_id=? AND league_id=? AND phase='regular'
    """, (team_id, league_id)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Managed season queries
# ---------------------------------------------------------------------------

def get_all_managed_seasons():
    """Return all managed seasons with league + team name, newest first."""
    from sim.db import init_schema
    conn = get_conn()
    init_schema(conn)   # ensure table exists (safe to re-run)
    rows = conn.execute("""
        SELECT ms.*,
               l.name AS league_name, l.season,
               t.name AS team_name
        FROM sim_managed_seasons ms
        JOIN sim_leagues l ON ms.league_id = l.id
        JOIN sim_teams t ON ms.user_team_id = t.id
        ORDER BY ms.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_managed_season(game_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT ms.*,
               l.name AS league_name, l.season,
               t.name AS team_name
        FROM sim_managed_seasons ms
        JOIN sim_leagues l ON ms.league_id = l.id
        JOIN sim_teams t ON ms.user_team_id = t.id
        WHERE ms.id=?
    """, (game_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_matchday_fixtures(league_id: int, matchday: int):
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.id, f.round_num, f.played, f.home_score, f.away_score, f.result_type,
               ht.name AS home_team, ht.id AS home_team_id,
               at.name AS away_team, at.id AS away_team_id
        FROM sim_fixtures f
        JOIN sim_teams ht ON f.home_team_id = ht.id
        JOIN sim_teams at ON f.away_team_id = at.id
        WHERE f.league_id=? AND f.round_num=? AND f.phase='regular'
        ORDER BY f.id ASC
    """, (league_id, matchday)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_teams_for_league(league_id: int):
    """Return all teams in a league with their overall quality indicator."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT t.id, t.name,
               ROUND(AVG(p.overall), 1) AS avg_overall
        FROM sim_teams t
        JOIN sim_players p ON p.team_id = t.id
        WHERE t.league_id=?
        GROUP BY t.id
        ORDER BY avg_overall DESC
    """, (league_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_team_players(team_id: int):
    """Return players grouped by position pool for the line editor."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, name, position, age, overall, line_number, slot
        FROM sim_players
        WHERE team_id=?
        ORDER BY
            CASE position WHEN 'LW' THEN 1 WHEN 'C' THEN 2 WHEN 'RW' THEN 3
                          WHEN 'LD' THEN 4 WHEN 'RD' THEN 5 ELSE 6 END,
            line_number, overall DESC
    """, (team_id,)).fetchall()
    conn.close()
    by_pos: dict[str, list] = {}
    for r in rows:
        d = dict(r)
        by_pos.setdefault(d["position"], []).append(d)
    return by_pos


def get_league_champion(league_id: int):
    """Return the name of the team that won the final playoff fixture."""
    conn = get_conn()
    row = conn.execute("""
        SELECT f.home_score, f.away_score,
               ht.name AS home_team, at.name AS away_team
        FROM sim_fixtures f
        JOIN sim_teams ht ON f.home_team_id = ht.id
        JOIN sim_teams at ON f.away_team_id = at.id
        WHERE f.league_id=? AND f.phase='playoff_final' AND f.played=1
        ORDER BY f.id DESC LIMIT 1
    """, (league_id,)).fetchone()
    conn.close()
    if not row:
        return None
    r = dict(row)
    return r["home_team"] if r["home_score"] > r["away_score"] else r["away_team"]
