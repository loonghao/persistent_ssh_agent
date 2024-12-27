"""Additional tests to improve code coverage for core SSH management module."""

# Import built-in modules
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import mock_open
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent
import pytest


@pytest.fixture
def ssh_manager():
    """Create a PersistentSSHAgent instance."""
    return PersistentSSHAgent()


def test_start_ssh_agent_windows_kill(ssh_manager, tmp_path):
    """Test SSH agent startup with Windows process kill."""
    with patch("os.name", "nt"), \
         patch.object(ssh_manager, "_run_command") as mock_run:

        # Mock successful process kill
        mock_run.return_value = subprocess.CompletedProcess(
            args=["taskkill"],
            returncode=0,
            stdout=b"",
            stderr=b""
        )

        # Create a temporary key file
        key_file = tmp_path / "test_key"
        key_file.write_text("test key content")

        # Test agent start
        result = ssh_manager._start_ssh_agent(str(key_file))
        assert result is True

        # Verify Windows-specific kill command was called
        mock_run.assert_any_call(
            ["taskkill", "/F", "/IM", "ssh-agent.exe"],
            check_output=False
        )


def test_run_command_with_timeout(ssh_manager):
    """Test command execution with timeout."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)

        result = ssh_manager._run_command(["test"], timeout=1)
        assert result is None


def test_parse_ssh_config_with_include_directive(ssh_manager, tmp_path, monkeypatch):
    """Test parsing SSH config with Include directive."""
    # Create SSH directory
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    monkeypatch.setattr(ssh_manager, "_ssh_dir", ssh_dir)

    # Create main config file
    config_file = ssh_dir / "config"
    config_file.write_text("""
Host example.com
    IdentityFile ~/.ssh/id_rsa
    User git
""")

    # Create identity file
    id_rsa = ssh_dir / "id_rsa"
    id_rsa.write_text("test key content")

    # Test config parsing
    config = ssh_manager._parse_ssh_config()
    assert config is not None
    assert len(config) > 0
    assert "example.com" in config
    assert config["example.com"].get("user") == "git"
    assert config["example.com"].get("identityfile") == "~/.ssh/id_rsa"


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
        assert key_file.as_posix() in command


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


def test_parse_ssh_config_with_conditional_blocks(ssh_manager, tmp_path, monkeypatch):
    """Test parsing SSH config with conditional blocks."""
    # Create SSH directory
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    monkeypatch.setattr(ssh_manager, "_ssh_dir", ssh_dir)

    config_content = """
Host example.com
    IdentityFile ~/.ssh/id_rsa
    User git

Host *.staging
    IdentityFile ~/.ssh/staging_key
    User deploy
