"""Capture cached website previews for GitHub Pages (no API key)."""
import concurrent.futures, hashlib, json, time, urllib.parse, urllib.request
from pathlib import Path

def capture(site):
    filename=hashlib.sha256(site['url'].encode()).hexdigest()[:20]+'.jpg'
    dest=Path('docs/screenshots')/filename
    if dest.exists():return
    try:
        url='https://s.wordpress.com/mshots/v1/'+urllib.parse.quote(site['url'],safe='')+'?w=640'
        for attempt in range(2):
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=12) as response:data=response.read(1500000)
            if data.startswith(b'\xff\xd8'):dest.write_bytes(data);return
            if attempt==0:time.sleep(2)
    except Exception:pass

def main():
    sites=json.loads(Path('docs/data/sites.json').read_text())['sites']
    Path('docs/screenshots').mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(6) as pool:list(pool.map(capture,[s for s in sites if s.get('status')!='dead']))
    print('Cached screenshots:',len(list(Path('docs/screenshots').glob('*.jpg'))))
if __name__=='__main__':main()
