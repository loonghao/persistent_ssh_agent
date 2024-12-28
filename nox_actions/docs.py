"""Nox actions for documentation tasks."""

# Import built-in modules
import locale
import os
import shutil
import stat
from pathlib import Path
from typing import Any, Callable
import errno

# Import third-party modules
import nox
from nox.sessions import Session

languages = ['en_US', 'zh_CN']

# Documentation dependencies
docs_dependencies = [
    "sphinx>=5.0",
    "furo",
    "sphinx-autobuild",
    "sphinx-copybutton",
    "doc8",
    "sphinx-intl",
    "myst_parser"
]


def handle_remove_readonly(func: Callable, path: str, exc: Any) -> None:
    """Handle read-only files when removing directories.
    
    Args:
        func: The function that failed
        path: The path that is being processed
        exc: The exception that was raised
    """
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)  # Try again
    else:
        raise


def install_docs_dependencies(session: Session) -> None:
    """Install all documentation dependencies.
    
    Args:
        session: Nox session object
    """
    # Install the package in editable mode with docs dependencies
    session.install("-e", ".[docs]")
    
    # Install documentation dependencies
    session.install(*docs_dependencies)


def get_docs_dir() -> Path:
    """Get the docs directory path."""
    return Path(__file__).parent.parent / "docs"


def get_system_language() -> str:
    """Get the system language.
    
    Returns:
        str: Language code (e.g., 'en_US' or 'zh_CN')
    """
    try:
        # Get system locale
        system_locale = locale.getdefaultlocale()[0]
        if system_locale:
            # Map locale to our supported languages
            if system_locale.startswith('zh'):
                return 'zh_CN'
            elif system_locale.startswith('en'):
                return 'en_US'
    except Exception:
        pass
    # Default to English if detection fails or unsupported language
    return 'en_US'


def clean_docs(session: Session) -> None:
    """Clean documentation build directory.
    
    Args:
        session: Nox session object
    """
    docs_dir = get_docs_dir()
    build_dir = docs_dir / "build"
    
    if build_dir.exists():
        session.log(f"Cleaning {build_dir}")
        try:
            shutil.rmtree(str(build_dir), onerror=handle_remove_readonly)
            session.log("Documentation build directory cleaned")
        except Exception as e:
            session.warn(f"Failed to clean {build_dir}: {e}")
            # Try to continue even if cleaning fails
            pass


@nox.session(name="docs-clean")
def docs_clean(session: Session) -> None:
    """Clean documentation build directory.
    
    Args:
        session: Nox session object
    """
    clean_docs(session)


@nox.session(name="docs")
def docs(session: Session, builder: str = "html", language: str = None) -> None:
    """Build documentation with sphinx.
    
    Args:
        session: Nox session object
        builder: Sphinx builder to use
        language: Target language to build (default: all languages)
    """
    # Install dependencies
    install_docs_dependencies(session)

    # Clean build directory first
    clean_docs(session)
    
    # Get docs directory
    docs_dir = get_docs_dir()
    
    # Build for specified language or all languages
    build_languages = [language] if language else languages
    
    with session.chdir(str(docs_dir)):
        for lang in build_languages:
            session.log(f"Building documentation for {lang}")
            env = {"SPHINX_LANGUAGE": lang}
            output_dir = f"build/html/{lang}"
            
            session.run(
                "sphinx-build",
                "-b", builder,
                "-D", f"language={lang}",
                "source",
                output_dir,
                env=env
            )
    
    session.log("Documentation built successfully")


