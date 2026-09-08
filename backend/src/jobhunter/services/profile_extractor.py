"""Rule-based extraction of skills, seniority, experience and domain signals from CV text."""

import re
from collections.abc import Iterable

from jobhunter.models.search_criteria import SeniorityLevel

_WORD_BOUNDARY = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase and collapse punctuation to single spaces, padded, for whole-phrase search."""
    collapsed = _WORD_BOUNDARY.sub(" ", text.lower())
    return f" {collapsed.strip()} "


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    needle = f" {_WORD_BOUNDARY.sub(' ', phrase.lower()).strip()} "
    return needle in normalized_text


def find_matching_terms(text: str, terms: Iterable[str]) -> list[str]:
    normalized = normalize(text)
    return sorted({term for term in terms if contains_phrase(normalized, term)})


SKILLS_CATALOG: dict[str, list[str]] = {
    "programming_languages": [
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
        "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql",
        "bash", "shell scripting", "html", "css",
    ],
    "frameworks_tools": [
        "fastapi", "django", "flask", "react", "angular", "vue", "node js", "spring",
        "dotnet", "express", "next js", "graphql", "rest api", "grpc", "svelte",
    ],
    "cloud_infra": [
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform",
        "ansible", "jenkins", "ci cd", "linux", "git", "github actions", "microservices",
    ],
    "data_ml": [
        "machine learning", "deep learning", "nlp", "computer vision", "data engineering",
        "data analysis", "data science", "etl", "spark", "hadoop", "airflow", "nosql",
        "mongodb", "postgresql", "mysql", "redis", "kafka", "tableau", "power bi",
        "excel", "pandas", "numpy", "tensorflow", "pytorch", "scikit learn", "keras",
    ],
    "business_soft_skills": [
        "project management", "product management", "stakeholder management", "agile",
        "scrum", "kanban", "leadership", "communication", "negotiation", "presentation",
        "public speaking", "strategy", "consulting", "client management",
        "cross functional collaboration", "mentoring", "budgeting", "forecasting",
    ],
    "methodologies": [
        "agile", "scrum", "kanban", "lean", "six sigma", "waterfall", "devops", "tdd",
    ],
}

TITLES_CATALOG: set[str] = {
    "engineer", "developer", "analyst", "scientist", "manager", "intern",
    "director", "lead", "head", "vp", "president", "consultant", "specialist",
    "architect", "designer", "researcher", "associate", "coordinator", "administrator",
}

DOMAIN_SIGNALS: dict[str, tuple[str, ...]] = {
    "consulting": ("consulting", "consultant", "advisory", "strategy"),
    "finance": ("finance", "banking", "investment", "accounting"),
    "fintech": ("fintech", "payments", "trading", "brokerage", "banking api"),
    "healthcare": ("healthcare", "hospital", "clinical", "pharma"),
    "technology": ("software", "engineering", "developer", "api", "saas"),
    "developer_tools": ("developer tools", "devtools", "sdk", "ci cd", "infrastructure", "api platform"),
    "ai_ml": ("machine learning", "artificial intelligence", "deep learning", "llm", "nlp", "data science"),
    "productivity_saas": ("productivity", "collaboration", "workflow", "project management tool"),
    "marketplace_delivery": ("marketplace", "delivery", "logistics", "gig economy", "on demand"),
    "hr_tech": ("recruiting", "payroll", "human resources", "hr tech", "talent"),
    "design": ("design", "ux", "ui", "figma", "prototyping"),
    "crypto_web3": ("crypto", "blockchain", "web3", "defi", "nft"),
    "marketing": ("marketing", "brand", "campaign", "communications"),
}

_YEARS_PATTERNS = [
    re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s*)?experience", re.I),
    re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:in|as|working)", re.I),
]

_SENIORITY_KEYWORDS: list[tuple[SeniorityLevel, tuple[str, ...]]] = [
    (SeniorityLevel.EXECUTIVE, ("chief", "cxo", "vp", "vice president", "president")),
    (SeniorityLevel.DIRECTOR, ("director", "head of")),
    (SeniorityLevel.MANAGER, ("manager", "engineering manager", "team lead")),
    (SeniorityLevel.LEAD, ("lead", "principal", "staff")),
    (SeniorityLevel.SENIOR, ("senior", "sr.")),
    (SeniorityLevel.JUNIOR, ("junior", "jr.", "entry level")),
    (SeniorityLevel.INTERN, ("intern", "internship")),
]

_YEARS_TO_SENIORITY: list[tuple[int, SeniorityLevel]] = [
    (1, SeniorityLevel.JUNIOR),
    (4, SeniorityLevel.MID),
    (8, SeniorityLevel.SENIOR),
    (12, SeniorityLevel.LEAD),
]


def extract_skills(cv_text: str) -> tuple[list[str], dict[str, list[str]]]:
    normalized = normalize(cv_text)
    by_category = {
        category: sorted({term for term in terms if contains_phrase(normalized, term)})
        for category, terms in SKILLS_CATALOG.items()
    }
    flat = sorted({term for terms in by_category.values() for term in terms})
    if not flat:
        flat = ["python"]
    return flat, {category: terms for category, terms in by_category.items() if terms}


def extract_titles(cv_text: str) -> list[str]:
    return find_matching_terms(cv_text, TITLES_CATALOG)


def extract_years_of_experience(cv_text: str) -> int | None:
    matches = [int(match.group(1)) for pattern in _YEARS_PATTERNS for match in pattern.finditer(cv_text)]
    return max(matches) if matches else None


def extract_seniority(cv_text: str, years: int | None) -> SeniorityLevel | None:
    normalized = normalize(cv_text)
    for level, keywords in _SENIORITY_KEYWORDS:
        if any(contains_phrase(normalized, keyword) for keyword in keywords):
            return level

    if years is None:
        return None
    for threshold, level in _YEARS_TO_SENIORITY:
        if years <= threshold:
            return level
    return SeniorityLevel.DIRECTOR


def extract_domain_tags(text: str) -> list[str]:
    normalized = normalize(text)
    return sorted(
        tag for tag, phrases in DOMAIN_SIGNALS.items() if any(contains_phrase(normalized, phrase) for phrase in phrases)
    )
