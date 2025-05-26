"""Git integration for SSH agent management."""

# Import built-in modules
import logging
import os
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Import third-party modules
from persistent_ssh_agent.constants import GitConstants
from persistent_ssh_agent.constants import SSHAgentConstants
from persistent_ssh_agent.utils import extract_hostname as _extract_hostname
from persistent_ssh_agent.utils import is_valid_hostname
from persistent_ssh_agent.utils import run_command


# Set up logger
logger = logging.getLogger(__name__)


class GitIntegration:
    """Git integration for SSH agent management.

    This class provides two main categories of functionality:
    1. SSH-based Git operations (get_git_ssh_command, _test_ssh_connection)
    2. Credential-based Git operations (setup_git_credentials, clear_credential_helpers)

    The credential-based operations are completely independent of SSH functionality
    and do not require SSH keys or SSH agent setup.
    """

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

        NOTE: This method is SSH-specific and requires SSH keys and SSH agent setup.
        It is NOT used by Git credential operations (git-setup, git-clear commands).

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
            result = run_command(["git", "config", "--global", "credential.helper", credential_helper])

            if not result or result.returncode != 0:
                logger.error("Failed to configure Git credential helper")
                return False

            logger.debug("Git credential helper configured successfully")
            return True

        except Exception as e:
            logger.error("Failed to configure Git credential helper: %s", str(e))
            return False

    def get_current_credential_helpers(self) -> List[str]:
        """Get current Git credential helpers.

        This method is completely independent of SSH functionality and only
        queries Git's credential helper configuration.

        Returns:
            List[str]: List of current credential helper configurations
        """
        try:
            result = run_command(["git", "config", "--global", "--get-all", "credential.helper"])
            if result and result.returncode == 0 and result.stdout:
                helpers = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
                return helpers
            return []
        except Exception as e:
            logger.debug("Failed to get current credential helpers: %s", str(e))
            return []

    def get_git_env_with_credentials(self, username: Optional[str] = None, password: Optional[str] = None) -> dict:
        """Get environment variables for Git commands with credentials.

        This method returns a dictionary of environment variables that can be used
        to run Git commands with temporary credentials without modifying global Git config.

        Args:
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            dict: Environment variables for Git commands

        Example:
            >>> agent = PersistentSSHAgent()
            >>> env = agent.git.get_git_env_with_credentials('user', 'pass')
            >>> subprocess.run(['git', 'clone', 'https://github.com/user/repo.git'], env=env)
        """
        # Import built-in modules
        import os

        # Start with current environment
        env = os.environ.copy()

        # Use provided credentials or fall back to environment variables
        git_username = username or os.environ.get("GIT_USERNAME")
        git_password = password or os.environ.get("GIT_PASSWORD")

        if git_username and git_password:
            # Set the credentials in environment variables for temporary use
            env["GIT_USERNAME"] = git_username
            env["GIT_PASSWORD"] = git_password

            logger.debug("Created Git environment with temporary credentials")
        else:
            logger.debug("No credentials provided, using existing environment")

        return env

    def run_git_command_with_credentials(
        self, command: List[str], username: Optional[str] = None, password: Optional[str] = None
    ) -> Optional[object]:
        """Run a Git command with temporary credentials.

        This method runs Git commands with temporary credentials without modifying
        global Git configuration.

        Args:
            command: Git command as list (e.g., ['git', 'clone', 'repo_url'])
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            Command result object or None if failed

        Example:
            >>> agent = PersistentSSHAgent()
            >>> result = agent.git.run_git_command_with_credentials(
            ...     ['git', 'submodule', 'update', '--init', '--recursive'],
            ...     username='user', password='pass'
            ... )
        """
        # Use provided credentials or fall back to environment variables
        git_username = username or os.environ.get("GIT_USERNAME")
        git_password = password or os.environ.get("GIT_PASSWORD")

        if not git_username or not git_password:
            logger.warning("No Git credentials provided, running command without authentication")
            return run_command(command)

        # Create credential helper command
        credential_helper = self._create_platform_credential_helper(git_username, git_password)

        # Add credential helper to the git command using -c option
        if command[0] == "git":
            # Insert the credential helper config before the git subcommand
            enhanced_command = [
                command[0],  # 'git'
                "-c",
                f"credential.helper={credential_helper}",
                *command[1:],  # rest of the command
            ]
        else:
            enhanced_command = command

        logger.debug("Running Git command with temporary credentials: %s", enhanced_command)
        return run_command(enhanced_command)

    def get_credential_helper_command(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> Optional[str]:
        """Get the credential helper command for temporary use.

        This method returns the credential helper command that can be used with
        'git -c credential.helper=<command>' for temporary authentication.

        Args:
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            str: Credential helper command if credentials provided, None otherwise

        Example:
            >>> agent = PersistentSSHAgent()
            >>> helper = agent.git.get_credential_helper_command('user', 'pass')
            >>> # Use with: git -c credential.helper="{helper}" clone repo_url
        """
        # Use provided credentials or fall back to environment variables
        git_username = username or os.environ.get("GIT_USERNAME")
        git_password = password or os.environ.get("GIT_PASSWORD")

        if not git_username or not git_password:
            logger.debug("No Git credentials provided for credential helper")
            return None

        # Create and return credential helper command
        credential_helper = self._create_platform_credential_helper(git_username, git_password)
        logger.debug("Generated credential helper command")
        return credential_helper

    def test_credentials(
        self,
        host: Optional[str] = None,
        timeout: int = 30,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Test Git credentials validity by attempting to access repositories.

        This method tests Git credentials by using 'git ls-remote' command to check
        if the credentials can successfully authenticate with Git repositories.

        Args:
            host: Specific host to test (e.g., 'github.com'). If None, tests common Git hosts.
            timeout: Timeout in seconds for each test (default: 30)
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            Dict[str, bool]: Dictionary mapping host names to test results (True = valid, False = invalid)

        Example:
            >>> agent = PersistentSSHAgent()
            >>> results = agent.git.test_credentials('github.com', username='user', password='token')
            >>> print(results)  # {'github.com': True}
        """
        if host:
            return {host: self._test_single_host_credentials(host, timeout, username, password)}
        else:
            return self._test_common_git_hosts_credentials(timeout, username, password)

    def _test_single_host_credentials(
        self, host: str, timeout: int, username: Optional[str] = None, password: Optional[str] = None
    ) -> bool:
        """Test credentials for a single Git host.

        Args:
            host: Git host to test (e.g., 'github.com')
            timeout: Timeout in seconds
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        try:
            # Use provided credentials or fall back to environment variables
            git_username = username or os.environ.get("GIT_USERNAME")
            git_password = password or os.environ.get("GIT_PASSWORD")

            if not git_username or not git_password:
                logger.debug("No credentials provided for testing host: %s", host)
                return False

            # Create a test repository URL for the host
            test_urls = self._get_test_urls_for_host(host)

            for test_url in test_urls:
                logger.debug("Testing credentials for %s with URL: %s", host, test_url)

                # Create credential helper command
                credential_helper = self._create_platform_credential_helper(git_username, git_password)

                # Run git ls-remote with credentials
                result = run_command(
                    ["git", "-c", f"credential.helper={credential_helper}", "ls-remote", test_url], timeout=timeout
                )

                if result and result.returncode == 0:
                    logger.debug("Credentials test successful for %s", host)
                    return True
                elif result and result.returncode != 0:
                    logger.debug("Credentials test failed for %s: %s", host, result.stderr)
                else:
                    logger.debug("Credentials test timed out or failed for %s", host)

            return False

        except Exception as e:
            logger.error("Error testing credentials for %s: %s", host, str(e))
            return False

    def _test_common_git_hosts_credentials(
        self, timeout: int, username: Optional[str] = None, password: Optional[str] = None
    ) -> Dict[str, bool]:
        """Test credentials for common Git hosting services.

        Args:
            timeout: Timeout in seconds for each test
            username: Git username (optional, uses GIT_USERNAME env var if not provided)
            password: Git password/token (optional, uses GIT_PASSWORD env var if not provided)

        Returns:
            Dict[str, bool]: Dictionary mapping host names to test results
        """
        common_hosts = ["github.com", "gitlab.com", "bitbucket.org"]

        results = {}
        for host in common_hosts:
            results[host] = self._test_single_host_credentials(host, timeout, username, password)

        return results

    def _get_test_urls_for_host(self, host: str) -> List[str]:
        """Get test repository URLs for a specific Git host.

        Args:
            host: Git host name

        Returns:
            List[str]: List of test URLs to try
        """
        # Map of hosts to their test repositories
        test_repos = {
            "github.com": ["https://github.com/octocat/Hello-World.git"],
            "gitlab.com": ["https://gitlab.com/gitlab-org/gitlab.git"],
            "bitbucket.org": ["https://bitbucket.org/atlassian/atlassian-frontend.git"],
        }

        # Return specific test URLs for known hosts, or create a generic one
        if host in test_repos:
            return test_repos[host]
        else:
            # For unknown hosts, try a generic test URL
            return [f"https://{host}/test/repo.git"]

    def clear_credential_helpers(self) -> bool:
        """Clear all existing Git credential helpers.

        This method is completely independent of SSH functionality and only
        modifies Git's credential helper configuration.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if there are any credential helpers to clear
            current_helpers = self.get_current_credential_helpers()
            if not current_helpers:
                logger.debug("No credential helpers to clear")
                return True

            logger.debug("Clearing %d existing credential helpers", len(current_helpers))

            # Clear all credential helpers
            result = run_command(["git", "config", "--global", "--unset-all", "credential.helper"])

            if not result or result.returncode != 0:
                logger.error("Failed to clear Git credential helpers")
                if result and result.stderr:
                    # Handle both string and bytes stderr output
                    stderr_msg = result.stderr
                    if isinstance(stderr_msg, bytes):
                        stderr_msg = stderr_msg.decode("utf-8", errors="replace")
                    logger.error("Git config error: %s", stderr_msg.strip())
                return False

            logger.debug("Successfully cleared all credential helpers")
            return True

        except Exception as e:
            logger.error("Failed to clear Git credential helpers: %s", str(e))
            return False

    def setup_git_credentials(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Set up Git credential helper with environment variables (simplified version).

        IMPORTANT: This method is completely independent of SSH functionality.
        It does NOT require SSH keys, SSH agent, or any SSH configuration.
        It only configures Git's credential helper system to use username/password authentication.

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

            # Check current credential helpers for debugging
            current_helpers = self.get_current_credential_helpers()
            if current_helpers:
                logger.debug("Current credential helpers found: %s", current_helpers)
                logger.debug("Will replace all existing credential helpers")
            else:
                logger.debug("No existing credential helpers found")

            # Create platform-specific credential helper command
            credential_helper = self._create_platform_credential_helper(git_username, git_password)

            logger.debug("Using credential helper command: %s", credential_helper)

            # Use --replace-all to handle multiple existing credential.helper values
            result = run_command(["git", "config", "--global", "--replace-all", "credential.helper", credential_helper])

            if not result or result.returncode != 0:
                logger.error("Failed to configure Git credential helper")
                if result and result.stderr:
                    # Handle both string and bytes stderr output
                    stderr_msg = result.stderr
                    if isinstance(stderr_msg, bytes):
                        stderr_msg = stderr_msg.decode("utf-8", errors="replace")
                    logger.error("Git config error: %s", stderr_msg.strip())

                    # Provide helpful suggestions for common errors
                    if "multiple values" in stderr_msg.lower():
                        logger.info("💡 Suggestion: Try clearing existing credential helpers first:")
                        logger.info("   uvx persistent_ssh_agent git-clear")
                        logger.info("   Then run git-setup again")
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
            credential_helper = f"!echo username={escaped_username}; echo password={escaped_password}"
        else:
            # Unix/Linux: Use bash compatible syntax
            credential_helper = f"!f() {{ echo username={escaped_username}; echo password={escaped_password}; }}; f"

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

        NOTE: This method is SSH-specific and is NOT used by Git credential operations.

        Args:
            hostname: Hostname to test connection with

        Returns:
            bool: True if connection successful
        """
        test_result = run_command(["ssh", "-T", "-o", "StrictHostKeyChecking=no", f"git@{hostname}"])

        if test_result is None:
            logger.error("SSH connection test failed")
            return False

        # Most Git servers return 1 for successful auth
        if test_result.returncode in [0, 1]:
            logger.debug("SSH connection test successful")
            return True

        logger.error("SSH connection test failed with code: %d", test_result.returncode)
        return False

    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of Git authentication systems.

        This method checks the status of Git credentials, SSH keys, network connectivity,
        and provides recommendations for improving authentication setup.

        Returns:
            Dict[str, Any]: Comprehensive health check results

        Example:
            >>> agent = PersistentSSHAgent()
            >>> health = agent.git.health_check()
            >>> print(health['overall'])  # 'healthy', 'warning', or 'error'
        """
        logger.debug("Starting Git authentication health check")

        health_status = {
            "overall": "healthy",
            "timestamp": time.time(),
            "git_credentials": self._check_git_credentials(),
            "ssh_keys": self._check_ssh_keys(),
            "network": self._check_network_connectivity(),
            "recommendations": [],
        }

        # Determine overall health status
        issues = []
        if health_status["git_credentials"]["status"] == "error":
            issues.append("git_credentials")
        if health_status["ssh_keys"]["status"] == "error":
            issues.append("ssh_keys")
        if health_status["network"]["status"] == "error":
            issues.append("network")

        if len(issues) >= 2:
            health_status["overall"] = "error"
        elif len(issues) == 1:
            health_status["overall"] = "warning"

        # Generate recommendations
        health_status["recommendations"] = self._generate_recommendations(health_status)

        logger.debug("Health check completed with overall status: %s", health_status["overall"])
        return health_status

    def clear_invalid_credentials(self, hosts: Optional[List[str]] = None) -> bool:
        """Clear invalid Git credential helpers.

        This method identifies and removes credential helpers that are no longer
        valid or accessible, helping to clean up Git configuration.

        Args:
            hosts: Optional list of hosts to check. If None, checks common Git hosts.
                  Currently not used but reserved for future functionality.

        Returns:
            bool: True if cleanup was successful, False otherwise

        Example:
            >>> agent = PersistentSSHAgent()
            >>> agent.git.clear_invalid_credentials(['github.com', 'gitlab.com'])
        """
        # Note: hosts parameter is reserved for future use
        _ = hosts
        logger.debug("Starting invalid credentials cleanup")

        try:
            # Get current credential helpers
            current_helpers = self.get_current_credential_helpers()
            if not current_helpers:
                logger.debug("No credential helpers found to check")
                return True

            # Test each credential helper
            invalid_helpers = []
            for helper in current_helpers:
                if not self._is_credential_helper_valid(helper):
                    invalid_helpers.append(helper)

            if not invalid_helpers:
                logger.debug("All credential helpers are valid")
                return True

            logger.info("Found %d invalid credential helpers", len(invalid_helpers))

            # Clear all credential helpers and reconfigure with valid ones
            if not self.clear_credential_helpers():
                logger.error("Failed to clear existing credential helpers")
                return False

            # Reconfigure with valid helpers only
            valid_helpers = [h for h in current_helpers if h not in invalid_helpers]
            for helper in valid_helpers:
                result = run_command(["git", "config", "--global", "--add", "credential.helper", helper])
                if not result or result.returncode != 0:
                    logger.warning("Failed to restore valid credential helper: %s", helper)

            logger.info("Successfully cleaned up invalid credential helpers")
            return True

        except Exception as e:
            logger.error("Failed to clear invalid credentials: %s", str(e))
            return False

    def setup_smart_credentials(self, host: str, strategy: str = "auto", **kwargs) -> bool:
        """Set up Git credentials using intelligent authentication strategy.

        This method uses the authentication strategy system to intelligently
        configure Git credentials based on the specified strategy and available
        authentication methods.

        Args:
            host: Target Git host (e.g., 'github.com')
            strategy: Authentication strategy ('auto', 'ssh_first', 'credentials_first', 'ssh_only')
            **kwargs: Additional parameters (username, password, etc.)

        Returns:
            bool: True if setup was successful, False otherwise

        Example:
            >>> agent = PersistentSSHAgent()
            >>> # Auto-detect best authentication method
            >>> agent.git.setup_smart_credentials('github.com', 'auto')
            >>> # Force SSH authentication
            >>> agent.git.setup_smart_credentials('github.com', 'ssh_only')
        """
        logger.debug("Setting up smart credentials for host: %s with strategy: %s", host, strategy)

        try:
            # Import here to avoid circular imports
            # Import third-party modules
            from persistent_ssh_agent.auth_strategy import AuthenticationStrategyFactory

            # Create authentication strategy
            auth_strategy = AuthenticationStrategyFactory.create_strategy(strategy, self._ssh_agent, **kwargs)

            # Attempt authentication
            success = auth_strategy.authenticate(host, **kwargs)

            if success:
                logger.info("Smart credentials setup successful for %s using strategy: %s", host, strategy)
                return True
            else:
                logger.error("Smart credentials setup failed for %s", host)
                return False

        except Exception as e:
            logger.error("Failed to setup smart credentials for %s: %s", host, str(e))
            return False

    def _check_git_credentials(self) -> Dict[str, Any]:
        """Check Git credentials status.

        Returns:
            Dict[str, Any]: Git credentials status information
        """
        try:
            # Get current credential helpers
            helpers = self.get_current_credential_helpers()

            # Test credentials with common hosts
            test_results = self.test_credentials()

            # Determine status
            if not helpers:
                status = "warning"
                message = "No credential helpers configured"
            elif any(test_results.values()):
                status = "healthy"
                message = "Credentials working for at least one host"
            else:
                status = "error"
                message = "Credentials not working for any tested hosts"

            return {"status": status, "message": message, "helpers": helpers, "test_results": test_results}

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to check Git credentials: {e}",
                "helpers": [],
                "test_results": {},
            }

    def _check_ssh_keys(self) -> Dict[str, Any]:
        """Check SSH keys status.

        Returns:
            Dict[str, Any]: SSH keys status information
        """
        try:
            # Check if SSH agent is running
            ssh_agent_active = getattr(self._ssh_agent, "_ssh_agent_started", False)

            # Test SSH connection to common Git hosts
            ssh_test_results = {}
            common_hosts = GitConstants.COMMON_GIT_HOSTS

            for host in common_hosts:
                try:
                    ssh_test_results[host] = self._ssh_agent._test_ssh_connection(host)
                except Exception:
                    ssh_test_results[host] = False

            # Determine status
            if not ssh_agent_active:
                status = "warning"
                message = "SSH agent not active"
            elif any(ssh_test_results.values()):
                status = "healthy"
                message = "SSH keys working for at least one host"
            else:
                status = "error"
                message = "SSH keys not working for any tested hosts"

            return {
                "status": status,
                "message": message,
                "ssh_agent_active": ssh_agent_active,
                "test_results": ssh_test_results,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to check SSH keys: {e}",
                "ssh_agent_active": False,
                "test_results": {},
            }

    def _check_network_connectivity(self) -> Dict[str, Any]:
        """Check network connectivity to Git hosts.

        Returns:
            Dict[str, Any]: Network connectivity status information
        """
        try:
            connectivity_results = {}
            common_hosts = GitConstants.COMMON_GIT_HOSTS

            for host in common_hosts:
                try:
                    # Simple connectivity test using git ls-remote
                    result = run_command(["git", "ls-remote", f"https://{host}/test/test.git"], timeout=10)

                    # Even if authentication fails, we can reach the host if we get a response
                    connectivity_results[host] = result is not None

                except Exception:
                    connectivity_results[host] = False

            # Determine status
            reachable_hosts = sum(connectivity_results.values())
            total_hosts = len(connectivity_results)

            if reachable_hosts == total_hosts:
                status = "healthy"
                message = "All Git hosts are reachable"
            elif reachable_hosts > 0:
                status = "warning"
                message = f"Only {reachable_hosts}/{total_hosts} Git hosts are reachable"
            else:
                status = "error"
                message = "No Git hosts are reachable"

            return {"status": status, "message": message, "connectivity_results": connectivity_results}

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to check network connectivity: {e}",
                "connectivity_results": {},
            }

    def _generate_recommendations(self, health_status: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on health check results.

        Args:
            health_status: Health check results

        Returns:
            List[str]: List of recommendations
        """
        recommendations = []

        try:
            # Git credentials recommendations
            git_creds = health_status.get("git_credentials", {})
            if git_creds.get("status") == "error":
                recommendations.append("Configure Git credentials using 'uvx persistent_ssh_agent git-setup'")
            elif git_creds.get("status") == "warning":
                recommendations.append("Consider setting up Git credentials for better authentication")

            # SSH keys recommendations
            ssh_keys = health_status.get("ssh_keys", {})
            if ssh_keys.get("status") == "error":
                recommendations.append("Set up SSH keys using 'uvx persistent_ssh_agent setup <hostname>'")
            elif not ssh_keys.get("ssh_agent_active", False):
                recommendations.append("Start SSH agent for better SSH key management")

            # Network connectivity recommendations
            network = health_status.get("network", {})
            if network.get("status") == "error":
                recommendations.append("Check network connectivity and firewall settings")
            elif network.get("status") == "warning":
                recommendations.append("Some Git hosts are unreachable - check network configuration")

            # General recommendations
            if health_status.get("overall") == "error":
                recommendations.append("Run 'uvx persistent_ssh_agent health-check --verbose' for detailed diagnostics")

        except Exception as e:
            logger.debug("Failed to generate recommendations: %s", str(e))
            recommendations.append("Run health check again for updated recommendations")

        return recommendations

    def _is_credential_helper_valid(self, helper: str) -> bool:
        """Check if a credential helper is valid and accessible.

        Args:
            helper: Credential helper configuration string

        Returns:
            bool: True if helper is valid, False otherwise
        """
        try:
            # Skip built-in helpers (they start with !)
            if helper.startswith("!"):
                return True

            # For file-based helpers, check if the file exists and is executable
            if os.path.exists(helper):
                return os.access(helper, os.X_OK) if os.name != "nt" else True

            # For system helpers (like 'manager', 'store'), assume they're valid
            # These are typically built into Git or the system
            system_helpers = ["manager", "store", "cache", "osxkeychain", "wincred"]
            return any(helper.endswith(sh) for sh in system_helpers)

        except Exception as e:
            logger.debug("Error checking credential helper validity: %s", str(e))
            return False
