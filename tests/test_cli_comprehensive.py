"""Comprehensive tests for CLI module to improve coverage."""

# Import built-in modules
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.cli import ConfigManager
from persistent_ssh_agent.constants import CLIConstants
from persistent_ssh_agent.constants import SystemConstants
import pytest


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def config_manager(temp_config_dir):
    """Create a ConfigManager instance with temporary directory."""
    manager = ConfigManager()
    manager.config_dir = temp_config_dir
    manager.config_file = temp_config_dir / CLIConstants.CONFIG_FILE_NAME
    return manager


class TestConfigManagerInitialization:
    """Test ConfigManager initialization and setup."""

    def test_config_manager_init(self):
        """Test ConfigManager initialization."""
        manager = ConfigManager()
        
        assert manager.config_dir.name == CLIConstants.CONFIG_DIR_NAME
        assert manager.config_file.name == CLIConstants.CONFIG_FILE_NAME

    def test_ensure_config_dir_creation(self, temp_config_dir):
        """Test config directory creation."""
        config_dir = temp_config_dir / "new_config"
        config_file = config_dir / CLIConstants.CONFIG_FILE_NAME
        
        manager = ConfigManager()
        manager.config_dir = config_dir
        manager.config_file = config_file
        
        # Directory should be created when _ensure_config_dir is called
        manager._ensure_config_dir()
        assert config_dir.exists()

    def test_ensure_config_dir_permissions_unix(self, config_manager):
        """Test config directory permissions on Unix systems."""
        with patch("os.name", "posix"), \
             patch("os.chmod") as mock_chmod:
            
            config_manager._ensure_config_dir()
            
            mock_chmod.assert_called_once_with(
                config_manager.config_dir, 
                CLIConstants.CONFIG_DIR_PERMISSIONS
            )

    def test_ensure_config_dir_permissions_windows(self, config_manager):
        """Test config directory permissions on Windows (should skip chmod)."""
        with patch("os.name", SystemConstants.WINDOWS_PLATFORM), \
             patch("os.chmod") as mock_chmod:
            
            config_manager._ensure_config_dir()
            
            # chmod should not be called on Windows
            mock_chmod.assert_not_called()


class TestConfigManagerLoadSave:
    """Test configuration loading and saving."""

    def test_load_config_nonexistent_file(self, config_manager):
        """Test loading config when file doesn't exist."""
        result = config_manager.load_config()
        assert result == {}

    def test_load_config_success(self, config_manager):
        """Test successful config loading."""
        test_config = {"test_key": "test_value"}
        config_manager.config_file.write_text(json.dumps(test_config))
        
        result = config_manager.load_config()
        assert result == test_config

    def test_load_config_json_decode_error(self, config_manager):
        """Test config loading with invalid JSON."""
        config_manager.config_file.write_text("invalid json")
        
        result = config_manager.load_config()
        assert result == {}

    def test_load_config_io_error(self, config_manager):
        """Test config loading with IO error."""
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = IOError("Permission denied")
            
            result = config_manager.load_config()
            assert result == {}

    def test_save_config_success(self, config_manager):
        """Test successful config saving."""
        test_config = {"test_key": "test_value"}
        
        result = config_manager.save_config(test_config)
        
        assert result
        assert config_manager.config_file.exists()
        
        # Verify content
        saved_config = json.loads(config_manager.config_file.read_text())
        assert saved_config == test_config

    def test_save_config_permissions_unix(self, config_manager):
        """Test config file permissions on Unix systems."""
        with patch("os.name", "posix"), \
             patch("os.chmod") as mock_chmod:
            
            test_config = {"test_key": "test_value"}
            config_manager.save_config(test_config)
            
            mock_chmod.assert_called_once_with(
                config_manager.config_file,
                CLIConstants.CONFIG_FILE_PERMISSIONS
            )

    def test_save_config_permissions_windows(self, config_manager):
        """Test config file permissions on Windows (should skip chmod)."""
        with patch("os.name", SystemConstants.WINDOWS_PLATFORM), \
             patch("os.chmod") as mock_chmod:
            
            test_config = {"test_key": "test_value"}
            config_manager.save_config(test_config)
            
            # chmod should not be called on Windows
            mock_chmod.assert_not_called()

    def test_save_config_io_error(self, config_manager):
        """Test config saving with IO error."""
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = IOError("Permission denied")
            
            result = config_manager.save_config({"test": "value"})
            assert not result


