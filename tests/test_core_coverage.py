"""Additional tests to improve code coverage for core SSH management module."""

# Import built-in modules
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Optional
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent
from persistent_ssh_agent.utils import extract_hostname
from persistent_ssh_agent.utils import is_valid_hostname
from persistent_ssh_agent.utils import run_command
import pytest


@pytest.fixture
def ssh_manager():
    """Create a PersistentSSHAgent instance."""
    return PersistentSSHAgent()


def _normalize_path(path: Optional[str]) -> Optional[str]:
    """Normalize path for cross-platform compatibility."""
    if path is None:
        return None
    return str(path).replace("\\", "/")


def test_run_command_with_timeout(ssh_manager):
    """Test command execution with timeout."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)

        result = run_command(["test"], timeout=1)
        assert result is None


def test_git_ssh_command_with_custom_options(ssh_manager, tmp_path):
    """Test Git SSH command generation with custom options."""
    # Create SSH directory and key file
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    key_file = ssh_dir / "id_rsa"
    key_file.write_text("test key content")

    # Create config file with absolute path
    config_file = ssh_dir / "config"
    config_file.write_text(f"""
Host github.com
    IdentityFile {key_file}
    User git
""")

    # Mock the SSH directory path and setup_ssh
    with patch.object(ssh_manager, "_ssh_dir", ssh_dir), patch.object(
        ssh_manager, "setup_ssh"
    ) as mock_setup, patch.object(ssh_manager, "_get_identity_file") as mock_get_identity:
        mock_setup.return_value = True
        mock_get_identity.return_value = str(key_file)

        command = ssh_manager.git.get_git_ssh_command("github.com")
        assert command is not None
        assert "-o StrictHostKeyChecking=no" in command
        assert key_file.name in command


def test_extract_hostname_edge_cases(ssh_manager):
    """Test hostname extraction with edge cases."""
    # Test with various edge cases
    test_cases = [
        ("git@example.com:user/repo.git", "example.com"),
        ("git@sub.domain.example.com:path/repo", "sub.domain.example.com"),
        ("git@192.168.1.1:user/repo.git", "192.168.1.1"),
        ("not_a_git_url", None),
        ("git@:user/repo.git", None),
    ]

    for url, expected in test_cases:
        assert extract_hostname(url) == expected


def test_save_agent_info_failure(ssh_manager):
    """Test agent info save failure handling."""
    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = IOError("Test error")
        ssh_manager._save_agent_info("test_sock", "test_pid")
        # Function should handle the error gracefully without raising exception


def test_load_agent_info_invalid_data(ssh_manager):
    """Test loading invalid agent info."""
    # Test with missing required fields
    with patch("builtins.open", mock_open(read_data='{"timestamp": 0}')):
        assert not ssh_manager._load_agent_info()

    # Test with expired timestamp
    with patch(
        "builtins.open",
        mock_open(
            read_data=json.dumps(
                {"SSH_AUTH_SOCK": "test_sock", "SSH_AGENT_PID": "test_pid", "timestamp": 0, "platform": os.name}
            )
        ),
    ):
        assert not ssh_manager._load_agent_info()


def test_verify_loaded_key(ssh_manager):
    """Test key verification in agent."""
    with patch("subprocess.run") as mock_subprocess_run:
        # Test successful verification
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["ssh-add", "-l"], returncode=0, stdout="test_key", stderr=""
        )
        assert ssh_manager._verify_loaded_key("test_key")

        # Test failed verification
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["ssh-add", "-l"], returncode=1, stdout="", stderr="error"
        )
        assert not ssh_manager._verify_loaded_key("test_key")

        # Test command failure (ssh-add not found)
        mock_subprocess_run.side_effect = FileNotFoundError("ssh-add not found")
        assert not ssh_manager._verify_loaded_key("test_key")


def test_start_ssh_agent_failure_modes(ssh_manager):
    """Test SSH agent startup failure modes."""
    with patch("subprocess.run") as mock_run:
        # Test agent start failure
        mock_run.return_value = subprocess.CompletedProcess(args=["ssh-agent"], returncode=1, stdout="", stderr="error")
        assert not ssh_manager._start_ssh_agent("test_key")

        # Test empty agent output
        mock_run.return_value = subprocess.CompletedProcess(args=["ssh-agent"], returncode=0, stdout="", stderr="")
        assert not ssh_manager._start_ssh_agent("test_key")


def test_parse_ssh_config_invalid_content(ssh_manager, tmp_path):
    """Test SSH config parsing with invalid content."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    config_file = ssh_dir / "config"

    # Test with invalid key-value pairs
    config_file.write_text("""
Host github.com
    InvalidKey=Value
    Port=abc
    User=
""")

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        config = ssh_manager._parse_ssh_config()
        assert "github.com" in config
        assert "invalidkey" not in config["github.com"]
        assert "port" not in config["github.com"]
        assert "user" not in config["github.com"]


def test_write_temp_key_failures(ssh_manager):
    """Test temporary key file writing failures."""
    # Test permission error
    with patch("tempfile.NamedTemporaryFile") as mock_temp:
        mock_temp.side_effect = PermissionError("Test error")
        assert ssh_manager._write_temp_key("test content") is None

    # Test with invalid content
    with patch("tempfile.NamedTemporaryFile") as mock_temp:
        mock_file = MagicMock()
        mock_file.write.side_effect = IOError("Write error")
        mock_temp.return_value.__enter__.return_value = mock_file
        assert ssh_manager._write_temp_key("") is None


