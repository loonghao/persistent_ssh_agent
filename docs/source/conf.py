"""Configuration file for the Sphinx documentation builder."""

# Import built-in modules
import os
import sys


# Add project root to sys.path
sys.path.insert(0, os.path.abspath("../.."))

# Get version directly from version file to avoid import issues
with open(os.path.join(os.path.abspath("../.."), "persistent_ssh_agent", "__version__.py"), encoding="utf-8") as f:
    version_line = f.read().strip()
    __version__ = version_line.split("=")[1].strip().strip('"').strip("'")

# -- Project information -----------------------------------------------------
project = "persistent_ssh_agent"
copyright_str = "2024, persistent_ssh_agent"
author = "persistent_ssh_agent"
release = __version__

# The short X.Y version.
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "myst_parser",
]

# Source parsers
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Suppress all warnings
suppress_warnings = [
    "ref.class",  # Suppress class reference warnings
    "ref.ref",  # Suppress undefined label warnings
]

# Don't treat warnings as errors
nitpicky = False
warning_is_error = False

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# Theme options
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#2980b9",
        "color-brand-content": "#2980b9",
    },
    "dark_css_variables": {
        "color-brand-primary": "#3498db",
        "color-brand-content": "#3498db",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/loonghao/persistent_ssh_agent",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
    "source_repository": "https://github.com/loonghao/persistent_ssh_agent",
    "source_branch": "main",
    "source_directory": "docs/",
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "show_toc_level": 2,
}

# Sidebar configuration
html_sidebars = {
    "**": [
        "sidebar/brand.html",
        "language-switcher.html",
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
    ]
}

# Configure templates
templates_path = ["_templates"]

# -- Language configuration -------------------------------------------------
language = os.getenv("SPHINX_LANGUAGE", "en")

# Mapping of supported languages
supported_languages = {
    "en": "English",
    "zh_CN": "简体中文"
}

# Locale directories for translations
locale_dirs = ["locale/"]
gettext_compact = False
gettext_uuid = True
gettext_location = True

# Language to use for generating the HTML full-text search index.
html_search_language = {
    "en": "en",
    "zh_CN": "zh"
}.get(language, "en")

# Language links configuration
language_links = {
    "en": {
        "zh_CN": "../zh_CN/",
    },
    "zh_CN": {
        "en": "../en/",
    }
}

# HTML context for templates
html_context = {
    "current_language": language,
    "current_language_name": supported_languages.get(language, "English"),
    "available_languages": supported_languages,
    "languages": supported_languages,  # 为了兼容性保留这个键
    "project_root": "/persistent_ssh_agent",  # 添加项目根路径
}

# Configure master document
master_doc = "index"

# -- Custom configuration --------------------------------------------------
def setup(app):
    """Setup Sphinx application."""
    app.add_css_file("custom.css")
