"""Coordinates scrapers, deduplication, matching and ranking into one search run."""

from collections.abc import Sequence

from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.services.dedup import deduplicate_postings
from jobhunter.services.matcher import rank_jobs


class JobSearchOrchestrator:
    """Executes scraper aggregation and matching."""

    def __init__(self, scrapers: Sequence[Scraper]) -> None:
        self._scrapers = list(scrapers)

    def run_search(self, profile: CandidateProfile, criteria: SearchCriteria) -> list[MatchResult]:
        postings = []
        for scraper in self._scrapers:
            postings.extend(scraper.search(criteria))

        unique_postings = deduplicate_postings(postings)
        return rank_jobs(profile=profile, criteria=criteria, postings=unique_postings)
