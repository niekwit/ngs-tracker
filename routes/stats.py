import json
from collections import defaultdict
from datetime import datetime

from flask import render_template
from sqlalchemy import func

from models import Project, Researcher, ResearchGroup, WorkflowRun, db


def register(app):
    @app.route("/stats")
    def stats():
        runtime_rows = (
            db.session.query(
                WorkflowRun.workflow_name,
                func.avg(WorkflowRun.runtime_seconds).label("avg_seconds"),
                func.count(WorkflowRun.id).label("run_count"),
            )
            .filter(
                WorkflowRun.trashed == False,
                WorkflowRun.runtime_seconds.isnot(None),
            )
            .group_by(WorkflowRun.workflow_name)
            .order_by(func.avg(WorkflowRun.runtime_seconds).desc())
            .all()
        )

        workflows = [
            {
                "name": r.workflow_name,
                "avg_minutes": round(r.avg_seconds / 60, 1),
                "avg_seconds": int(r.avg_seconds),
                "run_count": r.run_count,
            }
            for r in runtime_rows
        ]

        exec_rows = (
            db.session.query(
                WorkflowRun.workflow_name,
                func.count(WorkflowRun.id).label("total"),
            )
            .filter(WorkflowRun.trashed == False)
            .group_by(WorkflowRun.workflow_name)
            .order_by(func.count(WorkflowRun.id).desc())
            .all()
        )

        executions = [{"name": r.workflow_name, "total": r.total} for r in exec_rows]

        # Runs per month — last 12 calendar months
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
        timeline_data = json.dumps({m: timeline_counts[m] for m in months})

        pub_rows = (
            db.session.query(
                ResearchGroup.name.label("group_name"),
                func.count(Project.id).label("published_count"),
            )
            .join(Researcher, Researcher.group_id == ResearchGroup.id)
            .join(Project, Project.researcher_id == Researcher.id)
            .filter(
                ResearchGroup.trashed == False,
                Researcher.trashed == False,
                Project.trashed == False,
                Project.published == True,
            )
            .group_by(ResearchGroup.id, ResearchGroup.name)
            .order_by(func.count(Project.id).desc())
            .all()
        )
        published_by_group = [
            {"group": r.group_name, "count": r.published_count} for r in pub_rows
        ]

        return render_template(
            "stats.html",
            workflows=workflows,
            executions=executions,
            timeline_data=timeline_data,
            published_by_group=published_by_group,
        )
