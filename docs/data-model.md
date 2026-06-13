# Data model

NGS Tracker organises data in a four-level hierarchy:

```
Research Group
└── Researcher
    └── Project
        ├── Workflow Run
        │   ├── Sample Sheet  (CSV, displayed as a scrollable table)
        │   ├── Attached Files  (config, QC, results, sample info, other)
        │   └── Linked Samples  (confirmed from the sample sheet)
        ├── Sample  (per-sample run history across all runs)
        └── Custom Analysis Script
            └── Script Output Files
```

Every level has its own detail page with breadcrumb navigation back up the tree.

## Research Groups

A Research Group is the top-level container. Each group shows a summary of its researchers, project count, run count, and total disk usage.

## Researchers

A Researcher belongs to one group. The researcher detail page lists all their projects with per-project disk usage and links to export the researcher's full run history.

## Projects

A Project belongs to one researcher and is the primary unit for organising related workflow runs. Projects can be marked as **Published** with an optional publication URL.

The project detail page shows:
- All workflow runs with dates, statuses, and tags
- All named samples with links to their run histories
- Custom analysis scripts and their output files
- Total disk usage across all attached files
- An **Export** dropdown (CSV or Markdown)

## Samples

After a sample sheet is uploaded to a run and the confirmation step is completed, each named sample becomes a first-class record inside the project. The sample detail page shows a full chronological history of every workflow run that included that sample — useful for tracing a sample from raw data through QC, alignment, and variant calling.

- The same sample name across multiple runs within a project is treated as the same sample
- Samples can be renamed or deleted from their detail page
- Re-confirming after a sample sheet re-upload does not create duplicates
- All project samples appear as clickable badges on the project detail page

## Custom Analysis Scripts

Scripts can be uploaded to a project (Python, R, Shell, Bash, Perl, MATLAB, Julia, Jupyter — auto-detected from the file extension). Each script can have multiple output files attached, with an optional description.

Scripts are soft-deleted to the trash like all other records.
