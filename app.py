import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import shutil

import yaml

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from models import (
    FILE_TYPES,
    RUN_STATUSES,
    SCRIPT_LANGUAGES,
    AttachedFile,
    Project,
    ProjectScript,
    SampleSheet,
    ScriptOutputFile,
    Researcher,
    ResearchGroup,
    WorkflowRun,
    db,
)

# Settings live in the user's home directory so they survive re-clones.
SETTINGS_DIR = Path.home() / ".ngs-tracker"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
WORKFLOWS_FILE = SETTINGS_DIR / "workflows.yaml"
# Legacy location (app directory) — migrated on first load if found.
_LEGACY_SETTINGS = Path(__file__).parent / "settings.json"
DEFAULT_DB = SETTINGS_DIR / "ngs_tracker.db"

_DEFAULT_WORKFLOWS = [
    {"name": "atac-seq", "url": "https://github.com/niekwit/atac-seq"},
    {"name": "chip-seq", "url": "https://github.com/niekwit/chip-seq"},
    {"name": "crispr-screens", "url": "https://github.com/niekwit/crispr-screens"},
    {"name": "cut_and_run", "url": "https://github.com/niekwit/cut_and_run"},
    {"name": "damid-seq", "url": "https://github.com/niekwit/damid-seq"},
    {"name": "eCLIP", "url": "https://github.com/niekwit/eCLIP"},
    {"name": "gps-orfeome", "url": "https://github.com/niekwit/gps-orfeome"},
    {"name": "methyl-seq", "url": "https://github.com/niekwit/methyl-seq"},
    {"name": "remora", "url": "https://github.com/niekwit/remora"},
    {"name": "rip-seq", "url": "https://github.com/niekwit/rip-seq"},
    {
        "name": "rna-seq-salmon-deseq2",
        "url": "https://github.com/niekwit/rna-seq-salmon-deseq2",
    },
    {
        "name": "rna-seq-star-deseq2",
        "url": "https://github.com/niekwit/rna-seq-star-deseq2",
    },
    {
        "name": "rna-seq-star-tetranscripts",
        "url": "https://github.com/niekwit/rna-seq-star-tetranscripts",
    },
    {"name": "smallRNA-seq", "url": "https://github.com/niekwit/smallRNA-seq"},
    {"name": "tt-seq", "url": "https://github.com/niekwit/tt-seq"},
]


# ── Settings helpers ──────────────────────────────────────────────────────────


def load_settings() -> dict:
    # Migrate from old app-directory location on first run after upgrade
    if not SETTINGS_FILE.exists() and _LEGACY_SETTINGS.exists():
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_SETTINGS, SETTINGS_FILE)
        _LEGACY_SETTINGS.unlink(missing_ok=True)
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def save_settings(settings: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def is_configured() -> bool:
    s = load_settings()
    return bool(s.get("storage_path") and s.get("db_path"))


def get_storage_path() -> Path:
    s = load_settings()
    if s.get("storage_path"):
        return Path(s["storage_path"])
    return SETTINGS_DIR / "uploads"


# ── Workflow helpers ───────────────────────────────────────────────────────────


def load_workflows() -> list:
    if not WORKFLOWS_FILE.exists():
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(WORKFLOWS_FILE, "w") as f:
            yaml.dump(_DEFAULT_WORKFLOWS, f, default_flow_style=False, sort_keys=False)
    with open(WORKFLOWS_FILE) as f:
        return yaml.safe_load(f) or []


def save_workflows(workflows: list) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKFLOWS_FILE, "w") as f:
        yaml.dump(workflows, f, default_flow_style=False, sort_keys=False)


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("NGS_SECRET_KEY", "ngs-tracker-dev-secret")

    settings = load_settings()
    db_path = settings.get("db_path") or str(DEFAULT_DB)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

    db.init_app(app)
    with app.app_context():
        db.create_all()
        # Inline migrations for columns added after initial release
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
            # project_script / script_output_file tables created by db.create_all()
        ]:
            try:
                db.session.execute(db.text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()

    return app


app = create_app()
app.jinja_env.filters["from_json"] = json.loads


# ── Guards ────────────────────────────────────────────────────────────────────


@app.before_request
def require_setup():
    if request.endpoint in ("setup", "static"):
        return
    if not is_configured():
        return redirect(url_for("setup"))


# ── Dashboard ─────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    groups = (
        ResearchGroup.query.filter_by(trashed=False).order_by(ResearchGroup.name).all()
    )
    recent_runs = (
        WorkflowRun.query.filter_by(trashed=False)
        .order_by(WorkflowRun.run_date.desc())
        .limit(8)
        .all()
    )
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
        "index.html", groups=groups, recent_runs=recent_runs, stats=stats
    )


