"""
REST API — /api/...

Authentication: pass the API key (shown in Settings) via the
  X-Api-Key  header  or  ?api_key=  query parameter.

Endpoints
---------
GET  /api/health              No auth. Returns {"status": "ok"}.
GET  /api/runs                List runs. Optional ?status=&project_id=&researcher_id=
GET  /api/runs/<id>           Single run.
POST /api/runs                Create a run.
PATCH /api/runs/<id>          Update status / notes / tags / backups.
POST /api/runs/<id>/files     Attach a file from disk to a run.
GET  /api/projects            List projects.
GET  /api/researchers         List researchers.
"""

import json
import shutil
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import jsonify, request
from werkzeug.utils import secure_filename

from config import db_log, get_api_key, get_storage_path
from helpers import (
    _parse_mapping_rates,
    _parse_snakemake_config,
    _parse_snakemake_log,
    find_duplicate_runs,
)
from models import (
    FILE_TYPES,
    AttachedFile,
    Project,
    Researcher,
    ResearchGroup,
    RUN_STATUSES,
    WorkflowRun,
    db,
)


# ── Auth ──────────────────────────────────────────────────────────────────────


def _require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-Api-Key") or request.args.get("api_key", "")
        if not key or key != get_api_key():
            return (
                jsonify({"error": "Unauthorized — provide a valid X-Api-Key header"}),
                401,
            )
        return f(*args, **kwargs)

    return decorated


# ── Serialisers ───────────────────────────────────────────────────────────────


def _run_dict(run: WorkflowRun) -> dict:
    return {
        "id": run.id,
        "project_id": run.project_id,
        "project": run.project.name,
        "researcher": run.project.researcher.name,
        "group": run.project.researcher.group.name,
        "workflow_name": run.workflow_name,
        "workflow_tag": run.workflow_tag or "",
        "workflow_system": run.workflow_system or "snakemake",
        "description": run.description or "",
        "status": run.status,
        "run_date": run.run_date.isoformat(),
        "tags": run.tag_list,
        "notes": run.notes or "",
        "backups": run.backups_list,
        "created_by": run.created_by or "",
        "runtime_seconds": run.runtime_seconds,
    }


def _project_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "researcher_id": p.researcher_id,
        "researcher": p.researcher.name,
        "group": p.researcher.group.name,
        "published": p.published,
        "publication_url": p.publication_url or "",
    }


def _researcher_dict(r: Researcher) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "email": r.email or "",
        "group_id": r.group_id,
        "group": r.group.name,
    }


