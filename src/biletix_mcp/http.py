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


_PROFILES = ("chrome120", "chrome131", "safari17_0")
_MAX_ATTEMPTS = 2  # one retry with the next profile
_RETRY_BACKOFF = 1.0  # seconds between attempts
_profile_idx = 0  # sticky: profile that last succeeded


def _request(url: str, headers: dict, timeout: float = TIMEOUT):
    """GET with fingerprint rotation.

    Starts at the sticky profile (chrome120 on a fresh process), retries
    once with the next profile on HTTP 403/429 or a transport error, then
    returns the last response (so the caller raises the specific 403/429
    error) or raises a network error if every attempt failed at the
    transport. Added 2026-11-10 (fleet audit fix).
    """
    global _profile_idx
    last_exc: Exception | None = None
    for k in range(_MAX_ATTEMPTS):
        profile = _PROFILES[(_profile_idx + k) % len(_PROFILES)]
        try:
            resp = _r.get(url, impersonate=profile, headers=headers, timeout=timeout)
        except Exception as e:
            last_exc = e
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            raise BiletixError(f"network error fetching {url}: {e}") from e
        if resp.status_code in (403, 429):
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            return resp
        _profile_idx = (_profile_idx + k) % len(_PROFILES)
        return resp
    raise BiletixError(f"network error fetching {url}: {last_exc}") from last_exc


def _get(url: str) -> str:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = _request(url, _HEADERS)
    except BiletixError:
        raise
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


def health_check() -> dict:
    """One polite probe of the source site.

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `biletix_health` tool
    and the daily smoke CI. Added 2026-11-10 (fleet audit fix).
    """
    url = "https://www.biletix.com/"
    try:
        fetch_home_html()
    except BiletixError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
