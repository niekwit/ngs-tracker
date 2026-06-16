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

import glob as _glob
import json
import os
import re
import sys
from datetime import datetime as _dt
from pathlib import Path

try:
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None


DEFAULT_BASE_URL = "http://127.0.0.1:5000/api"
VALID_STATUSES = {"completed", "running", "pending", "failed"}
VALID_FILE_TYPES = {
    "config",
    "sample_info",
    "qc",
    "results",
    "mapping_rates",
    "snakemake_log",
    "other",
}

_SETTINGS_FILE = Path.home() / ".ngs-tracker" / "settings.json"


_TS_RE = re.compile(r"\[(\w{3} \w{3} +\d+ \d{2}:\d{2}:\d{2} \d{4})\]")
_FINISHED_JOB_RE = re.compile(r"^Finished job(?:id:)? \d+", re.MULTILINE)


def _log_has_executions(path) -> bool:
    """Return True if the Snakemake log contains at least one completed job.

    Snakemake writes ``Finished job N.`` for every rule that actually ran.
    Dry-runs (``-n``), ``--containerize``, ``--touch``, ``--list-*`` and other
    non-executing modes never write this line, so it is a reliable signal that
    real work was done.
    """
    try:
        with open(path) as f:
            return bool(_FINISHED_JOB_RE.search(f.read()))
    except Exception:
        return False


def _parse_snakemake_log(path) -> int | None:
    """Return total pipeline duration in seconds from a Snakemake main log.

    Snakemake writes timestamps like ``[Fri Dec 12 11:36:18 2025]`` for every
    job event.  We take the first and last timestamp and return the difference.
    """
    timestamps = []
    try:
        with open(path) as f:
            for line in f:
                m = _TS_RE.search(line)
                if m:
                    # Collapse double-spaces (single-digit day: "Dec  2")
                    ts_str = " ".join(m.group(1).split())
                    try:
                        timestamps.append(_dt.strptime(ts_str, "%a %b %d %H:%M:%S %Y"))
                    except ValueError:
                        pass
    except Exception:
        return None
    if len(timestamps) < 2:
        return None
    return int((timestamps[-1] - timestamps[0]).total_seconds())


def _local_credentials() -> tuple[str, str]:
    """Return (api_key, current_user) from ~/.ngs-tracker/settings.json, or ('', '')."""
    try:
        with open(_SETTINGS_FILE) as f:
            s = json.load(f)
        return s.get("api_key", ""), s.get("current_user", "")
    except Exception:
        return "", ""


def _expand_file_entries(entries: list) -> list:
    """Expand glob patterns in file entries and resolve paths.

    Each entry may have a ``path`` that contains glob wildcards. Unmatched
    globs are kept as-is so that a warning is emitted later; matched globs
    produce one entry per matched file, inheriting ``type`` and ``description``.
    """
    result = []
    for entry in entries:
        raw_path = entry.get("path", "")
        if not raw_path:
            continue

        # Resolve relative to CWD before globbing
        base = Path(raw_path)
        if not base.is_absolute():
            base = Path.cwd() / base

        file_type = entry.get("type", "other")
        if file_type not in VALID_FILE_TYPES:
            _warn(
                f"Unknown file type '{file_type}',"
                f" using 'other'. Valid types: {sorted(VALID_FILE_TYPES)}"
            )
            file_type = "other"

        if any(c in raw_path for c in ("*", "?", "[")):
            matched = sorted(_glob.glob(str(base)))
            if not matched:
                _warn(f"Glob matched no files, skipping: {raw_path}")
            for m in matched:
                result.append(
                    {**entry, "path": str(Path(m).resolve()), "type": file_type}
                )
        else:
            path = base.resolve()
            if not path.exists():
                _warn(f"File not found, skipping: {path}")
                continue
            result.append({**entry, "path": str(path), "type": file_type})

    return result


