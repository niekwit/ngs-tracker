import json

from flask import flash, redirect, render_template, request, url_for

from config import (
    add_default_tag,
    db_log,
    get_backup_locations,
    get_current_user,
    get_default_tags,
    load_run_templates,
    load_workflows,
)
from helpers import _compare_configs, _parse_datetime
from models import (
    FILE_TYPES,
    RUN_STATUSES,
    AttachedFile,
    Project,
    ResearchGroup,
    Researcher,
    WorkflowRun,
    db,
)


def register(app):
    PER_PAGE = 50

    @app.route("/runs")
    def runs_list():
        sort = request.args.get("sort", "date")
        direction = request.args.get("dir", "desc")
        tag_filter = request.args.get("tag", "").strip()
        status_filter = request.args.get("status", "").strip().lower()
        page = max(1, request.args.get("page", 1, type=int))
        reverse = direction == "desc"

        all_runs = WorkflowRun.query.filter_by(trashed=False).all()
        all_tags = sorted({tag for r in all_runs for tag in r.tag_list})

        runs = all_runs
        if tag_filter:
            runs = [r for r in runs if tag_filter in r.tag_list]
        if status_filter and status_filter in RUN_STATUSES:
            runs = [r for r in runs if r.status == status_filter]

        key_map = {
            "workflow": lambda r: r.workflow_name.lower(),
            "project": lambda r: r.project.name.lower(),
            "researcher": lambda r: r.project.researcher.name.lower(),
            "date": lambda r: r.run_date,
            "status": lambda r: r.status,
            "backup": lambda r: len(r.backup_labels),
            "files": lambda r: len(r.attached_files),
        }
        runs.sort(key=key_map.get(sort, key_map["date"]), reverse=reverse)

        total = len(runs)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, total_pages)
        runs_page = runs[(page - 1) * PER_PAGE : page * PER_PAGE]

        return render_template(
            "runs/list.html",
            runs=runs_page,
            sort=sort,
            dir=direction,
            tag_filter=tag_filter,
            status_filter=status_filter,
            all_tags=all_tags,
            run_statuses=RUN_STATUSES,
            page=page,
            total_pages=total_pages,
            total=total,
            per_page=PER_PAGE,
            backup_locations=get_backup_locations(),
        )

    @app.route("/runs/<int:id>")
    def run_detail(id):
        run = db.get_or_404(WorkflowRun, id)
        workflows = load_workflows()
        wf_urls = {w["name"]: w["url"] for w in workflows}
        wf_entry = next((w for w in workflows if w["name"] == run.workflow_name), {})
        mapping_rate_cutoff = float(wf_entry.get("mapping_rate_cutoff", 60.0))

        # Runs with at least one parsed config, excluding this run, for the compare picker
        config_run_ids = (
            db.session.query(AttachedFile.workflow_run_id)
            .filter(
                AttachedFile.file_type == "config",
                AttachedFile.parsed_config.isnot(None),
            )
            .distinct()
            .subquery()
        )
        compare_runs = (
            WorkflowRun.query.filter(
                WorkflowRun.id != id,
                WorkflowRun.trashed == False,
                WorkflowRun.id.in_(config_run_ids),
            )
            .order_by(WorkflowRun.workflow_name, WorkflowRun.run_date.desc())
            .all()
        )

        backup_locations = get_backup_locations()
        backed_up = {b["location"]: b["path"] for b in run.backups_list}
        loc_names = [l["name"] for l in backup_locations]
        return render_template(
            "runs/detail.html",
            run=run,
            file_types=FILE_TYPES,
            wf_urls=wf_urls,
            compare_runs=compare_runs,
            backup_locations=backup_locations,
            backed_up=backed_up,
            loc_names=loc_names,
            mapping_rate_cutoff=mapping_rate_cutoff,
        )

    @app.route("/runs/new", methods=["GET", "POST"])
    def run_new():
        projects = (
            Project.query.filter_by(trashed=False)
            .join(Researcher)
            .filter(Researcher.trashed == False)
            .join(ResearchGroup)
            .filter(ResearchGroup.trashed == False)
            .order_by(ResearchGroup.name, Researcher.name, Project.name)
            .all()
        )
        if not projects:
            flash("Create a project first.", "warning")
            return redirect(url_for("project_new"))

        preselected = request.args.get("project_id", type=int)
        template_id = request.args.get("template_id", "")
        prefill = next(
            (t for t in load_run_templates() if t.get("id") == template_id),
            None,
        )

        if request.method == "POST":
            project_id = request.form.get("project_id", type=int)
            workflow_name = request.form.get("workflow_name", "").strip()
            workflow_tag = request.form.get("workflow_tag", "").strip()
            description = request.form.get("description", "").strip()
            notes = request.form.get("notes", "").strip()
            status = request.form.get("status", "completed")
            run_date = _parse_datetime(request.form.get("run_date", ""))
            selected_locs = set(request.form.getlist("backup_loc"))
            backups = [
                {
                    "location": loc["name"],
                    "path": request.form.get(f"backup_path_{loc['name']}", "").strip(),
                }
                for loc in get_backup_locations()
                if loc["name"] in selected_locs
            ]
            wf_list = load_workflows()
            wf_systems = {w["name"]: w.get("system", "snakemake") for w in wf_list}
            workflow_system = wf_systems.get(workflow_name, "other")

            # Persist any newly created tags to the defaults list
            for t in request.form.get("new_tags", "").split(","):
                add_default_tag(t.strip())
            selected_tags = request.form.getlist("tags")
            tags = ", ".join(t for t in selected_tags if t.strip())

            if not workflow_name or not project_id:
                flash("Workflow name and project are required.", "danger")
                default_tags = get_default_tags()
                return render_template(
                    "runs/form.html",
                    run=None,
                    projects=projects,
                    preselected=preselected,
                    file_types=FILE_TYPES,
                    workflows=wf_list,
                    run_statuses=RUN_STATUSES,
                    default_tags=default_tags,
                    extra_tags=[],
                    backup_locations=get_backup_locations(),
                    prefill=prefill,
                    templates=load_run_templates(),
                    wf_systems_json=json.dumps(wf_systems),
                )

            run = WorkflowRun(
                project_id=project_id,
                workflow_name=workflow_name,
                workflow_tag=workflow_tag,
                description=description,
                tags=tags,
                run_date=run_date,
                notes=notes,
                status=status,
                backups=json.dumps(backups),
                workflow_system=workflow_system,
                created_by=get_current_user(),
            )
            db.session.add(run)
            db.session.commit()
            db_log(
                "CREATE",
                "WorkflowRun",
                run.id,
                f"{run.workflow_name} (project: {run.project.name})",
            )
            flash(f'Workflow run "{workflow_name}" created.', "success")
            return redirect(url_for("run_detail", id=run.id))

        default_tags = get_default_tags()
        wf_list = load_workflows()
        return render_template(
            "runs/form.html",
            run=None,
            projects=projects,
            preselected=preselected,
            file_types=FILE_TYPES,
            workflows=wf_list,
            run_statuses=RUN_STATUSES,
            default_tags=default_tags,
            extra_tags=[],
            backup_locations=get_backup_locations(),
            prefill=prefill,
            templates=load_run_templates(),
            wf_systems_json=json.dumps(
                {w["name"]: w.get("system", "snakemake") for w in wf_list}
            ),
        )

    @app.route("/runs/<int:id>/edit", methods=["GET", "POST"])
    def run_edit(id):
        run = db.get_or_404(WorkflowRun, id)
        projects = (
            Project.query.filter_by(trashed=False)
            .join(Researcher)
            .filter(Researcher.trashed == False)
            .join(ResearchGroup)
            .filter(ResearchGroup.trashed == False)
            .order_by(ResearchGroup.name, Researcher.name, Project.name)
            .all()
        )
        if request.method == "POST":
            run.workflow_name = request.form.get("workflow_name", "").strip()
            run.workflow_tag = request.form.get("workflow_tag", "").strip()
            run.description = request.form.get("description", "").strip()
            run.notes = request.form.get("notes", "").strip()
            run.status = request.form.get("status", "completed")
            run.run_date = _parse_datetime(request.form.get("run_date", ""))
            selected_locs = set(request.form.getlist("backup_loc"))
            run.backups = json.dumps(
                [
                    {
                        "location": loc["name"],
                        "path": request.form.get(
                            f"backup_path_{loc['name']}", ""
                        ).strip(),
                    }
                    for loc in get_backup_locations()
                    if loc["name"] in selected_locs
                ]
            )
            wf_systems = {
                w["name"]: w.get("system", "snakemake") for w in load_workflows()
            }
            run.workflow_system = wf_systems.get(run.workflow_name, "other")
            for t in request.form.get("new_tags", "").split(","):
                add_default_tag(t.strip())
            selected_tags = request.form.getlist("tags")
            run.tags = ", ".join(t for t in selected_tags if t.strip())
            db.session.commit()
            db_log(
                "UPDATE", "WorkflowRun", id, f"{run.workflow_name} status={run.status}"
            )
            flash("Workflow run updated.", "success")
            return redirect(url_for("run_detail", id=id))
        default_tags = get_default_tags()
        extra_tags = [t for t in run.tag_list if t not in default_tags]
        wf_list = load_workflows()
        return render_template(
            "runs/form.html",
            run=run,
            projects=projects,
            preselected=run.project_id,
            file_types=FILE_TYPES,
            workflows=wf_list,
            run_statuses=RUN_STATUSES,
            default_tags=default_tags,
            extra_tags=extra_tags,
            backup_locations=get_backup_locations(),
            prefill=None,
            templates=[],
            wf_systems_json=json.dumps(
                {w["name"]: w.get("system", "snakemake") for w in wf_list}
            ),
        )

    @app.route("/runs/<int:id>/clone", methods=["POST"])
    def run_clone(id):
        src = db.get_or_404(WorkflowRun, id)
        clone = WorkflowRun(
            project_id=src.project_id,
            workflow_name=src.workflow_name,
            workflow_tag=src.workflow_tag,
            description=src.description,
            tags=src.tags,
            notes=src.notes,
            status="pending",
            backups=json.dumps(src.backups_list),
            workflow_system=src.workflow_system or "snakemake",
        )
        db.session.add(clone)
        db.session.commit()
        db_log(
            "CREATE",
            "WorkflowRun",
            clone.id,
            f"{clone.workflow_name} (cloned from id={src.id})",
        )
        flash(f'Run cloned from "{src.workflow_name}" — review and save.', "success")
        return redirect(url_for("run_edit", id=clone.id))

    @app.route("/runs/compare")
    def run_compare():
        id_a = request.args.get("a", type=int)
        id_b = request.args.get("b", type=int)
        if not id_a or not id_b:
            flash("Two run IDs are required for comparison.", "danger")
            return redirect(url_for("runs_list"))

        run_a = db.get_or_404(WorkflowRun, id_a)
        run_b = db.get_or_404(WorkflowRun, id_b)

        config_a = next(
            (
                f.config_dict
                for f in run_a.attached_files
                if f.file_type == "config" and f.config_dict
            ),
            None,
        )
        config_b = next(
            (
                f.config_dict
                for f in run_b.attached_files
                if f.file_type == "config" and f.config_dict
            ),
            None,
        )

        if not config_a and not config_b:
            flash("Neither run has a parsed Snakemake config.", "warning")
            return redirect(url_for("run_detail", id=id_a))

        diff_rows = _compare_configs(config_a or {}, config_b or {})
        counts = {
            s: sum(1 for r in diff_rows if r["status"] == s)
            for s in ("same", "changed", "added", "removed")
        }

        return render_template(
            "runs/compare.html",
            run_a=run_a,
            run_b=run_b,
            diff_rows=diff_rows,
            counts=counts,
            config_a=config_a,
            config_b=config_b,
        )

    @app.route("/runs/<int:id>/delete", methods=["POST"])
    def run_delete(id):
        run = db.get_or_404(WorkflowRun, id)
        run.trashed = True
        db.session.commit()
        db_log("TRASH", "WorkflowRun", run.id, run.workflow_name)
        flash(f'Workflow run "{run.workflow_name}" moved to trash.', "success")
        return redirect(url_for("project_detail", id=run.project_id))

    @app.route("/runs/batch", methods=["POST"])
    def runs_batch():
        run_ids = request.form.getlist("run_ids", type=int)
        action = request.form.get("action", "")
        value = request.form.get("value", "").strip()
        redir_kw = {
            k: request.form.get(k, "") for k in ("sort", "dir", "tag", "status")
        }
        redir_kw = {k: v for k, v in redir_kw.items() if v}

        if not run_ids:
            flash("No runs selected.", "warning")
            return redirect(url_for("runs_list", **redir_kw))

        batch_runs = WorkflowRun.query.filter(
            WorkflowRun.id.in_(run_ids),
            WorkflowRun.trashed == False,
        ).all()

        if action == "set_status":
            if value not in RUN_STATUSES:
                flash("Invalid status.", "danger")
            else:
                for run in batch_runs:
                    run.status = value
                    db_log("UPDATE", "WorkflowRun", run.id, f"batch: status → {value}")
                db.session.commit()
                label = RUN_STATUSES[value][0]
                flash(
                    f'Status set to "{label}" for {len(batch_runs)} run(s).', "success"
                )

        elif action == "add_tag":
            if not value:
                flash("No tag specified.", "warning")
            else:
                add_default_tag(value)
                updated = 0
                for run in batch_runs:
                    tags = run.tag_list
                    if value not in tags:
                        tags.append(value)
                        run.tags = ",".join(tags)
                        updated += 1
                        db_log(
                            "UPDATE",
                            "WorkflowRun",
                            run.id,
                            f"batch: tag added '{value}'",
                        )
                db.session.commit()
                flash(f'Tag "{value}" added to {updated} run(s).', "success")

        elif action == "mark_backup":
            if not value:
                flash("No backup location specified.", "warning")
            else:
                updated = 0
                for run in batch_runs:
                    blist = run.backups_list
                    if value not in [b["location"] for b in blist]:
                        blist.append({"location": value, "path": ""})
                        run.backups = json.dumps(blist)
                        updated += 1
                        db_log(
                            "UPDATE",
                            "WorkflowRun",
                            run.id,
                            f"batch: backup marked '{value}'",
                        )
                db.session.commit()
                flash(
                    f'Marked backed up at "{value}" for {updated} run(s).',
                    "success",
                )

        else:
            flash("Unknown batch action.", "danger")

        return redirect(url_for("runs_list", **redir_kw))
