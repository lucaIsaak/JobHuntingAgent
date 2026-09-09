"""Extraction entrypoint: always runs the rule-based extractor; optionally layers an LLM pass on
top when configured. Never raises — extraction failures degrade gracefully, they don't 500 the
upload endpoint.
"""

from __future__ import annotations

import logging
from datetime import date

from jobhunter.candidate import llm_extractor, rules_extractor
from jobhunter.candidate.schema import CandidateProfile

logger = logging.getLogger(__name__)


def extract(
    cv_text: str,
    pages: list[str] | None,
    *,
    profile_id: str,
    candidate_id: str,
    anthropic_api_key: str = "",
    as_of: date | None = None,
) -> CandidateProfile:
    """Rule-based extraction always runs. If `anthropic_api_key` is set, an LLM pass also runs
    and its fields win where present and schema-valid; rules fields fill any gaps. On any LLM
    failure, the rules-only profile is returned unchanged."""
    rules_profile = rules_extractor.extract(
        cv_text, pages, profile_id=profile_id, candidate_id=candidate_id, as_of=as_of
    )

    if not anthropic_api_key:
        return rules_profile

    llm_profile = llm_extractor.extract_with_llm(
        cv_text,
        api_key=anthropic_api_key,
        profile_id=profile_id,
        candidate_id=candidate_id,
        as_of=as_of,
    )
    if llm_profile is None:
        return rules_profile

    merged = _merge(rules_profile, llm_profile)
    logger.info(
        "extraction complete for %s: source=%s confidence=%.2f",
        profile_id, merged.extraction_source, merged.extraction_confidence,
    )
    return merged


def _merge(rules_profile: CandidateProfile, llm_profile: CandidateProfile) -> CandidateProfile:
    """LLM fields win where non-empty/non-null; rules fields fill any gap the LLM left."""
    merged = llm_profile.model_copy(deep=True)

    for field_name in CandidateProfile.model_fields:
        if field_name in {"profile_id", "candidate_id", "original_text", "cleaned_text", "extraction_source"}:
            continue
        llm_value = getattr(llm_profile, field_name)
        if llm_value in (None, "", [], {}):
            setattr(merged, field_name, getattr(rules_profile, field_name))

    merged.original_text = rules_profile.original_text
    merged.cleaned_text = rules_profile.cleaned_text
    merged.extraction_source = "rules+llm"
    confidences = [rules_profile.extraction_confidence, llm_profile.extraction_confidence]
    merged.extraction_confidence = round(sum(confidences) / len(confidences), 2)
    return merged
