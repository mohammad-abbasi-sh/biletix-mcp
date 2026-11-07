"""Stdlib parsing for biletix.com server-rendered pages.

Verified live 2026-11-07 against real pages (fixtures in tests/):
- Homepage /anasayfa/TURKIYE/tr (989KB): 92 distinct event cards in two
  SSR sections — "Etkinliklere Göz Atın" (43 cards) and "24 Saat
  İçinde Başlayacaklar" (50 cards, 1 listed in both sections). The
  "Popüler Etkinlikler" and "Biletix'te Yeni Satışta" headings have no
  SSR cards (client-side only). Cards are <a class="event-card"> with
  schema.org microdata: h4 name, startDate/endDate <meta>, location
  name span ("Bostancı Gösteri Merkezi, İstanbul" or "Çeşitli
  Mekanlar" for groups), Turkish date text ("07 Kas 2026" or a range),
  price meta + display text ("1.995₺ 'den itibaren"). Cards link to
  single events (/etkinlik/<code>/...), event groups/tours
  (/etkinlik-grup/<id>/...), artist tours (/artist/<id>/...), one
  venue card (/mekan/<code>/...) and two guide cards
  (guides.biletix.com). Event slugs carry the category prefix + date +
  city ("music-aura-16-11-2026-istanbul"), but some slugs start with
  the artist name instead ("sibel-can-13-11-2026-ankara") — only known
  category tokens count as a category.
- Event detail /etkinlik/<code>/TURKIYE/tr/<slug> (369KB): full
  MusicEvent JSON-LD (name, description, startDate/endDate with +03:00,
  eventStatus, location with address + geo, offers price TRY +
  availability, image) + a venue link (/mekan/<code>/...).
- Venue page /mekan/<code>/TURKIYE/tr/<slug> (482KB): a [Place,
  ItemList] JSON-LD pair — venue name, description, address + geo,
  and 25 upcoming events with offers prices (no event-card markup).
- Event-group page /etkinlik-grup/<id>/... (328KB): an ItemList
  JSON-LD (name + 2 MusicEvent items).

Prices are Turkish format in display text ("1.995₺" -> 1995.0,
"3.171,25₺" -> 3171.25); the price <meta> mixes "3.000" (thousands
dot) and "3171.25" (decimal point), so the display text is parsed.
"""
from __future__ import annotations

import html
import json
import re

BASE = "https://www.biletix.com"

_SECTIONS = {
    "browse": "Etkinliklere Göz Atın",
    "starting_soon": "24 Saat İçinde Başlayacaklar",
}

