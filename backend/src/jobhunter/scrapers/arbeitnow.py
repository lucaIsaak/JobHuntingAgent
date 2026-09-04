"""Arbeitnow job-board API adapter."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


def _plain_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _employment_type(job_types: list[str]) -> EmploymentType:
    value = " ".join(job_types).lower()
    if "intern" in value:
        return EmploymentType.INTERN
    if "part" in value:
        return EmploymentType.PART_TIME
    if "contract" in value or "freelance" in value:
        return EmploymentType.CONTRACT
    return EmploymentType.FULL_TIME


def _to_posting(item: dict[str, object]) -> JobPosting | None:
    title = str(item.get("title", "")).strip()
    url = str(item.get("url", "")).strip()
    if not title or not url:
        return None

    job_types = item.get("job_types", [])
    if not isinstance(job_types, list):
        job_types = []

    return JobPosting(
        source="arbeitnow",
        title=title,
        company=str(item.get("company_name", "Unknown company")).strip(),
        location=str(item.get("location", "Unspecified")).strip(),
        is_remote=bool(item.get("remote", False)),
        employment_type=_employment_type([str(value) for value in job_types]),
        description=_plain_text(str(item.get("description", ""))),
        url=url,
    )


class ArbeitnowScraper(Scraper):
    """Fetches current jobs from Arbeitnow's public API."""

    def __init__(
        self,
        endpoint: str = ARBEITNOW_URL,
        timeout: float = 5.0,
        fetch: Callable[..., object] = urlopen,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        request = Request(
            self._endpoint,
            headers={"Accept": "application/json", "User-Agent": "JobHunter/0.1"},
        )
        try:
            with self._fetch(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except (OSError, URLError, ValueError, TimeoutError):
            return []

        items = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return []

        postings = [
            posting
            for item in items
            if isinstance(item, dict)
            for posting in [_to_posting(item)]
            if posting is not None
        ]
        return filter_postings(postings, criteria)
