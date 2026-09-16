"""Normalization primitives for the candidate extractor: skill/title/company synonyms, date
parsing, seniority inference, language-level ordinals, and multilingual section headers.

Builds on `jobhunter.services.profile_extractor`'s `normalize`/`contains_phrase` helpers and
catalogs rather than duplicating them from scratch.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from jobhunter.services.profile_extractor import (
    DOMAIN_SIGNALS,
    contains_phrase,
    find_matching_terms,
    normalize,
)

__all__ = [
    "DOMAIN_SIGNALS",
    "LANGUAGE_LEVELS",
    "SECTION_HEADERS",
    "SKILLS_CATALOG",
    "SKILL_SYNONYMS",
    "contains_phrase",
    "duration_months",
    "find_matching_terms",
    "infer_seniority",
    "normalize",
    "normalize_company",
    "normalize_skill",
    "normalize_title",
    "parse_date_range",
    "years_of_experience_total",
]

# ---------------------------------------------------------------------------
# Skills catalog — extends profile_extractor.SKILLS_CATALOG with marketing/analytics/business
# terms the spec explicitly calls out (current catalog skews software/data-heavy).
# ---------------------------------------------------------------------------

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
        "looker", "dbt", "snowflake", "big query", "statistics", "a b testing",
    ],
    "marketing": [
        "seo", "sem", "ppc", "google ads", "google analytics", "content marketing",
        "email marketing", "social media marketing", "brand strategy", "growth marketing",
        "performance marketing", "marketing automation", "hubspot", "mailchimp",
        "campaign management", "copywriting", "influencer marketing", "crm",
        "salesforce", "conversion rate optimization", "market research", "media planning",
    ],
    "business_soft_skills": [
        "project management", "product management", "stakeholder management", "agile",
        "scrum", "kanban", "leadership", "communication", "negotiation", "presentation",
        "public speaking", "strategy", "consulting", "client management",
        "cross functional collaboration", "mentoring", "budgeting", "forecasting",
        "sales", "account management", "business development", "customer success",
    ],
    "methodologies": [
        "agile", "scrum", "kanban", "lean", "six sigma", "waterfall", "devops", "tdd",
        "okrs", "design thinking",
    ],
}

# Which top-level categories count as "soft" for Skill.is_soft_skill.
SOFT_SKILL_CATEGORIES = {"business_soft_skills"}

# ---------------------------------------------------------------------------
# Skill synonym normalization — raw form (lowercased) -> canonical display form.
# ---------------------------------------------------------------------------

SKILL_SYNONYMS: dict[str, str] = {
    "python3": "Python", "py": "Python",
    "js": "JavaScript", "javascript es6": "JavaScript",
    "ts": "TypeScript",
    "powerbi": "Power BI", "power bi": "Power BI",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "ai": "Artificial Intelligence",
    "k8s": "Kubernetes",
    "gcp": "Google Cloud Platform", "google cloud": "Google Cloud Platform",
    "reactjs": "React", "react.js": "React",
    "nodejs": "Node.js", "node": "Node.js", "node js": "Node.js",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "ms excel": "Excel", "microsoft excel": "Excel",
    "ga4": "Google Analytics", "google analytics": "Google Analytics",
    "google ads": "Google Ads", "adwords": "Google Ads", "google adwords": "Google Ads",
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "next js": "Next.js", "nextjs": "Next.js",
    "ci cd": "CI/CD", "ci/cd": "CI/CD",
    "a b testing": "A/B Testing", "ab testing": "A/B Testing",
    "scikit learn": "scikit-learn",
    "big query": "BigQuery", "bigquery": "BigQuery",
}

_ACRONYMS = {
    "sql", "aws", "gcp", "api", "etl", "nlp", "ml", "ai", "crm", "seo", "sem", "ppc",
    "kpi", "roi", "html", "css", "php", "cfa", "pmp", "mba", "b2b", "b2c", "cpg", "ux",
    "ui", "sdk", "grpc", "tdd", "okrs",
}


def normalize_skill(name: str) -> str:
    """Map a raw skill mention to its canonical display form. Never fabricates — falls back to
    the original text (acronym-cased when recognized) when no synonym is known."""
    stripped = name.strip()
    key = stripped.lower()
    if key in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[key]
    if key in _ACRONYMS:
        return key.upper()
    return stripped


def skill_category(normalized_name: str) -> str:
    """Best-effort catalog category for a normalized skill name; 'other' when unknown."""
    lowered = normalized_name.lower()
    for category, terms in SKILLS_CATALOG.items():
        if any(term == lowered or contains_phrase(f" {lowered} ", term) for term in terms):
            return category
    return "other"


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------

_SENIORITY_PREFIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(sr\.?|senior)\s+", re.IGNORECASE), "Senior "),
    (re.compile(r"^(jr\.?|junior)\s+", re.IGNORECASE), "Junior "),
    (re.compile(r"^(lead)\s+", re.IGNORECASE), "Lead "),
    (re.compile(r"^(principal)\s+", re.IGNORECASE), "Principal "),
    (re.compile(r"^(staff)\s+", re.IGNORECASE), "Staff "),
]


def normalize_title(title: str) -> str:
    """'Sr. Data Analyst' -> 'Senior Data Analyst'. Grounded rewrite only, no fabrication."""
    stripped = title.strip()
    if not stripped:
        return stripped
    for pattern, canonical in _SENIORITY_PREFIXES:
        match = pattern.match(stripped)
        if match:
            return f"{canonical}{stripped[match.end():].strip()}"
    return stripped


# ---------------------------------------------------------------------------
# Company normalization
# ---------------------------------------------------------------------------

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|gmbh|corp|corporation|co|company|ag|s\.?a\.?|plc)\b\.?",
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    stripped = _COMPANY_SUFFIXES.sub("", name)
    stripped = re.sub(r"[,.]+$", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,.")
    return stripped or name.strip()


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_MONTHS: dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

PRESENT_WORDS = {
    "present", "current", "currently", "now", "today", "ongoing",
    "heute", "aktuell", "gegenwärtig", "derzeit",
    "actuel", "présent", "présente",
    "presente", "actual", "actualidad",
}

_MONTH_NAME_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_TOKEN = rf"(?:(?:{_MONTH_NAME_PATTERN})\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
_PRESENT_PATTERN = "|".join(re.escape(word) for word in sorted(PRESENT_WORDS, key=len, reverse=True))
_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*(?:-|–|—|to|bis|à|a)\s*(?P<end>{_DATE_TOKEN}|{_PRESENT_PATTERN})",
    re.IGNORECASE,
)
_ACADEMIC_YEAR_RE = re.compile(r"\b(?P<start>\d{4})/(?P<end>\d{4})\b")
_BARE_DATE_RE = re.compile(_DATE_TOKEN, re.IGNORECASE)


def _parse_token(token: str) -> str | None:
    token = token.strip().rstrip(".")
    match = re.match(r"^(\d{1,2})/(\d{4})$", token)
    if match:
        month, year = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
        return None
    match = re.match(r"^([A-Za-zÀ-ÿ]+)\.?\s+(\d{4})$", token)
    if match:
        month = _MONTHS.get(match.group(1).lower())
        year = int(match.group(2))
        if month:
            return f"{year:04d}-{month:02d}"
        return None
    match = re.match(r"^(\d{4})$", token)
    if match:
        return match.group(1)
    return None


def parse_date_range(text: str, as_of: date | None = None) -> tuple[str | None, str | None, bool]:
    """Extract (start, end, is_current) from free text. Dates are 'YYYY-MM' or 'YYYY' strings.
    'Present'/'Aktuell'/... resolves to `as_of` (default: today) so callers can pin it for
    deterministic tests. Returns (None, None, False) when nothing recognizable is found."""
    as_of = as_of or date.today()

    academic = _ACADEMIC_YEAR_RE.search(text)
    if academic and not _RANGE_RE.search(text):
        return academic.group("start"), academic.group("end"), False

    match = _RANGE_RE.search(text)
    if match:
        start = _parse_token(match.group("start"))
        end_token = match.group("end")
        if end_token.strip().lower().rstrip(".") in PRESENT_WORDS:
            return start, f"{as_of.year:04d}-{as_of.month:02d}", True
        return start, _parse_token(end_token), False

    single = _BARE_DATE_RE.search(text)
    if single:
        return _parse_token(single.group(0)), None, False

    return None, None, False


def _split_year_month(value: str) -> tuple[int | None, int | None]:
    match = re.match(r"^(\d{4})(?:-(\d{2}))?$", value)
    if not match:
        return None, None
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    return year, month


def duration_months(start: str | None, end: str | None) -> int | None:
    """Whole months spanned by a single [start, end] pair. Per-entry only — no overlap logic."""
    if not start or not end:
        return None
    start_year, start_month = _split_year_month(start)
    end_year, end_month = _split_year_month(end)
    if start_year is None or end_year is None:
        return None
    start_month = start_month or 1
    end_month = end_month or 12
    months = (end_year - start_year) * 12 + (end_month - start_month) + 1
    return max(months, 0)


def years_of_experience_total(
    ranges: Iterable[tuple[str | None, str | None]], as_of: date | None = None
) -> float:
    """Sum of non-overlapping [start, end] month intervals, in years (rounded to 1 decimal).
    Concurrent/overlapping roles are merged first so they aren't double-counted."""
    as_of = as_of or date.today()
    as_of_index = as_of.year * 12 + (as_of.month - 1)

    intervals: list[tuple[int, int]] = []
    for start, end in ranges:
        if not start:
            continue
        start_year, start_month = _split_year_month(start)
        if start_year is None:
            continue
        start_index = start_year * 12 + ((start_month or 1) - 1)

        if end:
            end_year, end_month = _split_year_month(end)
            if end_year is None:
                continue
            end_index = end_year * 12 + ((end_month or 12) - 1)
        else:
            end_index = as_of_index

        if end_index >= start_index:
            intervals.append((start_index, end_index))

    if not intervals:
        return 0.0

    intervals.sort()
    merged = [intervals[0]]
    for start_index, end_index in intervals[1:]:
        last_start, last_end = merged[-1]
        if start_index <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end_index))
        else:
            merged.append((start_index, end_index))

    total_months = sum(end_index - start_index + 1 for start_index, end_index in merged)
    return round(total_months / 12, 1)


