"""HTTP routes the frontend calls (trigger search, fetch results, etc.)."""

import difflib
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from jobhunter.agent import health_monitor
from jobhunter.agent.orchestrator import JobSearchOrchestrator
from jobhunter.config import settings
from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria, SeniorityLevel
from jobhunter.scrapers.arbeitnow import ArbeitnowScraper
from jobhunter.scrapers.adzuna import AdzunaScraper
from jobhunter.scrapers.glassdoor import GlassdoorScraper
from jobhunter.scrapers.company_boards import CompanyBoardScraper
from jobhunter.scrapers.configured_api import ConfiguredJsonScraper
from jobhunter.scrapers.jooble import JoobleScraper
from jobhunter.scrapers.bundesagentur import BundesagenturScraper
from jobhunter.services import profile_extractor
from jobhunter.services.cv_parser import parse_cv_file
from jobhunter.storage.repository import SQLiteRepository, StoredSearchRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
repository = SQLiteRepository(database_path=settings.database_path)
scrapers = [
    GlassdoorScraper(),
    ArbeitnowScraper(),
    BundesagenturScraper(
        **({"client_id": settings.arbeitsagentur_token} if settings.arbeitsagentur_token else {}),
        endpoint=settings.arbeitsagentur_endpoint
        or "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs",
    ),
]
if settings.adzuna_app_id and settings.adzuna_app_key:
    scrapers.insert(
        0,
        AdzunaScraper(
            app_id=settings.adzuna_app_id,
            app_key=settings.adzuna_app_key,
            country=settings.adzuna_country,
        ),
    )
if settings.jooble_api_key:
    scrapers.append(JoobleScraper(settings.jooble_api_key, settings.jooble_endpoint or "https://jooble.org/api"))
if settings.eures_endpoint:
    scrapers.append(ConfiguredJsonScraper("eures", settings.eures_endpoint, settings.eures_token))
scrapers.append(
    CompanyBoardScraper(
        settings.greenhouse_boards,
        settings.lever_sites,
        catalog_top_n=settings.greenhouse_catalog_top_n,
    )
)

orchestrator = JobSearchOrchestrator(scrapers=scrapers)


class UploadCvRequest(BaseModel):
    cv_text: str = Field(min_length=20)
    preferred_locations: list[str] = Field(default_factory=list)


class UploadCvResponse(BaseModel):
    profile_id: str
    skills: list[str]
    titles: list[str]
    seniority: SeniorityLevel | None = None
    years_of_experience: int | None = None
    industries: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    profile_id: str | None = None
    criteria: SearchCriteria


class SourceStatus(BaseModel):
    source: str
    status: str  # "ok" | "no_results" — see note on run_search for why "error" isn't distinguished here
    count: int


class SearchResponse(BaseModel):
    run_id: str
    profile_id: str
    criteria: SearchCriteria
    results: list[MatchResult]
    source_status: list[SourceStatus] = Field(default_factory=list)


def _store_profile(cv_text: str, preferred_locations: list[str]) -> UploadCvResponse:
    profile_id = str(uuid4())
    skills, skill_categories = profile_extractor.extract_skills(cv_text)
    titles = profile_extractor.extract_titles(cv_text)
    years_of_experience = profile_extractor.extract_years_of_experience(cv_text)
    seniority = profile_extractor.extract_seniority(cv_text, years_of_experience)
    industries = profile_extractor.extract_domain_tags(cv_text)

    profile = CandidateProfile(
        profile_id=profile_id,
        raw_cv_text=cv_text,
        skills=skills,
        titles=titles,
        preferred_locations=preferred_locations,
        industries=industries,
        seniority=seniority,
        years_of_experience=years_of_experience,
        skill_categories=skill_categories,
    )
    repository.save_profile(profile)

    return UploadCvResponse(
        profile_id=profile_id,
        skills=skills,
        titles=titles,
        seniority=seniority,
        years_of_experience=years_of_experience,
        industries=industries,
    )


@router.post("/profiles/upload", response_model=UploadCvResponse)
def upload_cv_text(payload: UploadCvRequest) -> UploadCvResponse:
    return _store_profile(payload.cv_text, payload.preferred_locations)


