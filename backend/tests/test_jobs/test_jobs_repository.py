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


def test_prefilter_by_language_matches_stated_requirement(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(
        job_id="j1", languages_required=[JobLanguageRequirement(language="German", level="C1")]
    ))
    repo.upsert_job(_job(
        job_id="j2", languages_required=[JobLanguageRequirement(language="French", level="B2")]
    ))
    results = repo.prefilter(MatchFilters(language="German"))
    assert {job.job_id for job in results} == {"j1"}


def test_prefilter_by_language_does_not_exclude_untagged_jobs(tmp_path):
    """Live-scraped postings almost never carry real language data — a job with no stated
    language requirement at all must not be excluded by this filter, only a job that states a
    requirement and it doesn't match."""
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(
        job_id="j1", languages_required=[JobLanguageRequirement(language="German", level="C1")]
    ))
    repo.upsert_job(_job(job_id="j2", languages_required=[]))
    results = repo.prefilter(MatchFilters(language="German"))
    assert {job.job_id for job in results} == {"j1", "j2"}


def test_prefilter_by_seniority_does_not_exclude_untagged_jobs(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", seniority="junior"))
    repo.upsert_job(_job(job_id="j2", seniority="senior"))
    repo.upsert_job(_job(job_id="j3", seniority=None))
    results = repo.prefilter(MatchFilters(seniority="junior"))
    assert {job.job_id for job in results} == {"j1", "j3"}


def test_prefilter_by_industry_does_not_exclude_untagged_jobs(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", industry="fintech"))
    repo.upsert_job(_job(job_id="j2", industry="marketing"))
    repo.upsert_job(_job(job_id="j3", industry=None))
    results = repo.prefilter(MatchFilters(industry="fintech"))
    assert {job.job_id for job in results} == {"j1", "j3"}


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


def test_set_and_get_job_feedback(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1"))
    assert repo.get_job_feedback("j1") is None

    repo.set_job_feedback("j1", "like")
    assert repo.get_job_feedback("j1") == "like"


def test_set_job_feedback_replaces_not_duplicates(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1"))
    repo.set_job_feedback("j1", "like")
    repo.set_job_feedback("j1", "dislike")
    assert repo.get_job_feedback("j1") == "dislike"
    assert repo.all_job_feedback() == {"j1": "dislike"}


def test_set_job_feedback_none_clears_rating(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1"))
    repo.set_job_feedback("j1", "like")
    repo.set_job_feedback("j1", None)
    assert repo.get_job_feedback("j1") is None
    assert repo.all_job_feedback() == {}


def test_prefilter_by_locations_ors_multiple_countries(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", location="Berlin, Germany"))
    repo.upsert_job(_job(job_id="j2", location="Paris, France"))
    repo.upsert_job(_job(job_id="j3", location="Tokyo, Japan"))
    results = repo.prefilter(MatchFilters(locations=["Germany", "France"]))
    assert {job.job_id for job in results} == {"j1", "j2"}


def test_prefilter_by_locations_falls_back_to_singular_location(tmp_path):
    """Callers that only ever set the legacy singular field (GET /api/jobs, the CV-match
    endpoint) must keep working unchanged."""
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1", location="Berlin, Germany"))
    repo.upsert_job(_job(job_id="j2", location="Paris, France"))
    results = repo.prefilter(MatchFilters(location="Berlin"))
    assert {job.job_id for job in results} == {"j1"}


def test_prefilter_by_languages_ors_multiple_languages(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(
        job_id="j1", languages_required=[JobLanguageRequirement(language="German", level="C1")]
    ))
    repo.upsert_job(_job(
        job_id="j2", languages_required=[JobLanguageRequirement(language="French", level="B2")]
    ))
    repo.upsert_job(_job(
        job_id="j3", languages_required=[JobLanguageRequirement(language="Japanese", level="B2")]
    ))
    results = repo.prefilter(MatchFilters(languages=["German", "French"]))
    assert {job.job_id for job in results} == {"j1", "j2"}


def test_prefilter_by_languages_does_not_exclude_untagged_jobs(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(
        job_id="j1", languages_required=[JobLanguageRequirement(language="German", level="C1")]
    ))
    repo.upsert_job(_job(job_id="j2", languages_required=[]))
    results = repo.prefilter(MatchFilters(languages=["German", "French"]))
    assert {job.job_id for job in results} == {"j1", "j2"}


def test_prefilter_by_languages_falls_back_to_singular_language(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(
        job_id="j1", languages_required=[JobLanguageRequirement(language="German", level="C1")]
    ))
    repo.upsert_job(_job(
        job_id="j2", languages_required=[JobLanguageRequirement(language="French", level="B2")]
    ))
    results = repo.prefilter(MatchFilters(language="German"))
    assert {job.job_id for job in results} == {"j1"}


def test_all_job_feedback_reflects_multiple_jobs(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    repo.upsert_job(_job(job_id="j1"))
    repo.upsert_job(_job(job_id="j2"))
    repo.upsert_job(_job(job_id="j3"))
    repo.set_job_feedback("j1", "like")
    repo.set_job_feedback("j2", "dislike")
    assert repo.all_job_feedback() == {"j1": "like", "j2": "dislike"}
