"""SSH management module for repository updater."""

# Import built-in modules
from contextlib import suppress
import fnmatch
import json
import logging
import os
from pathlib import Path
import re
import subprocess
from tempfile import NamedTemporaryFile
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
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

    def __init__(self, expiration_time: int = 86400, config: Optional[SSHConfig] = None):
        """Initialize SSH manager.

        Args:
            expiration_time: Time in seconds before agent info expires
            config: Optional SSH configuration
        """
        self._ensure_home_env()
        self._ssh_dir = Path.home() / ".ssh"
        self._agent_info_file = self._ssh_dir / "agent_info.json"
        self._ssh_config_cache: Dict[str, Dict[str, Any]] = {}
        self._ssh_agent_started = False
        self._expiration_time = expiration_time
        self._config = config

    def _ensure_home_env(self) -> None:
        """Ensure HOME environment variable is set correctly.

        This method ensures the HOME environment variable is set to the user's
        home directory, which is required for SSH operations. It uses Python's
        os.path.expanduser() which handles platform-specific differences.
        """
        if "HOME" not in os.environ:
            os.environ["HOME"] = os.path.expanduser("~")

        logger.debug("HOME set to: %s", os.environ.get("HOME"))

    def _save_agent_info(self, auth_sock: str, agent_pid: str) -> None:
        """Save SSH agent information to file.

        Args:
            auth_sock: SSH_AUTH_SOCK value
            agent_pid: SSH_AGENT_PID value

        Note:
            This method will not raise exceptions, only log errors
        """
        try:
            agent_info = {
                "SSH_AUTH_SOCK": auth_sock,
                "SSH_AGENT_PID": agent_pid,
                "timestamp": time.time(),
                "platform": os.name
            }
            os.makedirs(os.path.dirname(self._agent_info_file), exist_ok=True)
            with open(self._agent_info_file, "w") as f:
                json.dump(agent_info, f)
            logger.debug("Saved agent info to %s", self._agent_info_file)
        except Exception as e:
            logger.error("Failed to save agent info: %s", e)

    def _load_agent_info(self) -> bool:
        """Load and verify SSH agent information.

        Returns:
            True if valid agent info was loaded and agent is running

        Note:
            Agent info is considered invalid if:
            - File doesn't exist
            - Info is older than 24 hours
            - Platform doesn't match
            - Required environment variables are missing
            - Agent is not running
        """
        try:
            if not os.path.exists(self._agent_info_file):
                return False

            with open(self._agent_info_file, "r") as f:
                agent_info = json.load(f)

            # Check if the agent info is recent (less than 24 hours old)
            if time.time() - agent_info.get("timestamp", 0) > self._expiration_time:
                logger.debug("Agent info too old")
                return False

            # Check platform compatibility
            if agent_info.get("platform") != os.name:
                logger.debug("Agent info platform mismatch")
                return False

            # Set environment variables
            auth_sock = agent_info.get("SSH_AUTH_SOCK")
            agent_pid = agent_info.get("SSH_AGENT_PID")
            if not auth_sock or not agent_pid:
                logger.debug("Missing required agent info")
                return False

            os.environ["SSH_AUTH_SOCK"] = auth_sock
            os.environ["SSH_AGENT_PID"] = agent_pid

            # Verify agent is running
            try:
                result = self._run_command(
                    ["ssh-add", "-l"],
                )
                return result.returncode != 2  # returncode 2 means agent not running
            except Exception as e:
                logger.debug("Failed to verify agent: %s", e)
                return False

        except Exception as e:
            logger.error("Failed to load agent info: %s", e)
            return False

    def _start_ssh_agent(self, identity_file: str) -> bool:
        """Start SSH agent and add specific key.

        Args:
            identity_file: Path to the SSH key to add

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # If agent is already started, check if key is loaded
            if self._ssh_agent_started:
                logger.debug("Agent already started, checking loaded keys")
                result = self._run_command(["ssh-add", "-l"])
                if result and result.returncode == 0 and identity_file in result.stdout:
                    logger.debug("Key already loaded")
                    return True

            # Kill any existing agent on Windows
            if os.name == "nt":
                logger.debug("Killing existing SSH agent on Windows")
                self._run_command(
                    ["taskkill", "/F", "/IM", "ssh-agent.exe"],
                    check_output=False
                )
                time.sleep(1)  # Wait for process to fully terminate

            # Start the agent
            logger.debug("Starting SSH agent")
            if os.name == "nt":
                # On Windows, start ssh-agent directly and parse output
                result = subprocess.run(
                    ["ssh-agent", "-s"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10  # Add timeout to prevent hanging
                )
            else:
                result = self._run_command(
                    ["ssh-agent"],
                    shell=False
                )

            if not result or result.returncode != 0:
                logger.error("Failed to start agent")
                return False

            # Parse agent output to get environment variables
            env_vars = {}
            for line in result.stdout.split("\n"):
                if "=" in line and ";" in line:
                    var = line.split("=", 1)[0].strip()
                    val = line.split("=", 1)[1].split(";")[0].strip()
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]  # Remove quotes
                    env_vars[var] = val

            # Set environment variables
            os.environ.update(env_vars)
            self._ssh_agent_started = True

            # Save agent info for persistence
            if "SSH_AUTH_SOCK" in env_vars and "SSH_AGENT_PID" in env_vars:
                self._save_agent_info(env_vars["SSH_AUTH_SOCK"], env_vars["SSH_AGENT_PID"])

            # Add the key
            logger.debug("Adding key to agent")
            if not self._add_ssh_key(identity_file):
                logger.error("Failed to add key to agent")
                return False

            # Verify key was added with timeout
            logger.debug("Verifying key was added")
            max_retries = 3
            retry_delay = 1
            for attempt in range(max_retries):
                try:
                    result = self._run_command(
                        ["ssh-add", "-l"],
                        timeout=5  # Add timeout for the verification
                    )
                    if result and result.returncode == 0:
                        logger.debug("Key verification successful")
                        return True
                    logger.debug(f"Verification attempt {attempt + 1} failed, retrying...")
                    time.sleep(retry_delay)
                except subprocess.TimeoutExpired:
                    logger.debug(f"Verification attempt {attempt + 1} timed out")
                    continue

            logger.error("Failed to verify key was added after all retries")
            return False

        except subprocess.TimeoutExpired as e:
            logger.error(f"SSH agent operation timed out: {e!s}")
            return False
        except Exception as e:
            logger.error(f"Failed to start SSH agent: {e!s}")
            return False

    def _add_ssh_key(self, identity_file: str) -> bool:
        """Add SSH key to the agent.

        Args:
            identity_file: Path to the SSH key to add

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            passphrase = None
            if self._config and self._config.identity_passphrase:
                passphrase = self._config.identity_passphrase
                logger.debug("Using passphrase from config")
            elif "SSH_KEY_PASSPHRASE" in os.environ:
                passphrase = os.environ["SSH_KEY_PASSPHRASE"]
                logger.debug("Using passphrase from environment")

            if passphrase:
                if os.name == "nt":
                    # Windows-specific approach
                    logger.debug("Using Windows-specific key addition")
                    result = subprocess.run(
                        ["ssh-add", identity_file],
                        input=f"{passphrase}\n".encode(),
                        capture_output=True,
                        check=False,
                        timeout=10
                    )
                else:
                    # Unix-specific approach using expect
                    logger.debug("Using Unix-specific key addition")
                    expect_script = f"""#!/usr/bin/expect -f
set timeout 10
spawn ssh-add {identity_file}
expect "Enter passphrase"
send "{passphrase}\\r"
expect {{
    "Identity added" {{
        exit 0
    }}
    timeout {{
        exit 1
    }}
    eof {{
        exit 2
    }}
}}
"""
                    # Create temporary expect script
                    with NamedTemporaryFile(mode="w", suffix=".exp", delete=False) as script_file:
                        script_path = script_file.name
                        script_file.write(expect_script)

                    try:
                        # Make script executable
                        os.chmod(script_path, 0o700)

                        # Run expect script
                        result = subprocess.run(
                            ["expect", script_path],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=10
                        )
                    finally:
                        # Clean up script
                        try:
                            os.unlink(script_path)
                        except Exception as e:
                            logger.debug(f"Failed to remove temporary script: {e}")

                if result and result.returncode == 0:
                    logger.debug("Successfully added key with passphrase")
                    return True

                # If the above methods fail, try a simpler approach
                logger.debug("First attempt failed, trying simpler approach")
                env = os.environ.copy()
                env["DISPLAY"] = ":0"  # Required for some SSH implementations

                result = subprocess.run(
                    ["ssh-add", identity_file],
                    input=passphrase.encode(),
                    env=env,
                    capture_output=True,
                    check=False,
                    timeout=10
                )

                if result and result.returncode == 0:
                    logger.debug("Successfully added key with simple passphrase method")
                    return True

                logger.error(f"Failed to add key: {result.stderr.decode() if result and result.stderr else 'Unknown error'}")
                return False

            else:
                # Add key without passphrase
                logger.debug("Adding key without passphrase")
                result = self._run_command(
                    ["ssh-add", identity_file],
                    timeout=10
                )

                if not result or result.returncode != 0:
                    logger.error(f"Failed to add key: {result.stderr if result else 'Unknown error'}")
                    return False

                return True

        except Exception as e:
            logger.error(f"Failed to add key: {e!s}")
            return False

    def setup_ssh(self, hostname: str) -> bool:
        """Set up SSH authentication for a host.

        Args:
            hostname: Hostname to set up SSH for

        Returns:
            True if setup successful, False otherwise
        """
        try:
            self._ensure_home_env()

            # Get the correct identity file
            identity_file = self._get_identity_file(hostname)
            if not os.path.exists(identity_file):
                logger.warning("Identity file not found: %s", identity_file)
                return False

            logger.debug("Using SSH key for %s: %s", hostname, identity_file)

            # Start SSH agent with the specific key
            if not self._start_ssh_agent(identity_file):
                return False

            # Test SSH connection
            test_result = self._run_command(
                ["ssh", "-T", "-o", "StrictHostKeyChecking=no", f"git@{hostname}"],
            )

            # Check if command execution failed
            if test_result is None:
                return False

            # Most Git servers return 1 for successful auth
            return test_result.returncode in [0, 1]

        except Exception as e:
            logger.error("Error in SSH setup: %s", str(e))
            return False

    def _decode_output(self, output: Union[str, bytes]) -> str:
        """Safely decode command output.

        Args:
            output: String or bytes output from command

        Returns:
            str: Decoded string
        """
        if isinstance(output, str):
            return output
        try:
            return output.decode("utf-8")
        except UnicodeDecodeError:
            return output.decode("latin-1")

    def _run_command(
            self,
            cmd: Union[str, List[str]],
            check_output: bool = True,
            shell: bool = False,
            env: Optional[Dict[str, str]] = None,
            input: Optional[Union[str, bytes]] = None,
            timeout: Optional[int] = None
    ) -> Optional[subprocess.CompletedProcess]:
        """Run a command and handle its output.

        Args:
            cmd: Command and arguments to run
            check_output: Whether to check command output
            shell: Whether to run command through shell
            env: Environment variables to use
            input: Input to pass to the command
            timeout: Timeout in seconds for the command

        Returns:
            CompletedProcess instance or None if command failed
        """
        try:
            # Set up environment
            if env is None:
                env = os.environ.copy()

            # Run command
            result = subprocess.run(
                cmd,
                shell=shell,
                env=env,
                input=input,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout
            )

            # Check output if requested
            if check_output and result.returncode != 0:
                logger.error("Command failed with exit code %d", result.returncode)
                if result.stderr:
                    logger.error("stderr: %s", result.stderr)
                return None

            return result

        except subprocess.TimeoutExpired as e:
            logger.error("Command timed out after %d seconds: %s", timeout, str(e))
            return None
        except Exception as e:
            logger.error("Command failed: %s", str(e))
            return None

    def _get_identity_file(self, hostname: str) -> Optional[str]:
        """Get SSH identity file for a host."""
        logger.debug("Getting identity file for hostname: %s", hostname)

        # Check config first
        if self._config and (self._config.identity_file or self._config.identity_content):
            logger.debug("Using configured identity")
            if self._config.identity_file and os.path.exists(self._config.identity_file):
                return str(Path(self._config.identity_file))
            elif self._config.identity_content:
                return self._write_temp_key(self._config.identity_content)

        # Check environment variables
        env_file = os.environ.get("SSH_IDENTITY_FILE")
        if env_file and os.path.exists(env_file):
            logger.debug("Using identity file from environment: %s", env_file)
            return str(Path(env_file))

        env_content = os.environ.get("SSH_IDENTITY_CONTENT")
        if env_content:
            logger.debug("Using identity content from environment")
            return self._write_temp_key(env_content)

        # Check SSH config
        config = self._parse_ssh_config()
        logger.debug("Checking SSH config for hostname %s: %s", hostname, config)

        def resolve_identity_file(identity_path: str) -> Optional[str]:
            """Resolve identity file path, handling both absolute and relative paths."""
            # First try as is
            if os.path.exists(identity_path):
                return str(Path(identity_path))

            # Try expanding home directory
            expanded_path = os.path.expanduser(identity_path)
            if os.path.exists(expanded_path):
                return str(Path(expanded_path))

            # Try relative to ssh dir
            relative_path = os.path.basename(identity_path)
            full_path = str(self._ssh_dir / relative_path)
            if os.path.exists(full_path):
                return full_path

            # If path starts with ~/.ssh/, try relative to ssh dir
            if identity_path.startswith("~/.ssh/"):
                ssh_relative_path = identity_path.replace("~/.ssh/", "")
                ssh_full_path = str(self._ssh_dir / ssh_relative_path)
                if os.path.exists(ssh_full_path):
                    return ssh_full_path

            return None

        # Try exact hostname match
        if hostname in config:
            logger.debug("Found exact match for hostname: %s", hostname)
            if "identityfile" in config[hostname]:
                identity_path = config[hostname]["identityfile"]
                logger.debug("Trying to resolve identity file: %s", identity_path)
                resolved_path = resolve_identity_file(identity_path)
                if resolved_path:
                    return resolved_path

        # Try pattern matching
        for pattern, settings in config.items():
            logger.debug("Checking pattern %s against hostname %s", pattern, hostname)
            if "*" in pattern and "identityfile" in settings and fnmatch.fnmatch(hostname, pattern):
                logger.debug("Pattern %s matched hostname %s", pattern, hostname)
                identity_path = settings["identityfile"]
                logger.debug("Trying to resolve identity file: %s", identity_path)
                resolved_path = resolve_identity_file(identity_path)
                if resolved_path:
                    return resolved_path

        # Try default key files
        logger.debug("Trying default key files")
        for key_name in ["id_ed25519", "id_rsa"]:
            identity_file = str(self._ssh_dir / key_name)
            if os.path.exists(identity_file):
                logger.debug("Using default key file: %s", identity_file)
                return identity_file

        # Return default path even if it doesn't exist
        default_key = str(self._ssh_dir / "id_rsa")
        logger.debug("Falling back to default key: %s", default_key)
        return default_key

    def _write_temp_key(self, key_content: str) -> Optional[str]:
        """Write key content to a temporary file.

        Args:
            key_content: SSH key content to write

        Returns:
            str: Path to temporary key file or None if operation failed
        """
        # Convert line endings to LF
        key_content = key_content.replace("\r\n", "\n")
        temp_key = None

        try:
            # Create temp file with proper permissions
            with NamedTemporaryFile(mode="w", delete=False) as temp_file:
                temp_key = temp_file.name
                temp_file.write(key_content)
            # Set proper permissions for SSH key
            if os.name != "nt":  # Skip on Windows
                os.chmod(temp_key, 0o600)
            return temp_key

        except (PermissionError, OSError) as e:
            if temp_key and os.path.exists(temp_key):
                with suppress(OSError):
                    os.unlink(temp_key)
            logger.error(f"Failed to write temporary key file: {e!s}")
            return None

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
            "hostname": lambda x: is_valid_hostname(x),
            "port": lambda x: str(x).isdigit() and 1 <= int(x) <= 65535,
            "user": lambda x: bool(x and not any(c in x for c in " \t\n\r")),
            "identityfile": lambda x: True,  # Path validation handled elsewhere
            "identitiesonly": lambda x: x.lower() in ("yes", "no"),
            "forwardagent": lambda x: x.lower() in ("yes", "no"),
            "proxycommand": lambda x: bool(x),
            "proxyhost": lambda x: is_valid_hostname(x),
            "proxyport": lambda x: str(x).isdigit() and 1 <= int(x) <= 65535,
            "proxyuser": lambda x: bool(x and not any(c in x for c in " \t\n\r")),
            "stricthostkeychecking": lambda x: x.lower() in ("yes", "no", "accept-new", "off", "ask"),
            "userknownhostsfile": lambda x: True,  # Path validation handled elsewhere
            "batchmode": lambda x: x.lower() in ("yes", "no"),
            "compression": lambda x: x.lower() in ("yes", "no"),
        }

        def is_valid_hostname(hostname: str) -> bool:
            """Check if a hostname is valid."""
            if not hostname or len(hostname) > 255:
                return False
            allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
            return all(c.lower() in allowed for c in hostname)

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

                    # Handle glob patterns
                    # Import built-in modules
                    import glob
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

    def get_git_ssh_command(self, hostname: str) -> Optional[str]:
        """Get Git SSH command with appropriate configuration.

        Args:
            hostname: Hostname to configure SSH for

        Returns:
            SSH command string or None if setup failed

        Note:
            The command includes:
            - Identity file configuration
            - StrictHostKeyChecking disabled
        """
        if not hostname:
            logger.error("No hostname provided")
            return None

        if not self.setup_ssh(hostname):
            return None

        identity_file = self._get_identity_file(hostname)
        if os.path.exists(identity_file):
            # Use forward slashes even on Windows
            identity_file = identity_file.replace("\\", "/")
            return f"ssh -i {identity_file} -o StrictHostKeyChecking=no"

        return None

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
