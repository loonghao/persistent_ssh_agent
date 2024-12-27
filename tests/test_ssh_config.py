"""Test SSH configuration functionality."""
import os
import tempfile
from pathlib import Path

import pytest

from persistent_ssh_agent.config import SSHConfig
from persistent_ssh_agent.core import PersistentSSHAgent


@pytest.fixture
def ssh_key_content():
    """Sample SSH key content for testing."""
    return """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture
def protected_ssh_key_content():
    """Sample password-protected SSH key content for testing."""
    return """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0AAAAGAAAABD+UwXz5w
-----END OPENSSH PRIVATE KEY-----"""


def test_config_identity_file():
    """Test loading identity file from config."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("test key content")
        temp_file.flush()
        
        config = SSHConfig(identity_file=temp_file.name)
        agent = PersistentSSHAgent(config=config)
        
        identity_file = agent._get_identity_file("github.com")
        assert identity_file == temp_file.name
        
        os.unlink(temp_file.name)


def test_config_identity_content(ssh_key_content):
    """Test loading identity content from config."""
    config = SSHConfig(identity_content=ssh_key_content)
    agent = PersistentSSHAgent(config=config)
    
    identity_file = agent._get_identity_file("github.com")
    assert identity_file is not None
    assert os.path.exists(identity_file)
    
    with open(identity_file, 'r') as f:
        content = f.read()
        assert content == ssh_key_content
    
    os.unlink(identity_file)


def test_config_with_passphrase(protected_ssh_key_content):
    """Test loading identity with passphrase from config."""
    config = SSHConfig(
        identity_content=protected_ssh_key_content,
        identity_passphrase="testpass"
    )
    agent = PersistentSSHAgent(config=config)
    
    identity_file = agent._get_identity_file("github.com")
    assert identity_file is not None
    assert os.path.exists(identity_file)
    
    # Start SSH agent with the protected key
    assert agent._start_ssh_agent(identity_file)
    
    os.unlink(identity_file)


def test_env_identity_file():
    """Test loading identity file from environment variable."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("test key content")
        temp_file.flush()
        
        os.environ["SSH_IDENTITY_FILE"] = temp_file.name
        agent = PersistentSSHAgent()
        
        identity_file = agent._get_identity_file("github.com")
        assert identity_file == temp_file.name
        
        del os.environ["SSH_IDENTITY_FILE"]
        os.unlink(temp_file.name)


def test_env_identity_content(ssh_key_content):
    """Test loading identity content from environment variable."""
    os.environ["SSH_IDENTITY_CONTENT"] = ssh_key_content
    agent = PersistentSSHAgent()
    
    identity_file = agent._get_identity_file("github.com")
    assert identity_file is not None
    assert os.path.exists(identity_file)
    
    with open(identity_file, 'r') as f:
        content = f.read()
        assert content == ssh_key_content
    
    del os.environ["SSH_IDENTITY_CONTENT"]
    os.unlink(identity_file)


def test_env_with_passphrase(protected_ssh_key_content):
    """Test loading identity with passphrase from environment."""
    os.environ["SSH_IDENTITY_CONTENT"] = protected_ssh_key_content
    os.environ["SSH_KEY_PASSPHRASE"] = "testpass"
    agent = PersistentSSHAgent()
    
    identity_file = agent._get_identity_file("github.com")
    assert identity_file is not None
    assert os.path.exists(identity_file)
    
    # Start SSH agent with the protected key
    assert agent._start_ssh_agent(identity_file)
    
    del os.environ["SSH_IDENTITY_CONTENT"]
    del os.environ["SSH_KEY_PASSPHRASE"]
    os.unlink(identity_file)
