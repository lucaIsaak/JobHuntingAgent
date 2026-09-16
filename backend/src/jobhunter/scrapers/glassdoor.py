"""Placeholder Glassdoor adapter.

Glassdoor has no public search API and scraping it directly violates its
terms of service, so this returns a single synthetic posting rather than
making any network call. It exists so the source appears in searches and in
the source-health panel like every other adapter.
"""

from __future__ import annotations

from collections.abc import Sequence

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper


class GlassdoorScraper(Scraper):
    """Synthetic stand-in adapter for Glassdoor."""

    sources = ("glassdoor",)

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        role = criteria.role or " ".join(criteria.keywords) or "Open role"
        keyword_text = f" Skills: {', '.join(criteria.keywords)}." if criteria.keywords else ""
        return [
            JobPosting(
                source="glassdoor",
                title=role,
                company="Sample Employer",
                location=criteria.location or "Unspecified",
                is_remote=criteria.remote_only,
                employment_type=criteria.employment_types[0] if criteria.employment_types else EmploymentType.FULL_TIME,
                description=(
                    f"Placeholder Glassdoor listing for '{role}'.{keyword_text} "
                    "Glassdoor has no public search API."
                ),
                url="https://www.glassdoor.com/Job/index.htm",
            )
        ]
