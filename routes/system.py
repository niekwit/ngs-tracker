import os
import threading
import time

from flask import flash, redirect, render_template, request, url_for

from config import LOG_FILE, SETTINGS_DIR, db_log, load_workflows, save_workflows
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

    @app.route("/log")
    def log_viewer():
        f_user = request.args.get("user", "").strip()
        f_action = request.args.get("action", "").strip()
        f_search = request.args.get("search", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = 100

        entries = []
        if LOG_FILE.exists():
            with open(LOG_FILE) as fh:
                for line in fh:
                    line = line.rstrip("\n")
                    parts = line.split(" | ", 5)
                    if len(parts) < 5:
                        continue
                    entry = {
                        "ts": parts[0].strip(),
                        "action": parts[1].strip(),
                        "model": parts[2].strip(),
                        "record_id": parts[3].replace("id=", "").strip(),
                        "user": parts[4].replace("user=", "").strip(),
                        "detail": parts[5].strip() if len(parts) > 5 else "",
                    }
                    entries.append(entry)

        entries.reverse()

        all_users = sorted(
            {e["user"] for e in entries if e["user"] and e["user"] != "—"}
        )
        all_actions = sorted({e["action"] for e in entries})

        if f_user:
            entries = [e for e in entries if e["user"] == f_user]
        if f_action:
            entries = [e for e in entries if e["action"] == f_action]
        if f_search:
            s = f_search.lower()
            entries = [
                e
                for e in entries
                if s in e["detail"].lower()
                or s in e["model"].lower()
                or s in e["record_id"].lower()
            ]

        total = len(entries)
        pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, pages))
        entries = entries[(page - 1) * per_page : page * per_page]

        return render_template(
            "log.html",
            entries=entries,
            total=total,
            page=page,
            pages=pages,
            per_page=per_page,
            f_user=f_user,
            f_action=f_action,
            f_search=f_search,
            all_users=all_users,
            all_actions=all_actions,
        )

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