class TestConfigManagerGetSetValues:
    """Test configuration value getting and setting."""

    def test_get_config_value_existing(self, config_manager):
        """Test getting existing config value."""
        test_config = {"existing_key": "existing_value"}
        config_manager.config_file.write_text(json.dumps(test_config))
        
        result = config_manager._get_config_value("existing_key")
        assert result == "existing_value"

    def test_get_config_value_nonexistent(self, config_manager):
        """Test getting non-existent config value."""
        result = config_manager._get_config_value("nonexistent_key")
        assert result is None

    def test_set_config_value_success(self, config_manager):
        """Test setting config value."""
        result = config_manager._set_config_value("new_key", "new_value")
        
        assert result
        
        # Verify value was saved
        saved_config = json.loads(config_manager.config_file.read_text())
        assert saved_config["new_key"] == "new_value"

    def test_set_config_value_update_existing(self, config_manager):
        """Test updating existing config value."""
        # Set initial config
        initial_config = {"existing_key": "old_value"}
        config_manager.save_config(initial_config)
        
        # Update value
        result = config_manager._set_config_value("existing_key", "new_value")
        
        assert result
        
        # Verify value was updated
        saved_config = json.loads(config_manager.config_file.read_text())
        assert saved_config["existing_key"] == "new_value"


class TestConfigManagerSpecificMethods:
    """Test specific configuration methods."""

    def test_get_set_passphrase(self, config_manager):
        """Test passphrase getting and setting."""
        # Test getting non-existent passphrase
        assert config_manager.get_passphrase() is None
        
        # Test setting passphrase (should be encrypted)
        result = config_manager.set_passphrase("secret_password")
        assert result
        
        # Test getting passphrase (should return encrypted value)
        stored_passphrase = config_manager.get_passphrase()
        assert stored_passphrase is not None
        assert stored_passphrase != "secret_password"  # Should be encrypted

    def test_get_set_identity_file(self, config_manager):
        """Test identity file getting and setting."""
        # Test getting non-existent identity file
        assert config_manager.get_identity_file() is None
        
        # Test setting identity file
        test_path = "~/.ssh/id_rsa"
        result = config_manager.set_identity_file(test_path)
        assert result
        
        # Test getting identity file (should be expanded)
        stored_path = config_manager.get_identity_file()
        assert stored_path is not None
        assert "~" not in stored_path  # Should be expanded

    def test_get_set_expiration_time(self, config_manager):
        """Test expiration time getting and setting."""
        # Test getting non-existent expiration time
        assert config_manager.get_expiration_time() is None
        
        # Test setting expiration time (in hours)
        result = config_manager.set_expiration_time(24)
        assert result
        
        # Test getting expiration time (should be in seconds)
        stored_time = config_manager.get_expiration_time()
        assert stored_time == 24 * CLIConstants.SECONDS_PER_HOUR

    def test_get_set_reuse_agent(self, config_manager):
        """Test reuse agent getting and setting."""
        # Test getting non-existent reuse agent setting
        assert config_manager.get_reuse_agent() is None
        
        # Test setting reuse agent
        result = config_manager.set_reuse_agent(True)
        assert result
        
        # Test getting reuse agent
        stored_setting = config_manager.get_reuse_agent()
        assert stored_setting is True


class TestConfigManagerKeyManagement:
    """Test key management methods."""

    def test_list_keys_empty(self, config_manager):
        """Test listing keys when none are configured."""
        result = config_manager.list_keys()
        assert result == {}

    def test_list_keys_with_default(self, config_manager):
        """Test listing keys with default key configured."""
        config_manager.set_identity_file("/path/to/default/key")
        
        result = config_manager.list_keys()
        assert CLIConstants.DEFAULT_KEY_NAME in result
        assert "/path/to/default/key" in result[CLIConstants.DEFAULT_KEY_NAME]

    def test_list_keys_with_named_keys(self, config_manager):
        """Test listing keys with named keys configured."""
        # Set up config with named keys
        config = {
            CLIConstants.CONFIG_KEY_KEYS: {
                "work": "/path/to/work/key",
                "personal": "/path/to/personal/key"
            }
        }
        config_manager.save_config(config)
        
        result = config_manager.list_keys()
        assert "work" in result
        assert "personal" in result
        assert result["work"] == "/path/to/work/key"
        assert result["personal"] == "/path/to/personal/key"

    def test_add_key_default(self, config_manager):
        """Test adding default key."""
        result = config_manager.add_key(CLIConstants.DEFAULT_KEY_NAME, "/path/to/key")
        assert result
        
        # Should be stored as identity_file
        stored_identity = config_manager.get_identity_file()
        assert "/path/to/key" in stored_identity

    def test_add_key_named(self, config_manager):
        """Test adding named key."""
        result = config_manager.add_key("work", "/path/to/work/key")
        assert result
        
        # Verify key was added
        keys = config_manager.list_keys()
        assert "work" in keys
        assert "/path/to/work/key" in keys["work"]

    def test_remove_key_default(self, config_manager):
        """Test removing default key."""
        # Set up default key
        config_manager.set_identity_file("/path/to/key")
        
        result = config_manager.remove_key(CLIConstants.DEFAULT_KEY_NAME)
        assert result
        
        # Verify key was removed
        assert config_manager.get_identity_file() is None

    def test_remove_key_named(self, config_manager):
        """Test removing named key."""
        # Set up named key
        config_manager.add_key("work", "/path/to/work/key")
        
        result = config_manager.remove_key("work")
        assert result
        
        # Verify key was removed
        keys = config_manager.list_keys()
        assert "work" not in keys

    def test_remove_key_nonexistent(self, config_manager):
        """Test removing non-existent key."""
        result = config_manager.remove_key("nonexistent")
        assert not result

    def test_clear_config(self, config_manager):
        """Test clearing all configuration."""
        # Set up some config
        config_manager.set_identity_file("/path/to/key")
        config_manager.set_reuse_agent(True)
        
        result = config_manager.clear_config()
        assert result
        
        # Verify config was cleared
        config = config_manager.load_config()
        assert config == {}


