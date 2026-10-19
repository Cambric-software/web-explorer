RANKS = [(0,"Explorer"),(10,"Scout"),(50,"Navigator"),(150,"Pathfinder"),(400,"Adventurer"),
         (1000,"Master Explorer"),(2500,"Internet Cartographer"),(5000,"Legendary Explorer")]
GEM_POINTS = {"like": 1, "gem": 3, "favorite": 5, "dislike": -1}

def rank_for(visited: int) -> str:
    name = RANKS[0][1]
    for t, n in RANKS:
        if visited >= t: name = n
    return name

def badges(stats: dict) -> list[str]:
    b = []
    if stats["sites_discovered"] >= 1: b.append("First Discovery")
    if stats["sites_visited"] >= 100: b.append("100 Websites Visited")
    if stats["sites_visited"] >= 1000: b.append("1000 Websites Visited")
    if stats["hidden_gems_found"] >= 10: b.append("10 Hidden Gems Found")
    cats = stats["category_counts"]
    if cats.get("Retro", 0) >= 25: b.append("Retro Explorer")
    if cats.get("Personal", 0) + cats.get("Developer", 0) >= 25: b.append("Indie Explorer")
    if cats.get("Tools", 0) >= 25: b.append("Tool Hunter")
    if cats.get("Communities", 0) >= 25: b.append("Community Discoverer")
    return b
