"""Shared HTTP session with rate-limiting, retries, and HTML parsing."""

import logging
import time

import requests
from bs4 import BeautifulSoup

from config import MAX_RETRIES, REQUEST_DELAY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(
            {"User-Agent": "siha-scraper/1.0 (hockey stats research)"}
        )
    return _session


def get_soup(url: str) -> BeautifulSoup | None:
    """Fetch *url* and return a BeautifulSoup, or None on 404 / exhausted retries."""
    session = get_session()
    delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_DELAY)
        try:
            logger.debug("GET %s (attempt %d)", url, attempt)
            t0 = time.monotonic()
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            elapsed = time.monotonic() - t0
            logger.debug("  → %d in %.2fs", resp.status_code, elapsed)

            if resp.status_code == 404:
                logger.warning("404 for %s — skipping", url)
                return None

            if resp.status_code == 429:
                wait = 30
                logger.warning("429 rate-limit; sleeping %ds", wait)
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                logger.warning("HTTP %d for %s", resp.status_code, url)
                time.sleep(delay)
                delay *= 2
                continue

            resp.raise_for_status()

            try:
                return BeautifulSoup(resp.content, "lxml")
            except Exception:
                return BeautifulSoup(resp.content, "html.parser")

        except requests.RequestException as exc:
            logger.warning("Request error for %s: %s", url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2

    logger.error("Giving up on %s after %d attempts", url, MAX_RETRIES)
    return None
