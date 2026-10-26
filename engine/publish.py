"""Generate crawlable pages, sitemap and RSS for the static GitHub Pages site."""
import datetime, html, json, hashlib
from pathlib import Path
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, tostring

BASE='https://cambric-software.github.io/web-explorer'
ROOT=Path('docs')

def generate():
    db=json.loads((ROOT/'data/sites.json').read_text())
    for s in db['sites']:
        s['screenshot_file']=hashlib.sha256(s['url'].encode()).hexdigest()[:20]+'.jpg'
    (ROOT/'data/sites.json').write_text(json.dumps(db,indent=1,ensure_ascii=False))
    sites=[s for s in db['sites'] if s.get('status')!='dead' and s.get('review')!='flagged']
    categories=sorted({s['category'] for s in sites})
    import shutil; shutil.rmtree(ROOT/'categories',ignore_errors=True)
    sitemap=Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for url in [BASE+'/']+[BASE+'/categories/'+quote(c.lower())+'/' for c in categories]:
        SubElement(SubElement(sitemap,'url'),'loc').text=url
    (ROOT/'sitemap.xml').write_bytes(tostring(sitemap,encoding='utf-8',xml_declaration=True))
    (ROOT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+BASE+'/sitemap.xml\n')
    for c in categories:
        dest=ROOT/'categories'/c.lower();dest.mkdir(parents=True,exist_ok=True)
        title=f'{c} Websites — Website Explorer'
        desc=f'Discover independent {c.lower()} websites, useful finds and hidden gems with Website Explorer.'
        cards=''.join(f'<article class="site"><div class="site-body"><span class="tag">{html.escape(c)}</span><h2>{html.escape(s["title"])}</h2><p>{html.escape(s.get("description", ""))}</p><p class="muted">'+(f'First archived {s["first_seen"]} · ' if s.get('first_seen') else '')+f'Checked {html.escape(s.get("checked","Unknown"))}</p><a class="btn" href="{html.escape(s["url"],quote=True)}" target="_blank" rel="noopener noreferrer">Visit ↗</a></div></article>' for s in sites if s['category']==c)
        (dest/'index.html').write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc,quote=True)}"><meta property="og:title" content="{html.escape(title,quote=True)}"><meta property="og:description" content="{html.escape(desc,quote=True)}"><meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image"><meta property="og:image" content="{BASE}/og.png"><meta name="twitter:image" content="{BASE}/og.png"><link rel="canonical" href="{BASE}/categories/{quote(c.lower())}/"><link rel="stylesheet" href="../../style.css"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet"></head><body><header><a class="logo" href="../../">WEBSITE<span>/</span>EXPLORER</a><a href="../../?category={quote(c)}#browse">Browse {html.escape(c)} ↗</a></header><main><h1>{html.escape(c)} websites</h1><div class="grid">{cards}</div></main><footer>Cambric Software &amp; Hardware Studios · Website Explorer</footer></body></html>''')
    rss=Element('rss',version='2.0');channel=SubElement(rss,'channel')
    for k,v in [('title','Website Explorer — New discoveries'),('link',BASE+'/'),('description','Independent websites and hidden gems, discovered every hour.')]:SubElement(channel,k).text=v
    for s in sorted(sites,key=lambda s:s.get('added',''),reverse=True)[:50]:
        item=SubElement(channel,'item')
        for k,v in [('title',s['title']),('link',s['url']),('description',s.get('description','')),('category',s['category']),('guid',s['url'])]:SubElement(item,k).text=v
        if s.get('added'):
            try:SubElement(item,'pubDate').text=datetime.datetime.fromisoformat(s['added']).strftime('%a, %d %b %Y 00:00:00 +0000')
            except ValueError:pass
    (ROOT/'feed.xml').write_bytes(tostring(rss,encoding='utf-8',xml_declaration=True))
    print(f'Generated {len(categories)} categories, sitemap, robots and feed.')

if __name__=='__main__':generate()
