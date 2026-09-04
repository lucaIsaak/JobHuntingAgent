"""StepStone adapter."""

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings


class StepStoneScraper(Scraper):
    """Offline StepStone-shaped source used for local development."""

    def search(self, criteria: SearchCriteria):
        postings = [
            JobPosting(
                source="stepstone",
                title="Data Platform Engineer",
                company="Atlas Mobility",
                location="Munich",
                employment_type=EmploymentType.FULL_TIME,
                description="Design data pipelines with Python, SQL, and Kubernetes.",
                url="https://www.stepstone.de/stellenangebote--data-platform-engineer-1",
            ),
        ]
        return filter_postings(postings, criteria)
