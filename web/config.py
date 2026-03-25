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
COMPETITIONS = ["SNL", "Scottish Cup"]

# Team display configuration
# Maps the DB team name (as stored from SIHA) to display info.
# full  = full team name shown in standings and team pages
# short = nickname only, shown in fixtures and stats tables
# slug  = URL-safe identifier used in /teams/<slug>/
# logo  = filename in web/static/img/teams/
TEAM_DISPLAY = {
    "Caps": {
        "full":  "Edinburgh Capitals",
        "short": "Capitals",
        "slug":  "edinburgh-capitals",
        "logo":  "edinburgh-capitals.png",
    },
    "Rockets": {
        "full":  "Dundee Rockets",
        "short": "Rockets",
        "slug":  "dundee-rockets",
        "logo":  "dundee-rockets.png",
    },
    "Warriors": {
        "full":  "Whitley Bay Warriors",
        "short": "Warriors",
        "slug":  "whitley-bay-warriors",
        "logo":  "whitley-bay-warriors.png",
    },
    "Paisley Pirates": {
        "full":  "Paisley Pirates",
        "short": "Pirates",
        "slug":  "paisley-pirates",
        "logo":  "paisley-pirates.png",
    },
    "Kestrels": {
        "full":  "Kirkcaldy Kestrels",
        "short": "Kestrels",
        "slug":  "kirkcaldy-kestrels",
        "logo":  "kirkcaldy-kestrels.png",
    },
    "Lynx": {
        "full":  "Aberdeen Lynx",
        "short": "Lynx",
        "slug":  "aberdeen-lynx",
        "logo":  "aberdeen-lynx.png",
    },
    "Sharks": {
        "full":  "Solway Sharks",
        "short": "Sharks",
        "slug":  "solway-sharks",
        "logo":  "solway-sharks.png",
    },
    "Wild": {
        "full":  "North Ayrshire Wild",
        "short": "Wild",
        "slug":  "north-ayrshire-wild",
        "logo":  "north-ayrshire-wild.png",
    },
    "Kilmarnock": {
        "full":  "Kilmarnock Thunder",
        "short": "Thunder",
        "slug":  "kilmarnock-thunder",
        "logo":  "kilmarnock-thunder.png",
    },
}

# Reverse lookup: URL slug → DB team name
TEAM_BY_SLUG = {v["slug"]: k for k, v in TEAM_DISPLAY.items()}

# Bump this string whenever you push CSS/JS changes to force Cloudflare to
# fetch the new file instead of serving a stale cached copy.
STATIC_VERSION = "20260325-4"
