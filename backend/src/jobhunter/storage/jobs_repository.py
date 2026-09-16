"""SQLite persistence for the curated jobs database.

Real columns on `jobs` cover everything the structured prefilter needs (seniority, remote_type,
employment_type, industry, location, years_experience_min/max). `job_skills`/`job_languages`/
`job_certifications` are inverted-index side tables used both by the prefilter and by the API's
filters, so Layer A's language/cert knockouts and the `language` job filter can run as real SQL
instead of scanning JSON blobs. `corpus_stats` caches document frequencies for the TF-IDF semantic
layer so IDF stays stable across match runs (see `matching/semantic.py`).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from jobhunter.jobs.schema import Job
from jobhunter.matching.schema import MatchFilters


class JobsRepository:
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
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    normalized_title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    industry TEXT,
                    function TEXT,
                    location TEXT,
                    remote_type TEXT NOT NULL,
                    employment_type TEXT NOT NULL,
                    seniority TEXT,
                    years_experience_min INTEGER,
                    years_experience_max INTEGER,
                    updated_at TEXT NOT NULL,
                    job_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_skills (
                    job_id TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    is_must_have INTEGER NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_skills_name ON job_skills(normalized_name)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_languages (
                    job_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    level TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_languages_lang ON job_languages(language)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_certifications (
                    job_id TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS corpus_stats (
                    term TEXT PRIMARY KEY,
                    document_frequency INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS corpus_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_feedback (
                    job_id TEXT PRIMARY KEY,
                    rating TEXT NOT NULL,
                    rated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
                """
            )

    def upsert_job(self, job: Job) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs
                (job_id, title, normalized_title, company, industry, function, location, remote_type,
                 employment_type, seniority, years_experience_min, years_experience_max, updated_at, job_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id, job.title, job.normalized_title, job.company, job.industry, job.function,
                    job.location, job.remote_type, job.employment_type, job.seniority,
                    job.years_experience_min, job.years_experience_max, job.updated_at,
                    job.model_dump_json(),
                ),
            )
            conn.execute("DELETE FROM job_skills WHERE job_id = ?", (job.job_id,))
            conn.executemany(
                "INSERT INTO job_skills (job_id, normalized_name, is_must_have) VALUES (?, ?, ?)",
                [(job.job_id, skill.normalized_name.lower(), int(skill.is_must_have)) for skill in job.skills],
            )
            conn.execute("DELETE FROM job_languages WHERE job_id = ?", (job.job_id,))
            conn.executemany(
                "INSERT INTO job_languages (job_id, language, level) VALUES (?, ?, ?)",
                [(job.job_id, requirement.language.lower(), requirement.level) for requirement in job.languages_required],
            )
            conn.execute("DELETE FROM job_certifications WHERE job_id = ?", (job.job_id,))
            conn.executemany(
                "INSERT INTO job_certifications (job_id, normalized_name) VALUES (?, ?)",
                [(job.job_id, name.lower()) for name in job.required_certifications],
            )

    def upsert_jobs(self, jobs: Sequence[Job]) -> None:
        for job in jobs:
            self.upsert_job(job)

    def get_job(self, job_id: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute("SELECT job_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return Job.model_validate_json(row[0]) if row else None

    def set_job_feedback(self, job_id: str, rating: str | None) -> None:
        """`rating` is 'like', 'dislike', or None to clear a previous rating (toggle-off)."""
        with self._connect() as conn:
            if rating is None:
                conn.execute("DELETE FROM job_feedback WHERE job_id = ?", (job_id,))
                return
            conn.execute(
                """
                INSERT INTO job_feedback (job_id, rating, rated_at) VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET rating = excluded.rating, rated_at = excluded.rated_at
                """,
                (job_id, rating, datetime.now(UTC).isoformat()),
            )

    def get_job_feedback(self, job_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT rating FROM job_feedback WHERE job_id = ?", (job_id,)).fetchone()
        return row[0] if row else None

    def all_job_feedback(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT job_id, rating FROM job_feedback").fetchall()
        return dict(rows)

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def all_job_texts(self) -> list[str]:
        """title + must-have requirements + description, per job — the corpus for TF-IDF IDF."""
        with self._connect() as conn:
            rows = conn.execute("SELECT job_json FROM jobs").fetchall()
        texts = []
        for (job_json,) in rows:
            job = Job.model_validate_json(job_json)
            texts.append(" ".join([job.title, " ".join(job.requirements_must), job.description]))
        return texts

    def prefilter(self, filters: MatchFilters | None = None, required_languages: Sequence[str] = ()) -> list[Job]:
        """Structured SQL prefilter: user-supplied filters plus (optionally) a language
        requirement gate, both resolved against real columns/side tables.

        `seniority` and `industry` are frequently NULL for live-scraped postings (the title
        alone often isn't enough to confidently infer either) — treating an untagged job as
        "fails the filter" would silently exclude most of the database on any of these filters.
        An untagged job passes through instead; only a job with a real, conflicting tag is
        excluded. Same principle for `language` below, via the job_languages side table.

        `locations`/`languages` (plural) are OR'd together when given -- a job matching any one
        of several selected countries/languages is kept, needed so a search spanning multiple
        countries doesn't have its own broader fetch immediately undone by a filter that only
        kept one of them. `location`/`language` (singular) stay as a fallback for callers that
        never populate the plural fields (GET /api/jobs, POST /candidates/{id}/match).
        """
        clauses: list[str] = []
        params: list[object] = []

        if filters:
            if filters.locations:
                clauses.append("(" + " OR ".join("location LIKE ?" for _ in filters.locations) + ")")
                params.extend(f"%{location}%" for location in filters.locations)
            elif filters.location:
                clauses.append("location LIKE ?")
                params.append(f"%{filters.location}%")
            if filters.seniority:
                clauses.append("(seniority = ? OR seniority IS NULL)")
                params.append(filters.seniority)
            if filters.industry:
                clauses.append("(industry = ? OR industry IS NULL)")
                params.append(filters.industry)
            if filters.remote_type:
                clauses.append("remote_type = ?")
                params.append(filters.remote_type)
            if filters.employment_type:
                clauses.append("employment_type = ?")
                params.append(filters.employment_type)
            if filters.title:
                clauses.append("normalized_title LIKE ?")
                params.append(f"%{filters.title}%")
            if filters.company:
                clauses.append("company LIKE ?")
                params.append(f"%{filters.company}%")

        query = "SELECT job_id, job_json FROM jobs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            job_ids = {row[0] for row in rows}

            language_values = (
                filters.languages if (filters and filters.languages)
                else ([filters.language] if (filters and filters.language) else [])
            )
            if language_values:
                all_language_job_ids = {
                    row[0] for row in conn.execute("SELECT DISTINCT job_id FROM job_languages").fetchall()
                }
                placeholders = ",".join("?" for _ in language_values)
                matching_language_job_ids = {
                    row[0]
                    for row in conn.execute(
                        f"SELECT job_id FROM job_languages WHERE language IN ({placeholders})",
                        [language.lower() for language in language_values],
                    ).fetchall()
                }
                # A job with no stated language requirement at all isn't disqualified — only
                # exclude a job that has language data but none of it matches any requested language.
                job_ids -= all_language_job_ids - matching_language_job_ids

        return [Job.model_validate_json(job_json) for job_id, job_json in rows if job_id in job_ids]

    def job_ids_matching_skills(self, normalized_skill_names: Sequence[str]) -> set[str]:
        """Inverted skill index: jobs sharing at least one skill with the candidate."""
        if not normalized_skill_names:
            return set()
        placeholders = ",".join("?" for _ in normalized_skill_names)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT job_id FROM job_skills WHERE normalized_name IN ({placeholders})",
                [name.lower() for name in normalized_skill_names],
            ).fetchall()
        return {row[0] for row in rows}

    def required_certifications_for_job(self, job_id: str) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT normalized_name FROM job_certifications WHERE job_id = ?", (job_id,)
            ).fetchall()
        return {row[0] for row in rows}

    def save_corpus_stats(self, document_frequencies: dict[str, int], document_count: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM corpus_stats")
            conn.executemany(
                "INSERT INTO corpus_stats (term, document_frequency) VALUES (?, ?)",
                list(document_frequencies.items()),
            )
            conn.execute(
                "INSERT OR REPLACE INTO corpus_meta (key, value) VALUES ('document_count', ?)",
                (str(document_count),),
            )

    def get_corpus_stats(self) -> tuple[dict[str, int], int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT term, document_frequency FROM corpus_stats").fetchall()
            meta_row = conn.execute(
                "SELECT value FROM corpus_meta WHERE key = 'document_count'"
            ).fetchone()
        document_count = int(meta_row[0]) if meta_row else 0
        return {term: frequency for term, frequency in rows}, document_count
