"""Abstract Scraper interface that every job-site adapter implements."""

from abc import ABC, abstractmethod


class Scraper(ABC):
    @abstractmethod
    def search(self, criteria):
        """Return an iterable of JobPosting objects matching the search criteria."""
        raise NotImplementedError
