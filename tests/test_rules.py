import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
import crawl

class Rules(unittest.TestCase):
    def test_www_and_http_are_the_same_site(self):
        self.assertEqual(crawl.key("http://www.Example.com/page"), crawl.key("https://example.com"))
    def test_dedupe_keeps_one_per_domain_and_prefers_alive(self):
        out = crawl.dedupe([{"url": "https://a.com", "status": "dead"}, {"url": "http://www.a.com", "status": "ok"}])
        self.assertEqual(len(out), 1); self.assertEqual(out[0]["status"], "ok")
    def test_dead_sites_are_kept_for_graveyard(self):
        self.assertEqual(len(crawl.dedupe([{"url": "https://b.com", "status": "dead"}])), 1)
    def test_title_drops_generic_parts_and_domains(self):
        p = crawl.Page(); p.feed("<title>Home | Cozy Pages</title>")
        self.assertEqual(crawl.best_title(p, "cozy.com"), "Cozy Pages")
        p = crawl.Page(); p.feed("<title>elonlit.com | Elon Litman</title>")
        self.assertEqual(crawl.best_title(p, "elonlit.com"), "Elon Litman")
    def test_script_code_does_not_make_a_site_developer(self):
        p = crawl.Page(); p.feed("<script>javascript api developer code</script><title>Pixel Garden</title><p>A gallery of my paintings and illustration work by an artist</p>")
        cat, _, _ = crawl.categorize("Pixel Garden", "", p.heads, " ".join(p.words), "pixel.garden")
        self.assertEqual(cat, "Art")
    def test_weak_signal_is_random(self):
        self.assertEqual(crawl.categorize("Zzz", "", [], "nothing here", "zzz.com")[0], "Random")

if __name__ == "__main__": unittest.main()
