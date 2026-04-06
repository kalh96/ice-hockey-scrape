# Scottish Ice Hockey News — Scraper & Website

A Python project combining a stats scraper and a Flask website for Scottish ice hockey. The scraper pulls fixtures, results, player stats, and standings from the SIHA website into a SQLite database. The website serves that data alongside articles written in Markdown.

**Live site:** [scottishhockeynews.co.uk](https://scottishhockeynews.co.uk)

Covers the Scottish National League (SNL), SNL Play-offs, and Scottish Cup.

---

## Repository Structure

```
ice_hockey_scrape/
│
├── main.py                # Scraper entry point — orchestrates all passes
├── scraper.py             # HTTP fetching with retries and rate limiting
├── fixtures.py            # Parses the fixtures/results page
├── events.py              # Parses individual event pages (period scores, player stats)
├── season_stats.py        # Parses skater and netminder season stats lists
├── team_stats.py          # Parses team special-teams stats and standings tables
├── db.py                  # Database layer: schema, migrations, upsert helpers
├── config.py              # Scraper config: URLs, season, team name overrides, skip slugs
├── run_and_push.py        # Runs the scraper, validates the log, commits and pushes siha.db
├── run_scraper.bat        # Windows batch launcher used by Task Scheduler
├── last_run_status.json   # Written after every run_and_push.py execution
├── requirements.txt       # Scraper dependencies
├── Procfile               # Render deployment (runs the Flask web app)
├── runtime.txt            # Python version pin for Render
├── siha.db                # SQLite database (committed for Render deployment)
│
└── web/                   # Flask website
    ├── app.py             # Routes, template filters, bracket builder, article helpers
    ├── db_queries.py      # Read-only SQL queries for the web layer
    ├── config.py          # Web config: seasons, team display, bracket definitions
    ├── requirements.txt   # Web dependencies (Flask, gunicorn, markdown2, etc.)
    ├── articles/          # Markdown article files with YAML frontmatter
    ├── templates/         # Jinja2 HTML templates
    └── static/
        ├── css/style.css
        ├── js/main.js
        └── img/teams/     # Team logo PNG files
```

---

## Scraper

### How it works

Each run of `main.py` executes the following passes in order:

1. **Fixtures pass** — parses all fixtures from the SIHA scoreboard and fixture matrix, upserting results and scheduled games. Blank placeholder fixtures (teams TBC) are skipped for SNL. Dates are normalised to ISO format (`YYYY-MM-DD HH:MM`) on every upsert.
2. **Event detail pass** — for each newly completed fixture, fetches the event page to capture per-period scores and player stats.
3. **Date backfill pass** — fills in missing dates for completed fixtures that were scraped before a date was available.
4. **Season stats pass** — scrapes cumulative skater, netminder, team special-teams, and standings tables.
5. **Validation pass** — cross-checks standings computed from fixture results against the scraped league table and logs any discrepancies.

All passes are idempotent — re-running is safe and only updates changed data.

### Competition protection

The scraper only overwrites the `competition_id` of a fixture if it is currently tagged as SNL or Scottish Cup. Fixtures manually tagged as **SNL Play-offs** are preserved across scraper runs.

### Setup

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
```

### Usage

```bash
# Full scrape (recommended)
python main.py

# Fixtures and season stats only (skip event detail scraping)
python main.py --stats-only

# Fixtures pass only
python main.py --fixtures-only

# Force-fetch a single event by ID (for debugging)
python main.py --event 17434 --verbose

# Use a different database file
python main.py --db ~/backups/siha_backup.db
```

| Flag | Description |
|------|-------------|
| `--fixtures-only` | Only run the fixtures pass |
| `--stats-only` | Run fixtures + season stats passes |
| `--event ID` | Force-fetch a single event by ID |
| `--db PATH` | Path to SQLite database (default: `siha.db`) |
| `-v`, `--verbose` | Enable DEBUG-level logging |

### Logging

Logs are written to both stdout and `scraper.log`. Use `-v` for debug output.

### Team name overrides

The SIHA website occasionally returns incorrect or abbreviated team names. Corrections are defined in `config.py`:

```python
TEAM_NAME_OVERRIDES = {
    "paisleypirates": "Paisley Pirates",
}
```

Add entries here (keyed by URL slug) to permanently fix a team name regardless of what the SIHA website returns.

### Skipping teams

Non-SNL or youth teams that appear on the SIHA fixtures page can be excluded by slug:

```python
SKIP_TEAM_SLUGS = {"moray", "moray-juniors-u14", "belfast-giants"}
```

Any fixture involving one of these slugs is silently skipped.

### Season management

The current season is set in `config.py`:

```python
CURRENT_SEASON = "2025-26"
```

All scraped data is tagged with this value. When a new season starts, update `CURRENT_SEASON` and the URL constants in `config.py` — previous seasons' data is preserved in the database.

---

## Automation

### run_and_push.py

`run_and_push.py` is the single entry point for scheduled runs. It:

1. Runs `python main.py`
2. Reads the tail of `scraper.log` and checks for errors
3. Commits and pushes `siha.db` to git if the run was clean (exit 0, no ERROR lines, "Done." present)
4. Writes a status summary to `last_run_status.json`

```bash
python run_and_push.py
```

### Windows Task Scheduler

`run_scraper.bat` launches `run_and_push.py` and appends all output to `run_and_push.log`. It is triggered by the Windows Task Scheduler task **IceHockeyScraper** on the following schedule:

- **Saturday and Sunday** at 23:00 local time
- **Tuesday** at 06:00 local time

The scheduled task can be managed with:

```powershell
schtasks /Query /TN "IceHockeyScraper" /FO LIST
```

### Remote validation agent

A Claude Code scheduled agent runs after each scrape window to verify the live site has updated correctly:

- **Schedule:** 07:00 UTC on Sunday, Monday, and Tuesday
- **Manage at:** https://claude.ai/code/scheduled/trig_016z2zhBc5tHM47GA3iPEkf1

---

## Database Schema

The database is created and migrated automatically on each scraper run.

### `fixtures`
| Column | Type | Description |
|--------|------|-------------|
| event_id | INTEGER PK | SIHA event ID |
| competition_id | INTEGER FK | |
| season | TEXT | e.g. `2025-26` |
| date | TEXT | ISO datetime (may be NULL until backfilled) |
| home_team_id / away_team_id | INTEGER FK | |
| home_score / away_score | INTEGER | NULL for scheduled fixtures |
| status | TEXT | `final` or `scheduled` |
| event_url | TEXT | Relative path to event page |
| scraped_at | TEXT | ISO timestamp of last scrape |

### `event_period_scores`
Per-team period breakdown for each completed event.

| Column | Type | Description |
|--------|------|-------------|
| event_id / team_id | INTEGER FK | Composite unique key |
| period_1 / period_2 / period_3 | INTEGER | Goals per period |
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
| season / competition_id / player_id | | Composite unique key |
| team_id | INTEGER FK | |
| position | TEXT | |
| gp / goals / assists / total_points / pim | INTEGER | |

### `season_netminder_stats`
Cumulative season stats per netminder per competition.

| Column | Type | Description |
|--------|------|-------------|
| season / competition_id / player_id | | Composite unique key |
| gp / shots_against / saves / goals_against | INTEGER | |
| save_pct | REAL | |
| gaa | REAL | Goals against average |
| toi | TEXT | |

### `team_season_stats`
Team standings and special-teams stats per competition.

| Column | Type | Description |
|--------|------|-------------|
| season / competition_id / team_id | | Composite unique key |
| pos / gp / wins / losses / otl | INTEGER | Standings |
| gf / ga / goal_diff / pts | INTEGER | Standings |
| ppo / ppg / pp_pct | INTEGER / REAL | Power play |
| ppga / ppoa / pk_pct | INTEGER / REAL | Penalty kill |
| shg / shga | INTEGER | Shorthanded goals |

---

## Website

A Flask application served from the `web/` directory. It reads live data from `siha.db` and renders articles written in Markdown.

### Running locally

```bash
cd web
pip install -r requirements.txt
flask run
```

The site will be available at `http://localhost:5000`.

### Pages

| URL | Description |
|-----|-------------|
| `/` | Home — recent results (all competitions), upcoming fixtures, mini standings, latest articles |
| `/articles/` | Article index |
| `/articles/<slug>/` | Single article |
| `/statistics/` | SNL standings with logos, top skaters, top netminders |
| `/statistics/skaters/` | Full season skater stats — sortable table |
| `/statistics/netminders/` | Full season netminder stats — sortable table |
| `/fixtures/` | All fixtures and results; Scottish Cup and SNL Play-offs tabs show a visual bracket |
| `/fixtures/<id>/` | Match report — period scores and player stats |
| `/teams/` | Team grid |
| `/teams/<slug>/` | Team page — logo, club website link, SNL standings, results, player stats, related articles |
| `/about/` | About |
| `/terms/` | Terms of Service |
| `/privacy/` | Privacy Policy |

Statistics and fixtures pages include a season selector (visible once more than one season exists) and a competition filter (SNL / SNL Play-offs / Scottish Cup). All league tables and stats tables support client-side column sorting.

### Tournament brackets

The fixtures page displays a visual bracket for the Scottish Cup and SNL Play-offs. Bracket definitions are maintained in `web/config.py`:

- **`CUP_BRACKET`** — Scottish Cup: QF, SF, Final event IDs (two-legged QFs and SFs, single-leg Final)
- **`PLAYOFFS_BRACKET`** — SNL Play-offs: QF, SF, Final event IDs (two-legged QFs, single-leg SFs and Final)

Each matchup is a list of event IDs (one per leg). Update these each season with the real event IDs from the SIHA website.

### Writing articles

Create a Markdown file in `web/articles/` with a date-prefixed filename:

```
web/articles/2026-03-25-my-article.md
```

Every article requires a frontmatter block at the top:

```markdown
---
title: "My Article Title"
date: 2026-03-25
description: "A one-line summary shown on the articles list."
teams:
  - Edinburgh Capitals
  - Dundee Rockets
---

Article content in Markdown here...
```

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Displayed as the article heading |
| `date` | Yes | Format `YYYY-MM-DD` — used for sorting |
| `description` | No | Preview text on the articles list and home page |
| `teams` | No | List of full team names — article appears on those teams' pages |

To publish, commit and push the file:

```bash
git add web/articles/2026-03-25-my-article.md
git commit -m "Add article: My Article Title"
git push
```

Render deploys automatically within a minute or two.

### Team configuration

Each team's display settings and club website URL are defined in `web/config.py` under `TEAM_DISPLAY`:

```python
"Caps": {
    "full":    "Edinburgh Capitals",   # Full name (standings, team pages)
    "short":   "Capitals",             # Nickname (fixtures, stats tables)
    "slug":    "edinburgh-capitals",   # URL identifier (/teams/<slug>/)
    "logo":    "edinburgh-capitals.png",
    "website": "https://www.edcapitals.com",
},
```

Logo PNG files live in `web/static/img/teams/`. Pages degrade gracefully if a logo file is missing. The club website button only appears on a team page if `website` is non-empty.

### Season rollover (each August)

**`config.py`** (scraper):
```python
CURRENT_SEASON = "2026-27"
FIXTURES_URL = f"{BASE_URL}/fixtures-26-27/"
# Update all STATS_URLS entries to point to 2026-27 pages
```

**`web/config.py`** (website):
```python
CURRENT_SEASON = "2026-27"
SEASONS = ["2025-26", "2026-27"]
# Reset CUP_BRACKET and PLAYOFFS_BRACKET with the new season's event IDs
```

Push the changes. The scraper immediately starts writing 2026-27 data separately, and a season selector appears on the website allowing visitors to browse historical seasons.

### Static asset caching

Cloudflare caches static files aggressively. Bump `STATIC_VERSION` in `web/config.py` whenever CSS, JS, or image files change:

```python
STATIC_VERSION = "20260405-4"
```

All static asset URLs include `?v={{ static_version }}` to bust the Cloudflare cache on the next deploy.

### Deployment

The site is deployed on [Render](https://render.com) with [Cloudflare](https://cloudflare.com) handling DNS and CDN.

- **Build command:** `pip install -r web/requirements.txt`
- **Start command:** `gunicorn --chdir web app:app`
- Render redeploys automatically on every push to `master`
- Database updates are delivered by committing `siha.db` — handled automatically by `run_and_push.py` after each scheduled scrape
