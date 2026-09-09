from jobhunter.candidate.schema import CandidateProfile, Certification, Constraints, ExtractionEvidence, Language
from jobhunter.jobs.schema import Job, JobLanguageRequirement
from jobhunter.matching.constraints import evaluate_constraints


def _profile(**overrides) -> CandidateProfile:
    defaults = dict(profile_id="p1", candidate_id="c1")
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def _job(**overrides) -> Job:
    defaults = dict(job_id="j1", title="Engineer", normalized_title="Engineer", company="Acme")
    defaults.update(overrides)
    return Job(**defaults)


def test_no_constraints_no_disqualification():
    result = evaluate_constraints(_profile(), _job())
    assert result.is_disqualified is False
    assert result.disqualify_reasons == []


def test_missing_required_language_disqualifies():
    profile = _profile(languages=[])
    job = _job(languages_required=[JobLanguageRequirement(language="German", level="C1")])
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is True
    assert any("German" in reason for reason in result.disqualify_reasons)


def test_present_language_does_not_disqualify():
    evidence = ExtractionEvidence(source_text="German (Native)", confidence=0.9)
    profile = _profile(languages=[Language(language="German", level="native", evidence=evidence)])
    job = _job(languages_required=[JobLanguageRequirement(language="German", level="C1")])
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False


def test_missing_must_have_certification_disqualifies():
    profile = _profile(certifications=[])
    job = _job(required_certifications=["AWS Certified Solutions Architect"])
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is True


def test_present_certification_does_not_disqualify():
    evidence = ExtractionEvidence(source_text="AWS Certified Solutions Architect", confidence=0.9)
    profile = _profile(
        certifications=[Certification(name="AWS Certified Solutions Architect", evidence=evidence)]
    )
    job = _job(required_certifications=["AWS Certified Solutions Architect"])
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False


def test_relocation_refusal_disqualifies_onsite_job_in_different_location():
    profile = _profile(location="Berlin, Germany", relocation_willingness="no")
    job = _job(location="New York, USA", remote_type="onsite")
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is True


def test_relocation_refusal_does_not_disqualify_remote_job():
    profile = _profile(location="Berlin, Germany", relocation_willingness="no")
    job = _job(location="New York, USA", remote_type="remote")
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False


def test_relocation_refusal_does_not_disqualify_same_location():
    profile = _profile(location="Berlin, Germany", relocation_willingness="no")
    job = _job(location="Berlin, Germany", remote_type="onsite")
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False


def test_overqualified_is_soft_penalty_not_disqualification():
    profile = _profile(seniority_level="senior")
    job = _job(seniority="junior")
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False
    assert result.seniority_mismatch == "over"
    assert "seniority" in result.soft_penalties
    assert result.soft_penalties["seniority"] < 1.0


def test_underqualified_is_soft_penalty_not_disqualification():
    profile = _profile(seniority_level="junior")
    job = _job(seniority="senior")
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False
    assert result.seniority_mismatch == "under"


def test_industry_mismatch_is_soft_penalty():
    profile = _profile(industries=["fintech"])
    job = _job(industry="healthcare")
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is False
    assert result.soft_penalties.get("industry") == 0.5
    assert any("healthcare" in reason for reason in result.gap_reasons)


def test_work_authorization_conflict_disqualifies_when_stated_and_unmatched():
    profile = _profile(constraints=Constraints(work_authorization="Authorized to work in Canada only"))
    job = _job(
        description="This role requires candidates to be authorized to work in the US without sponsorship.",
        requirements_must=["Must be authorized to work in the US without sponsorship"],
    )
    result = evaluate_constraints(profile, job)
    assert result.is_disqualified is True
