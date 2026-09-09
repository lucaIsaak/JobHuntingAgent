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