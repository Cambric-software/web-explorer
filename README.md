# Website Explorer — "Discover the Internet Again."
By Cambric Software & Hardware Studios · Founder Asser Karim

**Live site:** https://cambric-software.github.io/web-explorer/

## Runs 100% on GitHub
- `docs/` — the website (GitHub Pages serves it).
- `docs/data/sites.json` — the website database. `stats.json` — discovery statistics.
- `engine/crawl.py` — discovery + verification engine.
- `.github/workflows/discover.yml` — runs the engine every 6 hours (and on demand from the Actions tab). It finds new sites (Hacker News, Lobsters, links from known sites, user submissions), checks they load and aren't parked, sorts them into categories, re-checks older sites, removes sites that fail 3 checks, and commits the updated database.
- Beta: first 10 days check 50 new candidates per run, then 25.
- Submissions: anyone opens an issue with the "Submit a website" form; the next run picks it up.
- Admin: the repo owner — edit `docs/data/sites.json` to remove/fix sites, run the workflow manually from Actions.
- Votes and favorites are saved in each visitor's browser.

## Full server version
`backend/`, `frontend/`, `docker-compose.yml` contain the full server version (accounts, shared voting, admin dashboard). It needs a server host; run with `docker compose up --build`.
