# Website Explorer
**"Discover the Internet Again."**
Created by Cambric Software & Hardware Studios — Founder: Asser Karim

A self-growing website discovery platform: Discover → Verify → Store → Categorize → Serve → Discover more.

## Stack
- Frontend: React + TypeScript + Tailwind (Vite)
- Backend: FastAPI
- Database: PostgreSQL
- Cache / broker: Redis
- Background jobs: Celery (worker + beat)
- Deployment: Docker Compose

## Quick start
```bash
cp .env.example .env        # edit SECRET_KEY and ADMIN_EMAIL
docker compose up --build
```
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

The database is seeded with starter sites on first boot. Register with the email in `ADMIN_EMAIL` to get admin access.

## How Explore works
- **Beta mode** (first `BETA_DAYS` days, default 10): each click generates up to 50 candidates, verifies them all in parallel, stores the working ones and returns one.
- **After beta**: 50% Database Mode (random stored, alive site), 50% Discovery Mode (find → verify → save → return).

Candidate sources: links extracted from known sites, crawling, search (DuckDuckGo HTML), user submissions. `discovery.py` has a hook for the future Cambric AI Agent.

## Verification checks
1. HTTP 200  2. not 404/500/503  3. not parked ("buy this domain", "domain for sale", "coming soon"…)
4. real content (min text length)  5. loads within 8s timeout  6. unique (normalized URL)
7. safety filter (blocklist of keywords/TLDs, optional Google Safe Browsing key)

## Background jobs (Celery beat)
- Re-verify sites older than 30 days every hour (dead → hidden)
- Background discovery batch every 15 minutes

## Hidden gem score
Like +1, Hidden Gem +3, Favorite +5, Dislike -1.

## Ranks
Explorer, Scout, Navigator, Pathfinder, Adventurer, Master Explorer, Internet Cartographer, Legendary Explorer — based on sites visited.

## Project layout
```
backend/app/       FastAPI app, models, verifier, discovery, celery tasks
frontend/src/      React pages: Explore, Search, Collections, Profile, Admin, Login
docker-compose.yml
```
