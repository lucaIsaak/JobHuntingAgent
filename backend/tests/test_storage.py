from jobhunter.models.job import EmploymentType, JobPosting, MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria, SeniorityLevel
from jobhunter.storage.repository import SourceHealth, SQLiteRepository, StoredSearchRun


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


def test_sqlite_repository_persists_seniority_and_years_of_experience(tmp_path):
    db_path = tmp_path / "jobhunter-test.db"
    repository = SQLiteRepository(str(db_path))

    profile = CandidateProfile(
        profile_id="profile-2",
        raw_cv_text="senior python engineer",
        skills=["python"],
        seniority=SeniorityLevel.SENIOR,
        years_of_experience=7,
        skill_categories={"programming_languages": ["python"]},
    )
    repository.save_profile(profile)

    stored_profile = repository.get_profile("profile-2")
    assert stored_profile is not None
    assert stored_profile.seniority == SeniorityLevel.SENIOR
    assert stored_profile.years_of_experience == 7
    assert stored_profile.skill_categories == {"programming_languages": ["python"]}


def test_sqlite_repository_persists_discovered_jobs(tmp_path):
    db_path = tmp_path / "jobhunter-test.db"
    repository = SQLiteRepository(str(db_path))

    postings = [
        JobPosting(
            source="arbeitnow",
            title="Backend Engineer",
            company="Acme",
            location="Berlin",
            is_remote=True,
            employment_type=EmploymentType.FULL_TIME,
            description="Build APIs",
            url="https://example.com/job-1",
        ),
        JobPosting(
            source="bundesagentur",
            title="Software Developer",
            company="Beispiel GmbH",
            location="Munich",
            is_remote=False,
            employment_type=EmploymentType.FULL_TIME,
            description="Entwickeln",
            url="https://example.com/job-2",
        ),
    ]

    repository.save_discovered_jobs("run-1", postings)

    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT run_id, source, title, location FROM discovered_jobs ORDER BY id"
        ).fetchall()

    assert rows == [
        ("run-1", "arbeitnow", "Backend Engineer", "Berlin"),
        ("run-1", "bundesagentur", "Software Developer", "Munich"),
    ]


def test_sqlite_repository_persists_and_updates_source_health(tmp_path):
    db_path = tmp_path / "jobhunter-test.db"
    repository = SQLiteRepository(str(db_path))

    finding = SourceHealth(
        source="jooble",
        status="error",
        discovered_count=0,
        checked_at="2026-09-09T12:00:00+00:00",
        http_status=400,
        error_detail="HTTP 400: bad request",
        diagnosis="Wrong field name in request body.",
        proposed_fix_content="# fixed file content",
        fix_file_path=str(tmp_path / "jooble.py"),
        fix_status="proposed",
    )
    repository.save_source_health(finding)

    stored = repository.get_all_source_health()
    assert len(stored) == 1
    assert stored[0].source == "jooble"
    assert stored[0].status == "error"
    assert stored[0].fix_status == "proposed"
    assert stored[0].diagnosis == "Wrong field name in request body."

    # Re-saving the same source (as a fresh check would) replaces the row rather than duplicating it.
    repository.save_source_health(
        SourceHealth(
            source="jooble",
            status="ok",
            discovered_count=5,
            checked_at="2026-09-09T12:30:00+00:00",
        )
    )
    stored = repository.get_all_source_health()
    assert len(stored) == 1
    assert stored[0].status == "ok"
    assert stored[0].discovered_count == 5

    repository.update_fix_status("jooble", "dismissed")
    stored = repository.get_all_source_health()
    assert stored[0].fix_status == "dismissed"