# ── Setup ─────────────────────────────────────────────────────────────────────


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
        "storage_path": settings.get("storage_path", str(SETTINGS_DIR / "uploads")),
        "db_path": settings.get("db_path", str(DEFAULT_DB)),
    }
    return render_template(
        "setup.html", settings=defaults, settings_file=str(SETTINGS_FILE)
    )


# ── List views ────────────────────────────────────────────────────────────────


@app.route("/groups")
def groups_list():
    groups = (
        ResearchGroup.query.filter_by(trashed=False).order_by(ResearchGroup.name).all()
    )
    return render_template("groups/list.html", groups=groups)


@app.route("/researchers")
def researchers_list():
    researchers = (
        Researcher.query.filter_by(trashed=False)
        .join(ResearchGroup)
        .filter(ResearchGroup.trashed == False)
        .order_by(ResearchGroup.name, Researcher.name)
        .all()
    )
    return render_template("researchers/list.html", researchers=researchers)


@app.route("/projects")
def projects_list():
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    reverse = direction == "desc"

    projects = (
        Project.query.filter_by(trashed=False)
        .join(Researcher)
        .filter(Researcher.trashed == False)
        .join(ResearchGroup)
        .filter(ResearchGroup.trashed == False)
        .all()
    )

    key_map = {
        "name": lambda p: p.name.lower(),
        "researcher": lambda p: p.researcher.name.lower(),
        "group": lambda p: p.researcher.group.name.lower(),
        "runs": lambda p: sum(1 for r in p.workflow_runs if not r.trashed),
        "published": lambda p: p.published,
    }
    projects.sort(key=key_map.get(sort, key_map["name"]), reverse=reverse)

    return render_template(
        "projects/list.html", projects=projects, sort=sort, dir=direction
    )


@app.route("/runs")
def runs_list():
    sort = request.args.get("sort", "date")
    direction = request.args.get("dir", "desc")
    reverse = direction == "desc"

    runs = WorkflowRun.query.filter_by(trashed=False).all()

    key_map = {
        "workflow": lambda r: r.workflow_name.lower(),
        "project": lambda r: r.project.name.lower(),
        "researcher": lambda r: r.project.researcher.name.lower(),
        "date": lambda r: r.run_date,
        "status": lambda r: r.status,
        "backup": lambda r: len(r.backup_labels),
        "files": lambda r: len(r.attached_files),
    }
    runs.sort(key=key_map.get(sort, key_map["date"]), reverse=reverse)

    return render_template("runs/list.html", runs=runs, sort=sort, dir=direction)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("search.html", q="", results=None)
    like = f"%{q}%"
    results = {
        "groups": ResearchGroup.query.filter(
            ResearchGroup.trashed == False,
            ResearchGroup.name.ilike(like) | ResearchGroup.description.ilike(like),
        ).all(),
        "researchers": Researcher.query.filter(
            Researcher.trashed == False,
            Researcher.name.ilike(like) | Researcher.email.ilike(like),
        ).all(),
        "projects": Project.query.filter(
            Project.trashed == False,
            Project.name.ilike(like) | Project.description.ilike(like),
        ).all(),
        "runs": WorkflowRun.query.filter(
            WorkflowRun.trashed == False,
            WorkflowRun.workflow_name.ilike(like)
            | WorkflowRun.description.ilike(like)
            | WorkflowRun.notes.ilike(like),
        ).all(),
        "scripts": ProjectScript.query.filter(
            ProjectScript.trashed == False,
            ProjectScript.original_filename.ilike(like)
            | ProjectScript.description.ilike(like),
        ).all(),
    }
    total = sum(len(v) for v in results.values())
    return render_template("search.html", q=q, results=results, total=total)


