"""Glassdoor adapter."""

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings


class GlassdoorScraper(Scraper):
    """Offline Glassdoor-shaped source used for local development."""

    def search(self, criteria: SearchCriteria):
        postings = [
            JobPosting(
                source="glassdoor",
                title="Software Engineer, Platform",
                company="Brightside Labs",
                location="Hamburg",
                is_remote=True,
                employment_type=EmploymentType.CONTRACT,
                description="Ship reliable backend systems with FastAPI and AWS.",
                url="https://www.glassdoor.com/job-listing/jobhunter-glassdoor-1",
            ),
        ]
        return filter_postings(postings, criteria)
