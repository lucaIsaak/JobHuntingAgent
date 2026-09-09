import pytest
from pydantic import ValidationError

from jobhunter.candidate.schema import CandidateProfile, Experience, ExtractionEvidence
from jobhunter.jobs.schema import Job
from jobhunter.matching.constraints import ConstraintResult
from jobhunter.matching.fusion import effective_weights_for_profile, fuse
from jobhunter.matching.lexical import LexicalResult
from jobhunter.matching.schema import MatchWeights


def _profile(**overrides) -> CandidateProfile:
    defaults = dict(profile_id="p1", candidate_id="c1")
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def _job(**overrides) -> Job:
    defaults = dict(job_id="j1", title="Engineer", normalized_title="Engineer", company="Acme")
    defaults.update(overrides)
    return Job(**defaults)


def test_weights_must_sum_to_100():
    with pytest.raises(ValidationError):
        MatchWeights(skills=50, experience=50, seniority=50, semantic=0, industry=0, language=0, education=0, location=0)


def test_default_weights_sum_to_100():
    weights = MatchWeights()
    assert sum(weights.as_dict().values()) == 100


def test_disqualified_job_gets_zero_score():
    constraints = ConstraintResult(is_disqualified=True, disqualify_reasons=["missing required language"])
    lexical = LexicalResult(skills_fit=1.0)
    result = fuse(_profile(), _job(), lexical, semantic_score=1.0, constraints=constraints, effective_weights=MatchWeights())
    assert result.is_disqualified is True
    assert result.overall_fit == 0.0
    assert result.gap_reasons == ["missing required language"]


def test_overall_fit_within_bounds():
    lexical = LexicalResult(skills_fit=0.8, title_similarity=0.5, industry_fit=0.6, language_fit=1.0, education_fit=0.7)
    result = fuse(
        _profile(years_of_experience_total=5), _job(), lexical, semantic_score=0.5,
        constraints=ConstraintResult(), effective_weights=MatchWeights(),
    )
    assert 0.0 <= result.overall_fit <= 100.0


def test_career_switcher_transition_fit_flag():
    # High skills_fit, low title_similarity -> transition fit should trigger and be explained.
    lexical = LexicalResult(skills_fit=0.9, title_similarity=0.0)
    profile = _profile(
        years_of_experience_total=6,
        experience=[
            Experience(
                title="High School Teacher", normalized_title="High School Teacher",
                company="X", company_normalized="X",
                evidence=ExtractionEvidence(source_text="x", confidence=0.9),
            )
        ],
    )
    result = fuse(profile, _job(), lexical, semantic_score=0.5, constraints=ConstraintResult(), effective_weights=MatchWeights())
    assert result.transition_fit is True
    assert any("transition fit" in reason for reason in result.match_reasons)


def test_non_switcher_does_not_get_transition_flag():
    lexical = LexicalResult(skills_fit=0.9, title_similarity=0.9)
    profile = _profile(years_of_experience_total=6)
    result = fuse(profile, _job(), lexical, semantic_score=0.5, constraints=ConstraintResult(), effective_weights=MatchWeights())
    assert result.transition_fit is False


def test_overqualified_shown_not_hidden():
    lexical = LexicalResult(skills_fit=0.9, title_similarity=0.5)
    constraints = ConstraintResult(seniority_mismatch="over", soft_penalties={"seniority": 0.7})
    result = fuse(_profile(), _job(), lexical, semantic_score=0.5, constraints=constraints, effective_weights=MatchWeights())
    assert result.is_disqualified is False
    assert result.seniority_mismatch == "over"
    assert result.subscores["seniority"] == 0.7


def test_sparse_profile_marked_low_confidence():
    lexical = LexicalResult(skills_fit=0.5)
    profile = _profile()  # no experience, no years_of_experience_total
    result = fuse(profile, _job(), lexical, semantic_score=0.5, constraints=ConstraintResult(), effective_weights=MatchWeights())
    assert result.confidence == "low"


def test_effective_weights_unchanged_when_experience_present():
    profile = _profile(experience=[
        Experience(
            title="Engineer", normalized_title="Engineer", company="X", company_normalized="X",
            evidence=ExtractionEvidence(source_text="x", confidence=0.9),
        )
    ])
    weights = MatchWeights()
    effective = effective_weights_for_profile(weights, profile)
    assert effective == weights


def test_effective_weights_redistributed_for_sparse_profile():
    profile = _profile()  # no experience entries
    weights = MatchWeights()
    effective = effective_weights_for_profile(weights, profile)
    assert effective.experience == 0.0
    assert effective.seniority < weights.seniority
    assert effective.education > weights.education
    assert effective.semantic > weights.semantic
    assert abs(sum(effective.as_dict().values()) - 100.0) < 0.01
