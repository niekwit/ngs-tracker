import csv
import json
import re
from datetime import datetime
from pathlib import Path

import requests
import yaml

from config import SETTINGS_DIR
from models import AttachedFile, ProjectScript, ScriptOutputFile, WorkflowRun

_JOURNAL_CACHE = SETTINGS_DIR / "journal_cache.json"
_CROSSREF_UA = "NGS-Tracker/1.0 (mailto:nw416@cam.ac.uk)"


def get_journal_name(doi_url: str) -> str | None:
    """Resolve a doi.org URL to a journal name via CrossRef API. Results are cached."""
    if not doi_url or "doi.org/" not in doi_url.lower():
        return None
    doi = doi_url.strip().split("doi.org/", 1)[1]
    cache: dict = {}
    if _JOURNAL_CACHE.exists():
        try:
            cache = json.loads(_JOURNAL_CACHE.read_text())
        except Exception:
            pass
    if doi in cache:
        return cache[doi] or None
    try:
        resp = requests.get(
            f"https://api.crossref.org/works/{doi}",
            timeout=5,
            headers={"User-Agent": _CROSSREF_UA},
        )
        titles = (
            resp.json().get("message", {}).get("container-title", []) if resp.ok else []
        )
        journal = titles[0] if titles else ""
    except Exception:
        journal = ""
    cache[doi] = journal
    try:
        _JOURNAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _JOURNAL_CACHE.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass
    return journal or None


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


