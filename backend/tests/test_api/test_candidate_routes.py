import sqlite3

from fastapi.testclient import TestClient

from jobhunter.api import candidate_routes, routes
from jobhunter.jobs.schema import Job, JobSkill
from jobhunter.main import app
from jobhunter.models.job import EmploymentType, JobPosting

client = TestClient(app)

_CV_TEXT = """Jane Doe
jane.doe@example.com

EXPERIENCE
Senior Data Analyst, Acme Analytics Inc.
Jan 2020 - Present
- Built Power BI dashboards used by 200 users

SKILLS
Python, SQL, Power BI

LANGUAGES
English (Native)
"""


def _seed_one_job() -> None:
    candidate_routes.jobs_repository.upsert_job(
        Job(
            job_id="api-test-job-1",
            title="Senior Data Analyst",
            normalized_title="Senior Data Analyst",
            company="Acme Analytics Inc.",
            industry="technology",
            function="analytics",
            location="Remote",
            remote_type="remote",
            employment_type="full_time",
            seniority="senior",
            description="Own analytics for the growth org.",
            skills=[JobSkill(name="Python", normalized_name="Python", is_must_have=True)],
        )
    )
    from jobhunter.matching.semantic import build_corpus_stats
    document_frequency, document_count = build_corpus_stats(candidate_routes.jobs_repository.all_job_texts())
    candidate_routes.jobs_repository.save_corpus_stats(document_frequency, document_count)


def test_upload_candidate_cv_returns_structured_profile():
    response = client.post(
        "/api/candidates/upload-file",
        files={"cv_file": ("cv.txt", _CV_TEXT.encode(), "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Jane Doe"
    assert any(skill["normalized_name"].lower() == "python" for skill in body["skills"])
    assert body["profile_id"]


def test_upload_candidate_cv_rejects_empty_file():
    response = client.post(
        "/api/candidates/upload-file",
        files={"cv_file": ("cv.txt", b"", "text/plain")},
    )
    assert response.status_code == 400


def test_get_candidate_profile_roundtrip():
    upload = client.post(
        "/api/candidates/upload-file",
        files={"cv_file": ("cv.txt", _CV_TEXT.encode(), "text/plain")},
    )
    profile_id = upload.json()["profile_id"]

    fetched = client.get(f"/api/candidates/{profile_id}")
    assert fetched.status_code == 200
    assert fetched.json()["profile_id"] == profile_id


def test_get_candidate_profile_missing_returns_404():
    response = client.get("/api/candidates/does-not-exist")
    assert response.status_code == 404


def test_update_candidate_profile_allows_correction():
    upload = client.post(
        "/api/candidates/upload-file",
        files={"cv_file": ("cv.txt", _CV_TEXT.encode(), "text/plain")},
    )
    profile = upload.json()
    profile["full_name"] = "Jane A. Doe"

    response = client.put(f"/api/candidates/{profile['profile_id']}", json=profile)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Jane A. Doe"

    refetched = client.get(f"/api/candidates/{profile['profile_id']}")
    assert refetched.json()["full_name"] == "Jane A. Doe"


def test_run_match_and_fetch_run():
    _seed_one_job()
    upload = client.post(
        "/api/candidates/upload-file",
        files={"cv_file": ("cv.txt", _CV_TEXT.encode(), "text/plain")},
    )
    profile_id = upload.json()["profile_id"]

    match_response = client.post(f"/api/candidates/{profile_id}/match", json={"top_k": 5})
    assert match_response.status_code == 200
    run = match_response.json()
    assert run["profile_id"] == profile_id
    assert run["results"]

    fetched_run = client.get(f"/api/match-runs/{run['run_id']}")
    assert fetched_run.status_code == 200
    assert fetched_run.json()["run_id"] == run["run_id"]


def test_match_missing_profile_returns_404():
    response = client.post("/api/candidates/does-not-exist/match", json={})
    assert response.status_code == 404


def test_list_jobs_returns_seeded_job():
    _seed_one_job()
    response = client.get("/api/jobs", params={"remote_type": "remote"})
    assert response.status_code == 200
    job_ids = {job["job_id"] for job in response.json()}
    assert "api-test-job-1" in job_ids


def _fake_fetch_postings(postings, source_counts):
    def fetch(profile, criteria):
        return postings, source_counts

    return fetch


def test_unified_search_without_profile_uses_keyword_ranking_and_stores_postings(monkeypatch):
    monkeypatch.setattr(
        routes.orchestrator,
        "fetch_postings",
        _fake_fetch_postings(
            [
                JobPosting(
                    source="stub",
                    title="Senior Data Analyst",
                    company="Acme",
                    location="Berlin",
                    employment_type=EmploymentType.FULL_TIME,
                    description="Analyze data for the growth team.",
                    url="https://example.com/jobs/unified-1",
                )
            ],
            {"stub": 1},
        ),
    )

    response = client.post(
        "/api/search",
        json={"role": "Senior Data Analyst", "sources": ["stub"], "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_profile"] is False
    assert body["source_status"] == [{"source": "stub", "status": "ok", "count": 1}]
    assert body["results"]
    assert body["results"][0]["overall_fit"] > 0
    assert body["results"][0]["subscores"] == {}

    # The posting from this request's fetch should now be in the jobs database, not just returned.
    from jobhunter.jobs.from_posting import _job_id_for_url

    job_id = _job_id_for_url("https://example.com/jobs/unified-1")
    assert candidate_routes.jobs_repository.get_job(job_id) is not None

    # The run and its raw postings should also be recorded for the discovered-jobs audit log.
    run_id = body["run_id"]
    stored_run = routes.repository.get_search_run(run_id)
    assert stored_run is not None
    assert stored_run.run_id == run_id

    with sqlite3.connect(routes.repository._database_path) as conn:
        discovered_count = conn.execute(
            "SELECT COUNT(*) FROM discovered_jobs WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
    assert discovered_count == 1


def test_unified_search_with_profile_uses_matching_engine(monkeypatch):
    monkeypatch.setattr(
        routes.orchestrator,
        "fetch_postings",
        _fake_fetch_postings(
            [
                JobPosting(
                    source="stub",
                    title="Senior Data Analyst",
                    company="Acme Analytics Inc.",
                    location="Remote",
                    is_remote=True,
                    employment_type=EmploymentType.FULL_TIME,
                    description="Own analytics for the growth org.",
                    url="https://example.com/jobs/unified-2",
                )
            ],
            {"stub": 1},
        ),
    )
    upload = client.post(
        "/api/candidates/upload-file",
        files={"cv_file": ("cv.txt", _CV_TEXT.encode(), "text/plain")},
    )
    profile_id = upload.json()["profile_id"]

    response = client.post(
        "/api/search",
        json={"candidate_profile_id": profile_id, "role": "Data Analyst", "sources": ["stub"], "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_profile"] is True
    assert body["results"]
    # subscores are only populated by the real matching engine, not the keyword-ranking fallback.
    assert body["results"][0]["subscores"]


def test_unified_search_missing_profile_returns_404(monkeypatch):
    monkeypatch.setattr(routes.orchestrator, "fetch_postings", _fake_fetch_postings([], {}))

    response = client.post(
        "/api/search",
        json={"candidate_profile_id": "does-not-exist", "role": "Engineer"},
    )

    assert response.status_code == 404
