# Workflows & templates

## Workflow registry

Workflows are stored in `~/.ngs-tracker/workflows.yaml` and pre-populated from a built-in default list (all Snakemake pipelines) on first run. Each entry has the following fields:

```yaml
- name: rna-seq-star-deseq2
  url: https://github.com/niekwit/rna-seq-star-deseq2
  local_path: ""
  system: snakemake
  mapping_rate_cutoff: 60.0

- name: private-chip-seq
  url: ""
  local_path: /home/you/repos/chip-seq-pipeline
  system: snakemake
  mapping_rate_cutoff: 60.0
```

Manage workflows from the **Workflows** page in the sidebar or by editing the YAML file directly.

## Workflow systems

Four systems are supported:

| System | Badge colour | Notes |
|---|---|---|
| `snakemake` | Green | Default for all built-in workflows |
| `nextflow` | Orange | |
| `cwl` | Blue | |
| `other` | Grey | For any other workflow manager |

Existing entries in `workflows.yaml` that predate this field are automatically migrated to `snakemake` on first read.

When a workflow is selected in the new/edit run form, the matching coloured badge appears immediately below the dropdown. The same badge is shown on the run detail page next to the workflow name, and in the workflow list table on the Workflows page.

## Private repository support

For workflows hosted in private GitHub repositories, provide a **local path** to a clone of the repo instead of (or in addition to) a GitHub URL:

- Leave the **GitHub URL** field blank.
- Enter the full absolute path to the local clone in **Local repo path** (e.g. `/home/you/repos/chip-seq-pipeline`).
- The path must exist and be a valid git repository. NGS Tracker validates this when you save the workflow.

The folder icon appears next to the workflow name in the Workflows table for local-path entries. On the run detail page, no clickable badge link is shown (since there is no public URL).

## Release tag selection

When creating or editing a run, NGS Tracker automatically populates the **Release tag** dropdown depending on how the workflow is configured:

- **GitHub URL (public repos):** tags are fetched live from the GitHub API (releases, then tags, then recent commits as a fallback).
- **Local path (private repos):** tags are read locally from the cloned repo via `git tag`. If the repo has no tags, the 10 most recent commits are shown instead.

The selected tag is stored with the run. For public repos it is shown as a linked badge on the detail page — clicking it opens that release on GitHub. For local-path repos it is shown as a plain badge.

If neither source is available the dropdown shows an explanatory message.

## Mapping rate cutoff

Each workflow has a configurable **mapping rate cutoff** (default: **60 %**). This threshold is used when a [Mapping Rates](runs.md) CSV is attached to a run of that workflow — samples whose alignment rate falls below the cutoff are highlighted in a warning banner and marked in red on the chart.

Change the cutoff for any workflow from the **Workflows** page by editing the percentage field next to the workflow name. The value is stored in `workflows.yaml` as `mapping_rate_cutoff`.

## Run templates

Any workflow run can be saved as a reusable template via the **Save as Template** button on its detail page. A template stores:

- Template name (e.g. "Standard RNA-seq v2.1")
- Workflow name
- Release tag
- Description

Templates are listed on the **Workflows** page and can be loaded from the picker at the top of the new-run form to pre-fill those fields. They are stored in `~/.ngs-tracker/run_templates.json`.
