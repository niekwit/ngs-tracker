# Settings

All settings are persisted to `~/.ngs-tracker/settings.json` and survive re-clones or moves of the repository. The **Settings** page is accessible from the navbar gear icon.

## Storage paths

| Setting | Description |
|---|---|
| **Database path** | Full path to the SQLite file (e.g. `/data/ngs.db`). Changing this requires a server restart. |
| **File storage path** | Directory where all uploaded files are written. |

```{note}
After changing the database path, restart the server so the new path takes effect. The file storage path is re-read on every request.
```

## Users

NGS Tracker has a lightweight user system — no passwords, just named profiles. The active user is recorded in every change log entry and shown in the navbar.

- **Add** a user by typing their name and clicking Add
- **Switch** to a user by clicking their button
- **Remove** a user by clicking ×

If only one user exists they are selected automatically. Users are stored in `settings.json`.

## REST API key

NGS Tracker generates an API key on first use and stores it in `settings.json`. The key authenticates requests to the [REST API](api.md).

The **Settings** page shows the current key in a read-only field with a copy-to-clipboard button.

### Rotating the key

Click **Rotate key** to generate a fresh 256-bit random key. The old key stops working immediately — update any scripts or pipelines that use the API before rotating.

```{warning}
Rotating the key cannot be undone. Clients still using the old key will receive `401 Unauthorized` responses.
```

## Default tags

Tags are free-text labels attached to workflow runs. The default list is shown as a coloured checkbox picker when creating or editing a run. New tags typed inline are added to the list automatically.

Each tag has a configurable **colour** chosen from:

| Colour | Bootstrap class | Typical use |
|---|---|---|
| Yellow | `warning` | Caution, low-priority flags |
| Red | `danger` | Failures, contamination |
| Green | `success` | Published, final, approved |
| Blue | `primary` | General purpose |
| Cyan | `info` | Informational, pilot |
| Grey | `secondary` | Neutral, archived |
| Dark | `dark` | High-contrast label |

The built-in defaults ship with sensible colours (`failed-QC` → Red, `published` → Green, `needs-review` → Yellow, etc.). Change any colour instantly from the Settings page — the dropdown auto-saves on change.

- **Add** a tag (with colour) from the Settings page
- **Change colour** via the colour dropdown next to each tag
- **Remove** a tag by clicking ×

Removing a tag from the defaults does not affect runs that already use it.

## Backup locations

Backup locations are the named destinations shown when recording that a workflow run has been backed up. Each location has:

| Field | Description |
|---|---|
| **Name** | Short label shown on the run form, e.g. `RCS`, `HPC`, `External Drive`. |
| **Type** | `remote` (server icon) or `local` (hard drive icon). Cosmetic only. |
| **Base path** | Optional path prefix. When set, the run form shows the prefix as read-only text and only asks the user to enter the subdirectory. The full path stored in the database is `base_path/subdir`. |

**Example:** set base path to `/rcs/groups/mylab/backups` for the *RCS* location. When recording a backup, the user enters `project_xyz/run_001` and the stored path is `/rcs/groups/mylab/backups/project_xyz/run_001`.

Locations with no base path behave as before — the user types the full path. The base path can be set (or updated) at any time from the Settings page; existing run records are not affected.

## Backup reminder

The backup reminder flags runs that have been completed or failed for longer than a configurable number of days without any backup being recorded. When triggered, a warning banner appears on the [Dashboard](dashboard.md) listing the affected runs.

| Setting | Effect |
|---|---|
| **0** | Reminder disabled — no banner is shown |
| **N > 0** | Warn for runs older than N days with no backup |

The default threshold is **30 days**. Change it from the Settings page under **Backup Reminder**. The setting persists in `settings.json` as `backup_reminder_days`.

Only runs with status **Completed** or **Failed** are flagged — Running and Pending runs are excluded because they have not yet produced data worth backing up. Runs tagged `published-data` are also excluded.

### Slack alert

If Slack notifications are enabled, NGS Tracker also posts a daily summary to the **Workflow runs channel** whenever there are overdue runs. The alert fires at most once per calendar day (UTC) and is skipped on days when there are no overdue runs. The date of the last alert is stored in `settings.json` as `last_backup_alert_sent`.

## Snapshot backup

The snapshot backup creates point-in-time copies of the database and uploads directory in a separate location — for example an external drive, a second cloud path, or a network share. Configure it under **Snapshot Backup** in Settings.

