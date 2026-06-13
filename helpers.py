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


def _flatten_config(d: dict, prefix: str = "") -> dict:
    result = {}
    if not isinstance(d, dict):
        return result
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            result.update(_flatten_config(v, key))
        else:
            result[key] = v
    return result


def _compare_configs(a: dict, b: dict) -> list[dict]:
    flat_a = _flatten_config(a)
    flat_b = _flatten_config(b)
    all_keys = sorted(set(flat_a) | set(flat_b), key=str.lower)
    rows = []
    for key in all_keys:
        in_a = key in flat_a
        in_b = key in flat_b
        val_a = flat_a.get(key)
        val_b = flat_b.get(key)
        if in_a and not in_b:
            status = "removed"
        elif not in_a and in_b:
            status = "added"
        elif repr(val_a) != repr(val_b):
            status = "changed"
        else:
            status = "same"
        rows.append({"key": key, "val_a": val_a, "val_b": val_b, "status": status})
    return rows


def _project_disk_bytes(project) -> int:
    total = 0
    for run in project.workflow_runs:
        for f in run.attached_files:
            try:
                total += Path(f.stored_path).stat().st_size
            except OSError:
                pass
        if run.sample_sheet:
            try:
                total += Path(run.sample_sheet.stored_path).stat().st_size
            except OSError:
                pass
    for script in project.scripts:
        try:
            total += Path(script.stored_path).stat().st_size
        except OSError:
            pass
        for of in script.output_files:
            try:
                total += Path(of.stored_path).stat().st_size
            except OSError:
                pass
    return total


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
