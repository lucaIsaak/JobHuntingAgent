from jobhunter.models.job import EmploymentType, JobPosting
from jobhunter.models.search_criteria import CandidateProfile, SearchCriteria
from jobhunter.services.dedup import deduplicate_postings
from jobhunter.services.matcher import rank_jobs


def test_deduplicate_postings_removes_duplicates():
    posting = JobPosting(
        source="a",
        title="Python Developer",
        company="Acme",
        location="Berlin",
        is_remote=True,
        employment_type=EmploymentType.FULL_TIME,
        description="Python FastAPI",
        url="https://example.com/1",
    )
    duplicate = posting.model_copy(update={"source": "b", "url": "https://example.com/2"})

    unique = deduplicate_postings([posting, duplicate])

    assert len(unique) == 1
    assert unique[0].url == "https://example.com/1"


def test_rank_jobs_orders_by_score():
    profile = CandidateProfile(
        profile_id="p1",
        raw_cv_text="Python FastAPI SQL",
        skills=["python", "fastapi", "sql"],
        titles=["engineer"],
        preferred_locations=["berlin"],
    )
    criteria = SearchCriteria(role="engineer", keywords=["python"], remote_only=True)
    best = JobPosting(
        source="linkedin",
        title="Python Backend Engineer",
        company="Acme",
        location="Berlin",
        is_remote=True,
        employment_type=EmploymentType.FULL_TIME,
        description="Python FastAPI",
        url="https://example.com/1",
    )
    weaker = best.model_copy(
        update={
            "title": "Operations Specialist",
            "description": "Office operations",
            "is_remote": False,
            "url": "https://example.com/2",
        }
    )

    ranked = rank_jobs(profile, criteria, [weaker, best])

    assert ranked[0].job.url == "https://example.com/1"
    assert ranked[0].score > ranked[1].score
