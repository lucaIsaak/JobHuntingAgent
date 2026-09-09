"""Credentialed/configurable adapters for portals without one universal public API."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper


class ConfiguredJsonScraper(Scraper):
    """Adapter for a provider JSON endpoint configured by the operator."""

    def __init__(self, source: str, endpoint: str, token: str = "", fetch: Callable[..., object] = urlopen):
        self._source, self._endpoint, self._token, self._fetch = source, endpoint, token, fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        params = {"what": criteria.role or " ".join(criteria.keywords), "where": criteria.location or ""}
        separator = "&" if "?" in self._endpoint else "?"
        request = Request(self._endpoint + separator + urlencode(params), headers={"Accept": "application/json", "User-Agent": "JobHunter/0.1"})
        if self._token:
            request.add_header("Authorization", f"Bearer {self._token}")
        try:
            with self._fetch(request, timeout=5) as response:
                payload = json.load(response)
        except (OSError, ValueError, TimeoutError):
            return []
        items = payload.get("results", payload.get("jobs", payload.get("data", []))) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []
        jobs = []
        for item in items:
            if not isinstance(item, dict):
                continue
            jobs.append(JobPosting(
                source=self._source,
                title=str(item.get("title", item.get("name", ""))),
                company=str(item.get("company", item.get("company_name", "Unknown company"))),
                location=str(item.get("location", "Unspecified")),
                is_remote=bool(item.get("remote", False)),
                employment_type=EmploymentType.FULL_TIME,
                description=str(item.get("description", "")),
                url=str(item.get("url", item.get("redirect_url", ""))),
            ))
        return [job for job in jobs if job.title and job.url]
