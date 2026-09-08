"""Scores/ranks job postings against a user profile or CV."""

from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.services import profile_extractor


def rank_jobs(
    profile: CandidateProfile,
    criteria: SearchCriteria,
    postings,
) -> list[MatchResult]:
    """Score and sort postings using rule-based skill/seniority/domain heuristics."""

    wanted_terms = set(profile.skills) | set(criteria.keywords)
    wanted_terms = {term.lower() for term in wanted_terms if term}

    ranked: list[MatchResult] = []

    for posting in postings:
        posting_text = f"{posting.title} {posting.description} {posting.company}"
        normalized_text = profile_extractor.normalize(posting_text)
        score = 0.0
        reasons: list[str] = []

        if criteria.role and criteria.role.lower() in posting.title.lower():
            score += 0.35
            reasons.append("title matches requested role")

        if wanted_terms:
            matched = [term for term in wanted_terms if profile_extractor.contains_phrase(normalized_text, term)]
            if matched:
                score += min(0.40, len(matched) * 0.08)
                reasons.append(f"{len(matched)} skill/keyword matches")

        preferred_locations = {location.lower() for location in profile.preferred_locations}
        if preferred_locations and posting.location.lower() in preferred_locations:
            score += 0.1
            reasons.append("matches preferred location")

        if posting.is_remote and criteria.remote_only:
            score += 0.1
            reasons.append("remote requirement satisfied")

        if profile.seniority and profile_extractor.contains_phrase(normalized_text, profile.seniority.value):
            score += 0.05
            reasons.append(f"seniority matches ({profile.seniority.value})")

        if profile.industries:
            posting_tags = set(profile_extractor.extract_domain_tags(posting_text))
            overlap = len(set(profile.industries) & posting_tags)
            if overlap:
                score += min(0.10, overlap * 0.05)
                reasons.append(f"{overlap} industry/domain matches")

        score = min(score, 1.0)
        ranked.append(MatchResult(job=posting, score=score, reasons=reasons or ["baseline candidate match"]))

    ranked.sort(key=lambda result: result.score, reverse=True)
    return ranked
