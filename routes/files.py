import uuid
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from config import db_log, get_storage_path
from helpers import _delete_file, _parse_csv, _parse_snakemake_config
from models import FILE_TYPES, AttachedFile, SampleSheet, WorkflowRun, db


def register(app):
    @app.route("/runs/<int:id>/upload", methods=["POST"])
    def run_upload(id):
        run = db.get_or_404(WorkflowRun, id)

        files = [f for f in request.files.getlist("file") if f.filename]
        if not files:
            flash("No file selected.", "danger")
            return redirect(url_for("run_detail", id=id))

        file_type = request.form.get("file_type", "other")
        description = request.form.get("description", "").strip()
        run_dir = get_storage_path() / "runs" / str(id)
        run_dir.mkdir(parents=True, exist_ok=True)

        saved = []
        for file in files:
            original_name = secure_filename(file.filename)
            stored_path = run_dir / f"{uuid.uuid4().hex}_{original_name}"
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
            db.session.flush()
            db_log(
                "CREATE",
                "AttachedFile",
                attached.id,
                f"{original_name} [{file_type}] on run id={id}",
            )
            saved.append(original_name)

        db.session.commit()
        if len(saved) == 1:
            flash(f'File "{saved[0]}" uploaded.', "success")
        else:
            flash(f"{len(saved)} files uploaded.", "success")
        return redirect(url_for("run_detail", id=id))

    @app.route("/files/<int:id>/download")
    def file_download(id):
        f = db.get_or_404(AttachedFile, id)
        stored = Path(f.stored_path)
        if not stored.exists():
            abort(404)
        return send_file(
            str(stored), as_attachment=True, download_name=f.original_filename
        )

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
        fname = f.original_filename
        _delete_file(f.stored_path)
        db.session.delete(f)
        db.session.commit()
        db_log("DELETE", "AttachedFile", id, f"{fname} from run id={run_id}")
        flash(f'File "{fname}" deleted.', "success")
        return redirect(url_for("run_detail", id=run_id))

    # ── Sample sheets ─────────────────────────────────────────────────────────

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
        db_log("CREATE", "SampleSheet", sheet.id, f"{original_name} on run id={id}")
        flash(
            f'Sample sheet "{original_name}" uploaded — confirm samples below.',
            "success",
        )
        return redirect(url_for("sample_confirm", id=id))

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
    def sample_sheet_delete(id):
        run = db.get_or_404(WorkflowRun, id)
        if run.sample_sheet:
            sheet_id = run.sample_sheet.id
            fname = run.sample_sheet.original_filename
            _delete_file(run.sample_sheet.stored_path)
            db.session.delete(run.sample_sheet)
            db.session.commit()
            db_log("DELETE", "SampleSheet", sheet_id, f"{fname} from run id={id}")
            flash("Sample sheet deleted.", "success")
        return redirect(url_for("run_detail", id=id))
