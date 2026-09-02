"""Indeed adapter."""

from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper


class IndeedScraper(Scraper):
    """Placeholder adapter."""

    def search(self, criteria: SearchCriteria):
        return []