# ---------------------------------------------------------------------------
# Seniority inference
# ---------------------------------------------------------------------------

_SENIORITY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("executive", ("chief", "cxo", "vp", "vice president", "president")),
    ("director", ("director", "head of")),
    ("manager", ("manager", "engineering manager", "team lead")),
    ("lead", ("lead", "principal", "staff")),
    ("senior", ("senior", "sr.")),
    ("junior", ("junior", "jr.", "entry level")),
    ("intern", ("intern", "internship")),
]

_YEARS_TO_SENIORITY: list[tuple[float, str]] = [
    (1, "junior"),
    (4, "mid"),
    (8, "senior"),
    (12, "lead"),
]

SENIORITY_LEVELS = (
    "intern", "junior", "mid", "senior", "lead", "manager", "director", "executive",
)


def infer_seniority(titles: Iterable[str], years: float | None) -> tuple[str | None, bool]:
    """Returns (level, inferred). inferred=False when an explicit title keyword matched,
    True when derived from years of experience alone."""
    combined = normalize(" ".join(titles))
    for level, keywords in _SENIORITY_KEYWORDS:
        if any(contains_phrase(combined, keyword) for keyword in keywords):
            return level, False

    if years is None:
        return None, False
    for threshold, level in _YEARS_TO_SENIORITY:
        if years <= threshold:
            return level, True
    return "director", True


