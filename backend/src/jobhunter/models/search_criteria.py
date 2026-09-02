"""User profile and search input schemas."""

from pydantic import BaseModel, Field

from jobhunter.models.job import EmploymentType


class CandidateProfile(BaseModel):
    """Normalized candidate profile extracted from a CV."""

    profile_id: str
    raw_cv_text: str
    skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)


class SearchCriteria(BaseModel):
    """User-entered role, keywords, and filters."""

    role: str | None = None
    location: str | None = None
    keywords: list[str] = Field(default_factory=list)
    remote_only: bool = False
    employment_types: list[EmploymentType] = Field(default_factory=list)
    limit: int = Field(default=25, ge=1, le=200)