| Field | Description |
|---|---|
| **Backup directory** | Full path to the directory where snapshots are written. Leave empty to disable. |
| **Every (hours)** | How often to run an automatic backup. Set to 0 to disable the schedule (manual only). |
| **Keep (copies)** | How many snapshots to retain (DB and upload snapshots); the oldest are pruned automatically. |
| **Cloud backup (rclone remote)** | Optional rclone remote path (e.g. `myremote:mybucket/ngs-tracker`). After every snapshot, the entire local backup directory is mirrored to this remote with `rclone sync`. Leave empty to disable. |

The database snapshot uses SQLite's built-in online backup API, which produces a fully consistent copy even while the app is running — no shutdown required. The snapshot file is gzip-compressed (`.db.gz`).

### Cloud backup via rclone

If a **Cloud backup** remote is configured, NGS Tracker runs `rclone sync` after each snapshot (manual or scheduled), mirroring the full local backup directory — DB snapshots, SHA-256 sidecars, and uploads — to the remote. Pruning is reflected automatically: files deleted locally are also deleted on the remote.

**Requirements:**

- `rclone` must be installed and in `PATH`.
- The remote must already be configured with `rclone config` (e.g. `rclone config` → add Dropbox, S3, Google Drive, etc.).
- The remote path must be writable by the user running NGS Tracker.

**Example remote paths:**

| Backend | Example path |
|---|---|
| Dropbox | `dropbox:ngs-tracker-backup` |
| S3 | `s3:mybucket/ngs-tracker` |
| Google Drive | `gdrive:ngs-tracker` |
| SFTP / RCS | `rcs:~/ngs-tracker-backup` |

rclone failures are non-fatal — if the sync fails, a warning is logged but the local snapshot is always saved and the last-snapshot timestamp is still updated. Check the application log if the cloud badge does not appear after a snapshot.

### Storage structure

**Linux (with rsync):** Each backup writes a timestamped `.db.gz` DB file and a timestamped uploads directory. The uploads snapshot uses `rsync --link-dest` so that unchanged files are stored as hardlinks to the previous snapshot — they use no extra disk space.

```
<backup directory>/
  db/
    ngs_tracker_YYYYMMDD_HHMMSS.db.gz   ← gzip-compressed, up to N kept
    ngs_tracker_YYYYMMDD_HHMMSS.db.gz
    ...
  uploads/
    YYYYMMDD_HHMMSS/   ← full tree at that point (unchanged files are hardlinks)
    YYYYMMDD_HHMMSS/
    ...
```

**Other platforms:** Uploads are compressed into a single `uploads.tar.gz` archive (overwritten on each backup).

```
<backup directory>/
  db/
    ngs_tracker_YYYYMMDD_HHMMSS.db.gz
    ...
  uploads.tar.gz   ← latest uploads, overwritten each run
```

The **Snapshot Now** button (visible once a directory is configured) triggers an immediate backup and shows the result as a flash message. The last backup time is displayed next to the status badge.

The scheduler checks every 10 minutes whether a backup is due — so the actual gap between backups is within 10 minutes of the configured interval.

### Snapshot integrity

Every snapshot is verified immediately after it is written:

1. A **SHA-256 checksum** of the `.db.gz` file is computed and stored alongside it as a `.sha256` sidecar file.
2. The snapshot is decompressed into a temporary file and SQLite's `PRAGMA integrity_check` is run to confirm the database is not corrupt.

The **Restore Snapshot** table shows an **Integrity** badge for each snapshot:

| Badge | Meaning |
|---|---|
| **OK** (green) | SHA-256 verified — file matches the checksum stored at write time |
| **Failed** (red) | SHA-256 mismatch — the file was modified or corrupted after writing |
| **—** (grey) | No checksum stored (snapshot predates integrity checks) |

If any snapshot shows **Failed**, a red warning banner appears at the top of the Restore Snapshot section. Take a fresh snapshot and do not rely on the failed file for recovery.

### Restoring a snapshot

The **Restore Snapshot** table in Settings lists all available snapshots, newest first. Each row shows the timestamp, integrity status, and whether an uploads snapshot is included. Click **Restore** to:

1. Automatically take a safety snapshot of the current state first (so you can undo the restore)
2. Decompress the DB snapshot and write it into the live database — no restart required
3. On Linux: `rsync` the upload snapshot back over the live uploads directory. On other platforms: extract `uploads.tar.gz`.

```{warning}
Restoring overwrites the live database and uploads. A safety snapshot is always saved first, but if critical data is at stake verify that snapshot was written before confirming the restore.
```

