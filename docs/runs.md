# Workflow runs

A Workflow Run is the core record in NGS Tracker. It belongs to a project and captures everything about a single pipeline execution.

## Creating a run

When creating or editing a run you can fill in:

| Field | Notes |
|---|---|
| **Project** | Required. Cannot be changed after creation. |
| **Run date** | Defaults to today. |
| **Status** | Completed / Running / Pending / Failed |
| **Workflow** | Selected from the registered workflow list |
| **Release tag** | Fetched live from GitHub after a workflow is chosen |
| **Description** | Short free-text summary |
| **Tags** | Tick from the default list; add new tags inline |
| **Notes** | Long-form Markdown text |
| **Backup status** | Per-location checkboxes with optional storage path |

## Workflow system badge

When a workflow is selected in the form, a coloured pill badge immediately shows the workflow system — Snakemake (green), Nextflow (orange), CWL (blue), or Other (grey). The badge also appears on the run detail page next to the workflow name.

## Run templates

Any run can be saved as a named template (**Save as Template** button on the detail page). Templates store the workflow name, release tag, and description. They appear in a picker at the top of the new-run form.

Templates are stored in `~/.ngs-tracker/run_templates.json` and managed via the **Workflows** page.

## Cloning a run

The **Clone** button on a run detail page copies all settings (workflow, tag, description, tags, notes, backup locations) into a new run with status set to **Pending**. Use this for re-running a pipeline with the same parameters.

## Config files

Upload a YAML or JSON config/params file using the **Config** file type. If the file parses as a dictionary, it is displayed as a **collapsible tree** on the run detail page:

- Top-level keys are expanded by default
- Nested keys are shown inside `<details>` elements — click to expand
- A **Collapse all / Expand all** button controls the entire tree at once
- The raw file is always available for download

Files that do not parse as YAML/JSON (e.g. a Nextflow Groovy `.config` file) are stored and available for download but no tree is shown.

### Config diff

When a run has a parsed config, a **Compare Config** button appears on the detail page. Select any other run that also has a parsed config and the comparison page shows a three-column table:

| Colour | Meaning |
|---|---|
| Yellow | Value changed between the two runs |
| Red | Key only in run A (removed) |
| Green | Key only in run B (added) |
| Plain | Identical in both |

Nested keys are flattened to dot-notation (e.g. `params.threads`). A **Hide unchanged** toggle collapses identical rows.

## Sample sheets

Upload a CSV or TSV sample sheet via the **Upload CSV** button on the run detail page. After upload:

1. You are taken to a confirmation page
2. Choose which column contains the sample names
3. Rename entries if needed
4. Click **Confirm** to link the samples to the run and create sample records in the project

The sample sheet is rendered as a full scrollable table with a sticky header on the run detail page.

## File attachments

Multiple files can be uploaded at once. Each batch is assigned a **type** and an optional description:

| Type | Typical contents |
|---|---|
| Config | YAML/JSON pipeline config or params file |
| Sample Info | Metadata spreadsheets |
| QC | MultiQC HTML, FastQC reports |
| Results | Count matrices, VCF files, peak calls |
| Other | Anything else |

Images (PNG, JPG, SVG, WEBP, …) and PDFs open in an **inline lightbox** — no download required.

## Tags

Tags are free-text labels shared across all runs. A default list is maintained in Settings. When creating or editing a run:

- Tick tags from the default list
- Type a new tag to add it to the defaults automatically and select it
- Tags appear as clickable badges on the run detail page and link to a filtered view of all runs with that tag

## Backup status

Each run records which backup locations hold a copy, along with an optional storage path for each. Locations are configured in [Settings](settings.md).

The run detail page shows a check or cross for every configured location. Locations that have been removed from the config but were recorded on historical runs appear with a `(removed)` label — the data is preserved.

## Notes

The notes field supports full **Markdown** formatting — headings, bullet lists, numbered lists, code blocks (fenced and inline), bold/italic, links, blockquotes, and tables. Notes are rendered in the browser when viewing the run.

## Export

Every project, researcher, and group detail page has an **Export** dropdown. The generated file covers all workflow runs with these columns: Group, Researcher, Project, Run Date, Workflow, Tag, Status, Backup, Tags, Notes, Samples, Files.

| Format | Use case |
|---|---|
| **CSV** | Import into Excel, R, or Python for further analysis |
| **Markdown** | Paste into a lab notebook, grant report, or email to a PI |

## Filtering by status

The runs list can be filtered to show only runs with a specific status. Click any segment of the **Status breakdown** donut on the [Dashboard](dashboard.md), or navigate directly:

```
/runs?status=completed
/runs?status=failed
/runs?status=running
/runs?status=pending
```

A dismissible banner at the top of the list shows the active status filter. Click **clear filter** to return to the full list.

You can combine a status filter with a tag filter:

```
/runs?status=failed&tag=RNA-seq
```

## Pagination

The runs list shows **50 runs per page**. When there are more than 50 runs, a page count (`Showing X–Y of Z`) appears below the page heading and Bootstrap pagination controls appear below the table.

The current page, sort column, sort direction, tag filter, and status filter are all preserved in pagination links — navigating between pages does not reset your filters or sort order.

Pagination is also supported via the [REST API](api.md) when querying `/api/runs`.
