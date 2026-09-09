"""Optional Claude-based extraction layer. Fully isolated: importing this module never requires
the `anthropic` package to be installed, and calling it never raises out — any failure (missing
package, missing key, network error, malformed/invalid JSON) is caught and logged, and the caller
falls back to the rules-only profile. Nothing in the app depends on this module working.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from jobhunter.candidate.schema import CandidateProfile

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT = """You are a precise CV/resume information extractor. You will be given raw CV \
text and a JSON schema. Extract every field the schema defines that is actually supported by the \
CV text.

Rules:
- Do NOT fabricate employers, degrees, skills, dates, or any other fact not present in the text.
- Fill every array field exhaustively — list every role, every skill, every education entry, \
every language, every certification, every project you can find. Do not stop after the first few.
- For every extracted item, copy the source snippet verbatim into its evidence field, and give a \
confidence between 0 and 1 (1.0 = explicitly stated, lower = inferred or ambiguous).
- If a field is not present in the CV, omit it or leave it null/empty — never guess a plausible \
value.
- Return JSON only. No prose, no markdown fences, no commentary — a single JSON object matching \
the schema."""


def _schema_prompt() -> str:
    schema = CandidateProfile.model_json_schema()
    return (
        "Extract a CandidateProfile matching exactly this JSON schema "
        "(profile_id/candidate_id will be overwritten by the caller, use placeholder \"\" for "
        "them):\n\n" + json.dumps(schema)
    )


def extract_with_llm(
    cv_text: str,
    *,
    api_key: str,
    profile_id: str,
    candidate_id: str,
    as_of: date | None = None,
) -> CandidateProfile | None:
    """Returns a validated CandidateProfile, or None on any failure (never raises)."""
    try:
        import anthropic
    except ImportError:
        logger.info("anthropic package not installed; skipping LLM extraction")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"{_schema_prompt()}\n\nCV TEXT:\n{cv_text}",
                }
            ],
        )
        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        payload = json.loads(raw_text)
        payload["profile_id"] = profile_id
        payload["candidate_id"] = candidate_id
        payload.setdefault("original_text", cv_text)
        payload.setdefault("cleaned_text", cv_text)
        payload["extraction_source"] = "rules+llm"
        return CandidateProfile.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - any failure here must fall back, never propagate
        logger.warning("LLM extraction failed, falling back to rules-only: %s", exc)
        return None
