"""Tests for CLI module."""

# Import built-in modules
import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from click.testing import CliRunner
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import export_config
from persistent_ssh_agent.cli import import_config
from persistent_ssh_agent.cli import list_keys
from persistent_ssh_agent.cli import main
from persistent_ssh_agent.cli import remove_key
from persistent_ssh_agent.cli import run_ssh_connection_test
from persistent_ssh_agent.cli import setup_config
import pytest


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
    # Mock _derive_key_from_system to avoid OS-specific issues in CI
    with patch.object(config_manager, "_derive_key_from_system") as mock_derive:
        # Return a fixed key and salt for testing
        mock_derive.return_value = (b"0" * 32, b"1" * 16)

        # Set a passphrase
        assert config_manager.set_passphrase("test") is True

        # Get the passphrase
        mock_derive.reset_mock()
        mock_derive.return_value = (b"0" * 32, b"1" * 16)
        passphrase = config_manager.get_passphrase()
        assert passphrase is not None
        assert passphrase != "test"  # Should be encrypted

        # Verify the passphrase can be decrypted
        mock_derive.reset_mock()
        mock_derive.return_value = (b"0" * 32, b"1" * 16)
        deobfuscated = config_manager.deobfuscate_passphrase(passphrase)
        assert deobfuscated == "test"


def test_config_manager_get_set_identity_file(config_manager):
    """Test getting and setting an identity file."""
    # Set an identity file
    assert config_manager.set_identity_file("~/.ssh/id_rsa") is True

    # Get the identity file
    identity_file = config_manager.get_identity_file()
    # We expect the expanded path, so we'll just check that it ends with the right part
    assert identity_file.endswith(".ssh/id_rsa") or identity_file.endswith(".ssh\\id_rsa")


def test_config_manager_encrypt_decrypt(config_manager):
    """Test encryption and decryption of passphrase."""
    # Mock _derive_key_from_system to avoid OS-specific issues in CI
    with patch.object(config_manager, "_derive_key_from_system") as mock_derive:
        # Return a fixed key and salt for testing
        mock_derive.return_value = (b"0" * 32, b"1" * 16)

        passphrase = "test_passphrase"
        encrypted = config_manager._encrypt_passphrase(passphrase)

        # Reset the mock to ensure decryption uses the same key/salt
        mock_derive.reset_mock()
        mock_derive.return_value = (b"0" * 32, b"1" * 16)

        decrypted = config_manager.deobfuscate_passphrase(encrypted)
        assert decrypted == passphrase


@patch("persistent_ssh_agent.cli.ConfigManager")
@patch("persistent_ssh_agent.cli.os.path.exists", return_value=True)
def test_setup_config_identity_file(mock_exists, mock_config_manager):
    """Test setting up configuration with identity file."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = "~/.ssh/id_rsa"
    args.passphrase = None
    args.prompt_passphrase = False
    # Add expiration and reuse_agent attributes
    args.expiration = None
    args.reuse_agent = None

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
    # Add expiration and reuse_agent attributes
    args.expiration = None
    args.reuse_agent = None

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
    # Add new attributes
    args.expiration = None
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


def test_main():
    """Test the main function."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    # Verify the command ran successfully
    assert result.exit_code == 0

    # Verify the help text contains our commands
    assert "Commands:" in result.output
    assert "config" in result.output
    assert "test" in result.output
    assert "list" in result.output
    assert "remove" in result.output
    assert "export" in result.output
    assert "import" in result.output


def test_config_command():
    """Test the config command."""
    runner = CliRunner()

    # Test with identity file
    with patch("persistent_ssh_agent.cli.setup_config") as mock_setup_config:
        result = runner.invoke(main, ["config", "--identity-file", "~/.ssh/id_rsa"])
        assert result.exit_code == 0
        mock_setup_config.assert_called_once()
        args = mock_setup_config.call_args[0][0]
        assert args.identity_file == "~/.ssh/id_rsa"

    # Test with passphrase
    with patch("persistent_ssh_agent.cli.setup_config") as mock_setup_config:
        result = runner.invoke(main, ["config", "--passphrase", "test"])
        assert result.exit_code == 0
        mock_setup_config.assert_called_once()
        args = mock_setup_config.call_args[0][0]
        assert args.passphrase == "test"

    # Test with prompt passphrase
    with patch("persistent_ssh_agent.cli.setup_config") as mock_setup_config:
        result = runner.invoke(main, ["config", "--prompt-passphrase"])
        assert result.exit_code == 0
        mock_setup_config.assert_called_once()
        args = mock_setup_config.call_args[0][0]
        assert args.prompt_passphrase is True


