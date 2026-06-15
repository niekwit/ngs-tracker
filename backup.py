import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config import (
    get_last_snapshot_time,
    get_snapshot_backup_dir,
    get_snapshot_interval_hours,
    get_snapshot_keep,
    load_settings,
    set_last_snapshot_time,
    DEFAULT_DB,
)


def run_snapshot() -> str:
    """
    Write a timestamped DB snapshot and mirror the uploads directory to the
    configured snapshot backup directory.  Returns the snapshot DB path.
    Raises if no backup dir is configured or the directory cannot be created.
    """
    backup_dir = get_snapshot_backup_dir()
    if not backup_dir:
        raise ValueError("No snapshot backup directory configured.")

    settings = load_settings()
    db_path = settings.get("db_path") or str(DEFAULT_DB)
    storage_path = settings.get("storage_path", "")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_root = Path(backup_dir)
    db_dir = dest_root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    # Safe online backup using SQLite's built-in API
    snapshot_db = db_dir / f"ngs_tracker_{ts}.db"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(str(snapshot_db))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    # Mirror uploads — keep a single up-to-date copy (no per-snapshot duplication)
    if storage_path and Path(storage_path).exists():
        uploads_mirror = dest_root / "uploads"
        uploads_mirror.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            storage_path,
            str(uploads_mirror),
            dirs_exist_ok=True,
            copy_function=shutil.copy2,
        )

    _prune_db_snapshots(db_dir)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    set_last_snapshot_time(now)
    return str(snapshot_db)


def _prune_db_snapshots(db_dir: Path) -> None:
    keep = get_snapshot_keep()
    snapshots = sorted(db_dir.glob("ngs_tracker_*.db"), reverse=True)
    for old in snapshots[keep:]:
        old.unlink(missing_ok=True)


def is_snapshot_due() -> bool:
    hours = get_snapshot_interval_hours()
    if hours <= 0 or not get_snapshot_backup_dir():
        return False
    last = get_last_snapshot_time()
    if not last:
        return True
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M")
    except ValueError:
        return True
    return (datetime.now() - last_dt).total_seconds() >= hours * 3600
