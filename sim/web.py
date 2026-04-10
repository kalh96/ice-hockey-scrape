"""
Flask blueprint for the simulation game — mounted at /sim/.

Routes
------
GET  /sim/                       → index: list all saved seasons
POST /sim/new/                   → generate + simulate + save a new season
GET  /sim/<lid>/                 → season overview (standings + results)
GET  /sim/<lid>/scorers/         → top scorers leaderboard
GET  /sim/<lid>/match/<fid>/     → match report
GET  /sim/<lid>/team/<tid>/      → team profile + roster + stats
"""

import random
import sys
from pathlib import Path

# Ensure repo root is importable when Flask runs from web/
_REPO_ROOT = str(Path(__file__).parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.append(_REPO_ROOT)

from flask import Blueprint, abort, redirect, render_template, request, url_for

import sim.queries as sq
import sim.managed as sm
from sim.season import Season
from sim.db import get_conn, init_schema, create_managed_season

sim_bp = Blueprint("sim", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PHASE_LABELS = {
    "playoff_qf":    "Quarter-Finals",
    "playoff_sf":    "Semi-Finals",
    "playoff_final": "Final",
}


def _group_playoffs(fixtures: list[dict]) -> list[dict]:
    """Group playoff fixture list by round for template rendering."""
    order = ["playoff_qf", "playoff_sf", "playoff_final"]
    seen: set = set()
    groups: list[dict] = []
    phase_map: dict[str, list] = {}
    for f in fixtures:
        phase_map.setdefault(f["phase"], []).append(f)
    for phase in order:
        if phase in phase_map:
            groups.append({
                "label":    _PHASE_LABELS.get(phase, phase),
                "fixtures": phase_map[phase],
            })
    return groups


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@sim_bp.route("/")
def index():
    leagues = sq.get_all_leagues()
    # Attach champion name to each league for display
    for lg in leagues:
        lg["champion"] = sq.get_league_champion(lg["id"])
    return render_template("sim/index.html", leagues=leagues)


@sim_bp.route("/new/", methods=["POST"])
def new_season():
    n_teams  = int(request.form.get("n_teams",  8))
    playoffs = int(request.form.get("playoffs", 4))
    name     = (request.form.get("name",   "Sim Hockey League") or "Sim Hockey League").strip()
    season   = (request.form.get("season", "2026-27") or "2026-27").strip()
    seed_raw = request.form.get("seed", "").strip()

    n_teams  = max(4, min(16, n_teams))
    playoffs = min(playoffs, n_teams // 2 * 2)  # keep even
    playoffs = max(2, playoffs)

    if seed_raw.isdigit():
        random.seed(int(seed_raw))

    s = Season(
        n_teams=n_teams,
        name=name,
        season_label=season,
        n_playoff_teams=playoffs,
    )
    s.schedule()
    s.simulate_regular_season()
    s.run_playoffs()
    league_id = s.save_to_db()

    return redirect(url_for("sim.season", lid=league_id))


@sim_bp.route("/<int:lid>/")
def season(lid: int):
    league = sq.get_league(lid)
    if not league:
        abort(404)
    standings = sq.get_standings(lid)
    recent    = sq.get_results(lid, phase="regular", limit=10)
    playoffs  = _group_playoffs(sq.get_playoff_results(lid))
    champion  = sq.get_league_champion(lid)
    return render_template(
        "sim/season.html",
        league=league,
        standings=standings,
        recent=recent,
        playoffs=playoffs,
        champion=champion,
    )


@sim_bp.route("/<int:lid>/scorers/")
def scorers(lid: int):
    league = sq.get_league(lid)
    if not league:
        abort(404)
    scorer_list = sq.get_top_scorers(lid, n=30)
    return render_template("sim/scorers.html", league=league, scorers=scorer_list)


@sim_bp.route("/<int:lid>/match/<int:fid>/")
def match(lid: int, fid: int):
    fixture = sq.get_fixture(fid)
    if not fixture or fixture["league_id"] != lid:
        abort(404)
    events = sq.get_fixture_events(fid)
    league = sq.get_league(lid)

    # Build a running score per period for template clarity
    periods: list[dict] = []
    current: dict | None = None
    home_total = away_total = 0

    for ev in events:
        period_key = ev.get("period") or "OT"
        if current is None or current["period"] != period_key:
            current = {"period": period_key, "events": []}
            periods.append(current)
        enriched = dict(ev)
        if ev["event_type"] == "goal":
            if ev["team_name"] == fixture["home_team"]:
                home_total += 1
            else:
                away_total += 1
            enriched["home_score"] = home_total
            enriched["away_score"] = away_total
        current["events"].append(enriched)

    return render_template(
        "sim/match.html",
        fixture=fixture,
        periods=periods,
        league=league,
    )


# ---------------------------------------------------------------------------
# Phase 5 — managed play routes
# ---------------------------------------------------------------------------

@sim_bp.route("/play/")
def play_index():
    games = sq.get_all_managed_seasons()
    return render_template("sim/play_index.html", games=games)


@sim_bp.route("/play/new/", methods=["POST"])
def play_new():
    n_teams  = int(request.form.get("n_teams",  8))
    playoffs = int(request.form.get("playoffs", 4))
    name     = (request.form.get("name",   "Sim Hockey League") or "Sim Hockey League").strip()
    season   = (request.form.get("season", "2026-27") or "2026-27").strip()
    seed_raw = request.form.get("seed", "").strip()

    n_teams  = max(4, min(16, n_teams))
    playoffs = max(2, min(n_teams // 2 * 2, playoffs))

    if seed_raw.isdigit():
        random.seed(int(seed_raw))

    s = Season(n_teams=n_teams, name=name, season_label=season, n_playoff_teams=playoffs)
    s.schedule()
    league_id, _, _ = s.save_structure_to_db()

    return redirect(url_for("sim.play_pick", lid=league_id))


@sim_bp.route("/play/pick/<int:lid>/", methods=["GET", "POST"])
def play_pick(lid: int):
    league = sq.get_league(lid)
    if not league:
        abort(404)

    if request.method == "POST":
        team_id      = int(request.form.get("team_id", 0))
        playoffs     = int(request.form.get("n_playoff_teams", 4))
        if not team_id:
            abort(400)

        conn = get_conn()
        init_schema(conn)

        # Total matchdays = max round_num in fixtures
        row = conn.execute(
            "SELECT MAX(round_num) AS total FROM sim_fixtures WHERE league_id=? AND phase='regular'",
            (lid,),
        ).fetchone()
        total_md = row["total"] or 0

        game_id = create_managed_season(conn, lid, team_id, total_md, playoffs)
        conn.close()
        return redirect(url_for("sim.play_game", gid=game_id))

    teams = sq.get_teams_for_league(lid)
    return render_template("sim/play_pick.html", league=league, teams=teams)


@sim_bp.route("/play/<int:gid>/")
def play_game(gid: int):
    game = sq.get_managed_season(gid)
    if not game:
        abort(404)

    lid  = game["league_id"]
    tid  = game["user_team_id"]
    md   = game["current_matchday"]
    done = game["status"] == "finished"

    standings  = sq.get_standings(lid)
    league     = sq.get_league(lid)
    user_pos   = next((r["pos"] for r in standings if r["team_id"] == tid), "–")

    if done:
        playoffs = _group_playoffs(sq.get_playoff_results(lid))
        champion = sq.get_league_champion(lid)
        return render_template(
            "sim/play_game.html",
            game=game, league=league,
            standings=standings, playoffs=playoffs,
            champion=champion, user_pos=user_pos,
            phase="finished",
        )

    # Results of the previous matchday (if any)
    prev_md      = md - 1
    prev_results = sq.get_matchday_fixtures(lid, prev_md) if prev_md >= 1 else []
    prev_events  = {}
    if prev_md >= 1:
        for f in prev_results:
            if f["played"]:
                prev_events[f["id"]] = sq.get_fixture_events(f["id"])

    # Upcoming matchday fixtures
    upcoming = sq.get_matchday_fixtures(lid, md)

    # User's team lineup for line editor
    players_by_pos = sq.get_user_team_players(tid)

    return render_template(
        "sim/play_game.html",
        game=game, league=league,
        standings=standings,
        prev_results=prev_results, prev_events=prev_events, prev_md=prev_md,
        upcoming=upcoming,
        players_by_pos=players_by_pos,
        user_pos=user_pos,
        phase="active",
    )


@sim_bp.route("/play/<int:gid>/simulate/", methods=["POST"])
def play_simulate(gid: int):
    game = sq.get_managed_season(gid)
    if not game or game["status"] != "active":
        abort(404)

    lid = game["league_id"]
    tid = game["user_team_id"]
    md  = game["current_matchday"]

    conn = get_conn()
    init_schema(conn)

    # Apply line changes from form
    assignments = {}
    for key, val in request.form.items():
        if (key.startswith("line_") or key.startswith("pair_") or key == "goalie_starter") and val:
            try:
                assignments[key] = int(val)
            except ValueError:
                pass
    if assignments:
        sm.update_player_lines(tid, assignments, conn)

    # Simulate all games in this matchday
    sm.simulate_matchday(lid, md, conn)

    next_md = md + 1
    if next_md > game["total_matchdays"]:
        # Regular season over — run playoffs
        sm.run_managed_playoffs(gid, lid, game["n_playoff_teams"], conn)
    else:
        from sim.db import advance_managed_season
        advance_managed_season(conn, gid, new_matchday=next_md)

    conn.close()
    return redirect(url_for("sim.play_game", gid=gid))


@sim_bp.route("/<int:lid>/team/<int:tid>/")
def team(lid: int, tid: int):
    team_data = sq.get_team(tid)
    if not team_data or team_data["league_id"] != lid:
        abort(404)
    league   = sq.get_league(lid)
    players  = sq.get_team_players(tid, lid)
    fixtures = sq.get_team_fixtures(tid, lid)
    standing = sq.get_team_standing(tid, lid)

    # Split players by position group
    forwards  = [p for p in players if p["position"] in ("LW", "C", "RW")]
    defence   = [p for p in players if p["position"] in ("LD", "RD")]
    goalies   = [p for p in players if p["position"] == "G"]

    # Tag each fixture with result from team's perspective
    for f in fixtures:
        is_home = f["home_team_id"] == tid
        gf = f["home_score"] if is_home else f["away_score"]
        ga = f["away_score"] if is_home else f["home_score"]
        opp = f["away_team"] if is_home else f["home_team"]
        opp_id = f["away_team_id"] if is_home else f["home_team_id"]
        rt = f["result_type"]
        if gf > ga:
            res = "W" if rt == "REG" else "OTW"
        else:
            res = "L" if rt == "REG" else "OTL"
        f["gf"]     = gf
        f["ga"]     = ga
        f["opp"]    = opp
        f["opp_id"] = opp_id
        f["result"] = res
        f["venue"]  = "H" if is_home else "A"

    return render_template(
        "sim/team.html",
        team=team_data,
        league=league,
        forwards=forwards,
        defence=defence,
        goalies=goalies,
        fixtures=fixtures,
        standing=standing,
    )