def test_resolve_identity_file_paths(ssh_manager, tmp_path):
    """Test identity file path resolution."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    key_file = ssh_dir / "test_key"
    key_file.write_text("test content")

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        # Test absolute path
        assert _normalize_path(ssh_manager._resolve_identity_file(str(key_file))) == _normalize_path(str(key_file))

        # Test relative path
        assert _normalize_path(ssh_manager._resolve_identity_file("test_key")) == _normalize_path(str(key_file))

        # Test non-existent file
        assert ssh_manager._resolve_identity_file("non_existent") is None


def test_get_identity_file_sources(ssh_manager, tmp_path):
    """Test identity file retrieval from different sources."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    key_file = ssh_dir / "id_rsa"
    key_file.write_text("test content")

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir), patch.object(ssh_manager.ssh_key_manager, "ssh_dir", ssh_dir):
        # Test environment variable source
        with patch.dict(os.environ, {"SSH_IDENTITY_FILE": str(key_file)}):
            assert _normalize_path(ssh_manager._get_identity_file("github.com")) == _normalize_path(str(key_file))

        # Test SSH config source
        config_file = ssh_dir / "config"
        config_file.write_text(f"""Host github.com
    IdentityFile {key_file}
""")
        # Recreate SSH config parser with test directory
        # Import third-party modules
        from persistent_ssh_agent.ssh_config_parser import SSHConfigParser

        ssh_manager.ssh_config_parser = SSHConfigParser(ssh_dir)

        assert _normalize_path(ssh_manager._get_identity_file("github.com")) == _normalize_path(str(key_file))

        # Test fallback to available keys
        os.remove(config_file)
        pub_key = key_file.with_suffix(".pub")
        pub_key.write_text("test pub key")
        assert _normalize_path(ssh_manager._get_identity_file("github.com")) == _normalize_path(str(key_file))


def test_add_key_with_passphrase(ssh_manager):
    """Test adding SSH key with passphrase."""
    with patch("subprocess.Popen") as mock_popen:
        # Mock process for successful key addition
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        assert ssh_manager._add_key_with_passphrase("test_key", "passphrase")

        # Test process failure
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error")
        assert not ssh_manager._add_key_with_passphrase("test_key", "passphrase")


def test_test_ssh_connection_scenarios(ssh_manager):
    """Test SSH connection testing with various scenarios."""
    with patch("subprocess.run") as mock_subprocess_run:
        # Test successful connection
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["ssh", "-T", "-o", "StrictHostKeyChecking=no", "git@test_host"],
            returncode=1,  # Git servers often return 1 for successful auth
            stdout="Hi user! You've successfully authenticated",
            stderr="",
        )
        assert ssh_manager._test_ssh_connection("test_host")

        # Test connection failure with error code
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["ssh", "-T", "-o", "StrictHostKeyChecking=no", "git@test_host"],
            returncode=255,  # SSH specific error code
            stdout="",
            stderr="Connection refused",
        )
        assert not ssh_manager._test_ssh_connection("test_host")

        # Test timeout error (ssh command not found)
        mock_subprocess_run.side_effect = FileNotFoundError("ssh not found")
        assert not ssh_manager._test_ssh_connection("test_host")


def test_setup_ssh_with_identity_file(ssh_manager):
    """Test SSH setup with identity file."""
    test_key = "/tmp/test_key"

    with patch.object(ssh_manager, "_start_ssh_agent") as mock_start, patch.object(
        ssh_manager, "_test_ssh_connection"
    ) as mock_test, patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, patch(
        "os.path.exists"
    ) as mock_exists:
        # Test successful setup
        mock_start.return_value = True
        mock_test.return_value = True
        mock_get_identity.return_value = test_key
        mock_exists.return_value = True

        assert ssh_manager.setup_ssh("github.com")

        # Test failure in agent start
        mock_start.return_value = False
        assert not ssh_manager.setup_ssh("github.com")

        # Test missing identity file
        mock_get_identity.return_value = None
        assert not ssh_manager.setup_ssh("github.com")


def test_parse_ssh_agent_output_edge_cases(ssh_manager):
    """Test SSH agent output parsing with edge cases."""
    # Test with empty output
    assert not ssh_manager._parse_ssh_agent_output("")

    # Test with invalid format
    output = "invalid output without equals"
    parsed = ssh_manager._parse_ssh_agent_output(output)
    assert not any(key in parsed for key in ("SSH_AUTH_SOCK", "SSH_AGENT_PID"))

    # Test with missing required variables
    output = "SSH_OTHER_VAR=value; export SSH_OTHER_VAR;"
    parsed = ssh_manager._parse_ssh_agent_output(output)
    assert not any(key in parsed for key in ("SSH_AUTH_SOCK", "SSH_AGENT_PID"))

    # Test with valid output
    output = "SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
    result = ssh_manager._parse_ssh_agent_output(output)
    assert result["SSH_AUTH_SOCK"] == "/tmp/ssh.sock"
    assert result["SSH_AGENT_PID"] == "123"


