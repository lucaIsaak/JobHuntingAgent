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


def test_convert_posting_seniority_falls_back_to_years_from_description():
    """No title keyword ('Data Analyst' matches no seniority tier), so seniority should fall
    back to the years-of-experience the description does state, rather than staying blank."""
    job = convert_posting(_posting(
        title="Data Analyst",
        description="Looking for someone with 2+ years of experience.",
    ))
    assert job.seniority == "mid"


def test_convert_posting_seniority_blank_when_no_title_keyword_or_years():
    job = convert_posting(_posting(
        title="Data Analyst",
        description="General business role, no explicit level or experience mentioned.",
    ))
    assert job.seniority is None


def test_convert_posting_industry_inferred_from_company_name():
    """Description has no domain keywords, but the company name does — industry should still
    be inferred from it rather than left blank."""
    job = convert_posting(_posting(
        title="Account Manager",
        company="Muster Consulting GmbH",
        description="General business role, no explicit domain keywords here.",
    ))
    assert job.industry == "consulting"


def test_convert_posting_company_name_does_not_leak_into_skills():
    """Company-derived industry signal must stay separate from skill matching, or a company
    like 'AWS Solutions GmbH' would spuriously tag every one of its postings with the 'aws'
    skill regardless of what the role actually involves."""
    job = convert_posting(_posting(
        title="Office Manager",
        company="AWS Solutions GmbH",
        description="General administrative tasks, nothing technical.",
    ))
    skill_names = {skill.normalized_name.lower() for skill in job.skills}
    assert "aws" not in skill_names


def test_convert_posting_never_fabricates_requirements_or_certs():
    """Skill importance, general requirement text, certifications, and education stay
    unguessed — free-text postings give no reliable must-have/nice-to-have signal for these,
    unlike language (see the test_convert_posting_*_language* tests below), which is usually
    stated plainly."""
    job = convert_posting(_posting())
    assert job.requirements_must == []
    assert job.requirements_nice == []
    assert job.required_certifications == []
    assert job.education_requirements == []


def test_convert_posting_extracts_language_with_explicit_required_cue():
    job = convert_posting(_posting(
        description="You need to speak German and English, French is a plus."
    ))
    required = {req.language for req in job.languages_required}
    assert required == {"German", "English"}


def test_convert_posting_does_not_require_language_from_bare_mention():
    """No 'required'/'must'/etc. cue anywhere near the language names — a job where the team
    just happens to work in English and German isn't the same as the candidate being required
    to speak either, so this must stay unrecorded rather than guessed."""
    job = convert_posting(_posting(
        description="The team communicates in English and German on a daily basis."
    ))
    assert job.languages_required == []


def test_convert_posting_excludes_language_when_cues_conflict_in_same_clause():
    """A single clause carrying both a required-sounding word and an optional-sounding word is
    ambiguous — treated as not-required rather than guessed either way."""
    job = convert_posting(_posting(
        description="German is required and nice to have for this role."
    ))
    assert job.languages_required == []


def test_convert_posting_language_level_detected_when_stated():
    job = convert_posting(_posting(description="You must speak German at C1 level."))
    assert len(job.languages_required) == 1
    assert job.languages_required[0].language == "German"
    assert job.languages_required[0].level == "C1"


def test_convert_posting_language_level_defaults_to_unspecified():
    job = convert_posting(_posting(description="You must speak German for this role."))
    assert len(job.languages_required) == 1
    assert job.languages_required[0].level == "unspecified"


def test_job_id_is_deterministic_for_same_url():
    url = "https://example.com/jobs/123"
    assert _job_id_for_url(url) == _job_id_for_url(url)


def test_job_id_differs_for_different_urls():
    assert _job_id_for_url("https://example.com/a") != _job_id_for_url("https://example.com/b")


def test_convert_posting_job_id_reconverts_to_same_id():
    first = convert_posting(_posting(url="https://example.com/jobs/123"))
    second = convert_posting(_posting(url="https://example.com/jobs/123", title="Updated Title"))
    assert first.job_id == second.job_id
