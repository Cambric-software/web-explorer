import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
import crawl

def page(html):
    p = crawl.Page(); p.feed(html); return p

class Duplicates(unittest.TestCase):
    def test_www_http_slash_and_tracking_are_the_same_site(self):
        k = crawl.key("https://example.com")
        for u in ["http://www.Example.com/page", "https://example.com/", "https://EXAMPLE.com.:443/?utm_source=x",
                  "https://m.example.com", "http://www2.example.com/#top"]:
            self.assertEqual(crawl.key(u), k, u)
            self.assertEqual(crawl.norm(u), "https://example.com", u)
    def test_dedupe_keeps_one_per_domain_and_prefers_alive(self):
        out = crawl.dedupe([{"url": "https://a.com", "status": "dead"}, {"url": "http://www.a.com", "status": "ok"}])
        self.assertEqual(len(out), 1); self.assertEqual(out[0]["status"], "ok")
    def test_dedupe_prefers_hand_edited_copy(self):
        out = crawl.dedupe([{"url": "https://a.com", "status": "ok"}, {"url": "https://www.a.com", "status": "ok", "locked": True}])
        self.assertTrue(out[0].get("locked"))
    def test_same_name_and_description_on_two_domains_is_one_site(self):
        d = "Computer news and analysis for IT leaders and professionals everywhere."
        out = crawl.dedupe([{"url": "https://cw.com", "title": "Computerworld", "description": d},
                            {"url": "https://computerworld.com", "title": "Computerworld", "description": d}])
        self.assertEqual(len(out), 1)
    def test_dead_sites_are_kept_for_graveyard(self):
        self.assertEqual(len(crawl.dedupe([{"url": "https://b.com", "status": "dead"}])), 1)

class Titles(unittest.TestCase):
    def test_title_drops_generic_parts_and_domains(self):
        self.assertEqual(crawl.best_title(page("<title>Home | Cozy Pages</title>"), "cozy.com"), "Cozy Pages")
        self.assertEqual(crawl.best_title(page("<title>elonlit.com | Elon Litman</title>"), "elonlit.com"), "Elon Litman")
    def test_platform_name_is_never_the_title(self):
        self.assertEqual(crawl.best_title(page("<title>Substack</title><h1>The Quiet Letter</h1>"), "quietletter.com"), "The Quiet Letter")
    def test_welcome_prefix_removed(self):
        self.assertEqual(crawl.best_title(page("<title>Welcome to Moss Hollow</title>"), "mosshollow.net"), "Moss Hollow")
    def test_fallback_is_readable_domain(self):
        self.assertEqual(crawl.best_title(page("<title>Untitled</title>"), "entropic-thoughts.com"), "Entropic Thoughts")

class Descriptions(unittest.TestCase):
    def test_cookie_banner_is_not_a_description(self):
        p = page('<meta name="description" content="We use cookies to improve your experience on this site."><p>A slow, hand-drawn zine about growing tomatoes on a tiny balcony.</p>')
        self.assertEqual(crawl.best_description(p, "Zine"), "A slow, hand-drawn zine about growing tomatoes on a tiny balcony.")
    def test_entities_and_title_prefix_cleaned(self):
        p = page('<meta name="description" content="Moss Hollow &amp;mdash; a quiet archive of hand-bound books &amp;amp; letters.">')
        self.assertEqual(crawl.best_description(p, "Moss Hollow"), "A quiet archive of hand-bound books & letters.")
    def test_long_text_cut_at_sentence(self):
        d = crawl.shorten("First sentence is long enough to count as a real sentence, really it is. " + "word " * 60)
        self.assertTrue(d.endswith("really it is."))

class Categories(unittest.TestCase):
    def test_script_code_does_not_make_a_site_developer(self):
        p = page("<script>javascript api developer code</script><pre>python code api</pre><title>Pixel Garden</title><p>A gallery of my paintings and illustration work by an artist</p>")
        cat, _, _ = crawl.categorize("Pixel Garden", "", p.heads, " ".join(p.heads + p.paras), "pixel.garden")
        self.assertEqual(cat, "Art")
    def test_ambiguous_word_in_body_does_not_decide(self):
        cat, _, _ = crawl.categorize("Bread Notes", "", [], "our api is fast. code code code api api", "bread.com")
        self.assertNotEqual(cat, "Developer")
    def test_weak_signal_is_random(self):
        self.assertEqual(crawl.categorize("Zzz", "", [], "nothing here", "zzz.com")[0], "Random")

class Robot(unittest.TestCase):
    def test_robot_never_overwrites_locked_site(self):
        s = {"title": "Mine", "description": "Hand written", "category": "Art", "locked": True}
        crawl.apply(s, {"title": "X", "description": "Y", "category": "Developer", "confidence": 1, "tags": [], "fingerprint": "",
                        "lang": "en", "load_time": 1, "https": True, "words": 100, "embed": True})
        self.assertEqual((s["title"], s["description"], s["category"]), ("Mine", "Hand written", "Art"))
    def test_frame_blocking_headers_disable_inline_preview(self):
        self.assertFalse(crawl.embeddable({"X-Frame-Options": "DENY"}))
        self.assertFalse(crawl.embeddable({"Content-Security-Policy": "frame-ancestors 'self'"}))
        self.assertTrue(crawl.embeddable({}))

class VibesAndTech(unittest.TestCase):
    def test_wordpress_detected_and_not_hand_coded(self):
        t = crawl.tech_tags('<link href="/wp-content/themes/x.css"><script src="a.js"></script>')
        self.assertIn("WordPress", t); self.assertNotIn("Hand-coded", t)
    def test_plain_page_is_hand_coded_without_javascript(self):
        self.assertEqual(crawl.tech_tags("<html><body><p>hi</p></body></html>"), ["Hand-coded", "No JavaScript"])
    def test_vibes_come_from_words_not_code(self):
        v = crawl.vibes("My Cozy Garden", "Tea, baking and my cat", "garden journal", 500, 0, "<script>game play fun</script>", ["Hand-coded"])
        self.assertIn("cozy", v); self.assertNotIn("playful", v)
    def test_old_site_is_retro(self):
        self.assertIn("retro", crawl.vibes("A", "b", "c", 500, 1999))
    def test_locked_site_keeps_its_vibes(self):
        s = {"locked": True, "vibes": ["calm"]}
        crawl.apply(s, {"lang": "en", "load_time": 1, "https": True, "words": 9, "embed": True, "tech": ["Hugo"], "vibes": ["weird"]})
        self.assertEqual((s["vibes"], s["tech"]), (["calm"], ["Hugo"]))

import votes
class HallOfFame(unittest.TestCase):
    def test_each_account_counts_once_newest_wins(self):
        known = {"https://a.com": "https://a.com"}
        issues = [{"title": "Votes: x", "user": {"login": "u"}, "created_at": "1", "body": "+3 https://a.com"},
                  {"title": "Votes: x", "user": {"login": "u"}, "created_at": "2", "body": "+1 https://a.com"},
                  {"title": "Votes: x", "user": {"login": "v"}, "created_at": "3", "body": "+5 https://www.a.com/"}]
        score, voters = votes.tally(issues, known)
        self.assertEqual((score["https://a.com"]["score"], voters), (6, 2))
    def test_made_up_vote_values_ignored(self):
        self.assertEqual(votes.parse("+100 https://a.com"), {})

if __name__ == "__main__": unittest.main()
