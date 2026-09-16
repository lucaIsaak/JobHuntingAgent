"""Lightweight keyword-relevance scoring for the no-profile search path.

Pure token overlap, no ML, no candidate profile required. Not a competitor to the full
matching engine (constraints.py/lexical.py/semantic.py/fusion.py) — this exists only to give
a sensible sort order over prefiltered jobs when there's no CV to actually match against.
"""

from __future__ import annotations

from jobhunter.jobs.schema import Job
from jobhunter.matching.semantic import tokenize


def score_by_keywords(query_text: str, job: Job) -> float:
    """0-100 relevance score: Jaccard overlap between the query text and the job's title
    plus description."""
    query_tokens = set(tokenize(query_text))
    if not query_tokens:
        return 0.0
    job_tokens = set(tokenize(f"{job.normalized_title} {job.description}"))
    if not job_tokens:
        return 0.0
    overlap = len(query_tokens & job_tokens)
    union = len(query_tokens | job_tokens)
    return round((overlap / union) * 100, 1) if union else 0.0
