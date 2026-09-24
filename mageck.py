"""MAGeCK gene summary parsing and cross-comparison hit overlaps."""

import csv
import json
import re
from pathlib import Path

from models import AttachedFile, Project, Researcher, WorkflowRun, db

CUTOFF_COLUMNS = ("score", "p-value", "fdr")
DEFAULT_CUTOFF_COLUMN = "fdr"
DEFAULT_CUTOFF_VALUE = 0.25

# MAGeCK RRA gene_summary: "neg|" = depleted, "pos|" = enriched
_DIRECTIONS = {"depleted": "neg", "enriched": "pos"}

_SUFFIX_RE = re.compile(r"\.?gene_summary(\.txt)?$|\.txt$", re.IGNORECASE)


def normalise_cutoff(column, value) -> tuple[str, float]:
    """Validate a cutoff column/value pair (None -> defaults). Raises ValueError."""
    column = (str(column).strip().lower() if column else "") or DEFAULT_CUTOFF_COLUMN
    if column not in CUTOFF_COLUMNS:
        raise ValueError(
            f"Invalid cutoff_column '{column}'. Choose from: {list(CUTOFF_COLUMNS)}"
        )
    if value is None or str(value).strip() == "":
        return column, DEFAULT_CUTOFF_VALUE
    try:
        return column, float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid cutoff_value '{value}': must be a number")


def default_comparison_name(filename: str) -> str:
    """Comparison label from a file name, e.g. 'A_vs_B.gene_summary.txt' -> 'A_vs_B'."""
    return _SUFFIX_RE.sub("", filename) or filename


def _to_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_mageck_results(
    path: Path,
    cutoff_column: str = DEFAULT_CUTOFF_COLUMN,
    cutoff_value: float = DEFAULT_CUTOFF_VALUE,
    comparison: str | None = None,
) -> str | None:
    """Parse a MAGeCK (RRA) gene summary into JSON holding the hits at or below the cutoff.

    Enriched hits come from the ``pos|`` columns and depleted hits from ``neg|``.
    Returns None if the file is not a readable gene summary.
    """
    try:
        cutoff_column, cutoff_value = normalise_cutoff(cutoff_column, cutoff_value)
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter="\t")
            fields = reader.fieldnames or []
            if "id" not in fields or any(
                f"{p}|{cutoff_column}" not in fields for p in _DIRECTIONS.values()
            ):
                return None
            hits = {name: [] for name in _DIRECTIONS}
            n_genes = 0
            for row in reader:
                gene = (row.get("id") or "").strip()
                if not gene:
                    continue
                n_genes += 1
                for name, prefix in _DIRECTIONS.items():
                    metric = _to_float(row.get(f"{prefix}|{cutoff_column}"))
                    if metric is None or metric > cutoff_value:
                        continue
                    hits[name].append(
                        {
                            "gene": gene,
                            "score": _to_float(row.get(f"{prefix}|score")),
                            "p-value": _to_float(row.get(f"{prefix}|p-value")),
                            "fdr": _to_float(row.get(f"{prefix}|fdr")),
                            "lfc": _to_float(row.get(f"{prefix}|lfc")),
                        }
                    )
        if n_genes == 0:
            return None
        for name in hits:
            hits[name].sort(
                key=lambda h: (h[cutoff_column] is None, h[cutoff_column] or 0, h["gene"])
            )
        return json.dumps(
            {
                "comparison": comparison or default_comparison_name(Path(path).name),
                "cutoff_column": cutoff_column,
                "cutoff_value": cutoff_value,
                "n_genes": n_genes,
                **hits,
            }
        )
    except Exception:
        return None


def _gene_key(hit_or_gene) -> str:
    gene = hit_or_gene["gene"] if isinstance(hit_or_gene, dict) else hit_or_gene
    return gene.casefold()


def _comparison_dict(f: AttachedFile) -> dict:
    data = f.config_dict
    run = f.run
    return {
        "file_id": f.id,
        "run_id": run.id,
        "run_label": f"{run.workflow_name} #{run.id}",
        "project": run.project.name,
        "run_date": run.run_date,
        "comparison": data.get("comparison") or f.original_filename,
        "cutoff_column": data.get("cutoff_column"),
        "cutoff_value": data.get("cutoff_value"),
        "n_genes": data.get("n_genes"),
        "enriched": sorted(data.get("enriched", []), key=_gene_key),
        "depleted": sorted(data.get("depleted", []), key=_gene_key),
    }


def run_comparisons(run: WorkflowRun) -> list[dict]:
    """All parsed MAGeCK comparisons attached to a run."""
    return [
        _comparison_dict(f)
        for f in run.attached_files
        if f.file_type == "mageck_results" and f.config_dict
    ]


def _group_comparisons(run: WorkflowRun) -> list[dict]:
    """Parsed MAGeCK comparisons from other runs of the same research group."""
    group_id = run.project.researcher.group_id
    files = (
        AttachedFile.query.join(WorkflowRun, AttachedFile.workflow_run_id == WorkflowRun.id)
        .join(Project, WorkflowRun.project_id == Project.id)
        .join(Researcher, Project.researcher_id == Researcher.id)
        .filter(
            AttachedFile.file_type == "mageck_results",
            AttachedFile.parsed_config.isnot(None),
            WorkflowRun.id != run.id,
            WorkflowRun.trashed == False,
            Project.trashed == False,
            Researcher.trashed == False,
            Researcher.group_id == group_id,
        )
        .order_by(WorkflowRun.run_date.desc(), AttachedFile.id)
        .all()
    )
    return [_comparison_dict(f) for f in files]


def _overlap(a: dict, b: dict) -> list[dict]:
    """Same-direction hit overlaps between two comparisons (gene symbols case-insensitive)."""
    result = []
    for direction in _DIRECTIONS:
        b_genes = {h["gene"].upper() for h in b[direction]}
        genes = sorted(
            (h["gene"] for h in a[direction] if h["gene"].upper() in b_genes),
            key=_gene_key,
        )
        if genes:
            result.append({"direction": direction, "a": a, "b": b, "genes": genes})
    return result


def find_overlaps(run: WorkflowRun, mine: list[dict] | None = None) -> dict:
    """Overlapping hits between comparisons within a run and against the run's research group.

    Returns ``{"within_run": [...], "across_runs": [...]}``; each entry has
    ``direction`` (enriched|depleted), the two comparisons ``a`` and ``b``
    and the shared ``genes``.
    """
    if mine is None:
        mine = run_comparisons(run)
    within, across = [], []
    if not mine:
        return {"within_run": within, "across_runs": across}
    for i, a in enumerate(mine):
        for b in mine[i + 1 :]:
            within.extend(_overlap(a, b))
    for a in mine:
        for b in _group_comparisons(run):
            across.extend(_overlap(a, b))
    return {"within_run": within, "across_runs": across}