def test_try_add_key_without_passphrase(ssh_manager):
    """Test adding SSH key without passphrase."""
    with patch("subprocess.Popen") as mock_popen:
        # Test successful addition
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        success, needs_passphrase = ssh_manager._try_add_key_without_passphrase("test_key")
        assert success
        assert not needs_passphrase

        # Test key requires passphrase
        mock_process = MagicMock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = (b"", b"Enter passphrase")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        # Mock the stderr check
        def communicate_side_effect(*args, **kwargs):
            if "timeout" in kwargs and kwargs["timeout"] == 1:
                return b"", b"Enter passphrase"
            return b"", b""

        mock_process.communicate.side_effect = communicate_side_effect

        success, needs_passphrase = ssh_manager._try_add_key_without_passphrase("test_key")
        assert not success
        assert needs_passphrase


def test_error_handling_scenarios(ssh_manager):
    """Test various error handling scenarios."""
    with patch("os.path.exists") as mock_exists, patch("builtins.open", mock_open()) as mock_file, patch(
        "json.dump"
    ) as mock_dump:
        # Test file operation errors
        mock_exists.return_value = True
        mock_dump.side_effect = IOError("Mock IO Error")
        mock_file.side_effect = IOError("Mock file error")

        # Test save agent info with file error
        ssh_manager._save_agent_info("test_sock", "test_pid")

        # Test load agent info with invalid data
        mock_file.side_effect = None
        mock_file.return_value.read.return_value = "invalid json"
        assert not ssh_manager._load_agent_info()


def test_ssh_key_management_edge_cases(ssh_manager):
    """Test edge cases in SSH key management."""
    with patch("persistent_ssh_agent.utils.run_command") as mock_run:
        # Test key verification failure
        mock_run.return_value = None
        assert not ssh_manager._verify_loaded_key("test_key")

        # Test start ssh agent with command failure
        mock_run.side_effect = [None, None]
        assert not ssh_manager._start_ssh_agent("test_key")

        # Test add key with invalid process
        mock_run.side_effect = None
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"Invalid key")
        assert not ssh_manager._add_ssh_key("test_key")


def test_identity_file_resolution(ssh_manager):
    """Test identity file resolution."""
    with patch("os.path.expanduser") as mock_expand, patch("os.path.abspath") as mock_abspath, patch(
        "os.path.exists"
    ) as mock_exists:
        # Test with absolute path
        mock_expand.return_value = "/absolute/path/key"
        mock_abspath.return_value = "/absolute/path/key"
        mock_exists.return_value = True
        result = ssh_manager._resolve_identity_file("/absolute/path/key")
        assert _normalize_path(result) == _normalize_path("/absolute/path/key")

        # Test with relative path
        mock_expand.return_value = "relative/path/key"
        mock_abspath.return_value = "/current/dir/relative/path/key"
        mock_exists.return_value = True
        result = ssh_manager._resolve_identity_file("relative/path/key")
        assert _normalize_path(result) == _normalize_path("/current/dir/relative/path/key")

        # Test with home directory
        mock_expand.return_value = "/home/user/.ssh/id_rsa"
        mock_abspath.return_value = "/home/user/.ssh/id_rsa"
        mock_exists.return_value = True
        result = ssh_manager._resolve_identity_file("~/.ssh/id_rsa")
        assert _normalize_path(result) == _normalize_path("/home/user/.ssh/id_rsa")

        # Test with non-existent file
        mock_exists.return_value = False
        result = ssh_manager._resolve_identity_file("/non/existent/file")
        assert result is None


def test_available_keys_handling(ssh_manager):
    """Test handling of available SSH keys."""
    with patch("persistent_ssh_agent.utils.run_command") as mock_run, patch("os.path.exists") as mock_exists, patch(
        "glob.glob"
    ) as mock_glob:
        # Mock ssh-add -l output
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"""2048 SHA256:abc123 /home/user/.ssh/id_rsa (RSA)
2048 SHA256:def456 /home/user/.ssh/id_rsa2 (RSA)""",
            stderr=b"",
        )

        # Mock file existence checks
        def exists_side_effect(path):
            path_str = str(path).replace("\\", "/")  # Normalize path for comparison
            valid_paths = [
                "/home/user/.ssh/id_rsa",
                "/home/user/.ssh/id_rsa.pub",
                "/home/user/.ssh/id_rsa2",
                "/home/user/.ssh/id_rsa2.pub",
            ]
            return path_str in valid_paths

        mock_exists.side_effect = exists_side_effect

        # Mock glob behavior
        def glob_side_effect(pattern):
            pattern_str = str(pattern).replace("\\", "/")  # Normalize pattern for comparison
            if "id_rsa[0-9]*" in pattern_str:
                return [os.path.join(str(ssh_manager._ssh_dir), "id_rsa2")]
            return []

        mock_glob.side_effect = glob_side_effect

        # Mock the _ssh_dir property and ssh_key_manager
        with patch.object(ssh_manager, "_ssh_dir", Path("/home/user/.ssh")), patch.object(
            ssh_manager.ssh_key_manager, "ssh_dir", Path("/home/user/.ssh")
        ):
            # Test getting available keys
            keys = ssh_manager._get_available_keys()
            # Should find both id_rsa (base key) and id_rsa2 (numbered key)
            assert len(keys) == 2
            assert "/home/user/.ssh/id_rsa" in keys
            assert "/home/user/.ssh/id_rsa2" in keys


