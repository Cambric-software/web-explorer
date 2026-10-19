"""Website Explorer discovery + verification engine.
Runs inside GitHub Actions. Uses only the Python standard library.
Database = docs/data/sites.json (served by GitHub Pages)."""
import json, os, random, re, datetime, urllib.request, urllib.parse
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

DB = "docs/data/sites.json"; STATS = "docs/data/stats.json"
UA = {"User-Agent": "WebsiteExplorerBot/1.0 (+https://cambric-software.github.io/web-explorer/)"}
TODAY = datetime.date.today().isoformat()
BIG = {"google.com","youtube.com","facebook.com","twitter.com","x.com","instagram.com","github.com","reddit.com",
       "amazon.com","wikipedia.org","linkedin.com","tiktok.com","medium.com","apple.com","microsoft.com","t.co","bit.ly"}
CATS = {"Games":["game","play","puzzle"],"Tools":["tool","app","generator","converter","editor"],
        "Developer":["code","api","developer","programming","open source","rust","python","javascript"],
        "Art":["art","design","illustration","music","photo"],"Education":["learn","course","tutorial","guide","explained"],
        "Science":["science","physics","space","math","biology"],"Retro":["retro","90s","geocities","old web","ascii"],
        "Personal":["blog","my name","about me","essays","notes"],"Communities":["forum","community","club","members"],
        "Technology":["tech","hardware","electronics","ai"]}

def get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.geturl(), r.read(400_000).decode("utf-8", "ignore")

def domain(u): return urllib.parse.urlparse(u).netloc.lower().removeprefix("www.")
def norm(u):
    p = urllib.parse.urlparse(u.strip())
    return f"{p.scheme}://{p.netloc.lower()}" if p.scheme in ("http","https") and p.netloc else None

class Meta(HTMLParser):
    def __init__(s): super().__init__(); s.title=""; s.desc=""; s.lang=""; s.links=[]; s._t=False
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag=="title": s._t=True
        if tag=="html": s.lang=(a.get("lang") or "")[:2]
        if tag=="meta" and (a.get("name","").lower()=="description" or a.get("property","")=="og:description") and not s.desc:
            s.desc=(a.get("content") or "")[:240]
        if tag=="a" and a.get("href","").startswith("http"): s.links.append(a["href"])
    def handle_endtag(s, tag):
        if tag=="title": s._t=False
    def handle_data(s, d):
        if s._t and len(s.title)<120: s.title+=d

def categorize(text):
    t=text.lower(); best=max(CATS, key=lambda c: sum(k in t for k in CATS[c]))
    return best if any(k in t for k in CATS[best]) else "Random"

def verify(url):
    try:
        st, final, html = get(url)
        if st >= 400 or len(html) < 200: return None
        m = Meta(); m.feed(html)
        text = (m.title+" "+m.desc).lower()
        if any(w in text for w in ["domain for sale","buy this domain","parked","account suspended","coming soon"]): return None
        title = re.sub(r"\s+"," ",m.title).strip() or domain(final)
        return {"url": norm(final) or url, "title": title[:100], "description": m.desc.strip(), "lang": m.lang or "?",
                "category": categorize(text+" "+html[:5000]), "links": m.links[:60]}
    except Exception:
        return None

def sources(known):
    found=set()
    def add(u):
        n=norm(u or "")
        if n and domain(n) not in BIG and n not in known: found.add(n)
    for q in ["show_hn","story"]:
        try:
            _,_,b=get(f"https://hn.algolia.com/api/v1/search_by_date?tags={q}&hitsPerPage=100")
            for h in json.loads(b)["hits"]: add(h.get("url"))
        except Exception as e: print("hn", e)
    try:
        _,_,b=get("https://lobste.rs/newest.json")
        for h in json.loads(b): add(h.get("url"))
    except Exception as e: print("lobsters", e)
    try:  # user submissions via GitHub issues labelled "submit"
        repo=os.environ.get("GITHUB_REPOSITORY"); tok=os.environ.get("GITHUB_TOKEN")
        if repo and tok:
            r=urllib.request.Request(f"https://api.github.com/repos/{repo}/issues?labels=submit&state=open",headers={**UA,"Authorization":"Bearer "+tok})
            for i in json.loads(urllib.request.urlopen(r).read()):
                for u in re.findall(r"https?://[^\s)>\]]+", (i.get("title") or "")+" "+(i.get("body") or "")): add(u)
    except Exception as e: print("issues", e)
    return found

def main():
    db=json.load(open(DB)); st=json.load(open(STATS))
    sites=db["sites"]; known={s["url"] for s in sites}
    beta=(datetime.date.today()-datetime.date.fromisoformat(db["beta_start"])).days < 10
    limit=50 if beta else 25
    cand=list(sources(known)); random.shuffle(cand)
    # crawl outbound links of a few random known sites (the web grows from itself)
    with ThreadPoolExecutor(10) as ex:
        res=[r for r in ex.map(verify, random.sample(sorted(known), min(8,len(known)))) if r]
    for r in res:
        for l in r["links"]:
            n=norm(l)
            if n and n not in known and domain(n) not in BIG: cand.append(n)
    cand=list(dict.fromkeys(cand))[:limit]
    with ThreadPoolExecutor(10) as ex: ok=[r for r in ex.map(verify, cand) if r]
    added=0
    for r in ok:
        if r["url"] in known: continue
        known.add(r["url"]); added+=1
        sites.append({"url":r["url"],"title":r["title"],"description":r["description"],"category":r["category"],
                      "lang":r["lang"],"source":"discovery","status":"ok","added":TODAY,"checked":TODAY,"fails":0})
    # re-verify the 40 oldest-checked sites
    old=sorted(sites,key=lambda s:s["checked"])[:40]
    with ThreadPoolExecutor(10) as ex: chk=list(ex.map(lambda s: verify(s["url"]), old))
    for s,r in zip(old,chk):
        s["checked"]=TODAY
        if r: s["fails"]=0; s["status"]="ok"
        else:
            s["fails"]=s.get("fails",0)+1
            s["status"]="dead" if s["fails"]>=3 else "warn"
    db["sites"]=[s for s in sites if s["status"]!="dead"]
    st.update(total=len(db["sites"]),runs=st["runs"]+1,last_run=datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat()+"Z",
              found_last_run=added,beta=beta,candidates_checked=len(cand))
    st["history"]=(st["history"]+[{"date":TODAY,"added":added,"total":len(db["sites"])}])[-60:]
    json.dump(db,open(DB,"w"),indent=1); json.dump(st,open(STATS,"w"),indent=1)
    print(f"checked {len(cand)} candidates, added {added}, total {len(db['sites'])}")

if __name__=="__main__": main()
