"""
Business logic for player-managed seasons (Phase 5).

Key responsibilities:
  - Reconstruct team dicts from DB (for simulate_game())
  - Simulate a single matchday and persist results incrementally
  - Update standings and player stats after each game
  - Run managed playoffs after the regular season concludes
  - Update player line assignments from user form input
"""

import sqlite3

from sim.db import get_conn, advance_managed_season
from sim.engine import simulate_game


# ---------------------------------------------------------------------------
# Team reconstruction
# ---------------------------------------------------------------------------

def reconstruct_team(team_id: int, conn: sqlite3.Connection) -> dict | None:
    """
    Rebuild a team dict from DB players, suitable for passing to simulate_game().
    Respects the current line_number / slot assignments stored in sim_players.
    """
    team_row = conn.execute(
        "SELECT * FROM sim_teams WHERE id=?", (team_id,)
    ).fetchone()
    if not team_row:
        return None

    players = conn.execute(
        "SELECT * FROM sim_players WHERE team_id=? ORDER BY line_number, slot",
        (team_id,),
    ).fetchall()

    lines    = [{"line": i + 1, "lw": None, "c": None, "rw": None} for i in range(4)]
    pairings = [{"pairing": i + 1, "ld": None, "rd": None}         for i in range(3)]
    goalies: list = []

    for p in players:
        pd   = dict(p)
        pos  = pd["position"]
        ln   = max(0, (pd.get("line_number") or 1) - 1)
        slot = pd.get("slot") or pos.lower()

        if pos in ("LW", "C", "RW"):
            if ln < len(lines):
                lines[ln][slot] = pd
        elif pos in ("LD", "RD"):
            if ln < len(pairings):
                pairings[ln][slot] = pd
        elif pos == "G":
            goalies.append(pd)

    goalies.sort(key=lambda g: g.get("line_number") or 1)

    return {
        "name":     team_row["name"],
        "lines":    lines,
        "pairings": pairings,
        "goalies":  goalies,
    }


# ---------------------------------------------------------------------------
# Incremental standings / stat updates
# ---------------------------------------------------------------------------

def _team_id_by_name(league_id: int, name: str, conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM sim_teams WHERE league_id=? AND name=?", (league_id, name)
    ).fetchone()
    return row["id"] if row else None


def _update_standings(league_id: int, result: dict, conn: sqlite3.Connection) -> None:
    ht, at  = result["home_team"], result["away_team"]
    hs, as_ = result["home_score"], result["away_score"]
    rt      = result["result_type"]

    for is_home in (True, False):
        name    = ht if is_home else at
        gf      = hs if is_home else as_
        ga      = as_ if is_home else hs
        won     = gf > ga
        team_id = _team_id_by_name(league_id, name, conn)
        if not team_id:
            continue

        conn.execute("""
            INSERT OR IGNORE INTO sim_standings
                (league_id, team_id, phase, gp, w, otw, l, otl, gf, ga, pts)
            VALUES (?,?,'regular',0,0,0,0,0,0,0,0)
        """, (league_id, team_id))

        if won and rt == "REG":
            conn.execute("""
                UPDATE sim_standings SET gp=gp+1, w=w+1, gf=gf+?, ga=ga+?, pts=pts+2
                WHERE league_id=? AND team_id=? AND phase='regular'
            """, (gf, ga, league_id, team_id))
        elif won:                               # OT / SO win
            conn.execute("""
                UPDATE sim_standings SET gp=gp+1, otw=otw+1, gf=gf+?, ga=ga+?, pts=pts+2
                WHERE league_id=? AND team_id=? AND phase='regular'
            """, (gf, ga, league_id, team_id))
        elif rt == "REG":                       # regulation loss
            conn.execute("""
                UPDATE sim_standings SET gp=gp+1, l=l+1, gf=gf+?, ga=ga+?
                WHERE league_id=? AND team_id=? AND phase='regular'
            """, (gf, ga, league_id, team_id))
        else:                                   # OT / SO loss
            conn.execute("""
                UPDATE sim_standings SET gp=gp+1, otl=otl+1, gf=gf+?, ga=ga+?, pts=pts+1
                WHERE league_id=? AND team_id=? AND phase='regular'
            """, (gf, ga, league_id, team_id))


