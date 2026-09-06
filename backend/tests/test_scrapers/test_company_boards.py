from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.scrapers.company_boards import CompanyBoardScraper


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
    ).search_for_profile(
        CandidateProfile(
            profile_id="p1",
            raw_cv_text="consulting internship",
            industries=["consulting"],
        ),
        SearchCriteria(),
    )

    assert calls == [{"consulting-board"}, {"consulting-site"}]