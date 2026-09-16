"""SQLite persistence for the rich candidate profile subsystem.

Follows the same pattern as `storage/repository.py`: raw sqlite3, CREATE TABLE IF NOT EXISTS,
JSON-blob columns for the nested profile (matching always loads one profile at a time in Python
and never needs to SQL-query into its sub-lists).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jobhunter.candidate.schema import Candidate, CandidateProfile


class CandidateRepository:
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
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    latest_profile_id TEXT NOT NULL,
                    cv_filename TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_profiles (
                    profile_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
                )
                """
            )

    def save_candidate(self, candidate: Candidate) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO candidates (candidate_id, created_at, latest_profile_id, cv_filename)
                VALUES (?, ?, ?, ?)
                """,
                (candidate.candidate_id, candidate.created_at, candidate.latest_profile_id, candidate.cv_filename),
            )

    def get_candidate(self, candidate_id: str) -> Candidate | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT candidate_id, created_at, latest_profile_id, cv_filename FROM candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if not row:
            return None
        return Candidate(candidate_id=row[0], created_at=row[1], latest_profile_id=row[2], cv_filename=row[3])

    def save_profile(self, profile: CandidateProfile) -> None:
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO candidate_profiles (profile_id, candidate_id, profile_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (profile.profile_id, profile.candidate_id, profile.model_dump_json(), created_at),
            )
            existing = conn.execute(
                "SELECT candidate_id FROM candidates WHERE candidate_id = ?", (profile.candidate_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE candidates SET latest_profile_id = ? WHERE candidate_id = ?",
                    (profile.profile_id, profile.candidate_id),
                )
            else:
                conn.execute(
                    "INSERT INTO candidates (candidate_id, created_at, latest_profile_id, cv_filename) VALUES (?, ?, ?, ?)",
                    (profile.candidate_id, created_at, profile.profile_id, None),
                )

    def get_profile(self, profile_id: str) -> CandidateProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json FROM candidate_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
        if not row:
            return None
        return CandidateProfile.model_validate_json(row[0])
