# Frontend

Small Vite UI for uploading a CV, configuring a job search, and reviewing ranked results.

## Run locally

Start the backend first:

```bash
cd ../backend
./.venv/bin/uvicorn jobhunter.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Set `VITE_API_URL` when the backend is running on a different host or port.
