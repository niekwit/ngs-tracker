project = "NGS Tracker"
author = "Niek Wit"
copyright = "2025, Niek Wit"
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

myst_enable_extensions = ["colon_fence", "deflist"]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Logo — add the repo-level logo/ dir so furo can find the images
html_static_path = ["_static", "../logo"]

html_theme = "furo"

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
        "color-announcement-background": "#0d6efd",
        "color-announcement-text": "#ffffff",
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
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/niekwit/ngs-tracker",
            "html": (
                '<svg stroke="currentColor" fill="currentColor" stroke-width="0" '
                'viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8'
                "c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49"
                "-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01"
                "-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07"
                "-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12"
                " 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 "
                '2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87'
                " 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46"
                '.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path></svg>'
            ),
            "class": "",
        },
    ],
}

html_css_files = ["custom.css"]

html_title = "NGS Tracker"
html_short_title = "NGS Tracker"