@nox.session(name="docs-live")
def docs_live(session: Session, language: str = None) -> None:
    """Build documentation with live reload using sphinx-autobuild.
    
    Args:
        session: Nox session object
        language: Target language for live preview (default: system language)
    """
    # Install dependencies
    install_docs_dependencies(session)

    # Determine language
    if language is None:
        language = get_system_language()
    
    # Validate language
    if language not in languages:
        session.error(f"Unsupported language: {language}")
    
    # Set up environment
    env = os.environ.copy()
    env["SPHINX_LANGUAGE"] = language
    
    # Clean build directory first
    clean_docs(session)
    
    # Get docs directory
    docs_dir = get_docs_dir()
    
    # First build all languages
    for lang in languages:
        session.log(f"Building documentation for {lang}")
        with session.chdir(str(docs_dir)):
            session.run(
                "sphinx-build",
                "-b", "html",
                "-D", f"language={lang}",
                "source",
                f"build/html/{lang}",
                env={"SPHINX_LANGUAGE": lang}
            )
    
    # Then start autobuild for the selected language
    with session.chdir(str(docs_dir)):
        output_dir = f"build/html/{language}"
        session.log(f"Starting live preview for language: {language}")
        session.run(
            "sphinx-autobuild",
            "-b", "html",
            "-D", f"language={language}",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--watch", "source",
            "--ignore", "*.swp",
            "--ignore", "*.pdf",
            "--ignore", "*.log",
            "--ignore", "*.out",
            "--ignore", "_build",
            "--ignore", "build",
            "--re-ignore", r".*\/__pycache__\/.*",
            "--re-ignore", r"\.pytest_cache\/.*",
            "--re-ignore", r"\.git\/.*",
            "--re-ignore", r"\.tox\/.*",
            "--re-ignore", r"\.nox\/.*",
            "--re-ignore", r"\.idea\/.*",
            "--re-ignore", r"\.vscode\/.*",
            "source",
            output_dir,
            env=env
        )


@nox.session(name="docs-lint")
def docs_lint(session: Session) -> None:
    """Run documentation linting.
    
    Args:
        session: Nox session object
    """
    # Install dependencies
    install_docs_dependencies(session)
    
    docs_dir = get_docs_dir()
    source_dir = docs_dir / "source"
    
    # First run sphinx-build in dummy mode to generate necessary files
    with session.chdir(str(docs_dir)):
        session.run(
            "sphinx-build",
            "-b", "dummy",
            "-D", "language=en_US",
            "source",
            "build/dummy",
            silent=True
        )
    
    # Then run doc8
    session.run(
        "doc8",
        "--ignore", "D001",  # Ignore line length
        str(source_dir)
    )


@nox.session(name="docs-i18n")
def docs_i18n(session: Session) -> None:
    """Generate and update translation files.
    
    This function will:
    1. Extract messages from source files to .pot files
    2. Update or create .po files for each language
    3. Compile .po files to .mo files
    
    The translation files will be organized as:
    docs/source/locale/
    ├── en_US/
    │   └── LC_MESSAGES/
    │       ├── *.pot  # Translation templates
    │       ├── *.po   # Translation files
    │       └── *.mo   # Compiled translation files
    └── zh_CN/
        └── LC_MESSAGES/
            ├── *.pot  # Translation templates
            ├── *.po   # Translation files
            └── *.mo   # Compiled translation files
    
    Args:
        session: Nox session object
    """
    # Install dependencies
    install_docs_dependencies(session)
    
    docs_dir = get_docs_dir()
    source_dir = docs_dir / "source"
    locale_dir = source_dir / "locale"
    
    with session.chdir(str(docs_dir)):
        # Extract messages to .pot files
        session.run(
            "sphinx-build",
            "-b", "gettext",
            "source",
            "build/gettext"
        )
        
        # Update .po files for all supported languages
        for lang in languages:
            # Create language directories if they don't exist
            lang_dir = locale_dir / lang / "LC_MESSAGES"
            lang_dir.mkdir(parents=True, exist_ok=True)
            
            # Update .po files
            session.run(
                "sphinx-intl",
                "update",
                "-p", "build/gettext",
                "-d", str(locale_dir),
                "-l", lang
            )
            
            # Compile .po files to .mo files
            session.run(
                "sphinx-intl",
                "build",
                "-d", str(locale_dir)
            )
    
    # Clean up temporary gettext files
    gettext_dir = docs_dir / "build" / "gettext"
    if gettext_dir.exists():
        shutil.rmtree(str(gettext_dir))
    
    session.log("Translation files updated successfully")


@nox.session(name="docs-build")
def docs_build(session: Session) -> None:
    """Build documentation for all languages.
    
    Args:
        session: Nox session object
    """
    # Install dependencies
    install_docs_dependencies(session)
    
    # Clean build directory first
    clean_docs(session)
    
    # Build for each language
    for lang in languages:
        session.log(f"Building documentation for {lang}")
        env = {"SPHINX_LANGUAGE": lang}
        output_dir = f"build/html/{lang}"
        with session.chdir(str(get_docs_dir())):
            session.run(
                "sphinx-build",
                "-b", "html",
                "-D", f"language={lang}",
                "source",
                output_dir,
                env=env
            )
    
    session.log("Documentation built successfully for all languages")