def test_test_command():
    """Test the test command."""
    runner = CliRunner()

    # Test with hostname
    with patch("persistent_ssh_agent.cli.run_ssh_connection_test") as mock_test:
        result = runner.invoke(main, ["test", "github.com"])
        assert result.exit_code == 0
        mock_test.assert_called_once()
        args = mock_test.call_args[0][0]
        assert args.hostname == "github.com"

    # Test with identity file
    with patch("persistent_ssh_agent.cli.run_ssh_connection_test") as mock_test:
        result = runner.invoke(main, ["test", "github.com", "--identity-file", "~/.ssh/id_rsa"])
        assert result.exit_code == 0
        mock_test.assert_called_once()
        args = mock_test.call_args[0][0]
        assert args.hostname == "github.com"
        assert args.identity_file == "~/.ssh/id_rsa"


def test_list_command():
    """Test the list command."""
    runner = CliRunner()

    with patch("persistent_ssh_agent.cli.list_keys") as mock_list:
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        mock_list.assert_called_once_with(None)


def test_remove_command():
    """Test the remove command."""
    runner = CliRunner()

    # Test with name
    with patch("persistent_ssh_agent.cli.remove_key") as mock_remove:
        result = runner.invoke(main, ["remove", "--name", "github"])
        assert result.exit_code == 0
        mock_remove.assert_called_once()
        args = mock_remove.call_args[0][0]
        assert args.name == "github"
        assert args.all is False

    # Test with all
    with patch("persistent_ssh_agent.cli.remove_key") as mock_remove:
        result = runner.invoke(main, ["remove", "--all"])
        assert result.exit_code == 0
        mock_remove.assert_called_once()
        args = mock_remove.call_args[0][0]
        assert args.name is None
        assert args.all is True


def test_export_command():
    """Test the export command."""
    runner = CliRunner()

    # Test without options
    with patch("persistent_ssh_agent.cli.export_config") as mock_export:
        result = runner.invoke(main, ["export"])
        assert result.exit_code == 0
        mock_export.assert_called_once()
        args = mock_export.call_args[0][0]
        assert args.output is None
        assert args.include_sensitive is False

    # Test with output file
    with patch("persistent_ssh_agent.cli.export_config") as mock_export:
        result = runner.invoke(main, ["export", "--output", "config.json"])
        assert result.exit_code == 0
        mock_export.assert_called_once()
        args = mock_export.call_args[0][0]
        assert args.output == "config.json"

    # Test with include sensitive
    with patch("persistent_ssh_agent.cli.export_config") as mock_export:
        result = runner.invoke(main, ["export", "--include-sensitive"])
        assert result.exit_code == 0
        mock_export.assert_called_once()
        args = mock_export.call_args[0][0]
        assert args.include_sensitive is True


def test_import_command():
    """Test the import command."""
    runner = CliRunner()

    with patch("persistent_ssh_agent.cli.import_config") as mock_import:
        result = runner.invoke(main, ["import", "config.json"])
        assert result.exit_code == 0
        mock_import.assert_called_once()
        args = mock_import.call_args[0][0]
        assert args.input == "config.json"


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
        with patch("json.load", return_value={"identity_file": "~/.ssh/id_rsa"}):
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                import_config(args)

                # Verify open was called with the correct parameters
                mock_open.assert_called_once_with("config.json", "r", encoding="utf-8")

                # Verify import_config was called with the correct parameters
                mock_manager.import_config.assert_called_once_with({"identity_file": "~/.ssh/id_rsa"})

                # Verify logger was called with the correct message
                mock_logger.info.assert_called_once_with("Configuration imported successfully")
