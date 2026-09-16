"""HTTP routes for the CV-to-job matcher: upload/edit a candidate profile, run matching against
the curated jobs database, inspect results. Separate router from `api/routes.py` (the live-scraper
search flow), mounted alongside it in `main.py`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from jobhunter.api import routes
from jobhunter.candidate import extractor
from jobhunter.candidate.normalize import DOMAIN_SIGNALS, SKILLS_CATALOG, normalize_skill
from jobhunter.candidate.schema import Candidate, CandidateProfile
from jobhunter.config import settings
from jobhunter.geo.regions import LANGUAGE_OPTIONS, REGIONS, countries_for_regions
from jobhunter.jobs.from_posting import convert_posting
from jobhunter.jobs.schema import Job
from jobhunter.matching import engine
from jobhunter.matching.keyword_rank import score_by_keywords
from jobhunter.matching.preference import build_preference_signals, score_preference_bonus
from jobhunter.matching.schema import MatchFilters, MatchResult, MatchRun, MatchWeights
from jobhunter.matching.semantic import build_corpus_stats
from jobhunter.models.search_criteria import CandidateProfile as LegacyCandidateProfile, SearchCriteria
from jobhunter.services.cv_parser import parse_cv_file_pages
from jobhunter.storage.candidate_repository import CandidateRepository
from jobhunter.storage.jobs_repository import JobsRepository
from jobhunter.storage.match_repository import MatchRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
candidate_repository = CandidateRepository(database_path=settings.database_path)
jobs_repository = JobsRepository(database_path=settings.database_path)
match_repository = MatchRepository(database_path=settings.database_path)


@router.post("/candidates/upload-file", response_model=CandidateProfile)
async def upload_candidate_cv(cv_file: UploadFile = File(...)) -> CandidateProfile:
    file_content = await cv_file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="uploaded file exceeds 5MB limit")

    try:
        cv_text, pages = parse_cv_file_pages(cv_file.filename or "cv", file_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(cv_text) < 20:
        raise HTTPException(status_code=400, detail="extracted CV text is too short")

    candidate_id = str(uuid4())
    profile_id = str(uuid4())
    profile = extractor.extract(
        cv_text,
        pages,
        profile_id=profile_id,
        candidate_id=candidate_id,
        anthropic_api_key=settings.anthropic_api_key,
    )

    candidate_repository.save_candidate(
        Candidate(
            candidate_id=candidate_id,
            created_at=datetime.now(UTC).isoformat(),
            latest_profile_id=profile_id,
            cv_filename=cv_file.filename,
        )
    )
    candidate_repository.save_profile(profile)
    return profile


@router.get("/skills-catalog", response_model=list[str])
def get_skills_catalog() -> list[str]:
    """Known skill terms for the CV-summary editor's add-a-skill autocomplete."""
    terms = sorted({term for terms in SKILLS_CATALOG.values() for term in terms})
    display = [normalize_skill(term) if normalize_skill(term) != term else term.title() for term in terms]
    return sorted(set(display))


@router.get("/candidates/{profile_id}", response_model=CandidateProfile)
def get_candidate_profile(profile_id: str) -> CandidateProfile:
    profile = candidate_repository.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")
    return profile


@router.put("/candidates/{profile_id}", response_model=CandidateProfile)
def update_candidate_profile(profile_id: str, profile: CandidateProfile) -> CandidateProfile:
    """Replace the stored profile with a user-edited version, so extraction errors can be
    corrected before matching. Validated against the same CandidateProfile schema."""
    existing = candidate_repository.get_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="profile not found")
    if profile.profile_id != profile_id:
        raise HTTPException(status_code=400, detail="profile_id in body must match the URL")
    candidate_repository.save_profile(profile)
    return profile


def _apply_preference_bonus(results: list[MatchResult]) -> list[MatchResult]:
    """Nudges results by the user's accumulated like/dislike feedback (see
    `matching/preference.py`) and re-sorts. A no-op — returns `results` unchanged — until at
    least one job has been rated."""
    feedback = jobs_repository.all_job_feedback()
    if not feedback:
        return results
    signals = build_preference_signals(feedback, jobs_repository.get_job)
    if signals.is_empty():
        return results

    boosted: list[MatchResult] = []
    for result in results:
        job = jobs_repository.get_job(result.job_id)
        bonus = score_preference_bonus(job, signals) if job else 0.0
        if bonus == 0.0:
            boosted.append(result)
        elif bonus > 0:
            boosted.append(
                result.model_copy(
                    update={
                        "overall_fit": min(100.0, result.overall_fit + bonus),
                        "match_reasons": [*result.match_reasons, "similar to jobs you've liked"],
                    }
                )
            )
        else:
            boosted.append(
                result.model_copy(
                    update={
                        "overall_fit": max(0.0, result.overall_fit + bonus),
                        "gap_reasons": [*result.gap_reasons, "similar to jobs you've disliked"],
                    }
                )
            )
    boosted.sort(key=lambda result: result.overall_fit, reverse=True)
    return boosted


