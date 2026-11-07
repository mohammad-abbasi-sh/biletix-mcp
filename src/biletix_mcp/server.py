"""MCP server: unofficial read-only access to biletix.com events."""
from __future__ import annotations

import json
from collections import Counter

from mcp.server.fastmcp import FastMCP

from . import events as _E
from . import http as _http

mcp = FastMCP("biletix-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for biletix.com, Türkiye's dominant
ticketing platform (Ticketmaster-owned) — concerts, theatre, festivals,
sport. Data comes from the site's server-rendered pages — no login, no
API key. Homepage /anasayfa/TURKIYE/tr carries two SSR sections:
"Etkinliklere Göz Atın" (browse, ~43 featured events) and "24 Saat
İçinde Başlayacaklar" (starting within 24h, ~50 events); the
"Popüler Etkinlikler" and "Biletix'te Yeni Satışta" sections render
client-side only, so trending covers the two SSR sections. Event cards
carry schema.org microdata (title, start/end, venue + city, price from
in TRY, category + date + city in the URL slug, e.g.
"music-aura-16-11-2026-istanbul"). Event detail pages carry full Event
JSON-LD (description, venue with address + geo, price from, availability)
plus a venue-page link. Venue pages list that venue's upcoming events;
event-group pages list an artist/festival tour's dates. Search filters
the homepage's currently featured events (keyword + city) — the site's
own /search page is an Angular shell and its search API is not directly
reachable, so keyword search is scoped to featured listings. Read-only;
transport uses Chrome TLS impersonation; requests are spaced ~0.8s apart.
Built by Mohammad Abbasi (mohammad-abbasi-sh) — Turkey MCP
factory.\
"""

_SECTIONS = ("browse", "starting_soon", "all")


def _err(e: Exception) -> str:
    return json.dumps({"error": str(e)}, ensure_ascii=False)


def _validate_limit(limit: int, lo: int = 1, hi: int = 50) -> int:
    if not lo <= limit <= hi:
        raise ValueError(f"limit must be between {lo} and {hi}")
    return limit


@mcp.tool()
def biletix_trending(section: str = "browse", limit: int = 10) -> str:
    """Trending/featured events on biletix.com. section: "browse"
    ("Etkinliklere Göz Atın", featured events), "starting_soon"
    ("24 Saat İçinde Başlayacaklar", starting within 24h), or "all"
    (every featured event on the homepage). limit 1..50. Returns
    events (title, start/end, date text, venue, city, price from in
    TRY, category, event URL; group/tour cards flagged is_group)."""
    try:
        section = (section or "browse").strip().lower()
        if section not in _SECTIONS:
            raise ValueError(f"section must be one of {', '.join(_SECTIONS)}")
        _validate_limit(limit)
        html_text = _http.fetch_home_html()
        data = _E.parse_homepage(html_text)
        rows = data.get(section, [])
    except (ValueError, _http.BiletixError) as e:
        return _err(e)
    return json.dumps(
        {"section": section, "count": min(limit, len(rows)), "events": rows[:limit]},
        ensure_ascii=False,
    )


@mcp.tool()
def biletix_search_events(query: str, city: str | None = None,
                          limit: int = 10) -> str:
    """Keyword search over biletix.com's currently featured events
    (the homepage's SSR listings — concerts, theatre, festivals,
    sport). query: e.g. "Simge", "Dolu Kadehi Ters Tut", "caz";
    city: e.g. "istanbul", "ankara", "izmir" (matches the event's
    city). limit 1..50. Returns matching events (title, start/end,
    date text, venue, city, price from in TRY, category, event URL).
    Note: this searches featured listings only, not the full
    catalogue — the site's own search page renders client-side."""
    try:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        _validate_limit(limit)
        html_text = _http.fetch_home_html()
        rows = _E.parse_homepage(html_text)["all"]
        q = query.strip().lower()
        c = (city or "").strip().lower()
        matches = []
        for r in rows:
            hay = f"{r.get('title', '')} {r.get('venue', '')}".lower()
            if q not in hay:
                continue
            if c and c not in (r.get("city", "") or "").lower():
                continue
            matches.append(r)
    except (ValueError, _http.BiletixError) as e:
        return _err(e)
    return json.dumps(
        {
            "query": query.strip(),
            "city": city or None,
            "count": min(limit, len(matches)),
            "events": matches[:limit],
        },
        ensure_ascii=False,
    )


@mcp.tool()
def biletix_get_event(event_url: str) -> str:
    """Full detail for one event. event_url: the event's biletix.com
    URL (as returned by the trending/search tools, e.g.
    "https://www.biletix.com/etkinlik/5BG07/TURKIYE/tr/music-aura-16-11-2026-istanbul").
    Returns name, description, start/end, status, venue (+ city,
    geo coordinates, venue-page URL), price from in TRY, availability
    and image."""
    try:
        if not event_url or not event_url.strip():
            raise ValueError("event_url must not be empty")
        html_text = _http.fetch_page_html(event_url.strip())
        data = _E.parse_event_detail(html_text)
    except (ValueError, _http.BiletixError) as e:
        return _err(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
def biletix_list_by_category(category: str, limit: int = 10) -> str:
    """Featured events in one category, from the homepage's SSR
    listings. category: the URL-slug prefix, e.g. "music" (concerts).
    limit 1..50. Returns events in that category plus the list of
    categories present on the homepage today (when the homepage is
    music-heavy, other categories may be empty — the site renders
    non-music categories client-side)."""
    try:
        if not category or not category.strip():
            raise ValueError("category must not be empty")
        _validate_limit(limit)
        html_text = _http.fetch_home_html()
        rows = _E.parse_homepage(html_text)["all"]
        cat = category.strip().lower()
        matches = [r for r in rows if (r.get("category") or "").lower() == cat]
        present = sorted({r.get("category") for r in rows if r.get("category")})
    except (ValueError, _http.BiletixError) as e:
        return _err(e)
    return json.dumps(
        {
            "category": cat,
            "categories_present": present,
            "count": min(limit, len(matches)),
            "events": matches[:limit],
        },
        ensure_ascii=False,
    )


@mcp.tool()
def biletix_list_venues(limit: int = 20) -> str:
    """Venues behind the homepage's featured events: distinct venue
    names with city and featured-event count. limit 1..50. Use
    biletix_get_event to get a venue's page URL, then
    biletix_venue_events for its upcoming events."""
    try:
        _validate_limit(limit)
        html_text = _http.fetch_home_html()
        rows = _E.parse_homepage(html_text)["all"]
        counts: Counter = Counter()
        cities: dict[str, str] = {}
        for r in rows:
            v = r.get("venue")
            if not v:
                continue
            counts[v] += 1
            cities.setdefault(v, r.get("city", ""))
        venues = [
            {"venue": v, "city": cities[v], "featured_events": n}
            for v, n in counts.most_common()
        ]
    except (ValueError, _http.BiletixError) as e:
        return _err(e)
    return json.dumps(
        {"count": min(limit, len(venues)), "venues": venues[:limit]},
        ensure_ascii=False,
    )


@mcp.tool()
def biletix_venue_events(venue_url: str, limit: int = 10) -> str:
    """Upcoming events at one venue. venue_url: the venue's biletix.com
    page URL (as returned by biletix_get_event's venue_url field, e.g.
    "https://www.biletix.com/mekan/340BG/TURKIYE/tr/bostanci-gosteri-merkezi-istanbul").
    limit 1..50. Returns the venue name + its events (title, start/end,
    date text, price from in TRY, event URL)."""
    try:
        if not venue_url or not venue_url.strip():
            raise ValueError("venue_url must not be empty")
        _validate_limit(limit)
        html_text = _http.fetch_page_html(venue_url.strip())
        data = _E.parse_venue_page(html_text)
        rows = data.get("events", [])
    except (ValueError, _http.BiletixError) as e:
        return _err(e)
    out = {
        "venue": data.get("venue"),
        "city": data.get("city"),
        "description": data.get("description"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "count": min(limit, len(rows)),
        "events": rows[:limit],
    }
    return json.dumps(
        {k: v for k, v in out.items() if v not in (None, "")},
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
