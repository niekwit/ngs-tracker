import csv
import json
from datetime import datetime
from pathlib import Path

import yaml

from models import AttachedFile, ProjectScript, ScriptOutputFile, WorkflowRun


def _delete_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _delete_run_files(run: WorkflowRun) -> None:
    for f in run.attached_files:
        _delete_file(f.stored_path)


def _delete_group_files(group) -> None:
    for r in group.researchers:
        for p in r.projects:
            for run in p.workflow_runs:
                _delete_run_files(run)


def _parse_csv(path: Path) -> str | None:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        return json.dumps(rows)
    except Exception:
        return None


def _parse_snakemake_config(path: Path) -> str | None:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        data.pop("resources", None)
        return json.dumps(data)
    except Exception:
        return None


def _parse_datetime(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            pass
    return datetime.utcnow()


def _total_file_size() -> int:
    total = 0
    for model in (AttachedFile, ProjectScript, ScriptOutputFile):
        for row in model.query.all():
            try:
                total += Path(row.stored_path).stat().st_size
            except OSError:
                pass
    return total


def _format_file_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
