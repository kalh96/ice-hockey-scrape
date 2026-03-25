# SIHA Ice Hockey Scraper

Scrapes fixtures, results, player stats, and standings from the SIHA website into a local SQLite database. Covers the Scottish National League (SNL) and Scottish Cup for the 2025-26 season.

## Overview

The scraper runs a series of passes on each execution:

1. **Fixtures pass** — parses all fixtures from the scoreboard and matrix, upserting results and scheduled games
2. **Event detail pass** — for each newly completed fixture, fetches the event page to capture per-period scores and player stats
3. **Date backfill pass** — fills in any missing dates for completed fixtures
4. **Season stats pass** — scrapes cumulative skater, netminder, team special-teams, and standings tables
5. **Validation pass** — cross-checks computed standings (derived from fixture results) against the scraped league table and logs any discrepancies

All data is stored in `siha.db` (SQLite). Passes are idempotent — re-running is safe and will only update changed data.

## Setup

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
```

Dependencies:
- `requests` — HTTP fetching
- `beautifulsoup4` + `lxml` — HTML parsing

## Usage

### Full scrape (recommended)

```bash
python main.py
```

Runs all passes in sequence.

### Options

| Flag | Description |
|------|-------------|
| `--fixtures-only` | Only run the fixtures pass |
| `--stats-only` | Run fixtures + season stats passes (skip event detail scraping) |
| `--event ID` | Force-fetch a single event by ID (useful for debugging) |
| `--db PATH` | Path to the SQLite database file (default: `siha.db`) |
| `-v`, `--verbose` | Enable DEBUG-level logging |

### Examples

```bash
# Quick update of fixtures and standings only
python main.py --stats-only

# Debug a specific event
python main.py --event 17434 --verbose

# Use a different database file
python main.py --db ~/backups/siha_backup.db
```

## Database Schema

The database is created automatically on first run. All tables use `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE` semantics so re-runs are safe.

### `competitions`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| name | TEXT | `SNL` or `Scottish Cup` |

### `teams`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| slug | TEXT | URL slug (unique) |
| name | TEXT | Display name |

### `players`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| slug | TEXT | URL slug (unique) |
| name | TEXT | Display name |

### `fixtures`
| Column | Type | Description |
|--------|------|-------------|
| event_id | INTEGER PK | SIHA event ID |
| competition_id | INTEGER FK | |
| date | TEXT | ISO date (may be NULL until backfilled) |
| home_team_id / away_team_id | INTEGER FK | |
| home_score / away_score | INTEGER | NULL for scheduled fixtures |
| status | TEXT | `final` or `scheduled` |
| event_url | TEXT | Relative path to event page |
| scraped_at | TEXT | ISO timestamp of last scrape |

### `event_period_scores`
Per-team period breakdown for each completed event.

| Column | Type | Description |
|--------|------|-------------|
| event_id | INTEGER FK | |
| team_id | INTEGER FK | |
| period_1/2/3 | INTEGER | Goals per period |
| ppg | INTEGER | Power-play goals |
| ppo | INTEGER | Power-play opportunities |
| outcome | TEXT | `win` / `loss` |

### `event_player_stats`
Individual player stats per event.

| Column | Type | Description |
|--------|------|-------------|
| event_id / team_id / player_id | INTEGER FK | Composite unique key |
| jersey_number | TEXT | |
| position | TEXT | |
| goals / assists / pim | INTEGER | Skater stats |
| shots_against / saves / goals_against | INTEGER | Netminder stats (NULL for skaters) |
| toi | TEXT | Time on ice |

### `season_skater_stats`
Cumulative season stats per skater per competition.

| Column | Type | Description |
|--------|------|-------------|
| competition_id / player_id | | Composite unique key |
| team_id | INTEGER FK | |
| position | TEXT | |
| gp / goals / assists / total_points / pim | INTEGER | |

### `season_netminder_stats`
Cumulative season stats per netminder per competition.

| Column | Type | Description |
|--------|------|-------------|
| competition_id / player_id | | Composite unique key |
| gp / shots_against / saves / goals_against | INTEGER | |
| save_pct | REAL | |
| gaa | REAL | Goals against average |
| toi | TEXT | |

### `team_season_stats`
Team standings and special-teams stats per competition.

| Column | Type | Description |
|--------|------|-------------|
| competition_id / team_id | | Composite unique key |
| pos / gp / wins / losses / otl | INTEGER | Standings |
| gf / ga / goal_diff / pts | INTEGER | Standings |
| ppo / ppg / pp_pct | INTEGER / REAL | Power play |
| ppga / ppoa / pk_pct | INTEGER / REAL | Penalty kill |
| shg / shga | INTEGER | Shorthanded goals |

## Project Structure

```
ice_hockey_scrape/
├── main.py          # Entry point — orchestrates all passes
├── scraper.py       # HTTP fetching with retries and rate limiting
├── fixtures.py      # Parses the fixtures/results page
├── events.py        # Parses individual event pages (period scores, player stats)
├── season_stats.py  # Parses skater and netminder season stats lists
├── team_stats.py    # Parses team special-teams stats and standings tables
├── db.py            # Database layer: schema init and upsert helpers
├── config.py        # URLs, DB path, request settings
├── requirements.txt
└── siha.db          # SQLite database (created on first run)
```

## Logging

Logs are written to both stdout and `scraper.log`. Use `-v` for debug output including individual HTTP requests.
