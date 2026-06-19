import uuid
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from config import db_log, get_storage_path, resolve_stored_path
from helpers import (
    _delete_file,
    _parse_csv,
    _parse_mapping_rates,
    _parse_snakemake_config,
    _parse_snakemake_log,
)
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
        parsed_runtime = None
        new_log_paths = []
        for file in files:
            original_name = secure_filename(file.filename)
            stored_path = run_dir / f"{uuid.uuid4().hex}_{original_name}"
            file.save(str(stored_path))

            if file_type == "config":
                parsed_config = _parse_snakemake_config(stored_path)
            elif file_type == "mapping_rates":
                parsed_config = _parse_mapping_rates(stored_path)
            elif file_type == "snakemake_log":
                parsed_config = None
                new_log_paths.append(stored_path)
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
                f"{original_name} [{file_type}] on run id={id}",
            )
            saved.append(original_name)

        if new_log_paths:
            all_log_files = AttachedFile.query.filter_by(
                workflow_run_id=id, file_type="snakemake_log"
            ).all()
            total = sum(
                s for f in all_log_files
                if (s := _parse_snakemake_log(Path(f.stored_path))) is not None
            )
            if total > 0:
                run.runtime_seconds = total
                parsed_runtime = total

        db.session.commit()
        label = f'File "{saved[0]}"' if len(saved) == 1 else f"{len(saved)} files"
        msg = f"{label} uploaded."
        if parsed_runtime is not None:
            msg += f" Runtime parsed: {run.runtime_display}."
        flash(msg, "success")
        return redirect(url_for("run_detail", id=id))

    @app.route("/files/<int:id>/download")
    def file_download(id):
        f = db.get_or_404(AttachedFile, id)
        stored = resolve_stored_path(f.stored_path)
        if not stored.exists():
            abort(404)
        return send_file(
            str(stored), as_attachment=True, download_name=f.original_filename
        )

    @app.route("/files/<int:id>/view")
    def file_view(id):
        f = db.get_or_404(AttachedFile, id)
        stored = resolve_stored_path(f.stored_path)
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

    @app.route("/files/<int:id>/edit", methods=["POST"])
    def file_edit(id):
        f = db.get_or_404(AttachedFile, id)
        run_id = f.workflow_run_id
        new_name = request.form.get("original_filename", "").strip()
        if new_name:
            f.original_filename = new_name
        f.file_type = request.form.get("file_type", f.file_type)
        f.description = request.form.get("description", "").strip()
        db.session.commit()
        db_log("UPDATE", "AttachedFile", id, f"edited {f.original_filename} on run id={run_id}")
        flash(f'File "{f.original_filename}" updated.', "success")
        return redirect(url_for("run_detail", id=run_id))

    @app.route("/runs/<int:id>/files/batch-delete", methods=["POST"])
    def files_batch_delete(id):
        run = db.get_or_404(WorkflowRun, id)
        file_ids = request.form.getlist("file_ids", type=int)
        deleted = 0
        for fid in file_ids:
            f = db.session.get(AttachedFile, fid)
            if f and f.workflow_run_id == run.id:
                fname = f.original_filename
                _delete_file(f.stored_path)
                db.session.delete(f)
                db.session.flush()
                db_log("DELETE", "AttachedFile", fid, f"{fname} from run id={id}")
                deleted += 1
        db.session.commit()
        flash(f'{deleted} file{"s" if deleted != 1 else ""} deleted.', "success")
        return redirect(url_for("run_detail", id=id))

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
        stored = resolve_stored_path(run.sample_sheet.stored_path)
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
