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
import pytest


@pytest.fixture
def ssh_manager():
    """Create a PersistentSSHAgent instance."""
    return PersistentSSHAgent()


def _normalize_path(path: Optional[str]) -> Optional[str]:
    """Normalize path for cross-platform compatibility."""
    if path is None:
        return None
    return str(Path(path)).replace("\\", "/")


def test_run_command_with_timeout(ssh_manager):
    """Test command execution with timeout."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)

        result = ssh_manager.run_command(["test"], timeout=1)
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
    with patch.object(ssh_manager, "_ssh_dir", ssh_dir), \
         patch.object(ssh_manager, "setup_ssh") as mock_setup, \
         patch.object(ssh_manager, "_get_identity_file") as mock_get_identity:
        mock_setup.return_value = True
        mock_get_identity.return_value = str(key_file)

        command = ssh_manager.get_git_ssh_command("github.com")
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
        assert ssh_manager._extract_hostname(url) == expected


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
    with patch("builtins.open", mock_open(read_data=json.dumps({
        "SSH_AUTH_SOCK": "test_sock",
        "SSH_AGENT_PID": "test_pid",
        "timestamp": 0,
        "platform": os.name
    }))):
        assert not ssh_manager._load_agent_info()


def test_verify_loaded_key(ssh_manager):
    """Test key verification in agent."""
    with patch.object(ssh_manager, "run_command") as mock_run:
        # Test successful verification
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh-add", "-l"],
            returncode=0,
            stdout="test_key",
            stderr=""
        )
        assert ssh_manager._verify_loaded_key("test_key")

        # Test failed verification
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh-add", "-l"],
            returncode=1,
            stdout="",
            stderr="error"
        )
        assert not ssh_manager._verify_loaded_key("test_key")


def test_start_ssh_agent_failure_modes(ssh_manager):
    """Test SSH agent startup failure modes."""
    with patch("subprocess.run") as mock_run:
        # Test agent start failure
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh-agent"],
            returncode=1,
            stdout="",
            stderr="error"
        )
        assert not ssh_manager._start_ssh_agent("test_key")

        # Test empty agent output
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh-agent"],
            returncode=0,
            stdout="",
            stderr=""
        )
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

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        # Test environment variable source
        with patch.dict(os.environ, {"SSH_IDENTITY_FILE": str(key_file)}):
            assert _normalize_path(ssh_manager._get_identity_file("github.com")) == _normalize_path(str(key_file))

        # Test SSH config source
        config_file = ssh_dir / "config"
        config_file.write_text(f"""
Host github.com
    IdentityFile {key_file}
