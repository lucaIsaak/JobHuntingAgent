import io
import json

from jobhunter.models.job import EmploymentType
from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.adzuna import AdzunaScraper


class FakeResponse:
    def __init__(self, payload: dict):
        self._stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self._stream

    def __exit__(self, *args):
        self._stream.close()


def test_adzuna_scraper_normalizes_job_response():
    payload = {
        "results": [
            {
                "title": "Python API Engineer",
                "company": {"display_name": "Adzuna Company"},
                "location": {"display_name": "Berlin"},
                "description": "<p>Build Python services.</p>",
                "contract_type": "permanent",
                "redirect_url": "https://example.com/adzuna/1",
            }
        ]
    }
    scraper = AdzunaScraper(
        app_id="id",
        app_key="key",
        fetch=lambda request, timeout: FakeResponse(payload),
    )

    results = scraper.search(SearchCriteria(role="Python", location="Berlin"))

    assert len(results) == 1
    assert results[0].source == "adzuna"
    assert results[0].company == "Adzuna Company"
    assert results[0].employment_type == EmploymentType.FULL_TIME
    assert results[0].description == "Build Python services."


def _adzuna_page_payload(count: int, page: int) -> dict:
    return {
        "results": [
            {
                "title": f"Job {page}-{i}",
                "company": {"display_name": "Acme"},
                "location": {"display_name": "Berlin"},
                "description": "Build things.",
                "contract_type": "permanent",
                "redirect_url": f"https://example.com/adzuna/{page}/{i}",
            }
            for i in range(count)
        ]
    }


def test_adzuna_scraper_fetches_additional_pages_to_reach_the_limit():
    requested_pages = []

    def fake_fetch(request, timeout):
        page = int(request.full_url.rsplit("/search/", 1)[1].split("?")[0])
        requested_pages.append(page)
        # A full page (50) on page 1, a partial page on page 2 -- exactly reaching the limit.
        count = 50 if page == 1 else 10
        return FakeResponse(_adzuna_page_payload(count, page))

    scraper = AdzunaScraper(app_id="id", app_key="key", fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Engineer", limit=60))

    assert requested_pages == [1, 2]
    assert len(results) == 60


def test_adzuna_scraper_stops_early_on_a_short_page():
    requested_pages = []

    def fake_fetch(request, timeout):
        page = int(request.full_url.rsplit("/search/", 1)[1].split("?")[0])
        requested_pages.append(page)
        return FakeResponse(_adzuna_page_payload(5, page))  # short page, well under 50

    scraper = AdzunaScraper(app_id="id", app_key="key", fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Engineer", limit=200))

    assert requested_pages == [1]  # never asked for page 2 since page 1 was already short
    assert len(results) == 5


def test_adzuna_scraper_logs_and_fails_closed_on_provider_errors(caplog):
    scraper = AdzunaScraper(
        app_id="id", app_key="key", fetch=lambda request, timeout: (_ for _ in ()).throw(OSError("boom"))
    )

    with caplog.at_level("WARNING"):
        results = scraper.search(SearchCriteria(role="Engineer"))

    assert results == []
    assert "adzuna" in caplog.text
    assert "boom" in caplog.text