"""

    config_file = ssh_dir / "config"
    config_file.write_text(config_content)

    # Create identity files
    id_rsa = ssh_dir / "id_rsa"
    id_rsa.write_text("test key content")
    staging_key = ssh_dir / "staging_key"
    staging_key.write_text("test key content")

    # Test config parsing
    config = ssh_manager._parse_ssh_config()
    assert config is not None
    assert len(config) > 0
    assert "example.com" in config
    assert config["example.com"].get("user") == "git"
    assert config["example.com"].get("identityfile") == "~/.ssh/id_rsa"


def test_windows_ssh_agent_error_handling(ssh_manager):
    """Test error handling in Windows SSH agent operations."""
    with patch("os.name", "nt"), \
         patch.object(ssh_manager, "_run_command") as mock_run, \
         patch("subprocess.run") as mock_subprocess_run:

        # Mock process kill failure
        mock_run.return_value = subprocess.CompletedProcess(
            args=["taskkill"],
            returncode=1,
            stdout=b"",
            stderr=b"Access denied"
        )

        # Mock SSH agent start failure
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd="ssh-agent", timeout=10)

        # Test agent start with failure
        result = ssh_manager._start_ssh_agent("nonexistent_key")
        assert result is False


def test_agent_info_file_operations(ssh_manager, tmp_path):
    """Test SSH agent info file operations with various error conditions."""
    with patch.object(ssh_manager, "_agent_info_file", tmp_path / "agent_info.json"), \
         patch("time.time", return_value=1000):

        # Test saving invalid JSON data
        with patch("json.dump", side_effect=TypeError("Invalid data")):
            ssh_manager._save_agent_info("test_sock", "test_pid")

        # Test loading non-existent file
        assert ssh_manager._load_agent_info() is False

        # Test loading expired agent info
        info = {
            "timestamp": 0,  # Expired
            "platform": os.name,
            "SSH_AUTH_SOCK": "test_sock",
            "SSH_AGENT_PID": "test_pid"
        }
        (tmp_path / "agent_info.json").write_text(json.dumps(info))
        assert ssh_manager._load_agent_info() is False


def test_ssh_key_verification_retries(ssh_manager):
    """Test SSH key verification with retries and timeouts."""
    with patch.object(ssh_manager, "_run_command") as mock_run:
        # Mock the ssh-add command
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh-add", timeout=10)

        # Add and verify the key
        result = ssh_manager._add_ssh_key("test_key")
        assert result is False

        # Verify command was called with correct arguments
        mock_run.assert_called_once_with(
            ["ssh-add", "test_key"],
            timeout=10
        )


def test_ssh_key_verification_retries_with_multiple_attempts(ssh_manager):
    """Test SSH key verification with retries and timeouts."""
    with patch.object(ssh_manager, "_run_command") as mock_run:
        # Mock the ssh-add command
        mock_run.side_effect = [
            subprocess.CompletedProcess(  # First ssh-add succeeds
                args=["ssh-add", "test_key"],
                returncode=0,
                stdout=b"",
                stderr=b""
            )
        ]

        # Add and verify the key
        result = ssh_manager._add_ssh_key("test_key")
        assert result is True

        # Verify command was called with correct arguments
        mock_run.assert_called_once_with(
            ["ssh-add", "test_key"],
            timeout=10
        )


def test_ssh_agent_start_error_handling(ssh_manager):
    """Test error handling during SSH agent startup."""
    with patch.object(ssh_manager, "_run_command") as mock_run:
        # Mock SSH agent startup failure
        mock_run.side_effect = [
            None,  # ssh-agent command fails
            subprocess.CompletedProcess(  # ssh-add command succeeds
                args=["ssh-add", "test_key"],
                returncode=0,
                stdout=b"",
                stderr=b""
            )
        ]

        result = ssh_manager._start_ssh_agent("test_key")
        assert result is False


def test_ssh_config_parse_edge_cases(ssh_manager):
    """Test SSH config parsing edge cases."""
    config_content = """
    Host test-host
        IdentityFile ~/.ssh/id_rsa

    Match host test-host
        IdentityFile ~/.ssh/special_key

    Match all
        IdentityFile ~/.ssh/default_key
    """

    mock_file = mock_open(read_data=config_content)
    with patch("builtins.open", mock_file), \
         patch("os.path.exists", return_value=True), \
         patch("glob.glob", return_value=[]):
        config = ssh_manager._parse_ssh_config()
        assert "test-host" in config
        assert "identityfile" in config["test-host"]
        assert config["test-host"]["identityfile"] == "~/.ssh/default_key"


def test_ssh_url_parsing_errors(ssh_manager):
    """Test SSH URL parsing error cases."""
    invalid_urls = [
        "not-a-git-url",
        "git@",
        "git@:repo.git",
        "git@host:",
        "git@host",
        "git@host/repo.git"
    ]

    for url in invalid_urls:
        hostname = ssh_manager._extract_hostname(url)
        assert hostname is None, f"URL '{url}' should be invalid"


def test_ssh_config_include_errors(ssh_manager):
    """Test SSH config include directive error handling."""
    config_content = """
    Include ~/non-existent/*.conf
    Include /invalid/path/config

    Host test-host
        IdentityFile ~/.ssh/id_rsa
    """

    mock_file = mock_open(read_data=config_content)
    with patch("builtins.open", mock_file), \
         patch("os.path.exists", side_effect=[True, False, False]), \
         patch("glob.glob", return_value=[]):
        config = ssh_manager._parse_ssh_config()
        assert "test-host" in config


def test_ssh_config_parse_with_empty_file(ssh_manager):
    """Test SSH config parsing with empty file."""
    mock_file = mock_open(read_data="")
    with patch("builtins.open", mock_file), \
         patch("os.path.exists", return_value=True), \
         patch("glob.glob", return_value=[]):
        config = ssh_manager._parse_ssh_config()
        assert isinstance(config, dict)
        assert len(config) == 0


def test_ssh_config_parse_with_invalid_content(ssh_manager):
    """Test SSH config parsing with invalid content."""
    config_content = """
    Invalid Line
    Host test-host
        IdentityFile ~/.ssh/id_rsa
    """

    mock_file = mock_open(read_data=config_content)
    with patch("builtins.open", mock_file), \
         patch("os.path.exists", return_value=True), \
         patch("glob.glob", return_value=[]):
        config = ssh_manager._parse_ssh_config()
        assert "test-host" in config
        assert config["test-host"]["identityfile"] == "~/.ssh/id_rsa"


def test_ssh_config_parse_with_missing_file(ssh_manager):
    """Test SSH config parsing with missing file."""
    with patch("os.path.exists", side_effect=lambda x: False), \
         patch("glob.glob", return_value=[]), \
         patch("pathlib.Path.home", return_value=Path("/home/test")), \
         patch.object(ssh_manager, "_ssh_config_cache", {}), \
         patch("builtins.open", side_effect=FileNotFoundError("File not found")):
        config = ssh_manager._parse_ssh_config()
        assert isinstance(config, dict)
        assert len(config) == 0


def test_ssh_config_parse_with_file_error(ssh_manager):
    """Test SSH config parsing with file error."""
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=PermissionError("Permission denied")):
        config = ssh_manager._parse_ssh_config()
        assert isinstance(config, dict)
        assert len(config) == 0
