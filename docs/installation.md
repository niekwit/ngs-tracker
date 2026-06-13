# Installation

## Requirements

- [Conda](https://docs.conda.io/) (Miniconda or Miniforge recommended)
- Python 3.11

## Install

```bash
git clone https://github.com/niekwit/ngs-tracker.git
cd ngs-tracker

conda create -n ngs-tracker python=3.11 -y
conda activate ngs-tracker
pip install -r requirements.txt
```

## Run

```bash
./run.sh
```

Then open **http://127.0.0.1:5000** in your browser.

## First launch

On first launch you are redirected to the **Settings** page to configure two paths:

| Setting | Description |
|---|---|
| **Database path** | Full path to the SQLite database file (e.g. `/data/ngs.db`) |
| **File storage path** | Directory where uploaded files are saved |

Both values are written to `~/.ngs-tracker/settings.json` and survive re-clones or moves of the repository directory. Database migrations are applied automatically on every startup — no manual steps are ever needed.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NGS_PORT` | `5000` | Port to listen on |
| `NGS_HOST` | `127.0.0.1` | Bind address — use `0.0.0.0` to expose on the local network |

```bash
NGS_PORT=8080 ./run.sh
```
