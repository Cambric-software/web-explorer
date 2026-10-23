"""Website Explorer discovery robot (v2).
Runs inside GitHub Actions with only the Python standard library.
Database = docs/data/sites.json, statistics = docs/data/stats.json.

Jobs on every run:
  1. clean    - merge duplicate websites (same domain, www/http variants)
  2. discover - gather candidates from several sources, verify, describe, categorize
  3. recheck  - re-verify the oldest-checked websites and refresh their details
  4. archive  - look up the first Internet Archive year for a few websites
"""
import json, os, random, re, time, datetime, html as htmllib, urllib.request, urllib.parse
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

DB = "docs/data/sites.json"; STATS = "docs/data/stats.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; WebsiteExplorerBot/2.0; +https://cambric-software.github.io/web-explorer/)",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en;q=0.9,*;q=0.5"}
TODAY = datetime.date.today().isoformat()
BIG = {"google.com","youtube.com","youtu.be","facebook.com","twitter.com","x.com","instagram.com","github.com","reddit.com",
       "amazon.com","wikipedia.org","linkedin.com","tiktok.com","medium.com","apple.com","microsoft.com","t.co","bit.ly",
       "news.ycombinator.com","lobste.rs","docs.google.com","drive.google.com","archive.org","web.archive.org","arxiv.org",
       "nytimes.com","bbc.co.uk","bbc.com","theguardian.com","cnn.com","bloomberg.com","substack.com","imgur.com",
       "discord.gg","discord.com","t.me","whatsapp.com","pinterest.com","goo.gl","apps.apple.com","play.google.com"}
BAD_TLDS = (".zip", ".mov", ".xyz.ru")
PARKED = ["domain for sale","buy this domain","this domain is for sale","domain is parked","parked free","parkingcrew",
          "sedoparking","account suspended","coming soon","under construction","website is under construction",
          "default web site page","welcome to nginx","apache2 ubuntu default page","it works!","index of /",
          "hugedomains","dan.com","afternic","godaddy.com/domains"]
BLOCKED = ["just a moment...","attention required","access denied","verify you are human","enable javascript and cookies",
           "403 forbidden","404 not found","page not found","site not found","error 404","bad gateway"]
UNSAFE = ["casino","betting","porn","xxx","escort","viagra","crypto giveaway","free bitcoin","loan approval","hack account"]

# Weighted vocabulary. Multi-word phrases score higher than single words.
CATS = {
 "Developer": ["programming","developer","software engineer","source code","open source","compiler","framework","library for",
               "api","sdk","cli","command line","javascript","typescript","python","rust","golang","haskell","lisp","kotlin",
               "database","devops","kubernetes","linux kernel","git ","repository","code","coding","debugger","terminal"],
 "Games": ["game","games","play online","puzzle","arcade","multiplayer","indie game","roguelike","level","high score",
           "board game","chess","crossword","sudoku","speedrun","steam","itch.io","gameplay","player"],
 "Art": ["art","artist","illustration","painting","drawing","gallery","portfolio","photography","photographer","design studio",
         "typography","music","album","musician","band","poetry","animation","sketch","generative art","exhibition"],
 "Retro": ["retro","90s","1990s","geocities","old web","ascii","vintage","nostalgia","8-bit","pixel art","web 1.0","neocities",
           "webring","guestbook","amiga","commodore","dos","floppy","crt","classic computing"],
 "Education": ["learn","learning","course","tutorial","lesson","guide to","explained","beginner","teach","university",
               "school","students","curriculum","how to","introduction to","handbook","textbook","academy"],
 "Science": ["science","scientific","physics","astronomy","space","nasa","math","mathematics","biology","chemistry",
             "research","experiment","climate","geology","quantum","telescope","planet","neuroscience","paper"],
 "Business": ["business","startup","company","pricing","customers","saas","enterprise","marketing","sales","invoice",
              "finance","investors","agency","consulting","ecommerce","shop","store","buy now","our clients","b2b"],
 "Technology": ["technology","tech","hardware","electronics","gadget","robot","robotics","3d printing","arduino","raspberry pi",
                "artificial intelligence","machine learning","ai","ai agents","llm","security","cybersecurity","malware","pentest","news and reviews","gpu","cloud","semiconductor","chip","battery","engineering","maker"],
 "Communities": ["forum","community","club","members","join us","discussion","meetup","discord","mailing list","fans",
                 "society","collective","volunteers","group","board","chat"],
 "Personal": ["blog","my name is","about me","personal website","personal site","essays","notes","journal","diary",
              "i write","i'm a","i am a","i'm an","i am an","my blog","my career","my work","writing about","undergraduate","phd","engineer at","homepage of","weblog","digital garden","newsletter","thoughts","posts","essays","articles","writers","publishes"],
 "Tools": ["tool","online tool","generator","converter","calculator","editor","free app","utility","extension","plugin",
           "productivity","template","checker","viewer","maker","builder","dashboard","tracker","planner","timer","video editor","in your browser","macos","app for","free and open source","upload","remove","convert","analytics","checker","online"],
}
DOMAIN_HINTS = [(r"\.edu$|\.ac\.[a-z]+$", "Education", 6), (r"neocities\.org$|tripod|angelfire", "Retro", 6),
                (r"itch\.io$", "Games", 6), (r"\.dev$|\.sh$", "Developer", 2), (r"\.art$", "Art", 4),
                (r"bearblog\.dev$|\.blog$|wordpress\.com$|blogspot\.", "Personal", 5), (r"\.tools?$|\.app$", "Tools", 2)]

