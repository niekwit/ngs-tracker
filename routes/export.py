import csv
import io
from datetime import datetime

from flask import make_response, request

from models import Project, Researcher, ResearchGroup, db

_HEADERS = [
    "Group",
    "Researcher",
    "Project",
    "Run Date",
    "Workflow",
    "Tag",
    "Status",
    "Backup",
    "Tags",
    "Notes",
    "Samples",
    "Files",
]

_KEYS = [
    "group",
    "researcher",
    "project",
    "run_date",
    "workflow",
    "tag",
    "status",
    "backup",
    "tags",
    "notes",
    "samples",
    "files",
]


def _run_row(run):
    return {
        "group": run.project.researcher.group.name,
        "researcher": run.project.researcher.name,
        "project": run.project.name,
        "run_date": run.run_date.strftime("%Y-%m-%d"),
        "workflow": run.workflow_name,
        "tag": run.workflow_tag or "",
        "status": run.status_label,
        "backup": ", ".join(run.backup_labels) or "None",
        "tags": ", ".join(run.tag_list),
        "notes": (run.notes or "").replace("\n", " "),
        "samples": str(len(run.run_samples)),
        "files": str(len(run.attached_files)),
    }


def _project_rows(project):
    return [_run_row(r) for r in project.sorted_runs]


def _researcher_rows(researcher):
    rows = []
    for p in sorted(
        (p for p in researcher.projects if not p.trashed), key=lambda p: p.name
    ):
        rows.extend(_project_rows(p))
    return rows


def _group_rows(group):
    rows = []
    for r in sorted(
        (r for r in group.researchers if not r.trashed), key=lambda r: r.name
    ):
        rows.extend(_researcher_rows(r))
    return rows


def _to_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_KEYS, extrasaction="ignore")
    writer.writerow(dict(zip(_KEYS, _HEADERS)))
    writer.writerows(rows)
    return buf.getvalue()


def _to_markdown(title, meta_lines, rows):
    now = datetime.utcnow().strftime("%Y-%m-%d")
    lines = [f"# {title}", ""]
    for line in meta_lines:
        lines.append(f"**{line[0]}:** {line[1]}  ")
    lines += [f"**Generated:** {now}  ", f"**Total runs:** {len(rows)}", ""]

    if not rows:
        lines.append("_No workflow runs recorded._")
        return "\n".join(lines) + "\n"

    widths = [
        max(len(h), max((len(str(r[k])) for r in rows), default=0))
        for h, k in zip(_HEADERS, _KEYS)
    ]

    def md_row(cells):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"

    lines.append(md_row(_HEADERS))
    lines.append("| " + " | ".join("-" * w for w in widths) + " |")
    for r in rows:
        lines.append(md_row([r[k] for k in _KEYS]))

    return "\n".join(lines) + "\n"


def _respond(rows, title, meta_lines, fmt, slug):
    stamp = datetime.utcnow().strftime("%Y%m%d")
    if fmt == "md":
        body = _to_markdown(title, meta_lines, rows)
        resp = make_response(body)
        resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
        resp.headers[
            "Content-Disposition"
        ] = f'attachment; filename="{slug}_{stamp}.md"'
    else:
        body = _to_csv(rows)
        resp = make_response(body)
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers[
            "Content-Disposition"
        ] = f'attachment; filename="{slug}_{stamp}.csv"'
    return resp


def register(app):
    @app.route("/projects/<int:id>/export")
    def project_export(id):
        project = db.get_or_404(Project, id)
        fmt = request.args.get("fmt", "csv")
        rows = _project_rows(project)
        meta = [
            ("Project", project.name),
            ("Researcher", project.researcher.name),
            ("Group", project.researcher.group.name),
        ]
        if project.description:
            meta.append(("Description", project.description))
        if project.published and project.publication_url:
            meta.append(("Publication", project.publication_url))
        return _respond(
            rows,
            f"{project.name} — Project Export",
            meta,
            fmt,
            f"project_{project.id}",
        )

    @app.route("/researchers/<int:id>/export")
    def researcher_export(id):
        researcher = db.get_or_404(Researcher, id)
        fmt = request.args.get("fmt", "csv")
        rows = _researcher_rows(researcher)
        meta = [
            ("Researcher", researcher.name),
            ("Group", researcher.group.name),
        ]
        if researcher.email:
            meta.append(("Email", researcher.email))
        return _respond(
            rows,
            f"{researcher.name} — Researcher Export",
            meta,
            fmt,
            f"researcher_{researcher.id}",
        )

    @app.route("/groups/<int:id>/export")
    def group_export(id):
        group = db.get_or_404(ResearchGroup, id)
        fmt = request.args.get("fmt", "csv")
        rows = _group_rows(group)
        active_researchers = [r for r in group.researchers if not r.trashed]
        meta = [
            ("Group", group.name),
            ("Researchers", str(len(active_researchers))),
        ]
        if group.description:
            meta.append(("Description", group.description))
        return _respond(
            rows,
            f"{group.name} — Group Export",
            meta,
            fmt,
            f"group_{group.id}",
        )