""")
        assert _normalize_path(ssh_manager._get_identity_file("github.com")) == _normalize_path(str(key_file))

        # Test fallback to available keys
        os.remove(config_file)
        pub_key = key_file.with_suffix(".pub")
        pub_key.write_text("test pub key")
        assert _normalize_path(ssh_manager._get_identity_file("github.com")) == _normalize_path(str(key_file))


def test_add_key_with_passphrase(ssh_manager):
    """Test adding SSH key with passphrase."""
    with patch.object(ssh_manager, "_create_ssh_add_process") as mock_create_process:
        # Mock process for successful key addition
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_create_process.return_value = mock_process

        assert ssh_manager._add_key_with_passphrase("test_key", "passphrase")

        # Test process failure
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error")
        assert not ssh_manager._add_key_with_passphrase("test_key", "passphrase")


def test_test_ssh_connection_scenarios(ssh_manager):
    """Test SSH connection testing with various scenarios."""
    with patch.object(ssh_manager, "run_command") as mock_run:
        # Test successful connection
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh", "-T", "-o", "StrictHostKeyChecking=no", "git@test_host"],
            returncode=1,  # Git servers often return 1 for successful auth
            stdout="Hi user! You've successfully authenticated",
            stderr=""
        )
        assert ssh_manager._test_ssh_connection("test_host")

        # Test connection failure with error code
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ssh", "-T", "-o", "StrictHostKeyChecking=no", "git@test_host"],
            returncode=255,  # SSH specific error code
            stdout="",
            stderr="Connection refused"
        )
        assert not ssh_manager._test_ssh_connection("test_host")

        # Test timeout error
        mock_run.return_value = None
        assert not ssh_manager._test_ssh_connection("test_host")


def test_setup_ssh_with_identity_file(ssh_manager):
    """Test SSH setup with identity file."""
    test_key = "/tmp/test_key"

    with patch.object(ssh_manager, "_start_ssh_agent") as mock_start, \
         patch.object(ssh_manager, "_test_ssh_connection") as mock_test, \
         patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, \
         patch("os.path.exists") as mock_exists:

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
    with patch.object(ssh_manager, "_create_ssh_add_process") as mock_create_process:
        # Test successful addition
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_create_process.return_value = mock_process

        success, needs_passphrase = ssh_manager._try_add_key_without_passphrase("test_key")
        assert success
        assert not needs_passphrase

        # Test key requires passphrase
        mock_process = MagicMock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = (b"", b"Enter passphrase")
        mock_process.returncode = 1
        mock_create_process.return_value = mock_process

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
    with patch("os.path.exists") as mock_exists, \
         patch("builtins.open", mock_open()) as mock_file, \
         patch("json.dump") as mock_dump:

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
    with patch.object(ssh_manager, "run_command") as mock_run:
        # Test key verification failure
        mock_run.return_value = None
        assert not ssh_manager._verify_loaded_key("test_key")

        # Test start ssh agent with command failure
        mock_run.side_effect = [None, None]
        assert not ssh_manager._start_ssh_agent("test_key")

        # Test add key with invalid process
        mock_run.side_effect = None
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"", stderr=b"Invalid key"
        )
        assert not ssh_manager._add_ssh_key("test_key")


def test_ssh_config_parsing_edge_cases(ssh_manager):
    """Test edge cases in SSH config parsing."""
    with patch("builtins.open", mock_open(read_data="""
Host test
    HostName test.example.com
    User testuser
    Port 2222
    IdentityFile ~/.ssh/invalid_key
Host *
    IdentityFile ~/.ssh/default_key
