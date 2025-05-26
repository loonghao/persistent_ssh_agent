"""Tests for Git-related CLI commands."""

import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from persistent_ssh_agent.cli import main


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


def test_git_debug_command(runner):
    """Test git-debug CLI command."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class, \
         patch("persistent_ssh_agent.cli.run_command") as mock_run_command:

        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = ["helper1", "helper2"]

        # Mock run_command for git config
        mock_run_command.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="file:/path/to/.gitconfig\tcredential.helper=helper1\n"
        )

        # Mock environment variables
        with patch.dict("os.environ", {"GIT_USERNAME": "testuser", "GIT_PASSWORD": "testpass"}):
            result = runner.invoke(main, ["git-debug"])

        assert result.exit_code == 0
        assert "Git Credential Configuration Debug" in result.output
        assert "Current credential helpers:" in result.output
        assert "helper1" in result.output
        assert "helper2" in result.output
        assert "GIT_USERNAME: testuser" in result.output
        assert "GIT_PASSWORD: (set, hidden)" in result.output


def test_git_debug_command_no_helpers(runner):
    """Test git-debug CLI command with no credential helpers."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = []

        result = runner.invoke(main, ["git-debug"])

        assert result.exit_code == 0
        assert "No credential helpers currently configured" in result.output
        assert "No credential helpers configured" in result.output


def test_git_clear_command_with_helpers(runner):
    """Test git-clear CLI command with existing helpers."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = ["helper1", "helper2"]
        mock_agent.git.clear_credential_helpers.return_value = True

        # Use --confirm to skip the confirmation prompt
        result = runner.invoke(main, ["git-clear", "--confirm"])

        assert result.exit_code == 0
        assert "credential helper(s) to clear" in result.output
        assert "helper1" in result.output
        assert "helper2" in result.output
        assert "Successfully cleared all Git credential helpers" in result.output
        mock_agent.git.clear_credential_helpers.assert_called_once()


def test_git_clear_command_no_helpers(runner):
    """Test git-clear CLI command with no existing helpers."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = []

        result = runner.invoke(main, ["git-clear"])

        assert result.exit_code == 0
        assert "No credential helpers found to clear" in result.output


def test_git_clear_command_with_confirmation(runner):
    """Test git-clear CLI command with user confirmation."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = ["helper1"]
        mock_agent.git.clear_credential_helpers.return_value = True

        # Simulate user confirming the action
        result = runner.invoke(main, ["git-clear"], input="y\n")

        assert result.exit_code == 0
        assert "Are you sure you want to clear all credential helpers?" in result.output
        assert "Successfully cleared all Git credential helpers" in result.output
        mock_agent.git.clear_credential_helpers.assert_called_once()


def test_git_clear_command_user_cancels(runner):
    """Test git-clear CLI command when user cancels."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = ["helper1"]

        # Simulate user canceling the action
        result = runner.invoke(main, ["git-clear"], input="n\n")

        assert result.exit_code == 0
        assert "Operation cancelled" in result.output
        mock_agent.git.clear_credential_helpers.assert_not_called()


def test_git_clear_command_failure(runner):
    """Test git-clear CLI command when clearing fails."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.get_current_credential_helpers.return_value = ["helper1"]
        mock_agent.git.clear_credential_helpers.return_value = False

        result = runner.invoke(main, ["git-clear", "--confirm"])

        assert result.exit_code == 1
        assert "Failed to clear Git credential helpers" in result.output


def test_git_setup_command_with_multiple_values_suggestion(runner):
    """Test git-setup command shows suggestion for multiple values error."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent and its git methods
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.git.setup_git_credentials.return_value = False

        result = runner.invoke(main, ["git-setup", "--username", "testuser", "--password", "testpass"])

        assert result.exit_code == 1
        assert "Failed to configure Git credentials" in result.output


