"""Flask web application for Scottish Ice Hockey stats and articles."""

import os
from datetime import date
from pathlib import Path

import frontmatter
import markdown2
from flask import Flask, abort, redirect, render_template, request, url_for

import db_queries
import eihl_queries
import wnihl_queries
from config import (
    ARTICLES_DIR, COMPETITIONS, CUP_BRACKET, CURRENT_SEASON, PLAYOFFS_BRACKET,
    SEASONS, STATIC_VERSION, TEAM_BY_SLUG, TEAM_DISPLAY,
    EIHL_COMPETITIONS, EIHL_COMP_LABELS, EIHL_CURRENT_SEASON, EIHL_SEASONS,
    EIHL_TEAM_DISPLAY, EIHL_SLUG_TO_TEAM,
    WNIHL_COMPETITIONS, WNIHL_COMP_LABELS, WNIHL_CURRENT_SEASON, WNIHL_SEASONS,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-prod")


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------

@app.template_filter("full_name")
def full_name_filter(db_name):
    """DB team name → full team name (e.g. 'Caps' → 'Edinburgh Capitals')."""
    return TEAM_DISPLAY.get(db_name, {}).get("full", db_name)


@app.template_filter("short_name")
def short_name_filter(db_name):
    """DB team name → nickname (e.g. 'Caps' → 'Capitals')."""
    return TEAM_DISPLAY.get(db_name, {}).get("short", db_name)


@app.template_filter("team_slug")
def team_slug_filter(db_name):
    """DB team name → URL slug (e.g. 'Caps' → 'edinburgh-capitals')."""
    return TEAM_DISPLAY.get(db_name, {}).get("slug", db_name.lower().replace(" ", "-"))


@app.template_filter("team_logo")
def team_logo_filter(db_name):
    """DB team name → logo filename (e.g. 'Caps' → 'edinburgh-capitals.png')."""
    return TEAM_DISPLAY.get(db_name, {}).get("logo", "")


@app.template_filter("eihl_logo")
def eihl_logo_filter(db_name):
    """EIHL DB team name → logo filename (e.g. 'Belfast Giants' → 'belfast-giants.png')."""
    return EIHL_TEAM_DISPLAY.get(db_name, {}).get("logo", "")


@app.template_filter("eihl_slug")
def eihl_slug_filter(db_name):
    """EIHL DB team name → URL slug (e.g. 'Belfast Giants' → 'belfast-giants')."""
    return EIHL_TEAM_DISPLAY.get(db_name, {}).get("slug", "")


@app.template_filter("wnihl_slug")
def wnihl_slug_filter(team_name):
    """WNIHL team name → URL slug (e.g. 'Queen Bees' → 'queen-bees')."""
    return wnihl_queries.slugify(team_name)


# ---------------------------------------------------------------------------
# Win probability model
# ---------------------------------------------------------------------------

_FULL_CONFIDENCE_GP = 10  # games needed before prior-season data is fully dropped


def _team_strength(db_name, season):
    """
    Gather strength indicators for one team.
    Returns: pts_pct, form_pct, goal_ratio (all 0–1 floats or None), gp (int).

    Early-season robustness
    -----------------------
    Rather than a hard switch (use prior if gp==0, else ignore it), we blend
    current and prior season data linearly over the first _FULL_CONFIDENCE_GP
    games.  At GP=0 it's 100 % prior; at GP>=10 it's 100 % current.
    If no prior season exists (brand-new team or first season tracked) the
    current data is blended with a league-neutral value of 0.5 so that a
    hot/cold start doesn't immediately dominate the model.
    """
    record = db_queries.get_team_standings_row(db_name, "SNL", season)
    gp = (record or {}).get("gp") or 0

    # Always fetch prior season record for blending, regardless of current gp
    prior_record = None
    idx = SEASONS.index(season) if season in SEASONS else -1
    if idx > 0:
        prior_record = db_queries.get_team_standings_row(
            db_name, "SNL", SEASONS[idx - 1]
        )

    # blend = 0 → all prior/neutral;  blend = 1 → all current
    blend = min(gp, _FULL_CONFIDENCE_GP) / _FULL_CONFIDENCE_GP

    def _pts_pct(rec):
        if not rec or not rec.get("gp"):
            return None
        return rec["pts"] / (rec["gp"] * 2)

    def _goal_ratio(rec):
        if not rec:
            return None
        gf = rec.get("gf") or 0
        ga = rec.get("ga") or 0
        return gf / (gf + ga) if (gf + ga) > 0 else None

    def _blend(curr, prior, neutral=0.5):
        """Weighted blend; falls back gracefully when data is absent."""
        if curr is not None and prior is not None:
            return blend * curr + (1 - blend) * prior
        if curr is not None:
            # No prior season: blend current with league-neutral
            return blend * curr + (1 - blend) * neutral
        if prior is not None:
            return prior   # No current data at all — use prior in full
        return None        # No data whatsoever

    curr_pts  = _pts_pct(record)
    curr_goal = _goal_ratio(record)
    prior_pts = _pts_pct(prior_record)

    # For form: use current-season last-5, blended with prior pts% as proxy
    form_games = db_queries.get_team_form(db_name, season, n=5)
    curr_form  = (
        sum(1 for g in form_games if g["result"] == "W") / len(form_games)
        if form_games else None
    )

    return {
        "pts_pct":    _blend(curr_pts,  prior_pts),
        "form_pct":   _blend(curr_form, prior_pts),   # prior pts% as form proxy
        "goal_ratio": _blend(curr_goal, _goal_ratio(prior_record)),
        "gp":         gp,
    }


def calculate_win_probability(home_db, away_db, season):
    """
    Return win-probability dict for a scheduled fixture.

    Model (weights normalised when H2H unavailable):
      35 % — season points percentage   (blended with prior season early on)
      30 % — recent form (last-5 win %) (blended with prior season early on)
      20 % — goal ratio GF/(GF+GA)      (blended with prior season early on)
      15 % — current-season H2H win rate
             → 8 % if only prior-season H2H is available (half weight)
             → dropped / redistributed if no H2H data at all
    Home advantage: flat +5 % added to raw home score before normalisation.
    Any still-missing factor defaults to 0.5 (neutral).
    """
    NEUTRAL = 0.5
    HOME_ADV = 0.05

    home_s = _team_strength(home_db, season)
    away_s = _team_strength(away_db, season)

    # Current-season H2H
    h2h = db_queries.get_head_to_head(home_db, away_db, season)

    # Prior-season H2H carry-forward (used at half weight when no current H2H)
    prior_h2h = None
    if not h2h:
        idx = SEASONS.index(season) if season in SEASONS else -1
        if idx > 0:
            prior_h2h = db_queries.get_head_to_head(home_db, away_db, SEASONS[idx - 1])

    def _h2h_rate(games):
        wins = sum(
            1 for g in games
            if (g["home_team"] == home_db and (g["home_score"] or 0) > (g["away_score"] or 0))
            or (g["away_team"] == home_db and (g["away_score"] or 0) > (g["home_score"] or 0))
        )
        return wins / len(games)

    if h2h:
        home_h2h = _h2h_rate(h2h)
        away_h2h = 1.0 - home_h2h
        h2h_weight = 0.15
        h2h_source = "current"
    elif prior_h2h:
        home_h2h = _h2h_rate(prior_h2h)
        away_h2h = 1.0 - home_h2h
        h2h_weight = 0.08   # half weight — historical data, less predictive
        h2h_source = "prior"
    else:
        home_h2h = away_h2h = None
        h2h_weight = 0
        h2h_source = "none"

    def _val(v): return v if v is not None else NEUTRAL

    factors = [
        (_val(home_s["pts_pct"]),    _val(away_s["pts_pct"]),    0.35),
        (_val(home_s["form_pct"]),   _val(away_s["form_pct"]),   0.30),
        (_val(home_s["goal_ratio"]), _val(away_s["goal_ratio"]), 0.20),
    ]
    if home_h2h is not None:
        factors.append((home_h2h, away_h2h, h2h_weight))

    total_w  = sum(f[2] for f in factors)
    raw_home = sum(h * w for h, _, w in factors) / total_w + HOME_ADV
    raw_away = sum(a * w for _, a, w in factors) / total_w
    total    = raw_home + raw_away

    home_pct = round(raw_home / total * 100)
    away_pct = 100 - home_pct

    def _pct(v): return round(v * 100) if v is not None else None

    return {
        "home_pct":  home_pct,
        "away_pct":  away_pct,
        "home_factors": {
            "pts":  _pct(home_s["pts_pct"]),
            "form": _pct(home_s["form_pct"]),
            "goals": _pct(home_s["goal_ratio"]),
            "h2h":  _pct(home_h2h),
        },
        "away_factors": {
            "pts":  _pct(away_s["pts_pct"]),
            "form": _pct(away_s["form_pct"]),
            "goals": _pct(away_s["goal_ratio"]),
            "h2h":  _pct(away_h2h),
        },
        "h2h_count":  len(h2h),
        "h2h_source": h2h_source,
        "prior_h2h_count": len(prior_h2h) if prior_h2h else 0,
        "home_gp":    home_s["gp"],
        "away_gp":    away_s["gp"],
        "using_prior_season": home_s["gp"] < _FULL_CONFIDENCE_GP or away_s["gp"] < _FULL_CONFIDENCE_GP,
    }


# ---------------------------------------------------------------------------
# Cup bracket builder
# ---------------------------------------------------------------------------

def _build_cup_bracket(fixtures_by_id, bracket_def=None):
    """Build a renderable bracket structure from a {event_id: fixture} lookup."""
    if bracket_def is None:
        bracket_def = CUP_BRACKET

    def goals_for(team, leg):
        if leg['home_team'] == team:
            return leg['home_score'] or 0
        if leg['away_team'] == team:
            return leg['away_score'] or 0
        return 0

    rounds = []
    for round_def in bracket_def:
        matchups = []
        for leg_ids in round_def['matchups']:
            legs = [fixtures_by_id[eid] for eid in leg_ids if eid in fixtures_by_id]
            if not legs:
                continue
            leg1 = legs[0]
            team1 = leg1['home_team']
            team2 = leg1['away_team']
            if len(legs) >= 2:
                t1_agg = sum(goals_for(team1, l) for l in legs)
                t2_agg = sum(goals_for(team2, l) for l in legs)
                winner = team1 if t1_agg > t2_agg else (team2 if t2_agg > t1_agg else None)
                matchups.append({
                    'team1': team1, 'team2': team2,
                    't1_agg': t1_agg, 't2_agg': t2_agg,
                    'winner': winner, 'legs': legs, 'status': 'final',
                })
            else:
                t1_score = leg1['home_score']
                t2_score = leg1['away_score']
                if leg1['status'] == 'final':
                    winner = team1 if (t1_score or 0) > (t2_score or 0) else (
                             team2 if (t2_score or 0) > (t1_score or 0) else None)
                else:
                    t1_score = t2_score = winner = None
                matchups.append({
                    'team1': team1, 'team2': team2,
                    't1_agg': t1_score, 't2_agg': t2_score,
                    'winner': winner, 'legs': legs, 'status': leg1['status'],
                    'date': leg1.get('date'),
                })
        rounds.append({'name': round_def['name'], 'matchups': matchups})
    return rounds


# ---------------------------------------------------------------------------
# Article helpers
# ---------------------------------------------------------------------------

def _load_articles():
    """Return list of article metadata dicts, sorted newest first."""
    articles = []
    for path in ARTICLES_DIR.glob("*.md"):
        post = frontmatter.load(str(path))
        slug = path.stem
        teams_raw = post.get("teams", [])
        # Extract first paragraph for use as a preview snippet
        first_para = ""
        for block in post.content.strip().split("\n\n"):
            block = block.strip()
            if block and not block.startswith("#"):
                first_para = markdown2.markdown(block)
                break
        articles.append(
            {
                "slug": slug,
                "title": post.get("title", slug),
                "date": post.get("date", ""),
                "description": post.get("description", ""),
                "preview": first_para,
                "teams": teams_raw if isinstance(teams_raw, list) else [teams_raw],
            }
        )
    articles.sort(key=lambda a: str(a["date"]), reverse=True)
    return articles


def _load_article(slug):
    """Return (metadata, html_body) for a single article slug, or None."""
    path = ARTICLES_DIR / f"{slug}.md"
    if not path.exists():
        return None
    post = frontmatter.load(str(path))
    html = markdown2.markdown(
        post.content,
        extras=["fenced-code-blocks", "tables", "header-ids", "strike"],
    )
    teams_raw = post.get("teams", [])
    meta = {
        "slug": slug,
        "title": post.get("title", slug),
        "date": post.get("date", ""),
        "description": post.get("description", ""),
        "teams": teams_raw if isinstance(teams_raw, list) else [teams_raw],
    }
    return meta, html


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    from flask import request as _req, session
    endpoint = _req.endpoint or ""

    # SNL-specific pages explicitly set context to SNL
    _SNL_ENDPOINTS = {
        "fixtures", "fixture_preview", "event_detail", "standings",
        "statistics", "stats_skaters", "stats_netminders",
        "teams_list", "team_detail",
    }

    if endpoint.startswith("eihl"):
        league_ctx = "eihl"
        session["league_ctx"] = "eihl"
    elif endpoint.startswith("wnihl"):
        league_ctx = "wnihl"
        session["league_ctx"] = "wnihl"
        # Track which WNIHL competition was last viewed for the nav teams list
        wnihl_comp = _req.args.get("comp") or session.get("wnihl_comp", "Elite")
        session["wnihl_comp"] = wnihl_comp
    elif endpoint in _SNL_ENDPOINTS:
        league_ctx = "snl"
        session["league_ctx"] = "snl"
    else:
        # Generic pages (home, articles, about) — preserve the last league visited
        league_ctx = session.get("league_ctx", "snl")

    # For WNIHL nav: fetch the team list for the currently active competition
    wnihl_nav_teams = []
    if league_ctx == "wnihl":
        wnihl_comp = session.get("wnihl_comp", "Elite")
        try:
            wnihl_nav_teams = wnihl_queries.get_wnihl_teams_for_nav(wnihl_comp, WNIHL_CURRENT_SEASON)
        except Exception:
            wnihl_nav_teams = []

    return {
        "current_year": date.today().year,
        "team_display": TEAM_DISPLAY,
        "static_version": STATIC_VERSION,
        "league_ctx": league_ctx,
        "eihl_team_display": EIHL_TEAM_DISPLAY,
        "wnihl_comp_labels": WNIHL_COMP_LABELS,
        "wnihl_nav_teams": wnihl_nav_teams,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    recent = db_queries.get_recent_results("all", season=CURRENT_SEASON, limit=5)
    upcoming = db_queries.get_upcoming_fixtures("all", season=CURRENT_SEASON, limit=5)
    standings = db_queries.get_standings("SNL", season=CURRENT_SEASON)
    articles = _load_articles()[:4]
    return render_template(
        "home.html",
        recent=recent,
        upcoming=upcoming,
        standings=standings,
        articles=articles,
    )


@app.route("/articles/")
def articles_list():
    articles = _load_articles()
    return render_template("articles_list.html", articles=articles)


@app.route("/articles/<slug>/")
def article_detail(slug):
    result = _load_article(slug)
    if result is None:
        abort(404)
    meta, body = result
    return render_template("article.html", meta=meta, body=body)


@app.route("/statistics/")
def statistics():
    season = request.args.get("season", CURRENT_SEASON)
    if season not in SEASONS:
        season = CURRENT_SEASON
    comp = request.args.get("comp", "SNL")
    if comp not in COMPETITIONS:
        comp = "SNL"
    standings = db_queries.get_standings(comp, season=season) if comp == "SNL" else []
    top_skaters = db_queries.get_skater_stats(comp, season=season)[:5]
    top_netminders = db_queries.get_netminder_stats(comp, season=season)[:5]
    return render_template(
        "stats.html",
        comp=comp,
        competitions=COMPETITIONS,
        season=season,
        seasons=SEASONS,
        standings=standings,
        top_skaters=top_skaters,
        top_netminders=top_netminders,
    )


@app.route("/statistics/skaters/")
def stats_skaters():
    season = request.args.get("season", CURRENT_SEASON)
    if season not in SEASONS:
        season = CURRENT_SEASON
    comp = request.args.get("comp", "SNL")
    if comp not in COMPETITIONS:
        comp = "SNL"
    skaters = db_queries.get_skater_stats(comp, season=season)
    return render_template(
        "stats_skaters.html",
        comp=comp,
        competitions=COMPETITIONS,
        season=season,
        seasons=SEASONS,
        skaters=skaters,
    )


@app.route("/statistics/netminders/")
def stats_netminders():
    season = request.args.get("season", CURRENT_SEASON)
    if season not in SEASONS:
        season = CURRENT_SEASON
    comp = request.args.get("comp", "SNL")
    if comp not in COMPETITIONS:
        comp = "SNL"
    netminders = db_queries.get_netminder_stats(comp, season=season)
    return render_template(
        "stats_netminders.html",
        comp=comp,
        competitions=COMPETITIONS,
        season=season,
        seasons=SEASONS,
        netminders=netminders,
    )


@app.route("/fixtures/")
def fixtures():
    season = request.args.get("season", CURRENT_SEASON)
    if season not in SEASONS:
        season = CURRENT_SEASON
    comp = request.args.get("comp", "all")
    all_fixtures = db_queries.get_all_fixtures(comp, season=season)
    upcoming = [f for f in all_fixtures if f["status"] == "scheduled"]
    results = [f for f in all_fixtures if f["status"] == "final"]

    bracket = None
    bracket_title = None
    if comp == "Scottish Cup" and season == CURRENT_SEASON:
        all_ids = [eid for rd in CUP_BRACKET for leg in rd["matchups"] for eid in leg]
        bracket = _build_cup_bracket(db_queries.get_fixtures_by_ids(all_ids))
        bracket_title = "2025–26 Scottish Cup"
    elif comp == "SNL Play-offs" and season == CURRENT_SEASON:
        all_ids = [eid for rd in PLAYOFFS_BRACKET for leg in rd["matchups"] for eid in leg]
        bracket = _build_cup_bracket(db_queries.get_fixtures_by_ids(all_ids), PLAYOFFS_BRACKET)
        bracket_title = "2025–26 SNL Play-offs"

    return render_template(
        "fixtures.html",
        comp=comp,
        competitions=["all"] + COMPETITIONS,
        season=season,
        seasons=SEASONS,
        upcoming=upcoming,
        results=results,
        bracket=bracket,
        bracket_title=bracket_title,
    )


@app.route("/fixtures/<int:event_id>/preview/")
def fixture_preview(event_id):
    fixtures_map = db_queries.get_fixtures_by_ids([event_id])
    if not fixtures_map:
        abort(404)
    fixture = fixtures_map[event_id]

    if fixture["status"] == "final":
        return redirect(url_for("event_detail", event_id=event_id))

    home_db = fixture["home_team"]
    away_db = fixture["away_team"]

    home_skaters   = db_queries.get_team_skater_stats(home_db,   season=CURRENT_SEASON)
    home_netminders = db_queries.get_team_netminder_stats(home_db, season=CURRENT_SEASON)
    away_skaters   = db_queries.get_team_skater_stats(away_db,   season=CURRENT_SEASON)
    away_netminders = db_queries.get_team_netminder_stats(away_db, season=CURRENT_SEASON)

    home_form = db_queries.get_team_form(home_db, CURRENT_SEASON)
    away_form = db_queries.get_team_form(away_db, CURRENT_SEASON)
    h2h       = db_queries.get_head_to_head(home_db, away_db, CURRENT_SEASON)
    prob      = calculate_win_probability(home_db, away_db, CURRENT_SEASON)

    return render_template(
        "fixture_preview.html",
        fixture=fixture,
        home_skaters=home_skaters,
        home_netminders=home_netminders,
        away_skaters=away_skaters,
        away_netminders=away_netminders,
        home_form=home_form,
        away_form=away_form,
        h2h=h2h,
        prob=prob,
    )


@app.route("/fixtures/<int:event_id>/")
def event_detail(event_id):
    # Redirect scheduled games to the preview page
    fixtures_map = db_queries.get_fixtures_by_ids([event_id])
    if fixtures_map and fixtures_map[event_id]["status"] != "final":
        return redirect(url_for("fixture_preview", event_id=event_id))

    data = db_queries.get_event_detail(event_id)
    if data is None:
        abort(404)
    skaters = [p for p in data["player_stats"] if p["position"] != "GK"]
    goalkeepers = [p for p in data["player_stats"] if p["position"] == "GK"]
    return render_template(
        "event_detail.html",
        fixture=data["fixture"],
        period_scores=data["period_scores"],
        skaters=skaters,
        goalkeepers=goalkeepers,
    )


@app.route("/teams/")
def teams_list():
    standings = db_queries.get_standings("SNL", season=CURRENT_SEASON)
    # Build a position lookup keyed by DB name
    pos_lookup = {r["name"]: r for r in standings}
    teams = []
    for db_name, info in sorted(TEAM_DISPLAY.items(),
                                key=lambda x: pos_lookup.get(x[0], {}).get("pos", 99)):
        row = pos_lookup.get(db_name)
        teams.append({
            "db_name": db_name,
            "full":    info["full"],
            "slug":    info["slug"],
            "logo":    info["logo"],
            "pos":     row["pos"] if row else None,
            "pts":     row["pts"] if row else None,
            "gp":      row["gp"] if row else None,
        })
    return render_template("teams.html", teams=teams)


@app.route("/teams/<slug>/")
def team_detail(slug):
    db_name = TEAM_BY_SLUG.get(slug)
    if db_name is None:
        abort(404)
    info = TEAM_DISPLAY[db_name]

    recent   = db_queries.get_team_recent_results(db_name, season=CURRENT_SEASON, limit=5)
    upcoming = db_queries.get_team_upcoming_fixtures(db_name, season=CURRENT_SEASON, limit=5)
    standings = db_queries.get_standings("SNL", season=CURRENT_SEASON)
    skaters  = db_queries.get_team_skater_stats(db_name, season=CURRENT_SEASON)
    netminders = db_queries.get_team_netminder_stats(db_name, season=CURRENT_SEASON)

    all_articles = _load_articles()
    team_articles = [a for a in all_articles if info["full"] in a["teams"]]

    return render_template(
        "team_detail.html",
        db_name=db_name,
        info=info,
        standings=standings,
        recent=recent,
        upcoming=upcoming,
        skaters=skaters,
        netminders=netminders,
        articles=team_articles,
        season=CURRENT_SEASON,
    )


@app.route("/about/")
def about():
    return render_template("about.html")


@app.route("/terms/")
def terms():
    return render_template("terms.html")


@app.route("/privacy/")
def privacy():
    return render_template("privacy.html")


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# EIHL routes  (/uk-hockey/elite-league/...)
# ---------------------------------------------------------------------------

def _eihl_short(db_name: str) -> str:
    return EIHL_TEAM_DISPLAY.get(db_name, {}).get("short", db_name)


@app.route("/uk-hockey/elite-league/")
def eihl_overview():
    season = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    comp = request.args.get("comp", "League")
    if comp not in EIHL_COMPETITIONS:
        comp = "League"
    recent    = eihl_queries.get_eihl_recent_results(comp, season=season, limit=8)
    upcoming  = eihl_queries.get_eihl_upcoming_fixtures(comp, season=season, limit=5)
    standings = eihl_queries.get_eihl_standings(comp, season=season)
    return render_template(
        "eihl/overview.html",
        comp=comp, competitions=EIHL_COMPETITIONS,
        comp_labels=EIHL_COMP_LABELS,
        season=season, seasons=EIHL_SEASONS,
        recent=recent, upcoming=upcoming, standings=standings,
        eihl_short=_eihl_short,
    )


@app.route("/uk-hockey/elite-league/fixtures/")
def eihl_fixtures():
    season = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    comp = request.args.get("comp", "all")
    if comp not in (["all"] + EIHL_COMPETITIONS):
        comp = "all"
    all_fx   = eihl_queries.get_eihl_all_fixtures(comp, season=season)
    upcoming = [f for f in all_fx if f["status"] == "scheduled"]
    results  = [f for f in all_fx if f["status"] != "scheduled"]
    return render_template(
        "eihl/fixtures.html",
        comp=comp, competitions=["all"] + EIHL_COMPETITIONS,
        comp_labels=EIHL_COMP_LABELS,
        season=season, seasons=EIHL_SEASONS,
        upcoming=upcoming, results=results,
        eihl_short=_eihl_short,
    )


@app.route("/uk-hockey/elite-league/game/<game_id>/")
def eihl_game_detail(game_id):
    data = eihl_queries.get_eihl_game_detail(game_id)
    if data is None:
        abort(404)
    fixture      = data["fixture"]
    events       = data["events"]
    player_stats = data["player_stats"]
    goals        = [e for e in events if e["event_type"] == "goal"]
    penalties    = [e for e in events if e["event_type"] == "penalty"]
    home_skaters = [p for p in player_stats
                    if p["team"] == fixture["home_team"] and p["position"] != "GK"]
    home_goalies = [p for p in player_stats
                    if p["team"] == fixture["home_team"] and p["position"] == "GK"]
    away_skaters = [p for p in player_stats
                    if p["team"] == fixture["away_team"] and p["position"] != "GK"]
    away_goalies = [p for p in player_stats
                    if p["team"] == fixture["away_team"] and p["position"] == "GK"]
    return render_template(
        "eihl/game_detail.html",
        fixture=fixture,
        goals=goals, penalties=penalties,
        home_skaters=home_skaters, home_goalies=home_goalies,
        away_skaters=away_skaters, away_goalies=away_goalies,
        eihl_short=_eihl_short,
    )


@app.route("/uk-hockey/elite-league/standings/")
def eihl_standings():
    season = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    comp = request.args.get("comp", "League")
    if comp not in EIHL_COMPETITIONS:
        comp = "League"
    standings = eihl_queries.get_eihl_standings(comp, season=season)
    return render_template(
        "eihl/standings.html",
        comp=comp, competitions=EIHL_COMPETITIONS,
        comp_labels=EIHL_COMP_LABELS,
        season=season, seasons=EIHL_SEASONS,
        standings=standings,
    )


@app.route("/uk-hockey/elite-league/teams/<slug>/")
def eihl_team_detail(slug):
    team_name = EIHL_SLUG_TO_TEAM.get(slug)
    if not team_name:
        abort(404)
    season          = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    all_fx          = eihl_queries.get_eihl_team_fixtures(team_name, season=season)
    upcoming        = [f for f in all_fx if f["status"] == "scheduled"]
    results         = [f for f in all_fx if f["status"] != "scheduled"]
    league_standings = eihl_queries.get_eihl_standings("League", season=season)
    cup_standings   = eihl_queries.get_eihl_standings("Cup", season=season)
    skaters         = eihl_queries.get_eihl_team_skaters(team_name, season=season)
    info            = EIHL_TEAM_DISPLAY.get(team_name, {})
    return render_template(
        "eihl/team_detail.html",
        team_name=team_name, info=info, slug=slug,
        season=season, seasons=EIHL_SEASONS,
        upcoming=upcoming, results=results,
        league_standings=league_standings,
        cup_standings=cup_standings,
        skaters=skaters,
        eihl_short=_eihl_short,
    )


@app.route("/uk-hockey/elite-league/statistics/")
def eihl_statistics():
    season = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    comp = request.args.get("comp", "League")
    if comp not in EIHL_COMPETITIONS:
        comp = "League"
    skaters = eihl_queries.get_eihl_skater_stats(comp, season=season)[:10]
    goalies = eihl_queries.get_eihl_goalie_stats(comp, season=season)[:5]
    return render_template(
        "eihl/statistics.html",
        comp=comp, competitions=EIHL_COMPETITIONS,
        comp_labels=EIHL_COMP_LABELS,
        season=season, seasons=EIHL_SEASONS,
        skaters=skaters, goalies=goalies,
    )


@app.route("/uk-hockey/elite-league/statistics/skaters/")
def eihl_stats_skaters():
    season = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    comp = request.args.get("comp", "League")
    if comp not in EIHL_COMPETITIONS:
        comp = "League"
    skaters = eihl_queries.get_eihl_skater_stats(comp, season=season)
    return render_template(
        "eihl/stats_skaters.html",
        comp=comp, competitions=EIHL_COMPETITIONS,
        comp_labels=EIHL_COMP_LABELS,
        season=season, seasons=EIHL_SEASONS,
        skaters=skaters,
    )


@app.route("/uk-hockey/elite-league/statistics/goalies/")
def eihl_stats_goalies():
    season = request.args.get("season", EIHL_CURRENT_SEASON)
    if season not in EIHL_SEASONS:
        season = EIHL_CURRENT_SEASON
    comp = request.args.get("comp", "League")
    if comp not in EIHL_COMPETITIONS:
        comp = "League"
    goalies = eihl_queries.get_eihl_goalie_stats(comp, season=season)
    return render_template(
        "eihl/stats_goalies.html",
        comp=comp, competitions=EIHL_COMPETITIONS,
        comp_labels=EIHL_COMP_LABELS,
        season=season, seasons=EIHL_SEASONS,
        goalies=goalies,
    )


# ---------------------------------------------------------------------------
# WNIHL routes  (/uk-hockey/wnihl/...)
# ---------------------------------------------------------------------------

@app.route("/uk-hockey/wnihl/")
def wnihl_overview():
    season = request.args.get("season", WNIHL_CURRENT_SEASON)
    if season not in WNIHL_SEASONS:
        season = WNIHL_CURRENT_SEASON
    comp = request.args.get("comp", "Elite")
    if comp not in WNIHL_COMPETITIONS:
        comp = "Elite"
    recent    = wnihl_queries.get_wnihl_recent_results(comp, season, limit=8)
    upcoming  = wnihl_queries.get_wnihl_upcoming_fixtures(comp, season, limit=5)
    standings = wnihl_queries.get_wnihl_standings(comp, season)
    return render_template(
        "wnihl/overview.html",
        comp=comp, competitions=WNIHL_COMPETITIONS,
        comp_labels=WNIHL_COMP_LABELS,
        season=season, seasons=WNIHL_SEASONS,
        recent=recent, upcoming=upcoming, standings=standings,
    )


@app.route("/uk-hockey/wnihl/fixtures/")
def wnihl_fixtures():
    season = request.args.get("season", WNIHL_CURRENT_SEASON)
    if season not in WNIHL_SEASONS:
        season = WNIHL_CURRENT_SEASON
    comp = request.args.get("comp", "all")
    if comp not in (["all"] + WNIHL_COMPETITIONS):
        comp = "all"
    all_fx   = wnihl_queries.get_wnihl_all_fixtures(comp, season)
    upcoming = [f for f in all_fx if f["status"] == "scheduled"]
    results  = [f for f in all_fx if f["status"] != "scheduled"]
    return render_template(
        "wnihl/fixtures.html",
        comp=comp, competitions=["all"] + WNIHL_COMPETITIONS,
        comp_labels=WNIHL_COMP_LABELS,
        season=season, seasons=WNIHL_SEASONS,
        upcoming=upcoming, results=results,
    )


@app.route("/uk-hockey/wnihl/teams/")
def wnihl_teams():
    season = request.args.get("season", WNIHL_CURRENT_SEASON)
    if season not in WNIHL_SEASONS:
        season = WNIHL_CURRENT_SEASON
    comp = request.args.get("comp", "Elite")
    if comp not in WNIHL_COMPETITIONS:
        comp = "Elite"
    standings = wnihl_queries.get_wnihl_standings(comp, season)
    return render_template(
        "wnihl/teams.html",
        comp=comp, competitions=WNIHL_COMPETITIONS,
        comp_labels=WNIHL_COMP_LABELS,
        season=season, seasons=WNIHL_SEASONS,
        standings=standings,
    )


@app.route("/uk-hockey/wnihl/teams/<slug>/")
def wnihl_team_detail(slug):
    info = wnihl_queries.get_wnihl_team_by_slug(slug, season=WNIHL_CURRENT_SEASON)
    if not info:
        abort(404)
    team_name   = info["team"]
    competition = info["competition"]
    all_fx      = wnihl_queries.get_wnihl_team_fixtures(team_name, season=WNIHL_CURRENT_SEASON)
    upcoming    = [f for f in all_fx if f["status"] == "scheduled"]
    results     = [f for f in all_fx if f["status"] != "scheduled"]
    standings   = wnihl_queries.get_wnihl_standings(competition, season=WNIHL_CURRENT_SEASON)
    players     = wnihl_queries.get_wnihl_team_players(team_name, competition, season=WNIHL_CURRENT_SEASON)
    return render_template(
        "wnihl/team_detail.html",
        team_name=team_name, competition=competition, slug=slug,
        comp_labels=WNIHL_COMP_LABELS,
        upcoming=upcoming, results=results,
        standings=standings, players=players,
    )


@app.route("/uk-hockey/wnihl/standings/")
def wnihl_standings():
    season = request.args.get("season", WNIHL_CURRENT_SEASON)
    if season not in WNIHL_SEASONS:
        season = WNIHL_CURRENT_SEASON
    comp = request.args.get("comp", "Elite")
    if comp not in WNIHL_COMPETITIONS:
        comp = "Elite"
    standings = wnihl_queries.get_wnihl_standings(comp, season)
    return render_template(
        "wnihl/standings.html",
        comp=comp, competitions=WNIHL_COMPETITIONS,
        comp_labels=WNIHL_COMP_LABELS,
        season=season, seasons=WNIHL_SEASONS,
        standings=standings,
    )


@app.route("/uk-hockey/wnihl/statistics/")
def wnihl_statistics():
    season = request.args.get("season", WNIHL_CURRENT_SEASON)
    if season not in WNIHL_SEASONS:
        season = WNIHL_CURRENT_SEASON
    comp = request.args.get("comp", "Elite")
    if comp not in WNIHL_COMPETITIONS:
        comp = "Elite"
    stats = wnihl_queries.get_wnihl_player_stats(comp, season)
    return render_template(
        "wnihl/statistics.html",
        comp=comp, competitions=WNIHL_COMPETITIONS,
        comp_labels=WNIHL_COMP_LABELS,
        season=season, seasons=WNIHL_SEASONS,
        stats=stats,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
