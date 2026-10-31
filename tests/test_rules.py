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

GOOD_TEXT = ("I grow tomatoes, beans and far too many herbs on a tiny city balcony, and this journal is where I write down "
             "what worked, what failed and what the pigeons stole this week. ") * 8
def good_html(title="Balcony Tomato Journal", desc="A slow, hand-written journal about growing tomatoes and herbs on a tiny city balcony.", body=GOOD_TEXT, extra=""):
    return (f'<html lang="en"><head><title>{title}</title><meta name="description" content="{desc}"></head><body>'
            f'<h1>{title}</h1><p>{body}</p>{extra}</body></html>')

class QualityGates(unittest.TestCase):
    def test_real_human_page_passes(self):
        self.assertEqual(crawl.junk_reason(page(good_html()), good_html()), "")
    def test_low_word_count_rejected(self):
        h = good_html(body="Only a few real words about my balcony garden. " * 9)
        self.assertEqual(crawl.junk_reason(page(h), h), "too few words")
    def test_header_and_nav_words_do_not_count(self):
        filler = "<header>" + "menu word " * 300 + "</header><nav>" + "nav word " * 300 + "</nav>"
        h = good_html(body="Only a few real words about my balcony garden. " * 9, extra=filler)
        self.assertEqual(crawl.junk_reason(page(h), h), "too few words")
    def test_small_handmade_page_with_100_plus_words_passes(self):
        h = good_html(body="My little corner of the web where I share pixel art and zines. " * 10)
        self.assertEqual(crawl.junk_reason(page(h), h), "")
    def test_creator_and_social_links_are_not_a_link_farm(self):
        links = "".join(f'<a href="https://{d}/me">support me on {d} please thank you</a>' for d in ["patreon.com","ko-fi.com","github.com","bsky.app"] * 6)
        h = good_html(body="I write long essays about software and performance. " * 25, extra=links)
        self.assertEqual(crawl.junk_reason(page(h), h), "")
    def test_link_heavy_directory_rejected(self):
        links = "".join(f'<li><a href="https://site{i}.com">Wonderful hand made website number {i}</a></li>' for i in range(80))
        h = good_html(body="A list of websites I like.", extra="<ul>" + links + "</ul>")
        self.assertEqual(crawl.junk_reason(page(h), h), "link farm")
    def test_empty_javascript_shell_rejected(self):
        h = '<html><head><title>Cool App</title></head><body><div id="root"></div><script src="/app.js"></script></body></html>'
        self.assertEqual(crawl.junk_reason(page(h), h), "empty javascript shell")
    def test_wordpress_starter_rejected(self):
        h = good_html(title="Sunny Days", extra="<p>Just another WordPress site</p>")
        self.assertEqual(crawl.junk_reason(page(h), h), "starter template")
    def test_default_server_page_rejected(self):
        for t in ["Welcome to nginx!", "Apache2 Ubuntu Default Page: It works"]:
            h = good_html(title=t)
            self.assertIn(crawl.junk_reason(page(h), h), ("starter template", "parked"), t)
    def test_cookie_wall_rejected(self):
        h = good_html(body="We use cookies to give you the best experience. Accept all cookies to continue. " + GOOD_TEXT)
        self.assertEqual(crawl.junk_reason(page(h), h), "cookie wall")
    def test_cookie_banner_description_rejected(self):
        self.assertFalse(crawl.good_description("We use cookies to improve your experience on this website, please accept."))
    def test_login_gate_rejected(self):
        h = good_html(body="Sign in to continue reading this page. " + GOOD_TEXT)
        self.assertEqual(crawl.junk_reason(page(h), h), "login gate")
    def test_bot_challenge_rejected(self):
        h = good_html(title="Just a moment...")
        self.assertEqual(crawl.junk_reason(page(h), h), "bot challenge")
    def test_parked_domain_rejected(self):
        h = good_html(extra="<p>This domain is for sale. Powered by sedoparking.</p>")
        self.assertEqual(crawl.junk_reason(page(h), h), "parked")

class LazyTitles(unittest.TestCase):
    def test_generic_titles_rejected(self):
        for t in ["Home", "Index", "Welcome", "Main Page", "Untitled", "example.com", "Example"]:
            self.assertTrue(crawl.lazy_title(t, "example.com"), t)
    def test_real_name_accepted(self):
        self.assertFalse(crawl.lazy_title("Moss Hollow Press", "mosshollow.net"))
    def test_bare_domain_page_has_no_title(self):
        self.assertEqual(crawl.page_title(page("<title>Home</title>"), "zzz.com"), "")
    def test_branding_suffix_stripped(self):
        self.assertEqual(crawl.best_title(page("<title>Moss Hollow | Powered by WordPress</title>"), "mh.net"), "Moss Hollow")

