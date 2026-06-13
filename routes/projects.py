from flask import flash, redirect, render_template, request, url_for

from config import db_log
from helpers import _format_file_size, _project_disk_bytes
from models import SCRIPT_LANGUAGES, Project, ResearchGroup, Researcher, db


def register(app):
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

    @app.route("/projects/<int:id>")
    def project_detail(id):
        project = db.get_or_404(Project, id)
        disk_usage = _format_file_size(_project_disk_bytes(project))
        return render_template(
            "projects/detail.html",
            project=project,
            script_languages=SCRIPT_LANGUAGES,
            disk_usage=disk_usage,
        )

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
            db_log(
                "CREATE",
                "Project",
                project.id,
                f"{project.name} (researcher: {project.researcher.name})",
            )
            flash(f'Project "{name}" created.', "success")
            return redirect(url_for("project_detail", id=project.id))

        return render_template(
            "projects/form.html",
            project=None,
            researchers=researchers,
            preselected=preselected,
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
            db_log("UPDATE", "Project", id, project.name)
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
        db_log("TRASH", "Project", project.id, project.name)
        flash(f'Project "{project.name}" moved to trash.', "success")
        return redirect(url_for("researcher_detail", id=project.researcher_id))
