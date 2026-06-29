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


# Known top-level subdirectories under storage_path
_STORAGE_SUBDIRS = {"runs", "samples", "scripts", "outputs"}


def resolve_stored_path(stored_path: str) -> Path:
    """Return the real path for a stored file, handling cross-machine mounts.

    When the database is shared via Dropbox (or similar) across machines with
    different mount points, stored_path may contain an absolute prefix that
    doesn't exist here.  Strategy: find the first path component that matches
    a known storage subdirectory (runs/, samples/, scripts/, outputs/) and
    re-anchor everything from there under the current storage root.

    Also tries keeping one extra parent component before the anchor to handle
    the case where one machine configured an intermediate subdirectory (e.g.
    uploads/) that the other machine's storage root already includes.
    """
    p = Path(stored_path)
    if p.exists():
        return p
    parts = p.parts
    root = get_storage_path()
    for i, part in enumerate(parts):
        if part in _STORAGE_SUBDIRS:
            # Primary: anchor directly at the known subdirectory
            candidate = root / Path(*parts[i:])
            if candidate.exists():
                return candidate
            # Fallback: keep one extra parent component (e.g. uploads/runs/…)
            if i > 0:
                candidate2 = root / Path(*parts[i - 1 :])
                if candidate2.exists():
                    return candidate2
            break
    return p


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

TAG_COLOR_OPTIONS = [
    ("warning", "Yellow"),
    ("danger", "Red"),
    ("success", "Green"),
    ("primary", "Blue"),
    ("info", "Cyan"),
    ("secondary", "Grey"),
    ("dark", "Dark"),
]

# Colors applied during migration for known built-in tag names
_DEFAULT_TAG_COLORS: dict[str, str] = {
    "contamination": "danger",
    "failed-QC": "danger",
    "final": "success",
    "low-coverage": "warning",
    "needs-review": "warning",
    "pilot": "info",
    "published": "success",
    "re-run": "secondary",
    "test": "secondary",
}

_DEFAULT_TAGS: list[dict] = [
    {"name": name, "color": color}
    for name, color in sorted(_DEFAULT_TAG_COLORS.items(), key=lambda x: x[0].lower())
]


def _migrate_tags(tags: list) -> list[dict]:
    """Upgrade old list[str] format to list[dict] with colour."""
    migrated = []
    for t in tags:
        if isinstance(t, str):
            migrated.append({"name": t, "color": _DEFAULT_TAG_COLORS.get(t, "warning")})
        else:
            migrated.append(t)
    return migrated


def get_default_tags() -> list[dict]:
    s = load_settings()
    if "default_tags" not in s:
        s["default_tags"] = _DEFAULT_TAGS[:]
        save_settings(s)
        return _DEFAULT_TAGS[:]
    tags = _migrate_tags(s["default_tags"])
    if tags != s["default_tags"]:
        s["default_tags"] = tags
        save_settings(s)
    return sorted(tags, key=lambda t: t["name"].lower())


def get_tag_colors() -> dict[str, str]:
    """Return {tag_name: bootstrap_color} for all default tags."""
    return {t["name"]: t["color"] for t in get_default_tags()}


def add_default_tag(name: str, color: str = "warning") -> None:
    name = name.strip()
    if not name:
        return
    s = load_settings()
    tags = _migrate_tags(s.get("default_tags", []))
    if name not in [t["name"] for t in tags]:
        tags.append({"name": name, "color": color})
        tags.sort(key=lambda t: t["name"].lower())
        s["default_tags"] = tags
        save_settings(s)


def remove_default_tag(name: str) -> None:
    s = load_settings()
    tags = _migrate_tags(s.get("default_tags", []))
    s["default_tags"] = [t for t in tags if t["name"] != name]
    save_settings(s)


def set_tag_color(name: str, color: str) -> None:
    s = load_settings()
    tags = _migrate_tags(s.get("default_tags", []))
    for t in tags:
        if t["name"] == name:
            t["color"] = color
            break
    s["default_tags"] = tags
    save_settings(s)


# ── Backup locations ──────────────────────────────────────────────────────────

_DEFAULT_BACKUP_LOCATIONS = [
    {"name": "Local", "type": "local"},
    {"name": "RCS", "type": "remote"},
    {"name": "RFS", "type": "remote"},
]


def _migrate_backup_locs(locs: list) -> list[dict]:
    """Upgrade old list[str] format to list[dict], and add missing keys."""
    if locs and isinstance(locs[0], str):
        locs = [{"name": l, "type": "remote"} for l in locs]
    return [{**l, "base_path": l.get("base_path", "")} for l in locs]


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


def add_backup_location(
    name: str, loc_type: str = "remote", base_path: str = ""
) -> None:
    name = name.strip()
    if not name:
        return
    s = load_settings()
    locs = _migrate_backup_locs(s.get("backup_locations", _DEFAULT_BACKUP_LOCATIONS[:]))
    if name not in [l["name"] for l in locs]:
        locs.append({"name": name, "type": loc_type, "base_path": base_path.strip()})
        s["backup_locations"] = locs
        save_settings(s)


