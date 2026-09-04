import io
import json

from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.arbeitnow import ArbeitnowScraper


class FakeResponse:
    def __init__(self, payload: dict):
        self._stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self._stream

    def __exit__(self, *args):
        self._stream.close()


def test_arbeitnow_scraper_normalizes_and_filters_jobs():
    payload = {
        "data": [
            {
                "title": "Senior Python Engineer",
                "company_name": "Real Company",
                "description": "<p>Build Python APIs.</p>",
                "remote": True,
                "job_types": ["Full Time"],
                "location": "Berlin",
                "url": "https://example.com/jobs/1",
            }
        ]
    }

    scraper = ArbeitnowScraper(fetch=lambda request, timeout: FakeResponse(payload))

    results = scraper.search(
        SearchCriteria(role="Python Engineer", location="Berlin", remote_only=True)
    )

    assert len(results) == 1
    assert results[0].source == "arbeitnow"
    assert results[0].description == "Build Python APIs."
    assert results[0].is_remote is True


def test_arbeitnow_scraper_fails_closed_on_provider_errors():
    scraper = ArbeitnowScraper(fetch=lambda request, timeout: (_ for _ in ()).throw(OSError()))

    assert scraper.search(SearchCriteria()) == []