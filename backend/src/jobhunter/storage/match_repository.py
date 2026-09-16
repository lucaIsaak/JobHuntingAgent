"""SQLite persistence for match runs (JSON-blob pattern, same as `search_runs` in repository.py)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jobhunter.matching.schema import MatchRun


class MatchRepository:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS match_runs (
                    run_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    run_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save_match_run(self, run: MatchRun) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO match_runs (run_id, profile_id, run_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run.run_id, run.profile_id, run.model_dump_json(), run.created_at),
            )

    def get_match_run(self, run_id: str) -> MatchRun | None:
        with self._connect() as conn:
            row = conn.execute("SELECT run_json FROM match_runs WHERE run_id = ?", (run_id,)).fetchone()
        return MatchRun.model_validate_json(row[0]) if row else None
