import gzip
import json
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

_DEFAULT_WORKFLOWS = [
    {"name": "atac-seq", "url": "https://github.com/niekwit/atac-seq"},
    {"name": "chip-seq", "url": "https://github.com/niekwit/chip-seq"},
    {"name": "crispr-screens", "url": "https://github.com/niekwit/crispr-screens"},
    {"name": "cut_and_run", "url": "https://github.com/niekwit/cut_and_run"},
    {"name": "damid-seq", "url": "https://github.com/niekwit/damid-seq"},
    {"name": "eCLIP", "url": "https://github.com/niekwit/eCLIP"},
    {"name": "gps-orfeome", "url": "https://github.com/niekwit/gps-orfeome"},
    {"name": "methyl-seq", "url": "https://github.com/niekwit/methyl-seq"},
    {"name": "remora", "url": "https://github.com/niekwit/remora"},
    {"name": "rip-seq", "url": "https://github.com/niekwit/rip-seq"},
    {
        "name": "rna-seq-salmon-deseq2",
        "url": "https://github.com/niekwit/rna-seq-salmon-deseq2",
    },
    {
        "name": "rna-seq-star-deseq2",
        "url": "https://github.com/niekwit/rna-seq-star-deseq2",
    },
    {
        "name": "rna-seq-star-tetranscripts",
        "url": "https://github.com/niekwit/rna-seq-star-tetranscripts",
    },
    {"name": "smallRNA-seq", "url": "https://github.com/niekwit/smallRNA-seq"},
    {"name": "tt-seq", "url": "https://github.com/niekwit/tt-seq"},
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
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def save_settings(settings: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


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


# ── Workflows ─────────────────────────────────────────────────────────────────


def load_workflows() -> list:
    if not WORKFLOWS_FILE.exists():
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(WORKFLOWS_FILE, "w") as f:
            yaml.dump(_DEFAULT_WORKFLOWS, f, default_flow_style=False, sort_keys=False)
    with open(WORKFLOWS_FILE) as f:
        return yaml.safe_load(f) or []


def save_workflows(workflows: list) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKFLOWS_FILE, "w") as f:
        yaml.dump(workflows, f, default_flow_style=False, sort_keys=False)