def register_run(config: dict, status: str = "completed", log_file=None) -> int | None:
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
    log_file (str | Path, optional):
        Path to the Snakemake main log file.  In Snakemake ``onsuccess`` /
        ``onerror`` blocks the built-in ``log`` variable holds this path.
        When provided (or inferred from a ``snakemake_log`` file entry),
        the log is checked for completed-job markers before registration.
        If none are found the run is silently skipped — this means dry-runs
        (``-n``), ``--containerize``, ``--touch``, and other non-executing
        modes are automatically ignored without any special-casing in the
        Snakefile.  Runtime is also parsed from the log and stored on the
        run record.
    files (list[dict], optional):
        Files to attach.  Each entry has:
          path (str):        Path to the file (absolute or relative to CWD).
                             Glob wildcards (``*``, ``?``) are supported and
                             expand to all matching files at registration time.
          type (str):        File type — config / sample_info / qc / results /
                             mapping_rates / snakemake_log / other.
                             ``snakemake_log`` entries are parsed for runtime
                             if no other runtime source is available.
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

    # Key resolution: env var > ~/.ngs-tracker/settings.json > config YAML
    _local_key, _local_user = _local_credentials()
    key = os.environ.get("NGS_TRACKER_KEY") or _local_key or cfg.get("api_key", "")
    if not key:
        _warn(
            "No API key found. Set NGS_TRACKER_KEY or ensure NGS Tracker has "
            f"been started at least once (key is written to {_SETTINGS_FILE})."
        )
        return None

    project_id = cfg.get("project_id")
    if not project_id:
        _warn("'project_id' is required in config['ngs_tracker'].")
        return None

    headers = {"X-Api-Key": key}

    # User resolution: env var > ~/.ngs-tracker/settings.json > config YAML
    created_by = (
        os.environ.get("NGS_TRACKER_USER") or _local_user or cfg.get("created_by", "")
    )

    # Expand globs in the files list and deduplicate by resolved path.
    _expanded_files = _expand_file_entries(cfg.get("files", []))
    _seen_paths: set[str] = set()
    _deduped_files = []
    for _e in _expanded_files:
        if _e["path"] not in _seen_paths:
            _seen_paths.add(_e["path"])
            _deduped_files.append(_e)
    _expanded_files = _deduped_files

    # Build a deduplicated ordered list of all Snakemake log paths.
    # Sources: explicit log_file arg/config key + snakemake_log file entries.
    # Deduplication prevents the same file being counted twice for runtime or
    # dry-run detection when log_file= points to a file already in the entries.
    _explicit_log = log_file or cfg.get("log_file")
    _explicit_resolved = str(Path(_explicit_log).resolve()) if _explicit_log else None
    _log_file_paths: list[str] = []
    _seen_logs: set[str] = set()
    if _explicit_resolved:
        _log_file_paths.append(_explicit_resolved)
        _seen_logs.add(_explicit_resolved)
    for _e in _expanded_files:
        if _e.get("type") == "snakemake_log" and _e["path"] not in _seen_logs:
            _log_file_paths.append(_e["path"])
            _seen_logs.add(_e["path"])

    # Skip registration when logs are available but contain no completed jobs —
    # this catches dry-runs (-n), --containerize, --touch, --list-*, etc.
    if _log_file_paths and not any(_log_has_executions(p) for p in _log_file_paths):
        _info(
            "No completed jobs found in any Snakemake log — "
            "skipping registration (dry-run or non-executing mode)."
        )
        return None

    # Sum runtime from all unique log files.
    # The total goes in the initial POST so the run record always shows the
    # correct value, even before file attachments are processed.
    runtime_seconds = None
    if _log_file_paths:
        _total_secs = 0
        _parsed_count = 0
        for _p in _log_file_paths:
            _secs = _parse_snakemake_log(_p)
            if _secs is not None:
                _total_secs += _secs
                _parsed_count += 1
                _info(f"  + {_secs}s from {Path(_p).name}")
        if _parsed_count:
            runtime_seconds = _total_secs
            if _parsed_count > 1:
                _info(f"Total runtime: {runtime_seconds}s from {_parsed_count} log(s)")

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
            "created_by": created_by,
        }
        if runtime_seconds is not None:
            payload["runtime_seconds"] = runtime_seconds

        resp = _requests.post(f"{base}/runs", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        run_id = resp.json()["id"]
        _info(f"Run {run_id} registered (status={status}) — {base}/runs/{run_id}")

        # ── Attach files ──────────────────────────────────────────────────────
        for entry in _expanded_files:
            path = Path(entry["path"])
            file_type = entry.get("type", "other")

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