def test_ssh_agent_info_handling(ssh_manager):
    """Test SSH agent info handling."""
    with patch("builtins.open", mock_open()), patch("json.load") as mock_load, patch(
        "pathlib.Path.exists"
    ) as mock_exists, patch("subprocess.run") as mock_subprocess_run:
        # Set up mocks for successful load
        mock_exists.return_value = True
        mock_load.return_value = {
            "timestamp": time.time(),
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid",
            "platform": os.name,
        }
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["ssh-add", "-l"], returncode=0, stdout=b"", stderr=b""
        )

        # Test loading agent info
        assert ssh_manager._load_agent_info()

        # Verify environment variables
        assert os.environ.get("SSH_AUTH_SOCK") == "test_sock"
        assert os.environ.get("SSH_AGENT_PID") == "test_pid"

        # Test with missing fields
        mock_load.return_value = {"timestamp": time.time(), "SSH_AUTH_SOCK": "test_sock"}
        assert not ssh_manager._load_agent_info()

        # Test with expired timestamp
        mock_load.return_value = {
            "timestamp": time.time() - 90000,  # Expired
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid",
            "platform": os.name,
        }
        assert not ssh_manager._load_agent_info()

        # Test with invalid JSON
        mock_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        assert not ssh_manager._load_agent_info()

        # Test with non-running agent
        mock_load.side_effect = None
        mock_load.return_value = {
            "timestamp": time.time(),
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid",
            "platform": os.name,
        }
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=["ssh-add", "-l"], returncode=2, stdout=b"", stderr=b""
        )
        assert not ssh_manager._load_agent_info()


def test_ssh_connection_handling(ssh_manager):
    """Test SSH connection handling."""
    with patch("subprocess.run") as mock_subprocess_run, patch.object(
        ssh_manager, "_get_identity_file"
    ) as mock_get_identity, patch("os.path.exists") as mock_exists, patch.object(
        ssh_manager, "_start_ssh_agent"
    ) as mock_start_agent:
        mock_get_identity.return_value = "/path/to/key"
        mock_exists.return_value = True
        mock_start_agent.return_value = True

        # Test successful connection (returncode=1 is success for Git servers)
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"")
        assert ssh_manager._test_ssh_connection("test.example.com")

        # Test failed connection
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=255, stdout=b"", stderr=b"Connection refused"
        )
        assert not ssh_manager._test_ssh_connection("test.example.com")

        # Test connection timeout (ssh command not found)
        mock_subprocess_run.side_effect = FileNotFoundError("ssh not found")
        assert not ssh_manager._test_ssh_connection("test.example.com")


def test_git_ssh_command_generation(ssh_manager):
    """Test Git SSH command generation."""
    with patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, patch(
        "os.path.exists"
    ) as mock_exists, patch.object(ssh_manager, "_start_ssh_agent") as mock_start_agent, patch.object(
        ssh_manager, "_test_ssh_connection"
    ) as mock_test_connection:
        # Test with valid identity file
        mock_get_identity.return_value = "/path/to/key"
        mock_exists.return_value = True
        mock_start_agent.return_value = True
        mock_test_connection.return_value = True

        cmd = ssh_manager.git.get_git_ssh_command("github.com")
        assert "ssh" in cmd
        assert "-i" in cmd
        assert "/path/to/key" in cmd

        # Test with invalid identity file
        mock_get_identity.return_value = None
        assert ssh_manager.git.get_git_ssh_command("github.com") is None


def test_ssh_setup_with_custom_config(ssh_manager):
    """Test SSH setup with custom configuration."""
    with patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, patch.object(
        ssh_manager, "_start_ssh_agent"
    ) as mock_start_agent, patch.object(ssh_manager, "_test_ssh_connection") as mock_test_connection, patch(
        "os.path.exists"
    ) as mock_exists:
        # Test successful setup
        mock_get_identity.return_value = "/path/to/key"
        mock_exists.return_value = True
        mock_start_agent.return_value = True
        mock_test_connection.return_value = True
        assert ssh_manager.setup_ssh("github.com")

        # Test setup with missing identity file
        mock_get_identity.return_value = None
        assert not ssh_manager.setup_ssh("github.com")

        # Test setup with agent start failure
        mock_get_identity.return_value = "/path/to/key"
        mock_start_agent.return_value = False
        assert not ssh_manager.setup_ssh("github.com")


def test_ssh_agent_start_failure_scenarios(ssh_manager):
    """Test SSH agent start failure scenarios."""
    with patch("persistent_ssh_agent.utils.run_command") as mock_run, patch("os.environ") as mock_environ:
        # Test agent start command failure
        mock_run.return_value = None
        mock_environ.copy.return_value = {}
        assert not ssh_manager._start_ssh_agent("test_key")

        # Test agent environment variable setting failure
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"SSH_AUTH_SOCK=/tmp/ssh-XXX/agent.123; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;\n",
            stderr=b"",
        )
        mock_environ.__setitem__.side_effect = Exception("Mock environ error")
        assert not ssh_manager._start_ssh_agent("test_key")


def test_file_operation_errors(ssh_manager):
    """Test file operation error scenarios."""
    with patch("builtins.open") as mock_open, patch("os.path.exists") as mock_exists:
        # Test file read error
        mock_exists.return_value = True
        mock_open.side_effect = PermissionError("Mock permission error")
        assert not ssh_manager._load_agent_info()

        # Test file write error with directory creation failure
        mock_exists.return_value = False
        mock_open.side_effect = OSError("Mock directory creation error")
        ssh_manager._save_agent_info("test_sock", "test_pid")


