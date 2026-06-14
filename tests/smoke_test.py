"""
Smoke test: create demo DB, start Flask, hit key endpoints, assert 200.
Cross-platform — works on Linux, macOS, and Windows.
"""

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
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


def find_free_port() -> int:
    """Ask the OS for an available port so we never collide with existing services."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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
    port = find_free_port()
    base = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["NGS_DB_PATH"] = str(demo_db)
    env["NGS_STORAGE_PATH"] = str(demo_files)
    env["NGS_PORT"] = str(port)
    env["NGS_HOST"] = "127.0.0.1"
    env["PYTHONUTF8"] = "1"

    # ── Create demo database ──────────────────────────────────────────────────
    print("Creating demo database...")
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, str(REPO / "create_demo_db.py"), "--out", str(demo_db)],
        env=env,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        print("ERROR: create_demo_db.py failed")
        return 1

    # ── Start Flask app ───────────────────────────────────────────────────────
    print(f"Starting app on port {port}...")
    sys.stdout.flush()

    flask_stderr = tempfile.TemporaryFile()
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "app.py")],
        env=env,
        cwd=str(REPO),
        stderr=flask_stderr,
    )

    try:
        # ── Wait for server to be ready ───────────────────────────────────────
        if not wait_for_server(f"{base}/", timeout=30):
            exit_code = proc.poll()
            flask_stderr.seek(0)
            err = flask_stderr.read().decode("utf-8", errors="replace").strip()
            if exit_code is not None:
                print(f"ERROR: Flask exited with code {exit_code} before responding")
            else:
                print("ERROR: Flask is running but did not respond within 30 s")
            if err:
                print("--- Flask stderr ---")
                print(err)
                print("-------------------")
            return 1

        print("Server ready.\n")
        sys.stdout.flush()

        # ── Check each endpoint ───────────────────────────────────────────────
        failed = []
        for endpoint in ENDPOINTS:
            url = f"{base}{endpoint}"
            try:
                resp = urllib.request.urlopen(url, timeout=10)
                status = resp.status
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception as e:
                status = f"ERR ({e})"

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

    finally:
        print("\nStopping server...")
        sys.stdout.flush()
        if sys.platform == "win32":
            proc.terminate()
        else:
            os.kill(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        flask_stderr.close()


if __name__ == "__main__":
    sys.exit(main())