class TestConfigManagerEncryption:
    """Test encryption and decryption functionality."""

    def test_derive_key_from_system(self, config_manager):
        """Test system key derivation."""
        key, salt = config_manager._derive_key_from_system()

        assert len(key) == CLIConstants.KEY_SIZE
        assert len(salt) == CLIConstants.SALT_SIZE
        assert isinstance(key, bytes)
        assert isinstance(salt, bytes)

    def test_derive_key_consistency(self, config_manager):
        """Test that key derivation is consistent."""
        key1, salt1 = config_manager._derive_key_from_system()
        key2, salt2 = config_manager._derive_key_from_system()

        # Should be consistent for same system
        assert key1 == key2
        assert salt1 == salt2

    def test_get_username_methods(self, config_manager):
        """Test different username retrieval methods."""
        # Test with os.getlogin() working
        with patch("os.getlogin", return_value="test_user"):
            username = config_manager._get_username()
            assert username == "test_user"

        # Test with os.getlogin() failing, getpass.getuser() working
        with patch("os.getlogin", side_effect=OSError), \
             patch("getpass.getuser", return_value="getpass_user"):
            username = config_manager._get_username()
            assert username == "getpass_user"

        # Test with both failing, using environment variables
        with patch("os.getlogin", side_effect=OSError), \
             patch("getpass.getuser", side_effect=Exception), \
             patch.dict(os.environ, {SystemConstants.ENV_USER: "env_user"}):
            username = config_manager._get_username()
            assert username == "env_user"

        # Test with USER not set, using USERNAME
        with patch("os.getlogin", side_effect=OSError), \
             patch("getpass.getuser", side_effect=Exception), \
             patch.dict(os.environ, {SystemConstants.ENV_USERNAME: "username_user"}, clear=True):
            username = config_manager._get_username()
            assert username == "username_user"

        # Test with all methods failing
        with patch("os.getlogin", side_effect=OSError), \
             patch("getpass.getuser", side_effect=Exception), \
             patch.dict(os.environ, {}, clear=True):
            username = config_manager._get_username()
            assert username == SystemConstants.UNKNOWN_USER

    def test_get_machine_id_linux(self, config_manager):
        """Test machine ID retrieval on Linux."""
        test_machine_id = "test-machine-id-12345"

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=f"{test_machine_id}\n")):
            machine_id = config_manager._get_machine_id()
            assert machine_id == test_machine_id

    def test_get_machine_id_windows(self, config_manager):
        """Test machine ID retrieval on Windows."""
        test_guid = "12345678-1234-1234-1234-123456789012"

        with patch("os.path.exists", return_value=False), \
             patch("os.name", SystemConstants.WINDOWS_PLATFORM):

            # Mock winreg module
            mock_winreg = MagicMock()
            mock_key = MagicMock()
            mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
            mock_winreg.QueryValueEx.return_value = (test_guid, None)

            with patch.dict("sys.modules", {"winreg": mock_winreg}):
                machine_id = config_manager._get_machine_id()
                assert machine_id == test_guid

    def test_get_machine_id_fallback(self, config_manager):
        """Test machine ID fallback to hostname hash."""
        test_hostname = "test-hostname"

        with patch("os.path.exists", return_value=False), \
             patch("os.name", "other"), \
             patch("socket.gethostname", return_value=test_hostname):

            machine_id = config_manager._get_machine_id()
            expected_hash = hashlib.sha256(test_hostname.encode()).hexdigest()
            assert machine_id == expected_hash

    def test_encrypt_decrypt_passphrase(self, config_manager):
        """Test passphrase encryption and decryption."""
        original_passphrase = "my_secret_password"

        # Encrypt passphrase
        encrypted = config_manager._encrypt_passphrase(original_passphrase)
        assert encrypted != original_passphrase
        assert isinstance(encrypted, str)

        # Decrypt passphrase
        decrypted = config_manager.deobfuscate_passphrase(encrypted)
        assert decrypted == original_passphrase

    def test_encrypt_passphrase_error_handling(self, config_manager):
        """Test encryption error handling."""
        with patch.object(config_manager, "_derive_key_from_system", side_effect=Exception("Key error")):
            with pytest.raises(Exception, match="Key error"):
                config_manager._encrypt_passphrase("test")

    def test_decrypt_passphrase_error_handling(self, config_manager):
        """Test decryption error handling."""
        # Test with invalid base64 data that will cause decryption to fail
        with pytest.raises(Exception, match="Incorrect padding|Invalid base64|Key error"):
            config_manager.deobfuscate_passphrase("invalid_data")

    def test_pad_unpad_data(self, config_manager):
        """Test data padding and unpadding."""
        test_data = b"Hello, World!"

        # Pad data
        padded = config_manager._pad_data(test_data)
        assert len(padded) % CLIConstants.AES_BLOCK_SIZE == 0
        assert len(padded) >= len(test_data)

        # Unpad data
        unpadded = config_manager._unpad_data(padded)
        assert unpadded == test_data

    def test_pad_data_exact_block_size(self, config_manager):
        """Test padding data that's exactly block size."""
        # Create data that's exactly one block size
        test_data = b"A" * CLIConstants.AES_BLOCK_SIZE

        padded = config_manager._pad_data(test_data)
        # Should add another full block of padding
        assert len(padded) == CLIConstants.AES_BLOCK_SIZE * 2

        unpadded = config_manager._unpad_data(padded)
        assert unpadded == test_data


