"""Persistence layer for search runs and job postings."""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from jobhunter.models.job import JobPosting, MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria


@dataclass
class StoredSearchRun:
    run_id: str
    profile_id: str
    criteria: SearchCriteria
    results: Sequence[MatchResult]


@dataclass
class SourceHealth:
    """Latest health-check finding for one job source."""

    source: str
    status: str  # ok | no_results | error
    discovered_count: int
    checked_at: str
    http_status: int | None = None
    error_detail: str | None = None
    diagnosis: str | None = None
    proposed_fix_content: str | None = None
    fix_file_path: str | None = None
    fix_status: str = "none"  # none | proposed | applied | dismissed
    try_status: str = "none"  # none | worked | failed
    try_detail: str | None = None


class Repository(Protocol):
    def save_profile(self, profile: CandidateProfile) -> None: ...

    def get_profile(self, profile_id: str) -> CandidateProfile | None: ...

    def save_search_run(self, search_run: StoredSearchRun) -> None: ...

    def get_search_run(self, run_id: str) -> StoredSearchRun | None: ...

    def save_discovered_jobs(self, run_id: str, postings: Sequence[JobPosting]) -> None: ...

    def save_source_health(self, finding: SourceHealth) -> None: ...

    def get_all_source_health(self) -> list[SourceHealth]: ...

    def update_fix_status(self, source: str, fix_status: str) -> None: ...

    def update_try_result(self, source: str, try_status: str, try_detail: str | None) -> None: ...


