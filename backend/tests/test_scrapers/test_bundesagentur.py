import io
import json

from jobhunter.models.search_criteria import SearchCriteria
from jobhunter.scrapers.bundesagentur import BundesagenturScraper


class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self.stream

    def __exit__(self, *args):
        self.stream.close()


def test_bundesagentur_scraper_normalizes_v6_jobs():
    scraper = BundesagenturScraper(
        fetch=lambda request, timeout: FakeResponse({"ergebnisliste": [{
            "stellenangebotsTitel": "Software Engineer",
            "arbeitgeber": "Example GmbH",
            "referenznummer": "10001-123-S",
            "externeUrl": "https://example.com/job",
            "stellenlokationen": [{"adresse": {"ort": "Berlin"}}],
            "arbeitszeitHeimTelearbeit": True,
        }]}),
    )

    results = scraper.search(SearchCriteria(role="Software Engineer", location="Berlin"))

    assert len(results) == 1
    assert results[0].source == "bundesagentur"
    assert results[0].company == "Example GmbH"
    assert results[0].is_remote is True


def _bundesagentur_page_payload(count: int, page: int) -> dict:
    return {
        "ergebnisliste": [
            {
                "stellenangebotsTitel": f"Job {page}-{i}",
                "arbeitgeber": "Example GmbH",
                "referenznummer": f"1000{page}-{i}-S",
                "externeUrl": f"https://example.com/job/{page}/{i}",
                "stellenlokationen": [{"adresse": {"ort": "Berlin"}}],
            }
            for i in range(count)
        ]
    }


def test_bundesagentur_scraper_fetches_additional_pages_to_reach_the_limit():
    requested = []

    def fake_fetch(request, timeout):
        if "/jobdetails/" in request.full_url:
            return FakeResponse({"stellenangebotsBeschreibung": ""})
        query = dict(pair.split("=") for pair in request.full_url.split("?", 1)[1].split("&"))
        page = int(query["page"])
        requested.append(page)
        count = 100 if page == 1 else 30
        return FakeResponse(_bundesagentur_page_payload(count, page))

    scraper = BundesagenturScraper(fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Software Engineer", limit=130))

    assert requested == [1, 2]
    assert len(results) == 130


def test_bundesagentur_scraper_stops_early_on_a_short_page():
    requested = []

    def fake_fetch(request, timeout):
        if "/jobdetails/" in request.full_url:
            return FakeResponse({"stellenangebotsBeschreibung": ""})
        query = dict(pair.split("=") for pair in request.full_url.split("?", 1)[1].split("&"))
        requested.append(int(query["page"]))
        return FakeResponse(_bundesagentur_page_payload(5, 1))  # short page, well under 100

    scraper = BundesagenturScraper(fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Software Engineer", limit=200))

    assert requested == [1]
    assert len(results) == 5


def test_bundesagentur_scraper_fetches_description_via_jobdetails_when_missing_from_search():
    detail_requests = []

    def fake_fetch(request, timeout):
        if "/jobdetails/" in request.full_url:
            detail_requests.append(request.full_url)
            return FakeResponse({"stellenangebotsBeschreibung": "Full posting text."})
        return FakeResponse({"ergebnisliste": [{
            "stellenangebotsTitel": "Software Engineer",
            "arbeitgeber": "Example GmbH",
            "referenznummer": "10001-123-S",
            "externeUrl": "https://example.com/job",
            "stellenlokationen": [{"adresse": {"ort": "Berlin"}}],
        }]})

    scraper = BundesagenturScraper(fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Software Engineer"))

    assert len(detail_requests) == 1
    assert "jobdetails" in detail_requests[0]
    assert results[0].description == "Full posting text."


def test_bundesagentur_scraper_leaves_description_empty_when_jobdetails_lookup_fails():
    def fake_fetch(request, timeout):
        if "/jobdetails/" in request.full_url:
            raise OSError("boom")
        return FakeResponse({"ergebnisliste": [{
            "stellenangebotsTitel": "Software Engineer",
            "arbeitgeber": "Example GmbH",
            "referenznummer": "10001-123-S",
            "externeUrl": "https://example.com/job",
            "stellenlokationen": [{"adresse": {"ort": "Berlin"}}],
        }]})

    scraper = BundesagenturScraper(fetch=fake_fetch)

    results = scraper.search(SearchCriteria(role="Software Engineer"))

    assert len(results) == 1
    assert results[0].description == ""


def test_bundesagentur_scraper_logs_and_fails_closed_on_provider_errors(caplog):
    scraper = BundesagenturScraper(fetch=lambda request, timeout: (_ for _ in ()).throw(OSError("boom")))

    with caplog.at_level("WARNING"):
        results = scraper.search(SearchCriteria(role="Engineer"))

    assert results == []
    assert "bundesagentur" in caplog.text
    assert "boom" in caplog.text


def test_bundesagentur_scraper_omits_empty_location_param():
    # The live API returns HTTP 400 when "wo" is present but empty — verified against the real
    # endpoint. criteria.location=None must not send "wo=" at all, only omit the param.
    captured_urls = []

    def fake_fetch(request, timeout):
        captured_urls.append(request.full_url)
        return FakeResponse({"ergebnisliste": []})

    scraper = BundesagenturScraper(fetch=fake_fetch)
    scraper.search(SearchCriteria(role="Software Engineer"))

    assert len(captured_urls) == 1
    assert "wo=" not in captured_urls[0]
