<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logo/ngs-tracker_v3_text_dark.png">
  <img alt="NGS Tracker" src="logo/ngs-tracker_v3_text.png" height="240">
</picture>

A browser-based web app for tracking bioinformatics projects and analyses.
Data is organised as **Research Group → Researcher → Project → Workflow Run**,
with support for custom analysis scripts, file attachments, backup status,
and publication tracking.

---

## Features

- Hierarchical records: Research Groups → Researchers → Projects → Workflow Runs
- Attach Snakemake config files (YAML) — settings are parsed and displayed inline
- Select workflow and release tag directly from GitHub (tags fetched live)
- Track backup status per run (Local / RCS / RFS) with storage paths
- Attach processed data files to workflow runs (peak calls, data, etc.)
- Upload custom analysis scripts per project with output file attachments
- Mark projects as published with an optional publication URL
- Soft-delete trash bin — deleted records can be restored or permanently removed
- Dashboard with live stats (record counts and total file size)
- Sortable tables on the Projects and Runs list pages
- Settings (database path, file storage path) persisted to `~/.ngs-tracker/`

---

## Requirements

- [Conda](https://docs.conda.io/) (Miniconda or Anaconda)
- Python 3.11

---

## Installation

```bash
git clone https://github.com/niekwit/ngs-tracker.git
cd ngs-tracker

# Create the conda environment
conda create -n ngs-tracker python=3.11 -y
conda activate ngs-tracker
pip install -r requirements.txt
```

---

## Running

```bash
./run.sh
```

Then open **http://127.0.0.1:5000** in your browser.

On first launch you will be taken to the **Settings** page to configure:

| Setting | Description |
|---|---|
| **File storage path** | Directory where uploaded files are saved |
| **Database path** | Full path to the SQLite database file (e.g. `/data/ngs.db`) |

Both settings are saved to `~/.ngs-tracker/settings.json` and survive re-clones or moves of the repo directory.

### Optional environment variables

| Variable | Default | Description |
|---|---|---|
| `NGS_PORT` | `5000` | Port to listen on |
| `NGS_HOST` | `127.0.0.1` | Host to bind to — set to `0.0.0.0` to expose on the local network |

```bash
NGS_PORT=8080 ./run.sh
```

---

## Data model

```
Research Group
└── Researcher
    └── Project
        ├── Workflow Run
        │   └── Attached Files  (config, peak calls, processed data, other)
        └── Custom Analysis Script
            └── Script Output Files
```

### Workflow Runs

- Select from 15 built-in Snakemake workflows; release tags are fetched live from GitHub
- Upload a Snakemake YAML config — all settings (excluding `resources`) are displayed in the run view
- Record backup locations (Local, RCS, RFS) with storage paths

### Custom Analysis Scripts

Supported languages (auto-detected from extension): Python, R, Shell, Bash, Perl, MATLAB, Julia, Jupyter

---

## Trash / recycle bin

Clicking **Delete** on any record moves it to the trash rather than permanently removing it.

- **Restore** — returns the record to its normal location
- **Delete** — permanently removes the record and all its associated files
- **Empty Trash** — permanently removes everything in the trash at once

Access the trash via the **Trash** link in the sidebar.

---

## Updating

```bash
git pull
# Dependencies rarely change, but re-run if requirements.txt was updated:
pip install -r requirements.txt
```

Database schema migrations are applied automatically on startup — no manual steps needed.
