"""Configuration for the WNIHL scraper."""

BASE_URL      = "https://websites.mygameday.app"
ASSOC_CLIENT  = "0-12995-0-0-0"   # &c= parameter for all URLs
CURRENT_SEASON = "2025-26"

# comp_info.cgi action pages
# a=FIXTURE → all fixtures + results (var matches embedded in HTML)
# a=LADDER  → standings HTML table
# a=STATS   → player stats HTML table
COMPETITIONS = {
    "Elite":  {"comp_id": "652426", "label": "WNIHL Elite"},
    "1 North": {"comp_id": "652430", "label": "WNIHL 1 North"},
    "1 South": {"comp_id": "652427", "label": "WNIHL 1 South"},
}

REQUEST_DELAY   = 2.0
REQUEST_TIMEOUT = 20
MAX_RETRIES     = 3

# ---------------------------------------------------------------------------
# Team name normalisation
# ---------------------------------------------------------------------------
# Source names include league/division suffixes (e.g. "Streatham Storm WNIHL/Elite").
# Map each raw source name to a clean display name.
# Rule: use the shortest meaningful base name; if the same base name appears in
# a lower league, append " 2" for the lower-league entry.

TEAM_NAME_MAP = {
    # WNIHL Elite
    "Bristol Huskies":              "Bristol Huskies",
    "Guildford Lightning":          "Guildford Lightning",
    "Queen Bees":                   "Queen Bees",
    "Solihull Vixens Elite":        "Solihull Vixens",
    "Streatham Storm WNIHL/Elite":  "Streatham Storm",
    "Whitley Bay Beacons":          "Whitley Bay Beacons",
    # WNIHL 1 North
    "Caledonia Steel Queens D1":    "Caledonia Steel Queens",
    "Kingston Diamonds WNIHL 1":    "Kingston Diamonds",
    "Nottingham Vipers WNIHL 1 North": "Nottingham Vipers",
    "Sheffield Shadows WNIHL 1":    "Sheffield Shadows",
    "Solway Sharks":                "Solway Sharks",
    "Widnes Wild Women WNIHL 1N":   "Widnes Wild Women",
    # WNIHL 1 South
    "Cambridge Kodiaks":            "Cambridge Kodiaks",
    "Chelmsford Cobras":            "Chelmsford Cobras",
    "Firebees":                     "Firebees",
    "Milton Keynes Falcons WNIHL1": "Milton Keynes Falcons",
    "Streatham Storm WNIHL1S":      "Streatham Storm 2",   # lower-league entry
    "Swindon Topcats - WNIHL":      "Swindon Topcats",
}

import re as _re
_SUFFIX_RE = _re.compile(
    r'\s*(?:WNIHL[\w/\s]*\w|[-\s]+WNIHL|\bD\d+\b|\bElite\b)\s*$',
    _re.IGNORECASE,
)

def clean_team_name(raw: str) -> str:
    """Return a clean display name for a raw source team name.

    Uses the explicit TEAM_NAME_MAP first, then falls back to a regex that
    strips known WNIHL league-suffix patterns.
    """
    if raw in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[raw]
    cleaned = _SUFFIX_RE.sub("", raw).strip()
    return cleaned or raw
