# Building the docs

The documentation is written in Markdown (MyST flavour) and built with [Sphinx](https://www.sphinx-doc.org/). It is published automatically on [ReadTheDocs](https://ngs-tracker.readthedocs.io/) whenever a commit is pushed to `main`.

## Install dependencies

The doc build dependencies are separate from the app. Install them into the existing `ngs-tracker` conda environment:

```bash
conda activate ngs-tracker
pip install -r docs/requirements.txt
```

## Build HTML locally

Run from the **repository root**:

```bash
conda activate ngs-tracker
sphinx-build -b html docs docs/_build/html
```

Then open the result in a browser:

```bash
xdg-open docs/_build/html/index.html   # Linux
open docs/_build/html/index.html       # macOS
```

To do a clean rebuild (removes cached output first):

```bash
rm -rf docs/_build
sphinx-build -b html docs docs/_build/html
```

## Adding screenshots

Store screenshots under `docs/_static/screenshots/` and reference them in any `.md` file with a relative path:

```markdown
![Alt text](_static/screenshots/filename.png)
```

## Structure

| Path | Purpose |
|---|---|
| `docs/*.md` | One page per topic |
| `docs/index.md` | Table of contents / landing page |
| `docs/conf.py` | Sphinx configuration |
| `docs/requirements.txt` | Build dependencies |
| `docs/_static/` | CSS, images, and other static assets |
| `docs/_build/` | Generated output — not committed (gitignored) |
