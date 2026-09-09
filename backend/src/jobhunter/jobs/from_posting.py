"""Converts a live-scraped `JobPosting` into the matcher's structured `Job` schema.

A smaller, job-side analogue of the CV extractor: reuses the same catalogs/heuristics
(`candidate/normalize.py`) rather than duplicating them, so a skill or industry tag means the
same thing on both sides of a match. Free-text scraped postings give no reliable must-have/
nice-to-have, requirement, language, or certification signal, so those all default to
empty/absent rather than being guessed — inventing them would let Layer A hard-knockout a
candidate over a constraint the posting never actually stated.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from jobhunter.candidate.normalize import (
    DOMAIN_SIGNALS,
    SKILLS_CATALOG,
    contains_phrase,
    infer_seniority,
    normalize,
    normalize_skill,
    normalize_title,
)
from jobhunter.jobs.schema import Job, JobSkill
from jobhunter.models.job import JobPosting
from jobhunter.services.profile_extractor import extract_years_of_experience

_ALL_SKILL_TERMS = sorted({term for terms in SKILLS_CATALOG.values() for term in terms}, key=len, reverse=True)


def _job_id_for_url(url: str) -> str:
    """Deterministic id so re-discovering the same posting on a later search upserts instead of
    duplicating."""
    return "live:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _remote_type(posting: JobPosting) -> str:
    if posting.is_remote:
        return "remote"
    if "hybrid" in posting.description.lower():
        return "hybrid"
    return "onsite"


def convert_posting(posting: JobPosting) -> Job:
    combined_text = f"{posting.title} {posting.description}"
    normalized_text = normalize(combined_text)

    matched_skills = sorted({term for term in _ALL_SKILL_TERMS if contains_phrase(normalized_text, term)})
    skills = [
        JobSkill(name=term, normalized_name=normalize_skill(term), is_must_have=False)
        for term in matched_skills
    ]

    industry_tags = sorted(
        tag for tag, phrases in DOMAIN_SIGNALS.items() if any(contains_phrase(normalized_text, phrase) for phrase in phrases)
    )
    seniority, _ = infer_seniority([posting.title], years=None)

    return Job(
        job_id=_job_id_for_url(posting.url),
        title=posting.title,
        normalized_title=normalize_title(posting.title),
        company=posting.company,
        industry=industry_tags[0] if industry_tags else None,
        function=industry_tags[1] if len(industry_tags) > 1 else None,
        location=posting.location,
        remote_type=_remote_type(posting),
        employment_type=posting.employment_type.value,
        seniority=seniority,
        description=posting.description,
        skills=skills,
        years_experience_min=extract_years_of_experience(posting.description),
        years_experience_max=None,
        updated_at=datetime.now(UTC).isoformat(),
    )
