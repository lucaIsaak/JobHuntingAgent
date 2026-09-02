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


settings = Settings()
