"""HTTP layer for biletix_mcp.

biletix.com serves its homepage (/anasayfa/TURKIYE/tr), event detail
pages (/etkinlik/<code>/TURKIYE/tr/<slug>), event-group pages
(/etkinlik-grup/<id>/TURKIYE/tr/<slug>) and venue pages
(/mekan/<code>/TURKIYE/tr/<slug>) server-rendered — no login, no API
key, no session cookies needed. Plain HTTP 200 with a browser UA
(verified live 2026-11-07). The bare homepage (/) is only a JS
redirector shell (1.1KB, redirector.js -> /anasayfa/TURKIYE/tr), and
the /search and /category pages are Angular shells whose data comes
from a client-side API (the /api/v1/searchquery/searchSuggestion
endpoint 302s to a 404 page for direct calls) — so this server uses
the SSR pages only. The transport still uses curl-cffi chrome120
impersonation, the same proven pattern as the other Turkey-factory
servers. Requests are kept gentle (one at a time, ~0.8s apart) and
read-only. Queue-it waiting-room scripts load on the search page but
do not gate the SSR listing/detail fetches.
"""
from __future__ import annotations

import time
from urllib.parse import quote

from curl_cffi import requests as _r

BASE = "https://www.biletix.com"
TIMEOUT = 30.0
MIN_INTERVAL = 0.8  # seconds between requests — be polite

_HEADERS = {
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

_last_fetch = 0.0


class BiletixError(RuntimeError):
    pass


def _get(url: str) -> str:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = _r.get(url, impersonate="chrome120", headers=_HEADERS, timeout=TIMEOUT)
    except Exception as e:
        raise BiletixError(f"network error fetching {url}: {e}") from e
    finally:
        _last_fetch = time.monotonic()
    if resp.status_code == 403:
        raise BiletixError(
            "biletix.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise BiletixError(
            "biletix.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code in (404, 410):
        raise BiletixError(
            f"page not found (HTTP {resp.status_code}): {url} — check the event / venue URL"
        )
    if resp.status_code != 200:
        raise BiletixError(f"unexpected HTTP {resp.status_code} fetching {url}")
    return resp.text


def fetch_home_html() -> str:
    """Homepage: /anasayfa/TURKIYE/tr (SSR event sections)."""
    return _get(f"{BASE}/anasayfa/TURKIYE/tr")


def fetch_page_html(path_or_url: str) -> str:
    """Any biletix.com page by path (/etkinlik/...) or full URL."""
    if path_or_url.startswith("http"):
        url = path_or_url
    else:
        url = f"{BASE}/{path_or_url.lstrip('/')}"
    if "biletix.com" not in url:
        raise BiletixError(f"not a biletix.com URL: {path_or_url}")
    return _get(url)