class TestConfigManagerExportImport:
    """Test configuration export and import functionality."""

    def test_export_config_non_sensitive(self, config_manager):
        """Test exporting non-sensitive configuration."""
        # Set up test config
        config_manager.set_identity_file("/path/to/key")
        config_manager.set_expiration_time(12)
        config_manager.set_reuse_agent(False)
        config_manager.set_passphrase("secret")  # Sensitive data

        exported = config_manager.export_config(include_sensitive=False)

        # Should include non-sensitive data
        assert CLIConstants.CONFIG_KEY_IDENTITY_FILE in exported
        assert CLIConstants.CONFIG_KEY_EXPIRATION_TIME in exported
        assert CLIConstants.CONFIG_KEY_REUSE_AGENT in exported

        # Should not include sensitive data
        assert CLIConstants.CONFIG_KEY_PASSPHRASE not in exported

    def test_export_config_with_sensitive(self, config_manager):
        """Test exporting configuration with sensitive data."""
        # Set up test config
        config_manager.set_identity_file("/path/to/key")
        config_manager.set_passphrase("secret")

        exported = config_manager.export_config(include_sensitive=True)

        # Should include both non-sensitive and sensitive data
        assert CLIConstants.CONFIG_KEY_IDENTITY_FILE in exported
        assert CLIConstants.CONFIG_KEY_PASSPHRASE in exported

    def test_export_config_empty(self, config_manager):
        """Test exporting empty configuration."""
        exported = config_manager.export_config()
        assert exported == {}

    def test_import_config_success(self, config_manager):
        """Test successful configuration import."""
        import_data = {
            CLIConstants.CONFIG_KEY_IDENTITY_FILE: "/imported/key",
            CLIConstants.CONFIG_KEY_EXPIRATION_TIME: 7200,
            CLIConstants.CONFIG_KEY_REUSE_AGENT: True
        }

        result = config_manager.import_config(import_data)
        assert result

        # Verify imported data
        assert config_manager.get_identity_file() == "/imported/key"
        assert config_manager.get_expiration_time() == 7200
        assert config_manager.get_reuse_agent() is True

    def test_import_config_invalid_data(self, config_manager):
        """Test importing invalid configuration data."""
        result = config_manager.import_config("not a dictionary")
        assert not result

    def test_import_config_merge_with_existing(self, config_manager):
        """Test importing config merges with existing data."""
        # Set up existing config
        config_manager.set_identity_file("/existing/key")
        config_manager.set_reuse_agent(False)

        # Import new data
        import_data = {
            CLIConstants.CONFIG_KEY_EXPIRATION_TIME: 3600,
            CLIConstants.CONFIG_KEY_REUSE_AGENT: True  # Should override existing
        }

        result = config_manager.import_config(import_data)
        assert result

        # Verify merge results
        assert config_manager.get_identity_file() == "/existing/key"  # Preserved
        assert config_manager.get_expiration_time() == 3600  # Added
        assert config_manager.get_reuse_agent() is True  # Overridden
