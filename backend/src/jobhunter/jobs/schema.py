"""Structured job schema for the curated jobs database (distinct from the live-scraper
`jobhunter.models.job.JobPosting`, which stays as-is)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobRequirement(BaseModel):
    text: str
    is_must_have: bool = True
    kind: str = "other"  # skill | cert | language | education | experience | other


class JobSkill(BaseModel):
    name: str
    normalized_name: str
    is_must_have: bool = True


class JobLanguageRequirement(BaseModel):
    language: str
    level: str  # A1-C2 | native | fluent | professional | basic


class Job(BaseModel):
    job_id: str
    title: str
    normalized_title: str
    company: str
    industry: str | None = None
    function: str | None = None

    location: str | None = None
    remote_type: str = "onsite"  # onsite | hybrid | remote
    employment_type: str = "full_time"
    seniority: str | None = None

    description: str = ""
    requirements_must: list[str] = Field(default_factory=list)
    requirements_nice: list[str] = Field(default_factory=list)

    skills: list[JobSkill] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages_required: list[JobLanguageRequirement] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    # Structured so Layer A's must-have-cert knockout can run as SQL rather than text-matching
    # requirements_must; a name here is expected to also appear in requirements_must as prose.
    required_certifications: list[str] = Field(default_factory=list)

    years_experience_min: int | None = None
    years_experience_max: int | None = None
    salary_range: str | None = None

    embedding_json: str | None = None
    updated_at: str = ""
