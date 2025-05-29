"""Additional tests for core module to improve coverage."""

# Import built-in modules
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch

# Import third-party modules
from persistent_ssh_agent import PersistentSSHAgent
from persistent_ssh_agent.config import SSHConfig
from persistent_ssh_agent.constants import SSHAgentConstants
import pytest


@pytest.fixture
def temp_ssh_dir():
    """Create a temporary SSH directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def persistent_agent(temp_ssh_dir):
    """Create a PersistentSSHAgent instance with temporary directory."""
    with patch("persistent_ssh_agent.core.Path.home") as mock_home:
        mock_home.return_value = temp_ssh_dir.parent
        agent = PersistentSSHAgent()
        agent._ssh_dir = temp_ssh_dir
        agent._agent_info_file = temp_ssh_dir / SSHAgentConstants.AGENT_INFO_FILE
        return agent


class TestPersistentSSHAgentBasics:
    """Test basic PersistentSSHAgent functionality."""

    def test_init_with_config(self, temp_ssh_dir):
        """Test initialization with SSH configuration."""
        config = SSHConfig()

        with patch("persistent_ssh_agent.core.Path.home") as mock_home:
            mock_home.return_value = temp_ssh_dir.parent
            agent = PersistentSSHAgent(config=config)

            assert agent._config == config
            # SSH dir should be .ssh under the parent directory
            expected_ssh_dir = temp_ssh_dir.parent / ".ssh"
            assert agent._ssh_dir == expected_ssh_dir

    def test_context_manager(self, persistent_agent):
        """Test context manager functionality."""
        with persistent_agent as agent:
            assert agent is persistent_agent

    def test_parse_ssh_agent_output(self):
        """Test parsing SSH agent output."""
        output = "SSH_AUTH_SOCK=/tmp/ssh-agent.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=12345; export SSH_AGENT_PID;"
        
        result = PersistentSSHAgent._parse_ssh_agent_output(output)
        
        expected = {
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "SSH_AGENT_PID": "12345"
        }
        assert result == expected

    def test_parse_ssh_agent_output_empty(self):
        """Test parsing empty SSH agent output."""
        result = PersistentSSHAgent._parse_ssh_agent_output("")
        assert result == {}

    def test_write_temp_key_string(self):
        """Test writing string key content to temporary file."""
        key_content = "-----BEGIN OPENSSH PRIVATE KEY-----\ntest key content\n-----END OPENSSH PRIVATE KEY-----"
        
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_file = MagicMock()
            mock_file.name = "/tmp/temp_key"
            mock_temp.return_value.__enter__.return_value = mock_file
            
            with patch("os.name", "posix"), \
                 patch("os.chmod") as mock_chmod:
                
                temp_key_path = PersistentSSHAgent._write_temp_key(key_content)
                
                assert temp_key_path == "/tmp/temp_key"
                mock_file.write.assert_called_once_with(key_content)
                mock_chmod.assert_called_once()

    def test_write_temp_key_bytes(self):
        """Test writing bytes key content to temporary file."""
        key_content = b"-----BEGIN OPENSSH PRIVATE KEY-----\ntest key content\n-----END OPENSSH PRIVATE KEY-----"
        
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_file = MagicMock()
            mock_file.name = "/tmp/temp_key"
            mock_temp.return_value.__enter__.return_value = mock_file
            
            with patch("os.name", "posix"), \
                 patch("os.chmod"):
                
                temp_key_path = PersistentSSHAgent._write_temp_key(key_content)
                
                assert temp_key_path == "/tmp/temp_key"
                # Should convert bytes to string
                expected_content = key_content.decode("utf-8")
                mock_file.write.assert_called_once_with(expected_content)

    def test_write_temp_key_error(self):
        """Test writing temporary key file with error."""
        key_content = "test key content"
        
        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("Permission denied")):
            temp_key_path = PersistentSSHAgent._write_temp_key(key_content)
            assert temp_key_path is None

    def test_build_ssh_options_basic(self, persistent_agent):
        """Test building SSH options with basic configuration."""
        identity_file = "/path/to/key"
        
        options = persistent_agent._build_ssh_options(identity_file)
        
        assert "ssh" in options
        assert "-i" in options
        assert identity_file in options
        # Should contain default options
        assert "-o" in options

    def test_build_ssh_options_with_config(self, persistent_agent):
        """Test building SSH options with custom configuration."""
        config = SSHConfig()
        config.ssh_options = {"StrictHostKeyChecking": "no", "UserKnownHostsFile": "/dev/null"}
        persistent_agent._config = config
        
        identity_file = "/path/to/key"
        options = persistent_agent._build_ssh_options(identity_file)
        
        assert "ssh" in options
        assert "-i" in options
        assert identity_file in options
        # Should contain custom options
        assert "StrictHostKeyChecking=no" in " ".join(options)

    def test_build_ssh_options_invalid_config(self, persistent_agent):
        """Test building SSH options with invalid configuration."""
        config = SSHConfig()
        config.ssh_options = {"": "value", "key": ""}  # Invalid options
        persistent_agent._config = config
        
        identity_file = "/path/to/key"
        options = persistent_agent._build_ssh_options(identity_file)
        
        # Should still work and skip invalid options
        assert "ssh" in options
        assert "-i" in options
        assert identity_file in options


class TestPersistentSSHAgentAgentInfo:
    """Test agent info management."""

    def test_save_agent_info(self, persistent_agent):
        """Test saving agent information."""
        auth_sock = "/tmp/ssh-agent.sock"
        agent_pid = "12345"
        
        persistent_agent._save_agent_info(auth_sock, agent_pid)
        
        # Check that file was created
        assert persistent_agent._agent_info_file.exists()
        
        # Verify content
        with open(persistent_agent._agent_info_file, encoding="utf-8") as f:
            saved_info = json.load(f)
        
        assert saved_info["SSH_AUTH_SOCK"] == auth_sock
        assert saved_info["SSH_AGENT_PID"] == agent_pid
        assert "timestamp" in saved_info
        assert "platform" in saved_info

    def test_save_agent_info_error(self, persistent_agent):
        """Test saving agent info with error."""
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # Should not raise exception
            persistent_agent._save_agent_info("/tmp/sock", "12345")

    def test_load_agent_info_success(self, persistent_agent):
        """Test loading agent information successfully."""
        # Create valid agent info
        agent_info = {
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "SSH_AGENT_PID": "12345",
            "timestamp": 1234567890.0,
            "platform": os.name
        }
        
        with open(persistent_agent._agent_info_file, "w", encoding="utf-8") as f:
            json.dump(agent_info, f)
        
        with patch("persistent_ssh_agent.core.run_command") as mock_run:
            # Mock successful ssh-add command
            mock_result = MagicMock()
            mock_result.returncode = 1  # Return code 1 means "no identities" which is fine
            mock_run.return_value = mock_result

            with patch("time.time", return_value=1234567890.0):  # Same timestamp
                result = persistent_agent._load_agent_info()

                assert result
                # Check environment variables are set
                assert os.environ.get("SSH_AUTH_SOCK") == "/tmp/ssh-agent.sock"
                assert os.environ.get("SSH_AGENT_PID") == "12345"

    def test_load_agent_info_expired(self, persistent_agent):
        """Test loading expired agent information."""
        # Create expired agent info
        agent_info = {
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "SSH_AGENT_PID": "12345",
            "timestamp": 1234567890.0,  # Old timestamp
            "platform": os.name
        }
        
        with open(persistent_agent._agent_info_file, "w", encoding="utf-8") as f:
            json.dump(agent_info, f)
        
        with patch("time.time", return_value=1234567890.0 + 100000):  # Much later
            result = persistent_agent._load_agent_info()
            assert not result

    def test_load_agent_info_missing_fields(self, persistent_agent):
        """Test loading agent info with missing required fields."""
        # Create incomplete agent info
        agent_info = {
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            # Missing SSH_AGENT_PID, timestamp, platform
        }
        
        with open(persistent_agent._agent_info_file, "w", encoding="utf-8") as f:
            json.dump(agent_info, f)
        
        result = persistent_agent._load_agent_info()
        assert not result

    def test_load_agent_info_platform_mismatch_windows(self, persistent_agent):
        """Test loading agent info with platform mismatch on Windows."""
        # Create agent info with wrong platform
        agent_info = {
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "SSH_AGENT_PID": "12345",
            "timestamp": 1234567890.0,
            "platform": "posix"  # Wrong platform for Windows
        }
        
        with open(persistent_agent._agent_info_file, "w", encoding="utf-8") as f:
            json.dump(agent_info, f)
        
        with patch("os.name", "nt"), \
             patch("time.time", return_value=1234567890.0):
            result = persistent_agent._load_agent_info()
            assert not result

    def test_load_agent_info_agent_not_running(self, persistent_agent):
        """Test loading agent info when agent is not running."""
        # Create valid agent info
        agent_info = {
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "SSH_AGENT_PID": "12345",
            "timestamp": 1234567890.0,
            "platform": os.name
        }
        
        with open(persistent_agent._agent_info_file, "w", encoding="utf-8") as f:
            json.dump(agent_info, f)
        
        with patch("persistent_ssh_agent.core.run_command") as mock_run:
            # Mock ssh-add command returning "agent not running"
            mock_result = MagicMock()
            mock_result.returncode = 2  # Agent not running
            mock_run.return_value = mock_result

            with patch("time.time", return_value=1234567890.0):
                result = persistent_agent._load_agent_info()
                assert not result


class TestPersistentSSHAgentIdentityMethods:
    """Test identity file resolution methods."""

    def test_resolve_identity_file_absolute_path(self, persistent_agent):
        """Test resolving absolute identity file path."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = persistent_agent._resolve_identity_file(temp_path)
            assert result is not None
            assert temp_path.replace("\\", "/") in result
        finally:
            os.unlink(temp_path)

    def test_resolve_identity_file_relative_path(self, persistent_agent):
        """Test resolving relative identity file path."""
        # Create a test file in SSH directory
        test_file = persistent_agent._ssh_dir / "test_key"
        test_file.write_text("test key content")
        
        result = persistent_agent._resolve_identity_file("test_key")
        assert result is not None
        assert "test_key" in result

    def test_resolve_identity_file_user_path(self, persistent_agent):
        """Test resolving user home path."""
        with patch("os.path.expanduser") as mock_expand, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.abspath") as mock_abs:
            
            mock_expand.return_value = "/home/user/.ssh/id_rsa"
            mock_abs.return_value = "/home/user/.ssh/id_rsa"
            
            result = persistent_agent._resolve_identity_file("~/.ssh/id_rsa")
            
            assert result == "/home/user/.ssh/id_rsa"
            mock_expand.assert_called_once_with("~/.ssh/id_rsa")

    def test_resolve_identity_file_not_found(self, persistent_agent):
        """Test resolving non-existent identity file."""
        result = persistent_agent._resolve_identity_file("/nonexistent/key")
        assert result is None

    def test_resolve_identity_file_invalid_path(self, persistent_agent):
        """Test resolving invalid identity file path."""
        with patch("os.path.expanduser", side_effect=TypeError("Invalid path")):
            result = persistent_agent._resolve_identity_file(None)
            assert result is None
