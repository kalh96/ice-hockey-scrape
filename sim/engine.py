"""
Match simulation engine.

Given two team dicts (as produced by generator.generate_team), simulates a
full game and returns a result dict containing the score and a chronological
list of events (goals and penalties).
"""

import random

from sim.config import (
    EVENTS_PER_PERIOD, OT_EVENTS,
    SHOT_BASE_PROB, GOAL_BASE_RATE,
    SHOT_DIFF_FACTOR, GOAL_DIFF_FACTOR,
    PP_SHOT_BONUS, PP_GOAL_BONUS, PP_EVENTS,
    PENALTY_PROB, HOME_ADVANTAGE,
    FATIGUE_BASE, FATIGUE_STAMINA,
    LINE_WEIGHTS, PAIRING_WEIGHTS,
    INFRACTIONS,
)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _line_attack_score(line: dict) -> float:
    """
    Forward line attack quality.
    Wings contribute shooting; centre contributes passing; all contribute
    a skating component that reflects zone-entry and puck-carrying ability.
    """
    players = [p for p in (line.get("lw"), line.get("c"), line.get("rw")) if p]
    if not players:
        return 10.0
    shooting = sum(p.get("shooting", 10) for p in players) / len(players)
    passing  = sum(p.get("passing",  10) for p in players) / len(players)
    skating  = sum(p.get("skating",  10) for p in players) / len(players)
    return shooting * 0.45 + passing * 0.30 + skating * 0.25


def _pairing_defence_score(pairing: dict) -> float:
    """Defensive pairing quality — pure defensive suppression."""
    players = [p for p in (pairing.get("ld"), pairing.get("rd")) if p]
    if not players:
        return 10.0
    defence  = sum(p.get("defence",     10) for p in players) / len(players)
    physical = sum(p.get("physicality", 10) for p in players) / len(players)
    skating  = sum(p.get("skating",     10) for p in players) / len(players)
    return defence * 0.55 + physical * 0.25 + skating * 0.20


def _goalie_score(goalie: dict | None) -> float:
    """Goalie save quality."""
    if not goalie:
        return 10.0
    return (
        goalie.get("positioning",     10) * 0.45
        + goalie.get("reflexes",      10) * 0.40
        + goalie.get("rebound_control", 10) * 0.15
    )


def _team_avg_stamina(team: dict) -> float:
    """Average stamina of all active skaters (lines + pairings)."""
    players = []
    for line in team.get("lines", []):
        for slot in ("lw", "c", "rw"):
            if line.get(slot):
                players.append(line[slot])
    for pair in team.get("pairings", []):
        for slot in ("ld", "rd"):
            if pair.get(slot):
                players.append(pair[slot])
    if not players:
        return 10.0
    return sum(p.get("stamina", 10) for p in players) / len(players)


# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------

def _pick_line(lines: list) -> dict:
    """Weighted random line — first line gets most ice time."""
    w = LINE_WEIGHTS[:len(lines)]
    return random.choices(lines, weights=w, k=1)[0]


def _pick_pairing(pairings: list) -> dict:
    """Weighted random pairing — first pairing gets most ice time."""
    w = PAIRING_WEIGHTS[:len(pairings)]
    return random.choices(pairings, weights=w, k=1)[0]


def _pick_scorer(line: dict) -> tuple:
    """
    Return (scorer, assist1, assist2) from a forward line.
    Scorer weighted by shooting; assists weighted by passing.
    """
    players = [p for p in (line.get("lw"), line.get("c"), line.get("rw")) if p]
    if not players:
        return None, None, None

    shoot_w = [p.get("shooting", 10) for p in players]
    scorer  = random.choices(players, weights=shoot_w, k=1)[0]

    others = [p for p in players if p is not scorer]
    if not others:
        return scorer, None, None

    pass_w  = [p.get("passing", 10) for p in others]
    assist1 = random.choices(others, weights=pass_w, k=1)[0]

    remaining = [p for p in others if p is not assist1]
    assist2   = remaining[0] if remaining and random.random() < 0.55 else None

    return scorer, assist1, assist2


