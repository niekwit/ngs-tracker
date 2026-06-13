import json

from flask import flash, redirect, render_template, request, url_for

from config import db_log
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

        # GET — determine which column to use for sample names
        col = request.args.get("col", 0, type=int)
        col = max(0, min(col, len(headers) - 1))

        # Deduplicate while preserving order
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
            already_linked=already_linked,
            project_samples=project_samples,
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
