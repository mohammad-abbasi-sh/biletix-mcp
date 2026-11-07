# biletix-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/biletix-mcp

Unofficial **read-only** MCP server for biletix.com, Türkiye's dominant ticketing platform (Ticketmaster-owned) — concerts, theatre, festivals, sport: featured/trending events, keyword + city search over featured listings, full event details (venue, dates, price from, availability), events by category, venues and per-venue upcoming events.

> Built by Mohammad Abbasi as part of the "Turkey MCP factory" (Sepehr-style pipeline). Not affiliated with biletix.com.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "biletix": {
      "command": "uvx",
      "args": ["biletix-mcp"]
    }
  }
}
```

Or run locally: `python -m biletix_mcp.server` (needs `mcp<2`, `curl-cffi`).

## Tools

| Tool | Description |
|------|-------------|
| `biletix_trending` | Featured events — `section`: "browse" ("Etkinliklere Göz Atın", 43 events), "starting_soon" ("24 Saat İçinde Başlayacaklar", 50 events), "all" (92 distinct events); `limit` 1..50 |
| `biletix_search_events` | Keyword search over the homepage's featured events — `query` ("Simge", "caz"), optional `city` ("istanbul", "ankara"); `limit` 1..50 |
| `biletix_get_event` | Full detail for one event — `event_url` (as returned by the trending/search tools); returns name, description, start/end, status, venue (+ city, geo, venue-page URL), price from in TRY, availability, image |
| `biletix_list_by_category` | Featured events in one category — `category`: the URL-slug prefix, e.g. "music"; also returns the categories present on the homepage today |
| `biletix_list_venues` | Distinct venues behind the featured events, with city and featured-event count; `limit` 1..50 |
| `biletix_venue_events` | Upcoming events at one venue — `venue_url` (from `biletix_get_event`'s `venue_url` field); `limit` 1..50 |

Example output (`biletix_get_event` / AURA, 16 Nov 2026, Bostancı Gösteri Merkezi):

```json
{"name": "AURA", "start": "2026-11-16T20:00:00+03:00",
 "venue": "Bostancı Gösteri Merkezi", "city": "İstanbul",
 "latitude": 40.9569, "longitude": 29.1018,
 "price_from_try": 1680.0, "price_currency": "TRY",
 "availability": "LimitedAvailability",
 "venue_url": "https://www.biletix.com/mekan/340BG/TURKIYE/tr/bostanci-gosteri-merkezi-istanbul"}
```

## How it works

biletix.com serves its homepage (`/anasayfa/TURKIYE/tr`), event detail pages (`/etkinlik/<code>/TURKIYE/tr/<slug>`), event-group pages (`/etkinlik-grup/<id>/...`) and venue pages (`/mekan/<code>/...`) fully server-rendered — no login, no API key, no session cookies. The bare homepage (`/`) is only a 1.1KB JS redirector shell (`redirector.js` → `/anasayfa/TURKIYE/tr`). Two homepage sections are SSR: "Etkinliklere Göz Atın" (43 cards) and "24 Saat İçinde Başlayacaklar" (50 cards); "Popüler Etkinlikler" and "Biletix'te Yeni Satışta" render client-side only. Event cards carry schema.org microdata (title, start/end, venue + city, price from in TRY, category + date + city in the slug, e.g. `music-aura-16-11-2026-istanbul`); group/tour cards (`/etkinlik-grup/...`, venue "Çeşitli Mekanlar") use the same markup. Detail pages carry a full Event JSON-LD block (description, venue with address + geo, offers price/availability). Prices are Turkish format in the display text ("1.995₺" → 1995.0, "3.171,25₺" → 3171.25). The `/search` and `/category` pages are Angular shells and the `/api/v1/searchquery/searchSuggestion` endpoint 302s to a 404 page for direct calls, so keyword search is scoped to the homepage's featured listings (92 distinct events at build time). Queue-it waiting-room scripts load on the search page but do not gate the SSR fetches. Transport uses Chrome TLS impersonation (`curl-cffi`, `chrome120`); requests are spaced ~0.8s apart; everything is read-only.

## Install

```bash
uvx biletix-mcp        # run directly (needs uv)
# or
pip install biletix-mcp
biletix-mcp    # starts the MCP server on stdio
```

## Tests

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Offline tests run on recorded fixtures (real pages fetched 2026-11-07); live tests hit biletix.com. 24/24 green at build time (15 offline + 9 live) plus an MCP stdio smoke test.

## Roadmap

- Full-catalogue search (needs the site's client-side search API or a sitemap of event URLs)
- Ticket categories / seat-plan prices per event (currently only "from" price)
- Artist pages (`/etkinlik-grup/...` already lists tour dates; a dedicated tool could add them)

## License

MIT — see [LICENSE](LICENSE).
