"""Additional tests to improve coverage for core module (part 2)."""

# Import built-in modules
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent
from persistent_ssh_agent.utils import run_command


def test_verify_loaded_key_success():
    """Test verifying loaded key with success."""
    agent = PersistentSSHAgent()

    # Mock subprocess.run to return success
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "The agent has 1 key ~/.ssh/id_rsa"
    with patch("subprocess.run", return_value=mock_result):
        # Call _verify_loaded_key
        result = agent._verify_loaded_key("~/.ssh/id_rsa")

        # Verify the result
        assert result is True


def test_verify_loaded_key_failure():
    """Test verifying loaded key with failure."""
    agent = PersistentSSHAgent()

    # Mock run_command to return failure
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "The agent has no identities."
    with patch("persistent_ssh_agent.utils.run_command", return_value=mock_result):
        # Call _verify_loaded_key
        result = agent._verify_loaded_key("~/.ssh/id_rsa")

        # Verify the result
        assert result is False


def test_verify_loaded_key_command_failure():
    """Test verifying loaded key with command failure."""
    agent = PersistentSSHAgent()

    # Mock run_command to return None (command failure)
    with patch("persistent_ssh_agent.utils.run_command", return_value=None):
        # Call _verify_loaded_key
        result = agent._verify_loaded_key("~/.ssh/id_rsa")

        # Verify the result
        assert result is False


def test_add_ssh_key_no_passphrase_success():
    """Test adding SSH key without passphrase successfully."""
    agent = PersistentSSHAgent()

    # Mock os.path.exists and os.path.expanduser
    with patch("os.path.exists", return_value=True):
        with patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa"):
            # Mock subprocess.Popen to avoid SSH command execution
            with patch("subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = ("", "")
                mock_popen.return_value = mock_process

                # Call _add_ssh_key
                result = agent._add_ssh_key("~/.ssh/id_rsa")

                # Verify the result
                assert result is True


def test_add_ssh_key_with_passphrase_success():
    """Test adding SSH key with passphrase successfully."""
    agent = PersistentSSHAgent()

    # Mock os.path.exists and os.path.expanduser
    with patch("os.path.exists", return_value=True):
        with patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa"):
            # Mock the SSH key manager methods directly
            with patch.object(agent.ssh_key_manager, "try_add_key_without_passphrase", return_value=(False, True)):
                with patch.object(agent.ssh_key_manager, "add_key_with_passphrase", return_value=True):
                    # Set up a mock config with identity_passphrase
                    agent._config = MagicMock()
                    agent._config.identity_passphrase = "passphrase"

                    # Call _add_ssh_key (which delegates to ssh_key_manager.add_ssh_key)
                    result = agent.ssh_key_manager.add_ssh_key("~/.ssh/id_rsa", agent._config)

                    # Verify the result
                    assert result is True


def test_add_ssh_key_with_passphrase_failure():
    """Test adding SSH key with passphrase with failure."""
    agent = PersistentSSHAgent()

    # Mock os.path.exists and os.path.expanduser
    with patch("os.path.exists", return_value=True):
        with patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa"):
            # Mock _try_add_key_without_passphrase to return needs_passphrase
            with patch.object(agent, "_try_add_key_without_passphrase", return_value=(False, True)):
                # Mock _has_cli to be True
                with patch("persistent_ssh_agent.core._has_cli", True):
                    # Mock getpass.getpass to return a passphrase
                    with patch("getpass.getpass", return_value="passphrase"):
                        # Mock _add_key_with_passphrase to return failure
                        with patch.object(agent, "_add_key_with_passphrase", return_value=False):
                            # Call _add_ssh_key
                            result = agent._add_ssh_key("~/.ssh/id_rsa")

                            # Verify the result
                            assert result is False


def test_add_ssh_key_failure():
    """Test adding SSH key with failure."""
    agent = PersistentSSHAgent()

    # Mock os.path.exists and os.path.expanduser
    with patch("os.path.exists", return_value=True):
        with patch("os.path.expanduser", return_value="/home/user/.ssh/id_rsa"):
            # Mock _try_add_key_without_passphrase to return failure
            with patch.object(agent, "_try_add_key_without_passphrase", return_value=(False, False)):
                # Call _add_ssh_key
                result = agent._add_ssh_key("~/.ssh/id_rsa")

                # Verify the result
                assert result is False


def test_setup_ssh_with_identity_file_success():
    """Test setting up SSH with identity file successfully."""
    agent = PersistentSSHAgent()

    # Mock is_valid_hostname to return True
    with patch("persistent_ssh_agent.utils.is_valid_hostname", return_value=True):
        # Mock _get_identity_file to return a path
        with patch.object(agent, "_get_identity_file", return_value="/home/user/.ssh/id_rsa"):
            # Mock os.path.exists to return True
            with patch("os.path.exists", return_value=True):
                # Mock _start_ssh_agent to return success
                with patch.object(agent, "_start_ssh_agent", return_value=True):
                    # Mock _test_ssh_connection to return success
                    with patch.object(agent, "_test_ssh_connection", return_value=True):
                        # Call setup_ssh
                        result = agent.setup_ssh("github.com")

                        # Verify the result
                        assert result is True


def test_setup_ssh_with_identity_file_not_exists():
    """Test setting up SSH with non-existent identity file."""
    agent = PersistentSSHAgent()

    # Mock is_valid_hostname to return True
    with patch("persistent_ssh_agent.utils.is_valid_hostname", return_value=True):
        # Mock _get_identity_file to return a path
        with patch.object(agent, "_get_identity_file", return_value="/home/user/.ssh/id_rsa"):
            # Mock os.path.exists to return False
            with patch("os.path.exists", return_value=False):
                # Call setup_ssh
                result = agent.setup_ssh("github.com")

                # Verify the result
                assert result is False


def test_setup_ssh_with_identity_file_agent_failure():
    """Test setting up SSH with identity file but agent failure."""
    agent = PersistentSSHAgent()

    # Mock is_valid_hostname to return True
    with patch("persistent_ssh_agent.utils.is_valid_hostname", return_value=True):
        # Mock _get_identity_file to return a path
        with patch.object(agent, "_get_identity_file", return_value="/home/user/.ssh/id_rsa"):
            # Mock os.path.exists to return True
            with patch("os.path.exists", return_value=True):
                # Mock _start_ssh_agent to return failure
                with patch.object(agent, "_start_ssh_agent", return_value=False):
                    # Call setup_ssh
                    result = agent.setup_ssh("github.com")

                    # Verify the result
                    assert result is False


def test_run_command_success():
    """Test running command successfully."""
    # Mock subprocess.run to return success
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "success"
    with patch("subprocess.run", return_value=mock_result):
        # Call run_command
        result = run_command(["echo", "test"])

        # Verify the result
        assert result is mock_result
        assert result.returncode == 0
        assert result.stdout == "success"


def test_run_command_failure():
    """Test running command with failure."""
    # Mock subprocess.run to raise exception
    with patch("subprocess.run", side_effect=subprocess.SubprocessError("Command failed")):
        # Call run_command
        result = run_command(["invalid", "command"])

        # Verify the result
        assert result is None