class UnifiedSearchRequest(BaseModel):
    """One request shape for both entry points: with a candidate_profile_id, results come from
    the full matching engine; without one, from simple keyword relevance. Either way, live
    postings are fetched first and written into the same jobs database before filtering.

    `regions`/`countries`/`city` replace the old single free-text `location` field: explicit
    `countries` win when given, else `countries_for_regions(regions)` expands the picked
    region(s); each gets queried live as its own search (see `_build_location_queries` below and
    `orchestrator.fetch_postings_for_locations`), not just used to narrow one request."""

    candidate_profile_id: str | None = None
    role: str = Field(min_length=2)
    keywords: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    city: str | None = None
    remote_type: str | None = None  # onsite | hybrid | remote
    employment_type: str | None = None
    seniority: str | None = None
    industry: str | None = None
    company: str | None = None
    languages: list[str] = Field(default_factory=list)
    min_score: float = 0.0
    limit: int = 20
    sources: list[str] = Field(default_factory=list)


class UnifiedSearchResponse(BaseModel):
    run_id: str
    used_profile: bool
    filters_used: MatchFilters
    results: list[MatchResult]
    source_status: list[routes.SourceStatus] = Field(default_factory=list)


def _build_location_queries(payload: UnifiedSearchRequest) -> list[str]:
    """Turns the structured region/country/city picks into the list of location strings to
    search live, one per country -- explicit `countries` win over region-expansion; `city` (when
    given) gets combined into each; no selection at all returns an empty list, which callers
    treat as "no location constraint" (today's unchanged behavior)."""
    countries = payload.countries or countries_for_regions(payload.regions)
    if not countries:
        return [payload.city] if payload.city else []
    if payload.city:
        return [f"{payload.city}, {country}" for country in countries]
    return countries


class SearchMetadata(BaseModel):
    regions: dict[str, list[str]]
    industries: list[str]
    languages: list[str]


@router.get("/search-metadata", response_model=SearchMetadata)
def get_search_metadata() -> SearchMetadata:
    """Static option lists for the search form's Region/Country, Industry, and Language
    pickers, fetched once and cached client-side (same pattern as GET /api/skills-catalog)."""
    return SearchMetadata(
        regions={name: list(countries) for name, countries in REGIONS.items()},
        industries=sorted(DOMAIN_SIGNALS.keys()),
        languages=list(LANGUAGE_OPTIONS),
    )


