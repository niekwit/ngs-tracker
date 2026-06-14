import json

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from pathlib import Path

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ResearchGroup(db.Model):
    __tablename__ = "research_group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=_now)
    trashed = db.Column(db.Boolean, default=False, nullable=False)
    researchers = db.relationship(
        "Researcher",
        backref="group",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Researcher.name",
    )

    @property
    def project_count(self):
        return sum(
            1
            for r in self.researchers
            if not r.trashed
            for p in r.projects
            if not p.trashed
        )

    @property
    def run_count(self):
        return sum(
            1
            for r in self.researchers
            if not r.trashed
            for p in r.projects
            if not p.trashed
            for run in p.workflow_runs
            if not run.trashed
        )


class Researcher(db.Model):
    __tablename__ = "researcher"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), default="")
    group_id = db.Column(db.Integer, db.ForeignKey("research_group.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    trashed = db.Column(db.Boolean, default=False, nullable=False)
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
    researcher_id = db.Column(
        db.Integer, db.ForeignKey("researcher.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=_now)
    published = db.Column(db.Boolean, default=False)
    publication_url = db.Column(db.String(500), default="")
    trashed = db.Column(db.Boolean, default=False, nullable=False)
    workflow_runs = db.relationship(
        "WorkflowRun",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan",
    )
    samples = db.relationship(
        "Sample",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Sample.name",
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
        return sorted(
            (r for r in self.workflow_runs if not r.trashed),
            key=lambda r: r.run_date,
            reverse=True,
        )


SCRIPT_LANGUAGES = {
    ".py": "Python",
    ".r": "R",
    ".R": "R",
    ".sh": "Shell",
    ".bash": "Bash",
    ".pl": "Perl",
    ".m": "MATLAB",
    ".jl": "Julia",
    ".nb": "Jupyter",
    ".ipynb": "Jupyter",
}

SCRIPT_LANGUAGE_COLORS = {
    "Python": "primary",
    "R": "danger",
    "Shell": "secondary",
    "Bash": "secondary",
    "Perl": "warning",
    "MATLAB": "warning",
    "Julia": "success",
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
    trashed = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.String(100), default="")
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
    script_id = db.Column(
        db.Integer, db.ForeignKey("project_script.id"), nullable=False
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(255), default="")
    uploaded_at = db.Column(db.DateTime, default=_now)


FILE_TYPES = {
    "config": ("Config", "primary"),
    "sample_info": ("Sample Info", "success"),
    "qc": ("QC", "info"),
    "results": ("Results", "purple"),
    "mapping_rates": ("Mapping Rates", "teal"),
    "other": ("Other", "secondary"),
}

BACKUP_LOCATIONS = ["Local", "RCS", "RFS"]


RUN_STATUSES = {
    "completed": ("Completed", "success"),
    "running": ("Running", "warning"),
    "pending": ("Pending", "secondary"),
    "failed": ("Failed", "danger"),
}


class WorkflowRun(db.Model):
    __tablename__ = "workflow_run"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    workflow_name = db.Column(db.String(150), nullable=False)
    workflow_tag = db.Column(db.String(50), default="")
    description = db.Column(db.Text, default="")
    trashed = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.String(100), default="")
    status = db.Column(db.String(20), default="completed", nullable=False)
    run_date = db.Column(db.DateTime, default=_now)
    notes = db.Column(db.Text, default="")
    backup_local = db.Column(db.Boolean, default=False)
    backup_local_path = db.Column(db.String(500), default="")
    backup_rcs = db.Column(db.Boolean, default=False)
    backup_rcs_path = db.Column(db.String(500), default="")
    backup_rfs = db.Column(db.Boolean, default=False)
    backup_rfs_path = db.Column(db.String(500), default="")
    backups = db.Column(db.Text, nullable=True)  # JSON list of {location, path}
    workflow_system = db.Column(db.String(20), default="snakemake")
    tags = db.Column(db.String(500), default="")
    sample_sheet = db.relationship(
        "SampleSheet",
        backref="run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    run_samples = db.relationship(
        "RunSample",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    attached_files = db.relationship(
        "AttachedFile",
        backref="run",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="AttachedFile.uploaded_at",
    )

    @property
    def status_label(self):
        return RUN_STATUSES.get(self.status, ("Unknown", "secondary"))[0]

    @property
    def status_color(self):
        return RUN_STATUSES.get(self.status, ("Unknown", "secondary"))[1]

    @property
    def tag_list(self):
        return (
            [t.strip() for t in self.tags.split(",") if t.strip()] if self.tags else []
        )

    @property
    def backups_list(self) -> list[dict]:
        if self.backups is not None:
            return json.loads(self.backups) if self.backups else []
        # Fall back to legacy columns for records not yet migrated
        result = []
        if self.backup_local:
            result.append({"location": "Local", "path": self.backup_local_path or ""})
        if self.backup_rcs:
            result.append({"location": "RCS", "path": self.backup_rcs_path or ""})
        if self.backup_rfs:
            result.append({"location": "RFS", "path": self.backup_rfs_path or ""})
        return result

    @property
    def backup_labels(self) -> list[str]:
        return [b["location"] for b in self.backups_list]


class SampleSheet(db.Model):
    __tablename__ = "sample_sheet"
    id = db.Column(db.Integer, primary_key=True)
    workflow_run_id = db.Column(
        db.Integer, db.ForeignKey("workflow_run.id"), nullable=False, unique=True
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=_now)
    csv_data = db.Column(db.Text, nullable=True)  # JSON list-of-lists (header + rows)


class AttachedFile(db.Model):
    __tablename__ = "attached_file"
    id = db.Column(db.Integer, primary_key=True)
    workflow_run_id = db.Column(
        db.Integer, db.ForeignKey("workflow_run.id"), nullable=False
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), default="other")
    description = db.Column(db.String(255), default="")
    uploaded_at = db.Column(db.DateTime, default=_now)
    parsed_config = db.Column(db.Text, nullable=True)  # JSON; only set for config files

    _IMAGE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
    }

    @property
    def is_image(self):
        return Path(self.original_filename).suffix.lower() in self._IMAGE_EXTENSIONS

    @property
    def is_pdf(self):
        return Path(self.original_filename).suffix.lower() == ".pdf"

    @property
    def is_viewable(self):
        return self.is_image or self.is_pdf

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


class Sample(db.Model):
    __tablename__ = "sample"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=_now)
    run_samples = db.relationship(
        "RunSample",
        back_populates="sample",
        cascade="all, delete-orphan",
    )

    @property
    def sorted_runs(self):
        return sorted(
            self.run_samples,
            key=lambda rs: rs.run.run_date,
            reverse=True,
        )


class RunSample(db.Model):
    __tablename__ = "run_sample"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("workflow_run.id"), nullable=False)
    sample_id = db.Column(db.Integer, db.ForeignKey("sample.id"), nullable=False)
    run = db.relationship("WorkflowRun", back_populates="run_samples")
    sample = db.relationship("Sample", back_populates="run_samples")
