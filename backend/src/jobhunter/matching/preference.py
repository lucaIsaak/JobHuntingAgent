"""Learns a lightweight, explainable preference model from the user's like/dislike feedback on
past jobs, and turns it into a small bonus/penalty applied to future search results.

Pure counting, no ML — same hand-rolled-heuristic style as `semantic.py`'s TF-IDF and
`keyword_rank.py`'s Jaccard overlap. With no feedback yet, every job scores exactly 0.0, so
ranking is unaffected until the user starts rating jobs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from jobhunter.jobs.schema import Job

_POINTS_PER_NET_SIGNAL = 2.0
_MAX_BONUS = 15.0

_LIKE_WEIGHT = {"like": 1, "dislike": -1}


@dataclass
class PreferenceSignals:
    """Net (likes - dislikes) tally per feature value, across every rated job."""

    skills: dict[str, int] = field(default_factory=dict)
    companies: dict[str, int] = field(default_factory=dict)
    industries: dict[str, int] = field(default_factory=dict)
    seniorities: dict[str, int] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.skills or self.companies or self.industries or self.seniorities)


def build_preference_signals(feedback: dict[str, str], job_lookup: Callable[[str], Job | None]) -> PreferenceSignals:
    """One pass over every rated job: tallies which skills/company/industry/seniority show up
    disproportionately in liked vs. disliked jobs."""
    signals = PreferenceSignals()
    for job_id, rating in feedback.items():
        weight = _LIKE_WEIGHT.get(rating)
        if weight is None:
            continue
        job = job_lookup(job_id)
        if job is None:
            continue
        for skill in job.skills:
            signals.skills[skill.normalized_name.lower()] = signals.skills.get(skill.normalized_name.lower(), 0) + weight
        signals.companies[job.company.lower()] = signals.companies.get(job.company.lower(), 0) + weight
        if job.industry:
            signals.industries[job.industry] = signals.industries.get(job.industry, 0) + weight
        if job.seniority:
            signals.seniorities[job.seniority] = signals.seniorities.get(job.seniority, 0) + weight
    return signals


def score_preference_bonus(job: Job, signals: PreferenceSignals) -> float:
    """Sums the net signal for every skill/company/industry/seniority the job matches, scaled
    and clamped to +/-15 points so a handful of ratings can nudge results without ever swamping
    the underlying match score."""
    if signals.is_empty():
        return 0.0

    net = sum(signals.skills.get(skill.normalized_name.lower(), 0) for skill in job.skills)
    net += signals.companies.get(job.company.lower(), 0)
    if job.industry:
        net += signals.industries.get(job.industry, 0)
    if job.seniority:
        net += signals.seniorities.get(job.seniority, 0)

    bonus = net * _POINTS_PER_NET_SIGNAL
    return max(-_MAX_BONUS, min(_MAX_BONUS, bonus))