def _update_player_stats(league_id: int, result: dict, conn: sqlite3.Connection) -> None:
    # GP for every player on both teams
    for team_name in (result["home_team"], result["away_team"]):
        team_id = _team_id_by_name(league_id, team_name, conn)
        if not team_id:
            continue
        players = conn.execute(
            "SELECT id FROM sim_players WHERE team_id=?", (team_id,)
        ).fetchall()
        for p in players:
            conn.execute("""
                INSERT OR IGNORE INTO sim_player_stats
                    (league_id, player_id, phase, gp, g, a, pts)
                VALUES (?,?,'regular',0,0,0,0)
            """, (league_id, p["id"]))
            conn.execute("""
                UPDATE sim_player_stats SET gp=gp+1
                WHERE league_id=? AND player_id=? AND phase='regular'
            """, (league_id, p["id"]))

    # Goals and assists from event log
    for ev in result.get("events", []):
        if ev["type"] != "goal":
            continue
        team_id = _team_id_by_name(league_id, ev["team"], conn)
        if not team_id:
            continue
        for attr, col in [("scorer", "g"), ("assist1", "a"), ("assist2", "a")]:
            pname = ev.get(attr)
            if not pname:
                continue
            player = conn.execute(
                "SELECT id FROM sim_players WHERE team_id=? AND name=?",
                (team_id, pname),
            ).fetchone()
            if not player:
                continue
            conn.execute(f"""
                UPDATE sim_player_stats SET {col}={col}+1, pts=pts+1
                WHERE league_id=? AND player_id=? AND phase='regular'
            """, (league_id, player["id"]))


# ---------------------------------------------------------------------------
# Matchday simulation
# ---------------------------------------------------------------------------

