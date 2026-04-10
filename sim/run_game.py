"""
CLI entry point — Phase 1 & 2 smoke test.

Generates two fictional teams, prints their rosters, simulates one game,
and prints a formatted match report.

Usage:
    python -m sim.run_game
    python -m sim.run_game --seed 42        # reproducible output
    python -m sim.run_game --games 5        # simulate N games between same teams
"""

import argparse
import random
import sys

# Ensure box-drawing characters render correctly on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sim.generator import generate_team, player_overall
from sim.engine import simulate_game


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

WIDTH = 66


def _bar(char: str = "─", width: int = WIDTH) -> str:
    return char * width


def _centre(text: str, width: int = WIDTH) -> str:
    return text.center(width)


def _short(name: str) -> str:
    """'Kyle Morrison' → 'K. Morrison'"""
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {' '.join(parts[1:])}"
    return name


def _assists(ev: dict) -> str:
    a1 = _short(ev["assist1"]) if ev.get("assist1") else None
    a2 = _short(ev["assist2"]) if ev.get("assist2") else None
    if a1 and a2:
        return f"({a1}, {a2})"
    if a1:
        return f"({a1})"
    return "(unassisted)"


def print_roster(team: dict) -> None:
    print(f"\n  {team['name'].upper()}")
    print(f"  {_bar('─', WIDTH - 2)}")

    # Lines
    for line in team["lines"]:
        lw  = line.get("lw")
        c   = line.get("c")
        rw  = line.get("rw")
        names = "  ".join(
            f"{p['name']:<22} {p['position']} OVR {p['overall']:>4}"
            for p in [lw, c, rw] if p
        )
        print(f"  Line {line['line']}: {names}")

    print()
    for pair in team["pairings"]:
        ld = pair.get("ld")
        rd = pair.get("rd")
        names = "  ".join(
            f"{p['name']:<22} {p['position']} OVR {p['overall']:>4}"
            for p in [ld, rd] if p
        )
        print(f"  Pair {pair['pairing']}: {names}")

    print()
    for i, g in enumerate(team["goalies"]):
        label = "Starter" if i == 0 else "Backup "
        print(f"  {label}: {g['name']:<22} GK  OVR {g['overall']:>4}")

    print()


def print_report(result: dict) -> None:
    home = result["home_team"]
    away = result["away_team"]

    print("\n" + "═" * WIDTH)
    print(_centre(f"{home}  vs  {away}"))
    print("═" * WIDTH)

    current_period = None
    home_score = 0
    away_score = 0

    for ev in result["events"]:
        period = ev["period"]

        # Print period header when period changes
        if period != current_period:
            current_period = period
            label = f" PERIOD {period} " if isinstance(period, int) else f" {period} "
            dashes = (_bar() + label + _bar())[:WIDTH]
            half = (WIDTH - len(label)) // 2
            print(f"\n{'─' * half}{label}{'─' * (WIDTH - half - len(label))}")

        time_str = ev["time"]

        if ev["type"] == "goal":
            if ev["team"] == home:
                home_score += 1
            else:
                away_score += 1
            score_str = f"{home_score}–{away_score}"

            goal_label = {
                "PPG": "PPG! ",
                "SHG": "SHG! ",
                "OTG": "OTG! ",
                "SO":  " SO  ",
            }.get(ev.get("goal_type"), "GOAL ")

            scorer_str  = _short(ev["scorer"]) if ev.get("scorer") else "?"
            assist_str  = _assists(ev)
            team_abbr   = ev["team"][:14]

            print(
                f"  {time_str}  {goal_label}  "
                f"{team_abbr:<14}  "
                f"{scorer_str:<18} {assist_str:<26}  [{score_str}]"
            )

        elif ev["type"] == "penalty":
            player_str = _short(ev.get("player", "Unknown"))
            infraction  = ev.get("infraction", "")
            mins        = ev.get("minutes", 2)
            team_abbr   = ev["team"][:14]
            print(
                f"  {time_str}  PEN    "
                f"{team_abbr:<14}  "
                f"{player_str:<18} {infraction} ({mins} min)"
            )

        elif ev["type"] == "shootout":
            print(f"\n  Shootout won by {ev['team']}")

    # Final score
    rt = result["result_type"]
    suffix = f" ({rt})" if rt != "REG" else ""
    print("\n" + "═" * WIDTH)
    print(_centre(f"FINAL{suffix}"))
    print(_centre(f"{home}  {result['home_score']}  –  {result['away_score']}  {away}"))
    print("═" * WIDTH + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate an ice hockey game.")
    parser.add_argument("--seed",  type=int,  default=None, help="Random seed for reproducibility")
    parser.add_argument("--games", type=int,  default=1,    help="Number of games to simulate")
    parser.add_argument("--rosters", action="store_true",   help="Print team rosters before the match")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    home = generate_team()
    away = generate_team()

    if args.rosters:
        print("\n" + "═" * WIDTH)
        print(_centre("TEAM ROSTERS"))
        print("═" * WIDTH)
        print_roster(home)
        print_roster(away)

    for game_num in range(args.games):
        if args.games > 1:
            print(f"\n{'━' * WIDTH}")
            print(_centre(f"GAME {game_num + 1} OF {args.games}"))
        result = simulate_game(home, away)
        print_report(result)


if __name__ == "__main__":
    main()
