"""Shared filtering for the local job-source catalog."""

from collections.abc import Sequence

from jobhunter.models.job import JobPosting
from jobhunter.models.search_criteria import SearchCriteria


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

    return results[: criteria.limit]
