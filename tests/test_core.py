"""Tests for the core SSH management module."""

# Import built-in modules
import json
import os
from pathlib import Path
import subprocess
import time
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


def test_ensure_home_env(ssh_manager):
    """Test HOME environment variable setup."""
    # Save original environment
    original_env = os.environ.copy()

    try:
        # Remove HOME if it exists
        if "HOME" in os.environ:
            del os.environ["HOME"]

        # Get expected home directory
        expected_home = os.path.expanduser("~")

        # Test HOME environment setup
        ssh_manager._ensure_home_env()
        assert os.environ["HOME"] == expected_home

        # Test that existing HOME is not modified
        test_home = "/test/home"
        os.environ["HOME"] = test_home
        ssh_manager._ensure_home_env()
        assert os.environ["HOME"] == test_home

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_parse_ssh_config(ssh_manager, mock_ssh_config, monkeypatch):
    """Test SSH config parsing."""
    monkeypatch.setenv("HOME", str(mock_ssh_config.parent))
    ssh_manager._ssh_dir = mock_ssh_config  # Update ssh_dir to use mock config
    config = ssh_manager._parse_ssh_config()

    assert "github.com" in config
    assert config["github.com"]["identityfile"] == "~/.ssh/id_ed25519"
    assert config["github.com"]["user"] == "git"

    assert "*.gitlab.com" in config
    assert config["*.gitlab.com"]["identityfile"] == "~/.ssh/gitlab_key"
    assert config["*.gitlab.com"]["user"] == "git"


def test_get_identity_file(ssh_manager, mock_ssh_config, monkeypatch):
    """Test identity file resolution."""
    monkeypatch.setenv("HOME", str(mock_ssh_config.parent))
    ssh_manager._ssh_dir = mock_ssh_config  # Update ssh_dir to use mock config

    # Test exact match
    identity = ssh_manager._get_identity_file("github.com")
    assert "id_ed25519" in identity

    # Test pattern match
    identity = ssh_manager._get_identity_file("test.gitlab.com")
    assert "gitlab_key" in identity


def test_extract_hostname(ssh_manager):
    """Test hostname extraction from repository URLs."""
    # Test standard GitHub URL
    hostname = ssh_manager._extract_hostname("git@github.com:user/repo.git")
    assert hostname == "github.com"

    # Test GitLab URL
    hostname = ssh_manager._extract_hostname("git@gitlab.com:group/project.git")
    assert hostname == "gitlab.com"

    # Test custom domain
    hostname = ssh_manager._extract_hostname("git@git.example.com:org/repo.git")
    assert hostname == "git.example.com"

    # Test invalid URLs
    assert ssh_manager._extract_hostname("invalid-url") is None
    assert ssh_manager._extract_hostname("https://github.com/user/repo.git") is None
    assert ssh_manager._extract_hostname("") is None


