"""Score fusion: combines Layer A/B/C into overall_fit + subscores + reasons/gaps.

Handles the three scoring edge cases from the spec:
- Career switcher: strong skills but low title overlap -> experience_fit is computed from
  duration/seniority alignment only (title-similarity component zeroed, not penalized),
  `transition_fit=True`, explained in match_reasons.
- Junior/sparse CV: no experience entries -> `effective_weights_for_profile` redistributes the
  experience/seniority weight into education + semantic before fusion runs, and the result is
  marked `confidence="low"`.
- Overqualified: never disqualified — `seniority_mismatch="over"` plus a gap reason, score
  reduced via the constraints layer's soft penalty, job still shown.
"""

from __future__ import annotations

import logging

from jobhunter.candidate.schema import CandidateProfile
from jobhunter.jobs.schema import Job
from jobhunter.matching.constraints import ConstraintResult
from jobhunter.matching.lexical import LexicalResult
from jobhunter.matching.schema import SUBSCORE_NAMES, MatchResult, MatchWeights

logger = logging.getLogger(__name__)

TRANSITION_SKILLS_THRESHOLD = 0.5
TRANSITION_TITLE_THRESHOLD = 0.2
SPARSE_SENIORITY_RETENTION = 0.3


def effective_weights_for_profile(weights: MatchWeights, profile: CandidateProfile) -> MatchWeights:
    """Sparse/junior-CV reweighting: applies once per profile (stable across a whole match run,
    since every job in a run is scored against the same candidate)."""
    if profile.experience:
        return weights

    data = weights.as_dict()
    retained_seniority = data["seniority"] * SPARSE_SENIORITY_RETENTION
    freed = data["experience"] + (data["seniority"] - retained_seniority)
    data["experience"] = 0.0
    data["seniority"] = retained_seniority
    data["education"] += freed / 2
    data["semantic"] += freed / 2

    total = sum(data.values())
    return MatchWeights(**{name: (value / total) * 100 for name, value in data.items()})


def _years_alignment(profile: CandidateProfile, job: Job) -> float:
    years = profile.years_of_experience_total
    if years is None:
        return 0.5
    lo = job.years_experience_min
    hi = job.years_experience_max
    if lo is None and hi is None:
        return 0.7
    lo = lo if lo is not None else 0
    hi = hi if hi is not None else lo + 5
    if lo <= years <= hi:
        return 1.0
    distance = min(abs(years - lo), abs(years - hi))
    return max(0.0, 1.0 - distance * 0.1)


def _experience_fit(profile: CandidateProfile, job: Job, lexical: LexicalResult) -> tuple[float, bool]:
    transition_fit = (
        lexical.skills_fit >= TRANSITION_SKILLS_THRESHOLD and lexical.title_similarity < TRANSITION_TITLE_THRESHOLD
    )
    duration_component = _years_alignment(profile, job)
    if transition_fit:
        return duration_component, True
    return 0.5 * lexical.title_similarity + 0.5 * duration_component, False


def _location_fit(profile: CandidateProfile, job: Job) -> float:
    if job.remote_type == "remote":
        return 1.0
    if not job.location or not profile.location:
        return 0.5
    same_location = profile.location.lower() in job.location.lower() or job.location.lower() in profile.location.lower()
    if same_location:
        return 1.0
    return 0.7 if profile.relocation_willingness == "yes" else 0.2


def _match_reasons(subscores: dict[str, float], transition_fit: bool) -> list[str]:
    reasons: list[str] = []
    if transition_fit:
        reasons.append(
            "transferable skills are strong despite a title change from prior roles — flagged as a transition fit"
        )
    ranked = sorted(subscores.items(), key=lambda item: item[1], reverse=True)
    for name, score in ranked[:3]:
        if score > 0:
            reasons.append(f"strong {name} fit ({score:.0%})")
    return reasons


def fuse(
    profile: CandidateProfile,
    job: Job,
    lexical: LexicalResult,
    semantic_score: float,
    constraints: ConstraintResult,
    effective_weights: MatchWeights,
) -> MatchResult:
    if constraints.is_disqualified:
        result = MatchResult(
            job_id=job.job_id,
            overall_fit=0.0,
            subscores={},
            match_reasons=[],
            gap_reasons=constraints.disqualify_reasons,
            evidence=[],
            is_disqualified=True,
            confidence="normal",
        )
        logger.debug("disqualified job %s: %s", job.job_id, constraints.disqualify_reasons)
        return result

    experience_fit, transition_fit = _experience_fit(profile, job, lexical)
    seniority_fit = constraints.soft_penalties.get("seniority", 1.0)
    industry_fit = lexical.industry_fit * constraints.soft_penalties.get("industry", 1.0)

    subscores = {
        "skills": lexical.skills_fit,
        "experience": experience_fit,
        "seniority": seniority_fit,
        "semantic": semantic_score,
        "industry": industry_fit,
        "language": lexical.language_fit,
        "education": lexical.education_fit,
        "location": _location_fit(profile, job),
    }

    overall_fit = sum(subscores[name] * getattr(effective_weights, name) for name in SUBSCORE_NAMES)
    overall_fit = round(max(0.0, min(overall_fit, 100.0)), 1)

    gap_reasons = list(dict.fromkeys(lexical.gap_reasons + constraints.gap_reasons))
    confidence = "low" if not profile.experience or profile.years_of_experience_total is None else "normal"

    result = MatchResult(
        job_id=job.job_id,
        overall_fit=overall_fit,
        subscores={name: round(score, 2) for name, score in subscores.items()},
        match_reasons=_match_reasons(subscores, transition_fit),
        gap_reasons=gap_reasons,
        evidence=lexical.evidence,
        transition_fit=transition_fit,
        seniority_mismatch=constraints.seniority_mismatch,
        is_disqualified=False,
        confidence=confidence,
    )
    logger.debug("scored job %s: overall_fit=%.1f subscores=%s", job.job_id, overall_fit, subscores)
    return result
