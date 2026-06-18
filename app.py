import json
import os
import threading
import time

from flask import Flask, redirect, url_for
from flask import request as flask_request

from config import (
    DEFAULT_DB,
    TAG_COLOR_OPTIONS,
    WORKFLOW_SYSTEMS,
    get_current_user,
    get_tag_colors,
    get_version,
    is_configured,
    load_settings,
)
from models import db

import routes.api
import routes.dashboard
import routes.stats
import routes.export
import routes.files
import routes.groups
import routes.projects
import routes.researchers
import routes.runs
import routes.samples
import routes.scripts
import routes.system
import routes.trash


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("NGS_SECRET_KEY", "ngs-tracker-dev-secret")

    settings = load_settings()
    db_path = settings.get("db_path") or str(DEFAULT_DB)
    from pathlib import Path

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

    db.init_app(app)
    with app.app_context():
        db.create_all()
        for stmt in [
            "ALTER TABLE workflow_run ADD COLUMN workflow_tag VARCHAR(50) DEFAULT ''",
            "ALTER TABLE attached_file ADD COLUMN parsed_config TEXT",
            "ALTER TABLE workflow_run ADD COLUMN backup_local_path VARCHAR(500) DEFAULT ''",
            "ALTER TABLE workflow_run ADD COLUMN backup_rcs_path VARCHAR(500) DEFAULT ''",
            "ALTER TABLE workflow_run ADD COLUMN backup_rfs_path VARCHAR(500) DEFAULT ''",
            "ALTER TABLE project ADD COLUMN published BOOLEAN DEFAULT 0",
            "ALTER TABLE project ADD COLUMN publication_url VARCHAR(500) DEFAULT ''",
            "ALTER TABLE research_group ADD COLUMN trashed BOOLEAN DEFAULT 0",
            "ALTER TABLE researcher ADD COLUMN trashed BOOLEAN DEFAULT 0",
            "ALTER TABLE project ADD COLUMN trashed BOOLEAN DEFAULT 0",
            "ALTER TABLE workflow_run ADD COLUMN trashed BOOLEAN DEFAULT 0",
            "ALTER TABLE project_script ADD COLUMN trashed BOOLEAN DEFAULT 0",
            "ALTER TABLE workflow_run ADD COLUMN status VARCHAR(20) DEFAULT 'completed'",
            "ALTER TABLE workflow_run ADD COLUMN created_by VARCHAR(100) DEFAULT ''",
            "ALTER TABLE project_script ADD COLUMN created_by VARCHAR(100) DEFAULT ''",
            "ALTER TABLE workflow_run ADD COLUMN tags VARCHAR(500) DEFAULT ''",
            "ALTER TABLE workflow_run ADD COLUMN backups TEXT",
            "ALTER TABLE workflow_run ADD COLUMN workflow_system VARCHAR(20) DEFAULT 'snakemake'",
            "ALTER TABLE workflow_run ADD COLUMN runtime_seconds INTEGER",
            "ALTER TABLE researcher ADD COLUMN slack_user_id VARCHAR(20) DEFAULT ''",
        ]:
            try:
                db.session.execute(db.text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()

        # One-time migration: copy legacy backup columns into the JSON field
        from models import WorkflowRun

        unmigrated = WorkflowRun.query.filter(WorkflowRun.backups.is_(None)).all()
        for run in unmigrated:
            blist = []
            if run.backup_local:
                blist.append({"location": "Local", "path": run.backup_local_path or ""})
            if run.backup_rcs:
                blist.append({"location": "RCS", "path": run.backup_rcs_path or ""})
            if run.backup_rfs:
                blist.append({"location": "RFS", "path": run.backup_rfs_path or ""})
            run.backups = json.dumps(blist)
        if unmigrated:
            db.session.commit()

    return app


app = create_app()
app.jinja_env.filters["from_json"] = json.loads
app.jinja_env.globals["app_version"] = get_version()
app.jinja_env.globals["github_url"] = "https://github.com/niekwit/ngs-tracker"
app.jinja_env.globals["WORKFLOW_SYSTEMS"] = WORKFLOW_SYSTEMS


import re as _re


@app.template_filter("is_commit_sha")
def is_commit_sha_filter(s: str) -> bool:
    """True when s looks like a short (7-char) or full (40-char) git commit SHA."""
    return bool(_re.fullmatch(r"[0-9a-f]{7,40}", s or ""))


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


@app.context_processor
def inject_tag_context():
    return {
        "tag_colors": get_tag_colors(),
        "tag_color_options": TAG_COLOR_OPTIONS,
        # colors that need text-dark for readability
        "TAG_LIGHT_COLORS": {"warning", "info", "light"},
    }


@app.before_request
def require_setup():
    # API endpoints and static files bypass the setup redirect
    if flask_request.endpoint in ("setup", "static"):
        return
    if flask_request.path.startswith("/api/"):
        return
    if not is_configured():
        return redirect(url_for("setup"))


# Register all route modules
routes.api.register(app)
routes.dashboard.register(app)
routes.stats.register(app)
routes.export.register(app)
routes.groups.register(app)
routes.researchers.register(app)
routes.projects.register(app)
routes.runs.register(app)
routes.files.register(app)
routes.samples.register(app)
routes.scripts.register(app)
routes.trash.register(app)
routes.system.register(app)


def _start_snapshot_scheduler(app: Flask) -> None:
    """Daemon thread: check every 10 minutes and run a snapshot when due."""
    import logging
    from backup import is_snapshot_due, run_snapshot

    _log = logging.getLogger("ngs_tracker.snapshot")

    def _loop():
        while True:
            time.sleep(600)
            if is_snapshot_due():
                try:
                    with app.app_context():
                        from config import db_log
                        from notifier import send_snapshot_notification

                        path = run_snapshot()
                        db_log("CREATE", "Snapshot", 0, f"Scheduled snapshot: {path}")
                        send_snapshot_notification(True, path)
                except Exception as exc:
                    _log.error("Scheduled snapshot failed: %s", exc, exc_info=True)
                    try:
                        with app.app_context():
                            from notifier import send_snapshot_notification

                            send_snapshot_notification(False, str(exc))
                    except Exception:
                        pass

    threading.Thread(target=_loop, daemon=True, name="snapshot-scheduler").start()


_start_snapshot_scheduler(app)


if __name__ == "__main__":
    port = int(os.environ.get("NGS_PORT", 5000))
    host = os.environ.get("NGS_HOST", "127.0.0.1")
    app.run(debug=False, host=host, port=port)