def test_ssh_config_parsing_errors(ssh_manager):
    """Test SSH config parsing error scenarios."""
    # Import built-in modules
    from textwrap import dedent

    config_data = dedent("""
        Host test
            HostName test.example.com
            User testuser
            Port invalid_port
            IdentityFile ~/.ssh/test_key
    """).lstrip()

    with patch("pathlib.Path.exists") as mock_exists, patch("builtins.open", mock_open(read_data=config_data)):
        mock_exists.return_value = True
        config = ssh_manager._parse_ssh_config()

        # Verify that test host is in config despite invalid port
        assert "test" in config
        assert config["test"]["hostname"] == "test.example.com"
        assert config["test"]["user"] == "testuser"
        assert "port" not in config["test"]  # Invalid port should be ignored
        assert isinstance(config["test"]["identityfile"], list)
        assert "~/.ssh/test_key" in config["test"]["identityfile"]

        # Test with invalid file content
        with patch("builtins.open", mock_open(read_data="Invalid Config")):
            config = ssh_manager._parse_ssh_config()
            assert config == {}

        # Test with file read error
        with patch("builtins.open", side_effect=IOError("File read error")):
            config = ssh_manager._parse_ssh_config()
            assert config == {}


def test_ssh_key_management_failures(ssh_manager):
    """Test SSH key management failure scenarios."""
    with patch("persistent_ssh_agent.utils.run_command") as mock_run, patch("os.path.exists") as mock_exists, patch(
        "builtins.open", mock_open(read_data="test key data")
    ), patch("subprocess.Popen") as mock_popen:
        # Mock Popen to avoid actual subprocess creation
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"Error loading key")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        # Test key loading failure
        mock_exists.return_value = True
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"", stderr=b"Error loading key"
        )
        assert not ssh_manager._try_add_key_without_passphrase("test_key")[0]

        # Test key verification timeout
        mock_run.return_value = None
        assert not ssh_manager._verify_loaded_key(b"test_key")

        # Test key addition with invalid key
        mock_exists.return_value = False
        success, needs_passphrase = ssh_manager._try_add_key_without_passphrase("invalid_key")
        assert not success
        assert not needs_passphrase


def test_ssh_connection_failures(ssh_manager):
    """Test SSH connection failure scenarios."""
    with patch("persistent_ssh_agent.utils.run_command") as mock_run, patch.object(
        ssh_manager, "_get_identity_file"
    ) as mock_get_identity:
        # Test connection with invalid hostname
        assert not ssh_manager._test_ssh_connection("invalid@host")

        # Test connection with timeout
        mock_get_identity.return_value = "test_key"
        mock_run.return_value = None
        assert not ssh_manager._test_ssh_connection("test.example.com")

        # Test connection with authentication failure
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=255, stdout=b"", stderr=b"Permission denied"
        )
        assert not ssh_manager._test_ssh_connection("test.example.com")


def test_git_command_edge_cases(ssh_manager):
    """Test Git command generation edge cases."""
    with patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, patch("os.path.exists") as mock_exists:
        # Test with missing identity file
        mock_get_identity.return_value = None
        assert ssh_manager.git.get_git_ssh_command("github.com") is None

        # Test with non-existent identity file
        mock_get_identity.return_value = "test_key"
        mock_exists.return_value = False
        assert ssh_manager.git.get_git_ssh_command("github.com") is None

        # Test with invalid hostname
        mock_exists.return_value = True
        assert ssh_manager.git.get_git_ssh_command("invalid@host") is None


def test_git_credential_helper(ssh_manager, tmp_path):
    """Test Git credential helper functionality."""
    # Create a temporary credential helper script
    credential_helper = tmp_path / "credential-helper.sh"
    credential_helper.write_text("#!/bin/bash\necho username=$GIT_USERNAME\necho password=$GIT_PASSWORD\n")

    # Make it executable on non-Windows platforms
    if os.name != "nt":
        os.chmod(credential_helper, 0o755)

    # Test get_git_credential_command
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
        helper_path = ssh_manager.git.get_git_credential_command(str(credential_helper))
        assert helper_path is not None
        assert str(credential_helper).replace("\\", "/") in helper_path

    # Test with non-existent path
    with patch("os.path.exists", return_value=False):
        assert ssh_manager.git.get_git_credential_command("/non/existent/path") is None

    # Test configure_git_with_credential_helper
    with patch.object(ssh_manager.git, "get_git_credential_command") as mock_get_credential, patch(
        "subprocess.run"
    ) as mock_subprocess_run:
        mock_get_credential.return_value = str(credential_helper)
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        assert ssh_manager.git.configure_git_with_credential_helper(str(credential_helper)) is True
        mock_subprocess_run.assert_called_once()

        # Test with command failure
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)
        assert ssh_manager.git.configure_git_with_credential_helper(str(credential_helper)) is False


