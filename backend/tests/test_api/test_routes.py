from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from jobhunter.api import routes
from jobhunter.main import app


client = TestClient(app)


def test_real_public_api_sources_are_enabled_by_default():
    source_names = {source for scraper in routes.scrapers for source in getattr(scraper, "sources", ())}

    assert "arbeitnow" in source_names
    assert "bundesagentur" in source_names


def test_local_frontend_origin_on_alternate_port_is_allowed():
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:5174"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def _build_docx(content: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
</Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
  <w:body>
    <w:p><w:r><w:t>{content}</w:t></w:r></w:p>
  </w:body>
</w:document>""",
        )
    return buffer.getvalue()


def test_upload_file_and_search_flow():
    docx_bytes = _build_docx(
        "Senior Python backend engineer with 6 years of experience, FastAPI, SQL, Docker "
        "and Kubernetes, building fintech payments infrastructure in Berlin"
    )

    upload_response = client.post(
        "/api/profiles/upload-file",
        files={
            "cv_file": (
                "cv.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"preferred_locations": "Berlin"},
    )
    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    profile_id = upload_body["profile_id"]

    assert set(upload_body["skills"]) >= {"python", "fastapi", "sql", "docker", "kubernetes"}
    assert upload_body["seniority"] == "senior"
    assert upload_body["years_of_experience"] == 6
    assert "fintech" in upload_body["industries"]

    search_payload = {
        "profile_id": profile_id,
        "criteria": {
            "role": "engineer",
            "keywords": ["fastapi"],
            "remote_only": True,
            "employment_types": ["contract"],
            "limit": 10,
            "sources": ["glassdoor"],
        },
    }

    search_response = client.post("/api/searches", json=search_payload)
    assert search_response.status_code == 200
    body = search_response.json()
    assert body["results"]

    get_response = client.get(f"/api/searches/{body['run_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["run_id"] == body["run_id"]


def test_upload_file_rejects_unsupported_extension():
    upload_response = client.post(
        "/api/profiles/upload-file",
        files={"cv_file": ("cv.rtf", b"{\\rtf1 foo}", "application/rtf")},
    )

    assert upload_response.status_code == 400


def test_search_missing_profile_returns_404():
    payload = {
        "profile_id": "does-not-exist",
        "criteria": {
            "role": "Engineer",
            "keywords": [],
            "remote_only": False,
            "employment_types": [],
            "limit": 10,
        },
    }

    response = client.post("/api/searches", json=payload)
    assert response.status_code == 404


def test_search_without_profile_id_uses_role_only():
    response = client.post(
        "/api/searches",
        json={
            "criteria": {"role": "Engineer", "sources": ["glassdoor"], "limit": 20},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"]
    assert {result["job"]["source"] for result in body["results"]} == {"glassdoor"}


def test_search_requires_role():
    response = client.post(
        "/api/searches",
        json={"criteria": {"sources": ["glassdoor"], "limit": 20}},
    )

    assert response.status_code == 422


def test_search_can_limit_sources():
    upload_response = client.post(
        "/api/profiles/upload",
        json={"cv_text": "Python backend engineer with SQL experience."},
    )

    response = client.post(
        "/api/searches",
        json={
            "profile_id": upload_response.json()["profile_id"],
            "criteria": {"role": "Engineer", "sources": ["glassdoor"], "limit": 20},
        },
    )

    assert response.status_code == 200
    assert {result["job"]["source"] for result in response.json()["results"]} == {"glassdoor"}