def simulate_matchday(league_id: int, matchday: int, conn: sqlite3.Connection) -> list[dict]:
    """
    Find all unplayed fixtures in a matchday, simulate them, persist results.
    Returns a list of result dicts (one per game), each with fixture_id added.
    """
    fixtures = conn.execute("""
        SELECT f.id, f.home_team_id, f.away_team_id
        FROM sim_fixtures f
        WHERE f.league_id=? AND f.round_num=? AND f.phase='regular' AND f.played=0
        ORDER BY f.id ASC
    """, (league_id, matchday)).fetchall()

    results = []
    for fx in fixtures:
        home = reconstruct_team(fx["home_team_id"], conn)
        away = reconstruct_team(fx["away_team_id"], conn)
        if not home or not away:
            continue

        result = simulate_game(home, away)

        conn.execute("""
            UPDATE sim_fixtures
            SET home_score=?, away_score=?, result_type=?, played=1
            WHERE id=?
        """, (result["home_score"], result["away_score"], result["result_type"], fx["id"]))

        for ev in result["events"]:
            conn.execute("""
                INSERT INTO sim_game_events
                    (fixture_id, period, time, event_type, team_name,
                     scorer_name, assist1_name, assist2_name, goal_type,
                     penalty_player, infraction, minutes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                fx["id"],
                str(ev.get("period", "")), ev.get("time", ""),
                ev["type"], ev.get("team"),
                ev.get("scorer"), ev.get("assist1"), ev.get("assist2"),
                ev.get("goal_type"),
                ev.get("player"), ev.get("infraction"), ev.get("minutes"),
            ))

        results.append({**result, "fixture_id": fx["id"]})

    conn.commit()

    for r in results:
        _update_standings(league_id, r, conn)
        _update_player_stats(league_id, r, conn)

    conn.commit()
    return results


# ---------------------------------------------------------------------------
# Managed playoffs — step-by-step (one round at a time)
# ---------------------------------------------------------------------------

def _winner_id_from_result(league_id: int, result: dict, conn: sqlite3.Connection) -> int | None:
    winner_name = (
        result["home_team"] if result["home_score"] > result["away_score"]
        else result["away_team"]
    )
    row = conn.execute(
        "SELECT id FROM sim_teams WHERE league_id=? AND name=?",
        (league_id, winner_name),
    ).fetchone()
    return row["id"] if row else None


def init_managed_playoffs(
    game_id: int,
    league_id: int,
    n_playoff_teams: int,
    conn: sqlite3.Connection,
) -> None:
    """
    Called after the regular season ends.
    Creates the first round of playoff fixtures (unplayed) and sets
    status='playoff' with playoff_round pointing to the first round.
    """
    from sim.db import insert_fixture, advance_managed_season

    standings = conn.execute("""
        SELECT t.id AS team_id
        FROM sim_standings s
        JOIN sim_teams t ON s.team_id = t.id
        WHERE s.league_id=? AND s.phase='regular'
        ORDER BY s.pts DESC, (s.gf - s.ga) DESC, s.gf DESC
        LIMIT ?
    """, (league_id, n_playoff_teams)).fetchall()

    if len(standings) < 2:
        advance_managed_season(conn, game_id, status="finished")
        return

    q = [dict(r) for r in standings]

    if n_playoff_teams >= 8:
        for s1, s2 in [(0, 7), (1, 6), (2, 5), (3, 4)]:
            insert_fixture(conn, league_id, None, "playoff_qf",
                           q[s1]["team_id"], q[s2]["team_id"])
        first_round = "playoff_qf"
    else:
        insert_fixture(conn, league_id, None, "playoff_sf",
                       q[0]["team_id"], q[3]["team_id"])
        insert_fixture(conn, league_id, None, "playoff_sf",
                       q[1]["team_id"], q[2]["team_id"])
        first_round = "playoff_sf"

    conn.commit()
    advance_managed_season(conn, game_id, status="playoff", playoff_round=first_round)


def simulate_playoff_round(
    game_id: int,
    league_id: int,
    phase: str,
    conn: sqlite3.Connection,
) -> list[int]:
    """
    Simulate all unplayed fixtures for the current playoff phase.
    Creates next-round fixtures and advances the managed season state.
    Returns list of winner team IDs in bracket order.
    """
    from sim.db import insert_fixture, record_fixture_result, advance_managed_season

    fixtures = conn.execute("""
        SELECT f.id, f.home_team_id, f.away_team_id
        FROM sim_fixtures f
        WHERE f.league_id=? AND f.phase=? AND f.played=0
        ORDER BY f.id ASC
    """, (league_id, phase)).fetchall()

    winner_ids: list[int] = []
    for fx in fixtures:
        home = reconstruct_team(fx["home_team_id"], conn)
        away = reconstruct_team(fx["away_team_id"], conn)
        if not home or not away:
            continue
        result = simulate_game(home, away)
        record_fixture_result(conn, fx["id"], result)
        wid = _winner_id_from_result(league_id, result, conn)
        if wid:
            winner_ids.append(wid)

    conn.commit()

    if phase == "playoff_qf" and len(winner_ids) >= 4:
        insert_fixture(conn, league_id, None, "playoff_sf", winner_ids[0], winner_ids[3])
        insert_fixture(conn, league_id, None, "playoff_sf", winner_ids[1], winner_ids[2])
        conn.commit()
        advance_managed_season(conn, game_id, status="playoff", playoff_round="playoff_sf")
    elif phase == "playoff_sf" and len(winner_ids) >= 2:
        insert_fixture(conn, league_id, None, "playoff_final", winner_ids[0], winner_ids[1])
        conn.commit()
        advance_managed_season(conn, game_id, status="playoff", playoff_round="playoff_final")
    elif phase == "playoff_final":
        advance_managed_season(conn, game_id, status="finished")

    return winner_ids


# ---------------------------------------------------------------------------
# Line assignment updates
# ---------------------------------------------------------------------------

def update_player_lines(team_id: int, assignments: dict, conn: sqlite3.Connection) -> None:
    """
    Update line_number and slot for the user's team from form input.

    assignments: dict mapping "line_{n}_{slot}" → player_id (int)
    e.g. {"line_1_lw": 42, "line_2_c": 17, "pair_1_ld": 55, ...}
    """
    for key, player_id in assignments.items():
        if not player_id:
            continue
        if key.startswith("line_"):
            _, n, slot = key.split("_", 2)
            conn.execute("""
                UPDATE sim_players SET line_number=?, slot=?
                WHERE id=? AND team_id=?
            """, (int(n), slot, int(player_id), team_id))
        elif key.startswith("pair_"):
            _, n, slot = key.split("_", 2)
            conn.execute("""
                UPDATE sim_players SET line_number=?, slot=?
                WHERE id=? AND team_id=?
            """, (int(n), slot, int(player_id), team_id))
        elif key == "goalie_starter":
            conn.execute("""
                UPDATE sim_players SET line_number=1
                WHERE id=? AND team_id=?
            """, (int(player_id), team_id))
            conn.execute("""
                UPDATE sim_players SET line_number=2
                WHERE team_id=? AND position='G' AND id!=?
            """, (team_id, int(player_id)))
    conn.commit()
