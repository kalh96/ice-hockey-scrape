"""Configuration for the EIHL scraper."""

BASE_URL = "https://www.eliteleague.co.uk"

# EIHL website season/competition IDs for 2025-26.
# These appear in standings and stats URLs (e.g. /standings/2025/43-elite-ice-hockey-league).
# id_season=43 → Elite Ice Hockey League 2025-26
# id_season=44 → Challenge Cup 2025-26
EIHL_LEAGUE_SEASON_ID = 43
EIHL_CUP_SEASON_ID    = 44

# Stage IDs for /stats/* URLs (?id_season=43&id_stage=1)
# id_stage=1 confirmed for League; Cup stage ID to be verified on first run.
EIHL_LEAGUE_STAGE_ID = 1
EIHL_CUP_STAGE_ID    = 2   # TODO: verify this is correct for Challenge Cup stats

CURRENT_SEASON = "2025-26"
EIHL_SEASONS   = ["2025-26"]

# Path to the shared SQLite database
DB_PATH = "siha.db"

REQUEST_DELAY   = 2.0   # seconds between requests
REQUEST_TIMEOUT = 20    # seconds per request
MAX_RETRIES     = 3

# Game URL slug abbreviations → canonical team name.
# Verified: NOT = Nottingham (/game/4979-not-car), GLA = Glasgow (/game/4982-gla-she)
TEAM_ABBREV = {
    "bel": "Belfast Giants",
    "car": "Cardiff Devils",
    "cov": "Coventry Blaze",
    "dun": "Dundee Stars",
    "fif": "Fife Flyers",
    "gla": "Glasgow Clan",
    "gui": "Guildford Flames",
    "man": "Manchester Storm",
    "not": "Nottingham Panthers",
    "she": "Sheffield Steelers",
}