# ---------------------------------------------------------------------------
# Language proficiency ordinals
# ---------------------------------------------------------------------------

LANGUAGE_LEVELS: dict[str, int] = {
    "a1": 1, "a2": 2, "basic": 2,
    "b1": 3, "intermediate": 3, "conversational": 3,
    "b2": 4, "professional": 4, "working proficiency": 4, "professional working proficiency": 4,
    "c1": 5, "advanced": 5, "fluent": 5,
    "c2": 6, "native": 6, "bilingual": 6, "mother tongue": 6,
}


def language_level_rank(level: str) -> int:
    return LANGUAGE_LEVELS.get(level.strip().lower(), 0)


# ---------------------------------------------------------------------------
# Multilingual section headers — canonical section name -> header phrases across en/de/fr/es,
# so a non-English CV still segments into sections instead of falling into one undifferentiated
# block (spec: "detect language of the CV and still extract multilingual content").
# ---------------------------------------------------------------------------

SECTION_HEADERS: dict[str, tuple[str, ...]] = {
    "experience": (
        "experience", "work experience", "professional experience", "employment history",
        "career history",
        "berufserfahrung", "praktische erfahrung", "beruflicher werdegang",
        "expérience professionnelle", "expérience", "parcours professionnel",
        "experiencia laboral", "experiencia profesional", "trayectoria profesional",
    ),
    "education": (
        "education", "academic background", "academic history",
        "ausbildung", "bildung", "schulbildung",
        "formation", "études", "formation académique",
        "educación", "formación académica", "estudios",
    ),
    "skills": (
        "skills", "technical skills", "core competencies", "competencies", "key skills",
        "kenntnisse", "fähigkeiten", "kompetenzen",
        "compétences", "compétences clés",
        "habilidades", "competencias", "aptitudes",
    ),
    "languages": (
        "languages",
        "sprachen", "sprachkenntnisse",
        "langues", "langues parlées",
        "idiomas",
    ),
    "certifications": (
        "certifications", "certificates", "licenses", "licences",
        "zertifikate", "zertifizierungen",
        "certifications professionnelles",
        "certificaciones",
    ),
    "projects": ("projects", "key projects", "projekte", "projets", "proyectos"),
    "publications": (
        "publications", "veröffentlichungen", "publications scientifiques", "publicaciones",
    ),
    "awards": ("awards", "honors", "honours", "auszeichnungen", "distinctions", "premios", "logros"),
    "volunteering": (
        "volunteering", "volunteer experience", "ehrenamt", "ehrenamtliche tätigkeit",
        "bénévolat", "voluntariado",
    ),
    "summary": (
        "summary", "profile", "about", "about me", "objective",
        "zusammenfassung", "profil", "über mich",
        "résumé", "à propos",
        "resumen", "perfil", "acerca de",
    ),
}
