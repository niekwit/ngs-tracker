import json

from flask import flash, redirect, render_template, request, url_for

from config import db_log
from helpers import extract_samples_from_config, extract_samples_from_sample_info
from models import RunSample, Sample, WorkflowRun, db


def register(app):
    @app.route("/runs/<int:id>/samples/confirm", methods=["GET", "POST"])
    def sample_confirm(id):
        run = db.get_or_404(WorkflowRun, id)

        if not run.sample_sheet or not run.sample_sheet.csv_data:
            flash("No sample sheet found for this run.", "warning")
            return redirect(url_for("run_detail", id=id))

        rows = json.loads(run.sample_sheet.csv_data)
        if len(rows) < 2:
            flash("Sample sheet has no data rows.", "warning")
            return redirect(url_for("run_detail", id=id))

        headers = rows[0]
        data_rows = rows[1:]

        if request.method == "POST":
            # Collect confirmed selections
            names_to_link = []
            for i in range(len(data_rows)):
                if request.form.get(f"include_{i}"):
                    name = request.form.get(f"name_{i}", "").strip()
                    if name:
                        names_to_link.append(name)

            # Remove existing RunSample links for this run before re-linking
            RunSample.query.filter_by(run_id=id).delete()
            db.session.flush()

            project = run.project
            existing = {s.name: s for s in project.samples}

            for name in names_to_link:
                if name in existing:
                    sample = existing[name]
                else:
                    sample = Sample(project_id=project.id, name=name)
                    db.session.add(sample)
                    db.session.flush()
                    existing[name] = sample
                    db_log(
                        "CREATE",
                        "Sample",
                        sample.id,
                        f"{name} (project: {project.name})",
                    )

                rs = RunSample(run_id=id, sample_id=sample.id)
                db.session.add(rs)

            db.session.commit()
            n = len(names_to_link)
            flash(f"{n} sample{'s' if n != 1 else ''} linked to this run.", "success")
            return redirect(url_for("run_detail", id=id))

        # If both 'test' and 'control' columns exist, combine them automatically
        # (splitting semicolon-pooled entries) and skip the column picker.
        combined = "test" in headers and "control" in headers
        if combined:
            test_idx = headers.index("test")
            ctrl_idx = headers.index("control")
            seen = set()
            extracted = []
            for row in data_rows:
                for idx in (test_idx, ctrl_idx):
                    for name in (row[idx] if idx < len(row) else "").split(";"):
                        name = name.strip()
                        if name and name not in seen:
                            seen.add(name)
                            extracted.append(name)
            col = None
        else:
            col = request.args.get("col", 0, type=int)
            col = max(0, min(col, len(headers) - 1))
            seen = set()
            extracted = []
            for row in data_rows:
                val = row[col].strip() if col < len(row) else ""
                if val and val not in seen:
                    seen.add(val)
                    extracted.append(val)

        # Already-linked samples for this run
        already_linked = {rs.sample.name for rs in run.run_samples}
        # Existing samples in this project (for match highlighting)
        project_samples = {s.name: s for s in run.project.samples}

        return render_template(
            "runs/sample_confirm.html",
            run=run,
            headers=headers,
            extracted=extracted,
            col=col,
            combined=combined,
            already_linked=already_linked,
            project_samples=project_samples,
        )

    @app.route("/runs/<int:id>/samples/from-config", methods=["GET", "POST"])
    def samples_from_config(id):
        run = db.get_or_404(WorkflowRun, id)

        candidates = None
        for f in run.attached_files:
            if f.file_type == "config" and f.config_dict:
                candidates = extract_samples_from_config(run.workflow_name, f.config_dict)
                if candidates:
                    break

        if not candidates:
            flash("No extractable sample data found in the config for this workflow.", "warning")
            return redirect(url_for("run_detail", id=id))

        if request.method == "POST":
            RunSample.query.filter_by(run_id=id).delete()
            db.session.flush()

            project = run.project
            existing = {s.name: s for s in project.samples}
            linked = 0

            for i, c in enumerate(candidates):
                if not request.form.get(f"include_{i}"):
                    continue
                name = request.form.get(f"name_{i}", c["name"]).strip()
                description = request.form.get(f"desc_{i}", c["description"]).strip()
                if not name:
                    continue
                if name in existing:
                    sample = existing[name]
                    if description and sample.description != description:
                        sample.description = description
                else:
                    sample = Sample(project_id=project.id, name=name, description=description)
                    db.session.add(sample)
                    db.session.flush()
                    existing[name] = sample
                    db_log("CREATE", "Sample", sample.id, f"{name} (project: {project.name})")
                rs = RunSample(run_id=id, sample_id=sample.id)
                db.session.add(rs)
                linked += 1

            db.session.commit()
            flash(f"{linked} sample{'s' if linked != 1 else ''} linked from config.", "success")
            return redirect(url_for("run_detail", id=id))

        already_linked = {rs.sample.name for rs in run.run_samples}
        return render_template(
            "runs/sample_from_config.html",
            run=run,
            candidates=candidates,
            already_linked=already_linked,
            page_title="Samples from Config",
            source_desc="the uploaded config file",
            confirm_url=url_for("samples_from_config", id=id),
        )

    @app.route("/runs/<int:id>/samples/from-sample-info", methods=["GET", "POST"])
    def samples_from_sample_info(id):
        run = db.get_or_404(WorkflowRun, id)

        candidates = None
        for f in run.attached_files:
            if f.file_type == "sample_info":
                from pathlib import Path as _Path
                from config import resolve_stored_path
                stored = resolve_stored_path(f.stored_path)
                if stored.exists():
                    candidates = extract_samples_from_sample_info(run.workflow_name, stored)
                    if candidates:
                        break

        if not candidates:
            flash("No extractable sample data found in the sample info file for this workflow.", "warning")
            return redirect(url_for("run_detail", id=id))

        if request.method == "POST":
            RunSample.query.filter_by(run_id=id).delete()
            db.session.flush()

            project = run.project
            existing = {s.name: s for s in project.samples}
            linked = 0

            for i, c in enumerate(candidates):
                if not request.form.get(f"include_{i}"):
                    continue
                name = request.form.get(f"name_{i}", c["name"]).strip()
                description = request.form.get(f"desc_{i}", c["description"]).strip()
                if not name:
                    continue
                if name in existing:
                    sample = existing[name]
                    if description and sample.description != description:
                        sample.description = description
                else:
                    sample = Sample(project_id=project.id, name=name, description=description)
                    db.session.add(sample)
                    db.session.flush()
                    existing[name] = sample
                    db_log("CREATE", "Sample", sample.id, f"{name} (project: {project.name})")
                rs = RunSample(run_id=id, sample_id=sample.id)
                db.session.add(rs)
                linked += 1

            db.session.commit()
            flash(f"{linked} sample{'s' if linked != 1 else ''} linked from sample info.", "success")
            return redirect(url_for("run_detail", id=id))

        already_linked = {rs.sample.name for rs in run.run_samples}
        return render_template(
            "runs/sample_from_config.html",
            run=run,
            candidates=candidates,
            already_linked=already_linked,
            page_title="Samples from Sample Info",
            source_desc="the uploaded sample info file",
            confirm_url=url_for("samples_from_sample_info", id=id),
        )

    @app.route("/samples/<int:id>")
    def sample_detail(id):
        sample = db.get_or_404(Sample, id)
        return render_template("samples/detail.html", sample=sample)

    @app.route("/samples/<int:id>/rename", methods=["POST"])
    def sample_rename(id):
        sample = db.get_or_404(Sample, id)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("sample_detail", id=id))
        old = sample.name
        sample.name = name
        db.session.commit()
        db_log("UPDATE", "Sample", id, f"{old} → {name}")
        flash(f'Sample renamed to "{name}".', "success")
        return redirect(url_for("sample_detail", id=id))

    @app.route("/samples/<int:id>/delete", methods=["POST"])
    def sample_delete(id):
        sample = db.get_or_404(Sample, id)
        project_id = sample.project_id
        db_log("DELETE", "Sample", id, sample.name)
        db.session.delete(sample)
        db.session.commit()
        flash(f'Sample "{sample.name}" deleted.', "success")
        return redirect(url_for("project_detail", id=project_id))
