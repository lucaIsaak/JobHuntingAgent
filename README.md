# Frontend

Small Vite UI for uploading a CV, configuring a job search, and reviewing ranked results.

## Run locally

Prerequisites:

- Python 3.11 or newer
- Node.js and npm

Use two terminals. Run the backend first.

### 1. Start the backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install -e '.[dev]'
./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000
```

Leave this terminal running. The API is available at `http://127.0.0.1:8000`.

### 2. Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173`.

If the backend runs on another host or port, set `VITE_API_URL` before starting Vite:

```bash
VITE_API_URL=http://127.0.0.1:8001 npm run dev
```

## Troubleshooting

- **`./.venv/bin/uvicorn` not found:** Run the backend setup commands above from the `backend` directory.
- **`ModuleNotFoundError` in the backend:** Reinstall the backend with `./.venv/bin/python -m pip install -e '.[dev]'`.
- **Port 8000 or 5173 is already in use:** Stop the process using the port, or start the service on another port. Keep `VITE_API_URL` aligned with the backend port.
- **The frontend cannot reach the API:** Confirm the backend is running, then check the browser URL and `VITE_API_URL`.
- **`npm: command not found`:** Install Node.js, then run `npm install` again in `frontend`.

## Kill the terminal 
kill $(lsof -ti :8080)

## CV-to-job matcher (backend/API only, no frontend UI yet)

This is a second, separate matching subsystem alongside the live-search flow described above. The
live-search flow (`/api/searches`) queries external job APIs (Adzuna, Jooble, Bundesagentur,
company boards) in real time. The CV-to-job matcher instead extracts a rich, provenance-tracked
candidate profile from an uploaded CV and ranks it against a **curated jobs database** you load
ahead of time — the two systems don't share data yet.

### How extraction works

Every CV upload always runs a rule-based extractor (`backend/src/jobhunter/candidate/
rules_extractor.py`) — regex/heuristics, no external calls, no API key needed. It's the default
and fully functional on its own: contact info, work history with parsed dates/durations/
achievements, education, skills (deduplicated, with recency/evidence-strength hints), languages,
certifications, projects, and inferred seniority, each with a source snippet and confidence score.

If `ANTHROPIC_API_KEY` is set in `.env`, an optional Claude-based extraction pass also runs
(`candidate/llm_extractor.py`) and its fields take priority where present; on any failure (missing
key, network error, malformed response) it silently falls back to the rules-only result — nothing
in the app requires the LLM to work.

### Set up

```bash
cd backend
./.venv/bin/python -m pip install -e '.[dev]'      # add '.[dev,llm]' to also install the optional anthropic SDK
```

### Load the seed jobs

```bash
cd backend
python scripts/load_jobs.py data/seed_jobs.json
```

This validates and loads the 31 seed postings in `backend/data/seed_jobs.json` (analytics, ML,
marketing, software engineering, and business/ops roles) into the jobs database and rebuilds the
TF-IDF corpus statistics used by the semantic-similarity layer. Re-run it any time you edit that
file or add your own jobs JSON.

### Upload a CV and run a match

With the backend running (`./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000`):

```bash
# 1. Upload a CV, get back the full structured profile (edit and PUT it back to correct
#    extraction errors before matching)
curl -F "cv_file=@resume.pdf" http://127.0.0.1:8000/api/candidates/upload-file

# 2. Run matching against the jobs database
curl -X POST http://127.0.0.1:8000/api/candidates/<profile_id>/match \
  -H "Content-Type: application/json" \
  -d '{"location": "Berlin", "remote_type": "remote", "min_score": 50, "top_k": 10}'

# 3. Re-fetch a previous run
curl http://127.0.0.1:8000/api/match-runs/<run_id>

# Browse the jobs database directly
curl "http://127.0.0.1:8000/api/jobs?industry=technology&employment_type=full_time"
```

Available match filters: `min_score`, `location`, `seniority`, `industry`, `remote_type`
(`onsite`/`hybrid`/`remote`), `language`, `employment_type`.

### How the matching weights work

Each match run produces an `overall_fit` score (0-100) fused from 8 subscores — `skills`,
`experience`, `seniority`, `semantic`, `industry`, `language`, `education`, `location` — each
independently weighted. Defaults: skills 30, experience 10, seniority 10, semantic 20, industry
10, language 10, education 5, location 5 (must sum to 100). Override any subset in the `/match`
request body under `"weights"`, e.g. `{"weights": {"skills": 40, "experience": 5, "seniority": 5,
"semantic": 15, "industry": 15, "language": 10, "education": 5, "location": 5}}`.

For a CV with no work history, the engine automatically redistributes the `experience`/`seniority`
weight into `education`/`semantic` and marks results `"confidence": "low"` — you don't need to set
this manually.

Each result also carries `match_reasons` (top positive contributors), `gap_reasons` (missing
must-have skills, seniority mismatch direction, missing required language, etc.), and structured
`evidence` pairing a candidate span with the job requirement it satisfies.

### Env vars

| Variable | Required | Purpose |
|---|---|---|
| `JOBHUNTER_DB_PATH` | no | SQLite file path (default `backend/data/jobhunter.sqlite3`, shared by both subsystems) |
| `ANTHROPIC_API_KEY` | no | Enables the optional LLM extraction pass; omit to run rules-only |

### Tests

```bash
cd backend
./.venv/bin/python -m pytest
```

Covers normalization, the rule-based extractor (including 3 golden CV fixtures — an analytics
intern, a career switcher, and a senior multilingual marketer — under `tests/fixtures/cvs/`), the
LLM extractor (fully mocked, no network/API key needed), constraint/lexical/semantic/fusion
scoring, and an end-to-end run against the real seed jobs database.