def set_backup_location_base_path(name: str, base_path: str) -> None:
    s = load_settings()
    locs = _migrate_backup_locs(s.get("backup_locations", []))
    for loc in locs:
        if loc["name"] == name:
            loc["base_path"] = base_path.strip()
            break
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
        if "local_path" not in wf:
            wf["local_path"] = ""
            changed = True
    if changed:
        save_workflows(workflows)
    return workflows


def save_workflows(workflows: list) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKFLOWS_FILE, "w") as f:
        yaml.dump(workflows, f, default_flow_style=False, sort_keys=False)


# ── CRISPR screen libraries ───────────────────────────────────────────────────

CRISPR_LIBRARIES_FILE = SETTINGS_DIR / "crispr_libraries.json"


def load_crispr_libraries() -> list:
    """Return list of {name, addgene_id, publication_url}."""
    if CRISPR_LIBRARIES_FILE.exists():
        try:
            with open(CRISPR_LIBRARIES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_crispr_libraries(libs: list) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CRISPR_LIBRARIES_FILE, "w") as f:
        json.dump(libs, f, indent=2)


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


# ── Snapshot backup ───────────────────────────────────────────────────────────


def get_snapshot_backup_dir() -> str:
    if os.environ.get("NGS_SNAPSHOT_DIR"):
        return os.environ["NGS_SNAPSHOT_DIR"]
    return load_settings().get("snapshot_backup_dir", "")


def set_snapshot_backup_dir(path: str) -> None:
    s = load_settings()
    s["snapshot_backup_dir"] = path.strip()
    save_settings(s)


def get_snapshot_interval_hours() -> int:
    return max(0, int(load_settings().get("snapshot_interval_hours", 0)))


def set_snapshot_interval_hours(hours: int) -> None:
    s = load_settings()
    s["snapshot_interval_hours"] = max(0, int(hours))
    save_settings(s)


def get_snapshot_keep() -> int:
    return max(1, int(load_settings().get("snapshot_keep", 10)))


def set_snapshot_keep(n: int) -> None:
    s = load_settings()
    s["snapshot_keep"] = max(1, int(n))
    save_settings(s)


def get_rclone_remote() -> str:
    return load_settings().get("rclone_remote", "")


def set_rclone_remote(remote: str) -> None:
    s = load_settings()
    s["rclone_remote"] = remote.strip()
    save_settings(s)


def get_last_snapshot_time() -> str:
    return load_settings().get("last_snapshot_time", "")


def set_last_snapshot_time(ts: str) -> None:
    s = load_settings()
    s["last_snapshot_time"] = ts
    save_settings(s)


# ── Email alerts ──────────────────────────────────────────────────────────────


def get_email_alerts_enabled() -> bool:
    return bool(load_settings().get("email_alerts_enabled", False))


def set_email_alerts_enabled(v: bool) -> None:
    s = load_settings()
    s["email_alerts_enabled"] = bool(v)
    save_settings(s)


def get_smtp_host() -> str:
    return load_settings().get("smtp_host", "")


def set_smtp_host(v: str) -> None:
    s = load_settings()
    s["smtp_host"] = v.strip()
    save_settings(s)


def get_smtp_port() -> int:
    return int(load_settings().get("smtp_port", 587))


def set_smtp_port(v: int) -> None:
    s = load_settings()
    s["smtp_port"] = int(v)
    save_settings(s)


def get_smtp_user() -> str:
    return load_settings().get("smtp_user", "")


def set_smtp_user(v: str) -> None:
    s = load_settings()
    s["smtp_user"] = v.strip()
    save_settings(s)


def get_smtp_password() -> str:
    return load_settings().get("smtp_password", "")


def set_smtp_password(v: str) -> None:
    s = load_settings()
    s["smtp_password"] = v
    save_settings(s)


def get_alert_recipient() -> str:
    return load_settings().get("alert_recipient", "")


def set_alert_recipient(v: str) -> None:
    s = load_settings()
    s["alert_recipient"] = v.strip()
    save_settings(s)


def get_last_backup_alert_sent() -> str:
    return load_settings().get("last_backup_alert_sent", "")


def set_last_backup_alert_sent(ts: str) -> None:
    s = load_settings()
    s["last_backup_alert_sent"] = ts
    save_settings(s)


# ── Slack notifications ───────────────────────────────────────────────────────


def is_demo_mode() -> bool:
    return bool(os.environ.get("NGS_DB_PATH"))


def get_slack_enabled() -> bool:
    if is_demo_mode():
        return False
    return bool(load_settings().get("slack_enabled", False))


def set_slack_enabled(v: bool) -> None:
    s = load_settings()
    s["slack_enabled"] = bool(v)
    save_settings(s)


def get_slack_token() -> str:
    return load_settings().get("slack_token", "")


