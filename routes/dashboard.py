import json
from pathlib import Path

from flask import flash, redirect, render_template, request, url_for

from config import (
    DEFAULT_DB,
    SETTINGS_FILE,
    db_log,
    get_storage_path,
    is_configured,
    load_settings,
    save_settings,
)
from helpers import _format_file_size, _total_file_size
from models import (
    FILE_TYPES,
    AttachedFile,
    Project,
    ProjectScript,
    ResearchGroup,
    Researcher,
    ScriptOutputFile,
    WorkflowRun,
    db,
)


def register(app):
    @app.route("/")
    def index():
        groups = (
            ResearchGroup.query.filter_by(trashed=False)
            .order_by(ResearchGroup.name)
            .all()
        )
        recent_runs = (
            WorkflowRun.query.filter_by(trashed=False)
            .order_by(WorkflowRun.run_date.desc())
            .limit(8)
            .all()
        )
        file_type_counts = {
            label: AttachedFile.query.filter_by(file_type=key).count()
            for key, (label, _) in FILE_TYPES.items()
        }
        file_type_counts["Scripts"] = ProjectScript.query.count()
        file_type_counts["Script Outputs"] = ScriptOutputFile.query.count()
        file_type_counts = {k: v for k, v in file_type_counts.items() if v > 0}
        stats = {
            "groups": ResearchGroup.query.filter_by(trashed=False).count(),
            "researchers": Researcher.query.filter_by(trashed=False).count(),
            "projects": Project.query.filter_by(trashed=False).count(),
            "runs": WorkflowRun.query.filter_by(trashed=False).count(),
            "files": AttachedFile.query.count()
            + ProjectScript.query.count()
            + ScriptOutputFile.query.count(),
            "file_size": _format_file_size(_total_file_size()),
        }
        return render_template(
            "index.html",
            groups=groups,
            recent_runs=recent_runs,
            stats=stats,
            file_type_counts=json.dumps(file_type_counts),
        )

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if request.method == "POST":
            storage_path = request.form.get("storage_path", "").strip()
            db_path = request.form.get("db_path", "").strip()

            if not storage_path or not db_path:
                flash("Both paths are required.", "danger")
                return redirect(url_for("setup"))

            try:
                Path(storage_path).mkdir(parents=True, exist_ok=True)
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                flash(f"Could not create directories: {e}", "danger")
                return redirect(url_for("setup"))

            save_settings({"storage_path": storage_path, "db_path": db_path})
            flash(
                "Settings saved. Restart the server for the database path to take effect.",
                "success",
            )
            return redirect(url_for("index"))

        settings = load_settings()
        defaults = {
            "storage_path": settings.get("storage_path", str(get_storage_path())),
            "db_path": settings.get("db_path", str(DEFAULT_DB)),
        }
        return render_template(
            "setup.html", settings=defaults, settings_file=str(SETTINGS_FILE)
        )
