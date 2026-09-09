"""User profile and search input schemas."""

from enum import StrEnum

from pydantic import BaseModel, Field

from jobhunter.models.job import EmploymentType


class SeniorityLevel(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class CandidateProfile(BaseModel):
    """Normalized candidate profile extracted from a CV."""

    profile_id: str
    raw_cv_text: str
    skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    seniority: SeniorityLevel | None = None
    years_of_experience: int | None = None
    skill_categories: dict[str, list[str]] = Field(default_factory=dict)


class SearchCriteria(BaseModel):
    """User-entered role, keywords, and filters."""

    role: str = Field(min_length=2)
    location: str | None = None
    keywords: list[str] = Field(default_factory=list)
    remote_only: bool = False
    employment_types: list[EmploymentType] = Field(default_factory=list)
    limit: int = Field(default=25, ge=1, le=200)
    sources: list[str] = Field(default_factory=list)
