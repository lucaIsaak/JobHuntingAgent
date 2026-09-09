"""Anthropic client is mocked throughout — these tests never hit the network and never require a
real ANTHROPIC_API_KEY, so they run the same in CI as locally.
"""

import sys
import types
from unittest.mock import MagicMock

from jobhunter.candidate import llm_extractor


def _install_fake_anthropic(monkeypatch, response_text: str):
    fake_module = types.ModuleType("anthropic")

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = response_text

    response = MagicMock()
    response.content = [text_block]

    client = MagicMock()
    client.messages.create.return_value = response

    fake_module.Anthropic = MagicMock(return_value=client)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return client


def test_extract_with_llm_returns_none_without_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    result = llm_extractor.extract_with_llm(
        "some cv text", api_key="key", profile_id="p1", candidate_id="c1"
    )
    assert result is None


def test_extract_with_llm_parses_valid_response(monkeypatch):
    payload = (
        '{"full_name": "Jane Doe", "emails": ["jane@example.com"], "skills": [], '
        '"experience": [], "education": [], "languages": [], "certifications": [], '
        '"companies": [], "projects": []}'
    )
    _install_fake_anthropic(monkeypatch, payload)

    profile = llm_extractor.extract_with_llm(
        "cv text here", api_key="key", profile_id="p1", candidate_id="c1"
    )

    assert profile is not None
    assert profile.full_name == "Jane Doe"
    assert profile.profile_id == "p1"
    assert profile.candidate_id == "c1"
    assert profile.extraction_source == "rules+llm"


def test_extract_with_llm_falls_back_on_malformed_json(monkeypatch):
    _install_fake_anthropic(monkeypatch, "not valid json { at all")

    result = llm_extractor.extract_with_llm(
        "cv text here", api_key="key", profile_id="p1", candidate_id="c1"
    )
    assert result is None


def test_extract_with_llm_falls_back_on_schema_violation(monkeypatch):
    # emails must be a list of strings — this response violates the schema.
    _install_fake_anthropic(monkeypatch, '{"emails": "not-a-list"}')

    result = llm_extractor.extract_with_llm(
        "cv text here", api_key="key", profile_id="p1", candidate_id="c1"
    )
    assert result is None


def test_extract_with_llm_falls_back_on_client_exception(monkeypatch):
    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = MagicMock(side_effect=RuntimeError("network down"))
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    result = llm_extractor.extract_with_llm(
        "cv text here", api_key="key", profile_id="p1", candidate_id="c1"
    )
    assert result is None