def _pick_random_skater(team: dict) -> dict | None:
    """Pick any skater from the active lines for a penalty."""
    players = []
    for line in team.get("lines", []):
        for slot in ("lw", "c", "rw"):
            if line.get(slot):
                players.append(line[slot])
    for pair in team.get("pairings", []):
        for slot in ("ld", "rd"):
            if pair.get(slot):
                players.append(pair[slot])
    return random.choice(players) if players else None


def _format_time(period, event_idx: int, total_events: int, period_minutes: int) -> str:
    """Format a time string like '14:23' within the period."""
    elapsed = (event_idx / total_events) * period_minutes
    # Add small jitter so times don't land on round numbers
    elapsed += random.uniform(0, (period_minutes / total_events) * 0.9)
    elapsed  = min(elapsed, period_minutes - 0.05)
    mins = int(elapsed)
    secs = int((elapsed - mins) * 60)
    return f"{mins:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# Period simulation
# ---------------------------------------------------------------------------

def _simulate_period(
    home: dict,
    away: dict,
    period: int | str,
    sudden_death: bool = False,
) -> list[dict]:
    """
    Simulate one period and return a list of event dicts.
    If sudden_death=True, stops immediately after the first goal.
    """
    is_ot         = period == "OT"
    n_events      = OT_EVENTS if is_ot else EVENTS_PER_PERIOD
    period_mins   = 5 if is_ot else 20
    events: list  = []
    pp_state      = None   # {"attacker": team, "defender": team, "events_left": int}

    for idx in range(n_events):
        time_str = _format_time(period, idx, n_events, period_mins)

        # ── Determine attacker / defender ─────────────────────────────────
        if pp_state and pp_state["events_left"] > 0:
            attacker = pp_state["attacker"]
            defender = pp_state["defender"]
            is_pp    = True
            pp_state["events_left"] -= 1
            if pp_state["events_left"] <= 0:
                pp_state = None
        else:
            pp_state = None
            is_pp    = False
            home_prob = 0.50 + HOME_ADVANTAGE
            if random.random() < home_prob:
                attacker, defender = home, away
            else:
                attacker, defender = away, home

        # ── Pick matchup ──────────────────────────────────────────────────
        attack_line  = _pick_line(attacker["lines"])
        def_pairing  = _pick_pairing(defender["pairings"])
        def_goalie   = defender["goalies"][0] if defender["goalies"] else None

        attack_score  = _line_attack_score(attack_line)
        defence_score = _pairing_defence_score(def_pairing)
        goalie_score  = _goalie_score(def_goalie)

        # ── Fatigue (period 3 and OT only) ────────────────────────────────
        fatigue = 1.0
        if period in (3, "OT"):
            avg_stamina = _team_avg_stamina(attacker)
            fatigue     = FATIGUE_BASE + (avg_stamina - 10) * FATIGUE_STAMINA
            fatigue     = max(0.85, min(1.0, fatigue))

        # ── Shot attempt ──────────────────────────────────────────────────
        shot_prob = SHOT_BASE_PROB + (attack_score - defence_score) * SHOT_DIFF_FACTOR
        if is_pp:
            shot_prob += PP_SHOT_BONUS
        shot_prob = max(0.20, min(0.82, shot_prob)) * fatigue

        if random.random() < shot_prob:
            goal_prob = GOAL_BASE_RATE + (attack_score - goalie_score) * GOAL_DIFF_FACTOR
            if is_pp:
                goal_prob += PP_GOAL_BONUS
            goal_prob = max(0.03, min(0.24, goal_prob))

            if random.random() < goal_prob:
                scorer, assist1, assist2 = _pick_scorer(attack_line)
                goal_type = "OTG" if is_ot else ("PPG" if is_pp else None)
                events.append({
                    "type":      "goal",
                    "period":    period,
                    "time":      time_str,
                    "team":      attacker["name"],
                    "scorer":    scorer["name"]  if scorer  else "Unknown",
                    "assist1":   assist1["name"] if assist1 else None,
                    "assist2":   assist2["name"] if assist2 else None,
                    "goal_type": goal_type,
                })
                if is_pp:
                    pp_state = None     # PP ends on goal
                if sudden_death:
                    return events       # stop immediately

        # ── Penalty (even strength only) ──────────────────────────────────
        if not is_pp and random.random() < PENALTY_PROB:
            # Defender penalised 65% of the time (hooking, tripping attacker)
            if random.random() < 0.65:
                penalised, pp_team = defender, attacker
            else:
                penalised, pp_team = attacker, defender

            penalised_player = _pick_random_skater(penalised)
            events.append({
                "type":       "penalty",
                "period":     period,
                "time":       time_str,
                "team":       penalised["name"],
                "player":     penalised_player["name"] if penalised_player else "Unknown",
                "infraction": random.choice(INFRACTIONS),
                "minutes":    2,
            })
            pp_state = {"attacker": pp_team, "defender": penalised, "events_left": PP_EVENTS}

    return events


