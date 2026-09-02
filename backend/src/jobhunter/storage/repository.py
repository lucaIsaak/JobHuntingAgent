"""Persistence layer for search runs and job postings."""

from collections.abc import Sequence
from dataclasses import dataclass

from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria


@dataclass
class StoredSearchRun:
    run_id: str
    profile_id: str
    criteria: SearchCriteria
    results: Sequence[MatchResult]


class InMemoryRepository:
    """Simple in-memory repository used by the MVP."""

    def __init__(self) -> None:
        self._profiles: dict[str, CandidateProfile] = {}
        self._search_runs: dict[str, StoredSearchRun] = {}

    def save_profile(self, profile: CandidateProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get_profile(self, profile_id: str) -> CandidateProfile | None:
        return self._profiles.get(profile_id)

    def save_search_run(self, search_run: StoredSearchRun) -> None:
        self._search_runs[search_run.run_id] = search_run

    def get_search_run(self, run_id: str) -> StoredSearchRun | None:
        return self._search_runs.get(run_id)
