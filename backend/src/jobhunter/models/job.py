"""Job and match result schemas."""

from enum import StrEnum

from pydantic import BaseModel, Field


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class JobPosting(BaseModel):
    """Normalized posting returned by all scrapers."""

    source: str
    title: str
    company: str
    location: str
    is_remote: bool = False
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    description: str
    url: str


class MatchResult(BaseModel):
    """Scored result for a posting against a profile."""

    job: JobPosting
    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
