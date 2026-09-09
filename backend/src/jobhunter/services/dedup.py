"""Removes duplicate postings for the same role across sites."""

from jobhunter.models.job import JobPosting


def deduplicate_postings(postings: list[JobPosting]) -> list[JobPosting]:
    """Keep the first posting for each normalized title/company/location key."""

    seen: set[tuple[str, str, str]] = set()
    unique: list[JobPosting] = []

    for posting in postings:
        key = (
            posting.title.strip().lower(),
            posting.company.strip().lower(),
            posting.location.strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(posting)

    return unique
