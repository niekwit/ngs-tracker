from flask import render_template
from sqlalchemy import func

from models import WorkflowRun, db


def register(app):
    @app.route("/stats")
    def stats():
        rows = (
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
            for r in rows
        ]

        return render_template("stats.html", workflows=workflows)
