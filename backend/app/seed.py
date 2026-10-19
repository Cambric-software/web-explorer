"""Seed starter websites so Explore works on first boot."""
from sqlalchemy import select
from .database import Base, engine, SessionLocal
from .models import Website
from . import cache

SEED = [
 ("https://neal.fun","Neal.fun","Games, visualizations and interactive things.","Games"),
 ("https://www.spacejam.com/1996","Space Jam (1996)","The original 1996 Space Jam website, still online.","Retro"),
 ("https://neocities.org","Neocities","Free web hosting for creative personal websites.","Communities"),
 ("https://www.windows93.net","Windows 93","A parody browser operating system.","Games"),
 ("https://radio.garden","Radio Garden","Listen to live radio stations around the globe.","Tools"),
 ("https://www.theuselessweb.com","The Useless Web","Takes you to useless websites.","Random"),
 ("https://ciechanow.ski","Bartosz Ciechanowski","Interactive explanatory articles on engineering.","Education"),
 ("https://www.gwern.net","Gwern.net","Long-form essays on many topics.","Personal"),
 ("https://excalidraw.com","Excalidraw","Virtual hand-drawn style whiteboard.","Tools"),
 ("https://poolsuite.net","Poolsuite","Retro summer vibes music player.","Art"),
 ("https://www.cameronsworld.net","Cameron's World","A web collage of Geocities text and images.","Retro"),
 ("https://hackaday.com","Hackaday","Fresh hacks every day.","Technology"),
 ("https://news.ycombinator.com","Hacker News","Tech and startup community news.","Communities"),
 ("https://ooh.directory","ooh.directory","A collection of blogs about every topic.","Personal"),
 ("https://marginalia-search.com","Marginalia Search","A search engine for the small web.","Tools"),
 ("https://lichess.org","Lichess","Free, open-source chess.","Games"),
 ("https://www.drawabox.com","Drawabox","Free lessons on drawing fundamentals.","Education"),
 ("https://www.cs.cmu.edu/~rgs/alice-table.html","Alice's Adventures in Wonderland","An old hand-made academic web page.","Retro"),
 ("https://sr.ht","sourcehut","Hacker's forge for software development.","Developer"),
 ("https://justinjackson.ca","Justin Jackson","Personal site of an indie maker.","Personal"),
]

def run():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(Website.id).limit(1)): return
        for u, t, d, c in SEED:
            db.add(Website(url=u.rstrip("/"), title=t, description=d, category=c, source="seed", language="en"))
        db.commit()
    cache.push_frontier([s[0] for s in SEED])
    print("Seeded", len(SEED), "websites")

if __name__ == "__main__":
    run()
