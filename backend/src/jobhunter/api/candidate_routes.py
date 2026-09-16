"""HTTP routes for the CV-to-job matcher: upload/edit a candidate profile, run matching against
the curated jobs database, inspect results. Separate router from `api/routes.py` (the live-scraper
search flow), mounted alongside it in `main.py`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from jobhunter.candidate import extractor
from jobhunter.candidate.schema import Candidate, CandidateProfile
from jobhunter.config import settings
from jobhunter.jobs.schema import Job
from jobhunter.matching import engine
from jobhunter.matching.schema import MatchFilters, MatchRun, MatchWeights
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
