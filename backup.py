import gzip
import hashlib
import json
import logging
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

_log = logging.getLogger("ngs_tracker.backup")

from config import (
    DEFAULT_DB,
    get_last_snapshot_time,
    get_rclone_remote,
    get_snapshot_backup_dir,
    get_snapshot_interval_hours,
    get_snapshot_keep,
    load_settings,
    set_last_snapshot_time,
)

_RSYNC_AVAILABLE = sys.platform == "linux" and bool(shutil.which("rsync"))
_RCLONE_AVAILABLE = bool(shutil.which("rclone"))


def _sidecar(gz_path: Path) -> Path:
    return Path(str(gz_path) + ".sha256")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_and_store(gz_path: Path) -> bool:
    """Write a .sha256 sidecar and verify the snapshot via SQLite integrity_check.

    Returns True if the integrity check passes. Called once, immediately after
    the snapshot is written.
    """
    digest = _sha256(gz_path)
    _sidecar(gz_path).write_text(digest + "\n")

    tmp = gz_path.parent / f"_verify_{gz_path.name}.tmp.db"
    ok = False
    try:
        with gzip.open(gz_path, "rb") as f_in, open(tmp, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        conn = sqlite3.connect(str(tmp))
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        ok = bool(result and result[0] == "ok")
    except Exception as exc:
        _log.error("Snapshot integrity check failed for %s: %s", gz_path.name, exc)
    finally:
        tmp.unlink(missing_ok=True)

    if not ok:
        _log.error("Snapshot %s failed SQLite integrity_check", gz_path.name)
    return ok


def run_snapshot() -> tuple[str, str | None]:
    """
    Write a timestamped DB snapshot and back up the uploads directory.
    On Linux with rsync: incremental hardlink snapshot per timestamp.
    Otherwise: single overwritten tar.gz archive.
    Returns (db_snapshot_path, rclone_error) where rclone_error is None
    when rclone is not configured or succeeded, or an error string on failure.
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

    # DB snapshot — SQLite online backup API + gzip
    tmp_db = db_dir / f"ngs_tracker_{ts}.db"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(str(tmp_db))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    snapshot_gz = db_dir / f"ngs_tracker_{ts}.db.gz"
    with (
        open(tmp_db, "rb") as f_in,
        gzip.open(snapshot_gz, "wb", compresslevel=6) as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)
    tmp_db.unlink()

    _verify_and_store(snapshot_gz)

    # Uploads backup — failures are non-fatal so the DB snapshot is always recorded
    if storage_path and Path(storage_path).exists():
        try:
            if _RSYNC_AVAILABLE:
                _rsync_uploads(storage_path, dest_root, ts)
            else:
                uploads_gz = dest_root / "uploads.tar.gz"
                with tarfile.open(uploads_gz, "w:gz", compresslevel=6) as tar:
                    tar.add(storage_path, arcname="uploads")
        except Exception as exc:
            _log.warning("Uploads backup failed (DB snapshot still saved): %s", exc)

    _prune_db_snapshots(db_dir)
    if _RSYNC_AVAILABLE:
        uploads_dir = dest_root / "uploads"
        if uploads_dir.exists():
            _prune_upload_snapshots(uploads_dir)

    # rclone sync — mirror the whole backup dir to the configured remote
    rclone_error: str | None = None
    remote = get_rclone_remote()
    if remote:
        try:
            _rclone_sync(dest_root, remote)
        except Exception as exc:
            rclone_error = str(exc)
            _log.warning(
                "rclone sync to %s failed (local snapshot still saved): %s", remote, exc
            )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    set_last_snapshot_time(now)
    return str(snapshot_gz), rclone_error


def _rsync_uploads(storage_path: str, dest_root: Path, ts: str) -> None:
    uploads_dir = dest_root / "uploads"
    new_snap = uploads_dir / ts
    new_snap.mkdir(parents=True, exist_ok=True)

    # Find the most recent previous snapshot for --link-dest
    existing = sorted(
        [d for d in uploads_dir.iterdir() if d.is_dir() and d.name != ts],
        reverse=True,
    )

    cmd = ["rsync", "-a", "--delete"]
    if existing:
        cmd += [f"--link-dest={existing[0]}"]
    cmd += [storage_path.rstrip("/") + "/", str(new_snap) + "/"]
    subprocess.run(cmd, check=True)


def _rclone_sync(local_dir: Path, remote: str) -> None:
    """Mirror the entire local backup directory to an rclone remote path."""
    if not _RCLONE_AVAILABLE:
        raise RuntimeError("rclone is not installed or not in PATH.")
    subprocess.run(
        [
            "rclone",
            "sync",
            str(local_dir) + "/",
            remote.rstrip("/") + "/",
            "--fast-list",
            "--transfers=4",
        ],
        check=True,
        timeout=600,
    )


def _prune_db_snapshots(db_dir: Path) -> None:
    keep = get_snapshot_keep()
    for old in sorted(db_dir.glob("ngs_tracker_*.db.gz"), reverse=True)[keep:]:
        old.unlink(missing_ok=True)
        _sidecar(old).unlink(missing_ok=True)


def _prune_upload_snapshots(uploads_dir: Path) -> None:
    keep = get_snapshot_keep()
    snaps = sorted([d for d in uploads_dir.iterdir() if d.is_dir()], reverse=True)
    for old in snaps[keep:]:
        shutil.rmtree(str(old), ignore_errors=True)


def _meta_path(backup_dir: str) -> Path:
    return Path(backup_dir) / "db" / "snapshots_meta.json"


def _load_meta(backup_dir: str) -> dict:
    p = _meta_path(backup_dir)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def _save_meta(backup_dir: str, meta: dict) -> None:
    p = _meta_path(backup_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2))


def set_snapshot_comment(ts: str, comment: str) -> None:
    backup_dir = get_snapshot_backup_dir()
    if not backup_dir:
        return
    meta = _load_meta(backup_dir)
    meta[ts] = comment.strip()
    _save_meta(backup_dir, meta)


def list_snapshots() -> list[dict]:
    """Return available snapshots, newest first, with metadata."""
    backup_dir = get_snapshot_backup_dir()
    if not backup_dir:
        return []
    dest_root = Path(backup_dir)
    db_dir = dest_root / "db"
    if not db_dir.exists():
        return []

    uploads_dir = dest_root / "uploads"
    upload_tss = (
        {d.name for d in uploads_dir.iterdir() if d.is_dir()}
        if uploads_dir.exists()
        else set()
    )
    # Non-rsync: single tar.gz counts as uploads for every snapshot
    uploads_tar = (dest_root / "uploads.tar.gz").exists()

    meta = _load_meta(backup_dir)

    result = []
    for f in sorted(db_dir.glob("ngs_tracker_*.db.gz"), reverse=True):
        ts = f.name.replace("ngs_tracker_", "").replace(".db.gz", "")
        try:
            label = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            label = ts
        has_uploads = ts in upload_tss or uploads_tar

        sc = _sidecar(f)
        if sc.exists():
            try:
                stored = sc.read_text().strip()
                actual = _sha256(f)
                integrity = "ok" if actual == stored else "fail"
            except Exception:
                integrity = "error"
        else:
            integrity = "unverified"

        result.append(
            {
                "ts": ts,
                "label": label,
                "has_uploads": has_uploads,
                "comment": meta.get(ts, ""),
                "integrity": integrity,
            }
        )
    return result


def restore_snapshot(ts: str, engine) -> None:
    """
    Restore DB and uploads from snapshot timestamp ts.
    engine is the SQLAlchemy engine (db.engine) — its pool is disposed
    before the DB file is overwritten.
    """
    backup_dir = get_snapshot_backup_dir()
    if not backup_dir:
        raise ValueError("No backup directory configured.")

    settings = load_settings()
    db_path = settings.get("db_path") or str(DEFAULT_DB)
    storage_path = settings.get("storage_path", "")
    dest_root = Path(backup_dir)

    # Restore DB
    snap_gz = dest_root / "db" / f"ngs_tracker_{ts}.db.gz"
    if not snap_gz.exists():
        raise FileNotFoundError(f"DB snapshot for {ts} not found.")

    tmp = snap_gz.parent / f"_restore_{ts}.db"
    try:
        with gzip.open(snap_gz, "rb") as f_in, open(tmp, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        engine.dispose()
        src = sqlite3.connect(str(tmp))
        dst = sqlite3.connect(db_path)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    finally:
        tmp.unlink(missing_ok=True)

    # Restore uploads
    if storage_path:
        if _RSYNC_AVAILABLE:
            snap_uploads = dest_root / "uploads" / ts
            if snap_uploads.exists():
                Path(storage_path).mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    [
                        "rsync",
                        "-a",
                        "--delete",
                        str(snap_uploads).rstrip("/") + "/",
                        storage_path.rstrip("/") + "/",
                    ],
                    check=True,
                )
        else:
            uploads_tar = dest_root / "uploads.tar.gz"
            if uploads_tar.exists():
                parent = Path(storage_path).parent
                with tarfile.open(uploads_tar, "r:gz") as tar:
                    tar.extractall(str(parent))


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
