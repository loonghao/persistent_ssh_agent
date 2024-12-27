"""Test SSH configuration functionality."""
# Import built-in modules
import os
import shutil
import subprocess
import tempfile
from unittest.mock import Mock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.config import SSHConfig
from persistent_ssh_agent.core import PersistentSSHAgent
import pytest


@pytest.fixture
def protected_ssh_key_pair():
    """Generate a temporary password-protected SSH key pair for testing."""
    # Create a temporary directory for the key pair
    temp_dir = tempfile.mkdtemp()
    key_path = os.path.join(temp_dir, "test_key")

    try:
        # Generate the key pair with password protection
        subprocess.run([
            "ssh-keygen",
            "-t", "rsa",
            "-m", "PEM",
            "-f", key_path,
            "-N", "testpass"
        ], check=True, capture_output=True)

        # Read the key files
        with open(key_path, "r") as f:
            private_key = f.read()
        with open(key_path + ".pub", "r") as f:
            public_key = f.read()

        yield private_key, public_key, "test_key"

    finally:
        # Clean up the temporary files
        try:
            os.unlink(key_path)
            os.unlink(key_path + ".pub")
            os.rmdir(temp_dir)
        except (OSError, IOError) as e:
            print(f"Warning: Failed to cleanup test keys: {e}")


@pytest.mark.timeout(30)
def test_config_with_passphrase(protected_ssh_key_pair):
    """Test loading identity with passphrase from config."""
    private_key, public_key, key_path = protected_ssh_key_pair
    temp_dir = tempfile.mkdtemp()
    try:
        # Create config with the real protected key
        config = SSHConfig(
            identity_content=private_key,
            identity_passphrase="testpass"
        )
        agent = PersistentSSHAgent(config=config)

        # Get and verify identity file
        identity_file = agent._get_identity_file("github.com")
        assert identity_file is not None
        assert os.path.exists(identity_file)

        # Verify the key content was written correctly
        with open(identity_file, "r") as f:
            written_key = f.read().strip()
        assert written_key == private_key.strip()

        # Start SSH agent and add the key
        result = agent._start_ssh_agent(identity_file)
        assert result is True, "Failed to start SSH agent with passphrase"

        # Verify the key was added correctly
        list_result = agent._run_command(["ssh-add", "-l"], check_output=False)
        assert list_result is not None and list_result.returncode == 0, \
            f"Failed to list keys: {list_result.stderr if list_result else 'Command failed'}"

        # Get public key from private key
        key_pub = agent._run_command(
            ["ssh-keygen", "-y", "-f", identity_file, "-P", "testpass"],
            check_output=False
        )
        assert key_pub is not None and key_pub.returncode == 0, \
            f"Failed to get public key: {key_pub.stderr if key_pub else 'Command failed'}"

        # Verify public key content
        assert "ssh-rsa" in key_pub.stdout, "Invalid public key format"

        # Write public key to file
        pub_key_file = identity_file + ".pub"
        with open(pub_key_file, "w") as f:
            f.write(key_pub.stdout)

        # Get key fingerprint from public key
        key_fingerprint = agent._run_command(
            ["ssh-keygen", "-lf", pub_key_file],
            check_output=False
        )

        # Debug: Print file contents
        with open(identity_file, "r") as f:
            print(f"Identity file contents:\n{f.read()}")

        assert key_fingerprint is not None and key_fingerprint.returncode == 0, \
            f"Failed to get key fingerprint: {key_fingerprint.stderr if key_fingerprint else 'Command failed'}"

        # Verify fingerprint is in the agent's list
        assert key_fingerprint.stdout.split()[1] in list_result.stdout, \
            "Added key fingerprint not found in agent"

    finally:
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except (OSError, IOError) as e:
            print(f"Failed to cleanup: {e}")


@pytest.mark.timeout(30)
@patch("subprocess.run")
def test_start_ssh_agent_unit(mock_run, protected_ssh_key_pair):
    """Unit test for SSH agent startup with mocked commands."""
    private_key, _, _ = protected_ssh_key_pair

    # Mock ssh-agent startup
    mock_run.side_effect = [
        # ssh-agent -s
        Mock(
            returncode=0,
            stdout="SSH_AUTH_SOCK=/tmp/ssh-XXX/agent.123; export SSH_AUTH_SOCK;\n"
                  "SSH_AGENT_PID=123; export SSH_AGENT_PID;\n",
            stderr=""
        ),
        # ssh-add identity_file
        Mock(
            returncode=0,
            stdout="Identity added: test_key_pem",
            stderr=""
        ),
        # ssh-keygen -lf identity_file (for fingerprint)
        Mock(
            returncode=0,
            stdout="2048 SHA256:... test_key_pem",
            stderr=""
        ),
        # ssh-add -l (verification)
        Mock(
            returncode=0,
            stdout="2048 SHA256:... test_key_pem",
            stderr=""
        )
    ]

    config = SSHConfig(
        identity_content=private_key,
        identity_passphrase="testpass"
    )
    agent = PersistentSSHAgent(config=config)

    # Get identity file
    identity_file = agent._get_identity_file("github.com")
    assert identity_file is not None

    # Test starting agent
    result = agent._start_ssh_agent(identity_file)
    assert result is True, "Failed to start SSH agent"


@pytest.mark.timeout(30)
def test_env_with_passphrase(protected_ssh_key_pair, monkeypatch):
    """Test loading identity with passphrase from environment."""
    private_key, _, key_path = protected_ssh_key_pair

    # Set environment variable for passphrase
    monkeypatch.setenv("SSH_KEY_PASSPHRASE", "testpass")

    # Create config without passphrase (should use env var)
    config = SSHConfig(identity_content=private_key)
    agent = PersistentSSHAgent(config=config)

    # Get identity file
    identity_file = agent._get_identity_file("github.com")
    assert identity_file is not None

    # Verify key content
    with open(identity_file, "r") as f:
        written_key = f.read().strip()
    assert written_key == private_key.strip(), \
        "Key content mismatch"

    # Start agent and add key
    result = agent._start_ssh_agent(identity_file)
    assert result is True, "Failed to start SSH agent with passphrase from environment"