def test_setup_git_credentials(ssh_manager):
    """Test simplified Git credentials setup functionality."""
    # Test with direct username/password
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        assert ssh_manager.git.setup_git_credentials("testuser", "testpass") is True
        # Should be called twice: once for get_current_credential_helpers, once for config
        assert mock_subprocess_run.call_count == 2

        # Verify the second call (config command) contains the credentials
        config_call_args = mock_subprocess_run.call_args_list[1][0][0]
        assert "git" in config_call_args
        assert "config" in config_call_args
        assert "--replace-all" in config_call_args
        assert "credential.helper" in config_call_args

    # Test with environment variables
    with patch.dict(os.environ, {"GIT_USERNAME": "envuser", "GIT_PASSWORD": "envpass"}), patch(
        "subprocess.run"
    ) as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        assert ssh_manager.git.setup_git_credentials() is True
        # Should be called twice: once for get_current_credential_helpers, once for config
        assert mock_subprocess_run.call_count == 2

    # Test with missing credentials
    with patch.dict(os.environ, {}, clear=True):
        assert ssh_manager.git.setup_git_credentials() is False

    # Test with command failure
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)

        assert ssh_manager.git.setup_git_credentials("testuser", "testpass") is False


def test_setup_git_credentials_stderr_handling(ssh_manager):
    """Test Git credentials setup with stderr handling (both string and bytes)."""
    # Test with string stderr (current behavior after fix)
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stderr="Git config error message"
        )

        result = ssh_manager.git.setup_git_credentials("testuser", "testpass")
        assert result is False

    # Test with bytes stderr (edge case for compatibility)
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stderr=b"Git config error message"
        )

        result = ssh_manager.git.setup_git_credentials("testuser", "testpass")
        assert result is False

    # Test with empty stderr
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stderr="")

        result = ssh_manager.git.setup_git_credentials("testuser", "testpass")
        assert result is False

    # Test with None stderr
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stderr=None)

        result = ssh_manager.git.setup_git_credentials("testuser", "testpass")
        assert result is False


def test_get_current_credential_helpers(ssh_manager):
    """Test getting current Git credential helpers."""
    # Test with multiple helpers
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="helper1\nhelper2\n"
        )

        helpers = ssh_manager.git.get_current_credential_helpers()
        assert helpers == ["helper1", "helper2"]

    # Test with single helper
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="helper1\n")

        helpers = ssh_manager.git.get_current_credential_helpers()
        assert helpers == ["helper1"]

    # Test with no helpers
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="")

        helpers = ssh_manager.git.get_current_credential_helpers()
        assert helpers == []

    # Test with command failure
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = None

        helpers = ssh_manager.git.get_current_credential_helpers()
        assert helpers == []


def test_setup_git_credentials_with_replace_all(ssh_manager):
    """Test Git credentials setup uses --replace-all flag."""
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        result = ssh_manager.git.setup_git_credentials("testuser", "testpass")
        assert result is True

        # Verify --replace-all flag is used
        call_args = mock_subprocess_run.call_args[0][0]
        assert "git" in call_args
        assert "config" in call_args
        assert "--global" in call_args
        assert "--replace-all" in call_args
        assert "credential.helper" in call_args


def test_clear_credential_helpers(ssh_manager):
    """Test clearing Git credential helpers."""
    # Test clearing when helpers exist
    with patch("subprocess.run") as mock_subprocess_run:
        # Mock get_current_credential_helpers to return helpers
        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="helper1\nhelper2\n"),
            subprocess.CompletedProcess(args=[], returncode=0),
        ]

        result = ssh_manager.git.clear_credential_helpers()
        assert result is True
        assert mock_subprocess_run.call_count == 2

        # Verify --unset-all flag is used
        clear_call_args = mock_subprocess_run.call_args_list[1][0][0]
        assert "git" in clear_call_args
        assert "config" in clear_call_args
        assert "--global" in clear_call_args
        assert "--unset-all" in clear_call_args
        assert "credential.helper" in clear_call_args

    # Test clearing when no helpers exist
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="")

        result = ssh_manager.git.clear_credential_helpers()
        assert result is True
        # Should only call get_current_credential_helpers, not the clear command
        assert mock_subprocess_run.call_count == 1

    # Test clearing with command failure
    with patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="helper1\n"),
            subprocess.CompletedProcess(args=[], returncode=1, stderr="Error clearing helpers"),
        ]

        result = ssh_manager.git.clear_credential_helpers()
        assert result is False


def test_setup_git_credentials_with_multiple_values_error(ssh_manager):
    """Test Git credentials setup with multiple values error provides helpful suggestion."""
    with patch("subprocess.run") as mock_subprocess_run:
        # Mock get_current_credential_helpers call
        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="helper1\nhelper2\n"),
            subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stderr="warning: credential.helper has multiple values\nerror: cannot overwrite multiple values",
            ),
        ]

        result = ssh_manager.git.setup_git_credentials("testuser", "testpass")
        assert result is False
        assert mock_subprocess_run.call_count == 2


def test_platform_specific_credential_helper(ssh_manager):
    """Test platform-specific credential helper generation."""
    # Test Windows credential helper
    with patch("os.name", "nt"):
        helper = ssh_manager.git._create_platform_credential_helper("testuser", "testpass")
        assert ";" in helper  # Windows uses semicolon to separate commands (PowerShell compatible)
        assert "echo username=testuser" in helper
        assert "echo password=testpass" in helper
        assert helper.startswith("!")
        assert "&&" not in helper  # Should not use cmd.exe specific syntax

    # Test Unix credential helper
    with patch("os.name", "posix"):
        helper = ssh_manager.git._create_platform_credential_helper("testuser", "testpass")
        assert "{ echo username=testuser; echo password=testpass; }" in helper
        assert helper.startswith("!")


