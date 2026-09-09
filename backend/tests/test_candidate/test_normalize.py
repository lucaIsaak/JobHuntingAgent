from datetime import date

from jobhunter.candidate.normalize import (
    duration_months,
    infer_seniority,
    normalize_company,
    normalize_skill,
    normalize_title,
    parse_date_range,
    years_of_experience_total,
)


def test_normalize_skill_synonyms():
    assert normalize_skill("python3") == "Python"
    assert normalize_skill("js") == "JavaScript"
    assert normalize_skill("powerbi") == "Power BI"
    assert normalize_skill("PowerBI") == "Power BI"


def test_normalize_skill_preserves_known_acronyms():
    assert normalize_skill("sql") == "SQL"
    assert normalize_skill("SQL") == "SQL"


def test_normalize_skill_falls_back_to_original_when_unknown():
    assert normalize_skill("Storytelling") == "Storytelling"


def test_normalize_title_seniority_prefix():
    assert normalize_title("Sr. Data Analyst") == "Senior Data Analyst"
    assert normalize_title("Jr Software Engineer") == "Junior Software Engineer"
    assert normalize_title("Data Analyst") == "Data Analyst"


def test_normalize_company_strips_legal_suffixes():
    assert normalize_company("Acme Inc.") == "Acme"
    assert normalize_company("Beispiel GmbH") == "Beispiel"
    assert normalize_company("Nimbus Corp") == "Nimbus"


def test_parse_date_range_hyphen_years():
    assert parse_date_range("2019-2021") == ("2019", "2021", False)


def test_parse_date_range_month_present():
    start, end, is_current = parse_date_range("Jan 2020 - Present", as_of=date(2026, 9, 9))
    assert start == "2020-01"
    assert end == "2026-09"
    assert is_current is True


def test_parse_date_range_numeric_months():
    assert parse_date_range("06/2019 - 09/2021") == ("2019-06", "2021-09", False)


def test_parse_date_range_academic_year():
    assert parse_date_range("2019/2020") == ("2019", "2020", False)


def test_parse_date_range_no_match():
    assert parse_date_range("no dates here") == (None, None, False)


def test_duration_months_full_dates():
    assert duration_months("2019-06", "2021-09") == 28


def test_duration_months_missing_returns_none():
    assert duration_months(None, "2021-09") is None
    assert duration_months("2019-06", None) is None


def test_years_of_experience_total_merges_overlaps():
    ranges = [("2019-01", "2020-06"), ("2020-01", "2021-01")]
    total = years_of_experience_total(ranges, as_of=date(2026, 9, 9))
    assert total == 2.1  # merged interval, not naive sum (would be 2.5 unmerged)


def test_years_of_experience_total_empty():
    assert years_of_experience_total([]) == 0.0


def test_infer_seniority_explicit_keyword():
    level, inferred = infer_seniority(["Senior Data Analyst"], None)
    assert level == "senior"
    assert inferred is False


def test_infer_seniority_from_years_when_no_keyword():
    level, inferred = infer_seniority(["Data Analyst"], 2)
    assert level == "mid"
    assert inferred is True


def test_infer_seniority_no_signal():
    level, inferred = infer_seniority([], None)
    assert level is None
    assert inferred is False
