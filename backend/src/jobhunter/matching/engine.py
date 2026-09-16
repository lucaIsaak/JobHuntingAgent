"""Matching pipeline: SQL prefilter -> inverted-skill-index narrowing -> top-N by lexical score
-> semantic + fusion re-rank -> top-K, persisted as a MatchRun.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from jobhunter.candidate.schema import CandidateProfile
from jobhunter.matching.constraints import evaluate_constraints
from jobhunter.matching.fusion import effective_weights_for_profile, fuse
from jobhunter.matching.lexical import LexicalResult, compute_lexical
from jobhunter.matching.schema import MatchFilters, MatchRun, MatchWeights
from jobhunter.matching.semantic import TfIdfEmbeddingProvider
from jobhunter.storage.jobs_repository import JobsRepository
from jobhunter.storage.match_repository import MatchRepository

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 200
DEFAULT_TOP_K = 20
MIN_SKILLS_FOR_INDEX_NARROWING = 3


def _lexical_rank_score(lexical: LexicalResult) -> float:
    """Cheap composite used only to pick the top-N pool before the (more expensive) semantic
    + fusion re-rank runs."""
    return 0.6 * lexical.skills_fit + 0.2 * lexical.title_similarity + 0.2 * lexical.industry_fit


def run_match(
    profile: CandidateProfile,
    jobs_repo: JobsRepository,
    match_repo: MatchRepository,
    filters: MatchFilters | None = None,
    weights: MatchWeights | None = None,
    top_n: int = DEFAULT_TOP_N,
    top_k: int = DEFAULT_TOP_K,
) -> MatchRun:
    filters = filters or MatchFilters()
    weights = weights or MatchWeights()
    effective_weights = effective_weights_for_profile(weights, profile)

    prefiltered = jobs_repo.prefilter(filters)

    candidate_skill_names = [skill.normalized_name for skill in profile.skills]
    if len(candidate_skill_names) >= MIN_SKILLS_FOR_INDEX_NARROWING:
        skill_matched_ids = jobs_repo.job_ids_matching_skills(candidate_skill_names)
        narrowed = [job for job in prefiltered if job.job_id in skill_matched_ids] or prefiltered
    else:
        narrowed = prefiltered

    lexical_scored = [(job, compute_lexical(profile, job)) for job in narrowed]
    lexical_scored.sort(key=lambda pair: _lexical_rank_score(pair[1]), reverse=True)
    top_n_pool = lexical_scored[:top_n]

    document_frequency, document_count = jobs_repo.get_corpus_stats()
    embedding_provider = TfIdfEmbeddingProvider()

    results = []
    for job, lexical in top_n_pool:
        constraints = evaluate_constraints(profile, job)
        semantic_score = (
            0.0 if constraints.is_disqualified
            else embedding_provider.similarity(profile, job, document_frequency, document_count)
        )
        results.append(fuse(profile, job, lexical, semantic_score, constraints, effective_weights))

    results.sort(key=lambda result: result.overall_fit, reverse=True)
    if filters.min_score:
        results = [result for result in results if result.overall_fit >= filters.min_score]

    top_k_results = results[:top_k]

    run = MatchRun(
        run_id=str(uuid4()),
        profile_id=profile.profile_id,
        weights_used=effective_weights,
        filters_used=filters,
        created_at=datetime.now(UTC).isoformat(),
        results=top_k_results,
    )
    match_repo.save_match_run(run)

    top_score = top_k_results[0].overall_fit if top_k_results else 0.0
    logger.info(
        "match run %s: profile=%s prefiltered=%d narrowed=%d out=%d top_score=%.1f",
        run.run_id, profile.profile_id, len(prefiltered), len(narrowed), len(top_k_results), top_score,
    )
    return run
