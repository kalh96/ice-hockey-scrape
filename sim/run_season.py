"""
CLI entry point for Phase 3 — full season simulation.

Usage:
    python -m sim.run_season
    python -m sim.run_season --teams 10 --playoffs 4 --seed 42
    python -m sim.run_season --teams 8  --playoffs 8 --name "Highland League"
"""

import argparse
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sim.season import Season


# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

WIDTH = 70


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _bar(char: str = "─", w: int = WIDTH) -> str:
    return char * w


def _centre(text: str, w: int = WIDTH) -> str:
    return text.center(w)


def _progress(current: int, total: int) -> None:
    pct   = current / total
    filled = int(pct * 30)
    bar   = "█" * filled + "░" * (30 - filled)
    print(f"\r  [{bar}] {current}/{total}", end="", flush=True)


def _result_line(result: dict) -> str:
    rt     = result["result_type"]
    suffix = f" ({rt})" if rt != "REG" else ""
    return (
        f"  {result['home_team']:<24} "
        f"{result['home_score']}–{result['away_score']}"
        f"  {result['away_team']}{suffix}"
    )


# ---------------------------------------------------------------------------
# Print sections
# ---------------------------------------------------------------------------

def print_standings(season: Season) -> None:
    rows      = season.get_standings()
    n_qualify = season.n_playoff_teams

    print(f"\n{'═' * WIDTH}")
    print(_centre("REGULAR SEASON — FINAL STANDINGS"))
    print(f"{'═' * WIDTH}")
    print(
        f"  {'#':>2}  {'Team':<24}  "
        f"{'GP':>3}  {'W':>3}  {'OTW':>3}  {'L':>3}  {'OTL':>3}  "
        f"{'GF':>4}  {'GA':>4}  {'GD':>4}  {'PTS':>4}"
    )
    print(f"  {_bar('─', WIDTH - 2)}")

    for row in rows:
        gd      = row["gf"] - row["ga"]
        gd_str  = f"+{gd}" if gd > 0 else str(gd)
        marker  = "✓" if row["pos"] <= n_qualify else " "
        print(
            f"  {row['pos']:>2}  {row['team']:<24}  "
            f"{row['gp']:>3}  {row['w']:>3}  {row['otw']:>3}  "
            f"{row['l']:>3}  {row['otl']:>3}  "
            f"{row['gf']:>4}  {row['ga']:>4}  {gd_str:>4}  "
            f"{row['pts']:>4}  {marker}"
        )
        if row["pos"] == n_qualify:
            print(f"  {'· ' * (WIDTH // 2 - 1)}")

    games     = len(season.results)
    total_g   = season.total_goals()
    ot_games  = season.games_to_ot()
    print(f"\n  {games} games played · {total_g} goals · {ot_games} went to OT/SO")


def print_top_scorers(season: Season, n: int = 15) -> None:
    scorers = season.get_top_scorers(n)

    print(f"\n{'═' * WIDTH}")
    print(_centre(f"TOP SCORERS — REGULAR SEASON (TOP {n})"))
    print(f"{'═' * WIDTH}")
    print(
        f"  {'#':>2}  {'Player':<24}  {'Team':<22}  "
        f"{'GP':>3}  {'G':>3}  {'A':>3}  {'PTS':>4}"
    )
    print(f"  {_bar('─', WIDTH - 2)}")

    for i, p in enumerate(scorers, 1):
        print(
            f"  {i:>2}  {p['name']:<24}  {p['team']:<22}  "
            f"{p['gp']:>3}  {p['g']:>3}  {p['a']:>3}  {p['pts']:>4}"
        )


def print_playoffs(season: Season) -> None:
    if not season.playoff_results:
        return

    print(f"\n{'═' * WIDTH}")
    print(_centre("PLAYOFFS"))
    print(f"{'═' * WIDTH}")

    current_round = None
    round_order   = ["QF:", "Semi-Final", "Final"]

    def _round_label(label: str) -> str:
        if label.startswith("QF:"):
            return "QUARTER-FINALS"
        if "Semi" in label:
            return "SEMI-FINALS"
        if label == "Final":
            return "FINAL"
        return label.upper()

    printed_headers: set = set()

    for label, result in season.playoff_results:
        header = _round_label(label)
        if header not in printed_headers:
            print(f"\n  {_bar('─', 30)}  {header}  {_bar('─', WIDTH - 36 - len(header))}"[:WIDTH])
            printed_headers.add(header)
        print(_result_line(result))

    if season.champion:
        print(f"\n{'═' * WIDTH}")
        print(_centre(f"🏆  CHAMPIONS:  {season.champion}  🏆"))
        print(f"{'═' * WIDTH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a full ice hockey season.")
    parser.add_argument("--teams",    type=int, default=8,                    help="Number of teams (default 8)")
    parser.add_argument("--playoffs", type=int, default=4,                    help="Teams that qualify for playoffs (4 or 8)")
    parser.add_argument("--name",     type=str, default="Sim Hockey League",  help="League name")
    parser.add_argument("--season",   type=str, default="2026-27",            help="Season label")
    parser.add_argument("--seed",     type=int, default=None,                 help="Random seed")
    parser.add_argument("--scorers",  type=int, default=15,                   help="Number of top scorers to show")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    season = Season(
        n_teams=args.teams,
        name=args.name,
        season_label=args.season,
        n_playoff_teams=args.playoffs,
    )

    print(f"\n{'═' * WIDTH}")
    print(_centre(f"{args.name.upper()}  —  {args.season}"))
    print(f"{'═' * WIDTH}")

    n_fixtures = args.teams * (args.teams - 1)
    print(f"\n  {args.teams} teams · {n_fixtures} regular-season games")
    print(f"  Top {args.playoffs} qualify for playoffs\n")

    # Scheduling
    season.schedule()

    # Simulate regular season with live progress bar
    print("  Simulating regular season...")
    season.simulate_regular_season(progress_cb=_progress)
    print()   # newline after progress bar

    # Print standings
    print_standings(season)

    # Print top scorers
    print_top_scorers(season, n=args.scorers)

    # Playoffs
    print(f"\n  Simulating playoffs...")
    season.run_playoffs()
    print_playoffs(season)

    # Persist to DB
    league_id = season.save_to_db()
    print(f"\n  Saved to sim.db as league #{league_id}")
    print()


if __name__ == "__main__":
    main()
