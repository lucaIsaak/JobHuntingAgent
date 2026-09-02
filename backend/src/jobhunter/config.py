"""Runtime settings, loaded from environment variables / .env."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Job Hunting Agent API"
    app_version: str = "0.1.0"


settings = Settings()
