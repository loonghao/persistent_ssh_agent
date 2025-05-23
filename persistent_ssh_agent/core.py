"""Core SSH management module."""

# Import built-in modules
from contextlib import suppress
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Callable
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import TypeVar
from typing import Union

# Import third-party modules
from persistent_ssh_agent.config import SSHConfig
from persistent_ssh_agent.constants import SSHAgentConstants
from persistent_ssh_agent.git import GitIntegration
from persistent_ssh_agent.ssh_config_parser import SSHConfigParser
from persistent_ssh_agent.ssh_key_manager import SSHKeyManager
from persistent_ssh_agent.utils import ensure_home_env
from persistent_ssh_agent.utils import extract_hostname
from persistent_ssh_agent.utils import run_command


# Import local modules (conditional to avoid circular imports)
try:
    # Import third-party modules
    from persistent_ssh_agent.cli import ConfigManager
    _has_cli = True
except ImportError:
    _has_cli = False


logger = logging.getLogger(__name__)

# Type definitions
T = TypeVar("T")
ValidatorFunc = Callable[[str], bool]
SSHOptionValue = Union[str, List[str]]
YesNoOption = Literal["yes", "no"]
ExtendedYesNoOption = Literal["yes", "no", "ask", "confirm"]
StrictHostKeyCheckingOption = Literal["yes", "no", "accept-new", "off", "ask"]
RequestTTYOption = Literal["yes", "no", "force", "auto"]
ControlMasterOption = Literal["yes", "no", "ask", "auto", "autoask"]
CanonicalizeHostnameOption = Literal["yes", "no", "always"]


class SSHError(Exception):
    """Base exception for SSH-related errors."""