""")):
        config = ssh_manager._parse_ssh_config()
        assert "test" in config
        assert config["test"]["hostname"] == "test.example.com"
        assert config["test"]["user"] == "testuser"
        assert config["test"]["port"] == "2222"
        assert "~/.ssh/invalid_key" in config["test"]["identityfile"]
        assert "*" in config
        assert "identityfile" in config["*"]
        assert "~/.ssh/default_key" in config["*"]["identityfile"]


def test_identity_file_resolution(ssh_manager):
    """Test identity file resolution."""
    with patch("os.path.expanduser") as mock_expand, \
         patch("os.path.abspath") as mock_abspath, \
         patch("os.path.exists") as mock_exists:

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
    with patch.object(ssh_manager, "run_command") as mock_run, \
         patch("os.path.exists") as mock_exists, \
         patch("glob.glob") as mock_glob:
        # Mock ssh-add -l output
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"""2048 SHA256:abc123 /home/user/.ssh/id_rsa (RSA)
2048 SHA256:def456 /home/user/.ssh/id_rsa2 (RSA)""",
            stderr=b""
        )

        # Mock file existence checks
        def exists_side_effect(path):
            path_str = str(path).replace("\\", "/")  # Normalize path for comparison
            valid_paths = [
                "/home/user/.ssh/id_rsa",
                "/home/user/.ssh/id_rsa.pub",
                "/home/user/.ssh/id_rsa2",
                "/home/user/.ssh/id_rsa2.pub"
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

        # Mock the _ssh_dir property
        with patch.object(ssh_manager, "_ssh_dir", Path("/home/user/.ssh")):
            # Test getting available keys
            keys = ssh_manager._get_available_keys()
            assert len(keys) == 2
            assert "/home/user/.ssh/id_rsa" in keys
            assert "/home/user/.ssh/id_rsa2" in keys


def test_ssh_agent_info_handling(ssh_manager):
    """Test SSH agent info handling."""
    with patch("builtins.open", mock_open()), \
         patch("json.load") as mock_load, \
         patch("os.path.exists") as mock_exists, \
         patch.object(ssh_manager, "run_command") as mock_run:

        # Set up mocks for successful load
        mock_exists.return_value = True
        mock_load.return_value = {
            "timestamp": time.time(),
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid",
            "platform": os.name
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"", stderr=b""
        )

        # Test loading agent info
        assert ssh_manager._load_agent_info()

        # Verify environment variables
        assert os.environ.get("SSH_AUTH_SOCK") == "test_sock"
        assert os.environ.get("SSH_AGENT_PID") == "test_pid"


def test_ssh_connection_handling(ssh_manager):
    """Test SSH connection handling."""
    with patch.object(ssh_manager, "run_command") as mock_run, \
         patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, \
         patch("os.path.exists") as mock_exists, \
         patch.object(ssh_manager, "_start_ssh_agent") as mock_start_agent:

        mock_get_identity.return_value = "/path/to/key"
        mock_exists.return_value = True
        mock_start_agent.return_value = True

        # Test successful connection (returncode=1 is success for Git servers)
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"", stderr=b""
        )
        assert ssh_manager._test_ssh_connection("test.example.com")

        # Test failed connection
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=255, stdout=b"", stderr=b"Connection refused"
        )
        assert not ssh_manager._test_ssh_connection("test.example.com")

        # Test connection timeout
        mock_run.return_value = None
        assert not ssh_manager._test_ssh_connection("test.example.com")


def test_git_ssh_command_generation(ssh_manager):
    """Test Git SSH command generation."""
    with patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, \
         patch("os.path.exists") as mock_exists, \
         patch.object(ssh_manager, "_start_ssh_agent") as mock_start_agent, \
         patch.object(ssh_manager, "_test_ssh_connection") as mock_test_connection:

        # Test with valid identity file
        mock_get_identity.return_value = "/path/to/key"
        mock_exists.return_value = True
        mock_start_agent.return_value = True
        mock_test_connection.return_value = True

        cmd = ssh_manager.get_git_ssh_command("github.com")
        assert "ssh" in cmd
        assert "-i" in cmd
        assert "/path/to/key" in cmd

        # Test with invalid identity file
        mock_get_identity.return_value = None
        assert ssh_manager.get_git_ssh_command("github.com") is None


def test_ssh_setup_with_custom_config(ssh_manager):
    """Test SSH setup with custom configuration."""
    with patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, \
         patch.object(ssh_manager, "_start_ssh_agent") as mock_start_agent, \
         patch.object(ssh_manager, "_test_ssh_connection") as mock_test_connection, \
         patch("os.path.exists") as mock_exists:

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
    with patch.object(ssh_manager, "run_command") as mock_run, \
         patch("os.environ") as mock_environ:

        # Test agent start command failure
        mock_run.return_value = None
        mock_environ.copy.return_value = {}
        assert not ssh_manager._start_ssh_agent("test_key")

        # Test agent environment variable setting failure
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=b"SSH_AUTH_SOCK=/tmp/ssh-XXX/agent.123; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;\n",
            stderr=b""
        )
        mock_environ.__setitem__.side_effect = Exception("Mock environ error")
        assert not ssh_manager._start_ssh_agent("test_key")


def test_file_operation_errors(ssh_manager):
    """Test file operation error scenarios."""
    with patch("builtins.open") as mock_open, \
         patch("os.path.exists") as mock_exists:

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
    with patch("builtins.open", mock_open(read_data="""
Host test
    Invalid Option
    IdentityFile
    Port abc
