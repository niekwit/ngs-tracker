import os
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import flash, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from config import (
    LOG_FILE,
    SETTINGS_DIR,
    WORKFLOW_SYSTEMS,
    WORKFLOWS_FILE,
    add_run_template,
    delete_run_template,
    db_log,
    load_run_templates,
    load_workflows,
    save_workflows,
)
from models import (
    Project,
    ProjectScript,
    ResearchGroup,
    Researcher,
    Sample,
    WorkflowRun,
    db,
)


def _notes_snippet(notes: str, query: str, window: int = 140) -> Markup | None:
    """Return an HTML-safe excerpt from notes around the first query match, with <mark> highlight."""
    if not notes or not query:
        return None
    lower_notes = notes.lower()
    lower_query = query.lower()
    idx = lower_notes.find(lower_query)
    if idx == -1:
        return None
    half = window // 2
    start = max(0, idx - half)
    end = min(len(notes), idx + len(query) + half)
    excerpt = notes[start:end]
    prefix = Markup("&hellip;") if start > 0 else Markup("")
    suffix = Markup("&hellip;") if end < len(notes) else Markup("")
    match_start = idx - start
    match_end = match_start + len(query)
    return (
        prefix
        + escape(excerpt[:match_start])
        + Markup("<mark>")
        + escape(excerpt[match_start:match_end])
        + Markup("</mark>")
        + escape(excerpt[match_end:])
        + suffix
    )


def register(app):
    @app.route("/workflows", methods=["GET", "POST"])
    def workflows_manage():
        if request.method == "POST":
            action = request.form.get("action")
            workflows = load_workflows()

            if action == "add":
                name = request.form.get("name", "").strip()
                url = request.form.get("url", "").strip()
                local_path = request.form.get("local_path", "").strip()
                system = request.form.get("system", "snakemake")
                if system not in WORKFLOW_SYSTEMS:
                    system = "other"
                try:
                    cutoff = float(request.form.get("mapping_rate_cutoff", "60"))
                    cutoff = max(0.0, min(100.0, cutoff))
                except ValueError:
                    cutoff = 60.0
                if not name:
                    flash("Workflow name is required.", "danger")
                elif not url and not local_path:
                    flash("Provide a GitHub URL, a local repo path, or both.", "danger")
                elif local_path and not Path(local_path).is_dir():
                    flash(f"Local path not found: {local_path}", "danger")
                elif any(w["name"] == name for w in workflows):
                    flash(f'Workflow "{name}" already exists.', "warning")
                else:
                    workflows.append(
                        {
                            "name": name,
                            "url": url,
                            "local_path": local_path,
                            "system": system,
                            "mapping_rate_cutoff": cutoff,
                        }
                    )
                    workflows.sort(key=lambda w: w["name"].lower())
                    save_workflows(workflows)
                    flash(f'Workflow "{name}" added.', "success")

            elif action == "update_cutoff":
                name = request.form.get("name", "")
                try:
                    cutoff = float(request.form.get("mapping_rate_cutoff", "60"))
                    cutoff = max(0.0, min(100.0, cutoff))
                except ValueError:
                    cutoff = 60.0
                for wf in workflows:
                    if wf["name"] == name:
                        wf["mapping_rate_cutoff"] = cutoff
                        break
                save_workflows(workflows)
                flash(f'Cutoff for "{name}" updated to {cutoff}%.', "success")

            elif action == "delete":
                name = request.form.get("name", "")
                workflows = [w for w in workflows if w["name"] != name]
                save_workflows(workflows)
                flash(f'Workflow "{name}" removed.', "success")

        return render_template(
            "workflows/manage.html",
            workflows=load_workflows(),
            templates=load_run_templates(),
            workflow_systems=WORKFLOW_SYSTEMS,
            workflows_file=str(WORKFLOWS_FILE),
        )

    @app.route("/templates/save", methods=["POST"])
    def template_save():
        run_id = request.form.get("run_id", type=int)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Template name is required.", "danger")
            return redirect(url_for("run_detail", id=run_id))
        run = db.get_or_404(WorkflowRun, run_id)
        add_run_template(
            {
                "id": uuid.uuid4().hex[:8],
                "name": name,
                "workflow_name": run.workflow_name,
                "workflow_tag": run.workflow_tag or "",
                "description": run.description or "",
                "created_at": datetime.utcnow().strftime("%Y-%m-%d"),
            }
        )
        flash(f'Template "{name}" saved.', "success")
        return redirect(url_for("run_detail", id=run_id))

    @app.route("/templates/<tid>/delete", methods=["POST"])
    def template_delete(tid):
        delete_run_template(tid)
        flash("Template deleted.", "success")
        return redirect(url_for("workflows_manage"))

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
                | WorkflowRun.tags.ilike(like)
                | WorkflowRun.notes.ilike(like),
            )
            .order_by(WorkflowRun.run_date.desc())
            .all(),
            "scripts": ProjectScript.query.filter(
                ProjectScript.trashed == False,
                ProjectScript.original_filename.ilike(like)
                | ProjectScript.description.ilike(like),
            ).all(),
            "samples": Sample.query.filter(
                Sample.name.ilike(like) | Sample.description.ilike(like),
            ).all(),
        }
        notes_snippets = {
            run.id: _notes_snippet(run.notes, q)
            for run in results["runs"]
            if run.notes and q.lower() in run.notes.lower()
        }
        total = sum(len(v) for v in results.values())
        return render_template(
            "search.html",
            q=q,
            results=results,
            total=total,
            notes_snippets=notes_snippets,
        )

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

    @app.route("/workflows/<name>/tags")
    def workflow_tags(name):
        """Return git tags (or recent commits) for a workflow with a local_path set."""
        wf = next((w for w in load_workflows() if w["name"] == name), None)
        if not wf:
            return jsonify({"error": "Workflow not found"}), 404
        local_path = wf.get("local_path", "").strip()
        if not local_path:
            return jsonify({"error": "No local path configured for this workflow"}), 400
        if not Path(local_path).is_dir():
            return jsonify({"error": f"Local path not found: {local_path}"}), 400
        try:
            tag_result = subprocess.run(
                ["git", "-C", local_path, "tag", "--sort=-version:refname"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            tags = [t.strip() for t in tag_result.stdout.splitlines() if t.strip()]
            if tags:
                return jsonify({"type": "tags", "items": tags})

            # No tags — fall back to recent commits
            log_result = subprocess.run(
                [
                    "git",
                    "-C",
                    local_path,
                    "log",
                    "--oneline",
                    "-10",
                    "--format=%H\t%as\t%s",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            commits = []
            for line in log_result.stdout.splitlines():
                parts = line.split("\t", 2)
                if len(parts) == 3:
                    commits.append(
                        {
                            "sha": parts[0][:7],
                            "date": parts[1],
                            "subject": parts[2][:80],
                        }
                    )
            return jsonify({"type": "commits", "items": commits})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

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