# Slug first-tokens that are real categories. Event slugs sometimes start
# with the artist name instead ("sibel-can-13-11-2026-ankara"), so only
# known tokens count as a category; anything else leaves it unset.
KNOWN_CATEGORIES = {
    "music", "theatre", "tiyatro", "sport", "spor", "festival", "comedy",
    "komedi", "dance", "dans", "opera", "bale", "musical", "family",
    "aile", "concert", "konser", "show", "gosteri", "exhibition",
    "sergi", "film", "football", "futbol", "basketball", "basketbol",
    "volleyball", "voleybol", "circus", "sirk", "kids", "cocuk",
    "standup",
}


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_price_tr(raw: str | None) -> float | None:
    """Turkish display price -> float TRY. Display text uses Turkish
    format ("1.995" -> 1995.0, "3.171,25" -> 3171.25); the price <meta>
    sometimes uses a decimal point ("3171.25"). Disambiguation: a
    comma means Turkish format; without a comma, exactly three digits
    after the dot means a thousands separator, 1-2 digits a decimal."""
    if raw is None:
        return None
    s = str(raw).strip().replace("₺", "").replace("TL", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+\.\d{3}", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


_CARD_RE = re.compile(
    r'<a\b[^>]*class="event-card"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.S,
)


def _parse_card(url: str, block: str) -> dict:
    if url.startswith("http"):
        full_url = url
    else:
        full_url = BASE + url
    if "/etkinlik-grup/" in url:
        kind = "group"
    elif "/artist/" in url:
        kind = "artist"
    elif "/mekan/" in url:
        kind = "venue"
    elif "guides.biletix.com" in url:
        kind = "guide"
    else:
        kind = "event"
    row: dict = {
        "url": full_url,
        "kind": kind,
        "is_group": kind in ("group", "artist"),
    }
    m = re.search(r'<h4[^>]*itemprop="name"[^>]*>(.*?)</h4>', block, re.S)
    if m:
        row["title"] = _clean(m.group(1))
    m = re.search(r'itemprop="startDate" content="([^"]+)"', block)
    if m:
        row["start"] = m.group(1)
    m = re.search(r'itemprop="endDate" content="([^"]+)"', block)
    if m:
        row["end"] = m.group(1)
    m = re.search(
        r'itemprop="location".*?<span[^>]*itemprop="name"[^>]*>([^<]+)</span>',
        block, re.S,
    )
    if m:
        loc = _clean(m.group(1))
        row["venue"] = loc
        if "," in loc:
            row["city"] = loc.rsplit(",", 1)[1].strip()
    m = re.search(r'class="event-card__date">(.*?)</p>', block, re.S)
    if m:
        date_text = _clean(m.group(1))
        # Strip the mat-icon ligature text ("event") that precedes the date.
        date_text = re.sub(r"^event\s+", "", date_text)
        row["date_text"] = date_text
    m = re.search(r'class="event-card__price">(.*?)</p>', block, re.S)
    if m:
        price_block = m.group(1)
        pm = re.search(r"([\d][\d.,]*)\s*₺", price_block)
        if pm:
            row["price_from_try"] = parse_price_tr(pm.group(1))
        elif re.search(r"itemprop=\"price\" content=\"([^\"]+)\"", price_block):
            row["price_from_try"] = parse_price_tr(
                re.search(r"itemprop=\"price\" content=\"([^\"]+)\"", price_block).group(1)
            )
    # Category + city from the slug: <category>-<name>-<dd>-<mm>-<yyyy>-<city>.
    # Only known category tokens count — slugs often start with the
    # artist name instead ("sibel-can-13-11-2026-ankara").
    parts = url.split("/TURKIYE/tr/")
    if len(parts) == 2:
        slug = parts[1]
        first = slug.split("-")[0]
        if first in KNOWN_CATEGORIES:
            row["category"] = first
        cm = re.search(r"-\d{2}-\d{2}-\d{4}-([a-z]+)$", slug)
        if cm:
            row.setdefault("city", cm.group(1))
    return {k: v for k, v in row.items() if v not in (None, "")}


def parse_cards(html_text: str) -> list[dict]:
    """All event cards on a page (deduped by URL, order preserved)."""
    seen: set[str] = set()
    rows = []
    for url, block in _CARD_RE.findall(html_text):
        if url in seen:
            continue
        seen.add(url)
        row = _parse_card(url, block)
        if row.get("title"):
            rows.append(row)
    return rows


def parse_homepage(html_text: str) -> dict:
    """Homepage -> {"browse": [...], "starting_soon": [...], "all": [...]}.

    Only "Etkinliklere Göz Atın" and "24 Saat İçinde Başlayacaklar"
    are server-rendered; "Popüler Etkinlikler" and "Biletix'te Yeni
    Satışta" render client-side only."""
    heads = [
        (m.start(), _clean(m.group(1)))
        for m in re.finditer(r"<h3[^>]*>([^<]{3,60})</h3>", html_text)
    ]
    out: dict[str, list[dict]] = {}
    for i, (pos, name) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(html_text)
        key = next((k for k, v in _SECTIONS.items() if v == name), None)
        if key:
            out[key] = parse_cards(html_text[pos:end])
    all_rows = parse_cards(html_text)
    out["all"] = all_rows
    return out


# ---------------------------------------------------------------- detail

def parse_event_detail(html_text: str) -> dict:
    """Event detail page -> fields from the Event JSON-LD block."""
    data: dict = {}
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html_text, re.S,
    ):
        try:
            obj = json.loads(m.group(1))
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and str(obj.get("@type", "")).endswith("Event"):
            data = obj
            break
    if not data:
        raise ValueError("no Event JSON-LD found on this event page")
    out: dict = {}
    out["name"] = _clean(data.get("name"))
    out["description"] = _clean(data.get("description"))
    out["start"] = data.get("startDate")
    out["end"] = data.get("endDate")
    out["status"] = (data.get("eventStatus") or "").rsplit("/", 1)[-1]
    loc = data.get("location") or {}
    out["venue"] = _clean(loc.get("name"))
    addr = loc.get("address") or {}
    out["city"] = _clean(addr.get("addressLocality"))
    out["country"] = _clean(addr.get("addressCountry"))
    geo = loc.get("geo") or {}
    if geo.get("latitude") is not None:
        out["latitude"] = geo["latitude"]
        out["longitude"] = geo["longitude"]
    offers = data.get("offers") or {}
    price = offers.get("price")
    if price is not None:
        try:
            out["price_from_try"] = float(price)
        except (TypeError, ValueError):
            pass
    out["price_currency"] = offers.get("priceCurrency")
    out["availability"] = (offers.get("availability") or "").rsplit("/", 1)[-1]
    if data.get("image"):
        out["image"] = data["image"]
    if data.get("url"):
        out["url"] = data["url"]
    m = re.search(r'href="((?:https://www\.biletix\.com)?/mekan/[^"]+)"', html_text)
    if m:
        href = m.group(1)
        out["venue_url"] = href if href.startswith("http") else BASE + href
    m = re.search(r'<title>(.*?)</title>', html_text, re.S)
    if m and not out.get("name"):
        out["name"] = _clean(m.group(1)).split(" biletleri")[0]
    return {k: v for k, v in out.items() if v not in (None, "")}


