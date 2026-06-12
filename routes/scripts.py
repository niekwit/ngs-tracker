import uuid
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from config import db_log, get_current_user, get_storage_path
from helpers import _delete_file
from models import SCRIPT_LANGUAGES, Project, ProjectScript, ScriptOutputFile, db


def register(app):
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
            created_by=get_current_user(),
        )
        db.session.add(script)
        db.session.commit()
        db_log(
            "CREATE",
            "ProjectScript",
            script.id,
            f"{original_name} ({language}) on project id={id}",
        )
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
        db_log("TRASH", "ProjectScript", script.id, script.original_filename)
        flash(f'Script "{script.original_filename}" moved to trash.', "success")
        return redirect(url_for("project_detail", id=script.project_id))

    # ── Script output files ───────────────────────────────────────────────────

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
        db_log(
            "CREATE", "ScriptOutputFile", out.id, f"{original_name} on script id={id}"
        )
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
        db_log(
            "UPDATE",
            "ScriptOutputFile",
            id,
            f"{out.original_filename} description updated",
        )
        flash("Description updated.", "success")
        return redirect(url_for("script_detail", id=out.script_id))

    @app.route("/script-outputs/<int:id>/delete", methods=["POST"])
    def script_output_delete(id):
        out = db.get_or_404(ScriptOutputFile, id)
        script_id = out.script_id
        fname = out.original_filename
        _delete_file(out.stored_path)
        db.session.delete(out)
        db.session.commit()
        db_log("DELETE", "ScriptOutputFile", id, f"{fname} from script id={script_id}")
        flash(f'Output file "{fname}" deleted.', "success")
        return redirect(url_for("script_detail", id=script_id))
