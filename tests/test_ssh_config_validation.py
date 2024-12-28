"""Test SSH configuration validation."""

# Import built-in modules
from pathlib import Path
import tempfile

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent
import pytest


@pytest.fixture
def temp_ssh_dir():
    """Create a temporary SSH directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def ssh_manager(temp_ssh_dir):
    """Create a PersistentSSHAgent instance for testing."""
    agent = PersistentSSHAgent()
    agent._ssh_dir = temp_ssh_dir
    return agent

def write_ssh_config(ssh_dir: Path, config_content: str):
    """Write SSH config content to a temporary file."""
    config_path = ssh_dir / "config"
    config_path.write_text(config_content)

def test_connection_settings_validation(ssh_manager, temp_ssh_dir):
    """Test validation of connection-related settings."""
    # Test valid port
    write_ssh_config(temp_ssh_dir, "Host test\n    Port 22")
    config = ssh_manager._parse_ssh_config()
    assert config["test"]["port"] == "22"

    # Test invalid port (too low)
    write_ssh_config(temp_ssh_dir, "Host test\n    Port 0")
    config = ssh_manager._parse_ssh_config()
    assert "port" not in config.get("test", {})

    # Test invalid port (too high)
    write_ssh_config(temp_ssh_dir, "Host test\n    Port 65536")
    config = ssh_manager._parse_ssh_config()
    assert "port" not in config.get("test", {})

def test_security_settings_validation(ssh_manager, temp_ssh_dir):
    """Test validation of security-related settings."""
    # Test valid StrictHostKeyChecking options
    valid_options = ["yes", "no", "accept-new", "off", "ask"]
    for option in valid_options:
        write_ssh_config(temp_ssh_dir, f"Host test\n    StrictHostKeyChecking {option}")
        config = ssh_manager._parse_ssh_config()
        assert config["test"]["stricthostkeychecking"] == option.lower()

    # Test invalid option
    write_ssh_config(temp_ssh_dir, "Host test\n    StrictHostKeyChecking invalid")
    config = ssh_manager._parse_ssh_config()
    assert "stricthostkeychecking" not in config.get("test", {})

def test_connection_optimization_validation(ssh_manager, temp_ssh_dir):
    """Test validation of connection optimization settings."""
    # Test valid timeout
    write_ssh_config(temp_ssh_dir, "Host test\n    ConnectTimeout 30")
    config = ssh_manager._parse_ssh_config()
    assert config["test"]["connecttimeout"] == "30"

    # Test invalid timeout
    write_ssh_config(temp_ssh_dir, "Host test\n    ConnectTimeout -1")
    config = ssh_manager._parse_ssh_config()
    assert "connecttimeout" not in config.get("test", {})

def test_proxy_forwarding_validation(ssh_manager, temp_ssh_dir):
    """Test validation of proxy and forwarding settings."""
    # Test valid ForwardAgent option
    write_ssh_config(temp_ssh_dir, "Host test\n    ForwardAgent yes")
    config = ssh_manager._parse_ssh_config()
    assert config["test"]["forwardagent"] == "yes"

    # Test invalid option
    write_ssh_config(temp_ssh_dir, "Host test\n    ForwardAgent invalid")
    config = ssh_manager._parse_ssh_config()
    assert "forwardagent" not in config.get("test", {})

def test_environment_settings_validation(ssh_manager, temp_ssh_dir):
    """Test validation of environment-related settings."""
    # Test valid RequestTTY options
    valid_options = ["yes", "no", "force", "auto"]
    for option in valid_options:
        write_ssh_config(temp_ssh_dir, f"Host test\n    RequestTTY {option}")
        config = ssh_manager._parse_ssh_config()
        assert config["test"]["requesttty"] == option.lower()

    # Test invalid option
    write_ssh_config(temp_ssh_dir, "Host test\n    RequestTTY invalid")
    config = ssh_manager._parse_ssh_config()
    assert "requesttty" not in config.get("test", {})

def test_multiplexing_settings_validation(ssh_manager, temp_ssh_dir):
    """Test validation of multiplexing-related settings."""
    # Test valid ControlMaster options
    valid_options = ["yes", "no", "ask", "auto", "autoask"]
    for option in valid_options:
        write_ssh_config(temp_ssh_dir, f"Host test\n    ControlMaster {option}")
        config = ssh_manager._parse_ssh_config()
        assert config["test"]["controlmaster"] == option.lower()

    # Test invalid option
    write_ssh_config(temp_ssh_dir, "Host test\n    ControlMaster invalid")
    config = ssh_manager._parse_ssh_config()
    assert "controlmaster" not in config.get("test", {})

def test_canonicalization_settings_validation(ssh_manager, temp_ssh_dir):
    """Test validation of canonicalization settings."""
    # Test valid CanonicalizeHostname options
    valid_options = ["yes", "no", "always"]
    for option in valid_options:
        write_ssh_config(temp_ssh_dir, f"Host test\n    CanonicalizeHostname {option}")
        config = ssh_manager._parse_ssh_config()
        assert config["test"]["canonicalizehostname"] == option.lower()

    # Test valid CanonicalizeMaxDots
    write_ssh_config(temp_ssh_dir, "Host test\n    CanonicalizeMaxDots 1")
    config = ssh_manager._parse_ssh_config()
    assert config["test"]["canonicalizemaxdots"] == "1"

    # Test invalid value
    write_ssh_config(temp_ssh_dir, "Host test\n    CanonicalizeMaxDots -1")
    config = ssh_manager._parse_ssh_config()
    assert "canonicalizemaxdots" not in config.get("test", {})

def test_multiple_value_options(ssh_manager, temp_ssh_dir):
    """Test handling of options that can have multiple values."""
    # Test multiple IdentityFile entries
    config_content = """Host test
    IdentityFile ~/.ssh/id_rsa
    IdentityFile ~/.ssh/id_ed25519"""
    write_ssh_config(temp_ssh_dir, config_content)
    config = ssh_manager._parse_ssh_config()
    assert isinstance(config["test"]["identityfile"], list)
    assert len(config["test"]["identityfile"]) == 2

    # Test multiple SendEnv entries
    config_content = """Host test
    SendEnv LANG LC_*
    SendEnv GIT_*"""
    write_ssh_config(temp_ssh_dir, config_content)
    config = ssh_manager._parse_ssh_config()
    assert isinstance(config["test"]["sendenv"], list)
    assert len(config["test"]["sendenv"]) == 2

def test_invalid_config_format(ssh_manager, temp_ssh_dir):
    """Test handling of invalid configuration formats."""
    # Test empty config
    write_ssh_config(temp_ssh_dir, "")
    config = ssh_manager._parse_ssh_config()
    assert config == {}

    # Test invalid host pattern
    write_ssh_config(temp_ssh_dir, "Host\ninvalid\n    Port 22")
    config = ssh_manager._parse_ssh_config()
    assert config == {}

    # Test invalid key
    write_ssh_config(temp_ssh_dir, "Host test\n    InvalidKey value")
    config = ssh_manager._parse_ssh_config()
    assert "invalidkey" not in config.get("test", {})
