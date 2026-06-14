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

Tags are free-text labels attached to workflow runs. The default list is shown as a checkbox picker when creating or editing a run. New tags typed inline are added to the list automatically.

- **Add** a tag from the Settings page
- **Remove** a tag by clicking × on its badge

Removing a tag from the defaults does not affect runs that already use it.

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
