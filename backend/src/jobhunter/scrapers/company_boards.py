"""Public company career-board adapters for Greenhouse and Lever."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable, Sequence
from urllib.request import Request, urlopen

from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.base import Scraper


def _text(value: object) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", value).strip()


def _employment(value: object) -> EmploymentType:
    text = str(value or "").lower()
    if "intern" in text:
        return EmploymentType.INTERN
    if "part" in text:
        return EmploymentType.PART_TIME
    if "contract" in text or "freelance" in text:
        return EmploymentType.CONTRACT
    return EmploymentType.FULL_TIME


class GreenhouseScraper(Scraper):
    def __init__(self, boards: Sequence[str], fetch: Callable[..., object] = urlopen):
        self._boards = [board.strip() for board in boards if board.strip()]
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        postings = []
        for board in self._boards:
            request = Request(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
                headers={"Accept": "application/json", "User-Agent": "JobHunter/0.1"},
            )
            try:
                with self._fetch(request, timeout=5) as response:
                    payload = json.load(response)
            except (OSError, ValueError, TimeoutError):
                continue
            for item in payload.get("jobs", []) if isinstance(payload, dict) else []:
                location = item.get("location", {})
                postings.append(JobPosting(
                    source="greenhouse",
                    title=str(item.get("title", "")),
                    company=board,
                    location=str(location.get("name", "Unspecified")) if isinstance(location, dict) else "Unspecified",
                    description=_text(item.get("content", "")),
                    url=str(item.get("absolute_url", "")),
                ))
        return [job for job in postings if job.title and job.url]


class LeverScraper(Scraper):
    def __init__(self, sites: Sequence[str], fetch: Callable[..., object] = urlopen):
        self._sites = [site.strip() for site in sites if site.strip()]
        self._fetch = fetch

    def search(self, criteria: SearchCriteria) -> Sequence[JobPosting]:
        postings = []
        for site in self._sites:
            request = Request(
                f"https://api.lever.co/v0/postings/{site}?mode=json",
                headers={"Accept": "application/json", "User-Agent": "JobHunter/0.1"},
            )
            try:
                with self._fetch(request, timeout=5) as response:
                    payload = json.load(response)
            except (OSError, ValueError, TimeoutError):
                continue
            for item in payload if isinstance(payload, list) else []:
                categories = item.get("categories", {})
                postings.append(JobPosting(
                    source="lever",
                    title=str(item.get("text", "")),
                    company=site,
                    location=str(categories.get("location", "Unspecified")),
                    is_remote=str(item.get("workplaceType", "")).lower() == "remote",
                    employment_type=_employment(categories.get("commitment")),
                    description=_text(item.get("descriptionPlain", item.get("description", ""))),
                    url=str(item.get("hostedUrl", item.get("applyUrl", ""))),
                ))
        return [job for job in postings if job.title and job.url]


class CompanyBoardScraper:
    """Runs configured public company boards selected by candidate industries."""

    sources = ("greenhouse", "lever")

    def __init__(self, greenhouse: dict[str, list[str]], lever: dict[str, list[str]], fetch=urlopen):
        self._greenhouse = greenhouse
        self._lever = lever
        self._fetch = fetch

    def search_for_profile(self, profile: CandidateProfile, criteria: SearchCriteria) -> Sequence[JobPosting]:
        industries = set(profile.industries) or {"technology"}
        wanted_sources = set(criteria.sources) or set(self.sources)

        jobs: list[JobPosting] = []
        if "greenhouse" in wanted_sources:
            greenhouse = {board for industry in industries for board in self._greenhouse.get(industry, [])}
            jobs.extend(GreenhouseScraper(greenhouse, self._fetch).search(criteria))
        if "lever" in wanted_sources:
            lever = {site for industry in industries for site in self._lever.get(industry, [])}
            jobs.extend(LeverScraper(lever, self._fetch).search(criteria))
        return jobs
