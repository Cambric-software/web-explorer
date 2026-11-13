"""Website Explorer discovery robot (v4 - "guilty until proven innocent").
Runs inside GitHub Actions with only the Python standard library.
Database = docs/data/sites.json, statistics = docs/data/stats.json.

Jobs on every run:
  1. clean    - merge duplicate websites (strict address normalization + same-content check)
  2. discover - gather candidates from several sources, verify, describe, categorize
  3. deep     - read known websites' link pages / blogrolls for more candidates
  4. recheck  - re-verify websites not checked for 30 days (then the oldest), refresh details
  5. safety   - compare every website with a public malware list, re-scan the oldest-scanned pages
  6. tags     - vibe check (cozy, playful, retro...) and tech tags (WordPress, hand-coded...) per website
  7. archive  - look up the first Internet Archive year for websites that lack one
New websites must pass strict quality gates (enough real words, not a link farm, not an empty
JavaScript shell, not a starter template, cookie wall, login gate, bot challenge or parked domain,
a real name, a real description and a confident category). At most MAX_NEW are accepted per run.
Websites edited by hand in the control room are "locked": the robot never changes their
name, description, category, review flag or status.
"""
import json, os, random, re, time, datetime, html as htmllib, urllib.request, urllib.parse
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

DB = "docs/data/sites.json"; STATS = "docs/data/stats.json"

# Permanent domain blocklist loaded from docs/data/blocked.json
BLOCKED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data", "blocked.json")
try:
    if os.path.exists(BLOCKED_PATH):
        _raw_b = json.load(open(BLOCKED_PATH, "r", encoding="utf-8"))
        if isinstance(_raw_b, dict) and "domains" in _raw_b:
            BLOCKED_DOMAINS = set(_raw_b["domains"])
        elif isinstance(_raw_b, list):
            BLOCKED_DOMAINS = set(_raw_b)
        elif isinstance(_raw_b, dict):
            BLOCKED_DOMAINS = set(_raw_b.keys())
        else:
            BLOCKED_DOMAINS = set()
    else:
        BLOCKED_DOMAINS = set()
except Exception:
    BLOCKED_DOMAINS = set()
UA = {"User-Agent": "Mozilla/5.0 (compatible; WebsiteExplorerBot/3.0; +https://cambric-software.github.io/web-explorer/)",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en;q=0.9,*;q=0.5"}
TODAY = datetime.date.today().isoformat()
STALE_DAYS = 30
BIG = {"google.com","youtube.com","youtu.be","facebook.com","twitter.com","//x.com","instagram.com","github.com","reddit.com",
       "amazon.com","wikipedia.org","linkedin.com","tiktok.com","medium.com","apple.com","microsoft.com","t.co","bit.ly",
       "news.ycombinator.com","lobste.rs","docs.google.com","drive.google.com","sites.google.com","archive.org","arxiv.org",
       "nytimes.com","bbc.co.uk","bbc.com","theguardian.com","cnn.com","bloomberg.com","substack.com","imgur.com",
       "discord.gg","discord.com","t.me","whatsapp.com","pinterest.com","goo.gl","play.google.com","wiby.me","bearblog.dev",
       "web.archive.org","mastodon.social","bsky.app","threads.net","linktr.ee","patreon.com","ko-fi.com","buymeacoffee.com"}
BAD_TLDS = (".zip", ".mov", ".xyz.ru", ".gov", ".mil")
PARKED = ["domain for sale","buy this domain","this domain is for sale","domain is parked","parked free","parkingcrew",
          "sedoparking","account suspended","coming soon","under construction","website is under construction",
          "default web site page","welcome to nginx","apache2 ubuntu default page","it works!","index of /",
          "hugedomains","dan.com","afternic","godaddy.com/domains"]
BLOCKED = ["just a moment","attention required","access denied","verify you are human","enable javascript and cookies",
           "403 forbidden","404 not found","page not found","site not found","error 404","bad gateway","forbidden"]
MAX_NEW = 35           # newly accepted websites per run (fast growth, every one still passes the quality gates)
PLAY_MIN_WORDS = 12    # games, toys and interactive art need only a little text
PLAY_CATS = ("Games", "Art", "Retro")
PLAY_HTML = re.compile(r"<canvas|webgl|getcontext\(|three(\.min)?\.js|p5(\.min)?\.js|phaser|pixi(\.min)?\.js|kaboom|matter(\.min)?\.js|"
                       r"tone(\.min)?\.js|howler|<audio|webaudio|audiocontext|unity(loader|\.loader)|godot|\.wasm|ruffle|<svg[^>]+viewbox", re.I)
PLAY_WORDS = re.compile(r"(?<![a-z])(game|games|play|toy|toys|puzzle|interactive|draw|paint|synth|sound toy|generator|simulator|"
                        r"sandbox|arcade|experiment|experiments|click|maze|pixel|retro|8-bit|ascii|webring|guestbook|shrine|neocities)(?![a-z])", re.I)
MIN_WORDS = 100        # visible meaningful words a new website needs (small handmade home pages count)
MAX_LINK_RATIO = 0.50  # share of visible text that may be link text to other websites
# Creator / profile / support links never count toward the link-farm ratio
FRIENDLY_LINKS = ("patreon.com","ko-fi.com","github.com","gitlab.com","codeberg.org","buymeacoffee.com","liberapay.com",
                  "mastodon","fosstodon.org","hachyderm.io","bsky.app","twitter.com","//x.com","linkedin.com","youtube.com","instagram.com",
                  "neocities.org","web.archive.org","creativecommons.org","/rss","/feed")
MIN_CONTENT_CHARS = 200  # text inside <p>, <h1>-<h6>, <article>, <li>; less = empty JavaScript shell
MIN_DESC = 45
CAT_MIN_SCORE = 6; CAT_MIN_CONF = 0.6
# Commercial / big-tech platforms we never index or crawl
BIG |= {"ebay.com","etsy.com","aliexpress.com","alibaba.com","walmart.com","target.com","bestbuy.com","temu.com","shein.com",
        "shopify.com","myshopify.com","booking.com","tripadvisor.com","yelp.com","quora.com","yahoo.com","bing.com","msn.com",
        "netflix.com","spotify.com","twitch.tv","vimeo.com","dailymotion.com","tumblr.com","snapchat.com","vk.com","weibo.com",
        "godaddy.com","namecheap.com","dan.com","afternic.com","sedo.com","hugedomains.com","bodis.com","parkingcrew.net",
        "doubleclick.net","googlesyndication.com","adnxs.com","taboola.com","outbrain.com","criteo.com","amazon-adsystem.com",
        "beacons.ai","lnk.bio","bio.link","campsite.bio","carrd.co","about.me","sharepoint.com","office.com","atlassian.net",
        "slack.com","zoom.us","salesforce.com","hubspot.com","wix.com","squarespace.com","webflow.io","notion.site","forbes.com",
        "businessinsider.com","huffpost.com","buzzfeed.com","gofundme.com","onlyfans.com","fiverr.com","upwork.com","glassdoor.com",
        "indeed.com","play.google.com","apps.apple.com"}
PARKED += ["bodis","parked domain","this domain may be for sale","domain name is for sale","make an offer on this domain",
           "related searches","sponsored listings","this web page is parked","inquire about this domain"]
CHALLENGE = ["just a moment...","checking your browser","verify you are human","attention required! | cloudflare",
             "ddos protection by cloudflare","cf-browser-verification","cf-turnstile","challenge-platform","please complete the security check",
             "are you a robot","enable javascript and cookies to continue"]
TEMPLATE = ["just another wordpress site","welcome to wordpress","this is your first post","welcome to ghost",
            "thoughts, stories and ideas","welcome to strapi","built with webflow","this is a placeholder",
            "made with squarespace","this is your about page","welcome to our website","welcome to my website","under construction",
            "coming soon","site under maintenance","website is under maintenance","welcome to nginx","apache2 ubuntu default page",
            "apache2 debian default page","it works!","test page for the apache","iis windows server","lorem ipsum","your site description",
            "edit this page to","start editing to see some magic","create-react-app","vite + react","welcome to your new site"]
TEMPLATE_HEAD = ["hello world!", "hello world"]  # only a template when it is the page's title or heading
COOKIE = ["we use cookies","accept all cookies","accept cookies","by clicking accept","by clicking \"accept","you agree to our use of cookies",
          "gdpr","manage cookie preferences","cookie preferences","cookie settings","this site uses cookies","this website uses cookies",
          "consent to the use of cookies","your privacy choices"]
LOGIN = ["sign in to continue","log in to continue","login to continue","log in to view","sign in to view","log in to see",
         "subscribe to read","subscribe to continue reading","subscribe to read the full story","members only","create an account to continue",
         "you must be logged in","please log in","please sign in","enter your password","this content is password protected"]
FLIP = ["casino","betting","sportsbook","slot online","slot gacor","togel","judi","poker online","crypto giveaway","free bitcoin",
        "porn","xxx","adult cams","escort","viagra","payday loan","replica watches"]
CORPORATE = {"facebook.com","instagram.com","linkedin.com","medium.com","godaddy.com","dan.com","afternic.com","sedo.com",
             "hugedomains.com","twitter.com","//x.com","tiktok.com","linktr.ee","substack.com","wix.com","squarespace.com","namecheap.com"}
INDIE = re.compile(r"(neocities\.org|bearblog\.dev|github\.io|codeberg\.page|pages\.dev|tilde\.[a-z]+|ctrl-c\.club|"
                   r"sdf\.org|envs\.net|nekoweb\.org|omg\.lol|smol\.pub|prose\.sh|mataroa\.blog|micro\.blog)$")

# Strict Profanity, Slur, and NSFW Content Shield
PROFANITY_PATTERNS = [
    r"f+u+c+k+\w*", r"s+h+i+t+\w*", r"b+i+t+c+h+\w*", r"c+u+n+t+\w*",
    r"a+s+s+h+o+l+e+\w*", r"b+a+s+t+a+r+d+\w*", r"d+i+c+k+(head|bag|face|wad|less|ish|s)?\b",
    r"p+u+s+s+y+\w*", r"c+o+c+k+(s|head|sucker|ring|y)?\b", r"w+h+o+r+e+\w*", r"s+l+u+t+\w*",
    r"n+i+g+g+\w*", r"f+a+g+g+o+t+\w*", r"f+a+g+s?\b", r"r+e+t+a+r+d+\w*",
    r"18\+|r-18|r18|nsfw|mature\s+(content|themes?)", r"p+o+r+n+\w*", r"h+e+n+t+a+i+\w*",
    r"e+r+o+t+i+c+\w*", r"x+x+x+", r"n+u+d+e+s?|nudity", r"g+o+r+e+|snuff",
    r"c+a+s+i+n+o+|g+a+m+b+l+i+n+g+|s+l+o+t\s+online", r"o+n+l+y+f+a+n+s+", r"e+s+c+o+r+t+s?"
]
VULGARITY_AND_NSFW_RE = re.compile(
    r"(?<![a-zA-Z0-9])(" + "|".join(PROFANITY_PATTERNS) + r")(?![a-zA-Z0-9])",
    re.I
)

ADULT_RE = re.compile(r"(?<![a-z0-9])(18\+|r-18|r18|nsfw|mature (content|themes?)|sexual themes?|run by an adult|adult themes?|adults? only|libidos?|strong language|"
                      r"yaoi|yuri|hentai|lewd|erotic\w*|fetish\w*|skimpy|porn\w*|xxx|escorts?|onlyfans|nudes?|nudity|gore|"
                      r"casino|gambling|betting|slot online|slot gacor|togel|judi|poker online)(?![a-z])", re.I)
PROFANITY_RE = re.compile(r"(?<![a-z])(ass|asses|asshole|f+u+c+k+\w*|fck|wtf|s+h+i+t+\w*|bullshit|b+i+t+c+h+\w*|dick|dicks|cock|cocks|"
                          r"pussy|cunt\w*|bastard\w*|hellhole|damn|bs|stfu|motherf\w*|whore\w*|slut\w*)(?![a-z])", re.I)

def unsafe_text(*parts):
    """Zero tolerance: adult / explicit / gambling words or profanity anywhere in the given text."""
    s = " ".join(x or "" for x in parts)
    return bool(ADULT_RE.search(s) or PROFANITY_RE.search(s) or VULGARITY_AND_NSFW_RE.search(s))


UNSAFE = ["casino","betting","porn","xxx","escort","viagra","crypto giveaway","free bitcoin","loan approval","hack account"]

# ---------------------------------------------------------------- addresses
TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_|source$|igshid)")
STRIP_PREFIX = ("www.", "www1.", "www2.", "www3.", "m.", "mobile.", "amp.")

