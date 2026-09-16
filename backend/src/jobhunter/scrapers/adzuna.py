"""Adzuna job-search API adapter."""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Callable, Sequence
from json import load
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import build_search_query

logger = logging.getLogger(__name__)

ADZUNA_API_URL = "https://api.adzuna.com/v1/api"
RESULTS_PER_PAGE = 50  # Adzuna's own per-page maximum
MAX_PAGES = 5  # safety/politeness cap: at most 250 postings per search regardless of criteria.limit


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

    sources = ("adzuna",)

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
        return self._search(criteria.role or " ".join(criteria.keywords), criteria)

    def search_for_profile(
        self, profile: CandidateProfile, criteria: SearchCriteria
    ) -> Sequence[JobPosting]:
        return self._search(build_search_query(profile, criteria), criteria)

    def _search(self, what: str, criteria: SearchCriteria) -> Sequence[JobPosting]:
        pages_needed = min(-(-criteria.limit // RESULTS_PER_PAGE), MAX_PAGES)  # ceil division
        postings: list[JobPosting] = []
        for page in range(1, max(pages_needed, 1) + 1):
            page_postings = self._search_page(what, criteria, page)
            postings.extend(page_postings)
            if len(page_postings) < RESULTS_PER_PAGE:
                break  # short page means there's nothing more to fetch
        return postings

    def _search_page(self, what: str, criteria: SearchCriteria, page: int) -> list[JobPosting]:
        query = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "results_per_page": RESULTS_PER_PAGE,
            "what": what,
        }
        if criteria.location:
            query["where"] = criteria.location

        request = Request(
            f"{self._endpoint}/jobs/{self._country}/search/{page}?{urlencode(query)}",
            headers={"Accept": "application/json", "User-Agent": "JobHunter/0.1"},
        )
        try:
            with self._fetch(request, timeout=self._timeout) as response:
                payload = load(response)
        except (OSError, ValueError, TimeoutError) as exc:
            logger.warning("adzuna: search failed on page %s: %s", page, exc)
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
        return postings