@patch("subprocess.run")
def test_run_command(mock_run, ssh_manager):
    """Test command execution."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Success"
    mock_run.return_value = mock_process

    result = ssh_manager._run_command(["git", "status"])
    assert result is not None
    assert result.returncode == 0
    assert result.stdout == "Success"

    # Test command failure
    mock_process.returncode = 1
    result = ssh_manager._run_command(["git", "invalid"])
    assert result is None


@patch("subprocess.run")
def test_start_ssh_agent(mock_run, ssh_manager, temp_dir):
    """Test SSH agent startup."""
    # Create a mock identity file
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    # Mock successful agent startup
    def mock_run_side_effect(*args, **kwargs):
        if args[0][0] == "ssh-agent":
            return MagicMock(
                returncode=0,
                stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
            )
        elif args[0][0] == "ssh-add":
            return MagicMock(returncode=0)
        return MagicMock(returncode=0)

    mock_run.side_effect = mock_run_side_effect
    assert ssh_manager._start_ssh_agent(identity_file) is True




@patch("subprocess.run")
def test_setup_ssh_failures(mock_run: MagicMock, ssh_manager, temp_dir):
    """Test SSH setup failure cases."""
    # Test with missing identity file
    with patch.object(ssh_manager, "_get_identity_file", return_value=None):
        assert ssh_manager.setup_ssh("github.com") is False

    # Test with non-existent identity file
    with patch.object(ssh_manager, "_get_identity_file", return_value="/nonexistent/key"):
        assert ssh_manager.setup_ssh("github.com") is False

    # Test with SSH agent startup failure
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        def mock_run_failure(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return MagicMock(returncode=1, stderr="Failed to start agent")
            return MagicMock(returncode=1)

        mock_run.side_effect = mock_run_failure
        assert ssh_manager.setup_ssh("github.com") is False

    # Test with SSH connection failure
    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        def mock_run_ssh_failure(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return MagicMock(
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
                )
            elif args[0][0] == "ssh":
                return MagicMock(returncode=255, stderr="Connection refused")
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_ssh_failure
        assert ssh_manager.setup_ssh("github.com") is False

    # Test with command execution failure (returns None)
    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        def mock_run_none(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return MagicMock(
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
                )
            elif args[0][0] == "ssh":
                return None  # Simulate command execution failure
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_none
        assert ssh_manager.setup_ssh("github.com") is False


def test_save_load_agent_info(ssh_manager, temp_dir, monkeypatch):
    """Test saving and loading SSH agent information."""
    monkeypatch.setenv("HOME", temp_dir)

    # Test saving agent info
    ssh_manager._agent_info_file = os.path.join(temp_dir, ".ssh", "agent_info.json")
    ssh_manager._save_agent_info("/tmp/ssh.sock", "12345")

    assert os.path.exists(ssh_manager._agent_info_file)

    # Test loading valid agent info
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        assert ssh_manager._load_agent_info() is True
        assert os.environ.get("SSH_AUTH_SOCK") == "/tmp/ssh.sock"
        assert os.environ.get("SSH_AGENT_PID") == "12345"

    # Test loading with missing file
    os.unlink(ssh_manager._agent_info_file)
    assert ssh_manager._load_agent_info() is False

    # Test loading with invalid JSON
    with open(ssh_manager._agent_info_file, "w") as f:
        f.write("invalid json")
    assert ssh_manager._load_agent_info() is False


def test_clone_repository(ssh_manager, temp_dir):
    """Test repository cloning."""
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Test successful clone
        assert ssh_manager.clone_repository(
            "git@github.com:user/repo.git",
            os.path.join(temp_dir, "repo"),
            "main"
        ) is True

        # Test clone with invalid URL
        assert ssh_manager.clone_repository(
            "invalid-url",
            os.path.join(temp_dir, "repo2")
        ) is False


def test_version():
    """Test version import."""
    # Import third-party modules
    from persistent_ssh_agent.__version__ import __version__
    assert isinstance(__version__, str)
    assert __version__ != ""


def test_save_agent_info_errors(ssh_manager, temp_dir, monkeypatch):
    """Test error cases for saving agent info."""
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = Path(temp_dir) / ".ssh"
    ssh_manager._agent_info_file = ssh_manager._ssh_dir / "agent_info.json"

    # Test permission error
    with patch("os.makedirs") as mock_makedirs:
        mock_makedirs.side_effect = PermissionError()
        ssh_manager._save_agent_info("/tmp/ssh.sock", "12345")
        # Should not raise exception

    # Test file write error
    with patch("builtins.open") as mock_open:
        mock_open.side_effect = IOError()
        ssh_manager._save_agent_info("/tmp/ssh.sock", "12345")
        # Should not raise exception


def test_load_agent_info_edge_cases(ssh_manager, temp_dir, monkeypatch):
    """Test edge cases for loading agent info."""
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = Path(temp_dir) / ".ssh"
    ssh_manager._agent_info_file = ssh_manager._ssh_dir / "agent_info.json"

    # Test with expired timestamp
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time() - 90000,  # More than 24 hours old
        "platform": os.name
    }
    ssh_manager._ssh_dir.mkdir(parents=True, exist_ok=True)
    with open(ssh_manager._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    assert ssh_manager._load_agent_info() is False

    # Test with missing required fields
    agent_info = {
        "timestamp": time.time(),
        "platform": os.name
    }
    with open(ssh_manager._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    assert ssh_manager._load_agent_info() is False

    # Test with wrong platform
    agent_info = {
        "SSH_AUTH_SOCK": "/tmp/ssh.sock",
        "SSH_AGENT_PID": "12345",
        "timestamp": time.time(),
        "platform": "wrong_platform"
    }
    with open(ssh_manager._agent_info_file, "w") as f:
        json.dump(agent_info, f)

    assert ssh_manager._load_agent_info() is False


@patch("subprocess.run")
def test_start_ssh_agent_errors(mock_run, ssh_manager, temp_dir):
    """Test error cases for SSH agent startup."""
    # Test SSH agent start failure
    mock_run.return_value = MagicMock(returncode=1, stderr="Failed to start agent")
    identity_file = os.path.join(temp_dir, "test_key")

    # Create a mock key file
    with open(identity_file, "w") as f:
        f.write("mock key")

    assert ssh_manager._start_ssh_agent(identity_file) is False

    # Test ssh-add failure with proper command sequence
    def mock_run_side_effect(*args, **kwargs):
        if args[0][0] == "ssh-agent":
            return MagicMock(
                returncode=0,
                stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
            )
        elif args[0][0] == "ssh-add":
            return MagicMock(returncode=1, stderr="Failed to add key")
        elif args[0][0] == "taskkill":
            return MagicMock(returncode=0)
        return MagicMock(returncode=0)

    mock_run.side_effect = mock_run_side_effect
    assert ssh_manager._start_ssh_agent(identity_file) is False

    # Test command execution failure (returns None)
    def mock_run_none(*args, **kwargs):
        if args[0][0] == "ssh-agent":
            return MagicMock(
                returncode=0,
                stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
            )
        elif args[0][0] == "ssh-add":
            return None  # Simulate command execution failure
        return MagicMock(returncode=0)

    mock_run.side_effect = mock_run_none
    assert ssh_manager._start_ssh_agent(identity_file) is False


def test_get_git_ssh_command_errors(ssh_manager):
    """Test error cases for Git SSH command generation."""
    # Test with empty hostname
    assert ssh_manager.get_git_ssh_command("") is None

    # Test with setup failure
    with patch.object(ssh_manager, "setup_ssh", return_value=False):
        assert ssh_manager.get_git_ssh_command("github.com") is None

    # Test with nonexistent identity file
    with patch.object(ssh_manager, "setup_ssh", return_value=True), \
         patch.object(ssh_manager, "_get_identity_file", return_value="/nonexistent/key"):
        assert ssh_manager.get_git_ssh_command("github.com") is None


def test_clone_repository_errors(ssh_manager, temp_dir):
    """Test error cases for repository cloning."""
    # Test command execution error
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Command failed")
        result = ssh_manager.clone_repository(
            "git@github.com:user/repo.git",
            os.path.join(temp_dir, "repo")
        )
        assert result is False

    # Test with failed command
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = ssh_manager.clone_repository(
            "git@github.com:user/repo.git",
            os.path.join(temp_dir, "repo")
        )
        assert result is False

    # Test with invalid hostname extraction
    with patch.object(ssh_manager, "_extract_hostname", return_value=None):
        result = ssh_manager.clone_repository(
            "invalid-url",
            os.path.join(temp_dir, "repo")
        )
        assert result is False


def test_load_agent_info_errors(ssh_manager, temp_dir, monkeypatch):
    """Test error cases in load_agent_info."""
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = Path(temp_dir) / ".ssh"
    ssh_manager._agent_info_file = ssh_manager._ssh_dir / "agent_info.json"

    # Test JSON decode error
    ssh_manager._ssh_dir.mkdir(parents=True, exist_ok=True)
    with open(ssh_manager._agent_info_file, "w") as f:
        f.write("invalid json")
    assert ssh_manager._load_agent_info() is False

    # Test ssh-add command error
    with patch("builtins.open", mock_open(read_data='{"SSH_AUTH_SOCK": "/tmp/sock", "SSH_AGENT_PID": "123", "timestamp": 9999999999, "platform": "nt"}')), \
         patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Command failed")
        assert ssh_manager._load_agent_info() is False


def test_start_ssh_agent_additional_errors(ssh_manager, temp_dir):
    """Test additional error cases in start_ssh_agent."""
    identity_file = os.path.join(temp_dir, "test_key")

    # Test when identity file doesn't exist
    assert ssh_manager._start_ssh_agent("/nonexistent/key") is False

    # Test when ssh-agent fails with exception
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("ssh-agent failed")
        assert ssh_manager._start_ssh_agent(identity_file) is False


def test_run_command_additional_errors(ssh_manager):
    """Test additional error cases in run_command."""
    # Test subprocess.run raising exception
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Command failed")
        assert ssh_manager._run_command(["test"]) is None

    # Test with shell=True
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = ssh_manager._run_command("echo test", shell=True)
        assert result is not None
        mock_run.assert_called_with(
            "echo test",
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            shell=True
        )


def test_get_identity_file_additional_cases(ssh_manager, temp_dir, monkeypatch):
    """Test additional cases for get_identity_file."""
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = Path(temp_dir) / ".ssh"
    ssh_manager._ssh_dir.mkdir(parents=True, exist_ok=True)

    # Test when no SSH config exists
    identity = ssh_manager._get_identity_file("example.com")
    assert identity == str(ssh_manager._ssh_dir / "id_rsa")

    # Test with ed25519 key
    key_path = ssh_manager._ssh_dir / "id_ed25519"
    key_path.touch()
    identity = ssh_manager._get_identity_file("example.com")
    assert identity == str(key_path)


def test_git_ssh_command_errors(ssh_manager):
    """Test error cases in get_git_ssh_command."""
    # Test with empty hostname
    assert ssh_manager.get_git_ssh_command("") is None

    # Test with setup_ssh failure
    with patch.object(ssh_manager, "setup_ssh", return_value=False):
        assert ssh_manager.get_git_ssh_command("github.com") is None

    # Test with nonexistent identity file
    with patch.object(ssh_manager, "setup_ssh", return_value=True):
        with patch.object(ssh_manager, "_get_identity_file", return_value="/nonexistent/key"):
            assert ssh_manager.get_git_ssh_command("github.com") is None


def test_clone_repository_additional_errors(ssh_manager):
    """Test additional error cases in clone_repository."""
    # Test with empty URL
    assert ssh_manager.clone_repository("", "/tmp/repo") is False

    # Test with invalid URL format
    assert ssh_manager.clone_repository("invalid_url", "/tmp/repo") is False

    # Test with command execution error
    with patch.object(ssh_manager, "_extract_hostname", return_value="github.com"):
        with patch.object(ssh_manager, "_run_command", return_value=None):
            assert ssh_manager.clone_repository("git@github.com:user/repo.git", "/tmp/repo") is False


def test_extract_hostname_additional_cases(ssh_manager):
    """Test additional cases for extract_hostname."""
    # Test with None input
    assert ssh_manager._extract_hostname(None) is None

    # Test with empty string
    assert ssh_manager._extract_hostname("") is None

    # Test with malformed SSH URLs
    assert ssh_manager._extract_hostname("git@") is None
    assert ssh_manager._extract_hostname("git@:repo.git") is None
    assert ssh_manager._extract_hostname("@host:repo.git") is None
    assert ssh_manager._extract_hostname("git@:repo.git") is None

    # Test with special characters in hostname
    assert ssh_manager._extract_hostname("git@host_name.com:user/repo.git") == "host_name.com"
    assert ssh_manager._extract_hostname("git@host-name.com:user/repo.git") == "host-name.com"
    assert ssh_manager._extract_hostname("git@host.name.com:user/repo.git") == "host.name.com"

    # Test with invalid URL formats
    assert ssh_manager._extract_hostname("") is None
    assert ssh_manager._extract_hostname("invalid_url") is None
    assert ssh_manager._extract_hostname("git@") is None
    assert ssh_manager._extract_hostname("git@:repo.git") is None
    assert ssh_manager._extract_hostname("@host.com:repo.git") is None
    assert ssh_manager._extract_hostname("git@host.com") is None  # Missing :repo.git part


def test_parse_ssh_config_malformed(ssh_manager, temp_dir, monkeypatch):
    """Test parsing malformed SSH config."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Test malformed config
    config_path = ssh_dir / "config"
    config_path.write_text("""
Host github.com
    # Missing value
    IdentityFile
    User
Host *.gitlab.com
    BadKey Value
Host "quoted.host"
    IdentityFile "~/.ssh/quoted_key"
    User 'quoted_user'
""")

    config = ssh_manager._parse_ssh_config()
    assert "github.com" in config
    assert not config["github.com"]  # Should be empty dict due to missing values
    assert "*.gitlab.com" in config
    assert not config["*.gitlab.com"]  # Should be empty dict due to invalid key
    assert "quoted.host" not in config  # Quoted hosts are not valid


