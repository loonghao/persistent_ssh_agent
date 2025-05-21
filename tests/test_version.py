"""Tests for version module."""

# Import built-in modules
import re

# Import local modules
from persistent_ssh_agent.__version__ import __version__


def test_version_format():
    """Test that the version string follows semantic versioning."""
    # Check that version follows semantic versioning (X.Y.Z)
    assert re.match(r"^\d+\.\d+\.\d+$", __version__) is not None
