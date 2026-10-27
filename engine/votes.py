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

def main():
    repo = os.environ.get("GITHUB_REPOSITORY"); tok = os.environ.get("GITHUB_TOKEN")
    sites = json.loads(Path("docs/data/sites.json").read_text())["sites"]
    known = {canon(s["url"]): s["url"] for s in sites}
    issues = []
    if repo and tok:
        for page in range(1, 11):
            r = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}",
                                       headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"})
            try: batch = json.loads(urllib.request.urlopen(r, timeout=20).read())
            except Exception as e: print("issues", e); break
            issues += batch
            if len(batch) < 100: break
    score, voters = tally(issues, known)
    OUT.write_text(json.dumps({"voters": voters, "sites": score}, indent=1))
    print("Hall of Fame:", len(score), "websites with votes from", voters, "explorers")

if __name__ == "__main__": main()
