"""Capture cached website previews for GitHub Pages (no API key) and remove pictures nobody uses."""
import concurrent.futures, hashlib, json, time, urllib.parse, urllib.request
from pathlib import Path

DIR = Path('docs/screenshots')
MAX_NEW = 150  # per run, keeps every run short

def name(url): return hashlib.sha256(url.encode()).hexdigest()[:20] + '.jpg'

def capture(site):
    dest = DIR / name(site['url'])
    if dest.exists(): return
    try:
        url = 'https://s.wordpress.com/mshots/v1/' + urllib.parse.quote(site['url'], safe='') + '?w=640'
        for attempt in range(2):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=12) as response: data = response.read(1500000)
            if data.startswith(b'\xff\xd8') and len(data) > 6000: dest.write_bytes(data); return
            if attempt == 0: time.sleep(3)
    except Exception: pass

def main():
    sites = json.loads(Path('docs/data/sites.json').read_text())['sites']
    DIR.mkdir(exist_ok=True)
    wanted = {name(s['url']) for s in sites}
    removed = 0
    for f in DIR.glob('*.jpg'):
        if f.name not in wanted: f.unlink(); removed += 1
    todo = [s for s in sites if s.get('status') != 'dead' and s.get('review') != 'flagged' and not (DIR / name(s['url'])).exists()][:MAX_NEW]
    with concurrent.futures.ThreadPoolExecutor(6) as pool: list(pool.map(capture, todo))
    print('Cached screenshots:', len(list(DIR.glob('*.jpg'))), '· removed unused:', removed)

if __name__ == '__main__': main()
