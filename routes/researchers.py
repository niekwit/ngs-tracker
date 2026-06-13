from flask import flash, redirect, render_template, request, url_for

from config import db_log
from helpers import _format_file_size, _project_disk_bytes
from models import ResearchGroup, Researcher, db


def register(app):
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

    @app.route("/researchers/<int:id>")
    def researcher_detail(id):
        researcher = db.get_or_404(Researcher, id)
        project_sizes = {
            p.id: _format_file_size(_project_disk_bytes(p))
            for p in researcher.projects
            if not p.trashed
        }
        return render_template(
            "researchers/detail.html",
            researcher=researcher,
            project_sizes=project_sizes,
        )

    @app.route("/researchers/new", methods=["GET", "POST"])
    def researcher_new():
        groups = (
            ResearchGroup.query.filter_by(trashed=False)
            .order_by(ResearchGroup.name)
            .all()
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
            db_log(
                "CREATE",
                "Researcher",
                researcher.id,
                f"{researcher.name} (group: {researcher.group.name})",
            )
            flash(f'Researcher "{name}" created.', "success")
            return redirect(url_for("researcher_detail", id=researcher.id))

        return render_template(
            "researchers/form.html",
            researcher=None,
            groups=groups,
            preselected=preselected,
        )

    @app.route("/researchers/<int:id>/edit", methods=["GET", "POST"])
    def researcher_edit(id):
        researcher = db.get_or_404(Researcher, id)
        groups = (
            ResearchGroup.query.filter_by(trashed=False)
            .order_by(ResearchGroup.name)
            .all()
        )
        if request.method == "POST":
            researcher.name = request.form.get("name", "").strip()
            researcher.email = request.form.get("email", "").strip()
            researcher.group_id = request.form.get("group_id", type=int)
            db.session.commit()
            db_log("UPDATE", "Researcher", id, researcher.name)
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
        db_log("TRASH", "Researcher", researcher.id, researcher.name)
        flash(f'Researcher "{researcher.name}" moved to trash.', "success")
        return redirect(url_for("group_detail", id=researcher.group_id))
