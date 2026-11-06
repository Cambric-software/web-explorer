import json
import os
import re

SITES_PATH = "docs/data/sites.json"

if not os.path.exists(SITES_PATH):
    print(f"Error: {SITES_PATH} not found. Run from the repo root.")
    exit(1)

with open(SITES_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

sites = catalog.get("sites", [])
initial_count = len(sites)

# 1. Target URLs to permanently purge
REMOVE_URLS = {
    "https://strictllm.com",
    "https://wiki.tilde.green",
    "https://rakuraikou.neocities.org",
    "https://merisumu.nekoweb.org",
    "https://daisy.nekoweb.org",
    "https://kolala.neocities.org",
    "https://kunfucutsman.neocities.org",
    "https://leizy8499.neocities.org",
    "https://baggebo-the-goober.neocities.org",
    "https://philia995.neocities.org",
    "https://nickychaotix.neocities.org",
    "https://flimsknoght.neocities.org"
}

# 2. Polished titles and descriptions for high-quality sites that had messy metadata
POLISH_MAP = {
    "https://britains-disk.pages.dev": {
        "title": "Britain's Disk",
        "description": "An interactive fiscal simulation game where you delete or balance national budget categories to make government spending fit on a disk."
    },
    "https://ourspacevibes.com": {
        "title": "OurSpace — The MySpace Alternative",
        "description": "A retro social network recreating the classic early-2000s web: customize HTML profiles, pick your Top 8, and add profile music."
    },
    "https://atlyss.neocities.org": {
        "title": "Atlyss ORPG",
        "description": "Official site for Atlyss, an action indie online RPG with fluid retro controls, customizable combat, and handcrafted dungeons."
    },
    "https://undeadly.org": {
        "title": "The OpenBSD Journal",
        "description": "The premier community journal covering OpenBSD development, security advisories, release notes, and hacker culture."
    },
    "https://kitkatie.neocities.org": {
        "title": "KitKatie's Creative Corner",
        "description": "A vibrant personal creative site featuring animation projects, video commentary, and playful digital art."
    },
    "https://caby.neocities.org": {
        "title": "Caby's Abode",
        "description": "A cozy personal web home featuring handmade webcomics, personal art galleries, journal entries, and plushie collections."
    },
    "https://figurea.neocities.org": {
        "title": "Figurea Domain",
        "description": "An experimental digital garden and handmade web realm filled with interactive art, creative writing, and curiosities."
    },
    "https://misterdizzy.neocities.org": {
        "title": "Mister Dizzy",
        "description": "An old-school, hand-coded personal site celebrating nostalgic web design, creative experiments, and indie coding."
    },
    "https://jcw87.github.io": {
        "title": "JCW87 Web Experiments",
        "description": "Interactive HTML5 recreations and fan projects including Super Mario Bros World 1 and Undertale boss encounters."
    },
    "https://cherished-cat.neocities.org": {
        "title": "Cherished Cat",
        "description": "A charming indie personal blog featuring micro-essays, slice-of-life observations, and digital art doodles."
    },
    "https://faegardens333.neocities.org": {
        "title": "Fae Gardens",
        "description": "A whimsical personal digital sanctuary and garden dedicated to accessibility, gentle design, and cozy journaling."
    },
    "https://scripted.neocities.org": {
        "title": "Scripted Web Resources",
        "description": "Curated free webmaster tools, HTML templates, CSS snippets, and button assets for indie web builders."
    },
    "https://ocpdzim.neocities.org": {
        "title": "Zim's Corner",
        "description": "A cozy personal website featuring interactive community polls, quirky web experiments, and indie design logs."
    }
}

clean_sites = []
purged_count = 0
polished_count = 0

for site in sites:
    url = site.get("url", "").rstrip("/")
    # Check normalized URL
    if url in REMOVE_URLS or f"{url}/" in REMOVE_URLS:
        purged_count += 1
        continue
    
    if url in POLISH_MAP:
        site["title"] = POLISH_MAP[url]["title"]
        site["description"] = POLISH_MAP[url]["description"]
        polished_count += 1
    
    clean_sites.append(site)

catalog["sites"] = clean_sites

with open(SITES_PATH, "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print(f"Purge complete!")
print(f"Initial sites:  {initial_count}")
print(f"Purged:         {purged_count}")
print(f"Polished:       {polished_count}")
print(f"Remaining pure: {len(clean_sites)}")
