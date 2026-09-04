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

The local workflow is functional: CV upload, profile extraction, configurable searches, ranking, five offline source catalogs, and saved search runs are supported. To include current jobs from Arbeitnow's public API, start the backend with `JOBHUNTER_LIVE_JOBS=true`; provider failures fail closed and the local catalog remains available.

```bash
cd backend
JOBHUNTER_LIVE_JOBS=true ./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000
```

To also include Adzuna, register at [developer.adzuna.com](https://developer.adzuna.com/), then start with:

```bash
JOBHUNTER_LIVE_JOBS=true ADZUNA_APP_ID=your-id ADZUNA_APP_KEY=your-key ./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000
```

Set `ADZUNA_COUNTRY` to another supported country code when needed.

The live adapter is intentionally limited to a compliant public API. Each provider should be integrated through its documented API rather than by bypassing authentication or scraping restricted pages.
