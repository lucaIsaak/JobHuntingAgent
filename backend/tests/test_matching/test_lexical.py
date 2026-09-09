from jobhunter.candidate.schema import CandidateProfile, Experience, ExtractionEvidence, Skill
from jobhunter.jobs.schema import Job, JobSkill
from jobhunter.matching.lexical import compute_lexical, title_similarity


def _skill(name: str, evidence_count: int = 1) -> Skill:
    evidence = [ExtractionEvidence(source_text=name, confidence=0.9) for _ in range(evidence_count)]
    return Skill(name=name, normalized_name=name, category="other", evidence=evidence)


def _profile(**overrides) -> CandidateProfile:
    defaults = dict(profile_id="p1", candidate_id="c1")
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def _job(**overrides) -> Job:
    defaults = dict(job_id="j1", title="Engineer", normalized_title="Engineer", company="Acme")
    defaults.update(overrides)
    return Job(**defaults)


def test_skill_overlap_full_must_have_match_scores_high():
    profile = _profile(skills=[_skill("Python"), _skill("SQL")])
    job = _job(skills=[
        JobSkill(name="Python", normalized_name="Python", is_must_have=True),
        JobSkill(name="SQL", normalized_name="SQL", is_must_have=True),
    ])
    result = compute_lexical(profile, job)
    assert result.skills_fit == 1.0
    assert result.gap_reasons == []


def test_missing_must_have_skill_penalized_more_than_missing_nice_to_have():
    profile_missing_must = _profile(skills=[_skill("Nice")])
    job = _job(skills=[
        JobSkill(name="Must", normalized_name="Must", is_must_have=True),
        JobSkill(name="Nice", normalized_name="Nice", is_must_have=False),
    ])
    result_missing_must = compute_lexical(profile_missing_must, job)

    profile_missing_nice = _profile(skills=[_skill("Must")])
    result_missing_nice = compute_lexical(profile_missing_nice, job)

    assert result_missing_must.skills_fit < result_missing_nice.skills_fit
    assert any("Must" in reason for reason in result_missing_must.gap_reasons)


def test_recency_weighting_favors_skill_used_in_most_recent_role():
    recent_evidence = ExtractionEvidence(source_text="Python", confidence=0.9)
    skill = Skill(name="Python", normalized_name="Python", category="other", evidence=[recent_evidence])

    recent_experience = Experience(
        title="Engineer", normalized_title="Engineer", company="A", company_normalized="A",
        start_date="2024-01", end_date="2025-01", skills_used=["Python"],
        evidence=ExtractionEvidence(source_text="x", confidence=0.9),
    )
    old_experience = Experience(
        title="Engineer", normalized_title="Engineer", company="B", company_normalized="B",
        start_date="2018-01", end_date="2019-01", skills_used=["Python"],
        evidence=ExtractionEvidence(source_text="x", confidence=0.9),
    )

    job = _job(skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=True)])

    recent_profile = _profile(skills=[skill], experience=[recent_experience, old_experience])
    old_only_profile = _profile(
        skills=[skill],
        experience=[
            old_experience,
            Experience(
                title="Manager", normalized_title="Manager", company="C", company_normalized="C",
                start_date="2024-01", end_date="2025-01", skills_used=[],
                evidence=ExtractionEvidence(source_text="x", confidence=0.9),
            ),
        ],
    )

    recent_result = compute_lexical(recent_profile, job)
    old_result = compute_lexical(old_only_profile, job)
    assert recent_result.skills_fit >= old_result.skills_fit


def test_evidence_strength_favors_repeated_mentions():
    job = _job(skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=True)])
    strong_profile = _profile(skills=[_skill("Python", evidence_count=3)])
    weak_profile = _profile(skills=[_skill("Python", evidence_count=1)])
    assert compute_lexical(strong_profile, job).skills_fit >= compute_lexical(weak_profile, job).skills_fit


def test_title_similarity_exact_match():
    profile = _profile(experience=[
        Experience(
            title="Senior Data Analyst", normalized_title="Senior Data Analyst",
            company="X", company_normalized="X",
            evidence=ExtractionEvidence(source_text="x", confidence=0.9),
        )
    ])
    job = _job(normalized_title="Senior Data Analyst")
    assert title_similarity(profile, job) == 1.0


def test_title_similarity_no_overlap():
    profile = _profile(experience=[
        Experience(
            title="Sales Representative", normalized_title="Sales Representative",
            company="X", company_normalized="X",
            evidence=ExtractionEvidence(source_text="x", confidence=0.9),
        )
    ])
    job = _job(normalized_title="Machine Learning Engineer")
    assert title_similarity(profile, job) == 0.0


def test_language_overlap_satisfied_and_missing():
    from jobhunter.candidate.schema import Language
    from jobhunter.jobs.schema import JobLanguageRequirement

    profile = _profile(languages=[
        Language(language="English", level="native", evidence=ExtractionEvidence(source_text="x", confidence=0.9))
    ])
    job = _job(languages_required=[
        JobLanguageRequirement(language="English", level="professional"),
        JobLanguageRequirement(language="German", level="B2"),
    ])
    result = compute_lexical(profile, job)
    assert result.language_fit == 0.5
    assert any("German" in reason for reason in result.gap_reasons)


def test_education_overlap():
    from jobhunter.candidate.schema import Education

    profile = _profile(education=[
        Education(
            institution="University", field="Statistics",
            evidence=ExtractionEvidence(source_text="x", confidence=0.9),
        )
    ])
    job = _job(education_requirements=["Statistics or related field"])
    result = compute_lexical(profile, job)
    assert result.education_fit == 1.0