@app.route("/groups/new", methods=["GET", "POST"])
def group_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Group name is required.", "danger")
            return render_template("groups/form.html", group=None)
        if ResearchGroup.query.filter_by(name=name).first():
            flash("A group with that name already exists.", "danger")
            return render_template("groups/form.html", group=None)
        group = ResearchGroup(name=name, description=description)
        db.session.add(group)
        db.session.commit()
        flash(f'Research group "{name}" created.', "success")
        return redirect(url_for("group_detail", id=group.id))
    return render_template("groups/form.html", group=None)


@app.route("/groups/<int:id>")
def group_detail(id):
    group = db.get_or_404(ResearchGroup, id)
    return render_template("groups/detail.html", group=group)


@app.route("/groups/<int:id>/edit", methods=["GET", "POST"])
def group_edit(id):
    group = db.get_or_404(ResearchGroup, id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Group name is required.", "danger")
            return render_template("groups/form.html", group=group)
        group.name = name
        group.description = request.form.get("description", "").strip()
        db.session.commit()
        flash("Group updated.", "success")
        return redirect(url_for("group_detail", id=id))
    return render_template("groups/form.html", group=group)


@app.route("/groups/<int:id>/delete", methods=["POST"])
def group_delete(id):
    group = db.get_or_404(ResearchGroup, id)
    group.trashed = True
    db.session.commit()
    flash(f'Group "{group.name}" moved to trash.', "success")
    return redirect(url_for("groups_list"))


def _delete_group_files(group: ResearchGroup) -> None:
    for r in group.researchers:
        for p in r.projects:
            for run in p.workflow_runs:
                _delete_run_files(run)


# ── Researchers ───────────────────────────────────────────────────────────────


@app.route("/researchers/new", methods=["GET", "POST"])
def researcher_new():
    groups = (
        ResearchGroup.query.filter_by(trashed=False).order_by(ResearchGroup.name).all()
    )
    if not groups:
        flash("Create a research group first.", "warning")
        return redirect(url_for("group_new"))

    preselected = request.args.get("group_id", type=int)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        group_id = request.form.get("group_id", type=int)
        if not name or not group_id:
            flash("Name and group are required.", "danger")
            return render_template(
                "researchers/form.html",
                researcher=None,
                groups=groups,
                preselected=preselected,
            )
        researcher = Researcher(name=name, email=email, group_id=group_id)
        db.session.add(researcher)
        db.session.commit()
        flash(f'Researcher "{name}" created.', "success")
        return redirect(url_for("researcher_detail", id=researcher.id))

    return render_template(
        "researchers/form.html", researcher=None, groups=groups, preselected=preselected
    )


@app.route("/researchers/<int:id>")
def researcher_detail(id):
    researcher = db.get_or_404(Researcher, id)
    return render_template("researchers/detail.html", researcher=researcher)


@app.route("/researchers/<int:id>/edit", methods=["GET", "POST"])
def researcher_edit(id):
    researcher = db.get_or_404(Researcher, id)
    groups = (
        ResearchGroup.query.filter_by(trashed=False).order_by(ResearchGroup.name).all()
    )
    if request.method == "POST":
        researcher.name = request.form.get("name", "").strip()
        researcher.email = request.form.get("email", "").strip()
        researcher.group_id = request.form.get("group_id", type=int)
        db.session.commit()
        flash("Researcher updated.", "success")
        return redirect(url_for("researcher_detail", id=id))
    return render_template(
        "researchers/form.html",
        researcher=researcher,
        groups=groups,
        preselected=researcher.group_id,
    )


@app.route("/researchers/<int:id>/delete", methods=["POST"])
def researcher_delete(id):
    researcher = db.get_or_404(Researcher, id)
    researcher.trashed = True
    db.session.commit()
    flash(f'Researcher "{researcher.name}" moved to trash.', "success")
    return redirect(url_for("group_detail", id=researcher.group_id))


# ── Projects ──────────────────────────────────────────────────────────────────


@app.route("/projects/new", methods=["GET", "POST"])
def project_new():
    researchers = (
        Researcher.query.filter_by(trashed=False)
        .join(ResearchGroup)
        .filter(ResearchGroup.trashed == False)
        .order_by(ResearchGroup.name, Researcher.name)
        .all()
    )
    if not researchers:
        flash("Create a researcher first.", "warning")
        return redirect(url_for("researcher_new"))

    preselected = request.args.get("researcher_id", type=int)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        researcher_id = request.form.get("researcher_id", type=int)
        if not name or not researcher_id:
            flash("Name and researcher are required.", "danger")
            return render_template(
                "projects/form.html",
                project=None,
                researchers=researchers,
                preselected=preselected,
            )
        published = "published" in request.form
        publication_url = request.form.get("publication_url", "").strip()
        project = Project(
            name=name,
            description=description,
            researcher_id=researcher_id,
            published=published,
            publication_url=publication_url,
        )
        db.session.add(project)
        db.session.commit()
        flash(f'Project "{name}" created.', "success")
        return redirect(url_for("project_detail", id=project.id))

    return render_template(
        "projects/form.html",
        project=None,
        researchers=researchers,
        preselected=preselected,
    )


@app.route("/projects/<int:id>")
def project_detail(id):
    project = db.get_or_404(Project, id)
    return render_template(
        "projects/detail.html", project=project, script_languages=SCRIPT_LANGUAGES
    )


@app.route("/projects/<int:id>/edit", methods=["GET", "POST"])
def project_edit(id):
    project = db.get_or_404(Project, id)
    researchers = (
        Researcher.query.filter_by(trashed=False)
        .join(ResearchGroup)
        .filter(ResearchGroup.trashed == False)
        .order_by(ResearchGroup.name, Researcher.name)
        .all()
    )
    if request.method == "POST":
        project.name = request.form.get("name", "").strip()
        project.description = request.form.get("description", "").strip()
        project.researcher_id = request.form.get("researcher_id", type=int)
        project.published = "published" in request.form
        project.publication_url = request.form.get("publication_url", "").strip()
        db.session.commit()
        flash("Project updated.", "success")
        return redirect(url_for("project_detail", id=id))
    return render_template(
        "projects/form.html",
        project=project,
        researchers=researchers,
        preselected=project.researcher_id,
    )


@app.route("/projects/<int:id>/delete", methods=["POST"])
def project_delete(id):
    project = db.get_or_404(Project, id)
    project.trashed = True
    db.session.commit()
    flash(f'Project "{project.name}" moved to trash.', "success")
    return redirect(url_for("researcher_detail", id=project.researcher_id))


# ── Workflow Runs ─────────────────────────────────────────────────────────────


@app.route("/runs/new", methods=["GET", "POST"])
def run_new():
    projects = (
        Project.query.filter_by(trashed=False)
        .join(Researcher)
        .filter(Researcher.trashed == False)
        .join(ResearchGroup)
        .filter(ResearchGroup.trashed == False)
        .order_by(ResearchGroup.name, Researcher.name, Project.name)
        .all()
    )
    if not projects:
        flash("Create a project first.", "warning")
        return redirect(url_for("project_new"))

    preselected = request.args.get("project_id", type=int)

    if request.method == "POST":
        project_id = request.form.get("project_id", type=int)
        workflow_name = request.form.get("workflow_name", "").strip()
        workflow_tag = request.form.get("workflow_tag", "").strip()
        description = request.form.get("description", "").strip()
        notes = request.form.get("notes", "").strip()
        status = request.form.get("status", "completed")
        run_date = _parse_datetime(request.form.get("run_date", ""))
        backup_local = "backup_local" in request.form
        backup_rcs = "backup_rcs" in request.form
        backup_rfs = "backup_rfs" in request.form
        backup_local_path = request.form.get("backup_local_path", "").strip()
        backup_rcs_path = request.form.get("backup_rcs_path", "").strip()
        backup_rfs_path = request.form.get("backup_rfs_path", "").strip()

        if not workflow_name or not project_id:
            flash("Workflow name and project are required.", "danger")
            return render_template(
                "runs/form.html",
                run=None,
                projects=projects,
                preselected=preselected,
                file_types=FILE_TYPES,
                workflows=load_workflows(),
                run_statuses=RUN_STATUSES,
            )

        run = WorkflowRun(
            project_id=project_id,
            workflow_name=workflow_name,
            workflow_tag=workflow_tag,
            description=description,
            run_date=run_date,
            notes=notes,
            status=status,
            backup_local=backup_local,
            backup_local_path=backup_local_path,
            backup_rcs=backup_rcs,
            backup_rcs_path=backup_rcs_path,
            backup_rfs=backup_rfs,
            backup_rfs_path=backup_rfs_path,
        )
        db.session.add(run)
        db.session.commit()
        flash(f'Workflow run "{workflow_name}" created.', "success")
        return redirect(url_for("run_detail", id=run.id))

    return render_template(
        "runs/form.html",
        run=None,
        projects=projects,
        preselected=preselected,
        file_types=FILE_TYPES,
        workflows=load_workflows(),
        run_statuses=RUN_STATUSES,
    )


@app.route("/runs/<int:id>")
def run_detail(id):
    run = db.get_or_404(WorkflowRun, id)
    wf_urls = {w["name"]: w["url"] for w in load_workflows()}
    return render_template(
        "runs/detail.html", run=run, file_types=FILE_TYPES, wf_urls=wf_urls
    )


@app.route("/runs/<int:id>/edit", methods=["GET", "POST"])
def run_edit(id):
    run = db.get_or_404(WorkflowRun, id)
    projects = (
        Project.query.filter_by(trashed=False)
        .join(Researcher)
        .filter(Researcher.trashed == False)
        .join(ResearchGroup)
        .filter(ResearchGroup.trashed == False)
        .order_by(ResearchGroup.name, Researcher.name, Project.name)
        .all()
    )
    if request.method == "POST":
        run.workflow_name = request.form.get("workflow_name", "").strip()
        run.workflow_tag = request.form.get("workflow_tag", "").strip()
        run.description = request.form.get("description", "").strip()
        run.notes = request.form.get("notes", "").strip()
        run.status = request.form.get("status", "completed")
        run.run_date = _parse_datetime(request.form.get("run_date", ""))
        run.backup_local = "backup_local" in request.form
        run.backup_local_path = request.form.get("backup_local_path", "").strip()
        run.backup_rcs = "backup_rcs" in request.form
        run.backup_rcs_path = request.form.get("backup_rcs_path", "").strip()
        run.backup_rfs = "backup_rfs" in request.form
        run.backup_rfs_path = request.form.get("backup_rfs_path", "").strip()
        db.session.commit()
        flash("Workflow run updated.", "success")
        return redirect(url_for("run_detail", id=id))
    return render_template(
        "runs/form.html",
        run=run,
        projects=projects,
        preselected=run.project_id,
        file_types=FILE_TYPES,
        workflows=load_workflows(),
        run_statuses=RUN_STATUSES,
    )


@app.route("/runs/<int:id>/clone", methods=["POST"])
def run_clone(id):
    src = db.get_or_404(WorkflowRun, id)
    clone = WorkflowRun(
        project_id=src.project_id,
        workflow_name=src.workflow_name,
        workflow_tag=src.workflow_tag,
        description=src.description,
        notes=src.notes,
        status="pending",
        backup_local=src.backup_local,
        backup_local_path=src.backup_local_path,
        backup_rcs=src.backup_rcs,
        backup_rcs_path=src.backup_rcs_path,
        backup_rfs=src.backup_rfs,
        backup_rfs_path=src.backup_rfs_path,
    )
    db.session.add(clone)
    db.session.commit()
    flash(f'Run cloned from "{src.workflow_name}" — review and save.', "success")
    return redirect(url_for("run_edit", id=clone.id))


@app.route("/runs/<int:id>/delete", methods=["POST"])
def run_delete(id):
    run = db.get_or_404(WorkflowRun, id)
    run.trashed = True
    db.session.commit()
    flash(f'Workflow run "{run.workflow_name}" moved to trash.', "success")
    return redirect(url_for("project_detail", id=run.project_id))


# ── Workflow management ───────────────────────────────────────────────────────


@app.route("/workflows", methods=["GET", "POST"])
def workflows_manage():
    if request.method == "POST":
        action = request.form.get("action")
        workflows = load_workflows()

        if action == "add":
            name = request.form.get("name", "").strip()
            url = request.form.get("url", "").strip()
            if not name or not url:
                flash("Name and URL are required.", "danger")
            elif any(w["name"] == name for w in workflows):
                flash(f'Workflow "{name}" already exists.', "warning")
            else:
                workflows.append({"name": name, "url": url})
                workflows.sort(key=lambda w: w["name"].lower())
                save_workflows(workflows)
                flash(f'Workflow "{name}" added.', "success")

        elif action == "delete":
            name = request.form.get("name", "")
            workflows = [w for w in workflows if w["name"] != name]
            save_workflows(workflows)
            flash(f'Workflow "{name}" removed.', "success")

        return redirect(url_for("workflows_manage"))

    workflows = load_workflows()
    return render_template(
        "workflows/manage.html",
        workflows=workflows,
        workflows_file=str(WORKFLOWS_FILE),
    )


# ── File Attachments ──────────────────────────────────────────────────────────


@app.route("/runs/<int:id>/upload", methods=["POST"])
def run_upload(id):
    run = db.get_or_404(WorkflowRun, id)

    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("run_detail", id=id))

    file = request.files["file"]
    file_type = request.form.get("file_type", "other")
    description = request.form.get("description", "").strip()

    original_name = secure_filename(file.filename)
    run_dir = get_storage_path() / "runs" / str(id)
    run_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    stored_path = run_dir / stored_name
    file.save(str(stored_path))

    parsed_config = (
        _parse_snakemake_config(stored_path) if file_type == "config" else None
    )

    attached = AttachedFile(
        workflow_run_id=id,
        original_filename=original_name,
        stored_path=str(stored_path),
        file_type=file_type,
        description=description,
        parsed_config=parsed_config,
    )
    db.session.add(attached)
    db.session.commit()
    flash(f'File "{original_name}" uploaded.', "success")
    return redirect(url_for("run_detail", id=id))


