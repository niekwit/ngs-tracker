from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ResearchGroup(db.Model):
    __tablename__ = "research_group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=_now)
    researchers = db.relationship(
        "Researcher",
        backref="group",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Researcher.name",
    )

    @property
    def project_count(self):
        return sum(len(r.projects) for r in self.researchers)

    @property
    def run_count(self):
        return sum(
            len(p.workflow_runs) for r in self.researchers for p in r.projects
        )


class Researcher(db.Model):
    __tablename__ = "researcher"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), default="")
    group_id = db.Column(db.Integer, db.ForeignKey("research_group.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    projects = db.relationship(
        "Project",
        backref="researcher",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Project.name",
    )


class Project(db.Model):
    __tablename__ = "project"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    researcher_id = db.Column(db.Integer, db.ForeignKey("researcher.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    workflow_runs = db.relationship(
        "WorkflowRun",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan",
    )
    scripts = db.relationship(
        "ProjectScript",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="ProjectScript.uploaded_at",
    )

    @property
    def sorted_runs(self):
        return sorted(self.workflow_runs, key=lambda r: r.run_date, reverse=True)


SCRIPT_LANGUAGES = {
    ".py":   "Python",
    ".r":    "R",
    ".R":    "R",
    ".sh":   "Shell",
    ".bash": "Bash",
    ".pl":   "Perl",
    ".m":    "MATLAB",
    ".jl":   "Julia",
    ".nb":   "Jupyter",
    ".ipynb":"Jupyter",
}

SCRIPT_LANGUAGE_COLORS = {
    "Python":  "primary",
    "R":       "danger",
    "Shell":   "secondary",
    "Bash":    "secondary",
    "Perl":    "warning",
    "MATLAB":  "warning",
    "Julia":   "success",
    "Jupyter": "info",
}


class ProjectScript(db.Model):
    __tablename__ = "project_script"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    language = db.Column(db.String(50), default="")
    description = db.Column(db.String(255), default="")
    uploaded_at = db.Column(db.DateTime, default=_now)
    output_files = db.relationship(
        "ScriptOutputFile",
        backref="script",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="ScriptOutputFile.uploaded_at",
    )

    @property
    def language_color(self):
        return SCRIPT_LANGUAGE_COLORS.get(self.language, "secondary")


class ScriptOutputFile(db.Model):
    __tablename__ = "script_output_file"
    id = db.Column(db.Integer, primary_key=True)
    script_id = db.Column(db.Integer, db.ForeignKey("project_script.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(255), default="")
    uploaded_at = db.Column(db.DateTime, default=_now)


FILE_TYPES = {
    "config": ("Snakemake Config", "primary"),
    "peak_calls": ("Peak Calls", "purple"),
    "data": ("Processed Data", "warning"),
    "other": ("Other", "secondary"),
}

BACKUP_LOCATIONS = ["Local", "RCS", "RFS"]


WORKFLOWS = [
    "atac-seq",
    "chip-seq",
    "crispr-screens",
    "cut_and_run",
    "damid-seq",
    "eCLIP",
    "gps-orfeome",
    "methyl-seq",
    "remora",
    "rip-seq",
    "rna-seq-salmon-deseq2",
    "rna-seq-star-deseq2",
    "rna-seq-star-tetranscripts",
    "smallRNA-seq",
    "tt-seq",
]


class WorkflowRun(db.Model):
    __tablename__ = "workflow_run"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    workflow_name = db.Column(db.String(150), nullable=False)
    workflow_tag = db.Column(db.String(50), default="")
    description = db.Column(db.Text, default="")
    run_date = db.Column(db.DateTime, default=_now)
    notes = db.Column(db.Text, default="")
    backup_local = db.Column(db.Boolean, default=False)
    backup_local_path = db.Column(db.String(500), default="")
    backup_rcs = db.Column(db.Boolean, default=False)
    backup_rcs_path = db.Column(db.String(500), default="")
    backup_rfs = db.Column(db.Boolean, default=False)
    backup_rfs_path = db.Column(db.String(500), default="")
    attached_files = db.relationship(
        "AttachedFile",
        backref="run",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="AttachedFile.uploaded_at",
    )

    @property
    def backup_labels(self):
        labels = []
        if self.backup_local:
            labels.append("Local")
        if self.backup_rcs:
            labels.append("RCS")
        if self.backup_rfs:
            labels.append("RFS")
        return labels


class AttachedFile(db.Model):
    __tablename__ = "attached_file"
    id = db.Column(db.Integer, primary_key=True)
    workflow_run_id = db.Column(db.Integer, db.ForeignKey("workflow_run.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), default="other")
    description = db.Column(db.String(255), default="")
    uploaded_at = db.Column(db.DateTime, default=_now)
    parsed_config = db.Column(db.Text, nullable=True)  # JSON; only set for config files

    @property
    def type_label(self):
        return FILE_TYPES.get(self.file_type, ("Other", "secondary"))[0]

    @property
    def type_color(self):
        return FILE_TYPES.get(self.file_type, ("Other", "secondary"))[1]

    @property
    def config_dict(self):
        if self.parsed_config:
            import json
            return json.loads(self.parsed_config)
        return None