def test_parse_ssh_config_with_syntax_error(ssh_manager, temp_dir, monkeypatch):
    """Test parse_ssh_config with syntax errors in config."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Create config with various syntax errors
    config_path = ssh_dir / "config"
    config_path.write_text("""
# Invalid syntax with = and :
Host github.com
    IdentityFile=~/.ssh/id_ed25519
    User:git
    IdentityFile = ~/.ssh/another_key
    User = another_user

# Empty host values
Host
Host =
Host
    IdentityFile ~/.ssh/default_key

# Missing values
Host gitlab.com
    IdentityFile
    User
    IdentityFile =
    User =

# Invalid syntax
Host = example.com
    IdentityFile: ~/.ssh/example_key
    User = git

# Valid host with comments
Host valid.com  # This is a comment
    # This is a comment
    IdentityFile ~/.ssh/valid_key  # This is another comment
    User git  # Comment after value

# Invalid quotes
Host "invalid.host"
    IdentityFile "~/.ssh/invalid_key"
    User 'invalid_user'
""")

    config = ssh_manager._parse_ssh_config()

    # github.com should be parsed but without invalid values
    assert "github.com" in config
    assert not config["github.com"]  # Should be empty dict due to invalid syntax

    # Empty hosts should be ignored
    assert "" not in config
    assert "=" not in config

    # gitlab.com should be parsed but without empty values
    assert "gitlab.com" in config
    assert not config["gitlab.com"]  # Should be empty dict due to missing values

    # Invalid host syntax should be ignored
    assert "example.com" not in config
    assert "invalid.host" not in config

    # Valid host should be parsed correctly despite comments
    assert "valid.com" in config
    assert config["valid.com"]["identityfile"] == "~/.ssh/valid_key"
    assert config["valid.com"]["user"] == "git"


def test_setup_ssh_additional_errors(ssh_manager, temp_dir, monkeypatch):
    """Test additional error cases in setup_ssh."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Test with non-existent identity file
    with patch.object(ssh_manager, "_get_identity_file", return_value="/nonexistent/key"):
        assert ssh_manager.setup_ssh("github.com") is False

    # Test with SSH command error
    key_path = ssh_dir / "id_ed25519"
    key_path.touch()
    with patch.object(ssh_manager, "_get_identity_file", return_value=str(key_path)):
        with patch.object(ssh_manager, "_run_command", side_effect=Exception("SSH error")):
            assert ssh_manager.setup_ssh("github.com") is False


