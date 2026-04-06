"""Web app configuration."""

import os
from pathlib import Path

# Repo root is one level up from this file (web/)
_REPO_ROOT = Path(__file__).parent.parent

# Allow override via environment variable (useful for Render or local dev)
DB_PATH = os.environ.get("DB_PATH", str(_REPO_ROOT / "siha.db"))

# Directory containing markdown article files
ARTICLES_DIR = Path(__file__).parent / "articles"

# Current season — update this each August when the new season starts
CURRENT_SEASON = "2025-26"

# All seasons available — add the new season here each August
SEASONS = ["2025-26"]

# Competitions tracked
COMPETITIONS = ["SNL", "SNL Play-offs", "Scottish Cup"]

# Team display configuration
# Maps the DB team name (as stored from SIHA) to display info.
# full  = full team name shown in standings and team pages
# short = nickname only, shown in fixtures and stats tables
# slug  = URL-safe identifier used in /teams/<slug>/
# logo  = filename in web/static/img/teams/
TEAM_DISPLAY = {
    "Caps": {
        "full":    "Edinburgh Capitals",
        "short":   "Capitals",
        "slug":    "edinburgh-capitals",
        "logo":    "edinburgh-capitals.png",
        "website": "https://www.edcapitals.com",
    },
    "Rockets": {
        "full":    "Dundee Rockets",
        "short":   "Rockets",
        "slug":    "dundee-rockets",
        "logo":    "dundee-rockets.png",
        "website": "https://www.facebook.com/p/Dundee-Rockets-61561126066202/",
    },
    "Warriors": {
        "full":    "Whitley Bay Warriors",
        "short":   "Warriors",
        "slug":    "whitley-bay-warriors",
        "logo":    "whitley-bay-warriors.png",
        "website": "https://whitleywarriors.net",
    },
    "Paisley Pirates": {
        "full":    "Paisley Pirates",
        "short":   "Pirates",
        "slug":    "paisley-pirates",
        "logo":    "paisley-pirates.png",
        "website": "https://www.paisleypirates.co.uk",
    },
    "Kestrels": {
        "full":    "Kirkcaldy Kestrels",
        "short":   "Kestrels",
        "slug":    "kirkcaldy-kestrels",
        "logo":    "kirkcaldy-kestrels.png",
        "website": "https://kihc.org.uk/kirkcaldy-kestrels/",
    },
    "Lynx": {
        "full":    "Aberdeen Lynx",
        "short":   "Lynx",
        "slug":    "aberdeen-lynx",
        "logo":    "aberdeen-lynx.png",
        "website": "https://aberdeenlynx.com",
    },
    "Sharks": {
        "full":    "Solway Sharks",
        "short":   "Sharks",
        "slug":    "solway-sharks",
        "logo":    "solway-sharks.png",
        "website": "https://siha-uk.co.uk/team/solway-sharks-snl/",
    },
    "Wild": {
        "full":    "North Ayrshire Wild",
        "short":   "Wild",
        "slug":    "north-ayrshire-wild",
        "logo":    "north-ayrshire-wild.png",
        "website": "https://siha-uk.co.uk/team/north-ayrshire-wild/",
    },
    "Kilmarnock": {
        "full":    "Kilmarnock Thunder",
        "short":   "Thunder",
        "slug":    "kilmarnock-thunder",
        "logo":    "kilmarnock-thunder.png",
        "website": "https://www.facebook.com/p/The-Waterwise-Utilities-Kilmarnock-Thunder-100057359233356/",
    },
}

# Reverse lookup: URL slug → DB team name
TEAM_BY_SLUG = {v["slug"]: k for k, v in TEAM_DISPLAY.items()}

# Bump this string whenever you push CSS/JS changes to force Cloudflare to
# fetch the new file instead of serving a stale cached copy.
STATIC_VERSION = "20260406-6"

# Scottish Cup 2025-26 bracket structure.
# Each round lists matchups; each matchup is a list of event IDs (leg 1, leg 2).
# The Final has only one leg.
# SNL Play-offs 2025-26 bracket structure.
# QFs are two-legged (home + away); SFs and Final are one-legged.
# Seeding: 1 Caps, 2 Rockets, 3 Warriors, 4 Pirates, 5 Kestrels, 6 Lynx, 7 Sharks, 8 Wild
# Bracket order: 1v8 (top), 4v5, 3v6, 2v7 (bottom); SF1 = winner(1v8) v winner(4v5)
PLAYOFFS_BRACKET = [
    {
        "name": "Quarter-Finals",
        "matchups": [
            [1202457843, 1354946084],  # 1 Caps     vs 8 Wild      → SF1
            [1933183784, 1499847801],  # 4 Pirates  vs 5 Kestrels  → SF1
            [1988375590, 2136022216],  # 3 Warriors vs 6 Lynx      → SF2
            [1960190726, 1595441837],  # 2 Rockets  vs 7 Sharks    → SF2
        ],
    },
    {
        "name": "Semi-Finals",
        "matchups": [
            [90000021],  # SF1: winner(1v8) vs winner(4v5)
            [90000022],  # SF2: winner(3v6) vs winner(2v7)
        ],
    },
    {
        "name": "Final",
        "matchups": [
            [90000031],
        ],
    },
]

CUP_BRACKET = [
    {
        "name": "Quarter-Finals",
        "matchups": [
            [17419, 17437],            # Wild vs Caps        → feeds SF1
            [17442, 17471],            # Kestrels vs Rockets → feeds SF1
            [17429, 17448],            # Kilmarnock vs Lynx  → feeds SF2
            [1932643317, 1221019340],  # Warriors vs Pirates → feeds SF2
        ],
    },
    {
        "name": "Semi-Finals",
        "matchups": [
            [17499, 1644001149],       # Rockets vs Caps
            [19240, 1149401995],       # Warriors vs Lynx
        ],
    },
    {
        "name": "Final",
        "matchups": [
            [90000001],                # Caps vs Warriors
        ],
    },
]
