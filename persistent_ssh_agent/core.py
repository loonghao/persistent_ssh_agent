"""SSH management module for repository updater."""

# Import built-in modules
from contextlib import suppress
import json
import logging
import os
import re
import subprocess
import time
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


logger = logging.getLogger(__name__)


class PersistentSSHAgent:
    """Handles persistent SSH agent operations and authentication.

    This class manages SSH agent persistence across sessions by saving and
    restoring agent information. It also handles SSH key management and
    authentication for various operations including Git.
    """

    def __init__(self):
        """Initialize SSH manager."""
        self._ssh_config_cache = {}
        self._ensure_home_env()
        self._ssh_agent_started = False
        self._agent_info_file = os.path.expanduser("~/.ssh/agent_info.json")

    def _ensure_home_env(self) -> None:
        """Ensure HOME environment variable is set correctly on Windows."""
        if os.name == "nt":
            # Set both HOME and USERPROFILE
            home = os.environ.get("USERPROFILE", "")
            if not home:
                home = os.path.expanduser("~")
            os.environ["HOME"] = home
            os.environ["USERPROFILE"] = home
            logger.debug("Set HOME and USERPROFILE to: %s", home)
        else:
            # On Unix-like systems, ensure HOME is set
            home = os.environ.get("HOME", "")
            if not home:
                home = os.path.expanduser("~")
                os.environ["HOME"] = home
                logger.debug("Set HOME to: %s", home)

    def _save_agent_info(self, auth_sock: str, agent_pid: str) -> None:
        """Save SSH agent information to file.

        Args:
            auth_sock: SSH_AUTH_SOCK value
            agent_pid: SSH_AGENT_PID value
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
        """
        try:
            if not os.path.exists(self._agent_info_file):
                return False

            with open(self._agent_info_file, "r") as f:
                agent_info = json.load(f)

            # Check if the agent info is recent (less than 24 hours old)
            if time.time() - agent_info.get("timestamp", 0) > 86400:
                return False

            # Check platform compatibility
            if agent_info.get("platform") != os.name:
                logger.debug("Agent info platform mismatch")
                return False

            # Set environment variables
            auth_sock = agent_info.get("SSH_AUTH_SOCK")
            agent_pid = agent_info.get("SSH_AGENT_PID")
            if not auth_sock or not agent_pid:
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
            except Exception:
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
        if self._ssh_agent_started:
            # Check if key is already loaded
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True,
                env=os.environ.copy()
            )
            if result.returncode == 0 and identity_file in result.stdout:
                return True

        try:
            # Try to load existing agent info first
            if self._load_agent_info():
                logger.debug("Reused existing SSH agent")
                return True

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
                text=True
            )

            if result.returncode != 0:
                return False

            # Parse and set environment variables
            auth_sock = None
            agent_pid = None

            for line in result.stdout.splitlines():
                if "SSH_AUTH_SOCK=" in line:
                    auth_sock = line.split("=")[1].split(";")[0].strip().strip('"\'')
                    os.environ["SSH_AUTH_SOCK"] = auth_sock
                elif "SSH_AGENT_PID=" in line:
                    agent_pid = line.split("=")[1].split(";")[0].strip().strip('"\'')
                    os.environ["SSH_AGENT_PID"] = agent_pid

            if auth_sock and agent_pid:
                self._save_agent_info(auth_sock, agent_pid)

            # Add the key
            result = subprocess.run(
                ["ssh-add", identity_file],
                capture_output=True,
                text=True,
                env=os.environ.copy()
            )

            if result.returncode != 0:
                logger.error("Failed to add key: %s", result.stderr)
                return False

            self._ssh_agent_started = True
            return True

        except Exception as e:
            logger.error("Failed to start SSH agent: %s", e)
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
            test_result = subprocess.run(
                ["ssh", "-T", "-o", "StrictHostKeyChecking=no", f"git@{hostname}"],
                capture_output=True,
                text=True,
                env=os.environ.copy()
            )

            # Most Git servers return 1 for successful auth
            return test_result.returncode in [0, 1]

        except Exception as e:
            logger.error("Error in SSH setup: %s", str(e))
            return False

    def _run_command(self, cmd: Union[str, List[str]], check_output: bool = True, shell: bool = False) -> Optional[
        subprocess.CompletedProcess]:
        """Run a command and handle its output.

        Args:
            cmd: Command and arguments to run (string or list)
            check_output: Whether to check command output
            shell: Whether to run command through shell

        Returns:
            CompletedProcess instance or None if command failed
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

    def _get_identity_file(self, hostname: str) -> str:
        """Get the identity file for a specific host.

        Args:
            hostname: Hostname to get identity file for

        Returns:
            Path to identity file
        """
        config = self._parse_ssh_config()

        # Try exact hostname match
        if hostname in config and "identityfile" in config[hostname]:
            return config[hostname]["identityfile"]

        # Try pattern matching
        for host_pattern, host_config in config.items():
            # Convert glob patterns to regex
            pattern = host_pattern.replace(".", "\\.").replace("*", ".*")
            if re.match(pattern, hostname) and "identityfile" in host_config:
                return host_config["identityfile"]

        # Default to ed25519 if exists, otherwise id_rsa
        ssh_dir = os.path.join(os.environ.get("HOME", ""), ".ssh")
        if os.path.exists(os.path.join(ssh_dir, "id_ed25519")):
            return os.path.join(ssh_dir, "id_ed25519")
        return os.path.join(ssh_dir, "id_rsa")

    def _parse_ssh_config(self) -> Dict[str, Dict[str, str]]:
        """Parse SSH config file to get host-specific configurations.

        Returns:
            Dictionary mapping hostnames to their configurations
        """
        if self._ssh_config_cache:
            return self._ssh_config_cache

        ssh_config_path = os.path.join(os.environ.get("HOME", ""), ".ssh", "config")
        if not os.path.exists(ssh_config_path):
            logger.debug("No SSH config file found at: %s", ssh_config_path)
            return {}

        current_host = None
        config = {}

        try:
            with open(ssh_config_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split(None, 1)
                    if len(parts) != 2:
                        continue

                    key, value = parts
                    key = key.lower()

                    if key == "host":
                        current_host = value
                        if current_host not in config:
                            config[current_host] = {}
                    elif current_host and key == "identityfile":
                        config[current_host]["identityfile"] = value.strip('"\'')
                    elif current_host and key == "user":
                        config[current_host]["user"] = value

            logger.debug("Parsed SSH config: %s", config)
            self._ssh_config_cache = config
            return config
        except Exception as e:
            logger.debug("Error parsing SSH config: %s", str(e))
            return {}

    def get_git_ssh_command(self, hostname: str) -> Optional[str]:
        """Get Git SSH command with appropriate configuration.

        Args:
            hostname: Hostname to configure SSH for

        Returns:
            SSH command string or None if setup failed
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
        """
        try:
            hostname = self._extract_hostname(repo_url)
            if not hostname:
                return False

            cmd = ["git", "clone"]
            if branch:
                cmd.extend(["-b", branch])
            cmd.extend([repo_url, target_dir])

            result = self._run_command(cmd)
            return result and result.returncode == 0

        except Exception as e:
            logger.error("Failed to clone repository: %s", e)
            return False

    def _extract_hostname(self, repo_url: str) -> Optional[str]:
        """Extract hostname from a repository URL.

        Args:
            repo_url: Repository URL to extract hostname from

        Returns:
            Hostname or None if extraction failed
        """
        try:
            # Handle SSH URLs like git@github.com:user/repo.git
            if "@" in repo_url:
                # Split after @ and before :
                return repo_url.split("@")[1].split(":")[0]
            return None
        except Exception as e:
            logger.error("Failed to extract hostname: %s", e)
            return None