class PersistentSSHAgent:
    """Handles persistent SSH agent operations and authentication.

    This class manages SSH agent persistence across sessions by saving and
    restoring agent information. It also handles SSH key management and
    authentication for various operations including Git.
    """

    def __init__(self, config: Optional[SSHConfig] = None,
                 expiration_time: int = 86400,
                 reuse_agent: bool = True):
        """Initialize SSH manager.

        Args:
            expiration_time: Time in seconds before agent info expires
            config: Optional SSH configuration
            reuse_agent: Whether to attempt reusing existing SSH agent
        """
        ensure_home_env()

        # Initialize paths and state
        self._ssh_dir = Path.home() / ".ssh"
        self._agent_info_file = self._ssh_dir / "agent_info.json"
        self._ssh_config_cache: Dict[str, Dict[str, str]] = {}
        self._ssh_agent_started = False
        self._expiration_time = expiration_time
        self._config = config
        self._reuse_agent = reuse_agent

        # Initialize managers
        self.ssh_config_parser = SSHConfigParser(self._ssh_dir)
        self.ssh_key_manager = SSHKeyManager(self._ssh_dir, SSHAgentConstants.SSH_KEY_TYPES)

        # Initialize Git integration
        self.git = GitIntegration(self)

    def __enter__(self):
        """Context manager entry point.

        Returns:
            PersistentSSHAgent: Self for use in with statement
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            None: Don't suppress exceptions
        """
        # Currently no cleanup needed as SSH agent persists
        # Future: Could add cleanup logic here if needed
        del exc_type, exc_val, exc_tb  # Suppress unused variable warnings

    def _save_agent_info(self, auth_sock: str, agent_pid: str) -> None:
        """Save SSH agent information to file.

        Args:
            auth_sock: SSH_AUTH_SOCK value
            agent_pid: SSH_AGENT_PID value
        """
        agent_info = {
            "SSH_AUTH_SOCK": auth_sock,
            "SSH_AGENT_PID": agent_pid,
            "timestamp": time.time(),
            "platform": os.name
        }

        try:
            self._ssh_dir.mkdir(parents=True, exist_ok=True)
            with open(self._agent_info_file, "w", encoding="utf-8") as f:
                json.dump(agent_info, f)
            logger.debug("Saved agent info to: %s", self._agent_info_file)
        except (OSError, IOError) as e:
            logger.error("Failed to save agent info: %s", e)

    def _load_agent_info(self) -> bool:
        """Load and verify SSH agent information.

        Returns:
            bool: True if valid agent info was loaded and agent is running
        """
        if not self._agent_info_file.exists():
            logger.debug("Agent info file does not exist: %s", self._agent_info_file)
            return False

        try:
            with open(self._agent_info_file, encoding="utf-8") as f:
                agent_info = json.load(f)

            # Quick validation of required fields
            required_fields = ("SSH_AUTH_SOCK", "SSH_AGENT_PID", "timestamp", "platform")
            if not all(key in agent_info for key in required_fields):
                logger.debug("Missing required agent info fields: %s",
                             [f for f in required_fields if f not in agent_info])
                return False

            # Validate timestamp and platform
            current_time = time.time()
            if current_time - agent_info["timestamp"] > self._expiration_time:
                logger.debug("Agent info expired: %d seconds old",
                             current_time - agent_info["timestamp"])
                return False

            # Platform check is only enforced on Windows
            if os.name == "nt" and agent_info["platform"] != "nt":
                logger.debug("Platform mismatch: expected 'nt', got '%s'",
                             agent_info["platform"])
                return False

            # Set environment variables
            os.environ["SSH_AUTH_SOCK"] = agent_info["SSH_AUTH_SOCK"]
            os.environ["SSH_AGENT_PID"] = agent_info["SSH_AGENT_PID"]

            # Verify agent is running
            result = run_command(["ssh-add", "-l"])
            if not result:
                logger.debug("Failed to run ssh-add -l")
                return False

            # Return code 2 means "agent not running"
            # Return code 1 means "no identities" (which is fine)
            if result.returncode == 2:
                logger.debug("SSH agent is not running")
                return False

            logger.debug("Successfully loaded agent info")
            return True

        except json.JSONDecodeError as e:
            logger.error("Failed to parse agent info JSON: %s", e)
            return False
        except Exception as e:
            logger.error("Failed to load agent info: %s", e)
            return False

    @staticmethod
    def _parse_ssh_agent_output(output: str) -> Dict[str, str]:
        """Parse SSH agent output to extract environment variables.

        Args:
            output: SSH agent output string

        Returns:
            Dict[str, str]: Dictionary of environment variables
        """
        env_vars = {}
        for line in output.split("\n"):
            if "=" in line and ";" in line:
                var, value = line.split("=", 1)
                var = var.strip()
                value = value.split(";")[0].strip(' "')
                env_vars[var] = value
        return env_vars

    def _verify_loaded_key(self, identity_file: str) -> bool:
        """Verify if a specific key is loaded in the agent.

        Args:
            identity_file: Path to SSH key to verify

        Returns:
            bool: True if key is loaded
        """
        return self.ssh_key_manager.verify_loaded_key(identity_file)

    def _start_ssh_agent(self, identity_file: str) -> bool:
        """Start SSH agent and add identity.

        This method first attempts to load an existing SSH agent if reuse_agent is True.
        If that fails or if the agent is not running, it starts a new agent.

        Args:
            identity_file: Path to SSH key

        Returns:
            bool: True if successful
        """
        try:
            # Try to load existing agent if reuse is enabled
            if self._reuse_agent:
                if self._load_agent_info():
                    if self._verify_loaded_key(identity_file):
                        logger.debug("Using existing agent with loaded key: %s", identity_file)
                        return True
                    logger.debug("Existing agent found but key not loaded")
                else:
                    logger.debug("No valid existing agent found")
            else:
                logger.debug("Agent reuse disabled, starting new agent")

            # Check if key is already loaded in current session
            if self._ssh_agent_started and self._verify_loaded_key(identity_file):
                logger.debug("Key already loaded in current session: %s", identity_file)
                return True

            # Start SSH agent with platform-specific command
            command = ["ssh-agent"]
            if os.name == "nt":
                command.append("-s")

            result = run_command(command)
            if not result or result.returncode != 0:
                logger.error("Failed to start SSH agent")
                return False

            # Parse and set environment variables
            env_vars = self._parse_ssh_agent_output(result.stdout)
            if not env_vars:
                logger.error("No environment variables found in agent output")
                return False

            # Update environment
            os.environ.update(env_vars)
            self._ssh_agent_started = True

            # Save agent info if required variables are present
            if "SSH_AUTH_SOCK" in env_vars and "SSH_AGENT_PID" in env_vars:
                self._save_agent_info(env_vars["SSH_AUTH_SOCK"], env_vars["SSH_AGENT_PID"])

            # Add the key
            logger.debug("Adding key to agent: %s", identity_file)
            if not self.ssh_key_manager.add_ssh_key(identity_file, self._config):
                logger.error("Failed to add key to agent")
                return False

            return True

        except Exception as e:
            logger.error("Failed to start SSH agent: %s", str(e))
            return False

    def _test_ssh_connection(self, hostname: str) -> bool:
        """Test SSH connection to a host.

        Args:
            hostname: Hostname to test connection with

        Returns:
            bool: True if connection successful
        """
        test_result = run_command(
            ["ssh", "-T", "-o", "StrictHostKeyChecking=no", f"git@{hostname}"]
        )

        if test_result is None:
            logger.error("SSH connection test failed")
            return False

        # Most Git servers return 1 for successful auth
        if test_result.returncode in [0, 1]:
            logger.debug("SSH connection test successful")
            return True

        logger.error("SSH connection test failed with code: %d", test_result.returncode)
        return False

    def setup_ssh(self, hostname: str) -> bool:
        """Set up SSH authentication for a host.

        Args:
            hostname: Hostname to set up SSH for

        Returns:
            bool: True if setup successful
        """
        try:
            # Validate hostname
            # Import third-party modules
            from persistent_ssh_agent.utils import is_valid_hostname
            if not is_valid_hostname(hostname):
                logger.error("Invalid hostname: %s", hostname)
                return False

            # Get identity file
            identity_file = self._get_identity_file(hostname)
            if not identity_file:
                logger.error("No identity file found for: %s", hostname)
                return False

            if not os.path.exists(identity_file):
                logger.error("Identity file does not exist: %s", identity_file)
                return False

            logger.debug("Using SSH key: %s", identity_file)

            # Start SSH agent
            if not self._start_ssh_agent(identity_file):
                logger.error("Failed to start SSH agent")
                return False

            # Test connection
            return self._test_ssh_connection(hostname)

        except Exception as e:
            logger.error("SSH setup failed: %s", str(e))
            return False

    def _build_ssh_options(self, identity_file: str) -> List[str]:
        """Build SSH command options list.

        Args:
            identity_file: Path to SSH identity file

        Returns:
            List[str]: List of SSH command options
        """
        options = ["ssh"]

        # Add default options
        options.extend(SSHAgentConstants.SSH_DEFAULT_OPTIONS)

        # Add identity file
        options.extend(["-i", identity_file])

        # Add custom options from config
        if self._config and self._config.ssh_options:
            for key, value in self._config.ssh_options.items():
                # Skip empty or invalid options
                if not key or not value:
                    logger.warning("Skipping invalid SSH option: %s=%s", key, value)
                    continue
                options.extend(["-o", f"{key}={value}"])

        return options

    @staticmethod
    def _write_temp_key(key_content: Union[str, bytes]) -> Optional[str]:
        """Write key content to a temporary file.

        Args:
            key_content: SSH key content to write

        Returns:
            str: Path to temporary key file or None if operation failed
        """
        # Convert bytes to string if needed
        if isinstance(key_content, bytes):
            key_content = key_content.decode("utf-8")

        # Convert line endings to LF
        key_content = key_content.replace("\r\n", "\n")
        temp_key = None

        try:
            # Create temp file with proper permissions
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                temp_key = temp_file.name
                temp_file.write(key_content)
            # Set proper permissions for SSH key
            if os.name != "nt":  # Skip on Windows
                os.chmod(temp_key, 0o600)
            # Convert Windows path to Unix-style for consistency
            return temp_key.replace("\\", "/")

        except (PermissionError, OSError) as e:
            if temp_key and os.path.exists(temp_key):
                with suppress(OSError):
                    os.unlink(temp_key)
            logger.error(f"Failed to write temporary key file: {e}")
            return None

    def _resolve_identity_file(self, identity_path: str) -> Optional[str]:
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
                expanded_path = os.path.join(self._ssh_dir, expanded_path)

            # Convert to absolute path
            abs_path = os.path.abspath(expanded_path)

            # Check if file exists
            if not os.path.exists(abs_path):
                return None

            # Convert Windows path to Unix-style for consistency
            return abs_path.replace("\\", "/")

        except (TypeError, ValueError):
            return None

    def _get_available_keys(self) -> List[str]:
        """Get list of available SSH keys in .ssh directory.

        Returns:
            List[str]: List of available key paths with normalized format (forward slashes).
        """
        return self.ssh_key_manager.get_available_keys()

    def _get_identity_file(self, hostname: str) -> Optional[str]:
        """Get the identity file to use for a given hostname.

        This method tries multiple sources to find an appropriate SSH identity file,
        checking them in the following order of priority:
        1. SSH config file for the specific hostname
        2. CLI configuration (if available)
        3. SSH_IDENTITY_FILE environment variable
        4. Available SSH keys in the user's .ssh directory
        5. Default key path (~/.ssh/id_rsa) as a fallback

        Args:
            hostname: The hostname to get the identity file for.

        Returns:
            Optional[str]: Path to the identity file, or None if not found.

        Note:
            Even if no identity file is found in any of the sources, this method
            will still return a default path to ~/.ssh/id_rsa, which may not exist.
        """
        # Try to get identity file from different sources in order of priority

        # 1. Check SSH config for host-specific identity file
        identity_file = self._get_identity_from_ssh_config(hostname)
        if identity_file:
            return identity_file

        # 2. Check CLI configuration
        identity_file = self._get_identity_from_cli()
        if identity_file:
            return identity_file

        # 3. Check environment variable
        identity_file = self._get_identity_from_env()
        if identity_file:
            return identity_file

        # 4. Check available keys in .ssh directory
        identity_file = self._get_identity_from_available_keys()
        if identity_file:
            return identity_file

        # 5. Always return default key path, even if it doesn't exist
        return str(Path(os.path.join(self._ssh_dir, SSHAgentConstants.SSH_DEFAULT_KEY)))

    def _get_identity_from_ssh_config(self, hostname: str) -> Optional[str]:
        """Get identity file from SSH config for a specific hostname.

        This method checks the SSH configuration file (~/.ssh/config) for host-specific
        IdentityFile settings. It uses the SSH config parser to find the appropriate
        identity file for the given hostname.

        Args:
            hostname: The hostname to look up in SSH config

        Returns:
            Optional[str]: Path to identity file from SSH config or None if not found

        Example:
            >>> agent = PersistentSSHAgent()
            >>> identity_file = agent._get_identity_from_ssh_config("github.com")
            >>> if identity_file:
            ...     print(f"Using SSH config identity file: {identity_file}")
        """
        try:
            # Parse SSH config and find matching host configuration
            ssh_configs = self.ssh_config_parser.parse_ssh_config()

            # Look for exact hostname match first
            if hostname in ssh_configs and "identityfile" in ssh_configs[hostname]:
                identity_files = ssh_configs[hostname]["identityfile"]
                # Handle both single string and list of strings
                if isinstance(identity_files, list):
                    identity_file = identity_files[0]  # Use first identity file
                else:
                    identity_file = identity_files

                # Expand user directory and resolve path
                expanded_path = os.path.expanduser(identity_file)
                if os.path.exists(expanded_path):
                    logger.debug("Using identity file from SSH config: %s", expanded_path)
                    return expanded_path
                else:
                    logger.debug("SSH config identity file does not exist: %s", expanded_path)

            # Look for wildcard matches if no exact match found
            for host_pattern, config in ssh_configs.items():
                if self._match_hostname(hostname, host_pattern) and "identityfile" in config:
                    identity_files = config["identityfile"]
                    # Handle both single string and list of strings
                    if isinstance(identity_files, list):
                        identity_file = identity_files[0]  # Use first identity file
                    else:
                        identity_file = identity_files

                    # Expand user directory and resolve path
                    expanded_path = os.path.expanduser(identity_file)
                    if os.path.exists(expanded_path):
                        logger.debug("Using identity file from SSH config pattern %s: %s", host_pattern, expanded_path)
                        return expanded_path

        except Exception as e:
            logger.debug("Failed to get identity file from SSH config: %s", e)

        return None

    def _match_hostname(self, hostname: str, pattern: str) -> bool:
        """Check if hostname matches SSH config pattern.

        Args:
            hostname: The hostname to match
            pattern: The SSH config host pattern (may contain wildcards)

        Returns:
            bool: True if hostname matches the pattern

        Example:
            >>> agent = PersistentSSHAgent()
            >>> agent._match_hostname("github.com", "*.github.com")
            False
            >>> agent._match_hostname("api.github.com", "*.github.com")
            True
        """
        # Import built-in modules
        import fnmatch
        return fnmatch.fnmatch(hostname, pattern)

    def _get_identity_from_cli(self) -> Optional[str]:
        """Get identity file from CLI configuration.

        This method attempts to retrieve the identity file path from the CLI configuration
        manager if available. It checks if the CLI module is loaded, creates a ConfigManager
        instance, and retrieves the identity file path. It also verifies that the file exists.

        Returns:
            Optional[str]: Path to identity file or None if not found, CLI module is not
            available, or an error occurs during retrieval.

        Example:
            >>> agent = PersistentSSHAgent()
            >>> identity_file = agent._get_identity_from_cli()
            >>> if identity_file:
            ...     print(f"Using identity file: {identity_file}")
        """
        if not _has_cli:
            return None

        try:
            config_manager = ConfigManager()
            cli_identity_file = config_manager.get_identity_file()
            if cli_identity_file and os.path.exists(os.path.expanduser(cli_identity_file)):
                logger.debug("Using identity file from CLI config: %s", cli_identity_file)
                return os.path.expanduser(cli_identity_file)
        except Exception as e:
            logger.debug("Failed to get identity file from CLI config: %s", e)

        return None

    def _get_identity_from_env(self) -> Optional[str]:
        """Get identity file from environment variable.

        This method checks for the SSH_IDENTITY_FILE environment variable and verifies
        that the file exists at the specified path. If the environment variable is not set
        or the file doesn't exist, it returns None.

        Returns:
            Optional[str]: Path to identity file or None if not found or file doesn't exist

        Example:
            >>> # With SSH_IDENTITY_FILE set to an existing file
            >>> os.environ["SSH_IDENTITY_FILE"] = "/path/to/key"
            >>> agent = PersistentSSHAgent()
            >>> identity_file = agent._get_identity_from_env()
            >>> print(identity_file)  # "/path/to/key"
        """
        if "SSH_IDENTITY_FILE" in os.environ:
            identity_file = os.environ["SSH_IDENTITY_FILE"]
            if os.path.exists(identity_file):
                logger.debug("Using identity file from environment: %s", identity_file)
                return str(Path(identity_file))

        return None

    def _get_identity_from_available_keys(self) -> Optional[str]:
        """Get identity file from available keys in .ssh directory.

        This method searches for available SSH keys in the user's .ssh directory
        using the ssh_key_manager. It returns the first available key
        based on the priority order defined in SSH_KEY_TYPES (e.g., Ed25519 keys
        have higher priority than RSA keys).

        Returns:
            Optional[str]: Path to identity file or None if no keys are found

        Example:
            >>> agent = PersistentSSHAgent()
            >>> identity_file = agent._get_identity_from_available_keys()
            >>> if identity_file:
            ...     print(f"Using key: {identity_file}")
            ... else:
            ...     print("No SSH keys found")
        """
        return self.ssh_key_manager.get_identity_from_available_keys()

    # Delegation methods for backward compatibility with tests
    def _add_ssh_key(self, identity_file: str, config: Optional[SSHConfig] = None) -> bool:
        """Add SSH key to agent (delegation method).

        Args:
            identity_file: Path to SSH key
            config: Optional SSH configuration

        Returns:
            bool: True if successful
        """
        return self.ssh_key_manager.add_ssh_key(identity_file, config)

    def _create_ssh_add_process(self, identity_file: str):
        """Create SSH add process (delegation method).

        Args:
            identity_file: Path to SSH key

        Returns:
            subprocess.Popen: Process object
        """
        return self.ssh_key_manager.create_ssh_add_process(identity_file)

    def _try_add_key_without_passphrase(self, identity_file: str):
        """Try to add key without passphrase (delegation method).

        Args:
            identity_file: Path to SSH key

        Returns:
            Tuple[bool, bool]: (success, needs_passphrase)
        """
        return self.ssh_key_manager.try_add_key_without_passphrase(identity_file)

    def _add_key_with_passphrase(self, identity_file: str, passphrase: str) -> bool:
        """Add key with passphrase (delegation method).

        Args:
            identity_file: Path to SSH key
            passphrase: SSH key passphrase

        Returns:
            bool: True if successful
        """
        return self.ssh_key_manager.add_key_with_passphrase(identity_file, passphrase)

    def _parse_ssh_config(self) -> Dict[str, Dict[str, SSHOptionValue]]:
        """Parse SSH config file to get host-specific configurations.

        Returns:
            Dict[str, Dict[str, SSHOptionValue]]: A dictionary containing host-specific SSH configurations.
            The outer dictionary maps host patterns to their configurations,
            while the inner dictionary maps configuration keys to their values.
            Values can be either strings or lists of strings for multi-value options.
        """
        # Create a new parser instance with the current SSH directory
        # This ensures tests can override the SSH directory properly
        parser = SSHConfigParser(self._ssh_dir)
        return parser.parse_ssh_config()

    def extract_hostname(self, url: str) -> Optional[str]:
        """Extract hostname from SSH URL (public method).

        This is a public wrapper around the extract_hostname function in utils.

        Args:
            url: SSH URL to extract hostname from (e.g., git@github.com:user/repo.git)

        Returns:
            str: Hostname if valid URL, None otherwise
        """
        return extract_hostname(url)
