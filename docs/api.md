# REST API

NGS Tracker exposes a JSON REST API at `/api/`. Use it to create and update workflow runs from pipeline scripts, CI jobs, or any automation tool.

## Authentication

Every endpoint except `/api/health` requires an API key.

Pass the key in one of two ways:

```
X-Api-Key: <your-key>
```

or as a query parameter:

```
GET /api/runs?api_key=<your-key>
```

### Getting your API key

Your API key is shown on the **Settings** page (gear icon in the navbar), in the **REST API Key** section. Click the copy button to copy it to the clipboard.

### Rotating the key

Click **Rotate key** on the Settings page. All scripts using the old key will need updating — the old key stops working immediately.

The key is a 256-bit URL-safe random string generated with Python's `secrets.token_urlsafe(32)` and stored in `~/.ngs-tracker/settings.json`.

---

## Base URL

```
http://127.0.0.1:5000/api
```

Change host/port via `NGS_HOST` and `NGS_PORT` environment variables (see [Installation](installation.md)).

---

## Endpoints at a glance

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | No | Liveness check |
| `GET` | `/api/runs` | Yes | List workflow runs |
| `GET` | `/api/runs/<id>` | Yes | Get a single run |
| `POST` | `/api/runs` | Yes | Create a new run |
| `PATCH` | `/api/runs/<id>` | Yes | Update a run |
| `POST` | `/api/runs/<id>/files` | Yes | Attach a file from disk to a run |
| `GET` | `/api/projects` | Yes | List projects |
| `GET` | `/api/researchers` | Yes | List researchers |

---

## Error responses

All errors return JSON with an `error` key:

```json
{"error": "Unauthorized — provide a valid X-Api-Key header"}
```

| HTTP status | Meaning |
|-------------|---------|
| `400` | Bad request — missing required field or invalid value |
| `401` | Missing or incorrect API key |
| `404` | Record not found |

---

## `GET /api/health`

No authentication required. Use this to check that the server is reachable.

**Response**

```json
{"status": "ok"}
```

**curl**

```bash
curl http://127.0.0.1:5000/api/health
```

---

## `GET /api/runs`

List all workflow runs, newest first.

**Query parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `completed`, `running`, `pending`, `failed` |
| `project_id` | integer | Filter by project ID |
| `researcher_id` | integer | Filter by researcher ID |

**Response** — array of [run objects](#run-object)

**curl**

```bash
# All runs
curl -H "X-Api-Key: $KEY" http://127.0.0.1:5000/api/runs

# Only failed runs
curl -H "X-Api-Key: $KEY" "http://127.0.0.1:5000/api/runs?status=failed"

# Runs for project 3
curl -H "X-Api-Key: $KEY" "http://127.0.0.1:5000/api/runs?project_id=3"
```

**Python**

```python
import requests

KEY = "your-api-key"
BASE = "http://127.0.0.1:5000/api"
headers = {"X-Api-Key": KEY}

runs = requests.get(f"{BASE}/runs", headers=headers).json()
failed = [r for r in runs if r["status"] == "failed"]
```

---

## `GET /api/runs/<id>`

Get a single workflow run by its integer ID.

**Response** — a single [run object](#run-object)

**curl**

```bash
curl -H "X-Api-Key: $KEY" http://127.0.0.1:5000/api/runs/42
```

---

## `POST /api/runs`

Create a new workflow run.

**Request body** — JSON

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_id` | integer | Yes* | — | ID of the project this run belongs to |
| `project` | string | Yes* | — | Project name (alternative to `project_id`) |
| `workflow_name` | string | No | `""` | Name of the workflow |
| `workflow_tag` | string | No | `""` | Release tag (e.g. `v2.1.0`) |
| `workflow_system` | string | No | `"snakemake"` | One of `snakemake`, `nextflow`, `cwl`, `other` |
| `status` | string | No | `"completed"` | One of `completed`, `running`, `pending`, `failed` |
| `description` | string | No | `""` | Short free-text summary |
| `notes` | string | No | `""` | Long-form Markdown notes |
| `tags` | array of strings | No | `[]` | Tag labels |
| `run_date` | string | No | now | ISO 8601 datetime (e.g. `2025-06-14T09:00:00`) |
| `created_by` | string | No | `""` | Name of the user creating the run |
| `backups` | array of objects | No | `[]` | Backup records (see below) |

*Provide either `project_id` or `project` (name string); `project_id` takes precedence.

**Backup object**

```json
{"location": "RCS", "path": "/rcs/scratch/jones/rna-seq-2025"}
```

`location` must match one of the configured backup location names in Settings.

**Response** — the created [run object](#run-object), HTTP `201`

**curl**

```bash
curl -X POST http://127.0.0.1:5000/api/runs \
  -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "RNA-seq timecourse",
    "workflow_name": "rna-seq-pipeline",
    "workflow_tag": "v2.1.0",
    "workflow_system": "snakemake",
    "status": "completed",
    "description": "6-timepoint timecourse, n=3",
    "tags": ["RNA-seq", "timecourse"],
    "run_date": "2025-06-14T09:00:00"
  }'
```

**Python**

```python
resp = requests.post(
    f"{BASE}/runs",
    headers=headers,
    json={
        "project_id": 3,
        "workflow_name": "chip-seq-pipeline",
        "workflow_tag": "v1.3.0",
        "workflow_system": "snakemake",
        "status": "completed",
        "tags": ["ChIP-seq", "H3K27ac"],
    },
)
run = resp.json()
print(f"Created run {run['id']}")
```

---

## `PATCH /api/runs/<id>`

Update an existing run. Only the fields you provide are changed.

**Request body** — JSON (all fields optional)

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | New status: `completed`, `running`, `pending`, `failed` |
| `description` | string | Replaces the current description |
| `notes` | string | Replaces the current notes (Markdown) |
| `workflow_tag` | string | Replaces the current release tag |
| `tags` | array of strings or comma-string | Replaces current tags |
| `backups` | array of objects | Replaces current backup records |

**Response** — the updated [run object](#run-object)

**curl**

```bash
# Mark a run as failed
curl -X PATCH http://127.0.0.1:5000/api/runs/42 \
  -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "failed", "notes": "Job crashed at step 3 — out of memory."}'