@app.route("/files/<int:id>/download")
def file_download(id):
    f = db.get_or_404(AttachedFile, id)
    stored = Path(f.stored_path)
    if not stored.exists():
        abort(404)
    return send_file(str(stored), as_attachment=True, download_name=f.original_filename)


@app.route("/files/<int:id>/view")
def file_view(id):
    f = db.get_or_404(AttachedFile, id)
    stored = Path(f.stored_path)
    if not stored.exists():
        abort(404)
    return send_file(
        str(stored), as_attachment=False, download_name=f.original_filename
    )


@app.route("/files/<int:id>/delete", methods=["POST"])
def file_delete(id):
    f = db.get_or_404(AttachedFile, id)
    run_id = f.workflow_run_id
    _delete_file(f.stored_path)
    db.session.delete(f)
    db.session.commit()
    flash(f'File "{f.original_filename}" deleted.', "success")
    return redirect(url_for("run_detail", id=run_id))


# ── Sample Sheets ─────────────────────────────────────────────────────────────


@app.route("/runs/<int:id>/samples/upload", methods=["POST"])
def sample_upload(id):
    run = db.get_or_404(WorkflowRun, id)

    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("run_detail", id=id))

    file = request.files["file"]
    original_name = secure_filename(file.filename)

    sample_dir = get_storage_path() / "runs" / str(id) / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    stored_path = sample_dir / f"{uuid.uuid4().hex}_{original_name}"
    file.save(str(stored_path))

    csv_data = _parse_csv(stored_path)

    if run.sample_sheet:
        _delete_file(run.sample_sheet.stored_path)
        db.session.delete(run.sample_sheet)
        db.session.flush()

    sheet = SampleSheet(
        workflow_run_id=id,
        original_filename=original_name,
        stored_path=str(stored_path),
        csv_data=csv_data,
    )
    db.session.add(sheet)
    db.session.commit()
    flash(f'Sample sheet "{original_name}" uploaded.', "success")
    return redirect(url_for("run_detail", id=id))


