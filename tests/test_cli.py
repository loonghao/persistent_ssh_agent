"""Tests for CLI module."""

# Import built-in modules
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
import pytest

# Import local modules
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import export_config
from persistent_ssh_agent.cli import import_config
from persistent_ssh_agent.cli import list_keys
from persistent_ssh_agent.cli import main
from persistent_ssh_agent.cli import remove_key
from persistent_ssh_agent.cli import run_ssh_connection_test
from persistent_ssh_agent.cli import setup_config


@pytest.fixture
def config_manager(temp_dir):
    """Create a ConfigManager instance with a temporary directory."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = Path(temp_dir) / ".persistent_ssh_agent"
        manager.config_file = manager.config_dir / "config.json"
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        return manager


def test_config_manager_load_config_empty(config_manager):
    """Test loading an empty configuration."""
    assert config_manager.load_config() == {}


def test_config_manager_load_config(config_manager):
    """Test loading a configuration."""
    # Create a test configuration
    test_config = {"passphrase": "test", "identity_file": "~/.ssh/id_rsa"}
    with open(config_manager.config_file, "w") as f:
        json.dump(test_config, f)

    # Load the configuration
    assert config_manager.load_config() == test_config


def test_config_manager_save_config(config_manager):
    """Test saving a configuration."""
    # Save a test configuration
    test_config = {"passphrase": "test", "identity_file": "~/.ssh/id_rsa"}
    assert config_manager.save_config(test_config) is True

    # Verify the configuration was saved
    with open(config_manager.config_file, "r") as f:
        assert json.load(f) == test_config


def test_config_manager_get_set_passphrase(config_manager):
    """Test getting and setting a passphrase."""
    # Set a passphrase
    assert config_manager.set_passphrase("test") is True

    # Get the passphrase
    passphrase = config_manager.get_passphrase()
    assert passphrase is not None
    assert passphrase != "test"  # Should be obfuscated

    # Verify the passphrase can be deobfuscated
    deobfuscated = config_manager._deobfuscate_passphrase(passphrase)
    assert deobfuscated == "test"


def test_config_manager_get_set_identity_file(config_manager):
    """Test getting and setting an identity file."""
    # Set an identity file
    assert config_manager.set_identity_file("~/.ssh/id_rsa") is True

    # Get the identity file
    identity_file = config_manager.get_identity_file()
    # We expect the expanded path, so we'll just check that it ends with the right part
    assert identity_file.endswith(".ssh/id_rsa") or identity_file.endswith(".ssh\\id_rsa")


def test_config_manager_obfuscate_deobfuscate(config_manager):
    """Test obfuscation and deobfuscation of passphrase."""
    passphrase = "test_passphrase"
    obfuscated = config_manager._obfuscate_passphrase(passphrase)
    deobfuscated = config_manager._deobfuscate_passphrase(obfuscated)
    assert deobfuscated == passphrase


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_setup_config_identity_file(mock_exists, mock_config_manager):
    """Test setting up configuration with identity file."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = "~/.ssh/id_rsa"
    args.passphrase = None
    args.prompt_passphrase = False

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.set_identity_file.return_value = True
    mock_config_manager.return_value = mock_manager

    # Call setup_config
    setup_config(args)

    # Verify the identity file was set - we don't check the exact path since it gets expanded
    assert mock_manager.set_identity_file.call_count == 1
    # Check that the argument ends with the right part
    call_arg = mock_manager.set_identity_file.call_args[0][0]
    assert call_arg.endswith(".ssh/id_rsa") or call_arg.endswith(".ssh\\id_rsa")


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_setup_config_passphrase(mock_exists, mock_config_manager):
    """Test setting up configuration with passphrase."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = None
    args.passphrase = "test"
    args.prompt_passphrase = False

    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.set_passphrase.return_value = True
    mock_config_manager.return_value = mock_manager

    # Call setup_config
    setup_config(args)

    # Verify the passphrase was set
    mock_manager.set_passphrase.assert_called_once_with("test")


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.PersistentSSHAgent")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_test_connection(mock_exists, mock_agent, mock_config_manager):
    """Test testing a connection."""
    # Create mock arguments
    args = MagicMock()
    args.hostname = "github.com"
    args.identity_file = "~/.ssh/id_rsa"

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


@patch("persistent_ssh_agent.cli.argparse.ArgumentParser")
def test_main(mock_parser):
    """Test the main function."""
    # Create mock parser
    mock_parser_instance = MagicMock()
    mock_parser.return_value = mock_parser_instance

    # Create mock arguments
    mock_args = MagicMock()
    mock_args.command = None
    mock_parser_instance.parse_args.return_value = mock_args

    # Call main with sys.exit mocked
    with patch("persistent_ssh_agent.cli.sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_once_with(1)

    # Verify the parser was created and parse_args was called
    mock_parser.assert_called_once()
    mock_parser_instance.parse_args.assert_called_once()


@patch("persistent_ssh_agent.cli.ConfigManager")
def test_list_keys(mock_config_manager):
    """Test listing SSH keys."""
    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.list_keys.return_value = {
        "default": "~/.ssh/id_rsa",
        "github": "~/.ssh/github_key"
    }
    mock_config_manager.return_value = mock_manager

    # Call list_keys
    with patch("persistent_ssh_agent.cli.logger") as mock_logger:
        list_keys(None)

        # Verify logger was called with the correct messages
        mock_logger.info.assert_any_call("Configured SSH keys:")
        mock_logger.info.assert_any_call("  default: ~/.ssh/id_rsa")
        mock_logger.info.assert_any_call("  github: ~/.ssh/github_key")


@patch("persistent_ssh_agent.cli.ConfigManager")
def test_list_keys_empty(mock_config_manager):
    """Test listing SSH keys when none are configured."""
    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.list_keys.return_value = {}
    mock_config_manager.return_value = mock_manager

    # Call list_keys
    with patch("persistent_ssh_agent.cli.logger") as mock_logger:
        list_keys(None)

        # Verify logger was called with the correct message
        mock_logger.info.assert_called_once_with("No SSH keys configured")


@patch("persistent_ssh_agent.cli.ConfigManager")
def test_remove_key_by_name(mock_config_manager):
    """Test removing a specific SSH key."""
    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.remove_key.return_value = True
    mock_config_manager.return_value = mock_manager

    # Create mock arguments
    args = MagicMock()
    args.name = "github"
    args.all = False

    # Call remove_key
    with patch("persistent_ssh_agent.cli.logger") as mock_logger:
        remove_key(args)

        # Verify remove_key was called with the correct name
        mock_manager.remove_key.assert_called_once_with("github")

        # Verify logger was called with the correct message
        mock_logger.info.assert_called_once_with("SSH key 'github' removed")


@patch("persistent_ssh_agent.cli.ConfigManager")
def test_remove_all_keys(mock_config_manager):
    """Test removing all SSH keys."""
    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.clear_config.return_value = True
    mock_config_manager.return_value = mock_manager

    # Create mock arguments
    args = MagicMock()
    args.name = None
    args.all = True

    # Call remove_key
    with patch("persistent_ssh_agent.cli.logger") as mock_logger:
        remove_key(args)

        # Verify clear_config was called
        mock_manager.clear_config.assert_called_once()

        # Verify logger was called with the correct message
        mock_logger.info.assert_called_once_with("All SSH keys removed")


@patch("persistent_ssh_agent.cli.ConfigManager")
def test_export_config_to_console(mock_config_manager):
    """Test exporting configuration to console."""
    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.export_config.return_value = {
        "identity_file": "~/.ssh/id_rsa",
        "keys": {
            "github": "~/.ssh/github_key"
        }
    }
    mock_config_manager.return_value = mock_manager

    # Create mock arguments
    args = MagicMock()
    args.output = None
    args.include_sensitive = False

    # Call export_config
    with patch("builtins.print") as mock_print:
        export_config(args)

        # Verify export_config was called with the correct parameters
        mock_manager.export_config.assert_called_once_with(include_sensitive=False)

        # Verify print was called with the correct JSON
        mock_print.assert_called_once()


@patch("persistent_ssh_agent.cli.ConfigManager")
def test_import_config(mock_config_manager):
    """Test importing configuration."""
    # Create mock config manager
    mock_manager = MagicMock()
    mock_manager.import_config.return_value = True
    mock_config_manager.return_value = mock_manager

    # Create mock arguments
    args = MagicMock()
    args.input = "config.json"

    # Create mock file
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_file.read.return_value = '{"identity_file": "~/.ssh/id_rsa"}'

    # Call import_config
    with patch("builtins.open", return_value=mock_file) as mock_open:
        with patch("json.load", return_value={"identity_file": "~/.ssh/id_rsa"}) as mock_json_load:
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                import_config(args)

                # Verify open was called with the correct parameters
                mock_open.assert_called_once_with("config.json", "r", encoding="utf-8")

                # Verify import_config was called with the correct parameters
                mock_manager.import_config.assert_called_once_with({"identity_file": "~/.ssh/id_rsa"})

                # Verify logger was called with the correct message
                mock_logger.info.assert_called_once_with("Configuration imported successfully")