# Add a backup record
curl -X PATCH http://127.0.0.1:5000/api/runs/42 \
  -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"backups": [{"location": "RCS", "path": "/rcs/scratch/jones/chip-2025"}]}'
```

**Python**

```python
requests.patch(
    f"{BASE}/runs/42",
    headers=headers,
    json={"status": "completed", "workflow_tag": "v2.1.1"},
)
```

---

## `POST /api/runs/<id>/files`

Attach a file that already exists on the server's filesystem to a workflow run. This is the recommended way to record output files from a Snakemake or Nextflow pipeline — the pipeline knows its output paths, so there is no need to re-upload them over HTTP.

The file is **copied** into NGS Tracker's storage directory. The original file is not moved or deleted.

**Request body** — JSON

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file_path` | string | Yes | — | Absolute path to the file on disk |
| `file_type` | string | No | `"other"` | One of `config`, `sample_info`, `qc`, `results`, `other` |
| `description` | string | No | `""` | Short label shown in the UI |

**Response** — a [file object](#file-object), HTTP `201`

**curl**

```bash
curl -X POST http://127.0.0.1:5000/api/runs/42/files \
  -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/home/user/projects/rna-seq/results/multiqc_report.html",
    "file_type": "qc",
    "description": "MultiQC report"
  }'
```

**Snakemake `onsuccess` example**

```python
# Snakefile
onsuccess:
    import requests

    base = "http://127.0.0.1:5000/api"
    key  = os.environ["NGS_TRACKER_KEY"]
    headers = {"X-Api-Key": key}

    # First create the run record
    run = requests.post(f"{base}/runs", headers=headers, json={
        "project_id": NGS_PROJECT_ID,
        "workflow_name": "rna-seq-pipeline",
        "workflow_tag": config["workflow_tag"],
        "status": "completed",
    }).json()
    run_id = run["id"]

    # Then attach output files
    output_files = [
        ("/path/to/results/multiqc_report.html", "qc",      "MultiQC report"),
        ("/path/to/results/counts.tsv",           "results", "DESeq2 count matrix"),
        ("/path/to/config/config.yaml",            "config",  "Pipeline config"),
    ]
    for path, ftype, desc in output_files:
        requests.post(f"{base}/runs/{run_id}/files", headers=headers, json={
            "file_path": path,
            "file_type": ftype,
            "description": desc,
        })
```

---

## `GET /api/projects`

List all projects, ordered by group → researcher → project name.

**Response** — array of [project objects](#project-object)

**curl**

```bash
curl -H "X-Api-Key: $KEY" http://127.0.0.1:5000/api/projects
```

---

## `GET /api/researchers`

List all researchers, ordered by group → name.

**Response** — array of [researcher objects](#researcher-object)

**curl**

```bash
curl -H "X-Api-Key: $KEY" http://127.0.0.1:5000/api/researchers
```

---

## Response schemas

(file-object)=
### File object

Returned by `POST /api/runs/<id>/files`.

```json
{
  "id": 17,
  "workflow_run_id": 42,
  "original_filename": "multiqc_report.html",
  "file_type": "qc",
  "type_label": "QC",
  "description": "MultiQC report",
  "uploaded_at": "2025-06-14T09:15:00"
}
```

(run-object)=
### Run object

```json
{
  "id": 42,
  "project_id": 3,
  "project": "RNA-seq timecourse",
  "researcher": "Alice Johnson",
  "group": "Jones Lab",
  "workflow_name": "rna-seq-pipeline",
  "workflow_tag": "v2.1.0",
  "workflow_system": "snakemake",
  "description": "6-timepoint timecourse, n=3",
  "status": "completed",
  "run_date": "2025-06-14T09:00:00",
  "tags": ["RNA-seq", "timecourse"],
  "notes": "## Results\n\nAll samples passed QC.",
  "backups": [
    {"location": "RCS", "path": "/rcs/scratch/jones/rna-seq-2025"}
  ],
  "created_by": "alice"
}
```

(project-object)=
### Project object

```json
{
  "id": 3,
  "name": "RNA-seq timecourse",
  "description": "6-hour TNF-alpha timecourse in HeLa cells",
  "researcher_id": 1,
  "researcher": "Alice Johnson",
  "group": "Jones Lab",
  "published": false,
  "publication_url": ""
}
```

(researcher-object)=
### Researcher object

```json
{
  "id": 1,
  "name": "Alice Johnson",
  "email": "alice@example.ac.uk",
  "group_id": 1,
  "group": "Jones Lab"
}
```

---

## Pipeline integration

### Snakemake — using the `ngs_tracker` client (recommended)

NGS Tracker ships a lightweight Python client in the `ngs_tracker/` package.
Install it directly from GitHub into your workflow's conda environment — it only
requires `requests`, nothing from the web server stack:

```bash
pip install git+https://github.com/niekwit/ngs-tracker.git
```

**Step 1 — add an `ngs_tracker` block to your workflow's `config.yaml`**

```yaml
ngs_tracker:
  enabled: true                           # set to false to skip registration

  # Connection
  base_url: "http://127.0.0.1:5000/api"  # change host/port if needed

  # Run identity  (find project_id on the project detail page)
  project_id: 3
  workflow_name: "rna-seq-pipeline"
  workflow_tag: "v2.1.0"
  workflow_system: "snakemake"            # snakemake | nextflow | cwl | other
  description: "Full timecourse run"
  tags:
    - RNA-seq
    - timecourse

  # Files to attach — paths relative to the working directory or absolute
  # type: config | sample_info | qc | results | mapping_rates | other
  files:
    - path: "config/config.yaml"
      type: config
      description: "Pipeline config"
    - path: "results/qc/multiqc_report.html"
      type: qc
      description: "MultiQC report"
    - path: "results/counts/all_counts.tsv"
      type: results
      description: "Count matrix"
    - path: "results/mapping_rates.csv"
      type: mapping_rates
      description: "STAR alignment mapping rates"
```

A fully commented template is included in the package at
`ngs_tracker/example_config.yaml`.

**Step 2 — add `onsuccess` / `onerror` to your `Snakefile`**

```python
onsuccess:
    from ngs_tracker import register_run
    register_run(config)

onerror:
    from ngs_tracker import register_run
    register_run(config, status="failed")
```

**Step 3 — just run**

```bash
snakemake --cores 8
```

The API key and current user are read automatically from
`~/.ngs-tracker/settings.json` — the same file NGS Tracker writes on first
startup. No environment variables are needed on a machine where NGS Tracker
has been started at least once.

If you need to override (e.g. running on an HPC node that doesn't share your
home directory), set:

```bash
export NGS_TRACKER_KEY="your-api-key"   # shown in Settings → REST API Key
export NGS_TRACKER_USER="alice"         # optional — overrides the stored user
```

The client prints progress to stderr prefixed with `[ngs-tracker]` and
**never raises an exception** — if the server is unreachable or a file is
missing the run continues normally and a warning is printed instead.

**Credential resolution order** (first match wins):

| | API key | User |
|--|---------|------|
| 1 | `NGS_TRACKER_KEY` env var | `NGS_TRACKER_USER` env var |
| 2 | `~/.ngs-tracker/settings.json` | `~/.ngs-tracker/settings.json` |
| 3 | `api_key:` in config YAML | `created_by:` in config YAML |

---

### Snakemake — manual (no install required)

If you prefer not to install the package, paste this directly into your
`Snakefile`:

```python
onsuccess:
    import os, requests, datetime
    _base = "http://127.0.0.1:5000/api"
    _hdrs = {"X-Api-Key": os.environ["NGS_TRACKER_KEY"]}
    run = requests.post(f"{_base}/runs", headers=_hdrs, json={
        "project_id": 3,                         # find on project page
        "workflow_name": "rna-seq-pipeline",
        "workflow_tag": config.get("workflow_tag", ""),
        "status": "completed",
    }).json()
    run_id = run["id"]
    for path, ftype, desc in [
        ("results/qc/multiqc_report.html", "qc",      "MultiQC report"),
        ("results/counts/all_counts.tsv",  "results", "Count matrix"),
        ("config/config.yaml",             "config",  "Pipeline config"),
    ]:
        requests.post(f"{_base}/runs/{run_id}/files", headers=_hdrs, json={
            "file_path": str(__import__("pathlib").Path(path).resolve()),
            "file_type": ftype,
            "description": desc,
        })

onerror:
    import os, requests
    requests.post("http://127.0.0.1:5000/api/runs",
        headers={"X-Api-Key": os.environ["NGS_TRACKER_KEY"]},
        json={"project_id": 3, "workflow_name": "rna-seq-pipeline",
              "status": "failed"})
```

### Nextflow — register a run on completion

Add a `workflow.onComplete` handler to your `main.nf`:

```groovy
// main.nf
def ngsBase    = "http://127.0.0.1:5000/api"
def ngsKey     = System.getenv("NGS_TRACKER_KEY") ?: ""
def ngsProject = 3   // set to your project ID

workflow.onComplete {
    def status = workflow.success ? "completed" : "failed"
    def payload = groovy.json.JsonOutput.toJson([
        project_id    : ngsProject,
        workflow_name : workflow.scriptName,
        workflow_tag  : workflow.manifest.version ?: "",
        workflow_system: "nextflow",
        status        : status,
        run_date      : workflow.complete.toString(),
        description   : params.description ?: "",
    ])
    def conn = new URL("${ngsBase}/runs").openConnection()
    conn.requestMethod = "POST"
    conn.setRequestProperty("Content-Type", "application/json")
    conn.setRequestProperty("X-Api-Key", ngsKey)
    conn.doOutput = true
    conn.outputStream.write(payload.bytes)
    conn.responseCode  // trigger the request
}
```

### SLURM job epilogue

Register a run from a SLURM job script's epilogue step:

```bash
#!/bin/bash
#SBATCH --job-name=chip-seq
#SBATCH --output=logs/%j.out

# ... pipeline commands ...

# Register the completed run
curl -s -X POST http://127.0.0.1:5000/api/runs \
  -H "X-Api-Key: $NGS_TRACKER_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": 3,
    \"workflow_name\": \"chip-seq-pipeline\",
    \"workflow_tag\": \"v1.3.0\",
    \"workflow_system\": \"snakemake\",
    \"status\": \"completed\",
    \"description\": \"SLURM job $SLURM_JOB_ID\"
  }"
```

### Python helper class

A reusable helper you can drop into any project:

```python
import requests
from datetime import datetime


class NGSTracker:
    def __init__(self, base_url: str, api_key: str):
        self.base = base_url.rstrip("/") + "/api"
        self.headers = {"X-Api-Key": api_key}

    def create_run(self, project_id: int, workflow_name: str, **kwargs) -> dict:
        payload = {
            "project_id": project_id,
            "workflow_name": workflow_name,
            "run_date": datetime.now().isoformat(),
            **kwargs,
        }
        resp = requests.post(f"{self.base}/runs", headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def update_run(self, run_id: int, **kwargs) -> dict:
        resp = requests.patch(
            f"{self.base}/runs/{run_id}", headers=self.headers, json=kwargs
        )
        resp.raise_for_status()
        return resp.json()

    def get_runs(self, **filters) -> list[dict]:
        resp = requests.get(f"{self.base}/runs", headers=self.headers, params=filters)
        resp.raise_for_status()
        return resp.json()


# Usage
tracker = NGSTracker("http://127.0.0.1:5000", "your-api-key")

run = tracker.create_run(
    project_id=3,
    workflow_name="rna-seq-pipeline",
    workflow_tag="v2.1.0",
    status="running",
    tags=["RNA-seq"],
)
run_id = run["id"]

# Later, mark it done
tracker.update_run(run_id, status="completed", notes="All 12 samples passed QC.")
```
