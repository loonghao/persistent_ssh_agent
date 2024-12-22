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
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


logger = logging.getLogger(__name__)


class SSHError(Exception):
    """Base exception for SSH-related errors."""
    pass


class PersistentSSHAgent:
    """Handles persistent SSH agent operations and authentication.

    This class manages SSH agent persistence across sessions by saving and
    restoring agent information. It also handles SSH key management and
    authentication for various operations including Git.
    """

    def __init__(self):
        """Initialize SSH manager."""
        self._ensure_home_env()
        self._ssh_dir = Path.home() / ".ssh"
        self._agent_info_file = self._ssh_dir / "agent_info.json"
        self._ssh_config_cache: Dict[str, Dict[str, Any]] = {}
        self._ssh_agent_started = False

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
            if time.time() - agent_info.get("timestamp", 0) > 86400:
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
                result = subprocess.run(
                    ["ssh-add", "-l"],
                    capture_output=True,
                    text=True,
                    env=os.environ.copy()
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

        Note:
            This method will:
            1. Kill any existing agents
            2. Start a new agent
            3. Add the specified identity
            4. Save agent info for persistence
        """
        try:
            # Ensure identity file exists and is absolute
            identity_file = os.path.abspath(os.path.expanduser(identity_file))
            if not os.path.exists(identity_file):
                logger.error("Identity file not found: %s", identity_file)
                return False

            # Kill any existing SSH agents
            if os.name == "nt":
                with suppress(Exception):  # Ignore errors if no agent is running
                    subprocess.run(["taskkill", "/F", "/IM", "ssh-agent.exe"],
                                capture_output=True, text=True)
            else:
                with suppress(Exception):  # Ignore errors if no agent is running or pkill not found
                    subprocess.run(["pkill", "ssh-agent"],
                                capture_output=True, text=True)

            # Start the SSH agent
            result = subprocess.run(
                ["ssh-agent", "-s"] if os.name != "nt" else ["ssh-agent"],
                capture_output=True,
                text=True,
                check=True
            )

            if result.returncode != 0:
                logger.error("Failed to start SSH agent: %s", result.stderr)
                return False

            # Parse agent output and set environment variables
            for line in result.stdout.splitlines():
                if "SSH_AUTH_SOCK" in line:
                    sock_match = re.search(r"SSH_AUTH_SOCK=([^;]+)", line)
                    if sock_match:
                        os.environ["SSH_AUTH_SOCK"] = sock_match.group(1)
                elif "SSH_AGENT_PID" in line:
                    pid_match = re.search(r"SSH_AGENT_PID=(\d+)", line)
                    if pid_match:
                        os.environ["SSH_AGENT_PID"] = pid_match.group(1)

            if "SSH_AUTH_SOCK" not in os.environ or "SSH_AGENT_PID" not in os.environ:
                logger.error("Failed to set SSH agent environment variables")
                return False

            # Add the identity
            result = subprocess.run(
                ["ssh-add", identity_file],
                capture_output=True,
                text=True,
                env=os.environ
            )

            if result.returncode != 0:
                logger.error("Failed to add identity: %s", result.stderr)
                return False

            # Save agent info for persistence
            self._save_agent_info(
                os.environ["SSH_AUTH_SOCK"],
                os.environ["SSH_AGENT_PID"]
            )
            self._ssh_agent_started = True
            return True

        except Exception as e:
            logger.error("SSH agent startup failed: %s", e)
            return False

    def setup_ssh(self, hostname: str) -> bool:
        """Set up SSH authentication for a host.

        Args:
            hostname: Hostname to set up SSH for

        Returns:
            True if setup successful, False otherwise

        Note:
            This method will:
            1. Get the correct identity file for the host
            2. Start the SSH agent with that identity
            3. Test the SSH connection
        """
        try:
            self._ensure_home_env()

            # Get the correct identity file
            identity_file = self._get_identity_file(hostname)
            if not identity_file:
                logger.warning("No identity file found for host: %s", hostname)
                return False

            if not os.path.exists(identity_file):
                logger.warning("Identity file not found: %s", identity_file)
                return False

            logger.debug("Using SSH key for %s: %s", hostname, identity_file)

            # Start SSH agent with the specific key
            if not self._start_ssh_agent(identity_file):
                logger.error("Failed to start SSH agent for %s", hostname)
                return False

            # Test SSH connection
            test_cmd = ["ssh", "-T", f"git@{hostname}"]
            result = self._run_command(test_cmd, check_output=False)

            # GitHub returns 1 for successful auth
            if result and (result.returncode == 0 or
                         (hostname == "github.com" and result.returncode == 1)):
                logger.debug("SSH setup successful for %s", hostname)
                return True

            logger.error("SSH setup failed for %s", hostname)
            return False

        except Exception as e:
            logger.error("SSH setup failed for %s: %s", hostname, e)
            return False

    def _run_command(
        self,
        cmd: Union[str, List[str]],
        check_output: bool = True,
        shell: bool = False
    ) -> Optional[subprocess.CompletedProcess]:
        """Run a command and handle its output.

        Args:
            cmd: Command and arguments to run
            check_output: Whether to check command output
            shell: Whether to run command through shell

        Returns:
            CompletedProcess instance or None if command failed

        Note:
            If check_output is True, command failure will return None
            If check_output is False, command result is returned regardless of exit code
        """
        try:
            logger.debug("Running command: %s", cmd)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                shell=shell
            )
            if check_output and result.returncode != 0:
                logger.debug("Command failed with code %d", result.returncode)
                logger.debug("stdout: %s", result.stdout)
                logger.debug("stderr: %s", result.stderr)
                return None
            return result
        except Exception as e:
            logger.error("Command execution failed: %s", e)
            return None

    def _get_identity_file(self, hostname: str) -> Optional[str]:
        """Get SSH identity file for a host.

        Args:
            hostname: Host to get identity file for

        Returns:
            str: Path to identity file or None if not found

        Note:
            The search order is:
            1. Exact match in SSH config
            2. Pattern match in SSH config (e.g. *.example.com)
            3. Default key files (id_ed25519, id_rsa)
        """
        config = self._parse_ssh_config()

        # Try exact hostname match first
        if hostname in config and "identityfile" in config[hostname]:
            identity_file = os.path.expanduser(config[hostname]["identityfile"])
            return str(Path(identity_file))

        # Try pattern matching
        for pattern, settings in config.items():
            if "*" in pattern and "identityfile" in settings and fnmatch.fnmatch(hostname, pattern):
                # Convert SSH config pattern to fnmatch pattern
                # SSH uses * and ? as wildcards, which is compatible with fnmatch
                identity_file = os.path.expanduser(settings["identityfile"])
                return str(Path(identity_file))

        # Default to standard key files if no match in config
        for key_name in ["id_ed25519", "id_rsa"]:
            key_path = self._ssh_dir / key_name
            if key_path.exists():
                return str(key_path)

        return str(self._ssh_dir / "id_rsa")  # Return default path even if it doesn't exist

    def _parse_ssh_config(self) -> Dict[str, Dict[str, str]]:
        """Parse SSH config file to get host-specific configurations.

        Returns:
            dict: SSH configuration mapping hostnames to their settings

        Note:
            Config format example:
            Host github.com
                IdentityFile ~/.ssh/id_ed25519
                User git
        """
        if self._ssh_config_cache:
            return self._ssh_config_cache

        ssh_config_path = self._ssh_dir / "config"
        if not ssh_config_path.exists():
            logger.debug("No SSH config file found at: %s", ssh_config_path)
            return {}

        config = {}
        current_host = None

        def is_valid_value(value: str) -> bool:
            """Check if a value has valid syntax."""
            if not value:
                return False
            # Check for invalid syntax characters at start
            if any(value.startswith(c) for c in ("=", ":", '"', "'")):
                return False
            # Check for invalid syntax in value
            return not any(c in value for c in ("=", ":"))

        try:
            with open(ssh_config_path) as f:
                for line in f:
                    # Remove comments and strip whitespace
                    if "#" in line:
                        line = line[:line.index("#")]
                    line = line.strip()

                    if not line:
                        continue

                    # Split into key and value
                    parts = line.split(None, 1)
                    if not parts:
                        continue

                    key = parts[0].lower()

                    # Handle Host directive
                    if key == "host":
                        current_host = None  # Reset current host
                        if len(parts) > 1:
                            host_value = parts[1].strip()
                            if is_valid_value(host_value):
                                current_host = host_value
                                if current_host not in config:
                                    config[current_host] = {}
                        continue

                    # Skip if no valid host context
                    if not current_host:
                        continue

                    # Handle other directives
                    if key not in ("identityfile", "user"):
                        continue

                    if len(parts) <= 1:  # No value provided
                        continue

                    value = parts[1].strip()
                    if is_valid_value(value):
                        config[current_host][key] = value

            self._ssh_config_cache = config
            return config
        except Exception as e:
            logger.error("Failed to parse SSH config: %s", e)
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

    def clone_repository(self, repo_url: str, target_dir: str, branch: Optional[str] = None) -> bool:
        """Clone a Git repository using SSH.

        Args:
            repo_url: Repository URL to clone from
            target_dir: Directory to clone into
            branch: Optional branch to clone

        Returns:
            True if clone successful, False otherwise

        Note:
            This method will:
            1. Extract hostname from repo URL
            2. Set up SSH for that host
            3. Clone the repository
        """
        try:
            hostname = self._extract_hostname(repo_url)
            if not hostname:
                logger.error("Failed to extract hostname from URL: %s", repo_url)
                return False

            cmd = ["git", "clone"]
            if branch:
                cmd.extend(["-b", branch])
            cmd.extend([repo_url, target_dir])

            result = self._run_command(cmd)
            if result is None:
                return False
            return result.returncode == 0

        except Exception as e:
            logger.error("Failed to clone repository: %s", e)
            return False

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
