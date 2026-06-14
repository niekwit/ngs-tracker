"""
NGS Tracker client — lightweight helper for registering Snakemake / Nextflow
workflow runs via the NGS Tracker REST API.

Typical usage in a Snakefile
-----------------------------
    import os

    onsuccess:
        from ngs_tracker import register_run
        register_run(config)

    onerror:
        from ngs_tracker import register_run
        register_run(config, status="failed")

The function reads all settings from config["ngs_tracker"] and does nothing
when config["ngs_tracker"]["enabled"] is False or absent.

API key
-------
Set the NGS_TRACKER_KEY environment variable, or add api_key: "..." to the
ngs_tracker block in your config YAML.  The environment variable takes
precedence.

The current user is read from NGS_TRACKER_USER (env var) or
config["ngs_tracker"]["created_by"].
"""

import os
import sys
from pathlib import Path

try:
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None


DEFAULT_BASE_URL = "http://127.0.0.1:5000/api"
VALID_STATUSES = {"completed", "running", "pending", "failed"}
VALID_FILE_TYPES = {"config", "sample_info", "qc", "results", "mapping_rates", "other"}


def register_run(config: dict, status: str = "completed") -> int | None:
    """
    Register a workflow run in NGS Tracker.

    Parameters
    ----------
    config:
        Snakemake config dict.  Must contain an ``ngs_tracker`` key whose
        value is a dict (see below).
    status:
        Run status — one of ``completed``, ``failed``, ``running``,
        ``pending``.  Defaults to ``completed``.

    Returns
    -------
    The new run ID on success, or ``None`` if registration was skipped or
    failed.

    Config keys (config["ngs_tracker"])
    ------------------------------------
    enabled (bool, required):
        Set to ``true`` to activate; ``false`` silently skips everything.
    project_id (int, required):
        NGS Tracker project ID.  Visible on the project detail page.
    base_url (str, optional):
        API base URL.  Defaults to ``http://127.0.0.1:5000/api``.
    api_key (str, optional):
        API key.  Prefer the ``NGS_TRACKER_KEY`` environment variable.
    workflow_name (str, optional):
        Name of the workflow as registered in NGS Tracker.
    workflow_tag (str, optional):
        Release tag, e.g. ``v2.1.0``.
    workflow_system (str, optional):
        One of ``snakemake``, ``nextflow``, ``cwl``, ``other``.
        Defaults to ``snakemake``.
    description (str, optional):
        Short free-text description of this run.
    tags (list[str], optional):
        Tag labels.
    notes (str, optional):
        Long-form Markdown notes stored on the run.
    created_by (str, optional):
        Username.  Prefer the ``NGS_TRACKER_USER`` environment variable.
    files (list[dict], optional):
        Files to attach.  Each entry has:
          path (str):        Path to the file (absolute or relative to CWD).
          type (str):        File type — config / sample_info / qc / results /
                             mapping_rates / other.
          description (str): Optional label shown in the UI.
    """
    cfg = config.get("ngs_tracker", {})
    if not cfg.get("enabled", False):
        return None

    if _requests is None:
        _warn("'requests' is not installed — run: pip install requests")
        return None

    if status not in VALID_STATUSES:
        _warn(f"Invalid status '{status}'. Using 'completed'.")
        status = "completed"

    base = cfg.get("base_url", DEFAULT_BASE_URL).rstrip("/")
    key = os.environ.get("NGS_TRACKER_KEY") or cfg.get("api_key", "")
    if not key:
        _warn("No API key found. Set the NGS_TRACKER_KEY environment variable.")
        return None

    project_id = cfg.get("project_id")
    if not project_id:
        _warn("'project_id' is required in config['ngs_tracker'].")
        return None

    headers = {"X-Api-Key": key}

    try:
        # ── Create the run ────────────────────────────────────────────────────
        payload = {
            "project_id": int(project_id),
            "workflow_name": cfg.get("workflow_name", ""),
            "workflow_tag": cfg.get("workflow_tag", ""),
            "workflow_system": cfg.get("workflow_system", "snakemake"),
            "status": status,
            "description": cfg.get("description", ""),
            "tags": cfg.get("tags", []),
            "notes": cfg.get("notes", ""),
            "created_by": os.environ.get("NGS_TRACKER_USER", "")
            or cfg.get("created_by", ""),
        }

        resp = _requests.post(f"{base}/runs", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        run_id = resp.json()["id"]
        _info(f"Run {run_id} registered (status={status}) — {base}/runs/{run_id}")

        # ── Attach files ──────────────────────────────────────────────────────
        for entry in cfg.get("files", []):
            raw_path = entry.get("path", "")
            if not raw_path:
                continue

            path = Path(raw_path)
            if not path.is_absolute():
                path = Path.cwd() / path
            path = path.resolve()

            if not path.exists():
                _warn(f"File not found, skipping: {path}")
                continue

            file_type = entry.get("type", "other")
            if file_type not in VALID_FILE_TYPES:
                _warn(
                    f"Unknown file type '{file_type}' for {path.name},"
                    f" using 'other'. Valid types: {sorted(VALID_FILE_TYPES)}"
                )
                file_type = "other"

            r = _requests.post(
                f"{base}/runs/{run_id}/files",
                headers=headers,
                json={
                    "file_path": str(path),
                    "file_type": file_type,
                    "description": entry.get("description", ""),
                },
                timeout=30,
            )
            if r.ok:
                _info(f"  Attached {path.name} [{file_type}]")
            else:
                _warn(f"  Could not attach {path.name}: HTTP {r.status_code}")

        return run_id

    except _requests.exceptions.ConnectionError:
        _warn(f"Could not connect to NGS Tracker at {base}. Is the server running?")
        return None
    except _requests.exceptions.Timeout:
        _warn("Request to NGS Tracker timed out.")
        return None
    except _requests.exceptions.HTTPError as exc:
        _warn(f"HTTP error from NGS Tracker: {exc}")
        return None
    except Exception as exc:
        _warn(f"Unexpected error: {exc}")
        return None


def _info(msg: str) -> None:
    print(f"[ngs-tracker] {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"[ngs-tracker] WARNING: {msg}", file=sys.stderr)
