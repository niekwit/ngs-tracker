"""
Smoke test: create demo DB, start Flask, hit key endpoints, assert 200.
Cross-platform — works on Linux, macOS, and Windows.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).parent.parent
PORT = 5100  # avoid clashing with a running dev instance
BASE = f"http://127.0.0.1:{PORT}"

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


def wait_for_server(url: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    demo_db = REPO / "demo.db"
    demo_files = Path(tempfile.mkdtemp(prefix="ngs-tracker-ci-"))

    env = os.environ.copy()
    env["NGS_DB_PATH"] = str(demo_db)
    env["NGS_STORAGE_PATH"] = str(demo_files)
    env["NGS_PORT"] = str(PORT)
    env["NGS_HOST"] = "127.0.0.1"

    # ── Create demo database ──────────────────────────────────────────────────
    print("Creating demo database...")
    result = subprocess.run(
        [sys.executable, str(REPO / "create_demo_db.py"), "--out", str(demo_db)],
        env=env,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        print("ERROR: create_demo_db.py failed")
        return 1

    # ── Start Flask app ───────────────────────────────────────────────────────
    print(f"Starting app on port {PORT}...")
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "app.py")],
        env=env,
        cwd=str(REPO),
    )

    try:
        # ── Wait for server to be ready ───────────────────────────────────────
        if not wait_for_server(f"{BASE}/", timeout=30):
            print("ERROR: server did not respond within 30 s")
            return 1
        print("Server ready.\n")

        # ── Check each endpoint ───────────────────────────────────────────────
        failed = []
        for endpoint in ENDPOINTS:
            url = f"{BASE}{endpoint}"
            try:
                resp = urllib.request.urlopen(url, timeout=10)
                status = resp.status
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception as e:
                status = f"ERR ({e})"

            ok = status == 200
            marker = "OK  " if ok else "FAIL"
            print(f"  {marker}  {endpoint}  →  {status}")
            if not ok:
                failed.append((endpoint, status))

        print()
        if failed:
            print(f"FAILED: {len(failed)} endpoint(s) did not return 200:")
            for ep, st in failed:
                print(f"  {ep}  →  {st}")
            return 1

        print(f"All {len(ENDPOINTS)} endpoints returned 200. ✓")
        return 0

    finally:
        print("\nStopping server...")
        if sys.platform == "win32":
            proc.terminate()
        else:
            os.kill(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