def test_git_debug_command_with_exception(runner):
    """Test git-debug CLI command when an exception occurs."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent to raise an exception
        mock_agent_class.side_effect = Exception("Test exception")

        result = runner.invoke(main, ["git-debug"])

        assert result.exit_code == 1
        assert "Failed to debug Git configuration" in result.output


def test_git_clear_command_with_exception(runner):
    """Test git-clear CLI command when an exception occurs."""
    with patch("persistent_ssh_agent.cli.PersistentSSHAgent") as mock_agent_class:
        # Mock the SSH agent to raise an exception
        mock_agent_class.side_effect = Exception("Test exception")

        result = runner.invoke(main, ["git-clear"])

        assert result.exit_code == 1
        assert "Failed to clear Git credential helpers" in result.output


# Tests for new Git credential functionality
def test_git_integration_get_git_env_with_credentials():
    """Test GitIntegration.get_git_env_with_credentials method."""
    from persistent_ssh_agent import PersistentSSHAgent

    agent = PersistentSSHAgent()

    # Test with direct credentials
    env = agent.git.get_git_env_with_credentials("testuser", "testpass")

    assert "GIT_USERNAME" in env
    assert "GIT_PASSWORD" in env
    assert env["GIT_USERNAME"] == "testuser"
    assert env["GIT_PASSWORD"] == "testpass"


def test_git_integration_get_git_env_with_credentials_from_env():
    """Test GitIntegration.get_git_env_with_credentials method with environment variables."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch.dict(os.environ, {"GIT_USERNAME": "envuser", "GIT_PASSWORD": "envpass"}):
        agent = PersistentSSHAgent()
        env = agent.git.get_git_env_with_credentials()

        assert "GIT_USERNAME" in env
        assert "GIT_PASSWORD" in env
        assert env["GIT_USERNAME"] == "envuser"
        assert env["GIT_PASSWORD"] == "envpass"


def test_git_integration_get_git_env_with_credentials_no_credentials():
    """Test GitIntegration.get_git_env_with_credentials method without credentials."""
    from persistent_ssh_agent import PersistentSSHAgent

    # Only clear Git-related environment variables, keep HOME
    env_to_clear = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    with patch.dict(os.environ, env_to_clear, clear=True):
        agent = PersistentSSHAgent()
        env = agent.git.get_git_env_with_credentials()

        # Should return environment but without setting GIT_USERNAME/GIT_PASSWORD
        assert isinstance(env, dict)


def test_git_integration_get_credential_helper_command():
    """Test GitIntegration.get_credential_helper_command method."""
    from persistent_ssh_agent import PersistentSSHAgent

    agent = PersistentSSHAgent()

    # Test with direct credentials
    helper = agent.git.get_credential_helper_command("testuser", "testpass")

    assert helper is not None
    assert "testuser" in helper
    assert "testpass" in helper


def test_git_integration_get_credential_helper_command_from_env():
    """Test GitIntegration.get_credential_helper_command method with environment variables."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch.dict(os.environ, {"GIT_USERNAME": "envuser", "GIT_PASSWORD": "envpass"}):
        agent = PersistentSSHAgent()
        helper = agent.git.get_credential_helper_command()

        assert helper is not None
        assert "envuser" in helper
        assert "envpass" in helper


def test_git_integration_get_credential_helper_command_no_credentials():
    """Test GitIntegration.get_credential_helper_command method without credentials."""
    from persistent_ssh_agent import PersistentSSHAgent

    # Only clear Git-related environment variables, keep HOME
    env_to_clear = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    with patch.dict(os.environ, env_to_clear, clear=True):
        agent = PersistentSSHAgent()
        helper = agent.git.get_credential_helper_command()

        assert helper is None


def test_git_integration_run_git_command_with_credentials():
    """Test GitIntegration.run_git_command_with_credentials method."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        agent = PersistentSSHAgent()
        result = agent.git.run_git_command_with_credentials(
            ["git", "--version"],
            username="testuser",
            password="testpass"
        )

        assert result is not None
        assert result.returncode == 0

        # Verify the command was enhanced with credential helper
        mock_run.assert_called_once()
        called_command = mock_run.call_args[0][0]
        assert called_command[0] == "git"
        assert "-c" in called_command
        assert any("credential.helper=" in arg for arg in called_command)


