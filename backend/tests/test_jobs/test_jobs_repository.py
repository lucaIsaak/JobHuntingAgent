from jobhunter.jobs.schema import Job, JobLanguageRequirement, JobSkill
from jobhunter.matching.schema import MatchFilters
from jobhunter.storage.jobs_repository import JobsRepository


def _job(**overrides) -> Job:
    defaults = dict(
        job_id="j1", title="Data Analyst", normalized_title="Data Analyst", company="Acme",
        industry="technology", location="Berlin, Germany", remote_type="hybrid",
        employment_type="full_time", seniority="mid",
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_upsert_and_get_job(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job())
    fetched = repo.get_job("j1")
    assert fetched is not None
    assert fetched.title == "Data Analyst"
    assert repo.count() == 1


def test_upsert_replaces_existing_job(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(title="Old Title"))
    repo.upsert_job(_job(title="New Title"))
    assert repo.count() == 1
    assert repo.get_job("j1").title == "New Title"


def test_prefilter_by_location(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", location="Berlin, Germany"))
    repo.upsert_job(_job(job_id="j2", location="New York, USA"))
    results = repo.prefilter(MatchFilters(location="Berlin"))
    assert {job.job_id for job in results} == {"j1"}


def test_prefilter_by_remote_type_and_seniority(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", remote_type="remote", seniority="senior"))
    repo.upsert_job(_job(job_id="j2", remote_type="onsite", seniority="senior"))
    repo.upsert_job(_job(job_id="j3", remote_type="remote", seniority="junior"))
    results = repo.prefilter(MatchFilters(remote_type="remote", seniority="senior"))
    assert {job.job_id for job in results} == {"j1"}


def test_prefilter_by_language(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(
        job_id="j1", languages_required=[JobLanguageRequirement(language="German", level="C1")]
    ))
    repo.upsert_job(_job(job_id="j2", languages_required=[]))
    results = repo.prefilter(MatchFilters(language="German"))
    assert {job.job_id for job in results} == {"j1"}


def test_job_ids_matching_skills(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=True)]))
    repo.upsert_job(_job(job_id="j2", skills=[JobSkill(name="SQL", normalized_name="SQL", is_must_have=True)]))
    matched = repo.job_ids_matching_skills(["Python"])
    assert matched == {"j1"}


def test_required_certifications_for_job(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", required_certifications=["PMP"]))
    assert repo.required_certifications_for_job("j1") == {"pmp"}


def test_corpus_stats_roundtrip(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.save_corpus_stats({"python": 5, "sql": 3}, document_count=10)
    stats, count = repo.get_corpus_stats()
    assert stats == {"python": 5, "sql": 3}
    assert count == 10
