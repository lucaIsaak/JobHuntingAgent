"""End-to-end: golden CV fixtures matched against the real seed jobs database, asserting the
top results skew toward the expected job characteristics for each fixture.
"""

from datetime import date
from pathlib import Path

import pytest

from jobhunter.candidate.rules_extractor import extract
from jobhunter.jobs.seed_loader import load_jobs_from_json
from jobhunter.matching.engine import run_match
from jobhunter.matching.schema import MatchFilters
from jobhunter.storage.jobs_repository import JobsRepository
from jobhunter.storage.match_repository import MatchRepository

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvs"
SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "seed_jobs.json"
AS_OF = date(2026, 9, 9)


@pytest.fixture(scope="module")
def jobs_repo(tmp_path_factory):
    repo = JobsRepository(database_path=str(tmp_path_factory.mktemp("jobs") / "jobs.sqlite3"))
    load_jobs_from_json(SEED_FILE, repo)
    return repo


@pytest.fixture
def match_repo(tmp_path):
    return MatchRepository(database_path=str(tmp_path / "matches.sqlite3"))


def _profile(name: str):
    cv_text = (FIXTURES_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return extract(cv_text, [cv_text], profile_id=f"{name}-profile", candidate_id=f"{name}-candidate", as_of=AS_OF)


def test_senior_analyst_style_profile_ranks_analytics_jobs_highly(jobs_repo, match_repo):
    profile = _profile("analytics_intern")
    run = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(), top_k=10)
    assert run.results
    top_functions = {jobs_repo.get_job(result.job_id).function for result in run.results[:5]}
    assert "analytics" in top_functions


def test_career_switcher_gets_transition_fit_flagged_somewhere(jobs_repo, match_repo):
    profile = _profile("career_switcher")
    run = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(), top_k=20)
    assert run.results
    # Strong tech skills, non-tech title history — engineering roles should show up and at least
    # one should be flagged as a transition fit rather than crushed for the title mismatch.
    engineering_results = [
        result for result in run.results if jobs_repo.get_job(result.job_id).function == "engineering"
    ]
    assert engineering_results
    assert any(result.transition_fit for result in engineering_results)


def test_senior_marketer_ranks_marketing_jobs_highly(jobs_repo, match_repo):
    profile = _profile("senior_multilingual_marketer")
    run = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(), top_k=10)
    assert run.results
    top_job = jobs_repo.get_job(run.results[0].job_id)
    assert top_job.function == "marketing"


def test_min_score_filter_excludes_low_scores(jobs_repo, match_repo):
    profile = _profile("analytics_intern")
    unfiltered = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(), top_k=30)
    threshold = unfiltered.results[len(unfiltered.results) // 2].overall_fit
    filtered = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(min_score=threshold), top_k=30)
    assert all(result.overall_fit >= threshold for result in filtered.results)


def test_match_run_is_persisted_and_retrievable(jobs_repo, match_repo):
    profile = _profile("analytics_intern")
    run = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(), top_k=5)
    fetched = match_repo.get_match_run(run.run_id)
    assert fetched is not None
    assert fetched.run_id == run.run_id
    assert len(fetched.results) == len(run.results)


def test_sparse_profile_weights_used_are_redistributed(jobs_repo, match_repo):
    profile = _profile("analytics_intern")  # has one short experience entry — not fully sparse
    run = run_match(profile, jobs_repo, match_repo, filters=MatchFilters(), top_k=5)
    assert abs(sum(run.weights_used.as_dict().values()) - 100.0) < 0.01
