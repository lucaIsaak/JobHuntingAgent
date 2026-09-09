"""Matching run/result/evidence schema and configurable fusion weights."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

SUBSCORE_NAMES = (
    "skills",
    "experience",
    "seniority",
    "semantic",
    "industry",
    "language",
    "education",
    "location",
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "skills": 30,
    "experience": 10,
    "seniority": 10,
    "semantic": 20,
    "industry": 10,
    "language": 10,
    "education": 5,
    "location": 5,
}


class MatchWeights(BaseModel):
    """Configurable fusion weights. Must sum to 100."""

    skills: float = DEFAULT_WEIGHTS["skills"]
    experience: float = DEFAULT_WEIGHTS["experience"]
    seniority: float = DEFAULT_WEIGHTS["seniority"]
    semantic: float = DEFAULT_WEIGHTS["semantic"]
    industry: float = DEFAULT_WEIGHTS["industry"]
    language: float = DEFAULT_WEIGHTS["language"]
    education: float = DEFAULT_WEIGHTS["education"]
    location: float = DEFAULT_WEIGHTS["location"]

    @model_validator(mode="after")
    def _weights_sum_to_100(self) -> "MatchWeights":
        total = sum(self.as_dict().values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"match weights must sum to 100, got {total}")
        return self

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in SUBSCORE_NAMES}


class MatchEvidence(BaseModel):
    candidate_span: str
    job_requirement: str
    subscore_kind: str  # one of SUBSCORE_NAMES


class MatchFilters(BaseModel):
    min_score: float = 0.0
    location: str | None = None
    seniority: str | None = None
    industry: str | None = None
    remote_type: str | None = None  # onsite | hybrid | remote
    language: str | None = None
    employment_type: str | None = None


class MatchResult(BaseModel):
    job_id: str
    overall_fit: float = Field(ge=0.0, le=100.0)
    subscores: dict[str, float] = Field(default_factory=dict)
    match_reasons: list[str] = Field(default_factory=list)
    gap_reasons: list[str] = Field(default_factory=list)
    evidence: list[MatchEvidence] = Field(default_factory=list)
    transition_fit: bool = False
    seniority_mismatch: str | None = None  # "under" | "over" | None
    is_disqualified: bool = False
    confidence: str = "normal"  # "normal" | "low"


class MatchRun(BaseModel):
    run_id: str
    profile_id: str
    weights_used: MatchWeights
    filters_used: MatchFilters
    created_at: str
    results: list[MatchResult] = Field(default_factory=list)
