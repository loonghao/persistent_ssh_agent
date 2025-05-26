"""Test SSH configuration parsing performance."""

# Import built-in modules
from pathlib import Path
import time

# Import third-party modules
from persistent_ssh_agent.core import PersistentSSHAgent
import pytest


@pytest.fixture
def temp_ssh_dir(tmp_path):
    """Create a temporary SSH directory for testing."""
    return tmp_path


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


def test_config_parsing_performance_small(ssh_manager, temp_ssh_dir):
    """Test performance of parsing a small config file."""
    # Create a small config with 10 hosts
    config_content = "\n".join(
        [f"Host host{i}\n    Hostname example{i}.com\n    Port {22 + i}\n    User user{i}" for i in range(10)]
    )
    write_ssh_config(temp_ssh_dir, config_content)

    # Measure parsing time
    start_time = time.time()
    config = ssh_manager._parse_ssh_config()
    parse_time = time.time() - start_time

    # Verify results
    assert len(config) == 10
    assert parse_time < 0.1  # Should parse in less than 100ms


def test_config_parsing_performance_medium(ssh_manager, temp_ssh_dir):
    """Test performance of parsing a medium config file."""
    # Create a medium config with 100 hosts
    config_content = "\n".join(
        [f"Host host{i}\n    Hostname example{i}.com\n    Port {22 + i}\n    User user{i}" for i in range(100)]
    )
    write_ssh_config(temp_ssh_dir, config_content)

    # Measure parsing time
    start_time = time.time()
    config = ssh_manager._parse_ssh_config()
    parse_time = time.time() - start_time

    # Verify results
    assert len(config) == 100
    assert parse_time < 0.5  # Should parse in less than 500ms


def test_config_parsing_performance_large(ssh_manager, temp_ssh_dir):
    """Test performance of parsing a large config file."""
    # Create a large config with 1000 hosts
    config_content = "\n".join(
        [f"Host host{i}\n    Hostname example{i}.com\n    Port {22 + i}\n    User user{i}" for i in range(1000)]
    )
    write_ssh_config(temp_ssh_dir, config_content)

    # Measure parsing time
    start_time = time.time()
    config = ssh_manager._parse_ssh_config()
    parse_time = time.time() - start_time

    # Verify results
    assert len(config) == 1000
    assert parse_time < 2.0  # Should parse in less than 2 seconds


def test_config_parsing_with_includes(ssh_manager, temp_ssh_dir):
    """Test performance of parsing config with includes."""
    # Create main config
    main_config = "Include config.d/*\n\nHost *\n    ForwardAgent yes"
    write_ssh_config(temp_ssh_dir, main_config)

    # Create included configs
    config_d = temp_ssh_dir / "config.d"
    config_d.mkdir()

    for i in range(5):
        include_content = "\n".join(
            [
                f"Host host{j}\n    Hostname example{j}.com\n    Port {22 + j}\n    User user{j}"
                for j in range(i * 10, (i + 1) * 10)
            ]
        )
        (config_d / f"config{i}").write_text(include_content)

    # Measure parsing time
    start_time = time.time()
    config = ssh_manager._parse_ssh_config()
    parse_time = time.time() - start_time

    # Verify results
    assert len(config) >= 50  # 50 hosts plus wildcard
    assert parse_time < 0.5  # Should parse in less than 500ms


def test_config_parsing_with_complex_options(ssh_manager, temp_ssh_dir):
    """Test performance of parsing config with complex options."""
    # Create config with all possible options
    config_content = """Host complex
    # Connection settings
    Hostname example.com
    Port 2222
    User testuser
    IdentityFile ~/.ssh/id_rsa
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    AddressFamily inet
    BindAddress 0.0.0.0
    ConnectTimeout 30
    ConnectionAttempts 3

    # Security settings
    StrictHostKeyChecking accept-new
    UserKnownHostsFile ~/.ssh/known_hosts
    BatchMode yes
    PasswordAuthentication no
    PubkeyAuthentication yes
    KbdInteractiveAuthentication no
    HostbasedAuthentication no
    GSSAPIAuthentication no
    PreferredAuthentications publickey,keyboard-interactive

    # Connection optimization
    Compression yes
    TCPKeepAlive yes
    ServerAliveCountMax 3
    ServerAliveInterval 60
    RekeyLimit 1G 1h

    # Proxy and forwarding
    ProxyCommand ssh -W %h:%p jumphost
    ProxyJump jumphost:2222
    ForwardAgent yes
    ForwardX11 yes
    ForwardX11Trusted no
    DynamicForward 1080
    LocalForward 3000 localhost:3000
    RemoteForward 3001 localhost:3001

    # Environment
    SendEnv LANG LC_*
    SetEnv FOO=bar
    RequestTTY auto
    PermitLocalCommand yes

    # Multiplexing
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 1h

    # Misc
    AddKeysToAgent yes
    CanonicalDomains example.com example.net
    CanonicalizeHostname yes
    CanonicalizeMaxDots 1
    CanonicalizePermittedCNAMEs *.example.com:*.example.net
    IPQoS lowdelay throughput
    PKCS11Provider /usr/lib/pkcs11.so
    RevokedHostKeys ~/.ssh/revoked-keys
    StreamLocalBindMask 0177
    StreamLocalBindUnlink yes"""

    write_ssh_config(temp_ssh_dir, config_content)

    # Measure parsing time
    start_time = time.time()
    config = ssh_manager._parse_ssh_config()
    parse_time = time.time() - start_time

    # Verify results
    assert "complex" in config
    assert len(config["complex"]) >= 30  # Should have at least 30 options
    assert parse_time < 0.1  # Should parse in less than 100ms


def test_config_validation_performance(ssh_manager, temp_ssh_dir):
    """Test performance of config validation."""
    # Create config with valid and invalid values
    config_content = """Host test
    # Valid options
    Port 22
    User testuser
    StrictHostKeyChecking yes

    # Invalid options
    Port 999999
    InvalidKey value
    StrictHostKeyChecking invalid

    # Complex validation
    PreferredAuthentications publickey,invalid
    IPQoS invalid lowdelay
    StreamLocalBindMask 999"""

    write_ssh_config(temp_ssh_dir, config_content)

    # Measure parsing time
    start_time = time.time()
    config = ssh_manager._parse_ssh_config()
    parse_time = time.time() - start_time

    # Verify results
    assert "test" in config
    assert config["test"]["port"] == "22"  # Valid port should be kept
    assert "invalidkey" not in config["test"]  # Invalid key should be skipped
    assert parse_time < 0.1  # Should parse in less than 100ms
