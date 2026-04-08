"""Read-only DB queries for the WNIHL web pages."""

import sqlite3
from config import DB_PATH


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
