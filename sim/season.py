"""
Season orchestration — scheduling, simulation loop, standings, playoffs.

Usage:
    from sim.season import Season
    s = Season(n_teams=8)
    s.schedule()
    s.simulate_regular_season()
    s.run_playoffs()
    standings = s.get_standings()
    scorers   = s.get_top_scorers()
"""

import random

from sim.engine import simulate_game
from sim.generator import generate_league


# ---------------------------------------------------------------------------
# Fixture scheduler — double round-robin
# ---------------------------------------------------------------------------

def _round_robin(teams: list) -> list[tuple]:
    """
    Generate a full home-and-away round-robin schedule using the standard
    rotation algorithm.

    Returns a list of (matchday, home_team, away_team) tuples.
    Matchdays are numbered 1 … 2*(N-1). Within each matchday the order is
    fixed; matchdays themselves are in order so week-by-week play works.
    """
    t = list(teams)
    if len(t) % 2 == 1:
        t.append(None)          # dummy bye slot
    n = len(t)
    n_rounds = n - 1            # rounds per half

    first_half: list[tuple] = []
    for r in range(n_rounds):
        md = r + 1
        for i in range(n // 2):
            home = t[i]
            away = t[n - 1 - i]
            if home is not None and away is not None:
                first_half.append((md, home, away))
        # Rotate: pin element 0, rotate the rest clockwise
        t = [t[0]] + [t[-1]] + t[1:-1]

    # Second half: reverse home/away, matchdays continue from n_rounds+1
    second_half = [(md + n_rounds, away, home) for md, home, away in first_half]

    return first_half + second_half


# ---------------------------------------------------------------------------
# Season class
# ---------------------------------------------------------------------------

class Season:
    """
    Manages one simulated season: team generation, scheduling, simulation,
    standings, player stats, and playoffs.
    """

    def __init__(
        self,
        n_teams: int = 8,
        name: str = "Sim Hockey League",
        season_label: str = "2026-27",
        n_playoff_teams: int = 4,
    ):
        self.name            = name
        self.season_label    = season_label
        self.n_playoff_teams = n_playoff_teams
        self.teams           = generate_league(n_teams)
        self.team_map        = {t["name"]: t for t in self.teams}

        self.fixtures:         list[tuple]  = []   # (home_team, away_team)
        self.results:          list[dict]   = []   # full result dicts from engine
        self.standings:        dict         = self._empty_standings()
        self.player_stats:     dict         = {}   # (team_name, player_name) → stats
        self.playoff_results:  list[tuple]  = []   # (label, result_dict)
        self.champion:         str | None   = None

    # ── Standings init ────────────────────────────────────────────────────

    def _empty_standings(self) -> dict:
        return {
            t["name"]: {
                "team": t["name"],
                "gp": 0, "w": 0, "otw": 0, "l": 0, "otl": 0,
                "gf": 0, "ga": 0, "pts": 0,
            }
            for t in self.teams
        }

    # ── Scheduling ────────────────────────────────────────────────────────

    def schedule(self) -> None:
        """Build the full regular-season fixture list."""
        self.fixtures = _round_robin(self.teams)

    # ── Regular season ────────────────────────────────────────────────────

    def simulate_regular_season(self, progress_cb=None) -> None:
        """
        Simulate every regular-season fixture.
        progress_cb(current, total) is called after each game if provided.
        """
        total = len(self.fixtures)
        for i, (md, home, away) in enumerate(self.fixtures):
            result = simulate_game(home, away)
            self.results.append(result)
            self._update_standings(result)
            self._update_player_stats(result, home, away)
            if progress_cb:
                progress_cb(i + 1, total)

    def _update_standings(self, result: dict) -> None:
        ht  = result["home_team"]
        at  = result["away_team"]
        hs  = result["home_score"]
        as_ = result["away_score"]
        rt  = result["result_type"]

        sh = self.standings[ht]
        sa = self.standings[at]

        sh["gp"] += 1
        sa["gp"] += 1
        sh["gf"] += hs
        sh["ga"] += as_
        sa["gf"] += as_
        sa["ga"] += hs

        if hs > as_:                  # home win
            if rt == "REG":
                sh["w"]   += 1;  sh["pts"] += 2
                sa["l"]   += 1
            else:                     # OT / SO win
                sh["otw"] += 1;  sh["pts"] += 2
                sa["otl"] += 1;  sa["pts"] += 1
        else:                         # away win
            if rt == "REG":
                sa["w"]   += 1;  sa["pts"] += 2
                sh["l"]   += 1
            else:
                sa["otw"] += 1;  sa["pts"] += 2
                sh["otl"] += 1;  sh["pts"] += 1

    def _update_player_stats(self, result: dict, home: dict, away: dict) -> None:
        # Increment GP for every active player on both teams
        for team in (home, away):
            for player in self._active_players(team):
                key = (team["name"], player["name"])
                self.player_stats.setdefault(key, {
                    "team":     team["name"],
                    "name":     player["name"],
                    "position": player["position"],
                    "g": 0, "a": 0, "gp": 0,
                })
                self.player_stats[key]["gp"] += 1

        # Goals and assists from events
        for ev in result["events"]:
            if ev["type"] != "goal":
                continue
            team_name = ev["team"]
            for role, stat in (("scorer", "g"), ("assist1", "a"), ("assist2", "a")):
                name = ev.get(role)
                if not name:
                    continue
                key = (team_name, name)
                if key not in self.player_stats:
                    self.player_stats[key] = {
                        "team": team_name, "name": name,
                        "position": "?", "g": 0, "a": 0, "gp": 0,
                    }
                self.player_stats[key][stat] += 1

    @staticmethod
    def _active_players(team: dict) -> list:
        players = []
        for line in team.get("lines", []):
            for slot in ("lw", "c", "rw"):
                if line.get(slot):
                    players.append(line[slot])
        for pair in team.get("pairings", []):
            for slot in ("ld", "rd"):
                if pair.get(slot):
                    players.append(pair[slot])
        for g in team.get("goalies", []):
            if g:
                players.append(g)
        return players

    @property
    def total_matchdays(self) -> int:
        """Number of matchdays in the regular season."""
        if not self.fixtures:
            return 0
        return max(md for md, _, _ in self.fixtures)

    # ── Standings / scorers ───────────────────────────────────────────────

    def get_standings(self) -> list[dict]:
        """Return standings sorted by PTS → GD → GF."""
        rows = list(self.standings.values())
        rows.sort(
            key=lambda r: (r["pts"], r["gf"] - r["ga"], r["gf"]),
            reverse=True,
        )
        for i, row in enumerate(rows):
            row["pos"] = i + 1
        return rows

    def get_top_scorers(self, n: int = 20) -> list[dict]:
        """Return top n skaters by points (G+A)."""
        stats = [
            {**v, "pts": v["g"] + v["a"]}
            for v in self.player_stats.values()
            if v.get("position") not in ("G", "GK")
        ]
        stats.sort(key=lambda s: (s["pts"], s["g"]), reverse=True)
        return stats[:n]

    # ── Playoffs ──────────────────────────────────────────────────────────

    def _winner(self, result: dict) -> dict:
        """Return the winning team dict from a result."""
        winner_name = (
            result["home_team"]
            if result["home_score"] > result["away_score"]
            else result["away_team"]
        )
        return self.team_map[winner_name]

    def run_playoffs(self) -> None:
        """
        Simulate single-elimination playoffs using top n_playoff_teams.
        Supports 4-team (SF + Final) or 8-team (QF + SF + Final) brackets.
        """
        standings  = self.get_standings()
        qualifiers = [self.team_map[row["team"]] for row in standings[: self.n_playoff_teams]]

        if self.n_playoff_teams == 4:
            self._run_4team(qualifiers)
        elif self.n_playoff_teams == 8:
            self._run_8team(qualifiers)
        else:
            # Fallback: halve until 4 remain, then run 4-team
            survivors = self._run_qf_round(qualifiers)
            while len(survivors) > 4:
                survivors = self._run_qf_round(survivors)
            self._run_4team(survivors)

    def _run_4team(self, q: list) -> None:
        """1 vs 4, 2 vs 3 semis → final."""
        sf1 = simulate_game(q[0], q[3])
        sf2 = simulate_game(q[1], q[2])
        self.playoff_results.append(("Semi-Final 1", sf1))
        self.playoff_results.append(("Semi-Final 2", sf2))

        final = simulate_game(self._winner(sf1), self._winner(sf2))
        self.playoff_results.append(("Final", final))
        self.champion = (
            final["home_team"]
            if final["home_score"] > final["away_score"]
            else final["away_team"]
        )

    def _run_8team(self, q: list) -> None:
        """1v8, 2v7, 3v6, 4v5 QFs → 4-team SF+Final."""
        qf_pairs = [(0, 7), (1, 6), (2, 5), (3, 4)]
        survivors = []
        for s1, s2 in qf_pairs:
            res = simulate_game(q[s1], q[s2])
            self.playoff_results.append(
                (f"QF: {q[s1]['name']} vs {q[s2]['name']}", res)
            )
            survivors.append(self._winner(res))
        self._run_4team(survivors)

    def _run_qf_round(self, teams: list) -> list:
        """Generic pair-off: first vs last, etc. Returns winners."""
        survivors = []
        n = len(teams)
        for i in range(n // 2):
            res = simulate_game(teams[i], teams[n - 1 - i])
            self.playoff_results.append(
                (f"Round: {teams[i]['name']} vs {teams[n-1-i]['name']}", res)
            )
            survivors.append(self._winner(res))
        return survivors

    # ── Persistence ───────────────────────────────────────────────────────

    def save_structure_to_db(self) -> tuple[int, dict, dict]:
        """
        Persist the league structure (teams, players, fixtures) WITHOUT results.
        Used for managed seasons where games are simulated one matchday at a time.
        Returns (league_id, team_id_map {name→id}, player_id_map {(team,player)→id}).
        """
        from sim.db import (
            get_conn, init_schema, insert_league, insert_team,
            insert_player, insert_fixture,
        )

        conn = get_conn()
        init_schema(conn)

        league_id = insert_league(conn, self.name, self.season_label, len(self.teams))

        team_id_map:   dict[str, int]   = {}
        player_id_map: dict[tuple, int] = {}

        for team in self.teams:
            team_id = insert_team(conn, league_id, team["name"], 0)
            team_id_map[team["name"]] = team_id

            for line in team.get("lines", []):
                for slot in ("lw", "c", "rw"):
                    p = line.get(slot)
                    if p:
                        pid = insert_player(conn, team_id, p, line["line"], slot)
                        player_id_map[(team["name"], p["name"])] = pid

            for pair in team.get("pairings", []):
                for slot in ("ld", "rd"):
                    p = pair.get(slot)
                    if p:
                        pid = insert_player(conn, team_id, p, pair["pairing"], slot)
                        player_id_map[(team["name"], p["name"])] = pid

            for i, g in enumerate(team.get("goalies", [])):
                if g:
                    pid = insert_player(conn, team_id, g, i + 1, "g")
                    player_id_map[(team["name"], g["name"])] = pid

        for md, home, away in self.fixtures:
            insert_fixture(
                conn, league_id, md, "regular",
                team_id_map[home["name"]], team_id_map[away["name"]],
            )

        conn.close()
        return league_id, team_id_map, player_id_map

    def save_to_db(self) -> int:
        """
        Persist the completed season to sim.db.
        Returns the newly created league_id.
        """
        from sim.db import (
            get_conn, init_schema, insert_league, insert_team,
            insert_player, insert_fixture, record_fixture_result,
            upsert_standing, upsert_player_stat,
        )

        conn = get_conn()
        init_schema(conn)

        league_id = insert_league(conn, self.name, self.season_label, len(self.teams))

        team_id_map:   dict[str, int]   = {}
        player_id_map: dict[tuple, int] = {}

        for team in self.teams:
            team_id = insert_team(conn, league_id, team["name"], 0)
            team_id_map[team["name"]] = team_id

            for line in team.get("lines", []):
                for slot in ("lw", "c", "rw"):
                    p = line.get(slot)
                    if p:
                        pid = insert_player(conn, team_id, p, line["line"], slot)
                        player_id_map[(team["name"], p["name"])] = pid

            for pair in team.get("pairings", []):
                for slot in ("ld", "rd"):
                    p = pair.get(slot)
                    if p:
                        pid = insert_player(conn, team_id, p, pair["pairing"], slot)
                        player_id_map[(team["name"], p["name"])] = pid

            for i, g in enumerate(team.get("goalies", [])):
                if g:
                    pid = insert_player(conn, team_id, g, i + 1, "g")
                    player_id_map[(team["name"], g["name"])] = pid

        for (md, home, away), result in zip(self.fixtures, self.results):
            fid = insert_fixture(
                conn, league_id, md, "regular",
                team_id_map[home["name"]], team_id_map[away["name"]],
            )
            record_fixture_result(conn, fid, result)

        for label, result in self.playoff_results:
            if label.startswith("QF"):
                phase = "playoff_qf"
            elif "Semi" in label:
                phase = "playoff_sf"
            else:
                phase = "playoff_final"
            fid = insert_fixture(
                conn, league_id, None, phase,
                team_id_map[result["home_team"]], team_id_map[result["away_team"]],
            )
            record_fixture_result(conn, fid, result)

        for row in self.get_standings():
            upsert_standing(conn, league_id, team_id_map[row["team"]], "regular", row)

        for (team_name, player_name), stats in self.player_stats.items():
            key = (team_name, player_name)
            if key in player_id_map:
                upsert_player_stat(
                    conn, league_id, player_id_map[key], "regular",
                    stats["gp"], stats["g"], stats["a"],
                )

        conn.close()
        return league_id

    # ── Summary ───────────────────────────────────────────────────────────

    def total_goals(self) -> int:
        return sum(r["home_score"] + r["away_score"] for r in self.results)

    def games_to_ot(self) -> int:
        return sum(1 for r in self.results if r["result_type"] in ("OT", "SO"))