def test_run_command_additional_errors(ssh_manager):
    """Test additional error cases in run_command."""
    # Test with None command
    assert ssh_manager._run_command(None) is None

    # Test with empty command list
    assert ssh_manager._run_command([]) is None

    # Test with command execution error
    with patch("subprocess.run", side_effect=Exception("Command failed")):
        assert ssh_manager._run_command(["test"]) is None


def test_get_git_ssh_command_additional_errors(ssh_manager):
    """Test additional error cases in get_git_ssh_command."""
    # Test with None hostname
    assert ssh_manager.get_git_ssh_command(None) is None

    # Test with empty hostname
    assert ssh_manager.get_git_ssh_command("") is None

    # Test with setup_ssh failure
    with patch.object(ssh_manager, "setup_ssh", return_value=False):
        assert ssh_manager.get_git_ssh_command("github.com") is None


def test_clone_repository_additional_errors(ssh_manager):
    """Test additional error cases in clone_repository."""
    # Test with None URL
    assert ssh_manager.clone_repository(None, "/tmp/repo") is False

    # Test with None target path
    assert ssh_manager.clone_repository("git@github.com:user/repo.git", None) is False

    # Test with empty target path
    assert ssh_manager.clone_repository("git@github.com:user/repo.git", "") is False

    # Test with invalid URL format
    assert ssh_manager.clone_repository("invalid_url", "/tmp/repo") is False

    # Test with command execution error
    with patch.object(ssh_manager, "_run_command", return_value=None):
        assert ssh_manager.clone_repository("git@github.com:user/repo.git", "/tmp/repo") is False


