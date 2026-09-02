from fastapi.testclient import TestClient

from jobhunter.main import app


client = TestClient(app)


def test_upload_and_search_flow():
    upload_payload = {
        "cv_text": "Python backend engineer with FastAPI and SQL experience in Berlin",
        "preferred_locations": ["Berlin"],
    }
    upload_response = client.post("/api/profiles/upload", json=upload_payload)
    assert upload_response.status_code == 200
    profile_id = upload_response.json()["profile_id"]

    search_payload = {
        "profile_id": profile_id,
        "criteria": {
            "role": "engineer",
            "location": "Berlin",
            "keywords": ["python", "fastapi"],
            "remote_only": True,
            "employment_types": ["full_time"],
            "limit": 10,
        },
    }

    search_response = client.post("/api/searches", json=search_payload)
    assert search_response.status_code == 200
    body = search_response.json()
    assert body["results"]
    assert body["results"][0]["job"]["source"] == "linkedin"

    get_response = client.get(f"/api/searches/{body['run_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["run_id"] == body["run_id"]


def test_search_missing_profile_returns_404():
    payload = {
        "profile_id": "does-not-exist",
        "criteria": {
            "keywords": [],
            "remote_only": False,
            "employment_types": [],
            "limit": 10,
        },
    }

    response = client.post("/api/searches", json=payload)
    assert response.status_code == 404
