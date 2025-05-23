#!/usr/bin/env python3
"""
Test utilities for cross-platform testing.

This module provides utilities to handle cross-platform testing issues,
particularly for SSH-related functionality.
"""

# Import built-in modules
import os
from pathlib import Path
import sys
from typing import List
from typing import Optional
from typing import Tuple
from unittest.mock import MagicMock
from unittest.mock import patch


def normalize_path(path: str) -> str:
    """Normalize path for cross-platform comparison.

    Args:
        path: Path to normalize

    Returns:
        str: Normalized path with forward slashes
    """
    return str(Path(path)).replace("\\", "/")


def create_mock_subprocess_popen(returncode: int = 0,
                                stdout: str = "",
                                stderr: str = "",
                                side_effect: Optional[Exception] = None) -> MagicMock:
    """Create a mock subprocess.Popen object.

    Args:
        returncode: Process return code
        stdout: Process stdout
        stderr: Process stderr
        side_effect: Exception to raise

    Returns:
        MagicMock: Mock Popen object
    """
    mock_process = MagicMock()
    mock_process.returncode = returncode
    mock_process.communicate.return_value = (stdout, stderr)
    mock_process.poll.return_value = returncode

    if side_effect:
        mock_process.communicate.side_effect = side_effect

    return mock_process


def mock_ssh_commands():
    """Context manager to mock SSH commands across platforms.

    This mocks subprocess.Popen to avoid platform-specific SSH command issues.
    """
    def mock_popen_factory(*args, **kwargs):
        # Default successful SSH command
        return create_mock_subprocess_popen(returncode=0, stdout="", stderr="")

    return patch("subprocess.Popen", side_effect=mock_popen_factory)


def create_test_ssh_directory(tmp_path: Path,
                             keys: Optional[List[str]] = None,
                             config_content: Optional[str] = None) -> Path:
    """Create a test SSH directory with keys and config.

    Args:
        tmp_path: Temporary directory path
        keys: List of key names to create (without extension)
        config_content: SSH config file content

    Returns:
        Path: SSH directory path
    """
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Create SSH keys
    if keys:
        for key_name in keys:
            # Create private key
            key_file = ssh_dir / key_name
            key_file.write_text(f"{key_name} private key")

            # Create public key
            pub_key = ssh_dir / f"{key_name}.pub"
            pub_key.write_text(f"{key_name} public key")

    # Create SSH config
    if config_content:
        config_file = ssh_dir / "config"
        config_file.write_text(config_content)

    return ssh_dir


def skip_on_platform(platform: str):
    """Decorator to skip tests on specific platforms.

    Args:
        platform: Platform to skip ('windows', 'linux', 'darwin')
    """
    # Import third-party modules
    import pytest

    platform_map = {
        "windows": "win32",
        "linux": "linux",
        "darwin": "darwin"
    }

    current_platform = sys.platform
    skip_platform = platform_map.get(platform, platform)

    return pytest.mark.skipif(
        current_platform.startswith(skip_platform),
        reason=f"Test not supported on {platform}"
    )


def mock_ssh_agent_environment():
    """Mock SSH agent environment variables."""
    return patch.dict(os.environ, {
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
        "SSH_AGENT_PID": "12345"
    })


class MockSSHKeyManager:
    """Mock SSH key manager for testing."""

    def __init__(self, ssh_dir: Path, available_keys: Optional[List[str]] = None):
        self.ssh_dir = ssh_dir
        self.available_keys = available_keys or []

    def get_available_keys(self) -> List[str]:
        """Return mock available keys."""
        return self.available_keys

    def get_identity_from_available_keys(self) -> Optional[str]:
        """Return first available key or None."""
        return self.available_keys[0] if self.available_keys else None

    def try_add_key_without_passphrase(self, identity_file: str) -> Tuple[bool, bool]:
        """Mock try add key without passphrase."""
        return True, False

    def add_key_with_passphrase(self, identity_file: str, passphrase: str) -> bool:
        """Mock add key with passphrase."""
        return True

    def create_ssh_add_process(self, identity_file: str):
        """Mock create SSH add process."""
        return create_mock_subprocess_popen()


def patch_ssh_key_manager(ssh_agent, ssh_dir: Path, available_keys: Optional[List[str]] = None):
    """Patch SSH key manager with mock implementation.

    Args:
        ssh_agent: SSH agent instance to patch
        ssh_dir: SSH directory path
        available_keys: List of available keys

    Returns:
        Context manager for patching
    """
    mock_manager = MockSSHKeyManager(ssh_dir, available_keys)
    return patch.object(ssh_agent, "ssh_key_manager", mock_manager)


def ensure_test_isolation(ssh_agent, tmp_path: Path):
    """Ensure test isolation by patching SSH directory and related components.

    Args:
        ssh_agent: SSH agent instance
        tmp_path: Temporary directory for test

    Returns:
        Context manager for test isolation
    """
    ssh_dir = create_test_ssh_directory(tmp_path)

    # Create patches for all SSH-related components
    patches = [
        patch.object(ssh_agent, "_ssh_dir", ssh_dir),
        patch.object(ssh_agent.ssh_key_manager, "ssh_dir", ssh_dir),
        mock_ssh_commands(),
        mock_ssh_agent_environment()
    ]

    # Stack all patches
    # Import built-in modules
    from contextlib import ExitStack
    return ExitStack().enter_context(*patches)


# Platform detection utilities
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Common test constants
DEFAULT_SSH_KEYS = ["id_ed25519", "id_rsa", "id_ecdsa"]
TEST_SSH_CONFIG = """Host github.com
    IdentityFile ~/.ssh/github_key
    User git

Host *.gitlab.com
    IdentityFile ~/.ssh/gitlab_key
    User git
"""
