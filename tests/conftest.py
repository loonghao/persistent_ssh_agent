"""Test configuration and fixtures."""

# Import built-in modules
from pathlib import Path
import shutil
import tempfile

# Import third-party modules
import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_ssh_config(temp_dir):
    """Create a mock SSH config file."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    config_path = ssh_dir / "config"

    config_path.write_text("""
Host github.com
    IdentityFile ~/.ssh/id_ed25519
    User git

Host *.gitlab.com
    IdentityFile ~/.ssh/gitlab_key
    User git
""")

    # Create mock key files
    (ssh_dir / "id_ed25519").touch()
    (ssh_dir / "gitlab_key").touch()

    return ssh_dir
