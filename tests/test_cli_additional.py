"""Additional tests for CLI module."""

# Import built-in modules
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
import pytest
from click.testing import CliRunner

# Import local modules
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import export_config
from persistent_ssh_agent.cli import run_ssh_connection_test
from persistent_ssh_agent.cli import setup_config


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def config_manager(temp_dir):
    """Create a ConfigManager instance with a temporary directory."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = Path(temp_dir) / ".persistent_ssh_agent"
        manager.config_file = manager.config_dir / "config.json"
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        return manager


def test_config_manager_get_expiration_time(config_manager):
    """Test getting expiration time."""
    # Set expiration time
    assert config_manager.set_expiration_time(24) is True

    # Get expiration time
    expiration_time = config_manager.get_expiration_time()
    assert expiration_time == 24 * 3600  # Converted to seconds


def test_config_manager_get_reuse_agent(config_manager):
    """Test getting reuse agent setting."""
    # Set reuse agent
    assert config_manager.set_reuse_agent(True) is True

    # Get reuse agent
    reuse_agent = config_manager.get_reuse_agent()
    assert reuse_agent is True


def test_config_manager_add_key(config_manager):
    """Test adding a named SSH key."""
    # Add a key
    assert config_manager.add_key("github", "~/.ssh/github_key") is True

    # Verify the key was added
    keys = config_manager.list_keys()
    assert "github" in keys
    assert keys["github"].endswith(".ssh/github_key") or keys["github"].endswith(".ssh\\github_key")


def test_config_manager_clear_config(config_manager):
    """Test clearing configuration."""
    # Set some configuration
    config_manager.set_identity_file("~/.ssh/id_rsa")
    config_manager.add_key("github", "~/.ssh/github_key")

    # Clear configuration
    assert config_manager.clear_config() is True

    # Verify configuration was cleared
    assert config_manager.load_config() == {}


def test_config_manager_secure_delete_from_memory():
    """Test secure deletion from memory."""
    # Test with string
    test_str = "sensitive_data"
    ConfigManager.secure_delete_from_memory(test_str)
    # We can't really verify the string was overwritten, but we can check the function doesn't crash

    # Test with bytearray
    test_bytes = bytearray(b"sensitive_data")
    ConfigManager.secure_delete_from_memory(test_bytes)
    # Verify bytes were zeroed
    assert all(b == 0 for b in test_bytes)

    # Test with bytes (immutable)
    test_immutable = b"sensitive_data"
    ConfigManager.secure_delete_from_memory(test_immutable)
    # We can't verify immutable bytes were affected, but we can check the function doesn't crash


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_setup_config_expiration(mock_exists, mock_config_manager):
    """Test setting up configuration with expiration time."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = None
    args.passphrase = None
    args.prompt_passphrase = False
    args.expiration = 24
    args.reuse_agent = None

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.set_expiration_time.return_value = True
    mock_config_manager.return_value = mock_manager

    # Call setup_config
    setup_config(args)

    # Verify the expiration time was set
    mock_manager.set_expiration_time.assert_called_once_with(24)


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_setup_config_reuse_agent(mock_exists, mock_config_manager):
    """Test setting up configuration with reuse agent."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = None
    args.passphrase = None
    args.prompt_passphrase = False
    args.expiration = None
    args.reuse_agent = True

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.set_reuse_agent.return_value = True
    mock_config_manager.return_value = mock_manager

    # Call setup_config
    setup_config(args)

    # Verify the reuse agent was set
    mock_manager.set_reuse_agent.assert_called_once_with(True)


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.PersistentSSHAgent")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_run_ssh_connection_test_with_expiration(mock_exists, mock_agent, mock_config_manager):
    """Test testing a connection with expiration time."""
    # Create mock arguments
    args = MagicMock()
    args.hostname = "github.com"
    args.identity_file = "~/.ssh/id_rsa"
    args.expiration = 24
    args.reuse_agent = None
    args.verbose = False

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.get_passphrase.return_value = None
    mock_config_manager.return_value = mock_manager

    # Create mock agent
    mock_agent_instance = MagicMock()
    mock_agent_instance.setup_ssh.return_value = True
    mock_agent.return_value = mock_agent_instance

    # Call run_ssh_connection_test
    run_ssh_connection_test(args)

    # Verify the agent was created and setup_ssh was called
    mock_agent.assert_called_once()
    mock_agent_instance.setup_ssh.assert_called_once_with("github.com")


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.PersistentSSHAgent")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_run_ssh_connection_test_with_reuse_agent(mock_exists, mock_agent, mock_config_manager):
    """Test testing a connection with reuse agent."""
    # Create mock arguments
    args = MagicMock()
    args.hostname = "github.com"
    args.identity_file = "~/.ssh/id_rsa"
    args.expiration = None
    args.reuse_agent = True
    args.verbose = False

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.get_passphrase.return_value = None
    mock_config_manager.return_value = mock_manager

    # Create mock agent
    mock_agent_instance = MagicMock()
    mock_agent_instance.setup_ssh.return_value = True
    mock_agent.return_value = mock_agent_instance

    # Call run_ssh_connection_test
    run_ssh_connection_test(args)

    # Verify the agent was created and setup_ssh was called
    mock_agent.assert_called_once()
    mock_agent_instance.setup_ssh.assert_called_once_with("github.com")


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.PersistentSSHAgent")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_run_ssh_connection_test_with_verbose(mock_exists, mock_agent, mock_config_manager):
    """Test testing a connection with verbose output."""
    # Create mock arguments
    args = MagicMock()
    args.hostname = "github.com"
    args.identity_file = "~/.ssh/id_rsa"
    args.expiration = None
    args.reuse_agent = None
    args.verbose = True

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.get_passphrase.return_value = None
    mock_config_manager.return_value = mock_manager

    # Create mock agent
    mock_agent_instance = MagicMock()
    mock_agent_instance.setup_ssh.return_value = True
    mock_agent.return_value = mock_agent_instance

    # Call run_ssh_connection_test
    with patch("persistent_ssh_agent.cli.logger") as mock_logger:
        run_ssh_connection_test(args)

        # Verify logger was reconfigured
        mock_logger.remove.assert_called_once()
        mock_logger.add.assert_called_once()

    # Verify the agent was created and setup_ssh was called
    mock_agent.assert_called_once()
    mock_agent_instance.setup_ssh.assert_called_once_with("github.com")


def test_export_config_to_file():
    """Test exporting configuration to a file."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create mock arguments
        args = MagicMock()
        args.output = "config.json"
        args.include_sensitive = False

        # Create mock config manager
        with patch("persistent_ssh_agent.cli.ConfigManager") as mock_config_manager:
            mock_manager = MagicMock()
            mock_manager.export_config.return_value = {
                "identity_file": "~/.ssh/id_rsa",
                "keys": {
                    "github": "~/.ssh/github_key"
                }
            }
            mock_config_manager.return_value = mock_manager

            # Call export_config
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                export_config(args)

                # Verify export_config was called with the correct parameters
                mock_manager.export_config.assert_called_once_with(include_sensitive=False)

                # Verify logger was called with the correct message
                mock_logger.info.assert_called_once_with("Configuration exported to config.json")

            # Verify file was created
            assert os.path.exists("config.json")
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                assert config["identity_file"] == "~/.ssh/id_rsa"
                assert config["keys"]["github"] == "~/.ssh/github_key"
