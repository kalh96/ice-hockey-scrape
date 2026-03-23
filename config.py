BASE_URL = "https://www.siha-uk.co.uk"
FIXTURES_URL = f"{BASE_URL}/fixtures-25-26/"
EVENT_URL = f"{BASE_URL}/event/{{}}/"

STATS_URLS = {
    "SNL": {
        "skaters":    f"{BASE_URL}/list/scottish-cup-top-points-scorers-24-25-2-2-2/",
        "netminders": f"{BASE_URL}/list/snl-top-netminder-sv-2-3-3-2/",
        "teams":      f"{BASE_URL}/table/scottish-national-league-snl-24-25-2-2/",
    },
    "Scottish Cup": {
        "skaters":    f"{BASE_URL}/list/scottish-cup-top-points-scorers-24-25-3/",
        "netminders": f"{BASE_URL}/list/snl-top-netminder-sv-2-3-2-2/",
    },
}

DB_PATH = "siha.db"
REQUEST_DELAY = 1.5   # seconds between requests
REQUEST_TIMEOUT = 20  # seconds per request
MAX_RETRIES = 3
