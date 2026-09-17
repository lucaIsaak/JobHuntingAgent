"""Bundesagentur fuer Arbeit Jobsuche API adapter."""

from __future__ import annotations

import json
import base64
import logging
from collections.abc import Callable, Sequence
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.base import Scraper
from jobhunter.scrapers.catalog import build_search_query

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
DEFAULT_DETAILS_ENDPOINT = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails"
DEFAULT_CLIENT_ID = "jobboerse-jobsuche"
RESULTS_PER_PAGE = 100  # the API's own per-page maximum
MAX_PAGES = 5  # safety/politeness cap: at most 500 postings per search regardless of criteria.limit


class BundesagenturScraper(Scraper):
    """Fetch current German vacancies from the public v6 search endpoint.

    The search endpoint's own listing items never carry the full posting text — per the API's
    documented flow (github.com/bundesAPI/jobsuche-api), the description only lives behind the
    separate jobdetails endpoint, keyed by the search result's base64-encoded `referenznummer`.
    """

    sources = ("bundesagentur",)

    def __init__(
        self,
        client_id: str = DEFAULT_CLIENT_ID,
        endpoint: str = DEFAULT_ENDPOINT,
        details_endpoint: str = DEFAULT_DETAILS_ENDPOINT,
        fetch: Callable[..., object] = urlopen,
    ) -> None:
        self._client_id = client_id
        self._endpoint = (
            DEFAULT_ENDPOINT
            if not endpoint or "jobdetails" in endpoint
            else endpoint
        )
        self._details_endpoint = details_endpoint or DEFAULT_DETAILS_ENDPOINT
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        return self._search(criteria.role or " ".join(criteria.keywords), criteria)

    def search_for_profile(
        self, profile: CandidateProfile, criteria: SearchCriteria
    ) -> Sequence[JobPosting]:
        return self._search(build_search_query(profile, criteria), criteria)

    def _search(self, was: str, criteria: SearchCriteria) -> Sequence[JobPosting]:
        pages_needed = min(-(-criteria.limit // RESULTS_PER_PAGE), MAX_PAGES)  # ceil division
        jobs: list[JobPosting] = []
        for page in range(1, max(pages_needed, 1) + 1):
            page_jobs = self._search_page(was, criteria, page)
            jobs.extend(page_jobs)
            if len(page_jobs) < RESULTS_PER_PAGE:
                break  # short page means there's nothing more to fetch
        return jobs

    def _search_page(self, was: str, criteria: SearchCriteria, page: int) -> list[JobPosting]:
        params = {
            "was": was,
            "page": str(page),
            "size": str(RESULTS_PER_PAGE),
        }
        # The API 400s on an empty "wo" param — only send it when a location is actually given.
        if criteria.location:
            params["wo"] = criteria.location
        request = Request(
            f"{self._endpoint}?{urlencode(params)}",
            headers={
                "Accept": "application/json",
                "User-Agent": "JobHunter/0.1",
                "X-API-Key": self._client_id,
            },
        )
        try:
            with self._fetch(request, timeout=5) as response:
                payload = json.load(response)
        except (OSError, ValueError, TimeoutError) as exc:
            logger.warning("bundesagentur: search failed on page %s: %s", page, exc)
            return []

        jobs = []
        for item in payload.get("ergebnisliste", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            locations = item.get("stellenlokationen", [])
            location = "Unspecified"
            if locations and isinstance(locations[0], dict):
                address = locations[0].get("adresse", {})
                if isinstance(address, dict):
                    location = str(address.get("ort", "Unspecified"))
            title = str(item.get("stellenangebotsTitel", "")).strip()
            reference = str(item.get("referenznummer", "")).strip()
            encoded_reference = (
                quote(base64.b64encode(reference.encode()).decode()) if reference else ""
            )
            url = str(item.get("externeUrl") or "").strip()
            if not url and encoded_reference:
                url = (
                    "https://rest.arbeitsagentur.de/jobboerse/"
                    f"jobsuche-service/pc/v4/jobdetails/{encoded_reference}"
                )
            if not title or not url:
                continue
            description = str(item.get("stellenangebotsBeschreibung") or "").strip()
            if not description and encoded_reference:
                description = self._fetch_description(encoded_reference)
            jobs.append(JobPosting(
                source="bundesagentur",
                title=title,
                company=str(item.get("firma") or item.get("arbeitgeber") or "Unknown company"),
                location=location,
                is_remote=bool(
                    item.get("homeofficemoeglich")
                    or item.get("arbeitszeitHeimTelearbeit")
                ),
                employment_type=(
                    EmploymentType.INTERN
                    if str(item.get("stellenangebotsart", "")).upper() in {"PRAKTIKUM", "TRAINEE"}
                    else EmploymentType.FULL_TIME
                ),
                description=description,
                url=url,
            ))
        return jobs

    def _fetch_description(self, encoded_reference: str) -> str:
        """Look up the full posting text via the jobdetails endpoint.

        The search endpoint never returns it (see the class docstring), so this is a second
        request per posting keyed off the referenznummer already encoded for the fallback URL.
        Failures are swallowed and fall back to an empty description, same as a failed search
        page — a missing description shouldn't drop an otherwise valid posting.
        """
        request = Request(
            f"{self._details_endpoint}/{encoded_reference}",
            headers={
                "Accept": "application/json",
                "User-Agent": "JobHunter/0.1",
                "X-API-Key": self._client_id,
            },
        )
        try:
            with self._fetch(request, timeout=5) as response:
                payload = json.load(response)
        except (OSError, ValueError, TimeoutError) as exc:
            logger.warning("bundesagentur: jobdetails lookup failed: %s", exc)
            return ""
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("stellenangebotsBeschreibung") or payload.get("stellenbeschreibung") or "").strip()
