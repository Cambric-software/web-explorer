"""Website Explorer discovery robot (v3).
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
Websites edited by hand in the control room are "locked": the robot never changes their
name, description, category, review flag or status.
"""
import json, os, random, re, time, datetime, html as htmllib, urllib.request, urllib.parse
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

DB = "docs/data/sites.json"; STATS = "docs/data/stats.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; WebsiteExplorerBot/3.0; +https://cambric-software.github.io/web-explorer/)",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en;q=0.9,*;q=0.5"}
TODAY = datetime.date.today().isoformat()
STALE_DAYS = 30
BIG = {"google.com","youtube.com","youtu.be","facebook.com","twitter.com","x.com","instagram.com","github.com","reddit.com",
       "amazon.com","wikipedia.org","linkedin.com","tiktok.com","medium.com","apple.com","microsoft.com","t.co","bit.ly",
       "news.ycombinator.com","lobste.rs","docs.google.com","drive.google.com","sites.google.com","archive.org","arxiv.org",
       "nytimes.com","bbc.co.uk","bbc.com","theguardian.com","cnn.com","bloomberg.com","substack.com","imgur.com",
       "discord.gg","discord.com","t.me","whatsapp.com","pinterest.com","goo.gl","play.google.com","wiby.me","bearblog.dev",
       "web.archive.org","mastodon.social","bsky.app","threads.net","linktr.ee","patreon.com","ko-fi.com","buymeacoffee.com"}
BAD_TLDS = (".zip", ".mov", ".xyz.ru")
PARKED = ["domain for sale","buy this domain","this domain is for sale","domain is parked","parked free","parkingcrew",
          "sedoparking","account suspended","coming soon","under construction","website is under construction",
          "default web site page","welcome to nginx","apache2 ubuntu default page","it works!","index of /",
          "hugedomains","dan.com","afternic","godaddy.com/domains"]
BLOCKED = ["just a moment","attention required","access denied","verify you are human","enable javascript and cookies",
           "403 forbidden","404 not found","page not found","site not found","error 404","bad gateway","forbidden"]
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
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z0-9-]{2,}", h) or h.endswith(BAD_TLDS) or ".." in h: return None
    if re.fullmatch(r"[\d.]+", h): return None
    return "https://" + h

def allowed(u):
    h = host(u)
    return bool(h) and not any(h == b or h.endswith("." + b) and b not in ("bearblog.dev",) for b in BIG)

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
    def handle_starttag(s, tag, a):
        a = {k: (v or "") for k, v in a}
        if tag in s.VOID:
            if tag == "meta":
                k = (a.get("name") or a.get("property") or "").lower()
                if k and a.get("content") and k not in s.meta: s.meta[k] = a["content"]
            if tag == "link" and "canonical" in a.get("rel", "").lower() and not s.canonical: s.canonical = a.get("href", "")
            return
        if tag in s.SKIP: s._skip += 1
        if tag == "html": s.lang = a.get("lang", "")[:2].lower()
        if tag == "a":
            s._a = a.get("href", ""); s._atext = ""
            if s._a.startswith("http"): s.links.append(s._a)
        if tag in ("title", "h1", "h2", "p", "li") and not s._skip: s._stack.append(tag); s._buf = ""
    def handle_endtag(s, tag):
        if tag in s.SKIP and s._skip: s._skip -= 1
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
        if len(s.words) < 3000: s.words.extend(d.split())

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
           "loading...","react app","vite app","vite + react","coming soon","about","about me","default","landing page","app","start here","get started","hello","hello world","posts","articles","writing","notes","news"}
PLATFORM = {"substack","wordpress","wordpress.com","blogger","blogspot","medium","ghost","squarespace","wix","weebly",
            "notion","carrd","github pages","neocities","tumblr","bear blog","ʕ•ᴥ•ʔ bear blog","micro.blog","write.as",
            "hashnode","dev.to","linktree","shopify","webflow","framer","jekyll","hugo","next.js","gatsby"}
PREFIX = re.compile(r"^(welcome to|welcome|home page of|homepage of|home of|the official (web)?site of|official (web)?site of)\b\s*[:\-–—|,!]?\s*", re.I)
DOMAINLIKE = re.compile(r"(https?://)?(www\.)?[\w.-]+\.[a-z]{2,}/?")

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

