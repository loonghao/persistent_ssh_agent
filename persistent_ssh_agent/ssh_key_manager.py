"""SSH key management functionality."""

# Import built-in modules
import glob
import logging
import os
from pathlib import Path
import subprocess
from typing import List
from typing import Optional
from typing import Tuple

# Import third-party modules
from persistent_ssh_agent.utils import run_command


# Set up logger
logger = logging.getLogger(__name__)


class SSHKeyManager:
    """Manages SSH key operations and discovery."""

    def __init__(self, ssh_dir: Path, ssh_key_types: List[str]):
        """Initialize SSH key manager.

        Args:
            ssh_dir: Path to SSH directory
            ssh_key_types: List of SSH key types in order of preference
        """
        self.ssh_dir = ssh_dir
        self.ssh_key_types = ssh_key_types

    def get_available_keys(self) -> List[str]:
        """Get list of available SSH keys in .ssh directory.

        Returns:
            List[str]: List of available key paths ordered by SSH_KEY_TYPES preference.
        """
        try:
            available_keys = []  # Use list to maintain order
            for key_type in self.ssh_key_types:
                # Check for base key type (e.g., id_rsa)
                key_path = os.path.join(str(self.ssh_dir), key_type)
                pub_key_path = key_path + ".pub"
                if os.path.exists(key_path) and os.path.exists(pub_key_path):
                    normalized_path = str(Path(key_path)).replace("\\", "/")
                    if normalized_path not in available_keys:  # Avoid duplicates
                        available_keys.append(normalized_path)

                # Check for keys with numeric suffixes (e.g., id_rsa2)
                pattern = os.path.join(str(self.ssh_dir), f"{key_type}[0-9]*")
                for numbered_key_path in sorted(glob.glob(pattern)):  # Sort numbered keys
                    pub_key_path = numbered_key_path + ".pub"
                    if os.path.exists(numbered_key_path) and os.path.exists(pub_key_path):
                        normalized_path = str(Path(numbered_key_path)).replace("\\", "/")
                        if normalized_path not in available_keys:  # Avoid duplicates
                            available_keys.append(normalized_path)

            return available_keys  # Return in SSH_KEY_TYPES preference order
        except (OSError, IOError):
            return []

    def resolve_identity_file(self, identity_path: str) -> Optional[str]:
        """Resolve identity file path, handling both absolute and relative paths.

        Args:
            identity_path: Path to identity file, can be absolute or relative

        Returns:
            str: Resolved absolute path if file exists, None otherwise
        """
        try:
            # Expand user directory (e.g., ~/)
            expanded_path = os.path.expanduser(identity_path)

            # If it's a relative path, resolve it relative to SSH directory
            if not os.path.isabs(expanded_path):
                expanded_path = os.path.join(self.ssh_dir, expanded_path)

            # Convert to absolute path
            abs_path = os.path.abspath(expanded_path)

            # Check if file exists
            if not os.path.exists(abs_path):
                return None

            # Convert Windows path to Unix-style for consistency
            return abs_path.replace("\\", "/")

        except (TypeError, ValueError):
            return None

    def verify_loaded_key(self, identity_file: str) -> bool:
        """Verify if a specific key is loaded in the agent.

        Args:
            identity_file: Path to SSH key to verify

        Returns:
            bool: True if key is loaded
        """
        result = run_command(["ssh-add", "-l"])
        return bool(result and result.returncode == 0 and identity_file in result.stdout)

    def create_ssh_add_process(self, identity_file: str) -> subprocess.Popen:
        """Create a subprocess for ssh-add command.

        Args:
            identity_file: Path to SSH key to add

        Returns:
            subprocess.Popen: Process object for ssh-add command
        """
        return subprocess.Popen(
            ["ssh-add", identity_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def try_add_key_without_passphrase(self, identity_file: str) -> Tuple[bool, bool]:
        """Try to add SSH key without passphrase.

        Args:
            identity_file: Path to SSH key

        Returns:
            Tuple[bool, bool]: (success, needs_passphrase)
        """
        process = self.create_ssh_add_process(identity_file)

        try:
            _, stderr = process.communicate(timeout=1)
            if process.returncode == 0:
                logger.debug("Key added without passphrase")
                return True, False
            stderr_str = stderr.decode() if isinstance(stderr, bytes) else stderr
            if "Enter passphrase" in stderr_str:
                return False, True
            logger.error("Failed to add key: %s", stderr_str)
            return False, False
        except subprocess.TimeoutExpired:
            process.kill()
            return False, True
        except Exception as e:
            logger.error("Error adding key: %s", str(e))
            process.kill()
            return False, False

    def add_key_with_passphrase(self, identity_file: str, passphrase: str) -> bool:
        """Add SSH key with passphrase.

        Args:
            identity_file: Path to SSH key
            passphrase: Key passphrase

        Returns:
            bool: True if successful
        """
        process = self.create_ssh_add_process(identity_file)

        try:
            _, stderr = process.communicate(input=f"{passphrase}\n", timeout=5)
            if process.returncode == 0:
                logger.debug("Key added with passphrase")
                return True
            logger.error("Failed to add key with passphrase: %s", stderr)
            return False
        except subprocess.TimeoutExpired:
            logger.error("Timeout while adding key with passphrase")
            process.kill()
            return False
        except Exception as e:
            logger.error("Error adding key with passphrase: %s", str(e))
            process.kill()
            return False

    def add_ssh_key(self, identity_file: str, config=None) -> bool:
        """Add SSH key to the agent.

        Args:
            identity_file: Path to the SSH key to add
            config: SSH configuration object (optional)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate identity file
            identity_file = os.path.expanduser(identity_file)
            if not os.path.exists(identity_file):
                logger.error("Identity file not found: %s", identity_file)
                return False

            # Try adding without passphrase first
            success, needs_passphrase = self.try_add_key_without_passphrase(identity_file)
            if success:
                return True

            # If passphrase is needed, try with configured passphrase
            if needs_passphrase:
                # First check if we have a passphrase in the config
                if config and config.identity_passphrase:
                    logger.debug("Using passphrase from SSHConfig")
                    return self.add_key_with_passphrase(identity_file, config.identity_passphrase)

                # Then check if we have a passphrase from CLI
                cli_passphrase = self._get_cli_passphrase()
                if cli_passphrase:
                    logger.debug("Using passphrase from CLI config")
                    return self.add_key_with_passphrase(identity_file, cli_passphrase)

            return False

        except Exception as e:
            logger.error("Failed to add key: %s", str(e))
            return False

    def get_identity_from_available_keys(self) -> Optional[str]:
        """Get identity file from available keys in .ssh directory.

        This method searches for available SSH keys in the user's .ssh directory
        using the get_available_keys method. It returns the first available key
        based on the priority order defined in SSH_KEY_TYPES (e.g., Ed25519 keys
        have higher priority than RSA keys).

        Returns:
            Optional[str]: Path to identity file or None if no keys are found

        Example:
            >>> key_manager = SSHKeyManager(Path.home() / ".ssh", ["id_ed25519", "id_rsa"])
            >>> identity_file = key_manager.get_identity_from_available_keys()
            >>> if identity_file:
            ...     print(f"Using key: {identity_file}")
            ... else:
            ...     print("No SSH keys found")
        """
        available_keys = self.get_available_keys()
        if available_keys:
            # Use the first available key (highest priority)
            logger.debug("Using first available key: %s", available_keys[0])
            return available_keys[0]  # Already a full path

        return None

    def _get_cli_passphrase(self) -> Optional[str]:
        """Get passphrase from CLI configuration if available.

        Returns:
            Optional[str]: Deobfuscated passphrase or None if not available
        """
        try:
            # Import third-party modules
            from persistent_ssh_agent.cli import ConfigManager
            config_manager = ConfigManager()
            cli_passphrase = config_manager.get_passphrase()
            if cli_passphrase:
                return config_manager.deobfuscate_passphrase(cli_passphrase)
        except ImportError:
            logger.debug("CLI module not available")
        except Exception as e:
            logger.debug("Failed to get passphrase from CLI config: %s", e)
        return None
