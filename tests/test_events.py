"""Offline tests for biletix_mcp.events — recorded real biletix.com pages.

Fixtures are real pages fetched 2026-11-07 (curl-cffi chrome120):
- homepage.html: /anasayfa/TURKIYE/tr (93 cards: 43 "Etkinliklere
  Göz Atın" + 50 "24 Saat İçinde Başlayacaklar", 92 distinct events).
- event-detail.html: AURA, 16 Nov 2026, Bostancı Gösteri Merkezi
  (MusicEvent JSON-LD, price from 1680 TRY).
- venue.html: Bostancı Gösteri Merkezi ([Place, ItemList] JSON-LD,
  25 upcoming events).
- event-group.html: Sibel Can tour (ItemList JSON-LD, 2 dates).
"""
import os
import unittest

from biletix_mcp import events as E

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class TestParsePrice(unittest.TestCase):
    def test_turkish_format(self):
        self.assertEqual(E.parse_price_tr("1.995"), 1995.0)
        self.assertEqual(E.parse_price_tr("3.171,25"), 3171.25)
        self.assertEqual(E.parse_price_tr("3171.25"), 3171.25)
        self.assertEqual(E.parse_price_tr("200"), 200.0)

    def test_bad(self):
        self.assertIsNone(E.parse_price_tr(None))
        self.assertIsNone(E.parse_price_tr("n/a"))


class TestHomepageParse(unittest.TestCase):
    def setUp(self):
        self.data = E.parse_homepage(_read("homepage.html"))

    def test_section_counts(self):
        self.assertEqual(len(self.data["browse"]), 43)
        self.assertEqual(len(self.data["starting_soon"]), 50)
        self.assertEqual(len(self.data["all"]), 92)

    def test_first_browse_card(self):
        c = self.data["browse"][0]
        self.assertEqual(c["title"], "Yalın - Bir Büyülü Gece")
        self.assertTrue(c["is_group"])
        self.assertEqual(c["start"], "2026-12-11T18:00:00")
        self.assertEqual(c["venue"], "Çeşitli Mekanlar")
        self.assertEqual(c["date_text"], "11 Ara 2026 - 12 Ara 2026")
        self.assertEqual(c["price_from_try"], 3000.0)

    def test_first_soon_card(self):
        c = self.data["starting_soon"][0]
        self.assertEqual(c["title"], "Sanat Performance'ta Sahne Senin! - Karaoke Night - Kasım Etkinlikleri")
        self.assertEqual(c["venue"], "Sanat Performance, İstanbul")
        self.assertEqual(c["city"], "İstanbul")
        self.assertEqual(c["category"], "music")
        self.assertEqual(c["price_from_try"], 200.0)

    def test_music_category(self):
        music = [r for r in self.data["all"] if r.get("category") == "music"]
        self.assertEqual(len(music), 65)

    def test_all_have_title_url(self):
        for r in self.data["all"]:
            self.assertIn("title", r)
            self.assertTrue(
                r["url"].startswith("https://www.biletix.com/")
                or r["url"].startswith("https://guides.biletix.com/")
            )

    def test_card_kinds(self):
        from collections import Counter

        kinds = Counter(r.get("kind") for r in self.data["all"])
        self.assertEqual(kinds["event"], 65)
        self.assertEqual(kinds["group"], 21)
        self.assertEqual(kinds["artist"], 3)
        self.assertEqual(kinds["guide"], 2)
        self.assertEqual(kinds["venue"], 1)


class TestEventDetailParse(unittest.TestCase):
    def setUp(self):
        self.d = E.parse_event_detail(_read("event-detail.html"))

    def test_core(self):
        self.assertEqual(self.d["name"], "AURA")
        self.assertEqual(self.d["start"], "2026-11-16T20:00:00+03:00")
        self.assertEqual(self.d["venue"], "Bostancı Gösteri Merkezi")
        self.assertEqual(self.d["city"], "İstanbul")
        self.assertEqual(self.d["price_from_try"], 1680.0)
        self.assertEqual(self.d["price_currency"], "TRY")
        self.assertEqual(self.d["availability"], "LimitedAvailability")

    def test_geo(self):
        self.assertAlmostEqual(float(self.d["latitude"]), 40.9569, places=3)
        self.assertAlmostEqual(float(self.d["longitude"]), 29.1018, places=3)

    def test_venue_url(self):
        self.assertEqual(
            self.d["venue_url"],
            "https://www.biletix.com/mekan/340BG/TURKIYE/tr/bostanci-gosteri-merkezi-istanbul",
        )

    def test_no_event(self):
        with self.assertRaises(ValueError):
            E.parse_event_detail("<html><body>no data</body></html>")


class TestVenueParse(unittest.TestCase):
    def setUp(self):
        self.v = E.parse_venue_page(_read("venue.html"))

    def test_venue(self):
        self.assertEqual(self.v["venue"], "Bostancı Gösteri Merkezi")
        self.assertEqual(self.v["city"], "İstanbul")
        self.assertAlmostEqual(float(self.v["latitude"]), 40.9569, places=3)

    def test_events(self):
        self.assertEqual(len(self.v["events"]), 25)
        first = self.v["events"][0]
        self.assertEqual(first["title"], "Saatleri Ayarlama Enstitüsü")
        self.assertEqual(first["start"], "2026-11-07T21:00:00+03:00")
        self.assertEqual(first["price_from_try"], 1404.0)
        self.assertEqual(first["venue"], "Bostancı Gösteri Merkezi")


class TestGroupParse(unittest.TestCase):
    def test_group(self):
        g = E.parse_event_group_page(_read("event-group.html"))
        self.assertEqual(g["title"], "Sibel Can - Bayhan Müzik Konserleri")
        self.assertEqual(len(g["events"]), 2)
        self.assertEqual(g["events"][0]["title"], "Sibel Can")
        self.assertEqual(g["events"][0]["city"], "Ankara")
        self.assertEqual(g["events"][0]["price_from_try"], 1249.0)
        self.assertEqual(g["events"][1]["city"], "İstanbul")
        self.assertEqual(g["events"][1]["price_from_try"], 1836.5)


if __name__ == "__main__":
    unittest.main()
