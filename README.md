# project-idea-discovery

Daily, an automated Claude routine pulls Reddit RSS feeds, picks 3 promising
project ideas, scores them, and commits a dated file to `ideas/`.

## How it works

1. A scheduled remote agent runs every day at **6am America/Los_Angeles** (14:00 UTC).
2. The agent fetches RSS from the feeds in [`sources.md`](sources.md).
3. It filters out titles already in [`archive/seen-titles.txt`](archive/seen-titles.txt)
   so the same idea isn't suggested twice.
4. It picks the 3 strongest candidates and scores each on:
   - **Usability** (1-10) — how many people would actually use it
   - **Token cost** (S/M/L) — estimated cost to implement with Claude
   - **Time to build** (hours)
   - **Novelty** (1-10) — how original
   - **Tech risk** (low/med/high) — APIs, scraping, ML, infra complexity
5. Writes `ideas/YYYY-MM-DD.md`, appends new titles to `archive/seen-titles.txt`,
   and pushes.

## Picking one to implement

Open the latest file under `ideas/`, pick a winner, and ask Claude to implement
it. (Implementation flow is separate from this repo.)

## Editing sources

Edit [`sources.md`](sources.md) — one RSS URL per line, lines starting with `#`
are ignored.
