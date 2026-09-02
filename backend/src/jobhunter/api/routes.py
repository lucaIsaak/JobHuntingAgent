"""HTTP routes the frontend calls (trigger search, fetch results, etc.)."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobhunter.agent.orchestrator import JobSearchOrchestrator
from jobhunter.models.job import MatchResult
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.linkedin import LinkedInScraper
from jobhunter.storage.repository import InMemoryRepository, StoredSearchRun

router = APIRouter(prefix="/api")
repository = InMemoryRepository()
orchestrator = JobSearchOrchestrator(scrapers=[LinkedInScraper()])


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


def _extract_profile(cv_text: str, preferred_locations: list[str]) -> tuple[list[str], list[str]]:
    tokens = [token.strip(".,").lower() for token in cv_text.split()]
    skills_catalog = {"python", "fastapi", "sql", "docker", "aws", "kubernetes", "pandas"}
    titles_catalog = {"engineer", "developer", "analyst", "scientist", "manager", "intern"}

    skills = sorted({token for token in tokens if token in skills_catalog})
    titles = sorted({token for token in tokens if token in titles_catalog})

    if not skills:
        skills = ["python"]

    return skills, titles


@router.post("/profiles/upload", response_model=UploadCvResponse)
def upload_cv(payload: UploadCvRequest) -> UploadCvResponse:
    profile_id = str(uuid4())
    skills, titles = _extract_profile(payload.cv_text, payload.preferred_locations)
    profile = CandidateProfile(
        profile_id=profile_id,
        raw_cv_text=payload.cv_text,
        skills=skills,
        titles=titles,
        preferred_locations=payload.preferred_locations,
    )
    repository.save_profile(profile)

    return UploadCvResponse(profile_id=profile_id, skills=skills, titles=titles)


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
