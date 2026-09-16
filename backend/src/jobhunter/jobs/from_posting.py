"""Converts a live-scraped `JobPosting` into the matcher's structured `Job` schema.

A smaller, job-side analogue of the CV extractor: reuses the same catalogs/heuristics
(`candidate/normalize.py`) rather than duplicating them, so a skill or industry tag means the
same thing on both sides of a match. Free-text scraped postings give no reliable must-have/
nice-to-have skill signal, general requirement text, or certification signal, so those all
default to empty/absent rather than being guessed. Language is the one exception handled below:
postings usually state it plainly enough ("you need to speak German and English, French is a
plus") to distinguish a real requirement from a nice-to-have — inventing any of the other fields
above would let Layer A hard-knockout a candidate over a constraint the posting never actually
stated.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from jobhunter.candidate.normalize import (
    DOMAIN_SIGNALS,
    LANGUAGE_DISPLAY,
    LANGUAGE_LEVELS,
    LANGUAGE_NAMES,
    SKILLS_CATALOG,
    contains_phrase,
    infer_seniority,
    normalize,
    normalize_skill,
    normalize_title,
)
from jobhunter.jobs.schema import Job, JobLanguageRequirement, JobSkill
from jobhunter.models.job import JobPosting
from jobhunter.services.profile_extractor import extract_years_of_experience

_ALL_SKILL_TERMS = sorted({term for terms in SKILLS_CATALOG.values() for term in terms}, key=len, reverse=True)

_REQUIRED_LANGUAGE_QUALIFIERS = (
    "required", "require", "requires", "must", "essential", "mandatory", "necessary", "need",
    "prerequisite",
    "erforderlich", "vorausgesetzt", "zwingend", "notwendig", "voraussetzung", "pflicht", "benötigt",
)
_OPTIONAL_LANGUAGE_QUALIFIERS = (
    "plus", "nice to have", "advantage", "beneficial", "bonus", "desirable", "optional",
    "von vorteil", "wünschenswert", "vorteilhaft", "willkommen",
)
_LEVEL_KEYS_BY_LENGTH_DESC = sorted(LANGUAGE_LEVELS, key=len, reverse=True)


def _job_id_for_url(url: str) -> str:
    """Deterministic id so re-discovering the same posting on a later search upserts instead of
    duplicating."""
    return "live:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _remote_type(posting: JobPosting) -> str:
    if posting.is_remote:
        return "remote"
    if "hybrid" in posting.description.lower():
        return "hybrid"
    return "onsite"


def _extract_required_languages(description: str) -> list[JobLanguageRequirement]:
    """Only records a language as required when its own sentence/clause also carries an
    explicit "required"/"must" cue — a bare mention (the posting is written in English, the
    company operates in Germany, a duty involves translating between languages) is not treated
    as a candidate requirement. A clause carrying a competing "plus"/"nice to have" cue is
    treated as optional and skipped even if a required-sounding word appears too, and a clause
    with neither cue is left out entirely — same conservative default as the other unproven
    fields in this module. Level detection is best-effort per clause (like the CV extractor's),
    so a clause naming two languages at different levels may mislabel one — harmless here since
    the matching engine's hard-knockout check only looks at the language name, never the level.
    """
    requirements: dict[str, JobLanguageRequirement] = {}
    for segment in re.split(r"[.,;\n]", description):
        normalized_segment = normalize(segment)
        if not any(contains_phrase(normalized_segment, qualifier) for qualifier in _REQUIRED_LANGUAGE_QUALIFIERS):
            continue
        if any(contains_phrase(normalized_segment, qualifier) for qualifier in _OPTIONAL_LANGUAGE_QUALIFIERS):
            continue

        level = "unspecified"
        for level_key in _LEVEL_KEYS_BY_LENGTH_DESC:
            if contains_phrase(normalized_segment, level_key):
                level = level_key.upper() if len(level_key) <= 2 else level_key
                break

        for name in LANGUAGE_NAMES:
            if not contains_phrase(normalized_segment, name):
                continue
            display_name = LANGUAGE_DISPLAY.get(name, name.title())
            requirements.setdefault(display_name.lower(), JobLanguageRequirement(language=display_name, level=level))

    return list(requirements.values())


def convert_posting(posting: JobPosting) -> Job:
    combined_text = f"{posting.title} {posting.description}"
    normalized_text = normalize(combined_text)

    matched_skills = sorted({term for term in _ALL_SKILL_TERMS if contains_phrase(normalized_text, term)})
    skills = [
        JobSkill(name=term, normalized_name=normalize_skill(term), is_must_have=False)
        for term in matched_skills
    ]

    # Company name is checked separately from title/description (not folded into
    # `normalized_text` above) so it only feeds industry inference, not skill matching —
    # a company like "SAP" or "IBM" would otherwise spuriously tag every one of its postings
    # with the matching skill regardless of what the role actually involves.
    industry_text = normalize(f"{combined_text} {posting.company}")
    industry_tags = sorted(
        tag for tag, phrases in DOMAIN_SIGNALS.items() if any(contains_phrase(industry_text, phrase) for phrase in phrases)
    )

    years = extract_years_of_experience(posting.description)
    seniority, _ = infer_seniority([posting.title], years=years)

    return Job(
        job_id=_job_id_for_url(posting.url),
        title=posting.title,
        normalized_title=normalize_title(posting.title),
        company=posting.company,
        source=posting.source,
        url=posting.url,
        industry=industry_tags[0] if industry_tags else None,
        function=industry_tags[1] if len(industry_tags) > 1 else None,
        location=posting.location,
        remote_type=_remote_type(posting),
        employment_type=posting.employment_type.value,
        seniority=seniority,
        description=posting.description,
        skills=skills,
        languages_required=_extract_required_languages(posting.description),
        years_experience_min=years,
        years_experience_max=None,
        updated_at=datetime.now(UTC).isoformat(),
    )
