"""
Quick exploration script for the Greenhouse Job Board API.

Usage:
    python test_greenhouse_api.py <board_token> [--content] [--job-id ID]

Examples:
    python test_greenhouse_api.py stripe
    python test_greenhouse_api.py airbnb --content
    python test_greenhouse_api.py airbnb --job-id 1234567

Notes:
- board_token is the slug in a company's public careers URL, e.g. for
  https://boards.greenhouse.io/stripe the token is "stripe".
- No API key is required to read job listings.
- Passing --content fetches the full HTML job description for every job,
  which makes the request heavier but avoids a second call per job.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


def fetch_jobs(board_token: str, include_content: bool = False) -> dict:
    url = f"{BASE_URL}/{board_token}/jobs"
    params = {"content": "true"} if include_content else {}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_job(board_token: str, job_id: str) -> dict:
    url = f"{BASE_URL}/{board_token}/jobs/{job_id}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_departments(board_token: str) -> dict:
    url = f"{BASE_URL}/{board_token}/departments"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_offices(board_token: str) -> dict:
    url = f"{BASE_URL}/{board_token}/offices"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def summarize_jobs(payload: dict, limit: int = 5) -> None:
    jobs = payload.get("jobs", [])
    print(f"\nTotal jobs returned: {len(jobs)}")
    print(f"Showing first {min(limit, len(jobs))}:\n")
    for job in jobs[:limit]:
        location = job.get("location", {}).get("name", "N/A")
        print(f"- id={job.get('id')} | {job.get('title')} | {location}")
        print(f"    updated_at:      {job.get('updated_at')}")
        print(f"    first_published: {job.get('first_published')}")
        print(f"    apply_url:       {job.get('absolute_url')}")
        if "content" in job:
            snippet = job["content"][:120].replace("\n", " ")
            print(f"    content_snippet: {snippet}...")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore the Greenhouse Job Board API")
    parser.add_argument("board_token", help="Company's Greenhouse board token, e.g. 'stripe'")
    parser.add_argument("--content", action="store_true", help="Fetch full HTML job content inline")
    parser.add_argument("--job-id", help="Fetch a single job by its ID instead of the full list")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the raw JSON response to a file in ./output/",
    )
    args = parser.parse_args()

    try:
        if args.job_id:
            payload = fetch_job(args.board_token, args.job_id)
            print(json.dumps(payload, indent=2)[:2000])
        else:
            payload = fetch_jobs(args.board_token, include_content=args.content)
            summarize_jobs(payload)

            print("Departments:")
            depts = fetch_departments(args.board_token)
            for d in depts.get("departments", [])[:10]:
                print(f"  - {d.get('name')} (id={d.get('id')})")

            print("\nOffices:")
            offices = fetch_offices(args.board_token)
            for o in offices.get("offices", [])[:10]:
                print(f"  - {o.get('name')} (id={o.get('id')})")

        if args.save:
            out_dir = Path("output")
            out_dir.mkdir(exist_ok=True)
            out_file = out_dir / f"{args.board_token}_greenhouse.json"
            out_file.write_text(json.dumps(payload, indent=2))
            print(f"\nSaved raw response to {out_file}")

    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