@app.route("/runs/<int:id>/samples/download")
def sample_download(id):
    run = db.get_or_404(WorkflowRun, id)
    if not run.sample_sheet:
        abort(404)
    stored = Path(run.sample_sheet.stored_path)
    if not stored.exists():
        abort(404)
    return send_file(
        str(stored),
        as_attachment=True,
        download_name=run.sample_sheet.original_filename,
    )


@app.route("/runs/<int:id>/samples/delete", methods=["POST"])
def sample_delete(id):
    run = db.get_or_404(WorkflowRun, id)
    if run.sample_sheet:
        _delete_file(run.sample_sheet.stored_path)
        db.session.delete(run.sample_sheet)
        db.session.commit()
        flash("Sample sheet deleted.", "success")
    return redirect(url_for("run_detail", id=id))


# ── Project Scripts ───────────────────────────────────────────────────────────


@app.route("/projects/<int:id>/scripts/upload", methods=["POST"])
def script_upload(id):
    project = db.get_or_404(Project, id)

    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("project_detail", id=id))

    file = request.files["file"]
    description = request.form.get("description", "").strip()

    original_name = secure_filename(file.filename)
    ext = Path(original_name).suffix.lower()
    language = (
        SCRIPT_LANGUAGES.get(ext)
        or SCRIPT_LANGUAGES.get(Path(original_name).suffix)
        or "Other"
    )

    script_dir = get_storage_path() / "projects" / str(id) / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    stored_path = script_dir / stored_name
    file.save(str(stored_path))

    script = ProjectScript(
        project_id=id,
        original_filename=original_name,
        stored_path=str(stored_path),
        language=language,
        description=description,
    )
    db.session.add(script)
    db.session.commit()
    flash(f'Script "{original_name}" uploaded.', "success")
    return redirect(url_for("project_detail", id=id))


