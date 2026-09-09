"""Rich, provenance-tracked candidate profile schema for the CV-to-job matcher.

Distinct from `jobhunter.models.search_criteria.CandidateProfile`, which stays as-is for the
live-scraper search flow. This is the schema used by the new candidate/matching subsystem.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionEvidence(BaseModel):
    """Where an extracted value came from, and how sure the extractor is about it."""

    source_page: int | None = None
    source_text: str
    confidence: float = Field(ge=0.0, le=1.0)


class Skill(BaseModel):
    name: str
    normalized_name: str
    category: str
    is_soft_skill: bool = False
    proficiency: str | None = None
    years_hint: int | None = None
    last_used_hint: str | None = None
    evidence: list[ExtractionEvidence] = Field(default_factory=list)


class Certification(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None
    cert_id: str | None = None
    evidence: ExtractionEvidence


class Language(BaseModel):
    language: str
    iso_code: str | None = None
    level: str
    evidence: ExtractionEvidence


class Achievement(BaseModel):
    text: str
    value: float | None = None
    unit: str | None = None
    context: str | None = None


class Experience(BaseModel):
    title: str
    normalized_title: str
    company: str
    company_normalized: str
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    duration_months: int | None = None
    location: str | None = None
    employment_type: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    skills_used: list[str] = Field(default_factory=list)
    industry: str | None = None
    domain: str | None = None
    tools: list[str] = Field(default_factory=list)
    methodologies: list[str] = Field(default_factory=list)
    team_size: int | None = None
    reports_to: str | None = None
    people_managed: int | None = None
    evidence: ExtractionEvidence


class Education(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start: str | None = None
    end: str | None = None
    grade: str | None = None
    coursework: list[str] = Field(default_factory=list)
    honors: list[str] = Field(default_factory=list)
    location: str | None = None
    evidence: ExtractionEvidence


class CompanyMention(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    industry: str | None = None
    size_hint: str | None = None
    notable_context: str | None = None


class Project(BaseModel):
    title: str
    role: str | None = None
    start: str | None = None
    end: str | None = None
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    impact: str | None = None
    links: list[str] = Field(default_factory=list)
    kind: str = "project"  # project | publication | patent | volunteering | award


class Constraints(BaseModel):
    work_authorization: str | None = None
    notice_period: str | None = None
    salary_expectation: str | None = None
    remote_preference: str | None = None
    travel: str | None = None
    visa: str | None = None
    availability: str | None = None


class CandidateProfile(BaseModel):
    """Normalized, provenance-tracked profile extracted from a CV."""

    profile_id: str
    candidate_id: str

    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    location: str | None = None
    relocation_willingness: str | None = None

    headline: str | None = None
    years_of_experience_total: float | None = None
    seniority_level: str | None = None
    seniority_inferred: bool = False
    detected_cv_language: str | None = None
    career_timeline: list[str] = Field(default_factory=list)

    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    companies: list[CompanyMention] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)

    industries: list[str] = Field(default_factory=list)
    subdomains: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)

    constraints: Constraints = Field(default_factory=Constraints)

    original_text: str = ""
    cleaned_text: str = ""

    field_evidence: dict[str, ExtractionEvidence] = Field(default_factory=dict)
    extraction_confidence: float = 0.0
    extraction_source: str = "rules"  # "rules" | "rules+llm"


class Candidate(BaseModel):
    """Lightweight identity record. A candidate can accumulate multiple profile versions."""

    candidate_id: str
    created_at: str
    latest_profile_id: str
    cv_filename: str | None = None
