"""Runtime settings, loaded from environment variables / .env."""

import os
import json
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=True)


def _json_mapping(name: str) -> dict[str, list[str]]:
    try:
        value = json.loads(os.getenv(name, "{}"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Job Hunting Agent API"
    app_version: str = "0.1.0"
    database_path: str = os.getenv("JOBHUNTER_DB_PATH", str(BASE_DIR / "data" / "jobhunter.sqlite3"))
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
    adzuna_country: str = os.getenv("ADZUNA_COUNTRY", "de")
    jooble_endpoint: str = os.getenv("JOOBLE_ENDPOINT", "")
    jooble_api_key: str = os.getenv("JOOBLE_API_KEY", "")
    arbeitsagentur_endpoint: str = os.getenv("ARBEITSAGENTUR_ENDPOINT", "")
    arbeitsagentur_token: str = os.getenv("ARBEITSAGENTUR_TOKEN", "")
    eures_endpoint: str = os.getenv("EURES_ENDPOINT", "")
    eures_token: str = os.getenv("EURES_TOKEN", "")
    greenhouse_boards: dict[str, list[str]] = field(
        default_factory=lambda: _json_mapping("GREENHOUSE_BOARDS_JSON")
    )
    lever_sites: dict[str, list[str]] = field(
        default_factory=lambda: _json_mapping("LEVER_SITES_JSON")
    )


settings = Settings()
