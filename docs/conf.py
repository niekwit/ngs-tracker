import subprocess
from pathlib import Path


def _git_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--abbrev=7"],
            cwd=Path(__file__).parent.parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "dev"


project = "NGS Tracker"
author = "Niek Wit"
copyright = "2025, Niek Wit"
release = _git_version()
version = release

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

myst_enable_extensions = ["colon_fence", "deflist"]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Add the repo-level logo/ dir so furo can find the light/dark logo images
html_static_path = ["_static", "../logo"]

html_theme = "furo"

html_sidebars = {
    "**": [
        "sidebar/brand.html",       # overridden in _templates — adds GitHub+version
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
        "sidebar/variant-selector.html",
    ]
}

html_theme_options = {
    "light_logo": "ngs-tracker_v3_text.png",
    "dark_logo": "ngs-tracker_v3_text_dark.png",
    "light_css_variables": {
        "color-brand-primary": "#0d6efd",
        "color-brand-content": "#0a58ca",
        "color-sidebar-background": "#f8f9fa",
        "color-sidebar-brand-text": "#212529",
        "color-sidebar-caption-text": "#6c757d",
        "color-sidebar-link-text": "#212529",
        "color-sidebar-item-background--hover": "rgba(13, 110, 253, 0.08)",
        "color-sidebar-item-expander-background--hover": "rgba(13, 110, 253, 0.08)",
        "color-highlight-on-target": "rgba(13, 110, 253, 0.06)",
        "color-foreground-primary": "#212529",
        "color-foreground-secondary": "#6c757d",
        "color-background-primary": "#ffffff",
        "color-background-secondary": "#f8f9fa",
        "font-stack": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        "font-stack--monospace": "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
    },
    "dark_css_variables": {
        "color-brand-primary": "#6ea8fe",
        "color-brand-content": "#6ea8fe",
        "color-sidebar-background": "#1a1d20",
        "color-sidebar-link-text": "#dee2e6",
        "color-sidebar-item-background--hover": "rgba(110, 168, 254, 0.08)",
        "color-background-primary": "#212529",
        "color-background-secondary": "#2b3035",
        "color-foreground-primary": "#f8f9fa",
        "color-foreground-secondary": "#adb5bd",
    },
    "navigation_with_keys": True,
    "source_repository": "https://github.com/niekwit/ngs-tracker",
    "source_branch": "main",
    "source_directory": "docs/",
}

html_css_files = ["custom.css"]

html_title = "NGS Tracker"
html_short_title = "NGS Tracker"
