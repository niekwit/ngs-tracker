import os
import threading
import time

from flask import flash, redirect, render_template, request, url_for

from config import SETTINGS_DIR, db_log, load_workflows, save_workflows
from models import Project, ProjectScript, ResearchGroup, Researcher, WorkflowRun, db


def register(app):
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

        return render_template("workflows/manage.html", workflows=load_workflows())

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

    @app.route("/restart", methods=["POST"])
    def restart():
        def _exit():
            time.sleep(0.3)
            (SETTINGS_DIR / ".restart").touch()
            os._exit(0)

        threading.Thread(target=_exit, daemon=True).start()
        return "", 204

    @app.route("/stop", methods=["POST"])
    def stop():
        def _exit():
            time.sleep(0.3)
            os._exit(0)

        threading.Thread(target=_exit, daemon=True).start()
        return "", 204