def _ld_json_blocks(html_text: str) -> list:
    """All JSON-LD blocks on a page (objects or arrays)."""
    out = []
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html_text, re.S,
    ):
        try:
            out.append(json.loads(m.group(1)))
        except (ValueError, TypeError):
            continue
    return out


def _event_row_from_jsonld(item: dict, venue_name: str | None = None) -> dict:
    """One Event JSON-LD object -> the same row shape as a card."""
    row: dict = {}
    if item.get("url"):
        row["url"] = item["url"]
    row["is_group"] = False
    if item.get("name"):
        row["title"] = _clean(item["name"])
    if item.get("startDate"):
        row["start"] = item["startDate"]
    if item.get("endDate"):
        row["end"] = item["endDate"]
    loc = item.get("location") or {}
    if loc.get("name"):
        row["venue"] = _clean(loc["name"])
        if "," in row["venue"]:
            row["city"] = row["venue"].rsplit(",", 1)[1].strip()
    addr = loc.get("address") or {}
    if addr.get("addressLocality"):
        row["city"] = _clean(addr["addressLocality"])
    if venue_name:
        row.setdefault("venue", venue_name)
    offers = item.get("offers") or {}
    price = offers.get("price")
    if price is not None:
        try:
            row["price_from_try"] = float(price)
        except (TypeError, ValueError):
            pass
    if item.get("url"):
        parts = item["url"].split("/TURKIYE/tr/")
        if len(parts) == 2:
            slug = parts[1]
            first = slug.split("-")[0]
            if first in KNOWN_CATEGORIES:
                row["category"] = first
            cm = re.search(r"-\d{2}-\d{2}-\d{4}-([a-z]+)$", slug)
            if cm:
                row.setdefault("city", cm.group(1))
    return {k: v for k, v in row.items() if v not in (None, "")}


def _item_list_events(html_text: str) -> tuple[str, list[dict]] | None:
    """(list name, event rows) from a JSON-LD ItemList block, if any."""
    for block in _ld_json_blocks(html_text):
        blocks = block if isinstance(block, list) else [block]
        for obj in blocks:
            if isinstance(obj, dict) and obj.get("@type") == "ItemList":
                rows = []
                for el in obj.get("itemListElement", []):
                    item = el.get("item") if isinstance(el, dict) else None
                    if isinstance(item, dict):
                        rows.append(_event_row_from_jsonld(item))
                return _clean(obj.get("name")), rows
    return None


def parse_venue_page(html_text: str) -> dict:
    """Venue page -> {"venue", "description", "city", "latitude",
    "longitude", "events": [...]} from the [Place, ItemList] JSON-LD."""
    out: dict = {"events": []}
    for block in _ld_json_blocks(html_text):
        blocks = block if isinstance(block, list) else [block]
        for obj in blocks:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") == "Place":
                out["venue"] = _clean(obj.get("name"))
                out["description"] = _clean(obj.get("description"))
                addr = obj.get("address") or {}
                out["city"] = _clean(addr.get("addressLocality"))
                geo = obj.get("geo") or {}
                if geo.get("latitude") is not None:
                    out["latitude"] = geo["latitude"]
                    out["longitude"] = geo["longitude"]
            elif obj.get("@type") == "ItemList":
                for el in obj.get("itemListElement", []):
                    item = el.get("item") if isinstance(el, dict) else None
                    if isinstance(item, dict):
                        out["events"].append(
                            _event_row_from_jsonld(item, out.get("venue"))
                        )
    if not out["events"]:
        # Fallback: plain event cards.
        cards = parse_cards(html_text)
        if cards:
            out["events"] = cards
    if not out.get("venue"):
        m = re.search(r"<title>(.*?)</title>", html_text, re.S)
        if m:
            out["venue"] = _clean(m.group(1)).removesuffix(" biletleri").strip()
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def parse_event_group_page(html_text: str) -> dict:
    """Event-group page -> {"title": ..., "events": [cards]} from the
    ItemList JSON-LD (falls back to plain cards)."""
    found = _item_list_events(html_text)
    if found:
        title, rows = found
        return {"title": title, "events": rows}
    title = ""
    m = re.search(r"<title>(.*?)</title>", html_text, re.S)
    if m:
        title = _clean(m.group(1)).split(" biletleri")[0].split(" | ")[0]
    return {"title": title, "events": parse_cards(html_text)}