# ---------------------------------------------------------------------------
# Shootout
# ---------------------------------------------------------------------------

def _simulate_shootout(home: dict, away: dict) -> str:
    """
    Simple shootout — compare best forward shooting vs opposing goalie.
    Returns name of winning team.
    """
    def best_shooter(team: dict) -> float:
        shooters = [
            p for line in team["lines"]
            for slot in ("lw", "c", "rw")
            if (p := line.get(slot))
        ]
        if not shooters:
            return 10.0
        return max(p.get("shooting", 10) for p in shooters)

    home_shoot  = best_shooter(home)
    away_shoot  = best_shooter(away)
    home_goalie = _goalie_score(home["goalies"][0] if home["goalies"] else None)
    away_goalie = _goalie_score(away["goalies"][0] if away["goalies"] else None)

    # Home team scores minus away goalie; away team scores minus home goalie
    home_edge = (home_shoot - away_goalie) - (away_shoot - home_goalie)
    home_win_prob = max(0.25, min(0.75, 0.50 + home_edge * 0.025))

    return home["name"] if random.random() < home_win_prob else away["name"]


# ---------------------------------------------------------------------------
# Full game
# ---------------------------------------------------------------------------

def simulate_game(home: dict, away: dict) -> dict:
    """
    Simulate a complete game between home and away teams.

    Returns:
        home_team   str
        away_team   str
        home_score  int
        away_score  int
        result_type str  — 'REG', 'OT', or 'SO'
        events      list of event dicts in chronological order
    """
    home_score = 0
    away_score = 0
    all_events: list = []

    # ── Regulation ────────────────────────────────────────────────────────
    for period in (1, 2, 3):
        period_events = _simulate_period(home, away, period)
        for ev in period_events:
            if ev["type"] == "goal":
                if ev["team"] == home["name"]:
                    home_score += 1
                else:
                    away_score += 1
        all_events.extend(period_events)

    result_type = "REG"

    # ── Overtime (sudden death) ────────────────────────────────────────────
    if home_score == away_score:
        ot_events = _simulate_period(home, away, "OT", sudden_death=True)
        for ev in ot_events:
            if ev["type"] == "goal":
                if ev["team"] == home["name"]:
                    home_score += 1
                else:
                    away_score += 1
        all_events.extend(ot_events)

        if home_score != away_score:
            result_type = "OT"
        else:
            # ── Shootout ──────────────────────────────────────────────────
            winner = _simulate_shootout(home, away)
            if winner == home["name"]:
                home_score += 1
            else:
                away_score += 1
            result_type = "SO"
            all_events.append({
                "type": "shootout", "period": "SO",
                "time": "--", "team": winner,
                "scorer": None, "assist1": None, "assist2": None,
                "goal_type": "SO",
            })

    return {
        "home_team":   home["name"],
        "away_team":   away["name"],
        "home_score":  home_score,
        "away_score":  away_score,
        "result_type": result_type,
        "events":      all_events,
    }
