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
