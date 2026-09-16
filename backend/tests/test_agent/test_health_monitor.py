import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import urlopen

import jobhunter.agent.health_monitor as health_monitor
import pytest
from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria


def _posting(source: str) -> JobPosting:
    return JobPosting(
        source=source,
        title="Software Engineer",
        company="Acme",
        location="Berlin",
        employment_type=EmploymentType.FULL_TIME,
        description="Build things.",
        url=f"https://example.com/{source}",
    )


class _StubScraper:
    """Mimics the real scrapers' `fetch`-injection seam without doing any network I/O."""

    def __init__(self, sources: tuple[str, ...], behavior: str, postings: list[JobPosting] | None = None):
        self.sources = sources
        self._fetch = urlopen
        self._behavior = behavior
        self._postings = postings or []

    def search(self, criteria: SearchCriteria):
        if self._behavior == "ok":
            return self._postings
        if self._behavior == "empty":
            return []
        # "error": actually call fetch (so the diagnostic wrapper captures the failure),
        # then swallow it, matching every real scraper's own except-block.
        try:
            self._fetch(object(), timeout=5)
        except Exception:
            pass
        return []


def test_diagnostic_fetch_captures_http_error(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise HTTPError(
            url="https://example.com",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b"bad request body"),
        )

    monkeypatch.setattr(health_monitor, "urlopen", fake_urlopen)
    diagnostic = health_monitor._DiagnosticFetch()

    with pytest.raises(HTTPError):
        diagnostic(request=None, timeout=5)

    assert diagnostic.http_status == 400
    assert "bad request body" in diagnostic.error


