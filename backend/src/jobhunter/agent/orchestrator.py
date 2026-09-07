"""Coordinates scrapers, deduplication, matching and ranking into one search run."""

from collections.abc import Sequence
from dataclasses import dataclass

from jobhunter.models.job import JobPosting, MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings
from jobhunter.services.dedup import deduplicate_postings
from jobhunter.services.matcher import rank_jobs


@dataclass
class SearchOutcome:
    """Ranked results plus the raw, pre-dedup postings each source returned."""

    results: list[MatchResult]
    raw_postings: list[JobPosting]


def _balance_by_source(ranked: list[MatchResult], limit: int) -> list[MatchResult]:
    """Cap each source's share of the limit so one prolific source can't crowd out the rest."""
    if len(ranked) <= limit:
        return ranked

    sources = list(dict.fromkeys(result.job.source for result in ranked))
    cap = max(1, limit // len(sources))

    buckets: dict[str, list[MatchResult]] = {source: [] for source in sources}
    for result in ranked:
        buckets[source := result.job.source].append(result)

    selected: list[MatchResult] = []
    leftover: list[MatchResult] = []
    for source in sources:
        selected.extend(buckets[source][:cap])
        leftover.extend(buckets[source][cap:])

    if len(selected) < limit:
        leftover.sort(key=lambda result: result.score, reverse=True)
        selected.extend(leftover[: limit - len(selected)])

    selected.sort(key=lambda result: result.score, reverse=True)
    return selected[:limit]


class JobSearchOrchestrator:
    """Executes scraper aggregation and matching."""

    def __init__(self, scrapers: Sequence[Scraper]) -> None:
        self._scrapers = list(scrapers)

    def run_search(self, profile: CandidateProfile, criteria: SearchCriteria) -> SearchOutcome:
        postings = []
        for scraper in self._scrapers:
            scraper_sources = getattr(scraper, "sources", ())
            if criteria.sources and scraper_sources and not set(scraper_sources) & set(criteria.sources):
                continue
            if hasattr(scraper, "search_for_profile"):
                postings.extend(scraper.search_for_profile(profile, criteria))
            else:
                postings.extend(scraper.search(criteria))

        unique_postings = deduplicate_postings(postings)
        filtered_postings = filter_postings(unique_postings, criteria)
        ranked = rank_jobs(profile=profile, criteria=criteria, postings=filtered_postings)
        results = _balance_by_source(ranked, criteria.limit)
        return SearchOutcome(results=results, raw_postings=postings)
