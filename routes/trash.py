from flask import abort, flash, redirect, render_template, url_for

from config import db_log
from helpers import _delete_file, _delete_group_files, _delete_run_files
from models import Project, ProjectScript, ResearchGroup, Researcher, WorkflowRun, db

_TRASH_MODELS = {
    "group": ResearchGroup,
    "researcher": Researcher,
    "project": Project,
    "run": WorkflowRun,
    "script": ProjectScript,
}


def _trash_label(type_key: str, record) -> str:
    if type_key in ("group", "researcher", "project"):
        return record.name
    if type_key == "run":
        return record.workflow_name
    if type_key == "script":
        return record.original_filename
    return str(record.id)


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


def register(app):
    @app.route("/trash")
    def trash():
        items = {
            "groups": ResearchGroup.query.filter_by(trashed=True)
            .order_by(ResearchGroup.name)
            .all(),
            "researchers": Researcher.query.filter_by(trashed=True)
            .order_by(Researcher.name)
            .all(),
            "projects": Project.query.filter_by(trashed=True)
            .order_by(Project.name)
            .all(),
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
        db_log("RESTORE", model.__name__, id, _trash_label(type, record))
        flash("Record restored.", "success")
        return redirect(url_for("trash"))

    @app.route("/trash/<type>/<int:id>/delete", methods=["POST"])
    def trash_delete(type, id):
        model = _TRASH_MODELS.get(type)
        if not model:
            abort(404)
        record = db.get_or_404(model, id)
        label = _trash_label(type, record)
        _trash_hard_delete(type, record)
        db_log("DELETE", model.__name__, id, f"{label} (permanent)")
        flash("Record permanently deleted.", "success")
        return redirect(url_for("trash"))

    @app.route("/trash/empty", methods=["POST"])
    def trash_empty():
        for type_key, model in _TRASH_MODELS.items():
            for record in model.query.filter_by(trashed=True).all():
                label = _trash_label(type_key, record)
                rec_id = record.id
                _trash_hard_delete(type_key, record)
                db_log("DELETE", model.__name__, rec_id, f"{label} (permanent)")
        flash("Trash emptied.", "success")
        return redirect(url_for("trash"))
