"""HTTP session for the WNIHL scraper.

The mygameday.app site returns 403 without browser-like headers.
Reuses the same User-Agent approach as the EIHL scraper.
"""

import logging
import time

import requests
from bs4 import BeautifulSoup

from wnihl_config import MAX_RETRIES, REQUEST_DELAY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
        })
    return _session


def get_soup(url: str) -> BeautifulSoup | None:
    """Fetch *url* and return a BeautifulSoup, or None on failure."""
    session = get_session()
    delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_DELAY)
        try:
            logger.debug("GET %s (attempt %d)", url, attempt)
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            logger.debug("  -> %d", resp.status_code)

            if resp.status_code == 404:
                logger.warning("404 for %s -- skipping", url)
                return None
            if resp.status_code == 403:
                logger.warning("403 for %s -- access denied", url)
                return None
            if resp.status_code == 429:
                logger.warning("429 rate-limit; sleeping 30s")
                time.sleep(30)
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
