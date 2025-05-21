"""Tests for export and import functionality in CLI module."""

# Import built-in modules
import json
import os
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

# Import third-party modules
import pytest
from persistent_ssh_agent.cli import Args
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import export_config
from persistent_ssh_agent.cli import import_config


@pytest.fixture
def config_manager(temp_dir):
    """Create a ConfigManager instance with a temporary directory."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()
        manager.config_dir = Path(temp_dir) / ".persistent_ssh_agent"
        manager.config_file = manager.config_dir / "config.json"
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        return manager


def test_export_config_to_console(config_manager):
    """Test exporting configuration to console."""
    # Mock configuration data
    config_data = {
        "identity_file": "~/.ssh/id_rsa",
        "keys": {
            "github": "~/.ssh/github_key"
        },
        "expiration_time": 86400,
        "reuse_agent": True,
        "passphrase": "encrypted_passphrase"
    }

    # Mock ConfigManager.export_config to return our test data
    with patch.object(ConfigManager, "export_config", return_value=config_data):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(output=None, include_sensitive=False)

            # Mock print function
            with patch("builtins.print") as mock_print:
                # Call export_config
                export_config(args)

                # Verify print was called with the expected JSON
                mock_print.assert_called_once()
                printed_json = mock_print.call_args[0][0]
                assert json.loads(printed_json) == config_data


def test_export_config_to_file(config_manager, temp_dir):
    """Test exporting configuration to a file."""
    # Mock configuration data
    config_data = {
        "identity_file": "~/.ssh/id_rsa",
        "keys": {
            "github": "~/.ssh/github_key"
        },
        "expiration_time": 86400,
        "reuse_agent": True
    }

    # Create output file path
    output_file = os.path.join(temp_dir, "config_export.json")

    # Mock ConfigManager.export_config to return our test data
    with patch.object(ConfigManager, "export_config", return_value=config_data):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(output=output_file, include_sensitive=False)

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Call export_config
                export_config(args)

                # Verify logger was called with the expected message
                mock_logger.info.assert_called_once_with(f"Configuration exported to {output_file}")

                # Verify file was written with the expected content
                with open(output_file, "r", encoding="utf-8") as f:
                    exported_data = json.load(f)
                    assert exported_data == config_data


def test_export_config_with_sensitive_data(config_manager):
    """Test exporting configuration with sensitive data."""
    # Mock configuration data
    config_data = {
        "identity_file": "~/.ssh/id_rsa",
        "keys": {
            "github": "~/.ssh/github_key"
        },
        "passphrase": "encrypted_passphrase"
    }

    # Mock ConfigManager.export_config to return our test data
    with patch.object(ConfigManager, "export_config", return_value=config_data):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(output=None, include_sensitive=True)

            # Mock print function
            with patch("builtins.print") as mock_print:
                # Call export_config
                export_config(args)

                # Verify print was called with the expected JSON
                mock_print.assert_called_once()
                printed_json = mock_print.call_args[0][0]
                assert "passphrase" in json.loads(printed_json)


def test_export_config_file_error(config_manager):
    """Test exporting configuration with file error."""
    # Mock configuration data
    config_data = {
        "identity_file": "~/.ssh/id_rsa"
    }

    # Mock ConfigManager.export_config to return our test data
    with patch.object(ConfigManager, "export_config", return_value=config_data):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(output="/invalid/path/config.json", include_sensitive=False)

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Mock open to raise IOError
                with patch("builtins.open", side_effect=IOError("Test error")):
                    # Mock sys.exit to avoid test termination
                    with patch("sys.exit") as mock_exit:
                        # Call export_config
                        export_config(args)

                        # Verify logger was called with the expected error message
                        mock_logger.error.assert_called_once()
                        assert "Failed to export configuration" in mock_logger.error.call_args[0][0]

                        # Verify sys.exit was called with exit code 1
                        mock_exit.assert_called_once_with(1)


def test_import_config_success(config_manager, temp_dir):
    """Test importing configuration successfully."""
    # Create test configuration data
    config_data = {
        "identity_file": "~/.ssh/id_rsa",
        "keys": {
            "github": "~/.ssh/github_key"
        }
    }

    # Create input file path
    input_file = os.path.join(temp_dir, "config_import.json")

    # Write test configuration to file
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)

    # Mock ConfigManager.import_config to return True
    with patch.object(ConfigManager, "import_config", return_value=True):
        # Create mock ConfigManager instance
        with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
            # Create mock arguments
            args = Args(input=input_file)

            # Mock logger
            with patch("persistent_ssh_agent.cli.logger") as mock_logger:
                # Call import_config
                import_config(args)

                # Verify logger was called with the expected message
                mock_logger.info.assert_called_once_with("Configuration imported successfully")


def test_import_config_file_error(config_manager):
    """Test importing configuration with file error."""
    # Create mock ConfigManager instance
    with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
        # Create mock arguments
        args = Args(input="/invalid/path/config.json")

        # Mock logger
        with patch("persistent_ssh_agent.cli.logger") as mock_logger:
            # Mock open to raise IOError
            mock_open_func = mock_open()
            mock_open_func.side_effect = IOError("Test error")
            with patch("builtins.open", mock_open_func):
                # Mock json.load to avoid UnboundLocalError
                with patch("json.load", return_value={}):
                    # Mock sys.exit to avoid test termination
                    with patch("sys.exit") as mock_exit:
                        # Call import_config
                        import_config(args)

                        # Verify logger was called with the expected error message
                        assert any("Failed to import configuration" in call[0][0]
                                   for call in mock_logger.error.call_args_list)

                        # Verify sys.exit was called with exit code 1
                        assert mock_exit.call_count >= 1
                        assert mock_exit.call_args_list[0][0][0] == 1


def test_import_config_json_error(config_manager):
    """Test importing configuration with JSON error."""
    # Create mock ConfigManager instance
    with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
        # Create mock arguments
        args = Args(input="config.json")

        # Mock logger
        with patch("persistent_ssh_agent.cli.logger") as mock_logger:
            # Mock open to return invalid JSON
            mock_open_func = mock_open(read_data="invalid json")
            with patch("builtins.open", mock_open_func):
                # Mock json.load to raise JSONDecodeError
                json_error = json.JSONDecodeError("Test error", "", 0)
                with patch("json.load", side_effect=json_error):
                    # Mock sys.exit to avoid test termination
                    with patch("sys.exit") as mock_exit:
                        # Call import_config
                        import_config(args)

                        # Verify logger was called with the expected error message
                        assert any("Failed to import configuration" in call[0][0]
                                   for call in mock_logger.error.call_args_list)

                        # Verify sys.exit was called with exit code 1
                        assert mock_exit.call_count >= 1
                        assert mock_exit.call_args_list[0][0][0] == 1


def test_import_config_import_error(config_manager):
    """Test importing configuration with import error."""
    # Create test configuration data
    config_data = {
        "identity_file": "~/.ssh/id_rsa"
    }

    # Create mock ConfigManager instance
    with patch("persistent_ssh_agent.cli.ConfigManager", return_value=config_manager):
        # Create mock arguments
        args = Args(input="config.json")

        # Mock logger
        with patch("persistent_ssh_agent.cli.logger") as mock_logger:
            # Mock open to return valid JSON
            with patch("builtins.open", mock_open(read_data=json.dumps(config_data))):
                # Mock json.load to return our test data
                with patch("json.load", return_value=config_data):
                    # Mock ConfigManager.import_config to return False
                    with patch.object(ConfigManager, "import_config", return_value=False):
                        # Mock sys.exit to avoid test termination
                        with patch("sys.exit") as mock_exit:
                            # Call import_config
                            import_config(args)

                            # Verify logger was called with the expected error message
                            assert any("Failed to import configuration" == call[0][0]
                                       for call in mock_logger.error.call_args_list)

                            # Verify sys.exit was called with exit code 1
                            assert mock_exit.call_count >= 1
                            assert mock_exit.call_args_list[0][0][0] == 1
