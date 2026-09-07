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

