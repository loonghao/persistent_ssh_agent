"""Configuration file for the Sphinx documentation builder."""

# Import built-in modules
import os
import sys


# Add project root to sys.path
sys.path.insert(0, os.path.abspath("../.."))

# -- Project information -----------------------------------------------------
project = "persistent_ssh_agent"
copyright = "2024, persistent_ssh_agent"
author = "persistent_ssh_agent"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
]

# Myst Parser settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

# Source parsers
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Prioritize .md over .rst for readme
source_parsers = {
    ".md": "markdown",
}

# Suppress all warnings
suppress_warnings = [
    "ref.class",  # Suppress class reference warnings
    "ref.ref",    # Suppress undefined label warnings
]

# Don't treat warnings as errors
nitpicky = False
warning_is_error = False

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# -- Language configuration -------------------------------------------------
language = os.getenv("SPHINX_LANGUAGE", "en_US")

# Mapping of supported languages and their display names
supported_languages = {
    "en_US": {
        "name": "English",
        "url_prefix": "en_US",
        "sphinx_lang": "en",
        "locale": "en_US",
        "icon": ""
    },
    "zh_CN": {
        "name": "中文",
        "url_prefix": "zh_CN",
        "sphinx_lang": "zh_CN",
        "locale": "zh_CN",
        "icon": ""
    }
}

def get_alternate_languages():
    """Get list of alternate languages for the current page.

    Returns:
        list: List of dictionaries containing language metadata
              for languages other than the current one.
    """
    alternates = []
    current_lang = language
    for lang_code, lang_data in supported_languages.items():
        if lang_code != current_lang:
            alternates.append({
                "code": lang_code,
                "name": lang_data["name"],
                "url_prefix": lang_data["url_prefix"],
                "icon": lang_data["icon"]
            })
    return alternates

# Locale directories for translations
locale_dirs = ["locale/"]
gettext_compact = False
gettext_uuid = True
gettext_location = True

# Language to use for generating the HTML full-text search index.
html_search_language = supported_languages[language]["sphinx_lang"]

# Context for templates
html_context = {
    "current_language": language,
    "current_language_name": supported_languages[language]["name"],
    "alternate_languages": get_alternate_languages(),
    "supported_languages": supported_languages
}

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
}

# Configure templates
templates_path = ["_templates"]

# Configure master document
master_doc = "index"

# Configure sidebars
html_sidebars = {
    "**": [
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
        "sidebar/variant-selector.html",
    ]
}

# -- Custom configuration --------------------------------------------------
def setup(app):
    """Setup Sphinx application."""
    app.add_css_file("custom.css")

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
