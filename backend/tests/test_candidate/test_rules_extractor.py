"""Golden-fixture tests for the rule-based extractor. `as_of` is pinned so 'Present'/duration
results are deterministic regardless of when the suite runs.
"""

from datetime import date
from pathlib import Path

import pytest

from jobhunter.candidate.rules_extractor import extract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvs"
AS_OF = date(2026, 9, 9)


def _load(name: str):
    cv_text = (FIXTURES_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return extract(cv_text, [cv_text], profile_id=f"{name}-profile", candidate_id=f"{name}-candidate", as_of=AS_OF)


@pytest.fixture(scope="module")
def analytics_intern():
    return _load("analytics_intern")


@pytest.fixture(scope="module")
def career_switcher():
    return _load("career_switcher")


@pytest.fixture(scope="module")
def senior_multilingual_marketer():
    return _load("senior_multilingual_marketer")


# ---------------------------------------------------------------------------
# Analytics intern — junior/sparse profile
# ---------------------------------------------------------------------------

def test_analytics_intern_seniority_is_explicit(analytics_intern):
    assert analytics_intern.seniority_level == "intern"
    assert analytics_intern.seniority_inferred is False


def test_analytics_intern_skills_present(analytics_intern):
    skill_names = {skill.normalized_name for skill in analytics_intern.skills}
    assert {"SQL", "python", "excel"} <= skill_names


def test_analytics_intern_short_experience(analytics_intern):
    assert len(analytics_intern.experience) == 1
    entry = analytics_intern.experience[0]
    assert entry.title == "Data Analytics Intern"
    assert entry.company == "Northwind Retail"
    assert entry.duration_months == 3


def test_analytics_intern_years_total_is_small(analytics_intern):
    assert analytics_intern.years_of_experience_total is not None
    assert 0 < analytics_intern.years_of_experience_total < 1


def test_analytics_intern_education(analytics_intern):
    assert len(analytics_intern.education) == 1
    education = analytics_intern.education[0]
    assert "Toronto" in education.institution
    assert education.field == "Statistics"


def test_analytics_intern_language(analytics_intern):
    assert any(lang.language == "English" and lang.level == "native" for lang in analytics_intern.languages)


def test_analytics_intern_field_evidence_populated(analytics_intern):
    assert "full_name" in analytics_intern.field_evidence
    assert analytics_intern.field_evidence["full_name"].confidence > 0


# ---------------------------------------------------------------------------
# Career switcher — strong tech skills, non-tech title history
# ---------------------------------------------------------------------------

def test_career_switcher_skills_present(career_switcher):
    skill_names = {skill.normalized_name for skill in career_switcher.skills}
    assert {"python", "javascript", "SQL"} <= skill_names


def test_career_switcher_seniority_is_inferred(career_switcher):
    # Neither title ("High School Mathematics Teacher", "Software Engineering Fellow") contains
    # an explicit seniority keyword, so the level must come from total years, not a keyword hit.
    assert career_switcher.seniority_inferred is True
    assert career_switcher.seniority_level is not None


def test_career_switcher_experience_entries(career_switcher):
    assert len(career_switcher.experience) == 2
    titles = {entry.title for entry in career_switcher.experience}
    assert titles == {"High School Mathematics Teacher", "Software Engineering Fellow"}
    teacher_entry = next(e for e in career_switcher.experience if "Teacher" in e.title)
    assert teacher_entry.duration_months == 71


def test_career_switcher_certification_captured(career_switcher):
    assert any("aws" in cert.name.lower() for cert in career_switcher.certifications)


def test_career_switcher_skill_not_falsely_duplicated(career_switcher):
    # "React" only appears once in the CV (in the SKILLS list, no bullet mention) — it must not
    # be inflated to look like it has repeated evidence just because the whole-document scan
    # re-covers the skills-section text.
    react = next(skill for skill in career_switcher.skills if skill.normalized_name == "react")
    assert len(react.evidence) == 1


def test_career_switcher_skill_with_real_second_mention_has_multiple_evidence(career_switcher):
    # "Python" is both in the SKILLS list and used in a bullet — a genuine second mention.
    python_skill = next(skill for skill in career_switcher.skills if skill.normalized_name == "python")
    assert len(python_skill.evidence) >= 2


# ---------------------------------------------------------------------------
# Senior multilingual marketer — non-English section header, multiple languages, metrics
# ---------------------------------------------------------------------------

def test_marketer_multilingual_section_header_still_segments_experience(senior_multilingual_marketer):
    # "BERUFSERFAHRUNG" (German for "work experience") must still be recognized as the
    # experience header so entries are extracted, not swallowed into the pre-header block.
    assert len(senior_multilingual_marketer.experience) == 2
    titles = {entry.title for entry in senior_multilingual_marketer.experience}
    assert "Senior Marketing Manager" in titles
    assert "Marketing Manager" in titles


def test_marketer_languages(senior_multilingual_marketer):
    levels = {lang.language: lang.level for lang in senior_multilingual_marketer.languages}
    assert levels["German"] == "native"
    assert levels["English"] == "professional"
    assert levels["French"] == "B1"


def test_marketer_achievement_metrics_parsed(senior_multilingual_marketer):
    achievements = [a for entry in senior_multilingual_marketer.experience for a in entry.achievements]
    assert any(a.value == 25.0 and a.unit == "%" for a in achievements)
    assert any(a.value == 40.0 and a.unit == "%" for a in achievements)


def test_marketer_current_role_duration(senior_multilingual_marketer):
    current_entry = next(entry for entry in senior_multilingual_marketer.experience if entry.is_current)
    assert current_entry.title == "Senior Marketing Manager"
    assert current_entry.duration_months == 91  # Mar 2019 through the pinned as_of (Sep 2026)


def test_marketer_skill_deduplicated_with_merged_evidence(senior_multilingual_marketer):
    # "SEO" appears both in the SKILLS list and inline in a bullet — must be a single Skill
    # entry with both evidence spans merged, not two separate entries.
    seo_skills = [skill for skill in senior_multilingual_marketer.skills if skill.normalized_name == "SEO"]
    assert len(seo_skills) == 1
    assert len(seo_skills[0].evidence) >= 2


def test_marketer_certification(senior_multilingual_marketer):
    assert any("google ads" in cert.name.lower() for cert in senior_multilingual_marketer.certifications)
