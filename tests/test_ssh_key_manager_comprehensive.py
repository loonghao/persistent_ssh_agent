"""Comprehensive tests for SSH key manager to improve coverage."""

# Import built-in modules
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.ssh_key_manager import SSHKeyManager
import pytest


@pytest.fixture
def temp_ssh_dir():
    """Create a temporary SSH directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def ssh_key_manager(temp_ssh_dir):
    """Create an SSHKeyManager instance for testing."""
    ssh_key_types = ["id_ed25519", "id_ecdsa", "id_rsa", "id_dsa"]
    return SSHKeyManager(temp_ssh_dir, ssh_key_types)


class TestSSHKeyManagerGetAvailableKeys:
    """Test get_available_keys method comprehensively."""

    def test_get_available_keys_with_numbered_keys(self, ssh_key_manager, temp_ssh_dir):
        """Test detection of numbered SSH keys (e.g., id_rsa2, id_rsa3)."""
        # Create numbered key pairs
        for i in range(1, 4):
            key_name = f"id_rsa{i}"
            key_file = temp_ssh_dir / key_name
            pub_file = temp_ssh_dir / f"{key_name}.pub"
            key_file.write_text(f"RSA KEY {i}")
            pub_file.write_text(f"RSA KEY {i} PUBLIC")

        available_keys = ssh_key_manager.get_available_keys()
        
        # Should find all numbered keys
        assert len(available_keys) == 3
        for i in range(1, 4):
            expected_path = str(temp_ssh_dir / f"id_rsa{i}").replace("\\", "/")
            assert expected_path in available_keys

    def test_get_available_keys_mixed_types_and_numbers(self, ssh_key_manager, temp_ssh_dir):
        """Test detection with mixed key types and numbered variants."""
        # Create various key types - only base types and numbered variants are detected
        keys_to_create = [
            "id_ed25519", "id_ecdsa", "id_ecdsa2",
            "id_rsa", "id_rsa2", "id_rsa10", "id_dsa"
        ]

        for key_name in keys_to_create:
            key_file = temp_ssh_dir / key_name
            pub_file = temp_ssh_dir / f"{key_name}.pub"
            key_file.write_text(f"KEY CONTENT {key_name}")
            pub_file.write_text(f"PUBLIC KEY {key_name}")

        available_keys = ssh_key_manager.get_available_keys()

        # Should find all keys
        assert len(available_keys) == len(keys_to_create)

        # Check order preference (ed25519 should come first)
        ed25519_keys = [k for k in available_keys if "ed25519" in k]
        rsa_keys = [k for k in available_keys if "rsa" in k and "ed25519" not in k]

        if ed25519_keys and rsa_keys:
            first_ed25519_idx = available_keys.index(ed25519_keys[0])
            first_rsa_idx = available_keys.index(rsa_keys[0])
            assert first_ed25519_idx < first_rsa_idx

    def test_get_available_keys_missing_public_key(self, ssh_key_manager, temp_ssh_dir):
        """Test that keys without corresponding public keys are ignored."""
        # Create private key without public key
        private_key = temp_ssh_dir / "id_rsa"
        private_key.write_text("RSA PRIVATE KEY")
        
        # Create complete key pair
        complete_private = temp_ssh_dir / "id_ed25519"
        complete_public = temp_ssh_dir / "id_ed25519.pub"
        complete_private.write_text("ED25519 PRIVATE KEY")
        complete_public.write_text("ED25519 PUBLIC KEY")

        available_keys = ssh_key_manager.get_available_keys()
        
        # Should only find the complete key pair
        assert len(available_keys) == 1
        assert "id_ed25519" in available_keys[0]

    def test_get_available_keys_glob_error_handling(self, ssh_key_manager, temp_ssh_dir):
        """Test error handling when glob operations fail."""
        with patch("glob.glob") as mock_glob:
            mock_glob.side_effect = OSError("Permission denied")
            available_keys = ssh_key_manager.get_available_keys()
            assert available_keys == []

    def test_get_available_keys_path_normalization(self, ssh_key_manager, temp_ssh_dir):
        """Test that paths are properly normalized (forward slashes)."""
        # Create a key pair
        key_file = temp_ssh_dir / "id_rsa"
        pub_file = temp_ssh_dir / "id_rsa.pub"
        key_file.write_text("RSA KEY")
        pub_file.write_text("RSA PUBLIC KEY")

        available_keys = ssh_key_manager.get_available_keys()
        
        assert len(available_keys) == 1
        # Path should use forward slashes
        assert "\\" not in available_keys[0]
        assert "/" in str(available_keys[0])


class TestSSHKeyManagerVerifyLoadedKey:
    """Test verify_loaded_key method."""

    def test_verify_loaded_key_success(self, ssh_key_manager):
        """Test successful key verification."""
        with patch("persistent_ssh_agent.ssh_key_manager.run_command") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "2048 SHA256:abc123 /home/user/.ssh/id_rsa (RSA)"
            mock_run.return_value = mock_result

            # The key path should be in the stdout for verification to succeed
            result = ssh_key_manager.verify_loaded_key("/home/user/.ssh/id_rsa")
            assert result is True

    def test_verify_loaded_key_not_found(self, ssh_key_manager):
        """Test key verification when key is not loaded."""
        with patch("persistent_ssh_agent.ssh_key_manager.run_command") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "2048 SHA256:xyz789 /home/user/.ssh/id_ed25519 (ED25519)"
            mock_run.return_value = mock_result

            assert not ssh_key_manager.verify_loaded_key("/home/user/.ssh/id_rsa")

    def test_verify_loaded_key_command_failure(self, ssh_key_manager):
        """Test key verification when ssh-add command fails."""
        with patch("persistent_ssh_agent.ssh_key_manager.run_command") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            assert not ssh_key_manager.verify_loaded_key("/home/user/.ssh/id_rsa")

    def test_verify_loaded_key_no_result(self, ssh_key_manager):
        """Test key verification when run_command returns None."""
        with patch("persistent_ssh_agent.ssh_key_manager.run_command") as mock_run:
            mock_run.return_value = None

            assert not ssh_key_manager.verify_loaded_key("/home/user/.ssh/id_rsa")


class TestSSHKeyManagerCreateSSHAddProcess:
    """Test create_ssh_add_process method."""

    def test_create_ssh_add_process(self, ssh_key_manager):
        """Test SSH add process creation."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process
            
            result = ssh_key_manager.create_ssh_add_process("/path/to/key")
            
            assert result == mock_process
            mock_popen.assert_called_once_with(
                ["ssh-add", "/path/to/key"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )


class TestSSHKeyManagerTryAddKeyWithoutPassphrase:
    """Test try_add_key_without_passphrase method."""

    def test_try_add_key_success(self, ssh_key_manager):
        """Test successful key addition without passphrase."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("", "")
            mock_process.returncode = 0
            mock_create.return_value = mock_process
            
            success, needs_passphrase = ssh_key_manager.try_add_key_without_passphrase("/path/to/key")
            
            assert success
            assert not needs_passphrase

    def test_try_add_key_needs_passphrase(self, ssh_key_manager):
        """Test key addition when passphrase is required."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("", "Enter passphrase for /path/to/key:")
            mock_process.returncode = 1
            mock_create.return_value = mock_process
            
            success, needs_passphrase = ssh_key_manager.try_add_key_without_passphrase("/path/to/key")
            
            assert not success
            assert needs_passphrase

    def test_try_add_key_timeout(self, ssh_key_manager):
        """Test key addition timeout."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.side_effect = subprocess.TimeoutExpired("ssh-add", 1)
            mock_create.return_value = mock_process
            
            success, needs_passphrase = ssh_key_manager.try_add_key_without_passphrase("/path/to/key")
            
            assert not success
            assert needs_passphrase
            mock_process.kill.assert_called_once()

    def test_try_add_key_exception(self, ssh_key_manager):
        """Test key addition with unexpected exception."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.side_effect = Exception("Unexpected error")
            mock_create.return_value = mock_process
            
            success, needs_passphrase = ssh_key_manager.try_add_key_without_passphrase("/path/to/key")
            
            assert not success
            assert not needs_passphrase
            mock_process.kill.assert_called_once()

    def test_try_add_key_bytes_stderr(self, ssh_key_manager):
        """Test key addition with bytes stderr output."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("", b"Enter passphrase for key")
            mock_process.returncode = 1
            mock_create.return_value = mock_process
            
            success, needs_passphrase = ssh_key_manager.try_add_key_without_passphrase("/path/to/key")
            
            assert not success
            assert needs_passphrase


class TestSSHKeyManagerAddKeyWithPassphrase:
    """Test add_key_with_passphrase method."""

    def test_add_key_with_passphrase_success(self, ssh_key_manager):
        """Test successful key addition with passphrase."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("", "")
            mock_process.returncode = 0
            mock_create.return_value = mock_process
            
            result = ssh_key_manager.add_key_with_passphrase("/path/to/key", "secret")
            
            assert result
            mock_process.communicate.assert_called_once_with(input="secret\n", timeout=5)

    def test_add_key_with_passphrase_failure(self, ssh_key_manager):
        """Test failed key addition with passphrase."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("", "Bad passphrase")
            mock_process.returncode = 1
            mock_create.return_value = mock_process
            
            result = ssh_key_manager.add_key_with_passphrase("/path/to/key", "wrong")
            
            assert not result

    def test_add_key_with_passphrase_timeout(self, ssh_key_manager):
        """Test key addition with passphrase timeout."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.side_effect = subprocess.TimeoutExpired("ssh-add", 5)
            mock_create.return_value = mock_process
            
            result = ssh_key_manager.add_key_with_passphrase("/path/to/key", "secret")
            
            assert not result
            mock_process.kill.assert_called_once()

    def test_add_key_with_passphrase_exception(self, ssh_key_manager):
        """Test key addition with passphrase exception."""
        with patch.object(ssh_key_manager, "create_ssh_add_process") as mock_create:
            mock_process = MagicMock()
            mock_process.communicate.side_effect = Exception("Unexpected error")
            mock_create.return_value = mock_process
            
            result = ssh_key_manager.add_key_with_passphrase("/path/to/key", "secret")

            assert not result
            mock_process.kill.assert_called_once()


class TestSSHKeyManagerAddSSHKey:
    """Test add_ssh_key method comprehensively."""

    def test_add_ssh_key_file_not_found(self, ssh_key_manager):
        """Test add_ssh_key with non-existent file."""
        result = ssh_key_manager.add_ssh_key("/nonexistent/key")
        assert not result

    def test_add_ssh_key_success_without_passphrase(self, ssh_key_manager, temp_ssh_dir):
        """Test successful key addition without passphrase."""
        # Create a test key file
        key_file = temp_ssh_dir / "test_key"
        key_file.write_text("TEST KEY CONTENT")

        with patch.object(ssh_key_manager, "try_add_key_without_passphrase") as mock_try_add:
            mock_try_add.return_value = (True, False)

            result = ssh_key_manager.add_ssh_key(str(key_file))
            assert result

    def test_add_ssh_key_with_config_passphrase(self, ssh_key_manager, temp_ssh_dir):
        """Test key addition using passphrase from config."""
        # Create a test key file
        key_file = temp_ssh_dir / "test_key"
        key_file.write_text("TEST KEY CONTENT")

        # Create mock config with passphrase
        mock_config = MagicMock()
        mock_config.identity_passphrase = "config_secret"

        with patch.object(ssh_key_manager, "try_add_key_without_passphrase") as mock_try_add, \
             patch.object(ssh_key_manager, "add_key_with_passphrase") as mock_add_with_pass:

            mock_try_add.return_value = (False, True)  # Needs passphrase
            mock_add_with_pass.return_value = True

            result = ssh_key_manager.add_ssh_key(str(key_file), mock_config)

            assert result
            mock_add_with_pass.assert_called_once_with(str(key_file), "config_secret")

    def test_add_ssh_key_with_cli_passphrase(self, ssh_key_manager, temp_ssh_dir):
        """Test key addition using passphrase from CLI."""
        # Create a test key file
        key_file = temp_ssh_dir / "test_key"
        key_file.write_text("TEST KEY CONTENT")

        with patch.object(ssh_key_manager, "try_add_key_without_passphrase") as mock_try_add, \
             patch.object(ssh_key_manager, "_get_cli_passphrase") as mock_get_cli, \
             patch.object(ssh_key_manager, "add_key_with_passphrase") as mock_add_with_pass:

            mock_try_add.return_value = (False, True)  # Needs passphrase
            mock_get_cli.return_value = "cli_secret"
            mock_add_with_pass.return_value = True

            result = ssh_key_manager.add_ssh_key(str(key_file))

            assert result
            mock_add_with_pass.assert_called_once_with(str(key_file), "cli_secret")

    def test_add_ssh_key_no_passphrase_available(self, ssh_key_manager, temp_ssh_dir):
        """Test key addition when passphrase is needed but not available."""
        # Create a test key file
        key_file = temp_ssh_dir / "test_key"
        key_file.write_text("TEST KEY CONTENT")

        with patch.object(ssh_key_manager, "try_add_key_without_passphrase") as mock_try_add, \
             patch.object(ssh_key_manager, "_get_cli_passphrase") as mock_get_cli:

            mock_try_add.return_value = (False, True)  # Needs passphrase
            mock_get_cli.return_value = None  # No CLI passphrase

            result = ssh_key_manager.add_ssh_key(str(key_file))

            assert not result

    def test_add_ssh_key_exception_handling(self, ssh_key_manager, temp_ssh_dir):
        """Test exception handling in add_ssh_key."""
        # Create a test key file
        key_file = temp_ssh_dir / "test_key"
        key_file.write_text("TEST KEY CONTENT")

        with patch.object(ssh_key_manager, "try_add_key_without_passphrase") as mock_try_add:
            mock_try_add.side_effect = Exception("Unexpected error")

            result = ssh_key_manager.add_ssh_key(str(key_file))
            assert not result

    def test_add_ssh_key_expanduser(self, ssh_key_manager):
        """Test that add_ssh_key properly expands user paths."""
        with patch("os.path.expanduser") as mock_expand, \
             patch("os.path.exists") as mock_exists, \
             patch.object(ssh_key_manager, "try_add_key_without_passphrase") as mock_try_add:

            mock_expand.return_value = "/home/user/.ssh/id_rsa"
            mock_exists.return_value = True
            mock_try_add.return_value = (True, False)

            result = ssh_key_manager.add_ssh_key("~/.ssh/id_rsa")

            assert result
            mock_expand.assert_called_once_with("~/.ssh/id_rsa")


class TestSSHKeyManagerGetCLIPassphrase:
    """Test _get_cli_passphrase method."""

    def test_get_cli_passphrase_success(self, ssh_key_manager):
        """Test successful CLI passphrase retrieval."""
        # Mock the import inside the method
        with patch("builtins.__import__") as mock_import:
            mock_config_manager_class = MagicMock()
            mock_manager = MagicMock()
            mock_manager.get_passphrase.return_value = "encrypted_passphrase"
            mock_manager.deobfuscate_passphrase.return_value = "decrypted_secret"
            mock_config_manager_class.return_value = mock_manager

            # Mock the module import
            mock_cli_module = MagicMock()
            mock_cli_module.ConfigManager = mock_config_manager_class

            def import_side_effect(name, *args, **kwargs):
                if name == "persistent_ssh_agent.cli":
                    return mock_cli_module
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = ssh_key_manager._get_cli_passphrase()

            assert result == "decrypted_secret"

    def test_get_cli_passphrase_import_error(self, ssh_key_manager):
        """Test CLI passphrase retrieval when CLI module is not available."""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            result = ssh_key_manager._get_cli_passphrase()
            assert result is None

    def test_get_cli_passphrase_no_stored_passphrase(self, ssh_key_manager):
        """Test CLI passphrase retrieval when no passphrase is stored."""
        with patch("builtins.__import__") as mock_import:
            mock_config_manager_class = MagicMock()
            mock_manager = MagicMock()
            mock_manager.get_passphrase.return_value = None
            mock_config_manager_class.return_value = mock_manager

            mock_cli_module = MagicMock()
            mock_cli_module.ConfigManager = mock_config_manager_class

            def import_side_effect(name, *args, **kwargs):
                if name == "persistent_ssh_agent.cli":
                    return mock_cli_module
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = ssh_key_manager._get_cli_passphrase()
            assert result is None

    def test_get_cli_passphrase_exception(self, ssh_key_manager):
        """Test CLI passphrase retrieval with exception."""
        with patch("builtins.__import__") as mock_import:
            mock_config_manager_class = MagicMock()
            mock_config_manager_class.side_effect = Exception("Config error")

            mock_cli_module = MagicMock()
            mock_cli_module.ConfigManager = mock_config_manager_class

            def import_side_effect(name, *args, **kwargs):
                if name == "persistent_ssh_agent.cli":
                    return mock_cli_module
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = ssh_key_manager._get_cli_passphrase()
            assert result is None


class TestSSHKeyManagerGetIdentityFromAvailableKeys:
    """Test get_identity_from_available_keys method."""

    def test_get_identity_from_available_keys_success(self, ssh_key_manager):
        """Test successful identity retrieval from available keys."""
        with patch.object(ssh_key_manager, "get_available_keys") as mock_get_keys:
            mock_get_keys.return_value = ["/path/to/id_ed25519", "/path/to/id_rsa"]

            result = ssh_key_manager.get_identity_from_available_keys()

            assert result == "/path/to/id_ed25519"

    def test_get_identity_from_available_keys_no_keys(self, ssh_key_manager):
        """Test identity retrieval when no keys are available."""
        with patch.object(ssh_key_manager, "get_available_keys") as mock_get_keys:
            mock_get_keys.return_value = []

            result = ssh_key_manager.get_identity_from_available_keys()

            assert result is None


class TestSSHKeyManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_ssh_key_manager_initialization(self, temp_ssh_dir):
        """Test SSH key manager initialization."""
        ssh_key_types = ["id_ed25519", "id_rsa"]
        manager = SSHKeyManager(temp_ssh_dir, ssh_key_types)

        assert manager.ssh_dir == temp_ssh_dir
        assert manager.ssh_key_types == ssh_key_types

    def test_get_available_keys_with_special_characters(self, ssh_key_manager, temp_ssh_dir):
        """Test key detection with special characters in filenames."""
        # Create keys with special characters that don't match standard patterns
        special_keys = ["id_rsa-backup", "id_ed25519_work"]

        for key_name in special_keys:
            key_file = temp_ssh_dir / key_name
            pub_file = temp_ssh_dir / f"{key_name}.pub"
            key_file.write_text(f"KEY CONTENT {key_name}")
            pub_file.write_text(f"PUBLIC KEY {key_name}")

        available_keys = ssh_key_manager.get_available_keys()

        # These should not be detected as they don't match the standard patterns
        # (only base key types and numbered variants are detected)
        assert len(available_keys) == 0

    def test_verify_loaded_key_with_empty_stdout(self, ssh_key_manager):
        """Test key verification with empty stdout."""
        with patch("persistent_ssh_agent.utils.run_command") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            assert not ssh_key_manager.verify_loaded_key("/path/to/key")

    def test_create_ssh_add_process_parameters(self, ssh_key_manager):
        """Test that create_ssh_add_process uses correct parameters."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process

            ssh_key_manager.create_ssh_add_process("/test/key")

            # Verify the exact parameters passed to Popen
            mock_popen.assert_called_once_with(
                ["ssh-add", "/test/key"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