class InMemoryRepository:
    """Simple in-memory repository used by the MVP."""

    def __init__(self) -> None:
        self._profiles: dict[str, CandidateProfile] = {}
        self._search_runs: dict[str, StoredSearchRun] = {}
        self._discovered_jobs: list[tuple[str, JobPosting]] = []
        self._source_health: dict[str, SourceHealth] = {}

    def save_profile(self, profile: CandidateProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get_profile(self, profile_id: str) -> CandidateProfile | None:
        return self._profiles.get(profile_id)

    def save_search_run(self, search_run: StoredSearchRun) -> None:
        self._search_runs[search_run.run_id] = search_run

    def get_search_run(self, run_id: str) -> StoredSearchRun | None:
        return self._search_runs.get(run_id)

    def save_discovered_jobs(self, run_id: str, postings: Sequence[JobPosting]) -> None:
        self._discovered_jobs.extend((run_id, posting) for posting in postings)

    def save_source_health(self, finding: SourceHealth) -> None:
        self._source_health[finding.source] = finding

    def get_all_source_health(self) -> list[SourceHealth]:
        return list(self._source_health.values())

    def update_fix_status(self, source: str, fix_status: str) -> None:
        if source in self._source_health:
            self._source_health[source].fix_status = fix_status

    def update_try_result(self, source: str, try_status: str, try_detail: str | None) -> None:
        if source in self._source_health:
            self._source_health[source].try_status = try_status
            self._source_health[source].try_detail = try_detail


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
                    preferred_locations_json TEXT NOT NULL,
                    industries_json TEXT NOT NULL DEFAULT '[]',
                    seniority TEXT,
                    years_of_experience INTEGER,
                    skill_categories_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            try:
                conn.execute("ALTER TABLE profiles ADD COLUMN industries_json TEXT NOT NULL DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE profiles ADD COLUMN seniority TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE profiles ADD COLUMN years_of_experience INTEGER")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE profiles ADD COLUMN skill_categories_json TEXT NOT NULL DEFAULT '{}'")
            except sqlite3.OperationalError:
                pass
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discovered_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    is_remote INTEGER NOT NULL,
                    employment_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    url TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES search_runs(run_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_health (
                    source TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    discovered_count INTEGER NOT NULL,
                    checked_at TEXT NOT NULL,
                    http_status INTEGER,
                    error_detail TEXT,
                    diagnosis TEXT,
                    proposed_fix_content TEXT,
                    fix_file_path TEXT,
                    fix_status TEXT NOT NULL DEFAULT 'none',
                    try_status TEXT NOT NULL DEFAULT 'none',
                    try_detail TEXT
                )
                """
            )
            try:
                conn.execute("ALTER TABLE source_health ADD COLUMN try_status TEXT NOT NULL DEFAULT 'none'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE source_health ADD COLUMN try_detail TEXT")
            except sqlite3.OperationalError:
                pass

    def save_profile(self, profile: CandidateProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO profiles
                (profile_id, raw_cv_text, skills_json, titles_json, preferred_locations_json, industries_json,
                 seniority, years_of_experience, skill_categories_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.profile_id,
                    profile.raw_cv_text,
                    json.dumps(profile.skills),
                    json.dumps(profile.titles),
                    json.dumps(profile.preferred_locations),
                    json.dumps(profile.industries),
                    profile.seniority.value if profile.seniority else None,
                    profile.years_of_experience,
                    json.dumps(profile.skill_categories),
                ),
            )

    def get_profile(self, profile_id: str) -> CandidateProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT profile_id, raw_cv_text, skills_json, titles_json, preferred_locations_json, industries_json,
                       seniority, years_of_experience, skill_categories_json
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
            industries=json.loads(row[5]),
            seniority=row[6],
            years_of_experience=row[7],
            skill_categories=json.loads(row[8]) if row[8] else {},
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

    def save_discovered_jobs(self, run_id: str, postings: Sequence[JobPosting]) -> None:
        if not postings:
            return

        discovered_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO discovered_jobs
                (run_id, source, title, company, location, is_remote, employment_type, description, url, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        posting.source,
                        posting.title,
                        posting.company,
                        posting.location,
                        int(posting.is_remote),
                        posting.employment_type.value,
                        posting.description,
                        posting.url,
                        discovered_at,
                    )
                    for posting in postings
                ],
            )

    def save_source_health(self, finding: SourceHealth) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_health
                (source, status, discovered_count, checked_at, http_status, error_detail,
                 diagnosis, proposed_fix_content, fix_file_path, fix_status, try_status, try_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    status=excluded.status,
                    discovered_count=excluded.discovered_count,
                    checked_at=excluded.checked_at,
                    http_status=excluded.http_status,
                    error_detail=excluded.error_detail,
                    diagnosis=excluded.diagnosis,
                    proposed_fix_content=excluded.proposed_fix_content,
                    fix_file_path=excluded.fix_file_path,
                    fix_status=excluded.fix_status,
                    try_status=excluded.try_status,
                    try_detail=excluded.try_detail
                """,
                (
                    finding.source,
                    finding.status,
                    finding.discovered_count,
                    finding.checked_at,
                    finding.http_status,
                    finding.error_detail,
                    finding.diagnosis,
                    finding.proposed_fix_content,
                    finding.fix_file_path,
                    finding.fix_status,
                    finding.try_status,
                    finding.try_detail,
                ),
            )

    def get_all_source_health(self) -> list[SourceHealth]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, status, discovered_count, checked_at, http_status, error_detail,
                       diagnosis, proposed_fix_content, fix_file_path, fix_status, try_status, try_detail
                FROM source_health
                ORDER BY source
                """
            ).fetchall()

        return [
            SourceHealth(
                source=row[0],
                status=row[1],
                discovered_count=row[2],
                checked_at=row[3],
                http_status=row[4],
                error_detail=row[5],
                diagnosis=row[6],
                proposed_fix_content=row[7],
                fix_file_path=row[8],
                fix_status=row[9],
                try_status=row[10],
                try_detail=row[11],
            )
            for row in rows
        ]

    def update_fix_status(self, source: str, fix_status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE source_health SET fix_status = ? WHERE source = ?",
                (fix_status, source),
            )

    def update_try_result(self, source: str, try_status: str, try_detail: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE source_health SET try_status = ?, try_detail = ? WHERE source = ?",
                (try_status, try_detail, source),
            )
