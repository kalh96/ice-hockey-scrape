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

# ---------------------------------------------------------------------------
# EIHL configuration
# ---------------------------------------------------------------------------

EIHL_CURRENT_SEASON = "2025-26"
EIHL_SEASONS        = ["2025-26"]
EIHL_COMPETITIONS   = ["League", "Cup"]

# Display names for EIHL competition tabs
EIHL_COMP_LABELS = {
    "League": "Elite Ice Hockey League",
    "Cup":    "Challenge Cup",
}

# Maps DB team name → display info for the 10 EIHL teams.
# Place logo PNGs in web/static/img/eihl/ matching the logo filename below.
EIHL_TEAM_DISPLAY = {
    "Belfast Giants":      {"full": "Belfast Giants",      "short": "Giants",   "slug": "belfast-giants",      "logo": "belfast-giants.png"},
    "Cardiff Devils":      {"full": "Cardiff Devils",      "short": "Devils",   "slug": "cardiff-devils",      "logo": "cardiff-devils.png"},
    "Coventry Blaze":      {"full": "Coventry Blaze",      "short": "Blaze",    "slug": "coventry-blaze",      "logo": "coventry-blaze.png"},
    "Dundee Stars":        {"full": "Dundee Stars",        "short": "Stars",    "slug": "dundee-stars",        "logo": "dundee-stars.png"},
    "Fife Flyers":         {"full": "Fife Flyers",         "short": "Flyers",   "slug": "fife-flyers",         "logo": "fife-flyers.png"},
    "Glasgow Clan":        {"full": "Glasgow Clan",        "short": "Clan",     "slug": "glasgow-clan",        "logo": "glasgow-clan.png"},
    "Guildford Flames":    {"full": "Guildford Flames",    "short": "Flames",   "slug": "guildford-flames",    "logo": "guildford-flames.png"},
    "Manchester Storm":    {"full": "Manchester Storm",    "short": "Storm",    "slug": "manchester-storm",    "logo": "manchester-storm.png"},
    "Nottingham Panthers": {"full": "Nottingham Panthers", "short": "Panthers", "slug": "nottingham-panthers", "logo": "nottingham-panthers.png"},
    "Sheffield Steelers":  {"full": "Sheffield Steelers",  "short": "Steelers", "slug": "sheffield-steelers",  "logo": "sheffield-steelers.png"},
}

# Reverse mapping: EIHL slug → DB team name
EIHL_SLUG_TO_TEAM = {info["slug"]: name for name, info in EIHL_TEAM_DISPLAY.items()}

# EIHL League Play-offs 2025-26 bracket
# QF: 4 two-legged matchups (Apr 11-12); SF: one-leg (Apr 18); Final: one-leg (Apr 19)
# SF/Final game_ids are synthetic placeholders — replaced once QF results are known.
EIHL_PLAYOFFS_BRACKET = [
    {
        "name": "Quarter-Finals",
        "matchups": [
            ["5050", "5054"],  # Belfast Giants vs Glasgow Clan
            ["5053", "5049"],  # Coventry Blaze vs Cardiff Devils
            ["5052", "5047"],  # Manchester Storm vs Nottingham Panthers
            ["5051", "5048"],  # Guildford Flames vs Sheffield Steelers
        ],
    },
    {
        "name": "Semi-Finals",
        "matchups": [
            ["80000021"],  # TBD vs TBD — Apr 18
            ["80000022"],  # TBD vs TBD — Apr 18
        ],
    },
    {
        "name": "Final",
        "matchups": [
            ["80000031"],  # TBD vs TBD — Apr 19
        ],
    },
]

# EIHL Challenge Cup 2025-26 bracket (knockout phase only — group stage shown separately)
# Groups: A = Sheffield, Coventry, Nottingham, Cardiff, Manchester, Guildford
#         B = Belfast, Glasgow, Dundee, Fife
# Elimination game (B2 vs A3): Glasgow 1-4 Nottingham → Nottingham advances
# SF1: Nottingham vs Sheffield — Nottingham wins 5-4 agg
# SF2: Coventry vs Belfast — Coventry wins 9-5 agg
# Final: Nottingham Panthers 3-2 OT Coventry Blaze → Nottingham Panthers win
EIHL_CUP_BRACKET = [
    {
        "name": "Elimination Game",
        "matchups": [
            ["5037"],  # Glasgow Clan 1-4 Nottingham Panthers
        ],
    },
    {
        "name": "Semi-Finals",
        "matchups": [
            ["5040", "5041"],  # Nottingham Panthers vs Sheffield Steelers
            ["5038", "5039"],  # Coventry Blaze vs Belfast Giants
        ],
    },
    {
        "name": "Final",
        "matchups": [
            ["5042"],  # Nottingham Panthers 3-2 OT Coventry Blaze
        ],
    },
]

# ---------------------------------------------------------------------------
# WNIHL configuration
# ---------------------------------------------------------------------------

WNIHL_CURRENT_SEASON = "2025-26"
WNIHL_SEASONS        = ["2025-26"]
WNIHL_COMPETITIONS   = ["Elite", "1 North", "1 South"]

WNIHL_COMP_LABELS = {
    "Elite":   "WNIHL Elite",
    "1 North": "WNIHL 1 North",
    "1 South": "WNIHL 1 South",
}

# Bump this string whenever you push CSS/JS changes to force Cloudflare to
# fetch the new file instead of serving a stale cached copy.
STATIC_VERSION = "20260409-2"

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
            [1989416961],              # Warriors vs Caps (Apr 11)
        ],
    },
]