def _parse_mapping_rates(path: Path) -> str | None:
    """Parse a two-column CSV (sample, mapping_rate%) into JSON for chart rendering."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample_text = f.read(4096)
        import io

        dialect = csv.Sniffer().sniff(sample_text, delimiters=",\t;")
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f, dialect)
            rows = [r for r in reader if any(c.strip() for c in r)]
        if len(rows) < 2:
            return None
        # Detect header: skip first row if the second column doesn't parse as float
        start = 0
        try:
            float(rows[0][1].strip().rstrip("%"))
        except (ValueError, IndexError):
            start = 1  # first row is a header
        data_rows = rows[start:]
        if not data_rows:
            return None
        samples, rates = [], []
        for row in data_rows:
            if len(row) < 2:
                continue
            try:
                rate = float(row[1].strip().rstrip("%"))
            except ValueError:
                continue
            samples.append(row[0].strip())
            rates.append(round(rate, 2))
        if not samples:
            return None
        return json.dumps({"samples": samples, "rates": rates})
    except Exception:
        return None


_SNAKEMAKE_TS_RE = re.compile(r"\[(\w{3} \w{3} +\d+ \d{2}:\d{2}:\d{2} \d{4})\]")
_SNAKEMAKE_TS_LINE_RE = re.compile(r"^\[\w{3} \w{3}\s+\d+ \d{2}:\d{2}:\d{2} \d{4}\]$")
_ERROR_RULE_RE = re.compile(r"^Error in rule (\S+):")
_SEP_LINE_RE = re.compile(r"^={20,}")


def _parse_snakemake_log(path: Path) -> int | None:
    """Return pipeline duration in seconds from a Snakemake main log, or None."""
    timestamps = []
    try:
        with open(path, errors="replace") as f:
            for line in f:
                m = _SNAKEMAKE_TS_RE.search(line)
                if m:
                    ts_str = " ".join(m.group(1).split())
                    try:
                        timestamps.append(
                            datetime.strptime(ts_str, "%a %b %d %H:%M:%S %Y")
                        )
                    except ValueError:
                        pass
    except Exception:
        return None
    if len(timestamps) < 2:
        return None
    return int((timestamps[-1] - timestamps[0]).total_seconds())


def _parse_snakemake_errors(path: Path) -> list[str]:
    """Return deduplicated Snakemake error blocks from a log file.

    Each entry is one unique failed rule (by rule name). Parallel jobs failing
    with the same rule produce only one entry.
    """
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except Exception:
        return []

    seen_rules: set[str] = set()
    blocks: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        if lines[i] == "RuleException:":
            # Collect exception description lines until the timestamp line
            exc_start = i + 1
            i += 1
            while i < n and not _SNAKEMAKE_TS_LINE_RE.match(lines[i]):
                i += 1
            exc_lines = [l for l in lines[exc_start:i] if l.strip()]

            # Skip timestamp line
            if i < n and _SNAKEMAKE_TS_LINE_RE.match(lines[i]):
                i += 1

            # Parse "Error in rule <name>:" block
            if i < n:
                m = _ERROR_RULE_RE.match(lines[i])
                if m:
                    rule_name = m.group(1)
                    block_lines = [lines[i]]
                    i += 1

                    # Indented detail lines (jobid, input, output, log, conda-env)
                    while i < n and (
                        lines[i].startswith("    ") or lines[i].startswith("\t")
                    ):
                        block_lines.append(lines[i])
                        i += 1

                    # Optional logfile line and inline content
                    if i < n and lines[i].startswith("Logfile "):
                        block_lines.append(lines[i])
                        i += 1
                        if block_lines[-1].rstrip().endswith(":"):
                            # Opening === separator
                            if i < n and _SEP_LINE_RE.match(lines[i]):
                                block_lines.append(lines[i])
                                i += 1
                                while i < n and not _SEP_LINE_RE.match(lines[i]):
                                    block_lines.append(lines[i])
                                    i += 1
                                if i < n:
                                    block_lines.append(lines[i])  # closing ===
                                    i += 1

                    if rule_name not in seen_rules:
                        seen_rules.add(rule_name)
                        exc_text = "\n".join(exc_lines)
                        rule_text = "\n".join(block_lines)
                        combined = (
                            f"{exc_text}\n\n{rule_text}" if exc_text else rule_text
                        )
                        blocks.append(combined.strip())
        else:
            i += 1

    return blocks


def extract_samples_from_config(workflow_name: str, config: dict) -> list[dict] | None:
    """
    Extract sample names and group/condition labels from a parsed workflow config.
    Returns list of {"name": str, "description": str}, or None if unsupported.

    smallRNA-seq: samples: {sample_name: group}
    gps-orfeome:  conditions: {condition: "sample1 sample2 ..."}
    """
    if workflow_name == "smallRNA-seq":
        raw = config.get("samples")
        if not isinstance(raw, dict):
            return None
        return [{"name": str(k), "description": str(v)} for k, v in raw.items()]

    if workflow_name == "gps-orfeome":
        conditions = config.get("conditions")
        if not isinstance(conditions, dict):
            return None
        bin_number = int(config.get("bin_number", 1))
        seen: dict[str, str] = {}
        for condition, value in conditions.items():
            names = value if isinstance(value, list) else str(value).split()
            for name in names:
                name = str(name).strip()
                if not name:
                    continue
                if bin_number > 1:
                    for b in range(1, bin_number + 1):
                        binned = f"{name}_{b}"
                        if binned not in seen:
                            seen[binned] = str(condition)
                else:
                    if name not in seen:
                        seen[name] = str(condition)
        return [{"name": name, "description": cond} for name, cond in seen.items()]

    return None


def extract_samples_from_sample_info(workflow_name: str, path: Path) -> list[dict] | None:
    """Extract sample names from a sample_info file.

    Returns list of {"name": str, "description": str} or None if unsupported/unparseable.

    crispr-screens: stats.csv with 'test' and 'control' columns; unique names from both.
    """
    if workflow_name != "crispr-screens":
        return None
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            if "test" not in fields or "control" not in fields:
                return None
            roles: dict[str, set[str]] = {}
            for row in reader:
                for col in ("test", "control"):
                    name = row.get(col, "").strip()
                    if name:
                        roles.setdefault(name, set()).add(col)
        if not roles:
            return None
        return [
            {"name": name, "description": "/".join(sorted(roles[name]))}
            for name in roles
        ]
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


def find_duplicate_runs(
    project_id: int,
    workflow_name: str,
    run_date: datetime,
    exclude_id: int | None = None,
    description: str = "",
    sample_names: set | None = None,
) -> list:
    """Return runs sharing the same project, workflow, and calendar date.

    Candidates are excluded when both runs carry non-empty descriptions that
    differ, or both carry non-empty sample sets that differ — indicating
    intentionally distinct runs on the same day.
    """
    target_date = run_date.date()
    q = WorkflowRun.query.filter(
        WorkflowRun.project_id == project_id,
        WorkflowRun.workflow_name == workflow_name,
        WorkflowRun.trashed == False,
    )
    if exclude_id is not None:
        q = q.filter(WorkflowRun.id != exclude_id)
    candidates = [r for r in q.all() if r.run_date.date() == target_date]

    results = []
    for c in candidates:
        if description and c.description and description.strip() != c.description.strip():
            continue
        if sample_names:
            c_samples = {rs.sample.name for rs in c.run_samples}
            if c_samples and c_samples != sample_names:
                continue
        results.append(c)
    return results


def find_all_duplicate_run_ids(runs: list) -> set:
    """Return the IDs of all runs that have at least one genuine duplicate.

    Uses the same description/sample exclusion rules as find_duplicate_runs,
    but operates over an already-loaded list so it needs no extra queries.
    """
    from collections import defaultdict
    from itertools import combinations

    groups: dict = defaultdict(list)
    for run in runs:
        key = (run.project_id, run.workflow_name, run.run_date.date())
        groups[key].append(run)

    duplicate_ids: set = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        for a, b in combinations(group, 2):
            if a.description and b.description and a.description.strip() != b.description.strip():
                continue
            sa = {rs.sample.name for rs in a.run_samples}
            sb = {rs.sample.name for rs in b.run_samples}
            if sa and sb and sa != sb:
                continue
            duplicate_ids.add(a.id)
            duplicate_ids.add(b.id)
    return duplicate_ids


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
