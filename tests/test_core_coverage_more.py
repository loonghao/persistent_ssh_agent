"""Additional tests to improve coverage for core module."""

# Import built-in modules
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent


def test_load_agent_info_expired():
    """Test loading expired agent info."""
    agent = PersistentSSHAgent()

    # Create a mock agent info file
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_file.read.return_value = (
        '{"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock", "SSH_AGENT_PID": "123", '
        '"timestamp": 0, "platform": "posix"}'
    )

    # Mock the agent info file
    with patch.object(agent, "_agent_info_file") as mock_agent_info_file:
        mock_agent_info_file.exists.return_value = True

        # Mock open to return our mock file
        with patch("builtins.open", return_value=mock_file):
            # Mock json.load to return our mock agent info
            with patch("json.load", return_value={
                "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
                "SSH_AGENT_PID": "123",
                "timestamp": 0,  # Very old timestamp
                "platform": "posix"
            }):
                # Call _load_agent_info
                result = agent._load_agent_info()

                # Verify the result
                assert result is False


def test_load_agent_info_platform_mismatch():
    """Test loading agent info with platform mismatch."""
    agent = PersistentSSHAgent()

    # Create a mock agent info file
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_file.read.return_value = (
        '{"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock", "SSH_AGENT_PID": "123", '
        '"timestamp": 9999999999, "platform": "posix"}'
    )

    # Mock the agent info file
    with patch.object(agent, "_agent_info_file") as mock_agent_info_file:
        mock_agent_info_file.exists.return_value = True

        # Mock open to return our mock file
        with patch("builtins.open", return_value=mock_file):
            # Mock json.load to return our mock agent info
            with patch("json.load", return_value={
                "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
                "SSH_AGENT_PID": "123",
                "timestamp": 9999999999,  # Future timestamp
                "platform": "posix"  # Different from os.name in the test
            }):
                # Mock os.name to be "nt" (Windows)
                with patch("os.name", "nt"):
                    # Call _load_agent_info
                    result = agent._load_agent_info()

                    # Verify the result
                    assert result is False


def test_load_agent_info_ssh_add_failure():
    """Test loading agent info with ssh-add failure."""
    agent = PersistentSSHAgent()

    # Create a mock agent info file
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_file.read.return_value = (
        '{"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock", "SSH_AGENT_PID": "123", '
        '"timestamp": 9999999999, "platform": "nt"}'
    )

    # Mock the agent info file
    with patch.object(agent, "_agent_info_file") as mock_agent_info_file:
        mock_agent_info_file.exists.return_value = True

        # Mock open to return our mock file
        with patch("builtins.open", return_value=mock_file):
            # Mock json.load to return our mock agent info
            with patch("json.load", return_value={
                "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
                "SSH_AGENT_PID": "123",
                "timestamp": 9999999999,  # Future timestamp
                "platform": "nt"  # Same as os.name in the test
            }):
                # Mock os.name to be "nt" (Windows)
                with patch("os.name", "nt"):
                    # Mock run_command to return None (failure)
                    with patch("persistent_ssh_agent.utils.run_command", return_value=None):
                        # Call _load_agent_info
                        result = agent._load_agent_info()

                        # Verify the result
                        assert result is False


def test_load_agent_info_ssh_add_not_running():
    """Test loading agent info with ssh-add indicating agent not running."""
    agent = PersistentSSHAgent()

    # Create a mock agent info file
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_file.read.return_value = (
        '{"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock", "SSH_AGENT_PID": "123", '
        '"timestamp": 9999999999, "platform": "nt"}'
    )

    # Mock the agent info file
    with patch.object(agent, "_agent_info_file") as mock_agent_info_file:
        mock_agent_info_file.exists.return_value = True

        # Mock open to return our mock file
        with patch("builtins.open", return_value=mock_file):
            # Mock json.load to return our mock agent info
            with patch("json.load", return_value={
                "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
                "SSH_AGENT_PID": "123",
                "timestamp": 9999999999,  # Future timestamp
                "platform": "nt"  # Same as os.name in the test
            }):
                # Mock os.name to be "nt" (Windows)
                with patch("os.name", "nt"):
                    # Mock run_command to return returncode 2 (agent not running)
                    mock_result = MagicMock()
                    mock_result.returncode = 2
                    with patch("persistent_ssh_agent.utils.run_command", return_value=mock_result):
                        # Call _load_agent_info
                        result = agent._load_agent_info()

                        # Verify the result
                        assert result is False


def test_start_ssh_agent_reuse_with_key():
    """Test starting SSH agent with reuse and key already loaded."""
    agent = PersistentSSHAgent(reuse_agent=True)

    # Mock _load_agent_info to return True
    with patch.object(agent, "_load_agent_info", return_value=True):
        # Mock _verify_loaded_key to return True
        with patch.object(agent, "_verify_loaded_key", return_value=True):
            # Call _start_ssh_agent
            result = agent._start_ssh_agent("~/.ssh/id_rsa")

            # Verify the result
            assert result is True


