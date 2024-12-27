"""Tests for SSH key management functionality."""

# Import built-in modules
import os
from pathlib import Path
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent
import pytest


@pytest.fixture
def ssh_manager():
    """Create a PersistentSSHAgent instance."""
    return PersistentSSHAgent()


def test_get_available_keys(ssh_manager, tmp_path):
    """Test detection of available SSH keys."""
    # Create mock .ssh directory
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Create various key pairs
    key_pairs = {
        "id_ed25519": "ED25519 KEY",
        "id_rsa": "RSA KEY",
        "id_ecdsa": "ECDSA KEY",
        "id_dsa": "DSA KEY"
    }

    for key_name, content in key_pairs.items():
        # Create private key
        key_file = ssh_dir / key_name
        key_file.write_text(content)
        # Create public key
        pub_key = ssh_dir / f"{key_name}.pub"
        pub_key.write_text(f"{content}.pub")

    # Create a key without public key (should be ignored)
    invalid_key = ssh_dir / "id_invalid"
    invalid_key.write_text("INVALID KEY")

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        available_keys = ssh_manager._get_available_keys()

        # Check if keys are found in correct order
        expected_ed25519_path = str(ssh_dir / "id_ed25519").replace("\\", "/")
        expected_ecdsa_path = str(ssh_dir / "id_ecdsa").replace("\\", "/")
        expected_rsa_path = str(ssh_dir / "id_rsa").replace("\\", "/")
        expected_dsa_path = str(ssh_dir / "id_dsa").replace("\\", "/")

        assert expected_ed25519_path in available_keys
        assert expected_ecdsa_path in available_keys
        assert expected_rsa_path in available_keys
        assert expected_dsa_path in available_keys

        # Check if order matches SSH_KEY_TYPES preference
        key_positions = {key: available_keys.index(key) for key in available_keys}
        assert key_positions[expected_ed25519_path] < key_positions[expected_rsa_path]  # Ed25519 should be preferred over RSA


def test_get_available_keys_empty_dir(ssh_manager, tmp_path):
    """Test key detection with empty .ssh directory."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        available_keys = ssh_manager._get_available_keys()
        assert len(available_keys) == 0


def test_get_available_keys_error_handling(ssh_manager):
    """Test error handling during key detection."""
    with patch.object(ssh_manager, "_ssh_dir", Path("/nonexistent/path")):
        available_keys = ssh_manager._get_available_keys()
        assert isinstance(available_keys, list)
        assert len(available_keys) == 0


def test_get_identity_file_with_multiple_keys(ssh_manager, tmp_path):
    """Test identity file selection with multiple available keys."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Create multiple key pairs
    key_pairs = {
        "id_ed25519": "ED25519 KEY",
        "id_rsa": "RSA KEY"
    }

    for key_name, content in key_pairs.items():
        key_file = ssh_dir / key_name
        key_file.write_text(content)
        pub_key = ssh_dir / f"{key_name}.pub"
        pub_key.write_text(f"{content}.pub")

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        identity_file = ssh_manager._get_identity_file("example.com")
        assert identity_file is not None
        assert Path(identity_file).name == "id_ed25519"  # Should prefer Ed25519


def test_get_identity_file_fallback_behavior(ssh_manager, tmp_path):
    """Test identity file fallback behavior when no keys are available."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        identity_file = ssh_manager._get_identity_file("example.com")
        assert identity_file is not None
        assert Path(identity_file).name == "id_rsa"  # Default key should be id_rsa


def test_get_identity_file_config_priority(ssh_manager, tmp_path):
    """Test that configured identity file takes priority over discovered keys."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Create a key pair
    key_file = ssh_dir / "id_ed25519"
    key_file.write_text("ED25519 KEY")
    pub_key = ssh_dir / "id_ed25519.pub"
    pub_key.write_text("ED25519 KEY.pub")

    # Set environment variable
    with patch.dict(os.environ, {"SSH_IDENTITY_FILE": str(key_file)}), \
         patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        identity_file = ssh_manager._get_identity_file("example.com")
        assert identity_file == str(key_file)


def test_security_key_detection(ssh_manager, tmp_path):
    """Test detection of security keys (FIDO/U2F)."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Create security key pairs
    security_keys = {
        "id_ecdsa_sk": "ECDSA-SK KEY",
        "id_ed25519_sk": "ED25519-SK KEY"
    }

    for key_name, content in security_keys.items():
        key_file = ssh_dir / key_name
        key_file.write_text(content)
        pub_key = ssh_dir / f"{key_name}.pub"
        pub_key.write_text(f"{content}.pub")

    with patch.object(ssh_manager, "_ssh_dir", ssh_dir):
        available_keys = ssh_manager._get_available_keys()
        expected_ecdsa_sk_path = str(ssh_dir / "id_ecdsa_sk").replace("\\", "/")
        expected_ed25519_sk_path = str(ssh_dir / "id_ed25519_sk").replace("\\", "/")

        assert expected_ecdsa_sk_path in available_keys
        assert expected_ed25519_sk_path in available_keys
