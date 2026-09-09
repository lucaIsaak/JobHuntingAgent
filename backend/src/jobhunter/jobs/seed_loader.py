"""Loads jobs from a JSON file into the jobs database and rebuilds the TF-IDF corpus stats."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from jobhunter.jobs.schema import Job
from jobhunter.matching.semantic import build_corpus_stats
from jobhunter.storage.jobs_repository import JobsRepository

logger = logging.getLogger(__name__)


def load_jobs_from_json(path: str | Path, repo: JobsRepository) -> int:
    """Validates each entry in the JSON file against `Job`, upserts it, then rebuilds
    `corpus_stats` from every job's text so semantic-layer IDF stays current. Returns the number
    of jobs loaded."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("expected a JSON array of job objects")

    jobs = [Job.model_validate(entry) for entry in raw]
    repo.upsert_jobs(jobs)

    document_frequency, document_count = build_corpus_stats(repo.all_job_texts())
    repo.save_corpus_stats(document_frequency, document_count)

    logger.info("loaded %d jobs from %s, corpus now has %d documents", len(jobs), path, document_count)
    return len(jobs)
