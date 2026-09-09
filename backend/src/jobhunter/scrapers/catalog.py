"""Shared filtering and query-building for the local job-source catalog."""

from collections.abc import Sequence

from jobhunter.models.job import JobPosting
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria


def build_search_query(profile: CandidateProfile, criteria: SearchCriteria, max_terms: int = 4) -> str:
    """Merge the CV-derived title/skills with the user's explicit role/keywords into one query.

    Used to pre-filter API calls (Adzuna, Jooble, Bundesagentur) that accept a free-text search
    term. Capped at max_terms so the merged query doesn't over-constrain the API's AND-style
    text match; filter_postings and rank_jobs narrow further downstream regardless.
    """
    ordered_terms = [criteria.role, *profile.titles[:1], *criteria.keywords, *profile.skills[:2]]

    seen: set[str] = set()
    merged: list[str] = []
    for term in ordered_terms:
        key = (term or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(term.strip())
        if len(merged) >= max_terms:
            break
    return " ".join(merged)


def filter_postings(
    postings: Sequence[JobPosting], criteria: SearchCriteria
) -> list[JobPosting]:
    """Apply the common search filters used by each source adapter."""
    results = list(postings)

    if criteria.role:
        role_terms = criteria.role.lower().split()
        results = [
            posting
            for posting in results
            if all(term in posting.title.lower() for term in role_terms)
        ]

    if criteria.location:
        location = criteria.location.lower()
        results = [
            posting for posting in results if location in posting.location.lower()
        ]

    if criteria.remote_only:
        results = [posting for posting in results if posting.is_remote]

    if criteria.employment_types:
        allowed = set(criteria.employment_types)
        results = [posting for posting in results if posting.employment_type in allowed]

    if criteria.keywords:
        keywords = [keyword.lower() for keyword in criteria.keywords]
        results = [
            posting
            for posting in results
            if any(
                keyword in f"{posting.title} {posting.description} {posting.company}".lower()
                for keyword in keywords
            )
        ]

    return results