def test_credential_escaping(ssh_manager):
    """Test credential value escaping for different platforms."""
    # Test Windows escaping
    with patch("os.name", "nt"):
        escaped = ssh_manager.git._escape_credential_value('test"value%special')
        assert '""' in escaped  # Double quotes should be escaped
        assert "%%" in escaped  # Percent signs should be escaped

    # Test Unix escaping
    with patch("os.name", "posix"):
        escaped = ssh_manager.git._escape_credential_value("test\"value'special")
        assert '\\"' in escaped  # Double quotes should be escaped
        # Test that single quotes are properly escaped
        assert "'\"'\"'" in escaped


def test_context_manager(ssh_manager):
    """Test PersistentSSHAgent as context manager."""
    # Test basic context manager functionality
    with ssh_manager as agent:
        assert agent is ssh_manager

    # Test that no exceptions are raised during exit
    try:
        with ssh_manager:
            pass
    except Exception:
        pytest.fail("Context manager should not raise exceptions during normal exit")


def test_error_handling_edge_cases(ssh_manager):
    """Test error handling edge cases."""
    # Import built-in modules
    import time

    with patch("persistent_ssh_agent.utils.run_command") as mock_run, patch(
        "builtins.open", mock_open()
    ) as mock_file, patch("os.path.exists") as mock_exists, patch("json.load") as mock_load, patch(
        "os.name", "nt"
    ):  # Mock Windows platform for consistent testing
        # Test file read error with permission denied
        mock_exists.return_value = True
        mock_file.side_effect = PermissionError("Mock permission error")
        assert not ssh_manager._load_agent_info()

        # Test JSON parse error
        mock_file.side_effect = None
        mock_load.side_effect = json.JSONDecodeError("Mock JSON error", "", 0)
        assert not ssh_manager._load_agent_info()

        # Test environment variable error
        mock_load.side_effect = None
        mock_load.return_value = {
            "timestamp": time.time(),
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid",
            "platform": "nt",  # Match the mocked Windows platform
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout=b"",
            stderr=b"",  # Return code 2 indicates agent not running
        )
        with patch.dict(os.environ, {}, clear=True):
            assert not ssh_manager._load_agent_info()

        # Test platform mismatch error
        mock_load.return_value = {
            "timestamp": time.time(),
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid",
            "platform": "posix",  # Mismatch with Windows platform
        }
        assert not ssh_manager._load_agent_info()


def test_ssh_config_advanced_parsing(ssh_manager):
    """Test advanced SSH config parsing scenarios."""
    # Import built-in modules
    from textwrap import dedent

    config_data = dedent("""
        Host *
            Port 22
            IdentityFile ~/.ssh/default_key
            StrictHostKeyChecking no

        Host test1
            HostName test1.example.com
            User testuser
            Port invalid_port
            IdentityFile ~/.ssh/test1_key

        Host test2
            HostName test2.example.com
            IdentityFile ~/.ssh/test2_key
            Port 2222
            User test2user

        Match host test3
            HostName test3.example.com
            User test3user
            Port 2222

        Include ~/.ssh/config.d/*.conf
    """).lstrip()

    with patch("pathlib.Path.exists") as mock_exists, patch("builtins.open", mock_open(read_data=config_data)):
        mock_exists.return_value = True

        # Mock glob for Include directive
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = []
            config = ssh_manager._parse_ssh_config()

            # Check wildcard host settings
            assert "*" in config
            assert config["*"]["port"] == "22"
            assert isinstance(config["*"]["identityfile"], list)
            assert "~/.ssh/default_key" in config["*"]["identityfile"]
            assert config["*"]["stricthostkeychecking"] == "no"

            # Check specific host settings
            assert "test1" in config
            assert config["test1"]["hostname"] == "test1.example.com"
            assert config["test1"]["user"] == "testuser"
            assert "port" not in config["test1"]  # Invalid port should be ignored
            assert isinstance(config["test1"]["identityfile"], list)
            assert "~/.ssh/test1_key" in config["test1"]["identityfile"]

            assert "test2" in config
            assert config["test2"]["hostname"] == "test2.example.com"
            assert config["test2"]["user"] == "test2user"
            assert config["test2"]["port"] == "2222"
            assert isinstance(config["test2"]["identityfile"], list)
            assert "~/.ssh/test2_key" in config["test2"]["identityfile"]

            # Check Match block parsing
            assert "test3" in config
            assert config["test3"]["hostname"] == "test3.example.com"
            assert config["test3"]["user"] == "test3user"
            assert config["test3"]["port"] == "2222"

            # Test Include directive
            mock_glob.return_value = ["/path/to/included.conf"]
            with patch(
                "builtins.open",
                mock_open(
                    read_data="""
Host included
    HostName included.example.com
    User includeduser
"""
                ),
            ):
                config = ssh_manager._parse_ssh_config()
                assert "included" in config
                assert config["included"]["hostname"] == "included.example.com"
                assert config["included"]["user"] == "includeduser"


def test_url_hostname_extraction(ssh_manager):
    """Test hostname extraction from URLs."""
    # Test valid SSH URLs
    assert extract_hostname("git@github.com:user/repo.git") == "github.com"
    assert extract_hostname("git@example.com:8080/repo.git") == "example.com"

    # Test invalid URLs
    assert extract_hostname("invalid_url") is None
    assert extract_hostname("git@") is None
    assert extract_hostname("") is None


