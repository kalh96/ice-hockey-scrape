"""
Player and team generation.

All players are fictional. Attribute values sit on a 1–20 scale defined in
config.ATTR_RANGES; a quality_bias shifts the whole team up or down.
"""

import random

from sim.config import ATTR_RANGES, POSITIONS, SKATER_ATTRS, GOALIE_ATTRS
from sim.names import FIRST_NAMES, LAST_NAMES, NICKNAMES, CITIES


# ---------------------------------------------------------------------------
# Attribute helpers
# ---------------------------------------------------------------------------

def _rand_attr(lo: int, hi: int, bias: int = 0) -> int:
    """
    Return an integer attribute in [lo+bias, hi+bias] clamped to [1, 20].
    Averaging two rolls gives a bell-shaped distribution peaked in the middle
    of the range, so extreme values are possible but uncommon.
    """
    lo = max(1, min(20, lo + bias))
    hi = max(1, min(20, hi + bias))
    if lo > hi:
        lo, hi = hi, lo
    return (random.randint(lo, hi) + random.randint(lo, hi)) // 2


def _generate_age() -> int:
    """Weighted age distribution realistic for a professional hockey league."""
    ages = list(range(18, 39))
    # Peak at 24-28, thin tails at either end
    weights = [
        2, 3, 4, 5, 7, 8, 8, 8, 8, 7,   # 18-27
        6, 5, 4, 3, 3, 2, 2, 1, 1, 1,   # 28-37
        1,                                 # 38
    ]
    return random.choices(ages, weights=weights, k=1)[0]


def _age_bias(age: int) -> int:
    """Young players are slightly weaker; prime-age players slightly stronger."""
    if age <= 20:
        return -2
    if age <= 22:
        return -1
    if 24 <= age <= 30:
        return 1
    if age >= 34:
        return -1
    return 0


# ---------------------------------------------------------------------------
# Player generation
# ---------------------------------------------------------------------------

def player_overall(player: dict) -> float:
    """
    Compute a position-appropriate overall rating (1–20 float).
    Used for sorting and display; not used directly in the match engine.
    """
    pos = player["position"]
    if pos == "G":
        return (
            player["positioning"]     * 0.40
            + player["reflexes"]      * 0.40
            + player["rebound_control"] * 0.20
        )
    # Position-weighted skater overall
    weights = {
        "LW": {"skating": 0.20, "shooting": 0.35, "passing": 0.15,
               "physicality": 0.10, "defence": 0.05, "stamina": 0.15},
        "RW": {"skating": 0.20, "shooting": 0.35, "passing": 0.15,
               "physicality": 0.10, "defence": 0.05, "stamina": 0.15},
        "C":  {"skating": 0.20, "shooting": 0.15, "passing": 0.30,
               "physicality": 0.08, "defence": 0.12, "stamina": 0.15},
        "LD": {"skating": 0.15, "shooting": 0.05, "passing": 0.10,
               "physicality": 0.25, "defence": 0.35, "stamina": 0.10},
        "RD": {"skating": 0.15, "shooting": 0.05, "passing": 0.10,
               "physicality": 0.25, "defence": 0.35, "stamina": 0.10},
    }
    w = weights.get(pos, {attr: 1/6 for attr in SKATER_ATTRS})
    return sum(player.get(attr, 10) * wt for attr, wt in w.items())


def generate_player(position: str, quality_bias: int = 0) -> dict:
    """
    Generate a single fictional player.

    quality_bias: integer shift applied to all attributes (-3 to +3).
    Positive = above-average team; negative = weaker team.
    """
    ranges = ATTR_RANGES[position]
    age    = _generate_age()
    ab     = _age_bias(age) + quality_bias

    player: dict = {
        "name":      f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        "position":  position,
        "age":       age,
        "potential": random.randint(max(1, 8 + quality_bias), 20),  # hidden ceiling
        "morale":    random.randint(9, 13),
    }

    if position == "G":
        for attr in GOALIE_ATTRS:
            player[attr] = _rand_attr(*ranges[attr], bias=ab)
    else:
        for attr in SKATER_ATTRS:
            player[attr] = _rand_attr(*ranges[attr], bias=ab)

    player["overall"] = round(player_overall(player), 1)
    return player


# ---------------------------------------------------------------------------
# Team generation
# ---------------------------------------------------------------------------

def _auto_lines(roster: list[dict]) -> tuple[list, list, list]:
    """
    Sort each position group by overall rating and assign to lines/pairings
    automatically — best players get the top line.
    """
    by_pos: dict[str, list] = {p: [] for p in POSITIONS}
    for pl in roster:
        by_pos[pl["position"]].append(pl)

    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: p["overall"], reverse=True)

    lws = by_pos["LW"]
    cs  = by_pos["C"]
    rws = by_pos["RW"]
    lds = by_pos["LD"]
    rds = by_pos["RD"]
    gs  = by_pos["G"]

    lines = [
        {"line": i + 1,
         "lw": lws[i] if i < len(lws) else None,
         "c":  cs[i]  if i < len(cs)  else None,
         "rw": rws[i] if i < len(rws) else None}
        for i in range(POSITIONS["LW"]["count"])
    ]
    pairings = [
        {"pairing": i + 1,
         "ld": lds[i] if i < len(lds) else None,
         "rd": rds[i] if i < len(rds) else None}
        for i in range(POSITIONS["LD"]["count"])
    ]
    return lines, pairings, gs


def generate_team(name: str | None = None, quality_bias: int = 0) -> dict:
    """
    Generate a full team: roster, lines, pairings, goalies.

    name: team name string; auto-generated from CITIES + NICKNAMES if omitted.
    quality_bias: -3 (weak) to +3 (strong).
    """
    if name is None:
        city     = random.choice(CITIES)
        nickname = random.choice(NICKNAMES)
        name     = f"{city} {nickname}"

    roster = [
        generate_player(pos, quality_bias)
        for pos, info in POSITIONS.items()
        for _ in range(info["count"])
    ]

    lines, pairings, goalies = _auto_lines(roster)

    return {
        "name":     name,
        "roster":   roster,
        "lines":    lines,
        "pairings": pairings,
        "goalies":  goalies,   # index 0 = starter
    }


def generate_league(n_teams: int = 8) -> list[dict]:
    """
    Generate n_teams with naturally spread quality.
    Teams are assigned a quality_bias drawn from a normal-ish distribution
    so the league has a realistic spread of strong and weak clubs.
    """
    used_names: set[str] = set()
    teams = []

    # Spread biases so roughly: 1–2 strong, 4–5 average, 1–2 weak
    biases = random.choices([-2, -1, 0, 0, 0, 1, 1, 2], k=n_teams)
    random.shuffle(biases)

    for bias in biases:
        while True:
            city     = random.choice(CITIES)
            nickname = random.choice(NICKNAMES)
            name     = f"{city} {nickname}"
            if name not in used_names:
                used_names.add(name)
                break
        teams.append(generate_team(name, quality_bias=bias))

    return teams
