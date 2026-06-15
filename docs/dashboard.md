# Dashboard, search & trash

## Dashboard

The dashboard (`/`) is the home page. It provides a live overview of the entire database.

### Stats row

Five summary cards at the top show total counts for Groups, Researchers, Projects, Runs, and Files. Clicking the **Files** card opens a pie chart broken down by file type (Config, QC, Results, etc.).

### Groups panel

A quick-reference list of all research groups with researcher and project counts, linking directly to each group's detail page.

### Recent runs

The eight most recently added workflow runs, with links to the run and its parent project.

### Status breakdown

A donut chart showing run counts by status:

| Segment | Colour |
|---|---|
| Completed | Green |
| Running | Yellow |
| Pending | Grey |
| Failed | Red |

Click any slice to navigate to the runs list filtered by that status. The cursor changes to a pointer when hovering over a slice to indicate it is clickable.

### Backup reminder

When the backup reminder is enabled (configured in [Settings](settings.md#backup-reminder)), a warning banner appears at the top of the dashboard listing every completed or failed run that has no backup recorded and is older than the configured threshold. Each entry links directly to the run's detail page so backup status can be updated immediately.

The banner is hidden when there are no overdue runs or when the reminder is disabled (threshold = 0).

Runs tagged **published-data** are excluded from the reminder entirely, as publicly available data does not require a separate backup.

### Backup coverage

A progress bar showing the percentage of runs with at least one backup location recorded, followed by a per-location breakdown using your configured backup locations.

When runs are missing a backup, the progress bar is clickable — a modal opens listing every unprotected run with links to the run and its parent project. A red **N without backup** link next to the coverage summary provides the same shortcut.

Runs tagged **published-data** are excluded from all backup coverage calculations (count, percentage, per-location totals, and the unprotected-runs modal), since publicly available data is considered inherently accessible without a dedicated backup.

---

## Search

The search box in the navbar searches all record types simultaneously:

- Research Groups (name, description)
- Researchers (name, email)
- Projects (name, description)
- Workflow Runs (workflow name, description, notes)
- Samples (name, description)
- Scripts (filename, description)

Results are grouped by type and link directly to each record.

---

## Trash

Clicking **Delete** on any record moves it to the trash rather than permanently removing it. Access the trash via the **Trash** link in the sidebar.

From the trash you can:

- **Restore** — return the record to its normal location
- **Delete** — permanently remove the record and all its associated files from disk
- **Empty Trash** — permanently remove everything in the trash at once

```{warning}
Permanent deletion removes files from disk and cannot be undone.
```
