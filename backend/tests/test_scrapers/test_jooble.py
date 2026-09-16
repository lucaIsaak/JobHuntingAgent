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


def _jooble_page_payload(count: int, page: int) -> dict:
    return {
        "jobs": [
            {
                "title": f"Job {page}-{i}",
                "company": "Example",
                "location": "Berlin",
                "snippet": "Build APIs",
                "link": f"https://example.com/job/{page}/{i}",
            }
            for i in range(count)
        ]
    }


def test_jooble_scraper_fetches_additional_pages_to_reach_the_limit():
    requested_pages = []

    def fake_fetch(request, timeout):
        page = json.loads(request.data)["page"]
        requested_pages.append(page)
        count = 20 if page == 1 else 5
        return FakeResponse(_jooble_page_payload(count, page))

    scraper = JoobleScraper("key", fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Python", limit=25))

    assert requested_pages == [1, 2]
    assert len(results) == 25


def test_jooble_scraper_stops_early_on_a_short_page():
    requested_pages = []

    def fake_fetch(request, timeout):
        requested_pages.append(json.loads(request.data)["page"])
        return FakeResponse(_jooble_page_payload(3, 1))  # short page, well under 20

    scraper = JoobleScraper("key", fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Python", limit=100))

    assert requested_pages == [1]
    assert len(results) == 3


def test_jooble_scraper_logs_and_fails_closed_on_provider_errors(caplog):
    scraper = JoobleScraper("key", fetch=lambda request, timeout: (_ for _ in ()).throw(OSError("boom")))

    with caplog.at_level("WARNING"):
        results = scraper.search(SearchCriteria(role="Engineer"))

    assert results == []
    assert "jooble" in caplog.text
    assert "boom" in caplog.text


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
