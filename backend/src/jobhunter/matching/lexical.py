"""Layer B: lexical / entity overlap between candidate and job.

Skill overlap weights must-have matches more than nice-to-have (0.7/0.3), and multiplies each
matched skill by a recency factor (used in the candidate's most recent role scores higher) and an
evidence-strength factor (skills backed by >=2 evidence spans score higher than a single mention).
Tool overlap folds into the skills subscore (the spec's weight table has no separate "tools"
bucket). Title similarity feeds `experience_fit` in fusion.py, not a standalone weight.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jobhunter.candidate.normalize import language_level_rank, normalize
from jobhunter.candidate.schema import CandidateProfile, Experience
from jobhunter.jobs.schema import Job
from jobhunter.matching.schema import MatchEvidence

RECENCY_MOST_RECENT = 1.3
RECENCY_OLDER_ONLY = 0.8
RECENCY_UNLINKED = 1.0
EVIDENCE_STRENGTH_MULTIPLIER = 1.15
MUST_HAVE_WEIGHT = 0.7
NICE_TO_HAVE_WEIGHT = 0.3


@dataclass
class LexicalResult:
    skills_fit: float = 0.0
    title_similarity: float = 0.0
    industry_fit: float = 1.0
    language_fit: float = 1.0
    education_fit: float = 1.0
    evidence: list[MatchEvidence] = field(default_factory=list)
    gap_reasons: list[str] = field(default_factory=list)


def _skill_recency_multiplier(normalized_name: str, experience: list[Experience]) -> float:
    if not experience:
        return RECENCY_UNLINKED
    ordered = sorted(experience, key=lambda entry: entry.start_date or "", reverse=True)
    if normalized_name in {used.lower() for used in ordered[0].skills_used}:
        return RECENCY_MOST_RECENT
    if any(normalized_name in {used.lower() for used in entry.skills_used} for entry in ordered[1:]):
        return RECENCY_OLDER_ONLY
    return RECENCY_UNLINKED


def _skill_bucket_ratio(
    job_skills: list, candidate_skills: dict, experience: list[Experience], gap_reasons: list[str], evidence: list[MatchEvidence]
) -> float:
    if not job_skills:
        return 1.0
    matched_weight = 0.0
    for job_skill in job_skills:
        key = job_skill.normalized_name.lower()
        candidate_skill = candidate_skills.get(key)
        if candidate_skill is None:
            if job_skill.is_must_have:
                gap_reasons.append(f"missing must-have skill: {job_skill.name}")
            continue
        multiplier = _skill_recency_multiplier(key, experience)
        if len(candidate_skill.evidence) >= 2:
            multiplier *= EVIDENCE_STRENGTH_MULTIPLIER
        matched_weight += min(multiplier, 1.5)
        evidence.append(
            MatchEvidence(
                candidate_span=candidate_skill.name, job_requirement=job_skill.name, subscore_kind="skills"
            )
        )
    return min(matched_weight / len(job_skills), 1.0)


def _skill_overlap(profile: CandidateProfile, job: Job, evidence: list[MatchEvidence], gap_reasons: list[str]) -> float:
    candidate_skills = {skill.normalized_name.lower(): skill for skill in profile.skills}
    must_haves = [skill for skill in job.skills if skill.is_must_have]
    nice_haves = [skill for skill in job.skills if not skill.is_must_have]

    must_ratio = _skill_bucket_ratio(must_haves, candidate_skills, profile.experience, gap_reasons, evidence)
    nice_ratio = _skill_bucket_ratio(nice_haves, candidate_skills, profile.experience, [], evidence)

    if must_haves and nice_haves:
        skill_score = MUST_HAVE_WEIGHT * must_ratio + NICE_TO_HAVE_WEIGHT * nice_ratio
    elif must_haves:
        skill_score = must_ratio
    elif nice_haves:
        skill_score = nice_ratio
    else:
        skill_score = 0.5  # job states no specific skills — neither reward nor punish

    if job.tools:
        candidate_tools = {tool.lower() for entry in profile.experience for tool in entry.tools}
        candidate_tools |= set(candidate_skills)
        tool_matches = sum(1 for tool in job.tools if tool.lower() in candidate_tools)
        tool_score = tool_matches / len(job.tools)
        skill_score = 0.8 * skill_score + 0.2 * tool_score

    return skill_score


def title_similarity(profile: CandidateProfile, job: Job) -> float:
    candidate_titles = [entry.normalized_title for entry in profile.experience]
    if profile.headline:
        candidate_titles.append(profile.headline)
    if not candidate_titles:
        return 0.0

    job_tokens = set(normalize(job.normalized_title).split())
    if not job_tokens:
        return 0.0

    best = 0.0
    for title in candidate_titles:
        candidate_tokens = set(normalize(title).split())
        if not candidate_tokens:
            continue
        overlap = len(candidate_tokens & job_tokens) / len(candidate_tokens | job_tokens)
        best = max(best, overlap)
    return best


def _industry_overlap(profile: CandidateProfile, job: Job) -> float:
    if not job.industry:
        return 1.0
    if not profile.industries:
        return 0.3
    return 1.0 if job.industry in profile.industries else 0.0


def _language_overlap(profile: CandidateProfile, job: Job, gap_reasons: list[str]) -> float:
    if not job.languages_required:
        return 1.0
    candidate_levels = {language.language.lower(): language_level_rank(language.level) for language in profile.languages}
    satisfied = 0
    for requirement in job.languages_required:
        required_rank = language_level_rank(requirement.level)
        candidate_rank = candidate_levels.get(requirement.language.lower(), 0)
        if candidate_rank >= required_rank:
            satisfied += 1
        else:
            gap_reasons.append(f"language requirement not met: {requirement.language} ({requirement.level})")
    return satisfied / len(job.languages_required)


def _education_overlap(profile: CandidateProfile, job: Job) -> float:
    if not job.education_requirements:
        return 1.0
    candidate_fields = {(edu.field or "").lower() for edu in profile.education if edu.field}
    candidate_fields |= {(edu.degree or "").lower() for edu in profile.education if edu.degree}
    candidate_fields.discard("")
    if not candidate_fields:
        return 0.3
    matched = sum(
        1
        for requirement in job.education_requirements
        if any(field in requirement.lower() or requirement.lower() in field for field in candidate_fields)
    )
    return matched / len(job.education_requirements)


def compute_lexical(profile: CandidateProfile, job: Job) -> LexicalResult:
    evidence: list[MatchEvidence] = []
    gap_reasons: list[str] = []

    skills_fit = _skill_overlap(profile, job, evidence, gap_reasons)
    education_fit = _education_overlap(profile, job)
    language_fit = _language_overlap(profile, job, gap_reasons)
    industry_fit = _industry_overlap(profile, job)

    return LexicalResult(
        skills_fit=skills_fit,
        title_similarity=title_similarity(profile, job),
        industry_fit=industry_fit,
        language_fit=language_fit,
        education_fit=education_fit,
        evidence=evidence,
        gap_reasons=gap_reasons,
    )
