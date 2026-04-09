"""
update_eihl_playoffs.py
=======================
Run this AFTER the EIHL scraper has picked up the semi-final and/or final
game IDs from the EIHL website.  It will:

  1. Show all scraped EIHL League playoff games (phase='playoff').
  2. Identify which placeholder IDs (80000021 / 80000022 / 80000031) can be
     replaced with real game IDs.
  3. Update EIHL_PLAYOFFS_BRACKET in web/config.py.
  4. Remove the replaced placeholder rows from siha.db.

Safe to run multiple times — it only replaces placeholders that still exist
in the bracket config and have a matching real game in the DB.

Usage:
    python update_eihl_playoffs.py [--dry-run]
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT  = Path(__file__).parent
DB_PATH    = REPO_ROOT / "siha.db"
CONFIG_PATH = REPO_ROOT / "web" / "config.py"

# Placeholder game IDs (synthetic) that need replacing
PLACEHOLDER_IDS = {"80000021", "80000022", "80000031"}

# QF game IDs that are already real (don't replace these)
QF_GAME_IDS = {"5047", "5048", "5049", "5050", "5051", "5052", "5053", "5054"}

# Expected dates for each round (YYYY-MM-DD prefix)
SF_DATE_PREFIX    = "2026-04-18"
FINAL_DATE_PREFIX = "2026-04-19"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_playoff_fixtures(conn):
    """Return all EIHL League playoff fixtures (real game IDs only)."""
    rows = conn.execute(
        """
        SELECT game_id, date, home_team, away_team, home_score, away_score, status
        FROM eihl_fixtures
        WHERE competition = 'League'
          AND phase = 'playoff'
          AND game_id NOT IN ('80000021','80000022','80000031')
        ORDER BY COALESCE(date, 'z'), game_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def remove_placeholders(conn, ids_to_remove):
    for gid in ids_to_remove:
        conn.execute("DELETE FROM eihl_fixtures WHERE game_id = ?", (gid,))
    conn.commit()


# ---------------------------------------------------------------------------
# Config patch helpers
# ---------------------------------------------------------------------------

def read_config():
    return CONFIG_PATH.read_text(encoding="utf-8")


def write_config(text):
    CONFIG_PATH.write_text(text, encoding="utf-8")


def replace_id_in_config(config_text, old_id, new_id):
    """Replace a single placeholder game ID string in EIHL_PLAYOFFS_BRACKET."""
    # Match the ID as a quoted string, e.g. "80000021" or '80000021'
    pattern = rf'(["\']){re.escape(old_id)}(["\'])'
    replacement = rf'\g<1>{new_id}\g<2>'
    new_text, count = re.subn(pattern, replacement, config_text)
    return new_text, count


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Replace EIHL playoff placeholder IDs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing anything")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # --- 1. Show all scraped playoff fixtures ---
    fixtures = get_playoff_fixtures(conn)
    print("=== Scraped EIHL League playoff fixtures ===")
    if not fixtures:
        print("  None found yet — run the EIHL scraper first.")
        conn.close()
        return

    qf_fixtures = [f for f in fixtures if f["game_id"] in QF_GAME_IDS]
    sf_fixtures  = [f for f in fixtures if f["game_id"] not in QF_GAME_IDS
                    and (f["date"] or "").startswith(SF_DATE_PREFIX)]
    fin_fixtures = [f for f in fixtures if f["game_id"] not in QF_GAME_IDS
                    and (f["date"] or "").startswith(FINAL_DATE_PREFIX)]
    other        = [f for f in fixtures if f["game_id"] not in QF_GAME_IDS
                    and f not in sf_fixtures and f not in fin_fixtures]

    print(f"\nQF games ({len(qf_fixtures)}):")
    for f in qf_fixtures:
        score = f"{f['home_score']}-{f['away_score']}" if f["status"] != "scheduled" else "vs"
        print(f"  {f['game_id']:>10}  {f['home_team']} {score} {f['away_team']}  [{f['date']}]")

    print(f"\nSemi-final games on {SF_DATE_PREFIX} ({len(sf_fixtures)}):")
    for f in sf_fixtures:
        score = f"{f['home_score']}-{f['away_score']}" if f["status"] != "scheduled" else "vs"
        print(f"  {f['game_id']:>10}  {f['home_team']} {score} {f['away_team']}  [{f['date']}]")

    print(f"\nFinal game on {FINAL_DATE_PREFIX} ({len(fin_fixtures)}):")
    for f in fin_fixtures:
        score = f"{f['home_score']}-{f['away_score']}" if f["status"] != "scheduled" else "vs"
        print(f"  {f['game_id']:>10}  {f['home_team']} {score} {f['away_team']}  [{f['date']}]")

    if other:
        print(f"\nOther playoff fixtures (unexpected date):")
        for f in other:
            print(f"  {f['game_id']:>10}  {f['home_team']} vs {f['away_team']}  [{f['date']}]")

    # --- 2. Determine replacements ---
    # Placeholders: 80000021 = SF1, 80000022 = SF2, 80000031 = Final
    replacements = []  # list of (old_placeholder_id, new_real_id)

    if len(sf_fixtures) >= 1:
        replacements.append(("80000021", sf_fixtures[0]["game_id"]))
    if len(sf_fixtures) >= 2:
        replacements.append(("80000022", sf_fixtures[1]["game_id"]))
    if len(fin_fixtures) >= 1:
        replacements.append(("80000031", fin_fixtures[0]["game_id"]))

    if not replacements:
        print("\nNo new game IDs to replace yet — nothing to do.")
        conn.close()
        return

    print("\n=== Proposed changes to web/config.py (EIHL_PLAYOFFS_BRACKET) ===")
    for old_id, new_id in replacements:
        label = {"80000021": "SF1", "80000022": "SF2", "80000031": "Final"}.get(old_id, old_id)
        print(f"  {label}: replace placeholder '{old_id}' → '{new_id}'")

    print("\n=== Placeholder DB rows to delete ===")
    for old_id, _ in replacements:
        print(f"  DELETE FROM eihl_fixtures WHERE game_id = '{old_id}'")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        conn.close()
        return

    # --- 3. Confirm ---
    answer = input("\nApply these changes? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        conn.close()
        return

    # --- 4. Patch web/config.py ---
    config_text = read_config()
    for old_id, new_id in replacements:
        config_text, count = replace_id_in_config(config_text, old_id, new_id)
        if count == 0:
            print(f"WARNING: '{old_id}' not found in config — already replaced?")
        else:
            print(f"  Replaced '{old_id}' → '{new_id}' in web/config.py ({count} occurrence)")

    write_config(config_text)

    # --- 5. Remove placeholder DB rows ---
    ids_to_remove = [old_id for old_id, _ in replacements]
    remove_placeholders(conn, ids_to_remove)
    print(f"  Removed {len(ids_to_remove)} placeholder row(s) from siha.db")

    conn.close()

    print()
    print("Done. Next steps:")
    print("  1. Review the change in web/config.py (check EIHL_PLAYOFFS_BRACKET)")
    print("  2. Run: git add siha.db web/config.py && git commit -m 'chore: update EIHL playoff bracket with real SF/Final game IDs' && git push")


if __name__ == "__main__":
    main()
