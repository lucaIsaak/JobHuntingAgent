from jobhunter.jobs.from_posting import _job_id_for_url, convert_posting
from jobhunter.models.job import EmploymentType, JobPosting


def _posting(**overrides) -> JobPosting:
    defaults = dict(
        source="adzuna",
        title="Senior Data Analyst",
        company="Acme Analytics",
        location="Berlin, Germany",
        is_remote=False,
        employment_type=EmploymentType.FULL_TIME,
        description="We need 5+ years experience with Python and SQL. Hybrid work available.",
        url="https://example.com/jobs/123",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def test_convert_posting_derives_skills():
    job = convert_posting(_posting())
    skill_names = {skill.normalized_name.lower() for skill in job.skills}
    assert "python" in skill_names
    assert "sql" in skill_names


def test_convert_posting_skills_default_to_not_must_have():
    job = convert_posting(_posting())
    assert job.skills
    assert all(skill.is_must_have is False for skill in job.skills)


def test_convert_posting_derives_seniority():
    job = convert_posting(_posting(title="Senior Data Analyst"))
    assert job.seniority == "senior"


def test_convert_posting_remote_type_from_description_hint():
    job = convert_posting(_posting(is_remote=False, description="Hybrid work available."))
    assert job.remote_type == "hybrid"


def test_convert_posting_remote_type_onsite_default():
    job = convert_posting(_posting(is_remote=False, description="No remote signal here."))
    assert job.remote_type == "onsite"


def test_convert_posting_remote_type_from_is_remote_flag():
    job = convert_posting(_posting(is_remote=True))
    assert job.remote_type == "remote"


def test_convert_posting_employment_type_passthrough():
    job = convert_posting(_posting(employment_type=EmploymentType.CONTRACT))
    assert job.employment_type == "contract"


def test_convert_posting_years_experience_extracted():
    job = convert_posting(_posting(description="Looking for someone with 5+ years experience."))
    assert job.years_experience_min == 5
    assert job.years_experience_max is None


def test_convert_posting_never_fabricates_requirements_or_certs_or_languages():
    job = convert_posting(_posting())
    assert job.requirements_must == []
    assert job.requirements_nice == []
    assert job.languages_required == []
    assert job.required_certifications == []
    assert job.education_requirements == []


def test_job_id_is_deterministic_for_same_url():
    url = "https://example.com/jobs/123"
    assert _job_id_for_url(url) == _job_id_for_url(url)


def test_job_id_differs_for_different_urls():
    assert _job_id_for_url("https://example.com/a") != _job_id_for_url("https://example.com/b")


def test_convert_posting_job_id_reconverts_to_same_id():
    first = convert_posting(_posting(url="https://example.com/jobs/123"))
    second = convert_posting(_posting(url="https://example.com/jobs/123", title="Updated Title"))
    assert first.job_id == second.job_id
