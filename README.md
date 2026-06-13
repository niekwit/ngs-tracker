<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="logo/ngs-tracker_v3_text_dark.png">
    <img alt="NGS Tracker" src="logo/ngs-tracker_v3_text.png" height="240">
  </picture>
</p>

[![DOI](https://zenodo.org/badge/1266199288.svg)](https://doi.org/10.5281/zenodo.20677413)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A self-hosted, browser-based web app for tracking bioinformatics projects and pipeline executions.
Data is organised as **Research Group → Researcher → Project → Workflow Run**, where each run records the workflow system (Snakemake, Nextflow, CWL, or other), release tag, config files, sample sheets, file attachments, backup status across multiple locations, and free-text notes with Markdown rendering.

Full documentation: https://ngs-tracker.readthedocs.io/en/latest/

## Quick start (Linux)

**Requirements:** [Conda](https://docs.conda.io/) (Miniconda or Miniforge) and Python 3.11.

```bash
git clone https://github.com/niekwit/ngs-tracker.git
cd ngs-tracker

conda create -n ngs-tracker python=3.11 -y
conda activate ngs-tracker
pip install -r requirements.txt

./run.sh
```

Open **http://127.0.0.1:5000** in your browser. On first launch you will be asked to set a database path and a file storage path — both are saved to `~/.ngs-tracker/settings.json` and survive updates.

To run NGS Tracker automatically at login, see the [startup instructions](https://ngs-tracker.readthedocs.io/en/latest/startup.html) for Linux (systemd), macOS (launchd), and Windows (Task Scheduler).

