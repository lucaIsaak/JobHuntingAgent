import io
import json

from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.configured_api import ConfiguredJsonScraper


class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.stream

    def __exit__(self, *args):
        self.stream.close()


def test_configured_json_scraper_normalizes_jobs():
    scraper = ConfiguredJsonScraper(
        "eures",
        "https://example.com/api",
        fetch=lambda request, timeout: FakeResponse(
            {"jobs": [{"title": "Engineer", "company": "Example", "url": "https://example.com/job"}]}
        ),
    )

    results = scraper.search(SearchCriteria(role="Engineer"))

    assert len(results) == 1
    assert results[0].source == "eures"
    assert results[0].company == "Example"


def test_configured_json_scraper_logs_and_fails_closed_on_provider_errors(caplog):
    scraper = ConfiguredJsonScraper(
        "eures",
        "https://example.com/api",
        fetch=lambda request, timeout: (_ for _ in ()).throw(OSError("boom")),
    )

    with caplog.at_level("WARNING"):
        results = scraper.search(SearchCriteria(role="Engineer"))

    assert results == []
    assert "eures" in caplog.text
    assert "boom" in caplog.text