def get(url, timeout=8, limit=600_000):
    req = urllib.request.Request(url, headers=UA)
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(limit)
        ctype = r.headers.get("Content-Type", "")
        charset = (re.search(r"charset=([\w-]+)", ctype) or [None, "utf-8"])[1]
        try: text = body.decode(charset, "ignore")
        except LookupError: text = body.decode("utf-8", "ignore")
        return r.status, r.geturl(), text, ctype, round(time.time() - t, 2)

def host(u):
    try: return urllib.parse.urlparse(u).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception: return ""

def key(u):
    """Duplicate key: one website per domain, whatever the scheme, www or path."""
    return host(u)

def norm(u):
    """Canonical homepage URL for a candidate."""
    try: p = urllib.parse.urlparse((u or "").strip())
    except Exception: return None
    if p.scheme not in ("http", "https") or not p.netloc or "@" in p.netloc: return None
    h = p.netloc.lower().split(":")[0]
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", h) or h.endswith(BAD_TLDS): return None
    return "https://" + h

def allowed(u):
    h = host(u)
    return bool(h) and not any(h == b or h.endswith("." + b) for b in BIG)

class Page(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "nav", "footer"}
    def __init__(s):
        super().__init__(convert_charrefs=True)
        s.title = ""; s.meta = {}; s.lang = ""; s.links = []; s.heads = []; s.paras = []; s.words = []
        s._stack = []; s._skip = 0; s._buf = ""
    def handle_starttag(s, tag, a):
        a = {k: (v or "") for k, v in a}
        if tag in s.SKIP: s._skip += 1
        if tag == "html": s.lang = a.get("lang", "")[:2].lower()
        if tag == "meta":
            k = (a.get("name") or a.get("property") or "").lower()
            if k and a.get("content") and k not in s.meta: s.meta[k] = a["content"]
        if tag == "a" and a.get("href", "").startswith("http"): s.links.append(a["href"])
        if tag in ("title", "h1", "h2", "p"): s._stack.append(tag); s._buf = ""
    def handle_endtag(s, tag):
        if tag in s.SKIP and s._skip: s._skip -= 1
        if s._stack and s._stack[-1] == tag:
            s._stack.pop(); t = clean(s._buf)
            if tag == "title" and not s.title: s.title = t
            elif tag in ("h1", "h2") and t and len(s.heads) < 8: s.heads.append(t)
            elif tag == "p" and len(t) > 40 and len(s.paras) < 12: s.paras.append(t)
            s._buf = ""
    def handle_data(s, d):
        if s._skip and not (s._stack and s._stack[-1] == "title"): return
        if s._stack: s._buf += d
        if len(s.words) < 3000: s.words.extend(d.split())

def clean(t):
    return re.sub(r"\s+", " ", htmllib.unescape(t or "").replace("\u2019", "'").replace("\u2018", "'")).strip()