```{note}
Your database is already inside Dropbox (`/mnt/4TB_SSD/Dropbox/ngs-tracker/`), giving you continuous cloud sync. Snapshot backup is most useful for a second off-Dropbox copy (e.g. an external drive) or for point-in-time recovery in case a corruption syncs to the cloud before you notice.
```

## Slack notifications

NGS Tracker can post snapshot success and failure messages to a Slack channel via a Slack Bot Token.

### One-time Slack app setup

**1. Create the app**

Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**. Give it a name (e.g. *NGS Tracker*) and select your workspace.

**2. Add Bot Token Scopes**

Under **OAuth & Permissions** → **Bot Token Scopes**, add:

| Scope | Purpose |
|---|---|
| `chat:write` | Post messages to channels and DMs |
| `chat:write.public` | Post to public channels without joining them |

If an `incoming-webhook` scope was added automatically, remove it — it is not needed.

**3. Install the app**

Click **Install to Workspace** and approve the permissions. Once installed, copy the **Bot User OAuth Token** (starts with `xoxb-`) from the **OAuth & Permissions** page.

**4. Create the Slack channels**

Create the channels you want NGS Tracker to post to — for example `#snapshots` and `#workflow_runs`.

**5. Configure NGS Tracker**

Go to **Settings → Slack Notifications**:

- Paste the `xoxb-…` token into **Bot Token**
- Set the **Snapshots channel** name (without `#`)
- Set the **Workflow runs channel** name (without `#`)
- Enable the toggle
- Click **Save**
- Click **Send test message** to verify

### Private channels

`chat:write.public` only covers public channels. If a channel is private, invite the bot from within that channel:

```
/invite @NGS Tracker
```

This must be done for every private channel the bot should post to.

### What is notified automatically

| Event | Channel setting |
|---|---|
| Snapshot succeeded | Snapshots channel |
| Snapshot failed | Snapshots channel |
| Workflow run created via REST API | Workflow runs channel |
| Workflow run status changed via REST API | Workflow runs channel |
| Daily backup-overdue reminder (when runs need backup) | Workflow runs channel |

Snapshot notifications fire on both manual snapshots ("Snapshot Now" button) and scheduled automatic snapshots.

The workflow run message is sent when a run is created via the API **or** when its status is changed via a PATCH request — so runs created via the web form still get a notification when `register_run()` marks them as completed or failed.

The workflow run message includes: project name, researcher, workflow name and tag, workflow system, submitted by, runtime (if available), description, and tags. For failed runs, the Snakemake error block is appended.

The backup reminder lists all overdue runs (project, workflow, status, age in days). It fires at most once per calendar day (UTC) and is skipped on days when there are no overdue runs. Runs tagged `published-data` are excluded.

### Manual run notifications

In addition to automatic notifications, NGS Tracker supports composing and sending a message manually from any workflow run detail page — see [Slack notification](runs.md) in the runs documentation.

### Researcher Slack user ID

To include a proper `@mention` in manual run notification messages, store each researcher's Slack member ID on their profile. To find it in Slack: open the researcher's profile → click **More** → **Copy member ID**. The ID looks like `U012AB3CD`.

Set it by going to the researcher's edit page (**Groups → Researcher → Edit**). Once set, the ID is shown on the researcher detail page and is used automatically when composing a Slack message for any of their runs.

If no Slack user ID is set for a researcher, their plain display name is used in the message instead.

### Settings stored

Slack settings are saved to `~/.ngs-tracker/settings.json`:

| Key | Description |
|---|---|
| `slack_enabled` | Whether notifications are active |
| `slack_token` | Bot User OAuth Token (`xoxb-…`) |
| `slack_snapshot_channel` | Channel name for snapshot events (without `#`) |
| `slack_runs_channel` | Channel name for workflow run registrations (without `#`) |

## Backup locations

Backup locations are the named destinations shown on every run form. Each location has a **type**:

| Type | Icon | Use case |
|---|---|---|
| **Local** | HDD | On-machine or directly attached storage |
| **Remote** | Server | HPC scratch, RCS, RFS, NAS, cloud |

### Managing locations

From the Settings page you can:

- **Add** a location by entering a name and selecting Local or Remote, then clicking Add
- **Remove** a location by clicking × on its badge

Removing a location does not delete backup records from existing runs — historical entries are preserved and shown with a `(removed)` label on the run detail page.

### Default locations

The built-in defaults are:

| Name | Type |
|---|---|
| Local | Local |
| RCS | Remote |
| RFS | Remote |

These are written to `settings.json` on first use and can be freely modified.
