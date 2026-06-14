# Search

The search box in the top navigation bar searches across all entities in NGS Tracker.

## What is searched

| Entity | Fields searched |
|---|---|
| Research Groups | Name, description |
| Researchers | Name, email |
| Projects | Name, description |
| Workflow Runs | Workflow name, description, tags, **notes** |
| Scripts | Filename, description |

Type any term and press Enter (or click the search icon). Matches are shown grouped by entity type with a count badge per group.

## Notes full-text search

When a workflow run matches because of content in its **Notes** field, the result shows:

- An **in notes** badge to distinguish it from a name/description match
- A highlighted excerpt from the notes with the matching term wrapped in a yellow highlight

The excerpt is approximately 140 characters centred on the first match. Raw Markdown syntax may appear in the excerpt — the full rendered notes are visible on the run detail page.

## Search behaviour

- Search is **case-insensitive**.
- Search matches any **substring** — e.g. `ATAC` matches `ATAC-seq`, `atacseq`, and `Paired-end ATAC`.
- Workflow runs are returned sorted by date (most recent first).
- Only non-trashed records are returned.
