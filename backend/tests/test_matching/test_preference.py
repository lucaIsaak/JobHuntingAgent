from jobhunter.jobs.schema import Job, JobSkill
from jobhunter.matching.preference import build_preference_signals, score_preference_bonus


def _job(**overrides) -> Job:
    defaults = dict(
        job_id="j1", title="Backend Engineer", normalized_title="Backend Engineer", company="Acme",
        skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)],
    )
    defaults.update(overrides)
    return Job(**defaults)


def _lookup(jobs: dict[str, Job]):
    return lambda job_id: jobs.get(job_id)


def test_score_preference_bonus_is_zero_with_no_feedback():
    signals = build_preference_signals({}, _lookup({}))
    assert score_preference_bonus(_job(), signals) == 0.0


def test_score_preference_bonus_positive_for_shared_liked_skill():
    liked = _job(job_id="liked", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)])
    candidate = _job(job_id="candidate", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)])

    signals = build_preference_signals({"liked": "like"}, _lookup({"liked": liked}))

    assert score_preference_bonus(candidate, signals) > 0


def test_score_preference_bonus_negative_for_shared_disliked_skill():
    disliked = _job(job_id="disliked", skills=[JobSkill(name="Java", normalized_name="Java", is_must_have=False)])
    candidate = _job(job_id="candidate", skills=[JobSkill(name="Java", normalized_name="Java", is_must_have=False)])

    signals = build_preference_signals({"disliked": "dislike"}, _lookup({"disliked": disliked}))

    assert score_preference_bonus(candidate, signals) < 0


def test_score_preference_bonus_conflicting_signals_partially_cancel():
    liked = _job(job_id="liked", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)], company="Acme")
    disliked = _job(job_id="disliked", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)], company="Acme")
    candidate = _job(job_id="candidate", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)], company="Acme")

    signals = build_preference_signals(
        {"liked": "like", "disliked": "dislike"}, _lookup({"liked": liked, "disliked": disliked})
    )

    # Same skill + same company liked once and disliked once nets to zero for both features.
    assert score_preference_bonus(candidate, signals) == 0.0


def test_score_preference_bonus_is_clamped():
    rated = {f"liked-{i}": "like" for i in range(50)}
    jobs = {
        job_id: _job(job_id=job_id, skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)])
        for job_id in rated
    }
    candidate = _job(job_id="candidate", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)])

    signals = build_preference_signals(rated, _lookup(jobs))

    assert score_preference_bonus(candidate, signals) == 15.0


def test_score_preference_bonus_ignores_unmatched_job():
    liked = _job(job_id="liked", skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=False)], company="Acme", industry="technology", seniority="mid")
    candidate = _job(job_id="candidate", skills=[JobSkill(name="Excel", normalized_name="Excel", is_must_have=False)], company="Other Corp", industry="finance", seniority="senior")

    signals = build_preference_signals({"liked": "like"}, _lookup({"liked": liked}))

    assert score_preference_bonus(candidate, signals) == 0.0


def test_build_preference_signals_skips_missing_jobs():
    """A rated job_id that's no longer in the jobs table (e.g. pruned) is skipped rather than
    raising."""
    signals = build_preference_signals({"gone": "like"}, _lookup({}))
    assert signals.is_empty()
