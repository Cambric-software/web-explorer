"""Verification engine: the 7 checks every website must pass."""
import asyncio, re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup
from .config import settings

PARKED = ["buy this domain","domain for sale","this domain is for sale","coming soon","domain is parked",
          "parked free","under construction","this domain may be for sale","hugedomains","sedo.com","dan.com"]
UNSAFE_WORDS = ["casino","viagra","crypto-doubler","free-bitcoin","porn","xxx","loan-approval","login-verify","account-suspended"]
UNSAFE_TLDS = [".zip",".mov",".tk",".ml",".ga",".cf",".gq"]
MIN_TEXT = 200
HEADERS = {"User-Agent": "WebsiteExplorerBot/1.0 (+https://github.com/cambric/website-explorer)"}

CATEGORY_KEYWORDS = {
    "Developer": ["github","open source","developer","api","code","programming","npm","rust","python"],
    "Games": ["game","play","puzzle","arcade","score","level"],
    "Art": ["art","artist","gallery","illustration","painting","portfolio","design"],
    "Retro": ["geocities","web 1.0","guestbook","webring","under construction","90s","neocities"],
    "Education": ["learn","course","tutorial","university","lesson","education","study"],
    "Business": ["shop","store","services","pricing","contact us","our team","company"],
    "Technology": ["technology","hardware","software","ai","robot","tech","engineering"],
    "Communities": ["forum","community","members","discussion","thread","board"],
    "Personal": ["blog","about me","my name","personal","journal","posts"],
    "Tools": ["tool","generator","converter","calculator","online","free tool","utility"],
}

def normalize(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url): url = "https://" + url
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.")
    path = p.path.rstrip("/")
    return urlunparse(("https", host, path, "", "", ""))

def categorize(text: str, url: str) -> str:
    t = (text + " " + url).lower()
    scores = {c: sum(t.count(k) for k in ks) for c, ks in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Random"

def is_safe_url(url: str) -> bool:
    u = url.lower()
    host = urlparse(u).hostname or ""
    if any(host.endswith(t) for t in UNSAFE_TLDS): return False
    if any(w in u for w in UNSAFE_WORDS): return False
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host): return False
    return True

async def safe_browsing(client: httpx.AsyncClient, url: str) -> bool:
    if not settings.GOOGLE_SAFE_BROWSING_KEY: return True
    try:
        r = await client.post(
            f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={settings.GOOGLE_SAFE_BROWSING_KEY}",
            json={"client": {"clientId": "website-explorer", "clientVersion": "1.0"},
                  "threatInfo": {"threatTypes": ["MALWARE","SOCIAL_ENGINEERING","UNWANTED_SOFTWARE"],
                                 "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"],
                                 "threatEntries": [{"url": url}]}}, timeout=5)
        return not r.json().get("matches")
    except Exception:
        return True

@dataclass
class Result:
    ok: bool
    url: str
    reason: str = ""
    title: str = ""
    description: str = ""
    category: str = "Random"
    language: str | None = None
    links: list[str] | None = None

async def verify(url: str, client: httpx.AsyncClient | None = None) -> Result:
    url = normalize(url)
    if not is_safe_url(url): return Result(False, url, "unsafe")       # check 7
    own = client is None
    client = client or httpx.AsyncClient(headers=HEADERS, follow_redirects=True)
    try:
        r = await client.get(url, timeout=settings.VERIFY_TIMEOUT)      # check 5 (timeout)
    except Exception as e:
        if own: await client.aclose()
        return Result(False, url, f"unreachable: {type(e).__name__}")
    try:
        if r.status_code != 200:                                       # check 1 & 2
            return Result(False, url, f"status {r.status_code}")
        if "text/html" not in r.headers.get("content-type", ""):
            return Result(False, url, "not html")
        soup = BeautifulSoup(r.text[:500_000], "html.parser")
        for s in soup(["script","style","noscript"]): s.decompose()
        text = " ".join(soup.get_text(" ").split())
        low = text.lower()
        if any(p in low[:3000] for p in PARKED) and len(text) < 3000:   # check 3
            return Result(False, url, "parked")
        if len(text) < MIN_TEXT:                                        # check 4
            return Result(False, url, "no content")
        if not await safe_browsing(client, url):                        # check 7
            return Result(False, url, "unsafe")
        title = (soup.title.string.strip() if soup.title and soup.title.string else urlparse(url).hostname)[:500]
        md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        desc = (md.get("content", "").strip() if md else text[:240])[:1000]
        lang = (soup.html.get("lang") if soup.html else None)
        links = []
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if h.startswith("http"):
                links.append(h)
        final = normalize(str(r.url))
        return Result(True, final, "ok", title, desc, categorize(title + " " + desc + " " + text[:4000], final),
                      (lang or "")[:16] or None, links[:200])
    finally:
        if own: await client.aclose()

async def verify_many(urls: list[str]) -> list[Result]:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True,
                                 limits=httpx.Limits(max_connections=50)) as c:
        return await asyncio.gather(*(verify(u, c) for u in urls))
