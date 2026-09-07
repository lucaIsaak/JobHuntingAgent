# Job Hunting Agent

An agent that screens job boards (LinkedIn, Xing, StepStone, Indeed, Glassdoor, ...) and surfaces postings matching a user's profile.

## Repository structure

```
backend/                   Python backend
  src/jobhunter/
    agent/                 Orchestrator: runs scrapers, then dedup -> match -> rank
    scrapers/               One adapter per job site, all implementing scrapers/base.py's Scraper interface
    models/                 Shared data schemas (JobPosting, SearchCriteria)
    services/               matcher.py (CV/profile matching), dedup.py (cross-site duplicates)
    storage/                Persistence layer for search runs and results
    api/                    HTTP routes the frontend calls
    config.py, main.py
  tests/                    Mirrors src/ layout
  pyproject.toml, .env.example

frontend/                  Separate UI app (framework TBD), talks to backend/ via its API

docs/                       Architecture notes, design decisions
data/                        Local/sample data (gitignored, except .gitkeep)
scripts/                     Dev/setup scripts
```

## Status

The local workflow is functional: CV upload, profile extraction, configurable searches, ranking, five offline source catalogs, and saved search runs are supported. Arbeitnow's and Bundesagentur für Arbeit's public job APIs are enabled by default with no configuration, so a fresh checkout already returns current real listings alongside the offline catalog; provider failures fail closed and the local catalog remains available.

```bash
cd backend
./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000
```

To also include Adzuna, register at [developer.adzuna.com](https://developer.adzuna.com/), then start with:

```bash
ADZUNA_APP_ID=your-id ADZUNA_APP_KEY=your-key ./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000
```

Set `ADZUNA_COUNTRY` to another supported country code when needed.

The live adapters are intentionally limited to compliant public APIs. Each provider should be integrated through its documented API rather than by bypassing authentication or scraping restricted pages.

Additional configured sources activate automatically once their credentials are set: `JOOBLE_API_KEY` (with optional `JOOBLE_ENDPOINT`), `ARBEITSAGENTUR_ENDPOINT`/`ARBEITSAGENTUR_TOKEN` (Bundesagentur already works without these — set them only to override the defaults), and `EURES_ENDPOINT`/`EURES_TOKEN`. Greenhouse and Lever company boards are configured with `GREENHOUSE_BOARDS_JSON` and `LEVER_SITES_JSON`; the CV parser infers industries such as consulting, finance, healthcare, marketing, and technology and searches the matching board group.

Every posting each source returns for a search — before dedup and ranking — is logged to the `discovered_jobs` table in the SQLite database (`backend/data/jobhunter.sqlite3` by default), tagged by `run_id` and `source`, so you can inspect what each provider actually returned, e.g. `sqlite3 backend/data/jobhunter.sqlite3 "select source, title, location from discovered_jobs"`.
