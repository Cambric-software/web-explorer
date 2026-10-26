# Website Explorer

[![Discovery engine](https://github.com/Cambric-software/web-explorer/actions/workflows/discover.yml/badge.svg)](https://github.com/Cambric-software/web-explorer/actions/workflows/discover.yml)

**Discover the Internet Again.** One click takes you somewhere new: an
independent, working website found, checked, and sorted by a robot.

Live at **[cambric-software.github.io/web-explorer](https://cambric-software.github.io/web-explorer/)**.
It runs entirely on free GitHub hosting, with no server, no accounts, and no paid
services.

> **Proprietary.** Copyright (c) 2026 Cambric Software. All rights reserved.
> Not open source. See [LICENSE](LICENSE).

---

## Table of contents

- [What this is](#what-this-is)
- [State of the project](#state-of-the-project)
- [Features](#features)
- [The discovery robot](#the-discovery-robot)
- [Verification checks](#verification-checks)
- [Categories](#categories)
- [Control room](#control-room)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Server version](#server-version)
- [What it is not](#what-it-is-not)
- [Licence](#licence)

---

## What this is

Website Explorer is a website discovery platform that grows by itself:

```text
Discover → Verify → Store → Categorize → Serve → Discover more
```

A robot on GitHub Actions finds candidate websites, checks that each one really
works, writes a name and description, sorts it into a category, and publishes
the result to the website. Visitors press **EXPLORE →** and get one of them.

Built by **Cambric Software & Hardware Studios**. Founder: Asser Karim.

## State of the project

| Part | Where | State |
|---|---|---|
| Website | `docs/` | Live on GitHub Pages |
| Discovery robot (v3) | `engine/crawl.py` | Runs every hour and on demand |
| Previews | `engine/screenshots.py` | Caches a picture of each website |
| Search-engine pages, RSS | `engine/publish.py` | Rebuilt on every run |
| Tests | `tests/` | Python unit tests for the robot's rules |
| Database | `docs/data/sites.json` | Reset on 2026-10-26; refilled by robot v3 |

## Features

**Exploring**
- One-click Explore with category and era filters (*Older than Google*,
  1990s, 2000s, 2010s, 2020s).
- 🎲 Surprise category, swipe-to-explore on phones, and keyboard shortcuts
  (`E` / `→` explore, `R` surprise, `/` search, `?` help).
- Site of the day, identical for every visitor.
- Rank progress from **Explorer** to **Legendary Explorer** (Scout, Navigator,
  Pathfinder, Adventurer, Master Explorer, Internet Cartographer on the way).

**Browsing**
- Search by name, description, and address; filter by category (with
  counts), language, and era; sort by newest, A–Z, or oldest archived.
- A real preview picture and an "online since" year from the Internet Archive.
- A graveyard of websites that stopped working.
- **Stumble Bar**: preview a website inside the page with Next, Gem, and
  Save buttons. Websites that refuse previews open in a new tab.
- **Time Warp** slider (1994–2026): restyles the site like the web of that era
  (Web 1.0, Y2K, Web 2.0) and shows only websites that already existed then.
- **Vibe Journeys**: themed trails of 8 websites (Small Web Wander, Maker's
  Bench, Curious Minds, Play & Make, Time Capsule, Fresh Off the Robot,
  Wildcard) walked one stop at a time in the Stumble Bar. New trails weekly.

**Keeping**
- Votes: 👍 Like +1, ❤️ Hidden Gem +3, 👎 Dislike −1, ⭐ Favorite +5.
- Favorites, named lists, shareable list links, and export to browser
  bookmarks.
- Settings, backup, and restore. Everything is stored in the visitor's own
  browser.

**Being found**
- A page per category, sitemap, RSS feed, share previews, an embeddable
  "site of the day" widget, and installable app support.

## The discovery robot

Defined in [`.github/workflows/discover.yml`](.github/workflows/discover.yml).
It runs every hour, when started by hand from the Actions tab or the control
room, and when a submission is labelled. The repository is public, so GitHub
Actions minutes are free. Each run does six jobs:

1. **Clean** — merges duplicates. One website per domain, whatever the
   `http`/`https`, `www`/`m.`, port, page path, or tracking tags. Two domains
   with the same name and description count as one website.
2. **Discover** — gathers candidates from Hacker News, Lobsters, Wiby's random
   small-web sites, Bear Blog, and visitor submissions (GitHub issues labelled
   `submit`). It checks 100 candidates per run during the 10-day beta and 60
   after.
3. **Deep crawl** — visits 25 known websites and their link pages, blogrolls,
   and webrings to find more of the independent web.
4. **Recheck** — revisits every website not checked in 30 days (then the
   oldest), up to 80 per run, and moves a website to the graveyard after 3
   failed checks in a row.
5. **Safety** — compares every website with the free URLhaus malware list and
   re-scans pages for unsafe content. Problem websites are flagged and hidden.
6. **Archive** — looks up the first Internet Archive year for up to 40
   websites per run.

Websites edited in the control room are **hand-checked**: the robot never
changes their name, description, category, flag, or status.

Every run is logged in `docs/data/stats.json`: candidates per source, reasons
for rejection, websites added, and websites that stopped working.

**Names and descriptions.** The robot decodes symbols, removes filler such as
"Home |", "Welcome to", platform names (Substack, WordPress…) or a bare
domain, prefers the site's own name, skips cookie banners and keyword lists,
and shortens long text at the end of a sentence.

## Verification checks

A candidate is stored only if it passes all of these:

| Check | Rule |
|---|---|
| Responds | HTTP 200, HTML page |
| Fast | Loads within 8 seconds |
| Not parked | No "domain for sale", "coming soon", default server pages |
| Not blocked | No bot walls, error pages, or "page not found" |
| Real content | At least 40 words of visible text |
| Unique | Its domain is not already stored |
| Safe | No gambling, adult, or scam signals; big platforms excluded |

## Categories

Art, Business, Communities, Developer, Education, Games, News, Personal,
Retro, Science, Technology, Tools, and Random.

The robot reads only what a visitor sees: the title, the description,
headings, and visible text, never code, scripts, menus, or footers. Words with
more than one meaning ("api", "code", "ai") count only in the name,
description, and headings. The title counts most,
then the description, then headings, then body text. Some addresses add a hint
(`.edu` → Education, `neocities.org` → Retro, `itch.io` → Games). When no
category clearly wins, the website goes to **Random** rather than a wrong
guess, and the robot records how sure it was.

## Control room

A private page for the owner. It is not linked anywhere; open it by clicking
the logo five times quickly or typing `cambric` on the site.

- **Password-protected.** Only a SHA-256 fingerprint of the password is in the
  code, never the password itself.
- **Locked GitHub key.** On first use the owner pastes a GitHub key once. It is
  encrypted with the password (PBKDF2, 600,000 rounds, AES-256-GCM) and saved
  as `docs/data/admin-key.json`. After that only the password is needed, on any
  device.
- **Moderation queue.** Every website appears as a card with its preview
  picture and an editable name, description, and category. Each one is
  *Unreviewed*, *Verified safe*, or *Flagged* (hidden from visitors).
- **Batch actions.** Select many cards and approve, flag, lock, unlock, or
  delete them at once. Filter by review state, category, status, or unsure
  category.
- Retire, revive, delete, or add websites; start the robot; view recent runs;
  delete every website.
- Websites edited by hand are marked 🔒 and the robot will not overwrite them.
  Saving replays only your changes on top of the newest database, so websites
  the robot found in the meantime are kept.

## Repository layout

```text
docs/                    The website served by GitHub Pages
  data/sites.json        Website database
  data/stats.json        Discovery statistics and run log
  admin.html, admin.js   Control room
  categories/            Generated category pages
engine/
  crawl.py               Discovery, verification, sorting, rechecks
  screenshots.py         Preview pictures
  publish.py             Category pages, sitemap, robots.txt, RSS
tests/                   Unit tests for the robot
.github/workflows/       The scheduled robot
backend/, frontend/      Full server version (FastAPI + React + Docker)
```

## Quick start

The website needs nothing installed. To run the robot locally (Python 3.12,
standard library only):

```powershell
python engine/crawl.py
python engine/screenshots.py
python engine/publish.py
python -m unittest discover tests
```

Preview the site from `docs/`:

```powershell
python -m http.server 8000 --directory docs
```

## Server version

`backend/`, `frontend/`, and `docker-compose.yml` hold a full-featured version
with FastAPI, PostgreSQL, Redis, Celery, and user accounts. Copy
`.env.example` to `.env` and run:

```powershell
docker compose up --build
```

Never commit the real `.env`.

## What it is not

- Not a search engine. It holds a curated, growing collection, not the whole
  web.
- Not a safety guarantee. Checks look for warning signs; they cannot prove a
  website is safe.
- Not an account system. Visitor data stays in each visitor's browser.

## Licence

This is proprietary software; the source is published for inspection and
personal use under the terms in [LICENSE](LICENSE).
