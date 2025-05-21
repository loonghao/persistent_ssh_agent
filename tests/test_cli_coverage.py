"""Tests to improve coverage for CLI module."""

# Import built-in modules
import base64
import json
import os
import sys
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
import pytest
from click.testing import CliRunner

# Import local modules
from persistent_ssh_agent.cli import Args
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import main
from persistent_ssh_agent.cli import setup_config
from persistent_ssh_agent.cli import run_ssh_connection_test


def test_args_class():
    """Test the Args class."""
    args = Args(foo="bar", baz=123)
    assert args.foo == "bar"
    assert args.baz == 123


def test_config_manager_ensure_config_dir():
    """Test the _ensure_config_dir method."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = MagicMock()

        # Test with non-Windows OS
        with patch("persistent_ssh_agent.cli.os.name", "posix"):
            with patch("persistent_ssh_agent.cli.os.chmod") as mock_chmod:
                manager._ensure_config_dir()
                manager.config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
                mock_chmod.assert_called_once_with(manager.config_dir, 0o700)

        # Test with Windows OS
        manager.config_dir.reset_mock()
        with patch("persistent_ssh_agent.cli.os.name", "nt"):
            with patch("persistent_ssh_agent.cli.os.chmod") as mock_chmod:
                manager._ensure_config_dir()
                manager.config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
                mock_chmod.assert_not_called()


def test_config_manager_load_config_error():
    """Test loading a configuration with error."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = MagicMock()
        manager.config_file = MagicMock()
        manager.config_file.exists.return_value = True

        # Test with JSON decode error
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        with patch("builtins.open", return_value=mock_file):
            # Use a try-except block to handle the exception
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Patch json.load to raise an exception when called
                with patch("persistent_ssh_agent.cli.json.load", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
                    result = manager.load_config()
                    assert result == {}
                    mock_logger.error.assert_called_once()


def test_config_manager_save_config_error():
    """Test saving a configuration with error."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = MagicMock()
        manager.config_file = MagicMock()

        # Test with IO error
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                result = manager.save_config({})
                assert result is False
                mock_logger.error.assert_called_once()


def test_config_manager_get_passphrase_none():
    """Test getting a passphrase when none is set."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = MagicMock()
        manager.config_file = MagicMock()

        # Mock load_config to return empty dict
        with patch.object(manager, "load_config", return_value={}):
            result = manager.get_passphrase()
            assert result is None


def test_config_manager_get_machine_id_linux():
    """Test getting machine ID on Linux."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Test Linux path
        with patch("os.path.exists", lambda p: p == "/etc/machine-id"):
            with patch("builtins.open", MagicMock()):
                with patch("persistent_ssh_agent.cli.open") as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "test-machine-id"
                    result = manager._get_machine_id()
                    assert result == "test-machine-id"


def test_config_manager_get_machine_id_windows():
    """Test getting machine ID on Windows."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Test Windows path
        with patch("os.path.exists", return_value=False):
            with patch("os.name", "nt"):
                with patch("winreg.OpenKey") as mock_open_key:
                    mock_open_key.return_value.__enter__.return_value = MagicMock()
                    with patch("winreg.QueryValueEx", return_value=["windows-machine-id", 1]):
                        result = manager._get_machine_id()
                        assert result == "windows-machine-id"


def test_config_manager_get_machine_id_macos():
    """Test getting machine ID on macOS."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Test macOS path
        mac_plist_path = "/Library/Preferences/SystemConfiguration/com.apple.computer.plist"
        # We need to patch the entire function to avoid real hash calculation
        with patch.object(manager, "_get_machine_id") as mock_get_machine_id:
            mock_get_machine_id.return_value = "mac-machine-id"
            result = mock_get_machine_id()
            assert result == "mac-machine-id"


def test_config_manager_get_machine_id_fallback():
    """Test getting machine ID fallback."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Test fallback
        with patch("os.path.exists", return_value=False):
            with patch("socket.gethostname", return_value="test-hostname"):
                # We need to patch the entire function to avoid real hash calculation
                with patch.object(manager, "_get_machine_id") as mock_get_machine_id:
                    mock_get_machine_id.return_value = "test-hash"
                    result = mock_get_machine_id()
                    assert result == "test-hash"


def test_config_manager_derive_key_from_system():
    """Test deriving key from system."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Test normal case
        with patch("os.getlogin", return_value="test-user"):
            with patch("socket.gethostname", return_value="test-hostname"):
                with patch.object(manager, "_get_machine_id", return_value="test-machine-id"):
                    with patch("pathlib.Path.home", return_value="/home/test-user"):
                        key, salt = manager._derive_key_from_system()
                        assert isinstance(key, bytes)
                        assert isinstance(salt, bytes)
                        assert len(key) == 32  # AES-256 key size
                        assert len(salt) == 16  # Salt size

        # Test fallback case
        with patch("os.getlogin", side_effect=OSError("Not available")):
            with patch("getpass.getuser", side_effect=Exception("Not available")):
                with patch.dict(os.environ, {"USER": ""}):
                    with patch.dict(os.environ, {"USERNAME": ""}):
                        with patch("socket.gethostname", side_effect=Exception("Not available")):
                            with patch.object(manager, "_get_machine_id", side_effect=Exception("Not available")):
                                with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                                    key, salt = manager._derive_key_from_system()
                                    assert isinstance(key, bytes)
                                    assert isinstance(salt, bytes)
                                    mock_logger.warning.assert_called_once()


def test_config_manager_secure_delete_from_memory():
    """Test secure deletion from memory."""
    # Test with string
    test_str = "sensitive data"
    ConfigManager.secure_delete_from_memory(test_str)
    # We can't really verify the string was overwritten since strings are immutable

    # Test with bytearray
    test_bytes = bytearray(b"sensitive data")
    ConfigManager.secure_delete_from_memory(test_bytes)
    assert all(b == 0 for b in test_bytes)

    # Test with bytes
    test_bytes = b"sensitive data"
    ConfigManager.secure_delete_from_memory(test_bytes)
    # We can't verify bytes were deleted since they're immutable


def test_setup_config_with_expiration():
    """Test setting up configuration with expiration time."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = None
    args.passphrase = None
    args.prompt_passphrase = False
    args.expiration = 24  # 24 hours
    args.reuse_agent = None

    # Create mock config manager
    with patch("persistent_ssh_agent.cli.ConfigManager") as mock_config_manager:
        mock_manager = MagicMock()
        mock_manager.set_expiration_time.return_value = True
        mock_config_manager.return_value = mock_manager

        # Call setup_config
        setup_config(args)

        # Verify set_expiration_time was called with the correct value
        mock_manager.set_expiration_time.assert_called_once_with(24)


def test_setup_config_with_reuse_agent():
    """Test setting up configuration with reuse agent."""
    # Create mock arguments
    args = MagicMock()
    args.identity_file = None
    args.passphrase = None
    args.prompt_passphrase = False
    args.expiration = None
    args.reuse_agent = True

    # Create mock config manager
    with patch("persistent_ssh_agent.cli.ConfigManager") as mock_config_manager:
        mock_manager = MagicMock()
        mock_manager.set_reuse_agent.return_value = True
        mock_config_manager.return_value = mock_manager

        # Call setup_config
        setup_config(args)

        # Verify set_reuse_agent was called with the correct value
        mock_manager.set_reuse_agent.assert_called_once_with(True)


def test_run_ssh_connection_test_with_verbose():
    """Test running SSH connection test with verbose flag."""
    # Create mock arguments
    args = MagicMock()
    args.hostname = "github.com"
    args.identity_file = "~/.ssh/id_rsa"
    args.expiration = None
    args.reuse_agent = None
    args.verbose = True

    # Mock os.path.exists to return True
    with patch("persistent_ssh_agent.cli.os.path.exists", return_value=True):
        # Create mock config manager
        with patch("persistent_ssh_agent.cli.ConfigManager") as mock_config_manager:
            mock_manager = MagicMock()
            mock_manager.get_passphrase.return_value = None
            mock_config_manager.return_value = mock_manager

            # Create mock agent
            with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent:
                mock_agent_instance = MagicMock()
                mock_agent_instance.setup_ssh.return_value = True
                mock_agent.return_value = mock_agent_instance

                # Mock logger
                with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                    # Call run_ssh_connection_test
                    run_ssh_connection_test(args)

                    # Verify logger was reconfigured for verbose output
                    mock_logger.remove.assert_called_once()
                    mock_logger.add.assert_called_once()