def test_check_all_sources_classifies_ok_error_and_no_results(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise HTTPError(
            url="https://example.com", code=500, msg="Server Error", hdrs=None, fp=io.BytesIO(b"boom")
        )

    monkeypatch.setattr(health_monitor, "urlopen", fake_urlopen)

    scrapers = [
        _StubScraper(("healthy",), "ok", [_posting("healthy")]),
        _StubScraper(("broken",), "error"),
        _StubScraper(("quiet",), "empty"),
    ]

    findings = {finding.source: finding for finding in health_monitor.check_all_sources(scrapers)}

    assert findings["healthy"].status == "ok"
    assert findings["healthy"].discovered_count == 1

    assert findings["broken"].status == "error"
    assert findings["broken"].http_status == 500
    assert "boom" in findings["broken"].error_detail

    assert findings["quiet"].status == "no_results"
    assert findings["quiet"].error_detail is None


def test_check_all_sources_attributes_multi_source_scraper_by_posting():
    scraper = _StubScraper(
        ("greenhouse", "lever"),
        "ok",
        [_posting("greenhouse"), _posting("greenhouse"), _posting("lever")],
    )

    findings = {finding.source: finding for finding in health_monitor.check_all_sources([scraper])}

    assert findings["greenhouse"].discovered_count == 2
    assert findings["lever"].discovered_count == 1


def test_run_check_only_diagnoses_error_sources(monkeypatch):
    diagnosed = []
    monkeypatch.setattr(health_monitor, "_diagnose_and_propose_fix", lambda finding: diagnosed.append(finding.source))

    saved = []

    class _FakeRepo:
        def save_source_health(self, finding):
            saved.append(finding.source)

    scrapers = [
        _StubScraper(("healthy",), "ok", [_posting("healthy")]),
        _StubScraper(("broken",), "error"),
    ]

    health_monitor.run_check(scrapers, _FakeRepo())

    assert diagnosed == ["broken"]
    assert sorted(saved) == ["broken", "healthy"]


def test_diagnose_and_propose_fix_noop_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(
        health_monitor, "settings", SimpleNamespace(anthropic_api_key="", health_check_model="claude-sonnet-5")
    )
    scraper_file = tmp_path / "jooble.py"
    scraper_file.write_text("original content")
    monkeypatch.setitem(health_monitor.SOURCE_FILE, "jooble", scraper_file)

    finding = health_monitor.SourceHealth(
        source="jooble", status="error", discovered_count=0, checked_at="now", error_detail="boom"
    )
    health_monitor._diagnose_and_propose_fix(finding)

    assert finding.diagnosis is None
    assert finding.proposed_fix_content is None


def test_diagnose_and_propose_fix_parses_llm_response(monkeypatch, tmp_path):
    scraper_file = tmp_path / "jooble.py"
    scraper_file.write_text("original content")
    monkeypatch.setitem(health_monitor.SOURCE_FILE, "jooble", scraper_file)
    monkeypatch.setattr(
        health_monitor, "settings", SimpleNamespace(anthropic_api_key="sk-test", health_check_model="claude-sonnet-5")
    )

    class _FakeTextBlock:
        type = "text"
        text = json.dumps({"diagnosis": "wrong field name", "fixed_file_content": "fixed content"})

    class _FakeResponse:
        content = [_FakeTextBlock()]

    class _FakeMessages:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeClient:
        def __init__(self, api_key=None):
            self.messages = _FakeMessages()

    monkeypatch.setattr(health_monitor, "Anthropic", _FakeClient)

    finding = health_monitor.SourceHealth(
        source="jooble", status="error", discovered_count=0, checked_at="now", error_detail="boom"
    )
    health_monitor._diagnose_and_propose_fix(finding)

    assert finding.diagnosis == "wrong field name"
    assert finding.proposed_fix_content == "fixed content"
    assert finding.fix_status == "proposed"
    assert finding.fix_file_path == str(scraper_file)


class _RealScraperStub:
    """Stands in for an already-configured real scraper instance in `routes.scrapers`."""

    def __init__(self, sources, **attrs):
        self.sources = sources
        self._fetch = urlopen
        for key, value in attrs.items():
            setattr(self, key, value)

    def search(self, criteria):
        return []


_WORKING_TRIAL_CODE = """
class TrialScraper:
    sources = ("testsource",)

    def search(self, criteria):
        class Posting:
            source = "testsource"
        return [Posting()]
"""

_FAILING_TRIAL_CODE = """
class TrialScraper:
    sources = ("testsource",)

    def search(self, criteria):
        try:
            self._fetch(object(), timeout=5)
        except Exception:
            pass
        return []
"""

_EMPTY_NO_ERROR_TRIAL_CODE = """
class TrialScraper:
    sources = ("testsource",)

    def search(self, criteria):
        return []
"""

_ATTRIBUTE_CHECKING_TRIAL_CODE = """
class TrialScraper:
    sources = ("testsource",)

    def search(self, criteria):
        class Posting:
            source = "testsource"
        return [Posting()] if self.api_key == "real-secret" else []
"""


def test_try_fix_reports_worked_when_trial_returns_results(monkeypatch):
    monkeypatch.setitem(health_monitor.SOURCE_CLASS, "testsource", "TrialScraper")
    real_scraper = _RealScraperStub(("testsource",))
    finding = health_monitor.SourceHealth(
        source="testsource",
        status="error",
        discovered_count=0,
        checked_at="now",
        proposed_fix_content=_WORKING_TRIAL_CODE,
        fix_file_path="/does/not/matter.py",
        fix_status="proposed",
    )

    try_status, try_detail = health_monitor.try_fix("testsource", finding, [real_scraper])

    assert try_status == "worked"
    assert "1 job" in try_detail


def test_try_fix_reports_failed_with_captured_error(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise HTTPError(url="https://example.com", code=500, msg="Server Error", hdrs=None, fp=io.BytesIO(b"still broken"))

    monkeypatch.setattr(health_monitor, "urlopen", fake_urlopen)
    monkeypatch.setitem(health_monitor.SOURCE_CLASS, "testsource", "TrialScraper")
    real_scraper = _RealScraperStub(("testsource",))
    finding = health_monitor.SourceHealth(
        source="testsource",
        status="error",
        discovered_count=0,
        checked_at="now",
        proposed_fix_content=_FAILING_TRIAL_CODE,
        fix_file_path="/does/not/matter.py",
        fix_status="proposed",
    )

    try_status, try_detail = health_monitor.try_fix("testsource", finding, [real_scraper])

    assert try_status == "failed"
    assert "still broken" in try_detail


def test_try_fix_reports_failed_when_inconclusive(monkeypatch):
    monkeypatch.setitem(health_monitor.SOURCE_CLASS, "testsource", "TrialScraper")
    real_scraper = _RealScraperStub(("testsource",))
    finding = health_monitor.SourceHealth(
        source="testsource",
        status="error",
        discovered_count=0,
        checked_at="now",
        proposed_fix_content=_EMPTY_NO_ERROR_TRIAL_CODE,
        fix_file_path="/does/not/matter.py",
        fix_status="proposed",
    )

    try_status, try_detail = health_monitor.try_fix("testsource", finding, [real_scraper])

    assert try_status == "failed"
    assert "inconclusive" in try_detail


def test_try_fix_carries_over_real_instance_attributes(monkeypatch):
    monkeypatch.setitem(health_monitor.SOURCE_CLASS, "testsource", "TrialScraper")
    real_scraper = _RealScraperStub(("testsource",), api_key="real-secret")
    finding = health_monitor.SourceHealth(
        source="testsource",
        status="error",
        discovered_count=0,
        checked_at="now",
        proposed_fix_content=_ATTRIBUTE_CHECKING_TRIAL_CODE,
        fix_file_path="/does/not/matter.py",
        fix_status="proposed",
    )

    try_status, _ = health_monitor.try_fix("testsource", finding, [real_scraper])

    assert try_status == "worked"


def test_try_fix_raises_without_proposed_content():
    finding = health_monitor.SourceHealth(source="testsource", status="error", discovered_count=0, checked_at="now")

    with pytest.raises(health_monitor.TryFixError):
        health_monitor.try_fix("testsource", finding, [])


def test_try_fix_raises_for_unknown_source():
    finding = health_monitor.SourceHealth(
        source="mystery",
        status="error",
        discovered_count=0,
        checked_at="now",
        proposed_fix_content="class Whatever: pass",
        fix_file_path="/x.py",
    )

    with pytest.raises(health_monitor.TryFixError):
        health_monitor.try_fix("mystery", finding, [])


def test_try_fix_raises_when_proposed_code_missing_expected_class(monkeypatch):
    monkeypatch.setitem(health_monitor.SOURCE_CLASS, "testsource", "TrialScraper")
    real_scraper = _RealScraperStub(("testsource",))
    finding = health_monitor.SourceHealth(
        source="testsource",
        status="error",
        discovered_count=0,
        checked_at="now",
        proposed_fix_content="class SomeOtherClass:\n    pass\n",
        fix_file_path="/does/not/matter.py",
        fix_status="proposed",
    )

    with pytest.raises(health_monitor.TryFixError):
        health_monitor.try_fix("testsource", finding, [real_scraper])
