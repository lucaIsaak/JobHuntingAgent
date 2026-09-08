from jobhunter.models.search_criteria import SeniorityLevel
from jobhunter.services import profile_extractor


def test_extract_skills_finds_multi_word_and_single_word_terms():
    cv_text = "Experienced in Python, machine learning, project management and Docker."

    skills, categories = profile_extractor.extract_skills(cv_text)

    assert "python" in skills
    assert "machine learning" in skills
    assert "project management" in skills
    assert "docker" in skills
    assert categories["data_ml"] == ["machine learning"]


def test_extract_skills_falls_back_to_python_when_nothing_matches():
    skills, categories = profile_extractor.extract_skills("Loves long walks on the beach.")

    assert skills == ["python"]
    assert categories == {}


def test_extract_years_of_experience_takes_the_max_mention():
    cv_text = "Summary: 5+ years experience. Worked 8 years as a backend engineer."

    assert profile_extractor.extract_years_of_experience(cv_text) == 8


def test_extract_years_of_experience_returns_none_when_absent():
    assert profile_extractor.extract_years_of_experience("No duration mentioned here.") is None


def test_extract_seniority_prefers_explicit_keyword_over_years():
    cv_text = "Senior Backend Engineer with 2 years of experience."

    assert profile_extractor.extract_seniority(cv_text, years=2) == SeniorityLevel.SENIOR


def test_extract_seniority_falls_back_to_years_threshold():
    assert profile_extractor.extract_seniority("Backend engineer.", years=6) == SeniorityLevel.SENIOR
    assert profile_extractor.extract_seniority("Backend engineer.", years=None) is None


def test_extract_domain_tags_detects_fintech_and_ai_ml():
    cv_text = "Built payments infrastructure and machine learning models for fraud detection."

    tags = profile_extractor.extract_domain_tags(cv_text)

    assert "fintech" in tags
    assert "ai_ml" in tags
