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


def test_jooble_scraper_sends_query_under_keywords_field():
    # Jooble's API silently 400s on {"search": ...} — it requires {"keywords": ...} — verified
    # against the live endpoint. Regression test for that exact field name.
    captured_payloads = []

    def fake_fetch(request, timeout):
        captured_payloads.append(json.loads(request.data))
        return FakeResponse({"jobs": []})

    scraper = JoobleScraper("key", fetch=fake_fetch)
    scraper.search(SearchCriteria(role="Python"))

    assert len(captured_payloads) == 1
    assert captured_payloads[0]["keywords"] == "Python"
    assert "search" not in captured_payloads[0]