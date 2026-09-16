"""Section-based, rule-driven CV extractor. Zero external calls, works standalone.

Splits CV text into labeled sections (multilingual header matching), then applies regex/heuristic
parsing per section. Every extracted field carries an `ExtractionEvidence` snippet + confidence.
Never fabricates: unmatched fields stay `None`/empty rather than being guessed or defaulted.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from jobhunter.candidate.normalize import (
    DOMAIN_SIGNALS,
    LANGUAGE_LEVELS,
    SECTION_HEADERS,
    SKILLS_CATALOG,
    SOFT_SKILL_CATEGORIES,
    contains_phrase,
    duration_months,
    infer_seniority,
    normalize,
    normalize_company,
    normalize_skill,
    normalize_title,
    parse_date_range,
    skill_category,
    years_of_experience_total,
)
from jobhunter.candidate.schema import (
    Achievement,
    CandidateProfile,
    Certification,
    CompanyMention,
    Constraints,
    Education,
    Experience,
    ExtractionEvidence,
    Language,
    Project,
    Skill,
)

logger = logging.getLogger(__name__)

CONFIDENCE_EXPLICIT = 0.9
CONFIDENCE_INFERRED = 0.6
CONFIDENCE_WEAK = 0.4

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}")
_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[\w-]+\.[a-z]{2,}(?:/[^\s,;]*)?", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[\w-]+", re.IGNORECASE)

_BULLET_RE = re.compile(r"^\s*[-•*•]\s*(.+)$")
_METRIC_RE = re.compile(
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>%|percent|x|k|m|million|billion|users?|customers?|"
    r"€|\$|£|hours?|days?|points?)",
    re.IGNORECASE,
)

_DEGREE_KEYWORDS = (
    "bachelor", "master", "phd", "ph.d", "mba", "b.sc", "bsc", "m.sc", "msc", "b.a", "ba ",
    "m.a", "ma ", "associate degree", "diploma", "bachelor's", "master's", "doctorate",
)
_INSTITUTION_KEYWORDS = (
    "university", "college", "institute", "hochschule", "universität", "école", "universidad",
    "polytechnic", "academy",
)
_GPA_RE = re.compile(r"(?:gpa|grade)[:\s]*([0-4]\.\d{1,2}|\d{1,2}[.,]\d{1,2}\s*/\s*\d{1,2})", re.IGNORECASE)

_CERT_ACRONYMS = (
    "pmp", "pmi-acp", "cfa", "cpa", "scrum master", "csm", "psm", "cissp", "six sigma",
    "aws certified", "azure certified", "gcp certified", "google cloud certified",
    "comptia", "itil", "cma",
)
_CERT_PATTERN_RE = re.compile(r"([\w .&/-]*?\bcertifi(?:ed|cation)\b[\w .&/-]*)", re.IGNORECASE)

_LANGUAGE_NAMES = (
    "english", "german", "french", "spanish", "italian", "portuguese", "dutch", "mandarin",
    "chinese", "japanese", "korean", "russian", "arabic", "polish", "turkish", "hindi",
    "deutsch", "englisch", "französisch", "spanisch", "français", "anglais", "allemand",
    "espagnol", "inglés", "alemán", "francés",
)
_LANGUAGE_DISPLAY = {
    "deutsch": "German", "englisch": "English", "französisch": "French", "spanisch": "Spanish",
    "français": "French", "anglais": "English", "allemand": "German", "espagnol": "Spanish",
    "inglés": "English", "alemán": "German", "francés": "French",
}
_ISO_CODES = {
    "english": "en", "german": "de", "french": "fr", "spanish": "es", "italian": "it",
    "portuguese": "pt", "dutch": "nl", "mandarin": "zh", "chinese": "zh", "japanese": "ja",
    "korean": "ko", "russian": "ru", "arabic": "ar", "polish": "pl", "turkish": "tr", "hindi": "hi",
}

_CONSTRAINT_PATTERNS: dict[str, re.Pattern[str]] = {
    "work_authorization": re.compile(
        r"(work authoriz\w+|authorized to work|arbeitserlaubnis)[:\s]*([^\n.]{0,80})", re.IGNORECASE
    ),
    "visa": re.compile(r"(visa[^\n.]{0,80})", re.IGNORECASE),
    "notice_period": re.compile(r"(notice period[:\s]*[^\n.]{0,40})", re.IGNORECASE),
    "salary_expectation": re.compile(
        r"(expected salary|salary expectation)[:\s]*([^\n.]{0,60})", re.IGNORECASE
    ),
    "travel": re.compile(r"(willing to travel|travel[:\s]*\d{1,3}%)[^\n.]{0,40}", re.IGNORECASE),
    "availability": re.compile(r"(available from|availability)[:\s]*([^\n.]{0,40})", re.IGNORECASE),
}
_REMOTE_PREFERENCE_RE = re.compile(r"\b(remote|hybrid|onsite|on-site)\s+(?:preferred|only)\b", re.IGNORECASE)
_RELOCATION_RE = re.compile(
    r"(open to relocat\w+|willing to relocat\w+|not (?:open|willing) to relocat\w+|"
    r"no relocation)", re.IGNORECASE,
)

_ALL_SKILL_TERMS = sorted({term for terms in SKILLS_CATALOG.values() for term in terms}, key=len, reverse=True)

_STOPWORDS_BY_LANGUAGE: dict[str, set[str]] = {
    "en": {"the", "and", "of", "to", "in", "a", "for", "with", "on", "is", "at", "as"},
    "de": {"der", "die", "das", "und", "mit", "für", "von", "ein", "eine", "im", "auf", "ist"},
    "es": {"el", "la", "de", "y", "en", "un", "una", "con", "para", "los", "las", "por"},
    "fr": {"le", "la", "les", "de", "et", "un", "une", "des", "en", "pour", "avec", "dans"},
}


def _evidence(snippet: str, page: int | None, confidence: float) -> ExtractionEvidence:
    return ExtractionEvidence(source_page=page, source_text=snippet.strip()[:400], confidence=confidence)


def detect_cv_language(text: str) -> str:
    """Lightweight stopword-overlap heuristic across en/de/es/fr. Best-effort, no heavy deps."""
    normalized_words = re.findall(r"[a-zà-ÿ]+", text.lower())
    if not normalized_words:
        return "en"
    counts = {
        lang: sum(1 for word in normalized_words if word in stopwords)
        for lang, stopwords in _STOPWORDS_BY_LANGUAGE.items()
    }
    best = max(counts, key=lambda lang: counts[lang])
    return best if counts[best] > 0 else "en"


def _split_sections(text: str) -> tuple[str, dict[str, list[str]]]:
    """Returns (pre_header_block, {section_name: [line, ...]}). Header matching is
    multilingual and case-insensitive via SECTION_HEADERS."""
    header_by_line: dict[str, str] = {}
    for section, phrases in SECTION_HEADERS.items():
        for phrase in phrases:
            header_by_line[phrase] = section

    lines = text.splitlines()
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    pre_header: list[str] = []

    for line in lines:
        stripped = line.strip().strip(":").lower()
        matched_section = header_by_line.get(stripped)
        if matched_section is None and len(stripped) < 40:
            for phrase, section in header_by_line.items():
                if stripped == phrase:
                    matched_section = section
                    break
        if matched_section:
            current_section = matched_section
            sections.setdefault(current_section, [])
            continue
        if current_section is None:
            pre_header.append(line)
        else:
            sections[current_section].append(line)

    return "\n".join(pre_header), sections


def _extract_contact(pre_header: str, page: int | None, profile: CandidateProfile) -> None:
    emails = sorted(set(_EMAIL_RE.findall(pre_header) or _EMAIL_RE.findall(profile.original_text)))
    profile.emails = emails

    linkedin = _LINKEDIN_RE.findall(profile.original_text)
    github = _GITHUB_RE.findall(profile.original_text)
    urls = sorted(set(linkedin + github))
    profile.urls = urls

    phones = []
    for line in pre_header.splitlines():
        # Strip email/URL substrings first rather than skipping the whole line — contact lines
        # commonly pack "email | phone | linkedin" onto one line.
        scrubbed = _URL_RE.sub(" ", _EMAIL_RE.sub(" ", line))
        match = _PHONE_RE.search(scrubbed)
        if match and sum(character.isdigit() for character in match.group(0)) >= 7:
            phones.append(match.group(0).strip())
    profile.phones = sorted(set(phones))

    lines = [line.strip() for line in pre_header.splitlines() if line.strip()]
    name_line = next(
        (
            line for line in lines
            if not _EMAIL_RE.search(line) and not _PHONE_RE.search(line) and not _URL_RE.search(line)
            and len(line.split()) <= 5
        ),
        None,
    )
    if name_line:
        profile.full_name = name_line
        profile.field_evidence["full_name"] = _evidence(name_line, page, CONFIDENCE_EXPLICIT)

    headline_line = next(
        (line for line in lines[1:] if line != name_line and len(line.split()) <= 12), None
    )
    if headline_line:
        profile.headline = headline_line
        profile.field_evidence["headline"] = _evidence(headline_line, page, CONFIDENCE_WEAK)


def _extract_experience_entries(
    lines: list[str], page: int, as_of: date
) -> list[Experience]:
    entries: list[Experience] = []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)

    for block in blocks:
        # Title/company always come from the block's first line; the date range is searched
        # independently across the first few lines, since CVs commonly put "Title, Company" and
        # "Jan 2020 - Present" on separate lines — conflating them was a real bug (the date line
        # would get parsed as if it were the title line, discarding the actual title/company).
        title_line = block[0]
        start, end, is_current = None, None, False
        for candidate_line in block[:4]:
            candidate_start, candidate_end, candidate_is_current = parse_date_range(candidate_line, as_of=as_of)
            if candidate_start:
                start, end, is_current = candidate_start, candidate_end, candidate_is_current
                break

        parts = re.split(r"\s*(?:,|\||\bat\b|–|-)\s*", title_line, maxsplit=1)
        title = parts[0].strip() if parts else title_line.strip()
        title = _DATE_STRIP_RE.sub("", title).strip(" -–|,")
        company = parts[1].strip() if len(parts) > 1 else "Unknown"
        company = _DATE_STRIP_RE.sub("", company).strip(" -–|,")

        body_lines = [line for line in block if line is not title_line]
        responsibilities: list[str] = []
        achievements: list[Achievement] = []
        for line in body_lines:
            bullet_match = _BULLET_RE.match(line)
            content = bullet_match.group(1) if bullet_match else line.strip()
            if not content:
                continue
            metric_matches = list(_METRIC_RE.finditer(content))
            if metric_matches:
                for metric in metric_matches:
                    achievements.append(
                        Achievement(
                            text=content,
                            value=float(metric.group("value").replace(",", "")),
                            unit=metric.group("unit"),
                            context=content,
                        )
                    )
            elif bullet_match:
                responsibilities.append(content)

        entry_text = "\n".join(block)
        entry_normalized = normalize(entry_text)
        skills_used = sorted(
            {term for term in _ALL_SKILL_TERMS if contains_phrase(entry_normalized, term)}
        )
        industry_tags = sorted(
            tag for tag, phrases in DOMAIN_SIGNALS.items() if any(contains_phrase(entry_normalized, phrase) for phrase in phrases)
        )

        entries.append(
            Experience(
                title=title or "Unknown",
                normalized_title=normalize_title(title or "Unknown"),
                company=company or "Unknown",
                company_normalized=normalize_company(company or "Unknown"),
                start_date=start,
                end_date=end,
                is_current=is_current,
                duration_months=duration_months(start, end) if start and end else None,
                responsibilities=responsibilities,
                achievements=achievements,
                skills_used=[normalize_skill(term) for term in skills_used],
                industry=industry_tags[0] if industry_tags else None,
                domain=industry_tags[1] if len(industry_tags) > 1 else None,
                evidence=_evidence(entry_text, page, CONFIDENCE_EXPLICIT if start else CONFIDENCE_WEAK),
            )
        )

    return entries


_DATE_STRIP_RE = re.compile(
    # Bare 4-digit year, OR a month word actually followed by a year (so "Marketing"/"May" as
    # plain English words in a title aren't mistaken for "Mar"/"May" + trailing year).
    r"\b(?:\d{4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})\b",
    re.IGNORECASE,
)


def _extract_education_entries(lines: list[str], page: int) -> list[Education]:
    entries: list[Education] = []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)

    for block in blocks:
        block_text = "\n".join(block)
        lowered = block_text.lower()
        degree = next((keyword for keyword in _DEGREE_KEYWORDS if keyword in lowered), None)

        # A degree line often packs "Degree in Field, Institution" onto one line — split it
        # there first, so "field" doesn't swallow the institution name (and vice versa).
        degree_line = next((line for line in block if degree and degree in line.lower()), None)
        field: str | None = None
        institution: str | None = None
        if degree_line:
            combined_match = re.search(
                r"\bin\s+(?P<field>[A-Za-zÀ-ÿ &/-]{2,60}?)\s*,\s*(?P<institution>.+)$",
                degree_line,
                re.IGNORECASE,
            )
            if combined_match:
                field = combined_match.group("field").strip()
                institution = combined_match.group("institution").strip()

        if institution is None:
            institution = next(
                (
                    line.strip() for line in block
                    if line is not degree_line and any(keyword in line.lower() for keyword in _INSTITUTION_KEYWORDS)
                ),
                None,
            )
        if field is None:
            field_match = re.search(r"\bin\s+([A-Za-zÀ-ÿ &-]{3,60})", block_text)
            if field_match:
                field = field_match.group(1).strip()

        institution = institution or (block[0].strip() if block else "Unknown")
        start, end, _ = parse_date_range(block_text)
        gpa_match = _GPA_RE.search(block_text)

        entries.append(
            Education(
                institution=institution or "Unknown",
                degree=degree.title() if degree else None,
                field=field,
                start=start,
                end=end,
                grade=gpa_match.group(1) if gpa_match else None,
                evidence=_evidence(block_text, page, CONFIDENCE_EXPLICIT if degree else CONFIDENCE_WEAK),
            )
        )

    return entries


def _collect_skill_mentions(
    text: str, page: int, section_hint: bool
) -> dict[str, list[ExtractionEvidence]]:
    normalized_text = normalize(text)
    mentions: dict[str, list[ExtractionEvidence]] = {}
    for term in _ALL_SKILL_TERMS:
        if contains_phrase(normalized_text, term):
            snippet = _find_snippet(text, term) or term
            confidence = CONFIDENCE_EXPLICIT if section_hint else CONFIDENCE_INFERRED
            mentions.setdefault(normalize_skill(term), []).append(_evidence(snippet, page, confidence))
    return mentions


def _find_snippet(text: str, term: str) -> str | None:
    match = re.search(re.escape(term), text, re.IGNORECASE)
    if not match:
        return None
    start = max(0, match.start() - 30)
    end = min(len(text), match.end() + 30)
    return text[start:end].strip()


def _build_skills(
    skills_section_text: str,
    pages: list[str],
    experience: list[Experience],
    page: int,
) -> list[Skill]:
    merged: dict[str, list[ExtractionEvidence]] = {}
    for normalized_name, evidence in _collect_skill_mentions(skills_section_text, page, True).items():
        merged.setdefault(normalized_name, []).extend(evidence)
    # Whole-document scan runs per original page, so evidence carries the real page number
    # rather than a single default — this is the highest-volume provenance source. The skills
    # section text is excluded here so a skill listed only in that section doesn't get double
    # counted as "multiple evidence" against itself; a second evidence span should mean a real
    # second mention elsewhere (a bullet, a project), not the same substring scanned twice.
    for page_number, page_text in enumerate(pages, start=1):
        remaining_text = page_text.replace(skills_section_text, "") if skills_section_text else page_text
        for normalized_name, evidence in _collect_skill_mentions(remaining_text, page_number, False).items():
            merged.setdefault(normalized_name, []).extend(evidence)

    last_used_by_skill: dict[str, str] = {}
    months_by_skill: dict[str, int] = {}
    for entry in sorted(experience, key=lambda e: e.start_date or "", reverse=True):
        for used in entry.skills_used:
            if used not in last_used_by_skill:
                last_used_by_skill[used] = entry.end_date or ("current" if entry.is_current else entry.start_date or "")
            if entry.duration_months:
                months_by_skill[used] = months_by_skill.get(used, 0) + entry.duration_months

    skills: list[Skill] = []
    for normalized_name, evidence_list in merged.items():
        category = skill_category(normalized_name)
        skills.append(
            Skill(
                name=evidence_list[0].source_text if evidence_list else normalized_name,
                normalized_name=normalized_name,
                category=category,
                is_soft_skill=category in SOFT_SKILL_CATEGORIES,
                years_hint=round(months_by_skill[normalized_name] / 12) if normalized_name in months_by_skill else None,
                last_used_hint=last_used_by_skill.get(normalized_name),
                evidence=evidence_list,
            )
        )
    return skills


def _extract_certifications(text: str, page: int) -> list[Certification]:
    certifications: list[Certification] = []
    for line in text.splitlines():
        line_lower = line.lower()
        for acronym in _CERT_ACRONYMS:
            if acronym in line_lower:
                certifications.append(
                    Certification(
                        name=line.strip(),
                        evidence=_evidence(line, page, CONFIDENCE_EXPLICIT),
                    )
                )
                break
        else:
            match = _CERT_PATTERN_RE.search(line)
            if match:
                certifications.append(
                    Certification(
                        name=match.group(1).strip(),
                        evidence=_evidence(line, page, CONFIDENCE_INFERRED),
                    )
                )
    seen = set()
    unique = []
    for cert in certifications:
        key = cert.name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(cert)
    return unique


def _extract_languages(text: str, page: int) -> list[Language]:
    languages: list[Language] = []
    # CVs commonly list several languages on one comma-separated line
    # ("English (Native), German (Professional)") — split into segments so each gets its own
    # name+level pair instead of only the first language on the line being captured.
    for line in text.splitlines():
        for segment in re.split(r"[,;]", line):
            lowered = segment.lower()
            for name in _LANGUAGE_NAMES:
                if name in lowered:
                    level = "unspecified"
                    for level_key in sorted(LANGUAGE_LEVELS, key=len, reverse=True):
                        if level_key in lowered:
                            level = level_key.upper() if len(level_key) <= 2 else level_key
                            break
                    display_name = _LANGUAGE_DISPLAY.get(name, name.title())
                    languages.append(
                        Language(
                            language=display_name,
                            iso_code=_ISO_CODES.get(display_name.lower()),
                            level=level,
                            evidence=_evidence(
                                segment, page, CONFIDENCE_EXPLICIT if level != "unspecified" else CONFIDENCE_WEAK
                            ),
                        )
                    )
                    break
    seen = set()
    unique = []
    for language in languages:
        if language.language not in seen:
            seen.add(language.language)
            unique.append(language)
    return unique


def _extract_projects(lines_by_section: dict[str, list[str]], page: int) -> list[Project]:
    projects: list[Project] = []
    for kind in ("projects", "publications", "awards", "volunteering"):
        lines = lines_by_section.get(kind, [])
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if not line.strip():
                if current:
                    blocks.append(current)
                    current = []
                continue
            current.append(line)
        if current:
            blocks.append(current)

        for block in blocks:
            block_text = "\n".join(block)
            title = block[0].strip()
            start, end, _ = parse_date_range(block_text)
            normalized_text = normalize(block_text)
            skills = sorted(
                {normalize_skill(term) for term in _ALL_SKILL_TERMS if contains_phrase(normalized_text, term)}
            )
            links = _URL_RE.findall(block_text)
            projects.append(
                Project(
                    title=title,
                    start=start,
                    end=end,
                    description="\n".join(block[1:]) if len(block) > 1 else "",
                    skills=skills,
                    links=links,
                    kind="publication" if kind == "publications" else "award" if kind == "awards" else "volunteering" if kind == "volunteering" else "project",
                )
            )
    return projects


def _extract_companies(experience: list[Experience]) -> list[CompanyMention]:
    grouped: dict[str, list[Experience]] = {}
    for entry in experience:
        grouped.setdefault(entry.company_normalized, []).append(entry)

    companies: list[CompanyMention] = []
    for normalized_name, entries in grouped.items():
        raw_names = [entry.company for entry in entries]
        primary = max(set(raw_names), key=raw_names.count)
        aliases = sorted({name for name in raw_names if name != primary})
        industry = next((entry.industry for entry in entries if entry.industry), None)
        context = next((entry.responsibilities[0] for entry in entries if entry.responsibilities), None)
        companies.append(
            CompanyMention(
                name=primary,
                aliases=aliases,
                industry=industry,
                notable_context=context,
            )
        )
    return companies


def _extract_constraints(text: str) -> Constraints:
    values: dict[str, str] = {}
    for field, pattern in _CONSTRAINT_PATTERNS.items():
        match = pattern.search(text)
        if match:
            values[field] = match.group(0).strip()

    remote_match = _REMOTE_PREFERENCE_RE.search(text)
    remote_preference = remote_match.group(0).strip() if remote_match else None

    return Constraints(
        work_authorization=values.get("work_authorization"),
        notice_period=values.get("notice_period"),
        salary_expectation=values.get("salary_expectation"),
        remote_preference=remote_preference,
        travel=values.get("travel"),
        visa=values.get("visa"),
        availability=values.get("availability"),
    )


def _relocation_willingness(text: str) -> str | None:
    match = _RELOCATION_RE.search(text)
    if not match:
        return None
    return "no" if "not" in match.group(0).lower() or "no relocation" in match.group(0).lower() else "yes"


def extract(
    cv_text: str,
    pages: list[str] | None = None,
    *,
    profile_id: str,
    candidate_id: str,
    as_of: date | None = None,
) -> CandidateProfile:
    """Rule-based extraction, no external calls. `as_of` is threaded through for deterministic
    'Present'/duration handling in tests; defaults to today."""
    as_of = as_of or date.today()
    pages = pages or [cv_text]
    default_page = 1

    profile = CandidateProfile(
        profile_id=profile_id,
        candidate_id=candidate_id,
        original_text=cv_text,
        cleaned_text=re.sub(r"[ \t]+", " ", cv_text).strip(),
        detected_cv_language=detect_cv_language(cv_text),
    )

    pre_header, sections = _split_sections(profile.cleaned_text)
    _extract_contact(pre_header, default_page, profile)

    profile.experience = _extract_experience_entries(sections.get("experience", []), default_page, as_of)

    profile.education = _extract_education_entries(sections.get("education", []), default_page)

    skills_section_text = "\n".join(sections.get("skills", []))
    profile.skills = _build_skills(skills_section_text, pages, profile.experience, default_page)

    profile.certifications = _extract_certifications(
        "\n".join(sections.get("certifications", [])) or profile.cleaned_text, default_page
    )
    profile.languages = _extract_languages(
        "\n".join(sections.get("languages", [])) or profile.cleaned_text, default_page
    )
    profile.projects = _extract_projects(sections, default_page)
    profile.companies = _extract_companies(profile.experience)
    profile.constraints = _extract_constraints(profile.cleaned_text)
    profile.relocation_willingness = _relocation_willingness(profile.cleaned_text)

    all_titles = [entry.title for entry in profile.experience] or ([profile.headline] if profile.headline else [])
    years_total = years_of_experience_total(
        [(entry.start_date, entry.end_date) for entry in profile.experience], as_of=as_of
    )
    profile.years_of_experience_total = years_total if years_total > 0 else None
    if profile.years_of_experience_total is not None:
        profile.field_evidence["years_of_experience_total"] = _evidence(
            f"computed from {len(profile.experience)} experience entries", default_page, CONFIDENCE_EXPLICIT
        )

    seniority, inferred = infer_seniority(all_titles, profile.years_of_experience_total)
    profile.seniority_level = seniority
    profile.seniority_inferred = inferred
    if seniority:
        profile.field_evidence["seniority_level"] = _evidence(
            ", ".join(all_titles) or "years of experience", default_page,
            CONFIDENCE_INFERRED if inferred else CONFIDENCE_EXPLICIT,
        )

    normalized_full_text = normalize(profile.cleaned_text)
    profile.industries = sorted(
        tag for tag, phrases in DOMAIN_SIGNALS.items() if any(contains_phrase(normalized_full_text, phrase) for phrase in phrases)
    )
    profile.functions = sorted({entry.industry for entry in profile.experience if entry.industry})

    profile.career_timeline = [
        f"{entry.title} @ {entry.company} "
        f"({entry.start_date or '?'}–{'Present' if entry.is_current else (entry.end_date or '?')})"
        for entry in sorted(profile.experience, key=lambda e: e.start_date or "", reverse=True)
    ]

    all_confidences = [evidence.confidence for evidence in profile.field_evidence.values()]
    all_confidences += [evidence.confidence for skill in profile.skills for evidence in skill.evidence]
    all_confidences += [entry.evidence.confidence for entry in profile.experience]
    all_confidences += [entry.evidence.confidence for entry in profile.education]
    all_confidences += [entry.evidence.confidence for entry in profile.certifications]
    all_confidences += [entry.evidence.confidence for entry in profile.languages]
    profile.extraction_confidence = round(sum(all_confidences) / len(all_confidences), 2) if all_confidences else 0.0
    profile.extraction_source = "rules"

    logger.info(
        "extracted profile %s: confidence=%.2f source=%s skills=%d experience=%d education=%d",
        profile.profile_id, profile.extraction_confidence, profile.extraction_source,
        len(profile.skills), len(profile.experience), len(profile.education),
    )

    return profile
