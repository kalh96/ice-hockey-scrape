"""Flask web application for Scottish Ice Hockey stats and articles."""

import os
from datetime import date
from pathlib import Path

import frontmatter
import markdown2
from flask import Flask, abort, render_template, request

import db_queries
from config import (
    ARTICLES_DIR, COMPETITIONS, CURRENT_SEASON, SEASONS,
    STATIC_VERSION, TEAM_BY_SLUG, TEAM_DISPLAY,
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
        articles.append(
            {
                "slug": slug,
                "title": post.get("title", slug),
                "date": post.get("date", ""),
                "description": post.get("description", ""),
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
    return {
        "current_year": date.today().year,
        "team_display": TEAM_DISPLAY,
        "static_version": STATIC_VERSION,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    recent = db_queries.get_recent_results("SNL", season=CURRENT_SEASON, limit=5)
    upcoming = db_queries.get_upcoming_fixtures("SNL", season=CURRENT_SEASON, limit=3)
    standings = db_queries.get_standings("SNL", season=CURRENT_SEASON)
    articles = _load_articles()[:3]
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
    return render_template(
        "fixtures.html",
        comp=comp,
        competitions=["all"] + COMPETITIONS,
        season=season,
        seasons=SEASONS,
        upcoming=upcoming,
        results=results,
    )


@app.route("/fixtures/<int:event_id>/")
def event_detail(event_id):
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
