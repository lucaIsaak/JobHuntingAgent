"""Abstract Scraper interface that every job-site adapter implements."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from jobhunter.models.job import JobPosting
from jobhunter.models.search_criteria import SearchCriteria


class Scraper(ABC):
    """Contract for a job-source adapter."""

    @abstractmethod
    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        """Return job postings that roughly match given criteria."""
        raise NotImplementedError