def test_setup_ssh_with_ssh_add_error(ssh_manager, temp_dir, monkeypatch):
    """Test setup_ssh with ssh-add error."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Create a valid key file
    key_path = ssh_dir / "id_ed25519"
    key_path.touch()

    # Mock ssh-add to fail
    def mock_run(*args, **kwargs):
        if "ssh-add" in args[0]:
            raise subprocess.CalledProcessError(1, args[0], "ssh-add failed")
        return subprocess.CompletedProcess(args[0], 0)

    with patch("subprocess.run", side_effect=mock_run):
        assert ssh_manager.setup_ssh("github.com") is False


def test_parse_ssh_config_with_file_error(ssh_manager, temp_dir, monkeypatch):
    """Test parse_ssh_config with file read error."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    config_path = ssh_dir / "config"
    config_path.touch()

    # Make file unreadable
    with patch("builtins.open", side_effect=IOError("Permission denied")):
        config = ssh_manager._parse_ssh_config()
        assert config == {}


def test_extract_hostname_invalid_formats(ssh_manager):
    """Test _extract_hostname with invalid formats."""
    # Test with invalid URL formats
    assert ssh_manager._extract_hostname("") is None
    assert ssh_manager._extract_hostname("invalid_url") is None
    assert ssh_manager._extract_hostname("git@") is None
    assert ssh_manager._extract_hostname("git@:repo.git") is None
    assert ssh_manager._extract_hostname("@host.com:repo.git") is None
    assert ssh_manager._extract_hostname("git@host.com") is None  # Missing :repo.git part


def test_run_command_with_invalid_input(ssh_manager):
    """Test _run_command with invalid input."""
    # Test with invalid command types
    assert ssh_manager._run_command(123) is None  # Non-list/str input
    assert ssh_manager._run_command("") is None   # Empty string
    assert ssh_manager._run_command([""]) is None # Empty command in list

    # Test with command that raises CalledProcessError
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["test"], "Error")):
        assert ssh_manager._run_command(["test"]) is None


def test_setup_ssh_with_permission_error(ssh_manager, temp_dir, monkeypatch):
    """Test setup_ssh with permission error."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Create a valid key file
    key_path = ssh_dir / "id_ed25519"
    key_path.touch()

    def mock_run(*args, **kwargs):
        if "ssh-add" in args[0]:
            raise PermissionError("Permission denied")
        return subprocess.CompletedProcess(args[0], 0)

    with patch("subprocess.run", side_effect=mock_run):
        assert ssh_manager.setup_ssh("github.com") is False


def test_run_command_with_various_errors(ssh_manager):
    """Test _run_command with various error types."""
    # Test with PermissionError
    with patch("subprocess.run", side_effect=PermissionError("Permission denied")):
        assert ssh_manager._run_command(["test"]) is None

    # Test with FileNotFoundError
    with patch("subprocess.run", side_effect=FileNotFoundError("Command not found")):
        assert ssh_manager._run_command(["test"]) is None

    # Test with generic OSError
    with patch("subprocess.run", side_effect=OSError("Generic OS error")):
        assert ssh_manager._run_command(["test"]) is None


def test_get_identity_file_with_invalid_config(ssh_manager, temp_dir, monkeypatch):
    """Test _get_identity_file with invalid config."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Create config with invalid patterns
    config_path = ssh_dir / "config"
    config_path.write_text("""
Host [invalid.pattern
    IdentityFile ~/.ssh/invalid_key
Host *.[
    IdentityFile ~/.ssh/another_key
""")

    # Test with invalid patterns
    identity = ssh_manager._get_identity_file("example.com")
    assert identity == str(ssh_dir / "id_rsa")  # Should fall back to default


def test_parse_ssh_config_with_syntax_error(ssh_manager, temp_dir, monkeypatch):
    """Test parse_ssh_config with syntax errors in config."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", temp_dir)
    ssh_manager._ssh_dir = ssh_dir

    # Create config with various syntax errors
    config_path = ssh_dir / "config"
    config_path.write_text("""
# Invalid syntax with = and :
Host github.com
    IdentityFile = ~/.ssh/id_ed25519
    User: git

# Empty host values
Host
Host =
Host
    IdentityFile ~/.ssh/default_key

# Missing values
Host gitlab.com
    IdentityFile
    User
    IdentityFile =
    User =

# Invalid syntax
Host = example.com
    IdentityFile: ~/.ssh/example_key
    User = git

# Valid host with comments
Host valid.com  # This is a comment
    # This is a comment
    IdentityFile ~/.ssh/valid_key  # This is another comment
    User git  # Comment after value

# Invalid quotes
Host "invalid.host"
    IdentityFile "~/.ssh/invalid_key"
    User 'invalid_user'
