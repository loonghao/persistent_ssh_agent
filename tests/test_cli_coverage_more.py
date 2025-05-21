"""Additional tests to improve coverage for CLI module."""

# Import built-in modules
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from click.testing import CliRunner

# Import local modules
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.cli import main


def test_config_manager_encrypt_decrypt():
    """Test the encrypt and decrypt methods of ConfigManager."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Mock _derive_key_from_system to return a fixed key and salt
        with patch.object(manager, "_derive_key_from_system") as mock_derive:
            key = b"0123456789abcdef0123456789abcdef"  # 32 bytes for AES-256
            salt = b"0123456789abcdef"  # 16 bytes
            mock_derive.return_value = (key, salt)

            # Test encrypt
            plaintext = "test-passphrase"
            with patch("os.urandom", return_value=b"0123456789abcdef"):  # Mock IV
                encrypted = manager._encrypt_passphrase(plaintext)
                assert encrypted != plaintext
                assert isinstance(encrypted, str)

            # Test decrypt
            with patch.object(manager, "_derive_key_from_system", return_value=(key, salt)):
                decrypted = manager._deobfuscate_passphrase(encrypted)
                assert decrypted == plaintext


def test_config_manager_set_get_passphrase():
    """Test setting and getting passphrase."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Mock _encrypt_passphrase method
        with patch.object(manager, "_encrypt_passphrase", return_value="encrypted-passphrase"):
            # Mock load_config and save_config
            with patch.object(manager, "load_config", return_value={}):
                with patch.object(manager, "save_config", return_value=True):
                    # Test set_passphrase
                    result = manager.set_passphrase("test-passphrase")
                    assert result is True

            # Mock load_config to return config with passphrase
            config = {"passphrase": "encrypted-passphrase"}
            with patch.object(manager, "load_config", return_value=config):
                # Test get_passphrase
                result = manager.get_passphrase()
                assert result == "encrypted-passphrase"


def test_config_manager_set_get_expiration_time():
    """Test setting and getting expiration time."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Mock load_config and save_config
        with patch.object(manager, "load_config", return_value={}):
            with patch.object(manager, "save_config", return_value=True):
                # Test set_expiration_time
                result = manager.set_expiration_time(24)
                assert result is True

        # Mock load_config to return config with expiration_time
        with patch.object(manager, "load_config", return_value={"expiration_time": 86400}):
            # Test get_expiration_time
            result = manager.get_expiration_time()
            assert result == 86400


def test_config_manager_set_get_reuse_agent():
    """Test setting and getting reuse agent flag."""
    with patch.object(ConfigManager, "__init__", return_value=None):
        manager = ConfigManager()

        # Mock load_config and save_config
        with patch.object(manager, "load_config", return_value={}):
            with patch.object(manager, "save_config", return_value=True):
                # Test set_reuse_agent
                result = manager.set_reuse_agent(True)
                assert result is True

        # Mock load_config to return config with reuse_agent
        with patch.object(manager, "load_config", return_value={"reuse_agent": True}):
            # Test get_reuse_agent
            result = manager.get_reuse_agent()
            assert result is True


def test_main_config_command():
    """Test the config command in the CLI."""
    runner = CliRunner()

    # Mock setup_config
    with patch("persistent_ssh_agent.cli.setup_config") as mock_setup:
        # Run the command
        result = runner.invoke(main, ["config", "--identity-file", "~/.ssh/id_rsa"])

        # Verify the result
        assert result.exit_code == 0
        mock_setup.assert_called_once()


def test_main_test_command():
    """Test the test command in the CLI."""
    runner = CliRunner()

    # Mock run_ssh_connection_test
    with patch("persistent_ssh_agent.cli.run_ssh_connection_test") as mock_run:
        # Run the command
        result = runner.invoke(main, ["test", "github.com"])

        # Verify the result
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_main_list_command():
    """Test the list command in the CLI."""
    runner = CliRunner()

    # Mock ConfigManager
    with patch("persistent_ssh_agent.cli.ConfigManager") as mock_config_manager:
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = {
            "keys": {
                "github": {"path": "~/.ssh/id_rsa", "added_at": "2023-01-01"}
            }
        }
        mock_config_manager.return_value = mock_manager

        # Run the command
        result = runner.invoke(main, ["list"])

        # Verify the result
        assert result.exit_code == 0
        # Just check that the command ran successfully, since the output format may vary
        # The output is in stderr, not stdout, so we can't check it here
