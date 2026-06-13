from flask import flash, redirect, render_template, request, url_for

from config import db_log
from helpers import _delete_group_files, _format_file_size, _project_disk_bytes
from models import ResearchGroup, db


def register(app):
    @app.route("/groups")
    def groups_list():
        groups = (
            ResearchGroup.query.filter_by(trashed=False)
            .order_by(ResearchGroup.name)
            .all()
        )
        return render_template("groups/list.html", groups=groups)

    @app.route("/groups/<int:id>")
    def group_detail(id):
        group = db.get_or_404(ResearchGroup, id)
        researcher_sizes = {}
        for r in group.researchers:
            if not r.trashed:
                total = sum(_project_disk_bytes(p) for p in r.projects if not p.trashed)
                researcher_sizes[r.id] = _format_file_size(total)
        return render_template(
            "groups/detail.html", group=group, researcher_sizes=researcher_sizes
        )

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
            db_log("CREATE", "ResearchGroup", group.id, group.name)
            flash(f'Research group "{name}" created.', "success")
            return redirect(url_for("group_detail", id=group.id))
        return render_template("groups/form.html", group=None)

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
            db_log("UPDATE", "ResearchGroup", id, group.name)
            flash("Group updated.", "success")
            return redirect(url_for("group_detail", id=id))
        return render_template("groups/form.html", group=group)

    @app.route("/groups/<int:id>/delete", methods=["POST"])
    def group_delete(id):
        group = db.get_or_404(ResearchGroup, id)
        group.trashed = True
        db.session.commit()
        db_log("TRASH", "ResearchGroup", group.id, group.name)
        flash(f'Group "{group.name}" moved to trash.', "success")
        return redirect(url_for("groups_list"))
