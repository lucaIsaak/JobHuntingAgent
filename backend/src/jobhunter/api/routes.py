"""HTTP routes the frontend calls (trigger search, fetch results, etc.)."""

from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from jobhunter.agent.orchestrator import JobSearchOrchestrator
from jobhunter.config import settings
from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.linkedin import LinkedInScraper
from jobhunter.scrapers.arbeitnow import ArbeitnowScraper
from jobhunter.scrapers.adzuna import AdzunaScraper
from jobhunter.scrapers.indeed import IndeedScraper
from jobhunter.scrapers.glassdoor import GlassdoorScraper
from jobhunter.scrapers.stepstone import StepStoneScraper
from jobhunter.scrapers.xing import XingScraper
from jobhunter.services.cv_parser import parse_cv_file
from jobhunter.storage.repository import SQLiteRepository, StoredSearchRun

router = APIRouter(prefix="/api")
repository = SQLiteRepository(database_path=settings.database_path)
scrapers = [
    LinkedInScraper(),
    XingScraper(),
    StepStoneScraper(),
    IndeedScraper(),
    GlassdoorScraper(),
]
if settings.live_jobs_enabled:
    scrapers.insert(0, ArbeitnowScraper())
    if settings.adzuna_app_id and settings.adzuna_app_key:
        scrapers.insert(
            0,
            AdzunaScraper(
                app_id=settings.adzuna_app_id,
                app_key=settings.adzuna_app_key,
                country=settings.adzuna_country,
            ),
        )

orchestrator = JobSearchOrchestrator(scrapers=scrapers)


class UploadCvRequest(BaseModel):
    cv_text: str = Field(min_length=20)
    preferred_locations: list[str] = Field(default_factory=list)


class UploadCvResponse(BaseModel):
    profile_id: str
    skills: list[str]
    titles: list[str]


class SearchRequest(BaseModel):
    profile_id: str
    criteria: SearchCriteria


class SearchResponse(BaseModel):
    run_id: str
    profile_id: str
    criteria: SearchCriteria
    results: list[MatchResult]


def _extract_profile(cv_text: str) -> tuple[list[str], list[str]]:
    tokens = [token.strip(".,").lower() for token in cv_text.split()]
    skills_catalog = {"python", "fastapi", "sql", "docker", "aws", "kubernetes", "pandas"}
    titles_catalog = {"engineer", "developer", "analyst", "scientist", "manager", "intern"}

    skills = sorted({token for token in tokens if token in skills_catalog})
    titles = sorted({token for token in tokens if token in titles_catalog})

    if not skills:
        skills = ["python"]

    return skills, titles


def _store_profile(cv_text: str, preferred_locations: list[str]) -> UploadCvResponse:
    profile_id = str(uuid4())
    skills, titles = _extract_profile(cv_text)

    profile = CandidateProfile(
        profile_id=profile_id,
        raw_cv_text=cv_text,
        skills=skills,
        titles=titles,
        preferred_locations=preferred_locations,
    )
    repository.save_profile(profile)

    return UploadCvResponse(profile_id=profile_id, skills=skills, titles=titles)


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


@router.post("/searches", response_model=SearchResponse)
def run_search(payload: SearchRequest) -> SearchResponse:
    profile = repository.get_profile(payload.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")

    results = orchestrator.run_search(profile=profile, criteria=payload.criteria)
    run_id = str(uuid4())
    search_run = StoredSearchRun(
        run_id=run_id,
        profile_id=payload.profile_id,
        criteria=payload.criteria,
        results=results,
    )
    repository.save_search_run(search_run)

    return SearchResponse(
        run_id=run_id,
        profile_id=payload.profile_id,
        criteria=payload.criteria,
        results=list(results),
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
