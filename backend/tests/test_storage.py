from jobhunter.models.job import EmploymentType, JobPosting, MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.storage.repository import SQLiteRepository, StoredSearchRun


def test_sqlite_repository_persists_profiles_and_runs(tmp_path):
    db_path = tmp_path / "jobhunter-test.db"
    repository = SQLiteRepository(str(db_path))

    profile = CandidateProfile(
        profile_id="profile-1",
        raw_cv_text="python fastapi",
        skills=["python", "fastapi"],
        titles=["engineer"],
        preferred_locations=["Berlin"],
    )
    repository.save_profile(profile)

    stored_profile = repository.get_profile("profile-1")
    assert stored_profile is not None
    assert stored_profile.skills == ["python", "fastapi"]

    criteria = SearchCriteria(role="engineer", location="Berlin", limit=5)
    result = MatchResult(
        job=JobPosting(
            source="linkedin",
            title="Python Engineer",
            company="Acme",
            location="Berlin",
            is_remote=True,
            employment_type=EmploymentType.FULL_TIME,
            description="Build APIs",
            url="https://example.com/job",
        ),
        score=0.9,
        reasons=["title matches requested role"],
    )

    repository.save_search_run(
        StoredSearchRun(
            run_id="run-1",
            profile_id="profile-1",
            criteria=criteria,
            results=[result],
        )
    )

    stored_run = repository.get_search_run("run-1")
    assert stored_run is not None
    assert stored_run.profile_id == "profile-1"
    assert stored_run.criteria.role == "engineer"
    assert stored_run.results[0].job.title == "Python Engineer"
