"""Tests for list_keys functionality in CLI module."""

# Import built-in modules
from pathlib import Path
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.cli import Args
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import list_keys
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


def test_list_keys_empty(config_manager):
    """Test listing keys when there are no keys."""
    # Mock ConfigManager.list_keys to return empty dict
    with patch.object(ConfigManager, "list_keys", return_value={}):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args()

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Call list_keys
                list_keys(args)

                # Verify logger was called with the expected message
                mock_logger.info.assert_called_once_with("No SSH keys configured")


def test_list_keys_with_keys(config_manager):
    """Test listing keys when there are keys."""
    # Mock keys data
    keys_data = {
        "github": "~/.ssh/github_key",
        "gitlab": "~/.ssh/gitlab_key"
    }

    # Mock ConfigManager.list_keys to return our test data
    with patch.object(ConfigManager, "list_keys", return_value=keys_data):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args()

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Call list_keys
                list_keys(args)

                # Verify logger was called with the expected messages
                mock_logger.info.assert_any_call("Configured SSH keys:")
                mock_logger.info.assert_any_call("  github: ~/.ssh/github_key")
                mock_logger.info.assert_any_call("  gitlab: ~/.ssh/gitlab_key")


def test_list_keys_with_json_format():
    """Test listing keys in JSON format."""
    # We don't need to test JSON format as the list_keys function doesn't support it
    # This test is kept as a placeholder for future implementation
    pytest.skip("JSON format not supported in list_keys function")


def test_list_keys_with_json_format_empty():
    """Test listing keys in JSON format when there are no keys."""
    # We don't need to test JSON format as the list_keys function doesn't support it
    # This test is kept as a placeholder for future implementation
    pytest.skip("JSON format not supported in list_keys function")


def test_list_keys_with_error(config_manager):
    """Test listing keys when there is an error."""
    # Mock ConfigManager.list_keys to raise an exception
    with patch.object(ConfigManager, "list_keys", side_effect=Exception("Test error")):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args()

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Mock sys.exit to avoid test termination
                with patch("sys.exit") as mock_exit:
                    # Call list_keys
                    list_keys(args)

                    # Verify logger was called with the expected error message
                    mock_logger.error.assert_called_once()
                    assert "Failed to list SSH keys" in mock_logger.error.call_args[0][0]

                    # Verify sys.exit was called with exit code 1
                    assert mock_exit.call_count >= 1
                    assert mock_exit.call_args_list[0][0][0] == 1
