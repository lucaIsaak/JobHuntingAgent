"""Jooble job-search API adapter."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper


class JoobleScraper(Scraper):
    sources = ("jooble",)

    def __init__(self, api_key: str, endpoint: str = "https://jooble.org/api", fetch: Callable[..., object] = urlopen):
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        if not self._endpoint.startswith(("http://", "https://")):
            self._endpoint = f"https://{self._endpoint}"
        if self._endpoint == "https://jooble.org":
            self._endpoint += "/api"
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        payload = json.dumps({
            "search": criteria.role or " ".join(criteria.keywords),
            "location": criteria.location or "",
            "page": 1,
        }).encode()
        request = Request(
            f"{self._endpoint}/{self._api_key}",
            data=payload,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "JobHunter/0.1"},
        )
        try:
            with self._fetch(request, timeout=5) as response:
                result = json.load(response)
        except (OSError, ValueError, TimeoutError):
            return []

        jobs = []
        for item in result.get("jobs", []) if isinstance(result, dict) else []:
            if not isinstance(item, dict):
                continue
            jobs.append(JobPosting(
                source="jooble",
                title=str(item.get("title", "")),
                company=str(item.get("company", "Unknown company")),
                location=str(item.get("location", "Unspecified")),
                employment_type=EmploymentType.FULL_TIME,
                description=str(item.get("snippet", "")),
                url=str(item.get("link", "")),
            ))
        return [job for job in jobs if job.title and job.url]