@router.post("/search", response_model=UnifiedSearchResponse)
def unified_search(payload: UnifiedSearchRequest) -> UnifiedSearchResponse:
    rich_profile: CandidateProfile | None = None
    if payload.candidate_profile_id:
        rich_profile = candidate_repository.get_profile(payload.candidate_profile_id)
        if not rich_profile:
            raise HTTPException(status_code=404, detail="profile not found")

    # search_for_profile()-aware scrapers (e.g. company boards) pick boards by industry — reuse
    # the real profile's industries when we have one, for a better live fetch even in this step.
    scraper_profile = LegacyCandidateProfile(
        profile_id=str(uuid4()),
        raw_cv_text=f"Role-only search: {payload.role}",
        titles=[payload.role],
        industries=list(rich_profile.industries) if rich_profile else [],
    )
    criteria = SearchCriteria(
        role=payload.role,
        keywords=payload.keywords,
        remote_only=payload.remote_type == "remote",
        employment_types=[payload.employment_type] if payload.employment_type else [],
        limit=payload.limit,
        sources=payload.sources,
    )

    location_queries = _build_location_queries(payload)
    postings, source_counts = routes.orchestrator.fetch_postings_for_locations(
        scraper_profile, criteria, location_queries
    )

    try:
        jobs_repository.upsert_jobs([convert_posting(posting) for posting in postings])
        document_frequency, document_count = build_corpus_stats(jobs_repository.all_job_texts())
        jobs_repository.save_corpus_stats(document_frequency, document_count)
    except Exception:
        logger.exception("failed to import discovered postings into the matching database")

    source_status = [
        routes.SourceStatus(source=source, status="ok" if count > 0 else "no_results", count=count)
        for source, count in sorted(source_counts.items())
    ]

    filters = MatchFilters(
        min_score=payload.min_score,
        locations=location_queries,
        seniority=payload.seniority,
        industry=payload.industry,
        remote_type=payload.remote_type,
        languages=payload.languages,
        employment_type=payload.employment_type,
        title=payload.role,
        company=payload.company,
    )

    if rich_profile:
        match_run = engine.run_match(
            profile=rich_profile,
            jobs_repo=jobs_repository,
            match_repo=match_repository,
            filters=filters,
            top_k=payload.limit,
        )
        run_id, results = match_run.run_id, _apply_preference_bonus(match_run.results)
        # engine.run_match() already persisted the unboosted run — re-save so a later
        # GET /api/match-runs/{run_id} reflects the same boosted order returned here.
        match_repository.save_match_run(match_run.model_copy(update={"results": results}))
    else:
        query_text = f"{payload.role} {' '.join(payload.keywords)}"
        scored = [
            MatchResult(
                job_id=job.job_id,
                overall_fit=score_by_keywords(query_text, job),
                match_reasons=["matches your search"],
            )
            for job in jobs_repository.prefilter(filters)
        ]
        scored = [result for result in scored if result.overall_fit >= payload.min_score]
        scored.sort(key=lambda result: result.overall_fit, reverse=True)
        results = _apply_preference_bonus(scored[: payload.limit])
        run_id = str(uuid4())
        match_repository.save_match_run(
            MatchRun(
                run_id=run_id,
                profile_id=scraper_profile.profile_id,
                weights_used=MatchWeights(),
                filters_used=filters,
                created_at=datetime.now(UTC).isoformat(),
                results=results,
            )
        )

    try:
        # results is a matching.schema.MatchResult list (already saved via match_repository above),
        # not the legacy models.job.MatchResult StoredSearchRun.results expects — leave it empty here.
        routes.repository.save_search_run(
            routes.StoredSearchRun(
                run_id=run_id,
                profile_id=scraper_profile.profile_id,
                criteria=criteria,
                results=[],
            )
        )
        routes.repository.save_discovered_jobs(run_id, postings)
    except Exception:
        logger.exception("failed to persist discovered jobs for run %s", run_id)

    return UnifiedSearchResponse(
        run_id=run_id,
        used_profile=rich_profile is not None,
        filters_used=filters,
        results=results,
        source_status=source_status,
    )


class MatchRequest(MatchFilters):
    weights: MatchWeights | None = None
    top_k: int = 20


@router.post("/candidates/{profile_id}/match", response_model=MatchRun)
def run_match(profile_id: str, payload: MatchRequest) -> MatchRun:
    profile = candidate_repository.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")

    filters = MatchFilters.model_validate(payload.model_dump(exclude={"weights", "top_k"}))
    return engine.run_match(
        profile=profile,
        jobs_repo=jobs_repository,
        match_repo=match_repository,
        filters=filters,
        weights=payload.weights,
        top_k=payload.top_k,
    )


@router.get("/match-runs/{run_id}", response_model=MatchRun)
def get_match_run(run_id: str) -> MatchRun:
    run = match_repository.get_match_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="match run not found")
    return run


@router.get("/jobs", response_model=list[Job])
def list_jobs(
    location: str | None = None,
    seniority: str | None = None,
    industry: str | None = None,
    remote_type: str | None = None,
    language: str | None = None,
    employment_type: str | None = None,
) -> list[Job]:
    filters = MatchFilters(
        location=location,
        seniority=seniority,
        industry=industry,
        remote_type=remote_type,
        language=language,
        employment_type=employment_type,
    )
    return jobs_repository.prefilter(filters)


class JobFeedbackRequest(BaseModel):
    rating: Literal["like", "dislike"] | None = None


class JobFeedbackResponse(BaseModel):
    job_id: str
    rating: str | None


@router.put("/jobs/{job_id}/feedback", response_model=JobFeedbackResponse)
def set_job_feedback(job_id: str, payload: JobFeedbackRequest) -> JobFeedbackResponse:
    if not jobs_repository.get_job(job_id):
        raise HTTPException(status_code=404, detail="job not found")
    jobs_repository.set_job_feedback(job_id, payload.rating)
    return JobFeedbackResponse(job_id=job_id, rating=payload.rating)


@router.get("/jobs/feedback", response_model=dict[str, str])
def get_all_job_feedback() -> dict[str, str]:
    """{job_id: 'like' | 'dislike'} for every rated job, so the frontend can hydrate which
    result cards are already rated in one call."""
    return jobs_repository.all_job_feedback()
