"""
Smoke test: create demo DB, then use Flask's test client to check key endpoints.
No networking required — avoids platform-specific port-binding issues on macOS.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent

ENDPOINTS = [
    "/",
    "/runs",
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

    client = flask_app.app.test_client()

    print("Running endpoint checks...\n")
    sys.stdout.flush()

    failed = []
    for endpoint in ENDPOINTS:
        resp = client.get(endpoint, follow_redirects=True)
        status = resp.status_code
        ok = status == 200
        marker = "OK  " if ok else "FAIL"
        print(f"  {marker}  {endpoint}  ->  {status}")
        if not ok:
            failed.append((endpoint, status))

    print()
    if failed:
        print(f"FAILED: {len(failed)} endpoint(s) did not return 200:")
        for ep, st in failed:
            print(f"  {ep}  ->  {st}")
        return 1

    print(f"All {len(ENDPOINTS)} endpoints returned 200.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
