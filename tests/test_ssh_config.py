"""Tests for SSH configuration handling."""

# Import built-in modules
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.config import SSHConfig
from persistent_ssh_agent.core import PersistentSSHAgent
import pytest


@pytest.fixture
def ssh_config():
    """Create an SSHConfig instance."""
    return SSHConfig(identity_passphrase="test_passphrase")


@pytest.fixture
def ssh_manager(ssh_config):
    """Create a PersistentSSHAgent instance with config."""
    return PersistentSSHAgent(config=ssh_config)


def test_config_with_passphrase(ssh_manager, tmp_path):
    """Test SSH agent with passphrase configuration."""
    identity_file = tmp_path / "test_key"
    identity_file.write_text("test key")

    with patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen:

        # Mock SSH agent startup
        def mock_run_side_effect(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return subprocess.CompletedProcess(
                    args=["ssh-agent", "-s"],
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh-XXX; export SSH_AUTH_SOCK;\n"
                          "SSH_AGENT_PID=1234; export SSH_AGENT_PID;\n",
                    stderr=b""
                )
            elif args[0][0] == "ssh-add":
                if len(args[0]) > 1 and args[0][1] == "-l":
                    # First call to ssh-add -l should return 1 (no identities)
                    # Subsequent calls should return 0 (identity added)
                    return subprocess.CompletedProcess(
                        args=["ssh-add", "-l"],
                        returncode=1 if not ssh_manager._ssh_agent_started else 0,
                        stdout=b"",
                        stderr=b""
                    )
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = mock_run_side_effect

        # Mock Popen for ssh-add with passphrase
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"Identity added", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Test agent start with passphrase
        result = ssh_manager._start_ssh_agent(str(identity_file))
        assert result is True

        # Verify Popen was called with correct command
        mock_popen.assert_called_with(
            ["ssh-add", str(identity_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )


def test_start_ssh_agent_unit(ssh_manager, tmp_path):
    """Test SSH agent startup with unit tests."""
    identity_file = tmp_path / "test_key"
    identity_file.write_text("test key")

    with patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen:

        # Mock SSH agent startup
        def mock_run_side_effect(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return subprocess.CompletedProcess(
                    args=["ssh-agent", "-s"],
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh-XXX; export SSH_AUTH_SOCK;\n"
                          "SSH_AGENT_PID=1234; export SSH_AGENT_PID;\n",
                    stderr=""
                )
            elif args[0][0] == "ssh-add":
                if len(args[0]) > 1 and args[0][1] == "-l":
                    # First call should return 1 (no identities)
                    # Subsequent calls should return 0 (identity added)
                    return subprocess.CompletedProcess(
                        args=["ssh-add", "-l"],
                        returncode=1 if not ssh_manager._ssh_agent_started else 0,
                        stdout=b"",
                        stderr=b""
                    )
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = mock_run_side_effect

        # Mock key addition
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"Identity added", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = ssh_manager._start_ssh_agent(str(identity_file))
        assert result is True, "Failed to start SSH agent"


def test_env_with_passphrase(ssh_manager, tmp_path):
    """Test SSH agent with passphrase from environment."""
    identity_file = tmp_path / "test_key"
    identity_file.write_text("test key")

    with patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen:

        # Mock SSH agent startup
        def mock_run_side_effect(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return subprocess.CompletedProcess(
                    args=["ssh-agent", "-s"],
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh-XXX; export SSH_AUTH_SOCK;\n"
                          "SSH_AGENT_PID=1234; export SSH_AGENT_PID;\n",
                    stderr=""
                )
            elif args[0][0] == "ssh-add":
                if len(args[0]) > 1 and args[0][1] == "-l":
                    # First call should return 1 (no identities)
                    # Subsequent calls should return 0 (identity added)
                    return subprocess.CompletedProcess(
                        args=["ssh-add", "-l"],
                        returncode=1 if not ssh_manager._ssh_agent_started else 0,
                        stdout=b"",
                        stderr=b""
                    )
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = mock_run_side_effect

        # Mock key addition with passphrase
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"Identity added", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = ssh_manager._start_ssh_agent(str(identity_file))
        assert result is True, "Failed to start SSH agent with passphrase from environment"
