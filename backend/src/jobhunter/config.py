"""Runtime settings, loaded from environment variables / .env."""

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Job Hunting Agent API"
    app_version: str = "0.1.0"
    database_path: str = os.getenv("JOBHUNTER_DB_PATH", str(BASE_DIR / "data" / "jobhunter.sqlite3"))
    live_jobs_enabled: bool = os.getenv("JOBHUNTER_LIVE_JOBS", "false").lower() == "true"
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
    adzuna_country: str = os.getenv("ADZUNA_COUNTRY", "de")


settings = Settings()
