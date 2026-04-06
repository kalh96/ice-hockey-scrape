"""
Retroactive backtest of the win-probability model.

For each test game the model is given only data from games played
*before* that date, so no future information leaks in.

Usage:
    python backtest.py            # last 5 SNL games per team
    python backtest.py --n 10     # last 10 SNL games per team
"""

import argparse
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import DB_PATH, CURRENT_SEASON

NEUTRAL   = 0.5
HOME_ADV  = 0.05


# ---------------------------------------------------------------------------
# Retroactive data helpers
# ---------------------------------------------------------------------------

def _prior_snl_games(conn, db_name, before_date, before_eid, season):
    """All completed SNL games for a team strictly before the test game."""
    return conn.execute(
        """
        SELECT f.home_score, f.away_score,
               ht.name AS home_team, at.name AS away_team
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        JOIN competitions c ON c.id = f.competition_id
        WHERE f.status = 'final' AND f.season = ? AND c.name = 'SNL'
          AND (ht.name = ? OR at.name = ?)
          AND f.event_id != ?
          AND (f.date IS NOT NULL AND f.date < ?)
        """,
        (season, db_name, db_name, before_eid, before_date),
    ).fetchall()


def _prior_all_games(conn, db_name, before_date, before_eid, season, limit=5):
    """Last `limit` completed games (all competitions) before the test game."""
    return conn.execute(
        """
        SELECT f.home_score, f.away_score,
               ht.name AS home_team, at.name AS away_team
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        WHERE f.status = 'final' AND f.season = ?
          AND (ht.name = ? OR at.name = ?)
          AND f.event_id != ?
          AND (f.date IS NOT NULL AND f.date < ?)
        ORDER BY f.date DESC, f.event_id DESC
        LIMIT ?
        """,
        (season, db_name, db_name, before_eid, before_date, limit),
    ).fetchall()


def _won(row, db_name):
    is_home = row["home_team"] == db_name
    hs, as_ = (row["home_score"] or 0), (row["away_score"] or 0)
    return hs > as_ if is_home else as_ > hs


def retroactive_strength(conn, db_name, before_date, before_eid, season):
    snl  = _prior_snl_games(conn, db_name, before_date, before_eid, season)
    form = _prior_all_games(conn, db_name, before_date, before_eid, season, limit=5)

    if not snl:
        return {"pts_pct": None, "form_pct": None, "goal_ratio": None, "gp": 0}

    gp   = len(snl)
    wins = sum(1 for r in snl if _won(r, db_name))
    gf   = sum((r["home_score"] if r["home_team"] == db_name else r["away_score"]) or 0 for r in snl)
    ga   = sum((r["away_score"] if r["home_team"] == db_name else r["home_score"]) or 0 for r in snl)

    pts_pct    = wins / gp
    goal_ratio = gf / (gf + ga) if (gf + ga) > 0 else None
    form_pct   = sum(1 for r in form if _won(r, db_name)) / len(form) if form else None

    return {"pts_pct": pts_pct, "form_pct": form_pct, "goal_ratio": goal_ratio, "gp": gp}


