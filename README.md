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

Early scaffolding. Functionality (which sites are scraped vs. queried via API, matching approach, auth handling) is still being decided — see `technical-description.md`.
