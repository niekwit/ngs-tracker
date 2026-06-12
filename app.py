import json
import os

from flask import Flask, redirect, url_for
from flask import request as flask_request

from config import DEFAULT_DB, is_configured, load_settings
from models import db

import routes.dashboard
import routes.files
import routes.groups
import routes.projects
import routes.researchers
import routes.runs
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
        ]:
            try:
                db.session.execute(db.text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()

    return app


app = create_app()
app.jinja_env.filters["from_json"] = json.loads


@app.before_request
def require_setup():
    if flask_request.endpoint in ("setup", "static"):
        return
    if not is_configured():
        return redirect(url_for("setup"))


# Register all route modules
routes.dashboard.register(app)
routes.groups.register(app)
routes.researchers.register(app)
routes.projects.register(app)
routes.runs.register(app)
routes.files.register(app)
routes.scripts.register(app)
routes.trash.register(app)
routes.system.register(app)


if __name__ == "__main__":
    port = int(os.environ.get("NGS_PORT", 5000))
    host = os.environ.get("NGS_HOST", "127.0.0.1")
    app.run(debug=False, host=host, port=port)
