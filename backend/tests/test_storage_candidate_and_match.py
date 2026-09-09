from datetime import UTC, datetime

from jobhunter.candidate.schema import Candidate, CandidateProfile
from jobhunter.matching.schema import MatchFilters, MatchRun, MatchWeights
from jobhunter.storage.candidate_repository import CandidateRepository
from jobhunter.storage.match_repository import MatchRepository


def test_candidate_repository_profile_roundtrip(tmp_path):
    repo = CandidateRepository(database_path=str(tmp_path / "candidates.sqlite3"))
    profile = CandidateProfile(profile_id="p1", candidate_id="c1", full_name="Jane Doe")
    repo.save_profile(profile)

    fetched = repo.get_profile("p1")
    assert fetched is not None
    assert fetched.full_name == "Jane Doe"

    candidate = repo.get_candidate("c1")
    assert candidate is not None
    assert candidate.latest_profile_id == "p1"


def test_candidate_repository_save_profile_updates_latest_pointer(tmp_path):
    repo = CandidateRepository(database_path=str(tmp_path / "candidates.sqlite3"))
    repo.save_candidate(
        Candidate(candidate_id="c1", created_at=datetime.now(UTC).isoformat(), latest_profile_id="p1")
    )
    repo.save_profile(CandidateProfile(profile_id="p1", candidate_id="c1"))
    repo.save_profile(CandidateProfile(profile_id="p2", candidate_id="c1"))

    candidate = repo.get_candidate("c1")
    assert candidate.latest_profile_id == "p2"
    # both profile versions remain retrievable
    assert repo.get_profile("p1") is not None
    assert repo.get_profile("p2") is not None


def test_candidate_repository_get_missing_profile_returns_none(tmp_path):
    repo = CandidateRepository(database_path=str(tmp_path / "candidates.sqlite3"))
    assert repo.get_profile("nope") is None


def test_match_repository_roundtrip(tmp_path):
    repo = MatchRepository(database_path=str(tmp_path / "matches.sqlite3"))
    run = MatchRun(
        run_id="r1", profile_id="p1", weights_used=MatchWeights(), filters_used=MatchFilters(),
        created_at=datetime.now(UTC).isoformat(), results=[],
    )
    repo.save_match_run(run)

    fetched = repo.get_match_run("r1")
    assert fetched is not None
    assert fetched.profile_id == "p1"


def test_match_repository_missing_run_returns_none(tmp_path):
    repo = MatchRepository(database_path=str(tmp_path / "matches.sqlite3"))
    assert repo.get_match_run("nope") is None