def test_hostname_validation(ssh_manager):
    """Test hostname validation logic."""
    # Test valid hostnames
    assert is_valid_hostname("example.com")
    assert is_valid_hostname("sub.example.com")
    assert is_valid_hostname("example-1.com")

    # Test invalid hostnames
    assert not is_valid_hostname("")
    assert not is_valid_hostname("a" * 256)  # Too long
    assert not is_valid_hostname("-example.com")  # Starts with hyphen
    assert not is_valid_hostname("example-.com")  # Ends with hyphen
    assert not is_valid_hostname("exam@ple.com")  # Invalid character


def test_agent_reuse_enabled(tmp_path):
    """Test SSH agent reuse when enabled."""
    # Setup
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    agent = PersistentSSHAgent(reuse_agent=True)
    agent._ssh_dir = ssh_dir
    agent._agent_info_file = ssh_dir / "agent_info.json"

    # Create mock agent info
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time(),
        "platform": "nt" if os.name == "nt" else "posix",
    }
    with open(agent._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    # Mock subprocess.run to simulate running agent
    def mock_subprocess_run(command, **kwargs):
        if command == ["ssh-add", "-l"]:
            return subprocess.CompletedProcess(command, returncode=1, stdout="")
        return subprocess.CompletedProcess(command, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        # Test loading existing agent
        assert agent._load_agent_info() is True
        assert os.environ.get("SSH_AUTH_SOCK") == agent_info["SSH_AUTH_SOCK"]
        assert os.environ.get("SSH_AGENT_PID") == agent_info["SSH_AGENT_PID"]


def test_agent_reuse_disabled(tmp_path):
    """Test SSH agent reuse when disabled."""
    # Setup
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    agent = PersistentSSHAgent(reuse_agent=False)
    agent._ssh_dir = ssh_dir
    agent._agent_info_file = ssh_dir / "agent_info.json"

    # Create mock agent info
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time(),
        "platform": "nt" if os.name == "nt" else "posix",
    }
    with open(agent._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    # Mock _start_ssh_agent to verify it's called
    original_start_ssh_agent = agent._start_ssh_agent
    start_ssh_agent_called = False

    def mock_start_ssh_agent(identity_file):
        nonlocal start_ssh_agent_called
        start_ssh_agent_called = True
        return original_start_ssh_agent(identity_file)

    agent._start_ssh_agent = mock_start_ssh_agent

    # Test that a new agent is started
    identity_file = ssh_dir / "id_rsa"
    identity_file.touch()
    agent._start_ssh_agent(str(identity_file))
    assert start_ssh_agent_called is True


def test_agent_reuse_expired(tmp_path):
    """Test SSH agent reuse when agent info is expired."""
    # Setup
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    agent = PersistentSSHAgent(expiration_time=1, reuse_agent=True)
    agent._ssh_dir = ssh_dir
    agent._agent_info_file = ssh_dir / "agent_info.json"

    # Create expired agent info
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time() - 2,  # Expired
        "platform": "nt" if os.name == "nt" else "posix",
    }
    with open(agent._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    # Test that expired agent info is not loaded
    assert agent._load_agent_info() is False


def test_agent_reuse_with_existing_key(tmp_path):
    """Test SSH agent reuse with existing key verification."""
    # Setup
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    agent = PersistentSSHAgent(reuse_agent=True)
    agent._ssh_dir = ssh_dir
    agent._agent_info_file = ssh_dir / "agent_info.json"

    # Create mock agent info
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time(),
        "platform": "nt" if os.name == "nt" else "posix",
    }
    with open(agent._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    # Create test key file
    identity_file = ssh_dir / "id_rsa"
    identity_file.touch()

    # Mock subprocess.run to simulate existing agent with loaded key
    def mock_subprocess_run(command, **kwargs):
        if command == ["ssh-add", "-l"]:
            return subprocess.CompletedProcess(command, returncode=0, stdout=str(identity_file))
        return subprocess.CompletedProcess(command, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        # Test loading existing agent with key
        assert agent._load_agent_info() is True
        assert agent._verify_loaded_key(str(identity_file)) is True
        assert os.environ.get("SSH_AUTH_SOCK") == agent_info["SSH_AUTH_SOCK"]
        assert os.environ.get("SSH_AGENT_PID") == agent_info["SSH_AGENT_PID"]


def test_agent_reuse_with_key_not_loaded(tmp_path):
    """Test SSH agent reuse when key is not loaded."""
    # Setup
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    agent = PersistentSSHAgent(reuse_agent=True)
    agent._ssh_dir = ssh_dir
    agent._agent_info_file = ssh_dir / "agent_info.json"

    # Create mock agent info
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time(),
        "platform": "nt" if os.name == "nt" else "posix",
    }
    with open(agent._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    # Create test key file
    identity_file = ssh_dir / "id_rsa"
    identity_file.touch()

    # Mock subprocess.run to simulate existing agent without loaded key
    def mock_subprocess_run(command, **kwargs):
        if command == ["ssh-add", "-l"]:
            return subprocess.CompletedProcess(command, returncode=0, stdout="")
        return subprocess.CompletedProcess(command, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        # Test loading existing agent without key
        assert agent._load_agent_info() is True
        assert agent._verify_loaded_key(str(identity_file)) is False
        assert os.environ.get("SSH_AUTH_SOCK") == agent_info["SSH_AUTH_SOCK"]
        assert os.environ.get("SSH_AGENT_PID") == agent_info["SSH_AGENT_PID"]
