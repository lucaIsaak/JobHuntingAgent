"""Indeed adapter."""

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings


class IndeedScraper(Scraper):
    """Offline Indeed-shaped source used for local development."""

    def search(self, criteria: SearchCriteria):
        postings = [
            JobPosting(
                source="indeed",
                title="Python API Developer",
                company="Northstar Systems",
                location="Berlin",
                is_remote=True,
                employment_type=EmploymentType.FULL_TIME,
                description="Maintain Python APIs and Docker deployments.",
                url="https://de.indeed.com/viewjob?jk=jobhunter-indeed-1",
            ),
        ]
        return filter_postings(postings, criteria)
