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

## Backup reminder

The backup reminder flags runs that have been completed or failed for longer than a configurable number of days without any backup being recorded. When triggered, a warning banner appears on the [Dashboard](dashboard.md) listing the affected runs.

| Setting | Effect |
|---|---|
| **0** | Reminder disabled — no banner is shown |
| **N > 0** | Warn for runs older than N days with no backup |

The default threshold is **30 days**. Change it from the Settings page under **Backup Reminder**. The setting persists in `settings.json` as `backup_reminder_days`.

Only runs with status **Completed** or **Failed** are flagged — Running and Pending runs are excluded because they have not yet produced data worth backing up.

## Snapshot backup

The snapshot backup creates point-in-time copies of the database and a mirror of the uploads directory in a separate location — for example an external drive, a second cloud path, or a network share. Configure it under **Snapshot Backup** in Settings.

| Field | Description |
|---|---|
| **Backup directory** | Full path to the directory where snapshots are written. Leave empty to disable. |
| **Every (hours)** | How often to run an automatic backup. Set to 0 to disable the schedule (manual only). |
| **Keep (copies)** | How many DB snapshots to retain; the oldest are pruned automatically. Uploads are mirrored (single copy, overwritten each run). |

The database snapshot uses SQLite's built-in online backup API, which produces a fully consistent copy even while the app is running — no shutdown required.

Each automatic or manual backup writes:

```
<backup directory>/
  db/
    ngs_tracker_YYYYMMDD_HHMMSS.db   ← timestamped, up to N kept
    ngs_tracker_YYYYMMDD_HHMMSS.db
    ...
  uploads/                            ← mirrored copy, updated each run
```

The **Snapshot Now** button (visible once a directory is configured) triggers an immediate backup and shows the result as a flash message. The last backup time is displayed next to the status badge.

The scheduler checks every 10 minutes whether a backup is due — so the actual gap between backups is within 10 minutes of the configured interval.

```{note}
Your database is already inside Dropbox (`/mnt/4TB_SSD/Dropbox/ngs-tracker/`), giving you continuous cloud sync. Snapshot backup is most useful for a second off-Dropbox copy (e.g. an external drive) or for point-in-time recovery in case a corruption syncs to the cloud before you notice.
```

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
