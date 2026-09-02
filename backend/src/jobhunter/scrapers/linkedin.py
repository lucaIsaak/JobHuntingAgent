"""LinkedIn adapter."""

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper


class LinkedInScraper(Scraper):
    """Stub scraper that returns static sample data for MVP development."""

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
        results = self._jobs

        if criteria.role:
            role = criteria.role.lower()
            results = [j for j in results if role in j.title.lower()]

        if criteria.location:
            location = criteria.location.lower()
            results = [j for j in results if location in j.location.lower()]

        if criteria.remote_only:
            results = [j for j in results if j.is_remote]

        if criteria.employment_types:
            allowed = set(criteria.employment_types)
            results = [j for j in results if j.employment_type in allowed]

        if criteria.keywords:
            keywords = [k.lower() for k in criteria.keywords]
            results = [
                j
                for j in results
                if any(
                    keyword in f"{j.title} {j.description} {j.company}".lower()
                    for keyword in keywords
                )
            ]

        return results[: criteria.limit]
