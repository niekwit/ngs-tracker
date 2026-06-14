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

### Snakemake — register a run on success

Add an `onsuccess` block to your `Snakefile` so each completed run is automatically recorded in NGS Tracker.

```python
# Snakefile
NGS_BASE = "http://127.0.0.1:5000/api"
NGS_KEY  = os.environ.get("NGS_TRACKER_KEY", "")
NGS_PROJECT_ID = 3   # set to your project ID

onsuccess:
    import requests, datetime
    requests.post(
        f"{NGS_BASE}/runs",
        headers={"X-Api-Key": NGS_KEY},
        json={
            "project_id": NGS_PROJECT_ID,
            "workflow_name": "rna-seq-pipeline",
            "workflow_tag": config.get("workflow_tag", ""),
            "workflow_system": "snakemake",
            "status": "completed",
            "run_date": datetime.datetime.now().isoformat(),
            "description": config.get("description", ""),
            "tags": config.get("tags", []),
        },
    )

onerror:
    import requests, datetime
    requests.post(
        f"{NGS_BASE}/runs",
        headers={"X-Api-Key": NGS_KEY},
        json={
            "project_id": NGS_PROJECT_ID,
            "workflow_name": "rna-seq-pipeline",
            "status": "failed",
            "run_date": datetime.datetime.now().isoformat(),
        },
    )
```

Store your API key in the environment rather than hard-coding it:

```bash
export NGS_TRACKER_KEY="your-api-key"
snakemake --cores 8
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