""")):
        config = ssh_manager._parse_ssh_config()
        assert "test" in config
        assert "identityfile" not in config["test"]
        assert "port" not in config["test"]


def test_ssh_key_management_failures(ssh_manager):
    """Test SSH key management failure scenarios."""
    with patch.object(ssh_manager, "run_command") as mock_run, \
         patch("os.path.exists") as mock_exists, \
         patch("builtins.open", mock_open(read_data="test key data")):

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
    with patch.object(ssh_manager, "run_command") as mock_run, \
         patch.object(ssh_manager, "_get_identity_file") as mock_get_identity:

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
    with patch.object(ssh_manager, "_get_identity_file") as mock_get_identity, \
         patch("os.path.exists") as mock_exists:

        # Test with missing identity file
        mock_get_identity.return_value = None
        assert ssh_manager.get_git_ssh_command("github.com") is None

        # Test with non-existent identity file
        mock_get_identity.return_value = "test_key"
        mock_exists.return_value = False
        assert ssh_manager.get_git_ssh_command("github.com") is None

        # Test with invalid hostname
        mock_exists.return_value = True
        assert ssh_manager.get_git_ssh_command("invalid@host") is None


def test_error_handling_edge_cases(ssh_manager):
    """Test error handling edge cases."""
    # Import built-in modules
    import time
    with patch.object(ssh_manager, "run_command") as mock_run, \
         patch("builtins.open", mock_open()) as mock_file, \
         patch("os.path.exists") as mock_exists, \
         patch("json.load") as mock_load:

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
            "platform": "wrong_platform"  # Use wrong platform to trigger error
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"", stderr=b""
        )
        with patch.dict(os.environ, {}, clear=True):
            assert not ssh_manager._load_agent_info()


def test_ssh_config_advanced_parsing(ssh_manager):
    """Test advanced SSH config parsing scenarios."""
    with patch("builtins.open", mock_open(read_data="""
Host *
    IdentityFile ~/.ssh/default_key
    Port 22

Host test1
    HostName test1.example.com
    User testuser
    IdentityFile ~/.ssh/test1_key
    Port invalid_port

Host test2
    HostName test2.example.com
    IdentityFile
    Port
    User
""")):
        config = ssh_manager._parse_ssh_config()
        assert "*" in config
        assert "test1" in config
        assert "test2" in config

        # Check default values
        assert config["*"]["port"] == "22"
        assert "~/.ssh/default_key" in config["*"]["identityfile"]

        # Check override values
        assert config["test1"]["hostname"] == "test1.example.com"
        assert config["test1"]["user"] == "testuser"
        assert "~/.ssh/test1_key" in config["test1"]["identityfile"]
        assert "port" not in config["test1"]  # Invalid port should be ignored

        # Check empty values
        assert "hostname" in config["test2"]
        assert "identityfile" not in config["test2"]
        assert "port" not in config["test2"]
        assert "user" not in config["test2"]


def test_url_hostname_extraction(ssh_manager):
    """Test hostname extraction from URLs."""
    # Test valid SSH URLs
    assert ssh_manager._extract_hostname("git@github.com:user/repo.git") == "github.com"
    assert ssh_manager._extract_hostname("git@example.com:8080/repo.git") == "example.com"

    # Test invalid URLs
    assert ssh_manager._extract_hostname("invalid_url") is None
    assert ssh_manager._extract_hostname("git@") is None
    assert ssh_manager._extract_hostname("") is None


def test_hostname_validation(ssh_manager):
    """Test hostname validation logic."""
    # Test valid hostnames
    assert ssh_manager.is_valid_hostname("example.com")
    assert ssh_manager.is_valid_hostname("sub.example.com")
    assert ssh_manager.is_valid_hostname("example-1.com")

    # Test invalid hostnames
    assert not ssh_manager.is_valid_hostname("")
    assert not ssh_manager.is_valid_hostname("a" * 256)  # Too long
    assert not ssh_manager.is_valid_hostname("-example.com")  # Starts with hyphen
    assert not ssh_manager.is_valid_hostname("example-.com")  # Ends with hyphen
    assert not ssh_manager.is_valid_hostname("exam@ple.com")  # Invalid character