"""Resilient multi-tier website screenshot capture engine for Web Explorer.
Tiers:
1. Local integrity validation (checks magic bytes and minimum size > 3.5KB)
2. WordPress mshots (dual-pass with render wait)
3. Backup proxy capture (image.thum.io / s-shot.ru)
4. Direct OpenGraph / Twitter card image extraction from site HTML
5. Local synthetic retro card generator (zero-missing guarantee)
"""

import concurrent.futures, hashlib, json, time, urllib.parse, urllib.request, re, sys
from pathlib import Path

DIR = Path("docs/screenshots")
MAX_NEW = 150
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 WebExplorer/4.0"

def name(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20] + ".jpg"

def is_valid_image(data: bytes) -> bool:
    if not data or len(data) < 3500:
        return False
    if data.startswith(b"\xff\xd8"):  # JPEG
        return True
    if data.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WebP
        return True
    return False

def fetch_mshots(url: str):
    mshots_url = "https://s.wordpress.com/mshots/v1/" + urllib.parse.quote(url, safe="") + "?w=720"
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(2):
        try:
            req = urllib.request.Request(mshots_url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                data = response.read(2000000)
                if is_valid_image(data):
                    return data
        except Exception:
            pass
        if attempt == 0:
            time.sleep(3.5)
    return None

def fetch_backup_proxy(url: str):
    headers = {"User-Agent": USER_AGENT}
    try:
        t_url = "https://image.thum.io/get/width/720/crop/540/noanimate/" + url
        req = urllib.request.Request(t_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            data = response.read(2000000)
            if is_valid_image(data):
                return data
    except Exception:
        pass
    try:
        s_url = "https://mini.s-shot.ru/1024x768/JPEG/720/Z100/?" + urllib.parse.quote(url, safe=":/._-?=&")
        req = urllib.request.Request(s_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            data = response.read(2000000)
            if is_valid_image(data):
                return data
    except Exception:
        pass
    return None

def fetch_og_image(url: str):
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as resp:
            html = resp.read(350000).decode("utf-8", errors="ignore")
        m = re.search(r"<meta\s+[^>]*property=[\"\x27]og:image[\"\x27][^>]*content=[\"\x27](https?://[^\"\x27]+)[\"\x27]", html, re.I)
        if not m:
            m = re.search(r"<meta\s+[^>]*content=[\"\x27](https?://[^\"\x27]+)[\"\x27][^>]*property=[\"\x27]og:image[\"\x27]", html, re.I)
        if m:
            img_url = m.group(1)
            req2 = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req2, timeout=8) as r2:
                data = r2.read(2000000)
                if is_valid_image(data):
                    return data
    except Exception:
        pass
    return None

def synthesize_local_fallback(site: dict, dest: Path):
    domain = urllib.parse.urlparse(site["url"]).netloc.replace("www.", "")
    title = (site.get("title") or domain)[:32]
    cat = (site.get("category") or "indie").upper()
    vibes = " · ".join((site.get("vibes") or [])[:2]).upper() or "AUTHENTIC WEB ARTIFACT"
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="800" height="500">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#140f24"/>
      <stop offset="100%" stop-color="#07040a"/>
    </linearGradient>
    <pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="800" height="500" fill="url(#bg)"/>
  <rect width="800" height="500" fill="url(#g)"/>
  <rect x="24" y="24" width="752" height="452" rx="10" fill="none" stroke="rgba(168,85,247,0.35)" stroke-width="1.5"/>
  <circle cx="50" cy="46" r="6" fill="#ef4444"/>
  <circle cx="70" cy="46" r="6" fill="#f59e0b"/>
  <circle cx="90" cy="46" r="6" fill="#10b981"/>
  <text x="115" y="51" fill="rgba(255,255,255,0.7)" font-family="monospace" font-size="13" font-weight="bold">⚡ {domain}</text>
  <text x="400" y="210" text-anchor="middle" fill="#a855f7" font-family="sans-serif" font-size="14" font-weight="bold" letter-spacing="3">[{cat}]</text>
  <text x="400" y="260" text-anchor="middle" fill="#ffffff" font-family="sans-serif" font-size="30" font-weight="bold">{title}</text>
  <text x="400" y="300" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-family="sans-serif" font-size="14">{vibes}</text>
  <text x="400" y="440" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-family="monospace" font-size="11">WEB EXPLORER ARCHIVE ARTIFACT █</text>
</svg>"""
    dest.write_text(svg, encoding="utf-8")

def capture(site: dict):
    dest = DIR / name(site["url"])
    if dest.exists() and dest.stat().st_size > 3500:
        return "cached"

    data = fetch_mshots(site["url"])
    if data:
        dest.write_bytes(data)
        return "mshots"

    data = fetch_backup_proxy(site["url"])
    if data:
        dest.write_bytes(data)
        return "proxy"

    data = fetch_og_image(site["url"])
    if data:
        dest.write_bytes(data)
        return "og_image"

    synthesize_local_fallback(site, dest)
    return "synthesized"

def main():
    sites = json.loads(Path("docs/data/sites.json").read_text(encoding="utf-8"))["sites"]
    DIR.mkdir(parents=True, exist_ok=True)
    wanted = {name(s["url"]) for s in sites}
    removed = 0
    for f in DIR.iterdir():
        if f.is_file() and f.name not in wanted:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass

    todo = [s for s in sites if s.get("status") != "dead" and s.get("review") != "flagged" and not (DIR / name(s["url"])).exists()][:MAX_NEW]
    
    results = {"cached": 0, "mshots": 0, "proxy": 0, "og_image": 0, "synthesized": 0}
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        for res in pool.map(capture, todo):
            results[res] = results.get(res, 0) + 1

    total = len(list(DIR.iterdir()))
    print(f"Screenshots cached: {total} (New captures: {results}) · Cleaned unreferenced: {removed}")

if __name__ == "__main__":
    main()
