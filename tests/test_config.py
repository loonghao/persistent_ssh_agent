"""Test configuration module."""
# Import built-in modules

# Import third-party modules
from persistent_ssh_agent.config import SSHConfig


def test_ssh_config_default_init():
    """Test SSHConfig initialization with default values."""
    config = SSHConfig()
    assert config.identity_file is None
    assert config.identity_content is None
    assert config.identity_passphrase is None
    assert isinstance(config.ssh_options, dict)
    assert len(config.ssh_options) == 0


def test_ssh_config_with_values():
    """Test SSHConfig initialization with custom values."""
    config = SSHConfig(
        identity_file="~/.ssh/id_rsa",
        identity_content="test-content",
        identity_passphrase="test-pass",
        ssh_options={"StrictHostKeyChecking": "no"}
    )
    assert config.identity_file == "~/.ssh/id_rsa"
    assert config.identity_content == "test-content"
    assert config.identity_passphrase == "test-pass"
    assert config.ssh_options == {"StrictHostKeyChecking": "no"}


def test_ssh_config_with_none_ssh_options():
    """Test SSHConfig with None ssh_options."""
    config = SSHConfig(ssh_options=None)
    assert isinstance(config.ssh_options, dict)
    assert len(config.ssh_options) == 0


def test_ssh_config_with_empty_ssh_options():
    """Test SSHConfig with empty ssh_options."""
    config = SSHConfig(ssh_options={})
    assert isinstance(config.ssh_options, dict)
    assert len(config.ssh_options) == 0


def test_ssh_config_with_partial_values():
    """Test SSHConfig with partial values."""
    config = SSHConfig(
        identity_file="~/.ssh/id_rsa",
        ssh_options={"BatchMode": "yes"}
    )
    assert config.identity_file == "~/.ssh/id_rsa"
    assert config.identity_content is None
    assert config.identity_passphrase is None
    assert config.ssh_options == {"BatchMode": "yes"}


def test_ssh_config_post_init_idempotent():
    """Test that calling __post_init__ multiple times is safe."""
    config = SSHConfig()
    original_options = config.ssh_options
    config.__post_init__()
    assert config.ssh_options is original_options
    assert len(config.ssh_options) == 0
