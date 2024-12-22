"""Test configuration and fixtures."""

# Import built-in modules
import os
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
    ssh_dir = os.path.join(temp_dir, ".ssh")
    os.makedirs(ssh_dir)
    config_path = os.path.join(ssh_dir, "config")

    with open(config_path, "w") as f:
        f.write("""
Host github.com
    IdentityFile ~/.ssh/id_ed25519
    User git

Host *.gitlab.com
    IdentityFile ~/.ssh/gitlab_key
    User git
""")

    # Create mock key files
    open(os.path.join(ssh_dir, "id_ed25519"), "w").close()
    open(os.path.join(ssh_dir, "gitlab_key"), "w").close()

    return ssh_dir
