"""Tests for Git-related CLI commands."""

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
