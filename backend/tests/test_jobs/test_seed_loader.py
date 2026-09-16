import json
from pathlib import Path

import pytest

from jobhunter.jobs.seed_loader import load_jobs_from_json
from jobhunter.storage.jobs_repository import JobsRepository

SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "seed_jobs.json"


def test_load_seed_jobs_file_has_at_least_30_diverse_jobs():
    raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    assert len(raw) >= 30
    functions = {entry["function"] for entry in raw}
    assert len(functions) >= 5  # analytics, ML, marketing, software, business — spread required


def test_load_jobs_from_json_populates_repo_and_corpus_stats(tmp_path):
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    count = load_jobs_from_json(SEED_FILE, repo)
    assert count == repo.count()
    assert count >= 30

    document_frequency, document_count = repo.get_corpus_stats()
    assert document_count == count
    assert len(document_frequency) > 0


def test_load_jobs_from_json_rejects_non_list(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps({"not": "a list"}))
    repo = JobsRepository(database_path=str(tmp_path / "jobs.sqlite3"))
    with pytest.raises(ValueError):
        load_jobs_from_json(bad_file, repo)