@app.route("/scripts/<int:id>/download")
def script_download(id):
    script = db.get_or_404(ProjectScript, id)
    stored = Path(script.stored_path)
    if not stored.exists():
        abort(404)
    return send_file(
        str(stored), as_attachment=True, download_name=script.original_filename
    )


@app.route("/scripts/<int:id>")
def script_detail(id):
    script = db.get_or_404(ProjectScript, id)
    return render_template("scripts/detail.html", script=script)


@app.route("/scripts/<int:id>/delete", methods=["POST"])
def script_delete(id):
    script = db.get_or_404(ProjectScript, id)
    script.trashed = True
    db.session.commit()
    flash(f'Script "{script.original_filename}" moved to trash.', "success")
    return redirect(url_for("project_detail", id=script.project_id))


@app.route("/scripts/<int:id>/outputs/upload", methods=["POST"])
def script_output_upload(id):
    script = db.get_or_404(ProjectScript, id)

    if "file" not in request.files or request.files["file"].filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("script_detail", id=id))

    file = request.files["file"]
    description = request.form.get("description", "").strip()
    original_name = secure_filename(file.filename)

    out_dir = (
        get_storage_path()
        / "projects"
        / str(script.project_id)
        / "scripts"
        / str(id)
        / "outputs"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    stored_path = out_dir / stored_name
    file.save(str(stored_path))

    out = ScriptOutputFile(
        script_id=id,
        original_filename=original_name,
        stored_path=str(stored_path),
        description=description,
    )
    db.session.add(out)
    db.session.commit()
    flash(f'Output file "{original_name}" attached.', "success")
    return redirect(url_for("script_detail", id=id))


@app.route("/script-outputs/<int:id>/download")
def script_output_download(id):
    out = db.get_or_404(ScriptOutputFile, id)
    stored = Path(out.stored_path)
    if not stored.exists():
        abort(404)
    return send_file(
        str(stored), as_attachment=True, download_name=out.original_filename
    )


@app.route("/script-outputs/<int:id>/edit", methods=["POST"])
def script_output_edit(id):
    out = db.get_or_404(ScriptOutputFile, id)
    out.description = request.form.get("description", "").strip()
    db.session.commit()
    flash("Description updated.", "success")
    return redirect(url_for("script_detail", id=out.script_id))


@app.route("/script-outputs/<int:id>/delete", methods=["POST"])
def script_output_delete(id):
    out = db.get_or_404(ScriptOutputFile, id)
    script_id = out.script_id
    _delete_file(out.stored_path)
    db.session.delete(out)
    db.session.commit()
    flash(f'Output file "{out.original_filename}" deleted.', "success")
    return redirect(url_for("script_detail", id=script_id))


# ── Trash ─────────────────────────────────────────────────────────────────────

_TRASH_MODELS = {
    "group": ResearchGroup,
    "researcher": Researcher,
    "project": Project,
    "run": WorkflowRun,
    "script": ProjectScript,
}


@app.route("/trash")
def trash():
    items = {
        "groups": ResearchGroup.query.filter_by(trashed=True)
        .order_by(ResearchGroup.name)
        .all(),
        "researchers": Researcher.query.filter_by(trashed=True)
        .order_by(Researcher.name)
        .all(),
        "projects": Project.query.filter_by(trashed=True).order_by(Project.name).all(),
        "runs": WorkflowRun.query.filter_by(trashed=True)
        .order_by(WorkflowRun.run_date.desc())
        .all(),
        "scripts": ProjectScript.query.filter_by(trashed=True)
        .order_by(ProjectScript.original_filename)
        .all(),
    }
    total = sum(len(v) for v in items.values())
    return render_template("trash.html", items=items, total=total)


@app.route("/trash/<type>/<int:id>/restore", methods=["POST"])
def trash_restore(type, id):
    model = _TRASH_MODELS.get(type)
    if not model:
        abort(404)
    record = db.get_or_404(model, id)
    record.trashed = False
    db.session.commit()
    flash("Record restored.", "success")
    return redirect(url_for("trash"))


@app.route("/trash/<type>/<int:id>/delete", methods=["POST"])
def trash_delete(type, id):
    model = _TRASH_MODELS.get(type)
    if not model:
        abort(404)
    record = db.get_or_404(model, id)
    _trash_hard_delete(type, record)
    flash("Record permanently deleted.", "success")
    return redirect(url_for("trash"))


@app.route("/trash/empty", methods=["POST"])
def trash_empty():
    for type_key, model in _TRASH_MODELS.items():
        for record in model.query.filter_by(trashed=True).all():
            _trash_hard_delete(type_key, record)
    flash("Trash emptied.", "success")
    return redirect(url_for("trash"))


def _trash_hard_delete(type_key: str, record) -> None:
    if type_key == "group":
        _delete_group_files(record)
    elif type_key == "researcher":
        for p in record.projects:
            for run in p.workflow_runs:
                _delete_run_files(run)
            for script in p.scripts:
                _delete_file(script.stored_path)
                for out in script.output_files:
                    _delete_file(out.stored_path)
    elif type_key == "project":
        for run in record.workflow_runs:
            _delete_run_files(run)
        for script in record.scripts:
            _delete_file(script.stored_path)
            for out in script.output_files:
                _delete_file(out.stored_path)
    elif type_key == "run":
        _delete_run_files(record)
    elif type_key == "script":
        for out in record.output_files:
            _delete_file(out.stored_path)
        _delete_file(record.stored_path)
    db.session.delete(record)
    db.session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_csv(path: Path) -> str | None:
    """Parse a CSV file and return its rows as a JSON list-of-lists."""
    import csv

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        return json.dumps(rows)
    except Exception:
        return None


def _parse_snakemake_config(path: Path) -> str | None:
    """Parse a Snakemake YAML config, drop the 'resources' section, return as JSON."""
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


def _delete_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _delete_run_files(run: WorkflowRun) -> None:
    for f in run.attached_files:
        _delete_file(f.stored_path)


def _total_file_size() -> int:
    """Return total bytes for all stored files across all three file tables."""
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


if __name__ == "__main__":
    port = int(os.environ.get("NGS_PORT", 5000))
    host = os.environ.get("NGS_HOST", "127.0.0.1")
    app.run(debug=False, host=host, port=port)
