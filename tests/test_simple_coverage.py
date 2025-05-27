"""Simple tests to improve coverage without network requests."""

# Import built-in modules
import os
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent.utils import _decode_subprocess_output
from persistent_ssh_agent.utils import create_temp_key_file
from persistent_ssh_agent.utils import ensure_home_env
from persistent_ssh_agent.utils import extract_hostname
from persistent_ssh_agent.utils import is_valid_hostname
from persistent_ssh_agent.utils import resolve_path
from persistent_ssh_agent.utils import run_command


class TestSimpleCoverage:
    """Simple tests to improve coverage."""

    def test_decode_subprocess_output_fallback(self):
        """Test _decode_subprocess_output fallback behavior."""
        # Test with bytes that might cause encoding issues
        test_data = b"\xff\xfe\xfd\xfc"
        result = _decode_subprocess_output(test_data)
        assert isinstance(result, str)

    def test_run_command_timeout_cleanup(self):
        """Test run_command timeout with process cleanup."""
        with patch("subprocess.run") as mock_run:
            mock_process = MagicMock()
            timeout_error = subprocess.TimeoutExpired(["test"], 30)
            timeout_error.process = mock_process
            mock_run.side_effect = timeout_error

            result = run_command(["sleep", "60"], timeout=1)
            assert result is None

    def test_run_command_git_enhancements(self):
        """Test run_command Git command enhancements."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = b"output"
            mock_result.stderr = b"error"
            mock_run.return_value = mock_result

            # Test git submodule command
            run_command(["git", "submodule", "update"])
            called_args = mock_run.call_args[0][0]
            assert "git" in called_args
            assert "submodule" in called_args
            assert "update" in called_args

            # Test git credential command
            mock_run.reset_mock()
            run_command(["git", "-c", "credential.helper=test", "clone", "repo"])
            called_args = mock_run.call_args[0][0]
            assert "git" in called_args
            assert "-c" in called_args
            assert "credential.helper=test" in called_args

    def test_is_valid_hostname_edge_cases(self):
        """Test is_valid_hostname edge cases."""
        # Empty hostname
        assert is_valid_hostname("") is False

        # Too long hostname
        assert is_valid_hostname("a" * 256) is False

        # Label too long
        assert is_valid_hostname("a" * 64 + ".com") is False

        # Empty labels
        assert is_valid_hostname("example..com") is False
        assert is_valid_hostname(".example.com") is False

        # Invalid characters
        assert is_valid_hostname("example_test.com") is False

        # Hyphens at start/end
        assert is_valid_hostname("-example.com") is False
        assert is_valid_hostname("example-.com") is False

    def test_is_valid_hostname_ipv6(self):
        """Test is_valid_hostname with IPv6."""
        with patch("socket.inet_pton", return_value=True):
            assert is_valid_hostname("[::1]") is True
            assert is_valid_hostname("::1") is True

        with patch("socket.inet_pton", side_effect=ValueError("Invalid")):
            assert is_valid_hostname("invalid::ipv6") is False

    def test_extract_hostname_edge_cases(self):
        """Test extract_hostname edge cases."""
        # None input
        assert extract_hostname(None) is None

        # Non-string input
        assert extract_hostname(123) is None

        # Invalid formats
        assert extract_hostname("not-ssh-url") is None
        assert extract_hostname("git@host:") is None
        assert extract_hostname("git@host:/") is None

        # Invalid hostname
        with patch("persistent_ssh_agent.utils.is_valid_hostname", return_value=False):
            assert extract_hostname("git@invalid..host:user/repo.git") is None

    def test_create_temp_key_file_errors(self):
        """Test create_temp_key_file error cases."""
        # Empty content
        assert create_temp_key_file("") is None
        assert create_temp_key_file(None) is None

        # Permission error
        with patch("tempfile.NamedTemporaryFile", side_effect=PermissionError("Permission denied")):
            assert create_temp_key_file("test key") is None

        # OS error
        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("OS error")):
            assert create_temp_key_file("test key") is None

    def test_resolve_path_errors(self):
        """Test resolve_path error cases."""
        # Type error
        with patch("os.path.expanduser", side_effect=TypeError("Type error")):
            assert resolve_path("~/test") is None

        # Value error
        with patch("os.path.expanduser", side_effect=ValueError("Value error")):
            assert resolve_path("~/test") is None

    def test_ensure_home_env(self):
        """Test ensure_home_env function."""
        # Test when HOME is not set
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.path.expanduser", return_value="/home/user"):
                ensure_home_env()
                assert os.environ.get("HOME") == "/home/user"

        # Test when HOME is already set
        with patch.dict(os.environ, {"HOME": "/existing/home"}, clear=True):
            ensure_home_env()
            assert os.environ.get("HOME") == "/existing/home"

    def test_git_integration_basic_errors(self):
        """Test basic GitIntegration error paths."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test extract_hostname with invalid URLs
        assert agent.git.extract_hostname("") is None
        assert agent.git.extract_hostname("invalid-url") is None

        # Test get_git_credential_command with invalid paths
        assert agent.git.get_git_credential_command("") is None
        assert agent.git.get_git_credential_command("/non/existent/path") is None

    def test_git_integration_credential_errors(self):
        """Test GitIntegration credential error paths."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test without credentials
        with patch.dict(os.environ, {}, clear=True):
            result = agent.git.get_credential_helper_command()
            assert result is None

        # Test run_git_command_with_credentials without credentials
        with patch.dict(os.environ, {}, clear=True):
            with patch("persistent_ssh_agent.git.run_command") as mock_run:
                mock_run.return_value = MagicMock()
                agent.git.run_git_command_with_credentials(["git", "status"])
                mock_run.assert_called_once_with(["git", "status"])

    @patch("persistent_ssh_agent.git.run_command")
    def test_git_integration_clear_helpers_errors(self, mock_run_command):
        """Test GitIntegration clear_credential_helpers errors."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test when git config fails
        with patch.object(agent.git, "get_current_credential_helpers", return_value=["helper1"]):
            mock_run_command.return_value = MagicMock(returncode=1, stderr=b"Error")
            result = agent.git.clear_credential_helpers()
            assert result is False

        # Test when run_command returns None
        with patch.object(agent.git, "get_current_credential_helpers", return_value=["helper1"]):
            mock_run_command.return_value = None
            result = agent.git.clear_credential_helpers()
            assert result is False

    def test_git_integration_test_credentials_errors(self):
        """Test GitIntegration test_credentials errors."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test without credentials
        with patch.dict(os.environ, {}, clear=True):
            result = agent.git._test_single_host_credentials("github.com", 30)
            assert result is False

        # Test when helper creation fails
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(agent.git, "_create_credential_helper_file", return_value=None):
                result = agent.git._test_single_host_credentials("github.com", 30)
                assert result is False

    @patch("persistent_ssh_agent.git.run_command")
    def test_git_integration_test_credentials_command_errors(self, mock_run_command):
        """Test GitIntegration test_credentials command errors."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test when git command fails
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(agent.git, "_create_credential_helper_file", return_value="/path/to/helper"):
                mock_run_command.return_value = MagicMock(returncode=1, stderr="Auth failed")
                result = agent.git._test_single_host_credentials("github.com", 30)
                assert result is False

        # Test when git command times out
        with patch.dict(os.environ, {"GIT_USERNAME": "user", "GIT_PASSWORD": "pass"}):
            with patch.object(agent.git, "_create_credential_helper_file", return_value="/path/to/helper"):
                mock_run_command.return_value = None  # Timeout
                result = agent.git._test_single_host_credentials("github.com", 30)
                assert result is False

    def test_git_integration_ssh_errors(self):
        """Test GitIntegration SSH-related errors."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test with invalid hostname
        result = agent.git.get_git_ssh_command("invalid..hostname")
        assert result is None

        # Test when no identity file found
        with patch.object(agent, "_get_identity_file", return_value=None):
            result = agent.git.get_git_ssh_command("github.com")
            assert result is None

        # Test when identity file doesn't exist
        with patch.object(agent, "_get_identity_file", return_value="/non/existent/key"):
            result = agent.git.get_git_ssh_command("github.com")
            assert result is None

    def test_git_integration_get_test_urls(self):
        """Test GitIntegration _get_test_urls_for_host."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Test unknown host
        urls = agent.git._get_test_urls_for_host("unknown.example.com")
        assert len(urls) == 1
        assert "unknown.example.com" in urls[0]
        assert urls[0] == "https://unknown.example.com/test/repo.git"

    def test_git_integration_ssh_config_edge_cases(self):
        """Test GitIntegration SSH config edge cases."""
        # Import third-party modules
        from persistent_ssh_agent import PersistentSSHAgent

        agent = PersistentSSHAgent()

        # Mock config with invalid options
        agent._config = MagicMock()
        agent._config.ssh_options = {
            "ValidOption": "value",
            "": "invalid",  # Empty key
            "EmptyValue": "",  # Empty value
        }

        # Test _build_ssh_options
        options = agent.git._build_ssh_options("/path/to/key")
        assert "ssh" in options
        assert "-i" in options
        assert "/path/to/key" in options
        assert "ValidOption=value" in options
