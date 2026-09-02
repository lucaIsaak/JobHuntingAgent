"""Persistence layer for search runs and job postings."""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria


@dataclass
class StoredSearchRun:
    run_id: str
    profile_id: str
    criteria: SearchCriteria
    results: Sequence[MatchResult]


class Repository(Protocol):
    def save_profile(self, profile: CandidateProfile) -> None: ...

    def get_profile(self, profile_id: str) -> CandidateProfile | None: ...

    def save_search_run(self, search_run: StoredSearchRun) -> None: ...

    def get_search_run(self, run_id: str) -> StoredSearchRun | None: ...


class InMemoryRepository:
    """Simple in-memory repository used by the MVP."""

    def __init__(self) -> None:
        self._profiles: dict[str, CandidateProfile] = {}
        self._search_runs: dict[str, StoredSearchRun] = {}

    def save_profile(self, profile: CandidateProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get_profile(self, profile_id: str) -> CandidateProfile | None:
        return self._profiles.get(profile_id)

    def save_search_run(self, search_run: StoredSearchRun) -> None:
        self._search_runs[search_run.run_id] = search_run

    def get_search_run(self, run_id: str) -> StoredSearchRun | None:
        return self._search_runs.get(run_id)


class SQLiteRepository:
    """SQLite-backed repository for profiles and search runs."""

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
                CREATE TABLE IF NOT EXISTS profiles (
                    profile_id TEXT PRIMARY KEY,
                    raw_cv_text TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    titles_json TEXT NOT NULL,
                    preferred_locations_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_runs (
                    run_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    criteria_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(profile_id)
                )
                """
            )

    def save_profile(self, profile: CandidateProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO profiles
                (profile_id, raw_cv_text, skills_json, titles_json, preferred_locations_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    profile.profile_id,
                    profile.raw_cv_text,
                    json.dumps(profile.skills),
                    json.dumps(profile.titles),
                    json.dumps(profile.preferred_locations),
                ),
            )

    def get_profile(self, profile_id: str) -> CandidateProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT profile_id, raw_cv_text, skills_json, titles_json, preferred_locations_json
                FROM profiles
                WHERE profile_id = ?
                """,
                (profile_id,),
            ).fetchone()

        if not row:
            return None

        return CandidateProfile(
            profile_id=row[0],
            raw_cv_text=row[1],
            skills=json.loads(row[2]),
            titles=json.loads(row[3]),
            preferred_locations=json.loads(row[4]),
        )

    def save_search_run(self, search_run: StoredSearchRun) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO search_runs (run_id, profile_id, criteria_json, results_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    search_run.run_id,
                    search_run.profile_id,
                    search_run.criteria.model_dump_json(),
                    json.dumps([result.model_dump(mode="json") for result in search_run.results]),
                ),
            )

    def get_search_run(self, run_id: str) -> StoredSearchRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT run_id, profile_id, criteria_json, results_json
                FROM search_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if not row:
            return None

        return StoredSearchRun(
            run_id=row[0],
            profile_id=row[1],
            criteria=SearchCriteria.model_validate_json(row[2]),
            results=[MatchResult.model_validate(item) for item in json.loads(row[3])],
        )