GENERIC = {"home","homepage","welcome","index","main page","official website","official site","start","untitled","blog"}
def best_title(p, h):
    site = clean(p.meta.get("og:site_name", ""))
    raw = clean(p.meta.get("og:title", "")) if len(clean(p.title)) < 3 else clean(p.title)
    raw = raw or clean(p.meta.get("twitter:title", "")) or (p.heads[0] if p.heads else "")
    parts = [x.strip() for x in re.split(r"\s+[|–—·•:»-]\s+|\s+::\s+", raw) if x.strip()]
    parts = [x for x in parts if x.lower() not in GENERIC]
    if len(parts) > 1: parts = [x for x in parts if not re.fullmatch(r"(www\.)?[\w.-]+\.[a-z]{2,}", x.lower())] or parts
    if site and site.lower() not in GENERIC and len(site) <= 60 and not re.fullmatch(r"(www\.)?[\w.-]+\.[a-z]{2,}", site.lower()): title = site
    elif parts:
        # The site's own name is usually the shortest meaningful segment or the one matching the domain
        stem = h.split(".")[0].replace("-", "")
        match = [x for x in parts if stem and stem in x.lower().replace(" ", "").replace("-", "")]
        title = match[0] if match else (parts[-1] if len(parts) > 1 and len(parts[-1]) < len(parts[0]) and len(parts[-1]) > 2 else parts[0])
    else: title = h
    title = title.strip(" -|·")
    if len(title) < 2 or title.lower() in GENERIC: title = h
    return title[:80]

def best_description(p, title):
    for k in ("description", "og:description", "twitter:description"):
        d = clean(p.meta.get(k, ""))
        if len(d) >= 25 and d.lower() != title.lower() and "javascript" not in d.lower()[:40]: break
    else:
        d = next((x for x in p.paras if len(x.split()) >= 8), "") or (p.heads[1] if len(p.heads) > 1 else "")
    d = re.sub(r"https?://\S+", "", d).strip()
    if len(d) > 220: d = d[:217].rsplit(" ", 1)[0] + "…"
    return d

def categorize(title, desc, heads, body, h):
    """Score only human-visible text, weighting title and description above body text."""
    zones = [(title.lower(), 4), (desc.lower(), 3), (" ".join(heads).lower(), 2), (body.lower()[:6000], 1)]
    scores = {c: 0.0 for c in CATS}
    for c, words in CATS.items():
        for w in words:
            pat = r"(?<![a-z])" + re.escape(w.strip()) + r"(?![a-z])"
            for text, weight in zones:
                n = len(re.findall(pat, text))
                if n: scores[c] += weight * min(n, 3) * (1.5 if " " in w.strip() else 1)
    for pat, c, bonus in DOMAIN_HINTS:
        if re.search(pat, h): scores[c] += bonus
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    (top, s1), (second, s2) = ranked[0], ranked[1]
    confidence = round(s1 / (s1 + s2), 2) if s1 else 0
    if s1 < 3: return "Random", confidence, []
    tags = [c for c, s in ranked[1:4] if s >= max(4, s1 * 0.5)]
    return top, confidence, tags

def verify(url):
    """Run every check. Returns details for a working website, or None with a reason."""
    try:
        st, final, html, ctype, secs = get(url)
    except Exception as e:
        return None, "unreachable"
    if st != 200: return None, f"http {st}"
    if "html" not in ctype.lower(): return None, "not html"
    if secs > 8: return None, "slow"
    p = Page()
    try: p.feed(html)
    except Exception: pass
    h = host(final) or host(url)
    title = best_title(p, h)
    visible = " ".join(p.words)
    low = (title + " " + clean(p.title) + " " + visible[:4000]).lower()
    if any(w in low for w in PARKED): return None, "parked"
    if any(w in clean(p.title).lower() for w in BLOCKED): return None, "blocked"
    if any(re.search(r"(?<![a-z])" + w + r"(?![a-z])", low) for w in UNSAFE): return None, "unsafe"
    if len(p.words) < 40: return None, "too little content"
    desc = best_description(p, title)
    cat, conf, tags = categorize(title, desc, p.heads, visible, h)
    lang = p.lang or (p.meta.get("og:locale", "")[:2].lower()) or "?"
    return {"url": "https://" + h if final.startswith("https") else "http://" + h, "title": title, "description": desc,
            "category": cat, "confidence": conf, "tags": tags, "lang": lang, "load_time": secs,
            "https": final.startswith("https"), "words": len(p.words), "links": p.links[:80]}, "ok"

def safe_verify(u):
    try: return verify(u)
    except Exception: return None, "error"

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
    for _ in range(12):  # Wiby's "surprise me" redirects to a random small-web site
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

def first_archive_year(url):
    try:
        q = urllib.parse.urlencode({"url": host(url), "output": "json", "filter": "statuscode:200", "limit": 1, "fl": "timestamp"})
        rows = json.loads(get("https://web.archive.org/cdx/search/cdx?" + q, timeout=10)[2])
        return int(rows[1][0][:4]) if len(rows) > 1 else None
    except Exception:
        return None

