"""Live tests for biletix_mcp — real requests to biletix.com.

Requires network + Chrome TLS impersonation (curl-cffi). The server
is polite by design (~0.8s between requests), so this file takes
~15s. Run: python -m unittest discover -s tests -v

Line-ups change during the day; tests assert structure and sane
ranges, not exact titles or prices.
"""
import json
import unittest

from biletix_mcp import events as E
from biletix_mcp import http as H


class TestLiveHomepage(unittest.TestCase):
    def test_sections(self):
        html_text = H.fetch_home_html()
        data = E.parse_homepage(html_text)
        self.assertGreater(len(data["browse"]), 10)
        self.assertGreater(len(data["starting_soon"]), 10)
        self.assertGreater(len(data["all"]), 20)
        c = data["all"][0]
        self.assertIn("title", c)
        self.assertIn("url", c)
        self.assertIn("price_from_try", c)

    def test_music_present(self):
        html_text = H.fetch_home_html()
        rows = E.parse_homepage(html_text)["all"]
        self.assertGreater(
            sum(1 for r in rows if r.get("category") == "music"), 10
        )


class TestLiveDetail(unittest.TestCase):
    def test_aura(self):
        html_text = H.fetch_page_html(
            "/etkinlik/5BG07/TURKIYE/tr/music-aura-16-11-2026-istanbul"
        )
        d = E.parse_event_detail(html_text)
        self.assertEqual(d["name"], "AURA")
        self.assertEqual(d["venue"], "Bostancı Gösteri Merkezi")
        self.assertGreater(d["price_from_try"], 0)

    def test_unknown_event_404(self):
        with self.assertRaises(H.BiletixError):
            H.fetch_page_html("/etkinlik/XXXXX/TURKIYE/tr/music-nope-01-01-2026-istanbul")


class TestLiveVenue(unittest.TestCase):
    def test_bostanci(self):
        html_text = H.fetch_page_html(
            "/mekan/340BG/TURKIYE/tr/bostanci-gosteri-merkezi-istanbul"
        )
        v = E.parse_venue_page(html_text)
        self.assertEqual(v["venue"], "Bostancı Gösteri Merkezi")
        self.assertGreater(len(v["events"]), 0)


class TestLiveServerTools(unittest.TestCase):
    """End-to-end: call the MCP tool functions and check JSON output."""

    def test_trending_tool(self):
        from biletix_mcp.server import biletix_trending

        out = json.loads(biletix_trending("browse", limit=3))
        self.assertNotIn("error", out)
        self.assertEqual(out["count"], 3)

    def test_search_tool(self):
        from biletix_mcp.server import biletix_search_events

        out = json.loads(biletix_search_events("Simge", limit=5))
        self.assertNotIn("error", out)
        self.assertGreaterEqual(out["count"], 1)

    def test_get_event_tool(self):
        from biletix_mcp.server import biletix_get_event

        out = json.loads(
            biletix_get_event(
                "https://www.biletix.com/etkinlik/5BG07/TURKIYE/tr/"
                "music-aura-16-11-2026-istanbul"
            )
        )
        self.assertNotIn("error", out)
        self.assertEqual(out["name"], "AURA")

    def test_bad_section_error(self):
        from biletix_mcp.server import biletix_trending

        out = json.loads(biletix_trending("nope"))
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
