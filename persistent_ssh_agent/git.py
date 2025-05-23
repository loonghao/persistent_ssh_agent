"""Git integration for SSH agent management."""

# Import built-in modules
import logging
import os
from typing import List
from typing import Optional

# Import third-party modules
from persistent_ssh_agent.constants import SSHAgentConstants
from persistent_ssh_agent.utils import extract_hostname as _extract_hostname
from persistent_ssh_agent.utils import is_valid_hostname
from persistent_ssh_agent.utils import run_command


# Set up logger
logger = logging.getLogger(__name__)


class GitIntegration:
    """Git integration for SSH agent management."""

    def __init__(self, ssh_agent):
        """Initialize Git integration.

        Args:
            ssh_agent: PersistentSSHAgent instance
        """
        self._ssh_agent = ssh_agent

    def extract_hostname(self, url: str) -> Optional[str]:
        """Extract hostname from SSH URL (public method).

        This is a public wrapper around the _extract_hostname method.

        Args:
            url: SSH URL to extract hostname from (e.g., git@github.com:user/repo.git)

        Returns:
            str: Hostname if valid URL, None otherwise
        """
        return _extract_hostname(url)

    def _build_ssh_options(self, identity_file: str) -> List[str]:
        """Build SSH command options list.

        Args:
            identity_file: Path to SSH identity file

        Returns:
            List[str]: List of SSH command options
        """
        options = ["ssh"]

        # Add default options from SSHAgentConstants
        options.extend(SSHAgentConstants.SSH_DEFAULT_OPTIONS)

        # Add identity file
        options.extend(["-i", identity_file])

        # Add custom options from config
        if self._ssh_agent._config and self._ssh_agent._config.ssh_options:
            for key, value in self._ssh_agent._config.ssh_options.items():
                # Skip empty or invalid options
                if not key or not value:
                    logger.warning("Skipping invalid SSH option: %s=%s", key, value)
                    continue
                options.extend(["-o", f"{key}={value}"])

        return options

    def get_git_credential_command(self, credential_helper_path: str) -> Optional[str]:
        """Generate Git credential helper command.

        This method generates a command to use a credential helper script that
        reads username and password from environment variables.

        Args:
            credential_helper_path: Path to credential helper script

        Returns:
            str: Credential helper command if successful, None on error
        """
        try:
            # Validate credential helper path
            if not credential_helper_path or not os.path.exists(credential_helper_path):
                logger.error("Invalid credential helper path: %s", credential_helper_path)
                return None

            # Make sure the script is executable
            if os.name != "nt" and not os.access(credential_helper_path, os.X_OK):
                logger.warning("Making credential helper script executable: %s", credential_helper_path)
                try:
                    os.chmod(credential_helper_path, 0o755)
                except Exception as e:
                    logger.error("Failed to make credential helper executable: %s", e)
                    return None

            # Return the credential helper command
            credential_helper_path = credential_helper_path.replace("\\", "/")
            logger.debug("Using credential helper: %s", credential_helper_path)
            return credential_helper_path

        except Exception as e:
            logger.error("Failed to generate Git credential helper command: %s", str(e))
            return None

    def get_git_ssh_command(self, hostname: str) -> Optional[str]:
        """Generate Git SSH command with proper configuration.

        Args:
            hostname: Target Git host

        Returns:
            SSH command string if successful, None on error
        """
        try:
            # Validate hostname
            if not is_valid_hostname(hostname):
                logger.error("Invalid hostname: %s", hostname)
                return None

            # Get and validate identity file
            identity_file = self._ssh_agent._get_identity_file(hostname)
            if not identity_file:
                logger.error("No identity file found for: %s", hostname)
                return None

            if not os.path.exists(identity_file):
                logger.error("Identity file does not exist: %s", identity_file)
                return None

            # Set up SSH connection
            if not self._ssh_agent.setup_ssh(hostname):
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

    def configure_git_with_credential_helper(self, credential_helper_path: str) -> bool:
        """Configure Git to use a credential helper script.

        This method configures Git to use a credential helper script that reads
        username and password from environment variables (GIT_USERNAME and GIT_PASSWORD).

        Args:
            credential_helper_path: Path to credential helper script

        Returns:
            bool: True if successful, False otherwise

        Example:
            >>> agent = PersistentSSHAgent()
            >>> # Create a credential helper script
            >>> with open('/path/to/credential-helper.sh', 'w') as f:
            ...     f.write('#!/bin/bash\\necho username=$GIT_USERNAME\\necho password=$GIT_PASSWORD')
            >>> # Make it executable
            >>> import os
            >>> os.chmod('/path/to/credential-helper.sh', 0o755)
            >>> # Configure Git to use it
            >>> agent.git.configure_git_with_credential_helper('/path/to/credential-helper.sh')
            >>> # Set environment variables
            >>> os.environ['GIT_USERNAME'] = 'your-username'
            >>> os.environ['GIT_PASSWORD'] = 'your-password'
            >>> # Now Git commands will use these credentials
        """
        try:
            # Get credential helper command
            credential_helper = self.get_git_credential_command(credential_helper_path)
            if not credential_helper:
                return False

            # Configure Git to use the credential helper
            result = run_command([
                "git", "config", "--global", "credential.helper", credential_helper
            ])

            if not result or result.returncode != 0:
                logger.error("Failed to configure Git credential helper")
                return False

            logger.debug("Git credential helper configured successfully")
            return True

        except Exception as e:
            logger.error("Failed to configure Git credential helper: %s", str(e))
            return False

    def setup_git_credentials(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Set up Git credential helper with environment variables (simplified version).

        This simplified method handles all credential helper setup internally,
        eliminating the need for manual script creation and configuration.
        It automatically detects the operating system and uses the appropriate
        shell syntax for Windows (cmd/PowerShell) or Unix/Linux (bash).

        Args:
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            bool: True if successful, False otherwise

        Example:
            >>> agent = PersistentSSHAgent()
            >>> # Set credentials directly
            >>> agent.git.setup_git_credentials('myuser', 'mytoken')
            >>> # Or use environment variables
            >>> import os
            >>> os.environ['GIT_USERNAME'] = 'myuser'
            >>> os.environ['GIT_PASSWORD'] = 'mytoken'
            >>> agent.git.setup_git_credentials()
        """
        try:
            # Use provided credentials or fall back to environment variables
            git_username = username or os.environ.get("GIT_USERNAME")
            git_password = password or os.environ.get("GIT_PASSWORD")

            if not git_username or not git_password:
                logger.error("Git credentials not provided via parameters or environment variables")
                return False

            # Create platform-specific credential helper command
            credential_helper = self._create_platform_credential_helper(git_username, git_password)

            logger.debug("Using credential helper command: %s", credential_helper)

            result = run_command([
                "git", "config", "--global", "credential.helper", credential_helper
            ])

            if not result or result.returncode != 0:
                logger.error("Failed to configure Git credential helper")
                if result and result.stderr:
                    logger.error("Git config error: %s", result.stderr.decode().strip())
                return False

            logger.debug("Git credentials configured successfully")
            return True

        except Exception as e:
            logger.error("Failed to set up Git credentials: %s", str(e))
            return False

    def _create_platform_credential_helper(self, username: str, password: str) -> str:
        """Create platform-specific credential helper command.

        Args:
            username: Git username
            password: Git password/token

        Returns:
            str: Platform-specific credential helper command
        """
        # Escape special characters in credentials
        escaped_username = self._escape_credential_value(username)
        escaped_password = self._escape_credential_value(password)

        if os.name == "nt":
            # Windows: Use PowerShell compatible syntax
            # Use semicolon to separate commands (works in both cmd and PowerShell)
            credential_helper = (
                f"!echo username={escaped_username}; echo password={escaped_password}"
            )
        else:
            # Unix/Linux: Use bash compatible syntax
            credential_helper = (
                f"!f() {{ echo username={escaped_username}; echo password={escaped_password}; }}; f"
            )

        return credential_helper

    def _escape_credential_value(self, value: str) -> str:
        """Escape special characters in credential values.

        Args:
            value: Credential value to escape

        Returns:
            str: Escaped credential value
        """
        # Escape characters that could cause issues in shell commands
        # For both Windows and Unix, we need to handle quotes and special chars
        if os.name == "nt":
            # Windows cmd.exe escaping
            # Escape double quotes and percent signs
            return value.replace('"', '""').replace("%", "%%")

        # Unix/Linux bash escaping
        # Escape backslashes first, then double quotes, then single quotes
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "'\"'\"'")

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