def set_slack_token(v: str) -> None:
    s = load_settings()
    s["slack_token"] = v.strip()
    save_settings(s)


def get_slack_snapshot_channel() -> str:
    return load_settings().get("slack_snapshot_channel", "snapshots")


def set_slack_snapshot_channel(v: str) -> None:
    s = load_settings()
    s["slack_snapshot_channel"] = v.strip().lstrip("#")
    save_settings(s)


def get_slack_runs_channel() -> str:
    return load_settings().get("slack_runs_channel", "workflow_runs")


def set_slack_runs_channel(v: str) -> None:
    s = load_settings()
    s["slack_runs_channel"] = v.strip().lstrip("#")
    save_settings(s)


# ── Startup DB → local config sync ───────────────────────────────────────────


def sync_from_db() -> None:
    """Merge values present in the shared DB but missing from local config.

    Called once at startup so that settings entered on one machine (e.g. at
    work) are automatically available on another (e.g. at home) as soon as
    the shared database file is visible.

    Currently syncs: CRISPR libraries, run tags, users.
    """
    if is_demo_mode():
        return

    from models import db

    _sync_crispr_libraries(db)
    _sync_tags(db)
    _sync_users(db)


def _sync_crispr_libraries(db) -> None:
    from models import CrisprLibrary

    # Seed DB table from local JSON if the table is still empty (first run on
    # this machine, or first run after upgrading to this version).
    if CrisprLibrary.query.count() == 0:
        local_libs = load_crispr_libraries()
        for lib in local_libs:
            db.session.add(
                CrisprLibrary(
                    name=lib["name"],
                    genome=lib.get("genome", ""),
                    addgene_id=lib.get("addgene_id", ""),
                    publication_url=lib.get("publication_url", ""),
                )
            )
        if local_libs:
            db.session.commit()
            print(
                f"  [sync] Seeded {len(local_libs)} CRISPR librar{'y' if len(local_libs) == 1 else 'ies'} from local JSON into DB"
            )

    # Also pull in any library name used in a run but not yet in the table.
    rows = db.session.execute(
        db.text(
            "SELECT DISTINCT crispr_library FROM workflow_run"
            " WHERE crispr_library != '' AND trashed = 0"
        )
    ).fetchall()
    for (name,) in rows:
        if not CrisprLibrary.query.filter_by(name=name).first():
            db.session.add(CrisprLibrary(name=name))
    db.session.commit()

    # Now populate local JSON from DB (the authoritative source).
    all_libs = CrisprLibrary.query.order_by(CrisprLibrary.name).all()
    local_libs = load_crispr_libraries()
    local_names = {lib["name"] for lib in local_libs}
    new_libs = [lib for lib in all_libs if lib.name not in local_names]
    if not new_libs:
        return

    for lib in new_libs:
        local_libs.append(lib.to_dict())
    local_libs.sort(key=lambda x: x["name"].lower())
    save_crispr_libraries(local_libs)
    print(
        f"  [sync] Added {len(new_libs)} CRISPR librar{'y' if len(new_libs) == 1 else 'ies'}"
        f" from DB: {', '.join(lib.name for lib in new_libs)}"
    )


def _sync_tags(db) -> None:
    rows = db.session.execute(
        db.text("SELECT tags FROM workflow_run WHERE tags != '' AND trashed = 0")
    ).fetchall()
    db_tags: set[str] = set()
    for (tag_str,) in rows:
        for t in tag_str.split(","):
            t = t.strip()
            if t:
                db_tags.add(t)
    if not db_tags:
        return

    s = load_settings()
    existing = s.get("default_tags", [])
    local_names = {entry["name"] for entry in existing}
    new_tags = db_tags - local_names
    if not new_tags:
        return

    for name in sorted(new_tags):
        existing.append({"name": name, "color": "secondary"})
    s["default_tags"] = existing
    save_settings(s)
    print(
        f"  [sync] Added {len(new_tags)} tag{'s' if len(new_tags) != 1 else ''}"
        f" from DB: {', '.join(sorted(new_tags))}"
    )


def _sync_users(db) -> None:
    rows = db.session.execute(
        db.text(
            "SELECT DISTINCT created_by FROM workflow_run WHERE created_by != ''"
            " UNION SELECT DISTINCT created_by FROM project_script WHERE created_by != ''"
        )
    ).fetchall()
    db_users = {r[0] for r in rows}
    if not db_users:
        return

    s = load_settings()
    local_users = set(s.get("users", []))
    new_users = db_users - local_users
    if not new_users:
        return

    users = sorted(local_users | new_users, key=str.lower)
    s["users"] = users
    if not s.get("current_user") and users:
        s["current_user"] = users[0]
    save_settings(s)
    print(
        f"  [sync] Added {len(new_users)} user{'s' if len(new_users) != 1 else ''}"
        f" from DB: {', '.join(sorted(new_users))}"
    )
