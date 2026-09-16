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