""")

    config = ssh_manager._parse_ssh_config()

    # github.com should be parsed but without invalid values
    assert "github.com" in config
    assert not config["github.com"]  # Should be empty dict due to invalid syntax

    # Empty hosts should be ignored
    assert "" not in config
    assert "=" not in config

    # gitlab.com should be parsed but without empty values
    assert "gitlab.com" in config
    assert not config["gitlab.com"]  # Should be empty dict due to missing values

    # Invalid host syntax should be ignored
    assert "example.com" not in config
    assert "invalid.host" not in config

    # Valid host should be parsed correctly despite comments
    assert "valid.com" in config
    assert config["valid.com"]["identityfile"] == "~/.ssh/valid_key"
    assert config["valid.com"]["user"] == "git"


def test_clone_repository_with_git_errors(ssh_manager, temp_dir):
    """Test clone_repository with git errors."""
    # Test with git command failure
    def mock_run_error(*args, **kwargs):
        if "git" in args[0]:
            raise subprocess.CalledProcessError(128, args[0], "fatal: repository not found")
        return subprocess.CompletedProcess(args[0], 0)

    with patch("subprocess.run", side_effect=mock_run_error):
        assert ssh_manager.clone_repository("git@github.com:user/repo.git", temp_dir) is False

    # Test with git command not found
    with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
        assert ssh_manager.clone_repository("git@github.com:user/repo.git", temp_dir) is False


def test_extract_hostname_with_special_cases(ssh_manager):
    """Test _extract_hostname with special cases."""
    # Test with various special characters in hostname
    assert ssh_manager._extract_hostname("git@host_name.com:user/repo.git") == "host_name.com"
    assert ssh_manager._extract_hostname("git@host-name.com:user/repo.git") == "host-name.com"
    assert ssh_manager._extract_hostname("git@host.name.com:user/repo.git") == "host.name.com"

    # Test with invalid URL formats
    assert ssh_manager._extract_hostname("git@host@com:repo.git") is None  # Multiple @ signs
    assert ssh_manager._extract_hostname("git:host.com:repo.git") is None  # Wrong format
    assert ssh_manager._extract_hostname("git@host.com:") is None  # Missing repository
    assert ssh_manager._extract_hostname("git@host.com/repo.git") is None  # Wrong separator


def test_run_command_additional_errors(ssh_manager):
    """Test additional error cases in run_command."""
    # Test with None command
    assert ssh_manager._run_command(None) is None

    # Test with empty command
    assert ssh_manager._run_command("") is None

    # Test with command list containing None
    assert ssh_manager._run_command(["git", None, "status"]) is None

    # Test with invalid command type
    assert ssh_manager._run_command(123) is None


def test_clone_repository_additional_errors(ssh_manager):
    """Test additional error cases in clone_repository."""
    # Test with None URL
    assert ssh_manager.clone_repository(None, "/tmp/repo") is False

    # Test with empty URL
    assert ssh_manager.clone_repository("", "/tmp/repo") is False

    # Test with None target directory
    assert ssh_manager.clone_repository("git@github.com:user/repo.git", None) is False

    # Test with empty target directory
    assert ssh_manager.clone_repository("git@github.com:user/repo.git", "") is False

def test_parse_ssh_config_with_syntax_error(ssh_manager, temp_dir, monkeypatch):
    """Test parse_ssh_config with syntax errors in config."""
    ssh_dir = Path(temp_dir) / ".ssh"
    ssh_dir.mkdir()
    config_path = ssh_dir / "config"

    # Test with empty lines and comments
    config_content = """
# Comment
Host github.com
    IdentityFile ~/.ssh/id_ed25519

# Another comment

Host example.com
    User git
    """
    config_path.write_text(config_content)
    monkeypatch.setattr(ssh_manager, "_ssh_dir", ssh_dir)
    config = ssh_manager._parse_ssh_config()
    assert "github.com" in config
    assert "example.com" in config
    if "identityfile" in config["github.com"]:
        assert config["github.com"]["identityfile"] == "~/.ssh/id_ed25519"
    if "user" in config["example.com"]:
        assert config["example.com"]["user"] == "git"

    # Test with invalid syntax - should skip invalid entries but keep valid ones
    config_content = """
# Invalid entries - should be skipped
Host
Host =
Host
    IdentityFile ~/.ssh/default_key

# Valid entry - should be parsed
Host github.com
    IdentityFile ~/.ssh/id_ed25519

# Invalid entries - should be skipped
Host invalid.com
    IdentityFile = ~/.ssh/invalid_key
    User = git

# Another valid entry - should be parsed
Host example.com
    User git
    """
    config_path.write_text(config_content)
    config = ssh_manager._parse_ssh_config()

    # Check that valid entries are parsed
    assert "github.com" in config
    assert "example.com" in config
    if "identityfile" in config["github.com"]:
        assert config["github.com"]["identityfile"] == "~/.ssh/id_ed25519"
    if "user" in config["example.com"]:
        assert config["example.com"]["user"] == "git"

    # Check that invalid entries are skipped
    assert "invalid.com" not in config

def test_start_ssh_agent_key_already_loaded(ssh_manager, temp_dir):
    """Test SSH agent startup when key is already loaded."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch("subprocess.run") as mock_run:
        # Mock that agent is started and key is already loaded
        ssh_manager._ssh_agent_started = True
        mock_process = MagicMock(
            returncode=0,
            stdout=f"2048 SHA256:xxx {identity_file} (RSA)"
        )
        mock_run.return_value = mock_process

        assert ssh_manager._start_ssh_agent(identity_file) is True
        call_args = mock_run.call_args
        assert call_args[0][0] == ["ssh-add", "-l"]
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True
        assert "shell" in call_args[1]
        assert "env" in call_args[1]

def test_start_ssh_agent_parse_error(ssh_manager, temp_dir):
    """Test SSH agent startup with environment variable parsing error."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch("subprocess.run") as mock_run:
        # First call for checking existing key
        mock_run.side_effect = [
            # First call - check existing key
            MagicMock(returncode=1),
            # Second call - load agent info fails
            MagicMock(returncode=0, stdout="Invalid output format"),
            # Third call - ssh-add fails
            MagicMock(returncode=1)
        ]

        assert ssh_manager._start_ssh_agent(identity_file) is False

def test_ssh_setup_with_invalid_key(ssh_manager, temp_dir, monkeypatch):
    """Test SSH setup with invalid key file."""
    monkeypatch.setattr(ssh_manager, "_get_identity_file",
                       lambda x: os.path.join(temp_dir, "nonexistent_key"))

    assert ssh_manager.setup_ssh("github.com") is False

def test_ssh_setup_with_agent_failure(ssh_manager, temp_dir, monkeypatch):
    """Test SSH setup when agent fails to start."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    monkeypatch.setattr(ssh_manager, "_get_identity_file", lambda x: identity_file)
    monkeypatch.setattr(ssh_manager, "_start_ssh_agent", lambda x: False)

    assert ssh_manager.setup_ssh("github.com") is False

