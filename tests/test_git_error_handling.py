"""Tests for Git integration error handling and edge cases."""

# Import built-in modules
import os
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

# Import third-party modules
import pytest
from persistent_ssh_agent.git import GitIntegration
from persistent_ssh_agent.utils import run_command


class TestGitIntegrationErrorHandling:
    """Test error handling and edge cases in GitIntegration."""

    @pytest.fixture
    def mock_ssh_agent(self):
        """Create a mock SSH agent for testing."""
        agent = MagicMock()
        agent._ssh_agent_started = True
        agent._config = None
        agent._get_identity_file.return_value = "/path/to/key"
        agent.setup_ssh.return_value = True
        return agent

    @pytest.fixture
    def git_integration(self, mock_ssh_agent):
        """Create a GitIntegration instance for testing."""
        return GitIntegration(mock_ssh_agent)

    def test_extract_hostname_invalid_url(self, git_integration):
        """Test extract_hostname with invalid URL."""
        assert git_integration.extract_hostname("") is None
        assert git_integration.extract_hostname("invalid-url") is None
        assert git_integration.extract_hostname("http://github.com") is None
        assert git_integration.extract_hostname(None) is None

    def test_build_ssh_options_with_config(self, git_integration):
        """Test _build_ssh_options with SSH config."""
        # Test with config containing SSH options
        git_integration._ssh_agent._config = MagicMock()
        git_integration._ssh_agent._config.ssh_options = {
            "StrictHostKeyChecking": "no",
            "UserKnownHostsFile": "/dev/null",
            "": "invalid",  # Empty key
            "ValidKey": "",  # Empty value
        }

        options = git_integration._build_ssh_options("/path/to/key")

        # Should include valid options and skip invalid ones
        assert "ssh" in options
        assert "-i" in options
        assert "/path/to/key" in options
        assert "-o" in options
        assert "StrictHostKeyChecking=no" in options
        assert "UserKnownHostsFile=/dev/null" in options

    def test_build_ssh_options_no_config(self, git_integration):
        """Test _build_ssh_options without config."""
        git_integration._ssh_agent._config = None

        options = git_integration._build_ssh_options("/path/to/key")

        assert "ssh" in options
        assert "-i" in options
        assert "/path/to/key" in options

    def test_get_git_credential_command_invalid_path(self, git_integration):
        """Test get_git_credential_command with invalid paths."""
        # Test with empty path
        assert git_integration.get_git_credential_command("") is None

        # Test with non-existent path
        assert git_integration.get_git_credential_command("/non/existent/path") is None

    @patch('os.path.exists')
    @patch('os.access')
    @patch('os.chmod')
    def test_get_git_credential_command_chmod_failure(self, mock_chmod, mock_access, mock_exists, git_integration):
        """Test get_git_credential_command when chmod fails."""
        mock_exists.return_value = True
        mock_access.return_value = False  # Not executable
        mock_chmod.side_effect = PermissionError("Permission denied")

        with patch('os.name', 'posix'):
            result = git_integration.get_git_credential_command("/path/to/script")
            assert result is None

    def test_get_git_ssh_command_invalid_hostname(self, git_integration):
        """Test get_git_ssh_command with invalid hostname."""
        result = git_integration.get_git_ssh_command("invalid..hostname")
        assert result is None

    def test_get_git_ssh_command_no_identity_file(self, git_integration):
        """Test get_git_ssh_command when no identity file found."""
        git_integration._ssh_agent._get_identity_file.return_value = None

        result = git_integration.get_git_ssh_command("github.com")
        assert result is None

    def test_get_git_ssh_command_identity_file_not_exists(self, git_integration):
        """Test get_git_ssh_command when identity file doesn't exist."""
        git_integration._ssh_agent._get_identity_file.return_value = "/non/existent/key"

        result = git_integration.get_git_ssh_command("github.com")
        assert result is None

    def test_get_git_ssh_command_ssh_setup_fails(self, git_integration):
        """Test get_git_ssh_command when SSH setup fails."""
        git_integration._ssh_agent.setup_ssh.return_value = False

        with patch('os.path.exists', return_value=True):
            result = git_integration.get_git_ssh_command("github.com")
            assert result is None

    @patch('persistent_ssh_agent.git.run_command')
    def test_configure_git_with_credential_helper_failure(self, mock_run_command, git_integration):
        """Test configure_git_with_credential_helper when git config fails."""
        # Mock successful credential helper creation but failed git config
        with patch.object(git_integration, 'get_git_credential_command', return_value="/path/to/helper"):
            mock_run_command.return_value = MagicMock(returncode=1)

            result = git_integration.configure_git_with_credential_helper("/path/to/helper")
            assert result is False

    @patch('persistent_ssh_agent.git.run_command')
    def test_configure_git_with_credential_helper_no_result(self, mock_run_command, git_integration):
        """Test configure_git_with_credential_helper when run_command returns None."""
        with patch.object(git_integration, 'get_git_credential_command', return_value="/path/to/helper"):
            mock_run_command.return_value = None

            result = git_integration.configure_git_with_credential_helper("/path/to/helper")
            assert result is False

    @patch('persistent_ssh_agent.git.run_command')
    def test_get_current_credential_helpers_exception(self, mock_run_command, git_integration):
        """Test get_current_credential_helpers when exception occurs."""
        mock_run_command.side_effect = Exception("Command failed")

        result = git_integration.get_current_credential_helpers()
        assert result == []

    @patch('persistent_ssh_agent.git.run_command')
    def test_clear_credential_helpers_failure(self, mock_run_command, git_integration):
        """Test clear_credential_helpers when git config fails."""
        # Mock existing helpers
        with patch.object(git_integration, 'get_current_credential_helpers', return_value=["helper1"]):
            mock_run_command.return_value = MagicMock(returncode=1, stderr="Error message")

            result = git_integration.clear_credential_helpers()
            assert result is False

    @patch('persistent_ssh_agent.git.run_command')
    def test_clear_credential_helpers_no_result(self, mock_run_command, git_integration):
        """Test clear_credential_helpers when run_command returns None."""
        with patch.object(git_integration, 'get_current_credential_helpers', return_value=["helper1"]):
            mock_run_command.return_value = None

            result = git_integration.clear_credential_helpers()
            assert result is False

    def test_run_git_command_with_credentials_no_credentials(self, git_integration):
        """Test run_git_command_with_credentials without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('persistent_ssh_agent.git.run_command') as mock_run:
                mock_run.return_value = MagicMock()

                result = git_integration.run_git_command_with_credentials(["git", "status"])
                mock_run.assert_called_once_with(["git", "status"])

    def test_run_git_command_with_credentials_helper_creation_fails(self, git_integration):
        """Test run_git_command_with_credentials when helper creation fails."""
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(git_integration, '_create_credential_helper_file', return_value=None):
                result = git_integration.run_git_command_with_credentials(["git", "status"])
                assert result is None

    def test_get_credential_helper_command_no_credentials(self, git_integration):
        """Test get_credential_helper_command without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            result = git_integration.get_credential_helper_command()
            assert result is None

    def test_test_single_host_credentials_no_credentials(self, git_integration):
        """Test _test_single_host_credentials without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            result = git_integration._test_single_host_credentials("github.com", 30)
            assert result is False

    def test_test_single_host_credentials_helper_creation_fails(self, git_integration):
        """Test _test_single_host_credentials when helper creation fails."""
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(git_integration, '_create_credential_helper_file', return_value=None):
                result = git_integration._test_single_host_credentials("github.com", 30)
                assert result is False

    @patch('persistent_ssh_agent.git.run_command')
    def test_test_single_host_credentials_command_fails(self, mock_run_command, git_integration):
        """Test _test_single_host_credentials when git command fails."""
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(git_integration, '_create_credential_helper_file', return_value="/path/to/helper"):
                # Mock all git ls-remote calls to fail
                mock_run_command.return_value = MagicMock(returncode=1, stderr="Auth failed")

                result = git_integration._test_single_host_credentials("github.com", 30)
                assert result is False

    @patch('persistent_ssh_agent.git.run_command')
    def test_test_single_host_credentials_command_timeout(self, mock_run_command, git_integration):
        """Test _test_single_host_credentials when git command times out."""
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(git_integration, '_create_credential_helper_file', return_value="/path/to/helper"):
                # Mock git ls-remote to timeout (return None)
                mock_run_command.return_value = None  # Timeout

                result = git_integration._test_single_host_credentials("github.com", 30)
                assert result is False

    def test_test_single_host_credentials_exception(self, git_integration):
        """Test _test_single_host_credentials when exception occurs."""
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(git_integration, '_create_credential_helper_file', side_effect=Exception("Error")):
                result = git_integration._test_single_host_credentials("github.com", 30)
                assert result is False

    def test_get_test_urls_for_host_unknown_host(self, git_integration):
        """Test _get_test_urls_for_host with unknown host."""
        urls = git_integration._get_test_urls_for_host("unknown.example.com")
        assert len(urls) == 1
        assert "unknown.example.com" in urls[0]
        assert urls[0] == "https://unknown.example.com/test/repo.git"