def retroactive_h2h(conn, home_db, away_db, before_date, before_eid, season):
    rows = conn.execute(
        """
        SELECT f.home_score, f.away_score,
               ht.name AS home_team, at.name AS away_team
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        WHERE f.status = 'final' AND f.season = ?
          AND (
            (ht.name = ? AND at.name = ?)
            OR  (ht.name = ? AND at.name = ?)
          )
          AND f.event_id != ?
          AND (f.date IS NOT NULL AND f.date < ?)
        """,
        (season, home_db, away_db, away_db, home_db, before_eid, before_date),
    ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Retroactive prediction
# ---------------------------------------------------------------------------

def predict(conn, home_db, away_db, before_date, event_id, season):
    home_s = retroactive_strength(conn, home_db, before_date, event_id, season)
    away_s = retroactive_strength(conn, away_db, before_date, event_id, season)

    h2h = retroactive_h2h(conn, home_db, away_db, before_date, event_id, season)
    if h2h:
        home_h2h_wins = sum(1 for r in h2h if _won(r, home_db))
        home_h2h = home_h2h_wins / len(h2h)
        away_h2h = 1.0 - home_h2h
    else:
        home_h2h = away_h2h = None

    def _val(v): return v if v is not None else NEUTRAL

    factors = [
        (_val(home_s["pts_pct"]),    _val(away_s["pts_pct"]),    0.35),
        (_val(home_s["form_pct"]),   _val(away_s["form_pct"]),   0.30),
        (_val(home_s["goal_ratio"]), _val(away_s["goal_ratio"]), 0.20),
    ]
    if home_h2h is not None:
        factors.append((home_h2h, away_h2h, 0.15))

    total_w  = sum(f[2] for f in factors)
    raw_home = sum(h * w for h, _, w in factors) / total_w + HOME_ADV
    raw_away = sum(a * w for _, a, w in factors) / total_w
    total    = raw_home + raw_away

    home_pct = round(raw_home / total * 100)
    return home_pct, 100 - home_pct, home_s["gp"], away_s["gp"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Backtest win-probability model.")
    parser.add_argument("--n",      type=int, default=5,             help="Last N games per team (default 5)")
    parser.add_argument("--season", default=CURRENT_SEASON,          help="Season (default current)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # All completed SNL games, newest first
    all_games = conn.execute(
        """
        SELECT f.event_id, f.date, f.home_score, f.away_score,
               ht.name AS home_team, at.name AS away_team
        FROM fixtures f
        JOIN teams ht ON ht.id = f.home_team_id
        JOIN teams at ON at.id = f.away_team_id
        JOIN competitions c ON c.id = f.competition_id
        WHERE f.status = 'final' AND f.season = ? AND c.name = 'SNL'
          AND f.date IS NOT NULL
        ORDER BY f.date DESC, f.event_id DESC
        """,
        (args.season,),
    ).fetchall()

    # Pick last N games per team (deduplicated)
    team_counts: dict[str, int] = {}
    seen: set[int] = set()
    test_games = []

    for r in all_games:
        eid = r["event_id"]
        if eid in seen:
            continue
        home, away = r["home_team"], r["away_team"]
        if team_counts.get(home, 0) < args.n or team_counts.get(away, 0) < args.n:
            test_games.append(dict(r))
            seen.add(eid)
            team_counts[home] = team_counts.get(home, 0) + 1
            team_counts[away] = team_counts.get(away, 0) + 1

    # Sort chronologically
    test_games.sort(key=lambda g: (g["date"], g["event_id"]))

    # Run model
    correct = 0
    confident_correct = confident_total = 0
    rows_out = []

    for g in test_games:
        home_pct, away_pct, home_gp, away_gp = predict(
            conn, g["home_team"], g["away_team"],
            g["date"], g["event_id"], args.season,
        )
        actual_home_win    = (g["home_score"] or 0) > (g["away_score"] or 0)
        predicted_home_win = home_pct > away_pct
        ok  = predicted_home_win == actual_home_win
        confident = abs(home_pct - away_pct) >= 15  # model has a clear opinion

        if ok:
            correct += 1
        if confident:
            confident_total += 1
            if ok:
                confident_correct += 1

        rows_out.append({
            **g,
            "home_pct":  home_pct,
            "away_pct":  away_pct,
            "home_gp":   home_gp,
            "away_gp":   away_gp,
            "correct":   ok,
            "confident": confident,
        })

    conn.close()

    # ---------------------------------------------------------------------------
    # Output
    # ---------------------------------------------------------------------------
    W = 90
    print(f"\n{'=' * W}")
    print(f"  WIN PROBABILITY BACKTEST  --  {args.season} SNL  (last {args.n} games per team)")
    print(f"{'=' * W}")
    hdr = f"  {'Date':<12} {'Home':<22} {'Score':<7} {'Away':<22} {'Pred (H/A)':<12} {'H-GP':>4}  {'A-GP':>4}  OK"
    print(hdr)
    print(f"  {'-' * (W - 2)}")

    for r in rows_out:
        date_str = r["date"][:10]
        score    = f"{r['home_score']}-{r['away_score']}"
        pred     = f"{r['home_pct']}%/{r['away_pct']}%"
        tick     = "Y" if r["correct"] else "N"
        flag     = " *" if not r["confident"] else ""
        print(
            f"  {date_str:<12} {r['home_team']:<22} {score:<7} {r['away_team']:<22}"
            f" {pred:<12} {r['home_gp']:>4}  {r['away_gp']:>4}  {tick}{flag}"
        )

    total = len(rows_out)
    pct   = round(correct / total * 100) if total else 0
    conf_pct = round(confident_correct / confident_total * 100) if confident_total else 0

    print(f"  {'-' * (W - 2)}")
    print(f"  Overall accuracy :  {correct}/{total}  ({pct}%)")
    if confident_total:
        print(f"  Confident calls  :  {confident_correct}/{confident_total}  ({conf_pct}%)  [margin >=15%]")
    print(f"  * = margin <15% (close call)\n  Home advantage applied: +{int(HOME_ADV*100)}%")
    print(f"{'=' * W}\n")


if __name__ == "__main__":
    main()
