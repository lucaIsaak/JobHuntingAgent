import io
import json

from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.jooble import JoobleScraper


class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.stream

    def __exit__(self, *args):
        self.stream.close()


def test_jooble_scraper_normalizes_jobs():
    scraper = JoobleScraper(
        "key",
        fetch=lambda request, timeout: FakeResponse({"jobs": [{
            "title": "Python Engineer",
            "company": "Example",
            "location": "Berlin",
            "snippet": "Build APIs",
            "link": "https://example.com/job",
        }]}),
    )

    results = scraper.search(SearchCriteria(role="Python"))

    assert len(results) == 1
    assert results[0].source == "jooble"
    assert results[0].company == "Example"