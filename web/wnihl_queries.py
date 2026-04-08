"""Read-only DB queries for the WNIHL web pages."""

import re
import sqlite3
from config import DB_PATH, WNIHL_CURRENT_SEASON


def slugify(name: str) -> str:
    """Convert a team name to a URL slug. 'Streatham Storm 2' → 'streatham-storm-2'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def wnihl_tables_exist() -> bool:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='wnihl_fixtures'"
        ).fetchone()
        return bool(row and row[0])
    finally:
        conn.close()


def get_wnihl_recent_results(competition: str | None, season: str, limit: int = 10) -> list[dict]:
    conn = _conn()
    try:
        if competition and competition != "all":
            rows = conn.execute(
                """SELECT * FROM wnihl_fixtures
                   WHERE season=? AND competition=? AND status='final'
                   ORDER BY date DESC NULLS LAST LIMIT ?""",
                (season, competition, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM wnihl_fixtures
                   WHERE season=? AND status='final'
                   ORDER BY date DESC NULLS LAST LIMIT ?""",
                (season, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wnihl_upcoming_fixtures(competition: str | None, season: str, limit: int = 10) -> list[dict]:
    conn = _conn()
    try:
        if competition and competition != "all":
            rows = conn.execute(
                """SELECT * FROM wnihl_fixtures
                   WHERE season=? AND competition=? AND status='scheduled'
                   ORDER BY date ASC NULLS LAST LIMIT ?""",
                (season, competition, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM wnihl_fixtures
                   WHERE season=? AND status='scheduled'
                   ORDER BY date ASC NULLS LAST LIMIT ?""",
                (season, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wnihl_all_fixtures(competition: str | None, season: str) -> list[dict]:
    conn = _conn()
    try:
        if competition and competition != "all":
            rows = conn.execute(
                """SELECT * FROM wnihl_fixtures
                   WHERE season=? AND competition=?
                   ORDER BY date ASC NULLS LAST""",
                (season, competition),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM wnihl_fixtures
                   WHERE season=?
                   ORDER BY competition, date ASC NULLS LAST""",
                (season,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wnihl_standings(competition: str | None, season: str) -> list[dict]:
    conn = _conn()
    try:
        if competition and competition != "all":
            rows = conn.execute(
                "SELECT * FROM wnihl_standings WHERE season=? AND competition=? ORDER BY pos",
                (season, competition),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM wnihl_standings WHERE season=? ORDER BY competition, pos",
                (season,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wnihl_player_stats(competition: str | None, season: str) -> list[dict]:
    conn = _conn()
    try:
        if competition and competition != "all":
            rows = conn.execute(
                """SELECT * FROM wnihl_player_stats
                   WHERE season=? AND competition=?
                   ORDER BY points DESC NULLS LAST, goals DESC NULLS LAST""",
                (season, competition),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM wnihl_player_stats
                   WHERE season=?
                   ORDER BY competition, points DESC NULLS LAST, goals DESC NULLS LAST""",
                (season,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wnihl_teams_for_nav(competition: str, season: str = WNIHL_CURRENT_SEASON) -> list[dict]:
    """Return list of {team, slug} for all teams in a competition, ordered by standing pos."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT team FROM wnihl_standings WHERE competition=? AND season=? ORDER BY pos",
            (competition, season),
        ).fetchall()
        return [{"team": r["team"], "slug": slugify(r["team"])} for r in rows]
    finally:
        conn.close()


def get_wnihl_team_by_slug(slug: str, season: str = WNIHL_CURRENT_SEASON):
    """Return {team, competition} for the team matching the slug, or None."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT team, competition FROM wnihl_standings WHERE season=? ORDER BY competition, pos",
            (season,),
        ).fetchall()
        for r in rows:
            if slugify(r["team"]) == slug:
                return {"team": r["team"], "competition": r["competition"]}
        return None
    finally:
        conn.close()


def get_wnihl_team_fixtures(team_name: str, season: str = WNIHL_CURRENT_SEASON) -> list[dict]:
    """Return all fixtures for a team, ordered by date ascending."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT fixture_id, date, home_team, away_team, home_score, away_score,
                      status, competition
               FROM wnihl_fixtures
               WHERE (home_team=? OR away_team=?) AND season=?
               ORDER BY COALESCE(date, 'z') ASC""",
            (team_name, team_name, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wnihl_team_players(team_name: str, competition: str, season: str = WNIHL_CURRENT_SEASON) -> list[dict]:
    """Return player stats for a team."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT player_name, games, goals, assists, points
               FROM wnihl_player_stats
               WHERE team=? AND competition=? AND season=?
               ORDER BY points DESC NULLS LAST, goals DESC NULLS LAST""",
            (team_name, competition, season),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
