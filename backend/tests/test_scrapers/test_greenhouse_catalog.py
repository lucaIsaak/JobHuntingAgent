from jobhunter.models.search_criteria import CandidateProfile
from jobhunter.scrapers.greenhouse_catalog import score_company, select_top_companies

_PROFILE = CandidateProfile(profile_id="p1", raw_cv_text="")


def test_select_top_companies_prefers_ai_ml_tagged_boards():
    profile = _PROFILE.model_copy(update={"industries": ["ai_ml"]})

    boards = select_top_companies(profile, top_n=5)

    assert boards
    assert {"anthropic", "openai", "perplexity", "huggingface", "replit"} & set(boards)
    assert "brex" not in boards


def test_select_top_companies_prefers_fintech_tagged_boards():
    profile = _PROFILE.model_copy(update={"industries": ["fintech"]})

    boards = select_top_companies(profile, top_n=5)

    assert "stripe" in boards
    assert "anthropic" not in boards


def test_select_top_companies_falls_back_to_technology_when_no_domain_signal():
    profile = _PROFILE.model_copy(update={"industries": []})

    boards = select_top_companies(profile, top_n=3)

    assert len(boards) == 3


def test_score_company_is_proportional_overlap():
    from jobhunter.scrapers.greenhouse_catalog import GREENHOUSE_COMPANIES

    stripe = next(c for c in GREENHOUSE_COMPANIES if c.board_token == "stripe")

    full_match = _PROFILE.model_copy(update={"industries": ["fintech", "developer_tools", "technology"]})
    partial_match = _PROFILE.model_copy(update={"industries": ["fintech"]})
    no_match = _PROFILE.model_copy(update={"industries": ["hr_tech"]})

    assert score_company(full_match, stripe) == 1.0
    assert score_company(partial_match, stripe) == 1 / 3
    assert score_company(no_match, stripe) == 0.0