def best_title(p, h):
    stem = re.sub(r"[^a-z0-9]", "", h.split(".")[0])
    def pick(raw):
        parts = [good_name(x) for x in re.split(SEP, clean(raw))]; parts = [x for x in parts if x]
        if not parts: return ""
        match = [x for x in parts if stem and len(stem) > 2 and stem in re.sub(r"[^a-z0-9]", "", x.lower())]
        if match: return min(match, key=len)
        if len(parts) == 1: return parts[0]
        return parts[-1] if len(parts[-1]) <= 30 and len(parts[-1]) < len(parts[0]) else parts[0]
    site = good_name(p.meta.get("og:site_name", ""))
    title = (site if site and len(site) <= 60 else "") or pick(p.title) or pick(p.meta.get("og:title", "")) \
        or pick(p.meta.get("twitter:title", "")) or next((good_name(x) for x in p.heads[:2] if good_name(x) and len(x) <= 60), "") \
        or pretty_domain(h)
    if len(title) > 70: title = title[:70].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    return title

BOILER = re.compile(r"cookie|javascript|enable js|your browser|skip to|sign in|log in|login|subscribe now|all rights reserved|"
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
    if s1 < 3: return "Random", confidence, []
    tags = [c for c, s in ranked[1:4] if s >= max(4, s1 * 0.5)]
    return top, confidence, tags

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

def verify(url):
    """Run every check. Returns details for a working website, or None with a reason."""
    try: st, final, html, ctype, secs, headers = get(url)
    except Exception: return None, "unreachable"
    if st != 200: return None, f"http {st}"
    if "html" not in ctype.lower(): return None, "not html"
    if secs > 8: return None, "slow"
    p = Page()
    try: p.feed(html)
    except Exception: pass
    h = host(final) or host(url)
    if not allowed("https://" + h): return None, "big platform"
    title = best_title(p, h)
    visible = " ".join(p.words)
    low = (title + " " + clean(p.title) + " " + visible[:4000]).lower()
    if any(w in low for w in PARKED): return None, "parked"
    if any(w in clean(p.title).lower() for w in BLOCKED): return None, "blocked"
    if any(re.search(r"(?<![a-z])" + w + r"(?![a-z])", low) for w in UNSAFE): return None, "unsafe"
    if len(p.words) < 40: return None, "too little content"
    desc = best_description(p, title)
    body = " ".join(p.heads + p.paras)
    cat, conf, tags = categorize(title, desc, p.heads, body, h)
    tech = tech_tags(html, h); vibe = vibes(title, desc, body, len(p.words), 0, html, tech)
    lang = p.lang or (p.meta.get("og:locale", "")[:2].lower()) or "?"
    alias = {h}
    for extra in (p.canonical, p.meta.get("og:url", "")):
        n = norm(urllib.parse.urljoin(final, extra)) if extra else None
        if n and allowed(n): alias.add(key(n))
    anchors = [(urllib.parse.urljoin(final, a), t) for a, t in p.anchors if a and not a.startswith(("#", "mailto:", "javascript:"))]
    return {"url": ("https://" if final.startswith("https") else "http://") + h, "title": title, "description": desc,
            "category": cat, "confidence": conf, "tags": tags, "tech": tech, "vibes": vibe, "lang": lang, "load_time": secs,
            "https": final.startswith("https"), "words": len(p.words), "embed": embeddable(headers),
            "aliases": sorted(alias), "fingerprint": fingerprint(title, desc),
            "links": [a for a, _ in anchors if a.startswith("http")][:120], "anchors": anchors}, "ok"

def safe_verify(u):
    try: return verify(u)
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
            b = get(f"https://hn.algolia.com/api/v1/search_by_date?tags={q}&hitsPerPage=100", limit=3_000_000)[2]
            for x in json.loads(b)["hits"]: add(x.get("url"), "hacker news")
        except Exception as e: print("hn", e)
    try:
        for x in json.loads(get("https://lobste.rs/newest.json", limit=3_000_000)[2]): add(x.get("url"), "lobsters")
    except Exception as e: print("lobsters", e)
    for _ in range(20):  # Wiby's "surprise me" redirects to a random small-web site
        try: add(get("https://wiby.me/surprise/", timeout=6, limit=2000)[1], "wiby")
        except Exception: pass
    try:
        b = get("https://bearblog.dev/discover/", limit=1_000_000)[2]
        for u in re.findall(r'href="(https?://[a-z0-9.-]+\.bearblog\.dev)/?"', b): add(u, "bear blog")
    except Exception as e: print("bear", e)
    try:  # visitor submissions: GitHub issues labelled "submit"
        repo = os.environ.get("GITHUB_REPOSITORY"); tok = os.environ.get("GITHUB_TOKEN")
        if repo and tok:
            r = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues?labels=submit&state=open", headers={**UA, "Authorization": "Bearer " + tok})
            for i in json.loads(urllib.request.urlopen(r).read()):
                for u in re.findall(r"https?://[^\s)>\]\"']+", (i.get("title") or "") + " " + (i.get("body") or "")): add(u, "submission")
    except Exception as e: print("issues", e)
    return found

LINKPAGE = re.compile(r"\b(links|blogroll|friends|webring|cool sites|neighbou?rs|bookmarks|recommend|elsewhere|other sites|link ?list)\b", re.I)

def link_pages(r):
    """Same-website pages that usually list other websites (blogrolls, link pages, webrings)."""
    h = host(r["url"])
    out = []
    for a, t in r.get("anchors", []):
        if host(a) == h and LINKPAGE.search(t or "") and a.rstrip("/") != r["url"].rstrip("/"): out.append(a)
    return list(dict.fromkeys(out))[:2]

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
    db = json.load(open(DB)); st = json.load(open(STATS))
    log = {"started": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "rejected": {}}
    before = len(db["sites"]); sites = dedupe(db["sites"]); log["duplicates_removed"] = before - len(sites)
    known = {key(s["url"]) for s in sites} | {a for s in sites for a in s.get("aliases", [])}
    fps = {s.get("fingerprint") for s in sites if s.get("fingerprint")}
    beta = days_since(db.get("beta_start", TODAY)) < 10
    limit = 100 if beta else 60
    found = sources(known); log["sources"] = {}
    for _, src in found.values(): log["sources"][src] = log["sources"].get(src, 0) + 1
    cand = list(found.values()); random.shuffle(cand)

    # Deep crawl: outbound links + blogroll/link pages of random known websites
    alive = [s for s in sites if s.get("status") != "dead" and s.get("review") != "flagged"]
    seeds = random.sample(alive, min(25, len(alive)))
    with ThreadPoolExecutor(10) as ex: res = [r for r, _ in ex.map(safe_verify, [s["url"] for s in seeds]) if r]
    pages = [p for r in res for p in link_pages(r)][:30]
    with ThreadPoolExecutor(8) as ex: extra = list(ex.map(harvest, pages))
    have = {key(c) for c, _ in cand}; deep = 0
    for r, links in [(r, r["links"]) for r in res] + [(None, l) for l in extra]:
        for l in links:
            n = norm(l)
            if n and allowed(n) and key(n) not in known and key(n) not in have:
                have.add(key(n)); deep += 1
                cand.append((n, "link from " + host(r["url"]) if r else "link page"))
    cand = cand[:limit]
    bad_hosts = malware_hosts()
    with ThreadPoolExecutor(12) as ex: results = list(ex.map(lambda c: safe_verify(c[0]) if key(c[0]) not in bad_hosts else (None, "malware list"), cand))
    added = 0
    for (u, src), (r, why) in zip(cand, results):
        if not r: count(log, why); continue
        if any(a in known for a in r["aliases"]) or (r["fingerprint"] and r["fingerprint"] in fps) or key(r["url"]) in bad_hosts:
            count(log, "duplicate"); continue
        known.update(r["aliases"]); fps.add(r["fingerprint"]); added += 1
        s = {"url": r["url"], "source": src, "status": "ok", "review": "unreviewed", "added": TODAY, "checked": TODAY,
             "fails": 0, "aliases": r["aliases"]}
        apply(s, r); sites.append(s)

    # Recheck: everything older than 30 days first, then the oldest-checked
    old = sorted([s for s in sites if s.get("added") != TODAY], key=lambda s: s.get("checked", ""))
    stale = [s for s in old if days_since(s.get("checked", "")) >= STALE_DAYS]
    untagged = [s for s in old if "tech" not in s and s not in stale][:120]  # one-off catch-up: give older sites vibes/tech tags
    old = (stale + untagged + [s for s in old if s not in stale and s not in untagged])[:80 + len(untagged)]
    with ThreadPoolExecutor(12) as ex: chk = list(ex.map(lambda s: safe_verify(s["url"]), old))
    died = 0; flagged = 0
    for s, (r, why) in zip(old, chk):
        s["checked"] = TODAY
        if r: s["fails"] = 0; apply(s, r); s["status"] = s["status"] if s.get("locked") else "ok"; continue
        s["fails"] = s.get("fails", 0) + 1; s["robot_note"] = f"{why} ({TODAY})"
        if why == "unsafe" and not s.get("locked"): s["review"] = "flagged"; s["flag_reason"] = "unsafe words found"; flagged += 1
        if s.get("locked"): continue  # hand-checked: report only, never change status
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
              candidates_checked=len(cand), categories=cats, bot_version=3)
    st["history"] = (st.get("history", []) + [{"date": TODAY, "added": added, "total": len(visible)}])[-240:]
    st["runs_log"] = ([log] + st.get("runs_log", []))[:30]
    json.dump(db, open(DB, "w"), indent=1, ensure_ascii=False); json.dump(st, open(STATS, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(log, indent=1))

if __name__ == "__main__": main()
