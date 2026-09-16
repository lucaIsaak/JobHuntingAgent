"""Background agent that checks each job source, diagnoses failures with an
LLM, and proposes a fix for a human to review and apply.

Every scraper already accepts a `fetch` callable in its constructor (used in
tests to inject a fake response). We reuse that same seam here: swap in an
instrumented fetch for the duration of one check, so we see the real
exception a scraper's own broad `except: return []` would otherwise swallow.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from anthropic import Anthropic

from jobhunter.config import settings
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.storage.repository import SourceHealth

logger = logging.getLogger(__name__)

SCRAPERS_DIR = Path(__file__).resolve().parents[1] / "scrapers"

SOURCE_FILE = {
    "arbeitnow": SCRAPERS_DIR / "arbeitnow.py",
    "adzuna": SCRAPERS_DIR / "adzuna.py",
    "jooble": SCRAPERS_DIR / "jooble.py",
    "bundesagentur": SCRAPERS_DIR / "bundesagentur.py",
    "greenhouse": SCRAPERS_DIR / "company_boards.py",
    "lever": SCRAPERS_DIR / "company_boards.py",
    "glassdoor": SCRAPERS_DIR / "glassdoor.py",
}

# The class in each file that actually implements the source, so a trial run
# can construct a fresh instance from proposed code without touching the real
# file. For the shared company_boards.py file, both sources are tried through
# the same CompanyBoardScraper wrapper.
SOURCE_CLASS = {
    "arbeitnow": "ArbeitnowScraper",
    "adzuna": "AdzunaScraper",
    "jooble": "JoobleScraper",
    "bundesagentur": "BundesagenturScraper",
    "greenhouse": "CompanyBoardScraper",
    "lever": "CompanyBoardScraper",
    "glassdoor": "GlassdoorScraper",
}

_CHECK_CRITERIA = SearchCriteria(role="Software Engineer", limit=10)
_CHECK_PROFILE = CandidateProfile(
    profile_id="health-check",
    raw_cv_text="Automated source health check.",
    industries=["technology"],
)


class _DiagnosticFetch:
    """Wraps urlopen so a scraper's own except-block still swallows the
    error normally, while we capture what actually happened on the side."""

    def __init__(self) -> None:
        self.error: str | None = None
        self.http_status: int | None = None

    def __call__(self, request, timeout=None):
        try:
            response = urlopen(request, timeout=timeout)
            self.http_status = getattr(response, "status", None)
            return response
        except HTTPError as exc:
            self.http_status = exc.code
            try:
                body = exc.read(500).decode(errors="replace")
            except Exception:
                body = ""
            self.error = f"HTTP {exc.code}: {body}"
            raise
        except URLError as exc:
            self.error = f"URLError: {exc.reason}"
            raise
        except Exception as exc:  # noqa: BLE001 - deliberately broad, this is diagnostic capture
            self.error = f"{type(exc).__name__}: {exc}"
            raise


def _checked_search(scraper) -> tuple[list, _DiagnosticFetch]:
    """Run one scraper's search with an instrumented fetch, then restore it."""
    diagnostic = _DiagnosticFetch()
    original_fetch = getattr(scraper, "_fetch", None)
    if original_fetch is not None:
        scraper._fetch = diagnostic
    try:
        if hasattr(scraper, "search_for_profile"):
            postings = list(scraper.search_for_profile(_CHECK_PROFILE, _CHECK_CRITERIA))
        else:
            postings = list(scraper.search(_CHECK_CRITERIA))
    finally:
        if original_fetch is not None:
            scraper._fetch = original_fetch
    return postings, diagnostic


def _classify(source: str, count: int, diagnostic: _DiagnosticFetch) -> SourceHealth:
    status = "ok" if count > 0 else ("error" if diagnostic.error else "no_results")
    return SourceHealth(
        source=source,
        status=status,
        discovered_count=count,
        checked_at=datetime.now(UTC).isoformat(),
        http_status=diagnostic.http_status,
        error_detail=diagnostic.error,
    )


def check_all_sources(scrapers) -> list[SourceHealth]:
    """Run a real search against every configured scraper and classify each source."""
    findings: list[SourceHealth] = []
    for scraper in scrapers:
        sources = getattr(scraper, "sources", ())
        if not sources:
            continue
        postings, diagnostic = _checked_search(scraper)
        if len(sources) == 1:
            findings.append(_classify(sources[0], len(postings), diagnostic))
            continue
        # A scraper covering multiple sources in one call (e.g. greenhouse+lever):
        # attribute counts by each posting's own source, best-effort share any
        # captured error across the sources that came back empty.
        counts = {source: 0 for source in sources}
        for posting in postings:
            if posting.source in counts:
                counts[posting.source] += 1
        for source in sources:
            findings.append(_classify(source, counts[source], diagnostic))
    return findings