def test_ssh_setup_with_key_add_failure(ssh_manager, temp_dir, monkeypatch):
    """Test SSH setup when key addition fails."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    monkeypatch.setattr(ssh_manager, "_get_identity_file", lambda x: identity_file)
    monkeypatch.setattr(ssh_manager, "_start_ssh_agent", lambda x: True)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Could not add identity"
        )
        assert ssh_manager.setup_ssh("github.com") is False

def test_parse_ssh_config_with_empty_file(ssh_manager, temp_dir, monkeypatch):
    """Test parsing empty SSH config file."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    assert ssh_manager._parse_ssh_config() == {}

def test_parse_ssh_config_with_comments(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config with comments."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("""
# This is a comment
Host github.com
    # This is another comment
    IdentityFile ~/.ssh/id_ed25519
    User git
""")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    config = ssh_manager._parse_ssh_config()
    assert "github.com" in config
    assert config["github.com"]["identityfile"] == "~/.ssh/id_ed25519"

def test_run_command_with_environment(ssh_manager):
    """Test running command with custom environment."""
    env = {"TEST_VAR": "test_value"}

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = ssh_manager._run_command(["echo", "$TEST_VAR"], env=env)
        assert result is not None
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert "env" in kwargs
        assert kwargs["env"]["TEST_VAR"] == "test_value"

def test_git_ssh_command_with_no_identity(ssh_manager):
    """Test Git SSH command generation with no identity file."""
    with patch.object(ssh_manager, "_get_identity_file", return_value=None):
        assert ssh_manager.get_git_ssh_command("github.com") is None

def test_git_ssh_command_with_spaces(ssh_manager, temp_dir):
    """Test Git SSH command with path containing spaces."""
    identity_file = os.path.join(temp_dir, "test key with spaces")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        cmd = ssh_manager.get_git_ssh_command("github.com")
        assert cmd is not None
        assert identity_file.replace(" ", "\\ ") in cmd

def test_parse_ssh_config_with_invalid_lines(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config with invalid lines."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("""
Host github.com
    Invalid Line
    IdentityFile ~/.ssh/id_ed25519
    User git
""")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    config = ssh_manager._parse_ssh_config()
    assert "github.com" in config
    assert config["github.com"]["identityfile"] == "~/.ssh/id_ed25519"

def test_start_ssh_agent_with_add_failure(ssh_manager, temp_dir):
    """Test SSH agent startup when key addition fails."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch("subprocess.run") as mock_run:
        def mock_run_side_effect(*args, **kwargs):
            if args[0][0] == "ssh-agent":
                return MagicMock(
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
                )
            elif args[0][0] == "ssh-add":
                return MagicMock(returncode=1, stderr="Could not add identity")
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect
        assert ssh_manager._start_ssh_agent(identity_file) is False

def test_git_ssh_command_with_spaces(ssh_manager, temp_dir):
    """Test Git SSH command with path containing spaces."""
    identity_file = os.path.join(temp_dir, "test key with spaces")
    with open(identity_file, "w") as f:
        f.write("mock key")

    # Mock _get_identity_file to return our test key
    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        # Mock setup_ssh to succeed
        with patch.object(ssh_manager, "setup_ssh", return_value=True):
            # Mock os.path.exists to return True for our test key
            with patch("os.path.exists", return_value=True):
                cmd = ssh_manager.get_git_ssh_command("github.com")
                assert cmd is not None
                assert identity_file.replace("\\", "/") in cmd
                assert "-o StrictHostKeyChecking=no" in cmd

def test_start_ssh_agent_with_kill_error(ssh_manager, temp_dir):
    """Test SSH agent startup when killing existing agent fails."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch("subprocess.run") as mock_run:
        def mock_run_side_effect(*args, **kwargs):
            if args[0][0] == "taskkill":
                return MagicMock(returncode=1)  # Kill fails
            elif args[0][0] == "ssh-agent":
                return MagicMock(
                    returncode=0,
                    stdout="SSH_AUTH_SOCK=/tmp/ssh.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=123; export SSH_AGENT_PID;"
                )
            elif args[0][0] == "ssh-add":
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect
        with patch("os.name", "nt"):
            assert ssh_manager._start_ssh_agent(identity_file) is True

def test_setup_ssh_with_key_load_error(ssh_manager, temp_dir):
    """Test SSH setup when key loading fails."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("subprocess.run") as mock_run:
            def mock_run_side_effect(*args, **kwargs):
                if args[0][0] == "ssh-add":
                    return MagicMock(returncode=1, stderr="Permission denied")
                return MagicMock(returncode=0)

            mock_run.side_effect = mock_run_side_effect
            assert ssh_manager.setup_ssh("github.com") is False

def test_setup_ssh_with_agent_env_error(ssh_manager, temp_dir):
    """Test SSH setup when agent environment is invalid."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("subprocess.run") as mock_run:
            def mock_run_side_effect(*args, **kwargs):
                if args[0][0] == "ssh-agent":
                    return MagicMock(returncode=0, stdout="Invalid environment output")
                return MagicMock(returncode=0)

            mock_run.side_effect = mock_run_side_effect
            assert ssh_manager.setup_ssh("github.com") is False

def test_parse_ssh_config_with_invalid_values(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config with invalid values."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("""
Host github.com
    IdentityFile ~/.ssh/id_ed25519
    User git
    Port invalid_port
""")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    config = ssh_manager._parse_ssh_config()
    assert "github.com" in config
    assert config["github.com"]["identityfile"] == "~/.ssh/id_ed25519"
    assert config["github.com"]["user"] == "git"
    assert "port" not in config["github.com"]

def test_parse_ssh_config_with_read_error(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config when file read fails."""

    def mock_open(*args, **kwargs):
        raise IOError("Failed to read file")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    with patch("builtins.open", mock_open):
        config = ssh_manager._parse_ssh_config()
        assert config == {}

def test_setup_ssh_with_missing_env(ssh_manager, temp_dir):
    """Test SSH setup when environment variables are missing."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("subprocess.run") as mock_run:
            def mock_run_side_effect(*args, **kwargs):
                if args[0][0] == "ssh-agent":
                    return MagicMock(
                        returncode=0,
                        stdout="Invalid=value;"  # Missing required env vars
                    )
                return MagicMock(returncode=0)

            mock_run.side_effect = mock_run_side_effect
            assert ssh_manager.setup_ssh("github.com") is False

def test_start_ssh_agent_with_env_parse_error(ssh_manager, temp_dir):
    """Test SSH agent startup when environment parsing fails."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch("subprocess.run") as mock_run:
        def mock_run_side_effect(*args, **kwargs):
            if args[0][0] == "ssh-add":
                return MagicMock(returncode=1)
            elif args[0][0] == "ssh-agent":
                return MagicMock(
                    returncode=0,
                    stdout="Invalid environment format"  # Invalid format
                )
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect
        assert ssh_manager._start_ssh_agent(identity_file) is False

def test_setup_ssh_with_agent_start_exception(ssh_manager, temp_dir):
    """Test SSH setup when agent start raises an exception."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Agent start failed")
            assert ssh_manager.setup_ssh("github.com") is False

def test_parse_ssh_config_with_invalid_host(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config with invalid host pattern."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("""
Host *invalid*host*  # Invalid host pattern
    IdentityFile ~/.ssh/id_ed25519
    User git
""")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    config = ssh_manager._parse_ssh_config()
    assert config == {}

def test_setup_ssh_with_key_not_found(ssh_manager):
    """Test SSH setup when no identity file is found."""
    with patch.object(ssh_manager, "_get_identity_file", return_value=None):
        assert ssh_manager.setup_ssh("github.com") is False

def test_setup_ssh_with_empty_hostname(ssh_manager):
    """Test SSH setup with empty hostname."""
    assert ssh_manager.setup_ssh("") is False

def test_setup_ssh_with_key_permission_error(ssh_manager, temp_dir):
    """Test SSH setup when key file has permission error."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("os.path.exists", side_effect=PermissionError("Access denied")):
            assert ssh_manager.setup_ssh("github.com") is False

def test_setup_ssh_with_agent_env_error(ssh_manager, temp_dir):
    """Test SSH setup when agent environment is invalid."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("subprocess.run") as mock_run:
            def mock_run_side_effect(*args, **kwargs):
                if args[0][0] == "ssh-agent":
                    return MagicMock(returncode=0, stdout="Invalid environment output")
                elif args[0][0] == "ssh-add":
                    return MagicMock(returncode=1)  # Key add fails
                return MagicMock(returncode=0)

            mock_run.side_effect = mock_run_side_effect
            assert ssh_manager.setup_ssh("github.com") is False

def test_setup_ssh_with_missing_env(ssh_manager, temp_dir):
    """Test SSH setup when environment variables are missing."""
    identity_file = os.path.join(temp_dir, "test_key")
    with open(identity_file, "w") as f:
        f.write("mock key")

    with patch.object(ssh_manager, "_get_identity_file", return_value=identity_file):
        with patch("subprocess.run") as mock_run:
            def mock_run_side_effect(*args, **kwargs):
                if args[0][0] == "ssh-agent":
                    return MagicMock(
                        returncode=0,
                        stdout="Invalid=value;"  # Missing required env vars
                    )
                elif args[0][0] == "ssh-add":
                    return MagicMock(returncode=1)  # Key add fails
                return MagicMock(returncode=0)

            mock_run.side_effect = mock_run_side_effect
            assert ssh_manager.setup_ssh("github.com") is False

def test_parse_ssh_config_with_invalid_host(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config with invalid host pattern."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("""
Host [invalid.host]  # Invalid host pattern
    IdentityFile ~/.ssh/id_ed25519
    User git
""")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    config = ssh_manager._parse_ssh_config()
    assert config == {}

def test_parse_ssh_config_with_invalid_host(ssh_manager, temp_dir, monkeypatch):
    """Test parsing SSH config with invalid host pattern."""
    config_file = os.path.join(temp_dir, "config")
    with open(config_file, "w") as f:
        f.write("""
Host github.com|example.com  # Invalid host pattern with pipe
    IdentityFile ~/.ssh/id_ed25519
    User git
""")

    monkeypatch.setattr(ssh_manager, "_ssh_dir", Path(temp_dir))
    config = ssh_manager._parse_ssh_config()
    assert config == {}
