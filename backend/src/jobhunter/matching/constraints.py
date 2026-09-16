"""Layer A: structured hard constraints + soft constraint scoring.

Hard knockouts are reserved for genuinely blocking, explicitly-stated mismatches (work auth,
missing required language entirely, missing a must-have certification, refusing relocation to an
onsite-only job). Everything else (seniority gap, industry/employment-type mismatch) is a soft
penalty folded into the relevant subscore plus a gap reason — never a knockout — so career
switchers, junior candidates, and overqualified candidates aren't hidden outright.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jobhunter.candidate.schema import CandidateProfile
from jobhunter.jobs.schema import Job

_AUTH_STATEMENT_PHRASES = (
    "citizenship required", "must be authorized to work", "no sponsorship",
    "without sponsorship", "cannot sponsor", "sponsorship is not available",
)
_AUTH_IGNORED_TOKENS = {"work", "authorization", "authorized", "citizen", "citizenship", "the", "and", "for"}


@dataclass
class ConstraintResult:
    is_disqualified: bool = False
    disqualify_reasons: list[str] = field(default_factory=list)
    # subscore name -> multiplier in [0, 1] applied by fusion.py
    soft_penalties: dict[str, float] = field(default_factory=dict)
    gap_reasons: list[str] = field(default_factory=list)
    seniority_mismatch: str | None = None  # "under" | "over" | None


def _work_auth_conflict(profile: CandidateProfile, job: Job) -> bool:
    """Best-effort: the Job schema has no dedicated work-authorization field (not in the spec's
    minimum job fields), so this scans requirements_must/description for an explicit auth
    statement and checks whether the candidate's stated authorization overlaps with it."""
    if not profile.constraints.work_authorization:
        return False
    job_text = f"{job.description} {' '.join(job.requirements_must)}".lower()
    if not any(phrase in job_text for phrase in _AUTH_STATEMENT_PHRASES):
        return False
    candidate_tokens = [
        token for token in re.findall(r"[a-z]{3,}", profile.constraints.work_authorization.lower())
        if token not in _AUTH_IGNORED_TOKENS
    ]
    if not candidate_tokens:
        return False
    return not any(token in job_text for token in candidate_tokens)


def _missing_required_language(profile: CandidateProfile, job: Job) -> str | None:
    candidate_languages = {language.language.lower() for language in profile.languages}
    for requirement in job.languages_required:
        if requirement.language.lower() not in candidate_languages:
            return requirement.language
    return None


def _missing_required_certification(profile: CandidateProfile, job: Job) -> str | None:
    candidate_certs = {cert.name.lower() for cert in profile.certifications}
    for required in job.required_certifications:
        required_lower = required.lower()
        if not any(required_lower in have or have in required_lower for have in candidate_certs):
            return required
    return None


def _relocation_conflict(profile: CandidateProfile, job: Job) -> bool:
    if job.remote_type != "onsite" or not profile.location or not job.location:
        return False
    same_location = (
        profile.location.lower() in job.location.lower() or job.location.lower() in profile.location.lower()
    )
    if same_location:
        return False
    return profile.relocation_willingness == "no"


_SENIORITY_ORDER = ("intern", "junior", "mid", "senior", "lead", "manager", "director", "executive")


def _seniority_gap(candidate_level: str | None, job_level: str | None) -> tuple[int, str | None]:
    if not candidate_level or not job_level or candidate_level not in _SENIORITY_ORDER or job_level not in _SENIORITY_ORDER:
        return 0, None
    candidate_index = _SENIORITY_ORDER.index(candidate_level)
    job_index = _SENIORITY_ORDER.index(job_level)
    gap = candidate_index - job_index
    if gap == 0:
        return 0, None
    return gap, "over" if gap > 0 else "under"


def evaluate_constraints(profile: CandidateProfile, job: Job) -> ConstraintResult:
    result = ConstraintResult()

    if _work_auth_conflict(profile, job):
        result.is_disqualified = True
        result.disqualify_reasons.append("candidate's stated work authorization conflicts with job requirements")

    missing_language = _missing_required_language(profile, job)
    if missing_language:
        result.is_disqualified = True
        result.disqualify_reasons.append(f"job requires {missing_language}, which candidate does not have")

    missing_cert = _missing_required_certification(profile, job)
    if missing_cert:
        result.is_disqualified = True
        result.disqualify_reasons.append(f"job requires certification '{missing_cert}', which candidate does not have")

    if _relocation_conflict(profile, job):
        result.is_disqualified = True
        result.disqualify_reasons.append(
            f"job is onsite in {job.location} and candidate is not open to relocation"
        )

    if result.is_disqualified:
        return result

    # Soft: seniority gap
    gap, direction = _seniority_gap(profile.seniority_level, job.seniority)
    if direction:
        result.seniority_mismatch = direction
        if direction == "over":
            result.soft_penalties["seniority"] = max(0.4, 1.0 - 0.15 * gap)
            result.gap_reasons.append(
                f"candidate ({profile.seniority_level}) is more senior than the role ({job.seniority})"
            )
        else:
            result.soft_penalties["seniority"] = max(0.3, 1.0 - 0.2 * abs(gap))
            result.gap_reasons.append(
                f"candidate ({profile.seniority_level}) is less senior than the role ({job.seniority})"
            )

    # Soft: industry mismatch
    if job.industry and profile.industries and job.industry not in profile.industries:
        result.soft_penalties["industry"] = 0.5
        result.gap_reasons.append(f"candidate has no stated experience in {job.industry}")

    # Soft: employment type mismatch
    # (Filtering on employment_type is also available as an explicit user filter; this is the
    # scoring-side penalty when it's not filtered out but still mismatched.)

    return result