def _diagnose_and_propose_fix(finding: SourceHealth) -> None:
    """Ask Claude to explain the failure and propose a corrected file. Mutates `finding` in place."""
    file_path = SOURCE_FILE.get(finding.source)
    if not file_path or not file_path.exists() or not settings.anthropic_api_key:
        return

    current_content = file_path.read_text()
    prompt = f"""A job-board scraper named "{finding.source}" is failing. Here is what a diagnostic run captured:

HTTP status: {finding.http_status}
Error: {finding.error_detail}

Here is the current content of the file that implements it ({file_path.name}):

```python
{current_content}
```

Diagnose the root cause and propose a minimal fix. Respond with ONLY a JSON object (no markdown fences, no other text) with exactly these two keys:
- "diagnosis": a short (1-3 sentence) plain-English explanation of the root cause
- "fixed_file_content": the complete corrected file content, ready to overwrite the file as-is

Keep the fix minimal and preserve the file's existing structure, style, and behavior for anything unrelated to the bug."""

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.health_check_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        finding.diagnosis = parsed.get("diagnosis")
        finding.proposed_fix_content = parsed.get("fixed_file_content")
        finding.fix_file_path = str(file_path)
        if finding.proposed_fix_content:
            finding.fix_status = "proposed"
    except Exception:
        logger.exception("health check: LLM diagnosis failed for source %s", finding.source)


def run_check(scrapers, repository) -> list[SourceHealth]:
    """Run one full check across all sources, diagnose failures, and persist results."""
    findings = check_all_sources(scrapers)
    for finding in findings:
        if finding.status == "error":
            _diagnose_and_propose_fix(finding)
        repository.save_source_health(finding)
    return findings


class TryFixError(Exception):
    """Raised when a proposed fix can't even be tried (not a failed trial — a setup problem)."""


def _load_module_from_source(code: str, module_label: str):
    """Exec proposed file content as an isolated module, never touching the real file on disk."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as handle:
        handle.write(code)
        temp_path = Path(handle.name)

    module_name = f"jobhunter._trial.{module_label}.{uuid.uuid4().hex}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, temp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        raise TryFixError(f"proposed code failed to load: {exc}") from exc
    finally:
        sys.modules.pop(module_name, None)
        temp_path.unlink(missing_ok=True)


def _find_real_scraper(source: str, scrapers):
    for scraper in scrapers:
        if source in getattr(scraper, "sources", ()):
            return scraper
    return None


def try_fix(source: str, finding: SourceHealth, scrapers) -> tuple[str, str]:
    """Load the proposed fix in isolation and run a real check against it,
    without writing to the real file or affecting the live running scrapers.

    Returns (try_status, try_detail); "worked" only when the trial produced
    real results with no captured error.
    """
    if not finding.proposed_fix_content or not finding.fix_file_path:
        raise TryFixError("no proposed fix to try")

    class_name = SOURCE_CLASS.get(source)
    real_scraper = _find_real_scraper(source, scrapers)
    if not class_name or real_scraper is None:
        raise TryFixError(f"don't know how to trial source '{source}'")

    module = _load_module_from_source(finding.proposed_fix_content, source)
    trial_class = getattr(module, class_name, None)
    if trial_class is None:
        raise TryFixError(f"proposed code has no {class_name} class")

    # Build a fresh instance of the *new* code, carrying over the real instance's
    # already-configured attributes (credentials, boards, etc.) instead of
    # re-deriving construction logic per scraper type.
    trial_instance = object.__new__(trial_class)
    trial_instance.__dict__.update(real_scraper.__dict__)

    postings, diagnostic = _checked_search(trial_instance)
    if len(getattr(real_scraper, "sources", (source,))) > 1:
        count = sum(1 for posting in postings if posting.source == source)
    else:
        count = len(postings)

    if count > 0:
        return "worked", f"{count} job{'s' if count != 1 else ''} found using the proposed fix."
    if diagnostic.error:
        return "failed", f"Still failing: {diagnostic.error}"
    return "failed", "Ran without error but returned no results — inconclusive."


async def run_loop(scrapers, repository, interval_seconds: int, initial_delay_seconds: int = 10) -> None:
    """Repeatedly run health checks in the background for as long as the app is up."""
    await asyncio.sleep(initial_delay_seconds)
    while True:
        try:
            await asyncio.to_thread(run_check, scrapers, repository)
            logger.info("source health check completed")
        except Exception:
            logger.exception("source health check loop failed")
        await asyncio.sleep(interval_seconds)
