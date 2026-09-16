from jobhunter.jobs.schema import Job
from jobhunter.matching.keyword_rank import score_by_keywords


def _job(**overrides) -> Job:
    defaults = dict(job_id="j1", title="Backend Engineer", normalized_title="Backend Engineer", company="Acme")
    defaults.update(overrides)
    return Job(**defaults)


def test_score_by_keywords_rewards_overlapping_title():
    job = _job(normalized_title="Senior Backend Engineer", description="Build APIs with Python.")

    score = score_by_keywords("Backend Engineer", job)

    assert score > 0


def test_score_by_keywords_is_zero_for_disjoint_text():
    job = _job(normalized_title="Marketing Manager", description="Run campaigns and brand strategy.")

    score = score_by_keywords("Backend Engineer Python", job)

    assert score == 0.0


def test_score_by_keywords_is_zero_for_empty_query():
    job = _job()

    assert score_by_keywords("", job) == 0.0


def test_score_by_keywords_higher_for_closer_match():
    exact_job = _job(normalized_title="Backend Engineer", description="")
    loose_job = _job(normalized_title="Backend Engineer Intern Assistant", description="Some unrelated filler text about coffee.")

    exact_score = score_by_keywords("Backend Engineer", exact_job)
    loose_score = score_by_keywords("Backend Engineer", loose_job)

    assert exact_score > loose_score
