# Audit log

Every create, update, trash, restore, and delete action is appended to a plain-text log file at `~/.ngs-tracker/changes.log`.

## Log format

Each line contains a timestamp, action type, model name, record ID, user, and a human-readable detail string:

```
2025-06-12 14:03:22 | CREATE   | WorkflowRun         | id=42     | user=Niek                 | rna-seq-star-deseq2 (project: KO screen)
2025-06-12 14:05:01 | UPDATE   | WorkflowRun         | id=42     | user=Niek                 | rna-seq-star-deseq2 status=completed
2025-06-12 14:10:44 | CREATE   | AttachedFile        | id=17     | user=Niek                 | config.yaml [config] on run id=42
```

## Rotation

When the log file exceeds **100 MB** it is gzip-archived with a timestamp suffix (e.g. `changes.20250612_140322.log.gz`) and a new file is started. Archived logs remain in `~/.ngs-tracker/` indefinitely.

## In-app log viewer

The **Change Log** page (sidebar link) lets you browse and filter log entries without leaving the browser:

- **User filter** — show entries from a specific user
- **Action filter** — narrow to CREATE / UPDATE / TRASH / DELETE / RESTORE
- **Free-text search** — matches against the model name, record ID, and detail string
- Results are shown most-recent-first, paginated at 100 entries per page