def _file_dict(f: AttachedFile) -> dict:
    return {
        "id": f.id,
        "workflow_run_id": f.workflow_run_id,
        "original_filename": f.original_filename,
        "file_type": f.file_type,
        "type_label": f.type_label,
        "description": f.description or "",
        "uploaded_at": f.uploaded_at.isoformat(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────


def register(app):
    # ── Health ────────────────────────────────────────────────────────────────

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    # ── Runs — list ───────────────────────────────────────────────────────────

    @app.route("/api/runs")
    @_require_api_key
    def api_runs_list():
        from datetime import timedelta

        q = WorkflowRun.query.filter_by(trashed=False)
        if status := request.args.get("status"):
            q = q.filter_by(status=status)
        if pid := request.args.get("project_id", type=int):
            q = q.filter_by(project_id=pid)
        if rid := request.args.get("researcher_id", type=int):
            q = q.join(Project).filter(Project.researcher_id == rid)
        if df_str := request.args.get("date_from", "").strip():
            try:
                df = datetime.strptime(df_str, "%Y-%m-%d")
                q = q.filter(WorkflowRun.run_date >= df)
            except ValueError:
                return jsonify({"error": "Invalid date_from — use YYYY-MM-DD"}), 400
        if dt_str := request.args.get("date_to", "").strip():
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d") + timedelta(days=1)
                q = q.filter(WorkflowRun.run_date < dt)
            except ValueError:
                return jsonify({"error": "Invalid date_to — use YYYY-MM-DD"}), 400
        runs = q.order_by(WorkflowRun.run_date.desc()).all()
        return jsonify([_run_dict(r) for r in runs])

    # ── Runs — single ─────────────────────────────────────────────────────────

    @app.route("/api/runs/<int:id>")
    @_require_api_key
    def api_run_get(id):
        run = db.get_or_404(WorkflowRun, id)
        return jsonify(_run_dict(run))

    # ── Runs — create ─────────────────────────────────────────────────────────

    @app.route("/api/runs", methods=["POST"])
    @_require_api_key
    def api_run_create():
        data = request.get_json(force=True, silent=True) or {}

        # Resolve project — accept project_id (int) or project name (str)
        project_id = data.get("project_id")
        if not project_id and data.get("project"):
            p = Project.query.filter_by(name=data["project"], trashed=False).first()
            if not p:
                return jsonify({"error": f"Project '{data['project']}' not found"}), 404
            project_id = p.id
        if not project_id:
            return jsonify({"error": "'project_id' or 'project' name is required"}), 400

        if not db.session.get(Project, project_id):
            return jsonify({"error": f"Project {project_id} not found"}), 404

        # Validate status
        status = data.get("status", "completed")
        if status not in RUN_STATUSES:
            return (
                jsonify(
                    {
                        "error": f"Invalid status '{status}'. Choose from: {list(RUN_STATUSES)}"
                    }
                ),
                400,
            )

        run = WorkflowRun(
            project_id=project_id,
            workflow_name=data.get("workflow_name", ""),
            workflow_tag=data.get("workflow_tag", ""),
            workflow_system=data.get("workflow_system", "snakemake"),
            description=data.get("description", ""),
            status=status,
            notes=data.get("notes", ""),
            tags=",".join(data["tags"])
            if isinstance(data.get("tags"), list)
            else data.get("tags", ""),
            created_by=data.get("created_by", ""),
            backups=json.dumps(data.get("backups", [])),
        )

        if "run_date" in data:
            try:
                run.run_date = datetime.fromisoformat(data["run_date"])
            except (ValueError, TypeError):
                return (
                    jsonify(
                        {
                            "error": "Invalid run_date — use ISO 8601 (e.g. 2025-06-14T09:00:00)"
                        }
                    ),
                    400,
                )

        if "runtime_seconds" in data:
            try:
                run.runtime_seconds = int(data["runtime_seconds"])
            except (TypeError, ValueError):
                pass

        db.session.add(run)
        db.session.commit()
        db_log("CREATE", "WorkflowRun", run.id, f"{run.workflow_name} via API")
        resp = _run_dict(run)
        duplicates = find_duplicate_runs(
            run.project_id, run.workflow_name, run.run_date, exclude_id=run.id
        )
        if duplicates:
            resp["duplicate_warning"] = True
            resp["duplicate_of"] = [r.id for r in duplicates]
        return jsonify(resp), 201

    # ── Runs — update ─────────────────────────────────────────────────────────

    @app.route("/api/runs/<int:id>", methods=["PATCH"])
    @_require_api_key
    def api_run_update(id):
        run = db.get_or_404(WorkflowRun, id)
        data = request.get_json(force=True, silent=True) or {}

        if "status" in data:
            if data["status"] not in RUN_STATUSES:
                return jsonify({"error": f"Invalid status '{data['status']}'"}), 400
            run.status = data["status"]
        if "description" in data:
            run.description = data["description"]
        if "notes" in data:
            run.notes = data["notes"]
        if "workflow_tag" in data:
            run.workflow_tag = data["workflow_tag"]
        if "tags" in data:
            t = data["tags"]
            run.tags = ",".join(t) if isinstance(t, list) else t
        if "backups" in data:
            run.backups = json.dumps(data["backups"])

        db.session.commit()
        db_log("UPDATE", "WorkflowRun", run.id, f"{run.workflow_name} via API")
        return jsonify(_run_dict(run))

    # ── Files — attach from disk path ─────────────────────────────────────────

    @app.route("/api/runs/<int:id>/files", methods=["POST"])
    @_require_api_key
    def api_run_attach_file(id):
        run = db.get_or_404(WorkflowRun, id)
        data = request.get_json(force=True, silent=True) or {}

        file_path = data.get("file_path", "").strip()
        if not file_path:
            return jsonify({"error": "'file_path' is required"}), 400

        src = Path(file_path)
        if not src.exists():
            return jsonify({"error": f"File not found: {file_path}"}), 400
        if not src.is_file():
            return jsonify({"error": f"Path is not a file: {file_path}"}), 400

        file_type = data.get("file_type", "other")
        if file_type not in FILE_TYPES:
            return (
                jsonify(
                    {
                        "error": f"Invalid file_type '{file_type}'. "
                        f"Choose from: {list(FILE_TYPES)}"
                    }
                ),
                400,
            )

        description = data.get("description", "").strip()

        run_dir = get_storage_path() / "runs" / str(id)
        run_dir.mkdir(parents=True, exist_ok=True)

        original_name = secure_filename(src.name)
        stored_path = run_dir / f"{uuid.uuid4().hex}_{original_name}"
        shutil.copy2(src, stored_path)

        if file_type == "config":
            parsed_config = _parse_snakemake_config(stored_path)
        elif file_type == "mapping_rates":
            parsed_config = _parse_mapping_rates(stored_path)
        elif file_type == "snakemake_log":
            parsed_config = None
            secs = _parse_snakemake_log(stored_path)
            if secs is not None:
                run.runtime_seconds = (run.runtime_seconds or 0) + secs
        else:
            parsed_config = None

        attached = AttachedFile(
            workflow_run_id=id,
            original_filename=original_name,
            stored_path=str(stored_path),
            file_type=file_type,
            description=description,
            parsed_config=parsed_config,
        )
        db.session.add(attached)
        db.session.flush()
        db_log(
            "CREATE",
            "AttachedFile",
            attached.id,
            f"{original_name} [{file_type}] on run id={id} via API",
        )
        db.session.commit()
        return jsonify(_file_dict(attached)), 201

    # ── Projects ──────────────────────────────────────────────────────────────

    @app.route("/api/projects")
    @_require_api_key
    def api_projects_list():
        projects = (
            Project.query.filter_by(trashed=False)
            .join(Researcher)
            .filter(Researcher.trashed == False)
            .join(ResearchGroup)
            .filter(ResearchGroup.trashed == False)
            .order_by(ResearchGroup.name, Researcher.name, Project.name)
            .all()
        )
        return jsonify([_project_dict(p) for p in projects])

    # ── Researchers ───────────────────────────────────────────────────────────

    @app.route("/api/researchers")
    @_require_api_key
    def api_researchers_list():
        researchers = (
            Researcher.query.filter_by(trashed=False)
            .join(ResearchGroup)
            .filter(ResearchGroup.trashed == False)
            .order_by(ResearchGroup.name, Researcher.name)
            .all()
        )
        return jsonify([_researcher_dict(r) for r in researchers])
