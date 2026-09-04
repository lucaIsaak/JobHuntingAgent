"""Xing adapter."""

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings


class XingScraper(Scraper):
    """Offline Xing-shaped source used for local development."""

    def search(self, criteria: SearchCriteria):
        postings = [
            JobPosting(
                source="xing",
                title="Backend Engineer",
                company="Rhein Digital",
                location="Cologne",
                employment_type=EmploymentType.FULL_TIME,
                description="Build Python services with SQL and cloud tooling.",
                url="https://www.xing.com/jobs/cologne-backend-engineer-1",
            ),
        ]
        return filter_postings(postings, criteria)