def canon_host(h):
    h = (h or "").strip().lower().split("@")[-1].split(":")[0].rstrip(".")
    try: h = h.encode("idna").decode("ascii")
    except Exception: pass
    for p in STRIP_PREFIX:
        if h.startswith(p) and h.count(".") >= 2: h = h[len(p):]; break
    return h

def host(u):
    try:
        u = (u or "").strip()
        return canon_host(urllib.parse.urlparse(u if "//" in u else "//" + u).netloc)
    except Exception: return ""

def key(u):
    """Duplicate key: one website per domain, whatever the scheme, www/m., port, path or tracking tags."""
    return host(u)

def norm(u):
    """Canonical homepage URL for a candidate, or None if it is not a usable website address."""
    try: p = urllib.parse.urlparse((u or "").strip())
    except Exception: return None
    if p.scheme not in ("http", "https") or not p.netloc or "@" in p.netloc: return None
    h = canon_host(p.netloc)
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z0-9-]{2,}", h) or h.endswith(BAD_TLDS) or ".gov." in h or ".mil." in h or ".." in h: return None
    if re.fullmatch(r"[\d.]+", h): return None
    return "https://" + h

# Hosting platforms whose own homepage is commercial, while their users' subdomains are indie websites.
PLATFORM_ROOTS = {"wordpress.com","neocities.org","github.io","bearblog.dev","blogspot.com","tumblr.com","codeberg.page",
                  "pages.dev","netlify.app","vercel.app","micro.blog","omg.lol","nekoweb.org","substack.com"}

def allowed(u):
    h = host(u)
    if not h or h in PLATFORM_ROOTS: return False
    if BLOCKED_DOMAINS and (h in BLOCKED_DOMAINS or key(u) in BLOCKED_DOMAINS): return False
    if h.endswith(BAD_TLDS) or ".gov." in h or ".mil." in h: return False
    if any(h == b or h.endswith("." + b) and b not in ("bearblog.dev",) for b in BIG): return False
    if h in ("phys.org", "johndcook.com"): return False
    return True

def embeddable(headers):
    """Can the website be shown inside our Stumble Bar frame?"""
    xfo = (headers.get("X-Frame-Options") or "").strip().lower()
    if xfo in ("deny", "sameorigin") or xfo.startswith("allow-from"): return False
    m = re.search(r"frame-ancestors([^;]*)", headers.get("Content-Security-Policy") or "", re.I)
    if m and not re.search(r"(^|\s)(\*|https:)(\s|$)", m.group(1).strip()): return False
    return True

def get(url, timeout=8, limit=600_000):
    req = urllib.request.Request(url, headers=UA)
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(limit)
        ctype = r.headers.get("Content-Type", "")
        charset = (re.search(r"charset=([\w-]+)", ctype) or [None, "utf-8"])[1]
        try: text = body.decode(charset, "ignore")
        except LookupError: text = body.decode("utf-8", "ignore")
        return r.status, r.geturl(), text, ctype, round(time.time() - t, 2), r.headers

# ---------------------------------------------------------------- reading pages
class Page(HTMLParser):
    """Collects only what a human sees. Scripts, styles, code blocks, menus, forms and footers are ignored."""
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "nav", "footer", "pre", "code", "form",
            "button", "select", "option", "textarea", "aside", "math", "canvas", "object"}
    VOID = {"area","base","br","col","embed","hr","img","input","link","meta","source","track","wbr"}
    def __init__(s):
        super().__init__(convert_charrefs=True)
        s.title = ""; s.meta = {}; s.lang = ""; s.links = []; s.anchors = []; s.heads = []; s.paras = []; s.words = []
        s.canonical = ""; s._stack = []; s._skip = 0; s._buf = ""; s._a = None; s._atext = ""
        s.link_words = 0; s.link_counts = {}; s.content_chars = 0; s.passwords = 0; s.forms = 0; s._hdr = 0; s._content = 0
    def handle_starttag(s, tag, a):
        a = {k: (v or "") for k, v in a}
        if tag in s.VOID:
            if tag == "meta":
                k = (a.get("name") or a.get("property") or "").lower()
                if k and a.get("content") and k not in s.meta: s.meta[k] = a["content"]
            if tag == "link" and "canonical" in a.get("rel", "").lower() and not s.canonical: s.canonical = a.get("href", "")
            if tag == "input" and a.get("type", "").lower() == "password": s.passwords += 1
            return
        if tag == "form": s.forms += 1
        if tag == "header": s._hdr += 1
        if tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "article", "li", "blockquote") and not s._skip: s._content += 1
        if tag in s.SKIP: s._skip += 1
        if tag == "html": s.lang = a.get("lang", "")[:2].lower()
        if tag == "a":
            s._a = a.get("href", ""); s._atext = ""
            if s._a.startswith("http"): s.links.append(s._a)
        if tag in ("title", "h1", "h2", "p", "li") and not s._skip: s._stack.append(tag); s._buf = ""
    def handle_endtag(s, tag):
        if tag in s.SKIP and s._skip: s._skip -= 1
        if tag == "header" and s._hdr: s._hdr -= 1
        if tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "article", "li", "blockquote") and s._content: s._content -= 1
        if tag == "a" and s._a is not None:
            if len(s.anchors) < 300: s.anchors.append((s._a, clean(s._atext)))
            s._a = None
        if s._stack and s._stack[-1] == tag:
            s._stack.pop(); t = clean(s._buf)
            if tag == "title" and not s.title: s.title = t
            elif tag in ("h1", "h2") and t and len(s.heads) < 8: s.heads.append(t)
            elif tag == "p" and len(t) > 40 and len(s.paras) < 12: s.paras.append(t)
            s._buf = ""
    def handle_data(s, d):
        if s._a is not None: s._atext += d
        if s._skip and not (s._stack and s._stack[-1] == "title"): return
        if s._stack: s._buf += d
        if s._stack and s._stack[-1] == "title": return  # the <title> is not page content
        if s._content: s.content_chars += len(d.strip())
        if s._hdr: return
        w = [x for x in d.split() if re.search(r"[^\W\d_]{2,}", x)]
        if len(s.words) < 3000:
            if s._a is not None: s.link_words += len(w); s.link_counts[s._a] = s.link_counts.get(s._a, 0) + len(w)
            s.words.extend(w)

