# Workflows & templates

## Workflow registry

Workflows are stored in `~/.ngs-tracker/workflows.yaml` and pre-populated from a built-in default list (all Snakemake pipelines) on first run. Each entry has three fields:

```yaml
- name: rna-seq-star-deseq2
  url: https://github.com/niekwit/rna-seq-star-deseq2
  system: snakemake

- name: my-nf-pipeline
  url: https://github.com/some-org/my-nf-pipeline
  system: nextflow

- name: variant-calling-cwl
  url: https://github.com/some-org/variant-calling-cwl
  system: cwl
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

## GitHub release tags

When a workflow with a GitHub URL is selected, NGS Tracker fetches its releases (or tags if no releases exist) live from the GitHub API and populates a **Release tag** dropdown. The selected tag is stored with the run and shown as a linked badge on the detail page — clicking it opens that release on GitHub.

If the GitHub API is unreachable the dropdown falls back to a plain text input.

## Mapping rate cutoff

Each workflow has a configurable **mapping rate cutoff** (default: **60 %**). This threshold is used when a [Mapping Rates](runs.md#mapping-rates) CSV is attached to a run of that workflow — samples whose alignment rate falls below the cutoff are highlighted in a warning banner and marked in red on the chart.

Change the cutoff for any workflow from the **Workflows** page by editing the percentage field next to the workflow name. The value is stored in `workflows.yaml` as `mapping_rate_cutoff`.

## Run templates

Any workflow run can be saved as a reusable template via the **Save as Template** button on its detail page. A template stores:

- Template name (e.g. "Standard RNA-seq v2.1")
- Workflow name
- Release tag
- Description

Templates are listed on the **Workflows** page and can be loaded from the picker at the top of the new-run form to pre-fill those fields. They are stored in `~/.ngs-tracker/run_templates.json`.
