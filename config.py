import gzip
import json
import os
import secrets
import shutil
import subprocess
import yaml
from datetime import datetime
from pathlib import Path

SETTINGS_DIR = Path.home() / ".ngs-tracker"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
WORKFLOWS_FILE = SETTINGS_DIR / "workflows.yaml"
LOG_FILE = SETTINGS_DIR / "changes.log"
_LOG_MAX_BYTES = 100 * 1024 * 1024  # 100 MB
_LEGACY_SETTINGS = Path(__file__).parent / "settings.json"
DEFAULT_DB = SETTINGS_DIR / "ngs_tracker.db"

WORKFLOW_SYSTEMS = {
    "snakemake": {"label": "Snakemake", "color": "#2e8b57"},
    "nextflow": {"label": "Nextflow", "color": "#ef5b25"},
    "cwl": {"label": "CWL", "color": "#4a86e8"},
    "other": {"label": "Other", "color": "#6c757d"},
}

_DEFAULT_WORKFLOWS = [
    {
        "name": "atac-seq",
        "url": "https://github.com/niekwit/atac-seq",
        "system": "snakemake",
    },
    {
        "name": "chip-seq",
        "url": "https://github.com/niekwit/chip-seq",
        "system": "snakemake",
    },
    {
        "name": "crispr-screens",
        "url": "https://github.com/niekwit/crispr-screens",
        "system": "snakemake",
    },
    {
        "name": "cut_and_run",
        "url": "https://github.com/niekwit/cut_and_run",
        "system": "snakemake",
    },
    {
        "name": "damid-seq",
        "url": "https://github.com/niekwit/damid-seq",
        "system": "snakemake",
    },
    {"name": "eCLIP", "url": "https://github.com/niekwit/eCLIP", "system": "snakemake"},
    {
        "name": "gps-orfeome",
        "url": "https://github.com/niekwit/gps-orfeome",
        "system": "snakemake",
    },
    {
        "name": "methyl-seq",
        "url": "https://github.com/niekwit/methyl-seq",
        "system": "snakemake",
    },
    {
        "name": "remora",
        "url": "https://github.com/niekwit/remora",
        "system": "snakemake",
    },
    {
        "name": "rip-seq",
        "url": "https://github.com/niekwit/rip-seq",
        "system": "snakemake",
    },
    {
        "name": "rna-seq-salmon-deseq2",
        "url": "https://github.com/niekwit/rna-seq-salmon-deseq2",
        "system": "snakemake",
    },
    {
        "name": "rna-seq-star-deseq2",
        "url": "https://github.com/niekwit/rna-seq-star-deseq2",
        "system": "snakemake",
    },
    {
        "name": "rna-seq-star-tetranscripts",
        "url": "https://github.com/niekwit/rna-seq-star-tetranscripts",
        "system": "snakemake",
    },
    {
        "name": "smallRNA-seq",
        "url": "https://github.com/niekwit/smallRNA-seq",
        "system": "snakemake",
    },
    {
        "name": "tt-seq",
        "url": "https://github.com/niekwit/tt-seq",
        "system": "snakemake",
    },
]


# ── Version ───────────────────────────────────────────────────────────────────


def get_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--abbrev=7"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return ""


# ── Change log ────────────────────────────────────────────────────────────────


