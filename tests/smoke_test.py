"""
Smoke test: create demo DB, then use Flask's test client to check key endpoints.
No networking required — avoids platform-specific port-binding issues on macOS.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent

# Standard UI pages
UI_ENDPOINTS = [
    "/",
    "/runs",
    "/runs?page=1",
    "/runs/1",
    "/runs/2",
    "/groups",
    "/researchers",
    "/projects",
    "/projects/1",
    "/workflows",
    "/log",
]


def main() -> int:
    demo_db = REPO / "demo.db"
    demo_files = Path(tempfile.mkdtemp(prefix="ngs-tracker-ci-"))

    # Set env vars before importing app — config.py reads them at import time
    os.environ["NGS_DB_PATH"] = str(demo_db)
    os.environ["NGS_STORAGE_PATH"] = str(demo_files)

    # Run create_demo_db.py as a subprocess so its SQLAlchemy state
    # doesn't collide with the one we're about to import
    print("Creating demo database...")
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, str(REPO / "create_demo_db.py"), "--out", str(demo_db)],
        cwd=str(REPO),
    )
    if result.returncode != 0:
        print("ERROR: create_demo_db.py failed")
        return 1

    # Import app after env vars are set so create_app() picks up the demo DB path
    sys.path.insert(0, str(REPO))
    import app as flask_app
    from config import get_api_key

    client = flask_app.app.test_client()
    api_key = get_api_key()

    failed = []

    # ── UI endpoints ──────────────────────────────────────────────────────────
    print("UI endpoint checks...\n")
    sys.stdout.flush()
    for endpoint in UI_ENDPOINTS:
        resp = client.get(endpoint, follow_redirects=True)
        status = resp.status_code
        ok = status == 200
        print(f"  {'OK  ' if ok else 'FAIL'}  {endpoint}  ->  {status}")
        if not ok:
            failed.append((endpoint, status))

    # ── API endpoints ─────────────────────────────────────────────────────────
    print("\nAPI endpoint checks...\n")
    sys.stdout.flush()

    # Health — no auth required
    resp = client.get("/api/health")
    ok = resp.status_code == 200
    print(f"  {'OK  ' if ok else 'FAIL'}  GET /api/health  ->  {resp.status_code}")
    if not ok:
        failed.append(("/api/health", resp.status_code))

    # Unauthenticated request should be 401
    resp = client.get("/api/runs")
    ok = resp.status_code == 401
    print(
        f"  {'OK  ' if ok else 'FAIL'}  GET /api/runs (no key)  ->  {resp.status_code} (expect 401)"
    )
    if not ok:
        failed.append(("/api/runs [no-auth]", resp.status_code))

    headers = {"X-Api-Key": api_key}

    # Authenticated list endpoints
    for endpoint in ["/api/runs", "/api/projects", "/api/researchers"]:
        resp = client.get(endpoint, headers=headers)
        ok = resp.status_code == 200
        data = resp.get_json()
        count = len(data) if isinstance(data, list) else "?"
        print(
            f"  {'OK  ' if ok else 'FAIL'}  GET {endpoint}  ->  {resp.status_code} ({count} items)"
        )
        if not ok:
            failed.append((endpoint, resp.status_code))

    # Single run
    resp = client.get("/api/runs/1", headers=headers)
    ok = resp.status_code == 200
    print(f"  {'OK  ' if ok else 'FAIL'}  GET /api/runs/1  ->  {resp.status_code}")
    if not ok:
        failed.append(("/api/runs/1", resp.status_code))

    # Create a run via API
    payload = {
        "project_id": 1,
        "workflow_name": "test-pipeline",
        "workflow_tag": "v1.0.0",
        "workflow_system": "snakemake",
        "status": "completed",
        "description": "Created by smoke test",
        "tags": ["test"],
    }
    resp = client.post(
        "/api/runs",
        data=json.dumps(payload),
        content_type="application/json",
        headers=headers,
    )
    ok = resp.status_code == 201
    new_id = resp.get_json().get("id") if ok else None
    print(
        f"  {'OK  ' if ok else 'FAIL'}  POST /api/runs  ->  {resp.status_code} (id={new_id})"
    )
    if not ok:
        failed.append(("/api/runs [POST]", resp.status_code))

    # Update the run's status via PATCH
    if new_id:
        resp = client.patch(
            f"/api/runs/{new_id}",
            data=json.dumps({"status": "failed", "notes": "smoke test patch"}),
            content_type="application/json",
            headers=headers,
        )
        ok = resp.status_code == 200 and resp.get_json().get("status") == "failed"
        print(
            f"  {'OK  ' if ok else 'FAIL'}  PATCH /api/runs/{new_id}  ->  {resp.status_code}"
        )
        if not ok:
            failed.append((f"/api/runs/{new_id} [PATCH]", resp.status_code))

    # Attach a file to the run via API
    if new_id:
        tmp_file = demo_files / "smoke_test_output.txt"
        tmp_file.write_text("smoke test file content")
        resp = client.post(
            f"/api/runs/{new_id}/files",
            data=json.dumps(
                {
                    "file_path": str(tmp_file),
                    "file_type": "results",
                    "description": "smoke test attachment",
                }
            ),
            content_type="application/json",
            headers=headers,
        )
        ok = resp.status_code == 201
        print(
            f"  {'OK  ' if ok else 'FAIL'}  POST /api/runs/{new_id}/files  ->  {resp.status_code}"
        )
        if not ok:
            failed.append((f"/api/runs/{new_id}/files [POST]", resp.status_code))

    print()
    if failed:
        print(f"FAILED: {len(failed)} check(s):")
        for ep, st in failed:
            print(f"  {ep}  ->  {st}")
        return 1

    total = len(UI_ENDPOINTS) + 8  # UI + API checks
    print(f"All {total} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