def test_git_integration_run_git_command_with_credentials_no_credentials():
    """Test GitIntegration.run_git_command_with_credentials method without credentials."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        # Only clear Git-related environment variables, keep HOME
        env_to_clear = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with patch.dict(os.environ, env_to_clear, clear=True):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            agent = PersistentSSHAgent()
            result = agent.git.run_git_command_with_credentials(["git", "--version"])

            assert result is not None

            # Verify the command was called without enhancement
            mock_run.assert_called_once_with(["git", "--version"])


def test_git_integration_run_git_command_with_credentials_non_git_command():
    """Test GitIntegration.run_git_command_with_credentials method with non-Git command."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        agent = PersistentSSHAgent()
        result = agent.git.run_git_command_with_credentials(
            ["python", "--version"],
            username="testuser",
            password="testpass"
        )

        assert result is not None

        # Verify the command was called without Git-specific enhancement
        mock_run.assert_called_once_with(["python", "--version"])


# Tests for Git credentials testing functionality
def test_git_integration_test_credentials_single_host():
    """Test GitIntegration.test_credentials method for a single host."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        agent = PersistentSSHAgent()
        results = agent.git.test_credentials(
            host="github.com",
            username="testuser",
            password="testpass"
        )

        assert isinstance(results, dict)
        assert "github.com" in results
        assert results["github.com"] is True

        # Verify git ls-remote was called with credentials
        mock_run.assert_called_once()
        called_command = mock_run.call_args[0][0]
        assert called_command[0] == "git"
        assert "-c" in called_command
        assert "ls-remote" in called_command


def test_git_integration_test_credentials_single_host_failure():
    """Test GitIntegration.test_credentials method for a single host with invalid credentials."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Authentication failed"
        mock_run.return_value = mock_result

        agent = PersistentSSHAgent()
        results = agent.git.test_credentials(
            host="github.com",
            username="testuser",
            password="wrongpass"
        )

        assert isinstance(results, dict)
        assert "github.com" in results
        assert results["github.com"] is False


def test_git_integration_test_credentials_multiple_hosts():
    """Test GitIntegration.test_credentials method for multiple hosts."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        # Mock successful results for all hosts
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        agent = PersistentSSHAgent()
        results = agent.git.test_credentials(
            username="testuser",
            password="testpass"
        )

        assert isinstance(results, dict)
        assert "github.com" in results
        assert "gitlab.com" in results
        assert "bitbucket.org" in results

        # Should have called git ls-remote for each host
        assert mock_run.call_count == 3


def test_git_integration_test_credentials_no_credentials():
    """Test GitIntegration.test_credentials method without credentials."""
    from persistent_ssh_agent import PersistentSSHAgent

    # Only clear Git-related environment variables, keep HOME
    env_to_clear = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    with patch.dict(os.environ, env_to_clear, clear=True):
        agent = PersistentSSHAgent()
        results = agent.git.test_credentials(host="github.com")

        assert isinstance(results, dict)
        assert "github.com" in results
        assert results["github.com"] is False


def test_git_integration_test_credentials_timeout():
    """Test GitIntegration.test_credentials method with timeout."""
    from persistent_ssh_agent import PersistentSSHAgent

    with patch("persistent_ssh_agent.git.run_command") as mock_run:
        # Mock timeout (run_command returns None on timeout)
        mock_run.return_value = None

        agent = PersistentSSHAgent()
        results = agent.git.test_credentials(
            host="github.com",
            timeout=5,
            username="testuser",
            password="testpass"
        )

        assert isinstance(results, dict)
        assert "github.com" in results
        assert results["github.com"] is False

        # Verify timeout was passed to run_command
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["timeout"] == 5


def test_git_integration_get_test_urls_for_host():
    """Test GitIntegration._get_test_urls_for_host method."""
    from persistent_ssh_agent import PersistentSSHAgent

    agent = PersistentSSHAgent()

    # Test known hosts
    github_urls = agent.git._get_test_urls_for_host("github.com")
    assert len(github_urls) > 0
    assert "github.com" in github_urls[0]

    gitlab_urls = agent.git._get_test_urls_for_host("gitlab.com")
    assert len(gitlab_urls) > 0
    assert "gitlab.com" in gitlab_urls[0]

    # Test unknown host
    unknown_urls = agent.git._get_test_urls_for_host("example.com")
    assert len(unknown_urls) > 0
    assert "example.com" in unknown_urls[0]
