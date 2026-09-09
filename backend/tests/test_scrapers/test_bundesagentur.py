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