def test_start_ssh_agent_reuse_without_key():
    """Test starting SSH agent with reuse but key not loaded."""
    agent = PersistentSSHAgent(reuse_agent=True)

    # Mock _load_agent_info to return True
    with patch.object(agent, "_load_agent_info", return_value=True):
        # Mock _verify_loaded_key to return False
        with patch.object(agent, "_verify_loaded_key", return_value=False):
            # Mock subprocess.run for ssh-agent
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = (
                "SSH_AUTH_SOCK=/tmp/ssh-agent.sock; export SSH_AUTH_SOCK;\n"
                "SSH_AGENT_PID=123; export SSH_AGENT_PID;"
            )
            with patch("subprocess.run", return_value=mock_result):
                # Mock _add_ssh_key to return True
                with patch.object(agent, "_add_ssh_key", return_value=True):
                    # Mock SSH key manager to avoid subprocess calls
                    with patch.object(agent.ssh_key_manager, "add_ssh_key", return_value=True):
                        # Call _start_ssh_agent
                        result = agent._start_ssh_agent("~/.ssh/id_rsa")

                        # Verify the result
                        assert result is True


def test_start_ssh_agent_already_started():
    """Test starting SSH agent when it's already started."""
    agent = PersistentSSHAgent(reuse_agent=False)
    agent._ssh_agent_started = True

    # Mock _verify_loaded_key to return True
    with patch.object(agent, "_verify_loaded_key", return_value=True):
        # Call _start_ssh_agent
        result = agent._start_ssh_agent("~/.ssh/id_rsa")

        # Verify the result
        assert result is True


def test_start_ssh_agent_failure():
    """Test starting SSH agent with failure."""
    agent = PersistentSSHAgent(reuse_agent=False)

    # Mock run_command to return None (failure)
    with patch("persistent_ssh_agent.utils.run_command", return_value=None):
        # Call _start_ssh_agent
        result = agent._start_ssh_agent("~/.ssh/id_rsa")

        # Verify the result
        assert result is False


def test_start_ssh_agent_no_env_vars():
    """Test starting SSH agent with no environment variables in output."""
    agent = PersistentSSHAgent(reuse_agent=False)

    # Mock run_command to return success but no environment variables
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Some output without environment variables"
    with patch("persistent_ssh_agent.utils.run_command", return_value=mock_result):
        # Call _start_ssh_agent
        result = agent._start_ssh_agent("~/.ssh/id_rsa")

        # Verify the result
        assert result is False


def test_try_add_key_without_passphrase_success():
    """Test adding key without passphrase successfully."""
    agent = PersistentSSHAgent()

    # Mock subprocess.Popen directly
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = ("stdout", "stderr")

    with patch("subprocess.Popen", return_value=mock_process):
        # Call _try_add_key_without_passphrase
        success, needs_passphrase = agent._try_add_key_without_passphrase("~/.ssh/id_rsa")

        # Verify the result
        assert success is True
        assert needs_passphrase is False


def test_try_add_key_without_passphrase_needs_passphrase():
    """Test adding key without passphrase when it needs a passphrase."""
    agent = PersistentSSHAgent()

    # Mock subprocess.Popen directly
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = (
        "stdout",
        "Enter passphrase for /home/user/.ssh/id_rsa:"
    )
    with patch("subprocess.Popen", return_value=mock_process):
        # Call _try_add_key_without_passphrase
        success, needs_passphrase = agent._try_add_key_without_passphrase("~/.ssh/id_rsa")

        # Verify the result
        assert success is False
        assert needs_passphrase is True


def test_try_add_key_without_passphrase_timeout():
    """Test adding key without passphrase with timeout."""
    agent = PersistentSSHAgent()

    # Mock subprocess.Popen directly
    mock_process = MagicMock()
    mock_process.communicate.side_effect = subprocess.TimeoutExpired("ssh-add", 1)
    with patch("subprocess.Popen", return_value=mock_process):
        # Call _try_add_key_without_passphrase
        success, needs_passphrase = agent._try_add_key_without_passphrase("~/.ssh/id_rsa")

        # Verify the result
        assert success is False
        assert needs_passphrase is True


def test_add_key_with_passphrase_success():
    """Test adding key with passphrase successfully."""
    agent = PersistentSSHAgent()

    # Mock subprocess.Popen directly
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = ("stdout", "stderr")
    with patch("subprocess.Popen", return_value=mock_process):
        # Call _add_key_with_passphrase
        result = agent._add_key_with_passphrase("~/.ssh/id_rsa", "passphrase")

        # Verify the result
        assert result is True


def test_add_key_with_passphrase_failure():
    """Test adding key with passphrase with failure."""
    agent = PersistentSSHAgent()

    # Mock subprocess.Popen directly
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = ("stdout", "Bad passphrase")
    with patch("subprocess.Popen", return_value=mock_process):
        # Call _add_key_with_passphrase
        result = agent._add_key_with_passphrase("~/.ssh/id_rsa", "passphrase")

        # Verify the result
        assert result is False