def dedupe(sites):
    """Keep one entry per domain: prefer alive, admin-locked, then oldest."""
    best = {}
    for s in sites:
        k = key(s["url"]); o = best.get(k)
        if not o or (s.get("status") != "dead", bool(s.get("locked"))) > (o.get("status") != "dead", bool(o.get("locked"))): best[k] = s
    return list(best.values())

def apply(site, r):
    """Copy fresh details onto a stored site unless the admin locked it."""
    for f in ("lang", "load_time", "https", "words"): site[f] = r[f]
    if not site.get("locked"):
        for f in ("title", "description", "category", "confidence", "tags"): site[f] = r[f]

def main():
    db = json.load(open(DB)); st = json.load(open(STATS))
    log = {"started": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "rejected": {}}
    before = len(db["sites"]); sites = dedupe(db["sites"]); log["duplicates_removed"] = before - len(sites)
    known = {key(s["url"]) for s in sites}
    beta = (datetime.date.today() - datetime.date.fromisoformat(db.get("beta_start", TODAY))).days < 10
    limit = 80 if beta else 50
    found = sources(known); log["sources"] = {}
    for _, src in found.values(): log["sources"][src] = log["sources"].get(src, 0) + 1
    cand = list(found.values()); random.shuffle(cand)
    # Crawl outbound links of random known sites: the web grows from itself
    alive = [s for s in sites if s.get("status") != "dead"]
    with ThreadPoolExecutor(10) as ex:
        res = [r for r, _ in ex.map(safe_verify, [s["url"] for s in random.sample(alive, min(10, len(alive)))]) if r]
    for r in res:
        for l in r["links"]:
            n = norm(l)
            if n and allowed(n) and key(n) not in known and all(key(n) != key(c) for c, _ in cand): cand.append((n, "link from " + host(r["url"])))
    cand = cand[:limit]
    with ThreadPoolExecutor(12) as ex: results = list(ex.map(lambda c: safe_verify(c[0]), cand))
    added = 0
    for (u, src), (r, why) in zip(cand, results):
        if not r: log["rejected"][why] = log["rejected"].get(why, 0) + 1; continue
        if key(r["url"]) in known: log["rejected"]["duplicate"] = log["rejected"].get("duplicate", 0) + 1; continue
        known.add(key(r["url"])); added += 1
        s = {"url": r["url"], "source": src, "status": "ok", "added": TODAY, "checked": TODAY, "fails": 0}
        apply(s, r); sites.append(s)
    # Re-verify the oldest-checked websites (everything gets rechecked well within 30 days)
    old = sorted([s for s in sites if s.get("added") != TODAY], key=lambda s: s["checked"])[:60]
    with ThreadPoolExecutor(12) as ex: chk = list(ex.map(lambda s: safe_verify(s["url"]), old))
    died = 0
    for s, (r, why) in zip(old, chk):
        s["checked"] = TODAY
        if r: s["fails"] = 0; s["status"] = "ok"; apply(s, r)
        else:
            s["fails"] = s.get("fails", 0) + 1
            if s["fails"] >= 3 and s["status"] != "dead": died += 1
            s["status"] = "dead" if s["fails"] >= 3 else "warn"
    alive = [s for s in sites if s["status"] != "dead"]
    pending = sorted([s for s in alive if not s.get("first_seen") and s.get("archive_checked") != TODAY], key=lambda s: s.get("archive_checked", ""))[:15]
    with ThreadPoolExecutor(3) as ex: years = list(ex.map(lambda s: first_archive_year(s["url"]), pending))
    for s, y in zip(pending, years):
        s["archive_checked"] = TODAY
        if y: s["first_seen"] = y
    db["sites"] = sites
    cats = {}
    for s in alive: cats[s["category"]] = cats.get(s["category"], 0) + 1
    log.update(candidates=len(cand), added=added, rechecked=len(old), newly_dead=died, archive_years=sum(1 for y in years if y))
    st.update(total=len(alive), dead=len(sites) - len(alive), runs=st.get("runs", 0) + 1, last_run=log["started"],
              found_last_run=added, beta=beta, candidates_checked=len(cand), categories=cats, bot_version=2)
    st["history"] = (st.get("history", []) + [{"date": TODAY, "added": added, "total": len(alive)}])[-120:]
    st["runs_log"] = ([log] + st.get("runs_log", []))[:20]
    json.dump(db, open(DB, "w"), indent=1, ensure_ascii=False); json.dump(st, open(STATS, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(log, indent=1))

if __name__ == "__main__": main()
