#!/usr/bin/env python3
"""Load jobs from a JSON file into the jobs database.

Usage (from backend/):
    python scripts/load_jobs.py data/seed_jobs.json
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobhunter.config import settings  # noqa: E402
from jobhunter.jobs.seed_loader import load_jobs_from_json  # noqa: E402
from jobhunter.storage.jobs_repository import JobsRepository  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if len(sys.argv) != 2:
        print("usage: python scripts/load_jobs.py <path-to-jobs.json>", file=sys.stderr)
        raise SystemExit(1)

    repo = JobsRepository(database_path=settings.database_path)
    count = load_jobs_from_json(sys.argv[1], repo)
    print(f"loaded {count} jobs into {settings.database_path}")


if __name__ == "__main__":
    main()
