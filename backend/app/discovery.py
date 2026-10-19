"""Discovery engine: generate candidates, verify, store."""
import random, re
from datetime import datetime
from urllib.parse import urlparse, unquote
import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Website, Submission
from .verifier import verify_many, normalize, HEADERS
from . import cache

BIG_SITES = {"google.com","facebook.com","youtube.com","twitter.com","x.com","instagram.com","linkedin.com",
             "amazon.com","wikipedia.org","apple.com","microsoft.com","tiktok.com","reddit.com","pinterest.com",
             "t.co","bit.ly","goo.gl","whatsapp.com","fb.com","github.com/login"}

SEARCH_TERMS = ["personal homepage","indie web","my little website","neocities","handmade website","webring",
                "browser game made by","small web","hobby project","weird website","digital garden","retro web",
                "useful online tool","fan site","old internet","home page of","tiny web toy","blogroll"]

def host_of(u: str) -> str:
    return (urlparse(u).hostname or "").removeprefix("www.")

def is_interesting(u: str) -> bool:
    h = host_of(u)
    return bool(h) and not any(h == b or h.endswith("." + b) for b in BIG_SITES)

def from_known_sites(db: Session, n: int) -> list[str]:
    """Extract links from websites already known (cached outlinks or a quick crawl)."""
    out: list[str] = []
    for link in cache.pop_frontier(n):
        out.append(link)
    return out

async def from_search(n: int) -> list[str]:
    term = random.choice(SEARCH_TERMS)
    out = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=8, follow_redirects=True) as c:
            r = await c.post("https://html.duckduckgo.com/html/", data={"q": term})
            for m in re.findall(r'uddg=([^&"]+)', r.text):
                out.append(unquote(m))
    except Exception:
        pass
    return out[:n]

def from_submissions(db: Session, n: int) -> list[str]:
    subs = db.scalars(select(Submission).where(Submission.status == "pending").limit(n)).all()
    for s in subs: s.status = "processing"
    db.commit()
    return [s.url for s in subs]

async def from_ai(n: int) -> list[str]:
    """Future: Cambric AI Agent discovery hook."""
    return []

async def generate_candidates(db: Session, n: int) -> list[str]:
    cands = from_submissions(db, n // 5) + from_known_sites(db, n // 2) + await from_search(n) + await from_ai(n // 5)
    seen, out = set(), []
    for c in cands:
        try:
            u = normalize(c)
        except Exception:
            continue
        # only homepages of new hosts, avoid duplicates (check 6)
        u = normalize("https://" + host_of(u))
        if u in seen or not is_interesting(u): continue
        seen.add(u); out.append(u)
    if out:
        existing = set(db.scalars(select(Website.url).where(Website.url.in_(out))).all())
        out = [u for u in out if u not in existing]
    return out[:n]

async def discover(db: Session, n: int = 50, user_id: int | None = None) -> list[Website]:
    cands = await generate_candidates(db, n)
    if not cands: return []
    results = await verify_many(cands)
    saved = []
    for r in results:
        if r.links:
            cache.push_frontier([l for l in r.links if is_interesting(l)])
        if not r.ok: continue
        if db.scalar(select(Website.id).where(Website.url == r.url)): continue
        w = Website(url=r.url, title=r.title, description=r.description, category=r.category,
                    language=r.language, source="discovery", discovered_by=user_id,
                    last_verified=datetime.utcnow(), status="alive")
        db.add(w); saved.append(w)
    db.query(Submission).filter(Submission.status == "processing").update({"status": "done"})
    db.commit()
    for w in saved: db.refresh(w)
    cache.incr("stats:discovered", len(saved))
    return saved

def random_alive(db: Session, category: str | None = None) -> Website | None:
    q = select(Website).where(Website.status == "alive")
    if category and category != "Random": q = q.where(Website.category == category)
    return db.scalars(q.order_by(func.random()).limit(1)).first()
