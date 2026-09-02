"""Scores/ranks job postings against a user profile or CV."""

from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria


def _tokens(text: str) -> set[str]:
    return {token.strip().lower() for token in text.replace(",", " ").split() if token.strip()}


def rank_jobs(
    profile: CandidateProfile,
    criteria: SearchCriteria,
    postings,
) -> list[MatchResult]:
    """Score and sort postings using lightweight keyword heuristics."""

    wanted_terms = set(profile.skills) | set(criteria.keywords)
    wanted_terms = {term.lower() for term in wanted_terms if term}

    ranked: list[MatchResult] = []

    for posting in postings:
        text_tokens = _tokens(f"{posting.title} {posting.description} {posting.company}")
        score = 0.0
        reasons: list[str] = []

        if criteria.role and criteria.role.lower() in posting.title.lower():
            score += 0.35
            reasons.append("title matches requested role")

        if wanted_terms:
            overlap = len(wanted_terms & text_tokens)
            if overlap:
                skill_score = min(0.45, overlap * 0.15)
                score += skill_score
                reasons.append(f"{overlap} skill/keyword matches")

        preferred_locations = {location.lower() for location in profile.preferred_locations}
        if preferred_locations and posting.location.lower() in preferred_locations:
            score += 0.1
            reasons.append("matches preferred location")

        if posting.is_remote and criteria.remote_only:
            score += 0.1
            reasons.append("remote requirement satisfied")

        score = min(score, 1.0)
        ranked.append(MatchResult(job=posting, score=score, reasons=reasons or ["baseline candidate match"]))

    ranked.sort(key=lambda result: result.score, reverse=True)
    return ranked[: criteria.limit]
