"""LinkedIn adapter."""

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings


class LinkedInScraper(Scraper):
    """Offline LinkedIn-shaped source used for local development."""

    def __init__(self) -> None:
        self._jobs = [
            JobPosting(
                source="linkedin",
                title="Python Backend Engineer",
                company="Acme AI",
                location="Berlin",
                is_remote=True,
                employment_type=EmploymentType.FULL_TIME,
                description="Build backend services in Python and FastAPI.",
                url="https://www.linkedin.com/jobs/view/1",
            ),
            JobPosting(
                source="linkedin",
                title="Data Analyst",
                company="Insight Labs",
                location="Munich",
                is_remote=False,
                employment_type=EmploymentType.FULL_TIME,
                description="Analyze hiring funnel and build dashboards.",
                url="https://www.linkedin.com/jobs/view/2",
            ),
            JobPosting(
                source="linkedin",
                title="ML Engineer Intern",
                company="Acme AI",
                location="Berlin",
                is_remote=False,
                employment_type=EmploymentType.INTERN,
                description="Support NLP and recommendation model work.",
                url="https://www.linkedin.com/jobs/view/3",
            ),
        ]

    def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        return filter_postings(self._jobs, criteria)