def db_log(action: str, model: str, record_id: int, detail: str) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists() and LOG_FILE.stat().st_size >= _LOG_MAX_BYTES:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = LOG_FILE.with_name(f"changes.{ts}.log.gz")
        with open(LOG_FILE, "rb") as f_in, gzip.open(archive, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        LOG_FILE.unlink()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = get_current_user() or "—"
    with open(LOG_FILE, "a") as f:
        f.write(
            f"{ts} | {action:<8} | {model:<20} | id={record_id:<6} | user={user:<20} | {detail}\n"
        )


# ── Settings ──────────────────────────────────────────────────────────────────


def load_settings() -> dict:
    if not SETTINGS_FILE.exists() and _LEGACY_SETTINGS.exists():
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGACY_SETTINGS, SETTINGS_FILE)
        _LEGACY_SETTINGS.unlink(missing_ok=True)
    settings: dict = {}
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            settings = json.load(f)
    # Env var overrides — used by demo mode so the real settings.json is never touched
    if os.environ.get("NGS_DB_PATH"):
        settings["db_path"] = os.environ["NGS_DB_PATH"]
    if os.environ.get("NGS_STORAGE_PATH"):
        settings["storage_path"] = os.environ["NGS_STORAGE_PATH"]
    return settings


def save_settings(settings: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    to_write = dict(settings)
    # When env var overrides are active (demo/CI mode) we must NOT bake the
    # overridden paths into the real settings file.  Read the original on-disk
    # values and restore them so that any save during demo mode is transparent.
    if os.environ.get("NGS_DB_PATH") or os.environ.get("NGS_STORAGE_PATH"):
        raw: dict = {}
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE) as _f:
                raw = json.load(_f)
        if os.environ.get("NGS_DB_PATH"):
            if "db_path" in raw:
                to_write["db_path"] = raw["db_path"]
            else:
                to_write.pop("db_path", None)
        if os.environ.get("NGS_STORAGE_PATH"):
            if "storage_path" in raw:
                to_write["storage_path"] = raw["storage_path"]
            else:
                to_write.pop("storage_path", None)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(to_write, f, indent=2)


def is_configured() -> bool:
    s = load_settings()
    return bool(s.get("storage_path") and s.get("db_path"))


def get_storage_path() -> Path:
    s = load_settings()
    if s.get("storage_path"):
        return Path(s["storage_path"])
    return SETTINGS_DIR / "uploads"


# ── Users ────────────────────────────────────────────────────────────────────


def get_users() -> list[str]:
    return load_settings().get("users", [])


def get_current_user() -> str:
    return load_settings().get("current_user", "")


def add_user(name: str) -> None:
    s = load_settings()
    users = s.get("users", [])
    if name and name not in users:
        users.append(name)
        users.sort(key=str.lower)
        s["users"] = users
        if not s.get("current_user"):
            s["current_user"] = name
        save_settings(s)


def remove_user(name: str) -> None:
    s = load_settings()
    users = [u for u in s.get("users", []) if u != name]
    s["users"] = users
    if s.get("current_user") == name:
        s["current_user"] = users[0] if users else ""
    save_settings(s)


def set_current_user(name: str) -> None:
    s = load_settings()
    if name in s.get("users", []):
        s["current_user"] = name
        save_settings(s)


# ── Default tags ──────────────────────────────────────────────────────────────

_DEFAULT_TAGS = [
    "contamination",
    "failed-QC",
    "final",
    "low-coverage",
    "needs-review",
    "pilot",
    "published",
    "re-run",
    "test",
]


def get_default_tags() -> list[str]:
    s = load_settings()
    if "default_tags" not in s:
        s["default_tags"] = sorted(_DEFAULT_TAGS, key=str.lower)
        save_settings(s)
    return sorted(s["default_tags"], key=str.lower)


def add_default_tag(name: str) -> None:
    name = name.strip()
    if not name:
        return
    s = load_settings()
    tags = s.get("default_tags", [])
    if name not in tags:
        tags.append(name)
        tags.sort(key=str.lower)
        s["default_tags"] = tags
        save_settings(s)


def remove_default_tag(name: str) -> None:
    s = load_settings()
    s["default_tags"] = [t for t in s.get("default_tags", []) if t != name]
    save_settings(s)


# ── Backup locations ──────────────────────────────────────────────────────────

_DEFAULT_BACKUP_LOCATIONS = [
    {"name": "Local", "type": "local"},
    {"name": "RCS", "type": "remote"},
    {"name": "RFS", "type": "remote"},
]


