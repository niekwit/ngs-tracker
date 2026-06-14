# NGS Tracker

A browser-based web app for tracking bioinformatics projects and workflow analyses.
Data is organised as **Research Group → Researcher → Project → Workflow Run**, with support
for sample tracking, custom scripts, file attachments, backup status, and publication tracking.

---

## Features at a glance

**Project hierarchy**
: Research Groups → Researchers → Projects → Workflow Runs — each level with its own detail page, disk usage summary, and export.

**Multi-system workflow support**
: Register workflows from Snakemake, Nextflow, CWL, or Other systems. Each run carries a coloured system badge throughout the UI.

**Config viewer & diff**
: Upload YAML/JSON config files — they are parsed and rendered as a collapsible tree. Compare two run configs side-by-side with colour-coded differences.

**Sample tracking**
: Upload a CSV sample sheet per run. A confirmation step links named samples to the run and builds a cross-run history for each sample.

**Backup tracking**
: Per-run backup status across user-defined locations, each tagged as local or remote.

**Run templates**
: Save a run as a named template (workflow + tag + description) and load it when creating future runs.

**Export**
: Download project, researcher, or group summaries as CSV or Markdown — ready for grant reports or PI emails.

**Dashboard**
: Live stats, status breakdown donut (click any slice to filter runs), backup coverage panel, and file-type pie chart.

**Statistics**
: Cross-run charts showing execution counts and average wall-clock runtime per registered workflow, populated automatically when `register_run()` is called with the Snakemake log file.

**Audit log**
: Every action is written to a plain-text change log with user attribution, filterable in the browser.

**REST API**
: A JSON API at `/api/` lets you register and update workflow runs from Snakemake `onsuccess` blocks, Nextflow `workflow.onComplete` handlers, SLURM epilogues, or any script. Authentication via a per-installation API key shown in Settings.

---

```{toctree}
:maxdepth: 2
:hidden:
:caption: Getting started

installation
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Using NGS Tracker

data-model
runs
workflows
settings
audit-log
dashboard
stats
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Automation

api
```

```{toctree}
:maxdepth: 1
:hidden:
:caption: Deployment

startup
updating
```
