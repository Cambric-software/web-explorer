"""Tally public votes for the Global Top 25 Hall of Fame.
Visitors send their votes as a GitHub issue titled "Votes: ..." (pre-filled by the site).
Each GitHub account counts once (its newest issue wins); only the site's real vote values are accepted.
Writes docs/data/votes.json. Standard library only."""
import json, os, re, urllib.request
from pathlib import Path

OUT = Path("docs/data/votes.json")
LINE = re.compile(r"^\s*([+-]?\d+)\s+(https?://\S+)\s*$", re.M)
ALLOWED = {-1, 1, 3, 4, 5, 6, 8}  # dislike, like, gem, favorite and favorite combinations

def canon(url): return url.rstrip("/").lower().replace("://www.", "://")

def parse(body):
    out = {}
    for n, url in LINE.findall(body or ""):
        n = int(n)
        if n in ALLOWED: out[canon(url)] = n
    return dict(list(out.items())[:200])

def tally(issues, known):
    per_user = {}
    for i in sorted(issues, key=lambda i: i.get("created_at", "")):
        if not (i.get("title") or "").lower().startswith("votes:") or "pull_request" in i: continue
        per_user[(i.get("user") or {}).get("login", "?")] = parse(i.get("body"))
    score = {}
    for votes in per_user.values():
        for url, n in votes.items():
            if url in known:
                s = score.setdefault(known[url], {"score": 0, "voters": 0}); s["score"] += n; s["voters"] += 1
    return score, len(per_user)

LEDGER = Path("docs/data/cloud_ledger.json")

def cloud(path, method="GET"):
    url = os.environ.get("SUPABASE_URL", "").rstrip("/"); key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and key): return None
    r = urllib.request.Request(url + "/rest/v1/" + path, method=method,
                               headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=20).read() or b"null")

def cloud_votes(known):
    """Pull the buffered anonymous votes, fold them into the ledger (one vote per device per site), then empty the buffer."""
    import hashlib
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    try: rows = cloud("pending_votes?select=id,explorer_id,site_url,vote&order=id&limit=5000") or []
    except Exception as e: print("cloud votes", e); rows = []
    for r in rows:
        dev = hashlib.sha256(str(r.get("explorer_id")).encode()).hexdigest()[:16]
        url, n = canon(str(r.get("site_url", ""))), r.get("vote")
        if url not in known: continue
        mine = ledger.setdefault(dev, {})
        if n in ALLOWED: mine[url] = n
        else: mine.pop(url, None)
        if not mine: ledger.pop(dev)
    if rows:
        try: cloud("pending_votes?id=lte.%d" % max(r["id"] for r in rows), "DELETE")
        except Exception as e: print("cloud flush", e)
    LEDGER.write_text(json.dumps(ledger, separators=(",", ":")))
    print("Cloud votes:", len(rows), "new,", len(ledger), "devices total")
    return ledger

def main():
    raw_sites = json.loads(Path("docs/data/sites.json").read_text(encoding="utf-8"))
    sites = raw_sites.get("sites", raw_sites) if isinstance(raw_sites, dict) else raw_sites
    known = {canon(s["url"]): s["url"] for s in sites}
    score = {}
    voters = 0
    # Clean anonymous voting via Supabase ledger (GitHub Issues voting retired)
    for votes in cloud_votes(known).values():
        voters += 1
        for url, n in votes.items():
            s = score.setdefault(known[url], {"score": 0, "voters": 0})
            s["score"] += n
            s["voters"] += 1
    OUT.write_text(json.dumps({"voters": voters, "sites": score}, indent=1), encoding="utf-8")
    print("Hall of Fame:", len(score), "websites with votes from", voters, "explorers (Supabase ledger)")

if __name__ == "__main__": main()
