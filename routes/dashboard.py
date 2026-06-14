import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from flask import flash, redirect, render_template, request, url_for

from config import (
    DEFAULT_DB,
    SETTINGS_FILE,
    add_backup_location,
    add_default_tag,
    add_user,
    db_log,
    get_api_key,
    get_backup_locations,
    get_current_user,
    get_default_tags,
    get_storage_path,
    get_users,
    is_configured,
    load_settings,
    remove_backup_location,
    remove_default_tag,
    remove_user,
    rotate_api_key,
    save_settings,
    set_current_user,
)
from helpers import _format_file_size, _total_file_size
from models import (
    FILE_TYPES,
    AttachedFile,
    Project,
    ProjectScript,
    ResearchGroup,
    Researcher,
    ScriptOutputFile,
    WorkflowRun,
    db,
)


def register(app):
    @app.route("/")
    def index():
        groups = (
            ResearchGroup.query.filter_by(trashed=False)
            .order_by(ResearchGroup.name)
            .all()
        )
        recent_runs = (
            WorkflowRun.query.filter_by(trashed=False)
            .order_by(WorkflowRun.run_date.desc())
            .limit(8)
            .all()
        )
        file_type_counts = {
            label: AttachedFile.query.filter_by(file_type=key).count()
            for key, (label, _) in FILE_TYPES.items()
        }
        file_type_counts["Scripts"] = ProjectScript.query.count()
        file_type_counts["Script Outputs"] = ScriptOutputFile.query.count()
        file_type_counts = {k: v for k, v in file_type_counts.items() if v > 0}

        # Status breakdown + backup coverage
        all_runs = WorkflowRun.query.filter_by(trashed=False).all()
        status_counts = defaultdict(int)
        for r in all_runs:
            status_counts[r.status] += 1
        status_data = {
            "Completed": status_counts.get("completed", 0),
            "Running": status_counts.get("running", 0),
            "Pending": status_counts.get("pending", 0),
            "Failed": status_counts.get("failed", 0),
        }
        status_urls = {
            "Completed": url_for("runs_list", status="completed"),
            "Running": url_for("runs_list", status="running"),
            "Pending": url_for("runs_list", status="pending"),
            "Failed": url_for("runs_list", status="failed"),
        }

        n_runs = len(all_runs)
        n_backup = sum(1 for r in all_runs if r.backups_list)
        backup_pct = round(n_backup / n_runs * 100) if n_runs else 0
        backup_by_loc = defaultdict(int)
        for r in all_runs:
            for b in r.backups_list:
                backup_by_loc[b["location"]] += 1
        backup_locations = get_backup_locations()

        # Timeline: runs per month for the last 12 months
        now = datetime.utcnow()
        months = []
        for i in range(11, -1, -1):
            month_num = now.month - i
            year = now.year + (month_num - 1) // 12
            month = ((month_num - 1) % 12) + 1
            months.append(f"{year:04d}-{month:02d}")

        timeline_counts = defaultdict(int)
        for run in WorkflowRun.query.filter_by(trashed=False).all():
            key = run.run_date.strftime("%Y-%m")
            if key in months:
                timeline_counts[key] += 1
        timeline_data = {m: timeline_counts[m] for m in months}

        stats = {
            "groups": ResearchGroup.query.filter_by(trashed=False).count(),
            "researchers": Researcher.query.filter_by(trashed=False).count(),
            "projects": Project.query.filter_by(trashed=False).count(),
            "runs": WorkflowRun.query.filter_by(trashed=False).count(),
            "files": AttachedFile.query.count()
            + ProjectScript.query.count()
            + ScriptOutputFile.query.count(),
            "file_size": _format_file_size(_total_file_size()),
        }
        return render_template(
            "index.html",
            groups=groups,
            recent_runs=recent_runs,
            stats=stats,
            file_type_counts=json.dumps(file_type_counts),
            timeline_data=json.dumps(timeline_data),
            status_data=json.dumps(status_data),
            status_urls=json.dumps(status_urls),
            backup_pct=backup_pct,
            backup_by_loc=backup_by_loc,
            backup_locations=backup_locations,
            n_backup=n_backup,
            n_runs=n_runs,
        )

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if request.method == "POST":
            action = request.form.get("action", "")

            if action == "add_user":
                name = request.form.get("username", "").strip()
                if not name:
                    flash("User name is required.", "danger")
                elif name in get_users():
                    flash(f'User "{name}" already exists.', "warning")
                else:
                    add_user(name)
                    set_current_user(name)
                    flash(f'User "{name}" added and selected.', "success")
                return redirect(url_for("setup"))

            if action == "remove_user":
                name = request.form.get("username", "")
                remove_user(name)
                flash(f'User "{name}" removed.', "success")
                return redirect(url_for("setup"))

            if action == "set_user":
                name = request.form.get("username", "")
                set_current_user(name)
                flash(f'Switched to "{name}".', "success")
                return redirect(url_for("setup"))

            if action == "add_tag":
                name = request.form.get("tag_name", "").strip()
                if not name:
                    flash("Tag name is required.", "danger")
                elif name in get_default_tags():
                    flash(f'Tag "{name}" already exists.', "warning")
                else:
                    add_default_tag(name)
                    flash(f'Tag "{name}" added.', "success")
                return redirect(url_for("setup"))

            if action == "remove_tag":
                name = request.form.get("tag_name", "")
                remove_default_tag(name)
                flash(f'Tag "{name}" removed from defaults.', "success")
                return redirect(url_for("setup"))

            if action == "add_backup_loc":
                name = request.form.get("loc_name", "").strip()
                loc_type = request.form.get("loc_type", "remote")
                if not name:
                    flash("Location name is required.", "danger")
                elif name in [l["name"] for l in get_backup_locations()]:
                    flash(f'"{name}" already exists.', "warning")
                else:
                    add_backup_location(name, loc_type)
                    flash(f'Backup location "{name}" added.', "success")
                return redirect(url_for("setup"))

            if action == "remove_backup_loc":
                name = request.form.get("loc_name", "")
                remove_backup_location(name)
                flash(f'Backup location "{name}" removed.', "success")
                return redirect(url_for("setup"))

            if action == "rotate_api_key":
                rotate_api_key()
                flash(
                    "API key rotated. Update any scripts using the old key.", "success"
                )
                return redirect(url_for("setup"))

            # Storage settings
            storage_path = request.form.get("storage_path", "").strip()
            db_path = request.form.get("db_path", "").strip()
            if not storage_path or not db_path:
                flash("Both paths are required.", "danger")
                return redirect(url_for("setup"))
            try:
                Path(storage_path).mkdir(parents=True, exist_ok=True)
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                flash(f"Could not create directories: {e}", "danger")
                return redirect(url_for("setup"))
            save_settings({"storage_path": storage_path, "db_path": db_path})
            flash(
                "Settings saved. Restart the server for the database path to take effect.",
                "success",
            )
            return redirect(url_for("index"))

        settings = load_settings()
        defaults = {
            "storage_path": settings.get("storage_path", str(get_storage_path())),
            "db_path": settings.get("db_path", str(DEFAULT_DB)),
        }
        return render_template(
            "setup.html",
            settings=defaults,
            settings_file=str(SETTINGS_FILE),
            users=get_users(),
            current_user=get_current_user(),
            default_tags=get_default_tags(),
            backup_locations=get_backup_locations(),
            api_key=get_api_key(),
        )