@router.post("/profiles/upload-file", response_model=UploadCvResponse)
async def upload_cv_file(
    cv_file: UploadFile = File(...),
    preferred_locations: list[str] = Form(default_factory=list),
) -> UploadCvResponse:
    file_content = await cv_file.read()

    if not file_content:
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="uploaded file exceeds 5MB limit")

    try:
        cv_text = parse_cv_file(cv_file.filename or "cv", file_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(cv_text) < 20:
        raise HTTPException(status_code=400, detail="extracted CV text is too short")

    return _store_profile(cv_text, preferred_locations)


def _role_only_profile(role: str) -> CandidateProfile:
    """Minimal stand-in profile for a search run when no CV profile was built."""
    profile = CandidateProfile(
        profile_id=str(uuid4()),
        raw_cv_text=f"Role-only search: {role}",
        titles=[role],
    )
    repository.save_profile(profile)
    return profile


@router.post("/searches", response_model=SearchResponse)
def run_search(payload: SearchRequest) -> SearchResponse:
    if payload.profile_id:
        profile = repository.get_profile(payload.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="profile not found")
    else:
        profile = _role_only_profile(payload.criteria.role)

    outcome = orchestrator.run_search(profile=profile, criteria=payload.criteria)
    run_id = str(uuid4())
    search_run = StoredSearchRun(
        run_id=run_id,
        profile_id=profile.profile_id,
        criteria=payload.criteria,
        results=outcome.results,
    )
    repository.save_search_run(search_run)
    try:
        repository.save_discovered_jobs(run_id, outcome.raw_postings)
    except Exception:
        logger.exception("failed to persist discovered jobs for run %s", run_id)

    source_status = [
        SourceStatus(source=source, status="ok" if count > 0 else "no_results", count=count)
        for source, count in sorted(outcome.source_counts.items())
    ]
    empty_sources = [status.source for status in source_status if status.status == "no_results"]
    if empty_sources:
        logger.warning(
            "search run %s: %d of %d source(s) returned nothing (%s) — check the source's own "
            "log lines above for the actual failure reason, if any",
            run_id,
            len(empty_sources),
            len(source_status),
            ", ".join(empty_sources),
        )

    return SearchResponse(
        run_id=run_id,
        profile_id=profile.profile_id,
        criteria=payload.criteria,
        results=list(outcome.results),
        source_status=source_status,
    )


@router.get("/searches/{run_id}", response_model=SearchResponse)
def get_search(run_id: str) -> SearchResponse:
    search_run = repository.get_search_run(run_id)
    if not search_run:
        raise HTTPException(status_code=404, detail="search run not found")

    return SearchResponse(
        run_id=search_run.run_id,
        profile_id=search_run.profile_id,
        criteria=search_run.criteria,
        results=list(search_run.results),
    )


class SourceHealthResponse(BaseModel):
    source: str
    status: str
    discovered_count: int
    checked_at: str
    http_status: int | None = None
    error_detail: str | None = None
    diagnosis: str | None = None
    fix_status: str = "none"
    diff_preview: str | None = None
    try_status: str = "none"
    try_detail: str | None = None


def _diff_preview(finding) -> str | None:
    if not finding.proposed_fix_content or not finding.fix_file_path:
        return None
    try:
        current = Path(finding.fix_file_path).read_text()
    except OSError:
        return None
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        finding.proposed_fix_content.splitlines(keepends=True),
        fromfile=f"{finding.source} (current)",
        tofile=f"{finding.source} (proposed)",
    )
    return "".join(diff)


@router.get("/health/sources", response_model=list[SourceHealthResponse])
def get_source_health() -> list[SourceHealthResponse]:
    return [
        SourceHealthResponse(
            source=finding.source,
            status=finding.status,
            discovered_count=finding.discovered_count,
            checked_at=finding.checked_at,
            http_status=finding.http_status,
            error_detail=finding.error_detail,
            diagnosis=finding.diagnosis,
            fix_status=finding.fix_status,
            diff_preview=_diff_preview(finding) if finding.fix_status == "proposed" else None,
            try_status=finding.try_status,
            try_detail=finding.try_detail,
        )
        for finding in repository.get_all_source_health()
    ]


@router.post("/health/sources/{source}/try-fix")
def try_source_fix(source: str) -> dict[str, str]:
    findings = {finding.source: finding for finding in repository.get_all_source_health()}
    finding = findings.get(source)
    if not finding or finding.fix_status != "proposed" or not finding.proposed_fix_content:
        raise HTTPException(status_code=400, detail="no pending fix for this source")

    try:
        try_status, try_detail = health_monitor.try_fix(source, finding, scrapers)
    except health_monitor.TryFixError as exc:
        try_status, try_detail = "failed", str(exc)

    repository.update_try_result(source, try_status, try_detail)
    return {"try_status": try_status, "try_detail": try_detail}


@router.post("/health/sources/{source}/apply-fix")
def apply_source_fix(source: str) -> dict[str, str]:
    findings = {finding.source: finding for finding in repository.get_all_source_health()}
    finding = findings.get(source)
    if not finding or finding.fix_status != "proposed" or not finding.proposed_fix_content:
        raise HTTPException(status_code=400, detail="no pending fix for this source")

    try:
        Path(finding.fix_file_path).write_text(finding.proposed_fix_content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not write fix: {exc}") from exc

    repository.update_fix_status(source, "applied")
    return {"status": "applied"}


@router.post("/health/sources/{source}/dismiss-fix")
def dismiss_source_fix(source: str) -> dict[str, str]:
    repository.update_fix_status(source, "dismissed")
    return {"status": "dismissed"}
