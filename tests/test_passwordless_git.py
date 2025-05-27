"""Tests for passwordless Git operations."""

# Import built-in modules
import os
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent import PersistentSSHAgent


class TestPasswordlessGit:
    """Test passwordless Git operations."""

    def setup_method(self):
        """Set up test environment."""
        self.ssh_agent = PersistentSSHAgent()

    def test_extract_hostname_from_git_command_ssh_url(self):
        """Test extracting hostname from Git command with SSH URL."""
        command = ["git", "clone", "git@github.com:user/repo.git"]
        hostname = self.ssh_agent._extract_hostname_from_git_command(command)
        assert hostname == "github.com"

    def test_extract_hostname_from_git_command_https_url(self):
        """Test extracting hostname from Git command with HTTPS URL."""
        command = ["git", "clone", "https://github.com/user/repo.git"]
        hostname = self.ssh_agent._extract_hostname_from_git_command(command)
        assert hostname == "github.com"

    def test_extract_hostname_from_git_command_no_url(self):
        """Test extracting hostname from Git command without URL."""
        command = ["git", "status"]
        hostname = self.ssh_agent._extract_hostname_from_git_command(command)
        assert hostname is None

    def test_are_credentials_available_with_params(self):
        """Test checking credentials availability with parameters."""
        result = self.ssh_agent._are_credentials_available("user", "pass")
        assert result is True

    def test_are_credentials_available_with_env_vars(self):
        """Test checking credentials availability with environment variables."""
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            result = self.ssh_agent._are_credentials_available()
            assert result is True

    def test_are_credentials_available_missing(self):
        """Test checking credentials availability when missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = self.ssh_agent._are_credentials_available()
            assert result is False

    @patch("persistent_ssh_agent.core.run_command")
    def test_run_git_command_passwordless_ssh_preferred(self, mock_run_command):
        """Test running Git command with SSH preferred."""
        # Mock successful SSH setup
        with patch.object(self.ssh_agent, "_is_ssh_available_for_host", return_value=True), \
             patch.object(self.ssh_agent, "_run_git_command_with_ssh") as mock_ssh_run:

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_ssh_run.return_value = mock_result

            command = ["git", "clone", "git@github.com:user/repo.git"]
            result = self.ssh_agent.run_git_command_passwordless(command)

            assert result == mock_result
            mock_ssh_run.assert_called_once_with(command, "github.com")

    @patch("persistent_ssh_agent.core.run_command")
    def test_run_git_command_passwordless_credentials_preferred(self, mock_run_command):
        """Test running Git command with credentials preferred."""
        # Mock successful credential setup
        with patch.object(self.ssh_agent, "_are_credentials_available", return_value=True), \
             patch.object(self.ssh_agent.git, "run_git_command_with_credentials") as mock_cred_run:

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_cred_run.return_value = mock_result

            command = ["git", "clone", "https://github.com/user/repo.git"]
            result = self.ssh_agent.run_git_command_passwordless(
                command, username="user", password="pass", prefer_ssh=False
            )

            assert result == mock_result
            mock_cred_run.assert_called_once_with(command, "user", "pass")

    @patch("persistent_ssh_agent.core.run_command")
    def test_run_git_command_passwordless_fallback_to_credentials(self, mock_run_command):
        """Test running Git command with SSH failing and falling back to credentials."""
        # Mock SSH failure and credential success
        with patch.object(self.ssh_agent, "_is_ssh_available_for_host", return_value=True), \
             patch.object(self.ssh_agent, "_are_credentials_available", return_value=True), \
             patch.object(self.ssh_agent, "_run_git_command_with_ssh") as mock_ssh_run, \
             patch.object(self.ssh_agent.git, "run_git_command_with_credentials") as mock_cred_run:

            # SSH fails
            mock_ssh_result = MagicMock()
            mock_ssh_result.returncode = 1
            mock_ssh_run.return_value = mock_ssh_result

            # Credentials succeed
            mock_cred_result = MagicMock()
            mock_cred_result.returncode = 0
            mock_cred_run.return_value = mock_cred_result

            command = ["git", "clone", "git@github.com:user/repo.git"]
            result = self.ssh_agent.run_git_command_passwordless(
                command, username="user", password="pass"
            )

            assert result == mock_cred_result
            mock_ssh_run.assert_called_once()
            mock_cred_run.assert_called_once()

    @patch("persistent_ssh_agent.core.run_command")
    def test_run_git_command_passwordless_no_auth_available(self, mock_run_command):
        """Test running Git command with no authentication available."""
        mock_result = MagicMock()
        mock_run_command.return_value = mock_result

        with patch.object(self.ssh_agent, "_is_ssh_available_for_host", return_value=False), \
             patch.object(self.ssh_agent, "_are_credentials_available", return_value=False):

            command = ["git", "status"]
            result = self.ssh_agent.run_git_command_passwordless(command)

            assert result == mock_result
            mock_run_command.assert_called_once_with(command)

    def test_is_ssh_available_for_host_no_identity_file(self):
        """Test SSH availability check when no identity file exists."""
        with patch.object(self.ssh_agent, "_get_identity_file", return_value=None):
            result = self.ssh_agent._is_ssh_available_for_host("github.com")
            assert result is False

    def test_is_ssh_available_for_host_key_loaded(self):
        """Test SSH availability check when key is already loaded."""
        with patch.object(self.ssh_agent, "_get_identity_file", return_value="/path/to/key"), \
             patch("os.path.exists", return_value=True), \
             patch.object(self.ssh_agent, "_verify_loaded_key", return_value=True):

            self.ssh_agent._ssh_agent_started = True
            result = self.ssh_agent._is_ssh_available_for_host("github.com")
            assert result is True

    @patch("persistent_ssh_agent.core.run_command")
    def test_run_git_command_with_ssh_success(self, mock_run_command):
        """Test running Git command with SSH authentication."""
        mock_result = MagicMock()
        mock_run_command.return_value = mock_result

        with patch.object(self.ssh_agent, "setup_ssh", return_value=True), \
             patch.object(self.ssh_agent.git, "get_git_ssh_command", return_value="ssh -i /path/to/key"):

            command = ["git", "clone", "git@github.com:user/repo.git"]
            result = self.ssh_agent._run_git_command_with_ssh(command, "github.com")

            assert result == mock_result
            # Verify that GIT_SSH_COMMAND was set in environment
            call_args = mock_run_command.call_args
            assert call_args[1]["env"]["GIT_SSH_COMMAND"] == "ssh -i /path/to/key"

    def test_run_git_command_with_ssh_setup_failure(self):
        """Test running Git command with SSH when setup fails."""
        with patch.object(self.ssh_agent, "setup_ssh", return_value=False):
            command = ["git", "clone", "git@github.com:user/repo.git"]
            result = self.ssh_agent._run_git_command_with_ssh(command, "github.com")
            assert result is None

    def test_run_git_command_with_ssh_no_ssh_command(self):
        """Test running Git command with SSH when SSH command generation fails."""
        with patch.object(self.ssh_agent, "setup_ssh", return_value=True), \
             patch.object(self.ssh_agent.git, "get_git_ssh_command", return_value=None):

            command = ["git", "clone", "git@github.com:user/repo.git"]
            result = self.ssh_agent._run_git_command_with_ssh(command, "github.com")
            assert result is None
