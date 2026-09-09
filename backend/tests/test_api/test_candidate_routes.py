from fastapi.testclient import TestClient

from jobhunter.api import candidate_routes
from jobhunter.jobs.schema import Job, JobSkill
from jobhunter.main import app

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