def _migrate_backup_locs(locs: list) -> list[dict]:
    """Upgrade old list[str] format to list[dict]."""
    if locs and isinstance(locs[0], str):
        return [{"name": l, "type": "remote"} for l in locs]
    return locs


def get_backup_locations() -> list[dict]:
    s = load_settings()
    if "backup_locations" not in s:
        s["backup_locations"] = _DEFAULT_BACKUP_LOCATIONS[:]
        save_settings(s)
        return _DEFAULT_BACKUP_LOCATIONS[:]
    locs = _migrate_backup_locs(s["backup_locations"])
    if locs != s["backup_locations"]:
        s["backup_locations"] = locs
        save_settings(s)
    return locs


def add_backup_location(name: str, loc_type: str = "remote") -> None:
    name = name.strip()
    if not name:
        return
    s = load_settings()
    locs = _migrate_backup_locs(s.get("backup_locations", _DEFAULT_BACKUP_LOCATIONS[:]))
    if name not in [l["name"] for l in locs]:
        locs.append({"name": name, "type": loc_type})
        s["backup_locations"] = locs
        save_settings(s)


def remove_backup_location(name: str) -> None:
    s = load_settings()
    locs = _migrate_backup_locs(s.get("backup_locations", []))
    s["backup_locations"] = [l for l in locs if l["name"] != name]
    save_settings(s)


# ── Workflows ─────────────────────────────────────────────────────────────────


def load_workflows() -> list:
    if not WORKFLOWS_FILE.exists():
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(WORKFLOWS_FILE, "w") as f:
            yaml.dump(_DEFAULT_WORKFLOWS, f, default_flow_style=False, sort_keys=False)
    with open(WORKFLOWS_FILE) as f:
        workflows = yaml.safe_load(f) or []
    # Migrate old entries missing new fields
    changed = False
    for wf in workflows:
        if "system" not in wf:
            wf["system"] = "snakemake"
            changed = True
        if "mapping_rate_cutoff" not in wf:
            wf["mapping_rate_cutoff"] = 60.0
            changed = True
    if changed:
        save_workflows(workflows)
    return workflows


def save_workflows(workflows: list) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKFLOWS_FILE, "w") as f:
        yaml.dump(workflows, f, default_flow_style=False, sort_keys=False)


# ── Run templates ─────────────────────────────────────────────────────────────

TEMPLATES_FILE = SETTINGS_DIR / "run_templates.json"


def load_run_templates() -> list:
    if TEMPLATES_FILE.exists():
        with open(TEMPLATES_FILE) as f:
            return json.load(f)
    return []


def save_run_templates(templates: list) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates, f, indent=2)


def add_run_template(template: dict) -> None:
    templates = load_run_templates()
    templates.append(template)
    save_run_templates(templates)


def delete_run_template(tid: str) -> None:
    templates = [t for t in load_run_templates() if t.get("id") != tid]
    save_run_templates(templates)


# ── API key ───────────────────────────────────────────────────────────────────


def get_api_key() -> str:
    """Return the API key, generating one on first call."""
    s = load_settings()
    if not s.get("api_key"):
        s["api_key"] = secrets.token_urlsafe(32)
        save_settings(s)
    return s["api_key"]


def rotate_api_key() -> str:
    """Generate and store a new API key, invalidating the old one."""
    s = load_settings()
    s["api_key"] = secrets.token_urlsafe(32)
    save_settings(s)
    return s["api_key"]


# ── Backup reminder ───────────────────────────────────────────────────────────


def get_backup_reminder_days() -> int:
    """Return the backup reminder threshold in days (0 = disabled)."""
    return max(0, int(load_settings().get("backup_reminder_days", 30)))


def set_backup_reminder_days(days: int) -> None:
    s = load_settings()
    s["backup_reminder_days"] = max(0, int(days))
    save_settings(s)
