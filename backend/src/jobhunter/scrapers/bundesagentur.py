"""Bundesagentur fuer Arbeit Jobsuche API adapter."""

from __future__ import annotations

import json
import base64
from collections.abc import Callable, Sequence
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.base import Scraper

DEFAULT_ENDPOINT = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
DEFAULT_CLIENT_ID = "jobboerse-jobsuche"


class BundesagenturScraper(Scraper):
    """Fetch current German vacancies from the public v6 search endpoint."""

    sources = ("bundesagentur",)

    def __init__(
        self,
        client_id: str = DEFAULT_CLIENT_ID,
        endpoint: str = DEFAULT_ENDPOINT,
        fetch: Callable[..., object] = urlopen,
    ) -> None:
        self._client_id = client_id
        self._endpoint = (
            DEFAULT_ENDPOINT
            if not endpoint or "jobdetails" in endpoint
            else endpoint
        )
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        params = {
            "was": criteria.role or " ".join(criteria.keywords),
            "wo": criteria.location or "",
            "page": "1",
            "size": str(min(criteria.limit, 100)),
        }
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
        except (OSError, ValueError, TimeoutError):
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
            url = str(item.get("externeUrl") or "").strip()
            if not url and reference:
                encoded_reference = quote(
                    base64.b64encode(reference.encode()).decode()
                )
                url = (
                    "https://rest.arbeitsagentur.de/jobboerse/"
                    f"jobsuche-service/pc/v4/jobdetails/{encoded_reference}"
                )
            if not title or not url:
                continue
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
                description=str(item.get("stellenangebotsBeschreibung", "")),
                url=url,
            ))
        return jobs
