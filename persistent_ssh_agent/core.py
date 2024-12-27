"""Core SSH management module."""

# Import built-in modules
from contextlib import suppress
import glob
import json
import logging
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

# Import third-party modules
from persistent_ssh_agent.config import SSHConfig


logger = logging.getLogger(__name__)


class SSHError(Exception):
    """Base exception for SSH-related errors."""


class PersistentSSHAgent:
    """Handles persistent SSH agent operations and authentication.

    This class manages SSH agent persistence across sessions by saving and
    restoring agent information. It also handles SSH key management and
    authentication for various operations including Git.
    """

    # SSH command constants
    SSH_DEFAULT_OPTIONS = {  # noqa: RUF012
        "StrictHostKeyChecking": "no"
    }

    # Supported SSH key types in order of preference
    SSH_KEY_TYPES = [  # noqa: RUF012
        "id_ed25519",  # Ed25519 (recommended, most secure)
        "id_ecdsa",  # ECDSA
        "id_ecdsa_sk",  # ECDSA with security key
        "id_ed25519_sk",  # Ed25519 with security key
        "id_rsa",  # RSA
        "id_dsa"  # DSA (legacy, not recommended)
    ]

    SSH_DEFAULT_KEY = "id_rsa"  # Fallback default key

    def __init__(self, expiration_time: int = 86400, config: Optional[SSHConfig] = None):
        """Initialize SSH manager.

        Args:
            expiration_time: Time in seconds before agent info expires
            config: Optional SSH configuration
        """
        self._ensure_home_env()

        # Initialize paths and state
        self._ssh_dir = Path.home() / ".ssh"
        self._agent_info_file = self._ssh_dir / "agent_info.json"
        self._ssh_config_cache = {}
        self._ssh_agent_started = False
        self._expiration_time = expiration_time
        self._config = config


    @staticmethod
    def _ensure_home_env() -> None:
        """Ensure HOME environment variable is set correctly.

        This method ensures the HOME environment variable is set to the user's
        home directory, which is required for SSH operations.
        """
        if "HOME" not in os.environ:
            os.environ["HOME"] = os.path.expanduser("~")

        logger.debug("Set HOME environment variable: %s", os.environ.get("HOME"))


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
            with open(self._agent_info_file, "w") as f:
                json.dump(agent_info, f)
            logger.debug("Saved agent info to: %s", self._agent_info_file)
        except Exception as e:
            logger.error("Failed to save agent info: %s", e)

    def _load_agent_info(self) -> bool:
        """Load and verify SSH agent information.

        Returns:
            bool: True if valid agent info was loaded and agent is running
        """
        if not self._agent_info_file.exists():
            return False

        try:
            with open(self._agent_info_file) as f:
                agent_info = json.load(f)

            # Quick validation of required fields
            if not all(key in agent_info for key in ("SSH_AUTH_SOCK", "SSH_AGENT_PID", "timestamp", "platform")):
                logger.debug("Missing required agent info fields")
                return False

            # Validate timestamp and platform
            if (time.time() - agent_info["timestamp"] > self._expiration_time or
                agent_info["platform"] != os.name):
                logger.debug("Agent info expired or platform mismatch")
                return False

            # Set environment variables
            os.environ["SSH_AUTH_SOCK"] = agent_info["SSH_AUTH_SOCK"]
            os.environ["SSH_AGENT_PID"] = agent_info["SSH_AGENT_PID"]

            # Verify agent is running
            result = self.run_command(["ssh-add", "-l"])
            return result.returncode != 2

        except Exception as e:
            logger.error("Failed to load agent info: %s", e)
            return False

    def _parse_ssh_agent_output(self, output: str) -> Dict[str, str]:
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
        result = self.run_command(["ssh-add", "-l"])
        return bool(result and result.returncode == 0 and identity_file in result.stdout)

    def _start_ssh_agent(self, identity_file: str) -> bool:
        """Start SSH agent and add identity.

        Args:
            identity_file: Path to SSH key

        Returns:
            bool: True if successful
        """
        try:
            # Check if key is already loaded
            if self._ssh_agent_started and self._verify_loaded_key(identity_file):
                logger.debug("Key already loaded: %s", identity_file)
                return True

            # Start SSH agent based on platform
            command = ["ssh-agent", "-s"] if os.name == "nt" else ["ssh-agent"]
            result = subprocess.run(command, capture_output=True, text=True, check=False) if os.name == "nt" else self.run_command(command)

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
            if not self._add_ssh_key(identity_file):
                logger.error("Failed to add key to agent")
                return False

            return True

        except Exception as e:
            logger.error("Failed to start SSH agent: %s", str(e))
            return False

    def _create_ssh_add_process(self, identity_file: str) -> subprocess.Popen:
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

    def _try_add_key_without_passphrase(self, identity_file: str) -> Tuple[bool, bool]:
        """Try to add SSH key without passphrase.

        Args:
            identity_file: Path to SSH key

        Returns:
            Tuple[bool, bool]: (success, needs_passphrase)
        """
        process = self._create_ssh_add_process(identity_file)

        try:
            stdout, stderr = process.communicate(timeout=1)
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

    def _add_key_with_passphrase(self, identity_file: str, passphrase: str) -> bool:
        """Add SSH key with passphrase.

        Args:
            identity_file: Path to SSH key
            passphrase: Key passphrase

        Returns:
            bool: True if successful
        """
        process = self._create_ssh_add_process(identity_file)

        try:
            stdout, stderr = process.communicate(input=f"{passphrase}\n", timeout=5)
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

    def _add_ssh_key(self, identity_file: str) -> bool:
        """Add SSH key to the agent.

        Args:
            identity_file: Path to the SSH key to add

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
            success, needs_passphrase = self._try_add_key_without_passphrase(identity_file)
            if success:
                return True

            # If passphrase is needed and we have it configured, try with passphrase
            if needs_passphrase and self._config and self._config.identity_passphrase:
                return self._add_key_with_passphrase(identity_file, self._config.identity_passphrase)

            return False

        except Exception as e:
            logger.error("Failed to add key: %s", str(e))
            return False

    def _test_ssh_connection(self, hostname: str) -> bool:
        """Test SSH connection to a host.

        Args:
            hostname: Hostname to test connection with

        Returns:
            bool: True if connection successful
        """
        test_result = self.run_command(
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
            if not self.is_valid_hostname(hostname):
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
        for key, value in self.SSH_DEFAULT_OPTIONS.items():
            options.extend(["-o", f"{key}={value}"])

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

    def get_git_ssh_command(self, hostname: str) -> Optional[str]:
        """Generate Git SSH command with proper configuration.

        Args:
            hostname: Target Git host

        Returns:
            SSH command string if successful, None on error
        """
        try:
            # Validate hostname
            if not self.is_valid_hostname(hostname):
                logger.error("Invalid hostname: %s", hostname)
                return None

            # Get and validate identity file
            identity_file = self._get_identity_file(hostname)
            if not identity_file:
                logger.error("No identity file found for: %s", hostname)
                return None

            if not os.path.exists(identity_file):
                logger.error("Identity file does not exist: %s", identity_file)
                return None

            # Set up SSH connection
            if not self.setup_ssh(hostname):
                logger.error("SSH setup failed for: %s", hostname)
                return None

            # Build command with options
            options = self._build_ssh_options(identity_file)
            command = " ".join(options)
            logger.debug("Generated SSH command: %s", command)
            return command

        except Exception as e:
            logger.error("Failed to generate Git SSH command: %s", str(e))
            return None

    def run_command(self, command: List[str], shell: bool = False,
                    check_output: bool = True, timeout: Optional[int] = None,
                    env: Optional[Dict[str, str]] = None) -> Optional[subprocess.CompletedProcess]:
        """Run a command and return its output.

        Args:
            command: Command and arguments to run
            shell: Whether to run command through shell
            check_output: Whether to capture command output
            timeout: Command timeout in seconds
            env: Environment variables for command

        Returns:
            CompletedProcess object if successful, None on error
        """
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=check_output,
                text=True,
                timeout=timeout,
                env=env,
                check=False
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error("Command timed out: %s", command)
            return None
        except Exception as e:
            logger.error("Command failed: %s - %s", command, e)
            return None

    def _write_temp_key(self, key_content: Union[str, bytes]) -> Optional[str]:
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
        try:
            available_keys = set()  # Use set to avoid duplicates
            for key_type in self.SSH_KEY_TYPES:
                # Check for base key type (e.g., id_rsa)
                key_path = os.path.join(self._ssh_dir, key_type)
                pub_key_path = f"{key_path}.pub"
                if os.path.exists(key_path) and os.path.exists(pub_key_path):
                    available_keys.add(str(Path(key_path)).replace("\\", "/"))

                # Check for keys with numeric suffixes (e.g., id_rsa2)
                pattern = os.path.join(self._ssh_dir, f"{key_type}[0-9]*")
                for numbered_key_path in glob.glob(pattern):
                    pub_key_path = f"{numbered_key_path}.pub"
                    if os.path.exists(numbered_key_path) and os.path.exists(pub_key_path):
                        available_keys.add(str(Path(numbered_key_path)).replace("\\", "/"))

            return sorted(available_keys)  # Convert back to sorted list
        except (OSError, IOError):
            return []

    def _get_identity_file(self, hostname: str) -> Optional[str]:
        """Get the identity file to use for a given hostname.

        Args:
            hostname: The hostname to get the identity file for.

        Returns:
            Optional[str]: Path to the identity file, or None if not found.
        """
        # Check environment variable first
        if "SSH_IDENTITY_FILE" in os.environ:
            identity_file = os.environ["SSH_IDENTITY_FILE"]
            if os.path.exists(identity_file):
                return str(Path(identity_file))

        # Check available keys
        available_keys = self._get_available_keys()
        if available_keys:
            # Use the first available key (highest priority)
            return available_keys[0]  # Already a full path

        # Always return default key path, even if it doesn't exist
        return str(Path(os.path.join(self._ssh_dir, "id_rsa")))

    def _parse_ssh_config(self) -> Dict[str, Dict[str, str]]:
        """Parse SSH config file to get host-specific configurations.

        Returns:
            dict: SSH configuration mapping hostnames to their settings
        """
        if self._ssh_config_cache:
            return self._ssh_config_cache

        ssh_config_path = self._ssh_dir / "config"
        if not ssh_config_path.exists():
            logger.debug("No SSH config file found at: %s", ssh_config_path)
            return {}

        logger.debug("Parsing SSH config file: %s", ssh_config_path)
        config = {}
        current_host = None
        current_match = None

        # Valid SSH config keys and their validation functions
        valid_keys = {
            "host": lambda x: True,  # Host patterns are handled separately
            "hostname": lambda x: self.is_valid_hostname(x),
            "port": lambda x: str(x).isdigit() and 1 <= int(x) <= 65535,
            "user": lambda x: bool(x and not any(c in x for c in " \t\n\r")),
            "identityfile": lambda x: True,  # Path validation handled elsewhere
            "identitiesonly": lambda x: x.lower() in ("yes", "no"),
            "forwardagent": lambda x: x.lower() in ("yes", "no"),
            "proxycommand": lambda x: bool(x),
            "proxyhost": lambda x: self.is_valid_hostname(x),
            "proxyport": lambda x: str(x).isdigit() and 1 <= int(x) <= 65535,
            "proxyuser": lambda x: bool(x and not any(c in x for c in " \t\n\r")),
            "stricthostkeychecking": lambda x: x.lower() in ("yes", "no", "accept-new", "off", "ask"),
            "userknownhostsfile": lambda x: True,  # Path validation handled elsewhere
            "batchmode": lambda x: x.lower() in ("yes", "no"),
            "compression": lambda x: x.lower() in ("yes", "no"),
        }

        def is_valid_host_pattern(pattern: str) -> bool:
            """Check if a host pattern is valid."""
            if not pattern:
                return False
            # Check for invalid characters that shouldn't be in a hostname
            invalid_chars = "|[]{}\\;"
            return not any(c in pattern for c in invalid_chars)

        try:
            with open(ssh_config_path) as f:
                content = f.read()

            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Handle Include directives
                if line.lower().startswith("include "):
                    include_path = line.split(None, 1)[1]
                    include_path = os.path.expanduser(include_path)
                    include_path = os.path.expandvars(include_path)

                    include_files = glob.glob(include_path)
                    for include_file in include_files:
                        if os.path.isfile(include_file):
                            try:
                                with open(include_file) as inc_f:
                                    content += "\n" + inc_f.read()
                            except Exception as e:
                                logger.debug(f"Failed to read include file {include_file}: {e}")
                    continue

                # Handle Match blocks
                if line.lower().startswith("match "):
                    current_match = line.split(None, 1)[1].lower()
                    continue

                # Handle Host blocks
                if line.lower().startswith("host "):
                    current_host = line.split(None, 1)[1]
                    if is_valid_host_pattern(current_host):
                        config[current_host] = {}
                    current_match = None
                    continue

                # Parse key-value pairs
                if current_host and "=" in line:
                    key, value = [x.strip() for x in line.split("=", 1)]
                    key = key.lower()
                    # Skip invalid keys or values
                    if key not in valid_keys or not valid_keys[key](value):
                        logger.debug(f"Skipping invalid config entry: {key}={value}")
                        continue
                    if current_match:
                        # Apply match block settings
                        if current_match == "all" or current_host in current_match:
                            config[current_host][key] = value
                    else:
                        config[current_host][key] = value
                elif current_host and len(line.split()) == 2:
                    # Handle space-separated format
                    key, value = line.split()
                    key = key.lower()
                    # Skip invalid keys or values
                    if key not in valid_keys or not valid_keys[key](value):
                        logger.debug(f"Skipping invalid config entry: {key} {value}")
                        continue
                    if current_match:
                        if current_match == "all" or current_host in current_match:
                            config[current_host][key] = value
                    else:
                        config[current_host][key] = value

            self._ssh_config_cache = config
            return config

        except Exception as e:
            logger.error(f"Failed to parse SSH config: {e}")
            return {}

    def _extract_hostname(self, url: str) -> Optional[str]:
        """Extract hostname from SSH URL.

        Args:
            url: SSH URL to extract hostname from

        Returns:
            str: Hostname if valid URL, None otherwise

        Note:
            Valid formats:
            - git@github.com:user/repo.git
            - git@host.example.com:user/repo.git
        """
        if not url or not isinstance(url, str):
            return None

        # Check for basic URL structure
        if ":" not in url or "@" not in url:
            return None

        # Split URL into user@host and path parts
        try:
            user_host, path = url.split(":", 1)
        except ValueError:
            return None

        # Validate path part
        if not path or not path.strip("/"):
            return None

        # Extract hostname
        try:
            parts = user_host.split("@")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                return None
            hostname = parts[1]

            # Basic hostname validation
            if not hostname or hostname.startswith(".") or hostname.endswith("."):
                return None

            # Allow only valid hostname characters
            if not re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9._]*[a-zA-Z0-9]$", hostname):
                return None

            return hostname
        except Exception:
            return None

    def is_valid_hostname(self, hostname: str) -> bool:
        """Check if a hostname is valid according to RFC 1123 and supports IPv6.

        Args:
            hostname: The hostname to validate

        Returns:
            bool: True if the hostname is valid, False otherwise

        Notes:
            - Maximum length of 255 characters
            - Can contain letters (a-z), numbers (0-9), dots (.) and hyphens (-)
            - Cannot start or end with a dot or hyphen
            - Labels (parts between dots) cannot start or end with a hyphen
            - Labels cannot be longer than 63 characters
            - IPv6 addresses are supported (with or without brackets)
        """
        if not hostname:
            return False

        # Handle IPv6 addresses
        if ":" in hostname:
            # Remove brackets if present
            if hostname.startswith("[") and hostname.endswith("]"):
                hostname = hostname[1:-1]
            try:
                # Try to parse as IPv6 address
                socket.inet_pton(socket.AF_INET6, hostname)
                return True
            except (socket.error, ValueError):
                return False

        # Check length
        if len(hostname) > 255:
            return False

        # Check for valid characters and label lengths
        labels = hostname.split(".")
        for label in labels:
            if not label or len(label) > 63:
                return False
            if label.startswith("-") or label.endswith("-"):
                return False
            if not all(c.isalnum() or c == "-" for c in label):
                return False

        return True