class StrictDescriptions(unittest.TestCase):
    def test_short_description_rejected(self):
        self.assertFalse(crawl.good_description("A tiny zine about tomatoes."))
    def test_self_referential_rejected(self):
        self.assertFalse(crawl.good_description("Welcome to my website, where you can find out more about everything here."))
        self.assertFalse(crawl.good_description("Click here to find out more about our wonderful little hand made shop."))
    def test_lowercase_or_gibberish_rejected(self):
        self.assertFalse(crawl.good_description("a slow, hand-drawn zine about growing tomatoes on a tiny balcony."))
        self.assertFalse(crawl.good_description("Xkcdrt bvnmw qrtzp lkjhg sdfgh trwqp mnbvc zxcvb plkjh qwrtz."))
    def test_real_description_accepted(self):
        self.assertTrue(crawl.good_description("A slow, hand-drawn zine about growing tomatoes on a tiny city balcony."))

class StrictCategories(unittest.TestCase):
    def test_low_confidence_site_rejected(self):
        self.assertIsNone(crawl.strict_category("Zzz", "", [], "nothing here", "zzz.com"))
    def test_tied_categories_rejected(self):
        self.assertIsNone(crawl.strict_category("Game Art", "Games and art", ["game", "art"], "", "x.com"))
    def test_clear_category_accepted(self):
        r = crawl.strict_category("Pixel Garden", "A gallery of paintings and illustration by an artist", ["Illustration gallery"], "painting drawing", "pixel.garden")
        self.assertEqual(r[0], "Art")

class SelfHealing(unittest.TestCase):
    def test_casino_takeover_detected(self):
        h = "<title>Best Casino Online</title><h1>Online casino and sports betting</h1><p>Play slot gacor casino, betting bonus every day for you.</p>"
        self.assertTrue(crawl.flipped(page(h)))
        self.assertFalse(crawl.flipped(page(good_html())))
    def test_redirect_to_big_platform_detected(self):
        self.assertTrue(crawl.corporate_redirect("https://oldblog.net", "https://www.facebook.com/oldblog"))
        self.assertTrue(crawl.corporate_redirect("https://oldblog.net", "https://dan.com/buy-domain/oldblog.net"))
        self.assertFalse(crawl.corporate_redirect("https://oldblog.net", "https://www.oldblog.net/home"))

class Sourcing(unittest.TestCase):
    def test_indie_platforms_come_first(self):
        self.assertGreater(crawl.priority("https://tomato.neocities.org"), crawl.priority("https://shop.bigcorp.com"))
        self.assertGreater(crawl.priority("https://mosshollow.me"), crawl.priority("https://mosshollow.com"))
    def test_commercial_platforms_blocked(self):
        for u in ["https://www.etsy.com", "https://linktr.ee", "https://shop.ebay.com", "https://wordpress.com"]:
            self.assertFalse(crawl.allowed(u), u)
        self.assertTrue(crawl.allowed("https://tomato.wordpress.com"))
    def test_endorsement_pages_followed(self):
        r = {"url": "https://me.net", "anchors": [("https://me.net/blogroll", "Blogroll"), ("https://me.net/now", "Now"),
                                                    ("https://me.net/shop", "Shop")]}
        pages = crawl.link_pages(r)
        self.assertIn("https://me.net/blogroll", pages); self.assertNotIn("https://me.net/shop", pages)
    def test_run_cap_is_small(self):
        self.assertTrue(30 <= crawl.MAX_NEW <= 50)

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


class PlayfulSites(unittest.TestCase):
    def test_canvas_game_with_little_text_passes(self):
        h = "<html><head><title>Tiny Space Game</title></head><body><h1>Tiny Space Game</h1><p>Click to play. Dodge the rocks and beat your high score.</p><canvas id=c></canvas><script>c.getContext('2d')</script></body></html>"
        self.assertEqual(crawl.junk_reason(page(h), h), "")
    def test_short_text_without_play_still_rejected(self):
        h = "<html><head><title>Notes</title></head><body><h1>Notes</h1><p>Some short notes about my week and things here.</p></body></html>"
        self.assertIn(crawl.junk_reason(page(h), h), ("too few words", "empty javascript shell"))
    def test_play_category_never_random(self):
        self.assertIn(crawl.play_category("Bloop", "A little sound toy", [], "", "bloop.neocities.org")[0], crawl.PLAY_CATS)
        self.assertEqual(crawl.play_category("Maze Runner", "Play a maze", [], "", "x.com")[0], "Games")

if __name__ == "__main__": unittest.main()
