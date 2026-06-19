# Statistics

The Statistics page (`/stats`, **Statistics** in the sidebar) provides cross-run charts
that summarise pipeline usage and performance across the entire database.

## Workflow Runs per Month

A bar chart of workflow run activity over the last 12 calendar months, covering all
non-trashed runs regardless of status.

## Published Projects per Research Group

A bar chart showing how many projects have been marked as **published** for each research
group, sorted from most to least. Each bar is coloured distinctly per group. Hovering
over a bar shows the exact count. Groups with no published projects are not shown.

## Executions per Workflow

A bar chart showing the total number of runs (all statuses, non-trashed) recorded for
each workflow, sorted from most to least executed. Use this to see which pipelines are
run most frequently across all researchers and projects.

## Average Runtime per Workflow

A bar chart of the mean wall-clock runtime for each workflow, derived from runs that
have a recorded `runtime_seconds` value. Runs without runtime data (e.g. those created
manually or via the API without a log file) are excluded from this average.

The Y axis is labelled in minutes; ticks above 60 minutes are displayed in hours
(e.g. `14.6 h`). Hovering over a bar shows the exact formatted runtime
(e.g. `14h 33m 58s`) and the number of runs the average is based on.

### Recording runtime automatically

Runtime is captured from the Snakemake main log file and sent to the tracker when you
call `register_run()` from a `onsuccess` / `onerror` block:

```python
onsuccess:
    from ngs_tracker import register_run
    register_run(config, log_file=log)   # 'log' is Snakemake's built-in log path
```

See {doc}`api` for full details on the Python client and the `log_file` parameter.

```{note}
If no runs have runtime data yet, the average runtime chart is not shown and an
informational message is displayed instead.
```

## Runtime Trend per Workflow

A line chart showing how the runtime of a single workflow evolves across successive runs,
ordered chronologically. Use it to spot regressions after updating a pipeline or to track
the effect of parameter changes on wall-clock time.

A **workflow selector** dropdown in the card header lets you switch between all workflows
that have at least one run with recorded runtime. The X-axis labels show the run date; if
a workflow tag (version) is recorded for a run it is appended in parentheses (e.g.
`2025-06-14 (v1.2.0)`).

Hovering over a data point shows:
- Run date and project name
- Exact formatted runtime (e.g. `2h 4m 17s`)
- Run ID

Clicking a point navigates directly to that run's detail page.
