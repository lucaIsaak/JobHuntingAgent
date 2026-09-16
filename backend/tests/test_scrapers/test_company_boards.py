from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.company_boards import CompanyBoardScraper, GreenhouseScraper, LeverScraper


def test_company_boards_use_candidate_industry(monkeypatch):
    calls = []

    class EmptyScraper:
        def __init__(self, boards, fetch):
            calls.append(set(boards))

        def search(self, criteria):
            return []

    monkeypatch.setattr("jobhunter.scrapers.company_boards.GreenhouseScraper", EmptyScraper)
    monkeypatch.setattr("jobhunter.scrapers.company_boards.LeverScraper", EmptyScraper)

    CompanyBoardScraper(
        {"consulting": ["consulting-board"]},
        {"consulting": ["consulting-site"]},
        catalog=(),  # isolate from the real built-in catalog, which may itself contribute
        # real "consulting"-tagged boards — this test only checks that the configured
        # per-industry boards get used, not what the catalog happens to contain.
    ).search_for_profile(
        CandidateProfile(
            profile_id="p1",
            raw_cv_text="consulting internship",
            industries=["consulting"],
        ),
        SearchCriteria(role="Consultant"),
    )

    assert calls == [{"consulting-board"}, {"consulting-site"}]


def test_greenhouse_scraper_logs_and_skips_board_on_provider_errors(caplog):
    scraper = GreenhouseScraper(
        ["broken-board"], fetch=lambda request, timeout: (_ for _ in ()).throw(OSError("boom"))
    )

    with caplog.at_level("WARNING"):
        results = scraper.search(SearchCriteria(role="Engineer"))

    assert results == []
    assert "greenhouse" in caplog.text
    assert "broken-board" in caplog.text
    assert "boom" in caplog.text


def test_lever_scraper_logs_and_skips_site_on_provider_errors(caplog):
    scraper = LeverScraper(["broken-site"], fetch=lambda request, timeout: (_ for _ in ()).throw(OSError("boom")))

    with caplog.at_level("WARNING"):
        results = scraper.search(SearchCriteria(role="Engineer"))

    assert results == []
    assert "lever" in caplog.text
    assert "broken-site" in caplog.text
    assert "boom" in caplog.text