def clean(t):
    """Readable single-line text: entities decoded, tags/control characters removed, spaces collapsed."""
    t = htmllib.unescape(htmllib.unescape(t or ""))
    t = re.sub(r"<[^>]{0,200}>", " ", t)
    t = re.sub(r"[\u200b-\u200f\u2028\u2029\ufeff\x00-\x1f\x7f]", " ", t)
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()

SEP = r"\s+[|–—·•:»/-]\s+|\s+::\s+|\s*\|\s*|(?<=[a-z]):\s+"
GENERIC = {"home","homepage","home page","welcome","index","main","main page","official website","official site","start",
           "untitled","blog","my blog","my site","my website","website","site","portfolio","document","new tab","loading",
           "loading...","react app","vite app","vite + react","coming soon","about","about me","default","landing page","app","start here","get started","hello","hello world","posts","articles","writing","notes","news","landing","landing!","enter","portal","neko","uwu","guh","dog","other sites","redirecting..."}
PLATFORM = {"substack","wordpress","wordpress.com","blogger","blogspot","medium","ghost","squarespace","wix","weebly",
            "notion","carrd","github pages","neocities","tumblr","bear blog","ʕ•ᴥ•ʔ bear blog","micro.blog","write.as",
            "hashnode","dev.to","linktree","shopify","webflow","framer","jekyll","hugo","next.js","gatsby"}
DOMAINLIKE = re.compile(r"(https?://)?(www\.)?[\w.-]+\.[a-z]{2,}/?")
PREFIX = re.compile(r"^(welcome to|welcome|home page of|homepage of|home of|the official (web)?site of|official (web)?site of)\b\s*[:\-–—|,!]?|^(/[a-zA-Z0-9_.-]+)+/\s*", re.I)


def good_name(t):
    t = PREFIX.sub("", clean(t)).strip(" -|·:•»")
    low = t.lower()
    if not (2 <= len(t) <= 80) or low in GENERIC or low in PLATFORM or DOMAINLIKE.fullmatch(low): return ""
    if not re.search(r"[^\W\d_]", t) or any(b in low for b in BLOCKED): return ""
    return t

def pretty_domain(h):
    labels = h.split(".")
    stem = labels[0] if len(labels) > 1 else h
    return re.sub(r"[-_]+", " ", stem).strip().title() or h

BRANDING = re.compile(r"\s*([|•·–—-]|::)\s*(powered by\b.*|just another\b.*|official (web)?site\b.*|proudly powered\b.*|"
                      r"built with\b.*|made with\b.*|a wordpress site\b.*)$|\s+(powered|proudly powered) by\b.*$", re.I)

def page_title(p, h):
    """Name taken from the page itself, or "" when the page offers no real name."""
    return best_title(p, h, fallback=False)

def best_title(p, h, fallback=True):
    stem = re.sub(r"[^a-z0-9]", "", h.split(".")[0])
    def pick(raw):
        parts = [good_name(x) for x in re.split(SEP, BRANDING.sub("", clean(raw)))]; parts = [x for x in parts if x]
        if not parts: return ""
        match = [x for x in parts if stem and len(stem) > 2 and stem in re.sub(r"[^a-z0-9]", "", x.lower())]
        if match: return min(match, key=len)
        if len(parts) == 1: return parts[0]
        return parts[-1] if len(parts[-1]) <= 30 and len(parts[-1]) < len(parts[0]) else parts[0]
    site = good_name(p.meta.get("og:site_name", ""))
    title = (site if site and len(site) <= 60 else "") or pick(p.title) or pick(p.meta.get("og:title", "")) \
        or pick(p.meta.get("twitter:title", "")) or next((good_name(x) for x in p.heads[:2] if good_name(x) and len(x) <= 60), "") \
        or (pretty_domain(h) if fallback else "")
    if len(title) > 70: title = title[:70].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    return title

BOILER = re.compile(r"click to open|add my button|copy the code|link back to me|for webrings|use the mouse wheel|touch swipe|not optimized for mobile|cookie|javascript|enable js|your browser|skip to|sign in|log in|login|subscribe now|all rights reserved|"
                    r"copyright|©|lorem ipsum|loading|click here|privacy policy|terms of (use|service)|page not found|"
                    r"just a moment|accept all|we use|this site uses|redirecting|please wait|404", re.I)

