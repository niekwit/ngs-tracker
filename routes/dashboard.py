import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from backup import list_snapshots as _list_snapshots

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
    get_backup_reminder_days,
    get_current_user,
    get_default_tags,
    get_last_snapshot_time,
    get_slack_enabled,
    get_slack_runs_channel,
    get_slack_snapshot_channel,
    get_slack_token,
    get_snapshot_backup_dir,
    get_snapshot_interval_hours,
    get_snapshot_keep,
    get_storage_path,
    get_users,
    is_configured,
    load_settings,
    remove_backup_location,
    remove_default_tag,
    remove_user,
    rotate_api_key,
    save_settings,
    set_backup_reminder_days,
    set_current_user,
    set_slack_enabled,
    set_slack_runs_channel,
    set_slack_snapshot_channel,
    set_slack_token,
    set_snapshot_backup_dir,
    set_snapshot_interval_hours,
    set_snapshot_keep,
    set_tag_color,
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

        reminder_days = get_backup_reminder_days()
        if reminder_days > 0:
            cutoff = datetime.utcnow() - timedelta(days=reminder_days)
            no_backup_runs = sorted(
                [
                    r
                    for r in all_runs
                    if not r.backups_list
                    and r.run_date < cutoff
                    and r.status in ("completed", "failed")
                ],
                key=lambda r: r.run_date,
            )
        else:
            no_backup_runs = sorted(
                [
                    r
                    for r in all_runs
                    if not r.backups_list
                    and r.status in ("completed", "failed")
                ],
                key=lambda r: r.run_date,
            )
        unbackedup_runs = no_backup_runs

        n_runs = len(all_runs)
        n_backup = sum(1 for r in all_runs if r.backups_list)
        backup_pct = round(n_backup / n_runs * 100) if n_runs else 0
        backup_by_loc = defaultdict(int)
        for r in all_runs:
            for b in r.backups_list:
                backup_by_loc[b["location"]] += 1
        backup_locations = get_backup_locations()

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
            status_data=json.dumps(status_data),
            status_urls=json.dumps(status_urls),
            backup_pct=backup_pct,
            backup_by_loc=backup_by_loc,
            backup_locations=backup_locations,
            n_backup=n_backup,
            n_runs=n_runs,
            unbackedup_runs=unbackedup_runs,
            reminder_days=reminder_days,
            no_backup_runs=no_backup_runs,
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
                color = request.form.get("tag_color", "warning")
                if not name:
                    flash("Tag name is required.", "danger")
                elif name in [t["name"] for t in get_default_tags()]:
                    flash(f'Tag "{name}" already exists.', "warning")
                else:
                    add_default_tag(name, color)
                    flash(f'Tag "{name}" added.', "success")
                return redirect(url_for("setup"))

            if action == "remove_tag":
                name = request.form.get("tag_name", "")
                remove_default_tag(name)
                flash(f'Tag "{name}" removed from defaults.', "success")
                return redirect(url_for("setup"))

            if action == "set_tag_color":
                name = request.form.get("tag_name", "")
                color = request.form.get("tag_color", "warning")
                set_tag_color(name, color)
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

            if action == "set_backup_reminder":
                try:
                    days = max(0, int(request.form.get("reminder_days", 30)))
                except (ValueError, TypeError):
                    days = 30
                set_backup_reminder_days(days)
                if days == 0:
                    flash("Backup reminder disabled.", "success")
                else:
                    flash(f"Backup reminder set to {days} day(s).", "success")
                return redirect(url_for("setup"))

            if action == "set_snapshot_backup":
                bdir = request.form.get("snapshot_backup_dir", "").strip()
                try:
                    hours = max(0, int(request.form.get("snapshot_interval_hours", 0)))
                except (ValueError, TypeError):
                    hours = 0
                try:
                    keep = max(1, int(request.form.get("snapshot_keep", 10)))
                except (ValueError, TypeError):
                    keep = 10
                if bdir:
                    try:
                        Path(bdir).mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        flash(f"Could not create backup directory: {e}", "danger")
                        return redirect(url_for("setup"))
                set_snapshot_backup_dir(bdir)
                set_snapshot_interval_hours(hours)
                set_snapshot_keep(keep)
                if bdir and hours > 0:
                    flash(
                        f"Snapshot backup enabled: every {hours}h to {bdir}, keeping {keep} copies.",
                        "success",
                    )
                elif bdir:
                    flash(
                        f"Snapshot backup directory set to {bdir} (automatic schedule disabled).",
                        "success",
                    )
                else:
                    flash("Snapshot backup disabled.", "success")
                return redirect(url_for("setup"))

            if action == "run_snapshot_now":
                from backup import run_snapshot
                from notifier import send_snapshot_notification

                try:
                    path = run_snapshot()
                    db_log("CREATE", "Snapshot", 0, f"Manual snapshot: {path}")
                    flash(f"Snapshot saved to {path}.", "success")
                    send_snapshot_notification(True, path)
                except Exception as e:
                    flash(f"Snapshot failed: {e}", "danger")
                    send_snapshot_notification(False, str(e))
                return redirect(url_for("setup"))

            if action == "set_slack_settings":
                token = request.form.get("slack_token", "").strip()
                channel = (
                    request.form.get("slack_snapshot_channel", "snapshots")
                    .strip()
                    .lstrip("#")
                )
                runs_channel = (
                    request.form.get("slack_runs_channel", "workflow_runs")
                    .strip()
                    .lstrip("#")
                )
                enabled = request.form.get("slack_enabled") == "1"
                if token:
                    set_slack_token(token)
                set_slack_snapshot_channel(channel)
                set_slack_runs_channel(runs_channel)
                set_slack_enabled(enabled)
                flash("Slack settings saved.", "success")
                return redirect(url_for("setup") + "#slack-notifications")

            if action == "test_slack_notification":
                from notifier import test_notification

                channel = (
                    request.form.get("slack_snapshot_channel", "").strip().lstrip("#")
                    or get_slack_snapshot_channel()
                )
                ok, err = test_notification(channel)
                if ok:
                    flash(f"Test message sent to #{channel}.", "success")
                else:
                    flash(f"Slack test failed: {err}", "danger")
                return redirect(url_for("setup") + "#slack-notifications")

            if action == "save_snapshot_comment":
                from backup import set_snapshot_comment

                ts = request.form.get("snapshot_ts", "").strip()
                comment = request.form.get("comment", "").strip()
                if ts:
                    set_snapshot_comment(ts, comment)
                return redirect(url_for("setup") + "#snapshot-backup")

            if action == "restore_snapshot":
                from backup import restore_snapshot, run_snapshot
                from models import db

                ts = request.form.get("snapshot_ts", "").strip()
                if not ts:
                    flash("No snapshot selected.", "danger")
                    return redirect(url_for("setup"))
                try:
                    run_snapshot()  # safety copy before overwriting
                    restore_snapshot(ts, db.engine)
                    db_log(
                        "UPDATE",
                        "Snapshot",
                        0,
                        f"Restored to snapshot {ts} (safety copy saved first)",
                    )
                    flash(
                        f"Restored to snapshot {ts}. A safety snapshot of the previous state was saved first.",
                        "success",
                    )
                except Exception as e:
                    flash(f"Restore failed: {e}", "danger")
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
        snap_interval = get_snapshot_interval_hours()
        snap_dir = get_snapshot_backup_dir()
        last_snap = get_last_snapshot_time()
        next_snapshot_time = None
        if snap_interval > 0 and snap_dir:
            if last_snap:
                try:
                    next_dt = datetime.strptime(
                        last_snap, "%Y-%m-%d %H:%M"
                    ) + timedelta(hours=snap_interval)
                    next_snapshot_time = next_dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    pass
            else:
                next_snapshot_time = "Due now"
        return render_template(
            "setup.html",
            settings=defaults,
            settings_file=str(SETTINGS_FILE),
            users=get_users(),
            current_user=get_current_user(),
            default_tags=get_default_tags(),
            backup_locations=get_backup_locations(),
            api_key=get_api_key(),
            backup_reminder_days=get_backup_reminder_days(),
            snapshot_backup_dir=snap_dir,
            snapshot_interval_hours=snap_interval,
            snapshot_keep=get_snapshot_keep(),
            last_snapshot_time=last_snap,
            next_snapshot_time=next_snapshot_time,
            snapshots=_list_snapshots(),
            slack_enabled=get_slack_enabled(),
            slack_token=get_slack_token(),
            slack_snapshot_channel=get_slack_snapshot_channel(),
            slack_runs_channel=get_slack_runs_channel(),
        )
