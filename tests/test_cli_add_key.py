"""Tests for add_key functionality in CLI module."""

# Import built-in modules
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.cli import Args
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import add_key
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


def test_add_key_default(config_manager):
    """Test adding a default SSH key."""
    # Mock ConfigManager.add_key to return True
    with patch.object(ConfigManager, "add_key", return_value=True):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(name="default", identity_file="~/.ssh/id_rsa")

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Call add_key
                add_key(args)

                # Verify ConfigManager.add_key was called with the correct arguments
                config_manager.add_key.assert_called_once_with("default", "~/.ssh/id_rsa")

                # Verify logger was called with the expected message
                mock_logger.info.assert_called_once_with("SSH key 'default' added")


def test_add_key_named(config_manager):
    """Test adding a named SSH key."""
    # Mock ConfigManager.add_key to return True
    with patch.object(ConfigManager, "add_key", return_value=True):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(name="github", identity_file="~/.ssh/github_key")

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Call add_key
                add_key(args)

                # Verify ConfigManager.add_key was called with the correct arguments
                config_manager.add_key.assert_called_once_with("github", "~/.ssh/github_key")

                # Verify logger was called with the expected message
                mock_logger.info.assert_called_once_with("SSH key 'github' added")


def test_add_key_failure(config_manager):
    """Test adding a SSH key with failure."""
    # Mock ConfigManager.add_key to return False
    with patch.object(ConfigManager, "add_key", return_value=False):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(name="github", identity_file="~/.ssh/github_key")

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Mock sys.exit to avoid test termination
                with patch("sys.exit") as mock_exit:
                    # Call add_key
                    add_key(args)

                    # Verify ConfigManager.add_key was called with the correct arguments
                    config_manager.add_key.assert_called_once_with("github", "~/.ssh/github_key")

                    # Verify logger was called with the expected error message
                    mock_logger.error.assert_called_once_with("Failed to add SSH key 'github'")

                    # Verify sys.exit was called with exit code 1
                    mock_exit.assert_called_once_with(1)


def test_add_key_exception(config_manager):
    """Test adding a SSH key with exception."""
    # Mock ConfigManager.add_key to raise an exception
    with patch.object(ConfigManager, "add_key", side_effect=Exception("Test error")):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(name="github", identity_file="~/.ssh/github_key")

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Mock sys.exit to avoid test termination
                with patch("sys.exit") as mock_exit:
                    # Call add_key
                    add_key(args)

                    # Verify logger was called with the expected error message
                    mock_logger.error.assert_called_once()
                    assert "Failed to add SSH key 'github'" in mock_logger.error.call_args[0][0]

                    # Verify sys.exit was called with exit code 1
                    mock_exit.assert_called_once_with(1)


def test_add_key_missing_name(config_manager):
    """Test adding a SSH key with missing name."""
    # Create mock ConfigManager instance
    with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
        # Create mock arguments
        args = Args(identity_file="~/.ssh/id_rsa")

        # Mock logger
        with patch("persistent_ssh_agent.cli.logger") as mock_logger:
            # Mock sys.exit to avoid test termination
            with patch("sys.exit") as mock_exit:
                # Set side effect to raise an exception to stop execution
                mock_exit.side_effect = SystemExit(1)

                with suppress(SystemExit):
                    # Call add_key
                    add_key(args)

                # Verify logger was called with the expected error message
                mock_logger.error.assert_called_once_with("No key name specified")

                # Verify sys.exit was called with exit code 1
                mock_exit.assert_called_once_with(1)


def test_add_key_missing_identity_file(config_manager):
    """Test adding a SSH key with missing identity file."""
    # Create mock ConfigManager instance
    with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
        # Create mock arguments
        args = Args(name="github")

        # Mock logger
        with patch("persistent_ssh_agent.cli.logger") as mock_logger:
            # Mock sys.exit to avoid test termination
            with patch("sys.exit") as mock_exit:
                # Set side effect to raise an exception to stop execution
                mock_exit.side_effect = SystemExit(1)

                with suppress(SystemExit):
                    # Call add_key
                    add_key(args)

                # Verify logger was called with the expected error message
                mock_logger.error.assert_called_once_with("No identity file specified")

                # Verify sys.exit was called with exit code 1
                mock_exit.assert_called_once_with(1)
