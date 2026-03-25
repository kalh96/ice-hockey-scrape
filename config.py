BASE_URL = "https://www.siha-uk.co.uk"
FIXTURES_URL = f"{BASE_URL}/fixtures-25-26/"
EVENT_URL = f"{BASE_URL}/event/{{}}/"

LEAGUE_TABLE_URL = f"{BASE_URL}/snl-league-table-25-26/"

STATS_URLS = {
    "SNL": {
        "skaters":    f"{BASE_URL}/list/scottish-cup-top-points-scorers-24-25-2-2-2/",
        "netminders": f"{BASE_URL}/list/snl-top-netminder-sv-2-3-3-2/",
        "teams":      f"{BASE_URL}/table/scottish-national-league-snl-24-25-2-2/",
        "standings":  LEAGUE_TABLE_URL,
    },
    "Scottish Cup": {
        "skaters":    f"{BASE_URL}/list/scottish-cup-top-points-scorers-24-25-3/",
        "netminders": f"{BASE_URL}/list/snl-top-netminder-sv-2-3-2-2/",
    },
}

# Canonical team name overrides — applied whenever a team is upserted.
# Add entries here if the SIHA website returns an incorrect or abbreviated name.
TEAM_NAME_OVERRIDES = {
    "paisleypirates": "Paisley Pirates",
}

DB_PATH = "siha.db"
REQUEST_DELAY = 1.5   # seconds between requests
REQUEST_TIMEOUT = 20  # seconds per request
MAX_RETRIES = 3
