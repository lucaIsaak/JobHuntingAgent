from jobhunter.agent.orchestrator import JobSearchOrchestrator
from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria


def _profile() -> CandidateProfile:
    return CandidateProfile(profile_id="p1", raw_cv_text="engineer", skills=["python"])


def _posting(source: str, title: str = "Engineer") -> JobPosting:
    return JobPosting(
        source=source,
        title=title,
        company="Acme",
        location="Berlin",
        employment_type=EmploymentType.FULL_TIME,
        description="Build things.",
        url=f"https://example.com/{source}",
    )


class _StubScraper:
    def __init__(self, sources, postings):
        self.sources = sources
        self._postings = postings

    def search(self, criteria):
        return self._postings


def test_run_search_counts_postings_per_source():
    orchestrator = JobSearchOrchestrator(
        scrapers=[
            _StubScraper(("healthy",), [_posting("healthy"), _posting("healthy")]),
            _StubScraper(("empty",), []),
        ]
    )

    outcome = orchestrator.run_search(profile=_profile(), criteria=SearchCriteria(role="Engineer"))

    assert outcome.source_counts == {"healthy": 2, "empty": 0}


def test_run_search_only_counts_sources_actually_queried():
    orchestrator = JobSearchOrchestrator(
        scrapers=[
            _StubScraper(("wanted",), [_posting("wanted")]),
            _StubScraper(("skipped",), [_posting("skipped")]),
        ]
    )

    outcome = orchestrator.run_search(
        profile=_profile(), criteria=SearchCriteria(role="Engineer", sources=["wanted"])
    )

    assert outcome.source_counts == {"wanted": 1}


def test_fetch_postings_returns_raw_postings_and_counts_without_filtering_or_ranking():
    orchestrator = JobSearchOrchestrator(
        scrapers=[
            _StubScraper(("healthy",), [_posting("healthy", title="Unrelated Title")]),
            _StubScraper(("empty",), []),
        ]
    )

    postings, source_counts = orchestrator.fetch_postings(
        profile=_profile(), criteria=SearchCriteria(role="Engineer")
    )

    # Unlike run_search(), fetch_postings() does no title/role filtering or ranking — a
    # posting whose title doesn't match the role is still returned as-is.
    assert [posting.title for posting in postings] == ["Unrelated Title"]
    assert source_counts == {"healthy": 1, "empty": 0}


def test_fetch_postings_reuses_source_selection_used_by_run_search():
    orchestrator = JobSearchOrchestrator(
        scrapers=[
            _StubScraper(("wanted",), [_posting("wanted")]),
            _StubScraper(("skipped",), [_posting("skipped")]),
        ]
    )

    postings, source_counts = orchestrator.fetch_postings(
        profile=_profile(), criteria=SearchCriteria(role="Engineer", sources=["wanted"])
    )

    assert [posting.source for posting in postings] == ["wanted"]
    assert source_counts == {"wanted": 1}


class _LocationAwareScraper:
    """Records the `criteria.location` it was called with -- lets a test prove each location in
    a multi-location fetch actually reached the scraper as its own separate call."""

    def __init__(self, sources):
        self.sources = sources
        self.seen_locations: list[str | None] = []

    def search(self, criteria):
        self.seen_locations.append(criteria.location)
        return [_posting(self.sources[0], title=f"Job in {criteria.location}")]


def test_fetch_postings_for_locations_queries_each_location_and_merges():
    scraper = _LocationAwareScraper(("stub",))
    orchestrator = JobSearchOrchestrator(scrapers=[scraper])

    postings, source_counts = orchestrator.fetch_postings_for_locations(
        profile=_profile(),
        criteria=SearchCriteria(role="Engineer"),
        locations=["Germany", "France", "Spain"],
    )

    assert scraper.seen_locations == ["Germany", "France", "Spain"]
    assert [posting.title for posting in postings] == ["Job in Germany", "Job in France", "Job in Spain"]
    assert source_counts == {"stub": 3}


def test_fetch_postings_for_locations_empty_list_falls_back_to_a_single_call():
    scraper = _LocationAwareScraper(("stub",))
    orchestrator = JobSearchOrchestrator(scrapers=[scraper])

    postings, source_counts = orchestrator.fetch_postings_for_locations(
        profile=_profile(),
        criteria=SearchCriteria(role="Engineer", location="Berlin"),
        locations=[],
    )

    assert scraper.seen_locations == ["Berlin"]  # criteria.location untouched, exactly one call
    assert source_counts == {"stub": 1}
