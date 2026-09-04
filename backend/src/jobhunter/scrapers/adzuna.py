"""Adzuna job-search API adapter."""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Sequence
from json import load
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import filter_postings

ADZUNA_API_URL = "https://api.adzuna.com/v1/api"


def _plain_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _employment_type(value: object) -> EmploymentType:
    contract = str(value or "").lower()
    if "part" in contract:
        return EmploymentType.PART_TIME
    if "contract" in contract or "freelance" in contract:
        return EmploymentType.CONTRACT
    return EmploymentType.FULL_TIME


class AdzunaScraper(Scraper):
    """Fetch current jobs from Adzuna's documented search API."""

    def __init__(
        self,
        app_id: str,
        app_key: str,
        country: str = "de",
        endpoint: str = ADZUNA_API_URL,
        timeout: float = 5.0,
        fetch: Callable[..., object] = urlopen,
    ) -> None:
        self._app_id = app_id
        self._app_key = app_key
        self._country = country
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        query = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "results_per_page": min(criteria.limit, 50),
            "what": criteria.role or " ".join(criteria.keywords),
        }
        if criteria.location:
            query["where"] = criteria.location

        request = Request(
            f"{self._endpoint}/jobs/{self._country}/search/1?{urlencode(query)}",
            headers={"Accept": "application/json", "User-Agent": "JobHunter/0.1"},
        )
        try:
            with self._fetch(request, timeout=self._timeout) as response:
                payload = load(response)
        except (OSError, ValueError, TimeoutError):
            return []

        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            return []

        postings: list[JobPosting] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            url = str(item.get("redirect_url", "")).strip()
            company = item.get("company", {})
            location = item.get("location", {})
            if not title or not url:
                continue
            postings.append(
                JobPosting(
                    source="adzuna",
                    title=title,
                    company=str(company.get("display_name", "Unknown company"))
                    if isinstance(company, dict)
                    else "Unknown company",
                    location=str(location.get("display_name", "Unspecified"))
                    if isinstance(location, dict)
                    else "Unspecified",
                    is_remote="remote" in f"{title} {item.get('description', '')}".lower(),
                    employment_type=_employment_type(item.get("contract_type")),
                    description=_plain_text(str(item.get("description", ""))),
                    url=url,
                )
            )
        return filter_postings(postings, criteria)