def shorten(d, n=200):
    d = re.sub(r"\s*(\.\.\.|…)\s*$", "", d).strip()
    if len(d) <= n: return d
    cut = d[:n]; end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end >= 60: return cut[:end + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:-–") + "…"

def tidy_description(d, title):
    d = clean(d); d = re.sub(r"https?://\S+|www\.\S+", "", d).strip()
    t = title.lower().rstrip("…")
    if t and d.lower().startswith(t):  # "Name - what it is" -> "what it is"
        rest = d[len(t):]
        if re.match(r"^\s*[|–—:·•-]\s*", rest): d = re.sub(r"^\s*[|–—:·•-]\s*", "", rest)
    d = d.strip(" -|·•")
    if len(d) < 25 or d.lower() == t or BOILER.search(d): return ""
    words = d.split()
    if len(words) < 4 or d.count("|") + d.count(",") > len(words) / 2: return ""  # keyword lists
    if sum(c.isalpha() for c in d) < len(d) * 0.6: return ""
    if d.isupper(): d = d.capitalize()
    d = shorten(d)
    return d[0].upper() + d[1:]

def best_description(p, title):
    for raw in [p.meta.get("description", ""), p.meta.get("og:description", ""), p.meta.get("twitter:description", "")] \
               + [x for x in p.paras if len(x.split()) >= 8] + p.heads[1:3]:
        d = tidy_description(raw, title)
        if d: return d
    return ""

# ---------------------------------------------------------------- quality gates (new websites)
SELF_REF = re.compile(r"^(welcome to (my|our|the)\b|welcome!|click here|find out more|official (home|site|website) of|"
                      r"this is (my|our) (web)?site|home of the official|visit our|learn more about us|just another)", re.I)

def lazy_title(t, h=""):
    """Generic, empty or bare-domain names are not good enough for a new website."""
    low = clean(t).lower().strip(" .!")
    if not low or low in GENERIC or low in PLATFORM or DOMAINLIKE.fullmatch(low): return True
    if re.match(r"^(hello+|hey+|hi+|test+|asdf+)", low): return True
    bare = re.sub(r"[^a-z0-9]", "", low)
    if h and bare in (re.sub(r"[^a-z0-9]", "", h.lower()), re.sub(r"[^a-z0-9]", "", h.lower().split(".")[0])): return True
    if not re.search(r"[^\W\d_]{3,}", low): return True
    return False

def good_description(d):
    """At least MIN_DESC characters of real, capitalised sentences with a natural mix of vowels."""
    d = (d or "").strip()
    if len(d) < MIN_DESC or not d[0].isupper() or SELF_REF.search(d): return False
    if any(w in d.lower() for w in COOKIE + LOGIN + TEMPLATE): return False
    letters = [c for c in d.lower() if c.isalpha()]
    if not letters: return False
    if all(ord(c) < 128 for c in letters):  # vowel check only makes sense for Latin text
        v = sum(c in "aeiouy" for c in letters) / len(letters)
        if not 0.25 <= v <= 0.6: return False
    words = d.split()
    if len(words) < 7: return False
    if sum(1 for w in words if w[:1].isupper()) > len(words) * 0.6: return False  # Menu Item Lists Like This
    return True

def link_ratio(p, h=""):
    """Share of visible words that are link text pointing to OTHER websites (link farms, directories).
    Links to the website's own posts are not counted: a blog index is not a link farm."""
    out = sum(n for a, n in p.link_counts.items() if a.startswith(("http://", "https://", "//")) and (not h or key(a if "//" != a[:2] else "https:" + a) != key(h))
              and not any(f in a.lower() for f in FRIENDLY_LINKS))
    return out / max(1, len(p.words))

def playful(p, html, title="", h=""):
    """A game, web toy or interactive art piece: real play happens in a canvas / audio / script, not in text."""
    text = " ".join([clean(p.title), title, p.meta.get("description", ""), p.meta.get("og:description", "")] + p.heads[:10] + p.words[:120])
    word_hits = len(PLAY_WORDS.findall(text))
    tech = bool(PLAY_HTML.search((html or "")[:400_000]))
    retro_host = bool(re.search(r"(neocities\.org|nekoweb\.org)$", h or ""))
    return (tech and word_hits >= 1) or (retro_host and word_hits >= 2)

# ---------------------------------------------------------------- AI slop shield
AI_SLOP_PHRASES = [
    r"in today'?s (fast[- ]paced|rapidly changing|ever[- ]evolving) digital (world|landscape|era|age)",
    r"in this (fast[- ]paced|rapidly evolving) digital (era|landscape|world)",
    r"\bdelv(e|ing|es) (deep(ly)? )?into\b",
    r"\ba testament to (the|how|its)\b",
    r"\bstands? as a testament to\b",
    r"\bit'?s (crucial|imperative|vital|essential) to (remember|understand|note|recognize) that\b",
    r"\bnavigat(e|ing) the (complexities|nuances) of\b",
    r"\bunlock(ing)? the (full )?potential of\b",
    r"\bharness(ing)? the power of\b",
    r"\brevolutioniz(e|ing) the way we\b",
    r"\bgame[- ]changer for\b",
    r"\bwhether you'?re a seasoned [a-z]+ or a (curious )?beginner\b",
    r"\bin conclusion,?( it is clear that| whether you'?re looking to)\b",
    r"\bas an ai language model\b",
    r"\bgenerated (by|with) (chatgpt|ai|claude|openai)\b",
    r"\bthis (article|post|page) was (written|generated) (using|by) ai\b",
]
AI_SLOP_RE = re.compile("|".join(AI_SLOP_PHRASES), re.I)

def ai_slop_reason(p, html="", title="", h=""):
    """Detects programmatic synthetic AI content farms while protecting creative coding, games, and indie personal sites."""
    if playful(p, html, title, h):
        return ""
    if re.search(r"(neocities\.org|nekoweb\.org)$", h or ""):
        return ""
    text = " ".join([clean(p.title), title, p.meta.get("description", ""), p.meta.get("og:description", "")] + p.heads[:8] + p.words[:800]).lower()
    if any(m in text for m in ["as an ai language model", "generated by chatgpt", "generated with chatgpt", "this article was generated using ai"]):
        return "ai disclosure"
    hits = len(list(AI_SLOP_RE.finditer(text)))
    if hits >= 2:
        return "ai slop"
    return ""

def junk_reason(p, html, title="", h=""):
    """Why a page is a dead end / junk, or "" when it looks like a real human website."""
    low_html = (html or "")[:300_000].lower()
    visible = " ".join(p.words); vlow = visible.lower()
    ptitle = clean(p.title).lower()
    first = " ".join(p.words[:150]).lower()
    heads = " ".join([ptitle] + [x.lower() for x in p.heads])
    B2B_CONSULTING = [
    "clients have included", "clients include", "consulting services",
    "available for contracting", "available for consulting", "contact our sales team",
    "request an enterprise demo", "b2b software", "schedule a demo",
    "staff-level engineer available for", "hire our agency", "our consulting practice"]  
    slop = ai_slop_reason(p, html, title, h)
    if slop: return slop
    if any(w in vlow[:8000] for w in B2B_CONSULTING): return "corporate consulting"   
    if any(w in ptitle or w in first for w in CHALLENGE) or re.search(r"cf-turnstile|challenge-platform|cf_chl_", low_html): return "bot challenge"
    if any(w in ptitle or w in vlow[:6000] or w in low_html[:20000] for w in PARKED): return "parked"
    if any(w in ptitle or w in vlow[:6000] for w in TEMPLATE) or any(heads.startswith(w) or (" " + w) in (" " + ptitle) for w in TEMPLATE_HEAD):
        return "starter template"
    desc = " ".join([p.meta.get("description", ""), p.meta.get("og:description", "")]).lower()
    if any(w in first or w in desc for w in COOKIE): return "cookie wall"
    if any(w in first or w in ptitle for w in LOGIN) or (p.passwords and len(p.words) < 400): return "login gate"
    play = playful(p, html, title, h)
    if play:
        if len(p.words) < PLAY_MIN_WORDS: return "too few words"
        if link_ratio(p, h) > MAX_LINK_RATIO: return "link farm"
        return ""
    if p.content_chars < MIN_CONTENT_CHARS and (len(p.words) < 40 or re.search(r'<div[^>]+id=["\']?(app|root|__next|__nuxt|svelte)["\' >]', low_html)):
        return "empty javascript shell"
    if len(p.words) < MIN_WORDS: return "too few words"
    if p.content_chars < MIN_CONTENT_CHARS: return "empty javascript shell"
    if link_ratio(p, h) > MAX_LINK_RATIO: return "link farm"
    return ""

def play_category(title, desc, heads, body, h):
    """Category for a game / toy / interactive art site: always Games, Art or Retro."""
    cat, conf, tags, score = _categorize(title, desc, heads, body, h)
    if cat in PLAY_CATS and score >= 3: return cat, max(conf, 0.6), tags
    t = " ".join([title, desc] + list(heads)).lower() + " " + h
    if re.search(r"game|play|puzzle|arcade|maze|level|score", t): return "Games", 0.6, tags
    if re.search(r"retro|90s|8-bit|ascii|geocities|webring|guestbook|shrine|neocities|nekoweb", t): return "Retro", 0.6, tags
    return "Art", 0.6, tags

def play_description(d):
    """Interactive sites often have short blurbs: a real capitalised sentence of 4+ words is enough."""
    d = (d or "").strip()
    return len(d) >= 20 and d[0].isupper() and len(d.split()) >= 4 and not SELF_REF.search(d) and not any(w in d.lower() for w in COOKIE + LOGIN + TEMPLATE)

def strict_category(title, desc, heads, body, h):
    """(category, confidence, tags) only when one category clearly wins, else None. Never "Random"."""
    cat, conf, tags, score = _categorize(title, desc, heads, body, h)
    if cat == "Random" or score < CAT_MIN_SCORE or conf < CAT_MIN_CONF: return None
    return cat, conf, tags

def priority(u):
    """Higher = check first. Indie platforms and personal domains beat everything else."""
    h = host(u)
    if INDIE.search(h): return 3
    if h.count(".") == 1 and not re.search(r"\.(com|net|biz|info|shop|store|online|site|xyz|top|club)$", h): return 2  # personal-style domains (.me, .dev, .page, country TLDs...)
    if h.count(".") == 1: return 1
    return 0

def flipped(p):
    """Old personal site taken over by casino / betting / crypto / adult spam?"""
    text = (clean(p.title) + " " + " ".join(p.heads) + " " + " ".join(p.words[:800])).lower()
    hits = sum(len(re.findall(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text)) for w in FLIP)
    return hits >= 3

def corporate_redirect(url, final):
    a, b = host(url), host(final)
    return bool(b) and a != b and any(b == c or b.endswith("." + c) for c in CORPORATE)

# ---------------------------------------------------------------- categories
# "~word" = ambiguous word: only counted in the name, description and headings, never body text.
CATS = {
 "Developer": ["programming","programmer","developer","developers","software engineer","software engineering","source code",
               "open source","open-source","compiler","framework","sdk","command line","command-line","javascript","typescript",
               "python","rust","golang","haskell","lisp","kotlin","database","devops","kubernetes","docker","web development",
               "debugger","coding","~api","~code","~git","~cli","~terminal","~linux","~repository","~backend","~frontend"],
 "Games": ["video game","video games","indie game","play online","puzzle game","arcade","multiplayer","roguelike","high score",
           "board game","chess","crossword","sudoku","speedrun","itch.io","gameplay","~game","~games","~puzzle","~play","~level"],
 "Art": ["artist","illustration","illustrator","painting","drawing","gallery","photography","photographer","design studio",
         "typography","album","musician","poetry","poems","animation","sketchbook","generative art","exhibition","artwork",
         "~art","~music","~band","~design","~portfolio","~comics"],
 "Retro": ["retro","90s","1990s","geocities","old web","ascii art","vintage","nostalgia","8-bit","pixel art","web 1.0","neocities",
           "webring","guestbook","amiga","commodore","ms-dos","floppy","classic computing","small web","~dos","~crt"],
 "Education": ["learn","learning","online course","tutorial","tutorials","lesson","lessons","beginner","beginners","teach","teaching",
               "university","students","curriculum","how to","introduction to","handbook","textbook","academy","literacy","children's books","reading program","~course","~school","~guide","~books"],
 "Science": ["science","scientific","physics","astronomy","astrophysics","nasa","mathematics","biology","chemistry","research",
             "experiment","climate","geology","quantum","telescope","neuroscience","ecology","~math","~space","~planet","~paper"],
 "Business": ["business","startup","pricing","customers","saas","enterprise","marketing","sales team","invoice","invoicing",
              "finance","investors","agency","consulting","ecommerce","e-commerce","buy now","our clients","b2b","free trial",
              "book a demo","~company","~shop","~store","~team"],
 "Technology": ["technology","hardware","electronics","gadget","gadgets","robotics","3d printing","arduino","raspberry pi",
                "artificial intelligence","machine learning","llm","cybersecurity","malware","semiconductor","gpu","cloud computing",
                "engineering","maker","~tech","~ai","~robot","~security","~chip","~battery","~cloud"],
 "News": ["news","breaking news","latest news","headlines","journalism","journalist","newsroom","reporting","editorial",
          "politics","magazine","~daily","~weekly","~stories"],
 "Communities": ["forum","forums","community","club","members","join us","discussion","meetup","mailing list","fan site",
                 "society","collective","volunteers","~discord","~group","~chat","~board"],
 "Personal": ["my name is","about me","personal website","personal site","personal blog","essays","journal","diary","i write",
              "i'm a","i am a","i'm an","i am an","my blog","writing about","digital garden","newsletter","weblog","homepage of",
              "hi, i'm","hello, i'm","hey, i'm","i'm ","welcome to my","my notes","my projects","i collect","i make","i build",
              "~blog","~notes","~thoughts","~posts","~writing"],
 "Tools": ["online tool","generator","converter","calculator","free app","utility","browser extension","plugin","productivity",
           "template","templates","checker","viewer","dashboard","tracker","planner","timer","in your browser","app for",
           "mac app","macos app","windows app","screenshot tool","pdf","~tool","~tools","~editor","~app","~builder","~windows"],
}
DOMAIN_HINTS = [(r"\.edu$|\.ac\.[a-z]+$", "Education", 6), (r"neocities\.org$|tripod|angelfire", "Retro", 6),
                (r"itch\.io$", "Games", 6), (r"\.art$", "Art", 4), (r"\.news$", "News", 4),
                (r"bearblog\.dev$|\.blog$|wordpress\.com$|blogspot\.", "Personal", 5), (r"\.tools?$", "Tools", 3)]
_PATS = {c: [(re.compile(r"(?<![a-z0-9])" + re.escape(w.lstrip("~")) + r"(?:s|es)?(?![a-z0-9])"), w.startswith("~"), " " in w) for w in ws]
         for c, ws in CATS.items()}

def categorize(title, desc, heads, body, h):
    """Score only human-visible text, weighting the name and description far above body text."""
    return _categorize(title, desc, heads, body, h)[:3]

def _categorize(title, desc, heads, body, h):
    zones = [(title.lower(), 5, False), (desc.lower(), 4, False), (" ".join(heads).lower(), 2, False), (body.lower()[:4000], 1, True)]
    scores = {c: 0.0 for c in CATS}
    for c, pats in _PATS.items():
        for pat, weak, phrase in pats:
            for text, weight, is_body in zones:
                if weak and is_body: continue
                n = len(pat.findall(text))
                if n: scores[c] += weight * min(n, 2 if is_body else 3) * (1.5 if phrase else 1) * (0.8 if weak else 1)
    for pat, c, bonus in DOMAIN_HINTS:
        if re.search(pat, h): scores[c] += bonus
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    (top, s1), (second, s2) = ranked[0], ranked[1]
    confidence = round(s1 / (s1 + s2), 2) if s1 else 0
    if s1 < 3: return "Random", confidence, [], s1
    tags = [c for c, s in ranked[1:4] if s >= max(4, s1 * 0.5)]
    return top, confidence, tags, s1

# ---------------------------------------------------------------- verification
# ---------------------------------------------------------------- vibe check + tech tags
# Tech tags come from the raw page source (that is where the tools leave their fingerprints);
# vibes come only from visible words, the archive year and page size - never from code.
TECH = [("WordPress", r"wp-content/|wp-includes/|generator\" content=\"wordpress"), ("Next.js", r"__next_data__|/_next/static"),
        ("Nuxt", r"__nuxt__|/_nuxt/"), ("Gatsby", r"___gatsby|generator\" content=\"gatsby"), ("Astro", r"astro-island|generator\" content=\"astro"),
        ("Hugo", r"generator\" content=\"hugo"), ("Jekyll", r"generator\" content=\"jekyll"), ("Eleventy", r"generator\" content=\"eleventy"),
        ("Ghost", r"generator\" content=\"ghost|ghost-portal"), ("Squarespace", r"squarespace\.com|static1\.squarespace"),
        ("Wix", r"wixstatic\.com|x-wix"), ("Shopify", r"cdn\.shopify\.com"), ("Webflow", r"webflow\.(js|com)|data-wf-page"),
        ("Svelte", r"svelte-[a-z0-9]{5,}|__sveltekit"), ("React", r"data-reactroot|react-dom|_reactlistening"),
        ("Vue", r"data-v-[a-f0-9]{6,}|vue(\.min)?\.js"), ("jQuery", r"jquery(\.min)?\.js|jquery-\d"),
        ("Bootstrap", r"bootstrap(\.min)?\.(css|js)"), ("Tailwind", r"tailwindcss|class=\"[^\"]*\b(?:flex|grid) [^\"]*\b(?:px|py|mx|my)-\d")]
BUILDERS = {"WordPress", "Next.js", "Nuxt", "Gatsby", "Astro", "Hugo", "Jekyll", "Eleventy", "Ghost", "Squarespace", "Wix", "Shopify", "Webflow", "Svelte", "React", "Vue"}
def tech_tags(html, h=""):
    low = (html or "")[:400_000].lower(); out = [n for n, rx in TECH if re.search(rx, low)]
    if h.endswith("neocities.org"): out.append("Neocities")
    if h.endswith("github.io"): out.append("GitHub Pages")
    if not set(out) & BUILDERS: out.append("Hand-coded")
    if "<script" not in low: out.append("No JavaScript")
    return out[:6]

VIBE_WORDS = {"cozy": ["cozy", "cosy", "garden", "tea", "knit", "baking", "recipe", "my cat", "journal", "diary", "comfort", "homemade"],
              "playful": ["game", "play", "toy", "puzzle", "fun", "interactive", "silly", "doodle", "arcade", "quiz"],
              "calm": ["calm", "quiet", "slow", "peaceful", "meditation", "ambient", "relax", "nature", "breathe", "mindful"],
              "weird": ["weird", "strange", "odd", "absurd", "bizarre", "surreal", "curious", "oddity", "eerie", "mystery"],
              "nerdy": ["algorithm", "physics", "math", "theorem", "compiler", "linux", "electronics", "astronomy", "data", "research"],
              "artsy": ["art", "illustration", "painting", "poetry", "photography", "zine", "sketch", "gallery", "music", "design"]}
def vibes(title, desc, body, words, first_seen=0, html="", tech=()):
    text = " " + " ".join([title, title, desc, desc, body[:6000]]).lower() + " "
    score = {v: sum(len(re.findall(r"(?<![a-z])" + w + r"(?![a-z])", text)) for w in ws) for v, ws in VIBE_WORDS.items()}
    out = [v for v, n in sorted(score.items(), key=lambda x: -x[1]) if n >= 2][:2]
    low = (html or "")[:200_000].lower()
    if (first_seen and int(first_seen) <= 2005) or re.search(r"<(marquee|blink|font |center>)|<table[^>]+bgcolor", low): out.append("retro")
    if "Hand-coded" in tech and words < 2500: out.append("handmade")
    if words >= 2500: out.append("deep read")
    elif words < 300: out.append("minimal")
    return out[:4]

# ---------------------------------------------------------------- 16-dimensional taste vector
VECTOR_DIMS = ["tool", "play", "audio", "visual_art", "knowledge", "personal", "interactivity", "session_length",
               "visual_density", "retro", "quirky", "mobile", "embeddable", "handmade", "audio_required", "evergreen"]

def _hits(text, words): return sum(1 for w in words if w in text)

def compute_vector(title="", desc="", cat="", vibes=(), tech=(), url="", words=100, embed=True, html=""):
    """Continuous 16-number fingerprint (each 0.0-1.0) used by the in-browser recommender."""
    v_ = " ".join(vibes or []).lower(); t_ = " ".join(tech or []).lower(); h = (html or "")[:200000].lower()
    text = f"{title} {desc} {cat} {v_} {t_}".lower(); u = (url or "").lower()
    indie = bool(re.search(r"neocities\.org|nekoweb\.org|tilde|github\.io|bearblog|omg\.lol", u))
    canvas = "canvas" in t_ or "<canvas" in h or "webgl" in h
    audio_tech = "audio" in t_ or "<audio" in h or "audiocontext" in h
    d = [0.0] * 16
    d[0] = 0.1 + 0.5 * (cat in ("Tools", "Developer")) + 0.12 * _hits(text, ["tool", "generator", "converter", "calculator", "editor", "search", "maker", "utility", "download", "app"])
    d[1] = 0.05 + 0.6 * (cat == "Games") + 0.12 * _hits(text, ["game", "play", "arcade", "puzzle", "rpg", "simulator", "toy", "interactive", "maze"]) + 0.25 * canvas
    d[2] = 0.15 * _hits(text, ["music", "synth", "sound", "audio", "radio", "song", "piano", "beat"]) + 0.3 * audio_tech
    d[3] = 0.05 + 0.55 * (cat == "Art") + 0.1 * _hits(text, ["art", "pixel", "ascii", "ansi", "visual", "generative", "drawing", "gallery", "illustration", "shader", "design"]) + 0.15 * canvas
    d[4] = 0.1 + 0.5 * (cat in ("Writing", "Science", "Education", "News", "Developer")) + 0.1 * _hits(text, ["essay", "research", "guide", "history", "archive", "wiki", "newsletter", "zine", "learn", "book", "document"]) + 0.2 * (words > 600)
    d[5] = 0.1 + 0.55 * (cat == "Personal") + 0.2 * indie + 0.1 * _hits(text, ["personal", "blog", "digital garden", "webmaster", "my corner", "about me", "homepage"])
    d[6] = 0.1 + 0.35 * canvas + 0.1 * _hits(text, ["interactive", "click", "drag", "type", "build", "play"]) + 0.2 * (cat in ("Games", "Tools"))
    d[7] = min(1.0, 0.2 + words / 3000) + 0.3 * (cat in ("Games", "Writing"))
    d[8] = 0.5 - 0.3 * (words > 1500 or "minimal" in text) + 0.35 * bool(_hits(text, ["pixel", "retro", "gif", "colorful", "flashing", "glitter"]))
    d[9] = 0.05 + 0.5 * (cat == "Retro") + 0.12 * _hits(text, ["retro", "vintage", "90s", "y2k", "webring", "myspace", "ansi", "ascii", "old web", "geocities"]) + 0.1 * indie
    d[10] = 0.15 + 0.15 * _hits(text, ["quirky", "silly", "strange", "weird", "obscure", "curious", "fun", "odd", "surreal", "absurd"]) + 0.15 * (cat in ("Games", "Art"))
    d[11] = 0.2 if re.search(r"not (optimi[sz]ed|made) for (mobile|phone)|desktop only|best viewed on (a )?desktop", text + h) else 0.85
    d[12] = 1.0 if embed else 0.0
    d[13] = 0.4 + 0.35 * indie + 0.15 * (not t_ or "vanilla" in t_ or "html" in t_) + 0.1 * ("handmade" in text)
    d[14] = 0.8 if re.search(r"music player|turn (your )?sound on|headphones|listen", text) else (0.3 if audio_tech else 0.0)
    d[15] = 0.85 if cat in ("Tools", "Games", "Art", "Retro", "Education") else (0.45 if cat == "News" else 0.7)
    return [round(max(0.0, min(1.0, x)), 3) for x in d]

def deep_check_subpages(base_url, anchors):
    """Scan 2-3 internal subpages (about, blog, rants, diary) for profanity or vulgarity."""
    h = host(base_url)
    targets = []
    for a, t in anchors:
        if not a or not a.startswith("http"): continue
        if host(a) == h and a.rstrip("/") != base_url.rstrip("/"):
            path = urllib.parse.urlparse(a).path.lower()
            if any(term in path for term in ("about", "blog", "rant", "journal", "post", "diary", "story", "me")):
                targets.append(a)
    targets = list(dict.fromkeys(targets))[:3]
    for sub in targets:
        try:
            status, final_sub, sub_body, _ = get(sub, timeout=5, limit=500_000)
            if status < 400 and sub_body:
                sub_p = Parser(sub_body)
                sub_vis = " ".join(sub_p.words[:1500])
                if unsafe_text(sub_p.title, sub_vis):
                    return True
        except Exception:
            pass
    return False


def parse_feed_date(date_str):
    if not date_str: return None
    try:
        parsed_tuple = email.utils.parsedate_to_datetime(date_str)
        return parsed_tuple.date().isoformat()
    except Exception:
        pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m: return m.group(1)
    return None

def find_feed_link(base_url, html):
    patterns = [
        r'<link[^>]+rel=[\"\']alternate[\"\'][^>]+type=[\"\']application/(?:rss\+xml|atom\+xml|xml|feed\+json)[\"\'][^>]+href=[\"\']([^\"\']+)[\"\']',
        r'<link[^>]+type=[\"\']application/(?:rss\+xml|atom\+xml|xml|feed\+json)[\"\'][^>]+rel=[\"\']alternate[\"\'][^>]+href=[\"\']([^\"\']+)[\"\']'
    ]
    for p in patterns:
        m = re.search(p, html, re.I)
        if m: return urllib.parse.urljoin(base_url, m.group(1))
    return None

def detect_feed_and_freshness(base_url, html=""):
    feed_url = find_feed_link(base_url, html)
    if not feed_url:
        for cand in ["/feed", "/rss.xml", "/atom.xml", "/index.xml", "/feed.xml"]:
            try:
                cand_url = urllib.parse.urljoin(base_url, cand)
                req = urllib.request.Request(cand_url, headers=UA)
                with urllib.request.urlopen(req, timeout=3) as r:
                    if r.status == 200:
                        sample = r.read(600).decode("utf-8", errors="ignore")
                        if any(x in sample for x in ["<rss", "<feed", "<?xml"]):
                            feed_url = cand_url
                            break
            except Exception:
                pass
    if not feed_url:
        return None, None
    try:
        freq = urllib.request.Request(feed_url, headers=UA)
        with urllib.request.urlopen(freq, timeout=4) as fr:
            ftext = fr.read(250_000).decode("utf-8", errors="ignore")
        dates = re.findall(r"<(?:pubDate|updated|published)>([^<]+)</(?:pubDate|updated|published)>", ftext, re.I)
        latest_date = None
        for d in dates:
            iso = parse_feed_date(d.strip())
            if iso:
                if not latest_date or iso > latest_date:
                    latest_date = iso
        return feed_url, latest_date
    except Exception:
        return feed_url, None

def verify(url, strict=True):
    """Run every check. Returns details for a working website, or None with a reason.
    strict=True (new candidates): every quality gate must pass. strict=False (re-checks of stored
    websites): only "is it still alive and still the same website" checks."""
    try: st, final, html, ctype, secs, headers = get(url)
    except Exception: return None, "unreachable"
    if st != 200: return None, f"http {st}"
    if "html" not in ctype.lower(): return None, "not html"
    if secs > 8: return None, "slow"
    p = Page()
    try: p.feed(html)
    except Exception: pass
    h = host(final) or host(url)
    if corporate_redirect(url, final): return None, "corporate redirect"
    if not allowed("https://" + h): return None, "big platform"
    title = best_title(p, h)
    visible = " ".join(p.words)
    low = (title + " " + clean(p.title) + " " + visible[:4000]).lower()
    if any(w in low for w in PARKED): return None, "parked"
    if any(w in clean(p.title).lower() for w in BLOCKED): return None, "blocked"
    if flipped(p): return None, "flipped"
    if any(re.search(r"(?<![a-z])" + w + r"(?![a-z])", low) for w in UNSAFE): return None, "unsafe"
    if unsafe_text(title, clean(p.title), " ".join(p.heads[:8]), visible[:6000]): return None, "unsafe"
    if strict:
        why = junk_reason(p, html, title, h)
        if why: return None, why
        if lazy_title(page_title(p, h), h): return None, "lazy title"
    elif len(p.words) < 40: return None, "too little content"
    desc = best_description(p, title)
    play = strict and playful(p, html, title, h)
    if strict and not (good_description(desc) or (play and play_description(desc))): return None, "weak description"
    if unsafe_text(desc): return None, "unsafe"
    if deep_check_subpages(final, p.anchors): return None, "unsafe subpage"
    body = " ".join(p.heads + p.paras)
    if strict:
        sc = strict_category(title, desc, p.heads, body, h)
        if play and (not sc or sc[0] not in PLAY_CATS): sc = play_category(title, desc, p.heads, body, h)
        if not sc: return None, "unsure category"
        cat, conf, tags = sc
    else: cat, conf, tags = categorize(title, desc, p.heads, body, h)
    tech = tech_tags(html, h); vibe = vibes(title, desc, body, len(p.words), 0, html, tech)
    lang = p.lang or (p.meta.get("og:locale", "")[:2].lower()) or "?"
    alias = {h}
    for extra in (p.canonical, p.meta.get("og:url", "")):
        n = norm(urllib.parse.urljoin(final, extra)) if extra else None
        if n and allowed(n): alias.add(key(n))
    anchors = [(urllib.parse.urljoin(final, a), t) for a, t in p.anchors if a and not a.startswith(("#", "mailto:", "javascript:"))]
    feed_url, last_tended = detect_feed_and_freshness(final, html)
    vec = compute_vector(title, desc, cat, vibe, tech, final, len(p.words), embeddable(headers), html)
    return {"vector": vec, "url": ("https://" if final.startswith("https") else "http://") + h, "title": title, "description": desc,
            "category": cat, "confidence": conf, "tags": tags, "tech": tech, "vibes": vibe, "lang": lang, "load_time": secs,
            "https": final.startswith("https"), "words": len(p.words), "embed": embeddable(headers),
            "aliases": sorted(alias), "fingerprint": fingerprint(title, desc),
            "feed_url": feed_url, "last_tended": last_tended, "links": [a for a, _ in anchors if a.startswith("http")][:120], "anchors": anchors}, "ok"

def safe_verify(u, strict=True):
    try: return verify(u, strict)
    except Exception: return None, "error"

def fingerprint(title, desc):
    """Same name + same description on two domains = the same website (mirrors, renamed domains)."""
    if len(desc) < 30: return ""
    return re.sub(r"[^a-z0-9]", "", (title + "|" + desc[:80]).lower())

# ---------------------------------------------------------------- candidate sources
def sources(known):
    found = {}
    def add(u, src):
        n = norm(u)
        if n and allowed(n) and key(n) not in known and key(n) not in found: found[key(n)] = (n, src)
    for q in ["show_hn", "front_page", "story"]:
        try:
            b = get(f"https://hn.algolia.com/api/v1/search_by_date?tags={q}&hitsPerPage=10", limit=3_000_000)[2]
            for x in json.loads(b)["hits"]: add(x.get("url"), "hacker news")
        except Exception as e: print("hn", e)
    try:
        for x in json.loads(get("https://lobste.rs/newest.json", limit=3_000_000)[2]): add(x.get("url"), "lobsters")
    except Exception as e: print("lobsters", e)
    # Tools, games and creative experiments (Target: 90% of discoveries)
    for url, src in [("https://tiny-helpers.dev/", "tiny helpers"), ("https://js13kgames.com/2024/games", "js13k"),
                     ("https://experiments.withgoogle.com/collection/chrome", "chrome experiments"),
                     ("https://github.com/sindresorhus/awesome/raw/main/readme.md", "awesome lists"),
                     ("https://theuselessweb.com/", "useless web"), ("https://pico-8-edu.com/", "pico-8"),
                     ("https://itch.io/games/free/web", "itch.io web"),
                     ("https://indieweb.org/IndieWeb_Examples", "indieweb")]:
        try:
            body = get(url, limit=3_000_000)[2]
            for m in re.findall(r"https?://[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s\"'<>)]*)?", body)[:150]: add(m, src)
        except Exception as e: print(src, e)
    # Fun indie web: Neocities, Nekoweb, tilde towns, Marginalia random, ooh.directory
    for url, pat, src in [
        ("https://neocities.org/browse?sort_by=random", r'href="(https?://[a-z0-9-]+\.neocities\.org)/?"', "neocities"),
        ("https://neocities.org/browse?sort_by=last_updated", r'href="(https?://[a-z0-9-]+\.neocities\.org)/?"', "neocities"),
        ("https://nekoweb.org/explore?sort=lastupd", r'href="(https?://[a-z0-9-]+\.nekoweb\.org)/?"', "nekoweb"),
        ("https://nekoweb.org/explore?sort=followers", r'href="(https?://[a-z0-9-]+\.nekoweb\.org)/?"', "nekoweb"),
        ("https://tildeverse.org/members/", r'href="(https?://[^"\s]+)"', "tildeverse"),
        ("https://search.marginalia.nu/explore/random", r'href="(https?://[^"\s]+)"', "marginalia"),
    ]:
        try:
            b = get(url, limit=2_000_000)[2]
            for u in re.findall(pat, b)[:60]: add(u, src)
        except Exception as e: print(src, e)
    for _ in range(20):  # Wiby's "surprise me" redirects to a random small-web site
        try: add(get("https://wiby.me/surprise/", timeout=6, limit=2000)[1], "wiby")
        except Exception: pass
    # bearblog discovery removed (hard blog quota in effect)
    # Legacy GitHub issues submissions retired (now handled via Supabase pending_submissions)
    try:  # anonymous visitor suggestions buffered in Supabase (flushed every run)
        sb = os.environ.get("SUPABASE_URL", "").rstrip("/"); key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if sb and key:
            hd = {"apikey": key, "Authorization": "Bearer " + key}
            rows = json.loads(urllib.request.urlopen(urllib.request.Request(sb + "/rest/v1/pending_submissions?select=id,submitted_url&order=id&limit=500", headers=hd), timeout=20).read())
            for row in rows:
                for u in re.findall(r"https?://[^\s)>\]\"']+", str(row.get("submitted_url") or ""))[:1]: add(u, "submission")
            if rows:
                urllib.request.urlopen(urllib.request.Request(sb + "/rest/v1/pending_submissions?id=lte.%d" % max(r["id"] for r in rows), headers=hd, method="DELETE"), timeout=20)
            print("Cloud suggestions:", len(rows))
    except Exception as e: print("cloud suggestions", e)
    return found

LINKPAGE = re.compile(r"\b(links|blogroll|friends|webring|cool sites|neighbou?rs|bookmarks|recommend|elsewhere|other sites|link ?list|"
                      r"about|now|favou?rites|ideas|resources)\b", re.I)
LINKPATH = re.compile(r"/(about|blogroll|links|favou?rites|now|ideas|resources|friends|webring|bookmarks)(/|\.html?)?$", re.I)

def link_pages(r):
    """Same-website pages that usually list other websites (blogrolls, link pages, webrings)."""
    h = host(r["url"])
    out = []
    for a, t in r.get("anchors", []):
        path = urllib.parse.urlparse(a).path
        if host(a) == h and (LINKPATH.search(path) or LINKPAGE.fullmatch((t or "").strip())) and a.rstrip("/") != r["url"].rstrip("/"):
            out.append(a)
    out.sort(key=lambda a: 0 if LINKPATH.search(urllib.parse.urlparse(a).path) else 1)
    return list(dict.fromkeys(out))[:3]

def harvest(url):
    try:
        st, final, html, ctype, _, _ = get(url, timeout=8)
        if st != 200 or "html" not in ctype.lower(): return []
        return re.findall(r'href=["\'](https?://[^"\'#\s]+)', html)[:200]
    except Exception: return []

def malware_hosts():
    """Public URLhaus host list (abuse.ch). Free, no key. Empty set if unavailable."""
    try:
        txt = get("https://urlhaus.abuse.ch/downloads/hostfile/", timeout=20, limit=20_000_000)[2]
        return {canon_host(l.split()[-1]) for l in txt.splitlines() if l and not l.startswith("#") and len(l.split()) >= 2}
    except Exception as e: print("urlhaus", e); return set()

def first_archive_year(url):
    try:
        q = urllib.parse.urlencode({"url": host(url), "output": "json", "filter": "statuscode:200", "limit": 1, "fl": "timestamp"})
        rows = json.loads(get("https://web.archive.org/cdx/search/cdx?" + q, timeout=12)[2])
        return int(rows[1][0][:4]) if len(rows) > 1 else None
    except Exception:
        return None

# ---------------------------------------------------------------- database rules
def better(s, o):
    """Which of two copies of the same website to keep: hand-edited, then alive, then oldest."""
    rank = lambda x: (bool(x.get("locked")), x.get("status") != "dead", x.get("review") == "verified", -int((x.get("added") or "9999").replace("-", "") or 0))
    return rank(s) > rank(o)

def dedupe(sites):
    """Keep one entry per domain (strict normalization) and per identical name + description."""
    best = {}
    for s in sites:
        k = key(s["url"]); o = best.get(k)
        if not o or better(s, o): best[k] = s
    out = {}
    for s in best.values():
        fp = s.get("fingerprint") or fingerprint(s.get("title", ""), s.get("description", ""))
        k = fp or key(s["url"]); o = out.get(k)
        if not o or better(s, o): out[k] = s
    return list(out.values())

def apply(site, r):
    """Copy fresh details onto a stored site unless the admin locked it."""
    for f in ("lang", "load_time", "https", "words", "embed"): site[f] = r[f]
    site["safety_checked"] = TODAY
    if "tech" in r: site["tech"] = r["tech"]
    if "vector" in r: site["vector"] = r["vector"]
    if not site.get("locked"):
        for f in ("title", "description", "category", "confidence", "tags", "fingerprint"): site[f] = r[f]
        if "vibes" in r:
            v = [x for x in r["vibes"] if x != "retro"]
            if site.get("first_seen") and int(site["first_seen"]) <= 2005 or "retro" in r["vibes"]: v.append("retro")
            site["vibes"] = v[:4]

def days_since(d):
    try: return (datetime.date.today() - datetime.date.fromisoformat(d)).days
    except Exception: return 9999

def count(log, why): log["rejected"][why] = log["rejected"].get(why, 0) + 1

def main():
    try:
        cfg_p = os.path.join(os.path.dirname(DB), "bot-config.json")
        if os.path.exists(cfg_p):
            cfg = json.load(open(cfg_p, "r", encoding="utf-8"))
            if cfg.get("paused", False):
                print("[BOT PAUSED] Crawler is paused in bot-config.json. Exiting.")
                return
            interval = cfg.get("interval_hours", 1)
            st_chk = json.load(open(STATS, "r", encoding="utf-8")) if os.path.exists(STATS) else {}
            last_run = st_chk.get("last_run")
            if last_run and interval > 1:
                last_dt = datetime.datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                diff_h = (now_dt - last_dt).total_seconds() / 3600.0
                if diff_h < (interval - 0.1):
                    print(f"[BOT INTERVAL] Run skipped: {diff_h:.1f}h elapsed < {interval}h interval.")
                    return
    except Exception as e:
        print("[BOT CONFIG WARNING]", e)
    db = json.load(open(DB)); st = json.load(open(STATS))
    log = {"started": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "rejected": {}}
    before = len(db["sites"]); sites = dedupe(db["sites"]); log["duplicates_removed"] = before - len(sites)
    known = {key(s["url"]) for s in sites} | {a for s in sites for a in s.get("aliases", [])}
    fps = {s.get("fingerprint") for s in sites if s.get("fingerprint")}
    beta = days_since(db.get("beta_start", TODAY)) < 10
    limit = 180 if beta else 140
    found = sources(known); log["sources"] = {}
    for _, src in found.values(): log["sources"][src] = log["sources"].get(src, 0) + 1
    cand = list(found.values()); random.shuffle(cand)

    # Deep crawl: outbound links + blogroll/link pages of random known websites
    alive = [s for s in sites if s.get("status") != "dead" and s.get("review") != "flagged"]
    seeds = random.sample(alive, min(25, len(alive)))
    with ThreadPoolExecutor(10) as ex: res = [r for r, _ in ex.map(lambda u: safe_verify(u, False), [s["url"] for s in seeds]) if r]
    pages = [p for r in res for p in link_pages(r)][:30]
    with ThreadPoolExecutor(8) as ex: extra = list(ex.map(harvest, pages))
    have = {key(c) for c, _ in cand}; deep = 0
    for r, links in [(r, r["links"]) for r in res] + [(None, l) for l in extra]:
        for l in links:
            n = norm(l)
            if n and allowed(n) and key(n) not in known and key(n) not in have:
                have.add(key(n)); deep += 1
                cand.append((n, "link from " + host(r["url"]) if r else "link page"))
    random.shuffle(cand); cand.sort(key=lambda c: -priority(c[0])); cand = cand[:limit]
    bad_hosts = malware_hosts()
    with ThreadPoolExecutor(12) as ex: results = list(ex.map(lambda c: safe_verify(c[0]) if key(c[0]) not in bad_hosts else (None, "malware list"), cand))
    added = 0
    ranked = sorted(zip(cand, results), key=lambda x: -(x[1][0]["confidence"] + priority(x[0][0]) / 10 if x[1][0] else -1))
    blog_added = 0
    for (u, src), (r, why) in ranked:
        if not r: count(log, why); continue
        if added >= MAX_NEW: count(log, "over run cap"); continue
        if any(a in known for a in r["aliases"]) or (r["fingerprint"] and r["fingerprint"] in fps) or key(r["url"]) in bad_hosts:
            count(log, "duplicate"); continue
        if BLOCKED_DOMAINS and (host(r["url"]) in BLOCKED_DOMAINS or key(r["url"]) in BLOCKED_DOMAINS):
            count(log, "blocked domain"); continue
        is_blog = r.get("category") in ("Writing", "Personal") or "blog" in r.get("vibes", [])
        if is_blog and blog_added >= 1:
            count(log, "blog quota exceeded"); continue
        if is_blog: blog_added += 1
        known.update(r["aliases"]); fps.add(r["fingerprint"]); added += 1
        s = {"url": r["url"], "source": src, "status": "ok", "review": "unreviewed", "added": TODAY, "checked": TODAY,
             "fails": 0, "aliases": r["aliases"]}
        apply(s, r); sites.append(s)

    # Recheck: everything older than 30 days first, then the oldest-checked
    old = sorted([s for s in sites if s.get("added") != TODAY], key=lambda s: s.get("checked", ""))
    stale = [s for s in old if days_since(s.get("checked", "")) >= STALE_DAYS]
    untagged = [s for s in old if "tech" not in s and s not in stale][:120]  # one-off catch-up: give older sites vibes/tech tags
    old = (stale + untagged + [s for s in old if s not in stale and s not in untagged])[:200 + len(untagged)]
    with ThreadPoolExecutor(12) as ex: chk = list(ex.map(lambda s: safe_verify(s["url"], False), old))
    died = 0; flagged = 0
    for s, (r, why) in zip(old, chk):
        s["checked"] = TODAY
        if r: s["fails"] = 0; apply(s, r); s["status"] = s["status"] if s.get("locked") else "ok"; continue
        s["fails"] = s.get("fails", 0) + 1; s["robot_note"] = f"{why} ({TODAY})"
        if why == "unsafe" and not s.get("locked"): s["review"] = "flagged"; s["flag_reason"] = "unsafe words found"; flagged += 1
        if s.get("locked"): continue  # hand-checked: report only, never change status
        if why in ("flipped", "corporate redirect"):  # domain taken over or redirected away: purge at once
            if s.get("status") != "dead": died += 1
            s["status"] = "dead"; s["review"] = "flagged"; flagged += 1
            s["flag_reason"] = "domain taken over by spam" if why == "flipped" else "now redirects to a big platform"
            continue  # hand-checked: report only, never change status
        if s["fails"] >= 3 and s.get("status") != "dead": died += 1
        s["status"] = "dead" if s["fails"] >= 3 else "warn"

    # Safety: malware list check on every website
    for s in sites:
        if bad_hosts and key(s["url"]) in bad_hosts and s.get("review") != "flagged" and not s.get("locked"):
            s["review"] = "flagged"; s["flag_reason"] = "listed on URLhaus malware list"; flagged += 1

    # Archive years: websites never looked up, or not found and last tried 14+ days ago
    alive = [s for s in sites if s.get("status") != "dead"]
    pending = sorted([s for s in alive if not s.get("first_seen") and days_since(s.get("archive_checked", "")) >= 14],
                     key=lambda s: s.get("archive_checked", ""))[:40]
    with ThreadPoolExecutor(4) as ex: years = list(ex.map(lambda s: first_archive_year(s["url"]), pending))
    for s, y in zip(pending, years):
        s["archive_checked"] = TODAY
        if y: s["first_seen"] = y

    db["sites"] = sites
    visible = [s for s in alive if s.get("review") != "flagged"]
    cats = {}
    for s in visible: cats[s["category"]] = cats.get(s["category"], 0) + 1
    log.update(candidates=len(cand), deep_links=deep, added=added, rechecked=len(old), stale_rechecked=min(len(stale), 80),
               newly_dead=died, flagged=flagged, malware_list=len(bad_hosts), archive_years=sum(1 for y in years if y))
    st.update(total=len(visible), dead=len(sites) - len(alive), flagged=sum(1 for s in sites if s.get("review") == "flagged"),
              runs=st.get("runs", 0) + 1, last_run=log["started"], found_last_run=added, beta=beta,
              candidates_checked=len(cand), categories=cats, bot_version=4)
    st["history"] = (st.get("history", []) + [{"date": TODAY, "added": added, "total": len(visible)}])[-240:]
    st["runs_log"] = ([log] + st.get("runs_log", []))[:30]
    json.dump(db, open(DB, "w"), indent=1, ensure_ascii=False); json.dump(st, open(STATS, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(log, indent=1))

if __name__ == "__main__": main()
