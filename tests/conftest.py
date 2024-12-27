"""Test configuration and fixtures."""

# Import built-in modules
import os
from pathlib import Path
import shutil
import subprocess
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
    IdentityFile gitlab_key
    User git
""")

    # Create mock key files
    (ssh_dir / "id_ed25519").touch()
    (ssh_dir / "gitlab_key").touch()

    return ssh_dir


@pytest.fixture
def protected_ssh_key_pair():
    """Generate a real password-protected SSH key pair for testing.

    Returns:
        tuple: (private_key_content, public_key_content, key_path)
    """
    key_dir = tempfile.mkdtemp()
    key_path = os.path.join(key_dir, "test_key")
    try:
        # Generate SSH key pair with password protection
        subprocess.run([
            "ssh-keygen",
            "-t", "rsa",
            "-b", "2048",
            "-N", "testpass",
            "-f", key_path,
            "-q"  # Quiet mode
        ], check=True)

        # Read private and public key contents
        with open(key_path, "r") as f:
            private_key = f.read()
        with open(f"{key_path}.pub", "r") as f:
            public_key = f.read()

        yield private_key, public_key, key_path
    finally:
        # Cleanup
        try:
            if os.path.exists(key_path):
                os.unlink(key_path)
            if os.path.exists(f"{key_path}.pub"):
                os.unlink(f"{key_path}.pub")
            if os.path.exists(key_dir):
                os.rmdir(key_dir)
        except (OSError, IOError) as e:
            print(f"Failed to cleanup test keys: {e}")


@pytest.fixture
def mock_ssh_agent(monkeypatch):
    """Mock SSH agent environment for testing."""
    agent_sock = "/tmp/mock-ssh-agent.sock" if os.name != "nt" else r"\\.\pipe\mock-ssh-agent"
    agent_pid = "12345"

    monkeypatch.setenv("SSH_AUTH_SOCK", agent_sock)
    monkeypatch.setenv("SSH_AGENT_PID", agent_pid)

    return {
        "SSH_AUTH_SOCK": agent_sock,
        "SSH_AGENT_PID": agent_pid
    }
